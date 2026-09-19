#!/usr/bin/env bash
# install-skills.sh - Copy the bundled Claude skills to ~/.claude/skills/.
#
# Run from the root of the Moblee package:
#
#   bash scripts/install-skills.sh         # safe install, refuses to overwrite
#   bash scripts/install-skills.sh -f      # replace existing skills (old copies are kept)
#   bash scripts/install-skills.sh --update  # same as -f, and skips the PDF question
#   bash scripts/install-skills.sh --quiet   # safe install, no header, no PDF question
#                                            # (the installer uses this; PDF is on the checklist)
#
# Each skill in skills/<name>/ becomes ~/.claude/skills/<name>/. Claude Code
# and Cowork pick them up automatically at the next session. Nothing is ever
# deleted: a skill being replaced is moved to ~/.config/moblee/backups/<stamp>/.

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
UPDATE=0
if [[ "${1:-}" == "-f" || "${1:-}" == "--force" ]]; then
  FORCE=1
fi
if [[ "${1:-}" == "--update" ]]; then
  FORCE=1
  UPDATE=1
fi
QUIET=0
if [[ "${1:-}" == "--quiet" ]]; then
  QUIET=1
fi
BACKUP_DIR="$HOME/.config/moblee/backups/$(date '+%Y%m%d-%H%M%S')/skills"

# ----- destination ------------------------------------------------------------
SKILLS_DST="$HOME/.claude/skills"
mkdir -p "$SKILLS_DST"

if [[ $UPDATE -eq 0 && $QUIET -eq 0 ]]; then
  echo ""
  echo "==================================================================="
  echo "  Moblee skills installer"
  echo "==================================================================="
  echo ""
  echo "Source:      $SKILLS_SRC"
  echo "Destination: $SKILLS_DST"
  echo ""
fi

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
    # Never delete: the previous copy is moved aside, so it can be put back.
    mkdir -p "$BACKUP_DIR"
    mv "$dst" "$BACKUP_DIR/$name"
    KEPT=1
  fi

  cp -R "$entry" "$dst"
  INSTALLED+=("$name")
done

# ----- skills that have been renamed or folded into another -------------------
# Left in place, an old skill would answer to the same phrases as its successor.
# Once the successor is installed, the old copy is moved to the backups folder
# (never deleted). "old:new" pairs.
for pair in "get-started:companion"; do
  old="${pair%%:*}"; new="${pair##*:}"
  if [[ -d "$SKILLS_DST/$old" && -d "$SKILLS_DST/$new" ]]; then
    mkdir -p "$BACKUP_DIR"
    mv "$SKILLS_DST/$old" "$BACKUP_DIR/$old"
    KEPT=1
    echo "The \`$old\` skill is now part of \`$new\`; the old copy was moved aside."
  fi
done
if [[ "${KEPT:-0}" -eq 1 ]]; then
  echo "Previous copies kept at ${BACKUP_DIR/#$HOME/~}"
fi

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
if [[ $UPDATE -eq 1 || $QUIET -eq 1 ]]; then
  exit 0
fi
echo ""
echo "Optional: the \`wiki-to-pdf\` skill renders wiki pages as PDFs. It needs"
echo "WeasyPrint and a few system libraries."
echo ""
echo "You can safely skip this. Nothing else needs it, and you can just ask"
echo "Claude to set it up the first time you want a PDF."
echo ""
read -r -p "Install the PDF dependencies now? (press Return to skip) [y/N]: " INSTALL_DEPS
if [[ "$INSTALL_DEPS" =~ ^[Yy]$ ]]; then
  # The Python packages are useless without the system libraries underneath
  # them, so Homebrew decides whether this step can run at all. Checking it
  # first means a Mac without Homebrew skips cleanly instead of failing twice
  # on its way to the same answer.
  DEPS_LOG="$HOME/.claude/moblee-pdf-setup.log"

  if ! command -v brew >/dev/null 2>&1; then
    echo ""
    echo "PDF setup needs Homebrew, which is not on this Mac yet, so this step"
    echo "is being skipped. Nothing else is affected, and the rest of the"
    echo "install is complete. The first time you want a PDF, ask Claude to set"
    echo "it up and it will install what is needed for you."
  else
    echo ""
    echo "Installing the system libraries (this can take a few minutes)..."
    if brew install cairo pango gdk-pixbuf libffi >>"$DEPS_LOG" 2>&1; then
      echo "  System libraries installed."
    else
      echo "  System libraries did not install. Details: $DEPS_LOG"
    fi

    echo "Installing the Python packages..."
    # Stock macOS ships pip3 (/usr/bin/pip3) and no `pip` at all, so resolve
    # the command rather than assuming.
    PIP_CMD=""
    if command -v pip3 >/dev/null 2>&1; then
      PIP_CMD="pip3"
    elif command -v pip >/dev/null 2>&1; then
      PIP_CMD="pip"
    fi

    # --break-system-packages arrived in pip 23.0. Stock macOS ships pip
    # 21.2.4, where passing an unknown option aborts with a usage dump, so
    # probe for the flag rather than assuming it exists.
    BSP=""
    if [[ -n "$PIP_CMD" ]] && "$PIP_CMD" install --help 2>/dev/null | grep -q -- "--break-system-packages"; then
      BSP="--break-system-packages"
    fi

    PIP_OK=0
    if [[ -n "$PIP_CMD" ]]; then
      "$PIP_CMD" install --user $BSP weasyprint markdown jinja2 PyYAML pypdf >>"$DEPS_LOG" 2>&1 && PIP_OK=1
    fi
    if [[ $PIP_OK -eq 0 ]]; then
      python3 -m pip install --user $BSP weasyprint markdown jinja2 PyYAML pypdf >>"$DEPS_LOG" 2>&1 && PIP_OK=1
    fi

    if [[ $PIP_OK -eq 1 ]]; then
      echo "  Python packages installed. PDF rendering is ready."
    else
      echo ""
      echo "  The Python packages did not install this time, which is not a"
      echo "  problem: everything else is installed and working. Ask Claude to"
      echo "  finish the PDF setup the first time you want a PDF."
      echo "  Details, if they are ever wanted: $DEPS_LOG"
    fi
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
