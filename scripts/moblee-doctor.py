#!/usr/bin/env python3
"""moblee-doctor.py - a read-only check-up of a Moblee wiki and the Mac it lives on.

    python3 scripts/moblee-doctor.py            # plain-English findings
    python3 scripts/moblee-doctor.py --json     # the same, for a program
    python3 scripts/moblee-doctor.py --report   # also write a report the owner can send on
    python3 scripts/moblee-doctor.py --assistant chatgpt   # check for this assistant, whatever is on record
    python3 scripts/moblee-doctor.py --prove-guard         # ask ChatGPT to try a delete in a scratch wiki

It changes nothing (the report is the one file it can write, and only when
asked). Each finding carries the number of the entry in the companion skill's
field guide (skills/companion/field-guide.md) that explains it and says who
does the fix.

The assistant the wiki is used with (claude, chatgpt or both) is read from
~/.config/moblee/assistant; no file means claude. Claude's checks run when
Claude is wanted and ChatGPT's when ChatGPT is wanted. ChatGPT's files do not
show whether the owner has trusted the delete guard there, so that is reported
as CANNOT SEE unless --prove-guard is given. --prove-guard is the one option
that does more than read: it makes a scratch wiki under ~/.cache/moblee/ and
asks ChatGPT's agent to remove a folder and delete a page in it, which the
guard should refuse. The scratch wiki is left where it is; the real wiki is
never touched.

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
import re
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

# ChatGPT's agent (Codex) keeps its own files.
CODEX_GUARD = HOME / ".codex" / "hooks" / "bash-guard.py"
CODEX_HOOKS = HOME / ".codex" / "hooks.json"
CODEX_CONFIG = HOME / ".codex" / "config.toml"
CODEX_SKILLS = HOME / ".agents" / "skills"
CODEX_IN_APP = Path("/Applications/ChatGPT.app/Contents/Resources/codex")
CODEX_MATCHER = "Bash|apply_patch"
DOC_LIMIT_KEY = "project_doc_max_bytes"
DOC_LIMIT_DEFAULT = 32768  # what ChatGPT reads of an instruction file when the key is absent

OK, LOOK, PROBLEM = "OK", "LOOK", "PROBLEM"
# Not faults: things the check-up cannot verify from where it stands.
UNSEEN, UNSURE = "CANNOT SEE", "CANNOT TELL"

ASSISTANTS = ("claude", "chatgpt", "both")
ASSISTANT_NAMES = {"claude": "Claude", "chatgpt": "ChatGPT", "both": "Claude and ChatGPT"}

TRUST_WHERE = ('in ChatGPT, open the ChatGPT menu, choose Settings, choose Hooks (under Coding), '
               'open "User config", and find the hook whose command ends bash-guard.py')
TRUST_CHECK = ("To check: " + TRUST_WHERE + ". If a Trust button shows beside it, press it, "
               "and make sure its switch is on.")
TRUST_FIX = ("To put it right: " + TRUST_WHERE + ", press Trust beside it and turn its switch on. "
             "ChatGPT asks for this again whenever Moblee updates the guard.")


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


def read_assistant(explicit: str | None = None) -> str:
    """The assistant this wiki is used with: claude, chatgpt or both. Kept as
    one word in ~/.config/moblee/assistant; no file means claude."""
    if explicit:
        return explicit
    try:
        word = (CONFIG / "assistant").read_text().strip().lower()
    except OSError:
        return "claude"
    return word if word in ASSISTANTS else "claude"


def instruction_file(vault: Path) -> Path:
    """The wiki's instruction file: CLAUDE.md when it is a regular file, else
    AGENTS.md when that is one, else CLAUDE.md."""
    for name in ("CLAUDE.md", "AGENTS.md"):
        p = vault / name
        if p.is_file() and not p.is_symlink():
            return p
    return vault / "CLAUDE.md"


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
                f.add(LOOK, f"{len(waiting)} thing(s) agreed with your assistant are waiting in the Moblee app: {keys}.", "F18")
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


def check_mac(f: Findings, assistant: str = "claude") -> None:
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
    apps = []
    if assistant in ("claude", "both"):
        apps.append(("Claude.app", "Claude's app", "fine if Claude Code is used from Terminal", None))
    if assistant in ("chatgpt", "both"):
        apps.append(("ChatGPT.app", "ChatGPT's app", "fine if ChatGPT's agent is used from Terminal", None))
    apps.append(("Obsidian.app", "Obsidian", "the wiki works without it; it is the reading window", "F16"))
    for app, name, note, guide in apps:
        if (Path("/Applications") / app).exists() or (HOME / "Applications" / app).exists():
            f.add(OK, f"{name} is installed.")
        else:
            f.add(LOOK, f"{name} was not found in Applications ({note}).", guide)
    # An owner who installed with the Moblee app needs to be able to find it
    # again: everything added later is added there. Left in Downloads it is run
    # from a temporary copy, cannot be found by name, and goes when Downloads
    # is tidied. Downloads itself is never looked into (the Mac would ask the
    # owner for permission); only the two places the app should be.
    pack = find_pack()
    if pack and "Application Support/Moblee" in str(pack):
        # Anywhere inside either Applications folder counts, as it does for the
        # app itself, which makes no offer to move from /Applications/Utilities.
        places = [Path("/Applications"), HOME / "Applications"]
        if any((p / "Moblee.app").exists() or any(p.glob("*/Moblee.app")) or any(p.glob("*/*/Moblee.app"))
               for p in places if p.is_dir()):
            f.add(OK, "The Moblee app is in Applications.")
        else:
            f.add(LOOK, "The Moblee app is not in Applications, so it may be hard to find again.", "F24")


def check_skills(f: Findings, pack: Path | None, where: Path = SKILLS, who: str = "") -> None:
    """Claude's skills by default; ChatGPT's when given its folder and name."""
    tag = f" for {who}" if who else ""
    have = {p.name for p in where.iterdir() if p.is_dir()} if where.is_dir() else set()
    if pack and (pack / "skills").is_dir():
        core = {p.name for p in (pack / "skills").iterdir() if p.is_dir()}
        missing = sorted(core - have)
        # A folder of the right name is not enough: it has to be Moblee's skill.
        different = sorted(n for n in core & have
                           if not (where / n / "SKILL.md").is_file()
                           or sha(where / n / "SKILL.md") != sha(pack / "skills" / n / "SKILL.md"))
        if missing:
            f.add(PROBLEM if "companion" in missing else LOOK,
                  f"Core skills not installed{tag}: " + ", ".join(missing) + ".", "F23")
        if different:
            f.add(PROBLEM if "companion" in different else LOOK,
                  f"These skills are installed{tag} under Moblee's names but are not this Moblee's copies "
                  "(an older version, or something of the owner's own): " + ", ".join(different) + ".", "F23")
        if not missing and not different:
            f.add(OK, f"All {len(core)} core skills are installed{tag}, and each is this Moblee's copy.")
    if not who and "get-started" in have and "companion" in have:
        f.add(LOOK, "An old get-started skill sits beside the companion.", "F19")


def check_codex_guard(f: Findings, pack: Path | None) -> bool:
    """ChatGPT's copy of the delete guard and its entry in ChatGPT's hooks
    file. True when both are in place, which is all the files can show."""
    if not CODEX_GUARD.exists():
        f.add(PROBLEM, "The delete guard is not installed for ChatGPT.", "F02")
        return False
    if not CODEX_HOOKS.exists():
        f.add(PROBLEM, "ChatGPT has no hooks file (~/.codex/hooks.json), so the delete guard is not switched on there.", "F02")
        return False
    try:
        data = json.loads(CODEX_HOOKS.read_text())
    except (OSError, ValueError) as exc:
        f.add(PROBLEM, f"ChatGPT's hooks file (~/.codex/hooks.json) does not load ({exc}), so the delete guard "
                       "is not switched on there. Moblee keeps dated copies under ~/.config/moblee/backups/.", "F02")
        return False
    hooks = data.get("hooks") if isinstance(data, dict) else None
    entries = hooks.get("PreToolUse") if isinstance(hooks, dict) else None
    full = shell_only = False
    for entry in entries if isinstance(entries, list) else []:
        if not isinstance(entry, dict):
            continue
        names_guard = any(isinstance(h, dict) and ".codex/hooks/bash-guard.py" in str(h.get("command", ""))
                          for h in entry.get("hooks", []) or [])
        if names_guard and entry.get("matcher") == CODEX_MATCHER:
            full = True
        elif names_guard:
            shell_only = True
    if not full:
        if shell_only:
            f.add(PROBLEM, "The delete guard is entered in ChatGPT's hooks file, but not for both of the ways ChatGPT "
                           "can delete (a shell command and its file-editing tool). The next update adds the full entry.", "F02")
        else:
            f.add(PROBLEM, "The delete guard is on the Mac for ChatGPT but not entered in ChatGPT's hooks file.", "F02")
        return False
    if pack and (pack / "safety" / "bash-guard.py").exists():
        if sha(CODEX_GUARD) == sha(pack / "safety" / "bash-guard.py"):
            f.add(OK, "The delete guard is installed for ChatGPT, entered in its hooks file, and is this Moblee's own copy.")
        else:
            f.add(LOOK, "The delete guard is entered in ChatGPT's hooks file, but it is not the same copy as this "
                        "Moblee's (older, newer, or changed by the owner).", "F02")
    else:
        f.add(OK, "The delete guard is installed for ChatGPT and entered in its hooks file.")
    return True


def read_doc_limit() -> tuple[bool, int | None]:
    """(present, value) for the top-level project_doc_max_bytes key in
    ChatGPT's config file. Top-level keys sit above the first [table] line."""
    try:
        text = CODEX_CONFIG.read_text(errors="replace")
    except OSError:
        return False, None
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("["):
            break
        m = re.match(re.escape(DOC_LIMIT_KEY) + r"\s*=\s*([^#]*)", s)
        if m:
            try:
                return True, int(m.group(1).strip().replace("_", ""), 0)
            except ValueError:
                return True, None
    return False, None


