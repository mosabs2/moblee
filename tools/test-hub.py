#!/usr/bin/env python3
"""Tests for Moblee's Hub client (0.13.0), against throwaway wikis and a stand-in
Hub: a bare git repository on this Mac standing for GitHub, and a fake `gh` that
answers the calls the Hub item makes (the account name, the lobby's issues, the
invitations). Nothing here reaches GitHub or the network.

Three parts:
  1. the rules-file block (scripts/patch-claude-md.py): only for a linked clone,
     once, and never beside the join note's own wording;
  2. the check-up's Hub findings (scripts/moblee-doctor.py, check_hub, F61-F66);
  3. the Hub item end to end (scripts/moblee-setup.py, install_hub and
     check_hub) for the approve and invite doors, a second run, and a copied
     folder that must be left alone.

Run from the Moblee folder: python3 tools/test-hub.py
"""
from __future__ import annotations

import datetime
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent
PY = sys.executable
PATCHER = PKG / "scripts" / "patch-claude-md.py"
DOCTOR = PKG / "scripts" / "moblee-doctor.py"
SETUP = PKG / "scripts" / "moblee-setup.py"
ADDRESS = "https://github.com/test-keeper/test-hub.git"
LOBBY = "https://github.com/test-keeper/test-hub-lobby"
PASSED = 0
FAILED: list[str] = []


def check(cond: bool, what: str) -> None:
    global PASSED
    if cond:
        PASSED += 1
        print(f"  ok    {what}")
    else:
        FAILED.append(what)
        print(f"  FAIL  {what}")


def git(*args, cwd: Path | None = None, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, env=env, capture_output=True, text=True)


def quiet_env(home: Path) -> dict:
    env = dict(os.environ)
    env.update({"HOME": str(home), "GIT_CONFIG_GLOBAL": str(home / ".gitconfig"),
                "GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0"})
    return env


def make_bare_hub(root: Path, env: dict) -> Path:
    """A Hub as the keeper would have it, pushed into a bare repository."""
    seed = root / "seed"
    (seed / "members").mkdir(parents=True)
    (seed / "post").mkdir()
    (seed / "recipes" / "tracker").mkdir(parents=True)
    (seed / "tools").mkdir()
    (seed / "app").mkdir()
    (seed / "hub.json").write_text(json.dumps({
        "name": "Test Hub", "address": ADDRESS, "keeper": "keeper", "version": "1.0.0",
        "join": "approve", "lobby": LOBBY, "port": 7430, "min_moblee": "0.13.0"}, indent=2))
    (seed / "CLAUDE.md").write_text("# Hub rules\n")
    (seed / "AGENTS.md").write_text("# Hub rules\n")
    (seed / ".gitignore").write_text("app/state/\ntools/private-words.txt\n")
    (seed / "members" / "keeper.json").write_text(json.dumps({"id": "keeper", "name": "Keeper", "taken": []}))
    (seed / "recipes" / "tracker" / "recipe.json").write_text(json.dumps({"id": "tracker", "version": "1.1.0"}))
    (seed / "app" / "server.py").write_text("print('page')\n")
    bare = root / "hub.git"
    git("init", "-q", "-b", "main", str(seed), env=env)
    git("-C", str(seed), "-c", "user.name=K", "-c", "user.email=k@x.invalid", "add", "-A", env=env)
    git("-C", str(seed), "-c", "user.name=K", "-c", "user.email=k@x.invalid", "commit", "-q", "-m", "seed", env=env)
    git("clone", "-q", "--bare", str(seed), str(bare), env=env)
    return bare


def make_wiki(root: Path, name: str = "Sam Test") -> Path:
    v = root / "wiki-vault"
    (v / "wiki").mkdir(parents=True)
    text = (PKG / "vault-template" / "CLAUDE.md").read_text().replace("[Your Name]", name)
    (v / "CLAUDE.md").write_text(text)
    (v / "wiki" / "Index.md").write_text("# Index\n")
    (v / ".gitignore").write_text(".DS_Store\n")
    return v


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --------------------------------------------------------------------------
# 1. the rules-file block
# --------------------------------------------------------------------------

