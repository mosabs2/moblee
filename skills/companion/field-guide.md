# Field guide

What goes wrong with a Moblee wiki, how to confirm it, what fixes it and who does the fix. Every entry up to F25 has been met in a real install; F26 to F28 were found while testing Moblee with ChatGPT. The check-up (`moblee-doctor.py` in the Moblee folder's `scripts/`) prints the entry number beside anything it finds, so start there, then read the entry.

"Owner" fixes are done by the owner, in the Moblee app or in a Terminal window of their own, because they change the assistant's settings or the Mac. "Assistant" fixes stay inside the vault. Nothing in this guide deletes anything. Where an entry differs by assistant it says **With Claude:** and **With ChatGPT:**; which one the owner uses is the one word in `~/.config/moblee/assistant`.

## F01. Claude asks permission for almost everything

**With Claude:** **Confirms it:** the check-up reports no permission rules. **Why:** the starter rules were never installed (an old version, or an install that stopped early). **Fix, owner:** open Moblee, which shows a Repair button when it finds the guard or the rules missing; or in Terminal, `python3 "<moblee folder>/safety/install-safety.py" --vault "<vault>"`. It adds the rules for routine, safe actions with the delete guard beneath them, and keeps a copy of the old settings. **With ChatGPT:** Moblee does not set this up for ChatGPT yet.

## F02. The delete guard is missing, not switched on, or not the pack's copy

**Confirms it:** the check-up says which. **Why:** an old version, a settings file replaced by hand, or an update that stopped. **Fix, owner:** the same Repair as F01. The guard cannot be installed or upgraded from inside the assistant, by design. Until it is back, the assistant takes extra care: no clean-ups, no moves out of the vault. **With ChatGPT:** the guard is kept in `~/.codex/hooks/` and entered in `~/.codex/hooks.json`, and the Terminal line in F01 puts both right. A repair or an update that only replaces the guard file keeps ChatGPT's trust; one that adds the entry needs the Trust steps, and says so when it finishes (F26). After either, ask for the proof again. Once the hook is trusted ChatGPT does not check the guard file itself, so the check-up's line that the guard "is this Moblee's own copy", together with the proof, is what shows the file has not been swapped. If the check-up says the guard is not running in ChatGPT, go straight to F26.

## F03. Claude's settings file does not load

**With Claude:** **Confirms it:** the check-up reports `~/.claude/settings.json` is not valid. **Why:** edited by hand, or written by another tool. **Fix, owner:** Moblee keeps dated copies under `~/.config/moblee/backups/`. The assistant lists them (reading is allowed) and gives the owner two Terminal lines: the first moves the broken file aside under a new name (`mv ~/.claude/settings.json ~/.claude/settings.json.broken`), the second copies the newest good one into its place. Nothing is overwritten. The assistant does not edit the file. **With ChatGPT:** the file is `~/.codex/hooks.json`, the check-up reports it under F02 when it does not load, and the same two steps mend it. Run the proof in F26 afterwards, because ChatGPT skips any hook it counts as new or changed.

## F04. Something has gone missing: a page, a folder, a section, some data

**Do not repair yet. Ask first:** is it a page, a section of a page, or data that should have arrived by itself? **Then search every place, renames first:** `git log --diff-filter=R --name-status` for pages renamed or moved, `git log --diff-filter=D --name-only` for deletions, and `git log -p -- "<path>"` for a page's earlier versions; the vault's `.trash/`; the Mac's Trash (Obsidian's default for deleted files); any sync folder; `archive/` and the Context Archive page; `raw/processed/` and `Clippings/processed/`. Obsidian's File recovery (Settings, Core plugins) is one more place, and only the owner can look there. **Most often** nothing was deleted: a page was renamed or split (tell the owner its new name and offer to rename it back; do not restore a second copy), a feed stopped (F05), or a housekeeping pass moved a section to an archive page. **Fix, assistant:** if it truly went, restore from git by copying the old version into place, tell the owner what happened, record it in the log. The check-up adds little to this one; go straight to the search.

## F05. Something that used to arrive by itself has stopped

