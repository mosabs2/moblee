#!/usr/bin/env python3
"""
lint-v2: structural-conventions verifier for a Moblee wiki vault.

Reads the vault, checks the structural schema conventions codified in the
vault's CLAUDE.md, and writes a markdown report to
outputs/lint/lint-v2-YYYY-MM-DD.md inside the vault.

Companion to the qualitative lint (which reads for contradictions, stale
claims, missing concepts, and data gaps — judgement calls a script cannot
make). This script does the things that are structural and scriptable:
log-header timestamps, append-only ordering, session-metadata footers on
housekeeping entries, frontmatter schemas on typed folders (cluster notes,
daily notes), duplicate frontmatter blocks, dangling wikilinks, broken
section anchors, orphan pages, source attribution, the token-budget weight
guard (always-loaded files and the skills layer), and a handful of advisory
sweeps (superlatives, prose boilerplate, correction rate), and (v0.7) a
habits-and-tools check that asks whether the owner's setup still fits.

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


# Housekeeping entries that legitimately lack the session-metadata footer and
# cannot be retro-edited (append-only log). Same shape as the list above:
# date, title prefix, one-line reason. Empty on a fresh vault.
SESSION_FOOTER_EXCEPTIONS: list[dict[str, str]] = [
    # {"date": "2027-01-01",
    #  "title_prefix": "Small mid-session note",
    #  "reason": "Parent session's footer landed on the closing entry of the same day."},
]


def is_session_footer_exception(date: datetime.date, title: str) -> bool:
    for e in SESSION_FOOTER_EXCEPTIONS:
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


def _head_lines(path: Path, n: int) -> list[str]:
    """First n lines of a file, without reading the rest of it."""
    try:
        with path.open(encoding="utf-8", errors="ignore") as f:
            out: list[str] = []
            for i, line in enumerate(f):
                if i >= n:
                    break
                out.append(line.rstrip("\n"))
            return out
    except OSError as e:
        if path.exists():
            READ_FAILURES.append(f"{path} ({e.__class__.__name__})")
        return []


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


def check_frontmatter_schema(
    vault: Path,
    findings: list[str],
    folder_rel: str,
    required_fields: list[str],
    label: str,
    parent_required: str | None = None,
) -> tuple[int, int]:
    """Generic frontmatter-schema check for one folder of typed pages.

    Every `*.md` in `folder_rel` (relative to the vault) must carry YAML
    frontmatter with each of `required_fields`. When `parent_required` is
    given, a `parent` value that does not contain it is flagged (a note filed
    under the wrong parent page). The folder's own index page (stem equal to
    the folder name) is navigation, not an item, and is skipped. A missing
    folder skips silently so a fresh vault lints clean.
    """
    folder = vault / folder_rel
    if not folder.is_dir():
        return (0, 0)
    issues: list[str] = []
    bad_files: set[str] = set()
    total = 0
    for f in sorted(folder.glob("*.md")):
        if f.stem == folder.name:
            continue
        total += 1
        rel = f.relative_to(vault).as_posix()
        fm = read_frontmatter(f)
        if fm is None:
            issues.append(f"`{rel}`: no frontmatter or malformed YAML")
            bad_files.add(rel)
            continue
        missing_fields = [k for k in required_fields if k not in fm]
        if missing_fields:
            issues.append(f"`{rel}`: missing fields → {', '.join(missing_fields)}")
            bad_files.add(rel)
        if parent_required and fm.get("parent") and parent_required not in str(fm["parent"]):
            issues.append(f"`{rel}`: parent is `{fm['parent']}`, expected `{parent_required}`")
            bad_files.add(rel)
    if total == 0:
        return (0, 0)
    clean = total - len(bad_files)
    if issues:
        findings.append(
            f"- **{label} frontmatter**: {clean}/{total} clean. **{len(issues)} issue(s)**:"
        )
        for i in issues:
            findings.append(f"  - {i}")
    else:
        findings.append(
            f"- **{label} frontmatter**: {total}/{total} files carry the canonical schema "
            f"({', '.join(required_fields)}). ✓"
        )
    return (clean, total)


def check_cluster_note_frontmatter(vault: Path, findings: list[str]) -> tuple[int, int]:
    """Each cluster note carries the canonical frontmatter (date, type, parent).

    Delegates to check_frontmatter_schema per `wiki/<Topic> Cluster Notes/`
    folder. When the parent synthesis page `wiki/<Topic>.md` exists, a note's
    `parent` must point at it; when it does not, the parent value is left
    unchecked (the owner may have named the parent page differently).
    """
    folders = cluster_note_folders(vault)
    if not folders:
        return (0, 0)
    passed = 0
    total = 0
    for folder in folders:
        topic = folder.name[: -len(" Cluster Notes")]
        parent_required = f"[[{topic}]]" if (vault / "wiki" / f"{topic}.md").is_file() else None
        p, t = check_frontmatter_schema(
            vault,
            findings,
            f"wiki/{folder.name}",
            ["date", "type", "parent"],
            f"{topic} cluster-note",
            parent_required=parent_required,
        )
        passed += p
        total += t
    return (passed, total)


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
    # Identity.md is loaded every session by CLAUDE.md and kept off the Index
    # by design (it is the standard Claude is held to, not catalogue content).
    infrastructure_exempt = {"Index", "log", "_context", "Identity"}
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


def check_log_session_metadata(vault: Path, findings: list[str]) -> tuple[int, int]:
    """Session-metadata footers on housekeeping log entries.

    The vault's CLAUDE.md asks the closing entry of a substantive session to
    carry an italicised metadata line (`*Session: started …; ended …*`, or
    `*Workday: …*` for a close-day entry). This check reads every
    `housekeeping` entry and every `workday-close` entry and looks for that
    footer in the entry's own body (sliced to the next header of ANY type, so
    a neighbour's footer never satisfies it). Because the convention is
    per-session rather than per-entry, an unfooted housekeeping entry is
    accepted when any entry of the same day or the next day carries a footer
    (sessions legitimately close past midnight). Titles containing
    "addendum" are exempt. Genuine leftovers go on SESSION_FOOTER_EXCEPTIONS.
    A log with no housekeeping entries yet passes.
    """
    log = vault / "wiki" / "log.md"
    if not log.exists():
        findings.append("- **Session metadata footers**: skipped — log.md missing.")
        return (0, 0)
    text = page_text(log)
    footer_re = re.compile(r"\*(?:Session|Workday)[^:\n]{0,80}:.+?\*", re.DOTALL)
    all_headers = [h.start() for h in re.finditer(r"^## \[", text, re.MULTILINE)]
    all_headers.append(len(text))

    def body_of(start: int) -> str:
        for h in all_headers:
            if h > start:
                return text[start:h]
        return text[start:]

    any_entry_re = re.compile(
        r"^## \[(\d{4}-\d{2}-\d{2}) \d{2}:\d{2}[^\]]*\] [\w-]+ \|", re.MULTILINE
    )
    footered_dates: set[datetime.date] = set()
    for m in any_entry_re.finditer(text):
        try:
            d0 = datetime.date.fromisoformat(m.group(1))
        except ValueError:
            continue
        if footer_re.search(body_of(m.start())):
            footered_dates.add(d0)

    hk_re = re.compile(
        r"^## \[(\d{4}-\d{2}-\d{2}) \d{2}:\d{2}[^\]]*\] housekeeping \| (.+?)$",
        re.MULTILINE,
    )
    housekeeping_entries: list[tuple[datetime.date, str, int]] = []
    for m in hk_re.finditer(text):
        try:
            d = datetime.date.fromisoformat(m.group(1))
        except ValueError:
            continue
        title = m.group(2)
        if "addendum" in title.lower():
            continue
        housekeeping_entries.append((d, title, m.start()))

    missing_footers: list[str] = []
    suppressed = 0
    for d, title, start in housekeeping_entries:
        if footer_re.search(body_of(start)):
            continue
        if is_session_footer_exception(d, title):
            suppressed += 1
            continue
        if d in footered_dates or (d + datetime.timedelta(days=1)) in footered_dates:
            suppressed += 1  # covered by the session's own closing footer
            continue
        missing_footers.append(f"{d.isoformat()} | {title[:70]}")

    wc_re = re.compile(
        r"^## \[(\d{4}-\d{2}-\d{2}) \d{2}:\d{2}[^\]]*\] workday-close \| (.+?)$",
        re.MULTILINE,
    )
    wc_missing: list[str] = []
    wc_total = 0
    for m in wc_re.finditer(text):
        try:
            datetime.date.fromisoformat(m.group(1))
        except ValueError:
            continue
        wc_total += 1
        if not re.search(r"\*Workday[^:\n]{0,80}:.+?\*", body_of(m.start()), re.DOTALL):
            wc_missing.append(f"{m.group(1)} | workday-close | {m.group(2)[:60]}")

    total = len(housekeeping_entries)
    if total + wc_total == 0:
        findings.append("- **Session metadata footers**: no housekeeping or workday-close entries yet. ✓")
        return (1, 1)
    note = (
        f" ({suppressed} suppressed: known exceptions or covered by a same/next-day closing footer)"
        if suppressed else ""
    )
    if missing_footers or wc_missing:
        findings.append(
            f"- **Session metadata footers** (housekeeping entries; addenda exempt; workday-close checked for its *Workday…* footer): "
            f"housekeeping {total - len(missing_footers) - suppressed}/{total}, workday-close {wc_total - len(wc_missing)}/{wc_total}; "
            f"**{len(missing_footers) + len(wc_missing)} missing**{note}:"
        )
        for m_str in missing_footers + wc_missing:
            findings.append(f"  - {m_str}")
    else:
        findings.append(
            f"- **Session metadata footers**: {total - suppressed}/{total} housekeeping entries and "
            f"{wc_total}/{wc_total} workday-close entries carry their footers (addenda exempt){note}. ✓"
        )
    return (total + wc_total - len(missing_footers) - len(wc_missing), total + wc_total)


# ---------------------------------------------------------------------------
# outputs/ size guard (advisory)
# ---------------------------------------------------------------------------

OUTPUTS_SIZE_THRESHOLD_MB = 200


def check_outputs_size(vault: Path, findings: list[str]) -> tuple[int, int]:
    """Advisory size guard on outputs/.

    Reports total size; when the threshold is crossed, lists the largest
    render artefacts. STRICTLY ADVISORY: this check never removes anything
    and must never be extended to remove anything. The only action it ever
    suggests is moving old renders into an `archive/` folder, and only on the
    vault owner's say-so.
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
        "This is information, not an instruction: nothing is touched automatically. "
        "If the folder feels heavy, ask Claude to move old renders into an `archive/` folder "
        "(they can be re-rendered from the markdown sources at any time), or raise the threshold "
        "in `scripts/lint-v2.py` if the working set is legitimately larger now. The 15 largest:"
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
SKILL_TOKEN_FLAG = 12_000


