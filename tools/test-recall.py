#!/usr/bin/env python3
"""Tests for extras/recall/: memory search against throwaway wikis, with a
stand-in for the model (MOBLEE_EMBED_STUB=1: words hashed into a small vector)
so no Ollama is needed. Run from the Moblee folder: python3 tools/test-recall.py

Covers: what is indexed and what never is (Private, Ghost Reconstructions, a
`restricted:` page); a question finding its section; the incremental rebuild;
the lock; the hook's skips (outside the wiki, short, a command, a system
message, no index, a weak match) and its firing; the installer (copies, the
hook registered once with a kept copy of the settings, the launch agent, the
dry run, a settings file that is not JSON); the rebuild script; and the
post-commit hook running only for a commit that touched the wiki."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent
PY = sys.executable
RECALL = PKG / "extras" / "recall" / "recall.py"
INJECT = PKG / "extras" / "recall" / "recall-inject.py"
INSTALL = PKG / "extras" / "recall" / "install-recall.py"
REBUILD = PKG / "extras" / "recall" / "rebuild-index.sh"
POST_COMMIT = PKG / "scripts" / "hooks" / "post-commit"
PASSED = 0
FAILED: list[str] = []


def check(cond: bool, what: str, note: str = "") -> None:
    global PASSED
    if cond:
        PASSED += 1
        print(f"  ok    {what}")
    else:
        FAILED.append(what)
        print(f"  FAIL  {what}" + (f"  [{note[:200]}]" if note else ""))


def run(cmd, env, cwd=None, stdin=None, timeout=120):
    r = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=cwd, input=stdin, timeout=timeout)
    return r.returncode, r.stdout, r.stderr


def make_vault(root: Path) -> Path:
    v = root / "wiki-vault"
    (v / "wiki" / "Private").mkdir(parents=True)
    (v / "wiki" / "Ghost Reconstructions").mkdir(parents=True)
    (v / "memory").mkdir(parents=True)
    (v / "wiki" / "Golf.md").write_text(
        "# Golf\n\nThe owner's golf, kept here.\n\n## Putting\n\nPutting practice on the green each week, "
        "with the gate drill and ten balls from six feet.\n\n## Driving\n\nThe driver carry is about 230 yards "
        "with a slight fade off the tee.\n", encoding="utf-8")
    (v / "wiki" / "Health.md").write_text(
        "# Health\n\n## Shoulder\n\nThe shoulder aches after swimming; stretch before each session.\n\n"
        "### Exercises\n\nWall sits, step-downs and straight-leg raises, each morning.\n", encoding="utf-8")
    (v / "wiki" / "Private" / "Diary.md").write_text("# Diary\n\n## Secret\n\nA candid private entry about a friend.\n")
    (v / "wiki" / "Ghost Reconstructions" / "2026-01-01 Voice.md").write_text(
        "---\nrestricted: ghost-only\n---\n# Voice\n\n## Reconstruction\n\nA reconstructed voice about putting.\n")
    (v / "wiki" / "Marked.md").write_text("---\ntitle: Marked\nrestricted: yes\n---\n# Marked\n\n## Body\n\nA restricted page about driving.\n")
    (v / "memory" / "note.md").write_text("# A memory\n\n## Preference\n\nThe owner prefers short answers in the morning.\n")
    (v / "wiki" / "Long.md").write_text("# Long\n\n## Big section\n\n" + " ".join(f"word{i}" for i in range(2500)) + "\n")
    # the adversary's cases: a link into Private, a link to a private file, a
    # private folder in another case, a restricted page behind a byte-order
    # mark, a memory that links to a private page, and a private page that
    # shares a question's words
    os.symlink(v / "wiki" / "Private", v / "wiki" / "Notes")
    os.symlink(v / "wiki" / "Private" / "Diary.md", v / "wiki" / "Linked.md")
    (v / "wiki" / "private").mkdir(exist_ok=True)   # on a disk that folds case this is the same folder, which is fine
    (v / "wiki" / "private" / "Lower.md").write_text("# Lower\n\n## Secret\n\nA private page about the gate drill on the green.\n")
    (v / "wiki" / "Bom.md").write_text("﻿---\nrestricted: ghost-only\n---\n# Bom\n\n## Body\n\nA restricted page behind a byte-order mark about the gate drill.\n", encoding="utf-8")
    (v / "memory" / "quotes-private.md").write_text("# A memory\n\n## Note\n\nThe owner said, as recorded on [[Diary]], that the gate drill is private.\n")
    (v / "wiki" / "Private" / "Diary.md").write_text("# Diary\n\n## Secret\n\nA candid private entry about putting practice on the green with the gate drill.\n")
    return v


def main() -> int:
    root = Path(tempfile.mkdtemp(prefix="moblee-recall-test-"))
    home = root / "home"
    (home / ".claude").mkdir(parents=True)
    cache = root / "cache"
    vault = make_vault(root)
    env = dict(os.environ, HOME=str(home), MOBLEE_EMBED_STUB="1", MOBLEE_RECALL_CACHE=str(cache),
               MOBLEE_VAULT=str(vault))
    env.pop("MOBLEE_OLLAMA", None)

    print("recall.py")
    code, out, err = run([PY, str(RECALL), "status"], env)
    check(code == 0 and "no index yet" in out, "status with no index says so", out + err)
    code, out, err = run([PY, str(RECALL), "--json", "putting practice"], env)
    check(code != 0 and "no index yet" in (out + err), "a question with no index exits with the rebuild line", out + err)
    code, out, err = run([PY, str(RECALL), "rebuild"], env)
    check(code == 0 and "index built" in out, "the first rebuild builds the index", out + err)
    meta = json.loads((cache / "meta.json").read_text())
    pages = sorted({c["page"] for c in meta["chunks"]})
    check("Golf" in pages and "Health" in pages and "note" in pages, "wiki pages and memories are indexed", str(pages))
    check("Diary" not in pages, "a page under Private is never indexed", str(pages))
    check("2026-01-01 Voice" not in pages, "a page under Ghost Reconstructions is never indexed", str(pages))
    check("Marked" not in pages, "a page with restricted: in its front matter is never indexed", str(pages))
    check(not any("/Private/" in c["path"] for c in meta["chunks"]), "no indexed path is under Private")
    check("Notes" not in pages and not any("/Notes/" in c["path"] for c in meta["chunks"]), "a link into Private is not followed", str(pages))
    check("Linked" not in pages, "a link to a private file is not followed", str(pages))
    check("Lower" not in pages, "a private folder in another case is excluded", str(pages))
    check("Bom" not in pages, "a restricted page behind a byte-order mark is excluded", str(pages))
    check("quotes-private" not in pages, "a memory that links to a private page is left out", str(pages))
    check(all(c["page"] != "Diary" for c in meta["chunks"]), "the private page sharing the question's words is not there either")
    check((cache / "vectors.f32").stat().st_size == 4 * meta["dims"] * meta["count"], "the vectors file matches the count")
    long_parts = [c for c in meta["chunks"] if c["page"] == "Long"]
    check(len(long_parts) >= 3, "a section over a thousand words is split into parts", str(len(long_parts)))
    headings = {(c["page"], c["heading"]) for c in meta["chunks"]}
    check(("Health", "Shoulder > Exercises") in headings, "an H3 carries its H2 in the heading path", str(sorted(headings))[:200])
    check(("Golf", "(intro)") in headings, "text before the first heading is the intro section")

    code, out, err = run([PY, str(RECALL), "--json", "putting practice on the green with the gate drill"], env)
    hits = json.loads(out) if code == 0 else []
    check(code == 0 and hits and hits[0]["page"] == "Golf" and "Putting" in hits[0]["heading"],
          "a question finds the section closest to it", out[:200] + err[:200])
    check(hits and hits[0]["score"] >= 0.60, "and the closest scores above the hook's threshold", str(hits[:1]))
    code, out, err = run([PY, str(RECALL), "wall sits and step downs"], env)
    check(code == 0 and "[[Health]] > Shoulder > Exercises" in out, "the readable form names page and heading path", out[:200])

    code, out, err = run([PY, str(RECALL), "rebuild"], env)
    check("0 new or changed" in out, "a second rebuild with nothing changed embeds nothing", out)
    (vault / "wiki" / "Golf.md").write_text((vault / "wiki" / "Golf.md").read_text().replace("230 yards", "240 yards"))
    code, out, err = run([PY, str(RECALL), "rebuild"], env)
    check("1 new or changed" in out, "a changed section is the only one embedded again", out)
    code, out, err = run([PY, str(RECALL), "rebuild", "--full"], env)
    n = json.loads((cache / "meta.json").read_text())["count"]
    check(f"({n} embedded)" in out, "--full embeds everything", out)
    import fcntl
    held = open(cache / "rebuild.lock", "a+")
    fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
    code, out, err = run([PY, str(RECALL), "rebuild"], env)
    check(code == 0 and "another rebuild is running" in out, "a rebuild stands down while another holds the lock", out)
    held.close()
    code, out, err = run([PY, str(RECALL), "rebuild"], env)
    check(code == 0 and "index built" in out, "and goes ahead once the lock is let go", out)
    check(not list(cache.glob("*.tmp")), "no half-written index file is left behind")
    env_b = dict(env)
    env_b.pop("MOBLEE_RECALL_CACHE")
    code, out, err = run([PY, str(RECALL), "status"], env_b)
    check("moblee-recall/" in out and len(out.rstrip("/").split("moblee-recall/")[-1].strip()) == 12,
          "without the override, the cache is a folder of its own per wiki", out)
    other = root / "other-vault"
    (other / "wiki").mkdir(parents=True)
    code, out2, err = run([PY, str(RECALL), "status"], dict(env_b, MOBLEE_VAULT=str(other)))
    check(out2 != out, "and a second wiki gets a different folder", out2)
    code, out, err = run([PY, str(RECALL), "status"], env)
    check("sections, built" in out, "status reports the count and age", out)
    empty = root / "empty-vault"
    (empty / "wiki").mkdir(parents=True)
    env_empty = dict(env, MOBLEE_VAULT=str(empty), MOBLEE_RECALL_CACHE=str(root / "empty-cache"))
    code, out, err = run([PY, str(RECALL), "rebuild"], env_empty)
    check(code == 0 and "nothing to index" in out and not (root / "empty-cache" / "meta.json").exists(),
          "an empty wiki builds no index and says so", out + err)
    env_nov = dict(env, MOBLEE_VAULT=str(root / "nowhere"))
    env_nov["HOME"] = str(root / "home-without-config")
    code, out, err = run([PY, str(RECALL), "rebuild"], env_nov)
    check(code != 0 and "could not be found" in (out + err), "no wiki anywhere is a plain refusal", out + err)

    print("recall-inject.py")
    log = cache / "inject.log"

    def hook(prompt, cwd=None, e=None):
        payload = json.dumps({"prompt": prompt, "cwd": cwd or str(vault)})
        return run([PY, str(INJECT)], e or env, stdin=payload)

    def last_log():
        try:
            return log.read_text().strip().splitlines()[-1]
        except (OSError, IndexError):
            return ""

    code, out, err = hook("putting practice on the green with the gate drill?", cwd=str(root))
    check(code == 0 and out == "" and not log.exists(), "outside the wiki nothing is attached and nothing logged", out + err)
    code, out, err = hook("the drill?")
    check(code == 0 and out == "" and "skip (short)" in last_log(), "a short message is skipped", last_log())
    code, out, err = hook("orient me on the putting practice please")
    check(out == "" and "skip (command)" in last_log(), "a command is skipped", last_log())
    code, out, err = hook("<task-notification> putting practice on the green with the gate drill </task-notification>")
    check(out == "" and "skip (system)" in last_log(), "a system message is skipped", last_log())
    code, out, err = hook("Please tidy the files on the desk today.")
    check(out == "" and "skip (not-a-question)" in last_log(), "a statement is skipped", last_log())
    code, out, err = hook("what about the zebra and the quartz lantern festival?")
    check(out == "" and "skip (best" in last_log(), "a weak match attaches nothing", last_log())
    code, out, err = hook("putting practice on the green with the gate drill?")
    check(code == 0 and out.startswith("[recall]") and "[[Golf]], under Putting" in out and "leads, not answers" in out,
          "a question with a close section attaches it, as a lead", out[:200] + err[:200])
    check("fired (?, " in last_log(), "and the firing is logged", last_log())
    code, out, err = hook("Tell me about putting practice on the green with the gate drill")
    check(out.startswith("[recall]") and "fired (question-word" in last_log(), "a question-word start fires without a question mark", last_log())
    check("Diary" not in out and "Private" not in out and "Lower" not in out and "Bom" not in out and "Notes" not in out,
          "nothing private is attached, though the private pages share the question's words", out)
    # the index may be hours old: a page restricted or gone since is checked as it is now
    golf = vault / "wiki" / "Golf.md"
    golf_text = golf.read_text()
    golf.write_text("---\nrestricted: yes\n---\n" + golf_text)
    code, out, err = hook("putting practice on the green with the gate drill?")
    check(out == "" and "nothing allowed" in last_log(), "a page marked restricted since the index was built is not attached", out + last_log())
    golf.write_text(golf_text)
    moved = vault / "wiki" / "Golf-moved.md"
    os.rename(golf, moved)
    code, out, err = hook("putting practice on the green with the gate drill?")
    check("[[Golf]]" not in out, "a page gone since the index was built is not attached", out)
    os.rename(moved, golf)
    code, out, err = run([PY, str(INJECT)], env, stdin="not json")
    check(code == 0 and out == "", "bad input exits quietly", out + err)
    env_noidx = dict(env, MOBLEE_RECALL_CACHE=str(root / "no-index-cache"))
    code, out, err = hook("putting practice on the green with the gate drill?", e=env_noidx)
    check(code == 0 and out == "" and "skip (no index)" in (root / "no-index-cache" / "inject.log").read_text(),
          "no index means nothing attached and a log line", out + err)

    print("install-recall.py")
    settings = home / ".claude" / "settings.json"
    settings.write_text(json.dumps({"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "echo stop"}]}]},
                                    "permissions": {"allow": ["Bash(ls:*)"]}}, indent=2))
    code, out, err = run([PY, str(INSTALL), "--vault", str(vault), "--dry-run"], env)
    check(code == 0 and "would put" in out and "would tell it" in out and not (vault / "scripts" / "recall").exists()
          and "recall-inject" not in settings.read_text(), "a dry run changes nothing and says what it would do", out + err)
    code, out, err = run([PY, str(INSTALL), "--vault", str(vault), "--no-schedule"], env)
    dest = vault / "scripts" / "recall"
    check(code == 0 and all((dest / n).exists() for n in ("recall.py", "recall-inject.py", "rebuild-index.sh")),
          "the three scripts are put in the wiki", out + err)
    check(all(os.access(dest / n, os.X_OK) for n in ("recall.py", "rebuild-index.sh")), "and are executable")
    data = json.loads(settings.read_text())
    ups = data["hooks"]["UserPromptSubmit"]
    cmds = [h["command"] for g in ups for h in g["hooks"]]
    check(len(cmds) == 1 and "recall-inject.py" in cmds[0] and cmds[0].endswith("|| true"),
          "the hook is registered once, and cannot block a message if the file goes", str(cmds))
    check(data["hooks"]["Stop"][0]["hooks"][0]["command"] == "echo stop" and data["permissions"]["allow"] == ["Bash(ls:*)"],
          "the owner's other hooks and rules are untouched")
    kept = list((home / ".config" / "moblee" / "backups").glob("*/settings.json"))
    check(len(kept) == 1 and "Stop" in kept[0].read_text(), "the settings file before the change is kept", str(kept))
    plist = home / "Library" / "LaunchAgents" / "com.moblee.recall-rebuild.plist"
    check(plist.exists() and "rebuild-index.sh" in plist.read_text() and "<integer>4</integer>" in plist.read_text(),
          "the daily rebuild's launch agent is written for 04:40", str(plist))
    check("<string>launchd</string>" in plist.read_text(), "and passes the trigger name")
    code, out, err = run([PY, str(INSTALL), "--vault", str(vault), "--no-schedule"], env)
    data = json.loads(settings.read_text())
    cmds = [h["command"] for g in data["hooks"]["UserPromptSubmit"] for h in g["hooks"]]
    check(code == 0 and "already told" in out and "already in place" in out and len(cmds) == 1,
          "run twice, nothing is added twice", out + err)
    (dest / "recall.py").write_text("# an older copy\n")
    code, out, err = run([PY, str(INSTALL), "--vault", str(vault), "--no-schedule"], env)
    befores = list(dest.glob("recall.py.before-*"))
    check(code == 0 and (dest / "recall.py").read_bytes() == RECALL.read_bytes() and len(befores) == 1,
          "an older copy is replaced and kept beside under a dated name", out + err)
    settings.write_text("{not json")
    code, out, err = run([PY, str(INSTALL), "--vault", str(vault), "--no-schedule"], env)
    check(code == 1 and "could not be read" in out and settings.read_text() == "{not json",
          "a settings file that is not JSON stops the hook step and is left as it was", out + err)
    settings.write_text("[]")
    code, out, err = run([PY, str(INSTALL), "--vault", str(vault), "--no-schedule"], env)
    check(code == 1 and "not in the shape" in out, "a settings file of the wrong shape is refused", out + err)
    settings.write_text(json.dumps({"hooks": {"UserPromptSubmit": "not a list"}}))
    code, out, err = run([PY, str(INSTALL), "--vault", str(vault), "--no-schedule"], env)
    check(code == 1 and "shape" in out and settings.read_text() == json.dumps({"hooks": {"UserPromptSubmit": "not a list"}}),
          "a hook list of the wrong type is refused and left alone", out + err)
    old_place = json.dumps({"hooks": {"UserPromptSubmit": [{"hooks": [{"type": "command",
                            "command": "python3 /Users/someone/OldWiki/scripts/recall/recall-inject.py 2>/dev/null || true"}]}]}})
    settings.write_text(old_place)
    code, out, err = run([PY, str(INSTALL), "--vault", str(vault), "--no-schedule"], env)
    data = json.loads(settings.read_text())
    cmds = [h["command"] for g in data["hooks"]["UserPromptSubmit"] for h in g["hooks"]]
    check(code == 0 and "corrected" in out and len(cmds) == 1 and str(vault) in cmds[0] and "OldWiki" not in cmds[0],
          "a hook left pointing at an old place of the wiki is corrected, not kept beside", out + str(cmds))
    code, out, err = run([PY, str(INSTALL), "--vault", str(root / "not-a-wiki"), "--no-schedule"], env)
    check(code == 1 and "no wiki/ folder" in out, "a folder without wiki/ is refused", out + err)
    settings.write_text("{}")
    code, out, err = run([PY, str(INSTALL), "--vault", str(vault), "--no-schedule"], env)
    check(code == 0 and "recall-inject" in settings.read_text(), "an empty settings file gains the hook", out + err)

    print("rebuild-index.sh")
    cache2 = home / ".cache" / "moblee-recall"
    env_sh = dict(env)
    env_sh.pop("MOBLEE_RECALL_CACHE")   # the shell script and recall.py both derive the folder from the wiki
    env_sh.pop("MOBLEE_VAULT")          # and the wiki is found from the script's own place
    code, out, err = run(["bash", str(dest / "rebuild-index.sh"), "test-run"], env_sh, timeout=300)
    folders = list(cache2.glob("*/rebuild.log"))
    rlog = folders[0].read_text() if folders else ""
    meta2 = folders[0].with_name("meta.json") if folders else cache2 / "meta.json"
    check(code == 0 and "[test-run] ok in" in rlog and meta2.exists(),
          "the rebuild script builds the index from inside the wiki, in the wiki's own folder, and logs the trigger", rlog + out + err)
    found = json.loads(meta2.read_text())["vault"] if meta2.exists() else ""
    check(os.path.realpath(found) == os.path.realpath(vault), "and found the wiki from its own place", found)

    print("post-commit hook")
    repo = root / "repo"
    (repo / "wiki").mkdir(parents=True)
    (repo / "scripts" / "hooks").mkdir(parents=True)
    (repo / "scripts" / "recall").mkdir(parents=True)
    mark = root / "rebuild-mark.txt"
    (repo / "scripts" / "recall" / "rebuild-index.sh").write_text(f'#!/bin/bash\necho "$1" >> "{mark}"\n')
    os.chmod(repo / "scripts" / "recall" / "rebuild-index.sh", 0o755)
    hook_copy = repo / "scripts" / "hooks" / "post-commit"
    hook_copy.write_bytes(POST_COMMIT.read_bytes())
    os.chmod(hook_copy, 0o755)
    g = dict(env, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
    run(["git", "init", "-q"], g, cwd=repo)
    run(["git", "config", "core.hooksPath", "scripts/hooks"], g, cwd=repo)
    (repo / "wiki" / "First.md").write_text("# First\n")
    run(["git", "add", "-A"], g, cwd=repo)
    run(["git", "commit", "-qm", "the first commit, with a page"], g, cwd=repo)
    for _ in range(25):
        if mark.exists():
            break
        time.sleep(0.2)
    check(mark.exists(), "the very first commit, with a page in it, starts a rebuild")
    marks_before = mark.read_text().count("post-commit") if mark.exists() else 0
    (repo / "README.md").write_text("hello\n")
    run(["git", "add", "-A"], g, cwd=repo)
    run(["git", "commit", "-qm", "no wiki change"], g, cwd=repo)
    time.sleep(2)
    check((mark.read_text().count("post-commit") if mark.exists() else 0) == marks_before,
          "a later commit that touched no wiki page starts no rebuild")
    (repo / "wiki" / "El Niño and the café.md").write_text("# A page named with accents\n")
    run(["git", "add", "-A"], g, cwd=repo)
    code, out, err = run(["git", "commit", "-qm", "a wiki change under a non-ASCII name"], g, cwd=repo)
    for _ in range(25):
        if mark.exists() and mark.read_text().count("post-commit") > marks_before:
            break
        time.sleep(0.2)
    check(code == 0 and mark.exists() and mark.read_text().count("post-commit") > marks_before,
          "a commit that touched a page with a non-ASCII name starts the rebuild in the background, with its trigger", out + err)
    os.chmod(repo / "scripts" / "recall" / "rebuild-index.sh", 0o644)
    (repo / "wiki" / "Page.md").write_text("# Page\n\nmore\n")
    run(["git", "add", "-A"], g, cwd=repo)
    code, out, err = run(["git", "commit", "-qm", "another"], g, cwd=repo)
    check(code == 0, "the hook never fails a commit, even when the script is not runnable", out + err)

    print()
    if FAILED:
        print(f"test-recall: {PASSED} passed, {len(FAILED)} FAILED")
        for f in FAILED:
            print("  - " + f)
    else:
        print(f"test-recall: {PASSED} checks passed, 0 failed")
    print(f"scratch kept: {root}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
