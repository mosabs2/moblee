# Changelog

## v0.8.1 (20 September 2026)

The app and companion release. v0.7.0 made the owner the one who installs, which meant Terminal for everyone, and its first conversation ended in a command to run there. It also treated getting to know the owner as one conversation and the occasional review. This release gives the owner an app to install, update and add things with, and turns the first conversation into a standing guide that grows the wiki with them, one step at a time. The principle is unchanged: the owner runs every installer, nothing is pasted into Claude as instructions, Claude never installs anything or edits its own settings, and nothing deletes. Mac only. A paid Claude plan is needed for the Code tab in Claude's app.

### Added

- **The Moblee app** (source under `app/`), a small Mac app that is the installer. One picture, one sentence and one button per screen: welcome; a check of what the Mac needs (Apple's developer tools, Claude's app, and Obsidian marked "Can wait"), with a Get button for anything missing; one typed question ("What should Claude call you?"); a plain statement of what is about to be made and where; the build, shown as six pictures that light up (the wiki, its tools, its history, the guard, Claude's skills, finishing); and a hand-off with three numbered pictures (click Code in Claude's app, pick the wiki's folder, say "get me started"), the words being copied to the clipboard by the Open Claude button, and a receipt of what was made. Every screen can be read aloud on the Mac, honours Reduce Motion, is labelled for VoiceOver and is legible in dark mode. A build that stops offers Try again first, and a half-made wiki is finished, never doubled, even after the app is closed and reopened. The practice switches used for testing are refused unless `MOBLEE_PRACTICE=1` is set. The wiki is named after its owner (for example "Sam Wiki") and placed in a `Wiki` folder in the home folder; a taken name gets a number. The app runs the pack's own `scripts/install.sh` underneath, so an app install and a Terminal install are the same install. It carries the pack inside it and copies it once to `~/Library/Application Support/Moblee/pack-<version>`, because the wiki's tools need the pack later. The app is signed and notarised by Apple and is offered as `Moblee-0.8.1.zip` on the Releases page of the GitHub repository; the Terminal install in `docs/02-install.md` always works.
- **A home screen for a Mac that already has a wiki.** Tiles for the things the owner and Claude agreed to add, read from `.moblee/requests.json` in the wiki (the app never writes to the wiki); an Update screen when the app carries a newer Moblee than the wiki has, which runs `scripts/update.sh` underneath and shows nine steps; and a Repair button if the delete guard is missing, which runs `safety/install-safety.py`. Tiles are of three sorts: items the app adds by itself with a progress mark (`news-brief`, `trips`, `x-capture`, `weekly`, `lessons`, `voice`); items that need the owner at a Terminal window because of Homebrew's password, a sign-in or the `claude` command, where the app first shows a three-picture explanation and then opens a Terminal window that runs `python3 scripts/moblee-setup.py --only <item>`; and connections made by clicks inside Claude's own app, where the app shows the clicks as pictures and opens the connectors page. A skill Claude has drafted for the owner under `made-for-you/skills/<name>/` in the wiki appears as a tile too, and the app copies it into `~/.claude/skills/` when the owner presses Add; an older copy is moved to `~/.config/moblee/backups/`, never deleted.
- **The `companion` skill** (`skills/companion/`: `SKILL.md`, `method.md`, `builders-rules.md`, `field-guide.md`), which replaces `get-started`. It holds the first conversation ("get me started" still works, and so does "guide me"), in which the first page now comes before any talk of extras and at most two items are proposed. In every later session it offers at most one next step, with the reason. It records what is agreed on `wiki/Wiki Operations/Habits and Tools.md` and in `.moblee/requests.json`, builds small made-to-measure tools by the method in `method.md`, keeps replies short by default, writes down every correction the owner makes, runs a check-up when something seems wrong, and holds the setup reviews. It never runs an installer, never copies anything into `~/.claude/` and never edits Claude's settings.
- **`scripts/moblee-doctor.py`**, a read-only check-up of the wiki and the Mac. Plain findings marked `OK`, `LOOK` or `PROBLEM`, each pointing at a numbered entry in `skills/companion/field-guide.md` that says what fixes it and who does the fix. `--json` prints the same for a program. `--report` also writes `outputs/moblee-report-<date>.md` in the wiki, holding the state of the setup and nothing from the wiki's pages, marked `do_not_ingest`; an earlier report is never overwritten.
- **New sections on the `Habits and Tools` page**: "How Claude talks with the owner", "Working with the owner", "Waiting in Moblee" and "Made for the owner".
- **A section "The companion" in the vault's `CLAUDE.md`**, added to existing wikis by `scripts/patch-claude-md.py`: one guide, one offer, one page; corrections written down the moment they are made; short replies by default.
- **An install diary.** Every run of `scripts/install.sh` keeps a plain diary at `~/.config/moblee/install-diary.txt`: what ran, what passed, what failed and why. It has no names in it and writes the home folder as `~`, so it is safe to pass on when an install goes wrong.
- `docs/11-the-app-and-the-companion.md`, which explains the two together for an owner.

### Changed

- **`scripts/install.sh` takes its answers up front** (`--name`, `--vault-name`, `--location`), which is how the app runs it, and `--progress` prints one machine-readable line per step. A typed name containing `&`, `|` or a backslash now arrives as typed.
- **`scripts/moblee-setup.py`** gains `--list --json`; `--only <items> --yes`, which skips the "Start now?" question and is refused when started from inside Claude Code, since installing is the owner's act; and `--progress`. **`scripts/update.sh`** gains `--progress`.
- **The updater moves an old installed `get-started` skill to the backups folder** (`scripts/install-skills.sh`), once `companion` is installed. Left in place, it would answer to the same phrases.
- `README.md`, `START_HERE.md`, `skills/README.md` and the install, skills, updating, safety and connections docs updated for all of the above.

### Fixed before release, from the first run on a fresh account (20 September 2026)

The signed app was run end to end on a new macOS account with nothing on it, and the owner's Claude there wrote up what it met. Every finding was acted on.

- **The app moves itself to Applications.** Opened from Downloads it stayed there, twice over, and macOS ran it from a temporary copy: it could not be found by name, could not be replaced by a newer one, and would go when Downloads was tidied. It now offers the move on opening (one button; "Not now" asks again next time), clears the download mark from the copy so that the copy is run from where it is, puts the original in the Bin, and reopens. An account that may not write to `/Applications` gets `~/Applications`. The check-up reports an app that is not in either place (field guide F24).
- **A connection the check cannot see is reported as "cannot see", never as "not working".** Google and ElevenLabs are connected to the owner's Claude account; the check asks Terminal's `claude`, which signs in separately, so an owner on the Claude app with all three Google connections working was told none worked and the tile could never finish. `--check` now prints `CANNOT SEE` with the question to ask Claude that proves it, exits 0 when nothing is seen to be broken, and records such items under `unseen` in `setup-state.json`; the weekly health check reads that as "cannot tell". The companion proves a `clicks` item by one small read-only call through the connection, and the owner finishes the tile with Done (field guide F25).
- **The Google tile says where to go, what to switch on and how to tell it worked.** It used to open Claude and say nothing more. The three cards come from the pack (`steps` in `--list --json`), so Terminal owners read the same words.
- **The starter's dates are filled in.** The log's first entry was headed `[YYYY-MM-DD HH:MM ±TZ]` for ever, and the dashboard showed it so. `scripts/stamp-starter-dates.py` stamps the log, the working-state page and the index at install; the updater runs it on older wikis, dating them from their first commit and touching only lines that still hold the placeholder.
- **The Terminal window no longer asks "Start now?"** after the owner has pressed Add and then Open it, and no longer ends on Terminal's own "truncating history files" and "Deleting expired sessions", which read badly beside a promise that nothing is deleted: the window's throwaway shell is ended before it can print them.
- **Wording.** "0.0 GB of space" for a 5 MB item is now "5 MB"; a tile that takes no room says nothing about room; "Quit Claude and open it again so it sees the new skills" (or connections) says which.
- **The dashboard's inbox count** no longer counts the starter's own `HOW-TO-ADD-CONTENT.md` as pending. Its README says plainly that a browser which closes a tab without letting the page say goodbye leaves the server running for up to thirty minutes.
- **`lint-v2.py --help`** prints help and runs nothing; a mistyped switch is refused. It used to run a full lint and write a report.
- **The galaxy** leaves the blank daily-note template out of the picture and calls its count "pages with no links in or out", which is what it is; it was never the health check's "orphans", and the two are now not confused.
- **`log-append.py` keeps the minutes of a zone that has them** (`+0530`); it used to cut every zone to the hour, which would have put entries in the wrong hour for India, Iran, Nepal and others. The vault rules show the form by example.
- **`setup-state.json`** holds the whole list of what works under `working`, where it held only the last run's; the misleading `chosen` is gone (`last_run_items` says what it is).
- **Housekeeping commits leave an un-ingested source alone**: the companion commits only the two files its request touches, and the vault rules say the same for any commit that is not an ingest.

A reviewer who had seen none of the reasoning then read those fixes cold, and a second run was made on the same account with the fixed build. From those:

- **The move to Applications never leaves an owner without an app.** The new copy is made beside its destination under a temporary name, checked, and has its download mark cleared, before an older Moblee is set aside or the opened one goes to the Bin; a failure before that point changes nothing. It never moves onto itself, leaves alone anything called Moblee that is not Moblee, uses a Moblee already in Applications that is the same or newer, stays open with a plain sentence if the copy will not open, and sets the older one aside under a name that can be seen in the Bin ("Moblee older" and its version).
- **The app keeps `~/.config/moblee/package-path` pointing at the Moblee folder it is using.** On the second run a newer build settled its pack in a new folder while the note still named the old one, so the check-up compared the guard and the skills with stale copies and raised two false alarms (F02, F23).
- **A delete guard that is switched on but older than this Moblee's is offered for Repair**, as a missing skill already was, so the app and the check-up agree. An older guard does not know the newer pack's own scripts.
- **`app/scripts/release-app.sh` refuses to build from uncommitted work or with stale guard hashes**, since the app carries the pack as last committed; and `safety/release-hashes.py --help` prints help where it used to rewrite the hashes.
- **The Terminal window's shell is ended only when Terminal opened it for that file** (it is under ten seconds old), never a shell someone was already working in, and "Finished" is said only when the step finished.
- **An older wiki with no git history keeps its placeholder log header**, because today's date on the log's first entry would put the log out of order for ever; the script also keeps a file's own line endings and leaves alone a file it cannot read as text.
- **A sweep that could not see a connection says so in the saved record**, and a damaged record or note is started afresh, never a crash. The owner's Done answers the one asking it was given for.
- **Claude's Connectors page has moved** (seen September 2026: "Connectors has moved to Customise"). The cards, the Terminal steps and `docs/10-connections.md` say what to click when that page appears.
- The dashboard's inbox count leaves out the starter's note by its exact name, so an owner's own "how-to" file is counted; the galaxy skill and the install guide say what the code now does.

The number 0.8.0 was carried by the builds tested on that account and was never published; the published release is 0.8.1, so that the account's wiki, made at 0.8.0, is brought level by the app's own Update button.

### Verified

On the maintainer's two Macs, on the committed code: the installer test (62 checks: the app-style and Terminal installs, the diary, a place already taken, a broken settings file, a half-made wiki, a skill already under one of Moblee's names, the starter dates, the connections check seen and unseen, the saved record) and the release test (72 checks: a fresh install, the checklist engine, the updater on a wiki made by 0.7.0, the check-up, made-to-measure skills, and `safety/release-hashes.py --check`) passed on every round; the app test (46 checks) drew twenty-three screens in light and dark and drove the real window through an install, the home screen, each kind of addition, a stale note of where the pack is, an aged guard repaired, three hostile requests refused, and the move to Applications from a pretend Downloads against an older Moblee, first with a copy made to fail and then for real. Fifteen awkward owner names, among them Arabic, accented, quoted and command-shaped ones, installed correctly and none was ever executed. The signed app was then run twice by a person on a new macOS account with nothing on it, and the findings of both runs are the section above. A reviewer who had seen none of the reasoning read the changes before the second run.

