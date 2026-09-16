#!/usr/bin/env bash
# install-schedule.sh — put the weekly structural lint on a schedule (macOS).
#
# Run from the root of the Moblee package:
#
#   bash scripts/install-schedule.sh
#
# What it does:
#   1. Copies scripts/cadence/run-weekly-lint.sh to ~/.config/moblee/run-weekly-lint.sh.
#   2. Fills in the launchd template (scripts/cadence/com.moblee.weekly-lint.plist.template)
#      with your home folder and writes it to ~/Library/LaunchAgents/com.moblee.weekly-lint.plist.
#   3. Loads it with launchctl, so the lint runs every Saturday at 09:04.
#      If the schedule was already installed, it is unloaded and reloaded, so
#      running this script again is always safe.
#
# To remove the schedule later:
#   launchctl bootout gui/$(id -u)/com.moblee.weekly-lint
#   (or: launchctl unload ~/Library/LaunchAgents/com.moblee.weekly-lint.plist)

set -euo pipefail

if [[ "$(uname)" != "Darwin" ]]; then
  echo "This scheduler uses launchd, which exists only on macOS. Nothing installed."
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CADENCE_DIR="$SCRIPT_DIR/cadence"
RUNNER_SRC="$CADENCE_DIR/run-weekly-lint.sh"
PLIST_SRC="$CADENCE_DIR/com.moblee.weekly-lint.plist.template"

for f in "$RUNNER_SRC" "$PLIST_SRC"; do
  if [[ ! -f "$f" ]]; then
    echo "Error: $f not found. Run this from the Moblee package (bash scripts/install-schedule.sh)."
    exit 1
  fi
done

LABEL="com.moblee.weekly-lint"
CONFIG_DIR="$HOME/.config/moblee"
LOG_DIR="$CONFIG_DIR/logs"
RUNNER_DST="$CONFIG_DIR/run-weekly-lint.sh"
AGENTS_DIR="$HOME/Library/LaunchAgents"
PLIST_DST="$AGENTS_DIR/$LABEL.plist"
UID_NUM="$(id -u)"

echo ""
echo "==================================================================="
echo "  Moblee weekly lint scheduler"
echo "==================================================================="
echo ""

# ----- make sure the runner will be able to find the vault -------------------
mkdir -p "$CONFIG_DIR" "$LOG_DIR" "$AGENTS_DIR"
VAULT_PATH_FILE="$CONFIG_DIR/vault-path"
if [[ -f "$VAULT_PATH_FILE" ]] && [[ -f "$(head -n 1 "$VAULT_PATH_FILE")/wiki/Index.md" ]]; then
  echo "Vault: $(head -n 1 "$VAULT_PATH_FILE")  (from $VAULT_PATH_FILE)"
else
  found=""
  dir="$(pwd)"
  while [[ "$dir" != "/" ]]; do
    if [[ -f "$dir/wiki/Index.md" ]]; then found="$dir"; break; fi
    dir="$(dirname "$dir")"
  done
  if [[ -n "$found" ]]; then
    echo "$found" > "$VAULT_PATH_FILE"
    echo "Vault: $found  (recorded in $VAULT_PATH_FILE so the scheduled run can find it)"
  else
    echo "Note: no vault path is recorded yet and this folder is not inside a vault."
    echo "      The schedule will be installed, but each run will fail until you write"
    echo "      your vault's full path into $VAULT_PATH_FILE"
    echo "      (the Moblee installer does this for you when it creates a vault)."
  fi
fi

# ----- 1. the runner ---------------------------------------------------------
cp "$RUNNER_SRC" "$RUNNER_DST"
chmod +x "$RUNNER_DST"
echo "Runner copied to $RUNNER_DST"

# ----- 2. the launchd agent --------------------------------------------------
sed "s|__HOME__|$HOME|g" "$PLIST_SRC" > "$PLIST_DST"
echo "Schedule written to $PLIST_DST"

# ----- 3. (re)load it --------------------------------------------------------
if launchctl print "gui/$UID_NUM/$LABEL" >/dev/null 2>&1; then
  launchctl bootout "gui/$UID_NUM/$LABEL" >/dev/null 2>&1 \
    || launchctl unload "$PLIST_DST" >/dev/null 2>&1 \
    || true
  echo "A previous copy of the schedule was loaded; unloaded it first."
fi

if launchctl bootstrap "gui/$UID_NUM" "$PLIST_DST" >/dev/null 2>&1; then
  echo "Schedule loaded."
elif launchctl load "$PLIST_DST" >/dev/null 2>&1; then
  echo "Schedule loaded (using the older launchctl load command)."
else
  echo "Error: launchctl refused to load the schedule. Try running these by hand:"
  echo "  launchctl bootstrap gui/$UID_NUM \"$PLIST_DST\""
  echo "  launchctl load \"$PLIST_DST\""
  exit 1
fi

if launchctl print "gui/$UID_NUM/$LABEL" >/dev/null 2>&1; then
  STATUS="confirmed loaded"
else
  STATUS="loaded, but launchctl could not confirm it (this can happen on some macOS versions; check next Saturday's log)"
fi

# ----- done ------------------------------------------------------------------
echo ""
echo "==================================================================="
echo "  Done."
echo "==================================================================="
echo ""
echo "Every Saturday at 09:04 (while this Mac is awake and you are logged in)"
echo "the structural lint runs and writes its report to"
echo "  <your vault>/outputs/lint/lint-v2-<date>.md"
echo "Status: $STATUS."
echo ""
echo "To check it ran:      ls $LOG_DIR"
echo "To run it right now:  bash $RUNNER_DST"
echo "To remove it:         launchctl bootout gui/$UID_NUM/$LABEL"
echo ""
