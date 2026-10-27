#!/usr/bin/env python3
"""Run the commit gate as it behaves on a Mac with no PyYAML installed.

G8, the frontmatter check, does the full YAML parse where PyYAML happens to be
there and uses its own simpler test where it is not. Nothing in the pack
installs PyYAML, so the simpler test is the one most owners actually run, and
it needs proving as well as the other.

This loads the gate out of the wiki it is run in, takes PyYAML away from that
copy of it, and runs it. The exit code and everything printed are the gate's
own, so the rig can read them exactly as it reads an ordinary run.

    cd <wiki> && python3 .../gate-without-pyyaml.py
"""
import importlib.util
import pathlib
import sys

gate = pathlib.Path.cwd() / "scripts" / "vault-gate.py"
if not gate.is_file():
    print(f"no commit gate at {gate} — run this from the wiki's own folder", file=sys.stderr)
    sys.exit(2)

spec = importlib.util.spec_from_file_location("vault_gate_without_pyyaml", gate)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.yaml = None
sys.exit(module.main())
