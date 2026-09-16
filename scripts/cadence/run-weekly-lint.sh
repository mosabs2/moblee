#!/usr/bin/env bash
# run-weekly-lint.sh — the scheduled weekly structural lint for a Moblee vault.
#
# Installed by scripts/install-schedule.sh to ~/.config/moblee/run-weekly-lint.sh
# and run by launchd every Saturday at 09:04 (see com.moblee.weekly-lint.plist).
# It can also be run by hand at any time:  bash ~/.config/moblee/run-weekly-lint.sh
#
# What it does, in order:
#   1. Finds the vault (MOBLEE_VAULT, then ~/.config/moblee/vault-path, then
#      walking up from the current directory for a folder with wiki/Index.md).
#   2. Skips if today's report, outputs/lint/lint-v2-YYYY-MM-DD.md, already
#      exists (so a manual run and the scheduled run never collide).
#   3. Runs python3 scripts/lint-v2.py inside the vault, which writes that report.
#   4. Writes a short log to ~/.config/moblee/logs/weekly-lint-YYYY-MM-DD.log.
#   5. Moves logs older than 90 days into ~/.config/moblee/logs/archive/.
#      Nothing is ever deleted.
# It makes no network calls, never commits, and never writes into wiki/.
set -u
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

LOG_DIR="$HOME/.config/moblee/logs"
ARCHIVE_DIR="$LOG_DIR/archive"
mkdir -p "$LOG_DIR" "$ARCHIVE_DIR"
TODAY=$(date '+%Y-%m-%d')
LOG="$LOG_DIR/weekly-lint-$TODAY.log"

log() {
  echo "$(date '+%Y-%m-%d %H:%M') $*" >> "$LOG"
}

# --- 5 (done first so it runs even when the lint is skipped): archive old logs.
# The launchd stream file is excluded: launchd holds it open, and moving it
# would silently redirect the stream.
find "$LOG_DIR" -maxdepth 1 -type f -name '*.log' ! -name 'launchd-*.log' \
  -mtime +90 -exec mv {} "$ARCHIVE_DIR/" \; 2>/dev/null

# --- 1: find the vault by the Moblee convention.
is_vault() { [ -n "${1:-}" ] && [ -f "$1/wiki/Index.md" ]; }

VAULT=""
if is_vault "${MOBLEE_VAULT:-}"; then
  VAULT="$MOBLEE_VAULT"
elif [ -f "$HOME/.config/moblee/vault-path" ]; then
  recorded=$(head -n 1 "$HOME/.config/moblee/vault-path" | tr -d '\r')
  recorded="${recorded/#\~/$HOME}"
  if is_vault "$recorded"; then
    VAULT="$recorded"
  fi
fi
if [ -z "$VAULT" ]; then
  dir=$(pwd)
  while [ "$dir" != "/" ]; do
    if is_vault "$dir"; then VAULT="$dir"; break; fi
    dir=$(dirname "$dir")
  done
fi
if [ -z "$VAULT" ]; then
  log "FAILED: could not find the vault. Set MOBLEE_VAULT, or write the vault's full path into ~/.config/moblee/vault-path (the installer normally does this)."
  exit 1
fi

# --- interpreter: launchd's PATH is minimal, so resolve python3 explicitly.
if command -v python3 >/dev/null 2>&1; then
  PY=python3
elif [ -x /opt/homebrew/bin/python3 ]; then
  PY=/opt/homebrew/bin/python3
elif [ -x /usr/bin/python3 ]; then
  PY=/usr/bin/python3
else
  log "FAILED: no python3 found on PATH, at /opt/homebrew/bin/python3, or at /usr/bin/python3."
  exit 1
fi

LINT="$VAULT/scripts/lint-v2.py"
if [ ! -f "$LINT" ]; then
  log "FAILED: $LINT is missing. Copy lint-v2.py from the Moblee pack's scripts/ folder into the vault's scripts/ folder."
  exit 1
fi

# --- 2: idempotent skip.
REPORT="$VAULT/outputs/lint/lint-v2-$TODAY.md"
if [ -e "$REPORT" ]; then
  log "today's report already exists, nothing to do: $REPORT"
  exit 0
fi

# --- 3: run the lint from inside the vault.
log "weekly lint starting in $VAULT"
cd "$VAULT" || { log "FAILED: could not enter $VAULT"; exit 1; }
"$PY" "$LINT" >> "$LOG" 2>&1
rc=$?
if [ "$rc" -ne 0 ]; then
  log "FAILED: lint exited $rc (see the lines above)"
  exit "$rc"
fi
if [ -e "$REPORT" ]; then
  log "done: report written to $REPORT"
else
  log "lint exited 0 but no report appeared at $REPORT; check the lines above"
  exit 1
fi
exit 0
