#!/usr/bin/env python3
"""
Tests for scripts/lint-v2.py, the read-only structure check.

    python3 tools/test-lint-v2.py

The groups:

  warn      The warning band on the always-loaded files. A file that has
            reached 95 per cent of its limit is reported as getting close,
            in words that say plainly that nothing is broken yet; a file at
            80 per cent is not mentioned that way at all; and a file over
            its limit still fails exactly as it did before. The 95 per cent
            mark itself counts as close, and the wording carries the real
            figures rather than a hard-coded cap.
  missing   An always-loaded file that is not there. It is named as a
            missing file instead of being passed over in silence, and it is
            still counted, so a wiki with a file astray cannot come back
            all-clean. A file that is there but cannot be opened is told
            apart from one that is absent.
  crash     A check that fails with an error of its own. It is written into
            the report as one issue, the error is named, and every other
            check still runs and the report is still written — the thing
            that used to leave the owner with no report at all. Proved two
            ways: on the helper directly, and on a whole run with two
            checks forced to fail.

Everything is built under $TMPDIR, in a practice wiki copied from the pack's
own vault-template. Nothing is deleted, here or anywhere: the practice wikis
are left where they are (a few kilobytes) and named at the end.

The check is loaded as a module rather than started as a program, so the
tests run the same code without starting a second process, and HOME is
pointed at a throwaway folder for every run: two of the checks look in the
home folder for installed skills, and no test may read the real one.

Prints a pass/fail table and exits non-zero on any failure.
"""
import contextlib
import datetime
import importlib.util
import io
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACK = HERE.parent
LINT = PACK / "scripts" / "lint-v2.py"
TEMPLATE = PACK / "vault-template"

ROWS = []
FAILURES = 0


def check(group, label, passed, note=""):
    global FAILURES
    if not passed:
        FAILURES += 1
    ROWS.append(("PASS" if passed else "FAIL", group, label, note))
    return passed


