#!/usr/bin/env python3
"""
PreToolUse Bash guard, v4 — enforce the vault's "never-list" for real.

The Claude Code settings deny list is string-pattern based and cannot catch
indirect destruction (`find -exec rm`, `python3 -c "shutil.rmtree(...)"`,
`… | xargs rm`, `git rebase`, `mv wiki /tmp`). This hook inspects the
*resolved* Bash command and blocks the destructive class however it is
spelled:

  * file deletion   — rm / rmdir / unlink / trash / shred / srm / truncate /
                      ditto, find -delete or -exec <deleter>, rsync --delete,
                      tar --remove-files, zip -m / -d, diskutil erase, mkfs,
                      dd of=, and the interpreter primitives (rmtree, unlink,
                      fs.rm, File.delete, removeItem, do shell script …) in
                      -c / -e bodies, heredocs, piped code and script files
  * clobber         — truncating `>` redirects, tee, cp /dev/null and
                      mv/cp over an existing file; mv/cp of vault material to
                      a destination outside the vault or into /tmp, ~/.Trash,
                      /dev/null or /Volumes
  * history rewrite — git reset --hard/--merge/--keep, clean, rebase,
                      filter-branch, stash, restore, checkout of paths,
                      commit --amend, reflog expire, gc --prune, force-push
                      and branch/tag deletion

What it deliberately lets through:

  * deletes of throwaway files: rm / rmdir / unlink (and os.remove,
    os.unlink, os.rmdir, rmtree on a literal path) when EVERY target resolves
    (variables from the same command line, then the environment, then
    realpath so a symlink cannot point back in) to a path outside the vault
    and strictly under /tmp, /private/tmp, /var/tmp, $TMPDIR, ~/.cache,
    ~/Library/Caches or ~/.config/moblee/logs. A target that cannot be
    resolved (unexpanded variable, glob, substitution, stdin via xargs)
    still blocks.
  * mv / cp whose sources are all outside the vault (`cp ~/.zshrc
    ~/.zshrc.bak`), subject only to the overwrite check.
  * the pack's own tooling, recognised by SHA-256 (KNOWN_SAFE_SHA256 below,
    maintained by safety/release-hashes.py): a scanned file whose hash is
    listed skips the file scan; the command line around it is still scanned.

Script files are scanned language-aware: language from the extension, else
the shebang, else the invoking interpreter, else "unknown" (everything).
Shell scripts get the shell-segment scan only (plus any inline interpreter
bodies with their own keyword set); python/perl/ruby/node/php/swift/
AppleScript get their own keyword subset; comments and docstrings are
stripped first.

Design contract:
  * FAIL CLOSED on a matched pattern: exit 2, one-paragraph reason on stderr.
  * FAIL OPEN only on a malformed hook payload (bad JSON, unknown shape):
    exit 0, allow. Inside the scan every rule is wrapped individually, so a
    bug in one rule skips that rule rather than the whole guard, and a bug
    in the framework itself still exits 0 so Claude Code can never freeze.
  * stdlib only; Python 3.9 (stock macOS); well under 100 ms per call.

Hook payload: {"tool_name": "Bash", "tool_input": {"command": "…"}, "cwd": "…"}
(cwd may be absent — the vault-relative rules then degrade to name checks).

Per-machine: lives in ~/.claude/hooks/ on the Mac that runs Claude Code
against the vault, wired in ~/.claude/settings.json as a PreToolUse hook
matching Bash by safety/install-safety.py. Part of Moblee from v0.5
(September 2026); ported from the maintainer's vault. v4 (16 September 2026)
followed an adversarial review of v3; safety/test-guard.py is the suite.
"""
import hashlib
import json
import os
import re
import shlex
import sys
import unicodedata

VERSION = "v4"
MAX_DEPTH = 6
MAX_FILE_BYTES = 512 * 1024
MAX_HASH_BYTES = 4 * 1024 * 1024
MAX_FILES_PER_CALL = 6

# --- KNOWN_SAFE begin ---
KNOWN_SAFE_SHA256 = {
    "09e53a07cc802efbc4e39781bed40c5fdadca619e4e3760fd79c4fa1b05edca1": "dashboard/server.py",
    "c98790741c58336bed68ec4c0c1a40566ac25dacc77331e4c4da591d083980a3": "safety/install-safety.py",
    "240bfbf6d74ce37085d1c20718f82fbeb1cb32e649dc11e0885064320ebf8ab6": "safety/test-guard.py",
    "3e314ed6bde5799b1f32c190a2a4996eb5f52107b22f9fc7a8c1a626213983dd": "scripts/add-identity.py",
    "749ed9603f05e1a633f9586383e86777289fb0eb78b8b7bd9c7e2e0706c6672d": "scripts/cadence/run-weekly-lint.sh",
    "ccd320d41251a54c6ec367513de80a8ea2dcf2bdc1b0f47943b4adc26a07c7cb": "scripts/hooks/post-commit",
    "42bb3ae68fb171ff5670ac7e1fa8ec3e49bfc1e138c8727ee497158ab1c12c8e": "scripts/hooks/pre-commit",
    "e6526d9d84ff88e7c3c581064c67fbcd71c94ffeaf69b439e48b7413f40148ba": "scripts/install-schedule.sh",
    "b0cd60f9e9604b44ae1245e952e1ff0a7a7df31c2aafbe7f61d01c2f02af8736": "scripts/install-skills.sh",
    "3cf98b8394dcfa7a26a2fbf616c0dc9301f115c84ae3cf871a54ae282931036e": "scripts/install.sh",
    "a7f27a9bb6689a2b1da759b59742330f73009cdf634d74b8d2066edcd9ed9622": "scripts/lint-v2.py",
    "3bd00f93bc66ff9b2faa48c98c73eca4189344f591bf0156a6cc724cb8ed85a5": "scripts/log-append.py",
    "6a0e526b3e26bc35ede1c822dd1c3757aab5d68b01a056df6bcea70ec2cd7018": "scripts/patch-claude-md.py",
    "41bd8e860d52babfc79a0d1b023f83f5f109eece055907a848e08a9bce6bbe86": "scripts/seed-memory.py",
    "06633feefaa632d1acff20c89b109a9784cf0bce5aac8881fd2329b90c3eba8c": "scripts/update.sh",
    "f04b1d65016edfa8a53d2275871ceeb6c6a68283d11dd2480e670598dd616447": "scripts/vault-gate.py",
    "9bbb913618cbcd856b241df4e2372e89765024cbfdca15f86547d1b9368086d1": "scripts/vault-orient-preflight.sh",
    "364f1d41fe71489eeb4096b7fc9c6132c7212f7ae6c5ee05dad9c59bef09ce57": "scripts/vault.sh",
    "80e45b151dedc1149022d87d32cf4bda9ecb087110ff05930c08606631e22ef1": "scripts/wiki-galaxy/build.py",
    "c6f8b5cb80264cf421df250ceb8f0c6fea1ec183ac7207ae7af7e485664d91f3": "skills/wiki-to-pdf/render.py",
    "20c7d895e7d6dda0b2a68b2cc2ee5122575f084d2181aad03747b82db44bd39f": "voice/install-voice.py",
}
# --- KNOWN_SAFE end ---

