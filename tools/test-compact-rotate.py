#!/usr/bin/env python3
"""Tests for scripts/compact-rotate.py: the refresh-note rotation, against
throwaway wikis. Run from the Moblee folder: python3 tools/test-compact-rotate.py"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent
PY = sys.executable
ROTATE = PKG / "scripts" / "compact-rotate.py"
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


def note(n: int) -> str:
    return f"{n} October 2026 22:00 +01 BST, for the {n} October workday (**Headline {n}.** Body of note {n}, with detail that runs on.)"


def context_with(notes: int) -> str:
    para = "Last refreshed: " + note(notes)
    for i in range(notes - 1, 0, -1):
        para += " Previous refresh: " + note(i)
    return ("# Working state and tempo\n\nWorking state for a test wiki.\n\n" + para +
            "\n\n## Active threads\n\n- **A thread.** Still open.\n\n## Vault snapshot\n\nSmall.\n")


def rotate(vault: Path, *flags: str) -> tuple[int, str]:
    r = subprocess.run([PY, str(ROTATE), "--vault", str(vault), *flags], capture_output=True, text=True, timeout=60)
    return r.returncode, (r.stdout + r.stderr).strip()


def main() -> int:
    root = Path(tempfile.mkdtemp(prefix="moblee-rotate-test-"))
    vault = root / "wiki-a"
    shutil.copytree(PKG / "vault-template", vault)
    ctx = vault / "wiki" / "_context.md"
    archive = vault / "wiki" / "Wiki Operations" / "Context Archive.md"
    print("compact-rotate")
    # 1. the template's own file: nothing to rotate
    code, out = rotate(vault)
    check(code == 0 and "nothing to rotate" in out, "a fresh wiki has nothing to rotate")
    # 2. five notes: three stay, two go to the archive, which is created
    ctx.write_text(context_with(5), encoding="utf-8")
    code, out = rotate(vault, "--dry-run")
    check(code == 0 and "would move 2" in out and "cut 2" in out and "archive 4" in out and not archive.exists(),
          "a dry run says what would move and creates nothing")
    code, out = rotate(vault)
    text = ctx.read_text(encoding="utf-8")
    check(code == 0 and "moved 2" in out and "archived 4" in out, "two notes leave the live file and four are archived in full")
    check(text.count("Previous refresh:") == 2 and "Body of note 5" in text and "Body of note 4" not in text
          and "**Headline 4.**" in text and "**Headline 3.**" in text and "Headline 2" not in text,
          "the newest stays in full, the two before it keep their headline, the rest leave")
    check("Earlier refresh notes live in full at [[Context Archive#Refresh-note history]]" in text,
          "the live file points at the archive")
    arch0 = archive.read_text() if archive.exists() else ""
    check(archive.exists() and "## Refresh-note history" in arch0 and "Body of note 2" in arch0 and "Body of note 1" in arch0
          and "Body of note 4" in arch0 and "Body of note 3" in arch0 and "Body of note 5" not in arch0
          and "## Closed threads and decisions" in arch0,
          "the archive page is created with both sections and holds every cut or moved note in full")
    check("## Active threads" in text and "- **A thread.** Still open." in text and "Small." in text,
          "nothing else in the working-state file is touched")
    # 3. a second run changes nothing
    before = text
    arch_before = archive.read_text()
    code, out = rotate(vault)
    check(code == 0 and "nothing to rotate" in out and ctx.read_text() == before and archive.read_text() == arch_before,
          "a second run changes nothing")
    # 4. a new refresh added later rotates one more into the existing archive, under its heading
    ctx.write_text(ctx.read_text().replace("Last refreshed: ", "Last refreshed: " + note(6) + " Previous refresh: ", 1),
                   encoding="utf-8")
    code, out = rotate(vault)
    arch = archive.read_text()
    check(code == 0 and "moved 1" in out and "cut 1" in out and "archived 1" in out and "Body of note 5" in arch
          and arch.count("Body of note 3") == 1 and arch.count("Body of note 2") == 1,
          "a later refresh cuts the next note, archives it once, and moves the oldest headline out")
    check(arch.index("## Refresh-note history") < arch.index("Body of note 5") < arch.index("## Closed threads and decisions"),
          "and it lands under the right heading")
    text2 = ctx.read_text(encoding="utf-8")
    check("Body of note 6" in text2 and "**Headline 5.**" in text2 and "Body of note 5" not in text2
          and "**Headline 4.**" in text2 and "Headline 3" not in text2, "the live file keeps three: one in full, two as headlines")
    # 5. a wiki with no such paragraph, and a missing file
    (vault / "wiki" / "_context.md").write_text("# Working state\n\nNo refresh line here.\n", encoding="utf-8")
    code, out = rotate(vault)
    check(code == 0 and "no 'Last refreshed:'" in out, "a file without the paragraph is left alone")
    code, out = rotate(root / "nowhere")
    check(code == 1, "a missing wiki is an error, not a crash")
    print(f"\ncompact-rotate: {PASSED} passed, {len(FAILED)} failed")
    for f in FAILED:
        print("  -", f)
    print(f"(the throwaway folder is {root}; the system clears it in time)")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
