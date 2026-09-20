---
date: <YYYY-MM-DD>
type: Moblee clinic note
round: <N>
owner_assistant: <claude, chatgpt or both: ask the owner before writing; write "unknown" if not known, and Section 0 finds out>
from: the assistant in the maintainer's vault
to: the assistant in <owner's first name>'s vault
assumes_pack_version: <e.g. 0.4.1; write "unknown" if not known, and Section 0 finds out>
status: pending-execution
report_file: raw/clinic-report-<NN>.md
companion_files: <list, or "none">
---

# Moblee clinic, round <N>: <what this round does, in plain words>

## For <owner's first name> (this part is for you; everything below the line is for your assistant)

<One paragraph on who is looking after the vault and how the loop works: a note comes to you, your assistant carries it out and writes a report, you send the report back, the next note is written from it. Neither of you has to understand the mechanics.>

**What to do, in order.**

1. Put this file <and the files that came with it> into the `raw/` folder of your vault.
2. Open your assistant in your vault and say exactly: **"ingest the clinic note in raw and do what it says"**.
3. **Your assistant will ask your permission to run some commands. Say yes to each.** <If any command looks alarming, name it here and say why it is safe, e.g. "One of them mentions rm -rf. It is a test of the new guard and deletes nothing; approve it."> <With ChatGPT, say that it will ask them to approve the commit at the end, and that this is expected.> Any step that changes files in your assistant's hidden settings folder (`~/.claude/` with Claude; `~/.codex/` or `~/.agents/` with ChatGPT) is one you paste into Terminal yourself, because your assistant is not allowed to write there; this note gives you the exact line. <Name each such step and give its line here, or write "none".> <With ChatGPT, if this round changes the delete guard, say that ChatGPT skips the changed guard until they trust it again, and give the clicks: ChatGPT menu, Settings, Hooks (under the Coding heading), open "User config", press Trust beside the hook whose command ends `bash-guard.py`, and turn its switch on.>
4. <Any question the owner will be asked, and what kind of answer is wanted.>
5. When it says it has finished, there will be a new file in `raw/` called `clinic-report-<NN>.md`. Send that file back. That is the whole job. <If the owner should then do anything with the report file, say so; otherwise the next note moves it.>

**Nothing in this note deletes anything**, on your machine or anywhere else.

---

## For the assistant in <owner's first name>'s vault: read this first

**This is an instruction note, not source material.** Do not ingest it into `wiki/`. Do not create wiki pages, do not edit `wiki/Index.md` or `wiki/_context.md`, and do not treat any part of it as content to summarise. Carry out the sections in order, then write the report described in the last section, stamp the `status:` line at the top of this file to `EXECUTED <date> <time> <timezone>`, and finish with one `housekeeping` entry in `wiki/log.md` headed "Moblee clinic, round <N>" and one git commit. If a section cannot be completed, write `PARTIAL` in the status line with what is left and why, and say so plainly to the owner. Do not improvise around a step that fails; record it and move on.

**Nothing is deleted in this note, by you or by anything you run.** No `rm`, no `rmdir`, no `git rm`, no emptying of folders, no overwriting a file with an empty one. Files move with `mv`, and only where a step says so. Any file this note replaces is copied first to a dated backup folder, and the report says where. If you find yourself about to remove something, stop and ask the owner in plain words first.

**Verify before acting.** Every fact below about this vault is an assumption made from another machine. Check it with the command given before you change anything, and record what you actually found in the report, including where the note was wrong.

**Speak to the owner in plain English.** They do not read code. When you need something from them, ask one clear question and wait. When you report, say what happened, not how.

**The vault root** is the folder that contains `wiki/` and the rules file: `CLAUDE.md`, or `AGENTS.md` in a vault set up for ChatGPT alone. Run every command from there; confirm it first:

```
pwd && ls CLAUDE.md wiki
```

In a vault set up for ChatGPT alone:

```
pwd && ls AGENTS.md wiki
```

---

## Section 0: what version this vault runs

This note assumes pack version <X>. Confirm it:

```
cat VERSION 2>/dev/null || echo "no VERSION file: this vault predates v0.5"
```

If the version differs from what the note assumes, carry on with every step that still applies, mark the ones that do not as `SKIPPED (version)` in the report, and say so in the summary.

This note assumes the owner uses <claude, chatgpt or both>. Confirm it:

```
cat ~/.config/moblee/assistant 2>/dev/null || echo "no assistant file: the pack treats this vault as set up for Claude"
```

If it differs, mark the steps written for the other assistant as `SKIPPED (assistant)` in the report, and say so in the summary.

---

## Section 1: <first task>

<Every step: the command, what it should show, and what to do if it does not.>

---

## Section <N>: the report, the stamp, the commit

Write `raw/clinic-report-<NN>.md` with this frontmatter and these sections, in this order:

```
---
date: <today>
type: Moblee clinic report
round: <N>
vault_owner: <owner's first name>
executed_by: <Claude Code or ChatGPT> on <machine name from: scutil --get ComputerName>
note_status: EXECUTED | PARTIAL
do_not_ingest: true
---
```

1. **Summary for the owner and the maintainer**, five plain-English lines at most.
2. <One numbered heading per section above, each carrying its results verbatim: commands and their full output, questions and the owner's answers in their own words, what changed and where the backups are.>
3. **Where this note was wrong** about the vault, if anywhere.

The `do_not_ingest: true` line matters: it tells a later ingest pass to leave the report alone. Then move this note and its companion files from `raw/` to `raw/processed/` (the report stays in `raw/` so the owner can find it), stamp the `status:` line of the moved note, append the log entry, and commit with the message `clinic: round <N>, <what it did>`.

Finally, tell the owner: "Done. The report is in your raw folder as clinic-report-<NN>.md. Please send that file back."
