#!/usr/bin/env bash
# install-skills.sh - Copy the bundled skills to ~/.claude/skills/ (Claude),
# ~/.agents/skills/ (ChatGPT), or both.
#
# Run from the root of the Moblee package:
#
#   bash scripts/install-skills.sh         # safe install, refuses to overwrite
#   bash scripts/install-skills.sh -f      # replace existing skills (old copies are kept)
#   bash scripts/install-skills.sh --update  # same as -f, and skips the PDF question
#   bash scripts/install-skills.sh --quiet   # safe install, no header, no PDF question
#                                            # (the installer uses this; PDF is on the checklist)
#
# Any of these also takes  --assistant claude|chatgpt|both  (anywhere on the
# line). Without it the choice is the one word kept in
# ~/.config/moblee/assistant, and claude when there is no such file.
#
# Each skill in skills/<name>/ becomes ~/.claude/skills/<name>/ for Claude
# (Claude Code and Cowork pick them up automatically at the next session) and
# ~/.agents/skills/<name>/ for ChatGPT. Nothing is ever deleted: a skill being
# replaced is moved to ~/.config/moblee/backups/<stamp>/.

set -euo pipefail

# ----- locate the package root ------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SKILLS_SRC="$PACKAGE_ROOT/skills"

if [[ ! -d "$SKILLS_SRC" ]]; then
  echo "Error: skills/ not found at $SKILLS_SRC"
  exit 1
fi

# ----- which assistant --------------------------------------------------------
# --assistant <value> is taken out of the arguments first, wherever it sits, so
# the flags below are read exactly as they always were.
ASSISTANT=""
ASSISTANT_GIVEN=0
REST=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --assistant)
      if [[ $# -lt 2 ]]; then
        echo "--assistant needs a value: claude, chatgpt or both."
        exit 2
      fi
      ASSISTANT="$2"
      ASSISTANT_GIVEN=1
      shift 2
      ;;
    --assistant=*)
      ASSISTANT="${1#--assistant=}"
      ASSISTANT_GIVEN=1
      shift
      ;;
    *)
      REST+=("$1")
      shift
      ;;
  esac
done
set -- ${REST[@]+"${REST[@]}"}

if [[ $ASSISTANT_GIVEN -eq 0 ]]; then
  # the owner's choice, kept as one word by the installer; no file means claude
  CHOICE_FILE="$HOME/.config/moblee/assistant"
  # read as the installer and the updater read it: the first line, spaces
  # dropped, and the word exactly as they write it (small letters); anything
  # else counts as no choice
  if [[ -f "$CHOICE_FILE" ]]; then
    ASSISTANT="$(head -1 "$CHOICE_FILE" 2>/dev/null | tr -d '[:space:]' || true)"
  fi
else
  ASSISTANT="$(printf '%s' "$ASSISTANT" | tr '[:upper:]' '[:lower:]')"
fi
case "$ASSISTANT" in
  claude|chatgpt|both) ;;
  *)
    if [[ $ASSISTANT_GIVEN -eq 1 ]]; then
      echo "The assistant must be one of claude, chatgpt or both; \"$ASSISTANT\" is not one of them."
      exit 2
    fi
    ASSISTANT="claude"
    ;;
esac

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
BACKUP_ROOT="$HOME/.config/moblee/backups/$(date '+%Y%m%d-%H%M%S')"

# ----- destinations -----------------------------------------------------------
# One entry per assistant wanted, in three lists that run side by side (bash 3.2
# has no associative arrays). Each destination keeps its old copies in a folder
# of its own, so the same skill replaced in both places is kept twice, not
# moved one inside the other.
DEST_NAMES=()
DEST_DIRS=()
DEST_BACKUPS=()
DEST_KINDS=()
if [[ "$ASSISTANT" == "claude" || "$ASSISTANT" == "both" ]]; then
  DEST_NAMES+=("Claude")
  DEST_DIRS+=("$HOME/.claude/skills")
  DEST_BACKUPS+=("$BACKUP_ROOT/skills")
  DEST_KINDS+=("claude")
fi
if [[ "$ASSISTANT" == "chatgpt" || "$ASSISTANT" == "both" ]]; then
  DEST_NAMES+=("ChatGPT")
  DEST_DIRS+=("$HOME/.agents/skills")
  DEST_BACKUPS+=("$BACKUP_ROOT/skills-chatgpt")
  DEST_KINDS+=("chatgpt")
