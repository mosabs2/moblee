# 10. Connections: the checklist, item by item

Moblee's wiki works on its own, but it is more useful when Claude can read what is already on your Mac and in your accounts: your calendar, your mail, your files, a video someone sent you. Everything of that kind is chosen from one checklist, `scripts/moblee-setup.py`. The easiest way to fill it in is to say "get me started" to Claude in your wiki, which suggests what fits and gives you the command. The installer and the updater also offer it, and you can run it at any time from the Moblee folder in Terminal:

```
python3 scripts/moblee-setup.py
```

Each line of the checklist says what the item does, roughly how long it takes, how much space it uses and what it costs. Items that are already working are marked `working` and left alone. You type the numbers of the items to tick or untick (for example `3 7 12`), `all` for everything, `free` for everything that costs nothing, or `none` to clear the list, and then press Return on its own when the list is right. Before anything is installed the checklist shows a summary: the order it will work in, its estimate of time and space for what you ticked, and every moment you will be needed at the keyboard. It then asks "Start now?". Nothing is ticked in advance. The easier way to choose is to open Claude in your wiki and say "get me started" (or "review my setup" later): Claude asks how you work and gives you a command, such as `python3 scripts/moblee-setup.py --tick videos,google`, that opens this checklist with only the fitting items ticked. You can still change anything before you press Return. `--list` prints every item with its key, time, space and cost.

**Time, space and cost, honestly.** Ticking everything free on a Mac that has never had developer tools takes about an hour and a half the first time, most of it waiting for downloads, and uses several gigabytes: Apple's developer tools, Homebrew (the standard free installer for Mac tools) and the video renderer are the large parts. The checklist prints its own estimate for what you actually ticked before it starts. Keep the Mac plugged in and awake. Only one item can cost money (creating new images, video and voices with ElevenLabs), and the checklist itself never buys anything.

**What you do, and what the checklist does.** The checklist installs the tools. Signing in is yours: Google, GitHub, the Chrome extensions, the Mac's own permission pop-ups and, if you choose it, ElevenLabs. When one of these comes up, the checklist stops, prints the steps in plain words, opens the right page, and waits for you to press Return. Typing `s` and Return at that point skips the step, and the item can be finished later.

**Three commands to remember.** All run from the Moblee folder.

```
python3 scripts/moblee-setup.py --check
```

tests every item, changes nothing, prints `WORKING` or `NOT WORKING` with a reason for each, and saves the result to `outputs/setup/` in your vault.

```
python3 scripts/moblee-setup.py --list
```

prints the short key for each item (for example `google`, `film`, `vault-fn`).

```
python3 scripts/moblee-setup.py --only google,github
```

installs just the items you name, skipping the list.

**What is never touched.** The checklist deletes nothing. Every settings file it changes is first copied to `~/.config/moblee/backups/`, and the full output of every long install is kept in a log file under `~/.config/moblee/`. When it has finished, quit Claude Code and open it again so it sees the new connections.

## What Claude does with a connection

The rules below are written into your vault's `CLAUDE.md`, in the section "Connected accounts and live facts", so your Claude follows them in every session. The updater adds the section to vaults installed before v0.6.0.

Claude reads a connected account only when your request needs it. It does not sweep your inbox or your feeds on its own initiative. It never sends an email; never creates, accepts, changes or deletes a calendar event or a reminder; never moves or bins a file through a connection; and never posts, likes, follows, comments, sends a message or buys anything on any site, unless you say yes to that one action in the same conversation. Drafts are the default: Claude writes the email or the post, and you send it. Anything that spends money or paid credits is asked about first, every time. Nothing read from an account goes into your wiki unless you ask for it to be recorded.

Two habits follow from these rules. If you hand Claude an export (a calendar file, a screenshot of an email) that a connection could read directly, Claude uses the connection and tells you once. And facts that change (news, prices, scores, schedules) are checked against a live source and cited with its date; a news claim is confirmed by a second independent source before it is presented as fact.

## Connect your life

### Your Mac's Calendar, Reminders, Mail and Notes (`mac-apps`)

**What it connects.** Orchard, a free open-source link, lets Claude read the Mac's own Calendar, Reminders, Mail and Notes, so you never need to export a calendar file again. It needs macOS 14 (Sonoma) or later, and it brings in Apple's developer tools, Homebrew and Node if they are not already there. About 8 minutes and 60 MB, plus those foundations. Free.

**What you will be asked to do.** Your Mac will ask whether this may read your Calendars and Reminders (and possibly Mail and Notes).

1. On each pop-up, click Allow.
2. When the window says "Press Enter after granting access", press Return.
3. At the end it prints a line starting `claude mcp add`. Ignore it; the checklist does that step for you.

If you click Don't Allow by mistake: open System Settings, then Privacy & Security, then Calendars, and switch on Terminal and AppleBridge.

**What Claude will and will never do.** Claude reads your calendar, reminders, mail and notes when you ask. Orchard's tools that move, bin or delete (files, reminders, reminder lists, slides and sheets) are blocked outright in Claude's settings by the checklist, so they cannot run even by mistake. The tools that write over an existing document (Pages, Numbers and Keynote edits, copying a file, saving a mail attachment) are set to ask you every single time. Creating a reminder or drafting a mail happens only with your yes.

