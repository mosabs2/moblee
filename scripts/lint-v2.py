#!/usr/bin/env python3
"""
lint-v2: structural-conventions verifier for a Moblee wiki vault.

Reads the vault, checks the structural schema conventions codified in the
vault's CLAUDE.md, and writes a markdown report to
outputs/lint/lint-v2-YYYY-MM-DD.md inside the vault.

Companion to the qualitative lint (which reads for contradictions, stale
claims, missing concepts, and data gaps — judgement calls a script cannot
make). This script does the things that are structural and scriptable:
log-header timestamps, append-only ordering, dangling wikilinks, broken
section anchors, orphan pages, source attribution, the token-budget
weight guard, and a handful of advisory sweeps.

Vault detection, in order of precedence:
  1. the MOBLEE_VAULT environment variable (absolute path to the vault);
  2. ~/.config/moblee/vault-path (a single line holding the absolute
     vault path — the Moblee installer writes this);
  3. walking up from the current working directory looking for a
     directory that contains wiki/Index.md.

Run from anywhere inside the vault:
    python3 scripts/lint-v2.py
Optional: --out <path> to override the dated default report path.
"""

from __future__ import annotations

import datetime
import os
import re
import sys
from pathlib import Path

try:
    import yaml  # type: ignore
    HAVE_YAML = True
except ImportError:
    HAVE_YAML = False


