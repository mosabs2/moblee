#!/bin/bash
# Test the Moblee app before anyone is asked to open it.
#
#   bash app/scripts/test-app.sh
#
# Builds the app, then, in a fresh temporary practice home so nothing on this
# Mac is changed:
#   1. draws every screen to picture files (no window),
#   2. rehearses a real install through the app's own code (no window),
#   3. opens the real window and lets the app click through every screen by
#      itself, with a real install on the way.
# The third is the one that catches faults which only happen while live
# screens are being drawn. A window appears for about half a minute.
# Nothing is deleted. Prints PASS or FAIL for each check and a total.
set -u
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK=$(mktemp -d /tmp/moblee-app-test.XXXXXX)
PASS=0; FAIL=0
ok()   { echo "PASS  $1"; PASS=$((PASS+1)); }
bad()  { echo "FAIL  $1"; FAIL=$((FAIL+1)); }

echo "Moblee app test. Working folder: $WORK"
if bash "$here/build-app.sh" > "$WORK/build.txt" 2>&1; then ok "the app builds"; else bad "the app builds (see $WORK/build.txt)"; echo "$PASS passed, $FAIL failed."; exit 1; fi
APP="$(cat "${MOBLEE_BUILD_DIR:-$HOME/Library/Caches/moblee-build}/latest.txt")"
BIN="$APP/Contents/MacOS/Moblee"
[[ -f "$APP/Contents/Resources/pack/scripts/install.sh" ]] && ok "the pack is inside the app" || bad "the pack is inside the app"

mkdir -p "$WORK/home-draw" "$WORK/home-rehearse" "$WORK/home-drive"

# Without this the app ignores every practice switch, as a released app must.
( unset MOBLEE_PRACTICE; "$BIN" --home "$WORK/home-refused" --snapshot "$WORK/screens-refused" > "$WORK/refused.txt" 2>&1 )
[[ $? -eq 2 && ! -e "$WORK/screens-refused" && ! -e "$WORK/home-refused" ]] && ok "without MOBLEE_PRACTICE=1 a practice switch is refused outright, and nothing is touched" || bad "without MOBLEE_PRACTICE=1 a practice switch is refused outright"
export MOBLEE_PRACTICE=1

"$BIN" --home "$WORK/home-draw" --snapshot "$WORK/screens" > "$WORK/draw.txt" 2>&1
[[ "$(ls "$WORK/screens" 2>/dev/null | grep -c '\.png$')" == "23" ]] && ok "twenty-three screens drawn to picture files ($WORK/screens)" || bad "twenty-three screens drawn (see $WORK/draw.txt)"
"$BIN" --dark --home "$WORK/home-draw" --snapshot "$WORK/screens-dark" > "$WORK/draw-dark.txt" 2>&1
[[ "$(ls "$WORK/screens-dark" 2>/dev/null | grep -c '\.png$')" == "23" ]] && ok "and the same twenty-three in dark mode ($WORK/screens-dark)" || bad "twenty-three dark screens drawn (see $WORK/draw-dark.txt)"
[[ ! -e "$WORK/home-draw/.claude" ]] && ok "drawing screens installs nothing" || bad "drawing screens installs nothing"

"$BIN" --home "$WORK/home-rehearse" --owner "Tom & Sam" --rehearse "$WORK/screens" > "$WORK/rehearse.txt" 2>&1
RC=$?
[[ $RC -eq 0 ]] && grep -q "phase: finished" "$WORK/rehearse.txt" && ok "rehearsed install finishes" || bad "rehearsed install finishes (see $WORK/rehearse.txt)"
V="$WORK/home-rehearse/Wiki/Tom Wiki"
[[ -f "$V/CLAUDE.md" ]] && git -C "$V" rev-parse --verify --quiet HEAD >/dev/null && [[ -z "$(git -C "$V" status --porcelain)" ]] && ok "rehearsed wiki exists, has its history, and is clean" || bad "rehearsed wiki exists, has its history, and is clean"
[[ "$(cat "$WORK/home-rehearse/.config/moblee/vault-path" 2>/dev/null)" == "$V" ]] && ok "the record of the wiki's place is written (by the last step)" || bad "the record of the wiki's place is written"
! grep -q "Tom" "$WORK/home-rehearse/.config/moblee/install-diary.txt" && ok "the install diary holds no name, not even in the wiki's folder name" || bad "the install diary holds no name"
grep -q "Tom & Sam" "$V/CLAUDE.md" 2>/dev/null && ok "the owner's name arrives as typed" || bad "the owner's name arrives as typed"
[[ -f "$WORK/home-rehearse/.claude/hooks/bash-guard.py" ]] && ok "the guard is installed" || bad "the guard is installed"
[[ -d "$WORK/home-rehearse/Library/Application Support/Moblee" ]] && ok "the pack is settled under Application Support" || bad "the pack is settled under Application Support"
"$BIN" --rehearse "$WORK/screens" > "$WORK/refuse.txt" 2>&1
[[ $? -eq 2 ]] && ok "a rehearsal without a practice home is refused" || bad "a rehearsal without a practice home is refused"

# The download mark macOS puts on a downloaded app, put here on one file of
# this build, so the move to Applications can be seen to clear it from the copy.
xattr -w com.apple.quarantine "0081;00000000;Safari;" "$APP/Contents/Info.plist" 2>/dev/null

