#!/usr/bin/env python3
"""Write a CLAUDE.md large enough that the pack's own commit gate refuses it.

Reproduces the real 21 September 2026 fault rather than simulating it: an
owner's rules file had grown past the gate's 10,000-token cap, so the update's
closing commit was refused. An earlier version of the test installed its own
pre-commit hook, which the updater correctly moved aside — the updater points
git at scripts/hooks/ so that only one gate runs — and so tested nothing at all.

Usage: make-oversized-claude-md.py <path to CLAUDE.md>
"""
import sys
from pathlib import Path

# The gate counts roughly four characters to the token and caps the rules file
# at 10,000, so comfortably past it without being absurd.
TARGET_CHARS = 48_000

HEAD = """# CLAUDE.md

The rules this wiki follows. This copy is deliberately over the commit gate's
size cap, so that an update's closing commit is refused and the test can check
that every place reporting on the update says so.

## Habits and tools

A placeholder the updater's own patcher replaces.

## Padding

"""

LINE = ("This paragraph exists only to take up room, and says nothing an owner "
        "would ever want to read, which is rather the point of it. ")


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    target = Path(sys.argv[1])
    body = HEAD + (LINE * ((TARGET_CHARS - len(HEAD)) // len(LINE) + 1))
    target.write_text(body, encoding="utf-8")
    print(f"wrote {target} at {len(body)} characters (~{len(body)//4} tokens)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
