---
name: brain
description: Run reflective queries against the user's personal Obsidian wiki. Trigger when the user wants substantive analytical output drawing across multiple wiki pages or sources, when the user wants to move items between status tiers on _context.md, when the user wants to channel a wiki-documented persona's voice, or when the user wants a morning brief, an end-of-day close, or forward planning. Eleven patterns. Six read-only originals: trace (how an idea or stated belief has evolved over time; the drift variant handles position shifts), connect (bridges between two domains), emerge (latent themes the vault implies but never states), challenge (pressure-test a belief against the vault's history), ideas (vault-wide ideation against active threads and the watch list), synthesise (place a new source into the existing corpus). Two with narrow writeback — graduate (promote/demote items between Active Threads / Open Decisions / Watch List / Closed on _context.md) and ghost (adopt the voice of a persona the wiki documents deeply, read-only). Three temporal patterns operating on the Daily Notes layer — today (morning brief), close-day (end-of-workday reflection writing closed_at to the current workday's daily note), schedule (planning ahead into future daily notes). Trigger on phrases like "trace X across my wiki", "connect X and Y", "what does my vault imply", "challenge my view that X", "give me ideas from my vault", "synthesise this against my wiki", "promote X to active", "close the Y decision", "what would [persona] say about Z", "today", "morning brief", "close the day", "plan the week", or any clear variant. Do not trigger on simple lookups, factual recall, or capture-only requests (those route to wiki-capture directly).
---

# Brain — reflective queries against the wiki

A skill for asking the wiki questions that draw across multiple pages and sources, rather than retrieving a single fact, and for the temporal patterns that operate on the Daily Notes layer. **Eleven patterns** in three groups:

- **Six read-only analytical patterns**: **trace** (how an idea or stated belief has evolved over time; `drift` is a triggerable variant focused on position shifts), **connect** (bridges between two domains), **emerge** (latent themes the vault implies but never states), **challenge** (pressure-test a belief against the vault's history), **ideas** (vault-wide ideation against active threads and the watch list), and **synthesise** (place a new source into the existing corpus).
- **Two governance/persona patterns**: **graduate** (promote/demote items between `_context.md` status tiers — narrow writeback to `_context.md` plus `log.md`), and **ghost** (adopt the voice of a wiki-documented persona to answer a question, read-only).
- **Three temporal patterns** operating on the `Daily Notes/` layer: **today** (morning brief), **close-day** (end-of-workday reflection with narrow writeback), and **schedule** (planning ahead, narrow writeback to future daily notes).

## Why this exists

The wiki's three core operations are ingest, query, and lint. Ingest writes new material in; query retrieves; lint health-checks. What is missing without this skill is the reflective layer — patterns that take the corpus as it stands and produce analytical synthesis: how a position has evolved, what two domains share, what the vault implies but never says, where a stated belief contradicts the vault's own history — plus the daily rhythm: what today looks like, how the workday closed, what the week ahead holds.

**Writeback discipline.** Eight of the eleven patterns are read-only and use `wiki-capture` for save-back, preserving the separation between reflection and writing. Three patterns have narrow scoped writeback: `graduate` writes only to `_context.md` (the file it operates on by definition), `log.md` (so every move is audited), and optionally `Index.md` (catalogue moves); `close-day` writes only `closed_at` to the current workday's daily-note frontmatter, a `workday-close` housekeeping entry to `wiki/log.md`, and the next calendar day's daily note (created from template with carry-forwards seeded into Plan); `schedule` writes only to future `Daily Notes/YYYY-MM-DD.md` files. None of the three write to any other `wiki/` page, and none write to a daily note's body (the daily note is a planning-only artefact).

## The corpus

The vault lives at the user's configured vault path (the directory this repository's installer created, e.g. `[Your Vault]/`). Four locations are in scope, all read-only:

- **`wiki/`** — compiled wiki pages. The primary corpus.
- **`wiki/log.md`** — append-only chronology. Use this for absolute-time anchoring (`## [YYYY-MM-DD HH:MM ±TZ]` headers).
- **`raw/processed/`** — source material already merged into the wiki. Use to verify claims against original sources where needed.
- **`Clippings/processed/`** — clipped articles already merged. Same use.

Two locations are deliberately out of scope by default:

- **`raw/`** (unprocessed) — material the wiki has not yet adopted a view on. Querying it would mix the vault's positions with material it has not yet integrated. The user can override explicitly ("include unprocessed material"). Exception: the `ideas` pattern scans the inbox by design.
- **`Clippings/`** (unprocessed) — same reasoning.

