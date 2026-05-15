# How to add content to your wiki

This folder, `raw/`, is the inbox for source material before it's curated into the wiki. Anything you drop in here is treated as immutable: Claude reads from it, extracts what's useful into the wiki, and then moves the original into `raw/processed/` so the provenance is preserved.

You never edit files in `raw/` after dropping them. The wiki layer (`wiki/`) is where curated, interlinked knowledge lives; `raw/` is the source layer that the wiki is built from.

## Three ways content lands here

**Web Clipper.** Articles you read in the browser, clipped via the Obsidian Web Clipper extension, drop into `Clippings/` (not `raw/`). Clippings arrive as clean markdown with YAML frontmatter that preserves the source URL, the author, and the publication date.

**Readwise.** If you have a Readwise account and the Obsidian Readwise plugin installed, your highlights, books, and tweets sync into `Clippings/Readwise/` automatically. The three sub-folders (`Articles/`, `Books/`, `Tweets/`) each have slightly different handling rules; see `CLAUDE.md` at the vault root for the full Readwise conventions.

**Manual drop.** Anything else, PDFs, screenshots, text files, transcripts, voice memos, audio clips, you drop into this folder (`raw/`) directly. Drag it from Finder; quote the filename if it contains spaces or non-ASCII characters when you mention it to Claude.

## What happens when Claude processes a source

1. Claude reads the source.
2. Claude updates all relevant existing wiki pages (a single source typically touches 5–15 pages).
3. Claude appends a dated entry to `wiki/log.md`.
4. Claude moves the original from `raw/` to `raw/processed/` (or from `Clippings/` to `Clippings/processed/`). Files in `Clippings/Readwise/` stay in place but get a `processed: true` frontmatter flag.
5. Claude commits the change to git.

You'll see the wiki update; you won't have to lift a finger after the drop.

## How to ask Claude to process this folder

In Cowork or Claude Code, just say:

- "Process the new files in raw/."
- "Process the new clippings."
- "I dropped a PDF in raw/, please ingest it."

Claude will scan, read, integrate, log, and commit.
