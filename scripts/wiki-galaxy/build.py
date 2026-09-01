#!/usr/bin/env python3
"""Wiki Galaxy — render a Moblee wiki vault as an interactive 3D knowledge galaxy.

Walks the vault's wiki/ folder (plus Daily Notes/, if you keep one), resolves
wikilinks into a graph, and writes a fully offline viewer to
<vault>/outputs/galaxy/ (open index.html straight in a browser — no server,
no CDN, no keys). The Moblee dashboard's Galaxy button runs this build and
serves the result at /galaxy/.

Privacy: wiki/Private/ is excluded entirely at build time (no nodes, no
titles), as is any page carrying a `restricted:` frontmatter marker — belt
and braces. log.md is excluded so chronology doesn't distort the knowledge
structure.

Groups are derived from the vault itself: Index.md is the sun, top-level
wiki pages are the core, Wiki Operations and _context.md are operations,
Daily Notes are dust, and every other wiki/ subfolder gets its own colour
from a fixed palette automatically — no per-vault configuration needed.

Adapted from the AI Workshop "Brain Studio" build script (Zubair Trabzada),
rebuilt for the Moblee vault structure and conventions.

Usage:  python3 scripts/wiki-galaxy/build.py
The vault is found via the MOBLEE_VAULT environment variable, then
~/.config/moblee/vault-path (the Moblee installer writes this), then by
walking up from the current directory looking for wiki/Index.md.
"""
import json
import os
import re
import shutil
import sys
import time


def find_vault():
    """Locate the vault root, or exit with a plain-English error."""
    def looks_like_vault(p):
        return os.path.isfile(os.path.join(p, "wiki", "Index.md"))

    env = os.environ.get("MOBLEE_VAULT", "").strip()
    if env:
        p = os.path.abspath(os.path.expanduser(env))
        if looks_like_vault(p):
            return p
        sys.exit("MOBLEE_VAULT points at %r, but that folder does not look "
                 "like a Moblee vault (there is no wiki/Index.md inside it). "
                 "Fix or unset MOBLEE_VAULT and try again." % env)
    cfg = os.path.expanduser("~/.config/moblee/vault-path")
    if os.path.isfile(cfg):
        try:
            with open(cfg, encoding="utf-8") as f:
                p = f.readline().strip()
        except OSError:
            p = ""
        if p:
            p = os.path.abspath(os.path.expanduser(p))
            if looks_like_vault(p):
                return p
    d = os.getcwd()
    while True:
        if looks_like_vault(d):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    sys.exit("Could not find your vault. Either run this from inside the "
             "vault folder, or set the MOBLEE_VAULT environment variable to "
             "the vault's full path, or put that path on the first line of "
             "~/.config/moblee/vault-path (the Moblee installer normally "
             "writes that file for you). A vault is any folder containing "
             "wiki/Index.md.")


PKG = os.path.dirname(os.path.abspath(__file__))
VAULT = find_vault()
OUT = os.path.join(VAULT, "outputs", "galaxy")

# Excluded at build time — never indexed, never named.
EXCLUDE_DIRS = {
    os.path.join("wiki", "Private"),
}
EXCLUDE_FILES = {os.path.join("wiki", "log.md")}
RESTRICTED_RE = re.compile(r"^restricted:", re.M)

# Fixed structural groups. Colour, radius, glow, display name, major (labels).
BASE_GROUPS = {
    "sun":   {"c": "#f5d76e", "r": 13,  "glow": 34, "name": "Index",      "major": True},
    "core":  {"c": "#e7e5e4", "r": 7,   "glow": 16, "name": "Wiki pages", "major": True},
    "meta":  {"c": "#94a3b8", "r": 5,   "glow": 10, "name": "Operations", "major": False},
    "daily": {"c": "#3e4c63", "r": 2.2, "glow": 0,  "name": "Daily Notes", "major": False},
}
# Every other wiki/ subfolder is assigned one of these automatically
# (deterministic: sorted folder order), cycling if there are more folders.
SUBFOLDER_PALETTE = ["#fb923c", "#4ade80", "#22d3ee", "#e879f9", "#a78bfa",
                     "#f87171", "#facc15", "#60a5fa", "#2dd4bf", "#f472b6"]

WIKILINK = re.compile(r"\[\[([^\]|#]+)(?:[|#][^\]]*)?\]\]")


def excluded(rel):
    if rel in EXCLUDE_FILES:
        return True
    return any(rel == d or rel.startswith(d + os.sep) for d in EXCLUDE_DIRS)


def collect():
    files = []
    for base in ("wiki", "Daily Notes"):
        root_dir = os.path.join(VAULT, base)
        if not os.path.isdir(root_dir):
            continue
        for root, dirs, names in os.walk(root_dir):
            # Sorted walk: duplicate-basename resolution in stem_map is
            # first-wins, so the walk order must be deterministic.
            dirs[:] = sorted(d for d in dirs if not d.startswith("."))
            names = sorted(names)
            for n in names:
                if not n.endswith(".md"):
                    continue
                rel = os.path.relpath(os.path.join(root, n), VAULT)
                if not excluded(rel):
                    files.append(rel)
    return files


