#!/usr/bin/env bash
# run.sh — run the real installer end to end against throwaway wikis and check
# what it actually did.
#
#   bash tools/install-test/run.sh            # every case
#   bash tools/install-test/run.sh refused    # one case by name
#
# Why this exists. On 23 September 2026 a code review found that the installer
# carried, untouched, the fault that had just been fixed in the updater: when
# git refused its closing commit the refusal was silenced twice over — stderr
# to /dev/null, the exit code to `|| true` — and the script went on to say the
# install had finished, print the Done banner, and tell the app to green every
# tile. The updater's version of that fault reached a real owner's Mac before
# anybody saw it, which is the most expensive place to find one. Its sibling rig
# at tools/update-test/ exists for the same reason, and the two run the same way.
#
# A release that touches scripts/install.sh runs this first.
#
# SAFETY. The installer writes to the HOME it is given: ~/.claude (the delete
# guard, the permission rules, the skills, the starting memories), ~/.config/
# moblee and ~/.codex. On a machine where ~/.claude/skills is a symlink into a
# live vault — which is true of both of the author's Macs — running it with a
# real HOME would write over real skills. Every case here therefore runs with
# HOME set to a throwaway directory under TMPDIR, and the script refuses to
# start if that is not so. Nothing outside that directory is written or removed.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE_ROOT="$(cd "$HERE/../.." && pwd)"
FIXTURES="$HERE/fixtures"
WANT="${1:-all}"
ROOT="${TMPDIR:-/tmp}/moblee-install-test-$(date '+%Y%m%d-%H%M%S')"
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

# run_install <home> <vault location> [args...] — runs the installer, sets RC.
#
# The three lessons the updater's rig paid for, kept here rather than learned
# again: stdin comes from /dev/null, because the installer asks questions and
# takes its default at end of input, and left on a terminal it waits for ever
# for an answer to a question the redirection has hidden; the result is set in a
# variable rather than echoed, because `rc=$(run_install …)` waits for every
# writer to the pipe, the backgrounded timeout included, so the rig sits silent
# for the whole timeout after the work has finished and looks like the hang it
# is meant to catch; and the installer's own output is shown as it happens as
# well as captured, so a real stall names the step it died on.
INSTALL_TIMEOUT="${INSTALL_TIMEOUT:-240}"
RC=0
run_install() {
  local home="$1" loc="$2" who="$3"; shift 3
  ( cd "$PACKAGE_ROOT" && HOME="$home" bash scripts/install.sh \
      --name "Test Owner" --vault-name "TestWiki" --location "$loc" \
      --assistant "$who" --progress "$@" ) \
    < /dev/null 2>&1 | tee "$home/install-output.txt" | sed 's/^/      | /' &
  local pid=$!
  ( sleep "$INSTALL_TIMEOUT"; kill -9 "$pid" 2>/dev/null ) >/dev/null 2>&1 &
  local killer=$!
  disown "$killer" 2>/dev/null
  wait "$pid"; RC=$?
  kill "$killer" >/dev/null 2>&1
  if [[ $RC -ge 128 ]]; then
    bad "the installer did not finish within ${INSTALL_TIMEOUT}s and was stopped"
  fi
}

# The vault location is NOT created here: the installer refuses to write into a
# folder that already exists, and rightly, so a case that wants one makes it
# itself and says why.
start() {
  CASE="$1"
  HOME_DIR="$ROOT/$CASE/home"; SBX="$ROOT/$CASE/wiki"
  mkdir -p "$HOME_DIR/.config/moblee"
  printf '\n  %s\n' "$CASE"
}

wanted() { [[ "$WANT" == "all" || "$WANT" == "$1" ]]; }

[[ "$ROOT" == "${TMPDIR:-/tmp}"* ]] || { red "refusing: scratch dir is not under TMPDIR"; exit 2; }

