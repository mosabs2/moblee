#!/usr/bin/env python3
"""install-safety.py — put the delete guard and the permission rules in place.

Run by the Moblee installer and updater; safe to run by hand and safe to
run twice:

    python3 safety/install-safety.py                 # vault from ~/.config/moblee/vault-path
    python3 safety/install-safety.py --vault ~/Wiki/MyWiki
    python3 safety/install-safety.py --dry-run       # say what would change, change nothing
    python3 safety/install-safety.py --assistant chatgpt   # claude (default), chatgpt or both

Without --assistant the choice is read from ~/.config/moblee/assistant; with
no such file it is claude, and everything below happens exactly as it always
has.

What it does for Claude, in order, stopping at the first failure:

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

What it does for ChatGPT, in order, stopping at the first failure:

  1. Copies bash-guard.py to ~/.codex/hooks/ and makes it executable, then
     proves it the same way, with one more test: a file-editing patch that
     deletes a page must be refused too.
  2. Registers the guard in ~/.codex/hooks.json as a PreToolUse hook on
     Bash and apply_patch. The entry is only ever added at the end of the
     list: ChatGPT remembers the owner's trust hook by hook, and a hook that
     moves is switched off until it is trusted again. Nothing already in the
     file is reordered, removed or rewritten.
  3. Makes sure ~/.codex/config.toml sets project_doc_max_bytes, so ChatGPT
     reads the whole instruction file. No existing line is altered.

ChatGPT runs a new or changed hook only after the owner trusts it. When that
step is needed the last line printed is "@@moblee-trust-needed chatgpt", which
the app and the updater read.

Everything here is standard-library Python; nothing is downloaded.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import re
import shlex
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

# ChatGPT (its agent, Codex, keeps its settings under ~/.codex)
CODEX_DIR = Path.home() / ".codex"
CODEX_HOOKS_DIR = CODEX_DIR / "hooks"
CODEX_GUARD_DST = CODEX_HOOKS_DIR / "bash-guard.py"
CODEX_HOOKS_JSON = CODEX_DIR / "hooks.json"
CODEX_CONFIG = CODEX_DIR / "config.toml"
CODEX_MATCHER = "Bash|apply_patch"
CODEX_GUARD_MARK = ".codex/hooks/bash-guard.py"
CODEX_GUARD_BACKUP = "codex-bash-guard.py"  # Claude's guard has the same file name
CODEX_DOC_KEY = "project_doc_max_bytes"
CODEX_DOC_VALUE = "65536"
CODEX_DOC_COMMENT = "# added by Moblee: lets ChatGPT read the whole wiki instruction file"
TRUST_LINE = "@@moblee-trust-needed chatgpt"

ASSISTANT_FILE = Path.home() / ".config" / "moblee" / "assistant"
ASSISTANTS = ("claude", "chatgpt", "both")


def say(msg: str) -> None:
    print(msg, flush=True)


def short(p: Path) -> str:
    s = str(p)
    home = str(Path.home())
    return "~" + s[len(home):] if s.startswith(home) else s


def read_assistant(explicit: str | None) -> str:
    """The owner's choice of assistant: --assistant when given, otherwise the
    one word kept in ~/.config/moblee/assistant, otherwise claude."""
    if explicit is not None and explicit.strip():
        value, where = explicit.strip().lower(), "--assistant"
    else:
        try:
            value = ASSISTANT_FILE.read_text().strip().lower()
        except (OSError, ValueError):
            value = ""
        where = short(ASSISTANT_FILE)
        if not value:
            return "claude"
    if value not in ASSISTANTS:
        print(f"'{value}' ({where}) is not an assistant Moblee knows. "
              "Use claude, chatgpt or both.", file=sys.stderr, flush=True)
        sys.exit(2)
    return value


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


def backup(path: Path, stamp: str, name: str | None = None) -> Path | None:
    if not path.exists():
        return None
    dst_dir = BACKUP_ROOT / stamp
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / (name or path.name)
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


# ------------------------------------------------------------------ ChatGPT
def read_utf8(path: Path) -> str | None:
    """The file's text exactly as it sits on disk (line endings kept), or None
    when there is no such file."""
    if not path.exists():
        return None
    try:
        return path.read_bytes().decode("utf-8")
    except (OSError, ValueError) as e:
        sys.exit(f"{short(path)} could not be read ({e}). Nothing was changed; "
                 "fix or move it aside, then re-run.")


def write_text_checked(path: Path, text: str, expected=None) -> None:
    """Write beside the real file, check the copy, then swap it in. With
    `expected`, the copy must parse as JSON to exactly that. A file that is a
    link stays a link, and the file keeps its permissions."""
    real = Path(os.path.realpath(path))
    real.parent.mkdir(parents=True, exist_ok=True)
    tmp = real.with_suffix(real.suffix + ".tmp")
    tmp.write_bytes(text.encode("utf-8"))
    if tmp.read_bytes().decode("utf-8") != text:
        sys.exit(f"Refusing to write {short(path)}: the copy did not read back the same.")
    if expected is not None and json.loads(text) != expected:
        sys.exit(f"Refusing to write {short(path)}: the result is not what was intended.")
    if real.exists():
        shutil.copymode(real, tmp)
    os.replace(tmp, real)


def codex_python() -> str:
    """The Python that ChatGPT will start the guard with."""
    stock = "/usr/bin/python3"
    return stock if os.access(stock, os.X_OK) else sys.executable


def codex_guard_cmd() -> str:
    # The full path is written out. The hooks documentation never says that
    # $HOME is expanded in a hook command, and a guard that cannot be found
    # does not stop anything.
    return f"{shlex.quote(codex_python())} {shlex.quote(str(CODEX_GUARD_DST))}"


def codex_entry() -> dict:
    return {"matcher": CODEX_MATCHER,
            "hooks": [{"type": "command", "command": codex_guard_cmd(), "timeout": 10}]}


def codex_entry_present(pre: list) -> bool:
    for g in pre:
        if not isinstance(g, dict) or g.get("matcher") != CODEX_MATCHER:
            continue
        for h in g.get("hooks") or []:
            if isinstance(h, dict) and CODEX_GUARD_MARK in str(h.get("command", "")):
                return True
    return False


def load_codex_hooks() -> tuple:
    """(settings object, text on disk or None). Stops with one plain sentence,
    before anything is changed, if the file cannot be added to."""
    raw = read_utf8(CODEX_HOOKS_JSON)
    if raw is None:
        return {}, None
    try:
        data = json.loads(raw)
    except Exception as e:  # noqa: BLE001
        sys.exit(f"{short(CODEX_HOOKS_JSON)} is not valid JSON ({e}). Nothing was "
                 "changed; fix or move it aside, then re-run.")
    if not isinstance(data, dict):
        sys.exit(f"{short(CODEX_HOOKS_JSON)} does not hold the expected settings object. "
                 "Nothing was changed; move it aside, then re-run.")
    hooks = data.get("hooks", {})
    if not isinstance(hooks, dict) or not isinstance(hooks.get("PreToolUse", []), list):
        sys.exit(f"{short(CODEX_HOOKS_JSON)} has a 'hooks' section that is not the usual "
                 "shape. Nothing was changed; ask your assistant to look at that file "
                 "before re-running.")
    return data, raw


_WS = " \t\r\n"


def _skip_ws(t: str, i: int) -> int:
    while i < len(t) and t[i] in _WS:
        i += 1
    return i


def _skip_string(t: str, i: int) -> int:
    i += 1
    while t[i] != '"':
        i += 2 if t[i] == "\\" else 1
    return i + 1


def _skip_value(t: str, i: int) -> int:
    """Index just past the JSON value that starts at t[i]."""
    if t[i] == '"':
        return _skip_string(t, i)
    if t[i] in "{[":
        depth = 0
        while True:
            c = t[i]
            if c == '"':
                i = _skip_string(t, i)
                continue
            if c in "{[":
                depth += 1
            elif c in "}]":
                depth -= 1
                if depth == 0:
                    return i + 1
            i += 1
    while i < len(t) and t[i] not in ",}]" + _WS:
        i += 1
    return i


def _member_value(t: str, obj: int, key: str) -> int:
    """Index where the value of `key` starts inside the object opening at
    t[obj], or -1 when the object has no such key."""
    i = _skip_ws(t, obj + 1)
    while t[i] != "}":
        end = _skip_string(t, i)
        name = json.loads(t[i:end])
        i = _skip_ws(t, end)        # at the colon
        i = _skip_ws(t, i + 1)      # at the value
        if name == key:
            return i
        i = _skip_ws(t, _skip_value(t, i))
        if t[i] == ",":
            i = _skip_ws(t, i + 1)
    return -1


def _append_in(t: str, open_idx: int, item: str, pad: str) -> str:
    """t with `item` added as the last element of the list or object that
    opens at t[open_idx]. Every original character stays where it was."""
    close = _skip_value(t, open_idx) - 1
    if not t[open_idx + 1:close].strip():
        return t[:close] + "\n" + item + "\n" + pad[2:] + t[close:]
    j = close
    while t[j - 1] in _WS:
        j -= 1
    return t[:j] + ",\n" + item + t[j:]


def _indented(obj, pad: str, key: str | None = None) -> str:
    body = json.dumps(obj, indent=2)
    if key is not None:
        body = json.dumps(key) + ": " + body
    return "\n".join(pad + line for line in body.splitlines())


def append_codex_entry_text(text: str, entry: dict) -> str:
    """The hooks.json text with `entry` added at the end of hooks.PreToolUse
    and not one other character touched, so the hooks the owner has already
    trusted stay exactly as ChatGPT last saw them."""
    top = _skip_ws(text, 0)
    if text[top] != "{":
        raise ValueError("not an object")
    h = _member_value(text, top, "hooks")
    if h < 0:
        return _append_in(text, top, _indented({"PreToolUse": [entry]}, "  ", "hooks"), "  ")
    p = _member_value(text, h, "PreToolUse")
    if p < 0:
        return _append_in(text, h, _indented([entry], "    ", "PreToolUse"), "    ")
    return _append_in(text, p, _indented(entry, "      "), "      ")


def _toml_line_state(line: str, depth: int, ml: str | None) -> tuple:
    """Bracket depth and open multi-line string after reading one line."""
    i, n = 0, len(line)
    while i < n:
        if ml:
            j = line.find(ml, i)
            if j < 0:
                return depth, ml
            i, ml = j + 3, None
            continue
        c = line[i]
        if c == "#":
            break
        if line.startswith('"""', i) or line.startswith("'''", i):
            ml = line[i:i + 3]
            i += 3
            continue
        if c == '"':
            i += 1
            while i < n and line[i] != '"':
                i += 2 if line[i] == "\\" else 1
            i += 1
            continue
        if c == "'":
            j = line.find("'", i + 1)
            i = n if j < 0 else j + 1
            continue
        if c in "[{":
            depth += 1
        elif c in "]}":
            depth = max(0, depth - 1)
        i += 1
    return depth, ml


