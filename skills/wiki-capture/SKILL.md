---
name: wiki-capture
description: Capture substantive knowledge from a chat into the user's personal Obsidian wiki, which lives on the user's Mac at their configured vault path and syncs via Obsidian Sync (not iCloud). Use whenever the user says "save this to the wiki", "capture this", "log this", "wiki this", "add to my wiki", "remember this for the wiki", "capture everything from this chat", "save the whole conversation", "bulk capture", "summarise this chat and save it", or any clear variant. Also trigger after producing a chat summary, or after a clearly substantive exchange (research, decisions, contacts, project milestones), offer capture once at the end. Also use for vault housekeeping, when the user says "move the processed files", "tidy up raw", or "archive what's been merged", move merged files into raw/processed/. Do not trigger on chitchat, simple lookups, or ephemeral coding help. Writes directly to the vault when mounted, otherwise produces a copy-paste markdown artifact.
---

# Wiki Capture

A skill for funnelling knowledge from scattered Claude chats into a single Obsidian wiki that follows the Karpathy LLM Wiki Pattern.

## Why this exists

The wiki is maintained by Claude in a dedicated Cowork project, but the user interacts with Claude across many one-off chats throughout the day. Substantive material from those chats, a research answer, a decision, a new contact, a domain-specific insight, tends to evaporate when the chat closes. This skill makes capture a one-step operation: produce a well-formed note destined for `raw/`, either written directly (when the vault is on the filesystem) or as a copy-paste artifact (everywhere else). The ingest pass that runs in the dedicated wiki project handles promotion from `raw/` into the proper `wiki/` pages; this skill never touches `wiki/` itself.

## Vault location

The vault lives on the user's Mac at their configured vault path, typically:

```
[Your Vault]/
```

It is synced between the user's devices via **Obsidian Sync**, not via iCloud. Do not look for the vault in iCloud Drive, in `~/Library/Mobile Documents`, in any `Obsidian` subfolder under iCloud, or in any other location. If older project memory references an iCloud path, that information is out of date and must be ignored.

If a different user or machine adopts this skill, the path above is the only thing that should change; everything else in the skill is location-agnostic.

## Folders in the vault

Five folders matter. The skill should know what lives in each so it never writes to the wrong one:

- **`raw/`**, unprocessed source material. Chat exports, dumped documents, anything not yet compiled. **This is where capture notes go.**
- **`raw/processed/<source>/`**, where material moves after it has been merged into `wiki/`. `<source>` is one of `capture/`, `clippings/`, or similar; it records where the material originated. See "Housekeeping" below. Users with a one-time legacy notes import (for instance from Apple Notes) may also have a `raw/processed/apple-notes/` subfolder.
- **`Clippings/`**, articles saved from Safari via the Obsidian Web Clipper. Read-only from this skill's perspective; the ingest pass reads them and moves them to `raw/processed/clippings/` once merged.
- **`wiki/`**, the compiled, curated knowledge base. **Never written to by this skill.** The ingest pass owns it.
- **`outputs/`**, generated documents (PDFs, Word docs, exports). Not relevant to capture.

## When to use this skill

### Explicit triggers

Any of these (or clear variants) should invoke the skill:

- "save this to the wiki"
- "capture this"
- "log this"
- "wiki this"
- "add to my wiki"
- "remember this for the wiki"
- "capture everything from this chat" / "save the whole conversation" / "bulk capture", bulk mode, see below
- "summarise this chat and save it" / "sum this up and capture it" / "summary to the wiki", summary-capture combined, see below

### Summary-then-capture flow

The user routinely asks Claude to summarise a chat or a section of its contents. Summarising itself is a normal Claude task and does not invoke this skill. But two related patterns do:

1. **Combined phrasing** ("summarise this chat and save it to the wiki", "sum up the last hour and capture it"): route straight to bulk-capture mode. Do not produce a separate conversational summary first; the bulk-capture output *is* the summary, filtered and structured for the wiki. The difference between a plain summary and a capture is that capture filters ephemera and groups by target page; a combined request still wants that filter applied.

2. **Summary-then-offer**: when the user asks only for a summary, produce the summary normally, then offer capture once at the end. A summary is by definition a substantive synthesis, so it meets the proactive-offer bar. One sentence is enough:

   > *Want me to capture the wiki-worthy parts of that summary?*

   If the user accepts, proceed as bulk capture; the summary has already done the synthesis work, the capture step just applies the filter (drop ephemera), groups by target page, and formats into capture notes.

