# Skills bundle

This folder ships eight Claude skills that pair with the Moblee vault template. Once installed, Claude (running in Claude Code or in Cowork with the vault mounted) picks them up automatically and invokes them when the user's natural-language phrasing matches their trigger surface.

## What's in the bundle

- **`brain/`**, reflective queries against the wiki. Eleven patterns: six analytical (trace, connect, emerge, challenge, ideas, synthesise), ghost (a wiki-documented persona's reconstructed voice), graduate (`_context.md` tier moves), and the daily rhythm of today, close-day and schedule over a `Daily Notes/` layer. Eight are read-only with save-back routed through `wiki-capture`; three have narrowly scoped writes.
- **`wiki-capture/`**, funnels knowledge from one-off Claude chats into the vault's `raw/` folder as well-formed capture notes for the next ingest pass. Direct-write when the vault is mounted, copy-paste artifact when it is not. Also handles housekeeping (`raw/` → `raw/processed/` moves) on explicit request. The blank note template lives in `wiki-capture/references/`.
- **`wiki-interview/`**, conducts a structured interview with the user on a topic that lives only in their head and writes the conversation up as a wiki page, with a cross-reference check before any named entity is written and a detect-surface-preserve rule for contradictions with existing pages.
- **`wiki-to-pdf/`**, renders any wiki page (and optionally its cluster notes) as a branded PDF. Markdown → HTML → WeasyPrint pipeline. Uses CSS custom properties so the brand is a one-place edit. Verifies its own output for leaked scaffolding before handing over.
- **`design-your-brand/`**, short interview skill that captures the user's visual identity (colours, typography, monogram) and applies it to `wiki-to-pdf`. Run this first if you want the PDFs to be in your brand rather than the neutral default.
- **`compact/`**, keeps the always-loaded files light. Acts on the lint's vault-weight flags: archive-only rotations run unattended, anything that drops a line or moves a file is listed and confirmed first, and lossy prose trims are proposed with before/after sizes and executed only on sign-off.
- **`companion/`**, the owner's standing guide, which replaces `get-started` from v0.8.1. It holds the first conversation in a new vault (how the owner works, then the first page, then one or two checklist items that fit), offers at most one next step in any later session, builds small made-to-measure tools by the method in its folder (`method.md`, `builders-rules.md`), runs the read-only check-up (`scripts/moblee-doctor.py`) against its `field-guide.md` when something seems wrong, and holds the setup reviews. It records what is agreed on `wiki/Wiki Operations/Habits and Tools.md` and in `.moblee/requests.json` in the vault, which the Moblee app reads; without the app it gives the owner a `moblee-setup.py --tick` command to run themselves. "Get me started", "guide me", "review my setup", "something is wrong". Never installs anything itself and never edits Claude's settings.
- **`galaxy/`**, rebuilds the offline 3D knowledge-graph view of the vault (`scripts/wiki-galaxy/build.py`, output in `outputs/galaxy/`) and opens it in the default browser. "Galaxy", "show me my brain in 3D". Read-only on `wiki/`.

## Recommended install order

1. Install all eight skills (one shell command, below).
2. Install the WeasyPrint Python and system dependencies if you plan to use `wiki-to-pdf`.
3. Run `design-your-brand` once, in chat, to set up the brand.
4. Try `wiki-to-pdf` against any wiki page to confirm the brand applies.
5. Use `wiki-capture` and `brain` as needed during normal wiki work; `compact` when the lint flags a heavy file; `galaxy` whenever you want to see the graph.

## One-line install

From the root of the Moblee bundle (the folder containing this `skills/` subdirectory):

```
mkdir -p ~/.claude/skills && cp -R skills/*/ ~/.claude/skills/
```

This creates one folder per skill under `~/.claude/skills/` (`brain/`, `wiki-capture/`, `wiki-interview/`, `wiki-to-pdf/`, `design-your-brand/`, `compact/`, `galaxy/`, `companion/`). Each folder contains the skill's `SKILL.md` and any supporting files. If an older `get-started/` folder is already there, `scripts/install-skills.sh` moves it to `~/.config/moblee/backups/` once `companion/` is installed (it is not deleted); the one-line copy above leaves it in place, which is harmless. The `galaxy` skill runs `scripts/wiki-galaxy/build.py` from inside the vault, which the main installer copies there; if you installed the skills alone, copy `scripts/wiki-galaxy/` into your vault's `scripts/` folder as well.

If you are installing the skills as part of running `install-skills.sh` from the Moblee bundle root, the script wires this same step plus the WeasyPrint dependency install.

## Dependencies for `wiki-to-pdf`

`wiki-to-pdf` needs Python 3 with WeasyPrint plus a few system libraries. On macOS:

```
pip install --break-system-packages weasyprint markdown jinja2 PyYAML pypdf
brew install cairo pango gdk-pixbuf libffi
```

See `wiki-to-pdf/README.md` for the full install detail.

The other skills have no external dependencies; they use Claude's built-in file and shell tools (`galaxy` needs only the Python 3 that macOS ships).

## Verifying the install

In Claude Code, run `/skills` at the prompt. The eight skills should appear in the list, each with its trigger surface as documented in its `SKILL.md`.

In Cowork, the skills appear automatically in the available-skills list at session start. Trigger one by phrasing a request that matches its description field, for instance "design my brand" for `design-your-brand`, or "PDF up [Your Domain]" for `wiki-to-pdf`.

## Customising the skills

Each `SKILL.md` is a markdown file under `~/.claude/skills/<skill-name>/`. Edit it to adjust trigger phrases, change defaults, or extend the workflow. The skills are deliberately readable and self-contained; you do not need to touch any other configuration to change behaviour.

`wiki-to-pdf/brand.css` is the one place the visual identity is configured. The CSS variables at the top of that file drive every colour, the typeface, and the brand-mark path; the rest of the stylesheet references those variables. `design-your-brand` writes here for you, but you can also edit by hand.