def ensure_top_level_key(text: str, key: str, value_literal: str) -> str:
    """`text` (a TOML file) with `key = value_literal` as a top-level setting.
    If the key is already set above the first [table], the text comes back
    unchanged, whatever its value. Otherwise the line goes in just above the
    first [table] header (above a comment that sits directly on that header,
    so the comment stays with its table), or at the end when there is no
    table. Lines are only ever added; no existing line is altered."""
    cr = "\r" if "\r\n" in text else ""
    lines = text.split("\n")
    key_re = re.compile(r"""^\s*(?:%s|"%s"|'%s')\s*=""" % ((re.escape(key),) * 3))
    depth, ml = 0, None
    clean = []      # does line i start outside any value that spans lines?
    header = None
    for idx, line in enumerate(lines):
        is_clean = depth == 0 and ml is None
        clean.append(is_clean)
        if is_clean:
            if line.lstrip().startswith("["):
                header = idx
                break
            if key_re.match(line):
                return text
        depth, ml = _toml_line_state(line, depth, ml)
    added = [CODEX_DOC_COMMENT + cr, f"{key} = {value_literal}" + cr]
    if header is None:
        if lines[-1] == "":
            at = len(lines) - 1
            tail = []
        else:
            at = len(lines)
            tail = [""]
        if at > 0 and lines[at - 1].strip():
            added.insert(0, cr)
        lines[at:at] = added + tail
    else:
        at = header
        while at > 0 and clean[at - 1] and lines[at - 1].lstrip().startswith("#"):
            at -= 1
        lines[at:at] = added + [cr]
    return "\n".join(lines)


