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

Two assistants send that payload, in the same shape. Claude Code sends it
for the shell only, and has no other tool that removes a file. ChatGPT's
agent (Codex) sends it for the shell and ALSO for its file-editing tool,
as {"tool_name": "apply_patch", "tool_input": {"command": "<patch text>"}},
and a patch can delete a file ("*** Delete File:"), move one ("*** Move
to:") or write over one ("*** Add File:" on a path that exists). scan_patch
reads those three lines and nothing else: an ordinary edit ("*** Update
File:" with hunks) is never refused, as an Edit is never refused on Claude.
It reads them the way Codex's own patch reader does: outside an Update
hunk a header may be indented, inside one only a header at column 0 counts
(an indented line there is the page's own text); paths are taken literally,
with no ~ or $ expansion; and a new file may be claimed once per patch, so
a move followed by an add onto the same name cannot replace a page. If
reading a patch fails and it holds a delete or move line, it is refused.
Through the shell, apply_patch is allowed in one spelling only, a single
quoted heredoc with no cd before it, because every other spelling hides the
patch or the folder it applies in. A shell or interpreter started with
nothing to run is refused for both assistants: Codex can type into such a
session afterwards (write_stdin) without the hook being asked again.
(Payload shape and patch grammar confirmed by a live Codex run and from
codex-rs/apply-patch/src/parser.rs and streaming_parser.rs, 20 September
2026.)

Per-machine: lives in ~/.claude/hooks/ (Claude Code) or ~/.codex/hooks/
(ChatGPT), wired as a PreToolUse hook by safety/install-safety.py, matching
Bash on Claude Code and Bash|apply_patch on ChatGPT. First shipped in Moblee
v0.5 (September 2026). v4 (16 September 2026) followed an adversarial review
of v3; safety/test-guard.py is the suite. A wiki is recognised by CLAUDE.md
or AGENTS.md beside a wiki/ folder.

v5.1 (October 2026) closes six routes a review found open, each of which
returned 0: (1) Python that starts a process under another name (`from
subprocess import run`, `import subprocess as s`, os.exec*/spawn*/
posix_spawn, pty.spawn), now matched on word boundaries, with the command
lines a script hands to such a call read as commands; (2) wrappers the
guard did not peel (timeout, gtimeout, taskpolicy, xcrun, sandbox-exec,
watch, and the option arguments of stdbuf, arch and time); (3) git
checkout by pathspec magic (`:/`, `:(top)`), by --pathspec-from-file, by a
glob, or under -C / --work-tree; (4) the vault folder itself, protected
whatever folder the session starts in, taken from the MOBLEE_VAULT
environment variable or ~/.config/moblee/vault-path; (5) a command sent
over ssh, read as if it ran on the machine it is sent to; (6) the guard's
own files: ~/.claude/settings.json, settings.local.json, everything in
~/.claude/hooks/, and any .claude/settings*.json, against in-place edits,
chmod and kin, moves, copies onto them, links and writes from inline code.
Reading them passes. Homebrew's GNU tools, which carry a g prefix (grm,
gmv, gsed …), are read as the tools whose work they do.

v5.2 (October 2026) knows a build folder from the wiki. A cold review of the
first cut found six ways round it, each closed with a case in the suite: git
pointed at the wiki by --work-tree, --git-dir, core.worktree or the
environment while sitting in a build folder; the two files that tell the guard
where the wiki and the build roots are, now protected like its own settings;
.git, data and state spelt in another case on a disk that ignores case; mv of
a build folder itself or of those three; a wiki that lives under ~/Apps, which
is a wiki; and a `>` through a link into the wiki, which truncated a page. The build skill puts
anything that needs installing outside the wiki at ~/Apps/<name>/, and the
first owner to work there met refusals on every ordinary step and switched
the guard off by hand. Now a path strictly inside a build folder (under
~/Apps, or a root named in ~/.config/moblee/build-roots or
MOBLEE_BUILD_ROOTS) may be deleted, found-and-deleted, written over or
moved, and a build folder's own repository may restore, stash and check out
paths. Never: the folder itself, its .git, its data/ and state/ folders,
anything in any vault, history rewrites (reset --hard, rebase, clean,
force-push, branch delete) anywhere, and the guard's own files. A session
started inside a build folder sees no vault there; the recorded vault stays
protected by its absolute path.
"""
import ast
import hashlib
import json
import os
import re
import shlex
import sys
import unicodedata

VERSION = "v5.2"
MAX_DEPTH = 6
MAX_FILE_BYTES = 512 * 1024
MAX_HASH_BYTES = 4 * 1024 * 1024
MAX_FILES_PER_CALL = 6

# --- KNOWN_SAFE begin ---
KNOWN_SAFE_SHA256 = {
    "238f80a5feaf5f8cd64a61d90386640aa153290537f2bfe8bc1a1ee77b9e44ff": "dashboard/server.py",
    "eaeb66d6d49dd061399f203945b330dd7ba88d86b61385592fff92473a46c57d": "extras/recall/install-recall.py",
    "58d03e41cc158f36d736871c1e6b740c7706a748fbcb8f6b60f3856dcc73e1f2": "extras/recall/rebuild-index.sh",
    "0da0d35e4131214cac6564771278bf44f726ac30f672fdf6d5882e8cc720be9a": "extras/recall/recall-inject.py",
    "1f6251657d9ac39d61f342e2739ceab9268e88fe56a47f2327798454bad05f69": "extras/recall/recall.py",
    "a4294253dcd091c30997668bd55ce359076597de23e4bf341e690168373ea65c": "learning-path/moblee-tip.sh",
    "9b4500ffcbd523cc46bc40a4676ceb328c2272df6b3a210b3bb46828e20573ec": "safety/install-safety.py",
    "839b16abae93385eceb46c30cbfa1fab1938020d591b266ccd613bb341f805e8": "safety/test-guard.py",
    "8a5524c075c8643ba9606bcf6243bd94523078dd504d76b52f0b629296be5ad0": "scripts/add-habits-page.py",
    "4b2f688c92a7b56fb2fc98c25a922ecf958b77b13659173e0b86cfa336aff211": "scripts/add-identity.py",
    "e0a74cf640a0a76f0bfedade668fe7cf65042e3c790c0c2e4b4ccbc6525b65ab": "scripts/add-reference-pages.py",
    "12bee9b30a2d2f2498f2c110f5b57b9939941937c2a628ed775ebfd581550250": "scripts/cadence/run-weekly-lint.sh",
    "0887660d33b9b383645a584aaf3aa2e16cc1448b850561a215f849fe135e7b78": "scripts/compact-rotate.py",
    "f478877cc79bc5c60778f00e57717a433a2b1a768b663e799ca840fab55ae77e": "scripts/hooks/post-commit",
    "42bb3ae68fb171ff5670ac7e1fa8ec3e49bfc1e138c8727ee497158ab1c12c8e": "scripts/hooks/pre-commit",
    "41f250df9ce19f0b0118ea0775877732102b5da4864531e72321c7587678ba79": "scripts/install-learning-path.py",
    "e6526d9d84ff88e7c3c581064c67fbcd71c94ffeaf69b439e48b7413f40148ba": "scripts/install-schedule.sh",
    "e311dbe293d6d31dcbf4405e1083c18148cc11e68fc274a121272f37e1b01326": "scripts/install-skills.sh",
    "01f3aefa92b7bfc4b35ce773469230ca56d4813fec2403078f2b85728eaf8fa3": "scripts/install.sh",
    "1b790b84e08e7f116346feed1201660d2cd6d15bbca7f12e7e0474e3bd8adcb4": "scripts/job-switch.py",
    "aea04e2f4b23d1fe669649f7b7847fec941de0dfa8ed54a799739c72b8dcdc73": "scripts/lint-v2.py",
    "3dc036a7fd72607eae7eb8adfdefd749858205ba6aac05d604373a1714a56f57": "scripts/log-append.py",
    "ec6e30ab37f521406942ce12157e3e6ece278c3ea02e6afa515942e0499764ff": "scripts/moblee-doctor.py",
    "f7d4682dbece9cfb06d810ed4791636acd2ad0ecd26c7b132ca9fba4e5654f30": "scripts/moblee-setup.py",
    "9cb2b290a789ad0b80dec548f7517963d75276d8a1eac268367a01ebf2859090": "scripts/patch-claude-md.py",
    "8d1c998cdd9208de0909e6c4b4d68b5ac667466ce2acb3c1a9ba81fbef3febda": "scripts/seed-memory.py",
    "c6860063b170bd3019dd319081c0992a2401cd5aacf99b6e4b56b2c729734d21": "scripts/test-patch-claude-md.py",
    "631a9c1d17b75715643d07b0b9fdbaccd89ba6c5995f84065a5b0988cdec1d4f": "scripts/turn-end-commit.py",
    "6f2789d0510c35b61a64d8d0404a00a29fe142d927c35e48bdb2cea52e3bb0c8": "scripts/update.sh",
    "56f68e1a9c981abedca1d35bd06d1e20bdd0c60574ec79e04313a1806507d303": "scripts/vault-gate.py",
    "ebecd70937e2dc3b7f31e15877d0e718df2d4bf532146878c9f832e5a6998414": "scripts/vault-orient-preflight.sh",
    "5506f733bb7c75c57fb3f5cc534696bb5a0180719b7f1d060815bf035acf1eba": "scripts/vault.sh",
    "5b05a52f0e41d9b4e80ab2d5199d1a927d2fa9702ae16e538b9dd198d162be9e": "scripts/weekly-card.py",
    "32c7c39b37a9b90097158891e3f75df69110528f73e36b4a10157e6b787ea2d2": "scripts/wiki-galaxy/build.py",
    "55c3de294c860151146b82a41d161244fb8574ed781a8594a193b43f9c4b71cc": "skills/build/parts/keychain.py",
    "ab49d9f8c7d95c1996ea1e6bc185a3b4ac4321bb168be20dad15f9c8c75d9fac": "skills/build/parts/publish.py",
    "a6131913e86fdb8c67dbc9251fed721ec670905e944e8c5e5a1aff72b77ec741": "skills/build/parts/scaffold.py",
    "452bfff60a78080f4987e9d71c62cfad769fd60445bdd1afc31023c97a96b65d": "skills/build/parts/share.py",
    "90584cbb4c1f48899470712aa96f459dd2d927bd90f4143210d59077b6e341e0": "skills/build/parts/sweep.py",
    "bd68a8eedbda1a8227e692661459cb3c963a6f8224ecd42f0998a98ccd7154c8": "skills/build/parts/think-job.py",
    "c6f8b5cb80264cf421df250ceb8f0c6fea1ec183ac7207ae7af7e485664d91f3": "skills/wiki-to-pdf/render.py",
    "3b9bf0e7879138d40d31e06cbf2a1f997e60bc2fced09a48c70d116e7d2ea09a": "tools/test-build.py",
    "f646bbc2029f01cce0edbca5a93dc0404519aac869c916b3d78b02ea135695fe": "voice/install-voice.py",
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
# (v0.9.2) `ditto` came out of this set: it is a copy tool, the macOS cousin
# of cp, and sat among the shredders where nothing it did could be allowed.
# It goes through the same destination checks as mv and cp instead.
HARD_DELETERS = {"trash", "truncate", "shred", "srm", "rimraf"}
CONTENT_DIRS = ("wiki", "raw", "Clippings", "Daily Notes")
INSTRUCTION_FILES = ("CLAUDE.md", "AGENTS.md")
CONTENT_FILES = INSTRUCTION_FILES + ("VERSION",)
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
                "-E", "-e", "-L", "-m", "-O", "-Q", "-R", "-S", "-w", "-B",
                "-I", "-P"}
GIT_GLOBAL_ARG = {"-C", "-c", "--git-dir", "--work-tree", "--namespace",
                  "--exec-path", "--super-prefix", "--config-env",
                  "--list-cmds"}

# (v5.1) The vault this guard protects whatever folder a session starts in,
# alongside the cwd-based discovery in find_vault. A command that named the
# vault by absolute path while the session sat in /tmp or the home folder was
# judged as if it had named nothing at all. The path is read from the two
# places the rest of the pack reads it from — the MOBLEE_VAULT environment
# variable, then the single line the installer writes into
# ~/.config/moblee/vault-path — once, when this file loads, because the guard
# runs on every shell command and must not stat the same file repeatedly.
def _configured_vault_roots():
    """The vault root to protect by absolute path, or none if not recorded."""
    try:
        named = os.environ.get("MOBLEE_VAULT")
        if not named:
            cfg = os.path.join(os.path.expanduser("~"), ".config", "moblee",
                               "vault-path")
            try:
                with open(cfg, "r") as fh:
                    named = fh.read(4096).strip()
            except OSError:
                named = ""
        if named:
            p = os.path.normpath(os.path.expanduser(named))
            if os.path.isabs(p) and os.path.isdir(os.path.join(p, "wiki")):
                return (p,)
    except Exception:
        pass
    return ()


KNOWN_VAULT_ROOTS = _configured_vault_roots()
# Stands in for "no vault here" while a remote command is read: nothing is
# inside it, so only the recorded root above protects a remote path.
NO_VAULT = "/.bash-guard-remote-no-vault"
# (v5.1) Homebrew's GNU tools carry a g prefix (grm, gmv, gtimeout, gsed …)
# and run exactly what their unprefixed names run.
GNU_PREFIXED = {"rm", "rmdir", "unlink", "mv", "cp", "ln", "link", "install",
                "dd", "shred", "truncate", "tee", "sort", "uniq", "timeout",
                "stdbuf", "nice", "nohup", "env", "chmod", "chown", "chgrp",
                "touch", "find", "xargs", "sed", "tar", "time"}
# (v5.1) The guard's own files: the hooks folder (the guard and every hook
# beside it) and the files that register hooks and permissions.
PROTECTED_DIRS_REL = ((".claude", "hooks"), (".codex", "hooks"))
PROTECTED_FILES_REL = ((".claude", "settings.json"),
                       (".claude", "settings.local.json"),
                       (".codex", "hooks.json"),
                       # (v5.2) the two files that tell the guard where the
                       # wiki is and where build folders live: a line written
                       # into either widens or narrows what may be deleted
                       (".config", "moblee", "vault-path"),
                       (".config", "moblee", "build-roots"))
SETTINGS_RE = re.compile(r"(?:^|/)\.claude/settings[^/]*\.json$")
PROTECTED_SPELL_RE = re.compile(
    r"\.claude/+(?:settings[^/\s'\"]*\.json|hooks(?:/|$|[\s'\"]))|\.codex/+hooks"
    r"|\.config/+moblee/+(?:vault-path|build-roots)(?:$|[\s'\"])", re.I)
LOCAL_HOME = os.path.expanduser("~")
CHMODS = {"chmod", "chown", "chgrp", "chflags", "setfacl", "chacl", "lchmod",
          "lchown"}
EDITORS = {"ed", "red", "ex", "vi", "vim", "nvim", "nano", "pico", "emacs",
           "joe", "micro", "mcedit", "kak", "hx", "sponge"}

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
        # (v5.1) qx// is perl's backtick under another name
        "shellout": ("system(", "exec \"", "exec '", "exec(", "qx(", "qx{",
                     "qx/", "qx[", "qx'", "qx!", "qx|"),
        "res_body": (), "res_file": (), "backticks": True,
    },
    "ruby": {
        "del": ("file.delete", "fileutils.rm", "unlink", "rm_rf", "rm_r(",
                "remove_entry", ".truncate("),
        # (v5.1) %x() is ruby's backtick; IO.popen and Open3 run a command too
        "shellout": ("system(", "exec \"", "exec '", "exec(", "spawn(", "%x(",
                     "%x{", "%x[", "%x|", "io.popen", "open3"),
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
# (v5.1) Python APIs that start another process. Used only as a cheap gate (on
# a lower-cased body) before the AST read in py_spawn_hit does the real work,
# and as the fallback when a body does not parse. `subprocess.` as a substring
# missed `from subprocess import run` and `import subprocess as s`; os.exec*,
# os.spawn*, os.posix_spawn and pty.spawn were not listed at all.
PY_SPAWN_RE = re.compile(
    r"\bsubprocess\b"
    r"|\bcreate_subprocess_(?:shell|exec)\b"
    r"|\bpty\s*\.\s*spawn\b|\bpty\b[^\n]{0,30}\bspawn\b"
    r"|\bos\s*\.\s*(?:system|popen\w*|exec\w*|spawn\w*|posix_spawn\w*|forkpty)\b"
    r"|\b(?:popen[234]?|exec(?:l|le|lp|lpe|v|ve|vp|vpe)|spawn(?:l|le|lp|lpe|v|ve|vp|vpe)"
    r"|posix_spawnp?|forkpty)\s*\("
    r"|\bsystem\s*\("
    r"|\bget(?:status)?output\s*\(")
# Bare names (and the module they can come from) that start a process.
PY_SPAWN_NAMES = {"system", "popen", "popen2", "popen3", "popen4", "execv",
                  "execve", "execvp", "execvpe", "execl", "execle", "execlp",
                  "execlpe", "spawnv", "spawnve", "spawnvp", "spawnvpe", "spawnl",
                  "spawnle", "spawnlp", "spawnlpe", "posix_spawn", "posix_spawnp",
                  "forkpty", "run", "call", "check_call", "check_output",
                  "getoutput", "getstatusoutput", "popen", "spawn",
                  "create_subprocess_shell", "create_subprocess_exec"}
PY_SPAWN_MODULES = {"os", "subprocess", "pty", "asyncio", "commands", "sp",
                    "subp", "subproc"}
# Attribute calls that spawn whatever their object (so x.Popen(...), p.run(...)).
PY_SPAWN_ATTRS = {"popen", "run", "call", "check_call", "check_output",
                  "getoutput", "getstatusoutput", "system", "spawn",
                  "create_subprocess_shell", "create_subprocess_exec"}
# getattr(x, "<name>") naming one of these is a spawn/delete call in disguise.
PY_RISKY_ATTRS = {"system", "popen", "remove", "unlink", "rmdir", "removedirs",
                  "rmtree", "truncate", "spawn", "posix_spawn", "posix_spawnp",
                  "forkpty", "execv", "execve", "execvp", "execvpe", "execl",
                  "execle", "execlp", "execlpe", "run", "call", "check_call",
                  "check_output", "getoutput", "getstatusoutput"}
# Fallback when a body does not parse: a spawn call with a literal first argument.
PY_SPAWN_CALL_TEXT_RE = re.compile(
    r"\b(?:run|call|check_call|check_output|popen|system|getoutput|getstatusoutput"
    r"|exec[lv]\w*|spawn[lv]\w*|posix_spawnp?)"
    r"\s*\(\s*(\[[^\]\n]{0,400}\]|[rRbBuUfF]?(['\"])[^'\"\n]*\2)")
# The write must be tied to the protected PATH, not merely present somewhere in
# the body: a script that READS settings.local.json (json.load(open(...))) and
# writes an unrelated output file is not touching the guard. So the check looks
# for a write verb immediately before, or a write mode immediately after, the
# protected literal — not a write verb anywhere in the body.
# A write mode right after the literal: open('<prot>', 'w'), possibly after a
# wrapping call's close paren (open(expanduser('<prot>'),'w')). A read mode
# ('r', 'rb') does not match, so READING the file is not flagged.
SELF_WRITE_AFTER_RE = re.compile(
    r"^\s*(?:\)[^,\n]*)?,\s*(?:mode\s*=\s*)?['\"][rbt]*[wax+]")
# Verbs that only ever write; paired with a protected literal anywhere in the
# body they are a write to the guard (unlike open(), which may be a read).
SELF_WRITE_UNAMBIG_RE = re.compile(
    r"writefilesync|\bwritefile\b|appendfilesync|\bappendfile\b|createwritestream"
    r"|copyfilesync|\bcopyfile\b|\.write_text\s*\(|\.write_bytes\s*\(", re.I)
# A protected path built by joining adjacent string literals ('.claude' /
# 'settings.json', or Path.home()/'.claude'/'hooks'): prose in a wiki page is
# one literal, so it does not match this adjacent-literal-plus-slash shape.
PATHLIB_SELF_RE = re.compile(
    r"['\"]\.?\.?/?\.claude['\"]\s*/\s*['\"](?:hooks|settings[^'\"]*\.json)['\"]"
    r"|['\"]\.codex['\"]\s*/\s*['\"]hooks", re.I)
PATHLIB_WRITE_RE = re.compile(
    r"write_text|write_bytes|open\s*\(|\.rename\s*\(|\.replace\s*\(", re.I)
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
STATE = {"cwd": None, "vault": None, "files": 0, "chdir": False,
         "remote": False, "no_files": False}


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
        if (any(os.path.isfile(os.path.join(p, f)) for f in INSTRUCTION_FILES)
                and os.path.isdir(os.path.join(p, "wiki"))):
            return p
        if git_root is None and os.path.exists(os.path.join(p, ".git")):
            git_root = p
        parent = os.path.dirname(p)
        if parent == p:
            break
        p = parent
    found = git_root or os.path.abspath(cwd)
    # (v5.2) A folder under a build root with no wiki above it is a build
    # folder, which the guard treats as no vault at all: the recorded vault
    # stays protected by its absolute path wherever the command starts.
    try:
        folder = None if known_root_of(found) else build_folder_of(found)
        if folder and not _wiki_between(_real(os.path.normpath(found)), folder):
            return NO_VAULT
    except Exception:
        pass
    return found


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


# (v5.1) A Mac's disk ignores letter case and accent form, so a path spelled
# in another case, or with its accents composed differently, reaches exactly
# the same files as the canonical spelling.
def _fold(p):
    return unicodedata.normalize("NFC", p).casefold()


def _real(p):
    try:
        return os.path.realpath(p)
    except (ValueError, OSError):
        return p


def in_root(path, root):
    """inside(), compared without regard to letter case or accent form, and
    for paths that do not exist on this Mac (a remote vault)."""
    if not path or not root or not os.path.isabs(path) or not os.path.isabs(root):
        return False
    ps = {_fold(os.path.normpath(path)), _fold(_real(path))}
    rs = {_fold(os.path.normpath(root)).rstrip("/"), _fold(_real(root)).rstrip("/")}
    for p in ps:
        for r in rs:
            if p == r or p.startswith(r + "/"):
                return True
    return False


def known_root_of(path):
    """The known vault root an absolute path lies in, or None."""
    if not path:
        return None
    for k in KNOWN_VAULT_ROOTS:
        if in_root(path, k):
            return k
    return None


def _under_content(resolved, root):
    for d in CONTENT_DIRS:
        if in_root(resolved, os.path.join(root, d)):
            return True
    for f in CONTENT_FILES:
        if _fold(os.path.normpath(resolved)) == _fold(os.path.join(root, f)):
            return True
    return False


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
    # (v5.1) the known vaults and the guard's own files are never throwaway
    if known_root_of(real) or known_root_of(p) or is_protected(target):
        return False
    for root in throwaway_roots():
        if real.startswith(root + os.sep) or (allow_root and real == root):
            return True
    return False


# (v5.2) Build folders. The build skill places anything that needs installing
# outside the wiki, at ~/Apps/<name>/, with its own git history and nothing of
# the owner's that is not also in git; the wiki keeps the thing's page, a
# pointer folder and anything worth keeping under wiki/data/<name>/. Ordinary
# work in such a folder means removing a dependencies or build folder, writing
# over a generated file, checking out or stashing in its own repository. The
# guard refused all of these, because its list of throwaway places stopped at
# the temporary folders, and the first owner to meet that switched the guard
# off by hand. So a path strictly inside a build folder is disposable, with
# three exceptions that are never: the folder itself (the owner removes a
# thing by hand), its .git, and its data/ and state/ folders. The wiki is
# never a build folder, whatever folder it lives in, and nothing inside any
# known vault is ever disposable.
BUILD_KEEP = ("data", "state", ".git")


def build_roots():
    """The folders under which build folders live: ~/Apps, plus any named in
    ~/.config/moblee/build-roots (one per line) or MOBLEE_BUILD_ROOTS
    (colon-separated). Read at call time: the guard runs once per command."""
    roots = [os.path.expanduser("~/Apps")]
    try:
        extra = os.environ.get("MOBLEE_BUILD_ROOTS", "")
        for r in extra.split(":"):
            if r.strip():
                roots.append(os.path.expanduser(r.strip()))
        cfg = os.path.join(os.path.expanduser("~"), ".config", "moblee", "build-roots")
        with open(cfg, "r") as fh:
            for line in fh.read(4096).splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    roots.append(os.path.expanduser(line))
    except OSError:
        pass
    except Exception:
        pass
    out = []
    homes = {_fold(_real(h)) for h in _homes()}
    for r in roots:
        if not os.path.isabs(r):
            continue
        n = os.path.normpath(r)
        # a root that would make the disk, a home or a wiki "build material"
        # is no root at all
        if n == "/" or _fold(_real(n)) in homes or known_root_of(n):
            continue
        out.append(n)
    return out


def _is_real_vault(v):
    """True if v is a wiki (recorded, or holding an instruction file beside a
    wiki/ folder) rather than the guard's fallback of "the folder the session
    started in", which from ~ would otherwise swallow ~/Apps."""
    if not v or v == NO_VAULT:
        return False
    if known_root_of(v):
        return True
    try:
        return (any(os.path.isfile(os.path.join(v, f)) for f in INSTRUCTION_FILES)
                and os.path.isdir(os.path.join(v, "wiki")))
    except OSError:
        return False


def _wiki_between(real, folder):
    """True if any folder from real up to and including the build folder is
    a wiki (an instruction file beside wiki/): a wiki that lives under ~/Apps
    is a wiki, never build material."""
    try:
        p = real if os.path.isdir(real) else os.path.dirname(real)
        stop = _fold(folder)
        for _ in range(64):
            if (any(os.path.isfile(os.path.join(p, f)) for f in INSTRUCTION_FILES)
                    and os.path.isdir(os.path.join(p, "wiki"))):
                return True
            if _fold(p) == stop:
                break
            parent = os.path.dirname(p)
            if parent == p:
                break
            p = parent
    except OSError:
        return True
    return False


def build_keep_reason(target, assigns=None):
    """A reason string if target is a build folder itself or one of the parts
    of it that are never disposable (.git, data, state), else None."""
    if not target or UNRESOLVABLE_RE.search(target):
        return None
    p = resolve(target, assigns)
    if p is None:
        return None
    real = _real(os.path.normpath(p))
    folder = build_folder_of(real)
    if not folder:
        return None
    if _fold(real) == _fold(folder):
        return "touches a build folder itself (%s), which only the owner removes or moves" % target
    try:
        first = os.path.relpath(real, folder).split(os.sep)[0]
    except ValueError:
        return None
    if _fold(first) in BUILD_KEEP:
        return "touches a build folder's %s (%s), which is never deleted or moved" % (first, target)
    return None


def build_folder_of(path):
    """The build folder (<root>/<name>) a path is in or under, as a real path,
    or None. The root itself (~/Apps) is not a build folder. Everything is
    compared in real-path form, because a home under /var/folders or a
    symlinked ~/Apps spells the same folder two ways."""
    if not path or not os.path.isabs(path):
        return None
    real = _real(os.path.normpath(path))
    for root in build_roots():
        rb = _real(os.path.normpath(root))
        if not in_root(real, rb):
            continue
        try:
            rel = os.path.relpath(real, rb)
        except ValueError:
            continue
        parts = [p for p in rel.split(os.sep) if p and p != "."]
        if not parts or parts[0] == "..":
            continue
        return os.path.join(rb, parts[0])
    return None


def build_target(target, assigns=None):
    """True iff target resolves to a path strictly inside a build folder,
    outside every vault, and not the folder itself, its .git, data/ or state/."""
    if not target or UNRESOLVABLE_RE.search(target):
        return False
    p = resolve(target, assigns)
    if p is None:
        return False
    real = _real(os.path.normpath(p))
    if _is_real_vault(STATE["vault"]) and inside(real, STATE["vault"]):
        return False
    if known_root_of(real) or known_root_of(p) or is_protected(target):
        return False
    folder = build_folder_of(real)
    if not folder:
        return False
    if _fold(real) == _fold(folder):
        return False  # the thing itself is the owner's to remove
    try:
        rel = os.path.relpath(real, folder)
    except ValueError:
        return False
    first = rel.split(os.sep)[0]
    if _fold(first) in BUILD_KEEP or first == "..":
        return False
    if _wiki_between(real, folder):
        return False  # a wiki under ~/Apps is a wiki
    return True


def disposable_target(target, assigns=None, allow_root=False):
    """A target that may be deleted: throwaway (under /tmp and kin) or build
    material (strictly inside a build folder)."""
    return throwaway_target(target, assigns, allow_root) or build_target(target, assigns)


def in_build_repo():
    """True iff the command runs inside a build folder (after any cd or
    git -C), which is not a known vault."""
    cwd = STATE.get("cwd")
    if not cwd:
        return False
    real = _real(os.path.normpath(cwd))
    if known_root_of(real) or known_root_of(cwd):
        return False
    if _is_real_vault(STATE["vault"]) and inside(real, STATE["vault"]):
        return False
    folder = build_folder_of(real)
    if folder is None:
        return False
    return not _wiki_between(real, folder)


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


# (v0.9.2) The guard's own file and the files that register it, for both
# assistants. Nothing else the guard protects matters if these can be written
# over: `echo x > ~/.claude/hooks/bash-guard.py` ends every rule in this file,
# and `echo` is allow-listed. The owner changes these in their own Terminal, as
# they always could; what is refused is the assistant doing it.
SELF_PATHS = tuple(os.path.join(os.path.expanduser("~"), *parts) for parts in (
    (".claude", "hooks", "bash-guard.py"),
    (".claude", "settings.json"),
    (".codex", "hooks", "bash-guard.py"),
    (".codex", "hooks.json"),
))


def is_self_path(path_raw):
    """True if the path names the guard itself or the file that registers it."""
    if not path_raw:
        return False
    resolved = resolve(path_raw)
    for s in SELF_PATHS:
        if resolved and os.path.realpath(resolved) == os.path.realpath(s):
            return True
        # a path the guard cannot resolve is judged on its spelling, since what
        # cannot be read cannot be cleared for writing either
        if os.path.basename(str(path_raw)) == os.path.basename(s) \
                and os.path.dirname(s).split(os.sep)[-1] in str(path_raw):
            return True
    return False


# (v5.1) The wider set: the hooks folder and everything in it, every file that
# registers hooks or permissions (any .claude/settings*.json, wherever it is),
# for this Mac's home and, while a remote command is read, the remote home.
def _homes():
    out = [LOCAL_HOME]
    cur = os.path.expanduser("~")
    if cur and cur not in out:
        out.append(cur)
    return out


def _vault_roots():
    out = list(KNOWN_VAULT_ROOTS)
    v = STATE.get("vault")
    if v and v != NO_VAULT and v not in out:
        out.append(v)
    return out


def protected_concrete():
    """Absolute protected paths (files and folders) for the ancestor test."""
    out = []
    for h in _homes():
        for rel in PROTECTED_FILES_REL + PROTECTED_DIRS_REL:
            out.append(os.path.join(h, *rel))
    for root in _vault_roots():
        out.append(os.path.join(root, ".claude", "settings.json"))
        out.append(os.path.join(root, ".claude", "settings.local.json"))
    return out


def _protected_by_name(f):
    """f: a folded, normalised absolute path."""
    if SETTINGS_RE.search(f):
        return True
    for h in _homes():
        for rel in PROTECTED_DIRS_REL:
            d = _fold(os.path.join(h, *rel))
            if f == d or f.startswith(d + "/"):
                return True
        for rel in PROTECTED_FILES_REL:
            if f == _fold(os.path.join(h, *rel)):
                return True
    return False


def _same_file_as_protected(resolved):
    """A hard link to a protected file is the same file under another name."""
    try:
        st = os.stat(resolved)
    except (OSError, ValueError):
        return False
    if st.st_nlink < 2 or not os.path.isfile(resolved):
        return False
    cands = []
    for h in _homes():
        for rel in PROTECTED_FILES_REL:
            cands.append(os.path.join(h, *rel))
        for rel in PROTECTED_DIRS_REL:
            d = os.path.join(h, *rel)
            try:
                cands.extend(os.path.join(d, x) for x in os.listdir(d))
            except OSError:
                pass
    for c in cands:
        try:
            cs = os.stat(c)
        except OSError:
            continue
        if (cs.st_dev, cs.st_ino) == (st.st_dev, st.st_ino):
            return True
    return False


def is_protected(path_raw):
    """True if the path is one of the guard's own files (see above)."""
    if not path_raw:
        return False
    if is_self_path(path_raw):
        return True
    resolved = resolve(path_raw)
    if resolved is None:
        # judged on its spelling, as is_self_path does
        f = _fold(str(path_raw))
        return bool(SETTINGS_RE.search(f) or PROTECTED_SPELL_RE.search(f)
                    or f.rstrip("/").endswith("/.claude/hooks"))
    for c in (resolved, _real(resolved)):
        if _protected_by_name(_fold(os.path.normpath(c))):
            return True
    return _same_file_as_protected(resolved)


def is_protected_or_ancestor(path_raw):
    """is_protected, or a folder that holds a protected path (moving or
    locking ~/.claude moves or locks the guard with it). Any .claude folder
    counts, since each can hold a settings file."""
    if is_protected(path_raw):
        return True
    resolved = resolve(path_raw)
    if resolved is None:
        return os.path.basename(_fold(str(path_raw)).rstrip("/")) == ".claude"
    for c in (resolved, _real(resolved)):
        f = _fold(os.path.normpath(c)).rstrip("/")
        if os.path.basename(f) == ".claude":
            return True
        for p in protected_concrete():
            pf = _fold(os.path.normpath(p))
            if pf.startswith(f + "/"):
                return True
    return False


def protected_why(path_raw):
    return ("the delete guard's own files (%s), which would end the rules it "
            "applies. The owner changes these in their own Terminal" % path_raw)


def _known_vault_content(resolved):
    """(v5.1) For a path inside the recorded vault root, True if it is a page
    (or other content file) that exists there, False if it is a new file in
    that vault, None if the path is not in the recorded vault at all. This
    tells an existing page, whose truncation is refused, from a new file,
    which may be written — for a path named by absolute path from anywhere."""
    k = known_root_of(resolved)
    if not k:
        return None
    try:
        # (v5.2) both in real-path form: a link into the wiki from elsewhere
        # resolved to the root but not to the page, so `> link/Page.md` read
        # as a new file
        rel = os.path.relpath(_real(resolved), _real(k))
    except ValueError:
        return False
    if rel.startswith(".."):
        return False
    cand = os.path.normpath(os.path.join(k, rel))
    return bool(os.path.isfile(cand) and _under_content(cand, k))


def is_content_path(path_raw):
    """True if path is (or names) an existing regular file under a content location."""
    resolved = resolve(path_raw)
    vault = STATE["vault"]
    # (v5.1) the recorded vault, whatever folder the command starts in and
    # even over ssh, judged on whether the page exists there
    if resolved:
        known = _known_vault_content(resolved)
        if known is not None:
            return known
        # (v5.2) a wiki that lives under a build root is a wiki: an existing
        # file in it is content wherever the command starts
        real = _real(os.path.normpath(resolved))
        folder = build_folder_of(real)
        if folder and _wiki_between(real, folder):
            return os.path.isfile(real)
    if vault and resolved and vault != NO_VAULT:
        if not os.path.isfile(resolved):
            return False
        for d in CONTENT_DIRS:
            if inside(resolved, os.path.join(vault, d)):
                return True
        for f in CONTENT_FILES:
            if os.path.realpath(resolved) == os.path.realpath(os.path.join(vault, f)):
                return True
        return False
    # (v5.1) A path that resolved but is in no known or local vault is not
    # content: the name fallback below is only for a path the guard could not
    # resolve at all (no cwd), where the relative spelling is all it has. This
    # stops a ~/.cache/<x>/raw/... path reading as content on the "/raw/" in it.
    if resolved is not None:
        return False
    text = os.path.normpath(expand(path_raw) or path_raw).lstrip("./")
    for d in CONTENT_DIRS:
        if text.startswith(d + "/") or ("/" + d + "/") in text:
            return True
    return os.path.basename(text) in CONTENT_FILES


# ---------------------------------------------------------------- tokens
def norm_head(t):
    # (v0.9.2) Lowercased. A Mac's filesystem is case-insensitive by default, so
    # `RM -rf wiki` and `/bin/RM` both run rm, while a head compared exactly
    # matched no rule at all. Every command name the guard knows is written in
    # lower case, and the original token is what any path check still uses.
    t = unicodedata.normalize("NFKC", t)
    b = os.path.basename(t).lower()
    # (v5.1) grm, gmv, gtimeout … are the GNU tools under Homebrew's prefix
    if b.startswith("g") and b[1:] in GNU_PREFIXED:
        return b[1:]
    return b


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


# (v0.9.2) All four spellings bash accepts. The delimiter is whichever group
# matched: <<\EOF and <<'E-O-F' and <<"END.OF" are as ordinary as <<EOF, and a
# guard that knows only the last of them can be handed a heredoc it will not
# read. A quoted delimiter may hold anything but its own quote.
HEREDOC_RE = re.compile(
    r"(?<![<\w])<<(?!<)-?\s*(?:"
    r"\\([A-Za-z_][A-Za-z0-9_]*)"
    r"|'([^'\n]+)'"
    r"|\"([^\"\n]+)\""
    r"|([A-Za-z_][A-Za-z0-9_]*)"
    r")")


def heredoc_quoted(text):
    """True if the first heredoc opened in `text` has a quoted delimiter.

    <<'EOF', <<"EOF" and <<\\EOF all stop the shell rewriting the body; a bare
    <<EOF does not. Asked by name because the groups moved when the pattern
    learned the other three spellings.
    """
    m = HEREDOC_RE.search(blank_noncode(text))
    if not m:
        return False
    return m.group(4) is None      # group 4 is the only unquoted spelling


def heredoc_delims(line):
    """The delimiters a line opens, reading only the parts of it that are code.

    Quoted text and comments are blanked first. Before v0.9.2 the raw line was
    searched, so `echo "mentions <<EOF"` opened a heredoc and every line after
    it was swallowed as the body — which is to say, never read as a command.
    """
    out = []
    for m in HEREDOC_RE.finditer(blank_noncode(line)):
        out.append(next(g for g in m.groups() if g is not None))
    return out


def blank_noncode(line):
    """The line with quoted runs and any trailing comment replaced by spaces.

    Length is kept so nothing that reads offsets is disturbed.
    """
    out, q, esc = [], None, False
    for i, ch in enumerate(line):
        if esc:
            esc = False
            out.append(" " if q else ch)
            continue
        if ch == "\\" and q != "'":
            esc = True
            out.append(ch if not q else " ")
            continue
        if q:
            out.append(" " if ch != q else ch)
            if ch == q:
                q = None
            continue
        if ch in "'\"":
            q = ch
            out.append(ch)
            continue
        if ch == "#" and (i == 0 or line[i - 1] in " \t;&|("):
            out.append(" " * (len(line) - i))
            break
        out.append(ch)
    return "".join(out)


def strip_heredocs(text):
    """Remove heredoc bodies; return (text_without_bodies, {phys_line: [bodies]})."""
    lines = text.split("\n")
    out, bodies = [], {}
    i = 0
    while i < len(lines):
        line = lines[i]
        delims = heredoc_delims(line)
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
        return " " if disposable_target(m.group(2), assigns) else m.group(0)
    return PY_DEL_CALL_RE.sub(rep, body)


# (v0.9.2) A `del` keyword that is a plain identifier used to be matched as a
# bare substring, so `unlink` fired on `unlinked`, on `unlink_later`, and on the
# word inside a string a script prints. Matching on word boundaries instead
# removes those and removes nothing real: every actual call or statement still
# has a boundary on each side. Keywords carrying a dot or a bracket
# (`os.remove`, `rmdir(`, `do shell script`) are left as substrings.
_BARE_WORD_RE = re.compile(r"^[a-z_][a-z0-9_]*$")
_KW_CACHE = {}


def _kw_present(k, low):
    if k not in _KW_CACHE:
        # `sync` may follow: node's entries are written as the bare verb and
        # its real calls carry that suffix, which the boundary would otherwise
        # reject along with the past participles this is here to drop.
        _KW_CACHE[k] = (re.compile(r"(?<![a-z0-9_])" + re.escape(k) + r"(?:sync)?(?![a-z0-9_])")
                        if _BARE_WORD_RE.match(k) else None)
    rx = _KW_CACHE[k]
    return bool(rx.search(low)) if rx is not None else (k in low)


# The standard atomic write is: make a temp file, write it, then os.replace() it
# over the target. Blocking os.replace( outright refused every carefully written
# Python file in a vault the moment it was edited — including the pack's own —
# and taught its owner to work around the guard. Where the same body shows a
# temp file being made, the replace is read as that idiom and is not a hit on
# its own; everything else in the body is still scanned exactly as before.
_ATOMIC_WRITE_RE = re.compile(r"mkstemp\(|namedtemporaryfile\(|tempfile\.")

# open("literal", "w") whose literal is plainly not vault content. A body used
# to be refused for any truncating open at all, wherever it wrote; a file has
# always been judged on the path. The two now agree, and an unresolvable target
# is still refused, since what cannot be read cannot be cleared.
PY_OPEN_W_CALL_RE = re.compile(
    r"open\(\s*[rR]?(['\"])([^'\"]*)\1\s*,\s*(?:mode\s*=\s*)?['\"]w[bt+]*['\"]")


def drop_safe_open_w(body):
    def rep(m):
        target = m.group(2)
        if UNRESOLVABLE_RE.search(target) or is_content_path(target) or is_protected(target):
            return m.group(0)
        return " "
    return PY_OPEN_W_CALL_RE.sub(rep, body)


# ---------------------------------------------------------------- python, read
# (v5.1) What a Python body hands to a process, read from its syntax tree.
PY_ARG = "$__py_arg"   # an argument the guard cannot read: never resolvable


def _py_name(func):
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return None


def _py_str(node, depth=0):
    """The string a node evaluates to when it is written out in full
    ('rm', 'r' + 'm', f'rm', ' '.join(['rm', '-rf'])), else None."""
    if node is None or depth > 20:
        return None
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        a, b = _py_str(node.left, depth + 1), _py_str(node.right, depth + 1)
        if a is not None and b is not None:
            return a + b
        return None
    if isinstance(node, ast.JoinedStr):
        parts = []
        for v in node.values:
            s = _py_str(v, depth + 1)
            if s is None:
                return None
            parts.append(s)
        return "".join(parts)
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr == "join" and len(node.args) == 1
            and isinstance(node.args[0], (ast.List, ast.Tuple))):
        sep = _py_str(node.func.value, depth + 1)
        items = [_py_str(e, depth + 1) for e in node.args[0].elts]
        if sep is not None and all(i is not None for i in items):
            return sep.join(items)
    return None


def _py_argv(node, names, depth=0):
    """A command line from an argv-shaped list or tuple (or a name bound to
    one, or a sum of them), or a literal string; None when there is none."""
    if node is None or depth > 6:
        return None
    if isinstance(node, ast.Name) and names and node.id in names:
        return _py_argv(names[node.id], None, depth + 1)
    if isinstance(node, (ast.List, ast.Tuple)):
        parts = []
        for e in node.elts:
            s = None if isinstance(e, ast.Starred) else _py_str(e)
            parts.append(shlex.quote(s) if s is not None else PY_ARG)
        return " ".join(parts) if parts else None
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        a = _py_argv(node.left, names, depth + 1)
        b = _py_argv(node.right, names, depth + 1)
        if a is not None or b is not None:
            return "%s %s" % (a or PY_ARG, b or PY_ARG)
        return None
    return _py_str(node)


def _py_import_map(tree):
    """(modules, spawn_names): names bound to a spawn module (import os as o,
    import subprocess as sp) and names bound directly to a spawn function
    (from subprocess import run; from os import system as s)."""
    modules = dict(zip(PY_SPAWN_MODULES, PY_SPAWN_MODULES))
    spawn_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name.split(".")[0] in PY_SPAWN_MODULES:
                    modules[a.asname or a.name] = a.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom):
            mod = (node.module or "").split(".")[0]
            if mod in PY_SPAWN_MODULES:
                for a in node.names:
                    if a.name in PY_SPAWN_NAMES or a.name == "Popen":
                        spawn_names.add(a.asname or a.name)
                    if a.name in PY_SPAWN_MODULES:
                        modules[a.asname or a.name] = a.name
    return modules, spawn_names


