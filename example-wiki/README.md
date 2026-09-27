# example-wiki

## What this is

A small, finished Moblee wiki that belongs to an invented person called Sam. It sits in `Sam Wiki/` beside this file. It is here for one reason: a new owner is asked to build a wiki without ever having seen one, and "what is a wiki?" is a question that explaining does not answer. Being shown one does.

Open `Sam Wiki/Welcome.md` and follow the links. The reading path, meaning `Welcome.md` and the pages it sends you to, is about 2,000 words and takes under ten minutes.

## Everyone in it is invented

Sam does not exist. Nothing here is drawn from any real person, and nothing in it can be traced to one. There are no real place names, no employer, no family, no ages, no pronouns. Sam bakes bread on Saturdays, rides a second-hand bike and borrows library books, and that is the whole of Sam.

Every source in the example is a conversation with Sam, so no publication, author or book title is named anywhere. That was deliberate: an invented title or byline can collide with a real one, and the example has no need of either.

## It is meant to stay small

Nine markdown files and 3,700 words, of which about 2,000 sit on the reading path: `Welcome.md`, the three content pages, `Index.md` and `_context.md`. The other three, `CLAUDE.md`, `Identity.md` and `log.md`, are there so the shape is honest and are meant to be skimmed rather than read.

Nine is the number because the four canonical files plus `Identity.md` and `Welcome.md` are fixed at six, and three content pages is the smallest number that shows a page being cross-linked, a page growing over months and a page going quiet. Two would not show all three. A new owner who is defeated by the example has learned nothing from it, and every page added makes that more likely. If something new needs showing, make an existing page richer rather than adding a tenth.

It is also frozen. The example ends on 19 September 2026 and will slowly age relative to today's date. That is cosmetic: the dates are there to show that a page grows over months and that a log has gaps in it, and a reader will read them as a history rather than as news.

## It is not a template

The starter vault that gets copied into a new owner's home folder is `vault-template/`, one level up. This folder is never installed, never copied and never updated. Three things keep the two apart:

1. **The name.** `example-wiki`, with no "template", "starter" or "vault" in it, and the installers look for `vault-template` by name.
2. **A marker on every file.** Every one of the nine markdown files in `Sam Wiki/` carries the HTML comment `<!-- MOBLEE EXAMPLE. Sam is invented. This is a worked example for reading. It is never installed. -->` as its first line — except `wiki/Identity.md`, which has YAML frontmatter, as a real `Identity.md` does, and carries the marker on the line straight after it. (This README is not one of the nine and has no marker; it is about the example rather than part of it.) The comment is invisible in Obsidian's reading view, so it does not spoil the read, and it is what anybody opening a file or grepping the repository finds.
3. **What is missing.** No `VERSION` file and no `.gitignore`, both of which a real vault has. Anything that treats this folder as a vault to install or update will find it incomplete.

`Sam Wiki/CLAUDE.md` is a shortened rules file, under a page rather than the real one's several. It says so at the top and points at `vault-template/CLAUDE.md` for the full set.

## What it is for

Three things, in order.

**Showing what a wiki is.** Pages that hold what somebody knows, linked to each other, that grow.

**Showing what the assistant does.** Sam never opens a file. Every page here arrived by Sam saying something out loud, and the log records who wrote what and when.

**Showing the payoff.** `Sam Wiki/wiki/Bread.md` is the page to read. Sam mentioned in passing on 16 May 2026 that the kitchen was cold. On 5 September 2026 a loaf failed, and that sentence, recorded nearly four months earlier for no reason, explained it. A wiki is what makes that possible, and no description of a wiki conveys it.
