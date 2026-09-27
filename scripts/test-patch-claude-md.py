#!/usr/bin/env python3
"""
Test suite for the section engine in scripts/patch-claude-md.py, and for
scripts/add-reference-pages.py, which is the other half of it.

    python3 scripts/test-patch-claude-md.py

Prints a pass/fail table and exits non-zero on any failure. Everything is built
in a throwaway folder under the system temp area, which is left where it is.

What is being proved. From v0.9.4 the updater REPLACES the sections Moblee owns
in an owner's rules file and DROPS the ones whose content has moved to a page of
its own. The whole design rests on one rule: a section is only touched where its
body still matches, word for word, something Moblee shipped. These tests are the
rule. Sibling of tools/update-test/, which proves the same thing through the
real updater end to end; this one proves it directly, case by case.
"""
from __future__ import annotations

import importlib.util
import os
import re
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACK = HERE.parent
TEMPLATE = PACK / "vault-template" / "CLAUDE.md"

spec = importlib.util.spec_from_file_location("patch_claude_md", HERE / "patch-claude-md.py")
engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine)

ROOT = Path(tempfile.mkdtemp(prefix="moblee-sections-", dir=os.environ.get("TMPDIR") or "/tmp"))
ROWS: list[tuple[bool, str, str]] = []

# (v0.9.4) The engine falls back to the name git keeps for a vault when a rules
# file has no sentence naming its owner. Point git at an empty configuration
# for the whole run, so the answer is the same on every machine and no real
# person's name can turn up in the output of a test. The one case that is about
# that fallback puts a name of its own in, below.
EMPTY_GITCONFIG = ROOT / "gitconfig-empty"
EMPTY_GITCONFIG.write_text("", encoding="utf-8")
os.environ["GIT_CONFIG_GLOBAL"] = str(EMPTY_GITCONFIG)
os.environ["GIT_CONFIG_NOSYSTEM"] = "1"


def check(good: bool, label: str, note: str = "") -> None:
    ROWS.append((bool(good), label, note))


def vault_with(rules: str, pages: bool = True) -> Path:
    """A throwaway wiki holding this rules file, and the four reference pages
    unless the case is about them being absent."""
    v = Path(tempfile.mkdtemp(prefix="wiki-", dir=str(ROOT)))
    ops = v / "wiki" / "Wiki Operations"
    ops.mkdir(parents=True)
    (v / "wiki" / "Index.md").write_text("# Index\n", encoding="utf-8")
    (v / "CLAUDE.md").write_text(rules, encoding="utf-8")
    if pages:
        for name in engine.REFERENCE_PAGES:
            src = PACK / "vault-template" / "wiki" / "Wiki Operations" / f"{name}.md"
            (ops / f"{name}.md").write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return v


def old_template() -> str:
    """The rules file as it stood in v0.9.3, read from the corpus fixture kept
    for the updater's own tests, so this suite needs no git."""
    return (PACK / "tools" / "update-test" / "fixtures" / "old-wiki-0.9.3" / "CLAUDE.md").read_text(encoding="utf-8")


def run(rules: str, pages: bool = True):
    v = vault_with(rules, pages)
    return engine.plan_sections(rules, v), v


# --------------------------------------------------------------------- reading
def test_normalising() -> None:
    n = engine.normalise_body
    check(n("a   \nb\n") == "a\nb", "trailing whitespace comes off every line")
    check(n("a\n\n\n\nb") == "a\n\nb", "a run of blank lines becomes one")
    check(n("\n\n a \n\n") == " a", "blank lines at either end go")
    check(engine.digest_body("a\n\n\nb  ") == engine.digest_body("a\n\nb"),
          "two bodies that differ only in whitespace have the same digest")
    check(engine.digest_body("a\nb") != engine.digest_body("a\nb\nc"),
          "one extra line is a different digest")


