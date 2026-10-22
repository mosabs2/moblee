#!/usr/bin/env python3
"""install-recall.py - put Moblee's memory search in place for a wiki.

    python3 extras/recall/install-recall.py --vault <wiki> [--dry-run] [--no-schedule]

Run by the "Memory search" item in the Moblee app (the owner's press), never
by the assistant. It does three things, each safe to repeat, and what it
prints is shown to the owner by the item:

  1. copies recall.py, recall-inject.py and rebuild-index.sh into
     <wiki>/scripts/recall/ (an older copy is kept beside under a dated name);
  2. tells Claude to use it: recall-inject.py becomes Claude's UserPromptSubmit
     hook in ~/.claude/settings.json, once, after a dated copy of the file,
     written whole or not at all, and a hook left pointing at an old place of
     the wiki is corrected rather than kept;
  3. writes the nightly refresh's launch agent, com.moblee.recall-rebuild at
     04:40 (the next wake on a laptop), to ~/Library/LaunchAgents/ and loads it.

The post-commit hook the wiki already has calls rebuild-index.sh in the
background when scripts/recall/ exists, so nothing is changed there. The
first build of the index is the item's own next step.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

HERE = Path(__file__).resolve().parent
HOME = Path(os.path.expanduser("~"))
SETTINGS = HOME / ".claude" / "settings.json"
BACKUPS = HOME / ".config" / "moblee" / "backups"
AGENTS = HOME / "Library" / "LaunchAgents"
LABEL = "com.moblee.recall-rebuild"
FILES = ("recall.py", "recall-inject.py", "rebuild-index.sh")


def say(s: str = "") -> None:
    print(s)


def cache_dir(vault: Path) -> Path:
    env = os.environ.get("MOBLEE_RECALL_CACHE")
    if env:
        return Path(os.path.expanduser(env))
    key = hashlib.sha1(os.path.realpath(str(vault)).encode("utf-8")).hexdigest()[:12]
    return HOME / ".cache" / "moblee-recall" / key


def backup(path: Path, stamp: str) -> Path | None:
    if not path.exists():
        return None
    dst = BACKUPS / stamp
    dst.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, dst / path.name)
    return dst / path.name


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vault", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-schedule", action="store_true", help="write the launch agent but do not load it (tests)")
    a = ap.parse_args()
    vault = Path(a.vault).expanduser().resolve()
    if not (vault / "wiki").is_dir():
        say(f"{vault} has no wiki/ folder; is that the wiki?")
        return 1
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = vault / "scripts" / "recall"
    say("Memory search: the scripts")
    for name in FILES:
        src, dst = HERE / name, dest / name
        if dst.exists() and dst.read_bytes() == src.read_bytes():
            say(f"  already in place: scripts/recall/{name}")
            continue
        if a.dry_run:
            say(f"  would put scripts/recall/{name}" + (" (the older copy kept)" if dst.exists() else ""))
            continue
        dest.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            kept = dst.with_name(f"{dst.name}.before-{stamp}")
            shutil.copy2(dst, kept)
        shutil.copy2(src, dst)
        dst.chmod(dst.stat().st_mode | 0o111)
        say(f"  put scripts/recall/{name}")
    # "|| true": if the wiki is ever moved, the hook must fail silently rather
    # than block every message the owner sends (a non-zero exit here is shown
    # to the owner, and exit 2 stops the message).
    hook_cmd = f"python3 {shlex.quote(str(dest / 'recall-inject.py'))} 2>/dev/null || true"
    say("Telling Claude to use it")
    try:
        settings = json.loads(SETTINGS.read_text(encoding="utf-8")) if SETTINGS.exists() else {}
    except (OSError, ValueError):
        say("  Claude's settings could not be read, so Claude was not told; Check my wiki offers Repair")
        return 1
    if not isinstance(settings, dict):
        say("  Claude's settings are not in the shape Claude expects; nothing was changed")
        return 1
    hooks = settings.get("hooks")
    if hooks is None:
        hooks = settings["hooks"] = {}
    if not isinstance(hooks, dict):
        say("  the part of Claude's settings this goes in is not in the usual shape; nothing was changed")
        return 1
    ups = hooks.get("UserPromptSubmit")
    if ups is None:
        ups = []
    if not isinstance(ups, list):
        say("  the part of Claude's settings this goes in is not in the usual shape; nothing was changed")
        return 1
    current, stale = False, []
    for g in ups:
        for h in (g.get("hooks") or []) if isinstance(g, dict) else []:
            if isinstance(h, dict) and "recall-inject.py" in str(h.get("command", "")):
                if str(h.get("command")) == hook_cmd:
                    current = True
                else:
                    stale.append(h)
    if current and not stale:
        say("  already told; nothing to change")
    elif a.dry_run:
        say("  would tell it" + (" (and correct an entry pointing at an old place of the wiki)" if stale else ""))
    else:
        b = backup(SETTINGS, stamp)
        if b:
            say(f"  previous settings kept at {b}")
        for h in stale:
            h["command"] = hook_cmd
            h["timeout"] = 12
        if not current and not stale:
            ups.append({"hooks": [{"type": "command", "command": hook_cmd, "timeout": 12}]})
        hooks["UserPromptSubmit"] = ups
        text = json.dumps(settings, indent=2) + "\n"
        json.loads(text)
        SETTINGS.parent.mkdir(parents=True, exist_ok=True)
        tmp = SETTINGS.with_name(SETTINGS.name + f".{os.getpid()}.tmp")
        tmp.write_text(text, encoding="utf-8")
        json.loads(tmp.read_text(encoding="utf-8"))
        os.replace(tmp, SETTINGS)
        say("  corrected: Claude's link to it pointed at an old place of the wiki" if stale else
            "  told: the closest wiki sections are attached to a question before Claude reads it")
    say("The nightly refresh, at twenty to five or the next wake")
    plist = AGENTS / f"{LABEL}.plist"
    cache = cache_dir(vault)
    body = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>{xml_escape(str(dest / "rebuild-index.sh"))}</string>
        <string>launchd</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>4</integer>
        <key>Minute</key>
        <integer>40</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>{xml_escape(str(cache / "launchd.log"))}</string>
    <key>StandardErrorPath</key>
    <string>{xml_escape(str(cache / "launchd.log"))}</string>
    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
"""
    if a.dry_run:
        say(f"  would write {plist} and set it")
    else:
        AGENTS.mkdir(parents=True, exist_ok=True)
        cache.mkdir(parents=True, exist_ok=True)
        if plist.exists() and plist.read_text(encoding="utf-8") != body:
            shutil.copy2(plist, plist.with_name(plist.name + f".before-{stamp}"))
        plist.write_text(body, encoding="utf-8")
        if not a.no_schedule:
            uid = os.getuid()
            subprocess.run(["launchctl", "bootout", f"gui/{uid}/{LABEL}"], capture_output=True, text=True, timeout=30)
            r = subprocess.run(["launchctl", "bootstrap", f"gui/{uid}", str(plist)], capture_output=True, text=True, timeout=30)
            say("  set" if r.returncode == 0 else f"  could not be set ({r.stderr.strip()[:120]}); choose this item again")
        else:
            say("  written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
