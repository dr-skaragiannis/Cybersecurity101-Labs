# Learning Path 1 — Introduction to Cybersecurity

**Thirteen VulnHub machines, in order, from "I have never opened a terminal" to
"I can chain four vulnerabilities into root."**

This is a *curriculum*, not a list. Each machine was chosen to introduce attack
types the previous ones did not, so by the end you have practised almost every
class of bug a junior penetration tester meets — web, service, credential and
Linux privilege-escalation attacks — on machines that are genuinely beginner-rated.

Everything here is **legal, offline and safe**: every target is a virtual machine
you download and run on your own computer, deliberately built to be attacked.

> **Read [`00-Before-You-Start.md`](00-Before-You-Start.md) first.** It covers the
> lab setup, the ground rules, and the study method that makes this path work.

---

## Who this is for

You should be comfortable using a computer and willing to type commands you do not
yet understand. You do **not** need to know networking, Linux or programming.

You **do** need to be willing to do the work in order. Machine 1 exists to teach
you how to read an `nmap` scan; machine 13 assumes you can. Skipping ahead is the
single most common way people stall.

| If you… | Start at |
| --- | --- |
| have never used a terminal | [`00-Before-You-Start.md`](00-Before-You-Start.md), then Machine 1 |
| know Linux but not networking | [`01-Foundations-Networking-and-Recon.md`](01-Foundations-Networking-and-Recon.md) |
| can already run nmap and read it | Machine 1 anyway — it is short, and the *method* matters more than the difficulty |
| have done a few VulnHub boxes before | Use the [coverage matrix](#what-you-will-have-practised) to find the attack types you have *not* met, and jump to those machines |

---

## How to study each machine

The walkthroughs in [`labs/`](../labs/) are complete — every command, every line of
output, every explanation. That is a trap: **reading a walkthrough feels like
learning and is not.** Use this loop for every machine.

1. **Read the theory module first.** Each machine below lists which one. Skimming
   it takes 20 minutes and turns the machine from a puzzle into an exercise.
2. **Snapshot the VM before you touch it.** You will break these machines. Being
   able to rewind in ten seconds is the difference between experimenting and
   being afraid to.
3. **Answer the pre-lab questions** on the machine's lesson card *before* opening
   the walkthrough. They tell you what to look for.
4. **Attempt it blind, with a time box.** 45–60 minutes for machines 1–5, up to
   2–3 hours later on. Take notes as you go — what you tried, what happened.
5. **Use the hints ladder when stuck.** Each lesson card has progressive hints,
   from "look at that port again" to the actual answer. Stop at the first hint
   that unblocks you. *Using hint 1 is learning; jumping to hint 5 is not.*
6. **Only then read the walkthrough.** Read it to compare against what you did —
   not to find out what to do.
7. **Reproduce every command yourself**, including the ones you got right. Type
   them; do not paste. Take the screenshots in the walkthrough's checklist.
8. **Answer the post-lab questions.** If you cannot, you have not finished.
9. **Write one page.** What the machine was, how you got in, how you got root,
   and — most importantly — **what the administrator should have done**. This is
   the habit that separates a person who runs tools from a person who does the job.

> Expect machines 1–4 to take a few hours each including the reading, and the
> later ones a full evening. Thirteen machines is roughly **40–70 hours**. That is
> a real course, and it is worth it.

---

## The thirteen machines

Difficulty bands come from the repository-wide
[scale](../README.md#difficulty-scale). Every machine here is band **2 (Very
Easy)** or band **3 (Easy)** — this path never leaves beginner territory, it just
walks you across the whole of it.

| # | Machine | Folder | Band | What it introduces | Est. |
| --: | --- | --- | :-: | --- | :-: |
| [1](Machines/01-basic-pentesting-1.md) | **Basic Pentesting: 1** | [`2-001`](../labs/2-001-basic-pentesting-1/README.md) | 2 | The whole lifecycle on one box: recon, content discovery, **anonymous FTP**, a **published service backdoor** (EDB-15662 / CVE-2010-20103), **WordPress default credentials**, and a world-writable `/etc/passwd` | 3–4 h |
| [2](Machines/02-cybersploit-1.md) | **CyberSploit: 1** | [`2-002`](../labs/2-002-cybersploit-1/README.md) | 2 | **Encoding vs encryption** (base64, binary), the `searchsploit` → Exploit-DB research workflow, and your first **kernel exploit** (overlayfs, Dirty COW) | 3–4 h |
| [3](Machines/03-dc-1.md) | **DC: 1** | [`2-003`](../labs/2-003-dc-1/README.md) | 2 | Exploiting a **CMS CVE** (Drupalgeddon, CVE-2014-3704) with **Metasploit**, reading DB credentials out of a config file, and **SUID** privilege escalation | 3–5 h |
| [4](Machines/04-dc-2.md) | **DC: 2** | [`2-004`](../labs/2-004-dc-2/README.md) | 2 | **Building a targeted wordlist** with `cewl`, WordPress user enumeration, **escaping a restricted shell (`rbash`)**, and `sudo` abuse via GTFOBins | 4–6 h |
| [5](Machines/05-kioptrix-level-1-1.md) | **Kioptrix: Level 1** | [`3-046`](../labs/3-046-kioptrix-level-1-1/README.md) | 3 | **Legacy service exploitation**: Apache mod_ssl (OpenFuck, CVE-2002-0082) and Samba (CVE-2003-0201), compiling an old exploit, working on a 2010-era Linux | 4–6 h |
| [6](Machines/06-bossplayersctf-1.md) | **bossplayersCTF: 1** | [`3-016`](../labs/3-016-bossplayersctf-1/README.md) | 3 | **OS command injection** in its cleanest form, information disclosure in page source, deliberately misleading decoy files, SUID shell escape | 3–4 h |
| [7](Machines/07-mr-robot-1.md) | **Mr-Robot: 1** | [`3-053`](../labs/3-053-mr-robot-1/README.md) | 3 | **Content discovery** (`robots.txt`, `dirb`), username enumeration from verbose errors, **WordPress Theme Editor → code execution**, cracking unsalted MD5 | 4–6 h |
| [8](Machines/08-empire-breakout.md) | **Empire: Breakout** | [`3-028`](../labs/3-028-empire-breakout/README.md) | 3 | **Brainfuck** obfuscation, **SMB null sessions and RID cycling**, admin consoles (Webmin/Usermin), and **file capabilities** (`getcap`, `cap_dac_read_search`) | 4–5 h |
| [9](Machines/09-cengbox-1.md) | **CengBox: 1** | [`3-018`](../labs/3-018-cengbox-1/README.md) | 3 | **SQL injection properly** — boolean-blind, time-blind and UNION — plus an extension-only **upload filter**, a world-writable script run by **root cron**, and an `lxd` group escape | 5–8 h |
| [10](Machines/10-pwnlab-init.md) | **PwnLab: init** | [`3-057`](../labs/3-057-pwnlab-init/README.md) | 3 | **Local File Inclusion** three ways (GET parameter, cookie, `php://filter` source disclosure), **upload filter bypass with a GIF magic header**, a SUID chain, and **PATH hijacking** | 5–8 h |
| [11](Machines/11-photographer-1.md) | **Photographer: 1** | [`3-055`](../labs/3-055-photographer-1/README.md) | 3 | **Anonymous SMB** leaking real correspondence, inferring credentials from a leaked email, a **CMS upload bypass** (Koken, EDB 48706), and SUID on a PHP interpreter | 4–6 h |
| [12](Machines/12-symfonos-1.md) | **symfonos: 1** | [`3-062`](../labs/3-062-symfonos-1/README.md) | 3 | **SMTP log poisoning → RCE**, reading an unprotected **Postfix mailbox**, vulnerable WordPress plugins, and SUID calling a binary by bare name | 5–8 h |
| [13](Machines/13-hackinos-1.md) | **HackInOS: 1** | [`3-040`](../labs/3-040-hackinos-1/README.md) | 3 | **Reverse-engineering an upload filter from the developer's own published source**, a predictable `md5($name.rand(1,100))` filename, and a **Docker container escape** to host root | 6–9 h |

**Click the number in the first column** to open that machine's *lesson card*:
why it is in the path, its learning objectives, the attack classes it covers, what to
read first, pre-lab questions, a **five-rung hints ladder** (rung 1 is a nudge, rung 5
is the full answer, each hidden behind a fold), post-lab review questions and a
defensive fix table. All thirteen live in [`Machines/`](Machines/).

---

## What you will have practised

The point of the ordering is coverage. This is what each attack class is
introduced by, and where it recurs:

| Attack class | Introduced | Practised again in |
| --- | :-: | --- |
| Host discovery, port scanning, service/version detection | 1 | every machine |
| Web content discovery & directory brute forcing | 1 | 7, 9 |
| Information disclosure (comments, backups, exposed configs, leaked docs) | 1 | 2, 6, 7, 8, 10, 11, 12, 13 |
| Anonymous FTP & file-service abuse | 1 | 5 |
| Published service backdoors / legacy CVEs | 1 | 3, 5, 11 |
| **Encoding vs hashing vs encryption** | 2 | 6, 7, 8 |
| Exploit research (`searchsploit`, Exploit-DB, CVE/CVSS) | 2 | 3, 5, 11 |
| Kernel exploitation | 2 | 5 |
| CMS exploitation — Drupal | 3 | — |
| CMS exploitation — WordPress | 4 | 7, 12 |
| CMS exploitation — other (Koken, custom admin panels) | 9 | 11, 13 |
| **Metasploit** and Meterpreter | 3 | 5 |
| Building targeted wordlists (`cewl`) | 4 | 7, 9 |
| **Restricted-shell (`rbash`) escape** | 4 | — |
| **OS command injection** | 6 | 9, 10 (in a SUID helper), 12 (into a mailbox) |
| **SQL injection** (blind, time-based, UNION) | 9 | 10 |
| **Local File Inclusion** & `php://filter` | 10 | 12 |
| **Log poisoning** (SMTP) | 12 | — |
| **File upload → web shell**, and filter bypasses | 9 | 10, 11, 13 |
| SMB null sessions, share enumeration, RID cycling | 8 | 11, 12 |
| Password cracking (unsalted MD5, MD5-crypt) | 1 | 7, 13 |
| Credential reuse and spraying | 1 | 4, 7, 9, 10, 11, 12, 13 |
| **SUID** abuse | 3 | 6, 7, 10, 11, 12, 13 |
| **`sudo` / GTFOBins** abuse | 1 | 4, 9 |
| **File capabilities** (`getcap`) | 8 | 13 (`docker` group) |
| Writable files, world-writable scripts & readable secrets | 1 | 2, 8, 9 |
| **Cron job** abuse | 9 | — |
| `/etc/passwd` overwrite | 1 | — |
| **PATH hijacking** | 10 | 12, 13 |
| **Container / `lxd` / `docker` group escape** | 9 | 13 |
| Reverse shells and **TTY upgrades** | 1 | every machine that gets a shell |

### Deliberately *not* in this path

These are intermediate-to-advanced classes. They are documented in
[`docs/CONCEPTS.md`](../docs/CONCEPTS.md) and practised on higher-band machines,
and they belong to Learning Path 2:

buffer overflows and writing your own exploits · insecure deserialisation ·
JWT and session attacks · XSS and CSRF · LDAP injection · IDOR and broken access
control · Active Directory · tunnelling and pivoting between networks · Windows
privilege escalation.

If you finish this path and want a bridge, these band-3 machines each add exactly
one missing class:

| Machine | Adds |
| --- | --- |
| [`3-039-ha-wordy`](../labs/3-039-ha-wordy/README.md) | **CSRF → authentication bypass**, and RFI |
| [`3-064-symfonos-52`](../labs/3-064-symfonos-52/README.md) | **LDAP injection** and anonymous LDAP bind |
| [`3-020-darkhole-1`](../labs/3-020-darkhole-1/README.md) | **IDOR** / parameter tampering in a password reset |
| [`3-063-symfonos-2`](../labs/3-063-symfonos-2/README.md) | **SSH port forwarding** to reach a localhost-only app |
| [`3-060-serial-1`](../labs/3-060-serial-1/README.md) | **PHP object injection / insecure deserialisation** |

Then the next step up is band 4 (Medium) — start with
[`4-070-basic-pentesting-2`](../labs/4-070-basic-pentesting-2/README.md) and
[`4-075-dc-9`](../labs/4-075-dc-9/README.md), or browse the whole collection in
difficulty order in [`docs/CATALOG.md`](../docs/CATALOG.md).

---

## The theory modules

Read the module **before** the machines that use it. Each one links into
[`docs/CONCEPTS.md`](../docs/CONCEPTS.md) for the full treatment — the modules tell
you what matters for *this* path, the primer explains everything.

| Module | Read before | Covers |
| --- | --- | --- |
| [`00-Before-You-Start.md`](00-Before-You-Start.md) | Machine 1 | Lab setup, ground rules, terminal basics, note-taking, the study method |
| [`01-Foundations-Networking-and-Recon.md`](01-Foundations-Networking-and-Recon.md) | Machines 1–5 | IP/CIDR, MAC/ARP, ports, the TCP handshake, how nmap works, enumeration |
| [`02-Web-Attacks.md`](02-Web-Attacks.md) | Machines 1, 4, 6, 7, 9, 10, 11, 12, 13 | Content discovery, HTTP status codes, SQLi, LFI, command injection, file upload and its bypasses |
| [`03-Service-and-Network-Attacks.md`](03-Service-and-Network-Attacks.md) | Machines 1, 5, 8, 11, 12 | FTP, SMB, SMTP, SSH, legacy services, and how to enumerate each |
| [`04-Credentials-and-Cracking.md`](04-Credentials-and-Cracking.md) | Machines 1, 2, 4, 7, 9, 11, 13 | Wordlists, hashing vs encoding, John/hashcat, reuse, spraying |
| [`05-Linux-Privilege-Escalation.md`](05-Linux-Privilege-Escalation.md) | Machines 1, 3, 6, 7, 8, 9, 10, 11, 12, 13 | `sudo`, SUID, capabilities, cron, writable files, `/etc/passwd`, kernel, PATH hijacking |
| [`06-Shells-Persistence-and-Escapes.md`](06-Shells-Persistence-and-Escapes.md) | Machines 1, 4, 6, 9, 10, 12, 13 | Reverse vs bind shells, TTY upgrades, `rbash` escapes, container escapes, cleanup and reporting |
| [`07-Permissions-and-Access-Control.md`](07-Permissions-and-Access-Control.md) | Machines 1, 3, 6, 8, 9, 10, 11 | The DAC model in full (bits, `umask`, special bits, ACLs, `chattr`, capabilities) and **MAC** — SELinux and AppArmor |
| [`08-Identity-Authentication-and-PAM.md`](08-Identity-Authentication-and-PAM.md) | Machines 1, 4, 7, 9, 10, 11, 12 | `/etc/passwd`·`shadow`·`group`, `su` vs `sudo`, the **PAM** stack, SSH key authentication |
| [`09-Cryptography-GPG-and-Encryption.md`](09-Cryptography-GPG-and-Encryption.md) | Machine 2, and the extended track | Encoding vs hashing vs **encryption**; GPG **key issuance**, signing, symmetric files, `openssl enc`, LUKS |
| [`10-Firewalls-and-Sandboxing.md`](10-Firewalls-and-Sandboxing.md) | Machines 5, 8, and the extended track | iptables/nftables/ufw, ingress vs **egress**, port knocking, and sandboxing (systemd, seccomp, MAC) |
| [`11-Malware-Analysis-and-YARA.md`](11-Malware-Analysis-and-YARA.md) | Extended track / DFIR interest | Static vs dynamic analysis, `strings`/`binwalk`, IOCs, and writing **YARA** rules |

### The extended track (modules 07–11)

Modules 00–06 teach the *offensive* lifecycle on beginner boot2root machines. Modules
**07–11** add the **systems and defensive** half of the discipline — permissions and
MAC, identity and PAM, cryptography and key management, firewalls and sandboxing, and
malware analysis. They stand alone as theory, and each is best *practised* on the
band-3/4 machines below (already written up in [`labs/`](../labs/)):

| Module | Practise on | Why that machine |
| --- | --- | --- |
| **07 — Permissions & MAC** | [`3-068-w1r3s-101`](../labs/3-068-w1r3s-101/README.md), [`3-031-fristileaks-13`](../labs/3-031-fristileaks-13/README.md), [`3-028-empire-breakout`](../labs/3-028-empire-breakout/README.md) | world-writable `/etc/shadow`; **SELinux** `httpd_t`; **file capabilities** |
| **08 — Identity & PAM** | [`3-019-corrosion-1`](../labs/3-019-corrosion-1/README.md), [`3-059-raven-1`](../labs/3-059-raven-1/README.md), [`4-082-ha-narak`](../labs/4-082-ha-narak/README.md) | `su`/`sudo`/PAM-driven login behaviour; account and login-flow misconfiguration |
| **09 — Crypto & GPG** | [`4-073-dc-7`](../labs/4-073-dc-7/README.md), [`3-056-prime-1`](../labs/3-056-prime-1/README.md) | GPG-encrypted backup + **passphrase leaked in cron mail**; `openssl enc` with a hardcoded key |
| **10 — Firewalls & Sandboxing** | [`4-086-sickos-12`](../labs/4-086-sickos-12/README.md), [`6-098-lord-of-the-root-101`](../labs/6-098-lord-of-the-root-101/README.md) | **egress firewall** (only 443/8080 out); **port knocking** |
| **11 — Malware Analysis & YARA** | [`5-097-tr0ll-2`](../labs/5-097-tr0ll-2/README.md), [`2-002-cybersploit-1`](../labs/2-002-cybersploit-1/README.md) | metadata forensics and `binwalk`; decoding obfuscated blobs |

> **Why these are modules, not new machines.** The 13 path machines are chosen for a
> clean beginner *offence* chain. The extended topics are best learned as a focused
> read followed by practising on a machine that already exists — so the path stays
> honest about what is beginner-rated while still covering the systems side.

**Every module ends with an *Annotated command reference*, and every machine card ends
with *The commands, annotated*.** Those sections walk through each command you will type
in that stage — token by token: what each flag means, the real terminal output you should
see, and a line-by-line reading of that output, plus what the usual failure messages mean.
Read the module for the *concepts*, then read its annotated reference while you are at the
keyboard. If a command's output on your box differs from the one shown, the annotated
section tells you whether the difference matters.

### Recommended step-by-step study order (interleaving theory & labs)

To get the maximum benefit without reading all twelve theory modules up front, follow this five-phase sequence that pairs each theory module immediately with the machines that practise it:

| Phase | Step | Read (Theory) | Practise (Lesson Card → Full Walkthrough) | Core skill unlocked |
| --- | --: | --- | --- | --- |
| **Phase 0 — Lab & Terminal Setup** | 0 | [`docs/LAB-SETUP.md`](../docs/LAB-SETUP.md) · [`docs/TOOLS.md`](../docs/TOOLS.md) · [`00-Before-You-Start.md`](00-Before-You-Start.md) | — | Isolated host-only lab, snapshots, Linux CLI, pipes/redirection |
| **Phase 1 — Recon, Enumeration & First Root (Band 2)** | 1 | [`01-Foundations-Networking-and-Recon.md`](01-Foundations-Networking-and-Recon.md) | [Card 01](Machines/01-basic-pentesting-1.md) → [`2-001-basic-pentesting-1`](../labs/2-001-basic-pentesting-1/README.md) | `nmap`, `/etc/hosts` VHOST, service backdoors, WP admin, writable `/etc/passwd` |
| | 2 | [`04-Credentials-and-Cracking.md`](04-Credentials-and-Cracking.md) (§1–2) | [Card 02](Machines/02-cybersploit-1.md) → [`2-002-cybersploit-1`](../labs/2-002-cybersploit-1/README.md) | Encoding vs hashing vs encryption, `searchsploit`, kernel exploit workflow |
| | 3 | [`02-Web-Attacks.md`](02-Web-Attacks.md) (§7) · [`05-Linux-Privilege-Escalation.md`](05-Linux-Privilege-Escalation.md) (§2) | [Card 03](Machines/03-dc-1.md) → [`2-003-dc-1`](../labs/2-003-dc-1/README.md) | CMS CVE (Drupalgeddon), config-file DB secrets, SUID `find -p` |
| | 4 | [`04-Credentials-and-Cracking.md`](04-Credentials-and-Cracking.md) (§3–5) · [`06-Shells-Persistence-and-Escapes.md`](06-Shells-Persistence-and-Escapes.md) (§3) | [Card 04](Machines/04-dc-2.md) → [`2-004-dc-2`](../labs/2-004-dc-2/README.md) | Targeted wordlists (`cewl`), `wpscan`, `rbash` escape, `sudo` GTFOBins |
| **Phase 2 — Service, Web & Capability Chains (Band 3 early)** | 5 | [`03-Service-and-Network-Attacks.md`](03-Service-and-Network-Attacks.md) | [Card 05](Machines/05-kioptrix-level-1-1.md) → [`3-046-kioptrix-level-1-1`](../labs/3-046-kioptrix-level-1-1/README.md) | SMB/Samba fingerprinting, `trans2open`, legacy C exploit compilation |
| | 6 | [`02-Web-Attacks.md`](02-Web-Attacks.md) (§1–2, §5) · [`06-Shells-Persistence-and-Escapes.md`](06-Shells-Persistence-and-Escapes.md) (§1–2) | [Card 06](Machines/06-bossplayersctf-1.md) → [`3-016-bossplayersctf-1`](../labs/3-016-bossplayersctf-1/README.md) | Multi-layer base64, OS command injection, reverse shells & TTY upgrade |
| | 7 | [`02-Web-Attacks.md`](02-Web-Attacks.md) (§2, §7) · [`04-Credentials-and-Cracking.md`](04-Credentials-and-Cracking.md) (§4) | [Card 07](Machines/07-mr-robot-1.md) → [`3-053-mr-robot-1`](../labs/3-053-mr-robot-1/README.md) | Wordlist hygiene (`sort -u`), WP Theme Editor RCE, raw-MD5 cracking, SUID `nmap` |
| | 8 | [`03-Service-and-Network-Attacks.md`](03-Service-and-Network-Attacks.md) (§2) · [`05-Linux-Privilege-Escalation.md`](05-Linux-Privilege-Escalation.md) (§3) | [Card 08](Machines/08-empire-breakout.md) → [`3-028-empire-breakout`](../labs/3-028-empire-breakout/README.md) | SMB RID cycling (`enum4linux`), Usermin vs Webmin, Linux capabilities (`getcap`) |
| **Phase 3 — SQLi, LFI, Upload Bypasses, Cron/PATH & Containers (Band 3 late)** | 9 | [`02-Web-Attacks.md`](02-Web-Attacks.md) (§3, §6) · [`05-Linux-Privilege-Escalation.md`](05-Linux-Privilege-Escalation.md) (§4–5) | [Card 09](Machines/09-cengbox-1.md) → [`3-018-cengbox-1`](../labs/3-018-cengbox-1/README.md) | `sqlmap` login bypass & DB dump, `.ceng` upload bypass, `pspy` cron hunting |
| | 10 | [`02-Web-Attacks.md`](02-Web-Attacks.md) (§4, §6) · [`05-Linux-Privilege-Escalation.md`](05-Linux-Privilege-Escalation.md) (§7) | [Card 10](Machines/10-pwnlab-init.md) → [`3-057-pwnlab-init`](../labs/3-057-pwnlab-init/README.md) | `php://filter` LFI source leak, GIF magic-byte polyglot, `PATH` hijacking |
| | 11 | [`03-Service-and-Network-Attacks.md`](03-Service-and-Network-Attacks.md) (§2) · [`02-Web-Attacks.md`](02-Web-Attacks.md) (§6) | [Card 11](Machines/11-photographer-1.md) → [`3-055-photographer-1`](../labs/3-055-photographer-1/README.md) | Anonymous SMB mail leak, Koken upload bypass (EDB-48706), SUID `php7.2 -p` |
| | 12 | [`03-Service-and-Network-Attacks.md`](03-Service-and-Network-Attacks.md) (§3) · [`02-Web-Attacks.md`](02-Web-Attacks.md) (§4) | [Card 12](Machines/12-symfonos-1.md) → [`3-062-symfonos-1`](../labs/3-062-symfonos-1/README.md) | WP plugin LFI (`mail-masta`), SMTP log poisoning → RCE, SUID `PATH` hijack |
| | 13 | [`06-Shells-Persistence-and-Escapes.md`](06-Shells-Persistence-and-Escapes.md) (§5–7) · [`05-Linux-Privilege-Escalation.md`](05-Linux-Privilege-Escalation.md) (§8) | [Card 13](Machines/13-hackinos-1.md) → [`3-040-hackinos-1`](../labs/3-040-hackinos-1/README.md) | Source-assisted upload bypass, internal Docker DB pivot, `docker` group host escape |
| **Phase 4 — Extended Systems & Defensive Track** | 14–18 | [`07`](07-Permissions-and-Access-Control.md) → [`08`](08-Identity-Authentication-and-PAM.md) → [`09`](09-Cryptography-GPG-and-Encryption.md) → [`10`](10-Firewalls-and-Sandboxing.md) → [`11`](11-Malware-Analysis-and-YARA.md) | Paired Band 3/4 labs (`3-068-w1r3s-101`, `3-031-fristileaks-13`, `3-019-corrosion-1`, `4-073-dc-7`, `4-086-sickos-12`, `5-097-tr0ll-2`) | DAC/MAC (SELinux & AppArmor), PAM, GPG & crypto, firewalls/egress/sandboxing, YARA |
| **Phase 5 — Bridge Labs to Intermediate** | 19+ | [`docs/CONCEPTS.md`](../docs/CONCEPTS.md) (§13, §16–18) | `3-039-ha-wordy` → `3-064-symfonos-52` → `3-020-darkhole-1` → `3-063-symfonos-2` → `3-060-serial-1` → `4-070-basic-pentesting-2` → `4-075-dc-9` | CSRF/RFI, LDAPi, IDOR, SSH port forwarding, deserialisation, Band 4 chains |


---

## Progress tracker

Copy this into your notes and tick as you go. Do not tick a machine until you have
written your one-page report for it.

- [ ] 00 — Before you start *(lab built, snapshot discipline, ethics read)*
- [ ] 01 — Basic Pentesting: 1
- [ ] 02 — CyberSploit: 1
- [ ] 03 — DC: 1
- [ ] 04 — DC: 2
- [ ] 05 — Kioptrix: Level 1
- [ ] 06 — bossplayersCTF: 1
- [ ] 07 — Mr-Robot: 1
- [ ] 08 — Empire: Breakout
- [ ] 09 — CengBox: 1
- [ ] 10 — PwnLab: init
- [ ] 11 — Photographer: 1
- [ ] 12 — symfonos: 1
- [ ] 13 — HackInOS: 1
- [ ] One-page report written for all thirteen
- [ ] Can explain, without notes: what a port scan does at packet level · why a reverse shell beats a bind shell · the privesc checklist in order · the difference between encoding, hashing and encryption

---

## Ground rules

These are not boilerplate. Read [`00-Before-You-Start.md`](00-Before-You-Start.md)
for why each one matters.

1. **Only attack machines you own or are explicitly authorised to test.** Every
   target in this path is a VM you downloaded and booted yourself, on a host-only
   network. Never point these tools at anything else — not a website, not a
   neighbour's Wi-Fi, not a corporate network where you have a job but no written
   authorisation.
2. **Keep the lab isolated.** Host-only or internal networking, so the VMs cannot
   reach the internet or your LAN.
3. **The techniques here are the same ones attackers use.** The only difference
   between this and a crime is permission and intent. Everything you learn has a
   defensive counterpart, and each walkthrough ends with one — read those too.
4. **Do not skip the defensive sections.** Being able to say *"here is how you
   would have stopped me"* is what makes this a profession rather than a hobby.

---

## You have completed Learning Path 1 when…

1. You have written **13 one-page reports** (one per machine, including the root cause and the blue-team fix for every vulnerability).
2. You can explain **what every flag does** in `nmap`, `sqlmap`, `john`, `hashcat`, `hydra`, `wpscan`, `ffuf`, `smbclient`, `getcap`, and `find -perm`.
3. You can read `id` output and immediately state whether you hold root via `uid=0` or `euid=0` — and why a shell without `-p` drops `euid=0`.
4. You know the **privilege-escalation checklist** in order from memory: `sudo -l` → SUID → capabilities → cron/`pspy` → writable files → privileged groups (`docker`/`lxd`) → kernel.
5. You have re-solved at least **two machines from a clean snapshot without opening the walkthrough**.

---

> 🩺 **On Windows?** Antivirus software may flag educational reverse-shell snippets inside Markdown files as false positives. See [Module 00, §9.11](00-Before-You-Start.md), [`docs/LAB-SETUP.md` §10](../docs/LAB-SETUP.md#10-windows--antivirus--keep-your-lab-files-from-being-deleted), and the [Repository Audit (`docs/AUDIT.md`)](../docs/AUDIT.md).

---

_Part of the [Cybersecurity101-Labs](../README.md) collection ·
[reading order](../docs/INDEX.md) · [Greek edition (`Μαθησιακή Διαδρομή 1`)](../%CE%9C%CE%B1%CE%B8%CE%B7%CF%83%CE%B9%CE%B1%CE%BA%CE%AE%20%CE%94%CE%B9%CE%B1%CE%B4%CF%81%CE%BF%CE%BC%CE%AE%201%20-%20%CE%95%CE%B9%CF%83%CE%B1%CE%B3%CF%89%CE%B3%CE%AE%20%CF%83%CF%84%CE%B7%CE%BD%20%CE%9A%CF%85%CE%B2%CE%B5%CF%81%CE%BD%CE%BF%CE%B1%CF%83%CF%86%CE%AC%CE%BB%CE%B5%CE%B9%CE%B1/README.md) · [catalog](../docs/CATALOG.md) ·
[concepts primer](../docs/CONCEPTS.md) · [all walkthroughs by difficulty](../docs/PROGRESS.md)._