def test_splitting() -> None:
    text = "# T\n\nintro\n\n## One\n\nbody one\n\n## Two\n\n```\n## not a heading\n```\n"
    pre, secs = engine.split_sections(text)
    check(pre.strip() == "# T\n\nintro".strip(), "the preamble is everything above the first heading")
    check([h for h, _b in secs] == ["One", "Two"], "sections split on the ## headings")
    check("## not a heading" in secs[1][1], "a ## line inside a code fence stays in the body")


# ------------------------------------------------------------- the happy path
def test_clean_file_shrinks() -> None:
    plan, _v = run(old_template())
    check(plan.untouched == "", "a clean v0.9.3 file is not left untouched")
    check(plan.text is not None, "a clean v0.9.3 file is rewritten")
    new = (plan.text or "")
    # Not the template byte for byte: the owner's order is kept, and in v0.9.3
    # the commit section sat after House style rather than before it. Every
    # section the template has is there, saying exactly what the template says.
    want = dict(engine.split_sections(TEMPLATE.read_text(encoding="utf-8"))[1])
    got = dict(engine.split_sections(new)[1])
    check(set(got) == set(want), "it ends with exactly the sections the v0.9.4 template has",
          "extra: %s missing: %s" % (sorted(set(got) - set(want)), sorted(set(want) - set(got))))
    differ = [h for h in want if h in got
              and engine.normalise_body(got[h]) != engine.normalise_body(want[h])]
    check(not differ, "and every one of them word for word as the template has it", str(differ))
    tokens = len(new) // 4
    check(tokens < 4600, f"the result is under 4,600 tokens (it is {tokens:,})")
    check(plan.skipped == [], "nothing was skipped", ", ".join(plan.skipped))
    check(len(plan.dropped) == 11, f"eleven sections moved to a page (got {len(plan.dropped)})")
    check(("Readwise conventions", "Readwise") in plan.dropped,
          "Readwise conventions moved to the Readwise page")
    check(("Connected accounts and live facts", "Tools and Connections") in plan.dropped,
          "Connected accounts moved to the Tools and Connections page")
    check("Plain words" in plan.inserted, "the new Plain words section was added")


def test_renames() -> None:
    plan, _v = run(old_template())
    new = plan.text or ""
    check("## Three layers" in new and "## Three-layer architecture" not in new,
          "Three-layer architecture became Three layers")
    check("## Commit at the end of every piece of work" in new and "## Git commit workflow" not in new,
          "Git commit workflow became Commit at the end of every piece of work")
    check("## Tools\n" in new and "## Useful tools in this environment" not in new,
          "Useful tools in this environment became Tools")
    check("Three layers" not in plan.inserted, "a renamed section is not also added as a new one")


def test_twice_changes_nothing() -> None:
    plan, _v = run(old_template())
    again, _v2 = run(plan.text or "")
    check(again.text is None, "running the engine a second time changes nothing")
    check(again.skipped == [], "and skips nothing", ", ".join(again.skipped))


# ------------------------------------------------------------- the safety rule
OWNER_BULLET = "- **Never work on the boat accounts after nine in the evening.**"
OWNER_PARA = "The owner also wants every price written with the currency spelled out in full."
OWNER_SECTION = "## How the owner files receipts\n\nReceipts go in a folder named for the month.\n"


def owners_file() -> str:
    """A v0.9.3 template with the owner's own words in three places."""
    text = old_template()
    text = text.replace("## Hard rules\n\n", "## Hard rules\n\n" + OWNER_BULLET + "\n", 1)
    at = text.index("## Log timestamps")
    text = text[:at] + OWNER_PARA + "\n\n" + text[at:]
    return text.rstrip("\n") + "\n\n" + OWNER_SECTION


