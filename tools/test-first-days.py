#!/usr/bin/env python3
"""Test suite for scripts/first-days.py, the first-week tour (0.16.0).

Builds throwaway practice wikis and a throwaway home folder in the system temp
area and runs the tour the way Claude's SessionStart hook runs it: days of use
across dates (a week away is not a day), an older wiki starting its tour on
the day it is first used, "stop the tour", once a day and not every
conversation, the ChatGPT wording, every error kept silent, and a real run as
a separate program to show it is quick and never blocks.

It also checks the two pieces around the script: safety/install-safety.py
registers it as a SessionStart hook for Claude by its full path, once, keeping
every hook already there; and scripts/patch-claude-md.py gives an orient
section the owner has edited the day's Plan rule by addition.

The scripts are imported and their main() called, so that the vault safety
guard has nothing to read this test for; one case starts the tour as a
separate program on purpose, because "never blocks" is about the real thing.

Usage:  python3 tools/test-first-days.py
Prints a pass/fail table and exits non-zero on any failure. Nothing is
deleted: the practice folders are left in the temp area, paths printed.
"""
import contextlib
import datetime
import fcntl
import importlib.util
import io
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time

PACK = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = PACK / "scripts" / "first-days.py"
ROOT = pathlib.Path(tempfile.mkdtemp(prefix="first-days-test-"))
HOME = ROOT / "home"
HOME.mkdir()

rows, failures = [], 0


def check(group, label, ok, detail=""):
    global failures
    rows.append(("ok" if ok else "FAIL", group, label + ("" if ok or not detail else f" ({detail})")))
    if not ok:
        failures += 1


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def wiki(name, catalogue=False):
    v = ROOT / name
    (v / "wiki" / "Wiki Operations").mkdir(parents=True)
    (v / "wiki" / "Index.md").write_text("# Index\n")
    (v / "CLAUDE.md").write_text("# CLAUDE.md\n")
    if catalogue:
        (v / "wiki" / "Wiki Operations" / "What Your Wiki Can Do.md").write_text(
            "---\ngenerated_by: moblee catalogue-page\n---\n\n## Already in your wiki\n")
    return v.resolve()


class FakeDate(datetime.date):
    current = datetime.date(2026, 11, 2)

    @classmethod
    def today(cls):
        return cls.current


class FakeDatetime:
    date = FakeDate


def run(mod, vault, on, argv=(), state=None, assistant=None):
    """One conversation starting in `vault` on date `on`: (exit code, stdout)."""
    FakeDate.current = on
    mod.datetime = FakeDatetime
    os.environ["MOBLEE_VAULT"] = str(vault)
    os.environ["MOBLEE_FIRST_DAYS_STATE"] = str(state or (ROOT / "state.json"))
    if assistant:
        (HOME / ".config" / "moblee").mkdir(parents=True, exist_ok=True)
        (HOME / ".config" / "moblee" / "assistant").write_text(assistant + "\n")
    out = io.StringIO()
    old_stdin = sys.stdin
    sys.stdin = io.StringIO(json.dumps({"hook_event_name": "SessionStart", "source": "startup",
                                        "cwd": str(vault)}))
    try:
        with contextlib.redirect_stdout(out):
            code = mod.main(list(argv))
    finally:
        sys.stdin = old_stdin
    return code, out.getvalue()


def context(text):
    try:
        obj = json.loads(text)
        hs = obj["hookSpecificOutput"]
        return hs["additionalContext"] if hs.get("hookEventName") == "SessionStart" else None
    except (ValueError, KeyError, TypeError):
        return None


def d(n):
    return datetime.date(2026, 11, 2) + datetime.timedelta(days=n)


