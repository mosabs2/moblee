# Git and Commits

How the assistant saves the owner's work. The short rule is in `CLAUDE.md` under "Commit at the end of every piece of work", and it is the one that binds. This page holds the detail behind it.

## The principle

The vault is under git. **The assistant runs git on the owner's behalf. The owner should never need to type, or be asked to type, a git command.** The assistant commits at the close of every unit of wiki work, without prompting and without asking permission.

Git holding every earlier version of every file is what makes the never-delete rule survivable: "put it back the way it was on 14 April" is always possible.

## When to commit

At the natural close of any unit of wiki work, large or small:

- after each ingest pass, once the original has moved to `processed/`;
- after a lint pass, committing the report plus any wiki edits it caused;
- after any housekeeping entry that touched `log.md`, `_context.md` or `Index.md`;
- after any tooling or schema change, including edits to `CLAUDE.md` or to skill files kept in the vault;
- after a comparative analysis, committing the indexing line on the relevant page (the output file itself is gitignored under `outputs/`);
- at the close of any session that touched `wiki/` content at all, even a routine same-pattern ingest.

A session that is a no-op on `wiki/`, a read-only query with nothing saved, needs no commit. Everything else does.

## How to commit

**Claude Code, on a Mac or Linux workstation.** Run `git add .` then `git commit -m "<message>"` through the Bash tool. The machine's global git config carries the author identity. This is fully autonomous and the owner sees nothing.

One exception to `git add .`: when the commit is not an ingest, and a file is sitting in `raw/` or `Clippings/` that has not been ingested yet, add only the paths the work actually touched. A source should first be committed by the ingest that reads it, not swept into an unrelated housekeeping commit.

**ChatGPT.** The same two commands, with the same exception. ChatGPT's sandbox protects `.git`, so it asks the owner to approve each commit. That is expected, and it is not a reason to skip the commit.

**Claude in Cowork.** Two platform constraints block full autonomy today. The workspace bash mount uses a bindfs FUSE filesystem that blocks the `unlink` syscall, and git relies on unlinking `.git/index.lock` after every operation, even a read-only `git status`; attempting git in the sandbox leaves stale lock files behind. Terminal is also granted at tier "click" under Anthropic's app policy, so computer-use cannot type into it either.

The workable mechanism is the **clipboard handoff**. Claude composes the full git command, including any stale-lock cleanup (`rm -f .git/index.lock .git/index.lock.stale`) if an earlier sandbox attempt left files behind, writes it to the owner's clipboard with `mcp__computer-use__write_clipboard` (which needs `clipboardWrite: true` in the `request_access` call), brings Terminal forward with `open_application` if needed, and asks the owner to paste and press Return. Two keystrokes, with nothing to remember.

A Cowork session that cannot commit leaves its work unsaved and notes what it changed in its `wiki/log.md` entry, which is the audit trail. It does not stay unsaved: the end-of-reply save below picks it up, as changes found in the wiki, at the end of the next reply in any conversation. Some owners also have a `vault` shell function installed on their machine, which commits everything accumulated at the start of their next Claude Code session.

## The wiki saves itself at the end of every reply

From v0.10.0 the wiki has a second way of being saved, and it needs nobody to ask for it. `scripts/turn-end-commit.py`, inside the wiki, is wired as the assistant's Stop hook — with Claude and with ChatGPT alike — so it runs once a reply has finished. It saves in up to two parts: the files that conversation changed itself, under the conversation's own title, and anything else it finds changed as "changes found in the wiki".

**This is a backstop, not a replacement for the commits above.** The assistant still saves each piece of work itself, under its own description, because that is the message the owner reads months later. The end-of-reply save only catches what is left over. That matters most when the owner walks away mid-task: without it, their next message in that conversation has to be "save everything", which is the dearest message of the day, because the assistant re-reads the whole conversation before it can do anything.

