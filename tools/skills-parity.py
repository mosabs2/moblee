#!/usr/bin/env python3
"""Skills parity: the pack's copies of the shared skills against the live ones.

The six skills the pack shares with its maker's own vault (brain, compact,
galaxy, wiki-capture, wiki-interview, wiki-to-pdf) move on that Mac between
releases, and a release that ships the pack's older copy quietly loses what
was learned. This lists, file by file, what differs between a live skills
folder and the pack's, so the maintainer decides before the release commit.
It judges nothing: a live skill carries its owner's paths and the pack's copy
is generalised, so a difference is a question, not a fault.

    python3 tools/skills-parity.py                     # live folder: ~/.claude/skills
    python3 tools/skills-parity.py --live <folder>     # another live folder
    python3 tools/skills-parity.py --skills brain,compact

Exit status 0 when every shared skill is identical, 1 when any differs, 2 when
the live folder cannot be read. Stdlib only; Python 3.9.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACK = HERE.parent
SHARED = ("brain", "compact", "galaxy", "wiki-capture", "wiki-interview", "wiki-to-pdf")
SKIP_DIRS = {"__pycache__", ".git", "node_modules"}
SKIP_FILES = {".DS_Store"}


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def files_of(root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not root.is_dir():
        return out
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            if name in SKIP_FILES:
                continue
            p = Path(dirpath) / name
            if p.is_symlink() and not p.exists():
                continue
            rel = str(p.relative_to(root))
            try:
                out[rel] = digest(p)
            except OSError:
                out[rel] = "unreadable"
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--live", default=os.path.expanduser("~/.claude/skills"),
                    help="the live skills folder (default ~/.claude/skills)")
    ap.add_argument("--skills", default=",".join(SHARED),
                    help="comma-separated skill names to compare")
    ap.add_argument("--quiet", action="store_true", help="print only the summary line")
    args = ap.parse_args()
    live_root = Path(os.path.expanduser(args.live))
    if not live_root.is_dir():
        print(f"skills-parity: live folder not found: {live_root}")
        return 2
    names = [n.strip() for n in args.skills.split(",") if n.strip()]
    drift = 0
    for name in names:
        live = files_of(live_root / name)
        pack = files_of(PACK / "skills" / name)
        if not live and not pack:
            print(f"{name}: in neither place")
            drift += 1
            continue
        if not live:
            print(f"{name}: only in the pack ({len(pack)} files)")
            drift += 1
            continue
        if not pack:
            print(f"{name}: only live ({len(live)} files)")
            drift += 1
            continue
        same = [f for f in pack if f in live and live[f] == pack[f]]
        differs = [f for f in pack if f in live and live[f] != pack[f]]
        only_pack = [f for f in pack if f not in live]
        only_live = [f for f in live if f not in pack]
        if not differs and not only_pack and not only_live:
            print(f"{name}: identical ({len(same)} files)")
            continue
        drift += 1
        print(f"{name}: differs ({len(same)} same, {len(differs)} differ, "
              f"{len(only_live)} only live, {len(only_pack)} only in the pack)")
        if not args.quiet:
            for f in differs:
                print(f"    differs     {f}")
            for f in only_live:
                print(f"    only live   {f}")
            for f in only_pack:
                print(f"    only pack   {f}")
    print()
    if drift:
        print(f"skills-parity: {drift} of {len(names)} shared skills differ between "
              f"{live_root} and the pack; read each before the release commit")
        return 1
    print(f"skills-parity: all {len(names)} shared skills identical")
    return 0


if __name__ == "__main__":
    sys.exit(main())
