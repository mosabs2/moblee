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
     reads the whole instruction file. The line goes in at the top of the
     file; no existing line is altered.

Where CODEX_HOME is set, that folder is used in place of ~/.codex, as ChatGPT
itself does. Before anything is changed the script stops, with exit code 1,
if config.toml already sets up hooks of its own ([hooks] tables) or turns
hooks off (hooks = false under [features]): Moblee does not change ChatGPT's
hook arrangement by itself. Each file is read again just before it is
written, and left alone if it changed in the meantime.

ChatGPT runs a new or changed hook only after the owner trusts it. When that
step is needed the last line printed is "@@moblee-trust-needed chatgpt", which
the app and the updater read; it is printed even when a later step fails.

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

# ChatGPT (its agent, Codex, keeps its settings under ~/.codex, or under
# CODEX_HOME when that is set)
CODEX_DEFAULT_DIR = Path.home() / ".codex"
_CODEX_HOME = os.environ.get("CODEX_HOME", "").strip()
CODEX_DIR = Path(_CODEX_HOME).expanduser().absolute() if _CODEX_HOME else CODEX_DEFAULT_DIR
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


def write_text_checked(path: Path, text: str, original: str | None, expected=None) -> None:
    """Write beside the real file, check the copy, then swap it in. `original`
    is the text this script read at the start (None for no file): the file is
    read again just before the swap and left alone if it no longer matches,
    so a change made meanwhile (by ChatGPT itself, say) is never lost. With
    `expected`, the copy must parse as JSON to exactly that. A file that is a
    link stays a link, and the file keeps its permissions."""
    real = Path(os.path.realpath(path))
    real.parent.mkdir(parents=True, exist_ok=True)
    tmp = real.with_suffix(real.suffix + ".moblee-tmp")
    tmp.write_bytes(text.encode("utf-8"))
    if tmp.read_bytes().decode("utf-8") != text:
        sys.exit(f"Refusing to write {short(path)}: the copy did not read back the same.")
    if expected is not None and json.loads(text) != expected:
        sys.exit(f"Refusing to write {short(path)}: the result is not what was intended.")
    if read_utf8(path) != original:
        sys.exit(f"{short(path)} changed while this script was working, so it was left "
                 "exactly as it now is. Re-run to finish.")
    if real.exists():
        shutil.copymode(real, tmp)
    os.replace(tmp, real)


_CODEX_PYTHON = None


def codex_python() -> str:
    """The Python that ChatGPT will start the guard with: the one that comes
    with the Mac when it really is a Python. Without Apple's command line
    tools /usr/bin/python3 is a stand-in that only offers to install them, and
    a guard started with it would never run. It is not started here to find
    out (that opens Apple's install window); xcode-select says whether the
    tools are there. Otherwise the Python running this script is used."""
    global _CODEX_PYTHON
    if _CODEX_PYTHON is None:
        stock = "/usr/bin/python3"
        usable = os.access(stock, os.X_OK)
        if usable and sys.platform == "darwin":
            running = os.path.realpath(sys.executable)
            if not running.startswith(("/usr/bin/", "/Library/Developer/",
                                       "/Applications/Xcode")):
                try:
                    r = subprocess.run(["/usr/bin/xcode-select", "-p"],
                                       capture_output=True, text=True, timeout=20)
                    usable = r.returncode == 0
                except (OSError, subprocess.SubprocessError):
                    usable = False
        _CODEX_PYTHON = stock if usable else sys.executable
    return _CODEX_PYTHON


def codex_guard_cmd() -> str:
    # The full path is written out. The hooks documentation never says that
    # $HOME is expanded in a hook command, and a guard that cannot be found
    # does not stop anything.
    return f"{shlex.quote(codex_python())} {shlex.quote(str(CODEX_GUARD_DST))}"


def codex_entry() -> dict:
    return {"matcher": CODEX_MATCHER,
            "hooks": [{"type": "command", "command": codex_guard_cmd(), "timeout": 10}]}


def codex_entry_present(pre: list) -> bool:
    marks = [str(CODEX_GUARD_DST)]
    if CODEX_DIR == CODEX_DEFAULT_DIR:
        marks.append(CODEX_GUARD_MARK)  # also the "$HOME/.codex/…" spelling
    for g in pre:
        if not isinstance(g, dict) or g.get("matcher") != CODEX_MATCHER:
            continue
        for h in g.get("hooks") or []:
            if isinstance(h, dict) and any(m in str(h.get("command", "")) for m in marks):
                return True
    return False