### Gmail, Google Calendar and Google Drive (`google`)

**What it connects.** Your Google mail, calendar and files, through your Claude account. About 3 minutes; nothing is installed on the Mac. Free.

**What you will be asked to do.** Google connects in the browser.

1. A page opens: claude.ai, Settings, Connectors. If it asks you to log in, use the same Claude account as Claude Code.
2. Find Gmail and click Connect. Sign in with your Google account and allow what Google asks.
3. Do the same for Google Calendar, then Google Drive.
4. Come back to the checklist window.

**What Claude will and will never do.** Claude reads mail, events and files when you ask. It drafts; you send. It does not accept invitations, change events or delete anything without your yes for that one action.

### GitHub (`github`)

**What it connects.** GitHub's own command-line tool, signed in to your account, so Claude can read and work with your GitHub projects. About 4 minutes and 40 MB. Free, but it needs a free GitHub account; if you do not have one, make one first at github.com.

**What you will be asked to do.**

1. The window shows a code like `ABCD-1234`. Press Return.
2. Your browser opens. Paste the code and click Authorize.
3. Come back to the checklist window.

**What Claude will and will never do.** Claude reads your repositories and works on them when you ask. It does not publish anything on GitHub on its own initiative, and the delete guard refuses force pushes and history rewriting whoever asks.

### Chrome, with your X, Instagram and YouTube (`chrome`)

**What it connects.** Chrome is how Claude reads pages behind your own logins, including X, Instagram and YouTube. The checklist installs Chrome if you do not have it, and opens two extensions for you to add: Claude's own, and the Obsidian Web Clipper, which saves any web page into your wiki's `Clippings/` folder. About 5 minutes. Free.

**What you will be asked to do.**

1. A Chrome page opens on the Claude extension. Click Add to Chrome, then pin it (the puzzle-piece icon, then the pin).
2. Click the Claude icon and sign in with the same Claude account.
3. A second page opens on the Obsidian Web Clipper. Add it too.
4. In Chrome, log in to x.com, instagram.com and youtube.com if you are not already.
5. Come back to the checklist window.

One more step, later, inside Claude Code: type `/chrome` and switch it on. If the Web Clipper saves somewhere other than your vault, open its settings and point its save location at your vault's `Clippings/` folder.

**What Claude will and will never do.** Claude uses your existing logins to read pages you ask about. It never posts, likes, follows, comments or sends a message without your yes for that one action.

## Read and make things

These items install tools rather than connect accounts, so there is nothing to sign in to. Each is free unless noted.

**Watch and summarise videos (`videos`).** Send a YouTube, Instagram, TikTok or X link and Claude watches it for you: type `/watch` and the link. Installs the video downloader and converter through Homebrew, and the `watch` tool into Claude Code. About 4 minutes and 200 MB.

**PDF, Word, PowerPoint and Excel (`documents`).** Turns wiki pages into finished PDFs (the renderer behind the `wiki-to-pdf` skill) and lets Claude make or read Office documents. About 10 minutes and 300 MB.

**Video editing (`film`).** Cut clips together, add titles, captions and music, from a plain description; say "make a film" or "edit this video". Installs Node, the video renderer (Remotion) as a Claude Code plugin, and the `film` skill. About 12 minutes and 1.5 GB, plus the developer tools. Free for individuals under Remotion's licence; larger companies need one.

**Audio editing and read-aloud (`audio`).** Trim, join, clean up and convert audio, and turn any page into a spoken recording, with the `audio` skill. About 4 minutes and 150 MB.

**Picture editing (`pictures`).** Crop, resize, convert, compress and caption photos and images, with the `pictures` skill and ImageMagick. About 5 minutes and 120 MB.

**A daily news brief (`news-brief`).** Say "news brief" for news on what you follow, each item confirmed by a second source and linked. A skill only; about a minute.

**Trip planning (`trips`).** Say "start a trip to ..." for a page per trip with flights, stays and day plans, built from your booking emails. A skill only; about a minute. It reads a booking email only when you ask, through the Google or Mac apps connection, and never sends, replies to, moves or deletes anything in the account. It books and pays for nothing.

**Save X posts into the wiki (`x-capture`).** Paste an x.com link and say "capture this"; Claude keeps the post, properly sourced, in `raw/` for your next ingest. It needs the Chrome item to work.

**Teach Claude your own routines (`skill-maker`).** Describe something you do often ("make a skill for ...") and Claude turns it into a one-word command. About 2 minutes.

**Obsidian extras (`obsidian-extras`).** Claude can build Obsidian canvases, databases and diagrams in Obsidian's own formats. About 2 minutes.

**What Claude will and will never do.** The editing skills work on copies, never on your originals. The news brief states what a second source confirms and labels anything with only one source as that source's report. None of these tools posts or sends anything.

## Paid, or with a paid option

### Create new images, video, voices and music (`generation`)

