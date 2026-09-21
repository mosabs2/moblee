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
#   --assistant claude|chatgpt|both    which assistant the wiki is for (v0.9).
#                Claude reads CLAUDE.md and ChatGPT reads AGENTS.md, so the
#                template's instruction file is laid down under the name the
#                chosen assistant reads (for both: CLAUDE.md, with AGENTS.md a
#                link to it; for chatgpt: AGENTS.md, with CLAUDE.md a link to
#                it, so that an older copy of the Moblee app still knows the
#                wiki). Asked as a fourth question in a Terminal run that
#                asks the others; otherwise the choice already kept in
#                ~/.config/moblee/assistant stands, and with none kept, claude.
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
ARG_ASSISTANT=""; ASSISTANT_FLAG=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --name)        ARG_NAME="${2:-}"; shift 2 ;;
    --vault-name)  ARG_VAULT_NAME="${2:-}"; shift 2 ;;
    --location)    ARG_LOCATION="${2:-}"; shift 2 ;;
    --assistant)   ARG_ASSISTANT="${2:-}"; ASSISTANT_FLAG=1; shift; if [[ $# -gt 0 ]]; then shift; fi ;;
    --assistant=*) ARG_ASSISTANT="${1#--assistant=}"; ASSISTANT_FLAG=1; shift ;;
    --progress)    PROGRESS=1; shift ;;
    *) echo "Unknown option: $1"; exit 2 ;;
  esac
done
if [[ $ASSISTANT_FLAG -eq 1 ]]; then
  case "$ARG_ASSISTANT" in
    claude|chatgpt|both) ;;
    *)
      echo "The assistant must be one of: claude, chatgpt, both. \"$ARG_ASSISTANT\" is not one of them."
      echo "Nothing was changed."
      exit 2
      ;;
  esac
fi

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
emit_trust() {
  # (v0.9) not one of the six steps, so it carries no count: ChatGPT will not
  # run the delete guard until its owner trusts the hook in ChatGPT's settings
  [[ $PROGRESS -eq 1 ]] || return 0
  printf '@@moblee {"step":"trust","state":"needed","assistant":"chatgpt"}\n'
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

# ----- which assistant the wiki is for (v0.9) ---------------------------------
# claude, chatgpt or both, kept as one word in ~/.config/moblee/assistant; no
# file means claude. The question is put only in a Terminal run that is already
# asking the others: a run whose answers all came up front, a run started by
# the app, and a run with no Terminal to ask in are never asked, and take the
# choice already kept on this Mac, or claude where none is kept.
ASSISTANT_FILE="$HOME/.config/moblee/assistant"
STORED_ASSISTANT=""
if [[ -f "$ASSISTANT_FILE" ]]; then
  STORED_ASSISTANT="$(head -1 "$ASSISTANT_FILE" 2>/dev/null | tr -d '[:space:]' || true)"
fi
case "$STORED_ASSISTANT" in
  claude|chatgpt|both) ;;
  *) STORED_ASSISTANT="" ;;
esac
ASSISTANT="${STORED_ASSISTANT:-claude}"
ASSISTANT_CHOSEN=0   # 1 when the owner named it on this run: by the option, or by answering the question
if [[ $ASSISTANT_FLAG -eq 1 ]]; then
  ASSISTANT="$ARG_ASSISTANT"
  ASSISTANT_CHOSEN=1
elif [[ $PROGRESS -eq 0 && -t 0 && ( -z "$ARG_NAME" || -z "$ARG_VAULT_NAME" || -z "$ARG_LOCATION" ) ]]; then
  case "$ASSISTANT" in
    chatgpt) ASSISTANT_DEFAULT=2 ;;
    both)    ASSISTANT_DEFAULT=3 ;;
    *)       ASSISTANT_DEFAULT=1 ;;
  esac
  echo ""
  echo "Which assistant will you use with this wiki?"
  echo "  1) Claude"
  echo "  2) ChatGPT"
  echo "  3) Both"
  while true; do
    read -r -p "Choose 1, 2 or 3 [$ASSISTANT_DEFAULT]: " ASSISTANT_ANSWER || ASSISTANT_ANSWER=""  # no answer: the default
    case "$ASSISTANT_ANSWER" in
      "")                     break ;;
      1|[Cc]laude)            ASSISTANT="claude";  ASSISTANT_CHOSEN=1; break ;;
      2|[Cc]hat[Gg][Pp][Tt])  ASSISTANT="chatgpt"; ASSISTANT_CHOSEN=1; break ;;
      3|[Bb]oth)              ASSISTANT="both";    ASSISTANT_CHOSEN=1; break ;;
      *) echo "  Please answer 1, 2 or 3." ;;
    esac
  done
