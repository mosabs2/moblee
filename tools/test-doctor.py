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
  guardver  Which delete guard is on the Mac, in the guard's own words, said
            beside the hash comparison rather than instead of it, for Claude
            and for ChatGPT, and degrading to CANNOT TELL for a guard that
            does not say which it is.
  saving    Whether the wiki saves itself at the end of every reply: the script
            in the wiki, the Stop hook that runs it for each assistant, what
            the last run did, and the one line the card and the app's check-up
            screen carry about it. The hard one, as in the privacy sweep: a
            record names the files the commit gate stopped, and a file name in
            a wiki is a page title, so not one of them may reach the screen.
  prove     The proof that the save really fires, run with a stand-in for the
            assistant that makes the edit and then runs the pack's own
            end-of-reply script exactly as the hook runs it, so the commit and
            the record the proof reads are real ones.
  mods      Claude's own additions: the band above the prompt, which Moblee
            keeps in the wiki at scripts/claude-mods/ and registers with Claude
            from there. Which Claude is chosen and from where (the PATH first,
            then the Claude app's own engine, newest version first), the line
            below which a Claude is too old to take a mod at all, and the
            finding in each of its states — installed and switched on, not
            installed, switched off, read from some other folder, and no Claude
            new enough yet, which is said in one plain sentence word for word.
            Every engine is a stub, so nothing is installed anywhere.
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
import shlex
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
          "2 old pack folders" in said, said[:120])
    check("leftovers", "the backup folders are counted", "3 backup folders" in said)
    check("leftovers", "the scratch wikis from guard proofs are counted", "1 scratch wiki folder left by a guard proof" in said)
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
          "3 old pack folders" in unsure and "is not among them" not in unsure
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
          re.search(r"backup folders[^;]*at least \d+ (KB|MB|GB)", cut) is not None, cut[:160])
    check("leftovers", "a family that was counted in full still says \"about\", so the two are told apart",
          re.search(r"old pack folders[^;]*about \d+ (KB|MB|GB)", cut) is not None, cut[:160])
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

    # (v0.10.0) The end-of-reply save's proof leaves a scratch wiki every time
    # it runs, as the guard's proof does. A folder nothing counts is a folder
    # nobody clears out, so it is counted here and named apart from the other.
    f = doctor.Findings()
    saved = work / "home-saving-left"
    config2 = saved / ".config" / "moblee"
    for stamp in ("20261013-101010", "20261014-101010"):
        (config2 / "prove-saving" / stamp / "practice-wiki" / "wiki").mkdir(parents=True)
        (config2 / "prove-saving" / stamp / "practice-wiki" / "wiki" / "page.md").write_text("z" * 100)
    (config2 / "prove-guard" / "20261012-101010").mkdir(parents=True)
    try:
        doctor.HOME, doctor.CONFIG = saved, config2
        doctor.check_leftovers(f, None)
    finally:
        doctor.HOME, doctor.CONFIG = was_home, was_config
    both = next((r["text"] for r in f.rows if "keeps what it replaces" in r["text"]), "")
    check("leftovers", "the scratch wikis the end-of-reply proof leaves are counted too",
          "2 scratch wiki folders left by end-of-reply save proofs" in both, both[:160])
    check("leftovers", "and are named apart from the ones the guard proof leaves",
          "1 scratch wiki folder left by a guard proof" in both, both[:160])


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


# ------------------------------------------------- which guard is on this Mac
# (v0.10.0) The check-up compared the installed guard with the pack's copy by
# hash and said whether they matched, which answers "has it been swapped" and
# not "which guard have I got". An owner on the telephone to whoever is helping
# them could not say. These lock the second answer, and lock its degrading to
# CANNOT TELL for a guard that does not say, rather than guessing.
REGISTERED = {"hooks": {"PreToolUse": [
    {"matcher": "Bash", "hooks": [{"command": 'python3 "$HOME/.claude/hooks/bash-guard.py"'}]}]}}


def installed_guard(work, name, text):
    """A practice home folder with a guard of our choosing installed in it."""
    home = work / name
    (home / ".claude" / "hooks").mkdir(parents=True, exist_ok=True)
    guard = home / ".claude" / "hooks" / "bash-guard.py"
    guard.write_text(text)
    return guard


def guard_rows(doctor, guard, pack):
    """The findings check_guard makes about a guard installed at `guard`."""
    f = doctor.Findings()
    was = doctor.GUARD
    try:
        doctor.GUARD = guard
        doctor.check_guard(f, REGISTERED, pack)
    finally:
        doctor.GUARD = was
    return f.rows


def test_guard_version(doctor, work):
    ours = PACK / "safety" / "bash-guard.py"
    said = doctor.guard_version(ours)

    # 1. The pack's own guard says which it is, in the shape the check-up prints.
    check("guardver", "the pack's own guard says which version it is",
          bool(said) and re.fullmatch(r"v\d+(\.\d+)*", said or "") is not None, str(said))
    # Bump this with the guard: it is the one place that says, in a test, which
    # guard this release ships.
    check("guardver", "and this release ships v5.3", said == "v5.3", str(said))

    # 2. A guard that is the pack's own copy: the version said once, beside the
    #    comparison and not instead of it.
    same = installed_guard(work, "guard-same", ours.read_text())
    rows = guard_rows(doctor, same, PACK)
    texts = [r["text"] for r in rows]
    check("guardver", "an installed copy of the pack's guard is still called the pack's own copy",
          any("is this Moblee's own copy" in t for t in texts), "; ".join(t[:40] for t in texts))
    version_rows = [r for r in rows if "says it is" in r["text"]]
    check("guardver", "and one line beside it says which version Claude runs",
          len(version_rows) == 1 and version_rows[0]["level"] == doctor.OK
          and f"The delete guard Claude runs says it is {said}" in version_rows[0]["text"],
          str([r["text"][:60] for r in version_rows]))
    check("guardver", "and says it is the same version as the pack's, so nothing is left to work out",
          bool(version_rows) and "the same version as this Moblee's own copy" in version_rows[0]["text"])
    check("guardver", "the version line carries no field-guide code, having nothing of its own to fix",
          bool(version_rows) and version_rows[0]["guide"] is None)
    check("guardver", "and names no account folder, as every printed line must not",
          all("/Users/" not in r["text"] for r in rows), "; ".join(t[:40] for t in texts))

    # 3. An older guard: the fault is said once, by the comparison, and the
    #    version line says both versions rather than reading as reassurance.
    older = installed_guard(work, "guard-older", 'VERSION = "v4"\nprint("an older guard")\n')
    rows = guard_rows(doctor, older, PACK)
    compare = [r for r in rows if "not the same copy" in r["text"]]
    version_rows = [r for r in rows if "says it is" in r["text"]]
    check("guardver", "an older guard is still caught by the comparison, at LOOK with its code",
          len(compare) == 1 and compare[0]["level"] == doctor.LOOK and compare[0]["guide"] == "F02",
          str([(r["level"], r["guide"]) for r in compare]))
    check("guardver", "and the version line names both versions, so which one is on the Mac is plain",
          len(version_rows) == 1 and "says it is v4" in version_rows[0]["text"]
          and f"this Moblee's own copy says {said}" in version_rows[0]["text"],
          str([r["text"][:80] for r in version_rows]))
    check("guardver", "and points at the line that carries the fix instead of giving a second one",
          bool(version_rows) and "the line above" in version_rows[0]["text"].lower()
          and version_rows[0]["guide"] is None)

    # 4. A guard with no version line at all: CANNOT TELL, and nothing guessed.
    quiet = installed_guard(work, "guard-quiet", "# a guard that never says which it is\nprint(1)\n")
    rows = guard_rows(doctor, quiet, PACK)
    unsure = [r for r in rows if r["level"] == doctor.UNSURE]
    check("guardver", "a guard that does not say its version is a CANNOT TELL, not a guess",
          len(unsure) == 1 and "cannot be told" in unsure[0]["text"],
          str([(r["level"], r["text"][:40]) for r in rows]))
    check("guardver", "and that line says nothing is wrong with it beyond not saying",
          bool(unsure) and "says it is v" not in " ".join(r["text"] for r in rows))
    check("guardver", "and says which line to rely on instead, as CANNOT TELL lines must",
          bool(unsure) and "the line above" in unsure[0]["text"]
          and "Repair" in unsure[0]["text"])

    # 5. Nothing to compare against: the version is still said, as the guard's
    #    own word for itself.
    rows = guard_rows(doctor, same, None)
    version_rows = [r for r in rows if "says it is" in r["text"]]
    check("guardver", "with no Moblee folder found, the version is still said",
          len(version_rows) == 1 and f"says it is {said}" in version_rows[0]["text"],
          str([r["text"][:60] for r in version_rows]))
    check("guardver", "and is called the guard's own word for itself, not a comparison",
          bool(version_rows) and "own word for itself" in version_rows[0]["text"])

    # 6. A file that cannot be read at all, which must not raise.
    check("guardver", "a guard path that cannot be read gives no version rather than an error",
          doctor.guard_version(work) is None
          and doctor.guard_version(work / "no-guard-here.py") is None)

    # 7. ChatGPT's copy is reported in the same words, named for ChatGPT.
    codex_home = work / "guard-codex"
    (codex_home / ".codex" / "hooks").mkdir(parents=True, exist_ok=True)
    codex_guard = codex_home / ".codex" / "hooks" / "bash-guard.py"
    codex_guard.write_text(ours.read_text())
    hooks = codex_home / ".codex" / "hooks.json"
    hooks.write_text(json.dumps({"hooks": {"PreToolUse": [
        {"matcher": doctor.CODEX_MATCHER,
         "hooks": [{"command": 'python3 "$HOME/.codex/hooks/bash-guard.py"'}]}]}}))
    f = doctor.Findings()
    was_guard, was_hooks = doctor.CODEX_GUARD, doctor.CODEX_HOOKS
    try:
        doctor.CODEX_GUARD, doctor.CODEX_HOOKS = codex_guard, hooks
        doctor.check_codex_guard(f, PACK)
    finally:
        doctor.CODEX_GUARD, doctor.CODEX_HOOKS = was_guard, was_hooks
    version_rows = [r for r in f.rows if "says it is" in r["text"]]
    check("guardver", "ChatGPT's own copy of the guard has its version said too, named for ChatGPT",
          len(version_rows) == 1
          and f"The delete guard ChatGPT runs says it is {said}" in version_rows[0]["text"],
          str([r["text"][:60] for r in version_rows]))
    check("guardver", "and the comparison for ChatGPT is still made alongside it",
          any("is this Moblee's own copy" in r["text"] for r in f.rows))


