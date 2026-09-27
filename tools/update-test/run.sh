#!/usr/bin/env bash
# run.sh — run the real updater end to end against throwaway wikis and check
# what it actually did.
#
#   bash tools/update-test/run.sh            # every case
#   bash tools/update-test/run.sh refused    # one case by name
#
# Why this exists. Until 23 September 2026 the pack had no way to run
# scripts/update.sh from start to finish outside a real person's Mac, so every
# change to it was tested a piece at a time and shipped on reasoning. The faults
# fixed in v0.9.1 were all found by an owner after release, on their own wiki,
# which is the most expensive place to find them. A release that touches the
# updater runs this first.
#
# SAFETY. The updater writes to the HOME it is given: ~/.claude/skills,
# ~/.config/moblee, ~/.codex. On a machine where ~/.claude/skills is a symlink
# into a live vault, running it with a real HOME would overwrite real skills.
# Every case here therefore runs with HOME set to a throwaway directory under
# TMPDIR, and the script refuses to start if that is not so. Nothing outside
# that directory is written or removed.
#
# The wikis under test are built by copying fixtures/old-wiki, so the shapes
# being tested can be read as files rather than dug out of this script.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE_ROOT="$(cd "$HERE/../.." && pwd)"
FIXTURES="$HERE/fixtures"
WANT="${1:-all}"
ROOT="${TMPDIR:-/tmp}/moblee-update-test-$(date '+%Y%m%d-%H%M%S')"
PASS=0; FAIL=0; FAILED=()
CASE="(none)"

red()   { printf '\033[31m%s\033[0m\n' "$*"; }
green() { printf '\033[32m%s\033[0m\n' "$*"; }
ok()    { PASS=$((PASS+1)); printf '    ok    %s\n' "$*"; }
bad()   { FAIL=$((FAIL+1)); FAILED+=("$CASE: $*"); red "    FAIL  $*"; }

has()     { if grep -qF -- "$2" "$1" 2>/dev/null; then ok "$3"; else bad "$3 — not in $(basename "$1"): $2"; fi; }
hasnt()   { if grep -qF -- "$2" "$1" 2>/dev/null; then bad "$3 — unexpectedly present: $2"; else ok "$3"; fi; }
isfile()  { if [[ -f "$1" ]]; then ok "$2"; else bad "$2 — missing: $1"; fi; }
same()    { if [[ "$1" == "$2" ]]; then ok "$3"; else bad "$3 — expected [$2], got [$1]"; fi; }

# make_wiki <home> <sandbox> [fixture] — a wiki as it stands before an update.
# The fixture defaults to old-wiki, a stub of a rules file that says little. Pass
# old-wiki-0.9.3 for a wiki whose CLAUDE.md is the real v0.9.3 template, word for
# word as it shipped: the section engine added in v0.9.4 only touches a section
# whose body matches something Moblee shipped, so a stub proves nothing about it.
make_wiki() {
  local home="$1" sbx="$2" fixture="${3:-old-wiki}"
  mkdir -p "$sbx" "$home/.config/moblee"
  cp -R "$FIXTURES/$fixture/." "$sbx/"
  mkdir -p "$sbx/raw" "$sbx/wiki/Wiki Operations"
  ( cd "$sbx" && git init -q && git config user.email t@example.com && git config user.name Test \
      && git add -A && git commit -qm "the owner's wiki before the update" ) >/dev/null 2>&1
  printf '%s\n' "$sbx" | tee "$home/.config/moblee/vault-path" >/dev/null
}

# run_update <home> <sandbox> [args...] — runs the updater and sets RC.
#
# stdin comes from /dev/null, and that is not a detail. The updater asks three
# questions (the weekly health check, the learning path, the checklist) and is
# written to take its default when input ends. Left attached to a terminal it
# waits for an answer for ever, and because output was redirected the question
# was invisible: the run simply appeared to hang after printing the case name.
# That is what the first run of this rig did on 23 September 2026.
#
# It sets a variable rather than echoing the exit code, and that is deliberate.
# Called as rc=$(run_update …) the command substitution waits for every writer
# to the pipe to finish, and the background timeout below is one of them: the
# rig then sat silent for the whole timeout after the updater had already
# finished, which looked exactly like the hang it was meant to catch. Setting a
# variable keeps it out of a subshell entirely. (Found on 23 September 2026,
# twice in one afternoon, by the owner watching a cursor not blink.)
#
# The updater's own progress is shown as it happens as well as captured, so a
# real hang is obvious: the last line printed says which step it stopped on.
UPDATE_TIMEOUT="${UPDATE_TIMEOUT:-240}"
RC=0
run_update() {
  local home="$1" sbx="$2"; shift 2
  ( cd "$PACKAGE_ROOT" && HOME="$home" bash scripts/update.sh "$sbx" "$@" ) \
    < /dev/null 2>&1 | tee "$home/update-output.txt" | sed 's/^/      | /' &
  local pid=$!
  # The killer must not hold the pipeline open, hence its own redirection, and
  # it is disowned so that the shell does not print "Terminated: 15" every time
  # the timeout is cancelled, which it is on every ordinary run.
  ( sleep "$UPDATE_TIMEOUT"; kill -9 "$pid" 2>/dev/null ) >/dev/null 2>&1 &
  local killer=$!
  disown "$killer" 2>/dev/null
  wait "$pid"; RC=$?
  kill "$killer" >/dev/null 2>&1
  if [[ $RC -ge 128 ]]; then
    bad "the updater did not finish within ${UPDATE_TIMEOUT}s and was stopped"
  fi
}