def _is_spawn_call(node, modules, spawn_names):
    """True if this Call node starts a process."""
    f = node.func
    if isinstance(f, ast.Name):
        return f.id in spawn_names or f.id == "Popen"
    if isinstance(f, ast.Attribute):
        if f.attr in PY_SPAWN_ATTRS or f.attr == "Popen" or f.attr in PY_SPAWN_NAMES:
            base = f.value
            if isinstance(base, ast.Name):
                return (base.id in modules or base.id in PY_SPAWN_MODULES
                        or f.attr in ("run", "call", "check_call", "check_output",
                                      "popen", "system", "getoutput")
                        or f.attr.startswith(("exec", "spawn", "posix_spawn")))
            return True
    return False


def py_command_lines(raw):
    """Command lines the spawn calls in a Python body would start, read from
    the syntax tree: the argv/command argument of each, or the program+argv of
    os.exec*/spawn*. PY_ARG stands for a part the guard cannot read."""
    try:
        tree = ast.parse(raw)
    except (SyntaxError, ValueError, MemoryError, RecursionError):
        out = []
        for m in PY_SPAWN_CALL_TEXT_RE.finditer(raw):
            arg = m.group(1)
            if arg[:1] == "[":
                parts = []
                for item in arg[1:-1].split(","):
                    item = item.strip()
                    if not item:
                        continue
                    lit = QUOTED_RE.fullmatch(item.lstrip("rRbBuUfF"))
                    parts.append(shlex.quote(lit.group(1) if lit.group(1) is not None
                                             else lit.group(2)) if lit else PY_ARG)
                if parts:
                    out.append(" ".join(parts))
            else:
                lit = QUOTED_RE.search(arg)
                if lit:
                    out.append(lit.group(1) if lit.group(1) is not None else lit.group(2))
        return out, None
    modules, spawn_names = _py_import_map(tree)
    names, out, unreadable = {}, [], False
    for node in ast.walk(tree):
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)):
            names[node.targets[0].id] = node.value
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not _is_spawn_call(node, modules, spawn_names):
            continue
        fname = _py_name(node.func) or ""
        got = False
        cands = list(node.args[:1]) + [kw.value for kw in node.keywords
                                       if kw.arg in ("args", "cmd", "command")]
        for a in cands:
            c = _py_argv(a, names)
            if c:
                out.append(c)
                got = True
        if fname.startswith(("exec", "spawn", "posix_spawn")):
            consts = [s for s in (_py_str(a) for a in node.args) if s is not None]
            if len(consts) > 1:
                out.append(" ".join(shlex.quote(s) for s in consts[1:]))
                got = True
            for a in node.args:
                if isinstance(a, (ast.List, ast.Tuple)):
                    c = _py_argv(a, names)
                    if c:
                        out.append(c)
                        got = True
        if not got:
            unreadable = True
    # getattr(x, 'system')(...) and the like
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and _py_name(node.func) == "getattr"
                and len(node.args) >= 2):
            s = _py_str(node.args[1])
            if s is None or s.lower() in PY_RISKY_ATTRS:
                unreadable = True
    return out, unreadable