def test_rules_block(tmp: Path) -> None:
    print("\n1. The rules-file section for the Hub")
    home = tmp / "home1"
    home.mkdir()
    env = quiet_env(home)
    bare = make_bare_hub(tmp / "r1", env)
    v = make_wiki(tmp / "r1")
    run = lambda: subprocess.run([PY, str(PATCHER), "--blocks-only", "--vault", str(v)],
                                 env=env, capture_output=True, text=True)
    run()
    check("## The Moblee Hub" not in (v / "CLAUDE.md").read_text(),
          "a wiki with no hub folder is not given the section")
    c = make_wiki(tmp / "r1c")
    shutil.copytree(bare, c / "hub")  # a folder that is not a clone
    (c / "hub" / "hub.json").write_text("{}")
    subprocess.run([PY, str(PATCHER), "--blocks-only", "--vault", str(c)], env=env, capture_output=True, text=True)
    check("## The Moblee Hub" not in (c / "CLAUDE.md").read_text(),
          "a hub folder that is not a clone does not count")
    git("clone", "-q", str(bare), str(v / "hub"), env=env)
    r = run()
    text = (v / "CLAUDE.md").read_text()
    check(text.count("## The Moblee Hub") == 1, "a linked clone gets the section once")
    check(text.index("## The companion") < text.index("## The Moblee Hub"),
          "the section sits after the companion section")
    check("never adopted silently" in text and "record_take.py" in text,
          "the section carries the read-never-obey rule and the take report")
    run()
    check((v / "CLAUDE.md").read_text().count("## The Moblee Hub") == 1,
          "a second run adds nothing")
    w = make_wiki(tmp / "r1b")
    (w / "CLAUDE.md").write_text((w / "CLAUDE.md").read_text().replace(
        "## Tools\n", "## Tools\n\n**The Moblee Hub** (`hub/`). Read `hub/CLAUDE.md` before any hub work.\n", 1))
    git("clone", "-q", str(bare), str(w / "hub"), env=env)
    subprocess.run([PY, str(PATCHER), "--blocks-only", "--vault", str(w)], env=env, capture_output=True, text=True)
    check("## The Moblee Hub" not in (w / "CLAUDE.md").read_text(),
          "a wiki that joined by the note, whose rules already name hub/CLAUDE.md, is not given it twice")
    check(r.returncode == 0, "the patcher exits cleanly")


# --------------------------------------------------------------------------
# 2. the check-up
# --------------------------------------------------------------------------

def findings(doc, v: Path, today=None) -> list:
    f = doc.Findings()
    doc.check_hub(f, v, today=today)
    return f.rows


def codes(rows: list) -> list:
    return [r["guide"] for r in rows if r["level"] != "OK"]