def test_owner_additions_survive() -> None:
    text = owners_file()
    plan, _v = run(text)
    out = plan.text or ""
    check(OWNER_BULLET in out, "a bullet the owner added inside Hard rules is still there")
    check(OWNER_PARA in out, "a paragraph the owner added to House style is still there")
    check("## How the owner files receipts" in out, "the owner's own section is still there")
    check("Receipts go in a folder named for the month." in out, "and so is what it said")
    check("Hard rules" in plan.skipped, "Hard rules is reported as left alone",
          ", ".join(plan.skipped))
    check("House style" in plan.skipped, "House style is reported as left alone",
          ", ".join(plan.skipped))
    check("How the owner files receipts" not in plan.skipped,
          "the owner's own section is not judged at all")
    check("Hard rules" not in plan.replaced, "Hard rules was not replaced")
    check("Session opener" in plan.replaced, "a clean section was still replaced")
    check(("Readwise conventions", "Readwise") in plan.dropped,
          "a clean section was still moved to its page")
    # nothing of the old Hard rules body was quietly trimmed
    check("Identity disambiguation in source notes" in out,
          "the whole of the section left alone is left alone")


def test_order_is_kept() -> None:
    text = old_template()
    # the owner has moved House style to the top of their file
    pre, secs = engine.split_sections(text)
    order = [h for h, _b in secs]
    moved = [order[order.index("House style")]] + [h for h in order if h != "House style"]
    body = {h: b for h, b in secs}
    text = pre + "\n" + "".join(f"## {h}\n{body[h]}" for h in moved)
    plan, _v = run(text)
    out_order = [h for h, _b in engine.split_sections(plan.text or "")[1]]
    check(out_order[0] == "House style", "a section the owner moved stays where they put it")
    check(out_order.index("Hard rules") < out_order.index("Wikilinks and structure"),
          "and the rest of their order is kept")


# ------------------------------------------------------- the whole-file guard
# ------------------------------------------- the safety rules reach every file
# Shortening and rule-keeping are two different jobs. The engine will not
# rewrite a section it does not recognise, and must not; the additive blocks
# only ever ADD, and one of the things they add is the rule that stops the
# assistant deleting anything. A file Moblee no longer recognises is the last
# file that should be left without it.
def patched_through_main(rules: str, pages: bool = True) -> str:
    """The whole script, engine and additive blocks, run over a throwaway wiki."""
    import contextlib
    import io
    v = vault_with(rules, pages)
    argv, backup = sys.argv, os.environ.get("MOBLEE_BACKUP")
    os.environ["MOBLEE_BACKUP"] = str(v.parent / "backup")
    engine.RUN_BACKUP = os.environ["MOBLEE_BACKUP"]
    sys.argv = ["patch-claude-md.py", "--vault", str(v), "--assistant", "claude"]
    try:
        with contextlib.redirect_stdout(io.StringIO()) as out:
            engine.main()
    finally:
        sys.argv = argv
        if backup is None:
            os.environ.pop("MOBLEE_BACKUP", None)
        else:
            os.environ["MOBLEE_BACKUP"] = backup
    return (v / "CLAUDE.md").read_text(encoding="utf-8") + "\n<<<SAID>>>\n" + out.getvalue()


STUB = ("# CLAUDE.md\n\nThe rules this wiki follows. This is a fixture: a rules file as it stands on an\n"
        "older wiki, before the updater has added this version's sections to it.\n\n"
        "## Habits and tools\n\nA placeholder the updater's own patcher replaces.\n")


def test_unrecognised_file_still_gets_the_safety_rules() -> None:
    plan, _v = run(STUB)
    check(plan.untouched != "", "a file Moblee does not recognise is not rewritten")
    got = patched_through_main(STUB)
    text, said = got.split("\n<<<SAID>>>\n")
    check("A placeholder the updater's own patcher replaces." in text,
          "and every word of it is still there")
    check("never deletes, empties or discards" in text,
          "but the never-delete rule is added to it all the same")
    check("Shell commands are composed plainly" in text,
          "and so is the shell rule")
    check("Any rule this" in said, "and the run says adding a rule takes nothing away")
    # (v0.9.6) A second run over the result changes nothing. At 0.9.4 it did:
    # the companion section the blocks had just written is in wording Moblee
    # once shipped, so the next run took it as proof the file was Moblee's and
    # wrote in ten sections the owner had never had, which is what this file
    # promises never to do to a file it does not recognise. The engine now
    # knows the sections its own blocks write and does not count them as
    # proof (`self_written`), so the file is left as the first run left it.
    twice, said_twice = patched_through_main(text).split("\n<<<SAID>>>\n")
    check(twice == text, "a second run changes nothing: no Moblee section is added to a file it does not recognise")
    check("None of the sections in this file" in said_twice, "and the second run says the file was left alone")