def _scan_lines_quietly(cmds, depth):
    """scan_command over command lines lifted out of code: the folder is left
    as it was and script files are not followed (a literal is read as a
    command line, not chased into further files)."""
    saved = (STATE["cwd"], STATE.get("no_files"), STATE.get("chdir"))
    try:
        STATE["no_files"] = True
        for cmd in cmds:
            if not cmd or not cmd.strip() or len(cmd) > 4000 or cmd == PY_ARG:
                continue
            r = scan_command(cmd, depth)
            STATE["cwd"] = saved[0]
            if r:
                return r
    finally:
        STATE["cwd"], STATE["no_files"], STATE["chdir"] = saved
    return None


def py_spawn_hit(raw, low, is_file, lang):
    """(v5.1) Python (or unread code) that starts another process to run a
    never-list command. A bare `import subprocess`, or a spawn of an ordinary
    command (git status, date), is not refused: the command line the spawn
    carries is read and scanned, and only a never-list command is blocked.
    A spawn whose argument the guard cannot read is refused when the body also
    names a never-list token, since Bash(python3:*) runs with no prompt."""
    cmds, unreadable = py_command_lines(raw)
    r = _scan_lines_quietly(cmds, 2)
    if r:
        return "starts a process whose command line %s" % r
    if unreadable and FILE_DELETER_RE.search(raw):
        return ("starts a process with a command the guard cannot read, beside a "
                "never-list word")
    return None


