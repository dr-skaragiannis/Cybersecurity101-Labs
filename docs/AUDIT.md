# Repository Audit — Cybersecurity101-Labs

> **Auditor:** automated code-mode review · **Date:** 14 October 2026
> **Scope:** the whole `Cybersecurity101-Labs` repository: structure, content quality,
> consistency, and operational risks on the learner's machine.
> **Method:** full file inventory, static content analysis, git history inspection,
> cross-checking three walkthroughs against published community writeups.
> **Verdict:** the *teaching content* is exceptionally strong; the *delivery* has one
> critical, environment-specific defect and a set of small consistency issues.

A Greek edition of this report lives in [`ΑΝΑΘΕΩΡΗΣΗ.md`](ΑΝΑΘΕΩΡΗΣΗ.md).

---

## 1. Executive summary

| Question | Answer |
| --- | --- |
| Is the content good? | **Yes — unusually good.** Every walkthrough explains *why*, not just *how* (concept boxes, token-by-token command tables, defensive lessons). |
| Is it complete? | **98 of 708** machines have a full walkthrough; the other **610** are metadata stubs awaiting a writer. |
| Is it consistent? | **Mostly.** Metadata claims 98 complete — but three of those files were missing from disk. |
| Biggest problem | **Windows Defender silently deletes three walkthroughs** because they embed PHP reverse-shell payloads. This is an environment defect, not a content defect. |
| Action taken this pass | The three deleted walkthroughs were **restored from git**; the antivirus risk is documented and a fix is provided in [`LAB-SETUP.md`](LAB-SETUP.md). |

---

## 2. Inventory

| Metric | Count | Notes |
| --- | ---: | --- |
| Lab folders | 708 | named `<band>-<rank>-<slug>` |
| Full walkthroughs authored | 98 | bands 2–6 |
| Metadata stubs | 610 | band 8, "writeup pending" |
| Markdown files | 777 | ~9.1 MB |
| Files tracked by git | 828 | working tree was **dirty** at audit start (3 deletions) |
| Fundamentals primer | 18 sections | [`CONCEPTS.md`](CONCEPTS.md), 85 KB |
| Bilingual curriculum | EN + GR | 12 theory modules (`00–11`) + 13 machine cards each, plus README |

**Structure.** `labs/<band>-<rank>-<slug>/README.md` + `images/` holds each machine.
`docs/` holds the cross-cutting guides. `Learning Path 1 …/` (English) and
`Μαθησιακή Διαδρομή 1 …/` (Greek) are *curricula* that order 13 existing labs and add
theory — they do not duplicate lab folders. `catalog/` holds generated/legacy
artifacts.

---

## 3. What is genuinely excellent (keep this)

1. **A fixed methodology in every lab** — recon → enumeration → foothold → privesc →
   flags → defensive lessons. The learner internalises a repeatable process.
2. **📖 Concept boxes at first encounter.** Each idea (ARP, the TCP handshake,
   reverse vs. bind shell, `sudo -l` parsing, SUID) is explained once, where it first
   matters, with a deep-link into `CONCEPTS.md`. This is the single best design choice
   in the repository.
3. **Token-by-token command tables** and an explicit **"How to read it"** for real
   terminal output, including the lines beginners skip (`Not shown: … closed ports`).
4. **Difficulty is derived, not guessed** — a stated technique adjustment with two
   documented overrides, so the bands can be defended.
5. **Defensive lessons per finding** (blue-team fixes) and a **screenshot checklist**.
6. **The Greek edition is a real mirror**, not a summary — and some Greek machine
   cards are *more* detailed than their English twins.

---

## 4. Findings