def check_toml_insert(old: str, new: str, key: str) -> None:
    """Where this Python can read TOML (3.11 on), prove the new text is the old
    settings plus the one key, before anything is changed. Older Pythons
    cannot check and rely on ensure_top_level_key alone."""
    try:
        import tomllib
    except ImportError:
        return
    try:
        before = tomllib.loads(old)
    except Exception as e:  # noqa: BLE001
        sys.exit(f"{short(CODEX_CONFIG)} could not be read as settings ({e}). Nothing "
                 "was changed; fix or move it aside, then re-run.")
    try:
        after = tomllib.loads(new)
    except Exception:  # noqa: BLE001
        after = None
    if (after is None or key not in after
            or {k: v for k, v in after.items() if k != key} != before):
        sys.exit(f"{short(CODEX_CONFIG)} has a layout this script cannot safely add a "
                 f"line to. Nothing was changed; ask your assistant to add the line "
                 f"'{key} = {CODEX_DOC_VALUE}' at the top of that file, then re-run.")


def plan_codex_config() -> tuple:
    """(text on disk or None, text wanted), worked out before anything on the
    machine is changed."""
    raw = read_utf8(CODEX_CONFIG)
    new = ensure_top_level_key(raw or "", CODEX_DOC_KEY, CODEX_DOC_VALUE)
    if raw is None or new != raw:
        check_toml_insert(raw or "", new, CODEX_DOC_KEY)
    return raw, new


