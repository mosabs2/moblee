#!/usr/bin/env python3
"""Tests for 0.15.2: no part or item is called missing when it is in place.

Owners on 0.15.1 were told the safety guard was missing, and to install the
Moblee Hub and GitHub, on Macs where all three were installed and working.
Each case here is a working setup that an earlier check misread, built in a
throwaway home folder, with the setup script loaded as a module so single
checks can be asked directly. Nothing on this Mac is read or changed, and
nothing reaches the network: GitHub's tool and Claude are stand-ins.

  1. Addresses: the https and SSH forms of one GitHub repository are one.
  2. GitHub's tool where the Hub's join note puts it, and a sign-in read on
     this Mac, so an offline Mac or a second account is not "not signed in".
  3. The Hub at its old address, which GitHub forwards: in, not elsewhere;
     and unseen, not off, when GitHub cannot be asked.
  4. Plugins read from Claude's own record, and unseen (never off) when
     Claude cannot be asked.
  5. A check that breaks says it could not check, never "off".
  6. The guard's hook as the installer writes it, with $HOME.
  7. The usual tool folders (~/.local/bin) are on the PATH checks use.
  8. The check-up reads an SSH Hub address as the same Hub.
  9. (0.16.0) Claude's settings file damaged by hand: the checks that read it
     say they cannot tell, never "off".

Run from the Moblee folder: python3 tools/test-false-missing.py
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent
PASSED = 0
FAILED: list[str] = []


def check(cond: bool, what: str) -> None:
    global PASSED
    if cond:
        PASSED += 1
        print(f"  ok    {what}")
    else:
        FAILED.append(what)
        print(f"  FAIL  {what}")


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def stand_in(path: Path, body: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\n" + body + "\n")
    path.chmod(0o755)
    return str(path)


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="moblee-false-missing."))
    home = tmp / "home"
    home.mkdir()
    os.environ["HOME"] = str(home)
    for k in ("MOBLEE_GH", "MOBLEE_VAULT", "MOBLEE_PRACTICE", "MOBLEE_CLAUDE"):
        os.environ.pop(k, None)
    print(f"Moblee false-missing tests (throwaway folders under {tmp})")
    m = load("moblee_setup", PKG / "scripts" / "moblee-setup.py")
    d = load("moblee_doctor", PKG / "scripts" / "moblee-doctor.py")

    print("\n1. One repository, however its address is written")
    https = "https://github.com/Moblee-Main-Devs/moblee-hub.git"
    for other in ("git@github.com:Moblee-Main-Devs/moblee-hub.git", "ssh://git@github.com/Moblee-Main-Devs/moblee-hub",
                  "https://github.com/moblee-main-devs/moblee-hub/"):
        check(m.same_address(other, https), f"{other} is the same address as the https one")
    check(not m.same_address("git@github.com:someone/else.git", https), "a different repository is not")
    check(m.repo_slug("ssh://git@github.com/o/r.git") == "o/r", "an ssh:// address gives its owner/name")

    print("\n2. GitHub's tool where the Hub's join note puts it, and its sign-in")
    real_which = m.which
    m.which = lambda name: None                  # as if gh were on no PATH the app knows
    stand_in(home / "Apps" / "github-cli" / "gh_2.9.0_macOS_arm64" / "bin" / "gh", "exit 1")
    os.utime(home / "Apps" / "github-cli" / "gh_2.9.0_macOS_arm64" / "bin" / "gh", (1, 1))
    kept = stand_in(home / "Apps" / "github-cli" / "gh_2.10.0_macOS_arm64" / "bin" / "gh",
                    'if [ "$1 $2" = "auth token" ]; then echo gho_testtoken; exit 0; fi\n'
                    'if [ "$1 $2" = "auth status" ]; then echo "Logged in to github.com account test"; exit 0; fi; exit 1')
    check(m.gh_tool() == kept, "the newest copy under ~/Apps/github-cli is found (2.10.0, not 2.9.0 by its name)")
    ok, words = m.check_github()
    check(ok is True, "and GitHub reads as signed in when GitHub takes the sign-in (" + words + ")")
    out = stand_in(tmp / "gh-out" / "gh", 'echo "no oauth token found for github.com" >&2; exit 1')
    check(m.gh_signed_in(out) is False, "a gh with no sign-in is not signed in")
    check(m.gh_signed_in(str(tmp / "no-such-gh")) is None, "a gh that cannot be run gives no answer, not 'not signed in'")
    stale = stand_in(tmp / "gh-stale" / "gh",
                     'if [ "$1 $2" = "auth token" ]; then echo gho_revoked; exit 0; fi\n'
                     'echo "X Failed to log in to github.com account test (keyring)"; echo "- The token in keyring is invalid."; exit 1')
    real_reach = m.github_reachable
    m.github_reachable = lambda timeout=10: True
    check(m.gh_signed_in(stale) is False, "a kept sign-in GitHub turns down is not signed in (a false 'in' is as bad as a false 'missing')")
    m.github_reachable = lambda timeout=10: False
    check(m.gh_signed_in(stale) is None, "and the same words when GitHub cannot be reached give no answer, not 'not signed in'")
    m.github_reachable = real_reach
    m.which = real_which

    print("\n3. The Hub at its old address")
    folder = tmp / "wiki" / "hub"
    folder.mkdir(parents=True)
    saved = {n: getattr(m, n) for n in ("hub_folder", "hub_remote", "hub_manifest", "hub_me", "hub_git", "gh_tool", "gh_full_name", "gh_signed_in")}
    m.hub_folder = lambda: folder
    m.hub_remote = lambda f: "https://github.com/mmamas40501/moblee-hub.git"
    m.hub_manifest = lambda f: {"name": "Moblee Hub", "address": https, "version": "1.4.0"}
    m.hub_me = lambda f: "ahmed"
    m.hub_git = lambda args, timeout=30: (0, "")
    m.gh_tool = lambda: "gh"
    m.gh_signed_in = lambda gh: True
    m.gh_full_name = lambda gh, slug: "Moblee-Main-Devs/moblee-hub"
    ok, words = m.check_hub()
    check(ok is True and "old address" in words, "a copy at the old address GitHub forwards is in, and says so (" + words + ")")
    m.gh_full_name = lambda gh, slug: None
    real_reach = m.github_reachable
    m.github_reachable = lambda timeout=10: False
    ok, words = m.check_hub()
    check(ok is None, "when GitHub cannot be reached, it is unseen, not off")
    m.github_reachable = lambda timeout=10: True
    ok, words = m.check_hub()
    check(ok is False, "when GitHub is reached but does not know the old address, it is off, so the item that re-points it is offered")
    m.github_reachable = real_reach
    m.gh_full_name = lambda gh, slug: "someone/else"
    ok, _ = m.check_hub()
    check(ok is False, "a folder that really points at another repository is still off")
    m.hub_remote = lambda f: "git@github.com:Moblee-Main-Devs/moblee-hub.git"
    ok, _ = m.check_hub()
    check(ok is True, "a copy cloned over SSH is in")
    m.gh_signed_in = lambda gh: None
    ok, _ = m.check_hub()
    check(ok is True, "a sign-in that cannot be read just now does not make the Hub off")
    for n, f in saved.items():
        setattr(m, n, f)

    print("\n4. Plugins")
    real_ok = m.claude_ok
    m.claude_ok = lambda: False                  # no claude the app can find
    check(m.plugin_installed("skill-creator@claude-plugins-official") is None,
          "with no record of Claude's and no claude to ask, a plugin gives no answer")
    ok, _ = m.check_skill_maker()
    check(ok is None, "so Teach Claude is unseen, not off")
    plugins = home / ".claude" / "plugins"
    plugins.mkdir(parents=True)
    (plugins / "installed_plugins.json").write_text(json.dumps(
        {"version": 2, "plugins": {"obsidian@obsidian-skills": [{"scope": "user", "version": "1.0.0"}],
                                   "remotion@remotion": [{"scope": "project", "projectPath": "/elsewhere"}]}}))
    check(m.plugin_installed("obsidian@obsidian-skills") is True, "a plugin in Claude's own record for this Mac is installed, with no claude to ask")
    ok, _ = m.check_obsidian_extras()
    check(ok is True, "so Obsidian extras is on")
    check(m.plugin_installed("remotion@remotion") is False, "one installed only inside another project does not count")
    check(m.plugin_installed("skill-creator@claude-plugins-official") is False,
          "and one Claude's own record does not hold is not installed")
    m.claude_ok = real_ok

    print("\n5. A check that breaks")
    def broken():
        raise ValueError("a .zshrc that is not UTF-8")
    item = m.Item("test", "Make", "A test", "what", 1, 1, "free", install=lambda: True, check=broken)
    ok, words = item.check()
    check(ok is None and "could not check" in words, "says it could not check, and is not called off")

    print("\n6. The guard's hook as the installer writes it")
    guard = home / ".claude" / "hooks" / "bash-guard.py"
    guard.parent.mkdir(parents=True)
    guard.write_text("# guard\n")
    installer = (PKG / "safety" / "install-safety.py").read_text(encoding="utf-8")
    cmd = next(l.split("=", 1)[1].strip().strip("'") for l in installer.splitlines() if l.startswith("GUARD_CMD ="))
    check("$HOME" in cmd, "the installer's own command is read from install-safety.py: " + cmd)
    check(m._names_file(cmd, guard), "and it names the guard")
    check(not m._names_file('python3 "$HOME/elsewhere/bash-guard.py"', guard), "a guard somewhere else does not count")

    print("\n7. The usual tool folders")
    (home / ".local" / "bin").mkdir(parents=True)
    path = m.env_with_brew()["PATH"].split(":")
    check(str(home / ".local" / "bin") in path, "~/.local/bin (Anthropic's installer for Claude) is on the checks' PATH")
    first = os.environ.get("PATH", "").split(":")[0]
    check(not first or path.index(first) < path.index(str(home / ".local" / "bin")), "after the owner's own PATH, so their copy wins")

    print("\n8. The check-up")
    check(d.hub_norm("git@github.com:Moblee-Main-Devs/moblee-hub.git") == d.hub_norm(https),
          "reads an SSH Hub address as the same Hub")

    print("\n9. Claude's settings file damaged by hand (0.16.0)")
    settings = home / ".claude" / "settings.json"
    check(m.SETTINGS == settings, "the checks read Claude's settings in this home")
    check(m.deny_rules_present(["Bash(rm:*)"]) is False and m.recall_hook_registered() is False,
          "with no settings file, the rules and memory search's hook are plainly not there")
    settings.write_text('{"permissions": {"deny": ["Bash(rm:*)"]')
    check(m.deny_rules_present(["Bash(rm:*)"]) is None, "an unparseable file: whether the delete rules are in it cannot be told")
    check(m.recall_hook_registered() is None, "nor whether memory search is switched on")
    ok, words = m.check_voice()
    check(ok is None and "cannot be told" in words, "nor whether the voice is on: unseen, not off (" + words + ")")
    settings.write_text(json.dumps({"permissions": {"deny": ["Bash(rm:*)"]}}))
    check(m.deny_rules_present(["Bash(rm:*)"]) is True and m.deny_rules_present(["Bash(x:*)"]) is False,
          "a readable file still answers yes and no")
    settings.write_text(json.dumps(["not", "settings"]))
    check(m.deny_rules_present(["Bash(rm:*)"]) is False, "a file of the wrong shape holds no rules, and nothing breaks")

    print(f"\n{PASSED} passed, {len(FAILED)} failed")
    for what in FAILED:
        print("  FAIL  " + what.splitlines()[0])
    print(f"(the throwaway folder is {tmp}; the system clears it in time)")
    return 0 if not FAILED else 1


if __name__ == "__main__":
    sys.exit(main())
