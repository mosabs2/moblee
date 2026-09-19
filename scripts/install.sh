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
# the vault's VERSION always comes from the pack, so the template's copy cannot drift
if [[ -f "$PACKAGE_ROOT/VERSION" ]]; then cp "$PACKAGE_ROOT/VERSION" "$VAULT_LOCATION/VERSION"; fi

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
# and the pack's own folder, so the owner's Claude can point back at the checklist
echo "$PACKAGE_ROOT" > "$HOME/.config/moblee/package-path"

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

# ----- the core skills (v0.6: installed here, no longer a separate step) -----
echo ""
echo "Installing the core skills (brain, capture, interview, PDF, galaxy and more)..."
bash "$SCRIPT_DIR/install-skills.sh" --quiet \
  || echo "  (core skills not fully installed; run  bash scripts/install-skills.sh  later)"

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