fi
# The names Moblee has itself put into ~/.agents/skills, one to a line. That
# folder is shared with other tools, so only a skill named here is ever moved
# aside to make way for a newer copy; see install_into below.
AGENTS_RECORD="$HOME/.config/moblee/skills-chatgpt"
ours_in_agents() {
  [[ -f "$AGENTS_RECORD" ]] && grep -qxF -- "$1" "$AGENTS_RECORD" 2>/dev/null
}
record_in_agents() {
  if ! ours_in_agents "$1"; then
    mkdir -p "$HOME/.config/moblee"
    echo "$1" >> "$AGENTS_RECORD" 2>/dev/null || true
  fi
}
case "$ASSISTANT" in
  claude)  WHO="Claude" ;;
  chatgpt) WHO="ChatGPT" ;;
  *)       WHO="Claude or ChatGPT" ;;
esac

for d in "${DEST_DIRS[@]}"; do
  mkdir -p "$d"
done

if [[ $UPDATE -eq 0 && $QUIET -eq 0 ]]; then
  echo ""
  echo "==================================================================="
  echo "  Moblee skills installer"
  echo "==================================================================="
  echo ""
  echo "Source:      $SKILLS_SRC"
  for d in "${DEST_DIRS[@]}"; do
    echo "Destination: $d"
  done
  echo ""
fi

# ----- one destination: copy each skill, then report --------------------------
# Reads SKILLS_DST and BACKUP_DIR. Sets ANY_DIFFERENT when a skill was left out.
ANY_DIFFERENT=0