SHELLS = {"sh", "bash", "zsh", "ksh", "dash", "fish"}
PYTHONS = {"python", "python3", "python2", "pypy", "pypy3"}
# interpreter → flags whose next argument is an inline program body
E_FLAGS = {
    "perl": ("e", "E"),
    "ruby": ("e",),
    "node": ("e", "p"),
    "nodejs": ("e", "p"),
    "php": ("r",),
    "osascript": ("e",),
    "swift": ("e",),
}
AWKS = {"awk", "gawk", "nawk", "mawk"}
OTHER_INTERP = {"deno", "bun", "lua", "tclsh", "expect"}
DELETERS = {"rm", "rmdir", "unlink"}
HARD_DELETERS = {"trash", "truncate", "shred", "srm", "ditto", "rimraf"}
CONTENT_DIRS = ("wiki", "raw", "Clippings", "Daily Notes")
CONTENT_FILES = ("CLAUDE.md", "VERSION")
ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
VAR_HEAD_RE = re.compile(r"^\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?$")
VAR_REF_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)")
UNRESOLVABLE_RE = re.compile(r"[*?\[`]|\$\(")
SHELL_KEYWORDS = {"!", "{", "}", "then", "do", "else", "elif", "if", "while",
                  "until"}
REDIR_OPS = {">", ">>", ">|", "<", "<<", "<<<", "&>", "&>>", ">&", "<&", "<>"}
TRUNC_OPS = {">", ">|", "&>", ">&"}
PUNCT = set("();<>|&")
ESCAPED = {"\\;": " __SEMI__ ", "\\(": " __LP__ ", "\\)": " __RP__ "}
FIND_TERMINATORS = {";", "+", "__SEMI__"}
SUDO_ARG = {"-u", "-g", "-p", "-C", "-D", "-h", "-r", "-t", "-U", "-T",
            "--user", "--group", "--prompt", "--host", "--role", "--type",
            "--other-user", "--chdir", "--close-from"}
SSH_ARG_OPTS = {"-o", "-p", "-l", "-i", "-F", "-J", "-W", "-b", "-c", "-D",
                "-E", "-e", "-L", "-m", "-O", "-Q", "-R", "-S", "-w", "-B"}
GIT_GLOBAL_ARG = {"-C", "-c", "--git-dir", "--work-tree", "--namespace",
                  "--exec-path", "--super-prefix", "--config-env",
                  "--list-cmds"}

# ---------------------------------------------------------------- languages
# Deletion / clobber / shell-out primitives per language. Applied
# case-insensitively to -c / -e bodies, heredoc bodies, piped code and
# scanned script files — never to the plain arguments of a script invocation.
_GETATTR_RE = re.compile(r"getattr\(\s*(os|shutil|pathlib)\b")
_OPEN_W_RE = re.compile(r"open\([^()]*,\s*(?:mode\s*=\s*)?['\"]w[bt+]*['\"]")
# In a scanned file, open() in a truncating mode counts only when the path
# literal names a vault content location (a script writing its own report to
# outputs/ or a temp file is not a clobber), mirroring the redirect rule.
_OPEN_W_CONTENT_RE = re.compile(
    r"open\(\s*(['\"])[^'\"]*(?:wiki/|raw/|clippings/|daily notes/"
    r"|claude\.md|version)[^'\"]*\1\s*,\s*(?:mode\s*=\s*)?['\"]w[bt+]*['\"]")
_WRITEFILESYNC_RE = re.compile(r"writefilesync\([^()]*,\s*(\"\"|'')")

LANGS = {
    "python": {
        "del": ("rmtree", "os.remove", "os.unlink", "os.rmdir", "removedirs",
                "shutil.rm", "shutil.move(", "os.replace(", "os.truncate(",
                ".truncate(", "unlink", "send2trash", "__dict__[",
                "import_module(", "write_text(\"\")", "write_text('')"),
        "shellout": ("os.system", "subprocess.", "os.popen", "system(", "exec("),
        "res_body": (_GETATTR_RE, _OPEN_W_RE),
        "res_file": (_GETATTR_RE, _OPEN_W_CONTENT_RE),
        "backticks": False,
    },
    "perl": {
        "del": ("unlink", "rmtree", "remove_tree", "truncate("),
        "shellout": ("system(", "exec \"", "exec '", "exec("),
        "res_body": (), "res_file": (), "backticks": True,
    },
    "ruby": {
        "del": ("file.delete", "fileutils.rm", "unlink", "rm_rf", "rm_r(",
                "remove_entry", ".truncate("),
        "shellout": ("system(", "exec \"", "exec '", "exec(", "spawn("),
        "res_body": (), "res_file": (), "backticks": True,
    },
    "node": {
        "del": ("fs.rm", "rmsync", "rmdirsync", "rimraf", "unlink", ".rm(",
                "truncatesync", ".truncate("),
        "shellout": ("child_process", "execsync", "exec(", "spawnsync"),
        "res_body": (_WRITEFILESYNC_RE,), "res_file": (_WRITEFILESYNC_RE,),
        "backticks": True,
    },
    "php": {
        "del": ("unlink", "rmdir(", "ftruncate"),
        "shellout": ("system(", "exec(", "shell_exec", "passthru", "popen(",
                     "proc_open"),
        "res_body": (), "res_file": (), "backticks": True,
    },
    "swift": {
        "del": ("removeitem", "trashitem", "truncate("),
        "shellout": ("process(", "system(", "posix_spawn"),
        "res_body": (), "res_file": (), "backticks": False,
    },
    "awk": {
        "del": (), "shellout": ("system(",),
        "res_body": (), "res_file": (), "backticks": False,
    },
    "applescript": {
        "del": ("do shell script", "to trash", "delete folder", "delete file"),
        "shellout": (), "res_body": (), "res_file": (), "backticks": False,
    },
}
LANGS["unknown"] = {
    "del": tuple(k for spec in LANGS.values() for k in spec["del"]),
    "shellout": tuple(k for spec in LANGS.values() for k in spec["shellout"]),
    "res_body": (_GETATTR_RE, _OPEN_W_RE, _WRITEFILESYNC_RE),
    "res_file": (_GETATTR_RE, _OPEN_W_CONTENT_RE, _WRITEFILESYNC_RE),
    "backticks": True,
}
LANG_ALIAS = {"osascript": "applescript", "nodejs": "node", "python3": "python",
              "python2": "python", "pypy": "python", "pypy3": "python",
              "gawk": "awk", "nawk": "awk", "mawk": "awk", "sh": "shell",
              "bash": "shell", "zsh": "shell", "ksh": "shell", "dash": "shell",
              "fish": "shell", "source": "shell", ".": "shell"}
