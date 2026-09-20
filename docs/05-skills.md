# 05. The bundled skills

Moblee ships with its Claude skills installed by `scripts/install-skills.sh` into `~/.claude/skills/`. Each skill is a folder containing a `SKILL.md` (the instructions Claude reads) plus any supporting files. Claude auto-triggers the relevant skill from your natural-language phrasing; you never need to remember tool names.

## companion

**What it does.** Your standing guide to the wiki. From v0.8.1 it replaces the `get-started` skill, and the old phrases still work.

In a new wiki it holds the first conversation, one question at a time. It asks what you imagine putting in the wiki first, whether there is anything you want Claude to hold you to, and how you work: where your mail, calendar, notes and reminders live, what you read, watch and make, what you do over and over, and whether you would rather listen than read. It writes your answers on the `Habits and Tools` page, then helps you make your first page, which comes before any talk of extras. Only then does it propose one or two checklist items that clearly fit, each with its reason, time, space and cost. "Nothing extra for now" is a good answer and is recorded like any other.

On any later day, say "guide me" and it offers one next step, with the reason: something you agreed that is still waiting to be added, something you have now done by hand three times that an item would do for you, something you asked to be held to that is slipping, a part of the wiki you have not tried, or a small tool built for you. It offers one thing in a session unless you ask for more. A no is written down with the date and is not raised again for ninety days.

**Adding something.** What you agree is written on the `Habits and Tools` page under "Waiting in Moblee" and in a small file in your wiki, `.moblee/requests.json`, which the Moblee app reads. The item then waits as a tile in the app, and you press Add. If you installed from Terminal and have no app, Claude gives you one command to run in a Terminal window of your own. When you come back, Claude tests the item and records whether it is working.

**Made to measure.** When you need something no checklist item provides, the companion builds it small, inside your wiki, by the method in its own folder (`method.md` and `builders-rules.md`): notice the need, propose the smallest useful version, build it, prove it works in front of you, record it under "Made for the owner", and look at it again in a month. A page, a template or a script in the wiki's `scripts/` folder is made directly. A new skill is drafted under `made-for-you/skills/` in the wiki and reaches Claude through the app, like everything else that changes what Claude can do.

**How it talks.** Replies are two or three short lines, one question at a time, unless you ask for more or the `Habits and Tools` page says otherwise. Every correction you make to how Claude works ("shorter", "stop asking me that", "show me first") is written under "Working with the owner" on that page the moment you make it, in your words, and followed from then on.

**When something seems wrong.** It does not guess and does not start repairing. It runs the read-only check-up (`scripts/moblee-doctor.py`), matches what it shows to a numbered entry in its field guide (`field-guide.md`), and tells you in plain words what it is, what fixes it and who does the fix. If no entry fits, it offers to write a report you can send to whoever helps you with Moblee. `docs/11-the-app-and-the-companion.md` says more.

**Setup review.** When you ask, or when the weekly health check says one is due (more than ninety days since the last), it tells you in two or three sentences what your use looks like and asks, item by item, whether you want a change. Nothing is removed by Moblee.

**What it never does.** It never runs the installer, the updater or the checklist (the read-only `--check` and `--list` excepted), never copies anything into `~/.claude/`, and never edits Claude's settings. If you ask it to, it explains that these are yours to do in the Moblee app or in a Terminal window of your own. It never starts a conversation unasked, and it leaves any password, recovery phrase, card number or code it finds in your material out of the wiki and tells you.

**Trigger phrases.**

- "Get me started." / "Guide me."
- "What next?" / "What should I add?"
- "Review my setup."
- "Something is wrong." / "Run a check-up."
- "Can it do X every week?" / "I keep doing Y by hand."

## brain

**What it does.** Reflective queries against the wiki, plus your daily rhythm. Eleven patterns in three groups. Six analytical patterns ask your vault questions that draw across multiple pages: trace (follow a thread of thought or a position shift through the wiki), connect (find non-obvious links between two domains), emerge (surface what's been quietly accumulating), challenge (pressure-test a belief against the vault's own history), ideas (what should I work on next, judged against your active threads and inbox), synthesise (place a brand-new source into your existing corpus as a structured postscript). Two governance patterns: graduate (promote, demote or close items between the Active Threads / Open Decisions / Watch List tiers on `_context.md`, with every move logged) and ghost (answer a question in the reconstructed voice of a person your wiki documents deeply; it is always labelled as reconstruction, never invention). Three temporal patterns run your day against a `Daily Notes/` layer: today (a morning brief of your plan, due triggers and overnight activity), close-day (an end-of-workday reflection that writes the day's roll-up to the log and seeds tomorrow's plan with carry-forwards), and schedule (plan tomorrow, the week, or the run-up to a deadline into future daily notes, always proposed before written).

**When to use.** When you want to think with your wiki rather than just read it, and, with the temporal patterns, when you want the wiki to run the rhythm of your working day. The more you've put in, the more interesting the answers get.

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

**What it does.** Keeps the always-loaded files light. The programmatic lint's vault-weight guard flags files over their token caps (`_context.md`, `CLAUDE.md`, `Index.md`) but never trims; compact is the half that acts. The archive-only rotations (old refresh notes and closed items moved to a Context Archive page behind one-line pointers) run unattended, since nothing leaves the vault; anything that drops a line or moves a file is listed and confirmed with you first; lossy prose trims are proposed with before/after sizes and executed only on your explicit sign-off, with a reviewable git diff.

**When to use.** When the weekly lint flags a file over cap, or whenever Claude mentions the vault is getting heavy. "Compact the wiki", "trim _context", "the vault's heavy".

## galaxy

**What it does.** Rebuilds the offline 3D view of your knowledge graph (`scripts/wiki-galaxy/build.py`, output in `outputs/galaxy/`) fresh from the wiki, then opens it in your default browser. Pages are nodes, wikilinks are edges, folders become colour groups automatically. Read-only on `wiki/`.

**When to use.** Whenever you want to see the shape of what you have built, or to spot pages nothing links to (the build line counts pages with no links in or out; the health check's "orphans", pages nothing links to, are a different and stricter count). Worth waiting until there are a few dozen pages; a five-page galaxy is not much to look at.

**Trigger phrases.** "Galaxy." / "Open the galaxy." / "Show me my brain in 3D."

## wiki-interview

**What it does.** Conducts a structured interview with you on a subject only you can speak to (a person you knew, a project's history, a decision and why), then writes the page from your answers with your words preserved, cross-referencing names against the wiki before writing them, surfacing contradictions with what the vault already says rather than silently overwriting, and stripping anything sensitive.

**When to use.** When a page cannot be built from sources because you are the source. "Interview me on X." / "I want to add my own account of Y." / "Fill the gap on [page]."

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

Claude Code supports custom skills written by you. As your wiki matures and you find yourself wanting recurring workflows that the eight bundled skills don't cover, you can write your own. The skill format is documented at [docs.claude.com](https://docs.claude.com), and the existing skills in `~/.claude/skills/` serve as worked examples.
