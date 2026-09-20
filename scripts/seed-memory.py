#!/usr/bin/env python3
"""seed-memory.py — give a new vault's assistant a few starting memories.

Claude Code keeps per-project memory files under
~/.claude/projects/<encoded vault path>/memory/. The encoding replaces every
character that is not a letter or digit with a hyphen (a path such as
/Users/ann/Wiki/My Wiki becomes -Users-ann-Wiki-My-Wiki). This script writes
the generic memories bundled in memory-seed/ into that folder if they are not
already there, and adds their index lines to MEMORY.md. Nothing existing is
touched or removed. If the encoding ever differs from what Claude Code uses,
the files are simply never read, which is harmless.

ChatGPT's agent has no hand-written memory folder, so for ChatGPT the same
memories go into a page of the wiki instead, wiki/Wiki Operations/Assistant
Memory.md, one section per memory. A page already there only gains the
sections it lacks; nothing in it is rewritten. The instruction file (CLAUDE.md
or AGENTS.md) gains a short paragraph pointing the assistant at the page, if
it does not mention the page already, and the Wiki Operations line of
wiki/Index.md gains a link to it, if there is such a line.

Which assistant: --assistant claude|chatgpt|both, else the one word kept in
~/.config/moblee/assistant, else claude. "both" does both.

    python3 scripts/seed-memory.py [--vault <path>] [--assistant <which>] [--dry-run]
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SEEDS = HERE.parent / "memory-seed"
ASSISTANTS = ("claude", "chatgpt", "both")

NOTES_REL = Path("wiki") / "Wiki Operations" / "Assistant Memory.md"
NOTES_OPENING = (
    "# Assistant Memory\n"
    "\n"
    "Standing notes the assistant keeps about how the owner of this wiki works. "
    "The assistant reads this page at the start of every session, follows what it says, "
    "and adds a section of its own whenever the owner states a lasting preference. "
    "Each section below is one note. See [[Index]] for the rest of the wiki.\n"
)
INSTRUCTION_PARAGRAPH = (
    "## Assistant memory\n"
    "\n"
    "**Standing notes live on a wiki page.** `wiki/Wiki Operations/Assistant Memory.md` holds "
    "what the assistant has learned about how the owner works. The assistant reads it at the "
    "start of each session, along with `wiki/_context.md`, and follows it. When the owner states "
    "a lasting preference, the assistant adds it to that page as a short section of its own, "
    "without being asked.\n"
)
INDEX_LINK = ", [[Assistant Memory]] (standing notes the assistant keeps on how the owner works)"
# words a file name cannot capitalise for itself
PROPER = {"english": "English"}


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


def read_assistant(explicit: str | None) -> str:
    """Which assistant: --assistant, else ~/.config/moblee/assistant, else claude."""
    if explicit is not None:
        value = explicit.strip().lower()
        if value not in ASSISTANTS:
            print(f"The assistant must be one of claude, chatgpt or both; \"{explicit}\" is not one of them.")
            sys.exit(2)
        return value
    try:
        value = (Path.home() / ".config" / "moblee" / "assistant").read_text().strip().lower()
    except OSError:
        return "claude"
    return value if value in ASSISTANTS else "claude"


def instruction_file(vault: Path) -> Path:
    """CLAUDE.md if it is a regular file, else AGENTS.md if it is, else CLAUDE.md."""
    for name in ("CLAUDE.md", "AGENTS.md"):
        p = vault / name
        if p.is_file() and not p.is_symlink():
            return p
    return vault / "CLAUDE.md"


def index_line(seed: Path) -> str:
    text = seed.read_text()
    m = re.search(r"^description:\s*(.+)$", text, re.M)
    desc = m.group(1).strip() if m else ""
    title = seed.stem.replace("-", " ").capitalize()
    return f"- [{title}]({seed.name}) — {desc}"


def seed_claude(vault: Path, seeds: list[Path], dry_run: bool) -> int:
    encoded = re.sub(r"[^A-Za-z0-9]", "-", str(vault))
    mem = Path.home() / ".claude" / "projects" / encoded / "memory"
    home = str(Path.home())
    shown = "~" + str(mem)[len(home):] if str(mem).startswith(home) else str(mem)
    print(f"Starting memories for Claude (in {shown})")
    if dry_run:
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


# ----- ChatGPT: the same memories as a page of the wiki -----------------------

def write_atomic(path: Path, text: str) -> None:
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o644
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.chmod(tmp, mode)  # keep the file's own permissions, not mkstemp's owner-only ones
    os.replace(tmp, path)


def append_text(path: Path, addition: str) -> None:
    """Add text at the end of a file, one blank line below what is there.
    The file is opened for appending, so nothing already in it is rewritten."""
    current = path.read_text(encoding="utf-8")
    if not current or current.endswith("\n\n"):
        gap = ""
    elif current.endswith("\n"):
        gap = "\n"
    else:
        gap = "\n\n"
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(gap + addition)


def seed_heading(seed: Path, text: str) -> str:
    """The section heading: a title: line in the seed if it has one, else its file name."""
    front = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if front:
        m = re.search(r"^title:\s*(.+)$", front.group(1), re.M)
        if m and m.group(1).strip():
            return m.group(1).strip().strip("\"'")
    stem = seed.stem
    if stem.startswith("feedback-"):
        stem = stem[len("feedback-"):]
    words = [PROPER.get(w, w) for w in stem.split("-") if w]
    if not words:
        return seed.stem
    words[0] = words[0][:1].upper() + words[0][1:]
    return " ".join(words)


def seed_body(text: str) -> str:
    """The seed without its frontmatter."""
    front = re.match(r"^---\n.*?\n---\n", text, re.S)
    return (text[front.end():] if front else text).strip("\n")


def has_heading(page_text: str, heading: str) -> bool:
    want = ("## " + heading).lower()
    return any(l.strip().lower() == want for l in page_text.splitlines())


def mention_in_instruction_file(vault: Path, dry_run: bool) -> None:
    target = instruction_file(vault)
    if not target.is_file():
        print(f"  no {target.name} in the vault; the page is not mentioned anywhere yet")
        return
    if "Assistant Memory" in target.read_text(encoding="utf-8"):
        print(f"  {target.name} already mentions the page")
        return
    if dry_run:
        print(f"  would add a paragraph about the page to the end of {target.name}")
        return
    append_text(target, INSTRUCTION_PARAGRAPH)
    print(f"  paragraph about the page added to the end of {target.name}")


def extend_index(vault: Path, dry_run: bool) -> None:
    """Link the page from the Index's Wiki Operations line, only if there is such a line."""
    index = vault / "wiki" / "Index.md"
    if not index.is_file():
        return
    text = index.read_text(encoding="utf-8")
    if "[[Assistant Memory" in text:
        return
    lines = text.splitlines(keepends=True)
    for i, l in enumerate(lines):
        if l.lstrip().startswith("- Wiki Operations"):
            if dry_run:
                print("  would add the page to the Wiki Operations line of wiki/Index.md")
                return
            bare = l.rstrip("\r\n")
            lines[i] = bare.rstrip() + INDEX_LINK + l[len(bare):]
            write_atomic(index, "".join(lines))
            print("  page added to the Wiki Operations line of wiki/Index.md")
            return


