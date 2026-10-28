#!/usr/bin/env python3
"""Test suite for scripts/catalogue-page.py (0.16.0).

The page "What Your Wiki Can Do" is generated from the Moblee folder's own
checklist, never written by hand. These cases build it from a stand-in
checklist with every kind of item in it, and once from the pack's real one:
the four groups, one line per item with its title, what it does and how long,
the generated header, the ChatGPT wording, that it writes that one page and
nothing else, that a page of that name Moblee did not write is left alone,
and that a run which would change only the date writes nothing.

The script is imported and its main() called, so the vault safety guard has
nothing to read this test for. It starts the checklist as a separate program,
as it does in use.

Usage:  python3 tools/test-catalogue-page.py
Prints a pass/fail table and exits non-zero on any failure. Nothing is
deleted: the practice folders are left in the temp area, paths printed.
"""
import contextlib
import datetime
import importlib.util
import io
import json
import os
import pathlib
import sys
import tempfile

PACK = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = PACK / "scripts" / "catalogue-page.py"
ROOT = pathlib.Path(tempfile.mkdtemp(prefix="catalogue-page-test-"))
PAGE = pathlib.Path("wiki") / "Wiki Operations" / "What Your Wiki Can Do.md"

rows, failures = [], 0


def check(group, label, ok, detail=""):
    global failures
    rows.append(("ok" if ok else "FAIL", group, label + ("" if ok or not detail else f" ({detail})")))
    if not ok:
        failures += 1


PARTS = {
    "assistant": "claude", "vault": True, "checked": None,
    "core": [
        {"key": "companion", "title": "The companion", "what": "Sets things up with you",
         "say": "review my setup", "state": "in"},
        {"key": "galaxy", "title": "The wiki galaxy", "what": "Every page a star.",
         "say": "galaxy", "state": "missing"},
    ],
    "extras": {"news-brief": "off", "videos": "unknown", "google": "unseen",
               "generation": "unknown", "voice": "off", "lessons": "on", "vault-fn": "unknown"},
}
ITEMS = [
    {"key": "news-brief", "group": "Read and make things", "title": "A daily news brief",
     "what": "News on what you follow", "minutes": 1, "cost": "free", "paid": False, "how": "silent"},
    {"key": "videos", "group": "Read and make things", "title": "Watch and summarise videos",
     "what": "Send a link and Claude watches it.", "minutes": 4, "cost": "free", "paid": False, "how": "terminal"},
    {"key": "google", "group": "Connect your life", "title": "Gmail, Google Calendar and Google Drive",
     "what": "Claude reads your Google mail.", "minutes": 3, "cost": "free", "paid": False, "how": "clicks"},
    {"key": "generation", "group": "Paid, or with a paid option", "title": "Create new images",
     "what": "Generate things.", "minutes": 5, "cost": "PAID: plans from about $6 a month", "paid": True, "how": "clicks"},
    {"key": "voice", "group": "Paid, or with a paid option", "title": "Claude reads its replies aloud",
     "what": "Spoken replies.", "minutes": 3, "cost": "free (paid voice optional)", "paid": False, "how": "silent"},
    {"key": "lessons", "group": "Looking after the wiki", "title": "The learning path",
     "what": "Thirty-two short lessons.", "minutes": 1, "cost": "free", "paid": False, "how": "silent"},
    {"key": "vault-fn", "group": "Looking after the wiki", "title": "The vault shortcut",
     "what": "Type vault.", "minutes": 1, "cost": "free", "paid": False, "how": "hidden"},
]

STUB = '''import json, sys, pathlib
here = pathlib.Path(__file__).resolve().parent.parent
if (here / "fail").exists():
    print("Moblee runs on a Mac only."); sys.exit(1)
if "--parts" in sys.argv:
    print((here / "parts.json").read_text())
elif "--list" in sys.argv and "--json" in sys.argv:
    print((here / "items.json").read_text())
else:
    sys.exit(2)
'''


def package(name, parts=PARTS, items=ITEMS):
    p = ROOT / name
    (p / "scripts").mkdir(parents=True)
    (p / "scripts" / "moblee-setup.py").write_text(STUB)
    (p / "parts.json").write_text(json.dumps(parts))
    (p / "items.json").write_text(json.dumps(items))
    return p


def wiki(name):
    v = ROOT / name
    (v / "wiki" / "Wiki Operations").mkdir(parents=True)
    (v / "wiki" / "Index.md").write_text("# Index\n")
    return v