# ------------------------------ the wiki saving itself at the end of a reply
# (v0.10.0) The end-of-reply save: the script in the wiki, the Stop hook that
# runs it, what the last run did, and the one line the card and the app's
# check-up screen carry about all of it. The hard one here is the same as the
# privacy sweep's: a record names the files the commit gate stopped, and a file
# name in a wiki is a page title, so not one of them may reach the screen.
#
# (v0.10.0) The hook's command carries the WHOLE PATH of the wiki's own copy of
# the script. A settings file naming some other folder's copy is not this wiki
# saving itself, and the fixtures below keep the two apart on purpose.
def saving_settings(vault):
    """A settings file registering the end-of-reply save for THIS wiki."""
    return {"hooks": {"Stop": [{"hooks": [
        {"type": "command",
         "command": "python3 %s" % shlex.quote(str(Path(vault) / "scripts" / "turn-end-commit.py"))}
    ]}]}}


# A hook naming a wiki that is not the one being checked: a wiki that has been
# moved or renamed since the hook was entered, or a second wiki on the same Mac.
SAVING_ELSEWHERE = {"hooks": {"Stop": [{"hooks": [
    {"type": "command", "command": "python3 '/somewhere/another wiki/scripts/turn-end-commit.py'"}]}]}}


def saving_home(work, name, settings=None, records=None):
    """A practice home folder: a settings file that may register the save, and
    a record file that may hold what the last run did."""
    home = work / name
    (home / ".claude").mkdir(parents=True, exist_ok=True)
    (home / ".config" / "moblee" / "state").mkdir(parents=True, exist_ok=True)
    settings_path = home / ".claude" / "settings.json"
    if settings is not None:
        settings_path.write_text(json.dumps(settings, indent=1))
    state = home / ".config" / "moblee" / "state" / "turn-end-commit.json"
    if records is not None:
        state.write_text(records if isinstance(records, str)
                         else json.dumps(records, indent=1))
    return home, settings_path, state


def saving_rows(doctor, vault, assistant="claude", settings=None, state=None, codex=None,
                proving=False):
    """The findings check_saving makes, with the files it reads pointed at
    practice copies rather than at this Mac's own."""
    f = doctor.Findings()
    was = (doctor.SETTINGS, doctor.CODEX_HOOKS, doctor.TURN_END_STATE)
    try:
        if settings is not None:
            doctor.SETTINGS = settings
        if codex is not None:
            doctor.CODEX_HOOKS = codex
        if state is not None:
            doctor.TURN_END_STATE = state
        doctor.check_saving(f, vault, assistant, proving=proving)
    finally:
        doctor.SETTINGS, doctor.CODEX_HOOKS, doctor.TURN_END_STATE = was
    return f.rows


def saving_wiki(root, with_script=True):
    """A wiki that does, or does not, have the end-of-reply save in it."""
    plain_wiki(root)
    if with_script:
        (root / "scripts").mkdir(exist_ok=True)
        (root / "scripts" / "turn-end-commit.py").write_text("# a stand-in for the real one\n")
    return root


# A record with page titles in it, which is what must never be printed. Both
# names are invented for this test.
SAVING_BLOCKED = {"a-conversation": {
    "session": "a-conversation", "title": "A conversation of the owner's",
    "at": "2026-10-13T09:00:00+01:00", "state": "blocked", "commits": ["abc1234"],
    "own_left": ["wiki/My Private Diagnosis.md"],
    "other_left": ["wiki/The Divorce Settlement.md"],
    "reason": "[GATE] wiki/My Private Diagnosis.md links to a page that does not exist"}}
SAVING_SECRET_NAMES = ("My Private Diagnosis", "The Divorce Settlement",
                       "links to a page that does not exist")


