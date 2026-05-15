# 05. The bundled skills

Moblee ships with four Claude skills, installed by `scripts/install-skills.sh` into `~/.claude/skills/`. Each skill is a folder containing a `SKILL.md` (the instructions Claude reads) plus any companion files. Claude auto-triggers the relevant skill from your natural-language phrasing; you never need to remember tool names.

This document is a quick reference for what each skill does, when to use it, and the trigger phrases that activate it.

## brain

**What it does.** Reflective queries against the wiki. Six patterns for asking your vault questions that draw across multiple pages and sources: trace (follow a thread of thought through the wiki), connect (find non-obvious links between two domains), emerge (surface what's been quietly accumulating), challenge (identify weak claims or under-evidenced sections), ideas (brainstorm new directions for an existing topic), synthesise (compress what's been said across many pages into a single coherent paragraph).

**When to use.** When you want to think with your wiki rather than just read it. Periodic queries against your accumulated material are how the system pays back the cost of ingest: the more you've put in, the more interesting the answers get.

**Trigger phrases.**

- "Trace how my notes on X evolved over time."
- "Connect what I think about X to what I think about Y."
- "What's quietly emerging in my wiki right now?"
- "Challenge my page on X; what's weakest?"
- "Give me five ideas to develop the X page further."
- "Synthesise what my wiki says about X into one paragraph."

The skill is read-only by default. If a query yields something worth keeping, it routes the save-back through `wiki-capture` rather than writing directly.

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