EXT_LANG = {".sh": "shell", ".bash": "shell", ".zsh": "shell", ".ksh": "shell",
            ".command": "shell", ".py": "python", ".pyw": "python",
            ".pl": "perl", ".pm": "perl", ".rb": "ruby", ".js": "node",
            ".mjs": "node", ".cjs": "node", ".ts": "node", ".php": "php",
            ".swift": "swift", ".scpt": "applescript",
            ".applescript": "applescript", ".awk": "awk"}
SHEBANG_LANG = (("python", "python"), ("perl", "perl"), ("ruby", "ruby"),
                ("node", "node"), ("php", "php"), ("swift", "swift"),
                ("osascript", "applescript"), ("awk", "awk"),
                ("bash", "shell"), ("zsh", "shell"), ("ksh", "shell"),
                ("dash", "shell"), ("/sh", "shell"), ("env sh", "shell"))
# For scanned FILES, a shell-out keyword counts only if the file also names
# a deleter somewhere (subprocess.run(["git", "rm", …]) et al.); a script
# that merely shells out to `date` or `git status` is not destructive.
FILE_DELETER_RE = re.compile(r"(?<![\w./-])(rm|rmdir|unlink|shred|srm|trash|"
                             r"rmtree|--force|--hard|rebase|filter-branch)"
                             r"(?![\w-])", re.I)
# Comments and docstrings cannot execute; strip them before scanning a file.
_TRIPLE_RE = re.compile(r"(\"\"\"|''')(?:.*?)\1", re.S)
_HASH_COMMENT_RE = re.compile(r"^[ \t]*#.*$", re.M)
_SLASH_COMMENT_RE = re.compile(r"^[ \t]*//.*$", re.M)
_DASH_COMMENT_RE = re.compile(r"^[ \t]*--.*$", re.M)
# os.remove("literal") and friends: dropped from the body when the literal
# resolves to a throwaway path, so a temp-file cleanup does not trip.
PY_DEL_CALL_RE = re.compile(
    r"(?:os\.remove|os\.unlink|os\.rmdir|(?:shutil\.)?rmtree)\(\s*"
    r"(?:path\s*=\s*)?[rR]?(['\"])([^'\"]*)\1\s*[,)]")

# ---------------------------------------------------------------- state
STATE = {"cwd": None, "vault": None, "files": 0}


def _safe(fn, *args, **kw):
    """Run one rule; an exception inside it skips that rule only."""
    try:
        return fn(*args, **kw)
    except Exception:
        return None


# ---------------------------------------------------------------- paths
def find_vault(cwd):
    if not cwd:
        return None
    p = os.path.abspath(cwd)
    git_root = None
    while True:
        if (os.path.isfile(os.path.join(p, "CLAUDE.md"))
                and os.path.isdir(os.path.join(p, "wiki"))):
            return p
        if git_root is None and os.path.exists(os.path.join(p, ".git")):
            git_root = p
        parent = os.path.dirname(p)
        if parent == p:
            break
        p = parent
    return git_root or os.path.abspath(cwd)


def expand(path, assigns=None):
    if assigns:
        def rep(m):
            name = m.group(1) or m.group(2)
            return assigns.get(name, m.group(0))
        path = VAR_REF_RE.sub(rep, path)
    path = os.path.expandvars(os.path.expanduser(path))
    if "$" in path:
        return None
    return path


def resolve(path, assigns=None):
    """Absolute, normalised path (None if it cannot be resolved)."""
    p = expand(path, assigns)
    if p is None:
        return None
    if not os.path.isabs(p):
        if not STATE["cwd"]:
            return None
        p = os.path.join(STATE["cwd"], p)
    return os.path.normpath(p)


def inside(path, root):
    """True if path is root or below it, comparing realpaths (so the
    /var/folders vs /private/var/folders alias does not matter). Relative
    paths are never inside anything: resolving them against the hook
    process's own cwd would be meaningless."""
    if not path or not root or not os.path.isabs(path) or not os.path.isabs(root):
        return False
    rp = os.path.realpath(path)
    rr = os.path.realpath(root)
    return rp == rr or rp.startswith(rr + os.sep)


def tmp_roots():
    roots = ["/tmp", "/private/tmp", "/var/tmp", "/private/var/tmp", "/dev",
             os.path.expanduser("~/.Trash")]
    t = os.environ.get("TMPDIR")
    if t:
        roots.append(t.rstrip("/"))
    return roots


def throwaway_roots():
    roots = ["/tmp", "/private/tmp", "/var/tmp", "/private/var/tmp",
             os.path.expanduser("~/.cache"),
             os.path.expanduser("~/Library/Caches"),
             os.path.expanduser("~/.config/moblee/logs")]
    t = os.environ.get("TMPDIR")
    if t:
        roots.append(t.rstrip("/"))
    return [os.path.realpath(r) for r in roots]


def throwaway_target(target, assigns=None, allow_root=False):
    """True iff target resolves (assignments, env, realpath) to a path outside
    the vault and strictly under a throwaway root (or equal to one when
    allow_root, for find start paths)."""
    if not target or UNRESOLVABLE_RE.search(target):
        return False
    p = resolve(target, assigns)
    if p is None:
        return False
    real = os.path.realpath(p)
    if STATE["vault"] and inside(real, STATE["vault"]):
        return False
    for root in throwaway_roots():
        if real.startswith(root + os.sep) or (allow_root and real == root):
            return True
    return False


def forbidden_destination(dest_raw):
    """Reason string if the destination is a tmp / Trash / dev-null / Volumes sink.
    A destination inside the vault root is never a sink, wherever the vault
    itself lives (/tmp, /var/folders, /Volumes, ~/.cache …)."""
    text = expand(dest_raw) or dest_raw
    text = os.path.normpath(text) if text else text
    resolved = resolve(dest_raw)
    if resolved and STATE["vault"] and inside(resolved, STATE["vault"]):
        return None
    cands = [c for c in (text, resolved) if c and os.path.isabs(c)]
    for root in tmp_roots():
        for c in cands:
            if c == root or c.startswith(root + os.sep) or inside(c, root):
                return "goes to a temporary or trash location (%s)" % dest_raw
    if resolved and resolved.startswith("/Volumes/") and not inside(resolved, STATE["vault"]):
        return "goes to an external volume (%s)" % dest_raw
    if text.startswith("/Volumes/") and not STATE["vault"]:
        return "goes to an external volume (%s)" % dest_raw
    return None


def source_touches_vault(sources):
    """True if any source is inside the vault or cannot be resolved."""
    vault = STATE["vault"]
    if not vault or not sources:
        return True
    for s in sources:
        base = re.split(r"[*?\[]", s)[0]
        if base != s:
            base = os.path.dirname(base) or "."
        r = resolve(base or ".")
        if r is None or inside(r, vault):
            return True
    return False


