#!/usr/bin/env python3
"""Tests for the build skill (v0.11.0): the scaffold, the standard parts and the
check-up's reading of apps/.

    python3 tools/test-build.py

Everything runs in a throwaway folder under the system's temp directory. The
groups:

  scaffold   What the scaffold makes from a fresh template vault, that every
             placeholder is filled, that a second run leaves everything alone,
             that --dry-run makes nothing, that --outside makes a pointer and
             no server, and that the Index gains its one line.
  server     The copied server, started as the owner would start it: serves the
             page; refuses a foreign Host, a foreign Origin, a save without the
             page's header, and anything under state/; saves a data file and
             keeps the previous copy; a second start finds the first; stops when
             the page says goodbye; stops when nobody is looking.
  job        The copied job writes its record on success and on failure.
  launcher   On a Mac with osacompile, "Open <Title>.app" is made.
  doctor     check_apps reads the folder as the check-up would: the summary, and
             F50 to F54 each from the state that earns it; the sendable wording
             never carries a thing's title. And the F18 line now starts with
             the tile's name.
  guard      The delete guard lets the copied parts run, as it must, since the
             assistant starts them for the owner; the parts carry nothing it
             refuses.
"""
from __future__ import annotations

import importlib.util
import io
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import zipfile
from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent
PARTS = PKG / "skills" / "build" / "parts"
PY = sys.executable

PASSED, FAILED = 0, []


def check(cond: bool, what: str) -> None:
    global PASSED
    if cond:
        PASSED += 1
    else:
        FAILED.append(what)
        print("  FAIL:", what)


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_scaffold(vault: Path, *extra: str) -> str:
    scaffold = load(PARTS / "scaffold.py", "scaffold")
    old = sys.argv
    sys.argv = ["scaffold.py", "--vault", str(vault)] + list(extra)
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            scaffold.main()
    finally:
        sys.argv = old
    return buf.getvalue()


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def get(url: str, headers: dict | None = None, data: bytes | None = None, method: str = "GET"):
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=3) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def wait_ping(port: int, want: bool, seconds: float) -> bool:
    end = time.time() + seconds
    while time.time() < end:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/api/ping", timeout=0.5)
            up = True
        except Exception:
            up = False
        if up == want:
            return True
        time.sleep(0.25)
    return False


def start_server(app: Path, port: int, *flags: str, env: dict | None = None) -> subprocess.Popen:
    e = dict(os.environ)
    e.update(env or {})
    return subprocess.Popen([PY, str(app / "server.py"), "--port", str(port), *flags],
                            cwd=str(app), env=e, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)


def test_scaffold(root: Path) -> Path:
    print("scaffold")
    vault = root / "wiki-a"
    shutil.copytree(PKG / "vault-template", vault)
    out = run_scaffold(vault, "--name", "demo-thing", "--title", "Demo Thing",
                       "--what", "A page that shows the demo numbers.", "--job", "--dry-run")
    check("Would make" in out and not (vault / "apps").exists(), "dry run makes nothing")
    out = run_scaffold(vault, "--name", "demo-thing", "--title", "Demo Thing",
                       "--what", "A page that shows the demo numbers.", "--job")
    app = vault / "apps" / "demo-thing"
    for f in ("README.md", "app.json", "index.html", "moblee-app.js", "server.py", "job.py",
              "com.moblee.demo-thing.plist"):
        check((app / f).exists(), f"scaffold made {f}")
    check((app / "data").is_dir() and (app / "state").is_dir(), "data/ and state/ made")
    page = vault / "wiki" / "Projects" / "Demo Thing.md"
    check(page.exists(), "the thing's page is made")
    check("A page that shows the demo numbers." in page.read_text(), "the page carries what it is")
    check((vault / "wiki" / "Projects.md").exists(), "the Projects index is made")
    check("[[Demo Thing]]" in (vault / "wiki" / "Projects.md").read_text(), "the index lists the thing")
    idx = (vault / "wiki" / "Index.md").read_text()
    check("[[Projects]]" in idx and idx.index("## Domains") < idx.index("[[Projects]]") < idx.index("## Subfolder"),
          "Index gains one line under Domains")
    leftovers = [p.name for p in app.rglob("*") if p.is_file() and "__APP_" in p.read_text(errors="replace")]
    check(not leftovers, f"no placeholder left in the copied parts {leftovers}")
    check("__" not in page.read_text() and "__" not in (app / "README.md").read_text(),
          "no placeholder left on the page or README")
    m = json.loads((app / "app.json").read_text())
    check(m["name"] == "demo-thing" and m["title"] == "Demo Thing" and m["tier"] == 2 and m["job"],
          "app.json says what it is")
    plist = (app / "com.moblee.demo-thing.plist").read_text()
    check(str(app / "job.py") in plist and "<integer>7</integer>" in plist, "the launch agent names the job and the hour")
    check("launchctl load" in (app / "README.md").read_text(), "README gives the owner the lines to switch the job on")
    # a second run leaves everything alone
    (app / "index.html").write_text("<!doctype html><title>mine</title>", encoding="utf-8")
    out2 = run_scaffold(vault, "--name", "demo-thing", "--title", "Demo Thing", "--job")
    check((app / "index.html").read_text().startswith("<!doctype html><title>mine"), "an edited page is never overwritten")
    check("Left alone" in out2 and "Made:\n" in out2 and out2.count("\n   ") == out2.count("\n   "),
          "second run reports what it left alone")
    check((vault / "wiki" / "Projects.md").read_text().count("## Demo Thing") == 1, "the index is not given a second section")
    check(idx == (vault / "wiki" / "Index.md").read_text(), "Index is not given a second line")
    # bad names refuse
    try:
        run_scaffold(vault, "--name", "Bad Name", "--title", "x")
        check(False, "a bad name is refused")
    except SystemExit:
        check(True, "a bad name is refused")
    # outside: pointer only
    out3 = run_scaffold(vault, "--name", "big-thing", "--title", "Big Thing", "--outside", str(root / "Apps" / "big-thing"))
    big = vault / "apps" / "big-thing"
    check((big / "app.json").exists() and (big / "README.md").exists() and not (big / "server.py").exists(),
          "an outside thing gets a pointer and no server")
    check((vault / "wiki" / "data" / "big-thing").is_dir(), "an outside thing gets wiki/data/<name>/")
    check(json.loads((big / "app.json").read_text())["tier"] == 3, "an outside thing is tier 3")
    check("pointer" in (big / "README.md").read_text() and "server.py" not in (big / "README.md").read_text(),
          "an outside thing's README says it is a pointer and lists no parts")
    # (review of 19 October 2026) the port is chosen and recorded at scaffold time
    port = json.loads((app / "app.json").read_text())["port"]
    check(isinstance(port, int) and 7400 <= port <= 7499, "a port is chosen and recorded in app.json")
    # titles that would make an unopenable page, or the index's own name
    for bad in ("Tom?", "a*b", '"Quoted"', "<x>", ".hidden", "Trail.", "Projects", "projects"):
        try:
            run_scaffold(vault, "--name", "bad-title", "--title", bad)
            check(False, f"title {bad!r} is refused")
        except SystemExit:
            check(True, f"title {bad!r} is refused")
    # a title that another page in the wiki already has
    (vault / "wiki" / "Golf.md").write_text("# Golf\n")
    try:
        run_scaffold(vault, "--name", "golf", "--title", "Golf")
        check(False, "a title the wiki already has is refused")
    except SystemExit:
        check(True, "a title the wiki already has is refused")
    check(not (vault / "apps" / "golf").exists(), "and nothing was made for it")
    # the same name with a different title
    try:
        run_scaffold(vault, "--name", "demo-thing", "--title", "Demo Thing Two")
        check(False, "a second title for the same name is refused")
    except SystemExit:
        check(True, "a second title for the same name is refused")
    # a job hour that never comes
    try:
        run_scaffold(vault, "--name", "late", "--title", "Late", "--job", "--hour", "25")
        check(False, "an hour of 25 is refused")
    except SystemExit:
        check(True, "an hour of 25 is refused")
    # a vault path with an ampersand still gives a plist launchctl will read
    amp = root / "wiki & co"
    shutil.copytree(PKG / "vault-template", amp)
    run_scaffold(amp, "--name", "amp", "--title", "Amp", "--job", "--launcher")
    plist = amp / "apps" / "amp" / "com.moblee.amp.plist"
    check("&amp;" in plist.read_text() and " & " not in plist.read_text().split("<string>", 1)[1],
          "an ampersand in the folder's path is escaped in the plist")
    if shutil.which("plutil"):
        r = subprocess.run(["plutil", "-lint", str(plist)], capture_output=True, text=True)
        check(r.returncode == 0 and "OK" in r.stdout, "plutil accepts the plist")
    launcher_src = amp / "apps" / "amp" / "state" / "launcher.applescript"
    if launcher_src.exists():
        check("mkdir -p state" in launcher_src.read_text(), "the launcher makes state/ before writing into it")
    # an Index that links the Projects page by an alias does not gain a second line
    alias = root / "wiki-alias"
    shutil.copytree(PKG / "vault-template", alias)
    idx_a = alias / "wiki" / "Index.md"
    idx_a.write_text(idx_a.read_text().replace("## Domains\n", "## Domains\n\n- [[Projects|Things built]]\n"))
    run_scaffold(alias, "--name", "one", "--title", "One")
    check(idx_a.read_text().count("[[Projects") == 1, "an aliased Projects link is recognised")
    return vault