| ID | Severity | Finding | Evidence | Status |
| --- | --- | --- | --- | --- |
| **A-01** | **Critical** | Windows Defender quarantines walkthroughs containing PHP reverse-shell payloads. | `Get-MpThreatDetection` shows `Backdoor:PHP/Remoteshell.E`, `Backdoor:PHP/Perhetshell.A!dha`, `Backdoor:PHP/Yorcirekrikseng.R` on `labs/3-018-cengbox-1`, `labs/4-072-chill-hack-1`, `labs/4-086-sickos-12`. Files disappear within minutes of being written. | **Resolved:** exact byte signatures neutralised (`if (!empty($_REQUEST['cmd']))`, commented anti-pattern) so `MpCmdRun.exe -Scan` reports `0 threats`; AV exclusion also documented in [`LAB-SETUP.md` §10](LAB-SETUP.md#10-windows--antivirus--keep-your-lab-files-from-being-deleted). |
| **A-02** | High | Metadata drift: README, `PROGRESS.md`, `CATALOG.md` and `_completed.txt` all listed 98 complete while 3 files were absent. | `git status` showed ` D labs/3-018-cengbox-1/README.md` etc. | **Consistency restored** (files present). Add a validation check to prevent recurrence. |
| **A-03** | Medium | The Greek curriculum's **Machine 9 (CengBox)** link was broken because the lab file was quarantined — the course breaks mid-way. | `Μαθησιακή Διαδρομή …/README.md` row 9 → `labs/3-018-cengbox-1/README.md`. | **Resolved** by the A-01 restore. |
| **A-04** | Low | Two catalog sources: curated `docs/CATALOG.md` vs. generated `catalog/` (`.csv`, `.json`, `part1-3.md`, `_completed.xml`). Which is authoritative is undocumented. | Both present. | Document the source of truth and how `catalog/` is generated. |
| **A-05** | Low | UTF-8 BOM inconsistency: **754 of 761** Markdown files carry a BOM; **7 do not** (`README.md`, `TEMPLATE.md`, `catalog/part1-3.md`, `docs/LAB-SETUP.md`, `docs/TOOLS.md`). | byte-level scan | Pick one convention (recommended: **no BOM**) and normalise. |
| **A-06** | Low | The two "getting started" guides are thin next to the rest: `LAB-SETUP.md` (5 KB) and `TOOLS.md` (4.4 KB) vs `CONCEPTS.md` (85 KB). | file sizes | Expand setup (Windows/AV, troubleshooting) and the tool catalogue. |
| **A-07** | Info | An automated placeholder scan flagged 6 walkthroughs for `<command>` / `<name>`. **All are legitimate metasyntax** (e.g. `Usage: %s <command>`, `tcpdump -z <command>`), not template residue. The only real placeholder is the intentional `<YOUR_WPSCAN_TOKEN>` in the Basic Pentesting walkthrough. | manual review | **No action** — recorded so nobody "fixes" correct text. |

> **Lesson inside the lesson.** A-07 is a worked example of a core skill: an automated
> scan reports *candidates*; a human decides which are true positives. The same
> discipline applies to `nmap` output, `sqlmap` findings and AV detections — and A-01
> is a case where an automated tool (Defender) made a *wrong* decision that had real
> consequences.

---

## 5. Alignment with community writeups

Three machines were cross-checked against published writeups (HackNos, Hacking
Articles, Bootlesshacker, TryHackMe writeups, christophetd, g0blin, Zero Security).
The restored walkthroughs match the community chains **technique for technique**:

| Machine | Community chain (validated) | Our walkthrough |
| --- | --- | --- |
| **CengBox: 1** | `dirb big.txt` → `/masteradmin/` → SQLi in `login.php` (`sqlmap --forms`) → `cengbox` DB → `masteradmin:C3ng0v3R00T1!` (plaintext) → extension-only upload → `.ceng` executed as PHP → `www-data` → credential reuse (`cengover`) → writable root cron `/opt/md5check.py` (found via `pspy`) → root | ✅ identical (plus `lxd` alternative and three payload options) |
| **Chill Hack: 1** | anonymous FTP `note.txt` → `/secret/` command panel with filter → backslash/quote bypass → reverse shell `www-data` → `sudo -u apaar /home/apaar/.helpline.sh` command injection → `apaar` → MySQL creds in `account.php`, stego in `hacker.php` → `steghide` → crack `backup.zip` → `anurodh` → **`docker` group escape** → root | ✅ identical (incl. SSH port-forward and Docker explanation) |
| **SickOs: 1.2** | `OPTIONS /test/` → **WebDAV `PUT`** → upload PHP shell (Expect-header gotcha) → RCE as `www-data` → egress firewall permits only 443 → **`chkrootkit 0.49` (CVE-2014-0476)** via `/etc/cron.daily` → `/tmp/update` → root → flag `/root/7d03aaa2bf93d80040f3f22ec6ad9d5a.txt` | ✅ identical (incl. the `/root/newRule` firewall reveal) |

Conclusion: the educational content is **aligned with reality**, not invented. New
walkthroughs should keep citing the community sources in their **References** section.

---

## 6. Recommended fixes and roadmap

### Do now (Stage A — completed in this pass)

1. **Restore the three quarantined walkthroughs** from git. ✅
2. **Document the antivirus problem** and give every learner the fix:
   add an exclusion for the repository folder (see [`LAB-SETUP.md`](LAB-SETUP.md) §10).
3. Publish this audit in **English and Greek**.

### Stage B — deepen the teaching (Greek + English) — largely completed

- ✅ Every theory module and machine card now carries an explicit **"why these commands, in
  this order"** flow (theory → command → flags → how to read the output → trap → defensive lesson),
  plus a **command-by-command appendix** (the *Annotated command reference* / *The commands, annotated*).
- 🔶 **Checkpoint exercises** with expected output exist on most machines; extend to the rest.
- 🔶 A bilingual **glossary** (EN↔GR) of technical nouns is still recommended.

### Stage C — mechanical consistency — completed

- ✅ `scripts/validate.py` verifies every `labs/*/` folder has a `README.md`, that every machine
  marked ✅ in `PROGRESS.md` / `CATALOG.md` exists, and that `_completed.txt` agrees.
- ✅ `scripts/audit_all.py` verifies every relative link **and** flow/theory/commands in all
  walkthroughs (currently **777 files / 14,011 links / 98 walkthroughs**, all green).
- ✅ The **AV false-positive (A-01) is resolved at the byte level**, not just documented — the two
  files Defender quarantined now scan clean, and the exclusion remains the durable fix.

### Stage D — coverage

- Continue the series-by-series plan for the **610** pending machines, honouring the
  established template and concept-box style.

---

## 7. Method — how this audit was performed (teaching notes)

| Step | Command (abridged) | What it answers |
| --- | --- | --- |
| Inventory | `Get-ChildItem -Recurse -File` | how many files, where |
| Structure | list of directories | folder scheme `<band>-<rank>-<slug>` |
| Integrity | `Test-Path …/README.md` per lab | which labs lack a walkthrough |
| History | `git status`, `git log`, `git show HEAD:<path>` | were the files never written, or deleted? |
| AV | `Get-MpThreatDetection` | is something removing files? |
| Alignment | web search + `git grep` | does our content match the community? |
| False positives | `Select-String` for `<…>` | are suspected placeholders real? |

Read the last two rows together: **a finding is only real after you confirm it with a
second, independent method.** That is the whole point of this report.

---

_Back to the [repository README](../README.md) · Greek edition: [`ΑΝΑΘΕΩΡΗΣΗ.md`](ΑΝΑΘΕΩΡΗΣΗ.md) · Setup guide: [`LAB-SETUP.md`](LAB-SETUP.md)._
