#!/usr/bin/env python3
"""publish.py - put a thing's page on the web, as a public site on GitHub Pages.

    python3 publish.py --vault <wiki> --name <name> --prepare      # build the web copy and sweep it
    python3 publish.py --vault <wiki> --name <name> --finish       # after the first push: switch the address on, record it
    python3 publish.py --vault <wiki> --name <name> --status

The pattern is the one the maker's own public sites use: a page with no server
behind it, copied with its data into a small public repository, served by
GitHub Pages at https://<account>.github.io/<repository>/. It suits a page
that shows something: scores, a season, a chart, a record. It does not suit a
thing that saves, or that needs its server; those stay on the Mac.

--prepare assembles the web copy in a fresh folder of its own under state/
(never served, never kept in git, and taken away again when the run ends),
sweeps it there for keys, passwords and the owner's own name, refuses to
carry any file the sweep could not read (bar pictures, fonts and sounds),
and only then lays it into apps/<name>/site/: the page, its
helper swapped for the one that reads plain files instead of a server, the
data files, and anything named under "publish": {"files": [...]} in app.json
that lives inside the thing's own folder, leaving out "publish": {"private":
[...]}. A file that was carried before and is not in this copy is taken out
of the site's record (the file itself is left on the disk). site/ is its own
small repository, kept out of the wiki's history. It then prints the one
command the assistant runs, which Claude asks the owner about, as sending
anything to a website always does:

    gh repo create <repository> --public --source "<site>" --push

The repository's name is <name>-site unless app.json says otherwise. --finish
runs afterwards: it switches the address on through GitHub's own interface,
records the address in app.json and prints it. A later --prepare refreshes the
copy and commits; the assistant then pushes it (one asking, as before).

Needs the GitHub item from the Moblee app (the `gh` command, signed in).
Never runs on its own; never pushes by itself; never publishes anything the
sweep refused.
"""
from __future__ import annotations

import argparse
import datetime
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

PARTS = Path(__file__).resolve().parent
sys.path.insert(0, str(PARTS))
from sweep import MEDIA_EXT, report, sweep  # noqa: E402

ALWAYS = ("index.html",)
NEVER = {"server.py", "moblee-app.js", "job.py", "think-job.py", "notify.py", "keychain.py", "fence.json",
         "prompt.md", "app.json", "README.md"}
NEVER_DIRS = {"state", "site", "node_modules", ".git", "__pycache__", ".venv", "venv"}
REPO_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
IGNORE_LINE = "apps/*/site/"


def tidy_rel(rel: str) -> str:
    """A file name as written in app.json, with ./ and x/../ folded away, so
    that what is compared against the never and private lists is the file
    itself and not a spelling of it."""
    import os.path
    r = os.path.normpath(rel.strip())
    return "" if r in (".", "") else r


