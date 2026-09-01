#!/usr/bin/env python3
"""Moblee Dashboard — a local voice-and-graphics surface for your wiki vault.

A local-only web page on top of Claude Code. It shows the working state of
your vault (active threads, today's plan, the recent log), lets you ask the
wiki questions by voice or text (each ask runs `claude -p` in the vault), and
draws any charts you configure in dashboard-charts.json.

Plain-files safe: reads the vault markdown in place. Anything Claude changes
during an ask is recorded to outputs/dashboard-audit/ inside the vault, and
git is the undo path.

Binds to 127.0.0.1 only, and every request is checked for a loopback Host and
a same-origin (or absent) Origin, plus an X-Requested-By header on
state-changing POSTs, so a cross-origin page or a DNS-rebinding host cannot
drive it through your browser. The residual assumption is single-user: any
process already running as you on this machine can reach the port.

Voice is optional and degrades silently: replies are read aloud with
ElevenLabs if an API key is available (ELEVENLABS_API_KEY, or the macOS
Keychain item "elevenlabs_api_key"), falling back to the macOS `say` command,
falling back to silence.

Run:  python3 server.py     then open http://127.0.0.1:7373
The vault is found via MOBLEE_VAULT, then ~/.config/moblee/vault-path (the
Moblee installer writes this), then by walking up from the current directory.
"""

import base64
import csv
import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
import urllib.request
from collections import Counter
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


# --- Vault discovery ---------------------------------------------------------
def find_vault():
    """Locate the vault root.

    Order: the MOBLEE_VAULT environment variable; then the one-line path file
    ~/.config/moblee/vault-path (written by the Moblee installer); then a walk
    up from the current directory looking for a folder that contains
    wiki/Index.md. Exits with a plain-English error if none of those work.
    """
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


VAULT = find_vault()
WIKI = os.path.join(VAULT, "wiki")
HERE = os.path.dirname(os.path.abspath(__file__))
CHARTS_FILE = os.path.join(HERE, "dashboard-charts.json")
GALAXY_BUILD = os.path.join(os.path.dirname(HERE), "scripts", "wiki-galaxy",
                            "build.py")
PORT = int(os.environ.get("MOBLEE_DASH_PORT", "7373"))
RUN_TIMEOUT = int(os.environ.get("MOBLEE_RUN_TIMEOUT", "600"))  # inactivity kill

# Track in-flight `claude -p` subprocesses so /api/cancel can stop them.
# Maps each live Popen -> the session id it belongs to (None until the
# stream's init event reveals it).
ACTIVE = {}
ACTIVE_LOCK = threading.Lock()

# Recorded outcome of each finished run, so the browser can distinguish "the
# stream to me broke" from "the run itself failed". /api/lastrun lets the page
# ask for the truth before it stamps an error on a completed run.
LASTRUN = {}                     # session_id -> outcome string of its last run
LASTRUN_GLOBAL = {"sid": None, "outcome": None}
LASTRUN_MAX = 200                # bound the dict on this long-lived server
LASTRUN_LOCK = threading.Lock()


def _kill_tree(proc, sig=signal.SIGTERM):
    """Signal the child's whole process group, not just the direct child.

    `claude -p` spawns descendants that can inherit and hold the stdout pipe
    open; killing only the parent leaves them running and the read loop never
    sees EOF. The child leads its own session (start_new_session in Popen), so
    its pgid == its pid and one killpg reaches the whole tree.
    """
    try:
        os.killpg(os.getpgid(proc.pid), sig)
    except Exception:
        try:
            proc.kill() if sig == signal.SIGKILL else proc.terminate()
        except Exception:
            pass


# --- Browser-lifecycle binding ------------------------------------------------
# The server's life is bound to an open dashboard tab, so closing the window is
# the only shutdown action you ever take. The page heartbeats every few
# seconds; a watchdog thread shuts the server down when the browser goes away:
#   * Fast path: the page fires navigator.sendBeacon('/api/leaving') on
#     pagehide, which shuts down after LEAVE_GRACE unless a heartbeat arrives
#     first (a reload re-beats within ~1s, so it survives reloads).
#   * Backstop: no heartbeat for IDLE_TIMEOUT (crash, force-quit, long sleep)
#     shuts down anyway.
# The watchdog never kills the server while a `claude -p` run is in flight.
LIFECYCLE_LOCK = threading.Lock()
LAST_BEAT = time.monotonic()
LEAVING_AT = None            # set by /api/leaving, cleared by the next heartbeat
IDLE_TIMEOUT = float(os.environ.get("MOBLEE_IDLE_TIMEOUT", "1800"))
LEAVE_GRACE = 6.0            # clean-close shutdown delay; also the reload guard
WATCHDOG_TICK = 2.0


def mark_heartbeat():
    """Page is alive: refresh the beat and cancel any pending clean-close."""
    global LAST_BEAT, LEAVING_AT
    with LIFECYCLE_LOCK:
        LAST_BEAT = time.monotonic()
        LEAVING_AT = None


def mark_leaving():
    """Page fired its unload beacon: arm the clean-close timer."""
    global LEAVING_AT
    with LIFECYCLE_LOCK:
        LEAVING_AT = time.monotonic()


def _watchdog(srv):
    while True:
        time.sleep(WATCHDOG_TICK)
        now = time.monotonic()
        with LIFECYCLE_LOCK:
            idle = now - LAST_BEAT
            leaving = LEAVING_AT is not None and (now - LEAVING_AT) >= LEAVE_GRACE
        if not (leaving or idle >= IDLE_TIMEOUT):
            continue
        with ACTIVE_LOCK:
            busy = len(ACTIVE) > 0
        if busy:
            continue  # never abort an in-flight run; revisit next tick
        reason = "clean close" if leaving else ("idle %ds" % int(idle))
        print("lifecycle: browser gone (%s); shutting down" % reason)
        srv.shutdown()
        return