start() {
  CASE="$1"
  HOME_DIR="$ROOT/$CASE/home"; SBX="$ROOT/$CASE/wiki"
  mkdir -p "$HOME_DIR" "$SBX"
  printf '\n  %s\n' "$CASE"
}

wanted() { [[ "$WANT" == "all" || "$WANT" == "$1" ]]; }

[[ "$ROOT" == "${TMPDIR:-/tmp}"* ]] || { red "refusing: scratch dir is not under TMPDIR"; exit 2; }

# --------------------------------------------------------------------------
# An ordinary update: it runs, it commits, it says so, and it leaves the
# owner's own content alone.
case_happy() {
  start happy
  make_wiki "$HOME_DIR" "$SBX"
  run_update "$HOME_DIR" "$SBX"; local rc=$RC
  same "$rc" "0" "the updater exits cleanly"
  same "$(cat "$SBX/VERSION")" "$(cat "$PACKAGE_ROOT/VERSION")" "the wiki is on the new version"
  has   "$HOME_DIR/.config/moblee/install-diary.txt" "=== Moblee update finished ===" "the diary records a finish"
  hasnt "$HOME_DIR/.config/moblee/install-diary.txt" "NOT COMMITTED" "and does not report a refused commit"
  ( cd "$SBX" && git log -1 --format=%s ) | tee "$HOME_DIR/last-subject.txt" >/dev/null
  has   "$HOME_DIR/last-subject.txt" "moblee: updated" "the update committed itself"
  same  "$(cd "$SBX" && git status --porcelain | wc -l | tr -d ' ')" "0" "nothing is left staged"
  has   "$SBX/wiki/log.md" "the owner wrote this" "the owner's own content is untouched"
  has   "$SBX/wiki/Golf.md" "A page of the owner's own" "and so are his own pages"
  # (v0.9.4) This fixture's rules file is nothing the v0.9.4 engine recognises,
  # so the engine rewrites none of it and removes none of it. The rules that
  # stop harm must still reach it: they only ever ADD, and a file Moblee cannot
  # read is the last one that should be left without the never-delete rule.
  has   "$SBX/CLAUDE.md" "A placeholder the updater's own patcher replaces." \
        "a rules file Moblee does not recognise keeps every word of itself"
  has   "$SBX/CLAUDE.md" "never deletes, empties or discards" "and still gains the never-delete rule"
  has   "$SBX/CLAUDE.md" "Shell commands are composed plainly" "and the shell rule"
}

# --------------------------------------------------------------------------
# The v0.9.1 fault: git refuses the closing commit, and every place that
# reports on the update must say so rather than claim a finish.
case_refused() {
  start refused
  make_wiki "$HOME_DIR" "$SBX"
  # Trip the pack's OWN commit gate, by giving the wiki a rules file past its
  # size cap — which is exactly what happened to a real owner. An earlier
  # version of this case installed a pre-commit hook of its own; the updater
  # moved it aside, as it is written to do so that only one gate runs, and the
  # case passed while testing nothing. Found by running the rig, 23 September.
  python3 "$FIXTURES/make-oversized-claude-md.py" "$SBX/CLAUDE.md" >/dev/null
  ( cd "$SBX" && git add -A && git commit -qm "the owner's rules file grows past the cap" ) >/dev/null 2>&1
  run_update "$HOME_DIR" "$SBX"
  local diary="$HOME_DIR/.config/moblee/install-diary.txt"
  has   "$diary" "NOT COMMITTED" "the diary says the update is not committed"
  has   "$diary" "REFUSED" "and names the refusal on the closing step"
  hasnt "$diary" "finish: done" "and does not also mark that step done"
  has   "$HOME_DIR/update-output.txt" "closing commit was refused" "the screen says so too"
  local staged; staged=$(cd "$SBX" && git diff --cached --name-only | wc -l | tr -d ' ')
  if [[ "$staged" -gt 0 ]]; then ok "the work is staged, not lost ($staged files)"; else bad "nothing staged"; fi
}

