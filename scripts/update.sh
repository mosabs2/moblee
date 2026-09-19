#!/usr/bin/env bash
# update.sh - Bring an existing Moblee vault up to this version of the pack.
#
# Run from the root of a freshly downloaded Moblee package:
#
#   bash scripts/update.sh                 # vault from ~/.config/moblee/vault-path
#   bash scripts/update.sh ~/Wiki/MyWiki   # or name the vault
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
#   7. Adds wiki/Identity.md if the vault has none, and the starting memories.
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

# ----- find the vault ---------------------------------------------------------
VAULT="${1:-}"
if [[ -z "$VAULT" && -n "${MOBLEE_VAULT:-}" ]]; then
  VAULT="$MOBLEE_VAULT"
fi
if [[ -z "$VAULT" && -f "$HOME/.config/moblee/vault-path" ]]; then
  VAULT="$(cat "$HOME/.config/moblee/vault-path")"
fi
VAULT="${VAULT/#\~/$HOME}"
if [[ -z "$VAULT" || ! -f "$VAULT/CLAUDE.md" || ! -d "$VAULT/wiki" ]]; then
  echo "Could not find the vault. Run: bash scripts/update.sh <path to your vault>"
  exit 1
fi
OLD_VERSION="$(cat "$VAULT/VERSION" 2>/dev/null || echo 'before 0.5')"

echo ""
echo "==================================================================="
echo "  Moblee updater"
echo "==================================================================="
echo ""
echo "Vault:            $VAULT"
echo "Current version:  $OLD_VERSION"
echo "Updating to:      $NEW_VERSION"
echo "Backups go to:    $BACKUP"
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
echo "1. Vault tooling"
mkdir -p "$VAULT/scripts"
for tool in lint-v2.py vault-gate.py vault-orient-preflight.sh log-append.py; do
  if [[ -f "$SCRIPT_DIR/$tool" ]]; then
    if [[ -f "$VAULT/scripts/$tool" ]] && ! cmp -s "$SCRIPT_DIR/$tool" "$VAULT/scripts/$tool"; then
      keep_copy "$VAULT/scripts/$tool"
      echo "   replaced scripts/$tool (old copy kept)"
    elif [[ ! -f "$VAULT/scripts/$tool" ]]; then
      echo "   added scripts/$tool"
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
  echo "   this vault is not under git; skipped (ask Claude to set git up)"
fi

# ----- 4. skills --------------------------------------------------------------
echo "3. Skills"
if ! bash "$SCRIPT_DIR/install-skills.sh" --update | sed 's/^/   /'; then
  echo ""
  echo "The skills did not update, so the updater stopped here. The vault tooling"
  echo "and the commit gate are already updated (old copies in $BACKUP)."
  echo "The message above says why. Fix it and run the updater again; it is safe to repeat."
  exit 1
fi

# ----- 5. safety --------------------------------------------------------------
echo "4. Safety layer"
if ! python3 "$PACKAGE_ROOT/safety/install-safety.py" --vault "$VAULT" | sed 's/^/   /'; then
  echo ""
  echo "The safety layer did not install, so the updater stopped here."
  echo "Steps 1 to 3 have already run: the vault tooling, the commit gate and the"
  echo "skills are updated, with the old copies in $BACKUP."
  echo "CLAUDE.md, the identity file, the schedules and VERSION are unchanged."
  echo "The message above says why. Fix it and run the updater again; it is safe"
  echo "to repeat and carries on from here."
  exit 1
fi

# ----- 6. CLAUDE.md -----------------------------------------------------------
echo "5. CLAUDE.md"
if ! python3 "$SCRIPT_DIR/patch-claude-md.py" --vault "$VAULT" | sed 's/^/   /'; then
  echo ""
  echo "CLAUDE.md could not be brought up to date, so the updater stopped here."
  echo "The tooling, commit gate, skills and safety layer are already updated."
  echo "The message above says why. Fix it and run the updater again; it is safe to repeat."
  exit 1
fi

# ----- 7. identity and memories ----------------------------------------------
echo "6. Identity file and starting memories"
# The owner's name comes from the vault's git identity, else from the sentence
# the template CLAUDE.md carries, else is left for the opening conversation.
# Written by a script that creates the file only if absent (never overwrites).
python3 "$SCRIPT_DIR/add-identity.py" --vault "$VAULT" | sed 's/^/   /' \
  || echo "   (Identity.md not added; ask Claude to create it from the template)"
python3 "$SCRIPT_DIR/seed-memory.py" --vault "$VAULT" | sed 's/^/   /' \
  || echo "   (starting memories not seeded; harmless)"