## v0.7.0 (19 September 2026)

The delivery release. Up to v0.6.0 the quickest way in was to paste `START_HERE.md` into Claude: 3,200 words, addressed to Claude, telling it to walk the owner through installing a guard over its own commands, a list of actions it would stop asking about, and memories and skills in its own settings folder. That is the shape of an attempt to take control of an AI assistant, and a careful Claude said so and refused, which is the right response from Claude and a design fault in the pack. An early v0.6.0 install met exactly that refusal. The same install also ended with almost everything on the checklist accepted, because almost everything was ticked in advance and nothing had asked how the owner actually works. This release fixes both: the owner installs, and Claude gets to know the owner before suggesting anything.

### Changed

- **The owner runs the installer; nothing is pasted into Claude.** `START_HERE.md` is now a one-page guide for the person, with three steps (run `bash scripts/install.sh` in Terminal, open the wiki in Obsidian, open Claude in the wiki and say "get me started") and a plain explanation of why the installer is theirs to run. If they want help, they ask Claude in their own words and Claude reads the docs as information. `README.md`, `Welcome.md` and the docs follow.
- **Nothing on the checklist is ticked in advance.** Without a suggestion from Claude, the owner ticks what they want; the line at the top says how to get a suggestion instead. The "Habits" group is renamed "Looking after the wiki", since it holds the wiki's upkeep (weekly check, lessons, voice, the `vault` shortcut) and was read as a question about the owner's own habits.
- **The installer and the updater no longer open the checklist unasked.** Both point to the "get me started" (or "review my setup") conversation and offer the full checklist only to an owner who would rather choose alone (`[y/N]`). Both now record the pack's location at `~/.config/moblee/package-path`, so the owner's Claude can point back at the checklist.
- **A clinic note is carried out only on the owner's word.** The vault's rule used to say a clinic note's instructions are carried out as the owner's request. Now Claude acts on a clinic note only when the owner asks in the conversation for that named note; one merely found in `raw/` is mentioned and left alone. Claude reads the whole note first, says in plain words what it will do and waits for a yes, and never itself runs a step that deletes, sends anything out of the vault or changes Claude's own settings. Patched into existing vaults as an added paragraph.
- **The docs match the new path**: the download folder GitHub's Download ZIP produces (`moblee-main`), the install guide's steps in the order they happen, and every place that said the installer shows the checklist.
- **The older core skills are free of em dashes** (brain, compact, galaxy, wiki-interview, the capture template, a stylesheet comment), in line with the pack's own house style.