def main():
    os.environ["HOME"] = str(HOME)
    mod = load(SCRIPT, "first_days")
    state = ROOT / "state.json"

    # ----- days of use, across dates
    v = wiki("Counting")
    code, out = run(mod, v, d(0))
    ctx = context(out)
    check("days", "the first conversation in a new wiki is day 1", ctx is not None and "day 1 of 5" in ctx, out[:120])
    check("days", "and exits 0", code == 0)
    check("days", "the output is one JSON object, SessionStart's additionalContext shape",
          out.strip().startswith("{") and out.strip().count("\n") == 0 and ctx is not None)
    check("days", "day one carries the three-line map and 'show me everything'",
          ctx is not None and "three-line map" in ctx and "show me everything" in ctx)
    check("days", "it asks for the line at the end of the first reply only",
          ctx is not None and "FIRST reply" in ctx and "only that reply" in ctx)
    check("days", "it asks to show, not only to name", ctx is not None and "show you" in ctx)
    check("days", "it names Said no to, Review history and the catalogue page",
          ctx is not None and "Said no to" in ctx and "Review history" in ctx
          and "What Your Wiki Can Do.md" in ctx)
    code, out = run(mod, v, d(0))
    check("once", "a second conversation the same day hears nothing", code == 0 and out == "", out[:80])
    code, out = run(mod, v, d(1))
    check("days", "the next date is day 2", "day 2 of 5" in (context(out) or ""))
    check("days", "and day 2 has no map", "three-line map" not in (context(out) or "x"))
    code, out = run(mod, v, d(9))
    check("days", "a week away is not counted: the next day used is day 3", "day 3 of 5" in (context(out) or ""))
    run(mod, v, d(10))
    code, out = run(mod, v, d(12))
    ctx = context(out) or ""
    check("days", "the fifth day of use is day 5", "day 5 of 5" in ctx)
    check("days", "and says the tour ends today", "last day of the tour" in ctx)
    code, out = run(mod, v, d(13))
    check("days", "a sixth day of use hears nothing", code == 0 and out == "")
    rec = json.loads(state.read_text())["wikis"][str(v)]
    check("days", "and the record says the tour is done, five days counted",
          rec["done"] is True and len(rec["days"]) == 5, json.dumps(rec))
    code, out = run(mod, v, d(40))
    check("days", "and nothing ever again", out == "")

    # ----- an older wiki: no record when 0.16 arrives
    older = wiki("Older")
    code, out = run(mod, older, d(20))
    check("existing", "a wiki with no record starts its tour the day it is first used",
          "day 1 of 5" in (context(out) or ""))
    recs = json.loads(state.read_text())["wikis"]
    check("existing", "each wiki keeps its own record, by its resolved path",
          str(v) in recs and str(older) in recs and recs[str(older)]["days"] == [d(20).isoformat()])

    # ----- stop the tour
    stopper = wiki("Stopper")
    run(mod, stopper, d(0))
    code, out = run(mod, stopper, d(0), ["--stop"])
    check("stop", "--stop says the tour is stopped", code == 0 and "stopped" in out, out)
    code, out = run(mod, stopper, d(1))
    check("stop", "the next day of use hears nothing", out == "")
    code, out = run(mod, stopper, d(1), ["--stop"])
    check("stop", "a second --stop says it had already ended", "already ended" in out)
    code, out = run(mod, stopper, d(1), ["--status"])
    check("stop", "--status says it has ended", "ended" in out)
    fresh = wiki("Fresh")
    code, out = run(mod, fresh, d(0), ["--status"])
    check("stop", "--status on a wiki with no record says it starts next time, and counts nothing",
          "starts with the next conversation" in out
          and str(fresh) not in json.loads(state.read_text())["wikis"])

    # ----- the assistant's wording
    cg = wiki("ChatGPTWiki")
    code, out = run(mod, cg, d(0), assistant="chatgpt")
    ctx = context(out) or ""
    check("wording", "ChatGPT: name only what works there", "Name only what works in ChatGPT" in ctx)
    check("wording", "ChatGPT: say the extras are Claude only for now", "Claude only for now" in ctx)
    both = wiki("BothWiki")
    code, out = run(mod, both, d(0), assistant="both")
    ctx = context(out) or ""
    check("wording", "both: the extras are named as Claude's only", "Claude only for now" in ctx
          and "Name only what works in ChatGPT" not in ctx)
    cl = wiki("ClaudeWiki")
    code, out = run(mod, cl, d(0), assistant="claude")
    check("wording", "Claude alone: no ChatGPT sentence", "ChatGPT" not in (context(out) or "ChatGPT"))
    check("wording", "a catalogue not yet filled in: run catalogue-page.py first",
          "catalogue-page.py" in (context(out) or ""))
    filled = wiki("Filled", catalogue=True)
    code, out = run(mod, filled, d(0), assistant="claude")
    check("wording", "a filled-in catalogue: no such step", "catalogue-page.py` first" not in (context(out) or "x"))
    check("wording", "the note is well inside the 10,000-character cap on hook context",
          len(context(out) or "") < 4000, str(len(context(out) or "")))

    # ----- silent on every error
    plain = ROOT / "NotAWiki"
    plain.mkdir()
    other_state = ROOT / "state-notawiki.json"
    code, out = run(mod, plain, d(0), state=other_state)
    check("errors", "a folder that is not a Moblee wiki: nothing said, nothing written",
          code == 0 and out == "" and not other_state.exists())
    broken = ROOT / "state-broken.json"
    broken.write_text("{ this is not json")
    code, out = run(mod, wiki("Broken"), d(0), state=broken)
    # (0.16.0 review) a damaged record is started afresh, not left silent for good
    check("errors", "a record that cannot be read starts afresh: day one is told, exit 0",
          code == 0 and context(out) is not None and json.loads(broken.read_text()).get("wikis"))
    odd = ROOT / "state-odd.json"
    odd.write_text("[1, 2, 3]")
    code, out = run(mod, wiki("Odd"), d(0), state=odd)
    check("errors", "a record of the wrong shape starts afresh, exit 0",
          code == 0 and context(out) is not None)
    stopper = ROOT / "state-stop-broken.json"
    stopper.write_text("{ not json")
    code, out = run(mod, wiki("StopBroken"), d(0), argv=["--stop"], state=stopper)
    check("errors", "stop the tour works on a damaged record",
          code == 0 and "stopped" in out and json.loads(stopper.read_text())["wikis"])
    # (0.16.0 review) the hook is registered for every Claude conversation on the Mac
    elsewhere_state = ROOT / "state-elsewhere.json"
    here = wiki("Elsewhere")
    os.environ["MOBLEE_VAULT"] = str(here)
    os.environ["MOBLEE_FIRST_DAYS_STATE"] = str(elsewhere_state)
    FakeDate.current = d(0)
    mod.datetime = FakeDatetime
    out_buf, old_stdin = io.StringIO(), sys.stdin
    sys.stdin = io.StringIO(json.dumps({"hook_event_name": "SessionStart", "cwd": str(ROOT / "NotAWiki")}))
    try:
        with contextlib.redirect_stdout(out_buf):
            code = mod.main([])
    finally:
        sys.stdin = old_stdin
    check("errors", "a conversation started in another folder: nothing said, no day used",
          code == 0 and out_buf.getvalue() == "" and not elsewhere_state.exists())
    os.environ["MOBLEE_NO_TOUR"] = "1"
    try:
        code, out = run(mod, wiki("NoTour"), d(0), state=ROOT / "state-notour.json")
    finally:
        del os.environ["MOBLEE_NO_TOUR"]
    check("errors", "the check-up's test run (MOBLEE_NO_TOUR): nothing said, no day used",
          code == 0 and out == "" and not (ROOT / "state-notour.json").exists())
    as_dir = ROOT / "state-is-a-folder"
    as_dir.mkdir()
    code, out = run(mod, wiki("Unwritable"), d(0), state=as_dir)
    check("errors", "a record that cannot be written: silent, exit 0", code == 0 and out == "")
    locked_state = ROOT / "state-locked.json"
    with open(str(locked_state) + ".lock", "a") as held:
        fcntl.flock(held, fcntl.LOCK_EX)
        code, out = run(mod, wiki("Locked"), d(0), state=locked_state)
    check("errors", "another conversation counting at the same moment: silent, no wait",
          code == 0 and out == "")

    # ----- the real thing, as a separate program
    real = wiki("Real")
    env = dict(os.environ, MOBLEE_VAULT=str(real),
               MOBLEE_FIRST_DAYS_STATE=str(ROOT / "state-real.json"))
    t0 = time.monotonic()
    p = subprocess.run([sys.executable, str(SCRIPT)],
                       input=json.dumps({"hook_event_name": "SessionStart", "cwd": str(real)}),
                       capture_output=True, text=True, env=env, timeout=20)
    took = time.monotonic() - t0
    check("blocks", "run as the hook runs it: exit 0", p.returncode == 0, p.stderr[:200])
    check("blocks", "nothing on stderr", p.stderr == "", p.stderr[:200])
    check("blocks", "quick: well under a second of its own", took < 3, f"{took:.2f}s")
    check("blocks", "stdout is SessionStart context", context(p.stdout) is not None, p.stdout[:120])
    p = subprocess.run([sys.executable, str(SCRIPT)], input="", capture_output=True, text=True, cwd=str(real),
                       env=dict(env, MOBLEE_FIRST_DAYS_STATE=str(ROOT / "state-real2.json")), timeout=20)
    check("blocks", "an empty message on stdin is no problem (the folder it starts in stands in)",
          p.returncode == 0 and context(p.stdout) is not None)
    p = subprocess.run([sys.executable, str(SCRIPT)], stdin=subprocess.DEVNULL, capture_output=True,
                       text=True, env=dict(env, MOBLEE_FIRST_DAYS_STATE=str(as_dir)), timeout=20)
    check("blocks", "an error as a separate program: exit 0, nothing printed",
          p.returncode == 0 and p.stdout == "" and p.stderr == "")

    registration()
    rules_file()

    width = max(len(r[2]) for r in rows)
    print("%-4s %-12s %s" % ("", "group", "case"))
    for status, group, label in rows:
        print("%-4s %-12s %-*s" % (status, group, width, label))
    print()
    print("cases: %d   failures: %d" % (len(rows), failures))
    print("practice folders left in place: %s" % ROOT)
    sys.exit(1 if failures else 0)