### Proactive offer (gentle)

After a **clearly substantive** Claude turn, offer capture **once** at the end of the response. One sentence is enough, e.g.:

> *Want me to capture this to your wiki?*

Clearly substantive means the response produced something worth keeping: research synthesis, a decision the user has arrived at, a new contact or relationship fact, a product recommendation with reasoning, a project milestone, or reference material the user is likely to want again. If in doubt, do not offer; the cost of missing a capture is small (the user can always ask explicitly), the cost of pestering is real.

**Never offer capture for:** casual chitchat, simple factual lookups Claude answered in one sentence, debugging a one-off code error, weather, arithmetic, small talk, drafts the user has already said to discard, or anything the user has signalled is ephemeral. Never offer twice in one chat if the first offer was declined; respect the signal.

## What a capture note looks like

Use this structure for every capture. It is the contract the ingest pass expects.

```
# [Short title: noun phrase, not a sentence]

**Captured**: YYYY-MM-DD
**Target page**: [[Exact Wiki Page Name]]
**Source context**: [one-line description of what prompted this capture]

## Content

[Compiled synthesis of the knowledge in analytical prose. Preserve key facts,
names, dates, numbers. British English. Under 500 words unless the material
genuinely warrants more. No bullet soup, no emojis. Convert any relative dates
("last week", "yesterday") to absolute dates.]

## Suggested integration

[One paragraph explaining which section of the target wiki page this should
be added to or extended, and naming any cross-references to other wiki pages
using [[Wiki Link]] syntax.]
```

### Conventions to enforce