### Added

- **The `get-started` skill**, the eighth core skill. "Get me started" opens the owner's first conversation: Obsidian, what they want to be held to, then how they work (where their mail, calendar and notes live, what they read, watch and make, what they repeat, how much room the Mac has). It suggests only the checklist items that fit, each with the reason and with time, space and cost read from `--list`, and hands the owner one command to run themselves. Then it helps with the first page, and records the working items after `--check`. "Review my setup" holds the same conversation later, shorter, reading the log and the weekly report for what the owner has actually been doing. The skill never runs the installer, the updater or the checklist (read-only `--check` and `--list` excepted) and never edits Claude's settings.
- **`moblee-setup.py --tick <keys>`** opens the checklist with those items ticked and everything else unticked, for the owner to confirm or change; **`--list`** now prints each item's time, space, cost and foundations. The saved state records every item's status, refreshed by every run including `--check`, as a fallback for the weekly check, which looks at the Mac itself first where it cheaply can.
- **The `Habits and Tools` page** (`wiki/Wiki Operations/Habits and Tools.md`): how the owner works, what is installed and why, what they said no to, and the review history, with a `last_reviewed:` date. In the template and listed under the Index's Subfolder pages; the updater adds it to existing vaults through `scripts/add-habits-page.py`, never touching a page already there.
- **A "Habits and tools" section in `CLAUDE.md`**, patched into existing vaults: suggestions only for a reason the owner gave or the vault shows; notice when something is done by hand a third time that an uninstalled item would do, ask once, and record the answer; a no is not raised again for ninety days.
- **A "Habits and tools" check in the weekly health check** (informational). It reports when the setup conversation has not been held, when a review is more than ninety days old, and when three or more video links or X posts arrived in the last thirty days with the item that handles them not installed. Items the owner turned down in the last ninety days stay quiet, and so does the offer of the conversation itself once the owner has said no to it (recorded as `get-started`). A no is read from any line under "Said no to" that carries the item's key in backticks and a date in any common form. Orient offers a finding once, as a question, never as a to-do and never by starting the conversation unasked. The check is informational and never counts as an issue.

## v0.6.0 (19 September 2026)

The connections release. Up to v0.5.2 the wiki stood on its own: anything from the owner's calendar, mail or accounts reached it only as a file handed over by hand, and the optional parts of the pack were offered through yes/no questions scattered across the installer and the updater. This release puts everything optional on one checklist, connects the wiki to the owner's Mac and accounts, and makes Moblee a Mac-only pack.

### Added