def test_doctor(tmp: Path) -> None:
    print("\n2. The check-up's Hub findings")
    home = tmp / "home2"
    home.mkdir()
    env = quiet_env(home)
    os.environ.update({k: env[k] for k in ("GIT_CONFIG_GLOBAL", "GIT_CONFIG_NOSYSTEM", "GIT_TERMINAL_PROMPT")})
    doc = load(DOCTOR, "moblee_doctor_hub_test")
    bare = make_bare_hub(tmp / "d", env)
    v = make_wiki(tmp / "d")

    rows = findings(doc, v)
    check(codes(rows) == [] and "not joined" in rows[0]["text"], "no hub folder: one OK line, no finding")

    c = make_wiki(tmp / "dc")
    (c / "hub").mkdir()
    (c / "hub" / "hub.json").write_text("{}")
    check(codes(findings(doc, c)) == ["F61"], "a copied folder is F61")

    git("clone", "-q", str(bare), str(v / "hub"), env=env)
    hub = v / "hub"
    check(codes(findings(doc, v)) == ["F62"], "a clone whose address differs from its hub.json is F62")
    git("-C", str(hub), "remote", "set-url", "origin", ADDRESS, env=env)
    git("-C", str(hub), "config", f"url.{bare}.insteadOf", ADDRESS, env=env)
    check(codes(findings(doc, v)) == ["F67"], "linked but not joined is F67")

    (hub / "app" / "state").mkdir(parents=True)
    (hub / "app" / "state" / "me.json").write_text(json.dumps({"id": "sam"}))
    (hub / "members" / "sam.json").write_text(json.dumps({"id": "sam", "name": "Sam", "taken": ["tracker@1.0.0"]}))
    rows = findings(doc, v)
    check("F63" in codes(rows) and "member file" in " ".join(r["text"] for r in rows),
          "a member file not yet on GitHub is F63")
    check("F65" in codes(rows), "a recipe taken at 1.0.0 with 1.1.0 on the shelf is F65")
    g = ["-c", "user.name=S", "-c", "user.email=s@x.invalid"]
    git("-C", str(hub), *g, "add", "members/sam.json", env=env)
    git("-C", str(hub), *g, "commit", "-q", "-m", "joined", env=env)
    rows = findings(doc, v)
    check(any(r["guide"] == "F63" and "1 save of yours" in r["text"] for r in rows),
          "a commit not pushed is counted as one save")
    git("-C", str(hub), "push", "-q", env=env)
    git("-C", str(hub), "fetch", "-q", env=env)
    check("F63" not in codes(findings(doc, v)), "pushed, F63 clears")

    post = hub / "post"
    post.mkdir(exist_ok=True)  # git keeps no empty folder; a real Hub's post office has notes in it
    def note(nid, kind, to, frm):
        (post / f"{nid}.md").write_text(f"---\ntype: Moblee hub note\nid: {nid}\nkind: {kind}\nfrom: {frm}\nto: {to}\n"
                                        "title: t\ndo_not_ingest: true\n---\n\nSecret words here never quoted.\n")
    note("20261024-1000-keeper-a", "question", "sam", "keeper")
    note("20261024-1001-keeper-b", "instructions", "all", "keeper")
    note("20261024-1002-keeper-c", "report", "sam", "keeper")
    note("20261024-1003-sam-d", "question", "all", "sam")
    note("20261024-1004-keeper-e", "question", "other", "keeper")
    rows = findings(doc, v)
    f64 = [r for r in rows if r["guide"] == "F64"]
    check(len(f64) == 1 and f64[0]["text"].startswith("1 note"),
          "F64 counts the note to this member, not the report, their own note or another's")
    check(any(r["level"] == "OK" and r["text"].startswith("1 note to everyone") for r in rows),
          "a note to everyone is counted on an OK line, and never makes the wiki unwell")
    check(not any("Secret words" in r["text"] for r in rows), "no note's text is ever quoted")
    (post / "20261024-1000-keeper-a--reply-sam-20261024-1100.md").write_text("---\ntype: Moblee hub reply\n---\n")
    check("F64" not in codes(findings(doc, v)), "a reply from this member stops a note being counted")
    note("20261024-1005-keeper-f", "question", "sam", "keeper")
    (post / "20261024-1005-keeper-f.md").write_text((post / "20261024-1005-keeper-f.md").read_text().replace(
        "id: 20261024-1005-keeper-f", "id: something-else"))
    (post / "20261024-1005-keeper-f--reply-sam-20261024-1200.md").write_text("---\ntype: Moblee hub reply\n---\n")
    check("F64" not in codes(findings(doc, v)), "a reply named after the note's file answers it even when the id differs")

    manifest = json.loads((hub / "hub.json").read_text())
    manifest["door_token_expires"] = "2027-10-24"
    (hub / "hub.json").write_text(json.dumps(manifest))
    near = datetime.date(2027, 10, 1)
    check("F66" not in codes(findings(doc, v, today=near)), "a member who is not the keeper never sees F66")
    (hub / "app" / "state" / "me.json").write_text(json.dumps({"id": "keeper"}))
    check("F66" not in codes(findings(doc, v, today=datetime.date(2027, 9, 1))),
          "the keeper, 53 days out: no warning yet")
    rows = findings(doc, v, today=near)
    check(any(r["guide"] == "F66" and "in 23 days" in r["text"] for r in rows),
          "the keeper, 23 days out: F66 with the days left")
    rows = findings(doc, v, today=datetime.date(2027, 10, 25))
    check(any(r["guide"] == "F66" and "ran out" in r["text"] for r in rows), "the keeper, the day after: F66, ran out")
    del manifest["door_token_expires"]
    (hub / "hub.json").write_text(json.dumps(manifest))
    rows = findings(doc, v, today=near)
    check("F66" not in codes(rows) and any("door_token_expires" in r["text"] for r in rows if r["level"] == "OK"),
          "the keeper with no date in hub.json: an OK line saying how to get the warning")
    check(any(r.get("tag") == "hub-version" and "version 1.0.0" in r["text"] for r in rows),
          "the Hub's page version is on an OK line")
    card = doc.build_card(rows, None, today=near)
    check("version 1.0.0" in card.get("hub", "") and any("version 1.0.0" in l for l in card["lines"]),
          "the health card carries the Hub line, in its dict and in its printed lines")
    check("keeper" not in card.get("hub", "") and "Test Hub" not in card.get("hub", ""),
          "the card's Hub line carries no member id and no Hub name, as no card line does")
    plain = doc.build_card(findings(doc, make_wiki(tmp / "dn")), None, today=near)
    check(plain.get("hub") == "" and not any("Hub" in l for l in plain["lines"]),
          "a wiki outside any Hub gets no Hub line on its card")


