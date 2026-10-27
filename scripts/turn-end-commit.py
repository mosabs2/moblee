#!/usr/bin/env python3
"""turn-end-commit.py — save the wiki at the end of every reply.

An owner can walk away from a conversation at any moment, and whatever the
assistant had changed up to that point is left unsaved. The next message in
that conversation then has to be "save everything", and in a conversation that
has been left for a few hours that is the dearest message of the day: the
assistant re-reads the whole conversation from the beginning before it can do
anything at all. This script removes the need for that message. The assistant
still saves each piece of finished work itself, under its own description; this
catches whatever is left over when a reply ends.

INSTALLATION
    The script lives inside the wiki, at

        <wiki>/scripts/turn-end-commit.py

    and is wired as the assistant's Stop hook — the hook that runs once a reply
    has finished:

        python3 "<wiki>/scripts/turn-end-commit.py"

    The Moblee installer does that wiring. Nothing else needs setting: the
    script takes the wiki to be the folder that its own folder sits in, which is
    the same rule the commit gate and the other in-wiki scripts follow, so a
    wiki that is moved, copied or renamed needs no change here.

WHAT IT DOES
    It reads the hook's message from its standard input, detaches at once so
    that a reply never waits for it, and saves in up to two parts:

      * the files the conversation changed itself (its own file edits, and
        those of any helper it started), under the conversation's own title;
      * everything else that has changed in the wiki — files a script, another
        conversation or another machine may have written — as changes found.

    The commit gate (scripts/vault-gate.py) runs exactly as it does on any
    other save. When the gate stops a part, every file in that part is offered
    again on its own, so that one unhappy file cannot hold back the rest; the
    files the gate still stops are left unsaved and are named in the record, so
    the owner can be told which they are. The script never bypasses the gate,
    never deletes anything and never sends anything anywhere. One run holds the
    wiki at a time, and a run waits for a git command another conversation is
    running to finish.

WHAT IT LEAVES ALONE, AND WHY
    This hook saves a wiki's pages. It does not save work that is the owner's
    own, and it does not touch a snapshot somebody made deliberately.

      * The rules file, the ignore list and the files in Moblee's own folders
        are the owner's. Where one of those is found changed and the
        conversation did not change it itself, it is left for the owner's own
        next commit and named in the record, so that the check-up can tell
        them. (A file the conversation DID change itself is its own work and
        goes in under its own title, as any other file does.) This is the line
        scripts/update.sh has drawn since v0.9.6, in owners_own_file(), and it
        is drawn here for the same reason: an update can print "nothing of
        yours was committed" and the reply can end seconds later, and the two
        must not contradict each other.
      * A file somebody has staged AND changed again since is left exactly as
        it is. Naming a path in a commit takes what is on the disk, so saving
        it would throw away the half of it they staged on purpose.
      * Nothing at all is saved while the wiki's history is not on a branch.
        A save made then would belong to no branch and would be lost from the
        wiki as soon as it went back to one.

    One honest limitation: a save at the end of one reply can carry another
    open conversation's unfinished work under the heading "changes found in the
    wiki". Nothing is lost by that, and the other conversation's own save takes
    whatever is left after it.

WHERE IT KEEPS ITS RECORDS
    ~/.config/moblee/state/turn-end-commit.json
        One record per conversation — what was saved, what the gate stopped —
        kept for 30 days. Dropping an old record rewrites this one file; no
        file is ever deleted.
    ~/.config/moblee/logs/turn-end-commit.log
        One line per run. Both assistants write to the same two places, and
        neither is inside an assistant's own folder, which the pack's rules
        keep clear.

BY HAND
    python3 scripts/turn-end-commit.py --now < message.json   run and wait
    python3 scripts/turn-end-commit.py --status <id>          print one record
    python3 scripts/turn-end-commit.py --help

    MOBLEE_VAULT overrides which wiki is worked on, and
    MOBLEE_TURN_END_STATE and MOBLEE_TURN_END_LOG override the two files
    above. The pack's own tests use all three; ordinary use needs none of them.
"""
from __future__ import annotations

