#!/bin/bash
# Test the Moblee app before anyone is asked to open it.
#
#   bash app/scripts/test-app.sh
#
# Builds the app, then, in a fresh temporary practice home so nothing on this
# Mac is changed:
#   1. draws every screen to picture files (no window), and checks the app's
#      decisions about the assistant (no window, no scripts run),
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
[[ "$(ls "$WORK/screens" 2>/dev/null | grep -c '\.png$')" == "41" ]] && ok "forty-one screens drawn to picture files ($WORK/screens)" || bad "forty-one screens drawn (see $WORK/draw.txt)"
"$BIN" --dark --home "$WORK/home-draw" --snapshot "$WORK/screens-dark" > "$WORK/draw-dark.txt" 2>&1
[[ "$(ls "$WORK/screens-dark" 2>/dev/null | grep -c '\.png$')" == "41" ]] && ok "and the same forty-one in dark mode ($WORK/screens-dark)" || bad "forty-one dark screens drawn (see $WORK/draw-dark.txt)"
for s in 01b-checkup-older-chatgpt 03c-assistant-unanswered 06b-trust-steps 06e-trust-proved 07b-handoff-chatgpt 07c-handoff-both 08c-home-wiki-newer 10b-home-chatgpt 12b-home-repair-wiki-newer 15a-update-asks-assistant; do
  [[ -s "$WORK/screens/$s.png" ]] || bad "  drawn: $s"
done
[[ ! -e "$WORK/home-draw/.claude" && ! -e "$WORK/home-draw/.codex" && ! -e "$WORK/home-draw/.config" ]] && ok "drawing screens installs nothing" || bad "drawing screens installs nothing"

# The decisions about the assistant, checked without a window and without running
# any of the pack's scripts: whether an update asks the question first (only when
# no choice is on record), what the updater is then told, how the line that says
# ChatGPT is waiting for the owner's trust is taken, how lines that are not
# understood are ignored, how the proof's findings are read, and the link into
# ChatGPT. Also: that Change, Update and Repair are all refused on a wiki newer
# than the app; that a Trust note left from before a change to Claude alone is
# not shown; what each way of leaving the Trust screen does to that note; what
# is read from the wiki's rules files when the choice file is lost; and a
# ChatGPT app with no agent inside it. The proof's findings are read from samples
# of the check-up's own output (app/Fixtures/prove-guard), and the check-up inside
# the app is read to see that it still says what the samples say. It writes only
# inside its own practice home.
mkdir -p "$WORK/home-logic"
"$BIN" --home "$WORK/home-logic" --check-logic --fixtures "$here/../Fixtures" > "$WORK/logic.txt" 2>&1
RC=$?
[[ $RC -eq 0 ]] && grep -q "^logic: every check held" "$WORK/logic.txt" && ! grep -q "^logic: FAILED" "$WORK/logic.txt" && ok "the app's decisions about the assistant hold (see $WORK/logic.txt)" || bad "the app's decisions about the assistant hold (exit $RC; see $WORK/logic.txt)"
grep -q "^logic: ok: with no choice on record, an update asks the question first" "$WORK/logic.txt" && grep -q "^logic: ok: and the updater is told nothing, so the record stands" "$WORK/logic.txt" && ok "  an update asks which assistant only on a Mac with no choice on record, and otherwise tells the updater nothing" || bad "  when an update asks which assistant"
grep -q "^logic: ok: lines that are not understood are ignored" "$WORK/logic.txt" && ok "  progress lines that are not understood are still ignored" || bad "  progress lines that are not understood are still ignored"
grep -q "^logic: ok: on a wiki newer than this app, Change is hidden" "$WORK/logic.txt" && grep -q "^logic: ok: and neither Change nor Update can start this app's older updater" "$WORK/logic.txt" && grep -q "^logic: ok: a guard that looks off on a newer wiki is not this app's to repair" "$WORK/logic.txt" && ok "  on a wiki newer than the app, Change, Update and Repair are all refused" || bad "  on a wiki newer than the app, Change, Update and Repair are all refused"
grep -q "^logic: ok: a waiting note is not shown to an owner whose choice is Claude alone" "$WORK/logic.txt" && grep -q "^logic: ok: Later on the steps leaves the step waiting" "$WORK/logic.txt" && ok "  the Trust step waits through Later on the steps, and is not shown to an owner of Claude alone" || bad "  the Trust note"
grep -q "^logic: ok: with no choice on record and a wiki laid down for ChatGPT alone, the choice is read as ChatGPT" "$WORK/logic.txt" && grep -q "^logic: ok: a choice on record is believed over the shape of the files" "$WORK/logic.txt" && ok "  a lost choice file is made good from the wiki's rules files, and a kept one is believed over them" || bad "  a lost choice file"
grep -q "^logic: ok: a ChatGPT app with no agent inside is an older one, not a ready one" "$WORK/logic.txt" && ok "  a ChatGPT app with no agent inside it is not taken for a ready one" || bad "  a ChatGPT app with no agent inside it"
grep -q "^logic: ok: the check-up's own sample not-running.json is read as notRunning" "$WORK/logic.txt" && grep -q "^logic: ok: the check-up in this app's pack still opens its proved line" "$WORK/logic.txt" && ok "  the proof is read from the check-up's own samples, and the check-up in the app still says what they say" || bad "  the proof's samples"
[[ ! -e "$WORK/home-logic/.claude" && ! -e "$WORK/home-logic/.codex" && ! -e "$WORK/home-logic/Wiki" ]] && ok "  and checking them installs nothing" || bad "  checking the decisions installs nothing"
( unset MOBLEE_PRACTICE; "$BIN" --check-logic > "$WORK/logic-refused.txt" 2>&1 ); [[ $? -eq 2 ]] && ok "  without a practice run the check is refused" || bad "  without a practice run the logic check is refused"

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

