# Moblee

A starter pack for building your own LLM-managed personal knowledge wiki, following Andrej Karpathy's wiki pattern (April 2026).

## What this is

Moblee is the scaffolding you need to start a Karpathy-style personal wiki on your own machine. The system is an Obsidian vault (your reading layer), a set of structured workflows for getting material into it (the ingest pipeline), and Claude as the maintainer (the writing layer). You read; Claude writes. You drop sources into an inbox, and Claude reads them, updates the relevant pages, logs the change and commits to git. Over time the vault builds into an interlinked record of what you know, what you are working on, and how your thinking has changed.

The Karpathy pattern rests on four files, each with one job. `CLAUDE.md` is the schema (the rules Claude follows). `wiki/Index.md` is the content catalogue (what pages exist). `wiki/_context.md` is the working state (active threads, open decisions). `wiki/log.md` is the chronology (an append-only audit trail). No file duplicates another. Moblee adds a fifth, `wiki/Identity.md`, which sets how Claude works with you. The system is deliberately simple: plain markdown, no proprietary formats, no lock-in. If you stopped using Claude tomorrow, you would still have a complete Obsidian vault.

The templates come with opinionated defaults (British English, paragraph-first prose, no em dashes, dated absolute references, structured ingest workflows), and you can keep, change or strip any of them. `CLAUDE.md` is the source of truth for your conventions; once it is installed in your vault, you own it.

**New in v0.8.1.** **An app to install with, and a companion to grow the wiki with.** The **Moblee app** (source in `app/`) is a small Mac app that installs the wiki without Terminal: one picture, one sentence and one button on each screen, and one typed question. It runs the pack's own `scripts/install.sh` underneath, so an app install and a Terminal install are the same install. On a Mac that already has a wiki it opens a home screen: a tile for each thing you and Claude agreed to add, an Update screen when it carries a newer Moblee than your wiki, and a Repair button if the delete guard is missing. The app is offered on the Releases page of the GitHub repository, signed and notarised by Apple; the Terminal install in `docs/02-install.md` always works. The **`companion` skill** replaces `get-started`. It holds the first conversation ("get me started" still works, and so does "guide me"), offers at most one next step in a session, keeps replies short unless you ask for more, writes down every correction you make, builds small tools made to measure, and runs a check-up when something seems wrong. **`scripts/moblee-doctor.py`** is that check-up: it changes nothing, marks each finding OK, LOOK or PROBLEM, and can write a report that holds nothing from your pages. Every install now keeps a plain diary at `~/.config/moblee/install-diary.txt`. See `docs/11-the-app-and-the-companion.md`. What v0.7.0 brought (you run the installer, and Claude asks how you work before suggesting anything) is in `CHANGELOG.md`, with every earlier version.

**New in v0.6.0.** Everything optional is now chosen from **one checklist** (`scripts/moblee-setup.py`), which the installer shows at the end of a new install and the updater offers. It connects the wiki to **your Mac's Calendar, Reminders, Mail and Notes** (through Orchard, with its delete tools blocked), **Gmail, Google Calendar and Google Drive**, **GitHub**, and **Chrome** with your own X, Instagram and YouTube logins and the Obsidian Web Clipper; it adds **video watching**, **PDF, Word, PowerPoint and Excel**, **film, audio and picture editing**, a **news brief** in which every item is confirmed by a second source, **trip planning**, **X capture**, a **skill maker** and **Obsidian extras**; and it holds the habits that used to be separate installer questions (weekly health check, learning path, voice, the `vault` shortcut). Each line says what the item does, the time, the space and the cost; nothing paid is ticked by default, and the one paid option (generating images, video and voices with ElevenLabs) is your own account and decision. `python3 scripts/moblee-setup.py --check` tests every connection at any time. The vault's `CLAUDE.md` gains a section on **connected accounts and live facts** (read on request; never send, post, delete or spend without a yes; current facts fetched live and cited), which the updater adds to existing vaults. The installer now installs the core skills itself. Moblee is now Mac only. See `docs/10-connections.md`.

**New in v0.4.** The pack now carries a proven operational layer, generalised for any vault: the **brain skill grown to eleven patterns** (reflective queries, `_context` tier management, persona ghost-voices, and a daily rhythm of morning brief / close-day / week planning over a new Daily Notes layer); a **structural health layer** (`scripts/lint-v2.py` weekly checks, a `compact` skill that keeps the always-loaded files light, and a git **commit gate** that catches format drift before a commit exists); a **local dashboard** (orientation state, an Ask box that runs Claude against your vault, and a Visuals tab whose charts you add by asking Claude); the **3D galaxy** view of your knowledge graph; and an optional **voice stack** (replies read aloud and audible nudges when Claude needs you, free with the built-in macOS voice and upgradable to ElevenLabs). All of it is optional, and the same one-command installer sets it up.