def test_saving(doctor, work):
    wiki = saving_wiki(work / "saving-wiki")
    nowt = saving_wiki(work / "saving-wiki-bare", with_script=False)

    # 1. Is the save registered? Four answers, and the one that cannot be told
    #    apart from a no is told apart from a no.
    home, settings, state = saving_home(work, "saving-yes", saving_settings(wiki))
    check("saving", "a settings file with the Stop hook in it reads as registered",
          doctor.saving_registered(settings, wiki) == (True, ""))
    _, plain, _ = saving_home(work, "saving-no", {"hooks": {"PreToolUse": [
        {"matcher": "Bash", "hooks": [{"command": "python3 bash-guard.py"}]}]}})
    there, said = doctor.saving_registered(plain, wiki)
    check("saving", "a settings file with other hooks but not this one reads as not registered",
          there is False and said == "", said)
    missing = work / "saving-none" / "settings.json"
    there, said = doctor.saving_registered(missing, wiki)
    check("saving", "no settings file at all is a plain no, and says there is no such file",
          there is False and "there is no" in said, said)
    broken = work / "saving-broken.json"
    broken.write_text("{not json at all")
    there, said = doctor.saving_registered(broken, wiki)
    check("saving", "a settings file that does not load is neither yes nor no",
          there is None and "could not be read" in said, said)

    # 1b. (v0.10.0) A hook naming SOME OTHER folder's copy of the script. The
    #     command carries the path as it stood when the hook was entered, so a
    #     wiki moved or renamed since, and a second wiki on the same Mac, both
    #     leave one. It saves that other folder and not this wiki, and until
    #     v0.10.0 the name alone was matched, so both read as registered and
    #     the card said "The wiki saves itself after every reply".
    _, away, _ = saving_home(work, "saving-elsewhere", SAVING_ELSEWHERE)
    there, said = doctor.saving_registered(away, wiki)
    check("saving", "a hook naming another folder's copy of the script is NOT this wiki registered",
          there is False, "%r / %s" % (there, said[:50]))
    check("saving", "and it says so in plain words: another folder is the one being saved",
          "different folder" in said and "second wiki" in said, said[:80])
    rows = saving_rows(doctor, wiki, settings=away, state=state)
    check("saving", "so it is a PROBLEM carrying F44, and the card says the wiki does NOT save itself",
          rows[0]["level"] == doctor.PROBLEM and rows[0]["guide"] == "F44"
          and doctor.card_saving(rows) == doctor.SAVING_NO, rows[0]["text"][:80])
    moved = saving_wiki(work / "saving-wiki-moved")
    check("saving", "a second wiki beside the first is told apart from it, each by its own path",
          doctor.saving_registered(settings, moved)[0] is False
          and doctor.saving_registered(saving_home(work, "saving-yes-2",
                                                   saving_settings(moved))[1], moved)[0] is True)
    # The same command spelled with ~ for the home folder, and with the quoting
    # a path holding a space needs: both are the installer's own spellings.
    under_home = work / "saving-under-home"
    tilde = saving_wiki(under_home / "a wiki of one's own")
    _, spelled, _ = saving_home(work, "saving-tilde", {"hooks": {"Stop": [{"hooks": [
        {"command": "python3 %s" % shlex.quote(str(tilde / "scripts" / "turn-end-commit.py"))}]}]}})
    check("saving", "a path holding a space and a quote mark is read back whole",
          doctor.saving_registered(spelled, tilde)[0] is True)

    # 2. The script itself. Without it in the wiki there is nothing to register.
    rows = saving_rows(doctor, nowt, settings=settings, state=state)
    check("saving", "a wiki without the end-of-reply save in it is a PROBLEM, with its code",
          len(rows) == 1 and rows[0]["level"] == doctor.PROBLEM and rows[0]["guide"] == "F44",
          str([(r["level"], r["guide"]) for r in rows]))
    check("saving", "and that row is the one the card reads, so the card says it too",
          rows[0].get("tag") == doctor.SAVING_TAG
          and doctor.card_saving(rows) == doctor.SAVING_NO)
    check("saving", "no wiki at all makes no finding here: F37 has already said so",
          saving_rows(doctor, None, settings=settings, state=state) == [])

    # 3. Registered, and not, for Claude.
    rows = saving_rows(doctor, wiki, settings=settings, state=state)
    first = rows[0]
    check("saving", "with the hook registered, Claude's line is an OK and names Claude",
          first["level"] == doctor.OK and "Claude saves the wiki" in first["text"]
          and first["guide"] is None, first["text"][:70])
    check("saving", "and the card's one line says the wiki saves itself",
          doctor.card_saving(rows) == doctor.SAVING_YES
          and doctor.SAVING_YES == "The wiki saves itself after every reply.")
    rows = saving_rows(doctor, wiki, settings=plain, state=state)
    check("saving", "with it not registered, Claude's line is a PROBLEM carrying F44",
          rows[0]["level"] == doctor.PROBLEM and rows[0]["guide"] == "F44"
          and "does not save the wiki" in rows[0]["text"], rows[0]["text"][:70])
    rows = saving_rows(doctor, wiki, settings=broken, state=state)
    check("saving", "with a settings file that does not load, it is a CANNOT TELL and not a fault",
          rows[0]["level"] == doctor.UNSURE and doctor.card_saving(rows) == doctor.SAVING_UNSURE,
          rows[0]["text"][:70])

    # 4. Both assistants: one line each, and ChatGPT's says that an entered
    #    hook is not a hook that fires, because only the owner's trust makes it
    #    one and no file on the Mac shows that.
    _, codex_yes, _ = saving_home(work, "saving-codex", None)
    codex_yes = work / "saving-codex" / "hooks.json"
    codex_yes.write_text(json.dumps({"hooks": {"Stop": [
        {"matcher": "*", "hooks": [{"command": "python3 %s" % shlex.quote(
            str(wiki / "scripts" / "turn-end-commit.py"))}]}]}}))
    rows = saving_rows(doctor, wiki, "both", settings=settings, state=state, codex=codex_yes)
    tagged = [r for r in rows if r.get("tag") == doctor.SAVING_TAG]
    check("saving", "a wiki used with both assistants gets one line for each of them",
          len(tagged) == 2 and "Claude saves" in tagged[0]["text"]
          and "ChatGPT saves the wiki" in tagged[1]["text"],
          str([r["text"][:30] for r in tagged]))
    check("saving", "and ChatGPT's line says an entered hook is not yet a hook that fires",
          "trusted" in tagged[1]["text"] and "--prove-saving" in tagged[1]["text"])
    # (v0.10.0) ChatGPT's row is CANNOT TELL and not OK. The hook is entered,
    # and whether the owner has pressed Trust is not written down anywhere on
    # the Mac, so it cannot be known that anything is saving. At OK, an
    # all-OK set of rows made the card say "The wiki saves itself after every
    # reply" — to a wiki in the commonest state a fresh ChatGPT wiki is in,
    # entered and not yet trusted, where nothing whatever was saving.
    check("saving", "ChatGPT's entered-but-unproved hook is a CANNOT TELL, not an OK",
          tagged[1]["level"] == doctor.UNSURE, tagged[1]["level"])
    check("saving", "so for ChatGPT alone the card says it cannot be told, not that it saves",
          doctor.card_saving(saving_rows(doctor, wiki, "chatgpt", settings=settings,
                                         state=state, codex=codex_yes))
          == doctor.SAVING_UNSURE)
    check("saving", "and with Claude saving too the answer is still neither yes nor no",
          doctor.card_saving(rows) == doctor.SAVING_UNSURE, doctor.card_saving(rows))
    # (v0.10.0) And the steps the owner is given name BOTH of Moblee's hooks.
    # This release enters two of them and step 4 named only the delete guard,
    # so an owner who did as they were told trusted one and left the other,
    # and nothing said which was which.
    check("saving", "the Trust steps name both hooks, not only the delete guard",
          "each hook Moblee has entered" in doctor.TRUST_STEPS
          and "turn-end-commit.py, which saves your wiki" in doctor.TRUST_STEPS
          and "bash-guard.py, which is the delete guard" in doctor.TRUST_STEPS,
          doctor.TRUST_STEPS[-220:])
    check("saving", "with one assistant saving and the other not, the card says it does not",
          doctor.card_saving(saving_rows(doctor, wiki, "both", settings=settings, state=state,
                                         codex=plain)) == doctor.SAVING_NO)

    # 5. What the last run did, state by state.
    def record_row(records):
        _, _, st = saving_home(work, "saving-rec-%d" % abs(hash(str(records)) % 10 ** 8), None, records)
        rows = saving_rows(doctor, wiki, settings=settings, state=st)
        return [r for r in rows if "end-of-reply save" in r["text"]
                and not r.get("tag") and "recorded at" not in r["text"]][0]

    def one(state, **extra):
        return {"c": dict({"session": "c", "title": "t", "at": "2026-10-12T08:00:00+01:00",
                           "state": state, "commits": ["abc1234"], "own_left": [],
                           "other_left": [], "yours_left": [], "staged_left": [],
                           "reason": ""}, **extra)}

    row = record_row(one("committed"))
    check("saving", "a last save that went through is an OK that says the day and the count",
          row["level"] == doctor.OK and "2026-10-12" in row["text"] and "1 commit" in row["text"],
          row["text"][:80])
    check("saving", "a last save with nothing to do is an OK and not a fault",
          record_row(one("clean"))["level"] == doctor.OK)
    check("saving", "a save that stood aside for another one is an OK too",
          record_row(one("busy"))["level"] == doctor.OK)

    # (v0.10.0) The three states the end-of-reply save learned to tell apart,
    # and the old wording that was wrong about all of them. "busy" used to
    # cover every one, and the check-up filed it as OK saying "something else
    # was already saving the wiki. The next reply's save takes whatever it
    # missed" — which for a leftover lock file was false twice over.
    row = record_row(one("locked"))
    check("saving", "a leftover git lock file is a PROBLEM carrying F49, not an OK",
          row["level"] == doctor.PROBLEM and row["guide"] == "F49", row["text"][:80])
    check("saving", "and it says plainly that the next save will not take it either",
          "nor will the next one" in row["text"] and "index.lock" in row["text"],
          row["text"][:110])
    check("saving", "nothing says something else was saving the wiki, because nothing was",
          "already saving" not in row["text"])
    row = record_row(one("detached"))
    check("saving", "a save refused because the history was not on a branch is a LOOK with F49",
          row["level"] == doctor.LOOK and row["guide"] == "F49"
          and "not on a branch" in row["text"], row["text"][:80])
    check("saving", "and it says nothing is lost and that saves start again by themselves",
          "Nothing is lost" in row["text"] and "start again by themselves" in row["text"])
    row = record_row(one("paused"))
    check("saving", "a save that stood aside for a change git was making is an OK, nothing lost",
          row["level"] == doctor.OK and "middle of a change" in row["text"]
          and "Nothing was lost" in row["text"], row["text"][:80])
    row = record_row(one("yours"))
    check("saving", "a save whose only leftovers were the owner's own is an OK that says so",
          row["level"] == doctor.OK and "never commits" in row["text"], row["text"][:90])

    # A record with no time in it. Every one of these sentences used to be
    # built round a bare ", on ," with a hole where the date should be.
    for said in ("committed", "clean", "busy", "paused", "locked", "detached",
                 "blocked", "error", "something new", "yours"):
        row = record_row(one(said, at=""))
        check("saving", "a record with no date in it still reads as a whole sentence (%s)" % said,
              ", on ," not in row["text"] and ", on ." not in row["text"]
              and "save ," not in row["text"], row["text"][:70])

    # What the save left for the owner, said whatever else it did. A row that
    # is not there at all reads as a missing sentence rather than stopping the
    # whole suite, which is how the case before the fix shows itself.
    def saying(rows, phrase):
        found = [r for r in rows if phrase in r["text"]]
        return found[0] if found else {"level": "", "text": "", "guide": None}

    row = saying(saving_rows(
        doctor, wiki, settings=settings,
        state=saving_home(work, "saving-yours", None,
                          one("committed", yours_left=["CLAUDE.md"],
                              staged_left=["wiki/A Private Page.md"]))[2]),
        "work of your own")
    check("saving", "the files left for the owner's own commit are counted on their own line",
          row["level"] == doctor.OK and "2 files" in row["text"]
          and "Nothing of yours was committed" in row["text"], row["text"][:100])
    check("saving", "and not one of their names is printed, because a file name is a page title",
          "CLAUDE.md" not in row["text"] and "A Private Page" not in row["text"])

    row = record_row(SAVING_BLOCKED)
    check("saving", "a save the commit gate stopped is a LOOK carrying F45, with the count",
          row["level"] == doctor.LOOK and row["guide"] == "F45" and "2 files" in row["text"],
          row["text"][:90])
    row = record_row(one("error"))
    check("saving", "a save that ended in an error is a LOOK carrying F45, pointing at the log",
          row["level"] == doctor.LOOK and row["guide"] == "F45"
          and "turn-end-commit.log" in row["text"], row["text"][:90])
    row = record_row(one("something new"))
    check("saving", "a record this check-up cannot read is a CANNOT TELL, not a guess",
          row["level"] == doctor.UNSURE and "cannot be told" in row["text"], row["text"][:80])

    # 6. The hard one: a record names pages, and no page name may be printed.
    _, _, blocked_state = saving_home(work, "saving-blocked", None, SAVING_BLOCKED)
    rows = saving_rows(doctor, wiki, "both", settings=settings, state=blocked_state, codex=codex_yes)
    printed = " ".join(r["text"] + " " + str(r.get("sendable", "")) for r in rows)
    card, text = card_of(doctor, rows, wiki)
    leaked = [n for n in SAVING_SECRET_NAMES if n in printed or n in text]
    check("saving", "not one page name out of the record reaches the screen or the card",
          not leaked, "; ".join(leaked))
    check("saving", "and the account folder is written as ~ wherever a path is given",
          "/Users/" not in printed and str(Path.home()) not in printed)

    # 7. Where the record is kept, which is a fact and not a fault.
    rows = saving_rows(doctor, wiki, settings=settings, state=state)
    where = [r for r in rows if "recorded at" in r["text"]]
    check("saving", "one line says where the record and the log are kept, at OK with no code",
          len(where) == 1 and where[0]["level"] == doctor.OK and where[0]["guide"] is None
          and "turn-end-commit.json" in where[0]["text"]
          and "turn-end-commit.log" in where[0]["text"], where[0]["text"][:90] if where else "")
    check("saving", "and it says the thirty days the records are kept for",
          bool(where) and "thirty days" in where[0]["text"])

    # 8. No record at all: a CANNOT TELL, because a hook can be registered and
    #    never fire, and nothing on screen would say which.
    _, _, empty = saving_home(work, "saving-fresh", None, {})
    rows = saving_rows(doctor, wiki, settings=settings, state=empty)
    fresh = [r for r in rows if r["guide"] == "F46"]
    check("saving", "no record yet is a CANNOT TELL carrying F46, and offers the proof",
          len(fresh) == 1 and fresh[0]["level"] == doctor.UNSURE and fresh[0]["guide"] == "F46"
          and "--prove-saving" in fresh[0]["text"], str(fresh)[:90])
    # (v0.10.0) Not a LOOK. Nothing is wrong: this is what every Mac looks like
    # for the first few minutes after an update, and a LOOK made the card say
    # "This wiki needs attention: 1 thing to look at" about a wiki with nothing
    # whatever the matter with it.
    check("saving", "and it does not make the card call the wiki unwell",
          card_of(doctor, rows, wiki)[0]["headline"]
          == doctor.CARD_HEADLINES["unchecked"].format(unseen=doctor.things(1)),
          card_of(doctor, rows, wiki)[0]["headline"])
    # And with --prove-saving in the same run, the line goes: the proof a few
    # lines below is the answer, and telling the owner to run the very thing
    # they are running is worse than saying nothing.
    told = saving_rows(doctor, wiki, settings=settings, state=empty, proving=True)
    check("saving", "with --prove-saving in the same run it is not said at all",
          not [r for r in told if r["guide"] == "F46"],
          str([r["text"][:40] for r in told]))
    check("saving", "and a record file that cannot be read is a CANNOT TELL instead",
          any(r["level"] == doctor.UNSURE and "could not be read" in r["text"]
              for r in saving_rows(doctor, wiki, settings=settings, state=broken)))

    # 8b. (v0.10.0) A leftover git lock file in the wiki itself, read as it
    #     stands now. While it is there nothing in the wiki saves at all.
    def locked_wiki(name, age_seconds):
        """A wiki with a git lock file in it, of a given age, and a settings
        file registering the end-of-reply save for that wiki."""
        root = saving_wiki(work / name)
        (root / ".git").mkdir(exist_ok=True)
        lock = root / ".git" / "index.lock"
        lock.write_text("a lock file of the kind git leaves while it works\n")
        when = time.time() - age_seconds
        os.utime(lock, (when, when))
        return root, saving_home(work, name + "-home", saving_settings(root))[1]

    stale, stale_settings = locked_wiki("saving-locked", 3 * 3600)
    rows = saving_rows(doctor, stale, settings=stale_settings, state=state)
    stuck = saying(rows, "lock file left behind")
    check("saving", "a git lock file hours old in the wiki is a PROBLEM carrying F49",
          stuck["level"] == doctor.PROBLEM and stuck["guide"] == "F49",
          str([(r["level"], r["guide"]) for r in rows]))
    check("saving", "and it says how long, and that nothing in the wiki is changed by it",
          "180 minutes" in stuck["text"]
          and "nothing in the wiki is changed" in stuck["text"], stuck["text"][:130])
    live, live_settings = locked_wiki("saving-lock-fresh", 1)
    check("saving", "a lock file a moment old is a live git command and is not reported",
          doctor.stale_index_lock(live) is None
          and not [r for r in saving_rows(doctor, live, settings=live_settings, state=state)
                   if "lock file left behind" in r["text"]])

    # 9. The card's one line, in every state, and the card still one screen.
    check("saving", "with nothing tagged the card says nothing about saving, rather than guessing",
          doctor.card_saving(made_rows(doctor, [(doctor.OK, None)])) == ""
          and "saves itself" not in card_of(doctor, made_rows(doctor, [(doctor.OK, None)]))[1])
    rows = saving_rows(doctor, wiki, settings=settings, state=state)
    card, text = card_of(doctor, rows, wiki)
    # Under the headline, which may run to more than one line, and above the
    # blank line that starts the lists.
    head_lines = card["lines"].index("") if "" in card["lines"] else len(card["lines"])
    check("saving", "the line is on the card, under the headline, and in what a program reads",
          card["saving"] == doctor.SAVING_YES
          and card["lines"][head_lines - 1] == doctor.SAVING_YES,
          "; ".join(card["lines"][:head_lines]))
    big = saving_rows(doctor, wiki, "both", settings=plain, state=blocked_state, codex=plain) \
        + made_rows(doctor, [(doctor.PROBLEM, "F41")] * 6 + [(doctor.UNSEEN, "F31")] * 4)
    card, text = card_of(doctor, big, wiki)
    check("saving", "and it is still one screen with the line on it, however much else is wrong",
          len(card["lines"]) <= doctor.CARD_LINES
          and max(len(l) for l in card["lines"]) <= doctor.CARD_WIDTH
          and doctor.SAVING_NO in card["lines"],
          "%d lines, longest %d" % (len(card["lines"]), max(len(l) for l in card["lines"])))


