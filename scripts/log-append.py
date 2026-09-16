#!/usr/bin/env python3
"""log-append.py — the one way a log entry gets written.

Hand-composed log headers drift: a timestamp copied from earlier in the
session, a date-only header, three spellings of the same timezone. This
appender reads the system clock itself, emits the one canonical header form
(`## [YYYY-MM-DD HH:MM ±TZ] type | Title`), validates before touching the
log, and appends in a single write to the end of wiki/log.md, so the
compose-ahead error class retires.

Usage, from anywhere (the vault is found by the Moblee convention):
    python3 scripts/log-append.py --type tooling --title "Title text" \
        --body-file /path/to/body.md          # or --body "inline text"
    ... --dry-run    prints the entry instead of appending

The body should NOT include the header line; it is generated. The known type
taxonomy is advisory: an unknown type warns but does not block (a log has
legitimate rare types), unless --strict is passed.

Vault detection, in order of precedence:
  1. the MOBLEE_VAULT environment variable (absolute path to the vault);
  2. ~/.config/moblee/vault-path (a single line holding the absolute
     vault path — the Moblee installer writes this);
  3. walking up from the current working directory looking for a
     directory that contains wiki/Index.md.
"""
from __future__ import annotations

import argparse
import datetime
import os
import sys
from pathlib import Path

KNOWN_TYPES = {
    "ingest", "housekeeping", "tooling", "schema", "lint", "correction",
    "initialised", "workday-close", "render", "compact", "interview", "capture",
}


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


def header_now(entry_type: str, title: str) -> str:
    now = datetime.datetime.now().astimezone()
    offset = now.strftime("%z")[:3]  # +0100 -> +01
    return f"## [{now.strftime('%Y-%m-%d %H:%M')} {offset}] {entry_type} | {title}"


def main() -> int:
    ap = argparse.ArgumentParser(description="Append one correctly-stamped entry to wiki/log.md.")
    ap.add_argument("--type", required=True, dest="entry_type", help="entry type, e.g. ingest, housekeeping, tooling")
    ap.add_argument("--title", required=True, help="the entry title (no header markup)")
    ap.add_argument("--body-file", help="file holding the entry body (no header line)")
    ap.add_argument("--body", help="inline entry body (no header line)")
    ap.add_argument("--dry-run", action="store_true", help="print the entry instead of appending it")
    ap.add_argument("--strict", action="store_true", help="refuse a type outside the known taxonomy")
    args = ap.parse_args()

    title = args.title.strip()
    if not title:
        print("error: empty title", file=sys.stderr)
        return 1
    if "\n" in title:
        print("error: title must be a single line", file=sys.stderr)
        return 1

    if args.entry_type not in KNOWN_TYPES:
        msg = f"type {args.entry_type!r} is outside the known taxonomy {sorted(KNOWN_TYPES)}"
        if args.strict:
            print(f"error: {msg}", file=sys.stderr)
            return 1
        print(f"warning: {msg} — proceeding", file=sys.stderr)

    if args.body_file:
        try:
            body = Path(args.body_file).read_text(encoding="utf-8")
        except OSError as e:
            print(f"error: cannot read --body-file: {e}", file=sys.stderr)
            return 1
    elif args.body is not None:
        body = args.body
    elif args.dry_run:
        body = "(body)"
    else:
        print("error: provide --body-file or --body", file=sys.stderr)
        return 1
    body = body.strip("\n")
    if body.startswith("## ["):
        print("error: body begins with a header line — the header is generated, strip it", file=sys.stderr)
        return 1

    header = header_now(args.entry_type, title)
    entry = f"\n{header}\n\n{body}\n"
    if args.dry_run:
        print(entry)
        return 0

    vault = find_vault_root()
    log = vault / "wiki" / "log.md"
    if not log.exists():
        print(f"error: {log} missing", file=sys.stderr)
        return 1
    # One write call in append mode: the entry lands whole at the end of the
    # file, never interleaved with another writer's output.
    with log.open("a", encoding="utf-8") as f:
        f.write(entry)
    print(f"appended: {header[:100]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
