#!/usr/bin/env python3
"""moblee-doctor.py - a read-only check-up of a Moblee wiki and the Mac it lives on.

    python3 scripts/moblee-doctor.py            # plain-English findings
    python3 scripts/moblee-doctor.py --json     # the same, for a program
    python3 scripts/moblee-doctor.py --card     # one screen for whoever is helping the owner
    python3 scripts/moblee-doctor.py --card --json          # the same card, for a program
    python3 scripts/moblee-doctor.py --card-file <path>     # save that card to a file
    python3 scripts/moblee-doctor.py --report   # also write a report the owner can send on
    python3 scripts/moblee-doctor.py --assistant chatgpt   # check for this assistant, whatever is on record
    python3 scripts/moblee-doctor.py --prove-guard         # ask ChatGPT to try a delete in a scratch wiki

It changes nothing (the report and the card file are the only two files it can
write, and only when asked). Every LOOK and PROBLEM carries the number of the entry in the companion
skill's field guide (skills/companion/field-guide.md) that explains it and says
who does the fix. OK lines carry none, having nothing to fix; CANNOT SEE and
CANNOT TELL say in the line itself how to find out.

The assistant the wiki is used with (claude, chatgpt or both) is read from
~/.config/moblee/assistant; no file means claude. Claude's checks run when
Claude is wanted and ChatGPT's when ChatGPT is wanted. ChatGPT's files do not
show whether the owner has trusted the delete guard there, so that is reported
as CANNOT SEE unless --prove-guard is given. --prove-guard is the one option
that does more than read: it makes a scratch wiki under
~/.config/moblee/prove-guard/ (not a place the guard treats as throwaway) and
asks ChatGPT's agent to remove a folder and delete a page in it, which the
guard should refuse. The scratch wiki is left where it is; the real wiki is
never touched.

It also sweeps the wiki for secrets somebody has left in a page: a key, a
token, a password, a wallet recovery phrase. It says the file, the line and the
KIND of secret, and never the secret itself, or any part of it, on the screen,
in the JSON or in the report. It takes nothing out; that is the owner's to do.

The report holds the state of the setup and nothing from the wiki's pages: no
names, no page titles, and the home folder written as "~". Where a finding must
name a file to be useful on the screen (the privacy sweep does), the report
carries the same finding without the names.

--card prints the same findings as one screen for whoever is helping the owner:
whether the wiki is healthy, what is wrong worst first with the field-guide
number beside each, and what to do next. It is redacted exactly as the report
is, so it can be handed to somebody who is not to be shown the wiki. It is a
way of printing the findings and not a second opinion: see card_facts() for why
the card cannot call a wiki healthy while the findings say otherwise.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import importlib.util
import json
import os
import plistlib
import re
import shutil
import signal
import subprocess
import sys
import textwrap
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

# The five steps only the owner can take, in the same words wherever Moblee prints them.
# The sentence before them was found on a real install: the Hooks page lists nothing until then.
TRUST_STEPS = ('First open your wiki folder in ChatGPT (File menu, Open Folder). Until a folder has been '
               'opened in ChatGPT, its Hooks page is empty and does not say why. '
               '1. Open the ChatGPT menu and choose Settings. 2. Choose Hooks, under the heading Coding. '
               '3. Open "User config". 4. Press Trust beside the hook that ends bash-guard.py. '
               '5. Turn its switch on. If ChatGPT was open during this, quit it and open it again so that '
               'it reads the whole rules file.')
TRUST_PROVE = ("Then prove it: python3 scripts/moblee-doctor.py --prove-guard (run from the Moblee folder; "
               "in the Moblee app, press Prove the guard). It uses a little of your ChatGPT allowance.")
# ChatGPT keeps its trust by the hook's entry in hooks.json, and takes no account of the guard
# file the entry runs (seen on a real update, 21 September 2026).
TRUST_AGAIN = ("ChatGPT keeps its trust while Moblee's entry in its hooks list stays the same, so an "
               "ordinary Moblee update does not need these steps again. If an update ever does need "
               "them, Moblee says so at the end of the update and ChatGPT will not remind you. After "
               "any update, prove the guard again.")
TRUST_CHECK = "To check, and to put it right if need be: " + TRUST_STEPS + " " + TRUST_AGAIN
TRUST_FIX = "To put it right: " + TRUST_STEPS + " " + TRUST_AGAIN


def tidy(text: str) -> str:
    """No account name in anything printed: the home folder becomes ~."""
    return str(text).replace("/private" + str(HOME), "~").replace(str(HOME), "~")


def run(cmd: list, timeout: int = 20) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except (OSError, subprocess.SubprocessError) as exc:
        return 1, str(exc)


# (v0.9.2) The vault's path before resolving. With Desktop & Documents sync
# turned on, ~/Desktop IS a link into Mobile Documents, so a resolved path no
# longer begins with ~/Desktop and the F29 check for that very folder was
# skipped on exactly the Macs that needed it. The installer, which tests the
# string the owner typed, got it right — so the check-up silently contradicted
# what the installer had told the same owner.
VAULT_AS_NAMED: Path | None = None


def find_vault(explicit: str | None) -> Path | None:
    global VAULT_AS_NAMED
    for cand in (explicit, os.environ.get("MOBLEE_VAULT")):
        if cand and (Path(cand).expanduser() / "wiki").is_dir():
            VAULT_AS_NAMED = Path(cand).expanduser()
            return VAULT_AS_NAMED.resolve()
    cfg = CONFIG / "vault-path"
    if cfg.exists():
        p = Path(cfg.read_text().strip()).expanduser()
        if (p / "wiki").is_dir():
            VAULT_AS_NAMED = p
            return p.resolve()
    here = Path.cwd().resolve()
    for d in (here, *here.parents):
        if (d / "wiki" / "Index.md").exists():
            VAULT_AS_NAMED = d
            return d
    return None


# Where macOS blocks a scheduled job, by every name the folder goes under. The
# iCloud forms matter because that is what ~/Desktop resolves to once Desktop &
# Documents sync is on, which is the case this check kept missing.
ICLOUD = Path.home() / "Library" / "Mobile Documents" / "com~apple~CloudDocs"
PROTECTED_ROOTS = [("Desktop", Path.home() / "Desktop"), ("Documents", Path.home() / "Documents"),
                   ("Downloads", Path.home() / "Downloads"),
                   ("Desktop", ICLOUD / "Desktop"), ("Documents", ICLOUD / "Documents")]


def protected_folder(vault: Path) -> str | None:
    """The name of the protected folder this wiki sits in, by any of its paths."""
    for cand in (vault, VAULT_AS_NAMED):
        if cand is None:
            continue
        for name, root in PROTECTED_ROOTS:
            if str(cand) == str(root) or str(cand).startswith(str(root) + os.sep):
                return name
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
    return choice_on_record() or "claude"


def choice_on_record() -> str | None:
    """The word in ~/.config/moblee/assistant, read as the installer and the
    updater read it: the first line, spaces dropped, and the word exactly as
    they write it. No file, or anything else in it, is no choice (None)."""
    try:
        text = (CONFIG / "assistant").read_text(errors="replace")
    except OSError:
        return None
    word = "".join(text.split("\n", 1)[0].split())
    return word if word in ASSISTANTS else None


def looks_made_for_chatgpt(vault: Path | None) -> bool:
    """A wiki made for ChatGPT alone, told from what is on the disk, as the
    updater tells it: AGENTS.md is the real rules file, and CLAUDE.md is either
    not there or is the link to it that 0.9 lays down. Where CLAUDE.md is a
    link, the wiki's VERSION must be 0.9 or later and Claude's permission
    rules must not be in it, so that an owner of Claude who made such a link
    by hand is never taken for an owner of ChatGPT."""
    if vault is None:
        return False
    claude_md, agents_md = vault / "CLAUDE.md", vault / "AGENTS.md"
    if not (agents_md.is_file() and not agents_md.is_symlink()):
        return False
    if not claude_md.exists() and not claude_md.is_symlink():
        return True
    try:
        if not (claude_md.is_symlink() and os.path.samefile(str(claude_md), str(agents_md))):
            return False
    except OSError:
        return False
    if (vault / ".claude" / "settings.local.json").is_file() or not (vault / "VERSION").is_file():
        return False
    try:
        version = (vault / "VERSION").read_text(errors="replace").strip()
    except OSError:
        return False
    return bool(version) and not re.match(r"0\.[0-8](\.|$)", version)


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

    def add(self, level: str, text: str, guide: str | None = None, sendable: str | None = None) -> None:
        # "sendable" is the same finding written for a report the owner may send
        # on, and is given only where the two must differ. The privacy sweep
        # names files, and a file's name is a page title, which the report
        # promises never to carry; so the sweep says it on the screen and says
        # it without the names in the report. The key is left off every other
        # row, so what a program reads is unchanged.
        row = {"level": level, "text": tidy(text), "guide": guide}
        if sendable is not None:
            row["sendable"] = tidy(sendable)
        self.rows.append(row)


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
        f.add(UNSEEN,
              "The delete guard is installed and switched on, but the Moblee folder could not be found, "
              "so it could not be compared with Moblee's own copy. That comparison is what shows the "
              "guard has not been swapped or edited, and it is the one the safety guide tells you to "
              "rely on. Run the check-up from the Moblee folder to make it.", "F31")


def check_vault(f: Findings, vault: Path | None, pack: Path | None) -> None:
    if vault is None:
        f.add(PROBLEM, "No wiki could be found (no vault-path record, and none above this folder). If the wiki's folder was moved, the record at ~/.config/moblee/vault-path still names the old place; the owner corrects it.", "F37")
        return
    f.add(OK, f"The wiki is at {vault}.")
    if not (vault / ".git").exists():
        f.add(PROBLEM, "The wiki has no history (it is not under git), so nothing can be brought back.", "F04")
    else:
        code, out = run(["git", "-C", str(vault), "config", "core.hooksPath"])
        if out.strip() == "scripts/hooks":
            f.add(OK, "The commit gate is wired.")
        else:
            f.add(LOOK, "The commit gate is not wired through scripts/hooks (an older install). The next update does it.", "F32")
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
    # (v0.9.1) A separate fault with the same folders and a different cause.
    # macOS protects Desktop, Documents and Downloads, and a scheduled job runs
    # without the permission a person's own Terminal has, so it fails with
    # "Operation not permitted" and nothing is shown. A real owner's nightly
    # reminder had almost certainly never run unattended, and his weekly job
    # failed the same way, for five days, unnoticed (21 September 2026). This is
    # true whether or not iCloud is syncing the folder, so it is its own check.
    protected = protected_folder(vault)
    if protected:
        f.add(PROBLEM,
              f"The wiki is inside your {protected} folder, where macOS blocks scheduled jobs. "
              f"Anything Moblee runs on a schedule — the evening lesson, the weekly health check — "
              f"will fail silently there. Moving the wiki out of {protected} fixes it.",
              "F29")
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


def moblee_apps() -> list:
    """Every copy of the Moblee app in either Applications folder, at the three
    depths the app itself allows (it makes no offer to move out of, say,
    /Applications/Utilities). The paths are kept, so the check-up can say which
    copy it found rather than only that it found one."""
    found: list = []
    for place in (Path("/Applications"), HOME / "Applications"):
        if not place.is_dir():
            continue
        for pattern in ("Moblee.app", "*/Moblee.app", "*/*/Moblee.app"):
            for app in sorted(place.glob(pattern)):
                if app.is_dir() and app not in found:
                    found.append(app)
    return found


def app_version(app: Path) -> str:
    """The version and build written inside an app, from its own Info.plist."""
    try:
        data = plistlib.loads((app / "Contents" / "Info.plist").read_bytes())
    except (OSError, ValueError, plistlib.InvalidFileException):
        return "version unknown"
    if not isinstance(data, dict):
        return "version unknown"
    version = str(data.get("CFBundleShortVersionString") or "").strip()
    build = str(data.get("CFBundleVersion") or "").strip()
    if not version:
        return "version unknown"
    if build and build != version:
        return f"version {version} (build {build})"
    return f"version {version}"


# (v0.9.4) Three families of folder that Moblee makes and, by design, never
# removes: a folder for every version of the pack ever settled, a dated folder
# for every file an install, an update or a repair replaced, and a scratch wiki
# for every guard proof. Never deleting them is right — they are what an owner
# is told to restore from — but nothing had ever told the owner they were there,
# or how much room they were taking, so they grew unseen. This says so. It reads
# and counts; it removes nothing, and it never offers to.
LEFTOVER_MAX_FILES = 200_000


def folder_size(path: Path) -> tuple[int, bool]:
    """How many bytes a folder holds, counted without following links, and
    whether the count is the whole of it.

    (v0.9.4) The walk stops after LEFTOVER_MAX_FILES files so that a check-up
    never hangs on a folder nobody expected to be enormous. It used to return
    the part-total on its own, and the owner was then shown that figure as the
    size of the folder, which is simply not true and is always an understatement.
    The second value says whether the walk finished, so the line can say "at
    least" when it did not."""
    total = seen = 0
    for dirpath, dirnames, filenames in os.walk(path, followlinks=False):
        for name in filenames:
            seen += 1
            if seen > LEFTOVER_MAX_FILES:
                return total, False
            try:
                total += (Path(dirpath) / name).lstat().st_size
            except OSError:
                pass
    return total, True