# ---------------------------------- the proof that the save really does fire
# A stand-in for the assistant's own command-line program. It does what the
# real one is asked to do — one line added to one page — and then runs the
# pack's own end-of-reply save exactly as the Stop hook runs it, on the wiki and
# the record file the proof pointed it at. So the record and the commit the
# proof reads are real ones, written by the real script.
SAVE_STUB = """#!/usr/bin/env python3
import json, os, pathlib, subprocess, sys
vault = pathlib.Path(os.environ["MOBLEE_VAULT"])
page = vault / "wiki" / "page.md"
if "QUIETLY_DO_NOTHING" not in os.environ:
    with page.open("a") as fh:
        fh.write(PROMPT_LINE + "\\n")
if "QUIETLY_SKIP_THE_HOOK" not in os.environ:
    payload = json.dumps({"session_id": "a-practice-conversation",
                          "transcript_path": None, "hook_event_name": "Stop"})
    subprocess.run([sys.executable, SCRIPT, "--now"], input=payload, text=True,
                   capture_output=True)
print("done")
"""


def put_save_stub_on_path(work, doctor):
    bindir = work / "save-stub-bin"
    bindir.mkdir(parents=True, exist_ok=True)
    body = (SAVE_STUB.replace("PROMPT_LINE", json.dumps(doctor.PROVE_SAVING_LINE))
            .replace("SCRIPT", json.dumps(str(PACK / "scripts" / "turn-end-commit.py"))))
    for name in ("claude", "codex"):
        stub = bindir / name
        stub.write_text(body)
        stub.chmod(stub.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    os.environ["PATH"] = str(bindir) + os.pathsep + os.environ.get("PATH", "")
    return bindir / "claude"


def prove_saving_rows(doctor, work, name, settings, vault=None, env=None):
    """prove_saving run against a practice CONFIG folder, so the scratch wiki
    it makes and leaves is under the test's own working folder."""
    f = doctor.Findings()
    was_config, was_settings = doctor.CONFIG, doctor.SETTINGS
    added = dict(env or {})
    for key, value in added.items():
        os.environ[key] = value
    try:
        doctor.CONFIG = work / name
        doctor.SETTINGS = settings
        doctor.prove_saving(f, PACK, vault, "claude", announce=False, timeout=60)
    finally:
        doctor.CONFIG, doctor.SETTINGS = was_config, was_settings
        for key in added:
            os.environ.pop(key, None)
    return f.rows


def test_prove_saving(doctor, work):
    # The owner's own wiki, which is the one the hook has to be registered for.
    # The proof works in a scratch wiki, but it will not run at all until the
    # hook names THIS one, which is what the registration check is about.
    owners = saving_wiki(work / "prove-wiki")
    _, settings, _ = saving_home(work, "prove-yes", saving_settings(owners))
    _, plain, _ = saving_home(work, "prove-no", {"hooks": {}})
    _, away, _ = saving_home(work, "prove-elsewhere", SAVING_ELSEWHERE)

    # 1. Nothing to prove until the hook is registered, and the proof says so
    #    rather than asking the assistant and spending the owner's allowance.
    put_save_stub_on_path(work, doctor)
    rows = prove_saving_rows(doctor, work, "prove-unregistered", plain, owners)
    check("prove", "with the save not registered the proof is not run, and says that comes first",
          len(rows) == 1 and rows[0]["level"] == doctor.UNSURE
          and "that comes first" in rows[0]["text"], str(rows)[:120])
    # (v0.10.0) A hook naming some other folder is not this wiki registered,
    # so the proof must not run on the strength of it either.
    rows = prove_saving_rows(doctor, work, "prove-elsewhere-run", away, owners)
    check("prove", "a hook naming another folder does not count as registered for the proof",
          len(rows) == 1 and rows[0]["level"] == doctor.UNSURE
          and "that comes first" in rows[0]["text"], str(rows)[:120])

    # 2. The real thing: the stub makes the edit, the pack's own script saves it
    #    as the Stop hook would, and the proof reads the commit and the record.
    rows = prove_saving_rows(doctor, work, "prove-real", settings, owners)
    proved = [r for r in rows if r["text"].startswith("Proved:")]
    check("prove", "a save that really ran is proved, in the pack's own word for it",
          len(proved) == 1 and proved[0]["level"] == doctor.OK, str([r["text"][:70] for r in rows]))
    check("prove", "and the proved line says where the scratch wiki was left, as the guard's does",
          bool(proved) and "is left at" in proved[0]["text"])
    scratch = sorted((work / "prove-real" / "prove-saving").iterdir())
    check("prove", "the scratch wiki is left where it is, under the pack's own folder",
          len(scratch) == 1 and (scratch[0] / "practice-wiki" / ".git").is_dir(),
          str(scratch))
    if scratch:
        made = scratch[0] / "practice-wiki"
        code, out = doctor.run(["git", "-C", str(made), "log", "--format=%s"])
        check("prove", "the commit in the scratch wiki was made by the end-of-reply save itself",
              "saved automatically" in out, out.splitlines()[:1])
        check("prove", "the gate was wired into it, so the save went through the gate as on any commit",
              (made / "scripts" / "hooks" / "pre-commit").is_file()
              and (made / "scripts" / "vault-gate.py").is_file())
        record = json.loads((scratch[0] / "record.json").read_text())
        check("prove", "and the record was written beside it, not into the owner's own",
              any(v.get("state") == "committed" for v in record.values()), str(record)[:80])
        check("prove", "the owner's wiki is nowhere in it: the practice one is what was saved",
              (made / "wiki" / "page.md").read_text().count(doctor.PROVE_SAVING_LINE) == 1)

    # 3. The assistant made the edit and nothing saved it: that is the fault the
    #    proof exists to find.
    rows = prove_saving_rows(doctor, work, "prove-silent", settings, owners,
                             env={"QUIETLY_SKIP_THE_HOOK": "1"})
    check("prove", "an edit that nothing saved is a PROBLEM carrying F44",
          len(rows) == 1 and rows[0]["level"] == doctor.PROBLEM and rows[0]["guide"] == "F44"
          and "not running" in rows[0]["text"], str(rows)[:140])

    # 4. The assistant did nothing at all: neither proved nor disproved, which
    #    is not the same as proving the save broken.
    rows = prove_saving_rows(doctor, work, "prove-nothing", settings, owners,
                             env={"QUIETLY_DO_NOTHING": "1", "QUIETLY_SKIP_THE_HOOK": "1"})
    check("prove", "an assistant that made no edit leaves it neither proved nor disproved",
          len(rows) == 1 and rows[0]["level"] == doctor.UNSURE
          and "neither proved nor disproved" in rows[0]["text"], str(rows)[:140])

    # 5. No assistant program on this Mac: a CANNOT TELL, and no fault laid at
    #    the wiki's door.
    f = doctor.Findings()
    was = doctor.CLAUDE_ELSEWHERE
    path_was = os.environ.get("PATH", "")
    try:
        doctor.CLAUDE_ELSEWHERE = ()
        os.environ["PATH"] = str(work / "nothing-here")
        doctor.prove_saving(f, PACK, owners, "claude", announce=False, timeout=5)
    finally:
        doctor.CLAUDE_ELSEWHERE = was
        os.environ["PATH"] = path_was
    check("prove", "with no assistant program found, the proof is a CANNOT TELL and blames nothing",
          len(f.rows) == 1 and f.rows[0]["level"] == doctor.UNSURE
          and "was not found on this Mac" in f.rows[0]["text"], str(f.rows)[:140])
    check("prove", "the proof names its own timeout in words, as the guard's proof does",
          doctor.prove_limit_words(doctor.PROVE_SAVING_TIMEOUT) == "three minutes",
          doctor.prove_limit_words(doctor.PROVE_SAVING_TIMEOUT))


# ------------------------------------------------- Claude's own additions (mods)
# The band above the prompt is a Claude mod. Moblee keeps it in the wiki, at
# scripts/claude-mods/, and registers it with Claude from there. Mods arrived in
# Claude 2.1.287, so Moblee has to find a Claude new enough before it runs any
# of the plugin commands at all, and an owner whose Claude is older must be told
# in plain words rather than shown a failure.
#
# Every engine here is a stub: a little script that prints a version, records
# every call it was given, and answers `plugin list` with whatever the case
# wants. That is enough to assert which engine was chosen and which commands
# would be run, and nothing is installed anywhere.
def engine_stub(path, version, calls=None, listing="", json_listing=None, list_code=0):
    path.parent.mkdir(parents=True, exist_ok=True)
    body = ["#!/bin/sh"]
    if calls is not None:
        body.append('printf "%%s\\n" "$*" >> %s' % shlex.quote(str(calls)))
    body.append('if [ "$1" = "--version" ]; then printf "%%s (Claude Code)\\n" %s; exit 0; fi'
                % shlex.quote(version))
    if json_listing is None:
        # an engine too old to answer in JSON
        body.append('if [ "$*" = "plugin list --json" ]; then printf "unknown option\\n" >&2; exit 2; fi')
    else:
        body.append('if [ "$*" = "plugin list --json" ]; then printf "%%s\\n" %s; exit %d; fi'
                    % (shlex.quote(json_listing), list_code))
    body.append('if [ "$*" = "plugin list" ]; then printf "%%s\\n" %s; exit %d; fi'
                % (shlex.quote(listing), list_code))
    body.append("exit 0")
    path.write_text("\n".join(body) + "\n")
    path.chmod(0o755)
    return path


def app_engine_stub(root, version, build="9d6405864fdc", **kw):
    """An engine where the Claude app keeps its own: one folder per version,
    with a build folder inside it."""
    return engine_stub(root / version / build / "claude.app" / "Contents" / "MacOS" / "claude",
                       version, **kw)


def mods_wiki(root, with_mods=True):
    """A wiki that does, or does not, hold Claude's own additions."""
    plain_wiki(root)
    if with_mods:
        folder = root / "scripts" / "claude-mods"
        (folder / ".claude-plugin").mkdir(parents=True, exist_ok=True)
        (folder / ".claude-plugin" / "marketplace.json").write_text(
            json.dumps({"name": "moblee-mods", "plugins": []}))
        (folder / "cold-cache-warning").mkdir(exist_ok=True)
    return root


def mods_listing(vault, enabled=True, read_from=None):
    """What `plugin list --json` says when the band is installed."""
    folder = read_from or str(Path(vault) / "scripts" / "claude-mods" / "cold-cache-warning")
    return json.dumps([{"id": "cold-cache-warning@moblee-mods", "version": "1.0.0",
                        "scope": "user", "enabled": enabled, "readFromFolder": folder}])


def with_engines(doctor, path_dir, app_root, fn, elsewhere=()):
    """Run something with the three places Moblee looks for a Claude pointed at
    practice copies: the PATH, the places a Claude really sits on a Mac, and the
    folder the Claude app keeps its own in.

    The third is overridden even where a case does not use it, so that a real
    Claude in ~/.local/bin or under Homebrew on whichever Mac this runs on can
    never change the answer."""
    was = (os.environ.get("PATH", ""), doctor.CLAUDE_APP_ENGINES, doctor.CLAUDE_ELSEWHERE)
    try:
        os.environ["PATH"] = str(path_dir)
        doctor.CLAUDE_APP_ENGINES = Path(app_root)
        doctor.CLAUDE_ELSEWHERE = tuple(Path(p) for p in elsewhere)
        return fn()
    finally:
        os.environ["PATH"], doctor.CLAUDE_APP_ENGINES, doctor.CLAUDE_ELSEWHERE = was


def mods_rows(doctor, vault, path_dir, app_root, assistant="claude", elsewhere=()):
    f = doctor.Findings()
    with_engines(doctor, path_dir, app_root, lambda: doctor.check_mods(f, vault, assistant),
                 elsewhere)
    return f.rows


def test_mods(doctor, work):
    root = work / "mods"
    wiki = mods_wiki(root / "wiki")
    bare = mods_wiki(root / "wiki-without", with_mods=False)
    empty = root / "no-engine-anywhere"
    empty.mkdir(parents=True, exist_ok=True)

    # 1. Which Claude is chosen, and from where. This Mac is the real case the
    #    two branches were written for: a `claude` on the PATH that is too old,
    #    and the Claude app's own engine, which is not.
    on_path = root / "path-new"
    engine_stub(on_path / "claude", "2.1.295", calls=root / "path-new-calls.txt")
    found = with_engines(doctor, on_path, empty, doctor.find_mods_engine)
    check("mods", "a Claude new enough on the PATH is the one chosen",
          found[0] == str(on_path / "claude") and found[1] == (2, 1, 295), str(found))

    old_path = root / "path-old"
    engine_stub(old_path / "claude", "2.1.277", calls=root / "path-old-calls.txt")
    app_new = root / "app-new"
    app_engine_stub(app_new, "2.1.295")
    app_engine_stub(app_new, "2.1.9", build="aaaaaaaaaaaa")
    found = with_engines(doctor, old_path, app_new, doctor.find_mods_engine)
    check("mods", "a Claude on the PATH that is too old is rejected, and the app's own engine taken",
          found[0] is not None and "claude.app" in found[0] and found[1] == (2, 1, 295), str(found))
    check("mods", "and the newest of the app's engines is the one taken, by number and not by name",
          "2.1.295" in str(found[0]) and "2.1.9" not in str(found[0]), str(found[0]))

    app_old = root / "app-old"
    app_engine_stub(app_old, "2.1.200", build="bbbbbbbbbbbb")
    found = with_engines(doctor, old_path, app_old, doctor.find_mods_engine)
    check("mods", "with nothing new enough in either place, no engine is chosen",
          found[0] is None and found[1] is None, str(found))
    check("mods", "and the newest version seen at all is still handed back, so the finding can say it",
          found[2] == (2, 1, 277), str(found[2]))

    found = with_engines(doctor, empty, empty, doctor.find_mods_engine)
    check("mods", "with no Claude on the Mac at all, nothing is chosen and nothing is claimed",
          found == (None, None, None), str(found))

    # 1b. (v0.10.0) The places a Claude really sits on a Mac, which `which`
    #     cannot see from inside the Moblee app: the app runs the check-up from
    #     a window and hands over a PATH of the four system folders and nothing
    #     else. An owner with Claude Code but no Claude app was therefore told,
    #     on every press of Check my wiki, that their Claude was too old —
    #     about a Claude the check-up had never found.
    tucked = root / "tucked-away"
    engine_stub(tucked / "claude", "2.1.295")
    found = with_engines(doctor, empty, empty, doctor.find_mods_engine,
                         elsewhere=[tucked / "claude"])
    check("mods", "a Claude off the PATH, where one really sits on a Mac, is still found",
          found[0] == str(tucked / "claude") and found[1] == (2, 1, 295), str(found))
    rows = mods_rows(doctor, wiki, empty, empty, elsewhere=[tucked / "claude"])
    check("mods", "so the check-up does not call that Mac's Claude too old",
          not any("older than the band" in r["text"] for r in rows),
          str([r["text"][:50] for r in rows]))

    # 2. The line itself. 2.1.287 is where mods arrived, so it is in and the
    #    version before it is out.
    edge_in, edge_out = root / "edge-in", root / "edge-out"
    engine_stub(edge_in / "claude", "2.1.287")
    engine_stub(edge_out / "claude", "2.1.286")
    check("mods", "2.1.287, the version mods arrived in, is new enough",
          with_engines(doctor, edge_in, empty, doctor.find_mods_engine)[1] == (2, 1, 287))
    check("mods", "and 2.1.286, the version before it, is not",
          with_engines(doctor, edge_out, empty, doctor.find_mods_engine)[0] is None)

    # 3. A wiki used with ChatGPT alone: one sentence, and no fault reported.
    rows = mods_rows(doctor, wiki, on_path, empty, assistant="chatgpt")
    check("mods", "for ChatGPT alone the whole thing is skipped in one sentence, as an OK",
          len(rows) == 1 and rows[0]["level"] == doctor.OK
          and rows[0]["text"] == doctor.MODS_CHATGPT and rows[0]["guide"] is None,
          rows[0]["text"] if rows else "no rows")
    check("mods", "and that sentence says it is one of Claude's own additions, not that anything is missing",
          "nothing to install for a wiki used with ChatGPT alone" in doctor.MODS_CHATGPT
          and "ChatGPT" in doctor.MODS_CHATGPT)
    check("mods", "no wiki at all makes no finding here: F37 has already said so",
          mods_rows(doctor, None, on_path, empty) == [])

    # 4. No Claude new enough: the one plain sentence, word for word, with the
    #    versions said after it and not inside it.
    rows = mods_rows(doctor, wiki, old_path, app_old)
    # (v0.10.0) An OK and not a LOOK. The sentence's own words are that the
    # band appears by itself once Claude has updated and that nothing else is
    # affected; at LOOK it made the health card say "This wiki needs attention"
    # about a wiki with nothing the matter with it, and the reassuring half of
    # the sentence was cut off the card for room.
    check("mods", "with a Claude too old, the finding is an OK and does not call the wiki unwell",
          len(rows) == 1 and rows[0]["level"] == doctor.OK and rows[0]["guide"] == "F48",
          str([(r["level"], r["guide"]) for r in rows]))
    check("mods", "and the card says the wiki looks healthy rather than needing attention",
          card_of(doctor, rows, wiki)[0]["headline"] == doctor.CARD_HEADLINES["healthy"],
          card_of(doctor, rows, wiki)[0]["headline"])
    check("mods", "and it opens with the one plain sentence, word for word",
          rows[0]["text"].startswith(doctor.MODS_NO_ENGINE), rows[0]["text"][:90])
    check("mods", "the sentence says the band comes on its own and that nothing else is affected",
          "once Claude has updated itself" in doctor.MODS_NO_ENGINE
          and "nothing else is affected" in doctor.MODS_NO_ENGINE)
    check("mods", "and the finding says which version is needed and what was found",
          "2.1.287" in rows[0]["text"] and "2.1.277" in rows[0]["text"], rows[0]["text"][-80:])
    rows = mods_rows(doctor, wiki, empty, empty)
    check("mods", "with no Claude at all it says so rather than naming a version it never saw",
          rows[0]["guide"] == "F48" and "no Claude could be found" in rows[0]["text"],
          rows[0]["text"][-70:])
    # (v0.10.0) And it is a sentence of its own, at CANNOT TELL. Glued onto the
    # too-old sentence it read "The Claude on this Mac is older than the band
    # needs … (no Claude could be found on this Mac to ask)" — a sentence
    # asserting a Claude exists, with a bracket saying none does.
    check("mods", "with no Claude at all the answer is CANNOT TELL, not a verdict on a version",
          len(rows) == 1 and rows[0]["level"] == doctor.UNSURE, str([r["level"] for r in rows]))
    check("mods", "and it does not also say the Claude on this Mac is too old, there being none",
          doctor.MODS_NO_ENGINE not in rows[0]["text"]
          and "older than the band" not in rows[0]["text"], rows[0]["text"][:90])
    check("mods", "it says instead that nothing in the wiki depends on the band",
          "nothing in the wiki depends on it" in rows[0]["text"], rows[0]["text"][-70:])

    # 5. The wiki without the mods in it: nothing to install from.
    rows = mods_rows(doctor, bare, on_path, empty)
    check("mods", "a wiki that does not hold Claude's own additions is a LOOK carrying F47",
          len(rows) == 1 and rows[0]["level"] == doctor.LOOK and rows[0]["guide"] == "F47"
          and "scripts/claude-mods" in rows[0]["text"],
          str([(r["level"], r["guide"]) for r in rows]))
    check("mods", "and it is said before any Claude is asked anything, since there is nothing to ask about",
          not (root / "path-new-calls.txt").exists()
          or "plugin" not in (root / "path-new-calls.txt").read_text())

    # 6. Installed and switched on, read from the wiki's own copy: an OK.
    ok_engine = root / "engine-ok"
    engine_stub(ok_engine / "claude", "2.1.295", calls=root / "ok-calls.txt",
                json_listing=mods_listing(wiki))
    rows = mods_rows(doctor, wiki, ok_engine, empty)
    check("mods", "installed and switched on, read from the wiki, is an OK with no code",
          len(rows) == 1 and rows[0]["level"] == doctor.OK and rows[0]["guide"] is None
          and "installed and switched on" in rows[0]["text"], str(rows))
    check("mods", "and it names the wiki's own folder and the Claude that answered",
          "scripts/claude-mods" in rows[0]["text"] and "2.1.295" in rows[0]["text"],
          rows[0]["text"])
    check("mods", "Claude was asked for its list rather than its files being read behind its back",
          "plugin list --json" in (root / "ok-calls.txt").read_text(),
          (root / "ok-calls.txt").read_text().replace("\n", " | "))

    # 7. Not installed, switched off, and read from somewhere else: three
    #    different things to tell an owner, all under F47.
    none_engine = root / "engine-none"
    engine_stub(none_engine / "claude", "2.1.295", json_listing="[]")
    rows = mods_rows(doctor, wiki, none_engine, empty)
    check("mods", "a Claude that has it not installed is a LOOK carrying F47",
          rows[0]["level"] == doctor.LOOK and rows[0]["guide"] == "F47"
          and "not installed" in rows[0]["text"], rows[0]["text"][:80])

    off_engine = root / "engine-off"
    engine_stub(off_engine / "claude", "2.1.295", json_listing=mods_listing(wiki, enabled=False))
    rows = mods_rows(doctor, wiki, off_engine, empty)
    check("mods", "installed but switched off is told apart from not installed, under the same code",
          rows[0]["level"] == doctor.LOOK and rows[0]["guide"] == "F47"
          and "switched off" in rows[0]["text"], rows[0]["text"][:80])

    moved_engine = root / "engine-moved"
    engine_stub(moved_engine / "claude", "2.1.295",
                json_listing=mods_listing(wiki, read_from=str(root / "an-older-wiki" / "scripts"
                                                              / "claude-mods" / "cold-cache-warning")))
    rows = mods_rows(doctor, wiki, moved_engine, empty)
    check("mods", "a band Claude reads from another folder is a LOOK: an update to the wiki never reaches it",
          rows[0]["level"] == doctor.LOOK and rows[0]["guide"] == "F47"
          and "not from this wiki" in rows[0]["text"], rows[0]["text"][:100])
    # (v0.10.0) The fault goes first in the sentence. Shortened for the health
    # card, the old wording came out as "Claude's band above the prompt is
    # installed and switched..." — reassurance, for the finding that says the
    # opposite, and the card is the one screen a helper is handed.
    line = doctor.card_line(rows[0], str)
    check("mods", "and shortened for the card it cannot be read as all being well",
          "is installed and switched" not in line
          and line.startswith("Claude reads the band above the prompt from another folder"), line)

    # 8. An engine that cannot answer, and one too old to answer in JSON. The
    #    first is a CANNOT TELL and not a fault; the second is installed, and
    #    whether it is switched on is left unclaimed.
    mute_engine = root / "engine-mute"
    engine_stub(mute_engine / "claude", "2.1.295", json_listing="not json at all", list_code=1)
    rows = mods_rows(doctor, wiki, mute_engine, empty)
    check("mods", "a Claude that will not say what it has installed is a CANNOT TELL, not a fault",
          rows[0]["level"] == doctor.UNSURE and rows[0]["guide"] is None, str(rows))

    plain_engine = root / "engine-plain"
    engine_stub(plain_engine / "claude", "2.1.295",
                listing="Installed plugins:\n  cold-cache-warning@moblee-mods\n")
    rows = mods_rows(doctor, wiki, plain_engine, empty)
    check("mods", "a Claude with no JSON listing still shows the band as installed, from the plain one",
          rows[0]["level"] == doctor.OK and "is installed" in rows[0]["text"], rows[0]["text"][:80])
    check("mods", "and that line does not claim it is switched on, which the plain listing never said",
          "does not say" in rows[0]["text"], rows[0]["text"])

    # 9. Nothing printed here carries a page title, as nothing printed by the
    #    check-up may. The band's own folder is Moblee's and holds no pages.
    for name, rowset in (("installed", mods_rows(doctor, wiki, ok_engine, empty)),
                         ("not installed", mods_rows(doctor, wiki, none_engine, empty)),
                         ("no engine", mods_rows(doctor, wiki, old_path, app_old))):
        text = " ".join(r["text"] for r in rowset)
        check("mods", f"the {name} finding names no page in the wiki", ".md" not in text, text[:60])


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
          "2 sections of your own" in said and '"Ways I like to work"' in said
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
          "is Moblee's own wording throughout" in said and "sections of your own" not in said)

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


