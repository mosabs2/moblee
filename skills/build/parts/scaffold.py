#!/usr/bin/env python3
"""scaffold.py - lay down a new thing beside the wiki, from Moblee's standard parts.

    python3 scaffold.py --vault <wiki folder> --name <name> --title "<Title>" [options]

    --what "<one sentence>"   what it is, in the owner's words (goes on the page)
    --plan "<one sentence>"   what this first build will do (the first Progress line)
    --job                     it runs on a schedule: adds job.py and the launch agent
    --think                   its job asks the assistant: prompt.md, fence.json and a launch
                              agent that runs Moblee's think-job.py (implies --job)
    --hour H --minute M       when the job runs (default 07:30)
    --reach                   it also listens on the owner's phone route (the Reach item),
                              while the Mac is awake
    --launcher                make "Open <Title>.app" for a double-click start
    --outside <folder>        tier 3: the code lives outside the wiki (e.g. ~/Apps/<name>);
                              apps/<name>/ then holds only app.json and a README
    --port N                  the port the server uses (otherwise chosen from 7400-7499)
    --dry-run                 say what would be made, make nothing

What it makes, and never overwrites (an existing file is left alone and named):

    apps/<name>/README.md, app.json, index.html, moblee-app.js, server.py, notify.py, data/, state/
    apps/<name>/job.py and com.moblee.<name>.plist          (--job)
    apps/<name>/prompt.md, fence.json and the plist          (--think)
    apps/<name>/Open <Title>.app                             (--launcher, through the Mac's osacompile)
    wiki/Projects/<Title>.md                                 the thing's own page
    wiki/Projects.md                                         the index, if the wiki has none
    one line on wiki/Index.md                                 if the Projects page is not on it yet
    one entry in .claude/launch.json                         so Claude's app can open it in its preview

Nothing is deleted, moved or replaced. Run it from anywhere; it needs only the
Python that comes with the Mac.
"""
from __future__ import annotations

import argparse
import datetime
import json
import re
import shutil
import socket
import subprocess
import sys
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

PARTS = Path(__file__).resolve().parent

# Ports browsers refuse to open; the same list server.py carries.
BAD_PORTS = {
    1, 7, 9, 11, 13, 15, 17, 19, 20, 21, 22, 23, 25, 37, 42, 43, 53, 69, 77, 79,
    87, 95, 101, 102, 103, 104, 109, 110, 111, 113, 115, 117, 119, 123, 135, 137,
    139, 143, 161, 179, 389, 427, 465, 512, 513, 514, 515, 526, 530, 531, 532, 540,
    548, 554, 556, 563, 587, 601, 636, 989, 990, 993, 995, 1719, 1720, 1723, 2049,
    3659, 4045, 4190, 5060, 5061, 6000, 6566, 6665, 6666, 6667, 6668, 6669, 6697,
    10080,
}


def ports_taken(vault: Path) -> set:
    """The ports other things in apps/ have recorded."""
    taken = set()
    apps = vault / "apps"
    if apps.is_dir():
        for m in apps.glob("*/app.json"):
            try:
                loaded = json.loads(m.read_text(encoding="utf-8"))
                if isinstance(loaded, dict) and isinstance(loaded.get("port"), int):
                    taken.add(loaded["port"])
            except (OSError, ValueError):
                pass
    return taken


def pick_port(vault: Path) -> int:
    taken = ports_taken(vault)
    for p in range(7400, 7500):
        if p in BAD_PORTS or p in taken:
            continue
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.2)
            if s.connect_ex(("127.0.0.1", p)) != 0:
                return p
    fail("no free port between 7400 and 7499")


def fail(msg: str) -> None:
    sys.exit(f"scaffold: {msg}")


def owner_name(vault: Path) -> str:
    """The owner's name from the rules file, or 'the owner'."""
    for f in ("CLAUDE.md", "AGENTS.md"):
        p = vault / f
        if p.exists():
            m = re.search(r"knowledge base for \*{0,2}([^*\n]+?)\*{0,2} where", p.read_text(errors="replace"))
            if m and "[Your Name]" not in m.group(1):
                return m.group(1).strip()
    return "the owner"


