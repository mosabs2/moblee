---
name: design-your-brand
description: Walk the user through defining their personal brand identity (colours, typography, monogram) and apply it across wiki-to-pdf renders. Use when the user wants to set up or refresh the visual identity their PDFs and branded reports will use, before running `wiki-to-pdf` for the first time, or when they want to update their brand defaults. Trigger phrases include "design my brand", "set up brand", "set up my brand", "choose my colours", "set my brand colours", "personalise the PDF output", "configure brand", "refresh my brand", and clear variants. Do not trigger on requests that ask Claude to *generate* a logo or *create* artwork, this skill captures choices and applies them; it does not produce visual assets from scratch.
---

# Design Your Brand

A short interview skill that captures the user's personal visual identity (primary colour, secondary colour, gradient, typography, optional monogram or logo) and writes the answers into two places:

1. A new or refreshed `wiki/Brand Reference.md` page in the user's vault, documenting the brand in human-readable form.
2. The CSS custom properties at the top of `~/.claude/skills/wiki-to-pdf/brand.css`, so every subsequent PDF renders in the new brand without further configuration.

The skill is conversational, not declarative. It works through six short stages, asking one question at a time and offering thoughtful defaults when the user has no strong preference.

## When to use

Run this skill when:

- The user has just installed `wiki-to-pdf` and wants their first render to be in their brand rather than the neutral default.
- The user wants to refresh an existing brand: a new primary colour, a different typeface, a new monogram file.
- The user explicitly asks ("design my brand", "set my brand colours", "personalise the PDF output").

Do not run this skill when:

- The user wants Claude to *invent* a logo or *generate* artwork. This skill captures choices; it does not produce visual assets. If the user has no monogram, the skill records that and the PDFs render without one.
- The user is mid-render and just wants to override the variant for a single document. That is `wiki-to-pdf`'s `--variant` flag, not a full brand refresh.

## The interview

The interview has six short stages. Move through them one at a time. After each answer, confirm what was captured before moving on. Keep the tone conversational; the user may not have a strong brand opinion and will appreciate sensible defaults.

### Stage 1: Primary colour

This is the colour used for headings, the brand bar at the top of every page, the cover title, and most accent elements. It is the single most visible brand decision.

Ask:

> *What's your primary brand colour? You can give me a name ("navy", "forest green", "burgundy"), a hex code (`#1F3A68`), or just say "no preference" and I'll suggest a default.*

If the user has no preference, suggest one of:

- A confident professional navy (`#1F3A68` or similar): reads as serious and well-suited to reference material.
- A muted forest green (`#2F5D4B`): warmer, less corporate.
- A burgundy (`#6B1F3A`): distinctive and works well with cream or warm-grey body text.

If the user names a colour but not a hex, propose a specific hex value ("By 'navy' I'll assume `#1F3A68`, a confident professional navy. Sound right, or do you want something deeper or lighter?") and capture the hex once confirmed.

Note that this colour will be used for headings, accents, brand bars, and the gradient (which is built from it by default).

### Stage 2: Secondary colour

The secondary colour is used for meta text: the date line, the footer page-title-and-date, the small-caps page header, body-meta strings. It should be a desaturated grey or warm-grey that recedes visually, leaving the primary colour and the body copy as the focal points.

Ask:

> *Secondary colour next, this is for meta text like dates and footers. Something quiet and grey. Default is `#5A5A5A`, a neutral medium grey. Override?*

Most users will accept the default. If they want a warmer feel, suggest a warm-grey like `#6E665F`; for a cooler feel, `#586068`.

### Stage 3: Gradient

The skill renders a thin gradient bar at the top of every cover page and every body page. By default the gradient is a three-stop transition built from the primary colour (slightly lighter on the left, primary in the middle, slightly darker on the right).

Ask:

> *Top of every page has a thin gradient bar, three stops, light to dark. By default I'll build it from your primary colour. Want me to do that, or specify your own three stops?*

If the user wants minimal brand, offer to skip the gradient ("If you'd rather have a single flat brand bar, I can drop the gradient and use the primary colour as a solid"). Capture that preference.

If the user specifies their own three stops, capture all three hex values.

If they accept the default, derive the start and end stops automatically: lighten the primary by roughly 25% for the start stop, darken by roughly 25% for the end stop. Use a colour-space-aware adjustment (HSL lightness shift is fine) and present the derived stops back for confirmation.

### Stage 4: Typography

The skill uses Inter by default, with a system-font fallback chain (`'Helvetica Neue', Arial, sans-serif`). Inter is a strong free default that reads cleanly in print and is available via Google Fonts.

Ask:

> *Typography. Default is Inter, which is a strong free choice that reads cleanly in print. You can also name another typeface (Helvetica Neue, Söhne, IBM Plex Sans, anything you have a licence for). If you name a non-free typeface, I'll set up the font stack so it falls back gracefully if the renderer can't find it.*

Capture the typeface name. If it is Inter or another Google Fonts family, keep the `@import` line at the top of `brand.css`. If it is a system or licensed typeface, comment out the `@import` line and adjust the font stack to put the chosen family first.

### Stage 5: Monogram or logo

This is the most optional stage. The skill can render PDFs with or without a brand mark.

Ask:

> *Last visual decision: do you have a personal monogram or logo? If yes, place the file (PNG or SVG) at `[Your Vault]/wiki/Brand Reference/assets/monogram.png` and I'll wire it up. If no, I'll skip, the PDFs render cleanly without one, just with the gradient bar and your primary colour doing the brand work.*

If the user says yes and the file is already in place, capture the filename. If the user has the file but it is somewhere else, ask them to copy it to the expected path (or offer to do it for them in a follow-up step).

