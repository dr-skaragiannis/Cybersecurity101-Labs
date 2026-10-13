# Beginner Path — Suggested Order

New to penetration testing? Don't jump into the hardest boxes. Work down this
list. Each tier builds on the last. Every name links to the VulnHub download in
the [catalog](CATALOG.md); local walkthroughs live under `labs/<slug>/`.

> Tip: always do the [lab setup](LAB-SETUP.md) first, and take a snapshot before
> you attack.

---

## Tier 1 — Your first boots (single obvious flaw)

These are the classic "first VM ever" boxes. You will mostly do recognition +
one exploit.

| # | Machine | VulnHub | Local walkthrough |
| --- | --- | --- | --- |
| 1 | Kioptrix: Level 1 (#1) | [link](https://vulnhub.com/entry/kioptrix-level-1-1,22/) | `labs/kioptrix-level-1-1/` |
| 2 | Kioptrix: Level 1.1 (#2) | [link](https://vulnhub.com/entry/kioptrix-level-11-2,23/) | `labs/kioptrix-level-11-2/` |
| 3 | Kioptrix: Level 1.2 (#3) | [link](https://vulnhub.com/entry/kioptrix-level-12-3,24/) | `labs/kioptrix-level-12-3/` |
| 4 | Kioptrix: Level 1.3 (#4) | [link](https://vulnhub.com/entry/kioptrix-level-13-4,25/) | `labs/kioptrix-level-13-4/` |
| 5 | Fowsniff: 1 | [link](https://vulnhub.com/entry/fowsniff-1,262/) | `labs/fowsniff-1/` |
| 6 | LazySysAdmin: 1 | [link](https://vulnhub.com/entry/lazysysadmin-1,205/) | `labs/lazysysadmin-1/` |
| 7 | bossplayersCTF: 1 | [link](https://vulnhub.com/entry/bossplayersctf-1,375/) | `labs/bossplayersctf-1/` |
| 8 | EVM: 1 | [link](https://vulnhub.com/entry/evm-1,391/) | `labs/evm-1/` |
| 9 | Toppo: 1 | [link](https://vulnhub.com/entry/toppo-1,245/) | `labs/toppo-1/` |
| 10 | Tr0ll: 1 | [link](https://vulnhub.com/entry/tr0ll-1,100/) | `labs/tr0ll-1/` |
| 11 | **Basic Pentesting: 1** | [link](https://vulnhub.com/entry/basic-pentesting-1,216/) | [`labs/basic-pentesting-1/`](../labs/basic-pentesting-1/README.md) |
| 12 | **Bulldog: 1** | [link](https://vulnhub.com/entry/bulldog-1,211/) | [`labs/bulldog-1/`](../labs/bulldog-1/README.md) |

## Tier 2 — Web app flaws & weak credentials

You now meet web enumeration, default logins, and simple file uploads.

| # | Machine | VulnHub | Local walkthrough |
| --- | --- | --- | --- |
| 13 | Mr-Robot: 1 | [link](https://vulnhub.com/entry/mr-robot-1,151/) | `labs/mr-robot-1/` |
| 14 | NullByte: 1 | [link](https://vulnhub.com/entry/nullbyte-1,126/) | `labs/nullbyte-1/` |
| 15 | PwnLab: init | [link](https://vulnhub.com/entry/pwnlab-init,158/) | `labs/pwnlab-init/` |
| 16 | SickOs: 1.1 | [link](https://vulnhub.com/entry/sickos-11,132/) | `labs/sickos-11/` |
| 17 | Tommy Boy: 1 | [link](https://vulnhub.com/entry/tommy-boy-1,157/) | `labs/tommy-boy-1/` |
| 18 | Corrosion: 1 | [link](https://vulnhub.com/entry/corrosion-1,730/) | `labs/corrosion-1/` |
| 19 | DarkHole: 1 | [link](https://vulnhub.com/entry/darkhole-1,724/) | `labs/darkhole-1/` |
| 20 | Jangow: 1.0.1 | [link](https://vulnhub.com/entry/jangow-101,754/) | `labs/jangow-101/` |
| 21 | hackme: 1 | [link](https://vulnhub.com/entry/hackme-1,330/) | `labs/hackme-1/` |
| 22 | hackme: 2 | [link](https://vulnhub.com/entry/hackme-2,618/) | `labs/hackme-2/` |
| 23 | **FristiLeaks: 1.3** | [link](https://vulnhub.com/entry/fristileaks-13,133/) | [`labs/fristileaks-13/`](../labs/fristileaks-13/README.md) |
| 24 | **zico2: 1** | [link](https://vulnhub.com/entry/zico2-1,210/) | [`labs/zico2-1/`](../labs/zico2-1/README.md) |
| 25 | **SickOs: 1.2** | [link](https://vulnhub.com/entry/sickos-12,144/) | [`labs/sickos-12/`](../labs/sickos-12/README.md) |
| 26 | **Chill Hack: 1** | [link](https://vulnhub.com/entry/chill-hack-1,622/) | [`labs/chill-hack-1/`](../labs/chill-hack-1/README.md) |
| 27 | **HA: Wordy** | [link](https://vulnhub.com/entry/ha-wordy,363/) | [`labs/ha-wordy/`](../labs/ha-wordy/README.md) |

## Tier 3 — Chaining and enumeration-heavy boxes

Multiple steps, several services, and the start of real privilege escalation.

| # | Machine | VulnHub | Local walkthrough |
| --- | --- | --- | --- |
| 28 | Stapler: 1 | [link](https://vulnhub.com/entry/stapler-1,150/) | `labs/stapler-1/` |
| 29 | Prime: 1 | [link](https://vulnhub.com/entry/prime-1,358/) | `labs/prime-1/` |
| 30 | symfonos: 1 | [link](https://vulnhub.com/entry/symfonos-1,322/) | `labs/symfonos-1/` |
| 31 | Raven: 1 | [link](https://vulnhub.com/entry/raven-1,256/) | `labs/raven-1/` |
| 32 | GoldenEye: 1 | [link](https://vulnhub.com/entry/goldeneye-1,240/) | `labs/goldeneye-1/` |
| 33 | Matrix: 1 | [link](https://vulnhub.com/entry/matrix-1,259/) | `labs/matrix-1/` |
| 34 | Web Developer: 1 | [link](https://vulnhub.com/entry/web-developer-1,288/) | `labs/web-developer-1/` |
| 35 | pyexp: 1 | [link](https://vulnhub.com/entry/pyexp-1,534/) | `labs/pyexp-1/` |
| 36 | Funbox: 1 | [link](https://vulnhub.com/entry/funbox-1,518/) | `labs/funbox-1/` |
| 37 | Funbox: Scriptkiddie | [link](https://vulnhub.com/entry/funbox-scriptkiddie,725/) | `labs/funbox-scriptkiddie/` |
| 38 | NoobBox: 1 | [link](https://vulnhub.com/entry/noobbox-1,664/) | `labs/noobbox-1/` |
| 39 | BlueSky: 1 | [link](https://vulnhub.com/entry/bluesky-1,623/) | `labs/bluesky-1/` |
| 40 | serial: 1 | [link](https://vulnhub.com/entry/serial-1,349/) | `labs/serial-1/` |
| 41 | digitalworld.local: JOY | [link](https://vulnhub.com/entry/digitalworldlocal-joy,298/) | `labs/digitalworldlocal-joy/` |
| 42 | digitalworld.local: BRAVERY | [link](https://vulnhub.com/entry/digitalworldlocal-bravery,281/) | `labs/digitalworldlocal-bravery/` |
| 43 | hackNos: Os-hackNos | [link](https://vulnhub.com/entry/hacknos-os-hacknos,401/) | `labs/hacknos-os-hacknos/` |
| 44 | **Basic Pentesting: 2** | [link](https://vulnhub.com/entry/basic-pentesting-2,241/) | [`labs/basic-pentesting-2/`](../labs/basic-pentesting-2/README.md) |
| 45 | **VulnOS: 2** | [link](https://vulnhub.com/entry/vulnos-2,147/) | [`labs/vulnos-2/`](../labs/vulnos-2/README.md) |
| 46 | **Lord Of The Root: 1.0.1** | [link](https://vulnhub.com/entry/lord-of-the-root-101,129/) | [`labs/lord-of-the-root-101/`](../labs/lord-of-the-root-101/README.md) |
| 47 | **HackLAB: Vulnix** | [link](https://vulnhub.com/entry/hacklab-vulnix,48/) | [`labs/hacklab-vulnix/`](../labs/hacklab-vulnix/README.md) |

| 48 | **HA: Joker** | [link](https://vulnhub.com/entry/ha-joker,379/) | [`labs/ha-joker/`](../labs/ha-joker/README.md) |
| 49 | **HA: Rudra** | [link](https://vulnhub.com/entry/ha-rudra,386/) | [`labs/ha-rudra/`](../labs/ha-rudra/README.md) |
| 50 | **HA: Narak** | [link](https://vulnhub.com/entry/ha-narak,569/) | [`labs/ha-narak/`](../labs/ha-narak/README.md) |
## Tier 4 — Ready for OSCP-style practice

When Tier 3 feels routine, these mirror the enumeration-and-chaining style of
certification exams (OSCP-like). Several also introduce binary exploitation,
protocol-level abuse, or an OS that is not Linux.

| # | Machine | Why it earns its place | Walkthrough |
| --- | --- | --- | --- |
| 51 | **Kioptrix: 2014 (#5)** | **FreeBSD**, not Linux — every path assumption breaks; User-Agent access-control bypass; SYSRET kernel exploit | [read](../labs/kioptrix-2014-5/README.md) |
| 52 | **Tr0ll: 2** | Steganographic hints, Shellshock over an SSH forced command, and a **hand-written 32-bit buffer overflow** | [read](../labs/tr0ll-2/README.md) |
| 53 | symfonos: 2 | SMB + WordPress chaining | [stub](../labs/symfonos-2/README.md) |
| 54 | symfonos: 3.1 | Multi-service enumeration | [stub](../labs/symfonos-31/README.md) |
| 55 | DriftingBlues: 1 | Modern web + kernel privesc | [read](../labs/driftingblues-1/README.md) |
| 56 | hackNos: Os-hackNos-2.1 | Enumeration-heavy chain | [stub](../labs/hacknos-os-hacknos-21/README.md) |
| 57 | serial: 2 | Serialisation and chaining | [stub](../labs/serial-2/README.md) |
| 58 | dpwwn: 1 | WordPress + local privesc | [stub](../labs/dpwwn-1/README.md) |
| 59 | Stapler: 1 | Twenty-plus services, wide enumeration | [read](../labs/stapler-1/README.md) |
| 60 | **CyberSploit: 1** | *Complete-beginner* box: base64 + binary decoding, then Exploit-DB kernel matching | [read](../labs/cybersploit-1/README.md) |
| 61 | **Photographer: 1** | Anonymous SMB, Koken file-upload bypass, SUID PHP | [read](../labs/photographer-1/README.md) |
| 62 | **Empire: Breakout** | Brainfuck-encoded secret, Webmin/Usermin, Linux **file capabilities** (`getcap`) | [read](../labs/empire-breakout/README.md) |
| 63 | **W1R3S: 1.0.1** | Cuppa CMS LFI reading a world-writable `/etc/shadow`, `unshadow` + John | [read](../labs/w1r3s-101/README.md) |
| 64 | **billu: b0x** | Backslash SQLi bypass, `readfile` vs `include`, PHP hidden in a JPEG | [read](../labs/billu-b0x/README.md) |
| 65 | **CengBox: 1** | `sqlmap` on a login form, `.ceng` upload filter, **`pspy`** to find a root-run script | [read](../labs/cengbox-1/README.md) |
| 66 | **Lampião: 1** | `cewl` wordlists, Hydra, Drupalgeddon2, Dirty COW | [read](../labs/lampiao-1/README.md) |
| 67 | **HackInOS: 1** | Upload filter reading its own GitHub source, predictable `md5(name.rand(1,100))`, **container escape** | [read](../labs/hackinos-1/README.md) |
| 68 | **djinn: 1** | Automating a 1000-question TCP game, port knocking, Flask filter bypass, LXD escape | [read](../labs/djinn-1/README.md) |
| 69 | **SolidState: 1** | Apache James admin `root:root`, reading other users' mail, CVE-2015-7611 | [read](../labs/solidstate-1/README.md) |
| 70 | **Seppuku: 1** | Seven ports of rabbit holes, `rbash` escapes, a sudoers rule pointing at a file that does not exist | [read](../labs/seppuku-1/README.md) |
| 71 | **Temple of Doom: 1** | **Node.js insecure deserialisation** (CVE-2017-5941), shadowsocks injection, GTFOBins `tcpdump` | [read](../labs/temple-of-doom-1/README.md) |

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
