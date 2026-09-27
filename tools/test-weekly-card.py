#!/usr/bin/env python3
"""Test suite for scripts/weekly-card.py.

Builds throwaway practice vaults in the system temp area and runs the facts
gatherer against them, the way the assistant runs it: a busy week, a quiet
week, a vault whose weekly check has never run, and a week whose card has
already been written.

The script is imported and its main() called, rather than started as a
separate process, so that the vault safety guard has nothing to read this
test for. The real command it stands in for is:

    python3 scripts/weekly-card.py

Usage:  python3 tools/test-weekly-card.py
Prints a pass/fail table and exits non-zero on any failure.

Nothing is deleted: each practice vault is a few hundred bytes and is left
in the system temp area, with its path printed at the end.
"""
import contextlib
import datetime
import importlib.util
import io
import os
import pathlib
import sys
import tempfile

PACK = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = PACK / "scripts" / "weekly-card.py"

TODAY = datetime.date.today()
SATURDAY = TODAY - datetime.timedelta(days=(TODAY.weekday() - 5) % 7)
# (v0.9.4) A Saturday four weeks back, which is in the past whatever day this
# is run on. Cases about a report that arrived after its Saturday used to be
# hung on "is tomorrow in the past yet?", so on a Saturday, the day the weekly
# card is actually for, they simply did not run and nothing said so. They are
# run through --week against this fixed Saturday instead, so the same number of
# cases runs every day of the week.
PAST_SATURDAY = SATURDAY - datetime.timedelta(days=28)