# --------------------------------------------------------------------------
# The owner's own orientation checks must survive an update untouched.
case_extras() {
  start extras
  make_wiki "$HOME_DIR" "$SBX"
  run_update "$HOME_DIR" "$SBX"
  isfile "$SBX/scripts/orient-extras.sh" "the owner's extras file is created"
  has "$SBX/scripts/vault-orient-preflight.sh" "orient-extras.sh" "the preflight knows to run it"
  # (v0.9.1) The run that lays the stub down commits it, so it is in git from
  # the start and does not sit untracked in every `git status` the owner runs.
  ( cd "$SBX" && git ls-files -- scripts/orient-extras.sh ) > "$HOME_DIR/tracked.txt" 2>/dev/null
  has "$HOME_DIR/tracked.txt" "scripts/orient-extras.sh" "and the run that laid it down put it in git"
  # From here it is the owner's. What he writes in it must never be carried into
  # a commit that says "moblee: updated from X to Y", which is what the closing
  # commit's `git add -A -- scripts` used to do.
  cp "$FIXTURES/owners-own-check.sh" "$SBX/scripts/orient-extras.sh"
  cp "$FIXTURES/old-wiki/VERSION" "$SBX/VERSION"
  # the VERSION is committed and the owner's check is NOT: the second update has
  # real work to do, and his edit is uncommitted when it runs, which is the case
  # the sweep used to take
  ( cd "$SBX" && git add -- VERSION && git commit -qm "back to the old version" ) >/dev/null 2>&1
  run_update "$HOME_DIR" "$SBX"
  has "$SBX/scripts/orient-extras.sh" "the owner wrote this check himself" \
      "and a second update leaves it exactly as he left it"
  ( cd "$SBX" && git log -1 --format=%s ) > "$HOME_DIR/last-subject.txt" 2>/dev/null
  has  "$HOME_DIR/last-subject.txt" "moblee: updated" "the second update did make a commit of its own"
  ( cd "$SBX" && git log -1 --name-only --format= ) > "$HOME_DIR/committed-files.txt" 2>/dev/null
  hasnt "$HOME_DIR/committed-files.txt" "scripts/orient-extras.sh" "and his check is not in it"
  ( cd "$SBX" && git status --porcelain -- scripts/orient-extras.sh ) > "$HOME_DIR/his-to-commit.txt" 2>/dev/null
  has "$HOME_DIR/his-to-commit.txt" "scripts/orient-extras.sh" "which is still his to commit"
}

# --------------------------------------------------------------------------
# The four pages the assistant is told to write to are staged by the closing
# commit, so an owner's half-finished work on one of them was going into a
# commit message that names Moblee. The rules file and the Index already had
# this care; these did not.
case_owners_pages() {
  start owners_pages
  make_wiki "$HOME_DIR" "$SBX"
  run_update "$HOME_DIR" "$SBX"           # the first update lays Identity.md down and commits it
  isfile "$SBX/wiki/Identity.md" "the first update adds Identity.md"
  # The VERSION goes back and is COMMITTED, so the second update has real work
  # and makes a commit of its own. Without that it finds nothing to change, makes
  # no commit, and an assertion reading `git log -1` is answered by the FIRST
  # update's commit, which legitimately contains Identity.md: the case then fails
  # while the behaviour under test is correct. (Found by running it, 23 September.)
  cp "$FIXTURES/old-wiki/VERSION" "$SBX/VERSION"
  ( cd "$SBX" && git add -- VERSION && git commit -qm "back to the old version" ) >/dev/null 2>&1
  printf '\n\nThe owner was in the middle of writing this.\n' >> "$SBX/wiki/Identity.md"
  run_update "$HOME_DIR" "$SBX"
  ( cd "$SBX" && git log -1 --format=%s ) > "$HOME_DIR/last-subject.txt" 2>/dev/null
  has "$HOME_DIR/last-subject.txt" "moblee: updated" "the second update makes a commit of its own"
  ( cd "$SBX" && git log -1 --name-only --format= ) > "$HOME_DIR/committed-files.txt" 2>/dev/null
  hasnt "$HOME_DIR/committed-files.txt" "wiki/Identity.md" "a page the owner had half-written is not in it"
  has "$SBX/wiki/Identity.md" "The owner was in the middle of writing this" "and their words are still in the file"
  ( cd "$SBX" && git diff --name-only -- wiki/Identity.md ) > "$HOME_DIR/still-dirty.txt" 2>/dev/null
  has "$HOME_DIR/still-dirty.txt" "wiki/Identity.md" "and still theirs to commit"
}

