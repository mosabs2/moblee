#!/usr/bin/env python3
"""first-days.py — the five-day tour at the start of a conversation.

Owners who already know their assistant never say "guide me", so they never
hear about what the wiki can do beyond notes. For the first five days of use,
this hook asks the assistant to add one line to its first reply of the day:
one thing the wiki can do, chosen to fit what the owner has been doing, and
offered as something to see. After day five it says nothing, and the
companion's usual rule (one offer, only when asked) is all there is.

INSTALLATION
    The script lives inside the wiki, at

        <wiki>/scripts/first-days.py

    and is registered by safety/install-safety.py as Claude's SessionStart
    hook, the hook that runs when a conversation starts or is resumed:

        python3 "<wiki>/scripts/first-days.py"

    It takes the wiki to be the folder its own folder sits in, as the other
    in-wiki scripts do. It is registered for Claude only; see the notes in
    install-safety.py for why not yet for ChatGPT.

DAYS OF USE, NOT CALENDAR DAYS
    Each distinct local date on which a conversation starts in this wiki is
    one day. A week away does not use the tour up. The first conversation in a
    wiki with no record starts day one, so an owner who updates an older wiki
    gets the tour from that day. The line is given once per day of use, at the
    first conversation of that day; later conversations that day hear nothing.

WHAT IT PRINTS
    On a tour day, one JSON object on standard output:

        {"hookSpecificOutput": {"hookEventName": "SessionStart",
                                "additionalContext": "<the instruction>"}}

    which is the shape Claude Code's hooks reference documents for
    SessionStart (https://code.claude.com/docs/en/hooks: SessionStart is
    context-only; hookSpecificOutput.additionalContext is added to the
    conversation before the first prompt; plain stdout on exit 0 would also be
    taken as context, and JSON is parsed only when stdout is one object and
    nothing else). On every other day, nothing.

NEVER IN THE WAY
    No network, no subprocess, one small file read and written. Any error at
    all, and it prints nothing and exits 0: a conversation never waits on it,
    never sees an error from it, and is never blocked by it.

WHERE IT KEEPS ITS RECORD
    ~/.config/moblee/state/first-days.json, keyed by the wiki's resolved path:
        {"wikis": {"<path>": {"days": ["2026-10-28", ...],
                              "last_told": "2026-10-28",
                              "done": false, "ended": null}}}
    MOBLEE_FIRST_DAYS_STATE overrides the file, and MOBLEE_VAULT the wiki; the
    pack's tests use both.

BY HAND
    python3 scripts/first-days.py --stop      the owner said "stop the tour"
    python3 scripts/first-days.py --status    where the tour stands
    python3 scripts/first-days.py --preview   print today's line without counting
"""
from __future__ import annotations

import datetime
import fcntl
import json
import os
import sys
import tempfile
from pathlib import Path

TOUR_DAYS = 5
CATALOGUE = "wiki/Wiki Operations/What Your Wiki Can Do.md"
HABITS = "wiki/Wiki Operations/Habits and Tools.md"


def state_file() -> Path:
    env = os.environ.get("MOBLEE_FIRST_DAYS_STATE", "").strip()
    if env:
        return Path(env).expanduser()
    return Path.home() / ".config" / "moblee" / "state" / "first-days.json"


def vault_path() -> Path:
    env = os.environ.get("MOBLEE_VAULT", "").strip()
    if env:
        return Path(env).expanduser().resolve()
    return Path(__file__).resolve().parent.parent


def assistant_choice(explicit: str | None) -> str:
    if explicit in ("claude", "chatgpt", "both"):
        return explicit
    try:
        word = (Path.home() / ".config" / "moblee" / "assistant").read_text().split("\n", 1)[0]
        word = "".join(word.split()).lower()
    except (OSError, ValueError):
        word = ""
    return word if word in ("claude", "chatgpt", "both") else "claude"