def check_skill_weight(vault: Path, findings: list[str]) -> tuple[int, int]:
    """Report the token weight of every installed `SKILL.md` (informational).

    Looks in two places: `skills/` inside the vault (for owners who keep their
    skills under the vault so they travel with it) and `~/.claude/skills/`
    (where the Moblee skills installer puts them). A skill loads only when it
    is invoked, so this is not part of the always-loaded tax, but a heavy skill
    on a daily pattern is a daily cost. Never trims, never blocks; both
    locations missing means a silent skip.
    """
    locations = [
        (vault / "skills", "skills/"),
        (Path.home() / ".claude" / "skills", "~/.claude/skills/"),
    ]
    weights: list[tuple[int, str]] = []
    for folder, label in locations:
        if not folder.is_dir():
            continue
        for sk in sorted(folder.glob("*/SKILL.md")):
            weights.append((est_tokens(sk), f"{label}{sk.parent.name}/SKILL.md"))
    if not weights:
        return (0, 0)
    findings.append("")
    findings.append("### Skills-layer weight (informational; never trims, never blocks)")
    findings.append(
        "Estimated tokens (chars/4) for each skill definition. A `SKILL.md` loads when its "
        "skill is invoked, so these are not part of the always-loaded cost, but a heavy skill "
        "on a daily pattern is a daily cost. Listed so the weight is visible; nothing here is "
        "an issue, and nothing is trimmed."
    )
    weights.sort(reverse=True)
    total_tok = sum(w for w, _ in weights)
    over = [(w, n) for w, n in weights if w > SKILL_TOKEN_FLAG]
    findings.append(
        f"- **{len(weights)} skill(s), ~{total_tok:,} tok in total**; "
        f"{len(over)} over the {SKILL_TOKEN_FLAG:,}-tok flag."
    )
    for tok, name in weights:
        mark = (
            f" **— over the {SKILL_TOKEN_FLAG:,}-tok flag; split-candidate "
            "(reference detail into the skill's own `references/`)**"
            if tok > SKILL_TOKEN_FLAG else ""
        )
        findings.append(f"  - `{name}` — ~{tok:,} tok{mark}")
    return (1, 1)


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
    # Identity.md is reached through CLAUDE.md's session opener, not through
    # wikilinks, and is deliberately unlinked from the graph.
    orphans = sorted(
        s for s, p in pages.items()
        if inbound[s] == 0
        and s != "Identity"
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
# Habits and tools (informational, v0.7)
# ---------------------------------------------------------------------------

HABITS_PAGE = Path("wiki") / "Wiki Operations" / "Habits and Tools.md"
HABITS_REVIEW_DAYS = 90
HABITS_WINDOW_DAYS = 30
HABITS_THRESHOLD = 3
# item key -> (what the owner has been doing, link pattern)
HABIT_SIGNALS = {
    "videos": ("video links (YouTube, Instagram, TikTok)",
               re.compile(r"https?://(?:www\.|m\.)?(?:youtube\.com/(?:watch|shorts)|youtu\.be/|instagram\.com/(?:reel|p)/|tiktok\.com/)[^\s)\]>\"']+")),
    "x-capture": ("X posts",
                  re.compile(r"https?://(?:www\.|mobile\.)?(?:x|twitter)\.com/\w+/status/\d+")),
}


_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def _parse_day(text: str) -> datetime.date | None:
    """The first date in the text, written as 2026-09-19, 19 September 2026,
    19 Sept 2026 or September 19, 2026; None if there is none."""
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
    if m:
        try:
            return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    m = re.search(r"(\d{1,2})\s+([A-Za-z]{3,9})\.?,?\s+(\d{4})", text)
    if m:
        day, mon, year = m.group(1), m.group(2), m.group(3)
    else:
        m = re.search(r"([A-Za-z]{3,9})\.?\s+(\d{1,2}),?\s+(\d{4})", text)
        if not m:
            return None
        mon, day, year = m.group(1), m.group(2), m.group(3)
    month = _MONTHS.get(mon[:3].lower())
    if not month:
        return None
    try:
        return datetime.date(int(year), month, int(day))
    except ValueError:
        return None


def _installed_now(key: str) -> bool | None:
    """Look at the Mac itself where that is cheap; None when it cannot be told."""
    if key == "videos":
        return any(Path(d, "yt-dlp").exists() for d in ("/opt/homebrew/bin", "/usr/local/bin", "/usr/bin"))
    if key == "x-capture":
        return (Path.home() / ".claude" / "skills" / "x-capture").is_dir()
    return None


def _item_installed(key: str) -> bool | None:
    """True/False when known, None when it cannot be told from here. The Mac
    itself is looked at first; the checklist's saved state is the fallback."""
    now = _installed_now(key)
    if now is not None:
        return now
    state = Path.home() / ".config" / "moblee" / "setup-state.json"
    try:
        import json
        status = json.loads(state.read_text()).get("status", {})
        if key in status:
            return bool(status[key])
    except Exception:
        pass
    return None


def check_habits(vault: Path, findings: list[str]) -> tuple[int, int]:
    """Whether the owner's setup still fits how they work. Two parts: the
    Habits and Tools page's review date (the get-started conversation fills
    it in), and links that keep arriving in the inboxes and daily notes for
    something an uninstalled item would handle. Items the owner turned down
    in the last ninety days stay quiet. Informational: every finding is a
    question for the owner, never a to-do."""
    today = datetime.date.today()
    page = vault / HABITS_PAGE
    if not page.exists():  # found by name anywhere under wiki/, as the updater does
        page = next((p for p in (vault / "wiki").rglob(HABITS_PAGE.name)), page)
    notes: list[str] = []

    declined: dict[str, datetime.date] = {}
    if not page.exists():
        notes.append("there is no Habits and Tools page; the next Moblee update adds it")
    else:
        text = page_text(page)
        fm = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
        sec = re.search(r"^## Said no to\s*$(.*?)(?=^## |\Z)", text, re.MULTILINE | re.DOTALL)
        if sec:
            # any line in the section: every `key` in backticks, and the first date on the line
            for line in sec.group(1).splitlines():
                keys = re.findall(r"`([a-z0-9-]+)`", line)
                d = _parse_day(line)
                if keys and d:
                    for k in keys:
                        declined[k] = max(d, declined.get(k, d))
        raw_reviewed = ""
        if fm:
            m = re.search(r"^last_reviewed:[ \t]*(.*)$", fm.group(1), re.MULTILINE)
            raw_reviewed = m.group(1).strip() if m else ""
        reviewed = _parse_day(raw_reviewed) if raw_reviewed else None
        quiet = "get-started" in declined and (today - declined["get-started"]).days <= HABITS_REVIEW_DAYS
        if raw_reviewed and reviewed is None:
            notes.append(f"the review date on the Habits and Tools page (`{raw_reviewed}`) could not be read; write it as 19 September 2026")
        elif quiet:
            pass
        elif reviewed is None:
            notes.append("the \"get me started\" conversation has not been held yet; offer it to the owner once, and record a no as `get-started` under \"Said no to\"")
        elif (today - reviewed).days > HABITS_REVIEW_DAYS:
            notes.append(f"the setup was last reviewed on {reviewed.strftime('%-d %B %Y')}; offer the owner a setup review once, and record a no as `get-started` under \"Said no to\"")

    roots = [vault / "raw", vault / "Clippings", vault / "Daily Notes"]
    cutoff = datetime.datetime.now().timestamp() - HABITS_WINDOW_DAYS * 86400
    seen: dict[str, set[str]] = {k: set() for k in HABIT_SIGNALS}
    for root in roots:
        if not root.is_dir():
            continue
        for f in root.rglob("*.md"):
            try:
                if f.stat().st_mtime < cutoff:
                    continue
            except OSError:
                continue
            body = page_text(f)
            for key, (_, rx) in HABIT_SIGNALS.items():
                seen[key].update(rx.findall(body))

    for key, (what, _) in HABIT_SIGNALS.items():
        count = len(seen[key])
        said_no = key in declined and (today - declined[key]).days <= HABITS_REVIEW_DAYS
        if count < HABITS_THRESHOLD or said_no or _item_installed(key) is not False:
            continue
        notes.append(f"{count} {what} arrived in the last {HABITS_WINDOW_DAYS} days and the `{key}` item is not installed; ask the owner whether they want it")

    if notes:
        findings.append("- **Habits and tools (informational; questions for the owner, never to-dos)**:")
        for n in notes:
            findings.append(f"  - {n}.")
    else:
        findings.append("- **Habits and tools**: the setup fits what the vault shows.")
    return (1, 1)  # informational: questions for the owner, never counted as issues


# ---------------------------------------------------------------------------
# Prose boilerplate sweep (informational)
# ---------------------------------------------------------------------------

# Stock phrases that announce rather than say anything.
BOILERPLATE_OPENER_RE = re.compile(
    r"(It is important to note|It is worth (noting|mentioning)|It should be noted|"
    r"In today's (rapidly )?(changing|evolving|fast-paced)|This highlights the importance|"
    r"This underscores the importance|By understanding [A-Za-z]+, we can|"
    r"Ultimately, the key takeaway|serves as a testament|plays a (crucial|vital|key) role|"
    r"It is essential to (note|understand|recognise|recognize))",
    re.IGNORECASE,
)

# Paragraph-initial connectives. Mid-sentence "however" is ordinary English; the
# tell is the reflex of opening a paragraph with a transition word that the
# adjacency already implies.
TRANSITION_OPENER_RE = re.compile(
    r"^(\*\*)?(Furthermore|Moreover|Additionally|However|Consequently|Therefore|"
    r"In conclusion|Notably|Importantly|Overall)\b[,:]?",
)

# Fixed-schema operational files the sweep leaves alone: the schema file and
# the working-state bullets are not prose, and the lint's own reports quote
# the very phrases it hunts.
PROSE_GUARD_SKIP = {
    "CLAUDE.md",
    "wiki/_context.md",
}
PROSE_GUARD_SKIP_DIRS = ("/outputs/lint/", "/Ghost Reconstructions/")


def check_prose_boilerplate(vault: Path, findings: list[str]) -> tuple[int, int]:
    """Forced-look sweep (informational): lists stock openers and
    paragraph-initial transition words in wiki pages and outputs/ markdown
    modified in the last 7 days (the log's entry bodies included). Catches
    the mechanical tells only; structural symmetry, forced triads and low
    density are not greppable and stay a judgement call. Never rewrites."""
    cutoff = datetime.datetime.now().timestamp() - 7 * 86400
    roots = [vault / "wiki", vault / "outputs"]
    hits: list[str] = []
    scanned = 0
    for root in roots:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.md")):
            rel = path.relative_to(vault).as_posix()
            if rel in PROSE_GUARD_SKIP:
                continue
            if any(d in f"/{rel}" for d in PROSE_GUARD_SKIP_DIRS):
                continue
            try:
                if path.stat().st_mtime < cutoff:
                    continue
            except OSError:
                continue
            scanned += 1
            text = page_text(path)
            for lineno, line in enumerate(text.splitlines(), start=1):
                stripped = line.strip()
                if not stripped or stripped.startswith((">", "|", "#", "```")):
                    continue
                m = BOILERPLATE_OPENER_RE.search(stripped) or TRANSITION_OPENER_RE.match(stripped)
                if m:
                    hits.append(
                        f"`{rel}`:{lineno} — …{stripped[max(m.start() - 20, 0):m.start() + 90]}…"
                    )
                if len(hits) >= 20:
                    break
            if len(hits) >= 20:
                break
        if len(hits) >= 20:
            break
    if hits:
        findings.append(
            f"- **Prose boilerplate (last 7 days, informational)**: {len(hits)} instance(s) across {scanned} recently-modified file(s) "
            "— stock openers and paragraph-initial transitions; rewrite or justify each (capped at 20):"
        )
        for h in hits:
            findings.append(f"  - {h}")
    else:
        findings.append(
            f"- **Prose boilerplate (last 7 days)**: none found across {scanned} recently-modified file(s). ✓"
        )
    return (1, 1)


# The two habits The Economist's corpus study (30 July 2026) found Claude uses
# more than people do: stock contrast constructions, and long Latinate words.
# Counted per file and scaled per 1,000 words, because one "not X but Y" is
# ordinary English and the tell is the density.
CONTRAST_RE = re.compile(
    r"\bnot only\b[^.]{0,120}?\bbut (?:also )?\b"          # not only ... but also
    r"|\bnot (?:a |an |the )?[\w'-]+(?: [\w'-]+){0,5},? but\b"  # not X but Y
    r"|\w, not (?:a |an |the |its |his |their )?[a-z][\w'-]+",   # X, not Y
    re.IGNORECASE,
)
# The study's own examples, then a few long-standing model favourites.
FANCY_WORD_RE = re.compile(
    r"\b(significant(?:ly)?|increasingly|consequences|methodolog(?:y|ies)|parameters?|"
    r"interdependence|reindustriali[sz]ation|robust|pivotal|underscores?|multifaceted|"
    r"utili[sz]e[sd]?|facilitat(?:e|es|ed|ing))\b",
    re.IGNORECASE,
)
AI_TELL_CONTRAST_PER_K = 4.0   # contrast constructions per 1,000 words before a file is listed
AI_TELL_FANCY_PER_K = 3.0      # listed words per 1,000 words before a file is listed


def check_ai_writing_tells(vault: Path, findings: list[str]) -> tuple[int, int]:
    """Density sweep (informational, v0.5.1), from The Economist's study "How to
    spot AI writing" (30 July 2026): lists wiki and outputs/ markdown modified in
    the last 7 days whose rate of contrast constructions ("not X but Y", "not
    only... but also", "X, not Y") or listed Latinate words runs above the
    thresholds, with counts and one example each. Quoted passages are prose of
    their own and are skipped. Never rewrites."""
    cutoff = datetime.datetime.now().timestamp() - 7 * 86400
    listed: list = []
    scanned = 0
    for root in (vault / "wiki", vault / "outputs"):
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.md")):
            rel = path.relative_to(vault).as_posix()
            if rel in PROSE_GUARD_SKIP or any(d in f"/{rel}" for d in PROSE_GUARD_SKIP_DIRS):
                continue
            if rel in ("wiki/Identity.md", "wiki/log.md"):
                continue  # Identity.md is never quoted back at the owner; the log is fixed-format record
            try:
                if path.stat().st_mtime < cutoff:
                    continue
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            prose = "\n".join(
                l for l in text.splitlines()
                if l.strip() and not l.strip().startswith((">", "|", "#", "```", "---", "Source:"))
            )
            prose = re.sub(r'"[^"\n]{0,300}"|“[^”\n]{0,300}”', " ", prose)  # quoted words are the source's
            words = len(prose.split())
            if words < 150:
                continue
            scanned += 1
            contrasts = list(CONTRAST_RE.finditer(prose))
            fancy = list(FANCY_WORD_RE.finditer(prose))
            c_rate, f_rate = 1000 * len(contrasts) / words, 1000 * len(fancy) / words
            if c_rate >= AI_TELL_CONTRAST_PER_K or f_rate >= AI_TELL_FANCY_PER_K:
                ex = contrasts[0] if contrasts else fancy[0]
                snippet = prose[max(ex.start() - 30, 0):ex.end() + 30].replace("\n", " ")
                listed.append((max(c_rate, f_rate), f"`{rel}`: {len(contrasts)} contrast ({c_rate:.1f}/1k), "
                               f"{len(fancy)} listed words ({f_rate:.1f}/1k), {words} words; e.g. …{snippet}…"))
    if listed:
        listed.sort(reverse=True)
        findings.append(
            f"- **AI-writing tells (last 7 days, informational)**: {len(listed)} of {scanned} recently-modified file(s) "
            f"over {AI_TELL_CONTRAST_PER_K:g} contrast constructions or {AI_TELL_FANCY_PER_K:g} listed Latinate words per 1,000 words; "
            "read and rewrite where the habit is doing the work instead of the argument (top 15):"
        )
        for _, line in listed[:15]:
            findings.append(f"  - {line}")
    else:
        findings.append(f"- **AI-writing tells (last 7 days)**: no file over the thresholds across {scanned} recently-modified file(s). ✓")
    return (1, 1)


# ---------------------------------------------------------------------------
# Duplicate frontmatter blocks (advisory)
# ---------------------------------------------------------------------------

DUP_FM_SCAN_LINES = 40      # how far past the real frontmatter to look
DUP_FM_MAX_BLOCK = 25       # a plausible inert block closes within this many lines


def _yaml_mapping_keys(block: list[str]) -> list[str] | None:
    """Keys of the block if it parses as a non-empty YAML mapping, else None.

    With PyYAML absent, a line-shape test stands in: every non-blank line is
    either `key: value` or an indented / list continuation of one.
    """
    if HAVE_YAML:
        try:
            parsed = yaml.safe_load("\n".join(block))
        except yaml.YAMLError:
            return None
        if isinstance(parsed, dict) and parsed:
            return [str(k) for k in parsed]
        return None
    keys: list[str] = []
    for line in block:
        if not line.strip():
            continue
        m = re.match(r"^([A-Za-z0-9_-]+):(\s|$)", line)
        if m:
            keys.append(m.group(1))
        elif line.startswith((" ", "\t", "- ")):
            continue
        else:
            return None
    return keys or None


def check_duplicate_frontmatter(vault: Path, findings: list[str]) -> tuple[int, int]:
    """Flag a second `---` delimited YAML block shortly after the real
    frontmatter. Obsidian parses only the first, so the second is inert and
    renders as body text; when its values contradict the real block, every
    schema check passes on values the page does not display. A pair of `---`
    rules enclosing non-YAML prose is not counted, nor is a block inside a
    code fence (documentation of the syntax, not frontmatter)."""
    wiki = vault / "wiki"
    if not wiki.is_dir():
        findings.append("- **Duplicate frontmatter blocks**: skipped — wiki/ missing.")
        return (0, 0)

    issues: list[str] = []
    total = 0
    for path in sorted(wiki.rglob("*.md")):
        lines = _head_lines(path, DUP_FM_SCAN_LINES + DUP_FM_MAX_BLOCK + 4)
        if not lines or lines[0].strip() != "---":
            continue
        close = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
        if close is None:
            continue
        total += 1
        window = lines[close + 1 : close + 1 + DUP_FM_SCAN_LINES + DUP_FM_MAX_BLOCK]
        fenced: list[bool] = []
        in_fence = False
        for line in window:
            s = line.strip()
            if s.startswith("```") or s.startswith("~~~"):
                fenced.append(True)
                in_fence = not in_fence
                continue
            fenced.append(in_fence)

        def is_delim(x: int) -> bool:
            return window[x].rstrip() == "---" and not fenced[x]

        opens = [j for j in range(min(DUP_FM_SCAN_LINES, len(window))) if is_delim(j)]
        for j in opens:
            k = next((x for x in range(j + 1, min(j + 1 + DUP_FM_MAX_BLOCK, len(window)))
                      if is_delim(x)), None)
            if k is None:
                continue
            block = window[j + 1 : k]
            if not any(b.strip() for b in block):
                continue  # two adjacent horizontal rules, nothing enclosed
            keys = _yaml_mapping_keys(block)
            if keys:
                lineno = close + j + 2   # 1-based line of the second block's opener
                issues.append(
                    f"`{path.relative_to(vault).as_posix()}:{lineno}` — second `---` block "
                    f"{lineno - (close + 1)} line(s) after the real frontmatter closes; "
                    f"inert, renders as body text. Keys: {', '.join(keys[:6])[:80]}"
                )
            break  # one report per page is enough to force the look

    if total == 0:
        findings.append("- **Duplicate frontmatter blocks**: no pages carry frontmatter yet. ✓")
        return (1, 1)
    if issues:
        findings.append(
            f"- **Duplicate frontmatter blocks**: **{len(issues)} page(s) with a second block** "
            f"(of {total} carrying frontmatter) — reconcile the two and remove the inert one:"
        )
        for i in issues:
            findings.append(f"  - {i}")
    else:
        findings.append(
            f"- **Duplicate frontmatter blocks**: none across {total} page(s) carrying frontmatter. ✓"
        )
    return (total - len(issues), total)


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

    # Typed folders with a fixed frontmatter schema. Daily notes carry at
    # least a `date` (the template sets it). Add a line per folder the vault
    # owner adopts; a missing folder skips silently.
    pass_, tot = check_frontmatter_schema(vault, findings, "Daily Notes", ["date"], "Daily note")
    scorecard.append(("Daily-note frontmatter", pass_, tot))

    pass_, tot = check_index_domains_coverage(vault, findings)
    scorecard.append(("Index.md Domains coverage", pass_, tot))

    pass_, tot = check_log_timestamps(vault, findings)
    scorecard.append(("Log header format and timestamp ordering", pass_, tot))

    pass_, tot = check_log_session_metadata(vault, findings)
    scorecard.append(("Housekeeping session-metadata footers", pass_, tot))

    pass_, tot = check_outputs_size(vault, findings)
    scorecard.append(("outputs/ size guard (advisory, never removes files)", pass_, tot))

    pass_, tot = check_vault_weight(vault, findings)
    scorecard.append(("Vault weight (token caps, advisory, never trims)", pass_, tot))

    pass_, tot = check_skill_weight(vault, findings)
    scorecard.append(("Skills-layer weight (informational)", pass_, tot))

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

    pass_, tot = check_prose_boilerplate(vault, findings)
    scorecard.append(("Prose boilerplate sweep (informational)", pass_, tot))

    pass_, tot = check_ai_writing_tells(vault, findings)
    scorecard.append(("AI-writing tells sweep (informational)", pass_, tot))

    pass_, tot = check_correction_rate(vault, findings)
    scorecard.append(("Correction rate (informational)", pass_, tot))

    pass_, tot = check_duplicate_frontmatter(vault, findings)
    scorecard.append(("Duplicate frontmatter blocks (advisory)", pass_, tot))

    pass_, tot = check_habits(vault, findings)
    scorecard.append(("Habits and tools (informational)", pass_, tot))

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

    if LOG_TIMESTAMP_EXCEPTIONS or SESSION_FOOTER_EXCEPTIONS:
        findings.append("")
        findings.append("## Known accepted exceptions")
        findings.append("")
        findings.append(
            "Entries the structural checks would otherwise flag, that cannot be rewritten without violating the `Append-only log` hard rule. Listed here for transparency; the checks above subtract these from the issue counts. Review at each lint; remove an entry only if the underlying state is corrected at the source."
        )
        findings.append("")
        if LOG_TIMESTAMP_EXCEPTIONS:
            findings.append("**Log timestamp exceptions:**")
            findings.append("")
            for e in LOG_TIMESTAMP_EXCEPTIONS:
                findings.append(f"- `{e['date']}` `{e['title_prefix']}` — {e['reason']}")
            findings.append("")
        if SESSION_FOOTER_EXCEPTIONS:
            findings.append("**Session footer exceptions:**")
            findings.append("")
            for e in SESSION_FOOTER_EXCEPTIONS:
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
