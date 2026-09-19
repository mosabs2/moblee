#!/usr/bin/env python3
"""install-learning-path.py: add the optional learning path to a Moblee vault (Mac, Claude Code).

    python3 scripts/install-learning-path.py --vault <vault>                  add it, with the evening reminder
    python3 scripts/install-learning-path.py --vault <vault> --hour 20        a different reminder hour
    python3 scripts/install-learning-path.py --vault <vault> --no-reminder    the lessons without a reminder
    python3 scripts/install-learning-path.py --vault <vault> --remove-reminder   switch the reminder off

The installer and the updater ask before running it; it can also be run by hand at any time,
and running it again is safe. It does these things, each only if not already done:

  1. Copies the lessons page to wiki/Wiki Operations/Moblee Learning Path.md. An existing page
     is never replaced, because its Progress list records which lessons have been given.
  2. Adds a line for the page to wiki/Index.md, so the weekly check does not call it an orphan.
  3. Copies the reminder script to scripts/moblee-tip.sh (refreshed if the pack's copy changed).
  4. Adds the coaching rule to CLAUDE.md, directly after the orient section, so that saying
     "lesson" gives the next lesson and orient mentions it once a day.
  5. On macOS, schedules the reminder with launchd (com.moblee.nightly-tip). Without --hour an
     existing schedule keeps its hour (9 pm for a new one). A changed schedule file is copied to
     ~/.config/moblee/backups/<stamp>/ before it is refreshed.

Nothing is deleted. --remove-reminder unloads the schedule and moves its file to the backups folder.
"""
from __future__ import annotations