# --------------------------------------------------------------------------
# An ordinary install: it runs, it commits its own settings, and it says so in
# all three places — the screen, the diary the check-up reads, and the progress
# line the app reads.
case_happy() {
  start happy
  run_install "$HOME_DIR" "$SBX" claude; local rc=$RC
  same "$rc" "0" "the installer exits cleanly"
  isfile "$SBX/CLAUDE.md" "the wiki has its rules file"
  isfile "$SBX/wiki/Index.md" "and its starting pages"
  same "$(cat "$SBX/VERSION" 2>/dev/null)" "$(cat "$PACKAGE_ROOT/VERSION")" "the wiki is on this version"
  local diary="$HOME_DIR/.config/moblee/install-diary.txt"
  has   "$diary" "=== Moblee install finished ===" "the diary records a finish"
  hasnt "$diary" "NOT COMMITTED" "and does not report a refused commit"
  ( cd "$SBX" && git log -1 --format=%s ) > "$HOME_DIR/last-subject.txt" 2>/dev/null
  has   "$HOME_DIR/last-subject.txt" "moblee: safety layer" "the install committed its own settings"
  has   "$HOME_DIR/install-output.txt" '"step":"done","state":"ok"' "the app is told the run finished"
  hasnt "$HOME_DIR/install-output.txt" "One thing is not finished" "and the screen claims nothing outstanding"
}

# --------------------------------------------------------------------------
# The fault this rig was written for: git refuses the closing commit, and every
# place that reports on the install must say so rather than claim a finish.
#
# The refusal is real, not simulated. The wiki is one an earlier install left
# half-finished — the recovery path the installer is written for, and the one
# the app's Repair button takes — whose Index.md has grown past the commit
# gate's 8,000-token cap. The gate is wired before the closing commit, the
# starting-memories step adds its line to that Index, and so the Index is
# staged, over its cap, and refused: G3, the same rule and the same shape as the
# oversized CLAUDE.md that refused a real owner's update on 21 September 2026.
#
# It is a ChatGPT install, and that is not arbitrary. Measured on 23 September
# 2026 while writing this case: on a Claude install the closing commit stages
# one file, .claude/settings.local.json, which no gate rule caps or reads — the
# starting memories go to ~/.claude/, not into the wiki, so the Index is never
# touched. ChatGPT's memories are a wiki page, and the Index gains the line that
# links it, so that is the install whose closing commit the pack's own gate can
# refuse. The reporting being tested is shared by both.
case_refused() {
  start refused
  # a wiki an earlier run started and never finished: the note names it, and it
  # carries no git history of its own, which is what makes it a resume rather
  # than a hand-over to the updater
  mkdir -p "$SBX/wiki/Wiki Operations"
  python3 "$FIXTURES/make-oversized-index.py" "$SBX/wiki/Index.md" >/dev/null
  printf '%s\n' "$SBX" > "$HOME_DIR/.config/moblee/in-progress"
  run_install "$HOME_DIR" "$SBX" chatgpt
  local diary="$HOME_DIR/.config/moblee/install-diary.txt"
  local out="$HOME_DIR/install-output.txt"
  has   "$diary" "NOT COMMITTED" "the diary says the install is not committed"
  has   "$diary" "REFUSED" "and names the refusal on the closing step"
  hasnt "$diary" "finish: done" "and does not also mark that step done"
  has   "$out" "One thing is not finished" "the screen says so too"
  has   "$out" '"state":"needs-commit"' "and the app is told, so it cannot green the tiles"
  hasnt "$out" '"step":"done","state":"ok"' "the run-level signal does not still claim a finish"
  local staged; staged=$(cd "$SBX" && git diff --cached --name-only 2>/dev/null | wc -l | tr -d ' ')
  if [[ "${staged:-0}" -gt 0 ]]; then ok "the work is staged, not lost ($staged files)"; else bad "nothing staged"; fi
}

