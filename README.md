# Moblee

A starter pack for building your own LLM-managed personal knowledge wiki, following Andrej Karpathy's wiki pattern (April 2026).

## What this is

Moblee is the scaffolding you need to start a Karpathy-style personal wiki on your own machine. The system is an Obsidian vault (your reading layer), a set of structured workflows for getting material into it (the ingest pipeline), and Claude as the maintainer (the writing layer). You read; Claude writes. You drop sources into an inbox; Claude reads them, updates the relevant pages, logs the change, and commits to git. Over time the vault compounds into a living, interlinked record of what you know, what you're working on, and how your thinking has evolved.

The Karpathy pattern is built on a four-file separation of concerns. `CLAUDE.md` is the schema (the rules Claude follows). `wiki/Index.md` is the content catalogue (what pages exist). `wiki/_context.md` is the working state (active threads, open decisions). `wiki/log.md` is the chronology (an append-only audit trail). Each file owns one role and does not duplicate the others. The system is deliberately simple: plain markdown, no proprietary formats, no lock-in. You could walk away from Claude tomorrow and you would still have a complete Obsidian vault.

This starter pack is opinionated but not prescriptive. The templates are seeded with sensible defaults (British English, paragraph-first prose, no em dashes, dated absolute references, structured ingest workflows) which you can keep, change, or strip as you see fit. The `CLAUDE.md` is the source of truth for your conventions; once it's installed in your vault, you own it.

## What you'll need

A list of prerequisites, quick reference. The detailed install is in `docs/01-prerequisites.md`.

- A Mac (Apple Silicon recommended; tested on M-series macOS 14 and later)
- [Obsidian](https://obsidian.md), free
- [Claude Code](https://claude.ai/code), needs an Anthropic account
- Git (comes with macOS Command Line Tools, `xcode-select --install`)
- Python 3 (for the optional PDF rendering skill)

## Getting started, the one-paste route

The fastest path: paste the contents of [`START_HERE.md`](START_HERE.md) into Claude (Claude.ai web chat, Claude Code in a Terminal, or Cowork on the desktop) and let Claude walk you through everything. You do not need to read these files first. Claude reads the prompt, knows the system, and sequences your setup from there.

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
├── skills/                    ← four Claude skills that pair with the vault
│   ├── brain/                 ← reflective queries against the wiki
│   ├── wiki-capture/          ← funnels chat content into the vault
│   ├── wiki-to-pdf/           ← renders any wiki page as a branded PDF
│   └── design-your-brand/     ← interview that captures your visual identity
├── scripts/                   ← install scripts
│   ├── install.sh             ← lays down the vault on your Mac
│   ├── install-skills.sh      ← copies the skills to ~/.claude/skills/
│   └── vault.sh               ← the session-start function (paste into ~/.zshrc)
└── docs/                      ← longer-form documentation
    ├── 00-overview.md         ← what this is and why it works
    ├── 01-prerequisites.md    ← what to install before running Moblee
    ├── 02-install.md          ← step-by-step install of the starter pack
    ├── 03-first-conversation.md  ← how to work with Claude in this system
    ├── 04-first-ingest.md     ← walk through ingesting your first source
    ├── 05-skills.md           ← reference for the bundled skills
    └── 06-karpathy-method.md  ← the methodology explained for a beginner
```

## License

MIT, see [LICENSE](LICENSE).

## Credit

Built collaboratively by [Your Name] and Claude (via Cowork) as a starter pack for new wiki authors. Methodology credit: Andrej Karpathy, April 2026.