def test_damaged_and_codex_home(doctor, work):
    """(0.16.0) A settings or rules file damaged by hand says nothing either way,
    so the guard is 'cannot tell', never 'not switched on'; and ChatGPT's files
    are read from CODEX_HOME when that is set."""
    home = work / "damaged-home"
    (home / ".claude").mkdir(parents=True, exist_ok=True)
    settings = home / ".claude" / "settings.json"
    settings.write_text('{"hooks": {"PreToolUse": [ broken')
    guard = installed_guard(work, "damaged-guard", "# the guard\n")
    was = doctor.SETTINGS, doctor.GUARD
    try:
        doctor.SETTINGS, doctor.GUARD = settings, guard
        f = doctor.Findings()
        got = doctor.check_settings(f, None)
        doctor.check_guard(f, got, PACK)
    finally:
        doctor.SETTINGS, doctor.GUARD = was
    said = " ".join(r["text"] for r in f.rows)
    check("damaged", "an unparseable Claude settings file is still reported as not loading",
          any(r["level"] == doctor.PROBLEM and "does not load" in r["text"] for r in f.rows), said[:90])
    check("damaged", "and the guard is 'cannot tell', not 'not switched on'",
          any(r["level"] == doctor.UNSURE and "cannot be told" in r["text"] for r in f.rows)
          and "not switched on" not in said, said[-120:])

    # the wiki's own rules file damaged: cannot tell, not "the rules are not there"
    vault = work / "damaged-rules-wiki"
    (vault / ".claude").mkdir(parents=True, exist_ok=True)
    (vault / ".claude" / "settings.local.json").write_text('{"permissions": {"allow": [')
    settings.write_text(json.dumps({"permissions": {}}))
    try:
        doctor.SETTINGS = settings
        f = doctor.Findings()
        doctor.check_settings(f, vault)
    finally:
        doctor.SETTINGS = was[0]
    said = " ".join(r["text"] for r in f.rows)
    check("damaged", "a damaged rules file in the wiki is 'cannot tell', not 'the rules are not in place'",
          any(r["level"] == doctor.UNSURE and "settings.local.json" in r["text"] for r in f.rows)
          and "are not in the wiki's settings" not in said, said[:140])
    (vault / ".claude" / "settings.local.json").write_text(json.dumps({"permissions": {"allow": []}}))
    f = doctor.Findings()
    try:
        doctor.SETTINGS = settings
        doctor.check_settings(f, vault)
    finally:
        doctor.SETTINGS = was[0]
    check("damaged", "a readable rules file without Moblee's rules is still told they are missing",
          any(r["guide"] == "F01" and r["level"] == doctor.PROBLEM for r in f.rows))

    # ChatGPT's folder moved by CODEX_HOME
    moved = work / "codex-moved"
    (moved / "hooks").mkdir(parents=True, exist_ok=True)
    (moved / "hooks" / "bash-guard.py").write_text((PACK / "safety" / "bash-guard.py").read_text())
    entry = {"hooks": {"PreToolUse": [{"matcher": "Bash|apply_patch", "hooks": [
        {"type": "command", "command": f'python3 "{moved}/hooks/bash-guard.py"'}]}]}}
    (moved / "hooks.json").write_text(json.dumps(entry))
    before = os.environ.get("CODEX_HOME")
    os.environ["CODEX_HOME"] = str(moved)
    try:
        d2 = load_doctor()
    finally:
        if before is None:
            os.environ.pop("CODEX_HOME", None)
        else:
            os.environ["CODEX_HOME"] = before
    check("codexhome", "with CODEX_HOME set, the check-up looks for ChatGPT's guard there",
          d2.CODEX_GUARD == moved / "hooks" / "bash-guard.py" and d2.CODEX_HOOKS == moved / "hooks.json")
    f = d2.Findings()
    in_place = d2.check_codex_guard(f, PACK)
    said = " ".join(r["text"] for r in f.rows)
    check("codexhome", "and finds it installed, entered and the pack's own copy",
          in_place and "is this Moblee's own copy" in said, said[:120])
    check("codexhome", "and names no account folder in what it prints", "/Users/" not in said, said[:80])
    (moved / "hooks.json").write_text("{")
    f = d2.Findings()
    in_place = d2.check_codex_guard(f, PACK)
    said = " ".join(r["text"] for r in f.rows)
    check("codexhome", "a damaged ChatGPT hooks file is 'cannot tell', not 'not switched on'",
          not in_place and f.rows and f.rows[0]["level"] == d2.UNSURE and "cannot be told" in said
          and "is not switched on" not in said, said[:120])
    check("codexhome", "without CODEX_HOME, ~/.codex is the folder",
          doctor.CODEX_DIR == doctor.HOME / ".codex" or os.environ.get("CODEX_HOME"))