def prove_codex_guard(guard: Path, vault: Path) -> None:
    python = codex_python()

    def run(payload: dict) -> int:
        try:
            r = subprocess.run([python, str(guard)], input=json.dumps(payload),
                               capture_output=True, text=True, timeout=60)
        except (OSError, subprocess.SubprocessError):
            return -1
        return r.returncode
    blocked = run({"tool_name": "Bash", "tool_input": {"command": "rm -rf wiki/Something"}})
    passed = run({"tool_name": "Bash", "tool_input": {"command": "ls wiki"}})
    patch = "*** Begin Patch\n*** Delete File: wiki/x.md\n*** End Patch"
    patched = run({"tool_name": "apply_patch", "tool_input": {"command": patch},
                   "cwd": str(vault)})
    if blocked != 2 or passed != 0 or patched != 2:
        sys.exit(f"The guard did not behave as expected (delete test exit {blocked}, "
                 f"harmless test exit {passed}, file-editing delete test exit {patched}). "
                 "Nothing else was changed.")
    say("  guard proven: a delete command and a file-editing delete are refused, "
        "a harmless command passes")


def say_trust(trust_needed: bool) -> None:
    """The step only the owner can take, and the line the app and the updater
    look for. The machine-readable line is always the last thing printed."""
    if not trust_needed:
        say("The guard runs only while it is trusted in ChatGPT. To check: ChatGPT menu,")
        say("Settings, Hooks (under Coding), \"User config\". The hook whose command ends")
        say("bash-guard.py should show as trusted, with its switch on.")
        return
    say("One step is yours: ChatGPT will not run the guard until you trust it.")
    say("  1. Open the ChatGPT menu and choose Settings.")
    say("  2. Choose Hooks (under Coding).")
    say("  3. Open \"User config\".")
    say("  4. Press Trust beside the hook whose command ends bash-guard.py.")
    say("  5. Turn its switch on.")
    say("ChatGPT asks for this again whenever Moblee updates the guard.")
    say(TRUST_LINE)


