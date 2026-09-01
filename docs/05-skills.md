# 05. The bundled skills

Moblee ships with its Claude skills installed by `scripts/install-skills.sh` into `~/.claude/skills/`. Each skill is a folder containing a `SKILL.md` (the instructions Claude reads) plus any companion files. Claude auto-triggers the relevant skill from your natural-language phrasing; you never need to remember tool names.

This document is a quick reference for what each skill does, when to use it, and the trigger phrases that activate it.

## brain

**What it does.** Reflective queries against the wiki, plus your daily rhythm. Eleven patterns in three groups. Six analytical patterns ask your vault questions that draw across multiple pages: trace (follow a thread of thought or a position shift through the wiki), connect (find non-obvious links between two domains), emerge (surface what's been quietly accumulating), challenge (pressure-test a belief against the vault's own history), ideas (what should I work on next, judged against your active threads and inbox), synthesise (place a brand-new source into your existing corpus as a structured postscript). Two governance patterns: graduate (promote, demote or close items between the Active Threads / Open Decisions / Watch List tiers on `_context.md`, with every move logged) and ghost (answer a question in the reconstructed voice of a person your wiki documents deeply — always labelled as reconstruction, never invention). Three temporal patterns run your day against a `Daily Notes/` layer: today (a morning brief of your plan, due triggers and overnight activity), close-day (an end-of-workday reflection that writes the day's roll-up to the log and seeds tomorrow's plan with carry-forwards), and schedule (plan tomorrow, the week, or the run-up to a deadline into future daily notes, always proposed before written).

**When to use.** When you want to think with your wiki rather than just read it — and, with the temporal patterns, when you want the wiki to run your working day's rhythm. The more you've put in, the more interesting the answers get.

**Trigger phrases.**

- "Trace how my notes on X evolved over time."
- "Connect what I think about X to what I think about Y."
- "What's quietly emerging in my wiki right now?"
- "Challenge my view that X."
- "What should I work on next?"
- "Synthesise this article against my wiki."
- "Promote X to active threads." / "Close the Y decision."
- "What would [person my wiki documents] say about X?"
- "Today." / "Close the day." / "Plan the week."

The analytical and ghost patterns are read-only; save-back routes through `wiki-capture`. Graduate, close-day and schedule have narrowly scoped writes (`_context.md` + log; daily-note frontmatter + log; future daily notes respectively) and nothing else.

## compact

**What it does.** Keeps the always-loaded files light. The programmatic lint's vault-weight guard flags files over their token caps (`_context.md`, `CLAUDE.md`, `Index.md`) but never trims; compact is the half that acts. Mechanical, reversible rotations (old refresh notes and closed items moved to a Context Archive page behind one-line pointers) run without asking; lossy prose trims are proposed with before/after sizes and executed only on your explicit sign-off, with a reviewable git diff.

**When to use.** When the weekly lint flags a file over cap, or whenever Claude mentions the vault is getting heavy. "Compact the wiki", "trim _context", "the vault's heavy".

## wiki-capture

**What it does.** Funnels knowledge out of a one-off Claude chat (Cowork, Claude Code, claude.ai) and into the vault's `raw/` folder as a well-formed capture note. The next ingest pass picks it up and writes it into the wiki proper.

**When to use.** Anytime you have a substantive Claude conversation and want to keep the result. The skill recognises common phrasings and packages the relevant turns into a capture note with the right frontmatter, a clean source attribution, and a hint for the next ingest about which wiki pages the capture is likely to touch.

**Trigger phrases.**

- "Save this to the wiki."
- "Capture this."
- "Log this."
- "Wiki this."
- "Add to my wiki."
- "Capture everything from this chat."

When the vault is mounted (Claude Code or Cowork with the folder mounted), the skill writes directly into `raw/<date>-<topic>.md`. When the vault is not mounted, it produces a copy-paste markdown artefact for you to paste in by hand.

It also handles light housekeeping on request: "move the processed files" or "tidy up raw" will move ingested files into the `raw/processed/` subfolder for you.

## wiki-to-pdf

**What it does.** Renders any wiki page (and optionally its cluster notes) as a branded PDF. The pipeline is markdown → HTML → WeasyPrint, with a Jinja2 cover template and a CSS-variable-driven brand stylesheet. The output is a print-quality PDF in your visual identity (or a neutral default if you haven't run `design-your-brand` yet).

**When to use.** When you want to share a wiki page outside the wiki: a one-pager for a colleague, a printed reference for the wall, a PDF brief for a meeting. The skill is also useful as a periodic export: rendering the major pages once a quarter gives you a tangible artefact of what the wiki has become.

**Trigger phrases.**

- "PDF up [page name]."
- "Render [page name] as a PDF."
- "Make a branded PDF of my [domain] page."
- "Export [page name] to PDF."

The skill chooses an appropriate cover variant based on the page's content category and rotates through cover styles over time so a series of renders looks varied rather than identical. Output lands in `outputs/<date>-<page-name>.pdf`, with a one-line entry appended to `wiki/log.md`.

**Dependencies.** WeasyPrint plus a few system libraries; see [01-prerequisites.md](01-prerequisites.md) or `wiki-to-pdf/README.md` in the bundle.

## design-your-brand

**What it does.** A short interview skill that captures your visual identity (primary colour, secondary colour, gradient stops, typography, monogram) and writes the answers directly into `wiki-to-pdf/brand.css`. Also creates a `wiki/Brand Reference.md` page in your vault documenting the choices and showing the result, so you can revisit your brand without trying to remember which hex codes you picked.

**When to use.** Once, near the start, after the install. The PDF renderer works without it (with neutral defaults), but the brand makes the output look like yours rather than generic. After the initial run, you can re-run any time to update.

**Trigger phrases.**

- "Design my brand."
- "Set up my visual identity."
- "Configure the PDF brand."

The interview is six short questions. Total time is usually under five minutes. You can skip any question and accept the default.

## A note on tool names

You never need to type the skill name. The skills are described to Claude with rich trigger surfaces, and Claude picks the right one from your phrasing. If a phrase doesn't trigger what you expected, just describe what you want in plain English and Claude will either route it correctly or ask a clarifying question.

If you want to inspect a skill, the files are at `~/.claude/skills/<name>/`. Each `SKILL.md` is readable markdown; edit it freely to change behaviour, add trigger phrases, or extend the workflow.

## Beyond the bundle

Claude Code supports custom skills written by you. As your wiki matures and you find yourself wanting recurring workflows that the four bundled skills don't cover, you can write your own. The skill format is documented at [docs.claude.com](https://docs.claude.com), and the existing skills in `~/.claude/skills/` serve as worked examples.

A future Moblee release may bundle additional skills (a `wiki-interview` for onboarding entire domains by interview, others as needs surface). For now, the four shipped here cover the bulk of what a new wiki author needs.
