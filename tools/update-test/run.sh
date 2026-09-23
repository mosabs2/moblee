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
# fixed in v0.9.1 were all found by an owner after release, on his own wiki,
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

# make_wiki <home> <sandbox> — a wiki as it stands before an update.
make_wiki() {
  local home="$1" sbx="$2"
  mkdir -p "$sbx" "$home/.config/moblee"
  cp -R "$FIXTURES/old-wiki/." "$sbx/"
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
  mkdir -p "$HOME_DIR/nopython"
  printf '#!/bin/sh\nexit 127\n' > "$HOME_DIR/nopython/python3"
  chmod +x "$HOME_DIR/nopython/python3"
  ( cd "$PACKAGE_ROOT" && PATH="$HOME_DIR/nopython:$PATH" HOME="$HOME_DIR" \
      bash scripts/update.sh "$SBX" --progress ) < /dev/null > "$HOME_DIR/update-output.txt" 2>&1
  local diary="$HOME_DIR/.config/moblee/install-diary.txt"
  has  "$diary" "DID NOT FINISH" "the diary names what did not finish"
  has  "$diary" "done, except" "and the step says it finished all but that"
  has  "$HOME_DIR/update-output.txt" "did not finish" "the screen says so at the end"
  has  "$HOME_DIR/update-output.txt" '"state":"partial"' "and the app is told, so it can say so too"
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

for c in happy refused extras owners_pages partly backups index protected twice; do
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
