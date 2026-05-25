# 00. Overview: what Moblee is and why it works

Moblee is a starter pack for building your own LLM-managed personal knowledge wiki, following the pattern Andrej Karpathy described in April 2026. It bundles an opinionated vault template, four ready-to-use Claude skills, a small set of install scripts, and the documentation you're reading now. The whole package is designed to be paste-and-run: you install it once, ask Claude to walk you through the first day, and from then on you have a personal wiki that grows by use.

**Mac or Windows.** As of v0.2 (25 May 2026), Moblee supports both platforms. The Mac path is the default and ships with full automation via Claude Code and the four bundled skills. The Windows path was added in v0.2 to support users without a Mac; it runs the same vault pattern through Claude.ai web chat with a manual workflow in place of the Mac-side skills. The trade-offs are documented in `docs/07-windows-workflow.md`. If you have any access to a Mac, the Mac path is materially smoother and remains the recommended route; the Windows path exists so that you can begin without a Mac and migrate cleanly if you ever get one.

## The core idea

Imagine you read a long article, finish it, and want to keep what mattered. The usual options are weak. You can highlight in the app you read in, but those highlights die there. You can paste quotes into a notes app, but they pile up unsorted. You can summarise into a journal, but the journal grows linearly and never connects to anything else you've read. None of these compound.

The Karpathy pattern proposes a different shape. You drop the raw source into a folder. You ask Claude to ingest it. Claude reads it, finds the existing wiki pages it touches (a single article typically touches five to fifteen pages), updates each of them in your voice, adds a dated entry to your log, moves the source into a `processed/` archive, and commits the change to git. Over weeks the wiki accumulates. Connections form. Things you read in March quietly inform pages you started in May. The thing you build is not a pile of notes; it is a structured, queryable record of how your understanding evolved.

## The six layers

The system has six layers, each with one role.

The **raw layer** holds source material as it arrives: PDFs, web clippings, photographs of book pages, plain text dumps. You drop things in; Claude reads them; nothing in this layer is ever rewritten. After ingest, the original file moves to a `processed/` subfolder so you can always trace any wiki claim back to its source.

The **wiki layer** holds the compiled, interlinked markdown pages. Claude owns this layer entirely. You read; Claude writes. Every page links to other pages with `[[Wikilink]]` syntax so Obsidian's graph view lights up over time.

The **schema layer** holds your conventions: the `CLAUDE.md` at vault root (which Claude reads at the start of every session) plus a small handful of methodology pages inside `wiki/`. This layer co-evolves: you change the rules, Claude follows the new rules from then on.

The **log layer** is `wiki/log.md`, an append-only chronological record of every substantive change. New entries go at the bottom; old entries never get rewritten. The log is the audit trail that lets you (or Claude) reconstruct what happened and when.

The **context layer** is `wiki/_context.md`, the working state of the wiki: what threads are active right now, what decisions are open, what's been added recently. It's refreshed at the end of every session that moves the state. It is not the log; the log is permanent history, context is the live snapshot.

The **index layer** is `wiki/Index.md`, a compact catalogue of every top-level page. One short line per page, organised by category. Index is for navigation, not chronology; chronology lives in the log.

The four canonical files (`CLAUDE.md`, `Index.md`, `_context.md`, `log.md`) each own one role and do not duplicate the others. Resist the temptation to fold any one into another. The discipline of keeping them separate is what makes the system queryable, durable, and easy to maintain.

## Why it works

The system works because of three design choices that hold up over time.

**Markdown all the way down.** The vault is plain markdown files in a folder. Obsidian is just the reader; the files themselves are not locked into any application. You could open them in TextEdit. You could grep them. You could walk away from Claude and have a complete, portable record of everything you've written. There is no proprietary database, no cloud dependency for reading, no migration risk.

**LLM as maintainer, human as reader.** The user does not edit the wiki by hand because hand-edits drift: tone wobbles, conventions get forgotten, cross-references go stale. Claude writes because Claude can be made to follow rules consistently. The user reads, asks questions, and approves changes; the cost of maintenance falls to near zero.

**Append-only logging plus git.** Every substantive change is logged in a dated entry that is never reordered or rewritten, and the whole vault is under git. This gives you two independent audit trails: the human-readable log and the git history. If something looks wrong, you can always trace what happened.

## How a typical week looks

In a typical week, you do four kinds of work, all of them by talking to Claude in plain English.

You **ingest**. You read an article, save it to `Clippings/` with the Obsidian Web Clipper, and ask Claude to "ingest the new clipping". Claude reads the article, updates the relevant wiki pages, appends a log entry, moves the source to `Clippings/processed/`, and commits.

You **query**. You ask Claude a question that spans your wiki: "How does what I learned about X connect to what I'm doing in Y?" Claude reads the relevant pages, synthesises the answer, and offers to save it back as a wiki page so the exploration compounds.

You **render**. You ask Claude to "PDF up the page on [topic]". The `wiki-to-pdf` skill turns the page into a branded PDF in your visual identity, ready to share.

You **lint**. Periodically, you ask Claude to "lint the wiki". Claude scans for contradictions, stale claims, orphan pages, missing backlinks, and gaps. The report goes into `outputs/` and the issues it surfaces become a small backlog of corrective edits.

That's the whole rhythm. The rest is just the act of reading the world and dropping things into `raw/`.

## What this starter pack gives you

The starter pack ships a working version of all of this. The `vault-template/` is a clean Karpathy-pattern vault with the schema in place, ready for your first content. The `skills/` folder contains four Claude skills that auto-trigger when you talk to Claude in natural language. The `scripts/` folder has installers that lay it all down on your Mac in one or two commands. The `docs/` folder (which you are inside now) has the longer explanations.

When you're ready, move on to [01-prerequisites.md](01-prerequisites.md) for the install checklist, or skip ahead to [02-install.md](02-install.md) if you already have the prerequisites and want to run the installer.

Or, simplest of all: paste [`../START_HERE.md`](../START_HERE.md) into Claude and let it walk you through everything in conversation.
