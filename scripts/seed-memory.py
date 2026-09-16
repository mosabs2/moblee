#!/usr/bin/env python3
"""seed-memory.py — give a new vault's Claude a few starting memories.

Claude Code keeps per-project memory files under
~/.claude/projects/<encoded vault path>/memory/. The encoding replaces every
character that is not a letter or digit with a hyphen (a path such as
/Users/ann/Wiki/My Wiki becomes -Users-ann-Wiki-My-Wiki). This script writes
the generic memories bundled in memory-seed/ into that folder if they are not
already there, and adds their index lines to MEMORY.md. Nothing existing is
touched or removed. If the encoding ever differs from what Claude Code uses,
the files are simply never read, which is harmless.

    python3 scripts/seed-memory.py [--vault <path>] [--dry-run]
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SEEDS = HERE.parent / "memory-seed"


def find_vault(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    env = os.environ.get("MOBLEE_VAULT")
    if env:
        return Path(env).expanduser().resolve()
    cfg = Path.home() / ".config" / "moblee" / "vault-path"
    if cfg.exists() and cfg.read_text().strip():
        return Path(cfg.read_text().strip()).expanduser().resolve()
    here = Path.cwd().resolve()
    for cand in (here, *here.parents):
        if (cand / "wiki" / "Index.md").exists():
            return cand
    sys.exit("Could not find the vault. Pass --vault <path> or run from inside it.")


def index_line(seed: Path) -> str:
    text = seed.read_text()
    m = re.search(r"^description:\s*(.+)$", text, re.M)
    desc = m.group(1).strip() if m else ""
    title = seed.stem.replace("-", " ").capitalize()
    return f"- [{title}]({seed.name}) — {desc}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    vault = find_vault(a.vault)
    encoded = re.sub(r"[^A-Za-z0-9]", "-", str(vault))
    mem = Path.home() / ".claude" / "projects" / encoded / "memory"
    seeds = sorted(p for p in SEEDS.glob("*.md") if p.name != "MEMORY.md")
    home = str(Path.home())
    shown = "~" + str(mem)[len(home):] if str(mem).startswith(home) else str(mem)
    print(f"Starting memories for Claude (in {shown})")
    if a.dry_run:
        for s in seeds:
            print(f"  would seed {s.name}" if not (mem / s.name).exists() else f"  present {s.name}")
        return 0
    mem.mkdir(parents=True, exist_ok=True)
    index = mem / "MEMORY.md"
    existing = index.read_text() if index.exists() else "# MEMORY\n\n"
    added = 0
    for s in seeds:
        dst = mem / s.name
        if dst.exists():
            print(f"  present: {s.name}")
            continue
        dst.write_text(s.read_text())
        line = index_line(s)
        if s.name not in existing:
            existing = existing.rstrip("\n") + "\n" + line + "\n"
        added += 1
        print(f"  seeded: {s.name}")
    index.write_text(existing)
    print(f"  {added} memory file(s) added")
    return 0


if __name__ == "__main__":
    sys.exit(main())