def _literal_protected_file(lit):
    """True only when the literal RESOLVES to one of the guard's own files
    (not a loose substring match), so a page whose prose mentions the guard is
    not caught — only a literal that is a path to settings.json or a hook."""
    if not lit or len(lit) > 300:
        return False
    p = resolve(lit)
    if p is None:
        f = _fold(lit)
        return bool(SETTINGS_RE.search(f) or re.search(r"\.claude/+hooks/+[^/\s]+$", f)
                    or f.rstrip("/").endswith("/.claude/hooks")
                    or re.search(r"\.codex/+hooks", f))
    for c in (os.path.normpath(p), _real(p)):
        if _protected_by_name(_fold(c)):
            return True
    return False


def self_write_hit(raw):
    """(v5.1) Inline code that WRITES to one of the guard's own files: a string
    literal resolving to the guard, settings.json/.local.json or a hook, used
    as the target of a write (open(<p>, 'w'), writeFileSync(<p>, …), etc.). A
    literal that merely appears in the body — a page path being edited, prose
    naming the guard, or a settings file being READ — is not enough; the write
    must sit against the protected path."""
    have_protected = False
    unambig = SELF_WRITE_UNAMBIG_RE.search(raw)
    for m in QUOTED_RE.finditer(raw):
        lit = m.group(1) if m.group(1) is not None else m.group(2)
        if not lit or not _literal_protected_file(lit):
            continue
        have_protected = True
        post = raw[m.end():m.end() + 24]
        if SELF_WRITE_AFTER_RE.search(post):   # open('<prot>', 'w') and kin
            return "code that writes to the delete guard's own files (%s)" % lit[:60]
    # A write-only verb anywhere, with a protected literal anywhere: these verbs
    # never read, so the pairing is a write to the guard.
    if have_protected and unambig:
        return "code that writes to the delete guard's own files (%s)" % unambig.group(0)
    # Path.home()/'.claude'/'settings.json' from adjacent literals plus a write.
    if PATHLIB_SELF_RE.search(raw) and PATHLIB_WRITE_RE.search(raw):
        return "code that writes to the delete guard's own files (joined path)"
    return None


def keyword_hit(body, lang=None, is_file=False, assigns=None):
    lang = LANG_ALIAS.get(lang, lang) or "unknown"
    if lang == "shell":
        return None
    spec = LANGS.get(lang, LANGS["unknown"])
    raw_body = body
    if lang in ("python", "unknown"):
        body = drop_throwaway_py_calls(body, assigns)
    low = body.lower()
    if lang in ("python", "unknown"):
        if _ATOMIC_WRITE_RE.search(low):
            low = low.replace("os.replace(", " ")
        if not is_file:
            low = drop_safe_open_w(low)
    for k in spec["del"]:
        if _kw_present(k, low):
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
    # (v5.1) inline code writing to the guard's own files, and code that starts
    # a process to run a never-list command
    if not is_file:
        w = _safe(self_write_hit, raw_body)
        if w:
            return w
    if lang in ("python", "unknown"):
        k = _safe(py_spawn_hit, raw_body, raw_body.lower(), is_file, lang)
        if k:
            return k
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
    if STATE.get("no_files"):
        return None  # (v5.1) a command line lifted out of code: not followed
    if STATE["files"] >= MAX_FILES_PER_CALL:
        # (v0.9.2) Reaching the cap used to mean "nothing found", which is the
        # one answer the guard cannot honestly give about a file it has not
        # read: six harmless scripts and a seventh that emptied the wiki went
        # through together. The cap is still a cap; it is now a refusal.
        return ("this command runs more script files than the guard reads in one go "
                "(%d); run them in separate commands so each can be read"
                % MAX_FILES_PER_CALL)
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


# A shell or interpreter with no script, no inline body and nothing arriving
# on stdin has nothing to run: it sits open, and ChatGPT's agent can type into
# it afterwards (write_stdin) without the hook being asked again.
STDIN_OPS = ("<", "<<", "<<<", "<&", "<>")
SHELL_INFO = {"--version", "--help"}
PY_INFO = {"-V", "-VV", "--version", "-h", "-?", "--help", "--help-all",
           "--help-env", "--help-xoptions"}