# --------------------------------------------------------------------------
# 3. the Hub item, end to end
# --------------------------------------------------------------------------

FAKE_GH = r'''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
state = Path(os.environ["FAKEGH_STATE"]); state.mkdir(exist_ok=True)
log = state / "calls.txt"
with log.open("a") as fh: fh.write(" ".join(sys.argv[1:]) + "\n")
a = sys.argv[1:]
issues = state / "issues.json"
def load(): return json.loads(issues.read_text()) if issues.exists() else []
if a[:2] in (["auth", "status"], ["auth", "setup-git"]): sys.exit(0)
if a[:2] == ["api", "user"]: print("newmember"); sys.exit(0)
if a[:2] == ["api", "/user/repository_invitations"]:
    if (state / "approved").exists() and not (state / "accepted").exists():
        print(json.dumps([{"id": 7, "repository": {"full_name": "test-keeper/test-hub"}}]))
    else: print("[]")
    sys.exit(0)
if a[:3] == ["api", "-X", "PATCH"] and a[3] == "/user/repository_invitations/7":
    (state / "accepted").write_text("yes")
    cfg = Path(os.environ["GIT_CONFIG_GLOBAL"])
    cfg.write_text('[url "' + os.environ["FAKEGH_BARE"] + '"]\n\tinsteadOf = ' + os.environ["MOBLEE_HUB_ADDRESS"] + "\n")
    sys.exit(0)
if a[:2] == ["issue", "list"]: print(json.dumps(load())); sys.exit(0)
if a[:2] == ["issue", "create"]:
    title = a[a.index("--title") + 1]
    items = load(); items.append({"title": title}); issues.write_text(json.dumps(items))
    if os.environ.get("FAKEGH_APPROVE") == "1": (state / "approved").write_text("yes")
    sys.exit(0)
sys.exit(1)
'''

DRIVER = r'''
import importlib.util, json, sys
spec = importlib.util.spec_from_file_location("ms", sys.argv[1])
ms = importlib.util.module_from_spec(spec); spec.loader.exec_module(ms)
answers = json.loads(sys.argv[2])
def ask(prompt):
    return answers.pop(0) if answers else None
ms.ask = ask
ms.wait_for_return = lambda *a, **k: True
ok = ms.install_hub()
print("RESULT", json.dumps({"installed": ok, "check": ms.check_hub()}))
'''