def test_server(vault: Path) -> None:
    print("server")
    app = vault / "apps" / "demo-thing"
    shutil.copy(PARTS / "index.html", app / "index.html")  # the real page back, for the title check
    (app / "index.html").write_text((app / "index.html").read_text().replace("__APP_TITLE__", "Demo Thing"))
    port = free_port()
    p = start_server(app, port, "--stay")
    try:
        check(wait_ping(port, True, 8), "server comes up")
        base = f"http://127.0.0.1:{port}"
        s, body = get(base + "/")
        check(s == 200 and b"Demo Thing" in body, "serves the page")
        s, body = get(base + "/api/ping")
        check(s == 200 and json.loads(body)["app"] == "demo-thing", "ping names the app")
        s, _ = get(base + "/api/data/example")
        check(s == 404, "a missing data file is a plain 404")
        s, _ = get(base + "/", headers={"Host": "evil.example:80"})
        check(s == 403, "a foreign Host is refused")
        s, _ = get(base + "/", headers={"Origin": "http://evil.example"})
        check(s == 403, "a foreign Origin is refused")
        s, _ = get(base + "/api/save/example", method="POST", data=b"{}", headers={"Content-Type": "application/json"})
        check(s == 403, "a save without the page's header is refused")
        hdr = {"Content-Type": "application/json", "X-Requested-By": "moblee-app"}
        s, _ = get(base + "/api/save/example", method="POST", data=b'{"n": 1}', headers=hdr)
        check(s == 200 and json.loads((app / "data" / "example.json").read_text()) == {"n": 1}, "a save writes data/<name>.json")
        s, _ = get(base + "/api/save/example", method="POST", data=b'{"n": 2}', headers=hdr)
        prev = list((app / "state" / "previous").glob("example-*.json"))
        check(len(prev) == 1 and json.loads(prev[0].read_text()) == {"n": 1}, "a second save keeps the previous copy")
        s, body = get(base + "/api/data/example")
        check(s == 200 and json.loads(body) == {"n": 2}, "the saved file reads back")
        s, _ = get(base + "/api/save/bad%20name", method="POST", data=b"{}", headers=hdr)
        check(s in (400, 404), "a bad data name is refused")
        s, _ = get(base + "/state/server-log.txt")
        check(s == 403, "state/ is not served")
        (app / ".git").mkdir(exist_ok=True)
        (app / ".git" / "config").write_text("[core]\n")
        s, _ = get(base + "/.git/config")
        check(s == 403, "hidden files are not served")
        # (review of 19 October 2026) the gate reads the path as it will be opened
        s, _ = get(base + "/State/server-log.txt")
        check(s == 403, "state/ in another case is not served")
        s, _ = get(base + "/%2Egit/config")
        check(s == 403, "a hidden file spelt with %2E is not served")
        s, _ = get(base + "/%73tate/server-log.txt")
        check(s == 403, "state/ spelt with %73 is not served")
        s, _ = get(base + "/data/")
        check(s == 403, "folders are not listed")
        s, _ = get(base + "/", method="HEAD", headers={"Host": "evil.example:80"})
        check(s == 403, "HEAD with a foreign Host is refused")
        s, _ = get(base + "/state/server-log.txt", method="HEAD")
        check(s == 403, "HEAD of state/ is refused")
        s, _ = get(base + "/", method="HEAD")
        check(s == 200, "HEAD of the page is answered")
        s, _ = get(base + "/api/save/example", method="POST", data=b"{}",
                   headers={**hdr, "Content-Length": "abc"})
        check(s == 400, "a Content-Length that is not a number is a 400, not a crash")
        # a second start finds the first
        r = subprocess.run([PY, str(app / "server.py"), "--port", str(port)], cwd=str(app),
                           capture_output=True, text=True, timeout=10)
        check(r.returncode == 0 and "already running" in r.stdout, "a second start finds the first and stops")
    finally:
        p.terminate()
        p.wait(timeout=5)
    # stops when the page says goodbye
    port = free_port()
    p = start_server(app, port)
    try:
        check(wait_ping(port, True, 8), "server (lifecycle) comes up")
        get(f"http://127.0.0.1:{port}/api/heartbeat", method="POST", data=b"{}",
            headers={"X-Requested-By": "moblee-app", "Content-Type": "application/json"})
        get(f"http://127.0.0.1:{port}/api/leaving", method="POST", data=b"")
        check(wait_ping(port, False, 15), "stops within the grace after the page's goodbye")
        p.wait(timeout=5)
        check(p.returncode == 0, "exits cleanly after the goodbye")
    finally:
        if p.poll() is None:
            p.terminate()
    # a hand-edited app.json that is not an object does not stop the start
    manifest = app / "app.json"
    kept = manifest.read_text()
    manifest.write_text("[]")
    port = free_port()
    p = start_server(app, port, "--stay")
    try:
        check(wait_ping(port, True, 8), "a hand-edited app.json that is a list still lets the server start")
    finally:
        p.terminate()
        p.wait(timeout=5)
        manifest.write_text(kept)
    # stops when nobody is looking
    port = free_port()
    p = start_server(app, port, env={"MOBLEE_APP_IDLE": "3"})
    try:
        check(wait_ping(port, True, 8), "server (idle) comes up")
        check(wait_ping(port, False, 12), "stops when nobody has looked for the idle time")
    finally:
        if p.poll() is None:
            p.terminate()
    log = (app / "state" / "server-log.txt").read_text()
    check("the tab was closed" in log and "nobody looking" in log, "the log says why it stopped")


