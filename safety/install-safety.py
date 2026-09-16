#!/usr/bin/env python3
"""install-safety.py — put the delete guard and the permission rules in place.

Run by the Moblee installer and updater; safe to run by hand and safe to
run twice:

    python3 safety/install-safety.py                 # vault from ~/.config/moblee/vault-path
    python3 safety/install-safety.py --vault ~/Wiki/MyWiki
    python3 safety/install-safety.py --dry-run       # say what would change, change nothing

What it does, in order, stopping at the first failure:

  1. Copies bash-guard.py to ~/.claude/hooks/ and makes it executable.
  2. Proves the guard works by feeding it a delete command (must be
     refused, exit code 2) and a harmless command (must pass, exit code 0).
  3. Registers the guard in ~/.claude/settings.json as a PreToolUse hook on
     Bash. The file is backed up first; existing hooks are kept; the result
     is parsed again before it is accepted.
  4. Merges the starter permission rules into <vault>/.claude/settings.local.json:
     the allow list that stops the constant permission prompts, and the
     deny ring that refuses deletion, history rewriting and force pushes at
     the permission layer as well. Nothing already in the file is removed.

Everything here is standard-library Python; nothing is downloaded.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
GUARD_SRC = HERE / "bash-guard.py"
RULES_SRC = HERE / "starter-permissions.json"
HOOKS_DIR = Path.home() / ".claude" / "hooks"
GUARD_DST = HOOKS_DIR / "bash-guard.py"
SETTINGS = Path.home() / ".claude" / "settings.json"
GUARD_CMD = 'python3 "$HOME/.claude/hooks/bash-guard.py"'
BACKUP_ROOT = Path.home() / ".config" / "moblee" / "backups"


def say(msg: str) -> None:
    print(msg, flush=True)


def find_vault(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    env = os.environ.get("MOBLEE_VAULT")
    if env:
        return Path(env).expanduser().resolve()
    cfg = Path.home() / ".config" / "moblee" / "vault-path"
    if cfg.exists():
        p = cfg.read_text().strip()
        if p:
            return Path(p).expanduser().resolve()
    here = Path.cwd().resolve()
    for cand in (here, *here.parents):
        if (cand / "wiki" / "Index.md").exists():
            return cand
    sys.exit("Could not find the vault. Pass --vault <path> or run from inside it.")


def backup(path: Path, stamp: str) -> Path | None:
    if not path.exists():
        return None
    dst_dir = BACKUP_ROOT / stamp
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / path.name
    shutil.copy2(path, dst)
    return dst


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
    except Exception as e:  # noqa: BLE001
        sys.exit(f"{path} is not valid JSON ({e}). Fix or move it aside, then re-run.")
    if not isinstance(data, dict):
        sys.exit(f"{path} does not hold the expected settings object. Move it aside, then re-run.")
    return data


def check_hook_shape(settings: dict) -> None:
    """Stop with one plain sentence if the hooks section has a shape this
    script cannot merge into, before anything on the machine is changed."""
    hooks = settings.get("hooks", {})
    if not isinstance(hooks, dict):
        sys.exit("~/.claude/settings.json has a 'hooks' section that is not the usual "
                 "shape (a list where an object was expected). Nothing was changed; "
                 "ask Claude to look at that file before re-running.")
    for event, entries in hooks.items():
        if not isinstance(entries, list) or not all(isinstance(e, dict) for e in entries):
            sys.exit(f"~/.claude/settings.json has an unexpected shape under hooks/{event}. "
                     "Nothing was changed; ask Claude to look at that file before re-running.")
        for e in entries:
            if not isinstance(e.get("hooks", []), list):
                sys.exit(f"~/.claude/settings.json has an unexpected shape under hooks/{event}. "
                         "Nothing was changed; ask Claude to look at that file before re-running.")


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n")
    json.loads(tmp.read_text())  # parse-check before it replaces the real file
    os.replace(tmp, path)


def hook_count(hooks: dict) -> dict:
    return {k: sum(len(g.get("hooks", [])) for g in v) for k, v in hooks.items()}


def prove_guard(guard: Path) -> None:
    def run(cmd: str) -> int:
        payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": cmd}})
        r = subprocess.run([sys.executable, str(guard)], input=payload,
                           capture_output=True, text=True)
        return r.returncode
    blocked = run("rm -rf wiki/Something")
    passed = run("ls wiki")
    if blocked != 2 or passed != 0:
        sys.exit(f"The guard did not behave as expected (delete test exit {blocked}, "
                 f"harmless test exit {passed}). Nothing else was changed.")
    say("  guard proven: a delete command is refused, a harmless one passes")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    vault = find_vault(a.vault)
    if not (vault / "CLAUDE.md").exists() or not (vault / "wiki").is_dir():
        sys.exit(f"{vault} does not look like a vault (no CLAUDE.md or wiki/).")
    stamp = time.strftime("%Y%m%d-%H%M%S")
    def short(p: Path) -> str:
        s = str(p)
        home = str(Path.home())
        return "~" + s[len(home):] if s.startswith(home) else s

    say(f"Vault: {short(vault)}")

    # 0. read the settings first, so a file this script cannot merge into stops
    #    it before anything on the machine has changed
    settings = load_json(SETTINGS)
    check_hook_shape(settings)

    # 1. guard file
    say("Delete guard")
    if a.dry_run:
        say(f"  would copy {GUARD_SRC.name} to {short(GUARD_DST)}")
    else:
        HOOKS_DIR.mkdir(parents=True, exist_ok=True)
        if GUARD_DST.exists() and GUARD_DST.read_bytes() == GUARD_SRC.read_bytes():
            say(f"  already installed at {short(GUARD_DST)}")
        else:
            if GUARD_DST.exists():
                b = backup(GUARD_DST, stamp)
                say(f"  previous guard kept at {short(b)}")
            shutil.copy2(GUARD_SRC, GUARD_DST)
            say(f"  installed {short(GUARD_DST)}")
        GUARD_DST.chmod(GUARD_DST.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        prove_guard(GUARD_DST)

    # 2. hook registration
    say("Hook registration in ~/.claude/settings.json")
    hooks = settings.setdefault("hooks", {})
    before = hook_count(hooks)
    pre = hooks.setdefault("PreToolUse", [])
    present = any("bash-guard.py" in h.get("command", "")
                  for g in pre for h in g.get("hooks", []))
    if present:
        say("  already registered; nothing to change")
    elif a.dry_run:
        say("  would add a PreToolUse hook on Bash")
    else:
        b = backup(SETTINGS, stamp)
        if b:
            say(f"  previous settings kept at {short(b)}")
        pre.append({"matcher": "Bash", "hooks": [{"type": "command", "command": GUARD_CMD}]})
        after = hook_count(hooks)
        for k, n in before.items():
            if after.get(k, 0) < n:
                sys.exit(f"Refusing to write: hooks under {k} would be lost.")
        write_json(SETTINGS, settings)
        say(f"  registered; hook events now: {sorted(hooks.keys())}")

    # 3. permission rules in the vault
    say("Permission rules in the vault")
    rules = json.loads(RULES_SRC.read_text())
    vault_str = str(vault)
    want_allow = [r.replace("__VAULT__", vault_str) for r in rules["allow"]]
    want_deny = [r.replace("__VAULT__", vault_str) for r in rules["deny"]]
    local = vault / ".claude" / "settings.local.json"
    data = load_json(local)
    perms = data.setdefault("permissions", {})
    allow = perms.setdefault("allow", [])
    deny = perms.setdefault("deny", [])
    add_allow = [r for r in want_allow if r not in allow]
    add_deny = [r for r in want_deny if r not in deny]
    if not add_allow and not add_deny:
        say("  already in place; nothing to change")
    elif a.dry_run:
        say(f"  would add {len(add_allow)} allow rules and {len(add_deny)} deny rules")
    else:
        b = backup(local, stamp)
        if b:
            say(f"  previous rules kept at {short(b)}")
        allow.extend(add_allow)
        deny.extend(add_deny)
        write_json(local, data)
        say(f"  allow rules: {len(allow)} (added {len(add_allow)}); "
            f"deny rules: {len(deny)} (added {len(add_deny)})")

    if a.dry_run:
        say("")
        say("Dry run: nothing was changed.")
        return 0
    say("")
    say("Safety layer in place. From now on, in this vault:")
    say("  - Claude cannot delete files, empty folders, move things out of the vault,")
    say("    rewrite git history or force-push, however the command is phrased. If")
    say("    something must go, Claude tells you what and you remove it yourself.")
    say("  - Routine work (reading, searching, editing inside the vault, committing)")
    say("    runs without permission prompts. Anything outside that still asks.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