- **The checklist** (`scripts/moblee-setup.py`). One list of everything optional, grouped as connections, tools, paid options and habits. Each line says what the item does, about how long it takes, how much space it uses and what it costs; items already working are marked and left alone; nothing paid is ticked by default. Before anything starts it shows the order of work, its estimate of time and space, and every moment the owner is needed at the keyboard. Sign-ins are the owner's, and for each one the checklist prints plain numbered steps, opens the right page and waits. It deletes nothing, copies every settings file it changes to `~/.config/moblee/backups/` first, keeps the output of long installs in a log under `~/.config/moblee/`, and installs Apple's developer tools, Homebrew and Node only when a ticked item needs them. `--check` tests every item without changing anything and saves the result to the vault's `outputs/setup/`; `--only <keys>` installs named items; `--list` prints the keys. Standard library only, so the Python that ships with macOS runs it. A full free install takes about an hour and a half the first time and several gigabytes. `docs/10-connections.md` explains every item.
- **Mac apps** (`mac-apps`): Calendar, Reminders, Mail and Notes through Orchard, with the owner clicking Allow on the Mac's permission pop-ups. Orchard's tools that move, bin or delete (files, reminders, reminder lists, slides, sheets) are blocked outright in Claude's settings, because the delete guard watches shell commands only. Needs macOS 14 or later.
- **Google** (`google`): Gmail, Google Calendar and Google Drive, connected by the owner on claude.ai's Connectors page.
- **GitHub** (`github`): GitHub's command-line tool, signed in by the owner with a code in the browser.
- **Chrome** (`chrome`): installs Chrome if absent and opens the Claude extension and the Obsidian Web Clipper for the owner to add, so Claude can read X, Instagram and YouTube through the owner's own logins.
- **Watch** (`videos`): the `watch` tool with the video downloader and converter, so a YouTube, Instagram, TikTok or X link can be watched and summarised.
- **Documents** (`documents`): the PDF renderer behind `wiki-to-pdf`, installed with its system libraries, plus Word, PowerPoint and Excel tools.
- **Editing skills** in the new `extras/skills/` folder: `film` (video editing, with the Remotion plugin and Node), `audio` (editing and read-aloud) and `pictures` (with ImageMagick). All three work on copies, never originals.
- **More skills**: `news-brief` (a brief on what the owner follows, every item confirmed by a second source and linked), `trips` (a page per trip with legs and day plans, reading booking mail only when asked) and `x-capture` (saves an X post into `raw/` through Chrome).
- **Skill maker** (`skill-maker`), which turns a routine the owner describes into a one-word command, and **Obsidian extras** (`obsidian-extras`) for canvases, databases and diagrams.
- **Generation with ElevenLabs** (`generation`), the one paid option: images, video, voices, music and sound effects through the owner's own ElevenLabs account. As of September 2026 there is a free tier with small limits and paid plans from about $6 a month; the checklist says to check elevenlabs.io/pricing and never buys anything. Claude asks before anything that uses credits.
- **A "Connected accounts and live facts" section** in the template `CLAUDE.md`: connected accounts are read only when a request needs them; Claude never sends, posts, deletes or spends without the owner's yes for that one action, and drafts by default; a hand-made export is replaced by the live connection where one exists; facts that change are fetched live and cited, and a news claim needs a second independent source. `scripts/patch-claude-md.py` adds the section to existing vaults, so the updater brings it in.
- `docs/10-connections.md`: each checklist item in plain English (what it connects, the exact sign-in steps, the cost, how to check it and add it later, what Claude will and will never do with it), and what each message from `--check` means.

### Changed

- **The installer installs the core skills itself.** Running `install-skills.sh` is no longer a separate step (it is still there, and the installer calls it).
- **The installer's scattered yes/no questions are replaced by the checklist.** The weekly health check, the learning path, the voice stack and the `vault` shortcut are now checklist items (`weekly`, `lessons`, `voice`, `vault-fn`), alongside the new connections. The installer shows the checklist at the end of a new install; the updater offers it after an update, when run in a Terminal.
- **Mac only.** The Windows installer, its `vault` function and its three guides were moved to `archive/windows/` (kept, not deleted) and are no longer maintained. `README.md`, `START_HERE.md` and the docs describe the Mac path only.
- `README.md`, `START_HERE.md` (the walkthrough now ends with the checklist and the `--check` command), `docs/00-overview.md`, `docs/01-prerequisites.md` (Homebrew and the PDF renderer now come from the checklist), `docs/02-install.md` and `docs/08-updating.md` updated for all of the above.

## v0.5.2 (19 September 2026)

A small fix release, from rehearsing an update on a v0.2 vault exactly as a new user would run it.

### Changed

