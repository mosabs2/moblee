#!/usr/bin/env python3
"""moblee-doctor.py - a read-only check-up of a Moblee wiki and the Mac it lives on.

    python3 scripts/moblee-doctor.py            # plain-English findings
    python3 scripts/moblee-doctor.py --json     # the same, for a program
    python3 scripts/moblee-doctor.py --report   # also write a report the owner can send on

It changes nothing (the report is the one file it can write, and only when
asked). Each finding carries the number of the entry in the companion skill's
field guide (skills/companion/field-guide.md) that explains it and says who
does the fix.

The report holds the state of the setup and nothing from the wiki's pages: no
names, no page titles, and the home folder written as "~".
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

HOME = Path.home()
CONFIG = HOME / ".config" / "moblee"
SETTINGS = HOME / ".claude" / "settings.json"
GUARD = HOME / ".claude" / "hooks" / "bash-guard.py"
SKILLS = HOME / ".claude" / "skills"
AGENTS = HOME / "Library" / "LaunchAgents"
PACK_HERE = Path(__file__).resolve().parent.parent

OK, LOOK, PROBLEM = "OK", "LOOK", "PROBLEM"


def tidy(text: str) -> str:
    """No account name in anything printed: the home folder becomes ~."""
    return str(text).replace("/private" + str(HOME), "~").replace(str(HOME), "~")


def run(cmd: list, timeout: int = 20) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except (OSError, subprocess.SubprocessError) as exc:
        return 1, str(exc)


def find_vault(explicit: str | None) -> Path | None:
    for cand in (explicit, os.environ.get("MOBLEE_VAULT")):
        if cand and (Path(cand).expanduser() / "wiki").is_dir():
            return Path(cand).expanduser().resolve()
    cfg = CONFIG / "vault-path"
    if cfg.exists():
        p = Path(cfg.read_text().strip()).expanduser()
        if (p / "wiki").is_dir():
            return p.resolve()
    here = Path.cwd().resolve()
    for d in (here, *here.parents):
        if (d / "wiki" / "Index.md").exists():
            return d
    return None


def find_pack() -> Path | None:
    cfg = CONFIG / "package-path"
    if cfg.exists():
        p = Path(cfg.read_text().strip()).expanduser()
        if (p / "scripts" / "install.sh").exists():
            return p
    if (PACK_HERE / "scripts" / "install.sh").exists():
        return PACK_HERE
    return None


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Findings:
    def __init__(self) -> None:
        self.rows: list = []

    def add(self, level: str, text: str, guide: str | None = None) -> None:
        self.rows.append({"level": level, "text": tidy(text), "guide": guide})


def vault_rules(vault: Path | None) -> tuple[list, list]:
    """The permission rules Moblee installs live in the wiki's own settings."""
    allow: list = []
    deny: list = []
    if vault is None:
        return allow, deny
    for name in ("settings.local.json", "settings.json"):
        p = vault / ".claude" / name
        if p.exists():
            try:
                perms = json.loads(p.read_text()).get("permissions", {})
                allow += perms.get("allow", [])
                deny += perms.get("deny", [])
            except (OSError, ValueError):
                pass
    return allow, deny


def check_settings(f: Findings, vault: Path | None) -> dict | None:
    if not SETTINGS.exists():
        f.add(PROBLEM, "Claude has no settings file, so the safety guard is not switched on.", "F02")
        return None
    try:
        data = json.loads(SETTINGS.read_text())
    except (OSError, ValueError) as exc:
        f.add(PROBLEM, f"Claude's settings file does not load ({exc}). Claude should not edit it; the owner restores a copy.", "F03")
        return None
    f.add(OK, "Claude's settings file loads.")
    v_allow, v_deny = vault_rules(vault)
    allow = data.get("permissions", {}).get("allow", []) + v_allow
    deny = data.get("permissions", {}).get("deny", []) + v_deny
    # Moblee's starter rules number about fifty; a handful of the owner's own
    # rules does not mean the starter set is there.
    if len(v_allow) < 10:
        f.add(PROBLEM, "Moblee's permission rules are not in the wiki's settings, so Claude will ask before almost everything.", "F01")
    else:
        f.add(OK, f"Permission rules are in place ({len(allow)} allowed, {len(deny)} refused).")
    return data


def check_guard(f: Findings, settings: dict | None, pack: Path | None) -> None:
    if not GUARD.exists():
        f.add(PROBLEM, "The delete guard is not installed.", "F02")
        return
    registered = False
    if settings:
        for entry in settings.get("hooks", {}).get("PreToolUse", []) or []:
            for h in entry.get("hooks", []) or []:
                if "bash-guard.py" in str(h.get("command", "")):
                    registered = True
    if not registered:
        f.add(PROBLEM, "The delete guard is on the Mac but not switched on in Claude's settings.", "F02")
        return
    if pack and (pack / "safety" / "bash-guard.py").exists():
        if sha(GUARD) == sha(pack / "safety" / "bash-guard.py"):
            f.add(OK, "The delete guard is installed, switched on, and is this Moblee's own copy.")
        else:
            f.add(LOOK, "The delete guard is on, but it is not the same copy as this Moblee's (older, newer, or changed by the owner).", "F02")
    else:
        f.add(OK, "The delete guard is installed and switched on.")


