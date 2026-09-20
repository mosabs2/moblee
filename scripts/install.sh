#!/usr/bin/env bash
# install.sh - Lay down a Moblee wiki on this Mac.
#
# Run from the root of the Moblee package (the folder containing this script's
# parent `scripts/` directory, alongside `vault-template/` and `skills/`).
#
#   bash scripts/install.sh
#
# What it does:
#   1. Asks for a vault name (default: "MyWiki").
#   2. Asks for a vault location (default: "$HOME/Wiki/<vault name>").
#   3. Refuses to overwrite an existing directory.
#   4. Copies vault-template/ to the destination.
#   5. Substitutes [Your Name] and [Your Vault Name] placeholders inside files.
#   6. Installs the safety layer and the core skills.
#   7. Prints the next step: the "get me started" conversation with Claude in
#      the vault, which asks how the owner works and prepares the checklist
#      (scripts/moblee-setup.py). The checklist can also be opened here.
#
# The owner runs this script, not Claude: it changes Claude's own settings
# (the delete guard, the permission rules, the skills), and those changes are
# the owner's to make where they can see them.

#
# Answers can also be given up front, which is how the Moblee app runs this
# script (one install path, whether it is started from Terminal or the app):
#
#   bash scripts/install.sh --name "Sam" --vault-name "MyWiki" \
#        --location "$HOME/Wiki/MyWiki" --progress
#
#   --name, --vault-name, --location   each answers its question in advance
#   --progress   also print one line per step for a program to read, each
#                starting "@@moblee " followed by a small JSON object
#
# Every run, however it is started, keeps a plain diary of its steps at
# ~/.config/moblee/install-diary.txt: what ran, what passed, what failed and
# why. It holds no names and writes the home folder as "~", so it is safe to
# pass to whoever is helping if an install goes wrong.

set -euo pipefail

# ----- locate the package root ------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VAULT_TEMPLATE="$PACKAGE_ROOT/vault-template"

# ----- answers given up front -------------------------------------------------
ARG_NAME=""; ARG_VAULT_NAME=""; ARG_LOCATION=""; PROGRESS=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --name)        ARG_NAME="${2:-}"; shift 2 ;;
    --vault-name)  ARG_VAULT_NAME="${2:-}"; shift 2 ;;
    --location)    ARG_LOCATION="${2:-}"; shift 2 ;;
    --progress)    PROGRESS=1; shift ;;
    *) echo "Unknown option: $1"; exit 2 ;;
  esac
done

# ----- the install diary and the progress lines -------------------------------
DIARY_DIR="$HOME/.config/moblee"
DIARY="$DIARY_DIR/install-diary.txt"
mkdir -p "$DIARY_DIR"
STEP_TOTAL=6
STEP_N=0
CURRENT_STEP="starting"

diary() {
  # the home folder is written as "~" so the diary carries no account name, and
  # the wiki's folder as "<wiki>", since a wiki is often named after its owner
  local line="$*"
  if [[ -n "${VAULT_LOCATION:-}" ]]; then
    line="${line//\/private$VAULT_LOCATION/<wiki>}"
    line="${line//$VAULT_LOCATION/<wiki>}"
  fi
  if [[ -n "${VAULT_NAME:-}" ]]; then line="${line//$VAULT_NAME/<wiki>}"; fi
  line="${line//\/private$HOME/~}"
  line="${line//$HOME/~}"
  printf '%s  %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$line" >> "$DIARY" 2>/dev/null || true
}
emit() {
  # emit <step> <state> [why]   (why is always one of a fixed set of words)
  [[ $PROGRESS -eq 1 ]] || return 0
  if [[ -n "${3:-}" ]]; then
    printf '@@moblee {"step":"%s","state":"%s","n":%d,"of":%d,"why":"%s"}\n' "$1" "$2" "$STEP_N" "$STEP_TOTAL" "$3"
  else
    printf '@@moblee {"step":"%s","state":"%s","n":%d,"of":%d}\n' "$1" "$2" "$STEP_N" "$STEP_TOTAL"
  fi
}
step_start() { STEP_N=$((STEP_N+1)); CURRENT_STEP="$1"; diary "step $STEP_N of $STEP_TOTAL, $1: started"; emit "$1" start; }
step_ok()    { diary "step $STEP_N of $STEP_TOTAL, $1: done"; emit "$1" ok; }
step_fail()  { diary "step $STEP_N of $STEP_TOTAL, $1: FAILED ($2)"; emit "$1" fail "$2"; }
diary_tail() {
  # the last lines of a step's own output, kept only when the step failed
  local file="$1" l
  [[ -f "$file" ]] || return 0
  while IFS= read -r l; do diary "    | $l"; done < <(tail -n 15 "$file")
}
on_exit() {
  local code=$?
  if [[ $code -ne 0 ]]; then
    diary "stopped during \"$CURRENT_STEP\" with exit code $code"
    emit "$CURRENT_STEP" stopped
  fi
}
trap on_exit EXIT

