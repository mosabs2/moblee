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

A note the owner takes out stays out. The updater runs this script on every
update, so without a record a starting note the owner had deleted came back the
next time. What this script has given, and what it has since found gone, is
written down in the wiki itself, at .moblee/seed-state.json. A note is recorded
as removed only when this script can see both that it gave that note and that
the note is now gone. Nothing here ever deletes anything.

To have a removed note back, run the script again with --restore:

    python3 scripts/seed-memory.py --restore all

Which assistant: --assistant claude|chatgpt|both, else the one word kept in
~/.config/moblee/assistant, else claude. "both" does both.

    python3 scripts/seed-memory.py [--vault <path>] [--assistant <which>] [--dry-run]
    python3 scripts/seed-memory.py --restore all | --restore <note file name>
"""
from __future__ import annotations

import argparse
import datetime
import json
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

TODAY = datetime.date.today().isoformat()
RESTORE_COMMAND = "python3 scripts/seed-memory.py --restore all"
# names of the notes left out of this run because the owner removed them
LEFT_OUT: list[str] = []


# (v0.9.2) The path the vault was NAMED by, before resolving. Claude Code
# encodes a project folder by the path it was opened with, and this script
# resolves the path it is given, so for a vault reached through a symlink — or
# one under an iCloud-synced Desktop, where the real path runs through
# Mobile Documents — the two differ and the memories land in a folder Claude
# never reads, reported as installed either way.
VAULT_AS_NAMED: Path | None = None


def find_vault(explicit: str | None) -> Path:
    global VAULT_AS_NAMED
    raw: Path | None = None
    if explicit:
        raw = Path(explicit).expanduser()
    else:
        env = os.environ.get("MOBLEE_VAULT")
        cfg = Path.home() / ".config" / "moblee" / "vault-path"
        if env:
            raw = Path(env).expanduser()
        elif cfg.exists() and cfg.read_text().strip():
            raw = Path(cfg.read_text().strip()).expanduser()
    if raw is not None:
        VAULT_AS_NAMED = raw
        return raw.resolve()
    here = Path.cwd().resolve()
    for cand in (here, *here.parents):
        if (cand / "wiki" / "Index.md").exists():
            VAULT_AS_NAMED = cand
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
    # Read as the installer and the updater read it: the first line, spaces
    # dropped, and the word exactly as they write it. Anything else is no choice.
    try:
        text = (Path.home() / ".config" / "moblee" / "assistant").read_text(errors="replace")
    except OSError:
        return "claude"
    value = "".join(text.split("\n", 1)[0].split())
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


def memory_dirs(vault: Path) -> list[Path]:
    """Every folder Claude might read this vault's memories from.

    Claude Code names a project folder after the path it was OPENED with. A
    vault can be opened by more than one path — through a symlink, or under an
    iCloud-synced Desktop where the real path runs through Mobile Documents —
    and the memories are a handful of small files, so they are written to each
    rather than guessed at. Most likely first, and duplicates dropped.
    """
    seen: list[Path] = []
    for p in (vault, VAULT_AS_NAMED):
        if p is None:
            continue
        encoded = re.sub(r"[^A-Za-z0-9]", "-", str(p))
        mem = Path.home() / ".claude" / "projects" / encoded / "memory"
        if mem not in seen:
            seen.append(mem)
    return seen


def write_atomic(path: Path, text: str) -> None:
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o644
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.chmod(tmp, mode)  # keep the file's own permissions, not mkstemp's owner-only ones
    os.replace(tmp, path)


def write_atomic_bytes(path: Path, data: bytes) -> None:
    """The same, for bytes that must go back exactly as they are."""
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o644
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-")
    with os.fdopen(fd, "wb") as fh:
        fh.write(data)
    os.chmod(tmp, mode)
    os.replace(tmp, path)


# ----- the record: what was given, and what the owner has since taken out -----
#
# (v0.9.4) Every update runs this script again, so before this a starting note
# the owner had deleted came straight back, with its index line. The record is
# kept in the wiki, at .moblee/seed-state.json, beside the requests file the
# Moblee app reads: it belongs to the wiki rather than to the Mac, git keeps its
# history with the rest of the wiki, and it travels with the wiki to another
# Mac. A removal is written down only when this script can see both that it
# gave the note and that the note is now gone.

STATE_REL = Path(".moblee") / "seed-state.json"
STATE_ABOUT = (
    "What Moblee's starting notes have done in this wiki. Under each place, one entry "
    "per note: \"written\" is the day Moblee put the note there, \"removed\" is the day "
    "Moblee found a note it had written gone, taken out by the owner. A note recorded as "
    "removed is never written again."
)
STATE_BRING_BACK = (
    "To have every removed note back, run this from the Moblee folder: "
    + RESTORE_COMMAND
    + " . For one note only, use its file name in place of the word all."
)


def state_path(vault: Path) -> Path:
    return vault / STATE_REL


def empty_state() -> dict:
    return {"version": 1, "about": STATE_ABOUT, "to_bring_a_note_back": STATE_BRING_BACK,
            "places": {}}


def read_state(vault: Path) -> tuple[dict, bool]:
    """The record, and whether it may be written back.

    A record that cannot be read is left exactly as it is and nothing is
    recorded this run, which is said plainly. Treating it as empty and writing
    over it would throw away the only account of what the owner has removed.
    """
    path = state_path(vault)
    if not path.is_file():
        return empty_state(), True
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = None
    if not isinstance(data, dict):
        print(f"The record at {STATE_REL} could not be read. It is left exactly as it is,")
        print("and nothing is recorded this time, so a note you took out may come back.")
        return empty_state(), False
    places = data.get("places")
    tidy: dict = {}
    if isinstance(places, dict):
        for place, notes in places.items():
            if isinstance(notes, dict):
                tidy[place] = {n: e for n, e in notes.items() if isinstance(e, dict)}
    data["places"] = tidy
    data.setdefault("version", 1)
    return data, True


def save_state(vault: Path, state: dict, writable: bool, dry_run: bool) -> None:
    if dry_run or not writable:
        return
    state["version"] = 1
    state["about"] = STATE_ABOUT
    state["to_bring_a_note_back"] = STATE_BRING_BACK
    path = state_path(vault)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        write_atomic(path, json.dumps(state, indent=2, ensure_ascii=False) + "\n")
    except OSError:
        # the notes themselves are in place; a record that cannot be written is
        # said plainly and fails nothing
        print(f"The record at {STATE_REL} could not be written, so a note you take")
        print("out later may come back. Everything else was done.")


def claude_place(mem: Path) -> str:
    return "claude: " + shown_path(mem)


CHATGPT_PLACE = "chatgpt: " + str(NOTES_REL)


def note_entry(state: dict, place: str, name: str) -> dict:
    return state.get("places", {}).get(place, {}).get(name, {})


def was_written(state: dict, place: str, name: str) -> bool:
    return bool(note_entry(state, place, name).get("written"))


def was_removed(state: dict, place: str, name: str) -> bool:
    return bool(note_entry(state, place, name).get("removed"))


def mark_written(state: dict, place: str, name: str, dry_run: bool) -> None:
    if dry_run:
        return
    entry = state.setdefault("places", {}).setdefault(place, {}).setdefault(name, {})
    entry.setdefault("written", TODAY)


def mark_removed(state: dict, place: str, name: str, dry_run: bool) -> None:
    """Only ever called where the note was written and is now gone."""
    LEFT_OUT.append(name)
    if dry_run:
        return
    entry = state.setdefault("places", {}).setdefault(place, {}).setdefault(name, {})
    entry.setdefault("written", TODAY)
    entry["removed"] = TODAY


def restore(state: dict, what: str, seeds: list[Path], dry_run: bool) -> int:
    """Forget that the owner took a note out, so this run gives it again."""
    want = what.strip()
    names = {s.name for s in seeds}
    if want.lower() != "all":
        if want not in names and (want + ".md") in names:
            want += ".md"
        if want not in names:
            print(f"There is no starting note called \"{what}\". The notes are:")
            for n in sorted(names):
                print("  " + n)
            print("Use one of those, or the word all.")
            return 2
    print("Bringing back starting notes you had taken out")
    brought = set()   # a note can be recorded in more than one place; it is named once
    for notes in state.get("places", {}).values():
        for name in list(notes):
            if want.lower() != "all" and name != want:
                continue
            if "removed" not in notes[name]:
                continue
            brought.add(name)
            if not dry_run:
                notes.pop(name)
    for name in sorted(brought):
        print(f"  would bring back: {name}" if dry_run else f"  bringing back: {name}")
    if not brought:
        print("  nothing to bring back: no starting note is recorded as taken out")
    return 0


# ----- Claude: the memories as files in Claude Code's own memory folder -------

def shown_path(path: Path) -> str:
    home = str(Path.home())
    return "~" + str(path)[len(home):] if str(path).startswith(home) else str(path)


def seed_claude(vault: Path, seeds: list[Path], dry_run: bool, state: dict) -> int:
    rc = 0
    for mem in memory_dirs(vault):
        rc = seed_claude_into(mem, seeds, dry_run, state) or rc
    return rc


def seed_claude_into(mem: Path, seeds: list[Path], dry_run: bool, state: dict) -> int:
    print(f"Starting memories for Claude (in {shown_path(mem)})")
    place = claude_place(mem)
    index = mem / "MEMORY.md"
    existing = ""
    started = False       # the folder is only made when there is something to put in it
    # (v0.9.6) A memory folder with no index at all is a new one: a second Mac,
    # a new Mac, or a reset ~/.claude. The record travels with the wiki and
    # names the place the same way on every Mac, so without this every note
    # given on the first Mac was taken there for one the owner had removed,
    # and nothing was ever given on the second. An owner who takes notes out
    # takes out notes, not the index they are listed in.
    fresh = not index.exists()
    added = 0
    for s in seeds:
        dst = mem / s.name
        if dst.exists():
            # an install made before the record existed counts as given
            mark_written(state, place, s.name, dry_run)
            print(f"  present: {s.name}" if not dry_run else f"  present {s.name}")
            continue
        if was_removed(state, place, s.name):
            LEFT_OUT.append(s.name)
            print(f"  left out, because you took it out: {s.name}")
            continue
        if was_written(state, place, s.name) and not fresh:
            mark_removed(state, place, s.name, dry_run)
            print(f"  would note that you took this one out, and leave it out: {s.name}"
                  if dry_run else
                  f"  you took this one out, so it stays out from now on: {s.name}")
            continue
        if dry_run:
            print(f"  would seed {s.name}")
            continue
        if not started:
            mem.mkdir(parents=True, exist_ok=True)
            existing = index.read_text() if index.exists() else "# MEMORY\n\n"
            started = True
        dst.write_text(s.read_text())
        line = index_line(s)
        if s.name not in existing:
            existing = existing.rstrip("\n") + "\n" + line + "\n"
        added += 1
        mark_written(state, place, s.name, dry_run)
        print(f"  seeded: {s.name}")
    if dry_run:
        return 0
    if started:
        index.write_text(existing)
    print(f"  {added} memory file(s) added")
    return 0


# ----- ChatGPT: the same memories as a page of the wiki -----------------------

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


def seed_mark(seed: Path) -> str:
    """A line written under each section's heading, naming the seed it came
    from. The heading is the owner's and the assistant's to reword; the mark
    is how a later run still knows the note was given, and does not give it
    again. (A comment: it does not show when the page is read in Obsidian.)"""
    return f"<!-- moblee-seed: {seed.name} -->"


def already_given(page_text: str, seed: Path, heading: str) -> bool:
    """By its mark, or, for a page written before the marks existed, by its heading."""
    return seed_mark(seed) in page_text or has_heading(page_text, heading)


CLAUDE_ONLY_OPENING = "This note applies with Claude."


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
    if index.is_symlink():
        index = index.resolve()  # the file itself is written, never the link replaced
    # Read as bytes, so that every other line goes back exactly as it was:
    # its own line endings, and any byte that is not good UTF-8, untouched.
    try:
        raw = index.read_bytes()
    except OSError:
        return
    if b"[[Assistant Memory" in raw:
        return
    lines = raw.splitlines(keepends=True)
    for i, l in enumerate(lines):
        if l.lstrip().startswith(b"- Wiki Operations"):
            if dry_run:
                print("  would add the page to the Wiki Operations line of wiki/Index.md")
                return
            bare = l.rstrip(b"\r\n")
            lines[i] = bare.rstrip() + INDEX_LINK.encode("utf-8") + l[len(bare):]
            write_atomic_bytes(index, b"".join(lines))
            print("  page added to the Wiki Operations line of wiki/Index.md (that one line; nothing else in it was changed)")
            return


def seed_chatgpt(vault: Path, seeds: list[Path], dry_run: bool, state: dict) -> int:
    print(f"Starting memories for ChatGPT (in {NOTES_REL})")
    if not (vault / "wiki").is_dir():
        print(f"  no wiki/ folder at {vault}; nothing written")
        return 1
    page = vault / NOTES_REL
    current = page.read_text(encoding="utf-8") if page.is_file() else None
    place = CHATGPT_PLACE
    sections = []
    for s in seeds:
        text = s.read_text(encoding="utf-8")
        heading = seed_heading(s, text)
        body = seed_body(text)
        if body.lstrip().startswith(CLAUDE_ONLY_OPENING):
            # a note about Claude's own workings has no place on ChatGPT's page
            print(f"  left out (it applies with Claude only): {heading}")
            continue
        if current is not None and already_given(current, s, heading):
            # a page written before the record existed counts as given
            mark_written(state, place, s.name, dry_run)
            print(f"  present: {heading}" if not dry_run else f"  present {heading}")
            continue
        # The section is not on the page. If this script put it there once, the
        # owner has taken it out (or taken the whole page out), and it stays out.
        if was_removed(state, place, s.name):
            LEFT_OUT.append(s.name)
            print(f"  left out, because you took it out: {heading}")
            continue
        if was_written(state, place, s.name):
            mark_removed(state, place, s.name, dry_run)
            print(f"  would note that you took this one out, and leave it out: {heading}"
                  if dry_run else
                  f"  you took this one out, so it stays out from now on: {heading}")
            continue
        if dry_run:
            print(f"  would add {heading}")
            continue
        sections.append(f"## {heading}\n{seed_mark(s)}\n\n{body}\n")
        mark_written(state, place, s.name, dry_run)
        print(f"  added: {heading}")
    if not dry_run:
        if current is None and sections:
            page.parent.mkdir(parents=True, exist_ok=True)
            write_atomic(page, "\n".join([NOTES_OPENING] + sections))
        elif current is None:
            print("  the page is not there and every note has been taken out, so it is not made again")
        elif sections:
            append_text(page, "\n".join(sections))
        print(f"  {len(sections)} note(s) added")
    if dry_run or page.is_file():
        mention_in_instruction_file(vault, dry_run)
        extend_index(vault, dry_run)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault")
    ap.add_argument("--assistant", help="claude, chatgpt or both (default: the one kept in ~/.config/moblee/assistant, else claude)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--restore", metavar="WHAT",
                    help="bring back a starting note you took out: its file name, or all")
    a = ap.parse_args()
    LEFT_OUT.clear()   # so a second run in the same session starts from nothing
    assistant = read_assistant(a.assistant)
    vault = find_vault(a.vault)
    seeds = sorted(p for p in SEEDS.glob("*.md") if p.name != "MEMORY.md")
    state, writable = read_state(vault)
    if a.restore:
        rc = restore(state, a.restore, seeds, a.dry_run)
        if rc:
            return rc
        print("")
    rc = 0
    if assistant in ("claude", "both"):
        rc = seed_claude(vault, seeds, a.dry_run, state)
    if assistant in ("chatgpt", "both"):
        rc = seed_chatgpt(vault, seeds, a.dry_run, state) or rc
    save_state(vault, state, writable, a.dry_run)
    if LEFT_OUT:
        names = sorted(set(LEFT_OUT))
        print("")
        print(f"{len(names)} starting note(s) you took out would be left out, and would stay out."
              if a.dry_run else
              f"{len(names)} starting note(s) you took out were left out, and stay out.")
        print("To have them all back, run this from the Moblee folder:")
        print("  " + RESTORE_COMMAND)
        print("For one on its own, use its file name in place of the word all:")
        for n in names:
            print("  " + n)
    return rc


if __name__ == "__main__":
    sys.exit(main())