import datetime
import fcntl
import json
import os
import subprocess
import sys
import time
from pathlib import Path

# The tools the assistants use to change a file. A conversation's own edits are
# what gets saved under its title; everything else is saved as changes found.
EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
KEEP_DAYS = 30            # how long one conversation's record is kept
LIST_MAX = 40             # how many file names a commit message names
TITLE_MAX = 80            # a conversation title is one line, this long at most
PLAIN_TITLE = "a conversation"   # used when the hook's message gives no title
LOCK_WAIT_SECONDS = 90    # how long to wait for another run to finish
INDEX_LOCK_WAIT_SECONDS = 20   # how long to wait for someone else's git command
# A git command in a wiki takes a moment. A lock file older than this belongs
# to no running command: it was left behind by one that stopped partway, and
# nothing in git ever clears it. Said in the record so the check-up can tell
# the owner, who is the one who takes it away: this script never deletes.
INDEX_LOCK_STALE_SECONDS = 300
LOG_MAX_BYTES = 400_000   # above this the log is rewritten, keeping the last
LOG_KEEP_LINES = 2000     # this many lines

# The things git leaves behind while it is halfway through a change of its own.
# A save made in the middle of one of these would land in the middle of it.
MID_CHANGE = ("MERGE_HEAD", "rebase-merge", "rebase-apply", "CHERRY_PICK_HEAD",
              "REVERT_HEAD", "BISECT_LOG")

# (v0.10.0) What in a Moblee wiki is the owner's own, rather than the wiki's
# pages. The same line scripts/update.sh draws in owners_own_file(): the rules
# files, the ignore list, and what sits in Moblee's own folders.
#
# One difference, and it is deliberate. The updater can ask whether the pack
# ships a file of a given name, because it is running from the pack; this hook
# runs from inside the wiki, where there is no pack to ask. So it treats
# everything in those folders as the owner's. Erring that way leaves a file
# unsaved and named, which the check-up reports; erring the other way commits
# the owner's half-finished work in Moblee's name, which is the fault this is
# here to stop.
OWNER_OWN_FILES = ("CLAUDE.md", "AGENTS.md", ".gitignore")
OWNER_OWN_FOLDERS = ("scripts/", "dashboard/", ".claude/")
# The two in those folders that the pack writes and commits itself, named the
# same way round as the updater names them.
NOT_OWNER_OWN = ("VERSION", ".claude/settings.local.json")


def owners_own(path: str) -> bool:
    """Whether this path, named from the top of the wiki, is the owner's own
    work rather than one of the wiki's pages. See OWNER_OWN_FILES above."""
    if path in NOT_OWNER_OWN:
        return False
    if path in OWNER_OWN_FILES:
        return True
    return path.startswith(OWNER_OWN_FOLDERS)


def find_vault() -> Path:
    """The wiki this script belongs to.

    Installed, the script sits at <wiki>/scripts/turn-end-commit.py, so the
    wiki is the parent of the folder holding the script — the same rule the
    commit gate's hook uses. MOBLEE_VAULT, the variable used throughout the
    pack, overrides it; the tests work that way.
    """
    env = os.environ.get("MOBLEE_VAULT")
    if env:
        return Path(env).expanduser()
    return Path(__file__).resolve().parent.parent


def state_path() -> Path:
    """The file holding one record per conversation."""
    env = os.environ.get("MOBLEE_TURN_END_STATE")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".config" / "moblee" / "state" / "turn-end-commit.json"


def log_path() -> Path:
    """The file holding one line per run."""
    env = os.environ.get("MOBLEE_TURN_END_LOG")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".config" / "moblee" / "logs" / "turn-end-commit.log"