- **British English** throughout: colour, analyse, defence, organisation, optimise. (Adjust to the user's preferred spelling convention if they have configured one.)
- **Analytical prose**, not bullet lists. This is a wiki of understanding, not a dumping ground of transcripts. Compile and synthesise; do not paste the chat verbatim.
- **No em dashes**, no buzzwords, no press-release tone. Professional but conversational, matching the user's preferred writing style.
- **Convert relative dates to absolute**. Today's date is available; use it.
- **Single quotes under 15 words** in quotation marks, and only when the exact wording matters. Otherwise paraphrase. Never paste long source quotations.
- **No credentials, passwords, security questions, VPN tokens, card numbers, or sensitive authentication material.** If such material appears in the source exchange, omit it silently from the capture and note in the `Source context` line that sensitive details were excluded.
- **Suggest cross-links** to other wiki pages where obvious, using `[[Page Name]]` syntax.

## Picking the target page

The wiki's page list lives in `wiki/Index.md`. If that file is accessible, read it and use its list as authoritative. The page list will be whatever top-level pages the user has accumulated; do not assume any particular set.

If the Index is not accessible, ask the user one focused question rather than guessing:

> *Which page should this land on? If you can name one of your top-level pages, I'll route it there; otherwise I can produce the capture with a placeholder target and you can resolve it on ingest.*

Offer a best guess plus one or two alternatives if the match is not obvious:

> *This looks like it belongs on **[Your Domain]**, though part of it could go on another page. Do you want one note on [Your Domain] with a cross-link, or two separate notes?*

### When the material spans multiple domains

Produce **separate capture notes**, one per target page, each cross-linked to the others. Do not cram a multi-domain exchange into a single file; it makes the ingest pass harder and dilutes the wiki.

### When the material is a question, not an answer

If the user says "save this question for later" or the material is genuinely an open question rather than knowledge, still capture it, but under a `## Questions` heading in the `Content` section, and flag it in `Suggested integration` so the ingest pass routes it to a Questions section of the target page.

### When the source material is too thin

Sometimes the user asks for a capture but the source exchange is sparse: a single sentence, a recommendation with no specifics, a decision with no reasoning. Pushing a thin note into `raw/` produces a weak wiki entry that the ingest pass will struggle with.

Before writing, check: does the source material have enough substance to produce a useful synthesis? If a captured note would be three sentences of unanchored facts, it is probably not worth capturing yet. In that case, push back briefly and name what's missing:

> *The material here is thin, no specifics, no sense of whether you'd actually pursue it. Happy to capture as-is if you want a placeholder, or a sentence or two more would produce a much stronger note. Which?*

This is not an excuse to refuse routine captures. A two-sentence update with a clear date and a clear action is a perfectly good capture. The test is whether a reader of the wiki six months later would find the entry useful, or would wonder why it was saved.

## Detecting the environment

Before writing anything, decide whether the vault is accessible on the filesystem.

The canonical path on the user's Mac is the user's configured vault path, typically:

```
[Your Vault]/
```

Check for it with:

```bash
ls -d "[Your Vault]/raw" 2>/dev/null
```

If the skill is running on the Mac itself (Claude Code, a local agent, or a Cowork session with the home directory mounted), that path should exist. If it does, use **direct-write mode**.

If the skill is running in a Cowork session where the vault has been mounted under a session-specific path instead, try:

```bash
ls -d /sessions/*/mnt/*/raw 2>/dev/null | head -1
ls -d /mnt/user-data/*/raw 2>/dev/null | head -1
```

If any of these returns a path, use **direct-write mode** with that path.

If none returns a path, use **artifact mode**. Never guess, and never invent a path. A failed write is worse than a cleanly-produced artifact.

**Do not search iCloud, `~/Library/Mobile Documents`, or any `Obsidian` folder under iCloud.** The vault is not there. Sync is handled by Obsidian Sync.

## Mode A: Direct-write (vault mounted)

1. Resolve the vault path from the check above. The `raw/` directory sits directly inside it.
2. Build the filename: `capture-YYYY-MM-DD-[slug].md` where the slug is 3–6 lowercase words from the title joined by hyphens.
3. If a file with that exact name already exists, append `-2`, `-3`, etc.
4. Write the capture note to `raw/`.
5. Confirm to the user:

   > *Captured to `raw/capture-YYYY-MM-DD-[slug].md`. It'll be picked up on the next ingest pass into **[[Target Page]]**.*

Do not touch anything under `wiki/`. Do not modify `wiki/Index.md`. The ingest pass owns all promotion from `raw/` into `wiki/`.

### Housekeeping: moving processed files

Once material in `raw/` (or `Clippings/`) has been merged into `wiki/`, it should be moved out of the intake folder into `raw/processed/<source>/` so future runs can tell new material apart from already-handled material.

This skill is primarily a *capture* skill, not an *ingest* skill; most of the time it is only adding new files to `raw/` and the ingest pass in the dedicated wiki project does the moving. But when this skill is running on the Mac with the vault mounted and the user explicitly asks for it ("move the processed files", "tidy up raw/", "archive what's been merged"), it should do the move itself.

The layout to create inside `raw/processed/` mirrors the intake source:

```
raw/processed/capture/        ← originals from raw/capture-*.md files
raw/processed/clippings/      ← originals from Clippings/
```

A user with a one-time legacy notes import may also need a `raw/processed/apple-notes/` subfolder or similar.

How to decide what to move: a file is "processed" when the corresponding content has landed on a `wiki/` page. The cleanest signal is that the user (or the ingest-pass chat log) confirms a file has been merged. Do not guess; if unsure whether a given file has been merged, leave it where it is and ask.

To perform the move, use `mv` (not copy-and-delete) so the file's modification timestamp is preserved. Create the destination subfolder first if it doesn't exist:

```bash
mkdir -p "[Your Vault]/raw/processed/capture"
mv "[Your Vault]/raw/capture-YYYY-MM-DD-[slug].md" \
   "[Your Vault]/raw/processed/capture/"
```

After a move batch, confirm briefly:

> *Moved N files to `raw/processed/capture/` and M to `raw/processed/clippings/`.*

If the vault is not mounted, the skill cannot do the move; just remind the user to run the ingest pass in the wiki project, which handles it.

## Mode B: Artifact (vault not mounted)

1. Build the same filename as above.
2. Produce a markdown artifact containing the full capture note.
3. Tell the user the exact filename and where it goes:

   > *Here's the capture note. Save it as `capture-YYYY-MM-DD-[slug].md` in the `raw/` folder of your vault next time you're on your Mac, the vault lives at `[Your Vault]/raw/`. The ingest pass will pick it up from there.*

The artifact must be fully self-contained; a user in a plain Claude.ai chat with no filesystem access should be able to copy it, paste it into a new file on their Mac, and be done.

## Bulk-capture mode

Triggered by phrases like "capture everything from this chat", "save the whole conversation", or "bulk capture this". Use this when a single chat has produced multiple distinct pieces of wiki-worthy material.

Process:

1. Read back through the full conversation and identify **distinct knowledge units**, each one should be something that would belong in a particular wiki page's particular section. A unit is not "every Claude turn"; it is "every coherent piece of knowledge worth preserving".
2. Group units by target wiki page.
3. Produce **one capture note per target page**, combining all that page's material from the chat into a single `Content` section. If two or three units from the chat all target the same wiki page, they belong in one note, not three; the ingest pass can separate them if needed, but producing three thin notes on the same target wastes cycles. Conversely, if units target three different pages, produce three separate notes.
4. If there are more than three or four target pages, show the user the proposed grouping first and get confirmation before generating the notes; the user may want to drop some or merge others.
5. Write (direct-write mode) or present (artifact mode) each note separately. In artifact mode, present them as distinct artifacts with distinct filenames.

What to exclude from bulk capture, even if it appeared in the chat: anything ephemeral (debugging a transient error, one-off calculations), anything the user already said to discard, and anything sensitive per the credentials rule above.

## Examples

### Example 1: Explicit single capture, vault on Mac

**User (after a long exchange on a particular topic):** *Save this to the wiki.*

Skill:
1. Runs environment check, finds the vault under the user's configured path.
2. Asks: *This looks like it belongs on [Your Domain]. Correct?*
3. User confirms.
4. Writes `[Your Vault]/raw/capture-YYYY-MM-DD-[slug].md` with a synthesis of the exchange.
5. Confirms: *Captured to `raw/capture-YYYY-MM-DD-[slug].md`. It'll be picked up on the next ingest pass into [[Your Domain]].*

### Example 2: Proactive offer declined

After a substantive turn, Claude ends the response with:

> *Want me to capture this to your wiki?*

User: *Not this time.*

Skill does not offer again for the rest of the chat.

### Example 3: Ambiguous target, artifact mode

**User (in a plain Claude.ai chat):** *Capture this for me, it spans two of my domains.*

Skill:
1. Environment check finds no vault mount. Artifact mode.
2. Notes two candidate pages: *This spans [[Domain A]] and [[Domain B]]. Two separate notes, cross-linked?*
3. User confirms.
4. Produces two markdown artifacts:
   - `capture-YYYY-MM-DD-[slug-a].md` → targets `[[Domain A]]`, cross-links to `[[Domain B]]`.
   - `capture-YYYY-MM-DD-[slug-b].md` → targets `[[Domain B]]`, cross-links to `[[Domain A]]`.
5. Tells the user: *Drop both into the `raw/` folder of your vault.*

### Example 4: Bulk capture

**User (at the end of a long research chat):** *Capture everything worth keeping from this chat.*

Skill:
1. Reads back the conversation.
2. Identifies three knowledge units across two target pages.
3. Groups them by target page.
4. Asks the user to confirm the grouping if the routing is ambiguous.
5. Writes (or presents) the notes accordingly.

### Example 5: Housekeeping (move processed files)

**User (working in a chat on the Mac, after confirming several captures have been merged into their wiki pages):** *Tidy up raw/, the captures from last week have all been merged, move them to processed.*

Skill:
1. Confirms the vault is mounted at the canonical path.
2. Lists the files the user is referring to and reads back the names before moving, to make sure there's no ambiguity.
3. Creates `raw/processed/capture/` if it doesn't already exist.
4. `mv`s each file from `raw/` into `raw/processed/capture/`, preserving timestamps.
5. Confirms: *Moved N files to `raw/processed/capture/`: [list of slugs].*

Does not touch `Clippings/` in this pass, because the user only mentioned `raw/`. If the user wants those moved too, they can ask; the skill asks rather than guesses.

## What this skill does not do

- It does not edit any file under `wiki/`. Ever. That is the ingest pass's job.
- It does not create new wiki pages. If the material doesn't fit an existing page, flag it in `Suggested integration` and let the ingest pass decide.
- It does not perform the ingest pass itself, the step that reads `raw/` entries and merges their content into `wiki/` pages. Capture is upstream of ingest; they are deliberately separated so that capture can happen in any chat while ingest happens only in the dedicated wiki project.
- It does not modify files in `Clippings/`. Those are read by the ingest pass; this skill can only move them into `raw/processed/<source>/` after they have been merged, and only when explicitly asked.
- It does not store credentials, passwords, authentication tokens, or sensitive identification data, regardless of what the source exchange contains.
