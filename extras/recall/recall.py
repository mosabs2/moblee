#!/usr/bin/env python3
"""recall.py - search the wiki by meaning, not only by the exact word.

Moblee's optional memory search (the "Memory search" item). Every section of
every page is turned into a vector by a small model running on this Mac
(Ollama, nomic-embed-text, on 127.0.0.1 only), and a question is matched
against them. Nothing leaves the Mac, nothing is sent to anyone, and the index
is a disposable cache outside the wiki (under ~/.cache/moblee-recall/, one
folder per wiki) that can be rebuilt at any time; the markdown stays the only
record.

    python3 recall.py rebuild            # read the wiki and (re)build the index; only changed sections are embedded
    python3 recall.py rebuild --full     # embed everything again
    python3 recall.py "your question"    # the closest sections, readable
    python3 recall.py --json "question"  # the same as JSON, for the hook
    python3 recall.py status             # how big and how old the index is

The wiki is found the Moblee way: MOBLEE_VAULT, then ~/.config/moblee/vault-path,
then this file's own place (<wiki>/scripts/recall/recall.py). Pages under a
folder named Private or Ghost Reconstructions (by their real path, through any
link, in any spelling of the case), and any page whose front matter carries a
`restricted:` key, are never indexed; a memory that links to such a page is
left out too. Only the Python that comes with the Mac is needed: no numpy, no
torch, no key.
"""
from __future__ import annotations

import array
import fcntl
import glob
import hashlib
import json
import math
import operator
import os
import re
import sys
import time
import urllib.request

OLLAMA = os.environ.get("MOBLEE_OLLAMA", "http://127.0.0.1:11434")
MODEL = "nomic-embed-text"
EXCLUDE_DIRS = ("private", "ghost reconstructions")   # compared case-folded
STUB = os.environ.get("MOBLEE_EMBED_STUB") == "1"   # the test suite's stand-in for the model


def find_vault() -> str | None:
    cands = []
    v = os.environ.get("MOBLEE_VAULT")
    if v:
        cands.append(v)
    try:
        with open(os.path.expanduser("~/.config/moblee/vault-path"), encoding="utf-8") as fh:
            cands.append(fh.readline().strip())
    except OSError:
        pass
    here = os.path.dirname(os.path.realpath(__file__))
    cands.append(os.path.dirname(os.path.dirname(here)))
    for c in cands:
        c = os.path.expanduser(c)
        if c and os.path.isdir(os.path.join(c, "wiki")):
            return os.path.realpath(c)
    return None


def cache_dir(vault: str | None) -> str:
    """One folder per wiki, so two wikis on one Mac never share an index.
    MOBLEE_RECALL_CACHE overrides it (the tests)."""
    env = os.environ.get("MOBLEE_RECALL_CACHE")
    if env:
        return os.path.expanduser(env)
    key = hashlib.sha1(os.path.realpath(vault or "").encode("utf-8")).hexdigest()[:12]
    return os.path.join(os.path.expanduser("~/.cache/moblee-recall"), key)


VAULT = find_vault()
CACHE = cache_dir(VAULT)
VEC_PATH = os.path.join(CACHE, "vectors.f32")
META_PATH = os.path.join(CACHE, "meta.json")
LOCK_PATH = os.path.join(CACHE, "rebuild.lock")


def _is_restricted(text: str) -> bool:
    text = text.lstrip("﻿")
    if not text.startswith("---"):
        return False
    end = text.find("\n---", 3)
    return end != -1 and re.search(r"(?mi)^restricted:", text[3:end]) is not None


def _excluded_real(path: str, root_real: str) -> bool:
    """True when the file's real place (through any link) is under an excluded
    folder of the wiki root, or outside the wiki altogether."""
    real = os.path.realpath(path)
    if not real.startswith(root_real + os.sep):
        return True
    parts = os.path.relpath(real, root_real).split(os.sep)
    return any(p.casefold() in EXCLUDE_DIRS for p in parts[:-1])


def read_page(path: str) -> str | None:
    """A page's text, or None when it must not be used: unreadable, restricted
    by front matter, or (through a link) under an excluded folder."""
    try:
        with open(path, encoding="utf-8-sig", errors="ignore") as fh:
            text = fh.read()
    except OSError:
        return None
    if _is_restricted(text):
        return None
    return text