**Confirms it:** the check-up lists Moblee's scheduled jobs and flags any that are not loaded or last ended with an error; the newest file in `outputs/lint/` is more than two weeks old; a made-to-measure job's log has no recent line. **Why:** the Mac was asleep at the time, a sign-in expired, a website changed, the job was set up with cron. **Fix:** the assistant reads the job's log and says why; a sign-in is the owner's to renew; reloading a Moblee job is the owner's, through Moblee or `bash "<moblee folder>/scripts/install-schedule.sh"`. Catch up the missed days by hand. If the job never reported its own failure, mend that first (the scheduled-job rules in `builders-rules.md`).

## F06. Claude refused to install Moblee, or called the instructions a possible attack

**Why:** the owner pasted a file of instructions into the assistant, or asked it to run the installer. A careful assistant treats pasted orders as a stranger's orders, and is right to. **Fix, owner:** the owner installs, with the Moblee app or `bash scripts/install.sh` in Terminal. The assistant can explain any step from `docs/02-install.md`.

## F07. Claude says it cannot write to `~/.claude/`

**With Claude:** **Why:** Claude Code protects that folder by design. **Fix:** nothing is broken. Skills, hooks and settings go in through the Moblee app or a Terminal line the owner runs. Never coach the owner to approve a prompt they do not understand. **With ChatGPT:** the folders are `~/.agents/` and `~/.codex/`, and in its default mode ChatGPT's sandbox asks the owner before anything is written outside the wiki folder. Nothing is broken, and the fix is the same: the owner says no to the request, and the change goes in through the Moblee app or a Terminal line. The one exception is `brand.css`, which the `design-your-brand` skill edits at the owner's request.

## F08. After adding a connection, Claude has forgotten the conversation

**With Claude:** **Why:** a new connection only loads when Claude is quit and reopened, and a new session starts fresh. **Fix, assistant:** read the owner's page (`wiki/Wiki Operations/Habits and Tools.md`), which holds what was agreed, and carry on from "Adding something", step 5. If the page is empty, the earlier session did not write things down first; apologise, ask again briefly, and write it down this time. **With ChatGPT:** Moblee does not set this up for ChatGPT yet. A session that has lost the thread for any other reason is mended the same way, from the owner's page.

## F09. The install or an item ended with an alarming message about pip, Homebrew or PDF tools

**Why:** an optional part could not be set up on this Mac as it stands (no Homebrew, an old pip). **Fix:** nothing is wrong with the wiki. PDF rendering is the `documents` item and can be added later. Say so plainly; people read any red text as failure.

## F10. A commit is refused

**Confirms it:** the message begins `[GATE]`. **Why:** the commit gate found a link to a page that does not exist, a file over its size limit, or a rules file over its limit. **Fix, assistant:** do what the message says (correct the link, create the missing page if it was meant to exist, fold or trim the file) and commit again. The gate is never bypassed to save time.

## F11. The wiki is on an older Moblee than the one on this Mac

**Confirms it:** the check-up shows two version numbers. **Fix, owner:** open the newer Moblee app, which offers the update; or `bash "<moblee folder>/scripts/update.sh"`. The update never touches the owner's pages and keeps copies of what it replaces. **With ChatGPT:** the check-up also gives this number when the wiki has no `AGENTS.md` or the size setting is missing (F27, F28), and the same update adds them. After an update, run the proof in F26.

## F12. The Mac is nearly full

**Confirms it:** the check-up shows free space under 5 GB. **Fix:** the assistant tells the owner what in the vault is large (usually `outputs/` and downloaded videos) and what each thing is. The owner decides and removes by hand. Large items on the checklist are not added until there is room.

## F13. The vault is inside a folder that iCloud syncs

**Confirms it:** the check-up says the vault is under a synced Desktop or Documents folder. **Why it matters:** anything that builds or writes many small files inside the vault can clash with the sync, and private material is being copied to iCloud. **Fix:** note it on the owner's page; keep generated files out of the vault; if the owner wants it moved, the move is theirs, with the assistant writing the steps, and `~/.config/moblee/vault-path` is updated afterwards by the owner.

## F14. A password, recovery phrase, card number or code has turned up

**Fix, assistant:** stop, leave it out of the wiki, tell the owner where it was found. The place for it is a password manager. If one is already in a page, tell the owner which page and line; they remove it by hand, and they should know that git still holds the old version, which matters if the vault is ever shared.

## F15. There is no Code tab in the Claude app

