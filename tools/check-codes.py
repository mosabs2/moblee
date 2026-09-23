"""Does every code the check-up emits have an entry, and is every entry either
emitted or declared as one the owner reports?

Run from the Moblee folder:  python3 tools/check-codes.py

Two blind spots this had on its first run, both worth knowing about if it is
ever changed: a code can reach a finding through a data table rather than as an
argument (F16 does), and a finding's level can be written as a conditional
rather than a plain name (F23 is). Both are read for here.
"""
import ast
import pathlib
import re
import sys

PKG = pathlib.Path(__file__).resolve().parent.parent
if not (PKG / "scripts" / "moblee-doctor.py").exists():
    PKG = pathlib.Path("/Users/mosabs/Wiki/Mo Sabs Wiki/outputs/moblee")
DOC = PKG / "scripts" / "moblee-doctor.py"
GUIDE = PKG / "skills" / "companion" / "field-guide.md"

src = DOC.read_text()
tree = ast.parse(src)

LEVELS = {"LOOK", "PROBLEM", "UNSEEN", "UNSURE", "OK"}


def levels_of(node):
    """The level names a finding can be raised at, conditionals included."""
    if isinstance(node, ast.Name):
        return {node.id}
    if isinstance(node, ast.IfExp):
        return levels_of(node.body) | levels_of(node.orelse)
    return set()


uncoded = []
for node in ast.walk(tree):
    if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr == "add" and node.args):
        continue
    lv = levels_of(node.args[0]) & LEVELS
    if not (lv & {"LOOK", "PROBLEM"}):
        continue
    # A third argument is enough. It is usually the code itself, and sometimes a
    # variable carrying one from a table (the Applications sweep does that), and
    # a checker that insisted on seeing the literal would report the table as a
    # gap for ever. What a wrong code would produce is caught below, by the
    # entry check.
    coded = len(node.args) >= 3
    if not coded:
        uncoded.append((node.lineno, "/".join(sorted(lv))))

# every Fnn written anywhere in the check-up is a code it can show: they appear
# nowhere else in the file, which is what lets a table-borne one be counted
emitted = set(re.findall(r'"(F\d+)"', src))

guide_text = GUIDE.read_text()
explained = set(re.findall(r"^## (F\d+)\.", guide_text, re.M))
m = re.search(r"Eleven are things only the owner can report[^\n]*", guide_text)
owner_led = set(re.findall(r"F\d+", m.group(0))) if m else set()

fails = 0
if uncoded:
    fails += 1
    print("FAIL  findings with no field-guide code:")
    for lineno, level in uncoded:
        print(f"        moblee-doctor.py:{lineno} ({level})")
else:
    print("ok    every LOOK and PROBLEM carries a code")

missing = sorted(emitted - explained)
if missing:
    fails += 1
    print(f"FAIL  codes the check-up shows with no entry: {', '.join(missing)}")
else:
    print(f"ok    all {len(emitted)} codes the check-up shows have an entry")

orphans = sorted(explained - emitted - owner_led)
if orphans:
    fails += 1
    print("FAIL  entries neither shown by the check-up nor declared owner-reported: "
          + ", ".join(orphans))
    print("      add the code to the preamble's list, or wire it up")
else:
    print(f"ok    every entry is shown or declared owner-reported "
          f"({len(owner_led)} owner-reported)")

sys.exit(1 if fails else 0)
