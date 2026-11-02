#!/usr/bin/env python3
"""Test suite for the dashboard's reading of _context.md items (0.16.1).

The dashboard's Active threads, Open decisions and Watch list cards read the
items under those headings in wiki/_context.md. Owners' wikis write an item
either as a dashed line (`- **Title.** ...`) or as its own bold paragraph
(`**Title.** ...`); before 0.16.1 only the dashed form was read, and a wiki
written the other way showed empty cards. These cases build a practice wiki
whose _context.md uses every shape, load dashboard/server.py against it, and
check what build_state() reports: both shapes read, mixed in one section,
struck-out items and plain lines left out, a wikilink and a closing colon
cleaned from a title, and a later section never read.

The server is imported, never started. Usage:  python3 tools/test-dashboard-items.py
Prints a pass/fail table and exits non-zero on any failure. Nothing is
deleted: the practice wiki is left in the temp area, its path printed.
"""
import importlib.util
import os
import pathlib
import sys
import tempfile

PACK = pathlib.Path(__file__).resolve().parent.parent
SERVER = PACK / "dashboard" / "server.py"
ROOT = pathlib.Path(tempfile.mkdtemp(prefix="dashboard-items-test-"))

rows, failures = [], 0


def check(group, label, ok, detail=""):
    global failures
    rows.append(("ok" if ok else "FAIL", group, label + ("" if ok or not detail else f" ({detail})")))
    if not ok:
        failures += 1


CONTEXT = """# Context

Last refreshed: 29 October 2026 23:58

## Active threads

(Each thread named in bold, as its own paragraph.)

**Garden plan.** Beds measured, seeds ordered.

**The [[Kitchen]] refit:** quotes in from two firms.

~~**Old thread.**~~ Closed.

- **A dashed thread.** Written as a list.
  **Note:** a wrapped line inside the dashed item, not an item of its own.
- ~~**A struck dashed thread.**~~ Closed.
- **~~Struck inside the bold~~** closed too.

```
**Code sample.** Inside a code block, never an item.
```

## Open decisions

**Which school for the autumn.** Two visits left.

## Watch list

- **Train strike dates.** Watch the union's notice.

## Recent significant additions

**Not a thread.** This section is not read.
"""

wiki = ROOT / "wiki"
wiki.mkdir(parents=True)
(wiki / "Index.md").write_text("# Index\n", encoding="utf-8")
(wiki / "_context.md").write_text(CONTEXT, encoding="utf-8")
os.environ["MOBLEE_VAULT"] = str(ROOT)

spec = importlib.util.spec_from_file_location("moblee_dashboard_test", SERVER)
dash = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dash)
state = dash.build_state()


def titles(key):
    return [i["title"] for i in state[key]]


check("threads", "bold paragraphs and dashed lines both read, in order",
      titles("active") == ["Garden plan", "The Kitchen refit", "A dashed thread"], repr(titles("active")))
check("threads", "struck-out items left out, either shape",
      not any("Old" in t or "struck" in t for t in titles("active")), repr(titles("active")))
check("threads", "a plain line in brackets is not an item",
      not any(t.startswith("(") for t in titles("active")), repr(titles("active")))
check("decisions", "a decision written as a bold paragraph",
      titles("decisions") == ["Which school for the autumn"], repr(titles("decisions")))
check("watch", "a dashed watch item, as before",
      titles("watch") == ["Train strike dates"], repr(titles("watch")))
check("sections", "a bold paragraph in another section is never read",
      "Not a thread" not in titles("active") + titles("decisions") + titles("watch"))
check("titles", "a wikilink and a closing colon are cleaned from a title",
      "The Kitchen refit" in titles("active"), repr(titles("active")))
check("threads", "an indented bold line inside an item is not an item",
      "Note" not in titles("active"), repr(titles("active")))
check("threads", "a bold line inside a code block is not an item",
      "Code sample" not in titles("active"), repr(titles("active")))

# A _context.md saved in another encoding (Latin-1 here) must not stop the
# dashboard: before 0.16.1 it raised UnicodeDecodeError and no card loaded.
latin = ROOT / "latin1.md"
latin.write_bytes(b"## Active threads\n\n**Caf\xe9 plan.** Saved in Latin-1.\n")
try:
    read_ok = "plan" in dash.read_file(str(latin))
except UnicodeDecodeError:
    read_ok = False
check("encoding", "a file in another encoding is read, not a crash", read_ok)

width = max(len(g) for _, g, _ in rows)
for status, group, label in rows:
    print(f"{status:4}  {group:{width}}  {label}")
print(f"\n{len(rows) - failures} of {len(rows)} passed. Practice wiki: {ROOT}")
sys.exit(1 if failures else 0)
