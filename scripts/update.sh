#!/usr/bin/env bash
# update.sh - Bring an existing Moblee vault up to this version of the pack.
#
# Run from the root of a freshly downloaded Moblee package:
#
#   bash scripts/update.sh                 # vault from ~/.config/moblee/vault-path
#   bash scripts/update.sh ~/Wiki/MyWiki   # or name the vault
#   bash scripts/update.sh --assistant both   # (v0.9) change which assistant the wiki is for
#
# The assistant (claude, chatgpt or both) is read from ~/.config/moblee/assistant;
# no file means claude. --assistant changes it, and the instruction file follows
# by renaming or linking only: CLAUDE.md is what Claude reads, AGENTS.md what
# ChatGPT reads, and for both AGENTS.md is a link to CLAUDE.md. For Claude the
# skills go to ~/.claude/skills/ and for ChatGPT to ~/.agents/skills/; where the
# steps below say CLAUDE.md they mean whichever of the two is the real file.
#
# What it does, in order. Nothing in the vault's own content (wiki/, raw/,
# Clippings/, Daily Notes/, the log) is touched, and nothing is deleted:
# every file that is replaced is first copied to ~/.config/moblee/backups/<stamp>/.
#
#   1. Checks the folder is a vault and reads its current version.
#   2. Replaces the vault tooling in scripts/ and dashboard/ with the new copies.
#   3. Points git at scripts/hooks/ (the commit gate), moving any old
#      .git/hooks/pre-commit aside so only one gate runs.
#   4. Replaces the bundled skills in ~/.claude/skills/ (old copies kept).
#   5. Installs the safety layer: delete guard, hook registration, permission rules.
#   6. Adds the new rules and sections to CLAUDE.md without replacing the file.
#   7. Adds wiki/Identity.md if the vault has none, the starting memories, and
#      (v0.7) the Habits and Tools page the companion's first conversation fills in.
#   8. Offers the weekly health-check schedule (Mac).
#   9. Offers the optional learning path (refreshes it if already added).
#  10. Writes the new VERSION and commits the update in the vault.
#
# Safe to run twice: every step checks what is already there.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
NEW_VERSION="$(cat "$PACKAGE_ROOT/VERSION" 2>/dev/null || echo unknown)"
STAMP="$(date '+%Y%m%d-%H%M%S')"
BACKUP="$HOME/.config/moblee/backups/$STAMP"

# ----- progress lines for the Moblee app (--progress, anywhere on the line) ----
# (v0.9) and --assistant <value>, likewise anywhere on the line
PROGRESS=0
ARG_ASSISTANT=""; ASSISTANT_FLAG=0; TAKE_ASSISTANT=0
ARGS=()
for a in "$@"; do
  if [[ $TAKE_ASSISTANT -eq 1 ]]; then ARG_ASSISTANT="$a"; TAKE_ASSISTANT=0
  elif [[ "$a" == "--progress" ]]; then PROGRESS=1
  elif [[ "$a" == "--assistant" ]]; then ASSISTANT_FLAG=1; TAKE_ASSISTANT=1
  else ARGS+=("$a"); fi