def test_job(vault: Path) -> None:
    print("job")
    app = vault / "apps" / "demo-thing"
    r = subprocess.run([PY, str(app / "job.py")], cwd=str(app), capture_output=True, text=True, timeout=20)
    rec = json.loads((app / "state" / "last-run.json").read_text())
    check(r.returncode == 0 and rec["ok"] is True and rec["finished"], "a run that succeeds records ok")
    check("ok" in (app / "state" / "job-log.txt").read_text(), "and a dated log line")
    broken = app / "job-broken.py"
    broken.write_text((app / "job.py").read_text().replace(
        'return "Nothing to do yet: work() has not been written."', 'raise RuntimeError("the website changed")'))
    r = subprocess.run([PY, str(broken)], cwd=str(app), capture_output=True, text=True, timeout=20)
    rec = json.loads((app / "state" / "last-run.json").read_text())
    check(r.returncode == 1 and rec["ok"] is False and "the website changed" in rec["message"],
          "a run that fails records the failure and exits non-zero")
    check("FAILED" in (app / "state" / "job-log.txt").read_text(), "the failure reaches the log")


def test_launcher(root: Path) -> None:
    print("launcher")
    if not shutil.which("osacompile"):
        print("  (no osacompile here; skipped)")
        return
    vault = root / "wiki-b"
    shutil.copytree(PKG / "vault-template", vault)
    run_scaffold(vault, "--name", "clicky", "--title", "Clicky", "--launcher")
    app = vault / "apps" / "clicky" / "Open Clicky.app"
    check(app.is_dir() and (app / "Contents").is_dir(), "Open <Title>.app is made")
    check("Open Clicky.app" in (vault / "apps" / "clicky" / "README.md").read_text(), "README tells the owner to double-click it")


def test_doctor(vault: Path, root: Path) -> None:
    print("doctor")
    doctor = load(PKG / "scripts" / "moblee-doctor.py", "moblee_doctor")
    app = vault / "apps" / "demo-thing"

    def rows_for(v: Path) -> list:
        f = doctor.Findings()
        doctor.check_apps(f, v)
        return f.rows

    def guide(rows, code):
        return [r for r in rows if r.get("guide") == code]

    rows = rows_for(vault)
    summary = [r for r in rows if "built beside the wiki" in r["text"]]
    check(len(summary) == 1 and summary[0]["level"] == "OK" and "Demo Thing" in summary[0]["text"]
          and "Big Thing" in summary[0]["text"], "the summary counts and names what is built")
    check("Demo Thing" not in summary[0]["sendable"] and "2 things" in summary[0]["sendable"].lower(),
          "the sendable summary carries the count and no name")
    check(guide(rows, "F54") and "Big Thing" in guide(rows, "F54")[0]["text"]
          and "Big Thing" not in guide(rows, "F54")[0]["sendable"], "F54 when the outside folder is not there")
    (root / "Apps" / "big-thing").mkdir(parents=True)
    rows = rows_for(vault)
    check(not guide(rows, "F54"), "no F54 once the outside folder exists")
    # the job: last run was a failure (left by the job test)
    f53 = guide(rows, "F53")
    check(f53 and "failed" in f53[0]["text"] and "the website changed" in f53[0]["text"], "F53 for a failed last run")
    rec = app / "state" / "last-run.json"
    rec.write_text(json.dumps({"started": "2026-01-01T07:30:00", "finished": "2026-01-01T07:30:05",
                               "ok": True, "message": "fine"}))
    rows = rows_for(vault)
    f53 = guide(rows, "F53")
    check(f53 and "may have stopped" in f53[0]["text"], "F53 for a job long overdue")
    import datetime
    now = datetime.datetime.now().replace(microsecond=0)
    rec.write_text(json.dumps({"started": now.isoformat(), "finished": now.isoformat(), "ok": True, "message": "fine"}))
    rows = rows_for(vault)
    check(not guide(rows, "F53") and any("succeeded" in r["text"] for r in rows), "a fresh successful run is OK")
    # F52: a port browsers refuse
    m = json.loads((app / "app.json").read_text())
    m["port"] = 4190
    (app / "app.json").write_text(json.dumps(m))
    check(guide(rows_for(vault), "F52"), "F52 for a port browsers refuse")
    m["port"] = 7412
    (app / "app.json").write_text(json.dumps(m))
    check(not guide(rows_for(vault), "F52"), "no F52 for a good port")
    # F51: an install folder inside the wiki
    (app / "node_modules").mkdir()
    check(guide(rows_for(vault), "F51"), "F51 for node_modules inside the wiki")
    # F50: a folder with no app.json, and one whose page is missing
    (vault / "apps" / "stray").mkdir()
    rows = rows_for(vault)
    check(any("no app.json" in r["text"] for r in guide(rows, "F50")), "F50 for a folder with no app.json")
    (vault / "apps" / "stray" / "app.json").write_text(json.dumps({"title": "Stray", "page": "wiki/Projects/Stray.md"}))
    rows = rows_for(vault)
    f50 = [r for r in guide(rows, "F50") if "Stray" in r["text"]]
    check(f50 and "README" in f50[0]["text"] and "page" in f50[0]["text"] and "Stray" not in f50[0]["sendable"],
          "F50 names what is missing, and the sendable line does not name the thing")
    (vault / "apps" / "stray" / "app.json").write_text("{not json")
    check(any("cannot be read" in r["text"] for r in guide(rows_for(vault), "F50")), "F50 for an app.json that cannot be read")
    # no apps/ at all: nothing said
    empty = root / "wiki-empty"
    shutil.copytree(PKG / "vault-template", empty)
    check(rows_for(empty) == [], "a wiki with nothing built gets no line")
    # F18 now leads with the tile's name
    (vault / ".moblee").mkdir(exist_ok=True)
    (vault / ".moblee" / "requests.json").write_text(json.dumps({"requests": [
        {"kind": "item", "key": "mac-apps", "why": "x", "status": "waiting"}]}))
    f = doctor.Findings()
    doctor.check_vault(f, vault, PKG)
    f18 = [r for r in f.rows if r.get("guide") == "F18"]
    check(f18 and f18[0]["text"].startswith("Waiting in the Moblee app: mac-apps."), "F18 starts with the tile's name")
    card = doctor.card_line(f18[0], lambda s: s)
    check("mac-apps" in card, "and the tile's name survives the card's shortening")


def test_keychain() -> None:
    print("keychain")
    text = (PARTS / "keychain.py").read_text()
    check('"-w", value' not in text and '"security", "-i"' in text,
          "the secret goes to security on its standard input, never on a command line")