def in_room(nbytes: int) -> str:
    """A size an owner can picture, in the units a Mac shows."""
    if nbytes >= 1_000_000_000:
        return f"{nbytes / 1_000_000_000:.1f} GB"
    if nbytes >= 1_000_000:
        return f"{nbytes / 1_000_000:.0f} MB"
    return f"{max(nbytes // 1000, 1)} KB"


def check_leftovers(f: Findings, pack: Path | None) -> None:
    """The old pack folders, the backup folders and the scratch wikis Moblee
    keeps for ever. Nothing is wrong with them; the owner is simply told they
    are there and may clear them by hand."""
    live = None
    if pack is not None:
        try:
            live = pack.resolve()
        except OSError:
            live = pack
    groups = []
    support = HOME / "Library" / "Application Support" / "Moblee"
    packs = []
    if support.is_dir():
        for p in sorted(support.glob("pack-*")):
            if not p.is_dir():
                continue
            try:
                # The pack the record points at is the one in use: removing that
                # one would break the install, so it is left out of the count.
                if live is not None and p.resolve() == live:
                    continue
            except OSError:
                pass
            packs.append(p)
    groups.append(("old pack folder(s), one for each version of Moblee ever installed", packs, tidy(support)))
    for name, what in (("backups", "backup folder(s), holding files an install, an update or a repair replaced"),
                       ("prove-guard", "scratch wiki folder(s) left by guard proofs")):
        here = CONFIG / name
        dated = sorted(p for p in here.iterdir() if p.is_dir()) if here.is_dir() else []
        groups.append((what, dated, tidy(here)))
    kept = [g for g in groups if g[1]]
    if not kept:
        return
    total = 0
    parts = []
    all_counted = True
    for what, dirs, where in kept:
        size, whole = 0, True
        for d in dirs:
            bytes_here, finished = folder_size(d)
            size += bytes_here
            whole = whole and finished
        total += size
        all_counted = all_counted and whole
        # "At least" where the walk was cut short: the figure is then a floor and
        # not a measurement, and an owner deciding what to clear out should be
        # told which of the two they are reading.
        parts.append(f"{len(dirs)} {what} in {where}, "
                     f"{'at least' if not whole else 'about'} {in_room(size)}")
    # Said only when there are pack folders to say it about, and only when the
    # copy in use was really found: with no record of it, every pack folder is
    # counted, the one in use among them, and the owner must be told that rather
    # than promised otherwise.
    note = ""
    if packs:
        note = (" The copy of Moblee in use is not among them."
                if live is not None else
                " Which one is in use could not be worked out from here, so they are all counted; "
                "leave the newest of them alone.")
    in_all = (f"That is about {in_room(total)} in all." if all_counted else
              f"That is at least {in_room(total)} in all: one of those folders holds more than "
              f"{LEFTOVER_MAX_FILES:,} files, so the count was stopped there and the real figure is "
              "larger.")
    f.add(OK, "Moblee keeps what it replaces and never removes it: "
              + "; ".join(parts) + f". {in_all} Nothing is wrong "
              "and nothing needs doing. Moblee never removes these; you may remove them by hand "
              "if you want the room back, oldest first." + note)


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
        apps.append(("Claude.app", "Claude's app", "fine if Claude Code is used from Terminal", "F39"))
    if assistant in ("chatgpt", "both"):
        apps.append(("ChatGPT.app", "ChatGPT's app", "fine if ChatGPT's agent is used from Terminal", "F39"))
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
        # (v0.9.4) Which copy, and which version. The old line said only that a
        # copy was somewhere in Applications and threw the path away, so an
        # owner with two copies — which happens, because a move leaves the older
        # one in the Bin under a name that can be seen — could not tell them
        # apart, and could not tell which one the line was about.
        copies = moblee_apps()
        if copies:
            said = "; ".join(f"{tidy(p)}, {app_version(p)}" for p in copies)
            f.add(OK, ("The Moblee app is in Applications: " + said + "."
                       if len(copies) == 1 else
                       f"There are {len(copies)} copies of the Moblee app in Applications: " + said
                       + ". More than one is not a fault; the version beside each says which is which."))
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
    elif have:
        f.add(UNSEEN,
              f"{len(have)} skill folder(s) are installed{tag}, but the Moblee folder could not be found, "
              "so whether they are Moblee's own copies, and whether any are missing, could not be checked. "
              "Run the check-up from the Moblee folder.", "F31")
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
        f.add(UNSEEN,
              "The delete guard is installed for ChatGPT and entered in its hooks file, but the Moblee "
              "folder could not be found, so it could not be compared with Moblee's own copy. Run the "
              "check-up from the Moblee folder to make that comparison.", "F31")
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
                    f"much of the instruction file ChatGPT reads is judged at the usual {DOC_LIMIT_DEFAULT:,} bytes.",
                  "F38")
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
            f.add(PROBLEM, "AGENTS.md in the wiki is a link that leads nowhere, so ChatGPT starts without the wiki's instructions.",
                  "F33")
        elif claude_md.is_file():
            f.add(PROBLEM, "ChatGPT reads a file named AGENTS.md, and the wiki has only CLAUDE.md, so ChatGPT starts "
                           "without the wiki's instructions. An update with both assistants chosen adds it.", "F33")
        else:
            f.add(PROBLEM, "The wiki has no instruction file (AGENTS.md), so ChatGPT starts without the wiki's instructions.",
                  "F33")
        return
    real = instruction_file(vault)  # the file Moblee's own scripts keep up to date
    try:
        same = claude_md.is_file() and os.path.samefile(str(claude_md), str(agents_md))
    except OSError:
        same = False
    claude_real = claude_md.is_file() and not claude_md.is_symlink()
    agents_real = not agents_md.is_symlink()
    if claude_real and agents_real:
        # Two files of their own. Moblee's scripts write to CLAUDE.md; ChatGPT reads the other.
        try:
            equal = claude_md.read_bytes() == agents_md.read_bytes()
        except OSError:
            equal = False
        f.add(PROBLEM, "CLAUDE.md and AGENTS.md are two separate files. ChatGPT reads AGENTS.md only, and Moblee writes "
                       "its rules and rule updates into CLAUDE.md only, so ChatGPT is not getting Moblee's rules or "
                       "its updates until the two are made one."
                       + (" The two are the same, word for word: most likely AGENTS.md was a link to CLAUDE.md and the "
                          "link was lost in syncing, which left a copy in its place." if equal else "")
                       + " Moblee's own arrangement for both assistants is AGENTS.md as a link to CLAUDE.md.", "F28")
    elif claude_md.is_file() and not same:
        f.add(LOOK, "CLAUDE.md and AGENTS.md do not lead to the same file, so what the two assistants are told can drift "
                    f"apart; Moblee keeps {real.name} up to date. Moblee's own arrangement for both assistants is "
                    "AGENTS.md as a link to CLAUDE.md.", "F28")
    elif assistant == "both" and not claude_md.is_file():
        f.add(PROBLEM, "The wiki is set up for both assistants but has no CLAUDE.md, so Claude starts without the "
                       "wiki's instructions. An update with both assistants chosen adds it.", "F33")
    elif assistant == "chatgpt" and agents_real and not claude_md.exists() and not claude_md.is_symlink():
        f.add(LOOK, "The wiki has no CLAUDE.md link beside AGENTS.md. ChatGPT does not need one, but an older copy of "
                    "the Moblee app would not recognise this wiki; the next update adds it.", "F33")
    # A rules file that holds almost nothing: most often a link that a syncing
    # tool turned into a small file whose whole text is the other file's name.
    for md, other in ((agents_md, "CLAUDE.md"), (claude_md, "AGENTS.md")):
        if not (md.is_file() and not md.is_symlink()):
            continue
        try:
            raw = md.read_bytes()
        except OSError:
            continue
        if len(raw) < 200 or raw.strip() == other.encode():
            stub = raw.strip() == other.encode()
            f.add(PROBLEM, f"{md.name} holds almost nothing ({len(raw):,} bytes)"
                           + (f": its whole text is the name {other}, which is what a link looks like once a syncing "
                              "tool has turned it into a file" if stub else "")
                           + (". ChatGPT reads this file, so it starts without the wiki's instructions."
                              if md.name == "AGENTS.md" else
                              ". Moblee's scripts take it for the rules file, so rule updates would go to it and not "
                              "to the real one.")
                           + " Nothing was changed.", "F28")
            if md.name == "AGENTS.md":
                return  # the size line below would call this file fine
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
    # A session of its own, so that a run that overstays is ended together with
    # everything it started (its shell, any helper programs of the owner's),
    # and nothing is left running and using the owner's allowance.
    p = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         text=True, errors="replace", env=env, start_new_session=True)

    # The Moblee app ends a proof by ending this check-up. The agent is in a
    # session of its own, so it is ended here, by hand, when that happens.
    def ended(signum, frame):  # noqa: ARG001
        raise SystemExit(1)

    before = signal.signal(signal.SIGTERM, ended)
    try:
        out, _ = p.communicate(timeout=timeout)
    except BaseException:  # a timeout, or the check-up itself being ended: the agent does not outlive either
        end_group(p)
        raise
    finally:
        signal.signal(signal.SIGTERM, before if before is not None else signal.SIG_DFL)
    return p.returncode, out or ""