def find_vault_root() -> Path:
    """Locate the vault. See the module docstring for the precedence order."""
    env = os.environ.get("MOBLEE_VAULT")
    if env:
        p = Path(env).expanduser()
        if (p / "wiki" / "Index.md").is_file():
            return p
        print(
            "error: MOBLEE_VAULT is set to a path that is not a Moblee vault\n"
            f"  MOBLEE_VAULT = {env}\n"
            "  A vault is a folder containing wiki/Index.md. Fix or unset the variable.",
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
            print(
                f"note: {cfg} points at {recorded}, which is not a vault "
                "(no wiki/Index.md there); falling back to searching upward "
                "from the current directory.",
                file=sys.stderr,
            )
    cur = Path.cwd()
    for candidate in [cur, *cur.parents]:
        if (candidate / "wiki" / "Index.md").is_file():
            return candidate
    print(
        "error: could not find your wiki vault.\n"
        "  Tried, in order:\n"
        "  1. the MOBLEE_VAULT environment variable (not set);\n"
        f"  2. the path recorded in {cfg} (missing or invalid);\n"
        f"  3. walking up from {cur} looking for a folder containing wiki/Index.md.\n"
        "  Fix: run this from inside your vault, or set MOBLEE_VAULT to the "
        "vault's absolute path, or re-run the Moblee installer so it records "
        "the vault path.",
        file=sys.stderr,
    )
    sys.exit(1)


# Known-accepted append-only-protected log entries. The log is append-only by
# hard rule, so an entry flagged by the structural checks sometimes cannot be
# rewritten (a back-stamped entry recorded after a later-dated one, for
# example). Record such cases here — date, title prefix, and a one-line reason
# — and the checks will subtract them from the issue counts while still
# listing them in the report's "Known accepted exceptions" section for
# transparency. Keep the list short and reviewed at each lint pass: its
# purpose is to silence known carry-forwards, not to mask new drift.
LOG_TIMESTAMP_EXCEPTIONS: list[dict[str, str]] = [
    # {"date": "2027-01-01",
    #  "title_prefix": "ingest | Example title",
    #  "reason": "Back-stamped after a later-dated entry; append-only protected."},
]


def is_log_timestamp_exception(date: datetime.date, title: str) -> bool:
    for e in LOG_TIMESTAMP_EXCEPTIONS:
        if str(date) == e["date"] and title.startswith(e["title_prefix"]):
            return True
    return False


# Files that existed but could not be read this run. Reported as a loud
# finding at the end of main(): a check that ran over "" silently reports
# clean, which is the worst failure mode a linter has.
READ_FAILURES: list[str] = []


def page_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        if path.exists():
            READ_FAILURES.append(f"{path} ({e.__class__.__name__})")
        return ""


def read_frontmatter(path: Path) -> dict | None:
    """Extract YAML frontmatter from a markdown file. None if absent or malformed.

    Uses PyYAML when available; otherwise a minimal key: value parser that is
    good enough for presence checks (the only thing this lint needs).
    """
    text = page_text(path)
    if not text.startswith("---"):
        return None
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    if HAVE_YAML:
        try:
            return yaml.safe_load(parts[1]) or {}
        except yaml.YAMLError:
            return None
    fm: dict = {}
    for line in parts[1].splitlines():
        m = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if m:
            fm[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    return fm


def wikilink_targets(text: str) -> set[str]:
    """Return the set of basenames referenced as wikilinks in the given text."""
    targets: set[str] = set()
    for m in re.finditer(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]", text):
        raw = m.group(1).strip()
        basename = raw.split("/")[-1]
        targets.add(basename)
    return targets


def _strip_code_spans(text: str) -> str:
    """Blank out fenced blocks and inline code spans.

    A `[[wikilink]]` inside backticks is documentation of the syntax, not a
    live reference, and must not be counted by any link check.
    """
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    return re.sub(r"`[^`\n]*`", "", text)


# Restricted folders, if the vault owner adopts the pattern (private material,
# or AI voice-reconstructions, kept out of default reads and linked one
# direction only). Every check below that references these folders is
# conditional: a vault without them skips silently.
RESTRICTED_FOLDER_NAMES = ("Private", "Ghost Reconstructions")


def cluster_note_folders(vault: Path) -> list[Path]:
    """Folders following the cluster-notes pattern: wiki/<Topic> Cluster Notes/."""
    wiki = vault / "wiki"
    if not wiki.is_dir():
        return []
    return sorted(
        d for d in wiki.iterdir() if d.is_dir() and d.name.endswith(" Cluster Notes")
    )


# ---------------------------------------------------------------------------
# Cluster-note checks (conditional: skipped silently when the vault has no
# "* Cluster Notes" folders yet).
# ---------------------------------------------------------------------------


def check_cluster_note_coverage(vault: Path, findings: list[str]) -> tuple[int, int]:
    """Every cluster note must be wikilinked from its index: either the
    folder's own index page (wiki/<X> Cluster Notes/<X> Cluster Notes.md) or,
    failing that, the parent synthesis page (wiki/<X>.md)."""
    folders = cluster_note_folders(vault)
    if not folders:
        return (0, 0)
    passed = 0
    total = 0
    for folder in folders:
        index_page = folder / f"{folder.name}.md"
        parent_page = vault / "wiki" / f"{folder.name.removesuffix(' Cluster Notes')}.md"
        target = index_page if index_page.is_file() else parent_page
        if not target.is_file():
            findings.append(
                f"- **Cluster-note coverage ({folder.name})**: skipped — no folder "
                f"index page and no parent page `wiki/{parent_page.name}` to check against."
            )
            continue
        index_targets = wikilink_targets(page_text(target))
        missing: list[str] = []
        for f in sorted(folder.glob("*.md")):
            if f.stem == folder.name:  # the index page itself
                continue
            total += 1
            if f.stem in index_targets:
                passed += 1
            else:
                missing.append(f.stem)
        if missing:
            findings.append(
                f"- **Cluster-note coverage ({folder.name})**: **{len(missing)} note(s) missing** "
                f"from `{target.relative_to(vault)}`:"
            )
            for b in missing:
                findings.append(f"  - `{b}`")
        else:
            findings.append(
                f"- **Cluster-note coverage ({folder.name})**: all notes indexed on "
                f"`{target.relative_to(vault)}`. ✓"
            )
    return (passed, total)


def check_cluster_note_frontmatter(vault: Path, findings: list[str]) -> tuple[int, int]:
    """Each cluster note carries the canonical frontmatter (date, type, parent)."""
    folders = cluster_note_folders(vault)
    if not folders:
        return (0, 0)
    required = ["date", "type", "parent"]
    issues: list[str] = []
    total = 0
    for folder in folders:
        for f in sorted(folder.glob("*.md")):
            if f.stem == folder.name:  # folder index page is navigation, not an item
                continue
            total += 1
            fm = read_frontmatter(f)
            if fm is None:
                issues.append(f"`{f.relative_to(vault)}`: no frontmatter or malformed YAML")
                continue
            missing_fields = [k for k in required if k not in fm]
            if missing_fields:
                issues.append(
                    f"`{f.relative_to(vault)}`: missing fields → {', '.join(missing_fields)}"
                )
    if issues:
        findings.append(
            f"- **Cluster-note frontmatter**: {total - len(issues)}/{total} clean. "
            f"**{len(issues)} issue(s)**:"
        )
        for i in issues:
            findings.append(f"  - {i}")
    else:
        findings.append(
            f"- **Cluster-note frontmatter**: {total}/{total} notes carry the canonical schema (date, type, parent). ✓"
        )
    return (total - len(issues), total)


def check_attribution_lines(vault: Path, findings: list[str]) -> tuple[int, int]:
    """Every ingested source carries an attribution line. Checked where it is
    mechanically checkable: every cluster note must contain a `Source:` line."""
    folders = cluster_note_folders(vault)
    if not folders:
        return (0, 0)
    issues = []
    total = 0
    for folder in folders:
        for f in sorted(folder.glob("*.md")):
            if f.stem == folder.name:  # the folder index page is navigation, not a source
                continue
            total += 1
            if not re.search(r"(?mi)^#*\s*\**\s*sources?\b", page_text(f)):
                issues.append(f"`{f.relative_to(vault)}` — no `Source:`/`Sources:` attribution line")
    if issues:
        findings.append(
            f"- **Source attribution**: **{len(issues)} cluster note(s) without a `Source:` line**:"
        )
        for i in issues:
            findings.append(f"  - {i}")
    else:
        findings.append(f"- **Source attribution**: all {total} cluster notes carry a `Source:` line. ✓")
    return (total - len(issues), total)


# ---------------------------------------------------------------------------
# Index coverage
# ---------------------------------------------------------------------------


def check_index_domains_coverage(vault: Path, findings: list[str]) -> tuple[int, int]:
    """Every top-level wiki/*.md page (excluding infrastructure) must be
    wikilinked from Index.md."""
    wiki = vault / "wiki"
    index = wiki / "Index.md"
    if not index.exists():
        findings.append("- **Index.md Domains coverage**: skipped — Index.md missing.")
        return (0, 0)
    index_targets = wikilink_targets(page_text(index))
    infrastructure_exempt = {"Index", "log", "_context"}
    missing: list[str] = []
    total = 0
    for f in sorted(wiki.glob("*.md")):
        if f.stem in infrastructure_exempt:
            continue
        # Translation / snapshot pages that point at a canonical parent are
        # deliberately kept off the Domains list; exclude rather than force-index.
        fm = read_frontmatter(f) or {}
        type_val = str(fm.get("type", "")).strip().lower()
        status_val = str(fm.get("status", "")).strip().lower()
        if fm.get("parent") and (type_val == "translation" or status_val == "snapshot"):
            continue
        total += 1
        if f.stem not in index_targets:
            missing.append(f.stem)
    if missing:
        findings.append(
            f"- **Index.md Domains coverage**: {total - len(missing)}/{total} top-level pages indexed. **{len(missing)} missing**:"
        )
        for m in missing:
            findings.append(f"  - `{m}`")
    else:
        findings.append(f"- **Index.md Domains coverage**: {total}/{total} top-level pages indexed. ✓")
    return (total - len(missing), total)


# ---------------------------------------------------------------------------
# Log checks: header format and append-only ordering sanity
# ---------------------------------------------------------------------------


def check_log_timestamps(vault: Path, findings: list[str]) -> tuple[int, int]:
    """Log header format and ordering check.

    Every log entry header should read `## [YYYY-MM-DD HH:MM ±TZ] type | title`.
    The append-only rule allows correction or back-stamped entries that may be
    out of strict chronological order; genuine cases go on
    LOG_TIMESTAMP_EXCEPTIONS at the top of this file. The check enforces:
    (1) every parseable header carries the HH:MM ±TZ tail;
    (2) among consecutive entries that both carry a time and a parseable
        offset, UTC instants are non-decreasing (cross-timezone pairs are
        compared correctly rather than by local clock face);
    (3) otherwise, header dates are non-decreasing.
    The timezone tail tolerates bare offsets (`+03`), four-digit (`+0300`),
    labelled (`+01 BST`), and the bare labels `UTC` and `BST`.
    An empty log (no dated entries yet) passes.
    """
    log = vault / "wiki" / "log.md"
    if not log.exists():
        findings.append("- **Log timestamps**: skipped — log.md missing.")
        return (0, 0)
    text = page_text(log)
    entry_re = re.compile(
        r"^## \[(\d{4}-\d{2}-\d{2})(?: (\d{2}):(\d{2})(?: ([^\]]+))?)?\] (.+)$",
        re.MULTILINE,
    )
    offset_re = re.compile(r"^([+\-])(\d{2}):?(\d{2})?")

    def parse_offset_minutes(tz_blob: str | None) -> int | None:
        if not tz_blob:
            return None
        blob = tz_blob.strip()
        if blob.startswith("UTC"):
            return 0
        if blob.startswith("BST"):
            return 60
        m = offset_re.match(blob)
        if not m:
            return None
        sign = -1 if m.group(1) == "-" else 1
        return sign * (int(m.group(2)) * 60 + int(m.group(3) or 0))

    entries = []
    for m in entry_re.finditer(text):
        date_s, hh, mm, tz_blob, title = m.groups()
        try:
            d = datetime.date.fromisoformat(date_s)
        except ValueError:
            continue
        utc: datetime.datetime | None = None
        if hh and mm:
            try:
                local = datetime.datetime(d.year, d.month, d.day, int(hh), int(mm))
            except ValueError:
                local = None
            offset = parse_offset_minutes(tz_blob)
            if local is not None and offset is not None:
                utc = local - datetime.timedelta(minutes=offset)
        entries.append((d, utc, title.strip(), bool(hh and mm), tz_blob))
    total = len(entries)
    if total == 0:
        findings.append("- **Log timestamps**: no dated entries yet (new vault). ✓")
        return (1, 1)

    fmt_violations = []
    for d, utc, title, has_time, tz_blob in entries:
        bad = (not has_time) or (
            has_time and utc is None and parse_offset_minutes(tz_blob) is None
        )
        if bad:
            fmt_violations.append(f"`{title[:70]}` ({d}) — header lacks HH:MM ±TZ")
    if fmt_violations:
        findings.append(
            f"- **Log header format**: **{len(fmt_violations)} header(s) missing the HH:MM ±TZ tail**:"
        )
        for v in fmt_violations:
            findings.append(f"  - {v}")
    else:
        findings.append("- **Log header format**: all headers carry HH:MM ±TZ. ✓")

    out_of_order = []
    suppressed = 0
    for i in range(1, len(entries)):
        prev_d, prev_utc, prev_title = entries[i - 1][:3]
        curr_d, curr_utc, curr_title = entries[i][:3]
        if prev_utc and curr_utc:
            if curr_utc < prev_utc:
                if is_log_timestamp_exception(curr_d, curr_title):
                    suppressed += 1
                    continue
                out_of_order.append(
                    f"UTC instant out of order: `{curr_title[:60]}` ({curr_d}, {curr_utc:%H:%M} UTC) < prior `{prev_title[:60]}` ({prev_d}, {prev_utc:%H:%M} UTC)"
                )
        elif curr_d < prev_d:
            if is_log_timestamp_exception(curr_d, curr_title):
                suppressed += 1
                continue
            out_of_order.append(
                f"date out of order: `{curr_title[:60]}` ({curr_d}) < prior `{prev_title[:60]}` ({prev_d})"
            )
    exception_note = (
        f" ({suppressed} suppressed via Known accepted exceptions)" if suppressed else ""
    )
    if out_of_order:
        findings.append(
            f"- **Log timestamps**: {total} entries, **{len(out_of_order)} out-of-order**{exception_note}:"
        )
        for o in out_of_order:
            findings.append(f"  - {o}")
    else:
        findings.append(
            f"- **Log timestamps**: {total} entries, non-decreasing (UTC-normalised where offsets present){exception_note}. ✓"
        )
    return (total - len(out_of_order) - len(fmt_violations), total)


# ---------------------------------------------------------------------------
# outputs/ size guard (advisory)
# ---------------------------------------------------------------------------

OUTPUTS_SIZE_THRESHOLD_MB = 200


def check_outputs_size(vault: Path, findings: list[str]) -> tuple[int, int]:
    """Advisory size guard on outputs/.

    Reports total size; when the threshold is crossed, lists the largest
    render artefacts. STRICTLY ADVISORY: this check never deletes anything and
    must never be extended to delete anything — pruning happens only on the
    vault owner's explicit approval.
    """
    outputs = vault / "outputs"
    if not outputs.is_dir():
        findings.append("- **outputs/ size guard**: skipped — folder missing.")
        return (0, 0)
    files = [f for f in outputs.rglob("*") if f.is_file()]
    total_bytes = sum(f.stat().st_size for f in files)
    total_mb = total_bytes / (1024 * 1024)
    if total_mb <= OUTPUTS_SIZE_THRESHOLD_MB:
        findings.append(
            f"- **outputs/ size guard**: {total_mb:.0f} MB across {len(files)} files, under the {OUTPUTS_SIZE_THRESHOLD_MB} MB advisory threshold. ✓"
        )
        return (1, 1)
    largest = sorted(files, key=lambda f: f.stat().st_size, reverse=True)[:15]
    findings.append(
        f"- **outputs/ size guard**: **{total_mb:.0f} MB across {len(files)} files — over the {OUTPUTS_SIZE_THRESHOLD_MB} MB advisory threshold.** "
        "Everything in `outputs/` is an ephemeral render artefact (re-renderable on demand from the markdown sources), "
        "so pruning is safe in principle, but **nothing is deleted automatically and nothing should be deleted without the vault owner's explicit approval**. "
        "Options: (a) tell Claude which of the files below to remove and approve the proposed list before anything is touched; "
        "(b) delete manually in your file manager; (c) raise the threshold in `scripts/lint-v2.py` if the working set is legitimately larger now. The 15 largest:"
    )
    for f in largest:
        size_mb = f.stat().st_size / (1024 * 1024)
        age = datetime.date.fromtimestamp(f.stat().st_mtime).isoformat()
        findings.append(f"  - `{f.relative_to(vault)}` — {size_mb:.1f} MB, last modified {age}")
    return (0, 1)


# ---------------------------------------------------------------------------
# Vault weight (token-budget guard, advisory)
# ---------------------------------------------------------------------------

# Tokens are ESTIMATED as chars/4 — dependency-free and transparent, not a
# real tokenizer; the caps are set against that same estimate so the
# comparison is honest.
CHARS_PER_TOKEN = 4
CONTEXT_TOKEN_CAP = 12_000     # wiki/_context.md — loaded in full at every session start
INDEX_TOKEN_CAP = 8_000        # wiki/Index.md — a one-line-per-page catalogue by design
CLAUDE_MD_TOKEN_CAP = 10_000   # CLAUDE.md — schema, loaded every session
PAGE_TOKEN_FLAG = 25_000       # wiki pages — extraction-candidate threshold


def est_tokens(path: Path) -> int:
    """Rough token estimate (chars / 4). Not a tokenizer; deliberately simple."""
    try:
        return len(path.read_text(encoding="utf-8")) // CHARS_PER_TOKEN
    except OSError as e:
        if path.exists():
            READ_FAILURES.append(f"{path} ({e.__class__.__name__})")
        return 0


def check_vault_weight(vault: Path, findings: list[str]) -> tuple[int, int]:
    """Token-budget guard.

    Reports the weight of the always-loaded files against their caps and lists
    the pages over the extraction threshold, to feed the on-demand `compact`
    skill. STRICTLY ADVISORY: it never edits, trims, or deletes anything, and
    must never be extended to — compaction happens only in an on-demand
    `compact` pass with the vault owner's sign-off. Token counts are estimates.
    """
    findings.append("")
    findings.append("### Vault weight (token-budget guard, advisory)")
    findings.append(
        "Estimated tokens (chars/4). The always-loaded files are the per-session tax; "
        "this guard feeds the on-demand `compact` skill and never trims anything itself."
    )

    capped = [
        ("wiki/_context.md", CONTEXT_TOKEN_CAP, "loaded in full at every session start"),
        ("wiki/Index.md", INDEX_TOKEN_CAP, "one-line-per-page catalogue by design"),
        ("CLAUDE.md", CLAUDE_MD_TOKEN_CAP, "schema, loaded every session"),
    ]
    passed = 0
    total = 0
    for rel, cap, note in capped:
        p = vault / rel
        if not p.is_file():
            findings.append(f"- `{rel}`: skipped — file missing.")
            continue
        total += 1
        tok = est_tokens(p)
        if tok <= cap:
            passed += 1
            findings.append(f"- `{rel}`: ~{tok:,} tok, under the {cap:,} cap ({note}). ✓")
        else:
            findings.append(
                f"- `{rel}`: **~{tok:,} tok, over the {cap:,} cap** ({note}). "
                "Compaction candidate — run the `compact` skill."
            )

    wiki = vault / "wiki"
    big: list[tuple[str, int]] = []
    if wiki.is_dir():
        for f in wiki.glob("*.md"):
            if f.name in ("log.md", "_context.md", "Index.md"):
                continue
            tok = est_tokens(f)
            if tok > PAGE_TOKEN_FLAG:
                big.append((f.name, tok))
    big.sort(key=lambda x: x[1], reverse=True)
    if big:
        findings.append(
            f"- **{len(big)} top-level page(s) over the {PAGE_TOKEN_FLAG:,}-tok extraction threshold** "
            "(cluster-note / subfolder extraction candidates, stub-plus-link; advisory):"
        )
        for name, tok in big:
            findings.append(f"  - `wiki/{name}` — ~{tok:,} tok")
    else:
        findings.append(f"- No top-level page over the {PAGE_TOKEN_FLAG:,}-tok extraction threshold. ✓")

    # Subfolder pages over the same threshold. By-design heavy populations are
    # excluded: log-archive/ (annual rollovers) and the Context Archive (cold
    # storage, read only via wikilink).
    big_sub: list[tuple[str, int]] = []
    if wiki.is_dir():
        for f in wiki.glob("*/**/*.md"):
            rel = f.relative_to(wiki).as_posix()
            top = rel.split("/", 1)[0]
            if top == "log-archive":
                continue
            if rel == "Wiki Operations/Context Archive.md":
                continue
            tok = est_tokens(f)
            if tok > PAGE_TOKEN_FLAG:
                big_sub.append((rel, tok))
    big_sub.sort(key=lambda x: x[1], reverse=True)
    if big_sub:
        findings.append(
            f"- **{len(big_sub)} subfolder page(s) over the {PAGE_TOKEN_FLAG:,}-tok extraction threshold** "
            "(same advisory as above; log-archive and Context Archive excluded by design):"
        )
        for rel, tok in big_sub:
            findings.append(f"  - `wiki/{rel}` — ~{tok:,} tok")
    else:
        findings.append(
            f"- No subfolder page over the {PAGE_TOKEN_FLAG:,}-tok extraction threshold "
            "(log-archive and Context Archive excluded by design). ✓"
        )

    log = wiki / "log.md"
    if log.is_file():
        findings.append(
            f"- `wiki/log.md`: ~{est_tokens(log):,} tok (append-only, tailed not loaded; "
            "an annual rollover to `wiki/log-archive/` keeps the per-session cost bounded). Advisory only."
        )

    heavy = check_context_item_weight(vault, findings)
    passed += 1 if not heavy else 0
    total += 1

    return (passed, total)


# Per-item weight guard on _context.md.
#
# The file-level cap above only fires once _context is ALREADY over budget, by
# which point the fix is a large multi-item compaction pass. The actual
# failure mode is per item: an ingest appends a dated update to a watch item
# instead of folding the superseded state into current state, and the item
# quietly quadruples. This guard names the specific items to fold while each
# is still one item. STRICTLY ADVISORY: it never edits anything.
CONTEXT_ITEM_CHAR_BUDGET = 3_000   # a single Active-thread / Watch-list entry
CONTEXT_ITEM_HARD_FLAG = 4_000     # egregious; fold at the next pass


def check_context_item_weight(vault: Path, findings: list[str]) -> list[tuple[int, int, str]]:
    """List individual _context.md items over the per-item character budget."""
    path = vault / "wiki" / "_context.md"
    if not path.is_file():
        return []

    heavy: list[tuple[int, int, str]] = []
    in_scope = False
    for lineno, line in enumerate(page_text(path).split("\n"), 1):
        if line.startswith("## "):
            in_scope = line.strip() in ("## Active threads", "## Watch list")
            continue
        if not in_scope or not line.startswith("- "):
            continue
        if line.startswith("- ~~"):   # closed tombstone; the drift guard owns those
            continue
        if len(line) > CONTEXT_ITEM_CHAR_BUDGET:
            m = re.match(r"- \*\*(.+?)\*\*", line)
            title = m.group(1) if m else line[2:70]
            heavy.append((len(line), lineno, title))

    if not heavy:
        findings.append(
            f"- No `_context.md` item over the {CONTEXT_ITEM_CHAR_BUDGET:,}-char "
            "per-item budget (the fold-discipline guard). ✓"
        )
        return []

    heavy.sort(reverse=True)
    findings.append(
        f"- **{len(heavy)} `_context.md` item(s) over the {CONTEXT_ITEM_CHAR_BUDGET:,}-char "
        "per-item budget** — fold the superseded chronology into current state (the detail "
        "belongs on the parent page or cluster note), rather than waiting for the whole file "
        "to go over cap:"
    )
    for chars, lineno, title in heavy:
        mark = " **(egregious)**" if chars >= CONTEXT_ITEM_HARD_FLAG else ""
        findings.append(f"  - `wiki/_context.md:{lineno}` — {chars:,} chars{mark} — {title[:90]}")
    return heavy


# ---------------------------------------------------------------------------
# Link-graph checks: dangling links, broken anchors, orphans
# ---------------------------------------------------------------------------

ATTACHMENT_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".heic", ".pdf", ".excalidraw", ".canvas",
}
# Pointers to persistent-memory files and skill names, which are deliberately
# not wiki pages under the Claude Code memory conventions.
NON_PAGE_LINK_PREFIXES = ("reference-", "reference_", "feedback-", "feedback_", "project-", "memory/")


def check_dangling_links(vault: Path, findings: list[str]) -> tuple[int, int]:
    """Find wikilinks whose target page does not exist anywhere in the vault.

    A dangling link is a real graph defect — it reads as a live
    cross-reference on the page and resolves to nothing. Excluded by design:
    restricted folders (if present); file embeds (`![[image.png]]`);
    attachments; and memory-slug pointers, which are deliberate pointers to
    files outside wiki/. Folder links (where the folder exists but carries no
    index page) are reported separately as advisory, since Obsidian will not
    resolve them but they are a naming convention rather than a broken
    reference. A dangling link that appears only inside the append-only
    wiki/log.md is recorded but not counted: a historical entry records what
    was linked at the time and cannot be rewritten.
    """
    findings.append("")
    findings.append("### Dangling wikilinks (targets that do not exist)")
    findings.append(
        "A wikilink pointing at a page that does not exist anywhere in the vault. Reads as a "
        "live cross-reference, resolves to nothing. Memory-slug pointers, file embeds and "
        "attachments are exempt; folder links are advisory (see below)."
    )

    md_basenames = {p.stem for p in vault.rglob("*.md")}
    folder_names = {d.name for d in vault.rglob("*") if d.is_dir()}

    dangling: dict[str, set[str]] = {}
    folder_links: dict[str, set[str]] = {}
    log_only: dict[str, set[str]] = {}

    for path in sorted((vault / "wiki").rglob("*.md")):
        if any(part in RESTRICTED_FOLDER_NAMES for part in path.parts):
            continue
        for m in re.finditer(r"(!?)\[\[([^\]]+)\]\]", _strip_code_spans(page_text(path))):
            if m.group(1) == "!":  # file embed, not a page reference
                continue
            target = m.group(2).split("|")[0].split("#")[0].strip()
            if target.endswith("\\"):
                # Table-escaped alias form [[Page\|alias]]: Obsidian resolves
                # the backslash-pipe inside tables, so the trailing backslash
                # is not part of the page name.
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
            source = str(path.relative_to(vault))
            if basename in folder_names or target in folder_names:
                folder_links.setdefault(target, set()).add(source)
            else:
                dangling.setdefault(target, set()).add(source)

    for target in list(dangling):
        if dangling[target] == {"wiki/log.md"}:
            log_only[target] = dangling.pop(target)
    folder_log_only: dict[str, set[str]] = {}
    for target in list(folder_links):
        if folder_links[target] == {"wiki/log.md"}:
            folder_log_only[target] = folder_links.pop(target)

    if folder_log_only:
        findings.append(
            f"- **Exempt — {len(folder_log_only)} folder link(s) referenced only from "
            "`wiki/log.md`**: append-only by hard rule. Recorded, not counted as issues."
        )
    if log_only:
        findings.append(
            f"- **Exempt — {len(log_only)} dangling target(s) referenced only from `wiki/log.md`**: "
            "append-only by hard rule, so a historical entry's link cannot be rewritten. Recorded, "
            "not counted as issues."
        )
    if folder_links:
        total_folder = sum(len(v) for v in folder_links.values())
        findings.append(
            f"- **Advisory — {len(folder_links)} folder link(s)** ({total_folder} reference(s)): the folder "
            "exists but has no index page, so the link will not resolve in Obsidian. Create an index "
            "page or retarget the link."
        )
        for target, srcs in sorted(folder_links.items(), key=lambda kv: -len(kv[1])):
            findings.append(f"  - `[[{target}]]` — linked from {len(srcs)} page(s)")

    if dangling:
        total_refs = sum(len(v) for v in dangling.values())
        findings.append(
            f"- **{len(dangling)} dangling target(s)** across {total_refs} reference(s):"
        )
        for target, srcs in sorted(dangling.items(), key=lambda kv: (-len(kv[1]), kv[0])):
            shown = ", ".join(f"`{s}`" for s in sorted(srcs)[:3])
            more = f" (+{len(srcs) - 3} more)" if len(srcs) > 3 else ""
            findings.append(f"  - `[[{target}]]` <- {shown}{more}")
        return (0, len(dangling))

    findings.append("- No dangling wikilinks. ✓")
    return (1, 1)


def _anchor_norm(s: str) -> str:
    """Normalise a heading or anchor the way Obsidian resolves them."""
    s = re.sub(r"[`*_]", "", s)
    s = re.sub(r"[:;,.!?\"'()\[\]|#^]", " ", s)
    s = re.sub(r"[–—-]", " ", s)
    return re.sub(r"\s+", " ", s).strip().lower()


def check_broken_anchors(vault: Path, findings: list[str]) -> tuple[int, int]:
    """Find [[Page#Heading]] links whose target heading does not exist.

    The dangling-link check catches [[Page]] where the page does not exist;
    this catches the subtler case where the PAGE exists but the HEADING does
    not — a link that looks live, opens the right page, and silently lands
    nowhere near the section it promised. Aliased anchors
    ([[Page#Heading|display text]]) are checked the same way.
    """
    wiki = vault / "wiki"
    if not wiki.is_dir():
        return (0, 0)

    pages: dict[str, Path] = {}
    for p in wiki.rglob("*.md"):
        pages.setdefault(p.stem, p)

    heads_cache: dict[Path, set[str]] = {}

    def headings(p: Path) -> set[str]:
        if p not in heads_cache:
            heads_cache[p] = {
                _anchor_norm(l.lstrip("#"))
                for l in page_text(p).split("\n")
                if l.startswith("#")
            }
        return heads_cache[p]

    broken: dict[tuple[str, str], set[str]] = {}
    for path in sorted(wiki.rglob("*.md")):
        if path.name == "log.md":
            continue
        if any(part in RESTRICTED_FOLDER_NAMES for part in path.parts):
            continue
        for m in re.finditer(r"\[\[([^\]|#]+)#([^\]|]+)(?:\|[^\]]*)?\]\]",
                             _strip_code_spans(page_text(path))):
            target, anchor = m.group(1).strip(), m.group(2).strip()
            if target not in pages:
                continue  # a missing page is the dangling-link guard's business
            if _anchor_norm(anchor) not in headings(pages[target]):
                broken.setdefault((target, anchor), set()).add(
                    str(path.relative_to(wiki)))

    findings.append("")
    findings.append("### Broken section anchors")
    findings.append(
        "A `[[Page#Heading]]` link whose page exists but whose heading does not. It "
        "opens the right page and lands nowhere near the promised section, so it reads "
        "as live and is not. Anchors are normalised the way Obsidian resolves them; "
        "code spans are stripped so prose illustrating a link is not counted."
    )
    if not broken:
        findings.append("- No broken section anchors. ✓")
        return (1, 1)

    total_refs = sum(len(v) for v in broken.values())
    findings.append(
        f"- **{len(broken)} broken anchor(s)** ({total_refs} reference(s)):"
    )
    for (target, anchor), srcs in sorted(broken.items()):
        findings.append(f"  - `[[{target}#{anchor}]]` — from {', '.join(sorted(srcs)[:3])}")
    return (0, len(broken))


def check_orphan_pages(vault: Path, findings: list[str]) -> tuple[int, int]:
    """Find pages with no inbound wikilink from anywhere but the append-only log."""
    wiki = vault / "wiki"
    if not wiki.is_dir():
        return (0, 0)

    pages: dict[str, Path] = {}
    for p in wiki.rglob("*.md"):
        pages.setdefault(p.stem, p)

    inbound: dict[str, int] = {s: 0 for s in pages}
    for path in wiki.rglob("*.md"):
        if path.name == "log.md":
            continue
        seen = set()
        for m in re.finditer(r"\[\[([^\]|#]+)", _strip_code_spans(page_text(path))):
            t = m.group(1).strip()
            if t != path.stem:
                seen.add(t)
        for t in seen:
            if t in inbound:
                inbound[t] += 1

    # Restricted-folder pages (if the vault has any) are orphaned BY DESIGN:
    # the one-directional-link rule forbids subject pages from linking back.
    orphans = sorted(
        s for s, p in pages.items()
        if inbound[s] == 0
        and not any(part in RESTRICTED_FOLDER_NAMES for part in p.parts)
    )

    findings.append("")
    findings.append("### Orphan pages (no inbound link outside the log)")
    findings.append(
        "The inverse of a dangling link: a page nothing points at, reachable only by "
        "folder browsing. Restricted folders (if present) are excluded — their pages "
        "are orphaned by design under the one-directional-link rule."
    )
    if not orphans:
        findings.append("- No orphan pages. ✓")
        return (1, 1)
    findings.append(f"- **{len(orphans)} orphan page(s)**:")
    for o in orphans:
        findings.append(f"  - `wiki/{pages[o].relative_to(wiki)}`")
    return (0, len(orphans))


# ---------------------------------------------------------------------------
# _context.md state guards
# ---------------------------------------------------------------------------

# Self-cancelling-item guard.
# A discrete one-shot task recorded in an always-loaded file with a
# "strike once done" self-cancel condition is the dangerous class: when the
# work later lands but the entry is not struck, it goes stale-but-live and
# gets re-surfaced as actionable. This guard lists every OPEN self-cancelling
# item so each is cross-checked against the log at the lint pass. It CANNOT
# auto-resolve them (that needs a semantic log check); it only forces the
# look. STRICTLY ADVISORY: never edits or strikes anything.
SELF_CANCEL_FILES = [
    "wiki/_context.md",
]

# High-signal self-cancel markers. The explicit "strike/remove/drop the entry
# once X" instruction and the literal REMINDER framing are the dangerous
# class; persistent watch-list phrasing ("watch for X", "when it lands") is
# deliberately NOT matched, because those items are meant to persist.
SELF_CANCEL_RE = re.compile(
    r"\bREMINDER\b"
    r"|\b(?:strike|remove|drop|delete|retire)\b[^.\n]{0,40}?\bonce\b"
    r"|\bstrike (?:this|the) entry\b",
    re.IGNORECASE,
)


def check_self_cancelling_items(vault: Path, findings: list[str]) -> tuple[int, int]:
    """List open self-cancelling items in always-loaded TODO-bearing files.

    An item is a markdown bullet (`- ...`). Items already struck (the
    convention wraps closed items in `~~strikethrough~~`) are treated as
    resolved and skipped. Every surviving match is surfaced for a manual log
    cross-check; the count is reported as items-to-verify, not a hard failure.
    """
    findings.append("")
    findings.append("### Self-cancelling items (advisory; verify each against the log)")
    findings.append(
        "Open discrete-task / REMINDER entries in the always-loaded files that carry a "
        '"strike once done" self-cancel condition. Each must be checked against [[log]]: '
        "if the underlying work has landed, strike the entry in the same pass. This guard "
        "never strikes anything itself."
    )
    open_items: list[tuple[str, int, str]] = []
    for rel in SELF_CANCEL_FILES:
        path = vault / rel
        if not path.is_file():
            findings.append(f"- `{rel}`: skipped — file missing.")
            continue
        for lineno, raw in enumerate(page_text(path).splitlines(), start=1):
            line = raw.strip()
            if not line.startswith("-"):
                continue
            if "~~" in line:  # struck/closed by the strikethrough convention
                continue
            if SELF_CANCEL_RE.search(line):
                m = re.search(r"\*\*(.+?)\*\*", line)
                label = m.group(1) if m else line.lstrip("- ").strip()
                open_items.append((rel, lineno, label[:90]))
    if open_items:
        findings.append(f"- **{len(open_items)} open self-cancelling item(s) to verify:**")
        for rel, lineno, label in open_items:
            findings.append(f"  - `{rel}:{lineno}` — {label}")
        return (0, len(open_items))
    findings.append("- No open self-cancelling items found. ✓")
    return (1, 1)


# Dated state-drift and tombstone guard. _context.md is the live-state
# register; three drift modes are scriptable: (1) an expired dated trigger
# inside an OPEN item — an "expected/review/by <date>" that has passed while
# the item stays unstruck; (2) a stale "As of <date>" state line; (3) a closed
# (struck) entry whose inline tombstone has bloated past the
# one-line-index-entry retention policy. Undated event triggers are out of
# scope (qualitative-lint territory). STRICTLY ADVISORY: never edits.
STATE_DRIFT_FILE = "wiki/_context.md"
MONTH_NUM = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
}
# An absolute date carrying an explicit year: "17 June 2026", or month-only
# "August 2026" (month-only dates expire once the whole month has passed).
# Day-without-year dates are deliberately not matched: too many historical
# references omit the year, and the false-positive cost outweighs the coverage.
DATED_RE = re.compile(
    r"(?:(\d{1,2})\s+)?"
    r"(January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+(20\d{2})"
)
TRIGGER_VOCAB_RE = re.compile(
    r"\b(expected|review|revisit|re-?run|target|due|deadline|closes|by end of|"
    r"no later than|expires|until)\b",
    re.IGNORECASE,
)
AS_OF_RE = re.compile(r"[Aa]s of\s+(\d{1,2})\s+" + DATED_RE.pattern[len(r"(?:(\d{1,2})\s+)?"):])
# Words that mark the date immediately following them as historical reference,
# overriding an earlier trigger word in the same lookback window.
HISTORICAL_MARKER_RE = re.compile(
    r"\b(set|opened|established|created|shipped|built|since|from|recorded|folded|flagged|"
    r"ingested|surfaced|corrected|confirmed|verified|struck|resolved|"
    r"landed|began|started|published|announced)\b",
    re.IGNORECASE,
)
AS_OF_STALE_DAYS = 21
TRIGGER_GRACE_DAYS = 7
TRIGGER_LOOKBACK_CHARS = 45
TOMBSTONE_MAX_CHARS = 500


