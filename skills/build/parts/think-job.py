#!/usr/bin/env python3
"""think-job.py - a scheduled job that asks the assistant.

Moblee's shape for anything that runs on a schedule and needs Claude to think:
a morning page, a weekly tidy, a check that reads and writes. It stays in the
build skill's folder and is pointed at a thing's folder:

    python3 think-job.py --app <wiki>/apps/<name>           # run it now
    python3 think-job.py --app <wiki>/apps/<name> --dry-run # say what it would run

The thing's folder holds what the job needs:

    prompt.md      what to ask, written by the assistant with the owner; the
                   wiki's folder and the day it runs are filled in for
                   __VAULT__ and __TODAY__
    fence.json     what the assistant may do while it runs: a list of allowed
                   tools and rules in Claude's own form, a time limit in
                   minutes, the lowest battery level it will start at, and
                   whether to alert the phone when it finishes or fails
    state/         last-run.json and job-log.txt, as every job keeps, and
                   last-answer.md, the assistant's reply in full

What it does, in order. It will not start on battery below the level in the
fence (the owner's laptop may be closed and unplugged: the job then waits for
the next wake, which the Mac's scheduler gives it). It finds Claude's engine:
the one inside the Claude app, newest first, else `claude` on the path. It
reads a long-lived sign-in from ~/.config/moblee/claude-token if the owner
made one with `claude setup-token` (without it the engine uses the Mac's own
sign-in, which a scheduled job may not reach). It runs the engine once, with
the prompt, inside the wiki folder, with the fence as its only permissions and
no way to ask anybody anything, and stops it at the time limit. It records the
run as every job does, keeps the answer, and sends one line to the phone if
the fence says so: the path of what was written, never its contents.

Rules it keeps. It never deletes: the delete guard is not there when nobody
is watching, so the fence is a list of what is allowed (the five file tools
and a few plain commands), never a list of what is not, and anything else
written into fence.json is dropped and named; the prompt is told the same.
It never retries a failed run on its own: a failed run is recorded and
alerted, and the owner or the assistant looks. It runs once per start,
however many scheduled hours were missed while the laptop slept.
"""
from __future__ import annotations

import argparse
import datetime
import glob
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

HOME = Path(os.path.expanduser("~"))
TOKEN_FILE = HOME / ".config" / "moblee" / "claude-token"
DEFAULT_FENCE = {
    "allowed_tools": ["Read", "Grep", "Glob", "Edit", "Write",
                      "Bash(git add:*)", "Bash(git commit:*)", "Bash(git status:*)", "Bash(git log:*)",
                      "Bash(ls:*)", "Bash(cat:*)", "Bash(date:*)", "Bash(python3 scripts/log-append.py:*)"],
    "minutes": 20,
    "battery_floor": 30,
    "alert": True,
    "model": "",
}


def now() -> datetime.datetime:
    return datetime.datetime.now()


def record(state: Path, started: datetime.datetime, ok: bool, message: str) -> None:
    state.mkdir(parents=True, exist_ok=True)
    finished = now()
    (state / "last-run.json").write_text(json.dumps({
        "started": started.isoformat(timespec="seconds"),
        "finished": finished.isoformat(timespec="seconds"),
        "ok": ok,
        "message": message,
        "thinking": True,
    }, indent=2) + "\n", encoding="utf-8")
    with open(state / "job-log.txt", "a", encoding="utf-8") as fh:
        fh.write(f"{finished.strftime('%Y-%m-%d %H:%M:%S')} {'ok' if ok else 'FAILED'} {message}\n")


def on_battery_below(floor: int) -> tuple[bool, str]:
    """True if the Mac is on battery and below the floor. A Mac with no
    battery, or whose state cannot be read, is never held back."""
    if floor <= 0:
        return False, "no battery floor set"
    try:
        r = subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return False, "battery state unreadable; running"
    text = r.stdout
    if "Battery Power" not in text:
        return False, "on mains power, or no battery"
    m = re.search(r"(\d{1,3})%", text)
    if not m:
        return False, "battery level unreadable; running"
    level = int(m.group(1))
    if level < floor:
        return True, f"on battery at {level}%, below the {floor}% it waits at; it will run at the next wake on power"
    return False, f"on battery at {level}%"


