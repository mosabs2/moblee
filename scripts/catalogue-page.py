#!/usr/bin/env python3
"""catalogue-page.py — write the page that lists what this wiki can do.

The page is `wiki/Wiki Operations/What Your Wiki Can Do.md`. It is generated,
never written by hand: everything on it comes from the Moblee folder's own
checklist, read through

    python3 <moblee folder>/scripts/moblee-setup.py --parts    (what comes with the wiki)
    python3 <moblee folder>/scripts/moblee-setup.py --list --json   (every extra)

and grouped four ways: already in your wiki; added by itself in one press;
opens a Terminal window or needs a few clicks; paid or with a paid option.
Each item is one line: its title, what it does, and how long it takes.

It is the first-week tour's source of truth, so the assistant offers nothing
that is already here. It is refreshed by the updater and whenever the owner
says "show me everything". (The Saturday check does not refresh it: that job
promises never to write into wiki/, and keeps the promise.)

It writes that one page and nothing else, and only through the ordinary file
path. A page of that name that does not carry the generated mark is the
owner's, and is left exactly as it is. A run that would change nothing but
the date writes nothing.

    python3 scripts/catalogue-page.py                       # the usual places
    python3 scripts/catalogue-page.py --vault <wiki> --package <moblee folder>
    python3 scripts/catalogue-page.py --print               # show it, write nothing

The Moblee folder is --package, else ~/.config/moblee/package-path, else the
folder this script sits in when it is run from the Moblee folder itself.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

PAGE_REL = Path("wiki") / "Wiki Operations" / "What Your Wiki Can Do.md"
MARK = "generated_by: moblee catalogue-page"
PAID_GROUP = "Paid, or with a paid option"
CLAUDE_ONLY = ("Moblee's extras are set up for Claude only for now. In ChatGPT the wiki "
               "itself, its skills, orient and the dashboard all work.")

GROUPS = (
    ("in", "Already in your wiki"),
    ("silent", "Added by itself in one press"),
    ("window", "Opens a Terminal window or needs a few clicks"),
    ("paid", "Paid or with a paid option"),
)

MONTHS = ("January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December")


def long_date(d: datetime.date) -> str:
    return f"{d.day} {MONTHS[d.month - 1]} {d.year}"


def find_vault(explicit: str | None) -> Path | None:
    if explicit:
        return Path(explicit).expanduser().resolve()
    env = os.environ.get("MOBLEE_VAULT", "").strip()
    if env:
        return Path(env).expanduser().resolve()
    here = Path(__file__).resolve().parent.parent
    if (here / "wiki" / "Index.md").is_file():
        return here
    cfg = Path.home() / ".config" / "moblee" / "vault-path"
    try:
        p = cfg.read_text().strip()
    except OSError:
        p = ""
    if p and (Path(p).expanduser() / "wiki" / "Index.md").is_file():
        return Path(p).expanduser().resolve()
    cwd = Path.cwd().resolve()
    for cand in (cwd, *cwd.parents):
        if (cand / "wiki" / "Index.md").is_file():
            return cand
    return None


def find_package(explicit: str | None) -> Path | None:
    if explicit:
        c = Path(explicit).expanduser()
        return c.resolve() if (c / "scripts" / "moblee-setup.py").is_file() else None
    cands = []
    try:
        p = (Path.home() / ".config" / "moblee" / "package-path").read_text().strip()
        if p:
            cands.append(Path(p).expanduser())
    except OSError:
        pass
    cands.append(Path(__file__).resolve().parent.parent)
    for c in cands:
        if (c / "scripts" / "moblee-setup.py").is_file():
            return c.resolve()
    return None


def read_setup(package: Path, vault: Path, *args: str):
    env = dict(os.environ, MOBLEE_VAULT=str(vault))
    r = subprocess.run([sys.executable, str(package / "scripts" / "moblee-setup.py"), *args],
                       capture_output=True, text=True, timeout=120, env=env)
    if r.returncode != 0:
        raise RuntimeError(f"moblee-setup.py {' '.join(args)} stopped: "
                           + (r.stderr.strip() or r.stdout.strip())[:300])
    return json.loads(r.stdout)


def minutes(n) -> str:
    try:
        n = int(n)
    except (TypeError, ValueError):
        return ""
    return "about 1 minute" if n == 1 else f"about {n} minutes"


def sentence(s: str) -> str:
    s = " ".join(str(s or "").split())
    return s if not s or s[-1] in ".!?" else s + "."


def place(item: dict, state: str) -> str:
    """Which of the four groups an extra belongs in."""
    if state == "on":
        return "in"
    if item.get("paid") or item.get("group") == PAID_GROUP:
        return "paid"
    return "silent" if item.get("how") == "silent" else "window"


def extra_line(item: dict, state: str, group: str) -> str:
    what = sentence(item.get("what", ""))
    if group == "in":
        return f"- **{item.get('title', item.get('key'))}**: {what} In place."
    bits = [minutes(item.get("minutes"))]
    if item.get("how") == "terminal":
        bits.append("opens a Terminal window")
    elif item.get("how") == "clicks":
        bits.append("a few clicks in Claude's own app")
    if group == "paid":
        bits.append(str(item.get("cost", "")).replace("PAID: ", ""))
    tail = "; ".join(b for b in bits if b)
    tail = tail[0].upper() + tail[1:] + "." if tail else ""
    note = ""
    if state == "unseen":
        note = " (It may already be on: a connection made in Claude's own app cannot be seen from here.)"
    return f"- **{item.get('title', item.get('key'))}**: {what} {tail}{note}".rstrip()


def core_line(part: dict) -> str:
    what = sentence(part.get("what", ""))
    say = part.get("say") or ""
    try_it = f" Say \"{say}\"." if say else ""
    if part.get("state") == "missing":
        try_it += " Not in place right now: say \"something is wrong\" and your assistant will look."
    elif part.get("state") == "differs":
        try_it += " An older copy is in place; the next update brings it level."
    return f"- **{part.get('title', part.get('key'))}**: {what}{try_it}"


def mail_pass_on(vault: Path) -> bool:
    """Whether the owner's page records a yes to the mail pass, under
    "Installed, and why" (a `mail-pass` line there)."""
    try:
        text = (vault / "wiki" / "Wiki Operations" / "Habits and Tools.md").read_text(encoding="utf-8")
    except (OSError, ValueError):
        return False
    grab = False
    for line in text.split("\n"):
        if line.startswith("## "):
            grab = line[3:].strip().lower().startswith("installed")
            continue
        if grab and "`mail-pass`" in line:
            return True
    return False


def build_page(parts: dict, items: list, today: datetime.date, mail_pass_page: bool,
               mail_on: bool = False) -> str:
    """The whole page, from the two readings. Pure: no files, no clock."""
    assistant = parts.get("assistant") or "claude"
    extras_state = parts.get("extras") or {}
    groups: dict[str, list[str]] = {k: [] for k, _ in GROUPS}
    for part in parts.get("core") or []:
        groups["in"].append(core_line(part))
    orient = ("- **Orient, the morning pass**: Say \"orient\" for a short report on your wiki "
              "and today's to-do list at the top of your daily note. In place.")
    mail_name = "[[Mail Pass|The mail pass]]" if mail_pass_page else "The mail pass"
    mail = (f"- **{mail_name}**: Sorts your unread Apple Mail by sender and subject at each "
            "orient, keeping people, money and things to act on. "
            + ("On." if mail_on else "Off until you say yes; your assistant offers it once "
               "if your mail is in Apple Mail."))
    groups["in"] += [orient, mail]
    for item in items:
        if item.get("how") == "hidden" or not item.get("key"):
            continue
        state = extras_state.get(item["key"], "unknown")
        g = place(item, state)
        if assistant == "chatgpt" and g != "in":
            continue
        groups[g].append(extra_line(item, state, g))

    out = [
        "---",
        "type: Wiki Operations Reference",
        MARK,
        f"updated: {today.isoformat()}",
        "---",
        "",
        "# What Your Wiki Can Do",
        "",
        f"*Made by Moblee from what is on this Mac on {long_date(today)}. It is rewritten "
        "whole each time, so do not edit it by hand. To bring it up to date, say \"show me "
        "everything\".* What you have turned down is kept on [[Habits and Tools]].",
    ]
    if assistant in ("chatgpt", "both"):
        out += ["", CLAUDE_ONLY]
    for key, title in GROUPS:
        if assistant == "chatgpt" and key != "in":
            continue
        out += ["", f"## {title}", ""]
        out += groups[key] or ["*Nothing here right now.*"]
    return "\n".join(out) + "\n"


def without_date(text: str) -> str:
    return "\n".join(l for l in text.split("\n")
                     if not l.startswith("updated: ") and not l.startswith("*Made by Moblee from"))


def write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o644
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.chmod(tmp, mode)
    os.replace(tmp, path)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Write the page that lists what this wiki can do.")
    ap.add_argument("--vault")
    ap.add_argument("--package")
    ap.add_argument("--print", action="store_true", help="print the page and write nothing")
    a = ap.parse_args(argv)
    vault = find_vault(a.vault)
    if vault is None:
        print("Could not find the wiki. Pass --vault <path>, or run this from inside it.")
        return 1
    package = find_package(a.package)
    if package is None:
        print("Could not find the Moblee folder (no ~/.config/moblee/package-path). "
              "Pass --package <path to the Moblee folder>.")
        return 1
    try:
        parts = read_setup(package, vault, "--parts")
        items = read_setup(package, vault, "--list", "--json")
    except Exception as e:  # noqa: BLE001
        print(f"The list could not be read, so the page was left as it is ({e}).")
        return 1
    if not isinstance(parts, dict) or not isinstance(items, list):
        print("The list came back in a shape this script does not know; the page was left as it is.")
        return 1
    page = vault / PAGE_REL
    text = build_page(parts, items, datetime.date.today(),
                      (vault / "wiki" / "Wiki Operations" / "Mail Pass.md").is_file(),
                      mail_pass_on(vault))
    if a.print:
        sys.stdout.write(text)
        return 0
    old = None
    if page.exists():
        try:
            old = page.read_text(encoding="utf-8")
        except (OSError, ValueError):
            old = ""
        if MARK not in old:
            print(f"{PAGE_REL} is not one Moblee wrote (it has no generated mark), so it was "
                  "left exactly as it is.")
            return 0
        if without_date(old) == without_date(text):
            print(f"{PAGE_REL} is already up to date")
            return 0
    write_atomic(page, text)
    print(f"{'added' if old is None else 'refreshed'} {PAGE_REL}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
