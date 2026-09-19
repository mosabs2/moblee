#!/usr/bin/env python3
"""vault-gate.py — write-time commit gate for a Moblee wiki vault.

INSTALLATION
    This script runs as the git pre-commit hook of the vault's repository.
    The tracked hook at scripts/hooks/pre-commit calls it; the Moblee
    installer wires that folder in with

        git config core.hooksPath scripts/hooks

    To wire it by hand, run that command from the vault root (and make sure
    scripts/hooks/pre-commit is executable). core.hooksPath is local git
    configuration, so a vault synced to a second machine needs it set there
    too. Do not also copy the gate into .git/hooks/, or it runs twice.

WHAT IT DOES
    The periodic lint's detectors run days after an error lands; this gate
    runs the cheap, deterministic subset against the STAGED DIFF in under two
    seconds, so the commonest error classes are caught before the commit
    exists instead of at the next lint.

Checks (hard failures block the commit):
  G1  New log headers carry the mandatory `HH:MM ±TZ` tail.
  G2  No new log header (or staged `as of` line) is future-dated (> today+1).
  G3  Always-loaded files stay under their caps when staged
      (_context.md ≤ 12k tok, CLAUDE.md ≤ 10k, Index.md ≤ 8k; chars/4).
  G4  Newly added cluster notes carry a `Source:`/`Sources:` line
      (skipped when the vault has no `wiki/* Cluster Notes/` folders).
  G5  No staged non-restricted wiki page adds a wikilink into a restricted
      folder (wiki/Private/ or wiki/Ghost Reconstructions/, one-direction
      rule; skipped when the vault has no restricted folders;
      log/Context Archive/Index exempt as records).
  G6  Wikilinks ADDED by this commit to a wiki/ page resolve to a page that
      exists somewhere in the vault (Obsidian resolves by basename). The
      periodic lint finds dangling links days later; this catches them
      before the commit exists. Scoped to the staged diff, so pre-existing
      debt elsewhere never blocks a commit, and to wiki/ only: raw/ staging
      notes routinely name pages that do not exist yet. Exempt: file embeds
      (`![[...]]`), attachment links (.png, .pdf ...), memory-slug pointers,
      restricted folders, links inside code spans, and wiki/log.md (append-
      only, so a historical entry's link cannot be corrected). A link whose
      target is a folder rather than a page is advisory (W2), not blocking.
Advisory (printed, never blocks):
  W1  Superlative phrasing in added lines (first/largest/only/densest/
      on record ...) — grep the corpus before letting these stand.
  W2  Folder links added by this commit (target is a directory with no index
      page) — Obsidian will not resolve them, but they are a naming
      convention rather than a broken reference, so they never block.

Escape hatch for a deliberate exception: VAULT_GATE_SOFT=1 git commit ...
(reports everything, exits 0).
"""
from __future__ import annotations

import datetime
import os
import re
import subprocess
import sys
from pathlib import Path


def find_vault_root() -> Path:
    """Locate the vault: MOBLEE_VAULT env var, then ~/.config/moblee/vault-path,
    then walking up from the current working directory (a pre-commit hook runs
    at the repository root, so the walk-up finds the vault in normal use)."""
    # As a git hook, the gate must judge the repository the commit is happening
    # in, never a different vault recorded in the config file (an owner with two
    # vaults would otherwise have one gated against the other's files).
    git_dir = os.environ.get("GIT_DIR")
    if git_dir:
        p = Path(git_dir).resolve().parent
        if (p / "wiki" / "Index.md").is_file():
            return p
    cur = Path.cwd()
    for candidate in [cur, *cur.parents]:
        if (candidate / ".git").exists() and (candidate / "wiki" / "Index.md").is_file():
            return candidate
    env = os.environ.get("MOBLEE_VAULT")
    if env:
        p = Path(env).expanduser()
        if (p / "wiki" / "Index.md").is_file():
            return p
        print(
            "[gate] error: MOBLEE_VAULT is set to a path that is not a Moblee "
            f"vault (no wiki/Index.md at {env}). Fix or unset the variable.",
            file=sys.stderr,
        )
        sys.exit(1)
    cfg = Path.home() / ".config" / "moblee" / "vault-path"
    if cfg.is_file():
        try:
            recorded = cfg.read_text(encoding="utf-8").strip()
        except OSError:
            recorded = ""
        if recorded:
            p = Path(recorded).expanduser()
            if (p / "wiki" / "Index.md").is_file():
                return p
    cur = Path.cwd()
    for candidate in [cur, *cur.parents]:
        if (candidate / "wiki" / "Index.md").is_file():
            return candidate
    print(
        "[gate] error: could not find your wiki vault (no wiki/Index.md found "
        "via MOBLEE_VAULT, ~/.config/moblee/vault-path, or walking up from "
        f"{cur}). Run the commit from inside the vault, or set MOBLEE_VAULT.",
        file=sys.stderr,
    )
    sys.exit(1)