PY_BOOL_FLAGS = set("bBdEiIOqsSuvx")
INTERP_SESSION_FLAGS = {"-i", "--interactive", "-a", "-"}


def stdin_supplied(seg):
    """True if this step is given its input in the command itself."""
    if seg is None:
        return False
    return bool(seg.piped_in or any(op in STDIN_OPS for op, _ in seg.redirs))


def bare_session(b):
    return ("starts %s with nothing to run, which leaves a session open that "
            "the guard cannot see into; pass the command with -c (or -e), or "
            "name a script file" % b)


def python_stays_open(rest):
    """True for `python -i …`: the session stays open after the script."""
    i = 0
    while i < len(rest):
        t = rest[i]
        if (not t.startswith("-") or t in ("-", "--")
                or t.startswith("-c") or t.startswith("-m")):
            return False
        if t in ("-W", "-X", "-Q"):
            i += 2
            continue
        if (not t.startswith("--") and "i" in t[1:]
                and all(ch in PY_BOOL_FLAGS for ch in t[1:])):
            return True
        i += 1
    return False


# ---------------------------------------------------------------- wrappers
def peel(toks, assigns, depth=0, writes=None):
    """(basename-head, original head, rest) after peeling wrappers and keywords.
    writes, when given, collects (path, appends) for files a wrapper itself
    writes (script's typescript, time -o)."""
    if writes is None:
        writes = []
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
                        return peel(inner + toks[i + 2:], assigns, depth + 1, writes)
                    if t2.startswith("-S") or t2.startswith("--split-string="):
                        val = t2[2:] if t2.startswith("-S") else t2.split("=", 1)[1]
                        try:
                            inner = shlex.split(val)
                        except ValueError:
                            inner = val.split()
                        return peel(inner + toks[i + 1:], assigns, depth + 1, writes)
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
        # (v0.9.2) Three more wrappers that run the command handed to them, in
        # the same way as env and nohup. `arch -x86_64 rm -rf wiki` was read as
        # a call to arch, which has no rule, and went straight through.
        # (v5.1) Their option arguments: `stdbuf -o L rm …` and `arch -d VAR
        # rm …` left L and VAR read as the command.
        if b in ("arch", "stdbuf"):
            i += 1
            while i < n and toks[i].startswith("-"):
                if toks[i] == "--":
                    i += 1
                    break
                if b == "arch" and toks[i] in ("-arch", "-e", "-d"):
                    i += 2
                elif b == "stdbuf" and toks[i] in ("-i", "-o", "-e"):
                    i += 2
                else:
                    i += 1
            continue
        if b == "script":
            # macOS: script [options] [file [command ...]]. The first non-flag
            # is the typescript file and the command comes after it.
            # (v5.1) The typescript is written (truncated unless -a), so it is
            # judged as a redirect target; util-linux script -c runs a string.
            i += 1
            appends = False
            while i < n and toks[i].startswith("-"):
                if toks[i] in ("-c", "--command") and i + 1 < n:
                    try:
                        inner = shlex.split(toks[i + 1])
                    except ValueError:
                        inner = toks[i + 1].split()
                    return peel(inner, assigns, depth + 1, writes)
                if not toks[i].startswith("--") and "a" in toks[i][1:]:
                    appends = True
                i += 2 if toks[i] in ("-t", "-T", "-E", "-I", "-O", "-B") else 1
            if i < n:
                writes.append((toks[i], appends))
                i += 1
            continue
        if b in ("time", "nohup", "builtin", "exec", "caffeinate"):
            i += 1
            appends = False
            while i < n and toks[i].startswith("-"):
                t2 = toks[i]
                if t2 == "--":
                    i += 1
                    break
                if b == "exec" and t2 == "-a":
                    i += 2
                elif b == "caffeinate" and t2 in ("-t", "-w"):
                    i += 2
                elif b == "time" and t2 in ("-o", "--output", "-f", "--format"):
                    # (v5.1) time -o FILE writes FILE; -f takes a format
                    if t2 in ("-o", "--output") and i + 1 < n:
                        writes.append((toks[i + 1], appends))
                    i += 2
                elif b == "time" and t2.startswith("--output="):
                    writes.append((t2.split("=", 1)[1], appends))
                    i += 1
                else:
                    if b == "time" and (t2 in ("-a", "--append")):
                        appends = True
                    i += 1
            continue
        # (v5.1) Wrappers the guard did not peel at all: each runs the command
        # after its options (and, for timeout, after the duration).
        if b == "timeout":
            i += 1
            while i < n and toks[i].startswith("-") and toks[i] != "-":
                t2 = toks[i]
                if t2 == "--":
                    i += 1
                    break
                i += 2 if t2 in ("-s", "--signal", "-k", "--kill-after") else 1
            i += 1  # the duration
            continue
        if b == "taskpolicy":
            i += 1
            while i < n and toks[i].startswith("-"):
                i += 2 if toks[i] in ("-d", "-g", "-c", "-p", "-m", "-j", "-P", "-S",
                                      "-t", "-l") else 1
            continue
        if b == "xcrun":
            i += 1
            while i < n and toks[i].startswith("-"):
                t2 = toks[i]
                if t2 in ("-f", "--find"):
                    return "echo", "echo", []  # prints a tool's path, runs nothing
                if t2 == "--":
                    i += 1
                    break
                i += 2 if t2 in ("--sdk", "-sdk", "--toolchain", "-toolchain") else 1
            continue
        if b == "sandbox-exec":
            i += 1
            while i < n and toks[i].startswith("-"):
                i += 2 if toks[i] in ("-f", "-n", "-p", "-D") else 1
            continue
        if b in ("unbuffer", "chronic"):
            i += 1
            while i < n and toks[i].startswith("-"):
                i += 1
            continue
        if b == "watch":
            # procps watch joins what follows its options and runs it with sh -c
            i += 1
            while i < n and toks[i].startswith("-"):
                if toks[i] == "--":
                    i += 1
                    break
                i += 2 if toks[i] in ("-n", "--interval", "-q", "--equexit") else 1
            try:
                inner = shlex.split(" ".join(toks[i:]))
            except ValueError:
                inner = " ".join(toks[i:]).split()
            if not inner or depth >= 4:
                return "", "", []
            return peel(inner, assigns, depth + 1, writes)
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
                return peel(inner + toks[i + 1:], assigns, depth + 1, writes)
        return b, t, toks[i + 1:]
    return "", "", []


def rule_wrapper_writes(writes):
    """(v5.1) A file a wrapper writes on its own account: script's typescript,
    time -o. Judged as a redirect onto that file would be."""
    for target, appends in writes:
        if is_protected(target):
            return "a wrapper writes over %s" % protected_why(target)
        if not appends and is_content_path(target):
            return "a wrapper writes over the vault file %s" % target
    return None


# ---------------------------------------------------------------- rules
def rule_redirects(seg):
    for op, target in seg.redirs:
        # Any write at all, not only a truncating one: an append to the file
        # that registers the guard leaves JSON that cannot be parsed, and a
        # registration that cannot be parsed is a guard that does not run.
        if op in REDIR_OPS and op not in ("<", "<<", "<<<", "<&") and target and is_protected(target):
            return ("that writes to the delete guard itself (%s), which would end every "
                    "rule it applies. The owner changes it in their own Terminal" % target)
        if op in TRUNC_OPS and target and is_content_path(target):
            return "a `>` redirect truncates the vault file %s" % target
    return None


def _remote_scan(home, fn):
    """(v5.1) Run fn as if on the remote Mac: its home, ~ expanding there, the
    folder starting there, and no vault but the known roots."""
    saved = (STATE["cwd"], STATE["vault"], STATE.get("remote"), os.environ.get("HOME"))
    try:
        os.environ["HOME"] = home
        STATE["cwd"] = home
        STATE["remote"] = True
        STATE["vault"] = known_root_of(home) or NO_VAULT
        return fn()
    finally:
        STATE["cwd"], STATE["vault"], STATE["remote"] = saved[:3]
        if saved[3] is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = saved[3]


# ssh -o options whose value is a command: run here (ProxyCommand,
# LocalCommand, KnownHostsCommand) or there (RemoteCommand).
SSH_LOCAL_CMD_OPTS = ("proxycommand", "localcommand", "knownhostscommand")


def rule_ssh(b, rest, depth, seg=None):
    """(v5.1) ssh reads options after the destination as well as before it
    (`ssh host -t cmd`, `ssh host -- cmd`), and the remote command runs in
    the remote home: it is read there, with the known vault roots in force,
    not against this Mac's folder. Code fed to ssh on stdin with no command
    is a script for the remote shell, and is read as one."""
    if b != "ssh":
        return None
    i, n = 0, len(rest)
    host, user, remote, opts_done = None, None, [], False
    remote_opt = None
    while i < n:
        t = rest[i]
        if not opts_done and t == "--":
            opts_done = True
            i += 1
            continue
        if not opts_done and t.startswith("-") and len(t) > 1:
            j, used_next = 1, False
            while j < len(t):
                ch = t[j]
                if ("-" + ch) in SSH_ARG_OPTS:
                    val = t[j + 1:]
                    if not val and i + 1 < n:
                        val = rest[i + 1]
                        used_next = True
                    if ch == "l":
                        user = val
                    if ch == "o" and val:
                        key, _, v = val.partition("=")
                        if not _:
                            key, _, v = val.partition(" ")
                        key = key.strip().lower()
                        v = v.strip()
                        if key in SSH_LOCAL_CMD_OPTS and v:
                            r = scan_command(v, depth + 1)
                            if r:
                                return "ssh -o %s runs a command on this Mac: %s" % (key, r)
                        if key == "remotecommand" and v:
                            remote_opt = v
                    break
                j += 1
            i += 2 if used_next else 1
            continue
        if host is None:
            host = t
            i += 1
            continue
        remote = rest[i:]
        break
    if host is None:
        return None
    if host.lower().startswith("ssh://"):
        host = host[6:].split("/", 1)[0]
        if host.count(":") == 1:
            host = host.split(":", 1)[0]
    if "@" in host:
        user, host = host.rsplit("@", 1)
    if not user:
        # ssh logs in as this Mac's user unless told otherwise
        user = os.environ.get("USER") or os.environ.get("LOGNAME")
    # The folder the remote command starts in: /Users/<user> when a user is
    # named, else this Mac's own home. The guard keeps no list of machines.
    home = (("/Users/" + user if user and re.match(r"^[A-Za-z0-9._-]+$", user)
             else None)
            or LOCAL_HOME)
    text = " ".join(remote) if remote else remote_opt
    if text:
        r = _remote_scan(home, lambda: scan_command(text, depth + 1))
        if r:
            return "ssh remote command: %s" % r
        return None
    if seg is not None and stdin_supplied(seg):
        texts = list(seg.line.bodies) if seg.line else []
        for op, target in seg.redirs:
            if op == "<<<":
                texts.append(target)
            elif op == "<":
                p = resolve(target)  # the file is read here, on this Mac
                if p and os.path.isfile(p):
                    try:
                        with open(p, "rb") as fh:
                            texts.append(fh.read(MAX_FILE_BYTES).decode("utf-8", "replace"))
                    except OSError:
                        pass
        for body in texts:
            r = _remote_scan(home, lambda: scan_command(body, depth + 1))
            if r:
                return "ssh remote shell reading stdin: %s" % r
        if seg.piped_in and seg.line:
            probe = Seg()
            probe.toks, probe.piped_in, probe.line = list(seg.toks), True, seg.line
            r = _remote_scan(home, lambda: scan_stdin_code(probe, "shell", depth))
            if r:
                return "ssh remote shell reading stdin: %s" % r
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
    if not stdin_supplied(seg):
        if any(t in SHELL_INFO for t in rest):
            return None  # prints and exits
        return bare_session(b)
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
    if python_stays_open(rest) and not stdin_supplied(seg):
        return ("starts %s with -i, which keeps a session open after the "
                "script that the guard cannot see into; run it without -i" % b)
    i, n = 0, len(rest)
    while i < n:
        t = rest[i]
        if t == "-":
            if not stdin_supplied(seg):
                return bare_session(b)
            return scan_stdin_code(seg, "python", depth)
        if t == "--":
            i += 1
            break
        if t in PY_INFO:
            return None  # prints and exits
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
    if not stdin_supplied(seg):
        return bare_session(b)
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
    if not stdin_supplied(seg):
        # Only the plainly interactive forms: no argument at all, or nothing
        # but a flag that asks for a session (`node --test`, `php -m` and the
        # like do their work and exit).
        if all(t in INTERP_SESSION_FLAGS for t in rest):
            return bare_session(b)
    return scan_stdin_code(seg, b, depth)


# A redirect inside an awk program: `print > "wiki/Index.md"`. Truncating only;
# `>>` appends, as it does in the shell.
AWK_REDIR_RE = re.compile(r"(?<!>)>\s*(['\"])([^'\"]+)\1")
# Applications that run what they are given rather than showing it.
RUNNING_APPS = ("terminal", "iterm", "hyper", "warp", "kitty", "alacritty", "wezterm")
# Extensions macOS executes when they are opened.
RUNNING_EXTS = (".command", ".app", ".scpt", ".applescript", ".workflow", ".term")