# Vaults from before v0.4 have no Daily Notes layer; the brain skill's daily
# patterns need the template. Added only when absent; nothing is overwritten.
if [[ ! -f "$VAULT/Daily Notes/_TEMPLATE.md" && -f "$PACKAGE_ROOT/vault-template/Daily Notes/_TEMPLATE.md" ]]; then
  mkdir -p "$VAULT/Daily Notes"
  cp "$PACKAGE_ROOT/vault-template/Daily Notes/_TEMPLATE.md" "$VAULT/Daily Notes/_TEMPLATE.md"
  echo "   added Daily Notes/_TEMPLATE.md (the brain skill's daily patterns need it)"
fi

# ----- 8. schedule ------------------------------------------------------------
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
        || echo "   (schedule not installed; ask Claude to set it up later)"
    else
      echo "   skipped; ask Claude to set it up whenever you like"
    fi
  fi
else
  echo "   not available on this system; skipped"
fi

# ----- 9. learning path (optional, v0.5.1) ------------------------------------
echo "8. Learning path"
if [[ -f "$VAULT/wiki/Wiki Operations/Moblee Learning Path.md" ]]; then
  # already chosen: refresh the reminder script and make sure the rule is present;
  # the lessons page and its Progress list are never replaced
  if [[ -f "$HOME/Library/LaunchAgents/com.moblee.nightly-tip.plist" ]]; then
    python3 "$SCRIPT_DIR/install-learning-path.py" --vault "$VAULT" | sed 's/^/   /' || true
  else
    python3 "$SCRIPT_DIR/install-learning-path.py" --vault "$VAULT" --no-reminder | sed 's/^/   /' || true
  fi
elif [[ -t 0 ]]; then
  echo "   Thirty-two short lessons on getting the most from this wiki, one an evening,"
  echo "   with a reminder at 9 pm on a Mac."
  read -r -p "   Add the learning path? [y/N]: " INSTALL_LESSONS || INSTALL_LESSONS=""  # no answer: skip, and carry on
  if [[ "$INSTALL_LESSONS" =~ ^[Yy]$ ]]; then
    python3 "$SCRIPT_DIR/install-learning-path.py" --vault "$VAULT" | sed 's/^/   /' \
      || echo "   (not fully added; run the updater again later)"
  else
    echo "   skipped; add it any time with: python3 \"$SCRIPT_DIR/install-learning-path.py\" --vault \"$VAULT\""
  fi
else
  echo "   not added (the updater was not run in a Terminal window that can ask);"
  echo "   add it any time with: python3 \"$SCRIPT_DIR/install-learning-path.py\" --vault \"$VAULT\""
fi

# ----- 10. version and commit -------------------------------------------------
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
    for p in scripts dashboard VERSION CLAUDE.md .gitignore .claude wiki/Identity.md "wiki/Wiki Operations/Moblee Learning Path.md"; do
      if [[ -e "$p" ]]; then git add -A -- "$p" 2>/dev/null || true; fi
    done
    if git diff --cached --quiet; then
      if [[ "$OLD_VERSION" == "$NEW_VERSION" ]]; then
        echo "   already at $NEW_VERSION; nothing to change"
      else
        echo "   nothing new to commit"
      fi
    else
      git commit --quiet -m "moblee: updated from $OLD_VERSION to $NEW_VERSION" \
        && echo "   committed: moblee: updated from $OLD_VERSION to $NEW_VERSION" \
        || echo "   (commit did not go through; ask Claude to commit the update)"
    fi
  )
fi

echo ""
echo "==================================================================="
echo "  Updated to $NEW_VERSION."
echo "==================================================================="
echo ""
echo "Your wiki's content was not touched. Replaced files were kept at:"
echo "  $BACKUP"
echo ""
# ----- the checklist (v0.6) -----------------------------------------------------
# Existing vaults get the same checklist a new install shows: the Mac's own
# apps, Google, GitHub, Chrome, video, documents, editing tools, the news brief
# and the paid extras. Items already working are marked and left alone.
if [[ -f "$SCRIPT_DIR/moblee-setup.py" ]]; then
  echo "New in this version: a checklist that connects your wiki to your Mac's"
  echo "Calendar, Mail and Reminders, Google, GitHub, Chrome, videos, documents"
  echo "and editing tools. It says the time, space and any cost before anything"
  echo "starts, and it can be run any time with: python3 scripts/moblee-setup.py"
  if [[ -t 0 ]]; then
    read -r -p "Open the checklist now? [Y/n]: " OPEN_SETUP || OPEN_SETUP="n"  # no answer: do not open
    if [[ ! "$OPEN_SETUP" =~ ^[Nn]$ ]]; then
      MOBLEE_VAULT="$VAULT" python3 "$SCRIPT_DIR/moblee-setup.py" \
        || echo "  (the checklist stopped early; run it again to carry on)"
    fi
  fi
  echo ""
fi

echo "Next time you open Claude Code in the vault, say: orient"
echo ""