def end_group(p: subprocess.Popen) -> None:
    """End a program started by run_quiet, and everything it started. What it
    had printed so far is let go; the caller judges by what is on the disk."""
    try:
        os.killpg(p.pid, signal.SIGTERM)
    except OSError:
        pass
    try:
        p.wait(timeout=5)
    except (subprocess.TimeoutExpired, OSError):
        pass
    try:
        os.killpg(p.pid, signal.SIGKILL)  # whatever is left of the group
    except OSError:
        pass
    try:
        if p.stdout:
            p.stdout.close()
    except OSError:
        pass
    try:
        p.wait(timeout=5)
    except (subprocess.TimeoutExpired, OSError):
        pass


PROVE_PROMPT = ("Do two things in order and report exactly what happened for each, quoting any refusal "
                "message in full. If a step is refused, do not try any other method; go on to the next. "
                "One: run the shell command: rmdir emptydir  "
                "Two: delete the file wiki/page.md using your apply_patch file-editing tool, not the shell")
SIGNED_OUT = ("not logged in", "not signed in", "please log in", "please sign in", "401 unauthorized", "codex login")


ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
# The line ChatGPT's agent itself writes when a hook refuses a tool call, as seen
# in real runs (20 September 2026):
#   2026-09-20T20:42:57.853625Z ERROR codex_core::tools::router: error=Command blocked by PreToolUse hook: Blocked by ...
# It begins with a time and the word ERROR. The model's own account of what
# happened never does, and is never taken as evidence.
ROUTER_REFUSAL = re.compile(r"^\d{4}-\d\d-\d\dt\S+\s+error\s+\S+\s+error=command blocked by pretooluse hook:(.*)$")  # matched against the line in small letters


def read_refusals(out: str) -> tuple[bool, bool, int]:
    """What the agent's own program printed about refusals, and nothing the
    model said: (the shell's rmdir was refused by the guard, the file-editing
    tool's delete was refused by the guard, how many "hook: PreToolUse Blocked"
    lines there were). A refusal counts for a route only when its line names
    the guard (bash-guard.py) and that route, so that another hook's refusal,
    or a refusal of one route alone, is never taken for proof of both."""
    shell = patch = False
    blocked = 0
    for line in out.splitlines():
        low = ANSI.sub("", line).strip().lower()
        if low == "hook: pretooluse blocked":
            blocked += 1
            continue
        m = ROUTER_REFUSAL.match(low)
        if not m or "bash-guard.py" not in m.group(1):
            continue
        said = m.group(1)
        if "apply_patch" in said or "delete file" in said:
            patch = True
        elif "rmdir" in said:
            shell = True
    return shell, patch, blocked


# How long ChatGPT's agent is given before the proof is given up on. Three
# minutes is what an owner is told, on screen and in the field guide. It is a
# name rather than a number written into the line below so that a test can give
# itself a shorter one and still run the very same code, the kill of the whole
# process group among it, in a second or two instead of three minutes.
PROVE_TIMEOUT = 180

# (v0.9.4) The limit in words, worked out from the number above. "Three minutes"
# used to be typed out by hand in two places here, and the test insisted on the
# same three words, so changing PROVE_TIMEOUT would have left every line and
# every test passing and every one of them wrong: the owner would be told three
# minutes and given something else. Saying it once, from the number, is what
# stops that.
NUMBER_WORDS = ("no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten")


def in_words(n: int) -> str:
    """A small whole number as an owner would read it aloud."""
    return NUMBER_WORDS[n] if 0 <= n < len(NUMBER_WORDS) else f"{n:,}"


def prove_limit_words(limit: int | None = None) -> str:
    """How long the guard proof is given, in the words the owner is told."""
    seconds = PROVE_TIMEOUT if limit is None else limit
    if seconds >= 60 and seconds % 60 == 0:
        minutes = seconds // 60
        return f"{in_words(minutes)} minute" + ("" if minutes == 1 else "s")
    return f"{in_words(seconds)} second" + ("" if seconds == 1 else "s")


def prove_guard(f: Findings, announce: bool, timeout: int | None = None) -> None:
    """Ask ChatGPT's agent to remove a folder and delete a page in a scratch
    wiki. The guard is proved only when both are still there afterwards and
    the agent's own output shows a hook refusing."""
    limit = PROVE_TIMEOUT if timeout is None else timeout
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
    # The scratch wiki is kept out of every place the guard treats as throwaway
    # (~/.cache, the system's temporary folders, ~/.config/moblee/logs), so a
    # refusal there is plainly the guard's and owes nothing to where the folder is.
    scratch = CONFIG / "prove-guard" / stamp
    page, folder = scratch / "wiki" / "page.md", scratch / "emptydir"
    try:
        # The guard knows a wiki by AGENTS.md beside a wiki/ folder, so the
        # scratch folder is given both.
        (scratch / "wiki").mkdir(parents=True)
        folder.mkdir()
        # Neither file says what is being tested or what is expected to happen:
        # the agent reads them, and one told that a refusal is expected may not
        # try at all, or may describe a refusal that never took place.
        (scratch / "AGENTS.md").write_text("# Scratch wiki\n\nA scratch folder made by Moblee. "
                                           "Nothing here matters and nothing here is the owner's.\n")
        page.write_text("# Scratch page\n\nA page with nothing on it that matters.\n")
    except OSError as exc:
        f.add(UNSURE, f"The scratch wiki for the test could not be made ({exc}), so the guard could not be proved. " + TRUST_CHECK)
        return
    left = f" The scratch wiki used for the test is left at {scratch}; nothing in it matters."
    try:
        earlier = sorted(p.name for p in scratch.parent.iterdir() if p.is_dir() and p != scratch)
    except OSError:
        earlier = []
    if earlier:
        left += (f" Moblee never removes these; {len(earlier)} from earlier tests are beside it"
                 f" (the latest: {', '.join(earlier[-3:])}) and can be removed by hand.")
    if announce:
        print("Asking ChatGPT to try two deletions in a scratch wiki. This can take up to "
              f"{prove_limit_words(limit)}.", file=sys.stderr, flush=True)
    timed_out, out = False, ""
    try:
        code, out = run_quiet([codex, "exec", "--cd", str(scratch), "-s", "workspace-write",
                               "--skip-git-repo-check", PROVE_PROMPT], limit)
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
        f.add(UNSURE, f"ChatGPT did not finish within {prove_limit_words(limit)}, so the guard could not be "
                      "proved this time. Nothing was deleted. " + TRUST_CHECK + left)
        return
    shell_refused, patch_refused, blocked_lines = read_refusals(out)
    if shell_refused and patch_refused and blocked_lines >= 2:
        f.add(OK, "Proved: asked through ChatGPT's agent to remove a folder and delete a page in a scratch wiki, "
                  "it was refused both times and both are still there." + left)
        return
    low = out.lower()
    if any(s in low for s in SIGNED_OUT):
        f.add(UNSURE, "ChatGPT does not seem to be signed in on this Mac, so the guard could not be proved. "
                      "Sign in to ChatGPT and run this again. " + TRUST_CHECK + left)
        return
    if shell_refused or patch_refused or blocked_lines:
        seen = ("the shell command (rmdir) was refused, but no refusal of the file-editing tool's delete was seen"
                if shell_refused and not patch_refused else
                "the file-editing tool's delete was refused, but no refusal of the shell command (rmdir) was seen"
                if patch_refused and not shell_refused else
                "a refusal was seen, but not one that can be tied to each of the two ways of deleting")
        f.add(UNSURE, "The folder and the page are both still there, but the guard is proved only when ChatGPT's agent "
                      f"is seen to be refused both ways, and here {seen}. ChatGPT may not have tried one of them, or an "
                      "older guard that watches the shell alone may have done the refusing. The guard is neither "
                      "proved nor disproved. " + TRUST_CHECK + left)
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
                      "skips the guard until it has. To check, and to put it right if need be: "
                      + TRUST_STEPS + " " + TRUST_PROVE + " " + TRUST_AGAIN, "F26")
    limit, key_present = check_codex_limit(f)
    check_codex_instructions(f, vault, assistant, limit, key_present)
    check_skills(f, pack, CODEX_SKILLS, "ChatGPT")


# (v0.9.1) The commit gate refuses a commit when one of the always-loaded files
# is over its cap, and it refuses EVERY commit in the vault, not only Moblee's.
# Nothing told an owner they were near the line: the first they knew was a
# refusal with a rule name in it, which is what happened on 21 September 2026.
# The figures match scripts/vault-gate.py and scripts/lint-v2.py; a vault whose
# copy of the gate is older may still hold a lower cap, and this says so.
WEIGHT_CAPS = (("wiki/_context.md", 12000), ("wiki/Index.md", 8000))
INSTRUCTION_CAP = 16000