def registration():
    """safety/install-safety.py, Claude's branch, in a throwaway home."""
    vault = wiki("Registered")
    (vault / "scripts").mkdir()
    (vault / "scripts" / "first-days.py").write_text("# stand-in\n")
    (vault / "scripts" / "turn-end-commit.py").write_text("# stand-in\n")
    settings = HOME / ".claude" / "settings.json"
    settings.parent.mkdir(parents=True, exist_ok=True)
    settings.write_text(json.dumps({"hooks": {"SessionStart": [
        {"matcher": "startup", "hooks": [{"type": "command", "command": "echo owner-hook"}]}]}}))
    os.environ["HOME"] = str(HOME)
    os.environ.pop("MOBLEE_BACKUP", None)
    safety = load(PACK / "safety" / "install-safety.py", "install_safety")

    def go():
        out = io.StringIO()
        old = sys.argv
        sys.argv = ["install-safety.py", "--vault", str(vault), "--assistant", "claude"]
        try:
            with contextlib.redirect_stdout(out):
                code = safety.main()
        except SystemExit as e:
            code = e.code
        finally:
            sys.argv = old
        return code, out.getvalue()

    code, out = go()
    data = json.loads(settings.read_text())
    ss = data["hooks"].get("SessionStart", [])
    cmds = [h.get("command", "") for g in ss for h in g.get("hooks", [])]
    want = str(vault / "scripts" / "first-days.py")
    check("register", "install-safety exits 0", code == 0, out[-300:])
    check("register", "the tour is entered as a SessionStart hook by its full path",
          any(c.endswith("first-days.py") and want in c for c in cmds), json.dumps(cmds))
    check("register", "the owner's own SessionStart hook is kept, ahead of it",
          cmds and cmds[0] == "echo owner-hook")
    check("register", "the save is still entered as the Stop hook",
          any("turn-end-commit.py" in h.get("command", "")
              for g in data["hooks"].get("Stop", []) for h in g.get("hooks", [])))
    check("register", "the run says so in plain words", "first-week tour" in out)
    code, out = go()
    data = json.loads(settings.read_text())
    cmds = [h.get("command", "") for g in data["hooks"]["SessionStart"] for h in g.get("hooks", [])]
    check("register", "a second run enters nothing twice",
          sum(1 for c in cmds if "first-days.py" in c) == 1 and "already registered" in out)
    bare = wiki("NoScriptYet")
    (bare / "scripts").mkdir()
    old = sys.argv
    sys.argv = ["install-safety.py", "--vault", str(bare), "--assistant", "claude"]
    out = io.StringIO()
    try:
        with contextlib.redirect_stdout(out):
            safety.main()
    except SystemExit:
        pass
    finally:
        sys.argv = old
    data = json.loads(settings.read_text())
    cmds = [h.get("command", "") for g in data["hooks"]["SessionStart"] for h in g.get("hooks", [])]
    check("register", "a wiki without the script gets no hook that would fail",
          not any(str(bare) in c for c in cmds) and "not in the wiki yet" in out.getvalue())


