#!/usr/bin/env bash
# moblee-prepare-and-init.sh
#
# One-shot finaliser for the Moblee starter pack. Run this once on the Mac mini
# after Phase 2D, from anywhere (Terminal will resolve paths via $BASH_SOURCE).
#
# Usage:
#   bash /Users/[YourUser]/Wiki/[Your Vault]/outputs/moblee/moblee-prepare-and-init.sh
# or from inside the moblee directory:
#   bash moblee-prepare-and-init.sh
#
# What it does:
#   1. Detects its own location (works whether invoked by absolute path or
#      from inside outputs/moblee/).
#   2. Refuses to overwrite an existing .git/ directory.
#   3. Runs a pre-flight check that the key files are present.
#   4. git init, git add ., git commit with a multi-line message.
#   5. Prints next-step guidance for either GitHub push or AirDrop zip.

set -euo pipefail

# ----- locate ourselves -------------------------------------------------------
SCRIPT_PATH="${BASH_SOURCE[0]}"
SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_PATH")" && pwd)"
PACKAGE_ROOT="$SCRIPT_DIR"

# ----- colour helpers ---------------------------------------------------------
if command -v tput >/dev/null 2>&1 && [[ -t 1 ]]; then
  BOLD="$(tput bold)"
  DIM="$(tput dim)"
  GREEN="$(tput setaf 2)"
  YELLOW="$(tput setaf 3)"
  RED="$(tput setaf 1)"
  BLUE="$(tput setaf 4)"
  RESET="$(tput sgr0)"
else
  BOLD=""; DIM=""; GREEN=""; YELLOW=""; RED=""; BLUE=""; RESET=""
fi

banner() {
  echo ""
  echo "${BOLD}${BLUE}==================================================================="
  echo "  $1"
  echo "===================================================================${RESET}"
  echo ""
}

step()    { echo "${BOLD}${BLUE}>>${RESET} $1"; }
ok()      { echo "${GREEN}OK${RESET}  $1"; }
warn()    { echo "${YELLOW}!!${RESET}  $1"; }
fail()    { echo "${RED}xx${RESET}  $1" >&2; }

abort() {
  fail "$1"
  echo ""
  fail "Aborting. No changes have been committed."
  exit 1
}

# ----- enter the package root -------------------------------------------------
cd "$PACKAGE_ROOT"

banner "Moblee: prepare and init"
echo "Package root: ${DIM}$PACKAGE_ROOT${RESET}"
echo ""

# ----- safety: refuse to overwrite an existing repo ---------------------------
if [[ -d "$PACKAGE_ROOT/.git" ]]; then
  fail "$PACKAGE_ROOT/.git already exists."
  echo "    This package looks like it has already been initialised as a git repo."
  echo "    If you want to start over, delete the .git/ directory manually first:"
  echo "      rm -rf \"$PACKAGE_ROOT/.git\""
  echo "    Then re-run this script."
  exit 1
fi

# ----- pre-flight check -------------------------------------------------------
step "Pre-flight check: verifying key files are present..."

REQUIRED_FILES=(
  "README.md"
  "START_HERE.md"
  "LICENSE"
  ".gitignore"
  "scripts/install.sh"
  "scripts/install-skills.sh"
  "scripts/vault.sh"
  "vault-template/CLAUDE.md"
  "skills/brain/SKILL.md"
  "skills/wiki-capture/SKILL.md"
  "skills/wiki-to-pdf/SKILL.md"
  "skills/wiki-interview/SKILL.md"
  "skills/design-your-brand/SKILL.md"
)

MISSING=0
for f in "${REQUIRED_FILES[@]}"; do
  if [[ ! -f "$PACKAGE_ROOT/$f" ]]; then
    fail "missing: $f"
    MISSING=$((MISSING + 1))
  fi
done

if (( MISSING > 0 )); then
  abort "$MISSING required file(s) missing. Cannot initialise the repo."
fi

ok "all required files present (${#REQUIRED_FILES[@]} checked)"
echo ""

# ----- verify git is available ------------------------------------------------
if ! command -v git >/dev/null 2>&1; then
  abort "git is not installed or not on PATH. Install Xcode Command Line Tools first: xcode-select --install"
