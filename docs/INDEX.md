# The repository, in reading order

> Everything in this repository, arranged the way a learner should actually meet it.
> If you are new, start at **step 0** and work down. If you are looking for one
> specific thing, jump to the section that names it.

---

## 0. Set up your lab (once)

| Step | Document | Why |
| --- | --- | --- |
| 1 | [`LAB-SETUP.md`](LAB-SETUP.md) | Install a hypervisor + Kali, build an **isolated** network |
| 2 | [`LAB-SETUP.md` §10](LAB-SETUP.md#10-windows--antivirus--keep-your-lab-files-from-being-deleted) | **On Windows:** exclude the repo folder from antivirus or it deletes walkthroughs |
| 3 | [`TOOLS.md`](TOOLS.md) | What each tool in the repository does |

---

## 1. Learn the fundamentals (reference — dip in as needed)

| Document | What it is |
| --- | --- |
| [`CONCEPTS.md`](CONCEPTS.md) | The **18-section primer**: networking, nmap, enumeration, wordlists, encoding vs hashing vs encryption, shells, Linux privilege escalation, post-exploitation, reporting. Read it once and every lab becomes predictable. |

---

## 2. Follow a curriculum (the main path)

Pick **one** language — the two are complete mirrors of each other.

| | English | Greek |
| --- | --- | --- |
| Course home | [Learning Path 1](<../Learning Path 1 - Introduction to Cybersecurity/README.md>) | [Μαθησιακή Διαδρομή 1](<../Μαθησιακή Διαδρομή 1 - Εισαγωγή στην Κυβερνοασφάλεια/README.md>) |

**The order inside the course:**

1. **Theory modules 00–06** (offence), read *before* the machines that use them:
   `00` setup · `01` networking & recon · `02` web attacks · `03` service attacks ·
   `04` credentials & cracking · `05` Linux privilege escalation · `06` shells, persistence & escapes.
2. **The 13 machines**, in order — each one introduces one new attack class and
   repeats the previous ones. Machine cards live in `Machines/` (EN) and `Μηχανές/` (GR);
   the full walkthroughs live in [`labs/`](../labs/).
3. **Theory modules 07–11** (systems & defence — the *extended track*):
   `07` permissions, DAC & MAC · `08` identity, authentication & PAM ·
   `09` cryptography, GPG & file encryption · `10` firewalls & sandboxing ·
   `11` malware analysis & YARA. Each maps to existing band-3/4 labs.

> **A machine card is the lesson; a lab is the walkthrough.** The card teaches the
> *method* and lists what to read first; the `labs/<slug>/README.md` shows the
> commands with real output, line by line.

### Complete interleaved schedule (theory modules ↔ machine cards ↔ lab walkthroughs)

| Step | Theory to read first (EN / GR) | Lesson Card (EN / GR) | Full Lab Walkthrough |
| --: | --- | --- | --- |
| **0** | [`00-Before-You-Start`](<../Learning Path 1 - Introduction to Cybersecurity/00-Before-You-Start.md>) · [`00-Πριν-Ξεκινήσεις`](<../Μαθησιακή Διαδρομή 1 - Εισαγωγή στην Κυβερνοασφάλεια/00-Πριν-Ξεκινήσεις.md>) | — | [`LAB-SETUP.md`](LAB-SETUP.md) · [`TOOLS.md`](TOOLS.md) |
| **1** | [`01-Foundations`](<../Learning Path 1 - Introduction to Cybersecurity/01-Foundations-Networking-and-Recon.md>) · [`01-Βάσεις`](<../Μαθησιακή Διαδρομή 1 - Εισαγωγή στην Κυβερνοασφάλεια/01-Βάσεις-Δικτύωση-και-Αναγνώριση.md>) | [EN 01](<../Learning Path 1 - Introduction to Cybersecurity/Machines/01-basic-pentesting-1.md>) · [GR 01](<../Μαθησιακή Διαδρομή 1 - Εισαγωγή στην Κυβερνοασφάλεια/Μηχανές/01-basic-pentesting-1.md>) | [`labs/2-001-basic-pentesting-1`](../labs/2-001-basic-pentesting-1/README.md) |
| **2** | [`04-Credentials`](<../Learning Path 1 - Introduction to Cybersecurity/04-Credentials-and-Cracking.md>) · [`04-Διαπιστευτήρια`](<../Μαθησιακή Διαδρομή 1 - Εισαγωγή στην Κυβερνοασφάλεια/04-Διαπιστευτήρια-και-Σπασίματα.md>) (§1–2) | [EN 02](<../Learning Path 1 - Introduction to Cybersecurity/Machines/02-cybersploit-1.md>) · [GR 02](<../Μαθησιακή Διαδρομή 1 - Εισαγωγή στην Κυβερνοασφάλεια/Μηχανές/02-cybersploit-1.md>) | [`labs/2-002-cybersploit-1`](../labs/2-002-cybersploit-1/README.md) |
| **3** | [`02-Web-Attacks`](<../Learning Path 1 - Introduction to Cybersecurity/02-Web-Attacks.md>) · [`02-Επιθέσεις-στο-Web`](<../Μαθησιακή Διαδρομή 1 - Εισαγωγή στην Κυβερνοασφάλεια/02-Επιθέσεις-στο-Web.md>) + [`05`](<../Learning Path 1 - Introduction to Cybersecurity/05-Linux-Privilege-Escalation.md>) | [EN 03](<../Learning Path 1 - Introduction to Cybersecurity/Machines/03-dc-1.md>) · [GR 03](<../Μαθησιακή Διαδρομή 1 - Εισαγωγή στην Κυβερνοασφάλεια/Μηχανές/03-dc-1.md>) | [`labs/2-003-dc-1`](../labs/2-003-dc-1/README.md) |
| **4** | [`04-Credentials`](<../Learning Path 1 - Introduction to Cybersecurity/04-Credentials-and-Cracking.md>) + [`06-Shells`](<../Learning Path 1 - Introduction to Cybersecurity/06-Shells-Persistence-and-Escapes.md>) · [`06-Κελύφη`](<../Μαθησιακή Διαδρομή 1 - Εισαγωγή στην Κυβερνοασφάλεια/06-Κελύφη-Εμμονή-και-Διαφυγές.md>) | [EN 04](<../Learning Path 1 - Introduction to Cybersecurity/Machines/04-dc-2.md>) · [GR 04](<../Μαθησιακή Διαδρομή 1 - Εισαγωγή στην Κυβερνοασφάλεια/Μηχανές/04-dc-2.md>) | [`labs/2-004-dc-2`](../labs/2-004-dc-2/README.md) |
| **5** | [`03-Service-Attacks`](<../Learning Path 1 - Introduction to Cybersecurity/03-Service-and-Network-Attacks.md>) · [`03-Υπηρεσίες`](<../Μαθησιακή Διαδρομή 1 - Εισαγωγή στην Κυβερνοασφάλεια/03-Επιθέσεις-σε-Υπηρεσίες.md>) | [EN 05](<../Learning Path 1 - Introduction to Cybersecurity/Machines/05-kioptrix-level-1-1.md>) · [GR 05](<../Μαθησιακή Διαδρομή 1 - Εισαγωγή στην Κυβερνοασφάλεια/Μηχανές/05-kioptrix-level-1-1.md>) | [`labs/3-046-kioptrix-level-1-1`](../labs/3-046-kioptrix-level-1-1/README.md) |
| **6** | [`02-Web-Attacks`](<../Learning Path 1 - Introduction to Cybersecurity/02-Web-Attacks.md>) (§5) + [`06-Shells`](<../Learning Path 1 - Introduction to Cybersecurity/06-Shells-Persistence-and-Escapes.md>) (§1–2) | [EN 06](<../Learning Path 1 - Introduction to Cybersecurity/Machines/06-bossplayersctf-1.md>) · [GR 06](<../Μαθησιακή Διαδρομή 1 - Εισαγωγή στην Κυβερνοασφάλεια/Μηχανές/06-bossplayersctf-1.md>) | [`labs/3-016-bossplayersctf-1`](../labs/3-016-bossplayersctf-1/README.md) |
| **7** | [`02-Web-Attacks`](<../Learning Path 1 - Introduction to Cybersecurity/02-Web-Attacks.md>) (§2, §7) + [`04-Credentials`](<../Learning Path 1 - Introduction to Cybersecurity/04-Credentials-and-Cracking.md>) (§4) | [EN 07](<../Learning Path 1 - Introduction to Cybersecurity/Machines/07-mr-robot-1.md>) · [GR 07](<../Μαθησιακή Διαδρομή 1 - Εισαγωγή στην Κυβερνοασφάλεια/Μηχανές/07-mr-robot-1.md>) | [`labs/3-053-mr-robot-1`](../labs/3-053-mr-robot-1/README.md) |
| **8** | [`03-Service-Attacks`](<../Learning Path 1 - Introduction to Cybersecurity/03-Service-and-Network-Attacks.md>) (§2) + [`05-Linux-PrivEsc`](<../Learning Path 1 - Introduction to Cybersecurity/05-Linux-Privilege-Escalation.md>) (§3) | [EN 08](<../Learning Path 1 - Introduction to Cybersecurity/Machines/08-empire-breakout.md>) · [GR 08](<../Μαθησιακή Διαδρομή 1 - Εισαγωγή στην Κυβερνοασφάλεια/Μηχανές/08-empire-breakout.md>) | [`labs/3-028-empire-breakout`](../labs/3-028-empire-breakout/README.md) |
| **9** | [`02-Web-Attacks`](<../Learning Path 1 - Introduction to Cybersecurity/02-Web-Attacks.md>) (§3, §6) + [`05-Linux-PrivEsc`](<../Learning Path 1 - Introduction to Cybersecurity/05-Linux-Privilege-Escalation.md>) (§4–5) | [EN 09](<../Learning Path 1 - Introduction to Cybersecurity/Machines/09-cengbox-1.md>) · [GR 09](<../Μαθησιακή Διαδρομή 1 - Εισαγωγή στην Κυβερνοασφάλεια/Μηχανές/09-cengbox-1.md>) | [`labs/3-018-cengbox-1`](../labs/3-018-cengbox-1/README.md) |
| **10** | [`02-Web-Attacks`](<../Learning Path 1 - Introduction to Cybersecurity/02-Web-Attacks.md>) (§4, §6) + [`05-Linux-PrivEsc`](<../Learning Path 1 - Introduction to Cybersecurity/05-Linux-Privilege-Escalation.md>) (§7) | [EN 10](<../Learning Path 1 - Introduction to Cybersecurity/Machines/10-pwnlab-init.md>) · [GR 10](<../Μαθησιακή Διαδρομή 1 - Εισαγωγή στην Κυβερνοασφάλεια/Μηχανές/10-pwnlab-init.md>) | [`labs/3-057-pwnlab-init`](../labs/3-057-pwnlab-init/README.md) |
| **11** | [`03-Service-Attacks`](<../Learning Path 1 - Introduction to Cybersecurity/03-Service-and-Network-Attacks.md>) (§2) + [`02-Web-Attacks`](<../Learning Path 1 - Introduction to Cybersecurity/02-Web-Attacks.md>) (§6) | [EN 11](<../Learning Path 1 - Introduction to Cybersecurity/Machines/11-photographer-1.md>) · [GR 11](<../Μαθησιακή Διαδρομή 1 - Εισαγωγή στην Κυβερνοασφάλεια/Μηχανές/11-photographer-1.md>) | [`labs/3-055-photographer-1`](../labs/3-055-photographer-1/README.md) |
| **12** | [`03-Service-Attacks`](<../Learning Path 1 - Introduction to Cybersecurity/03-Service-and-Network-Attacks.md>) (§3) + [`02-Web-Attacks`](<../Learning Path 1 - Introduction to Cybersecurity/02-Web-Attacks.md>) (§4) | [EN 12](<../Learning Path 1 - Introduction to Cybersecurity/Machines/12-symfonos-1.md>) · [GR 12](<../Μαθησιακή Διαδρομή 1 - Εισαγωγή στην Κυβερνοασφάλεια/Μηχανές/12-symfonos-1.md>) | [`labs/3-062-symfonos-1`](../labs/3-062-symfonos-1/README.md) |
| **13** | [`06-Shells`](<../Learning Path 1 - Introduction to Cybersecurity/06-Shells-Persistence-and-Escapes.md>) (§5–7) + [`05-Linux-PrivEsc`](<../Learning Path 1 - Introduction to Cybersecurity/05-Linux-Privilege-Escalation.md>) (§8) | [EN 13](<../Learning Path 1 - Introduction to Cybersecurity/Machines/13-hackinos-1.md>) · [GR 13](<../Μαθησιακή Διαδρομή 1 - Εισαγωγή στην Κυβερνοασφάλεια/Μηχανές/13-hackinos-1.md>) | [`labs/3-040-hackinos-1`](../labs/3-040-hackinos-1/README.md) |
| **14–18** | Extended Systems Track: [`07`](<../Learning Path 1 - Introduction to Cybersecurity/07-Permissions-and-Access-Control.md>) · [`08`](<../Learning Path 1 - Introduction to Cybersecurity/08-Identity-Authentication-and-PAM.md>) · [`09`](<../Learning Path 1 - Introduction to Cybersecurity/09-Cryptography-GPG-and-Encryption.md>) · [`10`](<../Learning Path 1 - Introduction to Cybersecurity/10-Firewalls-and-Sandboxing.md>) · [`11`](<../Learning Path 1 - Introduction to Cybersecurity/11-Malware-Analysis-and-YARA.md>) | ([GR 07](<../Μαθησιακή Διαδρομή 1 - Εισαγωγή στην Κυβερνοασφάλεια/07-Δικαιώματα-και-Έλεγχος-Πρόσβασης.md>) · [08](<../Μαθησιακή Διαδρομή 1 - Εισαγωγή στην Κυβερνοασφάλεια/08-Ταυτότητα-Πιστοποίηση-και-PAM.md>) · [09](<../Μαθησιακή Διαδρομή 1 - Εισαγωγή στην Κυβερνοασφάλεια/09-Κρυπτογραφία-GPG-και-Κρυπτογράφηση.md>) · [10](<../Μαθησιακή Διαδρομή 1 - Εισαγωγή στην Κυβερνοασφάλεια/10-Τείχη-Προστασίας-και-Sandboxing.md>) · [11](<../Μαθησιακή Διαδρομή 1 - Εισαγωγή στην Κυβερνοασφάλεια/11-Ανάλυση-Κακόβουλου-Λογισμικού-και-YARA.md>)) | [`3-068-w1r3s-101`](../labs/3-068-w1r3s-101/README.md) · [`3-031-fristileaks-13`](../labs/3-031-fristileaks-13/README.md) · [`4-073-dc-7`](../labs/4-073-dc-7/README.md) · [`4-086-sickos-12`](../labs/4-086-sickos-12/README.md) · [`5-097-tr0ll-2`](../labs/5-097-tr0ll-2/README.md) |

---

## 3. Go further

| Resource | Use |
| --- | --- |
| [`BEGINNER-PATH.md`](BEGINNER-PATH.md) | A suggested order if you are not following the full course |
| [`PROGRESS.md`](PROGRESS.md) | The 98 finished walkthroughs, by difficulty |
| [`CATALOG.md`](CATALOG.md) | **All 708** VulnHub machines, indexed and rated |
| [`../labs/`](../labs/) | Every walkthrough folder, `<band>-<rank>-<slug>/` |
| Bridge labs (band 3) | One extra attack class each — see the course README's "Deliberately not in this path" |

---

## 4. Reference and meta

| Document | What it is |
| --- | --- |
| [`AUDIT.md`](AUDIT.md) | Repository audit: structure, consistency, the antivirus fix, alignment with community writeups |
| [`ΑΝΑΘΕΩΡΗΣΗ.md`](ΑΝΑΘΕΩΡΗΣΗ.md) | Ο ίδιος απολογισμός στα Ελληνικά |
| [`../TEMPLATE.md`](../TEMPLATE.md) | The standard **lab-walkthrough** template |
| [`../TEMPLATE-card.md`](../TEMPLATE-card.md) | The **machine-card** (lesson) template — method-first A–H |
| [`../catalog/README.md`](../catalog/README.md) | What the raw `catalog/` data is, and the encoding caveats |
| [`../scripts/validate.py`](../scripts/validate.py) | Checks that every lab has a walkthrough and the metadata agrees |
| [`../scripts/check_links.py`](../scripts/check_links.py) | Checks that every relative link in the docs and both paths resolves |
| [`../scripts/audit_all.py`](../scripts/audit_all.py) | Whole-repo audit: links **and** flow/theory/commands in every walkthrough |

---

## How the file tree maps to this order

```text
Cybersecurity101-Labs/
├── README.md                         ← repository overview
├── TEMPLATE.md                       ← writeup template
├── docs/
│   ├── INDEX.md  ← you are here      ← the reading order (this file)
│   ├── CONCEPTS.md                   ← step 1: fundamentals
│   ├── LAB-SETUP.md · TOOLS.md       ← step 0: setup
│   ├── BEGINNER-PATH.md · PROGRESS.md · CATALOG.md  ← step 3: browse
│   └── AUDIT.md · ΑΝΑΘΕΩΡΗΣΗ.md      ← step 4: audit
├── Learning Path 1 - Introduction to Cybersecurity/   ← step 2 (EN)
│   ├── README.md
│   ├── 00-…md … 11-…md               ← theory modules, in order
│   └── Machines/01-…md … 13-…md      ← machine cards, in order
├── Μαθησιακή Διαδρομή 1 - Εισαγωγή στην Κυβερνοασφάλεια/  ← step 2 (GR, mirror)
│   ├── README.md
│   ├── 00-…md … 11-…md
│   └── Μηχανές/01-…md … 13-…md
├── labs/<band>-<rank>-<slug>/README.md  ← the walkthroughs (step 2 & 3)
└── catalog/                          ← generated catalog data
```

> **Why the labs are not reordered.** Lab folders are named
> `<band>-<rank>-<slug>` — difficulty band, then a single global rank `001–708`.
> That *is* the logical order (easiest first), and every document links into it by
> that name. Reordering the folders would break hundreds of links for no gain; the
> reading order above is the layer that turns that flat, difficulty-ordered set into
> a guided course.

---

_Back to the [repository README](../README.md) · Greek: [`ΕΥΡΕΤΗΡΙΟ.md`](ΕΥΡΕΤΗΡΙΟ.md)._
