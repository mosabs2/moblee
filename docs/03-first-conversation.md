# 03. Your first conversation with Claude in this system

By this point you have a working Moblee vault and the skills installed. This document explains how the conversational workflow looks in practice, so you know what to expect when you open your assistant for the first time inside your new vault.

## Starting a session

**With Claude:** There are two ways to talk to Claude about your vault: Claude Code (the command-line tool) and Cowork (the desktop app). They are largely interchangeable, but they have different strengths.

**Claude Code** runs in a Terminal session that's `cd`'d into your vault. Use it for serious wiki work: batch ingests, lint passes, PDF renders, anything where Claude needs to make a sequence of edits and commit them. Claude Code can also run git directly, so commits happen automatically at the close of each unit of work.

**Cowork** is the desktop app. Use it for casual capture: a thought you want to file, a chat you want to save, a quick query. Cowork can also do ingests and most other wiki operations, but it cannot run git itself (a constraint of the sandbox it runs in), so it leaves its work unsaved and notes what it changed in your `wiki/log.md`. It does not stay unsaved for long. The wiki now saves itself at the end of every reply, so the next conversation you have in your wiki saves whatever Cowork left, as "changes found in the wiki".

A typical day might use both: Cowork during the day for whatever comes up, Claude Code in the evening for the bigger sessions.

**With ChatGPT:** Open ChatGPT and, from its File menu, choose Open Folder and pick your wiki folder. Make sure Work is chosen at the top of the window, and not Chat, before you type. <!-- verify on testdev --> A message typed while Chat is chosen is answered with an offer, "Continue in Work", and pressing it carries the task on in a folder of ChatGPT's own, outside your wiki, where the wiki's rules are not read. With Work chosen, the conversation runs in the wiki folder you opened. ChatGPT reads the vault's rules from `AGENTS.md`. Its sandbox protects the vault's `.git` folder, so ChatGPT asks you to approve each commit. That is expected.

## The standard task flow

Whatever the task, the flow looks roughly the same:

1. **You describe what you want**, in plain English. ("Ingest the new clipping." "Draft a page on Gardening with what I know so far." "Trace how my notes on stoicism connect to my notes on parenting.")
2. **Your assistant reads the vault.** It opens `CLAUDE.md` (`AGENTS.md` with ChatGPT) for the conventions, `wiki/_context.md` for the working state, and any relevant existing pages.
3. **Your assistant does the work.** It updates the wiki, follows your house style, adds backlinks where they belong, logs the change, and commits.
4. **Your assistant reports back.** A short summary of what changed and, if relevant, an offer to continue ("Would you like me to also update the related page on X?").

You almost never need to tell your assistant where to put things, what to name files, or how to format. The schema in `CLAUDE.md` answers all of that. You describe the work; your assistant handles the bookkeeping.

**Nothing is left unsaved.** The wiki also saves itself at the end of every reply. You can stop in the middle of something, close the window and walk away: the work up to that point is saved, and you never have to come back and ask for it. If a save was refused, nothing is lost: the work is still on your Mac, exactly as it was left, and only its entry in the wiki's history is missing. Two things tell you. **The check-up** — "Check my wiki" in the Moblee app — says how much the last save left unsaved and what to ask for; and **the band above where you type** in Claude says whether the wiki's work is saved, though only when it appears, which is on a long conversation that has gone quiet. And if you ask your assistant "what is still unsaved?", it reads the record and tells you. That record is kept at `~/.config/moblee/state/turn-end-commit.json`.

**Your own unfinished work is never swept into it.** Anything you have half-written yourself — in the rules file, or in Moblee's own folders — is left for your own next commit rather than saved under Moblee's name, and the check-up tells you it was left.

## Your first week

For the first five days you use the wiki, your assistant adds one line to the end of its first answer each day: one thing the wiki can do that fits what you have been doing, with an offer to show you. On the first day that line comes with a short map of what there is. Say yes and it shows you; say no and it is written down and not offered again for ninety days; say "not now" and nothing is written down. A day counts only when you use the wiki, so a week away does not use it up. Say "stop the tour" to end it early, and "show me everything" at any time to hear the whole list, which is kept on the page `What Your Wiki Can Do`. After the fifth day it goes quiet, and offers only when you say "guide me". **With ChatGPT:** there is no tour yet; "show me everything" still works.

## Saying orient each morning

Say **orient** when you come back to the wiki. You get one short report: the date and time, the three things most alive in your wiki, any decision waiting on you, and what is sitting in `raw/` and `Clippings/`. Your daily note's Plan becomes the day's to-do list in three parts: your to-dos, most urgent first; what you are waiting on from others; and standing items. At each orient your assistant adds the day's new to-dos at the top, and when a piece of work settles one, it ticks it straight away. The dashboard shows the same list. An unticked box means "planned this morning", never "you failed to do it": what is done is read from the wiki's record, not from the box.

**The mail pass, if you want it.** If your mail is in Apple Mail, your assistant offers once to sort your unread mail at each orient. It reads only the sender, subject and date of each unread message, never the message itself. Mail from people, money mail and things you must act on stay unread, and the things to act on go to the top of your to-do list; promotions are marked read, and newsletters are marked read and moved to a mailbox called News. Nothing is ever deleted, sent, unsubscribed or put in junk. The first time, macOS asks whether your assistant may control Mail, and you click OK; the first pass shows you what it would do and waits for your yes. Say no and it is not offered again for ninety days. The method is on the page `Mail Pass` in `wiki/Wiki Operations/`.

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
