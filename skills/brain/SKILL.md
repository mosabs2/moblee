---
name: brain
description: Run reflective queries against the user's personal Obsidian wiki, without writing to it. Trigger when the user wants substantive analytical output drawing across multiple wiki pages or sources. Six patterns: trace (how an idea has evolved over time), connect (bridges between two domains), emerge (latent themes the vault implies but never states), challenge (pressure-test a belief against the vault's history), ideas (vault-wide ideation against active threads and the watch list), and synthesise (place a new source into the existing corpus). Trigger on phrases like "trace X across my wiki", "how has X evolved", "connect X and Y", "bridge these domains", "what does my vault imply", "surface unstated patterns", "challenge my view that X", "pressure-test this against my wiki", "find counter-evidence", "give me ideas from my vault", "what should I work on next", "synthesise this against my wiki", "comparative postscript", or any clear variant. Operates read-only on wiki/, raw/processed/ and Clippings/processed/; never writes to wiki/ directly. Save-back is routed through the wiki-capture skill, which writes to raw/ for a later ingest pass. Uses obsidian-cli for link-graph queries when running in Claude Code; falls back to file-system reads (Grep, Read) when running in Cowork. Do not trigger on simple lookups, factual recall, or capture-only requests (those route to wiki-capture directly).
---

# Brain: reflective queries against the wiki

A skill for asking the wiki questions that draw across multiple pages and sources, rather than retrieving a single fact. Six patterns (trace, connect, emerge, challenge, ideas, synthesise) cover the reflective work the Karpathy LLM Wiki pattern grows into once the corpus has accumulated enough material to reflect on.

## Why this exists

The wiki's three core operations are ingest, query, and lint. Ingest writes new material in; query retrieves; lint health-checks. What is missing is the reflective layer, the patterns that take the corpus as it stands and produce analytical synthesis from it: how a position has evolved, what two domains share, what the vault implies but never says, where a stated belief contradicts the vault's own history.

Brain exposes six reflective patterns through natural-language triggering rather than a typed command vocabulary. The skill is deliberately read-only. It produces output in chat; if the user wants results saved back into the vault, the save passes through `wiki-capture`, which writes to `raw/` for a later ingest pass. This preserves the agent-versus-human zone separation: brain reflects, wiki-capture writes, the ingest pass integrates.

## The corpus

The vault lives at the user's configured vault path (typically `[Your Vault]/` on the user's Mac). Four locations are in scope, all read-only:

- **`wiki/`**, compiled wiki pages. The primary corpus.
- **`wiki/log.md`**, append-only chronology. Use this for absolute-time anchoring (`## [YYYY-MM-DD]` headers).
- **`raw/processed/`**, source material already merged into the wiki. Use to verify claims against original sources where needed.
- **`Clippings/processed/`**, Web Clipper articles already merged. Same use.

Three locations are deliberately out of scope by default:

- **`raw/`** (unprocessed), material the wiki has not yet adopted a view on. Querying this would mix the vault's own positions with material it has not yet integrated. The user can override by asking explicitly ("include unprocessed material").
- **`Clippings/`** (unprocessed), same reasoning.
- **Any one-time legacy notes import** (e.g. an Apple Notes inbox under `[Your Vault]/Apple Notes/`), out of scope unless the user explicitly invokes it.

The schema layer (`CLAUDE.md`, `wiki/_context.md`, `wiki/How to Use This Wiki.md`, `wiki/Karpathy LLM Wiki Pattern.md`) is read at session start but is not treated as analytical material; it is the rules and the state, not content to reflect on.

## When to use this skill

### Explicit triggers

Each pattern has its own trigger phrases, listed in its subsection below. The headline criterion is the affirmative one in the description field: the user wants substantive analytical output drawing across multiple wiki pages or sources. If a request can be satisfied by reading one page and quoting it, that is `query`, not `brain`. If it requires reading two or more pages and synthesising across them, this skill applies.

### Combined-pattern requests

Compound requests like "trace X then challenge it" or "connect A and B then run synthesise on the bridge" are natural and should be handled as sequential chains rather than fragmented into separate sessions. Run the first pattern to completion, present its output, then feed that output into the second pattern. The user is asking for one continuous piece of analysis, not two unrelated runs.

### Proactive offer (gentle)

After a substantive query response that has implicitly drawn across multiple pages, offer brain explicitly once at the end:

> *Want me to run a proper trace / connect / etc on this rather than just answer the surface question?*

The bar is the same as `wiki-capture`'s proactive offer: only when the response has already done analytical work that brain would do more thoroughly. Never offer twice in one chat if declined. Never offer for simple lookups, debugging, or chitchat.

