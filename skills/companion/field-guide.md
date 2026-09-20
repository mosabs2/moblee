# Field guide

What goes wrong with a Moblee wiki, how to confirm it, what fixes it and who does the fix. Every entry has been met in a real install. The check-up (`moblee-doctor.py` in the Moblee folder's `scripts/`) prints the entry number beside anything it finds, so start there, then read the entry.

"Owner" fixes are done by the owner, in the Moblee app or in a Terminal window of their own, because they change Claude's settings or the Mac. "Claude" fixes stay inside the vault. Nothing in this guide deletes anything.

## F01. Claude asks permission for almost everything

**Confirms it:** the check-up reports no permission rules. **Why:** the starter rules were never installed (an old version, or an install that stopped early). **Fix, owner:** open Moblee, which shows a Repair button when it finds the guard or the rules missing; or in Terminal, `python3 "<moblee folder>/safety/install-safety.py" --vault "<vault>"`. It adds the rules for routine, safe actions with the delete guard beneath them, and keeps a copy of the old settings.

## F02. The delete guard is missing, not switched on, or not the pack's copy

**Confirms it:** the check-up says which. **Why:** an old version, a settings file replaced by hand, or an update that stopped. **Fix, owner:** the same Repair as F01. The guard cannot be installed or upgraded from inside Claude, by design. Until it is back, Claude takes extra care: no clean-ups, no moves out of the vault.

## F03. Claude's settings file does not load

**Confirms it:** the check-up reports `~/.claude/settings.json` is not valid. **Why:** edited by hand, or written by another tool. **Fix, owner:** Moblee keeps dated copies under `~/.config/moblee/backups/`. Claude lists them (reading is allowed) and gives the owner two Terminal lines: the first moves the broken file aside under a new name (`mv ~/.claude/settings.json ~/.claude/settings.json.broken`), the second copies the newest good one into its place. Nothing is overwritten. Claude does not edit the file.

## F04. Something has gone missing: a page, a folder, a section, some data

**Do not repair yet. Ask first:** is it a page, a section of a page, or data that should have arrived by itself? **Then search every place, renames first:** `git log --diff-filter=R --name-status` for pages renamed or moved, `git log --diff-filter=D --name-only` for deletions, and `git log -p -- "<path>"` for a page's earlier versions; the vault's `.trash/`; the Mac's Trash (Obsidian's default for deleted files); any sync folder; `archive/` and the Context Archive page; `raw/processed/` and `Clippings/processed/`. Obsidian's File recovery (Settings, Core plugins) is one more place, and only the owner can look there. **Most often** nothing was deleted: a page was renamed or split (tell the owner its new name and offer to rename it back; do not restore a second copy), a feed stopped (F05), or a housekeeping pass moved a section to an archive page. **Fix, Claude:** if it truly went, restore from git by copying the old version into place, tell the owner what happened, record it in the log. The check-up adds little to this one; go straight to the search.

## F05. Something that used to arrive by itself has stopped

**Confirms it:** the check-up lists Moblee's scheduled jobs and flags any that are not loaded or last ended with an error; the newest file in `outputs/lint/` is more than two weeks old; a made-to-measure job's log has no recent line. **Why:** the Mac was asleep at the time, a sign-in expired, a website changed, the job was set up with cron. **Fix:** Claude reads the job's log and says why; a sign-in is the owner's to renew; reloading a Moblee job is the owner's, through Moblee or `bash "<moblee folder>/scripts/install-schedule.sh"`. Catch up the missed days by hand. If the job never reported its own failure, mend that first (the scheduled-job rules in `builders-rules.md`).

## F06. Claude refused to install Moblee, or called the instructions a possible attack

**Why:** the owner pasted a file of instructions into Claude, or asked Claude to run the installer. A careful Claude treats pasted orders as a stranger's orders, and is right to. **Fix, owner:** the owner installs, with the Moblee app or `bash scripts/install.sh` in Terminal. Claude can explain any step from `docs/02-install.md`.

## F07. Claude says it cannot write to `~/.claude/`

**Why:** Claude Code protects that folder by design. **Fix:** nothing is broken. Skills, hooks and settings go in through the Moblee app or a Terminal line the owner runs. Never coach the owner to approve a prompt they do not understand.

## F08. After adding a connection, Claude has forgotten the conversation

**Why:** a new connection only loads when Claude is quit and reopened, and a new session starts fresh. **Fix, Claude:** read the owner's page (`wiki/Wiki Operations/Habits and Tools.md`), which holds what was agreed, and carry on from "Adding something", step 5. If the page is empty, the earlier session did not write things down first; apologise, ask again briefly, and write it down this time.

## F09. The install or an item ended with an alarming message about pip, Homebrew or PDF tools

**Why:** an optional part could not be set up on this Mac as it stands (no Homebrew, an old pip). **Fix:** nothing is wrong with the wiki. PDF rendering is the `documents` item and can be added later. Say so plainly; people read any red text as failure.

## F10. A commit is refused

**Confirms it:** the message begins `[GATE]`. **Why:** the commit gate found a link to a page that does not exist, a file over its size limit, or a rules file over its limit. **Fix, Claude:** do what the message says (correct the link, create the missing page if it was meant to exist, fold or trim the file) and commit again. The gate is never bypassed to save time.

## F11. The wiki is on an older Moblee than the one on this Mac

**Confirms it:** the check-up shows two version numbers. **Fix, owner:** open the newer Moblee app, which offers the update; or `bash "<moblee folder>/scripts/update.sh"`. The update never touches the owner's pages and keeps copies of what it replaces.