# Loopback-only guard. The server binds to 127.0.0.1, but that only stops the
# network reaching it — it does not stop your own browser being used as a
# confused deputy: a cross-origin page can POST a CORS-safelisted (text/plain)
# body with no preflight, and DNS rebinding can point an attacker hostname at
# 127.0.0.1. We defend by requiring the Host header to be a loopback name we
# bound, and refusing any request whose Origin is present and not ourselves.
ALLOWED_HOSTS = {f"127.0.0.1:{PORT}", f"localhost:{PORT}", "127.0.0.1", "localhost"}
ALLOWED_ORIGINS = {f"http://127.0.0.1:{PORT}", f"http://localhost:{PORT}"}

# Optional voice hook: if you have a Claude Code voice hook script at this
# path it is preferred; otherwise the server falls back to the macOS `say`
# command, and to silence on other platforms. Nothing here is required.
VOICE = os.path.expanduser("~/.claude/hooks/voice")
_SAY = {"proc": None}

# ElevenLabs text-to-speech (optional). The key is read from the
# ELEVENLABS_API_KEY environment variable, or from the macOS Keychain item
# "elevenlabs_api_key". Absent key = the endpoint degrades and the browser
# falls back to local speech.
EL_VOICE = os.environ.get("MOBLEE_TTS_VOICE", "JBFqnCBsd6RMkjVDRZzb")
EL_MODEL = "eleven_turbo_v2_5"
EL_SETTINGS = {"stability": 0.5, "similarity_boost": 0.75, "style": 0.0,
               "use_speaker_boost": True, "speed": 1.1}

QUICK_ACTIONS = [
    {"id": "orient", "label": "Orient",
     "prompt": "Orient me: read wiki/_context.md and the tail of wiki/log.md, "
               "then give me a short situation report — active threads, "
               "anything waiting on me, and the state of the raw/ and "
               "Clippings/ inboxes."},
    {"id": "inbox", "label": "Inbox review",
     "prompt": "List what is waiting in raw/ and Clippings/ and suggest what "
               "to ingest first."},
    {"id": "ideas", "label": "Ideas",
     "prompt": "Read wiki/_context.md and suggest connections or next steps "
               "across my active threads."},
]


