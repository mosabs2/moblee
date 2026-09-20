# 08. Updating an existing vault

You never reinstall Moblee, and you never rebuild your wiki. Your pages, your log, your inbox and your daily notes are yours; the pack only ever replaces its own tooling around them.

## What an update changes, and what it never touches

An update replaces the scripts in `scripts/` and `dashboard/`, the skills in your Claude skills folder, the safety guard, and adds any new rules to `CLAUDE.md` by inserting them at named places rather than replacing the file. From v0.6.0 that includes the section "Connected accounts and live facts", which tells your Claude to read connected accounts only when you ask, never to send, post, delete or spend without your yes, and to check facts that change against a live source. Inside `wiki/` it adds only `wiki/Identity.md` and the `Habits and Tools` page if you do not have them (a page already there is never touched; the companion adds any newer sections to it in conversation) and, if you choose the learning path, its lessons page and one line for it in `wiki/Index.md`; it never touches your pages, `raw/`, `Clippings/`, your daily notes or the log (it only adds the `Daily Notes/_TEMPLATE.md` template if you have none). It commits the files it changed and leaves any work of yours that was not yet committed exactly as it was; the one exception is the learning-path line in `wiki/Index.md`, which it leaves uncommitted so that it goes in with your own next edits. Every file it replaces is first copied to `~/.config/moblee/backups/<date and time>/`, so nothing is lost even if you change your mind.

From v0.8.1 the skills step also moves an old `get-started` skill aside. That skill is now part of the `companion` skill, and left in place it would answer to the same phrases. Once `companion` is installed, the old copy is moved to `~/.config/moblee/backups/<date and time>/skills/`. It is not deleted. The update also adds a section called "The companion" to `CLAUDE.md`.

## The easy route: the Moblee app

If you have the Moblee app, download the newer app from the Releases page of the GitHub repository when a signed build is offered there, and open it. When the app carries a newer Moblee than your wiki has, it opens with the sentence "A newer Moblee is ready for your wiki.", the two version numbers, and the line "Your pages are not touched." Press Update. The update is shown as nine pictures that light up in turn: tools, the gate, skills, the guard, the rules, new pages, the weekly check, lessons, and finishing. When it says "Your wiki is up to date.", press Done.

The app runs the pack's own `scripts/update.sh` underneath, so everything in the section above holds for it. It asks no questions. If you already have the weekly health check or the learning path, they are refreshed; if you do not, an update run this way does not add them, and each can be added later (`docs/10-connections.md`). If the update stops, the app says "The update stopped. Nothing of yours was changed." The updater is safe to run again, and running it in Terminal, as described below, prints the message that says why it stopped.

If no signed app is offered yet, use the Terminal route below. It always works.

## The Terminal route

1. Download the new Moblee package the same way you got the first one (a fresh `git clone`, or download and unzip). Keep it separate from your vault.
2. Open Terminal, go into the new Moblee folder, and run:

```
bash scripts/update.sh
```

3. It finds your vault by itself (it remembers where the installer put it). If it cannot, run `bash scripts/update.sh` followed by the path to your vault.
4. Answer the questions it may ask: whether to schedule the weekly health check, and whether to add the learning path. Wait for each question to appear before typing.
5. When it says "Updated to", it suggests asking Claude which extras suit you ("review my setup" in your wiki, or "get me started" if you have never done it; the `companion` skill answers to both), then asks "Would you rather choose from the full checklist yourself now?". Press Return to leave it, or type `y` to open it. The checklist connects the wiki to your Mac's Calendar, Reminders, Mail and Notes, to Google, GitHub and Chrome, and adds tools for video, documents and editing. Items that are already working are marked and left alone, and each line says the time, space and cost before anything starts. Ticking everything free takes about an hour and a half the first time and several gigabytes; nothing is ticked in advance. `docs/10-connections.md` explains every item.
6. Open Claude Code in your vault and say `orient`. If you added any connections, quit Claude Code and open it again first so it sees them.

Running the updater twice is safe. Each step checks what is already there and skips it.

## The checklist, any time

The checklist is not tied to an update. From the Moblee folder, run it to add or repair anything:

```
python3 scripts/moblee-setup.py
```

or test that everything still works, changing nothing:

```
python3 scripts/moblee-setup.py --check
```

To add a single item, name its key (for example `python3 scripts/moblee-setup.py --only google`); `--list` prints every key.

## If you would rather not use the Terminal

Ask whoever gave you Moblee for a clinic note. That is a file you drop into your `raw/` folder; your own Claude reads it, carries out the update step by step, and writes a report you can send back. One part still needs you: anything written into the hidden `~/.claude/` folder (the delete guard and its settings) has to be pasted into Terminal by you, because your Claude is not allowed to write there. The clinic note gives you the exact line to paste for that part. An update run this way does not offer the checklist, since there is no Terminal for it to ask in; run `python3 scripts/moblee-setup.py` yourself afterwards if you want it. Its sign-ins (Google, GitHub, Chrome, the Mac's permission pop-ups) are yours in every case.

## Adding the learning path later

The learning path is thirty-two short lessons on getting the most from the wiki, one an evening, with an optional reminder at nine each evening. It needs Claude Code. If you said no when asked, or want it now, tick it on the checklist (`python3 scripts/moblee-setup.py --only lessons`), or run this from the folder where you downloaded Moblee (the same place you run the updater from), naming your vault:

```bash
python3 scripts/install-learning-path.py --vault ~/Wiki/MyWiki
```

Use `--hour 20` for a different reminder time, or `--no-reminder` to have the lessons without a notification. Running it again is safe: the lessons page, with its record of which lessons you have had, is never replaced. Then open Claude Code in your vault and say **lesson**. If the reminder never appears, allow notifications for Script Editor in System Settings, under Notifications.

## Checking what version you have

The file `VERSION` in your vault says which version of the pack it was last updated to. Vaults installed before v0.5 have no such file, and the updater treats them as "before 0.5".
