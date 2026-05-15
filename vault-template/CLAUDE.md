# CLAUDE.md

This is a starting `CLAUDE.md` for your wiki. Edit it freely as your conventions evolve. It documents the rules YOU want Claude to follow when working in your vault. The shape of the file (sections, ordering, the kind of rules it carries) follows the Karpathy LLM Wiki Pattern; the specific conventions inside are yours to keep, change, or strip.

This file provides guidance to Claude Code and Cowork when working with code in this repository.

## What this repository is

This is **not a code repository**. It is an Obsidian vault implementing the **Karpathy LLM Wiki Pattern**: a personal knowledge base for [Your Name] where Claude is the maintainer. There are no builds, tests, or package managers. "Work" here means reading source material and editing markdown files. See `wiki/Karpathy LLM Wiki Pattern.md` and `wiki/How to Use This Wiki.md` for the full philosophy.

## Session opener

At the start of any wiki work, read `wiki/_context.md` for current state and tempo (active threads, open decisions, watch list, and recent significant additions).

## Three-layer architecture

1. **Raw sources** (immutable): material the user drops in. Read from these, never modify.
   - `raw/`: manual drop zone for PDFs, HTML, text, images, audio. Quote paths if filenames contain spaces or non-ASCII characters.
   - `Clippings/`: Obsidian Web Clipper deposits clean markdown with YAML frontmatter (source URL, author, date). Treat identically to `raw/`. If you use Readwise, the feed lives under `Clippings/Readwise/` and follows different rules (see **Readwise conventions** below); the two populations are distinguished by path, not by folder.
   - `Clippings/Readwise/`: optional continuous automated feed from Readwise.io. Three sub-categories at `Clippings/Readwise/Articles/`, `Clippings/Readwise/Books/`, and `Clippings/Readwise/Tweets/`, each with different ingest rules.
2. **The wiki** (`wiki/`): Claude owns this layer entirely. Compiled, interlinked markdown pages. The user reads; Claude writes.
3. **The schema**: this file plus `wiki/How to Use This Wiki.md`, `wiki/Karpathy LLM Wiki Pattern.md`, and `wiki/_context.md`. Co-evolves over time.

`outputs/` holds generated reports (lint passes, triage reports), write new reports here, not in `wiki/`.

## The three core operations

**Ingest**, when given new files in `raw/` or `Clippings/`:
1. Read the source.
2. Update *all* relevant existing wiki pages (a single source typically touches 5–15 pages: entity pages, topic pages, cross-references). Create a new topic page only when a genuinely new domain emerges; new top-level pages require explicit user approval before creation.
3. Append a dated entry to `wiki/log.md` (format: `## [YYYY-MM-DD HH:MM ±TZ] type | Title, Publication`, one per source file, newest at the bottom, append-only). The `HH:MM ±TZ` time-stamp is mandatory on every new log entry. The log is the canonical chronological record; do not duplicate it onto `Index.md`.
4. Touch `wiki/Index.md` only when the ingest creates a new top-level page (add a one-line Domains entry) or a new subfolder page (extend the relevant Subfolder pages line). Bump the Index header's `Last updated` line if the ingest is substantive enough to warrant a state acknowledgement.
5. Refresh `wiki/_context.md` if the ingest moves the state of an active thread or open decision: bump the Last refreshed timestamp and re-tail the Recent significant additions paragraph. Routine same-pattern ingests that do not change state can be skipped.
6. Move the original from `raw/` (or `Clippings/`) to `raw/processed/` (or `Clippings/processed/`). Do not delete.
7. Commit the new work to git per the **Git commit workflow** section below. Claude runs `git add .` and `git commit -m "ingest: ..."` on the user's behalf; the user never types git commands.

**Query**: answer questions by searching the wiki and citing pages with `[[Page Name]]` links. After substantive answers (comparisons, analyses, syntheses), offer to save the answer back as a wiki page so explorations compound.

**Lint**: when asked to "lint" or "health-check" the wiki, scan for contradictions between pages, stale claims superseded by newer sources, orphan pages with no inbound links, important concepts mentioned but lacking their own page, missing reciprocal backlinks, and data gaps. Write the report to `outputs/lint-report-YYYY-MM-DD.md` and log it.

## House style

All new content written into the wiki follows these conventions. Apply them when creating pages or adding sections; do not retroactively reformat legacy pages (see "Style migration" below). Swap any of these for your own preference; this is the starter default.

**British English** throughout: colour, analyse, defence, organisation, optimise, recognise, behaviour, centre, programme. (Swap for American English if you prefer; pick one and stay consistent.)

**Analytical prose, not bullet lists.** Write in flowing paragraphs that develop a line of thought, using **bolded inline labels** where they help the reader scan. Reserve bullet points for genuinely list-like content: ordered steps in a sequence, inventories of items, tournament brackets, equipment specs, succession tables. A page that argues, compares, or explains should read as paragraphs.

