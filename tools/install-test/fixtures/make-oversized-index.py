#!/usr/bin/env python3
"""Write a wiki/Index.md large enough that the pack's own commit gate refuses it.

The gate caps the always-loaded files when they are staged: _context.md at
12,000 tokens, the rules file at 10,000 and Index.md at 8,000, counting roughly
four characters to the token (G3). An Index past its cap is the same rule and
the same shape as the oversized CLAUDE.md that refused a real owner's update on
21 September 2026, and it is the one of the three that the installer's closing
commit actually stages: the starting-memories step adds the new page to the
Index's "Wiki Operations" line, so the file is modified after the first commit
and staged for the second, which is the commit the gate is wired to judge.

The "Wiki Operations" line below is load-bearing — seed-memory.py adds its link
to that line and to no other, and with no such line the Index is never touched,
never staged, and the gate never sees it.

Usage: make-oversized-index.py <path to Index.md>
"""
import sys
from pathlib import Path

TARGET_CHARS = 40_000          # ~10,000 tokens, comfortably over the 8,000 cap

HEAD = """# Index

The wiki's contents. This copy is deliberately over the commit gate's size cap,
so that an install's closing commit is refused and the test can check that every
place reporting on the install says so.

## Subfolder pages

- Wiki Operations: [[Habits and Tools]] (how the owner works, and the extras installed to match)

## Domains

"""

LINE = ("A line of an Index that grew and grew, as an Index does, saying nothing "
        "anyone would miss, which is rather the point of it. ")


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    target = Path(sys.argv[1])
    body = HEAD + (LINE * ((TARGET_CHARS - len(HEAD)) // len(LINE) + 1))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")
    print(f"wrote {target} at {len(body)} characters (~{len(body)//4} tokens)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