def month_end(year: int, month: int) -> datetime.date:
    if month == 12:
        return datetime.date(year, 12, 31)
    return datetime.date(year, month + 1, 1) - datetime.timedelta(days=1)


def check_dated_state_drift(vault: Path, findings: list[str]) -> tuple[int, int]:
    """Flag dated state drift and tombstone bloat on _context.md (advisory).

    Three modes: expired dated triggers in open items, stale "As of" state
    lines, and closed tombstones bloated past the one-line retention policy.
    Every flag needs a judgement call (close the item, re-date the line, trim
    to the archive), so the guard only surfaces; the compact skill or the
    session pass acts.
    """
    findings.append("")
    findings.append("### Dated state drift and tombstones on _context.md (advisory; never edits)")
    findings.append(
        "Expired dated triggers in open items (the deadline passed while the item stays "
        "unstruck), stale `As of <date>` state lines, and closed tombstones grown past the "
        "one-line index-entry policy. Dated triggers only — undated event triggers are the "
        "qualitative lint's territory. Each flag is a judgement call for the session pass or "
        "the compact skill; this guard never edits."
    )
    path = vault / STATE_DRIFT_FILE
    if not path.is_file():
        findings.append(f"- `{STATE_DRIFT_FILE}`: skipped — file missing.")
        return (0, 0)
    today = datetime.date.today()
    issues: list[str] = []
    text = page_text(path)
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line.startswith("-"):
            continue
        body = line.lstrip("- ").strip()
        if body.startswith("~~"):
            if len(line) > TOMBSTONE_MAX_CHARS:
                m = re.search(r"\*\*(.+?)\*\*", body)
                label = m.group(1) if m else body[:60]
                issues.append(
                    f"`{STATE_DRIFT_FILE}:{lineno}` — closed tombstone at {len(line)} chars "
                    f"(policy: a one-line index entry; full text belongs in Context Archive) — {label[:90]}"
                )
            # Tombstone age: the retention rule drops a strikethrough index
            # line ~30 days after its close date, archive copy verified first.
            close_dates = []
            for dm in DATED_RE.finditer(line):
                day, month, year = dm.groups()
                if day:
                    try:
                        close_dates.append(
                            datetime.date(int(year), MONTH_NUM[month.lower()], int(day))
                        )
                    except ValueError:
                        # An impossible prose date ("31 June") is a typo, and
                        # must not crash the lint before the report is written.
                        issues.append(
                            f"`{STATE_DRIFT_FILE}:{lineno}` — impossible date in tombstone: \"{dm.group(0)}\""
                        )
            if close_dates and (today - max(close_dates)).days > 37:
                m = re.search(r"\*\*(.+?)\*\*", body)
                label = m.group(1) if m else body[:60]
                issues.append(
                    f"`{STATE_DRIFT_FILE}:{lineno}` — tombstone {(today - max(close_dates)).days} days past its close date "
                    f"(retention: drop ~30 days after close, archive copy verified first) — {label[:90]}"
                )
            continue
        for m in DATED_RE.finditer(line):
            day, month, year = m.groups()
            mnum = MONTH_NUM[month.lower()]
            try:
                due = (
                    datetime.date(int(year), mnum, int(day))
                    if day
                    else month_end(int(year), mnum)
                )
            except ValueError:
                issues.append(
                    f"`{STATE_DRIFT_FILE}:{lineno}` — impossible date in line: \"{m.group(0)}\""
                )
                continue
            lookback = line[max(0, m.start() - TRIGGER_LOOKBACK_CHARS) : m.start()]
            triggers = list(TRIGGER_VOCAB_RE.finditer(lookback))
            if not triggers:
                continue
            # The trigger must still be "aimed at" the matched date: if
            # another dated phrase or a historical marker sits between the
            # trigger and the date, the trigger was consumed by that nearer
            # phrase.
            between = lookback[triggers[-1].end() :]
            if DATED_RE.search(between) or HISTORICAL_MARKER_RE.search(between):
                continue
            # Retrospective-phrasing test. "Flagged for review on 8 May" says
            # when the flagging happened, not when anything is due. Both
            # conditions must hold to suppress, so a genuine forward trigger
            # ("revisit on 1 October") still fires: (1) the trigger is joined
            # to the date by "on" rather than a forward preposition; (2) a
            # historical marker appears anywhere earlier in the line.
            joiner = re.sub(r"[*_`]", "", between)
            if re.fullmatch(r"[\s,]*on[\s,]*", joiner, re.IGNORECASE):
                before_trigger = line[: max(0, m.start() - TRIGGER_LOOKBACK_CHARS)
                                      + triggers[-1].start()]
                if HISTORICAL_MARKER_RE.search(before_trigger):
                    continue
            if (today - due).days > TRIGGER_GRACE_DAYS:
                issues.append(
                    f"`{STATE_DRIFT_FILE}:{lineno}` — possible expired trigger: "
                    f'"…{lookback.strip()[-35:]} {m.group(0)}" has passed while the item stays open'
                )
    for m in AS_OF_RE.finditer(text):
        day, month, year = m.group(1), m.group(2), m.group(3)
        try:
            stamped = datetime.date(int(year), MONTH_NUM[month.lower()], int(day))
        except ValueError:
            lineno = text.count("\n", 0, m.start()) + 1
            issues.append(
                f"`{STATE_DRIFT_FILE}:{lineno}` — impossible date in as-of line: \"{m.group(0)}\""
            )
            continue
        if (today - stamped).days > AS_OF_STALE_DAYS:
            lineno = text.count("\n", 0, m.start()) + 1
            issues.append(
                f"`{STATE_DRIFT_FILE}:{lineno}` — stale state line: \"{m.group(0)}\" is "
                f"{(today - stamped).days} days old; re-date it or point it at the refresh chain"
            )
    if issues:
        findings.append(f"- **{len(issues)} state-drift flag(s):**")
        for issue in issues:
            findings.append(f"  - {issue}")
        return (0, len(issues))
    findings.append("- No semantic state drift detected. ✓")
    return (1, 1)