def _iter_md_files():
    for root in (os.path.join(VAULT, "wiki"), os.path.join(VAULT, "memory")):
        root_real = os.path.realpath(root)
        for path in glob.glob(os.path.join(glob.escape(root), "**", "*.md"), recursive=True):
            if os.path.islink(path) or _excluded_real(path, root_real):
                continue
            yield root, path


def _chunk(path: str, text: str):
    """A page split into its sections, each with its heading path."""
    page = os.path.splitext(os.path.basename(path))[0]
    h2, h3 = None, None
    buf: list[str] = []
    start = 1
    out = []

    def flush(cur_start: int):
        body = "\n".join(buf).strip()
        if len(body) < 20:
            return None
        hp = " > ".join(x for x in (h2, h3) if x) or "(intro)"
        return {"path": path, "page": page, "heading": hp, "start_line": cur_start,
                "text": f"{page} - {hp}\n{body}", "snippet": re.sub(r"\s+", " ", body)[:240]}

    for i, ln in enumerate(text.splitlines(), 1):
        m2 = re.match(r"^##\s+(.*)", ln)
        m3 = re.match(r"^###\s+(.*)", ln)
        if m2 or m3:
            c = flush(start)
            if c:
                out.append(c)
            buf, start = [], i
            if m2:
                h2, h3 = m2.group(1).strip(), None
            else:
                h3 = m3.group(1).strip()
        else:
            buf.append(ln)
    c = flush(start)
    if c:
        out.append(c)
    final = []
    for c in out:
        words = c["text"].split()
        if len(words) <= 1100:
            final.append(c)
            continue
        for j in range(0, len(words), 1000):
            w = dict(c)
            w["text"] = " ".join(words[j:j + 1000])
            final.append(w)
    return final


def _stub_vector(text: str, dims: int = 64) -> list:
    """A stand-in embedding for tests: words hashed into a small vector, so
    that two texts sharing words are close and unrelated texts are not."""
    v = [0.0] * dims
    for w in re.findall(r"[a-z0-9]+", text.lower()):
        h = int(hashlib.md5(w.encode()).hexdigest(), 16)
        v[h % dims] += 1.0
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def _embed(texts: list) -> list:
    if STUB:
        return [_stub_vector(t) for t in texts]
    vecs = []
    for i in range(0, len(texts), 64):
        batch = texts[i:i + 64]
        try:
            body = {"model": MODEL, "input": batch, "keep_alive": "24h"}   # the model stays loaded, so a question is quick
            req = urllib.request.Request(OLLAMA + "/api/embed", data=json.dumps(body).encode(),
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=180) as r:
                vecs.extend(json.loads(r.read())["embeddings"])
        except Exception:
            for t in batch:
                req = urllib.request.Request(OLLAMA + "/api/embeddings",
                                             data=json.dumps({"model": MODEL, "prompt": t, "keep_alive": "24h"}).encode(),
                                             headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=180) as r:
                    vecs.append(json.loads(r.read())["embedding"])
        if len(texts) > 1:   # progress for a rebuild; a single question is quiet
            sys.stderr.write(f"\r  embedded {min(i + 64, len(texts))}/{len(texts)}")
            sys.stderr.flush()
    if len(texts) > 1:
        sys.stderr.write("\n")
    out = []
    for v in vecs:
        n = math.sqrt(sum(x * x for x in v)) or 1.0
        out.append([x / n for x in v])
    return out


def _text_hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def _read_index():
    try:
        with open(META_PATH, encoding="utf-8") as fh:
            meta = json.load(fh)
        arr = array.array("f")
        with open(VEC_PATH, "rb") as fh:
            arr.frombytes(fh.read())
    except (OSError, ValueError):
        return None, None
    dims = int(meta.get("dims") or 0)
    if not dims or len(arr) != dims * len(meta.get("chunks", [])):
        return None, None
    return meta, arr


def _previous_vectors(meta, arr) -> dict:
    out = {}
    if meta is None or meta.get("model") != (("stub") if STUB else MODEL):
        return out
    dims = meta["dims"]
    for i, c in enumerate(meta["chunks"]):
        if c.get("h") and c["h"] not in out:
            out[c["h"]] = arr[i * dims:(i + 1) * dims].tolist()
    return out


def _links_excluded(text: str, excluded_pages: set) -> bool:
    """A memory that links to a page that must not be surfaced is left out."""
    for m in re.finditer(r"\[\[([^\]|#]+)", text):
        if m.group(1).strip().casefold() in excluded_pages:
            return True
    return False


