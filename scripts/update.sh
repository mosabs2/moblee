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
#   9. Writes the new VERSION and commits the update in the vault.
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
bash "$SCRIPT_DIR/install-skills.sh" --update | sed 's/^/   /'

# ----- 5. safety --------------------------------------------------------------
echo "4. Safety layer"
if ! python3 "$PACKAGE_ROOT/safety/install-safety.py" --vault "$VAULT" | sed 's/^/   /'; then
  echo ""
  echo "The safety layer did not install; stopping so nothing else changes."
  echo "The message above says why. Fix it and run the updater again."
  exit 1
fi

# ----- 6. CLAUDE.md -----------------------------------------------------------
echo "5. CLAUDE.md"
python3 "$SCRIPT_DIR/patch-claude-md.py" --vault "$VAULT" | sed 's/^/   /'

# ----- 7. identity and memories ----------------------------------------------
echo "6. Identity file and starting memories"
if [[ ! -f "$VAULT/wiki/Identity.md" ]]; then
  # The owner's name: from the vault's git identity (set by the v0.4.2+ installer),
  # else from the sentence the template CLAUDE.md carries, else left for the
  # first conversation to fill.
  OWNER="$(cd "$VAULT" && git config user.name 2>/dev/null || true)"
  if [[ -z "$OWNER" ]]; then
    OWNER="$(sed -n 's/.*knowledge base for \(.*\) where Claude is the maintainer.*/\1/p' "$VAULT/CLAUDE.md" | head -1)"
  fi
  OWNER="${OWNER:-[Your Name]}"
  TODAY="$(date '+%-d %B %Y')"
  sed -e "s|\[Your Name\]|$OWNER|g" -e "s|\[Install date\]|$TODAY|g" \
      "$PACKAGE_ROOT/vault-template/wiki/Identity.md" > "$VAULT/wiki/Identity.md"
  echo "   added wiki/Identity.md (the owner's own asks are filled in conversation)"
else
  echo "   wiki/Identity.md already present; left as it is"
fi
python3 "$SCRIPT_DIR/seed-memory.py" --vault "$VAULT" | sed 's/^/   /' \
  || echo "   (starting memories not seeded; harmless)"

# ----- 8. schedule ------------------------------------------------------------
echo "7. Weekly health check"
if [[ "$(uname)" == "Darwin" && -f "$SCRIPT_DIR/install-schedule.sh" ]]; then
  if [[ -f "$HOME/Library/LaunchAgents/com.moblee.weekly-lint.plist" ]]; then
    bash "$SCRIPT_DIR/install-schedule.sh" | sed 's/^/   /' || true
  else
    read -r -p "   Schedule the weekly health check to run every Saturday? [Y/n]: " INSTALL_SCHED
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

# ----- 9. version and commit --------------------------------------------------
echo "8. Version and commit"
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
    git add -A -- scripts dashboard VERSION CLAUDE.md .gitignore .claude wiki/Identity.md 2>/dev/null || true
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
echo "Next time you open Claude Code in the vault, say: orient"
echo ""