The schema layer (`CLAUDE.md`, `wiki/_context.md`, `wiki/How to Use This Wiki.md`, `wiki/Karpathy LLM Wiki Pattern.md`) is read at session start but is not treated as analytical material — it is the rules and the state, not content to reflect on.

**Restricted folders, if the user creates any.** If the vault grows folders the user marks as restricted (private material, or AI voice-reconstructions), exclude them from every pattern's default reads; they are opt-in only when the prompt names the folder or a page in it. A `restricted:` frontmatter field on a page is the marker to respect.

## House style

All output follows the vault's house style as recorded in its `CLAUDE.md`. The points that matter most for brain output: analytical prose rather than bullet lists; absolute dates only ("14 April 2026", never "last week"); quotations under fifteen words with attribution, otherwise paraphrase; cite with `[[Page Name]]` and section anchors; and the verification rule — never invent; if the corpus does not say something, do not say it; mark uncertainty `[Unverified]`.

## The six analytical patterns

### trace — how an idea has evolved over time

Use when the user asks to follow a single concept, theme, or position through the wiki and see how it has changed. Two registers under one workflow: concept-history (how coverage evolved) and **drift** (how the *stated position* shifted, including the user's own recorded stance).

**Triggers:** "trace X across my wiki", "show me the history of X", "track X over time", "how have my views on X drifted", "where has my thinking on X moved".

**Workflow:** identify the concept (one clarifying question if ambiguous); search the corpus for the term and close synonyms; cross-reference each occurrence against `wiki/log.md` for absolute time; group hits into chronological buckets, compressing each to one or two sentences naming what was claimed and what changed; close with a synthesis paragraph naming the arc and any active uncertainty (cross-reference `_context.md`'s watch list).

**Output:** dated chronology plus closing synthesis, 300-600 words (up to 1000 for long arcs). Ends with the save-back offer.

### connect — bridges between two domains

Use when the user asks how two named domains, pages, or topics relate.

**Triggers:** "connect X and Y", "what's the link between X and Y", "find the overlap", "X meets Y in my wiki".

**Workflow:** identify the two targets (propose the closest match if one has no page); read both pages in full; walk one level of backlinks out from each (bridges are most often in pages that link to both); identify shared entities, dates, sources, and thematic threads; rank bridges by non-obviousness — a shared person appearing in two eras is a high-value bridge, "both pages mention money" is not.

**Output:** structured synthesis naming each bridge with citations to both sides, 400-800 words. Flag any single-direction link as a candidate reciprocal-backlink fix for the next lint pass.

### emerge — latent themes the vault implies but never states

Use when the user asks what the vault knows but has not yet named.

**Triggers:** "what does my vault imply", "surface unstated patterns", "what's emerging", "what am I not yet seeing".

**Workflow:** take a scope (default: the last 30 days of `log.md`; the user may narrow or widen); scan for recurring concepts appearing in three or more pages without having their own page; weight by recency and cross-domain spread; discard candidates that already have `[[Page]]` status; present survivors with evidence.

**Distinction from `ideas`:** emerge surfaces patterns that exist but are unnamed (passive observation); ideas surfaces actions worth taking (active proposals).

**Output:** 3-7 candidate patterns, each with 2-4 citations and one sentence on why it is non-trivial. Ends with the offer to promote any candidate to a new wiki page (routed through `wiki-capture`).

### challenge — pressure-test a belief against the vault's history

Use when the user asks the wiki to argue against a stated position.

**Triggers:** "challenge my view that X", "pressure-test this", "what contradicts X in my wiki", "where am I wrong about X", "steel-man the opposite".

**Workflow:** locate the stated belief in the wiki (or accept it as given from chat); search for contradicting evidence in related pages and `raw/processed/`; identify prior position shifts via log timestamps; surface the wiki's own uncertainty markers; present a structured rebuttal.

**Output:** belief in one sentence; contradicting evidence with citations; prior shifts; residual uncertainty; a verdict line ("The wiki strongly / partially / does not support this view, with [main caveat]"). 400-700 words.

### ideas — vault-wide ideation against active threads and the watch list

Use when the user asks what to work on or where the live opportunities are.

**Triggers:** "give me ideas from my vault", "what should I work on next", "what's interesting in my wiki right now".

**Workflow:** read `_context.md` in full; scan the last 30 days of `log.md` for ingested-but-unintegrated material; cross-reference active threads against unprocessed `raw/` and `Clippings/` items (the inbox is in scope for this pattern only); look for cross-domain intersections; group candidates by horizon (immediate, medium, speculative).

**Output:** 5-10 candidate ideas, each one paragraph with rationale and 1-3 citations, grouped by horizon. 600-1000 words.

### synthesise — place a new source into the existing corpus

Use when a new source has been provided and the user wants a structured comparative reading against the existing wiki.

**Triggers:** "synthesise this against my wiki", "cross-reference this new source", "place this in context", "comparative postscript".

**Workflow:** read the new source in full; identify its core claim, the author's perspective, and its relevance to existing domains; search the corpus for related material; walk one level of backlinks from the most relevant page; produce a four-thread postscript: (1) **personal connection** (where the source's author or subjects appear elsewhere in the wiki), (2) **substantive connection** (where the argument fits existing analytical clusters), (3) **historical pattern** (what the source repeats or extends), (4) **strategic implications** (what it implies for active threads, with concrete tracking suggestions).

**Output:** four numbered subsections, 500-1500 words. Ends with the offer to file as a postscript on the relevant page (routed through `wiki-capture`).

## graduate — move items between status tiers on _context.md

Use when the user wants to move an item between the tiers on `wiki/_context.md`: **Active Threads**, **Open Decisions**, **Watch List**, and the closed (~~struck-through~~) historical record. Graduate's write access is scoped narrowly: `_context.md`, `log.md` (every move is audited), and optionally `Index.md` (catalogue changes only).

**Triggers:** "graduate X to active", "promote X", "retire the Y watch-list item", "close the Z decision", "the X thread is done — close it".

**Workflow:**

1. Read the relevant `_context.md` section and locate the item's exact wording; ask one clarifying question if ambiguous.
2. Identify the move: promote (watch → active, or watch → open decision), demote (active → watch), close (any tier → struck-through record), or reopen (rare).
3. Verify the move is sensible: promotions need named triggering evidence; closures need a named resolution. Ask for the rationale in one sentence if it has not been given — it gets folded into the edit.
4. Make the edit following the file's conventions: closures use a `~~CLOSED [YYYY-MM-DD HH:MM ±TZ]~~` strikethrough prefix with the resolution appended; keep original wording where possible.
5. **Closures only:** if the closed item leaves an unresolved variable behind, spawn it as a discrete Watch List item (concrete name, options, a date or condition trigger) and mention the spawn in the closure rationale, so nothing fades silently with a closure. Ask the user if unsure whether a variable remains open.
6. Append a one-line `## [YYYY-MM-DD HH:MM ±TZ] graduate | <descriptor>` entry to `log.md` (verify the time with `date` first).
7. Confirm by quoting the new `_context.md` entry back in chat.

**The verification rule applies even here:** if the user asks to close a thread the wiki shows as still active, push back.

## ghost — adopt the voice of a wiki-documented persona

Use when the user wants a question answered in the voice of a persona the wiki documents in substantial depth — a family member with a rich page, a historical figure whose writing the vault holds, a mentor whose views are recorded. Ghost is read-only; the persona's response is **reconstructed from the wiki's record** of what they said, wrote, and how they reasoned — never invented.

**Triggers:** "what would [persona] say about X", "channel [persona] on Y", "in [persona]'s voice".

**Eligibility:** the persona needs substantial wiki documentation — a dedicated page, recorded positions, quoted material. For thinly-documented people, fall back to "the wiki records this person as holding X; the available material suggests…" rather than ghosting fully.

**Workflow:** read the persona's pages in full; read the question's target; identify the persona's documented positions on adjacent topics, their characteristic reasoning mode and voice; produce the response opening with a **"Ghost-voice: [persona]"** header so the framing is unmistakable; cite the wiki sources inline; where the persona has no documented position, say so explicitly inside the ghost voice. Close with a citation list and the save-back offer.

**If the user keeps accepted ghost outputs**, store them in a dedicated folder (e.g. `wiki/Ghost Reconstructions/`) marked `restricted: ghost-only` in frontmatter, excluded from every skill's default reads, with links flowing one direction only (reconstruction → subject page, never back). AI inference of a real person's voice must never surface to other patterns as if it were the person's documented position.

## The three temporal patterns (Daily Notes layer)

These operate on `<vault>/Daily Notes/` (created from `Daily Notes/_TEMPLATE.md`). A daily note is a **planning-only artefact**: frontmatter (`date`, `day`, `created`, and `closed_at` once closed), a Plan section (checkboxes), a Scheduled section, Body and Notes. Item resolution is determined by `log.md`, not checkbox state.

### today — morning brief

**Triggers:** "today", "morning brief", "what's on my plate today", "what does today look like".

**Workflow:** verify the date via `date`; open today's daily note (create from `_TEMPLATE.md` if absent — the single write this pattern makes); check the prior note's `closed_at` (if absent, the prior workday never closed — flag it and offer `close-day` on it); read `_context.md` for date triggers due today and threads with movement; read `log.md` since the last workday-close (cross-reference seeded Plan items against log evidence — tick what is already done); compose the brief: today's plan, scheduled items, threads with movement, watch-list triggers, overnight activity, and a one-sentence shape of the day.

**Output:** structured brief, 200-500 words. No save-back offer — the brief is operational.

### close-day — end-of-workday reflection

**Triggers:** "close the day", "wrap up", "end of day", "close out today".

**Workday-bounded, not calendar-bounded:** the workday is keyed by the date it *started* on; a day that ends at 00:30 still closes the prior date's note, stamps `closed_at` with the actual fire time, and creates the new date's note.

**Workflow:**

1. Verify date and time via `date`.
2. Identify the current workday's note: the most recent `Daily Notes/YYYY-MM-DD.md` with no `closed_at`. If several are unclosed, ask which to close.
3. Read the note's Plan; read all `log.md` entries since the prior `workday-close` entry.
4. Walk Plan checkboxes against log evidence; items with evidence are done; for the rest, ask the user in one consolidated message (done / partial / carry forward).
5. Check `_context.md` for staleness: if the day's work moved state the file has not absorbed, offer to apply the refresh as part of the close.
6. Compose the `workday-close` entry for `log.md`: one paragraph on the shape of the day, one on carry-forwards, one as the wiki-activity roll-up, and an italicised footer (start, close, duration, session count).
7. Stamp `closed_at: YYYY-MM-DD HH:MM ±TZ` on the note's frontmatter; append the log entry; create the next day's note from template with carry-forwards seeded into Plan.
8. Confirm in chat briefly (under 200 words) — the log entry is the durable artefact.

### schedule — plan ahead

**Triggers:** "plan tomorrow", "plan the week", "plan before [date]", "schedule the week".

**Workflow:** identify the horizon (ask one clarifying question if ambiguous); verify the date; read `_context.md` for deadlines and date-shaped next steps in the horizon; read any existing future daily notes (schedule adds, never overwrites); propose a draft schedule in chat with per-day rationale; **ask for confirmation**; on approval, write Plan entries to the relevant future daily notes, creating missing ones from template; confirm each write.

## Reading the corpus

If `obsidian-cli` is installed, prefer it for backlink traversal (`obsidian-cli backlinks file="Page Name"` — named arguments; positional silently returns nothing) and content search (`obsidian-cli search query="text"`). Otherwise fall back to Grep for content search, Read for full pages, and manual `[[Page Name]]` scanning for backlinks — and say so once at the start of the response, since flat-text scanning may miss cross-references only the link graph would surface (this matters most for `connect` and `emerge`).

## Saving results back

Brain is **read-only with three narrow exceptions** (`graduate`, `close-day`, `schedule`, each scoped as described above). For the read-only patterns, when the user accepts a save-back offer, compose the result as a capture note in the format `wiki-capture` expects and hand it to `wiki-capture` for the write into `raw/`; the next ingest pass integrates it. If the user explicitly says "write it directly into [[Page]]", honour it — but flag once that this bypasses the ingest pass.

Daily-note writes are deliberately outside git-churn concerns: if the user's vault ignores `Daily Notes/` in git, that is fine — the log entries carry the durable record.

## What this skill does not do

- It does not write to `wiki/` for any pattern other than `graduate` (and `close-day`'s log entry). Save-back routes through `wiki-capture`.
- It does not perform ingest or lint; those are the wiki's separate operations.
- It does not run on raw/unprocessed material by default (exception: `ideas` scans the inbox).
- It does not invent — the verification rule applies to every pattern, including `ghost` (never invent a persona's position) and the temporal patterns (never invent a deadline, a completion, or a carry-forward the record does not support).

## The proactive offer

After a substantive query response that has implicitly drawn across multiple pages, offer brain explicitly **once**: *"Want me to run a proper trace / connect on this rather than just answer the surface question?"* Never offer twice in one chat if declined; never offer for simple lookups.