done
set -- ${ARGS[@]+"${ARGS[@]}"}
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
USTEP=""; USTEP_N=0; USTEP_TOTAL=9
emit() {
  [[ $PROGRESS -eq 1 ]] || return 0
  printf '@@moblee {"step":"%s","state":"%s","n":%d,"of":%d}\n' "$1" "$2" "$USTEP_N" "$USTEP_TOTAL"
}
emit_trust() {
  # (v0.9) not one of the nine steps, so it carries no count: ChatGPT will not
  # run the delete guard until its owner trusts the hook in ChatGPT's settings
  [[ $PROGRESS -eq 1 ]] || return 0
  printf '@@moblee {"step":"trust","state":"needed","assistant":"chatgpt"}\n'
}
# The same plain diary the installer keeps (~/.config/moblee/install-diary.txt):
# no names, the home folder written as "~". It is what the app shows, and what
# the check-up reads, when an update stops part-way.
DIARY="$HOME/.config/moblee/install-diary.txt"
mkdir -p "$HOME/.config/moblee"
diary() {
  local line="$*"
  if [[ -n "${VAULT:-}" ]]; then
    line="${line//\/private$VAULT/<wiki>}"
    line="${line//$VAULT/<wiki>}"
    line="${line//$(basename "$VAULT")/<wiki>}"
  fi
  line="${line//\/private$HOME/~}"
  line="${line//$HOME/~}"
  printf '%s  %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$line" >> "$DIARY" 2>/dev/null || true
}
ustep() {
  # closes the step before, opens the next
  if [[ -n "$USTEP" ]]; then emit "$USTEP" ok; diary "update step $USTEP_N of $USTEP_TOTAL, $USTEP: done"; fi
  USTEP="$1"; USTEP_N=$((USTEP_N+1)); emit "$USTEP" start
  diary "update step $USTEP_N of $USTEP_TOTAL, $USTEP: started"
}
on_exit() {
  local code=$?
  if [[ $code -ne 0 ]]; then
    diary "the update stopped during \"${USTEP:-starting}\" with exit code $code; the wiki's own pages were not touched"
    if [[ -n "$USTEP" ]]; then emit "$USTEP" fail; emit "$USTEP" stopped; fi
  fi
}
trap on_exit EXIT

# ----- find the vault ---------------------------------------------------------
VAULT="${1:-}"
if [[ -z "$VAULT" && -n "${MOBLEE_VAULT:-}" ]]; then
  VAULT="$MOBLEE_VAULT"
fi
if [[ -z "$VAULT" && -f "$HOME/.config/moblee/vault-path" ]]; then
  VAULT="$(cat "$HOME/.config/moblee/vault-path")"
fi
VAULT="${VAULT/#\~/$HOME}"
# (v0.9) a wiki made for ChatGPT alone carries AGENTS.md in place of CLAUDE.md
if [[ -z "$VAULT" || ! -d "$VAULT/wiki" ]] || [[ ! -f "$VAULT/CLAUDE.md" && ! -f "$VAULT/AGENTS.md" ]]; then
  echo "Could not find the vault. Run: bash scripts/update.sh <path to your vault>"
  exit 1
fi
OLD_VERSION="$(cat "$VAULT/VERSION" 2>/dev/null || echo 'before 0.5')"
printf '\n' >> "$DIARY" 2>/dev/null || true
diary "=== Moblee update begins ==="
diary "from version $OLD_VERSION to $NEW_VERSION; macOS $(sw_vers -productVersion 2>/dev/null || echo unknown), chip $(uname -m); started from $([[ $PROGRESS -eq 1 ]] && echo 'the app' || echo 'Terminal')"

# ----- which assistant the wiki is for (v0.9) ---------------------------------
# One word in ~/.config/moblee/assistant; no file means claude. --assistant
# changes it, and the file is written before any step runs, so every program
# called below, given the option or reading the file, sees the same choice.
ASSISTANT_FILE="$HOME/.config/moblee/assistant"
OLD_ASSISTANT=""
if [[ -f "$ASSISTANT_FILE" ]]; then
  OLD_ASSISTANT="$(head -1 "$ASSISTANT_FILE" 2>/dev/null | tr -d '[:space:]' || true)"
fi
case "$OLD_ASSISTANT" in
  claude|chatgpt|both) ;;
  *) OLD_ASSISTANT="claude" ;;
esac
ASSISTANT="$OLD_ASSISTANT"
if [[ $ASSISTANT_FLAG -eq 1 ]]; then
  ASSISTANT="$ARG_ASSISTANT"
  echo "$ASSISTANT" > "$ASSISTANT_FILE"
fi
diary "assistant: $ASSISTANT"
if [[ "$ASSISTANT" != "$OLD_ASSISTANT" ]]; then
  diary "    the assistant was changed on this run, from $OLD_ASSISTANT to $ASSISTANT"
fi
# how the assistant is named in the sentences below
case "$ASSISTANT" in
  chatgpt) ASSISTANT_LABEL="ChatGPT" ;;
  both)    ASSISTANT_LABEL="your assistant" ;;
  *)       ASSISTANT_LABEL="Claude" ;;
