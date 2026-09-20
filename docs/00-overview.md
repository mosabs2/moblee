# 00. Overview: what Moblee is and why it works

Moblee is a starter pack for building your own LLM-managed personal knowledge wiki, following the pattern Andrej Karpathy described in April 2026. It bundles an opinionated vault template, eight core skills, a checklist that connects the wiki to your Mac and your accounts, a small set of install scripts, and the documentation you're reading now. You install it once, ask your assistant to walk you through the first day, and from then on the wiki grows as you use it.

**Mac only.** Moblee runs on a Mac, with Claude, with ChatGPT, or with both, and nothing else. You choose which when you install. The older files for another platform are kept, unmaintained, in `archive/windows/`.

**How long it takes, and what it costs.** The wiki itself installs in a few minutes. **With Claude:** everything beyond it (the connections to your Mac's apps, Google, GitHub and Chrome, and the tools for video, documents and editing) is chosen from one checklist that says the time, space and cost of each item before anything starts. Ticking everything free takes about an hour and a half the first time and several gigabytes, mostly downloads of Apple's developer tools, Homebrew and the video renderer. Nothing on it is ticked in advance: Claude asks how you work and suggests only what fits. The only paid option is generating new images, video and voices with your own ElevenLabs account. **With ChatGPT:** Moblee does not set this up for ChatGPT yet.

## The core idea

Imagine you read a long article, finish it, and want to keep what mattered. The usual options are weak. You can highlight in the app you read in, but those highlights die there. You can paste quotes into a notes app, but they pile up unsorted. You can summarise into a journal, but the journal grows linearly and never connects to anything else you've read. None of these compound.

The Karpathy pattern proposes a different shape. You drop the raw source into a folder. You ask your assistant to ingest it. It reads the source, finds the existing wiki pages it touches (a single article typically touches five to fifteen pages), updates each of them in your voice, adds a dated entry to your log, moves the source into a `processed/` archive, and commits the change to git. Over weeks the wiki accumulates and connections form: things you read in March quietly inform pages you started in May. What you end up with is a structured, queryable record of how your understanding developed.

## The six layers

The system has six layers, each with one role.

The **raw layer** holds source material as it arrives: PDFs, web clippings, photographs of book pages, plain text dumps. You drop things in; your assistant reads them; nothing in this layer is ever rewritten. After ingest, the original file moves to a `processed/` subfolder so you can always trace any wiki claim back to its source.

The **wiki layer** holds the compiled, interlinked markdown pages. Your assistant owns this layer entirely. You read; your assistant writes. Every page links to other pages with `[[Wikilink]]` syntax so Obsidian's graph view lights up over time.

The **schema layer** holds your conventions: the `CLAUDE.md` at vault root (which your assistant reads at the start of every session; ChatGPT reads the same rules from a file named `AGENTS.md`) plus a small handful of method pages inside `wiki/`. This layer co-evolves: you change the rules, your assistant follows the new rules from then on.

The **log layer** is `wiki/log.md`, an append-only chronological record of every substantive change. New entries go at the bottom; old entries never get rewritten. The log is the audit trail that lets you (or your assistant) reconstruct what happened and when.

The **context layer** is `wiki/_context.md`, the working state of the wiki: what threads are active right now, what decisions are open, what's been added recently. It's refreshed at the end of every session that moves the state. The log is permanent history; the context file is the live snapshot.

The **index layer** is `wiki/Index.md`, a compact catalogue of every top-level page. One short line per page, organised by category. Index is for navigation; chronology lives in the log.

The four canonical files (`CLAUDE.md`, `Index.md`, `_context.md`, `log.md`) each own one role and do not duplicate one another. Keeping them separate, and not folding one into another, is what keeps the system queryable and easy to maintain. A fifth file, `wiki/Identity.md`, sets how your assistant works with you: it checks before it claims, it challenges rather than flatters, and it never deletes without your yes.

## Why it works

Three design choices carry the system.

**Markdown all the way down.** The vault is plain markdown files in a folder. Obsidian is only the reader; the files belong to no application. You could open them in TextEdit or grep them. If you stopped using an assistant, you would still have a complete, portable record of everything you have written, with no proprietary database and no cloud dependency for reading.

**LLM as maintainer, human as reader.** You do not edit the wiki by hand, because hand-edits drift: tone wobbles, conventions get forgotten, cross-references go stale. Your assistant writes because it can be made to follow rules consistently. You read, ask questions and approve changes, and the cost of maintenance falls to near zero.

**Append-only logging plus git.** Every substantive change is logged in a dated entry that is never reordered or rewritten, and the whole vault is under git. That gives you two independent audit trails, the human-readable log and the git history, so if something looks wrong you can always trace what happened.

## How a typical week looks

In a typical week, you do four kinds of work, all of them by talking to your assistant in plain English.

You **ingest**. You read an article, save it to `Clippings/` with the Obsidian Web Clipper, and ask your assistant to "ingest the new clipping". It reads the article, updates the relevant wiki pages, appends a log entry, moves the source to `Clippings/processed/`, and commits.

You **query**. You ask your assistant a question that spans your wiki: "How does what I learned about X connect to what I'm doing in Y?" It reads the relevant pages, synthesises the answer, and offers to save it back as a wiki page so the exploration compounds.

You **render**. You ask your assistant to "PDF up the page on [topic]". The `wiki-to-pdf` skill turns the page into a branded PDF in your visual identity, ready to share.

You **lint**. Periodically, you ask your assistant to "lint the wiki". It scans for contradictions, stale claims, orphan pages, missing backlinks, and gaps. The report goes into `outputs/` and the issues it surfaces become a small backlog of corrective edits.

Beyond that, you read and drop things into `raw/`.

## What this starter pack gives you

The `vault-template/` is a clean Karpathy-pattern vault with the schema in place, ready for your first content. The `skills/` folder contains eight core skills that auto-trigger when you talk to your assistant in natural language; the installer puts them in place. The `scripts/` folder has the installer, the updater and the checklist (`scripts/moblee-setup.py`). **With Claude:** Claude helps you fill the checklist in when you say "get me started" in your new wiki. The checklist connects Claude to your Mac's Calendar, Reminders, Mail and Notes, to Gmail, Google Calendar and Google Drive, to GitHub, and to Chrome with your own logins, and adds tools for watching videos, making PDF and Office documents, and editing film, audio and pictures, plus a news brief, trip pages and more (the extra skills live in `extras/skills/`). Claude reads a connected account only when you ask, and never sends, posts, deletes or spends without your yes. `docs/10-connections.md` covers every item. **With ChatGPT:** Moblee does not set this up for ChatGPT yet. The `docs/` folder (which you are inside now) has the longer explanations.

When you're ready, move on to [01-prerequisites.md](01-prerequisites.md) for the install checklist, or skip ahead to [02-install.md](02-install.md) if you already have the prerequisites and want to run the installer.

Or, simplest of all: follow [`../START_HERE.md`](../START_HERE.md). You run the installer yourself, then open your assistant in your new wiki and say "get me started"; it asks how you work and, with Claude, suggests only the extras that fit.