# --- the move to Applications -------------------------------------------------
# As an owner meets it: the app sits in a pretend Downloads carrying the mark
# macOS puts on anything downloaded, and an OLDER Moblee is already in the
# pretend Applications. Everything is the app's real code but the Mac's own Bin
# (a scratch folder stands in) and the reopening. Run after the walk through
# every screen, below: three quick openings of the app just before that walk
# left its window without the keyboard on one Mac, and the typed name never
# arrived.
move_checks() {
DL="$WORK/downloads"; APPS="$WORK/applications"; PBIN="$WORK/practice-bin"
mkdir -p "$DL" "$APPS" "$WORK/home-move"
cp -R "$APP" "$DL/Moblee.app"
xattr -w com.apple.quarantine "0081;00000000;Safari;" "$DL/Moblee.app/Contents/Info.plist" 2>/dev/null
cp -R "$APP" "$APPS/Moblee.app"
/usr/libexec/PlistBuddy -c "Set :CFBundleShortVersionString 0.0.1" "$APPS/Moblee.app/Contents/Info.plist" > /dev/null
echo "the older one" >> "$APPS/Moblee.app/Contents/old-marker.txt"
REAL_VERSION="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$APP/Contents/Info.plist")"
version_at() { /usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$1/Contents/Info.plist" 2>/dev/null; }
leftovers() { ls -A "$APPS" | grep -c '^\.Moblee-' | tr -d ' '; }

# first, a move whose new copy fails its check: nothing the owner had may change
"$DL/Moblee.app/Contents/MacOS/Moblee" --home "$WORK/home-move" --move-to "$APPS" --move-break copy --self-drive > "$WORK/move-broken.txt" 2>&1
RC=$?
[[ $RC -eq 0 ]] && grep -q "^self-drive: the broken move changed nothing and the app carried on" "$WORK/move-broken.txt" && ok "a move that cannot be completed says so, and the app carries on" || bad "a move that cannot be completed says so (exit $RC; see $WORK/move-broken.txt)"
[[ "$(version_at "$APPS/Moblee.app")" == "0.0.1" && -f "$APPS/Moblee.app/Contents/old-marker.txt" && ! -e "$PBIN" && -x "$DL/Moblee.app/Contents/MacOS/Moblee" && "$(leftovers)" == "0" ]] && ok "  and it left the older Moblee in Applications, the one in Downloads and the Bin exactly as they were, with no half-made copy behind" || bad "  a failed move changes nothing"

# then the move itself, with the real button
"$DL/Moblee.app/Contents/MacOS/Moblee" --home "$WORK/home-move" --move-to "$APPS" --self-drive > "$WORK/move.txt" 2>&1
RC=$?
MOVED="$APPS/Moblee.app"
[[ $RC -eq 0 ]] && grep -q "^self-drive: moved" "$WORK/move.txt" && ok "opened outside Applications, the app offers to move itself, and the button moves it" || bad "the app moves itself to Applications (exit $RC; see $WORK/move.txt)"
grep -q "^self-drive: ok: and nothing else has started behind the offer" "$WORK/move.txt" && ok "  nothing else starts while the offer is on screen" || bad "  nothing else starts while the offer is on screen"
[[ "$(version_at "$MOVED")" == "$REAL_VERSION" && ! -e "$MOVED/Contents/old-marker.txt" && -x "$MOVED/Contents/MacOS/Moblee" && -f "$MOVED/Contents/Resources/pack/scripts/install.sh" ]] && ok "  the new Moblee is in Applications, whole, in place of the older one" || bad "  the new Moblee is in Applications in place of the older one"
[[ "$(ls "$PBIN" 2>/dev/null | wc -l | tr -d ' ')" == "2" && -n "$(ls "$PBIN"/*/Contents/old-marker.txt 2>/dev/null)" && ! -e "$DL/Moblee.app" && -z "$(ls -A "$PBIN" | grep "^\.")" ]] && ok "  the older one and the one that was opened are both in the Bin under names that can be seen there; neither is deleted" || bad "  the older one and the opened one go to the Bin"
codesign --verify --strict "$MOVED" 2>/dev/null && ok "  the moved copy's signature is intact" || bad "  the moved copy's signature is intact"
xattr -r "$PBIN" 2>/dev/null | grep -q quarantine && ! xattr -r "$MOVED" 2>/dev/null | grep -q quarantine && ok "  the download mark is cleared from the copy (so macOS runs it from where it is)" || bad "  the download mark is cleared from the copy"
[[ "$(leftovers)" == "0" ]] && ok "  no half-made copy is left behind" || bad "  no half-made copy is left behind"
# opened again from a fresh Downloads copy of the same version: the one in Applications is used, nothing is copied over it
mkdir -p "$WORK/downloads2"; cp -R "$APP" "$WORK/downloads2/Moblee.app"; echo "kept" >> "$MOVED/Contents/kept-marker.txt"
"$WORK/downloads2/Moblee.app/Contents/MacOS/Moblee" --home "$WORK/home-move" --move-to "$APPS" --self-drive > "$WORK/move-again.txt" 2>&1
grep -q "^self-drive: already there" "$WORK/move-again.txt" && [[ -f "$MOVED/Contents/kept-marker.txt" && -x "$WORK/downloads2/Moblee.app/Contents/MacOS/Moblee" && "$(ls "$PBIN" | wc -l | tr -d ' ')" == "2" ]] && ok "  the same Moblee opened again from Downloads uses the one in Applications and copies nothing over it" || bad "  an equal version is not copied over the one in Applications (see $WORK/move-again.txt)"
}