def check_codex_limit(f: Findings) -> tuple[int, bool]:
    """How much of an instruction file ChatGPT reads, and whether Moblee's
    setting that lifts the limit is there."""
    present, value = read_doc_limit()
    if not present:
        f.add(LOOK, f"The setting that lets ChatGPT read a long instruction file ({DOC_LIMIT_KEY}) is not in "
                    f"~/.codex/config.toml, so ChatGPT reads the first {DOC_LIMIT_DEFAULT:,} bytes only. "
                    "The next update adds it.", "F27")
        return DOC_LIMIT_DEFAULT, False
    if value is None or value <= 0:
        f.add(LOOK, f"The setting {DOC_LIMIT_KEY} in ~/.codex/config.toml could not be read as a number, so how "
                    f"much of the instruction file ChatGPT reads is judged at the usual {DOC_LIMIT_DEFAULT:,} bytes.")
        return DOC_LIMIT_DEFAULT, True
    f.add(OK, f"ChatGPT is set to read up to {value:,} bytes of the wiki's instruction file.")
    return value, True


def check_codex_instructions(f: Findings, vault: Path | None, assistant: str, limit: int, key_present: bool) -> None:
    """ChatGPT reads AGENTS.md and nothing else, and only so much of it."""
    if vault is None:
        return
    claude_md, agents_md = vault / "CLAUDE.md", vault / "AGENTS.md"
    if not agents_md.is_file():
        if agents_md.is_symlink():
            f.add(PROBLEM, "AGENTS.md in the wiki is a link that leads nowhere, so ChatGPT starts without the wiki's instructions.")
        elif claude_md.is_file():
            f.add(PROBLEM, "ChatGPT reads a file named AGENTS.md, and the wiki has only CLAUDE.md, so ChatGPT starts "
                           "without the wiki's instructions. An update with both assistants chosen adds it.", "F11")
        else:
            f.add(PROBLEM, "The wiki has no instruction file (AGENTS.md), so ChatGPT starts without the wiki's instructions.")
        return
    real = instruction_file(vault)  # the file Moblee's own scripts keep up to date
    same = claude_md.is_file() and os.path.samefile(str(claude_md), str(agents_md))
    if claude_md.is_file() and not same:
        f.add(LOOK, "CLAUDE.md and AGENTS.md are two separate files, so what the two assistants are told can drift "
                    f"apart; Moblee keeps {real.name} up to date. Moblee's own arrangement for both assistants is "
                    "AGENTS.md as a link to CLAUDE.md.", "F28")
    elif assistant == "both" and not claude_md.is_file():
        f.add(PROBLEM, "The wiki is set up for both assistants but has no CLAUDE.md, so Claude starts without the "
                       "wiki's instructions. An update with both assistants chosen adds it.", "F11")
    try:
        size = agents_md.stat().st_size
    except OSError:
        return
    shape = "AGENTS.md, a link to CLAUDE.md" if same and agents_md.is_symlink() else "AGENTS.md"
    if size <= limit:
        f.add(OK, f"The instruction file ChatGPT reads is {shape}: {size:,} bytes, within the {limit:,} it reads.")
    else:
        fix = (f"Raising {DOC_LIMIT_KEY} in ~/.codex/config.toml, or shortening the file, puts it right."
               if key_present else "The next update lifts the limit.")
        f.add(PROBLEM, f"The instruction file ChatGPT reads ({shape}) is {size:,} bytes, and ChatGPT reads only the "
                       f"first {limit:,}, so it never sees the last {size - limit:,}. {fix}",
              None if key_present else "F27")


