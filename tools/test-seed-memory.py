#!/usr/bin/env python3
"""Test suite for scripts/seed-memory.py and the checklist's opening message.

Two things are tested here, both about what an owner is told and what comes
back at them after an update.

1. The starting memories (scripts/seed-memory.py). Throwaway practice homes and
   practice wikis are built in the system temp area and seeded the way the
   installer and the updater seed them: a first run, a second run that must
   change nothing, a note taken out by the owner and a run after that, which
   must leave it out, and --restore, which must bring it back. Both layouts are
   covered: Claude's memory folder and ChatGPT's page in the wiki.

2. The checklist's opening (scripts/moblee-setup.py, checklist_opening). An
   owner who uses ChatGPT alone must never be told to install Claude Code. The
   message is read for each of claude, chatgpt and both, with and without the
   claude command on the PATH.

Both scripts are imported and their functions called, rather than started as
separate processes, so that the vault safety guard has nothing to read this
test for. The real commands they stand in for are:

    python3 scripts/seed-memory.py --vault <wiki> --assistant claude
    python3 scripts/seed-memory.py --vault <wiki> --assistant chatgpt
    python3 scripts/seed-memory.py --vault <wiki> --restore all
    python3 scripts/moblee-setup.py

Usage:  python3 tools/test-seed-memory.py
Prints a pass/fail table and exits non-zero on any failure.

Nothing is deleted: each practice home is a few kilobytes and is left in the
system temp area, with its path printed at the end. Where a test needs a note
to be gone, the practice file is moved aside into the same throwaway folder,
never removed.
"""
import contextlib
import importlib.util
import io
import json
import os
import pathlib
import sys
import tempfile

PACK = pathlib.Path(__file__).resolve().parent.parent
SEED_SCRIPT = PACK / "scripts" / "seed-memory.py"
SETUP_SCRIPT = PACK / "scripts" / "moblee-setup.py"
SEEDS = sorted(p for p in (PACK / "memory-seed").glob("*.md") if p.name != "MEMORY.md")


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def practice(name):
    """A throwaway home with a practice wiki in it, and an aside/ folder."""
    # resolved, so that the path the wiki is named by and the path it resolves
    # to are the same one, and Claude's memory folder is named once
    root = pathlib.Path(tempfile.mkdtemp(prefix="seed-memory-%s-" % name)).resolve()
    home = root / "home"
    vault = home / "Wiki" / "Practice Wiki"
    write(vault / "CLAUDE.md", "# CLAUDE.md\n\nRules for this wiki.\n")
    write(vault / "wiki" / "Index.md",
          "# Index\n\n- Wiki Operations: [[Habits and Tools]]\n")
    (root / "aside").mkdir()
    return root, home, vault


def run_seed(mod, home, vault, argv):
    """Seed a practice wiki. Returns (exit code, printed text)."""
    out, err = io.StringIO(), io.StringIO()
    old_argv, old_home = sys.argv, os.environ.get("HOME")
    old_vault = os.environ.get("MOBLEE_VAULT")
    sys.argv = ["seed-memory.py", "--vault", str(vault)] + argv
    os.environ["HOME"] = str(home)
    os.environ.pop("MOBLEE_VAULT", None)
    mod.VAULT_AS_NAMED = None
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = mod.main()
            except SystemExit as e:
                code = e.code if isinstance(e.code, int) else 1
    finally:
        sys.argv = old_argv
        if old_home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = old_home
        if old_vault is not None:
            os.environ["MOBLEE_VAULT"] = old_vault
    return code, out.getvalue() + err.getvalue()


def memory_dir(home, vault):
    encoded = "".join(c if c.isalnum() else "-" for c in str(vault))
    return home / ".claude" / "projects" / encoded / "memory"


def snapshot(root):
    return sorted(str(p.relative_to(root)) for p in root.rglob("*"))


def record(vault):
    path = vault / ".moblee" / "seed-state.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def entries(vault, place_starts):
    """The one place in the record whose name starts with this, or {}."""
    data = record(vault) or {}
    for place, notes in (data.get("places") or {}).items():
        if place.startswith(place_starts):
            return notes
    return {}


