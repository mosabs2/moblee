# 03. Your first conversation with Claude in this system

By this point you have a working Moblee vault and the skills installed. This document explains how the conversational workflow looks in practice, so you know what to expect when you open your assistant for the first time inside your new vault.

## Starting a session

**With Claude:** There are two ways to talk to Claude about your vault: Claude Code (the command-line tool) and Cowork (the desktop app). They are largely interchangeable, but they have different strengths.

**Claude Code** runs in a Terminal session that's `cd`'d into your vault. Use it for serious wiki work: batch ingests, lint passes, PDF renders, anything where Claude needs to make a sequence of edits and commit them. Claude Code can also run git directly, so commits happen automatically at the close of each unit of work.

**Cowork** is the desktop app. Use it for casual capture: a thought you want to file, a chat you want to save, a quick query. Cowork can also do ingests and most other wiki operations, but it cannot run git directly (a platform constraint of the sandbox it runs in). Instead, it leaves the working tree dirty and your next Claude Code session auto-commits with the `vault` shell function.

A typical day might use both: Cowork during the day for whatever comes up, Claude Code in the evening for the bigger sessions.

**With ChatGPT:** Open ChatGPT and, from its File menu, choose Open Folder and pick your wiki folder. <!-- verify on testdev --> ChatGPT reads the vault's rules from `AGENTS.md`. Its sandbox protects the vault's `.git` folder, so ChatGPT asks you to approve each commit. That is expected.

## The standard task flow

Whatever the task, the flow looks roughly the same:

1. **You describe what you want**, in plain English. ("Ingest the new clipping." "Draft a page on Gardening with what I know so far." "Trace how my notes on stoicism connect to my notes on parenting.")
2. **Your assistant reads the vault.** It opens `CLAUDE.md` (`AGENTS.md` with ChatGPT) for the conventions, `wiki/_context.md` for the working state, and any relevant existing pages.
3. **Your assistant does the work.** It updates the wiki, follows your house style, adds backlinks where they belong, logs the change, and commits.
4. **Your assistant reports back.** A short summary of what changed and, if relevant, an offer to continue ("Would you like me to also update the related page on X?").

You almost never need to tell your assistant where to put things, what to name files, or how to format. The schema in `CLAUDE.md` answers all of that. You describe the work; your assistant handles the bookkeeping.

## Common requests

Here are some examples of the kinds of things you might say, and what your assistant will do. You do not need exact wording; it triggers the relevant skill from the phrasing.

**"Ingest the new clipping."** Your assistant looks in `Clippings/` for the most recent file, reads it, updates every relevant wiki page, appends a log entry, moves the source to `Clippings/processed/`, and commits.

**"Draft a page on [topic] from what I tell you."** Your assistant asks structured questions about the topic, captures your answers, drafts a top-level wiki page, and saves it. If `[topic]` already has a page, it appends to the existing one.

**"What does my wiki say about [X]?"** Your assistant searches the vault and answers, citing the pages it drew from with `[[Page Name]]` links. After substantive answers, it offers to save the answer back as a wiki page or a section of an existing page.

**"Lint the wiki."** Your assistant scans for contradictions, stale claims, orphan pages, and missing backlinks. The report goes to `outputs/lint-report-YYYY-MM-DD.md` and the issues become a small backlog of corrective edits you can work through over the next session.

**"PDF up the [page name] page."** The `wiki-to-pdf` skill renders the page (and optionally its cluster notes) as a branded PDF, saves the file to `outputs/`, and logs the render.

**"Capture this chat to the wiki."** The `wiki-capture` skill summarises the salient parts of the current chat, writes a well-formed capture note into `raw/`, and points you at the next ingest pass.

**"Save what we just discussed about [X]."** Like the above, but scoped to a specific topic from the current conversation rather than the whole chat.

## What Claude won't do without asking

A few things require explicit permission. Your assistant will pause and ask before:

- Creating a new top-level wiki page. (The convention is that new domains need your sign-off; subfolder pages and edits to existing pages don't.)
- Making changes to `CLAUDE.md` itself. (The schema is yours; your assistant proposes edits, you accept them.)
- Pushing to a remote git server. (With Claude, local commits happen automatically; with ChatGPT you approve each one. Pushes do not happen without asking.)

Deleting a file is different: your assistant never does it, with or without a yes. It renames or archives on its own, and if something should go it tells you what and where, and you remove it yourself (`09-safety.md`).

If your assistant is being too cautious or too aggressive, edit `CLAUDE.md` and adjust the rule. The schema is the source of truth for behaviour; change it and your assistant changes.

## When Claude is wrong

Your assistant will sometimes get something wrong: it'll mis-attribute a quote, conflate two people with similar names, or misread a date. The verification rule in `CLAUDE.md` (don't invent, don't speculate, mark uncertainty `[Unverified]`) reduces the rate, but does not eliminate it.

When you spot an error, tell your assistant. ("That date is wrong. The article is from 14 April, not 15." or "That quote is from a different person with the same name; please re-check.") It will correct the wiki page and add a `correction:` entry to the log explaining what changed and why. The log is append-only, so the error and its fix both stay visible.

Corrections are full entries in the log, and over time they make the system more trustworthy.

## When you're ready

Move on to [04-first-ingest.md](04-first-ingest.md) for a worked example of your first ingest, or jump to [05-skills.md](05-skills.md) for a reference on the bundled skills.