esac
# The vault's instruction file: CLAUDE.md if it is a regular file, else
# AGENTS.md if it is a regular file, else CLAUDE.md. A link is never the answer.
instruction_name() {
  if [[ -f "$VAULT/CLAUDE.md" && ! -L "$VAULT/CLAUDE.md" ]]; then echo "CLAUDE.md"
  elif [[ -f "$VAULT/AGENTS.md" && ! -L "$VAULT/AGENTS.md" ]]; then echo "AGENTS.md"
  else echo "CLAUDE.md"; fi
}
INSTR_NAME="$(instruction_name)"

echo ""
echo "==================================================================="
echo "  Moblee updater"
echo "==================================================================="
echo ""
echo "Vault:            $VAULT"
echo "Current version:  $OLD_VERSION"
echo "Updating to:      $NEW_VERSION"
echo "Backups go to:    $BACKUP"
if [[ "$ASSISTANT" != "claude" || $ASSISTANT_FLAG -eq 1 ]]; then
  case "$ASSISTANT" in
    chatgpt) echo "Assistant:        ChatGPT" ;;
    both)    echo "Assistant:        Claude and ChatGPT" ;;
    *)       echo "Assistant:        Claude" ;;
  esac
fi
echo ""

keep_copy() {
  # keep_copy <path inside vault or home> : copy to the backup folder, keeping the relative name
  local src="$1"
  if [[ -e "$src" ]]; then
    local rel="${src#$VAULT/}"
    rel="${rel#$HOME/}"
    mkdir -p "$BACKUP/$(dirname "$rel")"
    cp -R "$src" "$BACKUP/$rel"
  fi
}

# ----- 2. tooling --------------------------------------------------------------
ustep tools
echo "1. Vault tooling"
mkdir -p "$VAULT/scripts"
for tool in lint-v2.py vault-gate.py vault-orient-preflight.sh log-append.py; do
  if [[ -f "$SCRIPT_DIR/$tool" ]]; then
    if [[ -f "$VAULT/scripts/$tool" ]] && ! cmp -s "$SCRIPT_DIR/$tool" "$VAULT/scripts/$tool"; then
      keep_copy "$VAULT/scripts/$tool"
      echo "   replaced scripts/$tool (old copy kept)"
    elif [[ ! -f "$VAULT/scripts/$tool" ]]; then
      echo "   added scripts/$tool"
    else
      continue   # identical already: not rewritten, so its date does not suggest a change that did not happen
    fi
    cp "$SCRIPT_DIR/$tool" "$VAULT/scripts/$tool"
  fi
done
for dir in hooks wiki-galaxy; do
  if [[ -d "$SCRIPT_DIR/$dir" ]]; then
    if [[ -d "$VAULT/scripts/$dir" ]]; then
      if diff -rq -x __pycache__ "$SCRIPT_DIR/$dir" "$VAULT/scripts/$dir" >/dev/null 2>&1; then
        continue
      fi
      keep_copy "$VAULT/scripts/$dir"
      echo "   refreshed scripts/$dir (old copy kept)"
    else
      echo "   added scripts/$dir"
    fi
    mkdir -p "$VAULT/scripts/$dir"
    cp -R "$SCRIPT_DIR/$dir/." "$VAULT/scripts/$dir/"
  fi