VAULT = find_vault_root()
CAPS = {"wiki/_context.md": 12000, "CLAUDE.md": 10000, "wiki/Index.md": 8000}
RESTRICTED_DIRS = ("wiki/Private/", "wiki/Ghost Reconstructions/")
EXEMPT_LINK_SOURCES = {"wiki/log.md", "wiki/Wiki Operations/Context Archive.md",
                       "wiki/Index.md", "wiki/_context.md"}
HEADER_FULL = re.compile(r"^## \[(\d{4}-\d{2}-\d{2}) (\d{2}):(\d{2}) ([^\]]+)\] .+\|")
HEADER_ANY = re.compile(r"^## \[(\d{4}-\d{2}-\d{2})([^\]]*)\] ")
SUPERLATIVE = re.compile(
    r"\b(first|largest|biggest|densest|smallest|longest|highest ever|lowest ever|on record|never before|the only)\b",
    re.IGNORECASE)
# Pages the pack itself installs. Their wording is the pack's, so a style advisory on
# them is noise the owner can do nothing about (an update printed ten at once in v0.5.1).
PACK_PAGES = {"wiki/Identity.md", "wiki/Wiki Operations/Moblee Learning Path.md"}  # exempt from W1 only in the commit that adds them
WIKILINK = re.compile(r"\[\[([^\]|#]+)(?:[|#][^\]]*)?\]\]")
# G6 link-resolution exemptions, kept in step with scripts/lint-v2.py.
ATTACHMENT_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".heic", ".pdf", ".excalidraw", ".canvas",
}
NON_PAGE_LINK_PREFIXES = ("reference-", "reference_", "feedback-", "feedback_", "project-", "memory/")
ANY_WIKILINK = re.compile(r"(!?)\[\[([^\]]+)\]\]")


def strip_code(text: str) -> str:
    """Blank fenced blocks and inline code spans; a [[link]] in backticks is syntax, not a reference."""
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    return re.sub(r"`[^`\n]*`", "", text)


def vault_page_names() -> tuple[set[str], set[str]]:
    """(markdown basenames, directory names) across the whole vault — Obsidian resolves by basename."""
    return ({q.stem for q in VAULT.rglob("*.md") if ".git" not in q.parts},
            {d.name for d in VAULT.rglob("*") if d.is_dir() and ".git" not in d.parts})


def cluster_folders() -> tuple[str, ...]:
    """Cluster-note folders actually present in this vault (may be empty)."""
    wiki = VAULT / "wiki"
    if not wiki.is_dir():
        return ()
    return tuple(
        f"wiki/{d.name}/" for d in sorted(wiki.iterdir())
        if d.is_dir() and d.name.endswith(" Cluster Notes")
    )


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(VAULT), *args],
                          capture_output=True, text=True).stdout


def staged_files() -> list[str]:
    return [f for f in git("diff", "--cached", "--name-only").splitlines() if f]


def added_lines(path: str) -> list[str]:
    out = git("diff", "--cached", "--unified=0", "--", path)
    return [l[1:] for l in out.splitlines()
            if l.startswith("+") and not l.startswith("+++")]


def restricted_stems() -> set[str]:
    stems = set()
    for d in RESTRICTED_DIRS:
        p = VAULT / d
        if p.is_dir():
            stems.update(f.stem for f in p.rglob("*.md"))
    # Folder-index stems are navigation, catalogued on Index by design.
    stems.discard("Ghost Reconstructions")
    stems.discard("Private")
    return stems


