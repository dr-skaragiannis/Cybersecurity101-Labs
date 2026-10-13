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

## 6. What to read next

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

_Back to [Learning Path 1](README.md) · next: [01 — Foundations](01-Foundations-Networking-and-Recon.md)._
