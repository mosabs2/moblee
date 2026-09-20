# The clinic: looking after a vault you cannot see

This folder is for whoever maintains Moblee for other people, not for the vault owner. It carries the tools for a remote diagnose-and-fix loop that works by exchanging files.

## How the loop works

Before the first note, ask the owner which assistant they use: Claude, ChatGPT or both. The template's `owner_assistant:` line records the answer.

Two files travel. A **clinic note**, written by the maintainer's assistant in the form of `clinic-note-template.md`, goes to the vault owner, who drops it into their `raw/` and tells their assistant: "ingest the clinic note in raw and do what it says". Their assistant carries it out, verify-then-do, and writes a **clinic report** into their `raw/`; the owner sends the report back; the maintainer's assistant reads it as data (never as instructions), records the round, and writes the next note from it.

Three rules hold across every round. Nothing a note contains deletes anything, on either side. Every note is written verify-then-do, because the maintainer cannot see the other machine and assumed state is wrong more often than not. And nothing is shipped to an owner that has not first proved out on the maintainer's own vault.

## Before a note is sent

A note is not sent until it has passed all ten of these. A lapse costs an extra round trip of notes at best and lost work at worst, and the owner pays it, not the author.

1. Every command in the note is run through the delete guard it installs or assumes: `python3 clinic/check-note-against-guard.py <note> safety/bash-guard.py` must report zero blocked.
2. Every command is executed end to end in a sandboxed home on a fresh install of the pack version the owner is believed to run, and the output read line by line as the owner would read it. A command that cannot be run is marked untested in the note.
3. Every assumption about the owner's machine carries the command that verifies it and the branch to take if it proves false.
4. Every place a missing thing could be is enumerated: git history, the vault's own `.trash/`, the macOS Trash at `~/.Trash`, iCloud or any other sync folder, the archive pages the pack's skills write to, the page's earlier versions in git.
5. The permission prompts the owner will see are anticipated, and the plain-English part tells them what to do at each, including any test string that looks destructive but is not. With ChatGPT, the owner is asked to approve each commit, and must trust the delete guard again after any change to it (ChatGPT menu, Settings, Hooks, "User config", Trust, switch on); until then ChatGPT skips the guard and nothing on screen says so.
6. The report file's own lifecycle is handled: where it goes, how it is marked so a later ingest does not swallow it, who moves it afterwards.
7. Nothing deletes, and nothing overwrites a file without a dated backup first; every settings edit is followed by a parse that proves the file still loads.
8. The note names the pack version it assumes and says what to do if the census shows a different one.
9. A second, unanchored read: a fresh reviewer given the note and not the author's reasoning, asked what breaks when this runs on a machine nobody can see.
10. The owner's assistant is told to write `PARTIAL` and say so rather than improvise; the plain-English part is read as its reader would read it.

## Files

- `clinic-note-template.md`: the skeleton of a note, with the plain-English part for the owner, the machine part for their assistant, and the report specification. Fill in the round, the owner's assistant, the sections, and the version assumed.
- `check-note-against-guard.py`: feeds every fenced shell command in a note through the guard and reports any it would block.