## House style

All output follows the wiki's house style as recorded in `CLAUDE.md`. The points that matter most for brain output:

- **British English** throughout: colour, analyse, defence, behaviour, organisation. (Adjust to the user's preferred spelling convention if they have configured one.)
- **Analytical prose, not bullet lists.** Reflective output is by definition argumentative; it should read as paragraphs that develop a line of thought, with bolded inline labels where they help. Reserve bullet points for genuinely list-like content (dated chronology entries, candidate ideas, evidence lists).
- **No em dashes.** Use commas, semicolons, parentheses, or split sentences.
- **Absolute dates only.** "14 April 2026", never "last week" or "yesterday". When a wiki page uses relative dates, convert them.
- **No emojis.**
- **Quotations under fifteen words, only when exact wording matters, in quotation marks with attribution.** Otherwise paraphrase.
- **Cite with `[[Page Name]]` and section anchors `[[Page Name#Heading]]`.** For log entries, quote the `## [YYYY-MM-DD] ingest | …` header.
- **Verification rule.** Never invent. If the corpus does not say something, do not say it. Mark uncertainty `[Unverified]`.

## The six patterns

### trace: how an idea has evolved over time

Use when the user asks to follow a single concept, theme, or position through the wiki and see how it has changed.

**Trigger phrases:**

- "trace X across my wiki"
- "trace how X has evolved"
- "show me the history of X"
- "how have my views on X developed"
- "track X over time"
- "X timeline from the wiki"

**Workflow:**

1. Identify the target concept. If ambiguous (the term could mean several different things across the wiki), ask one focused clarifying question before proceeding.
2. Search the corpus for occurrences of the term and close synonyms. Use `obsidian-cli search` if available; otherwise `Grep` on `wiki/`, `raw/processed/` and `Clippings/processed/`.
3. Cross-reference each occurrence against `wiki/log.md` to anchor it in absolute time. The log's `## [YYYY-MM-DD]` headers are the canonical timestamp; page-internal dates come second.
4. Group hits into chronological buckets (typically by week or by analytical phase). Within each bucket, compress to one or two sentences naming what was claimed, who claimed it, and what changed from the previous bucket.
5. Close with a synthesis paragraph naming the arc: where the position started, the inflection points, where it stands now, and any active uncertainty (cross-reference the Watch list in `wiki/_context.md`).

**Output:** analytical prose with dated chronology and closing synthesis. 300 to 600 words for a single concept, up to 1000 if the arc spans many sources. Ends with the save-back offer.

**Default scope:** whole wiki.

**Example (generic):** following a single topic, say [your-topic], across the wiki from its first appearance to the present, surfacing the inflection points where the claim or position shifted.

### connect: bridges between two domains

Use when the user asks how two named domains, pages, or topics relate.

**Trigger phrases:**

- "connect X and Y"
- "what's the link between X and Y"
- "bridge these two"
- "find the overlap between X and Y"
- "compare these domains"
- "X meets Y in my wiki"

**Workflow:**

1. Identify the two targets. Both should map to existing wiki pages or sections; if one does not, propose the closest match and confirm before proceeding.
2. Read both target pages in full.
3. Walk one level of backlinks out from each via `obsidian-cli backlinks <page>` (Claude Code) or by searching for `[[Page]]` references (Cowork). The bridges are most often in the pages that link to both.
4. Identify shared entities (people, organisations, places), shared dates, shared sources, and thematic threads.
5. Rank bridges by non-obviousness. A bridge that surfaces a recurring person or recurring source across two apparently unrelated domains is high-value; a bridge that says "both pages mention oil" is not.

**Output:** structured synthesis naming each bridge with citations to both sides; 400 to 800 words. Flag any single-page bridge as a candidate for a reciprocal-backlink fix that the next lint pass should pick up.

**Default scope:** the two named pages plus their one-step backlink neighbourhoods.

**Example (generic):** identifying the people, sources or themes that recur across two top-level pages, for instance [Your Domain] and another domain, ranked by how non-obvious the bridge is.

### emerge: latent themes the vault implies but never states

Use when the user asks what the vault knows but has not yet named explicitly.

**Trigger phrases:**

- "what does my vault imply"
- "surface unstated patterns"
- "what's emerging across these pages"
- "what am I not yet seeing"
- "find latent themes"
- "what does the vault know that I haven't named"

**Workflow:**

1. Take a scope. Default: the last 30 days of `log.md`. The user may narrow ("emerge across two named domains only") or widen ("scan the whole vault").
2. Scan the scope for recurring concepts that appear in three or more pages without having their own page. The `obsidian-cli` graph queries help here in Claude Code; in Cowork, fall back to `Grep` for repeated proper nouns and noun phrases.
3. Weight candidates by recency (in-scope appearances in the last 30 days score higher) and cross-domain spread (a concept appearing in three different domains scores higher than one appearing three times in the same domain).
4. Filter: discard candidates that are already `[[Page Name]]` references, since those are already named.
5. Present the surviving candidates with evidence.

**Distinction from `ideas`:** emerge surfaces patterns that exist in the vault but have not been named (passive observation). `ideas` surfaces actions worth taking (active proposals). If the user is asking "what should I do", that is `ideas`. If asking "what is my vault telling me", that is `emerge`.

**Output:** 3 to 7 candidate patterns, each with 2 to 4 supporting citations and one sentence on why this is non-trivial. 500 to 1000 words. Ends with offer to promote any candidate to a new wiki page (routed through `wiki-capture`).

**Default scope:** last 30 days of `log.md`, all domains.

**Example (generic):** scanning the recent log for a recurring concept that has appeared in three different domains without yet having its own page, then proposing the page.

### challenge: pressure-test a belief against the vault's history

Use when the user asks the wiki to argue against a stated position.

**Trigger phrases:**

- "challenge my view that X"
- "pressure-test this"
- "what evidence contradicts X in my wiki"
- "find counter-evidence"
- "where am I wrong about X"
- "steel-man the opposite of X"

**Workflow:**

1. Locate the stated belief in the wiki, or accept it as given if the user has just stated it in chat.
2. Search the corpus for contradicting evidence. Look in: same-page revisions (older sections that say something different), related pages, source material in `raw/processed/`.
3. Identify prior position shifts using log timestamps. A claim made earlier in the year may have been qualified or reversed since; the log shows when.
4. Surface qualifying caveats, places where the wiki itself flags uncertainty (`[Unverified]` markers, lint-report findings).
5. Present a structured rebuttal.

**Output:** stated belief in one sentence; contradicting evidence with citations; prior shifts; residual uncertainty. 400 to 700 words. End with a verdict line: "The wiki strongly supports / partially supports / does not support this view, with [main caveat]."

**Default scope:** whole wiki, weighted toward recent material.

**Example (generic):** the user states a working assumption; brain searches the wiki for the strongest contradicting evidence and the moments when the user's own prior writing complicates the claim.

### ideas: vault-wide ideation against active threads and the watch list

Use when the user asks what to work on or where the live opportunities are.

**Trigger phrases:**

- "give me ideas from my vault"
- "what should I work on next"
- "vault-wide ideation"
- "surface project candidates"
- "what's interesting in my wiki right now"
- "ideas pass"

**Workflow:**

1. Read `wiki/_context.md` in full: active threads, open decisions, watch list, recent additions.
2. Scan the last 30 days of `log.md` for material the wiki has ingested but not yet integrated into a project or follow-up.
3. Cross-reference active threads against unprocessed `raw/` and `Clippings/` items (these *are* in scope for ideas, even though they are out of scope for trace and challenge; ideas wants to see the inbox).
4. Look for cross-domain intersections: where two active threads might combine, where a watch-list item has just landed in the inbox, where an open decision has fresh evidence.
5. Group candidates by horizon: immediate next session, medium term, speculative.

**Distinction from `emerge`:** see the emerge subsection above. ideas proposes actions; emerge surfaces patterns.

**Output:** 5 to 10 candidate ideas, each one paragraph with rationale and 1 to 3 wiki citations, grouped by horizon. 600 to 1000 words.

**Default scope:** `wiki/_context.md` plus last 30 days of `log.md` plus current `raw/` and `Clippings/` (ideas explicitly scans the inbox).

**Example (generic):** the user opens a session unsure what to pick up; brain reads `_context.md`, scans the inbox, and proposes one immediate-next-session candidate, two medium-term candidates, and one speculative candidate.

### synthesise: place a new source into the existing corpus

Use when a new source has been provided (in chat, in `raw/`, or in `Clippings/`) and the user wants a structured comparative reading against the existing wiki.

**Trigger phrases:**

- "synthesise this against my wiki"
- "cross-reference this new source"
- "place this in context"
- "fit this into the existing corpus"
- "comparative postscript"

**Workflow:**

1. Read the new source in full. If provided as a file path, read the file; if provided as a paste, work from the paste.
2. Identify the source's core claim, its author's perspective, and its relevance to existing wiki domains.
3. Search the corpus for related material via `obsidian-cli search` (Claude Code) or `Grep` (Cowork) on the source's key entities and concepts.
4. Walk one level of backlinks from the most relevant target page.
5. Produce a four-thread structure:
   1. **Personal connection.** Where the source's author or subjects appear elsewhere in the wiki, and what that vantage point adds.
   2. **Substantive connection.** Where the source's argument fits in the existing analytical clusters.
   3. **Historical pattern.** Where this source repeats or extends a pattern the wiki has already noticed.
   4. **Strategic implications.** What the source implies for active threads or watch-list items, with concrete tracking suggestions.

**Output:** structured postscript with four numbered subsections. 500 to 1500 words. Ends with offer to file as a postscript section on the relevant page (routed through `wiki-capture`).

**Default scope:** the new source plus the most relevant existing page plus its one-step backlink neighbourhood.

**Example (generic):** a new clipping lands in `Clippings/` on a topic the wiki already covers; brain produces a four-part postscript locating the new piece against the existing corpus.

## Reading the corpus

Before any pattern runs, detect the environment and pick the query path.

### In Claude Code (with `obsidian-cli`)

If the user has installed `obsidian-cli` on PATH (the standard install for Karpathy LLM Wiki users on a Mac), detect with:

```bash
which obsidian-cli
```

If present, prefer it for:

- **Backlink traversal:** `obsidian-cli backlinks "Page Name"` returns the list of pages that link to this one. Used by `connect`, `emerge`, `synthesise`.
- **Content search:** `obsidian-cli search "query"` returns matches across the vault, respecting wikilink structure. Used by all six patterns.
- **Page enumeration and graph queries** for cross-domain pattern detection in `emerge` and `ideas`.

Treat `obsidian-cli` as a shell command rather than a chained skill invocation; it is faster and the binary is on PATH already.

### In Cowork (without `obsidian-cli`)

The vault is mounted at the user's configured vault path in Cowork sessions. `obsidian-cli` is not on PATH in the Cowork sandbox.

Fall back to:

- `Grep` for content search across `wiki/`, `raw/processed/`, `Clippings/processed/`.
- `Read` for full-page reads.
- Manual `[[Page Name]]` reference scanning for backlinks.

When running without `obsidian-cli`, warn the user explicitly at the start of the response:

> *Running without `obsidian-cli` (Cowork environment); this is a flat-text scan, not a backlink-graph traversal, results may miss implicit cross-references that only the graph would surface.*

The warning matters most for `connect` and `emerge`, both of which depend on graph traversal. Trace, challenge, ideas, and synthesise are largely text-driven and degrade more gracefully.

## Output conventions

- **Open with the pattern name and target.** First line: "Trace of *[concept]* across the wiki" or "Connect: [[Page A]] and [[Page B]]" or similar.
- **Citations inline.** Every claim drawn from the wiki cites its page, ideally with a section anchor. Every dated claim cites the corresponding `## [YYYY-MM-DD]` log header.
- **Length targets per pattern** as listed in each subsection. Soft caps: if material genuinely warrants more, expand and say so.
- **Close with the save-back offer**, exactly one sentence, exactly once. Do not pester.

## Saving results back

Brain itself is read-only. The vault is never written to from inside this skill.

If the user accepts the save-back offer, brain composes the result as a `raw/` capture note in the format `wiki-capture` expects (title, target page, source context, content, suggested integration) and hands the composed note to `wiki-capture` for the actual write. The user can then ingest it on the next pass.

This preserves three things at once: the agent-versus-human zone-separation discipline; the `raw/` → ingest pass workflow that the rest of the wiki uses; and the testability of `wiki-capture` as the single write path into the vault.

If the user explicitly says "write it directly into [[Page]]", honour the request, but flag once that this bypasses the standard ingest pass and ask for confirmation.

## What this skill does not do

- It does not write to `wiki/` directly. Save-back is routed through `wiki-capture`.
- It does not perform `wiki-capture`'s job. If the user says "save this", "capture this", "log this", that is `wiki-capture`, not brain. Brain only handles save-back when it has just produced reflective output.
- It does not perform ingest. Ingest reads `raw/` and `Clippings/` and integrates into `wiki/`; brain reads the integrated layer (plus the `processed/` originals) and reflects on it.
- It does not perform lint. Lint is a structural health-check (contradictions, orphans, missing backlinks); brain is analytical synthesis. They share corpus-reading machinery but produce different output. If the user asks for "a lint pass", that is the wiki's separate lint operation.
- It does not run on raw or unprocessed material by default. The user can override.
- It does not invent. The verification rule applies: if the corpus does not say it, brain does not say it.
