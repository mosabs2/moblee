#!/usr/bin/env python3
"""
Maintain the KNOWN_SAFE_SHA256 block in safety/bash-guard.py.

The guard scans every script file a command runs and blocks on deletion or
clobber primitives. The pack's own tooling contains such primitives for
legitimate reasons (install-safety.py carries the rm -rf test payload and
os.replace; update.sh writes wiki/Identity.md; render.py unlinks its temp
files), so the guard skips the file scan for a file whose SHA-256 is listed.
The command line around the file is still scanned.

Usage (from anywhere):
  python3 safety/release-hashes.py          rewrite the block for FILES as they are now
  python3 safety/release-hashes.py --check  exit 1 listing files whose hash differs
                                            from the block (a release must not ship
                                            with stale hashes)
  python3 safety/release-hashes.py --table  for each listed file, say whether the
                                            guard skips it by hash, would pass the
                                            scan anyway, or would block without the
                                            hash (with the first reason)

This file is deliberately NOT in the list; the guard itself is not either.
"""
import hashlib
import importlib.util
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.dirname(HERE)
GUARD = os.path.join(HERE, "bash-guard.py")
BEGIN = "# --- KNOWN_SAFE begin ---"
END = "# --- KNOWN_SAFE end ---"

FILES = [
    "scripts/install.sh",
    "scripts/update.sh",
    "scripts/install-skills.sh",
    "scripts/install-schedule.sh",
    "scripts/install-learning-path.py",
    "learning-path/moblee-tip.sh",
    "scripts/lint-v2.py",
    "scripts/vault-gate.py",
    "scripts/log-append.py",
    "scripts/vault-orient-preflight.sh",
    "scripts/patch-claude-md.py",
    "scripts/seed-memory.py",
    "scripts/add-identity.py",
    "scripts/vault.sh",
    "scripts/hooks/pre-commit",
    "scripts/hooks/post-commit",
    "scripts/cadence/run-weekly-lint.sh",
    "scripts/wiki-galaxy/build.py",
    "dashboard/server.py",
    "safety/install-safety.py",
    "safety/test-guard.py",
    "voice/install-voice.py",
    "skills/wiki-to-pdf/render.py",
]
ENTRY_RE = re.compile(r'"([0-9a-f]{64})":\s*"([^"]*)"')


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def current_hashes():
    """rel → hex for files that exist; rel → None for missing ones."""
    out = {}
    for rel in FILES:
        p = os.path.join(PACK, rel)
        out[rel] = sha256(p) if os.path.isfile(p) else None
    return out


def read_guard():
    with open(GUARD, "r", encoding="utf-8") as fh:
        return fh.read()


def block_bounds(text):
    a = text.find(BEGIN)
    b = text.find(END)
    if a == -1 or b == -1 or b < a:
        sys.stderr.write("release-hashes: markers not found in %s\n" % GUARD)
        sys.exit(2)
    return a, b


def read_block(text):
    a, b = block_bounds(text)
    return {hexd: rel for hexd, rel in ENTRY_RE.findall(text[a:b])}


def render_block(hashes):
    lines = [BEGIN, "KNOWN_SAFE_SHA256 = {"]
    for rel in sorted(r for r, h in hashes.items() if h):
        lines.append('    "%s": "%s",' % (hashes[rel], rel))
    lines.append("}")
    lines.append(END)
    return "\n".join(lines)


def write_block():
    hashes = current_hashes()
    text = read_guard()
    a, b = block_bounds(text)
    new = text[:a] + render_block(hashes) + text[b + len(END):]
    with open(GUARD, "w", encoding="utf-8") as fh:
        fh.write(new)
    n = sum(1 for h in hashes.values() if h)
    print("release-hashes: wrote %d hashes into %s" % (n, os.path.relpath(GUARD, PACK)))
    for rel, h in hashes.items():
        if not h:
            print("  WARNING missing on disk, not listed: %s" % rel)
    return 0


def check():
    hashes = current_hashes()
    listed = read_block(read_guard())          # hex → rel
    listed_by_rel = {rel: hexd for hexd, rel in listed.items()}
    problems = []
    for rel, h in hashes.items():
        if h is None:
            problems.append("missing on disk: %s" % rel)
        elif listed_by_rel.get(rel) != h:
            problems.append("stale or absent hash: %s" % rel)
    for rel in listed_by_rel:
        if rel not in hashes:
            problems.append("listed in the block but not in FILES: %s" % rel)
    if problems:
        print("release-hashes --check: %d problem(s)" % len(problems))
        for p in problems:
            print("  " + p)
        return 1
    print("release-hashes --check: all %d hashes current" % len(listed))
    return 0


def load_guard():
    spec = importlib.util.spec_from_file_location("bash_guard", GUARD)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def find_vault_above(start):
    p = start
    while True:
        if os.path.isfile(os.path.join(p, "CLAUDE.md")) and os.path.isdir(os.path.join(p, "wiki")):
            return p
        parent = os.path.dirname(p)
        if parent == p:
            return None
        p = parent


def table():
    g = load_guard()
    rows = []
    entries = [(PACK, rel, rel) for rel in FILES]
    vault = find_vault_above(os.path.dirname(PACK))
    if vault:
        entries.append((vault, "scripts/vault-orient-preflight.sh",
                        "(vault) scripts/vault-orient-preflight.sh"))
    known = dict(g.KNOWN_SAFE_SHA256)
    for root, rel, label in entries:
        path = os.path.join(root, rel)
        if not os.path.isfile(path):
            rows.append((label, "missing on disk", ""))
            continue
        skipped = sha256(path) in known
        g.STATE["cwd"] = root
        g.STATE["vault"] = root
        g.STATE["files"] = 0
        g.KNOWN_SAFE_SHA256 = {}
        invoker = "python" if rel.endswith(".py") else "shell"
        try:
            reason = g.scan_file(path, invoker, 0)
        finally:
            g.KNOWN_SAFE_SHA256 = known
        if skipped:
            status = "(a) skipped by hash" + (" [would pass anyway]" if not reason
                                              else " [would block without it]")
        elif reason:
            status = "(c) would block without the hash"
        else:
            status = "(b) passes the scan anyway"
        rows.append((label, status, (reason or "").replace(root + "/", "")))
    w = max(len(r[0]) for r in rows)
    for label, status, reason in rows:
        line = "%-*s  %s" % (w, label, status)
        if reason:
            line += "  --  " + reason[:120]
        print(line)
    return 0


def main():
    if "--check" in sys.argv[1:]:
        sys.exit(check())
    if "--table" in sys.argv[1:]:
        sys.exit(table())
    sys.exit(write_block())


if __name__ == "__main__":
    main()
