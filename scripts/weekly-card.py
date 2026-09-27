#!/usr/bin/env python3
"""weekly-card.py — the week's facts, gathered for the weekly card.

After the Saturday check has run, the assistant offers the owner one short
page about their week: what the wiki learned, what is still unresolved, and
three suggestions. This script gathers the facts that page is built from, so
the counting is done by a machine and the judgement is done by the assistant.

It reads three things and nothing else:
  * the last seven days of `wiki/log.md`, for what went in;
  * `wiki/_context.md`, for what is still open;
  * the newest report in `outputs/lint/`, for what the Saturday check found.

**It writes nothing, anywhere.** The card itself is written by the assistant,
to `outputs/weekly/YYYY-MM-DD.md`, dated for the Saturday of the check. That
file is also the record that the card has been offered: if it is already
there, the offer has been made and is not made again. This script says which
it is, so the assistant does not have to work it out.

Usage, from anywhere (the vault is found by the Moblee convention):
    python3 scripts/weekly-card.py
    python3 scripts/weekly-card.py --week 2026-09-26   # a named Saturday

Vault detection, in order of precedence:
  1. the MOBLEE_VAULT environment variable (absolute path to the vault);
  2. ~/.config/moblee/vault-path (a single line holding the absolute
     vault path — the Moblee installer writes this);
  3. walking up from the current working directory looking for a
     directory that contains wiki/Index.md.
"""
from __future__ import annotations

import datetime
import os
import re
import sys
from pathlib import Path

# How much of each list is printed before it is summed up instead.
MAX_ENTRIES = 15
MAX_ITEMS = 6
MAX_LINE = 110

MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]

LOG_HEADER = re.compile(
    r"^## \[(\d{4}-\d{2}-\d{2})[^\]]*\]\s*([\w-]+)\s*\|\s*(.+?)\s*$", re.MULTILINE
)
LINT_NAME = re.compile(r"lint-v2-(\d{4}-\d{2}-\d{2})\.md$")
SUMMARY_ROW = re.compile(r"^\|\s*(.+?)\s*\|\s*(\d+)\s*/\s*(\d+)\s*\|", re.MULTILINE)


def find_vault_root() -> Path:
    """Locate the vault. See the module docstring for the precedence order."""
    env = os.environ.get("MOBLEE_VAULT")
    if env:
        p = Path(env).expanduser()
        if (p / "wiki" / "Index.md").is_file():
            return p
        print(
            "error: MOBLEE_VAULT is set to a path that is not a Moblee vault\n"
            f"  MOBLEE_VAULT = {env}\n"
            "  A vault is a folder containing wiki/Index.md. Fix or unset the variable.",
            file=sys.stderr,
        )
        sys.exit(1)
    cfg = Path.home() / ".config" / "moblee" / "vault-path"
    if cfg.is_file():
        try:
            recorded = cfg.read_text(encoding="utf-8").strip()
        except OSError:
            recorded = ""
        if recorded:
            p = Path(recorded).expanduser()
            if (p / "wiki" / "Index.md").is_file():
                return p
            print(
                f"note: {cfg} points at {recorded}, which is not a vault "
                "(no wiki/Index.md there); falling back to searching upward "
                "from the current directory.",
                file=sys.stderr,
            )
    cur = Path.cwd()
    for candidate in [cur, *cur.parents]:
        if (candidate / "wiki" / "Index.md").is_file():
            return candidate
    print(
        "error: could not find your wiki vault.\n"
        "  Tried, in order:\n"
        "  1. the MOBLEE_VAULT environment variable (not set);\n"
        f"  2. the path recorded in {cfg} (missing or invalid);\n"
        f"  3. walking up from {cur} looking for a folder containing wiki/Index.md.\n"
        "  Fix: run this from inside your vault, or set MOBLEE_VAULT to the "
        "vault's absolute path, or re-run the Moblee installer so it records "
        "the vault path.",
        file=sys.stderr,
    )
    sys.exit(1)


def read(path: Path) -> str:
    """The file's text, or an empty string if it cannot be read."""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def long_date(d: datetime.date) -> str:
    """26 September 2026. The house form: a date a reader can say aloud."""
    return f"{d.day} {MONTHS[d.month - 1]} {d.year}"


