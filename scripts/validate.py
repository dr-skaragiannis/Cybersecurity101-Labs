#!/usr/bin/env python3
"""Consistency validator for Cybersecurity101-Labs.

Run from anywhere:  python3 scripts/validate.py

It checks the invariants that an audit found could silently drift:
  1. Every folder in labs/ contains a README.md (a walkthrough).
  2. Every slug listed in docs/_completed.txt resolves to a real lab folder.
  3. Every lab referenced as complete in docs/PROGRESS.md exists on disk.
  4. Reports totals so you can compare against README/PROGRESS claims.

Exit code 0 = all good, 1 = problems found. No third-party dependencies.

Why this exists: on Windows, antivirus can quarantine walkthroughs that embed
educational reverse-shell payloads. The files are tracked by git, so they are
recoverable (`git checkout -- .`), but *silently* the metadata then lies. This
script turns that silent failure into a loud one.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LABS = ROOT / "labs"
COMPLETED = ROOT / "docs" / "_completed.txt"
PROGRESS = ROOT / "docs" / "PROGRESS.md"

problems: list[str] = []


def lab_folders() -> list[Path]:
    if not LABS.is_dir():
        problems.append(f"missing directory: {LABS}")
        return []
    return sorted(p for p in LABS.iterdir() if p.is_dir())


def check_readmes(folders: list[Path]) -> None:
    for folder in folders:
        if not (folder / "README.md").is_file():
            problems.append(f"lab without a walkthrough: {folder.name}/README.md")


def completed_slugs() -> list[str]:
    if not COMPLETED.is_file():
        problems.append(f"missing file: {COMPLETED}")
        return []
    return [
        line.strip()
        for line in COMPLETED.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]


def check_completed(slugs: list[str], folders: list[Path]) -> None:
    present = {f.name for f in folders}
    for slug in slugs:
        if slug not in present:
            problems.append(f"_completed.txt lists a missing lab folder: {slug}")
        elif not (LABS / slug / "README.md").is_file():
            problems.append(f"_completed.txt lists a lab with no walkthrough: {slug}")


def progress_links() -> list[str]:
    if not PROGRESS.is_file():
        problems.append(f"missing file: {PROGRESS}")
        return []
    text = PROGRESS.read_text(encoding="utf-8")
    # Markdown links of the form ../labs/<slug>/README.md
    return re.findall(r"\.\./labs/([^/)\s]+)/README\.md", text)


def main() -> int:
    folders = lab_folders()
    check_readmes(folders)
    slugs = completed_slugs()
    check_completed(slugs, folders)

    linked = progress_links()
    present = {f.name for f in folders}
    for slug in linked:
        if slug not in present:
            problems.append(f"PROGRESS.md links a missing lab: {slug}")

    print(f"lab folders            : {len(folders)}")
    print(f"walkthroughs on disk   : {sum(1 for f in folders if (f / 'README.md').is_file())}")
    print(f"_completed.txt entries : {len(slugs)}")
    print(f"PROGRESS.md links      : {len(linked)}")

    if problems:
        print(f"\n{len(problems)} problem(s) found:")
        for p in problems:
            print(f"  - {p}")
        return 1

    print("\nAll consistency checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