def check_future_dates(vault: Path, findings: list[str]) -> tuple[int, int]:
    """Future-dated stamps: no log header and no `as of` line in _context.md
    may be dated after tomorrow (one day of timezone slack). Catches the
    wrong-clock class of error before it propagates."""
    issues = []
    today = datetime.date.today()
    limit = today + datetime.timedelta(days=1)
    log = vault / "wiki" / "log.md"
    total = 0
    for m in re.finditer(r"^## \[(\d{4}-\d{2}-\d{2})", page_text(log), re.MULTILINE):
        total += 1
        try:
            d = datetime.date.fromisoformat(m.group(1))
        except ValueError:
            continue
        if d > limit:
            issues.append(f"log header dated {d} — in the future; verify the clock before stamping")
    ctx = vault / "wiki" / "_context.md"
    for m in AS_OF_RE.finditer(page_text(ctx)):
        total += 1
        try:
            d = datetime.date(int(m.group(3)), MONTH_NUM[m.group(2).lower()], int(m.group(1)))
        except (ValueError, KeyError):
            continue
        if d > limit:
            issues.append(f"_context.md as-of line dated {d} — in the future")
    if issues:
        findings.append(f"- **Future-dated stamps**: **{len(issues)} found**:")
        for i in issues:
            findings.append(f"  - {i}")
    else:
        findings.append(f"- **Future-dated stamps**: none across {total} dated stamps. ✓")
    return (total - len(issues), total)


