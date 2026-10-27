#!/usr/bin/env python3
"""job.py - the scheduled part of __APP_TITLE__.

Made by Moblee's build skill. Runs by hand with

    python3 job.py

and on a schedule once the owner has loaded the launch agent beside it (the
README gives the two lines). Whatever it does, it leaves a record every time:

    state/last-run.json   when it started and finished, whether it succeeded,
                          and one line saying what happened
    state/job-log.txt     one dated line per run, appended

The check-up reads last-run.json, so a job that has quietly stopped, or keeps
failing, is seen. Keep that part exactly as it is.

Rules this file keeps, because it runs when nobody is watching and outside the
delete guard: it never deletes and never overwrites a file the owner cares
about. It appends, or writes a new dated file. If the shape of a data file must
change, the old one is kept beside the new one under a dated name.
"""
from __future__ import annotations

import datetime
import json
import sys
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
STATE = HERE / "state"


def work() -> str:
    """Do the job. Return one plain sentence saying what happened. Raise on failure.

    Fill this in. Examples of the shape:
      - read a file in data/, compute, append a row to data/history.csv
      - fetch a page (urllib), save the day's numbers as data/YYYY-MM-DD.json
      - read a secret with keychain.py (never from a file) and call a service
    """
    DATA.mkdir(parents=True, exist_ok=True)
    return "Nothing to do yet: work() has not been written."


def record(started: datetime.datetime, ok: bool, message: str) -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    finished = datetime.datetime.now()
    (STATE / "last-run.json").write_text(json.dumps({
        "started": started.isoformat(timespec="seconds"),
        "finished": finished.isoformat(timespec="seconds"),
        "ok": ok,
        "message": message,
    }, indent=2) + "\n", encoding="utf-8")
    with open(STATE / "job-log.txt", "a", encoding="utf-8") as fh:
        fh.write(f"{finished.strftime('%Y-%m-%d %H:%M:%S')} {'ok' if ok else 'FAILED'} {message}\n")


def main() -> int:
    started = datetime.datetime.now()
    try:
        message = work()
    except Exception as exc:  # the failure must be seen, never swallowed
        record(started, False, f"{type(exc).__name__}: {exc}")
        traceback.print_exc()
        return 1
    record(started, True, message)
    print(message)
    return 0


if __name__ == "__main__":
    sys.exit(main())
