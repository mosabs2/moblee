#!/bin/bash
# rebuild-index.sh - rebuild the wiki's memory-search index, quietly.
#
# Called by the nightly launch agent (com.moblee.recall-rebuild, 04:40, or the
# next wake), by the wiki's post-commit hook in the background after a commit
# that touched wiki/ or memory/, and by the Memory search item once at setup.
# Only changed sections are embedded, so an ordinary run takes seconds. Never
# fails loudly: a skipped or failed rebuild is one line in the log and exit 0,
# so a commit is never held up. Nothing is deleted here; the one-at-a-time
# lock is kept by recall.py itself.
#
# The model's program (Ollama) is opened only by the nightly, setup and manual
# runs: a post-commit run with Ollama closed notes it and leaves it to the
# night, so an owner who quit Ollama does not see it reappear after every save.
#
# Usage: rebuild-index.sh [trigger]      e.g. post-commit | launchd | setup | manual
TRIGGER="${1:-manual}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
VAULT="$(cd "$HERE/../.." && pwd -P)"
if [ -n "${MOBLEE_RECALL_CACHE:-}" ]; then
  CACHE="$MOBLEE_RECALL_CACHE"
else
  KEY="$(printf '%s' "$VAULT" | /usr/bin/shasum | cut -c1-12)"
  CACHE="$HOME/.cache/moblee-recall/$KEY"
fi
LOG="$CACHE/rebuild.log"
OLLAMA="${MOBLEE_OLLAMA:-http://127.0.0.1:11434}"
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
mkdir -p "$CACHE"
log() { echo "$(date '+%Y-%m-%d %H:%M %z') [$TRIGGER] $1" >> "$LOG"; }

PY=""
for cand in /usr/bin/python3 "$(command -v python3 2>/dev/null)"; do
  [ -n "$cand" ] && [ -x "$cand" ] && { PY="$cand"; break; }
done
[ -z "$PY" ] && { log "skipped: no python3"; exit 0; }

up() { curl -fsS -m 5 "$OLLAMA/api/tags" >/dev/null 2>&1; }

if [ "${MOBLEE_EMBED_STUB:-}" != "1" ] && ! up; then
  if [ "$TRIGGER" != "post-commit" ] && [ -d /Applications/Ollama.app ]; then
    open -gj /Applications/Ollama.app 2>/dev/null
    for i in 1 2 3 4 5 6 7 8 9 10 11 12; do
      sleep 5
      up && break
    done
  fi
  if ! up; then
    log "skipped: the model service is not running (Ollama at $OLLAMA)"
    exit 0
  fi
fi

start=$(date +%s)
out=$(MOBLEE_VAULT="$VAULT" "$PY" "$HERE/recall.py" rebuild 2>&1)
rc=$?
secs=$(( $(date +%s) - start ))
if [ $rc -ne 0 ]; then
  log "FAILED (exit $rc) after ${secs}s: $(echo "$out" | grep -v 'embedded' | tail -1)"
elif echo "$out" | grep -q "another rebuild is running"; then
  log "skipped: another rebuild was running"
else
  log "ok in ${secs}s: $(echo "$out" | grep -o 'index built.*\|nothing to index.*' | head -1)"
fi
exit 0