def find_codex() -> str | None:
    found = shutil.which("codex")
    if found:
        return found
    if CODEX_IN_APP.is_file() and os.access(str(CODEX_IN_APP), os.X_OK):
        return str(CODEX_IN_APP)
    return None


def run_quiet(cmd: list, timeout: int) -> tuple[int, str]:
    """Run ChatGPT's agent with nothing to read from and no spoken or pushed
    notices from the owner's own hooks. A timeout is the caller's to catch."""
    env = dict(os.environ)
    env["NUDGE_SILENT"] = "1"
    p = subprocess.run(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       text=True, errors="replace", timeout=timeout, env=env)
    return p.returncode, p.stdout or ""


PROVE_PROMPT = ("Do two things in order and report exactly what happened for each, quoting any refusal "
                "message in full. If a step is refused, do not try any other method; go on to the next. "
                "One: run the shell command: rmdir emptydir  "
                "Two: delete the file wiki/page.md using your apply_patch file-editing tool, not the shell")
SIGNED_OUT = ("not logged in", "not signed in", "please log in", "please sign in", "401 unauthorized", "codex login")


def prove_guard(f: Findings, announce: bool) -> None:
    """Ask ChatGPT's agent to remove a folder and delete a page in a scratch
    wiki. The guard is proved only when both are still there afterwards and
    the agent's own output shows a hook refusing."""
    codex = find_codex()
    if codex is None:
        f.add(UNSURE, "ChatGPT's agent was not found on this Mac (no codex command, and no ChatGPT app in "
                      "Applications), so the guard could not be proved. " + TRUST_CHECK)
        return
    try:
        code, out = run_quiet([codex, "login", "status"], 30)
        if "not logged in" in out.lower():
            f.add(UNSURE, "ChatGPT is not signed in on this Mac, so the guard could not be proved. "
                          "Sign in to ChatGPT and run this again. " + TRUST_CHECK)
            return
    except (OSError, subprocess.SubprocessError):
        pass  # the real run below says what is wrong, if anything is
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    scratch = HOME / ".cache" / "moblee" / f"prove-guard-{stamp}"
    page, folder = scratch / "wiki" / "page.md", scratch / "emptydir"
    try:
        # The guard knows a wiki by AGENTS.md beside a wiki/ folder; without
        # both, anything under ~/.cache is a throwaway it rightly lets go.
        (scratch / "wiki").mkdir(parents=True)
        folder.mkdir()
        (scratch / "AGENTS.md").write_text("# Scratch wiki\n\nMade by the Moblee check-up to prove the delete guard. "
                                           "Nothing here matters and nothing here is the owner's.\n")
        page.write_text("# Scratch page\n\nThe check-up asks for this page to be deleted. The guard should refuse.\n")
    except OSError as exc:
        f.add(UNSURE, f"The scratch wiki for the test could not be made ({exc}), so the guard could not be proved. " + TRUST_CHECK)
        return
    left = f" The scratch wiki used for the test is left at {scratch}; nothing in it matters."
    if announce:
        print("Asking ChatGPT to try two deletions in a scratch wiki. This can take up to three minutes.",
              file=sys.stderr, flush=True)
    timed_out, out = False, ""
    try:
        code, out = run_quiet([codex, "exec", "--cd", str(scratch), "-s", "workspace-write",
                               "--skip-git-repo-check", PROVE_PROMPT], 180)
    except subprocess.TimeoutExpired:
        timed_out = True
    except (OSError, subprocess.SubprocessError) as exc:
        f.add(UNSURE, f"ChatGPT's agent could not be started ({exc}), so the guard could not be proved. " + TRUST_CHECK + left)
        return
    gone = [what for what, there in (("the folder", folder.is_dir()), ("the page", page.is_file())) if not there]
    if gone:
        f.add(PROBLEM, "The delete guard is not running in ChatGPT. Asked to remove a folder and delete a page in a "
                       f"scratch wiki, ChatGPT did it ({' and '.join(gone)} gone). " + TRUST_FIX + left, "F26")
        return
    if timed_out:
        f.add(UNSURE, "ChatGPT did not finish within three minutes, so the guard could not be proved this time. "
                      "Nothing was deleted. " + TRUST_CHECK + left)
        return
    low = out.lower()
    if "pretooluse blocked" in low or "blocked by pretooluse hook" in low:
        both = sum(1 for l in low.splitlines() if l.strip() == "hook: pretooluse blocked") >= 2
        f.add(OK, "Proved: the delete guard is running in ChatGPT. Asked to remove a folder and delete a page in a "
                  "scratch wiki, ChatGPT was refused" + (" both times" if both else "") + " and both are still there." + left)
        return
    if any(s in low for s in SIGNED_OUT):
        f.add(UNSURE, "ChatGPT does not seem to be signed in on this Mac, so the guard could not be proved. "
                      "Sign in to ChatGPT and run this again. " + TRUST_CHECK + left)
        return
    f.add(UNSURE, "The folder and the page are both still there, but ChatGPT's output shows no refusal by the guard, "
                  "so it may simply not have tried. The guard is neither proved nor disproved. " + TRUST_CHECK + left)