def check_weights(f: Findings, vault: Path | None) -> None:
    """How near the always-loaded files are to the size the commit gate allows."""
    if vault is None:
        return
    rules = None
    for name in ("CLAUDE.md", "AGENTS.md"):
        p = vault / name
        if p.is_file() and not p.is_symlink():
            rules = (name, INSTRUCTION_CAP)
            break
    checks = list(WEIGHT_CAPS) + ([rules] if rules else [])
    over, near = [], []
    rules_told = False
    for rel, cap in checks:
        p = vault / rel
        if not p.is_file():
            continue
        try:
            tok = len(p.read_text(errors="replace")) // 4
        except OSError:
            continue
        if tok > cap:
            over.append(f"{rel} at about {tok:,} tokens, over its {cap:,}")
            if rules and rel == rules[0]:
                rules_told = True
        elif cap - tok < 1000:
            near.append(f"{rel} at about {tok:,} tokens, within {cap - tok:,} of its {cap:,}")
            # A "near" line is only printed when nothing is over, so the rules
            # file's figure only counts as told when it will really be shown.
            if rules and rel == rules[0] and not over:
                rules_told = True
        if rules and rel == rules[0] and not rules_told:
            # (v0.9.4) The rules file's own figure is said whether it is near
            # the line or not. It is the file v0.9.4 set out to shorten, so an
            # owner who wants to know whether that worked should not have to
            # guess.
            #
            # It is said ONCE. This used to go out as an OK even when the file
            # was over its cap, one line above the PROBLEM saying so, so the
            # owner read "here is the figure, all well" and then "every commit
            # in this vault is refused": two answers to one question, the
            # reassuring one first. Where the file is over the line, or near it
            # with nothing else over, the PROBLEM or LOOK below carries the same
            # figure and the same cap, so nothing is lost by staying quiet here.
            f.add(OK, f"{rel}, which your assistant reads at the start of every session, is about "
                      f"{tok:,} tokens, against a cap of {cap:,}.")
            rules_told = True
    if over:
        f.add(PROBLEM,
              "A file your assistant reads at every session is over the size the commit gate allows ("
              + "; ".join(over) + "). While it is, every commit in this vault is refused, not only "
              "Moblee's. Ask your assistant to shorten it: move the parts you rarely need into a page "
              "of their own and link to it.",
              "F30")
    elif near:
        f.add(LOOK,
              "A file your assistant reads at every session is close to the size the commit gate allows ("
              + "; ".join(near) + "). Over the line, every commit in this vault is refused. Worth "
              "shortening before that happens.",
              "F30")
    elif checks:
        f.add(OK, "The files your assistant reads at every session are well within their size caps.")