def test_tour(doctor, work):
    """(0.16.0) The first-week tour: the wiki's scripts/first-days.py entered as
    Claude's SessionStart hook, read from the hook entries by full path, as the
    end-of-reply save is."""
    vault = work / "tour-wiki"
    (vault / "scripts").mkdir(parents=True, exist_ok=True)
    (vault / "scripts" / "first-days.py").write_text("# tour\n")
    settings = work / "tour-home" / ".claude" / "settings.json"
    settings.parent.mkdir(parents=True, exist_ok=True)

    def rows(text, assistant="claude", where=vault):
        if text is None:
            if settings.exists():
                settings.rename(settings.with_name("settings.json.moved-%d" % len(list(settings.parent.iterdir()))))
        else:
            settings.write_text(text)
        was = doctor.SETTINGS
        try:
            doctor.SETTINGS = settings
            f = doctor.Findings()
            doctor.check_tour(f, where, assistant)
        finally:
            doctor.SETTINGS = was
        return f.rows

    def entry(path):
        return json.dumps({"hooks": {"SessionStart": [{"hooks": [
            {"type": "command", "timeout": 10, "command": "python3 " + shlex.quote(str(path))}]}]}})

    r = rows(entry(vault / "scripts" / "first-days.py"))
    check("tour", "entered by its full path (with a space-free or quoted path): OK, switched on",
          len(r) == 1 and r[0]["level"] == doctor.OK and "switched on" in r[0]["text"], str(r)[:120])
    spaced = work / "tour wiki spaced"
    (spaced / "scripts").mkdir(parents=True, exist_ok=True)
    (spaced / "scripts" / "first-days.py").write_text("# tour\n")
    r = rows(entry(spaced / "scripts" / "first-days.py"), where=spaced)
    check("tour", "a wiki whose path holds a space is read as a shell reads it",
          len(r) == 1 and r[0]["level"] == doctor.OK, str(r)[:120])
    r = rows(entry(work / "elsewhere" / "scripts" / "first-days.py"))
    check("tour", "entered for another folder: LOOK, and says so",
          len(r) == 1 and r[0]["level"] == doctor.LOOK and "different folder" in r[0]["text"], str(r)[:120])
    r = rows(json.dumps({"permissions": {"allow": ["Bash(python3 scripts/first-days.py)"]}, "hooks": {}}))
    check("tour", "named only in a permission rule: not entered, LOOK with a code",
          len(r) == 1 and r[0]["level"] == doctor.LOOK and r[0]["guide"] and "never runs" in r[0]["text"], str(r)[:120])
    r = rows('{"hooks": {"SessionStart": [')
    check("tour", "an unparseable settings file: cannot tell, never 'not entered'",
          len(r) == 1 and r[0]["level"] == doctor.UNSURE and "cannot be told" in r[0]["text"], str(r)[:120])
    r = rows(entry(vault / "scripts" / "first-days.py"), assistant="chatgpt")
    check("tour", "an owner on ChatGPT alone is told nothing about it (entered for Claude only)", r == [])
    r = rows(entry(vault / "scripts" / "first-days.py"), where=work / "tour-old-wiki")
    check("tour", "a wiki from before 0.16.0, with no tour in it, adds no line (its version line covers it)", r == [])
    r = rows(None)
    check("tour", "no settings file at all: LOOK, not entered",
          len(r) == 1 and r[0]["level"] == doctor.LOOK, str(r)[:120])