# --- helpers -----------------------------------------------------------------
def read_file(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def read_bytes(path):
    try:
        with open(path, "rb") as f:
            return f.read()
    except OSError:
        return b""


def strip_wikilinks(s):
    return re.sub(r"\[\[([^\]|]+\|)?([^\]]+)\]\]", r"\2", s)


def section_lines(text, header):
    out, grab = [], False
    for ln in text.splitlines():
        if ln.startswith("## "):
            grab = ln[3:].strip().lower().startswith(header.lower())
            continue
        if grab:
            out.append(ln)
    return out


def open_items(lines):
    items = []
    for ln in lines:
        s = ln.strip()
        if not s.startswith("- "):
            continue
        body = s[2:].lstrip()
        if body.startswith("~~"):
            continue
        m = re.search(r"\*\*(.+?)\*\*", body)
        title = strip_wikilinks((m.group(1) if m else body[:90])).strip().rstrip(".")
        if title:
            items.append({"title": title})
    return items


def todays_plan():
    """Today's daily note Plan checklist, if a Daily Notes folder is in use."""
    today = date.today().isoformat()
    note = read_file(os.path.join(VAULT, "Daily Notes", f"{today}.md"))
    if not note:
        return {"date": today, "found": False, "items": []}
    items = []
    for ln in section_lines(note, "Plan"):
        m = re.match(r"- \[([ xX])\]\s*(.*)", ln.strip())
        if not m:
            continue
        body = m.group(2)
        bold = re.search(r"\*\*(.+?)\*\*", body)
        title = strip_wikilinks((bold.group(1) if bold else body[:90])).strip().rstrip(".")
        items.append({"done": m.group(1).lower() == "x", "title": title})
    return {"date": today, "found": True, "items": items}


def recent_log(n=14):
    """Newest entries from wiki/log.md (header form `## [stamp] type | Title`)."""
    text = read_file(os.path.join(WIKI, "log.md"))
    heads = re.findall(r"^## \[([^\]]+)\]\s*([^\n]+)", text, re.MULTILINE)
    out = []
    for stamp, rest in heads[-n:]:
        kind, _, title = rest.partition("|")
        out.append({"stamp": stamp.strip(), "kind": kind.strip(),
                    "title": strip_wikilinks(title.strip())})
    return list(reversed(out))


def inbox_files():
    out = []
    rawdir = os.path.join(VAULT, "raw")
    for f in sorted(os.listdir(rawdir)) if os.path.isdir(rawdir) else []:
        p = os.path.join(rawdir, f)
        if os.path.isfile(p) and not f.startswith("."):
            out.append({"name": f, "folder": "raw", "size": os.path.getsize(p)})
    clip = os.path.join(VAULT, "Clippings")
    for f in sorted(os.listdir(clip)) if os.path.isdir(clip) else []:
        p = os.path.join(clip, f)
        if os.path.isfile(p) and f.endswith(".md"):
            out.append({"name": f, "folder": "Clippings", "size": os.path.getsize(p)})
    return out


def wiki_page_count():
    n = 0
    for root, dirs, files in os.walk(WIKI):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        n += sum(1 for f in files if f.endswith(".md"))
    return n


def last_commit():
    line = _git("log", "-1", "--format=%h|%cr|%s")
    if not line or "|" not in line:
        return None
    h, when, msg = line.split("|", 2)
    return {"hash": h, "when": when, "msg": msg}


def build_state():
    ctx = read_file(os.path.join(WIKI, "_context.md"))
    refreshed = ""
    m = re.search(r"Last refreshed:\s*([^(\n]+)", ctx)
    if m:
        refreshed = m.group(1).strip()
    return {
        "vault": os.path.basename(VAULT),
        "refreshed": refreshed,
        "active": open_items(section_lines(ctx, "Active threads")),
        "decisions": open_items(section_lines(ctx, "Open decisions")),
        "watch": open_items(section_lines(ctx, "Watch list")),
        "plan": todays_plan(),
        "log": recent_log(),
        "hero": {
            "pages": wiki_page_count(),
            "inbox": len(inbox_files()),
            "commit": last_commit(),
        },
    }


# Restricted-pages rule: the page API never serves material from wiki/Private/
# or any page carrying a `restricted:` frontmatter marker to the browser or
# the read-aloud path. Delete-safe: an unreadable file fails closed.
RESTRICTED_DIR_MARKERS = (os.sep + "Private" + os.sep,)


def _is_restricted_page(path):
    if any(m in path for m in RESTRICTED_DIR_MARKERS):
        return True
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            head = f.read(2048)
    except OSError:
        return True  # unreadable: fail closed
    if not head.startswith("---"):
        return False
    end = head.find("\n---", 3)
    front = head[3:end] if end != -1 else head
    return re.search(r"(?mi)^restricted:", front) is not None


def find_page(name):
    name = name.strip().rstrip("/")
    target = (name if name.endswith(".md") else name + ".md").lower()
    for root, _, files in os.walk(WIKI):
        if any(m in root + os.sep for m in RESTRICTED_DIR_MARKERS):
            continue
        for f in files:
            if f.lower() == target:
                path = os.path.join(root, f)
                if _is_restricted_page(path):
                    return None
                return path
    return None


def latest_graph():
    """Newest link-graph HTML in outputs/reports/, if any tool has written one."""
    rep = os.path.join(VAULT, "outputs", "reports")
    if not os.path.isdir(rep):
        return None
    htmls = [os.path.join(rep, f) for f in os.listdir(rep)
             if f.startswith("wiki-explorer") and f.endswith(".html")]
    return max(htmls, key=os.path.getmtime) if htmls else None


# ---------- Config-driven charts (the Visuals tab) ----------------------------
# dashboard-charts.json lives next to this file. Each entry:
#   {"id": "...", "title": "...", "why": "one line on why this matters",
#    "csv": "path/relative/to/vault.csv"  OR  "builtin": "wiki-growth",
#    "type": "line" | "bar" | "cumulative",
#    "x": "column name", "y": "column name or list of names",
#    "date_x": true}
# Ask Claude to add a chart and it edits this file; the tab redraws on the
# next visit. The file is re-read on every request, so edits land live.

def load_charts():
    try:
        with open(CHARTS_FILE, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return []
    if isinstance(data, dict):
        data = data.get("charts", [])
    return [c for c in data if isinstance(c, dict) and c.get("id")]


def chart_list():
    keys = ("id", "title", "why", "type", "x", "y", "date_x", "csv", "builtin")
    return [{k: c.get(k) for k in keys if c.get(k) is not None}
            for c in load_charts()]


def wiki_growth_series():
    """Built-in example series: cumulative wiki page count by file-modified
    date. A rough proxy for growth (file dates move when pages are edited),
    but it needs no CSV and shows the chart pipeline working end to end."""
    per_day = Counter()
    latest = 0.0
    for root, dirs, files in os.walk(WIKI):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for f in files:
            if not f.endswith(".md"):
                continue
            try:
                m = os.path.getmtime(os.path.join(root, f))
            except OSError:
                continue
            latest = max(latest, m)
            per_day[time.strftime("%Y-%m-%d", time.localtime(m))] += 1
    pts, n = [], 0
    for d in sorted(per_day):
        n += per_day[d]
        pts.append({"x": d, "y": n, "series": "pages"})
    asof = time.strftime("%Y-%m-%d %H:%M", time.localtime(latest)) if latest else None
    return pts, asof


def _csv_rows(cfg):
    """Rows from the chart's CSV (vault-relative path, kept inside the vault)."""
    rel = (cfg.get("csv") or "").strip()
    if not rel:
        return None, "no csv path configured"
    path = os.path.realpath(os.path.join(VAULT, rel))
    if not path.startswith(os.path.realpath(VAULT) + os.sep):
        return None, "csv path must stay inside the vault"
    if not os.path.isfile(path):
        return None, f"csv not found: {rel}"
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    mtime = time.strftime("%Y-%m-%d %H:%M", time.localtime(os.path.getmtime(path)))
    return (rows, mtime), None


def chart_data(cid):
    cfg = next((c for c in load_charts() if c.get("id") == cid), None)
    if cfg is None:
        return {"error": f"no chart with id {cid!r} in dashboard-charts.json"}
    ctype = cfg.get("type") or "line"
    out = {"id": cfg["id"], "title": cfg.get("title") or cfg["id"],
           "why": cfg.get("why") or "", "type": ctype,
           "date_x": bool(cfg.get("date_x")), "points": [], "asof": None}
    if cfg.get("builtin") == "wiki-growth":
        out["points"], out["asof"] = wiki_growth_series()
        out["date_x"] = True
        return out
    if cfg.get("builtin"):
        return {"error": f"unknown builtin {cfg['builtin']!r} (only "
                         "\"wiki-growth\" is available)"}
    got, err = _csv_rows(cfg)
    if err:
        out["error"] = err
        return out
    rows, out["asof"] = got
    xcol = cfg.get("x") or ""
    ycols = cfg.get("y") or []
    if isinstance(ycols, str):
        ycols = [ycols]
    pts = []
    for r in rows:
        x = (r.get(xcol) or "").strip()
        if not x:
            continue
        for yc in ycols:
            v = (r.get(yc) or "").strip()
            if ctype == "cumulative" and not v:
                v = "1"          # each row counts one when no y column is set
            try:
                y = float(v)
            except ValueError:
                continue
            pts.append({"x": x, "y": y, "series": yc})
    if ctype == "cumulative" and not ycols:
        pts = [{"x": (r.get(xcol) or "").strip(), "y": 1.0, "series": "count"}
               for r in rows if (r.get(xcol) or "").strip()]
    pts.sort(key=lambda p: p["x"])
    if ctype == "cumulative":
        totals = {}
        for p in pts:
            totals[p["series"]] = totals.get(p["series"], 0) + p["y"]
            p["y"] = totals[p["series"]]
    out["points"] = pts
    return out


# ---------- Voice (all optional; every path degrades to silence) --------------
def speak_local(text):
    """Speak on the machine: prefer a user voice hook, else macOS `say`."""
    if os.path.exists(VOICE):
        subprocess.Popen(["/bin/zsh", VOICE, "say", text])
        return
    if sys.platform == "darwin":
        stop_local()
        try:
            _SAY["proc"] = subprocess.Popen(["say", text[:2500]])
        except Exception:
            pass
    # other platforms: silent no-op


def stop_local():
    if os.path.exists(VOICE):
        subprocess.Popen(["/bin/zsh", VOICE, "stop"])
        return
    p = _SAY.get("proc")
    if p and p.poll() is None:
        try:
            p.terminate()
        except Exception:
            pass


def eleven_key():
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if key:
        return key
    if sys.platform != "darwin":
        return ""
    try:
        r = subprocess.run(
            ["security", "find-generic-password", "-s", "elevenlabs_api_key", "-w"],
            capture_output=True, text=True, check=False)
        return r.stdout.strip()
    except Exception:
        return ""


def tts(text):
    """ElevenLabs audio bytes, or None (the browser then falls back to
    /api/speak, which falls back to `say`, which falls back to silence)."""
    key = eleven_key()
    if not key:
        return None
    text = text[:2500]
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{EL_VOICE}?output_format=mp3_44100_128"
    body = json.dumps({"text": text, "model_id": EL_MODEL,
                       "voice_settings": EL_SETTINGS}).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "xi-api-key": key, "Content-Type": "application/json",
        "Accept": "audio/mpeg"})
    try:
        return urllib.request.urlopen(req, timeout=30).read()
    except Exception:
        return None


