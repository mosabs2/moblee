---
name: get-started
description: The owner's first conversation in a new Moblee wiki, and the later setup reviews. Trigger when the owner says "get me started", "set me up", "start the setup", "what should I install", "which extras do I need", "prepare my checklist", "review my setup", "is my setup still right", or any clear variant, and when the owner says yes to the one-time offer of it that orient makes after the weekly health check reports the conversation has not been held or a review is due (the offer itself is only a question; never start this conversation unasked). Detect the vault at runtime (the MOBLEE_VAULT environment variable, then ~/.config/moblee/vault-path, then walking up from the working directory for a folder containing wiki/Index.md) and the Moblee folder from ~/.config/moblee/package-path. Asks how the owner uses their Mac and what they read, watch and make, proposes checklist items with a reason for each, records the answers on wiki/Wiki Operations/Habits and Tools.md, and hands the owner one Terminal command that opens the checklist with those items ticked. Never installs anything itself and never changes Claude's own settings. Do not trigger on ingest, lint, or connection-testing requests (those run `moblee-setup.py --check` directly).
---

# Getting started, and keeping the setup right

The owner has already run the installer in Terminal, so the vault, the safety layer and the core skills are in place. This conversation does the rest: it gets to know how the owner works, suggests the extras that fit, and gives them their first real page. It has two modes. **Getting started** is the first conversation. **Setup review** is the same conversation held again later, shorter, when the owner asks or when the weekly health check says one is due.

The checklist of extras (`scripts/moblee-setup.py` in the Moblee folder) changes Claude's own settings and signs the owner in to accounts, so **the owner runs it in Terminal, never Claude**. Claude prepares the list and explains it; the owner confirms each tick on their own screen. This split is what makes the setup trustworthy, and it is why nothing in this skill runs an installer.

## Finding things

The vault is found as the description says. The Moblee folder's path is in `~/.config/moblee/package-path`; if that file is missing, ask the owner where they downloaded Moblee. Get the current item list, with each item's time, space and cost, from:

```bash
python3 "<moblee folder>/scripts/moblee-setup.py" --list
```

Use the figures it prints rather than figures from memory, since they change between versions. To see what is already working, run the read-only test (it changes nothing, and takes a minute or two):

```bash
python3 "<moblee folder>/scripts/moblee-setup.py" --check
```

## Getting started

Work through these one at a time, waiting for the owner after each. If they want to skip a step, skip it and say it can be done later.

**1. Hello.** Introduce yourself in a line, use the owner's name (it is in `CLAUDE.md`), and ask what they imagine putting in the wiki first: a book, a project, their work, a hobby. Their answer shapes the first page in step 6.

**2. Obsidian.** Check the vault is open in Obsidian (File, Open vault, Open folder as vault, then the vault folder). Suggest they skim `Welcome.md` and `wiki/How to Use This Wiki.md` now or later, without studying them.

**3. What to hold them to.** Ask one question: "Is there anything you want me to keep you honest about, or push you on, over time? A habit, a project, a thing you keep putting off?" Write the answer, in their words, into the list under "What [their name] has asked to be held to" in `wiki/Identity.md`. If they have nothing yet, leave it and say they can add to it any time.

**4. How they work.** This is the conversation the checklist depends on, so give it proper attention and ask, never assume. Ask these one or two at a time, in plain words, skipping any their earlier answers already covered:

- Where their mail, calendar, notes and reminders live: the Mac's own apps, Google, or somewhere else.
- What they read and watch in a normal week: YouTube, Instagram, TikTok, X, news sites, podcasts. Ask whether they want to keep and summarise things from those, or only watch.
- What they make: documents, PDFs, presentations, spreadsheets, videos, audio, photos.
- Whether they follow the news on particular subjects, travel often, or work with code on GitHub.
- Anything they do over and over that they would like to hand to a one-word command.
- How much room the Mac has. Offer to look (`df -h ~` shows the free space) and say which items are large.
- Whether they would like a weekly health check, a short evening lesson, or spoken replies.