def fill(text: str, subs: dict) -> str:
    for k, v in subs.items():
        text = text.replace(k, v)
    return text


class Maker:
    def __init__(self, dry: bool) -> None:
        self.dry = dry
        self.made: list[str] = []
        self.skipped: list[str] = []

    def write(self, path: Path, text: str) -> bool:
        if path.exists():
            self.skipped.append(str(path))
            return False
        self.made.append(str(path))
        if not self.dry:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        return True

    def folder(self, path: Path) -> None:
        if not path.exists():
            self.made.append(str(path) + "/")
            if not self.dry:
                path.mkdir(parents=True, exist_ok=True)

    def append(self, path: Path, text: str, unless: str) -> None:
        """Add text to the end of an existing file, unless it already carries `unless`."""
        current = path.read_text(encoding="utf-8") if path.exists() else ""
        if unless in current:
            self.skipped.append(f"{path} (already has it)")
            return
        self.made.append(f"{path} (a line added)")
        if not self.dry:
            sep = "" if current.endswith("\n") or not current else "\n"
            path.write_text(current + sep + text, encoding="utf-8")


def add_index_line(mk: Maker, vault: Path) -> None:
    index = vault / "wiki" / "Index.md"
    if not index.exists():
        mk.skipped.append(f"{index} (no Index page to add to)")
        return
    text = index.read_text(encoding="utf-8")
    if "[[Projects]]" in text or "[[Projects|" in text or "[[Projects#" in text:
        mk.skipped.append(f"{index} (already links the Projects page)")
        return
    line = ("- [[Projects]]: everything built beside the wiki for its owner, with a page per thing "
            "in `wiki/Projects/` and the code in `apps/`")
    lines = text.split("\n")
    for i, l in enumerate(lines):
        if l.strip() == "## Domains":
            # after the heading and any explanatory paragraph that follows it
            j = i + 1
            while j < len(lines) and (lines[j].strip() == "" or lines[j].startswith("(")):
                j += 1
            lines.insert(j, line)
            break
    else:
        lines += ["", line]
    mk.made.append(f"{index} (a line added)")
    if not mk.dry:
        index.write_text("\n".join(lines), encoding="utf-8")


def add_launch_entry(mk: Maker, vault: Path, name: str, app_dir: Path, port: int | None) -> None:
    """(0.12.0) One entry in the wiki's .claude/launch.json, so the owner's
    Claude can open the thing in the desktop app's own preview pane and show
    it working. An entry of this name is left alone; a file that does not read
    as the expected shape is left alone and named."""
    if not port:
        return
    path = vault / ".claude" / "launch.json"
    entry = {"name": name, "runtimeExecutable": "python3",
             "runtimeArgs": [str(app_dir.relative_to(vault) / "server.py"), "--port", str(port)],
             "port": port}
    data = {"version": "0.0.1", "configurations": []}
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            loaded = None
        if not isinstance(loaded, dict) or not isinstance(loaded.get("configurations"), list):
            mk.skipped.append(f"{path} (not in the shape Claude's app expects; the preview entry was not added)")
            return
        data = loaded
        if any(isinstance(c, dict) and c.get("name") == name for c in data["configurations"]):
            mk.skipped.append(f"{path} (already has an entry for {name})")
            return
    data["configurations"].append(entry)
    if mk.dry:
        mk.made.append(f"{path} (would add the preview entry for {name})")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    mk.made.append(f"{path} (preview entry for {name})")