# --- Audit trail (the flight recorder) ---------------------------------------
# --- Conversation history (the History tab) ---------------------------------
# Claude Code writes a full JSONL transcript per session under
# ~/.claude/projects/<sanitised-cwd>/. Terminal sessions and the dashboard's
# own `claude -p` children share the vault cwd, so they land in the same
# folder; the per-event `entrypoint` field says which surface a session came
# from. Read-only views; per-machine by design (transcripts do not sync).
TRANSCRIPT_DIR = os.path.join(os.path.expanduser("~/.claude/projects"),
                              re.sub(r"[^A-Za-z0-9]", "-", VAULT))
HISTORY_SOURCES = {"sdk-cli": "dashboard", "cli": "terminal",
                   "claude-desktop": "desktop"}
HISTORY_LIST_MAX = 50      # newest sessions shown in the list
HISTORY_TURNS_MAX = 500    # newest turns shown per transcript
_HISTORY_CACHE = {}        # path -> (mtime, summary) so the list scan is cheap


def _msg_text(message):
    """Plain text of a user/assistant message (content is str or block list)."""
    content = message.get("content", "")
    if isinstance(content, str):
        return content
    return "\n".join(b.get("text", "") for b in content
                     if isinstance(b, dict) and b.get("type") == "text")


def _real_user_text(ev):
    """The prompt text of a genuine user turn, else ''. Filters out meta
    events, sub-agent sidechains, tool results (which arrive as user events)
    and harness wrappers like <command-name>/<system-reminder>."""
    if ev.get("isMeta") or ev.get("isSidechain"):
        return ""
    content = ev.get("message", {}).get("content", "")
    if isinstance(content, list) and any(
            isinstance(b, dict) and b.get("type") == "tool_result"
            for b in content):
        return ""
    text = _msg_text(ev.get("message", {})).strip()
    return "" if text.startswith("<") else text


def _session_summary(path):
    """One list-view row per transcript, cached by mtime."""
    st = os.stat(path)
    cached = _HISTORY_CACHE.get(path)
    if cached and cached[0] == st.st_mtime:
        return cached[1]
    title, started, source, prompts = "", "", "", 0
    with open(path, errors="replace") as f:
        for line in f:
            if '"type":"user"' not in line:
                continue
            try:
                ev = json.loads(line)
            except Exception:
                continue
            if ev.get("type") != "user":
                continue
            text = _real_user_text(ev)
            if not text:
                continue
            prompts += 1
            if not title:
                title = re.sub(r"\s+", " ", text)[:110]
                started = ev.get("timestamp", "")
                source = HISTORY_SOURCES.get(ev.get("entrypoint"), "other")
    summary = {"sid": os.path.basename(path)[:-6], "title": title,
               "started": started, "last": st.st_mtime, "n": prompts,
               "source": source} if title else None
    _HISTORY_CACHE[path] = (st.st_mtime, summary)
    return summary


