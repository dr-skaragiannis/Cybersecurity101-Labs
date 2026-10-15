# <Machine Name> — Lesson Card (method-first)

> **Copy this file to `Learning Path 1 - Introduction to Cybersecurity/Machines/<NN>-<slug>.md`**
> (and its Greek mirror to `Μαθησιακή Διαδρομή 1 …/Μηχανές/<NN>-<slug>.md`).
>
> This is the **machine-card** template — the *lesson* that accompanies a full walkthrough. It is
> deliberately **method-first**: it teaches the idea, then the machine, then explains every command
> **logically**, and finally gives defensive lessons, review questions, a hints ladder and
> references. The full walkthrough lives separately in `labs/<band>-<rank>-<slug>/README.md`; the
> card links to it and never duplicates its screenshots.
>
> Keep both language editions **structurally identical** (same Parts A–H, same section order).

---

| | |
| --- | --- |
| **Machine** | <name> |
| **Author** | <author> |
| **Released** | <date> |
| **Target OS** | <distro/version — key services and versions> |
| **VulnHub** | <https://vulnhub.com/entry/...> |
| **Flags / objective** | <user.txt + root.txt, or "root shell only"> |
| **Estimated time** | <N hours> |

> **Position:** <n> of 13 · **Band <1–7> — <label>** (global rank **<rank>** of 708)
> **Full writeup:** [`labs/<band>-<rank>-<slug>/README.md`](../../labs/<band>-<rank>-<slug>/README.md)

> *(Optional)* A short note if a widely-repeated fact about this machine is **wrong** — state the
> correction and the evidence, as a lesson in verifying assumptions against several sources.

---

## How to use this card

A one-paragraph orientation: this is not a list of commands; it has three parts — **A** the method
and theory, **B** the machine, **C** the walkthrough (every command explained logically). State the
study rule: read, then close the card, revert the snapshot, and redo from memory.

---

# Part A — The method (theory before the first command)

The **new idea(s)** this machine introduces, each explained in plain language *before* any command.
Draw on [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md). Typical subsections:

- **A.1** The new skill (in one line — e.g. "recognising an encoding", "content discovery",
  "capabilities vs SUID", "container escapes").
- **A.2** The core concept (encoding vs hashing vs encryption / SQLi techniques / LFI→RCE /
  log poisoning / predictable randomness …), with a small table where useful.
- **A.3** A "why it works" or "how to tell" section (e.g. how to read `sudo -l`, why reverse beats
  bind, why `getimagesize()` is fooled by magic bytes).
- **A.4+** Any additional primitive (PATH hijacking, command injection, RID cycling, the `docker`
  group, PAM, GPG, firewalls, YARA …).

> Use a **> 📖 Concept**-style callout for the single most important idea, and a bolded "single
> biggest lesson" sentence.

---

# Part B — The machine

- **B.1 What you will learn** — a numbered list of concrete skills.
- **B.2 The map** — a table of the stages and *where* on the box each lives (this is the flow).
- **B.3 Before you start** — links to the theory modules to read first, plus 4–5 questions the
  learner should answer **before** and verify during the lab.

---

# Part C — The walkthrough, step by step

Every command block uses the **same six labels**, so the reader always knows what to expect:

> **Why** → **The command** → **What it does** → **What you will see** → **How to read it** → **Trap**

- Explain the **logic** (why we run it, what it does internally), not just the flags.
- Show realistic output in a `text` block and read it **line by line**.
- Add a **Trap** for the classic silent failure (wrong `LHOST`, quoting a `$` hash, forgetting `-p`,
  a missing TTY, an unencoded `&`, …).
- Note where the learner should **restore** state (e.g. reset `$PATH`, remove artefacts).

Group the steps into phases: reconnaissance → enumeration → foothold → privilege escalation →
flags/cleanup.

---

# Part D — Defensive lessons

A table: **finding → fix**. Cover every technique used, and end with the **single biggest lesson**
of the box. This is the blue-team half and is not optional.

---

# Part E — Review questions

5–10 questions that force understanding (not recall): compare routes, explain a mechanism, justify a
design choice, say how a finding would be fixed.

---

# Part F — Hints ladder

`<details>` blocks, rung 1 → rung 5, with the explicit rule: read rung 1; only escalate when
genuinely stuck; **do not open rung 5 until you have tried everything**.

---

# Part G — References

- **VulnHub entry:** <link>
- **English lab:** [`labs/<slug>/README.md`](../../labs/<slug>/README.md)
- **Greek mirror of this card:** link
- **Cross-checked writeups** (2–4 community writeups you actually verified against):
  - [title](url) …

---

# Part H — If you get completely stuck

Connectivity checks, the common gotcha for this box, and a reminder that reverting the snapshot and
redoing from memory is the point.

---

_Back to [Learning Path 1](../README.md) · previous: … · next: … · full writeup: [`labs/<slug>`](../../labs/<slug>/README.md)._