def load(path: Path) -> dict:
    """The record, or a fresh one when there is none or it cannot be read. A
    damaged record is started afresh rather than leaving the tour silent for
    good: the worst it costs is a tour day told twice."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"wikis": {}}
    except (ValueError, UnicodeDecodeError):
        return {"wikis": {}}
    if not isinstance(data, dict) or not isinstance(data.get("wikis"), dict):
        return {"wikis": {}}
    return data


def save(path: Path, data: dict) -> None:
    """Written whole to a temporary file beside the record, then moved over it,
    so a reader never sees half a record."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-first-days-")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(json.dumps(data, indent=2, sort_keys=True) + "\n")
    os.replace(tmp, path)


def lock_file(path: Path) -> Path:
    return path.with_name(path.name + ".lock")


def started_here(raw: str, vault: Path) -> bool:
    """Whether the conversation started in this wiki. The hook is registered
    for every Claude conversation on the Mac, so one started in another folder
    (a code project, a second wiki) must neither hear the tour nor use a day.
    Claude sends the conversation's folder as "cwd"; without it, the folder
    the hook was started in stands in."""
    cwd = None
    try:
        msg = json.loads(raw) if raw.strip() else {}
        if isinstance(msg, dict) and isinstance(msg.get("cwd"), str) and msg["cwd"].strip():
            cwd = Path(msg["cwd"]).expanduser()
    except ValueError:
        cwd = None
    try:
        here = (cwd or Path.cwd()).resolve()
    except OSError:
        return False
    return here == vault or vault in here.parents


def entry_for(data: dict, key: str) -> dict:
    e = data["wikis"].get(key)
    if not isinstance(e, dict):
        e = {}
    days = e.get("days")
    e["days"] = [d for d in days if isinstance(d, str)] if isinstance(days, list) else []
    e.setdefault("last_told", None)
    e.setdefault("done", False)
    e.setdefault("ended", None)
    data["wikis"][key] = e
    return e


def count_today(e: dict, today: str) -> int | None:
    """Record today as a day of use. The day number to tell about, or None for
    nothing to say (the tour is over, or today was already told)."""
    if e.get("done"):
        return None
    if today not in e["days"]:
        if len(e["days"]) >= TOUR_DAYS:
            e["done"], e["ended"] = True, e.get("ended") or today
            return None
        e["days"].append(today)
    if e.get("last_told") == today:
        return None
    e["last_told"] = today
    return e["days"].index(today) + 1


def instruction(day: int, assistant: str, vault: Path) -> str:
    """What the assistant is asked to do today, in the pack's plain words."""
    try:
        have_page = "## Already in your wiki" in (vault / CATALOGUE).read_text(encoding="utf-8")
    except (OSError, ValueError):
        have_page = False
    lines = [
        f"Moblee's first-week tour: today is day {day} of {TOUR_DAYS} of use of this wiki.",
        "At the end of your FIRST reply in this conversation, and only that reply, add one short "
        "line offering one thing this wiki can do. Answer what the owner asked first; the line "
        "comes after, and it is never a second question.",
        "Choose it to fit what the owner has been doing: read the last 20 entries of wiki/log.md "
        "and glance at which pages they have been working on. Read the catalogue, "
        f"`{CATALOGUE}`, and skip anything it lists as already in the wiki. Read "
        f"`{HABITS}` and skip anything under \"Said no to\" (a no stands for 90 days), "
        "anything under \"Installed, and why\", and anything a \"tour:\" line under "
        "\"Review history\" shows was already offered.",
        "Offer to SHOW it, not only to name it: \"Want me to open it and show you?\" Keep it to "
        "one line in plain words, with the reason drawn from what they did.",
        f"Then write one dated line under \"Review history\" on `{HABITS}`: "
        f"\"tour: day {day}, offered <thing>\", and add their answer when they give it. "
        "A clear no goes under \"Said no to\" with the date, as the companion does; "
        "\"not now\" is not a no.",
    ]
    if not have_page:
        lines.append("The catalogue page is not filled in yet: run "
                     "`python3 scripts/catalogue-page.py` first (it reads what is on this Mac, "
                     "changes nothing else, and writes only that page).")
    if day == 1:
        lines.append("Today is day one, so before the offer give a three-line map of the kinds "
                     "of things available (what is already in the wiki; extras added in one "
                     "press; bigger extras that open a window or cost money), and say that "
                     "\"show me everything\" lists them all.")
    if day == TOUR_DAYS:
        lines.append("This is the last day of the tour. After today you only offer when asked.")
    if assistant == "chatgpt":
        lines.append("The owner uses ChatGPT. Name only what works in ChatGPT (the wiki's own "
                     "skills, orient, ingest, the dashboard) and say plainly that Moblee's "
                     "extras are set up for Claude only for now.")
    elif assistant == "both":
        lines.append("The owner uses Claude and ChatGPT. Moblee's extras are set up for Claude "
                     "only for now; say so if what you offer is one of them.")
    lines.append("If this conversation is the companion's first conversation (\"get me "
                 "started\"), give the line at its end instead; if the weekly card is offered "
                 "today, the card takes the line's place. If the owner says \"stop the "
                 "tour\", run `python3 scripts/first-days.py --stop` and say it is stopped. "
                 "Never mention this note itself.")
    return "\n".join(lines)