def test_skipped_section_still_gains_a_missing_rule() -> None:
    """A rule added to a section the owner has written in takes nothing of
    theirs away, so it is added."""
    text = old_template().replace(
        "## Hard rules\n\n", "## Hard rules\n\n" + OWNER_BULLET + "\n", 1)
    # their copy predates the shell rule
    shell = next(l for l in text.split("\n") if "Shell commands are composed plainly" in l)
    text = text.replace(shell + "\n", "")
    plan, _v = run(text)
    check("Hard rules" in plan.skipped, "the section they wrote in is left alone by the engine")
    out, _said = patched_through_main(text).split("\n<<<SAID>>>\n")
    check(OWNER_BULLET in out, "their bullet is still there")
    check("Shell commands are composed plainly" in out, "and the rule they were missing was added")
    check("Identity disambiguation in source notes" in out, "with the rest of the section intact")


def test_not_a_moblee_file() -> None:
    plan, _v = run("# Notes\n\n## Shopping\n\nBread.\n\n## Boats\n\nTwo of them.\n")
    check(plan.text is None, "a file that is not Moblee's is not rewritten")
    check(plan.untouched != "", "and the run says why")
    check(plan.skipped == [], "with no section named as skipped")


def test_every_section_drifted() -> None:
    text = old_template().replace("\n\n", "\n\nThe owner has been here.\n\n")
    plan, _v = run(text)
    check(plan.text is None, "a file whose every section has been edited is left untouched")
    check(plan.untouched != "", "and the run says why")


def test_drop_held_back_without_the_page() -> None:
    plan, _v = run(old_template(), pages=False)
    check(plan.dropped == [], "nothing is dropped while the pages it moves to are absent")
    check(len(plan.held_back) == 11, f"and all eleven are held back (got {len(plan.held_back)})")
    check("## Readwise conventions" in (plan.text or ""), "the content is still in the file")
    check("Session opener" in plan.replaced, "the replacements still happen")


def test_missing_section_is_added() -> None:
    text = old_template()
    pre, secs = engine.split_sections(text)
    keep = [(h, b) for h, b in secs if h != "Hard rules"]
    text = pre + "\n" + "".join(f"## {h}\n{b}" for h, b in keep)
    plan, _v = run(text)
    out_order = [h for h, _b in engine.split_sections(plan.text or "")[1]]
    check("Hard rules" in plan.inserted, "a section the file did not have is added")
    check(out_order.index("Hard rules") == out_order.index("House style") + 1,
          "and it lands beside the section it belongs after")


# --------------------------------------------- the sentence that names the owner
# (v0.9.4) The rules file Moblee ships says "[Your Name]"; the installer writes
# the owner's own name over it, so an installed file and the file Moblee
# shipped differ by that name alone. Until this version the engine read that
# difference as the owner having written in the section, reported it to them as
# theirs, and never shortened it; the fix before that took the name out of the
# shipped file altogether, which left every new owner's rules file naming
# nobody. Both faults are what these cases are for.
OWNER = "Tom & Sam"          # an ampersand, because that is what the installer's escaping turns on
OTHER_OWNER = "Ada Marsh"    # a plain name, for the case where git is the only source