def is_content_path(path_raw):
    """True if path is (or names) an existing regular file under a content location."""
    resolved = resolve(path_raw)
    vault = STATE["vault"]
    if vault and resolved:
        if not os.path.isfile(resolved):
            return False
        for d in CONTENT_DIRS:
            if inside(resolved, os.path.join(vault, d)):
                return True
        for f in CONTENT_FILES:
            if os.path.realpath(resolved) == os.path.realpath(os.path.join(vault, f)):
                return True
        return False
    # No cwd: fall back to a name check on the relative spelling.
    text = os.path.normpath(expand(path_raw) or path_raw).lstrip("./")
    for d in CONTENT_DIRS:
        if text.startswith(d + "/") or ("/" + d + "/") in text:
            return True
    return os.path.basename(text) in CONTENT_FILES


# ---------------------------------------------------------------- tokens
def norm_head(t):
    t = unicodedata.normalize("NFKC", t)
    return os.path.basename(t)


def shlex_tokens(text):
    for k, v in ESCAPED.items():
        text = text.replace(k, v)
    lex = shlex.shlex(text, posix=True, punctuation_chars=True)
    lex.whitespace_split = True
    return list(lex)


def fallback_tokens(text):
    out = []
    for w in text.split():
        if w and all(ch in PUNCT for ch in w):
            out.append(w)
        else:
            out.append(w.strip("'\""))
    return out


class Seg(object):
    __slots__ = ("toks", "redirs", "piped_in", "line")

    def __init__(self):
        self.toks = []
        self.redirs = []
        self.piped_in = False
        self.line = None


class Line(object):
    __slots__ = ("text", "bodies", "segs")

    def __init__(self, text, bodies):
        self.text = text
        self.bodies = bodies
        self.segs = []


def segment(tokens, line):
    segs, cur = [], Seg()
    cur.line = line
    i, n = 0, len(tokens)
    while i < n:
        t = tokens[i]
        if t and all(ch in PUNCT for ch in t):
            if t in REDIR_OPS:
                if cur.toks and cur.toks[-1].isdigit():
                    cur.toks.pop()
                target = tokens[i + 1] if i + 1 < n else ""
                cur.redirs.append((t, target))
                i += 2
                continue
            # separator (; | || && & ( ) ;; <( >( (( )) and any mix)
            segs.append(cur)
            cur = Seg()
            cur.line = line
            cur.piped_in = t in ("|", "|&") or t.endswith("|")
            i += 1
            continue
        cur.toks.append(t)
        i += 1
    segs.append(cur)
    return [s for s in segs if s.toks or s.redirs]


HEREDOC_RE = re.compile(r"(?<![<\w])<<(?!<)-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")


def strip_heredocs(text):
    """Remove heredoc bodies; return (text_without_bodies, {phys_line: [bodies]})."""
    lines = text.split("\n")
    out, bodies = [], {}
    i = 0
    while i < len(lines):
        line = lines[i]
        delims = [m.group(2) for m in HEREDOC_RE.finditer(line)]
        out.append(line)
        i += 1
        for d in delims:
            body = []
            while i < len(lines) and lines[i].strip("\t ") != d:
                body.append(lines[i])
                i += 1
            i += 1
            bodies.setdefault(len(out) - 1, []).append("\n".join(body))
    return "\n".join(out), bodies


def logical_lines(text):
    """Split on unquoted newlines (join backslash continuations).
    Returns list of (line_text, [physical line indices])."""
    out, cur, q, esc = [], [], None, False
    ln, start = 0, 0
    for ch in text:
        if esc:
            esc = False
            if ch == "\n":
                if cur and cur[-1] == "\\":
                    cur.pop()
                ln += 1
                continue
            cur.append(ch)
            continue
        if ch == "\\" and q != "'":
            esc = True
            cur.append(ch)
            continue
        if q:
            if ch == q:
                q = None
            if ch == "\n":
                ln += 1
            cur.append(ch)
            continue
        if ch in "'\"":
            q = ch
            cur.append(ch)
            continue
        if ch == "\n":
            out.append(("".join(cur), list(range(start, ln + 1))))
            cur = []
            ln += 1
            start = ln
            continue
        cur.append(ch)
    out.append(("".join(cur), list(range(start, ln + 1))))
    return out


def parse(command):
    """Full parse of a command string into Line objects with Segs."""
    text = command.replace("\r\n", "\n").replace("\r", "\n")
    text, bodies = strip_heredocs(text)
    lines = []
    for ltext, phys in logical_lines(text):
        if not ltext.strip():
            continue
        lb = []
        for p in phys:
            lb.extend(bodies.get(p, []))
        line = Line(ltext, lb)
        try:
            toks = shlex_tokens(ltext)
            line.segs = segment(toks, line)
        except ValueError:
            # Unbalanced quoting: lex each physical line coarsely instead.
            for pl in ltext.split("\n"):
                if pl.strip():
                    line.segs.extend(segment(fallback_tokens(pl), line))
        lines.append(line)
    return lines


def assignments(lines):
    """NAME → value for every NAME=value token in the command."""
    out = {}
    for line in lines:
        for seg in line.segs:
            for t in seg.toks:
                if ASSIGN_RE.match(t):
                    k, v = t.split("=", 1)
                    out[k] = v
    return out


def blank_single_quotes(text):
    """Same-length text with single-quoted spans blanked (they do not execute)."""
    out, q, esc = [], None, False
    for ch in text:
        if esc:
            esc = False
            out.append(ch)
            continue
        if ch == "\\" and q != "'":
            esc = True
            out.append(ch)
            continue
        if q == "'":
            if ch == "'":
                q = None
                out.append(ch)
            else:
                out.append(" ")
            continue
        if q == '"':
            if ch == '"':
                q = None
            out.append(ch)
            continue
        if ch in "'\"":
            q = ch
        out.append(ch)
    return "".join(out)


def substitutions(text):
    """Inner text of every $(...) and `...` outside single quotes."""
    view = blank_single_quotes(text)
    found = []
    i, n = 0, len(view)
    while i < n:
        if view.startswith("$(", i):
            depth, j = 0, i + 1
            while j < n:
                if view[j] == "(":
                    depth += 1
                elif view[j] == ")":
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            found.append(text[i + 2:j])
            i = j + 1
            continue
        if view[i] == "`":
            j = view.find("`", i + 1)
            if j == -1:
                break
            found.append(text[i + 1:j])
            i = j + 1
            continue
        i += 1
    return [f for f in found if f.strip()]


QUOTED_RE = re.compile(r"'([^']*)'|\"((?:[^\"\\]|\\.)*)\"")


def quoted_literals(text):
    out = []
    for m in QUOTED_RE.finditer(text):
        s = m.group(1) if m.group(1) is not None else m.group(2)
        if s and s.strip():
            out.append(s)
    return out


# ---------------------------------------------------------------- keyword scan
def drop_throwaway_py_calls(body, assigns):
    def rep(m):
        return " " if throwaway_target(m.group(2), assigns) else m.group(0)
    return PY_DEL_CALL_RE.sub(rep, body)