def rules_file():
    """scripts/patch-claude-md.py: an owner-edited orient section gains the rule."""
    os.environ["MOBLEE_BACKUP"] = str(ROOT / "backups" / "run")
    patch = load(PACK / "scripts" / "patch-claude-md.py", "patch_claude_md")
    p = subprocess.run(["git", "-C", str(PACK), "show", "v0.15.2:vault-template/CLAUDE.md"],
                       capture_output=True, text=True)
    old = p.stdout if p.returncode == 0 else ""
    if not old:
        check("rules", "the 0.15.2 rules file could be read from the pack's history", False)
        return

    def patched(text, name):
        v = wiki(name)
        for page in patch.REFERENCE_PAGES:
            (v / "wiki" / "Wiki Operations" / f"{page}.md").write_text("x\n")
        (v / "CLAUDE.md").write_text(text)
        oldargv = sys.argv
        sys.argv = ["patch-claude-md.py", "--vault", str(v), "--assistant", "claude"]
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                patch.main()
        finally:
            sys.argv = oldargv
        return (v / "CLAUDE.md").read_text()

    clean = patched(old, "RulesClean")
    check("rules", "a 0.15.2 rules file gets the new orient wording",
          "### Waiting on others" in clean and "[[Mail Pass]]" in clean)
    check("rules", "and the first-week line in its companion section", "first-days.py --stop" in clean)
    check("rules", "and the added blocks do not repeat it", clean.count("Waiting on others") == 1, str(clean.count("Waiting on others")))
    mine = "My own orient line, kept."
    edited = old.replace('No preamble and no "I\'ll now read…" narration.',
                         'No preamble and no "I\'ll now read…" narration. ' + mine, 1)
    out = patched(edited, "RulesEdited")
    check("rules", "an orient section the owner wrote in keeps their words", mine in out)
    check("rules", "and gains the day's Plan rule by addition", "Waiting on others" in out and "Mail Pass" in out)


if __name__ == "__main__":
    main()
