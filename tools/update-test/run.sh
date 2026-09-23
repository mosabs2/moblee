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

# run_update <home> <sandbox> [args...] — echoes the exit code.
run_update() {
  local home="$1" sbx="$2"; shift 2
  ( cd "$PACKAGE_ROOT" && HOME="$home" bash scripts/update.sh "$sbx" "$@" ) \
    > "$home/update-output.txt" 2>&1
  echo $?
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
  local rc; rc=$(run_update "$HOME_DIR" "$SBX")
  same "$rc" "0" "the updater exits cleanly"
  same "$(cat "$SBX/VERSION")" "$(cat "$PACKAGE_ROOT/VERSION")" "the wiki is on the new version"
  has   "$HOME_DIR/.config/moblee/install-diary.txt" "=== Moblee update finished ===" "the diary records a finish"
  hasnt "$HOME_DIR/.config/moblee/install-diary.txt" "NOT COMMITTED" "and does not report a refused commit"
  ( cd "$SBX" && git log -1 --format=%s ) | tee "$HOME_DIR/last-subject.txt" >/dev/null
  has   "$HOME_DIR/last-subject.txt" "moblee: updated" "the update committed itself"
  same  "$(cd "$SBX" && git status --porcelain | wc -l | tr -d ' ')" "0" "nothing is left staged"
  has   "$SBX/wiki/log.md" "the owner wrote this" "the owner's own content is untouched"
}

# --------------------------------------------------------------------------
# The v0.9.1 fault: git refuses the closing commit, and every place that
# reports on the update must say so rather than claim a finish.
case_refused() {
  start refused
  make_wiki "$HOME_DIR" "$SBX"
  mkdir -p "$SBX/.git/hooks"
  cp "$FIXTURES/refusing-pre-commit" "$SBX/.git/hooks/pre-commit"
  chmod +x "$SBX/.git/hooks/pre-commit"
  run_update "$HOME_DIR" "$SBX" >/dev/null
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
  run_update "$HOME_DIR" "$SBX" >/dev/null
  isfile "$SBX/scripts/orient-extras.sh" "the owner's extras file is created"
  has "$SBX/scripts/vault-orient-preflight.sh" "orient-extras.sh" "the preflight knows to run it"
  cp "$FIXTURES/owners-own-check.sh" "$SBX/scripts/orient-extras.sh"
  cp "$FIXTURES/old-wiki/VERSION" "$SBX/VERSION"
  ( cd "$SBX" && git add -A && git commit -qm "the owner adds his own check" ) >/dev/null 2>&1
  run_update "$HOME_DIR" "$SBX" >/dev/null
  has "$SBX/scripts/orient-extras.sh" "the owner wrote this check himself" \
      "and a second update leaves it exactly as he left it"
}

# --------------------------------------------------------------------------
# An Index that already keeps a Wiki Operations line must not gain a second.
case_index() {
  start index
  make_wiki "$HOME_DIR" "$SBX"
  run_update "$HOME_DIR" "$SBX" >/dev/null
  same "$(grep -c '^- Wiki Operations' "$SBX/wiki/Index.md" 2>/dev/null | tr -d ' ')" "1" \
       "the Index keeps exactly one Wiki Operations line"
}

# --------------------------------------------------------------------------
# Running the same update twice must change nothing the second time.
case_twice() {
  start twice
  make_wiki "$HOME_DIR" "$SBX"
  run_update "$HOME_DIR" "$SBX" >/dev/null
  local first; first=$(cd "$SBX" && git rev-parse HEAD)
  run_update "$HOME_DIR" "$SBX" >/dev/null
  same "$(cd "$SBX" && git rev-parse HEAD)" "$first" "a second run makes no new commit"
  same "$(cd "$SBX" && git status --porcelain | wc -l | tr -d ' ')" "0" "and leaves nothing staged"
}

for c in happy refused extras index twice; do
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