def now() -> str:
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def log(line: str) -> None:
    """Add one line to the log. A log that cannot be written is not a reason to
    fail: the save itself matters more than the note about it."""
    path = log_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S} {line}\n")
        if path.stat().st_size > LOG_MAX_BYTES:
            # Trimmed by rewriting this one file in place, never by deleting it.
            kept = path.read_text(encoding="utf-8", errors="replace").splitlines()
            path.write_text("\n".join(kept[-LOG_KEEP_LINES:]) + "\n", encoding="utf-8")
    except OSError:
        pass


def git(vault: Path, *args: str, stdin: str | None = None,
        check: bool = False) -> subprocess.CompletedProcess:
    """Run one git command inside the wiki and hand back what it printed.

    core.quotepath=false and literal pathspecs are what let a page named in
    Arabic, Chinese or Greek — or one holding a space, a quote mark or a square
    bracket — be read and named exactly as it stands. GIT_TERMINAL_PROMPT=0
    makes sure git can never sit waiting for someone to type something: this
    runs with nobody watching it.
    """
    env = dict(os.environ, GIT_LITERAL_PATHSPECS="1", GIT_TERMINAL_PROMPT="0")
    return subprocess.run(
        ["git", "-C", str(vault), "-c", "core.quotepath=false", *args],
        input=stdin, capture_output=True, text=True, env=env, check=check,
        timeout=120)


def on_a_branch(vault: Path) -> bool:
    """Whether the wiki's history is on a branch at this moment.

    git calls the other state a detached HEAD, and it is an ordinary thing to
    reach: looking at an older version of a page with `git checkout <save>`,
    a `git bisect`, or Obsidian's own git plugin doing either. A save made
    while detached is attached to nothing. The moment the wiki goes back to a
    branch it is gone from the wiki, reachable only through git's reflog, which
    expires — so it is not a save at all, and must not be recorded as one.
    """
    return git(vault, "symbolic-ref", "-q", "HEAD").returncode == 0


def head_name(vault: Path) -> str:
    """The short name of the save at the top of the wiki's history, or "" where
    there is none yet. Compared before and after a commit, so that a commit
    that did not happen is never written down as one."""
    out = git(vault, "rev-parse", "--short", "HEAD")
    return out.stdout.strip() if out.returncode == 0 else ""


def lock_verdict(lock: Path) -> dict:
    """What to record when a git lock file is still in the way after the wait.

    Two quite different things look the same from here, and the owner needs to
    be told which. A lock a moment old belongs to a git command that really is
    running, and the next reply's save takes whatever this one missed. A lock
    minutes or days old belongs to nothing: a command stopped partway and left
    it, and git has no way of clearing it, so every save in this wiki from now
    until somebody takes it away does exactly nothing. This script never
    deletes, so saying which it is, is the whole of what it can do.
    """
    try:
        age = max(time.time() - lock.stat().st_mtime, 0.0)
    except OSError:
        age = None
    if age is not None and age >= INDEX_LOCK_STALE_SECONDS:
        return {"state": "locked",
                "reason": "nothing was saved, and nothing will be: a lock file left "
                          "behind by a git command that is no longer running "
                          f"(.git/index.lock, about {age / 60:.0f} minutes old) is "
                          "stopping every save in this wiki until it is taken away"}
    return {"state": "busy",
            "reason": "a git command in the wiki was still running after "
                      f"{INDEX_LOCK_WAIT_SECONDS:g} seconds, so nothing was saved "
                      "this time"}