**5. The suggestion, and the command.** From the answers, propose the items that fit, as a short list in chat: each item, one line on why ("you said you save YouTube videos to watch later"), and its time, space and cost from `--list`. Leave out anything they gave no reason for. Say plainly that anything paid is their own account and their own decision. Then:

- Record the conversation on `wiki/Wiki Operations/Habits and Tools.md` now, before anything is installed, because installing connections means restarting Claude and this conversation will not carry over: their answers in their words under "How the owner works"; each agreed item under "Installed, and why" as a line such as ``- `videos`, 19 September 2026: saves YouTube videos to watch later (agreed; not yet checked)``; each item they turned down under "Said no to" in the same form; and the date in the `last_reviewed:` frontmatter, written as 19 September 2026. Commit.
- Give them the one command, with the keys of the items they agreed to, and tell them to run it in a **new Terminal window** (in Terminal, press Command and N), leaving this conversation open in the first one. It is not typed to Claude. For example:

```bash
cd "<moblee folder>" && python3 scripts/moblee-setup.py --tick videos,documents,google
```

Tell them what they will see: the checklist with those items already ticked and everything else unticked, which they can still change by typing numbers, then a summary of time and space and a "Start now?" question. Sign-ins (Google, GitHub, the Chrome extensions, the Mac's permission pop-ups) are theirs to do; the checklist prints the steps and waits. A full set of downloads can take an hour or more, so suggest they leave it running and carry on here with step 6.

**6. The first page.** The moment the wiki becomes theirs. If they have something to capture (an article, a PDF, notes on a project), have them drop it into `raw/` and ingest it. If not, interview them on the subject from step 1 and write the first top-level page from their answers. Either way, finish with the log entry and the commit that `CLAUDE.md` describes.

**7. After the checklist.** When they come back, run `--check` and tell them in plain words what is working. On the Habits and Tools page, change "(agreed; not yet checked)" to "working" for each item that is, and to what went wrong for any that is not. If the checklist added connections, they need to quit Claude Code and open it again (and type `/chrome` if they added Chrome); if that happens before this step, the page already holds what was agreed, so the new session reads it and carries on here.

**8. What next.** A few lines only: drop things into `raw/` or clip them into `Clippings/` and ask for an ingest; say "orient" when coming back after a break; ask anything in plain words, since the skills start from ordinary phrasing. If they would like PDFs of their pages in their own colours and type, "design my brand" starts that. Sign off with "Welcome to your wiki. Come back any time." and stop proposing further work.

## Setup review

Held when the owner asks, or when the weekly health check reports a review is due (the page's `last_reviewed:` date is more than ninety days old) or reports links arriving that an uninstalled item would handle.

1. Read `wiki/Wiki Operations/Habits and Tools.md`, the last ninety days of `wiki/log.md`, and the latest report in `outputs/lint/` for its "Habits and tools" findings. Run `--check`.
2. Tell the owner, in two or three sentences, what their use looks like: what they have been doing by hand that an item would do for them, and anything installed that has not been used.
3. Ask, item by item, whether they want a change. Never suggest an item they said no to in the last ninety days unless they raise it. Nothing is removed by Moblee and an unused tool costs only its disk space; if they want the space back, say what the tool is and let them decide.
4. For anything they want added, give the `--tick` command as in step 5 above.
5. Update the page: new answers, new "Said no to" lines, a dated line under "Review history", and today's date in `last_reviewed:`. Commit.

## Rules that hold throughout

- **Ask, never assume.** A suggestion comes from something the owner said or something in the vault, and the reason is stated with it.
- **The owner installs.** Claude never runs the checklist without `--check` or `--list`, never runs `install.sh`, `update.sh` or any other installer in the Moblee folder, and never edits `~/.claude/settings.json`. If the owner asks Claude to do one of these, or pastes the command into this conversation, explain that it is theirs to run in a Terminal window of its own and give the exact command again.
- **A no is remembered.** If the owner does not want this conversation or a review when it is offered, write `` `get-started` `` and the date under "Said no to", and it is not offered again for ninety days.
- **One question at a time**, warm and unhurried. Calibrate to the owner: compress for someone fluent, slow down and explain for someone new.
- **No pressure to install.** "Nothing extra for now" is a good answer and is recorded like any other.
