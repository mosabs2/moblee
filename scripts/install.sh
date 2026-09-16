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
#   6. Optionally appends the `vault` shell function to ~/.zshrc.
#   7. Prints next-step instructions.

set -euo pipefail

# ----- locate the package root ------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VAULT_TEMPLATE="$PACKAGE_ROOT/vault-template"

if [[ ! -d "$VAULT_TEMPLATE" ]]; then
  echo "Error: vault-template/ not found at $VAULT_TEMPLATE"
  echo "Are you running this script from inside the Moblee package?"
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
read -r -p "Your name (used in templates) [Your Name]: " USER_NAME
USER_NAME="${USER_NAME:-[Your Name]}"

read -r -p "Vault name [MyWiki]: " VAULT_NAME
VAULT_NAME="${VAULT_NAME:-MyWiki}"

DEFAULT_LOCATION="$HOME/Wiki/$VAULT_NAME"
read -r -p "Vault location [$DEFAULT_LOCATION]: " VAULT_LOCATION
VAULT_LOCATION="${VAULT_LOCATION:-$DEFAULT_LOCATION}"

# expand a leading ~ if the user typed one
VAULT_LOCATION="${VAULT_LOCATION/#\~/$HOME}"

# ----- an existing Moblee vault at this location is updated, not refused ------
# (v0.5) A vault that already carries a VERSION file, or a CLAUDE.md and wiki/,
# is handed to the updater, which brings it to this version without touching
# its content. This is also the recovery path if a previous install stopped
# part-way (for example at the safety step): run the installer again with the
# same answers and it finishes the job through the updater.
if [[ -f "$VAULT_LOCATION/CLAUDE.md" && -d "$VAULT_LOCATION/wiki" ]]; then
  echo ""
  echo "There is already a Moblee vault at $VAULT_LOCATION."
  echo "Nothing there will be overwritten. Bringing it up to this version instead..."
  exec bash "$SCRIPT_DIR/update.sh" "$VAULT_LOCATION"
fi

# ----- safety: refuse to overwrite --------------------------------------------
if [[ -e "$VAULT_LOCATION" ]]; then
  echo ""
  echo "Error: $VAULT_LOCATION already exists."
  echo "Refusing to overwrite. Pick a different location, or delete the existing"
  echo "directory first if you're sure you want to replace it."
  exit 1
fi

# ----- copy the template ------------------------------------------------------
echo ""
echo "Creating vault at $VAULT_LOCATION..."
mkdir -p "$(dirname "$VAULT_LOCATION")"
cp -R "$VAULT_TEMPLATE" "$VAULT_LOCATION"

# ----- substitute placeholders ------------------------------------------------
echo "Substituting placeholders..."

