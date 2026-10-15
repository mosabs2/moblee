#!/usr/bin/env bash
# run.sh — run the real installer end to end against throwaway wikis and check
# what it actually did, and run the commit gate it wires in against the commits
# a wiki really receives.
#
#   bash tools/install-test/run.sh                # every case
#   bash tools/install-test/run.sh refused        # one case by name
#   bash tools/install-test/run.sh engine_path    # (v0.10.0) one of the three
#   bash tools/install-test/run.sh engine_app     #   branches by which the
#   bash tools/install-test/run.sh engine_none    #   installer finds a Claude
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
  has "$B/out2.txt" "left alone" "and they are told so rather than finding out later"
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
        "and their own skill was left exactly as it is"
  has   "$HOME_DIR/.config/moblee/install-diary.txt" "skills: FAILED" "the diary records the step as failed"
}

# --------------------------------------------------------------------------
# Claude's own additions (v0.10.0): mods/ goes into the wiki at
# scripts/claude-mods/ and the band above the prompt is registered with Claude
# from there. Mods are a Claude Code feature and arrived in 2.1.287, so the
# installer has to find a Claude new enough before it runs a single plugin
# command, and it looks in two places: the `claude` on the owner's own PATH,
# and the engine inside the Claude app. Three branches, one case each.
#
# Every Claude here is a stub inside the case's own sandboxed HOME: a little
# script that prints a version and writes down every call it was given. That is
# what makes it possible to assert that the right commands were run, in the
# right order, by the right engine, without installing anything for real or
# touching this Mac's own Claude. The real 2.1.295 engine on the author's Mac
# was used separately, by hand, to prove the commands themselves work.
#
# engine_stub <path> <version> <calls file>
engine_stub() {
  local path="$1" version="$2" calls="$3"
  mkdir -p "$(dirname "$path")"
  cat > "$path" <<STUB
#!/bin/sh
printf '%s\n' "\$*" >> "$calls"
if [ "\$1" = "--version" ]; then printf '%s (Claude Code)\n' "$version"; exit 0; fi
case "\$*" in
  "plugin list --json")       printf '[]\n'; exit 0 ;;
  "plugin list")              printf 'No plugins installed\n'; exit 0 ;;
  "plugin marketplace list")  printf 'Configured marketplaces:\n'; exit 0 ;;
esac
exit 0
STUB
  chmod +x "$path"
}

# app_engine_stub <home> <version> <build> <calls file> — where the Claude app
# keeps its own engine: one folder per version, with a build folder inside it.
app_engine_stub() {
  engine_stub "$1/Library/Application Support/Claude/claude-code/$2/$3/claude.app/Contents/MacOS/claude" \
              "$2" "$4"
}

# The sentences are read from the product rather than typed again here, so that
# a case cannot pass against wording the installer no longer uses.
# shellcheck source=../../scripts/claude-mods.sh
. "$PACKAGE_ROOT/scripts/claude-mods.sh"

# mods_asserts <calls file of the engine that should have been used> — the two
# commands the install path takes, and the folder they are taken against.
mods_commands() {
  local calls="$1" vault="$2"
  has "$calls" "plugin marketplace add $vault/scripts/claude-mods" \
      "Claude was pointed at the wiki's own copy of the mods"
  has "$calls" "plugin install --scope user --yes cold-cache-warning@moblee-mods" \
      "and asked to install the band at user scope, without a prompt"
}

# The mods land in the wiki whatever Claude turns out to be, because the wiki is
# where they live: an owner whose Claude catches up later needs them to be there.
mods_in_wiki() {
  local vault="$1"
  isfile "$vault/scripts/claude-mods/.claude-plugin/marketplace.json" \
         "the mods are in the wiki, as scripts/claude-mods/"
  isfile "$vault/scripts/claude-mods/cold-cache-warning/.claude-plugin/plugin.json" \
         "with the band's own folder inside it"
  ( cd "$vault" && HOME="$HOME_DIR" git ls-files -- scripts/claude-mods ) \
    > "$HOME_DIR/mods-tracked.txt" 2>/dev/null
  has "$HOME_DIR/mods-tracked.txt" "scripts/claude-mods/cold-cache-warning" \
      "and they are in the wiki's history, not left untracked"
}