- **The updater and the installer carry on when a question gets no answer at all.** If input ended at one of their questions (Ctrl-D, or a scripted run with its input closed), v0.5.1 stopped at that point without saying so, leaving an update unfinished and uncommitted, or a new vault half set up. End of input now counts as "no" and the run finishes. (A key pressed early is not lost: it becomes the answer to the next question, so wait for each question before typing.)
- **Two updater steps no longer fail silently.** If the skills or the `CLAUDE.md` step fails, the updater now says what has already been updated and how to carry on, as the safety step already did.
- **The commit gate no longer flags the pack's own pages when they arrive.** Its advisory on words such as "first" and "only" is meant for what you and your Claude write; on an update that added the learning path it printed ten warnings about the lessons page's own wording. `wiki/Identity.md` and the lessons page are exempt in the commit that adds them; later edits to them are checked as usual.
- **The updating guide** now says everything an update may add (the learning path's page and Index line, the daily-notes template) and which change it leaves for you to commit, and that the updater asks two questions, each to be answered once it appears.

## v0.5.1 (19 September 2026)

A refinement release: fixes from the first remote support sessions, an optional learning path, and a documentation pass for new readers.

### Added

- **The learning path** (`learning-path/`, optional). Thirty-two short lessons, one an evening, on getting the most from the wiki: the daily habits first, then housekeeping, the thinking tools, the things that produce something to show, and the habits that hold it together. Say "lesson" and Claude gives the next one in its own words, tied to what the log shows you have been doing, and records it. `scripts/install-learning-path.py` adds the lessons page, the coaching rule in `CLAUDE.md` and, on a Mac, a reminder at nine each evening (`com.moblee.nightly-tip`); the installer and the updater ask first, and it can be added later by hand (`docs/08-updating.md`). Mac with Claude Code only; the Windows track does not include it. The page, with its record of lessons given, is never replaced.
- **A clinic-files rule** in `CLAUDE.md`: a file in `raw/` marked `do_not_ingest: true` is never ingested, and any clinic step that writes into `~/.claude/` is handed to the owner as a Terminal paste. The updater adds it to existing vaults.
- **A plain-prose rule** in `CLAUDE.md`'s house style: prefer the plain word to the Latinate one, use "not X but Y" and its relatives only to correct a likely misreading, break long "and"-chained sentences. These are the habits a 2026 corpus study (The Economist, "How to spot AI writing", 30 July 2026) measured as more frequent in Claude's prose than in people's. The updater adds it to existing vaults.
- **An AI-writing sweep** in the weekly lint: files edited that week with a high rate of those constructions or words are listed for a read. Informational; it never rewrites.

### Changed

- **The updating guide** no longer says a clinic note removes the Terminal entirely: the safety step, which writes into `~/.claude/`, is always a paste by the owner. The clinic-note template says the same at its step 3.
- **The updater no longer stops when there is no Terminal to answer its questions** (for example when Claude runs it for a clinic note): the weekly-check and learning-path questions are skipped with a note saying how to add them, instead of the whole update halting at the first unanswered prompt.
- **The updater's message when the safety layer fails** now says what has already changed by that point (tooling, commit gate and skills, with backups) and what has not.
- **Documentation**: every page a new user reads was revised for plain, professional English with no personal references; the stale "four skills" count corrected to seven; the Windows guide's inbox path corrected to `raw/`.

## v0.5.0 (16 September 2026)

The safety release. It exists because a recipient's vault lost a folder the day after its first housekeeping run, and the review that followed found that the three things protecting the maintainer's own vault (a delete guard, a permission list, and a written identity for Claude) had never shipped: all three lived outside the vault, and the v0.4 port had taken the vault as the boundary of the pattern. The rule from here on: a recipient gets what the maintainer has, or the pack does not ship.

### Added

- **A safety layer, installed with the pack and not optional** (`safety/`). `bash-guard.py` runs before every shell command Claude composes and refuses deletion, history rewriting and force pushes however they are spelled, including the indirect forms; `install-safety.py` installs it, proves it fires with a blocked test command before registering it, backs up and parse-checks every settings file it touches, and merges the **starter permission rules** (`starter-permissions.json`: an allow list for routine work so the vault stops asking permission forty times an hour, and a deny ring for deletion and history rewriting). The allow list is safe only because the guard sits beneath it. If the safety layer fails to install, the installer stops.
- **`wiki/Identity.md`**, a fifth always-loaded file: who Claude is to the owner (verify rather than guess, challenge rather than flatter, never delete without a yes, the owner works through conversation). One list in it is the owner's own standing asks, filled in during the opening conversation (`START_HERE.md` step 8b). Excluded from skill reads and kept off the Index by design.
- **The never-delete hard rule and the plain-shell-command rule** in the template `CLAUDE.md`, first under Hard rules; `scripts/patch-claude-md.py` inserts them (and the identity and scheduled-lint lines) into an existing vault's `CLAUDE.md` at named anchors without replacing the file.
- **`scripts/update.sh`**: brings an existing vault to the current version without touching its content. There was no update path before v0.5; every earlier fix reached only fresh installs. Every replaced file is kept under `~/.config/moblee/backups/<stamp>/`; safe to run twice. `docs/08-updating.md`.
- **`VERSION`** in the pack and in every vault, so a census or an update can read what a vault runs.
- **Four starting memories** (`memory-seed/`, written by `scripts/seed-memory.py`): check the record before hedging, no superlatives without a count, plain English on housekeeping, plain shell commands.
- **The `galaxy` skill**, so "galaxy" rebuilds and opens the 3D graph; the builder had shipped since v0.4 with nothing to trigger it.
- **A weekly health check on a schedule** (`scripts/install-schedule.sh`, `scripts/cadence/`): the structural lint runs every Saturday at 09:04 through a launch agent, writing to `outputs/lint/`, logs kept under `~/.config/moblee/logs/` and archived rather than deleted after 90 days. The orient command reads the newest report. Offered at install and update.
- **`scripts/log-append.py`**, the one way a log entry is written: it reads the clock itself and emits the one correct header form, retiring hand-composed timestamps.
- **The commit gate wired through `scripts/hooks/`** and `git config core.hooksPath`, so the gate is versioned and updates reach it; nothing is written into `.git/hooks/` any more. Gate gains **G6**: a wikilink added to `wiki/` must resolve (folder links advisory).
- **Five more lint checks**, generalised: frontmatter schema (cluster notes, daily notes), duplicate frontmatter, session-metadata footers, prose boilerplate, skills-layer weight.
- **`clinic/`**: the maintainer's tools for looking after a vault remotely by exchanging files: a clinic-note template, a checker that runs every command in a note through the guard, and the ten-point standard a note must pass before it is sent.
- `docs/08-updating.md` and `docs/09-safety.md`.

### Changed

- **`compact`** now lists what it would drop (aged tombstone lines) or move (`outputs/` root sweep) and asks before doing it; only the archive-only rotations run unattended.
- **The lint's `outputs/` size check** no longer mentions deletion; it suggests moving old renders into an `archive/` folder.
- **`install-skills.sh`** never deletes: a skill being replaced is moved to the backups folder. New `--update` mode for the updater.
- **The five shared skills brought level with their live originals**: brain's eight read-only / three narrow-writeback split and restricted-folder rules; wiki-to-pdf's mandatory output verification (exit 3 on a leaked marker), timestamped render log, canonical rotation log, non-Latin slug fallback, interpreter self-heal and `--font-scale`; wiki-capture's template, provenance footer and no-commit rule; wiki-interview's cross-reference, contradiction and sensitive-content rules.
- **`voice/README.md`** now says plainly that the waiting nudge works in the Terminal but not in the Claude desktop app, which does not send the signal it relies on.
- `START_HERE.md`, `README.md`, `docs/02-install.md` and `docs/05-skills.md` updated for all of the above.

### Found by an unanchored review before release, and fixed

A reviewer given the pack and none of the reasoning behind it was asked what a Claude with only this could still do wrong. Fixed before the release: the permission rules were written in a form (`///path`) that Claude Code may not match, so no allow or deny rule for reading and editing would have worked, and three `Bash(... scripts/:*)` rules required a space that the commands never contain, so every tooling run would have prompted (now `//path` and `Bash(python3:*)`, `Bash(bash:*)`, which are safe only because the guard reads script files); an install that failed at the safety step left a half-configured vault and told the owner to delete the folder to retry (the installer now hands an existing vault to the updater, and prints the exact re-run line); the updater committed the owner's own uncommitted work under its own message and reported a no-op as an update (it now commits only what it changed, and says "already at" when nothing is); the safety installer could print a Python traceback on an unusual settings shape after it had already copied the guard (it now checks the shape first and stops with one sentence); the commit gate consulted the recorded vault path before the repository it was running in, so an owner with two vaults would have had one gated against the other (repository first now); the vault shipped no `.gitignore`, so lint reports, editor state and caches were swept into every commit; and the docs claimed the guard "fails safe" (it fails open, deliberately, and now says so and why), that a delete needs "your explicit yes" (there is no yes; the owner removes things themselves), that the update "never touches `wiki/`" (it adds `Identity.md`), and that a missed Saturday runs later (it runs later only after sleep, not after a shutdown). The guard itself was rebuilt as **v4** against the reviewer's list, which had found that v3 read only the command line. v4 reads every script file a command would run (language-aware, so prose in a shell script's messages does not trip it) and code piped into a shell; bounds moves and copies to the vault and refuses a move over an existing file or into `/tmp`, the Trash or another volume; refuses a truncating `>` over a page, a source or `CLAUDE.md`; skips git's global options before reading the subcommand and adds the spellings that discard work (`stash`, `checkout` of an existing path, `reset --merge`/`--keep`, `reflog expire`, `gc --prune`, `branch -D`, `commit --amend`, a changed `core.hooksPath`); peels the wrappers (`sudo -u`, `nice`, `env`, `xargs` with any flags, `eval`, `!`, `{ }`, redirections before the head) and reads backticks as commands; knows the Mac's own deletion tools (`unlink`, `trash`, `truncate`, `rsync --delete`, `zip -m`, AppleScript's `delete`); allows deletes of throwaway files under `/tmp` and the caches when the path resolves, so tooling with a lock file still works; and recognises the pack's own tools by content hash (`safety/release-hashes.py` keeps the list current and `--check` gates a release), so an owner's Claude can run the updater and the safety installer even though those files contain the primitives. `safety/test-guard.py` holds the 416-case suite (286 blocked, 130 allowed, including 22 candidates deliberately left allowed so a change of mind shows as a diff); a run takes about 25 ms. Syntax checks (`bash -n`, `python3 -m py_compile`) count as reads, not runs. Two things an owner may notice: `git stash` and `git checkout` of a path that exists are refused (use a branch, or ask), and the guard cannot be upgraded or copied into `~/.claude/hooks/` through Claude, which is a Terminal job by design.

### Verified

Fresh install in a sandboxed home on a stock path (Python 3.9.6, Apple git), then a real v0.4.1 vault and a real v0.2 vault, each with the owner's own content, installed the same way and updated in place: 59 checks, all passing, including that re-running the installer on an existing vault finishes through the updater, that a fresh vault is git-clean when the installer ends, and that a v0.2 vault (no tooling, no orient section, no Daily Notes) comes out with all of them and its own pages untouched. Among them: the guard refuses `rm -rf` and `find -delete` from the sandbox and passes `mv`; settings files parse after the merge; the never-delete rule sits first under Hard rules; the old `.git/hooks/` gate is moved aside and `core.hooksPath` set; the owner's page survives the update untouched and their name reaches `Identity.md`; the gate blocks a dangling link in both vaults; the lint runs clean of errors in both; running the updater twice changes nothing. Every log read line by line as a recipient would read it.

## v0.4.2 (11 September 2026)

Three fixes found by installing the pack as a fourteen-year-old would: fresh clone, stock Mac, no Homebrew, no git experience. Every one of them is output that reads as failure at a moment when a beginner is deciding whether the thing works.

### Fixed

- **The optional PDF step failed twice on a stock Mac and printed two pages of usage text.** v0.4.1 resolved `pip3` correctly but passed `--break-system-packages`, an option that arrived in pip 23.0; macOS ships **pip 21.2.4**, which aborts with a usage dump on an unknown option. Both the primary and the fallback attempt failed this way before the calm recovery message was reached. The step now checks for Homebrew first and skips cleanly when it is absent, since the Python packages are useless without the system libraries underneath them; where Homebrew is present, the flag is probed for rather than assumed and the verbose output goes to a log rather than the screen.
- **The user's first real commit printed git's automatic-identity notice.** Nine lines about `git config --global --edit` and `git commit --amend --reset-author`, which read as an error to someone who has never used git. The installer now gives the new vault a repo-local identity from the name already collected at the first prompt. The user's global git config is untouched.
- **The commit gate ran its prose advisory over `raw/` and `Clippings/`.** Those folders hold source material the user drops in and Claude never rewrites, so flagging their wording is noise; the concrete symptom was a first commit of a file containing "my first note" answered with a superlative warning. The check is now scoped to `wiki/`, where the prose is Claude's own.

### Verified

Installed end to end three times in a sandboxed `HOME` on a stock `PATH`, with Homebrew and the user's dotfiles deliberately absent. Confirmed working from that environment: the installer, the skills installer, the six bundled skills, placeholder substitution, the orient preflight, `lint-v2.py`, the commit gate (both that it stays silent on `raw/` and that it still fires on `wiki/`), the galaxy build, and the dashboard serving on `127.0.0.1:7373`. The dashboard and galaxy need only the Python that macOS already ships.

## v0.4.1 (4 September 2026)

First-install fixes, found by running the installer as a fresh user on a stock Mac rather than on the maintainer's machine.

### Fixed

- **`install-skills.sh` called `pip`, which does not exist on a stock Mac.** macOS ships `pip3` at `/usr/bin/pip3` and no bare `pip`, so accepting the optional PDF-dependencies step ended a successful install with `pip: command not found` followed by a Homebrew warning: alarming output at the end of a run that had in fact worked. The script now resolves `pip3`, then `pip`, then falls back to `python3 -m pip --user`, and reports a calm, accurate message if none succeeds.
- **The optional PDF step now reads as optional.** It says plainly that skipping is safe, that nothing else depends on it, and that Claude can set it up on request the first time a PDF is wanted. The Homebrew-absent branch no longer reads as an error.

## v0.4 (1 September 2026)

The maintainer's operational layer, generalised. Everything below was built and battle-tested on the maintainer's live vault June-August 2026, then ported with all personal content stripped and vault-path detection generalised (`~/.config/moblee/vault-path`, written by the installer; `MOBLEE_VAULT` env override; walk-up fallback).

### Added

- **Brain skill v3**, from six patterns to eleven. New: `graduate` (promote/demote/close items between `_context.md` status tiers, every move logged), `ghost` (answer in the reconstructed voice of a persona the wiki documents deeply, always labelled), and the temporal trio `today` / `close-day` / `schedule` operating on a new **Daily Notes layer** (`Daily Notes/_TEMPLATE.md` added to the vault template; planning-only notes, workday-keyed closes, carry-forwards seeded into the next day's plan). `trace` gains the drift register (position shifts, not just coverage history).
- **Structural health layer.** `scripts/lint-v2.py` (mechanical convention checks: log-header timestamps, dangling wikilinks, broken section anchors including aliased links, attribution presence, a vault-weight guard with token caps on the always-loaded files); `skills/compact` (the guard's executor: mechanical rotations free, lossy trims on sign-off); `scripts/vault-gate.py` (a pre-commit gate running the cheap deterministic subset at write time; the installer wires it into `.git/hooks/pre-commit`). Checks referencing optional folders skip silently when the folder is absent.
- **Orient.** The `orient` session-start convention added to the template `CLAUDE.md`, with `scripts/vault-orient-preflight.sh` (Obsidian alive, file freshness, last commit, uncommitted count).
- **Dashboard** (`dashboard/`). A local web view of the vault: orientation state, inbox counts, an Ask box that runs Claude against the vault, a galaxy rebuild button, and a **config-driven Visuals tab**: charts are defined in `dashboard/dashboard-charts.json` (CSV-backed or built-in series), so "add a chart of X to my dashboard" is a one-line config edit Claude makes for you. Ships with a working wiki-growth example.
- **Wiki Galaxy** (`scripts/wiki-galaxy/`). The offline 3D knowledge-graph view, rebuilt fresh from the vault on demand into `outputs/galaxy/`.
- **Voice stack** (`voice/`, optional, macOS). Replies read aloud via a Stop hook; audible rotating nudges when Claude is waiting on input or a permission click. Free with the built-in macOS voice; add an ElevenLabs API key to the Keychain and the same stack upgrades itself. Control helper: `voice on | off | stop | last | full | say | paste | status`; `voice full` reads the latest reply in full. Installed by `voice/install-voice.py` (settings backed up, hooks never duplicated), offered by the main installer.
- Template `CLAUDE.md` gains sections carried from the live vault's evolution: the orient command, data-freshness convention for volatile figures, Daily Notes conventions, compaction discipline (fold-don't-append on `_context`, stratify reference detail out of CLAUDE.md), and the health-layer wiring.

### Changed

- `scripts/install.sh` copies the vault tooling into the new vault (`scripts/`, `dashboard/`), always records the vault path at `~/.config/moblee/vault-path`, installs the commit gate, and offers the voice stack on macOS.
- `docs/05-skills.md` rewritten for the eleven-pattern brain and the new compact skill.

### Not ported, deliberately

The maintainer's personal automations (scheduled news briefs, domain dashboards, semantic recall, cross-machine sync tooling) stay out: they are one person's assistant, not the pattern. The pattern is what ships.

### Migration

Existing installs keep working. To adopt v0.4 pieces on an existing vault: re-run `scripts/install-skills.sh` (updates brain, adds compact), copy `scripts/lint-v2.py`, `scripts/vault-gate.py`, `scripts/vault-orient-preflight.sh`, `scripts/wiki-galaxy/` and `dashboard/` into your vault, write your vault's path to `~/.config/moblee/vault-path`, create `Daily Notes/_TEMPLATE.md` from the template, and optionally run `voice/install-voice.py`.

## v0.3 (5 June 2026)

`wiki-to-pdf` rendering upgrades, ported from the maintainer's live skill and brand-abstracted so they are driven by your own `design-your-brand` settings.

### Added

- **CV / statement render style** (`--style cv`). A second, distinct visual language alongside the default brand template: no cover, no gradient bars, no monogram cover. An EB Garamond masthead, a brand-colour letter-spaced subtitle, a brand-colour rule, an EB Garamond lede, brand-colour uppercase section labels mapped from H2 headings, body copy in your brand typeface, and a single faint centred monogram watermark on every page (rendered only if a monogram is configured). New files: `skills/wiki-to-pdf/cv.css` and `skills/wiki-to-pdf/template-cv.html`.
- **Chart pre-rendering** in both styles. Fenced ` ```vega-lite ` (inline JSON) blocks render to inline SVG, and ` ```mermaid ` blocks render to an embedded PNG via the `mmdc` CLI. Both dependencies are optional (`pip install vl-convert-python`; `npm i -g @mermaid-js/mermaid-cli`); a missing dependency or a malformed block degrades to a small error box rather than failing the whole document.
- New `render.py` flags: `--style brand|cv`, `--subtitle`, `--watermark`, `--footer-label`, and `--no-charts`.

### Changed

- `skills/wiki-to-pdf/render.py` gained the `render_cv` path, the `pre_render_charts` step (wired into both render styles), and the `--style` dispatch in `main()`. The brand path is unchanged in behaviour.
- `skills/wiki-to-pdf/SKILL.md` documents the CV style, charts, and the new flags; the stale "WeasyPrint does not handle Mermaid" limitation was corrected.
- `skills/design-your-brand/SKILL.md` notes that the configured monogram doubles as the CV-style watermark.

### Brand abstraction

The CV style reads `--brand-primary`, `--brand-secondary`, `--brand-body`, and `--brand-font-family` from the same `brand.css` `:root` block that `design-your-brand` writes, so one brand setup drives both render styles. No maintainer-specific colours, fonts, or assets are baked in. The EB Garamond serif is the fixed signature of the statement style.

## v0.2 (25 May 2026)

Windows support added.

### Added

- `scripts/install.ps1`: PowerShell installer for Windows. Mirrors the bash `install.sh` step for step: collects user name, vault name, vault location; refuses to overwrite an existing directory; copies the vault template to the destination; substitutes `[Your Name]`, `[Your Vault Name]`, `[Your Vault]` placeholders; initialises git; optionally adds the `vault` function to the user's PowerShell profile.
- `scripts/vault.ps1`: PowerShell version of the session-start `vault` function. Reads the vault path from `$env:USERPROFILE\.config\moblee\vault-path`, auto-commits pending changes, shows recent git history, and confirms the vault is ready.
- `docs/01-prerequisites-windows.md`: Windows-specific prerequisites doc covering Obsidian for Windows, Git for Windows, claude.ai web chat (in place of Cowork), PowerShell 7, and a brief WSL2 alternative.
- `docs/02-install-windows.md`: Windows install walkthrough. Mirrors the structure of `02-install.md` (Mac) and covers the PowerShell execution-policy gate, post-install steps, Windows-specific quirks, and troubleshooting.
- `docs/07-windows-workflow.md`: Day-to-day Windows-track workflow document. Covers claude.ai web chat as the Claude interface, the manual ingest workflow that replaces Claude Code automation, manual workarounds for each of the four bundled skills (`brain`, `wiki-capture`, `wiki-to-pdf`, `design-your-brand`), and a note on cross-platform vault portability.
- `CHANGELOG.md`: this file. Records the v0.1 to v0.2 transition.

### Changed

- `README.md`: clarified that Moblee now supports Windows alongside Mac, with Mac as the default path and Windows as the manual-workflow alternative. Added Windows pointer to the prerequisites and install sections.
- `START_HERE.md`: extended the Claude briefing to recognise that the user may be on Mac or Windows, and to branch the install guidance accordingly. The platform-detection step is the new first thing Claude does in the conversation.
- `docs/00-overview.md`: added a one-paragraph note acknowledging the Windows track and pointing at the Windows-specific docs.

### Trade-offs documented in v0.2

The Windows track loses some automation relative to the Mac path. Captured explicitly so users can decide whether the trade-off suits them.

- **No Cowork.** The desktop Claude application is Mac-only. Windows users use claude.ai web chat as their Claude interface.
- **No Claude Code skills auto-load on the default Windows path.** Claude Code itself runs on Windows but is documented as advanced setup rather than the default. The four bundled skills (`brain`, `wiki-capture`, `wiki-to-pdf`, `design-your-brand`) target Claude Code on macOS in v0.2; manual workarounds for each are documented in `docs/07-windows-workflow.md`.
- **`wiki-to-pdf` is Mac-only in v0.2.** WeasyPrint dependencies on Windows are fiddlier than the Homebrew install on Mac. Windows users can render unbranded PDFs from Obsidian's built-in export.
- **Git commits are manual via the `vault` function plus a closing `git commit`.** The Mac path automates this through Claude Code; Windows users run the `vault` function at session start (auto-commits pending changes) and `git add . && git commit -m "..."` at session close.

These are the real costs of the Windows path. The benefit is that Windows users can build a working Karpathy-pattern wiki today without needing a Mac.

### Migration

Existing v0.1 installs on Mac continue to work without changes. No vault-template, skills, or Mac script content was modified for v0.2. The new files are Windows-specific additions only.

## v0.1 (15 May 2026)

Initial public release.

- Mac install path (`scripts/install.sh` and `scripts/install-skills.sh`).
- Vault template with `CLAUDE.md`, `Welcome.md`, the four canonical files (`wiki/Index.md`, `wiki/_context.md`, `wiki/log.md`), and methodology pages under `wiki/`.
- Four bundled Claude skills under `skills/`: `brain`, `wiki-capture`, `wiki-to-pdf`, `design-your-brand`.
- Documentation under `docs/`: overview, prerequisites, install, first conversation, first ingest, skills reference, Karpathy method explainer.
- `START_HERE.md` for one-paste Claude-guided setup.
- MIT license.

First shipped on 15 May 2026.
