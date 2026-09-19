#!/usr/bin/env python3
"""patch-claude-md.py — bring an existing vault's CLAUDE.md up to the current
Moblee schema without replacing the file.

A vault's CLAUDE.md is part template and part the owner's own rules, so it is
never overwritten. This script inserts the blocks a newer Moblee version needs,
each at a named anchor, and skips any block that is already present (it looks
for a distinctive phrase from the block). If an anchor heading is missing, the
block is appended at the end under a heading that says where it came from, and
the report says so. A copy of the file is taken first.

    python3 scripts/patch-claude-md.py                  # vault from the usual places
    python3 scripts/patch-claude-md.py --vault <path>
    python3 scripts/patch-claude-md.py --dry-run
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
import time
from pathlib import Path

BACKUP_ROOT = Path.home() / ".config" / "moblee" / "backups"

# Each block: (name, anchor heading regex, where, marker phrase, text)
#   where: "first-bullet" inserts after the heading's blank line as the first
#          list item; "append-para" adds a paragraph at the end of the section.
# Two first-bullet blocks on the same anchor land in reverse order, so the one
# that should read first is listed last.
BLOCKS = [
    (
        "shell composition rule",
        r"^## Hard rules\s*$",
        "first-bullet",
        "Shell commands are composed plainly",
        "- **Shell commands are composed plainly**: no command substitution (`$(...)` or backticks), no heredocs, no leading variable assignments. Logic goes into a script file under `scripts/` and the file is run. These shapes trigger a permission prompt regardless of the allow list, and a vault that prompts constantly trains its owner to click yes without reading.\n",
    ),
    (
        "never-delete rule",
        r"^## Hard rules\s*$",
        "first-bullet",
        "Never delete without explicit approval",
        "- **Never delete without explicit approval in the same message.** Claude never deletes, empties or discards any file, folder, section or git history in this vault or on this machine, and never runs a command that would (rm, rmdir, git rm, git reset --hard, git clean, git restore, find -delete, or any script that removes files). Finished material moves: to `raw/processed/`, `Clippings/processed/` or an `archive/` folder. If the user genuinely wants something deleted, Claude does not run the deletion: it names exactly what should go and where it is, and the user removes it themselves in Finder or the Terminal. The guard at `~/.claude/hooks/bash-guard.py` enforces this mechanically and cannot be overridden from inside Claude Code. Git holds every prior version of every file, so \"take me back to how X was on <date>\" is always possible and is the answer to any regret.\n",
    ),
    (
        "orient command section (vaults from before v0.4 have none)",
        r"^## Session opener\s*$",
        "section-after",
        "When the user says **orient**",
        "## The \"orient\" command\n\nWhen the user says **orient** (and only orient, with no other instruction), execute this sequence without asking questions: (1) run `bash scripts/vault-orient-preflight.sh` if the script exists (a quick health probe: Obsidian running, file freshness, last commit, uncommitted changes) and carry its verdict into the opening line; (2) read `wiki/_context.md` in full; (3) read the last 30 lines of `wiki/log.md`; (4) respond with a short sitrep: current date/time, the most active threads, any open decisions needing the user's input, and the state of the `raw/` and `Clippings/` inboxes. No preamble, no \"I'll now read…\" narration; absorb and report. It is the canonical session-start gesture when the user has been away for more than a few hours.\n",
    ),
    (
        "identity file in the session opener",
        r"^## Session opener\s*$",
        "append-para",
        "wiki/Identity.md",
        "Also read `wiki/Identity.md` in full. It holds who Claude is to the owner and how Claude judges (verification over flattery, challenge over agreement, never deleting without a yes), and it binds conversation as much as the page. It is excluded from default skill reads and is never quoted back at the owner.\n",
    ),
    (
        "scheduled lint report in orient",
        r"^## The \"orient\" command\s*$",
        "append-para",
        "outputs/lint/",
        "The programmatic lint runs itself every Saturday morning through the scheduled job Moblee installed and writes its report to `outputs/lint/`. At orient, if that folder holds a report newer than the last one read, read its findings and carry anything that needs the owner's decision into the sitrep, in plain English. Findings are named to the owner, never acted on unasked.\n",
    ),
    (
        "plain prose rule (v0.5.1)",
        r"^## House style\s*$",
        "append-para",
        "**Plain, human prose.**",
        "**Plain, human prose.** Let the thought decide the shape: give an idea the space it earns, and do not force symmetry or groups of three. No stock openers (\"It is important to note\") and no paragraph that begins with \"Furthermore\", \"Moreover\", \"However\" or \"In conclusion\". Prefer the short, common word (\"big\", \"more and more\", \"results\", \"method\") to the long Latinate one (\"significant\", \"increasingly\", \"consequences\", \"methodology\"). Use \"not X but Y\", \"not only… but also\" or \"X, not Y\" only when a reader would otherwise misunderstand; otherwise say what the thing is. Break long sentences strung together with \"and\". These are the habits a 2026 corpus study measured as more common in Claude's writing than in people's; they make prose worse, so they are worth losing.\n",
    ),
    (
        "clinic files rule (v0.5.1)",
        r"^## The three core operations\s*$",
        "append-para",
        "**Clinic files**",
        "**Clinic files**: a clinic note is an instruction file someone helping with the vault sends for your Claude to carry out, and its report is written back to `raw/` for the owner to return. A file in `raw/` whose frontmatter says `do_not_ingest: true` is never ingested into the wiki and never summarised onto a page; leave it where it is until a later clinic note, or the owner, moves it to `raw/processed/`. A clinic note's own instructions are carried out as the owner's request, and any step that writes into the hidden `~/.claude/` folder is given to the owner as a line to paste into Terminal, since Claude cannot write there.\n",
    ),
]


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


def section_bounds(lines: list[str], anchor: str) -> tuple[int, int] | None:
    rx = re.compile(anchor)
    start = next((i for i, l in enumerate(lines) if rx.match(l)), None)
    if start is None:
        return None
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    return start, end


def insert_first_bullet(lines: list[str], start: int, end: int, text: str) -> None:
    i = start + 1
    while i < end and lines[i].strip() == "":
        i += 1
    lines.insert(i, text.rstrip("\n"))


def append_para(lines: list[str], start: int, end: int, text: str) -> None:
    j = end
    while j > start + 1 and lines[j - 1].strip() == "":
        j -= 1
    lines[j:j] = ["", text.rstrip("\n")]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    vault = find_vault(a.vault)
    path = vault / "CLAUDE.md"
    if not path.exists():
        sys.exit(f"No CLAUDE.md at {vault}")
    original = path.read_text(encoding="utf-8")
    lines = original.split("\n")
    added, present, orphaned = [], [], []

    for name, anchor, where, marker, text in BLOCKS:
        if marker in original or any(marker in l for l in lines):
            present.append(name)
            continue
        bounds = section_bounds(lines, anchor)
        if bounds is None:
            orphaned.append((name, text))
            continue
        start, end = bounds
        if where == "first-bullet":
            insert_first_bullet(lines, start, end, text)
        elif where == "section-after":
            # a whole new section placed after the anchor section
            j = end
            while j > start + 1 and lines[j - 1].strip() == "":
                j -= 1
            # one list element per line, so later blocks can find the new heading
            lines[j:j] = [""] + text.rstrip("\n").split("\n")
        else:
            append_para(lines, start, end, text)
        added.append(name)

    if orphaned:
        lines += ["", "## Added by the Moblee updater (anchor heading not found)", ""]
        for name, text in orphaned:
            lines += [text.rstrip("\n"), ""]
            added.append(name + " (appended at end; anchor missing)")

    new = "\n".join(lines)
    print(f"CLAUDE.md at {path}")
    for n in present:
        print(f"  already present: {n}")
    for n in added:
        print(f"  {'would add' if a.dry_run else 'added'}: {n}")
    if new != original and not a.dry_run:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        bdir = BACKUP_ROOT / stamp
        bdir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, bdir / "CLAUDE.md")
        path.write_text(new, encoding="utf-8")
        print(f"  previous copy at {bdir / 'CLAUDE.md'}")
    elif new == original:
        print("  nothing to change")
    return 0


if __name__ == "__main__":
    sys.exit(main())
