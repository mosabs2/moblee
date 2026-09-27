<!-- MOBLEE EXAMPLE. Sam is invented. This is a worked example for reading. It is never installed. -->

# CLAUDE.md

**This is the example wiki's rules file, and Sam is an invented person.** It is a shortened version of the real one, kept to a page so that somebody reading the example can get through it. The full rules file, with every convention on it, is the one that comes with Moblee at `vault-template/CLAUDE.md`.

## What this repository is

Not a code repository. It is an Obsidian vault: a personal knowledge base for Sam, where the assistant is the maintainer. Work here means reading what Sam says and editing markdown files.

## Session opener

Read `wiki/_context.md` for current state, and `wiki/Identity.md` for how the assistant works with Sam.

## Three layers

Raw sources in `raw/` and `Clippings/`, which the assistant reads and never changes. The wiki in `wiki/`, which the assistant owns and Sam reads. The schema, meaning this file and `wiki/_context.md`.

## The three core operations

**Ingest.** Sam says something worth keeping, or drops a file in `raw/`. The assistant updates every page it touches, appends a dated entry to `wiki/log.md`, puts an attribution line in the section the source informs, and refreshes `wiki/_context.md` if the state moved.

**Query.** Answer from the pages, citing them as `[[Page Name]]` links, and offer to save a good answer back as a page.

**Lint.** On request, check for contradictions, stale claims, pages nothing links to, and gaps.

## Commit at the end of every piece of work

The assistant runs `git add .` and `git commit` itself, at the close of every unit of work. Sam never types a git command.

## Plain words

Sam does not read much and does not want to. Short sentences, one idea each, the common word rather than the long one. Say what happened and what it means for Sam. If a summary needs reading twice, it is not finished.

## House style

British English. Paragraphs rather than bullet lists, except for genuinely list-like things such as a recipe or an inventory. No em dashes. No emojis. Dates always absolute: "20 June 2026", never "last month". Third person throughout the wiki.

## Hard rules

- **Never delete without Sam's explicit yes in the same message.** Finished material moves; it is never removed. A guard on the machine enforces this.
- **Never invent, infer or speculate.** Only what a source actually says. Mark anything uncertain `[Unverified]`. Leave a gap blank rather than filling it.
- **Say when something is not known.** Anything that changes with time is checked against a live source before it is stated.
- **The log is append-only.** Never reorder or rewrite a past entry.
- **Filename equals link target**, capitalisation included.

## Four files, four jobs

`wiki/Index.md` is the catalogue. `wiki/log.md` is the chronology. `wiki/_context.md` is the working state. This file is the schema. None of them repeats another.

## Sam's own conventions

Added as Sam has made them, dated, in Sam's words.

- 16 May 2026: quantities in grams, oven temperatures in Celsius.
- 4 July 2026: no star ratings on books. Sam wants a sentence about what the book was like instead.
- 12 September 2026: put the part numbers on the page, because Sam will be standing in the shop reading it on a phone.