def check_refresh_note_retention(vault: Path, findings: list[str]) -> tuple[int, int]:
    """The _context refresh-chain retention rule: the latest note stays inline
    at full length, at most two prior notes stay as compressed headlines, and
    older notes rotate to the Context Archive. The `compact` skill is the
    executor; this is its detector."""
    path = vault / "wiki" / "_context.md"
    if not path.is_file():
        findings.append("- **Refresh-note retention**: skipped — _context.md missing.")
        return (0, 0)
    text = page_text(path)
    issues = []
    prev_count = text.count("Previous refresh:")
    if "Last refreshed:" not in text:
        issues.append("no `Last refreshed:` marker found in _context.md")
    if prev_count > 2:
        issues.append(f"{prev_count} `Previous refresh:` notes inline — the rule keeps at most two (rotate the rest to Context Archive)")
    for m in re.finditer(r"Previous refresh: [^(]{0,120}\(", text):
        start = m.end() - 1
        depth = 0
        for i in range(start, min(start + 6000, len(text))):
            if text[i] == "(":
                depth += 1
            elif text[i] == ")":
                depth -= 1
                if depth == 0:
                    note_len = i - start
                    if note_len > 1200:
                        issues.append(
                            f"a `Previous refresh:` note runs {note_len} chars — prior notes stay as one-sentence headlines (~≤1,200 chars), full text lives in Context Archive"
                        )
                    break
        else:
            issues.append("a `Previous refresh:` parenthetical never closes — malformed refresh chain")
    total = max(prev_count + 1, 1)
    if issues:
        findings.append(f"- **Refresh-note retention**: **{len(issues)} issue(s)**:")
        for i in issues:
            findings.append(f"  - {i}")
    else:
        findings.append(f"- **Refresh-note retention**: chain healthy (1 full note + {prev_count} headline(s) inline). ✓")
    return (total - min(len(issues), total), total)