def rebuild(full: bool = False) -> int:
    if VAULT is None:
        sys.exit("recall: the wiki could not be found")
    os.makedirs(CACHE, exist_ok=True)
    # One rebuild at a time: the lock is held by the kernel for as long as this
    # run lives and let go the moment it ends, however it ends; nothing to
    # stale, nothing to delete.
    lock = open(LOCK_PATH, "a+")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("recall: another rebuild is running; nothing done")
        return 0
    t0 = time.time()
    wiki_root = os.path.realpath(os.path.join(VAULT, "wiki"))
    excluded_pages = set()
    for path in glob.glob(os.path.join(glob.escape(wiki_root), "**", "*.md"), recursive=True):
        if _excluded_real(path, wiki_root) or read_page(path) is None:
            excluded_pages.add(os.path.splitext(os.path.basename(path))[0].casefold())
    chunks = []
    for root, path in _iter_md_files():
        text = read_page(path)
        if text is None:
            continue
        if root.endswith("memory") and _links_excluded(text, excluded_pages):
            continue
        chunks.extend(_chunk(path, text))
    if not chunks:
        print("recall: nothing to index yet")
        return 0
    for c in chunks:
        c["h"] = _text_hash(c["text"])
    meta, arr = (None, None) if full else _read_index()
    known = _previous_vectors(meta, arr)
    todo = [c for c in chunks if c["h"] not in known]
    print(f"recall: {len(chunks)} sections in the wiki; {len(todo)} new or changed, embedding those on this Mac...")
    fresh = dict(zip([c["h"] for c in todo], _embed([c["text"] for c in todo]))) if todo else {}
    vectors = [fresh[c["h"]] if c["h"] in fresh else known[c["h"]] for c in chunks]
    dims = len(vectors[0])
    flat = array.array("f")
    for v in vectors:
        flat.extend(v)
    tmp_v, tmp_m = f"{VEC_PATH}.{os.getpid()}.tmp", f"{META_PATH}.{os.getpid()}.tmp"
    with open(tmp_v, "wb") as fh:
        fh.write(flat.tobytes())
    with open(tmp_m, "w", encoding="utf-8") as fh:
        json.dump({"built": time.time(), "model": "stub" if STUB else MODEL, "dims": dims, "count": len(chunks),
                   "vault": VAULT,
                   "chunks": [{k: c[k] for k in ("path", "page", "heading", "start_line", "snippet", "h")} for c in chunks]}, fh)
    os.replace(tmp_v, VEC_PATH)
    os.replace(tmp_m, META_PATH)
    print(f"recall: index built, {len(chunks)} sections ({len(todo)} embedded) in {time.time() - t0:.0f}s")
    return 0


def query(q: str, n: int = 8, as_json: bool = False) -> int:
    meta, arr = _read_index()
    if meta is None:
        sys.exit("recall: no index yet. Run:  python3 recall.py rebuild")
    qv = _embed([q])[0]
    dims = meta["dims"]
    mul = operator.mul
    scores = []
    for i in range(len(meta["chunks"])):
        base = i * dims
        scores.append((sum(map(mul, arr[base:base + dims], qv)), i))
    scores.sort(reverse=True)
    hits = []
    for s, i in scores[:n]:
        c = meta["chunks"][i]
        hits.append({"score": round(float(s), 3), "page": c["page"], "heading": c["heading"],
                     "snippet": c["snippet"], "path": c["path"]})
    if as_json:
        print(json.dumps(hits, ensure_ascii=False, indent=2))
        return 0
    print(f'recall: "{q}"\n')
    for h in hits:
        loc = f'[[{h["page"]}]]' + ("" if h["heading"] == "(intro)" else f' > {h["heading"]}')
        print(f'  {h["score"]:.3f}  {loc}\n         {h["snippet"]}\n')
    return 0


def status() -> int:
    meta, _ = _read_index()
    if meta is None:
        print(f"recall: no index yet, at {CACHE}")
        return 0
    age = (time.time() - meta["built"]) / 3600
    print(f"recall: {meta['count']} sections, built {age:.1f} hours ago, at {CACHE}")
    return 0


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 2
    if args[0] == "rebuild":
        return rebuild(full="--full" in args)
    if args[0] == "status":
        return status()
    as_json = False
    if args[0] == "--json":
        as_json = True
        args = args[1:]
    q = " ".join(args).strip()
    if not q:
        print("recall: empty question")
        return 2
    return query(q, as_json=as_json)


if __name__ == "__main__":
    sys.exit(main())