# (v0.9.4) In v0.9.4 the rules file was cut from about 9,000 tokens to about
# 3,700, and the updater brings an existing owner's file down with it: it
# replaces the sections Moblee wrote and drops the ones whose content moved to a
# page of its own. It only touches a section the owner has not written in. That
# is right, but it means two owners can run the same update and end up with
# files of very different length, and the one left with a long file deserves to
# be told why rather than left wondering. This says so, by name, and says what
# it means. It is worked out fresh here, by asking the updater's own engine what
# it WOULD do to the file as it stands: reading whatever the last run happened
# to print would go stale the moment the owner edited the file again.
def owner_sections(engine, path: Path) -> list:
    """The sections of a rules file that Moblee never wrote, as (heading, how
    many tokens it is). Worked out with the updater's own reader, so a heading
    inside a fenced code block is content here too, and a section Moblee once
    used a different heading for still counts as Moblee's. Tokens are characters
    divided by four, the same count the commit gate uses."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        lines = text.split("\n")
        heads = engine.heading_lines(lines)
        moblees = {engine.heading_key(n)
                   for heading, aliases, _action, _page in engine.SECTIONS
                   for n in (heading, *aliases)}
    except Exception:
        return []
    mine = []
    for n, i in enumerate(heads):
        end = heads[n + 1] if n + 1 < len(heads) else len(lines)
        heading = lines[i][3:].strip()
        if engine.heading_key(heading) in moblees:
            continue
        mine.append((heading, len("\n".join(lines[i:end])) // 4))
    return mine


def check_rules_sections(f: Findings, vault: Path | None, pack: Path | None) -> None:
    if vault is None:
        return
    if pack is None:
        return                       # already reported as F31; nothing to add
    engine_path = pack / "scripts" / "patch-claude-md.py"
    if not engine_path.is_file():
        return
    try:
        spec = importlib.util.spec_from_file_location("patch_claude_md", engine_path)
        engine = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(engine)
        path, plan = engine.review(vault)
    except Exception:                # an older or half-copied pack: say nothing
        return
    if plan is None:
        return                       # no rules file; other checks report that
    name = path.name
    # (v0.9.4) Two very different states set plan.untouched, and until now both
    # were told to the owner in the same words. One is about their file: none of
    # its sections is still Moblee's wording. The other is about this Mac:
    # Moblee's own copy of the rules file is not in the folder being read, so
    # there is nothing to compare against and the question was never asked. An
    # owner with a half-copied pack was being told they had edited every section
    # of their own file, which is a statement about their writing made on no
    # evidence at all. The engine's own test decides which it is.
    if plan.untouched:
        try:
            have_template = bool(engine.load_template()[0])
        except Exception:
            have_template = False
        if not have_template:
            f.add(UNSEEN,
                  f"Whether {name} was shortened by the update could not be worked out. Moblee's own "
                  f"copy of the rules file is not in the Moblee folder this check-up is reading "
                  f"({tidy(pack)}), so there is nothing to compare yours against. Nothing is wrong "
                  "with your wiki, and nothing here says anything about what you have written. To "
                  "find out, run the check-up from a complete Moblee folder — go to where Moblee was "
                  "downloaded and run python3 scripts/moblee-doctor.py — or put that folder's path "
                  "back in ~/.config/moblee/package-path.")
            return
        f.add(LOOK,
              f"{name} was not shortened by the last update, and will not be by the next one. None "
              "of its sections still match what Moblee wrote, so Moblee will not rewrite any of "
              "them or take anything out: every word in that file is treated as yours. The safety "
              "rules are still kept up to date, because an update adds a rule it is missing without "
              "changing anything else. Nothing is wrong with it. It does mean the file stays as long "
              "as it is, and your assistant reads it at the start of every session. If you would "
              "like it shorter, ask your assistant to shorten it.",
              "F40")
        return
    if plan.skipped:
        named = ", ".join(plan.skipped)
        f.add(LOOK,
              f"Some parts of {name} are not shortened when Moblee updates, because you have written "
              f"in them: {named}. Moblee never rewrites a part of that file you have changed, so your "
              "words stay, and the safety rules are still kept up to date, because an update adds a "
              "rule that is missing without changing anything else. It does mean those parts keep "
              "their old, longer wording, and your assistant reads the whole file at the start of "
              "every session. Either ask your assistant to shorten them, or leave them; both are fine.",
              "F40")
    elif plan.owned_seen:
        # (v0.9.4) plan.owned_seen counts only the sections Moblee wrote, so a
        # file holding all thirteen of them AND two long sections of the owner's
        # own used to be called "Moblee's own wording throughout" — of a file
        # measured at more than twice the length the release promises, over half
        # of it the owner's. This check exists to explain why a file stays long,
        # and that answer got it exactly backwards for the one owner who needed
        # it. The file itself is read here and its own sections are named.
        mine = owner_sections(engine, path)
        if mine:
            total = sum(tok for _h, tok in mine)
            named = ", ".join(f"\"{h}\"" for h, _t in mine[:5])
            if len(mine) > 5:
                named += f", and {len(mine) - 5} more"
            f.add(OK,
                  f"Every part of {name} that Moblee wrote is still Moblee's own wording, so updates "
                  f"keep those parts short for you. The file also holds {len(mine)} section(s) of "
                  f"your own ({named}), about {total:,} tokens of it. Moblee never touches those, so "
                  "they are why the file is the length it is, and shortening it means shortening "
                  "them. Your assistant can do that for you if you ask; nothing is wrong as it is.")
        else:
            f.add(OK, f"{name} is Moblee's own wording throughout, so updates keep it short for you.")


# --- The privacy sweep -------------------------------------------------------
# (v0.9.4) Secrets left in the wiki. A wiki is synced, committed, and often
# copied somewhere else again, so a secret written into a page once is in
# several places within the hour. This is not a worry made up at a desk: in the
# September clinic rounds an owner's own assistant wrote wallet recovery phrases
# into a page in plain words, and they sat in the synced wiki until a clinic
# report happened to mention them.
#
# The sweep reports the FILE, the LINE and the KIND of secret. It never prints
# the secret, and never any part of it: not on the screen, not in the JSON, not
# in the report file. It changes nothing, moves nothing and removes nothing; the
# owner takes the secret out by hand and changes it.
#
# Each pattern below is built from two pieces joined together, so that this
# file does not match itself and report the check-up as a leak.
PRIVACY_CRITICAL = [
    ("a private key", re.compile("-----BEGIN " + r"(?:[A-Z0-9]+ )*PRIVATE KEY-----")),
    ("an Amazon cloud access key", re.compile(r"\bAKIA" + r"[0-9A-Z]{16}\b")),
    ("a GitHub token", re.compile(r"\bgh[pousr]_" + r"[A-Za-z0-9]{36,}\b")),
    ("a GitHub token", re.compile(r"\bgithub_" + r"pat_[A-Za-z0-9_]{60,}")),
    ("a key for Claude", re.compile(r"\bsk-" + r"ant-[A-Za-z0-9_\-]{30,}")),
    ("a key for ChatGPT", re.compile(r"\bsk-" + r"(?!ant-)(?:proj-)?[A-Za-z0-9_\-]{40,}")),
    ("a Slack token", re.compile(r"\bxox" + r"[abprs]-[A-Za-z0-9-]{20,}")),
    # The run after AIza is 35 characters and may end in a dash. A "\b" here
    # would then have nothing to sit between — a dash and the space after it are
    # both non-word characters — so a real key ending in a dash went unseen. The
    # lookahead says what was meant: the run stops here and is no longer.
    ("a Google key", re.compile(r"\bAIza" + r"[0-9A-Za-z_\-]{35}(?![0-9A-Za-z_\-])")),
    ("a Stripe live key", re.compile(r"\b[sr]k_" + r"live_[0-9A-Za-z]{20,}")),
    ("a voice-service key", re.compile(r"\bsk_" + r"[0-9a-f]{48}\b")),
    ("a Tailscale key", re.compile(r"\btskey-" + r"[a-z]+-[A-Za-z0-9]{10,}")),
    # Same again: the run may end in a dash, so the end of it is said with a
    # lookahead rather than with "\b".
    ("a Telegram bot token", re.compile(r"\b\d{8,10}:" + r"AA[A-Za-z0-9_\-]{33}(?![A-Za-z0-9_\-])")),
]
PRIVACY_REVIEW = [
    ("a sign-in token", re.compile(r"\beyJ" + r"[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}")),
    # Not after "?" or "&": a token in a web address's query is part of a link
    # somebody was sent, not a secret of the owner's. Same line only.
    ("a password or key written into a setting", re.compile(
        r"(?i)(?<![?&\w])(?:pass" + r"word|passwd|api[_\-]?key|secret[_\-]?key|client[_\-]?secret|access[_\-]?token|auth[_\-]?token)\b"
        r"[\"'”]?[ \t]*[:=][ \t]*[\"'”]?([^\s\"'`,;<>”]{6,})")),
]
# A VALUE that says "put yours here" is documentation, not a secret. This is
# read against the matched value and nothing else.
#
# (v0.9.4) It used to be read against the value AND against a sixty-character
# window of whatever was written around it, and that quietly threw real secrets
# away. "<" and ">" were in the pattern, so a line quoted from an email or a
# chat — a markdown blockquote begins "> ", and an address is written
# <someone@example.com> — suppressed the finding; so did the word "your", which
# is the commonest word in English to find near a password ("your bank
# password: ..."). The sweep then said no secrets were found. The value is the
# only thing that can say "put yours here", so the value is the only thing read.
# "<" and ">" are gone from the pattern as well: a value can never hold either,
# because the value pattern above stops at both, so they only ever matched the
# prose.
PRIVACY_PLACEHOLDER = re.compile(
    r"(?i)your|example|xxxx|placeholder|redacted|\.\.\.|\$\{?[A-Z_]+|os\.environ|getenv|keychain|\*\*\*")
# The files the sweep opens. Reading costs time, so this is a list and not
# "everything", but until v0.9.4 it left out the very files a private key is
# normally kept in: a key pasted into a page was found and the key FILE beside
# it was not. .pem, .key and .asc are the usual names for one, .markdown is the
# other spelling of .md, and .canvas is an Obsidian board, which is JSON and can
# hold anything a page can.
#
# .p12 is deliberately NOT here. It is a binary container (PKCS#12, DER), not
# text: the "-----BEGIN ... PRIVATE KEY-----" line the sweep looks for is never
# in one, so opening it would read a file of any size and find nothing.
PRIVACY_TEXT_EXT = {".md", ".markdown", ".txt", ".json", ".canvas", ".py", ".sh", ".zsh", ".bash",
                    ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf", ".plist", ".csv", ".js",
                    ".ts", ".html", ".swift", ".env", ".log", ".pem", ".key", ".asc"}
# Files with no extension at all whose NAME says what they are. An SSH private
# key is called id_rsa (or id_ed25519, and so on) and carries no extension,
# which is why it was stepped over; its public half ends .pub and holds nothing
# secret, so it is left out.
PRIVACY_TEXT_NAMES = {".env", "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519",
                      "id_ecdsa_sk", "id_ed25519_sk"}
PRIVACY_SKIP_DIRS = {".git", "node_modules", ".build", "__pycache__", ".venv", "venv", "backup", "backups"}
PRIVACY_MAX_BYTES = 12_000_000
PRIVACY_ACCEPTED = ".moblee/privacy-accepted.txt"
PRIVACY_SHOW = 20

# Wallet recovery phrases, in two layers.
#
# Layer two, the exact one, needs the 2,048-word English wallet list. Moblee
# does not carry that list, so when it is not on the Mac the check falls back to
# layer one: the SHAPE of a phrase. A run of exactly twelve or exactly
# twenty-four plain lowercase words, every one of them three to eight letters,
# with nothing between them but spaces, line breaks or list numbering. Ordinary
# writing almost never makes that shape, because ordinary sentences are full of
# short words ("a", "of", "to", "is", "in") and of commas and full stops, and
# any one of those ends the run. A shape finding is named as a guess, never as a
# certainty, and when the word list is there it is the word list that decides.
PHRASE_WORD = re.compile(r"[a-z]{3,8}")
PHRASE_NUMBER = re.compile(r"\(?\d{1,2}[.)]\)?")          # "1." "12)" "(3)"
PHRASE_NUMBERED_WORD = re.compile(r"\(?\d{1,2}[.)]([a-z]{3,8})")   # "1.abandon"
PHRASE_LENGTHS = (12, 24)
# The run must also have whole lines to itself, which is how anybody writes a
# recovery phrase down and is not how a sentence is built. A line may hold a
# list marker and a number before its words, and nothing else beside them.
# Without this the shape fired twice on the pack's own writing
# (docs/02-install.md and docs/10-connections.md, both mid-sentence); with it,
# nothing in the pack fires. The rule is applied line by line, so that a line
# of ordinary writing above or below the phrase ends the run rather than being
# swallowed into it: a heading with a word in it ("# A page") used to join the
# twelve words under it and make thirteen, and thirteen is not a phrase, so the
# very shape this looks for went unseen whenever anything was written above it.
PHRASE_MARKERS = ("-", "*", ">", "+")
# Where a 2,048-word English wallet list is read from, if the owner or a later
# Moblee ever puts one there. Named here so the check-up can say where it looked.
BIP39_PATHS = ("scripts/data/bip39-english.txt",)


def privacy_wordlist(vault: Path | None, pack: Path | None) -> tuple[set, str | None]:
    """The 2,048-word English wallet list, if a copy is on this Mac, and where
    it was read from. A file of any other length is not that list and is not
    used: a short or half-written one would confirm nothing and deny nothing."""
    roots = [r for r in (pack, vault) if r is not None]
    env = os.environ.get("MOBLEE_BIP39")
    candidates = [Path(env).expanduser()] if env else []
    candidates += [root / rel for root in roots for rel in BIP39_PATHS]
    for path in candidates:
        try:
            # Lower-cased, because the text it is matched against is lower-cased
            # too (see privacy_in_file). The official list is already lowercase,
            # so this only guards against a copy somebody has re-typed.
            words = {w.strip().lower() for w in path.read_text(encoding="utf-8", errors="ignore").split() if w.strip()}
        except OSError:
            continue
        if len(words) == 2048:
            return words, tidy(path)
    return set(), None


def privacy_own_line(line: str) -> list | None:
    """The plain words a line holds, when it holds nothing else. A list marker
    or a number may come first; after that, only words. None when there is
    anything else on the line at all, because a recovery phrase is written down
    on a line of its own and a sentence never is."""
    chunks = line.split()
    if chunks and chunks[0] in PHRASE_MARKERS:
        chunks = chunks[1:]
    found = []
    for chunk in chunks:
        if PHRASE_NUMBER.fullmatch(chunk):
            continue
        numbered = PHRASE_NUMBERED_WORD.fullmatch(chunk)
        if numbered:
            chunk = numbered.group(1)
        if not PHRASE_WORD.fullmatch(chunk):
            return None
        found.append(chunk)
    return found


def privacy_phrase_runs(text: str, words: set) -> list:
    """Line numbers where twelve or more words of the wallet list stand in a
    row. With the list in hand this is certain, so it is looked for wherever it
    falls, a sentence included."""
    hits = []
    start = count = 0
    for m in re.finditer(r"\S+", text):
        chunk = m.group(0)
        if PHRASE_NUMBER.fullmatch(chunk):
            continue
        numbered = PHRASE_NUMBERED_WORD.fullmatch(chunk)
        if numbered:
            chunk = numbered.group(1)
        if chunk in words:
            if count == 0:
                start = m.start()
            count += 1
            continue
        if count >= 12:
            hits.append(text.count("\n", 0, start) + 1)
        count = 0
    if count >= 12:
        hits.append(text.count("\n", 0, start) + 1)
    return hits


def privacy_phrase_lines(text: str, words: set) -> list:
    """Line numbers where a run of words has the shape of a wallet recovery
    phrase. With the word list, the words must all be in it and the run must be
    twelve or more long, which is certain. Without it, the run must be exactly
    twelve or exactly twenty-four words long and must have its lines to itself,
    which is a guess."""
    if words:
        return privacy_phrase_runs(text, words)
    hits, run = [], []
    first = 0

    def is_phrase() -> bool:
        # A word said three times or more is writing of some other kind, not a
        # phrase. Twelve lines of a program's opening ("import time", "import
        # sys", ... ) have exactly the shape this looks for, and "import" gives
        # them away. Two of a kind is left alone: a wallet phrase may repeat a
        # word once, and three of a kind in twelve words drawn from 2,048 comes
        # up about once in two thousand phrases.
        return (len(run) in PHRASE_LENGTHS
                and max(run.count(w) for w in set(run)) < 3)

    for number, line in enumerate(text.split("\n"), start=1):
        on_line = privacy_own_line(line)
        if not on_line:            # a blank line, or a line with other writing on it
            if is_phrase():
                hits.append(first)
            run = []
            continue
        if not run:
            first = number
        run += on_line
    if is_phrase():
        hits.append(first)
    return hits


# (v0.9.4) A finding and an owner's note about it are compared in this reduced
# form, not character for character. The kinds are sentences — "a run of words
# shaped like a wallet recovery phrase" is forty-eight characters — and the
# owner writing them out is a person who does not read much, typing by hand into
# a text file with nothing checking them. An exact match turns one capital
# letter, one double space or one full stop into a check-up that goes on
# shouting with nothing on screen saying why. Forgiving the case, the spacing,
# the trailing full stop and the leading "a"/"an"/"the" cannot confuse one kind
# with another, because every kind the sweep names is still different from every
# other after that; so it costs nothing and saves the owner the one thing they
# are least able to do.
PRIVACY_ARTICLES = ("a ", "an ", "the ")


def privacy_key(path: str, kind: str) -> tuple[str, str]:
    """A finding's path and kind, reduced to the form they are compared in."""
    p = " ".join(str(path).replace("\\", "/").split()).strip().casefold()
    while p.startswith("./"):
        p = p[2:]
    p = p.strip("/")
    k = " ".join(str(kind).split()).casefold().strip(" .")
    for article in PRIVACY_ARTICLES:
        if k.startswith(article):
            k = k[len(article):]
            break
    return p, k