# ---------------------------------------------------------------------------
# Restricted-folder invariants (conditional: skipped when neither folder exists)
# ---------------------------------------------------------------------------


def _frontmatter_head(path: Path, limit: int = 2048) -> str:
    try:
        with path.open(encoding="utf-8", errors="ignore") as f:
            head = f.read(limit)
    except OSError:
        return ""
    if not head.startswith("---"):
        return ""
    end = head.find("\n---", 3)
    return head[3:end] if end != -1 else head


def check_restricted_invariants(vault: Path, findings: list[str]) -> tuple[int, int]:
    """Two invariants of the restricted-folders pattern, checked without
    reading restricted prose (frontmatter heads and link syntax only):
    (1) every page under a restricted folder carries a `restricted:`
    frontmatter marker; (2) links flow one direction only — no page OUTSIDE
    the folders wikilinks a restricted basename. Skipped silently when the
    vault has no restricted folders."""
    restricted_dirs = [vault / "wiki" / name for name in RESTRICTED_FOLDER_NAMES]
    if not any(d.is_dir() for d in restricted_dirs):
        return (0, 0)
    issues = []
    restricted_stems: set[str] = set()
    total = 0
    for d in restricted_dirs:
        if not d.is_dir():
            continue
        for f in sorted(d.rglob("*.md")):
            total += 1
            restricted_stems.add(f.stem)
            if not re.search(r"(?mi)^restricted:", _frontmatter_head(f)):
                issues.append(f"`{f.relative_to(vault)}` — missing the mandatory `restricted:` frontmatter marker")
    # The one-direction rule governs SUBJECT pages. Records and navigation are
    # exempt by design: log.md and the Context Archive are append-only history
    # that legitimately name restricted pages; Index catalogues each folder
    # once. Links to the folder-index stems themselves are navigation.
    exempt_sources = {"log", "Context Archive", "Index", "_context"}
    folder_index_stems = set(RESTRICTED_FOLDER_NAMES)
    for f in sorted((vault / "wiki").rglob("*.md")):
        if any(str(f).startswith(str(d) + os.sep) for d in restricted_dirs):
            continue
        if f.stem in exempt_sources:
            continue
        for target in wikilink_targets(page_text(f)):
            if target in restricted_stems and target not in folder_index_stems:
                issues.append(
                    f"`{f.relative_to(vault)}` — wikilinks into a restricted folder (`[[{target[:40]}]]`); "
                    "links flow one direction only, remove the inbound link"
                )
    if issues:
        findings.append(f"- **Restricted-folder invariants**: **{len(issues)} violation(s)**:")
        for i in issues:
            findings.append(f"  - {i}")
    else:
        findings.append(
            f"- **Restricted-folder invariants**: {total} restricted page(s) all carry `restricted:`; no inbound links from the open graph. ✓"
        )
    return (max(total - len(issues), 0), total)