**With Claude:** **Why:** working in a folder on the Mac is part of Claude's paid plans. **Fix, owner:** a paid plan is needed to use Moblee with Claude. Say so plainly and leave the decision with them. **With ChatGPT:** this entry does not apply.

## F16. Obsidian does not show the wiki

**Fix, owner:** in Obsidian: Open another vault, Open folder as vault, then the wiki's folder (the check-up prints where it is). Obsidian is only the reading window; the wiki works without it.

## F17. A window offers to install "command line developer tools"

**Why:** the Mac's git and Python arrive with Apple's free developer tools, and something asked for them. **Fix, owner:** press Install and wait; it is safe and comes from Apple. Moblee needs them.

## F18. Things agreed with Claude were never added

**Confirms it:** the check-up lists requests still waiting. **Fix:** remind the owner once that Moblee has tiles waiting and offer to open it. If they have changed their mind, record the no and mark the request `declined`.

## F19. An old `get-started` skill sits beside the companion

**Why:** Moblee 0.7.0 called the first conversation `get-started`; it is now part of the companion. **Fix:** harmless. The next update moves the old copy to the backups folder.

## F20. The wiki feels like a heap: repeats, long pages, no order

**Fix, assistant:** run the health check ("lint the wiki") and read its report to the owner in plain words; run the `compact` skill on what it flags, which lists before it moves anything. Going forward, update existing pages before making new ones, as `CLAUDE.md` says (`AGENTS.md` with ChatGPT).

## F21. The evening lesson reminder never appears

**Fix, owner:** System Settings, Notifications, then allow notifications for Script Editor (or Terminal). The check-up shows whether the reminder job itself is loaded.

## F22. git printed a notice about a name and email being "configured automatically"

**Fix:** harmless, and only on wikis made by very old versions. The assistant sets a name and email for this vault only: `git config user.name "<name>"` and `git config user.email "<name>@<mac>.local"`.

## F23. One of Moblee's skills is missing, or a different skill is sitting under its name

**What the owner sees:** the install ended with "One part did not finish", or the assistant does not seem to know "guide me", or behaves oddly when asked for one of Moblee's skills. **Confirms it:** the check-up names the skills. **Why:** Moblee's skill names are ordinary words (`brain`, `companion`, `compact`, `galaxy`), and a folder of the same name was already among the assistant's skills (`~/.claude/skills`, or `~/.agents/skills` with ChatGPT): an older Moblee's copy, or something the owner put there. The installer never overwrites a skill it did not recognise, so it left it alone and said so. **Fix, owner:** open Moblee and press Repair, or in Terminal run `bash "<moblee folder>/scripts/install-skills.sh" --update`. Moblee's copies go in, and whatever was there before is moved to `~/.config/moblee/backups/`, never deleted. If what was there was the owner's own skill, tell them where it has gone and offer to bring it back under a different name (the move back is theirs to make).

## F24. The Moblee app cannot be found, or is still in Downloads

**What the owner sees:** Command and Space, "Moblee", and nothing comes up; or two Moblees; or `open -a Moblee` fails. **Confirms it:** the check-up says the Moblee app is not in Applications. **Why:** the app was opened from Downloads and never moved. From there the Mac runs it out of a temporary copy, so it cannot be found by name and goes when Downloads is tidied. **Fix, owner:** open Moblee from wherever it is (Downloads, in Finder); since 0.8.1 it offers to move itself to Applications, one button. If the app has gone altogether, download it again; the wiki and everything added to it are untouched, and the app picks them up. Until then, anything can still be added with the one Terminal line under "Adding something", step 4.

## F25. The check says Google (or ElevenLabs) "cannot be seen from here", or an older Moblee says it is "not working", while Claude can plainly read the calendar

**With Claude:** **Why:** connections made in the Claude app belong to the owner's Claude account and show only inside Claude. The checklist's check asks the `claude` command in Terminal, which signs in separately, and on a Mac where the owner only ever uses the Claude app it sees none of them. Before 0.8.1 that was reported as "not working", which was wrong. **Confirms it, assistant:** use the connection, read-only and small: today's calendar, the subject of the newest mail, a Drive search for one word. If it answers, it is connected, whatever the check says. A Drive "list recent files" call may come back "not implemented" while search works; that is the connector's gap, not a failure, so test Drive with a search. **Fix:** none needed. Mark the request `added` on the strength of the live read and say so on the owner's page. In Moblee the owner presses Done on the tile. If the live read fails too, the connection really is missing: "Adding something" again, and the three cards in Moblee say where to go. **With ChatGPT:** Moblee does not set this up for ChatGPT yet.