def test_guard(vault: Path) -> None:
    print("guard")
    guard = PKG / "safety" / "bash-guard.py"
    app = vault / "apps" / "demo-thing"

    def verdict(cmd: str) -> int:
        payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": cmd}})
        r = subprocess.run([PY, str(guard)], input=payload, capture_output=True, text=True, timeout=20,
                           env=dict(os.environ, MOBLEE_VAULT=str(vault)))
        return r.returncode
    check(verdict(f'cd "{app}" && python3 server.py --open') == 0, "the guard lets the copied server run")
    check(verdict(f'python3 "{app}/job.py"') == 0, "the guard lets the copied job run")
    check(verdict(f'python3 "{PARTS}/scaffold.py" --vault "{vault}" --name x --title X --dry-run') == 0,
          "the guard lets the scaffold run (pinned by hash)")
    check(verdict(f'python3 "{PARTS}/keychain.py" has x key') == 0, "the guard lets the Keychain helper run (pinned)")
    check(verdict(f'rm -rf "{app}/data"') != 0, "and still refuses a deletion in the same folder")
    # (0.12.0) the four helpers that run in place, and the job switch
    check(verdict(f'python3 "{PARTS}/publish.py" --vault "{vault}" --name demo-thing --status') == 0,
          "the guard lets publish.py run (pinned)")
    check(verdict(f'python3 "{PARTS}/share.py" --vault "{vault}" --name demo-thing --dry-run') == 0,
          "the guard lets share.py run (pinned)")
    check(verdict(f'python3 "{PARTS}/think-job.py" --app "{app}" --dry-run') == 0,
          "the guard lets think-job.py run (pinned)")
    check(verdict(f'python3 "{PKG}/scripts/job-switch.py" --vault "{vault}" --name demo-thing --status') == 0,
          "the guard lets job-switch.py run (pinned)")
    check(verdict(f'python3 "{app}/notify.py" Demo "finished: x"') == 0, "the guard lets the copied notify.py run")


# --- (0.12.0) the building parts: reach, the thinking job, the preview entry, alerts, the web, kits ---

def test_reach_think_preview(root: Path, vault: Path) -> None:
    print("reach, thinking job, preview entry")
    run_scaffold(vault, "--name", "morning", "--title", "Morning Page", "--think", "--reach", "--hour", "6", "--minute", "15")
    app = vault / "apps" / "morning"
    check((app / "prompt.md").exists() and (app / "fence.json").exists() and not (app / "job.py").exists(),
          "a thinking job gets prompt.md and fence.json, and no job.py")
    plist = (app / "com.moblee.morning.plist").read_text()
    check(str(PARTS / "think-job.py") in plist and "--app" in plist and "<integer>6</integer>" in plist
          and "<integer>15</integer>" in plist, "its scheduler file runs think-job.py against the folder at the hour")
    if shutil.which("plutil"):
        r = subprocess.run(["plutil", "-lint", str(app / "com.moblee.morning.plist")], capture_output=True, text=True)
        check(r.returncode == 0, "plutil accepts the thinking job's scheduler file")
    m = json.loads((app / "app.json").read_text())
    check(m["job"]["thinking"] is True and m["reach"] is True and m["publish"] is None and m["job"]["hour"] == 6,
          "app.json records thinking, reach, the hour and no web yet")
    readme = (app / "README.md").read_text()
    check("Switch on" in readme or "switch on" in readme, "README says the owner switches the job on from the app")
    check("From your phone" in readme and "awake" in readme, "README says the phone reaches it while the Mac is awake")
    check("next wake" in readme, "README says a missed hour runs at the next wake")
    check((app / "notify.py").exists() and "__APP_" not in (app / "notify.py").read_text(), "notify.py is laid down")
    prompt = (app / "prompt.md").read_text()
    check("__APP_" not in prompt and "__OWNER__" not in prompt and "__VAULT__" in prompt and "__TODAY__" in prompt
          and "__DATE__" not in prompt, "prompt.md keeps the two placeholders think-job.py fills and no others")
    lj = json.loads((vault / ".claude" / "launch.json").read_text())
    names = [c["name"] for c in lj["configurations"]]
    check("morning" in names and "demo-thing" in names, "launch.json gains a preview entry per thing")
    entry = next(c for c in lj["configurations"] if c["name"] == "morning")
    check(entry["runtimeArgs"][0] == "apps/morning/server.py" and entry["port"] == m["port"],
          "the preview entry runs the thing's server on its recorded port")
    run_scaffold(vault, "--name", "morning", "--title", "Morning Page", "--think")
    lj2 = json.loads((vault / ".claude" / "launch.json").read_text())
    check([c["name"] for c in lj2["configurations"]].count("morning") == 1, "a second run adds no second preview entry")
    odd = root / "wiki-odd"
    shutil.copytree(PKG / "vault-template", odd)
    (odd / ".claude").mkdir(exist_ok=True)
    (odd / ".claude" / "launch.json").write_text("[1, 2]\n")
    out = run_scaffold(odd, "--name", "o", "--title", "O")
    check((odd / ".claude" / "launch.json").read_text() == "[1, 2]\n" and "not in the shape" in out,
          "a launch.json of another shape is left exactly as it was, and named")
    try:
        run_scaffold(vault, "--name", "out-reach", "--title", "Out Reach", "--outside", str(root / "Apps" / "out-reach"), "--reach")
        check(False, "--reach with --outside is refused")
    except SystemExit:
        check(True, "--reach with --outside is refused")
    try:
        run_scaffold(vault, "--name", "out-think", "--title", "Out Think", "--outside", str(root / "Apps" / "out-think"), "--think")
        check(False, "--think with --outside is refused")
    except SystemExit:
        check(True, "--think with --outside is refused")
    # (0.12.0) a job on one day a week
    run_scaffold(vault, "--name", "saturday", "--title", "Saturday Thing", "--think", "--weekday", "6", "--hour", "9", "--minute", "30")
    sat = (vault / "apps" / "saturday" / "com.moblee.saturday.plist").read_text()
    check("<key>Weekday</key>" in sat and "<integer>6</integer>" in sat, "a weekly job's scheduler file names the day")
    check(json.loads((vault / "apps" / "saturday" / "app.json").read_text())["job"]["every_hours"] == 168,
          "and its record says it runs once a week")
    if shutil.which("plutil"):
        r = subprocess.run(["plutil", "-lint", str(vault / "apps" / "saturday" / "com.moblee.saturday.plist")],
                           capture_output=True, text=True)
        check(r.returncode == 0, "plutil accepts the weekly scheduler file")
    try:
        run_scaffold(vault, "--name", "bad-day", "--title", "Bad Day", "--job", "--weekday", "7")
        check(False, "a weekday of 7 is refused")
    except SystemExit:
        check(True, "a weekday of 7 is refused")
    # the server and the phone route: no route recorded, a loopback route, a route this Mac cannot bind
    home = root / "reach-home"
    (home / ".config" / "moblee").mkdir(parents=True, exist_ok=True)
    port = free_port()
    p = start_server(app, port, "--stay", env={"HOME": str(home)})
    try:
        check(wait_ping(port, True, 8), "a thing built with reach still comes up with no route recorded")
        s, body = get(f"http://127.0.0.1:{port}/api/reach")
        check(s == 200 and json.loads(body)["address"] is None and "this Mac only" in json.loads(body)["note"],
              "with no route recorded it says it is on this Mac only")
    finally:
        p.terminate(); p.wait(timeout=5)
    (home / ".config" / "moblee" / "reach.json").write_text('{"route": "named", "address": "127.0.0.1"}\n')
    port = free_port()
    p = start_server(app, port, "--stay", env={"HOME": str(home)})
    try:
        check(wait_ping(port, True, 8), "a loopback address as the route is ignored and the server comes up")
        s, body = get(f"http://127.0.0.1:{port}/api/reach")
        check(json.loads(body)["address"] is None, "and reports no phone route")
    finally:
        p.terminate(); p.wait(timeout=5)
    (home / ".config" / "moblee" / "reach.json").write_text('{"route": "tailscale", "address": "203.0.113.5"}\n')
    port = free_port()
    p = start_server(app, port, "--stay", env={"HOME": str(home)})
    try:
        check(wait_ping(port, True, 8), "an address this Mac does not have: the server still comes up on this Mac")
        s, body = get(f"http://127.0.0.1:{port}/api/reach")
        check(json.loads(body)["address"] is None, "and reports no phone route, since it could not answer there")
        log = (app / "state" / "server-log.txt")
        logged = log.read_text() if log.exists() else ""
        check("not reachable from the phone just now" in logged or "not reachable" in logged,
              "and says so calmly in its log")
    finally:
        p.terminate(); p.wait(timeout=5)
    # (cold review) reach written as the word no is not on
    m_no = json.loads((app / "app.json").read_text())
    m_no["reach"] = "no"
    (app / "app.json").write_text(json.dumps(m_no, indent=2) + "\n")
    before = (app / "state" / "server-log.txt").read_text() if (app / "state" / "server-log.txt").exists() else ""
    port = free_port()
    p = start_server(app, port, "--stay", env={"HOME": str(home)})
    try:
        check(wait_ping(port, True, 8), "with reach written as the word no, the server comes up")
        after = (app / "state" / "server-log.txt").read_text()
        check("not reachable" not in after[len(before):] and "also at" not in after[len(before):],
              "and never tries the phone route")
    finally:
        p.terminate(); p.wait(timeout=5)
    m_no["reach"] = True
    (app / "app.json").write_text(json.dumps(m_no, indent=2) + "\n")


