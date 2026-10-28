#!/usr/bin/env python3
"""moblee-setup.py: the checklist that connects a Moblee wiki to the owner's
Mac, accounts and tools, then proves each piece works.

Run from the Moblee package folder, in Terminal:

    python3 scripts/moblee-setup.py            # show the checklist, install what is ticked
    python3 scripts/moblee-setup.py --check    # test everything, change nothing
    python3 scripts/moblee-setup.py --only google,github   # just these items
    python3 scripts/moblee-setup.py --tick videos,google   # the checklist, with these ticked
    python3 scripts/moblee-setup.py --list     # every item with its time, space and cost

Nothing is ticked by default. The usual way in is the "get me started"
conversation with your assistant in the vault, which asks how the owner works
and gives them a --tick command for the items that fit.

The connections, plugins, optional skills and voice on this list are set up
for Claude. Moblee does not set them up for ChatGPT yet, so an owner who uses
ChatGPT alone is told that plainly and the run stops there; only --check,
which changes nothing, carries on.

The installer and the updater offer it; it can be run again at any time to add something that was left out. Nothing it
does deletes anything. Every settings file it changes is copied to
~/.config/moblee/backups/ first. Items already working are shown as such and
are not installed twice.

Mac only. Standard library only, so the Python that ships with macOS runs it.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HOME = Path.home()
PACKAGE_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = HOME / ".config" / "moblee"
BACKUP_ROOT = CONFIG_DIR / "backups"
STATE_FILE = CONFIG_DIR / "setup-state.json"
SETTINGS = HOME / ".claude" / "settings.json"
# (0.16.0) ChatGPT keeps its settings in CODEX_HOME when that is set, else
# ~/.codex, and the safety installer puts the guard and hooks.json there.
_CODEX_HOME = os.environ.get("CODEX_HOME", "").strip()


def _recorded_codex_dir():
    """The folder the safety installer noted in ~/.config/moblee/codex-home, or None."""
    try:
        line = (CONFIG_DIR / "codex-home").read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError):
        return None
    return Path(line) if line and "\n" not in line and line.startswith("/") else None


CODEX_DIR = (Path(_CODEX_HOME).expanduser().absolute() if _CODEX_HOME
             else (_recorded_codex_dir() or HOME / ".codex"))
SKILLS_DST = HOME / ".claude" / "skills"
EXTRA_SKILLS = PACKAGE_ROOT / "extras" / "skills"
STAMP = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")

CHROME_APP = Path("/Applications/Google Chrome.app")
CHROME_PROFILES = HOME / "Library" / "Application Support" / "Google" / "Chrome"
CLAUDE_EXTENSION_ID = "fcoeoabgfenejglbffodgkkbkcdhcgfn"
CLIPPER_EXTENSION_ID = "cnjifjpddelmedmihgijeibhnjfabmlf"
CLAUDE_EXTENSION_URL = "https://chromewebstore.google.com/detail/claude/" + CLAUDE_EXTENSION_ID
CLIPPER_EXTENSION_URL = "https://chromewebstore.google.com/detail/obsidian-web-clipper/" + CLIPPER_EXTENSION_ID
CONNECTORS_URL = "https://claude.ai/settings/connectors"
HOMEBREW_INSTALLER = "https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh"

ORCHARD_PACKAGE = "@l22-io/orchard-mcp"
# Orchard's tools that move, bin or delete. The delete guard watches shell
# commands only, so these are blocked outright in Claude's settings.
ORCHARD_DENY = [
    "mcp__orchard__files_trash",
    "mcp__orchard__files_move",
    "mcp__orchard__reminders_delete_reminder",
    "mcp__orchard__reminders_delete_list",
    "mcp__orchard__keynote_remove_slide",
    "mcp__orchard__numbers_remove_sheet",
]
# Orchard's tools that write over an existing document or file. Legitimate
# work, but never silent: Claude asks every time.
ORCHARD_ASK = [
    "mcp__orchard__pages_write",
    "mcp__orchard__pages_find_replace",
    "mcp__orchard__numbers_write",
    "mcp__orchard__keynote_edit_slide",
    "mcp__orchard__keynote_reorder_slides",
    "mcp__orchard__files_copy",
    "mcp__orchard__mail_save_attachment",
]

# ----------------------------------------------------------------------------
# output helpers
# ----------------------------------------------------------------------------

def say(msg: str = "") -> None:
    print(msg, flush=True)


def rule(title: str) -> None:
    say("")
    say("-" * 67)
    say("  " + title)
    say("-" * 67)


def ask(prompt: str) -> str | None:
    """Read one line; None means no answer is coming (end of input)."""
    try:
        return input(prompt)
    except EOFError:
        say("")
        return None


def yes(prompt: str, default: bool = False) -> bool:
    suffix = " [Y/n]: " if default else " [y/N]: "
    ans = ask(prompt + suffix)
    if ans is None:
        return False  # no answer is never a yes
    ans = ans.strip().lower()
    if not ans:
        return default
    return ans.startswith("y")


def wait_for_return(prompt: str = "Press Return when you have done that") -> bool:
    ans = ask("  " + prompt + " (or type s and Return to skip this step): ")
    if ans is None:
        return False
    return ans.strip().lower() != "s"


def assistant_choice() -> str:
    """The owner's assistant: claude, chatgpt or both. The installer keeps it
    as one word in ~/.config/moblee/assistant; no file means claude. Read only
    to choose what the checklist says about itself; nothing else depends on it."""
    # Read as the installer and the updater read it: the first line, spaces
    # dropped, and the word exactly as they write it. Anything else is no choice.
    try:
        text = (CONFIG_DIR / "assistant").read_text(errors="replace")
    except (OSError, ValueError):
        return "claude"
    word = "".join(text.split("\n", 1)[0].split())
    return word if word in ("claude", "chatgpt", "both") else "claude"


def checklist_opening(checking: bool) -> tuple[list, bool]:
    """What the checklist says about itself before it starts, and whether the
    run stops there.

    (v0.9.4) An owner who uses ChatGPT alone is told plainly that nothing on
    this list is set up for them yet, and the run ends. Until now they were
    told that, and then told on the very next line to go and install Claude
    Code, which is the one thing they had already said they were not doing.
    The two messages were written as separate questions and neither knew about
    the other. An owner who uses both still needs the Claude Code line, because
    for them the items do work.

    --check changes nothing and the companion runs it whatever the assistant,
    so that one keeps going, after saying what it is about to report.
    """
    assistant = assistant_choice()
    if assistant == "chatgpt":
        lines = [
            "Everything on this list is set up for Claude: the connections, the plugins,",
            "the optional skills and the voice. You use ChatGPT. Moblee does not set any",
            "of them up for ChatGPT yet, so there is nothing here for you to add today.",
            "",
            "Nothing is wrong, and nothing needs doing. When Moblee can set these up for",
            "ChatGPT, an update will tell you.",
        ]
        if not checking:
            return lines, True
        return lines + [
            "",
            "The test below still runs, and changes nothing. Every item on it is a Claude",
            "item, so it will say they are not set up. That is expected.",
        ], False
    lines = []
    if assistant == "both":
        lines += [
            "The connections, plugins, optional skills and voice on this list are set up",
            "for Claude. They work when you use Claude. Moblee does not set them up for",
            "ChatGPT yet.",
        ]
    if not claude_ok():
        lines += [
            "Claude Code is not installed yet. Install it first (see docs/01-prerequisites.md),",
            "then run this again. Items that do not need it can still be added now.",
        ]
    return lines, False


def open_url(url: str) -> None:
    subprocess.run(["open", url], check=False)


def open_in_chrome(url: str) -> None:
    if CHROME_APP.exists():
        subprocess.run(["open", "-a", "Google Chrome", url], check=False)
    else:
        open_url(url)


# ----------------------------------------------------------------------------
# commands
# ----------------------------------------------------------------------------

def brew_prefix() -> Path | None:
    for p in (Path("/opt/homebrew"), Path("/usr/local")):
        if (p / "bin" / "brew").exists():
            return p
    return None


def _usual_tool_dirs() -> list:
    """(0.15.2) Where a working tool sits that the app's short PATH misses:
    nodejs.org's and GitHub's own installers on Apple silicon (/usr/local/bin),
    Anthropic's installer for Claude (~/.local/bin), and Claude's engine inside
    the Claude app. Added after the PATH, so the owner's own copy still wins."""
    import glob
    dirs = [Path("/usr/local/bin"), Path.home() / ".local" / "bin"]
    engines = newest_first(glob.glob(str(Path.home() / "Library" / "Application Support" / "Claude" / "claude-code"
                                         / "*" / "*" / "claude.app" / "Contents" / "MacOS")))
    if engines:
        dirs.append(Path(engines[0]))
    return [str(d) for d in dirs if d.is_dir()]


def newest_first(paths: list) -> list:
    """(0.15.2) Newest copy first, by when it was put there: sorting the names
    put 2.9.0 after 2.10.0, so an older copy left on disk was the one used."""
    def when(p):
        try:
            return os.path.getmtime(p)
        except OSError:
            return 0.0
    return sorted(paths, key=when, reverse=True)


def env_with_brew() -> dict:
    env = dict(os.environ)
    prefix = brew_prefix()
    extra = [str(prefix / "bin"), str(prefix / "sbin")] if prefix else []
    path = env.get("PATH", "/usr/bin:/bin")
    after = [d for d in _usual_tool_dirs() if d not in path.split(":") and d not in extra]
    env["PATH"] = ":".join(extra + [path] + after)
    env["HOMEBREW_NO_INSTALL_CLEANUP"] = "1"  # Homebrew removes old versions otherwise
    env["HOMEBREW_NO_ENV_HINTS"] = "1"
    return env


def which(name: str) -> str | None:
    return shutil.which(name, path=env_with_brew()["PATH"])


def run(cmd: list, quiet: bool = True, timeout: int | None = None, interactive: bool = False) -> tuple[int, str]:
    """Run a command. Interactive commands share the Terminal with the owner."""
    try:
        if interactive:
            r = subprocess.run(cmd, env=env_with_brew(), timeout=timeout)
            return r.returncode, ""
        r = subprocess.run(cmd, env=env_with_brew(), capture_output=True, text=True, timeout=timeout)
        out = (r.stdout or "") + (r.stderr or "")
        if not quiet and out.strip():
            say(out.rstrip())
        return r.returncode, out
    except FileNotFoundError:
        return 127, f"{cmd[0]}: not found"
    except subprocess.TimeoutExpired:
        return 124, "timed out"


def log_path() -> Path:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    return CONFIG_DIR / f"setup-{STAMP}.log"


def run_logged(cmd: list, label: str, timeout: int = 3600) -> bool:
    """Run a long install quietly, keeping its full output in the setup log."""
    say(f"  {label}...")
    code, out = run(cmd, timeout=timeout)
    with open(log_path(), "a") as fh:
        fh.write(f"\n$ {' '.join(cmd)}\n{out}\n[exit {code}]\n")
    if code != 0:
        tail = "\n".join(out.strip().splitlines()[-6:])
        say(f"  That did not work. The last lines it printed:")
        for line in tail.splitlines():
            say("    " + line)
        say(f"  The full output is kept at {log_path()}")
    return code == 0


def backup(path: Path) -> Path | None:
    if not path.exists():
        return None
    dst = BACKUP_ROOT / STAMP / path.name
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not dst.exists():
        shutil.copy2(path, dst)
    return dst


# ----------------------------------------------------------------------------
# foundations: the things other items stand on
# ----------------------------------------------------------------------------

def devtools_ok() -> bool:
    return run(["xcode-select", "-p"])[0] == 0


def install_devtools() -> bool:
    if devtools_ok():
        return True
    rule("Apple's developer tools")
    say("Several of the tools you ticked need Apple's free developer tools.")
    say("A window will appear asking to install them. Click Install, then Agree.")
    say("It usually takes 5 to 20 minutes. This window will wait.")
    run(["xcode-select", "--install"])
    deadline = time.time() + 45 * 60
    while time.time() < deadline:
        if devtools_ok():
            say("  Developer tools are installed.")
            return True
        if not wait_for_return("Press Return once the developer tools window says it has finished"):
            break
    ok = devtools_ok()
    if not ok:
        say("  The developer tools are not installed yet. Items that need them will be skipped;")
        say("  run this checklist again once they are in.")
    return ok


def homebrew_ok() -> bool:
    return brew_prefix() is not None


def ensure_brew_on_path() -> None:
    """Homebrew's own 'next steps': make brew findable in every new Terminal
    window, which is also the shell Claude Code runs its commands in."""
    prefix = brew_prefix()
    if not prefix:
        return
    if run(["/bin/zsh", "-lc", "command -v brew"], timeout=60)[0] == 0:
        return
    zprofile = HOME / ".zprofile"
    existing = zprofile.read_text() if zprofile.exists() else ""
    if f"{prefix}/bin/brew shellenv" in existing:
        return
    backup(zprofile)
    with open(zprofile, "a") as fh:
        fh.write(f'\n# Homebrew (added by Moblee setup)\neval "$({prefix}/bin/brew shellenv)"\n')
    say("  Homebrew added to the path for new Terminal windows (in ~/.zprofile).")


def install_homebrew() -> bool:
    if homebrew_ok():
        ensure_brew_on_path()
        return True
    rule("Homebrew")
    say("Homebrew is the free, standard way to install tools on a Mac, and most of")
    say("what you ticked comes through it. Its own installer runs now.")
    say("")
    say("  1. It asks for your Mac password (the one you log in with). Typing it")
    say("     shows nothing on screen. That is normal; type it and press Return.")
    say("  2. It then asks you to press Return to continue. Press Return.")
    say("  3. It takes 5 to 10 minutes.")
    say("  4. At the end it prints 'Next steps' with some commands. Ignore them;")
    say("     this checklist does that step for you.")
    say("")
    if not wait_for_return("Press Return to start the Homebrew installer"):
        return False
    tmp = Path(tempfile.mkdtemp(prefix="moblee-brew-")) / "install.sh"
    code, out = run(["curl", "-fsSL", "--max-time", "120", HOMEBREW_INSTALLER, "-o", str(tmp)], timeout=180)
    if code != 0:
        say("  Could not download Homebrew's installer. Check the internet connection and try again.")
        return False
    run(["/bin/bash", str(tmp)], interactive=True)
    if not brew_prefix():
        say("  Homebrew did not install. Items that need it will be skipped.")
        return False
    ensure_brew_on_path()
    say("  Homebrew is installed.")
    return True


def brew_has(formula: str) -> bool:
    return run(["brew", "list", "--versions", formula], timeout=60)[0] == 0


def brew_install(formulas: list, cask: bool = False) -> bool:
    ok = True
    for f in formulas:
        if not cask and brew_has(f):
            continue
        cmd = ["brew", "install"] + (["--cask"] if cask else []) + [f]
        ok = run_logged(cmd, f"Installing {f}", timeout=3600) and ok
    return ok


def claude_ok() -> bool:
    return which("claude") is not None


