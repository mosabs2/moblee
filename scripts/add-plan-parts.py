#!/usr/bin/env python3
"""add-plan-parts.py — give the daily note template the Plan's three parts (0.16.0).

From 0.16.0 the Plan in a daily note is the day's to-do list in three parts:
the owner's to-dos, most urgent first; "### Waiting on others"; "### Standing".
New wikis get them from the template. This script, run by the updater, adds
the two subheadings to an existing `Daily Notes/_TEMPLATE.md`:

  * only when the template has a "## Plan" heading and neither subheading yet;
  * by adding two lines and their blank lines at the end of the Plan section,
    before the next "## " heading, and touching nothing else;
  * never to a daily note itself, which is the owner's and the assistant's.

    python3 scripts/add-plan-parts.py --vault <path>
    python3 scripts/add-plan-parts.py --vault <path> --dry-run

Prints "added" when it changed the template, so the updater knows to commit it.
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

PARTS = ("### Waiting on others", "### Standing")


def add_parts(text: str) -> str | None:
    """The template with the two subheadings added, or None to leave it."""
    lines = text.split("\n")
    if any(l.strip() in PARTS for l in lines):
        return None
    start = next((i for i, l in enumerate(lines) if l.strip() == "## Plan"), None)
    if start is None:
        return None
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    j = end
    while j > start + 1 and lines[j - 1].strip() == "":
        j -= 1
    # The blank lines that followed the Plan's last line stay where they were,
    # after the new parts, so the next heading keeps its spacing.
    tail = lines[j:]
    if tail and tail[0].startswith("## "):
        tail = [""] + tail
    return "\n".join(lines[:j] + ["", PARTS[0], "", PARTS[1]] + tail)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault", required=True)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    path = Path(a.vault).expanduser() / "Daily Notes" / "_TEMPLATE.md"
    if not path.is_file():
        print("no daily note template; nothing to change")
        return 0
    text = path.read_text(encoding="utf-8")
    new = add_parts(text)
    if new is None or new == text:
        print("the daily note template already has the Plan's parts, or has no Plan; left as it is")
        return 0
    if a.dry_run:
        print("would add the Plan's two parts to Daily Notes/_TEMPLATE.md")
        return 0
    mode = path.stat().st_mode & 0o777
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(new)
    os.chmod(tmp, mode)
    os.replace(tmp, path)
    print("added the Plan's two parts (Waiting on others, Standing) to Daily Notes/_TEMPLATE.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