fi
diary "assistant: $ASSISTANT"
# how the assistant is named in the sentences below
case "$ASSISTANT" in
  chatgpt) ASSISTANT_LABEL="ChatGPT" ;;
  both)    ASSISTANT_LABEL="your assistant" ;;
  *)       ASSISTANT_LABEL="Claude" ;;
esac

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
# (v0.9) A wiki with history is a wiki in use, whatever the note says: an
# install that stopped may have been finished some other way (the updater, or
# the safety step run by itself) and the wiki worked in since. More than the
# installer's own first commit means it goes to the updater, which writes over
# nothing, and is never finished "from the top".
if [[ $RESUME -eq 1 && -d "$VAULT_LOCATION/.git" ]]; then
  COMMITS="$(git -C "$VAULT_LOCATION" rev-list --count HEAD 2>/dev/null || echo 0)"
  if [[ "$COMMITS" =~ ^[0-9]+$ && "$COMMITS" -gt 1 ]]; then
    RESUME=0
    diary "the unfinished-install note names this wiki, but the wiki has $COMMITS commits, so it is in use; handing over to the updater"
  fi
fi
# (v0.9) A wiki made for ChatGPT alone carries AGENTS.md as its real rules
# file. CLAUDE.md marks a Moblee vault as it always has; AGENTS.md marks one
# only beside wiki/Index.md or a VERSION file, since many folders that are not
# wikis carry an AGENTS.md of their own.
if [[ $RESUME -eq 0 && -d "$VAULT_LOCATION/wiki" ]] \
   && [[ -f "$VAULT_LOCATION/CLAUDE.md" || ( -f "$VAULT_LOCATION/AGENTS.md" && ( -f "$VAULT_LOCATION/wiki/Index.md" || -f "$VAULT_LOCATION/VERSION" ) ) ]]; then
  echo ""
  echo "There is already a Moblee vault at $VAULT_LOCATION."
  echo "Nothing there will be overwritten. Bringing it up to this version instead..."
  diary "a Moblee wiki already exists at the chosen place; handing over to the updater"
  emit starting handed-to-updater
  trap - EXIT
  # the assistant goes along only when it was named on this run; otherwise the
  # updater keeps the choice this Mac already holds
  HANDOVER=("$VAULT_LOCATION")
  if [[ $PROGRESS -eq 1 ]]; then HANDOVER+=(--progress); fi
  if [[ $ASSISTANT_CHOSEN -eq 1 ]]; then HANDOVER+=(--assistant "$ASSISTANT"); fi
  exec bash "$SCRIPT_DIR/update.sh" "${HANDOVER[@]}"
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
# The assistant is kept from here on, where a wiki is really being made: a run
# that was refused above leaves the earlier choice as it was.
echo "$ASSISTANT" > "$ASSISTANT_FILE"
if [[ $RESUME -eq 1 ]]; then
  echo "Finishing the wiki that was started at $VAULT_LOCATION..."
  diary "an earlier install of this wiki stopped part-way; finishing it"
  # (v0.9) Finishing never writes over anything: only what is missing is laid
  # down (-n). If the earlier run laid the rules file down as AGENTS.md, it is
  # kept: for ChatGPT alone CLAUDE.md is linked to it first, so the template's
  # own CLAUDE.md is not copied in beside it; for Claude or both it is renamed
  # to CLAUDE.md, replacing nothing but a link.
  if [[ -f "$VAULT_LOCATION/AGENTS.md" && ! -L "$VAULT_LOCATION/AGENTS.md" ]] \
     && [[ -L "$VAULT_LOCATION/CLAUDE.md" || ! -e "$VAULT_LOCATION/CLAUDE.md" ]]; then
    if [[ "$ASSISTANT" == "chatgpt" ]]; then
      if [[ ! -L "$VAULT_LOCATION/CLAUDE.md" ]]; then
        ( cd "$VAULT_LOCATION" && ln -s AGENTS.md CLAUDE.md ) || true
      fi
    elif [[ -L "$VAULT_LOCATION/CLAUDE.md" ]]; then
      mv -f "$VAULT_LOCATION/AGENTS.md" "$VAULT_LOCATION/CLAUDE.md"   # takes the place of the link, and of nothing else
      diary "    the earlier run's AGENTS.md was renamed to CLAUDE.md (it took the place of the CLAUDE.md link)"
    else
      mv -n "$VAULT_LOCATION/AGENTS.md" "$VAULT_LOCATION/CLAUDE.md"
      diary "    the earlier run's AGENTS.md was renamed to CLAUDE.md"
    fi
  fi
  # some versions of cp count a file they left alone as a failure, so the
  # result is judged by what is there afterwards
  cp -Rn "$VAULT_TEMPLATE/." "$VAULT_LOCATION/" || true
  if [[ ! -f "$VAULT_LOCATION/wiki/Index.md" ]]; then
    echo "The wiki's starting pages could not be copied to $VAULT_LOCATION."
    echo "Nothing already there was changed. Check the disk has room and run this again."
    exit 1
  fi