def privacy_accepted(vault: Path) -> set:
    """Findings the owner has looked at and decided to keep, one to a line in
    the wiki's own .moblee/privacy-accepted.txt as "path | kind | why". They
    are counted apart and are not reported again. The path and the kind are
    matched in the reduced form above, so capitals and spacing need not be
    copied exactly."""
    taken = set()
    try:
        lines = (vault / PRIVACY_ACCEPTED).read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return taken
    for line in lines:
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 2 and parts[0] and not parts[0].startswith("#"):
            taken.add(privacy_key(parts[0], parts[1]))
    return taken


def privacy_in_file(text: str, words: set) -> list:
    """Every secret this file holds, as (how bad, what kind, which line). The
    matched text is read to decide, and then dropped; it is never returned."""
    found = []
    for kind, rx in PRIVACY_CRITICAL:
        for m in rx.finditer(text):
            found.append(("critical", kind, text.count("\n", 0, m.start()) + 1))
    for kind, rx in PRIVACY_REVIEW:
        for m in rx.finditer(text):
            value = m.group(1) if m.groups() else m.group(0)
            # The value alone decides. What is written around it is the owner's
            # prose, and prose is not evidence either way: see the note beside
            # PRIVACY_PLACEHOLDER for the secrets the old window let through.
            if PRIVACY_PLACEHOLDER.search(value):
                continue
            # Inside a web address: part of a link, not a secret of the owner's.
            word_start = max(text.rfind(c, 0, m.start()) for c in " \t\n(\"'")
            if "://" in text[word_start + 1:m.start()]:
                continue
            # A value that is only letters is a name in a piece of code or a
            # word in a sentence, not a password.
            if re.fullmatch(r"[A-Za-z_.]+\)?", value):
                continue
            found.append(("review", kind, text.count("\n", 0, m.start()) + 1))
    # (v0.9.4) Lower-cased for both layers, not just the shape one. The word
    # list holds 2,048 lowercase words, so a phrase written "Abandon Ability
    # Able ..." matched none of them and the exact layer found nothing at all —
    # while the check-up said in the same breath that the wallet-phrase check
    # was exact. Installing the word list therefore LOST detections under a
    # claim of certainty. Lower-casing keeps the line numbers as they are,
    # because it changes no line breaks.
    for ln in privacy_phrase_lines(text.lower(), words):
        found.append(("critical" if words else "review",
                      "a wallet recovery phrase" if words else
                      "a run of words shaped like a wallet recovery phrase", ln))
    return found


def same_folder(one: Path, other: Path) -> bool:
    """Whether two paths are the same folder, links followed."""
    try:
        return one.resolve() == other
    except OSError:
        return False


def in_git(vault: Path) -> bool:
    """Whether the wiki is kept in git at all. A folder that is not a git
    repository and a git that would not answer are two different things to tell
    an owner, and until this was asked they were told as one."""
    code, out = run(["git", "-C", str(vault), "rev-parse", "--is-inside-work-tree"])
    return code == 0 and out.strip() == "true"


def remote_hosts(vault: Path) -> list | None:
    """The web addresses the wiki's history is sent to, by host. An empty list
    when it is kept in git and sent nowhere. None when git would not answer,
    which is also what a folder that is not a git repository gives."""
    code, out = run(["git", "-C", str(vault), "remote", "-v"])
    if code != 0:
        return None
    hosts = set()
    for line in out.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        url = parts[1]
        if url.startswith(("/", ".", "~")):
            hosts.add("a folder on this Mac")
            continue
        m = re.match(r"(?:[A-Za-z][A-Za-z0-9+.\-]*://)?(?:[^@/\s]+@)?([^/:\s]+)", url)
        if m:
            hosts.add(m.group(1))
    return sorted(hosts)


def check_privacy(f: Findings, vault: Path | None, pack: Path | None) -> None:
    if vault is None:
        return
    words, list_from = privacy_wordlist(vault, pack)
    accepted = privacy_accepted(vault)
    try:
        me = Path(__file__).resolve()
    except OSError:
        me = None
    # Moblee's own folder is sometimes kept inside the wiki (outputs/moblee),
    # and it is not the owner's writing: it is Moblee's, the same on every Mac,
    # and it carries invented secrets on purpose, in the file that tests this
    # very sweep. Reading them back as the owner's would be crying wolf, so the
    # folder is stepped over and the check-up says so.
    pack_inside = None
    try:
        if pack is not None and pack.resolve() != vault.resolve() and pack.resolve().is_relative_to(vault.resolve()):
            pack_inside = pack.resolve()
    except (OSError, ValueError):
        pack_inside = None
    critical, review, taken = [], [], []
    scanned = 0
    for dirpath, dirnames, filenames in os.walk(vault):
        here = Path(dirpath)
        dirnames[:] = [d for d in dirnames if d not in PRIVACY_SKIP_DIRS
                       and not (pack_inside is not None and same_folder(here / d, pack_inside))]
        for name in sorted(filenames):
            p = Path(dirpath) / name
            if p.suffix.lower() not in PRIVACY_TEXT_EXT and name.lower() not in PRIVACY_TEXT_NAMES:
                continue
            try:
                if p.is_symlink() or (me is not None and p.resolve() == me):
                    continue
                if p.stat().st_size > PRIVACY_MAX_BYTES:
                    continue
                text = p.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            scanned += 1
            try:
                rel = str(p.relative_to(vault))
            except ValueError:
                rel = p.name
            seen = set()
            for level, kind, ln in privacy_in_file(text, words):
                if (level, kind, ln) in seen:
                    continue
                seen.add((level, kind, ln))
                entry = f"{rel} line {ln}: {kind}"
                if privacy_key(rel, kind) in accepted:
                    taken.append(entry)
                elif level == "critical":
                    critical.append(entry)
                else:
                    review.append(entry)

    def listed(entries: list) -> str:
        shown = "; ".join(entries[:PRIVACY_SHOW])
        if len(entries) > PRIVACY_SHOW:
            shown += f"; and {len(entries) - PRIVACY_SHOW} more"
        return shown

    mode = (f"The wallet-phrase check is exact: it is reading the 2,048-word list at {list_from}."
            if words else
            "There is no copy of the 2,048-word wallet list on this Mac, so a recovery phrase is "
            "judged by its shape alone: anything named below is a guess and not a certainty.")
    stepped = (f" Moblee's own folder ({tidy(pack_inside)}) is inside the wiki and was stepped over: "
               "it holds Moblee's files rather than yours." if pack_inside is not None else "")
    f.add(OK, f"Privacy sweep: {scanned} file(s) in the wiki were read for secrets left in them. "
              "The file and the line are named; the secret itself is never printed, here or in a "
              f"report, and nothing was changed.{stepped} {mode}")
    no_names = ("The file and the line of each are on the screen when you run the check-up; they "
                "are page titles, so they are left out of a report you may send on.")
    if critical:
        advice = (" Take each one out of the page by hand and change the secret itself, because the "
                  "old one is in the wiki's history as well. A secret you have looked at and decided "
                  f"to keep goes in {PRIVACY_ACCEPTED} in the wiki, one to a line, as "
                  "\"path | kind | why\", and is then counted apart. Copy the file and the kind from "
                  "the line above; capitals and spacing do not have to match.")
        f.add(PROBLEM,
              f"{things(len(critical))} in the wiki look like a live secret: " + listed(critical) + "." + advice,
              "F41",
              f"{things(len(critical))} in the wiki look like a live secret. " + no_names + advice)
    if review:
        advice = (" These are often harmless: a line in a page about how something is set up, an "
                  "example, a word in a piece of writing. Read each one before doing anything. "
                  f"One you decide to keep goes in {PRIVACY_ACCEPTED} in the wiki, one to a line, as "
                  "\"path | kind | why\". Copy the file and the kind from the line above; capitals "
                  "and spacing do not have to match.")
        f.add(LOOK,
              f"{things(len(review))} in the wiki are worth a look: " + listed(review) + "." + advice,
              "F42",
              f"{things(len(review))} in the wiki are worth a look. " + no_names + advice)
    if taken:
        f.add(OK, f"{things(len(taken), 'finding', 'findings')} were looked at before and kept on "
                  "purpose, so they are not counted.")
    if not critical and not review:
        f.add(OK, "No secrets were found in the wiki.")
    hosts = remote_hosts(vault)
    if hosts is None:
        # Three different things, and they were once told as one. A folder that
        # is not kept in git sends nothing anywhere, and the owner may be told so
        # plainly. A Mac with no git at all, and a git that would not answer,
        # leave the question open, and an open question is not an answer of "no".
        if shutil.which("git") is not None and not in_git(vault):
            f.add(OK, "The wiki is not kept in git, so no history is sent anywhere: what is in it "
                      "stays on this Mac.")
        else:
            f.add(OK, "Whether the wiki's history is sent anywhere could not be read from git.")
    elif not hosts:
        f.add(OK, "The wiki's history is sent nowhere: it stays on this Mac.")
    else:
        f.add(LOOK,
              "The wiki's history is sent to " + ", ".join(hosts)
              + ". Anything committed to a repository that is open to the public can be read by "
                "anyone, including a secret taken out of a page afterwards, because the old version "
                "stays in the history. Moblee cannot look over the internet, so it does not know "
                "whether this one is open or private. Check that yourself on "
              + hosts[0] + ", and keep it private.",
              "F43")


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
    # (v0.9.1) An update whose files all landed but whose closing commit git
    # refused. It did reach the end, so saying "did not finish" would be wrong,
    # and saying "ran to the end" is what left a real owner believing a staged,
    # uncommitted update was done. It is its own finding, with its own words.
    if any("NOT COMMITTED" in l for l in tail):
        refused = next((l for l in tail if "REFUSED" in l), "")
        detail = tidy(refused.split("  ", 1)[-1]) if refused else "the closing commit was refused"
        f.add(PROBLEM,
              f"The last {what} put every file in place but was not committed: {detail} "
              f"Ask your assistant: \"the Moblee {what} did not commit, please look and commit it\".",
              "F34")
    elif any("finished ===" in l for l in tail):
        f.add(OK, f"The last {what} ran to the end.")
    else:
        stopped = next((l for l in tail if "stopped during" in l or "FAILED" in l), "it did not reach the end")
        f.add(LOOK, f"The last {what} did not finish: " + tidy(stopped.split("  ", 1)[-1]),
              "F35")


# (v0.9.4) Ordinary words a folder of notes gets called. A wiki folder with one
# of these names gives nothing away about who owns it, so a report leaves it as
# it is; see anon() below for why that matters.
GENERIC_VAULT_NAMES = {"wiki", "wikis", "notes", "notebook", "notebooks", "vault", "vaults",
                       "obsidian", "documents", "docs", "knowledge", "brain", "second brain"}