def item_world(tmp: Path, tag: str, approve: bool = True, join: str = "approve"):
    root = tmp / tag
    home = root / "home"
    (home / ".config" / "moblee").mkdir(parents=True)
    env = quiet_env(home)
    bare = make_bare_hub(root, env)
    v = make_wiki(root)
    (home / ".config" / "moblee" / "vault-path").write_text(str(v))
    (home / ".gitconfig").write_text('[url "' + str(root / "nowhere.git") + '"]\n\tinsteadOf = ' + ADDRESS + "\n")
    gh = root / "gh"
    gh.write_text(FAKE_GH)
    gh.chmod(0o755)
    env.update({"MOBLEE_GH": str(gh), "MOBLEE_VAULT": str(v), "MOBLEE_HUB_ADDRESS": ADDRESS,
                "MOBLEE_HUB_LOBBY": LOBBY, "MOBLEE_HUB_JOIN": join, "MOBLEE_HUB_POLL": "1",
                "MOBLEE_HUB_WAIT": "4", "FAKEGH_STATE": str(root / "ghstate"), "FAKEGH_BARE": str(bare),
                "FAKEGH_APPROVE": "1" if approve else "0"})
    driver = root / "driver.py"
    driver.write_text(DRIVER)
    return root, v, bare, env, driver


def link_as_github(root: Path, v: Path, bare: Path, env: dict) -> None:
    """A clone made as the item would make it: the address is GitHub's, and the
    stand-in answers for it."""
    (root / "home" / ".gitconfig").write_text('[url "' + str(bare) + '"]\n\tinsteadOf = ' + ADDRESS + "\n")
    git("clone", "-q", ADDRESS, str(v / "hub"), env=env)


def run_item(env: dict, driver: Path, answers: list) -> tuple[dict, str]:
    r = subprocess.run([PY, str(driver), str(SETUP), json.dumps(answers)], env=env,
                       capture_output=True, text=True, timeout=180)
    for line in r.stdout.splitlines():
        if line.startswith("RESULT "):
            return json.loads(line[7:]), r.stdout + r.stderr
    return {}, r.stdout + r.stderr


