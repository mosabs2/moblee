#!/usr/bin/env python3
"""job-switch.py - switch a built thing's scheduled job on or off, from the Moblee app.

    python3 scripts/job-switch.py --vault <wiki> --name <name> --status [--json]
    python3 scripts/job-switch.py --vault <wiki> --name <name> --on [--json]
    python3 scripts/job-switch.py --vault <wiki> --name <name> --off [--json]

The build skill lays a scheduler file (com.moblee.<name>.plist) in apps/<name>/.
Until 0.12.0 the owner switched it on with two Terminal lines. Now the Moblee
app does the same two things when the owner presses the tile: copies the file
into ~/Library/LaunchAgents/ and asks the Mac's scheduler to take it. The
assistant never runs this with --on or --off: switching on a job that runs
when nobody is watching is the owner's act, and the app is their hand.

--status says, in JSON with --json: whether the file is in place, whether the
scheduler has it loaded, when it last ran and whether that run succeeded (from
state/last-run.json), and whether it is a thinking job.

A laptop that was asleep at the job's hour runs it at the next wake: that is
how the Mac's scheduler treats a calendar time it missed, once, however many
were missed. --off unloads and leaves the copy in LaunchAgents in place but
renamed with ".off", so nothing is deleted.
"""
from __future__ import annotations

import argparse
import json
import os
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

AGENTS = Path(os.path.expanduser("~")) / "Library" / "LaunchAgents"


def say(d: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(d, indent=2))
    else:
        for k, v in d.items():
            print(f"{k}: {v}")


def think_jobs() -> set:
    """The only copies of think-job.py a schedule may run: the installed
    skill's, and the pack's own."""
    out = set()
    home = Path(os.path.expanduser("~"))
    cands = [home / ".claude" / "skills" / "build" / "parts" / "think-job.py"]
    try:
        pack = (home / ".config" / "moblee" / "package-path").read_text(encoding="utf-8").strip()
        if pack:
            cands.append(Path(pack).expanduser() / "skills" / "build" / "parts" / "think-job.py")
    except OSError:
        pass
    pack_here = Path(__file__).resolve().parent.parent / "skills" / "build" / "parts" / "think-job.py"
    cands.append(pack_here)
    for c in cands:
        try:
            if c.is_file():
                out.add(c.resolve())
        except OSError:
            pass
    return out


def loaded(label: str) -> bool:
    try:
        r = subprocess.run(["launchctl", "print", f"gui/{os.getuid()}/{label}"],
                           capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return False
    return r.returncode == 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vault", required=True)
    ap.add_argument("--name", required=True)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--status", action="store_true")
    g.add_argument("--on", action="store_true")
    g.add_argument("--off", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="say what would be done, do nothing")
    a = ap.parse_args()

    vault = Path(a.vault).expanduser().resolve()
    name = a.name
    if not all(c.isalnum() or c == "-" for c in name) or not name:
        say({"ok": False, "why": "the name is letters, digits and hyphens"}, a.json)
        return 2
    app = vault / "apps" / name
    plist = app / f"com.moblee.{name}.plist"
    label = f"com.moblee.{name}"
    manifest = {}
    try:
        manifest = json.loads((app / "app.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    title = str(manifest.get("title") or name) if isinstance(manifest, dict) else name
    job = manifest.get("job") if isinstance(manifest, dict) else None
    thinking = bool(isinstance(job, dict) and job.get("thinking"))
    installed = AGENTS / plist.name
    last = {}
    try:
        last = json.loads((app / "state" / "last-run.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    status = {
        "ok": True, "title": title, "name": name, "label": label,
        "file": plist.exists(), "in_place": installed.exists(), "loaded": loaded(label),
        "thinking": thinking,
        "last_run": last.get("finished") if isinstance(last, dict) else None,
        "last_ok": last.get("ok") if isinstance(last, dict) else None,
        "last_message": last.get("message") if isinstance(last, dict) else None,
    }
    if a.status:
        say(status, a.json)
        return 0
    if not plist.exists():
        status.update(ok=False, why="This thing has no schedule to switch on. Tell Claude.")
        say(status, a.json)
        return 1
    try:
        with open(plist, "rb") as fh:
            loaded_plist = plistlib.load(fh)
    except Exception as exc:
        status.update(ok=False, why=f"the scheduler file does not read as one ({exc})")
        say(status, a.json)
        return 1
    # the file must be this thing's own: its label, and a program that is the
    # thing's job or Moblee's own thinking job
    args = loaded_plist.get("ProgramArguments") if isinstance(loaded_plist, dict) else None
    program_ok = False
    if isinstance(args, list) and len(args) >= 2 and all(isinstance(x, str) for x in args) \
            and args[0].endswith("python3"):
        program = Path(args[1])
        try:
            if program.resolve() == (app / "job.py").resolve():
                program_ok = len(args) == 2
            elif program.resolve() in think_jobs():
                # Moblee's own thinking job, pointed at this thing and nothing else
                program_ok = args[2:] == ["--app", str(app)] or args[2:] == ["--app", str(app.resolve())]
        except OSError:
            program_ok = False
    if not isinstance(loaded_plist, dict) or loaded_plist.get("Label") != label or not program_ok \
            or "EnvironmentVariables" in loaded_plist:
        status.update(ok=False, why="This thing's schedule file is not its own. Tell Claude.")
        say(status, a.json)
        return 1
    if a.dry_run:
        status.update(would=("switch on" if a.on else "switch off"))
        say(status, a.json)
        return 0
    AGENTS.mkdir(parents=True, exist_ok=True)
    if a.on:
        if installed.exists() and installed.read_bytes() != plist.read_bytes():
            # the copy in place is older: keep it beside under a dated name, never over
            import datetime
            keep = installed.with_name(installed.name + ".before-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
            shutil.copy2(installed, keep)
        shutil.copy2(plist, installed)
        if loaded(label):
            subprocess.run(["launchctl", "bootout", f"gui/{os.getuid()}/{label}"],
                           capture_output=True, text=True, timeout=30)
        r = subprocess.run(["launchctl", "bootstrap", f"gui/{os.getuid()}", str(installed)],
                           capture_output=True, text=True, timeout=30)
        status.update(in_place=True, loaded=loaded(label))
        if r.returncode != 0 and not status["loaded"]:
            status.update(ok=False, why=(r.stderr.strip() or "the scheduler did not take it")[:200])
            say(status, a.json)
            return 1
        say(status, a.json)
        return 0
    # --off: unload, and set the copy aside under a new name rather than delete it
    if loaded(label):
        subprocess.run(["launchctl", "bootout", f"gui/{os.getuid()}/{label}"],
                       capture_output=True, text=True, timeout=30)
    if installed.exists():
        aside = installed.with_name(installed.name + ".off")
        n = 1
        while aside.exists():
            n += 1
            aside = installed.with_name(f"{installed.name}.off{n}")
        installed.rename(aside)
    status.update(in_place=False, loaded=loaded(label))
    say(status, a.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