# Copied, deliberately, rather than imported: these are two other things that
# read the owner's name out of this file, and a test that shared a pattern with
# them could not catch the pattern itself drifting.
#   scripts/add-identity.py, which fills wiki/Identity.md
ADD_IDENTITY = re.compile(r"knowledge base for (.+?) where (?:Claude|the assistant) is the maintainer")
#   the clinic check-up, which greps the file line by line
CLINIC_GREP = re.compile(r"personal knowledge base for [^*]* where")


def installed_file(name: str) -> str:
    """A v0.9.3 rules file as it stands on a real wiki: the placeholder gone,
    the owner's name in its place, exactly as the installer leaves it."""
    return old_template().replace("[Your Name]", name)


def clinic_reads(text: str) -> str | None:
    """What the clinic's grep would pull out of this file: the first line that
    matches, and only the matching part of it."""
    for line in text.split("\n"):
        found = CLINIC_GREP.search(line)
        if found:
            return found.group(0)
    return None


def test_the_shipped_file_names_its_owner() -> None:
    text = TEMPLATE.read_text(encoding="utf-8")
    check("personal knowledge base for [Your Name] where the assistant is the maintainer" in text,
          "the shipped rules file still has the sentence naming its owner")
    check(clinic_reads(text) == "personal knowledge base for [Your Name] where",
          "the clinic check-up can still find that sentence", str(clinic_reads(text)))
    filled = text.replace("[Your Name]", OWNER)
    found = ADD_IDENTITY.search(filled)
    check(found is not None and found.group(1) == OWNER,
          "and add-identity.py can still read the name back out once it is filled in")


def test_an_installed_name_is_not_mistaken_for_an_edit() -> None:
    plan, _v = run(installed_file(OWNER))
    out = plan.text or ""
    check("What this repository is" not in plan.skipped,
          "an owner's own name in the section is not read as the owner having written in it",
          ", ".join(plan.skipped))
    check("What this repository is" in plan.replaced,
          "so the section is brought up to date like any other", ", ".join(plan.replaced))
    check(f"knowledge base for {OWNER} where the assistant is the maintainer" in out,
          "and their name, ampersand and all, is still in the file afterwards")
    check("[Your Name]" not in out, "with no placeholder left where their name was")
    found = ADD_IDENTITY.search(out)
    check(found is not None and found.group(1) == OWNER,
          "add-identity.py can still read the name out of the patched file",
          str(found.group(1)) if found else "no match")
    check(clinic_reads(out) == f"personal knowledge base for {OWNER} where",
          "and so can the clinic check-up", str(clinic_reads(out)))
    plain = run(installed_file(OTHER_OWNER))[0].text or ""
    check(f"knowledge base for {OTHER_OWNER} where" in plain,
          "a name with nothing special in it comes through the same way")
    again, _v2 = run(out)
    check(again.text is None, "and running the engine again over the result changes nothing")
    check(again.skipped == [], "and still skips nothing", ", ".join(again.skipped))


def test_the_name_survives_the_whole_script() -> None:
    out, _said = patched_through_main(installed_file(OWNER)).split("\n<<<SAID>>>\n")
    check(f"knowledge base for {OWNER} where" in out,
          "the name is still there after the blocks have run as well")
    check("[Your Name]" not in out, "and nothing put the placeholder back")


def test_a_section_the_owner_wrote_in_is_still_left_alone() -> None:
    """Name-blind is not edit-blind: a real addition still stops the rewrite."""
    text = installed_file(OWNER).replace(
        "See `wiki/Karpathy",
        "The boat papers are in here too. See `wiki/Karpathy", 1)
    plan, _v = run(text)
    out = plan.text or ""
    check("What this repository is" in plan.skipped,
          "a section the owner has written in is reported as theirs", ", ".join(plan.skipped))
    check("The boat papers are in here too." in out, "and their sentence is still there")
    check("Session opener" in plan.replaced, "while the sections they left alone are still updated")


