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
# (v0.9.1) The guard skips its file scan for the pack's own tooling by SHA-256.
# When a hash drifts the guard refuses that script on every owner's Mac — the
# check-up among them, which is the thing owners are told to ask for when
# something is wrong. v0.9.0 shipped with six of the seven stale. The signing
# script refuses a release on this, but the signing run is the owner's and comes
# last; this is the same check in the test that is run before anyone is asked to
# open the app, which is the loop the pack is actually developed in.
if ( cd "$here/../.." && python3 safety/release-hashes.py --check ) > "$WORK/hashes.txt" 2>&1; then
  ok "the guard's pinned hashes are current"
else
  bad "the guard's pinned hashes are current — run: python3 safety/release-hashes.py"
  sed 's/^/      /' "$WORK/hashes.txt"
fi

mkdir -p "$WORK/home-draw" "$WORK/home-rehearse" "$WORK/home-drive"

# Without this the app ignores every practice switch, as a released app must.
( unset MOBLEE_PRACTICE; "$BIN" --home "$WORK/home-refused" --snapshot "$WORK/screens-refused" > "$WORK/refused.txt" 2>&1 )
[[ $? -eq 2 && ! -e "$WORK/screens-refused" && ! -e "$WORK/home-refused" ]] && ok "without MOBLEE_PRACTICE=1 a practice switch is refused outright, and nothing is touched" || bad "without MOBLEE_PRACTICE=1 a practice switch is refused outright"
export MOBLEE_PRACTICE=1
# (v0.9.4) How big the words are is kept between openings, and a practice run
# keeps its own copy of that setting rather than the owner's. It is put back to
# normal here, so that every run of this test starts at the same size whatever
# the last one left behind.
defaults write moblee.practice moblee.textSize -int 0 2>/dev/null

"$BIN" --home "$WORK/home-draw" --snapshot "$WORK/screens" > "$WORK/draw.txt" 2>&1
[[ "$(ls "$WORK/screens" 2>/dev/null | grep -c '\.png$')" == "88" ]] && ok "eighty-eight screens drawn to picture files ($WORK/screens)" || bad "eighty-eight screens drawn (see $WORK/draw.txt)"
"$BIN" --dark --home "$WORK/home-draw" --snapshot "$WORK/screens-dark" > "$WORK/draw-dark.txt" 2>&1
[[ "$(ls "$WORK/screens-dark" 2>/dev/null | grep -c '\.png$')" == "88" ]] && ok "and the same eighty-eight in dark mode ($WORK/screens-dark)" || bad "eighty-eight dark screens drawn (see $WORK/draw-dark.txt)"
# (v0.9.4) The eleven added: how the move ends, in each of its ways (none of
# which had ever been drawn), how an UPDATE ends, in each of its four ways (only
# the running state had been drawn), and a skill wearing a Moblee name that no
# Moblee left there.
# (v0.9.5) And the four at the end: something dropped on Moblee. The receipt
# with one thing on it and the receipt with several (which carries every part of
# it at once — the count, the names, how many more there were, and one that did
# not go), and the two refusals that matter most: there is no wiki yet, and it
# was a folder. None of the four can be reached without really dropping a file
# on a real window, which is why they are set here to be looked at.
# (v0.9.6) And the five at the end: the check-up an owner runs themselves. While
# it runs, a wiki that looks healthy, a wiki with things to look at, and the two
# refusals that matter most — no wiki on this Mac at all, and a Moblee that
# cannot find its own check-up. Each of those needs the pack's check-up really
# run against a real wiki, so they too are set to be looked at.
for s in 01b-checkup-older-chatgpt 03c-assistant-unanswered 06a-trust-open-folder 06b-trust-steps 06e-trust-proved 07b-handoff-chatgpt 07c-handoff-both 08c-home-wiki-newer 10b-home-chatgpt 12b-home-repair-wiki-newer 15a-update-asks-assistant 08d-home-newer-release 11b-home-update-newer-release-hidden \
         00b-move-asking-the-other-one 00c-move-failed-copy 00d-move-failed-something-else 00e-move-failed-another-open 00f-move-failed-other-busy 00g-move-failed-mark \
         15b-update-finished 15c-update-finished-partial 15d-update-refused 15e-update-failed 12c-home-skill-not-moblees \
         13b-explain-terminal-two 13c-explain-terminal-three \
         19a-biggest-home-waiting 19b-biggest-explain-terminal 19c-biggest-update-refused \
         20a-keyboard-ring-tile 20b-keyboard-ring-not-now 20c-keyboard-ring-assistant \
         02b-name-arabic 03g-promise-arabic-name 07d-handoff-arabic-name \
         21a-drop-receipt-one 21b-drop-receipt-several 21c-drop-no-wiki 21d-drop-folder \
         19d-biggest-trust-steps 19e-biggest-handoff 19f-biggest-checkup 19g-biggest-drop-receipt \
         22a-keyboard-ring-listen-tile 22b-keyboard-ring-listen-step \
         23a-example-welcome 23b-example-page 23c-example-pages 23d-example-link-missing \
         19h-biggest-example-page 19i-biggest-example-pages \
         24a-clinic-running 24b-clinic-healthy 24c-clinic-problems 24d-clinic-no-wiki 24e-clinic-no-checkup 24f-home-check-my-wiki-while-busy; do
  [[ -s "$WORK/screens/$s.png" ]] || bad "  drawn: $s"
done
# (v0.9.6) The last six: the check-up an owner runs themselves. While it runs, a
# wiki that looks healthy, a wiki with things to look at, and the two refusals
# that matter most — no wiki on this Mac at all, and a Moblee that cannot find
# its own check-up. Each of those needs the pack's check-up really run against a
# real wiki, so they too are set here to be looked at. The sixth is the home
# screen with a dropped file still copying, where "Check my wiki" is greyed:
# the one state of that button an owner can actually meet, since a repair takes
# the whole corner away instead.
# (v0.9.6) The six before those: the example wiki, being read. An owner is
# asked to build a wiki without ever having seen one, so nine written pages ship
# inside the app and these are the four states of reading them — the page it
# opens on, a content page with its links, the list of every page, and a link
# that leads nowhere, which the shipped example never contains and which can
# therefore only be looked at by following one on purpose. The page and the list
# are drawn at the biggest size as well, because a screen made of a page of words
# is exactly what comes apart when the words are made half as big again.
# (v0.9.5) The six before those: "Read it to me" is now beside every block of words
# rather than beside the big sentence alone, and the risk in that is the layout,
# on screens that are already full, at the biggest text size. So the four screens
# that carry the most of the new controls are drawn at that size — the five Trust
# steps with one at the end of each line, the hand-off's three cards, the
# check-up's three cards, and the drop receipt's card of names — and the keyboard
# ring is drawn on the two smallest of them, because a ring nobody can see is no
# ring and these are 16-point symbols on a card's own corner.
# (v0.9.4) The three drawn at the biggest size an owner can set are drawn on
# the smallest window that size can be shown in — 1080 by 780 rather than 720
# by 520 — so a picture that is still 720 wide means the words grew and the
# window did not, which is how a screen ends up cut off.
big_enough() { [[ "$(sips -g pixelWidth "$1" 2>/dev/null | awk '/pixelWidth/{print $2}')" == "2160" ]]; }
if big_enough "$WORK/screens/19a-biggest-home-waiting.png" && big_enough "$WORK/screens-dark/19c-biggest-update-refused.png" \
   && big_enough "$WORK/screens/19d-biggest-trust-steps.png" && big_enough "$WORK/screens/19e-biggest-handoff.png" \
   && big_enough "$WORK/screens/19f-biggest-checkup.png" && big_enough "$WORK/screens-dark/19g-biggest-drop-receipt.png" \
   && big_enough "$WORK/screens/19h-biggest-example-page.png" && big_enough "$WORK/screens-dark/19i-biggest-example-pages.png"; then
  ok "  and the screens drawn at the biggest size are drawn on a window that grew with the words"
else
  bad "  the screens drawn at the biggest size are drawn on a bigger window"
fi
# The switch that draws them is a practice switch, and only takes 0, 1 or 2.
( unset MOBLEE_PRACTICE; "$BIN" --text-scale 2 --home "$WORK/home-scale" --snapshot "$WORK/screens-scale" > "$WORK/scale-refused.txt" 2>&1 )
[[ $? -eq 2 && ! -e "$WORK/screens-scale" ]] && ok "  outside a practice run --text-scale is refused, and nothing is drawn" || bad "  outside a practice run --text-scale is refused"
"$BIN" --text-scale 9 --home "$WORK/home-scale" --snapshot "$WORK/screens-scale" > "$WORK/scale-bad.txt" 2>&1
[[ $? -eq 2 ]] && grep -q "0 (normal), 1 (bigger) or 2 (biggest)" "$WORK/scale-bad.txt" && ok "  and a size that is not one of the three is refused, saying which three" || bad "  a --text-scale that is not one of the three is refused"
# (v0.9.4) And the same screens laid out RIGHT TO LEFT, as macOS lays out any
# app on a Mac whose own language is read that way — Arabic, Hebrew, Persian,
# Urdu. Moblee had never once been looked at in that state. `--rtl` mirrors a
# whole run, every screen in it, so this is the same list drawn again rather
# than a list of its own; a later version puts both appearances and both
# directions on one page from the same switch.
"$BIN" --rtl --home "$WORK/home-draw" --snapshot "$WORK/screens-rtl" > "$WORK/draw-rtl.txt" 2>&1
[[ "$(ls "$WORK/screens-rtl" 2>/dev/null | grep -c '\.png$')" == "88" ]] && ok "and all eighty-eight again laid out right to left ($WORK/screens-rtl)" || bad "eighty-eight mirrored screens drawn (see $WORK/draw-rtl.txt)"
"$BIN" --rtl --dark --home "$WORK/home-draw" --snapshot "$WORK/screens-rtl-dark" > "$WORK/draw-rtl-dark.txt" 2>&1
[[ "$(ls "$WORK/screens-rtl-dark" 2>/dev/null | grep -c '\.png$')" == "88" ]] && ok "  and in dark mode too ($WORK/screens-rtl-dark)" || bad "eighty-eight mirrored dark screens drawn (see $WORK/draw-rtl-dark.txt)"
# A switch that drew the same picture twice would pass every count above, so
# the key screens are required to have really come out different. These are the
# ones the eye was put on: the welcome picture, the check-up, the name with an
# Arabic name typed in, the question of which assistant, the promise, the build,
# the hand-off, the home screen with tiles waiting, and the move to Applications.
mirrored_really() {
  local n=0
  for s in 00-welcome 01-checkup 02b-name-arabic 03c-assistant-unanswered 03b-promise \
           04-build-running 07-handoff 08-home-waiting 00a-move-to-applications; do
    cmp -s "$WORK/screens/$s.png" "$WORK/screens-rtl/$s.png" && { echo "      same both ways: $s"; return 1; }
    [[ -s "$WORK/screens-rtl/$s.png" ]] || { echo "      missing: $s"; return 1; }
    n=$((n+1))
  done
  [[ $n -eq 9 ]]
}
if mirrored_really; then
  ok "  and the nine key screens really are drawn mirrored, not merely drawn again"
else
  bad "  the mirrored screens must differ from the ones laid out left to right"
fi
( unset MOBLEE_PRACTICE; "$BIN" --rtl --home "$WORK/home-rtl-refused" --snapshot "$WORK/screens-rtl-refused" > "$WORK/rtl-refused.txt" 2>&1 )
[[ $? -eq 2 && ! -e "$WORK/screens-rtl-refused" ]] && ok "  outside a practice run --rtl is refused, so a released Moblee follows the Mac's own direction" || bad "  outside a practice run --rtl is refused"
[[ ! -e "$WORK/home-draw/.claude" && ! -e "$WORK/home-draw/.codex" && ! -e "$WORK/home-draw/.config" ]] && ok "drawing screens installs nothing" || bad "drawing screens installs nothing"