## F12. The Mac is nearly full

**Confirms it:** the check-up shows free space under 5 GB. **Fix:** Claude tells the owner what in the vault is large (usually `outputs/` and downloaded videos) and what each thing is. The owner decides and removes by hand. Large items on the checklist are not added until there is room.

## F13. The vault is inside a folder that iCloud syncs

**Confirms it:** the check-up says the vault is under a synced Desktop or Documents folder. **Why it matters:** anything that builds or writes many small files inside the vault can clash with the sync, and private material is being copied to iCloud. **Fix:** note it on the owner's page; keep generated files out of the vault; if the owner wants it moved, the move is theirs, with Claude writing the steps, and `~/.config/moblee/vault-path` is updated afterwards by the owner.

## F14. A password, recovery phrase, card number or code has turned up

**Fix, Claude:** stop, leave it out of the wiki, tell the owner where it was found. The place for it is a password manager. If one is already in a page, tell the owner which page and line; they remove it by hand, and they should know that git still holds the old version, which matters if the vault is ever shared.

## F15. There is no Code tab in the Claude app

**Why:** working in a folder on the Mac is part of Claude's paid plans. **Fix, owner:** a paid plan is needed to use Moblee. Say so plainly and leave the decision with them.

## F16. Obsidian does not show the wiki

**Fix, owner:** in Obsidian: Open another vault, Open folder as vault, then the wiki's folder (the check-up prints where it is). Obsidian is only the reading window; the wiki works without it.

## F17. A window offers to install "command line developer tools"

**Why:** the Mac's git and Python arrive with Apple's free developer tools, and something asked for them. **Fix, owner:** press Install and wait; it is safe and comes from Apple. Moblee needs them.

## F18. Things agreed with Claude were never added

**Confirms it:** the check-up lists requests still waiting. **Fix:** remind the owner once that Moblee has tiles waiting and offer to open it. If they have changed their mind, record the no and mark the request `declined`.

## F19. An old `get-started` skill sits beside the companion

**Why:** Moblee 0.7.0 called the first conversation `get-started`; it is now part of the companion. **Fix:** harmless. The next update moves the old copy to the backups folder.

## F20. The wiki feels like a heap: repeats, long pages, no order

**Fix, Claude:** run the health check ("lint the wiki") and read its report to the owner in plain words; run the `compact` skill on what it flags, which lists before it moves anything. Going forward, update existing pages before making new ones, as `CLAUDE.md` says.

## F21. The evening lesson reminder never appears

**Fix, owner:** System Settings, Notifications, then allow notifications for Script Editor (or Terminal). The check-up shows whether the reminder job itself is loaded.

## F22. git printed a notice about a name and email being "configured automatically"

**Fix:** harmless, and only on wikis made by very old versions. Claude sets a name and email for this vault only: `git config user.name "<name>"` and `git config user.email "<name>@<mac>.local"`.

## F23. One of Moblee's skills is missing, or a different skill is sitting under its name

**What the owner sees:** the install ended with "One part did not finish", or Claude does not seem to know "guide me", or behaves oddly when asked for one of Moblee's skills. **Confirms it:** the check-up names the skills. **Why:** Moblee's skill names are ordinary words (`brain`, `companion`, `compact`, `galaxy`), and a folder of the same name was already among Claude's skills: an older Moblee's copy, or something the owner put there. The installer never overwrites a skill it did not recognise, so it left it alone and said so. **Fix, owner:** open Moblee and press Repair, or in Terminal run `bash "<moblee folder>/scripts/install-skills.sh" --update`. Moblee's copies go in, and whatever was there before is moved to `~/.config/moblee/backups/`, never deleted. If what was there was the owner's own skill, tell them where it has gone and offer to bring it back under a different name (the move back is theirs to make).

## F24. The Moblee app cannot be found, or is still in Downloads

**What the owner sees:** Command and Space, "Moblee", and nothing comes up; or two Moblees; or `open -a Moblee` fails. **Confirms it:** the check-up says the Moblee app is not in Applications. **Why:** the app was opened from Downloads and never moved. From there the Mac runs it out of a temporary copy, so it cannot be found by name and goes when Downloads is tidied. **Fix, owner:** open Moblee from wherever it is (Downloads, in Finder); since 0.8.1 it offers to move itself to Applications, one button. If the app has gone altogether, download it again; the wiki and everything added to it are untouched, and the app picks them up. Until then, anything can still be added with the one Terminal line under "Adding something", step 4.

## F25. The check says Google (or ElevenLabs) "cannot be seen from here", or an older Moblee says it is "not working", while Claude can plainly read the calendar

**Why:** connections made in the Claude app belong to the owner's Claude account and show only inside Claude. The checklist's check asks the `claude` command in Terminal, which signs in separately, and on a Mac where the owner only ever uses the Claude app it sees none of them. Before 0.8.1 that was reported as "not working", which was wrong. **Confirms it, Claude:** use the connection, read-only and small: today's calendar, the subject of the newest mail, a Drive search for one word. If it answers, it is connected, whatever the check says. A Drive "list recent files" call may come back "not implemented" while search works; that is the connector's gap, not a failure, so test Drive with a search. **Fix:** none needed. Mark the request `added` on the strength of the live read and say so on the owner's page. In Moblee the owner presses Done on the tile. If the live read fails too, the connection really is missing: "Adding something" again, and the three cards in Moblee say where to go.