def check_vault(f: Findings, vault: Path | None, pack: Path | None) -> None:
    if vault is None:
        f.add(PROBLEM, "No wiki could be found (no vault-path record, and none above this folder). If the wiki's folder was moved, the record at ~/.config/moblee/vault-path still names the old place; the owner corrects it.")
        return
    f.add(OK, f"The wiki is at {vault}.")
    if not (vault / ".git").exists():
        f.add(PROBLEM, "The wiki has no history (it is not under git), so nothing can be brought back.", "F04")
    else:
        code, out = run(["git", "-C", str(vault), "config", "core.hooksPath"])
        if out.strip() == "scripts/hooks":
            f.add(OK, "The commit gate is wired.")
        else:
            f.add(LOOK, "The commit gate is not wired through scripts/hooks (an older install). The next update does it.", "F11")
        code, out = run(["git", "-C", str(vault), "status", "--porcelain"])
        changed = len([l for l in out.splitlines() if l.strip()]) if code == 0 else 0
        code, out = run(["git", "-C", str(vault), "log", "-1", "--format=%ct"])
        if code == 0 and out.strip().isdigit():
            days = (datetime.datetime.now() - datetime.datetime.fromtimestamp(int(out.strip()))).days
            level = LOOK if (changed and days > 7) else OK
            f.add(level, f"Last commit {days} day(s) ago; {changed} file(s) changed since.")
    vv = (vault / "VERSION").read_text().strip() if (vault / "VERSION").exists() else "unknown"
    pv = (pack / "VERSION").read_text().strip() if pack and (pack / "VERSION").exists() else None
    if pv and vv != pv:
        f.add(LOOK, f"The wiki is on Moblee {vv}; the Moblee on this Mac is {pv}.", "F11")
    else:
        f.add(OK, f"The wiki is on Moblee {vv}.")
    synced = HOME / "Library" / "Mobile Documents" / "com~apple~CloudDocs"
    in_cloud = str(vault).startswith(str(HOME / "Library" / "Mobile Documents"))
    for name in ("Desktop", "Documents"):
        if (synced / name).exists() and str(vault).startswith(str(HOME / name)):
            in_cloud = True
    if in_cloud:
        f.add(LOOK, "The wiki sits inside a folder that iCloud syncs.", "F13")
    lint = vault / "outputs" / "lint"
    reports = sorted(lint.glob("*.md")) if lint.is_dir() else []
    if reports:
        age = (datetime.datetime.now() - datetime.datetime.fromtimestamp(reports[-1].stat().st_mtime)).days
        if age > 14:
            f.add(LOOK, f"The newest health-check report is {age} days old; the weekly check may have stopped.", "F05")
        else:
            f.add(OK, f"The newest health-check report is {age} day(s) old.")
    req = vault / ".moblee" / "requests.json"
    if req.exists():
        try:
            waiting = [r for r in json.loads(req.read_text()).get("requests", []) if r.get("status") == "waiting"]
            if waiting:
                keys = ", ".join(str(r.get("key")) for r in waiting)
                f.add(LOOK, f"{len(waiting)} thing(s) agreed with Claude are waiting in the Moblee app: {keys}.", "F18")
        except (OSError, ValueError):
            f.add(LOOK, "The list of things waiting for the Moblee app does not load; Claude can rewrite it.", "F18")


def check_jobs(f: Findings) -> None:
    plists = sorted(AGENTS.glob("com.moblee.*.plist")) if AGENTS.is_dir() else []
    if not plists:
        f.add(OK, "No Moblee scheduled jobs are set up (the weekly check and the lesson reminder are optional).")
        return
    code, listing = run(["launchctl", "list"])
    if code != 0:
        f.add(LOOK, f"{len(plists)} Moblee scheduled job(s) are set up, but the Mac would not say whether they are loaded.", "F05")
        return
    for p in plists:
        try:
            label = plistlib.loads(p.read_bytes()).get("Label", p.stem)
        except Exception:
            label = p.stem
        line = next((l for l in listing.splitlines() if l.strip().endswith(label)), None)
        if line is None:
            f.add(LOOK, f"The scheduled job {label} is set up but not loaded.", "F05")
            continue
        parts = line.split()
        status = parts[1] if len(parts) >= 3 else "0"
        if status not in ("0", "-"):
            f.add(LOOK, f"The scheduled job {label} ended with an error last time (code {status}).", "F05")
        else:
            f.add(OK, f"The scheduled job {label} is loaded.")