def move_aside(root, path):
    """Take a file out the way the owner would, without deleting anything."""
    target = root / "aside" / path.name
    n = 1
    while target.exists():
        target = root / "aside" / ("%d-%s" % (n, path.name))
        n += 1
    os.replace(path, target)


def drop_section(page, heading):
    """Delete one section from the ChatGPT page, the way the owner would in
    Obsidian: the heading, its mark and its body, down to the next heading."""
    lines = page.read_text(encoding="utf-8").splitlines(keepends=True)
    kept, skipping = [], False
    for line in lines:
        if line.strip() == "## " + heading:
            skipping = True
            continue
        if skipping and line.startswith("## "):
            skipping = False
        if not skipping:
            kept.append(line)
    page.write_text("".join(kept), encoding="utf-8")


def setup_opening(mod, home, checking, with_claude):
    """The checklist's opening message for this practice home."""
    # two folders, so that "not installed" is never a folder a previous case
    # has already put a claude command into
    bin_dir = home / ("bin-with-claude" if with_claude else "bin-without-claude")
    bin_dir.mkdir(parents=True, exist_ok=True)
    if with_claude:
        claude = bin_dir / "claude"
        if not claude.exists():
            claude.write_text("#!/bin/bash\necho claude\n", encoding="utf-8")
            claude.chmod(0o755)
    old_home, old_path = os.environ.get("HOME"), os.environ.get("PATH")
    old_prefix = mod.brew_prefix
    os.environ["HOME"] = str(home)
    os.environ["PATH"] = str(bin_dir)
    # the real Mac's Homebrew folder must not be searched for a real claude
    mod.brew_prefix = lambda: None
    mod.CONFIG_DIR = pathlib.Path(home) / ".config" / "moblee"
    try:
        return mod.checklist_opening(checking)
    finally:
        mod.brew_prefix = old_prefix
        if old_home is not None:
            os.environ["HOME"] = old_home
        if old_path is not None:
            os.environ["PATH"] = old_path