def plugin_installed(plugin_id: str) -> bool | None:
    """True or False, or None when Moblee could not ask (no `claude` found, or
    it did not answer in time), which a check reports as unseen, not as off.
    (0.15.2) Claude's own record of installed plugins is read first: it is a
    file, so it answers when the app's PATH cannot find `claude`. Only an
    install for the whole Mac counts (scope "user", as install_plugin makes
    it): one made inside another project does not reach this wiki."""
    record_read = False
    try:
        record = json.loads((Path.home() / ".claude" / "plugins" / "installed_plugins.json").read_text(encoding="utf-8"))
        plugins = record.get("plugins", record) if isinstance(record, dict) else {}
        if isinstance(plugins, dict):
            record_read = True
            entries = plugins.get(plugin_id)
            if isinstance(entries, list):
                if any(isinstance(e, dict) and e.get("scope") == "user" for e in entries):
                    return True
            elif entries:
                return True
    except (OSError, ValueError):
        pass
    if not claude_ok():
        # Claude's own record answered, and the plugin is not in it for this Mac.
        return False if record_read else None
    code, out = run(["claude", "plugin", "list", "--json"], timeout=120)
    if code in (124, 127):
        return None
    if code != 0:
        code, out = run(["claude", "plugin", "list"], timeout=120)
        if code in (124, 127):
            return None
    return plugin_id in out


def plugin_reading(plugin_id: str, missing: str) -> tuple | None:
    """The check's answer when the plugin is not plainly installed: unseen when
    Moblee could not ask, else off with the given words; None when installed."""
    have = plugin_installed(plugin_id)
    if have is None:
        return None, "Moblee could not ask Claude which plugins are installed just now; Look again to try once more"
    if not have:
        return False, missing
    return None


def install_plugin(marketplace_repo: str, plugin_id: str) -> bool:
    if not claude_ok():
        say("  Claude Code is not installed, so the plugin cannot be added yet.")
        return False
    if plugin_installed(plugin_id):
        return True
    market = plugin_id.split("@", 1)[1]
    code, out = run(["claude", "plugin", "marketplace", "list"], timeout=120)
    if market not in out:
        if not run_logged(["claude", "plugin", "marketplace", "add", marketplace_repo], f"Adding the {market} plugin source", timeout=600):
            return False
    label = f"Installing {plugin_id.split('@')[0]}"
    code, out = run(["claude", "plugin", "install", "--scope", "user", "--yes", plugin_id], timeout=900)
    if code != 0 and "unknown option" in out.lower():  # an older Claude Code without --yes
        return run_logged(["claude", "plugin", "install", "--scope", "user", plugin_id], label, timeout=900)
    with open(log_path(), "a") as fh:
        fh.write(f"\n$ claude plugin install {plugin_id}\n{out}\n[exit {code}]\n")
    say(f"  {label}... {'done' if code == 0 else 'did not work (details in ' + str(log_path()) + ')'}")
    return code == 0


# Each optional skill carries a marker file, so the checklist can tell its own
# copy from an owner's skill of the same name, and an old copy from a current one.
SKILL_MARKER = ".moblee-extra"


