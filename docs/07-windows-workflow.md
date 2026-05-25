# Windows workflow

This document covers the day-to-day workflow on the Windows track in Moblee v0.2. The Mac path is documented across `docs/03-first-conversation.md`, `docs/04-first-ingest.md`, and `docs/05-skills.md`; this document covers the Windows-specific variations and the manual workarounds you use in place of the Mac path's automation.

## What is the same on Windows

The wiki itself. Your vault is plain markdown in a folder. Obsidian reads it the same way on both platforms. The conventions in your `CLAUDE.md` (British English, paragraph-first prose, no em dashes, dated absolute references, the three-layer architecture, the four-file separation of concerns, the ingest / query / lint operations, the append-only log, the verification rule) all hold. The cluster-note pattern, the source-attribution discipline, the wikilink format — all identical.

Claude itself is the same model behind both interfaces. The model writes the same quality output in claude.ai web chat as it does in Cowork or Claude Code; the difference is in the input-output plumbing around the model, not in the model.

## What is different on Windows

A list, in rough order of how often each one matters.

**Claude is web chat, not desktop or terminal.** You use [claude.ai](https://claude.ai) in your browser. There is no Cowork application on Windows in v0.2, and Claude Code on Windows is documented as advanced (not part of the default install). The functional consequence: you copy sources into chat by hand, and copy Claude's responses out of chat into your vault files by hand. The Mac path automates both ends through skills; the Windows track does them manually.

**Skills do not auto-load on the Windows track.** The four skills bundled in Moblee (`brain`, `wiki-capture`, `wiki-to-pdf`, `design-your-brand`) are Claude Code skills that load automatically in Claude Code sessions. On the Windows track they are not installed and not invoked. What they do is documented below, with manual workarounds for each.

**Git commits happen manually via the `vault` function.** The `vault` PowerShell function (added to your profile by the installer) auto-commits any pending changes at the start of every session. At the end of a substantive session, you `git add . && git commit -m "summary"` in PowerShell by hand. This is two extra commands per session; cheap once you remember to do it.

**The PDF-rendering skill is Mac-only in v0.2.** `wiki-to-pdf` uses WeasyPrint, which on Windows needs GTK runtime libraries that are fiddlier than the Homebrew install on Mac. The Windows track does not include this; if you need a PDF of a wiki page, the easiest path is to render it from Obsidian directly via Obsidian's built-in `Export to PDF` command, which is not branded but is functional.

## A typical Windows session, end to end

This is what one substantive session looks like on the Windows track. Compare with `docs/04-first-ingest.md` for the Mac flow, which covers similar ground for the Mac side.

### 1. Start of session: run the `vault` function

Open PowerShell. Type `vault`. Press Enter.

The function changes directory into your vault, auto-commits any pending changes from the previous session, shows the last five commits, and confirms the vault is ready. You are now in the vault folder with a clean working tree.

### 2. Open Obsidian alongside

Obsidian should already be pointed at your vault from the install. If it is not running, open it now. Obsidian and PowerShell will sit side by side for the rest of the session: PowerShell handles git, Obsidian handles reading.

### 3. Open Claude.ai in a browser tab

Start a new conversation. Paste any standing context you want Claude to be aware of at the top of the conversation. A short version of your `CLAUDE.md` schema is useful here; you do not need to paste the whole thing, just the rules that matter for the conversation you are about to have.

### 4. Drop a source into your vault's `raw/` folder

Save the article, PDF, screenshot, or text file you want to ingest into `wiki/raw/` (inside your vault). On Windows you can drag files into the folder via File Explorer, save downloads directly to that folder, or paste text into a new `.md` file there.

### 5. Tell Claude what you have

In the claude.ai conversation, say something like:

> I have a new source at `raw/2026-05-25-iran-war-piece.md` I want to ingest into the wiki. Here is the content: [paste the source contents].

Claude reads the source and asks where to put it. You tell it which existing pages are relevant (or ask Claude to search; on the Windows track, "search" is Claude looking at the file structure you describe rather than autonomously scanning the vault).

### 6. Manually copy Claude's writes into your vault

Claude responds with the updated wiki pages as text in the chat. For each page Claude wants to update, open the page in Obsidian (or a text editor), paste the new content in, save. This is the step the Mac path automates through Claude Code; on Windows you do it by hand.

A useful pattern: ask Claude to give you the wiki updates one page at a time, with the page filename as a header and the content beneath. That makes the copy step click-and-paste mechanical rather than mental.

### 7. Append a log entry

Open `wiki/log.md`. Add a new entry at the bottom with a timestamped header and a brief summary of what changed. Claude can draft the log entry for you in the same chat; copy it across.

### 8. Move the source file from `raw/` to `raw/processed/`

In File Explorer, drag the source file from `wiki/raw/` to `wiki/raw/processed/`. This is the cleanup that signals "this source has been ingested".

### 9. End of session: commit

In PowerShell:

```powershell
git add .
git commit -m "ingest: <summary of what changed>"
```

The commit message follows the same taxonomy as the Mac path (`ingest:`, `housekeeping:`, `tooling:`, `schema:`, `lint:`, `correction:`). Done.

## Manual workarounds for the missing skills

What each skill does on the Mac path, and what to do instead on Windows.

### `brain` — reflective queries

Mac-side, the `brain` skill exposes eleven reflective patterns: `trace`, `connect`, `emerge`, `challenge`, `ideas`, `synthesise`, `today`, `close-day`, `schedule`, `graduate`, `ghost`. On Windows, you invoke any of these by asking Claude in chat directly. For a `connect` pass between two of your pages, say:

> Run a connect-style pass between [[Page A]] and [[Page B]]. Read both pages and surface the non-obvious bridges between them. Five bridges, ranked by structural significance. Report in 600-800 words.

Claude responds in chat. To save the response back to your vault, copy it into a new file at `wiki/<filename>.md` with appropriate frontmatter. The Mac path's `wiki-capture` step is what you do by hand here.

### `wiki-capture` — chat-to-wiki funnel

Mac-side, `wiki-capture` writes a chat exchange directly into the vault as a `raw/` capture file ready for ingest. On Windows, do it by hand: at the end of a substantive chat exchange, copy the relevant turns into a new file at `wiki/raw/YYYY-MM-DD-<short-title>.md`. Give the file a brief frontmatter (date, type, target pages) and ingest it via the normal flow.

### `wiki-to-pdf` — branded PDF rendering

Mac-side, `wiki-to-pdf` renders any wiki page as a brand-styled A4 PDF with a cover, monogram, and the wiki's house style baked in. The Windows track does not include this in v0.2 because the WeasyPrint dependencies on Windows are fiddlier than the Homebrew install on Mac.

If you need a PDF of a wiki page on Windows, the simplest path is Obsidian's built-in **File → Export to PDF**, which produces a clean unbranded PDF of the page you are viewing. It is not the brand-styled output the Mac path produces, but it is functional. If you later want the branded version, you can render it from a Mac (your own or borrowed) against the same vault.

### `design-your-brand` — visual identity interview

Mac-side, `design-your-brand` walks you through a structured interview that captures your visual identity: colour palette, monogram, typography, asset library. The output drives `wiki-to-pdf`'s branded covers. On the Windows track, you do not need this until you also need `wiki-to-pdf`, which is Mac-only in v0.2. Defer.

## When to consider upgrading to Claude Code on Windows

Claude Code does run on Windows. It is documented as advanced rather than default in Moblee v0.2 because the Mac install path is materially smoother and the skills are written against macOS conventions. Once you have used the Karpathy pattern for a few weeks and want the automation back, Claude Code on Windows is a reasonable next step. The skills under `skills/` in your Moblee package will mostly work; the small Mac-specific bits (`brew` calls, paths assuming `~/.zshrc`) can be patched as you go.

If you are reading this and considering the switch, ask your installed Claude (in web chat) something like:

> I am on Windows and want to move my Moblee setup from the manual workflow to Claude Code on Windows. Walk me through the migration.

Claude reads this document, your `CLAUDE.md` schema, and your existing vault, and produces a migration plan. The pattern is the same: the AI reads what you have and adapts; the docs are scaffolding for the AI to work from.

## Notes on cross-platform vault portability

If you ever get a Mac, your Windows-built vault is fully portable. The vault is just markdown files plus a `.git` folder; both are platform-agnostic.

To migrate: copy the entire vault folder onto the Mac (USB drive, OneDrive, Obsidian Sync, etc.), point Obsidian-on-Mac at the folder, run Moblee's Mac install for the skills (`bash scripts/install-skills.sh`), and you have the full Mac experience with all your existing content. The `CLAUDE.md` you wrote on Windows holds; no rewrites needed.

In the other direction (Mac to Windows), the same: the vault transfers cleanly, but you lose the Mac-only skills until you re-install them on a Mac.
