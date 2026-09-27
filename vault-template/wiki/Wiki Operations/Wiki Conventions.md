# Wiki Conventions

Reference detail the assistant reads when the work calls for it, kept off `CLAUDE.md` so the rules file stays short. The rules file carries the short form of everything here; this page carries the detail.

## Log entries

Every entry in `wiki/log.md` uses the header form `## [YYYY-MM-DD HH:MM ±TZ] type | Title, Publication`, where the time is the workstation clock when the entry is written. The zone is written short, `+01`, and keeps its minutes only where it has them (`+0530`). One entry per source file, newest at the bottom, append-only, and never reordered or rewritten afterwards.

Write entries with `python3 scripts/log-append.py` rather than composing the header by hand. It reads the clock itself and emits the one correct form. Verify the date by running `date`, never by guessing or by carrying a date over from a source.

The log is the canonical record of work, and over time it becomes queryable: how often the wiki is used, which sessions added the most, the tempo across weeks and months.

## End-of-session housekeeping entries

At the close of any substantive session, meaning anything more than a single trivial ingest, append a final log entry of type `housekeeping`, for example `## [2026-09-20 18:04 +01] housekeeping | End-of-session summary`.

That entry carries a metadata footer as a single italicised line, so it greps cleanly:

```
*Session: started YYYY-MM-DD HH:MM; ended YYYY-MM-DD HH:MM; duration Xh Ym; wiki pages touched: N (M new, P modified); raw/processed/ files added: K; raw/ → raw/processed/ moves: L; tooling/schema: <list>*
```

A brief session, one trivial ingest with no schema or tooling change, may skip the summary.

## Source attribution

Every ingested source carries an attribution line in the section it informs, so the provenance is visible on the page and not only in the log. Two forms:

- Web sources: `Source: [Title](URL), Publication, Date.`
- PDFs and local files: `Source: "Title," Date (filename.pdf).`

Place it at the end of the section the source informs, or as a footer on a dedicated subsection. Several sources informing one section get several attribution lines.

## Moving files after ingest

Moving the original is part of the ingest, not optional tidying afterwards:

- Files processed from `raw/` move to `raw/processed/`.
- Files processed from `Clippings/` move to `Clippings/processed/`.
- Files under `Clippings/Readwise/` never move; see [[Readwise]].
- A PDF that arrived as a chat attachment, rather than through `raw/`, gets a copy saved into `raw/processed/` under its original filename, so the provenance is kept in the vault.

Nothing is ever deleted.

## Data freshness

Stable knowledge gets ingested; data that changes constantly gets connected instead. Every volatile figure written into the wiki (prices, indices, league positions, counts) carries its absolute as-of date, and the section naming it points at its live source in prose.

When a query turns on a volatile figure and a live source exists, fetch the current value and answer with that, using the wiki's recorded value only as the trend anchor. Update the page's figure when it has materially diverged and the page is being touched anyway, never as a sweeping refresh pass. A volatile number that is the *subject* of an analytical claim is always fetched live before the claim is made.

## The Index

`wiki/Index.md` is the content catalogue: one short line per page, organised by category. It duplicates neither the chronology (`wiki/log.md`) nor the working state (`wiki/_context.md`).

A new top-level page gets a one-line entry in the Domains section. When subfolders gain new pages, the subfolder is listed once in the Subfolder Pages section, without enumerating each file, since the folder is browseable in Obsidian. The header's `Last updated` line records the most recent material change. Multi-paragraph "Sources Ingested" lists belong to the log, not here.

## Style migration

Do not retroactively reformat old pages. Write all new content in the current house style; old pages migrate as their sections are next edited in the course of normal ingests.

## Keeping `_context.md` light

`wiki/_context.md` is working state, and the assistant reads it in full at every session start, so it is kept light. When an ingest advances an item on it, **fold the superseded state into the current state** rather than appending another dated bullet; the detail belongs on the parent page. Appending without folding is the specific habit that bloats the file.

When finished history accumulates, lift it to `wiki/Wiki Operations/Context Archive.md`: keep only the latest three refresh notes inline, only the most recent at full length, and move closed items to the archive behind a one-line strikethrough pointer.

Before adding anything to `_context.md` or to `CLAUDE.md`, ask whether it is needed every session, in which case it belongs there, or whether it is reference detail needed occasionally, in which case it belongs on a page like this one behind a wikilink.

The weekly lint's weight guard flags always-loaded files over their token caps (`_context.md` 12k, `CLAUDE.md` 16k, `Index.md` 8k) and never trims them itself. When it flags a file, the **compact skill** acts on it: mechanical rotations run freely, lossy prose trims are proposed for the owner's sign-off.

## Daily Notes, an optional layer

If the brain skill's temporal patterns (`today`, `close-day`, `schedule`) are in use, daily notes live in `Daily Notes/YYYY-MM-DD.md`, created from `Daily Notes/_TEMPLATE.md`.

A daily note is a **planning-only artefact**: a Plan section holding the morning's intent, a Scheduled section, and frontmatter that gains `closed_at` when the workday closes. Unticked checkboxes mean "this was planned", not "this is unresolved"; whether an item was resolved is determined by `wiki/log.md`, not by checkbox state. The workday is keyed by the date it *started* on, so a session ending at 00:30 still closes the previous date's note. `close-day` is triggered by the owner at the end of their workday, never nudged at a session boundary.

## Domain patterns

Reusable shapes to apply when a domain produces recurring events or accumulates many similar documents. Fill in the brackets with the owner's own domains.

**Recurring sessions.** When a domain produces frequent dated events (training sessions, medical check-ups, project standups), each event is one page in `wiki/[Domain] Sessions/`, named date-first: `YYYY-MM-DD [descriptor].md`. Each carries YAML frontmatter (`date`, `type`, `parent: "[[Domain]]"`, plus domain-specific fields) and a canonical table or section schema. The main `wiki/[Domain].md` page holds synthesis only, plus a "Recent Sessions" list of wikilinks. A rolling data file at `wiki/data/[domain]-sessions.csv` can carry the headline numbers across all sessions for trend queries; append one row per session.

**Cluster notes.** When a topic accumulates more than three or four dated article ingests, they live one page per source in `wiki/[Domain] Cluster Notes/`, named `YYYY-MM-DD Title - Publication.md`, each with frontmatter (`date`, `type: Article`, `publication`, `parent`) and the analytical body and source line. The main domain page becomes synthesis only, with a thematically grouped index of the cluster notes. Promote a topic-level synthesis to a top-level page when it grows to multi-section depth.

**Comparative analyses.** Run only on the owner's explicit request. Each output is a dated standalone document in `outputs/` and is indexed by a single line in the relevant page's "Comparative Analyses" subsection. They are never maintained as living text inside a wiki page: they are snapshots, and they go out of date the moment the next session lands.

## Subfolder pages

A page in a subfolder (`wiki/[Domain]/[Sub-page].md`, `wiki/[Domain] Sessions/YYYY-MM-DD ....md`) still resolves through a plain `[[basename]]` wikilink, because Obsidian matches by filename across the whole vault.
