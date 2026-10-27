#!/usr/bin/env python3
"""compact-rotate.py - the one compaction move that needs no judgement, done by a script.

    python3 scripts/compact-rotate.py --vault <wiki> [--dry-run]

wiki/_context.md opens with a "Last refreshed:" paragraph that the brain
skill's close-day pattern extends at every refresh: the newest note in full,
then "Previous refresh: ..." notes, oldest last. Left alone it grows without
limit, and the whole of it is read at the start of every conversation. The
compact skill's rule for it is mechanical and loses nothing: keep the latest
three notes inline, the newest at full length and the two before it cut to
their bold headline, and move every older note in full to the Context Archive
page under "Refresh-note history". This script does exactly that, and nothing
else: no thread, decision or watch-list item is touched, no line is dropped
from anywhere, and the archive page is created if the wiki has none.

Run twice, the second run changes nothing. --dry-run says what would move.
Prints one line: what moved, or that nothing needed to. Exit 0 either way;
exit 1 when the wiki or the file cannot be read.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ARCHIVE_REL = Path("wiki") / "Wiki Operations" / "Context Archive.md"
HEADING = "## Refresh-note history"
KEEP = 3
TAIL_RE = re.compile(r"\s*Earlier refresh notes live in full at \[\[Context Archive#Refresh-note history\]\][^\n]*$")
SPLIT_RE = re.compile(r"\s+Previous refresh:\s+")
BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
DATE_RE = re.compile(r"^(.*?)(?=\s*\()", re.S)


def headline(note: str) -> str:
    """'<date part> (**headline**; full text at [[Context Archive#Refresh-note history]].)'"""
    m = BOLD_RE.search(note)
    date_part = note.split("(", 1)[0].strip().rstrip(",;")
    head = m.group(1).strip() if m else note.strip()[:160]
    return f"{date_part} (**{head}**; full text at [[Context Archive#Refresh-note history]].)"


def is_compressed(note: str) -> bool:
    return "full text at [[Context Archive#Refresh-note history]]" in note


def archive_page_text(vault_name: str) -> str:
    return (f"# Context Archive\n\nCold storage for `_context.md` in {vault_name}: the full text of every refresh "
            f"note rotated out of the working-state file, and of threads, decisions and watch-list items once "
            f"closed. Nothing here is deleted; the live file stays light because this page holds the history.\n\n"
            f"{HEADING}\n\n## Closed threads and decisions\n\n")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vault", required=True)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    vault = Path(a.vault).expanduser().resolve()
    ctx = vault / "wiki" / "_context.md"
    if not ctx.is_file():
        print(f"no wiki/_context.md at {vault}")
        return 1
    text = ctx.read_text(encoding="utf-8")
    m = re.search(r"^Last refreshed:\s*(.*?)(?=\n\n|\n#|\Z)", text, re.S | re.M)
    if not m:
        print("nothing to rotate: no 'Last refreshed:' paragraph")
        return 0
    para = m.group(1)
    tail = ""
    tm = TAIL_RE.search(para)
    if tm:
        tail = tm.group(0)
        para = para[:tm.start()]
    notes = [n.strip() for n in SPLIT_RE.split(para.strip()) if n.strip()]
    if len(notes) <= KEEP and all(is_compressed(n) for n in notes[1:KEEP]):
        print(f"nothing to rotate: {len(notes)} refresh note(s) inline, within the rule")
        return 0
    keep = [notes[0]] + [n if is_compressed(n) else headline(n) for n in notes[1:KEEP]]
    compressed = [n for n in notes[1:KEEP] if not is_compressed(n)]
    # Every note's full text reaches the archive once: the ones cut to a
    # headline now, and the ones leaving the live file now that were never
    # cut (one already cut had its full text archived when it was).
    moving = compressed + [n for n in notes[KEEP:] if not is_compressed(n)]
    leaving = notes[KEEP:]
    if not leaving and not compressed:
        print(f"nothing to rotate: {len(notes)} refresh note(s) inline, within the rule")
        return 0
    new_para = "Last refreshed: " + keep[0]
    for n in keep[1:]:
        new_para += " Previous refresh: " + n
    if leaving or tail or compressed:
        new_para += " Earlier refresh notes live in full at [[Context Archive#Refresh-note history]], per the retention rule."
    new_text = text[:m.start()] + new_para + text[m.end():]
    archive = vault / ARCHIVE_REL
    what = (f"would move {len(leaving)} refresh note(s) out of the live file, cut {len(compressed)} to a headline, "
            f"and archive {len(moving)} in full" if a.dry_run else
            f"moved {len(leaving)} refresh note(s) out of the live file, cut {len(compressed)} to a headline, "
            f"and archived {len(moving)} in full")
    if a.dry_run:
        print(what)
        return 0
    if moving:
        if archive.exists():
            arch = archive.read_text(encoding="utf-8")
            if HEADING not in arch:
                arch = arch.rstrip("\n") + f"\n\n{HEADING}\n\n"
        else:
            archive.parent.mkdir(parents=True, exist_ok=True)
            arch = archive_page_text(vault.name)
        entries = "".join(f"**Refresh note, rotated by the weekly tidy:** {n}\n\n" for n in moving)
        head_at = arch.index(HEADING) + len(HEADING)
        # under the heading, after any blank line, before the next heading
        rest = arch[head_at:]
        nxt = re.search(r"\n## ", rest)
        insert_at = head_at + (nxt.start() + 1 if nxt else len(rest))
        arch = arch[:insert_at].rstrip("\n") + "\n\n" + entries + arch[insert_at:].lstrip("\n")
        archive.write_text(arch, encoding="utf-8")
    ctx.write_text(new_text, encoding="utf-8")
    print(what)
    return 0


if __name__ == "__main__":
    sys.exit(main())
