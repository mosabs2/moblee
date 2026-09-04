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
# This step is entirely optional and only matters for PDF rendering. Skipping it
# is the recommended default: nothing else in the pack depends on it, and Claude
# can set it up on request the first time a PDF is actually wanted.
echo ""
echo "Optional: the \`wiki-to-pdf\` skill renders wiki pages as PDFs. It needs"
echo "WeasyPrint and a few system libraries."
echo ""
echo "You can safely skip this. Nothing else needs it, and you can just ask"
echo "Claude to set it up the first time you want a PDF."
echo ""
read -r -p "Install the PDF dependencies now? (press Return to skip) [y/N]: " INSTALL_DEPS
if [[ "$INSTALL_DEPS" =~ ^[Yy]$ ]]; then
  echo ""
  echo "Installing Python packages..."
  # Stock macOS ships pip3 (/usr/bin/pip3) and no `pip` at all, so resolve the
  # command rather than assuming. Fall back to `python3 -m pip --user`, which
  # works even where neither wrapper is on PATH.
  PIP_CMD=""
  if command -v pip3 >/dev/null 2>&1; then
    PIP_CMD="pip3"
  elif command -v pip >/dev/null 2>&1; then
    PIP_CMD="pip"
  fi

  PIP_OK=0
  if [[ -n "$PIP_CMD" ]]; then
    "$PIP_CMD" install --break-system-packages weasyprint markdown jinja2 PyYAML pypdf && PIP_OK=1
  fi
  if [[ $PIP_OK -eq 0 ]]; then
    python3 -m pip install --user --break-system-packages weasyprint markdown jinja2 PyYAML pypdf && PIP_OK=1
  fi
  if [[ $PIP_OK -eq 0 ]]; then
    echo ""
    echo "  Could not install the Python packages automatically."
    echo "  This is not a problem: everything else is installed and working."
    echo "  Ask Claude to set up WeasyPrint when you first want a PDF."
  fi

  if command -v brew >/dev/null 2>&1; then
    echo ""
    echo "Installing system libraries via Homebrew..."
    brew install cairo pango gdk-pixbuf libffi \
      || echo "  (skipped; ask Claude to finish this when you first want a PDF)"
  else
    echo ""
    echo "System libraries: not installed (Homebrew is not on this Mac)."
    echo "This is fine and expected. Ask Claude to finish the PDF setup when"
    echo "you first want a PDF, and it will handle Homebrew for you."
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
