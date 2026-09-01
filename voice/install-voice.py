#!/usr/bin/env python3
"""Moblee voice-stack installer (macOS only).

Copies the voice files into ~/.claude/hooks/, registers the Stop hook (reads
each Claude reply aloud) and the Notification hook (an audible nudge when
Claude is waiting on you) in ~/.claude/settings.json, and adds a `voice`
alias to your ~/.zshrc.

Safe to re-run: existing hooks are not duplicated, and nothing is removed.
A timestamped backup of settings.json is written before any change.

Works immediately with the built-in macOS voice. To upgrade to an ElevenLabs
voice later, add an API key to the Keychain:
  security add-generic-password -s elevenlabs_api_key -a elevenlabs -w
(then paste your key at the hidden prompt; get one at elevenlabs.io).
"""
import json, os, shutil, stat, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
HOOKS = os.path.expanduser("~/.claude/hooks")
SETTINGS = os.path.expanduser("~/.claude/settings.json")

STOP_CMD = 'python3 "$HOME/.claude/hooks/speak-elevenlabs.py"'
NOTIF_CMD = 'bash "$HOME/.claude/hooks/nudge.sh"'


def main():
    if sys.platform != "darwin":
        print("The voice stack is macOS-only (it uses `say`, `afplay` and the Keychain).")
        return 1

    os.makedirs(HOOKS, exist_ok=True)
    for name in ("speak-elevenlabs.py", "voice", "nudge.sh"):
        src, dst = os.path.join(HERE, name), os.path.join(HOOKS, name)
        shutil.copy2(src, dst)
        os.chmod(dst, os.stat(dst).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        print(f"installed {dst}")

    settings = {}
    if os.path.exists(SETTINGS):
        backup = SETTINGS + ".bak-" + time.strftime("%Y%m%d-%H%M%S")
        shutil.copy2(SETTINGS, backup)
        print(f"backed up settings to {backup}")
        try:
            with open(SETTINGS) as f:
                settings = json.load(f)
        except Exception:
            print(f"WARNING: {SETTINGS} is not valid JSON; fix it and re-run.")
            return 1

    hooks = settings.setdefault("hooks", {})

    def ensure(event, cmd):
        entries = hooks.setdefault(event, [])
        for group in entries:
            for h in group.get("hooks", []):
                if h.get("command") == cmd:
                    print(f"{event} hook already present — skipped")
                    return
        entries.append({"hooks": [{"type": "command", "command": cmd}]})
        print(f"{event} hook registered")

    ensure("Stop", STOP_CMD)
    ensure("Notification", NOTIF_CMD)

    with open(SETTINGS, "w") as f:
        json.dump(settings, f, indent=2)
    print(f"wrote {SETTINGS}")

    zshrc = os.path.expanduser("~/.zshrc")
    alias_line = 'alias voice="$HOME/.claude/hooks/voice"'
    existing = ""
    if os.path.exists(zshrc):
        with open(zshrc) as f:
            existing = f.read()
    if alias_line not in existing:
        with open(zshrc, "a") as f:
            f.write("\n# Moblee voice stack\n" + alias_line + "\n")
        print("added `voice` alias to ~/.zshrc (open a new terminal to use it)")
    else:
        print("`voice` alias already in ~/.zshrc")

    print("\nDone. From your next Claude Code session, replies are read aloud.")
    print("Commands: voice off | on | stop | last | full | say <text> | status")
    return 0


if __name__ == "__main__":
    sys.exit(main())
