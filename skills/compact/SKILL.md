---
name: compact
description: On-demand compaction pass that trims and stratifies the user's wiki vault to hold the per-session token budget down (detect the vault at runtime; the MOBLEE_VAULT environment variable, then ~/.config/moblee/vault-path, then walking up from the working directory for a folder containing wiki/Index.md). It is the executor half of the compaction system; the detector half is the lint-v2 "Vault weight" guard (scripts/lint-v2.py), which flags files over their token caps but never trims. Trigger when the user says "compact the wiki", "trim the wiki", "run a compaction pass", "compact", "the vault's heavy", "compact _context", "slim the Index", "trim [page]", "stratify [page]", or when the user tells you to act on a vault-weight flag a lint run raised. Two halves with different autonomy: (1) the deterministic, reversible MECHANICAL rotations (rotating _context.md refresh notes past the latest three into the Context Archive and archiving closed Active-thread / Open-decision / Watch-list entries to a one-line strikethrough index) run unattended, because they only move text into the archive page; the two mechanical moves that take something off a page or out of a folder (dropping aged strikethrough lines from _context.md, sweeping stray files from the outputs/ root into category subfolders) are LISTED first and run only after the owner says yes; (2) the lossy PROSE trims (condensing a verbose section, lifting detail to a wiki/Wiki Operations/ file behind a stub-plus-wikilink, re-slimming Index.md to one line per page) are proposed with before/after token weights and executed only on the user's explicit sign-off, in-session, with a reviewable git diff and a commit. Triages by token weight against the caps (_context.md ≤ 12k, Index.md ≤ 8k, CLAUDE.md ≤ 16k, wiki pages flagged > 25k); goes after the worst offenders, not every page. Hard guardrails: additive-to-archive never deletive (no sourced fact, figure, date, attribution or wikilink is dropped; it moves to the archive, a Wiki Operations file, or stays); the append-only log.md is never touched; any restricted folders are excluded; nothing lossy is autonomous. Do not trigger on lint health-checks (that is lint), on raw/ ingests (ingest), on reflective analysis (brain), on PDF renders (wiki-to-pdf), or on capture-to-raw (wiki-capture).
---

# compact: holding the wiki's token budget down

The compaction executor. Its job is to keep the vault light so every session starts cheap and every page is cheap to touch, without losing anything from the record. It is the deliberate, on-demand counterpart to the **detector**: the `lint-v2.py` "Vault weight" guard reports which files are over their caps; `compact` is what acts on that report, when the user asks.

## Finding the vault

Detect the vault root at runtime, in this order: the `MOBLEE_VAULT` environment variable; the path recorded in `~/.config/moblee/vault-path` (the Moblee installer writes it); otherwise walk up from the current working directory looking for a folder containing `wiki/Index.md`. If none of those finds a vault, say so plainly and stop; do not guess a path. With ChatGPT the vault's rules file is `AGENTS.md`; read that wherever this skill says `CLAUDE.md`.

## Why this exists

The session-start read (`CLAUDE.md` + `wiki/_context.md`) is paid in tokens at the start of every session, and every large page is paid again whenever it is touched. Left alone, `_context.md` creeps back up as threads accumulate, `Index.md` quietly stops being a one-line catalogue and becomes a document, and synthesis pages accrete past the point where editing them is cheap. The compaction *discipline* lives in the vault's `CLAUDE.md` (stratify a section past three or four paragraphs; keep the summary plus a wikilink, lift the detail to a `wiki/Wiki Operations/` file). This skill operationalises that discipline as a repeatable pass, paired with the lint's automated weight report so bloat never sneaks up.

## The Context Archive

The cold-storage companion for `_context.md` lives at `wiki/Wiki Operations/Context Archive.md`. **If it does not exist yet** (a fresh vault has no `Wiki Operations/` folder), create it on the first rotation: make the folder, create the page with a one-paragraph header explaining that it holds rotated `_context.md` refresh notes and the full text of closed threads and decisions, and give it two sections: `## Refresh-note history` and `## Closed threads and decisions`. Add a one-line entry for the new subfolder to `Index.md`'s Subfolder pages section, and link the archive from `_context.md` so it is reachable from the live file.