# Branch one: a Claude new enough is on the owner's own PATH, which is the one
# they type, so that is the one used.
case_engine_path() {
  start engine_path
  local calls="$HOME_DIR/path-engine-calls.txt"
  engine_stub "$HOME_DIR/bin/claude" "2.1.295" "$calls"
  app_engine_stub "$HOME_DIR" "2.1.200" "bbbbbbbbbbbb" "$HOME_DIR/app-engine-calls.txt"
  local was_path="$PATH"
  PATH="$HOME_DIR/bin:$PATH"
  run_install "$HOME_DIR" "$SBX" claude
  PATH="$was_path"
  local out="$HOME_DIR/install-output.txt" diary="$HOME_DIR/.config/moblee/install-diary.txt"
  same "$RC" "0" "the installer exits cleanly"
  mods_in_wiki "$SBX"
  mods_commands "$calls" "$SBX"
  has  "$out" "$MODS_YES_SENTENCE" "the screen says the band is in place"
  has  "$diary" "mods: using the Claude on the PATH, version 2.1.295" \
       "the diary says which Claude was used and from where"
  has  "$diary" "mods: installed" "and that the band went in"
  if [[ -s "$HOME_DIR/app-engine-calls.txt" ]]; then
    hasnt "$HOME_DIR/app-engine-calls.txt" "plugin" \
          "the older engine in the Claude app was never asked to install anything"
  else
    ok "the older engine in the Claude app was never asked to install anything"
  fi
}

# Branch two: the `claude` on the PATH is too old — which is the state of the
# author's own Mac, 2.1.277 against an app engine of 2.1.295 — so the engine
# inside the Claude app is used instead. The old one is asked its version and
# nothing else.
case_engine_app() {
  start engine_app
  local old="$HOME_DIR/path-engine-calls.txt" new="$HOME_DIR/app-engine-calls.txt"
  engine_stub "$HOME_DIR/bin/claude" "2.1.277" "$old"
  app_engine_stub "$HOME_DIR" "2.1.9" "aaaaaaaaaaaa" "$HOME_DIR/app-oldest-calls.txt"
  app_engine_stub "$HOME_DIR" "2.1.295" "9d6405864fdc" "$new"
  local was_path="$PATH"
  PATH="$HOME_DIR/bin:$PATH"
  run_install "$HOME_DIR" "$SBX" both
  PATH="$was_path"
  local out="$HOME_DIR/install-output.txt" diary="$HOME_DIR/.config/moblee/install-diary.txt"
  same "$RC" "0" "the installer exits cleanly"
  mods_in_wiki "$SBX"
  mods_commands "$new" "$SBX"
  has   "$old" "--version" "the Claude on the PATH was asked its version"
  hasnt "$old" "plugin" "and, being too old, was asked to do nothing else"
  hasnt "$HOME_DIR/app-oldest-calls.txt" "plugin" \
        "and neither was the older of the app's own engines"
  has   "$diary" "mods: using the Claude in the Claude app, version 2.1.295" \
        "the diary says the app's engine was the one used"
  has   "$out" "$MODS_YES_SENTENCE" "and the screen says the band is in place"
}

# Branch three: no Claude on this Mac is new enough. One plain sentence, in the
# same words on the screen and in the diary, the mods still laid into the wiki,
# and an install that finishes cleanly — nothing else depends on the band.
case_engine_none() {
  start engine_none
  local calls="$HOME_DIR/path-engine-calls.txt"
  engine_stub "$HOME_DIR/bin/claude" "2.1.277" "$calls"
  app_engine_stub "$HOME_DIR" "2.1.200" "bbbbbbbbbbbb" "$HOME_DIR/app-engine-calls.txt"
  local was_path="$PATH"
  PATH="$HOME_DIR/bin:$PATH"
  run_install "$HOME_DIR" "$SBX" claude
  PATH="$was_path"
  local out="$HOME_DIR/install-output.txt" diary="$HOME_DIR/.config/moblee/install-diary.txt"
  same  "$RC" "0" "the installer finishes cleanly all the same"
  has   "$diary" "=== Moblee install finished ===" "and the diary records a finish"
  mods_in_wiki "$SBX"
  has   "$out" "$MODS_NO_ENGINE_SENTENCE" "the screen says it in one plain sentence"
  has   "$diary" "$MODS_NO_ENGINE_SENTENCE" "and the diary carries the same sentence, word for word"
  has   "$diary" "the newest Claude found was 2.1.277" \
        "with the version it found written down beside it"
  hasnt "$calls" "plugin" "no plugin command was run against a Claude too old to know them"
  hasnt "$HOME_DIR/app-engine-calls.txt" "plugin" "nor against the old engine in the app"
  hasnt "$out" "could not be registered" "and nothing is reported as having failed"
}

