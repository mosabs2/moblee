---
name: wiki-to-pdf
description: Render a wiki page (and optionally its cluster notes) from the user's Obsidian vault as a branded PDF, using the user's configured brand. Trigger when the user asks to "render", "export", "PDF", "print", "make a PDF of", or "produce a branded version of" a named wiki page; also trigger on phrases like "send me [[Page]] as a PDF", "PDF up [Your Domain]", "give me a branded version of this page", or any clear variant. Operates read-only on `wiki/`, writes the PDF and accompanying HTML into `outputs/`. Picks a cover variant from the user's brand library based on content category, with a rotation log so the same finish is not repeated back-to-back within a category. Defaults to page-only; bundles cluster notes only when the user explicitly says "with cluster notes" or "include cluster notes". Italicises wikilinks in body copy (drops the brackets, drops the link, no footnote). Do not trigger on simple read-only queries, on wiki-capture-shaped requests, on lint-shaped requests, or on save-back of chat content (those route to wiki-capture).
---

# wiki-to-pdf: render wiki pages as branded PDFs

> **Run `design-your-brand` first.** This skill renders wiki pages as PDFs using your brand assets (colour palette, typography, monogram or logo). Before using `wiki-to-pdf` for the first time, run the `design-your-brand` skill to define those assets. The defaults shipped in `brand.css` are deliberately neutral (navy heading, grey body, system-font fallback); the personalisation happens via CSS variables that `design-your-brand` will set for you.

A skill for producing a clean, consistent branded PDF from any page in the wiki. The rendering pipeline (markdown → HTML → WeasyPrint) is shared across all users; the cover and brand styling are driven entirely by your `brand.css` and your monogram or logo assets.

## Why this exists

Reusing a hand-built template for every render is slow and drifts. The skill captures the rendering convention, the rotation discipline across cover variants, the cover-archetype selection logic, and the wikilink italicisation rule, and leaves the user to invoke it by naming the page.

## When to use this skill

The description-field triggers cover the natural-language patterns. The skill also fires explicitly when invoked by name ("wiki-to-pdf...").

What this skill does NOT handle:

- **Save-back of chat content into the wiki.** That is wiki-capture's job.
- **Lint or housekeeping.** Goes to the lint operation.
- **Brain reflective queries.** Trace / connect / emerge / etc. route to brain. (If brain produces output the user wants as a PDF, save it back via wiki-capture first, then run wiki-to-pdf on the resulting page.)
- **Comparative analyses across sessions.** Bespoke outputs that are not page renders stay manual.

## The corpus

Read-only on the wiki; write-only into `outputs/`.

1. Source page: any markdown file under `wiki/`, identified by name or wikilink.
2. Brand assets: stored under the user's brand-assets folder, typically `wiki/Brand Reference/assets/` once the user has run `design-your-brand`. The monogram or logo file referenced by the `--brand-mark-path` CSS variable lives here.
3. Rotation log: `outputs/.wiki-to-pdf-history.json`, last two variants picked per content category. Created on first run.

## Inputs and the bundle question

By default the skill renders **the named page only**. If the user adds "with cluster notes", "include cluster notes", "and the cluster notes", or any clear variant, gather the synthesis page plus every markdown file in its associated cluster-note subfolder (e.g. `wiki/[Your Domain].md` plus everything in `wiki/[Your Domain] Cluster Notes/`). The bundle renders as one continuous document with the synthesis page first and the cluster notes appended in date-ascending order, each starting on a fresh page.

If the user names a page that is itself a cluster note (e.g. `wiki/[Your Domain] Cluster Notes/YYYY-MM-DD Title.md`), default to that single page even when the parent has a cluster.

## Content categories and variant pools

Each render picks a cover variant from a pool keyed to the content category. The category list and the variant filenames are user-defined and pluggable: the skill ships with a default category set that any wiki using the Karpathy pattern is likely to want, and the user populates each pool with their own brand-mark variants when they run `design-your-brand`.

The default categories are:

- **Briefings to specific people / coaching reviews / advisory.** Pages prepared for a named person, anything with a "Prepared for" framing. Pool: configurable; defaults to the user's canonical brand mark if no variants are defined.
- **Family / heritage / personal background.** Pages under or about Family History, Personal Background, biographical material.
- **Technology / projects / system architecture.** Pages under Technology Projects, system designs, the wiki's own schema pages.
- **Health & Medical.** Pages under Health & Medical.
- **Reference docs.** Pages flagged `status: reference` in frontmatter, plus the wiki's own How to Use This Wiki and Karpathy LLM Wiki Pattern pages.
- **General / fallback.** Anything else.

The user can add or remove categories to match their own top-level domains (for instance Golf, Geopolitics, Reading). The variant pool for each category is a list of filenames in the user's brand-mark folder; the canonical brand mark (the one named in the `--brand-mark-path` CSS variable) is always a safe fallback.

### Determining the category

Walk the inputs in this order, taking the first signal that resolves:

1. The page's frontmatter `parent` field. If parent is `[[Health & Medical]]`, category is Health & Medical. And so on.
2. The page's path. Anything under `wiki/[Your Domain] Sessions/` or `wiki/[Your Domain] Reference/` is the matching domain.
3. Frontmatter `status: reference` flips category to Reference docs regardless of parent.
4. Title or H1 keyword inspection as a last resort: words like "Briefing", "Review for", "Session review for" push to Briefings.
5. Fallback to General.

When a bundle is rendered (page plus cluster notes), categorise by the synthesis page only.

### Rotation discipline

`outputs/.wiki-to-pdf-history.json` keys each category to a rolling list of the most recent two variants used. On render, pick the next variant from the pool that is not in the recent-2 list. If all pool members are in the recent-2 list (only possible for two-element pools), pick the least-recent one. After render, prepend the chosen variant to that category's recent list and prune to length 2.

Schema:

```json
{
  "Briefings": [],
  "Family": [],
  "Technology": [],
  "Health": [],
  "Reference": [],
  "General": []
}
```

If the file does not exist, create it on the first render.

## Cover archetypes

The cover layout adapts to category and word count:

- **No-cover short.** Pages under roughly 500 words. Skip the cover entirely. Render directly into the body template; the gradient bar at the top is enough branding for a short note.
- **Briefing.** Briefings or coaching reviews to a named person. Cover carries an eyebrow line "[Brand Mark Name] · [Category]" plus a "Prepared for [Name]" line, the chosen variant centred at smaller scale, the page title, and a meta strip at the bottom (Prepared for / Report ID where applicable / Date).
- **Reference.** Pages with `status: reference` or in the Reference docs pool. Minimal cover with the page title set large in the brand primary colour, the chosen variant centred, no "Prepared for" line. If the document exceeds 2,000 words after the cover, prepend a single-page table of contents derived from H2 headings on page two.
- **Default.** Everything else. Gradient frame at the top, brand mark centred or top-third, page title beneath, brand-secondary subtitle line under the title (use the page's `summary:` frontmatter field if present, otherwise the first sentence of the page), date in a quiet meta line near the bottom.

The skill picks the archetype based on category plus word count, with a default fallback. Word count is the count of plain-text words after stripping markdown syntax and frontmatter.

## CV / statement style

A second render style, selected with `--style cv` (the default is `--style brand`, everything described above). The CV style is a different visual language, not a cover archetype: **no cover, no gradient bars, no monogram cover, no variant rotation**. Instead it is a single clean statement layout with an EB Garamond masthead, a brand-colour letter-spaced subtitle line, a brand-colour rule, an EB Garamond lede paragraph, brand-colour letter-spaced uppercase section labels mapped from the page's H2 headings, body copy in your brand typeface, and one faint centred monogram watermark repeated on every page (rendered only if you have a monogram configured; if not, the style renders cleanly without one).

It is brand-aware: the section labels, rule and subtitle take your `--brand-primary` colour and the body takes your `--brand-font-family`, both read from the same `brand.css` `:root` block that `design-your-brand` writes, so a single brand setup drives both render styles. The EB Garamond serif is the fixed signature of the statement style.

**How the mapping works.** The page's H1 becomes the masthead. The subtitle comes from `--subtitle`, else the page's `summary` frontmatter, else its first sentence (`--subtitle ""` suppresses it). The opening paragraph, if the body begins with one, is set as the lede. Each H2 becomes a section label; H3 becomes an EB Garamond sub-heading. Use it for CVs, statements, briefs, and any single-purpose document where a cover would be overkill. Trigger on "CV style", "statement style", "the watermark style", "the Garamond style", or any clear request to match that look.

## Charts (vega-lite and mermaid)

Fenced ` ```vega-lite ` (inline JSON) and ` ```mermaid ` blocks are pre-rendered to inline graphics before the markdown pass, in **both** render styles. Vega-Lite renders to inline SVG; Mermaid renders to an embedded PNG (via the `mmdc` CLI, because WeasyPrint strips Mermaid's HTML-mode SVG labels). Both dependencies are optional: vega-lite needs `pip install vl-convert-python`, mermaid needs `npm i -g @mermaid-js/mermaid-cli`. If a dependency is missing or a block fails to parse, only that block degrades to a small error box and the rest of the document still renders. Pass `--no-charts` to skip the pre-render and leave fenced blocks as plain code.

## Body conventions

The brand styling lives in `brand.css` and is driven by CSS custom properties at the top of that file. The structure carried across the template is:

- A4 page, 14mm top / 15mm side / 12mm bottom margins for body pages; 0 margins on the cover (the cover handles its own padding).
- `[Brand Typeface]` at the top of the HTML, with system-font fallback.
- Body text in `var(--brand-secondary)` for meta, near-black for body copy, `var(--brand-primary)` for headings and emphasis.
- A 1.4mm gradient bar at the top of every body page using `linear-gradient(135deg, var(--brand-gradient-start), var(--brand-primary), var(--brand-gradient-end))`.
- A header row with the page title in small caps grey on the left, an inline brand mark on the right, separated from the body by a 1.5px brand-primary rule.
- H2: brand primary, 600 weight. H3: brand primary, uppercase, letterspaced.
- A footer with the page title and date on the left, the page number in brand primary on the right, separated by a 1px gray rule.
- Tables get the dark brand header band and zebra rows.
- Block quotes (lede paragraphs) get the left brand rule plus pale-brand tint.
- Code blocks get a thin grey frame and a tabular monospace; keep them rare.

All colours, the typeface and the brand-mark path are CSS variables, changing them in `brand.css` (or running `design-your-brand`) is the one-place edit that re-skins every subsequent render.

## Wikilink rendering

Wikilinks become italics with the brackets and link removed. The visible text is whatever the wikilink would have shown:

- `[[Page]]` → *Page*
- `[[Page|Display]]` → *Display*
- `[[Page#Heading]]` → *Page* (drop the heading anchor)
- `[[Page#Heading|Display]]` → *Display*

No footnote. No hyperlink. No bracket. Italic only. Apply this conversion before passing the markdown to the renderer.

## House style

British English by default (adjust to the user's preferred spelling convention if they have configured one). No em dashes (use commas, semicolons, parentheses). No emojis. Quotations only when exact wording matters and the quote is under fifteen words; otherwise paraphrase. Absolute dates throughout. The page title in the cover and the body header is whatever the page's H1 says (not the filename).

## Output

Write two files into `outputs/`:

- `<slug>-<YYYY-MM-DD>.pdf`, the rendered PDF.
- `<slug>-<YYYY-MM-DD>.html`, the source HTML (kept alongside for debugging and re-render).

Slug is the page title lowercased, non-alphanumeric runs replaced by single hyphens, leading and trailing hyphens trimmed.

If the named page is a bundle (page plus cluster notes), the slug is the synthesis page's slug, with "-bundle" appended.

After a successful render, append a single line to `wiki/log.md` in the standard form:

```
## [YYYY-MM-DD] render | <Page Title>: wiki-to-pdf, <variant filename>, <archetype>, <pages> pp
```

The render log line is part of the operation, not optional. It mirrors the discipline used by ingest entries.

## How the render runs

1. Resolve the source: if the user quotes `[[Page]]`, look up the file by exact title under `wiki/`. If a path is named, use it. Confirm the file exists; if not, ask before guessing.
2. Detect bundle intent from the request phrasing.
3. Read the source markdown plus any cluster notes.
4. Strip frontmatter and remember the `parent`, `summary`, and `status` fields.
5. Determine category, archetype, and word count.
6. Read the rotation log; pick the variant.
7. Italicise wikilinks in the body markdown.
8. Pass through markdown rendering to HTML.
9. Compose the full HTML document by injecting the body HTML into the template at the staged `template.html`, with `brand.css` inlined.
10. Render to PDF using WeasyPrint. Save the HTML and PDF side-by-side under the slug-and-date filename in `outputs/`.
11. Update the rotation log.
12. Append the log line.
13. Confirm to the user: file path, variant chosen, page count, archetype.

## Tooling

The render script lives at `render.py` in the skill directory. It uses Python 3 with `weasyprint`, `markdown`, `jinja2`, `PyYAML`, and (optionally) `pypdf` for page counting. Install with:

```
pip install --break-system-packages weasyprint markdown jinja2 PyYAML pypdf
```

WeasyPrint also needs the system libraries `cairo`, `pango`, and `gdk-pixbuf`. On macOS these come in via Homebrew:

```
brew install cairo pango gdk-pixbuf libffi
```

The script can be invoked as:

```
python3 ~/.claude/skills/wiki-to-pdf/render.py \
  --page "[Your Domain]" \
  --vault "[Your Vault]" \
  --output-dir "[Your Vault]/outputs"
```

Optional flags:

- `--with-cluster-notes` to bundle.
- `--archetype briefing|reference|default|no-cover` to override automatic archetype selection.
- `--variant <filename>` to override automatic variant selection (does not touch the rotation log when overridden).
- `--prepared-for "Recipient Name"` for briefing covers.
- `--report-id "Some ID"` to populate a report-id meta block.

The skill calls the script under the hood. The user does not have to type the command; they name the page and the skill assembles the rest.

## Limitations and judgement calls

- The variant rotation only protects against same-category back-to-back repeats, not cross-category collisions. If two consecutive renders happen in different categories and both happen to pick the same variant, that is allowed; the rotation log is per-category by design.
- The category resolver is heuristic. If a page does not fit cleanly into one category, the resolver picks the first matching parent in the priority order above. To force a category, override with `--variant`.
- WeasyPrint renders most markdown features cleanly. Mermaid and Vega-Lite chart blocks are supported through the optional pre-render step (see "Charts" above); if their dependencies are not installed, those blocks degrade to a small error box and the rest of the document renders. HTML iframes are not supported.
- Bundles can grow long. A mature cluster-note collection can run to thirty-plus notes; expect 60+ pages of output and a few seconds of render time. The skill should not refuse, but should mention the page count in the confirmation.

## Examples

**Default render.** *User: "Render [Your Domain] as a PDF."* Skill loads the page, sees `status: reference`, picks Reference docs category and Reference archetype, picks the first variant from the pool (no rotation history yet), renders, saves to `outputs/[your-domain]-YYYY-MM-DD.pdf`, logs.

**Briefing.** *User: "PDF up the latest [your-topic] session for [Recipient]."* Skill resolves the latest matching page, detects "for [Recipient]" and the parent `[[Your Domain]]`, picks Briefings category, picks the first available variant from the Briefings pool, renders the Briefing archetype with "Prepared for [Recipient]" on the cover.

**Bundle.** *User: "Render [Your Domain] with cluster notes."* Skill loads `wiki/[Your Domain].md` plus every file under `wiki/[Your Domain] Cluster Notes/`, sorts the cluster notes by date-prefix ascending, renders one PDF with the synthesis first and the cluster notes appended, picks a domain-pool variant, slug ends in `-bundle`.

**Short note.** *User: "PDF the short reference note."* If the source is short (under 500 words), the skill skips the cover and renders body-only with the gradient bar.

## What this skill does not do

- Does not write to `wiki/` directly. The only wiki write is the one-line render entry on `wiki/log.md` per the operation discipline. It does not modify the source page.
- Does not regenerate cover images. It uses the existing files referenced from your brand-mark folder.
- Does not handle non-markdown sources. PDFs and images in `raw/processed/` are not in scope.
- Does not produce slide decks or Word documents. PDF only. PowerPoint output goes through the `pptx` skill; Word goes through `docx`.