**What it connects.** ElevenLabs, a separate company with its own account and prices, for generating things that do not exist yet: images, video, voices, music and sound effects. Not ticked unless you tick it.

**What it costs.** As of September 2026, ElevenLabs has a free tier with small monthly limits and paid plans from about 6 US dollars a month; check elevenlabs.io/pricing for current prices before you pay for anything. The decision and the account are yours. Moblee takes no money and sets no plan.

**What you will be asked to do.**

1. If you do not have an ElevenLabs account, make one at elevenlabs.io.
2. A page opens: claude.ai, Settings, Connectors.
3. Find ElevenLabs, click Connect, and sign in with your ElevenLabs account.
4. Come back to the checklist window.

**What Claude will and will never do.** Claude asks before anything that uses up your ElevenLabs credits, every time.

### Claude reads its replies aloud (`voice`)

**What it connects.** Spoken replies, and an audible nudge when Claude is waiting on you. The Mac's built-in voice is free; the voice installer then asks its own questions and offers an ElevenLabs voice as an optional paid upgrade. About 3 minutes. Not ticked unless you tick it. `voice/README.md` has the detail.

## Looking after the wiki

**Weekly health check (`weekly`).** The wiki checks itself every Saturday morning and tells you what needs attention, including when your habits have moved on and a different extra might suit you. Free, and worth having: Claude suggests it in the "get me started" conversation.

**The learning path (`lessons`).** Thirty-two short lessons, one an evening, with a reminder at 9 pm; say "lesson" in your vault. Free.

**The `vault` shortcut in Terminal (`vault-fn`).** Type `vault` in Terminal to open Claude in your wiki. Free. The checklist adds it to `~/.zshrc`, keeping a copy of the old file first.

## If something is not working

Run `python3 scripts/moblee-setup.py --check` first; it tells you which item is not working and why. The fix for most messages is to run that item again with `--only` and its key. Keep a note of the exact message if you ask for help. The messages you may see, and what they mean:

- **"Claude Code is not installed yet"**: install Claude Code first (`docs/01-prerequisites.md`), then run the checklist again. The connections to Google, ElevenLabs and the plugins all go through it.
- **"not connected yet: Gmail, ..."** or **"ElevenLabs is not connected"**: the sign-in on claude.ai did not finish, or has expired. Open claude.ai, Settings, Connectors, and connect or reconnect the named service; then quit and reopen Claude Code and check again.
- **"the Mac apps link is not installed"** or **"installed, but not connected to Claude"**: run `--only mac-apps` again. If macOS is older than 14 (Sonoma), update it first.
- **"installed, but its setup step has not been run"** or **"registered with Claude, but it does not start"**: run `--only mac-apps` again and follow the steps; if it says Swift is missing, the checklist installs Apple's developer tools first.
- **"Claude Code shows no claude.ai connections at all"**: Claude Code is signed in with an API key, or not signed in. Open Claude Code, type `/login`, and choose your Claude account.
- **"the ... skill is an older version"**: run that item again; the old copy is kept in `~/.config/moblee/backups/`.
- **"a skill of your own called ... is in the way"**: you already have a skill with that name. Rename your folder in `~/.claude/skills/` if you want Moblee's instead.
- **"connected, but its delete tools are not blocked"**: run `--only mac-apps` again; it adds the block rules. If it says `~/.claude/settings.json` could not be read, that file has a typing error in it; ask Claude to show you where, and fix it before running again.
- **"GitHub's tool is not installed"** or **"installed, but not signed in"**: run `--only github` and follow the sign-in steps.
- **"Google Chrome is not installed"** or **"Chrome is here, but the Claude extension is not"**: run `--only chrome` and add the extension when the page opens. "(the Web Clipper is not added)" is a note, not a fault; add it the same way if you want it.
- **"installed, but it needs the Chrome item to work"**: the `x-capture` skill is in place but Chrome is not ready; run `--only chrome`.
- **"missing ..."** (for example `yt-dlp`, `ffmpeg`, `node`, ImageMagick, or "the PDF renderer"): a Homebrew or Python install did not finish. Run the item again with `--only`; if it fails again, the last lines it printed and the log file under `~/.config/moblee/` say why.
- **"the watch tool is not installed in Claude Code"**, **"the video studio plugin is not installed"** or **"the Word, PowerPoint and Excel tools"**: a Claude Code plugin did not install. Check the internet connection, run the item again, then quit and reopen Claude Code.
- **"the ... skill is not installed"** or **"not installed"** / **"not added"** / **"not scheduled"**: the item was not ticked or did not finish. Run it with `--only` and its key.
- **"Skipped: it needs devtools, homebrew ..."**: one of the foundations did not install, so the items standing on it were skipped. Finish the developer tools or Homebrew (their steps are printed when they come up), then run the checklist again.
- **"the check itself failed (...)"**: the test could not run at all. Run `--check` again; if it repeats, keep the message for whoever looks after your Moblee.

Anything connected through claude.ai (Google, ElevenLabs) can be disconnected there, on the Connectors page, at any time.