def seed_chatgpt(vault: Path, seeds: list[Path], dry_run: bool) -> int:
    print(f"Starting memories for ChatGPT (in {NOTES_REL})")
    if not (vault / "wiki").is_dir():
        print(f"  no wiki/ folder at {vault}; nothing written")
        return 1
    page = vault / NOTES_REL
    current = page.read_text(encoding="utf-8") if page.is_file() else None
    sections = []
    for s in seeds:
        text = s.read_text(encoding="utf-8")
        heading = seed_heading(s, text)
        if current is not None and has_heading(current, heading):
            print(f"  present: {heading}" if not dry_run else f"  present {heading}")
            continue
        if dry_run:
            print(f"  would add {heading}")
            continue
        sections.append(f"## {heading}\n\n{seed_body(text)}\n")
        print(f"  added: {heading}")
    if not dry_run:
        if current is None:
            page.parent.mkdir(parents=True, exist_ok=True)
            write_atomic(page, "\n".join([NOTES_OPENING] + sections))
        elif sections:
            append_text(page, "\n".join(sections))
        print(f"  {len(sections)} note(s) added")
    mention_in_instruction_file(vault, dry_run)
    if dry_run or page.is_file():
        extend_index(vault, dry_run)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault")
    ap.add_argument("--assistant", help="claude, chatgpt or both (default: the one kept in ~/.config/moblee/assistant, else claude)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    assistant = read_assistant(a.assistant)
    vault = find_vault(a.vault)
    seeds = sorted(p for p in SEEDS.glob("*.md") if p.name != "MEMORY.md")
    rc = 0
    if assistant in ("claude", "both"):
        rc = seed_claude(vault, seeds, a.dry_run)
    if assistant in ("chatgpt", "both"):
        rc = seed_chatgpt(vault, seeds, a.dry_run) or rc
    return rc


if __name__ == "__main__":
    sys.exit(main())
