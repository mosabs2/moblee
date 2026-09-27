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

An alternative for Cowork is a `vault` shell function installed once on the owner's machine, which commits everything accumulated at the start of their next Claude Code session. Cowork sessions then leave the working tree dirty and note what changed in their `wiki/log.md` entry, which is the audit trail.

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