def parse_date(text: str):
    try:
        return datetime.date(*(int(part) for part in text.split("-")))
    except (TypeError, ValueError):
        return None


def last_saturday(today: datetime.date) -> datetime.date:
    """The most recent Saturday, today included."""
    return today - datetime.timedelta(days=(today.weekday() - 5) % 7)


def newest_lint(vault: Path, not_before=None, not_after=None):
    """(date, path) of the newest dated report in outputs/lint/, or (None, None).

    With not_before set, only reports dated on or after that day are counted,
    which is how this week's check is told apart from an older one. not_after
    closes the other end. (v0.9.4) Without it, a week named with --week took the
    newest report in the vault however long after that week it had been written,
    and then called it "this week's newest reading of the vault". Catching up a
    missed week is the reason --week exists, so that was the case it was for.
    """
    folder = vault / "outputs" / "lint"
    if not folder.is_dir():
        return None, None
    best_date, best_path = None, None
    try:
        names = sorted(p.name for p in folder.iterdir() if p.is_file())
    except OSError:
        return None, None
    for name in names:
        m = LINT_NAME.search(name)
        if not m:
            continue
        d = parse_date(m.group(1))
        if d is None or (not_before is not None and d < not_before):
            continue
        if not_after is not None and d > not_after:
            continue
        if best_date is None or d > best_date:
            best_date, best_path = d, folder / name
    return best_date, best_path


def log_entries(vault: Path, start: datetime.date, end: datetime.date):
    """(entries, log_exists). Each entry is (date, type, title)."""
    log = vault / "wiki" / "log.md"
    if not log.is_file():
        return [], False
    out = []
    for m in LOG_HEADER.finditer(read(log)):
        d = parse_date(m.group(1))
        if d and start <= d <= end:
            out.append((d, m.group(2), m.group(3)))
    out.sort(key=lambda e: e[0])
    return out, True


def context_sections(vault: Path):
    """The open items on _context.md, by section name, in the page's order."""
    page = vault / "wiki" / "_context.md"
    if not page.is_file():
        return None
    wanted = [("active thread", "Active threads"),
              ("open decision", "Open decisions"),
              ("watch list", "Watch list")]
    found = {}
    heading = None
    for line in read(page).splitlines():
        if line.startswith("## "):
            title = line[3:].strip().lower()
            heading = None
            for needle, label in wanted:
                if needle in title:
                    heading = label
                    found.setdefault(label, [])
                    break
            continue
        if heading and (line.startswith("- ") or line.startswith("* ")):
            item = line[2:].strip().strip("*_ ").rstrip(".")
            if item:
                found[heading].append(item[:MAX_LINE])
    return found


def lint_issues(path: Path):
    """(rows, summary_found). Each row is (check name, number of issues)."""
    text = read(path)
    if "## Summary" not in text:
        return [], False
    table = text.split("## Summary", 1)[1]
    rows = []
    for m in SUMMARY_ROW.finditer(table):
        name, passed, total = m.group(1), int(m.group(2)), int(m.group(3))
        if total > passed:
            rows.append((name, total - passed))
    rows.sort(key=lambda r: (-r[1], r[0]))
    return rows, True


def show_list(items) -> None:
    for item in items[:MAX_ITEMS]:
        print(f"  - {item}")
    if len(items) > MAX_ITEMS:
        print(f"  - and {len(items) - MAX_ITEMS} more under that heading")