The commit gate runs on it exactly as on any other save. When the gate stops a part, every file in that part is offered again on its own, so one unhappy file cannot hold back the rest. The files the gate still stops are left unsaved and named in the record. The save never pushes, never deletes and never gets round the gate.

**What it leaves alone, and names in the record instead.** Three things, and none of them is a fault:

- **The owner's own uncommitted work**, which is this hook's business to leave: the rules file, `AGENTS.md`, `.gitignore`, and anything in `scripts/`, `dashboard/` or `.claude/`. It is left for the owner's own next commit, exactly as `scripts/update.sh` leaves it, and for the same reason: an update can print "nothing of yours was committed" and a reply can end seconds later, and the two must not contradict each other.
- **A file somebody has staged and changed again since.** Naming a path in a commit takes what is on the disk, which would throw away the snapshot they staged on purpose.
- **The whole wiki while its history is not on a branch** (git's detached HEAD — an older version of a page being looked at, a bisect). A save made then belongs to no branch and is gone from the wiki the moment it goes back to one.

**Nobody is told any of this by itself.** The hook's own output goes nowhere, and nothing puts the record into the next reply. So the record is the thing to read, and reading it is the assistant's job:

- **when the owner asks what is unsaved**, and
- **when a session opens on a wiki whose `git status` shows changes from earlier work** — which is the moment the rules file already tells you to commit those first.

Read it, and say plainly what is in it. Never let the owner believe work was saved when it was not. The owner's own two ways of seeing it without asking are **the Moblee check-up** (`moblee-doctor.py`, or "Check my wiki" in the app), which reports what the last save left, and **the band above the prompt** in Claude, which says whether the wiki's work is saved — but only when it appears, which is on a long conversation that has gone cold.

Where the record is kept:

- `~/.config/moblee/state/turn-end-commit.json` — one record per conversation: what was saved, what the gate stopped (`own_left`, `other_left`), what was left for the owner's own commit (`yours_left`, `staged_left`). Kept for 30 days.
- `~/.config/moblee/logs/turn-end-commit.log` — one line per run.

**A leftover `index.lock`.** While `.git/index.lock` sits in the wiki, nothing can be saved at all — not this hook, not your own commits — and nothing in git ever clears it. The hook does not clear it either: it records that it found one, and the check-up tells the owner (field guide F49). Clearing it is a person's decision, because a lock that really does belong to a running git command must not be taken away behind its back. So: make sure nothing else is using the wiki, then move the file aside — `mv .git/index.lock .git/index.lock.old` — rather than deleting it, and try the commit again.

To read one conversation's record, from the wiki:

```
python3 scripts/turn-end-commit.py --status <conversation id>
```

## When a commit is refused

The commit gate (`scripts/vault-gate.py`, reached through `scripts/hooks/pre-commit` and `core.hooksPath`) refuses commits that break the structural conventions, and refuses every commit in the vault when an always-loaded file is over its token cap.

If a commit is refused, say so plainly in one sentence, say which files are now uncommitted, and say what would clear it. Never let the owner believe work was saved when it was not. The work stays staged; it is not lost.

## Message format

One short imperative line, aligned with the log entry the commit accompanies:

| Kind of work | Message |
|---|---|
| Ingest | `ingest: <Title>, <Publication>` |
| Housekeeping summary | `housekeeping: <descriptor>` |
| Infrastructure | `tooling: <descriptor>` |
| Schema or conventions | `schema: <descriptor>` |
| Lint pass | `lint: <date> health check` |
| Correction | `correction: <descriptor>` |

## Catching up

If a session opens and `git status` shows untracked or modified files left from earlier work, commit those first, with descriptive messages based on what is actually there, before starting anything new.

## Recording in the log

A substantive commit is referenced by short hash in the relevant log entry's `tooling/schema:` field or housekeeping footer, when the work merits it. Routine commits need no hash recorded; the git log is the canonical record.
