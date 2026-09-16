#!/usr/bin/env python3
"""add-identity.py — give an existing vault its wiki/Identity.md if it has none.

Used by the updater. Reads the pack's template, fills the owner's name and
today's date, and writes the file only when it does not already exist; an
existing Identity.md is never touched.

    python3 scripts/add-identity.py --vault <path> [--owner "Name"]
"""
from __future__ import annotations

import argparse
import datetime
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE.parent / "vault-template" / "wiki" / "Identity.md"


def owner_name(vault: Path, explicit: str | None) -> str:
    if explicit:
        return explicit
    try:
        r = subprocess.run(["git", "-C", str(vault), "config", "user.name"],
                           capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except OSError:
        pass
    claude_md = vault / "CLAUDE.md"
    if claude_md.exists():
        for line in claude_md.read_text(encoding="utf-8").splitlines():
            head, sep, rest = line.partition("knowledge base for ")
            if sep and " where Claude is the maintainer" in rest:
                return rest.split(" where Claude is the maintainer")[0].strip()
    return "[Your Name]"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault", required=True)
    ap.add_argument("--owner")
    a = ap.parse_args()
    vault = Path(a.vault).expanduser().resolve()
    dst = vault / "wiki" / "Identity.md"
    if dst.exists():
        print("wiki/Identity.md already present; left as it is")
        return 0
    if not TEMPLATE.exists():
        print("template Identity.md not found in the pack; nothing written")
        return 1
    name = owner_name(vault, a.owner)
    today = datetime.date.today().strftime("%-d %B %Y")
    text = TEMPLATE.read_text(encoding="utf-8")
    text = text.replace("[Your Name]", name).replace("[Install date]", today)
    dst.parent.mkdir(parents=True, exist_ok=True)
    with open(dst, "x", encoding="utf-8") as fh:  # "x": create only, never overwrite
        fh.write(text)
    print(f"added wiki/Identity.md for {name} (the owner's own asks are filled in conversation)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