def output(text: str) -> str:
    return json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart",
                                              "additionalContext": text}})


def run_hook(explicit_assistant: str | None) -> int:
    raw = ""
    try:
        raw = sys.stdin.read() if not sys.stdin.isatty() else ""
    except Exception:  # noqa: BLE001  never fail on the message
        raw = ""
    try:
        if os.environ.get("MOBLEE_NO_TOUR", "").strip():
            return 0                      # a test run (the check-up's): no tour, no day used
        vault = vault_path()
        if not (vault / "wiki" / "Index.md").is_file():
            return 0                      # not a Moblee wiki: nothing to say
        if not started_here(raw, vault):
            return 0                      # a conversation in another folder
        path = state_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        # Two conversations opened at the same moment must not both be told:
        # one holds the record while it counts, and the other, finding it held,
        # says nothing rather than wait.
        with open(lock_file(path), "a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            data = load(path)
            e = entry_for(data, str(vault))
            today = datetime.date.today().isoformat()
            before = json.dumps(e, sort_keys=True)
            day = count_today(e, today)
            if json.dumps(e, sort_keys=True) != before:
                save(path, data)          # counted first: a record that cannot be saved means silence
        if day is None:
            return 0
        text = output(instruction(day, assistant_choice(explicit_assistant), vault))
        sys.stdout.write(text + "\n")
        sys.stdout.flush()
    except Exception:  # noqa: BLE001  silent on any error, always
        return 0
    return 0


def main(argv: list[str]) -> int:
    explicit = None
    if "--assistant" in argv:
        i = argv.index("--assistant")
        explicit = argv[i + 1] if i + 1 < len(argv) else None
    if "--stop" in argv or "--status" in argv or "--preview" in argv:
        vault = vault_path()
        path = state_file()
        if "--stop" in argv:
            # Under the same lock as the hook, so a conversation starting at the
            # same moment cannot write the old record back over the stop.
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                with open(lock_file(path), "a") as lock:
                    fcntl.flock(lock, fcntl.LOCK_EX)
                    data = load(path)
                    e = entry_for(data, str(vault))
                    if e.get("done"):
                        print("The tour had already ended.")
                        return 0
                    e["done"], e["ended"] = True, datetime.date.today().isoformat()
                    save(path, data)
            except OSError:
                print("The tour's record could not be written; nothing was changed.")
                return 1
            print("The tour is stopped. From now on the assistant offers things only when asked.")
            return 0
        try:
            data = load(path)
        except OSError:
            print("The tour's record could not be read; nothing was changed.")
            return 1
        e = entry_for(data, str(vault))
        if "--preview" in argv:
            day = min(len(e["days"]) or 1, TOUR_DAYS)
            print(instruction(day, assistant_choice(explicit), vault))
            return 0
        n = len(e["days"])
        if e.get("done"):
            print(f"The tour has ended ({n} day(s) of use counted).")
        elif n == 0:
            print("The tour starts with the next conversation in this wiki.")
        else:
            print(f"Day {n} of {TOUR_DAYS} of the tour; last told {e.get('last_told') or 'never'}.")
        return 0
    return run_hook(explicit)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