def history_list():
    try:
        files = [os.path.join(TRANSCRIPT_DIR, n)
                 for n in os.listdir(TRANSCRIPT_DIR) if n.endswith(".jsonl")]
    except Exception:
        return []
    files.sort(key=os.path.getmtime, reverse=True)
    live = set(files)  # prune cache entries for transcripts that no longer exist
    for k in [k for k in _HISTORY_CACHE if k not in live]:
        _HISTORY_CACHE.pop(k, None)
    out = []
    for p in files[:HISTORY_LIST_MAX]:
        try:
            s = _session_summary(p)
        except Exception:
            s = None
        if s:
            out.append(s)
    return out


def history_session(sid):
    """Full transcript of one session as user/ai turns, newest-capped."""
    if not re.fullmatch(r"[0-9a-fA-F-]{8,64}", sid or ""):
        return {"error": "bad session id"}
    path = os.path.join(TRANSCRIPT_DIR, sid + ".jsonl")
    if not os.path.isfile(path):
        return {"error": "not found"}
    turns = []
    with open(path, errors="replace") as f:
        for line in f:
            try:
                ev = json.loads(line)
            except Exception:
                continue
            kind = ev.get("type")
            if kind == "user":
                text = _real_user_text(ev)
                if text:
                    turns.append({"role": "user", "text": text})
            elif kind == "assistant" and not ev.get("isSidechain"):
                msg = ev.get("message", {})
                text = _msg_text(msg).strip()
                tools = [b.get("name", "") for b in msg.get("content", [])
                         if isinstance(b, dict) and b.get("type") == "tool_use"]
                # merge consecutive assistant events into one visible turn
                if turns and turns[-1]["role"] == "ai":
                    if text:
                        turns[-1]["text"] = (turns[-1]["text"] + "\n\n" + text).strip()
                    turns[-1]["tools"].extend(tools)
                else:
                    turns.append({"role": "ai", "text": text, "tools": tools})
    turns = [t for t in turns if t["text"] or t.get("tools")]
    truncated = len(turns) > HISTORY_TURNS_MAX
    return {"sid": sid, "truncated": truncated,
            "turns": turns[-HISTORY_TURNS_MAX:]}


# Every dashboard-driven `claude -p` run is logged with the exact set of files
# it changed, deletions flagged. Git is the source of truth and the undo path;
# this daily log is the human-readable index you can review any time.
AUDIT_DIR = os.path.join(VAULT, "outputs", "dashboard-audit")


def _git(*args):
    try:
        r = subprocess.run(["git", "-C", VAULT, *args],
                           capture_output=True, text=True, timeout=15, check=False)
        return r.stdout.strip()
    except Exception:
        return ""


def audit_before():
    """HEAD before a run, so we can diff the whole tree against it afterwards."""
    return _git("rev-parse", "HEAD")


def audit_after(prompt, before_head, outcome):
    """Append one entry recording what the run changed. Never raises."""
    try:
        os.makedirs(AUDIT_DIR, exist_ok=True)
        after_head = _git("rev-parse", "HEAD")
        # Tracked changes (committed or not) vs the pre-run HEAD, plus untracked.
        names = _git("diff", "--name-status", before_head) if before_head else ""
        nums = _git("diff", "--numstat", before_head) if before_head else ""
        untracked = [ln[3:] for ln in _git("status", "--porcelain").splitlines()
                     if ln.startswith("?? ")]
        counts = {}
        for ln in nums.splitlines():
            parts = ln.split("\t")
            if len(parts) == 3:
                counts[parts[2]] = (parts[0], parts[1])
        rows, deletions = [], 0
        for ln in names.splitlines():
            parts = ln.split("\t")
            if len(parts) < 2:
                continue
            flag, path = parts[0], parts[-1]
            add, rem = counts.get(path, ("", ""))
            if flag.startswith("D"):
                deletions += 1
                rows.append(f"  - **DELETED** `{path}`  (-{rem})")
            elif flag.startswith("A"):
                rows.append(f"  - added `{path}`  (+{add})")
            elif flag.startswith("R"):
                rows.append(f"  - renamed `{path}`")
            else:
                rows.append(f"  - modified `{path}`  (+{add} / -{rem})")
        for path in untracked:
            rows.append(f"  - new (uncommitted) `{path}`")
        stamp = time.strftime("%H:%M:%S %Z")
        head_line = (f"{before_head[:7]} → {after_head[:7]}"
                     if before_head and after_head and before_head != after_head
                     else (before_head[:7] if before_head else "n/a") + " (no commit)")
        body = [f"## {stamp} — \"{prompt[:200]}\"",
                f"- Outcome: {outcome}",
                f"- HEAD: {head_line}"]
        if deletions:
            body.append(f"- ⚠ {deletions} file(s) DELETED this run — review below")
        if rows:
            body.append(f"- Changed {len(rows)} file(s):")
            body.extend(rows)
        else:
            body.append("- No file changes.")
        body.append("")
        path = os.path.join(AUDIT_DIR, f"{date.today().isoformat()}.md")
        header = ""
        if not os.path.exists(path):
            header = (f"# Dashboard audit — {date.today().isoformat()}\n\n"
                      "Every command run from the dashboard, and the files it changed. "
                      "Git is the undo path: `git -C \"<vault>\" log`, `git diff <sha>`, "
                      "`git restore <file>`, or `git revert <sha>` to roll back a bad change.\n\n")
        with open(path, "a", encoding="utf-8") as f:
            f.write(header + "\n".join(body) + "\n")
    except Exception:
        pass