def main() -> int:
    args = sys.argv[1:]
    known = args == [] or (len(args) == 2 and args[0] == "--week")
    if not known:
        asked = any(a in ("-h", "--help") for a in args)
        print("usage: python3 scripts/weekly-card.py [--week YYYY-MM-DD]\n\n"
              "Gathers the week's facts for the weekly card: what went into the log,\n"
              "what is still open, and what the Saturday check found. It prints them\n"
              "and writes nothing. The assistant writes the card itself.",
              file=sys.stdout if asked else sys.stderr)
        return 0 if asked else 2

    vault = find_vault_root()
    today = datetime.date.today()

    # The week is always the one ending on the most recent Saturday, so there
    # is one card a week whatever day the owner comes back, and a lint anyone
    # ran by hand midweek does not move it.
    if args:
        end = parse_date(args[1])
        if end is None:
            print("error: --week wants a date written as YYYY-MM-DD, for example "
                  "--week 2026-09-26", file=sys.stderr)
            return 2
    else:
        end = last_saturday(today)
    start = end - datetime.timedelta(days=6)

    # This week's check is any report dated on or after that Saturday: the job
    # runs at 09:04 on Saturday, but a Mac that was asleep runs it when it next
    # wakes, which can be the Sunday or the Monday. (v0.9.4) It stops at the
    # Friday, because the Saturday after that belongs to the next week's card.
    # For a week ending today this changes nothing; for a past week named with
    # --week it is what stops a much later report being read as that week's.
    check_date, check_path = newest_lint(vault, not_before=end,
                                         not_after=end + datetime.timedelta(days=6))
    older_date, older_path = (None, None)
    if check_path is None:
        older_date, older_path = newest_lint(vault)

    entries, log_exists = log_entries(vault, start, end)
    card = vault / "outputs" / "weekly" / f"{end.isoformat()}.md"

    print("Weekly card facts")
    print(f"Vault: {vault}")
    print(f"Week: {long_date(start)} to {long_date(end)}")
    if end.weekday() != 5:
        print(f"Note: {long_date(end)} is not a Saturday. These are the seven days "
              "ending on it.")

    if check_path is not None and check_date == end:
        print(f"Saturday check: outputs/lint/{check_path.name}")
    elif check_path is not None:
        print(f"Saturday check: outputs/lint/{check_path.name}. It ran on "
              f"{long_date(check_date)}, not on the Saturday, so it is this week's "
              "newest reading of the vault.")
    elif older_path is not None:
        print(f"Saturday check: no report for this week. The newest is "
              f"outputs/lint/{older_path.name}, from {long_date(older_date)}.")
    else:
        print("Saturday check: no report found in outputs/lint/. The weekly check "
              "may not be switched on yet.")

    if card.is_file():
        print(f"Card: already written, at outputs/weekly/{card.name}. It has been "
              "offered once, so there is nothing to offer now.")
    else:
        print(f"Card: not written yet. It would go to outputs/weekly/{card.name}.")
    print(f"Quiet week: {'yes' if not entries else 'no'}")
    print()

    print("What the wiki learned")
    if not log_exists:
        print("  The log could not be read, so this part is unknown. Say so rather "
              "than guessing.")
    elif not entries:
        print("  Nothing was added in these seven days.")
    else:
        kinds = {}
        for _, kind, _ in entries:
            kinds[kind] = kinds.get(kind, 0) + 1
        spread = ", ".join(f"{n} {k}" for k, n in
                           sorted(kinds.items(), key=lambda kv: (-kv[1], kv[0])))
        word = "entry" if len(entries) == 1 else "entries"
        print(f"  {len(entries)} log {word}: {spread}.")
        for d, kind, title in entries[:MAX_ENTRIES]:
            print(f"  - {long_date(d)}, {kind}: {title[:MAX_LINE]}")
        if len(entries) > MAX_ENTRIES:
            print(f"  - and {len(entries) - MAX_ENTRIES} more in the log")
    print()

    print("What is unresolved")
    sections = context_sections(vault)
    if sections is None:
        print("  wiki/_context.md is not there, so nothing can be said about open "
              "work.")
    elif not sections:
        print("  wiki/_context.md has no active threads, open decisions or watch "
              "list headings.")
    else:
        for label in ("Active threads", "Open decisions", "Watch list"):
            if label not in sections:
                continue
            items = sections[label]
            if not items:
                print(f"  {label}: none listed.")
                continue
            print(f"  {label}: {len(items)}")
            show_list(items)
    print()

    print("What the Saturday check found")
    if check_path is None:
        # An older report is left unread on purpose: last month's findings put
        # in this week's card would say something untrue about this week.
        print("  No report for this week, so there is nothing to say here.")
    else:
        rows, summary = lint_issues(check_path)
        if not summary:
            print(f"  outputs/lint/{check_path.name} has no summary table, so its "
                  "findings could not be read here. Read the report itself.")
        elif not rows:
            print("  Nothing to fix.")
        else:
            for name, count in rows:
                thing = "thing" if count == 1 else "things"
                print(f"  - {name}: {count} {thing} to look at")
    return 0


if __name__ == "__main__":
    sys.exit(main())