"$BIN" --home "$WORK/home-drive" --move-to "$WORK/applications" --self-drive > "$WORK/drive.txt" 2>&1
RC=$?
[[ $RC -eq 0 ]] && ok "the real window opens every screen and finishes an install" || bad "the real window opens every screen and finishes an install (exit $RC; see $WORK/drive.txt)"
MOVED="$WORK/applications/Moblee.app"
grep -q "^self-drive: ok: clicking Move it there makes a whole copy" "$WORK/drive.txt" && [[ -x "$MOVED/Contents/MacOS/Moblee" ]] && ok "opened outside Applications, the app offers to move itself, and the button makes the copy" || bad "the app moves itself to Applications"
codesign --verify --strict "$MOVED" 2>/dev/null && ok "the moved copy's signature is intact" || bad "the moved copy's signature is intact"
xattr "$APP/Contents/Info.plist" | grep -q quarantine && ! xattr -r "$MOVED" 2>/dev/null | grep -q quarantine && ok "the download mark is cleared from the copy (so macOS runs it from where it is)" || bad "the download mark is cleared from the copy"
[[ -x "$BIN" ]] && ok "a practice move leaves the original where it is" || bad "a practice move leaves the original where it is"
for s in "move to Applications" welcome check-up name build hand-off home; do
  grep -q "^self-drive: $s" "$WORK/drive.txt" && ok "  reached: $s" || bad "  reached: $s"
done
grep -q "^self-drive: tiles waiting: trips, videos" "$WORK/drive.txt" && ok "home screen shows the two things agreed with Claude" || bad "home screen shows the two things agreed with Claude"
grep -q "^self-drive: trips ended: .*done" "$WORK/drive.txt" && [[ -f "$WORK/home-drive/.claude/skills/trips/SKILL.md" ]] && ok "pressing Add on a quiet item adds it (the skill is really there)" || bad "pressing Add on a quiet item adds it"
grep -q "^self-drive: videos ended: .*handedOver" "$WORK/drive.txt" && [[ -x "$WORK/home-drive/Library/Application Support/Moblee/run/add-videos.command" ]] && ok "a Terminal item is explained, then handed over as a command file" || bad "a Terminal item is explained, then handed over as a command file"
CMD="$WORK/home-drive/Library/Application Support/Moblee/run/add-videos.command"
grep -q "^python3 scripts/moblee-setup.py --only videos --yes$" "$CMD" && ok "the command file runs the pack's own checklist for that one item, without asking 'Start now?' a third time" || bad "the command file runs the pack's own checklist for that one item"
bash -n "$CMD" 2>/dev/null && grep -q 'kill -9 "\$PPID"' "$CMD" && grep -q 'Apple_Terminal' "$CMD" && ok "the command file is sound, and ends Terminal's own shell before it can print 'Deleting expired sessions'" || bad "the command file is sound and silences Terminal's closing lines"
grep -q "^self-drive: ok: the three cards are the pack's own" "$WORK/drive.txt" && ok "the Google tile says where to go, what to switch on by name, and how to tell it worked" || bad "the Google tile's three cards"
grep -q "^self-drive: google ended: .*done" "$WORK/drive.txt" && grep -q '"item:google"' "$WORK/home-drive/.config/moblee/app-state.json" 2>/dev/null && ok "clicks inside Claude are finished by the owner pressing Done, and it stays done" || bad "a clicks item can be marked done"
[[ "$(ls "$WORK/home-drive/Library/Application Support/Moblee/run/" | wc -l | tr -d " ")" == "1" ]] && ok "no other command file was written" || bad "no other command file was written"
grep -q "^self-drive: skill gym-log ended: .*done" "$WORK/drive.txt" && [[ -f "$WORK/home-drive/.claude/skills/gym-log/.made-for-you" && ! -L "$WORK/home-drive/.claude/skills/gym-log" ]] && ok "a skill Claude drafted is shown, then added as ordinary files" || bad "a skill Claude drafted is shown, then added as ordinary files"
grep -q "^self-drive: skill sneaky: .*blocked" "$WORK/drive.txt" && [[ ! -e "$WORK/home-drive/.claude/skills/sneaky" ]] && ok "a drafted skill that is a link to outside the wiki is refused" || bad "a drafted skill that is a link to outside the wiki is refused"
grep -q "^self-drive: skill brain: .*blocked" "$WORK/drive.txt" && grep -q "brain untouched: true" "$WORK/drive.txt" && ok "a drafted skill wearing a Moblee skill's name is refused, and the real one is untouched" || bad "a drafted skill wearing a Moblee skill's name is refused"
grep -q "nothing smuggled: true" "$WORK/drive.txt" && [[ ! -e /tmp/moblee-pwned ]] && ok "a request with a command or a path in its key makes no tile and runs nothing" || bad "a request with a command or a path in its key makes no tile and runs nothing"
"$BIN" --self-drive > "$WORK/refuse2.txt" 2>&1 &
PID=$!; sleep 3
if kill -0 $PID 2>/dev/null; then kill $PID; bad "self-drive without a practice home is refused"; else wait $PID; [[ $? -eq 2 ]] && ok "self-drive without a practice home is refused" || bad "self-drive without a practice home is refused"; fi

echo ""
echo "$PASS passed, $FAIL failed. Screens and outputs are in $WORK"
[[ $FAIL -eq 0 ]]