# --------------------------------------------------------------------------
# A step whose work failed used to close saying "done": `ustep` closes the step
# before it whatever happened, and the work inside is written `|| true` so that
# one part failing never stops an otherwise sound update. The screen said so and
# the diary did not, so the check-up — which reads the diary — reported a clean
# update over a step that had not done its job.
#
# The failure is made real rather than simulated: python3 is put out of reach for
# the run, so the three scripts the `pages` step calls cannot start. The wiki is
# not harmed by that, which is exactly the shape the swallowing was written for.
case_partly() {
  start partly
  make_wiki "$HOME_DIR" "$SBX"
  # The learning path is already in this wiki, which is the branch most owners
  # take: the update refreshes it rather than offering it. Then the folder those
  # two steps write into is made read-only, which fails add-habits-page.py in
  # step 6 and install-learning-path.py in step 8 and nothing else. Both are
  # written `|| true` or `|| echo` so that one part failing never stops an
  # otherwise sound update, which is right, and is why their failure has to be
  # carried to the end instead of being swallowed.
  #
  # The first version of this case put python3 out of reach for the run. That
  # killed the safety step, which correctly stops the update at step 4, so the
  # instrumented steps never ran at all and four checks failed over code that
  # was working. The failure has to be narrow or it tests nothing.
  cp "$FIXTURES/old-wiki/VERSION" "$SBX/wiki/Wiki Operations/Moblee Learning Path.md"
  chmod 500 "$SBX/wiki/Wiki Operations"
  run_update "$HOME_DIR" "$SBX" --progress
  chmod 700 "$SBX/wiki/Wiki Operations"
  local diary="$HOME_DIR/.config/moblee/install-diary.txt"
  has  "$diary" "DID NOT FINISH" "the diary names what did not finish"
  has  "$diary" "done, except" "and the step says it finished all but that"
  has  "$HOME_DIR/update-output.txt" "did not finish" "the screen says so at the end"
  has  "$HOME_DIR/update-output.txt" '"state":"partial"' "and the app is told, so it can say so too"
  has  "$HOME_DIR/update-output.txt" "Habits and Tools page" "and names which thing it was"
  # The note belongs to the step it happened in and must not spread to the next.
  # The learning-path step runs three steps later and finishes properly here: it
  # leaves an existing lessons page alone and writes only outside the folder this
  # case made read-only, so there is nothing for it to fail at. That is the code
  # being right, and an assertion that expected it to fail was the test being
  # wrong (23 September 2026, the second time this case was written).
  has  "$HOME_DIR/update-output.txt" '"step":"pages","state":"partial"' "the note lands on the step it happened in"
  has  "$HOME_DIR/update-output.txt" '"step":"lessons","state":"ok"' "and a later step that finished properly still closes clean"
  hasnt "$diary" "=== Moblee update finished, BUT" "the update itself still finished"
}

# --------------------------------------------------------------------------
# The closing banner names one folder as where everything replaced was kept.
# Three of the scripts the updater runs were each minting a folder of their own,
# a second or two apart, so an owner who went looking for their previous rules
# file opened the folder they were told about and found it empty or absent.
case_backups() {
  start backups
  make_wiki "$HOME_DIR" "$SBX"
  run_update "$HOME_DIR" "$SBX"
  local named; named=$(grep -A 1 "Everything it replaced was kept at" "$HOME_DIR/update-output.txt" | tail -1 | tr -d ' ')
  if [[ -z "$named" ]]; then
    # a run that replaced nothing names no folder, which is the other half of it
    hasnt "$HOME_DIR/update-output.txt" "Everything it replaced was kept at" \
          "a run that replaced nothing names no backup folder"
  else
    if [[ -d "$named" ]]; then ok "the folder the banner names exists"; else bad "the folder the banner names exists — $named"; fi
    if [[ -n "$(ls -A "$named" 2>/dev/null)" ]]; then ok "and has what was replaced in it"; else bad "and has what was replaced in it"; fi
    # everything one run replaced in one folder, not three a second apart
    same "$(ls -d "$HOME_DIR/.config/moblee/backups"/*/ 2>/dev/null | wc -l | tr -d ' ')" "1" \
         "and it is the only backup folder the run made"
  fi
}

# --------------------------------------------------------------------------
# An Index that already keeps a Wiki Operations line must not gain a second.
case_index() {
  start index
  make_wiki "$HOME_DIR" "$SBX"
  run_update "$HOME_DIR" "$SBX"
  same "$(grep -c '^- Wiki Operations' "$SBX/wiki/Index.md" 2>/dev/null | tr -d ' ')" "1" \
       "the Index keeps exactly one Wiki Operations line"
}

# --------------------------------------------------------------------------
# A wiki already inside a folder macOS protects. The installer warns while the
# location can still be typed again; an owner already there runs the UPDATER and
# would never see that warning, which is the owner the warning was written for.
case_protected() {
  start protected
  # The wiki goes inside the sandbox HOME's own Desktop, so $VAULT really is
  # under $HOME/Desktop from the updater's point of view.
  SBX="$HOME_DIR/Desktop/wiki"
  make_wiki "$HOME_DIR" "$SBX"
  run_update "$HOME_DIR" "$SBX"
  has "$HOME_DIR/update-output.txt" "inside your Desktop folder" "the update tells the owner about the folder"
  has "$HOME_DIR/update-output.txt" "may never have run" "and says the schedules may never have run"
  has "$HOME_DIR/update-output.txt" "Nothing here has moved it" "and makes clear nothing was moved"
  has "$HOME_DIR/.config/moblee/install-diary.txt" "macOS blocks scheduled jobs" "and the diary records it"
  isfile "$SBX/VERSION" "the wiki is still where the owner put it"
}

# --------------------------------------------------------------------------
# Running the same update twice must change nothing the second time.
case_twice() {
  start twice
  make_wiki "$HOME_DIR" "$SBX"
  run_update "$HOME_DIR" "$SBX"
  local first; first=$(cd "$SBX" && git rev-parse HEAD)
  run_update "$HOME_DIR" "$SBX"
  same "$(cd "$SBX" && git rev-parse HEAD)" "$first" "a second run makes no new commit"
  same "$(cd "$SBX" && git status --porcelain | wc -l | tr -d ' ')" "0" "and leaves nothing staged"
}

