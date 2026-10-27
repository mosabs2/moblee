#!/usr/bin/env python3
"""Tests for scripts/turn-end-commit.py, the end-of-reply save.

    python3 tools/test-turn-end-commit.py

Every case builds a throwaway practice wiki under $TMPDIR — a real git
repository with the pack's own commit gate wired in as its pre-commit hook —
and runs the script against it the way an assistant's Stop hook runs it, with
the hook's message on standard input.

Every case also runs against a sandboxed home folder of its own, inside
$TMPDIR, so that this Mac's own ~/.config, ~/.claude and ~/.codex are never
read and never written.

The groups:

  own        The files the conversation changed itself, saved under the
             conversation's own title.
  found      Everything else changed in the wiki, saved as changes found.
  clean      A reply that changed nothing: no save, and a record saying so.
  gate       A file the pack's commit gate stops. It must be named in the
             record, left on the disk untouched, and never forced through; the
             rest of its part must still go in. The same fixture is the proof
             that the gate accepts the two new commit messages, since the gate
             really is wired into these practice wikis.
  rename     A page given a new name, and a page that has gone. The old name
             is saved by being NAMED, never by being staged — staging a name
             with no file behind it fails the whole save.
  staged     A file another conversation had already staged: carried in, not
             lost, and nothing left staged afterwards. And one staged at one
             version and typed on since, which is left exactly as it is, since
             naming a path in a commit takes the working tree and would throw
             the staged snapshot away.
  branch     The wiki's history not on a branch (git's detached HEAD). Nothing
             is saved at all: a save made then belongs to no branch and is
             gone from the wiki the moment it goes back to one.
  yours      The owner's own uncommitted work — the rules files, the ignore
             list, Moblee's own folders — left for their own next commit and
             named, never committed in Moblee's name, and never described as
             something a script wrote. The line scripts/update.sh draws.
  index      A commit that does not happen leaves the owner's index as it was
             found: a refused file is never left staged.
  nothing    "nothing to commit" is not a save, and the hash at the top of the
             history is not written down as this run's.
  registered Which wiki the registered Stop hook names. Read through
             safety/install-safety.py's own functions, because a hook naming
             the wrong wiki saves the wrong wiki.
  lock       Two runs at once. One run holds the wiki at a time; the second
             waits and then says plainly that it did nothing. Also a git
             command another conversation is running, which is waited for; a
             lock file left behind by one that stopped, which is told apart
             from it and reported; and a wiki caught in the middle of
             something, which is left alone.
  detached   The run detaches, so a reply never waits for it, and the detached
             half still does the work and writes its record.
  payload    A hook message with no conversation record, with a null one, with
             one written in a shape this cannot read, and with no conversation
             id at all. None of these may fail; all of them fall back to
             saving everything as changes found.
  paths      The record and the log land under ~/.config/moblee/, which both
             assistants share and neither owns.
  pruning    Records over 30 days old are dropped BY REWRITING the one record
             file. No file is ever deleted, here or anywhere.
  safety     Read from the script's own text: no way of deleting a file, no
             bypassing of the commit gate, nothing sent anywhere.
  by hand    --status, --help, an unknown switch, and a folder that is not a
             wiki with a history.

Nothing is deleted, by this test or by the script it tests. Each practice wiki
is a few kilobytes and is left where it is, with its folder named at the end.

Prints a pass/fail table and exits non-zero on any failure.
"""
import datetime
import fcntl
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACK = HERE.parent
SCRIPT = PACK / "scripts" / "turn-end-commit.py"
GATE = PACK / "scripts" / "vault-gate.py"
HOOK = PACK / "scripts" / "hooks" / "pre-commit"

ROWS = []
FAILURES = 0
WIKIS = []

OWN_SUBJECT = "saved automatically: %s"
FOUND_SUBJECT = "saved automatically: changes found in the wiki"


def check(group, label, passed, note=""):
    global FAILURES
    if not passed:
        FAILURES += 1
    ROWS.append(("PASS" if passed else "FAIL", group, label, str(note)[:70]))
    return passed


