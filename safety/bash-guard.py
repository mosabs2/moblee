#!/usr/bin/env python3
"""
PreToolUse Bash guard — enforce the vault's "never-list" for real.

The Claude Code settings deny list is string-pattern based and cannot catch
indirect destruction (`find -exec rm`, `python3 -c "shutil.rmtree(...)"`,
`… | xargs rm`, `git rebase`). This hook inspects the *resolved* Bash command
and blocks the destructive class however it is spelled:

  * file deletion   — rm / rmdir (any position, incl. sudo/command/env/xargs
                      prefixes, find -delete / -exec rm, interpreter unlink)
  * force-push      — git push -f / --force / --force-with-lease / +refspec
  * history rewrite — git reset --hard, git clean, rebase, filter-branch/-repo
  * disk clobber    — mkfs, dd if=

Design contract:
  * FAIL CLOSED on a matched pattern: exit 2, reason on stderr, tool blocked.
  * FAIL OPEN on any hook error (bad JSON, unknown shape): exit 0, allow. A bug
    here must never paralyse normal Claude Code work — worst case is the status
    quo (the command runs), plus git remains the undo path.

Per-machine: this lives in ~/.claude/hooks/ on the Mac that runs Claude Code
against the vault; it is wired in ~/.claude/settings.json as a PreToolUse hook
matching Bash by safety/install-safety.py, which also proves it fires before
registering it. Part of Moblee from v0.5 (September 2026); ported from the
maintainer's vault, where it has run since August 2026 without a lost file.
"""
import json
import os
import re
import shlex
import sys

INTERPRETERS = {"python", "python3", "python2", "node", "deno", "bun", "ruby",
                "perl", "php", "osascript", "sh", "bash", "zsh", "ksh"}
# Deletion primitives inside an interpreter body (the -c/-e escape hatch).
DEL_KEYWORDS = ("rmtree", "os.remove", "os.unlink", "os.rmdir", "removedirs",
                "shutil.rm", "unlink(", ".unlink", "fs.rm", "rmsync", "rmdirsync",
                "rimraf", "remove_tree", "fileutils.rm", "pathname",
                # Shell-out escapes inside an interpreter body:
                # os.system("rm …") etc. dodge every keyword above.
                "os.system", "subprocess.", "os.popen", "child_process",
                "execsync")
# Command prefixes that just wrap another command; peel them to find the real one.
WRAPPERS = {"sudo", "command", "env", "time", "nice", "nohup", "caffeinate",
            "builtin", "exec", "then", "do", "else"}


def real_head(tokens):
    """(command, args-after-it), skipping wrappers and VAR=val assignments."""
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if "=" in t and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", t):
            i += 1; continue
        if t in WRAPPERS:
            i += 1; continue
        return t, tokens[i + 1:]
    return "", []


def base(cmd):
    return os.path.basename(cmd)


def command_is_destructive(command, depth=0):
    """Scan a full command string (used for recursion into ssh / shell -c bodies)."""
    if depth > 3 or not command or not isinstance(command, str):
        return None
    try:
        segs = split_segments(command)
    except Exception:
        segs = [command.split()]
    for seg in segs:
        r = segment_is_destructive(seg, depth)
        if r:
            return r
    return None


# ssh options that consume a following argument (must be skipped to find the host)
SSH_ARG_OPTS = {"-o", "-p", "-l", "-i", "-F", "-J", "-W", "-b", "-c", "-D",
                "-E", "-e", "-L", "-m", "-O", "-Q", "-R", "-S", "-w", "-B"}


