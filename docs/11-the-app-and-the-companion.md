# 11. The app and the companion

From v0.8.1 Moblee has two parts that work as a pair. The companion is a skill: it is how your assistant gets to know you, in conversation, inside your wiki. The Moblee app is where anything is added to your Mac or to Claude, by you, with a button on your own screen. Claude prepares and explains; you add.

**With Claude:** both parts work as this page describes. **With ChatGPT:** the companion skill is installed for ChatGPT as well, and the app's tiles and the extras they add are for Claude. Moblee does not set this up for ChatGPT yet.

The app is offered on the Releases page of the GitHub repository, signed and notarised by Apple. Everything it does can also be done in Terminal; the install, updating and connections docs give the commands.

## What the app shows, and when

**Opened from anywhere but Applications, it first offers to move itself there.** A downloaded app opened from Downloads is run by macOS out of a temporary copy, so it cannot be found by name later and goes when Downloads is tidied. One button copies Moblee to Applications (or to the Applications folder in your home folder, on an account that may not write to the shared one), puts the copy you opened in the Bin, where it can be got back, and reopens. "Not now" carries on as before and asks again next time.

**On a Mac with no wiki yet, it installs one.** Each screen has one picture, one sentence and one button. It checks what the Mac needs, asks what your assistant should call you and which assistant you use, builds the wiki, and ends by showing how to open your assistant in it and say "get me started". With ChatGPT it shows the Trust step before that last screen. `docs/02-install.md` describes each screen.

**On a Mac that already has a wiki, it opens a home screen.**

- If the app carries a newer Moblee than your wiki has, it offers the update first.
- If the delete guard is missing, it shows a Repair button that switches it back on.
- If you and Claude have agreed to add something, it shows tiles, each with the reason in your own words, the time, the space, the cost, and an Add button. Some items the app adds by itself, some need a Terminal window that it opens for you, and some are connected by clicks in Claude's own app (`docs/10-connections.md`). For those the app shows three cards first (where to go in Claude, what to switch on by name, and the question to ask Claude that proves it worked), and the tile is finished by you pressing Done, because a connection made inside Claude can only be seen from inside Claude.
- If nothing is waiting, it says so, and its button opens Claude.

A skill Claude has written for you appears as a tile too. Pressing Add copies it to where Claude keeps its skills; an older copy is moved to `~/.config/moblee/backups/`. The app reads a small list in your wiki, `.moblee/requests.json`.

**What the app writes into your wiki, and when.** It used to write nothing at all, and that is no longer true, so here is the whole of it. It never touches a page you or your assistant wrote, and it never deletes anything. It writes only into the two folders meant for things arriving: a file you drop on Moblee goes into `raw/` (v0.9.5), and the report from **Check my wiki** goes into `raw/` as well (v0.9.6). It also keeps its own small notes in the hidden `.moblee/` folder. That is all. Everything else — building the wiki, updating it, repairing it — is done by running the pack's own scripts, the same ones a Terminal user runs.

## What the companion does over the first weeks

**The first conversation.** Say "get me started". Your assistant asks, one question at a time, what you want to put in the wiki, whether there is anything you want to be held to, and how you work. It writes your answers down, helps you make your first page, and only then, with Claude, proposes one or two extras that clearly fit.

**After that, one offer at most.** Say "guide me" on any day. Your assistant offers one next step, with the reason: something still waiting in the app, something you keep doing by hand, something you asked to be held to, a part of the wiki you have not tried, or a small tool made for you. A no is recorded and not raised again for ninety days.

**Made to measure.** When you need something no item provides, your assistant builds the smallest useful version inside your wiki, runs it once in front of you, and looks at it again in a month.

**It learns how you like to work.** Replies are short unless you ask for more. Each correction you make is written down in your words and followed from then on.

## Where things are recorded

What your assistant learns about you is kept in your wiki, where you can read it. The page `wiki/Wiki Operations/Habits and Tools.md` holds how you work, how your assistant talks with you, your corrections, what is waiting in Moblee, what is installed and why, what was made for you, and what you said no to. Things you asked to be held to are in `wiki/Identity.md`. Every install keeps a plain diary at `~/.config/moblee/install-diary.txt`, with no names in it. ChatGPT has no hand-written memory folder, so with ChatGPT the assistant's standing notes are kept on a wiki page too, `wiki/Wiki Operations/Assistant Memory.md`.

## When something seems wrong