def load_script():
    """The script as a module, for the cases that are easier to drive from the
    inside (the two-runs-at-once case shortens its own waiting time). The pack's
    safety guard will not run a script that starts processes from a shell, and
    importing runs exactly the same code."""
    spec = importlib.util.spec_from_file_location("turn_end_commit", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sandbox_env(vault, home):
    """A sandboxed environment: this Mac's own home folder is never in it."""
    env = dict(os.environ)
    env["HOME"] = str(home)
    env["MOBLEE_VAULT"] = str(vault)
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    for leftover in ("MOBLEE_TURN_END_STATE", "MOBLEE_TURN_END_LOG"):
        env.pop(leftover, None)
    return env


def g(vault, home, *args, stdin=None):
    """One git command in a practice wiki, under its sandboxed home."""
    return subprocess.run(
        ["git", "-C", str(vault), "-c", "core.quotepath=false", *args],
        input=stdin, capture_output=True, text=True, env=sandbox_env(vault, home),
        timeout=120)


def new_wiki(name, with_gate=True):
    """A practice wiki: a git repository with the pack's commit gate wired in,
    and a sandboxed home folder beside it."""
    root = Path(tempfile.mkdtemp(prefix="turn-end-%s-" % name,
                                 dir=os.environ.get("TMPDIR") or None))
    vault, home = root / "Practice Wiki", root / "home"
    home.mkdir()
    write(vault / "CLAUDE.md", "# How to keep this wiki\n\nPlain rules.\n")
    write(vault / "wiki" / "Index.md", "# Index\n\nOne line per page.\n")
    write(vault / "wiki" / "_context.md", "# Working state\n\n## Active threads\n\n- None.\n")
    write(vault / "wiki" / "log.md",
          "# Log\n\n## [2026-10-01 09:00 +01] note | The first entry\n\nBody.\n")
    if with_gate:
        write(vault / "scripts" / "vault-gate.py", GATE.read_text(encoding="utf-8"))
        hook = vault / "scripts" / "hooks" / "pre-commit"
        write(hook, HOOK.read_text(encoding="utf-8"))
        hook.chmod(0o755)
    g(vault, home, "init", "-q", "-b", "main")
    g(vault, home, "config", "user.email", "practice@example.invalid")
    g(vault, home, "config", "user.name", "Practice Wiki")
    g(vault, home, "config", "commit.gpgsign", "false")
    if with_gate:
        g(vault, home, "config", "core.hooksPath", "scripts/hooks")
    g(vault, home, "add", "-A")
    first = g(vault, home, "commit", "-q", "-m", "the first save")
    WIKIS.append(root)
    return vault, home, first


def claude_transcript(path, title, edited_paths):
    """A conversation's own record of itself, in the shape Claude writes."""
    lines = [json.dumps({"type": "custom-title", "customTitle": title}),
             json.dumps({"type": "last-prompt", "lastPrompt": "tidy up the notes"})]
    for p in edited_paths:
        lines.append(json.dumps({
            "type": "assistant",
            "message": {"content": [
                {"type": "text", "text": "Done."},
                {"type": "tool_use", "name": "Edit", "input": {"file_path": str(p)}},
            ]},
        }))
    write(Path(path), "\n".join(lines) + "\n")
    return str(path)


def run_script(vault, home, payload, args=("--now",), timeout=180, extra_env=None):
    """The script, run as the Stop hook runs it, with the message on stdin."""
    env = sandbox_env(vault, home)
    env.update(extra_env or {})
    done = subprocess.run([sys.executable, str(SCRIPT), *args],
                          input=json.dumps(payload), capture_output=True,
                          text=True, env=env, timeout=timeout)
    record = {}
    if "--now" in args and done.stdout.strip():
        try:
            record = json.loads(done.stdout)
        except ValueError:
            record = {}
    return done, record


def history(vault, home):
    """Every save in the practice wiki, oldest first."""
    out = []
    for h in g(vault, home, "log", "--format=%H", "--reverse").stdout.split():
        out.append({
            "hash": h,
            "subject": g(vault, home, "show", "-s", "--format=%s", h).stdout.strip(),
            "body": g(vault, home, "show", "-s", "--format=%b", h).stdout,
            "files": [f for f in g(vault, home, "show", "--name-only", "--format=",
                                   h).stdout.splitlines() if f.strip()],
            "status": g(vault, home, "show", "--name-status", "--format=", h).stdout,
            # The same, read without git's renamed-file guessing: that is how a
            # file that has simply gone is told apart from one given a new name.
            "status_plain": g(vault, home, "show", "--name-status", "--format=",
                              "--no-renames", h).stdout,
        })
    return out


def dirty(vault, home):
    return g(vault, home, "status", "--porcelain=v1").stdout


def state_file(home):
    return home / ".config" / "moblee" / "state" / "turn-end-commit.json"


def log_file(home):
    return home / ".config" / "moblee" / "logs" / "turn-end-commit.log"


def records(home):
    try:
        return json.loads(state_file(home).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def files_under(folder):
    return {str(p.relative_to(folder)) for p in Path(folder).rglob("*") if p.is_file()}


# ------------------------------------------------------------------ the groups

def test_two_parts():
    """Both parts of a save: the conversation's own files, and everything else."""
    vault, home, _ = new_wiki("two-parts")
    title = "Tidying the kitchen notes"
    mine = vault / "wiki" / "Kitchen.md"
    write(mine, "# Kitchen\n\nThe new sink was fitted on Tuesday.\n")
    write(vault / "wiki" / "Roof.md", "# Roof\n\nWritten by something else.\n")
    write(vault / "raw" / "a note from the phone.md", "Dropped in by another conversation.\n")
    transcript = claude_transcript(Path(vault).parent / "transcript.jsonl", title, [mine])
    done, record = run_script(vault, home, {
        "session_id": "s-two-parts", "transcript_path": transcript,
        "hook_event_name": "Stop", "cwd": str(vault)})

    saves = history(vault, home)
    own = [s for s in saves if s["subject"] == OWN_SUBJECT % title]
    found = [s for s in saves if s["subject"] == FOUND_SUBJECT]
    check("own", "the run finishes quietly and says it saved",
          done.returncode == 0 and record.get("state") == "committed",
          record.get("state", done.stderr.strip()[:60]))
    check("own", "the conversation's own file is saved under the conversation's title",
          len(own) == 1 and own[0]["files"] == ["wiki/Kitchen.md"],
          own[0]["files"] if own else "no such save")
    check("own", "the message says in plain words why the save happened, and names the file",
          bool(own) and "finished a reply" in own[0]["body"]
          and "- wiki/Kitchen.md" in own[0]["body"])
    check("found", "everything else is saved as changes found in the wiki",
          len(found) == 1 and sorted(found[0]["files"]) ==
          ["raw/a note from the phone.md", "wiki/Roof.md"],
          sorted(found[0]["files"]) if found else "no such save")
    check("found", "the conversation's own file is not in that second save",
          bool(found) and "wiki/Kitchen.md" not in found[0]["files"])
    check("found", "one reply makes two saves, the conversation's own first",
          len(record.get("commits", [])) == 2
          and [s["subject"] for s in saves[1:]] == [OWN_SUBJECT % title, FOUND_SUBJECT],
          [s["subject"] for s in saves[1:]])
    check("found", "the wiki is left with nothing unsaved", dirty(vault, home) == "",
          dirty(vault, home)[:60])
    check("gate", "the pack's own commit gate was wired in and let both messages through",
          g(vault, home, "config", "core.hooksPath").stdout.strip() == "scripts/hooks"
          and len(own) == 1 and len(found) == 1)
    return vault, home


def test_clean():
    """A reply that changed nothing."""
    vault, home, _ = new_wiki("clean")
    before = history(vault, home)
    done, record = run_script(vault, home, {"session_id": "s-clean",
                                            "hook_event_name": "Stop"})
    check("clean", "a reply that changed nothing makes no save and records 'clean'",
          done.returncode == 0 and record.get("state") == "clean"
          and record.get("commits") == [] and history(vault, home) == before,
          record.get("state"))
    check("clean", "and the run is still written down, with one line in the log",
          records(home).get("s-clean", {}).get("state") == "clean"
          and len(log_file(home).read_text(encoding="utf-8").splitlines()) == 1,
          log_file(home).read_text(encoding="utf-8").strip()[-40:]
          if log_file(home).exists() else "no log")


def test_gate_stops_a_file():
    """A file the commit gate stops, and the files beside it that it does not."""
    vault, home, _ = new_wiki("gate")
    # The gate's first check: a new log entry must carry its time and time zone.
    # This one does not, so the gate stops it — and must go on stopping it.
    log = vault / "wiki" / "log.md"
    write(log, log.read_text(encoding="utf-8")
          + "\n## [2026-10-14] note | An entry with no time on it\n\nBody.\n")
    write(vault / "wiki" / "Garden.md", "# Garden\n\nThe hedge was cut back.\n")
    write(vault / "wiki" / "Boiler.md", "# Boiler\n\nServiced in September.\n")
    before = log.read_text(encoding="utf-8")
    done, record = run_script(vault, home, {"session_id": "s-gate",
                                            "hook_event_name": "Stop"})
    saves = history(vault, home)
    saved_files = sorted(f for s in saves[1:] for f in s["files"])
    check("gate", "the file the gate stops is named in the record, and left unsaved",
          record.get("other_left") == ["wiki/log.md"], record.get("other_left"))
    check("gate", "the state is written down as blocked, with the gate's own reason",
          record.get("state") == "blocked" and "G1" in record.get("reason", ""),
          record.get("reason", "")[:60])
    check("gate", "the other files in that part still go in, one save each",
          saved_files == ["wiki/Boiler.md", "wiki/Garden.md"], saved_files)
    check("gate", "the stopped file is left exactly as it was, and still shows as unsaved",
          log.read_text(encoding="utf-8") == before
          and "wiki/log.md" in dirty(vault, home), dirty(vault, home)[:40])
    check("gate", "the gate was never bypassed: the stopped file is in no save of this run",
          all("wiki/log.md" not in s["files"] for s in saves[1:]),
          [s["subject"] for s in saves[1:]])
    check("gate", "and the run itself still ends quietly, exit code 0",
          done.returncode == 0, done.returncode)
    return vault, home


def test_rename_and_deletion():
    """A page given a new name, and a page that has gone."""
    vault, home, _ = new_wiki("rename")
    write(vault / "wiki" / "Old Name.md", "# Old Name\n\nA page with a space in its name.\n")
    write(vault / "wiki" / "Doomed.md", "# Doomed\n\nThis page is about to go.\n")
    g(vault, home, "add", "-A")
    g(vault, home, "commit", "-q", "-m", "two more pages")

    g(vault, home, "mv", "wiki/Old Name.md", "wiki/New Name.md")
    done, record = run_script(vault, home, {"session_id": "s-rename",
                                            "hook_event_name": "Stop"})
    saves = history(vault, home)
    last = saves[-1] if saves else {"status": "", "subject": ""}
    check("rename", "a page given a new name is saved under both of its names",
          "wiki/Old Name.md" in last["status"] and "wiki/New Name.md" in last["status"],
          last["status"].replace("\n", " ")[:60])
    check("rename", "the old name goes in by being named, not by being staged",
          record.get("state") == "committed" and dirty(vault, home) == "",
          record.get("reason") or dirty(vault, home)[:40])
    check("rename", "and the old name is gone from the wiki's files, the new one there",
          not (vault / "wiki" / "Old Name.md").exists()
          and (vault / "wiki" / "New Name.md").is_file())

    # A page the owner has moved out of the way. Nothing is deleted to make
    # this case: the file is given another name, which is how git comes to see
    # the old name as gone.
    os.rename(vault / "wiki" / "Doomed.md", vault / "wiki" / "Doomed.md.put-away")
    done, record = run_script(vault, home, {"session_id": "s-gone",
                                            "hook_event_name": "Stop"})
    saves = history(vault, home)
    last = saves[-1]
    check("rename", "a page that is no longer there is saved as gone, nothing deleted",
          record.get("state") == "committed"
          and "D\twiki/Doomed.md" in last["status_plain"]
          and "wiki/Doomed.md\n" not in g(vault, home, "ls-files").stdout
          and (vault / "wiki" / "Doomed.md.put-away").is_file(),
          last["status_plain"].replace("\n", " ")[:60])


def test_already_staged():
    """A file another conversation had already staged."""
    vault, home, _ = new_wiki("staged")
    theirs = vault / "wiki" / "Theirs.md"
    write(theirs, "# Theirs\n\nStaged by another conversation and left there.\n")
    g(vault, home, "add", "wiki/Theirs.md")
    write(vault / "wiki" / "Mine.md", "# Mine\n\nChanged after that.\n")
    done, record = run_script(vault, home, {"session_id": "s-staged",
                                            "hook_event_name": "Stop"})
    saves = history(vault, home)
    saved_files = sorted(f for s in saves[1:] for f in s["files"])
    check("staged", "a file another conversation had staged is carried in, not lost",
          "wiki/Theirs.md" in saved_files
          and g(vault, home, "show", "HEAD:wiki/Theirs.md").stdout
          == theirs.read_text(encoding="utf-8"),
          saved_files)
    check("staged", "and nothing is left staged or unsaved afterwards",
          dirty(vault, home) == "" and record.get("state") == "committed",
          dirty(vault, home)[:60])


def test_detached_head():
    """(v0.10.0) The wiki's history not on a branch — git's detached HEAD.

    The worst of the faults the review of October 2026 proved. The hook used to
    commit, and record state "committed", and the save belonged to no branch:
    the moment anything put the wiki back on its branch, the work was gone from
    the wiki, reachable only through git's reflog, which expires. Reaching this
    state is ordinary — `git checkout <save>` to look at an older version of a
    page, a bisect, Obsidian's git plugin doing either — so the hook must
    refuse, and say so.
    """
    vault, home, _ = new_wiki("detached-head")
    write(vault / "wiki" / "Chimney.md", "# Chimney\n\nSwept.\n")
    g(vault, home, "add", "-A")
    g(vault, home, "commit", "-q", "-m", "a second save")
    first = g(vault, home, "rev-parse", "HEAD~1").stdout.strip()
    g(vault, home, "checkout", "-q", first)      # as git does to look at an older page
    on_branch = g(vault, home, "symbolic-ref", "-q", "HEAD")
    before = history(vault, home)
    write(vault / "wiki" / "Loft.md", "# Loft\n\nBoarded out while the older page was open.\n")
    done, record = run_script(vault, home, {"session_id": "s-detached-head",
                                            "hook_event_name": "Stop"})
    after = history(vault, home)
    check("branch", "the practice wiki really is off its branch, which is what this case needs",
          on_branch.returncode != 0, on_branch.stdout.strip() or "detached")
    check("branch", "nothing is saved while the history is not on a branch",
          record.get("state") == "detached" and record.get("commits") == []
          and len(after) == len(before),
          "%s, %d saves then %d" % (record.get("state"), len(before), len(after)))
    check("branch", "and the record says why, in words a person can read",
          "not on a branch" in record.get("reason", "")
          and "still there on the disk" in record.get("reason", ""),
          record.get("reason", "")[:70])
    check("branch", "the work is left on the disk exactly as the reply left it",
          (vault / "wiki" / "Loft.md").is_file()
          and "wiki/Loft.md" in dirty(vault, home), dirty(vault, home)[:40])
    check("branch", "nothing of the owner's is left staged by the refusal",
          all(l[0] == "?" or l[0] == " " for l in dirty(vault, home).splitlines()),
          dirty(vault, home)[:40])
    check("branch", "and the run still ends quietly, exit code 0", done.returncode == 0,
          done.returncode)
    # Back on the branch, the same work goes in as usual.
    g(vault, home, "checkout", "-q", "main")
    done, record = run_script(vault, home, {"session_id": "s-reattached",
                                            "hook_event_name": "Stop"})
    check("branch", "once the wiki is back on its branch the next reply saves as usual",
          record.get("state") == "committed" and dirty(vault, home) == "",
          record.get("state"))


def test_owners_own_work():
    """(v0.10.0) The owner's own uncommitted work is not this hook's to commit.

    The second of the worst two. Everything git reported that the conversation
    had not edited itself was committed wholesale as "changes found in the
    wiki", under a message saying the files "were written by a script, by
    another conversation, or arrived from another machine" — which of the
    owner's own half-finished edit to their rules file is false in every word.
    The sharpest case the review proved: scripts/update.sh prints "nothing of
    yours was committed", the reply ends seconds later, and the hook committed
    exactly those files. The line drawn here is the one update.sh draws in
    owners_own_file(): the rules files, the ignore list, Moblee's own folders.
    """
    vault, home, _ = new_wiki("owners-own")
    write(vault / ".gitignore", ".DS_Store\n")
    write(vault / "AGENTS.md", "# How to keep this wiki\n\nPlain rules.\n")
    write(vault / "scripts" / "a tool of my own.py", "print('mine')\n")
    write(vault / "VERSION", "0.9.6\n")
    g(vault, home, "add", "-A")
    g(vault, home, "commit", "-q", "-m", "the owner's own files")

    # What the owner has half-written, and what a script has written beside it.
    write(vault / "CLAUDE.md", "# How to keep this wiki\n\nPlain rules.\n\nAnd one of my own, half-ty")
    write(vault / "AGENTS.md", "# How to keep this wiki\n\nPlain rules.\n\nAnd one of my own too.\n")
    write(vault / ".gitignore", ".DS_Store\n.cache\n")
    write(vault / "scripts" / "a tool of my own.py", "print('mine, half-written')\n")
    write(vault / "dashboard" / "notes.txt", "A note of mine.\n")
    write(vault / "VERSION", "0.10.0\n")
    write(vault / "wiki" / "Roof.md", "# Roof\n\nWritten by something else.\n")
    mine_was = (vault / "CLAUDE.md").read_text(encoding="utf-8")
    done, record = run_script(vault, home, {"session_id": "s-owners-own",
                                            "hook_event_name": "Stop"})
    saves = history(vault, home)
    saved_files = sorted(f for s in saves[2:] for f in s["files"])
    held = sorted(record.get("yours_left") or [])
    check("yours", "the owner's own unsaved work is left for their own next commit",
          held == [".gitignore", "AGENTS.md", "CLAUDE.md", "dashboard/notes.txt",
                   "scripts/a tool of my own.py"], held)
    check("yours", "not one of those files is in any save this run made",
          saved_files == ["VERSION", "wiki/Roof.md"], saved_files)
    check("yours", "and what the owner had written is still there on the disk, word for word",
          (vault / "CLAUDE.md").read_text(encoding="utf-8") == mine_was)
    check("yours", "the file Moblee writes itself is still saved, not mistaken for theirs",
          "VERSION" in saved_files, saved_files)
    check("yours", "the page something else wrote is still saved, as changes found",
          [s["subject"] for s in saves[2:]] == [FOUND_SUBJECT],
          [s["subject"] for s in saves[2:]])
    body = saves[-1]["body"]
    check("yours", "and the message no longer claims a script wrote what the owner wrote",
          "they were written by a script" not in body
          and "may have" in body, body.replace("\n", " ")[:90])
    check("yours", "the message says the owner's own work was left for their own commit",
          "left for the owner's own next commit" in body,
          body.replace("\n", " ")[:120])
    check("yours", "nothing of the owner's is left staged: their index is as they left it",
          all(l[:1] in ("?", " ") for l in dirty(vault, home).splitlines()),
          dirty(vault, home)[:60])

    # The sharpest case of all, on its own: nothing in the wiki but the owner's
    # own unsaved work. There is nothing for this hook to do, and it must not
    # say it found nothing — it found their work and left it.
    vault2, home2, _ = new_wiki("owners-own-only")
    write(vault2 / "CLAUDE.md", "# How to keep this wiki\n\nPlain rules.\n\nMine, half-ty")
    before = history(vault2, home2)
    done, record = run_script(vault2, home2, {"session_id": "s-only-mine",
                                              "hook_event_name": "Stop"})
    check("yours", "a reply that left only the owner's own work makes no save at all",
          record.get("commits") == [] and history(vault2, home2) == before,
          record.get("commits"))
    check("yours", "and it is not written down as 'nothing left to save', which would be false",
          record.get("state") == "yours"
          and record.get("yours_left") == ["CLAUDE.md"], record.get("state"))


def test_half_staged():
    """(v0.10.0) A file staged at one version and typed on since.

    The docstring claimed "anything already staged by somebody else is left
    exactly as it is", which was false unconditionally: every staged file shows
    in git status, and naming paths in a commit is git's --only mode, which
    takes the WORKING TREE and throws the staged snapshot away. Proved: a file
    staged at version A and then typed on to an unfinished version B was
    committed as B. The fully-staged case is test_already_staged above; this is
    the half-staged one, which is a deliberate act by somebody and is left
    alone and named.
    """
    vault, home, _ = new_wiki("half-staged")
    page = vault / "wiki" / "Workshop.md"
    write(page, "# Workshop\n\nVersion A, which somebody staged on purpose.\n")
    g(vault, home, "add", "wiki/Workshop.md")
    staged_was = g(vault, home, "show", ":wiki/Workshop.md").stdout
    write(page, "# Workshop\n\nVersion A, which somebody staged on purpose.\n\nVersion B, half-ty")
    tree_was = page.read_text(encoding="utf-8")
    write(vault / "wiki" / "Bench.md", "# Bench\n\nA page with nothing odd about it.\n")
    done, record = run_script(vault, home, {"session_id": "s-half-staged",
                                            "hook_event_name": "Stop"})
    saves = history(vault, home)
    saved_files = sorted(f for s in saves[1:] for f in s["files"])
    check("staged", "a file staged and then typed on again is in no save of this run",
          "wiki/Workshop.md" not in saved_files, saved_files)
    check("staged", "the snapshot whoever staged it made is still in the index, untouched",
          g(vault, home, "show", ":wiki/Workshop.md").stdout == staged_was,
          g(vault, home, "show", ":wiki/Workshop.md").stdout[-40:])
    check("staged", "and the half-written version is still on the disk, word for word",
          page.read_text(encoding="utf-8") == tree_was)
    check("staged", "it is named in the record, so the owner can be told which file it is",
          record.get("staged_left") == ["wiki/Workshop.md"], record.get("staged_left"))
    check("staged", "the ordinary page beside it still goes in",
          saved_files == ["wiki/Bench.md"], saved_files)
    check("staged", "and the run ends quietly", done.returncode == 0, done.returncode)


def test_stale_lock(mod):
    """(v0.10.0) A lock file left behind by a git command that has stopped.

    The hook treated the file's existence as "another git command is running",
    waited and recorded "busy", and the check-up filed "busy" as OK, saying
    something else was already saving and the next reply's save would take what
    this one missed. For a leftover lock both halves are false: nothing else
    was saving, nothing ever clears the file, and every save in the wiki from
    then on does nothing at all. The hook does not remove it — the pack never
    deletes — but it must tell the two apart and say which it found.

    Driven from the inside so that the waiting can be shortened. The lock file
    is renamed aside afterwards, never deleted, which is what git's own
    commands do when they finish.
    """
    vault, home, _ = new_wiki("stale-lock")
    write(vault / "wiki" / "Pantry.md", "# Pantry\n\nShelved out.\n")
    lock = vault / ".git" / "index.lock"
    lock.write_text("a lock file of the kind git leaves while it works\n", encoding="utf-8")
    long_ago = time.time() - 3 * 3600
    os.utime(lock, (long_ago, long_ago))
    was_wait, was_vault = mod.INDEX_LOCK_WAIT_SECONDS, os.environ.get("MOBLEE_VAULT")
    mod.INDEX_LOCK_WAIT_SECONDS = 1
    os.environ["MOBLEE_VAULT"] = str(vault)
    try:
        record = mod.run({"session_id": "s-stale-lock", "hook_event_name": "Stop"})
        check("lock", "a lock file hours old is not called a git command that is still running",
              record.get("state") == "locked",
              "%s: %s" % (record.get("state"), record.get("reason", "")[:50]))
        check("lock", "and the record says no save will happen until it is taken away",
              "no longer running" in record.get("reason", "")
              and "until it is taken away" in record.get("reason", ""),
              record.get("reason", "")[:80])
        check("lock", "nothing is saved, and the work is still on the disk",
              record.get("commits") == [] and "wiki/Pantry.md" in dirty(vault, home),
              dirty(vault, home)[:40])
        check("lock", "the lock file is left exactly where it is: the pack never deletes",
              lock.is_file(), lock)
        # The same file, a moment old, is a live git command and nothing else.
        now_lock = vault / ".git" / "index.lock"
        os.utime(now_lock, None)
        record = mod.run({"session_id": "s-live-lock", "hook_event_name": "Stop"})
        check("lock", "a lock file a moment old is a live git command, and recorded as busy",
              record.get("state") == "busy" and "still running after" in record.get("reason", ""),
              record.get("reason", "")[:50])
    finally:
        mod.INDEX_LOCK_WAIT_SECONDS = was_wait
        if was_vault is None:
            os.environ.pop("MOBLEE_VAULT", None)
        else:
            os.environ["MOBLEE_VAULT"] = was_vault
        os.rename(now_lock, vault / ".git" / "index.lock.finished")


def test_index_left_as_found():
    """(v0.10.0) A commit that does not happen leaves the index as it was.

    attempt() runs `git add -A` on the whole group before offering it to the
    gate, so a file the gate refused stayed in the owner's index — a snapshot
    they never made, which their assistant's next `git add .` would carry into
    a commit about something else altogether.
    """
    vault, home, _ = new_wiki("index-kept")
    # The gate's first check: a new log entry must carry its time and time zone.
    log = vault / "wiki" / "log.md"
    write(log, log.read_text(encoding="utf-8")
          + "\n## [2026-10-14] note | An entry with no time on it\n\nBody.\n")
    write(vault / "wiki" / "Steps.md", "# Steps\n\nRe-pointed.\n")
    done, record = run_script(vault, home, {"session_id": "s-index-kept",
                                            "hook_event_name": "Stop"})
    rows = {l[3:]: l[:2] for l in dirty(vault, home).splitlines()}
    check("index", "the file the gate refused is left unsaved, as it always was",
          record.get("other_left") == ["wiki/log.md"], record.get("other_left"))
    check("index", "and it is NOT left staged in the owner's index by the refusal",
          rows.get("wiki/log.md") == " M", rows)
    check("index", "nothing at all is left staged after a refused save",
          all(xy[0] in " ?" for xy in rows.values()), rows)
    check("index", "the page the gate was happy with still went in",
          sorted(f for s in history(vault, home)[1:] for f in s["files"]) == ["wiki/Steps.md"],
          sorted(f for s in history(vault, home)[1:] for f in s["files"]))


def test_nothing_to_commit(mod):
    """(v0.10.0) "nothing to commit" is not a save.

    git says that, and exits non-zero, when another run has already saved what
    this one was about to. The hook treated it as success and then wrote down
    the hash at the top of the history — which belongs to that other run — so
    the record, the log and the check-up all reported a commit this run did not
    make. Driven from the inside, which is the plain way to ask git the
    question without two runs racing.
    """
    vault, home, _ = new_wiki("nothing-to-commit")
    was_vault = os.environ.get("MOBLEE_VAULT")
    os.environ["MOBLEE_VAULT"] = str(vault)
    try:
        before = history(vault, home)
        head_was = g(vault, home, "rev-parse", "--short", "HEAD").stdout.strip()
        # A file with nothing changed in it: git has nothing to commit.
        saved, left, why = mod.commit(
            Path(vault), ["wiki/Index.md"], "saved automatically: a conversation",
            "Saved automatically when a reply finished.")
        check("nothing", "a save with nothing in it writes down no commit of its own",
              saved == [], saved)
        check("nothing", "and does not report the hash at the top of the history as its own",
              head_was not in saved, "%s / %s" % (head_was, saved))
        check("nothing", "it is not treated as a refusal either: nothing is left unsaved",
              left == [] and why == "", "%s / %s" % (left, why))
        check("nothing", "and no save was added to the wiki's history",
              history(vault, home) == before, len(history(vault, home)))
        # End to end: a reply that changed nothing but whose files another run
        # has already saved records no commit and says it plainly.
        write(vault / "wiki" / "Hall.md", "# Hall\n\nRepapered.\n")
        g(vault, home, "add", "-A")
        g(vault, home, "commit", "-q", "-m", "another run got there first")
        record = mod.run({"session_id": "s-already-saved", "hook_event_name": "Stop"})
        check("nothing", "a reply whose work another run had already saved records no commit",
              record.get("commits") == [] and record.get("state") == "clean",
              "%s %s" % (record.get("state"), record.get("commits")))
    finally:
        if was_vault is None:
            os.environ.pop("MOBLEE_VAULT", None)
        else:
            os.environ["MOBLEE_VAULT"] = was_vault


def test_registration():
    """(v0.10.0) Which wiki the registered hook names.

    safety/install-safety.py matched on the SCRIPT'S NAME and not on the path,
    while the command it writes carries the wiki's whole path as it stood at
    install. So a hook naming a wiki that has been moved, renamed, or is simply
    a different wiki on the same Mac read as "already registered, nothing to
    change" — which meant a second wiki never saved itself, its conversations
    committed the first one, and neither the updater nor the app's Repair could
    ever put it right. Read here through install-safety's own functions.
    """
    spec = importlib.util.spec_from_file_location(
        "install_safety", PACK / "safety" / "install-safety.py")
    safety = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(safety)

    root = Path(tempfile.mkdtemp(prefix="turn-end-registration-",
                                 dir=os.environ.get("TMPDIR") or None))
    WIKIS.append(root)
    first, second = root / "A wiki of one's own", root / "Another wiki"
    for v in (first, second):
        write(v / "scripts" / "turn-end-commit.py", "# a stand-in for the real one\n")

    def entry(v):
        return {"hooks": [{"type": "command", "command": safety.turn_end_cmd(v)}]}

    check("registered", "a hook naming this wiki's own copy of the script reads as registered",
          safety.codex_stop_present([entry(first)], first) is True)
    check("registered", "a hook naming ANOTHER wiki's copy does not read as this one registered",
          safety.codex_stop_present([entry(second)], first) is False)
    mine, others = safety.stop_state([entry(second)], first)
    check("registered", "and the other wiki's hook is named, so it can be reported and left alone",
          mine is False and others == [str(second / "scripts" / "turn-end-commit.py")], others)
    mine, others = safety.stop_state([entry(second), entry(first)], first)
    check("registered", "with both entered, this wiki's is found and the other is still named",
          mine is True and len(others) == 1, "%s %s" % (mine, others))
    gone = root / "a wiki that was renamed"
    check("registered", "a hook naming a wiki that is no longer there is not called registered",
          safety.codex_stop_present([entry(gone)], first) is False)
    check("registered", "a path written with ~ for the home folder is read the same way",
          safety.stop_state([{"hooks": [{"command": "python3 '~/A wiki/scripts/"
                                                    "turn-end-commit.py'"}]}],
                            Path.home() / "A wiki")[0] is True)
    check("registered", "a command this cannot read matches no wiki, which is the safe way round",
          safety.stop_state([{"hooks": [{"command": "python3 \"unclosed turn-end-commit.py"}]}],
                            first)[0] is False)
    # The words every surface now uses for ChatGPT's Trust step name both of
    # Moblee's hooks. This release enters two and the step named one.
    printed = (PACK / "safety" / "install-safety.py").read_text(encoding="utf-8")
    step = [l.strip() for l in printed.splitlines() if "Press Trust beside" in l]
    check("registered", "the Trust step names both of Moblee's hooks, not only the delete guard",
          len(step) == 1 and "each hook Moblee has entered" in step[0], str(step)[:80])
    joined = " ".join(printed.split())
    check("registered", "and the sentence it is part of names each of them by its file",
          "one ends bash-guard.py" in joined
          and "one ends turn-end-commit.py, which saves your wiki." in joined,
          str(step)[:80])


def test_lock(mod):
    """Two runs at once: one run holds the wiki at a time."""
    vault, home, _ = new_wiki("lock")
    write(vault / "wiki" / "Shed.md", "# Shed\n\nThe door sticks.\n")
    before = history(vault, home)
    held = (vault / ".git" / "turn-end-commit.lock").open("w")
    fcntl.flock(held, fcntl.LOCK_EX)
    was_wait, was_vault = mod.LOCK_WAIT_SECONDS, os.environ.get("MOBLEE_VAULT")
    mod.LOCK_WAIT_SECONDS = 1          # a test should not wait the real 90 seconds
    os.environ["MOBLEE_VAULT"] = str(vault)
    try:
        started = time.monotonic()
        record = mod.run({"session_id": "s-second", "hook_event_name": "Stop"})
        waited = time.monotonic() - started
    finally:
        mod.LOCK_WAIT_SECONDS = was_wait
        if was_vault is None:
            os.environ.pop("MOBLEE_VAULT", None)
        else:
            os.environ["MOBLEE_VAULT"] = was_vault
        fcntl.flock(held, fcntl.LOCK_UN)
        held.close()
    check("lock", "a second run while one is in progress waits, then says it did nothing",
          record.get("state") == "busy" and waited >= 0.9,
          "%s after %.1fs" % (record.get("state"), waited))
    check("lock", "and it saves nothing at all while the other run holds the wiki",
          record.get("commits") == [] and history(vault, home) == before,
          record.get("reason", "")[:50])
    # With the lock free again, the same work goes in as usual.
    done, record = run_script(vault, home, {"session_id": "s-after-lock",
                                            "hook_event_name": "Stop"})
    check("lock", "once the other run has finished, the next reply saves as usual",
          record.get("state") == "committed" and dirty(vault, home) == "",
          record.get("state"))


def test_waits_for_git(mod):
    """A git command another conversation is running, and a wiki caught in the
    middle of something. Driven from the inside so that the waiting times can
    be shortened; nothing is deleted to clear a lock, it is renamed aside, which
    is what git's own commands do when they finish."""
    vault, home, _ = new_wiki("busy-git")
    write(vault / "wiki" / "Porch.md", "# Porch\n\nRepainted.\n")
    index_lock = vault / ".git" / "index.lock"
    index_lock.write_text("", encoding="utf-8")
    was_wait, was_vault = mod.INDEX_LOCK_WAIT_SECONDS, os.environ.get("MOBLEE_VAULT")
    mod.INDEX_LOCK_WAIT_SECONDS = 1     # a test should not wait the real 20 seconds
    os.environ["MOBLEE_VAULT"] = str(vault)
    try:
        record = mod.run({"session_id": "s-git-busy", "hook_event_name": "Stop"})
        check("lock", "a git command another conversation is running is waited for",
              record.get("state") == "busy"
              and "still running after" in record.get("reason", "")
              and history(vault, home)[-1]["subject"] == "the first save",
              record.get("reason", "")[:40])

        # The other conversation's command finishes: its lock goes.
        os.rename(index_lock, vault / ".git" / "index.lock.finished")
        record = mod.run({"session_id": "s-git-free", "hook_event_name": "Stop"})
        check("lock", "and once that command has finished, the save goes ahead",
              record.get("state") == "committed" and dirty(vault, home) == "",
              record.get("state"))

        # A wiki caught in the middle of something git is doing.
        write(vault / "wiki" / "Steps.md", "# Steps\n\nRe-pointed.\n")
        (vault / ".git" / "MERGE_HEAD").write_text("0" * 40 + "\n", encoding="utf-8")
        record = mod.run({"session_id": "s-mid-merge", "hook_event_name": "Stop"})
        # Recorded as "paused" and not as "busy". They are two different things
        # and the check-up has to tell them apart: "busy" means something else
        # really was saving the wiki and the next reply's save takes what this
        # one missed, which of a half-finished merge is not true.
        check("lock", "a wiki caught in the middle of something is left alone",
              record.get("state") == "paused"
              and "middle of something" in record.get("reason", "")
              and "wiki/Steps.md" in dirty(vault, home),
              record.get("reason", "")[:40])
        os.rename(vault / ".git" / "MERGE_HEAD", vault / ".git" / "MERGE_HEAD.finished")

        # (v0.10.0) The other two markers git leaves while it is halfway
        # through a change of its own. A bisect is how an owner's assistant
        # walks back through the history to find when a page changed.
        for marker in ("BISECT_LOG", "REVERT_HEAD"):
            (vault / ".git" / marker).write_text("0" * 40 + "\n", encoding="utf-8")
            record = mod.run({"session_id": "s-mid-" + marker, "hook_event_name": "Stop"})
            check("lock", "a wiki in the middle of a %s is left alone too" % marker,
                  record.get("state") == "paused" and marker in record.get("reason", "")
                  and "wiki/Steps.md" in dirty(vault, home),
                  record.get("reason", "")[:50])
            os.rename(vault / ".git" / marker, vault / ".git" / (marker + ".finished"))
    finally:
        mod.INDEX_LOCK_WAIT_SECONDS = was_wait
        if was_vault is None:
            os.environ.pop("MOBLEE_VAULT", None)
        else:
            os.environ["MOBLEE_VAULT"] = was_vault


def test_detached():
    """The run detaches, so a reply never waits for it."""
    vault, home, _ = new_wiki("detached")
    write(vault / "wiki" / "Gutters.md", "# Gutters\n\nCleared in October.\n")
    started = time.monotonic()
    done, _ = run_script(vault, home, {"session_id": "s-detached",
                                       "hook_event_name": "Stop"}, args=())
    handed_back = time.monotonic() - started
    check("detached", "the hook is handed back at once, with nothing printed at it",
          done.returncode == 0 and done.stdout == "" and handed_back < 10,
          "%.2fs" % handed_back)
    waited, record = 0.0, {}
    while waited < 30:
        record = records(home).get("s-detached", {})
        if record.get("state") in ("committed", "blocked", "error", "clean"):
            break
        time.sleep(0.2)
        waited += 0.2
    saves = history(vault, home)
    check("detached", "the detached half still does the save and writes its record",
          record.get("state") == "committed"
          and saves[-1]["files"] == ["wiki/Gutters.md"]
          and dirty(vault, home) == "",
          record.get("state") or "no record after %.0fs" % waited)
    return vault, home


def test_payloads():
    """Hook messages that say less than Claude's does."""
    # No conversation record at all. This practice wiki and its sandboxed home
    # are handed on to the groups below, which read the record and the log this
    # run left in their real default places.
    plain_vault, plain_home, _ = new_wiki("no-transcript")
    vault, home = plain_vault, plain_home
    write(vault / "wiki" / "Hedge.md", "# Hedge\n\nTrimmed.\n")
    done, record = run_script(vault, home, {"session_id": "s-no-transcript",
                                            "hook_event_name": "Stop"})
    saves = history(vault, home)
    check("payload", "a message with no conversation record saves everything as changes found",
          record.get("state") == "committed"
          and [s["subject"] for s in saves[1:]] == [FOUND_SUBJECT],
          [s["subject"] for s in saves[1:]])
    check("payload", "and the record carries a plain title, with nothing left over",
          record.get("title") == "a conversation"
          and record.get("own_left") == [] and record.get("other_left") == [],
          record.get("title"))

    # A null conversation record, which the other assistant's hook can send.
    vault, home, _ = new_wiki("null-transcript")
    write(vault / "wiki" / "Fence.md", "# Fence\n\nTwo posts replaced.\n")
    done, record = run_script(vault, home, {
        "session_id": "s-null", "transcript_path": None, "cwd": str(vault),
        "hook_event_name": "Stop", "turn_id": "t-1", "stop_hook_active": False,
        "last_assistant_message": "All done.", "permission_mode": "default"})
    saves = history(vault, home)
    check("payload", "a message whose conversation record is empty is treated the same way",
          done.returncode == 0 and record.get("state") == "committed"
          and [s["subject"] for s in saves[1:]] == [FOUND_SUBJECT]
          and record.get("title") == "a conversation",
          record.get("title"))

    # A conversation record written in a shape this cannot read.
    vault, home, _ = new_wiki("odd-transcript")
    write(vault / "wiki" / "Drive.md", "# Drive\n\nRe-gravelled.\n")
    odd = Path(vault).parent / "rollout-2026-10-14.jsonl"
    write(odd, "this is not the shape Claude writes\n"
               '{"not": "an event", "tool_use": "but it mentions one"}\n'
               '{"type": "response_item", "payload": {"type": "function_call", '
               '"name": "shell", "arguments": "{\\"command\\": [\\"ls\\"]}"}}\n'
               "{unclosed json\n")
    done, record = run_script(vault, home, {
        "session_id": "s-odd", "transcript_path": str(odd), "hook_event_name": "Stop"})
    saves = history(vault, home)
    check("payload", "a conversation record this cannot read falls back to changes found",
          [s["subject"] for s in saves[1:]] == [FOUND_SUBJECT]
          and record.get("title") == "a conversation",
          record.get("title"))
    check("payload", "and reading it never fails the run",
          done.returncode == 0 and record.get("state") == "committed"
          and "Traceback" not in done.stderr, done.stderr.strip()[:50])

    # No conversation id.
    vault, home, _ = new_wiki("no-session")
    write(vault / "wiki" / "Path.md", "# Path\n\nSlabs relaid.\n")
    done, record = run_script(vault, home, {"hook_event_name": "Stop",
                                            "cwd": str(vault)})
    check("payload", "a message with no conversation id is still saved and still recorded",
          done.returncode == 0 and record.get("state") == "committed"
          and record.get("session") == "unknown"
          and "unknown" in records(home), record.get("session"))
    return plain_vault, plain_home


def test_paths(vault, home):
    """Where the record and the log are kept. Run against the practice home a
    case above has already used, so these are the real default places."""
    check("paths", "the record is kept at ~/.config/moblee/state/turn-end-commit.json",
          state_file(home).is_file(), state_file(home))
    check("paths", "the log is kept at ~/.config/moblee/logs/turn-end-commit.log",
          log_file(home).is_file()
          and len(log_file(home).read_text(encoding="utf-8").splitlines()) >= 1,
          log_file(home))
    check("paths", "nothing is written inside either assistant's own folder",
          not (home / ".claude").exists() and not (home / ".codex").exists(),
          sorted(p.name for p in home.iterdir()))

    # The two overrides the pack's tests use, proved rather than assumed.
    other_vault, other_home, _ = new_wiki("overrides")
    write(other_vault / "wiki" / "Shelves.md", "# Shelves\n\nPut up.\n")
    elsewhere = other_home / "somewhere else"
    done, record = run_script(
        other_vault, other_home, {"session_id": "s-overrides",
                                  "hook_event_name": "Stop"},
        extra_env={"MOBLEE_TURN_END_STATE": str(elsewhere / "record.json"),
                   "MOBLEE_TURN_END_LOG": str(elsewhere / "run.log")})
    check("paths", "MOBLEE_TURN_END_STATE and MOBLEE_TURN_END_LOG move both files",
          record.get("state") == "committed"
          and (elsewhere / "record.json").is_file()
          and (elsewhere / "run.log").is_file()
          and not state_file(other_home).exists()
          and not log_file(other_home).exists(),
          sorted(p.name for p in elsewhere.iterdir()) if elsewhere.is_dir() else "none")


def test_pruning():
    """Records over 30 days old are dropped by rewriting the one record file."""
    vault, home, _ = new_wiki("pruning")
    write(vault / "wiki" / "Attic.md", "# Attic\n\nInsulated.\n")
    old = (datetime.datetime.now().astimezone()
           - datetime.timedelta(days=90)).isoformat(timespec="seconds")
    recent = (datetime.datetime.now().astimezone()
              - datetime.timedelta(days=2)).isoformat(timespec="seconds")
    seeded = {
        "s-ninety-days-ago": {"session": "s-ninety-days-ago", "title": "An old conversation",
                              "at": old, "state": "committed", "commits": ["aaaaaaa"],
                              "own_left": [], "other_left": [], "reason": ""},
        "s-two-days-ago": {"session": "s-two-days-ago", "title": "A recent conversation",
                           "at": recent, "state": "committed", "commits": ["bbbbbbb"],
                           "own_left": [], "other_left": [], "reason": ""},
    }
    write(state_file(home), json.dumps(seeded, indent=1) + "\n")
    was_inode = state_file(home).stat().st_ino
    files_before = files_under(home)

    done, record = run_script(vault, home, {"session_id": "s-today",
                                            "hook_event_name": "Stop"})
    kept = records(home)
    check("pruning", "a record over 30 days old is dropped",
          "s-ninety-days-ago" not in kept, sorted(kept))
    check("pruning", "the records either side of it are kept",
          "s-two-days-ago" in kept and "s-today" in kept, sorted(kept))
    check("pruning", "the record file is rewritten in place: the same file, not a new one",
          state_file(home).stat().st_ino == was_inode,
          "%s then %s" % (was_inode, state_file(home).stat().st_ino))
    check("pruning", "and no file anywhere under the home folder disappeared",
          files_before <= files_under(home),
          sorted(files_before - files_under(home))[:3])

    # A record file full of nonsense: the run must still work and still record.
    vault2, home2, _ = new_wiki("bad-record")
    write(vault2 / "wiki" / "Cellar.md", "# Cellar\n\nDamp-proofed.\n")
    write(state_file(home2), "{this is not json at all\n")
    done, record = run_script(vault2, home2, {"session_id": "s-after-nonsense",
                                              "hook_event_name": "Stop"})
    check("pruning", "a record file that cannot be read is treated as empty, never as an error",
          done.returncode == 0 and record.get("state") == "committed"
          and "s-after-nonsense" in records(home2), done.stderr.strip()[:50])


def test_safety():
    """Read from the script's own text.

    Every name looked for below is spelled in two halves on purpose. Spelled
    out whole, this test file would itself read to the pack's safety guard as a
    script that deletes or rewrites, and then it could not be run from a shell
    at all — which is exactly the guard doing its job.
    """
    text = SCRIPT.read_text(encoding="utf-8")

    def found(*halves):
        """Which of these names appear in the script. None of them should."""
        return [n for n in halves if n in text]

    deleting = found("un" + "link(", "os.re" + "move(", "r" + "mtree",
                     "os.rm" + "dir", "shutil", "missing_ok")
    check("safety", "the script names no way of deleting a file",
          deleting == [], deleting)
    bypass = found("--no-" + "ver" + "ify", "GATE_" + "SOFT")
    check("safety", "the script never bypasses the commit gate",
          bypass == [], bypass)
    sending = found('"pu' + 'sh"', '"fe' + 'tch"', '"rem' + 'ote"')
    check("safety", "the script never sends the wiki anywhere",
          sending == [], sending)
    rewriting = found("--" + "hard", "--" + "force", "filter-" + "bra" + "nch",
                      '"reba' + 'se"', '"res' + 'et"')
    check("safety", "the script never rewrites the wiki's history",
          rewriting == [], rewriting)
    # (v0.10.0) The two assistants' own folders. The plain word is no longer
    # the test, because the script now has to NAME one of them: ".claude/"
    # inside the WIKI, which is where Moblee keeps the wiki's permission rules
    # and which the end-of-reply save deliberately leaves for the owner. What
    # is tested is the thing that would matter — a path built out of the home
    # folder into one of them — and then, below, that the only folder the
    # script reaches out of the home folder for is Moblee's own.
    homely = [l.strip() for l in text.splitlines()
              if (".cla" + "ude") in l or (".co" + "dex") in l]
    reaching = [l for l in homely
                if "home" in l.lower() or "expanduser" in l or "~/" in l]
    check("safety", "nothing in the script writes inside an assistant's own folder",
          reaching == [], reaching[:1])
    homes = re.findall(r"Path\.home\(\)\s*/\s*\"([^\"]+)\"", text)
    check("safety", "and the only folder it reaches out of the home folder for is Moblee's own",
          set(homes) == {".config"}, sorted(set(homes)))
    # Whole words, so that ordinary English is not mistaken for a relation
    # ("reason" holds "son"). This script is part of a public product: it must
    # name no person, no family relation and no private place.
    private = re.findall(
        r"\b(?:mosabs|mohammed|macbook|mac mini|wife|husband|father|mother|"
        r"brother|sister|son|daughter|uncle|aunt|cousin)\b|/users/",
        text.lower())
    check("safety", "the script names nobody, no relation and no private place",
          private == [], sorted(set(private)))


def test_by_hand(vault, home):
    """The two switches an owner or a helper might use, and a folder that is
    not a wiki with a history."""
    done, _ = run_script(vault, home, {}, args=("--status", "s-no-transcript"))
    try:
        shown = json.loads(done.stdout)
    except ValueError:
        shown = {}
    check("by hand", "--status prints that one conversation's record",
          done.returncode == 0 and shown.get("session") == "s-no-transcript"
          and shown.get("state") == "committed", done.stdout.strip()[:50])
    done, _ = run_script(vault, home, {}, args=("--status", "never-happened"))
    check("by hand", "--status for a conversation it has never seen prints an empty record",
          done.returncode == 0 and done.stdout.strip() in ("{}", "{\n}"),
          done.stdout.strip()[:30])
    done, _ = run_script(vault, home, {}, args=("--help",))
    check("by hand", "--help explains it in plain words and exits 0",
          done.returncode == 0 and "end of every reply" in done.stdout
          and "ever deleted" in done.stdout.lower()
          and "~/.config/moblee/state/" in done.stdout, done.returncode)
    done, _ = run_script(vault, home, {}, args=("--wipe-everything",))
    check("by hand", "a switch it does not know is refused in plain words, and does nothing",
          done.returncode == 2 and "not something this understands" in done.stderr,
          done.stderr.strip()[:50])

    plain = Path(tempfile.mkdtemp(prefix="turn-end-not-a-wiki-",
                                  dir=os.environ.get("TMPDIR") or None))
    WIKIS.append(plain)
    (plain / "home").mkdir()
    done, record = run_script(plain, plain / "home", {"session_id": "s-nowhere",
                                                      "hook_event_name": "Stop"})
    check("by hand", "a folder that is not a wiki with a history is reported, not crashed",
          done.returncode == 0 and record.get("state") == "error"
          and "no wiki with a history" in record.get("reason", ""),
          record.get("reason", "")[:50])


def main():
    print("Testing %s" % SCRIPT)
    mod = load_script()
    test_two_parts()
    test_clean()
    test_gate_stops_a_file()
    test_rename_and_deletion()
    test_already_staged()
    test_detached_head()
    test_owners_own_work()
    test_half_staged()
    test_index_left_as_found()
    test_nothing_to_commit(mod)
    test_registration()
    test_lock(mod)
    test_waits_for_git(mod)
    test_stale_lock(mod)
    test_detached()
    payload_vault, payload_home = test_payloads()
    test_paths(payload_vault, payload_home)
    test_pruning()
    test_safety()
    test_by_hand(payload_vault, payload_home)

    width = max(len(r[2]) for r in ROWS)
    print("")
    print("%-4s %-9s %-*s %s" % ("", "group", width, "case", "note"))
    for status, group, label, note in ROWS:
        print("%-4s %-9s %-*s %s" % (status, group, width, label, note))
    print("")
    print("%d passed, %d failed, of %d." % (len(ROWS) - FAILURES, FAILURES, len(ROWS)))
    print("Practice wikis and sandboxed homes are left in place:")
    for w in WIKIS:
        print("  %s" % w)
    print("Run on %s" % datetime.date.today().isoformat())
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