def segment_is_destructive(seg, depth=0):
    """seg is a token list for one command (already split on shell operators)."""
    if not seg:
        return None
    head, rest = real_head(seg)
    if not head:
        return None
    b = base(head)
    low = [t.lower() for t in rest]

    # 0. ssh — the remote command string must be scanned with the same rules.
    #    Skip option tokens, skip the host, then everything after IS the remote
    #    command; recurse into it.
    if b == "ssh":
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
            r = command_is_destructive(" ".join(remote), depth + 1)
            if r:
                return f"ssh remote command: {r}"

    # 0b. shell -c / -lc bodies (bash -c "rm x", zsh -lc '...'); the generic
    #     interpreter keyword check below only knows python/node primitives.
    if b in ("sh", "bash", "zsh", "ksh", "dash"):
        for i, t in enumerate(rest):
            if t in ("-c", "-lc", "-ic", "-lic") and i + 1 < len(rest):
                r = command_is_destructive(rest[i + 1], depth + 1)
                if r:
                    return f"shell -c body: {r}"

    # 1. direct rm / rmdir (incl. peeled wrappers). xargs rm, command rm, etc.
    if b in ("rm", "rmdir"):
        return f"deletes files (`{head}`)"
    if b == "xargs" and any(base(t) in ("rm", "rmdir") for t in rest):
        return "pipes into rm (xargs rm)"

    # 2. find with a deleting action
    if b == "find":
        if "-delete" in low:
            return "find -delete removes files"
        for i, t in enumerate(low):
            if t in ("-exec", "-execdir", "-ok", "-okdir"):
                if any(base(x) in ("rm", "rmdir") for x in rest[i + 1:i + 3]):
                    return "find -exec rm removes files"
                # -exec sh -c 'body': recurse into the body, which the
                # head-position checks otherwise never see.
                tail = rest[i + 1:i + 6]
                for j, x in enumerate(tail):
                    if (base(x) in ("sh", "bash", "zsh", "ksh", "dash")
                            and j + 2 < len(tail) and tail[j + 1] in ("-c", "-lc")):
                        r = command_is_destructive(tail[j + 2], depth + 1)
                        if r:
                            return f"find -exec shell body: {r}"

    # 3. interpreter running a deletion primitive from -c / -e / inline body
    if b in INTERPRETERS:
        body = " ".join(rest).lower()
        if any(k in body for k in DEL_KEYWORDS):
            return f"interpreter deletes files ({head} … {'/'.join(k for k in DEL_KEYWORDS if k in body)[:40]})"

    # 4. git destructive subcommands
    if b == "git":
        sub = low[0] if low else ""
        if sub == "push" and any(f in low for f in ("-f", "--force", "--force-with-lease")):
            return "git force-push"
        if sub == "push" and any(t.startswith("+") for t in rest[1:]):
            return "git force-push (+refspec)"
        if sub == "reset" and "--hard" in low:
            return "git reset --hard discards work"
        if sub in ("clean", "rebase", "filter-branch", "filter-repo"):
            return f"git {sub} rewrites/deletes"
        if sub == "rm":
            return "git rm removes tracked files"

    # 5. raw disk clobber
    if b == "mkfs" or b.startswith("mkfs."):
        return "mkfs formats a disk"
    if b == "dd" and any(t.startswith("of=") for t in low):
        return "dd of= overwrites a device/file"

    return None


def _tokens(command):
    lex = shlex.shlex(command, posix=True, punctuation_chars=True)
    lex.whitespace_split = True
    return list(lex)


def _segment(toks):
    segs, cur = [], []
    OPS = {";", "|", "||", "&", "&&", "(", ")", "|&"}
    for t in toks:
        if t in OPS:
            if cur:
                segs.append(cur); cur = []
        else:
            cur.append(t)
    if cur:
        segs.append(cur)
    return segs


def split_segments(command):
    """Tokenise, then break into per-command segments on shell operators.

    shlex with punctuation_chars makes ; | & ( ) their own tokens and respects
    quotes, so a quoted "rm" (in grep/echo/commit message) is a single arg and
    never lands in a command position.

    Newline pass: shlex treats a newline as plain whitespace, so a multi-line
    command would hide every line after the first mid-segment ("echo x\\nrm y"
    never put rm in head position). Each physical line is therefore also
    tokenised independently and its segments added; a line that cannot lex
    alone is the interior of a quoted multi-line string — data, not a command —
    and is skipped.
    """
    segs = _segment(_tokens(command))
    if "\n" in command:
        for line in command.split("\n"):
            line = line.strip()
            if not line:
                continue
            try:
                segs.extend(_segment(_tokens(line)))
            except ValueError:
                continue
    return segs


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)  # fail open
    if data.get("tool_name") != "Bash":
        sys.exit(0)
    command = (data.get("tool_input") or {}).get("command", "")
    if not command or not isinstance(command, str):
        sys.exit(0)
    try:
        segs = split_segments(command)
    except Exception:
        # If tokenising fails, fall back to a coarse check rather than fail open
        # blindly on a command we couldn't parse.
        segs = [command.split()]
    reasons = []
    for seg in segs:
        r = segment_is_destructive(seg)
        if r:
            reasons.append(r)
    if reasons:
        sys.stderr.write(
            "Blocked by the vault safety gate (~/.claude/hooks/bash-guard.py): "
            + "; ".join(dict.fromkeys(reasons))
            + ". This is on the never-list (delete / force-push / history "
            "rewrite). If this is genuinely intended, the user runs it "
            "directly in a Terminal; otherwise move or rename via `mv` instead "
            "of deleting — git is the undo path.\n")
        sys.exit(2)  # block
    sys.exit(0)


if __name__ == "__main__":
    main()