# --------------------------------------------------------------------------
# (v0.9.4) The rules file shrinks. CLAUDE.md went from about 9,000 tokens to
# about 3,700, because the assistant reads it at the start of every session, and
# eleven of its sections moved to four pages it reads only when it needs them.
# An owner whose file is untouched Moblee wording must actually GET that, or the
# safety rule below could pass by never replacing anything at all.
case_shrink() {
  start shrink
  make_wiki "$HOME_DIR" "$SBX" old-wiki-0.9.3
  local before; before=$(( $(wc -c < "$SBX/CLAUDE.md") / 4 ))
  run_update "$HOME_DIR" "$SBX"; local rc=$RC
  same "$rc" "0" "the updater exits cleanly"
  local after; after=$(( $(wc -c < "$SBX/CLAUDE.md") / 4 ))
  if [[ "$after" -lt 4600 ]]; then ok "the rules file is under 4,600 tokens (was $before, now $after)";
  else bad "the rules file is under 4,600 tokens — was $before, now $after"; fi
  # the four pages the content moved to
  for p in "Wiki Conventions" "Git and Commits" "Tools and Connections" "Readwise"; do
    isfile "$SBX/wiki/Wiki Operations/$p.md" "the $p page arrived"
  done
  has  "$SBX/CLAUDE.md" "[[Wiki Conventions]]" "and the rules file points at them"
  hasnt "$SBX/CLAUDE.md" "## Readwise conventions" "a section that moved is out of the rules file"
  hasnt "$SBX/CLAUDE.md" "## Compaction discipline" "and so is another"
  has  "$SBX/CLAUDE.md" "## Plain words" "the new section is in"
  has  "$SBX/CLAUDE.md" "## Three layers" "a renamed section carries its new name"
  hasnt "$SBX/CLAUDE.md" "## Three-layer architecture" "and not its old one"
  has  "$HOME_DIR/update-output.txt" "is now on wiki/Wiki Operations/Readwise.md" \
       "the run says in plain words where each moved section went"
  same "$(grep -c '^- Wiki Operations' "$SBX/wiki/Index.md" 2>/dev/null | tr -d ' ')" "1" \
       "the Index still keeps exactly one Wiki Operations line"
  same "$(cd "$SBX" && git status --porcelain | wc -l | tr -d ' ')" "0" "nothing is left staged"
}

# --------------------------------------------------------------------------
# (v0.9.4) The hard one. An owner's rules file carries their own words as well
# as Moblee's, and the section engine may only replace what Moblee wrote. This
# wiki has the real v0.9.3 template with the owner's words in three places: a
# bullet inside one Moblee section, a paragraph at the end of another, and a
# whole section of their own. Every one of those must still be there, word for
# word, afterwards; the two sections they wrote in must be reported as left
# alone; and the sections they never touched must still have been brought up to
# date, or the safety rule would be passing by doing nothing.
case_owners_words() {
  start owners_words
  make_wiki "$HOME_DIR" "$SBX" old-wiki-0.9.3
  python3 "$FIXTURES/add-owner-words.py" "$SBX/CLAUDE.md" > "$HOME_DIR/owner-words.txt"
  ( cd "$SBX" && git add -A && git commit -qm "the owner writes in their own rules file" ) >/dev/null 2>&1
  run_update "$HOME_DIR" "$SBX"; local rc=$RC
  same "$rc" "0" "the updater exits cleanly"

  # 1, 2 and 3: every line the owner wrote is still in the file, word for word
  local n=0
  while IFS= read -r line; do
    n=$((n+1))
    has "$SBX/CLAUDE.md" "$line" "the owner's own words survive, line $n of 3"
  done < "$HOME_DIR/owner-words.txt"
  same "$n" "3" "all three of the owner's additions were put in by the fixture"
  has "$SBX/CLAUDE.md" "## How the owner files receipts" "the owner's own section is still there"

  # the two sections they wrote in are left whole, and named as left alone
  has "$SBX/CLAUDE.md" "Identity disambiguation in source notes" \
      "the section they wrote in keeps the rest of what it said"
  has "$HOME_DIR/update-output.txt" "because you have written in it" \
      "the run says some sections were left alone"
  has "$HOME_DIR/update-output.txt" "Hard rules" "and names Hard rules as one of them"
  has "$HOME_DIR/update-output.txt" "House style" "and House style as the other"

  # the sections they never touched were still brought up to date
  has  "$SBX/CLAUDE.md" "## Plain words" "a section they never touched was added"
  has  "$SBX/CLAUDE.md" "## Three layers" "and a renamed one was renamed"
  hasnt "$SBX/CLAUDE.md" "## Readwise conventions" "and a moved one moved"
  isfile "$SBX/wiki/Wiki Operations/Wiki Conventions.md" "the pages it moved to arrived"
  isfile "$SBX/wiki/Wiki Operations/Readwise.md" "all four of them"

  # nothing of the owner's own, anywhere in the wiki, was lost
  has "$SBX/wiki/log.md" "the owner wrote this" "the owner's log is untouched"
  has "$SBX/wiki/Golf.md" "A page of the owner's own" "and so are their pages"
  # the file they had before the run is kept, so any of this can be undone
  local kept; kept=$(grep -A 1 "Everything it replaced was kept at" "$HOME_DIR/update-output.txt" | tail -1 | tr -d ' ')
  isfile "$kept/CLAUDE.md" "the rules file as it was before the run is kept"
  has "$kept/CLAUDE.md" "## Readwise conventions" "with everything that left it still in it"
}