def wiki_changes(vault: Path) -> tuple[list[str], list[str], set[str]]:
    """What git finds changed in the wiki, in three parts:

      * every changed, new or gone file git is not told to ignore, named from
        the top of the wiki, that this hook may offer for saving;
      * the files somebody has staged AND changed again since, which it may
        not: naming a path in a commit takes what is on the disk, so saving one
        of these would throw away the half of it they staged on purpose. They
        are held back and named instead;
      * the files already staged with nothing changed since, so that this run
        can tell the index entries it made itself from the ones it found.

    Read with -z so that every file name survives whole.
    """
    out = git(vault, "status", "--porcelain=v1", "-z", "--untracked-files=all",
              check=True).stdout
    parts, paths, half, staged, i = out.split("\0"), [], [], set(), 0
    while i < len(parts):
        entry = parts[i]
        i += 1
        if len(entry) < 4:
            continue
        status, path = entry[:2], entry[3:]
        here = [path]
        if "R" in status or "C" in status:
            # A file given a new name carries its old name in the next entry.
            # Both are saved: the new one as it stands, the old one by naming it.
            if i < len(parts) and parts[i]:
                here.append(parts[i])
            i += 1
        index_side, tree_side = status[0], status[1]
        if index_side not in " ?" and tree_side != " ":
            # Staged, and then changed again. Also where an unfinished merge
            # leaves a file (both sides read "U"), which is left alone too.
            half += here
        else:
            paths += here
            if index_side not in " ?":
                staged.update(here)
    return sorted(set(paths)), sorted(set(half)), staged


def one_line(text: str) -> str:
    """A title fit for the first line of a commit message."""
    return " ".join(str(text).split())[:TITLE_MAX]


def transcript_facts(vault: Path, transcript, session: str) -> tuple[str, set[str]]:
    """The conversation's title, and the files it changed itself.

    The hook's message points at the conversation's own record of itself. Where
    that record is missing, is written in a shape this cannot read (the two
    assistants do not write the same one), or cannot be opened at all, the
    answer is a plain title and no files — so everything found in the wiki is
    saved as changes found, which is the safe outcome, never an error.
    """
    title, prompt, edited = "", "", set()
    if not transcript or not isinstance(transcript, str):
        return PLAIN_TITLE, edited
    main = Path(transcript)
    helpers = sorted((main.parent / main.stem / "subagents").glob("*.jsonl"))
    for f in [main] + helpers:
        try:
            lines = f.open(encoding="utf-8", errors="replace")
        except OSError:
            continue
        with lines:
            for line in lines:
                if ('"custom-title"' not in line and '"last-prompt"' not in line
                        and '"tool_use"' not in line):
                    continue
                try:
                    d = json.loads(line)
                except ValueError:
                    continue   # not a shape this can read; the fallback covers it
                if not isinstance(d, dict):
                    continue
                if d.get("type") == "custom-title" and f == main:
                    title = d.get("customTitle") or title
                elif d.get("type") == "last-prompt" and f == main and not prompt:
                    prompt = d.get("lastPrompt") or ""
                elif d.get("type") == "assistant":
                    message = d.get("message")
                    blocks = (message or {}).get("content") if isinstance(message, dict) else None
                    for block in blocks or []:
                        if not isinstance(block, dict) or block.get("type") != "tool_use":
                            continue
                        if block.get("name") not in EDIT_TOOLS:
                            continue
                        given = block.get("input") or {}
                        if not isinstance(given, dict):
                            continue
                        p = given.get("file_path") or given.get("notebook_path")
                        if p and isinstance(p, str):
                            edited.add(p)
    # Only files inside the wiki are the wiki's business.
    inside, root = set(), str(vault.resolve()) + os.sep
    for p in edited:
        full = os.path.realpath(p if os.path.isabs(p) else os.path.join(vault, p))
        if full.startswith(root):
            inside.add(full[len(root):])
        elif os.path.abspath(p).startswith(str(vault) + os.sep):
            inside.add(os.path.abspath(p)[len(str(vault)) + 1:])
    if not title:
        # No title was given to the conversation, so what the owner last asked
        # for stands in for one.
        flat = " ".join(str(prompt).split())
        title = flat[:TITLE_MAX] + "…" if len(flat) > TITLE_MAX else flat
    return one_line(title) or PLAIN_TITLE, inside