def build_groups(files):
    """BASE_GROUPS plus one auto-coloured group per wiki/ subfolder seen."""
    groups = dict(BASE_GROUPS)
    folder_group = {"Wiki Operations": "meta"}
    subs = sorted({parts[1] for parts in (rel.split(os.sep) for rel in files)
                   if parts[0] == "wiki" and len(parts) > 2
                   and parts[1] not in folder_group})
    for i, sub in enumerate(subs):
        key = "sub%d" % i
        groups[key] = {"c": SUBFOLDER_PALETTE[i % len(SUBFOLDER_PALETTE)],
                       "r": 4.5, "glow": 8, "name": sub, "major": False}
        folder_group[sub] = key
    return groups, folder_group


def group_of(rel, folder_group):
    parts = rel.split(os.sep)
    if parts[0] == "Daily Notes":
        return "daily"
    if rel == os.path.join("wiki", "Index.md"):
        return "sun"
    if rel == os.path.join("wiki", "_context.md"):
        return "meta"
    if len(parts) == 2:
        return "core"
    return folder_group.get(parts[1], "core")


def preview_of(text):
    if text.startswith("---"):
        end = text.find("---", 3)
        text = text[end + 3:] if end > 0 else text
    lines = [l.strip() for l in text.splitlines()
             if l.strip() and not l.strip().startswith(("#", "|", "---", "<!--", "> "))]
    body = " ".join(lines)
    body = re.sub(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", r"\1", body)
    body = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", body)
    body = re.sub(r"[*_`>]+", "", body)
    body = re.sub(r"\s+", " ", body).strip()
    return (body[:700] + "…") if len(body) > 700 else body


def build():
    files = collect()
    if not files:
        sys.exit("no markdown files found — is this really a vault with a wiki/ folder?")

    groups, folder_group = build_groups(files)

    stem_map = {}
    for rel in files:
        stem_map.setdefault(os.path.splitext(os.path.basename(rel))[0].lower(), rel)
        # Path-form wikilinks ([[Daily Notes/2026-05-22]], [[Subfolder/Page]])
        # never match the basename-only map, so index the slash-path stem too.
        stem_map.setdefault(os.path.splitext(rel)[0].replace(os.sep, "/").lower(), rel)

    nodes, links, skipped_restricted = {}, set(), 0
    read_failures = 0
    now = time.time()
    for rel in files:
        try:
            text = open(os.path.join(VAULT, rel), encoding="utf-8", errors="ignore").read()
        except OSError:
            read_failures += 1
            continue
        fm = text[3:text.find("---", 3)] if text.startswith("---") else ""
        if RESTRICTED_RE.search(fm):
            skipped_restricted += 1
            continue
        try:
            days = max(0, int((now - os.path.getmtime(os.path.join(VAULT, rel))) // 86400))
        except OSError:
            days = 9999
        nodes[rel] = {"g": group_of(rel, folder_group), "p": preview_of(text),
                      "days": days}
        for m in WIKILINK.finditer(text):
            tgt = stem_map.get(m.group(1).strip().lower())
            if tgt and tgt != rel:
                links.add(tuple(sorted((rel, tgt))))       # undirected, deduped
    links = {(a, b) for a, b in links if a in nodes and b in nodes}

    order = {g: i for i, g in enumerate(groups)}
    ordered = sorted(nodes.items(), key=lambda kv: (order.get(kv[1]["g"], 99), kv[0]))
    index = {rel: i for i, (rel, _) in enumerate(ordered)}
    out_nodes = [{"id": rel.replace(os.sep, "/"),
                  "label": os.path.splitext(os.path.basename(rel))[0],
                  "g": n["g"], "p": n["p"], "days": n["days"]}
                 for rel, n in ordered]
    out_links = [{"s": index[a], "t": index[b]} for a, b in sorted(links)]

    orphans = sum(1 for rel in nodes if not any(rel in pair for pair in links))
    brand = {"name": os.path.basename(VAULT).upper(),
             "vault": os.path.basename(VAULT)}

    os.makedirs(OUT, exist_ok=True)
    stamp = int(time.time())
    html = open(os.path.join(PKG, "viewer", "galaxy.html"), encoding="utf-8").read()
    html = html.replace("graph-data.js", f"graph-data.js?v={stamp}", 1)
    open(os.path.join(OUT, "index.html"), "w", encoding="utf-8").write(html)
    shutil.copy(os.path.join(PKG, "vendor", "galaxy-libs.min.js"), OUT)
    with open(os.path.join(OUT, "graph-data.js"), "w") as f:
        f.write("const GRAPH = ")
        json.dump({"brand": brand, "groups": groups, "nodes": out_nodes,
                   "links": out_links}, f)
        f.write(";\n")

    fail_note = f" · {read_failures} UNREADABLE FILES DROPPED (graph is partial)" if read_failures else ""
    print(f"✓ {len(out_nodes)} pages · {len(out_links)} links · {orphans} orphans"
          f" · {skipped_restricted} restricted pages excluded by frontmatter{fail_note}")
    print(f"✓ output: {OUT}  (open index.html in a browser — fully offline)")


if __name__ == "__main__":
    build()