# --------------------------------------------------------------------------
# (v0.9.4) The .gitignore of a wiki that already has one. Until now the updater
# copied the template only where there was no .gitignore at all, so every wiki
# installed before v0.9.4 — which is all of them — got none of the lines added
# to it, including the two fixes billed as "a wiki with nothing left unsaved".
# The file is the owner's, so lines are only ever ADDED to the end of it: this
# case checks that what they had is still there, in the order they had it, that
# the queue file is now ignored, and that the weekly card is now in git.
case_gitignore() {
  start gitignore
  make_wiki "$HOME_DIR" "$SBX"
  # the .gitignore a wiki installed before v0.9.4 has, plus a line of the
  # owner's own in the middle of it, to prove nothing is reordered
  printf '%s\n' '# Moblee vault: what git does not need to keep.' 'outputs/' \
    '.obsidian/workspace.json' 'my-own-notes.txt' '__pycache__/' '.DS_Store' \
    > "$SBX/.gitignore"
  mkdir -p "$SBX/outputs/weekly" "$SBX/outputs/lint" "$SBX/.moblee"
  printf '# This week\n' > "$SBX/outputs/weekly/2026-09-26.md"
  printf '# Lint\n'      > "$SBX/outputs/lint/lint-v2-2026-09-26.md"
  printf '[]\n'          > "$SBX/.moblee/requests.json"
  ( cd "$SBX" && git add -A && git commit -qm "the owner's .gitignore" ) >/dev/null 2>&1
  run_update "$HOME_DIR" "$SBX"; local rc=$RC
  same "$rc" "0" "the updater exits cleanly"
  has "$SBX/.gitignore" "my-own-notes.txt" "the owner's own line is still in the file"
  same "$(head -2 "$SBX/.gitignore" | tail -1)" "outputs/" \
       "and their lines are in the order they left them"
  has "$SBX/.gitignore" ".moblee/requests.json" "the queue file is now ignored"
  has "$SBX/.gitignore" "!outputs/weekly/" "and the weekly card is let through"
  has "$HOME_DIR/update-output.txt" "added to your .gitignore" "the screen says what it added"
  has "$HOME_DIR/update-output.txt" "nothing in it was changed or moved" "and that nothing was taken out"
  # what git actually does with it, which is the only thing that matters
  ( cd "$SBX" && git check-ignore -q -- outputs/weekly/2026-09-26.md ) \
    && bad "the weekly card is still ignored by git" || ok "git now keeps the weekly card"
  ( cd "$SBX" && git check-ignore -q -- outputs/lint/lint-v2-2026-09-26.md ) \
    && ok "and still ignores the lint reports" || bad "the lint reports are no longer ignored"
  ( cd "$SBX" && git check-ignore -q -- .moblee/requests.json ) \
    && ok "and still ignores the app's queue file" || bad "the app's queue file is not ignored"
  # (v0.9.6) the queue file stops being tracked without ever being moved, and
  # what was in it is still in it
  same "$(cat "$SBX/.moblee/requests.json")" "[]" "the queue file itself is untouched"
  same "$(cd "$SBX" && git ls-files -- .moblee/requests.json | wc -l | tr -d ' ')" "0" "and git no longer keeps it"
  same "$(ls -a "$SBX/.moblee" | grep -c 'requests.json.moblee')" "0" "and nothing was left moved aside"
  ( cd "$SBX" && git log --format=%s ) > "$HOME_DIR/subjects.txt"
  has "$HOME_DIR/subjects.txt" "queue file is no longer kept in git" "in a commit of its own"
  # running it again must add nothing a second time
  local sum; sum=$(cksum < "$SBX/.gitignore")
  run_update "$HOME_DIR" "$SBX"
  same "$(cksum < "$SBX/.gitignore")" "$sum" "a second update adds nothing a second time"
}

