# Changelog

## v0.5.0 — 16 September 2026

The safety release. It exists because a recipient's vault lost a folder the day after its first housekeeping run, and the review that followed found that the three things protecting the maintainer's own vault (a delete guard, a permission list, and a written identity for Claude) had never shipped: all three lived outside the vault, and the v0.4 port had taken the vault as the boundary of the pattern. The rule from here on: a recipient gets what the maintainer has, or the pack does not ship.

### Added

- **A safety layer, installed with the pack and not optional** (`safety/`). `bash-guard.py` runs before every shell command Claude composes and refuses deletion, history rewriting and force pushes however they are spelled, including the indirect forms; `install-safety.py` installs it, proves it fires with a blocked test command before registering it, backs up and parse-checks every settings file it touches, and merges the **starter permission rules** (`starter-permissions.json`: an allow list for routine work so the vault stops asking permission forty times an hour, and a deny ring for deletion and history rewriting). The allow list is safe only because the guard sits beneath it. If the safety layer fails to install, the installer stops.
- **`wiki/Identity.md`**, a fifth always-loaded file: who Claude is to the owner (verify rather than guess, challenge rather than flatter, never delete without a yes, the owner works through conversation). One list in it is the owner's own standing asks, filled in during the opening conversation (`START_HERE.md` step 8b). Excluded from skill reads and kept off the Index by design.
- **The never-delete hard rule and the plain-shell-command rule** in the template `CLAUDE.md`, first under Hard rules; `scripts/patch-claude-md.py` inserts them (and the identity and scheduled-lint lines) into an existing vault's `CLAUDE.md` at named anchors without replacing the file.
- **`scripts/update.sh`**: brings an existing vault to the current version without touching its content. There was no update path before v0.5; every earlier fix reached only fresh installs. Every replaced file is kept under `~/.config/moblee/backups/<stamp>/`; safe to run twice. `docs/08-updating.md`.
- **`VERSION`** in the pack and in every vault, so a census or an update can read what a vault runs.
- **Four starting memories** (`memory-seed/`, written by `scripts/seed-memory.py`): check the record before hedging, no superlatives without a count, plain English on housekeeping, plain shell commands.
- **The `galaxy` skill**, so "galaxy" rebuilds and opens the 3D graph; the builder had shipped since v0.4 with nothing to trigger it.
- **A weekly health check on a schedule** (`scripts/install-schedule.sh`, `scripts/cadence/`): the structural lint runs every Saturday at 09:04 through a launch agent, writing to `outputs/lint/`, logs kept under `~/.config/moblee/logs/` and archived rather than deleted after 90 days. The orient command reads the newest report. Offered at install and update.
- **`scripts/log-append.py`**, the one way a log entry is written: it reads the clock itself and emits the one correct header form, retiring hand-composed timestamps.
- **The commit gate wired through `scripts/hooks/`** and `git config core.hooksPath`, so the gate is versioned and updates reach it; nothing is written into `.git/hooks/` any more. Gate gains **G6**: a wikilink added to `wiki/` must resolve (folder links advisory).
- **Five more lint checks**, generalised: frontmatter schema (cluster notes, daily notes), duplicate frontmatter, session-metadata footers, prose boilerplate, skills-layer weight.
- **`clinic/`**: the maintainer's tools for looking after a vault remotely, by post: a clinic-note template, a checker that runs every command in a note through the guard, and the ten-point standard a note must pass before it is sent.
- `docs/08-updating.md` and `docs/09-safety.md`.

### Changed

- **`compact`** now lists what it would drop (aged tombstone lines) or move (`outputs/` root sweep) and asks before doing it; only the archive-only rotations run unattended.
- **The lint's `outputs/` size check** no longer mentions deletion; it suggests moving old renders into an `archive/` folder.
- **`install-skills.sh`** never deletes: a skill being replaced is moved to the backups folder. New `--update` mode for the updater.
- **The five shared skills brought level with their live originals**: brain's eight read-only / three narrow-writeback split and restricted-folder rules; wiki-to-pdf's mandatory output verification (exit 3 on a leaked marker), timestamped render log, canonical rotation log, non-Latin slug fallback, interpreter self-heal and `--font-scale`; wiki-capture's template, provenance footer and no-commit rule; wiki-interview's cross-reference, contradiction and sensitive-content rules.
- **`voice/README.md`** now says plainly that the waiting nudge works in the Terminal but not in the Claude desktop app, which does not send the signal it relies on.
- `START_HERE.md`, `README.md`, `docs/02-install.md` and `docs/05-skills.md` updated for all of the above.

### Found by an unanchored review before release, and fixed

