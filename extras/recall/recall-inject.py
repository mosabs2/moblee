#!/usr/bin/env python3
"""recall-inject.py - the question hook, for Moblee's memory search.

Runs when the owner sends a message (Claude's UserPromptSubmit hook). If the
message reads like a question and the conversation is in the owner's wiki, the
three or four sections of the wiki closest to it in meaning are attached to
the message before Claude reads it, as leads to read before relying on them.

What it never does: fire on a command ("orient", "ingest", "commit"), on a
short message, or outside the wiki; attach a weak match; attach anything from
a restricted folder or a page marked restricted, even one restricted since
the index was last built, or a page that has gone; or block: any error,
missing index or slow answer means nothing is attached and the message goes
through untouched. Every firing and every skip is one line in inject.log
beside the index.

Installed by extras/recall/install-recall.py, which registers it in Claude's
settings, which is the owner's act through the Moblee app.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import time

THRESHOLD = 0.60
MAX_HITS = 4
SNIPPET_CHARS = 320
TIMEOUT_S = 5
RECALL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "recall.py")
EXCLUDE_DIRS = ("private", "ghost reconstructions")
QUESTION_START = re.compile(
    r"^(what|what's|whats|when|where|who|whom|whose|why|how|which|is|are|was|were|"
    r"do|does|did|can|could|should|would|will|have|has|had|am|"
    r"tell me|remind me|explain|summari[sz]e|compare|find|look up|search|recall|"
    r"any (news|update|word|movement)|anything (new|on)|update me|catch me up|"
    r"do we have|have we|is there|are there)\b", re.I)
COMMAND_START = re.compile(
    r"^(orient|ingest|lint|close.day|commit|archive|build|upload|render|run |"
    r"go ahead|do it|yes|no|ok|okay|thanks|thank you|proceed|continue|stop|"
    r"brain|galaxy|compact|capture|save|stage|morning|lesson|watch )", re.I)


def vault_root():
    v = os.environ.get("MOBLEE_VAULT")
    if v:
        return os.path.realpath(os.path.expanduser(v))
    try:
        with open(os.path.expanduser("~/.config/moblee/vault-path"), encoding="utf-8") as fh:
            v = fh.readline().strip()
        return os.path.realpath(os.path.expanduser(v)) if v else None
    except OSError:
        return None


def cache_dir(root) -> str:
    env = os.environ.get("MOBLEE_RECALL_CACHE")
    if env:
        return os.path.expanduser(env)
    key = hashlib.sha1(os.path.realpath(root or "").encode("utf-8")).hexdigest()[:12]
    return os.path.join(os.path.expanduser("~/.cache/moblee-recall"), key)


def log(cache: str, line: str) -> None:
    try:
        os.makedirs(cache, exist_ok=True)
        with open(os.path.join(cache, "inject.log"), "a", encoding="utf-8") as fh:
            fh.write(time.strftime("%Y-%m-%d %H:%M %z") + " " + line + "\n")
    except Exception:
        pass


def looks_like_question(p: str):
    s = p.strip()
    if s.startswith("<") or "task-notification" in s or "SYSTEM NOTIFICATION" in s:
        return False, "system"
    words = s.split()
    if len(words) < 4:
        return False, "short"
    if COMMAND_START.match(s):
        return False, "command"
    if s.endswith("?") or "?" in s[-3:]:
        return True, "?"
    if QUESTION_START.match(s):
        return True, "question-word"
    if "?" in s and len(words) >= 8:
        return True, "?-inside"
    return False, "not-a-question"


def in_vault(cwd: str, root) -> bool:
    if not root or not cwd:
        return False
    c = os.path.realpath(cwd)
    return c == root or c.startswith(root + os.sep)


def still_allowed(path: str, root: str) -> bool:
    """The index may be hours old: the page is checked as it is now. Gone,
    moved under an excluded folder, or restricted since: not attached."""
    try:
        real = os.path.realpath(path)
        if not real.startswith(root + os.sep):
            return False
        parts = os.path.relpath(real, root).split(os.sep)
        if any(p.casefold() in EXCLUDE_DIRS for p in parts[:-1]):
            return False
        with open(path, encoding="utf-8-sig", errors="ignore") as fh:
            head = fh.read(2048)
        if head.startswith("---"):
            end = head.find("\n---", 3)
            fm = head[3:end] if end != -1 else head[3:]
            if re.search(r"(?mi)^restricted:", fm):
                return False
        return True
    except OSError:
        return False


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return
    prompt = (data.get("prompt") or "").strip()
    cwd = data.get("cwd") or os.getcwd()
    short = prompt.replace("\n", " ")[:80]
    root = vault_root()
    if not in_vault(cwd, root):
        return
    cache = cache_dir(root)
    ok, why = looks_like_question(prompt)
    if not ok:
        log(cache, f"skip ({why}): {short}")
        return
    if not os.path.exists(os.path.join(cache, "meta.json")):
        log(cache, f"skip (no index): {short}")
        return
    try:
        r = subprocess.run([sys.executable, RECALL, "--json", prompt[:1000]], capture_output=True, text=True,
                           timeout=TIMEOUT_S, env=dict(os.environ, MOBLEE_VAULT=root))
        hits = json.loads(r.stdout)
    except Exception as e:
        log(cache, f"skip (recall failed: {type(e).__name__}): {short}")
        return
    keep = []
    for h in hits:
        if h.get("score", 0) < THRESHOLD or len(keep) >= MAX_HITS:
            continue
        if not still_allowed(h.get("path", ""), root):
            continue
        keep.append(h)
    if not keep:
        top = hits[0]["score"] if hits else 0
        log(cache, f"skip (best {top:.2f} < {THRESHOLD}, or nothing allowed): {short}")
        return
    lines = ["[recall] Sections of your wiki close in meaning to this message, attached by Moblee as leads, "
             "not answers: read the page before relying on it."]
    for h in keep:
        loc = f"[[{h['page']}]]" + ("" if h["heading"] == "(intro)" else f", under {h['heading']}")
        snip = re.sub(r"\s+", " ", h.get("snippet", "")).strip()[:SNIPPET_CHARS]
        lines.append(f"- {loc}: {snip}")
    sys.stdout.write("\n".join(lines) + "\n")
    log(cache, f"fired ({why}, {len(keep)} sections, best {keep[0]['score']:.2f}): {short}")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
