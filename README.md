# Moblee

A starter pack for building your own LLM-managed personal knowledge wiki, following Andrej Karpathy's wiki pattern (April 2026).

## What this is

Moblee is the scaffolding you need to start a Karpathy-style personal wiki on your own machine. The system is an Obsidian vault (your reading layer), a set of structured workflows for getting material into it (the ingest pipeline), and Claude as the maintainer (the writing layer). You read; Claude writes. You drop sources into an inbox, and Claude reads them, updates the relevant pages, logs the change and commits to git. Over time the vault builds into an interlinked record of what you know, what you are working on, and how your thinking has changed.

The Karpathy pattern rests on four files, each with one job. `CLAUDE.md` is the schema (the rules Claude follows). `wiki/Index.md` is the content catalogue (what pages exist). `wiki/_context.md` is the working state (active threads, open decisions). `wiki/log.md` is the chronology (an append-only audit trail). No file duplicates another. Moblee adds a fifth, `wiki/Identity.md`, which sets how Claude works with you. The system is deliberately simple: plain markdown, no proprietary formats, no lock-in. If you stopped using Claude tomorrow, you would still have a complete Obsidian vault.

The templates come with opinionated defaults (British English, paragraph-first prose, no em dashes, dated absolute references, structured ingest workflows), and you can keep, change or strip any of them. `CLAUDE.md` is the source of truth for your conventions; once it is installed in your vault, you own it.

**New in v0.4.** The pack now carries a proven operational layer, generalised for any vault: the **brain skill grown to eleven patterns** (reflective queries, `_context` tier management, persona ghost-voices, and a daily rhythm of morning brief / close-day / week planning over a new Daily Notes layer); a **structural health layer** (`scripts/lint-v2.py` weekly checks, a `compact` skill that keeps the always-loaded files light, and a git **commit gate** that catches format drift before a commit exists); a **local dashboard** (orientation state, an Ask box that runs Claude against your vault, and a Visuals tab whose charts you add by asking Claude); the **3D galaxy** view of your knowledge graph; and an optional **voice stack** (replies read aloud and audible nudges when Claude needs you, free with the built-in macOS voice and upgradable to ElevenLabs). All of it is optional, and the same one-command installer sets it up.

**New in v0.5.** The pack now installs **a safety layer that cannot be skipped**. A delete guard inspects every shell command Claude composes and refuses deletion, history rewriting and force pushes however they are phrased; a starter permission list stops the constant prompts for routine work (safe only because the guard sits beneath it); and the never-delete rule is written into `CLAUDE.md` and into a new always-loaded **`wiki/Identity.md`** that holds who Claude is to you (verify rather than guess, challenge rather than flatter). Also new: **`scripts/update.sh`**, which brings an existing vault up to the current version without touching its content (there was no update path before v0.5); the **galaxy skill**; the commit gate wired through `scripts/hooks/` so updates reach it; five more health checks, the link guard, and a **weekly health check on a schedule**; a log appender that reads the clock itself; four starting memories; and a `VERSION` file. The compaction skill now lists what it would move or drop and asks first. See `docs/08-updating.md` and `docs/09-safety.md`.

**New in v0.5.1.** An optional **learning path**: thirty-two short lessons on getting the most from the wiki, one an evening, given by Claude when you say "lesson", with a reminder at nine each evening. It needs a Mac with Claude Code; the installer and the updater ask whether you want it, and the Windows track does not include it. Also: clearer instructions for updates done through a clinic note, a rule that keeps clinic reports out of the wiki, a writing rule against the habits that make machine prose read as machine prose (with a weekly check for them), and a documentation pass throughout.

## What you'll need

Moblee supports two paths: a Mac path (full automation through Claude Code and the bundled skills) and a Windows path (manual workflow through Claude.ai web chat, added in v0.2). Pick the one that fits your hardware.

**Mac path (default; full automation):**