# --------------------------------------------------------------------------
# The commit gate the installer wires into the wiki (scripts/vault-gate.py,
# called by the tracked hook at scripts/hooks/pre-commit). The cases below do
# not run the installer: they build a throwaway wiki wired the way the installer
# wires one, make the commit the owner would make, and read what the gate said.
#
# make_gate_vault <dir> — that wiki, with one starting commit the gate allowed.
# Everything is under TMPDIR, and git is given the case's sandboxed HOME, so no
# setting of this Mac's own is read and nothing of the owner's is written. The
# pages come from fixtures/make-gate-wiki.py, as the oversized Index of the
# `refused` case does, so that the awkward file names are written once and read
# the same way everywhere.
make_gate_vault() {
  local v="$1"
  python3 "$FIXTURES/make-gate-wiki.py" "$v" "$PACKAGE_ROOT" >/dev/null
  (
    cd "$v" || exit 1
    export HOME="$HOME_DIR"
    git init -q
    git config user.email "test-owner@example.invalid"
    git config user.name "Test Owner"
    git config commit.gpgsign false
    git config core.hooksPath scripts/hooks
    git add -A
    git commit -q -m "the practice wiki as it starts"
  ) >/dev/null 2>&1
  if gate_git "$v" rev-parse --verify -q HEAD >/dev/null 2>&1; then
    ok "the practice wiki starts with a commit the gate allowed"
  else
    bad "the practice wiki starts with a commit the gate allowed"
  fi
}

# gate_git <dir> [args...] — git in that wiki, with the sandboxed HOME.
gate_git() { local v="$1"; shift; ( cd "$v" && HOME="$HOME_DIR" git "$@" ); }

# gate_pages <dir> <set...> — lay down one of the fixture's sets of pages.
gate_pages() { local v="$1"; shift; python3 "$FIXTURES/make-gate-wiki.py" "$v" "$PACKAGE_ROOT" "$@" >/dev/null; }

# gate_commit <dir> <message> <output file> — stage everything and commit
# through the gate, keeping whatever the gate printed; sets RC.
gate_commit() {
  local v="$1" msg="$2" out="$3"
  (
    cd "$v" || exit 1
    export HOME="$HOME_DIR"
    git add -A
    git commit -q -m "$msg"
  ) >"$out" 2>&1
  RC=$?
}

# --------------------------------------------------------------------------
# The gate has to read every file name, whatever it is written in. Until
# v0.10.0 it asked git for the staged paths a line at a time and with git's
# default settings, which hands back a name holding anything but plain English
# letters as a quoted string of octal escapes — "wiki/\331\205..." — matching no
# file on the disk. Every check then passed over that page in silence: the owner
# was told nothing was wrong with a page the gate had never read.
#
# Both names here are ones that form breaks on: one written in Arabic, one with
# a space and a quote mark in it. Each page adds a link to a page that does not
# exist, which is G6's business, so the gate cannot say anything at all about
# either file without having read it.
case_gate_names() {
  start gate_names
  local v="$SBX"
  make_gate_vault "$v"
  gate_pages "$v" awkward-names
  gate_commit "$v" "two pages with awkward names" "$HOME_DIR/names-blocked.txt"
  local out="$HOME_DIR/names-blocked.txt"
  same "$RC" "1" "the gate refuses the commit"
  has  "$out" 'wiki/مرحبا بالعالم.md' "it read the page named in Arabic, by its real name"
  has  "$out" 'wiki/A page with "quotes" in it.md' "and the page with a space and a quote mark in its name"
  hasnt "$out" '\331' "no name came back as git's octal escapes"
  hasnt "$out" '\"quotes\"' "and none came back backslash-escaped"
  # the same two pages once the page they link to is there: both go in
  gate_pages "$v" link-target
  gate_commit "$v" "the pages, with their link resolving" "$HOME_DIR/names-passed.txt"
  same "$RC" "0" "and passes them once the link resolves"
  # Read back what is now tracked the way the gate itself reads git's paths:
  # with -z, which is the only form that hands a name holding a quote mark back
  # as it really is. Asked for a line at a time, git returns that one quoted and
  # backslash-escaped however core.quotepath is set.
  gate_git "$v" ls-files -z 2>/dev/null | tr '\0' '\n' > "$HOME_DIR/names-committed.txt"
  has "$HOME_DIR/names-committed.txt" 'wiki/مرحبا بالعالم.md' "the Arabic-named page is in the commit"
  has "$HOME_DIR/names-committed.txt" 'wiki/A page with "quotes" in it.md' "and so is the quoted one"
}