fi
ok "git found: $(git --version)"
echo ""

# ----- announce ---------------------------------------------------------------
banner "Initialising Moblee starter pack as a git repo..."

# ----- git init ---------------------------------------------------------------
step "git init"
git init --quiet --initial-branch=main 2>/dev/null || git init --quiet
ok "initialised"

# ----- git add ----------------------------------------------------------------
step "git add . (respects .gitignore, so .discarded/ is excluded)"
git add .
STAGED_COUNT=$(git diff --cached --numstat | wc -l | tr -d ' ')
ok "staged $STAGED_COUNT file(s)"

# ----- check author identity --------------------------------------------------
if ! git config user.name >/dev/null 2>&1 || ! git config user.email >/dev/null 2>&1; then
  warn "git author identity not set globally."
  warn "Setting a local identity for this repo only:"
  git config user.name "Moblee Starter"
  git config user.email "moblee@local"
  ok "local identity set (you can change it later with: git config user.name '...' && git config user.email '...')"
fi

# ----- git commit -------------------------------------------------------------
step "git commit"
COMMIT_MSG_BODY=$(cat <<'EOF'
Initial commit: Moblee v0.1 starter pack

Moblee is a starter pack for a Karpathy-style Obsidian wiki maintained by
Claude. This commit captures the v0.1 layout:

  - README.md, START_HERE.md, LICENSE   top-level entry points
  - scripts/                            install.sh, install-skills.sh, vault.sh
  - docs/                               philosophy and how-to documentation
  - skills/                             five Claude skills:
                                          brain
                                          wiki-capture
                                          wiki-to-pdf
                                          wiki-interview
                                          design-your-brand
  - vault-template/                     generic vault skeleton with CLAUDE.md
                                        and placeholder folders (raw/,
                                        Clippings/, wiki/, outputs/)

Users run `bash scripts/install.sh` to lay down a vault on their own Mac,
then `bash scripts/install-skills.sh` to copy the bundled skills into
~/.claude/skills/.
EOF
)

git commit --quiet -m "$COMMIT_MSG_BODY"
COMMIT_HASH=$(git rev-parse --short HEAD)
ok "committed as ${BOLD}$COMMIT_HASH${RESET}"

# ----- next steps -------------------------------------------------------------
banner "Your Moblee repo is ready."

cat <<EOF
${BOLD}What to do next${RESET}

Pick ${BOLD}one${RESET} of the two delivery paths below.

${BOLD}Option A: push to GitHub${RESET}

  If you have the GitHub CLI installed (gh):

    cd "$PACKAGE_ROOT"
    gh repo create moblee --public --source=. --remote=origin --push

  Or, manually, after creating an empty repo on github.com:

    cd "$PACKAGE_ROOT"
    git remote add origin git@github.com:[YourGitHubUser]/moblee.git
    git branch -M main
    git push -u origin main

  Then send Mubarak the repo URL and tell him:

    1. git clone <repo-url> ~/moblee
    2. cd ~/moblee
    3. bash scripts/install.sh
    4. (optionally) bash scripts/install-skills.sh

${BOLD}Option B: zip and AirDrop${RESET}

  cd "$(dirname "$PACKAGE_ROOT")"
  zip -r moblee-v0.1.zip "$(basename "$PACKAGE_ROOT")" -x "*.discarded/*" -x "*.DS_Store"

  Then AirDrop ${BOLD}moblee-v0.1.zip${RESET} to Mubarak and tell him:

    1. Double-click the zip to unpack (it produces a 'moblee' folder)
    2. cd ~/Downloads/moblee   (or wherever he unpacks it)
    3. bash scripts/install.sh
    4. (optionally) bash scripts/install-skills.sh

${BOLD}Either way${RESET}, the install.sh script asks Mubarak for his name and a vault
name, lays down the vault, and substitutes the placeholders. install-skills.sh
copies the bundled skills into ~/.claude/skills/ on his machine.

${DIM}Repo location: $PACKAGE_ROOT${RESET}
${DIM}Latest commit: $COMMIT_HASH${RESET}
EOF

echo ""
ok "done."
echo ""