else
  echo "Creating vault at $VAULT_LOCATION..."
  cp -R "$VAULT_TEMPLATE" "$VAULT_LOCATION"
fi
# the vault's VERSION always comes from the pack, so the template's copy cannot drift
if [[ -f "$PACKAGE_ROOT/VERSION" ]]; then cp "$PACKAGE_ROOT/VERSION" "$VAULT_LOCATION/VERSION"; fi

# ----- the instruction file, under the name the assistant reads (v0.9) --------
# Claude reads CLAUDE.md; ChatGPT reads AGENTS.md. The template carries one
# file, CLAUDE.md. For ChatGPT alone it is renamed; for both it stays the real
# file and AGENTS.md is a relative link to it, so there is one text to keep.
# Done here, before the placeholders are filled in and before the first commit.
# The placeholder walk below takes regular files only, so it fills in the real
# file and never follows or rewrites the link.
# For ChatGPT alone, CLAUDE.md is then added back as a relative link to
# AGENTS.md: the Moblee app released before 0.9 knows a wiki only by a
# CLAUDE.md, and without one would build a second wiki beside this one.
# Nothing is ever written over here: no -f, and a name already taken is left.
case "$ASSISTANT" in
  chatgpt)
    if [[ -f "$VAULT_LOCATION/CLAUDE.md" && ! -L "$VAULT_LOCATION/CLAUDE.md" ]]; then
      if [[ -e "$VAULT_LOCATION/AGENTS.md" || -L "$VAULT_LOCATION/AGENTS.md" ]]; then
        echo "An AGENTS.md is already in the wiki, so it was left as it is and CLAUDE.md was not renamed."
        diary "    AGENTS.md was already there; left as it is, CLAUDE.md not renamed"
      else
        mv -n "$VAULT_LOCATION/CLAUDE.md" "$VAULT_LOCATION/AGENTS.md"
        echo "The wiki's instruction file is AGENTS.md, the name ChatGPT reads."
        diary "    the instruction file was laid down as AGENTS.md"
      fi
    fi
    if [[ -f "$VAULT_LOCATION/AGENTS.md" && ! -L "$VAULT_LOCATION/AGENTS.md" ]] \
       && [[ ! -e "$VAULT_LOCATION/CLAUDE.md" && ! -L "$VAULT_LOCATION/CLAUDE.md" ]]; then
      if ( cd "$VAULT_LOCATION" && ln -s AGENTS.md CLAUDE.md ); then
        diary "    CLAUDE.md was laid down as a link to AGENTS.md"
      else
        diary "    the CLAUDE.md link could not be made; the next update adds it"
      fi
    fi
    ;;
  both)
    if [[ -L "$VAULT_LOCATION/AGENTS.md" ]]; then
      :   # the link is there already
    elif [[ -e "$VAULT_LOCATION/AGENTS.md" ]]; then
      echo "An AGENTS.md is already in the wiki, so it was left as it is and no link was made."
      diary "    AGENTS.md was already there as a file of its own; left as it is, no link made"
    else
      ( cd "$VAULT_LOCATION" && ln -s CLAUDE.md AGENTS.md )
      echo "The wiki's instruction file is CLAUDE.md, and AGENTS.md points at it for ChatGPT."
      diary "    AGENTS.md was laid down as a link to CLAUDE.md"
    fi
    ;;