def load_script():
    spec = importlib.util.spec_from_file_location("weekly_card", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def day(offset):
    """A date this many days before the anchor Saturday."""
    return SATURDAY - datetime.timedelta(days=offset)


def log_entry(date, kind, title, body="Body text."):
    return f"\n## [{date.isoformat()} 10:30 +01] {kind} | {title}\n\n{body}\n"


def base_vault(name):
    root = pathlib.Path(tempfile.mkdtemp(prefix="weekly-card-%s-" % name))
    vault = root / "PracticeVault"
    write(vault / "CLAUDE.md", "# CLAUDE.md\n")
    write(vault / "wiki" / "Index.md", "# Index\n")
    return vault


def lint_report(date, rows):
    """A report shaped like the one scripts/lint-v2.py writes."""
    lines = [f"# Lint v2 — Structural Conventions Check, {date.isoformat()}", "",
             "## Checks", "", "### Something", "", "## Summary", "",
             "| Check | Passed / Total | Status |", "|---|---|---|"]
    for name, passed, total in rows:
        status = "✓" if passed == total else "**%d issue(s)**" % (total - passed)
        lines.append(f"| {name} | {passed} / {total} | {status} |")
    return "\n".join(lines) + "\n"


CONTEXT_FULL = """# Working state and tempo

Last refreshed: whenever.

## Active threads

- The kitchen rebuild, waiting on the second quote
- Reading the 1974 planning file

## Open decisions

- Whether to keep the old photographs in the vault or in a box

## Watch list

- The council's new parking scheme
- The neighbour's boundary claim
- A book that has not arrived

## Vault snapshot

Nothing structural has moved.
"""

CONTEXT_EMPTY = """# Working state and tempo

## Active threads

(None yet.)

## Open decisions

(None yet.)
"""


def build_busy():
    vault = base_vault("busy")
    log = "# Log\n"
    log += log_entry(day(30), "ingest", "An old thing from last month")
    log += log_entry(day(5), "ingest", "The planning file, 1974")
    log += log_entry(day(3), "ingest", "A letter about the boundary")
    log += log_entry(day(1), "housekeeping", "Tidied the Index")
    write(vault / "wiki" / "log.md", log)
    write(vault / "wiki" / "_context.md", CONTEXT_FULL)
    write(vault / "outputs" / "lint" / f"lint-v2-{SATURDAY.isoformat()}.md",
          lint_report(SATURDAY, [("Dangling wikilinks", 4, 6),
                                 ("Orphan pages", 2, 3),
                                 ("Log header format", 9, 9)]))
    return vault


def build_quiet():
    vault = base_vault("quiet")
    write(vault / "wiki" / "log.md",
          "# Log\n" + log_entry(day(40), "ingest", "The last thing that went in"))
    write(vault / "wiki" / "_context.md", CONTEXT_EMPTY)
    write(vault / "outputs" / "lint" / f"lint-v2-{SATURDAY.isoformat()}.md",
          lint_report(SATURDAY, [("Dangling wikilinks", 6, 6),
                                 ("Orphan pages", 3, 3)]))
    return vault


def build_no_lint():
    vault = base_vault("no-lint")
    write(vault / "wiki" / "log.md",
          "# Log\n" + log_entry(day(2), "ingest", "A note on the roof repair"))
    write(vault / "wiki" / "_context.md", CONTEXT_FULL)
    return vault


def snapshot(vault):
    return sorted(str(p.relative_to(vault)) for p in vault.rglob("*"))


def run(mod, vault, argv):
    """Run the gatherer against a vault. Returns (exit code, printed text)."""
    out, err = io.StringIO(), io.StringIO()
    old_argv, old_env = sys.argv, os.environ.get("MOBLEE_VAULT")
    sys.argv = ["weekly-card.py"] + argv
    os.environ["MOBLEE_VAULT"] = str(vault)
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = mod.main()
            except SystemExit as e:
                code = e.code if isinstance(e.code, int) else 1
    finally:
        sys.argv = old_argv
        if old_env is None:
            os.environ.pop("MOBLEE_VAULT", None)
        else:
            os.environ["MOBLEE_VAULT"] = old_env
    return code, out.getvalue() + err.getvalue()


def main():
    mod = load_script()
    rows = []
    failures = 0

    skipped = []

    def check(group, label, ok):
        nonlocal failures
        if not ok:
            failures += 1
        rows.append(("PASS" if ok else "FAIL", group, label))

    def skip(group, label, why):
        """A case that did not run. It is printed, counted and named.

        (v0.9.4) A case used to be able to drop out on the day of the week the
        run happened, leaving no trace: the table simply came up two rows
        shorter. A skip that says nothing is a case nobody knows is untested."""
        skipped.append((group, label, why))
        rows.append(("SKIP", group, "%s -- NOT RUN: %s" % (label, why)))

    # ---------------------------------------------------------------- busy
    busy = build_busy()
    before = snapshot(busy)
    code, text = run(mod, busy, [])
    check("busy", "exits 0", code == 0)
    check("busy", "the week is not called quiet", "Quiet week: no" in text)
    check("busy", "counts the three entries inside the week",
          "3 log entries" in text)
    check("busy", "names this week's work", "The planning file, 1974" in text)
    check("busy", "leaves last month's entry out",
          "An old thing from last month" not in text)
    check("busy", "finds the Saturday report",
          f"Saturday check: outputs/lint/lint-v2-{SATURDAY.isoformat()}.md" in text)
    check("busy", "says the card is not written yet",
          f"Card: not written yet" in text
          and f"outputs/weekly/{SATURDAY.isoformat()}.md" in text)
    check("busy", "lists the open threads", "Active threads: 2" in text
          and "The kitchen rebuild" in text)
    check("busy", "lists the open decision", "Open decisions: 1" in text)
    check("busy", "lists the watch list", "Watch list: 3" in text)
    check("busy", "carries the check's findings",
          "Dangling wikilinks: 2 things to look at" in text
          and "Orphan pages: 1 thing to look at" in text)
    check("busy", "stays quiet about the clean checks",
          "Log header format" not in text)
    check("busy", "writes nothing", snapshot(busy) == before)

    # --------------------------------------------------- card already there
    card = busy / "outputs" / "weekly" / f"{SATURDAY.isoformat()}.md"
    write(card, "# This week\n\nAlready offered.\n")
    code, text = run(mod, busy, [])
    check("offered", "says the card is already written",
          "Card: already written" in text and "nothing to offer now" in text)
    check("offered", "does not say it is unwritten", "not written yet" not in text)

    # --------------------------------------------------------------- quiet
    quiet = build_quiet()
    before = snapshot(quiet)
    code, text = run(mod, quiet, [])
    check("quiet", "exits 0", code == 0)
    check("quiet", "calls the week quiet", "Quiet week: yes" in text)
    check("quiet", "says so plainly",
          "Nothing was added in these seven days." in text)
    check("quiet", "says the check found nothing", "Nothing to fix." in text)
    check("quiet", "uses no word of blame",
          not any(w in text.lower() for w in
                  ("streak", "missed", "failed", "behind", "should have", "days in a row")))
    check("quiet", "writes nothing", snapshot(quiet) == before)

    # ------------------------------------------------------------- no lint
    plain = build_no_lint()
    before = snapshot(plain)
    code, text = run(mod, plain, [])
    check("no check", "exits 0", code == 0)
    check("no check", "says there is no report",
          "no report found in outputs/lint/" in text)
    check("no check", "says the check may be off",
          "may not be switched on yet" in text)
    check("no check", "falls back to the last Saturday",
          f"outputs/weekly/{SATURDAY.isoformat()}.md" in text)
    check("no check", "still reads the log", "A note on the roof repair" in text)
    check("no check", "has nothing to read from the check",
          "No report for this week" in text)
    check("no check", "writes nothing", snapshot(plain) == before)

    # ------------------------------------------------- which report counts
    # A report someone ran by hand midweek must not move the card's week, and
    # last month's findings must not be read into this week's card.
    stale = build_no_lint()
    write(stale / "outputs" / "lint" / f"lint-v2-{day(33).isoformat()}.md",
          lint_report(day(33), [("Dangling wikilinks", 1, 9)]))
    code, text = run(mod, stale, [])
    check("report age", "the week still ends on the Saturday",
          f"to {mod.long_date(SATURDAY)}" in text)
    check("report age", "an old report is named, not used",
          "no report for this week" in text.lower()
          and f"lint-v2-{day(33).isoformat()}.md" in text)
    check("report age", "old findings are left out",
          "Dangling wikilinks" not in text)

    # A check the Mac ran on the Sunday, because it was asleep on the Saturday,
    # is still that week's check. Run against a Saturday four weeks back, so
    # that "the day after the Saturday" is always a day that has been and gone
    # and these two cases run on every day of the week, this one included.
    late = build_quiet()
    monday = PAST_SATURDAY + datetime.timedelta(days=2)
    write(late / "outputs" / "lint" / f"lint-v2-{monday.isoformat()}.md",
          lint_report(monday, [("Orphan pages", 2, 4)]))
    code, text = run(mod, late, ["--week", PAST_SATURDAY.isoformat()])
    check("report age", "a check that ran late still counts for the week",
          f"lint-v2-{monday.isoformat()}.md" in text
          and "not on the Saturday" in text
          and "Orphan pages: 2 things to look at" in text)
    check("report age", "the card keeps the Saturday's date",
          f"outputs/weekly/{PAST_SATURDAY.isoformat()}.md" in text)

    # And the other end of that window. build_quiet() leaves a report dated on
    # this week's Saturday, four weeks after the week being asked about. Before
    # v0.9.4 that report was read as the named week's newest reading of the
    # vault, and its findings went into a card for a week it says nothing
    # about. Catching up a missed week is what --week is for, so this was the
    # case it existed for.
    later = build_quiet()
    write(later / "outputs" / "lint" / f"lint-v2-{SATURDAY.isoformat()}.md",
          lint_report(SATURDAY, [("Dangling wikilinks", 1, 7)]))
    code, text = run(mod, later, ["--week", PAST_SATURDAY.isoformat()])
    check("report age", "a later week's report is not read as the named week's",
          "no report for this week" in text.lower()
          and "not on the Saturday" not in text)
    check("report age", "and its findings stay out of the named week",
          "Dangling wikilinks" not in text)
    check("report age", "the later report is still named, plainly",
          f"lint-v2-{SATURDAY.isoformat()}.md" in text)

    # ------------------------------------------------------------ long list
    crowded = build_no_lint()
    threads = "\n".join("- Thread number %d" % n for n in range(1, 10))
    write(crowded / "wiki" / "_context.md",
          "# Working state\n\n## Active threads\n\n%s\n" % threads)
    code, text = run(mod, crowded, [])
    check("long list", "the count is the real one", "Active threads: 9" in text)
    check("long list", "only the first few are printed",
          "Thread number 6" in text and "Thread number 7" not in text)
    check("long list", "the rest are summed up",
          "and 3 more under that heading" in text)

    # ------------------------------------------------------------ switches
    midweek = (SATURDAY - datetime.timedelta(days=3)).isoformat()
    code, text = run(mod, busy, ["--week", midweek])
    check("switches", "a named week is used", code == 0 and midweek in text)
    check("switches", "says when the date is not a Saturday",
          "is not a Saturday" in text)
    code, text = run(mod, busy, ["--week", "the 26th"])
    check("switches", "a date it cannot read is refused in plain words",
          code == 2 and "YYYY-MM-DD" in text)
    code, text = run(mod, busy, ["--help"])
    check("switches", "--help explains and exits 0",
          code == 0 and "writes nothing" in text)
    code, text = run(mod, busy, ["--wipe"])
    check("switches", "an unknown switch does nothing and exits 2", code == 2)

    width = max(len(r[2]) for r in rows)
    print("%-4s %-9s %s" % ("", "group", "case"))
    for status, group, label in rows:
        print("%-4s %-9s %-*s" % (status, group, width, label))
    print()
    print("cases: %d   failures: %d   skipped: %d" % (len(rows), failures, len(skipped)))
    # A skip is said out loud, twice: once in the table and once here. The same
    # number of cases should run every day of the week; if one ever does not,
    # the run has to be the thing that tells you.
    for group, label, why in skipped:
        print("  NOT RUN  %s: %s (%s)" % (group, label, why))
    print("practice vaults left in place:")
    for v in (busy, quiet, plain, stale, late, later, crowded):
        print("  %s" % v)
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