def gh(*args: str, timeout: int = 60) -> tuple[int, str]:
    try:
        r = subprocess.run(["gh", *args], capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as exc:
        return 1, str(exc)
    return r.returncode, (r.stdout or r.stderr).strip()


def git(site: Path, *args: str) -> tuple[int, str]:
    try:
        r = subprocess.run(["git", "-C", str(site), *args], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as exc:
        return 1, str(exc)
    return r.returncode, (r.stdout or r.stderr).strip()


def plain_date(iso) -> str:
    """2026-10-22 as the house writes it, 22 October 2026."""
    try:
        return datetime.date.fromisoformat(str(iso)).strftime("%-d %B %Y")
    except (TypeError, ValueError):
        return str(iso or "an unknown date")


def load_manifest(app: Path) -> dict | None:
    try:
        m = json.loads((app / "app.json").read_text(encoding="utf-8"))
        return m if isinstance(m, dict) else None
    except (OSError, ValueError):
        return None


def save_manifest(app: Path, m: dict) -> None:
    (app / "app.json").write_text(json.dumps(m, indent=2) + "\n", encoding="utf-8")


def publish_record(m: dict) -> dict:
    """The publish record as a dict, whatever app.json held there."""
    if not isinstance(m.get("publish"), dict):
        m["publish"] = {}
    return m["publish"]


def repo_name(m: dict, name: str) -> str:
    pub = m.get("publish") if isinstance(m.get("publish"), dict) else {}
    r = str(pub.get("repository") or f"{name}-site")
    return r if REPO_RE.match(r) and set(r) != {"."} else f"{name}-site"


def inside(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def ensure_ignored(vault: Path) -> None:
    """The wiki's history must not take the site's own repository in. One
    line is added to the wiki's .gitignore if it is not there; nothing else
    in that file is touched."""
    gi = vault / ".gitignore"
    if gi.is_symlink():
        print("The wiki's .gitignore is a link to somewhere else, so it was left alone; the owner adds the line "
              f"{IGNORE_LINE} by hand.")
        return
    try:
        current = gi.read_text(encoding="utf-8") if gi.exists() else ""
    except OSError:
        return
    if any(line.strip() == IGNORE_LINE for line in current.splitlines()):
        return
    sep = "" if current.endswith("\n") or not current else "\n"
    try:
        gi.write_text(current + sep + "# (0.12.0) a thing's web copy is its own small repository, not the wiki's\n"
                      + IGNORE_LINE + "\n", encoding="utf-8")
        print("Added one line to the wiki's .gitignore, so the web copy's own history stays out of the wiki's.")
    except OSError:
        pass


def prepare(vault: Path, app: Path, name: str, m: dict) -> int:
    site = app / "site"
    if site.exists() and not site.is_dir():
        print(f"apps/{name}/site exists and is not a folder; the owner moves it aside before a web copy can be made")
        return 1
    pub = publish_record(m)
    for key in ("files", "private"):
        if key in pub and not isinstance(pub[key], list):
            print(f"\"publish\": {{\"{key}\": ...}} in app.json must be a list of file names; it is not, so nothing was done")
            return 1
    extra = [tidy_rel(f) for f in (pub.get("files") or []) if isinstance(f, str)]
    private = {tidy_rel(f) for f in (pub.get("private") or []) if isinstance(f, str)}
    if (app / "index.html").is_symlink():
        print(f"apps/{name}/index.html is a link to somewhere else, which is not published")
        return 1
    if not (app / "index.html").is_file():
        print(f"apps/{name}/ has no index.html; there is no page to publish")
        return 1
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    staging = app / "state" / f"web-staging-{stamp}"
    n = 1
    while staging.exists():  # a fresh folder every run, never one with last time's files in it
        n += 1
        staging = app / "state" / f"web-staging-{stamp}-{n}"
    staging.mkdir(parents=True)
    wanted: list[tuple[Path, str]] = []
    left_out: list[str] = []
    for rel in list(ALWAYS) + extra:
        if not rel or rel.startswith("/") or rel == ".." or rel.startswith("../"):
            left_out.append(rel)
            continue
        src = app / rel
        first = rel.split("/")[0]
        if rel in NEVER or rel in private or first in NEVER_DIRS:
            continue
        if src.is_symlink() or not src.is_file() or not inside(src, app) or not inside(staging / rel, staging):
            left_out.append(rel)
            continue
        wanted.append((src, rel))
    data = app / "data"
    if data.is_dir():
        for p in sorted(data.iterdir()):
            rel = f"data/{p.name}"
            if rel in private or p.name.startswith("."):
                continue
            if p.is_symlink() or not p.is_file():
                left_out.append(rel)
                continue
            wanted.append((p, rel))
    for rel in left_out:
        print(f"  left out       {rel}: not a plain file inside this thing's own folder")
    for src, rel in wanted:
        dst = staging / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    shutil.copy2(PARTS / "moblee-app-static.js", staging / "moblee-app.js")
    (staging / ".nojekyll").write_text("", encoding="utf-8")
    critical, review, skipped, source = sweep(staging, vault)
    report(critical, review, source, skipped)
    unread = [(rel, why) for rel, why in skipped if Path(rel).suffix.lower() not in MEDIA_EXT]
    if critical or unread:
        # the copy assembled this run is this run's own and is taken away
        # again, so no copy of a secret lingers in a folder the wiki's sync carries
        shutil.rmtree(staging, ignore_errors=True)
        if critical:
            print("Stopped: something above must not go on the web. Nothing was laid into the web copy, and the "
                  "copy assembled for the sweep was taken away again.")
        else:
            print("Stopped: a file above could not be read by the sweep, so it is not carried. Name it under "
                  "\"publish\": {\"private\": [...]} in app.json to leave it out, or make it smaller or plain text.")
        return 2
    if review:
        print("Look at the lines marked above with the owner before publishing; they may be fine.")
    ensure_ignored(vault)
    site.mkdir(parents=True, exist_ok=True)
    carried: list[str] = []
    for p in sorted(staging.rglob("*")):
        if p.is_file():
            rel = p.relative_to(staging)
            dst = site / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dst)
            carried.append(str(rel))
    if not (site / ".git").is_dir():
        code, out = git(site, "init", "-q", "-b", "main")
        if code != 0:
            print("could not make the site's own repository:", out)
            return 1
    # the record holds exactly this copy: what was carried before and is not
    # carried now leaves the record (the file stays on the disk)
    code, tracked = git(site, "ls-files")
    if code == 0:
        for old in tracked.splitlines():
            if old and old not in carried:
                git(site, "rm", "-q", "--cached", "--", old)
                print(f"  no longer carried  {old} (the file is still on the disk)")
    git(site, "add", "--", *carried)
    git(site, "commit", "-q", "-m", f"the web copy, {datetime.datetime.now().strftime('%-d %B %Y %H:%M')}")
    shutil.rmtree(staging, ignore_errors=True)  # this run's own assembly folder, no longer needed
    repo = repo_name(m, name)
    pub["repository"] = repo
    pub["prepared"] = datetime.date.today().isoformat()
    save_manifest(app, m)
    print(f"The web copy is ready in apps/{name}/site/ ({len(carried)} files).")
    code, login = gh("api", "user", "-q", ".login")
    account = login if code == 0 and login else "<account>"
    if pub.get("url"):
        print("To send the new copy up, the assistant runs (Claude asks the owner first):")
        print(f'    git -C "{site}" push')
    else:
        print("To put it on the web for the first time, the assistant runs (Claude asks the owner first):")
        print(f'    gh repo create {repo} --public --source "{site}" --push')
        print(f"and then:  python3 \"{PARTS / 'publish.py'}\" --vault \"{vault}\" --name {name} --finish")
        print(f"The address will be https://{account}.github.io/{repo}/ once the web address is switched on.")
    return 0


def finish(vault: Path, app: Path, name: str, m: dict) -> int:
    repo = repo_name(m, name)
    code, login = gh("api", "user", "-q", ".login")
    if code != 0 or not login:
        print("GitHub is not signed in on this Mac (the GitHub item in the Moblee app signs you in).")
        return 1
    full = f"{login}/{repo}"
    code, _ = gh("repo", "view", full)
    if code != 0:
        print(f"The repository {full} is not on GitHub yet; run the create command first.")
        return 1
    code, out = gh("api", "-X", "POST", f"repos/{full}/pages", "-f", "build_type=legacy",
                   "-f", "source[branch]=main", "-f", "source[path]=/")
    if code != 0 and "already" not in out.lower() and "409" not in out:
        code2, _ = gh("api", f"repos/{full}/pages")
        if code2 != 0:
            print("The web address could not be switched on:", out[:300])
            return 1
    url = f"https://{login}.github.io/{repo}/"
    pub = publish_record(m)
    pub.update({"repository": repo, "account": login, "url": url, "published": datetime.date.today().isoformat()})
    save_manifest(app, m)
    print(f"On the web at {url} (it can take a minute or two to appear the first time).")
    print("The page in the wiki should carry this address; the assistant adds it.")
    return 0


def status(name: str, m: dict) -> int:
    if m.get("publish") == "declined":
        print(f"{name}: the owner said no to the web; not offered again.")
        return 0
    pub = m.get("publish") if isinstance(m.get("publish"), dict) else {}
    if pub.get("url"):
        print(f"{name}: on the web at {pub['url']} (published {plain_date(pub.get('published'))}, "
              f"copy prepared {plain_date(pub.get('prepared'))})")
    elif pub.get("prepared"):
        print(f"{name}: a web copy was prepared on {plain_date(pub['prepared'])} but not sent up yet")
    else:
        print(f"{name}: not on the web")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vault", required=True)
    ap.add_argument("--name", required=True)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--prepare", action="store_true")
    g.add_argument("--finish", action="store_true")
    g.add_argument("--status", action="store_true")
    a = ap.parse_args()
    vault = Path(a.vault).expanduser().resolve()
    if not a.name or not all(c.isalnum() or c == "-" for c in a.name):
        print("the name is letters, digits and hyphens")
        return 2
    app = vault / "apps" / a.name
    if not app.is_dir():
        print(f"apps/{a.name}/ is not in the wiki")
        return 2
    m = load_manifest(app)
    if m is None:
        print(f"apps/{a.name}/app.json does not read as the record of a thing; the assistant rewrites it from the page")
        return 2
    if m.get("publish") == "declined" and not a.status:
        print(f"The owner said no to putting {a.name} on the web; ask them before trying again, and if they say yes, "
              f"take \"declined\" out of app.json first.")
        return 1
    if a.prepare:
        return prepare(vault, app, a.name, m)
    if a.finish:
        return finish(vault, app, a.name, m)
    return status(a.name, m)


if __name__ == "__main__":
    sys.exit(main())
