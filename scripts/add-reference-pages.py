#!/usr/bin/env python3
"""add-reference-pages.py: give an existing vault the four reference pages the
v0.9.4 rules file links to.

In v0.9.4 CLAUDE.md was cut from about 9,000 tokens to about 3,700, because the
assistant reads it at the start of every session. The detail it used to carry
now lives on four pages the assistant reads only when the work calls for them:

    wiki/Wiki Operations/Wiki Conventions.md
    wiki/Wiki Operations/Git and Commits.md
    wiki/Wiki Operations/Tools and Connections.md
    wiki/Wiki Operations/Readwise.md

The updater runs this BEFORE scripts/patch-claude-md.py, and stops that script
running if this one fails. That order is the whole point: the patcher removes
those sections from CLAUDE.md, and removing them while the pages are missing
would lose the content.

Written the same way as add-habits-page.py:

  1. Each page is copied from the template ONLY if wiki/Wiki Operations/ has no
     page of that name already. A page the owner has edited is never touched
     and never overwritten.
  2. One line in wiki/Index.md links them, so the weekly check does not call
     them orphans. If the Index already keeps a Wiki Operations line, that line
     is extended rather than a second one added.
  3. (v0.9.4) A page of the owner's own carrying one of these four names,
     anywhere else under wiki/, stops that name dead. Readwise is the likely
     one, because the pack assumes a Readwise feed and an owner may well keep
     their own notes about it. Two pages of one name make [[Readwise]] point at
     whichever of them Obsidian picks, so Moblee's page is not added, no link
     to it is written, and the run says so and exits non-zero. The updater then
     leaves the rules file exactly as it is: a rules file that sends the
     assistant to the wrong page is worse than a long one.

    python3 scripts/add-reference-pages.py --vault <path>
    python3 scripts/add-reference-pages.py --vault <path> --check   # say, change nothing
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
PAGES = ("Wiki Conventions", "Git and Commits", "Tools and Connections", "Readwise")
PAGE_DIR = Path("wiki") / "Wiki Operations"


def index_line(names) -> str:
    return ("- Wiki Operations: the reference pages the rules file links to on demand: "
            + ", ".join(f"[[{p}]]" for p in names) + "\n")


def write_atomic(path: Path, text: str) -> None:
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o644
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.chmod(tmp, mode)  # keep the file's own permissions, not mkstemp's owner-only ones
    os.replace(tmp, path)


def collisions(vault: Path) -> dict[str, list[str]]:
    """name -> the owner's own pages of that name, outside wiki/Wiki Operations/.

    Matching by filename alone, the way the earlier version did, cannot tell
    Moblee's page from a page of the owner's that happens to share its name: it
    saw the name, took the page as present, and linked it. So the two are told
    apart by where they sit. Only wiki/Wiki Operations/<name>.md is Moblee's.
    """
    found: dict[str, list[str]] = {}
    wanted = {f"{name}.md": name for name in PAGES}
    mine = vault / PAGE_DIR
    for p in (vault / "wiki").rglob("*.md"):
        name = wanted.get(p.name)
        if name is None or p.parent == mine:
            continue
        found.setdefault(name, []).append(str(p.relative_to(vault)))
    for paths in found.values():
        paths.sort()
    return found


def add_pages(vault: Path, check: bool, clashing: dict[str, list[str]]) -> tuple[list[str], list[str]]:
    """(added, could not add). A page already in place is left exactly as it is."""
    added, failed = [], []
    for name in PAGES:
        src = PACKAGE_ROOT / "vault-template" / PAGE_DIR / f"{name}.md"
        if name in clashing:
            continue        # named in the report instead; see main()
        if (vault / PAGE_DIR / f"{name}.md").is_file():
            continue
        if not src.is_file():
            failed.append(name)
            continue
        if check:
            added.append(name)
            continue
        try:
            dest = vault / PAGE_DIR / f"{name}.md"
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
        except OSError:
            failed.append(name)
            continue
        added.append(name)
    return added, failed


def add_index_line(vault: Path, check: bool, linkable: list[str]) -> str:
    """Link the pages from wiki/Index.md, in one line, once.

    Only pages that are really in the wiki are linked. A link to a page that is
    not there is a dangling wikilink, and the pack's own commit gate refuses a
    commit that adds one, which would turn a page that could not be copied into
    an update that will not save."""
    index = vault / "wiki" / "Index.md"
    if not index.exists():
        return ""
    text = index.read_text(encoding="utf-8")
    missing = [p for p in linkable if f"[[{p}]]" not in text and f"[[{p}|" not in text]
    if not missing:
        return ""
    lines = text.splitlines(keepends=True)
    if lines and not lines[-1].endswith("\n"):
        lines[-1] += "\n"
    # An Index that already keeps a Wiki Operations line gains no second one:
    # the same care add-habits-page.py takes, for the same reason.
    for i, l in enumerate(lines):
        if l.lstrip().startswith("- Wiki Operations"):
            bare = l.rstrip("\r\n")
            ending = l[len(bare):] or "\n"
            lines[i] = (bare.rstrip().rstrip(",") + ", "
                        + ", ".join(f"[[{p}]]" for p in missing) + ending)
            if not check:
                write_atomic(index, "".join(lines))
            # Named one by one, and counted from what was really linked. The
            # earlier wording said "the four pages" whatever it had done, so a
            # run that linked three told the owner it had linked four.
            return ("added to the Wiki Operations line of wiki/Index.md: "
                    + ", ".join(missing))
    # otherwise at the end of the Subfolder pages section, or of the file
    at = None
    for i, l in enumerate(lines):
        if l.strip().lower().startswith("## subfolder"):
            at = len(lines)
            for j in range(i + 1, len(lines)):
                if lines[j].startswith("## "):
                    at = j
                    break
            break
    new_line = index_line(missing)
    if at is None:
        lines += ["\n", new_line]
    else:
        while at > 0 and lines[at - 1].strip() == "":
            at -= 1
        lines.insert(at, new_line if lines[at - 1].startswith("- ") else "\n" + new_line)
    if not check:
        write_atomic(index, "".join(lines))
    return "a line was added to wiki/Index.md for: " + ", ".join(missing)


def main() -> int:
    ap = argparse.ArgumentParser(description="Add the four reference pages to an existing Moblee vault.")
    ap.add_argument("--vault", required=True)
    ap.add_argument("--check", action="store_true", help="say what would happen; change nothing")
    args = ap.parse_args()
    vault = Path(os.path.expanduser(args.vault))
    if not (vault / "wiki").is_dir():
        print(f"No wiki/ folder at {vault}; nothing added.")
        return 1
    clashing = collisions(vault)
    added, failed = add_pages(vault, args.check, clashing)
    here = {p for p in PAGES if (vault / PAGE_DIR / f"{p}.md").is_file()}
    # A page is linked only once it is really at wiki/Wiki Operations/<name>.md.
    # A name the owner has used elsewhere is never linked, so [[Readwise]] can
    # never be made to point at a page of theirs that has nothing to do with it.
    linkable = [p for p in PAGES
                if p not in clashing and (p in here or (args.check and p in added))]
    note = add_index_line(vault, args.check, linkable)
    if added:
        print(("would add" if args.check else "added") + " the reference pages: " + ", ".join(added))
    if note:
        print(note)
    if not added and not note and not clashing:
        print("the four reference pages are already in this wiki; left as they are")
    for name in PAGES:
        if name not in clashing:
            continue
        where = " and ".join(clashing[name])
        print(f"not added: this wiki already has a page called {name}, at {where}. "
              f"Two pages of one name make [[{name}]] point at whichever one Obsidian "
              f"picks, so Moblee's {name} page was left out and nothing links to it. "
              f"Rename one of the two, then run the updater again.")
    if failed:
        print("could not add: " + ", ".join(failed))
        return 1
    if clashing:
        return 1
    # Every one of the four has to be there before CLAUDE.md may lose the
    # sections whose content they carry, so this is checked and not assumed.
    absent = [p for p in PAGES if p not in here]
    if absent and not args.check:
        print("still missing: " + ", ".join(absent))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