def find_engine() -> str | None:
    """Claude's engine: the one inside the Claude app, newest version first,
    else `claude` on the path. The app's copy is what every Moblee owner has."""
    override = os.environ.get("MOBLEE_ENGINE")
    if override:
        return override
    pattern = str(HOME / "Library" / "Application Support" / "Claude" / "claude-code" / "*" / "*"
                  / "claude.app" / "Contents" / "MacOS" / "claude")
    found = []
    for p in glob.glob(pattern):
        parts = Path(p).parts
        try:
            version = parts[-6]
        except IndexError:
            version = "0"
        key = tuple(int(x) if x.isdigit() else 0 for x in re.split(r"[.\-]", version))
        found.append((key, p))
    if found:
        found.sort()
        return found[-1][1]
    return shutil.which("claude")


def read_fence(app: Path) -> dict:
    fence = dict(DEFAULT_FENCE)
    try:
        loaded = json.loads((app / "fence.json").read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            for k in DEFAULT_FENCE:
                if k in loaded:
                    fence[k] = loaded[k]
    except (OSError, ValueError):
        pass
    tools = fence.get("allowed_tools")
    if not isinstance(tools, list) or not all(isinstance(t, str) for t in tools):
        tools = list(DEFAULT_FENCE["allowed_tools"])
    # The fence is a list of what is allowed, never a list of what is not: a
    # tool is kept only if it is one of the five file tools, or a command rule
    # of the exact form Bash(<prefix>:*) whose prefix is one this job may run.
    # Anything else written into the file, however spelt, is dropped and named.
    kept, dropped = [], []
    for t in tools:
        t = t.strip()
        if t in PLAIN_TOOLS:
            kept.append(t)
            continue
        m = re.fullmatch(r"Bash\(([^()*:]+):\*\)", t)
        if m and " ".join(m.group(1).split()) in BASH_PREFIXES:
            kept.append("Bash(" + " ".join(m.group(1).split()) + ":*)")
            continue
        dropped.append(t)
    fence["allowed_tools"] = kept
    fence["dropped"] = dropped
    try:
        fence["minutes"] = max(1, min(int(fence["minutes"]), 120))
    except (TypeError, ValueError):
        fence["minutes"] = DEFAULT_FENCE["minutes"]
    try:
        fence["battery_floor"] = max(0, min(int(fence["battery_floor"]), 100))
    except (TypeError, ValueError):
        fence["battery_floor"] = DEFAULT_FENCE["battery_floor"]
    alert = fence.get("alert", True)
    if isinstance(alert, str):
        alert = alert.strip().lower() in ("yes", "true", "on", "1")
    fence["alert"] = bool(alert) if isinstance(alert, (bool, int)) else True
    model = str(fence.get("model") or "").strip()
    fence["model"] = model if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.\-]{0,63}", model) else ""
    return fence


PLAIN_TOOLS = {"Read", "Grep", "Glob", "Edit", "Write"}
NEVER_TOOLS = ["Edit(scripts/**)", "Write(scripts/**)", "Edit(apps/**/fence.json)", "Write(apps/**/fence.json)",
               "Edit(apps/**/prompt.md)", "Write(apps/**/prompt.md)", "Edit(.claude/**)", "Write(.claude/**)",
               "Edit(.git/**)", "Write(.git/**)", "Edit(.gitignore)", "Write(.gitignore)",
               "Edit(**/*.py)", "Write(**/*.py)", "Edit(**/*.sh)", "Write(**/*.sh)",
               "Bash(git commit --amend:*)", "Bash(git commit -a:*)"]
BASH_PREFIXES = {"git add", "git commit", "git status", "git log", "git diff", "git show",
                 "ls", "cat", "head", "tail", "wc", "grep", "date", "pwd",
                 "python3 scripts/log-append.py", "python3 scripts/moblee-doctor.py", "python3 scripts/lint-v2.py",
                 "python3 scripts/compact-rotate.py", "python3 scripts/weekly-card.py"}


def vault_of(app: Path) -> Path | None:
    """The wiki this thing lives in: apps/<name>/ directly under it, and
    nowhere else, so a folder that merely sits below a wiki somewhere is not
    run in that wiki."""
    if app.parent.name != "apps":
        return None
    p = app.parent.parent
    if (p / "wiki").is_dir() and any((p / f).is_file() for f in ("CLAUDE.md", "AGENTS.md")):
        return p
    return None