# The decisions about the assistant, checked without a window and without running
# any of the pack's scripts: whether an update asks the question first (only when
# no choice is on record), what the updater is then told, how the line that says
# ChatGPT is waiting for the owner's trust is taken (and that a repair or an
# update which only replaced ChatGPT's guard file sets nothing waiting, since
# ChatGPT's trust follows the entry in its hooks list), how lines that are not
# understood are ignored, how the proof's findings are read, and the link into
# ChatGPT. Also: that Change, Update and Repair are all refused on a wiki newer
# than the app; that a Trust note left from before a change to Claude alone is
# not shown; what each way of leaving the Trust screen does to that note; what
# is read from the wiki's rules files when the choice file is lost; and a
# ChatGPT app with no agent inside it; that the Trust screen begins at opening
# the wiki folder in ChatGPT, before the five steps; and the hand-off's words
# (the File menu's Open Folder and then Work for ChatGPT, Claude's unchanged). The proof's findings are read from samples
# of the check-up's own output (app/Fixtures/prove-guard), and the check-up inside
# the app is read to see that it still says what the samples say. It writes only
# inside its own practice home.
mkdir -p "$WORK/home-logic"
"$BIN" --home "$WORK/home-logic" --check-logic --fixtures "$here/../Fixtures" > "$WORK/logic.txt" 2>&1
RC=$?
[[ $RC -eq 0 ]] && grep -q "^logic: every check held" "$WORK/logic.txt" && ! grep -q "^logic: FAILED" "$WORK/logic.txt" && ok "the app's decisions about the assistant hold (see $WORK/logic.txt)" || bad "the app's decisions about the assistant hold (exit $RC; see $WORK/logic.txt)"
grep -q "^logic: ok: with no choice on record, an update asks the question first" "$WORK/logic.txt" && grep -q "^logic: ok: and the updater is told nothing, so the record stands" "$WORK/logic.txt" && ok "  an update asks which assistant only on a Mac with no choice on record, and otherwise tells the updater nothing" || bad "  when an update asks which assistant"
grep -q "^logic: ok: lines about steps the app does not count are ignored" "$WORK/logic.txt" && ok "  progress lines about steps the app does not count are ignored" || bad "  progress lines about steps the app does not count are ignored"
# (v0.9.1) The three that stop a refused commit reading as success. This layer —
# the progress protocol between the scripts and the app — was the one nothing
# tested, which is how the fault reached a release.
grep -q "^logic: ok: an unknown state on a counted step is not treated as success" "$WORK/logic.txt" && ok "  an unknown state on a counted step is not success" || bad "  an unknown state on a counted step is not success"
grep -q "^logic: ok: needs-commit is recorded and the step is not shown as broken" "$WORK/logic.txt" && ok "  a refused commit is recorded without marking the step broken" || bad "  a refused commit is recorded without marking the step broken"
grep -q "^logic: ok: a refused commit does not end as finished" "$WORK/logic.txt" && ok "  a refused commit never ends as finished" || bad "  a refused commit never ends as finished"
# (v0.9.2) The check-up's codes against the companion's field guide. Tier 4 of
# the code review found one code carrying seven unrelated faults, four findings
# carrying none at all against a promise that all of them do, and eleven entries
# nothing could reach. All three are the kind of drift that only shows when
# somebody counts, so something counts them now.
if ( cd "$here/../.." && python3 tools/check-codes.py ) > "$WORK/codes.txt" 2>&1; then
  ok "the check-up's codes and the field guide agree"
else
  bad "the check-up's codes and the field guide agree"
  sed 's/^/      /' "$WORK/codes.txt"