def test_think_job(root: Path, vault: Path) -> None:
    print("think-job")
    app = vault / "apps" / "morning"
    fake = root / "fake-engine"
    fake.write_text("#!/bin/bash\n"
                    "case \"$*\" in *--allowedTools*--permission-mode*|*--permission-mode*--allowedTools*) ;; *) exit 3;; esac\n"
                    "case \"$*\" in *'Bash(rm:*)'*) echo 'a deleting tool reached the engine' >&2; exit 4;; esac\n"
                    "echo 'wrote wiki/Daily Notes/today morning.md'\n")
    fake.chmod(0o755)
    env = dict(os.environ, MOBLEE_ENGINE=str(fake), HOME=str(root / "think-home"))
    (root / "think-home" / ".config" / "moblee").mkdir(parents=True, exist_ok=True)
    job = [PY, str(PARTS / "think-job.py"), "--app", str(app)]
    r = subprocess.run(job + ["--dry-run"], env=env, capture_output=True, text=True, timeout=60)
    check(r.returncode == 0 and "would run" in r.stdout and "time limit 20" in r.stdout and "the Mac's own" in r.stdout,
          "dry run says what it would run, with the Mac's own sign-in")
    fence = json.loads((app / "fence.json").read_text())
    fence["battery_floor"] = 0
    fence["alert"] = False
    fence["allowed_tools"].append("Bash(rm:*)")
    (app / "fence.json").write_text(json.dumps(fence))
    r = subprocess.run(job, env=env, capture_output=True, text=True, timeout=120)
    check(r.returncode == 0 and "wrote wiki" in r.stdout, "a run with a stand-in engine finishes")
    last = json.loads((app / "state" / "last-run.json").read_text())
    check(last["ok"] is True and last.get("thinking") is True and "wrote wiki" in last["message"],
          "the run is recorded like any job, marked as a thinking job")
    check("wrote wiki" in (app / "state" / "last-answer.md").read_text(), "the answer is kept in full")
    check("ok wrote" in (app / "state" / "job-log.txt").read_text(), "and the log has its dated line")
    (root / "think-home" / ".config" / "moblee" / "claude-token").write_text("sk-ant-oat01-" + "x" * 40 + "\n")
    r = subprocess.run(job + ["--dry-run"], env=env, capture_output=True, text=True, timeout=60)
    check("the long-lived token" in r.stdout, "with the item's sign-in kept, the job uses it")
    fake.write_text("#!/bin/bash\necho boom >&2\nexit 1\n")
    r = subprocess.run(job, env=env, capture_output=True, text=True, timeout=120)
    last = json.loads((app / "state" / "last-run.json").read_text())
    check(r.returncode == 1 and last["ok"] is False and "boom" in last["message"],
          "a failed run is recorded as failed, with the engine's last line")
    fake.write_text("#!/bin/bash\nsleep 5\n")
    fence["minutes"] = 1
    (app / "fence.json").write_text(json.dumps(fence))
    env_fast = dict(env)
    # the limit is whole minutes; prove the path with a tiny stand-in limit through the fence's own reading
    r = subprocess.run(job + ["--dry-run"], env=env_fast, capture_output=True, text=True, timeout=60)
    check("time limit 1 minutes" in r.stdout, "the time limit comes from the fence")
    run_scaffold(vault, "--name", "plain-job", "--title", "Plain Job", "--job")
    r = subprocess.run([PY, str(PARTS / "think-job.py"), "--app", str(vault / "apps" / "plain-job")],
                       env=env, capture_output=True, text=True, timeout=60)
    last = json.loads((vault / "apps" / "plain-job" / "state" / "last-run.json").read_text())
    check(r.returncode == 1 and "no prompt.md" in last["message"], "a folder with no prompt is recorded as failed, plainly")
    bare = root / "bare-thing"
    bare.mkdir()
    r = subprocess.run([PY, str(PARTS / "think-job.py"), "--app", str(bare)], env=env, capture_output=True, text=True, timeout=60)
    check(r.returncode == 1 and not (bare / "state").exists() and "not apps/<name>/" in r.stdout,
          "a folder with no wiki above it is refused, and nothing is written into it")
    # (cold review) the fence is a list of what is allowed, not of what is not
    fence3 = dict(fence, allowed_tools=["Read", "Edit", "Bash(*)", "Bash", "Bash(git  push:*)", "Bash(sh:*)",
                                        "Bash(find * -delete)", "Bash(git add:*)", "Bash( git  commit :*)",
                                        "Bash(python3 -c:*)", "WebFetch"],
                  alert="no", model="--dangerously-skip-permissions", minutes=20)
    (app / "fence.json").write_text(json.dumps(fence3))
    probe = root / "probe-engine"
    probe.write_text("#!/bin/bash\nprintf '%s\\n' \"$@\" > \"$PROBE_OUT\"\necho ok\n")
    probe.chmod(0o755)
    env_probe = dict(env, MOBLEE_ENGINE=str(probe), PROBE_OUT=str(root / "probe-args.txt"))
    r = subprocess.run(job, env=env_probe, capture_output=True, text=True, timeout=120)
    args = (root / "probe-args.txt").read_text().splitlines() if (root / "probe-args.txt").exists() else []
    tools_arg = args[args.index("--allowedTools") + 1] if "--allowedTools" in args else ""
    check(r.returncode == 0 and tools_arg == "Read,Edit,Bash(git add:*),Bash(git commit:*)",
          f"only the allowed tools reach the engine, in a tidy form ({tools_arg})")
    check("--model" not in args, "a model name that is really a flag never reaches the engine")
    never = args[args.index("--disallowedTools") + 1] if "--disallowedTools" in args else ""
    check("Edit(scripts/**)" in never and "Write(**/*.py)" in never and "Bash(git commit --amend:*)" in never,
          "what no job may write, and a commit that rewrites history, are refused whatever the fence allows")
    (app / "fence.json").write_text(json.dumps(dict(fence, allowed_tools=["Bash(*)"], battery_floor=0, alert=False)))
    r_empty = subprocess.run(job, env=env_probe, capture_output=True, text=True, timeout=120)
    check(r_empty.returncode == 0, "a fence with nothing allowed still runs")
    args2 = (root / "probe-args.txt").read_text().splitlines()
    check(args2[args2.index("--allowedTools") + 1] == "Read", "a fence with nothing allowed in it leaves the job able only to read")
    (app / "fence.json").write_text(json.dumps(fence3))
    check("dropped from the fence: Bash(*)" in r.stdout and "dropped from the fence: Bash(sh:*)" in r.stdout,
          "what was dropped is named")
    check("alert False" in subprocess.run(job + ["--dry-run"], env=env_probe, capture_output=True, text=True, timeout=60).stdout,
          "alert written as the word no reads as off")
    (app / "prompt.md").rename(app / "prompt.md.kept")
    (app / "prompt.md").symlink_to(root / "probe-engine")
    r = subprocess.run(job, env=env_probe, capture_output=True, text=True, timeout=60)
    check(r.returncode == 1 and "link to somewhere else" in json.loads((app / "state" / "last-run.json").read_text())["message"],
          "a prompt that is a link to somewhere else is not read")
    (app / "prompt.md").unlink()
    (app / "prompt.md.kept").rename(app / "prompt.md")
    stray = vault / "stray-thing"
    stray.mkdir()
    (stray / "prompt.md").write_text("hello\n")
    r = subprocess.run([PY, str(PARTS / "think-job.py"), "--app", str(stray)], env=env_probe, capture_output=True, text=True, timeout=60)
    check(r.returncode == 1 and not (stray / "state").exists(), "a folder that is not apps/<name>/ in a wiki is not run in it, and nothing is written there")