# ---------------------------------------------------------------------------
# Informational sweeps
# ---------------------------------------------------------------------------


def check_reciprocal_backlinks(vault: Path, findings: list[str]) -> tuple[int, int]:
    """Sampled forced-look (informational): for pages modified in the last 7
    days, list outbound wikilinks whose target page never links back. Many
    one-way links are legitimate (log references, indexes), so this lists for
    judgement rather than counting issues."""
    now = datetime.datetime.now().timestamp()
    wiki = vault / "wiki"
    if not wiki.is_dir():
        return (0, 0)
    stems = {}
    for f in wiki.rglob("*.md"):
        stems.setdefault(f.stem, f)
    skip_targets = {"log", "_context", "Index", "Context Archive"}
    asymmetries = []
    sampled = 0
    for f in sorted(wiki.rglob("*.md")):
        if (now - f.stat().st_mtime) > 7 * 86400:
            continue
        if f.name == "log.md":  # append-only record; its links are one-way by design
            continue
        if any(part in RESTRICTED_FOLDER_NAMES for part in f.parts):
            continue
        sampled += 1
        text = page_text(f)
        for target in sorted(wikilink_targets(text)):
            if target in skip_targets or target == f.stem:
                continue
            tf = stems.get(target)
            if tf is None or tf.stem == tf.parent.name:  # dangling handled elsewhere; folder indexes exempt
                continue
            if any(part in RESTRICTED_FOLDER_NAMES for part in tf.parts):
                continue
            if f"[[{f.stem}" not in page_text(tf):
                asymmetries.append(f"`{f.stem[:50]}` → `{target[:50]}` (no backlink)")
            if len(asymmetries) >= 15:
                break
        if len(asymmetries) >= 15:
            break
    if asymmetries:
        findings.append(
            f"- **Reciprocal backlinks (sampled, informational)**: {len(asymmetries)} one-way link(s) on pages touched in the last 7 days — "
            "judge each: add the backlink or leave deliberately (capped at 15):"
        )
        for a in asymmetries:
            findings.append(f"  - {a}")
    else:
        findings.append(f"- **Reciprocal backlinks (sampled)**: no asymmetries on the {sampled} page(s) touched in the last 7 days. ✓")
    return (sampled, sampled)


SUPERLATIVE_RE = re.compile(
    r"\b(first|largest|biggest|densest|smallest|longest|highest ever|lowest ever|on record|never before|the only)\b",
    re.IGNORECASE,
)