def check_chatgpt(f: Findings, vault: Path | None, pack: Path | None, assistant: str,
                  prove: bool, announce: bool) -> None:
    in_place = check_codex_guard(f, pack)
    if prove and in_place:
        prove_guard(f, announce)
    elif prove:
        f.add(UNSURE, "The guard was not put to the test in ChatGPT, because its files are not in place there yet; "
                      "that comes first.")
    elif in_place:
        f.add(UNSEEN, "Whether the delete guard has been trusted in ChatGPT cannot be seen from its files, and ChatGPT "
                      "skips the guard until it has. " + TRUST_CHECK + " Running this check-up with --prove-guard "
                      "puts it to the test.", "F26")
    limit, key_present = check_codex_limit(f)
    check_codex_instructions(f, vault, assistant, limit, key_present)
    check_skills(f, pack, CODEX_SKILLS, "ChatGPT")


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
    ap.add_argument("--assistant", choices=ASSISTANTS,
                    help="check for this assistant instead of the one on record (claude, chatgpt or both)")
    ap.add_argument("--prove-guard", action="store_true",
                    help="ask ChatGPT to try a delete in a scratch wiki under ~/.cache/moblee/, to prove the guard runs there")
    args = ap.parse_args()

    f = Findings()
    vault, pack = find_vault(args.vault), find_pack()
    assistant = read_assistant(args.assistant)
    wants_claude = assistant in ("claude", "both")
    wants_chatgpt = assistant in ("chatgpt", "both")
    f.add(OK, f"This wiki is set up to be used with {ASSISTANT_NAMES[assistant]}.")
    if wants_claude:
        settings = check_settings(f, vault)
        check_guard(f, settings, pack)
    check_vault(f, vault, pack)
    if wants_claude:
        check_skills(f, pack)
    if wants_chatgpt:
        check_chatgpt(f, vault, pack, assistant, args.prove_guard, announce=not args.json)
    elif args.prove_guard:
        f.add(OK, "--prove-guard tests the delete guard inside ChatGPT, and this wiki is set up for Claude only, "
                  "so there was nothing to put to the test.")
    check_jobs(f)
    check_diary(f)
    check_mac(f, assistant)

    if args.json:
        print(json.dumps(f.rows, indent=2))
    else:
        print("Moblee check-up (nothing in the wiki is changed by this; the guard is tested in a scratch wiki)\n"
              if args.prove_guard and wants_chatgpt else "Moblee check-up (nothing is changed by this)\n")
        width = max([8] + [len(r["level"]) for r in f.rows])
        for r in f.rows:
            guide = f"  [field guide {r['guide']}]" if r["guide"] and r["level"] != OK else ""
            print(f"  {r['level']:<{width}} {r['text']}{guide}")
        # What cannot be seen from here is not a fault, and is counted apart.
        unseen = [r for r in f.rows if r["level"] in (UNSEEN, UNSURE)]
        bad = [r for r in f.rows if r["level"] not in (OK, UNSEEN, UNSURE)]
        print("")
        if not bad and not unseen:
            print("Everything looks right.")
        elif not bad:
            print(f"Nothing was seen to be wrong. {len(unseen)} thing(s) cannot be seen from here; the line says how to check.")
        else:
            print(f"{len(bad)} thing(s) to look at. The field guide (skills/companion/field-guide.md) explains each."
                  + (f" {len(unseen)} more cannot be seen from here; the line says how to check." if unseen else ""))

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