# --- every screen, with the real window ---------------------------------------
"$BIN" --home "$WORK/home-drive" --self-drive > "$WORK/drive.txt" 2>&1
RC=$?
[[ $RC -eq 0 ]] && ok "the real window opens every screen and finishes an install" || bad "the real window opens every screen and finishes an install (exit $RC; see $WORK/drive.txt)"
for s in welcome check-up name assistant build hand-off home; do
  grep -q "^self-drive: $s" "$WORK/drive.txt" && ok "  reached: $s" || bad "  reached: $s"
done
grep -q "^self-drive: ok: Return moves on exactly one screen, to the question of which assistant" "$WORK/drive.txt" && grep -q "^self-drive: ok: nothing is chosen for the owner beforehand" "$WORK/drive.txt" && grep -q "^self-drive: ok: tapping the Claude card answers the question" "$WORK/drive.txt" && ok "the question of which assistant appears after the name, with nothing chosen beforehand, and a tap on Claude answers it" || bad "the question of which assistant appears after the name and a tap answers it"
grep -q "^self-drive: ok: the answer went to the installer as --assistant claude" "$WORK/drive.txt" && [[ "$(tr -d '[:space:]' < "$WORK/home-drive/.config/moblee/assistant" 2>/dev/null)" == "claude" ]] && grep -q "assistant: claude" "$WORK/home-drive/.config/moblee/install-diary.txt" 2>/dev/null && ok "  --assistant claude reached the installer, which kept it on record and noted it in the diary" || bad "  --assistant claude reached the installer"
grep -q "^self-drive: ok: an install for Claude asks for no Trust step" "$WORK/drive.txt" && [[ ! -e "$WORK/home-drive/.codex" && ! -e "$WORK/home-drive/.config/moblee/trust-pending" ]] && ok "  an install for Claude puts nothing of ChatGPT's on the Mac and asks for no Trust step" || bad "  an install for Claude asks for no Trust step"
grep -q "^self-drive: ok: at home the wiki is known to be for Claude, and an update would ask nothing" "$WORK/drive.txt" && ok "  at home the choice is read from the record, so an update would ask nothing" || bad "  at home the choice is read from the record"
grep -q "^self-drive: tiles waiting: trips, videos" "$WORK/drive.txt" && ok "home screen shows the two things agreed with Claude" || bad "home screen shows the two things agreed with Claude"
grep -q "^self-drive: trips ended: .*done" "$WORK/drive.txt" && [[ -f "$WORK/home-drive/.claude/skills/trips/SKILL.md" ]] && ok "pressing Add on a quiet item adds it (the skill is really there)" || bad "pressing Add on a quiet item adds it"
grep -q "^self-drive: videos ended: .*handedOver" "$WORK/drive.txt" && [[ -x "$WORK/home-drive/Library/Application Support/Moblee/run/add-videos.command" ]] && ok "a Terminal item is explained, then handed over as a command file" || bad "a Terminal item is explained, then handed over as a command file"
CMD="$WORK/home-drive/Library/Application Support/Moblee/run/add-videos.command"
grep -q "^if python3 scripts/moblee-setup.py --only videos --yes; then$" "$CMD" && ok "the command file runs the pack's own checklist for that one item, without asking 'Start now?' a third time" || bad "the command file runs the pack's own checklist for that one item"
bash -n "$CMD" 2>/dev/null && grep -q 'kill -9 "\$PPID"' "$CMD" && grep -q 'Apple_Terminal' "$CMD" && grep -q 'opened_for_this" = yes' "$CMD" && grep -q 'That did not finish' "$CMD" && ok "the command file is sound, and ends Terminal's own shell before it can print 'Deleting expired sessions'" || bad "the command file is sound and silences Terminal's closing lines"
grep -q "^self-drive: ok: the three cards are the pack's own" "$WORK/drive.txt" && ok "the Google tile says where to go, what to switch on by name, and how to tell it worked" || bad "the Google tile's three cards"
grep -q "^self-drive: google ended: .*done" "$WORK/drive.txt" && grep -q '"item:google@2026-09-20"' "$WORK/home-drive/.config/moblee/app-state.json" 2>/dev/null && ok "clicks inside Claude are finished by the owner pressing Done, and it stays done" || bad "a clicks item can be marked done"
[[ "$(ls "$WORK/home-drive/Library/Application Support/Moblee/run/" | wc -l | tr -d " ")" == "1" ]] && ok "no other command file was written" || bad "no other command file was written"
POINTS_AT="$(cat "$WORK/home-drive/.config/moblee/package-path" 2>/dev/null)"
grep -q "^self-drive: the note of where Moblee is was put right: true" "$WORK/drive.txt" && [[ -f "$POINTS_AT/scripts/moblee-doctor.py" ]] && ok "a stale note of where the Moblee folder is gets put right by the app, so the check-up compares with the right copies" || bad "a stale note of where the Moblee folder is gets put right by the app"
( cd "$WORK/home-drive" && HOME="$WORK/home-drive" /usr/bin/python3 "$POINTS_AT/scripts/moblee-doctor.py" > "$WORK/doctor-after.txt" 2>&1 )
grep -q "^self-drive: stale guard repaired: true" "$WORK/drive.txt" && cmp -s "$WORK/home-drive/.claude/hooks/bash-guard.py" "$POINTS_AT/safety/bash-guard.py" && ! grep -q "F02\|F23" "$WORK/doctor-after.txt" && ok "a guard that is on but older is noticed, Repair (really pressed) brings it level, and the check-up then has no complaint about the guard or the skills" || bad "a stale guard is noticed and repaired (see $WORK/doctor-after.txt)"
grep -q "^self-drive: ok: Not now sets a repair about differing copies aside" "$WORK/drive.txt" && ok "Not now sets aside a repair that is only about copies differing, so an owner is never shut out of their tiles" || bad "Not now on a repair about differing copies"
grep -q "^self-drive: a wiki newer than this app is left alone .*: true" "$WORK/drive.txt" && ok "an old Moblee opened on a wiki a NEWER Moblee made offers no repair with its older guard and skills, and leaves the note of where Moblee is alone" || bad "an old app must never 'repair' a newer wiki with older copies"
grep -q "^self-drive: skill gym-log ended: .*done" "$WORK/drive.txt" && [[ -f "$WORK/home-drive/.claude/skills/gym-log/.made-for-you" && ! -L "$WORK/home-drive/.claude/skills/gym-log" ]] && ok "a skill Claude drafted is shown, then added as ordinary files" || bad "a skill Claude drafted is shown, then added as ordinary files"
grep -q "^self-drive: skill sneaky: .*blocked" "$WORK/drive.txt" && [[ ! -e "$WORK/home-drive/.claude/skills/sneaky" ]] && ok "a drafted skill that is a link to outside the wiki is refused" || bad "a drafted skill that is a link to outside the wiki is refused"
grep -q "^self-drive: skill brain: .*blocked" "$WORK/drive.txt" && grep -q "brain untouched: true" "$WORK/drive.txt" && ok "a drafted skill wearing a Moblee skill's name is refused, and the real one is untouched" || bad "a drafted skill wearing a Moblee skill's name is refused"
grep -q "nothing smuggled: true" "$WORK/drive.txt" && [[ ! -e /tmp/moblee-pwned ]] && ok "a request with a command or a path in its key makes no tile and runs nothing" || bad "a request with a command or a path in its key makes no tile and runs nothing"
"$BIN" --self-drive > "$WORK/refuse2.txt" 2>&1 &
PID=$!; sleep 3
if kill -0 $PID 2>/dev/null; then kill $PID; bad "self-drive without a practice home is refused"; else wait $PID; [[ $? -eq 2 ]] && ok "self-drive without a practice home is refused" || bad "self-drive without a practice home is refused"; fi

move_checks

echo ""
echo "$PASS passed, $FAIL failed. Screens and outputs are in $WORK"
[[ $FAIL -eq 0 ]]