Tell your assistant "something is wrong". It does not guess or start repairing. It runs the check-up, `scripts/moblee-doctor.py`, which changes nothing. Each finding is marked `OK`, `LOOK`, `PROBLEM`, `CANNOT SEE` or `CANNOT TELL`, and a `LOOK` or a `PROBLEM` points at a numbered entry in the companion's field guide. `CANNOT SEE` and `CANNOT TELL` mark what the check-up has no way to verify, and the line says how to check. The entry says what fixes it and who does the fix: your assistant, inside the wiki, or you, with a button in Moblee or a line in Terminal. With ChatGPT, the check-up cannot see whether you have trusted the delete guard; `python3 scripts/moblee-doctor.py --prove-guard`, run by you from the Moblee folder, proves it (`docs/09-safety.md`). In the Moblee app, press Prove the guard on the home screen. The proof uses a little of your ChatGPT allowance.

If no entry fits, your assistant offers to write a report for whoever helps you with Moblee. It goes to `outputs/` in your wiki as `moblee-report-<date>.md`. It holds the state of the setup and nothing from your pages: no names, no page titles, and your home folder written as `~`. Your assistant shows you what it says before you send it.

## When somebody is helping you: the health card

Most people have somebody who is good with computers: a relative, a neighbour, a friend. That person does not want to read forty findings, and you may not want them reading your wiki. So the check-up can print one screen for them instead. Say "somebody is helping me" and your assistant offers it, or run it yourself:

```bash
python3 "<moblee folder>/scripts/moblee-doctor.py" --card
```

One screen, and nothing else on it: whether your wiki is healthy, what is wrong with the worst first and one line each, and what to do next. Beside each line is a number, and that is the entry in the field guide that explains it, so your helper can look it up or ask your assistant to read it out. If more is wrong than fits, the card says how many it has not shown and that the full check-up lists every one.

**It is safe to show anybody.** It carries the same care the report does: your home folder written as `~`, your wiki's folder written as `<wiki>`, no page of your wiki named, nothing you have written on it, and no secret or any part of one. Where the check-up has found something in a page that looks like a secret, the card counts them and never says which page, because the name of a page is something you wrote.

**It says what could not be checked.** Some things cannot be seen from where the check-up stands, and those get a section of their own. A card that quietly left them out would tell your helper your wiki was healthy when nothing had looked, so it never calls a wiki healthy while anything is unchecked.

To keep a copy, or to hand one over, add a name for it:

```bash
python3 "<moblee folder>/scripts/moblee-doctor.py" --card --card-file ~/Desktop/health-card.txt
```

That writes the card and changes nothing else. It will replace an earlier card of the same name; if there is a file of that name that is not a health card, Moblee leaves it exactly as it is and says so.

## Checking your wiki yourself: "Check my wiki"

From v0.9.6 the Moblee app has a **Check my wiki** button in the corner of its home screen. Press it and the app runs the same check-up for you. You type nothing, you answer no permission prompts, and you do not have to ask your assistant. It takes a few seconds, and it changes nothing in your wiki.

You then see the health card on screen, at a size you can read across a room, with a listen button beside it. And the app saves a report into your wiki's `raw/` folder. Press **Show me the file** under the card and that folder opens with the report picked out, so you do not have to go looking for it. **Send that file to whoever looks after Moblee for you.** Its name begins `clinic-report-` and carries the day it was made. If a report of that name is already there, the new one is given a number rather than written over the old one.

The report carries the same care as everything else Moblee writes for somebody else to read: your home folder as `~`, your wiki's folder as `<wiki>`, no page of your wiki named, and no secret or any part of one. What it does carry is your name, counts, dates, and the health card word for word.

Two things it cannot do, and says so on the report rather than leaving you to wonder. It cannot ask you the two questions a person would have asked, so that part of the report says plainly that nobody was asked and puts nothing in their place; if you want to add your answers, tell your assistant "add my answers to the clinic report in raw". And it lists what needs attention rather than every single line the check-up looked at, because the card is one screen; your assistant can print the whole of it.

If the check-up cannot run at all — this Moblee has no copy of it, it stops with an error, your Mac's delete guard refuses it, or it is still going after a minute and a half and Moblee stops it — you are told which of those happened, told that nothing in your wiki has changed, and a report saying exactly that is still saved, so the person helping you learns that the check-up itself is the thing that is broken.

The button is greyed out while a wiki is being made, updated or repaired, and while a dropped file is still being copied in: a check-up of a wiki that is being written to at that moment would describe neither the wiki before nor the wiki after.

## What neither of them will ever do

Your assistant never runs an installer and never edits its own settings or skills folder. If you ask it to, it explains that these are yours to do. The app writes into your wiki only where something is arriving — a file you dropped, a check-up report — and never into a page you or your assistant wrote; it adds only what you pressed a button for. Neither deletes anything: what is replaced is moved to a backups folder. Neither buys anything. Neither asks you to paste a file into your assistant as instructions.