def test_a_file_that_never_had_a_name_put_in() -> None:
    """An install where nobody typed a name leaves the placeholder in the file.
    Nothing crashes, and no name is invented to fill it."""
    plan, _v = run(old_template())
    out = plan.text or ""
    check("What this repository is" in plan.replaced,
          "the section is still brought up to date", ", ".join(plan.replaced))
    check("knowledge base for [Your Name] where the assistant is the maintainer" in out,
          "and the placeholder is left exactly as it is")


def test_git_supplies_the_name_when_the_sentence_is_gone() -> None:
    """The one case the file itself cannot answer: the section is missing
    altogether, so the engine writes it from scratch and has nowhere to read
    the name from but the vault's own git settings."""
    text = installed_file(OWNER)
    pre, secs = engine.split_sections(text)
    text = pre + "\n" + "".join(f"## {h}\n{b}" for h, b in secs if h != "What this repository is")
    conf = ROOT / "gitconfig-with-a-name"
    conf.write_text(f"[user]\n\tname = {OTHER_OWNER}\n", encoding="utf-8")
    os.environ["GIT_CONFIG_GLOBAL"] = str(conf)
    try:
        plan, _v = run(text)
    finally:
        os.environ["GIT_CONFIG_GLOBAL"] = str(EMPTY_GITCONFIG)
    out = plan.text or ""
    check("What this repository is" in plan.inserted, "the missing section is written in")
    check(f"knowledge base for {OTHER_OWNER} where" in out,
          "carrying the name git keeps for the vault")


def test_blanking_only_touches_the_owner_sentence() -> None:
    b = engine.blank_owner_name
    real = "a personal knowledge base for Tom & Sam where the assistant is the maintainer."
    check(b(real) == "a personal knowledge base for [Your Name] where the assistant is the maintainer.",
          "the owner's name is put back to the placeholder before a body is digested")
    check(b(b(real)) == b(real), "and doing it twice gives the same answer as doing it once")
    old_words = "a knowledge base for Tom where Claude is the maintainer."
    check(b(old_words) == "a knowledge base for [Your Name] where Claude is the maintainer.",
          "the older wording, which said Claude by name, is blanked too")
    for prose in (
        "This is a knowledge base for boats. The assistant is the maintainer of it.",
        "A knowledge base for the whole family, where everyone writes things down.",
        "The shed is where the assistant is the maintainer of nothing at all.",
        "a knowledge base for\nTom & Sam where the assistant is the maintainer",
    ):
        check(b(prose) == prose, "ordinary prose is left alone: " + prose.split("\n")[0][:46])
    long_line = ("a knowledge base for the boats, the accounts, the club, the crossings and "
                 "everything else the owner keeps, where the assistant is the maintainer")
    check(b(long_line) == long_line,
          "and a whole line of prose between the two halves is too long to be a name")
    check(engine.digest_body("a personal knowledge base for Tom & Sam where the assistant is the maintainer.")
          == engine.digest_body("a personal knowledge base for [Your Name] where the assistant is the maintainer."),
          "so an owner's body and the body Moblee shipped come to the same digest")
    check(engine.digest_body("a knowledge base for Tom where the assistant is the maintainer. And more.")
          != engine.digest_body("a knowledge base for Tom where the assistant is the maintainer."),
          "while an added sentence is still a different digest")


# ------------------------------------------------- the pages the content moves to
# scripts/add-reference-pages.py is the other half of this: the updater runs it
# first, and a section may only be dropped once the page carrying it is there.
pages_spec = importlib.util.spec_from_file_location("add_reference_pages", HERE / "add-reference-pages.py")
pages_mod = importlib.util.module_from_spec(pages_spec)
pages_spec.loader.exec_module(pages_mod)


def add_pages_to(vault: Path) -> tuple[int, str]:
    import contextlib
    import io
    argv = sys.argv
    sys.argv = ["add-reference-pages.py", "--vault", str(vault)]
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            rc = pages_mod.main()
    finally:
        sys.argv = argv
    return rc, buf.getvalue().strip()