def test_item(tmp: Path) -> None:
    print("\n3. The Hub item, end to end, against a stand-in Hub")
    root, v, bare, env, driver = item_world(tmp, "i1")
    res, out = run_item(env, driver, ["", "", "Jones, Ali"])
    calls = (root / "ghstate" / "calls.txt").read_text() if (root / "ghstate" / "calls.txt").exists() else ""
    check(res.get("installed") is True, "approve door: the item finishes" + ("" if res.get("installed") else "\n" + out[-1500:]))
    check("issue create -R test-keeper/test-hub-lobby --title join: newmember --body" in calls,
          "it knocks once at the public lobby with the GitHub name and nothing else")
    check("Sam" not in calls and "Test" not in calls.replace("test-keeper", "").replace("test-hub", ""),
          "the owner's name never reaches the public lobby")
    check("api -X PATCH /user/repository_invitations/7" in calls, "it accepts the invitation itself")
    check((v / "hub" / ".git").exists() and (v / "hub" / "hub.json").exists(), "the Hub is cloned into hub/")
    member = v / "hub" / "members" / "sam.json"
    check(member.exists() and json.loads(member.read_text())["name"] == "Sam",
          "the member file takes the first word of the owner's name by default, and the id from it")
    check(json.loads((v / "hub" / "app" / "state" / "me.json").read_text()) == {"id": "sam"}, "me.json says who this Mac is")
    words = (v / "hub" / "tools" / "private-words.txt").read_text().split("\n")
    check("Jones" in words and "Ali" in words and "Sam" in words,
          "the private words hold what the owner typed and their name")
    shown = git("--git-dir", str(bare), "show", "main:members/sam.json", env=env)
    check(shown.returncode == 0, "the member file reached the stand-in GitHub")
    files = git("--git-dir", str(bare), "ls-tree", "-r", "--name-only", "main", env=env).stdout
    check("private-words" not in files and "app/state" not in files, "nothing private was pushed")
    check("/hub" in (v / ".gitignore").read_text().splitlines(), "the wiki's git ignores hub, folder or link")
    app = json.loads((v / ".obsidian" / "app.json").read_text())
    check("hub/" in app.get("userIgnoreFilters", []), "Obsidian is told to ignore hub/, its settings file made where missing")
    check("## The Moblee Hub" in (v / "CLAUDE.md").read_text(), "the rules file gains the Hub section")
    check(res.get("check", [False])[0] is True and "as sam" in res["check"][1] and "version 1.0.0" in res["check"][1],
          "the item's check says joined, the id and the Hub's version")

    res2, out2 = run_item(env, driver, [])
    calls2 = (root / "ghstate" / "calls.txt").read_text()
    check(res2.get("installed") is True, "a second run finishes" + ("" if res2.get("installed") else "\n" + out2[-1500:]))
    check(calls2.count("issue create") == 1, "a second run does not knock again")
    check((v / ".gitignore").read_text().splitlines().count("/hub") == 1
          and (v / "CLAUDE.md").read_text().count("## The Moblee Hub") == 1,
          "a second run adds nothing twice")

    root, v, bare, env, driver = item_world(tmp, "i1b")
    link_as_github(root, v, bare, env)
    g = ["-c", "user.name=S", "-c", "user.email=s@x.invalid"]
    (v / "hub" / "post").mkdir(exist_ok=True)
    (v / "hub" / "post" / "draft.md").write_text("an unsent reply\n")
    git("-C", str(v / "hub"), *g, "add", "post/draft.md", env=env)
    git("-C", str(v / "hub"), *g, "commit", "-q", "-m", "a reply not yet approved", env=env)
    res, out = run_item(env, driver, ["", "", ""])
    sent = git("--git-dir", str(bare), "ls-tree", "-r", "--name-only", "main", env=env).stdout
    check(res.get("installed") is False and "post/draft.md" not in sent and "members/sam.json" not in sent,
          "with another save waiting, the item sends nothing, that save included" + ("" if res.get("installed") is False else "\n" + out[-800:]))
    check("waiting to be sent" in out, "and says why, in plain words")

    root, v, bare, env, driver = item_world(tmp, "i1c")
    link_as_github(root, v, bare, env)
    (v / "hub" / "members" / "sam.json").write_text(json.dumps({"id": "sam", "name": "Sam", "taken": []}))
    git("-C", str(v / "hub"), *g, "add", "members/sam.json", env=env)
    git("-C", str(v / "hub"), *g, "commit", "-q", "-m", "sam joined on the other Mac", env=env)
    git("-C", str(v / "hub"), "push", "-q", env=env)
    res, out = run_item(env, driver, ["", "y"])
    check(res.get("installed") is True and json.loads((v / "hub" / "app" / "state" / "me.json").read_text()) == {"id": "sam"}
          and len(list((v / "hub" / "members").glob("*.json"))) == 2,
          "joined before on another Mac: asked 'Is that you?', and no second member is made" + ("" if res.get("installed") else "\n" + out[-800:]))

    root, v, bare, env, driver = item_world(tmp, "i2", approve=False, join="invite")
    res, out = run_item(env, driver, ["", "", ""])
    calls = (root / "ghstate" / "calls.txt").read_text()
    check(res.get("installed") is False and "issue create" not in calls,
          "invite door: no knock, and the item stops when the keeper has not invited in time")
    check("newmember" in out and "choose this item again later" in out, "it tells the owner their GitHub name and what to do")
    check(not (v / "hub").exists(), "nothing is cloned before the invitation")

    root, v, bare, env, driver = item_world(tmp, "i3")
    (v / "hub").mkdir()
    (v / "hub" / "mine.md").write_text("owner's file\n")
    res, out = run_item(env, driver, [])
    check(res.get("installed") is False and (v / "hub" / "mine.md").read_text() == "owner's file\n",
          "a copied hub folder is left exactly as it is")
    check(res.get("check", [True])[0] is False and "copied" in res["check"][1], "and its check says so")


# --------------------------------------------------------------------------
# 4. sharing a built thing to the Hub (skills/build/parts/share.py --to-hub)
# --------------------------------------------------------------------------

