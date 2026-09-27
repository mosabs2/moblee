# Readwise

Applies only if the Readwise plugin is in use. If it is not, this page is dormant and harmless, and the assistant never needs to read it.

## Two populations in one folder

`Clippings/` holds two distinct kinds of file with opposite ingest rules, told apart by path and not by anything inside them.

**Files directly under `Clippings/<file>.md`** are Obsidian Web Clipper one-shot captures. They follow the standard rule: ingest, then move to `Clippings/processed/`.

**Files under `Clippings/Readwise/<sub>/<file>.md`** are plugin-managed sync files. Readwise updates them on later syncs as more highlights are added, so they must **never** be moved to `Clippings/processed/`. Moving one breaks the plugin's update path and causes a re-sync and a double ingest.

A Web Clipper file inside `Clippings/Readwise/` would be a mistake, and a Readwise file outside it would break the plugin.

## Marking a Readwise file as done

This is the one thing the assistant ever writes into `Clippings/`, and the hard rule in the rules file names it as the one exception: everything else in `raw/` and `Clippings/` is read-only apart from the move to `processed/`. It exists because these files cannot be moved. It adds three lines at the top and changes not a word of the highlights.

Instead of moving it, mark it with YAML frontmatter and leave it exactly where it is. Three lines, between `---` markers at the top of the file:

```yaml
---
processed: true
processed_date: YYYY-MM-DD
wiki_target: see below
---
```

The third line names the page the highlights went to, as a wikilink in quotation marks: `wiki_target: "[[Page Name#Section]]"`. It is written here inside backticks, and it has to be: the commit gate reads a wikilink on a wiki page as a real link, and a made-up page name in an example would stop every commit in the vault.

On later ingest scans, skip any Readwise file with `processed: true` unless the owner explicitly asks for it to be re-processed.

## The three sub-categories

**Articles** (`Clippings/Readwise/Articles/`). Treat these like ordinary Clippings: ingest selectively when relevant, write the content into the right wiki page, add the `processed: true` frontmatter. Do not move the file.

**Books** (`Clippings/Readwise/Books/`). Do not ingest speculatively. These are ongoing highlight collections that grow over time. Use them on demand: when the owner wants to draw on a book's highlights for a page or a query, read the file then and extract what is relevant. Do not mark them processed, because the file is never finished.

**Tweets** (`Clippings/Readwise/Tweets/`). A reference layer only. Do not ingest. They are available for searching if a specific saved thread becomes relevant.