**New in v0.5.** The pack now installs **a safety layer that cannot be skipped**. A delete guard inspects every shell command Claude composes and refuses deletion, history rewriting and force pushes however they are phrased; a starter permission list stops the constant prompts for routine work (safe only because the guard sits beneath it); and the never-delete rule is written into `CLAUDE.md` and into a new always-loaded **`wiki/Identity.md`** that holds who Claude is to you (verify rather than guess, challenge rather than flatter). Also new: **`scripts/update.sh`**, which brings an existing vault up to the current version without touching its content (there was no update path before v0.5); the **galaxy skill**; the commit gate wired through `scripts/hooks/` so updates reach it; five more health checks, the link guard, and a **weekly health check on a schedule**; a log appender that reads the clock itself; four starting memories; and a `VERSION` file. The compaction skill now lists what it would move or drop and asks first. See `docs/08-updating.md` and `docs/09-safety.md`.

**New in v0.5.1.** An optional **learning path**: thirty-two short lessons on getting the most from the wiki, one an evening, given by Claude when you say "lesson", with a reminder at nine each evening. It needs Claude Code; the installer and the updater ask whether you want it. Also: clearer instructions for updates done through a clinic note, a rule that keeps clinic reports out of the wiki, a writing rule against the habits that make machine prose read as machine prose (with a weekly check for them), and a documentation pass throughout.

## What you'll need

Moblee runs on a Mac only (Apple Silicon recommended; tested on macOS 14 and later). The older Windows files are kept, unmaintained, in `archive/windows/`.