**No em dashes.** Use commas, semicolons, parentheses, or split the sentence into two. This applies even where an em dash would feel natural.

**No emojis** unless the user explicitly asks for them.

**Quotations**: only quote when the exact wording matters and the quote is under fifteen words; put it in quotation marks with attribution. Otherwise paraphrase. Long block quotes from sources should be summarised, not transcribed.

**Dates are always absolute.** Write "14 April 2026", never "last week", "yesterday", or "this month". When source material uses relative dates, convert them to absolute dates using the source's publication date as the anchor before saving to the wiki.

## Log timestamps and session-metadata convention

The log is the canonical record of work, and over time it becomes queryable for usage metrics: how often the wiki is accessed, which sessions added the most pages, what the working tempo looks like across weeks and months. Two conventions support this.

**1. Time-stamped headers.** Every log entry uses the format `## [YYYY-MM-DD HH:MM ±TZ] type | Title`, where `HH:MM ±TZ` is the workstation clock at the time the entry is written (typically the close of the activity it records). Verify the time via Bash `date` rather than guessing.

**2. End-of-session housekeeping summary entries.** At the close of any substantive session (anything more than a single trivial ingest), append a final log entry with the type `housekeeping` (e.g. `## [YYYY-MM-DD HH:MM ±TZ] housekeeping | End-of-session summary`). This entry carries an inline metadata footer with at least: session start time, session end time, duration, total wiki pages touched, count of new wiki pages, count of new `raw/processed/` files, count of `raw/` to `raw/processed/` moves, and any tooling or schema changes. Format the metadata as a single italicised line so it greps cleanly: `*Session: started YYYY-MM-DD HH:MM; ended YYYY-MM-DD HH:MM; duration Xh Ym; wiki pages touched: N (M new, P modified); raw/processed/ files added: K; raw/ → raw/processed/ moves: L; tooling/schema: <list>*`. This is the line future metric queries will aggregate against. If the session is genuinely brief (one trivial ingest, no schema or tooling change), the housekeeping summary may be skipped; in all other cases it is mandatory.

## Source attribution and file movement

**Every ingested source carries an attribution line** in the target section so the provenance is visible on the page itself, not just in the log. Two formats:

- Web sources: `Source: [Title](URL), Publication, Date.`
- PDFs and local files: `Source: "Title," Date (filename.pdf).`

Place the attribution at the end of the section the source informs, or as a footer on a dedicated subsection. Multiple sources informing the same section get multiple attribution lines.

**File movement after ingest** is part of the ingest operation, not optional cleanup:

- Clippings processed from `Clippings/` move to `Clippings/processed/`.
- Raw files processed from `raw/` move to `raw/processed/`.
- PDFs that arrived as chat attachments (rather than via `raw/` or `Clippings/`) get a copy saved into `raw/processed/` under their original filename, so the provenance is preserved in the vault.

## Git commit workflow

The vault is under git. **Claude is responsible for running git on the user's behalf. The user should never need to type or be asked to type a git command.** The rhythm is hard-wired into the workflow; Claude triggers it at the close of any unit of wiki work without prompting.

**When to commit.** At the natural close of any unit of wiki work, not only "big" sessions. Specifically: after each ingest pass (step 7 of the Ingest workflow, after the move to `processed/`); after a lint pass (commit the report plus any wiki edits the lint surfaced); after any housekeeping summary entries that touched `log.md`, `_context.md`, or `Index.md`; after tooling or schema changes (commit including any `CLAUDE.md` edits or skill-file edits where those live in the vault); after comparative-analysis outputs (commit the indexing line on the relevant wiki page; the output PDF itself is gitignored under `outputs/`); at the close of any session that touched `wiki/` content, even routine same-pattern ingests. If a session is genuinely a no-op on `wiki/` (a read-only query with no save, for example), no commit is needed.

**How Claude commits.** Mechanism depends on the runtime environment.

In **Claude Code** on a Mac or Linux workstation, run `git add .` then `git commit -m "<message>"` via the Bash tool; the global git config on the machine carries the author identity. Fully autonomous; the user sees nothing.