def chatgpt_branch(vault: Path, hooks_plan: tuple, config_plan: tuple,
                   stamp: str, dry_run: bool) -> tuple:
    """Returns (trust_needed, exit code)."""
    data, raw = hooks_plan
    config_raw, config_new = config_plan
    trust_needed = False

    # 1. guard file
    say("Delete guard for ChatGPT")
    if dry_run:
        say(f"  would copy {GUARD_SRC.name} to {short(CODEX_GUARD_DST)}")
    else:
        CODEX_HOOKS_DIR.mkdir(parents=True, exist_ok=True)
        if CODEX_GUARD_DST.exists() and CODEX_GUARD_DST.read_bytes() == GUARD_SRC.read_bytes():
            say(f"  already installed at {short(CODEX_GUARD_DST)}")
        else:
            if CODEX_GUARD_DST.exists():
                b = backup(CODEX_GUARD_DST, stamp, CODEX_GUARD_BACKUP)
                say(f"  previous guard kept at {short(b)}")
            shutil.copy2(GUARD_SRC, CODEX_GUARD_DST)
            say(f"  installed {short(CODEX_GUARD_DST)}")
            trust_needed = True
        CODEX_GUARD_DST.chmod(CODEX_GUARD_DST.stat().st_mode
                              | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        prove_codex_guard(CODEX_GUARD_DST, vault)

    # 2. hook registration: only ever added at the end of the list
    say(f"Hook registration in {short(CODEX_HOOKS_JSON)}")
    if codex_entry_present(data.get("hooks", {}).get("PreToolUse", [])):
        say("  already registered; nothing to change")
    elif dry_run:
        say("  would add a PreToolUse hook on Bash and apply_patch, after any hooks already there")
    else:
        entry = codex_entry()
        expected = copy.deepcopy(data)
        expected.setdefault("hooks", {}).setdefault("PreToolUse", []).append(entry)
        new_text = None
        if raw is not None:
            try:
                candidate = append_codex_entry_text(raw, entry)
                if json.loads(candidate) == expected:
                    new_text = candidate
            except Exception:  # noqa: BLE001
                new_text = None
        if new_text is None:
            new_text = json.dumps(expected, indent=2) + "\n"
        b = backup(CODEX_HOOKS_JSON, stamp)
        if b:
            say(f"  previous hooks file kept at {short(b)}")
        write_text_checked(CODEX_HOOKS_JSON, new_text, expected)
        say("  registered after any hooks already there; none of them was moved or changed")
        trust_needed = True

    # 3. let ChatGPT read the whole instruction file
    say(f"Instruction file size limit in {short(CODEX_CONFIG)}")
    if config_raw is not None and config_new == config_raw:
        say(f"  {CODEX_DOC_KEY} is already set; nothing to change")
    elif dry_run:
        say(f"  would add {CODEX_DOC_KEY} = {CODEX_DOC_VALUE}")
    else:
        try:
            b = backup(CODEX_CONFIG, stamp)
            if b:
                say(f"  previous settings kept at {short(b)}")
            write_text_checked(CODEX_CONFIG, config_new)
        except OSError as e:
            say(f"  could not write {short(CODEX_CONFIG)} ({e}). The guard is in place; "
                "re-run to finish this step.")
            return trust_needed, 1
        say(f"  added {CODEX_DOC_KEY} = {CODEX_DOC_VALUE}; no other line was touched")
    return trust_needed, 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--assistant", help="claude, chatgpt or both; without it, the choice "
                                        "kept in ~/.config/moblee/assistant, else claude")
    a = ap.parse_args()
    assistant = read_assistant(a.assistant)
    wants_claude = assistant in ("claude", "both")
    wants_chatgpt = assistant in ("chatgpt", "both")
    vault = find_vault(a.vault)
    if wants_chatgpt:
        # ChatGPT reads AGENTS.md; the installer may lay it down before or after this step
        named = (vault / "CLAUDE.md").exists() or (vault / "AGENTS.md").exists()
        if not named or not (vault / "wiki").is_dir():
            sys.exit(f"{vault} does not look like a vault (no CLAUDE.md or AGENTS.md, or no wiki/).")
    elif not (vault / "CLAUDE.md").exists() or not (vault / "wiki").is_dir():
        sys.exit(f"{vault} does not look like a vault (no CLAUDE.md or wiki/).")
    stamp = time.strftime("%Y%m%d-%H%M%S")

    say(f"Vault: {short(vault)}")
    if wants_chatgpt:
        say(f"Assistant: {assistant}")

    # 0. read the settings first, so a file this script cannot merge into stops
    #    it before anything on the machine has changed
    settings = {}
    if wants_claude:
        settings = load_json(SETTINGS)
        check_hook_shape(settings)
    hooks_plan = config_plan = None
    if wants_chatgpt:
        hooks_plan = load_codex_hooks()
        config_plan = plan_codex_config()

    if wants_claude:
        claude_branch(vault, settings, stamp, a.dry_run)
    trust_needed, code = False, 0
    if wants_chatgpt:
        trust_needed, code = chatgpt_branch(vault, hooks_plan, config_plan, stamp, a.dry_run)

    if a.dry_run:
        say("")
        say("Dry run: nothing was changed.")
        return 0
    if wants_claude:
        say("")
        say("Safety layer in place. From now on, in this vault:")
        say("  - Claude cannot delete files, empty folders, move things out of the vault,")
        say("    rewrite git history or force-push, however the command is phrased. If")
        say("    something must go, Claude tells you what and you remove it yourself.")
        say("  - Routine work (reading, searching, editing inside the vault, committing)")
        say("    runs without permission prompts. Anything outside that still asks.")
    if wants_chatgpt:
        say("")
        if code == 0:
            say("Safety layer in place for ChatGPT. Once the guard is trusted, in this vault:")
            say("  - ChatGPT cannot delete files, empty folders, move things out of the vault,")
            say("    rewrite git history or force-push, by a command or with its file-editing")
            say("    tool. If something must go, ChatGPT tells you what and you remove it yourself.")
        say_trust(trust_needed)
    return code


def claude_branch(vault: Path, settings: dict, stamp: str, dry_run: bool) -> None:
    """Today's behaviour for Claude, step for step."""
    # 1. guard file
    say("Delete guard")
    if dry_run:
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
    elif dry_run:
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
    elif dry_run:
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


if __name__ == "__main__":
    sys.exit(main())
