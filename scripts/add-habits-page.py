#!/usr/bin/env python3
"""add-habits-page.py: give an existing vault the Habits and Tools page (v0.7).

The page records how the owner works and which optional items are installed
to match; the get-started skill fills it in from conversation. New vaults get
it from the template. This script, run by the updater:

  1. Copies wiki/Wiki Operations/Habits and Tools.md from the template, only if
     the vault has no page of that name (an existing page is never touched).
  2. Adds a line for it to wiki/Index.md, so the weekly check does not call it
     an orphan, under Subfolder pages, only if the Index does not already
     link it.

    python3 scripts/add-habits-page.py --vault <path>
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
PAGE_REL = Path("wiki") / "Wiki Operations" / "Habits and Tools.md"
PAGE_SRC = PACKAGE_ROOT / "vault-template" / PAGE_REL
INDEX_LINE = "- Wiki Operations: [[Habits and Tools]] (how the owner works, and the extras installed to match)\n"


def write_atomic(path: Path, text: str) -> None:
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o644
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.chmod(tmp, mode)  # keep the file's own permissions, not mkstemp's owner-only ones
    os.replace(tmp, path)


def add_page(vault: Path) -> None:
    if any(p.name == PAGE_REL.name for p in (vault / "wiki").rglob("*.md")):
        print("Habits and Tools page already in place; left as it is")
        return
    dest = vault / PAGE_REL
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(PAGE_SRC, dest)
    print(f"Habits and Tools page added: {PAGE_REL}")


def add_index_line(vault: Path) -> None:
    index = vault / "wiki" / "Index.md"
    if not index.exists():
        return
    text = index.read_text(encoding="utf-8")
    if "[[Habits and Tools" in text:
        return
    lines = text.splitlines(keepends=True)
    if lines and not lines[-1].endswith("\n"):
        lines[-1] += "\n"
    # at the end of the Subfolder pages section, where the Index keeps
    # subfolder pages; at the end of the file if there is no such section
    at = None
    for i, l in enumerate(lines):
        if l.strip().lower().startswith("## subfolder"):
            at = len(lines)
            for j in range(i + 1, len(lines)):
                if lines[j].startswith("## "):
                    at = j
                    break
            break
    if at is None:
        lines += ["\n", INDEX_LINE]
    else:
        while at > 0 and lines[at - 1].strip() == "":
            at -= 1
        lines.insert(at, INDEX_LINE if lines[at - 1].startswith("- ") else "\n" + INDEX_LINE)
    write_atomic(index, "".join(lines))
    print("line for the Habits and Tools page added to wiki/Index.md")


def main() -> int:
    ap = argparse.ArgumentParser(description="Add the Habits and Tools page to an existing Moblee vault.")
    ap.add_argument("--vault", required=True)
    args = ap.parse_args()
    vault = Path(os.path.expanduser(args.vault))
    if not (vault / "wiki").is_dir():
        print(f"No wiki/ folder at {vault}; nothing added.")
        return 1
    if not PAGE_SRC.exists():
        print(f"The template page is missing from the pack ({PAGE_SRC}); nothing added.")
        return 1
    add_page(vault)
    add_index_line(vault)
    return 0


if __name__ == "__main__":
    sys.exit(main())