## F26. ChatGPT has not been told to trust the delete guard, or the guard has been updated since it was

**What the owner sees:** nothing, and that is the trouble. ChatGPT does not run a newly installed hook until the owner has reviewed it. Until then the guard is skipped, nothing on screen says so, and a deletion that should have been refused goes through. **Confirms it:** the check-up says it cannot see whether the guard has been trusted; run with `--prove-guard` it says "The delete guard is not running in ChatGPT". **Why:** Moblee has just been installed for ChatGPT, or an update or a Repair has added Moblee's entry to ChatGPT's hooks list. ChatGPT keeps its trust by that entry (its command, matcher, timeout and place in the list) and takes no account of the guard file the entry runs, so an updated guard file alone does not lose trust. This entry applies when the hook is new, or when the check-up or the app says trust is waiting; ChatGPT does not remind the owner. When the hook already shows as trusted there is no Trust button to press: ask for the proof and leave the steps. **An empty Hooks page:** if the Hooks page shows "No hooks found" and lists nothing, no folder has been opened in ChatGPT yet. The fix is to open the wiki folder first, then do the steps. **Fix, owner, five steps in ChatGPT:**

First open your wiki folder in ChatGPT (File menu, Open Folder). Until a folder has been opened in ChatGPT, its Hooks page is empty and does not say why. <!-- verify on testdev -->

1. Open the ChatGPT menu and choose Settings.
2. Choose Hooks, under the heading Coding.
3. Open "User config".
4. Press Trust beside the hook that ends `bash-guard.py`.
5. Turn its switch on.

If ChatGPT is open, quit it and open it again afterwards, so that it reads the whole rules file.

**The proof, owner:** in the Moblee app, press Prove the guard on the home screen. Without the app, in a Terminal window of their own, with the Moblee folder's real path filled in:

```bash
python3 "<moblee folder>/scripts/moblee-doctor.py" --prove-guard
```

It asks ChatGPT's agent to try two deletions in a scratch wiki. It can take up to three minutes, it uses a little of the owner's ChatGPT allowance, and the owner's wiki is not touched. "Proved" means the agent was refused and both things are still there. "CANNOT TELL" means neither proved nor disproved (ChatGPT was not signed in, was not found, or was too slow): look at the Hooks page by eye and run it again. Until it is proved, the assistant takes extra care: no clean-ups, no moves out of the vault.

**What the proof does and does not promise.** With Claude, the promise that the assistant cannot delete stands as written. With ChatGPT it holds once the hook is trusted and proven. OpenAI describes hooks as a guardrail and not a complete boundary, and a hook that crashes or takes too long lets the command through. ChatGPT's own sandbox is a second layer: in its default mode the agent does not write outside the wiki folder and the Mac's temporary folders, or use the network, without asking the owner, and it cannot change `.git`. The sandbox does not stop a deletion inside the wiki. The guard does.

**ChatGPT is working outside the wiki folder:** ChatGPT treats the wiki as an outside folder, asks approval for every write, and does not follow the wiki's rules. The likely cause is that the owner typed while Chat was chosen at the top of the window and pressed "Continue in Work", which carries the task on in a folder of ChatGPT's own, outside the wiki, where the wiki's rules are not read. **Fix, owner:** quit that chat, open ChatGPT and, from its File menu, choose Open Folder and pick the wiki folder. Make sure Work is chosen at the top of the window, and not Chat, before typing.

## F27. ChatGPT reads only the start of the wiki's rules file

**Confirms it:** the check-up says the setting `project_doc_max_bytes` is not in `~/.codex/config.toml`, or that the rules file is longer than ChatGPT reads. **What it means:** ChatGPT reads the wiki's rules from `AGENTS.md`, and by default only the first 32 KiB of it. Whatever lies past that point is never seen, so a rule near the end of the file is not followed and nothing says so. Moblee's installer raises the limit; here the setting is missing. **Fix, owner:** the next update adds it (F11); if ChatGPT is open, the owner quits it and opens it again afterwards, so that it reads the whole rules file. **Meanwhile, assistant:** tell the owner in one line, and if the check-up says the file is over the limit, offer the `compact` skill to shorten it. The assistant does not edit `~/.codex/config.toml`.

