# Changelog

## v0.4 — 1 September 2026

The maintainer's operational layer, generalised. Everything below was built and battle-tested on the maintainer's live vault June-August 2026, then ported with all personal content stripped and vault-path detection generalised (`~/.config/moblee/vault-path`, written by the installer; `MOBLEE_VAULT` env override; walk-up fallback).

### Added

- **Brain skill v3** — from six patterns to eleven. New: `graduate` (promote/demote/close items between `_context.md` status tiers, every move logged), `ghost` (answer in the reconstructed voice of a persona the wiki documents deeply, always labelled), and the temporal trio `today` / `close-day` / `schedule` operating on a new **Daily Notes layer** (`Daily Notes/_TEMPLATE.md` added to the vault template; planning-only notes, workday-keyed closes, carry-forwards seeded into the next day's plan). `trace` gains the drift register (position shifts, not just coverage history).
- **Structural health layer.** `scripts/lint-v2.py` (mechanical convention checks: log-header timestamps, dangling wikilinks, broken section anchors including aliased links, attribution presence, a vault-weight guard with token caps on the always-loaded files); `skills/compact` (the guard's executor: mechanical rotations free, lossy trims on sign-off); `scripts/vault-gate.py` (a pre-commit gate running the cheap deterministic subset at write time — the installer wires it into `.git/hooks/pre-commit`). Checks referencing optional folders skip silently when the folder is absent.
- **Orient.** The `orient` session-start convention added to the template `CLAUDE.md`, with `scripts/vault-orient-preflight.sh` (Obsidian alive, file freshness, last commit, uncommitted count).
- **Dashboard** (`dashboard/`). A local web view of the vault: orientation state, inbox counts, an Ask box that runs Claude against the vault, a galaxy rebuild button, and a **config-driven Visuals tab** — charts are defined in `dashboard/dashboard-charts.json` (CSV-backed or built-in series), so "add a chart of X to my dashboard" is a one-line config edit Claude makes for you. Ships with a working wiki-growth example.
- **Wiki Galaxy** (`scripts/wiki-galaxy/`). The offline 3D knowledge-graph view, rebuilt fresh from the vault on demand into `outputs/galaxy/`.
- **Voice stack** (`voice/`, optional, macOS). Replies read aloud via a Stop hook; audible rotating nudges when Claude is waiting on input or a permission click. Free with the built-in macOS voice; add an ElevenLabs API key to the Keychain and the same stack upgrades itself. Control helper: `voice on | off | stop | last | full | say | paste | status` — `voice full` reads the latest reply in full. Installed by `voice/install-voice.py` (settings backed up, hooks never duplicated), offered by the main installer.
- Template `CLAUDE.md` gains sections carried from the live vault's evolution: the orient command, data-freshness convention for volatile figures, Daily Notes conventions, compaction discipline (fold-don't-append on `_context`, stratify reference detail out of CLAUDE.md), and the health-layer wiring.

### Changed

- `scripts/install.sh` copies the vault tooling into the new vault (`scripts/`, `dashboard/`), always records the vault path at `~/.config/moblee/vault-path`, installs the commit gate, and offers the voice stack on macOS.
- `docs/05-skills.md` rewritten for the eleven-pattern brain and the new compact skill.

### Not ported, deliberately

The maintainer's personal automations (scheduled news briefs, domain dashboards, semantic recall, cross-machine sync tooling) stay out: they are one person's assistant, not the pattern. The pattern is what ships.

### Migration

Existing installs keep working. To adopt v0.4 pieces on an existing vault: re-run `scripts/install-skills.sh` (updates brain, adds compact), copy `scripts/lint-v2.py`, `scripts/vault-gate.py`, `scripts/vault-orient-preflight.sh`, `scripts/wiki-galaxy/` and `dashboard/` into your vault, write your vault's path to `~/.config/moblee/vault-path`, create `Daily Notes/_TEMPLATE.md` from the template, and optionally run `voice/install-voice.py`.

## v0.3 — 5 June 2026

`wiki-to-pdf` rendering upgrades, ported from the maintainer's live skill and brand-abstracted so they are driven by your own `design-your-brand` settings.

### Added

- **CV / statement render style** (`--style cv`). A second, distinct visual language alongside the default brand template: no cover, no gradient bars, no monogram cover. An EB Garamond masthead, a brand-colour letter-spaced subtitle, a brand-colour rule, an EB Garamond lede, brand-colour uppercase section labels mapped from H2 headings, body copy in your brand typeface, and a single faint centred monogram watermark on every page (rendered only if a monogram is configured). New files: `skills/wiki-to-pdf/cv.css` and `skills/wiki-to-pdf/template-cv.html`.
- **Chart pre-rendering** in both styles. Fenced ` ```vega-lite ` (inline JSON) blocks render to inline SVG, and ` ```mermaid ` blocks render to an embedded PNG via the `mmdc` CLI. Both dependencies are optional (`pip install vl-convert-python`; `npm i -g @mermaid-js/mermaid-cli`); a missing dependency or a malformed block degrades to a small error box rather than failing the whole document.
- New `render.py` flags: `--style brand|cv`, `--subtitle`, `--watermark`, `--footer-label`, and `--no-charts`.

### Changed

- `skills/wiki-to-pdf/render.py` gained the `render_cv` path, the `pre_render_charts` step (wired into both render styles), and the `--style` dispatch in `main()`. The brand path is unchanged in behaviour.
- `skills/wiki-to-pdf/SKILL.md` documents the CV style, charts, and the new flags; the stale "WeasyPrint does not handle Mermaid" limitation was corrected.
- `skills/design-your-brand/SKILL.md` notes that the configured monogram doubles as the CV-style watermark.

### Brand abstraction

The CV style reads `--brand-primary`, `--brand-secondary`, `--brand-body`, and `--brand-font-family` from the same `brand.css` `:root` block that `design-your-brand` writes, so one brand setup drives both render styles. No maintainer-specific colours, fonts, or assets are baked in. The EB Garamond serif is the fixed signature of the statement style.

## v0.2 — 25 May 2026

Windows support added.

### Added

- `scripts/install.ps1` — PowerShell installer for Windows. Mirrors the bash `install.sh` step for step: collects user name, vault name, vault location; refuses to overwrite an existing directory; copies the vault template to the destination; substitutes `[Your Name]`, `[Your Vault Name]`, `[Your Vault]` placeholders; initialises git; optionally adds the `vault` function to the user's PowerShell profile.
- `scripts/vault.ps1` — PowerShell version of the session-start `vault` function. Reads the vault path from `$env:USERPROFILE\.config\moblee\vault-path`, auto-commits pending changes, shows recent git history, and confirms the vault is ready.
- `docs/01-prerequisites-windows.md` — Windows-specific prerequisites doc covering Obsidian for Windows, Git for Windows, claude.ai web chat (in place of Cowork), PowerShell 7, and a brief WSL2 alternative.
- `docs/02-install-windows.md` — Windows install walkthrough. Mirrors the structure of `02-install.md` (Mac) and covers the PowerShell execution-policy gate, post-install steps, Windows-specific quirks, and troubleshooting.
- `docs/07-windows-workflow.md` — Day-to-day Windows-track workflow document. Covers claude.ai web chat as the Claude interface, the manual ingest workflow that replaces Claude Code automation, manual workarounds for each of the four bundled skills (`brain`, `wiki-capture`, `wiki-to-pdf`, `design-your-brand`), and a note on cross-platform vault portability.
- `CHANGELOG.md` — this file. Records the v0.1 to v0.2 transition.

### Changed

- `README.md` — clarified that Moblee now supports Windows alongside Mac, with Mac as the default path and Windows as the manual-workflow alternative. Added Windows pointer to the prerequisites and install sections.
- `START_HERE.md` — extended the Claude briefing to recognise that the user may be on Mac or Windows, and to branch the install guidance accordingly. The platform-detection step is the new first thing Claude does in the conversation.
- `docs/00-overview.md` — added a one-paragraph note acknowledging the Windows track and pointing at the Windows-specific docs.

### Trade-offs documented in v0.2

The Windows track loses some automation relative to the Mac path. Captured explicitly so users can decide whether the trade-off suits them.

- **No Cowork.** The desktop Claude application is Mac-only. Windows users use claude.ai web chat as their Claude interface.
- **No Claude Code skills auto-load on the default Windows path.** Claude Code itself runs on Windows but is documented as advanced setup rather than the default. The four bundled skills (`brain`, `wiki-capture`, `wiki-to-pdf`, `design-your-brand`) target Claude Code on macOS in v0.2; manual workarounds for each are documented in `docs/07-windows-workflow.md`.
- **`wiki-to-pdf` is Mac-only in v0.2.** WeasyPrint dependencies on Windows are fiddlier than the Homebrew install on Mac. Windows users can render unbranded PDFs from Obsidian's built-in export.
- **Git commits are manual via the `vault` function plus a closing `git commit`.** The Mac path automates this through Claude Code; Windows users run the `vault` function at session start (auto-commits pending changes) and `git add . && git commit -m "..."` at session close.

These are the real costs of the Windows path. The benefit is that Windows users can build a working Karpathy-pattern wiki today without needing a Mac.

### Migration

Existing v0.1 installs on Mac continue to work without changes. No vault-template, skills, or Mac script content was modified for v0.2. The new files are Windows-specific additions only.

## v0.1 — 15 May 2026

Initial public release.

- Mac install path (`scripts/install.sh` and `scripts/install-skills.sh`).
- Vault template with `CLAUDE.md`, `Welcome.md`, the four canonical files (`wiki/Index.md`, `wiki/_context.md`, `wiki/log.md`), and methodology pages under `wiki/`.
- Four bundled Claude skills under `skills/`: `brain`, `wiki-capture`, `wiki-to-pdf`, `design-your-brand`.
- Documentation under `docs/`: overview, prerequisites, install, first conversation, first ingest, skills reference, Karpathy method explainer.
- `START_HERE.md` for one-paste Claude-guided setup.
- MIT license.

Shipped to Mubarak as the first user on 15 May 2026.