# --------------------------------------------------------------------------
# scripts/install-skills.sh, which both the installer and the updater run.
#
# Until v0.9.2 its --update mode — the only mode the updater uses — replaced any
# skill of a Moblee name in ~/.claude/skills, whoever had written it, by moving
# the folder out to the backups folder. Two faults in one line. The owner's own
# work went without being asked; and where ~/.claude/skills is a symlink into a
# synced vault, which it is on both of the author's Macs, the move took vault
# content OUT of the vault, which every sync client reads as a deletion, on
# every machine at once.
case_skills() {
  start skills
  local A="$ROOT/skills/fresh-home" B="$ROOT/skills/owner-home"
  mkdir -p "$A/.claude/skills" "$B/.claude"

  ( cd "$PACKAGE_ROOT" && HOME="$A" bash scripts/install-skills.sh --update ) >"$A/out.txt" 2>&1
  isfile "$A/.config/moblee/skills-claude" "a fresh install writes down which skills are Moblee's"
  same "$(ls "$A/.claude/skills" | wc -l | tr -d ' ')" "$(find "$PACKAGE_ROOT/skills" -maxdepth 1 -type d ! -path "$PACKAGE_ROOT/skills" | wc -l | tr -d ' ')" \
       "and installs every one of them"

  # an owner from before the record: Moblee's skills in place, no record of them
  cp -R "$A/.claude/skills" "$B/.claude/skills"
  printf 'an older Moblee shipped this line\n' >> "$B/.claude/skills/brain/SKILL.md"
  local inode_before; inode_before=$(stat -f %i "$B/.claude/skills/brain")
  ( cd "$PACKAGE_ROOT" && HOME="$B" bash scripts/install-skills.sh --update ) >"$B/out.txt" 2>&1
  isfile "$B/.config/moblee/skills-claude" "an owner from before the record gets one, seeded from what is there"
  same "$(stat -f %i "$B/.claude/skills/brain")" "$inode_before" \
       "and Moblee's own skill is replaced where it stands, not moved out from under a sync client"
  hasnt "$B/.claude/skills/brain/SKILL.md" "an older Moblee shipped this line" "the pack's copy is now in place"
  if ls "$B/.config/moblee/backups"/*/skills/brain/SKILL.md >/dev/null 2>&1; then
    ok "and the copy it replaced is kept"
  else
    bad "and the copy it replaced is kept"
  fi

  # a skill of the owner's own, written after the record exists
  printf -- "---\nname: galaxy\n---\n\nThe owner wrote this one himself.\n" > "$B/.claude/skills/galaxy/SKILL.md"
  sed -i '' '/^galaxy$/d' "$B/.config/moblee/skills-claude"
  ( cd "$PACKAGE_ROOT" && HOME="$B" bash scripts/install-skills.sh --update ) >"$B/out2.txt" 2>&1
  has "$B/.claude/skills/galaxy/SKILL.md" "The owner wrote this one himself" \
      "a skill of the owner's own wearing a Moblee name is left exactly as it is"
  has "$B/out2.txt" "left alone" "and he is told so rather than finding out later"
}

# --------------------------------------------------------------------------
# The skills are what the assistant answers "get me started" with. When they do
# not all go in, the installer used to print "Your wiki is ready." and then send
# the owner to that very phrase, which would do nothing for them.
case_skills_failed() {
  start skills_failed
  # a skill of the owner's own wearing a Moblee name: the safe install leaves it
  # alone and reports, which is what makes the step fail
  mkdir -p "$HOME_DIR/.claude/skills/brain"
  printf -- "---\nname: brain\n---\n\nThe owner wrote this one himself.\n" > "$HOME_DIR/.claude/skills/brain/SKILL.md"
  run_install "$HOME_DIR" "$SBX" claude
  local out="$HOME_DIR/install-output.txt"
  hasnt "$out" "  Your wiki is ready." "the banner does not simply say the wiki is ready"
  has   "$out" "with one thing still to put right" "it says what is outstanding"
  has   "$out" "get me started" "and still gives the owner their next step"
  has   "$out" "install-skills.sh" "with the command that puts the skills in"
  has   "$HOME_DIR/.claude/skills/brain/SKILL.md" "The owner wrote this one himself" \
        "and his own skill was left exactly as it is"
  has   "$HOME_DIR/.config/moblee/install-diary.txt" "skills: FAILED" "the diary records the step as failed"
}

# --------------------------------------------------------------------------
printf '\n  Moblee install test — %s\n  scratch: %s\n' "$(cat "$PACKAGE_ROOT/VERSION")" "$ROOT"
for c in happy refused skills skills_failed; do
  if wanted "$c"; then "case_$c"; fi
done

printf '\n  %d passed, %d failed\n' "$PASS" "$FAIL"
if [[ $FAIL -gt 0 ]]; then
  for f in "${FAILED[@]}"; do red "    $f"; done
  printf '  the wikis under test were left at %s\n' "$ROOT"
  exit 1
fi
green "  all good"
printf '  the wikis under test were left at %s (remove it when you are done)\n' "$ROOT"