{
  printf '\n'
} >> "$DIARY" 2>/dev/null || true
diary "=== Moblee install begins ==="
diary "pack version: $(cat "$PACKAGE_ROOT/VERSION" 2>/dev/null || echo unknown)"
diary "macOS: $(sw_vers -productVersion 2>/dev/null || echo unknown), chip: $(uname -m)"
if xcode-select -p >/dev/null 2>&1; then
  diary "python3: $(command -v python3 || echo none) ($(python3 --version 2>&1 || true))"
  diary "git: $(git --version 2>&1 || echo none)"
else
  # asking the stand-in python3 or git for a version would pop up Apple's
  # install window, so the diary only notes that the tools are missing
  diary "Apple's developer tools are not installed (no git, no python3)"
fi
diary "started from: $([[ $PROGRESS -eq 1 ]] && echo 'the app' || echo 'Terminal'); answers up front: name=$([[ -n "$ARG_NAME" ]] && echo yes || echo no) wiki-name=$([[ -n "$ARG_VAULT_NAME" ]] && echo yes || echo no) place=$([[ -n "$ARG_LOCATION" ]] && echo yes || echo no)"

if [[ ! -d "$VAULT_TEMPLATE" ]]; then
  echo "Error: vault-template/ not found at $VAULT_TEMPLATE"
  echo "Are you running this script from inside the Moblee package?"
  diary "the pack's vault-template folder is missing"
  emit starting fail template-missing
  exit 1
fi

echo ""
echo "==================================================================="
echo "  Moblee installer"
echo "==================================================================="
echo ""
echo "This script lays down a Karpathy-style Obsidian vault on your Mac."
echo ""

# ----- collect user input -----------------------------------------------------
if [[ -n "$ARG_NAME" ]]; then
  USER_NAME="$ARG_NAME"
else
  read -r -p "Your name (used in templates) [Your Name]: " USER_NAME || USER_NAME=""
fi
USER_NAME="${USER_NAME:-[Your Name]}"

if [[ -n "$ARG_VAULT_NAME" ]]; then
  VAULT_NAME="$ARG_VAULT_NAME"
else
  read -r -p "Vault name [MyWiki]: " VAULT_NAME || VAULT_NAME=""
fi
VAULT_NAME="${VAULT_NAME:-MyWiki}"

DEFAULT_LOCATION="$HOME/Wiki/$VAULT_NAME"
if [[ -n "$ARG_LOCATION" ]]; then
  VAULT_LOCATION="$ARG_LOCATION"
else
  read -r -p "Vault location [$DEFAULT_LOCATION]: " VAULT_LOCATION || VAULT_LOCATION=""
fi
VAULT_LOCATION="${VAULT_LOCATION:-$DEFAULT_LOCATION}"

# expand a leading ~ if the user typed one
VAULT_LOCATION="${VAULT_LOCATION/#\~/$HOME}"