def main() -> int:
    files = staged_files()
    if not files:
        return 0
    hard: list[str] = []
    warn: list[str] = []
    today = datetime.date.today()
    limit = today + datetime.timedelta(days=1)

    # G1 + G2 — new log headers
    if "wiki/log.md" in files:
        for line in added_lines("wiki/log.md"):
            m = HEADER_ANY.match(line)
            if not m:
                continue
            if not HEADER_FULL.match(line):
                hard.append(f"G1 log header missing HH:MM ±TZ: {line[:90]}")
            try:
                d = datetime.date.fromisoformat(m.group(1))
                if d > limit:
                    hard.append(f"G2 future-dated log header ({d}): {line[:90]}")
            except ValueError:
                hard.append(f"G2 unparseable date in log header: {line[:90]}")

    # G2b — future 'as of' lines anywhere staged (cheap regex over added lines)
    asof = re.compile(r"[Aa]s of\s+(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})")
    months = {m.lower(): i for i, m in enumerate(
        ["January", "February", "March", "April", "May", "June", "July",
         "August", "September", "October", "November", "December"], 1)}
    for f in files:
        if not f.endswith(".md") or f == "wiki/log.md":
            continue
        for line in added_lines(f):
            for m in asof.finditer(line):
                mn = months.get(m.group(2).lower())
                if not mn:
                    continue
                try:
                    d = datetime.date(int(m.group(3)), mn, int(m.group(1)))
                except ValueError:
                    hard.append(f"G2 impossible as-of date in {f}: {m.group(0)!r}")
                    continue
                if d > limit:
                    hard.append(f"G2 future as-of date in {f}: {m.group(0)!r}")

    # G3 — caps on always-loaded files (only when staged)
    for rel, cap in CAPS.items():
        if rel in files:
            p = VAULT / rel
            if p.exists():
                tok = len(p.read_text(encoding="utf-8", errors="ignore")) // 4
                if tok > cap:
                    hard.append(f"G3 {rel} at ~{tok} tok, over its {cap} cap — fold or compact before committing")

    # G4 — new cluster notes need attribution (skipped if the vault has no
    # cluster-note folders yet)
    cluster_dirs = cluster_folders()
    if cluster_dirs:
        new_files = [f for f in git("diff", "--cached", "--name-only",
                                    "--diff-filter=A").splitlines() if f]
        index_stems = {Path(c).name.rstrip("/") for c in cluster_dirs}
        for f in new_files:
            if f.startswith(cluster_dirs) and f.endswith(".md"):
                if Path(f).stem in index_stems:
                    continue  # folder index page
                text = (VAULT / f).read_text(encoding="utf-8", errors="ignore") if (VAULT / f).exists() else ""
                if not re.search(r"(?mi)^#*\s*\**\s*sources?\b", text):
                    hard.append(f"G4 new cluster note without a Source line: {f}")

    # G5 — no new inbound links into restricted folders (skipped if the vault
    # has no restricted folders: restricted_stems() is empty then)
    stems = restricted_stems()
    if stems:
        for f in files:
            if not f.endswith(".md") or f in EXEMPT_LINK_SOURCES:
                continue
            if f.startswith(RESTRICTED_DIRS):
                continue
            for line in added_lines(f):
                for m in WIKILINK.finditer(line):
                    if m.group(1).strip() in stems:
                        hard.append(f"G5 {f} adds a link into a restricted folder: [[{m.group(1).strip()[:50]}]]")

    # G6 — wikilinks added by this commit must resolve. Scope: wiki/ only
    # (raw/ staging notes name target pages that may not exist yet, and
    # Clippings/ is source material). The log is exempt as append-only.
    link_files = [f for f in files
                  if f.endswith(".md")
                  and f.startswith("wiki/")
                  and f != "wiki/log.md"
                  and not f.startswith(RESTRICTED_DIRS)]
    if link_files:
        md_basenames, folder_names = vault_page_names()
        for f in link_files:
            for line in added_lines(f):
                for m in ANY_WIKILINK.finditer(strip_code(line)):
                    if m.group(1) == "!":          # file embed, not a page reference
                        continue
                    target = m.group(2).split("|")[0].split("#")[0].strip()
                    if target.endswith("\\"):     # table-escaped [[Page\|alias]]
                        target = target[:-1].strip()
                    if not target or target in md_basenames:
                        continue
                    if target.startswith(NON_PAGE_LINK_PREFIXES):
                        continue
                    if Path(target).suffix.lower() in ATTACHMENT_SUFFIXES:
                        continue
                    basename = target.split("/")[-1]
                    if basename in md_basenames:
                        continue
                    if basename in folder_names or target in folder_names:
                        if len(warn) < 10:
                            warn.append(f"W2 folder link (Obsidian will not resolve it) in {f}: [[{target[:50]}]]")
                        continue
                    hard.append(f"G6 {f} adds a link to a page that does not exist: [[{target[:60]}]]")

    newly_added = set(git("diff", "--cached", "--name-only", "--diff-filter=A").splitlines())
    # W1 — superlatives in added prose (advisory)
    # Scope: wiki/ only. raw/ and Clippings/ hold source material the user
    # dropped in and Claude must not rewrite, so flagging its wording is noise;
    # a first-time user adding "my first note" to raw/ should not be answered
    # with a style warning on their first commit.
    for f in files:
        if not f.endswith(".md"):
            continue
        if not f.startswith("wiki/"):
            continue
        if f in PACK_PAGES and f in newly_added:
            continue  # the pack's own first copy of the page (v0.5.2); later edits are checked as usual
        for line in added_lines(f):
            if line.lstrip().startswith(("#", "|")):
                continue
            sm = SUPERLATIVE.search(line)
            if sm and len(warn) < 10:
                warn.append(f"W1 superlative in {f}: …{line.strip()[max(sm.start()-30,0):sm.start()+60]}…")

    for w in warn:
        print(f"[gate advisory] {w}")
    if hard:
        for h in hard:
            print(f"[GATE] {h}", file=sys.stderr)
        if os.environ.get("VAULT_GATE_SOFT") == "1":
            print("[gate] VAULT_GATE_SOFT=1 — reporting only, commit allowed", file=sys.stderr)
            return 0
        print(f"[gate] {len(hard)} blocking issue(s) — fix and re-commit "
              "(deliberate exception: VAULT_GATE_SOFT=1 git commit …)", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