In **Cowork**, two platform constraints currently block full autonomy. The workspace bash mount that backs the sandbox uses a bindfs FUSE filesystem that blocks the `unlink` syscall, and git relies on unlinking `.git/index.lock` after every operation (even read-only ones like `git status`); attempting git in the sandbox leaves stale lock files behind. Terminal is also granted at tier "click" under Anthropic's app policy (visible and clickable, but typing is blocked), so computer-use cannot type into Terminal either. The workable mechanism is the **clipboard handoff**: Claude composes the full git command (including any stale-lock cleanup with `rm -f .git/index.lock .git/index.lock.stale` if a prior sandbox attempt left files behind), writes it to the user's clipboard via `mcp__computer-use__write_clipboard` (this requires `clipboardWrite: true` in the `request_access` call), brings Terminal forward via `open_application` if needed, and asks the user to paste (Cmd+V) and press Return. That is two keystrokes on the user's side with the command pre-composed by Claude; nothing for them to remember or to type from scratch. Full autonomy is only achievable in Claude Code today; in Cowork the two-keystroke paste-and-Enter is the minimum-friction approximation of the principle.

Alternative pattern for Cowork: a `vault` shell function installed once on the user's machine that auto-commits accumulated Cowork changes at the start of the next Claude Code session. With this pattern, Cowork sessions leave the working tree dirty and note what changed in their `wiki/log.md` entry; the log entry is the audit trail. The user runs `vault` at the start of their next session, which commits whatever has accumulated with a session-start commit message.

**Commit message format.** One short imperative line aligned with the log entry the commit accompanies: `ingest: <Title>, <Publication>` for ingests; `housekeeping: <descriptor>` for housekeeping summaries; `tooling: <descriptor>` or `schema: <descriptor>` for infrastructure or schema work; `lint: <date> health check` for lint passes; `correction: <descriptor>` for corrective entries.

**Mid-session catch-up.** If a session opens and `git status` shows untracked or modified files from prior work, catch those up first with descriptive commits based on what's there, before starting new work.

**Recording in the log.** Substantive commits should be referenced by short hash in the relevant log entry's `tooling/schema:` or housekeeping footer when the work itself merits it. Routine same-pattern commits do not need their hash recorded; the git log itself is the canonical record.

## Style migration

If your wiki accumulates material in different styles over time, do not retroactively reformat legacy pages. Write all new content (new pages, new sections appended to old pages) in the current house style. Old pages migrate naturally as their sections are next edited or rewritten in the course of normal ingests.

## Hard rules

- **Verification rule**: never invent, infer, or speculate. Only include what is explicitly stated in the source. Mark uncertainty `[Unverified]`. Leave gaps blank rather than filling them.
- **Filename = link target**: wiki page files must be named to exactly match their `[[Link]]` target (e.g. `[Your Domain].md`, not `02-[your-domain].md`) so Obsidian's graph view shows one node per page. Capitalisation matters.
- **Third person** throughout the wiki.
- **Append-only log**: never reorder or rewrite past `wiki/log.md` entries.
- **Index reflects navigation, not chronology**: every new top-level page gets a one-line entry in `wiki/Index.md` Domains; subfolder additions surface in the Subfolder pages section. The Index header's `Last updated` line records the most recent material change. The chronological record of every ingest lives in `wiki/log.md`, not on the Index.
- **Sensitive material** (credentials, VPN tokens, passwords) found in raw sources: flag it to the user, do not store it in the wiki. Recommend the user move credentials to a dedicated password manager.
- **Date verification**: before stamping any wiki page, log entry, source attribution line, or dated filename with today's date, verify the actual current date against the workstation clock. In Claude Code: run `date` via Bash. In Cowork (iPhone or web), where Bash is not available: trust the system-injected `currentDate` and, if any uncertainty remains or source materials carry a different date, ask the user to confirm the date in the conversation before writing. Never propagate a date from a source document or conversational context without checking it against the live clock first.
- **Identity disambiguation in source notes**: when a source note uses a bare first name, a first-person pronoun ("I", "me"), or a first-person plural ("we", "us", "our"), verify which person and role is being referenced before transcribing into the wiki. Meeting notes typically have a host and one or more visitors and the first-person voice may be either. When ambiguous, name both parties explicitly on first reference inside the wiki and use a disambiguating short form for subsequent mentions. Resolve source-side ambiguity before transcription, or the wiki will misattribute.

## Wikilinks and structure

- `[[Page Name]]` for full-page links; `[[Page Name#Heading]]` for sections; `[[Page Name|display text]]` for aliases.
- After updating any page, ensure reciprocal backlinks exist on related pages, this is how the graph stays healthy.
- The Index (`wiki/Index.md`) is the content catalogue: a Domains section (one short line per top-level page), a Subfolder pages section (one line per subfolder, not enumerating files), and a header-line `Last updated` field. Chronology lives in `wiki/log.md`; working state lives in `wiki/_context.md`; the schema lives in this file. The four-file split (Index for navigation, `log.md` for chronology, `_context.md` for working state, `CLAUDE.md` for schema and conventions) is the canonical separation of concerns: each file owns one role and does not duplicate the others. Resist the temptation to fold any one file's responsibility into another.

## Domain-specific patterns