## The two halves, by autonomy

Compaction is split by risk. The two archive-only moves run on their own; anything that removes a line from a page or relocates a file is listed and confirmed first; the lossy moves never run without sign-off.

### Half one: MECHANICAL rotations (deterministic, reversible)

These follow existing rules exactly and drop no information. Two of them only move text into the archive page and run unattended (beyond the commit at the end); the other two take something off a page or out of a folder, so the skill **lists exactly what it would do and waits for the owner's yes** before doing it:

1. **`_context.md` refresh-note rotation** (unattended). Keep the **latest three** *Last refreshed / Previous refresh* notes inline (only the most recent at full length, the two prior compressed to one-sentence headlines); lift the rest to the Context Archive under *Refresh-note history* (newest at the top of that list).
2. **Closed-entry archiving** (unattended). When an Active-thread / Open-decision / Watch-list entry has closed, move its **full text** to the Context Archive (under the matching closed section) and leave a **one-line strikethrough index entry** inline on `_context.md` (title, close date, archive link). Open entries stay inline in full.
3. **Tombstone aging** (list, then ask). Strikethrough index lines whose close date is more than ~30 days old are candidates for dropping from `_context.md` entirely, the archive staying the sole record. Before proposing any line, verify its full text exists in the Context Archive (grep the title); a line with no archive copy gets copied there verbatim first. Then present the candidate lines as a short list (title and close date for each) and ask for a yes; drop only the lines the owner confirms. If the drop empties a section, leave "None currently open" plus the archive link in its place.
4. **`outputs/` root sweep** (list, then ask). Stray render artefacts at the `outputs/` root are candidates for moving into category subfolders (create sensible ones, `reports/`, `lint/`, and so on, if the vault has none yet), leaving genuinely recent one-offs at root as the "what's new" view. Present the proposed moves as a list (each file and its destination folder) and ask for a yes; move only what the owner confirms. Never delete anything from `outputs/`.

### Half two: PROSE trims (lossy, judgement-gated, sign-off required)

These condense or relocate real prose, so they are **proposed, not done**: name the specific cut, show the before/after token weight, wait for the user's yes, then execute in-session with a `git diff` they can read:

1. **Section condensing.** Tighten a verbose section that has accreted repetition, while preserving every sourced fact, figure, date, attribution and wikilink in it. If a condense would risk dropping a fact, don't do it; lift instead.
2. **Stratify to a `Wiki Operations/` file.** When a section is long but load-bearing, move the detail to a dedicated `wiki/Wiki Operations/<Topic>.md` file and leave a **three-to-four-sentence summary plus a wikilink** in place.
3. **Cluster-note / subfolder extraction.** For an over-threshold synthesis page, move dated per-source material into the page's cluster-note subfolder (the `wiki/<Topic> Cluster Notes/` pattern from the vault's `CLAUDE.md`), leaving the synthesis plus a thematically grouped index.
4. **`Index.md` re-slimming.** Strip `Index.md` back toward one short line per page; lift any multi-paragraph "Sources Ingested"-style accretion off it (chronology belongs to `log.md`, not the Index).

## Triage: by weight, not by breadth

Run `python3 scripts/lint-v2.py` (or read the latest `outputs/lint/lint-v2-*.md`) for the current weight numbers, and go after the worst offenders only. The caps:

| Target | Cap | When over |
|---|---|---|
| `wiki/_context.md` | ≤ 12k tok | rotate refresh notes + archive closed items (mechanical); if still over, propose condensing the heaviest inline thread |
| `wiki/Index.md` | ≤ 8k tok | re-slim to one line per page (gated) |
| `CLAUDE.md` | ≤ 16k tok | stratify a section to a `Wiki Operations/` file (gated) |
| top-level `wiki/*.md` | flag > 25k tok | cluster-note / subfolder / stub-plus-link extraction (gated) |
| `wiki/log.md` | annual rollover | leave it: append-only, tailed not loaded; an annual rollover to `wiki/log-archive/` bounds it |