def snapshot(v):
    return sorted(str(p.relative_to(v)) for p in v.rglob("*"))


def run(mod, argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = mod.main(argv)
    return code, out.getvalue()


def section(text, title):
    lines, grab = [], False
    for l in text.split("\n"):
        if l.startswith("## "):
            grab = l[3:] == title
            continue
        if grab and l.startswith("- "):
            lines.append(l)
    return lines


def main():
    os.environ["HOME"] = str(ROOT / "home")
    spec = importlib.util.spec_from_file_location("catalogue_page", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    today = datetime.date(2026, 11, 4)

    # ----- the page itself, from the two readings
    text = mod.build_page(PARTS, ITEMS, today, mail_pass_page=True)
    check("page", "it says it is generated, and how to refresh it",
          "generated_by: moblee catalogue-page" in text and "show me everything" in text
          and "do not edit it by hand" in text)
    check("page", "dated in full", "4 November 2026" in text)
    for _k, title in mod.GROUPS:
        check("groups", f"has the group '{title}'", f"## {title}" in text)
    already = section(text, "Already in your wiki")
    press = section(text, "Added by itself in one press")
    window = section(text, "Opens a Terminal window or needs a few clicks")
    paid = section(text, "Paid or with a paid option")
    check("groups", "a part of every wiki is under Already", any("The companion" in l for l in already))
    check("groups", "with what to say to use it", any('Say "review my setup"' in l for l in already))
    check("groups", "a part not in place says so, and what to say",
          any("The wiki galaxy" in l and "something is wrong" in l for l in already))
    check("groups", "an extra already on is under Already", any("The learning path" in l for l in already)
          and not any("The learning path" in l for l in press))
    check("groups", "the morning pass and the mail pass are listed",
          any("Orient, the morning pass" in l for l in already)
          and any("[[Mail Pass|The mail pass]]" in l and "Off until you say yes" in l for l in already))
    check("groups", "a silent extra is under one press", any("A daily news brief" in l for l in press))
    check("groups", "a Terminal extra says it opens a window",
          any("Watch and summarise videos" in l and "opens a Terminal window" in l for l in window))
    check("groups", "a clicks extra says a few clicks", any("Gmail" in l and "a few clicks" in l for l in window))
    check("groups", "an unseen connection says it may already be on",
          any("Gmail" in l and "may already be on" in l for l in window))
    check("groups", "a paid extra is under Paid, with its cost",
          any("Create new images" in l and "$6 a month" in l for l in paid))
    check("groups", "an item in the paid group with a free start is under Paid too",
          any("reads its replies aloud" in l for l in paid) and not any("aloud" in l for l in press))
    check("groups", "a hidden item is not listed", "vault shortcut" not in text)
    check("lines", "every extra's line has its title, what it does and how long",
          all(l.startswith("- **") and "**: " in l and "About " in l for l in press + window + paid),
          "; ".join(press + window + paid))
    check("lines", "one minute is said in the singular", any("About 1 minute." in l for l in press))
    nolink = mod.build_page(PARTS, ITEMS, today, mail_pass_page=False)
    check("lines", "no link to a Mail Pass page the wiki does not have", "[[Mail Pass" not in nolink)

    cg = mod.build_page(dict(PARTS, assistant="chatgpt"), ITEMS, today, True)
    check("chatgpt", "ChatGPT: the Claude-only sentence", "set up for Claude only for now" in cg)
    check("chatgpt", "ChatGPT: the extras' groups are left out",
          "## Added by itself" not in cg and "## Paid" not in cg and "## Already in your wiki" in cg)
    both = mod.build_page(dict(PARTS, assistant="both"), ITEMS, today, True)
    check("chatgpt", "both: the sentence, and every group", "Claude only for now" in both and "## Paid" in both)
    claude = mod.build_page(PARTS, ITEMS, today, True)
    check("chatgpt", "Claude alone: no such sentence", "Claude only" not in claude)

    # ----- writing it
    pkg = package("Pack")
    v = wiki("Wiki")
    before = snapshot(v)
    code, out = run(mod, ["--vault", str(v), "--package", str(pkg)])
    page = v / PAGE
    check("write", "a first run adds the page", code == 0 and page.is_file() and "added" in out, out)
    check("write", "and writes nothing else in the wiki",
          [p for p in snapshot(v) if p not in before] == ["wiki/Wiki Operations/What Your Wiki Can Do.md"],
          str([p for p in snapshot(v) if p not in before]))
    first = page.read_text()
    stamp = page.stat().st_mtime_ns
    code, out = run(mod, ["--vault", str(v), "--package", str(pkg)])
    check("write", "a second run changes nothing and says so",
          code == 0 and "already up to date" in out and page.stat().st_mtime_ns == stamp)
    page.write_text(first.replace("updated: ", "updated: 2001-01-01x").replace(
        "on " + mod.long_date(datetime.date.today()), "on 1 January 2001"))
    stamp = page.stat().st_mtime_ns
    code, out = run(mod, ["--vault", str(v), "--package", str(pkg)])
    check("write", "a run that would change only the date writes nothing",
          "already up to date" in out and page.stat().st_mtime_ns == stamp)
    (pkg / "parts.json").write_text(json.dumps(dict(PARTS, extras=dict(PARTS["extras"], videos="on"))))
    code, out = run(mod, ["--vault", str(v), "--package", str(pkg)])
    check("write", "a real change is written", "refreshed" in out
          and any("Watch and summarise videos" in l for l in section(page.read_text(), "Already in your wiki")))
    code, out = run(mod, ["--vault", str(v), "--package", str(pkg), "--print"])
    check("write", "--print shows the page and writes nothing", code == 0 and "# What Your Wiki Can Do" in out)

    template = PACK / "vault-template" / PAGE
    t = wiki("FromTemplate")
    (t / PAGE).write_text(template.read_text())
    code, out = run(mod, ["--vault", str(t), "--package", str(pkg)])
    check("write", "the template's stand-in page carries the mark and is filled in",
          "refreshed" in out and "## Already in your wiki" in (t / PAGE).read_text())

    yes = wiki("SaidYes")
    (yes / "wiki" / "Wiki Operations" / "Habits and Tools.md").write_text(
        "# Habits and Tools\n\n## Said no to\n\n## Installed, and why\n\n"
        "- `mail-pass`, 4 November 2026: keeps my unread mail to what needs me\n")
    check("write", "a yes recorded on the owner's page shows the mail pass as on",
          mod.mail_pass_on(yes) and "keeping people, money and things to act on. On."
          in mod.build_page(PARTS, ITEMS, today, True, mod.mail_pass_on(yes)))
    check("write", "with no yes it is off", not mod.mail_pass_on(v))

    own = wiki("OwnersPage")
    (own / PAGE).write_text("# What Your Wiki Can Do\n\nMy own notes.\n")
    code, out = run(mod, ["--vault", str(own), "--package", str(pkg)])
    check("safety", "a page of that name Moblee did not write is left exactly as it is",
          code == 0 and (own / PAGE).read_text() == "# What Your Wiki Can Do\n\nMy own notes.\n"
          and "left exactly as it is" in out)
    failing = package("FailingPack")
    (failing / "fail").write_text("")
    f = wiki("FailWiki")
    code, out = run(mod, ["--vault", str(f), "--package", str(failing)])
    check("safety", "a checklist that cannot be read: page left as it is, exit 1, said plainly",
          code == 1 and not (f / PAGE).exists() and "left as it is" in out, out)
    code, out = run(mod, ["--vault", str(wiki("NoPack")), "--package", str(ROOT / "nowhere")])
    check("safety", "no Moblee folder: said plainly, exit 1", code == 1 and "Moblee folder" in out)

    # ----- the pack's real checklist
    if sys.platform == "darwin":
        r = wiki("RealPack")
        code, out = run(mod, ["--vault", str(r), "--package", str(PACK)])
        text = (r / PAGE).read_text() if (r / PAGE).exists() else ""
        check("real", "built from this pack's own moblee-setup.py", code == 0 and "## Already in your wiki" in text, out)
        check("real", "lists the real extras", "Watch and summarise videos" in text and "The Moblee Hub" in text)
        check("real", "every group has at least one line, or says it is empty",
              all(section(text, title) or "*Nothing here right now.*" in text for _k, title in mod.GROUPS))
    else:
        check("real", "the real checklist runs on a Mac only (not run here)", True)

    width = max(len(r[2]) for r in rows)
    print("%-4s %-8s %s" % ("", "group", "case"))
    for status, group, label in rows:
        print("%-4s %-8s %-*s" % (status, group, width, label))
    print()
    print("cases: %d   failures: %d" % (len(rows), failures))
    print("practice folders left in place: %s" % ROOT)
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
