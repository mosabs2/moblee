#!/usr/bin/env python3
"""
Tests for scripts/moblee-doctor.py, the read-only check-up.

    python3 tools/test-doctor.py

The groups:

  privacy   The sweep for secrets left in a wiki, run against a practice wiki
            full of invented, obviously-fake secrets, in BOTH layouts a Moblee
            wiki comes in (Claude's CLAUDE.md, and ChatGPT's AGENTS.md with
            CLAUDE.md as a link to it). The hard one: not one character of any
            planted secret may appear in the plain output, in the JSON, or in
            the report file.
  shape     The wallet-phrase detector in both of its layers: the word-list-free
            one measured against real writing (the pack's own docs/ and
            README.md) for false alarms, and both of them against phrases of the
            shape they are meant to catch, Title Case included.
  value     What the "put yours here" filter is allowed to read. It is the
            matched value and nothing else: a secret quoted in a page, or with
            the word "your" beside it, is still a secret.
  files     Which files the sweep will open, the ones a private key is really
            kept in among them.
  accepted  The owner's own note saying a finding was looked at and kept, and
            how forgivingly it is matched.
  rules     What the check-up says about the length of the rules file, and
            whether what it says is true of the file in front of it.
  weights   The size of the always-loaded files, said once and not twice.
  report    The report that must name nobody, and must still read as English.
  card      The one-screen health card a helping relative is handed: that it
            fits one screen whatever is wrong, that it counts what it does not
            show instead of dropping it, that it carries the report's own
            redaction so no page title or secret is on it, that it never calls a
            wiki healthy when something could not be checked, and — over every
            mixture of finding levels there is — that it cannot contradict the
            findings it was built from.
  app       Which copy of the Moblee app was found, and its version.
  leftovers The old pack folders, backup folders and scratch wikis that Moblee
            keeps for ever, counted and sized, with the live pack left out, and
            a count that was cut short told apart from one that finished.
  timeout   The limit on the guard proof, taken from PROVE_TIMEOUT rather than
            typed out, with a stub agent on PATH that forks a child of its own,
            so that the killing of the whole process group is really run and not
            merely assumed.

Everything is built under $TMPDIR. Nothing is deleted, here or anywhere: the
practice wikis are left where they are (a few kilobytes) and named at the end.
The only processes this ends are the stub agents it started itself.

Prints a pass/fail table and exits non-zero on any failure.
"""
import contextlib
import datetime
import importlib.util
import io
import json
import os
import plistlib
import re
import stat
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACK = HERE.parent
DOCTOR = PACK / "scripts" / "moblee-doctor.py"

ROWS = []
FAILURES = 0


def check(group, label, passed, note=""):
    global FAILURES
    if not passed:
        FAILURES += 1
    ROWS.append(("PASS" if passed else "FAIL", group, label, note))
    return passed