def keyword_hit(body, lang=None, is_file=False, assigns=None):
    lang = LANG_ALIAS.get(lang, lang) or "unknown"
    if lang == "shell":
        return None
    spec = LANGS.get(lang, LANGS["unknown"])
    if lang in ("python", "unknown"):
        body = drop_throwaway_py_calls(body, assigns)
    low = body.lower()
    for k in spec["del"]:
        if k in low:
            return k
    for rx in (spec["res_file"] if is_file else spec["res_body"]):
        m = rx.search(low)
        if m:
            return m.group(0)[:40]
    for k in spec["shellout"]:
        if k in low:
            if is_file and not FILE_DELETER_RE.search(body):
                continue
            return k
    if spec["backticks"] and "`" in body:
        return "backtick command"
    return None


# ---------------------------------------------------------------- script files
def self_bytes():
    """The running guard's own source, so it never blocks itself: the file
    contains every keyword it looks for and cannot carry its own hash."""
    if "self" not in STATE:
        try:
            with open(os.path.abspath(__file__), "rb") as fh:
                STATE["self"] = fh.read()
        except OSError:
            STATE["self"] = None
    return STATE["self"]


def file_language(path, content, invoker):
    ext = os.path.splitext(path)[1].lower()
    if ext in EXT_LANG:
        return EXT_LANG[ext]
    first = content.split("\n", 1)[0]
    if first.startswith("#!"):
        for key, lang in SHEBANG_LANG:
            if key in first:
                return lang
    inv = LANG_ALIAS.get(invoker, invoker)
    if inv == "shell" or inv in LANGS:
        return inv
    return "unknown"


def strip_comments(content, lang):
    if lang == "python":
        content = _TRIPLE_RE.sub("", content)
    if lang in ("python", "shell", "awk", "perl", "ruby", "unknown"):
        content = _HASH_COMMENT_RE.sub("", content)
    if lang in ("node", "php", "swift"):
        content = _SLASH_COMMENT_RE.sub("", content)
    if lang == "applescript":
        content = _DASH_COMMENT_RE.sub("", content)
    return content


def scan_file(path_raw, invoker, depth):
    if STATE["files"] >= MAX_FILES_PER_CALL:
        return None
    p = resolve(path_raw)
    if p is None or not os.path.isfile(p):
        return None
    STATE["files"] += 1
    try:
        size = os.path.getsize(p)
        with open(p, "rb") as fh:
            data = fh.read(min(size, MAX_HASH_BYTES) if size <= MAX_HASH_BYTES else MAX_FILE_BYTES)
    except OSError:
        return None
    if size <= MAX_HASH_BYTES and hashlib.sha256(data).hexdigest() in KNOWN_SAFE_SHA256:
        return None  # known pack tooling at its released hash
    if data == self_bytes():
        return None  # the guard itself (or a byte-identical copy anywhere)
    content = data[:MAX_FILE_BYTES].decode("utf-8", "replace")
    lang = file_language(p, content, invoker)
    content = strip_comments(content, lang)
    if lang != "shell":
        k = _safe(keyword_hit, content, lang, True)
        if k:
            return "script file %s (%s) contains a deletion/clobber primitive (%s)" % (
                path_raw, lang, k)
    if lang in ("shell", "unknown"):
        r = _safe(scan_command, content, depth + 1)
        if r:
            return "script file %s: %s" % (path_raw, r)
    return None


def scan_code_text(text, lang, depth):
    """Code arriving on stdin (pipe, <, <<, heredoc): scan the text as code."""
    k = _safe(keyword_hit, text, lang)
    if k:
        return "piped code contains %s" % k
    r = _safe(scan_command, text, depth + 1)
    if r:
        return "piped code: %s" % r
    return None


def scan_stdin_code(seg, lang, depth):
    """Shell/interpreter with no script and no -c body, reading code from stdin."""
    line = seg.line
    for body in (line.bodies if line else []):
        r = scan_code_text(body, lang, depth)
        if r:
            return "heredoc " + r
    for op, target in seg.redirs:
        if op == "<":
            r = scan_file(target, lang, depth)
            if r:
                return r
        elif op == "<<<":
            r = scan_code_text(target, lang, depth)
            if r:
                return r
    if seg.piped_in and line:
        k = _safe(keyword_hit, line.text, lang)
        if k:
            return "code piped into %s contains %s" % (lang or "a shell", k)
        for lit in quoted_literals(line.text):
            r = _safe(scan_command, lit, depth + 1)
            if r:
                return "code piped into %s: %s" % (lang or "a shell", r)
        for other in line.segs:
            if other is seg or not other.toks:
                continue
            r = _safe(scan_command, " ".join(other.toks[1:]), depth + 1)
            if r:
                return "code piped into %s: %s" % (lang or "a shell", r)
    return None


# ---------------------------------------------------------------- wrappers
def peel(toks, assigns, depth=0):
    """(basename-head, original head, rest) after peeling wrappers and keywords."""
    i, n = 0, len(toks)
    while i < n:
        t = toks[i]
        if t in SHELL_KEYWORDS or ASSIGN_RE.match(t):
            i += 1
            continue
        b = norm_head(t)
        if b in ("sudo", "doas"):
            i += 1
            while i < n and toks[i].startswith("-"):
                if toks[i] == "--":
                    i += 1
                    break
                i += 2 if toks[i] in SUDO_ARG else 1
            continue
        if b == "env":
            i += 1
            while i < n:
                t2 = toks[i]
                if ASSIGN_RE.match(t2):
                    i += 1
                    continue
                if t2 == "--":
                    i += 1
                    break
                if t2.startswith("-"):
                    if t2 in ("-u", "-C", "-P", "--unset", "--chdir"):
                        i += 2
                        continue
                    if t2 in ("-S", "--split-string") and i + 1 < n:
                        try:
                            inner = shlex.split(toks[i + 1])
                        except ValueError:
                            inner = toks[i + 1].split()
                        return peel(inner + toks[i + 2:], assigns, depth + 1)
                    if t2.startswith("-S") or t2.startswith("--split-string="):
                        val = t2[2:] if t2.startswith("-S") else t2.split("=", 1)[1]
                        try:
                            inner = shlex.split(val)
                        except ValueError:
                            inner = val.split()
                        return peel(inner + toks[i + 1:], assigns, depth + 1)
                    i += 1
                    continue
                break
            continue
        if b == "nice":
            i += 1
            while i < n and toks[i].startswith("-"):
                i += 2 if toks[i] in ("-n", "--adjustment") else 1
            continue
        if b == "command":
            i += 1
            if i < n and toks[i] in ("-v", "-V"):
                return "command", t, toks[i:]
            while i < n and toks[i].startswith("-"):
                i += 1
            continue
        if b in ("time", "nohup", "builtin", "exec", "caffeinate"):
            i += 1
            while i < n and toks[i].startswith("-"):
                if b == "exec" and toks[i] == "-a":
                    i += 2
                elif b == "caffeinate" and toks[i] in ("-t", "-w"):
                    i += 2
                else:
                    i += 1
            continue
        if b in ("xargs", "parallel"):
            i += 1
            while i < n and toks[i].startswith("-"):
                t2 = toks[i]
                if b == "xargs" and t2 in ("-n", "-P", "-I", "-L", "-s", "-E",
                                           "-J", "-R", "-S", "--max-args",
                                           "--max-procs", "--replace",
                                           "--max-lines", "--delimiter", "-d"):
                    i += 2
                else:
                    i += 1
            if i >= n:
                return "echo", "echo", []
            continue
        m = VAR_HEAD_RE.match(t)
        if m and m.group(1) in assigns and depth < 4:
            val = assigns[m.group(1)]
            try:
                inner = shlex.split(val)
            except ValueError:
                inner = val.split()
            if inner:
                return peel(inner + toks[i + 1:], assigns, depth + 1)
        return b, t, toks[i + 1:]
    return "", "", []