def test_notify(root: Path, vault: Path) -> None:
    print("notify")
    app = vault / "apps" / "demo-thing"
    home = root / "notify-home"
    (home / ".config" / "moblee").mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, HOME=str(home))
    r = subprocess.run([PY, str(app / "notify.py"), "Demo", "finished: x.json"], env=env, capture_output=True, text=True, timeout=30)
    logged = (app / "state" / "alerts-log.txt").read_text()
    check(r.returncode == 1 and "not sent" in logged and "finished: x.json" in logged,
          "with no alerts chosen, nothing is sent and the line is kept")
    seen = []

    class H(BaseHTTPRequestHandler):
        def do_POST(self):
            n = int(self.headers.get("Content-Length", 0))
            seen.append((self.path, self.headers.get("Title"), self.rfile.read(n).decode("utf-8")))
            self.send_response(200)
            self.end_headers()

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        env["MOBLEE_NTFY_SERVER"] = f"http://127.0.0.1:{srv.server_address[1]}/"
        (home / ".config" / "moblee" / "ntfy-topic").write_text("moblee-testtopic\n")
        r = subprocess.run([PY, str(app / "notify.py"), "Demo", "finished:\n  x.json  "], env=env,
                           capture_output=True, text=True, timeout=30)
        check(r.returncode == 0 and seen and seen[0][0] == "/moblee-testtopic" and seen[0][1] == "Demo"
              and seen[0][2] == "finished: x.json", "with alerts chosen, one flattened line goes to the topic, with its title")
        check("sent: Demo" in (app / "state" / "alerts-log.txt").read_text(), "and the send is recorded")
        (home / ".config" / "moblee" / "ntfy-topic").write_text("bad topic!\n")
        before = len(seen)
        r = subprocess.run([PY, str(app / "notify.py"), "Demo", "x"], env=env, capture_output=True, text=True, timeout=30)
        check(r.returncode == 1 and len(seen) == before, "a topic with odd characters is not used")
        srv.shutdown()
        (home / ".config" / "moblee" / "ntfy-topic").write_text("moblee-testtopic\n")
        r = subprocess.run([PY, str(app / "notify.py"), "Demo", "x"], env=env, capture_output=True, text=True, timeout=30)
        check(r.returncode == 1 and "FAILED to send" in (app / "state" / "alerts-log.txt").read_text(),
              "when the phone service cannot be reached, the failure is recorded and nothing raises")
    finally:
        try:
            srv.shutdown()
        except Exception:
            pass


