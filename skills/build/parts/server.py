#!/usr/bin/env python3
"""server.py - serves __APP_TITLE__ on this Mac only.

Made by Moblee's build skill. Needs nothing but the Python that comes with the
Mac. Start it from the app's folder:

    python3 server.py            start, and print the address
    python3 server.py --open     start, and open the page in the browser
    python3 server.py --port N   use a particular port
    python3 server.py --stay     do not stop when the tab closes (for testing)

What it does, and what it must stay:

  * It binds to 127.0.0.1, the Mac itself, and nothing on the network can
    reach it. Every request must also carry a Host header naming this address
    and, if it carries an Origin, one that is this page, so another website
    open in the same browser cannot use the page as a go-between.
  * It serves the files in this folder (index.html, moblee-app.js, anything
    the page needs) and the plain files in data/ through /api/data/<name>.
  * /api/save/<name> writes data/<name>.json when the page asks, after
    keeping the previous copy in state/previous/. It never deletes anything.
  * It shuts itself down when the owner closes the tab (the page says goodbye
    as it goes, and the heartbeat stops), or after half an hour with nobody
    looking. Closing the tab is the only "stop" the owner ever does.
  * Started a second time while running, it opens the running page instead
    of starting another copy.

Change what the page shows in index.html and what the data holds in data/.
Leave the binding, the Host and Origin checks and the shutdown alone: they are
what keeps the thing private to this Mac.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import shutil
import socket
import sys
import threading
import time
import urllib.request
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

APP_NAME = "__APP_NAME__"
APP_TITLE = "__APP_TITLE__"
HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
STATE = HERE / "state"
PREVIOUS = STATE / "previous"

# Ports browsers refuse to open (the Fetch standard's "bad ports"), so a page
# served on one of them shows an error with no explanation. 4190 is on the
# list, and it caught a real build once. The range below avoids them all.
BAD_PORTS = {
    1, 7, 9, 11, 13, 15, 17, 19, 20, 21, 22, 23, 25, 37, 42, 43, 53, 69, 77, 79,
    87, 95, 101, 102, 103, 104, 109, 110, 111, 113, 115, 117, 119, 123, 135, 137,
    139, 143, 161, 179, 389, 427, 465, 512, 513, 514, 515, 526, 530, 531, 532, 540,
    548, 554, 556, 563, 587, 601, 636, 989, 990, 993, 995, 1719, 1720, 1723, 2049,
    3659, 4045, 4190, 5060, 5061, 6000, 6566, 6665, 6666, 6667, 6668, 6669, 6697,
    10080,
}
PORT_RANGE = range(7400, 7500)

IDLE_TIMEOUT = float(os.environ.get("MOBLEE_APP_IDLE", "1800"))  # seconds with no heartbeat
LEAVE_GRACE = 6.0   # seconds after the page's goodbye before stopping (a reload re-beats sooner)
TICK = 2.0

_lock = threading.Lock()
_last_beat = time.monotonic()
_leaving_at: float | None = None
_stay = False


def log(line: str) -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(STATE / "server-log.txt", "a", encoding="utf-8") as fh:
        fh.write(f"{stamp} {line}\n")
    print(line, flush=True)


def heartbeat() -> None:
    global _last_beat, _leaving_at
    with _lock:
        _last_beat = time.monotonic()
        _leaving_at = None


def leaving() -> None:
    global _leaving_at
    with _lock:
        _leaving_at = time.monotonic()


def watchdog(server: ThreadingHTTPServer) -> None:
    while True:
        time.sleep(TICK)
        if _stay:
            continue
        now = time.monotonic()
        with _lock:
            idle = now - _last_beat
            gone = _leaving_at is not None and (now - _leaving_at) >= LEAVE_GRACE
        if gone or idle >= IDLE_TIMEOUT:
            log("stopping: " + ("the tab was closed" if gone else f"nobody looking for {int(idle)} seconds"))
            server.shutdown()
            return


def port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.2)
        return s.connect_ex(("127.0.0.1", port)) != 0


def already_ours(port: int) -> bool:
    """Is the thing on this port this very app, already running?"""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/ping", timeout=1) as r:
            return json.loads(r.read().decode()).get("app") == APP_NAME
    except Exception:
        return False


def choose_port(wanted: int | None) -> int:
    if wanted:
        if wanted in BAD_PORTS:
            sys.exit(f"Port {wanted} is one browsers refuse to open. Choose another.")
        return wanted
    cfg = HERE / "app.json"
    if cfg.exists():
        try:
            loaded = json.loads(cfg.read_text())
            p = int(loaded.get("port") or 0) if isinstance(loaded, dict) else 0
            if p and p not in BAD_PORTS:
                return p
        except (ValueError, OSError, TypeError):
            print("app.json could not be read for a port; choosing a free one.", flush=True)
    for p in PORT_RANGE:
        if p not in BAD_PORTS and port_free(p):
            return p
    sys.exit("No free port between 7400 and 7499.")


def safe_name(name: str) -> str | None:
    import re
    return name if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", name) else None


class Handler(SimpleHTTPRequestHandler):
    allowed_hosts: set = set()
    allowed_origins: set = set()

    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(HERE), **kw)

    def log_message(self, fmt, *args):  # quiet; the state log has what matters
        pass

    def _send(self, code: int, body, ctype: str = "application/json") -> None:
        data = body if isinstance(body, (bytes, bytearray)) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _loopback_ok(self) -> bool:
        host = (self.headers.get("Host") or "").strip().lower()
        if host not in self.allowed_hosts:
            return False
        origin = self.headers.get("Origin")
        return origin is None or origin.strip().lower() in self.allowed_origins

    def _file_ok(self) -> bool:
        """May the file this request names be served? Decided on the path as
        it will really be opened (unquoted, normalised), never on the raw
        request, so %2E, a capital S in State and the like cannot get round it:
        nothing under state/, no hidden file or folder, nothing outside this
        folder, and no folder listings."""
        real = Path(self.translate_path(self.path))
        try:
            rel = real.resolve().relative_to(HERE.resolve())
        except (ValueError, OSError):
            return False
        parts = rel.parts
        if any(p.startswith(".") for p in parts):
            return False
        if parts and parts[0].lower() == "state":
            return False
        return not real.is_dir()

    def list_directory(self, path):
        self._send(403, {"error": "folders are not listed"})
        return None

    def _api_get(self, path: str) -> bool:
        if path == "/api/ping":
            self._send(200, {"app": APP_NAME, "title": APP_TITLE, "ok": True})
            return True
        if path.startswith("/api/data/"):
            name = safe_name(path[len("/api/data/"):])
            file = DATA / f"{name}.json" if name else None
            if file and file.exists():
                self._send(200, file.read_bytes())
            else:
                self._send(404, {"error": "no such data file", "name": name})
            return True
        return False

    def do_GET(self):
        if not self._loopback_ok():
            self._send(403, {"error": "refused: not from this Mac's own page"})
            return
        path = self.path.split("?", 1)[0]
        if self._api_get(path):
            return
        if path == "/":
            self.path = "/index.html"
        if not self._file_ok():
            self._send(403, {"error": "not served"})
            return
        super().do_GET()

    def do_HEAD(self):
        if not self._loopback_ok():
            self._send(403, {"error": "refused: not from this Mac's own page"})
            return
        path = self.path.split("?", 1)[0]
        if path.startswith("/api/"):
            self._send(405, {"error": "use GET"})
            return
        if path == "/":
            self.path = "/index.html"
        if not self._file_ok():
            self._send(403, {"error": "not served"})
            return
        super().do_HEAD()

    def do_POST(self):
        if not self._loopback_ok():
            self._send(403, {"error": "refused: not from this Mac's own page"})
            return
        path = self.path.split("?", 1)[0]
        if path == "/api/leaving":          # sent by the page as it closes; it cannot carry headers
            leaving()
            self._send(200, {"ok": True})
            return
        if self.headers.get("X-Requested-By") != "moblee-app":
            self._send(403, {"error": "missing X-Requested-By header"})
            return
        if path == "/api/heartbeat":
            heartbeat()
            self._send(200, {"ok": True})
            return
        if path.startswith("/api/save/"):
            name = safe_name(path[len("/api/save/"):])
            if not name:
                self._send(400, {"error": "bad name"})
                return
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                self._send(400, {"error": "bad Content-Length"})
                return
            if length > 20 * 1024 * 1024:
                self._send(413, {"error": "too large"})
                return
            raw = self.rfile.read(length)
            try:
                parsed = json.loads(raw.decode("utf-8"))
            except ValueError:
                self._send(400, {"error": "not JSON"})
                return
            self._send(200, save_data(name, parsed))
            return
        self._send(404, {"error": "no such action"})


def save_data(name: str, value) -> dict:
    """Write data/<name>.json, keeping the previous copy first.

    The previous copy goes to state/previous/<name>-<stamp>.json before the
    file is written, so a save can never lose what was there. Copies are kept,
    never thinned: this file must stay free of anything that deletes, moves or
    replaces, because the delete guard reads scripts before it lets them run,
    and the owner's wiki history holds the data anyway."""
    DATA.mkdir(parents=True, exist_ok=True)
    target = DATA / f"{name}.json"
    if target.exists():
        PREVIOUS.mkdir(parents=True, exist_ok=True)
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        shutil.copy2(target, PREVIOUS / f"{name}-{stamp}.json")
    target.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    log(f"saved data/{name}.json")
    return {"ok": True, "file": f"data/{name}.json"}


def open_page(url: str) -> None:
    """Open the page in the browser, and say what to do if no browser would."""
    try:
        opened = webbrowser.open(url)
    except Exception:
        opened = False
    if not opened:
        log(f"No browser opened by itself. Open {url} in a browser.")


def main() -> int:
    global _stay
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int)
    ap.add_argument("--open", action="store_true", help="open the page in the browser")
    ap.add_argument("--stay", action="store_true", help="keep running when the tab closes")
    args = ap.parse_args()
    _stay = args.stay
    port = choose_port(args.port)
    url = f"http://127.0.0.1:{port}/"
    if not port_free(port):
        if already_ours(port):
            print(f"{APP_TITLE} is already running at {url}")
            if args.open:
                open_page(url)
            return 0
        sys.exit(f"Port {port} is in use by something else. Try --port with another number.")
    Handler.allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}", "127.0.0.1", "localhost"}
    Handler.allowed_origins = {f"http://127.0.0.1:{port}", f"http://localhost:{port}"}
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    threading.Thread(target=watchdog, args=(server,), daemon=True).start()
    log(f"{APP_TITLE} at {url}")
    if args.open:
        open_page(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    log("stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
