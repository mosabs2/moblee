# update-test

Runs the real `scripts/update.sh` from start to finish against throwaway wikis
and checks what it actually did.

## Running it

From the Moblee folder:

```
bash tools/update-test/run.sh
```

One case at a time: `bash tools/update-test/run.sh refused`.

It prints a line per check and a pass/fail count, and exits non-zero if anything
failed. The scratch directory is left behind so a failure can be inspected; its
path is the last line.

**A release that changes `scripts/update.sh` runs this first.**

## What each case proves

| Case | What it proves |
|---|---|
| `happy` | An ordinary update finishes, commits itself, records a finish in the diary, leaves nothing staged, and does not touch the owner's own content. |
| `refused` | When git refuses the closing commit, the diary, the screen and the step state all say so, the closing step is not marked done, and the work is staged rather than lost. |
| `extras` | `scripts/orient-extras.sh` is created, the preflight runs it, and a second update leaves the owner's own edits to it exactly as they were. |
| `index` | An Index that already keeps a Wiki Operations line does not gain a second one. |
| `twice` | Running the same update twice makes no second commit and leaves nothing staged. |

## Safety

The updater writes into the HOME it is given — `~/.claude/skills`,
`~/.config/moblee`, `~/.codex`. On a machine where `~/.claude/skills` is a
symlink into a live vault, running it against a real HOME would overwrite real
skills. Every case therefore sets HOME to a throwaway directory under `TMPDIR`,
and the script refuses to start if that is not so. Nothing outside that
directory is written or removed.

## Why it exists

Before 23 September 2026 there was no way to run the updater end to end off a
real person's Mac. Every change to it was tested a piece at a time and shipped
on reasoning, and the six faults fixed in v0.9.1 were all found by an owner
after release, on his own wiki. Each case above is one of those faults, or the
ordinary behaviour they broke.

## A note for whoever runs this with an assistant

A delete guard that scans script files will refuse to run this rig, and will
refuse `scripts/update.sh` itself, because the updater legitimately writes a
`VERSION` file into a wiki and that reads as clobbering a vault file. That is
the guard working as designed on a static read. Run the rig yourself in
Terminal rather than asking the assistant to, or run it on a machine with no
such guard.