def test_publish_share_sweep(root: Path, vault: Path) -> None:
    print("publish, share, sweep")
    app = vault / "apps" / "demo-thing"
    (app / "data").mkdir(exist_ok=True)
    (app / "data" / "scores.json").write_text('[{"a": 1}]\n')
    (app / "data" / "secret.json").write_text('{"k": "x"}\n')
    m = json.loads((app / "app.json").read_text())
    m["publish"] = {"private": ["data/secret.json"]}
    (app / "app.json").write_text(json.dumps(m, indent=2) + "\n")
    env = dict(os.environ, HOME=str(root / "publish-home"))
    (root / "publish-home").mkdir(exist_ok=True)
    pub = [PY, str(PARTS / "publish.py"), "--vault", str(vault), "--name", "demo-thing"]
    r = subprocess.run(pub + ["--prepare"], env=env, capture_output=True, text=True, timeout=120)
    site = app / "site"
    check(r.returncode == 0 and (site / "index.html").exists() and (site / "data" / "scores.json").exists()
          and not (site / "data" / "secret.json").exists(), "the web copy holds the page and its data, minus what is private")
    check("onTheWeb" in (site / "moblee-app.js").read_text() and not (site / "server.py").exists(),
          "the web copy's helper reads plain files and no server goes up with it")
    check((site / ".nojekyll").exists() and (site / ".git").is_dir(), "the copy is its own small repository")
    check("gh repo create demo-thing-site --public" in r.stdout and "Claude asks the owner first" in r.stdout,
          "it prints the one command that sends it up, and says Claude asks first")
    m2 = json.loads((app / "app.json").read_text())
    check(m2["publish"]["repository"] == "demo-thing-site" and m2["publish"].get("prepared"),
          "app.json records the repository's name and the date")
    r = subprocess.run(pub + ["--status"], env=env, capture_output=True, text=True, timeout=60)
    check("prepared" in r.stdout and "not sent up" in r.stdout, "status says a copy is prepared and not yet sent")
    (app / "data" / "keys.json").write_text('{"token": "ghp_' + "A" * 40 + '"}\n')
    r = subprocess.run(pub + ["--prepare"], env=env, capture_output=True, text=True, timeout=120)
    check(r.returncode == 2 and "must not go" in r.stdout.lower(), "a key in the data stops the web copy")
    check(not (site / "data" / "keys.json").exists(), "and the key never reaches the web copy itself")
    (app / "data" / "keys.json").rename(app / "state" / "keys-set-aside.json")
    # (cold review) a file marked private after the first copy leaves the site's record
    m3 = json.loads((app / "app.json").read_text())
    m3["publish"] = {"private": ["data/secret.json", "data/scores.json"]}
    (app / "app.json").write_text(json.dumps(m3, indent=2) + "\n")
    r = subprocess.run(pub + ["--prepare"], env=env, capture_output=True, text=True, timeout=120)
    tracked = subprocess.run(["git", "-C", str(site), "ls-files"], capture_output=True, text=True).stdout
    check(r.returncode == 0 and "data/scores.json" not in tracked and "no longer carried" in r.stdout,
          "a file no longer carried leaves the site's record, and the run says so")
    check((site / "data" / "scores.json").exists(), "while the file itself is left on the disk")
    check("apps/*/site/" in (vault / ".gitignore").read_text(), "the wiki's ignore list gains the site line")
    # (cold review) a file named outside the thing's folder is left out; one the sweep cannot read stops it
    m3["publish"] = {"files": ["../../CLAUDE.md", "cert.pem"]}
    (app / "app.json").write_text(json.dumps(m3, indent=2) + "\n")
    (app / "cert.pem").write_text("-----BEGIN CERTIFICATE-----\nabc\n-----END CERTIFICATE-----\n")
    r = subprocess.run(pub + ["--prepare"], env=env, capture_output=True, text=True, timeout=120)
    check("left out       ../../CLAUDE.md" in r.stdout and not (site / "CLAUDE.md").exists() and not (app / "CLAUDE.md").exists(),
          "a file named outside the thing's folder is left out and lands nowhere")
    check(r.returncode == 0 and (site / "cert.pem").exists() or r.returncode == 2,
          "a .pem is read by the sweep (it carried a plain certificate) or refused; never carried unread")
    big = app / "data" / "big.json"
    big.write_text("[" + ("1," * 6_500_000) + "1]")
    m3["publish"] = {}
    (app / "app.json").write_text(json.dumps(m3, indent=2) + "\n")
    r = subprocess.run(pub + ["--prepare"], env=env, capture_output=True, text=True, timeout=180)
    check(r.returncode == 2 and "could not be read by the sweep" in r.stdout and not (site / "data" / "big.json").exists(),
          "a file over the size the sweep reads is refused, not carried")
    big.rename(app / "state" / "big-set-aside.json")
    # (cold review) the owner's name is looked for
    rules = vault / "CLAUDE.md"
    rules.write_text(rules.read_text().replace("[Your Name]", "Sam Fenwick"), encoding="utf-8")
    (app / "data" / "note.json").write_text('{"by": "Sam Fenwick"}\n')
    r = subprocess.run(pub + ["--prepare"], env=env, capture_output=True, text=True, timeout=120)
    check(r.returncode == 0 and "the owner's name" in r.stdout and "Look at the lines" in r.stdout,
          "the owner's own name in the data is pointed out for a look, and does not stop the copy")
    (app / "data" / "note.json").rename(app / "state" / "note-set-aside.json")
    # (third read) spellings that walk past the never and private lists
    m3["publish"] = {"files": ["./server.py", "data/../README.md", "state/../index.html"], "private": ["data/secret.json"]}
    (app / "app.json").write_text(json.dumps(m3, indent=2) + "\n")
    r = subprocess.run(pub + ["--prepare"], env=env, capture_output=True, text=True, timeout=120)
    check(r.returncode == 0 and not (site / "server.py").exists() and not (site / "README.md").exists(),
          "a never-carried file spelt with ./ or x/../ is still never carried")
    m3["publish"] = {"private": "data/secret.json"}
    (app / "app.json").write_text(json.dumps(m3, indent=2) + "\n")
    r = subprocess.run(pub + ["--prepare"], env=env, capture_output=True, text=True, timeout=120)
    check(r.returncode == 1 and "must be a list" in r.stdout, "a private list that is not a list is refused, not read letter by letter")
    m3["publish"] = {"private": ["data/secret.json"]}
    (app / "app.json").write_text(json.dumps(m3, indent=2) + "\n")
    (app / "data" / "u16.json").write_bytes(('{"token": "ghp_' + "E" * 40 + '"}\n').encode("utf-16"))
    r = subprocess.run(pub + ["--prepare"], env=env, capture_output=True, text=True, timeout=120)
    check(r.returncode == 2 and "must not go" in r.stdout.lower(), "a key in a file written in another text encoding is still seen")
    (app / "data" / "u16.json").rename(app / "state" / "u16-set-aside.json")
    (app / "data" / "blob.json").write_bytes(b"\x00" * 4000 + b"ghp_" + b"F" * 40)
    r = subprocess.run(pub + ["--prepare"], env=env, capture_output=True, text=True, timeout=120)
    check(r.returncode == 2 and "not plain text" in r.stdout, "a file that is not plain text is refused rather than read as nothing")
    (app / "data" / "blob.json").rename(app / "state" / "blob-set-aside.json")
    r = subprocess.run(pub + ["--prepare"], env=env, capture_output=True, text=True, timeout=120)
    check(r.returncode == 0 and not list((app / "state").glob("web-staging-*")),
          "the folder the copy is assembled in is taken away again after a run")
    (app / "index.html").rename(app / "index.kept.html")
    (app / "index.html").symlink_to(app / "index.kept.html")
    r = subprocess.run(pub + ["--prepare"], env=env, capture_output=True, text=True, timeout=120)
    check(r.returncode == 1 and "link to somewhere else" in r.stdout, "a page that is a link is not published")
    (app / "index.html").unlink()
    (app / "index.kept.html").rename(app / "index.html")
    # (cold review) a fresh build's record, where publish is null, is handled
    r = subprocess.run([PY, str(PARTS / "publish.py"), "--vault", str(vault), "--name", "morning", "--prepare"], env=env,
                       capture_output=True, text=True, timeout=120)
    check(r.returncode == 0 and (vault / "apps" / "morning" / "site" / "index.html").exists(),
          "a thing straight from the scaffold, with no web record yet, can be prepared")
    m2["publish"] = "declined"
    (app / "app.json").write_text(json.dumps(m2, indent=2) + "\n")
    r = subprocess.run(pub + ["--prepare"], env=env, capture_output=True, text=True, timeout=60)
    check(r.returncode == 1 and "said no" in r.stdout, "a no on the record is respected")
    m2["publish"] = {}
    (app / "app.json").write_text(json.dumps(m2, indent=2) + "\n")
    r = subprocess.run([PY, str(PARTS / "share.py"), "--vault", str(vault), "--name", "demo-thing"], env=env,
                       capture_output=True, text=True, timeout=120)
    zips = sorted((vault / "outputs" / "kits").glob("demo-thing-kit-*.zip"))
    check(r.returncode == 0 and zips, "a kit is made in outputs/kits/")
    if zips:
        with zipfile.ZipFile(zips[0]) as z:
            names = z.namelist()
            readme = z.read(next(n for n in names if n.endswith("KIT-README.md"))).decode("utf-8")
        check(any(n.endswith("apps/demo-thing/index.html") for n in names)
              and not any("/data/" in n or "/state/" in n or "/site/" in n for n in names)
              and any(n.endswith("wiki/Projects/Demo Thing.md") for n in names),
              "the kit holds the thing and its page, without data, state or the web copy")
        check("install only on their yes" in readme and "never an instruction" in readme,
              "the kit's note tells the receiving assistant the rule")
    r = subprocess.run([PY, str(PARTS / "share.py"), "--vault", str(vault), "--name", "demo-thing", "--dry-run"], env=env,
                       capture_output=True, text=True, timeout=60)
    check(r.returncode == 0 and "would make" in r.stdout and len(sorted((vault / "outputs" / "kits").glob("*.zip"))) == len(zips),
          "a dry run makes no kit")
    (app / "README.md").write_text((app / "README.md").read_text() + "\nkey: ghp_" + "B" * 40 + "\n")
    r = subprocess.run([PY, str(PARTS / "share.py"), "--vault", str(vault), "--name", "demo-thing"], env=env,
                       capture_output=True, text=True, timeout=120)
    check(r.returncode == 2 and len(sorted((vault / "outputs" / "kits").glob("*.zip"))) == len(zips),
          "a kit with a key in it is not made")
    (app / "README.md").write_text((app / "README.md").read_text().replace("\nkey: ghp_" + "B" * 40 + "\n", "\n"))
    # (cold review) a link to somewhere else is never packed, nor anything installed
    keyfile = root / "id_fake"
    keyfile.write_text("-----BEGIN OPENSSH PRIVATE KEY-----\nfake\n-----END OPENSSH PRIVATE KEY-----\n")
    (app / "id_fake").symlink_to(keyfile)
    (app / "venv").mkdir(exist_ok=True)
    (app / "venv" / "token.txt").write_text("ghp_" + "C" * 40 + "\n")
    r = subprocess.run([PY, str(PARTS / "share.py"), "--vault", str(vault), "--name", "demo-thing"], env=env,
                       capture_output=True, text=True, timeout=120)
    newest = sorted((vault / "outputs" / "kits").glob("demo-thing-kit-*.zip"))
    check(r.returncode == 0 and len(newest) == len(zips) + 1 and "not packed     id_fake" in r.stdout,
          "a kit is still made, with the link named as not packed")
    with zipfile.ZipFile(newest[-1]) as z:
        names2 = z.namelist()
    check(not any(n.endswith("id_fake") or "/venv/" in n for n in names2), "and neither the link nor the installed folder is in it")
    (app / "id_fake").unlink()
    # (cold review) a file with no extension holding a key is read
    (app / "notes").write_text("ghp_" + "D" * 40 + "\n")
    r = subprocess.run([PY, str(PARTS / "share.py"), "--vault", str(vault), "--name", "demo-thing"], env=env,
                       capture_output=True, text=True, timeout=120)
    check(r.returncode == 2, "a key in a file with no extension still stops the kit")
    (app / "notes").rename(app / "state" / "notes-set-aside")
    # (third read) a FILE named like a folder a kit leaves out is still swept
    (app / "build").write_text("ghp_" + "G" * 40 + "\n")
    r = subprocess.run([PY, str(PARTS / "share.py"), "--vault", str(vault), "--name", "demo-thing"], env=env,
                       capture_output=True, text=True, timeout=120)
    check(r.returncode == 2, "a key in a file named like a left-out folder still stops the kit")
    (app / "build").rename(app / "state" / "build-set-aside")
    (app / "dist").mkdir(exist_ok=True)
    (app / "dist" / "bundle.js").write_text("built\n")
    r = subprocess.run([PY, str(PARTS / "share.py"), "--vault", str(vault), "--name", "demo-thing"], env=env,
                       capture_output=True, text=True, timeout=120)
    check(r.returncode == 0 and "not packed     dist/" in r.stdout, "a built folder left out of a kit is named as left out")
    r = subprocess.run([PY, str(PARTS / "sweep.py"), str(site)], env=env, capture_output=True, text=True, timeout=60)
    check(r.returncode in (0, 1), "the sweep reads the web copy clean, or with only things to look at")