SHARE = PKG / "skills" / "build" / "parts" / "share.py"


def real_checker() -> Path | None:
    """The Hub's own checker, which is the Hub's and not the pack's: read from a
    Hub clone on this Mac when there is one, so the test runs the real thing."""
    env = os.environ.get("MOBLEE_HUB_CHECKER")
    cands = [Path(env)] if env else []
    cands += sorted((Path.home() / "Wiki").glob("*/hub/tools/check_recipe.py"))
    return next((c for c in cands if c.is_file()), None)


def test_share(tmp: Path) -> None:
    print("\n4. Sharing a built thing to the Hub")
    home = tmp / "home4"
    home.mkdir()
    env = quiet_env(home)
    bare = make_bare_hub(tmp / "s", env)
    v = make_wiki(tmp / "s")
    app = v / "apps" / "counter"
    (app / "data").mkdir(parents=True)
    (app / "state").mkdir()
    (app / "screenshots").mkdir()
    (app / "app.json").write_text(json.dumps({"title": "Counter", "what": "Counts the things you do each day."}))
    (app / "main.py").write_text("print('counter')\n")
    (app / "data" / "mine.csv").write_text("day,count\n2026-10-24,3\n")
    (app / "state" / "last.json").write_text("{}")
    (app / "screenshots" / "home.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\0" * 32)
    (v / "wiki" / "Projects").mkdir()
    (v / "wiki" / "Projects" / "Counter.md").write_text("# Counter\n\nCounts things.\n")
    (v / "wiki" / "log.md").write_text("# Log\n\n## [2026-10-20 10:00 +01] tooling | Counter built\n\nBuilt apps/counter/.\n\n"
                                       "## [2026-10-21 10:00 +01] ingest | Something else\n\nNothing.\n")

    def share(*extra):
        r = subprocess.run([PY, str(SHARE), "--vault", str(v), "--name", "counter", "--to-hub", *extra],
                           env=env, capture_output=True, text=True, timeout=120)
        return r.returncode, r.stdout + r.stderr

    code, out = share()
    check(code == 2 and "not in a Hub" in out, "a wiki outside any Hub is told so, and nothing is written")
    git("clone", "-q", str(bare), str(v / "hub"), env=env)
    hub = v / "hub"
    checker = real_checker()
    if checker:
        (hub / "tools").mkdir(exist_ok=True)
        shutil.copy2(checker, hub / "tools" / "check_recipe.py")
    code, out = share()
    check(code == 2 and "not joined" in out, "linked but not joined: refused")
    (hub / "app" / "state").mkdir(parents=True, exist_ok=True)
    (hub / "app" / "state" / "me.json").write_text(json.dumps({"id": "sam"}))
    (hub / "members" / "sam.json").write_text(json.dumps({"id": "sam", "name": "Sam", "taken": []}))
    head_before = git("-C", str(hub), "rev-parse", "HEAD", env=env).stdout.strip()

    code, out = share()
    d = hub / "recipes" / "counter"
    check(code == 0 and d.is_dir(), "joined: the recipe folder is written" + ("" if code == 0 else "\n" + out[-800:]))
    meta = json.loads((d / "recipe.json").read_text()) if (d / "recipe.json").exists() else {}
    check(meta.get("by") == "sam" and meta.get("version") == "1.0.0" and meta.get("kind") == "project"
          and meta.get("summary") == "Counts the things you do each day.",
          "recipe.json: this member as maker, 1.0.0, the summary from app.json")
    check(meta.get("needs") == "" and meta.get("time") == "",
          "needs and time are left empty, never guessed")
    check((d / "kit" / "apps" / "counter" / "main.py").read_bytes() == (app / "main.py").read_bytes(),
          "the working code is shipped byte for byte")
    check(not (d / "kit" / "apps" / "counter" / "data").exists() and not (d / "kit" / "apps" / "counter" / "state").exists(),
          "the owner's data and state are left on the Mac")
    check((d / "kit" / "page" / "Counter.md").exists() and (d / "kit" / "screenshots" / "home.png").exists(),
          "the page and the screenshots go in kit/")
    inst = (d / "INSTALL.md").read_text()
    sections = ["For the owner", "Before you start", "Steps", "Make it theirs", "What done looks like",
                "Prove it works", "When it breaks", "How to undo", "Record it"]
    check(all(f"## {s}\n" in inst for s in sections) and "record_take.py counter" in inst,
          "INSTALL.md has every section the rule book names, and the record step")
    check(inst.count("**Check:**") >= 2 and "TO WRITE" in inst, "its steps carry checks, and the gaps are marked TO WRITE")
    check("result: not yet" in (d / "TESTED.md").read_text(), "TESTED.md says not yet: the blank-wiki test is still to run")
    check("Counter built" in out and "Something else" not in out, "the log entries that name it are listed, and no others")
    check(not any("log.md" in str(p) for p in d.rglob("*")) and "Something else" not in "".join(
        p.read_text(errors="ignore") for p in d.rglob("*.md")), "nothing of the log is written into the Hub")
    head_after = git("-C", str(hub), "rev-parse", "HEAD", env=env).stdout.strip()
    check(head_before == head_after and "Nothing was committed" in out, "nothing is committed or sent")
    check("python3 hub/tools/check_recipe.py counter" in out and "FAIL" not in out,
          "the Hub's checker is named for the assistant to run after reading it, never run by the tool")
    if checker:
        r = subprocess.run([PY, str(hub / "tools" / "check_recipe.py"), "counter"], env=env,
                           capture_output=True, text=True, timeout=60)
        check(r.returncode == 1 and "has no 'needs'" in r.stdout and "result: pass" in r.stdout,
              "run by hand, the Hub's own checker lists exactly what is still to do")
    else:
        print("  note  no Hub checker on this Mac; its part was not tested")
    check("## Record it\n\nKeep this section as it is, with `<id>` filled in." not in inst
          and "record_take.py counter" in inst, "the record section is the template's, with the id put in")

    before = (d / "INSTALL.md").read_text()
    code, out = share()
    check(code == 2 and "already yours" in out and (d / "INSTALL.md").read_text() == before,
          "a second run writes nothing over the recipe")
    (hub / "recipes" / "theirs").mkdir(parents=True)
    (hub / "recipes" / "theirs" / "recipe.json").write_text(json.dumps({"id": "theirs", "by": "keeper"}))
    code, out = share("--id", "theirs")
    check(code == 2 and "made by keeper" in out, "another member's recipe id is refused")
    (hub / "recipes" / "half").mkdir()
    (hub / "recipes" / "half" / "kit").mkdir()
    code, out = share("--id", "half")
    check(code == 2 and "unfinished folder" in out, "a folder left half-made by an earlier run is named as one")
    (v / "wiki" / "Private").mkdir()
    (v / "wiki" / "Private" / "Secret.md").write_text("# Secret\n")
    (app / "app.json").write_text(json.dumps({"title": "Counter", "what": "w", "page": "wiki/Private/Secret.md"}))
    code, out = share("--id", "counter-private")
    check(code == 2 and "wiki/Private" in out and not (hub / "recipes" / "counter-private").exists(),
          "a page in wiki/Private/ is never shared")
    (app / "app.json").write_text(json.dumps({"title": "Counter", "what": "Counts the things you do each day."}))
    (app / "main.py").write_text("key = 'AKIA" + "ABCDEFGHIJKLMNOP'\n")
    code, out = share("--id", "counter-two")
    check(code == 2 and not (hub / "recipes" / "counter-two").exists(),
          "a thing carrying a key is not shared, and no recipe folder is made")


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="moblee-hub-test."))
    print(f"Moblee Hub client tests (throwaway folders under {tmp})")
    test_rules_block(tmp)
    test_doctor(tmp)
    test_item(tmp)
    test_share(tmp)
    print(f"\n{PASSED} passed, {len(FAILED)} failed")
    for what in FAILED:
        print("  FAIL  " + what.splitlines()[0])
    return 0 if not FAILED else 1


if __name__ == "__main__":
    sys.exit(main())