# ---------------------------------------------------------------- rules
def rule_redirects(seg):
    for op, target in seg.redirs:
        if op in TRUNC_OPS and target and is_content_path(target):
            return "a `>` redirect truncates the vault file %s" % target
    return None


def rule_ssh(b, rest, depth):
    if b != "ssh":
        return None
    i, seen_host, remote = 0, False, []
    while i < len(rest):
        t = rest[i]
        if not seen_host and t.startswith("-"):
            i += 2 if t in SSH_ARG_OPTS and i + 1 < len(rest) else 1
            continue
        if not seen_host:
            seen_host = True
            i += 1
            continue
        remote.append(t)
        i += 1
    if remote:
        r = scan_command(" ".join(remote), depth + 1)
        if r:
            return "ssh remote command: %s" % r
    return None


def rule_eval(b, rest, depth):
    if b != "eval":
        return None
    r = scan_command(" ".join(rest), depth + 1)
    return ("eval body: %s" % r) if r else None


def rule_shell(b, rest, seg, depth):
    if b not in SHELLS:
        return None
    i, n = 0, len(rest)
    c_mode = noexec = False
    while i < n:
        t = rest[i]
        if t == "--":
            i += 1
            break
        if t.startswith("--"):
            i += 1
            continue
        if t.startswith("-") or t.startswith("+"):
            if "c" in t[1:]:
                c_mode = True
            if t.startswith("-") and "n" in t[1:]:
                noexec = True  # -n: syntax check only, the file never runs
            # -o / -O consume the next word, also at the end of a cluster
            # (`-euo pipefail`).
            i += 2 if t[1:] and t[-1] in "oO" else 1
            continue
        break
    if c_mode and i < n:
        r = scan_command(rest[i], depth + 1)
        return ("%s -c body: %s" % (b, r)) if r else None
    if noexec:
        return None  # `bash -n file` is a read
    if i < n and rest[i] != "-":
        return scan_file(rest[i], "shell", depth)
    return scan_stdin_code(seg, "shell", depth)


def rule_source(b, rest, depth):
    if b not in ("source", "."):
        return None
    if rest:
        r = scan_file(rest[0], "shell", depth)
        return ("sourced " + r) if r else None
    return None


def rule_python(b, rest, seg, depth, assigns):
    if b not in PYTHONS:
        return None
    i, n = 0, len(rest)
    while i < n:
        t = rest[i]
        if t == "-":
            return scan_stdin_code(seg, "python", depth)
        if t == "--":
            i += 1
            break
        if t.startswith("-") and len(t) > 1:
            if t.startswith("-c"):
                body = t[2:] if len(t) > 2 else (rest[i + 1] if i + 1 < n else "")
                k = keyword_hit(body, "python", False, assigns)
                return ("python -c body contains %s" % k) if k else None
            if t.startswith("-m"):
                mod = t[2:] if len(t) > 2 else (rest[i + 1] if i + 1 < n else "")
                if mod in ("py_compile", "compileall"):
                    return None  # compiles the file, never runs it
                cand = mod.replace(".", "/") + ".py"
                return scan_file(cand, "python", depth)
            if t in ("-W", "-X", "-Q"):
                i += 2
                continue
            i += 1
            continue
        break
    if i < n:
        return scan_file(rest[i], "python", depth)
    return scan_stdin_code(seg, "python", depth)


def rule_interp_e(b, rest, seg, depth):
    flags = E_FLAGS.get(b)
    if flags is None:
        return None
    i, n = 0, len(rest)
    bodies = []
    script = None
    while i < n:
        t = rest[i]
        if t == "--":
            i += 1
            break
        if t.startswith("--eval=") or t.startswith("--print="):
            bodies.append(t.split("=", 1)[1])
            i += 1
            continue
        if t in ("--eval", "--print", "-e", "-E") and i + 1 < n:
            if t == "-E" and b == "swift":
                i += 1
                continue
            bodies.append(rest[i + 1])
            i += 2
            continue
        if t.startswith("-") and len(t) > 1 and not t.startswith("--"):
            cluster = t[1:]
            if b == "perl" and cluster.startswith(("M", "m", "I")):
                i += 1
                continue
            if cluster[-1] in flags and i + 1 < n:
                bodies.append(rest[i + 1])
                i += 2
                continue
            if b == "osascript" and cluster == "l" and i + 1 < n:
                i += 2
                continue
            i += 1
            continue
        if t.startswith("--"):
            i += 1
            continue
        script = t
        break
    for body in bodies:
        k = keyword_hit(body, b)
        if k:
            return "%s -e body contains %s" % (b, k)
    if bodies:
        return None
    if script and script != "-":
        return scan_file(script, b, depth)
    return scan_stdin_code(seg, b, depth)


def rule_awk(b, rest, seg, depth):
    if b not in AWKS:
        return None
    i, n = 0, len(rest)
    while i < n:
        t = rest[i]
        if t == "--":
            i += 1
            break
        if t in ("-f", "--file") and i + 1 < n:
            return scan_file(rest[i + 1], "awk", depth)
        if t.startswith("-f") and len(t) > 2 and not t.startswith("--"):
            return scan_file(t[2:], "awk", depth)
        if t in ("-v", "-F") and i + 1 < n:
            i += 2
            continue
        if t.startswith("-"):
            i += 1
            continue
        k = keyword_hit(t, "awk")
        return ("awk program contains %s" % k) if k else None
    return None


def rule_other_interp(b, rest, seg, depth):
    if b not in OTHER_INTERP:
        return None
    body = " ".join(rest)
    k = keyword_hit(body, "unknown")
    return ("%s body contains %s" % (b, k)) if k else None


