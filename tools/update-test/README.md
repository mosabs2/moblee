# update-test

Runs the real `scripts/update.sh` from start to finish against throwaway wikis
and checks what it actually did. Sibling of `tools/install-test/`, which does the
same for the installer.

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
| `happy` | An ordinary update finishes, commits itself, records a finish in the diary, leaves nothing staged, and does not touch the owner's own content. Its rules file is nothing the v0.9.4 section engine recognises, so it also proves that such a file keeps every word of itself and still gains the never-delete and shell rules. |
| `refused` | When git refuses the closing commit, the diary, the screen and the step state all say so, the closing step is not marked done, and the work is staged rather than lost. |
| `extras` | `scripts/orient-extras.sh` is created, the preflight runs it, and a second update leaves the owner's own edits to it exactly as they were. |
| `index` | An Index that already keeps a Wiki Operations line does not gain a second one. |
| `protected` | A wiki inside the owner's Desktop is told that macOS blocks scheduled jobs there, that they may never have run, and that nothing has been moved. |
| `twice` | Running the same update twice makes no second commit and leaves nothing staged. |
| `shrink` | An ordinary v0.9.3 wiki whose rules file is untouched Moblee wording comes out under 4,600 tokens, with the four reference pages in place, the sections that moved named on screen, and one Wiki Operations line in the Index. |
| `owners_words` | A v0.9.3 wiki whose owner has written in their rules file in three places keeps all three, word for word; the two sections they wrote in are reported as left alone; the ones they never touched are still brought up to date; and the file as it was before the run is kept. |
| `gitignore` | A wiki that already has a `.gitignore`, which is every wiki installed before v0.9.4, gains the missing lines at the end of it: the owner's own lines stay where they are, the app's queue file is ignored, the weekly card is let into git, the screen says what was added, and a second update adds nothing a second time. |
| `name_clash` | An owner who already keeps a page called `Readwise` of their own is told so, in plain words, with the path of the page and what to do about it. Moblee's `Readwise` page is not added, the Index is not pointed at the owner's page, and the rules file is left exactly as it is, so nothing that would have moved to that page is dropped. Renaming the owner's page and running the updater again finishes the job. |

Two of the cases run against a second fixture, `fixtures/old-wiki-0.9.3/`, whose
`CLAUDE.md` is the real v0.9.3 template, word for word as it shipped. It has to
stay that way: the section engine only replaces a section whose body matches
something Moblee shipped, so a single edited character in that file would turn
the two cases above into tests of nothing. The owner's own words are added on
top of it at run time by `fixtures/add-owner-words.py`, which prints the three
lines it wrote so the case can look for exactly those words afterwards.

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

It refuses for a second reason while a release is being prepared. The guard
skips a pack script whose SHA-256 is in its own list, and the list in the
*installed* guard (`~/.claude/hooks/bash-guard.py`) is whatever the last install
or repair put there. The moment `scripts/update.sh` is edited, that hash stops
matching, the guard falls back to reading the file, and it stops on the line
that writes a `VERSION` into the wiki. Refreshing the list in the pack
(`python3 safety/release-hashes.py`) does not change the installed copy. So the
rig cannot be run by an assistant on a machine whose guard predates the edit,
and the maintainer runs it himself.

## Related

`python3 scripts/test-patch-claude-md.py` tests the section engine directly,
case by case, and needs no updater and no guard. `shrink` and `owners_words`
prove the same behaviour through the real thing; that suite proves the corners.
The digests the engine judges a section by are generated by
`python3 tools/claude-md-corpus/build-corpus.py`, which must be run again after
any change to `vault-template/CLAUDE.md`.