# --------------------------------------------------------------------------
# G7, new in v0.10.0. A comma inside a value, left unquoted, pushes everything
# after it into the next column, and the file reads wrong from that line down
# without ever looking broken.
case_gate_csv() {
  start gate_csv
  local v="$SBX"
  make_gate_vault "$v"
  gate_pages "$v" csv-unquoted
  gate_commit "$v" "a row with an unquoted comma" "$HOME_DIR/csv-blocked.txt"
  same "$RC" "1" "the gate refuses a row that does not fit the header"
  has "$HOME_DIR/csv-blocked.txt" "G7 wiki/data/notes.csv" "and names the file"
  has "$HOME_DIR/csv-blocked.txt" "reads as 4 columns against the header's 3" \
      "and says in plain words what is wrong with it"
  # the same row with the value quoted, which is how a comma is written in a CSV
  gate_pages "$v" csv-quoted
  gate_commit "$v" "the same row, quoted" "$HOME_DIR/csv-passed.txt"
  same "$RC" "0" "and passes the same row once the value is quoted"
}

# --------------------------------------------------------------------------
# G8, new in v0.10.0. A colon followed by a space inside a plain value ends the
# `---` block at the top of a page early; Obsidian then shows the page with no
# properties at all rather than an error, so nobody notices.
case_gate_frontmatter() {
  start gate_frontmatter
  local v="$SBX"
  make_gate_vault "$v"
  gate_pages "$v" frontmatter-broken
  gate_commit "$v" "frontmatter with an unquoted colon" "$HOME_DIR/fm-blocked.txt"
  same "$RC" "1" "the gate refuses frontmatter that no longer reads as YAML"
  has "$HOME_DIR/fm-blocked.txt" "G8" "and says which check stopped it"
  has "$HOME_DIR/fm-blocked.txt" "wiki/A page.md" "and names the page"
  gate_pages "$v" frontmatter-fixed
  gate_commit "$v" "the same page, quoted" "$HOME_DIR/fm-passed.txt"
  same "$RC" "0" "and passes the page once the value is quoted"
  # The same fault on a Mac with no PyYAML, where the gate uses its own simpler
  # test instead. Nothing in the pack installs PyYAML, so that is the path most
  # owners run.
  gate_pages "$v" frontmatter-broken
  gate_git "$v" add -A >/dev/null 2>&1
  ( cd "$v" && HOME="$HOME_DIR" python3 "$FIXTURES/gate-without-pyyaml.py" ) \
    > "$HOME_DIR/fm-no-pyyaml.txt" 2>&1
  same "$?" "1" "the same fault is caught where PyYAML is not installed"
  has "$HOME_DIR/fm-no-pyyaml.txt" "unquoted ': '" "and the owner is told which value to quote"
}

# --------------------------------------------------------------------------
printf '\n  Moblee install test — %s\n  scratch: %s\n' "$(cat "$PACKAGE_ROOT/VERSION")" "$ROOT"
for c in happy refused skills skills_failed engine_path engine_app engine_none \
         gate_names gate_csv gate_frontmatter; do
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
