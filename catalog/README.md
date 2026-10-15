# `catalog/` — raw VulnHub data (generated)

> **Short version:** this folder holds the **raw, machine-readable VulnHub data** from which the
> human-readable index was built. The **source of truth for humans is
> [`../docs/CATALOG.md`](../docs/CATALOG.md)**. This folder is data, not documentation.

If you are looking for the catalog to *read*, go to [`../docs/CATALOG.md`](../docs/CATALOG.md)
(all 708 machines, rated and linked) or [`../docs/PROGRESS.md`](../docs/PROGRESS.md) (the finished
walkthroughs). This folder exists so the catalog can be regenerated and cross-checked.

## What each file is

| File | Format | Contents | Notes |
| --- | --- | --- | --- |
| `catalog.json` | JSON array | one record per VM: `slug`, name, difficulty, description, entry URL, author, date | UTF-8 **with BOM** |
| `master-catalog.csv` | CSV | `Name, Difficulty, Description, EntryUrl, Author, Date` | the same data, spreadsheet-friendly |
| `part1.md`, `part2.md`, `part3.md` | Markdown tables | the same data split into three parts (a scrape artifact) | older export; **contains mojibake** in some descriptions (`It�??s`) |
| `_completed.xml` | PowerShell CLIXML | the list of finished walkthrough slugs | a `Select-Object` export artifact |

## The relationship to the rest of the repository

```text
catalog/*  (raw scrape/export)   ──generated into──▶   docs/CATALOG.md, docs/PROGRESS.md
                                                        (human-readable, source of truth)
```

- **`docs/CATALOG.md`** — the curated, difficulty-sorted index of **all 708** machines. Every
  machine links to its `labs/<band>-<rank>-<slug>/` folder.
- **`docs/PROGRESS.md`** — just the **98** finished walkthroughs, with authors and dates.
- **`docs/_completed.txt`** — the flat slug list the validation script reads
  ([`../scripts/validate.py`](../scripts/validate.py)).
- **`labs/<band>-<rank>-<slug>/README.md`** — the walkthroughs themselves.

## Known encoding caveats

- `catalog.json` and most `.md` files carry a **UTF-8 BOM**; a few do not. Tools that read them
  should use `utf-8-sig` (Python) or equivalent.
- `part1.md`–`part3.md` were exported before the encoding was normalised and show replacement
  characters (`�`) in some descriptions. They are **not** the reading copy — use
  `docs/CATALOG.md`.

## Regenerating / validating

Do not edit these files by hand. To check the repository is internally consistent (every lab has a
walkthrough; the metadata agrees), run:

```bash
python3 ../scripts/validate.py     # labs vs _completed.txt vs PROGRESS.md
python3 ../scripts/audit_all.py    # every link in every folder
```

---

## Στα ελληνικά

Ο φάκελος `catalog/` περιέχει **ακατέργαστα δεδομένα** (JSON/CSV/Markdown/XML) από το VulnHub, από
τα οποία παράγεται ο ανθρώπινα αναγνώσιμος κατάλογος. **Η πηγή αλήθειας για τον αναγνώστη είναι το
[`../docs/CATALOG.md`](../docs/CATALOG.md)** (όλα τα 708 μηχανήματα) και το
[`../docs/PROGRESS.md`](../docs/PROGRESS.md) (τα ολοκληρωμένα walkthroughs). Μην επεξεργάζεστε αυτά
τα αρχεία με το χέρι — ελέγξτε τη συνέπεια με τα `../scripts/validate.py` και `../scripts/audit_all.py`.

---

_Back to the [repository README](../README.md) · [reading order](../docs/INDEX.md)._