def notify(app: Path, title: str, line: str) -> None:
    """Through the thing's own notify.py if it has one; silent otherwise."""
    script = app / "notify.py"
    if not script.is_file():
        return
    try:
        subprocess.run([sys.executable, str(script), title, line], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        pass


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--app", required=True, help="the thing's folder, apps/<name> in the wiki")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    app = Path(a.app).expanduser().resolve()
    state = app / "state"
    started = now()
    title = app.name
    try:
        m = json.loads((app / "app.json").read_text(encoding="utf-8"))
        if isinstance(m, dict) and m.get("title"):
            title = str(m["title"])
    except (OSError, ValueError):
        pass
    vault = vault_of(app)
    if vault is None:
        # nothing is written into a folder that is not a thing in a wiki
        print(f"{app} is not apps/<name>/ inside a wiki; nothing was run")
        return 1
    prompt_file = app / "prompt.md"
    if prompt_file.is_symlink():
        record(state, started, False, "prompt.md is a link to somewhere else, which is not read")
        return 1
    if not prompt_file.is_file():
        record(state, started, False, "no prompt.md: the assistant writes what to ask, with the owner")
        return 1
    fence = read_fence(app)
    for t in fence.get("dropped", []):
        print(f"not allowed by this job, and dropped from the fence: {t}")
    held, why = on_battery_below(fence["battery_floor"])
    if held:
        record(state, started, True, f"not run: {why}")
        print(f"not run: {why}")
        return 0
    engine = find_engine()
    if not engine:
        record(state, started, False, "Claude could not be started on this Mac: the Claude app was not found")
        notify(app, title, "did not run: Claude could not be started on this Mac; open the Claude app once and tell your assistant")
        return 1
    prompt = prompt_file.read_text(encoding="utf-8")
    prompt = (prompt.replace("__VAULT__", str(vault))
              .replace("__TODAY__", started.strftime("%-d %B %Y")))
    prompt = (prompt.rstrip() + "\n\nYou are running on a schedule with nobody watching. Never delete, move "
              "out of the wiki or rewrite history; append or write new dated files. If something cannot be "
              "done, say so in one line and stop.\n")
    allowed = fence["allowed_tools"] or ["Read"]
    cmd = [engine, "-p", prompt, "--permission-mode", "default", "--output-format", "text",
           "--allowedTools", ",".join(allowed),
           # what no job may ever write, whatever the fence allows: the wiki's
           # own scripts and hooks (a script written and then run is unbounded),
           # its own prompt and fence, Claude's settings, git's own folder, and
           # a commit that rewrites history
           "--disallowedTools", ",".join(NEVER_TOOLS)]
    if fence["model"]:
        cmd += ["--model", fence["model"]]
    env = dict(os.environ)
    env.pop("CLAUDECODE", None)
    try:
        token = TOKEN_FILE.read_text(encoding="utf-8").strip()
        if token:
            env["CLAUDE_CODE_OAUTH_TOKEN"] = token
    except OSError:
        pass
    if a.dry_run:
        shown = [c if c is not prompt else f"<prompt, {len(prompt)} characters>" for c in cmd]
        print("would run, in", vault)
        print(" ", " ".join(shown))
        print("  time limit", fence["minutes"], "minutes; battery floor", fence["battery_floor"], "%; alert", fence["alert"])
        print("  sign-in:", "the long-lived token" if "CLAUDE_CODE_OAUTH_TOKEN" in env else "the Mac's own")
        return 0
    try:
        r = subprocess.run(cmd, cwd=str(vault), capture_output=True, text=True,
                           timeout=fence["minutes"] * 60, env=env)
    except subprocess.TimeoutExpired:
        record(state, started, False, f"stopped at the {fence['minutes']}-minute limit")
        if fence["alert"]:
            notify(app, title, f"did not finish: stopped at the {fence['minutes']}-minute limit; see {state / 'job-log.txt'}")
        return 1
    except OSError as exc:
        record(state, started, False, f"Claude could not be started ({exc})")
        if fence["alert"]:
            notify(app, title, f"did not run: Claude could not be started; see {state / 'job-log.txt'}")
        return 1
    state.mkdir(parents=True, exist_ok=True)
    (state / "last-answer.md").write_text(
        f"# {title}, {started.strftime('%-d %B %Y %H:%M')}\n\n{r.stdout.strip()}\n", encoding="utf-8")
    if r.returncode != 0:
        tail = (r.stderr.strip().splitlines() or ["no reason given"])[-1][:200]
        record(state, started, False, f"Claude ended with an error: {tail}")
        if fence["alert"]:
            notify(app, title, f"did not finish; see {state / 'job-log.txt'}")
        return 1
    first = (r.stdout.strip().splitlines() or ["finished"])[0][:160]
    record(state, started, True, first)
    if fence["alert"]:
        notify(app, title, f"finished: {first} (answer at {state / 'last-answer.md'})")
    print(first)
    return 0


if __name__ == "__main__":
    sys.exit(main())
