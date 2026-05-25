# Changelog

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