def rule_open(b, rest):
    """(v0.9.2) `open` hands a file to an application, and some of them run it.

    `open -a Terminal x.sh` runs the script in a window the hook never sees, and
    a .command file runs on being opened at all. Opening a page, a folder or a
    URL is ordinary work and stays so.
    """
    if b != "open":
        return None
    i = 0
    while i < len(rest):
        tok = rest[i]
        if tok in ("-a", "--application") and i + 1 < len(rest):
            app = os.path.basename(rest[i + 1]).lower()
            if any(k in app for k in RUNNING_APPS):
                return ("open -a %s runs what it is given, in a window outside this "
                        "guard" % rest[i + 1])
            i += 2
            continue
        if not tok.startswith("-"):
            if os.path.splitext(tok)[1].lower() in RUNNING_EXTS:
                return "open runs %s rather than showing it" % tok
        i += 1
    return None


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
        # (v0.9.2) awk redirects inside its own program — print > "file" — and
        # the shell never sees that `>`, so no redirect rule applied to it.
        for m in AWK_REDIR_RE.finditer(t):
            target = m.group(2)
            if is_content_path(target) or is_protected(target):
                return "awk writes over %s with its own redirect" % target
        k = keyword_hit(t, "awk")
        return ("awk program contains %s" % k) if k else None
    return None


def rule_other_interp(b, rest, seg, depth):
    if b not in OTHER_INTERP:
        return None
    if not rest and not stdin_supplied(seg):
        return bare_session(b)
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
        if targets and all(disposable_target(t, assigns, allow_root) for t in targets):
            return None  # every target is throwaway, or build material
        return ("deletes files (`%s`; only throwaway targets under /tmp, "
                "$TMPDIR, ~/.cache or ~/Library/Caches are allowed, or files "
                "inside a build folder under ~/Apps/<name>/ (never the folder "
                "itself, its .git, data or state), and every target must be a "
                "resolvable path. Finished material in the wiki moves, and the "
                "owner removes a thing by hand)" % head)
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
        if start_paths and all(disposable_target(p, assigns, True) for p in start_paths):
            return None
        return ("find -delete removes files (only under throwaway roots or inside "
                "a build folder is it allowed)")
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
            if is_content_path(rest[i + 1]) or is_protected(rest[i + 1]):
                return "find %s overwrites the vault file %s" % (t, rest[i + 1])
        i += 1
    return None


def _source_base(s):
    base = re.split(r"[*?\[]", s)[0]
    if base != s:
        base = os.path.dirname(base) or "."
    return base or "."


def _content_in_known_root(path_raw):
    """True if the path names content (a wiki/raw/Clippings/Daily Notes item or
    folder, or an instruction file) inside a known vault root, wherever the
    session is. outputs/, scripts/, archive/ are not content: copying a render
    out to another drive is ordinary work, moving a page out is not."""
    r = resolve(_source_base(path_raw))
    if r is None:
        return False
    k = known_root_of(r)
    return bool(k and _under_content(r, k))


def _known_root_move(cmd, sources, dest):
    """(v5.1) A source named by absolute path into a known vault must land
    inside that same vault, wherever the session started (cwd /tmp, ~, or a
    remote home). Only fires when the destination RESOLVES and is provably
    outside the vault; an unresolvable destination falls back to the existing
    contract (which allows it), so an in-vault move with a variable in the
    path is not newly refused."""
    rd = resolve(dest)
    if rd is None:
        return None
    for s in sources:
        if not _content_in_known_root(s):
            continue
        k = known_root_of(resolve(_source_base(s)))
        if k and not in_root(rd, k):
            return "%s takes a vault page out of the vault (%s -> %s)" % (cmd, s, dest)
    return None


def _lands_on_protected(src_raw, dest_resolved, contents):
    """Where a copy into a folder puts things: the source's own name in it, or
    (contents=True: `src/`, ditto) each entry of the source folder."""
    names = []
    if contents:
        sp = resolve(src_raw)
        if sp and os.path.isdir(sp):
            try:
                names = os.listdir(sp)
            except OSError:
                names = []
    else:
        names = [os.path.basename(src_raw.rstrip("/"))]
    for nm in names:
        if nm and nm not in (".", ".."):
            cand = os.path.join(dest_resolved, nm)
            if is_protected_or_ancestor(cand):
                return cand
    return None


def _protected_move_copy(cmd, flags, sources, dest):
    """(v5.1) mv/cp/git mv/install/ln and the guard's own files."""
    links = any(f in ("--link", "--symbolic-link") or
                (f.startswith("-") and not f.startswith("--") and
                 ("l" in f[1:] or "s" in f[1:])) for f in flags)
    for s in sources:
        if cmd in ("mv", "git mv") and is_protected_or_ancestor(s):
            return "%s moves %s" % (cmd, protected_why(s))
        if (cmd == "ln" or (cmd == "cp" and links)) and is_protected(s):
            return "%s links to %s" % (cmd, protected_why(s))
    if dest is None:
        return None
    if is_protected(dest) or (cmd == "ln" and is_protected_or_ancestor(dest)):
        return "%s writes over %s" % (cmd, protected_why(dest))
    rd = resolve(dest)
    if rd and (os.path.isdir(rd) or dest.endswith("/")):
        for s in sources:
            contents = s.endswith("/") or s.endswith("/.")
            hit = _lands_on_protected(s, rd, contents)
            if hit:
                return "%s puts %s in place of %s" % (cmd, s, protected_why(hit))
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
    # (v0.9.2) The guard's own file and its registration, whether or not one is
    # there now. An assistant putting a file at that path is replacing the
    # guard just as surely when the path is empty as when it is not.
    if dest is not None and is_self_path(dest):
        return "%s writes over the delete guard itself (%s)" % (cmd, dest)
    r = _protected_move_copy(cmd, flags, sources, dest)
    if r:
        return r
    # (v5.2) a build folder itself, its .git, data and state are never moved
    # by the assistant, whatever the destination; copying them is fine
    if cmd in ("mv", "git mv"):
        for s in sources:
            why = build_keep_reason(s)
            if why:
                return "%s %s" % (cmd, why)
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
    if vault_bound:
        r = _known_root_move(cmd, sources, dest)
        if r:
            return r
    if no_clobber:
        return None
    resolved = resolve(dest)
    if resolved is None:
        return None
    # (v5.2) a generated file inside a build folder may be written over
    if os.path.isfile(resolved):
        if build_target(dest):
            return None
        return "%s would silently overwrite the existing file %s" % (cmd, dest)
    if os.path.isdir(resolved):
        for s in sources:
            if any(ch in s for ch in "*?[$"):
                continue
            cand = os.path.join(resolved, os.path.basename(s.rstrip("/")))
            if os.path.isfile(cand):
                if build_target(cand):
                    continue
                return ("%s would silently overwrite the existing file %s"
                        % (cmd, os.path.join(dest, os.path.basename(s))))
    return None


def rule_move_copy(b, rest):
    if b in ("mv", "cp"):
        return _clobber_checks(b, rest, True)
    if b == "ditto":
        # (v0.9.2) Out of the shredder list, where nothing it did could be
        # allowed, and given the rule its behaviour actually calls for. ditto
        # copies, so copying OUT of the vault — the usual reason anyone reaches
        # for it, making a backup — is ordinary work. Copying IN is refused
        # whatever the destination is, folder as well as file, because ditto
        # writes a whole tree over a destination and what that leaves behind is
        # not something the guard can read off the command line.
        operands = [t for t in rest if not t.startswith("-")]
        for t in reversed(rest):
            if t.startswith("-"):
                continue
            d = resolve(t)
            if d and STATE["vault"] and inside(d, STATE["vault"]):
                return "ditto writes a whole tree into the vault (%s)" % t
            # (v5.1) the known vaults whatever the cwd, and the guard's files
            if d and known_root_of(d):
                return "ditto writes a whole tree into the vault (%s)" % t
            if is_protected_or_ancestor(t) and (is_protected(t) or os.path.basename(
                    _fold(t).rstrip("/")) == ".claude"):
                return "ditto writes into %s" % protected_why(t)
            if d and os.path.isdir(d):
                for s in operands[:-1]:
                    hit = _lands_on_protected(s, d, True)
                    if hit:
                        return "ditto puts %s in place of %s" % (s, protected_why(hit))
            break
        return None
    if b == "install":
        return _clobber_checks(b, rest, False)
    if b == "ln":
        return _clobber_checks(b, rest, False)
    return None


def rule_tee(b, rest):
    if b != "tee":
        return None
    # (v5.1) an append onto the guard's own files is refused as well: one more
    # line in settings.json is JSON that no longer parses, and no guard
    for t in rest:
        if not t.startswith("-") and is_protected(t):
            return "tee writes to %s" % protected_why(t)
    if any(t in ("-a", "--append") or (t.startswith("-") and not t.startswith("--")
                                        and "a" in t[1:]) for t in rest):
        return None
    for t in rest:
        if not t.startswith("-") and is_self_path(t):
            return "tee without -a writes over the delete guard itself (%s)" % t
        if not t.startswith("-") and is_content_path(t):
            return "tee without -a overwrites the vault file %s" % t
    return None


def _git_base(d, base):
    """The folder `git -C d` works in, given the folder before it."""
    e = expand(d)
    if e is None:
        return None
    if not os.path.isabs(e):
        anchor = base or STATE["cwd"]
        if not anchor:
            return None
        e = os.path.join(anchor, e)
    return os.path.normpath(e)


# (v5.1) `git -c key=value` with a key whose value git runs as a command.
GIT_CMD_CONFIG_RE = re.compile(
    r"^(?:core\.(?:sshcommand|pager|editor|fsmonitor|askpass|hookspath)"
    r"|sequence\.editor|diff\.external|gpg\.program|gpg\.\w+\.program"
    r"|credential\.helper|credential\..+\.helper|pager\..+|alias\..+"
    r"|(?:diff|filter|merge)\..+\.(?:textconv|command|clean|smudge|process|driver)"
    r"|uploadpack\.packobjectshook|core\.alternaterefscommand)$")
GIT_CMD_ENV = ("GIT_SSH_COMMAND", "GIT_SSH", "GIT_EDITOR", "GIT_PAGER",
               "GIT_EXTERNAL_DIFF", "GIT_ASKPASS", "GIT_SEQUENCE_EDITOR")


def _git_config_value(key, val, depth):
    key = key.lower()
    if key == "core.hookspath":
        if val and val != "scripts/hooks":
            return "git -c core.hooksPath re-points the hooks away from scripts/hooks"
        return None
    if key.startswith("alias."):
        if val.startswith("!"):
            r = scan_command(val[1:], depth + 1)
        else:
            r = scan_command("git " + val, depth + 1)
        return ("git alias to a destructive command: %s" % r) if r else None
    r = scan_command(val, depth + 1)
    return ("git -c %s runs a command that %s" % (key, r)) if r else None


def rule_git(b, rest, depth, assigns=None):
    """(v5.1) -C and --work-tree are followed, so a path is judged in the
    folder git will read it in; `git -c` values git runs are read."""
    if b != "git":
        return None
    i, n = 0, len(rest)
    base, base_bad, worktree = None, False, None
    while i < n and rest[i].startswith("-"):
        t = rest[i]
        if t == "-C" and i + 1 < n:
            nb = _git_base(rest[i + 1], base)
            if nb is None:
                base_bad = True
            else:
                base = nb
            i += 2
            continue
        if t == "--work-tree" and i + 1 < n:
            worktree = rest[i + 1]
            i += 2
            continue
        if t.startswith("--work-tree="):
            worktree = t.split("=", 1)[1]
            i += 1
            continue
        # (v5.2) --git-dir and core.worktree point git at another repository
        # from wherever the command starts, so the folder is not where the
        # command is judged; the build-folder freedoms never apply then
        if t == "--git-dir" and i + 1 < n:
            base_bad = True
            i += 2
            continue
        if t.startswith("--git-dir="):
            base_bad = True
            i += 1
            continue
        if t == "-c" and i + 1 < n:
            key, _sep, val = rest[i + 1].partition("=")
            if key.lower() in ("core.worktree", "core.gitdir"):
                base_bad = True
            if GIT_CMD_CONFIG_RE.match(key.lower()) and val:
                r = _git_config_value(key, val, depth)
                if r:
                    return r
            i += 2
            continue
        if t in GIT_GLOBAL_ARG or (t.startswith("-c") and len(t) == 2):
            i += 2
        else:
            i += 1
    for name in GIT_CMD_ENV:
        val = (assigns or {}).get(name)
        if val:
            r = scan_command(val, depth + 1)
            if r:
                return "%s runs a command that %s" % (name, r)
    if worktree is None and assigns:
        worktree = assigns.get("GIT_WORK_TREE")
    if assigns and (assigns.get("GIT_DIR") or assigns.get("GIT_WORK_TREE")):
        base_bad = True  # (v5.2) the same, set in the environment
    if i >= n:
        return None
    saved = STATE["cwd"]
    try:
        if base is not None:
            STATE["cwd"] = base
        return _git_sub(rest, i, depth, base_bad, worktree)
    finally:
        STATE["cwd"] = saved


