# 06. The Karpathy method, explained for a beginner

If you've made it this far without reading Andrej Karpathy's April 2026 description of the LLM Wiki Pattern, this document fills in the methodology. It explains the "why" behind the system: why the wiki is shaped the way it is, why ingest looks the way it does, why the four-file separation matters, and why this whole approach tends to work better than the alternatives most people reach for first.

## The problem this solves

Knowledge work has a memory problem. You read a long article and finish it; six months later you remember vaguely that you read something on the topic but cannot find it or reconstruct the argument. You have a productive conversation with a colleague and lose the thread by the following week. You build up expertise in a domain through years of reading and meetings and projects, and that expertise lives only in your head, where it cannot be queried, shared, or audited.

The conventional fixes do not compose. Highlights in a Kindle app stay there. Quotes in a notes app pile up unsorted and unconnected. A journal grows linearly and is hostile to retrieval. A Notion database with categories and tags imposes structure too early, before you know what categories you'll actually want, and the structure tends to ossify rather than evolve. None of these scales over years.

The Karpathy pattern proposes a different shape: a wiki of interlinked markdown pages that you read and an LLM writes, with a structured ingest workflow that turns raw reading material into compiled, cross-referenced knowledge. The wiki accumulates over time. The cross-references form organically. The maintenance cost is near zero because the LLM does the maintenance.

## Two core insights

The pattern rests on two insights.

**The first insight: writing is the bottleneck.** If you had to maintain a wiki of your own knowledge by hand, you wouldn't. The cost of formatting, cross-linking, keeping a tone consistent, and not letting old pages drift is too high. Most people who try a personal wiki give up within months for exactly this reason. But if writing is delegated to an LLM that follows your conventions, the bottleneck disappears. The user only reads and approves; the LLM handles the upkeep.

**The second insight: the LLM needs a schema.** An LLM left to its own devices will not produce a coherent wiki; it'll improvise different formats on different pages, contradict itself, forget which page is canonical, and slowly degrade the corpus. The fix is a written schema: a `CLAUDE.md` at vault root that documents the conventions in detail (filename rules, link syntax, log format, house style, source attribution, ingest workflow, git workflow). The LLM reads `CLAUDE.md` at the start of every session and follows it consistently. The schema is what turns "an LLM and some markdown files" into "a maintainable knowledge system".

These two insights together are the whole thing. Everything else is design choices that follow from them.

## The shape of the system

From those two insights, the structure falls out.

**Plain markdown in a folder.** No proprietary database; otherwise you're locked in and the LLM can't operate on the files directly. Markdown is the lowest-friction format that supports headings, links, and structure.

**Three ownership layers.** Raw sources are immutable (you drop in, the LLM reads, nothing rewrites). The wiki is the LLM's to write (you read; the LLM writes). The schema is shared (you set conventions, the LLM follows them). The boundary between these layers is rigid because it's what keeps the system from drifting.

**Four canonical files, each with one role.** `CLAUDE.md` is the schema. `wiki/Index.md` is the navigation catalogue. `wiki/_context.md` is the working state. `wiki/log.md` is the chronological audit trail. Each file owns one role and does not duplicate the others. The discipline of keeping them separate is what makes the system queryable and auditable. If you fold the log onto Index ("I'll just keep a list of recent ingests on the front page") the Index loses its role as a navigation catalogue and gains the role of a stale chronology, and now neither file is doing its job well.

**Append-only logging.** The log is never reordered or rewritten. New entries go at the bottom. Old entries stay exactly as written. This makes the log an audit trail rather than a draft document; you can trust it as a historical record, and corrections are added as new entries rather than rewrites of old ones.

**Git underneath.** The whole vault is version-controlled. Every commit by Claude captures one unit of work atomically. If something goes wrong, git is the ultimate audit trail. If Claude misattributes a quote, the correction lives as a new entry in the log and a new commit in git; both audit trails reinforce each other.

## The ingest workflow, broken down

The ingest workflow has seven explicit steps. Each step has a reason.

**Step 1, read the source.** Obvious; the LLM needs to know what the source says before it can integrate the content.

**Step 2, update every relevant existing wiki page.** A single source typically touches five to fifteen pages: a domain page, an entity page, a methodology page, cross-references on adjacent topics. The LLM updates all of them. The reason this matters is that without this step, the wiki becomes a pile of one-off pages with weak cross-references; with this step, the wiki becomes a graph.

**Step 3, append a log entry.** The log is the chronology. Every ingest gets one entry. The entry says what was ingested, what pages were touched, what page was created if any.

**Step 4, touch the Index only when a new top-level page was created.** This is the rule that keeps the Index from drifting. Updates to existing pages do not change navigation; only new top-level pages do. So only those touch the Index.

**Step 5, refresh `_context.md` if the state moved.** If the ingest moves the state of an active thread or opens a new decision, the context file is updated. Otherwise it's left alone. The discipline here is that `_context.md` is the live working state, not a duplicate of the log.

**Step 6, move the source to `processed/`.** This is part of the ingest, not optional cleanup. After step 6, you can always tell which sources have been ingested (they're in `processed/`) and which are waiting (they're still in `raw/` or `Clippings/`). The discipline of moving rather than deleting preserves provenance.

**Step 7, commit to git.** One commit per unit of work, with a commit message that mirrors the log entry. The git history and the log together form the audit trail.

Each step has a job and the workflow does not skip steps. Skipping the move-to-processed makes the inbox confusing. Skipping the log entry breaks the chronology. Skipping the commit loses atomicity. The discipline of doing all seven on every ingest is what makes the system robust over years.

## Synthesis pages and cluster notes

One pattern worth calling out explicitly: how the wiki handles a topic that's accumulating many sources.

For the first three or four sources on a topic, the convention is to write directly into a single top-level page. Each ingest extends the page with new claims and new attribution lines. The page grows.

Past three or four sources, the page starts to feel crowded. At that point, the topic is promoted: a subfolder is created (`wiki/<Topic> Cluster Notes/`), each source gets its own page named in date-first form (`2026-04-25 Title, Publication.md`), and the original top-level page becomes synthesis only. The synthesis page now distils what the cluster notes collectively say, with a thematically-grouped index of links to the individual notes at the bottom.

This pattern is what lets the wiki scale. Without it, a topic page grows linearly with the source base and eventually becomes unreadable. With it, the synthesis stays compact and the detail is available one click away when you want it.

## Why this pays back over time

The system feels like overhead in week one. By month three, the cross-references start surprising you: a new article on stoicism connects to an old note from a parenting book; a quote you saved in March turns up as the missing piece in a project you started in May. By month twelve, the wiki is genuinely useful as a personal reference. By year two, it's an asset you would not want to lose.

The compounding works because the structure is right. Plain markdown is portable. Cross-references form a graph that gets richer with each ingest. The append-only log makes the history queryable. The four-file separation keeps each role doing its job. The LLM's job is to keep the conventions in place; the user's job is to read the world and drop sources in the inbox.

This is the whole method. The Moblee starter pack just gives you a clean implementation of it, with the schema written, the skills installed, and the install scripts ready to run.

## Further reading

The original April 2026 description of the pattern is in Andrej Karpathy's tweet and accompanying notes. The pattern has since been picked up and adapted by others, with variations on the schema and the skill bundle. The Moblee pack is one such adaptation, opinionated toward the practical needs of a new wiki author (a friendly `START_HERE.md`, install scripts that just work, four skills that cover the bulk of day-to-day operations).

For the practical day-to-day, see `wiki/How to Use This Wiki.md` inside your vault.
