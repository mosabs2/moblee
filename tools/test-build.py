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
import time
import urllib.error
import urllib.request
from contextlib import redirect_stdout
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


def main() -> int:
    root = Path(tempfile.mkdtemp(prefix="moblee-build-test-"))
    try:
        vault = test_scaffold(root)
        test_server(vault)
        test_job(vault)
        test_launcher(root)
        test_doctor(vault, root)
        test_keychain()
        test_guard(vault)
    finally:
        print(f"(the throwaway folder is {root}; the system clears it in time)")
    print(f"\n{PASSED} passed, {len(FAILED)} failed")
    for f in FAILED:
        print("  -", f)
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
