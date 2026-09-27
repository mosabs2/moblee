#!/usr/bin/env python3
"""build-corpus.py — work out every body text Moblee has ever shipped for each
section of the vault's rules file, and write their digests to
scripts/claude-md-known.json.

Why this exists. From v0.9.4 the updater REPLACES the sections Moblee owns in an
existing owner's CLAUDE.md, rather than only adding to it. A replacement is only
safe where the section still says what Moblee last shipped, word for word: if the
owner has added a line of their own to it, the section must be left alone. That
judgement is made by comparing a SHA-256 of the section's body against the set of
bodies Moblee has shipped under that heading. This script builds that set.

A real owner's rules file is not a pristine template. It is some historical
template, with later Moblee updaters having inserted blocks into it. So for every
historical version V of vault-template/CLAUDE.md the corpus records:

  * the sections of V as shipped;
  * the sections of P(V) for every historical version P of the patcher, run for
    Claude and again for ChatGPT (the two differ by one paragraph);
  * the sections of the whole chain, every patcher in turn, oldest first, which
    is what an owner who has taken every update actually has.

It also checks the assumption the whole design rests on, that the patcher is
additive and idempotent, and says so if it does not hold.

Regenerate after any change to vault-template/CLAUDE.md, from the repo root:

    python3 tools/claude-md-corpus/build-corpus.py

Add --report to see, per heading, how many distinct bodies were found and which
versions produced them. Nothing outside the system temp folder is written except
the one JSON file.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACK = HERE.parent.parent

# The section reader lives in the script that uses it, which has a hyphen in
# its name and so cannot be imported the ordinary way.
_spec = importlib.util.spec_from_file_location("patch_claude_md", PACK / "scripts" / "patch-claude-md.py")
engine = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(engine)
PREAMBLE_KEY, digest_body, split_sections = engine.PREAMBLE_KEY, engine.digest_body, engine.split_sections

RULES_REL = "vault-template/CLAUDE.md"
PATCHER_REL = "scripts/patch-claude-md.py"
OUT = PACK / "scripts" / "claude-md-known.json"


def git(*args: str) -> str:
    p = subprocess.run(["git", "-C", str(PACK), *args], capture_output=True, text=True)
    if p.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed: {p.stderr.strip()}")
    return p.stdout


def commits(rel: str) -> list[str]:
    """Newest first, as git gives them; renames followed."""
    out = git("log", "--follow", "--format=%H", "--", rel).split()
    return out


def show(sha: str, rel: str) -> str | None:
    p = subprocess.run(["git", "-C", str(PACK), "show", f"{sha}:{rel}"],
                       capture_output=True, text=True)
    return p.stdout if p.returncode == 0 else None


def run_patcher(patcher: Path, rules: str, home: Path, assistant: str) -> str | None:
    """Patch one rules file in a throwaway vault and give back the result."""
    vault = Path(tempfile.mkdtemp(prefix="vault-", dir=str(home)))
    ops = vault / "wiki" / "Wiki Operations"
    ops.mkdir(parents=True)
    (vault / "wiki" / "Index.md").write_text("# Index\n", encoding="utf-8")
    (vault / "CLAUDE.md").write_text(rules, encoding="utf-8")
    # The four reference pages are put in place, because that is the state a
    # real wiki is in when the patcher runs: the updater lays them down first,
    # and without them the patcher holds back every drop.
    for name in ("Wiki Conventions", "Git and Commits", "Tools and Connections", "Readwise"):
        src = PACK / "vault-template" / "wiki" / "Wiki Operations" / f"{name}.md"
        if src.is_file():
            (ops / f"{name}.md").write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    env = dict(os.environ)
    env["HOME"] = str(home)
    env["MOBLEE_VAULT"] = str(vault)
    env["MOBLEE_BACKUP"] = str(home / "backups")
    for args in ([sys.executable, str(patcher), "--vault", str(vault), "--assistant", assistant],
                 [sys.executable, str(patcher), "--vault", str(vault)],
                 [sys.executable, str(patcher)]):
        p = subprocess.run(args, capture_output=True, text=True, cwd=str(vault), env=env)
        if p.returncode == 0:
            return (vault / "CLAUDE.md").read_text(encoding="utf-8")
    return None


def add(corpus: dict, provenance: dict, text: str, where: str) -> None:
    pre, sections = split_sections(text)
    for key, body in [(PREAMBLE_KEY, pre)] + [(h, b) for h, b in sections]:
        d = digest_body(body)
        corpus.setdefault(key, set()).add(d)
        provenance.setdefault(key, {}).setdefault(d, []).append(where)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()

    rules_shas = commits(RULES_REL)
    patch_shas = commits(PATCHER_REL)
    if not rules_shas:
        raise SystemExit("no history for " + RULES_REL)
    print(f"{len(rules_shas)} historical versions of {RULES_REL}")
    print(f"{len(patch_shas)} historical versions of {PATCHER_REL}")

    work = Path(tempfile.mkdtemp(prefix="moblee-corpus-", dir=os.environ.get("TMPDIR") or "/tmp"))
    home = work / "home"
    (home / ".config" / "moblee").mkdir(parents=True)

    old_patchers: list[tuple[str, Path]] = []
    for i, sha in enumerate(reversed(patch_shas)):        # oldest first
        text = show(sha, PATCHER_REL)
        if text is None:
            continue
        p = work / f"patcher-{i:02d}.py"
        p.write_text(text, encoding="utf-8")
        old_patchers.append((sha[:8], p))
    # the copy in the working tree is the one shipping now
    now_patcher = ("worktree", PACK / PATCHER_REL)

    versions: list[tuple[str, str]] = []
    for sha in reversed(rules_shas):                      # oldest first
        text = show(sha, RULES_REL)
        if text is not None:
            versions.append((sha[:8], text))
    versions.append(("worktree", (PACK / RULES_REL).read_text(encoding="utf-8")))

    corpus: dict[str, set] = {}
    provenance: dict[str, dict] = {}
    notes: list[str] = []

    def sweep(patchers: list[tuple[str, Path]]) -> None:
        for label, text in versions:
            add(corpus, provenance, text, f"{label} as shipped")
            for pl, patcher in patchers:
                for assistant in ("claude", "chatgpt"):
                    got = run_patcher(patcher, text, home, assistant)
                    if got is None:
                        notes.append(f"patcher {pl} would not run on {label}; skipped")
                        continue
                    add(corpus, provenance, got, f"{label} patched by {pl} ({assistant})")
                    # the assumption the whole design rests on
                    again = run_patcher(patcher, got, home, assistant)
                    if again is not None and again != got:
                        notes.append(f"NOT IDEMPOTENT: patcher {pl} on {label} ({assistant}) "
                                     f"changes the file a second time")
                        add(corpus, provenance, again, f"{label} patched twice by {pl} ({assistant})")
            # every updater in turn, oldest first: what an owner who took every update has
            chained = text
            for _pl, patcher in patchers:
                got = run_patcher(patcher, chained, home, "claude")
                if got is not None:
                    chained = got
            add(corpus, provenance, chained, f"{label} through every patcher in turn")

    def write_out() -> int:
        data = {
            "_comment": [
                "Digests of every section body Moblee has ever shipped in the vault's rules file.",
                "heading -> list of SHA-256 digests of the normalised body (trailing whitespace",
                "stripped per line, runs of blank lines collapsed to one, leading and trailing",
                "blank lines removed; the heading itself is not digested).",
                "scripts/patch-claude-md.py replaces or drops a section only when its body",
                "digest is in this list, so an owner's own addition is never overwritten.",
                "GENERATED FILE. Do not edit by hand. Regenerate from the repo root with:",
                "    python3 tools/claude-md-corpus/build-corpus.py",
                f"The key {PREAMBLE_KEY!r} is the text above the first '## ' heading.",
            ],
            "headings": {k: sorted(v) for k, v in sorted(corpus.items())},
        }
        OUT.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        return sum(len(v) for v in corpus.values())

    # Pass one: the patchers that shipped before this version. The one shipping
    # now reads the file this script writes, so it can only be run once there is
    # a file for it to read; the passes after that repeat until nothing new
    # turns up, which is also how its own idempotency gets proved.
    sweep(old_patchers)
    total = write_out()
    for n in range(1, 4):
        sweep([now_patcher])
        after = write_out()
        print(f"pass {n} with the patcher shipping now: {after - total} new bodies")
        if after == total:
            break
        total = after
    else:
        notes.append("the corpus was still growing after three passes; something is not settling")
    print(f"wrote {OUT.relative_to(PACK)}: {len(corpus)} headings, {total} distinct bodies")

    if notes:
        print("\nnotes:")
        for n in dict.fromkeys(notes):
            print("  " + n)
    else:
        print("\nthe patcher is additive and idempotent on every version tried: "
              "patch(patch(V)) == patch(V) throughout.")

    if a.report:
        print("")
        for key in sorted(corpus):
            print(f"  {key}: {len(corpus[key])} distinct bodies")
            for d in sorted(corpus[key]):
                print(f"      {d[:12]}  {provenance[key][d][0]}"
                      f" (+{len(provenance[key][d]) - 1} more)")
    print(f"\nscratch kept: {work}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