A reviewer given the pack and none of the reasoning behind it was asked what a Claude with only this could still do wrong. Fixed before the release: the permission rules were written in a form (`///path`) that Claude Code may not match, so no allow or deny rule for reading and editing would have worked, and three `Bash(... scripts/:*)` rules required a space that the commands never contain, so every tooling run would have prompted (now `//path` and `Bash(python3:*)`, `Bash(bash:*)`, which are safe only because the guard reads script files); an install that failed at the safety step left a half-configured vault and told the owner to delete the folder to retry (the installer now hands an existing vault to the updater, and prints the exact re-run line); the updater committed the owner's own uncommitted work under its own message and reported a no-op as an update (it now commits only what it changed, and says "already at" when nothing is); the safety installer could print a Python traceback on an unusual settings shape after it had already copied the guard (it now checks the shape first and stops with one sentence); the commit gate consulted the recorded vault path before the repository it was running in, so an owner with two vaults would have had one gated against the other (repository first now); the vault shipped no `.gitignore`, so lint reports, editor state and caches were swept into every commit; and the docs claimed the guard "fails safe" (it fails open, deliberately, and now says so and why), that a delete needs "your explicit yes" (there is no yes; the owner removes things themselves), that the update "never touches `wiki/`" (it adds `Identity.md`), and that a missed Saturday runs later (it runs later only after sleep, not after a shutdown). The guard itself was rebuilt as **v4** against the reviewer's list, which had found that v3 read only the command line. v4 reads every script file a command would run (language-aware, so prose in a shell script's messages does not trip it) and code piped into a shell; bounds moves and copies to the vault and refuses a move over an existing file or into `/tmp`, the Trash or another volume; refuses a truncating `>` over a page, a source or `CLAUDE.md`; skips git's global options before reading the subcommand and adds the spellings that discard work (`stash`, `checkout` of an existing path, `reset --merge`/`--keep`, `reflog expire`, `gc --prune`, `branch -D`, `commit --amend`, a changed `core.hooksPath`); peels the wrappers (`sudo -u`, `nice`, `env`, `xargs` with any flags, `eval`, `!`, `{ }`, redirections before the head) and reads backticks as commands; knows the Mac's own deletion tools (`unlink`, `trash`, `truncate`, `rsync --delete`, `zip -m`, AppleScript's `delete`); allows deletes of throwaway files under `/tmp` and the caches when the path resolves, so tooling with a lock file still works; and recognises the pack's own tools by content hash (`safety/release-hashes.py` keeps the list current and `--check` gates a release), so an owner's Claude can run the updater and the safety installer even though those files contain the primitives. `safety/test-guard.py` holds the 416-case suite (286 blocked, 130 allowed, including 22 candidates deliberately left allowed so a change of mind shows as a diff); a run takes about 25 ms. Syntax checks (`bash -n`, `python3 -m py_compile`) count as reads, not runs. Two things an owner may notice: `git stash` and `git checkout` of a path that exists are refused (use a branch, or ask), and the guard cannot be upgraded or copied into `~/.claude/hooks/` through Claude, which is a Terminal job by design.

### Verified

Fresh install in a sandboxed home on a stock path (Python 3.9.6, Apple git), then a real v0.4.1 vault and a real v0.2 vault, each with the owner's own content, installed the same way and updated in place: 59 checks, all passing, including that re-running the installer on an existing vault finishes through the updater, that a fresh vault is git-clean when the installer ends, and that a v0.2 vault (no tooling, no orient section, no Daily Notes) comes out with all of them and its own pages untouched. Among them: the guard refuses `rm -rf` and `find -delete` from the sandbox and passes `mv`; settings files parse after the merge; the never-delete rule sits first under Hard rules; the old `.git/hooks/` gate is moved aside and `core.hooksPath` set; the owner's page survives the update untouched and their name reaches `Identity.md`; the gate blocks a dangling link in both vaults; the lint runs clean of errors in both; running the updater twice changes nothing. Every log read line by line as a recipient would read it.

## v0.4.2 — 11 September 2026

Three fixes found by installing the pack as a fourteen-year-old would: fresh clone, stock Mac, no Homebrew, no git experience. Every one of them is output that reads as failure at a moment when a beginner is deciding whether the thing works.

### Fixed

- **The optional PDF step failed twice on a stock Mac and printed two pages of usage text.** v0.4.1 resolved `pip3` correctly but passed `--break-system-packages`, an option that arrived in pip 23.0; macOS ships **pip 21.2.4**, which aborts with a usage dump on an unknown option. Both the primary and the fallback attempt failed this way before the calm recovery message was reached. The step now checks for Homebrew first and skips cleanly when it is absent, since the Python packages are useless without the system libraries underneath them; where Homebrew is present, the flag is probed for rather than assumed and the verbose output goes to a log rather than the screen.
- **The user's first real commit printed git's automatic-identity notice.** Nine lines about `git config --global --edit` and `git commit --amend --reset-author`, which read as an error to someone who has never used git. The installer now gives the new vault a repo-local identity from the name already collected at the first prompt. The user's global git config is untouched.
- **The commit gate ran its prose advisory over `raw/` and `Clippings/`.** Those folders hold source material the user drops in and Claude never rewrites, so flagging their wording is noise; the concrete symptom was a first commit of a file containing "my first note" answered with a superlative warning. The check is now scoped to `wiki/`, where the prose is Claude's own.

### Verified

Installed end to end three times in a sandboxed `HOME` on a stock `PATH`, with Homebrew and the user's dotfiles deliberately absent. Confirmed working from that environment: the installer, the skills installer, the six bundled skills, placeholder substitution, the orient preflight, `lint-v2.py`, the commit gate (both that it stays silent on `raw/` and that it still fires on `wiki/`), the galaxy build, and the dashboard serving on `127.0.0.1:7373`. The dashboard and galaxy need only the Python that macOS already ships.

## v0.4.1 — 4 September 2026

First-install fixes, found by running the installer as a fresh user on a stock Mac rather than on the maintainer's machine.

### Fixed

- **`install-skills.sh` called `pip`, which does not exist on a stock Mac.** macOS ships `pip3` at `/usr/bin/pip3` and no bare `pip`, so accepting the optional PDF-dependencies step ended a successful install with `pip: command not found` followed by a Homebrew warning — alarming output at the end of a run that had in fact worked. The script now resolves `pip3`, then `pip`, then falls back to `python3 -m pip --user`, and reports a calm, accurate message if none succeeds.
- **The optional PDF step now reads as optional.** It says plainly that skipping is safe, that nothing else depends on it, and that Claude can set it up on request the first time a PDF is wanted. The Homebrew-absent branch no longer reads as an error.

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