def _git_sub(rest, i, depth, base_bad=False, worktree=None):
    sub = rest[i].lower()
    args = rest[i + 1:]
    low = [a.lower() for a in args]
    if sub == "rm":
        return "git rm removes tracked files"
    # (v0.9.2) Three of these have forms that destroy nothing, and refusing
    # them taught their user that the guard is wrong about git — which is how a
    # guard stops being read. `git clean -n` lists and removes nothing;
    # `git rebase --abort` and `--quit` end a rebase and put the branch back;
    # `git restore --staged` unstages and leaves the working tree alone. The
    # destructive forms of all three are refused exactly as before.
    if sub == "clean" and any(a == "--dry-run" or (a.startswith("-") and not a.startswith("--")
                                                   and "n" in a[1:]) for a in low):
        return None
    if sub == "rebase" and any(a in ("--abort", "--quit") for a in low):
        return None
    # -S/-W, not -s/-w: in git restore, -s is --source and takes a tree, so the
    # case matters and `low` cannot be used for this one.
    if sub == "restore" and ("--staged" in low or "-S" in args) \
            and "--worktree" not in low and "-W" not in args:
        return None
    # (v5.2) in a build folder's own repository, restoring a file, stashing
    # and checking out paths are ordinary work; history rewrites stay refused
    if sub == "restore" and worktree is None and not base_bad and in_build_repo():
        return None
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
        if "drop" in low or "clear" in low:
            return "git stash %s discards stashed work" % ("drop" if "drop" in low else "clear")
        if worktree is None and not base_bad and in_build_repo():
            return None
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
        return _git_checkout(args, base_bad, worktree)
    return None


def _exists_here(r):
    """os.path.exists, except on a remote Mac, where it cannot be known and
    a path is taken to be there."""
    return True if STATE.get("remote") else os.path.exists(r)


def _path_like_remote(a):
    return (a in (".", "./") or a.startswith(("/", "./", "../", "~"))
            or "." in os.path.basename(a.rstrip("/")))


def _git_checkout(args, base_bad=False, worktree=None):
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
            # (v5.1) the paths are in a file (or on stdin) the guard cannot read
            if a == "--pathspec-from-file" or a.startswith("--pathspec-from-file="):
                return ("git checkout --pathspec-from-file takes its paths from a file "
                        "the guard cannot read, and overwrites them")
            if a in ("-b", "--conflict", "--recurse-submodules"):
                i += 2
                continue
            i += 1
            continue
        nonflag.append(a)
        i += 1
    # (v5.1) Pathspec magic (`:/`, `:(top)wiki`, `:!x`) reaches files anywhere
    # in the repository, whatever the folder; a ref name cannot begin with ':'.
    for a in nonflag + (paths or []):
        if a.startswith(":"):
            return ("git checkout %s uses pathspec magic, which reaches files that "
                    "exist anywhere in the repository" % a)
    # (v5.2) a build folder's own repository: checking out a file is ordinary
    if worktree is None and not base_bad and in_build_repo():
        return None
    if paths is None:
        if not nonflag:
            return None
        if len(nonflag) == 1:
            a = nonflag[0]
            r = resolve(a)
            if any(ch in a for ch in "*?["):
                paths = [a]  # a glob; a branch name cannot hold one
            elif a in (".", "./") or (r is not None and os.path.exists(r)):
                paths = [a]
            elif STATE.get("remote") and _path_like_remote(a):
                paths = [a]
            elif r is None and ("/" in a or a.endswith(".md")):
                paths = [a]
            else:
                return None
        else:
            paths = nonflag[1:]
    if not paths:
        return None
    for p in paths:
        if any(ch in p for ch in "*?["):
            return ("git checkout %s: git matches that pattern itself, against files "
                    "that exist" % p)
    if base_bad:
        return "git checkout of paths in a folder the guard cannot place (-C)"
    if not STATE["cwd"]:
        return "git checkout of paths overwrites working-tree files"
    wt = None
    if worktree:
        wt = resolve(worktree)
        if wt is None:
            return "git checkout of paths in a work tree the guard cannot place"
    for p in paths:
        r = resolve(p)
        if r is None or _exists_here(r):
            return ("git checkout of %s overwrites a file that exists in the working tree"
                    % p)
        if wt is not None:
            e = expand(p)
            rw = os.path.normpath(e if e and os.path.isabs(e)
                                  else os.path.join(wt, e)) if e is not None else None
            if rw is None or _exists_here(rw):
                return ("git checkout of %s overwrites a file that exists in the work "
                        "tree" % p)
    return None  # pure restore of files that do not currently exist


# apply_patch run as a shell command (ChatGPT's agent puts it on the PATH).
PATCH_HEADS = {"apply_patch", "applypatch"}
CHDIR_HEADS = {"cd", "pushd", "popd", "chdir"}
PATCH_SHELL_WHY = (
    "runs apply_patch through the shell in a form the guard cannot read "
    "(%s); use the file-editing tool itself, or pass the whole patch as one "
    "quoted heredoc, apply_patch <<'EOF' ... EOF, with no cd before it")


def changes_folder(lines, assigns):
    """True if any step of the command changes the working folder."""
    for line in lines:
        for seg in line.segs:
            if not seg.toks:
                continue
            try:
                b = peel(seg.toks, assigns)[0]
            except Exception:
                b = norm_head(seg.toks[0])
            if b in CHDIR_HEADS:
                return True
            if any(t in ("-C", "--chdir") or t.startswith("--chdir=")
                   for t in seg.toks) and any(norm_head(t) == "env" for t in seg.toks):
                return True  # env -C <folder> <command>
    return False


def _apply_patch_shell(rest, seg):
    line = seg.line
    ops = [op for op, _ in seg.redirs]
    if rest:
        why = "the patch is passed as an argument"
    elif seg.piped_in:
        why = "the patch is piped in"
    elif any(op in ("<", "<<<", "<&", "<>") for op in ops):
        why = "the patch is read from a file or a string"
    elif ops.count("<<") != 1 or line is None or len(line.bodies) != 1:
        why = "the patch is not in one heredoc of its own"
    elif "<<-" in line.text:
        why = "a <<- heredoc strips tabs, so the patch is not what it looks like"
    elif STATE.get("chdir"):
        why = "the command changes folder first, so the paths cannot be placed"
    else:
        body = line.bodies[0]
        if not heredoc_quoted(line.text) and ("$" in body or "`" in body):
            why = ("the heredoc is unquoted and the patch holds $ or a "
                   "backtick, which the shell would rewrite")
        else:
            return scan_patch_guarded(body)
    return PATCH_SHELL_WHY % why


def rule_apply_patch(b, rest, seg):
    if b not in PATCH_HEADS:
        return None
    try:
        return _apply_patch_shell(rest, seg)
    except Exception:
        # A bug here must not freeze the assistant, but a visible delete or
        # move line is still refused.
        text = seg.line.text + "\n" + "\n".join(seg.line.bodies) if seg.line else ""
        if loose_patch_line(text):
            return PATCH_SHELL_WHY % "it holds a delete or move line and could not be read"
        return None


def rule_direct_script(b, head, rest, depth):
    """(v0.9.2) A script run as itself, rather than handed to an interpreter.

    `bash scripts/x.sh` was scanned and `./scripts/x.sh` was not, though the
    shebang makes them the same work. Only a path is considered — a bare word is
    a command on PATH and has its own rules — and only a file that reads as a
    script: an extension the guard knows, or a shebang. That keeps the scanner
    away from binaries, whose bytes would otherwise be read as text.
    """
    if "/" not in head:
        return None
    p = resolve(head)
    if not p or not os.path.isfile(p):
        return None
    if os.path.splitext(p)[1].lower() not in EXT_LANG:
        try:
            with open(p, "rb") as fh:
                if fh.read(2) != b"#!":
                    return None
        except OSError:
            return None
    return scan_file(head, "", depth)


def rule_text_writers(b, rest):
    """(v0.9.2) Three tools that write a file while looking like readers.

    `sort -o page`, `uniq input page` and awk's own `print > "page"` each empty
    or replace what is there, and every one of these heads was allow-listed, so
    a page could be cleared by a command with no delete word anywhere in it.
    """
    if b == "sort":
        i = 0
        while i < len(rest):
            tok = rest[i]
            if tok in ("-o", "--output") and i + 1 < len(rest):
                if is_content_path(rest[i + 1]) or is_protected(rest[i + 1]):
                    return "sort -o writes over %s" % rest[i + 1]
                i += 2
                continue
            if tok.startswith("--output="):
                target = tok.split("=", 1)[1]
                if is_content_path(target) or is_protected(target):
                    return "sort -o writes over %s" % target
            i += 1
        return None
    if b == "uniq":
        positional = [x for x in rest if not x.startswith("-")]
        # uniq [input [output]] — the second file is written, not read
        if len(positional) >= 2 and (is_content_path(positional[1])
                                     or is_protected(positional[1])):
            return "uniq writes its output over %s" % positional[1]
        return None
    return None


# ---------------------------------------------------------------- self
def _operands(rest):
    out, dd = [], False
    for t in rest:
        if not dd and t == "--":
            dd = True
            continue
        if not dd and t.startswith("-") and len(t) > 1:
            continue
        out.append(t)
    return out


def _cluster_has(t, wanted, stops):
    """True if a short-option cluster sets one of `wanted` before a letter in
    `stops`, whose argument is the rest of the cluster."""
    if not t.startswith("-") or t.startswith("--") or len(t) < 2:
        return False
    for ch in t[1:]:
        if ch in wanted:
            return True
        if ch in stops:
            return False
    return False


def _fetch_targets(b, rest):
    out = []
    for i, t in enumerate(rest):
        nxt = rest[i + 1] if i + 1 < len(rest) else None
        if b == "curl":
            if t in ("-o", "--output") and nxt:
                out.append(nxt)
            elif t.startswith("--output="):
                out.append(t.split("=", 1)[1])
            elif t.startswith("-o") and len(t) > 2 and not t.startswith("--"):
                out.append(t[2:])
        else:
            if t in ("-O", "--output-document", "-a", "--append-output", "-o",
                     "--output-file") and nxt:
                out.append(nxt)
            elif t.startswith(("--output-document=", "--append-output=", "--output-file=")):
                out.append(t.split("=", 1)[1])
            elif t.startswith("-O") and len(t) > 2:
                out.append(t[2:])
    return out


RSYNC_ARG_OPTS = {"-e", "--rsh", "-f", "--filter", "--exclude", "--include",
                  "--exclude-from", "--include-from", "--files-from", "--link-dest",
                  "--compare-dest", "--copy-dest", "--backup-dir", "--suffix",
                  "--chmod", "--chown", "--log-file", "--out-format", "--partial-dir",
                  "-T", "--temp-dir", "--timeout", "--bwlimit", "--max-size",
                  "--min-size", "--port", "--password-file", "-B", "--block-size",
                  "-M", "--remote-option", "--usermap", "--groupmap", "--info",
                  "--debug", "--rsync-path", "--iconv", "--checksum-choice",
                  "--compress-choice", "--max-delete", "--modify-window"}


def rule_protect_self(b, rest):
    """(v5.1) The guard's own files, against every way of changing them that is
    not a redirect, tee, rm or mv/cp (those have their own rules): in-place
    editors, chmod and its kin, links, rsync, ditto-likes, fetchers that write
    a file, archive extraction into ~/.claude, and plutil's writing actions.
    Reading them (cat, grep, jq ., diff, plutil -p) passes."""
    ops = _operands(rest)
    if b in CHMODS or (b == "xattr" and any(
            t in ("-w", "-d", "-c") or _cluster_has(t, "wdc", "") for t in rest)):
        for t in ops:
            if is_protected_or_ancestor(t):
                return "%s changes %s" % (b, protected_why(t))
    if b in EDITORS:
        for t in ops:
            if is_protected(t):
                return "%s edits %s" % (b, protected_why(t))
    if b == "sed":
        inplace = any(t.startswith("--in-place") or _cluster_has(t, "iI", "ef")
                      for t in rest)
        for t in rest:
            if t.startswith("-") and len(t) > 1:
                continue
            if not re.search(r"\s", t) and is_protected(t):
                if inplace:
                    return "sed -i edits %s" % protected_why(t)
                continue
            # a sed program that names one: `w FILE`, `s/x/y/w FILE`
            if PROTECTED_SPELL_RE.search(t) or (re.search(r"\s", t) and SETTINGS_RE.search(
                    _fold(t.split()[-1]))):
                return "a sed program writes to %s" % protected_why(t)
    if b in ("perl", "ruby"):
        stops = "MmIdDxl0CeEVF" if b == "perl" else "IreECF0WxKT"
        if any(_cluster_has(t, "i", stops) for t in rest):
            for t in rest:
                if not t.startswith("-") and is_protected(t):
                    return "%s -i edits %s" % (b, protected_why(t))
    if b == "plutil":
        # these write the file in place, or to -o's path when one is given
        # (-extract included: without -o it overwrites its input)
        if any(t in ("-convert", "-insert", "-replace", "-remove", "-create",
                     "-extract") for t in rest):
            if "-o" in rest and rest.index("-o") + 1 < len(rest):
                targets = [rest[rest.index("-o") + 1]]
            else:
                targets = rest
            for t in targets:
                if t != "-" and is_protected(t):
                    return "plutil writes to %s" % protected_why(t)
    if b in ("curl", "wget"):
        for t in _fetch_targets(b, rest):
            if is_protected(t):
                return "%s writes its download over %s" % (b, protected_why(t))
    if b in ("ln", "link"):
        for t in ops:
            if is_protected_or_ancestor(t):
                return "%s links %s" % (b, protected_why(t))
    if b == "rsync":
        pos, i = [], 0
        while i < len(rest):
            t = rest[i]
            if t.startswith("--") and "=" in t:
                k, v = t.split("=", 1)
                if k in ("--link-dest", "--copy-dest", "--compare-dest") \
                        and is_protected_or_ancestor(v):
                    return "rsync %s links from %s" % (k, protected_why(v))
                i += 1
                continue
            if t in RSYNC_ARG_OPTS and i + 1 < len(rest):
                if t in ("--link-dest", "--copy-dest", "--compare-dest") \
                        and is_protected_or_ancestor(rest[i + 1]):
                    return "rsync %s links from %s" % (t, protected_why(rest[i + 1]))
                i += 2
                continue
            if t.startswith("-") and len(t) > 1:
                i += 1
                continue
            pos.append(t)
            i += 1
        if len(pos) >= 2:
            dest = pos[-1]
            if ":" in dest.split("/", 1)[0]:
                return None  # a remote destination
            if is_protected(dest) or os.path.basename(_fold(dest).rstrip("/")) == ".claude":
                return "rsync writes into %s" % protected_why(dest)
            rd = resolve(dest)
            if rd:
                for s in pos[:-1]:
                    hit = _lands_on_protected(s, rd, s.endswith("/"))
                    if hit:
                        return "rsync puts %s in place of %s" % (s, protected_why(hit))
    if b in ("tar", "bsdtar", "unzip"):
        extracting = b == "unzip" or any(
            t in ("-x", "--extract", "--get") or _cluster_has(t, "x", "fCbTXIs")
            or (not t.startswith("-") and t == rest[0] and "x" in t and t.isalpha())
            for t in rest)
        if extracting:
            dest = None
            for i, t in enumerate(rest):
                if t in ("-C", "--directory", "-d") and i + 1 < len(rest):
                    if b == "unzip" and t != "-d":
                        continue
                    dest = rest[i + 1]
                elif t.startswith("--directory="):
                    dest = t.split("=", 1)[1]
            target = dest if dest is not None else STATE["cwd"]
            if target and (is_protected(target) or os.path.basename(
                    _fold(str(target)).rstrip("/")) == ".claude"):
                return "%s unpacks into %s" % (b, protected_why(target))
    return None


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
    writes = []
    try:
        b, head, rest = peel(seg.toks, assigns, 0, writes)
    except Exception:
        b, head, rest = norm_head(seg.toks[0]), seg.toks[0], seg.toks[1:]
    r = _safe(rule_wrapper_writes, writes)
    if r:
        return r
    if not b:
        return None
    for fn, a in (
            (rule_protect_self, (b, rest)),
            (rule_ssh, (b, rest, depth, seg)),
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
            (rule_git, (b, rest, depth, assigns)),
            (rule_apply_patch, (b, rest, seg)),
            (rule_text_writers, (b, rest)),
            (rule_open, (b, rest)),
            (rule_direct_script, (b, head, rest, depth)),
    ):
        r = _safe(fn, *a)
        if r:
            return r
    return None