def main():
    seed = load("seed_memory", SEED_SCRIPT)
    setup = load("moblee_setup", SETUP_SCRIPT)
    rows = []
    failures = 0
    roots = []

    def check(group, label, ok):
        nonlocal failures
        if not ok:
            failures += 1
        rows.append(("PASS" if ok else "FAIL", group, label))

    claude_only = [s.name for s in SEEDS
                   if seed.seed_body(s.read_text(encoding="utf-8")).lstrip()
                   .startswith(seed.CLAUDE_ONLY_OPENING)]
    for_chatgpt = [s.name for s in SEEDS if s.name not in claude_only]

    # ------------------------------------------------------- Claude: a first seed
    root, home, vault = practice("claude")
    roots.append(root)
    mem = memory_dir(home, vault)
    code, text = run_seed(seed, home, vault, ["--assistant", "claude"])
    check("claude first", "exits 0", code == 0)
    check("claude first", "every starting memory is written",
          all((mem / s.name).is_file() for s in SEEDS))
    check("claude first", "each one is reported as seeded",
          all(("seeded: " + s.name) in text for s in SEEDS))
    check("claude first", "the index lists them",
          all(s.name in (mem / "MEMORY.md").read_text() for s in SEEDS))
    check("claude first", "the record is written into the wiki",
          (vault / ".moblee" / "seed-state.json").is_file())
    check("claude first", "the record says what it is and how to undo a removal",
          "removed" in (record(vault) or {}).get("about", "")
          and "--restore all" in (record(vault) or {}).get("to_bring_a_note_back", ""))
    check("claude first", "every note is recorded as written",
          all(entries(vault, "claude:").get(s.name, {}).get("written") for s in SEEDS))
    check("claude first", "nothing is recorded as removed",
          not any("removed" in e for e in entries(vault, "claude:").values()))

    # -------------------------------------------------- Claude: a second seed
    before = snapshot(home)
    before_record = record(vault)
    code, text = run_seed(seed, home, vault, ["--assistant", "claude"])
    check("claude again", "exits 0", code == 0)
    check("claude again", "every note is reported as already present",
          all(("present: " + s.name) in text for s in SEEDS))
    check("claude again", "nothing is seeded again", "seeded:" not in text)
    check("claude again", "0 memory files added", "0 memory file(s) added" in text)
    check("claude again", "not one file changes", snapshot(home) == before)
    check("claude again", "the record does not change", record(vault) == before_record)

    # ------------------------------- Claude: the owner takes a note out
    gone = SEEDS[0]
    move_aside(root, mem / gone.name)
    code, text = run_seed(seed, home, vault, ["--assistant", "claude"])
    check("claude removal", "exits 0", code == 0)
    check("claude removal", "the removal is noticed and said plainly",
          ("you took this one out, so it stays out from now on: " + gone.name) in text)
    check("claude removal", "the note is NOT written again",
          not (mem / gone.name).exists())
    check("claude removal", "the removal is recorded",
          bool(entries(vault, "claude:").get(gone.name, {}).get("removed")))
    check("claude removal", "the day it was written is kept too",
          bool(entries(vault, "claude:").get(gone.name, {}).get("written")))
    check("claude removal", "the other notes are untouched",
          all((mem / s.name).is_file() for s in SEEDS[1:]))
    check("claude removal", "the owner is told how to get it back",
          "--restore all" in text and gone.name in text)

    # ------------------------------------- Claude: and it stays out next time
    code, text = run_seed(seed, home, vault, ["--assistant", "claude"])
    check("claude stays out", "exits 0", code == 0)
    check("claude stays out", "it is left out, and the reason is given",
          ("left out, because you took it out: " + gone.name) in text)
    check("claude stays out", "it is still not written", not (mem / gone.name).exists())
    check("claude stays out", "exactly one note is recorded as removed",
          sum(1 for e in entries(vault, "claude:").values() if "removed" in e) == 1)

    # ------------------------------------------------ Claude: a dry run records nothing
    move_aside(root, mem / SEEDS[1].name)
    before = snapshot(home)
    before_record = record(vault)
    code, text = run_seed(seed, home, vault, ["--assistant", "claude", "--dry-run"])
    check("claude dry run", "exits 0", code == 0)
    check("claude dry run", "it says what it would record",
          ("would note that you took this one out, and leave it out: " + SEEDS[1].name) in text)
    check("claude dry run", "it writes nothing at all", snapshot(home) == before)
    check("claude dry run", "the record is not touched", record(vault) == before_record)
    check("claude dry run", "the already-removed note is still reported as left out",
          ("left out, because you took it out: " + gone.name) in text)

    # --------------------------------------------------------- Claude: restore
    code, text = run_seed(seed, home, vault, ["--assistant", "claude"])   # record the second removal
    check("claude restore", "the second removal is recorded first",
          bool(entries(vault, "claude:").get(SEEDS[1].name, {}).get("removed")))
    code, text = run_seed(seed, home, vault, ["--assistant", "claude", "--restore", gone.name])
    check("claude restore", "exits 0", code == 0)
    check("claude restore", "it says which note is coming back",
          ("bringing back: " + gone.name) in text)
    check("claude restore", "the note is written again", (mem / gone.name).is_file())
    check("claude restore", "its removal is forgotten",
          "removed" not in entries(vault, "claude:").get(gone.name, {}))
    check("claude restore", "the other removed note stays out",
          not (mem / SEEDS[1].name).exists())
    code, text = run_seed(seed, home, vault, ["--assistant", "claude", "--restore", "all"])
    check("claude restore", "restore all brings the rest back",
          (mem / SEEDS[1].name).is_file())
    check("claude restore", "nothing is left recorded as removed",
          not any("removed" in e for e in entries(vault, "claude:").values()))
    code, text = run_seed(seed, home, vault,
                          ["--assistant", "claude", "--restore", "no-such-note.md"])
    check("claude restore", "an unknown name is refused, with the real names listed",
          code == 2 and all(s.name in text for s in SEEDS))

    # ------------------------------------------------------ ChatGPT: a first seed
    root2, home2, vault2 = practice("chatgpt")
    roots.append(root2)
    page = vault2 / seed.NOTES_REL
    code, text = run_seed(seed, home2, vault2, ["--assistant", "chatgpt"])
    check("chatgpt first", "exits 0", code == 0)
    check("chatgpt first", "the page is made", page.is_file())
    check("chatgpt first", "every note that suits ChatGPT is on it",
          all(seed.seed_mark(pathlib.Path(n)) in page.read_text() for n in for_chatgpt))
    check("chatgpt first", "the Claude-only note is left out, and said to be",
          bool(claude_only)
          and all(seed.seed_mark(pathlib.Path(n)) not in page.read_text() for n in claude_only)
          and "it applies with Claude only" in text)
    check("chatgpt first", "a Claude-only note is not recorded as given",
          not any(n in entries(vault2, "chatgpt:") for n in claude_only))
    check("chatgpt first", "the notes given are recorded as written",
          all(entries(vault2, "chatgpt:").get(n, {}).get("written") for n in for_chatgpt))

    # ------------------------------------------------- ChatGPT: a second seed
    before = snapshot(home2)
    before_record = record(vault2)
    code, text = run_seed(seed, home2, vault2, ["--assistant", "chatgpt"])
    check("chatgpt again", "exits 0", code == 0)
    check("chatgpt again", "nothing is added", "0 note(s) added" in text)
    check("chatgpt again", "not one file changes", snapshot(home2) == before)
    check("chatgpt again", "the record does not change", record(vault2) == before_record)

    # --------------------------------- ChatGPT: the owner deletes a section
    dropped = for_chatgpt[0]
    dropped_heading = seed.seed_heading(PACK / "memory-seed" / dropped,
                                        (PACK / "memory-seed" / dropped).read_text())
    drop_section(page, dropped_heading)
    check("chatgpt removal", "the section, mark and all, really is gone",
          seed.seed_mark(pathlib.Path(dropped)) not in page.read_text())
    code, text = run_seed(seed, home2, vault2, ["--assistant", "chatgpt"])
    check("chatgpt removal", "exits 0", code == 0)
    check("chatgpt removal", "the removal is noticed and said plainly",
          ("you took this one out, so it stays out from now on: " + dropped_heading) in text)
    check("chatgpt removal", "the section is NOT added again",
          seed.seed_mark(pathlib.Path(dropped)) not in page.read_text())
    check("chatgpt removal", "the removal is recorded",
          bool(entries(vault2, "chatgpt:").get(dropped, {}).get("removed")))
    check("chatgpt removal", "the owner is told how to get it back",
          "--restore all" in text and dropped in text)
    code, text = run_seed(seed, home2, vault2, ["--assistant", "chatgpt"])
    check("chatgpt stays out", "it stays out at the next update",
          ("left out, because you took it out: " + dropped_heading) in text
          and seed.seed_mark(pathlib.Path(dropped)) not in page.read_text())
    code, text = run_seed(seed, home2, vault2, ["--assistant", "chatgpt", "--restore", "all"])
    check("chatgpt restore", "restore all puts the section back",
          seed.seed_mark(pathlib.Path(dropped)) in page.read_text())

    # ----------------------------- ChatGPT: the owner deletes the whole page
    root3, home3, vault3 = practice("chatgpt-page")
    roots.append(root3)
    page3 = vault3 / seed.NOTES_REL
    run_seed(seed, home3, vault3, ["--assistant", "chatgpt"])
    move_aside(root3, page3)
    code, text = run_seed(seed, home3, vault3, ["--assistant", "chatgpt"])
    check("chatgpt page gone", "exits 0", code == 0)
    check("chatgpt page gone", "the page is not made again", not page3.exists())
    check("chatgpt page gone", "it says why",
          "every note has been taken out, so it is not made again" in text)
    check("chatgpt page gone", "every note given is recorded as removed",
          all(entries(vault3, "chatgpt:").get(n, {}).get("removed") for n in for_chatgpt))
    code, text = run_seed(seed, home3, vault3, ["--assistant", "chatgpt", "--restore", "all"])
    check("chatgpt page gone", "restore all makes the page again", page3.is_file())

    # ------------------------------------- a record that cannot be read
    root4, home4, vault4 = practice("broken-record")
    roots.append(root4)
    run_seed(seed, home4, vault4, ["--assistant", "claude"])
    broken = vault4 / ".moblee" / "seed-state.json"
    broken.write_text("{ this is not json", encoding="utf-8")
    code, text = run_seed(seed, home4, vault4, ["--assistant", "claude"])
    check("broken record", "exits 0", code == 0)
    check("broken record", "it says the record could not be read",
          "could not be read" in text)
    check("broken record", "the unreadable record is left exactly as it is",
          broken.read_text() == "{ this is not json")

    # ------------------------------------------------- a first seed for both
    root5, home5, vault5 = practice("both")
    roots.append(root5)
    code, text = run_seed(seed, home5, vault5, ["--assistant", "both"])
    check("both", "exits 0", code == 0)
    check("both", "Claude's folder and ChatGPT's page are both filled",
          (memory_dir(home5, vault5) / SEEDS[0].name).is_file()
          and (vault5 / seed.NOTES_REL).is_file())
    check("both", "the record keeps the two places apart",
          len(record(vault5)["places"]) == 2)
    check("both", "a note removed from one place is not called removed in the other",
          not any("removed" in e
                  for notes in record(vault5)["places"].values()
                  for e in notes.values()))

    # -------------------------------------------- the checklist's opening
    root6, home6, _ = practice("checklist")
    roots.append(root6)
    config = home6 / ".config" / "moblee"
    forbidden = "Claude Code is not installed yet"

    for choice in ("claude", "chatgpt", "both"):
        write(config / "assistant", choice + "\n")
        for has_claude in (True, False):
            lines, stop = setup_opening(setup, home6, False, has_claude)
            text = "\n".join(lines)
            label = "%s, claude %s" % (choice, "on the PATH" if has_claude else "not installed")
            if choice == "chatgpt":
                check("checklist", label + ": never told to install Claude Code",
                      forbidden not in text)
                check("checklist", label + ": told plainly there is nothing here yet",
                      "nothing here for you to add today" in text)
                check("checklist", label + ": told nothing is wrong",
                      "Nothing is wrong, and nothing needs doing." in text)
                check("checklist", label + ": the run stops there", stop is True)
            else:
                check("checklist", label + ": the run carries on", stop is False)
                check("checklist", label + ": the Claude Code line is right",
                      (forbidden in text) is (not has_claude))
            if choice == "both":
                check("checklist", label + ": told the list is set up for Claude",
                      "set up" in text and "Moblee does not set them up for" in text)
            if choice == "claude" and has_claude:
                check("checklist", label + ": nothing at all is said", lines == [])

    # --check keeps going for a ChatGPT owner, because it changes nothing
    write(config / "assistant", "chatgpt\n")
    lines, stop = setup_opening(setup, home6, True, False)
    text = "\n".join(lines)
    check("checklist", "chatgpt with --check: the test still runs", stop is False)
    check("checklist", "chatgpt with --check: still never told to install Claude Code",
          forbidden not in text)
    check("checklist", "chatgpt with --check: warned what the test will say",
          "it will say they are not set up" in text)

    # no file, and a file with nonsense in it, both mean Claude
    for content in (None, "banana\n"):
        if content is None:
            move_aside(root6, config / "assistant")
        else:
            write(config / "assistant", content)
        lines, stop = setup_opening(setup, home6, False, True)
        check("checklist", "no choice recorded (%s) means Claude, and the run carries on"
              % ("no file" if content is None else "a word that is not a choice"),
              stop is False and lines == [])

    # ------------------------------------------------------------------ table
    width = max(len(r[2]) for r in rows)
    group_width = max(len(r[1]) for r in rows)
    print("%-4s %-*s %-*s" % ("", group_width, "group", width, "case"))
    for status, group, label in rows:
        print("%-4s %-*s %-*s" % (status, group_width, group, width, label))
    print()
    print("cases: %d   failures: %d" % (len(rows), failures))
    for r in roots:
        print("practice home: %s" % r)
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
