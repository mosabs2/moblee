#!/usr/bin/env python3
"""Print one event's hook entries from a settings file, so that a case can say
whether an entry was left exactly as it was.

    python3 read-hooks.py <settings file> <event>

The entries come out as one line of JSON with their keys in a settled order, so
two runs of this can be compared as strings. A file that is not there, or that
does not read as settings, prints a word saying so rather than failing: the case
then fails on the comparison, which is where the reader is looking.
"""
import json
import sys

try:
    with open(sys.argv[1], encoding="utf-8") as fh:
        data = json.load(fh)
except OSError:
    print("no such settings file")
    raise SystemExit(0)
except ValueError as exc:
    print("not valid JSON (%s)" % exc)
    raise SystemExit(0)

hooks = data.get("hooks") if isinstance(data, dict) else None
entries = (hooks or {}).get(sys.argv[2], []) if isinstance(hooks, dict) else []
print(json.dumps(entries, sort_keys=True))