# Use a portable in-place sed that works on both BSD (macOS default) and GNU.
# We write to a temp file and move it back to avoid sed -i incompatibilities.
TODAY="$(date '+%-d %B %Y')"
substitute_in_file() {
  local file="$1"
  local tmp
  tmp="$(mktemp)"
  sed -e "s|\[Your Name\]|$USER_NAME|g" \
      -e "s|\[Your Vault Name\]|$VAULT_NAME|g" \
      -e "s|\[Your Vault\]|$VAULT_NAME|g" \
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

# ----- copy the vault tooling (v0.4, extended v0.5) ---------------------------
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

# ----- record the vault path for the tooling ----------------------------------
# lint-v2, the gate, the galaxy and the dashboard all find the vault through
# this file (overridable with the MOBLEE_VAULT environment variable).
mkdir -p "$HOME/.config/moblee"
echo "$VAULT_LOCATION" > "$HOME/.config/moblee/vault-path"

# ----- git init ---------------------------------------------------------------
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

# ----- safety layer (v0.5; not optional) --------------------------------------
# The delete guard inspects every shell command Claude composes and refuses
# deletion, history rewriting and force pushes; the permission rules stop the
# constant prompts for routine work. Without this layer the vault is not safe
# to hand to anyone, so a failure here stops the install.
echo ""
echo "Installing the safety layer (delete guard and permission rules)..."
if python3 "$PACKAGE_ROOT/safety/install-safety.py" --vault "$VAULT_LOCATION"; then
  :
else
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
python3 "$PACKAGE_ROOT/scripts/seed-memory.py" --vault "$VAULT_LOCATION" \
  || echo "  (starting memories not seeded; harmless, Claude builds its own)"

# ----- weekly health check on a schedule (v0.5, macOS) ------------------------
if [[ "$(uname)" == "Darwin" && -f "$SCRIPT_DIR/install-schedule.sh" ]]; then
  echo ""
  echo "The weekly health check can run by itself every Saturday morning, so"
  echo "the vault is checked without anyone having to remember."
  read -r -p "Schedule the weekly health check? [Y/n]: " INSTALL_SCHED
  if [[ ! "$INSTALL_SCHED" =~ ^[Nn]$ ]]; then
    bash "$SCRIPT_DIR/install-schedule.sh" \
      || echo "  (schedule not installed; ask Claude to set it up later)"
  fi
fi

# ----- optional: voice stack (macOS) ------------------------------------------
if [[ "$(uname)" == "Darwin" && -f "$PACKAGE_ROOT/voice/install-voice.py" ]]; then
  echo ""
  echo "The voice stack reads Claude's replies aloud and nudges you audibly"
  echo "when Claude is waiting on you. Free (built-in macOS voice), upgradable"
  echo "to ElevenLabs later. See voice/README.md."
  read -r -p "Install the voice stack? [y/N]: " INSTALL_VOICE
  if [[ "$INSTALL_VOICE" =~ ^[Yy]$ ]]; then
    python3 "$PACKAGE_ROOT/voice/install-voice.py" || echo "  (voice install failed; see voice/README.md)"
  fi
fi

# ----- optional: install the vault shell function -----------------------------
echo ""
read -r -p "Append the \`vault\` shell function to ~/.zshrc? [y/N]: " INSTALL_VAULT_FN
if [[ "$INSTALL_VAULT_FN" =~ ^[Yy]$ ]]; then
  # write the configured vault path to ~/.config/moblee/vault-path so vault.sh
  # picks it up
  mkdir -p "$HOME/.config/moblee"
  echo "$VAULT_LOCATION" > "$HOME/.config/moblee/vault-path"

  # append vault.sh contents to ~/.zshrc, with a guard so re-running the
  # installer does not duplicate the function
  if ! grep -q "# >>> moblee vault function >>>" "$HOME/.zshrc" 2>/dev/null; then
    {
      echo ""
      echo "# >>> moblee vault function >>>"
      cat "$SCRIPT_DIR/vault.sh"
      echo "# <<< moblee vault function <<<"
    } >> "$HOME/.zshrc"
    echo "  Appended to ~/.zshrc. Open a new Terminal or run \`source ~/.zshrc\`."
  else
    echo "  Already present in ~/.zshrc, skipped."
  fi
fi

# ----- commit the settings the install wrote (v0.5) ---------------------------
# The initial commit happened before the safety step; the permission rules and
# the ignore file it added are committed now, so the vault starts clean.
(
  cd "$VAULT_LOCATION"
  git add -A .claude .gitignore VERSION 2>/dev/null || true
  if ! git diff --cached --quiet 2>/dev/null; then
    git commit --quiet -m "moblee: safety layer and settings" 2>/dev/null || true
  fi
)

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
echo "  1. Install the bundled skills:"
echo "       bash scripts/install-skills.sh"
echo ""
echo "  2. Open Obsidian, choose \"Open folder as vault\", and point it at:"
echo "       $VAULT_LOCATION"
echo ""
echo "  3. Open the vault's Welcome.md and follow it from there. Or paste"
echo "     START_HERE.md into Claude and let it walk you through."
echo ""
echo "  4. Optional extras, whenever you like:"
echo "       Dashboard:  python3 \"$VAULT_LOCATION/dashboard/server.py\"   (then open the printed URL)"
echo "       Galaxy:     say \"galaxy\" to Claude in your vault"
echo "       Health check: runs by itself on Saturdays if you scheduled it; or ask Claude to \"run the lint\""
echo ""
echo "  Safety: the delete guard is on. Claude cannot delete files in this vault"
echo "  at all; if something must go, Claude tells you what and you remove it"
echo "  yourself. Routine work no longer asks permission."
echo "  To update later: download the new Moblee and run  bash scripts/update.sh"
echo ""