def index_lines(vault: Path) -> list[str]:
    return [l.rstrip() for l in (vault / "wiki" / "Index.md").read_text(encoding="utf-8").splitlines()
            if l.startswith("- Wiki Operations")]


def bare_vault() -> Path:
    v = vault_with(old_template(), pages=False)
    (v / "wiki" / "Index.md").write_text(
        "# Index\n\n## Domains\n\n- Golf: [[Golf]] (rounds)\n\n## Subfolder pages\n\n"
        "- Wiki Operations: [[Assistant Memory]] (what the assistant remembers)\n", encoding="utf-8")
    return v


def test_pages_arrive() -> None:
    v = bare_vault()
    rc, out = add_pages_to(v)
    check(rc == 0, "the four pages are added", out)
    for name in engine.REFERENCE_PAGES:
        check((v / "wiki" / "Wiki Operations" / f"{name}.md").is_file(), f"the {name} page is there")
    check(len(index_lines(v)) == 1, "the Index keeps one Wiki Operations line", str(index_lines(v)))
    check(all(f"[[{n}]]" in index_lines(v)[0] for n in engine.REFERENCE_PAGES),
          "and that line links all four", str(index_lines(v)))


def test_pages_are_never_overwritten() -> None:
    v = bare_vault()
    add_pages_to(v)
    mine = v / "wiki" / "Wiki Operations" / "Readwise.md"
    mine.write_text("# Readwise\n\nThe owner rewrote this page entirely.\n", encoding="utf-8")
    rc, out = add_pages_to(v)
    check(rc == 0, "a second run is clean", out)
    check("The owner rewrote this page entirely." in mine.read_text(encoding="utf-8"),
          "a page the owner has edited is never overwritten")
    check(len(index_lines(v)) == 1, "and the Index still keeps one Wiki Operations line")


def test_no_link_to_a_page_that_is_not_there() -> None:
    """The pack's commit gate refuses a commit that adds a dangling wikilink, so
    a page that could not be copied must not be linked either."""
    v = bare_vault()
    ops = v / "wiki" / "Wiki Operations"
    ops.chmod(0o500)
    try:
        rc, out = add_pages_to(v)
    finally:
        ops.chmod(0o700)
    check(rc != 0, "a run that cannot copy the pages says so", out)
    line = index_lines(v)[0] if index_lines(v) else ""
    check(not any(f"[[{n}]]" in line for n in engine.REFERENCE_PAGES),
          "and adds no link to a page that is not there", line)


def test_a_page_of_the_owners_own_blocks_the_name() -> None:
    """(v0.9.4) The owner already keeps a page called Readwise of their own.

    Matching by filename alone, as the first version of this script did, could
    not tell that page from Moblee's: it saw the name, took Moblee's page as
    present, wrote nothing, said it had added four pages when it had added
    three, and put [[Readwise]] on the Index, where it now pointed the assistant
    at a page of the owner's that has nothing to do with how Moblee ingests a
    Readwise feed. Nothing was lost, and nothing said anything was wrong."""
    v = bare_vault()
    mine = v / "wiki" / "Readwise.md"
    mine.write_text("# Readwise\n\nThe owner's own notes about the app.\n", encoding="utf-8")
    rc, out = add_pages_to(v)
    check(rc != 0, "a name the owner has already used stops the run", out)
    check("already has a page called Readwise" in out, "and the run says which name", out)
    check("wiki/Readwise.md" in out, "and where the owner's page is", out)
    check("Rename one of the two" in out, "and what to do about it", out)
    check("four" not in out, "and claims nothing about four pages", out)
    check(mine.read_text(encoding="utf-8").startswith("# Readwise\n\nThe owner's own"),
          "the owner's page is not touched")
    check(not (v / "wiki" / "Wiki Operations" / "Readwise.md").exists(),
          "Moblee's page of that name is not written beside it")
    line = index_lines(v)[0] if index_lines(v) else ""
    check("[[Readwise]]" not in line, "the Index is not pointed at the owner's page", line)
    check(all(f"[[{n}]]" in line for n in ("Wiki Conventions", "Git and Commits",
                                           "Tools and Connections")),
          "while the three that are really there are linked", line)
    # and the half of the pair that matters: the rules file keeps the section
    # whose content would have gone to the page that was not written.
    plan = engine.plan_sections((v / "CLAUDE.md").read_text(encoding="utf-8"), v)
    check(("Readwise conventions", "Readwise") in plan.held_back,
          "so the rules file keeps the section that would have moved there",
          str(plan.held_back))
    check("## Readwise conventions" in (plan.text or ""), "word for word")


