#!/bin/bash
# Notification-hook audible nudge — rotating weekly pool, random pick per nudge,
# never the same nudge twice in a row. Fires when Claude Code is waiting on you
# (a permission prompt, or input idle); a fixed phrase wears thin over long
# sessions, so the phrases rotate.
#
# Mechanics: four pools of six generic nudges rotating by ISO week (same pool
# all week, changes Monday) plus one standing permission pool; within a pool the
# pick is random, with the last-played nudge persisted and excluded from the
# next pick. Entries are "say:<phrase>" (macOS say), "snd:<Name>" (system
# sound), or "geo:<phrase>" (spoken via speak-elevenlabs.py — falls back to
# `say` inside that script if no ElevenLabs key is configured).
#
# Suppression: NUDGE_SILENT=1 is an explicit opt-out; the `voice off` mute flag
# silences nudges too. A Notification hook only fires when a human is actually
# waiting, so the safe default is to nudge.
RAWIN=$(cat 2>/dev/null)

[ -n "$NUDGE_SILENT" ] && exit 0
[ -f "$HOME/.claude/voice-mute" ] && exit 0

RATE=185
STATE="$HOME/.claude/hooks/.nudge-last"

MSG=$(printf '%s' "$RAWIN" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("message",""))' 2>/dev/null)

POOL0=("say:Claude needs you" "say:Your input is needed" "say:Over to you" "say:Knock knock" "snd:Glass" "say:Ready when you are")
POOL1=("say:A moment please" "say:Something here needs your eyes" "say:Your move" "say:Hello? Anyone home?" "snd:Submarine" "say:Awaiting instructions, boss")
POOL2=("say:Paging you" "say:Quick question for you" "say:The wiki calls" "say:Don't leave me hanging" "snd:Ping" "say:Claude here, slightly stuck")
POOL3=("say:Permission to proceed?" "say:Input, please" "say:One click and we're off" "say:The machines await your verdict" "snd:Hero" "say:Still with me?")
# Permission pool — spoken via speak-elevenlabs.py (ElevenLabs if configured, else say).
POOLP=("geo:Approval needed." "geo:There's a button waiting for you." "geo:Permission, please." "geo:I need a yes from you." "geo:One approval and I carry on." "geo:Waiting on your click.")

case "$MSG" in
  *ermission*|*pprov*)
    pool=("${POOLP[@]}"); week="P" ;;
  *)
    week=$(( 10#$(date +%V) % 4 ))
    eval "pool=(\"\${POOL${week}[@]}\")" ;;
esac
n=${#pool[@]}

last=$(cat "$STATE" 2>/dev/null)
while :; do
  i=$(( RANDOM % n ))
  key="${week}:${i}"
  [ "$key" != "$last" ] && break
done
echo "$key" > "$STATE"

entry="${pool[$i]}"
kind="${entry%%:*}"
val="${entry#*:}"

# NUDGE_DRY=1 prints the selection instead of playing it (for testing).
if [ -n "$NUDGE_DRY" ]; then
  echo "[$key] $entry"
  exit 0
fi

# Detached playback so the hook returns immediately.
if [ "$kind" = "snd" ]; then
  afplay "/System/Library/Sounds/${val}.aiff" >/dev/null 2>&1 &
elif [ "$kind" = "geo" ]; then
  python3 "$HOME/.claude/hooks/speak-elevenlabs.py" "$val" >/dev/null 2>&1 &
else
  say -r "$RATE" "$val" >/dev/null 2>&1 &
fi
exit 0