- [Obsidian](https://obsidian.md), free
- [Claude Code](https://claude.ai/code), which needs an Anthropic account
- Apple's free developer tools, which bring git (`xcode-select --install`)
- Python 3, which comes with the developer tools

`docs/01-prerequisites.md` covers each of these, then `docs/02-install.md` walks through the install.

## The checklist, and what the full package gives you

The installer lays down the vault, the safety layer and the core skills. Everything optional is then chosen from one checklist, and the easy way to choose is to open Claude in your new wiki and say "get me started" (or "guide me" at any later time). The `companion` skill asks how you use your Mac and what you read, watch and make, helps you make your first page, and then proposes one or two items that clearly fit. What you agree to waits as a tile in the Moblee app, where you press Add; if you installed from Terminal, Claude gives you one command that opens the checklist with those items ticked. Nothing is ticked otherwise. You confirm what you want; each line says what the item does, roughly how long it takes, how much space it uses and what it costs, and a summary before anything starts says when you will be needed at the keyboard. Sign-ins (Google, GitHub, the Chrome extensions, the Mac's own permission pop-ups) are yours to do, and the checklist prints plain step-by-step instructions for each and waits while you do them.

With everything free ticked, Claude can read your Mac's Calendar, Reminders, Mail and Notes, your Gmail, Google Calendar and Google Drive, your GitHub projects, and web pages behind your own logins in Chrome (including X, Instagram and YouTube); watch and summarise videos; turn pages into PDFs and make or read Word, PowerPoint and Excel files; edit film, audio and pictures on copies of your files; give you a news brief with every item checked against a second source; keep trip pages; save X posts into your inbox; and learn your own routines as one-word commands. Claude reads these accounts only when you ask, and never sends, posts, deletes or spends without your yes for that one action.

Ticking everything free takes about an hour and a half the first time, mostly waiting for downloads, and several gigabytes of space (Apple's developer tools, Homebrew and the video renderer are the large parts), which is why Claude suggests only what you will use. The only paid option, generating new images, video, voices and music, uses your own ElevenLabs account: as of September 2026 it has a free tier with small limits and paid plans from about $6 a month (check elevenlabs.io/pricing). Run the checklist again at any time to add something, or run `python3 scripts/moblee-setup.py --check` to test that everything still works. `docs/10-connections.md` explains every item.

## Getting started

Read [`START_HERE.md`](START_HERE.md): one page, three steps. You run the installer yourself, with the Moblee app from the Releases page or in Terminal (`bash scripts/install.sh`), open the new wiki in Obsidian, then open Claude in the wiki and say "get me started". The installer is yours to run because it changes Claude's own settings; a careful Claude will not make those changes on the strength of a downloaded file, so the pack never asks you to paste anything into Claude. A paid Claude plan is needed for the Code tab in Claude's app.

If you prefer to read more first, start at [`docs/00-overview.md`](docs/00-overview.md).

## What's in the box

```
moblee/
├── README.md                  ← this file
├── START_HERE.md              ← read this first: install, open, "get me started"
├── LICENSE                    ← MIT
├── VERSION                    ← the pack version (copied into every vault)
├── app/                       ← source of the Moblee app: installs, updates and adds what you agreed with Claude (v0.8.1)
├── vault-template/            ← the Obsidian vault scaffolding
│   ├── CLAUDE.md              ← the schema (rules Claude follows in your vault)
│   ├── Welcome.md             ← first page you'll see in Obsidian
│   ├── wiki/                  ← Index.md, log.md, _context.md, Identity.md, methodology pages
│   ├── raw/                   ← drop zone for PDFs, text, images
│   ├── Clippings/             ← Obsidian Web Clipper deposits land here
│   └── outputs/               ← generated reports (lint passes, PDFs, setup checks)
├── skills/                    ← the eight core skills, installed by the installer
│   ├── brain/                 ← reflective queries against the wiki, and the daily rhythm
│   ├── compact/               ← keeps the always-loaded files light (asks before dropping anything)
│   ├── companion/             ← your standing guide: the first conversation, one next step, made-to-measure tools, the check-up (v0.8.1)
│   ├── galaxy/                ← rebuilds and opens the 3D graph of the wiki
│   ├── wiki-capture/          ← funnels chat content into the vault
│   ├── wiki-interview/        ← builds a page from your own testimony
│   ├── wiki-to-pdf/           ← renders any wiki page as a branded PDF
│   └── design-your-brand/     ← interview that captures your visual identity
├── extras/
│   └── skills/                ← skills the checklist installs when ticked (v0.6.0)
│       ├── film/              ← video editing from a plain description
│       ├── audio/             ← audio editing and read-aloud
│       ├── pictures/          ← picture editing
│       ├── news-brief/        ← a news brief, every item confirmed by a second source
│       ├── trips/             ← a page per trip, with legs and day plans
│       └── x-capture/         ← saves X posts into raw/ through Chrome
├── safety/                    ← the delete guard and the starter permission rules (v0.5; not optional)
├── memory-seed/               ← four starting memories for your Claude (v0.5)
├── clinic/                    ← tools for whoever maintains Moblee for other people (v0.5)
├── learning-path/             ← optional: 32 evening lessons and their reminder (v0.5.1)
├── voice/                     ← optional voice stack (replies read aloud)
├── dashboard/                 ← optional local web dashboard
├── scripts/                   ← installers and the vault tooling
│   ├── install.sh             ← lays down the vault, tooling, safety layer and core skills, then the checklist
│   ├── moblee-setup.py        ← the checklist: connections and optional tools; --check tests them (v0.6.0)
│   ├── moblee-doctor.py       ← the read-only check-up of the wiki and the Mac; --report writes a report to pass on (v0.8.1)
│   ├── update.sh              ← brings an existing vault to this version, then offers the checklist (v0.5)
│   ├── install-skills.sh      ← copies the core skills to ~/.claude/skills/ (run by the installer)
│   ├── install-schedule.sh    ← puts the weekly health check on a schedule (v0.5)
│   ├── install-learning-path.py ← adds the optional learning path to a vault (v0.5.1)
│   ├── vault.sh               ← the `vault` session-start function (added to ~/.zshrc by the checklist)
│   ├── lint-v2.py, vault-gate.py, log-append.py, vault-orient-preflight.sh, patch-claude-md.py, seed-memory.py
│   ├── hooks/                 ← the git hooks a vault runs (commit gate), wired by core.hooksPath
│   ├── cadence/               ← the weekly lint runner and its launchd template
│   └── wiki-galaxy/           ← the galaxy builder and viewer
├── docs/                      ← longer-form documentation
│   ├── 00-overview.md         ← what this is and why it works
│   ├── 01-prerequisites.md    ← what to install before running Moblee
│   ├── 02-install.md          ← step-by-step install
│   ├── 03-first-conversation.md  ← how to work with Claude in this system
│   ├── 04-first-ingest.md     ← walk through ingesting your first source
│   ├── 05-skills.md           ← reference for the bundled Claude Code skills
│   ├── 06-karpathy-method.md  ← the methodology explained for a beginner
│   ├── 08-updating.md         ← how to update a vault without touching its content (v0.5)
│   ├── 09-safety.md           ← why Claude cannot delete your files (v0.5)
│   ├── 10-connections.md      ← the checklist item by item, and what Claude may do with each (v0.6.0)
│   └── 11-the-app-and-the-companion.md  ← the Moblee app and the companion skill, explained together (v0.8.1)
├── archive/
│   └── windows/               ← retired files, kept but not maintained
└── CHANGELOG.md               ← release notes, v0.1 to v0.8.1
```

## License

MIT, see [LICENSE](LICENSE).

## Credit

Built with Claude (via Cowork) as a starter pack for new wiki authors. Credit for the method: Andrej Karpathy, April 2026.