# --------------------------------------------------------------------------
# (v0.9.4) The owner already keeps a page called Readwise of their own, which is
# the likely clash: the pack assumes a Readwise feed, so an owner may well have
# written their own notes about it. Matching by filename alone, the updater took
# that page as Moblee's, never wrote Moblee's, said it had added four pages when
# it had added three, and pointed [[Readwise]] at the owner's unrelated page.
# The rules file must be left alone in that case, and the clash named.
case_name_clash() {
  start name_clash
  make_wiki "$HOME_DIR" "$SBX" old-wiki-0.9.3
  printf '# Readwise\n\nThe owner keeps his own notes about the Readwise app here.\n' \
    > "$SBX/wiki/Readwise.md"
  ( cd "$SBX" && git add -A && git commit -qm "the owner's own Readwise page" ) >/dev/null 2>&1
  run_update "$HOME_DIR" "$SBX"
  has "$HOME_DIR/update-output.txt" "already has a page called Readwise" "the run names the clash"
  has "$HOME_DIR/update-output.txt" "wiki/Readwise.md" "and says exactly where the other page is"
  has "$HOME_DIR/update-output.txt" "Rename one of the two" "and what to do about it"
  hasnt "$HOME_DIR/update-output.txt" "the four pages were added" "and claims nothing it did not do"
  has "$SBX/wiki/Readwise.md" "his own notes about the Readwise app" "the owner's page is untouched"
  hasnt "$SBX/wiki/Index.md" "[[Readwise]]" "the Index is not pointed at it"
  # the rules file keeps everything, because a section may only be dropped once
  # the page carrying it is really there
  has "$SBX/CLAUDE.md" "## Readwise conventions" "the rules file keeps the section that would have moved"
  has "$SBX/CLAUDE.md" "## Compaction discipline" "and every other one with it"
  has "$HOME_DIR/update-output.txt" "was left exactly as it is" "and the run says the rules file was left alone"
  # and the clash is fixable: rename the owner's page and run it again
  ( cd "$SBX" && git mv wiki/Readwise.md "wiki/My Readwise Notes.md" ) >/dev/null 2>&1
  printf '# My Readwise Notes\n\nThe owner keeps his own notes about the Readwise app here.\n' \
    > "$SBX/wiki/My Readwise Notes.md"
  ( cd "$SBX" && git add -A && git commit -qm "the owner renames his page" ) >/dev/null 2>&1
  cp "$FIXTURES/old-wiki/VERSION" "$SBX/VERSION"
  ( cd "$SBX" && git add -- VERSION && git commit -qm "back to the old version" ) >/dev/null 2>&1
  run_update "$HOME_DIR" "$SBX"
  isfile "$SBX/wiki/Wiki Operations/Readwise.md" "once renamed, Moblee's page arrives"
  hasnt "$SBX/CLAUDE.md" "## Readwise conventions" "and the section moves out of the rules file"
}


# --------------------------------------------------------------------------
# (v0.9.6) The owner's own uncommitted work, anywhere the closing commit looks.
# Until v0.9.6 only eight wiki pages had this care; an unfinished edit to the
# rules file, a script of the owner's own and a line added to .gitignore were
# all committed under "moblee: updated from X to Y" (found by the unanchored
# review of 27 September 2026, by running it on a vault path with a space and
# Arabic in it, which this case uses too).
case_owners_uncommitted() {
  start owners_uncommitted
  SBX="$ROOT/owners_uncommitted/ويكي My Wiki"
  make_wiki "$HOME_DIR" "$SBX" old-wiki-0.9.3
  printf '\nMy own rule, not yet saved.\n' >> "$SBX/CLAUDE.md"
  mkdir -p "$SBX/scripts"
  printf 'print("mine")\n' > "$SBX/scripts/mine.py"
  printf 'my-unsaved-line\n' >> "$SBX/.gitignore"
  run_update "$HOME_DIR" "$SBX"; local rc=$RC
  same "$rc" "0" "the updater exits cleanly on a path with a space and Arabic in it"
  ( cd "$SBX" && git log -1 --format=%s ) > "$HOME_DIR/last-subject.txt"
  has "$HOME_DIR/last-subject.txt" "moblee: updated" "the update still committed its own work"
  ( cd "$SBX" && git show --name-only --format= HEAD ) > "$HOME_DIR/committed.txt"
  hasnt "$HOME_DIR/committed.txt" "scripts/mine.py" "the owner's own script is not in Moblee's commit"
  hasnt "$HOME_DIR/committed.txt" "CLAUDE.md" "nor their half-finished rules file"
  hasnt "$HOME_DIR/committed.txt" ".gitignore" "nor their unsaved .gitignore"
  has "$SBX/CLAUDE.md" "My own rule, not yet saved." "their words are still in the rules file"
  has "$SBX/.gitignore" "my-unsaved-line" "and their line in .gitignore"
  ( cd "$SBX" && git status --porcelain --untracked-files=all ) > "$HOME_DIR/status.txt"
  has "$HOME_DIR/status.txt" "scripts/mine.py" "the script is still theirs to commit"
  has "$HOME_DIR/status.txt" "CLAUDE.md" "and so is the rules file"
  has "$HOME_DIR/update-output.txt" "held changes of yours that were not yet committed" "and the screen tells them so"
}