def load_lint():
    """Load the check as a module. Starting it as a program would work too,
    but importing it runs exactly the same code with no second process, and
    lets a test replace one check with one that fails on purpose."""
    spec = importlib.util.spec_from_file_location("lint_v2", LINT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_wiki(root):
    """A practice wiki, copied from the pack's own template so it is the real
    shape of an owner's wiki and not a stub."""
    shutil.copytree(TEMPLATE, root)
    return root


def sandbox_home(work, name):
    """A throwaway home folder, so no test reads this Mac's own."""
    home = work / f"home-{name}"
    (home / ".claude" / "skills").mkdir(parents=True, exist_ok=True)
    return home


def write_tokens(path, header, tokens, module):
    """Write a file whose estimated weight is exactly `tokens`.

    The estimate the check uses is characters divided by four, so the file is
    filled to exactly that many characters. The filler lines are short on
    purpose: a long line in _context.md would set off the separate per-item
    budget guard and muddy what is being measured here.
    """
    want = tokens * module.CHARS_PER_TOKEN
    body = header.rstrip("\n") + "\n"
    line = "- A short filler line, written to give the file some weight.\n"
    while len(body) + len(line) <= want:
        body += line
    body += "x" * (want - len(body))
    assert len(body) == want, (len(body), want)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def weight_findings(module, vault, home):
    """Run the weight check alone against one practice wiki, and hand back its
    (passed, total) score and the lines it wrote."""
    findings = []
    old_home, old_vault = os.environ.get("HOME"), os.environ.get("MOBLEE_VAULT")
    os.environ["HOME"] = str(home)
    os.environ["MOBLEE_VAULT"] = str(vault)
    try:
        score = module.check_vault_weight(vault, findings)
    finally:
        if old_home is not None:
            os.environ["HOME"] = old_home
        if old_vault is not None:
            os.environ["MOBLEE_VAULT"] = old_vault
    return score, findings


def line_for(findings, rel):
    """The one reported line about a named file."""
    for line in findings:
        if line.startswith(f"- `{rel}`"):
            return line
    return ""


def run_lint(module, vault, home, out):
    """A whole run, with the wiki and the home folder both pointed at
    throwaway copies. Hands back the exit code, what was printed, what went to
    the error stream, and the report that was written."""
    old = {k: os.environ.get(k) for k in ("HOME", "MOBLEE_VAULT")}
    os.environ["HOME"] = str(home)
    os.environ["MOBLEE_VAULT"] = str(vault)
    old_argv = sys.argv
    sys.argv = ["lint-v2.py", "--out", str(out)]
    said, erred = io.StringIO(), io.StringIO()
    try:
        with contextlib.redirect_stdout(said), contextlib.redirect_stderr(erred):
            code = module.main()
    finally:
        sys.argv = old_argv
        for k, v in old.items():
            if v is not None:
                os.environ[k] = v
    report = out.read_text(encoding="utf-8") if out.is_file() else ""
    return code, said.getvalue(), erred.getvalue(), report


# --------------------------------------------------------------- the warning band
def test_warn(module, work):
    """Three files in one wiki, at three different fractions of their limits."""
    vault = build_wiki(work / "warn-wiki" / "Practice Wiki")
    home = sandbox_home(work, "warn")

    # 96 per cent of its limit: the band must fire.
    close = int(module.INDEX_TOKEN_CAP * 0.96)
    write_tokens(vault / "wiki" / "Index.md", "# Index\n\n## Domains\n", close, module)
    # 80 per cent: comfortably inside, and must not be mentioned as close.
    easy = int(module.CLAUDE_MD_TOKEN_CAP * 0.80)
    write_tokens(vault / "CLAUDE.md", "# Rules for this practice wiki\n", easy, module)
    # 110 per cent: over, and must fail exactly as it did before the band existed.
    over = int(module.CONTEXT_TOKEN_CAP * 1.10)
    write_tokens(vault / "wiki" / "_context.md", "# Context\n", over, module)

    (passed, total), findings = weight_findings(module, vault, home)

    close_line = line_for(findings, "wiki/Index.md")
    easy_line = line_for(findings, "CLAUDE.md")
    over_line = line_for(findings, "wiki/_context.md")

    check("warn", "a file at 96% of its limit is reported as getting close to it",
          "getting close to its" in close_line, close_line[:110])
    check("warn", "and the warning says in plain words that nothing is broken yet",
          "Nothing is broken" in close_line and "still loads normally" in close_line)
    check("warn", "and it carries the file's own weight, its limit, and how far along it is",
          f"{close:,} tok" in close_line and f"{module.INDEX_TOKEN_CAP:,} limit" in close_line
          and "96%" in close_line)
    check("warn", "and it names the share the warning starts at, taken from the setting",
          f"starts at {module.CAP_WARN_FRACTION:.0%}" in close_line)
    check("warn", "a file at 80% of its limit is not called close to anything",
          "getting close" not in easy_line and "under the" in easy_line and "✓" in easy_line,
          easy_line[:110])
    check("warn", "a file over its limit still fails, in the words it always used",
          "over the" in over_line and "run the `compact` skill" in over_line
          and "getting close" not in over_line, over_line[:110])
    check("warn", "the close file and the over file both count as issues, the easy one does not",
          (passed, total) == (2, 4), f"{passed} / {total}")

    # The band is an at-or-above test, so the mark itself must count as close.
    edge = work / "edge-wiki" / "Practice Wiki"
    build_wiki(edge)
    exact = int(module.INDEX_TOKEN_CAP * module.CAP_WARN_FRACTION)
    write_tokens(edge / "wiki" / "Index.md", "# Index\n\n## Domains\n", exact, module)
    _, edge_findings = weight_findings(module, edge, sandbox_home(work, "edge"))
    check("warn", "exactly 95% of the limit counts as getting close",
          "getting close to its" in line_for(edge_findings, "wiki/Index.md"),
          f"{exact:,} tok of {module.INDEX_TOKEN_CAP:,}")

    # One below the mark must not warn, which is what makes the band a band.
    under = work / "under-wiki" / "Practice Wiki"
    build_wiki(under)
    write_tokens(under / "wiki" / "Index.md", "# Index\n\n## Domains\n", exact - 1, module)
    _, under_findings = weight_findings(module, under, sandbox_home(work, "under"))
    check("warn", "one token below the mark does not warn",
          "getting close" not in line_for(under_findings, "wiki/Index.md"),
          f"{exact - 1:,} tok of {module.INDEX_TOKEN_CAP:,}")

    # The instruction file's limit is the pack's own 16,000, which the commit
    # gate refuses on the same figure. A file at the vault-side 10,000 must
    # therefore be nowhere near its limit here.
    check("warn", "the instruction file's limit is the pack's 16,000",
          module.CLAUDE_MD_TOKEN_CAP == 16_000, f"{module.CLAUDE_MD_TOKEN_CAP:,}")

    # And the band must show up in a whole run too, not only when the weight
    # check is called on its own.
    code, _, _, report = run_lint(
        module, vault, home, work / "warn-report.md")
    check("warn", "a whole run puts the warning in the written report",
          code == 0 and "getting close to its" in report)


# ------------------------------------------------------------- the missing input
def test_missing(module, work):
    """An always-loaded file that is not there, and one that cannot be opened."""
    vault = work / "missing-wiki" / "Practice Wiki"
    home = sandbox_home(work, "missing")
    # Built by hand rather than copied, so _context.md is simply never written:
    # nothing is deleted to make this case.
    (vault / "wiki").mkdir(parents=True)
    (vault / "wiki" / "Index.md").write_text("# Index\n\n## Domains\n", encoding="utf-8")
    (vault / "CLAUDE.md").write_text("# Rules for this practice wiki\n", encoding="utf-8")
    (vault / "wiki" / "log.md").write_text("# Log\n", encoding="utf-8")

    (passed, total), findings = weight_findings(module, vault, home)
    missing_line = line_for(findings, "wiki/_context.md")

    check("missing", "a missing always-loaded file is named as missing",
          "this file is missing" in missing_line, missing_line[:120])
    check("missing", "and the owner is told why that matters, not just that it happened",
          "Every session expects it to be there" in missing_line
          and "this part of the report is incomplete" in missing_line)
    check("missing", "and it is still counted, so the run cannot come back all-clean",
          (passed, total) == (3, 4), f"{passed} / {total}")
    check("missing", "the present files beside it are still measured normally",
          "✓" in line_for(findings, "wiki/Index.md")
          and "✓" in line_for(findings, "CLAUDE.md"))

    # A file that is there but cannot be opened is a different fault, and must
    # read differently: it is listed among the read failures, not as absent.
    shut = work / "unreadable-wiki" / "Practice Wiki"
    build_wiki(shut)
    locked = shut / "wiki" / "_context.md"
    locked.chmod(0o000)
    try:
        (p2, t2), f2 = weight_findings(module, shut, sandbox_home(work, "unreadable"))
        locked_line = line_for(f2, "wiki/_context.md")
    finally:
        locked.chmod(0o644)
    check("missing", "a file that cannot be opened is told apart from one that is absent",
          "could not be read" in locked_line and "this file is missing" not in locked_line,
          locked_line[:120])
    check("missing", "and it is pointed at the read-failure list rather than passed",
          "READ FAILURES" in locked_line and (p2, t2) == (3, 4), f"{p2} / {t2}")

    # And the whole run must still write a report and still report the issue.
    code, said, _, report = run_lint(
        module, vault, home, work / "missing-report.md")
    check("missing", "a whole run over that wiki writes a report and reports the issue",
          code == 0 and "this file is missing" in report
          and "All checks clean." not in said)


# ----------------------------------------------------------- a check that fails
def test_crash(module, work):
    """A check that raises must become a reported issue, not the end of the run."""
    # First the helper on its own, with nothing else in the way.
    scorecard, findings = [], []

    def falls_over(vault, findings):
        raise ValueError("a planted fault, to prove this is reported")

    erred = io.StringIO()
    with contextlib.redirect_stderr(erred):
        module.run_check(scorecard, findings, "A planted check", falls_over, work, findings)

    text = "\n".join(findings)
    check("crash", "a check that raises is recorded as one issue, not as a pass",
          scorecard == [("A planted check", 0, 1)], str(scorecard))
    check("crash", "the report says the check could not finish, and names it",
          "could not finish" in text and "A planted check" in text)
    check("crash", "the error itself is quoted, so it can be reported to Moblee",
          "ValueError: a planted fault" in text)
    check("crash", "and the place it failed is given",
          bool(re.search(r"at test-lint-v2\.py:\d+", text)), text[-120:])
    check("crash", "the owner is told the rest of the report still stands",
          "Every other check ran" in text and "the rest of the report" in text)
    check("crash", "it is called a fault in Moblee, not a fault in the wiki",
          "a fault in Moblee, not in the wiki" in text)
    check("crash", "and the error stream carries it too, for anything reading the output",
          "lint-v2: a check could not finish: A planted check" in erred.getvalue(),
          erred.getvalue().strip()[:90])

    # A raise with no message at all must still produce a readable line.
    bare = []
    with contextlib.redirect_stderr(io.StringIO()):
        module.run_check([], bare, "A silent fault", lambda v, f: (_ for _ in ()).throw(KeyError()), work, bare)
    check("crash", "a fault with no message of its own still reads as English",
          "could not finish" in "\n".join(bare) and "KeyError" in "\n".join(bare))

    # Now a whole run, with two real checks forced to fail. The point is that
    # the run carries on: before this, the first one ended it with no report.
    vault = build_wiki(work / "crash-wiki" / "Practice Wiki")
    home = sandbox_home(work, "crash")
    module_again = load_lint()   # a fresh copy, so the real checks are left alone
    for name in ("check_dangling_links", "check_correction_rate"):
        def fails(vault, findings, _name=name):
            raise RuntimeError(f"a planted fault in {_name}")
        setattr(module_again, name, fails)

    out = work / "crash-report.md"
    code, said, erred2, report = run_lint(module_again, vault, home, out)

    check("crash", "the run finishes and the report is written anyway",
          out.is_file() and code == 0, f"exit {code}")
    check("crash", "both planted faults are in the report",
          report.count("could not finish") == 2, str(report.count("could not finish")))
    check("crash", "each shows as an issue in the summary table",
          "| Dangling wikilinks | 0 / 1 | **1 issue(s)** |" in report
          and "| Correction rate (informational) | 0 / 1 | **1 issue(s)** |" in report)
    check("crash", "every check after the first fault still ran",
          "| Broken section anchors |" in report
          and "| Orphan pages |" in report
          and "| Habits and tools (informational) |" in report)
    check("crash", "and the checks before it are untouched",
          "| Daily-note frontmatter | 1 / 1 | ✓ |" in report)
    check("crash", "the run does not claim to be clean",
          "All checks clean." not in said and "2 issue(s) across checks" in said,
          said.strip().splitlines()[-1][:80] if said.strip() else "")
    check("crash", "both faults reach the error stream too",
          erred2.count("lint-v2: a check could not finish") == 2,
          str(erred2.count("lint-v2: a check could not finish")))
    check("crash", "a wiki with nothing wrong in it is still reported clean",
          run_lint(load_lint(), build_wiki(work / "clean-wiki" / "Practice Wiki"),
                   sandbox_home(work, "clean"), work / "clean-report.md")[1]
          .endswith("All checks clean.\n"))


def main():
    work = Path(tempfile.mkdtemp(prefix="moblee-lint-test-",
                                 dir=os.environ.get("TMPDIR") or None))
    module = load_lint()
    print(f"Testing {LINT}")
    print(f"Working folder: {work}\n")
    test_warn(module, work)
    test_missing(module, work)
    test_crash(module, work)

    width = max(len(r[2]) for r in ROWS)
    print("%-4s %-8s %-*s %s" % ("", "group", width, "case", "note"))
    for status, group, label, note in ROWS:
        print("%-4s %-8s %-*s %s" % (status, group, width, label, note))
    print("")
    print("%d passed, %d failed, of %d." % (len(ROWS) - FAILURES, FAILURES, len(ROWS)))
    print("Practice wikis are left in %s" % work)
    print("Run on %s" % datetime.date.today().isoformat())
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
