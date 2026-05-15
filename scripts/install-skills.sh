#!/usr/bin/env bash
# install-skills.sh - Copy the bundled Claude skills to ~/.claude/skills/.
#
# Run from the root of the Moblee package:
#
#   bash scripts/install-skills.sh         # safe install, refuses to overwrite
#   bash scripts/install-skills.sh -f      # force, overwrites existing skills
#
# Each skill in skills/<name>/ becomes ~/.claude/skills/<name>/. Claude Code
# and Cowork pick them up automatically at the next session.

set -euo pipefail

# ----- locate the package root ------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SKILLS_SRC="$PACKAGE_ROOT/skills"

if [[ ! -d "$SKILLS_SRC" ]]; then
  echo "Error: skills/ not found at $SKILLS_SRC"
  exit 1
fi

# ----- parse flags ------------------------------------------------------------
FORCE=0
if [[ "${1:-}" == "-f" || "${1:-}" == "--force" ]]; then
  FORCE=1
fi

# ----- destination ------------------------------------------------------------
SKILLS_DST="$HOME/.claude/skills"
mkdir -p "$SKILLS_DST"

echo ""
echo "==================================================================="
echo "  Moblee skills installer"
echo "==================================================================="
echo ""
echo "Source:      $SKILLS_SRC"
echo "Destination: $SKILLS_DST"
echo ""

# ----- copy each skill --------------------------------------------------------
INSTALLED=()
SKIPPED=()

for entry in "$SKILLS_SRC"/*; do
  name="$(basename "$entry")"

  # skip non-directories (README.md at the skills/ root, placeholder file)
  if [[ ! -d "$entry" ]]; then
    continue
  fi

  # skip the placeholder file directory if any future one is added
  if [[ "$name" == *PLACEHOLDER* ]]; then
    SKIPPED+=("$name (placeholder)")
    continue
  fi

  dst="$SKILLS_DST/$name"
  if [[ -d "$dst" && $FORCE -eq 0 ]]; then
    SKIPPED+=("$name (already installed, use -f to overwrite)")
    continue
  fi

  if [[ -d "$dst" && $FORCE -eq 1 ]]; then
    rm -rf "$dst"
  fi

  cp -R "$entry" "$dst"
  INSTALLED+=("$name")
done

# ----- report -----------------------------------------------------------------
echo "Installed:"
if [[ ${#INSTALLED[@]} -eq 0 ]]; then
  echo "  (none)"
else
  for s in "${INSTALLED[@]}"; do
    echo "  - $s"
  done
fi

if [[ ${#SKIPPED[@]} -gt 0 ]]; then
  echo ""
  echo "Skipped:"
  for s in "${SKIPPED[@]}"; do
    echo "  - $s"
  done
fi

# ----- WeasyPrint dependencies (optional) -------------------------------------
echo ""
echo "The \`wiki-to-pdf\` skill needs Python 3 plus WeasyPrint and a few"
echo "system libraries. The bundled SKILL.md describes them in full."
echo ""
read -r -p "Install the WeasyPrint dependencies now? [y/N]: " INSTALL_DEPS
if [[ "$INSTALL_DEPS" =~ ^[Yy]$ ]]; then
  echo ""
  echo "Installing Python packages..."
  pip install --break-system-packages weasyprint markdown jinja2 PyYAML pypdf \
    || echo "  (pip install failed; install manually with the command above)"

  if command -v brew >/dev/null 2>&1; then
    echo ""
    echo "Installing Homebrew dependencies..."
    brew install cairo pango gdk-pixbuf libffi \
      || echo "  (brew install failed; install manually)"
  else
    echo ""
    echo "Homebrew not found. Install it from https://brew.sh, then run:"
    echo "  brew install cairo pango gdk-pixbuf libffi"
  fi
fi

# ----- done -------------------------------------------------------------------
echo ""
echo "==================================================================="
echo "  Done."
echo "==================================================================="
echo ""
echo "Verify the install by running Claude Code in your vault and typing"
echo "\`/skills\` at the prompt. The installed skills should appear in the list."
echo ""