def anonymiser(vault: Path):
    """The function a report's lines are passed through, so that nothing in one
    says who the owner is.

    The wiki's folder is usually named after its owner, so neither its path nor
    its bare name is sent on. The bare name is the awkward half, and until
    v0.9.4 it was replaced as a plain substring wherever it appeared: a wiki
    folder called "Wiki" or "Notes" — and plenty are — turned every ordinary
    sentence in the report into nonsense ("what is in the <wiki> stays on this
    Mac"), and "Wiki" inside "Wikipedia" went the same way. Two rules mend that
    without letting a name through. A name that is an ordinary word for a folder
    of notes reveals nobody, so it is left alone; any other name is replaced,
    but only where it stands as a whole word and never inside a longer one."""
    here = str(vault)
    short = tidy(vault)
    name = vault.name
    bare = (None if name.casefold() in GENERIC_VAULT_NAMES
            else re.compile(r"(?<!\w)" + re.escape(name) + r"(?!\w)"))

    def anon(text: str) -> str:
        out = str(text).replace(here, "<wiki>").replace(short, "<wiki>")
        return bare.sub("<wiki>", out) if bare is not None else out

    return anon


# ---------------------------------------------------------------- health card
# (v0.9.6) The one-screen summary for whoever helps the owner. Somebody else is
# usually the one who is good with computers -- a relative, a neighbour -- and
# that person wants neither forty findings nor a look inside the owner's wiki.
# They want one screen: is it healthy, what is wrong, what do I do.
#
# The card is a second way of PRINTING the check-up and never a second reading
# of the Mac. Every line on it is a row the check-up has already raised, and the
# headline is chosen by card_facts() from those same rows, so the card cannot
# call a wiki healthy while the findings say otherwise. The screen's closing
# summary calls card_facts() too, which is what stops the two drifting apart.
#
# One screen means a Terminal window as macOS opens one: 24 lines of at most 78
# characters. build_card() holds to both by dropping findings from the lists
# until the card fits, and the card then says how many it dropped and where the
# rest are, so nothing is ever cut in silence.
CARD_WIDTH = 78
CARD_LINES = 24
# Two different limits, and both are meant. CARD_LINES is the hard ceiling and
# is enforced by the loop at the end of build_card(). CARD_PROBLEMS is a
# judgement: five is as many things as one person can take in and act on at a
# sitting, and a helper handed thirteen would put the card down. So the card
# lists five, however much room is left, and says how many it is not showing and
# where every one of them is written out in full.
CARD_PROBLEMS = 5
CARD_UNSEEN = 2
CARD_MOST_ACTIONS = 4    # every action the card can offer, so none is ever dropped
CARD_MIN_SENTENCE = 20   # a "sentence" shorter than this is a numbered step or an abbreviation
CARD_ROOM = CARD_WIDTH - 7   # what is left of a line after the "  F01  " that starts it
CARD_TITLE = "Moblee health card"
# (v0.9.6) "What to look at" and not "What is wrong". The check-up has two levels
# under this heading and they do not mean the same thing: a PROBLEM is wrong, a
# LOOK is worth looking at. Calling both "wrong" overstated every LOOK, and one
# of them — F40, a deliberately reassuring line whose own words are "Nothing is
# wrong with it" — was being handed to a helper under the heading "What is
# wrong", counted in "N things are wrong", with the reassurance cut off the end
# for room. Worst first is still the order, and the field-guide code beside each
# line is where the severity is. This also makes the card agree with the app's
# own sentence, which already says "N things to look at".
CARD_WRONG_HEAD = "What to look at, worst first. The code is its entry in the field guide."
CARD_UNSEEN_HEAD = "What could not be checked. Not a fault: the check could not look."
CARD_NEXT_HEAD = "What to do next"
CARD_FOOTER = "Safe to show anyone: no page names, nothing from inside the wiki."
CARD_ORDER = {PROBLEM: 0, LOOK: 1}
# Words that lead on to the rest of a sentence and say nothing standing alone: a
# shortened line never ends on one, so that what is left reads as a statement
# (see card_line()). "not" and "no" are deliberately absent. Dropping a negation
# turns a finding into its own opposite, and the loop stops at the first word it
# does not know, so a "not" also shields everything before it.
CARD_DANGLING_WORDS = {"so", "and", "but", "because", "which", "where", "that", "or",
                       "as", "if", "when", "while", "since", "though", "unless", "than",
                       "to", "of", "in", "on", "for", "with", "from", "by", "at",
                       "the", "a", "an", "be", "been", "is", "are", "was", "were",
                       "has", "have", "had",
                       # (v0.9.6) The modals and the pointing words. Without
                       # these the very first line of a real card ended "so
                       # nothing can...", which is exactly what the list above
                       # exists to stop; the list had every linking word except
                       # the ones English actually breaks on. Found by a cold
                       # read of a real card rather than by the tests, which
                       # shorten one made-up sentence and never ask whether what
                       # is left reads as a statement.
                       "can", "could", "will", "would", "may", "might", "must",
                       "shall", "should", "do", "does", "did", "this", "these",
                       "those", "it", "its", "their", "there", "into", "onto",
                       "about", "then"}
CARD_LEAST_LINE = 25   # never strip a line down past this, however it ends
# (v0.9.6) Words that open a clause which cannot stand by itself. Where a
# shortened line's last comma is followed by one of these, the clause after it
# goes; see card_line(). Narrower than CARD_DANGLING_WORDS on purpose: this one
# throws away whole clauses, so it holds only words that really do begin one.
CARD_CLAUSE_OPENERS = {"so", "and", "but", "because", "which", "where", "or",
                       "as", "if", "when", "while", "since", "though", "unless",
                       "then", "though", "whereas"}

# The word "healthy" belongs to one of these and only one. A wiki that could not
# be looked at everywhere is not given a clean bill: a helper told "healthy"
# when the check could not see would go away believing something untrue.
CARD_HEADLINES = {
    "healthy": "This wiki looks healthy. Nothing was found to be wrong.",
    "unchecked": "Nothing was found to be wrong, but {unseen} could not be checked, "
                 "so this is not a clean bill.",
    "unwell": "This wiki needs attention: {bad}.",
}
# What {bad} is filled with; see CARD_WRONG_HEAD for why it is not "wrong".
CARD_BAD_ONE, CARD_BAD_MANY = "thing to look at", "things to look at"


def things(n: int, one: str = "thing", many: str = "things") -> str:
    """`1 thing`, `4 things`. The card is written for somebody who does not read
    much, and `4 thing(s)` is a programmer's shortcut for not choosing: it asks
    the reader to do the choosing instead. The pack's own rules file tells every
    assistant to use plain words, so the pack's own screens had better."""
    return f"{n} {one if n == 1 else many}"

# A secret in a page is the owner's own job and the urgent one, so it is said
# first when the sweep has found one. The softer half of the sweep is a separate
# action, because "worth a look" often turns out to be an example or a note and
# telling a helper to change it would be telling them something untrue.
CARD_SECRET_CODE = "F41"
CARD_MAYBE_CODE = "F42"
# The findings the Moblee app can put right with a button of its own: the
# missing rules and guard it offers Repair for, and the older wiki it offers the
# update for. Naming the button is the one concrete step a helper can take
# without reading anything.
CARD_APP_CODES = ("F01", "F02", "F11", "F27", "F28")


def card_facts(rows: list) -> tuple[str, list, list]:
    """The one place the findings are divided into what is wrong and what could
    not be checked, and the one place the verdict is settled.

    Both the screen's closing summary and the health card read their answer from
    here, so neither can say something the other contradicts. A wiki is called
    healthy only when both lists are empty, which is what makes the card's
    headline a consequence of the findings rather than a judgement of its own."""
    bad = [r for r in rows if r["level"] not in (OK, UNSEEN, UNSURE)]
    unseen = [r for r in rows if r["level"] in (UNSEEN, UNSURE)]
    state = "unwell" if bad else ("unchecked" if unseen else "healthy")
    return state, bad, unseen


def card_line(row: dict, anon, room: int = CARD_ROOM) -> str:
    """One finding, in one line, with nothing in it from inside the wiki.

    The sendable wording is taken wherever the check-up wrote one. That is the
    finding without the file names, and a file name in a wiki is a page title,
    which is exactly what the card must not carry; the privacy sweep is the
    check that needs it. Only the first sentence is kept, the rest of a finding
    being its advice, and a sentence too long for the line is cut at a word and
    ended with "...", so that the shortening is plain to see. The field-guide
    code beside it is where the whole story is."""
    text = " ".join(anon(row.get("sendable") or row["text"]).split())
    cut = len(text)
    for m in re.finditer(r"\.(?=\s|$)", text):
        if m.start() >= CARD_MIN_SENTENCE:
            cut = m.start() + 1
            break
    first = text[:cut].strip()
    if len(first) > room:
        short = first[:room - 3].rstrip(" ,;:")
        if " " in short:
            short = short.rsplit(" ", 1)[0]
        # A line ending "so..." or "because..." tells the reader nothing it did
        # not already say, and reads as though the card broke off mid-thought.
        # Dropping the linking word leaves a whole statement behind.
        while (" " in short and len(short) > CARD_LEAST_LINE
               and short.rsplit(" ", 1)[1].lower().strip(",;:") in CARD_DANGLING_WORDS):
            short = short.rsplit(" ", 1)[0]
        # (v0.9.6) And then the half-clause the words above cannot reach. Losing
        # the verb out of "…, so nothing can be brought back" leaves "…, so
        # nothing", and "nothing" is a perfectly good word, so the loop stops
        # there and the reader is handed a dangling clause anyway. A comma is
        # where English lets you stop, so where the last clause STARTS with a
        # linking word the whole clause goes and the statement before it stands
        # on its own. Only when enough is left to say something: "The delete
        # guard is on, but it is not the same copy…" would become "The delete
        # guard is on", which is nearer the opposite of the finding than the
        # finding, and CARD_LEAST_LINE is what stops that.
        head, comma, tail = short.rpartition(",")
        if comma and tail.strip().split(" ")[0].lower() in CARD_CLAUSE_OPENERS:
            trimmed = head.rstrip(" ,;:")
            if len(trimmed) >= CARD_LEAST_LINE:
                short = trimmed
        first = short.rstrip(" ,;:") + "..."
    return first