- A Mac (Apple Silicon recommended; tested on M-series macOS 14 and later)
- [Obsidian](https://obsidian.md), free
- [Claude Code](https://claude.ai/code), needs an Anthropic account
- Git (comes with macOS Command Line Tools, `xcode-select --install`)
- Python 3 (for the optional PDF rendering skill)
- Detailed install: `docs/01-prerequisites.md` then `docs/02-install.md`.

**Windows path (manual workflow; v0.2):**

- Windows 10 22H2 or Windows 11
- [Obsidian](https://obsidian.md) for Windows, free
- [claude.ai](https://claude.ai) web chat (Cowork desktop is Mac-only)
- [Git for Windows](https://git-scm.com/download/win)
- PowerShell 7 recommended ([github.com/PowerShell/PowerShell](https://github.com/PowerShell/PowerShell))
- Detailed install: `docs/01-prerequisites-windows.md` then `docs/02-install-windows.md`.
- The Windows path runs the same vault pattern with reduced automation; see `docs/07-windows-workflow.md` for the day-to-day flow and the manual workarounds for the bundled skills.

## Getting started, the one-paste route

The fastest path is to paste the contents of [`START_HERE.md`](START_HERE.md) into Claude (Claude.ai web chat, Claude Code in a Terminal, or Cowork on the desktop) and let Claude walk you through everything. You do not need to read these files first; the prompt tells Claude how the system works and what order to set it up in.

If you prefer to read first, start at [`docs/00-overview.md`](docs/00-overview.md).

## What's in the box

```
moblee/
├── README.md                  ← this file
├── START_HERE.md              ← paste into Claude to begin the guided setup
├── LICENSE                    ← MIT
├── vault-template/            ← the Obsidian vault scaffolding
│   ├── CLAUDE.md              ← the schema (rules Claude follows in your vault)
│   ├── Welcome.md             ← first page you'll see in Obsidian
│   ├── wiki/                  ← Index.md, log.md, _context.md, methodology pages
│   ├── raw/                   ← drop zone for PDFs, text, images
│   ├── Clippings/             ← Obsidian Web Clipper deposits land here
│   └── outputs/               ← generated reports (lint passes, PDFs)
├── VERSION                    ← the pack version (copied into every vault)
├── skills/                    ← seven Claude skills that pair with the vault
│   ├── brain/                 ← reflective queries against the wiki, and the daily rhythm
│   ├── compact/               ← keeps the always-loaded files light (asks before dropping anything)
│   ├── galaxy/                ← rebuilds and opens the 3D graph of the wiki
│   ├── wiki-capture/          ← funnels chat content into the vault
│   ├── wiki-interview/        ← builds a page from your own testimony
│   ├── wiki-to-pdf/           ← renders any wiki page as a branded PDF
│   └── design-your-brand/     ← interview that captures your visual identity
├── safety/                    ← the delete guard and the starter permission rules (v0.5; not optional)
├── memory-seed/               ← four starting memories for your Claude (v0.5)
├── clinic/                    ← tools for whoever maintains Moblee for other people (v0.5)
├── learning-path/             ← optional: 32 evening lessons and their reminder (v0.5.1)
├── voice/                     ← optional macOS voice stack
├── dashboard/                 ← optional local web dashboard
├── scripts/                   ← installers and the vault tooling
│   ├── install.sh             ← Mac: lays down the vault, tooling, safety layer
│   ├── update.sh              ← Mac: brings an existing vault to this version (v0.5)
│   ├── install.ps1            ← Windows: PowerShell installer (v0.2)
│   ├── install-skills.sh      ← Mac: copies the skills to ~/.claude/skills/
│   ├── install-schedule.sh    ← Mac: puts the weekly health check on a schedule (v0.5)
│   ├── install-learning-path.py ← adds the optional learning path to a vault (v0.5.1)
│   ├── vault.sh               ← Mac: session-start function (paste into ~/.zshrc)
│   ├── vault.ps1              ← Windows: session-start function (added to PowerShell profile, v0.2)
│   ├── lint-v2.py, vault-gate.py, log-append.py, vault-orient-preflight.sh, patch-claude-md.py, seed-memory.py
│   ├── hooks/                 ← the git hooks a vault runs (commit gate), wired by core.hooksPath
│   ├── cadence/               ← the weekly lint runner and its launchd template
│   └── wiki-galaxy/           ← the galaxy builder and viewer
├── docs/                      ← longer-form documentation
│   ├── 00-overview.md         ← what this is and why it works
│   ├── 01-prerequisites.md    ← Mac: what to install before running Moblee
│   ├── 01-prerequisites-windows.md ← Windows prerequisites (v0.2)
│   ├── 02-install.md          ← Mac: step-by-step install
│   ├── 02-install-windows.md  ← Windows install walkthrough (v0.2)
│   ├── 03-first-conversation.md  ← how to work with Claude in this system
│   ├── 04-first-ingest.md     ← walk through ingesting your first source
│   ├── 05-skills.md           ← reference for the bundled Claude Code skills
│   ├── 06-karpathy-method.md  ← the methodology explained for a beginner
│   ├── 07-windows-workflow.md ← Windows-track day-to-day workflow (v0.2)
│   ├── 08-updating.md         ← how to update a vault without touching its content (v0.5)
│   └── 09-safety.md           ← why Claude cannot delete your files (v0.5)
└── CHANGELOG.md               ← release notes, v0.1 to v0.5.1
```

## License

MIT, see [LICENSE](LICENSE).

## Credit

Built with Claude (via Cowork) as a starter pack for new wiki authors. Credit for the method: Andrej Karpathy, April 2026.
