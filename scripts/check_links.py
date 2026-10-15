#!/usr/bin/env python3
"""Link + structure checker for Cybersecurity101-Labs (docs, paths, root).

Scans the curated Markdown (docs/, both Learning Paths, root) for relative links
and reports any that do not resolve. It deliberately does NOT open the lab
walkthrough *bodies* (some contain educational payloads that antivirus may
quarantine); it only checks that links into labs/<slug>/README.md resolve.

Run:  python3 scripts/check_links.py
Exit: 0 = clean, 1 = broken links found.
"""

from __future__ import annotations

import re
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SCAN_DIRS = [
    ROOT / "docs",
    ROOT / "Learning Path 1 - Introduction to Cybersecurity",
    ROOT / "Μαθησιακή Διαδρομή 1 - Εισαγωγή στην Κυβερνοασφάλεια",
]
SCAN_ROOT_FILES = [ROOT / "README.md"]

LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
SKIP_PREFIX = ("http://", "https://", "mailto:", "#", "ftp://")
FENCE_RE = re.compile(r"```.*?```", re.DOTALL)


def strip_code(text: str) -> str:
    """Remove fenced code blocks so example links inside them are not checked."""
    return FENCE_RE.sub("", text)


def normalise(target: str) -> str:
    target = target.strip()
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1]
    target = target.split("#", 1)[0]          # drop anchor
    target = urllib.parse.unquote(target)      # %CE%9C... -> Greek
    return target


def md_files() -> list[Path]:
    files: list[Path] = []
    for d in SCAN_DIRS:
        if d.is_dir():
            files.extend(sorted(d.rglob("*.md")))
    for f in SCAN_ROOT_FILES:
        if f.is_file():
            files.append(f)
    return files


def check() -> int:
    broken: list[str] = []
    scanned = 0
    for path in md_files():
        scanned += 1
        try:
            text = strip_code(path.read_text(encoding="utf-8", errors="replace"))
        except OSError as exc:
            broken.append(f"{path.relative_to(ROOT)}: cannot read ({exc})")
            continue
        for raw in LINK_RE.findall(text):
            if raw.strip().startswith(SKIP_PREFIX):
                continue
            target = normalise(raw)
            if not target:
                continue
            resolved = (path.parent / target).resolve()
            if not resolved.exists():
                broken.append(
                    f"{path.relative_to(ROOT)} -> {raw}  (missing: {target})"
                )

    print(f"scanned {scanned} Markdown files (docs, both paths, root)")
    if broken:
        print(f"\n{len(broken)} broken relative link(s):")
        for b in broken:
            print(f"  - {b}")
        return 1
    print("All relative links resolve.")
    return 0


if __name__ == "__main__":
    sys.exit(check())