fi
grep -q "^logic: ok: a partly-finished step is recorded and is not shown as broken" "$WORK/logic.txt" && grep -q "^logic: ok: and the run still finishes, with the screen able to say so" "$WORK/logic.txt" && ok "  a step that finished while a part of it did not is recorded, and the run still finishes" || bad "  a partly-finished step is recorded and the run still finishes"
grep -q "^logic: ok: on a wiki newer than this app, Change is hidden" "$WORK/logic.txt" && grep -q "^logic: ok: and neither Change nor Update can start this app's older updater" "$WORK/logic.txt" && grep -q "^logic: ok: a guard that looks off on a newer wiki is not this app's to repair" "$WORK/logic.txt" && ok "  on a wiki newer than the app, Change, Update and Repair are all refused" || bad "  on a wiki newer than the app, Change, Update and Repair are all refused"
grep -q "^logic: ok: a waiting note is not shown to an owner whose choice is Claude alone" "$WORK/logic.txt" && grep -q "^logic: ok: Later on the steps leaves the step waiting" "$WORK/logic.txt" && ok "  the Trust step waits through Later on the steps, and is not shown to an owner of Claude alone" || bad "  the Trust note"
grep -q "^logic: ok: a repair or an update that only replaced ChatGPT's guard file sets no Trust step waiting" "$WORK/logic.txt" && ok "  a repair or an update that only replaced ChatGPT's guard file sets no Trust step waiting; only the scripts' own line does" || bad "  a replaced guard file alone sets no Trust step waiting"
grep -q "^logic: ok: the Trust screen begins at opening the wiki folder, before the steps" "$WORK/logic.txt" && grep -q "^logic: ok: a guard seen not running sends the owner to the folder first, then the five steps" "$WORK/logic.txt" && grep -q "^logic: ok: Later on opening the folder leaves the step waiting" "$WORK/logic.txt" && ok "  the wiki folder is opened in ChatGPT before the five steps, and Later there leaves the step waiting" || bad "  the wiki folder is opened in ChatGPT before the five steps"
grep -q "^logic: ok: the hand-off for ChatGPT has the owner open the wiki folder, then choose Work, then say the words" "$WORK/logic.txt" && grep -q "^logic: ok: the hand-off for ChatGPT names both Open Folder and Work, on its pictures and read aloud" "$WORK/logic.txt" && grep -q "^logic: ok: for both, ChatGPT's line is the File menu's Open Folder, the wiki folder, then Work" "$WORK/logic.txt" && grep -q "^logic: ok: Work is named to ChatGPT's owner alone: never in Claude's hand-off, never on the Trust screen" "$WORK/logic.txt" && grep -q "^logic: ok: nothing on the Trust screen or the hand-off tells an owner to make a project" "$WORK/logic.txt" && grep -q "^logic: ok: Claude's hand-off is word for word as it has always been, but for the plan line" "$WORK/logic.txt" && ok "  the hand-off sends ChatGPT's owner to the File menu's Open Folder and then to Work, never to a project, and Claude's three steps are unchanged" || bad "  the hand-off's words"
# (v0.9.4) The Code tab is not on the free plan. docs/02-install.md has said so
# since the app route was written; an owner on the free plan was sent to click
# Code and found nothing there, with nothing on the screen to explain it.
grep -q "^logic: ok: the hand-off says the Code tab needs a paid Claude plan, to an owner of Claude and to an owner of both" "$WORK/logic.txt" && grep -q "^logic: ok: and says nothing of plans to an owner of ChatGPT alone, who never opens Claude" "$WORK/logic.txt" && ok "  the hand-off says the Code tab needs a paid Claude plan, and says it only where Claude is used" || bad "  the paid-plan line at the hand-off"
# And the app says it in the very words the document does.
grep -qF "The Code tab in Claude's app needs a paid Claude plan." "$here/../../docs/02-install.md" && grep -qF 'static let paidPlan = "The Code tab in Claude'"'"'s app needs a paid Claude plan."' "$here/../Sources/Moblee/HandoffScreen.swift" && ok "  in the same words as docs/02-install.md" || bad "  the app and the document say the same words"
grep -q "^logic: ok: with no choice on record and a wiki laid down for ChatGPT alone, the choice is read as ChatGPT" "$WORK/logic.txt" && grep -q "^logic: ok: a choice on record is believed over the shape of the files" "$WORK/logic.txt" && ok "  a lost choice file is made good from the wiki's rules files, and a kept one is believed over them" || bad "  a lost choice file"
grep -q "^logic: ok: a ChatGPT app with no agent inside is an older one, not a ready one" "$WORK/logic.txt" && ok "  a ChatGPT app with no agent inside it is not taken for a ready one" || bad "  a ChatGPT app with no agent inside it"
grep -q "^logic: ok: the check-up's own sample not-running.json is read as notRunning" "$WORK/logic.txt" && grep -q "^logic: ok: the check-up in this app's pack still opens its proved line" "$WORK/logic.txt" && ok "  the proof is read from the check-up's own samples, and the check-up in the app still says what they say" || bad "  the proof's samples"
# (v0.9.4) The install diary a Repair leaves. Repair changes an owner's Mac and
# used to write nothing at all, so the check-up, which reads the diary, could
# not see that it had happened. The redaction is the scripts' own: an owner's
# name must never reach the file, and the wiki's folder name is how it would.
grep -q "^logic: ok: the diary writes the wiki's place, and its folder name, as <wiki>" "$WORK/logic.txt" && grep -q "^logic: ok: the home folder is written as ~, so the diary carries no account name" "$WORK/logic.txt" && grep -q "^logic: ok: an owner's name never reaches the diary, not even through the wiki's folder name" "$WORK/logic.txt" && ok "  the diary redacts the wiki's place, its folder name and the home folder, as the installer's own diary does" || bad "  the diary's redaction"
grep -q "^logic: ok: the diary is added to and never replaced, one stamped line at a time" "$WORK/logic.txt" && grep -q "^logic: ok: a step's own output is kept, but never without end" "$WORK/logic.txt" && ok "  the diary is added to, stamped line by line, and a step's output is kept but bounded" || bad "  the diary is added to and never replaced"
# (v0.9.4) A newer app opened while an older Moblee is in Applications: it asks
# that one to close instead of refusing, and the two ways that can end say two
# different things — an owner mid-install is never sent to close the app that
# is doing the installing.
grep -q "^logic: ok: a copy that took the quit request and stayed is busy; one that could not be asked is merely open" "$WORK/logic.txt" && grep -q "^logic: ok: the two say different things, and the busy one says why" "$WORK/logic.txt" && grep -q "^logic: ok: every way a move can fail has a sentence; the three an owner can act on have their own, and only the two that changed nothing share the general advice" "$WORK/logic.txt" && ok "  a move that another Moblee blocks says which of the two it was, and the three failures an owner can act on each have their own words" || bad "  the move's refusals"
# (v0.9.4) The live failure of 24 September: an earlier Moblee's copy of a skill
# was taken for somebody else's, so the app offered, for ever, a repair whose
# script would not replace it.
grep -q "^logic: ok: an earlier Moblee's copy of a skill is recognised as Moblee's, by its content, from the packs left on this Mac" "$WORK/logic.txt" && grep -q "^logic: ok: a skill that is missing altogether is a repair, not something of the owner's" "$WORK/logic.txt" && grep -q "^logic: ok: this Moblee's own copies in place ask for nothing" "$WORK/logic.txt" && ok "  an earlier Moblee's copy of a skill is recognised as Moblee's, from the packs left on this Mac" || bad "  an earlier Moblee's copy of a skill"
grep -q "^logic: ok: a skill matching no Moblee pack is named, and is never taken for one a repair can replace" "$WORK/logic.txt" && grep -q "^logic: ok: and the screen says which skill it is and what to do about it" "$WORK/logic.txt" && grep -q "^logic: ok: more than one is named together, and a long list is cut short" "$WORK/logic.txt" && ok "  a skill that is nobody's of Moblee's is named, with what to do, instead of a repair that cannot succeed" || bad "  a skill that is not Moblee's is named"
grep -q "^logic: ok: a skill the app has proved an earlier Moblee left is written into the skills script's own record, and the owner's is not" "$WORK/logic.txt" && grep -q "^logic: ok: and writing it down a second time adds nothing" "$WORK/logic.txt" && ok "  and what the app proves is written into the skills script's own record, so the repair it offers is one the script can make" || bad "  the app writes its proof into the skills script's record"
grep -q "^logic: ok: a name in the skills script's own record is Moblee's, and one that is not there is not" "$WORK/logic.txt" && grep -q "^logic: ok: with no record at all, Claude's folder counts as Moblee's and ChatGPT's does not, as the script itself decides" "$WORK/logic.txt" && grep -q "^logic: ok: two folders holding the same files match" "$WORK/logic.txt" && grep -q "^logic: ok: nor does the same file with different words in it" "$WORK/logic.txt" && ok "  the app asks exactly the two questions the skills script asks before it will replace a skill" || bad "  the app and the skills script ask the same questions"
# The skills script's second proof, read in the script itself: the app's judgement
# is worth nothing if the script it then runs still refuses to replace the skill.
grep -q "ours_by_content()" "$here/../../scripts/install-skills.sh" && grep -q 'ours_by_content "\$name" "\$dst"' "$here/../../scripts/install-skills.sh" && ok "  and the skills script itself will replace a skill it can prove, by content, an earlier Moblee left" || bad "  the skills script's content proof"
[[ ! -e "$WORK/home-logic/.claude" && ! -e "$WORK/home-logic/.codex" && ! -e "$WORK/home-logic/Wiki" ]] && ok "  and checking them installs nothing" || bad "  checking the decisions installs nothing"
# (v0.9.4) How big the words are. The window was nailed to 720 by 520 and every
# size in the app is written in points, so an owner with poor eyesight could do
# nothing at all about it: macOS's own text-size setting reaches none of it.
grep -q "^logic: ok: the three steps are normal, a quarter bigger, and half as big again" "$WORK/logic.txt" && grep -q "^logic: ok: one press moves on one step, and round again from the biggest" "$WORK/logic.txt" && ok "  three text sizes, and one control that moves round them" || bad "  the three text sizes"
grep -q "^logic: ok: at the biggest, a size, a card's width and the window's least size have all grown together" "$WORK/logic.txt" && grep -q "^logic: ok: and a card 200 points wide is never left 200 points wide while its words grow" "$WORK/logic.txt" && ok "  the words, the cards and the window's least size all grow together, so a big word is never left in a small card" || bad "  everything grows together"
grep -q "^logic: ok: the step is kept under Moblee's own key" "$WORK/logic.txt" && grep -q "^logic: ok: and is read back as itself by an app opening afresh" "$WORK/logic.txt" && grep -q "^logic: ok: nothing else kept in the same settings is disturbed" "$WORK/logic.txt" && ok "  the size an owner sets is still there when the app is opened again, under Moblee's own key, disturbing nothing else" || bad "  the text size is kept between openings"
grep -q "^logic: ok: an owner who has never set it reads as normal" "$WORK/logic.txt" && grep -q "^logic: ok: a step some later Moblee knows and this one does not is read as normal, never refused" "$WORK/logic.txt" && ok "  no setting, or one this Moblee does not understand, reads as normal rather than shutting the owner out" || bad "  an unreadable text size falls back to normal"
grep -q "^logic: ok: drawing a screen at a bigger size leaves the owner's own choice exactly as it was" "$WORK/logic.txt" && ok "  and drawing a screen bigger for a test never changes what the owner set" || bad "  --text-scale must not change the owner's setting"
# (v0.9.4) Laid out right to left. Most of the mirroring is SwiftUI's own; what
# is left is a handful of decisions — which way the back arrow points, which
# side a corner control sits on, which side a new screen slides in from — and
# nothing tested any of them, because the app had never been in that state.
grep -q "^logic: ok: the back arrow points the way back goes" "$WORK/logic.txt" && grep -q "^logic: ok: and so is the arrow that means \"to there\"" "$WORK/logic.txt" && ok "  the two arrows that mean a direction turn round with the words" || bad "  the arrows that mean a direction"
grep -q "^logic: ok: a new screen arrives from the side \"on\" is on" "$WORK/logic.txt" && grep -q "^logic: ok: and the screen before it leaves by the other side" "$WORK/logic.txt" && ok "  a new screen still arrives from the direction \"on\" means when the layout is mirrored" || bad "  which side a new screen slides in from"
grep -q "^logic: ok: which assistant sits in the far bottom corner" "$WORK/logic.txt" && grep -q "^logic: ok: the two quiet lines at the bottom are never in the same corner" "$WORK/logic.txt" && grep -q "^logic: ok: \"Bigger text\" is in the corner the reading ends at" "$WORK/logic.txt" && ok "  the corner controls swap over together and never land in the same corner" || bad "  the corner controls when the layout is mirrored"
grep -q "^logic: ok: an arrow that is a letter in a sentence is left alone" "$WORK/logic.txt" && ok "  and an arrow inside an English sentence is left alone, because the sentence keeps its own direction" || bad "  an arrow inside a sentence must not be turned round"
# (v0.9.4) An owner whose own name is not written in English, on a Mac that is.
grep -q "^logic: ok: a name typed in Arabic is kept exactly as typed, and the wiki folder is called after it" "$WORK/logic.txt" && grep -q "^logic: ok: a name mixing Arabic and English is taken by its first word" "$WORK/logic.txt" && grep -q "^logic: ok: and a name in English is still taken by its first word, exactly as before" "$WORK/logic.txt" && ok "  an Arabic name, a mixed one and an English one all make the wiki folder name the same way" || bad "  the wiki folder name from a name that is not in English"
grep -q "^logic: ok: no invisible mark ever reaches the folder's name or the place it is made in" "$WORK/logic.txt" && grep -q "^logic: ok: nor what is read aloud, which is left plain" "$WORK/logic.txt" && grep -q "^logic: ok: the marks are invisible ones" "$WORK/logic.txt" && ok "  the marks that let a name stand on its own in a sentence reach no folder, no path and no voice" || bad "  the marks must not reach a folder, a path or the voice"
# (v0.9.4) Escape, and the places it must do nothing.
grep -q "^logic: ok: Escape does what \"Not now\" does" "$WORK/logic.txt" && grep -q "^logic: ok: and nothing at all where the quiet words are something else, or where there are none" "$WORK/logic.txt" && ok "  Escape is \"Not now\", and is nothing at all where the quiet words are Open Claude, Later, or missing" || bad "  where Escape does and does not fire"
# (v0.9.4) The Terminal explanation, one picture at a time.
grep -q "^logic: ok: there are three pictures, in the words they have always had" "$WORK/logic.txt" && grep -q "^logic: ok: the big button says Next until the last of them, and only then opens the window" "$WORK/logic.txt" && grep -q "^logic: ok: and the owner is told which of the three they are on, in words" "$WORK/logic.txt" && ok "  the Terminal explanation is three pictures shown one at a time, in the same words, with where the owner is said plainly" || bad "  the Terminal explanation one at a time"
# (v0.9.5) Dropping a file, a photo or some words on Moblee. The whole of it,
# without a window: what lands in the wiki's inbox, what is refused and in whose
# words, what the diary is told, and — the promise the feature is built round —
# that the thing the owner dropped is still exactly where it was, byte for byte,
# after every one of those. Getting something into the wiki used to mean knowing
# where the wiki folder is in Finder; owners do not do that.
grep -q "^logic: ok: a file dropped on Moblee lands in the wiki's inbox under its own name" "$WORK/logic.txt" && grep -q "^logic: ok: and what landed is the same bytes as what was dropped" "$WORK/logic.txt" && grep -q "^logic: ok: several files dropped at once all land, in the order they were dropped" "$WORK/logic.txt" && grep -q "^logic: ok: and there is one receipt, which says how many" "$WORK/logic.txt" && ok "a file dropped on Moblee lands in the wiki's inbox, and several at once give one receipt that says how many" || bad "  a file, and several files, dropped on Moblee"
# The central promise, asked of every path including the ones that refuse.
grep -q "^logic: ok: the file the owner dropped is still exactly where it was, byte for byte, with its size and its date" "$WORK/logic.txt" && grep -q "^logic: ok: and every one of the originals is untouched" "$WORK/logic.txt" && grep -q "^logic: ok: and the enormous file is still exactly where it was" "$WORK/logic.txt" && grep -q "^logic: ok: and that file is untouched too" "$WORK/logic.txt" && grep -q "^logic: ok: and it does nothing at all to what was dropped" "$WORK/logic.txt" && ok "  it copies: the original is still where it was, byte for byte, after a drop that worked and after every one that was refused" || bad "  the original must never be moved or changed"
grep -q "^logic: ok: a name already taken in the inbox gets a number, the way a wiki folder's name does" "$WORK/logic.txt" && grep -q "^logic: ok: and the file already there is left exactly as it was" "$WORK/logic.txt" && grep -q "^logic: ok: and a third of the same name goes on counting up" "$WORK/logic.txt" && grep -q "^logic: ok: the numbering keeps the ending, which is what says what kind of file it is" "$WORK/logic.txt" && ok "  a name already taken in the inbox gets a number, and the file already there is never overwritten" || bad "  a name already taken in the inbox"
grep -q "^logic: ok: words dropped become one plain markdown file with a dated name" "$WORK/logic.txt" && grep -q "^logic: ok: the file says the words were dropped on the app rather than written into the wiki" "$WORK/logic.txt" && grep -q "^logic: ok: and the owner's words are in it, exactly as they typed them, with nothing round them lost" "$WORK/logic.txt" && ok "  words dropped become a dated markdown file that says where they came from" || bad "  words dropped on Moblee"
grep -q "^logic: ok: a folder is refused, and nothing of it is copied in" "$WORK/logic.txt" && grep -q "^logic: ok: and the folder itself is still there, with what was in it" "$WORK/logic.txt" && grep -q "^logic: ok: the words say what to do instead, and say nothing technical" "$WORK/logic.txt" && ok "  a folder is refused out loud, left exactly as it is, and the owner is told to open it and drop what is inside" || bad "  a folder dropped on Moblee"
grep -q "^logic: ok: something bigger than Moblee takes is refused, and the refusal says the size in the megabytes Finder shows" "$WORK/logic.txt" && grep -q "^logic: ok: a file Moblee cannot read is refused out loud, and never half-copied" "$WORK/logic.txt" && grep -q "^logic: ok: a file that is not there at all is refused rather than passed over in silence" "$WORK/logic.txt" && ok "  something enormous, something unreadable and something that is not there are each refused out loud" || bad "  the refusals for enormous, unreadable and missing"
grep -q "^logic: ok: a drop on a Mac with no wiki yet says plainly that the wiki has to be made first" "$WORK/logic.txt" && grep -q "^logic: ok: a drop while a wiki is being made, updated or repaired is refused, and says to wait" "$WORK/logic.txt" && grep -q "^logic: ok: and a repair stops a drop for the same reason an install does" "$WORK/logic.txt" && ok "  a drop with no wiki, and a drop into the middle of an install or a repair, are both refused rather than silently doing nothing" || bad "  a drop with no wiki, and a drop while busy"
# The diary. A dropped file's name is the owner's own content and no redaction
# could ever see inside it, so it is not written at all; see `Inbox.diaryLines`.
grep -q "^logic: ok: a drop writes itself into the install diary, the way a repair does" "$WORK/logic.txt" && grep -q "^logic: ok: and the diary carries no file name of what was dropped, because that is the owner's own content" "$WORK/logic.txt" && grep -q "^logic: ok: nor the wiki's place, its folder name, or the home folder" "$WORK/logic.txt" && grep -q "^logic: ok: every line a drop can write is free of names and paths" "$WORK/logic.txt" && ok "  a drop writes a line in the install diary saying how many landed, and never what was dropped" || bad "  the diary line a drop writes"
grep -q "^logic: ok: a dropped name can never reach out of the inbox, whatever it says" "$WORK/logic.txt" && grep -q "^logic: ok: and a name longer than a Mac takes is cut short with its ending kept" "$WORK/logic.txt" && ok "  a dropped name is treated as untrusted, and can never reach out of the inbox" || bad "  a dropped name is treated as untrusted"
# (v0.9.5) THE PROMISE, MADE STRUCTURALLY TRUE. It used to rest on asking
# whether a name was free and then calling `moveItem`, whose own guard is the
# same pair of steps and ends in `rename(2)`, which replaces without a word. Two
# things arriving at one name in that gap both passed both guards, both were
# told they had landed, and one was destroyed — six times out of six against a
# driver. The last step is now one operation the kernel either does or refuses.
grep -q "^logic: ok: two drops at the very same moment, both of a file with the same name, both land and neither is destroyed" "$WORK/logic.txt" && grep -q "^logic: ok: and every one of the two-at-a-time files is whole, so not one of them was written over" "$WORK/logic.txt" && grep -q "^logic: ok: every name the two of them landed under is a name of its own" "$WORK/logic.txt" && grep -q "^logic: ok: and neither of the two files the owner raced is touched" "$WORK/logic.txt" && ok "  two drops racing for the same name in the inbox both land, under names of their own, and neither file is ever written over" || bad "  two drops at once must not destroy one another's file"
grep -q "^logic: ok: the hidden name Moblee gives a half-made copy is a whole one, so two drops can never pick the same" "$WORK/logic.txt" && ok "  and the hidden name a half-made copy wears is a whole one, so no drop can ever delete another's file by picking the same" || bad "  the hidden name of a half-made copy must be a whole one"
grep -q "^logic: ok: a drop leaves alone the half-made copy another drop is writing this moment" "$WORK/logic.txt" && grep -q "^logic: ok: but does sweep up one left behind by a run that was cut off" "$WORK/logic.txt" && grep -q "^logic: ok: and its own file lands all the same" "$WORK/logic.txt" && ok "  and a drop no longer sweeps away the half-made copy another drop is still writing, while still tidying up after a run that was cut off" || bad "  one drop must not sweep away another's half-made copy"
# (v0.9.5) The length a filesystem stops at is counted in bytes, and one letter
# can be four of them. A long name used to pass a count of letters and then fail
# inside `copyItem`, and the owner was shown "Moblee could not put that in your
# wiki… Tell Claude" over a file that was perfectly readable.
grep -q "^logic: ok: a name is cut to the bytes a filesystem takes and not to a count of letters" "$WORK/logic.txt" && grep -q "^logic: ok: and a name cut short is never cut through the middle of a letter" "$WORK/logic.txt" && grep -q "^logic: ok: a long name really lands, rather than being refused with a sentence about telling an assistant" "$WORK/logic.txt" && grep -q "^logic: ok: and what landed wears a name cut to fit, with nothing else lost" "$WORK/logic.txt" && ok "  a long name is cut to the bytes a filesystem really takes, never through the middle of a letter, and the file lands" || bad "  a long name is cut by bytes and lands"
# And a name that cannot be a file name at all is its own refusal: nothing
# failed, so the owner is not sent to bother their assistant about it.
grep -q "^logic: ok: a name that cannot be a file name says so, and does not send the owner to their assistant" "$WORK/logic.txt" && grep -q "^logic: ok: and a real file whose whole name is full stops is refused for that reason and no other" "$WORK/logic.txt" && grep -q "^logic: ok: and that file is left exactly as it was" "$WORK/logic.txt" && ok "  a name that cannot be a file name is refused in its own words, and the owner is told to rename it rather than to fetch help" || bad "  a name that cannot be a file name"
# (v0.9.5) A photo with no file behind it. README, CHANGELOG and the wiki's own
# HOW-TO-ADD-CONTENT all say "drag a file, a photo or a piece of text", and an
# image dragged out of a web page carries only the picture's bytes: Moblee asked
# macOS for files and words alone, so the drag was never offered to it at all —
# it bounced back and nothing was said.
grep -q "^logic: ok: a picture dragged with no file behind it is read back as a picture" "$WORK/logic.txt" && grep -q "^logic: ok: a picture dragged out of a web page is taken as the picture, not as the page's address" "$WORK/logic.txt" && grep -q "^logic: ok: a dropped picture becomes a dated picture file in the inbox, with the right ending" "$WORK/logic.txt" && grep -q "^logic: ok: and a second picture the same day gets a number rather than replacing the first" "$WORK/logic.txt" && grep -q "^logic: ok: the window asks macOS for pictures as well as files and words" "$WORK/logic.txt" && ok "  a photo dragged with no file behind it is taken, and becomes a dated picture in the inbox" || bad "  a photo dragged with no file behind it"
grep -q "^logic: ok: a drop carrying both a file and a picture takes both, and says so once" "$WORK/logic.txt" && ok "  and a drop carrying both a file and a photo takes both and gives one receipt" || bad "  a drop carrying both a file and a photo"
grep -q "^logic: ok: a dropped file is read back as the file it is" "$WORK/logic.txt" && grep -q "^logic: ok: and dropped words are read back as words" "$WORK/logic.txt" && grep -q "^logic: ok: a file dropped with its own name as words beside it is taken as the file, and the words are ignored" "$WORK/logic.txt" && grep -q "^logic: ok: a drop carrying neither a file nor any words is refused rather than passed over" "$WORK/logic.txt" && ok "  what a drop carries is read as macOS really sends it: the file wins over the name Finder puts beside it" || bad "  what a drop carries"
grep -q "^logic: ok: the receipt names what landed and where, and what to do next, in the pack's own words" "$WORK/logic.txt" && grep -q "^logic: ok: every way a drop can be refused has its own sentence, and none of them is a technical message" "$WORK/logic.txt" && grep -q "^logic: ok: and no two of them say the same thing" "$WORK/logic.txt" && ok "  every way a drop can end has its own plain sentence, and not one of them is a technical message" || bad "  the words a drop ends in"
# (v0.9.5) Three of the refusals used to name Claude whoever the wiki was for.
# Unreachable from the receipt today, and a trap for whoever makes one of them
# reachable next. And the receipt's own button is asked of the screen rather
# than read back out of the value the check had just handed in.
grep -q "^logic: ok: and not one of them names an assistant the wiki is not for" "$WORK/logic.txt" && grep -q "^logic: ok: the receipt's button is Done when something landed and Carry on when nothing did" "$WORK/logic.txt" && ok "  not one refusal names an assistant the wiki is not for, and the receipt's button is asked of the screen itself" || bad "  the refusals must not name the wrong assistant"
# And the receipt says the very words the pack's own instructions say, so the
# screen and the wiki's own HOW-TO cannot drift apart.
grep -qF "Process the new files in raw/." "$here/../../vault-template/raw/HOW-TO-ADD-CONTENT.md" && grep -qF 'static let nextStep = "process the new files in raw/"' "$here/../Sources/Moblee/Inbox.swift" && ok "  in the same words vault-template/raw/HOW-TO-ADD-CONTENT.md tells the owner to say" || bad "  the receipt and the pack's own instructions say the same words"
# (v0.9.5) "Read it to me", beside every block of words rather than beside the
# big sentence alone. There was ONE listen control in the whole app and it read
# the headline; the cards, the tiles and their reasons, the check-up's findings,
# the skill preview, the drop receipt, the Trust steps and the quiet words were
# all silent, so an owner who would rather be told than read got the first line
# of each screen and nothing else. What can be checked without ears: which words
# each control would say (asked of the screen's own sentence, never of a copy),
# which voice each piece of words asks for, that starting one stops another, and
# that nothing ever starts on its own.
grep -q "^logic: ok: Moblee's own sentences are read in a British voice where the Mac has one" "$WORK/logic.txt" && grep -q "^logic: ok: with no British voice on the Mac, the Mac's own English is used" "$WORK/logic.txt" && grep -q "^logic: ok: and with no English voice at all nothing is chosen" "$WORK/logic.txt" && ok "Moblee's own words ask for a British voice, then the Mac's own English, and fall back to the voice the Mac itself would use" || bad "  which voice reads Moblee's own words"
grep -q "^logic: ok: the owner's own name written in Arabic asks for an Arabic voice, not an English one" "$WORK/logic.txt" && grep -q "^logic: ok: and a voice for that language in whatever country's form the Mac happens to have" "$WORK/logic.txt" && grep -q "^logic: ok: with no Arabic voice on the Mac it falls back to Moblee's own rather than refusing to read" "$WORK/logic.txt" && ok "  the owner's own words are read by a voice chosen for the letters they are written in, so an Arabic name is never read out in English" || bad "  which voice reads the owner's own words"
grep -q "^logic: ok: kana say Japanese outright" "$WORK/logic.txt" && grep -q "^logic: ok: one stray letter does not decide: the letters are counted" "$WORK/logic.txt" && grep -q "^logic: ok: and a Latin-lettered name on an Arabic Mac is not handed to the Arabic voice" "$WORK/logic.txt" && ok "  the letters are counted rather than the first one taken, and a Latin-lettered name is never handed to a voice that cannot read it" || bad "  how the letters choose the voice"
# (v0.9.5) The Han characters are shared between Japanese and Chinese and no
# rule over the letters can tell them apart. The check that stood here was
# called "Japanese is told from Chinese by its own letters" and then asserted
# that 日本語 is Chinese, so it guarded the fault instead of flagging it: a
# Japanese owner whose name is in kanji had it read out in Mandarin. The Mac's
# own language now settles it, and the checks say plainly what is a finding and
# what is a guess.
grep -q "^logic: ok: but the Han characters are shared, so the letters alone cannot say which language they are" "$WORK/logic.txt" && grep -q "^logic: ok: so on a Mac set to Japanese, a name in kanji is read by the Japanese voice and not by the Mandarin one" "$WORK/logic.txt" && grep -q "^logic: ok: and kana are never given to the Mandarin voice, whatever the Mac is set to" "$WORK/logic.txt" && ok "  the shared Han characters are owned up to as a guess, and a Mac set to Japanese settles it for a name in kanji" || bad "  Japanese and Chinese share their letters, and the Mac settles it"
grep -q "^logic: ok: a Latin-lettered name on a French Mac is read in the Mac's own voice" "$WORK/logic.txt" && grep -q "^logic: ok: but Moblee's own sentence on that same Mac is still read in English" "$WORK/logic.txt" && ok "  where the letters say nothing, the owner's words take the Mac's own voice and Moblee's own words stay in English" || bad "  the Mac's own voice for the owner's Latin-lettered words"
grep -q "^logic: ok: with nothing else said, a screen's listen control reads that screen's own sentence" "$WORK/logic.txt" && grep -q "^logic: ok: and where a screen says more aloud than it shows, that is what is read" "$WORK/logic.txt" && ok "each listen control reads the words it stands beside, asked of the screen's own sentence and never of a copy of it" || bad "  what each listen control reads"
grep -q "^logic: ok: a tile is read with its title, the reason it was asked for, what it costs and where it has got to" "$WORK/logic.txt" && grep -q "^logic: ok: a tile that went wrong is read with what went wrong" "$WORK/logic.txt" && grep -q "^logic: ok: a skill Claude wrote wears a name of the owner's own" "$WORK/logic.txt" && ok "  a tile says its reason and its cost, a broken one says what broke, and a skill's own name is read in a voice chosen for it" || bad "  what a tile says"
grep -q "^logic: ok: the card that names the wiki folder reads Moblee's words in Moblee's voice and the folder's name in one chosen for it" "$WORK/logic.txt" && grep -q "^logic: ok: a card with nothing of the owner's in it is read in one voice" "$WORK/logic.txt" && ok "  a sentence of Moblee's with the owner's folder name in it is read in two voices, and one with nothing of theirs in one" || bad "  a sentence with the owner's own words inside it"
grep -q "^logic: ok: the greeting reads Moblee's word in Moblee's voice and the owner's name in one chosen for the name" "$WORK/logic.txt" && grep -q "^logic: ok: and not one of the invisible marks reaches the voice" "$WORK/logic.txt" && ok "  the greeting says the owner's own name in their own voice, with none of the invisible marks that let it stand on the screen" || bad "  the greeting read back"
grep -q "^logic: ok: the receipt reads every name it shows, each in a voice chosen for the letters the owner named it in" "$WORK/logic.txt" && grep -q "^logic: ok: and a receipt with more names than it shows says how many more" "$WORK/logic.txt" && ok "  a dropped file's name is read in a voice chosen for that name, and the receipt says how many more there were" || bad "  the drop receipt read aloud"
grep -q "^logic: ok: the list of what is being made is read tile by tile" "$WORK/logic.txt" && grep -q "^logic: ok: a check-up card is read with what it is, whether it can wait, and where it has got to" "$WORK/logic.txt" && grep -q "^logic: ok: an assistant card says its own word, and whether it is the one chosen" "$WORK/logic.txt" && ok "  the build's tiles, the check-up's findings and the three assistant cards all say what they show and where they have got to" || bad "  the tiles and cards that were silent"
grep -q "^logic: ok: every control on the busiest screen has a name of its own" "$WORK/logic.txt" && grep -q "^logic: ok: and a listen control is never called the same thing as the control it stands beside" "$WORK/logic.txt" && grep -q "^logic: ok: the five Trust steps have a listen control each" "$WORK/logic.txt" && grep -q "^logic: ok: and three cards abreast have one each" "$WORK/logic.txt" && ok "  every listen control has a name of its own, so the keyboard, the walk and a screen reader can each tell six of them apart" || bad "  the names the listen controls are found by"
grep -q "^logic: ok: the busiest screen stays at twenty controls or fewer" "$WORK/logic.txt" && grep -q "^logic: ok: and the busiest screen really is the one with a Done button on every tile that has one" "$WORK/logic.txt" && ok "  and the busiest screen — the one whose handed-over tiles each grow a Done button — is still at twenty controls or fewer in all, with the listening ones never more than half of them" || bad "  the number of controls on the busiest screen"
# (v0.9.5) Each listen control has to stand BESIDE the words it reads on the
# keyboard's round, not merely be on it. All three tile speakers used to come
# one after another before any of the three Add buttons, so an owner pressing
# Tab could not tell which speaker belonged to which tile, and the quiet words'
# speaker was two places from the quiet words with a control from the opposite
# corner of the screen in between.
grep -q "^logic: ok: every tile's listen control stands next to that tile's own buttons on the keyboard's round" "$WORK/logic.txt" && grep -q "^logic: ok: and a tile's listen control never stands next to another tile's" "$WORK/logic.txt" && grep -q "^logic: ok: the quiet words and the two corner lines each have their listen control beside them too" "$WORK/logic.txt" && ok "  and every listen control stands beside the very words it reads, rather than merely being somewhere on the round" || bad "  each listen control stands beside its own words"
grep -q "^logic: ok: nothing has spoken: not one screen, not one card, not the whole of this check so far" "$WORK/logic.txt" && grep -q "^logic: ok: every one of those was the owner pressing something; the app started none of them" "$WORK/logic.txt" && grep -q "^logic: ok: a control with no words to say starts nothing" "$WORK/logic.txt" && ok "nothing speaks unless the owner presses something: no screen, no card and no check ever starts a voice" || bad "  nothing speaks unasked"
grep -q "^logic: ok: pressing another stops the first: one voice at a time" "$WORK/logic.txt" && grep -q "^logic: ok: pressing the one that is speaking stops it" "$WORK/logic.txt" && grep -q "^logic: ok: and leaving a screen stops whatever was reading" "$WORK/logic.txt" && grep -q "^logic: ok: a block read in two voices is still one control speaking" "$WORK/logic.txt" && ok "  one voice at a time: starting one stops another, pressing the reading one stops it, and leaving a screen stops it" || bad "  one voice at a time"
# (v0.9.6) The example wiki an owner reads inside the app. A new owner is asked
# to build a wiki without ever having seen one, and "what is a wiki?" is a
# question explaining does not answer. Nine written pages ship inside the app;
# this is the whole of what can be proved about reading them without a window.
# The live-window walk is what would press the buttons, and everything below is
# asked of the app's own code against the very pages it ships.
grep -q "^logic: ok: the example wiki is inside the app, and the page it opens on is in it" "$WORK/logic.txt" && grep -q "^logic: ok: the example opens on Welcome, not on Index" "$WORK/logic.txt" && ok "the example wiki is inside the app and opens on its welcome page, not on its catalogue" || bad "  the example wiki is inside the app"
grep "^logic: the example: " "$WORK/logic.txt" | sed 's/^/      /'
# The markdown subset, against the pages it was written for. It reads exactly
# what those nine pages contain and no more, so it cannot fail on syntax the
# example never has; a tenth page using something new fails this before anybody
# is asked to read it.
grep -q "^logic: ok: every mark the example uses is read, so not one piece of markup is left in the words an owner sees" "$WORK/logic.txt" && grep -q "^logic: ok: and each of the five kinds of piece really appears in the example" "$WORK/logic.txt" && grep -q "^logic: ok: underscores are not read as emphasis" "$WORK/logic.txt" && ok "  the markdown it reads is exactly what the example contains: every mark consumed, none of the subset dead, and underscores left alone because a page is called _context" || bad "  the markdown subset against the example"
grep -q "^logic: ok: the marker on every page is an HTML comment, and not one word of it is drawn" "$WORK/logic.txt" && grep -q "^logic: ok: and YAML frontmatter is hidden too" "$WORK/logic.txt" && grep -q "^logic: ok: three hyphens in the middle of a page is a rule and not the start of frontmatter" "$WORK/logic.txt" && ok "  the per-page marker and the frontmatter are both hidden, and a rule in the middle of a page is still a rule" || bad "  the marker and the frontmatter must be hidden"
# The one finding the whole reader turns on: inline code is read BEFORE a
# wikilink. Read the other way round the example has 64 links across 7 targets
# and one of them — a made-up page name inside an instruction about how to cite
# pages — can never resolve.
grep -q "^logic: ok: inline code is read before a wikilink, so a page name inside backticks is words and never a link" "$WORK/logic.txt" && grep -q "^logic: ok: exactly one pair of double brackets in the example is not a link, and it is the one inside backticks" "$WORK/logic.txt" && ok "  a page name written inside backticks is words and never a link, which is what makes every link in the example resolve" || bad "  inline code must be read before a wikilink"
grep -q "^logic: ok: every wikilink in the shipped example resolves, and following it really arrives at that page" "$WORK/logic.txt" && grep -q "^logic: ok: a page named in the wrong case is found all the same" "$WORK/logic.txt" && grep -q "^logic: ok: a link with an alias goes to the page and shows the alias" "$WORK/logic.txt" && grep -q "^logic: ok: a link to a heading inside a page goes to the page" "$WORK/logic.txt" && ok "  every wikilink in the shipped example resolves the way Obsidian resolves one, aliases, headings and the wrong case included" || bad "  every wikilink in the example must resolve"
grep -q "^logic: ok: a link that leads nowhere leaves the reader on the page it was on, with one quiet line and nothing technical" "$WORK/logic.txt" && grep -q "^logic: ok: and the line goes the moment the owner does anything else" "$WORK/logic.txt" && ok "  and a link that leads nowhere says one quiet line and leaves the reader where they were" || bad "  a link that leads nowhere"
grep -q "^logic: ok: back goes back through the pages that were read, one at a time" "$WORK/logic.txt" && grep -q "^logic: ok: the list of pages is built from the very map the links resolve against, with the way in first" "$WORK/logic.txt" && grep -q "^logic: ok: and a page opened from that list can be left the same way" "$WORK/logic.txt" && ok "  back goes back page by page, and the list of every page is built from the same map the links resolve against" || bad "  back, and the list of pages"
grep -q "^logic: ok: the buttons under a page are that page's own links, once each, in the order they are written" "$WORK/logic.txt" && grep -q "^logic: ok: every control on a page of the example has a name of its own" "$WORK/logic.txt" && ok "  every link is a button the keyboard can reach, because an inline link in wrapping text takes no keyboard focus on macOS" || bad "  the links must be reachable from the keyboard"
grep -q "^logic: ok: a page is read aloud in its own words, with its marker and its markup gone" "$WORK/logic.txt" && grep -q "^logic: ok: one quiet line says whose wiki this is, and says it is invented" "$WORK/logic.txt" && ok "  a page is read aloud in its own words, and one quiet line of chrome says the wiki is an invented example" || bad "  reading a page aloud, and the line of chrome"
# The one place in Moblee where mistaking a worked example for a starter
# template would really happen. It is strictly read only, it offers nothing,
# and reading the whole of it touches not one byte of the app's own bundle.
grep -q "^logic: ok: and not one word anywhere on the example offers to use it, copy it, or start a wiki from it" "$WORK/logic.txt" && grep -q "^logic: ok:   and that list really would catch it" "$WORK/logic.txt" && grep -q "^logic: ok: reading the whole example, and following every link in it, changed not one file in it" "$WORK/logic.txt" && grep -q "^logic: ok:   and there is no copy of the example anywhere in the practice home" "$WORK/logic.txt" && ok "  it is strictly a thing to read: nothing offers to use it, nothing is copied anywhere, and reading all of it changed not one file" || bad "  the example must be read-only and never a template"
grep -q "^logic: ok: a link inside the words carries Moblee's own scheme, and no other address is ever acted on" "$WORK/logic.txt" && ok "  and a link inside the words can open nothing at all outside the app" || bad "  a link in the example must open nothing outside the app"
grep -q "^logic: ok: the way into the example says the same four words in both places it appears" "$WORK/logic.txt" && grep -q "^logic: ok: on the home screen it is a second big button" "$WORK/logic.txt" && grep -q "^logic: ok: and closing it puts them back at the install, on the screen they left" "$WORK/logic.txt" && grep -q "^logic: ok: an owner who already has a wiki is put back on the home screen" "$WORK/logic.txt" && ok "  the way in says the same words in both places, and closing it puts an owner with no wiki back at the install and an owner with one back at home" || bad "  the two ways in, and where closing the example goes"
# And the words on the two ways in really are the words the app draws.
grep -qF 'static let wayIn = "See an example wiki"' "$here/../Sources/Moblee/ExampleWiki.swift" && grep -qF 'static let chrome = "Example wiki. Sam is invented."' "$here/../Sources/Moblee/ExampleWiki.swift" && ok "  in the words the screens themselves hold" || bad "  the example's own words"