## F28. The wiki has a CLAUDE.md and an AGENTS.md that are separate files

**Confirms it:** the check-up says the two are separate files and can drift apart. **Why it matters:** Claude reads `CLAUDE.md` and ChatGPT reads `AGENTS.md`. As two files they are edited apart, Moblee keeps only `CLAUDE.md` up to date, and the two assistants end up following different rules. **What the layout should be:** one real file, with the other name as a link to it, so there is one set of rules. A wiki made for both has `CLAUDE.md` as the real file; one made for ChatGPT alone has `AGENTS.md` as the real file and `CLAUDE.md` as the link; after a change of assistant the updater keeps whichever is real and links the other. **Fix:** the updater run with `--assistant both` makes that layout, and it never chooses between two real files, so the second one is set aside first. Assistant, with the owner's yes: compare the two files and tell the owner what differs; fold anything found only in `AGENTS.md` into `CLAUDE.md`; move `AGENTS.md` into `archive/` under a dated name (nothing is deleted); commit. Owner, in Terminal: `bash "<moblee folder>/scripts/update.sh" --assistant both`, which adds `AGENTS.md` back as a link to `CLAUDE.md` (an owner who uses ChatGPT alone leaves the option off; the link is added just the same). Run the check-up again to confirm.

## F29. The wiki is inside Desktop, Documents or Downloads, where scheduled jobs cannot run

**Confirms it:** the check-up says the wiki is inside one of those three folders and names it. **Why it matters:** macOS protects them, and a scheduled job does not carry the permission the owner's own Terminal has, so anything Moblee runs on a schedule — the evening lesson reminder, the weekly health check, any job the owner has added — fails with "Operation not permitted" and shows nothing at all. It looks exactly like a job that was never set up, and it can go unnoticed for weeks. This is separate from F13: it is true whether or not iCloud is syncing the folder, and moving the wiki out of iCloud's reach does not fix it if the wiki is still under Desktop. **Fix:** the wiki moves out of those three folders, to somewhere like `~/Wiki`. The move is the owner's, with the assistant writing the exact steps, and `~/.config/moblee/vault-path` is updated afterwards. Until it moves, tell the owner plainly which of their scheduled things are not running, rather than leaving them to assume it works.

## F30. A file the assistant reads at every session is at or over the commit gate's size cap

**Confirms it:** the check-up names the file, its size in tokens and the cap it is measured against. **Why it matters:** the gate refuses a commit when `CLAUDE.md` (or `AGENTS.md`), `wiki/_context.md` or `wiki/Index.md` is over its cap, and it refuses **every** commit in the vault, not only Moblee's — so the first sign is usually the owner's own work failing to save, with a rule name and no explanation. It happened to an owner on 21 September 2026, whose rules file had grown past the cap the pack itself nearly filled; the cap was raised in v0.9.1 and this check exists so the next owner hears about it while there is still room. **Fix:** shorten the file. Move the parts the owner rarely needs into a page of their own and link to it from the file, which is what the `compact` skill does; nothing is deleted. The caps are ~16k tokens for the rules file, 12k for `_context.md` and 8k for `Index.md`, counted as characters divided by four.

## F31. The Moblee folder could not be found, so some checks could not be made

**Confirms it:** the check-up says CANNOT SEE against the delete guard, the skills, or both, and names this as the reason. **Why it matters:** several checks work by comparing what is installed with Moblee's own copy of it, and without the folder they have nothing to compare against. The most important is the guard: comparing the installed `bash-guard.py` with Moblee's copy is what shows it has not been swapped or edited, and `docs/09-safety.md` tells the owner that is the check to rely on. Until v0.9.2 these three reported a plain OK in that state, so **a swapped guard passed the check-up with nothing said**. **Fix:** run the check-up from the Moblee folder — `cd` to where Moblee was downloaded and run `python3 scripts/moblee-doctor.py` — or put the folder's path back in `~/.config/moblee/package-path`, which the installer writes and which goes stale if the folder is moved or thrown away. Nothing is wrong with the wiki itself; the check-up simply cannot see far enough from where it was run.
