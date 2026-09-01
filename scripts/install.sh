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
substitute_in_file() {
  local file="$1"
  local tmp
  tmp="$(mktemp)"
  sed -e "s|\[Your Name\]|$USER_NAME|g" \
      -e "s|\[Your Vault Name\]|$VAULT_NAME|g" \
      -e "s|\[Your Vault\]|$VAULT_NAME|g" \
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

# ----- copy the vault tooling (v0.4) ------------------------------------------
echo "Copying vault tooling (lint, commit gate, preflight, galaxy, dashboard)..."
mkdir -p "$VAULT_LOCATION/scripts"
for tool in lint-v2.py vault-gate.py vault-orient-preflight.sh; do
  if [[ -f "$SCRIPT_DIR/$tool" ]]; then
    cp "$SCRIPT_DIR/$tool" "$VAULT_LOCATION/scripts/$tool"
  fi
done
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
  git add . >/dev/null
  git commit --quiet -m "initial vault from Moblee starter pack" \
    || echo "  (git commit skipped, configure user.name and user.email first)"
)

# ----- install the commit gate as a pre-commit hook ---------------------------
if [[ -f "$VAULT_LOCATION/scripts/vault-gate.py" && -d "$VAULT_LOCATION/.git" ]]; then
  {
    echo '#!/bin/sh'
    echo 'exec python3 "$(git rev-parse --show-toplevel)/scripts/vault-gate.py"'
  } > "$VAULT_LOCATION/.git/hooks/pre-commit"
  chmod +x "$VAULT_LOCATION/.git/hooks/pre-commit"
  echo "Commit gate installed (.git/hooks/pre-commit)."
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
echo "       Galaxy:     python3 \"$VAULT_LOCATION/scripts/wiki-galaxy/build.py\""
echo "       Weekly health check: ask Claude to \"run the lint\""
echo ""
