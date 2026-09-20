# Welcome

Welcome to your wiki. This is your personal knowledge base, built on the [[Karpathy LLM Wiki Pattern]]: a structured, interlinked collection of markdown notes that you curate and your assistant maintains. It works with Claude, with ChatGPT, or with both.

You're looking at it now in Obsidian. Most of what you'll do here is read pages and ask your assistant to add to them. The folder structure, formatting, and bookkeeping are all your assistant's job.

## The four files to know about

Your vault has four canonical files that, between them, govern everything, and a fifth, `wiki/Identity.md`, that sets how your assistant works with you. They live at different layers and serve different roles; don't fold any one into another.

`CLAUDE.md` (vault root; `AGENTS.md` with ChatGPT, and with both, `AGENTS.md` is a link to `CLAUDE.md`). The schema. Rules and conventions your assistant follows when working in your vault. Edit this as your conventions evolve.

`wiki/Index.md`. The content catalogue. One short line per top-level page, organised by category. It's for navigation, not chronology.

`wiki/_context.md`. The working state. Active threads, open decisions, recent significant additions. Refreshed at the end of any session that moves the state.

`wiki/log.md`. The chronology. Append-only dated entries for every substantive change. This is the audit trail.

## What to read next

Open [[How to Use This Wiki]] for the practical day-to-day guide: how to add content, how the three operations (Ingest, Query, Lint) work, how to connect notes with wikilinks, and what to ask your assistant. It assumes no technical knowledge.

If you want the methodology behind all of this, read [[Karpathy LLM Wiki Pattern]].

## How you'll work with Claude or ChatGPT

**With Claude:** you'll talk to Claude either through **Cowork** (the desktop app, easiest for everyday capture and questions) or through **Claude Code** in a Terminal (more powerful, used for heavier sessions and git operations).

<!-- verify on testdev -->
**With ChatGPT:** open the ChatGPT app, choose Work at the top, and open your wiki folder as a project.

Either way, the experience is the same conversation: you ask, your assistant reads the wiki, makes edits, logs the change, and commits. ChatGPT asks you to approve each commit. That is expected.

## When you're ready to start

**With Claude:** open Claude Code in this folder (in Terminal, `cd` into the vault and type `claude`). **With ChatGPT:** open your wiki folder as a project, as above. <!-- verify on testdev --> Then say **get me started**. Your assistant asks how you use your Mac and what you read, watch and make, suggests the extras that fit with a reason for each, and gives you one command to run that installs them. The extras are set up for Claude; Moblee does not set them up for ChatGPT yet. Then it helps you make your first page. Your answers are kept on [[Habits and Tools]], and your assistant checks back from time to time as your habits change, always asking before anything is added.
