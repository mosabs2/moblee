# Welcome

Welcome to your wiki. This is your personal knowledge base, built on the [[Karpathy LLM Wiki Pattern]]: a structured, interlinked collection of markdown notes that you curate and Claude maintains.

You're looking at it now in Obsidian. Most of what you'll do here is read pages and ask Claude to add to them. The folder structure, formatting, and bookkeeping are all Claude's job.

## The four files to know about

Your vault has four canonical files that, between them, govern everything. They live at different layers and serve different roles; don't fold any one into another.

`CLAUDE.md` (vault root). The schema. Rules and conventions Claude follows when working in your vault. Edit this as your conventions evolve.

`wiki/Index.md`. The content catalogue. One short line per top-level page, organised by category. It's for navigation, not chronology.

`wiki/_context.md`. The working state. Active threads, open decisions, recent significant additions. Refreshed at the end of any session that moves the state.

`wiki/log.md`. The chronology. Append-only dated entries for every substantive change. This is the audit trail.

## What to read next

Open [[How to Use This Wiki]] for the practical day-to-day guide: how to add content, how the three operations (Ingest, Query, Lint) work, how to connect notes with wikilinks, and what to ask Claude. It assumes no technical knowledge.

If you want the methodology behind all of this, read [[Karpathy LLM Wiki Pattern]].

## How you'll work with Claude

You'll talk to Claude either through **Cowork** (the desktop app, easiest for everyday capture and questions) or through **Claude Code** in a Terminal (more powerful, used for heavier sessions and git operations). Either way, the experience is the same conversation: you ask, Claude reads the wiki, makes edits, logs the change, and commits.

## When you're ready to start

Paste the contents of `START_HERE.md` (in the Moblee repo root) into Claude. It walks Claude through your specific setup: your name, your vault location, the conventions you want enforced. Claude will use it to personalise this `CLAUDE.md` and bring the wiki online.