# --- HTTP --------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body)
        data = body.encode("utf-8") if isinstance(body, str) else body
        try:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            if data:
                self.wfile.write(data)
        except OSError:
            pass  # client disconnected mid-response; nothing to do

    def _query(self):
        from urllib.parse import urlparse, parse_qs
        return parse_qs(urlparse(self.path).query)

    def _loopback_ok(self):
        """Refuse cross-origin / DNS-rebinding requests. See ALLOWED_HOSTS."""
        host = (self.headers.get("Host") or "").strip().lower()
        if host not in ALLOWED_HOSTS:
            return False
        origin = self.headers.get("Origin")
        if origin is not None and origin.strip().lower() not in ALLOWED_ORIGINS:
            return False
        return True

    def do_GET(self):
        if not self._loopback_ok():
            self._send(403, {"error": "cross-origin or non-loopback request refused"})
            return
        path = self.path.split("?")[0]
        if path == "/" or path.startswith("/index"):
            self._send(200, read_file(os.path.join(HERE, "dashboard.html")),
                       "text/html; charset=utf-8")
        elif path == "/api/state":
            self._send(200, build_state())
        elif path == "/api/actions":
            self._send(200, QUICK_ACTIONS)
        elif path == "/api/inbox":
            self._send(200, inbox_files())
        elif path == "/api/page":
            name = (self._query().get("name") or [""])[0]
            p = find_page(name)
            self._send(200, {"name": name, "found": bool(p),
                             "markdown": read_file(p) if p else ""})
        elif path == "/api/graph":
            g = latest_graph()
            if g:
                self._send(200, read_bytes(g), "text/html; charset=utf-8")
            else:
                self._send(200, "<p style='font:14px sans-serif'>No 2D link "
                                "graph on file. Use the Galaxy button in the "
                                "header for the 3D view of your wiki's links.</p>",
                           "text/html")
        elif path == "/api/history":
            self._send(200, history_list())
        elif path == "/api/history_session":
            sid = (self._query().get("sid") or [""])[0]
            self._send(200, history_session(sid))
        elif path == "/api/status":
            with ACTIVE_LOCK:
                running = len(ACTIVE)
            self._send(200, {"running": running, "pid": os.getpid(),
                             "port": PORT, "vault": VAULT})
        elif path == "/api/lastrun":
            # Truth-check for a torn stream: "running" while the run is still
            # in flight, then the recorded outcome. Running is checked first
            # so a resumed session's previous outcome can't shadow a live run.
            sid = (self._query().get("session_id") or [""])[0]
            with ACTIVE_LOCK:
                active_sids = [s for s in ACTIVE.values()]
            running = (sid in active_sids) if sid else bool(active_sids)
            if running:
                self._send(200, {"outcome": "running"})
            else:
                with LASTRUN_LOCK:
                    out = (LASTRUN.get(sid) if sid else None) \
                        or LASTRUN_GLOBAL["outcome"]
                self._send(200, {"outcome": out})
        elif path == "/api/charts":
            self._send(200, chart_list())
        elif path == "/api/chart/custom":
            cid = (self._query().get("id") or [""])[0]
            self._send(200, chart_data(cid))
        elif path == "/galaxy" or path.startswith("/galaxy/"):
            # Wiki Galaxy: serve the offline 3D graph viewer from
            # <vault>/outputs/galaxy/. The header button rebuilds via POST
            # /api/galaxy_rebuild first; a bare GET with no build on disk runs
            # one build so the link never 404s. Basename-only join keeps this
            # off the traversal path.
            gdir = os.path.join(VAULT, "outputs", "galaxy")
            if not os.path.isfile(os.path.join(gdir, "index.html")):
                try:
                    subprocess.run(["python3", GALAXY_BUILD],
                                   capture_output=True, timeout=120,
                                   env={**os.environ, "MOBLEE_VAULT": VAULT})
                except Exception:
                    pass
            fn = os.path.basename(path[len("/galaxy"):].lstrip("/")) or "index.html"
            gtypes = {"html": "text/html; charset=utf-8",
                      "js": "application/javascript; charset=utf-8", "png": "image/png"}
            ext = fn.rsplit(".", 1)[-1].lower()
            d = read_bytes(os.path.join(gdir, fn)) if ext in gtypes else b""
            self._send(200 if d else 404, d or {"error": "galaxy not built"},
                       gtypes[ext] if d else "application/json")
        elif path.startswith("/vendor/"):
            # Locally-vendored, version-pinned JS libs (marked, DOMPurify,
            # vega). Basename-only join keeps this off the traversal path.
            fn = os.path.basename(path)
            fp = os.path.join(HERE, "vendor", fn)
            d = read_bytes(fp) if fn.endswith(".js") else b""
            self._send(200 if d else 404,
                       d or {"error": "no such vendor file"},
                       "application/javascript; charset=utf-8" if d else "application/json")
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        if not self._loopback_ok():
            self._send(403, {"error": "cross-origin or non-loopback request refused"})
            return
        # CSRF belt-and-braces: a state-changing POST must carry a custom
        # header that only same-origin JS can set (a cross-origin attempt to
        # set it forces a preflight this server never answers). /api/leaving
        # is exempt: it rides navigator.sendBeacon, which cannot attach
        # headers, and only arms a shutdown timer a heartbeat cancels.
        if self.path != "/api/leaving" and \
                self.headers.get("X-Requested-By") != "dashboard":
            self._send(403, {"error": "missing X-Requested-By header"})
            return
        length = int(self.headers.get("Content-Length", 0))
        if length > 40 * 1024 * 1024:  # cap the body before reading it into memory
            self._send(413, {"error": "request body too large"})
            return
        raw = self.rfile.read(length)
        if self.path == "/api/heartbeat":
            mark_heartbeat()
            self._send(200, {"ok": True})
            return
        if self.path == "/api/leaving":
            mark_leaving()
            self._send(200, {"ok": True})
            return
        if self.path == "/api/snapshot":
            out = os.path.join(VAULT, "outputs",
                               f"dashboard-snapshot-{date.today().isoformat()}.html")
            os.makedirs(os.path.dirname(out), exist_ok=True)
            with open(out, "wb") as f:
                f.write(raw)
            self._send(200, {"ok": True, "path": out, "bytes": len(raw)})
            return
        try:
            payload = json.loads(raw or b"{}")
        except Exception:
            self._send(400, {"error": "invalid JSON body"})
            return
        if self.path == "/api/speak":
            t = (payload.get("text") or "").strip()
            if t:
                speak_local(t)
            self._send(200, {"ok": True})
        elif self.path == "/api/stop":
            stop_local()
            self._send(200, {"ok": True})
        elif self.path == "/api/galaxy_rebuild":
            # Rebuild the Wiki Galaxy so the header button always opens a view
            # matching the current wiki. Synchronous — a build takes seconds.
            try:
                r = subprocess.run(["python3", GALAXY_BUILD],
                                   capture_output=True, text=True, timeout=120,
                                   env={**os.environ, "MOBLEE_VAULT": VAULT})
                lines = (r.stdout or "").strip().splitlines()
                self._send(200 if r.returncode == 0 else 500,
                           {"ok": r.returncode == 0,
                            "summary": lines[0] if lines else (r.stderr or "")[:200]})
            except Exception as e:
                self._send(500, {"ok": False, "summary": str(e)[:200]})
        elif self.path == "/api/cancel":
            # Cancel only the requesting session's runs when a session_id is
            # given; a bare cancel still stops everything.
            sid = payload.get("session_id") or None
            with ACTIVE_LOCK:
                procs = [p for p, s in ACTIVE.items() if sid is None or s == sid]
            for p in procs:
                _kill_tree(p)  # whole process group, not just the direct child
            self._send(200, {"ok": True, "cancelled": len(procs)})
        elif self.path == "/api/tts":
            audio = tts((payload.get("text") or "").strip())
            if audio:
                self._send(200, audio, "audio/mpeg")
            else:
                self._send(502, {"error": "tts unavailable"})
        elif self.path == "/api/upload":
            name = re.sub(r"[^A-Za-z0-9._-]", "_",
                          os.path.basename(payload.get("name") or "image.png")) or "image.png"
            try:
                raw = base64.b64decode((payload.get("data") or "").split(",")[-1])
            except Exception:
                self._send(400, {"error": "bad image data"})
                return
            if not raw or len(raw) > 25 * 1024 * 1024:
                self._send(413, {"error": "image missing or over 25 MB"})
                return
            updir = os.path.join(VAULT, "outputs", "dashboard-uploads")
            os.makedirs(updir, exist_ok=True)
            p = os.path.join(updir, time.strftime("%Y%m%d-%H%M%S-") + name)
            with open(p, "wb") as f:
                f.write(raw)
            self._send(200, {"path": p, "name": name})
        elif self.path == "/api/run":
            self._stream_run((payload.get("prompt") or "").strip(),
                             (payload.get("session_id") or None))
        else:
            self._send(404, {"error": "not found"})

    def _stream_run(self, prompt, session_id=None):
        """Run `claude -p` in stream-json mode so the conversation can resume.

        session_id is echoed back in the X-Session-Id response header
        (captured from the stream's init event); the client sends it on the
        next request via --resume, so follow-up commands continue the same
        conversation. A null session_id starts a fresh one.
        """
        if not prompt:
            self._send(400, {"error": "empty prompt"})
            return

        cmd = ["claude", "-p", prompt, "--output-format", "stream-json", "--verbose"]
        if session_id:
            cmd += ["--resume", session_id]

        proc, before_head, outcome = None, audit_before(), "ok"
        sid = session_id
        sent = False          # response headers sent yet?

        def parse(line):
            """(session_id, text-to-emit) for one stream-json line."""
            line = line.strip()
            if not line:
                return None, ""
            try:
                obj = json.loads(line)
            except Exception:
                return None, ""
            text = ""
            if obj.get("type") == "assistant":
                for blk in obj.get("message", {}).get("content", []):
                    if blk.get("type") == "text":
                        text += blk.get("text", "")
                    # tool_use blocks are intentionally not surfaced in the
                    # transcript — the spinner already signals activity.
            return obj.get("session_id"), text

        def start_headers():
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            if sid:
                self.send_header("X-Session-Id", sid)
            self.send_header("Access-Control-Expose-Headers", "X-Session-Id")
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()

        client_gone = {"v": False}

        def chunk(s):
            # Disconnect-tolerant: if the browser side vanishes mid-stream
            # (system sleep, tab close, network drop), stop writing but do NOT
            # kill the run — the read loop keeps draining the child so it can
            # finish its work, and the audit entry records the real outcome.
            if not s or client_gone["v"]:
                return
            b = s.encode("utf-8")
            try:
                self.wfile.write(f"{len(b):X}\r\n".encode() + b + b"\r\n")
                self.wfile.flush()
            except OSError:
                client_gone["v"] = True

        watchdog_stop, timed_out, caff = None, {"v": False}, None
        try:
            # Strip TERM and desktop-app markers so the child looks headless
            # to any user speech hooks — the browser autoread is the
            # dashboard's single voice, and an inherited marker can make a
            # hook read every reply a second time.
            child_env = {k: v for k, v in os.environ.items()
                         if k not in ("TERM", "CLAUDE_CODE_ENTRYPOINT",
                                      "__CFBundleIdentifier")}
            # start_new_session: the child leads its own process group so a
            # stalled/cancelled run can be killed as a whole tree.
            #
            # The claude CLI auto-updates in place; an exec landing inside the
            # swap window hits a partial file and dies with ENOEXEC. Retrying
            # over ~15s covers short swap windows; a persistent failure
            # surfaces a plain-language outcome instead of the raw errno.
            for attempt in range(3):
                try:
                    proc = subprocess.Popen(cmd, cwd=VAULT, stdout=subprocess.PIPE,
                                            stderr=subprocess.STDOUT, text=True,
                                            bufsize=1, env=child_env,
                                            start_new_session=True)
                    break
                except OSError as e:
                    if getattr(e, "errno", None) not in (2, 8):  # ENOENT, ENOEXEC
                        raise
                    if attempt == 2:
                        raise RuntimeError(
                            "the claude CLI failed to launch three times over "
                            f"~15s — likely mid-auto-update (original: {e}); "
                            "wait a minute and retry") from e
                    time.sleep(5 * (attempt + 1))
            # Hold the machine awake while the run works (macOS): on battery
            # an idle sleep mid-run tears down the browser's stream.
            # caffeinate -i blocks idle sleep, -w <pid> scopes the assertion
            # to the child's lifetime. Best-effort; absent elsewhere.
            try:
                caff = subprocess.Popen(["caffeinate", "-i", "-w", str(proc.pid)],
                                        stdout=subprocess.DEVNULL,
                                        stderr=subprocess.DEVNULL)
            except Exception:
                caff = None
            with ACTIVE_LOCK:
                ACTIVE[proc] = sid
            # The read loop below blocks on readline until the child closes
            # stdout, so a watchdog thread kills the process once the child
            # has been silent for RUN_TIMEOUT. The deadline is inactivity,
            # not wall-clock from run start: every streamed line pushes it
            # out, so a long run that is still producing output is never
            # killed and only a genuinely stalled child is.
            last_output = {"t": time.monotonic()}
            watchdog_stop = threading.Event()

            def _kill_stalled():
                while True:
                    idle = time.monotonic() - last_output["t"]
                    if idle >= RUN_TIMEOUT:
                        timed_out["v"] = True
                        _kill_tree(proc, signal.SIGKILL)
                        return
                    if watchdog_stop.wait(min(RUN_TIMEOUT - idle, 5.0)):
                        return

            threading.Thread(target=_kill_stalled, daemon=True).start()
            for line in iter(proc.stdout.readline, ""):
                last_output["t"] = time.monotonic()
                sess, text = parse(line)
                if sess and not sid:
                    sid = sess
                    with ACTIVE_LOCK:
                        if proc in ACTIVE:
                            ACTIVE[proc] = sid
                if not sent and (sid or text):
                    start_headers()
                    sent = True
                if sent:
                    chunk(text)
            if watchdog_stop:
                watchdog_stop.set()
            # Bound the wait: if a pipe-holding grandchild kept the loop alive
            # and the child is wedged, kill the whole tree rather than hang
            # the handler thread.
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                _kill_tree(proc, signal.SIGKILL)
                try:
                    proc.wait(timeout=5)
                except Exception:
                    pass
            if client_gone["v"] and outcome == "ok":
                outcome = "client disconnected mid-stream; run completed headless"
            if timed_out["v"]:
                outcome = f"stalled (no output for {RUN_TIMEOUT}s, killed)"
                chunk(f"\n\n_[killed: no output for {RUN_TIMEOUT // 60} minutes; "
                      "the run stalled. Anything reported above had already "
                      "landed on disk before the kill.]_\n")
            elif proc.returncode and proc.returncode < 0:
                outcome = "cancelled"
                chunk("\n\n_[cancelled]_\n")
        except Exception as e:  # noqa
            outcome = f"error: {e}"
            chunk(f"\n\n_[error: {e}]_\n")
        finally:
            if watchdog_stop:
                watchdog_stop.set()
            if caff:  # release the sleep assertion; -w self-exits but don't rely on it
                try:
                    caff.terminate()
                except Exception:
                    pass
            # Record the outcome before ACTIVE is drained, so a client that
            # polls /api/lastrun after a torn stream sees either "running" or
            # the final outcome, never a gap between the two.
            with LASTRUN_LOCK:
                if sid:
                    LASTRUN[sid] = outcome
                    while len(LASTRUN) > LASTRUN_MAX:
                        LASTRUN.pop(next(iter(LASTRUN)))
                LASTRUN_GLOBAL["sid"], LASTRUN_GLOBAL["outcome"] = sid, outcome
            audit_after(prompt, before_head, outcome)
            if proc:
                with ACTIVE_LOCK:
                    ACTIVE.pop(proc, None)
            if not sent:  # nothing streamed (immediate failure) — still respond
                try:
                    start_headers()
                    sent = True
                    chunk("_[no output]_")
                except Exception:
                    pass
            try:
                self.wfile.write(b"0\r\n\r\n")
                self.wfile.flush()
            except Exception:
                pass


def main():
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    threading.Thread(target=_watchdog, args=(srv,), daemon=True).start()
    print(f"Moblee dashboard → http://127.0.0.1:{PORT}")
    print(f"Vault: {VAULT}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        srv.server_close()


if __name__ == "__main__":
    main()