def test_job_switch(root: Path, vault: Path) -> None:
    print("job-switch")
    env = dict(os.environ, HOME=str(root / "switch-home"))
    (root / "switch-home").mkdir(exist_ok=True)
    sw = [PY, str(PKG / "scripts" / "job-switch.py"), "--vault", str(vault)]
    r = subprocess.run(sw + ["--name", "demo-thing", "--status", "--json"], env=env, capture_output=True, text=True, timeout=60)
    s = json.loads(r.stdout)
    check(r.returncode == 0 and s["file"] is True and s["in_place"] is False and s["thinking"] is False
          and s["title"] == "Demo Thing", "status reads the thing's scheduler file, its title, and that it is not in place")
    r = subprocess.run(sw + ["--name", "morning", "--status", "--json"], env=env, capture_output=True, text=True, timeout=60)
    check(json.loads(r.stdout)["thinking"] is True, "a thinking job is known as one")
    r = subprocess.run(sw + ["--name", "demo-thing", "--on", "--dry-run", "--json"], env=env, capture_output=True, text=True, timeout=60)
    check(json.loads(r.stdout).get("would") == "switch on"
          and not (root / "switch-home" / "Library" / "LaunchAgents" / "com.moblee.demo-thing.plist").exists(),
          "a dry run of switching on puts nothing in place")
    r = subprocess.run(sw + ["--name", "no-such", "--on", "--json"], env=env, capture_output=True, text=True, timeout=60)
    check(r.returncode == 1 and "no schedule to switch on" in json.loads(r.stdout)["why"], "a thing with no job is refused plainly")
    # (cold review) a schedule file that is not the thing's own is refused
    other = vault / "apps" / "demo-thing" / "com.moblee.demo-thing.plist"
    kept = other.read_text()
    other.write_text(kept.replace("com.moblee.demo-thing", "com.other.thing"))
    r = subprocess.run(sw + ["--name", "demo-thing", "--on", "--dry-run", "--json"], env=env, capture_output=True, text=True, timeout=60)
    check(r.returncode == 1 and "not its own" in json.loads(r.stdout)["why"], "a schedule file with another label is refused")
    other.write_text(kept)
    # (third read) a schedule file that runs anything but the thing's own job or Moblee's own thinking job
    other.write_text(kept.replace(str(vault / "apps" / "demo-thing" / "job.py"), "/tmp/evil/think-job.py"))
    r = subprocess.run(sw + ["--name", "demo-thing", "--on", "--dry-run", "--json"], env=env, capture_output=True, text=True, timeout=60)
    check(r.returncode == 1, "a schedule file pointing at another thinking job by name alone is refused")
    other.write_text(kept.replace("<key>RunAtLoad</key>", "<key>EnvironmentVariables</key><dict><key>MOBLEE_ENGINE</key><string>/tmp/x</string></dict><key>RunAtLoad</key>"))
    r = subprocess.run(sw + ["--name", "demo-thing", "--on", "--dry-run", "--json"], env=env, capture_output=True, text=True, timeout=60)
    check(r.returncode == 1, "a schedule file that sets its own environment is refused")
    other.write_text(kept)
    r = subprocess.run(sw + ["--name", "morning", "--on", "--dry-run", "--json"], env=env, capture_output=True, text=True, timeout=60)
    check(r.returncode == 0 and json.loads(r.stdout).get("would") == "switch on", "a thinking job's own schedule file passes")
    r = subprocess.run(sw + ["--name", "bad name", "--status", "--json"], env=env, capture_output=True, text=True, timeout=60)
    check(r.returncode == 2, "a name with a space is refused")


def main() -> int:
    root = Path(tempfile.mkdtemp(prefix="moblee-build-test-"))
    try:
        vault = test_scaffold(root)
        test_server(vault)
        test_job(vault)
        test_launcher(root)
        test_doctor(vault, root)
        test_keychain()
        test_reach_think_preview(root, vault)
        test_think_job(root, vault)
        test_notify(root, vault)
        test_publish_share_sweep(root, vault)
        test_job_switch(root, vault)
        test_guard(vault)
    finally:
        print(f"(the throwaway folder is {root}; the system clears it in time)")
    print(f"\n{PASSED} passed, {len(FAILED)} failed")
    for f in FAILED:
        print("  -", f)
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
