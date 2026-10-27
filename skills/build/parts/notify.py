#!/usr/bin/env python3
"""notify.py - one line to the owner's phone, through the ntfy app.

Made by Moblee's build skill; the same file in every thing it builds. From a
job or a script:

    from notify import notify
    notify("Tide Times", "Today's tides are ready: apps/tide-times/data/2026-10-22.json")

or from the shell:

    python3 notify.py "Tide Times" "Today's tides are ready: <the file's path>"

Rules it keeps. It sends only when the owner has chosen alerts in the Moblee
app, which leaves a topic in ~/.config/moblee/ntfy-topic; without that file it
writes the line to state/alerts-log.txt and sends nothing. It names a file's
path and never attaches the file. It never raises: a job must finish its own
work whether or not the phone can be reached, and every attempt is recorded
in state/alerts-log.txt with whether it got through. Nothing but the title and
the one line leaves the Mac.
"""
from __future__ import annotations

import datetime
import os
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
STATE = HERE / "state"
TOPIC_FILE = Path(os.path.expanduser("~")) / ".config" / "moblee" / "ntfy-topic"
SERVER = os.environ.get("MOBLEE_NTFY_SERVER", "https://ntfy.sh/")  # the test suite points this at a stand-in


def topic() -> str | None:
    try:
        t = TOPIC_FILE.read_text(encoding="utf-8").strip().splitlines()[0].strip()
    except (OSError, IndexError):
        return None
    return t if t and all(c.isalnum() or c in "-_" for c in t) and len(t) <= 64 else None


def _record(line: str) -> None:
    try:
        STATE.mkdir(parents=True, exist_ok=True)
        with open(STATE / "alerts-log.txt", "a", encoding="utf-8") as fh:
            fh.write(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S ") + line + "\n")
    except OSError:
        pass


def notify(title: str, line: str, timeout: float = 10.0) -> bool:
    """Send one line. Returns True if the phone service accepted it."""
    title = " ".join(str(title).split())[:80]
    line = " ".join(str(line).split())[:500]
    t = topic()
    if not t:
        _record(f"not sent (no alerts chosen in Moblee): {title}: {line}")
        return False
    req = urllib.request.Request(SERVER + t, data=line.encode("utf-8"), method="POST")
    req.add_header("Title", title.encode("ascii", "ignore").decode("ascii") or "Moblee")
    req.add_header("Content-Type", "text/plain; charset=utf-8")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            ok = 200 <= r.status < 300
    except Exception as exc:  # the phone being out of reach is not the job's failure
        _record(f"FAILED to send ({type(exc).__name__}): {title}: {line}")
        return False
    _record(("sent: " if ok else "refused: ") + f"{title}: {line}")
    return ok


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print('usage: python3 notify.py "Title" "One line, naming a file\'s path if there is one"')
        sys.exit(2)
    sys.exit(0 if notify(sys.argv[1], " ".join(sys.argv[2:])) else 1)