esac

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
  || echo "  (the starter pages' dates were not filled in; harmless, $ASSISTANT_LABEL writes them at the first ingest)"

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
TRUST_NEEDED=0
# (v0.9) ChatGPT runs a hook only once its owner has trusted it, and only the
# owner can do that. The safety installer says when the step is due; it is
# passed on at once, so it is not lost if a later step stops, and the closing
# summary spells the step out. It is looked for when the safety step failed as
# well: the guard may be registered before a later part of that step fails,
# and a second run, finding it registered, would not say so again.
relay_trust() {
  if grep -q '^@@moblee-trust-needed chatgpt' "$SAFETY_OUT" 2>/dev/null; then
    TRUST_NEEDED=1
    diary "    ChatGPT's delete guard is in place and waits for the owner to trust it in ChatGPT's settings"
    emit_trust
  fi
}
# The five steps only the owner can take, in the same words wherever they are printed.
print_trust_steps() {
  local pad="$1"
  # (v0.9) found on a real install: the Hooks page lists nothing until then
  echo "${pad}First open your wiki folder in ChatGPT (File menu, Open Folder). Until a folder has been opened in ChatGPT, its Hooks page is empty and does not say why."
  echo "${pad}1. Open the ChatGPT menu and choose Settings."
  echo "${pad}2. Choose Hooks, under the heading Coding."
  echo "${pad}3. Open \"User config\"."
  echo "${pad}4. Press Trust beside the hook that ends bash-guard.py."
  echo "${pad}5. Turn its switch on."
  echo "${pad}If ChatGPT was open during this, quit it and open it again so that it reads the whole rules file."
  echo "${pad}Then prove it: python3 scripts/moblee-doctor.py --prove-guard (run from the Moblee folder; in the Moblee app, press Prove the guard). It uses a little of your ChatGPT allowance."
  echo "${pad}ChatGPT keeps its trust while Moblee's entry in its hooks list stays the same, so an ordinary Moblee update does not need these steps again. If an update ever does need them, Moblee says so at the end of the update and ChatGPT will not remind you. After any update, prove the guard again."
}
if python3 "$PACKAGE_ROOT/safety/install-safety.py" --vault "$VAULT_LOCATION" --assistant "$ASSISTANT" 2>&1 | tee "$SAFETY_OUT"; then
  step_ok safety
  relay_trust
else
  relay_trust
  step_fail safety safety-layer
  diary_tail "$SAFETY_OUT"
  echo ""
  echo "The safety layer did not install, so the installer has stopped here:"
  echo "a vault without it is not safe to use. The message above says why."
  echo "Once the cause is fixed, run this installer again with the same answers"
  echo "(it will finish the job without touching what is already there), or run"
  echo "the safety step on its own:"
  echo "  python3 \"$PACKAGE_ROOT/safety/install-safety.py\" --vault \"$VAULT_LOCATION\""
  if [[ $TRUST_NEEDED -eq 1 ]]; then
    echo ""
    echo "ChatGPT's delete guard was put in place before the step stopped. One step is"
    echo "yours alone. Until it is done, the delete guard does not run in ChatGPT:"
    print_trust_steps "  "
  fi
  exit 1
fi

# ----- starting memories (v0.5) -----------------------------------------------
step_start skills
python3 "$PACKAGE_ROOT/scripts/seed-memory.py" --vault "$VAULT_LOCATION" --assistant "$ASSISTANT" \
  || { echo "  (starting memories not seeded; harmless, $ASSISTANT_LABEL builds its own)"; diary "    starting memories not seeded (harmless)"; }

# ----- the core skills (v0.6: installed here, no longer a separate step) -----
echo ""
echo "Installing the core skills (brain, capture, interview, PDF, galaxy and more)..."
SKILLS_OUT="$(mktemp)"
if bash "$SCRIPT_DIR/install-skills.sh" --quiet --assistant "$ASSISTANT" 2>&1 | tee "$SKILLS_OUT"; then
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
if [[ "$ASSISTANT" != "chatgpt" ]]; then
  echo "Moblee can also connect your wiki to your Mac's Calendar, Mail and"
  echo "Reminders, Google, GitHub and Chrome, and add tools for videos, documents"
  echo "and editing. Rather than tick through a long list now, the easier way is"