def test_the_clash_clears_when_the_owner_renames_their_page() -> None:
    v = bare_vault()
    (v / "wiki" / "Readwise.md").write_text("# Readwise\n\nMine.\n", encoding="utf-8")
    add_pages_to(v)
    (v / "wiki" / "My Readwise Notes.md").write_text("# My Readwise Notes\n\nMine.\n",
                                                     encoding="utf-8")
    (v / "wiki" / "Readwise.md").rename(v / "wiki" / "renamed-away.txt")
    rc, out = add_pages_to(v)
    check(rc == 0, "once the owner renames their page the run is clean", out)
    check((v / "wiki" / "Wiki Operations" / "Readwise.md").is_file(),
          "and Moblee's page arrives")
    line = index_lines(v)[0] if index_lines(v) else ""
    check(line.count("[[Readwise]]") == 1, "linked from the Index exactly once", line)
    check(len(index_lines(v)) == 1, "on the one Wiki Operations line")


def test_moblees_own_page_is_not_read_as_a_clash() -> None:
    """The page at wiki/Wiki Operations/<name>.md is the one Moblee means, so a
    second run over a vault that already has all four is quiet and exits 0."""
    v = bare_vault()
    add_pages_to(v)
    rc, out = add_pages_to(v)
    check(rc == 0, "a vault that already has all four is left alone", out)
    check("already in this wiki" in out, "and says so in one line", out)


def main() -> int:
    for fn in (test_normalising, test_splitting, test_clean_file_shrinks, test_renames,
               test_twice_changes_nothing, test_owner_additions_survive, test_order_is_kept,
               test_unrecognised_file_still_gets_the_safety_rules,
               test_skipped_section_still_gains_a_missing_rule,
               test_not_a_moblee_file, test_every_section_drifted,
               test_drop_held_back_without_the_page, test_missing_section_is_added,
               test_the_shipped_file_names_its_owner,
               test_an_installed_name_is_not_mistaken_for_an_edit,
               test_the_name_survives_the_whole_script,
               test_a_section_the_owner_wrote_in_is_still_left_alone,
               test_a_file_that_never_had_a_name_put_in,
               test_git_supplies_the_name_when_the_sentence_is_gone,
               test_blanking_only_touches_the_owner_sentence,
               test_pages_arrive, test_pages_are_never_overwritten,
               test_no_link_to_a_page_that_is_not_there,
               test_a_page_of_the_owners_own_blocks_the_name,
               test_the_clash_clears_when_the_owner_renames_their_page,
               test_moblees_own_page_is_not_read_as_a_clash):
        try:
            fn()
        except Exception as exc:                      # a broken case is a failure, not a crash
            check(False, f"{fn.__name__} raised {type(exc).__name__}", str(exc)[:120])
    width = max(len(label) for _g, label, _n in ROWS)
    for good, label, note in ROWS:
        line = f"{'ok  ' if good else 'FAIL'}  {label:<{width}}"
        if note and not good:
            line += "   " + note
        print(line)
    bad = sum(1 for g, _l, _n in ROWS if not g)
    print("")
    print(f"section engine: {len(ROWS) - bad} checks passed, {bad} failed")
    print(f"scratch kept: {ROOT}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
