#!/usr/bin/env python3
"""stamp-starter-dates.py — put the real date where the starter pages say "[Date]".

The starter's log opens with an entry headed `[YYYY-MM-DD HH:MM ±TZ]`, and its
working-state page and index say `[Date]`. Left as they are, the log's first
entry is dated "YYYY-MM-DD" for ever (the log is append-only, so nobody corrects
it later) and the dashboard shows it that way (install test, 20 September 2026).

Used by the installer, which stamps the moment of the install, and by the
updater, which corrects a wiki made before this script existed and dates it
from the wiki's first commit. Only the starter's own three placeholder lines
are touched, and only while they still hold the placeholder; a line anyone has
since written over is left as it is.

    python3 scripts/stamp-starter-dates.py --vault <path> [--from-history]
"""
from __future__ import annotations

import argparse
import datetime
import re
import subprocess
from pathlib import Path

LOG_PLACEHOLDER = re.compile(r"^## \[YYYY-MM-DD HH:MM [^\]]*\] initialised \|", re.MULTILINE)
DATE_LINE = re.compile(r"^(Last (?:refreshed|updated): )\[Date\]", re.MULTILINE)


def short_zone(moment: datetime.datetime) -> str:
    """+0100 -> +01; a zone with minutes keeps them (+0530). As log-append.py."""
    z = moment.strftime("%z")
    return z[:3] if z[3:5] in ("", "00") else z[:5]


def first_commit(vault: Path) -> datetime.datetime | None:
    try:
        r = subprocess.run(["git", "-C", str(vault), "log", "--reverse", "--format=%aI"],
                           capture_output=True, text=True, timeout=60)
        first = r.stdout.strip().splitlines()[0] if r.returncode == 0 and r.stdout.strip() else ""
        return datetime.datetime.fromisoformat(first) if first else None
    except (OSError, ValueError, IndexError, subprocess.TimeoutExpired):
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault", required=True)
    ap.add_argument("--from-history", action="store_true",
                    help="date the pages from the wiki's first commit (the updater), not from now")
    a = ap.parse_args()
    vault = Path(a.vault).expanduser().resolve()

    moment = (first_commit(vault) if a.from_history else None) or datetime.datetime.now().astimezone()
    stamp = f"{moment.strftime('%Y-%m-%d %H:%M')} {short_zone(moment)}"
    day = moment.strftime("%-d %B %Y")

    jobs = [
        (vault / "wiki" / "log.md", LOG_PLACEHOLDER, f"## [{stamp}] initialised |"),
        (vault / "wiki" / "_context.md", DATE_LINE, rf"\g<1>{day}"),
        (vault / "wiki" / "Index.md", DATE_LINE, rf"\g<1>{day}"),
    ]
    done = []
    for path, pattern, replacement in jobs:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        new, n = pattern.subn(replacement, text, count=1)
        if n:
            path.write_text(new, encoding="utf-8")
            done.append(path.name)
    print("dated: " + ", ".join(done) if done else "starter dates already filled in; nothing changed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