If the user wants multiple variants (different finishes, light and dark versions, alternative cover marks), capture each one and tell them they can populate the per-category variant pools in `render.py` later: each pool is a Python list of filenames in the brand-mark folder, and the skill rotates through them per content category.

If the user has no monogram, do not offer to generate one. That is a separate creative task. Confirm that the brand will render without a monogram and move on.

The same monogram also serves as the faint centred watermark in `wiki-to-pdf`'s CV / statement style (`--style cv`). Nothing extra needs configuring: if a monogram is present it is used for both the brand-template cover and the CV watermark; if not, the CV style simply renders without a watermark.

### Stage 6: Save and apply

By this point the skill has captured:

- Primary colour (hex)
- Secondary colour (hex)
- Three gradient stops (hex × 3, or "single solid")
- Typeface family name and import strategy
- Monogram filename, or "none"

Before writing, present the full set back to the user one more time:

> *Here's what I've got. Primary `#XXXXXX`, secondary `#XXXXXX`, gradient from `#XXXXXX` through `#XXXXXX` to `#XXXXXX`, typeface [Brand Typeface], monogram at [path or "none"]. Shall I save?*

On confirmation, write to two places:

1. **`[Your Vault]/wiki/Brand Reference.md`**, a new top-level wiki page (or an update to the existing one) documenting the brand. Use this skeleton:

   ```markdown
   # Brand Reference

   **Last set:** YYYY-MM-DD

   ## Colour palette

   - **Primary:** `#XXXXXX` ([colour name])
   - **Secondary:** `#XXXXXX` ([colour name])
   - **Gradient stops:** `#XXXXXX` → `#XXXXXX` → `#XXXXXX`

   ## Typography

   [Brand Typeface], imported from [Google Fonts URL or "system fallback only"].

   ## Brand mark

   [Brand Mark Name] at `wiki/Brand Reference/assets/monogram.png`. (Or "No brand mark configured.")

   ## Where these values live

   These values are mirrored as CSS custom properties at the top of
   `~/.claude/skills/wiki-to-pdf/brand.css`. Edit either place to refresh
   the brand; the next `wiki-to-pdf` render picks up the new values
   automatically.

   ## Related pages

   - [[How to Use This Wiki]]
   ```

2. **`~/.claude/skills/wiki-to-pdf/brand.css`**, update the `:root` block at the top of the file to replace the default values with the user's. Preserve every other line in the file; only the variables and the `@import` line (if the typeface changed) should change. Use `Edit` rather than `Write` so the rest of the stylesheet is left untouched.

After saving, append a log entry to `wiki/log.md` in the standard form:

```
## [YYYY-MM-DD HH:MM ±TZ] schema | Brand reference set: design-your-brand
```

Then offer a single test render:

> *Want me to do a test render of one wiki page to confirm the brand applies correctly? Pick a page name and I'll run `wiki-to-pdf` on it.*

## Output

After the interview, the following are true:

- `wiki/Brand Reference.md` exists as a top-level wiki reference page.
- `~/.claude/skills/wiki-to-pdf/brand.css` carries the user's CSS variable values at the top.
- `wiki/log.md` has a one-line schema entry recording the brand setup.
- The next `wiki-to-pdf` render uses the new brand without further configuration.

## Re-running

The skill can be re-run any time to refresh the brand. On a re-run:

1. Detect the existing `wiki/Brand Reference.md` if present and read the current values.
2. Open the interview by showing the user the current settings and asking which stages they want to change.
3. Skip stages the user does not want to touch.
4. On save, overwrite only the changed values in `brand.css` (use `Edit` with `replace_all: false` on each variable line) and update `wiki/Brand Reference.md` with the new values plus an updated `Last set:` date.

If `wiki/Brand Reference.md` does not exist, treat the run as a first-time setup.

## House style for the Brand Reference page

The page itself follows the wiki's house style: British English, analytical prose where it makes sense, absolute dates, no em dashes, no emojis. The bullet-list usage in the skeleton above is appropriate because the brand reference is genuinely a list-like inventory of values, not flowing argumentation.

## Notes for Claude operating this skill

- **Be conversational.** The user may not have a strong brand opinion. Offer thoughtful defaults and move quickly through stages where the user has nothing to say.
- **Confirm before writing.** The save step touches two files; verify the captured values back before either edit.
- **Don't generate artwork.** If the user has no monogram, accept that and configure the PDFs to render without one. Generating logos or monograms is a separate creative task and not part of this skill.
- **Use `Edit` for brand.css, not `Write`.** The CSS file has structural content below the `:root` block that must be preserved. Only the values inside `:root` (and possibly the `@import` line) should change.
- **Verify the brand renders correctly.** After saving, offer a single test render of any wiki page to confirm the brand applies. If the test render produces unexpected colours (e.g. the user typed a hex with too few digits, or the typeface failed to load), surface the issue rather than burying it.
- **Update the log.** The schema entry on `wiki/log.md` is part of the operation, not optional.
- **Respect the user's pace.** A user who knows their brand can finish the interview in two minutes. A user starting from scratch may want to think for a few days between stages. Both are fine; the skill should not pressure the user to complete in one sitting.

## What this skill does not do

- It does not generate logos, monograms, or any visual artwork.
- It does not render PDFs itself; that is `wiki-to-pdf`'s job. This skill captures and applies the brand; `wiki-to-pdf` uses it.
- It does not modify the rendering pipeline or template structure. Only the CSS variables and (optionally) the `@import` line in `brand.css` are touched.
- It does not write to `wiki/` pages other than `wiki/Brand Reference.md` and a one-line log entry on `wiki/log.md`.
- It does not write secrets or sensitive values into the brand reference page. Brand assets are public-facing; if the user mentions any sensitive material in passing during the interview, exclude it from the saved page.