def rule_deleters(b, head, rest, assigns, allow_root=False):
    low = [t.lower() for t in rest]
    if b in DELETERS:
        targets, after_dd = [], False
        for t in rest:
            if not after_dd and t == "--":
                after_dd = True
                continue
            if not after_dd and t.startswith("-") and len(t) > 1:
                continue
            targets.append(t)
        if targets and all(throwaway_target(t, assigns, allow_root) for t in targets):
            return None  # every target is a throwaway file outside the vault
        return ("deletes files (`%s`; only throwaway targets under /tmp, "
                "$TMPDIR, ~/.cache or ~/Library/Caches are allowed, and every "
                "target must be a resolvable path)" % head)
    if b in HARD_DELETERS:
        return "deletes or truncates files (`%s`)" % head
    if b == "mkfs" or b.startswith("mkfs."):
        return "mkfs formats a disk"
    if b == "dd" and any(t.startswith("of=") for t in low):
        return "dd of= overwrites a device/file"
    if b == "diskutil" and any(t in ("erasedisk", "erasevolume", "reformat",
                                     "secureerase", "zerodisk", "randomdisk",
                                     "partitiondisk", "apfs") for t in low):
        return "diskutil erase/reformat"
    if b == "rsync" and any(t.startswith("--delete") or t == "--remove-source-files"
                            for t in low):
        return "rsync with a delete flag removes files"
    if b == "tar" and "--remove-files" in low:
        return "tar --remove-files deletes the sources"
    if b == "zip":
        for t in rest:
            if t.startswith("-") and not t.startswith("--") and ("m" in t[1:] or "d" in t[1:]):
                return "zip -m/-d deletes files or entries"
            if t in ("--move", "--delete"):
                return "zip -m/-d deletes files or entries"
    if b == "crontab" and any(t.startswith("-") and "r" in t[1:] for t in rest):
        return "crontab -r wipes the crontab"
    return None


def rule_find(b, rest, depth, assigns):
    if b != "find":
        return None
    low = [t.lower() for t in rest]
    start_paths = []
    for t in rest:
        if t.startswith("-") or t in ("__LP__", "!", ","):
            break
        start_paths.append(t)
    if "-delete" in low:
        if start_paths and all(throwaway_target(p, assigns, True) for p in start_paths):
            return None
        return "find -delete removes files (only under throwaway roots is it allowed)"
    i = 0
    while i < len(rest):
        t = low[i]
        if t in ("-exec", "-execdir", "-ok", "-okdir"):
            j = i + 1
            body = []
            while j < len(rest) and rest[j] not in FIND_TERMINATORS:
                x = rest[j]
                if x == "{}":
                    body.extend(start_paths or ["{}"])
                else:
                    body.append(x)
                j += 1
            if body:
                r = scan_segment_tokens(body, depth + 1, assigns=assigns, allow_root=True)
                if r:
                    return "find %s: %s" % (t, r)
            i = j + 1
            continue
        if t in ("-fprint", "-fprint0", "-fprintf", "-fls") and i + 1 < len(rest):
            if is_content_path(rest[i + 1]):
                return "find %s overwrites the vault file %s" % (t, rest[i + 1])
        i += 1
    return None


def _clobber_checks(cmd, args, vault_bound, dest_flag_t=True):
    """Shared mv/cp/install/ln destination rules."""
    flags, positional, dest, i = [], [], None, 0
    while i < len(args):
        t = args[i]
        if t == "--":
            positional.extend(args[i + 1:])
            break
        if t.startswith("--target-directory="):
            dest = t.split("=", 1)[1]
            flags.append("-t")
        elif t in ("-t", "--target-directory") and dest_flag_t and i + 1 < len(args):
            dest = args[i + 1]
            flags.append("-t")
            i += 1
        elif t.startswith("-") and len(t) > 1:
            flags.append(t)
        else:
            positional.append(t)
        i += 1
    if dest is None:
        if len(positional) < 2:
            return None
        dest, sources = positional[-1], positional[:-1]
    else:
        sources = positional
    no_clobber = any((f.startswith("-") and not f.startswith("--") and "n" in f[1:])
                     or f == "--no-clobber" for f in flags)
    if cmd == "ln" and not any(f.startswith("-") and not f.startswith("--") and "f" in f[1:]
                               for f in flags):
        return None
    if vault_bound and source_touches_vault(sources):
        why = forbidden_destination(dest)
        if why:
            return "%s %s" % (cmd, why)
        vault = STATE["vault"]
        resolved = resolve(dest)
        if vault and resolved and not inside(resolved, vault):
            return ("%s destination %s is outside the vault (%s)"
                    % (cmd, dest, vault))
    if no_clobber:
        return None
    resolved = resolve(dest)
    if resolved is None:
        return None
    if os.path.isfile(resolved):
        return "%s would silently overwrite the existing file %s" % (cmd, dest)
    if os.path.isdir(resolved):
        for s in sources:
            if any(ch in s for ch in "*?[$"):
                continue
            cand = os.path.join(resolved, os.path.basename(s.rstrip("/")))
            if os.path.isfile(cand):
                return ("%s would silently overwrite the existing file %s"
                        % (cmd, os.path.join(dest, os.path.basename(s))))
    return None


def rule_move_copy(b, rest):
    if b in ("mv", "cp"):
        return _clobber_checks(b, rest, True)
    if b == "install":
        return _clobber_checks(b, rest, False)
    if b == "ln":
        return _clobber_checks(b, rest, False)
    return None


def rule_tee(b, rest):
    if b != "tee":
        return None
    if any(t in ("-a", "--append") or (t.startswith("-") and not t.startswith("--")
                                        and "a" in t[1:]) for t in rest):
        return None
    for t in rest:
        if not t.startswith("-") and is_content_path(t):
            return "tee without -a overwrites the vault file %s" % t
    return None