install_into() {
  # ----- copy each skill ------------------------------------------------------
  INSTALLED=()
  SKIPPED=()
  SAME=()
  DIFFERENT=()
  KEPT=0

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
    # (v0.9) ~/.agents/skills is shared with other tools, and Moblee put nothing
    # there before 0.9. A skill of the same name found there that is not this
    # Moblee's copy is replaced on --update only if it is known to be Moblee's:
    # a record of the names Moblee has installed there is kept beside the
    # choice (~/.config/moblee/skills-chatgpt). Anything else is left alone and
    # reported, as the safe install has always done.
    if [[ -d "$dst" && $FORCE -eq 1 && "$DEST_KIND" == "chatgpt" ]] && ! ours_in_agents "$name" \
       && ! diff -rq -x .DS_Store "$entry" "$dst" >/dev/null 2>&1; then
      SKIPPED+=("$name (a different skill of this name is already installed; it was left alone)")
      DIFFERENT+=("$name")
      continue
    fi
    if [[ -d "$dst" && $FORCE -eq 0 ]]; then
      if diff -rq -x .DS_Store "$entry" "$dst" >/dev/null 2>&1; then
        SAME+=("$name")          # this Moblee's own copy is already there: nothing to do
        if [[ "$DEST_KIND" == "chatgpt" ]]; then record_in_agents "$name"; fi
      else
        # A different skill already has this name: an older Moblee's copy, or
        # something of the owner's own. It is left exactly as it is, and that is
        # said out loud, because Moblee does not work without its own skills.
        SKIPPED+=("$name (a different skill of this name is already installed; it was left alone)")
        DIFFERENT+=("$name")
      fi
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
    if [[ "$DEST_KIND" == "chatgpt" ]]; then record_in_agents "$name"; fi
  done

  # ----- skills that have been renamed or folded into another -----------------
  # Left in place, an old skill would answer to the same phrases as its successor.
  # Once the successor is installed, the old copy is moved to the backups folder
  # (never deleted). "old:new" pairs. For Claude's folder only: the old skills
  # were only ever installed there, so one of the same name in the folder
  # ChatGPT shares with other tools is somebody else's and is left alone.
  for pair in "get-started:companion"; do
    old="${pair%%:*}"; new="${pair##*:}"
    if [[ "$DEST_KIND" == "claude" && -d "$SKILLS_DST/$old" && -d "$SKILLS_DST/$new" ]]; then
      mkdir -p "$BACKUP_DIR"
      mv "$SKILLS_DST/$old" "$BACKUP_DIR/$old"
      KEPT=1
      echo "The \`$old\` skill is now part of \`$new\`; the old copy was moved aside."
    fi
  done
  if [[ $KEPT -eq 1 ]]; then
    echo "Previous copies kept at ${BACKUP_DIR/#$HOME/~}"
  fi

  # ----- report ---------------------------------------------------------------
  echo "Installed:"
  if [[ ${#INSTALLED[@]} -eq 0 ]]; then
    echo "  (none)"
  else
    for s in "${INSTALLED[@]}"; do
      echo "  - $s"
    done
  fi

  if [[ ${#SAME[@]} -gt 0 ]]; then
    echo "Already in place: ${SAME[*]}"
  fi

  if [[ ${#SKIPPED[@]} -gt 0 ]]; then
    echo ""
    echo "Skipped:"
    for s in "${SKIPPED[@]}"; do
      echo "  - $s"
    done
  fi

  if [[ ${#DIFFERENT[@]} -gt 0 && "$DEST_KIND" == "chatgpt" ]]; then
    echo ""
    echo "Moblee's own copy of these skills was NOT installed for ChatGPT, because a"
    echo "different skill already has the name in ~/.agents/skills, a folder other"
    echo "tools share: ${DIFFERENT[*]}"
    echo "Nothing of yours was touched. To use Moblee's copy, move yours out of that"
    echo "folder yourself and run this again."
    if [[ $FORCE -eq 0 ]]; then
      echo "(A copy that an earlier Moblee put there itself is replaced, and kept in the"
      echo "backups folder, by:  bash scripts/install-skills.sh --update)"
      ANY_DIFFERENT=1
    fi
    # On --update this is said and the run carries on: the updater must reach
    # the safety layer, and the check-up names the skills that are missing.
  elif [[ ${#DIFFERENT[@]} -gt 0 ]]; then
    echo ""
    echo "Moblee's own copy of these skills was NOT installed, because a different"
    echo "skill already has the name: ${DIFFERENT[*]}"
    echo "Nothing of yours was touched. To put Moblee's copies in (yours are moved to"
    echo "the backups folder, never deleted), run:  bash scripts/install-skills.sh --update"
    ANY_DIFFERENT=1
  fi
}

# ----- every destination in turn ----------------------------------------------
# With two destinations each report is headed by the assistant it is for; with
# one, the output is what it has always been. A skill left out of either one
# still ends the run with exit 3, after both have been attempted.
i=0
while [[ $i -lt ${#DEST_DIRS[@]} ]]; do
  SKILLS_DST="${DEST_DIRS[$i]}"
  BACKUP_DIR="${DEST_BACKUPS[$i]}"
  DEST_KIND="${DEST_KINDS[$i]}"
  if [[ ${#DEST_DIRS[@]} -gt 1 ]]; then
    if [[ $i -gt 0 ]]; then
      echo ""
    fi
    echo "Skills for ${DEST_NAMES[$i]}:"
  fi
  install_into
  i=$((i + 1))
done

if [[ $ANY_DIFFERENT -eq 1 ]]; then
  exit 3
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
echo "$WHO to set it up the first time you want a PDF."
echo ""
read -r -p "Install the PDF dependencies now? (press Return to skip) [y/N]: " INSTALL_DEPS
if [[ "$INSTALL_DEPS" =~ ^[Yy]$ ]]; then
  # The Python packages are useless without the system libraries underneath
  # them, so Homebrew decides whether this step can run at all. Checking it
  # first means a Mac without Homebrew skips cleanly instead of failing twice
  # on its way to the same answer.
  # The log stays where it has always been for an owner of Claude. An owner of
  # ChatGPT alone has no ~/.claude folder and is not given one: theirs goes
  # beside Moblee's other records.
  if [[ "$ASSISTANT" == "chatgpt" ]]; then
    DEPS_LOG="$HOME/.config/moblee/moblee-pdf-setup.log"
    mkdir -p "$HOME/.config/moblee"
  else
    DEPS_LOG="$HOME/.claude/moblee-pdf-setup.log"
    mkdir -p "$HOME/.claude"
  fi

  if ! command -v brew >/dev/null 2>&1; then
    echo ""
    echo "PDF setup needs Homebrew, which is not on this Mac yet, so this step"
    echo "is being skipped. Nothing else is affected, and the rest of the"
    echo "install is complete. The first time you want a PDF, ask $WHO to set"
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
      echo "  problem: everything else is installed and working. Ask $WHO to"
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
if [[ "$ASSISTANT" == "claude" || "$ASSISTANT" == "both" ]]; then
  echo "Verify the install by running Claude Code in your vault and typing"
  echo "\`/skills\` at the prompt. The installed skills should appear in the list."
fi
if [[ "$ASSISTANT" == "both" ]]; then
  echo ""
fi
if [[ "$ASSISTANT" == "chatgpt" || "$ASSISTANT" == "both" ]]; then
  echo "For ChatGPT: open ChatGPT, choose Work, and open your wiki folder. Then type \`@\` in the message box."
  echo "The installed skills should appear in the list. If they do not, quit"
  echo "ChatGPT and open it again."
fi
echo ""