def check_superlative_phrasing(vault: Path, findings: list[str]) -> tuple[int, int]:
    """Forced-look sweep (informational): lists superlative phrasing written
    into the last 7 days of log entries, for verification against the corpus
    (grep before letting any first/largest/only claim stand). Listing is not
    an accusation; verify each."""
    today = datetime.date.today()
    cutoff = today - datetime.timedelta(days=7)
    text = page_text(vault / "wiki" / "log.md")
    hits = []
    entries = list(re.finditer(r"^## \[(\d{4}-\d{2}-\d{2})[^\]]*\].*$", text, re.MULTILINE))
    for idx, m in enumerate(entries):
        try:
            d = datetime.date.fromisoformat(m.group(1))
        except ValueError:
            continue
        if d < cutoff:
            continue
        end = entries[idx + 1].start() if idx + 1 < len(entries) else len(text)
        body = text[m.start():end]
        for line in body.splitlines():
            sm = SUPERLATIVE_RE.search(line)
            if sm:
                snippet = line.strip()
                pos = max(sm.start() - 40, 0)
                hits.append(f"[{d}] …{snippet[pos:pos + 110]}…")
            if len(hits) >= 20:
                break
        if len(hits) >= 20:
            break
    if hits:
        findings.append(
            f"- **Superlative phrasing (last 7 days, informational)**: {len(hits)} instance(s) — verify each against the corpus "
            "(grep before any first/largest/only claim; capped at 20):"
        )
        for h in hits:
            findings.append(f"  - {h}")
    else:
        findings.append("- **Superlative phrasing (last 7 days)**: none found. ✓")
    return (1, 1)


def check_correction_rate(vault: Path, findings: list[str]) -> tuple[int, int]:
    """Error-rate dashboard line (informational): corrections per week over
    the last eight ISO weeks, so an error surge is a number on a trend rather
    than a felt read. Counts `correction`-type log headers."""
    text = page_text(vault / "wiki" / "log.md")
    today = datetime.date.today()
    weeks: dict[str, int] = {}
    for m in re.finditer(r"^## \[(\d{4}-\d{2}-\d{2})[^\]]*\]\s*correction\s*\|", text, re.MULTILINE):
        try:
            d = datetime.date.fromisoformat(m.group(1))
        except ValueError:
            continue
        if (today - d).days > 56:
            continue
        iso = d.isocalendar()
        weeks[f"{iso[0]}-W{iso[1]:02d}"] = weeks.get(f"{iso[0]}-W{iso[1]:02d}", 0) + 1
    if weeks:
        series = ", ".join(f"{k}: {v}" for k, v in sorted(weeks.items()))
        latest = sorted(weeks.items())[-1]
        note = " — elevated" if latest[1] >= 4 else ""
        findings.append(f"- **Correction rate (8 weeks, informational)**: {series}{note}.")
    else:
        findings.append("- **Correction rate (8 weeks)**: no correction entries in the window.")
    return (1, 1)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main() -> int:
    vault = find_vault_root()
    today = datetime.date.today()
    findings: list[str] = []

    findings.append(f"# Lint v2 — Structural Conventions Check, {today.isoformat()}")
    findings.append("")
    findings.append(
        f"Programmatic verifier of the structural schema conventions codified in the vault's `CLAUDE.md`. Runs alongside the qualitative lint, not in place of it. Vault root: `{vault}`."
    )
    findings.append("")
    findings.append("## Checks")
    findings.append("")

    scorecard: list[tuple[str, int, int]] = []

    pass_, tot = check_cluster_note_coverage(vault, findings)
    scorecard.append(("Cluster-note index coverage", pass_, tot))

    pass_, tot = check_cluster_note_frontmatter(vault, findings)
    scorecard.append(("Cluster-note frontmatter", pass_, tot))

    pass_, tot = check_index_domains_coverage(vault, findings)
    scorecard.append(("Index.md Domains coverage", pass_, tot))

    pass_, tot = check_log_timestamps(vault, findings)
    scorecard.append(("Log header format and timestamp ordering", pass_, tot))

    pass_, tot = check_outputs_size(vault, findings)
    scorecard.append(("outputs/ size guard (advisory, never deletes)", pass_, tot))

    pass_, tot = check_vault_weight(vault, findings)
    scorecard.append(("Vault weight (token caps, advisory, never trims)", pass_, tot))

    pass_, tot = check_dangling_links(vault, findings)
    scorecard.append(("Dangling wikilinks", pass_, tot))

    pass_, tot = check_broken_anchors(vault, findings)
    scorecard.append(("Broken section anchors", pass_, tot))

    pass_, tot = check_orphan_pages(vault, findings)
    scorecard.append(("Orphan pages", pass_, tot))

    pass_, tot = check_self_cancelling_items(vault, findings)
    scorecard.append(("Self-cancelling items (advisory; verify vs log)", pass_, tot))

    pass_, tot = check_dated_state_drift(vault, findings)
    scorecard.append(("Dated state drift and tombstones on _context.md (advisory)", pass_, tot))

    pass_, tot = check_restricted_invariants(vault, findings)
    scorecard.append(("Restricted-folder invariants (marker + one-way links)", pass_, tot))

    pass_, tot = check_future_dates(vault, findings)
    scorecard.append(("Future-dated stamps", pass_, tot))

    pass_, tot = check_attribution_lines(vault, findings)
    scorecard.append(("Cluster-note source attribution", pass_, tot))

    pass_, tot = check_refresh_note_retention(vault, findings)
    scorecard.append(("_context refresh-note retention", pass_, tot))

    pass_, tot = check_reciprocal_backlinks(vault, findings)
    scorecard.append(("Reciprocal backlinks (sampled, informational)", pass_, tot))

    pass_, tot = check_superlative_phrasing(vault, findings)
    scorecard.append(("Superlative phrasing sweep (informational)", pass_, tot))

    pass_, tot = check_correction_rate(vault, findings)
    scorecard.append(("Correction rate (informational)", pass_, tot))

    # Read-failure surfacing: a file that exists but could not be read makes
    # every check that touched it silently clean. Count each failure as a
    # failed unit so the run cannot report all-clean.
    if READ_FAILURES:
        findings.append("")
        findings.append(
            f"- **READ FAILURES**: **{len(READ_FAILURES)} file(s) existed but could not be read** — "
            "every check touching them ran against empty text and its ✓ is unreliable:"
        )
        for rf in sorted(set(READ_FAILURES)):
            findings.append(f"  - `{rf}`")
        scorecard.append(("File readability (checks above unreliable on failure)", 0, len(set(READ_FAILURES))))

    findings.append("")
    findings.append("## Summary")
    findings.append("")
    findings.append("| Check | Passed / Total | Status |")
    findings.append("|---|---|---|")
    for name, p, t in scorecard:
        if t == 0:
            status = "skipped"
        elif p == t:
            status = "✓"
        else:
            status = f"**{t - p} issue(s)**"
        findings.append(f"| {name} | {p} / {t} | {status} |")

    if LOG_TIMESTAMP_EXCEPTIONS:
        findings.append("")
        findings.append("## Known accepted exceptions")
        findings.append("")
        findings.append(
            "Entries the structural checks would otherwise flag, that cannot be rewritten without violating the `Append-only log` hard rule. Listed here for transparency; the checks above subtract these from the issue counts. Review at each lint; remove an entry only if the underlying state is corrected at the source."
        )
        findings.append("")
        for e in LOG_TIMESTAMP_EXCEPTIONS:
            findings.append(f"- `{e['date']}` `{e['title_prefix']}` — {e['reason']}")

    findings.append("")
    findings.append("---")
    findings.append("")
    findings.append(
        "*Output of `scripts/lint-v2.py`. Companion to the qualitative lint at `outputs/lint-report-YYYY-MM-DD.md`. The qualitative lint reads for content drift; this report reads for structural-convention drift.*"
    )

    # --out <path> overrides the dated default (useful for a scheduled run
    # that writes a fixed rolling path instead of one file per day).
    if "--out" in sys.argv:
        try:
            out_path = Path(sys.argv[sys.argv.index("--out") + 1])
        except IndexError:
            print("error: --out needs a path", file=sys.stderr)
            return 2
    else:
        out_path = vault / "outputs" / "lint" / f"lint-v2-{today.isoformat()}.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(findings) + "\n", encoding="utf-8")
    print(f"lint-v2 report written to: {out_path}")

    total_issues = sum(t - p for _, p, t in scorecard)
    if total_issues == 0:
        print("All checks clean.")
        return 0
    print(f"{total_issues} issue(s) across checks; see report.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