def put_index_back(vault: Path, paths: list[str]) -> None:
    """Put the index back as this run found it, for these paths only.

    The index belongs to whoever is working in the wiki. Where a commit does
    not happen, it must leave nothing behind in theirs: a file staged here and
    then refused would sit in their index as a snapshot they never made, and
    their assistant's next `git add .` would carry it into a commit about
    something else altogether. Only the paths this run staged itself are named
    — a snapshot somebody else made is never undone — and no file on the disk
    is written, moved or taken away.
    """
    if not paths:
        return
    git(vault, "restore", "--staged", "--pathspec-from-file=-",
        "--pathspec-file-nul", stdin="\0".join(paths) + "\0")


def commit(vault: Path, paths: list[str], subject: str, intro: str,
           already_staged: set[str] | None = None) -> tuple[list[str], list[str], str]:
    """Save these files and no others.

    A snapshot somebody staged on purpose is never overwritten: the files both
    staged and changed again since are held back before this is called, and the
    ones staged with nothing changed since are saved as they stand. Where a
    commit does not happen, the index is left exactly as this run found it.

    Hands back (what was saved, what is still unsaved, why the gate stopped it).
    """
    found_staged = already_staged or set()

    def attempt(group: list[str], subj: str) -> tuple[str, str]:
        """("saved", the new save's name), ("nothing", "") where there was
        nothing left to save, or ("refused", what git said)."""
        spec = "\0".join(group) + "\0"
        # Only files still on the disk are staged — a brand-new file has to be,
        # to be saved at all. A file that has gone, or the old name of a file
        # that has been given a new one, is saved simply by naming it: git takes
        # that one from the last save. Staging a name with nothing behind it
        # would fail the whole part.
        present = [p for p in group if os.path.lexists(vault / p)]
        ours = [p for p in present if p not in found_staged]
        if present:
            added = git(vault, "add", "-A", "--pathspec-from-file=-",
                        "--pathspec-file-nul", stdin="\0".join(present) + "\0")
            if added.returncode:
                put_index_back(vault, ours)
                return "refused", added.stderr.strip()
        shown = group[:LIST_MAX]
        if len(group) > LIST_MAX:
            shown = shown + [f"... and {len(group) - LIST_MAX} more"]
        message = (f"{subj}\n\n{intro}\n\n"
                   + "\n".join(f"- {p}" for p in shown) + "\n")
        was = head_name(vault)
        done = git(vault, "commit", "-q", "-m", message,
                   "--pathspec-from-file=-", "--pathspec-file-nul", stdin=spec)
        now_at = head_name(vault)
        if done.returncode == 0 and now_at and now_at != was:
            return "saved", now_at
        said = (done.stdout + done.stderr).strip()
        put_index_back(vault, ours)
        if done.returncode == 0 or "nothing to commit" in said or "no changes added" in said:
            # Another run got there first. Nothing is wrong, and nothing was
            # saved: the name at the top of the history belongs to that other
            # run, and writing it down here would report a save this run did
            # not make.
            return "nothing", ""
        return "refused", said

    saved, left, reasons = [], [], []
    how, info = attempt(paths, subject)
    if how == "saved":
        return [info], [], ""
    if how == "nothing":
        return [], [], ""
    if len(paths) == 1:
        return [], paths, info
    # The gate stopped the part as a whole. Offer every file on its own, so
    # that the ones it is happy with still go in, and only the ones it really
    # objects to are left for the owner.
    for p in paths:
        how, info = attempt([p], f"{subject} ({p.rsplit('/', 1)[-1]})")
        if how == "saved":
            saved.append(info)
        elif how == "refused":
            left.append(p)
            reasons.append(info)
    return saved, left, (reasons[0] if reasons else "")