Token counts are estimated as characters divided by four, matching how the lint's guard estimates them. **With ChatGPT:** by default only the first 32 KiB of the rules file is read, which is less than the 16k cap; Moblee's installer raises that limit, and the check-up says if it is missing (the companion's field guide, F27). Most pages are fine and should not be touched. A compaction pass is surgical: name the few files over cap, act on those.

## Hard guardrails

- **Additive-to-archive, never deletive.** Nothing leaves a page without landing somewhere durable first: the Context Archive, a `Wiki Operations/` file, or git history. No sourced fact, figure, date, attribution line or wikilink is dropped. When in doubt, lift rather than cut.
- **Verification rule applies in full.** A condensing rewrite must preserve the meaning and every verifiable claim of what it replaces. No invention, no smoothing-over of a `[Unverified]` marker, no quietly-dropped caveat.
- **`log.md` is never reordered, rewritten or pruned.** Append-only is a hard rule; the one permitted touch is appending the pass's own log entry like any other unit of wiki work. (Annual rollover is the only log-size mechanism, and it is not this skill's job.)
- **Excluded folders.** Any folders the vault marks as restricted (a `restricted:` frontmatter field, or a convention recorded in the vault's `CLAUDE.md`) are excluded from this skill exactly as from every other; never read or compact them.
- **Nothing lossy is autonomous, and nothing leaves a page or folder unasked.** The two archive-only rotations run unattended; tombstone drops and `outputs/` moves are listed and confirmed first; every prose trim waits for the user's explicit sign-off and shows them the diff.
- **Stub-plus-link on every lift.** A relocated detail block always leaves a short summary and a `[[wikilink]]` behind, so the page still reads coherently and the graph stays connected.

## Workflow

1. **Measure.** Run `scripts/lint-v2.py` and read the *Vault weight* section (or compute directly). Identify the files over cap.
2. **Mechanical pass.** Do the two archive-only rotations on the flagged always-loaded files (`_context.md` note-chain and closed-entry archiving; these alone often bring `_context` back under cap). Create the Context Archive first if the vault does not have one yet. Then list any aged tombstone lines and any stray `outputs/` root files as candidates, with what would happen to each, and wait for the user's yes before dropping or moving anything. Re-measure.
3. **Propose the rest.** If a file is still over cap, draft the specific prose trims as a short proposal: which section, which target file, the before/after token delta. Present it; do not execute yet.
4. **Execute approved.** On the user's yes, make the edits in-session, verifying each lift preserved its facts and left a stub-plus-link. Confirmed tombstone drops and `outputs/` moves can be batched with the same yes if the user gives one.
5. **Verify + report.** Re-run `lint-v2.py`; confirm the weight section now passes (or report the residual and why). Show what moved where.
6. **Commit** at the natural close of the pass (`housekeeping:` for mechanical-only, or a descriptive message naming the pages slimmed and the token deltas), and append the pass's log entry to `wiki/log.md`. The log entry names any tombstone lines dropped and any files moved, so the confirmation has a record.

## Relationship to the other operations

- **lint** is the detector; **compact** is the executor. The `lint-v2.py` weight guard flags files over cap and never trims; `compact` is run on demand to act on those flags. They are two halves of one budget-control loop.
- **brain `graduate`** (if installed) moves items between `_context.md` status tiers and is the natural precursor to the closed-entry archiving here; if a thread needs *closing* (a status decision), that is `graduate`; once it is closed, moving its text to the archive is `compact`.
- **ingest** grows the wiki; **compact** keeps it light. They pull in opposite directions by design, which is why compaction is a deliberate, periodic pass rather than something folded into every ingest.

## What this skill does not do

- It does not run on a schedule. The *detector* (the weight guard in the lint) can be cadenced; the *cutting* is on-demand only, because lossy edits to the knowledge base should be deliberate and reviewed.
- It does not delete from `raw/processed/` or `Clippings/processed/`, and it does not prune `outputs/`: the root sweep only relocates files into subfolders, and only the ones the user has confirmed.
- It does not drop a strikethrough line from `_context.md` or move a file without first listing it and getting a yes. Silence is not consent; if the user does not answer, the candidates stay where they are and are reported as pending.
- It does not invent, summarise away a caveat, or drop a fact to hit a number. If a page cannot be brought under cap without losing something, it reports that and leaves the page over cap rather than degrading it.