def test_permissions(doctor, work):
    # (0.12.0) The builder's rules, the working mode and auto mode's exceptions,
    # read from the wiki's settings and from Claude's own settings file.
    import json as _json
    was = doctor.SETTINGS
    try:
        home = work / "perm-home"
        vault = home / "Wiki"
        (vault / "wiki").mkdir(parents=True, exist_ok=True)
        (vault / ".claude").mkdir(parents=True, exist_ok=True)
        settings = home / "settings.json"
        local = vault / ".claude" / "settings.local.json"
        old_allow = ["Bash(git add:*)"] + ["Bash(tool%d:*)" % i for i in range(49)]
        # 1. the set from before 0.12.0: wiki-only rules, no mode, no exceptions
        local.write_text(_json.dumps({"permissions": {"allow": old_allow, "deny": ["Bash(rm:*)"]}}))
        settings.write_text(_json.dumps({"permissions": {}}))
        doctor.SETTINGS = settings
        f = doctor.Findings()
        doctor.check_settings(f, vault)
        codes = [r.get("guide") for r in f.rows]
        levels = {r.get("guide"): r["level"] for r in f.rows if r.get("guide")}
        said = " ".join(r["text"] for r in f.rows)
        check("perm", "the older rule set is named, at LOOK, as F55",
              "F55" in codes and levels.get("F55") == doctor.LOOK, str(codes))
        check("perm", "with no mode set, the line says so and names what each mode does, with no code",
              "not set" in said and "Manual asks" in said and "F0" not in said.split("mode")[0][-5:], said[:120])
        check("perm", "with no auto-mode exceptions, F56 at LOOK",
              "F56" in codes and levels.get("F56") == doctor.LOOK, str(codes))
        check("perm", "F01 is not raised when fifty rules are there",
              "F01" not in codes, str(codes))
        # 2. the 0.12.0 set: the builds' home, Accept edits, both exceptions
        local.write_text(_json.dumps({"permissions": {
            "allow": old_allow + ["Read(~/Apps/**)", "Edit(~/Apps/**)"],
            "deny": ["Bash(trash:*)"],
            "defaultMode": "acceptEdits",
            "additionalDirectories": [str(home / "Apps")]}}))
        settings.write_text(_json.dumps({"permissions": {}, "autoMode": {"allow": [
            "$defaults",
            "Moblee's check-up (scripts/moblee-doctor.py) may write its health card into raw/.",
            "Moblee's end-of-reply save (scripts/turn-end-commit.py) may commit the wiki."]}}))
        f = doctor.Findings()
        doctor.check_settings(f, vault)
        codes = [r.get("guide") for r in f.rows]
        said = " ".join(r["text"] for r in f.rows)
        check("perm", "with the 0.12.0 set, neither F55 nor F56 is raised",
              "F55" not in codes and "F56" not in codes, str(codes))
        check("perm", "building outside the wiki is reported covered",
              "Building outside the wiki is covered" in said, said[:120])
        check("perm", "the mode is reported in words an owner can read",
              "Accept edits" in said and "does not ask" in said, said[:160])
        check("perm", "auto mode's exceptions are reported known",
              "knows Moblee's own check-up" in said, said[:120])
        # 3. a mode the owner chose themselves is reported as theirs, not changed
        local.write_text(_json.dumps({"permissions": {
            "allow": old_allow + ["Edit(~/Apps/**)"], "defaultMode": "plan"}}))
        f = doctor.Findings()
        doctor.check_settings(f, vault)
        said = " ".join(r["text"] for r in f.rows)
        check("perm", "an owner's own mode is read back as set", "Plan (Claude reads" in said, said[:120])
        # 4. a settings file whose autoMode is not a dict does not crash the check
        settings.write_text(_json.dumps({"permissions": {}, "autoMode": "odd"}))
        f = doctor.Findings()
        doctor.check_settings(f, vault)
        codes = [r.get("guide") for r in f.rows]
        check("perm", "an odd autoMode value reads as no exceptions, not an error", "F56" in codes, str(codes))
    finally:
        doctor.SETTINGS = was


def test_backup(doctor, work):
    # (0.12.0) the weekly copy of the wiki's history, and Time Machine
    import datetime as _dt
    import os as _os
    was_dir, was_tm = doctor.BACKUPS_DIR, doctor.tm_destination_count
    try:
        folder = work / "backups"
        folder.mkdir(parents=True, exist_ok=True)
        doctor.BACKUPS_DIR = folder
        doctor.tm_destination_count = lambda: 1
        f = doctor.Findings()
        doctor.check_backup(f, None)
        said = " ".join(r["text"] for r in f.rows)
        codes = [r.get("guide") for r in f.rows]
        check("backup", "with no copy and the weekly check not chosen, it is said at OK and no code is raised",
              "F57" not in codes and "No copy of the wiki's history" in said, str(codes))
        fresh = folder / "wiki-2026-10-17.bundle"
        fresh.write_bytes(b"x")
        f = doctor.Findings()
        doctor.check_backup(f, None)
        said = " ".join(r["text"] for r in f.rows)
        check("backup", "a copy made this week is reported at OK with its age", "day(s) old" in said and "F57" not in
              [r.get("guide") for r in f.rows], said[:120])
        old = _dt.datetime.now() - _dt.timedelta(days=40)
        _os.utime(fresh, (old.timestamp(), old.timestamp()))
        f = doctor.Findings()
        doctor.check_backup(f, None)
        codes = [r.get("guide") for r in f.rows]
        check("backup", "a copy older than three weeks is F57 at LOOK",
              "F57" in codes and [r["level"] for r in f.rows if r.get("guide") == "F57"] == [doctor.LOOK], str(codes))
        for i in range(30):
            (folder / f"wiki-2026-{(i % 12) + 1:02d}-{(i % 27) + 1:02d}-{i}.bundle").write_bytes(b"x")
        f = doctor.Findings()
        doctor.check_backup(f, None)
        said = " ".join(r["text"] for r in f.rows)
        check("backup", "with many copies the oldest is named for the owner's own hand",
              "may be removed by the owner's own hand" in said, said[:160])
        doctor.tm_destination_count = lambda: 0
        f = doctor.Findings()
        doctor.check_backup(f, None)
        check("backup", "Time Machine with nowhere to copy to is F58", "F58" in [r.get("guide") for r in f.rows])
        doctor.tm_destination_count = lambda: None
        f = doctor.Findings()
        doctor.check_backup(f, None)
        check("backup", "when Time Machine cannot be read, it is CANNOT SEE and no code",
              any(r["level"] == doctor.UNSEEN for r in f.rows) and "F58" not in [r.get("guide") for r in f.rows])
        check("backup", "the check-up has a real Time Machine reader that returns a number or None",
              was_tm() is None or isinstance(was_tm(), int))
    finally:
        doctor.BACKUPS_DIR, doctor.tm_destination_count = was_dir, was_tm