# --------------------------------------------------------------------------
# (v0.9.6) What a refused commit leaves staged is Moblee's, not the owner's, and
# the next run commits it. Staged-only changes are therefore never counted as
# the owner's uncommitted work.
case_staged_leftovers() {
  start staged_leftovers
  make_wiki "$HOME_DIR" "$SBX"
  printf '\nStaged by an earlier update whose commit was refused.\n' >> "$SBX/CLAUDE.md"
  ( cd "$SBX" && git add -- CLAUDE.md ) >/dev/null 2>&1
  run_update "$HOME_DIR" "$SBX"
  ( cd "$SBX" && git show --name-only --format= HEAD ) > "$HOME_DIR/committed.txt"
  has "$HOME_DIR/committed.txt" "CLAUDE.md" "a rules file left staged by a refused update is committed this time"
  hasnt "$HOME_DIR/update-output.txt" "CLAUDE.md held changes of yours" "and is not called the owner's"
}

# --------------------------------------------------------------------------
# (v0.9.6) A clash over the Readwise page leaves the rules file's sections
# alone, and the rules that only add still go in. With a rules file that lacks
# them, v0.9.4 to v0.9.5 left the wiki without the never-delete rule until the
# owner renamed their page.
case_clash_keeps_safety() {
  start clash_keeps_safety
  make_wiki "$HOME_DIR" "$SBX"
  printf '# Readwise\n\nNotes of the owner'"'"'s own about the app.\n' > "$SBX/wiki/Readwise.md"
  ( cd "$SBX" && git add -A && git commit -qm "the owner's own Readwise page" ) >/dev/null 2>&1
  run_update "$HOME_DIR" "$SBX"
  has "$HOME_DIR/update-output.txt" "already has a page called Readwise" "the clash is named"
  has "$SBX/CLAUDE.md" "never deletes, empties or discards" "and the never-delete rule still goes in"
  has "$SBX/CLAUDE.md" "Shell commands are composed plainly" "with the shell rule"
  has "$SBX/CLAUDE.md" "A placeholder the updater's own patcher replaces." "and every word of theirs kept"
}

# --------------------------------------------------------------------------
# (v0.9.6) The same wiki on a second Mac, a new Mac, or after ~/.claude is
# reset. The record of starting notes travels with the wiki; the memory folder
# does not. v0.9.4 to v0.9.5 read the empty folder as the owner having taken
# every note out, said so, and never gave them on the second Mac.
case_second_mac() {
  start second_mac
  make_wiki "$HOME_DIR" "$SBX"
  run_update "$HOME_DIR" "$SBX"
  local first; first=$(find "$HOME_DIR/.claude/projects" -path "*/memory/*.md" 2>/dev/null | wc -l | tr -d ' ')
  if [[ "$first" -gt 1 ]]; then ok "the first Mac is given its starting notes ($first files)"; else bad "the first Mac got no starting notes"; fi
  local home2="$ROOT/second_mac/home2"
  mkdir -p "$home2/.config/moblee"
  printf '%s\n' "$SBX" > "$home2/.config/moblee/vault-path"
  cp "$FIXTURES/old-wiki/VERSION" "$SBX/VERSION"
  ( cd "$SBX" && git add -- VERSION && git commit -qm "an older Moblee on the second Mac" ) >/dev/null 2>&1
  run_update "$home2" "$SBX"
  local second; second=$(find "$home2/.claude/projects" -path "*/memory/*.md" 2>/dev/null | wc -l | tr -d ' ')
  same "$second" "$first" "the second Mac is given the same starting notes"
  hasnt "$home2/update-output.txt" "you took this one out" "and is not told the owner took them out"
}

# --------------------------------------------------------------------------
# (v0.9.6) A ChatGPT owner whose memory page already exists. What the update
# adds to it was left uncommitted on every run.
case_chatgpt_memory() {
  start chatgpt_memory
  make_wiki "$HOME_DIR" "$SBX"
  printf '# Assistant Memory\n\nWhat the assistant has learnt so far.\n' > "$SBX/wiki/Wiki Operations/Assistant Memory.md"
  ( cd "$SBX" && git add -A && git commit -qm "the memory page as it stood" ) >/dev/null 2>&1
  run_update "$HOME_DIR" "$SBX" --assistant chatgpt; local rc=$RC
  same "$rc" "0" "the updater exits cleanly for ChatGPT"
  ( cd "$SBX" && git status --porcelain -- "wiki/Wiki Operations/Assistant Memory.md" ) > "$HOME_DIR/mem-status.txt"
  same "$(wc -c < "$HOME_DIR/mem-status.txt" | tr -d ' ')" "0" "nothing the update wrote to the memory page is left uncommitted"
  has "$SBX/wiki/Wiki Operations/Assistant Memory.md" "What the assistant has learnt so far." "and what was there is kept"
}
for c in happy refused extras owners_pages partly backups index protected twice shrink owners_words gitignore name_clash owners_uncommitted staged_leftovers clash_keeps_safety second_mac chatgpt_memory; do
  wanted "$c" && "case_$c"
done

printf '\n'
if [[ $FAIL -eq 0 ]]; then
  green "update-test: $PASS checks passed, 0 failed"
else
  red "update-test: $PASS passed, $FAIL FAILED"
  for f in "${FAILED[@]}"; do red "  - $f"; done
fi
printf 'scratch kept for inspection: %s\n' "$ROOT"
exit $(( FAIL > 0 ? 1 : 0 ))
