# Skills bundle

This folder ships four Claude skills that pair with the Moblee vault template. Once installed, Claude (running in Claude Code or in Cowork with the vault mounted) picks them up automatically and invokes them when the user's natural-language phrasing matches their trigger surface.

## What's in the bundle

- **`brain/`**, reflective queries against the wiki. Six patterns (trace, connect, emerge, challenge, ideas, synthesise) for asking the wiki questions that draw across multiple pages and sources. Read-only; save-back is routed through `wiki-capture`.
- **`wiki-capture/`**, funnels knowledge from one-off Claude chats into the vault's `raw/` folder as well-formed capture notes for the next ingest pass. Direct-write when the vault is mounted, copy-paste artifact when it is not. Also handles housekeeping (`raw/` → `raw/processed/` moves) on explicit request.
- **`wiki-to-pdf/`**, renders any wiki page (and optionally its cluster notes) as a branded PDF. Markdown → HTML → WeasyPrint pipeline. Uses CSS custom properties so the brand is a one-place edit.
- **`design-your-brand/`**, short interview skill that captures the user's visual identity (colours, typography, monogram) and applies it to `wiki-to-pdf`. Run this first if you want the PDFs to be in your brand rather than the neutral default.

A fifth skill, `wiki-interview`, is reserved for a future addition. See `wiki-interview-PLACEHOLDER.md` for details.

## Recommended install order

1. Install all four skills (one shell command, below).
2. Install the WeasyPrint Python and system dependencies if you plan to use `wiki-to-pdf`.
3. Run `design-your-brand` once, in chat, to set up the brand.
4. Try `wiki-to-pdf` against any wiki page to confirm the brand applies.
5. Use `wiki-capture` and `brain` as needed during normal wiki work.

## One-line install

From the root of the Moblee bundle (the folder containing this `skills/` subdirectory):

```
mkdir -p ~/.claude/skills && cp -R skills/*/ ~/.claude/skills/
```

This creates `~/.claude/skills/brain/`, `~/.claude/skills/wiki-capture/`, `~/.claude/skills/wiki-to-pdf/`, and `~/.claude/skills/design-your-brand/`. Each folder contains the skill's `SKILL.md` and any companion files.

If you are installing the skills as part of running `install-skills.sh` from the Moblee bundle root, the script wires this same step plus the WeasyPrint dependency install.

## Dependencies for `wiki-to-pdf`

`wiki-to-pdf` needs Python 3 with WeasyPrint plus a few system libraries. On macOS:

```
pip install --break-system-packages weasyprint markdown jinja2 PyYAML pypdf
brew install cairo pango gdk-pixbuf libffi
```

See `wiki-to-pdf/README.md` for the full install detail.

The other three skills have no external dependencies; they use Claude's built-in file and shell tools.

## Verifying the install

In Claude Code, run `/skills` at the prompt. The four skills should appear in the list, each with its trigger surface as documented in its `SKILL.md`.

In Cowork, the skills appear automatically in the available-skills list at session start. Trigger one by phrasing a request that matches its description field, for instance "design my brand" for `design-your-brand`, or "PDF up [Your Domain]" for `wiki-to-pdf`.

## Customising the skills

Each `SKILL.md` is a markdown file under `~/.claude/skills/<skill-name>/`. Edit it to adjust trigger phrases, change defaults, or extend the workflow. The skills are deliberately readable and self-contained; you do not need to touch any other configuration to change behaviour.

`wiki-to-pdf/brand.css` is the one place the visual identity is configured. The CSS variables at the top of that file drive every colour, the typeface, and the brand-mark path; the rest of the stylesheet references those variables. `design-your-brand` writes here for you, but you can also edit by hand.

## Optional: future skills

- **`wiki-interview`**, walks the user through structured questions on a topic and writes the answers as a wiki page. Useful for onboarding when there is no source material to ingest yet. Not yet bundled; see `wiki-interview-PLACEHOLDER.md` for the staging path.