def plan_codex_hooks() -> tuple:
    """(settings object, text on disk or None, text wanted or None, settings
    wanted or None), worked out before anything on the machine is changed.
    The last two are None when the guard is already registered. The entry is
    added to the text as it stands; if that cannot be done the script stops
    rather than write the file out afresh, which could switch off hooks the
    owner has already trusted."""
    data, raw = load_codex_hooks()
    if codex_entry_present(data.get("hooks", {}).get("PreToolUse", [])):
        return data, raw, None, None
    entry = codex_entry()
    expected = copy.deepcopy(data)
    expected.setdefault("hooks", {}).setdefault("PreToolUse", []).append(entry)
    if raw is None:
        return data, raw, json.dumps(expected, indent=2) + "\n", expected
    try:
        candidate = append_codex_entry_text(raw, entry)
        good = json.loads(candidate) == expected
    except Exception:  # noqa: BLE001
        good = False
    if not good:
        sys.exit(f"{short(CODEX_HOOKS_JSON)} is laid out in a way this script cannot add "
                 "a hook to without writing the whole file out again, and that could "
                 "switch off hooks you have already trusted. Nothing was changed; ask "
                 "your assistant to add the guard's hook at the end of the PreToolUse "
                 "list by hand, then re-run.")
    return data, raw, candidate, expected


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
    unchanged, whatever its value. Otherwise the comment and the line go in at
    the very top of the file, after a byte-order mark if there is one. The top
    of a file is always outside every table and every value that spans lines,
    so the key cannot land inside one, whatever the rest of the file holds.
    Lines are only ever added; no existing line is altered."""
    bom = "﻿" if text.startswith("﻿") else ""
    body = text[len(bom):]
    cr = "\r" if "\r\n" in body else ""
    key_re = re.compile(r"""^\s*(?:%s|"%s"|'%s')\s*=""" % ((re.escape(key),) * 3))
    depth, ml = 0, None
    for line in body.split("\n"):
        if depth == 0 and ml is None:   # the line starts outside any value
            if line.lstrip().startswith("["):
                break                   # first [table]: the top level ends here
            if key_re.match(line):
                return text
        depth, ml = _toml_line_state(line, depth, ml)
    added = CODEX_DOC_COMMENT + cr + "\n" + f"{key} = {value_literal}" + cr + "\n"
    first = body.split("\n", 1)[0]
    if first.strip():
        added += cr + "\n"              # a blank line before what was the first line
    return bom + added + body


def _toml_clean_lines(text: str):
    """Each line of a TOML file that starts outside any value spanning lines."""
    depth, ml = 0, None
    for line in text.lstrip("﻿").split("\n"):
        if depth == 0 and ml is None:
            yield line
        depth, ml = _toml_line_state(line, depth, ml)


_TOML_HEADER_RE = re.compile(r"^\s*\[\[?\s*([^\]]*?)\s*\]")
_HOOKS_OFF_RE = re.compile(r"""^\s*["']?(?:codex_)?hooks["']?\s*=\s*false\b""")
_TOP_HOOKS_RE = re.compile(r"""^\s*["']?hooks["']?\s*[.=]""")
_TOP_FEATURES_OFF_RE = re.compile(
    r"""^\s*["']?features["']?\s*(?:\.\s*["']?(?:codex_)?hooks["']?\s*=\s*false\b"""
    r"""|=\s*\{.*\b(?:codex_)?hooks["']?\s*=\s*false\b)""")


def codex_config_findings(text: str) -> tuple:
    """(config.toml sets up hooks of its own, config.toml turns hooks off).
    Read line by line, and also with a TOML reader where this Python has one."""
    inline = off = False
    table = ""
    for line in _toml_clean_lines(text):
        m = _TOML_HEADER_RE.match(line)
        if m:
            table = m.group(1).replace('"', "").replace("'", "").replace(" ", "")
            if table == "hooks" or table.startswith("hooks."):
                inline = True
            continue
        if table == "" and _TOP_HOOKS_RE.match(line):
            inline = True
        if table == "" and _TOP_FEATURES_OFF_RE.match(line):
            off = True
        if table == "features" and _HOOKS_OFF_RE.match(line):
            off = True
    try:
        import tomllib
        data = tomllib.loads(text.lstrip("﻿"))
    except Exception:  # noqa: BLE001  (no reader on this Python, or not readable)
        data = {}
    if data.get("hooks"):
        inline = True
    feats = data.get("features")
    if isinstance(feats, dict) and (feats.get("hooks") is False
                                    or feats.get("codex_hooks") is False):
        off = True
    return inline, off


def check_codex_config(raw: str | None, registered: bool) -> None:
    """Stop, before anything is changed, where adding a hook would mean
    rearranging hooks ChatGPT already has, or where the guard could never run."""
    if not raw:
        return
    inline, off = codex_config_findings(raw)
    if off:
        sys.exit(f"{short(CODEX_CONFIG)} turns ChatGPT's hooks off (hooks = false under "
                 "[features]), so the guard would never run, and Moblee will not change "
                 "ChatGPT's hook arrangement by itself; nothing was changed.")
    if inline and not registered:
        sys.exit(f"{short(CODEX_CONFIG)} already sets up hooks of its own (a [hooks] "
                 "section), which ChatGPT would have to merge with a hooks.json file, and "
                 "Moblee will not change ChatGPT's hook arrangement by itself; nothing "
                 "was changed.")


def check_toml_insert(old: str, new: str, key: str) -> None:
    """Where this Python can read TOML (3.11 on), prove the new text is the old
    settings plus the one key, before anything is changed. Older Pythons
    cannot check and rely on ensure_top_level_key alone."""
    try:
        import tomllib
    except ImportError:
        return
    old, new = old.lstrip("﻿"), new.lstrip("﻿")
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


def plan_codex_config(raw: str | None) -> tuple:
    """(text on disk or None, text wanted), worked out before anything on the
    machine is changed. `raw` is config.toml as read, None for no file."""
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
    look for. The steps are the same five every time. The machine-readable
    line is printed only when trust is needed, and is then the last thing
    printed."""
    if trust_needed:
        say("One step is yours: ChatGPT will not run the guard until you trust it.")
    else:
        say("The guard runs only while it is trusted in ChatGPT. To check that it is, or to "
            "trust it if you have not yet:")
    # (v0.9) found on a real install: the Hooks page lists nothing until then
    say("First open your wiki folder in ChatGPT (File menu, Open Folder). Until a folder has "
        "been opened in ChatGPT, its Hooks page is empty and does not say why.")
    say("  1. Open the ChatGPT menu and choose Settings.")
    say("  2. Choose Hooks, under the heading Coding.")
    say("  3. Open \"User config\".")
    say("  4. Press Trust beside the hook that ends bash-guard.py.")
    say("  5. Turn its switch on.")
    say("If ChatGPT was open during this, quit it and open it again so that it reads "
        "the whole rules file.")
    say("You must do this again after any Moblee update that changes the guard. "
        "ChatGPT will not remind you.")
    if trust_needed:
        say(TRUST_LINE)


def chatgpt_branch(vault: Path, hooks_plan: tuple, config_plan: tuple,
                   stamp: str, dry_run: bool, progress: dict) -> int:
    """Returns the exit code. progress["trust"] is set the moment something
    is changed that the owner must trust, so the caller can still say so if a
    later step fails."""
    data, raw, hooks_new, hooks_expected = hooks_plan
    config_raw, config_new = config_plan

    # 1. guard file
    say("Delete guard for ChatGPT")
    python = codex_python()
    if python != "/usr/bin/python3":
        say(f"  the Python that comes with the Mac cannot be used here; ChatGPT will "
            f"start the guard with {python}")
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
            progress["trust"] = True
        CODEX_GUARD_DST.chmod(CODEX_GUARD_DST.stat().st_mode
                              | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        prove_codex_guard(CODEX_GUARD_DST, vault)

    # 2. hook registration: only ever added at the end of the list
    say(f"Hook registration in {short(CODEX_HOOKS_JSON)}")
    if hooks_new is None:
        say("  already registered; nothing to change")
    elif dry_run:
        say("  would add a PreToolUse hook on Bash and apply_patch, after any hooks already there")
    else:
        b = backup(CODEX_HOOKS_JSON, stamp)
        if b:
            say(f"  previous hooks file kept at {short(b)}")
        write_text_checked(CODEX_HOOKS_JSON, hooks_new, raw, hooks_expected)
        progress["trust"] = True
        if raw is None:
            say("  registered in a new hooks file")
        else:
            say("  registered after any hooks already there; none of them was moved or changed")

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
            write_text_checked(CODEX_CONFIG, config_new, config_raw)
        except OSError as e:
            say(f"  could not write {short(CODEX_CONFIG)} ({e}). The guard is in place; "
                "re-run to finish this step.")
            return 1
        say(f"  added {CODEX_DOC_KEY} = {CODEX_DOC_VALUE} at the top; no other line was touched")
    return 0


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
        if CODEX_DIR != CODEX_DEFAULT_DIR:
            say(f"ChatGPT settings folder: {short(CODEX_DIR)} (from CODEX_HOME, "
                f"in place of {short(CODEX_DEFAULT_DIR)})")

    # 0. read the settings first, so a file this script cannot merge into stops
    #    it before anything on the machine has changed
    settings = {}
    if wants_claude:
        settings = load_json(SETTINGS)
        check_hook_shape(settings)
    hooks_plan = config_plan = None
    if wants_chatgpt:
        hooks_plan = plan_codex_hooks()
        config_raw = read_utf8(CODEX_CONFIG)
        check_codex_config(config_raw, registered=hooks_plan[2] is None)
        config_plan = plan_codex_config(config_raw)

    if wants_claude:
        claude_branch(vault, settings, stamp, a.dry_run)
    elif GUARD_DST.exists():
        # The owner chose ChatGPT alone, but Claude on this Mac already runs a
        # Moblee guard from an earlier install. A guard left behind goes stale
        # and later refuses the pack's own newer tools, so its file is kept
        # level. Nothing else of Claude's is touched.
        keep_claude_guard_level(stamp, a.dry_run)
    progress, code = {"trust": False}, 0
    if wants_chatgpt:
        # Whatever stops a later step, the owner is still told when there is
        # something to trust: a guard that is registered but not trusted does
        # not run, and nothing else would say so.
        failure = None
        try:
            code = chatgpt_branch(vault, hooks_plan, config_plan, stamp, a.dry_run, progress)
        except SystemExit as e:
            failure = e.code if isinstance(e.code, str) else f"stopped (exit {e.code})"
        except Exception as e:  # noqa: BLE001
            failure = f"{type(e).__name__}: {e}"
        if failure is not None:
            print(f"The ChatGPT step did not finish: {failure}", file=sys.stderr, flush=True)
            if progress["trust"] and not a.dry_run:
                say("")
                say("Part of the ChatGPT step was done before it stopped.")
                say_trust(True)
            return 1
    trust_needed = progress["trust"]

    if a.dry_run:
        say("")
        say("Dry run: nothing was changed.")
        return 0
    if wants_claude:
        say("")
        say("Safety layer in place. From now on, in this vault:")
        say("  - Claude cannot delete files, empty folders, move things out of the vault,")
        say("    rewrite git history or force-push, in the forms it knows, including")
        say("    indirect ones. If something must go, Claude tells you what and you")
        say("    remove it yourself.")
        say("  - Routine work (reading, searching, editing inside the vault, committing)")
        say("    runs without permission prompts. Anything outside that still asks.")
    if wants_chatgpt:
        say("")
        if code == 0:
            say("Safety layer in place for ChatGPT. ChatGPT runs the guard only once you have")
            say("trusted it. Then prove it with the check-up's --prove-guard option. A guard")
            say("that crashes or takes too long lets the command through, so the written rule")
            say("in the wiki still matters. With the guard running, in this vault:")
            say("  - ChatGPT is refused when it tries to delete files, empty folders, move")
            say("    things out of the vault, rewrite git history or force-push, by a command")
            say("    or with its file-editing tool, in the forms the guard knows, including")
            say("    indirect ones. If something must go, ChatGPT tells you what and you")
            say("    remove it yourself.")
        say_trust(trust_needed)
    return code


def keep_claude_guard_level(stamp: str, dry_run: bool) -> None:
    """Refresh an existing ~/.claude guard file and nothing else of Claude's."""
    say("Delete guard already on this Mac for Claude")
    if GUARD_DST.read_bytes() == GUARD_SRC.read_bytes():
        say(f"  already this version at {short(GUARD_DST)}")
        return
    if dry_run:
        say(f"  would bring {short(GUARD_DST)} up to this version (the old copy kept)")
        return
    b = backup(GUARD_DST, stamp)
    say(f"  previous guard kept at {short(b)}")
    shutil.copy2(GUARD_SRC, GUARD_DST)
    GUARD_DST.chmod(GUARD_DST.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    prove_guard(GUARD_DST)
    say(f"  brought up to this version at {short(GUARD_DST)}")


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