def make_launcher(mk: Maker, app_dir: Path, title: str) -> None:
    out = app_dir / f"Open {title}.app"
    if out.exists():
        mk.skipped.append(str(out))
        return
    mk.made.append(str(out))
    if mk.dry:
        return
    if not shutil.which("osacompile"):
        print("   (no osacompile on this Mac, so no launcher was made; the README's line still works)")
        mk.made = [m for m in mk.made if m != str(out)]
        return
    folder = str(app_dir).replace("\\", "\\\\").replace('"', '\\"')
    # state/ is kept out of the wiki's history, so after a clone or a restore
    # it is not there until something makes it; the launcher makes it first.
    script = (
        f'do shell script "cd \\"{folder}\\" && mkdir -p state && /usr/bin/python3 server.py --open '
        f'> state/launcher-out.txt 2>&1 &"\n'
    )
    src = app_dir / "state" / "launcher.applescript"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text(script, encoding="utf-8")
    r = subprocess.run(["osacompile", "-o", str(out), str(src)], capture_output=True, text=True)
    if r.returncode != 0:
        print("   (osacompile could not make the launcher: " + r.stderr.strip() + ")")
        mk.made = [m for m in mk.made if m != str(out)]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vault", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--what", default="")
    ap.add_argument("--plan", default="the first, smallest version.")
    ap.add_argument("--job", action="store_true")
    ap.add_argument("--think", action="store_true")
    ap.add_argument("--hour", type=int, default=7)
    ap.add_argument("--minute", type=int, default=30)
    ap.add_argument("--weekday", type=int, help="run on one day a week: 0 Sunday to 6 Saturday")
    ap.add_argument("--reach", action="store_true")
    ap.add_argument("--launcher", action="store_true")
    ap.add_argument("--outside")
    ap.add_argument("--port", type=int)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    vault = Path(a.vault).expanduser().resolve()
    if not (vault / "wiki").is_dir():
        fail(f"{vault} has no wiki/ folder; is that the wiki?")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,39}", a.name):
        fail("--name is short and lower-case: letters, digits and hyphens, such as tide-times")
    a.title = a.title.strip()
    if (not re.fullmatch(r"[^/\\:\n\[\]#|*\"<>?^]{1,60}", a.title)
            or a.title.startswith(".") or a.title.endswith(".")):
        fail("--title cannot contain / \\ : [ ] # | * \" < > ? or ^, and cannot start or end with a dot")
    if a.title.casefold() == "projects":
        fail("--title cannot be Projects: that is the index page's name")
    if a.port and (not (1024 <= a.port <= 65535) or a.port in BAD_PORTS):
        fail("--port is a number between 1024 and 65535 that browsers accept (7400 to 7499 are safe)")
    if not (0 <= a.hour <= 23 and 0 <= a.minute <= 59):
        fail("--hour is 0 to 23 and --minute is 0 to 59")
    if a.weekday is not None and not (0 <= a.weekday <= 6):
        fail("--weekday is 0 (Sunday) to 6 (Saturday)")
    if a.think:
        a.job = True
    if a.reach and a.outside:
        fail("--reach is for a thing that runs on the wiki's own server; a thing outside the wiki has its own")
    if a.job and a.outside:
        fail("--job and --think are for a thing inside the wiki; a thing outside the wiki keeps its own schedule")

    today = datetime.datetime.now().strftime("%-d %B %Y")
    owner = owner_name(vault)
    app_dir = vault / "apps" / a.name
    outside = Path(a.outside).expanduser() if a.outside else None
    mk = Maker(a.dry_run)

    # The same name with a different title would leave two pages and two
    # sections for one thing; the first title stands.
    existing = app_dir / "app.json"
    if existing.exists():
        try:
            was = json.loads(existing.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            was = {}
        if isinstance(was, dict) and was.get("title") and was["title"] != a.title:
            fail(f"apps/{a.name}/ is already \"{was['title']}\"; keep that title, or choose a new --name")
    # A page of this title elsewhere in the wiki would catch the [[link]]
    # instead of the thing's own page, so the clash is named rather than made.
    page_path = vault / "wiki" / "Projects" / f"{a.title}.md"
    clash = next((p for p in (vault / "wiki").rglob(f"{a.title}.md") if p != page_path), None)
    if clash is not None:
        fail(f"the wiki already has a page called \"{a.title}\" at {clash}; choose another --title")
    if a.port is None and not outside:
        a.port = pick_port(vault)

    # --- the folder beside the wiki --------------------------------------
    mk.folder(app_dir)
    manifest = {
        "name": a.name,
        "title": a.title,
        "made": datetime.date.today().isoformat(),
        "tier": 3 if outside else 2,
        "outside": str(outside) if outside else None,
        "port": a.port,
        "job": ({"every_hours": 24 * 7 if a.weekday is not None else 24, "label": f"com.moblee.{a.name}",
                 "thinking": bool(a.think), "hour": a.hour, "minute": a.minute, "weekday": a.weekday} if a.job else None),
        "reach": bool(a.reach),
        "publish": None,
        "page": f"wiki/Projects/{a.title}.md",
    }
    mk.write(app_dir / "app.json", json.dumps(manifest, indent=2) + "\n")

    subs = {
        "__APP_NAME__": a.name, "__APP_TITLE__": a.title, "__OWNER__": owner, "__DATE__": today,
        "__APP_DIR__": str(app_dir), "__HOUR__": str(a.hour), "__MINUTE__": str(a.minute),
    }
    if outside:
        open_lines = (f"The code lives outside the wiki at `{outside}`. Its own README there says how to start it; "
                      f"the assistant can also start it when asked.")
        job_lines = ""
    else:
        open_lines = (f"Double-click `Open {a.title}.app` in this folder (you can keep it in the Dock), "
                      f"or say \"open {a.title}\" to the assistant." if a.launcher else
                      f"Say \"open {a.title}\" to the assistant, or in a Terminal window of your own: "
                      f"`cd \"{app_dir}\"` and then `python3 server.py --open`.")
        for part in ("index.html", "moblee-app.js", "server.py", "notify.py"):
            mk.write(app_dir / part, fill((PARTS / part).read_text(encoding="utf-8"), subs))
        mk.folder(app_dir / "data")
        mk.folder(app_dir / "state")
        job_lines = ""
        if a.job:
            plist = f"com.moblee.{a.name}.plist"
            # The plist is XML, so a folder name holding & or < is written escaped,
            # or launchctl refuses the file.
            plist_subs = {k: xml_escape(v) for k, v in subs.items()}
            plist_subs["__WEEKDAY_BLOCK__"] = (
                f"\n        <key>Weekday</key>\n        <integer>{a.weekday}</integer>" if a.weekday is not None else "")
            # The thinking job runs Moblee's own think-job.py from the skill's
            # installed folder, whose path stays the same across versions; the
            # pack's own copy is the fallback where the skill is not installed.
            installed_think = Path.home() / ".claude" / "skills" / "build" / "parts" / "think-job.py"
            think_path = installed_think if installed_think.is_file() else PARTS / "think-job.py"
            plist_subs["__THINK_JOB__"] = xml_escape(str(think_path))
            if a.think:
                mk.write(app_dir / "prompt.md", fill((PARTS / "prompt.template.md").read_text(encoding="utf-8"), subs))
                mk.write(app_dir / "fence.json", (PARTS / "fence.json").read_text(encoding="utf-8"))
                mk.write(app_dir / plist, fill((PARTS / "think-agent.plist").read_text(encoding="utf-8"), plist_subs))
                what_runs = (f"Moblee's `think-job.py` asks the assistant what `prompt.md` says, within the limits "
                             f"written in `fence.json` (what it may read and write, and how long it may take), every "
                             f"day at {a.hour:02d}:{a.minute:02d} once you have switched it on; the answer is kept at "
                             f"`state/last-answer.md`")
                by_hand = f"`python3 \"{think_path}\" --app \"{app_dir}\"`"
            else:
                mk.write(app_dir / "job.py", fill((PARTS / "job.py").read_text(encoding="utf-8"), subs))
                mk.write(app_dir / plist, fill((PARTS / "launch-agent.plist").read_text(encoding="utf-8"), plist_subs))
                what_runs = f"`job.py` runs every day at {a.hour:02d}:{a.minute:02d} once you have switched it on"
                by_hand = f"`cd \"{app_dir}\"` and then `python3 job.py`"
            job_lines = (
                f"\n## Its job, which runs on a schedule\n\n"
                f"{what_runs}. It writes `state/last-run.json` and a line in `state/job-log.txt` every time, so the "
                f"check-up can see if it stops. If this Mac was asleep at that hour, the job runs once at the next "
                f"wake, however many days were missed. **To switch it on,** say \"switch on {a.title}\" to the "
                f"assistant and press the tile that appears in the Moblee app; the app copies the scheduler file "
                f"into place and switches it on. Without the app, in a Terminal window of your own, one line at a time:\n\n"
                f"```\ncp \"{app_dir / plist}\" ~/Library/LaunchAgents/\n```\n\n"
                f"```\nlaunchctl load ~/Library/LaunchAgents/{plist}\n```\n\n"
                f"To run it by hand: {by_hand}. If you have chosen alerts in Moblee, a line reaches your phone "
                f"when it finishes or fails, naming the file to look at.\n"
            )
        if a.reach:
            job_lines += (
                f"\n## From your phone\n\n"
                f"While this Mac is awake, {a.title} also opens from your phone, at an address your assistant will "
                f"tell you, which ends in :{a.port}, over the route you chose in Moblee's item \"Reach your things "
                f"from your phone\". When the Mac is asleep or shut, it is not "
                f"reachable; a page that must always be reachable goes on the web instead (the assistant can offer that).\n"
            )
    subs["__OPEN_LINES__"] = open_lines
    subs["__JOB_LINES__"] = job_lines
    if outside:
        # A pointer folder holds none of the parts, so its README says what it
        # is rather than listing files that are not there.
        readme = (
            f"# {a.title}\n\n"
            f"Made for {owner} by the wiki's assistant on {today}, with Moblee's build skill. This folder is a "
            f"pointer: it says that {a.title} exists and where it lives. Its page in the wiki is "
            f"`wiki/Projects/{a.title}.md`, which says what it is for, the decisions behind it and everything "
            f"changed since.\n\n"
            f"## Where it is\n\n"
            f"- The code lives outside the wiki at `{outside}`, with its own history. Its README there says "
            f"how to start it; the assistant can also start it when asked.\n"
            f"- Anything it makes that is worth keeping is in `wiki/data/{a.name}/`, inside the wiki, where "
            f"the wiki's history keeps it.\n\n"
            f"## To change it\n\n"
            f"Tell the assistant what you want different, in your own words. It says what will change and "
            f"what will not, changes the code and never your data, shows you the result, and writes a dated "
            f"line on the page.\n\n"
            f"## If it stops working\n\n"
            f"Say \"something is wrong\" to the assistant. The check-up reads this folder and the page and says "
            f"what it found in plain words. Nothing here is ever deleted.\n"
        )
        mk.write(app_dir / "README.md", readme)
    else:
        mk.write(app_dir / "README.md", fill((PARTS / "README.template.md").read_text(encoding="utf-8"), subs))
    if a.launcher and not outside:
        make_launcher(mk, app_dir, a.title)
    if not outside:
        add_launch_entry(mk, vault, a.name, app_dir, a.port)

    # --- the wiki's record --------------------------------------------------
    what = a.what or f"*(What {a.title} is, in {owner}'s words.)*"
    if outside:
        where = (f"- Code: `{outside}`, outside the wiki, with its own git history. Pointer in `apps/{a.name}/`.\n"
                 f"- Data worth keeping: `wiki/data/{a.name}/`.\n"
                 f"- Open it: see the README at `{outside}`.")
        mk.folder(vault / "wiki" / "data" / a.name)
    else:
        where = (f"- Code and page: `apps/{a.name}/` in the wiki folder.\n"
                 f"- Data: `apps/{a.name}/data/`.\n"
                 f"- Open it: {open_lines}")
    page_subs = dict(subs, __WHAT_IT_IS__=what, __WHERE_LINES__=where, __PLAN_LINE__=a.plan)
    mk.write(page_path, fill((PARTS / "record-page.md").read_text(encoding="utf-8"), page_subs))
    projects = vault / "wiki" / "Projects.md"
    mk.write(projects, (PARTS / "projects-index.md").read_text(encoding="utf-8"))
    place = f"`~/Apps/{a.name}` (outside the wiki)" if outside else f"`apps/{a.name}/`"
    mk.append(projects,
              f"\n## {a.title}\n\n{what} Lives in {place}; its page is [[{a.title}]]. "
              f"**{today}:** planned.\n",
              unless=f"[[{a.title}]]")
    add_index_line(mk, vault)

    print("Would make:" if a.dry_run else "Made:")
    for m in mk.made:
        print("   " + m)
    if mk.skipped:
        print("Left alone (already there):")
        for s in mk.skipped:
            print("   " + s)
    return 0


if __name__ == "__main__":
    sys.exit(main())
