# wiki-to-pdf: install and customisation

This skill renders any page in your Obsidian vault as a branded PDF (and accompanying HTML), using your colour palette, your typography, and your monogram or logo. The pipeline is markdown → HTML → WeasyPrint, with a Jinja2 cover template and a CSS-variable-driven brand stylesheet.

## Files in this folder

- `SKILL.md`, the skill's instruction file. Describes the trigger surface, content categories, variant rotation, cover archetypes, output naming, and the operation-log discipline.
- `template.html`, Jinja2 HTML template with cover and body sections.
- `brand.css`, brand stylesheet. Top of file declares CSS custom properties (`--brand-primary`, `--brand-secondary`, gradient stops, typeface, brand-mark path). The rest of the file references those variables, so changing them in one place re-skins every render.
- `render.py`, Python 3 entry point. Resolves the page, picks the cover variant, italicises wikilinks, renders to HTML and then to PDF via WeasyPrint, updates the rotation log, and appends a one-line entry to `wiki/log.md`.
- `README.md`, this file.

## Recommended workflow

**Run `design-your-brand` first.** That skill walks you through six short questions (primary colour, secondary colour, gradient, typography, monogram, save-and-apply) and writes the answers directly into this `brand.css` file's CSS variables, plus creates a `Brand Reference.md` page in your wiki documenting the choices. Once that's done, `wiki-to-pdf` produces output in your brand without any further setup.

You can also edit `brand.css` by hand. The variables at the top of the file are the only personalisation points; the rest of the stylesheet derives everything from them.

## One-time install

```
mkdir -p ~/.claude/skills/wiki-to-pdf
cp -R ./* ~/.claude/skills/wiki-to-pdf/
chmod +x ~/.claude/skills/wiki-to-pdf/render.py
```

Python dependencies:

```
pip install --break-system-packages weasyprint markdown jinja2 PyYAML pypdf
```

WeasyPrint needs three system libraries. On macOS, install them via Homebrew:

```
brew install cairo pango gdk-pixbuf libffi
```

## Customisation: the brand.css variables

The top of `brand.css` looks like this:

```css
:root {
    --brand-primary:          #1F3A68;   /* Replace with your primary brand colour */
    --brand-secondary:        #5A5A5A;   /* Replace with your secondary text colour */
    --brand-gradient-start:   #3F6FB1;   /* Replace with your gradient stop 1 */
    --brand-gradient-mid:     #1F3A68;   /* Replace with your gradient stop 2 */
    --brand-gradient-end:     #162E50;   /* Replace with your gradient stop 3 */
    --brand-body:             #2a2a2a;   /* Body copy near-black */
    --brand-font-family:      'Inter', 'Helvetica Neue', 'Arial', sans-serif;
    --brand-mark-path:        '../assets/monogram.png';
}
```

The defaults are deliberately neutral so the skill produces a professional-looking PDF out of the box. Once `design-your-brand` runs, these values get replaced with your choices.

## Brand-mark assets

The render script looks for cover monograms in this order:

1. `[Your Vault]/wiki/Brand Reference/assets/monogram/variations/<filename>`
2. `[Your Vault]/wiki/Brand Reference/assets/monogram/<filename>`
3. `[Your Vault]/wiki/Brand Reference/assets/<filename>`

And an inline page-header monogram (small, top-right of every body page) in this order:

1. `[Your Vault]/outputs/inline-monogram.png`
2. `[Your Vault]/wiki/Brand Reference/assets/monogram/monogram.png`
3. `[Your Vault]/wiki/Brand Reference/assets/monogram.png`

If you do not have a monogram yet, the skill still renders cleanly, it just omits the brand mark from the cover and the page header.

## Smoke test after install

From your vault root:

```
python3 ~/.claude/skills/wiki-to-pdf/render.py \
  --page "[Your Domain]" \
  --vault "[Your Vault]" \
  --output-dir "[Your Vault]/outputs"
```

The script prints a JSON line on success with the variant chosen, page count, and output paths.

You can also omit `--vault` if you run the script from inside your vault; the script walks upward looking for a `.obsidian/` folder. Alternatively set the `WIKI_TO_PDF_VAULT` environment variable.

## Calling from Claude

In normal use you do not run the script directly. You say something like "render [Your Domain] as a PDF" or "PDF up the latest session for [Recipient]", and Claude invokes the skill. The skill's `SKILL.md` walks Claude through resolving the page, picking the archetype and variant, and assembling the right command-line invocation.

## What it does

1. **Variant rotation** keyed to content category, with a recent-2 history per category to prevent same-category back-to-back repeats. Stored in `outputs/.wiki-to-pdf-history.json`. Pools are user-configurable; users with multiple monogram or logo variants can populate them via `design-your-brand` or by editing `VARIANT_POOLS` at the top of `render.py`.
2. **Wikilink italicisation** (`[[Page]]` → *Page*) so wiki internal links read cleanly in print.
3. **Cover archetype selection** (briefing / reference / default / no-cover) based on category and word count.
4. **Bundle mode** that pairs a synthesis page with its cluster-note subfolder, rendered as one continuous document.

See `SKILL.md` for the full convention.