# The Dock route is declared conservatively: Moblee never becomes the app a file
# opens in, and is never offered as an owner of any type. LSHandlerRank None is
# the whole of what keeps the broad public.item declaration harmless.
DOCTYPES="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleDocumentTypes:0' "$APP/Contents/Info.plist" 2>/dev/null)"
[[ "$DOCTYPES" == *"LSHandlerRank = None"* && "$DOCTYPES" == *"public.item"* && "$DOCTYPES" != *"Owner"* && "$DOCTYPES" != *"Alternate"* ]] && ok "  the app says it will take a file dropped on its Dock icon, and never that it can open one" || bad "  the Dock declaration must be LSHandlerRank None"
[[ "$(/usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' "$APP/Contents/Info.plist")" == "io.github.mosabs2.moblee" ]] && ok "  and the bundle identifier is untouched" || bad "  the bundle identifier is untouched"
( unset MOBLEE_PRACTICE; "$BIN" --check-logic > "$WORK/logic-refused.txt" 2>&1 ); [[ $? -eq 2 ]] && ok "  without a practice run the check is refused" || bad "  without a practice run the logic check is refused"

# (v0.9.3) The look for a newer Moblee: what is taken from GitHub's answer and
# what is done with it, then the request itself against the real network — the
# real GitHub, an address that never answers, and two that answer wrongly.
grep -q "^logic: ok: anything but a plain version is refused, including addresses, paths and commands" "$WORK/logic.txt" && grep -q "^logic: ok: and no address is built from anything but a plain version" "$WORK/logic.txt" && ok "  only a plain version is taken from GitHub's answer, and the download address is built by the app" || bad "  only a plain version is taken from GitHub's answer"
grep -q "^logic: ok: a draft or a pre-release is never offered" "$WORK/logic.txt" && grep -q "^logic: ok: Not now keeps that version away, and a newer one is offered again" "$WORK/logic.txt" && grep -q "^logic: ok: an answer had today is used today without asking again" "$WORK/logic.txt" && ok "  a newer version is offered once a day, never a draft, and Not now holds until the next one" || bad "  what is offered, and when"
grep -q "^logic: ok: a practice run with no release switch asks nobody" "$WORK/logic.txt" && grep -q "^logic: ok: a released app always asks GitHub itself, whatever it is started with" "$WORK/logic.txt" && ok "  a practice run goes to the network only when told to, and a released app only to GitHub" || bad "  where the look goes"
grep -q "^logic: ok: a release that does not yet carry the app, or carries another version's, is not offered" "$WORK/logic.txt" && ok "  a release is offered only once the app itself is on it, so Download never opens a missing file" || bad "  a release without the app on it is not offered"
grep -q "^logic: ok: but never over an update this app can make" "$WORK/logic.txt" && grep -q "^logic: ok: nor over a repair" "$WORK/logic.txt" && grep -q "^logic: ok: nor over an explanation" "$WORK/logic.txt" && ok "  the line never shows over an update, a repair or an explanation" || bad "  where the line may show"
asked() { perl -e 'alarm 20; exec @ARGV' "$BIN" --ask-release "$@" 2>&1; }
# The four below need the internet. Offline (or with GitHub unreachable) they are
# skipped and said to be skipped: not a pass, and not a fault in the app.
if curl -m 5 -sfI https://api.github.com > /dev/null 2>&1; then
  A=$(asked); echo "      GitHub: $A"
  [[ "$A" =~ ^release:\ [0-9]+\.[0-9]+(\.[0-9]+)*\ in\ [0-4]\.[0-9]s$ ]] && ok "  GitHub itself answers with a plain version, inside five seconds" || bad "  GitHub itself answers with a plain version (rate-limited? got: $A)"
  A=$(asked --release-url http://10.255.255.1/x); echo "      never answers: $A"
  [[ "$A" =~ ^release:\ none\ in\ [45]\.[0-9]s$ ]] && ok "  an address that never answers is given up on, quietly, at five seconds" || bad "  an address that never answers is given up on at five seconds (got: $A)"
  A=$(asked --release-url https://api.github.com/repos/mosabs2/moblee/releases/tags/v999.0.0); B2=$(asked --release-url https://example.com/)
  [[ "$A" == release:\ none* && "$B2" == release:\ none* ]] && ok "  a missing release and a page that is not GitHub's answer both give nothing" || bad "  wrong answers give nothing (got: $A / $B2)"
else
  echo "SKIP  the four live checks against GitHub: this Mac cannot reach api.github.com just now"
fi
( unset MOBLEE_PRACTICE; "$BIN" --ask-release > "$WORK/ask-refused.txt" 2>&1 ); [[ $? -eq 2 ]] && ok "  and outside a practice run the probe is refused" || bad "  outside a practice run the probe is refused"

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

# (v0.9.4) Now with an older Moblee ALREADY OPEN in the pretend Applications,
# which is how an owner meets it: they open the new one while yesterday's is
# still running. The app used to refuse the move outright, and to refuse it for
# any second Moblee anywhere at all, so a second copy open in Downloads was
# enough to stop it. It now asks the one in the way to close, the ordinary way
# one Mac app asks another, and goes on.
#
# A third Moblee is opened somewhere else at the same time. It is not in the
# way of anything and must be left running and untouched.
mkdir -p "$WORK/elsewhere" "$WORK/home-older" "$WORK/home-bystander"
cp -R "$APP" "$WORK/elsewhere/Moblee.app"
( "$APPS/Moblee.app/Contents/MacOS/Moblee" --home "$WORK/home-older" > "$WORK/older.txt" 2>&1 & )
( "$WORK/elsewhere/Moblee.app/Contents/MacOS/Moblee" --home "$WORK/home-bystander" > "$WORK/bystander.txt" 2>&1 & )
sleep 5
open_at() { pgrep -f "^$1/Contents/MacOS/Moblee " > /dev/null 2>&1 && echo yes || echo no; }
[[ "$(open_at "$APPS/Moblee.app")" == "yes" && "$(open_at "$WORK/elsewhere/Moblee.app")" == "yes" ]] \
  && ok "  two more Moblees are open: the older one in Applications, and one somewhere else" \
  || bad "  the second and third Moblee did not open (see $WORK/older.txt, $WORK/bystander.txt)"

# then the move itself, with the real button
"$DL/Moblee.app/Contents/MacOS/Moblee" --home "$WORK/home-move" --move-to "$APPS" --self-drive > "$WORK/move.txt" 2>&1
RC=$?
[[ "$(open_at "$APPS/Moblee.app")" == "no" ]] && ok "  the older Moblee at the destination was asked to close, and closed" || bad "  the older Moblee at the destination was asked to close"
[[ "$(open_at "$WORK/elsewhere/Moblee.app")" == "yes" ]] && ok "  and a Moblee open somewhere else was neither closed nor allowed to stop the move" || bad "  a Moblee open somewhere else must not be touched, nor stop the move"
pkill -f "^$WORK/elsewhere/Moblee.app/Contents/MacOS/Moblee " 2>/dev/null
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
# Started the way Finder starts an app (through `open`), because macOS only
# lets an app take the front when it was opened that way. Started as a bare
# program from this script it stays behind whatever the person at the Mac is
# using, its window is never the key window, and its clicks on the screens'
# own controls go nowhere, which reads as two dozen failures that are not the
# app's. `open` does not pass the app's exit code on, so the walk's last line
# is what says whether it passed.
# (v0.9.5) With a time limit on it. `open -n -W` waits for ever, and on this Mac
# the walk hangs outright now and then: the app starts, draws nothing, writes not
# one byte, and never exits. Without a limit the whole test simply stops, with no
# word of why; and the app it leaves running holds the window server in a state
# where the NEXT run's drawing dies part way through, so one hang quietly spoils
# every run after it until somebody notices and ends the process by hand. Four
# minutes is about four times the walk's usual length. A hang is now a named
# failure and the process is ended, so the run after it starts clean.
drive_limit=240
open -n -W -a "$APP" --env MOBLEE_PRACTICE=1 --stdout "$WORK/drive.txt" --stderr "$WORK/drive.txt" \
     --args --home "$WORK/home-drive" --self-drive --latest 99.0.0 &
drive_waiter=$!
drive_hung=0
waited=0
while kill -0 "$drive_waiter" 2>/dev/null; do
  if [[ $waited -ge $drive_limit ]]; then drive_hung=1; break; fi
  sleep 2; waited=$((waited+2))
done
if [[ $drive_hung -eq 1 ]]; then
  # The app itself, not `open`: ended by the exact bundle it was started from, so
  # no other Moblee on this Mac is touched.
  pkill -f "^$APP/Contents/MacOS/Moblee " 2>/dev/null || true
  kill "$drive_waiter" 2>/dev/null || true
  sleep 2
  # Not counted as a failure here: the checks below read drive.txt, find nothing
  # in it and report every one of them, which is the count the summary needs.
  # This only says WHY they are all about to fail.
  echo ""
  echo "HUNG     the live-window walk did not start within ${drive_limit}s and was ended."
  echo "         It wrote $(wc -c < "$WORK/drive.txt" | tr -d ' ') bytes. This comes and goes on this Mac and is not a"
  echo "         fault in the app: run the test again. The checks below all fail for this one"
  echo "         reason. If it hangs twice running: pgrep -fl Moblee, and end anything left."
  echo ""
fi
wait "$drive_waiter" 2>/dev/null || true
if grep -q "^self-drive: every screen opened, the install finished" "$WORK/drive.txt" && ! grep -q "^self-drive: FAILED" "$WORK/drive.txt"; then RC=0; else RC=1; fi
if grep -q "^self-drive: NOT RUN" "$WORK/drive.txt"; then
  echo ""
  echo "NOT RUN  the live-window walk: macOS would not let the test window come to the front,"
  echo "         because another app was being used. This is not a pass and not a fault in the"
  echo "         app. Run the test again when nobody is using the Mac. ($WORK/drive.txt)"
  echo ""
  echo "$PASS passed, $FAIL failed, and the live-window walk was not run. Screens and outputs are in $WORK"
  exit 3
fi
[[ $RC -eq 0 ]] && ok "the real window opens every screen and finishes an install" || bad "the real window opens every screen and finishes an install (exit $RC; see $WORK/drive.txt)"
for s in welcome check-up name assistant build hand-off home; do
  grep -q "^self-drive: $s" "$WORK/drive.txt" && ok "  reached: $s" || bad "  reached: $s"
done
grep -q "^self-drive: ok: Return moves on exactly one screen, to the question of which assistant" "$WORK/drive.txt" && grep -q "^self-drive: ok: nothing is chosen for the owner beforehand" "$WORK/drive.txt" && grep -q "^self-drive: ok: tapping the Claude card answers the question" "$WORK/drive.txt" && ok "the question of which assistant appears after the name, with nothing chosen beforehand, and a tap on Claude answers it" || bad "the question of which assistant appears after the name and a tap answers it"
grep -q "^self-drive: ok: the answer went to the installer as --assistant claude" "$WORK/drive.txt" && [[ "$(tr -d '[:space:]' < "$WORK/home-drive/.config/moblee/assistant" 2>/dev/null)" == "claude" ]] && grep -q "assistant: claude" "$WORK/home-drive/.config/moblee/install-diary.txt" 2>/dev/null && ok "  --assistant claude reached the installer, which kept it on record and noted it in the diary" || bad "  --assistant claude reached the installer"
grep -q "^self-drive: ok: an install for Claude asks for no Trust step" "$WORK/drive.txt" && [[ ! -e "$WORK/home-drive/.codex" && ! -e "$WORK/home-drive/.config/moblee/trust-pending" ]] && ok "  an install for Claude puts nothing of ChatGPT's on the Mac and asks for no Trust step" || bad "  an install for Claude asks for no Trust step"
grep -q "^self-drive: ok: at home the wiki is known to be for Claude, and an update would ask nothing" "$WORK/drive.txt" && ok "  at home the choice is read from the record, so an update would ask nothing" || bad "  at home the choice is read from the record"
# (v0.9.4) The whole install from the keyboard, on the real window. "Which
# assistant?" is the screen nobody can skip — Next is greyed out until one of
# the three cards is chosen — and the cards took no keyboard at all, so without
# macOS's own Full Keyboard Access an owner who cannot use a mouse could not
# finish the install.
grep -q "^self-drive: ok: Tab alone reaches one of the three cards" "$WORK/drive.txt" && grep -q "^self-drive: ok: and Space alone answers the question" "$WORK/drive.txt" && grep -q "^self-drive: ok: and Space alone changes the answer" "$WORK/drive.txt" && ok "the three assistant cards are reached by Tab and answered by Space, with no mouse at all" || bad "the assistant cards from the keyboard"
grep -q "^self-drive: ok: Tab reaches the way back" "$WORK/drive.txt" && grep -q "^self-drive: ok: and Space alone goes back one screen" "$WORK/drive.txt" && ok "  and the way back, on every screen that has one, is reached by Tab and pressed by Space" || bad "  the way back from the keyboard"
grep -q "^self-drive: ok: the name box is reached without a mouse" "$WORK/drive.txt" && grep -q "^self-drive: ok: and neither does Return, which is what presses it when it is live" "$WORK/drive.txt" && ok "  the name box takes the keyboard without a mouse, and Return does nothing on a greyed-out Next" || bad "  the name box from the keyboard"
grep -q "^self-drive: ok: every screen of the install can be got past with the keyboard alone" "$WORK/drive.txt" && ok "  so the whole install — welcome, check-up, name, which assistant, promise, build — can be finished from the keyboard alone" || bad "  the whole install from the keyboard alone"
grep -q "^self-drive: tiles waiting: trips, videos" "$WORK/drive.txt" && ok "home screen shows the two things agreed with Claude" || bad "home screen shows the two things agreed with Claude"
# (v0.9.4) The keyboard alone, on the real window. The tile buttons and the
# quiet "Not now" could be worked by the mouse and by nothing else, which shut
# out anybody who cannot use one.
grep -q "^self-drive: ok: Tab alone reaches a tile's button" "$WORK/drive.txt" && grep -q "^self-drive: ok: and Space alone presses it" "$WORK/drive.txt" && ok "Tab reaches a tile's own button and Space presses it, with no mouse at all" || bad "the keyboard reaches and presses a tile's button"
# (v0.9.5) The new listen controls, on the real window, with the keyboard alone.
# Everything a picture file cannot show: that Tab really reaches one, that Space
# really starts it, that starting a second really stops the first, and that
# leaving the screen really stops it. A test cannot hear, so what is read is
# which control the app says is speaking.
grep -q "^self-drive: ok: nothing has spoken on the welcome screen" "$WORK/drive.txt" && grep -q "^self-drive: ok: through the whole install and home again, nothing has spoken by itself" "$WORK/drive.txt" && ok "on the real window, the whole install and the home screen go by without one word being spoken unasked" || bad "  nothing speaks unasked on the real window"
grep -q "^self-drive: ok: Tab alone reaches a tile's own listen control" "$WORK/drive.txt" && grep -q "^self-drive: ok: and Space alone starts it reading that tile" "$WORK/drive.txt" && ok "  Tab reaches a tile's own listen control and Space starts it, with no mouse at all" || bad "  a tile's listen control from the keyboard"
grep -q "^self-drive: ok: starting one stops the other: one voice at a time" "$WORK/drive.txt" && grep -q "^self-drive: ok: and it stops the tile that was reading" "$WORK/drive.txt" && grep -q "^self-drive: ok: leaving the screen stops it reading" "$WORK/drive.txt" && ok "  starting one stops another, only the one speaking says so, and leaving the screen stops it" || bad "  one voice at a time on the real window"
# (v0.9.5) The tab order, counted on the real window. v0.9.4's whole point was
# that every control can be reached by Tab; a listen control beside every block
# of words is exactly the change that could turn three presses into twenty.
grep -q "^self-drive: ok: the keyboard crosses the busiest screen in twenty presses or fewer" "$WORK/drive.txt" && grep -q "^self-drive: ok: and every tile's own button and its listen control are both on that round" "$WORK/drive.txt" && grep -q "^self-drive: ok: with the listening controls never more than half" "$WORK/drive.txt" && ok "  and the keyboard still crosses the busiest screen in twenty presses or fewer, with every new control on the round" || bad "  the tab order with the new controls on the screen"
# (v0.9.5) The round is walked from its very first control, not from wherever
# "Bigger text" happens to sit in it: Tab stops at the end rather than coming
# round again, so starting at that control measured the part of the round after
# it and called it the whole. And the real round is required to be EXACTLY the
# list the screen itself says it has, in that order, so neither can drift.
grep -q "^self-drive: ok: and the keyboard's real round is exactly the round the screen says it has, in that order" "$WORK/drive.txt" && grep -q "^self-drive: ok: every listen control on the round stands next to the very words it reads" "$WORK/drive.txt" && grep -q "^self-drive: ok: and no tile's listen control stands next to another tile's" "$WORK/drive.txt" && ok "  and on the real window every listen control stands beside its own words, in the very order the screen says" || bad "  the real tab order, measured from its first control"
grep "^self-drive: the keyboard goes round the home screen in this order" "$WORK/drive.txt" | sed 's/^/      /'
grep -q "^logic: ok: each tile's own buttons are named, so the keyboard and the walk can find them" "$WORK/logic.txt" && grep -q "^logic: ok: each thing the Mac still needs has a named Get button, for the keyboard and for the walk" "$WORK/logic.txt" && ok "  and every small button in the app has a name the keyboard ring and the walk can find it by" || bad "  the names the keyboard finds the small buttons by"
grep -q "^self-drive: ok: Escape does what Not now does" "$WORK/drive.txt" && grep -q "^self-drive: ok: Escape presses nothing where there is no Not now" "$WORK/drive.txt" && ok "  Escape is \"Not now\" where there is one, and presses nothing where there is not" || bad "  Escape on the real window"
# (v0.9.6) The example wiki, on the real window, from the keyboard alone. The
# links on a page are drawn as buttons under it as well as as coloured words
# inside it, because an inline link in wrapping text takes no keyboard focus on
# macOS at all — so an owner who cannot use a mouse could not follow one. That,
# and where the way out goes, are what this measures; everything else about the
# example is checked without a window above.
grep -q "^self-drive: ok: Tab alone reaches the way into the example wiki" "$WORK/drive.txt" && grep -q "^self-drive: ok: and Space alone opens it, on the page it opens on and not on the catalogue" "$WORK/drive.txt" && ok "the way into the example wiki is reached by Tab and opened by Space, on its welcome page" || bad "  the way into the example wiki, from the keyboard"
grep -q "^self-drive: ok: Tab alone reaches a link on the page" "$WORK/drive.txt" && grep -q "^self-drive: ok: and Space alone follows it to that page" "$WORK/drive.txt" && ok "  and a link on a page is reached by Tab and followed by Space, with no mouse at all" || bad "  following a link in the example from the keyboard"
grep -q "^self-drive: ok: Tab reaches the way back inside the example" "$WORK/drive.txt" && grep -q "^self-drive: ok: and Space alone goes back to the page before, not back through the install" "$WORK/drive.txt" && grep -q "^self-drive: ok: Tab reaches the list of every page" "$WORK/drive.txt" && ok "  back inside the example goes back a page and never a screen of the install, and the list of every page opens" || bad "  back, and the list of pages, on the real window"
grep -q "^self-drive: ok: nothing spoke inside the example unasked" "$WORK/drive.txt" && grep -q "^self-drive: ok: and the way out puts an owner who has a wiki back on the home screen" "$WORK/drive.txt" && ok "  nothing speaks inside the example unasked, and the way out puts an owner who has a wiki back on the home screen" || bad "  leaving the example on the real window"
grep -q "^self-drive: ok: Tab reaches Bigger text" "$WORK/drive.txt" && grep -q "^self-drive: ok: the words can be brought back to normal by the keyboard alone" "$WORK/drive.txt" && grep -q "^self-drive: ok: and Space makes the words bigger" "$WORK/drive.txt" && grep -q "^self-drive: ok: a third press puts the words back to normal" "$WORK/drive.txt" && ok "  Bigger text is reached and pressed by the keyboard, and goes round its three sizes" || bad "  Bigger text by the keyboard"
# (v0.9.4) The window itself: fixed at 720 by 520 with no way to make it, or
# the words in it, any bigger at all.
grep -q "^self-drive: ok: the window grows with the words" "$WORK/drive.txt" && grep -q "^self-drive: ok: and the window with them" "$WORK/drive.txt" && grep -q "^self-drive: ok: a window made bigger still draws its screens, with the big button in the middle" "$WORK/drive.txt" && grep -q "^self-drive: ok: and it can never be made smaller than 720 by 520" "$WORK/drive.txt" && ok "the window can be made bigger, grows with the words, keeps its layout centred, and never goes below 720 by 520" || bad "the window's sizes on the real window"
# (v0.9.4) And the other order, which nothing had ever tried: the owner sizes
# the window first and THEN presses "Bigger text". The second press used to
# take the window back to the size the words alone want, and the third to 720
# by 520, throwing away the size the owner had chosen.
grep -q "^self-drive: ok: and a window the owner sized is never made smaller by it" "$WORK/drive.txt" && grep -q "^self-drive: ok: nor by the second press, which is where the owner's size used to go" "$WORK/drive.txt" && grep -q "^self-drive: ok: and the words coming back down bring the window back to exactly the size the owner left it" "$WORK/drive.txt" && ok "  a window the owner sized themselves survives every press of Bigger text, and comes back to exactly their size" || bad "  an owner-sized window through the three text sizes"
# (v0.9.4) The Terminal explanation, one picture at a time, on the real window.
grep -q "^self-drive: ok: nothing is handed over on the first picture" "$WORK/drive.txt" && grep -q "^self-drive: ok: Next stays on the explanation and hands nothing over" "$WORK/drive.txt" && grep -q "^self-drive: ok: Back goes to the picture before, and still hands nothing over" "$WORK/drive.txt" && grep -q "^self-drive: ok: still nothing is handed over on the way through the three" "$WORK/drive.txt" && ok "the Terminal explanation is walked one picture at a time, forwards and back, and opens nothing until the last of the three" || bad "the Terminal explanation one picture at a time"
# (v0.9.3) Walked with --latest 99.0.0 standing in for GitHub.
grep -q "^self-drive: an install looked for a newer Moblee: false" "$WORK/drive.txt" && grep -q "^self-drive: ok: at home, a newer Moblee is offered, and the install before it never looked" "$WORK/drive.txt" && ok "  a newer Moblee is never looked for during an install, and is offered at home" || bad "  a newer Moblee: not during an install, offered at home"
grep -q "^self-drive: ok: the line is on the screen, with Download and Not now" "$WORK/drive.txt" && grep -q "^self-drive: ok: Not now takes the line away, and the version is remembered" "$WORK/drive.txt" && grep -q "^self-drive: ok: and the same version is not offered again" "$WORK/drive.txt" && ok "  the line is on the real window, its Not now works when clicked, and the version stays away" || bad "  the newer-Moblee line on the real window"
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
# (v0.9.4) The Repair above was really pressed, on the real window, against the
# real scripts. It must now be in the install diary: that it started, what it
# found, what the two scripts said, and how it ended. And still no owner's name,
# the wiki's folder name among them ("Tom Wiki").
DIARY="$WORK/home-drive/.config/moblee/install-diary.txt"
grep -q "^.*  --- Moblee repair ---$" "$DIARY" 2>/dev/null && grep -q "repair: started; pack version" "$DIARY" && grep -q "repair: what looked wrong: the delete guard is an older copy" "$DIARY" && ok "a Repair writes itself into the install diary: that it started, and what looked wrong" || bad "a Repair writes itself into the install diary (see $DIARY)"
grep -q "repair: the safety layer: done" "$DIARY" 2>/dev/null && grep -q "repair: Moblee's skills: done" "$DIARY" && grep -q "^.*      | " "$DIARY" && grep -q "repair: ended; nothing is still wrong" "$DIARY" && ok "  with what each of the two scripts replaced, and how the repair ended" || bad "  what the repair replaced, and how it ended"
# (v0.9.4) The diary is the one file an owner is told is safe to send when they
# need help, and it must never name a fault that was looked for and not found:
# a script that exits non-zero over a Mac the check afterwards finds nothing
# wrong with used to end "still wrong: one of Moblee's skills is not this
# Moblee's copy".
grep -q "^logic: ok: with nothing wrong, there is no reason to name" "$WORK/logic.txt" && grep -q "^logic: ok: and a step that did not finish on a Mac with nothing wrong says exactly that, and names no fault" "$WORK/logic.txt" && grep -q "^logic: ok: a repair that left something wrong says what is still wrong" "$WORK/logic.txt" && ok "  and a repair whose step did not finish over a Mac with nothing wrong says so, and names no fault it did not find" || bad "  the repair's last line in the diary"
# (v0.9.4) A repair changes an owner's Mac as an install does and could be cut
# off half-way: the owner presses Repair in the copy in Applications, opens a
# freshly downloaded Moblee and presses "Move it there", and that one asked this
# one to quit in the middle of it.
grep -q "^logic: ok: a Moblee half-way through a repair refuses to close, exactly as one half-way through an install does" "$WORK/logic.txt" && grep -q "^logic: ok: and lets itself be closed again the moment the repair has ended" "$WORK/logic.txt" && grep -q "^logic: ok: the refusal the other copy shows is true of every one of those, and names none of them wrongly" "$WORK/logic.txt" && ok "  a repair in progress refuses a quit, as an install does, and the other copy's screen says something true" || bad "  a repair in progress refuses a quit"
# (v0.9.5) And a drop, which writes into the wiki's inbox for as long as the
# copy takes. It refused to start under an update and an update started happily
# under it: a 90 MB scan dropped, Update pressed a second later, and the
# updater's scripts rewrote and committed the wiki while the copy was running.
grep -q "^logic: ok: a Moblee part-way through putting a dropped file in the wiki refuses to close too" "$WORK/logic.txt" && grep -q "^logic: ok: and two drops at once are still busy when the first of them ends" "$WORK/logic.txt" && grep -q "^logic: ok: and the moment the last drop has landed it lets itself be closed again" "$WORK/logic.txt" && ok "  a drop still copying is work that must not be cut off, and two at once are counted rather than flagged" || bad "  a drop in flight is busy work"
grep -q "^logic: ok: an update cannot start while a dropped file is still being copied into the wiki" "$WORK/logic.txt" && grep -q "^logic: ok: nor a repair, which runs the same scripts over the same wiki" "$WORK/logic.txt" && grep -q "^logic: ok: and the moment the drop has landed, Update works again" "$WORK/logic.txt" && ok "  so neither an update nor a repair can start underneath a drop, and both work again the moment it has landed" || bad "  an update or a repair must not start under a drop"
grep -q "^logic: ok: but a drop does not make another drop wait, which is what two quick drops are" "$WORK/logic.txt" && ok "  and a drop never makes another drop wait, which is what two files let go over the Dock icon a moment apart are" || bad "  a drop must not refuse another drop"
! grep -q "Tom" "$DIARY" 2>/dev/null && ok "  and no owner's name in any of it, not even through the wiki's folder name" || bad "  the repair's diary lines hold no name"
# (v0.9.4) The live failure of 24 September, end to end with the real scripts:
# a skill an earlier Moblee left is recognised and really put back, and a skill
# that matches no Moblee pack is named instead, and left exactly as it was.
grep -q "^self-drive: ok: a skill an earlier Moblee left is a repair this app can make, and is never called the owner's" "$WORK/drive.txt" && grep -q "^self-drive: ok: and pressing Repair really puts this Moblee's own copy back" "$WORK/drive.txt" && grep -q "^self-drive: an earlier Moblee's copy of a skill was recognised and put back: true" "$WORK/drive.txt" && ok "a skill an earlier Moblee left is recognised as Moblee's and Repair (really pressed) puts it back" || bad "a skill an earlier Moblee left is recognised and put back"
grep -q "^self-drive: ok: a skill matching no Moblee pack is named, and no repair is offered for it" "$WORK/drive.txt" && grep -q "^self-drive: the owner's own skill was named and left exactly as it was: true" "$WORK/drive.txt" && grep -q "^self-drive: and the skills are settled again afterwards: true" "$WORK/drive.txt" && ok "  and a skill that is nobody's of Moblee's is named, never replaced, and never offered a repair that cannot succeed" || bad "  a skill that is not Moblee's is named and left alone"
grep -q "^self-drive: ok: Not now sets a repair about differing copies aside" "$WORK/drive.txt" && ok "Not now sets aside a repair that is only about copies differing, so an owner is never shut out of their tiles" || bad "Not now on a repair about differing copies"
grep -q "^self-drive: a wiki newer than this app is left alone .*: true" "$WORK/drive.txt" && ok "an old Moblee opened on a wiki a NEWER Moblee made offers no repair with its older guard and skills, and leaves the note of where Moblee is alone" || bad "an old app must never 'repair' a newer wiki with older copies"
grep -q "^self-drive: skill gym-log ended: .*done" "$WORK/drive.txt" && [[ -f "$WORK/home-drive/.claude/skills/gym-log/.made-for-you" && ! -L "$WORK/home-drive/.claude/skills/gym-log" ]] && ok "a skill Claude drafted is shown, then added as ordinary files" || bad "a skill Claude drafted is shown, then added as ordinary files"
grep -q "^self-drive: skill sneaky: .*blocked" "$WORK/drive.txt" && [[ ! -e "$WORK/home-drive/.claude/skills/sneaky" ]] && ok "a drafted skill that is a link to outside the wiki is refused" || bad "a drafted skill that is a link to outside the wiki is refused"
grep -q "^self-drive: skill brain: .*blocked" "$WORK/drive.txt" && grep -q "brain untouched: true" "$WORK/drive.txt" && ok "a drafted skill wearing a Moblee skill's name is refused, and the real one is untouched" || bad "a drafted skill wearing a Moblee skill's name is refused"
grep -q "nothing smuggled: true" "$WORK/drive.txt" && [[ ! -e /tmp/moblee-pwned ]] && ok "a request with a command or a path in its key makes no tile and runs nothing" || bad "a request with a command or a path in its key makes no tile and runs nothing"
# (v0.9.4) The real window, mirrored, as a Mac whose own language is read right
# to left draws it. A short walk of its own, because what it has to prove is
# where things are and not what they do: nothing is clicked or typed, so it does
# not matter whether macOS lets the window come to the front. Started through
# `open` for the same reason the walk above is — started as a bare program from
# this script the app makes no window at all.
mkdir -p "$WORK/home-rtl"
open -n -W -a "$APP" --env MOBLEE_PRACTICE=1 --stdout "$WORK/drive-rtl.txt" --stderr "$WORK/drive-rtl.txt" \
     --args --home "$WORK/home-rtl" --rtl --self-drive
grep -q "^self-drive: mirrored: every side that means something is the right way round" "$WORK/drive-rtl.txt" && ! grep -q "^self-drive: FAILED" "$WORK/drive-rtl.txt" && ok "the real window, mirrored, puts every side that means something the right way round" || bad "the mirrored window (see $WORK/drive-rtl.txt)"
grep -q "^self-drive: ok: mirrored: the way back sits on the side the reading starts from, which is the right one" "$WORK/drive-rtl.txt" && grep -q "^self-drive: ok: mirrored: Bigger text sits in the top corner the reading ends at, which is the left one" "$WORK/drive-rtl.txt" && grep -q "^self-drive: ok: mirrored: and the big button is still in the middle" "$WORK/drive-rtl.txt" && ok "  back on the right, Bigger text on the left, the big button still in the middle" || bad "  where the controls sit on a mirrored window"
grep -q "^self-drive: ok: mirrored: an Arabic name makes a wiki folder called after it, with nothing invisible in it" "$WORK/drive-rtl.txt" && ok "  and an Arabic name still makes the wiki folder it is called after" || bad "  an Arabic name on a mirrored window"
# And the same two sides read the other way round on the unmirrored window, in
# the walk above, so both directions are looked at on a real window.
grep -q "^self-drive: ok: the way back sits on the side the reading starts from, which is the left one" "$WORK/drive.txt" && grep -q "^self-drive: ok: and Bigger text sits in the top corner the reading ends at, which is the right one" "$WORK/drive.txt" && ok "  and the other way round on the window that is not mirrored" || bad "  where the controls sit on the window that is not mirrored"
# (v0.9.4) A name typed in Arabic into the real box, on the real window. An
# owner's Mac may be in English while their own name is not, and the box had
# never once been given one.
grep -q "^self-drive: ok: a name typed in Arabic reaches the name box exactly as typed" "$WORK/drive.txt" && grep -q "^self-drive: ok: and the wiki folder is called after it, with nothing invisible in the name" "$WORK/drive.txt" && ok "a name typed in Arabic reaches the real name box as typed, and names the wiki folder" || bad "a name typed in Arabic into the real name box"
# (v0.9.4) And the wiki folder's name, which is the one instruction an owner has
# to match against Finder. Told to stand on its own, "نور Wiki" was drawn
# "Wiki نور" while Finder showed "نور Wiki"; a folder's name now takes the
# direction of the line it sits in, which puts the name first, as Finder does.
grep -q "^logic: ok: a wiki folder's name is left exactly as Finder will show it, with no invisible mark at all" "$WORK/logic.txt" && grep -q "^logic: ok: and the screens that send an owner to that folder put no mark in it either" "$WORK/logic.txt" && grep -q "^logic: ok: a name on its own still stands on its own, which is what settles the full stop after it" "$WORK/logic.txt" && ok "  a wiki folder's name is written the way Finder writes it, and a name on its own still stands on its own" || bad "  the wiki folder's name against Finder"
# (v0.9.5) Something dropped on Moblee, on the real window, into the real wiki
# the walk above really made. The receipt is drawn on the live screen and its
# own button is really clicked; the Dock route goes through the very delegate
# method macOS calls. What is not walked is macOS's own dragging, which wants a
# hand on a trackpad: the piece between it and the app is checked in the logic
# check above, against item providers of the shape macOS really sends.
grep -q "^self-drive: ok: a file dropped on Moblee lands in the wiki's inbox, and the receipt is on the real window" "$WORK/drive.txt" && grep -q "^self-drive: ok: and the receipt's own button, really clicked, puts the owner back where they were" "$WORK/drive.txt" && grep -q "^self-drive: ok: which is the home screen they were on" "$WORK/drive.txt" && ok "a file dropped on the real window lands in the wiki's inbox, and its receipt is drawn and really pressed" || bad "a file dropped on the real window"
# The Dock route is walked as macOS really works it: `open -a` asks Launch
# Services to give the file to this running copy, which is the same Apple event
# the Dock sends. (v0.9.5) A WindowGroup opens a SECOND window for a file given
# to it from outside, so an owner who dropped a PDF on the icon was left with
# two Moblee windows and the receipt on one of them; the count is checked here
# so it cannot come back.
grep -q "^self-drive: ok: a file dropped on the Dock icon lands the same way, with the same receipt" "$WORK/drive.txt" && grep -q "^self-drive: ok: and Moblee is still one window, not two" "$WORK/drive.txt" && ok "  and a file dropped on the Dock icon comes through Launch Services, lands the same way, and opens no second window" || bad "  the Dock route"
# (v0.9.5) AND FOUR AT ONCE, which is what letting go of four scans over the
# icon really is: one Apple event carrying four file URLs. The walk only ever
# sent one file this way, and one file was the only case that worked. Four
# together left exactly the first in the inbox and showed the owner a receipt
# naming that one and saying it was in their wiki, so an owner told the drop had
# worked stopped looking for the other three. `onOpenURL` is handed one URL at a
# time; Moblee now takes the whole event itself.
grep -q "^self-drive: ok: four files let go over the Dock icon at once all land, and the receipt says how many" "$WORK/drive.txt" && grep -q "^self-drive: ok: and it is ONE receipt for the whole drop, not one for each file" "$WORK/drive.txt" && grep -q "^self-drive: ok: and Moblee is still one window after four files at once" "$WORK/drive.txt" && ok "  and FOUR files let go over the Dock icon at once all land, under one receipt that says how many" || bad "  four files let go over the Dock icon at once"
grep -q "^self-drive: ok: the same name dropped again gets a number, and the one already there is untouched" "$WORK/drive.txt" && ok "  the same name dropped twice gets a number, and the file already in the inbox is untouched" || bad "  a name already taken, on the real window"
grep -q "^self-drive: ok: a folder dropped on Moblee is refused out loud, and nothing of it is copied in" "$WORK/drive.txt" && grep -q "^self-drive: ok: a drop while a wiki is being made is refused, and never half-lands" "$WORK/drive.txt" && ok "  a folder, and a drop into the middle of an install, are both refused on the real window" || bad "  the refusals on the real window"
grep -q "^self-drive: ok: words dropped on Moblee become a dated note in the inbox that says where they came from" "$WORK/drive.txt" && ok "  and words dropped become a dated note in the inbox that says it was dropped, not written" || bad "  words dropped on the real window"
grep -q "^self-drive: ok: a picture dropped with no file behind it becomes a dated picture in the inbox" "$WORK/drive.txt" && grep -q "^self-drive: ok: and that receipt is read the same way as a file's" "$WORK/drive.txt" && ok "  and a photo with no file behind it becomes a dated picture in the inbox, with the same receipt a file gets" || bad "  a photo dropped on the real window"
grep -q "^self-drive: everything dropped is still exactly where the owner left it: true" "$WORK/drive.txt" && ok "  and after all of it, every original is still exactly where the owner left it, byte for byte" || bad "  the originals must be left exactly as they were"
V2="$WORK/home-drive/Wiki/Tom Wiki"
[[ -f "$V2/raw/Gym plan.md" && -f "$V2/raw/Gym plan 2.md" && -f "$V2/raw/Scan 1.pdf" && -f "$V2/raw/Together 1.pdf" && -f "$V2/raw/Together 4.pdf" && -f "$WORK/home-drive/what the owner has/Gym plan.md" ]] && ok "  the dropped files really are in the wiki's raw folder, and the originals really are still in theirs" || bad "  the dropped files are in raw/ and the originals are still where they were"
cmp -s "$V2/raw/Gym plan.md" "$WORK/home-drive/what the owner has/Gym plan.md" && ok "  and the copy in the inbox is the same bytes as the original" || bad "  the copy in the inbox is the same bytes as the original"
[[ -z "$(ls -A "$V2/raw" | grep '^\.moblee-incoming-')" ]] && ok "  with no half-made copy of Moblee's own left in the inbox" || bad "  no half-made copy is left in the inbox"
grep -q "  drop: .* copied into the wiki's inbox" "$DIARY" && grep -q "drop: one thing was not taken: it is a folder" "$DIARY" && ok "  and each drop wrote its line in the install diary, saying how many landed" || bad "  the drops write their lines in the install diary"
! grep -qi "Gym plan\|Scan 1\|Together \|Cold \|Dropped note\|Dropped picture\|what the owner has" "$DIARY" && ok "  with not one file name of what was dropped in it, because that is the owner's own content" || bad "  the diary must carry no name of what was dropped"
# (v0.9.5) AND THE COLD ONE. Three files let go over the Dock icon of a Moblee
# that is not open at all: macOS starts the app and hands it the event before
# there is a window or a run to give them to, which is the route `Dropped`
# keeps a drop waiting for. The warm route is walked above inside the app; this
# is the only way to walk the cold one, because the walk itself needs the app
# already running. Same fault, and it had to be checked at both ends: the
# handler that takes the whole event has to win the race against SwiftUI's own
# at launch as well as afterwards.
COLD="$WORK/cold-drop"; mkdir -p "$COLD"
for n in 1 2 3; do printf 'cold %s\n' "$n" > "$COLD/Cold $n.pdf"; done
DIARY_WAS="$(wc -l < "$DIARY" | tr -d ' ')"
open -a "$APP" --env MOBLEE_PRACTICE=1 "$COLD/Cold 1.pdf" "$COLD/Cold 2.pdf" "$COLD/Cold 3.pdf" \
     --args --home "$WORK/home-drive" --latest 0.0.1
for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
  [[ -f "$V2/raw/Cold 3.pdf" ]] && break
  sleep 1
done
osascript -e 'tell application "Moblee" to quit' >/dev/null 2>&1
sleep 2; pkill -f "$APP/Contents/MacOS/Moblee" >/dev/null 2>&1
[[ -f "$V2/raw/Cold 1.pdf" && -f "$V2/raw/Cold 2.pdf" && -f "$V2/raw/Cold 3.pdf" ]] && ok "  three files let go over the Dock icon of a Moblee that was not even open all land" || bad "  three files let go over the Dock icon of a Moblee that was not open"
sed -n "$((DIARY_WAS + 1)),\$p" "$DIARY" | grep -q "drop: 3 thing(s) copied into the wiki's inbox" && ok "    and the diary says three, in one drop, rather than one drop of one" || bad "    the cold drop's diary line must say three"
cmp -s "$V2/raw/Cold 2.pdf" "$COLD/Cold 2.pdf" && [[ -f "$COLD/Cold 1.pdf" && -f "$COLD/Cold 2.pdf" && -f "$COLD/Cold 3.pdf" ]] && ok "    and every one of the three is the same bytes as the original, which is still where it was" || bad "    the cold drop's copies and originals"
"$BIN" --self-drive > "$WORK/refuse2.txt" 2>&1 &
PID=$!; sleep 3
if kill -0 $PID 2>/dev/null; then kill $PID; bad "self-drive without a practice home is refused"; else wait $PID; [[ $? -eq 2 ]] && ok "self-drive without a practice home is refused" || bad "self-drive without a practice home is refused"; fi

move_checks

echo ""
echo "$PASS passed, $FAIL failed. Screens and outputs are in $WORK"
[[ $FAIL -eq 0 ]]