def rule_git(b, rest, depth):
    if b != "git":
        return None
    i, n = 0, len(rest)
    while i < n and rest[i].startswith("-"):
        t = rest[i]
        if t in GIT_GLOBAL_ARG or (t.startswith("-c") and len(t) == 2):
            i += 2
        else:
            i += 1
    if i >= n:
        return None
    sub = rest[i].lower()
    args = rest[i + 1:]
    low = [a.lower() for a in args]
    if sub == "rm":
        return "git rm removes tracked files"
    if sub in ("clean", "rebase", "filter-branch", "filter-repo", "prune", "restore"):
        return "git %s rewrites or discards work" % sub
    if sub == "reset":
        for a in low:
            if a.startswith("--") and (
                    ("--hard".startswith(a) and len(a) >= 3)
                    or ("--merge".startswith(a) and len(a) >= 4)
                    or ("--keep".startswith(a) and len(a) >= 3)):
                return "git reset %s discards work" % a
    if sub == "push":
        for a in low:
            if a in ("-f", "-d", "--delete") or a.startswith("--force"):
                return "git force-push / remote delete"
            if a.startswith("-") and not a.startswith("--") and "f" in a[1:]:
                return "git force-push / remote delete"
            if a.startswith("+") or a.startswith(":"):
                return "git push with a forcing or deleting refspec"
    if sub == "stash":
        if not args or low[0] not in ("list", "show"):
            return "git stash hides uncommitted work"
    if sub in ("branch", "tag"):
        for a in low:
            if a in ("--delete", "-d") or (a.startswith("-") and not a.startswith("--")
                                           and ("d" in a[1:] or "D" in a[1:])):
                return "git %s delete" % sub
        for a in args:
            if a.startswith("-") and not a.startswith("--") and "D" in a[1:]:
                return "git %s delete" % sub
    if sub == "commit" and "--amend" in low:
        return "git commit --amend rewrites history"
    if sub == "reflog" and low and low[0] in ("expire", "delete"):
        return "git reflog %s destroys the undo path" % low[0]
    if sub == "gc" and any(a.startswith("--prune") for a in low):
        return "git gc --prune destroys the undo path"
    if sub == "worktree" and low and low[0] in ("remove", "prune"):
        return "git worktree %s" % low[0]
    if sub == "switch" and any(a in ("--discard-changes", "-f", "--force") for a in low):
        return "git switch discards changes"
    if sub == "read-tree" and "--reset" in low:
        return "git read-tree --reset discards work"
    if sub == "checkout-index" and any(a in ("-f", "--force") or
                                       (a.startswith("-") and not a.startswith("--")
                                        and "f" in a[1:]) for a in low):
        return "git checkout-index -f overwrites files"
    if sub == "update-ref" and any(a in ("-d", "--delete") for a in low):
        return "git update-ref -d deletes a ref"
    if sub == "config":
        reading = any(a in ("--get", "--get-all", "-l", "--list", "--get-regexp")
                      for a in low)
        for k, a in enumerate(low):
            if a == "core.hookspath" and not reading:
                val = args[k + 1] if k + 1 < len(args) else None
                # `git config core.hooksPath` with no value is a read.
                if val is not None and val != "scripts/hooks":
                    return "git config core.hooksPath re-points the hooks away from scripts/hooks"
            if a.startswith("alias.") and k + 1 < len(args):
                r = scan_command("git " + args[k + 1], depth + 1)
                if r:
                    return "git alias to a destructive command: %s" % r
        if "--unset" in low and "core.hookspath" in low:
            return "git config unsets core.hooksPath"
    if sub == "mv":
        return _clobber_checks("git mv", args, True, dest_flag_t=False)
    if sub == "checkout":
        return _git_checkout(args)
    return None


def _git_checkout(args):
    nonflag, paths, i = [], None, 0
    while i < len(args):
        a = args[i]
        if a == "--":
            paths = args[i + 1:]
            break
        if a.startswith("-"):
            if a in ("-f", "--force", "-B", "--orphan", "--ours", "--theirs", "--patch", "-p"):
                return "git checkout %s discards or rewrites work" % a
            if not a.startswith("--") and ("f" in a[1:] or "B" in a[1:]):
                return "git checkout %s discards or rewrites work" % a
            if a in ("-b", "--conflict", "--pathspec-from-file", "--recurse-submodules"):
                i += 2
                continue
            i += 1
            continue
        nonflag.append(a)
        i += 1
    if paths is None:
        if not nonflag:
            return None
        if len(nonflag) == 1:
            a = nonflag[0]
            r = resolve(a)
            if a in (".", "./") or (r is not None and os.path.exists(r)):
                paths = [a]
            elif r is None and ("/" in a or a.endswith(".md")):
                paths = [a]
            else:
                return None
        else:
            paths = nonflag[1:]
    if not paths:
        return None
    if not STATE["cwd"]:
        return "git checkout of paths overwrites working-tree files"
    for p in paths:
        r = resolve(p)
        if r is None or os.path.exists(r):
            return ("git checkout of %s overwrites a file that exists in the working tree"
                    % p)
    return None  # pure restore of files that do not currently exist


# ---------------------------------------------------------------- drivers
def scan_segment_tokens(toks, depth, seg=None, assigns=None, allow_root=False):
    if seg is None:
        seg = Seg()
        seg.toks = list(toks)
    if assigns is None:
        assigns = {}
    r = _safe(rule_redirects, seg)
    if r:
        return r
    if not seg.toks:
        return None
    try:
        b, head, rest = peel(seg.toks, assigns)
    except Exception:
        b, head, rest = norm_head(seg.toks[0]), seg.toks[0], seg.toks[1:]
    if not b:
        return None
    for fn, a in (
            (rule_ssh, (b, rest, depth)),
            (rule_eval, (b, rest, depth)),
            (rule_shell, (b, rest, seg, depth)),
            (rule_source, (b, rest, depth)),
            (rule_python, (b, rest, seg, depth, assigns)),
            (rule_interp_e, (b, rest, seg, depth)),
            (rule_awk, (b, rest, seg, depth)),
            (rule_other_interp, (b, rest, seg, depth)),
            (rule_deleters, (b, head, rest, assigns, allow_root)),
            (rule_find, (b, rest, depth, assigns)),
            (rule_move_copy, (b, rest)),
            (rule_tee, (b, rest)),
            (rule_git, (b, rest, depth)),
    ):
        r = _safe(fn, *a)
        if r:
            return r
    return None


def scan_command(command, depth=0):
    """Reason string if the command string contains a destructive step."""
    if depth > MAX_DEPTH or not command or not isinstance(command, str):
        return None
    try:
        lines = parse(command)
    except Exception:
        seg = Seg()
        seg.toks = fallback_tokens(command)
        return scan_segment_tokens(seg.toks, depth, seg)
    assigns = _safe(assignments, lines) or {}
    for line in lines:
        for seg in line.segs:
            r = scan_segment_tokens(seg.toks, depth, seg, assigns)
            if r:
                return r
        for inner in (_safe(substitutions, line.text) or []):
            r = scan_command(inner, depth + 1)
            if r:
                return "command substitution: %s" % r
    return None


BLOCK_MSG = (
    "Blocked by the vault safety gate (~/.claude/hooks/bash-guard.py): %s. "
    "This is on the never-list (delete, overwrite, move out of the vault, "
    "force-push, history rewrite). Do not look for another spelling of the "
    "same action. Keep moves and copies inside the vault (raw/processed/, "
    "archive/, outputs/), append rather than overwrite, and write new files "
    "with the Write tool; deleting is allowed only for throwaway files under "
    "/tmp, $TMPDIR or the caches, named by a resolvable path. If something "
    "else genuinely needs deleting, restoring or rewriting, tell the owner "
    "exactly what and why and let them do it themselves in Finder or "
    "Terminal; git holds the undo path.\n"
)


def main():
    try:
        data = json.load(sys.stdin)
        if data.get("tool_name") != "Bash":
            sys.exit(0)
        command = (data.get("tool_input") or {}).get("command", "")
        if not command or not isinstance(command, str):
            sys.exit(0)
        cwd = data.get("cwd")
        if isinstance(cwd, str) and cwd and os.path.isdir(cwd):
            STATE["cwd"] = os.path.abspath(cwd)
            STATE["vault"] = _safe(find_vault, STATE["cwd"])
    except SystemExit:
        raise
    except Exception:
        sys.exit(0)  # fail open only on a malformed payload
    try:
        reason = scan_command(command)
    except Exception:
        reason = None  # framework bug: never freeze Claude Code
    if reason:
        sys.stderr.write(BLOCK_MSG % reason)
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
