#!/usr/bin/env bash
# vault-orient-preflight.sh — vault-health probe run before a session-start
# orientation. Purpose: detect stale-vault conditions (Obsidian not running,
# unusually old working files, uncommitted work) before an orientation
# returns misleading state.
#
# Invoke with `bash scripts/vault-orient-preflight.sh` — do not rely on the
# executable bit, which some sync tools drop.
#
# Vault detection, in order of precedence:
#   1. the MOBLEE_VAULT environment variable (absolute path to the vault);
#   2. ~/.config/moblee/vault-path (single line, absolute path — the Moblee
#      installer writes it);
#   3. walking up from the current working directory looking for a folder
#      containing wiki/Index.md.

set -uo pipefail

# --- Vault detection ---
VAULT_ROOT=""
if [ -n "${MOBLEE_VAULT:-}" ]; then
  if [ -f "${MOBLEE_VAULT}/wiki/Index.md" ]; then
    VAULT_ROOT="$MOBLEE_VAULT"
  else
    echo "[ERROR] MOBLEE_VAULT is set to '$MOBLEE_VAULT', but that folder does not contain wiki/Index.md."
    echo "        A vault is a folder containing wiki/Index.md. Fix or unset MOBLEE_VAULT."
    exit 1
  fi
fi

CONFIG_FILE="$HOME/.config/moblee/vault-path"
if [ -z "$VAULT_ROOT" ] && [ -f "$CONFIG_FILE" ]; then
  candidate=""
  IFS= read -r candidate < "$CONFIG_FILE" || true
  if [ -n "$candidate" ] && [ -f "$candidate/wiki/Index.md" ]; then
    VAULT_ROOT="$candidate"
  elif [ -n "$candidate" ]; then
    echo "[NOTE] $CONFIG_FILE points at '$candidate', which is not a vault (no wiki/Index.md there); searching upward from the current directory instead."
  fi
fi

if [ -z "$VAULT_ROOT" ]; then
  dir="$PWD"
  while [ "$dir" != "/" ]; do
    if [ -f "$dir/wiki/Index.md" ]; then
      VAULT_ROOT="$dir"
      break
    fi
    dir="${dir%/*}"
    [ -z "$dir" ] && dir="/"
  done
fi

if [ -z "$VAULT_ROOT" ]; then
  echo "[ERROR] Could not find your wiki vault."
  echo "        Tried, in order: the MOBLEE_VAULT environment variable (not set),"
  echo "        the path recorded in $CONFIG_FILE (missing or invalid),"
  echo "        and walking up from $PWD looking for a folder containing wiki/Index.md."
  echo "        Fix: run this from inside your vault, set MOBLEE_VAULT to the vault's"
  echo "        absolute path, or re-run the Moblee installer so it records the path."
  exit 1
fi

WIKI_DIR="$VAULT_ROOT/wiki"
LOG_FILE="$WIKI_DIR/log.md"
CONTEXT_FILE="$WIKI_DIR/_context.md"

now=$(date "+%Y-%m-%d %H:%M:%S %Z")
now_epoch=$(date +%s)

echo "=== Vault Orient Preflight — $now ==="
echo ""

# --- A. Obsidian process health (a paused Obsidian means any sync service it
# runs is paused too, and edits made in it since the last save may be pending) ---
if pgrep -x "Obsidian" >/dev/null 2>&1; then
  echo "[OK] Obsidian process running"
else
  echo "[INFO] Obsidian process NOT running — fine if you work through Claude only; if you use Obsidian Sync or edit in Obsidian, restart it before trusting current state."
fi

# --- B. File freshness for the two orientation-critical files ---
check_freshness() {
  local f="$1"
  local fname
  fname=$(basename "$f")
  if [[ -f "$f" ]]; then
    local mt age_h
    mt=$(stat -f "%m" "$f" 2>/dev/null || stat -c "%Y" "$f")
    age_h=$(( (now_epoch - mt) / 3600 ))
    if (( age_h > 24 )); then
      echo "[INFO] $fname is ${age_h}h old — no working session has touched it in over a day; treat its state as possibly behind recent conversation."
    else
      echo "[OK] $fname is ${age_h}h old"
    fi
  else
    echo "[ERROR] $f not found"
  fi
}
check_freshness "$LOG_FILE"
check_freshness "$CONTEXT_FILE"

# --- C. Git state ---
if git -C "$VAULT_ROOT" rev-parse --git-dir >/dev/null 2>&1; then
  last_commit=$(git -C "$VAULT_ROOT" log -1 --format='%ci %h %s' 2>/dev/null || echo "no commits yet")
  [ -z "$last_commit" ] && last_commit="no commits yet"
  echo "[OK] Last commit: $last_commit"
  dirty=$(git -C "$VAULT_ROOT" status --short 2>/dev/null | wc -l | tr -d ' ')
  if (( dirty > 0 )); then
    echo "[INFO] $dirty uncommitted change(s) in working tree — content awaiting a commit at the next natural close of work"
  else
    echo "[OK] Working tree clean"
  fi
else
  echo "[INFO] Not a git repository — skipping commit check (version history is recommended; run 'git init' in the vault to enable it)"
fi

# --- D. Vault identity ---
echo ""
echo "[INFO] Vault root: $VAULT_ROOT"

echo ""
echo "=== Preflight complete ==="
