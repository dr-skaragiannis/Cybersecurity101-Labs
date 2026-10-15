# Cybersecurity101-Labs — VulnHub Walkthroughs

Educational, **beginner-friendly** walkthroughs for the vulnerable virtual machines
(OVAs) published on [VulnHub](https://vulnhub.com/).

Every writeup explains **what** we run, **why** we run it, and **how to read the
output** — starting from the absolute basics. The goal is that a student who has
never opened a terminal can follow along, understand the methodology, and reproduce
the result in their own lab.

Writeups do not just list commands. Each one is broken up by **📖 Concept boxes**
that stop and explain the underlying idea at the point it first comes up — what
reconnaissance actually is, what a port scan does at the packet level, where a
wordlist comes from and why it beats guessing, what a reverse shell is and why we
never use a bind shell, how `sudo -l` is meant to be read. Every box links to
[`docs/CONCEPTS.md`](docs/CONCEPTS.md) for the full treatment.

> **New to this? Read [`docs/CONCEPTS.md`](docs/CONCEPTS.md) first.** It is the
> repository-wide fundamentals primer: networking, how nmap works, enumeration,
> wordlists, encoding vs hashing vs encryption, shells, and Linux privilege
> escalation. Every command in every walkthrough is explained against it.

> ### ★ Want a course, not a catalog?
>
> **[Learning Path 1 — Introduction to Cybersecurity](Learning%20Path%201%20-%20Introduction%20to%20Cybersecurity/README.md)** is a complete,
> ordered beginner curriculum: **13 hand-picked machines** (the easiest rated labs in
> the repository, difficulty bands 2 and 3 only), **12 theory-and-practice modules (`00–11`)**
> (7 offensive core modules `00–06` plus 5 systems & defence modules `07–11`),
> and a **lesson card per machine** with learning objectives, pre-lab questions, a
> five-rung hints ladder, review questions, community writeup notes and a defensive fix table. It was chosen by
> reading every candidate writeup, so the 13 boxes between them cover **30+ distinct
> attack classes** — from anonymous FTP and default credentials through SQL injection,
> LFI, SMTP log poisoning and file-upload bypasses, to SUID abuse, `PATH` hijacking,
> Linux capabilities and a Docker container escape.
>
> Start at [00 — Before You Start](Learning%20Path%201%20-%20Introduction%20to%20Cybersecurity/00-Before-You-Start.md) if you have never run a
> lab VM before, or jump straight to [the path overview](Learning%20Path%201%20-%20Introduction%20to%20Cybersecurity/README.md).
>
> **Μιλάς Ελληνικά;** Η ίδια διαδρομή υπάρχει ολοκληρωμένη στα Ελληνικά:
> **[Μαθησιακή Διαδρομή 1 — Εισαγωγή στην Κυβερνοασφάλεια](%CE%9C%CE%B1%CE%B8%CE%B7%CF%83%CE%B9%CE%B1%CE%BA%CE%AE%20%CE%94%CE%B9%CE%B1%CE%B4%CF%81%CE%BF%CE%BC%CE%AE%201%20-%20%CE%95%CE%B9%CF%83%CE%B1%CE%B3%CF%89%CE%B3%CE%AE%20%CF%83%CF%84%CE%B7%CE%BD%20%CE%9A%CF%85%CE%B2%CE%B5%CF%81%CE%BD%CE%BF%CE%B1%CF%83%CF%86%CE%AC%CE%BB%CE%B5%CE%B9%CE%B1/README.md)**
> (ξεκινήστε από το [00 — Πριν Ξεκινήσεις](%CE%9C%CE%B1%CE%B8%CE%B7%CF%83%CE%B9%CE%B1%CE%BA%CE%AE%20%CE%94%CE%B9%CE%B1%CE%B4%CF%81%CE%BF%CE%BC%CE%AE%201%20-%20%CE%95%CE%B9%CF%83%CE%B1%CE%B3%CF%89%CE%B3%CE%AE%20%CF%83%CF%84%CE%B7%CE%BD%20%CE%9A%CF%85%CE%B2%CE%B5%CF%81%CE%BD%CE%BF%CE%B1%CF%83%CF%86%CE%AC%CE%BB%CE%B5%CE%B9%CE%B1/00-%CE%A0%CF%81%CE%B9%CE%BD-%CE%9E%CE%B5%CE%BA%CE%B9%CE%BD%CE%AE%CF%83%CE%B5%CE%B9%CF%82.md)). Οι εντολές, τα εργαλεία,
> οι σημαίες και τα πραγματικά αποτελέσματα τερματικού παραμένουν στα Αγγλικά —
> όπως εμφανίζονται σε οποιοδήποτε πραγματικό σύστημα· όλη η επεξήγηση, κάθε
> εννοιολογικό κουτί, κάθε ερώτηση και κάθε αμυντική σημείωση είναι στα Ελληνικά.

> This repository indexes **all 708 VulnHub virtual machines** in
> [`docs/CATALOG.md`](docs/CATALOG.md). Full walkthroughs are being added
> machine-by-machine into [`labs/`](labs/).

> ### 🩺 On Windows? Read this first.
>
> Antivirus software flags the **educational** reverse-shell payloads inside a few
> walkthroughs and **deletes those files**, so they appear to be missing from your
> clone. It is a false positive. The fix (a one-time folder exclusion) and the
> rest of the repository audit are in
> **[`docs/AUDIT.md`](docs/AUDIT.md)** (English) /
> **[`docs/ΑΝΑΘΕΩΡΗΣΗ.md`](docs/ΑΝΑΘΕΩΡΗΣΗ.md)** (Ελληνικά), and in
> [`docs/LAB-SETUP.md` §10](docs/LAB-SETUP.md#10-windows--antivirus--keep-your-lab-files-from-being-deleted).

> ### 🧭 Not sure where to start?
>
> **[`docs/INDEX.md`](docs/INDEX.md)** (English) / **[`docs/ΕΥΡΕΤΗΡΙΟ.md`](docs/ΕΥΡΕΤΗΡΙΟ.md)**
> (Ελληνικά) puts **everything** — setup, the fundamentals primer, both curriculum
> editions, the theory modules, the 13 machines and the full catalog — into a single
> logical reading order.

---

## Legal & ethical use

VulnHub VMs are **intentionally vulnerable**. They are designed to be attacked,
but **only inside an isolated lab**:

- Run them on a **host-only** or **NAT** virtual network.
- **Never** expose a lab VM to the public internet or a production network.
- Only ever test systems **you own** or have **written authorisation** to test.

Unauthorised access to computer systems is illegal in virtually every country.
Use these skills responsibly.

---

## Repository layout

```text
Cybersecurity101-Labs/
├── README.md               ← you are here
├── TEMPLATE.md             ← the standard lab-walkthrough template
├── TEMPLATE-card.md        ← the machine-card (lesson) template — method-first A–H
├── Learning Path 1 - Introduction to Cybersecurity/
│   ├── README.md           ← ★ the beginner curriculum — 13 ordered machines
│   ├── 00-Before-You-Start.md … 11-Malware-Analysis-and-YARA.md
│   │                       ← 12 theory + practice modules (00–06 offence, 07–11 systems/defence)
│   └── Machines/           ← one lesson card per machine (A–H structure + hints ladder)
├── Μαθησιακή Διαδρομή 1 - Εισαγωγή στην Κυβερνοασφάλεια/
│   ├── README.md           ← ★ το ίδιο μάθημα, ολοκληρωμένο στα Ελληνικά
│   ├── 00-Πριν-Ξεκινήσεις.md … 11-Ανάλυση-Κακόβουλου-Λογισμικού-και-YARA.md
│   └── Μηχανές/            ← μία κάρτα μαθήματος ανά μηχάνημα (Μέρη Α–Η)
├── docs/
│   ├── CONCEPTS.md         ← ★ the fundamentals primer — read this first
│   ├── CATALOG.md          ← index of ALL 708 VulnHub VMs
│   ├── PROGRESS.md         ← live list of finished walkthroughs
│   ├── LAB-SETUP.md        ← build your own lab (step by step)
│   ├── BEGINNER-PATH.md    ← suggested order for newcomers
│   ├── TOOLS.md            ← the toolkit and what each tool does
│   ├── AUDIT.md            ← repository audit + antivirus fix (English)
│   ├── ΑΝΑΘΕΩΡΗΣΗ.md        ← ο ίδιος απολογισμός στα Ελληνικά
│   ├── INDEX.md            ← ★ the whole repository in reading order (English)
│   └── ΕΥΡΕΤΗΡΙΟ.md         ← ★ όλο το αποθετήριο σε σειρά ανάγνωσης (Ελληνικά)
├── labs/
│   └── <band>-<rank>-<slug>/
│       ├── README.md       ← the walkthrough for that VM
│       └── images/         ← your screenshots for that VM
└── catalog/                ← raw VulnHub data (see catalog/README.md)
    ├── README.md           ← what this folder is, and the encoding caveats
    ├── master-catalog.csv  ← machine-readable catalog
    └── catalog.json        ← slug/URL/metadata map
```

Each VM has its **own folder** named `<band>-<rank>-<slug>`, where *band* is the
difficulty band (1–7 rated, 8 = writeup pending) and *rank* is the machine's position
in one global difficulty ordering (e.g. `labs/3-046-kioptrix-level-1-1/`). Lower rank
= easier. See the [difficulty scale](#difficulty-scale). Inside is a `README.md` (the
walkthrough) and an `images/` folder for your screenshots.

The [`Learning Path 1 - Introduction to Cybersecurity/`](Learning%20Path%201%20-%20Introduction%20to%20Cybersecurity/README.md) folder is a
*curriculum* rather than a set of labs: it orders 13 of the `labs/` folders into a
course and adds the theory around them, so no lab folder is duplicated.

[`Μαθησιακή Διαδρομή 1 - Εισαγωγή στην Κυβερνοασφάλεια/`](%CE%9C%CE%B1%CE%B8%CE%B7%CF%83%CE%B9%CE%B1%CE%BA%CE%AE%20%CE%94%CE%B9%CE%B1%CE%B4%CF%81%CE%BF%CE%BC%CE%AE%201%20-%20%CE%95%CE%B9%CF%83%CE%B1%CE%B3%CF%89%CE%B3%CE%AE%20%CF%83%CF%84%CE%B7%CE%BD%20%CE%9A%CF%85%CE%B2%CE%B5%CF%81%CE%BD%CE%BF%CE%B1%CF%83%CF%86%CE%AC%CE%BB%CE%B5%CE%B9%CE%B1/README.md) is the **complete
Greek edition** of that same curriculum: the same 13 machines, the same twelve theory modules (`00–11`) and
the same thirteen lesson cards, rewritten in Greek. Commands, tool names, flags, file paths and
real terminal output stay in English, because that is how they appear on any real system; every
explanation, concept box, question, hint rung and defensive note is in Greek. The English folder
is the source of truth for wording — the Greek folder is a full mirror, not a summary, and each
card cross-links to its English twin.

---

## Quick start

1. **Build your lab.** Follow [`docs/LAB-SETUP.md`](docs/LAB-SETUP.md)
   (install VirtualBox/VMware, create a host-only network, install Kali).
2. **Learn the fundamentals.** Skim
   [`docs/CONCEPTS.md`](docs/CONCEPTS.md) — at minimum
   [§2 Networking](docs/CONCEPTS.md#2-networking-you-must-know-first),
   [§5 How nmap works](docs/CONCEPTS.md#5-what-is-nmap-and-how-does-it-work), and
   [§15 Linux privilege escalation](docs/CONCEPTS.md#15-linux-privilege-escalation).
   You can also read it lazily: every walkthrough links into it at the point each
   concept first comes up.
3. **Pick a target.** New to this? Start with the
   [beginner path](docs/BEGINNER-PATH.md).
4. **Download the OVA** from the VM's VulnHub page (linked in the catalog and in
   each `labs/<vm>/README.md`).
5. **Import it** into your hypervisor and boot it.
6. **Open the walkthrough** and follow along — the 📖 Concept boxes explain the
   *why* before each command, and `> **How to read it:**` notes explain the output.

---

## The methodology (what every writeup covers)

1. **Reconnaissance** — find the target's IP address and open ports.
2. **Enumeration** — fingerprint services, banners, web apps, SMB shares, users.
3. **Exploitation (foothold)** — turn a finding into the first shell.
4. **Privilege escalation** — go from a normal user to `root`/`Administrator`.
5. **Capture the flags** — read `user.txt` / `root.txt` (or equivalent).
6. **Defensive lessons** — how a defender would have prevented each step.

Each section in a walkup uses four kinds of blocks:

```bash
# The command we run (copy/paste-able)
```

```text
The command's real output (or realistic representative output)
```

> **Why it works / How to read it:** a plain-English explanation of the command
> and its output, aimed at students.

> ### 📖 Concept — what the *idea* is
>
> Appears at the point a technique first comes up, and explains the underlying
> concept rather than the command: what a port scan does at the packet level, why
> a reverse shell beats a bind shell, what makes a wordlist work, how `sudo -l`
> is meant to be read. Each one ends with a **Deep dive** link into
> [`docs/CONCEPTS.md`](docs/CONCEPTS.md), the repository-wide primer, so a single
> walkthrough is self-contained while the fundamentals live in one place instead
> of being restated 98 different ways.

**Screenshots.** The console transcripts above are the primary teaching medium —
they are complete and self-contained, so every walkthrough is fully usable as text.
On top of that, each walkthrough also carries screenshot references using standard
Markdown, plus a **Screenshot checklist** as its final section:

```markdown
![nmap scan showing ports 22 and 80 open](images/01-recon.png)
```

Those `images/NN-*.png` files are **intentionally not committed**. They are
placeholders for *you* to fill in as you work through the machine in your own lab —
capturing your own screenshots is one of the highest-value parts of the exercise,
because it forces you to actually run every command rather than read about it. The
checklist at the end of each walkthrough tells you exactly which shots to take, in
order, and the `alt` text describes what each one should show.

To add them: create `labs/<slug>/images/`, drop in the numbered PNGs, and the
references resolve immediately. Every lab folder already ships an
`images/.gitkeep` so the directory exists.

---

## Difficulty scale

Every lab folder is named **`<band>-<rank>-<slug>`**, so the file tree itself is a
difficulty-ordered course:

```text
labs/2-001-basic-pentesting-1/     ← band 2 (Very Easy), rank 001
labs/4-075-dc-9/                   ← band 4 (Medium),    rank 075
labs/6-098-lord-of-the-root-101/   ← band 6 (Very Difficult), rank 098
labs/8-099-21ltr-scene-1/          ← band 8 (Unrated),   rank 099
```

- **band** is the difficulty, `1`–`7` on the scale below. `8` means **Unrated** —
  the writeup has not been written yet, so there are no commands to judge it from.
  Unrated machines are grouped at the *end* of the numbering.
- **rank** is a single global sequence `001`–`708` in ascending difficulty. It is the
  same number shown in the `#` column of [`docs/CATALOG.md`](docs/CATALOG.md) and
  [`docs/PROGRESS.md`](docs/PROGRESS.md), so any machine can be found by how hard it is.
- **slug** is the original VulnHub identifier, unchanged, so old links and search
  results still make sense.

| Band | Label | Labs | What it means | Examples |
| ---: | --- | ---: | --- | --- |
| **1** | **Ultra Easy** | 0 | A single obvious flaw. One command finds it, one command exploits it. | — |
| **2** | **Very Easy** | 13 | One or two steps, all with published tools and default or trivially guessed credentials. | [`basic-pentesting-1`](labs/2-001-basic-pentesting-1/README.md), [`cybersploit-1`](labs/2-002-cybersploit-1/README.md), [`dc-1`](labs/2-003-dc-1/README.md) … |
| **3** | **Easy** | 56 | A normal recon → enumeration → foothold → privesc chain. Some enumeration effort; no custom code. | [`billu-b0x`](labs/3-014-billu-b0x/README.md), [`bluesky-1`](labs/3-015-bluesky-1/README.md), [`bossplayersctf-1`](labs/3-016-bossplayersctf-1/README.md) … |
| **4** | **Medium** | 23 | Several bugs must be found and **chained**. Longer enumeration, less obvious privesc. | [`basic-pentesting-2`](labs/4-070-basic-pentesting-2/README.md), [`cherry-1`](labs/4-071-cherry-1/README.md), [`chill-hack-1`](labs/4-072-chill-hack-1/README.md) … |
| **5** | **Difficult** | 5 | Multiple rabbit holes, obscure encodings, or a kernel/memory-corruption privesc. You must write a solver script. | [`djinn-1`](labs/5-093-djinn-1/README.md), [`ha-joker`](labs/5-094-ha-joker/README.md), [`ha-rudra`](labs/5-095-ha-rudra/README.md) … |
| **6** | **Very Difficult** | 1 | Requires **writing an exploit yourself** (buffer overflow / shellcode) on top of a multi-stage chain. | [`lord-of-the-root-101`](labs/6-098-lord-of-the-root-101/README.md) |
| **7** | **Ultra Difficult** | 0 | Several of the above at once, on an unfamiliar platform, with little to no guidance. | — |
| **8** | **Unrated** | 610 | No writeup yet, so nothing to judge difficulty from. These are grouped at the end of the numbering and will be rated when written. | the 610 pending stubs, from `8-099-21ltr-scene-1` onward |

### How the ratings were decided

Difficulty is **derived from each writeup**, not guessed, and every rating is
recorded in that lab's metadata table as `**N — Label** (stated: *…*)` so you can see
the evidence:

1. **The stated difficulty** — from the machine's author or its VulnHub page where one
   exists (`Beginner`, `Easy`, `Easy/Intermediate`, `Intermediate`, `Intermediate to
   Hard`, …). This is the strongest signal and sets the base band. Where the author's
   wording is ambiguous, all the levels mentioned are averaged, so
   *Easy / Intermediate* lands between the two rather than at either.
2. **A technique adjustment** (capped at ±0.75 of a band), computed from the commands
   the writeup actually runs — port knocking, steganography, deserialisation, obscure
   encoding chains, kernel exploits, pivoting, container escapes push a machine up;
   default credentials, anonymous FTP/SMB, a published Metasploit or Exploit-DB
   exploit, and a `NOPASSWD` sudo rule push it down.
3. **Two overrides.** Running a *published* kernel or overflow exploit is much easier
   than writing one, so that bonus is cut by roughly two thirds when the writeup shows
   `searchsploit`/`msfconsole`/Exploit-DB doing the work. And any machine that requires
   **hand-written exploit development** is floored at band 5 — or band 6 when it also
   carries seven or more other hard signals — because an understated author rating
   should not hide the hardest work in the collection.

Technique detection runs on each writeup **with all blockquote lines removed**. The
📖 Concept boxes and *How to read it* notes are generic teaching text that mention hard
techniques in every single lab; scoring them rated Kioptrix Level 1, the canonical
beginner box, as "Very Difficult".

> **Bands 1 and 7 are currently empty, and that is the honest result.** The 98
> written walkthroughs were deliberately chosen as beginner-to-intermediate machines,
> so none is a single-step Ultra Easy and only `lord-of-the-root-101` reaches Very Difficult. Both ends
> of the scale will fill in as the 610 unrated machines get written.

---

## Writeup progress

| Batch | Machines | Status |
| --- | --- | --- |
| Master catalog (all VMs indexed) | 708 | ✅ Done |
| Lab setup / tools / beginner path docs | — | ✅ Done |
| **Fundamentals primer** ([`docs/CONCEPTS.md`](docs/CONCEPTS.md)) | 18 sections | ✅ Done |
| Full beginner walkthroughs | **98** written | 🚧 In progress |
| Walkthroughs carrying 📖 Concept boxes | **98** (1,261 boxes) | ✅ Done |
| Remaining machines | 610 | 🚧 Planned (metadata stubs, each linking to the primer) |

See the live list of finished walkthroughs in
[`docs/PROGRESS.md`](docs/PROGRESS.md).

The [catalog](docs/CATALOG.md) is the single source of truth for **every** VM:
name, difficulty (where stated), description, author, release date, the
VulnHub link, and whether a local walkthrough exists yet. Use it to find
machines by name or date.

### Newest walkthroughs

A batch of long-requested VulnHub classics, each with a full beginner-oriented
guide:

| Machine | Headline techniques | Walkthrough |
| --- | --- | --- |
| Kioptrix: 2014 (#5) | FreeBSD, LFI via pChart, User-Agent access-control bypass, PhpTax RCE, SYSRET kernel exploit | [`labs/3-050-kioptrix-2014-5/`](labs/3-050-kioptrix-2014-5/README.md) |
| Basic Pentesting: 1 | ProFTPD 1.3.3c backdoor, WordPress `admin:admin`, writable `/etc/passwd` | [`labs/2-001-basic-pentesting-1/`](labs/2-001-basic-pentesting-1/README.md) |
| Basic Pentesting: 2 | SMB/`enum4linux`, Hydra, SSH-key cracking, Struts2 CVE-2017-9805 | [`labs/4-070-basic-pentesting-2/`](labs/4-070-basic-pentesting-2/README.md) |
| Lord Of The Root: 1.0.1 | Port knocking, nested base64, SQLi, overlayfs, MySQL UDF, **hand-written buffer overflow** | [`labs/6-098-lord-of-the-root-101/`](labs/6-098-lord-of-the-root-101/README.md) |
| FristiLeaks: 1.3 | Base64 image in HTML, file-upload filter bypass, insecure cron, SUID via `sudo -u` | [`labs/3-031-fristileaks-13/`](labs/3-031-fristileaks-13/README.md) |
| HackLAB: Vulnix | `finger`/SMTP enumeration, NFS `root_squash`, UID impersonation, `sudoedit /etc/exports` | [`labs/4-083-hacklab-vulnix/`](labs/4-083-hacklab-vulnix/README.md) |
| VulnOS: 2 | OpenDocMan SQLi (CVE-2014-1945), Drupalgeddon2, overlayfs | [`labs/3-067-vulnos-2/`](labs/3-067-vulnos-2/README.md) |
| SickOs: 1.2 | WebDAV `PUT` upload, HTTP 417 gotcha, egress firewall, chkrootkit CVE-2014-0476 | [`labs/4-086-sickos-12/`](labs/4-086-sickos-12/README.md) |
| Tr0ll: 2 | Image metadata forensics, ZIP cracking, Shellshock over SSH, manual 32-bit buffer overflow | [`labs/5-097-tr0ll-2/`](labs/5-097-tr0ll-2/README.md) |
| zico2: 1 | LFI, phpLiteAdmin CVE-2012-4162, LFI→RCE chaining, Dirty COW | [`labs/4-092-zico2-1/`](labs/4-092-zico2-1/README.md) |
| Bulldog: 1 | SHA-1 hashes in HTML comments, Django admin, web-shell filter bypass, `strings` on an ELF | [`labs/3-017-bulldog-1/`](labs/3-017-bulldog-1/README.md) |
| Chill Hack: 1 | Anonymous FTP, command-injection filter bypass, SSH port forwarding, steganography, Docker→root | [`labs/4-072-chill-hack-1/`](labs/4-072-chill-hack-1/README.md) |

A second batch followed, covering vulnerability classes the first batch did not —
insecure deserialisation, Linux file capabilities, container escapes, mail-server
administration interfaces and restricted shells:

| Machine | Headline techniques | Walkthrough |
| --- | --- | --- |
| **CyberSploit: 1** | Base64 *and* binary decoding, `searchsploit` → Exploit-DB kernel matching | [`labs/2-002-cybersploit-1/`](labs/2-002-cybersploit-1/README.md) |
| **Photographer: 1** | Anonymous SMB, Koken CVE-48706 upload bypass, SUID `php7.2` | [`labs/3-055-photographer-1/`](labs/3-055-photographer-1/README.md) |
| **Empire: Breakout** | Brainfuck-encoded secret, Webmin vs Usermin, **`getcap` / `cap_dac_read_search`** | [`labs/3-028-empire-breakout/`](labs/3-028-empire-breakout/README.md) |
| **W1R3S: 1.0.1** | Cuppa CMS LFI, world-writable `/etc/shadow`, `unshadow` + John | [`labs/3-068-w1r3s-101/`](labs/3-068-w1r3s-101/README.md) |
| **billu: b0x** | Backslash SQLi bypass, `readfile` vs `include`, PHP hidden in a JPEG | [`labs/3-014-billu-b0x/`](labs/3-014-billu-b0x/README.md) |
| **CengBox: 1** | `sqlmap` on a login form, `.ceng` upload filter, **`pspy`** | [`labs/3-018-cengbox-1/`](labs/3-018-cengbox-1/README.md) |
| **Lampião: 1** | `cewl` wordlists, Hydra, Drupalgeddon2, Dirty COW | [`labs/3-051-lampiao-1/`](labs/3-051-lampiao-1/README.md) |
| **HackInOS: 1** | Upload filter reading its own GitHub source, predictable `md5(name.rand(1,100))`, **Docker container escape** | [`labs/3-040-hackinos-1/`](labs/3-040-hackinos-1/README.md) |
| **djinn: 1** | Automating a 1000-question TCP game, port knocking, Flask filter bypass, LXD escape | [`labs/5-093-djinn-1/`](labs/5-093-djinn-1/README.md) |
| **SolidState: 1** | Apache James admin `root:root`, reading users' mail, CVE-2015-7611 | [`labs/4-087-solidstate-1/`](labs/4-087-solidstate-1/README.md) |
| **Seppuku: 1** | Seven ports of rabbit holes, `rbash` escapes, a sudoers rule for a file that does not exist | [`labs/5-096-seppuku-1/`](labs/5-096-seppuku-1/README.md) |
| **Temple of Doom: 1** | **Node.js insecure deserialisation** (CVE-2017-5941), shadowsocks injection, GTFOBins `tcpdump` | [`labs/4-091-temple-of-doom-1/`](labs/4-091-temple-of-doom-1/README.md) |

Work now proceeds **series by series**, so that whole machine families complete
together rather than as scattered one-offs. The **HA series** (17 boot2root VMs by
Hacking Articles) is underway — these four are done:

| Machine | Headline techniques | Walkthrough |
| --- | --- | --- |
| **HA: Wordy** | Five independent routes into one WordPress box: Reflex Gallery upload, Mail Masta **LFI**, WP Support Plus **CSRF auth bypass**, Gwolle **RFI**, WP Symposium **SQLi**, then SUID `cp`/`wget` → `/etc/passwd` overwrite | [`labs/3-039-ha-wordy/`](labs/3-039-ha-wordy/README.md) |
| **HA: Joker** | HTTP Basic Auth brute-forced via a **base64 Burp Intruder payload**, Joomla template editing, and the **`lxd` group → privileged container** escape | [`labs/5-094-ha-joker/`](labs/5-094-ha-joker/README.md) |
| **HA: Rudra** | **NFS `no_root_squash`** export + LFI = RCE, MySQL on loopback with an empty root password, **Cloakify emoji-cipher** decoding, `sudo watch` | [`labs/5-095-ha-rudra/`](labs/5-095-ha-rudra/README.md) |
| **HA: Narak** | Why `nmap` without `-sU` **lies to you**, unauthenticated **TFTP**, `cewl` wordlists, WebDAV `PUT`, **Brainfuck** decoding, and **MOTD injection** (`/etc/update-motd.d/00-header` mode `777` → root) | [`labs/4-082-ha-narak/`](labs/4-082-ha-narak/README.md) |

---

## Contributing a walkthrough

1. Copy [`TEMPLATE.md`](TEMPLATE.md) into `labs/<vm-slug>/README.md`.
2. Fill in every section. Explain the *basics* — assume the reader is new.
3. Put screenshots in `labs/<vm-slug>/images/` and reference them relatively.
4. Link the community writeups you used in the **References** section.
5. Keep commands copy/paste-able and outputs accurate.

**Adding a Learning-Path machine card?** Use [`TEMPLATE-card.md`](TEMPLATE-card.md) — the
method-first A–H structure used by every card in
[Learning Path 1](Learning%20Path%201%20-%20Introduction%20to%20Cybersecurity/README.md) and its
[Greek mirror](%CE%9C%CE%B1%CE%B8%CE%B7%CF%83%CE%B9%CE%B1%CE%BA%CE%AE%20%CE%94%CE%B9%CE%B1%CE%B4%CF%81%CE%BF%CE%BC%CE%AE%201%20-%20%CE%95%CE%B9%CF%83%CE%B1%CE%B3%CF%89%CE%B3%CE%AE%20%CF%83%CF%84%CE%B7%CE%BD%20%CE%9A%CF%85%CE%B2%CE%B5%CF%81%CE%BD%CE%BF%CE%B1%CF%83%CF%86%CE%AC%CE%BB%CE%B5%CE%B9%CE%B1/README.md).
Keep the two language editions structurally identical. Before committing, run
`python3 scripts/validate.py` and `python3 scripts/audit_all.py`.

---

## Credits

- All vulnerable machines are the work of their **authors** and are hosted by
  **[VulnHub](https://vulnhub.com/)**. Full credit and download links are in the
  [catalog](docs/CATALOG.md).
- This repository only provides **educational walkthroughs** that link back to
  the original sources.
