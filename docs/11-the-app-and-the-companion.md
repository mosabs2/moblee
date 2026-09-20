# 11. The app and the companion

From v0.8.0 Moblee has two parts that work as a pair. The companion is a skill: it is how Claude gets to know you, in conversation, inside your wiki. The Moblee app is where anything is added to your Mac or to Claude, by you, with a button on your own screen. Claude prepares and explains; you add.

The app is offered on the Releases page of the GitHub repository when a signed build is available. Everything it does can also be done in Terminal; the install, updating and connections docs give the commands.

## What the app shows, and when

**Opened from anywhere but Applications, it first offers to move itself there.** A downloaded app opened from Downloads is run by macOS out of a temporary copy, so it cannot be found by name later and goes when Downloads is tidied. One button copies Moblee to Applications (or to the Applications folder in your home folder, on an account that may not write to the shared one), puts the copy you opened in the Bin, where it can be got back, and reopens. "Not now" carries on as before and asks again next time.

**On a Mac with no wiki yet, it installs one.** Each screen has one picture, one sentence and one button. It checks what the Mac needs, asks what Claude should call you, builds the wiki, and ends by showing how to open Claude in it and say "get me started". `docs/02-install.md` describes each screen.

**On a Mac that already has a wiki, it opens a home screen.**

- If the app carries a newer Moblee than your wiki has, it offers the update first.
- If the delete guard is missing, it shows a Repair button that switches it back on.
- If you and Claude have agreed to add something, it shows tiles, each with the reason in your own words, the time, the space, the cost, and an Add button. Some items the app adds by itself, some need a Terminal window that it opens for you, and some are connected by clicks in Claude's own app (`docs/10-connections.md`). For those the app shows three cards first (where to go in Claude, what to switch on by name, and the question to ask Claude that proves it worked), and the tile is finished by you pressing Done, because a connection made inside Claude can only be seen from inside Claude.
- If nothing is waiting, it says so, and its button opens Claude.

A skill Claude has written for you appears as a tile too. Pressing Add copies it to where Claude keeps its skills; an older copy is moved to `~/.config/moblee/backups/`. The app reads a small list in your wiki, `.moblee/requests.json`, and never writes to your wiki.

## What the companion does over the first weeks

**The first conversation.** Say "get me started". Claude asks, one question at a time, what you want to put in the wiki, whether there is anything you want to be held to, and how you work. It writes your answers down, helps you make your first page, and only then proposes one or two extras that clearly fit.

**After that, one offer at most.** Say "guide me" on any day. Claude offers one next step, with the reason: something still waiting in the app, something you keep doing by hand, something you asked to be held to, a part of the wiki you have not tried, or a small tool made for you. A no is recorded and not raised again for ninety days.

**Made to measure.** When you need something no item provides, Claude builds the smallest useful version inside your wiki, runs it once in front of you, and looks at it again in a month.

**It learns how you like to work.** Replies are short unless you ask for more. Each correction you make is written down in your words and followed from then on.

## Where things are recorded

What Claude learns about you is kept in your wiki, where you can read it. The page `wiki/Wiki Operations/Habits and Tools.md` holds how you work, how Claude talks with you, your corrections, what is waiting in Moblee, what is installed and why, what was made for you, and what you said no to. Things you asked to be held to are in `wiki/Identity.md`. Every install keeps a plain diary at `~/.config/moblee/install-diary.txt`, with no names in it.

## When something seems wrong

Tell Claude "something is wrong". Claude does not guess or start repairing. It runs the check-up, `scripts/moblee-doctor.py`, which changes nothing. Each finding is marked `OK`, `LOOK` or `PROBLEM`, and anything short of `OK` points at a numbered entry in the companion's field guide. The entry says what fixes it and who does the fix: Claude, inside the wiki, or you, with a button in Moblee or a line in Terminal.

If no entry fits, Claude offers to write a report for whoever helps you with Moblee. It goes to `outputs/` in your wiki as `moblee-report-<date>.md`. It holds the state of the setup and nothing from your pages: no names, no page titles, and your home folder written as `~`. Claude shows you what it says before you send it.

## What neither of them will ever do

Claude never runs an installer and never edits its own settings or skills folder. If you ask it to, it explains that these are yours to do. The app never writes to your wiki, and it adds only what you pressed a button for. Neither deletes anything: what is replaced is moved to a backups folder. Neither buys anything. Neither asks you to paste a file into Claude as instructions.
