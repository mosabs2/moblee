#!/usr/bin/env bash
# moblee-tip.sh: the learning path's evening reminder (macOS).
#
# Installed into the vault's scripts/ folder by scripts/install-learning-path.py and run each
# evening by launchd (com.moblee.nightly-tip), or by hand from the vault:
#   bash scripts/moblee-tip.sh            shows a notification naming the next lesson
#   bash scripts/moblee-tip.sh --print    prints the same text instead (for checks)
#
# It reads wiki/Wiki Operations/Moblee Learning Path.md, finds the lowest lesson number not yet
# listed under "## Progress", and names it. It never writes to the vault; once every lesson has
# been given it sends one closing notice, notes that in ~/.config/moblee/lessons-finished, and
# stays silent from then on. To switch the reminder off earlier, run the pack's
# scripts/install-learning-path.py with --remove-reminder.
set -u

PRINT_ONLY=0
if [[ "${1:-}" == "--print" ]]; then PRINT_ONLY=1; fi
FINISHED="$HOME/.config/moblee/lessons-finished"

notify() {
  # notify <title> <message>; the text is passed as arguments so quotes in it cannot break the script
  if [[ $PRINT_ONLY -eq 1 ]]; then
    echo "$1"
    echo "$2"
  else
    osascript -e 'on run argv' -e 'display notification (item 2 of argv) with title (item 1 of argv) sound name "Glass"' -e 'end run' "$1" "$2"
  fi
}

# Find the vault: MOBLEE_VAULT, then ~/.config/moblee/vault-path, then the folder above.
VAULT="${MOBLEE_VAULT:-}"
if [[ -z "$VAULT" && -f "$HOME/.config/moblee/vault-path" ]]; then
  VAULT="$(head -n 1 "$HOME/.config/moblee/vault-path")"
fi
if [[ -z "$VAULT" || ! -d "$VAULT/wiki" ]]; then
  dir="$(pwd)"
  while [[ "$dir" != "/" ]]; do
    if [[ -f "$dir/wiki/Index.md" ]]; then VAULT="$dir"; break; fi
    dir="$(dirname "$dir")"
  done
fi
PAGE="$VAULT/wiki/Wiki Operations/Moblee Learning Path.md"

if [[ -z "$VAULT" || ! -d "$VAULT" ]]; then
  notify "Moblee" "The evening reminder cannot find your vault. Tell your assistant: the lesson reminder cannot find the vault."
  exit 0
fi
if [[ ! -r "$PAGE" ]]; then
  notify "Moblee" "The evening reminder cannot read the learning path. Tell your assistant: the lesson reminder cannot read the learning path."
  exit 0
fi

TOTAL="$(grep -c '^## Lesson [0-9]' "$PAGE")"
# Delivered lesson numbers, one per line, from the Progress list (lines like "- 7, 2026-09-23").
DONE="$(sed -n '/^## Progress/,$p' "$PAGE" | grep -E '^- [0-9]+,' | sed -E 's/^- ([0-9]+),.*/\1/')"
NEXT=""
for ((n=1; n<=TOTAL; n++)); do
  found=0
  for d in $DONE; do
    if [[ "$d" == "$n" ]]; then found=1; break; fi
  done
  if [[ $found -eq 0 ]]; then NEXT="$n"; break; fi
done

if [[ -z "$NEXT" ]]; then
  if [[ $PRINT_ONLY -eq 0 && -f "$FINISHED" ]]; then exit 0; fi
  notify "Moblee" "All $TOTAL lessons done. Keep the rhythm: today, close the day, and the Saturday check. This is the last reminder."
  if [[ $PRINT_ONLY -eq 0 ]]; then mkdir -p "$(dirname "$FINISHED")" && date '+%Y-%m-%d' > "$FINISHED"; fi
else
  HEADING="$(grep -m1 "^## Lesson $NEXT:" "$PAGE" | sed "s/^## Lesson $NEXT: //")"
  notify "Moblee, lesson $NEXT of $TOTAL" "$HEADING. Open your assistant in your vault and say: lesson $NEXT"
fi
