# install-test

Runs the real `scripts/install.sh` from start to finish against throwaway wikis
and checks what it actually did. Sibling of `tools/update-test/`, which does the
same for the updater; the two work the same way and share their lessons.

## Running it

From the Moblee folder:

```
bash tools/install-test/run.sh
```

One case at a time: `bash tools/install-test/run.sh refused`.

It prints a line per check and a pass/fail count, and exits non-zero if anything
failed. The scratch directory is left behind so a failure can be inspected; its
path is the last line.

**A release that changes `scripts/install.sh` runs this first.**

## What each case proves

| Case | What it proves |
|---|---|
| `happy` | An ordinary install finishes, commits its own settings, records a finish in the diary, tells the app the run finished, and claims nothing outstanding on screen. |
| `refused` | When git refuses the closing commit, the diary, the screen and the run-level state the app reads all say so, the closing step is not marked done, and the work is staged rather than lost. |

## Why it exists

On 23 September 2026 a code review found that the installer still carried the
fault fixed in the updater that same morning: its closing commit's stderr went
to `/dev/null` and its exit code to `|| true`, so a refusal was silenced and the
script went on to record a finish, print the Done banner, and tell the app to
green every tile. The morning's fix had never been carried across.

The `refused` case was run against the pre-fix installer before the fix was
accepted. It reported `{"step":"done","state":"ok"}` to the app, wrote
`finish: done` and `=== Moblee install finished ===` to the diary, and exited 0 —
over a wiki holding one commit and three files staged and never committed. That
is what this case now catches.

## How the refusal is made real

It is the pack's own commit gate refusing, not a simulation. The wiki under test
is one an earlier install left half-finished — the recovery path the installer
is written for, and the one the app's Repair button takes — whose `wiki/Index.md`
has grown past the gate's 8,000-token cap (G3). The gate is wired before the
closing commit, the starting-memories step adds its line to that Index, so the
Index is staged, over its cap, and refused: the same rule and the same shape as
the oversized `CLAUDE.md` that refused a real owner's update on 21 September 2026.

The case installs for ChatGPT, and that is not arbitrary. Measured while writing
it: **on a Claude install the closing commit stages one file,
`.claude/settings.local.json`**, which no gate rule caps or reads — the starting
memories go to `~/.claude/`, so the wiki's Index is never touched and the gate
has nothing of its own to judge. ChatGPT's memories are a wiki page and the Index
gains the line that links it, so that is the install whose closing commit the
pack's gate can refuse today. The reporting being tested is shared by both, and
the Claude path's silence was latent rather than live.

## Safety

The installer writes into the HOME it is given — `~/.claude` (the delete guard,
the permission rules, the skills, the starting memories), `~/.config/moblee`,
`~/.codex`. On a machine where `~/.claude/skills` is a symlink into a live vault,
running it against a real HOME would write over real skills. Every case therefore
sets HOME to a throwaway directory under `TMPDIR`, and the script refuses to
start if that is not so. Nothing outside that directory is written or removed.

The vault location is never created by the rig's `start`: the installer refuses
to write into a folder that already exists, and a case that wants one (the
half-finished wiki) makes it itself and says why.

## A note for whoever runs this with an assistant

Unlike `tools/update-test/`, this rig ran under a delete guard that scans script
files (verified 23 September 2026 on the author's MacBook Pro). The updater trips
such a guard because it legitimately writes a `VERSION` file into a wiki; the
installer, which only ever writes into a folder it made itself, does not. If a
guard does refuse it, run it yourself in Terminal rather than asking the
assistant to.