def short_reason(text: str) -> str:
    """The one line of the gate's answer worth repeating to a person."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    plain = [l for l in lines
             if l.startswith(("G", "[GATE", "error", "fatal")) or "block" in l.lower()]
    return (plain or lines or ["unknown"])[0][:200]


def read_records() -> dict:
    """Every conversation's record. A file that cannot be read is treated as
    empty, so one bad character can never stop a save."""
    try:
        return json.loads(state_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def write_record(session: str, record: dict) -> None:
    """Keep this conversation's record, and drop the ones over 30 days old.

    Dropping them rewrites this one file in place. Nothing is deleted: the
    pack's safety guard refuses to run a script that deletes, and this script
    has to stay runnable by hand.
    """
    path = state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with (path.parent / (path.name + ".lock")).open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        records = read_records()
        records[session] = record
        cutoff = (datetime.datetime.now().astimezone()
                  - datetime.timedelta(days=KEEP_DAYS)).isoformat(timespec="seconds")
        records = {k: v for k, v in records.items()
                   if isinstance(v, dict) and str(v.get("at", "")) >= cutoff}
        path.write_text(json.dumps(records, indent=1, ensure_ascii=False) + "\n",
                        encoding="utf-8")


def blank_record(session: str, title: str) -> dict:
    """One conversation's record.

    own_left     files of the conversation's own that the gate stopped
    other_left   files found in the wiki that the gate stopped
    yours_left   files that are the owner's own, left for their own next commit
    staged_left  files somebody staged and changed again, left exactly as they are
    """
    return {"session": session, "title": title, "at": now(), "state": "clean",
            "commits": [], "own_left": [], "other_left": [], "yours_left": [],
            "staged_left": [], "reason": ""}


def run(hook: dict) -> dict:
    """Do the saving, and hand back the record of what happened."""
    vault = find_vault()
    session = str(hook.get("session_id") or "unknown")
    title, edited = transcript_facts(vault, hook.get("transcript_path"), session)
    record = blank_record(session, title)
    git_dir = vault / ".git"
    if not git_dir.is_dir():
        record.update(state="error",
                      reason=f"there is no wiki with a history at {vault}")
        return record
    lock = (git_dir / "turn-end-commit.lock").open("w")
    deadline = time.time() + LOCK_WAIT_SECONDS
    while True:   # one run at a time, across every conversation
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except BlockingIOError:
            if time.time() > deadline:
                record.update(state="busy",
                              reason="another end-of-reply save was still running")
                return record
            time.sleep(0.2)
    try:
        for marker in MID_CHANGE:
            if (git_dir / marker).exists():
                record.update(state="paused",
                              reason="the wiki is in the middle of something git is doing "
                                     f"({marker}), so nothing was saved this time")
                return record
        if not on_a_branch(vault):
            # See on_a_branch(). A save made now would be lost from the wiki
            # the moment it went back to a branch, so none is made, and the
            # record says so rather than saying the work was saved.
            record.update(
                state="detached",
                reason="the wiki's history is not on a branch at the moment, so nothing "
                       "was saved: a save made now would belong to no branch and would "
                       "go from the wiki as soon as it was back on one. Everything is "
                       "still there on the disk, exactly as the reply left it")
            return record
        waited = 0.0
        while (git_dir / "index.lock").exists():
            # Someone else's git command is running. Wait for it rather than
            # fight it; the next reply's save will pick up anything missed.
            if waited >= INDEX_LOCK_WAIT_SECONDS:
                record.update(**lock_verdict(git_dir / "index.lock"))
                return record
            time.sleep(0.2)
            waited += 0.2
        dirty, staged_left, already = wiki_changes(vault)
        record["staged_left"] = staged_left
        own = [p for p in dirty if p in edited]
        rest = [p for p in dirty if p not in edited]
        # (v0.10.0) The owner's own work is not this hook's to commit. See
        # owners_own() and WHAT IT LEAVES ALONE at the top of this file.
        yours = [p for p in rest if owners_own(p)]
        other = [p for p in rest if not owners_own(p)]
        record["yours_left"] = yours
        if not own and not other:
            # Nothing this hook may save. Which of the two it is matters: an
            # empty wiki is clean, and a wiki whose only unsaved work is the
            # owner's is not, and must not be reported as though it were.
            record["state"] = "yours" if (yours or staged_left) else "clean"
            return record
        reasons = []
        if own:
            saved, left, why = commit(
                vault, own, f"saved automatically: {title}",
                f'Saved automatically when the conversation "{title}" finished a '
                "reply: files that conversation changed itself and had not yet saved.",
                already)
            record["commits"] += saved
            record["own_left"] = left
            if why:
                reasons.append(short_reason(why))
        if other:
            saved, left, why = commit(
                vault, other, "saved automatically: changes found in the wiki",
                f'Saved automatically when the conversation "{title}" finished a '
                "reply. That conversation did not change these files itself: a script, "
                "another conversation or another machine may have. The rules file, the "
                "ignore list and the files in Moblee's own folders are not saved here: "
                "where one of those held work that was not yet committed, it was left "
                "for the owner's own next commit.",
                already)
            record["commits"] += saved
            record["other_left"] = left
            if why:
                reasons.append(short_reason(why))
        record["state"] = ("blocked" if (record["own_left"] or record["other_left"])
                           else "committed")
        record["reason"] = "; ".join(reasons)
        return record
    finally:
        fcntl.flock(lock, fcntl.LOCK_UN)
        lock.close()


HELP = """turn-end-commit.py — save the wiki at the end of every reply.