# ----- an existing Moblee vault at this location is updated, not refused ------
# (v0.5) A vault that already carries a VERSION file, or a CLAUDE.md and wiki/,
# is handed to the updater, which brings it to this version without touching
# its content. This is also the recovery path if a previous install stopped
# part-way (for example at the safety step): run the installer again with the
# same answers and it finishes the job through the updater.
IN_PROGRESS="$HOME/.config/moblee/in-progress"
RESUME=0
if [[ -f "$IN_PROGRESS" && -e "$VAULT_LOCATION" && "$(head -1 "$IN_PROGRESS" 2>/dev/null)" == "$VAULT_LOCATION" ]] \
   && ! grep -q "^finished " "$IN_PROGRESS" 2>/dev/null; then
  # This very wiki was started by an earlier run that never finished (the disk
  # filled, the Mac slept, the app was closed). Finish it from the top: nothing
  # of the owner's can be in it yet, since no install ever handed it over.
  RESUME=1
fi
if [[ $RESUME -eq 0 && -f "$VAULT_LOCATION/CLAUDE.md" && -d "$VAULT_LOCATION/wiki" ]]; then
  echo ""
  echo "There is already a Moblee vault at $VAULT_LOCATION."
  echo "Nothing there will be overwritten. Bringing it up to this version instead..."
  diary "a Moblee wiki already exists at the chosen place; handing over to the updater"
  emit starting handed-to-updater
  trap - EXIT
  if [[ $PROGRESS -eq 1 ]]; then
    exec bash "$SCRIPT_DIR/update.sh" "$VAULT_LOCATION" --progress
  fi
  exec bash "$SCRIPT_DIR/update.sh" "$VAULT_LOCATION"
fi

# ----- safety: refuse to overwrite --------------------------------------------
if [[ $RESUME -eq 0 && -e "$VAULT_LOCATION" ]]; then
  echo ""
  echo "There is already a folder at $VAULT_LOCATION, and it is not a Moblee wiki."
  echo "Nothing was changed. Choose a different name or place and run this again."
  diary "the chosen place already holds something that is not a Moblee wiki; nothing was changed"
  emit starting fail place-taken
  exit 1
fi

# ----- room on the disk -------------------------------------------------------
# A wiki is small, but a full disk stops the copy half-way and leaves a stump.
FREE_KB="$(df -k "$HOME" 2>/dev/null | awk 'NR==2 {print $4}')"
if [[ "${FREE_KB:-0}" =~ ^[0-9]+$ && "${FREE_KB:-0}" -lt 512000 ]]; then
  echo ""
  echo "This Mac has less than 500 MB free, so the wiki was not started."
  echo "Nothing was changed. Make some room and run this again."
  diary "less than 500 MB free ($((FREE_KB / 1024)) MB); nothing was changed"
  emit starting fail no-room
  exit 1
fi

# ----- copy the template ------------------------------------------------------
step_start folder
echo ""
mkdir -p "$(dirname "$VAULT_LOCATION")" "$HOME/.config/moblee"
# Which wiki is being made, so that a run that stops part-way can be finished
# by running the installer again with the same answers.
echo "$VAULT_LOCATION" > "$IN_PROGRESS"
if [[ $RESUME -eq 1 ]]; then
  echo "Finishing the wiki that was started at $VAULT_LOCATION..."
  diary "an earlier install of this wiki stopped part-way; finishing it"
  cp -R "$VAULT_TEMPLATE/." "$VAULT_LOCATION/"
else
  echo "Creating vault at $VAULT_LOCATION..."
  cp -R "$VAULT_TEMPLATE" "$VAULT_LOCATION"
fi
# the vault's VERSION always comes from the pack, so the template's copy cannot drift
if [[ -f "$PACKAGE_ROOT/VERSION" ]]; then cp "$PACKAGE_ROOT/VERSION" "$VAULT_LOCATION/VERSION"; fi

# ----- substitute placeholders ------------------------------------------------
echo "Substituting placeholders..."

