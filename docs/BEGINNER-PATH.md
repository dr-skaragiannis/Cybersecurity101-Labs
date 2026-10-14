# Beginner Path — Suggested Order

New to penetration testing? Don't jump into the hardest boxes. Work down this
list. Each tier builds on the last. Every name links to the VulnHub download in
the [catalog](CATALOG.md); local walkthroughs live under `labs/<band>-<rank>-<slug>/`.

The **Rank** column is the global difficulty rank shared with the folder names and
the [catalog](CATALOG.md) — lower is easier. Tiers below are still curated by
*teaching order* rather than raw difficulty, so ranks inside a tier need not be
contiguous. See the [difficulty scale](../README.md#difficulty-scale).

> ### ★ Prefer a full course over a list?
>
> **[Learning Path 1 — Introduction to Cybersecurity](../Learning%20Path%201%20-%20Introduction%20to%20Cybersecurity/README.md)** turns the
> beginner end of this page into a taught curriculum: **13 machines** in a fixed
> order, **6 theory-and-practice modules** (networking and recon, web attacks, service
> and network attacks, credentials and cracking, Linux privilege escalation, shells
> and escapes), and a **lesson card per machine** with objectives, pre-lab questions,
> a five-rung hints ladder, review questions and a defensive fix table. The four tiers
> below remain useful as a wider menu once you have finished it.
>
> **Μιλάς Ελληνικά;** Ολόκληρη η διαδρομή υπάρχει και στα Ελληνικά:
> **[Μαθησιακή Διαδρομή 1 — Εισαγωγή στην Κυβερνοασφάλεια](../%CE%9C%CE%B1%CE%B8%CE%B7%CF%83%CE%B9%CE%B1%CE%BA%CE%AE%20%CE%94%CE%B9%CE%B1%CE%B4%CF%81%CE%BF%CE%BC%CE%AE%201%20-%20%CE%95%CE%B9%CF%83%CE%B1%CE%B3%CF%89%CE%B3%CE%AE%20%CF%83%CF%84%CE%B7%CE%BD%20%CE%9A%CF%85%CE%B2%CE%B5%CF%81%CE%BD%CE%BF%CE%B1%CF%83%CF%86%CE%AC%CE%BB%CE%B5%CE%B9%CE%B1/README.md)**.
> Οι εντολές, τα εργαλεία και τα αποτελέσματα τερματικού παραμένουν στα Αγγλικά·
> όλη η επεξήγηση είναι στα Ελληνικά.

> Tip: always do the [lab setup](LAB-SETUP.md) first, and take a snapshot before
> you attack.

---

## Tier 1 — Your first boots (single obvious flaw)

These are the classic "first VM ever" boxes. You will mostly do recognition +
one exploit.

| Rank | Machine | Difficulty | VulnHub | Local walkthrough |
|---:|---------|-----------|---------|-------------------|
| **046** | Kioptrix: Level 1 (#1) | **3 — Easy** (stated: *Easy*) | [link](https://vulnhub.com/entry/kioptrix-level-1-1,22/) | `labs/3-046-kioptrix-level-1-1/` |
| **047** | Kioptrix: Level 1.1 (#2) | **3 — Easy** (stated: *Easy*) | [link](https://vulnhub.com/entry/kioptrix-level-11-2,23/) | `labs/3-047-kioptrix-level-11-2/` |
| **048** | Kioptrix: Level 1.2 (#3) | **3 — Easy** (stated: *Easy*) | [link](https://vulnhub.com/entry/kioptrix-level-12-3,24/) | `labs/3-048-kioptrix-level-12-3/` |
| **049** | Kioptrix: Level 1.3 (#4) | **3 — Easy** (stated: *Easy / Intermediate*) | [link](https://vulnhub.com/entry/kioptrix-level-13-4,25/) | `labs/3-049-kioptrix-level-13-4/` |
| **030** | Fowsniff: 1 | **3 — Easy** (stated: *Easy*) | [link](https://vulnhub.com/entry/fowsniff-1,262/) | `labs/3-030-fowsniff-1/` |
| **052** | LazySysAdmin: 1 | **3 — Easy** (stated: *Easy*) | [link](https://vulnhub.com/entry/lazysysadmin-1,205/) | `labs/3-052-lazysysadmin-1/` |
| **016** | bossplayersCTF: 1 | **3 — Easy** (stated: *Easy / Beginner*) | [link](https://vulnhub.com/entry/bossplayersctf-1,375/) | `labs/3-016-bossplayersctf-1/` |
| **029** | EVM: 1 | **3 — Easy** (stated: *Easy*) | [link](https://vulnhub.com/entry/evm-1,391/) | `labs/3-029-evm-1/` |
| **066** | Toppo: 1 | **3 — Easy** (stated: *Easy*) | [link](https://vulnhub.com/entry/toppo-1,245/) | `labs/3-066-toppo-1/` |
| **013** | Tr0ll: 1 | **2 — Very Easy** (stated: *Easy / Beginner*) | [link](https://vulnhub.com/entry/tr0ll-1,100/) | `labs/2-013-tr0ll-1/` |
| **001** | **Basic Pentesting: 1** | **2 — Very Easy** (stated: *Easy / Beginner*) | [link](https://vulnhub.com/entry/basic-pentesting-1,216/) | [`labs/2-001-basic-pentesting-1/`](../labs/2-001-basic-pentesting-1/README.md) |
| **017** | **Bulldog: 1** | **3 — Easy** (stated: *Beginner / Intermediate*) | [link](https://vulnhub.com/entry/bulldog-1,211/) | [`labs/3-017-bulldog-1/`](../labs/3-017-bulldog-1/README.md) |

## Tier 2 — Web app flaws & weak credentials

You now meet web enumeration, default logins, and simple file uploads.

| Rank | Machine | Difficulty | VulnHub | Local walkthrough |
|---:|---------|-----------|---------|-------------------|
| **053** | Mr-Robot: 1 | **3 — Easy** (stated: *Easy*) | [link](https://vulnhub.com/entry/mr-robot-1,151/) | `labs/3-053-mr-robot-1/` |
| **054** | NullByte: 1 | **3 — Easy** (stated: *Easy*) | [link](https://vulnhub.com/entry/nullbyte-1,126/) | `labs/3-054-nullbyte-1/` |
| **057** | PwnLab: init | **3 — Easy** (stated: *Easy*) | [link](https://vulnhub.com/entry/pwnlab-init,158/) | `labs/3-057-pwnlab-init/` |
| **085** | SickOs: 1.1 | **4 — Medium** (stated: *Easy / Intermediate*) | [link](https://vulnhub.com/entry/sickos-11,132/) | `labs/4-085-sickos-11/` |
| **065** | Tommy Boy: 1 | **3 — Easy** (stated: *Easy / Intermediate*) | [link](https://vulnhub.com/entry/tommy-boy-1,157/) | `labs/3-065-tommy-boy-1/` |
| **019** | Corrosion: 1 | **3 — Easy** (stated: *Easy*) | [link](https://vulnhub.com/entry/corrosion-1,730/) | `labs/3-019-corrosion-1/` |
| **020** | DarkHole: 1 | **3 — Easy** (stated: *Easy*) | [link](https://vulnhub.com/entry/darkhole-1,724/) | `labs/3-020-darkhole-1/` |
| **045** | Jangow: 1.0.1 | **3 — Easy** (stated: *Easy*) | [link](https://vulnhub.com/entry/jangow-101,754/) | `labs/3-045-jangow-101/` |
| **041** | hackme: 1 | **3 — Easy** (stated: *Easy*) | [link](https://vulnhub.com/entry/hackme-1,330/) | `labs/3-041-hackme-1/` |
| **042** | hackme: 2 | **3 — Easy** (stated: *Easy / Medium*) | [link](https://vulnhub.com/entry/hackme-2,618/) | `labs/3-042-hackme-2/` |
| **031** | **FristiLeaks: 1.3** | **3 — Easy** (stated: *Easy–Intermediate*) | [link](https://vulnhub.com/entry/fristileaks-13,133/) | [`labs/3-031-fristileaks-13/`](../labs/3-031-fristileaks-13/README.md) |
| **092** | **zico2: 1** | **4 — Medium** (stated: *Intermediate*) | [link](https://vulnhub.com/entry/zico2-1,210/) | [`labs/4-092-zico2-1/`](../labs/4-092-zico2-1/README.md) |
| **086** | **SickOs: 1.2** | **4 — Medium** (stated: *Intermediate*) | [link](https://vulnhub.com/entry/sickos-12,144/) | [`labs/4-086-sickos-12/`](../labs/4-086-sickos-12/README.md) |
| **072** | **Chill Hack: 1** | **4 — Medium** (stated: *Easy / Intermediate*) | [link](https://vulnhub.com/entry/chill-hack-1,622/) | [`labs/4-072-chill-hack-1/`](../labs/4-072-chill-hack-1/README.md) |
| **039** | **HA: Wordy** | **3 — Easy** (stated: *Easy*) | [link](https://vulnhub.com/entry/ha-wordy,363/) | [`labs/3-039-ha-wordy/`](../labs/3-039-ha-wordy/README.md) |

## Tier 3 — Chaining and enumeration-heavy boxes

Multiple steps, several services, and the start of real privilege escalation.

| Rank | Machine | Difficulty | VulnHub | Local walkthrough |
|---:|---------|-----------|---------|-------------------|
| **061** | Stapler: 1 | **3 — Easy** (stated: *Easy / Intermediate*) | [link](https://vulnhub.com/entry/stapler-1,150/) | `labs/3-061-stapler-1/` |
| **056** | Prime: 1 | **3 — Easy** (stated: *Easy / Intermediate*) | [link](https://vulnhub.com/entry/prime-1,358/) | `labs/3-056-prime-1/` |
| **062** | symfonos: 1 | **3 — Easy** (stated: *Easy / Medium*) | [link](https://vulnhub.com/entry/symfonos-1,322/) | `labs/3-062-symfonos-1/` |
| **059** | Raven: 1 | **3 — Easy** (stated: *Beginner / Intermediate*) | [link](https://vulnhub.com/entry/raven-1,256/) | `labs/3-059-raven-1/` |
| **081** | GoldenEye: 1 | **4 — Medium** (stated: *Intermediate*) | [link](https://vulnhub.com/entry/goldeneye-1,240/) | `labs/4-081-goldeneye-1/` |
| **084** | Matrix: 1 | **4 — Medium** (stated: *Intermediate*) | [link](https://vulnhub.com/entry/matrix-1,259/) | `labs/4-084-matrix-1/` |
| **069** | Web Developer: 1 | **3 — Easy** (stated: *Easy / Medium*) | [link](https://vulnhub.com/entry/web-developer-1,288/) | `labs/3-069-web-developer-1/` |
| **058** | pyexp: 1 | **3 — Easy** (stated: *Easy*) | [link](https://vulnhub.com/entry/pyexp-1,534/) | `labs/3-058-pyexp-1/` |
| **038** | Funbox: 1 | **3 — Easy** (stated: *Easy*) | [link](https://vulnhub.com/entry/funbox-1,518/) | `labs/3-038-funbox-1/` |
| **008** | Funbox: Scriptkiddie | **2 — Very Easy** (stated: *Easy*) | [link](https://vulnhub.com/entry/funbox-scriptkiddie,725/) | `labs/2-008-funbox-scriptkiddie/` |
| **010** | NoobBox: 1 | **2 — Very Easy** (stated: *Beginner*) | [link](https://vulnhub.com/entry/noobbox-1,664/) | `labs/2-010-noobbox-1/` |
| **015** | BlueSky: 1 | **3 — Easy** (stated: *Beginner / Easy*) | [link](https://vulnhub.com/entry/bluesky-1,623/) | `labs/3-015-bluesky-1/` |
| **060** | serial: 1 | **3 — Easy** (stated: *Easy / Medium*) | [link](https://vulnhub.com/entry/serial-1,349/) | `labs/3-060-serial-1/` |
| **078** | digitalworld.local: JOY | **4 — Medium** (stated: *Medium*) | [link](https://vulnhub.com/entry/digitalworldlocal-joy,298/) | `labs/4-078-digitalworldlocal-joy/` |
| **024** | digitalworld.local: BRAVERY | **3 — Easy** (stated: *Easy / Medium*) | [link](https://vulnhub.com/entry/digitalworldlocal-bravery,281/) | `labs/3-024-digitalworldlocal-bravery/` |
| **043** | hackNos: Os-hackNos | **3 — Easy** (stated: *Easy*) | [link](https://vulnhub.com/entry/hacknos-os-hacknos,401/) | `labs/3-043-hacknos-os-hacknos/` |
| **070** | **Basic Pentesting: 2** | **4 — Medium** (stated: *Easy–Intermediate*) | [link](https://vulnhub.com/entry/basic-pentesting-2,241/) | [`labs/4-070-basic-pentesting-2/`](../labs/4-070-basic-pentesting-2/README.md) |
| **067** | **VulnOS: 2** | **3 — Easy** (stated: *Easy–Intermediate*) | [link](https://vulnhub.com/entry/vulnos-2,147/) | [`labs/3-067-vulnos-2/`](../labs/3-067-vulnos-2/README.md) |
| **098** | **Lord Of The Root: 1.0.1** | **6 — Very Difficult** (stated: *Easy–Intermediate*) | [link](https://vulnhub.com/entry/lord-of-the-root-101,129/) | [`labs/6-098-lord-of-the-root-101/`](../labs/6-098-lord-of-the-root-101/README.md) |
| **083** | **HackLAB: Vulnix** | **4 — Medium** (stated: *Intermediate*) | [link](https://vulnhub.com/entry/hacklab-vulnix,48/) | [`labs/4-083-hacklab-vulnix/`](../labs/4-083-hacklab-vulnix/README.md) |

| **094** | **HA: Joker** | **5 — Difficult** (stated: *Intermediate*) | [link](https://vulnhub.com/entry/ha-joker,379/) | [`labs/5-094-ha-joker/`](../labs/5-094-ha-joker/README.md) |
| **095** | **HA: Rudra** | **5 — Difficult** (stated: *Intermediate*) | [link](https://vulnhub.com/entry/ha-rudra,386/) | [`labs/5-095-ha-rudra/`](../labs/5-095-ha-rudra/README.md) |
| **082** | **HA: Narak** | **4 — Medium** (stated: *Intermediate*) | [link](https://vulnhub.com/entry/ha-narak,569/) | [`labs/4-082-ha-narak/`](../labs/4-082-ha-narak/README.md) |
## Tier 4 — Ready for OSCP-style practice

When Tier 3 feels routine, these mirror the enumeration-and-chaining style of
certification exams (OSCP-like). Several also introduce binary exploitation,
protocol-level abuse, or an OS that is not Linux.

| # | Machine | Why it earns its place | Walkthrough |
|---:|---------|-----------|---------|-------------------|
| **050** | **Kioptrix: 2014 (#5)** | **3 — Easy** (stated: *Beginner*) | **FreeBSD**, not Linux — every path assumption breaks; User-Agent access-control bypass; SYSRET kernel exploit | [read](../labs/3-050-kioptrix-2014-5/README.md) |
| **097** | **Tr0ll: 2** | **5 — Difficult** (stated: *Beginner++ / Intermediate*) | Steganographic hints, Shellshock over an SSH forced command, and a **hand-written 32-bit buffer overflow** | [read](../labs/5-097-tr0ll-2/README.md) |
| **063** | symfonos: 2 | **3 — Easy** (stated: *Easy / Medium*) | SMB + WordPress chaining | [stub](../labs/3-063-symfonos-2/README.md) |
| **089** | symfonos: 3.1 | **4 — Medium** (stated: *Intermediate*) | Multi-service enumeration | [stub](../labs/4-089-symfonos-31/README.md) |
| **026** | DriftingBlues: 1 | **3 — Easy** (stated: *Easy*) | Modern web + kernel privesc | [read](../labs/3-026-driftingblues-1/README.md) |
| **044** | hackNos: Os-hackNos-2.1 | **3 — Easy** (stated: *Easy / Intermediate*) | Enumeration-heavy chain | [stub](../labs/3-044-hacknos-os-hacknos-21/README.md) |
| **568** | serial: 2 | **8 — Unrated** (writeup pending) | Serialisation and chaining | [stub](../labs/8-568-serial-2/README.md) |
| **257** | dpwwn: 1 | **8 — Unrated** (writeup pending) | WordPress + local privesc | [stub](../labs/8-257-dpwwn-1/README.md) |
| **061** | Stapler: 1 | **3 — Easy** (stated: *Easy / Intermediate*) | Twenty-plus services, wide enumeration | [read](../labs/3-061-stapler-1/README.md) |
| **002** | **CyberSploit: 1** | **2 — Very Easy** (stated: *Complete beginner*) | *Complete-beginner* box: base64 + binary decoding, then Exploit-DB kernel matching | [read](../labs/2-002-cybersploit-1/README.md) |
| **055** | **Photographer: 1** | **3 — Easy** (stated: *Easy*) | Anonymous SMB, Koken file-upload bypass, SUID PHP | [read](../labs/3-055-photographer-1/README.md) |
| **028** | **Empire: Breakout** | **3 — Easy** (stated: *Easy*) | Brainfuck-encoded secret, Webmin/Usermin, Linux **file capabilities** (`getcap`) | [read](../labs/3-028-empire-breakout/README.md) |
| **068** | **W1R3S: 1.0.1** | **3 — Easy** (stated: *Beginner / Intermediate*) | Cuppa CMS LFI reading a world-writable `/etc/shadow`, `unshadow` + John | [read](../labs/3-068-w1r3s-101/README.md) |
| **014** | **billu: b0x** | **3 — Easy** (stated: *Easy / Intermediate*) | Backslash SQLi bypass, `readfile` vs `include`, PHP hidden in a JPEG | [read](../labs/3-014-billu-b0x/README.md) |
| **018** | **CengBox: 1** | **3 — Easy** (stated: *Beginner / Intermediate*) | `sqlmap` on a login form, `.ceng` upload filter, **`pspy`** to find a root-run script | [read](../labs/3-018-cengbox-1/README.md) |
| **051** | **Lampião: 1** | **3 — Easy** (stated: *Easy*) | `cewl` wordlists, Hydra, Drupalgeddon2, Dirty COW | [read](../labs/3-051-lampiao-1/README.md) |
| **040** | **HackInOS: 1** | **3 — Easy** (stated: *Beginner / Intermediate*) | Upload filter reading its own GitHub source, predictable `md5(name.rand(1,100))`, **container escape** | [read](../labs/3-040-hackinos-1/README.md) |
| **093** | **djinn: 1** | **5 — Difficult** (stated: *Beginner–Intermediate*) | Automating a 1000-question TCP game, port knocking, Flask filter bypass, LXD escape | [read](../labs/5-093-djinn-1/README.md) |
| **087** | **SolidState: 1** | **4 — Medium** (stated: *Intermediate*) | Apache James admin `root:root`, reading other users' mail, CVE-2015-7611 | [read](../labs/4-087-solidstate-1/README.md) |
| **096** | **Seppuku: 1** | **5 — Difficult** (stated: *Intermediate to Hard*) | Seven ports of rabbit holes, `rbash` escapes, a sudoers rule pointing at a file that does not exist | [read](../labs/5-096-seppuku-1/README.md) |
| **091** | **Temple of Doom: 1** | **4 — Medium** (stated: *Easy / Intermediate*) | **Node.js insecure deserialisation** (CVE-2017-5941), shadowsocks injection, GTFOBins `tcpdump` | [read](../labs/4-091-temple-of-doom-1/README.md) |

See the full [catalog](CATALOG.md) to pick more — the *Writeup* column shows which
machines already have a complete local guide.

> **Where to start if you are brand new:** Tier 1 #11 **Basic Pentesting: 1**, then
> Tier 4 #56 **CyberSploit: 1** — despite the tier number, CyberSploit is the gentlest
> box in this repository and the author designed it for a first-time learner. The tiers
> describe *skill breadth*, not strictly difficulty.

---

## How to practise well

1. **Stuck for 30+ minutes?** Re-read your enumeration output — you usually
   missed a service, a directory, or a version.
2. **Never skip recon.** Most beginner boxes fall to good enumeration alone.
3. **Take notes.** Keep the IP, open ports, credentials, and every finding.
4. **Don't memorise answers.** Understand *why* each step works.
5. After each box, write your own one-paragraph "defensive lesson".

---

_Back to the [README](../README.md) · [Lab setup](LAB-SETUP.md) · [Tools](TOOLS.md) · [Catalog](CATALOG.md)._