done
chmod +x "$VAULT"/scripts/hooks/* 2>/dev/null || true
if [[ -d "$PACKAGE_ROOT/dashboard" ]]; then
  if [[ -d "$VAULT/dashboard" ]] && diff -rq -x __pycache__ "$PACKAGE_ROOT/dashboard" "$VAULT/dashboard" >/dev/null 2>&1; then
    :
  else
    if [[ -d "$VAULT/dashboard" ]]; then
      keep_copy "$VAULT/dashboard"
      echo "   refreshed dashboard/ (old copy kept)"
    else
      echo "   added dashboard/"
    fi
    mkdir -p "$VAULT/dashboard"
    cp -R "$PACKAGE_ROOT/dashboard/." "$VAULT/dashboard/"
  fi
fi
mkdir -p "$HOME/.config/moblee"
echo "$VAULT" > "$HOME/.config/moblee/vault-path"

# ----- 3. git hooks -----------------------------------------------------------
ustep gate
echo "2. Commit gate"
if [[ -d "$VAULT/.git" ]]; then
  if [[ -d "$VAULT/scripts/hooks" ]]; then
    ( cd "$VAULT" && git config core.hooksPath scripts/hooks )
    echo "   git now runs the gate from scripts/hooks/"
    if [[ -f "$VAULT/.git/hooks/pre-commit" ]]; then
      keep_copy "$VAULT/.git/hooks/pre-commit"
      mv "$VAULT/.git/hooks/pre-commit" "$VAULT/.git/hooks/pre-commit.before-$STAMP"
      echo "   the older gate in .git/hooks/ moved aside so only one runs"
    fi
  fi
else
  echo "   this vault is not under git; skipped (ask $ASSISTANT_LABEL to set git up)"
fi

# ----- the instruction file follows the choice (v0.9) -------------------------
# Not a step of its own (the count of steps is what the app shows), and placed
# here so that the rename's commit passes through the gate just brought up to
# date. Claude reads CLAUDE.md and ChatGPT reads AGENTS.md. A change of choice
# renames or links and does nothing else; nothing is ever deleted:
#   claude to both    AGENTS.md is added as a relative link to CLAUDE.md
#   chatgpt to both   AGENTS.md is renamed to CLAUDE.md (git mv, so its history
#                     goes with it), then the link is added
#   both to claude    the link is left where it is, harmless, and that is said
# The changes the list does not name go the same way, towards the one layout
# that serves either assistant: a wiki made for ChatGPT that is now for Claude
# is renamed and linked as above, and a wiki made for Claude that is now for
# ChatGPT gains the link. A wiki already laid out for both is left as it is.
instr_real()   { [[ -f "$VAULT/$1" && ! -L "$VAULT/$1" ]]; }
instr_absent() { [[ ! -e "$VAULT/$1" && ! -L "$VAULT/$1" ]]; }
rename_agents_to_claude() {
  keep_copy "$VAULT/AGENTS.md"
  if [[ -d "$VAULT/.git" ]] && git -C "$VAULT" ls-files --error-unmatch -- AGENTS.md >/dev/null 2>&1; then
    if ! git -C "$VAULT" mv -- AGENTS.md CLAUDE.md; then
      echo "   (AGENTS.md could not be renamed to CLAUDE.md; nothing was changed. The message above says why.)"
      return 1
    fi
    # The rename is committed by itself, naming only these two paths, so that
    # the file's history follows it plainly and none of the owner's other
    # staged work is swept in. If the commit does not go through, the rename
    # stays staged and goes into the updater's own commit at the end.
    if git -C "$VAULT" commit --quiet -m "moblee: AGENTS.md renamed to CLAUDE.md, so that Claude and ChatGPT read one file" -- AGENTS.md CLAUDE.md >/dev/null 2>&1; then
      echo "   AGENTS.md renamed to CLAUDE.md (its history goes with it; committed)"
    else
      echo "   AGENTS.md renamed to CLAUDE.md (its history goes with it; committed with the update below)"
    fi
  else
    if ! mv "$VAULT/AGENTS.md" "$VAULT/CLAUDE.md"; then
      echo "   (AGENTS.md could not be renamed to CLAUDE.md; nothing was changed. The message above says why.)"
      return 1
    fi
    echo "   AGENTS.md renamed to CLAUDE.md"
  fi
  diary "    the instruction file AGENTS.md was renamed to CLAUDE.md (old copy kept)"
}
link_agents_to_claude() {
  if ( cd "$VAULT" && ln -s CLAUDE.md AGENTS.md ); then
    echo "   AGENTS.md added as a link to CLAUDE.md, so ChatGPT reads the same instructions as Claude"
    diary "    AGENTS.md was added as a link to CLAUDE.md"
  else
    echo "   (the link from AGENTS.md to CLAUDE.md could not be made; run the updater again later)"
  fi
}
if instr_real AGENTS.md && instr_absent CLAUDE.md; then
  # made for ChatGPT alone
  if [[ "$ASSISTANT" == "claude" || "$ASSISTANT" == "both" ]]; then
    if rename_agents_to_claude; then link_agents_to_claude; fi
  fi
elif instr_real CLAUDE.md && instr_absent AGENTS.md; then
  # made for Claude alone
  if [[ "$ASSISTANT" == "chatgpt" || "$ASSISTANT" == "both" ]]; then
    link_agents_to_claude
  fi
elif instr_real CLAUDE.md && [[ -L "$VAULT/AGENTS.md" ]]; then
  # already laid out for both
  if [[ "$ASSISTANT" == "claude" && "$OLD_ASSISTANT" != "claude" ]]; then
    echo "   AGENTS.md stays where it is, as a link to CLAUDE.md. It does no harm, and nothing is removed."
    diary "    the assistant is now claude; the AGENTS.md link was left in place"
  fi
elif instr_real CLAUDE.md && instr_real AGENTS.md; then
  if [[ "$ASSISTANT" != "claude" ]]; then
    echo "   CLAUDE.md and AGENTS.md are separate files in this wiki, so both were left as they are."
    echo "   ChatGPT reads AGENTS.md and Moblee keeps CLAUDE.md up to date."
    diary "    CLAUDE.md and AGENTS.md are separate files here; both left as they are"
  fi
fi
INSTR_NAME="$(instruction_name)"

# ----- 4. skills --------------------------------------------------------------
ustep skills
echo "3. Skills"
if ! bash "$SCRIPT_DIR/install-skills.sh" --update --assistant "$ASSISTANT" | sed 's/^/   /'; then
  echo ""
  echo "The skills did not update, so the updater stopped here. The vault tooling"
  echo "and the commit gate are already updated (old copies in $BACKUP)."
  echo "The message above says why. Fix it and run the updater again; it is safe to repeat."
  exit 1
fi

# ----- 5. safety --------------------------------------------------------------
ustep safety
echo "4. Safety layer"
# (v0.9) what the safety installer printed is kept as well as shown, since it
# says on a line of its own when ChatGPT's guard waits for the owner's trust
SAFETY_OUT="$(mktemp)"
TRUST_NEEDED=0
if ! python3 "$PACKAGE_ROOT/safety/install-safety.py" --vault "$VAULT" --assistant "$ASSISTANT" | tee "$SAFETY_OUT" | sed 's/^/   /'; then
  echo ""
  echo "The safety layer did not install, so the updater stopped here."
  echo "Steps 1 to 3 have already run: the vault tooling, the commit gate and the"
  echo "skills are updated, with the old copies in $BACKUP."
  echo "$INSTR_NAME, the identity file, the schedules and VERSION are unchanged."
  echo "The message above says why. Fix it and run the updater again; it is safe"
  echo "to repeat and carries on from here."
  exit 1
fi
# ChatGPT runs a hook only once its owner has trusted it, and only the owner can
# do that. It is passed on at once, so it is not lost if a later step stops (a
# second run would not say it again), and spelled out in the closing summary.
if grep -q '^@@moblee-trust-needed chatgpt' "$SAFETY_OUT"; then
  TRUST_NEEDED=1
  diary "    ChatGPT's delete guard is in place and waits for the owner to trust it in ChatGPT's settings"
  emit_trust
fi

# ----- 6. CLAUDE.md (AGENTS.md in a wiki made for ChatGPT alone) --------------
ustep rules
echo "5. $INSTR_NAME"
if ! python3 "$SCRIPT_DIR/patch-claude-md.py" --vault "$VAULT" --assistant "$ASSISTANT" | sed 's/^/   /'; then
  echo ""
  echo "$INSTR_NAME could not be brought up to date, so the updater stopped here."
  echo "The tooling, commit gate, skills and safety layer are already updated."
  echo "The message above says why. Fix it and run the updater again; it is safe to repeat."
  exit 1
fi

# ----- 7. identity and memories ----------------------------------------------
ustep pages
echo "6. Identity file and starting memories"
# The owner's name comes from the vault's git identity, else from the sentence
# the template CLAUDE.md carries, else is left for the opening conversation.
# Written by a script that creates the file only if absent (never overwrites).
python3 "$SCRIPT_DIR/add-identity.py" --vault "$VAULT" --assistant "$ASSISTANT" | sed 's/^/   /' \
  || echo "   (Identity.md not added; ask $ASSISTANT_LABEL to create it from the template)"
python3 "$SCRIPT_DIR/seed-memory.py" --vault "$VAULT" --assistant "$ASSISTANT" | sed 's/^/   /' \
  || echo "   (starting memories not seeded; harmless)"
python3 "$SCRIPT_DIR/add-habits-page.py" --vault "$VAULT" | sed 's/^/   /' \
  || echo "   (Habits and Tools page not added; ask $ASSISTANT_LABEL to create it from the template)"
# A wiki made before 0.8.1 still has a first log entry headed "YYYY-MM-DD".
# It is dated from the wiki's first commit; a line already written over is left
# alone. Each of the three pages that had no uncommitted work of the owner's
# before this goes into the updater's own commit, with the correction named in
# the commit message and the diary, since the log is otherwise append-only. A
# page the owner was in the middle of changing is dated too, but left for their
# own next commit with the rest of their work.
STAMP_CLEAN=()
if [[ -d "$VAULT/.git" ]]; then
  for p in wiki/log.md wiki/_context.md wiki/Index.md; do
    if git -C "$VAULT" diff --quiet -- "$p" 2>/dev/null && git -C "$VAULT" diff --cached --quiet -- "$p" 2>/dev/null; then
      STAMP_CLEAN+=("$p")
    fi
  done
fi
STAMP_OUT="$(python3 "$SCRIPT_DIR/stamp-starter-dates.py" --vault "$VAULT" --from-history 2>&1 || true)"
if [[ -z "$STAMP_OUT" ]]; then STAMP_OUT="(the dates on the starter pages were left as they are; harmless)"; fi
echo "   $STAMP_OUT"
STAMP_NOTE=""
if [[ "$STAMP_OUT" == dated:* ]]; then
  STAMP_NOTE="; the starter pages' placeholder dates filled in from the wiki's first commit"
  diary "the starter pages' placeholder dates were filled in (${STAMP_OUT#dated: }), from the wiki's first commit"
fi
# so the owner's Claude can point back at the checklist in this folder
mkdir -p "$HOME/.config/moblee"
echo "$PACKAGE_ROOT" > "$HOME/.config/moblee/package-path"
# Vaults from before v0.4 have no Daily Notes layer; the brain skill's daily
# patterns need the template. Added only when absent; nothing is overwritten.
if [[ ! -f "$VAULT/Daily Notes/_TEMPLATE.md" && -f "$PACKAGE_ROOT/vault-template/Daily Notes/_TEMPLATE.md" ]]; then
  mkdir -p "$VAULT/Daily Notes"
  cp "$PACKAGE_ROOT/vault-template/Daily Notes/_TEMPLATE.md" "$VAULT/Daily Notes/_TEMPLATE.md"
  echo "   added Daily Notes/_TEMPLATE.md (the brain skill's daily patterns need it)"
fi

# ----- 8. schedule ------------------------------------------------------------
ustep weekly
echo "7. Weekly health check"
if [[ "$(uname)" == "Darwin" && -f "$SCRIPT_DIR/install-schedule.sh" ]]; then
  if [[ -f "$HOME/Library/LaunchAgents/com.moblee.weekly-lint.plist" ]]; then
    bash "$SCRIPT_DIR/install-schedule.sh" | sed 's/^/   /' || true
  elif [[ ! -t 0 ]]; then
    # no Terminal to ask in (for example, run by Claude for a clinic note): never
    # schedule unasked, and never stop the updater on an unanswerable question
    echo "   not scheduled (no Terminal to ask in); run bash \"$SCRIPT_DIR/install-schedule.sh\" to add it"
  else
    read -r -p "   Schedule the weekly health check to run every Saturday? [Y/n]: " INSTALL_SCHED || INSTALL_SCHED="n"  # no answer (end of input): never schedule unasked, never stop
    if [[ ! "$INSTALL_SCHED" =~ ^[Nn]$ ]]; then
      bash "$SCRIPT_DIR/install-schedule.sh" | sed 's/^/   /' \
        || echo "   (schedule not installed; ask $ASSISTANT_LABEL to set it up later)"
    else
      echo "   skipped; ask $ASSISTANT_LABEL to set it up whenever you like"
    fi
  fi
else
  echo "   not available on this system; skipped"
fi

# ----- 9. learning path (optional, v0.5.1) ------------------------------------
ustep lessons
echo "8. Learning path"
if [[ -f "$VAULT/wiki/Wiki Operations/Moblee Learning Path.md" ]]; then
  # already chosen: refresh the reminder script and make sure the rule is present;
  # the lessons page and its Progress list are never replaced
  if [[ -f "$HOME/Library/LaunchAgents/com.moblee.nightly-tip.plist" ]]; then
    python3 "$SCRIPT_DIR/install-learning-path.py" --vault "$VAULT" --assistant "$ASSISTANT" | sed 's/^/   /' || true
  else
    python3 "$SCRIPT_DIR/install-learning-path.py" --vault "$VAULT" --assistant "$ASSISTANT" --no-reminder | sed 's/^/   /' || true
  fi
elif [[ -t 0 ]]; then
  echo "   Thirty-two short lessons on getting the most from this wiki, one an evening,"
  echo "   with a reminder at 9 pm on a Mac."
  read -r -p "   Add the learning path? [y/N]: " INSTALL_LESSONS || INSTALL_LESSONS=""  # no answer: skip, and carry on
  if [[ "$INSTALL_LESSONS" =~ ^[Yy]$ ]]; then
    python3 "$SCRIPT_DIR/install-learning-path.py" --vault "$VAULT" --assistant "$ASSISTANT" | sed 's/^/   /' \
      || echo "   (not fully added; run the updater again later)"
  else
    echo "   skipped; add it any time with: python3 \"$SCRIPT_DIR/install-learning-path.py\" --vault \"$VAULT\""
  fi
else
  echo "   not added (the updater was not run in a Terminal window that can ask);"
  echo "   add it any time with: python3 \"$SCRIPT_DIR/install-learning-path.py\" --vault \"$VAULT\""
fi

# ----- 10. version and commit -------------------------------------------------
ustep finish
echo "9. Version and commit"
echo "$NEW_VERSION" > "$VAULT/VERSION"
if [[ ! -f "$VAULT/.gitignore" && -f "$PACKAGE_ROOT/vault-template/.gitignore" ]]; then
  cp "$PACKAGE_ROOT/vault-template/.gitignore" "$VAULT/.gitignore"
  echo "   added .gitignore (keeps reports, editor state and caches out of git)"
fi
if [[ -d "$VAULT/.git" ]]; then
  (
    cd "$VAULT"
    # Only what the update touched is committed; the owner's own uncommitted
    # work stays uncommitted, for them and their Claude to commit as they see fit.
    # One path per git add: a single missing path makes git stage nothing at all.
    # wiki/Index.md is left out on purpose, since it may hold the owner's own
    # uncommitted edits; a learning-path line added there is committed with them.
    # (v0.9) AGENTS.md sits beside CLAUDE.md: whichever of the two exists is
    # staged (-L as well, since AGENTS.md may be a link), and so is the page
    # the starting memories are written to for ChatGPT.
    for p in scripts dashboard VERSION CLAUDE.md AGENTS.md .gitignore .claude wiki/Identity.md "wiki/Wiki Operations/Moblee Learning Path.md" "wiki/Wiki Operations/Habits and Tools.md" "wiki/Wiki Operations/Assistant Memory.md"; do
      # in a wiki for Claude alone, an AGENTS.md that is a file of its own is the
      # owner's, kept for some other tool, and is left for them to commit
      if [[ "$p" == "AGENTS.md" && "$ASSISTANT" == "claude" && ! -L "$p" ]]; then continue; fi
      if [[ -e "$p" || -L "$p" ]]; then git add -A -- "$p" 2>/dev/null || true; fi
    done
    # the starter pages the updater dated, where the owner had no uncommitted work of their own
    for p in ${STAMP_CLEAN[@]+"${STAMP_CLEAN[@]}"}; do
      if [[ -e "$p" ]]; then git add -- "$p" 2>/dev/null || true; fi
    done
    if git diff --cached --quiet; then
      if [[ "$OLD_VERSION" == "$NEW_VERSION" ]]; then
        echo "   already at $NEW_VERSION; nothing to change"
      else
        echo "   nothing new to commit"
      fi
    else
      git commit --quiet -m "moblee: updated from $OLD_VERSION to $NEW_VERSION$STAMP_NOTE" \
        && echo "   committed: moblee: updated from $OLD_VERSION to $NEW_VERSION" \
        || echo "   (commit did not go through; ask $ASSISTANT_LABEL to commit the update)"
    fi
  )
fi

if [[ -n "$USTEP" ]]; then emit "$USTEP" ok; diary "update step $USTEP_N of $USTEP_TOTAL, $USTEP: done"; USTEP=""; fi
diary "=== Moblee update finished ==="
if [[ $PROGRESS -eq 1 ]]; then
  printf '@@moblee {"step":"done","state":"ok","n":%d,"of":%d}\n' "$USTEP_TOTAL" "$USTEP_TOTAL"
fi

echo ""
echo "==================================================================="
echo "  Updated to $NEW_VERSION."
echo "==================================================================="
echo ""
echo "Your wiki's content was not touched. Replaced files were kept at:"
echo "  $BACKUP"
echo ""
# ----- the step only the owner can take (v0.9) --------------------------------
if [[ $TRUST_NEEDED -eq 1 ]]; then
  echo "One step is yours alone. Until it is done, the delete guard does not run"
  echo "in ChatGPT:"
  echo "  1. In ChatGPT, open the ChatGPT menu and choose Settings."
  echo "  2. Choose Hooks (under Coding) and open \"User config\"."
  echo "  3. Press Trust beside the hook whose command ends bash-guard.py."
  echo "  4. Turn its switch on."
  echo "ChatGPT asks for this again whenever Moblee updates the guard."
  echo ""
fi
# ----- the checklist (v0.6; from v0.7 nothing is ticked in advance) ----------
# The usual way to choose extras is now the "get me started" conversation with
# Claude in the vault, which asks how the owner works and gives them a command
# that opens the checklist with the fitting items ticked. It can still be
# opened here by owners who would rather choose alone.
if [[ -f "$SCRIPT_DIR/moblee-setup.py" ]]; then
  case "$ASSISTANT" in
    chatgpt)
      echo "To carry on: open ChatGPT, choose Work, add your wiki folder as a project"
      echo "if it is not there yet, and say: get me started (if you have never done it)."
      echo "Moblee's optional extras (Calendar, Mail, Google, videos and the rest) are"
      echo "set up for Claude. Moblee does not set them up for ChatGPT yet."
      ;;
    both)
      echo "New in this version: your assistant can suggest which extras suit you. Open"
      echo "Claude or ChatGPT in your wiki (in ChatGPT, choose Work and add your wiki"
      echo "folder as a project if it is not there yet) and say: review my setup (or,"
      echo "if you have never done it, get me started). It asks how you use your Mac,"
      echo "suggests only what fits and gives you one command to install it."
      echo "The extras it installs are set up for Claude; Moblee does not set them"
      echo "up for ChatGPT yet."
      ;;
    *)
      echo "New in this version: Claude can suggest which extras suit you. Open Claude"
      echo "in your wiki and say: review my setup (or, if you have never done it,"
      echo "get me started). It asks how you use your Mac, suggests only what fits"
      echo "and gives you one command to install it."
      ;;
  esac
  if [[ -t 0 ]]; then
    read -r -p "Would you rather choose from the full checklist yourself now? [y/N]: " OPEN_SETUP || OPEN_SETUP="n"  # no answer: do not open
    if [[ "$OPEN_SETUP" =~ ^[Yy]$ ]]; then
      MOBLEE_VAULT="$VAULT" python3 "$SCRIPT_DIR/moblee-setup.py" \
        || echo "  (the checklist stopped early; run it again to carry on)"
    fi
  fi
  echo ""
fi

case "$ASSISTANT" in
  chatgpt) echo "Next time you open your wiki in ChatGPT, say: orient" ;;
  both)    echo "Next time you open Claude Code or ChatGPT in the vault, say: orient" ;;
  *)       echo "Next time you open Claude Code in the vault, say: orient" ;;
esac
echo ""