def check_mac(f: Findings) -> None:
    free_gb = shutil.disk_usage(str(HOME)).free / 1e9
    if free_gb < 5:
        f.add(PROBLEM, f"The Mac has {free_gb:.1f} GB free.", "F12")
    else:
        f.add(OK, f"The Mac has {free_gb:.0f} GB free.")
    code, _ = run(["xcode-select", "-p"])
    if code != 0:
        f.add(PROBLEM, "Apple's developer tools are not installed (no git).", "F17")
    code, out = run(["sw_vers", "-productVersion"])
    f.add(OK, f"macOS {out.strip()}, Python {sys.version.split()[0]}, chip {os.uname().machine}.")
    for app, name, note in (("Claude.app", "Claude's app", "fine if Claude Code is used from Terminal"),
                            ("Obsidian.app", "Obsidian", "the wiki works without it; it is the reading window")):
        if (Path("/Applications") / app).exists() or (HOME / "Applications" / app).exists():
            f.add(OK, f"{name} is installed.")
        else:
            f.add(LOOK, f"{name} was not found in Applications ({note}).", None if "Claude" in name else "F16")


def check_skills(f: Findings, pack: Path | None) -> None:
    have = {p.name for p in SKILLS.iterdir() if p.is_dir()} if SKILLS.is_dir() else set()
    if pack and (pack / "skills").is_dir():
        core = {p.name for p in (pack / "skills").iterdir() if p.is_dir()}
        missing = sorted(core - have)
        # A folder of the right name is not enough: it has to be Moblee's skill.
        different = sorted(n for n in core & have
                           if not (SKILLS / n / "SKILL.md").is_file()
                           or sha(SKILLS / n / "SKILL.md") != sha(pack / "skills" / n / "SKILL.md"))
        if missing:
            f.add(PROBLEM if "companion" in missing else LOOK,
                  "Core skills not installed: " + ", ".join(missing) + ".", "F23")
        if different:
            f.add(PROBLEM if "companion" in different else LOOK,
                  "These skills are installed under Moblee's names but are not this Moblee's copies "
                  "(an older version, or something of the owner's own): " + ", ".join(different) + ".", "F23")
        if not missing and not different:
            f.add(OK, f"All {len(core)} core skills are installed, and each is this Moblee's copy.")
    if "get-started" in have and "companion" in have:
        f.add(LOOK, "An old get-started skill sits beside the companion.", "F19")


def check_diary(f: Findings) -> None:
    diary = CONFIG / "install-diary.txt"
    if not diary.exists():
        return
    lines = diary.read_text(errors="replace").splitlines()
    last_begin = max((i for i, l in enumerate(lines) if "begins ===" in l), default=None)
    if last_begin is None:
        return
    what = "update" if "update begins" in lines[last_begin] else "install"
    tail = lines[last_begin:]
    if any("finished ===" in l for l in tail):
        f.add(OK, f"The last {what} ran to the end.")
    else:
        stopped = next((l for l in tail if "stopped during" in l or "FAILED" in l), "it did not reach the end")
        f.add(LOOK, f"The last {what} did not finish: " + tidy(stopped.split("  ", 1)[-1]),
              "F11" if what == "update" else "F02")


def main() -> int:
    ap = argparse.ArgumentParser(description="A read-only check-up of a Moblee wiki.")
    ap.add_argument("--vault")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--report", action="store_true", help="also write a report into the wiki's outputs/ folder")
    args = ap.parse_args()

    f = Findings()
    vault, pack = find_vault(args.vault), find_pack()
    settings = check_settings(f, vault)
    check_guard(f, settings, pack)
    check_vault(f, vault, pack)
    check_skills(f, pack)
    check_jobs(f)
    check_diary(f)
    check_mac(f)

    if args.json:
        print(json.dumps(f.rows, indent=2))
    else:
        print("Moblee check-up (nothing is changed by this)\n")
        for r in f.rows:
            guide = f"  [field guide {r['guide']}]" if r["guide"] and r["level"] != OK else ""
            print(f"  {r['level']:<8} {r['text']}{guide}")
        bad = [r for r in f.rows if r["level"] != OK]
        print("")
        print("Everything looks right." if not bad else
              f"{len(bad)} thing(s) to look at. The field guide (skills/companion/field-guide.md) explains each.")

    if args.report:
        if vault is None:
            print("\nNo wiki was found, so there is nowhere to write the report.")
            return 1
        out_dir = vault / "outputs"
        out_dir.mkdir(exist_ok=True)
        today = datetime.date.today()
        path = out_dir / f"moblee-report-{today.isoformat()}.md"
        n = 2
        while path.exists():  # never overwrite an earlier report
            path = out_dir / f"moblee-report-{today.isoformat()}-{n}.md"
            n += 1
        body = ["---", "do_not_ingest: true", "type: moblee-report", "---", "",
                f"# Moblee check-up report, {today.strftime('%-d %B %Y')}", "",
                "The state of the setup. Nothing here comes from the wiki's pages.", ""]
        def anon(text: str) -> str:
            # the wiki's folder is usually named after its owner, so it is not sent on
            return text.replace(tidy(vault), "<wiki>").replace(vault.name, "<wiki>")

        body += [f"- **{r['level']}** {anon(r['text'])}" + (f" (field guide {r['guide']})" if r["guide"] and r["level"] != OK else "")
                 for r in f.rows]
        body += ["", "## What the owner noticed", "",
                 "*(Claude writes here, in the owner's words, what seemed wrong, leaving out names and page titles, and nothing else.)*", ""]
        path.write_text("\n".join(body))
        print(f"\nReport written to {tidy(path)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
