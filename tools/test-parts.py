#!/usr/bin/env python3
"""Tests for the parts report (0.14.0): `scripts/moblee-setup.py --parts`, which
the app's "Add more" screen draws. Each case runs the real script in a throwaway
home folder, so nothing on this Mac is read or changed.

What is checked:
  1. a Mac with nothing on it: every part missing, every extra never looked at;
  2. a full Claude install: every part in place, each extra as the checklist's
     own record last saw it (on, off, cannot be seen);
  3. a skill that is not this Moblee's copy, and a galaxy with no tool beside it;
  4. ChatGPT, and both assistants: a part counts as in place only where every
     assistant the owner uses has it;
  5. a damaged record is read as no record, never a crash;
  6. the report is read only: the home folder is the same before and after;
  7. (0.16.0) ChatGPT's guard and hooks file are read from CODEX_HOME when set;
  8. (0.16.0) a settings file damaged by hand reads as 'unreadable', never 'missing';
  9. (0.16.0) the first-week tour, read from Claude's SessionStart entries by full path.

Run from the Moblee folder: python3 tools/test-parts.py
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent
SETUP = PKG / "scripts" / "moblee-setup.py"
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


def report(home: Path, extra: dict | None = None) -> dict:
    env = dict(os.environ)
    env.pop("MOBLEE_VAULT", None)
    env.pop("CODEX_HOME", None)
    env["HOME"] = str(home)
    env.update(extra or {})
    r = subprocess.run([sys.executable, str(SETUP), "--parts"], env=env, capture_output=True, text=True, timeout=120)
    try:
        return json.loads(r.stdout)
    except ValueError:
        return {"error": r.stdout[-400:] + r.stderr[-400:]}


def states(rep: dict) -> dict:
    return {p["key"]: p["state"] for p in rep.get("core", [])}


def snapshot(home: Path) -> dict:
    """Every file under the home folder, except Apple's Python's own cache of
    its compiled standard library (Library/Caches/com.apple.python), which
    that Python writes whatever script it runs (found on the Mac mini, 26
    October 2026)."""
    out = {}
    for p in sorted(home.rglob("*")):
        rel = str(p.relative_to(home))
        if p.is_file() and not rel.startswith("Library/Caches/com.apple.python"):
            out[rel] = p.read_bytes()
    return out


def make_home(root: Path, assistant: str = "claude") -> tuple[Path, Path]:
    home = root / "home"
    vault = home / "Wiki" / "Test Wiki"
    (vault / "wiki").mkdir(parents=True)
    (vault / "wiki" / "Index.md").write_text("# Index\n")
    cfg = home / ".config" / "moblee"
    cfg.mkdir(parents=True)
    (cfg / "vault-path").write_text(str(vault) + "\n")
    (cfg / "assistant").write_text(assistant + "\n")
    return home, vault


def hooks_file(guard_dir: Path, vault: Path, stop_for: Path | None = None) -> dict:
    """A settings file as the installer writes it: the guard and the save as
    hook entries, and, beside them, the permission rule that names the save
    by its file name (which is what a match on the file's text mistook for
    the save being switched on)."""
    stop_for = stop_for or vault
    return {"permissions": {"allow": ["Bash(python3 scripts/turn-end-commit.py)"],
                            "autoMode": "turn-end-commit.py and bash-guard.py are Moblee's own"},
            "hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": f"python3 '{guard_dir}/bash-guard.py'"}]}],
                      "Stop": [{"hooks": [{"type": "command", "command": f"python3 '{stop_for}/scripts/turn-end-commit.py'"}]}],
                      "SessionStart": [{"hooks": [{"type": "command", "timeout": 10,
                                                   "command": f"python3 '{stop_for}/scripts/first-days.py'"}]}]}}


def install_everything(home: Path, vault: Path, claude: bool = True, chatgpt: bool = False, galaxy_tool: bool = True) -> None:
    for d, on in ((home / ".claude" / "skills", claude), (home / ".agents" / "skills", chatgpt)):
        if on:
            d.mkdir(parents=True, exist_ok=True)
            for s in (PKG / "skills").iterdir():
                if s.is_dir():
                    shutil.copytree(s, d / s.name, dirs_exist_ok=True)
    if claude:
        (home / ".claude" / "hooks").mkdir(parents=True, exist_ok=True)
        (home / ".claude" / "hooks" / "bash-guard.py").write_text("# guard\n")
        (home / ".claude" / "settings.json").write_text(json.dumps(hooks_file(home / ".claude" / "hooks", vault)))
    if chatgpt:
        (home / ".codex" / "hooks").mkdir(parents=True, exist_ok=True)
        (home / ".codex" / "hooks" / "bash-guard.py").write_text("# guard\n")
        (home / ".codex" / "hooks.json").write_text(json.dumps(hooks_file(home / ".codex" / "hooks", vault)))
    (vault / "scripts" / "wiki-galaxy").mkdir(parents=True, exist_ok=True)
    if galaxy_tool:
        (vault / "scripts" / "wiki-galaxy" / "build.py").write_text("# build\n")
    (vault / "scripts" / "turn-end-commit.py").write_text("# save\n")
    (vault / "scripts" / "first-days.py").write_text("# tour\n")
    (vault / "dashboard").mkdir(exist_ok=True)
    (vault / "dashboard" / "server.py").write_text("# dashboard\n")
    (vault / "VERSION").write_text((PKG / "VERSION").read_text())


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="moblee-parts-test."))
    print(f"Moblee parts report tests (throwaway folders under {tmp})")
    core_names = {"guard", "save", "tour", "galaxy", "dashboard"} | {p.name for p in (PKG / "skills").iterdir() if p.is_dir()}

    print("\n1. A Mac with nothing on it")
    home = tmp / "empty"
    home.mkdir()
    rep = report(home)
    check("error" not in rep and rep.get("vault") is False, "it answers, and says no wiki was found" + ("" if "error" not in rep else "\n" + rep["error"]))
    check(set(states(rep)) == core_names, "every core part is listed, each skill this Moblee carries among them")
    check(set(states(rep).values()) == {"missing"}, "and every one is missing")
    check(rep.get("checked") is None and set(rep.get("extras", {}).values()) == {"unknown"},
          "every extra is 'never looked at', and no check is on record")
    listed = subprocess.run([sys.executable, str(SETUP), "--list", "--json"], capture_output=True, text=True,
                            env=dict(os.environ, HOME=str(home))).stdout
    check(set(rep.get("extras", {})) == {i["key"] for i in json.loads(listed)},
          "the extras are exactly the checklist's own items, the hub among them")
    check("hub" in rep.get("extras", {}) and "reach" in rep.get("extras", {}), "the hub and phone reach (Tailscale) are there")

    print("\n2. A full install for Claude, and the checklist's record")
    home, vault = make_home(tmp / "full")
    install_everything(home, vault)
    record = {"status": {"hub": True, "reach": False, "google": False, "voice": True},
              "unseen": ["google"], "working": ["hub", "voice"], "last_check": "20261026-1700"}
    (home / ".config" / "moblee" / "setup-state.json").write_text(json.dumps(record))
    before = snapshot(home)
    rep = report(home)
    check(set(states(rep).values()) == {"in"}, "every core part is in place" + ("" if set(states(rep).values()) == {"in"} else f" {states(rep)}"))
    ex = rep.get("extras", {})
    check(ex.get("hub") == "on" and ex.get("voice") == "on", "an extra the record says works is 'on'")
    check(ex.get("reach") == "off", "an extra the record says does not work is 'off'")
    check(ex.get("google") == "unseen", "an extra the record could not see is 'unseen', never 'off'")
    check(ex.get("film") == "unknown", "an extra the record does not name is 'unknown'")
    check(rep.get("checked") == "20261026-1700", "the time of the last check is given")
    galaxy = next(p for p in rep["core"] if p["key"] == "galaxy")
    dash = next(p for p in rep["core"] if p["key"] == "dashboard")
    check(galaxy["open"] == "galaxy" and dash["open"] == "dashboard" and galaxy["say"] == "galaxy",
          "the galaxy and the dashboard are marked as things the app can open")
    check(all(p["title"] and p["what"] for p in rep["core"]), "every part has a name and a line on what it is for")
    check(snapshot(home) == before, "nothing in the home folder was written or changed")

    print("\n3. Copies that are not this Moblee's")
    (home / ".claude" / "skills" / "brain" / "SKILL.md").write_text("an older brain\n")
    rep = report(home)
    check(states(rep).get("brain") == "differs", "a skill under Moblee's name that is not its copy is 'differs'")
    # A second home with no galaxy tool, rather than removing the first one's:
    # the vault's safety gate refuses any test that deletes, even in a scratch folder.
    nohome, novault = make_home(tmp / "nogalaxy")
    install_everything(nohome, novault, galaxy_tool=False)
    check(states(report(nohome)).get("galaxy") == "missing", "the galaxy skill without its tool in the wiki is 'missing'")
    s = hooks_file(home / ".claude" / "hooks", vault)
    s["hooks"] = {}
    (home / ".claude" / "settings.json").write_text(json.dumps(s))
    rep = report(home)
    check(states(rep).get("guard") == "missing" and states(rep).get("save") == "missing",
          "a guard and a save that are on the Mac, named only in the permission rules, are 'missing'")
    (home / ".claude" / "settings.json").write_text(json.dumps(hooks_file(home / ".claude" / "hooks", vault,
                                                                           stop_for=home / "Wiki" / "Old Wiki")))
    rep = report(home)
    check(states(rep).get("save") == "missing" and states(rep).get("guard") == "in",
          "a save entered for a wiki that has since moved does not count for this one")
    (vault / "VERSION").write_text("0.1.0\n")
    rep = report(home)
    check(states(rep).get("brain") == "in",
          "a wiki on a different Moblee version is not told its skills are not Moblee's")

    print("\n4. ChatGPT, and both assistants")
    home, vault = make_home(tmp / "chatgpt", "chatgpt")
    install_everything(home, vault, claude=False, chatgpt=True)
    rep = report(home)
    st = states(rep)
    check(rep.get("assistant") == "chatgpt" and st.get("brain") == "in" and st.get("dashboard") == "in",
          "for ChatGPT the skills are read from ChatGPT's own folder")
    check(st.get("guard") == "unseen" and st.get("save") == "unseen",
          "a guard and a save entered for ChatGPT are 'unseen' (whether ChatGPT trusts them cannot be seen), never 'in'")
    check("tour" not in st, "the first-week tour, entered for Claude only, is not listed for an owner on ChatGPT alone")
    home, vault = make_home(tmp / "both", "both")
    install_everything(home, vault, claude=True, chatgpt=False)
    rep = report(home)
    check(states(rep).get("brain") == "missing" and states(rep).get("guard") == "missing",
          "with both assistants, a part only Claude has is not in place")

    print("\n5. A damaged record")
    home, vault = make_home(tmp / "damaged")
    (home / ".config" / "moblee" / "setup-state.json").write_text("{not json")
    rep = report(home)
    check("error" not in rep and set(rep.get("extras", {}).values()) == {"unknown"},
          "is read as no record, and nothing breaks")
    (home / ".config" / "moblee" / "setup-state.json").write_text(json.dumps({"status": ["odd"], "unseen": "odd"}))
    rep = report(home)
    check("error" not in rep and set(rep.get("extras", {}).values()) == {"unknown"}, "nor does a record of the wrong shape")

    print("\n6. The guard and the save as the real installer enters them (0.15.2)")
    # Until 0.15.2 the fixtures above wrote the guard's command as a full path,
    # while the installer writes python3 "$HOME/.claude/hooks/bash-guard.py";
    # the report read only ~, so every installed guard showed as Missing. Here
    # the installer itself runs in a throwaway home and the report reads what
    # it wrote.
    for who in ("claude", "chatgpt"):
        home, vault = make_home(tmp / f"installed-{who}", who)
        (vault / "scripts").mkdir(parents=True, exist_ok=True)
        (vault / "scripts" / "turn-end-commit.py").write_text("# save\n")
        (vault / ("CLAUDE.md" if who == "claude" else "AGENTS.md")).write_text("# Wiki\n")
        env = dict(os.environ, HOME=str(home))
        for k in ("MOBLEE_VAULT", "CODEX_HOME"):
            env.pop(k, None)
        r = subprocess.run([sys.executable, str(PKG / "safety" / "install-safety.py"), "--vault", str(vault), "--assistant", who],
                           env=env, capture_output=True, text=True, timeout=300)
        check(r.returncode == 0, f"the installer puts the guard in for {who}" + ("" if r.returncode == 0 else "\n" + (r.stdout + r.stderr)[-600:]))
        st = states(report(home))
        want = "in" if who == "claude" else "unseen"
        check(st.get("guard") == want and st.get("save") == want,
              f"and the report reads the guard and the save as '{want}' for {who}" + ("" if st.get("guard") == want else f" (guard {st.get('guard')}, save {st.get('save')})"))

    print("\n7. ChatGPT's folder moved by CODEX_HOME (0.16.0)")
    home, vault = make_home(tmp / "codex-home", "chatgpt")
    install_everything(home, vault, claude=False, chatgpt=True)
    moved = home / "elsewhere" / "codex"
    (moved / "hooks").mkdir(parents=True)
    (moved / "hooks" / "bash-guard.py").write_text("# guard\n")
    (moved / "hooks.json").write_text(json.dumps(hooks_file(moved / "hooks", vault)))
    st = states(report(home, {"CODEX_HOME": str(moved)}))
    check(st.get("guard") == "unseen" and st.get("save") == "unseen",
          "a guard and a save entered in CODEX_HOME are found there ('unseen', as for ~/.codex)" + ("" if st.get("guard") == "unseen" else f" {st}"))
    empty = home / "elsewhere" / "empty-codex"
    empty.mkdir(parents=True)
    st = states(report(home, {"CODEX_HOME": str(empty)}))
    check(st.get("guard") == "missing", "with CODEX_HOME set, ~/.codex is not read in its place")
    st = states(report(home, {"CODEX_HOME": "  "}))
    check(st.get("guard") == "unseen", "a blank CODEX_HOME falls back to ~/.codex")

    print("\n8. A settings file damaged by hand reads as cannot tell, never off (0.16.0)")
    home, vault = make_home(tmp / "damaged-settings")
    install_everything(home, vault)
    (home / ".claude" / "settings.json").write_text('{"hooks": {"PreToolUse": [ broken')
    st = states(report(home))
    check(st.get("guard") == "unreadable" and st.get("save") == "unreadable",
          "an unparseable settings file makes the guard and the save 'unreadable', not 'missing'" + ("" if st.get("guard") == "unreadable" else f" {st}"))
    home2, vault2 = make_home(tmp / "damaged-no-guard")
    install_everything(home2, vault2)
    (home2 / ".claude" / "settings.json").write_text("not json at all")
    (home2 / ".claude" / "hooks" / "bash-guard.py").rename(home2 / ".claude" / "hooks" / "bash-guard.py.moved")
    check(states(report(home2)).get("guard") == "missing", "with no guard file on the Mac it is still 'missing'")
    home3, vault3 = make_home(tmp / "damaged-codex", "both")
    install_everything(home3, vault3, claude=True, chatgpt=True)
    (home3 / ".codex" / "hooks.json").write_text("{")
    st = states(report(home3))
    check(st.get("guard") == "unreadable", "for both assistants, a damaged ChatGPT hooks file makes the guard 'unreadable'")
    rep = report(home3)
    check(all(p["state"] in ("in", "missing", "differs", "unseen", "unreadable") for p in rep.get("core", [])),
          "every state is one of the report's words")
    check(states(report(home)).get("tour") == "unreadable", "and the first-week tour is 'unreadable' there too")

    print("\n9. The first-week tour, Claude's SessionStart hook (0.16.0)")
    home, vault = make_home(tmp / "tour")
    install_everything(home, vault)
    tour = next((p for p in report(home).get("core", []) if p["key"] == "tour"), {})
    check(tour.get("state") == "in" and tour.get("title") == "The first-week tour" and "five days" in tour.get("what", ""),
          "entered by its full path for this wiki: 'in', with its name and what it is for" + ("" if tour.get("state") == "in" else f" {tour}"))
    s = hooks_file(home / ".claude" / "hooks", vault)
    s["hooks"]["SessionStart"] = [{"hooks": [{"type": "command", "command": "python3 scripts/first-days.py"}]}]
    (home / ".claude" / "settings.json").write_text(json.dumps(s))
    check(states(report(home)).get("tour") == "missing", "named only by a relative path, it does not count")
    s["hooks"]["SessionStart"] = [{"hooks": [{"type": "command", "command": f"python3 '{home}/Wiki/Old Wiki/scripts/first-days.py'"}]}]
    (home / ".claude" / "settings.json").write_text(json.dumps(s))
    check(states(report(home)).get("tour") == "missing", "entered for another folder, it does not count for this one")
    s["hooks"].pop("SessionStart")
    s["permissions"]["allow"].append("Bash(python3 scripts/first-days.py)")
    (home / ".claude" / "settings.json").write_text(json.dumps(s))
    check(states(report(home)).get("tour") == "missing", "named only in a permission rule, it is 'missing'")
    home2, vault2 = make_home(tmp / "tour-no-script")
    install_everything(home2, vault2)
    (vault2 / "scripts" / "first-days.py").rename(vault2 / "scripts" / "first-days.py.moved")
    check(states(report(home2)).get("tour") == "missing", "entered but with no script in the wiki, it is 'missing'")
    home3, vault3 = make_home(tmp / "tour-both", "both")
    install_everything(home3, vault3, claude=True, chatgpt=True)
    check(states(report(home3)).get("tour") == "in", "for both assistants it is judged on Claude's settings alone")

    print(f"\n{PASSED} passed, {len(FAILED)} failed")
    for what in FAILED:
        print("  FAIL  " + what.splitlines()[0])
    print(f"(the throwaway folder is {tmp}; the system clears it in time)")
    return 0 if not FAILED else 1


if __name__ == "__main__":
    sys.exit(main())