def _tree_digest(folder: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    for f in sorted(p for p in folder.rglob("*") if p.is_file() and p.name != ".DS_Store"):
        h.update(str(f.relative_to(folder)).encode())
        h.update(f.read_bytes())
    return h.hexdigest()


def skill_state(name: str) -> str:
    """'current', 'outdated', 'foreign' (the owner's own skill), or 'absent'."""
    dst = SKILLS_DST / name
    if not (dst / "SKILL.md").exists():
        return "absent"
    if not (dst / SKILL_MARKER).exists():
        return "foreign"
    src = EXTRA_SKILLS / name
    if src.exists() and _tree_digest(src) != _tree_digest(dst):
        return "outdated"
    return "current"


def skill_installed(name: str) -> bool:
    return skill_state(name) == "current"


def skill_problem(name: str) -> str:
    return {"absent": f"the {name} skill is not installed",
            "outdated": f"the {name} skill is an older version (run this item again to update it)",
            "foreign": f"a skill of your own called '{name}' is in the way; Moblee's is not installed",
            }.get(skill_state(name), "")


def install_skill(name: str) -> bool:
    src = EXTRA_SKILLS / name
    if not (src / "SKILL.md").exists():
        say(f"  The {name} skill is missing from this copy of Moblee.")
        return False
    state = skill_state(name)
    if state == "current":
        return True
    if state == "foreign":
        say(f"  You already have a skill of your own called '{name}', so Moblee's was not")
        say("  installed over it. Rename yours in ~/.claude/skills/ if you want Moblee's.")
        return False
    dst = SKILLS_DST / name
    SKILLS_DST.mkdir(parents=True, exist_ok=True)
    if state == "outdated":
        # The old copy is kept in the backups, then the folder is brought up to
        # date file by file. A file the new version dropped is left in place
        # (harmless: only SKILL.md is read), because nothing here deletes.
        keep = BACKUP_ROOT / STAMP / "skills" / name
        if not keep.exists():
            shutil.copytree(dst, keep)
    shutil.copytree(src, dst, dirs_exist_ok=True)
    return True


def connector_status(name: str, _cache: dict = {}) -> str:
    """'connected', 'needs-login', 'absent', or 'no-claude-ai' for a claude.ai connector.

    'no-claude-ai' means this script cannot see the owner's connections at all:
    the `claude` command is missing, or is not signed in with a Claude account.
    That is the ordinary state of an owner who uses the Claude desktop app,
    which signs in separately, so it is reported as "cannot be seen from here"
    and never as "not working"."""
    if "out" not in _cache:
        say("  Asking Claude Code which connections it can see (this can take a minute or two)...")
        # A test can stand a pretend `claude` in for the real one, but only in a
        # declared practice run, the same rule the app's practice switches follow.
        stand_in = os.environ.get("MOBLEE_CLAUDE") if os.environ.get("MOBLEE_PRACTICE") == "1" else None
        if stand_in:
            _cache["out"] = run([stand_in, "mcp", "list"], timeout=240)[1]
        else:
            _cache["out"] = run(["claude", "mcp", "list"], timeout=240)[1] if claude_ok() else ""
    lines = _cache["out"].splitlines()
    for line in lines:
        if line.startswith(f"claude.ai {name}:"):
            return "connected" if "Connected" in line and "✘" not in line else "needs-login"
    if not any(l.startswith("claude.ai ") for l in lines):
        return "no-claude-ai"
    return "absent"


NO_CLAUDE_AI = ("connections made in the Claude app only show inside Claude, so this check cannot "
                "see them. Ask Claude \"{ask}\"; if it answers, it is connected. (In Terminal's "
                "Claude Code, /login with your Claude account lets this check see them too)")
ASK = {"google": "what is on my calendar today?", "generation": "can you see ElevenLabs?"}

APP_STATE = CONFIG_DIR / "app-state.json"


def owner_said_done(key: str) -> bool:
    """The owner pressed Done on this item's tile in the Moblee app."""
    try:
        done = json.loads(APP_STATE.read_text()).get("done", [])
    except (OSError, ValueError, AttributeError):
        return False
    if not isinstance(done, list):
        return False
    # the app writes "item:google@<the date on the request>"; an older app wrote "item:google"
    return any(isinstance(d, str) and (d == f"item:{key}" or d.startswith(f"item:{key}@")) for d in done)


def unseen(key: str):
    """What a check returns when it cannot see the thing it is asked about.
    None is neither working nor broken. The owner's own word, given in the
    Moblee app, is reported as exactly that and no more."""
    why = NO_CLAUDE_AI.format(ask=ASK.get(key, "can you use it?"))
    if owner_said_done(key):
        return None, "you marked this as connected in Moblee; " + why
    return None, why


def forget_connector_cache() -> None:
    connector_status.__defaults__[0].clear()


def chrome_extension_present(ext_id: str) -> bool:
    if not CHROME_PROFILES.exists():
        return False
    for profile in CHROME_PROFILES.iterdir():
        if (profile / "Extensions" / ext_id).exists():
            return True
    return False


def load_settings() -> dict:
    if not SETTINGS.exists():
        return {}
    return json.loads(SETTINGS.read_text())


def add_deny_rules(rules: list, kind: str = "deny") -> bool:
    """Add permission rules ('deny' blocks a tool, 'ask' makes Claude ask every time)."""
    try:
        data = load_settings()
    except json.JSONDecodeError:
        say("  ~/.claude/settings.json could not be read, so the safety rules were not added.")
        return False
    listed = data.setdefault("permissions", {}).setdefault(kind, [])
    missing = [r for r in rules if r not in listed]
    if not missing:
        return True
    backup(SETTINGS)
    listed.extend(missing)
    SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    new_text = json.dumps(data, indent=2) + "\n"
    json.loads(new_text)  # prove it parses before anything is written
    SETTINGS.write_text(new_text)
    json.loads(SETTINGS.read_text())
    return True


def deny_rules_present(rules: list, kind: str = "deny") -> bool | None:
    """(0.16.0) None when Claude's settings file is there and cannot be read:
    whether the rules are in it cannot be told, which is not the same as no."""
    try:
        data = load_settings()
    except (OSError, ValueError):
        return None
    perms = data.get("permissions") if isinstance(data, dict) else None
    listed = perms.get(kind) if isinstance(perms, dict) else None
    return all(r in listed for r in rules) if isinstance(listed, list) else not rules


# ----------------------------------------------------------------------------
# the items
# ----------------------------------------------------------------------------

class Item:
    def __init__(self, key, group, title, what, minutes, space_mb, cost,
                 needs=(), signin=None, install=None, check=None):
        self.key, self.group, self.title, self.what = key, group, title, what
        self.minutes, self.space_mb, self.cost = minutes, space_mb, cost
        self.needs, self.signin = list(needs), signin
        self._install, self._check = install, check

    def check(self) -> tuple[bool, str]:
        try:
            return self._check()
        except Exception as exc:  # a check must never crash the checklist
            # (0.15.2) A check that broke saw nothing, so it says so rather than
            # calling the item off and offering to install it again.
            return None, f"Moblee could not check this just now ({exc})"

    def install(self) -> bool:
        return self._install()


# --- Mac apps (Orchard) ------------------------------------------------------

def orchard_entry() -> Path | None:
    """Wherever npm put it: Homebrew's Node, or a Node from nodejs.org."""
    roots = []
    npm = which("npm")
    if npm:
        code, out = run([npm, "root", "-g"], timeout=60)
        if code == 0 and out.strip():
            roots.append(Path(out.strip().splitlines()[-1]))
    prefix = brew_prefix()
    if prefix:
        roots.append(prefix / "lib" / "node_modules")
    roots.append(Path("/usr/local/lib/node_modules"))  # (0.15.2) nodejs.org's Node on Apple silicon
    for root in roots:
        p = root / "@l22-io" / "orchard-mcp" / "build" / "index.js"
        if p.exists():
            return p
    return None


def node_major() -> int:
    node = which("node")
    if not node:
        return 0
    code, out = run([node, "--version"], timeout=30)
    try:
        return int(out.strip().lstrip("v").split(".")[0]) if code == 0 else 0
    except ValueError:
        return 0


def check_mac_apps():
    entry = orchard_entry()
    if not entry:
        return False, "the Mac apps link is not installed"
    bridge = entry.parent.parent / "swift" / ".build" / "AppleBridge.app"
    if not bridge.exists():
        return False, "installed, but its setup step has not been run (run the checklist item again)"
    if not claude_ok():
        return None, "installed; Moblee could not find Claude here to ask whether it is connected"
    code, out = run(["claude", "mcp", "get", "orchard"], timeout=120)
    if code in (124, 127):
        return None, "installed; Claude did not answer in time to say whether it is connected"
    if code != 0:
        return False, "installed, but not connected to Claude"
    if "Connected" not in out or "✘" in out:
        return False, "registered with Claude, but it does not start; run the checklist item again"
    blocked = deny_rules_present(ORCHARD_DENY)
    if blocked is None:
        return None, "connected; Claude's settings file could not be read, so whether its delete tools are blocked cannot be told"
    if not blocked:
        return False, "connected, but its delete tools are not blocked"
    return True, "connected: Claude can read Calendar, Reminders, Mail and Notes when you ask"


def install_mac_apps():
    major = int(platform.mac_ver()[0].split(".")[0] or 0)
    if major and major < 14:
        say("  This needs macOS 14 (Sonoma) or later. Update macOS first, then run the checklist again.")
        return False
    if node_major() < 22:  # Orchard needs Node 22 or later
        if not (homebrew_ok() and brew_install(["node"])):
            say("  The Mac apps link needs Node 22 or later, and it could not be installed.")
            return False
        if brew_has("node"):
            run_logged(["brew", "upgrade", "node"], "Bringing Node up to date", timeout=1800)
    node = which("node")
    npm = which("npm")
    if not (node and npm) or node_major() < 22:
        say("  The Mac apps link needs Node 22 or later, which is not available.")
        return False
    if not orchard_entry():
        if not run_logged([npm, "install", "-g", ORCHARD_PACKAGE], "Installing the Mac apps link", timeout=1200):
            say("  If the message mentions EACCES (permission denied), your Node was not installed")
            say("  by Homebrew. Run  brew install node  in Terminal, then this checklist item again.")
            return False
    entry = orchard_entry()
    if not entry:
        say("  The Mac apps link installed, but its files could not be found afterwards.")
        return False
    rule("Mac apps: permission")
    say("Your Mac will now ask whether this may read your Calendars and Reminders")
    say("(and possibly Mail and Notes).")
    say("")
    say("  1. On each pop-up, click Allow.")
    say("  2. When this window says 'Press Enter after granting access', press Return.")
    say("  3. At the end it prints a line starting 'claude mcp add'. Ignore it;")
    say("     this checklist does that step for you.")
    say("")
    say("If you click Don't Allow by mistake: System Settings, Privacy & Security,")
    say("Calendars, and switch on Terminal and AppleBridge.")
    say("")
    # The safety rules go in before the link is connected, never after.
    if not (add_deny_rules(ORCHARD_DENY, "deny") and add_deny_rules(ORCHARD_ASK, "ask")):
        return False
    if not wait_for_return("Press Return to start"):
        say("  Skipped. The Mac apps link is not connected; run this item again when ready.")
        return False
    run([node, str(entry), "setup"], interactive=True)
    if not (entry.parent.parent / "swift" / ".build" / "AppleBridge.app").exists():
        say("  The setup step did not finish. If it said 'Swift not found', Apple's developer")
        say("  tools are missing: tick this item again and the checklist installs them first.")
        return False
    if run(["claude", "mcp", "get", "orchard"], timeout=120)[0] != 0:
        if not run_logged(["claude", "mcp", "add", "--scope", "user", "orchard", "--", node, str(entry)],
                          "Connecting the Mac apps link to Claude", timeout=300):
            return False
    return True


# --- Google ------------------------------------------------------------------

def check_google():
    states = {n: connector_status(n) for n in ("Gmail", "Google Calendar", "Google Drive")}
    if "no-claude-ai" in states.values():
        return unseen("google")
    good = [n for n, s in states.items() if s == "connected"]
    if len(good) == 3:
        return True, "Gmail, Google Calendar and Google Drive are connected"
    missing = [n for n, s in states.items() if s != "connected"]
    return False, "not connected yet: " + ", ".join(missing)


def install_google():
    rule("Google: sign in (only you can do this)")
    say("Google connects through your Claude account, in the browser.")
    say("")
    say("  1. A page opens: claude.ai, Settings, Connectors. If it says Connectors has moved")
    say("     to Customise (seen September 2026), click Customise, then Connectors.")
    say("     If it asks you to log in, use the same Claude account as Claude Code.")
    say("  2. Find Gmail and click Connect. Sign in with your Google account and")
    say("     allow what Google asks.")
    say("  3. Do the same for Google Calendar, then Google Drive.")
    say("  4. To tell that it worked, ask Claude: what is on my calendar today?")
    say("  5. Come back to this window.")
    say("")
    open_url(CONNECTORS_URL)
    if not wait_for_return():
        return False
    forget_connector_cache()
    return True


# --- GitHub ------------------------------------------------------------------

def github_reachable(timeout: int = 10) -> bool:
    """(0.15.2) Whether GitHub answers from this Mac at all. `gh auth status`
    prints the same "token is invalid" offline as for a sign-in GitHub has
    revoked, so this is what tells the two apart. Any answer from GitHub, even
    an error page, counts as reached."""
    import urllib.error
    import urllib.request
    try:
        urllib.request.urlopen("https://api.github.com/zen", timeout=timeout).close()
        return True
    except urllib.error.HTTPError:
        return True
    except Exception:
        return False


def gh_signed_in(gh: str) -> bool | None:
    """(0.15.2) Whether GitHub's tool is signed in to github.com: True only
    when GitHub accepts the sign-in, False when it has none or GitHub turns it
    down, and None when the answer could not be had (offline, or the tool did
    not answer): until 0.15.2 an offline Mac read as "not signed in"."""
    code, out = run([gh, "auth", "token", "--hostname", "github.com"], timeout=30)
    if code in (124, 127):
        return None
    if code != 0 and ("no oauth token" in out.lower() or "not logged" in out.lower()):
        return False
    # A sign-in is kept (or this gh is from before 2.17, with no `auth token`):
    # ask GitHub whether it still takes it.
    code, out = run([gh, "auth", "status", "--hostname", "github.com"], timeout=60)
    if code == 0:
        return True
    if code in (124, 127):
        return None
    if "not logged" in out.lower():
        return False
    return False if github_reachable() else None


def check_github():
    gh = gh_tool()
    if not gh:
        return False, "GitHub's tool is not installed"
    signed = gh_signed_in(gh)
    if signed is None:
        return None, "GitHub's tool is installed; Moblee could not tell just now whether it is signed in"
    if not signed:
        return False, "installed, but not signed in"
    return True, "signed in to GitHub"


def install_github():
    gh = gh_tool()
    if gh and gh_signed_in(gh):
        return True                                # already working, wherever it was installed from
    if not brew_install(["gh"]):
        return False
    if run(["gh", "auth", "status"], timeout=60)[0] == 0:
        return True
    rule("GitHub: sign in (only you can do this)")
    say("If you do not have a GitHub account yet, make one first at github.com")
    say("(free), then come back.")
    say("")
    say("  1. If it asks 'Authenticate Git with your GitHub credentials?', press Return (Yes).")
    say("  2. It shows a code like ABCD-1234. Press Return.")
    say("  3. Your browser opens. Paste the code and click Authorize.")
    say("  4. Come back to this window.")
    say("")
    if not wait_for_return("Press Return to start"):
        return False
    run(["gh", "auth", "login", "--hostname", "github.com", "--git-protocol", "https", "--web"], interactive=True)
    return run(["gh", "auth", "status"], timeout=60)[0] == 0


# --- Chrome ------------------------------------------------------------------

def check_chrome():
    if not CHROME_APP.exists():
        return False, "Google Chrome is not installed"
    if not chrome_extension_present(CLAUDE_EXTENSION_ID):
        return False, "Chrome is here, but the Claude extension is not"
    note = "" if chrome_extension_present(CLIPPER_EXTENSION_ID) else " (the Web Clipper is not added)"
    return True, "Chrome has the Claude extension" + note


def install_chrome():
    if not CHROME_APP.exists():
        if not brew_install(["google-chrome"], cask=True):
            return False
    rule("Chrome: two extensions and your logins (only you can do this)")
    say("Chrome is how Claude reads X, Instagram and YouTube: it uses the logins")
    say("you already have in Chrome, and never posts anything without your yes.")
    say("")
    say("  1. A Chrome page opens on the Claude extension. Click Add to Chrome,")
    say("     then pin it (the puzzle-piece icon, then the pin).")
    say("  2. Click the Claude icon and sign in with the same Claude account.")
    say("  3. A second page opens on the Obsidian Web Clipper. Add it too; it")
    say("     saves any web page into your wiki. It saves to a folder called")
    say("     Clippings unless you change it, which is where your wiki looks,")
    say("     so leave that setting as it is.")
    say("  4. In Chrome, log in to x.com, instagram.com and youtube.com if you")
    say("     are not already.")
    say("  5. Come back to this window.")
    say("")
    open_in_chrome(CLAUDE_EXTENSION_URL)
    open_in_chrome(CLIPPER_EXTENSION_URL)
    if not wait_for_return():
        return False
    say("")
    say("  One more step, later, inside Claude Code: type /chrome and switch it on.")
    return True


# --- tools behind the skills -------------------------------------------------

def check_videos():
    missing = [t for t in ("yt-dlp", "ffmpeg") if not which(t)]
    if missing:
        return False, "missing " + ", ".join(missing)
    off = plugin_reading("watch@claude-video", "the watch tool is not installed in Claude Code")
    if off:
        return off
    return True, "Claude can watch and summarise videos (type /watch and a link)"


def install_videos():
    ok = brew_install(["yt-dlp", "ffmpeg"])
    if brew_has("yt-dlp"):
        run_logged(["brew", "upgrade", "yt-dlp"], "Bringing the video downloader up to date", timeout=900)
    return install_plugin("bradautomates/claude-video", "watch@claude-video") and ok


# The PDF renderer runs on Homebrew's Python: the Python that ships with macOS
# cannot load Homebrew's graphics libraries on Apple silicon. The interpreter
# is recorded where the wiki-to-pdf skill looks for it.
PDF_PYTHON_FILE = CONFIG_DIR / "pdf-python"


def pdf_python() -> str | None:
    prefix = brew_prefix()
    if prefix and (prefix / "bin" / "python3").exists():
        return str(prefix / "bin" / "python3")
    return None


def pdf_pythons() -> list:
    """(0.15.2) Every Python that may hold the PDF renderer: Homebrew's, and the
    one recorded where the wiki-to-pdf skill reads it (which an owner may have
    set up with another Python, as that skill's own notes allow)."""
    found = [pdf_python()]
    try:
        found.append(PDF_PYTHON_FILE.read_text(encoding="utf-8").strip())
    except OSError:
        pass
    out = []
    for py in found:
        if py and Path(py).is_file() and py not in out:
            out.append(py)
    return out


def renders_pdfs(py: str) -> bool:
    return run([py, "-c", "import weasyprint, markdown, jinja2, yaml, pypdf"], timeout=120)[0] == 0


def weasyprint_ok() -> bool:
    return any(renders_pdfs(py) for py in pdf_pythons())


def check_documents():
    problems = []
    if not weasyprint_ok():
        problems.append("the PDF renderer")
    off = plugin_reading("document-skills@anthropic-agent-skills", "")
    if off and off[0] is None and not problems:
        return off
    if off and off[0] is False:
        problems.append("the Word, PowerPoint and Excel tools")
    if problems:
        return False, "missing " + " and ".join(problems)
    return True, "PDF, Word, PowerPoint and Excel all work"


def install_documents():
    ok = brew_install(["python", "cairo", "pango", "gdk-pixbuf", "libffi"])
    py = pdf_python()
    # (0.15.2) Homebrew's own Python is the one set up and recorded here, so it is
    # the one asked: another Python that already renders is not overwritten
    # in the record unless Homebrew's renders too.
    if py and not renders_pdfs(py):
        ok = run_logged([py, "-m", "pip", "install", "--user", "--break-system-packages",
                         "weasyprint", "markdown", "jinja2", "PyYAML", "pypdf"],
                        "Installing the PDF renderer", timeout=1800) and ok
    if py and renders_pdfs(py):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        PDF_PYTHON_FILE.write_text(py + "\n")
    elif not py:
        say("  Homebrew's Python did not install, so the PDF renderer could not be set up.")
        ok = False
    return install_plugin("anthropics/skills", "document-skills@anthropic-agent-skills") and ok


def check_film():
    missing = [t for t in ("node", "ffmpeg") if not which(t)]
    if missing:
        return False, "missing " + ", ".join(missing)
    off = plugin_reading("remotion@remotion", "the video studio plugin is not installed")
    if off:
        return off
    if not skill_installed("film"):
        return False, skill_problem("film")
    return True, "video editing works (say 'make a film' or 'edit this video')"


def install_film():
    ok = brew_install(["node", "ffmpeg"])
    ok = install_plugin("remotion-dev/claude-code-plugin", "remotion@remotion") and ok
    return install_skill("film") and ok


def check_audio():
    if not which("ffmpeg"):
        return False, "missing ffmpeg"
    if not skill_installed("audio"):
        return False, skill_problem("audio")
    return True, "audio editing and read-aloud work"


def install_audio():
    ok = brew_install(["ffmpeg"])
    return install_skill("audio") and ok


def check_pictures():
    if not which("magick"):
        return False, "missing ImageMagick"
    if not skill_installed("pictures"):
        return False, skill_problem("pictures")
    return True, "picture editing works"


def install_pictures():
    ok = brew_install(["imagemagick"])
    return install_skill("pictures") and ok


def skill_item(name: str, label: str):
    def check():
        return (True, label) if skill_installed(name) else (False, skill_problem(name))

    def install():
        return install_skill(name)
    return check, install


def check_x_capture():
    if not skill_installed("x-capture"):
        return False, skill_problem("x-capture")
    if not chrome_extension_present(CLAUDE_EXTENSION_ID):
        return False, "installed, but it needs the Chrome item to work"
    return True, "paste an x.com link and say 'capture this'"


def check_skill_maker():
    off = plugin_reading("skill-creator@claude-plugins-official", "not installed")
    return off or (True, "say 'make a skill for ...' to teach Claude a routine")


def install_skill_maker():
    return install_plugin("anthropics/claude-plugins-official", "skill-creator@claude-plugins-official")


def check_obsidian_extras():
    off = plugin_reading("obsidian@obsidian-skills", "not installed")
    return off or (True, "canvases, databases and Obsidian's own formats")


def install_obsidian_extras():
    return install_plugin("kepano/obsidian-skills", "obsidian@obsidian-skills")


# --- the vault's own options (these used to be separate installer questions) --

def vault_path() -> Path | None:
    env = os.environ.get("MOBLEE_VAULT")
    if env and Path(env).is_dir():
        return Path(env)
    p = CONFIG_DIR / "vault-path"
    if p.exists():
        v = Path(p.read_text().strip())
        if v.is_dir():
            return v
    return None


def check_weekly():
    agent = HOME / "Library" / "LaunchAgents" / "com.moblee.weekly-lint.plist"
    if not agent.exists():
        return False, "not scheduled"
    if run(["launchctl", "print", f"gui/{os.getuid()}/com.moblee.weekly-lint"], timeout=30)[0] != 0:
        return False, "the schedule is written but not switched on (run this item again)"
    return True, "the health check runs by itself every Saturday"


# --- (0.12.0) alerts on the phone, reach from the phone, thinking jobs ----------

NTFY_TOPIC = CONFIG_DIR / "ntfy-topic"
REACH_FILE = CONFIG_DIR / "reach.json"
CLAUDE_TOKEN = CONFIG_DIR / "claude-token"
TAILSCALE_CLI = Path("/Applications/Tailscale.app/Contents/MacOS/Tailscale")


def check_alerts():
    try:
        t = NTFY_TOPIC.read_text(encoding="utf-8").strip()
    except OSError:
        return False, "not set up"
    if not t:
        return False, "not set up"
    return True, "alerts reach the ntfy app on your phone"


def install_alerts():
    import secrets
    rule("Alerts on your phone")
    say("  A free app called ntfy on your phone shows a line when a job of yours")
    say("  finishes or fails. Nothing but that line leaves this Mac: it names the")
    say("  file to look at and never sends the file.")
    say("")
    try:
        code = NTFY_TOPIC.read_text(encoding="utf-8").strip()
    except OSError:
        code = ""
    if not code:
        code = "moblee-" + secrets.token_urlsafe(12).replace("_", "x").replace("-", "y")
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        NTFY_TOPIC.write_text(code + "\n", encoding="utf-8")
        os.chmod(NTFY_TOPIC, 0o600)
    say("  1. On your phone, get the app called ntfy from the App Store (it is free).")
    say("  2. Open it, press the + sign to add a channel, and type this code exactly:")
    say("")
    say(f"         {code}")
    say("")
    say("  3. Press Subscribe. That is all; the code is your private channel.")
    say("")
    if not wait_for_return("Press Return when the app shows the channel"):
        return False
    import urllib.request
    try:
        req = urllib.request.Request("https://ntfy.sh/" + code, data=b"Moblee: alerts are working. This is the test.", method="POST")
        req.add_header("Title", "Moblee")
        with urllib.request.urlopen(req, timeout=15) as r:
            ok = 200 <= r.status < 300
    except Exception:
        ok = False
    if ok:
        say("  A test alert was sent; it should be on your phone now.")
    else:
        say("  The test could not be sent just now (no internet?). The channel is set up; ask your assistant to send a test alert when you are back online.")
    return True


def check_reach():
    try:
        cfg = json.loads(REACH_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False, "no route chosen"
    addr = cfg.get("address") if isinstance(cfg, dict) else None
    if not isinstance(addr, str) or not addr or len(addr) > 253 or not all(c.isalnum() or c in ".-:" for c in addr):
        return False, "no route chosen"
    route = "Tailscale" if cfg.get("route") == "tailscale" else "your own private network"
    return True, f"things made to open from your phone do so over {route} while this Mac is awake"


def tailscale_ip() -> str | None:
    for cli in (TAILSCALE_CLI, Path(which("tailscale") or "/nonexistent")):
        if cli.exists():
            code, out = run([str(cli), "ip", "-4"], timeout=30)
            if code == 0:
                for line in out.splitlines():
                    line = line.strip()
                    if line.count(".") == 3 and all(p.isdigit() for p in line.split(".")):
                        return line
    return None


def install_reach():
    rule("Reach your things from your phone")
    say("  A thing built for you runs on this Mac. To open it from your phone, your")
    say("  phone needs a private way to reach this Mac. Two choices:")
    say("")
    say("  1. Tailscale (recommended): a free private network for your own devices.")
    say("     Nothing is opened to the internet. An account, the app on this Mac and")
    say("     on your phone, and a sign-in on each. About every six months Tailscale")
    say("     asks you to sign in again on each device; that is normal and you can leave it so.")
    say("  2. A private way home you already have: a VPN, or your router's remote access.")
    say("     You give this Mac's address as your phone sees it. If you do not know it,")
    say("     press 3 for now and ask your assistant, who can read it from this Mac and tell you.")
    say("  3. Not now.")
    say("")
    try:
        choice = input("  Which? Type 1, 2 or 3 and press Return: ").strip()
    except (EOFError, KeyboardInterrupt):
        return False
    if choice == "3":
        say("  Nothing was changed.")
        return False
    if choice == "2":
        try:
            addr = input("  This Mac's address on your network (for example 192.168.1.20): ").strip()
        except (EOFError, KeyboardInterrupt):
            return False
        if not addr or len(addr) > 253 or not all(c.isalnum() or c in ".-:" for c in addr):
            say("  That does not read as an address; nothing was changed.")
            return False
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        REACH_FILE.write_text(json.dumps({"route": "named", "address": addr,
                                          "recorded": datetime.date.today().isoformat()}, indent=2) + "\n", encoding="utf-8")
        say(f"  Recorded: your phone reaches this Mac at {addr}. Things made to open from your phone will open there while this Mac is awake.")
        return True
    if choice != "1":
        say("  Nothing was changed.")
        return False
    if not TAILSCALE_CLI.exists():
        if not brew_install(["tailscale"], cask=True):
            say("  Tailscale could not be installed. You can get it from tailscale.com and run this again.")
            return False
    say("")
    say("  Tailscale will open. Sign in (or make an account) in the window it shows, and")
    say("  when the Mac shows a box saying Tailscale would like to add VPN configurations,")
    say("  press Allow. Then come back here.")
    run(["open", "-a", "Tailscale"], timeout=30)
    if not wait_for_return("Press Return once you are signed in to Tailscale"):
        return False
    ip = tailscale_ip()
    if not ip:
        say("  Tailscale does not show an address yet. Finish signing in, then run this item again from Moblee.")
        return False
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    REACH_FILE.write_text(json.dumps({"route": "tailscale", "address": ip,
                                      "recorded": datetime.date.today().isoformat()}, indent=2) + "\n", encoding="utf-8")
    say(f"  Recorded: this Mac is {ip} on your Tailscale network. Put Tailscale on your phone too, signed in to")
    say("  the same account, and things made to open from your phone will open there while this Mac is awake.")
    return True


def claude_engine() -> str | None:
    """Claude's engine: inside the Claude app, newest first, else on the path."""
    import glob
    found = newest_first(glob.glob(str(Path.home() / "Library" / "Application Support" / "Claude" / "claude-code"
                                       / "*" / "*" / "claude.app" / "Contents" / "MacOS" / "claude")))
    if found:
        return found[0]
    return which("claude")


def check_thinking():
    try:
        tok = CLAUDE_TOKEN.read_text(encoding="utf-8").strip()
    except OSError:
        tok = ""
    if not tok:
        return False, "no long-lived sign-in yet"
    if not claude_engine():
        return False, "the sign-in is kept, but the Claude app was not found on this Mac"
    return True, "jobs can ask Claude while you are away; the sign-in is kept in a file only you can read"


def install_thinking():
    import getpass
    rule("Jobs that ask Claude while you are away")
    say("  A job that runs on a schedule and asks Claude to think (a morning page, a")
    say("  weekly tidy) needs a sign-in that works with nobody at the screen. Claude")
    say("  makes one for you; it lasts about a year, and when it runs out the jobs stop")
    say("  and tell your phone, and you do this once more. Each such run uses a little")
    say("  of your Claude allowance, which the job's page says.")
    say("")
    engine = claude_engine()
    if not engine:
        say("  The Claude app was not found on this Mac. Open it once, then run this again.")
        return False
    say("  1. A web page opens; sign in there if it asks, and press Allow.")
    say("  2. Back in this black window a long code starting sk-ant- appears. Drag across")
    say("     the whole code to select it, then press Command and C.")
    say("  3. Press Return here, then press Command and V to paste it when asked.")
    say("     Nothing shows while you paste; that is normal.")
    say("")
    if not wait_for_return("Press Return to start"):
        return False
    run([engine, "setup-token"], interactive=True, timeout=600)
    try:
        tok = getpass.getpass("  Paste the code and press Return: ").strip()
    except (EOFError, KeyboardInterrupt):
        return False
    if not tok.startswith("sk-ant-") or len(tok) < 40 or any(c.isspace() for c in tok):
        say("  That does not read as the code. Nothing was kept; run this again when you have it.")
        return False
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CLAUDE_TOKEN.write_text(tok + "\n", encoding="utf-8")
    os.chmod(CLAUDE_TOKEN, 0o600)
    say("  Kept, in a file only you can read. Jobs that ask Claude can now run while you are away.")
    return True


# --- (0.12.0) the two jobs that ask Claude: the weekly tidy and the morning page --

def thing_status(name: str) -> dict:
    v = vault_path()
    if not v:
        return {}
    code, out = run(["python3", str(PACKAGE_ROOT / "scripts" / "job-switch.py"), "--vault", str(v),
                     "--name", name, "--status", "--json"], timeout=60)
    try:
        d = json.loads(out)
        return d if isinstance(d, dict) else {}
    except ValueError:
        return {}


def install_thinking_thing(name: str, title: str, prompt_file: Path, when: list, what: str) -> bool:
    """Lay the thing down with the build skill's scaffold, give it Moblee's own
    prompt, and switch its job on: the owner pressed this item, which is their
    hand on the switch."""
    v = vault_path()
    if not v:
        say("  The wiki could not be found, so nothing was set up.")
        return False
    if not CLAUDE_TOKEN.exists():
        say("  This needs the item \"Jobs that ask Claude while you are away\" first, which keeps the")
        say("  sign-in a job uses when nobody is at the screen. Choose that, then this again.")
        return False
    parts = PACKAGE_ROOT / "skills" / "build" / "parts"
    code, out = run(["python3", str(parts / "scaffold.py"), "--vault", str(v), "--name", name, "--title", title,
                     "--what", what, "--think", *when], timeout=120)
    if code != 0:
        say("  The thing could not be laid down: " + out.strip().splitlines()[-1][:200] if out.strip() else "  The thing could not be laid down.")
        return False
    prompt = v / "apps" / name / "prompt.md"
    try:
        current = prompt.read_text(encoding="utf-8") if prompt.exists() else ""
    except OSError:
        current = ""
    if not current or "The assistant replaces this paragraph" in current:
        # Moblee's own words go in only where the owner has not written their own
        prompt.write_text(prompt_file.read_text(encoding="utf-8"), encoding="utf-8")
    code, out = run(["python3", str(PACKAGE_ROOT / "scripts" / "job-switch.py"), "--vault", str(v),
                     "--name", name, "--on", "--json"], timeout=60)
    try:
        d = json.loads(out)
    except ValueError:
        d = {}
    if code != 0 or not d.get("loaded"):
        say("  It was laid down but could not be switched on: " + str(d.get("why") or "the scheduler did not take it"))
        return False
    say(f"  {title} is switched on. It runs within limits written down for it, which your assistant can show or")
    say("  change, and a missed hour runs at the next wake.")
    return True


def check_tidy():
    s = thing_status("moblee-tidy")
    if not s.get("file"):
        return False, "not set up"
    if not s.get("loaded"):
        return False, "set up but not switched on (choose this item again)"
    last = s.get("last_run")
    return True, "runs after the Saturday check" + (f"; last ran {str(last)[:10]}" if last else "; has not run yet")


def install_tidy():
    rule("The weekly tidy")
    say("  After the Saturday check, Claude puts right what can safely be put right and")
    say("  lists the rest for you on one short page. One run a week of your allowance.")
    return install_thinking_thing("moblee-tidy", "Weekly tidy", PACKAGE_ROOT / "scripts" / "cadence" / "tidy-prompt.md",
                                  ["--weekday", "6", "--hour", "9", "--minute", "30"],
                                  "The weekly tidy: what the Saturday check found, put right where it safely can be, and the rest listed for the owner.")


def check_morning():
    s = thing_status("moblee-morning")
    if not s.get("file"):
        return False, "not set up"
    if not s.get("loaded"):
        return False, "set up but not switched on (choose this item again)"
    last = s.get("last_run")
    return True, "a morning page each day" + (f"; last written {str(last)[:10]}" if last else "; not written yet")


def install_morning():
    rule("Your morning page")
    say("  Each morning, at half past six or the first wake after it, Claude writes you a")
    say("  page: what is on today, what moved, what is waiting, one thing worth doing.")
    say("  One run a day of your allowance.")
    return install_thinking_thing("moblee-morning", "Morning page", PACKAGE_ROOT / "scripts" / "cadence" / "morning-prompt.md",
                                  ["--hour", "6", "--minute", "30"],
                                  "The morning page: what matters today, from what the wiki holds, written before the owner is up.")


# --- (0.12.0) memory search: the wiki searched by meaning, on this Mac only ----

OLLAMA_URL = os.environ.get("MOBLEE_OLLAMA", "http://127.0.0.1:11434")
EMBED_MODEL = "nomic-embed-text"


def recall_cache_dir(v: Path) -> Path:
    """One folder per wiki, the same formula as recall.py and the check-up."""
    import hashlib
    env = os.environ.get("MOBLEE_RECALL_CACHE")
    if env:
        return Path(os.path.expanduser(env))
    key = hashlib.sha1(os.path.realpath(str(v)).encode("utf-8")).hexdigest()[:12]
    return HOME / ".cache" / "moblee-recall" / key


def ollama_present() -> bool:
    """The app, the command, or a service already answering (Homebrew's
    `brew services` runs it with neither on the path)."""
    return Path("/Applications/Ollama.app").is_dir() or bool(which("ollama")) or ollama_up(2)


def ollama_up(timeout: float = 4) -> bool:
    import urllib.request
    try:
        with urllib.request.urlopen(OLLAMA_URL + "/api/tags", timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def ollama_has_model() -> bool:
    import urllib.request
    try:
        with urllib.request.urlopen(OLLAMA_URL + "/api/tags", timeout=4) as r:
            names = [m.get("name", "") for m in json.loads(r.read()).get("models", [])]
        return any(n.split(":")[0] == EMBED_MODEL for n in names)
    except Exception:
        return False


def recall_hook_registered() -> bool | None:
    """None when Claude's settings file is there and cannot be read (0.16.0)."""
    if not SETTINGS.exists():
        return False
    try:
        settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    hooks = settings.get("hooks") if isinstance(settings, dict) else None
    ups = hooks.get("UserPromptSubmit") if isinstance(hooks, dict) else None
    for g in ups or []:
        for h in (g.get("hooks") or []) if isinstance(g, dict) else []:
            if isinstance(h, dict) and "recall-inject.py" in str(h.get("command", "")):
                return True
    return False


def check_recall():
    v = vault_path()
    if not v or not (v / "scripts" / "recall" / "recall.py").exists():
        return False, "not set up"
    told = recall_hook_registered()
    if told is None:
        return None, "set up; Claude's settings file could not be read, so whether Claude uses it cannot be told"
    if not told:
        return False, "set up, but Claude has not been told to use it (choose this item again)"
    if not ollama_present():
        return False, "set up, but the small model's program (Ollama) is not on this Mac (choose this item again)"
    meta = recall_cache_dir(v) / "meta.json"
    if not meta.exists():
        return False, "set up, but the index has not been built yet (choose this item again)"
    try:
        built = json.loads(meta.read_text(encoding="utf-8")).get("count")
    except (OSError, ValueError):
        built = None
    return True, f"questions find the closest pages by meaning ({built} sections indexed)" if built else \
        "questions find the closest pages by meaning"


def pull_model() -> bool:
    """Fetch the embedding model through Ollama's own service, so no command
    line tool and no password are needed; progress is shown as it comes."""
    import urllib.request
    try:
        req = urllib.request.Request(OLLAMA_URL + "/api/pull", data=json.dumps({"name": EMBED_MODEL}).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=1800) as r:
            last = ""
            for line in r:
                try:
                    d = json.loads(line)
                except ValueError:
                    continue
                st = str(d.get("status", ""))
                if d.get("total") and d.get("completed"):
                    pct = int(100 * d["completed"] / d["total"])
                    st = f"{st} {pct}%"
                if st != last:
                    sys.stdout.write(f"\r     {st[:70]:<70}")
                    sys.stdout.flush()
                    last = st
                if d.get("error"):
                    say("")
                    say(f"  The model could not be fetched: {d['error']}")
                    return False
        say("")
        return True
    except Exception as exc:
        say("")
        say(f"  The model could not be fetched: {exc}")
        return False


def install_recall():
    rule("Memory search")
    say("  Your assistant finds pages by the words in them. Memory search adds finding")
    say("  them by meaning: when you ask a question, the three or four sections of your")
    say("  wiki closest to it are put in front of Claude before it reads your message,")
    say("  as leads to check. A small model (Ollama, about 300 MB) runs on this Mac for")
    say("  it; nothing leaves the Mac, and the index is a disposable copy outside the wiki.")
    say("")
    v = vault_path()
    if not v:
        say("  The wiki could not be found, so nothing was set up.")
        return False
    if not ollama_present():
        say("  Installing Ollama with Homebrew (it may ask for your Mac password; nothing shows as you type).")
        code, _ = run(["brew", "install", "--cask", "ollama"], interactive=True, timeout=1800)
        if code != 0 or not ollama_present():
            say("  Ollama could not be installed. Run this item again when you have a moment, or fetch it from ollama.com.")
            return False
    if not ollama_up():
        say("  Opening Ollama. The first time, the Mac may ask whether to open a program fetched from the")
        say("  internet: press Open. It may also offer to finish its own setup; that can be skipped.")
        if Path("/Applications/Ollama.app").is_dir():
            run(["open", "-gj", "/Applications/Ollama.app"], timeout=30)
        else:
            run(["open", "-gja", "Ollama"], timeout=30)
        for _ in range(18):
            time.sleep(5)
            if ollama_up():
                break
    if not ollama_up():
        say("  Ollama is installed but did not start. Open it once from Applications and answer what it asks,")
        say("  then choose this item again.")
        return False
    if not ollama_has_model():
        say("  Fetching the small model (about 300 MB, once)...")
        if not pull_model():
            return False
    say("  Putting the scripts in your wiki and telling Claude about them...")
    code, out = run(["python3", str(PACKAGE_ROOT / "extras" / "recall" / "install-recall.py"), "--vault", str(v)],
                    timeout=300)
    for line in out.strip().splitlines():
        say("   " + line)
    if code != 0:
        return False
    say("  Building the index: every section of your wiki is read once, which takes a minute")
    say("  on a new wiki and longer on a large one. This window waits.")
    code, out = run(["bash", str(v / "scripts" / "recall" / "rebuild-index.sh"), "setup"], timeout=3600)
    if not (recall_cache_dir(v) / "meta.json").exists():
        say("  The index was not built. Choose this item again; if it fails twice, ask your assistant why,")
        say("  which can read the reason.")
        return False
    say("  Done. Ask your assistant a question and it has the closest pages in front of it.")
    say("  The index refreshes by itself after each save and once a night, in seconds.")
    return True


def install_weekly():
    code, _ = run(["bash", str(PACKAGE_ROOT / "scripts" / "install-schedule.sh")], interactive=True, timeout=300)
    return code == 0


def check_lessons():
    v = vault_path()
    if v and (v / "wiki" / "Wiki Operations" / "Moblee Learning Path.md").exists():
        return True, "thirty-two lessons; say 'lesson' in the vault"
    return False, "not added"


def install_lessons():
    v = vault_path()
    if not v:
        say("  The vault could not be found, so the learning path was not added.")
        return False
    code, _ = run(["python3", str(PACKAGE_ROOT / "scripts" / "install-learning-path.py"), "--vault", str(v)],
                  interactive=True, timeout=300)
    return code == 0


def check_voice():
    try:
        hooks = load_settings().get("hooks", {})
    except (OSError, ValueError, AttributeError):
        return None, "Claude's settings file could not be read, so whether the voice is on cannot be told"
    blob = json.dumps(hooks)
    if "speak-elevenlabs.py" in blob:
        return True, "Claude reads its replies aloud"
    return False, "not installed"


def install_voice():
    say("  The voice installer asks its own questions. The Mac's built-in voice is free;")
    say("  it offers the ElevenLabs voice as an optional paid upgrade.")
    code, _ = run(["python3", str(PACKAGE_ROOT / "voice" / "install-voice.py")], interactive=True)
    return code == 0


def check_generation():
    s = connector_status("ElevenLabs")
    if s == "no-claude-ai":
        return unseen("generation")
    if s == "connected":
        return True, "ElevenLabs is connected: images, video, voices, music and sound effects"
    return False, "ElevenLabs is not connected"


def install_generation():
    rule("Creating new images, video and voices (your choice, with your own account)")
    say("This uses ElevenLabs, a separate company with its own account and prices.")
    say("As of September 2026 it has a free tier with small monthly limits and paid")
    say("plans from about 6 US dollars a month; check elevenlabs.io/pricing for today's")
    say("prices before you pay for anything. Moblee takes no money and sets no plan.")
    say("")
    say("  1. If you do not have an ElevenLabs account, make one at elevenlabs.io.")
    say("  2. A page opens: claude.ai, Settings, Connectors. If it says Connectors has moved")
    say("     to Customise (seen September 2026), click Customise, then Connectors.")
    say("  3. Find ElevenLabs, click Connect, and sign in with your ElevenLabs account.")
    say("  4. Come back to this window.")
    say("")
    say("Claude asks before anything that uses up your ElevenLabs credits.")
    say("")
    open_url(CONNECTORS_URL)
    if not wait_for_return():
        return False
    forget_connector_cache()
    return True


def check_vault_fn():
    zshrc = HOME / ".zshrc"
    if zshrc.exists() and "# >>> moblee vault function >>>" in zshrc.read_text():
        return True, "type 'vault' in Terminal to open Claude in your wiki"
    return False, "not added"


def install_vault_fn():
    zshrc = HOME / ".zshrc"
    text = zshrc.read_text() if zshrc.exists() else ""
    if "# >>> moblee vault function >>>" in text:
        return True
    backup(zshrc)
    fn = (PACKAGE_ROOT / "scripts" / "vault.sh").read_text()
    with open(zshrc, "a") as fh:
        fh.write("\n# >>> moblee vault function >>>\n" + fn + "\n# <<< moblee vault function <<<\n")
    return True


# --- (0.13.0) the Moblee Hub ----------------------------------------------------
#
# The Hub is the group's shared wiki of wikis: a private GitHub repository kept
# by one member (the keeper), with a shelf of recipes and a post office of notes.
# Moblee is a client of it and copies none of its code: it reads the Hub's
# manifest (hub.json) and the fixed layout beside it, knocks at the door the
# manifest names, and clones. The page, the checker and the rules keep arriving
# by pull. The defaults below are the group's own Hub; ~/.config/moblee/hub.json
# names another, and the MOBLEE_HUB_* settings exist for the tests. The Hub
# moved into the group's own GitHub organisation on 26 October 2026; 0.13.1
# carries the new addresses and follows a move instead of stalling on one.

HUB_DEFAULT = {
    "name": "Moblee Hub",
    "address": "https://github.com/Moblee-Main-Devs/moblee-hub.git",
    "join": "approve",
    "lobby": "https://github.com/Moblee-Main-Devs/moblee-hub-lobby",
}
HUB_CHOICE = CONFIG_DIR / "hub.json"
HUB_POLICIES = ("invite", "approve", "open")
HUB_ID_CHARS = set("abcdefghijklmnopqrstuvwxyz0123456789-")
HUB_SLUG_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_./")


def hub_settings() -> dict:
    """Which Hub, before the folder exists: the owner's choice on record, else the
    group's own. Once hub/ is a clone, its own hub.json is the word on it."""
    hub = dict(HUB_DEFAULT)
    try:
        chosen = json.loads(HUB_CHOICE.read_text(encoding="utf-8"))
        if isinstance(chosen, dict):
            hub.update({k: v for k, v in chosen.items() if isinstance(v, str) and k in hub})
    except (OSError, ValueError):
        pass
    for key in ("address", "join", "lobby"):
        env = os.environ.get("MOBLEE_HUB_" + key.upper())
        if env:
            hub[key] = env
    if hub.get("join") not in HUB_POLICIES:
        hub["join"] = "invite"
    return hub


def same_address(one: str, other: str) -> bool:
    """(0.15.2) On GitHub, the https and SSH forms of one repository are one
    address, so a member who cloned over SSH is not told the Hub is elsewhere."""
    a, b = repo_slug(one), repo_slug(other)
    if a and b:
        return a.lower() == b.lower()

    def norm(a: str) -> str:
        a = (a or "").strip().rstrip("/")
        if a.endswith(".git"):
            a = a[:-4]
        return a.lower()
    return norm(one) == norm(other)


def repo_slug(address: str) -> str | None:
    """owner/name from a github.com address, or None for anything else."""
    a = (address or "").strip().rstrip("/")
    if a.endswith(".git"):
        a = a[:-4]
    for prefix in ("https://github.com/", "git@github.com:", "ssh://git@github.com/"):
        if a.lower().startswith(prefix):
            rest = a[len(prefix):]
            if rest.count("/") == 1 and all(rest.split("/")):
                return rest
    return None


def gh_tool() -> str | None:
    """GitHub's tool: a test's stand-in, the PATH (with the usual folders), or
    (0.15.2) the copy the Hub's own join note unpacks under ~/Apps/github-cli/."""
    found = os.environ.get("MOBLEE_GH") or which("gh")
    if found:
        return found
    import glob
    kept = newest_first(glob.glob(str(Path.home() / "Apps" / "github-cli" / "*" / "bin" / "gh")))
    return kept[0] if kept else None


def hub_git(args: list, timeout: int = 60) -> tuple[int, str]:
    """git for the Hub, never stopping at a password question nobody can see:
    a sign-in that is not set up fails at once and says so."""
    os.environ["GIT_TERMINAL_PROMPT"] = "0"
    return run(["git"] + args, timeout=timeout)


def env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default


def hub_folder() -> Path | None:
    v = vault_path()
    return (v / "hub") if v else None


def hub_manifest(folder: Path) -> dict | None:
    try:
        data = json.loads((folder / "hub.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def hub_remote(folder: Path) -> str | None:
    if not (folder / ".git").exists():
        return None
    code, out = hub_git(["-C", str(folder), "config", "--get", "remote.origin.url"], timeout=30)
    return out.strip() if code == 0 and out.strip() else None


def hub_me(folder: Path) -> str | None:
    try:
        me = json.loads((folder / "app" / "state" / "me.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    mid = me.get("id") if isinstance(me, dict) else None
    return mid if isinstance(mid, str) and mid and set(mid) <= HUB_ID_CHARS else None


def check_hub():
    folder = hub_folder()
    if folder is None:
        return False, "no wiki was found to join it from"
    if not folder.exists():
        return False, "this wiki has not joined the Hub"
    remote = hub_remote(folder)
    if remote is None:
        return False, "a hub folder is there, but it is not linked to GitHub (it was copied, not joined)"
    manifest = hub_manifest(folder)
    if manifest is None:
        return False, "the hub folder has no hub.json, so it is not a Hub this version of Moblee knows"
    address = str(manifest.get("address", ""))
    old_address = ""
    if not same_address(remote, address):
        # (0.15.2) A copy cloned before the Hub moved still works (GitHub
        # forwards the old address), so it is in, at its old address, once
        # GitHub confirms the move; unseen only when GitHub cannot be reached
        # (a repository GitHub does not know, or no GitHub tool, stays off,
        # so the item that points the copy at the Hub is still offered).
        old, new = repo_slug(remote), repo_slug(address)
        gh = gh_tool()
        now = gh_full_name(gh, old) if (old and new and gh) else None
        if now is None and old and new and gh and not github_reachable():
            return None, ("the hub folder points at " + remote + ", not the address the Hub gives; Moblee could "
                          "not reach GitHub just now to ask whether that is the Hub's old address")
        if not now or now.lower() != new.lower():
            return False, ("the hub folder points somewhere other than the address the Hub itself gives; if GitHub "
                           "confirms the Hub has moved, choosing this item again points your copy at "
                           + (address or "it"))
        old_address = "; your copy still uses the Hub's old address, which GitHub forwards (choosing this item again updates it)"
    me = hub_me(folder)
    if me is None:
        return False, "linked, but this Mac does not know yet which member you are: open the hub once, or run this item again"
    code, _ = hub_git(["-C", str(folder), "cat-file", "-e", f"@{{u}}:members/{me}.json"], timeout=30)
    if code != 0:
        return False, f"joined as {me}, but your member file has not reached GitHub yet (run this item again)"
    gh = gh_tool()
    if gh and repo_slug(remote) and gh_signed_in(gh) is False:
        return False, f"joined as {me}, but GitHub's sign-in on this Mac has lapsed (run the GitHub item again)"
    version = manifest.get("version")
    page = f"; the Hub's page is version {version}" if isinstance(version, str) and version else ""
    return True, f"in {manifest.get('name') or 'the Hub'} as {me}{page}{old_address}"


def hub_reachable(address: str) -> bool:
    return hub_git(["ls-remote", "--heads", address], timeout=60)[0] == 0


def hub_login(gh: str) -> str | None:
    code, out = run([gh, "api", "user", "--jq", ".login"], timeout=60)
    if code != 0:
        return None
    # gh's own notices (a new release, say) can arrive beside the answer: the
    # login is the one word on a line of its own.
    for line in reversed(out.strip().splitlines()):
        line = line.strip()
        if line and " " not in line and set(line) <= HUB_SLUG_CHARS and "/" not in line:
            return line
    return None


def gh_full_name(gh: str | None, slug: str | None) -> str | None:
    """The name GitHub gives a repository today, asked by the name on record.
    GitHub answers a moved repository's old name with its new one, so this is
    GitHub's own word on a move. Only the line shaped like owner/name counts:
    anything gh prints besides (a notice, a warning) is not an answer."""
    if not gh or not slug:
        return None
    code, out = run([gh, "api", f"repos/{slug}", "--jq", ".full_name"], timeout=60)
    if code != 0:
        return None
    for line in reversed(out.strip().splitlines()):
        line = line.strip()
        if line.count("/") == 1 and all(line.split("/")) and set(line) <= HUB_SLUG_CHARS:
            return line
    return None


def hub_moved_owner(gh: str, slug: str, lobby: str | None) -> str | None:
    """Where the Hub's keeper keeps it now, when the Hub has moved with its
    lobby. The lobby is public, so GitHub tells anyone its new name; a private
    Hub's new name is told only to members. Counted as a move only when the
    lobby has really moved and the Hub and lobby on record had the same owner."""
    if not lobby or lobby.split("/")[0].lower() != slug.split("/")[0].lower():
        return None
    now = gh_full_name(gh, lobby)
    if not now or now.lower() == lobby.lower():
        return None
    return now.split("/")[0]


def hub_invitation(gh: str, slug: str, lobby: str | None = None) -> int | None:
    """The waiting invitation to this Hub, if there is one. GitHub names the
    repository in an invitation as it is called now, so a Hub that has moved
    with its lobby is matched by its own name under the lobby's new owner
    (0.13.1: until then a moved Hub's invitation was never seen, and the join
    waited for ever)."""
    code, out = run([gh, "api", "/user/repository_invitations"], timeout=60)
    if code != 0:
        return None
    body = out[out.find("["):out.rfind("]") + 1] if "[" in out else "[]"   # gh's notices kept out
    try:
        invitations = [(str((inv.get("repository") or {}).get("full_name", "")), int(inv["id"]))
                       for inv in json.loads(body or "[]")]
    except (ValueError, KeyError, TypeError, AttributeError):
        return None
    for repo, iid in invitations:
        if repo.lower() == slug.lower():
            return iid
    name = slug.split("/")[1].lower()
    if not any(repo.lower().endswith("/" + name) for repo, _ in invitations):
        return None
    owner = hub_moved_owner(gh, slug, lobby)
    if owner:
        for repo, iid in invitations:
            if repo.lower() == f"{owner}/{name}".lower():
                return iid
    return None


def hub_same_hub(one: str, other: str) -> bool:
    """Two addresses for one Hub: the same address, or, on GitHub, an old one
    that GitHub itself says now leads to the other. Matching branches are not
    enough (an up-to-date copy elsewhere has the same ones), and an address
    outside GitHub is never taken for a move."""
    if same_address(one, other):
        return True
    old, new = repo_slug(one), repo_slug(other)
    if not old or not new:
        return False
    now = gh_full_name(gh_tool(), old)
    return bool(now) and now.lower() == new.lower()


def hub_follow_move(folder: Path) -> bool:
    """When the Hub's own hub.json gives a new address and GitHub says the old
    one the folder points at has moved there, point the folder at the new one.
    True when the folder now points where its hub.json says."""
    manifest = hub_manifest(folder) or {}
    new = str(manifest.get("address") or "")
    remote = hub_remote(folder) or ""
    if not new or same_address(remote, new):
        return bool(new)
    if not hub_same_hub(remote, new):
        return False
    if hub_git(["-C", str(folder), "remote", "set-url", "origin", new], timeout=30)[0] != 0:
        return False
    say("  The Hub has moved, so your copy now points at its new address:")
    say("  " + new)
    return True


def hub_knock(gh: str, hub: dict, login: str) -> bool:
    """Open the one issue in the lobby that asks the door to invite this account.

    The lobby is public, so the knock carries the GitHub name and nothing else:
    never the owner's own name, which is the first of the words they are about
    to be asked to keep off the Hub (cold read, 24 October 2026). An open issue
    already asking for the same account is not opened twice, and when the
    lobby's list cannot be read no new knock is made."""
    lobby = repo_slug(hub.get("lobby", ""))
    if not lobby:
        return False
    title = f"join: {login}"
    code, out = run([gh, "issue", "list", "-R", lobby, "--state", "open", "--limit", "200",
                     "--json", "title"], timeout=60)
    if code != 0:
        say("  The Hub's door could not be read just now (no internet?). Nothing was sent; choose")
        say("  this item again in a while.")
        return False
    try:
        mine = [i for i in json.loads(out or "[]")
                if str(i.get("title", "")).strip().lower() in (title.lower(),)
                or str(i.get("title", "")).lower().startswith(f"join: {login.lower()},")]
    except (ValueError, AttributeError):
        mine = []
    if mine:
        say("  The knock is already at the door from before; it is not sent twice.")
        return True
    say(f"  Knocking at the Hub's door. The door is a public page, so the knock carries only")
    say(f"  your GitHub name, {login}, and nothing else of yours.")
    body = ("Opened by Moblee on behalf of this account, to join the Hub. "
            "The keeper adds the label `approved` and the door sends the invitation.")
    code, out = run([gh, "issue", "create", "-R", lobby, "--title", title, "--body", body], timeout=60)
    if code != 0:
        say("  The knock could not be left at the door: " + (out.strip().splitlines() or ["no answer"])[-1])
        return False
    return True


def hub_wait_for_invitation(gh: str, slug: str, address: str, lobby: str | None = None) -> bool:
    """Wait for the keeper, accepting the invitation the moment it arrives. True
    once this account can read the Hub."""
    poll = max(1, env_int("MOBLEE_HUB_POLL", 15))
    limit = max(poll, env_int("MOBLEE_HUB_WAIT", 1800))
    waited = 0
    told = False
    while waited <= limit:
        inv = hub_invitation(gh, slug, lobby)
        if inv is not None:
            code, out = run([gh, "api", "-X", "PATCH", f"/user/repository_invitations/{inv}"], timeout=60)
            if code != 0:
                say("  The invitation came, but accepting it failed: " + (out.strip().splitlines() or ["no answer"])[-1])
                return False
            say("  The invitation came and has been accepted.")
            for _ in range(6):   # GitHub can take a moment to let a new member in
                if hub_reachable(address):
                    return True
                time.sleep(poll)
            say("  Accepted, but GitHub has not opened the Hub to you yet. Choose this item again")
            say("  in a minute; it carries on from here.")
            return False
        if hub_reachable(address):
            return True
        if not told:
            say("  Waiting for the Hub's keeper to let you in. You can leave this window open;")
            say("  it carries on by itself the moment they do. If you close it, choosing this")
            say("  item again picks up where it stopped.")
            told = True
        time.sleep(poll)
        waited += poll
    say("  The keeper has not let you in yet. Nothing is lost: choose this item again later.")
    return False


def hub_ignore(v: Path) -> None:
    """The wiki's git and Obsidian both leave the Hub alone."""
    gi = v / ".gitignore"
    try:
        text = gi.read_text(encoding="utf-8")
    except OSError:
        text = ""
    if not any(line.strip() in ("hub/", "/hub/", "hub", "/hub") for line in text.splitlines()):
        # "/hub" and not "hub/": a folder-only pattern lets git track a link called hub.
        if gi.exists():
            backup(gi)
        add = ("" if not text or text.endswith("\n") else "\n") + \
              "# The Moblee Hub keeps its own history (GitHub), so the wiki does not track it\n/hub\n"
        gi.write_text(text + add, encoding="utf-8")
    app = v / ".obsidian" / "app.json"
    try:
        data = json.loads(app.read_text(encoding="utf-8")) if app.exists() else {}
    except ValueError:
        say("  Obsidian's settings file could not be read, so it was left alone; the Hub's")
        say("  notes may show in Obsidian until it is put right.")
        return
    if not isinstance(data, dict):
        return
    filters = data.get("userIgnoreFilters")
    if not isinstance(filters, list):
        filters = []
    if "hub/" not in filters:
        if app.exists():
            backup(app)
        data["userIgnoreFilters"] = filters + ["hub/"]
        app.parent.mkdir(parents=True, exist_ok=True)
        app.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def hub_owner_name(v: Path) -> str | None:
    try:
        text = (v / "CLAUDE.md").read_text(encoding="utf-8")
    except OSError:
        try:
            text = (v / "AGENTS.md").read_text(encoding="utf-8")
        except OSError:
            return None
    import re
    m = re.search(r"knowledge base for ([^\n]{1,80}?) where (?:Claude|the assistant) is the maintainer", text)
    name = m.group(1).strip() if m else None
    return None if not name or name == "[Your Name]" else name


def hub_suggest_id(name: str) -> str:
    """The first word of the name, in small letters and digits only."""
    first = name.split()[0].lower() if name.split() else ""
    word = "".join(c for c in first if c in HUB_ID_CHARS and c != "-")
    return word[:24] or "me"


def hub_join(folder: Path, v: Path, name_hint: str | None) -> str | None:
    """The member file, the Mac's own record of who it is, and the private words.
    Returns the member id, or None when the owner stopped."""
    me = hub_me(folder)
    if me and (folder / "members" / f"{me}.json").exists():
        return me
    rule("The Hub: your name in the group")
    # The first word only, by default: the surname is the first of the words
    # the owner is about to be asked to keep off the Hub.
    default = (name_hint or "").split()[0] if (name_hint or "").split() else ""
    say("  The other members see this name beside everything you share.")
    name = ask(f"  What does the group call you?{' [' + default + ']' if default else ''} ")
    if name is None:
        return None
    name = name.strip() or default
    if not name:
        say("  A name is needed to join. Choose this item again when you have one.")
        return None
    taken = {p.stem for p in (folder / "members").glob("*.json")}
    mid = hub_suggest_id(name)
    # Joined before, on another Mac or before the folder was copied again: the
    # member file is already there, and is this owner's, not someone else's.
    if mid in taken:
        try:
            there = json.loads((folder / "members" / f"{mid}.json").read_text(encoding="utf-8")).get("name")
        except (OSError, ValueError, AttributeError):
            there = None
        if isinstance(there, str) and there.strip().lower() == name.strip().lower() \
                and yes(f"  The Hub already has a member called {there}, '{mid}'. Is that you?"):
            state = folder / "app" / "state"
            state.mkdir(parents=True, exist_ok=True)
            (state / "me.json").write_text(json.dumps({"id": mid}) + "\n", encoding="utf-8")
            return mid
    while True:
        if mid in taken:
            say(f"  The short name '{mid}' is already someone else's.")
            mid = ""
        typed = ask(f"  A short name for you, used in the Hub's file names (small letters, digits, hyphens){' [' + mid + ']' if mid else ''} ")
        if typed is None:
            return None
        typed = typed.strip().lower() or mid
        if typed and set(typed) <= HUB_ID_CHARS and typed not in taken and len(typed) <= 24:
            mid = typed
            break
        say("  That will not do: small letters, digits and hyphens only, and not one already taken.")
        mid = ""
    (folder / "members").mkdir(exist_ok=True)
    member = {"id": mid, "name": name, "joined": datetime.date.today().isoformat(), "taken": []}
    (folder / "members" / f"{mid}.json").write_text(json.dumps(member, indent=2) + "\n", encoding="utf-8")
    state = folder / "app" / "state"
    state.mkdir(parents=True, exist_ok=True)
    (state / "me.json").write_text(json.dumps({"id": mid}) + "\n", encoding="utf-8")
    words_file = folder / "tools" / "private-words.txt"
    if not words_file.exists():
        say("")
        say("  Last, the words that must never leave this Mac in anything you share: your")
        say("  surname, your family's names, the names of a coach, doctor or friend in your")
        say("  wiki. Type them on one line with commas between them, or press Return to")
        say("  add them later. They stay on this Mac; the Hub's checker sweeps for them.")
        typed = ask("  Words: ") or ""
        words = [w.strip() for w in typed.split(",") if w.strip()]
        words += [w for w in name.split() if len(w) > 2 and w not in words]
        words_file.parent.mkdir(parents=True, exist_ok=True)
        words_file.write_text("".join(w + "\n" for w in words), encoding="utf-8")
    return mid


def install_hub():
    v = vault_path()
    if v is None:
        say("  No wiki was found on this Mac to join the Hub from.")
        return False
    hub = hub_settings()
    folder = v / "hub"
    if folder.exists() and hub_remote(folder) is None:
        say("  There is a folder called hub in your wiki that is not linked to GitHub. It is")
        say("  left exactly as it is. Ask your assistant to look at it before trying again.")
        return False
    slug = repo_slug(hub["address"])
    gh = gh_tool()
    if slug:
        ok, _ = check_github()
        if not ok and not os.environ.get("MOBLEE_GH"):
            say("  The Hub lives on GitHub, so GitHub comes first.")
            if not install_github():
                return False
            gh = gh_tool()
        if not gh:
            say("  GitHub's tool is not on this Mac, so the Hub cannot be joined yet.")
            return False
        if run([gh, "auth", "setup-git"], timeout=60)[0] != 0:
            say("  GitHub's sign-in could not be set up for git on this Mac. Choose the GitHub")
            say("  item again, then this one.")
            return False
    rule("The Hub")
    if not folder.exists():
        if not hub_reachable(hub["address"]):
            if not slug:
                say("  The Hub's address does not answer: " + hub["address"])
                return False
            login = hub_login(gh)
            if not login:
                say("  Your GitHub name could not be read. Run the GitHub item again, then this one.")
                return False
            if hub_invitation(gh, slug, repo_slug(hub.get("lobby", ""))) is None:
                if hub["join"] == "invite":
                    say(f"  This Hub's keeper lets members in by hand. Send them your GitHub name,")
                    say(f"  {login}, and this window waits for the invitation.")
                else:
                    if not hub_knock(gh, hub, login):
                        return False
                    if hub["join"] == "approve":
                        say("  Your request is at the door. The Hub's keeper approves it with one press.")
            if not hub_wait_for_invitation(gh, slug, hub["address"], repo_slug(hub.get("lobby", ""))):
                return False
        code, out = run(["git", "clone", hub["address"], str(folder)], timeout=600)
        if code != 0:
            say("  The Hub could not be copied to this Mac: " + (out.strip().splitlines() or ["no answer"])[-1])
            return False
        # Copied from an old address GitHub forwards: point it at the Hub's own,
        # and join nothing whose own address GitHub does not confirm.
        claimed = str((hub_manifest(folder) or {}).get("address") or "")
        if claimed and not same_address(hub_remote(folder) or "", claimed) and not hub_follow_move(folder):
            say("  The Hub gives an address that GitHub could not confirm as its home just now,")
            say("  so nothing was sent. Choose this item again in a while; if it still cannot,")
            say("  the check-up names it (F62).")
            return False
    else:
        manifest = hub_manifest(folder) or {}
        claimed = str(manifest.get("address") or "")
        if claimed and not same_address(hub_remote(folder) or "", claimed) and not hub_follow_move(folder):
            say("  Your hub folder points somewhere other than the Hub it says it is. It is left")
            say("  as it is; the check-up names it (field guide F62).")
            return False
        code, out = run(["git", "-C", str(folder), "pull", "--rebase", "--autostash"], timeout=300)
        if code != 0:
            say("  The Hub could not be brought up to date just now (no internet?). Carrying on.")
        # The pull may bring a hub.json that names a new address (the Hub moved
        # since this copy was made): follow it now rather than at the next run,
        # and stop, as before the pull, when GitHub does not confirm the move.
        claimed = str((hub_manifest(folder) or {}).get("address") or "")
        if claimed and not same_address(hub_remote(folder) or "", claimed) and not hub_follow_move(folder):
            say("  The Hub now gives a new address, and GitHub could not confirm it as the")
            say("  Hub's new home just now, so your hub folder is left as it is. Choose this")
            say("  item again in a while; if it still cannot, the check-up names it (F62).")
            return False
    manifest = hub_manifest(folder)
    if manifest is None:
        say("  The Hub arrived without its hub.json, so this version of Moblee cannot use it.")
        return False
    hub_ignore(v)
    mid = hub_join(folder, v, hub_owner_name(v))
    if mid is None:
        return False
    member = f"members/{mid}.json"
    if run(["git", "-C", str(folder), "config", "user.name"], timeout=30)[1].strip() == "":
        # A fresh Mac may have no git identity, and a commit without one fails or
        # prints git's long notice. The Hub's own folder gets one; nothing global.
        login = hub_login(gh) if (gh and slug) else None
        member_name = json.loads((folder / member).read_text(encoding="utf-8")).get("name") or mid
        run(["git", "-C", str(folder), "config", "user.name", member_name], timeout=30)
        run(["git", "-C", str(folder), "config", "user.email",
             f"{login}@users.noreply.github.com" if login else f"{mid}@members.moblee.invalid"], timeout=30)
    code, _ = hub_git(["-C", str(folder), "cat-file", "-e", f"@{{u}}:{member}"], timeout=30)
    if code != 0:
        if hub_git(["-C", str(folder), "rev-parse", "--abbrev-ref", "@{u}"], timeout=30)[0] != 0:
            say("  The hub folder has no branch on GitHub to send to, so nothing was sent. Ask")
            say("  your assistant to look at it (field guide F62).")
            return False
        code, out = hub_git(["-C", str(folder), "rev-list", "--count", "@{u}..HEAD"], timeout=30)
        if code != 0 or out.strip() != "0":
            # Other saves of the owner's are waiting to go. They are the
            # assistant's to send with the owner's yes, not this item's.
            say("  Other saves of yours in the Hub are waiting to be sent, so this item sends")
            say("  nothing. Say 'check the hub' to your assistant, then choose this item again.")
            return False
        hub_git(["-C", str(folder), "add", "--", member], timeout=30)
        hub_git(["-C", str(folder), "commit", "-q", "-m", f"hub: {mid} joined", "--", member], timeout=60)
        code, out = hub_git(["-C", str(folder), "push", "-q"], timeout=300)
        if code != 0:
            hub_git(["-C", str(folder), "pull", "-q", "--rebase", "--autostash"], timeout=300)
            code, out = hub_git(["-C", str(folder), "push", "-q"], timeout=300)
        if code != 0:
            say("  You are in, but your member file could not be sent to GitHub just now. Choose")
            say("  this item again in a while; nothing is lost.")
            return False
    patcher = PACKAGE_ROOT / "scripts" / "patch-claude-md.py"
    run([sys.executable, str(patcher), "--blocks-only", "--vault", str(v)], timeout=120)
    say(f"  You are in the Hub as {mid}. Say 'open the hub' or 'check the hub' to your assistant.")
    return True


# --- the list, in the order it is shown ---------------------------------------

def build_items() -> list:
    news_check, news_install = skill_item("news-brief", "say 'news brief'; every item is checked against a second source")
    trips_check, trips_install = skill_item("trips", "say 'start a trip to ...'")
    connect, make, paid, habits = ("Connect your life", "Read and make things", "Paid, or with a paid option", "Looking after the wiki")
    return [
        Item("mac-apps", connect, "Your Mac's Calendar, Reminders, Mail and Notes",
             "Claude reads your Mac's own apps when you ask, so you never upload a calendar file again.",
             8, 60, "free", needs=("devtools", "homebrew", "node"), signin="click Allow on your Mac's pop-ups",
             install=install_mac_apps, check=check_mac_apps),
        Item("google", connect, "Gmail, Google Calendar and Google Drive",
             "Claude reads your Google mail, calendar and files when you ask. It drafts; you send.",
             3, 0, "free", signin="sign in to Google in your browser",
             install=install_google, check=check_google),
        Item("github", connect, "GitHub",
             "Claude can read and work with your GitHub projects.",
             4, 40, "free (needs a free GitHub account)", needs=("homebrew",), signin="sign in to GitHub in your browser",
             install=install_github, check=check_github),
        Item("hub", connect, "The Moblee Hub",
             "The group's shared wiki of wikis: take what another member's wiki has (a tracker, a way of working) and share yours. Private, on GitHub; the Hub's keeper lets you in with one tap.",
             4, 20, "free (needs the GitHub item, which this brings with it)", needs=("homebrew",),
             signin="sign in to GitHub if you have not, then wait for the keeper's yes",
             install=install_hub, check=check_hub),
        Item("chrome", connect, "Chrome, with your X, Instagram and YouTube",
             "Claude uses Chrome to read pages behind your own logins. It never posts without your yes.",
             5, 0, "free (installs Chrome if you do not have it)", needs=("homebrew",),
             signin="add two Chrome extensions and sign in",
             install=install_chrome, check=check_chrome),
        Item("videos", make, "Watch and summarise videos",
             "Send a YouTube, Instagram, TikTok or X link and Claude watches it for you.",
             4, 200, "free", needs=("homebrew",), install=install_videos, check=check_videos),
        Item("documents", make, "PDF, Word, PowerPoint and Excel",
             "Turn wiki pages into polished PDFs, and make or read Office documents.",
             10, 300, "free", needs=("homebrew",), install=install_documents, check=check_documents),
        Item("film", make, "Video editing",
             "Cut clips together, add titles, captions and music, from a plain description.",
             12, 1500, "free for individuals (Remotion's licence; larger companies need one)",
             needs=("devtools", "homebrew", "node"), install=install_film, check=check_film),
        Item("audio", make, "Audio editing and read-aloud",
             "Trim, join, clean up and convert audio, and turn any page into a spoken recording.",
             4, 150, "free", needs=("homebrew",), install=install_audio, check=check_audio),
        Item("pictures", make, "Picture editing",
             "Crop, resize, convert, compress and caption photos and images.",
             5, 120, "free", needs=("homebrew",), install=install_pictures, check=check_pictures),
        Item("news-brief", make, "A daily news brief, every item checked twice",
             "News on what you follow, each item confirmed by a second source and linked.",
             1, 1, "free", install=news_install, check=news_check),
        Item("trips", make, "Trip planning",
             "A page per trip with flights, stays and day plans, built from your booking emails.",
             1, 1, "free", install=trips_install, check=trips_check),
        Item("x-capture", make, "Save X posts into the wiki",
             "Paste an x.com link and Claude keeps the post, properly sourced. Needs the Chrome item.",
             1, 1, "free (needs the Chrome item)", install=lambda: install_skill("x-capture"), check=check_x_capture),
        Item("skill-maker", make, "Teach Claude your own routines",
             "Describe something you do often and Claude turns it into a one-word command.",
             2, 5, "free", install=install_skill_maker, check=check_skill_maker),
        Item("obsidian-extras", make, "Obsidian extras",
             "Claude can build Obsidian canvases, databases and diagrams.",
             2, 5, "free", install=install_obsidian_extras, check=check_obsidian_extras),
        Item("generation", paid, "Create new images, video, voices and music (ElevenLabs)",
             "Generate things that do not exist yet. Needs your own ElevenLabs account; see the prices first.",
             5, 0, "PAID: free tier with small limits; plans from about $6 a month (Sept 2026)",
             signin="make an ElevenLabs account and connect it", install=install_generation, check=check_generation),
        Item("voice", paid, "Claude reads its replies aloud",
             "Spoken replies and a nudge when Claude is waiting on you. Mac voice free; ElevenLabs voice optional and paid.",
             3, 5, "free (paid voice optional)", install=install_voice, check=check_voice),
        Item("alerts", connect, "Alerts on your phone",
             "A line on your phone when a job of yours finishes or fails, through the free ntfy app. It names the file to look at and never sends it.",
             3, 0, "free (the ntfy app on your phone)", signin="get the ntfy app on your phone and type one code",
             install=install_alerts, check=check_alerts),
        Item("reach", connect, "Reach your things from your phone",
             "Open a thing built for you from your phone, over a private network of your own: Tailscale (recommended), or one you already have. Works while this Mac is awake.",
             6, 100, "free (Tailscale's personal plan, or your own network)", needs=("homebrew",),
             signin="sign in to Tailscale on this Mac and on your phone, or give this Mac's address",
             install=install_reach, check=check_reach),
        Item("thinking", habits, "Jobs that ask Claude while you are away",
             "A scheduled job can ask Claude to think (a morning page, a weekly tidy). Needs a long-lived sign-in Claude makes for you; each run uses a little of your allowance.",
             4, 0, "free (uses your Claude allowance)", signin="sign in once in the browser and paste a code",
             install=install_thinking, check=check_thinking),
        Item("weekly", habits, "Weekly health check",
             "The wiki checks itself every Saturday morning, makes a copy of its whole history outside the wiki, and tells you what needs attention.",
             1, 0, "free", install=install_weekly, check=check_weekly),
        Item("tidy", habits, "The weekly tidy",
             "After the Saturday check, Claude puts right what can safely be put right and lists the rest for you on one short page. Needs the item for jobs that ask Claude.",
             1, 0, "free (one run a week of your Claude allowance)", install=install_tidy, check=check_tidy),
        Item("morning", habits, "Your morning page",
             "Each morning, or at the first wake after it, Claude writes you a page: what is on today, what moved, what is waiting, one thing worth doing. Needs the item for jobs that ask Claude.",
             1, 0, "free (one run a day of your Claude allowance)", install=install_morning, check=check_morning),
        Item("recall", habits, "Memory search",
             "Your assistant finds pages by their words; this adds finding them by meaning. A question puts the closest sections in front of Claude first. A small model runs on this Mac; nothing leaves it.",
             6, 400, "free (a 300 MB model on this Mac)", needs=("homebrew",), install=install_recall, check=check_recall),
        Item("lessons", habits, "The learning path",
             "Thirty-two short lessons, one an evening, with a 9 pm reminder.",
             1, 1, "free", install=install_lessons, check=check_lessons),
        Item("vault-fn", habits, "The 'vault' shortcut in Terminal",
             "Type vault in Terminal to open Claude in your wiki.",
             1, 0, "free", install=install_vault_fn, check=check_vault_fn),
    ]


FOUNDATION_COST = {"devtools": (15, 1500), "homebrew": (8, 500), "node": (3, 200)}


def foundations_needed(chosen: list) -> list:
    needed = []
    for key in ("devtools", "homebrew", "node"):
        if any(key in it.needs for it in chosen):
            if key == "devtools" and devtools_ok():
                continue
            if key == "homebrew" and homebrew_ok():
                continue
            if key == "node" and which("node"):
                continue
            needed.append(key)
    if "node" in needed and "homebrew" not in needed and not homebrew_ok():
        needed.insert(0, "homebrew")
    return needed


# ----------------------------------------------------------------------------
# the checklist
# ----------------------------------------------------------------------------

def show_checklist(items: list, ticked: dict, status: dict, from_claude: bool = False) -> None:
    say("")
    if from_claude:
        say("The items you agreed with Claude are ticked. Change anything you like.")
    else:
        say("Nothing is ticked yet. Not sure what you need? Open your assistant in your")
        say("wiki and say 'get me started': it asks how you work and suggests what fits.")
    say("Items already working are marked 'working' and are left alone. Type the")
    say("numbers to tick or untick (for example: 3 7 12), 'all' for everything,")
    say("'free' for everything free, 'none' to clear, and press Return on its own")
    say("when the list is right.")
    group = None
    for n, it in enumerate(items, 1):
        if it.group != group:
            group = it.group
            say("")
            say(f"  {group.upper()}")
        mark = "working" if status.get(it.key) else ("[x]" if ticked[it.key] else "[ ]")
        say(f"  {n:>2}. {mark:<7} {it.title}")
        say(f"               {it.what}")
        size = f"{it.space_mb / 1000:.1f} GB" if it.space_mb >= 1000 else f"{it.space_mb} MB"
        extra = f"; you will: {it.signin}" if it.signin else ""
        say(f"               about {it.minutes} min, {size}, {it.cost}{extra}")


def choose(items: list, status: dict, preset: set | None, tick: set | None = None) -> list:
    if preset is not None:
        return [it for it in items if it.key in preset and not status.get(it.key)]
    tick = tick or set()
    ticked = {it.key: it.key in tick and not status.get(it.key) for it in items}
    while True:
        show_checklist(items, ticked, status, from_claude=bool(tick))
        ans = ask("\nYour choice (Return to accept): ")
        if ans is None:
            say("No answer received, so nothing extra will be installed.")
            return []
        ans = ans.strip().lower()
        if not ans:
            break
        if ans == "all":
            ticked = {k: True for k in ticked}
            continue
        if ans == "free":
            ticked = {it.key: not it.cost.startswith("PAID") for it in items}
            continue
        if ans == "none":
            ticked = {k: False for k in ticked}
            continue
        for tok in ans.replace(",", " ").split():
            if tok.isdigit() and 1 <= int(tok) <= len(items):
                k = items[int(tok) - 1].key
                ticked[k] = not ticked[k]
            else:
                say(f"  '{tok}' is not a number on the list; ignored.")
    return [it for it in items if ticked[it.key] and not status.get(it.key)]


# How the Moblee app can add each item. "silent": the app runs it and shows
# progress, since it asks nothing and needs no password. "terminal": it needs
# the owner at a Terminal window (Homebrew's password, a sign-in, or the
# `claude` command), so the app opens one with the command ready. "clicks":
# it is done by clicks inside Claude's own app, which the app shows as
# pictures. "hidden": only useful to someone who works in Terminal.
HOW = {
    "news-brief": "silent", "trips": "silent", "x-capture": "silent",
    "weekly": "silent", "lessons": "silent", "voice": "silent", "tidy": "silent", "morning": "silent",
    "google": "clicks", "generation": "clicks",
    "vault-fn": "hidden",
}


def how(key: str) -> str:
    return HOW.get(key, "terminal")


# For a "clicks" item, the three cards the Moblee app shows before it sends the
# owner into Claude: where to go, what to press, and how to tell it worked. An
# owner sent to another app with no picture of what to look for cannot tell
# whether they arrived (the install test of 20 September 2026). Each line is
# short enough for a card: a title of two or three words, a detail under
# seventy characters.
CLICKS = {
    "google": [
        ["Connectors", "The page opens. If it says moved: Customise, then Connectors"],
        ["Switch on three", "Gmail, Google Calendar, Google Drive. Connect, then sign in"],
        ["Check it worked", "Ask Claude: what is on my calendar today?"],
    ],
    "generation": [
        ["Connectors", "The page opens. If it says moved: Customise, then Connectors"],
        ["ElevenLabs", "Press Connect and sign in. Paying is your choice, on their site"],
        ["Check it worked", "Ask Claude: can you see ElevenLabs?"],
    ],
}


PROGRESS = False


def emit(step: str, state: str, **extra) -> None:
    """One machine-readable line per event, for the Moblee app (--progress)."""
    if PROGRESS:
        print("@@moblee " + json.dumps(dict({"step": step, "state": state}, **extra)), flush=True)


def summarise(chosen: list, foundations: list, assume_yes: bool = False) -> bool:
    minutes = sum(it.minutes for it in chosen) + sum(FOUNDATION_COST[f][0] for f in foundations)
    space = sum(it.space_mb for it in chosen) + sum(FOUNDATION_COST[f][1] for f in foundations)
    rule("Before anything is installed")
    names = {"devtools": "Apple's developer tools", "homebrew": "Homebrew", "node": "Node"}
    if foundations:
        say("First, what the items stand on: " + ", ".join(names[f] for f in foundations) + ".")
    say("Then, in this order:" if foundations else "In this order:")
    for it in chosen:
        say(f"  - {it.title}")
    say("")
    room = (f"{space / 1000:.1f} GB of space" if space >= 1000
            else (f"{space} MB of space" if space else "almost no space"))
    say(f"Expect about {minutes} minute{'' if minutes == 1 else 's'} and {room},")
    say("most of it waiting for downloads. Keep the Mac plugged in and awake.")
    signins = [it for it in chosen if it.signin]
    if signins or "homebrew" in foundations:
        say("")
        say("You will be needed at the keyboard for:")
        if "homebrew" in foundations:
            say("  - your Mac password, once, for Homebrew")
        for it in signins:
            say(f"  - {it.title}: {it.signin}")
        say("Each of these is explained in plain steps when it comes up.")
    paid = [it for it in chosen if it.cost.startswith("PAID")]
    if paid:
        say("")
        say("You ticked something that can cost money: " + ", ".join(it.title for it in paid) + ".")
        say("Nothing is bought by this installer; you decide on that company's own site.")
    say("")
    if assume_yes:
        return True  # the owner already pressed the item's button in the Moblee app
    return yes("Start now?", default=True)


def write_report(results: list, vault: Path | None) -> Path:
    lines = [f"# Moblee setup check, {datetime.datetime.now().strftime('%-d %B %Y, %H:%M')}", ""]
    for it, ok, detail in results:
        word = "Cannot be seen from here (not a fault)" if ok is None else ("Working" if ok else "Not working")
        lines.append(f"- {word}: **{it.title}**. {detail}.")
    lines += ["", "Run `python3 scripts/moblee-setup.py` from the Moblee folder to add or repair anything above.", ""]
    target_dir = (vault / "outputs" / "setup") if vault else CONFIG_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f"setup-check-{STAMP}.md"
    path.write_text("\n".join(lines))
    return path


def final_check(items: list, only: set | None = None) -> list:
    rule("Checking that everything works")
    if only is not None:
        forget_connector_cache()  # after installs, ask afresh; a plain check asks once
    results = []
    for it in items:
        if only is not None and it.key not in only:
            continue
        ok, detail = it.check()
        results.append((it, ok, detail))
        word = "CANNOT SEE " if ok is None else ("WORKING    " if ok else "NOT WORKING")
        say(f"  {word}  {it.title}: {detail}")
    return results


def save_state(status: dict, results: list, checked=None, **extra) -> None:
    """The saved record of the last look at each item. `status` holds every
    item, true or false; `unseen` names the ones this script could not see
    either way (a connection made inside the Claude app), so that nothing
    reading the record takes "could not see" for "not working"; `working` is
    the whole list of what works, not only what the last run touched.
    `status` may hold None for an item that could not be seen; `checked` names
    the items really looked at this time (the rest of `status` was carried
    forward from the last record, and says nothing new). A record that is
    damaged, or is not the shape expected, is started afresh, never a crash."""
    try:
        state = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}
    except (OSError, ValueError):
        state = {}
    if not isinstance(state, dict):
        state = {}
    for old in ("chosen",):  # held only the last run's items, under a name that read as the full list
        state.pop(old, None)
    looked_at = {it.key for it, _, _ in results} | set(status if checked is None else checked)
    blind = {it.key for it, ok, _ in results if ok is None} | {k for k in looked_at if status.get(k, False) is None}
    before = state.get("unseen")
    before = {k for k in before if isinstance(k, str)} if isinstance(before, list) else set()
    state["unseen"] = sorted((before - looked_at) | blind)
    state["status"] = {k: bool(v) for k, v in status.items()}
    state["working"] = sorted(k for k, v in state["status"].items() if v)
    state.update(extra)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2) + "\n")


# (0.14.0) What comes with every Moblee wiki, for the app's "Add more" screen:
# the parts the installer always puts in, as the owner knows them. Each says what
# it is for and, where there is one, what to say to the assistant to use it.
# `open` names a part the app can open itself. These are not on the checklist:
# a part that is missing is put back by the app's Repair, which runs the updater.
CORE_PARTS = [
    {"key": "guard", "title": "The safety guard",
     "what": "Stops your assistant deleting or overwriting your files.", "say": "", "open": ""},
    {"key": "save", "title": "Saving after every reply",
     "what": "The wiki saves its own history after each answer, so any change can be undone.", "say": "", "open": ""},
    # (0.16.0) Claude only: the installer enters it for Claude alone, so for an
    # owner on ChatGPT alone it is not listed.
    {"key": "tour", "title": "The first-week tour",
     "what": "For your first five days of use, Claude offers one thing your wiki can do each day.", "say": "", "open": ""},
    {"key": "companion", "title": "The companion",
     "what": "Sets things up with you and suggests what suits the way you work.", "say": "review my setup", "open": ""},
    {"key": "brain", "title": "Big questions to your wiki",
     "what": "Traces an idea through your pages, connects two subjects and tests a view against what you wrote.",
     "say": "trace this idea across my wiki", "open": ""},
    {"key": "wiki-capture", "title": "Saving a conversation",
     "what": "Keeps a good answer or a passing thought in your wiki.", "say": "save this to the wiki", "open": ""},
    {"key": "wiki-interview", "title": "Interviews",
     "what": "Your assistant asks you questions and writes the page from your answers.", "say": "interview me about…", "open": ""},
    {"key": "wiki-to-pdf", "title": "Pages as PDFs",
     "what": "Turns a page of your wiki into a well-made PDF. It needs the \u201cPDF, Word, PowerPoint and Excel\u201d extra below.",
     "say": "make a PDF of…", "open": ""},
    {"key": "design-your-brand", "title": "Your own look",
     "what": "Your colours, letters and monogram, used on your PDFs.", "say": "design my brand", "open": ""},
    {"key": "galaxy", "title": "The wiki galaxy",
     "what": "Every page a star and every link a line between them, in 3D in your browser.", "say": "galaxy", "open": "galaxy"},
    {"key": "dashboard", "title": "The dashboard",
     "what": "Your wiki at a glance in your browser, with charts and questions asked aloud.", "say": "", "open": "dashboard"},
    {"key": "compact", "title": "Keeping the wiki light",
     "what": "Trims the files your assistant reads at the start of every conversation.", "say": "compact the wiki", "open": ""},
    {"key": "build", "title": "Building things for you",
     "what": "Plans and builds small apps beside your wiki, from a wish in plain words.", "say": "build me…", "open": ""},
]


def _file_sha(path: Path) -> str | None:
    import hashlib
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _hook_commands(path: Path, event: str) -> list | None:
    """The commands a settings or hooks file enters for one hook event, or None
    when the file is there and cannot be read. Read as the check-up reads it:
    the hook entries themselves, never the file as text, since a script's name
    also appears in the permission rules beside them (cold read, 26 October
    2026: the save looked switched on wherever those rules were)."""
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    hooks = data.get("hooks") if isinstance(data, dict) else None
    entries = hooks.get(event) if isinstance(hooks, dict) else None
    out = []
    for entry in entries if isinstance(entries, list) else []:
        for h in (entry.get("hooks") or []) if isinstance(entry, dict) else []:
            if isinstance(h, dict):
                out.append(str(h.get("command", "")))
    return out


def _names_file(command: str, wanted: Path) -> bool:
    """Whether a hook's command runs this very file: the whole path, read back
    the way a shell reads it, so a hook left pointing at a moved or renamed
    wiki, or at a second wiki on the Mac, does not count. (0.15.2) $HOME is
    read as the shell reads it too: the installer enters the guard as
    python3 "$HOME/.claude/hooks/bash-guard.py", which only ~ was read for
    before, so every installed guard showed as Missing on Add more."""
    import shlex
    try:
        words = shlex.split(command)
    except ValueError:
        words = [command]
    for w in words:
        try:
            if os.path.realpath(Path(os.path.expandvars(w)).expanduser()) == os.path.realpath(wanted):
                return True
        except (OSError, ValueError):
            continue
    return False


def parts_report() -> dict:
    """(0.14.0) Read only, and quick: nothing is run, fetched or written. What
    comes with every wiki and whether it is in place, and what the checklist
    last saw of each extra. The app's "Add more" screen draws this."""
    who = assistant_choice()
    v = vault_path()
    claude, chatgpt = who in ("claude", "both"), who in ("chatgpt", "both")
    skill_dirs = ([HOME / ".claude" / "skills"] if claude else []) + ([HOME / ".agents" / "skills"] if chatgpt else [])

    # A wiki on a different version from this Moblee is expected to hold
    # different copies of the skills: present is all that can be said then.
    try:
        same_version = v is not None and (v / "VERSION").read_text().strip() == (PACKAGE_ROOT / "VERSION").read_text().strip()
    except OSError:
        same_version = False

    def skill(name: str) -> str:
        mine = PACKAGE_ROOT / "skills" / name / "SKILL.md"
        states = []
        for d in skill_dirs:
            have = d / name / "SKILL.md"
            if not have.is_file():
                states.append("missing")
            elif same_version and _file_sha(have) != _file_sha(mine):
                states.append("differs")
            else:
                states.append("in")
        for word in ("missing", "differs"):
            if word in states:
                return word
        return "in" if states else "missing"

    def combine(states: list) -> str:
        """Every assistant the owner uses must have it. ChatGPT runs a hook only
        once the owner has trusted it, which cannot be seen from here, so a hook
        entered for ChatGPT is 'unseen', never 'in' (the check-up says the same).
        (0.16.0) A settings file that is there and cannot be read is
        'unreadable': what it says cannot be told, so it is never 'missing'."""
        for word in ("missing", "unreadable", "unseen"):
            if word in states:
                return word
        return "in"

    def guard() -> str:
        states = []
        for on, script, settings, trusted in (
                (claude, HOME / ".claude" / "hooks" / "bash-guard.py", HOME / ".claude" / "settings.json", True),
                (chatgpt, CODEX_DIR / "hooks" / "bash-guard.py", CODEX_DIR / "hooks.json", False)):
            if not on:
                continue
            commands = _hook_commands(settings, "PreToolUse")
            if commands is None and script.is_file():
                states.append("unreadable")
                continue
            entered = script.is_file() and any(_names_file(c, script) for c in commands or [])
            states.append(("in" if trusted else "unseen") if entered else "missing")
        return combine(states)

    def save() -> str:
        if v is None or not (v / "scripts" / "turn-end-commit.py").is_file():
            return "missing"
        wanted = v / "scripts" / "turn-end-commit.py"
        states = []
        for on, settings, trusted in ((claude, HOME / ".claude" / "settings.json", True),
                                      (chatgpt, CODEX_DIR / "hooks.json", False)):
            if not on:
                continue
            commands = _hook_commands(settings, "Stop")
            if commands is None:
                states.append("unreadable")
                continue
            entered = any(_names_file(c, wanted) for c in commands)
            states.append(("in" if trusted else "unseen") if entered else "missing")
        return combine(states)

    def tour() -> str:
        """(0.16.0) The first-week tour: the wiki's scripts/first-days.py entered
        as Claude's SessionStart hook by its full path, read as the save is."""
        wanted = v / "scripts" / "first-days.py" if v is not None else None
        if wanted is None or not wanted.is_file():
            return "missing"
        commands = _hook_commands(HOME / ".claude" / "settings.json", "SessionStart")
        if commands is None:
            return "unreadable"
        return "in" if any(_names_file(c, wanted) for c in commands) else "missing"

    core = []
    for part in CORE_PARTS:
        key = part["key"]
        if key == "guard":
            state = guard()
        elif key == "save":
            state = save()
        elif key == "tour":
            if not claude:
                continue      # entered for Claude only; nothing to show an owner on ChatGPT alone
            state = tour()
        elif key == "dashboard":
            state = "in" if v is not None and (v / "dashboard" / "server.py").is_file() else "missing"
        elif key == "galaxy":
            state = skill("galaxy")
            if state == "in" and (v is None or not (v / "scripts" / "wiki-galaxy" / "build.py").is_file()):
                state = "missing"
        elif (PACKAGE_ROOT / "skills" / key).is_dir():
            state = skill(key)
        else:
            continue          # a part this Moblee does not carry is not listed
        core.append(dict(part, state=state))

    try:
        record = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}
    except (OSError, ValueError):
        record = {}
    if not isinstance(record, dict):
        record = {}
    status = record.get("status") if isinstance(record.get("status"), dict) else {}
    unseen = set(k for k in record.get("unseen", []) if isinstance(k, str)) if isinstance(record.get("unseen"), list) else set()
    extras = {}
    for it in build_items():
        seen = status.get(it.key, "never")
        if it.key in unseen or seen is None:
            extras[it.key] = "unseen"
        elif seen is True:
            extras[it.key] = "on"
        elif seen is False:
            extras[it.key] = "off"
        else:
            extras[it.key] = "unknown"
    checked = record.get("last_check") if isinstance(record.get("last_check"), str) else None
    return {"assistant": who, "vault": bool(v), "checked": checked, "core": core, "extras": extras}


def main() -> int:
    ap = argparse.ArgumentParser(description="Connect a Moblee wiki to this Mac, its accounts and its tools.")
    ap.add_argument("--check", action="store_true", help="test everything and change nothing")
    ap.add_argument("--only", help="comma-separated item keys to install, skipping the checklist")
    ap.add_argument("--tick", help="comma-separated item keys to show ticked in the checklist (the owner still confirms)")
    ap.add_argument("--list", action="store_true", help="print every item with its key, time, space and cost, and stop")
    ap.add_argument("--json", action="store_true", help="with --list: print the items as JSON, for the Moblee app")
    ap.add_argument("--yes", action="store_true", help="with --only: do not ask 'Start now?' (the Moblee app uses this after the owner presses an item's button)")
    ap.add_argument("--progress", action="store_true", help="also print one machine-readable line per item, for the Moblee app")
    ap.add_argument("--parts", action="store_true", help="print, as JSON, what comes with the wiki and what was last seen of each extra; read only (0.14.0)")
    args = ap.parse_args()

    if platform.system() != "Darwin":
        say("Moblee runs on a Mac only.")
        return 1
    if args.yes and not args.only:
        say("--yes is only for use with --only, so that nothing is installed that was not named.")
        return 1
    if args.yes and os.environ.get("CLAUDECODE"):
        # Installing is the owner's act. Claude Code marks the commands it runs,
        # so a run started by Claude is turned away here.
        say("This has to be started by the owner, in the Moblee app or a Terminal window of their own.")
        return 1
    global PROGRESS
    PROGRESS = args.progress

    if args.parts:
        print(json.dumps(parts_report(), indent=2))
        return 0
    items = build_items()
    if args.list and args.json:
        print(json.dumps([{"key": it.key, "group": it.group, "title": it.title, "what": it.what, "minutes": it.minutes,
                           "space_mb": it.space_mb, "cost": it.cost, "paid": it.cost.startswith("PAID"),
                           "needs": it.needs, "signin": it.signin, "how": how(it.key),
                           "steps": CLICKS.get(it.key, [])}
                          for it in items], indent=2))
        return 0
    if args.list:
        for it in items:
            size = f"{it.space_mb / 1000:.1f} GB" if it.space_mb >= 1000 else f"{it.space_mb} MB"
            needs = f"; stands on {', '.join(it.needs)}" if it.needs else ""
            say(f"{it.key:<16} {it.title}: about {it.minutes} min, {size}, {it.cost}{needs}")
        say("")
        names = {"devtools": "Apple's developer tools", "homebrew": "Homebrew", "node": "Node"}
        say("Installed once, the first time an item stands on them:")
        for k, (m, mb) in FOUNDATION_COST.items():
            say(f"{k:<16} {names[k]}: about {m} min, {mb / 1000:.1f} GB")
        return 0

    rule("Moblee setup: connect your wiki to your life")
    opening, stop_here = checklist_opening(args.check)
    for line in opening:
        say(line)
    if stop_here:
        return 0

    if args.check:
        results = final_check(items)
        path = write_report(results, vault_path())
        # keep the saved state current, so the weekly check reads what is true now
        try:
            save_state({it.key: ok for it, ok, _ in results}, results, last_check=STAMP)
        except (OSError, TypeError, ValueError):
            pass  # a state file that cannot be written never fails the check
        say(f"\nThe result is saved at {path}")
        # "cannot see" is not a failure: only something seen to be broken is
        return 0 if all(ok is not False for _, ok, _ in results) else 1

    # so skills and the owner's Claude can find the pack to point back at it
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    (CONFIG_DIR / "package-path").write_text(str(PACKAGE_ROOT) + "\n")

    preset = {k.strip() for k in args.only.split(",") if k.strip()} if args.only else None
    if args.yes:
        # Started from the Moblee app for named items: check only those now, and
        # carry the rest forward from the last saved state, so a one-minute item
        # is not kept waiting behind a sweep of everything.
        try:
            saved = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}
            saved = saved.get("status", {}) if isinstance(saved, dict) else {}
        except (OSError, ValueError):
            saved = {}
        if not isinstance(saved, dict):
            saved = {}
        # (0.14.0) An item the record has never named stays unnamed, rather than
        # being written down as not working when nobody looked at it.
        status = {it.key: (it.check()[0] if it.key in preset else bool(saved[it.key]))
                  for it in items if it.key in preset or it.key in saved}
        checked = set(preset)
    else:
        say("Looking at what is already working (this can take a minute or two)...")
        status = {it.key: it.check()[0] for it in items}   # None: could not be seen, kept as such for the record
        checked = set(status)

    tick = {k.strip() for k in args.tick.split(",") if k.strip()} if args.tick else None
    for asked in (preset, tick):
        unknown = (asked or set()) - {it.key for it in items}
        if unknown:
            say("Not on the list: " + ", ".join(sorted(unknown)) + ". Use --list to see the keys.")
            return 1
    chosen = choose(items, status, preset, tick)
    if not chosen:
        say("Nothing to install. Everything you ticked is already working, or nothing was ticked.")
        for k in sorted(preset or ()):
            emit(k, "ok", already=True)
        emit("done", "ok", restart=False)
        return 0
    foundations = foundations_needed(chosen)
    if not summarise(chosen, foundations, assume_yes=args.yes):
        say("Nothing was installed. Run this again whenever you are ready.")
        return 0

    have = {"devtools": devtools_ok(), "homebrew": homebrew_ok()}
    if have["homebrew"]:
        ensure_brew_on_path()
    if "devtools" in foundations:
        have["devtools"] = install_devtools()
    if "homebrew" in foundations:
        have["homebrew"] = install_homebrew()
    have["node"] = bool(which("node")) or ("node" in foundations and have["homebrew"] and brew_install(["node"]))

    for it in chosen:
        blocked = [n for n in it.needs if not have.get(n)]
        rule(it.title)
        emit(it.key, "start")
        if blocked:
            say("  Skipped: it needs " + ", ".join(blocked) + ", which did not install.")
            continue
        try:
            it.install()
        except KeyboardInterrupt:
            say("\n  Stopped by you. Moving on to the next item.")
        except Exception as exc:
            say(f"  Something unexpected went wrong: {exc}")
            with open(log_path(), "a") as fh:
                fh.write(f"\n[{it.key}] exception: {exc!r}\n")

    results = final_check(items, only={it.key for it in chosen})
    path = write_report(results, vault_path())
    for it, ok, detail in results:
        status[it.key] = ok
        # the check's own plain sentence travels with a failure, so the app can
        # say why ("it needs the Chrome item first") and not only that it failed
        emit(it.key, "unseen" if ok is None else ("ok" if ok else "fail"),
             detail=str(detail).replace(str(HOME), "~"))
    save_state(status, results, checked=checked, last_run=STAMP, last_run_items=[it.key for it in chosen])

    failed = [it for it, ok, _ in results if ok is False]
    blind = [it for it, ok, _ in results if ok is None]
    say("")
    if blind:
        say("Cannot be seen from here: " + ", ".join(it.title for it in blind) + ".")
        say("That is not a fault. Ask Claude to use it; if it answers, it is connected.")
    if failed:
        say("Some items are not working yet (listed above). Nothing else is affected.")
        keys = [it.key for it in failed]
        if "x-capture" in keys and "chrome" not in keys and not check_chrome()[0]:
            keys.insert(0, "chrome")  # x-capture works through Chrome
        say("To try them again:  python3 scripts/moblee-setup.py --only " + ",".join(keys))
    elif blind:
        say("Everything else you ticked is working.")
    else:
        say("Everything you ticked is working.")
    say(f"This result is saved at {path}")
    connections = {"mac-apps", "google", "chrome", "generation"}
    skills_or_tools = {"videos", "film", "documents", "skill-maker", "obsidian-extras"}
    has_conn = any(it.key in connections for it in chosen)
    has_skill = any(it.key in skills_or_tools for it in chosen)
    restart = has_conn or has_skill
    emit("done", "ok", restart=restart)
    if restart:
        new = "connections and skills" if has_conn and has_skill else ("connections" if has_conn else "skills")
        say("")
        say(f"Quit Claude and open it again so it sees the new {new}.")
        if any(it.key == "chrome" for it in chosen):
            say("Then type /chrome inside Claude Code and switch it on.")
    # Started by the Moblee app (--yes), the exit code is what the app's Terminal
    # window reads to choose between "Finished" and "That did not finish", so an
    # item seen to be not working is a failure there. From the installer, the
    # updater or a Terminal of the owner's own it stays 0, as it always was: the
    # words above have already said what did not work, and those callers take
    # any other code to mean the checklist itself stopped early.
    return 1 if (failed and args.yes) else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        say("\nStopped. Anything half-installed is finished by running this again.")
        sys.exit(130)
