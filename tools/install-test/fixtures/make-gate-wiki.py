#!/usr/bin/env python3
"""Lay down the practice wiki, and the pages, the commit gate's cases need.

    make-gate-wiki.py <wiki folder> <package folder> [what ...]

With no `what`, it builds a small wiki with the gate wired in the way the
installer wires one: scripts/vault-gate.py and the tracked hook beside it, a
rules file, an Index and one page for the Index to link to. The rig then runs
`git init` and the first commit itself.

Each `what` after that writes one set of pages for a case to commit:

    awkward-names       two pages whose names git does not hand back plainly:
                        one written in Arabic, one with a space and a quote
                        mark in it. Both link to a page that does not exist,
                        so the gate has to have read the file to object.
    link-target         the page those two link to, so the same commit passes.
    csv-unquoted        a CSV row holding a comma nobody quoted.
    csv-quoted          the same row with the value quoted properly.
    frontmatter-broken  a page whose properties hold an unquoted colon, which
                        ends the block early and loses every property.
    frontmatter-fixed   the same page with that value in quotes.

The pages are written here rather than from the shell so that the content —
the Arabic name especially — is written once, in one place, and reads the same
on every Mac.
"""
import pathlib
import shutil
import stat
import sys

ARABIC_PAGE = "مرحبا بالعالم.md"
QUOTED_PAGE = 'A page with "quotes" in it.md'

SETS = {
    "awkward-names": {
        f"wiki/{ARABIC_PAGE}": "# مرحبا\n\nSee [[Nowhere At All]].\n",
        f"wiki/{QUOTED_PAGE}": "# Quoted\n\nSee [[Nowhere At All]].\n",
    },
    "link-target": {
        "wiki/Nowhere At All.md": "# Nowhere At All\n\nIt exists now.\n",
    },
    "csv-unquoted": {
        "wiki/data/notes.csv":
            "title,date,note\n"
            "Reading, Volume 2,2026-10-01,a comma nobody quoted\n",
    },
    "csv-quoted": {
        "wiki/data/notes.csv":
            "title,date,note\n"
            '"Reading, Volume 2",2026-10-01,a comma that was quoted\n',
    },
    "frontmatter-broken": {
        "wiki/A page.md":
            "---\ntitle: A page\nsummary: one thing: and another\n---\n\n"
            "# A page\n\nSome words.\n",
    },
    "frontmatter-fixed": {
        "wiki/A page.md":
            '---\ntitle: A page\nsummary: "one thing: and another"\n---\n\n'
            "# A page\n\nSome words.\n",
    },
}

STARTING_WIKI = {
    "wiki/Index.md": "# Index\n\n- [[Welcome]]\n",
    "wiki/Welcome.md": "# Welcome\n\nA practice wiki.\n",
    "CLAUDE.md": "# House rules\n\nNothing unusual.\n",
}


def write(root: pathlib.Path, rel: str, text: str) -> None:
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    print(f"wrote {rel}")


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    root = pathlib.Path(argv[0])
    package = pathlib.Path(argv[1])
    wanted = argv[2:]

    if not wanted:
        for rel, text in STARTING_WIKI.items():
            write(root, rel, text)
        (root / "scripts" / "hooks").mkdir(parents=True, exist_ok=True)
        shutil.copy2(package / "scripts" / "vault-gate.py", root / "scripts" / "vault-gate.py")
        hook = root / "scripts" / "hooks" / "pre-commit"
        shutil.copy2(package / "scripts" / "hooks" / "pre-commit", hook)
        hook.chmod(hook.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        print("wired the commit gate in as the pre-commit hook")
        return 0

    for what in wanted:
        if what not in SETS:
            print(f"unknown set of pages: {what}", file=sys.stderr)
            return 2
        for rel, text in SETS[what].items():
            write(root, rel, text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
