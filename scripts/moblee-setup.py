#!/usr/bin/env python3
"""moblee-setup.py: the checklist that connects a Moblee wiki to the owner's
Mac, accounts and tools, then proves each piece works.

Run from the Moblee package folder, in Terminal:

    python3 scripts/moblee-setup.py            # show the checklist, install what is ticked
    python3 scripts/moblee-setup.py --check    # test everything, change nothing
    python3 scripts/moblee-setup.py --only google,github   # just these items

The installer runs it after laying down the vault; the updater offers it; it
can be run again at any time to add something that was left out. Nothing it
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


def env_with_brew() -> dict:
    env = dict(os.environ)
    prefix = brew_prefix()
    extra = [str(prefix / "bin"), str(prefix / "sbin")] if prefix else []
    env["PATH"] = ":".join(extra + [env.get("PATH", "/usr/bin:/bin")])
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


def plugin_installed(plugin_id: str) -> bool:
    code, out = run(["claude", "plugin", "list", "--json"], timeout=120)
    if code != 0:
        code, out = run(["claude", "plugin", "list"], timeout=120)
    return plugin_id in out


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
    """'connected', 'needs-login', 'absent', or 'no-claude-ai' for a claude.ai connector."""
    if "out" not in _cache:
        say("  Asking Claude Code which connections it can see (this can take a minute or two)...")
        _cache["out"] = run(["claude", "mcp", "list"], timeout=240)[1] if claude_ok() else ""
    lines = _cache["out"].splitlines()
    for line in lines:
        if line.startswith(f"claude.ai {name}:"):
            return "connected" if "Connected" in line and "✘" not in line else "needs-login"
    if not any(l.startswith("claude.ai ") for l in lines):
        return "no-claude-ai"
    return "absent"


NO_CLAUDE_AI = ("Claude Code shows no claude.ai connections at all: it must be signed in with "
                "your Claude account (type /login in Claude Code), not an API key")


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


def deny_rules_present(rules: list, kind: str = "deny") -> bool:
    try:
        listed = load_settings().get("permissions", {}).get(kind, [])
    except json.JSONDecodeError:
        return False
    return all(r in listed for r in rules)


# ----------------------------------------------------------------------------
# the items
# ----------------------------------------------------------------------------

class Item:
    def __init__(self, key, group, title, what, minutes, space_mb, cost, default,
                 needs=(), signin=None, install=None, check=None):
        self.key, self.group, self.title, self.what = key, group, title, what
        self.minutes, self.space_mb, self.cost, self.default = minutes, space_mb, cost, default
        self.needs, self.signin = list(needs), signin
        self._install, self._check = install, check

    def check(self) -> tuple[bool, str]:
        try:
            return self._check()
        except Exception as exc:  # a check must never crash the checklist
            return False, f"the check itself failed ({exc})"

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
    code, out = run(["claude", "mcp", "get", "orchard"], timeout=120)
    if code != 0:
        return False, "installed, but not connected to Claude"
    if "Connected" not in out or "✘" in out:
        return False, "registered with Claude, but it does not start; run the checklist item again"
    if not deny_rules_present(ORCHARD_DENY):
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
        return False, NO_CLAUDE_AI
    good = [n for n, s in states.items() if s == "connected"]
    if len(good) == 3:
        return True, "Gmail, Google Calendar and Google Drive are connected"
    missing = [n for n, s in states.items() if s != "connected"]
    return False, "not connected yet: " + ", ".join(missing)


def install_google():
    rule("Google: sign in (only you can do this)")
    say("Google connects through your Claude account, in the browser.")
    say("")
    say("  1. A page opens: claude.ai, Settings, Connectors.")
    say("     If it asks you to log in, use the same Claude account as Claude Code.")
    say("  2. Find Gmail and click Connect. Sign in with your Google account and")
    say("     allow what Google asks.")
    say("  3. Do the same for Google Calendar, then Google Drive.")
    say("  4. Come back to this window.")
    say("")
    open_url(CONNECTORS_URL)
    if not wait_for_return():
        return False
    forget_connector_cache()
    return True


# --- GitHub ------------------------------------------------------------------

def check_github():
    if not which("gh"):
        return False, "GitHub's tool is not installed"
    if run(["gh", "auth", "status"], timeout=60)[0] != 0:
        return False, "installed, but not signed in"
    return True, "signed in to GitHub"


def install_github():
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
    if not plugin_installed("watch@claude-video"):
        return False, "the watch tool is not installed in Claude Code"
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


def weasyprint_ok() -> bool:
    py = pdf_python()
    return bool(py) and run([py, "-c", "import weasyprint, markdown, jinja2, yaml, pypdf"], timeout=120)[0] == 0


def check_documents():
    problems = []
    if not weasyprint_ok():
        problems.append("the PDF renderer")
    if not plugin_installed("document-skills@anthropic-agent-skills"):
        problems.append("the Word, PowerPoint and Excel tools")
    if problems:
        return False, "missing " + " and ".join(problems)
    return True, "PDF, Word, PowerPoint and Excel all work"


def install_documents():
    ok = brew_install(["python", "cairo", "pango", "gdk-pixbuf", "libffi"])
    py = pdf_python()
    if py and not weasyprint_ok():
        ok = run_logged([py, "-m", "pip", "install", "--user", "--break-system-packages",
                         "weasyprint", "markdown", "jinja2", "PyYAML", "pypdf"],
                        "Installing the PDF renderer", timeout=1800) and ok
    if py and weasyprint_ok():
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
    if not plugin_installed("remotion@remotion"):
        return False, "the video studio plugin is not installed"
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
    if plugin_installed("skill-creator@claude-plugins-official"):
        return True, "say 'make a skill for ...' to teach Claude a routine"
    return False, "not installed"


def install_skill_maker():
    return install_plugin("anthropics/claude-plugins-official", "skill-creator@claude-plugins-official")


def check_obsidian_extras():
    if plugin_installed("obsidian@obsidian-skills"):
        return True, "canvases, databases and Obsidian's own formats"
    return False, "not installed"


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
    except json.JSONDecodeError:
        return False, "settings could not be read"
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
        return False, NO_CLAUDE_AI
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
    say("  2. A page opens: claude.ai, Settings, Connectors.")
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


# --- the list, in the order it is shown ---------------------------------------

def build_items() -> list:
    news_check, news_install = skill_item("news-brief", "say 'news brief'; every item is checked against a second source")
    trips_check, trips_install = skill_item("trips", "say 'start a trip to ...'")
    connect, make, paid, habits = ("Connect your life", "Read and make things", "Paid, or with a paid option", "Habits")
    return [
        Item("mac-apps", connect, "Your Mac's Calendar, Reminders, Mail and Notes",
             "Claude reads your Mac's own apps when you ask, so you never upload a calendar file again.",
             8, 60, "free", True, needs=("devtools", "homebrew", "node"), signin="click Allow on your Mac's pop-ups",
             install=install_mac_apps, check=check_mac_apps),
        Item("google", connect, "Gmail, Google Calendar and Google Drive",
             "Claude reads your Google mail, calendar and files when you ask. It drafts; you send.",
             3, 0, "free", True, signin="sign in to Google in your browser",
             install=install_google, check=check_google),
        Item("github", connect, "GitHub",
             "Claude can read and work with your GitHub projects.",
             4, 40, "free (needs a free GitHub account)", True, needs=("homebrew",), signin="sign in to GitHub in your browser",
             install=install_github, check=check_github),
        Item("chrome", connect, "Chrome, with your X, Instagram and YouTube",
             "Claude uses Chrome to read pages behind your own logins. It never posts without your yes.",
             5, 0, "free (installs Chrome if you do not have it)", True, needs=("homebrew",),
             signin="add two Chrome extensions and sign in",
             install=install_chrome, check=check_chrome),
        Item("videos", make, "Watch and summarise videos",
             "Send a YouTube, Instagram, TikTok or X link and Claude watches it for you.",
             4, 200, "free", True, needs=("homebrew",), install=install_videos, check=check_videos),
        Item("documents", make, "PDF, Word, PowerPoint and Excel",
             "Turn wiki pages into polished PDFs, and make or read Office documents.",
             10, 300, "free", True, needs=("homebrew",), install=install_documents, check=check_documents),
        Item("film", make, "Video editing",
             "Cut clips together, add titles, captions and music, from a plain description.",
             12, 1500, "free for individuals (Remotion's licence; larger companies need one)", True,
             needs=("devtools", "homebrew", "node"), install=install_film, check=check_film),
        Item("audio", make, "Audio editing and read-aloud",
             "Trim, join, clean up and convert audio, and turn any page into a spoken recording.",
             4, 150, "free", True, needs=("homebrew",), install=install_audio, check=check_audio),
        Item("pictures", make, "Picture editing",
             "Crop, resize, convert, compress and caption photos and images.",
             5, 120, "free", True, needs=("homebrew",), install=install_pictures, check=check_pictures),
        Item("news-brief", make, "A daily news brief, every item checked twice",
             "News on what you follow, each item confirmed by a second source and linked.",
             1, 1, "free", True, install=news_install, check=news_check),
        Item("trips", make, "Trip planning",
             "A page per trip with flights, stays and day plans, built from your booking emails.",
             1, 1, "free", True, install=trips_install, check=trips_check),
        Item("x-capture", make, "Save X posts into the wiki",
             "Paste an x.com link and Claude keeps the post, properly sourced. Needs the Chrome item.",
             1, 1, "free", True, install=lambda: install_skill("x-capture"), check=check_x_capture),
        Item("skill-maker", make, "Teach Claude your own routines",
             "Describe something you do often and Claude turns it into a one-word command.",
             2, 5, "free", True, install=install_skill_maker, check=check_skill_maker),
        Item("obsidian-extras", make, "Obsidian extras",
             "Claude can build Obsidian canvases, databases and diagrams.",
             2, 5, "free", True, install=install_obsidian_extras, check=check_obsidian_extras),
        Item("generation", paid, "Create new images, video, voices and music (ElevenLabs)",
             "Generate things that do not exist yet. Needs your own ElevenLabs account; see the prices first.",
             5, 0, "PAID: free tier with small limits; plans from about $6 a month (Sept 2026)", False,
             signin="make an ElevenLabs account and connect it", install=install_generation, check=check_generation),
        Item("voice", paid, "Claude reads its replies aloud",
             "Spoken replies and a nudge when Claude is waiting on you. Mac voice free; ElevenLabs voice optional and paid.",
             3, 5, "free (paid voice optional)", False, install=install_voice, check=check_voice),
        Item("weekly", habits, "Weekly health check",
             "The wiki checks itself every Saturday morning and tells you what needs attention.",
             1, 0, "free", True, install=install_weekly, check=check_weekly),
        Item("lessons", habits, "The learning path",
             "Thirty-two short lessons, one an evening, with a 9 pm reminder.",
             1, 1, "free", False, install=install_lessons, check=check_lessons),
        Item("vault-fn", habits, "The 'vault' shortcut in Terminal",
             "Type vault in Terminal to open Claude in your wiki.",
             1, 0, "free", False, install=install_vault_fn, check=check_vault_fn),
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

def show_checklist(items: list, ticked: dict, status: dict) -> None:
    say("")
    say("Tick what you want. Items already working are marked 'working' and are")
    say("left alone. Type the numbers to tick or untick (for example: 3 7 12),")
    say("'all' for everything, 'free' for everything free, 'none' to clear, and")
    say("press Return on its own when the list is right.")
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


def choose(items: list, status: dict, preset: set | None) -> list:
    ticked = {it.key: (it.key in preset) if preset is not None else (it.default and not status.get(it.key)) for it in items}
    if preset is not None:
        return [it for it in items if ticked[it.key] and not status.get(it.key)]
    while True:
        show_checklist(items, ticked, status)
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


def summarise(chosen: list, foundations: list) -> bool:
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
    say(f"Expect about {minutes} minutes and {space / 1000:.1f} GB of space,")
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
    return yes("Start now?", default=True)


def write_report(results: list, vault: Path | None) -> Path:
    lines = [f"# Moblee setup check, {datetime.datetime.now().strftime('%-d %B %Y, %H:%M')}", ""]
    for it, ok, detail in results:
        lines.append(f"- {'Working' if ok else 'Not working'}: **{it.title}**. {detail}.")
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
        say(f"  {'WORKING    ' if ok else 'NOT WORKING'}  {it.title}: {detail}")
    return results


def main() -> int:
    ap = argparse.ArgumentParser(description="Connect a Moblee wiki to this Mac, its accounts and its tools.")
    ap.add_argument("--check", action="store_true", help="test everything and change nothing")
    ap.add_argument("--only", help="comma-separated item keys to install, skipping the checklist")
    ap.add_argument("--list", action="store_true", help="print the item keys and stop")
    args = ap.parse_args()

    if platform.system() != "Darwin":
        say("Moblee runs on a Mac only.")
        return 1

    items = build_items()
    if args.list:
        for it in items:
            say(f"{it.key:<16} {it.title}")
        return 0

    rule("Moblee setup: connect your wiki to your life")
    if not claude_ok():
        say("Claude Code is not installed yet. Install it first (see docs/01-prerequisites.md),")
        say("then run this again. Items that do not need it can still be added now.")

    if args.check:
        results = final_check(items)
        path = write_report(results, vault_path())
        say(f"\nThe result is saved at {path}")
        return 0 if all(ok for _, ok, _ in results) else 1

    # so skills and the owner's Claude can find the pack to point back at it
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    (CONFIG_DIR / "package-path").write_text(str(PACKAGE_ROOT) + "\n")

    say("Looking at what is already working (this can take a minute or two)...")
    status = {it.key: it.check()[0] for it in items}

    preset = {k.strip() for k in args.only.split(",") if k.strip()} if args.only else None
    if preset:
        unknown = preset - {it.key for it in items}
        if unknown:
            say("Not on the list: " + ", ".join(sorted(unknown)) + ". Use --list to see the keys.")
            return 1
    chosen = choose(items, status, preset)
    if not chosen:
        say("Nothing to install. Everything you ticked is already working, or nothing was ticked.")
        return 0
    foundations = foundations_needed(chosen)
    if not summarise(chosen, foundations):
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
    state = {"last_run": STAMP, "chosen": [it.key for it in chosen],
             "working": [it.key for it, ok, _ in results if ok]}
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2) + "\n")

    failed = [it for it, ok, _ in results if not ok]
    say("")
    if failed:
        say("Some items are not working yet (listed above). Nothing else is affected.")
        keys = [it.key for it in failed]
        if "x-capture" in keys and "chrome" not in keys and not check_chrome()[0]:
            keys.insert(0, "chrome")  # x-capture works through Chrome
        say("To try them again:  python3 scripts/moblee-setup.py --only " + ",".join(keys))
    else:
        say("Everything you ticked is working.")
    say(f"This result is saved at {path}")
    if any(it.key in ("mac-apps", "google", "chrome", "generation", "videos", "film", "documents",
                      "skill-maker", "obsidian-extras") for it in chosen):
        say("")
        say("Quit Claude Code and open it again so it sees the new connections.")
        if any(it.key == "chrome" for it in chosen):
            say("Then type /chrome inside Claude Code and switch it on.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        say("\nStopped. Anything half-installed is finished by running this again.")
        sys.exit(130)