# Use a portable in-place sed that works on both BSD (macOS default) and GNU.
# We write to a temp file and move it back to avoid sed -i incompatibilities.
TODAY="$(date '+%-d %B %Y')"
# A name typed by a person can hold characters sed treats specially in a
# replacement (a backslash, an ampersand, the | used as the separator here),
# so they are escaped before use: "Tom & Sam" must arrive as typed.
sed_safe() {
  local s="$1"
  s="${s//\\/\\\\}"
  s="${s//&/\\&}"
  s="${s//|/\\|}"
  printf '%s' "$s"
}
SED_USER_NAME="$(sed_safe "$USER_NAME")"
SED_VAULT_NAME="$(sed_safe "$VAULT_NAME")"
substitute_in_file() {
  local file="$1"
  local tmp
  tmp="$(mktemp)"
  sed -e "s|\[Your Name\]|$SED_USER_NAME|g" \
      -e "s|\[Your Vault Name\]|$SED_VAULT_NAME|g" \
      -e "s|\[Your Vault\]|$SED_VAULT_NAME|g" \
      -e "s|\[Install date\]|$TODAY|g" \
      "$file" > "$tmp"
  mv "$tmp" "$file"
}

# Walk the vault and substitute in every text file. We only touch .md, .css,
# .html, .py, and a small set of other text formats; binary files are skipped.
while IFS= read -r -d '' file; do
  substitute_in_file "$file"
done < <(find "$VAULT_LOCATION" \
              -type f \
              \( -name "*.md" -o -name "*.css" -o -name "*.html" \
                 -o -name "*.py" -o -name "*.txt" -o -name "*.yml" \
                 -o -name "*.yaml" -o -name "*.json" \) \
              -print0)

# The starter's log, working-state page and index say "[Date]" until someone
# fills them in, and the log's first entry can never be corrected afterwards.
# The installer knows the moment, so it writes it.
python3 "$SCRIPT_DIR/stamp-starter-dates.py" --vault "$VAULT_LOCATION" | sed 's/^/  /' \
  || echo "  (the starter pages' dates were not filled in; harmless, Claude writes them at the first ingest)"

step_ok folder

# ----- copy the vault tooling (v0.4, extended v0.5) ---------------------------
step_start tools
echo "Copying vault tooling (lint, commit gate, preflight, log appender, galaxy, dashboard)..."
mkdir -p "$VAULT_LOCATION/scripts"
for tool in lint-v2.py vault-gate.py vault-orient-preflight.sh log-append.py; do
  if [[ -f "$SCRIPT_DIR/$tool" ]]; then
    cp "$SCRIPT_DIR/$tool" "$VAULT_LOCATION/scripts/$tool"
  fi