Installed inside the wiki at <wiki>/scripts/turn-end-commit.py and run by the
assistant's Stop hook, with the hook's message on standard input. It saves the
files the conversation changed under the conversation's title, and everything
else it finds changed as changes found. The commit gate runs as usual, nothing
is ever deleted and nothing is ever sent anywhere.

It leaves three things alone, and names them in the record instead: the owner's
own work (the rules file, the ignore list, Moblee's own folders), a file
somebody has staged and changed again since, and the whole wiki while its
history is not on a branch.

    python3 scripts/turn-end-commit.py                 as the hook runs it
    python3 scripts/turn-end-commit.py --now           run and wait, print the record
    python3 scripts/turn-end-commit.py --status <id>   print one conversation's record
    python3 scripts/turn-end-commit.py --help          this text

Records:  ~/.config/moblee/state/turn-end-commit.json  (kept 30 days)
Log:      ~/.config/moblee/logs/turn-end-commit.log
"""


def main() -> int:
    args = sys.argv[1:]
    if "--help" in args or "-h" in args:
        print(HELP)
        return 0
    if args[:1] == ["--status"]:
        if len(args) != 2:
            print("usage: turn-end-commit.py --status <conversation id>",
                  file=sys.stderr)
            return 2
        print(json.dumps(read_records().get(args[1], {}), indent=1,
                         ensure_ascii=False))
        return 0
    unknown = [a for a in args if a != "--now"]
    if unknown:
        print(f"turn-end-commit.py: {unknown[0]} is not something this "
              "understands. Try --help.", file=sys.stderr)
        return 2
    try:
        hook = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        hook = {}
    if not isinstance(hook, dict):
        hook = {}
    if "--now" not in args:
        # Detach, so that the reply is never held up: the first parent hands
        # control straight back to the assistant and the work carries on here.
        if os.fork():
            return 0
        os.setsid()
        if os.fork():
            os._exit(0)
        nowhere = os.open(os.devnull, os.O_RDWR)
        for fd in (0, 1, 2):
            os.dup2(nowhere, fd)
    session = str(hook.get("session_id") or "unknown")
    try:
        record = run(hook)
    except Exception as e:   # a run always leaves a record, whatever happened
        record = blank_record(session, "")
        record.update(state="error", reason=f"{type(e).__name__}: {e}"[:300])
    try:
        write_record(session, record)
    except OSError:
        pass
    left = len(record.get("own_left") or []) + len(record.get("other_left") or [])
    yours = len(record.get("yours_left") or []) + len(record.get("staged_left") or [])
    log(f"{session[:8]} {record['state']} "
        f"saved={','.join(record['commits']) or '-'} left={left} yours={yours}"
        f"{' reason=' + record['reason'] if record['reason'] else ''} "
        f"| {record['title'][:60]}")
    if "--now" in args:
        print(json.dumps(record, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