def test_trust(doctor, work):
    # (0.12.0) the folder Claude trusts, read from Claude's own state file
    import json as _json
    was = doctor.CLAUDE_JSON
    try:
        vault = work / "trust-vault"
        vault.mkdir(parents=True, exist_ok=True)
        state = work / "claude-state.json"
        doctor.CLAUDE_JSON = state

        def run_it(assistant="claude"):
            f = doctor.Findings()
            doctor.check_trust(f, vault, assistant)
            return [r.get("guide") for r in f.rows], [r["level"] for r in f.rows], " ".join(r["text"] for r in f.rows)

        codes, levels, said = run_it()
        check("trust", "no state file at all is CANNOT SEE, not a finding", levels == [doctor.UNSEEN] and "F60" not in codes, said)
        state.write_text("{}")
        codes, levels, said = run_it()
        check("trust", "a wiki not in the state file is F60 at LOOK", codes == ["F60"] and levels == [doctor.LOOK], said[:120])
        state.write_text(_json.dumps({"projects": {str(vault): {"hasTrustDialogAccepted": False}}}))
        codes, levels, said = run_it()
        check("trust", "trust answered no is F60", codes == ["F60"], said[:120])
        state.write_text(_json.dumps({"projects": {str(vault): {"hasTrustDialogAccepted": True}}}))
        codes, levels, said = run_it()
        check("trust", "trust answered yes is OK", codes == [None] and levels == [doctor.OK], said[:120])
        import os as _os
        state.write_text(_json.dumps({"projects": {_os.path.realpath(str(vault)): {"hasTrustDialogAccepted": True}}}))
        codes, levels, said = run_it()
        check("trust", "trust under the folder's real path counts too", codes == [None], said[:120])
        state.write_text("{}")
        codes, levels, said = run_it("chatgpt")
        check("trust", "a ChatGPT wiki is not asked", codes == [] and levels == [])
        state.write_text("[]")
        codes, levels, said = run_it()
        check("trust", "a state file of the wrong shape is F60 rather than a crash", codes == ["F60"], said[:120])
    finally:
        doctor.CLAUDE_JSON = was


def test_recall(doctor, work):
    # (0.12.0) memory search: not chosen is OK; each half-set-up shape is F59
    import datetime as _dt
    import json as _json
    import os as _os
    was_settings, was_cache, was_ollama = doctor.SETTINGS, doctor.RECALL_CACHE, doctor.ollama_present
    try:
        vault = work / "recall-vault"
        (vault / "wiki").mkdir(parents=True, exist_ok=True)
        settings = work / "recall-settings.json"
        settings.write_text("{}")
        cache = work / "recall-cache"
        doctor.SETTINGS, doctor.RECALL_CACHE = settings, cache
        doctor.ollama_present = lambda: True

        def codes_of(v):
            f = doctor.Findings()
            doctor.check_recall(f, v)
            return [r.get("guide") for r in f.rows], " ".join(r["text"] for r in f.rows), f

        codes, said, f = codes_of(vault)
        check("recall", "not chosen is one OK line and no code", codes == [None] and "not chosen" in said, said[:100])
        hook = {"hooks": {"UserPromptSubmit": [{"hooks": [{"type": "command",
                                                           "command": f'python3 "{vault}/scripts/recall/recall-inject.py" 2>/dev/null || true'}]}]}}
        settings.write_text(_json.dumps(hook))
        codes, said, f = codes_of(vault)
        check("recall", "a hook pointing at scripts that are not there is F59 at LOOK",
              codes == ["F59"] and f.rows[0]["level"] == doctor.LOOK and "not in this wiki" in said, said[:120])
        (vault / "scripts" / "recall").mkdir(parents=True, exist_ok=True)
        (vault / "scripts" / "recall" / "recall.py").write_text("# stub\n")
        settings.write_text("{}")
        codes, said, f = codes_of(vault)
        check("recall", "scripts present but no hook is F59", codes == ["F59"] and "has not been told" in said, said[:120])
        settings.write_text(_json.dumps(hook))
        codes, said, f = codes_of(vault)
        check("recall", "a hook whose own file is missing (the wiki moved) is F59 and says so",
              codes == ["F59"] and "no longer at" in said, said[:120])
        (vault / "scripts" / "recall" / "recall-inject.py").write_text("# stub\n")
        was_model = doctor.ollama_has_model
        doctor.ollama_has_model = lambda name="x": None
        doctor.ollama_present = lambda: False
        codes, said, f = codes_of(vault)
        check("recall", "Ollama missing is F59 and says so", codes == ["F59"] and "Ollama" in said, said[:120])
        doctor.ollama_present = lambda: True
        codes, said, f = codes_of(vault)
        check("recall", "no index yet is F59", codes == ["F59"] and "not been built" in said, said[:120])
        cache.mkdir(parents=True, exist_ok=True)
        meta = cache / "meta.json"
        meta.write_text(_json.dumps({"count": 42}))
        codes, said, f = codes_of(vault)
        check("recall", "all four parts in place is OK with the section count",
              codes == [None] and "42 sections" in said, said[:120])
        old = _dt.datetime.now() - _dt.timedelta(days=20)
        _os.utime(meta, (old.timestamp(), old.timestamp()))
        codes, said, f = codes_of(vault)
        check("recall", "an index older than two weeks is F59 with its age", codes == ["F59"] and "20 days old" in said, said[:120])
        now = _dt.datetime.now()
        _os.utime(meta, (now.timestamp(), now.timestamp()))
        doctor.ollama_has_model = lambda name="x": False
        codes, said, f = codes_of(vault)
        check("recall", "the model not fetched is F59", codes == ["F59"] and "not been fetched" in said, said[:120])
        doctor.ollama_has_model = lambda name="x": None
        meta.write_text(_json.dumps({"count": 42, "vault": str(work / "elsewhere")}))
        codes, said, f = codes_of(vault)
        check("recall", "an index built for another place of the wiki is F59", codes == ["F59"] and "another place" in said, said[:120])
        meta.write_text(_json.dumps({"count": 42, "vault": str(vault)}))
        (cache / "rebuild.log").write_text("2026-10-22 04:40 +0100 [launchd] FAILED (exit 1) after 3s: boom\n")
        codes, said, f = codes_of(vault)
        check("recall", "a last refresh that failed is F59", codes == ["F59"] and "last refresh failed" in said, said[:120])
        (cache / "rebuild.log").write_text("2026-10-22 04:40 +0100 [launchd] ok in 2s: index built\n")
        codes, said, f = codes_of(vault)
        check("recall", "and a refresh that succeeded is OK again", codes == [None], said[:120])
        doctor.ollama_has_model = was_model
        settings.write_text("{not json")
        codes, said, f = codes_of(vault)
        check("recall", "an unreadable settings file does not crash the check", "F59" in codes, said[:120])
        check("recall", "the check-up has a real Ollama reader", isinstance(was_ollama(), bool))
        doctor.RECALL_CACHE = None
        a, b = doctor.recall_cache_dir(vault), doctor.recall_cache_dir(work / "elsewhere")
        check("recall", "the cache folder is one per wiki, under the shared folder",
              a != b and a.parent == b.parent == doctor.HOME / ".cache" / "moblee-recall" and len(a.name) == 12, str(a))
    finally:
        doctor.SETTINGS, doctor.RECALL_CACHE, doctor.ollama_present = was_settings, was_cache, was_ollama


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

    # ---- (v0.10.0) a shortened line still reads as a statement
    # All three of these came off real cards, and all three read as a line that
    # broke off in the middle of a thought. The possessive and the unclosed
    # bracket are the two the shortening had no rule for.
    def shortened(text, room=doctor.CARD_ROOM):
        f = doctor.Findings()
        f.add(doctor.PROBLEM, text, "F44")
        return doctor.card_line(f.rows[0], str, room)

    # The wording as it really stood, which gave "…as its Stop hook: Moblee's".
    line = shortened("Claude does not save the wiki at the end of every reply: Moblee's "
                     "end-of-reply save is not registered as its Stop hook. What a reply leaves "
                     "unsaved stays unsaved until somebody asks for it.")
    check("card", "a shortened line never ends on a possessive left hanging",
          not line.rstrip(".").endswith(("'s", "’s")), line)
    check("card", "and what is left of it is still the finding",
          line.startswith("Claude does not save the wiki") and line.endswith("..."), line)
    # And as it really stood here, which gave an open bracket and no close.
    line = shortened("The wiki has no end-of-reply save (scripts/turn-end-commit.py is not in "
                     "it), so what a reply leaves unsaved stays unsaved until somebody asks "
                     "for it.")
    check("card", "and never leaves a bracket open, which reads as a line cut in half",
          line.count("(") == line.count(")"), line)
    check("card", "what is left of that one is a whole statement too",
          line.startswith("The wiki has no end-of-reply save"), line)
    # (The third real example, a reassuring head on a fault that is the
    # opposite, was not the shortening's fault but the finding's; it is put
    # right in the finding and proved in the "mods" group.)
    # And the words the old list already held, kept under the new rule.
    check("card", "the linking words are still dropped, as they were before",
          not shortened("The delete guard is not switched on for Claude, so nothing stops a "
                        "command that would remove a page of yours for good.").rstrip(".")
          .endswith(("so", "and", "which")),
          shortened("The delete guard is not switched on for Claude, so nothing stops a command "
                    "that would remove a page of yours for good."))

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
    # (v0.10.0) `4 thing(s)` is a programmer's shortcut for not choosing, and it
    # asks a reader who does not read much to do the choosing instead. The pack
    # tells every assistant to use plain words; a whole check-up an owner reads
    # had better. things() is the helper, and this is the rule.
    shortcut = [l.strip() for l in (out["plain"] + out["card"]).splitlines() if "(s)" in l]
    check("card", "nothing an owner reads on an ordinary run says \"thing(s)\"",
          not shortcut, "; ".join(shortcut[:2])[:140])
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
    test_permissions(doctor, work)
    test_backup(doctor, work)
    test_trust(doctor, work)
    test_recall(doctor, work)
    test_weights(doctor, work)
    test_report_names(doctor, work)
    test_card(doctor, work)
    test_app(doctor, work)
    test_leftovers(doctor, work)
    test_guard_version(doctor, work)
    test_damaged_and_codex_home(doctor, work)
    test_tour(doctor, work)
    test_saving(doctor, work)
    test_prove_saving(doctor, work)
    test_mods(doctor, work)
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