done
if [[ -d "$SCRIPT_DIR/hooks" ]]; then
  cp -R "$SCRIPT_DIR/hooks" "$VAULT_LOCATION/scripts/hooks"
  chmod +x "$VAULT_LOCATION"/scripts/hooks/* 2>/dev/null || true
fi
if [[ -d "$SCRIPT_DIR/wiki-galaxy" ]]; then
  cp -R "$SCRIPT_DIR/wiki-galaxy" "$VAULT_LOCATION/scripts/wiki-galaxy"
fi
if [[ -d "$PACKAGE_ROOT/dashboard" ]]; then
  cp -R "$PACKAGE_ROOT/dashboard" "$VAULT_LOCATION/dashboard"
fi

step_ok tools

# ----- git init ---------------------------------------------------------------
step_start history
echo "Initialising git repository..."
(
  cd "$VAULT_LOCATION"
  git init --quiet --initial-branch=main 2>/dev/null || git init --quiet
  # Give the repo a local identity so the user's first real commit does not
  # print git's "your name and email address were configured automatically"
  # notice, which reads like an error to someone who has never used git.
  # Repo-local only; the user's global git config is left untouched.
  if [[ -z "$(git config user.email || true)" ]]; then
    if [[ "$USER_NAME" != "[Your Name]" ]]; then
      git config user.name "$USER_NAME"
    else
      git config user.name "$(id -un)"
    fi
    git config user.email "$(id -un)@$(hostname -s).local"
  fi
  git add . >/dev/null
  git commit --quiet -m "initial vault from Moblee starter pack" \
    || echo "  (git commit skipped, configure user.name and user.email first)"
)

# ----- wire the commit gate (v0.5: through scripts/hooks, never .git/hooks) ---
# The hooks live in the vault at scripts/hooks/, where updates reach them, and
# git is pointed at that folder. Nothing is written into .git/hooks/.
if [[ -d "$VAULT_LOCATION/scripts/hooks" && -d "$VAULT_LOCATION/.git" ]]; then
  ( cd "$VAULT_LOCATION" && git config core.hooksPath scripts/hooks )
  echo "Commit gate wired (git core.hooksPath = scripts/hooks)."
elif [[ -f "$VAULT_LOCATION/scripts/vault-gate.py" && -d "$VAULT_LOCATION/.git" ]]; then
  {
    echo '#!/bin/sh'
    echo 'exec python3 "$(git rev-parse --show-toplevel)/scripts/vault-gate.py"'
  } > "$VAULT_LOCATION/.git/hooks/pre-commit"
  chmod +x "$VAULT_LOCATION/.git/hooks/pre-commit"
  echo "Commit gate installed (.git/hooks/pre-commit)."
fi
if git -C "$VAULT_LOCATION" rev-parse --verify --quiet HEAD >/dev/null 2>&1; then
  step_ok history
else
  # the wiki works without its first commit, so this is recorded and not fatal
  diary "step $STEP_N of $STEP_TOTAL, history: the first commit was not made"
  emit history ok
fi

# ----- safety layer (v0.5; not optional) --------------------------------------
# The delete guard inspects every shell command Claude composes and refuses
# deletion, history rewriting and force pushes; the permission rules stop the
# constant prompts for routine work. Without this layer the vault is not safe
# to hand to anyone, so a failure here stops the install.
echo ""
echo "Installing the safety layer (delete guard and permission rules)..."
step_start safety
SAFETY_OUT="$(mktemp)"
if python3 "$PACKAGE_ROOT/safety/install-safety.py" --vault "$VAULT_LOCATION" 2>&1 | tee "$SAFETY_OUT"; then
  step_ok safety
else
  step_fail safety safety-layer
  diary_tail "$SAFETY_OUT"
  echo ""
  echo "The safety layer did not install, so the installer has stopped here:"
  echo "a vault without it is not safe to use. The message above says why."
  echo "Once the cause is fixed, run this installer again with the same answers"
  echo "(it will finish the job without touching what is already there), or run"
  echo "the safety step on its own:"
  echo "  python3 \"$PACKAGE_ROOT/safety/install-safety.py\" --vault \"$VAULT_LOCATION\""
  exit 1
fi

# ----- starting memories (v0.5) -----------------------------------------------
step_start skills
python3 "$PACKAGE_ROOT/scripts/seed-memory.py" --vault "$VAULT_LOCATION" \
  || { echo "  (starting memories not seeded; harmless, Claude builds its own)"; diary "    starting memories not seeded (harmless)"; }

# ----- the core skills (v0.6: installed here, no longer a separate step) -----
echo ""
echo "Installing the core skills (brain, capture, interview, PDF, galaxy and more)..."
SKILLS_OUT="$(mktemp)"
if bash "$SCRIPT_DIR/install-skills.sh" --quiet 2>&1 | tee "$SKILLS_OUT"; then
  step_ok skills
else
  if grep -q "was NOT installed" "$SKILLS_OUT"; then
    # a different skill already had one of Moblee's names; said plainly above
    step_fail skills skills-skipped
  else
    echo "  (core skills not fully installed; run  bash scripts/install-skills.sh  later)"
    step_fail skills skills-incomplete
  fi
  diary_tail "$SKILLS_OUT"
fi

# ----- the checklist (v0.6; offered, not shown, from v0.7) -------------------
# Everything optional is chosen from one checklist. From v0.7 nothing on it is
# ticked in advance: the usual path is the "get me started" conversation with
# Claude in the new vault, which asks how the owner works and gives them a
# command that opens the checklist with the fitting items ticked. Owners who
# would rather choose alone can open it here.
echo ""
echo "==================================================================="
echo "  Your wiki is ready."
echo "==================================================================="
echo ""
echo "Moblee can also connect your wiki to your Mac's Calendar, Mail and"
echo "Reminders, Google, GitHub and Chrome, and add tools for videos, documents"
echo "and editing. Rather than tick through a long list now, the easier way is"
echo "to open Claude in your new wiki and say: get me started"
echo "Claude asks how you use your Mac and what you read, watch and make, then"
echo "suggests only what fits and gives you one command to install it."
echo ""
if [[ -t 0 ]]; then
  read -r -p "Would you rather choose from the full checklist yourself now? [y/N]: " OPEN_SETUP || OPEN_SETUP="n"  # no answer: do not open
  if [[ "$OPEN_SETUP" =~ ^[Yy]$ ]]; then
    MOBLEE_VAULT="$VAULT_LOCATION" python3 "$SCRIPT_DIR/moblee-setup.py" \
      || echo "  (the checklist stopped early; run  python3 scripts/moblee-setup.py  to carry on)"
  fi
fi

# ----- commit the settings the install wrote (v0.5) ---------------------------
# The initial commit happened before the safety step; the permission rules and
# the ignore file it added are committed now, so the vault starts clean.
step_start finish
(
  cd "$VAULT_LOCATION"
  # one path per git add: a missing path makes git stage nothing at all
  for p in .claude .gitignore VERSION CLAUDE.md scripts wiki/Index.md "wiki/Wiki Operations/Moblee Learning Path.md"; do
    if [[ -e "$p" ]]; then git add -A -- "$p" 2>/dev/null || true; fi
  done
  if ! git diff --cached --quiet 2>/dev/null; then
    git commit --quiet -m "moblee: safety layer, settings and chosen options" 2>/dev/null || true
  fi
)

# ----- record the vault path for the tooling ----------------------------------
# lint-v2, the gate, the galaxy and the dashboard all find the vault through
# this file (overridable with the MOBLEE_VAULT environment variable). It is
# written last, so an install that stopped part-way is never mistaken for a
# finished wiki; running the installer again with the same answers finishes it.
mkdir -p "$HOME/.config/moblee"
echo "$VAULT_LOCATION" > "$HOME/.config/moblee/vault-path"
# and the pack's own folder, so the owner's Claude can point back at the checklist
echo "$PACKAGE_ROOT" > "$HOME/.config/moblee/package-path"
# the install is whole, so it is no longer "in progress": the note says so
echo "finished $(date '+%Y-%m-%d %H:%M')" >> "$IN_PROGRESS"
step_ok finish
CURRENT_STEP="finished"
diary "=== Moblee install finished ==="
if [[ $PROGRESS -eq 1 ]]; then
  JSON_VAULT="${VAULT_LOCATION//\\/\\\\}"
  JSON_VAULT="${JSON_VAULT//\"/\\\"}"
  printf '@@moblee {"step":"done","state":"ok","n":%d,"of":%d,"vault":"%s"}\n' "$STEP_TOTAL" "$STEP_TOTAL" "$JSON_VAULT"
fi

# ----- done -------------------------------------------------------------------
echo ""
echo "==================================================================="
echo "  Done."
echo "==================================================================="
echo ""
echo "Your vault lives at:"
echo "  $VAULT_LOCATION"
echo ""
echo "Next steps:"
echo "  1. Open Obsidian, choose \"Open folder as vault\", and point it at:"
echo "       $VAULT_LOCATION"
echo ""
echo "  2. Open Claude in your wiki and say \"get me started\":"
echo "       cd \"$VAULT_LOCATION\""
echo "       claude"
echo ""
echo "  3. Whenever you like, from this Moblee folder:"
echo "       Choose extras yourself:  python3 scripts/moblee-setup.py"
echo "       Test that it all works:  python3 scripts/moblee-setup.py --check"
echo "       Dashboard:  python3 \"$VAULT_LOCATION/dashboard/server.py\"   (then open the printed URL)"
echo "       Galaxy:     say \"galaxy\" to Claude in your vault"
echo ""
echo "  Safety: the delete guard is on. Claude cannot delete files in this vault"
echo "  at all; if something must go, Claude tells you what and you remove it"
echo "  yourself. Routine work no longer asks permission."
echo "  To update later: download the new Moblee and run  bash scripts/update.sh"
echo ""
