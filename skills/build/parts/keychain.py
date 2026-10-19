#!/usr/bin/env python3
"""keychain.py - a secret in the Mac's Keychain, never in a file.

    python3 keychain.py set <app> <key>     asks for the secret at a prompt (nothing shows), stores it
    python3 keychain.py get <app> <key>     prints it (for a script to read)
    python3 keychain.py has <app> <key>     says yes or no, exit 0 or 1

Each secret is a login-keychain item named moblee.<app>.<key>. The owner types
the secret at the prompt themselves; it never goes on a Terminal line, where the
shell's history would keep it, and never into the wiki.

A scheduled job can read it while the owner is logged in (the login keychain is
unlocked then). The first read by a new program may show the Mac's own "allow
access" dialogue once; Always Allow is the answer.
"""
from __future__ import annotations

import getpass
import re
import subprocess
import sys


def item(app: str, key: str) -> str:
    for part in (app, key):
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", part):
            sys.exit(f"'{part}' is not a plain name (letters, digits, dots, hyphens, underscores).")
    return f"moblee.{app}.{key}"


def main() -> int:
    if len(sys.argv) != 4 or sys.argv[1] not in ("set", "get", "has"):
        print(__doc__)
        return 2
    verb, app, key = sys.argv[1:4]
    name = item(app, key)
    if verb == "set":
        value = getpass.getpass(f"The secret for {name} (nothing will show as you type): ")
        if not value:
            print("Nothing entered; nothing stored.")
            return 1
        # The secret goes to `security` on its standard input, never on a
        # command line, where Activity Monitor and `ps` would show it.
        import shlex
        line = f"add-generic-password -U -a {shlex.quote(app)} -s {shlex.quote(name)} -w {shlex.quote(value)}\n"
        r = subprocess.run(["security", "-i"], input=line, capture_output=True, text=True)
        if r.returncode != 0:
            print("The Keychain refused: " + r.stderr.strip())
            return 1
        print(f"Stored as {name} in the login keychain.")
        return 0
    r = subprocess.run(["security", "find-generic-password", "-a", app, "-s", name, "-w"],
                       capture_output=True, text=True)
    if verb == "has":
        print("yes" if r.returncode == 0 else "no")
        return 0 if r.returncode == 0 else 1
    if r.returncode != 0:
        print(f"No secret named {name} in the Keychain. Store one with: python3 keychain.py set {app} {key}",
              file=sys.stderr)
        return 1
    print(r.stdout.rstrip("\n"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