These are pattern templates you can apply when a domain produces recurring events or accumulates many similar source documents. The shapes are reusable; fill in the brackets with your own domains.

**Recurring-session pattern.** When a domain produces frequent dated events (training sessions, medical checkups, project standups), each event lives as one page in `wiki/[Your Domain] Sessions/`, named in date-first form: `YYYY-MM-DD [descriptor].md`. Each session page carries YAML frontmatter (`date`, `type`, `parent: "[[Your Domain]]"`, plus any domain-specific fields) and a canonical table or structured section schema you settle on. The main `wiki/[Your Domain].md` page holds synthesis only (background, current state, narrative) plus a "Recent Sessions" list of wikilinks to the latest session pages. A rolling per-session data file at `wiki/data/[your-domain]-sessions.csv` can carry the headline numbers across all sessions for trend queries; append one row per session on each ingest.

**Comparative analyses.** Cross-session or cross-source comparative analyses are run only on explicit user request. Each output is saved as a dated standalone document in `outputs/` (PDF, HTML, or markdown as appropriate) and indexed by a single line in the relevant page's "Comparative Analyses" subsection. Comparative analyses are never maintained as living text inside a wiki page; treat them as snapshots that go out of date the moment the next session lands, not as sections to refresh on every ingest.

**Cluster-notes pattern.** When a topic accumulates more than three or four dated article ingests, dated article ingests for that thread live as one page per source in `wiki/[Your Domain] Cluster Notes/`, named in date-first form: `YYYY-MM-DD Title - Publication.md`. Each cluster note carries YAML frontmatter (`date`, `type: Article`, `publication`, `parent: "[[Your Domain]]"`) and the analytical body and source line. The main `wiki/[Your Domain].md` page becomes synthesis only, with a thematically grouped Cluster Notes index. Promote a topic-level synthesis page to top-level when it grows to multi-section depth.

## Index philosophy

`wiki/Index.md` is the **content catalogue**. One short line per page, organised by category. The Index does not duplicate the chronological record; that lives in `wiki/log.md`. The Index also does not duplicate working state; that lives in `wiki/_context.md`. When a new top-level page is created, add a one-line catalogue entry to the Domains section. When subfolders gain new pages, the subfolder is listed once in the Subfolder Pages section without enumerating each file (the folder is browseable in Obsidian). Resist the temptation to keep multi-paragraph "Sources Ingested" lists on Index; that work belongs to the log.

## Readwise conventions

(Applies only if you use the Readwise plugin. If you do not, this section is dormant but harmless.)

**Path-based disambiguation.** `Clippings/` holds two distinct file populations with opposite ingest rules. Files directly under `Clippings/<file>.md` are Obsidian Web Clipper one-shot captures and follow the standard move-to-`Clippings/processed/` convention on ingest. Files under `Clippings/Readwise/<sub>/<file>.md` are plugin-managed sync files and follow the stay-in-place plus frontmatter-mark convention described below. The discriminator is the path, not the folder; a Web Clipper file inside `Clippings/Readwise/` would be an error, and a Readwise file outside it would break the plugin's update path. Moving a Readwise file to `Clippings/processed/` would break the plugin's update guarantee and cause re-sync plus double-ingest, so never do it.

`Clippings/Readwise/` is a continuous automated feed, not a manual ingest inbox. Files are updated by Readwise on subsequent syncs as the user adds more highlights, so they must **never be moved to processed/**. Instead, mark a processed file with YAML frontmatter and leave it in place:

```yaml
---
processed: true
processed_date: YYYY-MM-DD
wiki_target: "[[PageName#Section]]"
---
```

The three sub-categories have different handling rules:

**Articles** (`Clippings/Readwise/Articles/`): treat like Clippings, ingest selectively when relevant, write the content into the appropriate wiki page, add `processed: true` frontmatter to the source file. Do not move the file. On future ingest scans, skip any Readwise file where `processed: true` is set unless the user explicitly asks to re-process it.

**Books** (`Clippings/Readwise/Books/`): do not ingest speculatively. These are ongoing highlight collections that grow over time. Use on demand: when the user wants to draw on a book's highlights for a wiki page or query, read the file and extract the relevant material at that point. Do not mark as processed (the file is never "done").

**Tweets** (`Clippings/Readwise/Tweets/`): reference layer only. Do not ingest. Available for searching if a specific saved thread becomes relevant.

## Useful tools in this environment

Web Clippings arrive with YAML frontmatter; preserve the source URL, author, and date when citing. PDFs and images in `raw/` can be read directly. Subfolder pages (e.g. `wiki/[Your Domain]/[Sub-page].md`, `wiki/[Your Domain] Sessions/YYYY-MM-DD ....md`) resolve via `[[basename]]` wikilinks regardless of folder, since Obsidian matches by filename across the vault.