def scan_command(command, depth=0):
    """Reason string if the command string contains a destructive step."""
    if not command or not isinstance(command, str):
        return None
    if depth > MAX_DEPTH:
        # (v0.9.2) As with the file cap: past the nesting limit the guard has
        # stopped reading, and saying nothing was found would be a claim about
        # text it never looked at.
        return ("this command nests shells deeper than the guard follows (%d); "
                "run the inner command on its own" % MAX_DEPTH)
    try:
        lines = parse(command)
    except Exception:
        seg = Seg()
        seg.toks = fallback_tokens(command)
        if any(norm_head(t) in CHDIR_HEADS for t in seg.toks):
            STATE["chdir"] = True
        return scan_segment_tokens(seg.toks, depth, seg)
    assigns = _safe(assignments, lines) or {}
    if _safe(changes_folder, lines, assigns):
        STATE["chdir"] = True  # stays set: an apply_patch step may be nested
    r = _safe(written_then_run, lines, assigns)
    if r:
        return r
    for line in lines:
        for seg in line.segs:
            r = scan_segment_tokens(seg.toks, depth, seg, assigns)
            if r:
                return r
            _safe(apply_chdir, seg, assigns)
        for inner in (_safe(substitutions, line.text) or []):
            r = scan_command(inner, depth + 1)
            if r:
                return "command substitution: %s" % r
    return None


def _segment_head(seg, assigns):
    try:
        return peel(seg.toks, assigns)
    except Exception:
        if not seg.toks:
            return "", "", []
        return norm_head(seg.toks[0]), seg.toks[0], seg.toks[1:]


def apply_chdir(seg, assigns):
    """(v0.9.2) Follow a `cd` so the paths after it are resolved where they
    will actually be read.

    Until now every path in a command was resolved against the folder the hook
    was started in, whatever the command did first. That let `cd /tmp && mv
    <vault>/wiki .` move the wiki out, `.` having been read as the vault, and it
    refused `cd /tmp && rm -rf mydir`, which touches nothing of anyone's. A cd
    whose target cannot be resolved leaves the cwd alone and the existing
    conservative flag set, which is the safe way to be uncertain.
    """
    b, _head, rest = _segment_head(seg, assigns)
    if b not in CHDIR_HEADS:
        return
    target = next((x for x in rest if not x.startswith("-")), None)
    if b == "cd" and target is None:
        target = os.path.expanduser("~")
    if not target:
        return
    resolved = resolve(target)
    # (v5.1) on a remote Mac the folder cannot be checked here: a resolvable
    # cd is followed, so `cd <remote vault> && mv wiki/x ~/` is read in the vault
    if resolved and (os.path.isdir(resolved) or (STATE.get("remote") and target != "-")):
        STATE["cwd"] = resolved


def written_then_run(lines, assigns):
    """(v0.9.2) A file written and then run inside the same command.

    `echo 'rm -rf wiki' > /tmp/z.sh && bash /tmp/z.sh` defeated the file scanner
    completely: the scan reads /tmp/z.sh as it stands now, which is not what is
    about to be in it. Splitting the two across two commands leaves both
    readable, and is the only thing this asks for.
    """
    written = set()
    for line in lines:
        for seg in line.segs:
            b, head, rest = _segment_head(seg, assigns)
            candidates = []
            if head:
                candidates.append(head)
            if b in SHELLS or b in PYTHONS or b in AWKS or b in OTHER_INTERP \
                    or b in ("node", "perl", "ruby", "php", "osascript", "source", "."):
                candidates.extend(x for x in rest if not x.startswith("-"))
            for c in candidates:
                r = resolve(c)
                if r and os.path.realpath(r) in written:
                    return ("`%s` is written and then run by the same command, so it "
                            "cannot be read before it runs. Write it, then run it in a "
                            "second command" % c)
            for op, target in seg.redirs:
                if op in TRUNC_OPS or op == ">>":
                    r = resolve(target)
                    if r:
                        written.add(os.path.realpath(r))
    return None


# ---------------------------------------------------------------- patches
PATCH_FILE_MARKS = (("*** add file:", "add"), ("*** delete file:", "delete"),
                    ("*** update file:", "update"))
PATCH_MOVE_MARK = "*** move to:"
PATCH_END_MARK = "*** end patch"


def patch_ops(text):
    """[(op, path)] in order, read as Codex's own patch reader reads them
    (streaming_parser.rs). Outside an Update hunk the reader trims a line
    before looking for a header, so an indented header counts. Inside one it
    trims the right-hand side only: a header counts at column 0, and an
    indented line is the page's own text (content is prefixed '+', '-' or a
    space). Letter case and a missing space after the colon are forgiven
    here, which errs towards refusing. One pass, no regular expression."""
    ops, in_update = [], False
    for raw in text.split("\n"):
        line = raw.rstrip() if in_update else raw.strip()
        if not line.startswith("***"):
            continue
        low = line.lower()
        for mark, op in PATCH_FILE_MARKS:
            if low.startswith(mark):
                ops.append((op, line[len(mark):].strip()))
                in_update = op == "update"
                break
        else:
            if low.startswith(PATCH_MOVE_MARK):
                ops.append(("move", line[len(PATCH_MOVE_MARK):].strip()))
            elif low.startswith(PATCH_END_MARK):
                in_update = False
    return ops


def loose_patch_line(text):
    """True if any line, however indented, asks for a delete or a move."""
    for raw in text.split("\n"):
        low = raw.strip().lower()
        if low.startswith("*** delete file:") or low.startswith(PATCH_MOVE_MARK):
            return True
    return False


def patch_path(path):
    """The absolute path a patch line names, taken literally as the patch tool
    takes it: no ~, no $VAR. None when it cannot be placed (no cwd, NUL)."""
    if not path or "\x00" in path:
        return None
    if not os.path.isabs(path):
        if not STATE["cwd"]:
            return None
        path = os.path.join(STATE["cwd"], path)
    return path


def patch_throwaway(path):
    """True iff the literal path lies outside the vault, under a throwaway root."""
    p = patch_path(path)
    if p is None:
        return False
    real = os.path.realpath(p)
    if STATE["vault"] and inside(real, STATE["vault"]):
        return False
    return any(real.startswith(root + os.sep) for root in throwaway_roots())


def patch_key(target):
    """One name per file on a filesystem that ignores case and accent form."""
    return unicodedata.normalize("NFC", os.path.realpath(target)).casefold()


def scan_patch(text):
    """Reason string if an apply_patch body deletes a file, moves one out of
    the vault or over another, or adds a file where one already exists,
    on disk or earlier in the same patch."""
    vault = STATE["vault"] if STATE["cwd"] else None
    moving, claimed = None, set()
    for op, path in patch_ops(text):
        if op == "update":
            moving = path
            continue
        if op == "delete":
            moving = None
            if _safe(patch_throwaway, path):
                continue
            return "deletes a file (apply_patch, Delete File: %s)" % path
        if op == "add":
            moving = None
            target = patch_path(path)
            if target is None:
                # Cannot be placed: judge the instruction files by name.
                if os.path.basename(path) in CONTENT_FILES:
                    return ("writes over an existing file (apply_patch, "
                            "Add File: %s)" % path)
                continue
            if os.path.lexists(target):
                return ("writes over an existing file (apply_patch, "
                        "Add File: %s)" % path)
            key = patch_key(target)
            if key in claimed:
                return ("writes twice to the same new file in one patch "
                        "(apply_patch, Add File: %s)" % path)
            claimed.add(key)
            continue
        # Move to: the destination of the Update File named just above.
        src = patch_path(moving) if moving else None
        dest = patch_path(path)
        source_name, moving = moving, None
        # (v5.1) the known vaults, whatever the cwd
        src_k = known_root_of(src) if src else None
        if src_k and (dest is None or not in_root(dest, src_k)):
            return ("moves vault material out of the vault "
                    "(apply_patch, Move to: %s)" % path)
        if vault:
            if src is None or inside(src, vault):
                if dest is None or not inside(dest, vault):
                    sink = _safe(forbidden_destination, path)
                    if sink:
                        return "apply_patch move %s" % sink
                    return ("moves vault material out of the vault "
                            "(apply_patch, Move to: %s)" % path)
        else:
            sink = _safe(forbidden_destination, path)
            if sink:
                return "apply_patch move %s" % sink
            if source_name is None or is_content_path(source_name):
                # No cwd, so nothing can be placed: a content page may move
                # only to another content location, judged by name.
                text_dest = os.path.normpath(path)
                if (os.path.isabs(text_dest) or text_dest.startswith("..")
                        or not any(text_dest.startswith(d + "/") for d in CONTENT_DIRS)):
                    return ("moves vault material out of the vault "
                            "(apply_patch, Move to: %s)" % path)
        if dest is not None:
            if os.path.lexists(dest):
                return ("moves over an existing file (apply_patch, "
                        "Move to: %s)" % path)
            key = patch_key(dest)
            if key in claimed:
                return ("moves onto a file written earlier in the same patch "
                        "(apply_patch, Move to: %s)" % path)
            claimed.add(key)
    return None


def scan_patch_guarded(text):
    """scan_patch, except that a failure while reading refuses a patch that
    holds a delete or move line rather than letting it through."""
    try:
        return scan_patch(text)
    except Exception:
        if loose_patch_line(text):
            return ("holds a delete or move line in a patch the guard could "
                    "not finish reading (apply_patch)")
        return None


BLOCK_MSG = (
    "Blocked by the vault safety gate (bash-guard.py): %s. "
    "This is on the never-list (delete, overwrite, move out of the vault, "
    "force-push, history rewrite). Do not look for another spelling of the "
    "same action. Keep moves and copies inside the vault (raw/processed/, "
    "archive/, outputs/), append rather than overwrite, and write new files "
    "with your file-writing tool; deleting is allowed only for throwaway files under "
    "/tmp, $TMPDIR or the caches, named by a resolvable path. If something "
    "else genuinely needs deleting, restoring or rewriting, tell the owner "
    "exactly what and why and let them do it themselves in Finder or "
    "Terminal; git holds the undo path.\n"
)


def main():
    try:
        data = json.load(sys.stdin)
        tool = data.get("tool_name")
        if tool not in ("Bash", "apply_patch"):
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
        if tool == "apply_patch":
            reason = scan_patch_guarded(command)
        else:
            reason = scan_command(command)
            # rule_apply_patch reads a patch fed to an apply_patch step. This
            # second look covers a step it could not see (behind a wrapper the
            # guard does not peel): the operation lines are read the same.
            if not reason and "*** Begin Patch" in command:
                reason = scan_patch_guarded(command)
    except Exception:
        reason = None  # framework bug: never freeze the assistant
    if reason:
        sys.stderr.write(BLOCK_MSG % reason)
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