fi
case "$ASSISTANT" in
  chatgpt)
    echo "To begin: open ChatGPT and, from its File menu, choose Open Folder and"
    echo "pick your wiki folder. Make sure Work is chosen at the top of the window,"
    echo "and not Chat, before you type. Then say: get me started"
    echo "ChatGPT asks how you work and what you read, watch and make, and helps"
    echo "you put your first pages in."
    echo ""
    echo "Moblee's optional extras (Calendar, Mail, Google, videos and the rest)"
    echo "are set up for Claude. Moblee does not set them up for ChatGPT yet."
    ;;
  both)
    echo "to open Claude or ChatGPT in your new wiki and say: get me started"
    echo "(for ChatGPT: open ChatGPT and, from its File menu, choose Open Folder and"
    echo "pick your wiki folder; make sure Work is chosen at the top of the window,"
    echo "and not Chat, before you type)."
    echo "It asks how you use your Mac and what you read, watch and make, then"
    echo "suggests only what fits and gives you one command to install it."
    echo "The extras it installs are set up for Claude; Moblee does not set them"
    echo "up for ChatGPT yet."
    ;;
  *)
    echo "to open Claude in your new wiki and say: get me started"
    echo "Claude asks how you use your Mac and what you read, watch and make, then"
    echo "suggests only what fits and gives you one command to install it."
    ;;
esac
echo ""
# (v0.9) the checklist's items are set up for Claude, so it is not offered to
# an owner who uses ChatGPT alone
if [[ -t 0 && "$ASSISTANT" != "chatgpt" ]]; then
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
  # (v0.9) AGENTS.md sits beside CLAUDE.md: whichever of the two exists is
  # staged (-L as well, since AGENTS.md may be a link), and the page the
  # starting memories are written to for ChatGPT goes in with them.
  for p in .claude .gitignore VERSION CLAUDE.md AGENTS.md scripts wiki/Index.md "wiki/Wiki Operations/Moblee Learning Path.md" "wiki/Wiki Operations/Assistant Memory.md"; do
    if [[ -e "$p" || -L "$p" ]]; then git add -A -- "$p" 2>/dev/null || true; fi
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
case "$ASSISTANT" in
  chatgpt)
    echo "  2. To begin: open ChatGPT and, from its File menu, choose Open Folder and"
    echo "     pick your wiki folder. Make sure Work is chosen at the top of the"
    echo "     window, and not Chat, before you type. Then say \"get me started\"."
    echo "     The folder is:"
    echo "       $VAULT_LOCATION"
    ;;
  both)
    echo "  2. Open either assistant in your wiki and say \"get me started\"."
    echo "     Claude:"
    echo "       cd \"$VAULT_LOCATION\""
    echo "       claude"
    echo "     ChatGPT: open ChatGPT and, from its File menu, choose Open Folder and"
    echo "     pick your wiki folder. Make sure Work is chosen at the top of the"
    echo "     window, and not Chat, before you type. The folder is:"
    echo "       $VAULT_LOCATION"
    ;;
  *)
    echo "  2. Open Claude in your wiki and say \"get me started\":"
    echo "       cd \"$VAULT_LOCATION\""
    echo "       claude"
    ;;
esac
echo ""
echo "  3. Whenever you like, from this Moblee folder:"
if [[ "$ASSISTANT" != "chatgpt" ]]; then
  # the checklist's items are set up for Claude, so it is not offered for ChatGPT alone
  echo "       Choose extras yourself:  python3 scripts/moblee-setup.py"
  echo "       Test that it all works:  python3 scripts/moblee-setup.py --check"
else
  echo "       Check-up:   python3 scripts/moblee-doctor.py"
fi
echo "       Dashboard:  python3 \"$VAULT_LOCATION/dashboard/server.py\"   (then open the printed URL)"
echo "       Galaxy:     say \"galaxy\" to $ASSISTANT_LABEL in your vault"
echo ""
if [[ "$ASSISTANT" == "claude" || "$ASSISTANT" == "both" ]]; then
  echo "  Safety: the delete guard is on. Claude cannot delete files in this vault"
  echo "  at all; if something must go, Claude tells you what and you remove it"
  echo "  yourself. Routine work no longer asks permission."
fi
if [[ "$ASSISTANT" == "chatgpt" || "$ASSISTANT" == "both" ]]; then
  if [[ "$ASSISTANT" == "both" ]]; then echo ""; fi
  echo "  Safety in ChatGPT: the delete guard is installed, and ChatGPT runs it only"
  echo "  once you have trusted it and you have proved it. A guard that crashes or"
  echo "  takes too long lets the command through, so the written rule in your wiki"
  echo "  still matters."
  if [[ $TRUST_NEEDED -eq 1 ]]; then
    echo ""
    echo "  One step is yours alone. Until it is done, the delete guard does not run"
    echo "  in ChatGPT:"
    print_trust_steps "    "
    echo ""
  fi
fi
echo "  To update later: download the new Moblee and run  bash scripts/update.sh"
echo ""
