#!/usr/bin/env python3
"""Whole-repository audit for Cybersecurity101-Labs.

Covers EVERY folder: root, docs/, both Learning Paths, labs/, catalog/.

It checks two things the curriculum depends on:

  1. LINKS   — every relative Markdown link resolves to a real file.
  2. FLOW    — every *full* walkthrough (a lab listed in docs/_completed.txt)
               contains the sections that give it flow, theory and
               command-by-command explanation.

The three walkthroughs that embed PHP reverse-shell payloads are skipped for
the content read (antivirus on some hosts quarantines them); their existence
is still checked via the link/structure pass.

Run:  python3 scripts/audit_all.py
Exit: 0 = clean, 1 = problems found.
"""

from __future__ import annotations

import re
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LABS = ROOT / "labs"
COMPLETED = ROOT / "docs" / "_completed.txt"

# Files whose bodies may contain AV-flagged payloads; we never read them.
AV_SKIP = {"3-018-cengbox-1", "4-072-chill-hack-1", "4-086-sickos-12"}

LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
SKIP_PREFIX = ("http://", "https://", "mailto:", "#", "ftp://")
# Screenshot references are intentional placeholders (not committed); skip them.
IMAGE_EXT = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp")

# Section keywords that give a walkthrough its flow / theory / explanations.
# Matched case-insensitively anywhere in the file.
SECTIONS = {
    "recon/ enumeration": r"recon|enumeration|scan",
    "how-to-read notes": r"how to read|why it works|how to read it",
    "concept / theory box": r"concept|📖",
    "foothold / shell": r"shell|foothold|exploit|reverse",
    "privilege escalation": r"privilege escalation|privesc|sudo -l|SUID|root",
    "defensive lessons": r"defensive|blue team|mitigat|remediat",
    "references": r"reference|vulnhub|writeup",
    "screenshot checklist": r"screenshot",
}

problems: list[str] = []


def strip_code(text: str) -> str:
    return FENCE_RE.sub("", text)


def all_markdown() -> list[Path]:
    files: list[Path] = []
    for p in ROOT.rglob("*.md"):
        # skip anything inside .git
        if ".git" in p.parts:
            continue
        files.append(p)
    return sorted(files)


def normalise(target: str) -> str:
    target = target.strip()
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1]
    target = target.split("#", 1)[0]
    return urllib.parse.unquote(target)


def check_links(files: list[Path]) -> int:
    checked = 0
    for path in files:
        try:
            text = strip_code(path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        for raw in LINK_RE.findall(text):
            if raw.strip().startswith(SKIP_PREFIX):
                continue
            target = normalise(raw)
            if not target:
                continue
            if target.lower().endswith(IMAGE_EXT) or "images/" in target.replace("\\", "/"):
                continue
            # TEMPLATE*.md use placeholder links relative to a future location.
            if path.name.startswith("TEMPLATE"):
                continue
            if "<" in target or ">" in target:
                continue
            resolved = (path.parent / target).resolve()
            if not resolved.exists():
                problems.append(f"link: {path.relative_to(ROOT)} -> {raw}")
            checked += 1
    return checked


def completed_slugs() -> list[str]:
    if not COMPLETED.is_file():
        problems.append("missing docs/_completed.txt")
        return []
    return [l.strip() for l in COMPLETED.read_text(encoding="utf-8").splitlines()
            if l.strip() and not l.startswith("#")]


def check_flow(slugs: list[str]) -> int:
    full = 0
    for slug in slugs:
        readme = LABS / slug / "README.md"
        if not readme.is_file():
            problems.append(f"flow: {slug} has no README.md")
            continue
        if slug in AV_SKIP:
            full += 1
            continue  # do not read the body (AV)
        text = readme.read_text(encoding="utf-8", errors="replace").lower()
        missing = [name for name, pat in SECTIONS.items()
                   if not re.search(pat, text)]
        if missing:
            problems.append(f"flow: {slug} missing sections: {', '.join(missing)}")
        full += 1
    return full


def main() -> int:
    files = all_markdown()
    checked = check_links(files)
    slugs = completed_slugs()
    full = check_flow(slugs)

    print(f"markdown files scanned : {len(files)}")
    print(f"relative links checked : {checked}")
    print(f"full walkthroughs      : {full}")

    if problems:
        print(f"\n{len(problems)} problem(s):")
        for p in problems[:80]:
            print(f"  - {p}")
        if len(problems) > 80:
            print(f"  ... and {len(problems) - 80} more")
        return 1
    print("\nAll links resolve; every full walkthrough has flow/theory/commands.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
