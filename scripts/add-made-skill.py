#!/usr/bin/env python3
"""add-made-skill.py - add a skill that Claude drafted for the owner.

Claude writes a made-to-measure skill as a draft inside the wiki, under
made-for-you/skills/<name>/. A skill changes what Claude can do in every
session on this Mac, so the owner adds it, after seeing what it says it does.
The Moblee app uses this script for its "made for you" tiles; an owner without
the app runs it in Terminal:

    python3 scripts/add-made-skill.py <name>              # shows it, asks, adds it
    python3 scripts/add-made-skill.py <name> --describe   # shows it, changes nothing
    python3 scripts/add-made-skill.py <name> --describe --json

Checks made before anything is copied: the name is plain; the draft is a real
folder inside the wiki holding only ordinary files (no links to other places);
it has a SKILL.md; it is small; its name is not one of Moblee's own skills; and
a skill already installed under that name is only replaced if it was itself
added this way. Nothing is deleted: a copy being replaced is moved to
~/.config/moblee/backups/<stamp>/skills/.

Started from inside Claude Code it will describe but not add: adding is the
owner's act.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import shutil
import sys
from pathlib import Path

HOME = Path.home()
CONFIG = HOME / ".config" / "moblee"
SKILLS = HOME / ".claude" / "skills"
PACK = Path(__file__).resolve().parent.parent
MARKER = ".made-for-you"
MAX_FILES, MAX_BYTES = 60, 2_000_000


def find_vault(explicit: str | None) -> Path | None:
    for cand in (explicit, os.environ.get("MOBLEE_VAULT")):
        if cand and (Path(cand).expanduser() / "wiki").is_dir():
            return Path(cand).expanduser().resolve()
    cfg = CONFIG / "vault-path"
    if cfg.exists():
        p = Path(cfg.read_text().strip()).expanduser()
        if (p / "wiki").is_dir():
            return p.resolve()
    return None


def reserved_names() -> set:
    names = set()
    for folder in (PACK / "skills", PACK / "extras" / "skills"):
        if folder.is_dir():
            names |= {p.name for p in folder.iterdir() if p.is_dir()}
    return names


def description_of(skill_md: Path) -> str:
    text = skill_md.read_text(errors="replace")
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
    if m:
        d = re.search(r"^description:\s*(.+?)\s*$(?=\n\S|\Z)", m.group(1), re.S | re.M)
        if d:
            return " ".join(d.group(1).strip().strip("\"'").split())
    return ""


def inspect(vault: Path, name: str) -> dict:
    """Everything the owner should see, and every reason not to add it."""
    out = {"name": name, "description": "", "body": "", "files": [], "problems": [], "replaces": False}
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,59}", name):
        out["problems"].append("The name must be plain letters, numbers, hyphens or underscores.")
        return out
    root = vault / "made-for-you" / "skills"
    src = root / name
    if src.is_symlink() or not src.is_dir():
        out["problems"].append("There is no draft folder of that name in the wiki (or it is a link to somewhere else).")
        return out
    if root.resolve() not in src.resolve().parents:
        out["problems"].append("The draft is not inside the wiki's made-for-you folder.")
        return out
    total = 0
    for p in sorted(src.rglob("*")):
        rel = str(p.relative_to(src))
        if p.is_symlink():
            out["problems"].append(f"{rel} is a link to somewhere else; a skill must hold only ordinary files.")
        elif p.is_file():
            size = p.stat().st_size
            total += size
            out["files"].append({"path": rel, "bytes": size})
        elif not p.is_dir():
            out["problems"].append(f"{rel} is not an ordinary file.")
    if not (src / "SKILL.md").is_file():
        out["problems"].append("The draft has no SKILL.md.")
    else:
        out["description"] = description_of(src / "SKILL.md")
        # The description is one line the skill writes about itself. What Claude
        # will actually follow is the rest of the file, so the owner is shown
        # that too, in full, before anything is added.
        out["body"] = (src / "SKILL.md").read_text(errors="replace")[:20000]
        if not out["description"]:
            out["problems"].append("SKILL.md does not say what the skill does (no description).")
    if len(out["files"]) > MAX_FILES or total > MAX_BYTES:
        out["problems"].append("The draft is larger than a skill should be.")
    if name in reserved_names():
        out["problems"].append(f"'{name}' is the name of one of Moblee's own skills; the draft needs a different name.")
    dst = SKILLS / name
    if dst.exists() or dst.is_symlink():
        if dst.is_symlink() or not (dst / MARKER).is_file():
            out["problems"].append(f"A skill called '{name}' is already installed and was not added this way; it is left alone.")
        else:
            out["replaces"] = True
    return out


def add(vault: Path, name: str) -> Path:
    src = vault / "made-for-you" / "skills" / name
    dst = SKILLS / name
    SKILLS.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        keep = CONFIG / "backups" / stamp / "skills"
        keep.mkdir(parents=True, exist_ok=True)
        shutil.move(str(dst), str(keep / name))
    shutil.copytree(str(src), str(dst), symlinks=False)
    (dst / MARKER).write_text("Added by the owner with Moblee on " + datetime.date.today().isoformat() + ".\n")
    return dst


def main() -> int:
    ap = argparse.ArgumentParser(description="Add a skill that Claude drafted for the owner.")
    ap.add_argument("name")
    ap.add_argument("--vault")
    ap.add_argument("--describe", action="store_true", help="show what would be added and change nothing")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--yes", action="store_true", help="do not ask (the Moblee app uses this after the owner has seen the skill and pressed Add)")
    args = ap.parse_args()

    vault = find_vault(args.vault)
    if vault is None:
        print("No wiki was found.")
        return 1
    info = inspect(vault, args.name)

    if args.json:
        print(json.dumps(info, indent=2))
    else:
        print(f"Skill: {info['name']}")
        print(f"What it says it does: {info['description'] or '(nothing)'}")
        for f in info["files"]:
            print(f"  {f['path']}  ({f['bytes']} bytes)")
        if info["body"]:
            print("\nWhat Claude would be told to do (the whole of SKILL.md):\n")
            print(info["body"])
            print("")
        if info["replaces"]:
            print("It replaces an earlier version you added before; that copy is kept in the backups folder.")
        for p in info["problems"]:
            print(f"NOT ADDED: {p}")
    if args.describe:
        return 0 if not info["problems"] else 1
    if info["problems"]:
        return 1
    if os.environ.get("CLAUDECODE"):
        print("Adding a skill is the owner's act: run this in the Moblee app or a Terminal window of your own.")
        return 1
    if not args.yes:
        try:
            answer = input("Add this skill, so Claude can use it in every session on this Mac? [y/N]: ")
        except EOFError:
            answer = ""
        if not answer.strip().lower().startswith("y"):
            print("Nothing was added.")
            return 0
    dst = add(vault, args.name)
    print("Added. Claude sees it from the next session. It is at " + str(dst).replace(str(HOME), "~"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