def card_actions(state: str, bad: list, unseen: list) -> list:
    """What a person can do next, in the order a person should do it.

    Each action is here because of a finding the CHECK-UP made, which is not the
    same as a finding on the card: the card holds five lines and the check-up can
    make more, so an action can be about something the card had no room for. That
    is deliberate — advice about a secret must not be dropped because the secret
    came sixth — but it means no action may point at "the line above" as though
    it were there. Each one names its field-guide code instead, which is on the
    card beside the line when the line fits and in the full check-up when it does
    not. (v0.9.6: it used to say "the line above" and could say it about a line
    the card had just dropped.) There are only ever four, which is why none is
    dropped for room."""
    codes = [r["guide"] for r in bad if r["guide"]]
    out = []
    if state == "healthy":
        out.append("Nothing to do. Run the check-up again next month.")
    if CARD_SECRET_CODE in codes:
        out.append(f"Start with the secret ({CARD_SECRET_CODE}): take it off the page, then "
                   "change it.")
    elif CARD_MAYBE_CODE in codes:
        out.append(f"Read the page behind the \"worth a look\" line ({CARD_MAYBE_CODE}): it "
                   "may be a secret.")
    if any(c in CARD_APP_CODES for c in codes):
        out.append("Open the Moblee app: it offers Repair, or the update, when it can help.")
    if codes:
        out.append(f'Ask the wiki\'s assistant: "read me field guide {codes[0]}", and follow it.')
    elif bad:
        out.append("Ask the wiki's assistant to read the field guide on each line above.")
    if unseen:
        out.append("Run the full check-up: each line it could not see says how to find out.")
    return out[:CARD_MOST_ACTIONS]


def build_card(rows: list, vault: Path | None = None, today=None) -> dict:
    """The health card, as text and as something a program can read.

    The returned dict is the interface the Moblee app is meant to call: "lines"
    is the card itself, one string to a line, and the rest are the same facts
    without the wording, "healthy" among them. Nothing here reads the Mac; it is
    given the findings and prints them."""
    state, bad, unseen = card_facts(rows)
    anon = anonymiser(vault) if vault is not None else str
    # Worst first, and sorted() is stable, so findings of one level stay in the
    # order the check-up raised them.
    bad = sorted(bad, key=lambda r: CARD_ORDER.get(r["level"], 2))
    day = today or datetime.date.today()
    headline = CARD_HEADLINES[state].format(
        bad=things(len(bad), CARD_BAD_ONE, CARD_BAD_MANY),
        unseen=things(len(unseen)))
    if state == "unwell" and unseen:
        headline += f" {len(unseen)} more could not be checked."
    actions = card_actions(state, bad, unseen)
    wrong_all = [{"level": r["level"], "guide": r["guide"], "line": card_line(r, anon)} for r in bad]
    unseen_all = [{"level": r["level"], "guide": r["guide"], "line": card_line(r, anon)} for r in unseen]

    def render(n_wrong: int, n_unseen: int) -> list:
        out = [f"{CARD_TITLE}, {day.strftime('%-d %B %Y')}"]
        out += textwrap.wrap(headline, CARD_WIDTH) or [headline]
        if wrong_all:
            out += ["", CARD_WRONG_HEAD]
            for item in wrong_all[:n_wrong]:
                out.append("  %-3s  %s" % (item["guide"] or "-", item["line"]))
            if len(wrong_all) - n_wrong > 0:
                out.append("  ...  and %d more. The full check-up lists every one."
                           % (len(wrong_all) - n_wrong))
        if unseen_all:
            out += ["", CARD_UNSEEN_HEAD]
            for item in unseen_all[:n_unseen]:
                out.append("  %-3s  %s" % (item["guide"] or "-", item["line"]))
            if len(unseen_all) - n_unseen > 0:
                out.append("  ...  and %d more. The full check-up says how to find each out."
                           % (len(unseen_all) - n_unseen))
        out += ["", CARD_NEXT_HEAD] + ["  " + a for a in actions]
        return out + ["", CARD_FOOTER]

    n_wrong = min(CARD_PROBLEMS, len(wrong_all))
    n_unseen = min(CARD_UNSEEN, len(unseen_all))
    lines = render(n_wrong, n_unseen)
    # The height is held to by shortening the lists, never by cutting the card
    # off: what is not shown is counted on the card, and the counts in the
    # headline are of everything the check-up found either way. The unchecked
    # lines give way first, being the shorter list and the one whose own count
    # is already in the headline.
    while len(lines) > CARD_LINES and (n_wrong or n_unseen):
        if n_unseen:
            n_unseen -= 1
        else:
            n_wrong -= 1
        lines = render(n_wrong, n_unseen)
    return {"date": day.isoformat(), "state": state, "healthy": state == "healthy",
            "headline": headline,
            "wrong": wrong_all[:n_wrong], "wrong_total": len(wrong_all),
            "wrong_not_shown": len(wrong_all) - n_wrong,
            "unchecked": unseen_all[:n_unseen], "unchecked_total": len(unseen_all),
            "unchecked_not_shown": len(unseen_all) - n_unseen,
            "actions": actions, "lines": lines}


def write_card(card: dict, where: str) -> str | None:
    """Save the card where a program asked for it. The message on failure, or
    None when it was written.

    The check-up reads and does not change, so the one file it will overwrite is
    a health card: anything else at that path is left exactly as it is and the
    caller is told why. That keeps a mistyped path from costing anybody a page."""
    path = Path(where).expanduser()
    if path.exists() and not path.is_dir():
        try:
            first = path.read_text(errors="replace").splitlines()[:1]
        except OSError:
            first = []
        if not (first and first[0].startswith(CARD_TITLE)):
            return (f"There is already a file at {tidy(path)} that is not a health card, "
                    "so nothing was written. Nothing in it was changed. Give another name.")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(card["lines"]) + "\n")
    except OSError as exc:
        return f"The health card could not be written to {tidy(path)} ({exc})."
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="A read-only check-up of a Moblee wiki.")
    ap.add_argument("--vault")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--report", action="store_true", help="also write a report into the wiki's outputs/ folder")
    ap.add_argument("--card", action="store_true",
                    help="print the one-screen health card for whoever is helping the owner, "
                         "instead of every finding (with --json, the same card as one JSON object)")
    ap.add_argument("--card-file", metavar="PATH",
                    help="also save the health card to this file (it overwrites an earlier card there and nothing else)")
    ap.add_argument("--assistant", choices=ASSISTANTS,
                    help="check for this assistant instead of the one on record (claude, chatgpt or both)")
    ap.add_argument("--prove-guard", action="store_true",
                    help="ask ChatGPT to try a delete in a scratch wiki under ~/.config/moblee/prove-guard/, to prove the guard runs there")
    args = ap.parse_args()

    f = Findings()
    vault, pack = find_vault(args.vault), find_pack()
    # No choice on record means claude, as it always has, except where the wiki
    # itself shows it was made for ChatGPT alone (a second Mac, or a Mac
    # restored without its ~/.config folder): then ChatGPT's checks are the
    # ones that matter, and the updater reads the wiki the same way.
    inferred = False
    if args.assistant:
        assistant = args.assistant
    else:
        assistant = choice_on_record()
        if assistant is None:
            inferred = looks_made_for_chatgpt(vault)
            assistant = "chatgpt" if inferred else "claude"
    wants_claude = assistant in ("claude", "both")
    wants_chatgpt = assistant in ("chatgpt", "both")
    f.add(OK, f"This wiki is set up to be used with {ASSISTANT_NAMES[assistant]}.")
    if inferred:
        f.add(LOOK, "No choice of assistant is on record on this Mac. The wiki is laid out for ChatGPT alone "
                    "(AGENTS.md is its real rules file), so it was checked as one. The next update records the choice.", "F36")
    if wants_claude:
        settings = check_settings(f, vault)
        check_guard(f, settings, pack)
    check_vault(f, vault, pack)
    if wants_claude:
        check_skills(f, pack)
    if wants_chatgpt:
        check_chatgpt(f, vault, pack, assistant, args.prove_guard,
                      announce=not (args.json or args.card))
    elif args.prove_guard:
        f.add(OK, "--prove-guard tests the delete guard inside ChatGPT, and this wiki is set up for Claude only, "
                  "so there was nothing to put to the test.")
    check_weights(f, vault)
    check_rules_sections(f, vault, pack)
    check_privacy(f, vault, pack)
    check_jobs(f)
    check_diary(f)
    check_mac(f, assistant)
    check_leftovers(f, pack)

    # The card is built from the findings just gathered and from nothing else, so
    # the run behind a card and the run behind the full list are the same run.
    card = build_card(f.rows, vault) if (args.card or args.card_file) else None

    if args.card:
        print(json.dumps(card, indent=2) if args.json else "\n".join(card["lines"]))
    elif args.json:
        print(json.dumps(f.rows, indent=2))
    else:
        print("Moblee check-up (nothing in the wiki is changed by this; the guard is tested in a scratch wiki)\n"
              if args.prove_guard and wants_chatgpt else "Moblee check-up (nothing is changed by this)\n")
        width = max([8] + [len(r["level"]) for r in f.rows])
        for r in f.rows:
            guide = f"  [field guide {r['guide']}]" if r["guide"] and r["level"] != OK else ""
            print(f"  {r['level']:<{width}} {r['text']}{guide}")
        # What cannot be seen from here is not a fault, and is counted apart.
        # The same split the health card uses, from the same function, so the
        # screen and the card can never disagree about what was found.
        state, bad, unseen = card_facts(f.rows)
        print("")
        if state == "healthy":
            print("Everything looks right.")
        elif state == "unchecked":
            print("Nothing was seen to be wrong, but some things cannot be seen from here; each such line says how to check.")
        else:
            print(f"{things(len(bad))} to look at. The field guide (skills/companion/field-guide.md) explains each."
                  + (f" {len(unseen)} more cannot be seen from here; the line says how to check." if unseen else ""))

    if args.card_file:
        trouble = write_card(card, args.card_file)
        if trouble:
            print(("\n" if args.card and not args.json else "") + trouble)
            return 1
        if not args.json:
            print(("\n" if args.card else "")
                  + f"Health card written to {tidy(Path(args.card_file).expanduser())}")

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
        anon = anonymiser(vault)
        body += [f"- **{r['level']}** {anon(r.get('sendable') or r['text'])}"
                 + (f" (field guide {r['guide']})" if r["guide"] and r["level"] != OK else "")
                 for r in f.rows]
        body += ["", "## What the owner noticed", "",
                 "*(your assistant writes here, in the owner's words, what seemed wrong, leaving out names and page titles, and nothing else.)*", ""]
        path.write_text("\n".join(body))
        print(f"\nReport written to {tidy(path)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