import argparse
import os
import platform
import plistlib
import shutil
import subprocess
import sys
import time
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent.parent
PAGE_SRC = PACKAGE / "learning-path" / "Moblee Learning Path.md"
TIP_SRC = PACKAGE / "learning-path" / "moblee-tip.sh"
PAGE_REL = Path("wiki") / "Wiki Operations" / "Moblee Learning Path.md"
LABEL = "com.moblee.nightly-tip"
PLIST = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"
BACKUPS = Path.home() / ".config" / "moblee" / "backups"
MARKER = "## The learning path (coaching)"
INDEX_LINE = "- [[Moblee Learning Path]]: thirty-two short lessons on using this wiki, one an evening; say \"lesson\" to Claude.\n"
COACHING = """## The learning path (coaching)

`wiki/Wiki Operations/Moblee Learning Path.md` holds thirty-two short lessons on using this wiki, with a Progress list at the bottom. If the evening reminder is installed, a notification names the next lesson each evening. When the user's whole message is **"lesson"**, **"next lesson"** or **"lesson N"** (and only that; a message that merely contains the word is not a trigger): read the page, take the lowest lesson not yet listed under Progress (or the one named), and give it in your own words in a few sentences, tied to what the log shows the user has actually done recently; offer to do its "This evening" step together now, and do it if the user agrees; then, if that lesson is not already listed, append a line `- N, YYYY-MM-DD` under Progress (date from the clock, never from memory) and commit. At every **orient**, if no lesson has been given today and lessons remain, end the sitrep with one sentence naming the next lesson (a statement, not a question); do not give it unasked. At the first orient on or after each Saturday, add one sentence saying how many lessons remain and naming one tool from a given lesson that the log shows has gone unused since, with an offer to go over it again. Never mark a lesson given that was not given. If the user asks to stop the evening reminder, tell them to run `python3 scripts/install-learning-path.py --vault <vault> --remove-reminder` from the folder where they downloaded Moblee.
"""
PROTECTED = ("Documents", "Desktop", "Downloads", "Library/Mobile Documents")


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def write_atomic(p: Path, text: str) -> None:
    tmp = p.with_name(p.name + ".moblee-tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, p)


def add_page(vault: Path) -> None:
    dest = vault / PAGE_REL
    if dest.exists():
        print(f"lessons page already in place ({PAGE_REL}); left as it is")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(PAGE_SRC, dest)
    print(f"lessons page added: {PAGE_REL}")


def add_index_line(vault: Path) -> None:
    index = vault / "wiki" / "Index.md"
    if not index.exists():
        return
    text = read(index)
    if "[[Moblee Learning Path]]" in text:
        return
    lines = text.splitlines(keepends=True)
    at = None
    for i, l in enumerate(lines):
        if l.strip().lower().startswith("## subfolder"):
            at = len(lines)
            for j in range(i + 1, len(lines)):
                if lines[j].startswith("## "):
                    at = j
                    break
            break
    if lines and not lines[-1].endswith("\n"):
        lines[-1] += "\n"
    if at is None:
        lines += ["\n", INDEX_LINE]
    else:
        while at > 0 and lines[at - 1].strip() == "":
            at -= 1
        lines.insert(at, INDEX_LINE if lines[at - 1].startswith("- ") else "\n" + INDEX_LINE)
    write_atomic(index, "".join(lines))
    print("line for the lessons page added to wiki/Index.md")


def add_tip_script(vault: Path) -> Path:
    dest = vault / "scripts" / "moblee-tip.sh"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.read_bytes() == TIP_SRC.read_bytes():
        print("reminder script already in place (scripts/moblee-tip.sh)")
    else:
        shutil.copy2(TIP_SRC, dest)
        print("reminder script copied to scripts/moblee-tip.sh")
    return dest


def add_coaching_rule(vault: Path) -> None:
    claude = vault / "CLAUDE.md"
    if not claude.exists():
        print("CLAUDE.md not found; the coaching rule was not added")
        return
    lines = read(claude).splitlines(keepends=True)
    if any(l.startswith(MARKER) for l in lines):
        print("coaching rule already in CLAUDE.md")
        return
    at = None
    for i, l in enumerate(lines):
        if l.startswith('## The "orient" command'):
            at = len(lines)
            for j in range(i + 1, len(lines)):
                if lines[j].startswith("## "):
                    at = j
                    break
            break
    if lines and not lines[-1].endswith("\n"):
        lines[-1] += "\n"
    if at is None:
        lines += ["\n", COACHING]
        where = "at the end (no orient section found)"
    else:
        lines.insert(at, COACHING + "\n")
        where = "after the orient section"
    write_atomic(claude, "".join(lines))
    print(f"coaching rule added to CLAUDE.md {where}")


def backup_plist() -> Path:
    keep = BACKUPS / time.strftime("%Y%m%d-%H%M%S")
    keep.mkdir(parents=True, exist_ok=True)
    shutil.copy2(PLIST, keep / PLIST.name)
    return keep


def current_hour() -> int | None:
    try:
        with open(PLIST, "rb") as fh:
            return int(plistlib.load(fh)["StartCalendarInterval"]["Hour"])
    except Exception:
        return None


def launchd(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["launchctl", *args], capture_output=True, text=True)


def is_loaded() -> bool:
    return launchd("print", f"gui/{os.getuid()}/{LABEL}").returncode == 0


def schedule_reminder(vault: Path, script: Path, hour: int | None) -> int:
    if platform.system() != "Darwin":
        print('the evening reminder needs macOS; skipped (say "lesson" to Claude whenever you like)')
        return 0
    if hour is None:
        hour = current_hour() if current_hour() is not None else 21
    home = Path.home()
    if any(str(vault).startswith(str(home / p) + os.sep) for p in PROTECTED):
        print("note: this vault is in a folder macOS protects (Documents, Desktop, Downloads or iCloud Drive).")
        print("      The reminder may be blocked from reading it; if no reminder ever appears, give")
        print("      /bin/bash Full Disk Access in System Settings > Privacy & Security, or keep the")
        print("      lessons without it (--remove-reminder) and say \"lesson\" when you like.")
    log_dir = home / ".config" / "moblee" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    job = {
        "Label": LABEL,
        "ProgramArguments": ["/bin/bash", str(script)],
        "EnvironmentVariables": {"MOBLEE_VAULT": str(vault)},
        "WorkingDirectory": str(vault),
        "StartCalendarInterval": {"Hour": hour, "Minute": 0},
        "StandardOutPath": str(log_dir / "nightly-tip.log"),
        "StandardErrorPath": str(log_dir / "nightly-tip.log"),
        "RunAtLoad": False,
    }
    PLIST.parent.mkdir(parents=True, exist_ok=True)
    unchanged = False
    if PLIST.exists():
        try:
            with open(PLIST, "rb") as fh:
                unchanged = plistlib.load(fh) == job
        except Exception:
            unchanged = False
    if unchanged:
        print(f"evening reminder already scheduled for {hour:02d}:00")
    else:
        if PLIST.exists():
            backup_plist()
        tmp = PLIST.with_name(PLIST.name + ".moblee-tmp")
        with open(tmp, "wb") as fh:
            plistlib.dump(job, fh)
        os.replace(tmp, PLIST)
        print(f"evening reminder scheduled for {hour:02d}:00")
    if os.environ.get("MOBLEE_NO_LOAD"):
        # set by the pack's sandbox tests: write the schedule file but never load it
        print("schedule written but not loaded (MOBLEE_NO_LOAD is set)")
        return 0
    if unchanged and is_loaded():
        return 0
    if is_loaded():
        launchd("bootout", f"gui/{os.getuid()}/{LABEL}")
        for _ in range(20):  # the old job takes a moment to leave; bootstrap fails while it is there
            if not is_loaded():
                break
            time.sleep(0.25)
    r = launchd("bootstrap", f"gui/{os.getuid()}", str(PLIST))
    if r.returncode != 0:
        time.sleep(1)
        r = launchd("bootstrap", f"gui/{os.getuid()}", str(PLIST))
    if r.returncode != 0:
        r = launchd("load", str(PLIST))
    if r.returncode != 0:
        print("launchd would not load the reminder:", (r.stderr or r.stdout).strip())
        print(f'Run this in Terminal to load it:  launchctl load "{PLIST}"')
        return 1
    print("reminder loaded. If macOS asks whether Script Editor or osascript may show notifications, choose Allow;")
    print("if no reminder ever appears, allow them in System Settings > Notifications.")
    return 0


def remove_reminder() -> int:
    if platform.system() != "Darwin":
        print("there is no evening reminder on this system")
        return 0
    if not os.environ.get("MOBLEE_NO_LOAD") and is_loaded():
        launchd("bootout", f"gui/{os.getuid()}/{LABEL}")
    if PLIST.exists():
        keep = backup_plist()
        PLIST.rename(keep / (PLIST.name + ".removed"))
        print(f"evening reminder switched off; its schedule file was moved to {keep}")
    else:
        print("no evening reminder was scheduled")
    print('The lessons stay in the vault: say "lesson" to Claude whenever you like.')
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Add the optional learning path to a Moblee vault.")
    ap.add_argument("--vault", required=True, help="the vault folder (the one holding CLAUDE.md and wiki/)")
    ap.add_argument("--hour", type=int, default=None, help="reminder hour, 0 to 23 (default: keep the current one, else 21)")
    ap.add_argument("--no-reminder", action="store_true", help="add the lessons without the evening reminder")
    ap.add_argument("--remove-reminder", action="store_true", help="switch the evening reminder off (the lessons stay)")
    a = ap.parse_args()
    if a.remove_reminder:
        return remove_reminder()
    vault = Path(a.vault).expanduser().resolve()
    if not (vault / "wiki").is_dir():
        sys.exit(f"{vault} does not look like a Moblee vault (no wiki/ folder).")
    if not PAGE_SRC.exists() or not TIP_SRC.exists():
        sys.exit(f"The pack's learning-path folder is incomplete ({PAGE_SRC.parent}).")
    if a.hour is not None and not 0 <= a.hour <= 23:
        sys.exit("--hour must be between 0 and 23.")
    add_page(vault)
    add_index_line(vault)
    script = add_tip_script(vault)
    add_coaching_rule(vault)
    rc = 0 if a.no_reminder else schedule_reminder(vault, script, a.hour)
    print('Learning path ready. Open Claude Code in your vault and say "lesson" to begin.')
    return rc


if __name__ == "__main__":
    sys.exit(main())