def load_doctor():
    """The check-up is loaded as a module rather than started as a program: the
    vault safety guard refuses to run it from a shell (it starts and stops a
    process group, which reads as a deletion primitive), and importing it runs
    exactly the same code."""
    spec = importlib.util.spec_from_file_location("moblee_doctor", DOCTOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ----------------------------------------------------------------- the secrets
# Every one of these is invented for this test and is not, and never was, a
# working secret anywhere. Each is written so that its shape matches what the
# sweep looks for while its content says plainly that it is a fake.
#
# The key of each pair is the KIND the sweep should call it. The value is the
# run of characters that must never, ever be printed.
PLANTED = {
    "a private key": "-----BEGIN OPENSSH PRIVATE KEY-----",
    "an Amazon cloud access key": "AKIAQQQQFAKEFAKE0000",
    "a GitHub token": "ghp_FAKEfake0000000000000000000000000000",
    "a key for Claude": "sk-ant-FAKEfake000000000000000000000000",
    "a Slack token": "xoxb-0000000000-0000000000-FAKEfake0000",
    # 39 characters, which is the length of the real thing, and ending in a dash,
    # which the real thing is allowed to do: the fake was 38 long and so matched
    # nothing, and a dash at the end used to slip past the check as well.
    "a Google key": "AIzaFAKEfake000000000000000000FAKEfake-",
    "a sign-in token": "eyJhbGciOiJub25lIn0.eyJmYWtlIjoieWVzIn0.QUZBS0VGQUtF",
    "a password or key written into a setting": "notarealpassword7",
    "a run of words shaped like a wallet recovery phrase":
        "wibble wobble tundra marmot kipper pylon thistle gherkin walrus bramble nimbus quartz",
}
# The body of the private key, kept apart so the test can also insist that the
# lines between the markers never reach the output either.
KEY_BODY = "QUZBS0VGQUtFRkFLRUZBS0VGQUtFRkFLRUZBS0VGQUtFRkFLRQ=="


def practice_pages():
    """The pages of the practice wiki, with one planted secret each."""
    return {
        "wiki/Index.md": "# Index\n\nA practice wiki.\n",
        "wiki/Keys.md": (
            "# Keys\n\nThis page is a test fixture. Nothing on it is real.\n\n"
            "```\n" + PLANTED["a private key"] + "\n" + KEY_BODY + "\n"
            "-----END OPENSSH PRIVATE KEY-----\n```\n"),
        "wiki/Cloud.md": (
            "# Cloud\n\nThe store card reads " + PLANTED["an Amazon cloud access key"] + " today.\n"),
        "wiki/Code.md": (
            "# Code\n\nToken on record: " + PLANTED["a GitHub token"] + "\n\n"
            "Assistant token: " + PLANTED["a key for Claude"] + "\n"),
        "wiki/Chat.md": (
            "# Chat\n\nTeam token " + PLANTED["a Slack token"] + " and map key "
            + PLANTED["a Google key"] + " were pasted in here.\n"),
        "wiki/Sign in.md": (
            "# Sign in\n\nThe web token it handed back was\n"
            + PLANTED["a sign-in token"] + "\n"),
        "settings.json": '{\n  "password": "' + PLANTED["a password or key written into a setting"] + '"\n}\n',
        "wiki/Wallet.md": (
            "# Wallet\n\nWritten down by the assistant, which it should never have done:\n\n"
            + PLANTED["a run of words shaped like a wallet recovery phrase"] + "\n"),
        "wiki/Quiet.md": (
            "# Quiet\n\nA page with nothing in it worth finding. It talks about a "
            "password in the ordinary way, and about api keys, without giving one.\n"),
    }


def build_wiki(root, layout):
    """A practice wiki with planted secrets, in one of the two layouts."""
    rules = ("# Practice wiki\n\nRules for a practice wiki. Nothing here is real.\n"
             + ("x" * 400) + "\n")
    root.mkdir(parents=True, exist_ok=True)
    (root / "VERSION").write_text("0.9.4\n")
    for rel, text in practice_pages().items():
        page = root / rel
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text(text)
    if layout == "claude":
        (root / "CLAUDE.md").write_text(rules)
    else:
        (root / "AGENTS.md").write_text(rules)
        os.symlink(root / "AGENTS.md", root / "CLAUDE.md")
    return root


# ------------------------------------------------------------------- the sweep
def run_doctor(doctor, argv):
    """One run of the check-up as a person meets it, argv and all. (exit code,
    everything it printed). Run in this process rather than started as a program,
    because the vault safety guard will not let the script be started from a
    shell; importing it runs exactly the same code."""
    buf = io.StringIO()
    old = sys.argv
    sys.argv = ["moblee-doctor.py"] + list(argv)
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
            code = doctor.main()
    finally:
        sys.argv = old
    return code, buf.getvalue()


def run_checkup(doctor, vault, assistant, report=False, card=False):
    """The whole check-up, as an owner meets it: the plain output, the JSON, the
    report file, and the one-screen card a helper is shown."""
    out = {}
    where = ["--vault", str(vault), "--assistant", assistant]
    out["plain"] = run_doctor(doctor, where)[1]
    out["json"] = run_doctor(doctor, where + ["--json"])[1]
    if card:
        out["card"] = run_doctor(doctor, where + ["--card"])[1]
        out["card-json"] = run_doctor(doctor, where + ["--card", "--json"])[1]
    if report:
        run_doctor(doctor, where + ["--report"])
        written = sorted((vault / "outputs").glob("moblee-report-*.md"))
        out["report"] = written[-1].read_text() if written else ""
        out["report-path"] = str(written[-1]) if written else ""
    return out


def fragments_of(secret):
    """A secret's own characters, whole and in pieces. A sweep that printed any
    one of these would have given the secret away."""
    pieces = [secret]
    stripped = secret.strip()
    if len(stripped) >= 16:
        pieces += [stripped[:12], stripped[-12:], stripped[len(stripped) // 2 - 6:len(stripped) // 2 + 6]]
    return [p for p in pieces if len(p) >= 8]


def test_privacy(doctor, work):
    for layout in ("claude", "chatgpt"):
        vault = build_wiki(work / f"wiki-{layout}", layout)
        out = run_checkup(doctor, vault, "claude" if layout == "claude" else "chatgpt", report=True)
        everything = out["plain"] + out["json"] + out["report"]
        rows = json.loads(out["json"])
        privacy = [r for r in rows if r.get("guide") in ("F41", "F42")]
        text = " ".join(r["text"] for r in privacy)

        # every planted kind is named, with a file and a line
        for kind in PLANTED:
            named = re.search(re.escape(": " + kind) + r"(\b|$)", text) is not None
            check("privacy", f"{layout}: the sweep names {kind}", named)
        lines_given = len(re.findall(r"\bline \d+: ", text))
        check("privacy", f"{layout}: every finding carries a file and a line number",
              lines_given >= len(PLANTED), f"{lines_given} findings with a line")

        # the levels: a live secret is a PROBLEM, a thing worth a look is a LOOK
        levels = {r["guide"]: r["level"] for r in privacy}
        check("privacy", f"{layout}: a live secret is reported at PROBLEM, with code F41",
              levels.get("F41") == "PROBLEM")
        check("privacy", f"{layout}: a thing worth a look is reported at LOOK, with code F42",
              levels.get("F42") == "LOOK")

        # THE ONE THAT MATTERS: no secret, and no piece of one, anywhere
        leaked = []
        for kind, secret in list(PLANTED.items()) + [("the private key's body", KEY_BODY)]:
            for piece in fragments_of(secret):
                if piece in everything:
                    leaked.append(f"{kind}: {piece[:16]}")
        check("privacy", f"{layout}: no planted secret, whole or in pieces, reaches the output, the JSON or the report",
              not leaked, "; ".join(leaked[:3]))

        # the report carries no page titles, which is what it has always promised
        check("privacy", f"{layout}: the report names no page of the wiki",
              "wiki/Wallet.md" not in out["report"] and "wiki/Keys.md" not in out["report"])
        check("privacy", f"{layout}: but the screen does, so the owner can find the page",
              "wiki/Wallet.md" in out["plain"] and "wiki/Keys.md" in out["plain"])

        # the mode is said out loud, so a guess is never read as a certainty
        check("privacy", f"{layout}: the output says the wallet check is running on shape alone",
              "judged by its shape alone" in out["plain"] and "a guess and not a certainty" in out["plain"])

        # nothing was changed
        after = practice_pages()
        same = all((vault / rel).read_text() == body for rel, body in after.items())
        check("privacy", f"{layout}: every page is exactly as it was; the sweep changed nothing", same)

    # the escape hatch: a finding the owner has looked at and kept
    vault = work / "wiki-claude"
    (vault / ".moblee").mkdir(exist_ok=True)
    (vault / ".moblee" / "privacy-accepted.txt").write_text(
        "# path | kind | why\n"
        "wiki/Keys.md | a private key | a fixture, looked at and kept\n")
    f = doctor.Findings()
    doctor.check_privacy(f, vault, PACK)
    text = " ".join(r["text"] for r in f.rows)
    check("privacy", "a finding accepted after review is counted apart and not reported again",
          "wiki/Keys.md line" not in text and "looked at before and kept on purpose" in text)

    # Moblee's own folder is sometimes kept inside the wiki (outputs/moblee).
    # Its files are Moblee's, not the owner's, and one of them carries invented
    # secrets on purpose — the very file this test is written in — so reading
    # them back as the owner's would be crying wolf.
    inside = build_wiki(work / "wiki-with-pack", "claude")
    pack_in_wiki = inside / "outputs" / "moblee" / "tools"
    pack_in_wiki.mkdir(parents=True)
    (pack_in_wiki / "test-doctor.py").write_text(
        "FAKE = \"" + PLANTED["an Amazon cloud access key"] + "\"\n")
    f = doctor.Findings()
    doctor.check_privacy(f, inside, inside / "outputs" / "moblee")
    text = " ".join(r["text"] for r in f.rows)
    check("privacy", "Moblee's own folder, kept inside the wiki, is stepped over and not read back at the owner",
          "outputs/moblee/tools/test-doctor.py" not in text)
    check("privacy", "and the sweep says out loud that it stepped over it, so nothing is skipped in silence",
          "is inside the wiki and was stepped over" in text)
    check("privacy", "the owner's own pages are still read: the sweep did not simply stop",
          "wiki/Keys.md line" in text)

    # the git remote, said honestly
    f = doctor.Findings()
    doctor.check_privacy(f, vault, PACK)
    remote_rows = [r for r in f.rows if "history is sent" in r["text"]]
    check("privacy", "a wiki with no git remote is told so plainly",
          len(remote_rows) == 1 and "stays on this Mac" in remote_rows[0]["text"])
    # With no git on the Mac at all the question is open, and an open question
    # must not be answered "no": the wiki may well be in git and sent somewhere.
    was_path = os.environ.get("PATH", "")
    empty = work / "no-git-here"
    empty.mkdir(exist_ok=True)
    f = doctor.Findings()
    try:
        os.environ["PATH"] = str(empty)
        doctor.check_privacy(f, vault, PACK)
    finally:
        os.environ["PATH"] = was_path
    said = " ".join(r["text"] for r in f.rows)
    check("privacy", "with no git on the Mac the question is left open, not answered \"no\"",
          "could not be read from git" in said and "stays on this Mac" not in said)

    f = doctor.Findings()
    doctor.check_privacy(f, PACK, PACK)
    remote_rows = [r for r in f.rows if "history is sent to" in r["text"]]
    said = remote_rows[0]["text"] if remote_rows else ""
    check("privacy", "a wiki with a remote is given the host, the risk, and no claim to know",
          bool(remote_rows) and remote_rows[0]["guide"] == "F43"
          and "does not know" in said and "can be read by anyone" in said,
          said[:70])


# ------------------------------------------------------------------- the shape
PROSE_WORDS = ["wibble", "wobble", "tundra", "marmot", "kipper", "pylon",
               "thistle", "gherkin", "walrus", "bramble", "nimbus", "quartz"]


def test_shape(doctor):
    corpus = sorted((PACK / "docs").glob("*.md")) + [PACK / "README.md"]
    hits, lines = 0, 0
    for page in corpus:
        body = page.read_text(errors="replace")
        lines += body.count("\n")
        hits += len(doctor.privacy_phrase_lines(body.lower(), set()))
    check("shape", "no false alarm on the pack's own writing (docs/*.md and README.md)",
          hits == 0, f"{len(corpus)} files, {lines} lines, {hits} hits")

    twelve = " ".join(PROSE_WORDS)
    check("shape", "twelve plain words alone on a line are caught",
          doctor.privacy_phrase_lines("# A page\n\n" + twelve + "\n", set()) == [3])
    check("shape", "twenty-four are caught too",
          doctor.privacy_phrase_lines(twelve + " " + twelve + "\n", set()) == [1])
    numbered = "\n".join(f"{i + 1}. {w}" for i, w in enumerate(PROSE_WORDS))
    check("shape", "a numbered list of twelve words is caught",
          doctor.privacy_phrase_lines(numbered + "\n", set()) == [1])
    check("shape", "a word of one or two letters in the run ends it",
          doctor.privacy_phrase_lines(" ".join(PROSE_WORDS[:6] + ["of"] + PROSE_WORDS[6:]) + "\n", set()) == [])
    check("shape", "a comma or a full stop in the run ends it",
          doctor.privacy_phrase_lines(" ".join(PROSE_WORDS[:5]) + ", " + " ".join(PROSE_WORDS[5:]) + "\n", set()) == [])
    check("shape", "twelve words inside a sentence are not a phrase, because a phrase is written on its own",
          doctor.privacy_phrase_lines("and then " + twelve + " came along.\n", set()) == [])
    check("shape", "thirteen words in a row are ordinary writing, not a phrase",
          doctor.privacy_phrase_lines(twelve + " onwards\n", set()) == [])
    # A run may be gathered from several lines, so a program's opening lines add
    # up to twelve words of the right shape. The word said over and over is what
    # gives them away.
    opening = "import stat\nimport sys\nimport tempfile\nimport time\nfrom pathlib import path\n"
    check("shape", "a program's opening lines add up to twelve words but are not a phrase",
          doctor.privacy_phrase_lines(opening, set()) == [],
          f"{len(opening.split())} words on {opening.count(chr(10))} lines")
    check("shape", "a word said twice is still allowed, because a phrase may repeat one",
          doctor.privacy_phrase_lines(" ".join(PROSE_WORDS[:11] + ["quartz"]) + "\n", set()) == [1])

    # with a word list present the exact check runs instead, and it is the one
    # that decides: words outside the list are not a phrase, however they look.
    words = set(PROSE_WORDS) | {f"word{n:04d}" for n in range(2048 - len(PROSE_WORDS))}
    check("shape", "with a word list, a run of list words inside a sentence IS caught",
          doctor.privacy_phrase_lines("and then " + twelve + " came along.\n", words) == [1])
    check("shape", "with a word list, words that are not in it are not a phrase",
          doctor.privacy_phrase_lines(
              " ".join(f"notaword{n}" for n in range(12)) + "\n", words) == [])

    # (v0.9.4) A phrase written in Title Case, which is how a phone or a wallet
    # app often shows one and how somebody copying it out often writes it. The
    # shape layer lower-cased the page before reading it; the exact layer did
    # not, so putting the 2,048-word list on the Mac LOST this detection
    # outright — while the check-up said in the same breath that the
    # wallet-phrase check was now exact. Both layers must find it.
    title = " ".join(w.capitalize() for w in PROSE_WORDS)
    page = "# A page\n\n" + title + "\n"
    check("shape", "a Title-Case phrase is caught by the shape check",
          doctor.privacy_in_file(page, set())
          == [("review", "a run of words shaped like a wallet recovery phrase", 3)],
          str(doctor.privacy_in_file(page, set())))
    check("shape", "and by the exact check too, so installing the word list never loses a finding",
          doctor.privacy_in_file(page, words) == [("critical", "a wallet recovery phrase", 3)],
          str(doctor.privacy_in_file(page, words)))
    check("shape", "a lowercase phrase is unaffected by that",
          doctor.privacy_in_file("# A page\n\n" + twelve + "\n", words)
          == [("critical", "a wallet recovery phrase", 3)])
    check("shape", "and a Title-Case run of words that are NOT in the list is still not a phrase",
          doctor.privacy_in_file(
              "# A page\n\n" + " ".join(f"Notaword{n}" for n in range(12)) + "\n", words) == [])

    # a list that is not 2,048 words long is not the list, and is not used
    empty, where = doctor.privacy_wordlist(PACK, PACK)
    check("shape", "with no 2,048-word list on this Mac, the exact check is off and says so",
          empty == set() and where is None)


# --------------------------------------------------------------------- the app
def make_app(path, version, build):
    (path / "Contents").mkdir(parents=True)
    plist = {"CFBundleName": "Moblee", "CFBundleShortVersionString": version}
    if build:
        plist["CFBundleVersion"] = build
    (path / "Contents" / "Info.plist").write_bytes(plistlib.dumps(plist))


def test_app(doctor, work):
    home = work / "home-app"
    apps = home / "Applications"
    make_app(apps / "Moblee.app", "0.9.4", "7")
    make_app(apps / "Utilities" / "Moblee.app", "0.8.1", "0.8.1")
    make_app(apps / "Extras" / "More" / "Moblee.app", "0.7.0", None)
    (apps / "Broken.app" / "Contents").mkdir(parents=True)
    was = doctor.HOME
    try:
        doctor.HOME = home
        found = [p for p in doctor.moblee_apps() if str(p).startswith(str(home))]
        versions = [doctor.app_version(p) for p in found]
    finally:
        doctor.HOME = was
    check("app", "every copy of the app is found, at all three depths, and its path kept",
          len(found) == 3, ", ".join(p.name for p in found))
    check("app", "the version and the build are read from each copy's own Info.plist",
          versions == ["version 0.9.4 (build 7)", "version 0.8.1", "version 0.7.0"],
          "; ".join(versions))
    check("app", "a bundle with no Info.plist is not guessed at",
          doctor.app_version(apps / "Broken.app") == "version unknown")

    # and the line an owner reads: which copy, and which version, with the home
    # folder written as ~ so a report carries no account name.
    f = doctor.Findings()
    was_home, was_config = doctor.HOME, doctor.CONFIG
    try:
        doctor.HOME = home
        doctor.CONFIG = home / ".config" / "moblee"
        (home / ".config" / "moblee").mkdir(parents=True, exist_ok=True)
        pack = home / "Library" / "Application Support" / "Moblee" / "pack-0.9.4"
        (pack / "scripts").mkdir(parents=True)
        (pack / "scripts" / "install.sh").write_text("#!/bin/bash\necho hi\n")
        (home / ".config" / "moblee" / "package-path").write_text(str(pack) + "\n")
        doctor.check_mac(f, "claude")
    finally:
        doctor.HOME, doctor.CONFIG = was_home, was_config
    said = next((r["text"] for r in f.rows if "Moblee app" in r["text"]), "")
    check("app", "the check-up says how many copies there are, and names each with its version",
          "3 copies" in said and "version 0.9.4 (build 7)" in said and "version 0.8.1" in said, said[:90])
    check("app", "and writes the home folder as ~, so a report carries no account name",
          str(home) not in said and "~/Applications/Moblee.app" in said)


# --------------------------------------------------------------- the leftovers
def test_leftovers(doctor, work):
    home = work / "home-left"
    support = home / "Library" / "Application Support" / "Moblee"
    live = support / "pack-0.9.4"
    for name in ("pack-0.9.2", "pack-0.9.3", "pack-0.9.4"):
        (support / name / "scripts").mkdir(parents=True)
        (support / name / "scripts" / "install.sh").write_text("x" * 5000)
    config = home / ".config" / "moblee"
    for stamp in ("20260901-101010", "20260902-101010", "20260903-101010"):
        (config / "backups" / stamp).mkdir(parents=True)
        (config / "backups" / stamp / "settings.json").write_text("y" * 2000)
    (config / "prove-guard" / "20260904-101010" / "wiki").mkdir(parents=True)
    (config / "prove-guard" / "20260904-101010" / "wiki" / "page.md").write_text("z" * 100)

    f = doctor.Findings()
    was_home, was_config = doctor.HOME, doctor.CONFIG
    try:
        doctor.HOME, doctor.CONFIG = home, config
        doctor.check_leftovers(f, live)
    finally:
        doctor.HOME, doctor.CONFIG = was_home, was_config
    said = next((r["text"] for r in f.rows if "keeps what it replaces" in r["text"]), "")
    check("leftovers", "all three families are counted and named", bool(said), said[:70])
    check("leftovers", "the pack in use is left out of the count, because removing it would break the install",
          "2 old pack folder(s)" in said, said[:120])
    check("leftovers", "the backup folders are counted", "3 backup folder(s)" in said)
    check("leftovers", "the scratch wikis from guard proofs are counted", "1 scratch wiki folder(s)" in said)
    check("leftovers", "how much room they take is given, for each family and in all",
          said.count("about ") >= 4 and re.search(r"about \d+ (KB|MB|GB) in all", said) is not None)
    check("leftovers", "it says Moblee never removes them and the owner may, by hand",
          "Moblee never removes these" in said and "remove them by hand" in said)
    check("leftovers", "it is not raised as a fault, so a tidy Mac is not told it has a problem",
          next(r["level"] for r in f.rows if "keeps what it replaces" in r["text"]) == doctor.OK)
    check("leftovers", "nothing was removed", live.is_dir() and (support / "pack-0.9.2").is_dir()
          and len(list((config / "backups").iterdir())) == 3)
    check("leftovers", "and the owner is told the copy in use was left out",
          "The copy of Moblee in use is not among them." in said)

    # With no record of which pack folder is in use, every one of them is
    # counted, so the line must not promise that the one in use was left out.
    f = doctor.Findings()
    try:
        doctor.HOME, doctor.CONFIG = home, config
        doctor.check_leftovers(f, None)
    finally:
        doctor.HOME, doctor.CONFIG = was_home, was_config
    unsure = next((r["text"] for r in f.rows if "keeps what it replaces" in r["text"]), "")
    check("leftovers", "with no record of the copy in use, all three pack folders are counted and no promise is made",
          "3 old pack folder(s)" in unsure and "is not among them" not in unsure
          and "leave the newest of them alone" in unsure, unsure[:80])

    # (v0.9.4) The walk gives up after LEFTOVER_MAX_FILES files so that a
    # check-up never hangs on a folder nobody expected to be enormous. The
    # part-total was then shown as the size of the folder, which is always an
    # understatement and was presented as a measurement. The limit is lowered
    # here rather than 200,000 files being made, so the same code runs.
    for n in range(3):
        (config / "backups" / "20260901-101010" / f"extra-{n}.json").write_text("y" * 2000)
    f = doctor.Findings()
    was_max = doctor.LEFTOVER_MAX_FILES
    try:
        doctor.HOME, doctor.CONFIG = home, config
        doctor.LEFTOVER_MAX_FILES = 2
        doctor.check_leftovers(f, live)
    finally:
        doctor.HOME, doctor.CONFIG = was_home, was_config
        doctor.LEFTOVER_MAX_FILES = was_max
    cut = next((r["text"] for r in f.rows if "keeps what it replaces" in r["text"]), "")
    check("leftovers", "a count that was cut short says \"at least\", not a figure it cannot stand behind",
          re.search(r"backup folder\(s\)[^;]*at least \d+ (KB|MB|GB)", cut) is not None, cut[:160])
    check("leftovers", "a family that was counted in full still says \"about\", so the two are told apart",
          re.search(r"old pack folder\(s\)[^;]*about \d+ (KB|MB|GB)", cut) is not None, cut[:160])
    check("leftovers", "and the total says \"at least\" as well, and says why",
          "That is at least" in cut and "the count was stopped there" in cut,
          cut[cut.find("That is"):][:120])
    check("leftovers", "a run where nothing was cut short says \"about\" throughout",
          "about " in said and "at least" not in said)

    # a Mac with nothing left over says nothing at all
    f = doctor.Findings()
    bare = work / "home-bare"
    (bare / ".config" / "moblee").mkdir(parents=True)
    try:
        doctor.HOME, doctor.CONFIG = bare, bare / ".config" / "moblee"
        doctor.check_leftovers(f, None)
    finally:
        doctor.HOME, doctor.CONFIG = was_home, was_config
    check("leftovers", "a Mac with nothing left over is told nothing", f.rows == [])


# ------------------------------------------------------------------ the timeout
STUB = """#!/bin/bash
# A stand-in for ChatGPT's agent. It answers the sign-in question at once, and
# then, when asked to do the real work, starts a child of its own and waits.
# Neither ever finishes, so the check-up's limit is what ends them, and the
# child is what proves the WHOLE process group was ended and not just the one
# program the check-up started.
if [ "$1" = "login" ]; then
  echo "Logged in"
  exit 0
fi
( sleep 600 ) &
echo "$!" > "PIDDIR/child"
echo "$$" > "PIDDIR/parent"
sleep 600
"""


def put_stub_on_path(work):
    bindir = work / "stub-bin"
    piddir = work / "stub-pids"
    bindir.mkdir(parents=True, exist_ok=True)
    piddir.mkdir(parents=True, exist_ok=True)
    stub = bindir / "codex"
    stub.write_text(STUB.replace("PIDDIR", str(piddir)))
    stub.chmod(stub.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    os.environ["PATH"] = str(bindir) + os.pathsep + os.environ.get("PATH", "")
    return stub, piddir


def alive(pid):
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def gone_within(pids, seconds):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if not any(alive(p) for p in pids):
            return True
        time.sleep(0.2)
    return not any(alive(p) for p in pids)


def read_pids(piddir):
    out = []
    for name in ("parent", "child"):
        try:
            out.append(int((piddir / name).read_text().strip()))
        except (OSError, ValueError):
            pass
    return out


def test_timeout(doctor, work):
    stub, piddir = put_stub_on_path(work)
    check("timeout", "find_codex() picks the agent up from PATH, which is the seam a test uses",
          doctor.find_codex() == str(stub), str(doctor.find_codex()))

    # Half one: the limit really is raised, and the group really is reaped.
    started = time.monotonic()
    raised = ""
    try:
        doctor.run_quiet([str(stub), "exec", "wait"], 2)
    except BaseException as exc:                      # noqa: BLE001 - the name is the assertion
        raised = type(exc).__name__
    took = time.monotonic() - started
    check("timeout", "a run that overstays raises TimeoutExpired", raised == "TimeoutExpired", raised)
    check("timeout", "and it is raised at the limit, not three minutes later", took < 10, f"{took:.1f}s")
    pids = read_pids(piddir)
    check("timeout", "the stub really did start a child of its own, so killing the group is put to the test",
          len(pids) == 2, str(pids))
    check("timeout", "the whole process group is ended: neither the agent nor its child survives",
          gone_within(pids, 8), str([(p, alive(p)) for p in pids]))

    # Half two: the same, through the proof itself, with the scratch wiki.
    for name in ("parent", "child"):
        if (piddir / name).is_file():
            (piddir / name).write_text("0")
    home = work / "home-prove"
    config = home / ".config" / "moblee"
    config.mkdir(parents=True)
    f = doctor.Findings()
    was_config, was_limit = doctor.CONFIG, doctor.PROVE_TIMEOUT
    try:
        doctor.CONFIG = config
        doctor.PROVE_TIMEOUT = 2          # the seam: the same code, in seconds
        started = time.monotonic()
        doctor.prove_guard(f, announce=False)
        took = time.monotonic() - started
    finally:
        doctor.CONFIG, doctor.PROVE_TIMEOUT = was_config, was_limit

    check("timeout", "the proof gives up at its limit rather than running for three minutes",
          took < 30, f"{took:.1f}s")
    rows = [r for r in f.rows]
    check("timeout", "exactly one finding comes out of it", len(rows) == 1, str(len(rows)))
    said = rows[0]["text"] if rows else ""
    # (v0.9.4) The limit in words is worked out from PROVE_TIMEOUT, so the
    # sentence says the limit that was really used. It used to be the three
    # words "three minutes", typed out by hand here and in the check-up both,
    # which meant that changing PROVE_TIMEOUT left the line wrong, the test
    # green, and the owner told a figure nothing had used.
    check("timeout", "it is the timeout one, and it names the limit it really ran to",
          rows and rows[0]["level"] == doctor.UNSURE
          and said.startswith("ChatGPT did not finish within " + doctor.prove_limit_words(2))
          and said.startswith("ChatGPT did not finish within two seconds"), said[:60])
    check("timeout", "at the limit Moblee ships, those words are \"three minutes\", as the docs and the app say",
          doctor.PROVE_TIMEOUT == 180 and doctor.prove_limit_words() == "three minutes",
          f"{doctor.PROVE_TIMEOUT}s -> {doctor.prove_limit_words()}")
    check("timeout", "and the words follow the number, so the two cannot drift apart",
          [doctor.prove_limit_words(n) for n in (1, 45, 60, 120, 600, 900)]
          == ["one second", "45 seconds", "one minute", "two minutes", "ten minutes", "15 minutes"],
          ", ".join(doctor.prove_limit_words(n) for n in (1, 45, 60, 120, 600, 900)))
    check("timeout", "it says nothing was deleted, and where the scratch wiki is",
          "Nothing was deleted." in said and "prove-guard" in said)

    scratch = sorted((config / "prove-guard").iterdir())
    check("timeout", "the scratch wiki is left exactly where it was made", len(scratch) == 1)
    if scratch:
        page = scratch[0] / "wiki" / "page.md"
        folder = scratch[0] / "emptydir"
        check("timeout", "and its contents are untouched: the page and the folder are both still there",
              page.is_file() and folder.is_dir()
              and page.read_text() == "# Scratch page\n\nA page with nothing on it that matters.\n")
    pids = read_pids(piddir)
    check("timeout", "and again no stray agent is left running on the owner's allowance",
          gone_within([p for p in pids if p > 1], 8), str(pids))

    # the timeout sentence the app's fixture carries must be the one above
    fixture = PACK / "app" / "Fixtures" / "prove-guard" / "timed-out.json"
    try:
        sample = json.loads(fixture.read_text())
    except (OSError, ValueError):
        sample = []
    row = next((r for r in sample if r.get("level") == "CANNOT TELL"
                and str(r.get("text", "")).startswith("ChatGPT did not finish")), None)
    # The sentence above was raised with the test's own two-second limit. Put
    # the shipped limit's words back into it and it is the sentence a real owner
    # meets, which is the one the app's sample has to match.
    shipped = said.replace("within " + doctor.prove_limit_words(2),
                           "within " + doctor.prove_limit_words(180), 1)
    check("timeout", "the app's timed-out.json sample carries the check-up's real timeout sentence",
          row is not None and shipped.startswith(str(row["text"])[:60]) if row else False,
          shipped[:60])


# ------------------------------------------------------- what counts as a value
# (v0.9.4) The "put yours here" filter used to be read against the matched value
# AND against forty characters before it and twenty after. Three of the four
# rows below were therefore dropped in silence and the sweep went on to say no
# secrets were found. A markdown blockquote is the ordinary way a wiki page
# quotes an email or a chat, and "your" is the commonest word in English to find
# beside a password, so this was not a corner: it was the middle of the road.
SECRET_VALUE = "Hunter2Swordfish"
AROUND_A_SECRET = [
    ("a bare line", "password: " + SECRET_VALUE),
    ("a quoted line, as a page quotes an email or a chat", "> password: " + SECRET_VALUE),
    ("prose with \"your\" in it", "Your bank password: " + SECRET_VALUE),
    ("an email address in angle brackets on the line",
     "mail <a@b.com> password: " + SECRET_VALUE),
]
# Documentation that must still be passed over. Every one of these says "put
# yours here" IN THE VALUE, which is what the filter was always meant to read.
STILL_DOCUMENTATION = [
    "password: your-password-here",
    "api_key = ${OPENAI_API_KEY}",
    'password = os.environ["WIKI_PW"]',
    "secret_key: REDACTED",
    "access_token: xxxxxxxx",
    "password: <put yours here>",
    "api-key: example-value-1234",
    "password: ********",
    "client_secret: $CLIENT_SECRET",
    "password: keychain-item-name",
    "auth_token: ...",
]


def test_value(doctor, work):
    for label, line in AROUND_A_SECRET:
        found = doctor.privacy_in_file(line + "\n", set())
        kinds = [k for _lvl, k, _ln in found]
        check("value", f"a password is found with {label}",
              kinds == ["a password or key written into a setting"], str(kinds))
    for line in STILL_DOCUMENTATION:
        check("value", f"documentation is still passed over: {line[:38]}",
              doctor.privacy_in_file(line + "\n", set()) == [])
    # and the whole sweep, not just the one function: a page written the way a
    # wiki really is must not come back "no secrets were found".
    vault = work / "wiki-quoted"
    (vault / "wiki").mkdir(parents=True)
    (vault / "wiki" / "Mail.md").write_text(
        "# Mail\n\nThe reply said:\n\n> password: " + SECRET_VALUE + "\n\n"
        "Your bank password: " + SECRET_VALUE + "\n")
    f = doctor.Findings()
    doctor.check_privacy(f, vault, PACK)
    said = " ".join(r["text"] for r in f.rows)
    check("value", "the sweep no longer reports a wiki full of quoted secrets as clean",
          "No secrets were found" not in said and "wiki/Mail.md line 5" in said
          and "wiki/Mail.md line 7" in said, said[:110])
    check("value", "and it still prints no part of the secret itself",
          SECRET_VALUE not in said and SECRET_VALUE[:8] not in said)


# --------------------------------------------- the files the sweep will open
def test_files(doctor, work):
    vault = work / "wiki-keyfiles"
    (vault / "wiki").mkdir(parents=True)
    (vault / ".ssh").mkdir(parents=True)
    key = PLANTED["a private key"] + "\n" + KEY_BODY + "\n-----END OPENSSH PRIVATE KEY-----\n"
    (vault / ".ssh" / "id_rsa").write_text(key)          # no extension at all
    (vault / ".ssh" / "id_rsa.pub").write_text("ssh-rsa AAAAfake practice@fixture\n")
    (vault / "wiki" / "server.pem").write_text(key)
    (vault / "wiki" / "Board.canvas").write_text(
        '{"nodes":[{"text":"' + PLANTED["an Amazon cloud access key"] + '"}]}\n')
    (vault / "wiki" / "Old page.markdown").write_text("# Old\n\n" + PLANTED["a GitHub token"] + "\n")
    f = doctor.Findings()
    doctor.check_privacy(f, vault, PACK)
    said = " ".join(r["text"] for r in f.rows)
    for rel in (".ssh/id_rsa", "wiki/server.pem", "wiki/Board.canvas", "wiki/Old page.markdown"):
        check("files", f"a secret in {rel} is found, not stepped over", f"{rel} line" in said, said[:90])
    check("files", "the public half of a key pair holds nothing secret and is not raised",
          ".ssh/id_rsa.pub line" not in said)
    check("files", "and no planted secret reaches the wording either",
          not any(p in said for s in PLANTED.values() for p in fragments_of(s)))
    # .p12 is a binary container, so the sweep does not open it: the marker it
    # looks for is never in one. This pins the decision rather than the accident.
    check("files", ".p12 is deliberately left out, being binary and never holding the marker",
          ".p12" not in doctor.PRIVACY_TEXT_EXT
          and {".pem", ".key", ".asc", ".markdown", ".canvas"} <= doctor.PRIVACY_TEXT_EXT)


# ------------------------------------------- the note saying "looked at, kept"
def test_accepted(doctor, work):
    vault = work / "wiki-accepted"
    (vault / "wiki").mkdir(parents=True)
    (vault / ".moblee").mkdir(parents=True)
    (vault / "wiki" / "Wallet.md").write_text(
        "# Wallet\n\n" + PLANTED["a run of words shaped like a wallet recovery phrase"] + "\n")
    # One more that has NOT been accepted, so the advice line is on screen and
    # can be read for what it promises the owner.
    (vault / "wiki" / "Cloud.md").write_text(
        "# Cloud\n\nThe store card reads " + PLANTED["an Amazon cloud access key"] + " today.\n")
    # Written the way somebody typing by hand writes it: a capital letter, a
    # doubled space, a full stop at the end, and no leading article on the kind.
    (vault / ".moblee" / "privacy-accepted.txt").write_text(
        "# path | kind | why\n"
        "Wiki/Wallet.md | Run of words  shaped like a wallet recovery phrase. | practice words\n")
    f = doctor.Findings()
    doctor.check_privacy(f, vault, PACK)
    said = " ".join(r["text"] for r in f.rows)
    check("accepted", "a note copied out by hand still matches, capitals, spacing and full stop apart",
          "wiki/Wallet.md line" not in said and "looked at before and kept on purpose" in said,
          said[:90])
    check("accepted", "and the check-up says on screen that it need not be copied exactly",
          "capitals and spacing do not have to match" in said)
    check("accepted", "a note about a different kind does not suppress this one",
          doctor.privacy_key("wiki/Wallet.md", "a wallet recovery phrase")
          != doctor.privacy_key("wiki/Wallet.md", "a run of words shaped like a wallet recovery phrase"))
    kinds = [k for k, _rx in doctor.PRIVACY_CRITICAL + doctor.PRIVACY_REVIEW] + \
            ["a wallet recovery phrase", "a run of words shaped like a wallet recovery phrase"]
    reduced = {doctor.privacy_key("p", k)[1] for k in kinds}
    check("accepted", "no two kinds collapse into one another once capitals and articles are forgiven",
          len(reduced) == len(set(kinds)), f"{len(reduced)} of {len(set(kinds))}")


# ----------------------------------------------------- the rules file's length
def rules_vault(root, extra=""):
    root.mkdir(parents=True, exist_ok=True)
    (root / "wiki" / "Wiki Operations").mkdir(parents=True, exist_ok=True)
    (root / "CLAUDE.md").write_text((PACK / "vault-template" / "CLAUDE.md").read_text() + extra)
    return root


def test_rules(doctor, work):
    # 1. Moblee's sections intact, plus two long ones of the owner's own. This
    #    used to be called "Moblee's own wording throughout", of a file more
    #    than twice the length the release promises, over half of it the owner's.
    mine = ("\n\n## Ways I like to work\n\n" + ("Words of my own. " * 400)
            + "\n\n## People and places\n\n" + ("More of my own words. " * 400) + "\n")
    vault = rules_vault(work / "rules-plus-mine", mine)
    f = doctor.Findings()
    doctor.check_rules_sections(f, vault, PACK)
    said = " ".join(r["text"] for r in f.rows)
    check("rules", "a file with sections of the owner's own is not called Moblee's wording throughout",
          "is Moblee's own wording throughout" not in said, said[:90])
    check("rules", "it says how many sections are the owner's, and names them",
          "2 section(s) of your own" in said and '"Ways I like to work"' in said
          and '"People and places"' in said, said[:150])
    check("rules", "and says how long they are, which is the question this check exists to answer",
          "tokens of it" in said and "why the file is the length it is" in said)

    # 2. The same file with nothing of the owner's in it: the old sentence, and
    #    it is the right one here.
    plain = rules_vault(work / "rules-plain")
    f = doctor.Findings()
    doctor.check_rules_sections(f, plain, PACK)
    said = " ".join(r["text"] for r in f.rows)
    check("rules", "a file that really is Moblee's throughout is still told so, in one short line",
          "is Moblee's own wording throughout" in said and "section(s) of your own" not in said)

    # 3. A half-copied pack: scripts/ there, vault-template/CLAUDE.md not. The
    #    engine says it could not compare; the owner used to be told instead
    #    that they had edited every section of their own file.
    half = work / "half-pack"
    (half / "scripts").mkdir(parents=True, exist_ok=True)
    for name in ("patch-claude-md.py", "claude-md-known.json"):
        src = PACK / "scripts" / name
        if src.is_file():
            (half / "scripts" / name).write_text(src.read_text())
    f = doctor.Findings()
    doctor.check_rules_sections(f, plain, half)
    rows = f.rows
    said = " ".join(r["text"] for r in rows)
    check("rules", "with Moblee's own copy missing, the check-up says it could not tell",
          len(rows) == 1 and rows[0]["level"] == doctor.UNSEEN, str([r["level"] for r in rows]))
    check("rules", "and says nothing whatever about what the owner has written",
          "None of its sections still match" not in said
          and "nothing here says anything about what you have written" in said, said[:110])
    check("rules", "and says how to find out, which is what CANNOT SEE lines are for",
          "package-path" in said and "run the check-up from a complete Moblee folder" in said)

    # 4. A file Moblee no longer recognises at all: that IS about the owner's
    #    writing, and the words for it are unchanged.
    own = work / "rules-all-mine"
    (own / "wiki").mkdir(parents=True, exist_ok=True)
    (own / "CLAUDE.md").write_text("# My rules\n\n## Mine\n\nEvery word of this is my own.\n")
    f = doctor.Findings()
    doctor.check_rules_sections(f, own, PACK)
    said = " ".join(r["text"] for r in f.rows)
    check("rules", "a file Moblee no longer recognises is still told so, at LOOK with its code",
          f.rows and f.rows[0]["level"] == doctor.LOOK and f.rows[0]["guide"] == "F40"
          and "None of its sections still match" in said)


def test_weights(doctor, work):
    # (v0.9.4) The rules file's size used to go out as an OK row saying the
    # figure and the cap, immediately above the PROBLEM row saying it was over
    # that cap. One question, two answers, the reassuring one first.
    over = work / "weights-over"
    (over / "wiki").mkdir(parents=True, exist_ok=True)
    (over / "CLAUDE.md").write_text("# Rules\n" + ("x" * (doctor.INSTRUCTION_CAP * 4 + 4000)))
    f = doctor.Findings()
    doctor.check_weights(f, over)
    about = [r for r in f.rows if "CLAUDE.md" in r["text"]]
    check("weights", "a rules file over its cap is spoken of exactly once",
          len(about) == 1, "; ".join(f"{r['level']}: {r['text'][:40]}" for r in about))
    check("weights", "and that once is the PROBLEM, not an OK saying all is well",
          bool(about) and about[0]["level"] == doctor.PROBLEM and about[0]["guide"] == "F30")
    check("weights", "the figure and the cap are still given, so nothing is lost by the OK going",
          bool(about) and "over its 16,000" in about[0]["text"], about[0]["text"][-60:] if about else "")

    # A rules file that is fine still has its own figure said, which is the
    # reason that line exists: it is the file v0.9.4 set out to shorten.
    fine = work / "weights-fine"
    (fine / "wiki").mkdir(parents=True, exist_ok=True)
    (fine / "CLAUDE.md").write_text("# Rules\n" + ("x" * 4000))
    f = doctor.Findings()
    doctor.check_weights(f, fine)
    about = [r for r in f.rows if "CLAUDE.md" in r["text"]]
    check("weights", "a rules file well within its cap is given its figure, once, as an OK",
          len(about) == 1 and about[0]["level"] == doctor.OK
          and "against a cap of 16,000" in about[0]["text"])

    # And when it is another file that is over, the rules file's figure is still
    # said: the two lines are then about two different files, not one.
    other = work / "weights-other"
    (other / "wiki").mkdir(parents=True, exist_ok=True)
    (other / "CLAUDE.md").write_text("# Rules\n" + ("x" * 4000))
    (other / "wiki" / "_context.md").write_text("x" * (12000 * 4 + 4000))
    f = doctor.Findings()
    doctor.check_weights(f, other)
    levels = {r["level"] for r in f.rows if "CLAUDE.md" in r["text"]}
    check("weights", "another file being over does not silence the rules file's own figure",
          levels == {doctor.OK} and any(r["guide"] == "F30" for r in f.rows), str(levels))


# ------------------------------------------------ the report that names nobody
def test_report_names(doctor, work):
    line = ("The wiki's history is sent nowhere. Wikipedia is not involved. "
            "Notes about notes are fine.")
    plain = doctor.anonymiser(Path(work / "Notes"))
    check("report", "a wiki folder called Notes is an ordinary word, so the report is left readable",
          plain(line) == line, plain(line)[:80])
    wiki_named = doctor.anonymiser(Path(work / "Wiki"))
    check("report", "and so is one called Wiki: \"Wikipedia\" and \"the wiki\" survive it",
          wiki_named(line) == line, wiki_named(line)[:80])
    # The one that really happened: a folder at ~/wiki, spelled the way the
    # check-up spells the word all through its own findings. Nine lines of the
    # report came out as nonsense.
    lower = doctor.anonymiser(Path(work / "wiki"))
    real = ("This wiki is set up to be used with Claude. Moblee's permission rules are not "
            "in the wiki's settings.")
    check("report", "a folder at ~/wiki no longer turns the check-up's own sentences into nonsense",
          lower(real) == real, lower(real)[:90])
    check("report", "but its path is still taken out, whatever the folder is called",
          lower("The wiki is at " + str(work / "wiki") + ".") == "The wiki is at <wiki>.",
          lower("The wiki is at " + str(work / "wiki") + "."))
    mine = doctor.anonymiser(Path(work / "Practice Owner Wiki"))
    said = mine("The folder Practice Owner Wiki is at " + str(work / "Practice Owner Wiki")
                + ". Wikipedia is not involved.")
    check("report", "a folder named after somebody is taken out, by name and by path",
          "Practice Owner Wiki" not in said and said.count("<wiki>") == 2, said)
    check("report", "and only where it stands alone: a longer word that contains it is left as it is",
          "Wikipedia" in said, said)


# ------------------------------------------------- the card a helper is shown
def card_of(doctor, rows, vault=None):
    """The card as a dict, and the card as the one block of text a person reads."""
    card = doctor.build_card(rows, vault)
    return card, "\n".join(card["lines"])


def plain_wiki(root, extra_pages=None):
    """A wiki with no planted secrets in it, for the cases about shape rather
    than about redaction."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "VERSION").write_text("0.9.4\n")
    (root / "CLAUDE.md").write_text("# Practice wiki\n\nNothing here is real.\n")
    (root / "wiki").mkdir(exist_ok=True)
    (root / "wiki" / "Index.md").write_text("# Index\n\nA practice wiki.\n")
    for rel, text in (extra_pages or {}).items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text)
    return root


def made_rows(doctor, spec):
    """Findings written out by hand, so that a case can be set up exactly. Each
    item is (level, code) and gets a sentence long enough to need shortening."""
    f = doctor.Findings()
    for n, (level, code) in enumerate(spec, start=1):
        f.add(level, f"Finding number {n} says something is the matter with the way this "
                     f"wiki is set up on this Mac, and goes on about it at length.", code)
    return f.rows


def test_card(doctor, work):
    # ---- a healthy wiki
    card, text = card_of(doctor, made_rows(doctor, [(doctor.OK, None), (doctor.OK, None)]))
    check("card", "a wiki with nothing wrong is called healthy, in those words",
          card["healthy"] and "looks healthy" in text, card["headline"][:60])
    check("card", "and is given nothing to do beyond coming back to it later",
          card["wrong_total"] == 0 and card["actions"] == ["Nothing to do. Run the check-up again next month."],
          "; ".join(card["actions"]))
    check("card", "a healthy card carries no \"what is wrong\" heading at all",
          doctor.CARD_WRONG_HEAD not in text)

    # ---- one problem
    card, text = card_of(doctor, made_rows(doctor, [(doctor.OK, None), (doctor.PROBLEM, "F01")]))
    check("card", "one problem is counted as one, and not called healthy",
          not card["healthy"] and "1 thing to look at" in card["headline"]
          and "healthy" not in text, card["headline"][:60])
    check("card", "it is listed, once, with its field-guide number beside it, so the helper can look it up",
          card["wrong_total"] == 1 and len(card["wrong"]) == 1
          and card["wrong"][0]["guide"] == "F01" and "  F01  " in text)
    check("card", "nothing is said to be hidden when nothing is",
          card["wrong_not_shown"] == 0 and "more. The full check-up" not in text)

    # ---- more problems than fit
    many = made_rows(doctor, [(doctor.PROBLEM, "F01")] * 9 + [(doctor.LOOK, "F02")] * 5)
    card, text = card_of(doctor, many)
    check("card", "more problems than fit are listed as far as the card goes",
          len(card["wrong"]) == doctor.CARD_PROBLEMS, str(len(card["wrong"])))
    check("card", "the headline still counts every one of them, not only the ones shown",
          f"{len(many)} things to look at" in card["headline"], card["headline"][:60])
    check("card", "the rest are counted on the card and never dropped in silence",
          f"and {len(many) - doctor.CARD_PROBLEMS} more" in text
          and card["wrong_not_shown"] == len(many) - doctor.CARD_PROBLEMS)
    check("card", "and the card says where the ones it left out are written out in full",
          "The full check-up lists every one." in text)
    check("card", "shown plus not shown is the whole count, so no finding can fall between them",
          len(card["wrong"]) + card["wrong_not_shown"] == card["wrong_total"] == len(many))
    check("card", "the worst come first: every PROBLEM is listed before any LOOK",
          [w["level"] for w in card["wrong"]] == [doctor.PROBLEM] * doctor.CARD_PROBLEMS,
          str([w["level"] for w in card["wrong"]]))

    # ---- one screen, in both directions
    widest, tallest = 0, 0
    for spec in ([(doctor.OK, None)],
                 [(doctor.PROBLEM, "F01")],
                 [(doctor.PROBLEM, "F41")] * 12 + [(doctor.LOOK, "F02")] * 12
                 + [(doctor.UNSEEN, "F26")] * 4 + [(doctor.UNSURE, "F31")] * 4,
                 [(doctor.UNSEEN, "F26")] * 6):
        c, t = card_of(doctor, made_rows(doctor, spec))
        tallest = max(tallest, len(c["lines"]))
        widest = max(widest, max(len(line) for line in c["lines"]))
    check("card", "no card is taller than one screen, however much is wrong",
          tallest <= doctor.CARD_LINES, f"{tallest} lines, cap {doctor.CARD_LINES}")
    check("card", "and none is wider, so nothing wraps in an ordinary Terminal window",
          widest <= doctor.CARD_WIDTH, f"{widest} columns, cap {doctor.CARD_WIDTH}")

    # ---- something that could not be checked
    card, text = card_of(doctor, made_rows(doctor, [(doctor.OK, None), (doctor.UNSEEN, "F26")]))
    check("card", "a wiki with nothing wrong but something unchecked is NOT called healthy",
          not card["healthy"] and "healthy" not in text, card["headline"][:70])
    check("card", "it is told plainly that this is not a clean bill",
          "not a clean bill" in card["headline"] and "1 thing could not be checked" in card["headline"])
    check("card", "what could not be checked has a section of its own, and is not a fault",
          doctor.CARD_UNSEEN_HEAD in text and card["unchecked_total"] == 1)
    check("card", "CANNOT TELL is carried the same way as CANNOT SEE",
          card_of(doctor, made_rows(doctor, [(doctor.UNSURE, "F31")]))[0]["unchecked_total"] == 1)
    both = made_rows(doctor, [(doctor.PROBLEM, "F01"), (doctor.UNSEEN, "F26"), (doctor.UNSURE, "F31")])
    card, text = card_of(doctor, both)
    check("card", "a wiki that is both unwell and partly unchecked says both, in the headline",
          "1 thing to look at" in card["headline"] and "2 more could not be checked" in card["headline"],
          card["headline"][:80])
    lots = made_rows(doctor, [(doctor.UNSEEN, "F26")] * 5)
    card, text = card_of(doctor, lots)
    check("card", "more unchecked lines than fit are counted too, not quietly dropped",
          card["unchecked_total"] == 5
          and len(card["unchecked"]) + card["unchecked_not_shown"] == 5
          and f"and {card['unchecked_not_shown']} more" in text)

    # ---- THE STRUCTURAL ONE: the card cannot contradict the findings
    # Every mixture of the five levels there is. The card may call a wiki healthy
    # only when the findings hold nothing wrong and nothing unchecked, and its
    # counts must be the findings' own counts. This is a property of
    # card_facts(), which is the one place the split is made.
    levels = (doctor.OK, doctor.LOOK, doctor.PROBLEM, doctor.UNSEEN, doctor.UNSURE)
    wrong_word, wrong_count, wrong_listed = [], [], []
    for bits in range(2 ** len(levels)):
        spec = [(lv, "F01" if lv in (doctor.LOOK, doctor.PROBLEM) else None)
                for i, lv in enumerate(levels) if bits >> i & 1]
        rows = made_rows(doctor, spec)
        card, text = card_of(doctor, rows)
        bad = [r for r in rows if r["level"] in (doctor.LOOK, doctor.PROBLEM)]
        unseen = [r for r in rows if r["level"] in (doctor.UNSEEN, doctor.UNSURE)]
        clean = not bad and not unseen
        if bool(re.search(r"\bhealthy\b", text)) != clean or card["healthy"] != clean:
            wrong_word.append(sorted({lv for lv, _ in spec}))
        if card["wrong_total"] != len(bad) or card["unchecked_total"] != len(unseen):
            wrong_count.append(sorted({lv for lv, _ in spec}))
        # and every line on the card is a finding of that run, not a line of its own
        for item in card["wrong"] + card["unchecked"]:
            stem = item["line"].rstrip(".").rstrip(".")[:30]
            if not any(stem in (r.get("sendable") or r["text"]) for r in rows):
                wrong_listed.append(item["line"][:40])
    check("card", "over every mixture of levels there is, \"healthy\" appears only when nothing is wrong and nothing is unchecked",
          not wrong_word, str(wrong_word[:2]))
    check("card", "and the card's counts are the findings' own counts, in every one of those mixtures",
          not wrong_count, str(wrong_count[:2]))
    check("card", "every line on a card comes from a finding of the same run; the card invents none",
          not wrong_listed, str(wrong_listed[:2]))

    # ---- the redaction, against a wiki full of planted secrets
    vault = build_wiki(work / "Practice Owner Card Wiki", "claude")
    out = run_checkup(doctor, vault, "claude", card=True)
    leaked = []
    for kind, secret in list(PLANTED.items()) + [("the private key's body", KEY_BODY)]:
        for piece in fragments_of(secret):
            if piece in out["card"] + out["card-json"]:
                leaked.append(f"{kind}: {piece[:16]}")
    check("card", "no planted secret, whole or in pieces, reaches the card or its JSON",
          not leaked, "; ".join(leaked[:3]))
    named = [rel for rel in practice_pages() if rel.startswith("wiki/") and rel in out["card"]]
    check("card", "the card names no page of the wiki, page titles being what a helper must not be shown",
          not named, "; ".join(named[:3]))
    check("card", "nor any bare page title on its own",
          "Wallet" not in out["card"] and "Sign in" not in out["card"])
    check("card", "the home folder is written as ~, so the card carries no account name",
          str(doctor.HOME) not in out["card"] and str(doctor.HOME) not in out["card-json"])
    card = json.loads(out["card-json"])
    check("card", "--card --json is one object a program can read, with the verdict in it as a plain yes or no",
          isinstance(card, dict) and card["healthy"] is False and card["state"] == "unwell"
          and card["lines"] == out["card"].rstrip("\n").splitlines())
    check("card", "and plain --json is untouched, still the bare list of findings a program already reads",
          isinstance(json.loads(out["json"]), list))
    after = practice_pages()
    check("card", "printing a card changed nothing in the wiki: the check-up is still read-only",
          all((vault / rel).read_text() == body for rel, body in after.items()))

    # The privacy sweep on its own, so that its findings are certainly on the
    # card: they name files, and a file name in a wiki is a page title. The card
    # must count them and never name them, and it does that with the sweep's own
    # "sendable" wording rather than a second mechanism of its own.
    f = doctor.Findings()
    doctor.check_privacy(f, vault, PACK)
    card, text = card_of(doctor, f.rows, vault)
    codes = [w["guide"] for w in card["wrong"]]
    check("card", "the privacy sweep's findings reach the card, counted",
          "F41" in codes and "F42" in codes and "look like a live secret" in text, str(codes))
    check("card", "counted but never named: not one of the pages it found is on the card",
          not [rel for rel in practice_pages() if rel.startswith("wiki/") and rel in text])
    check("card", "the wording is the sweep's own sendable wording, not a second redaction invented here",
          any(w["line"] in (r.get("sendable") or "") for w in card["wrong"] for r in f.rows
              if r["guide"] == "F41"),
          str([w["line"] for w in card["wrong"]])[:80])

    # anon() is the report's own redaction, and the card is passed through it too
    named_vault = work / "Practice Owner Card Wiki"
    f = doctor.Findings()
    f.add(doctor.PROBLEM, f"The folder Practice Owner Card Wiki at {named_vault} holds something "
                          "that wants looking at before anything else is done.", "F01")
    card, text = card_of(doctor, f.rows, named_vault)
    check("card", "the wiki's own folder name and path go out as <wiki>, exactly as in a report",
          "Practice Owner Card Wiki" not in text and "<wiki>" in text, text.splitlines()[4] if len(text.splitlines()) > 4 else text)

    # ---- how a program gets at it, and what it will not do
    where = plain_wiki(work / "card-file-wiki")
    path = work / "cards" / "health-card.txt"
    code, said = run_doctor(doctor, ["--vault", str(where), "--card", "--card-file", str(path)])
    check("card", "--card-file saves the card, making the folder if it has to, and says where it went",
          code == 0 and path.is_file() and "Health card written to" in said, said.strip()[-50:])
    check("card", "the file holds the same card that was printed, and ends with a newline",
          path.read_text() == said.split("\nHealth card written to")[0].rstrip("\n") + "\n")
    code, said = run_doctor(doctor, ["--vault", str(where), "--card", "--card-file", str(path)])
    check("card", "a second run replaces the earlier card at that path, which is what a program needs",
          code == 0 and path.read_text().startswith(doctor.CARD_TITLE))
    precious = work / "cards" / "a page of the owner's own.md"
    precious.write_text("# Mine\n\nNot a health card.\n")
    code, said = run_doctor(doctor, ["--vault", str(where), "--card", "--card-file", str(precious)])
    check("card", "but a file that is not a health card is left exactly as it was, and the caller told why",
          code == 1 and precious.read_text() == "# Mine\n\nNot a health card.\n"
          and "not a health card" in said and "Nothing in it was changed" in said)
    check("card", "--card prints the card and nothing else: no list of findings behind it",
          "Moblee check-up (nothing is changed by this)" not in
          run_doctor(doctor, ["--vault", str(where), "--card"])[1])


def main():
    work = Path(tempfile.mkdtemp(prefix="moblee-doctor-test-",
                                 dir=os.environ.get("TMPDIR") or None))
    doctor = load_doctor()
    print(f"Testing {DOCTOR}")
    print(f"Working folder: {work}\n")
    test_shape(doctor)
    test_privacy(doctor, work)
    test_value(doctor, work)
    test_files(doctor, work)
    test_accepted(doctor, work)
    test_rules(doctor, work)
    test_weights(doctor, work)
    test_report_names(doctor, work)
    test_card(doctor, work)
    test_app(doctor, work)
    test_leftovers(doctor, work)
    test_timeout(doctor, work)

    width = max(len(r[2]) for r in ROWS)
    print("%-4s %-9s %-*s %s" % ("", "group", width, "case", "note"))
    for status, group, label, note in ROWS:
        print("%-4s %-9s %-*s %s" % (status, group, width, label, note))
    print("")
    print("%d passed, %d failed, of %d." % (len(ROWS) - FAILURES, FAILURES, len(ROWS)))
    print("Practice wikis and fixtures are left in %s" % work)
    print("Run on %s" % datetime.date.today().isoformat())
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
