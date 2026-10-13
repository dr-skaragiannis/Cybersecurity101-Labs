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

## Tier 2 — Web app flaws & weak credentials

You now meet web enumeration, default logins, and simple file uploads.

| # | Machine | VulnHub | Local walkthrough |
| --- | --- | --- | --- |
| 11 | Mr-Robot: 1 | [link](https://vulnhub.com/entry/mr-robot-1,151/) | `labs/mr-robot-1/` |
| 12 | NullByte: 1 | [link](https://vulnhub.com/entry/nullbyte-1,126/) | `labs/nullbyte-1/` |
| 13 | PwnLab: init | [link](https://vulnhub.com/entry/pwnlab-init,158/) | `labs/pwnlab-init/` |
| 14 | SickOs: 1.1 | [link](https://vulnhub.com/entry/sickos-11,132/) | `labs/sickos-11/` |
| 15 | Tommy Boy: 1 | [link](https://vulnhub.com/entry/tommy-boy-1,157/) | `labs/tommy-boy-1/` |
| 16 | Corrosion: 1 | [link](https://vulnhub.com/entry/corrosion-1,730/) | `labs/corrosion-1/` |
| 17 | DarkHole: 1 | [link](https://vulnhub.com/entry/darkhole-1,724/) | `labs/darkhole-1/` |
| 18 | Jangow: 1.0.1 | [link](https://vulnhub.com/entry/jangow-101,754/) | `labs/jangow-101/` |
| 19 | hackme: 1 | [link](https://vulnhub.com/entry/hackme-1,330/) | `labs/hackme-1/` |
| 20 | hackme: 2 | [link](https://vulnhub.com/entry/hackme-2,618/) | `labs/hackme-2/` |

## Tier 3 — Chaining and enumeration-heavy boxes

Multiple steps, several services, and the start of real privilege escalation.

| # | Machine | VulnHub | Local walkthrough |
| --- | --- | --- | --- |
| 21 | Stapler: 1 | [link](https://vulnhub.com/entry/stapler-1,150/) | `labs/stapler-1/` |
| 22 | Prime: 1 | [link](https://vulnhub.com/entry/prime-1,358/) | `labs/prime-1/` |
| 23 | symfonos: 1 | [link](https://vulnhub.com/entry/symfonos-1,322/) | `labs/symfonos-1/` |
| 24 | Raven: 1 | [link](https://vulnhub.com/entry/raven-1,256/) | `labs/raven-1/` |
| 25 | GoldenEye: 1 | [link](https://vulnhub.com/entry/goldeneye-1,240/) | `labs/goldeneye-1/` |
| 26 | Matrix: 1 | [link](https://vulnhub.com/entry/matrix-1,259/) | `labs/matrix-1/` |
| 27 | Web Developer: 1 | [link](https://vulnhub.com/entry/web-developer-1,288/) | `labs/web-developer-1/` |
| 28 | pyexp: 1 | [link](https://vulnhub.com/entry/pyexp-1,534/) | `labs/pyexp-1/` |
| 29 | Funbox: 1 | [link](https://vulnhub.com/entry/funbox-1,518/) | `labs/funbox-1/` |
| 30 | Funbox: Scriptkiddie | [link](https://vulnhub.com/entry/funbox-scriptkiddie,725/) | `labs/funbox-scriptkiddie/` |
| 31 | NoobBox: 1 | [link](https://vulnhub.com/entry/noobbox-1,664/) | `labs/noobbox-1/` |
| 32 | BlueSky: 1 | [link](https://vulnhub.com/entry/bluesky-1,623/) | `labs/bluesky-1/` |
| 33 | serial: 1 | [link](https://vulnhub.com/entry/serial-1,349/) | `labs/serial-1/` |
| 34 | digitalworld.local: JOY | [link](https://vulnhub.com/entry/digitalworldlocal-joy,298/) | `labs/digitalworldlocal-joy/` |
| 35 | digitalworld.local: BRAVERY | [link](https://vulnhub.com/entry/digitalworldlocal-bravery,281/) | `labs/digitalworldlocal-bravery/` |
| 36 | hackNos: Os-hackNos | [link](https://vulnhub.com/entry/hacknos-os-hacknos,401/) | `labs/hacknos-os-hacknos/` |

## Tier 4 — Ready for OSCP-style practice

When Tier 3 feels routine, these mirror the enumeration-and-chaining style of
certification exams (OSCP-like).

- `labs/symfonos-2/`, `labs/symfonos-3-1/`, `labs/driftingblues-1/` …
- `labs/hacknos-os-hacknos-21/`, `labs/serial-2/`, `labs/dpwwn-1/`
- `labs/tr0ll-2/`, `labs/sickos-12/`, `labs/stapler-1/`

See the full [catalog](CATALOG.md) to pick more.

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
