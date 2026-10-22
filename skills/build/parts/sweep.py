#!/usr/bin/env python3
"""sweep.py - read a folder for anything that must not leave the Mac.

Used by publish.py before a page goes on the web and by share.py before a kit
is zipped: the check-up's own sweep, applied to one folder. It looks for keys
and tokens (a private key, a cloud key, a token for GitHub, Claude, ChatGPT,
Slack, Google, Stripe, Tailscale, Telegram and the like), for things that read
as passwords, for seed phrases, and for the owner's own name as the wiki's
rules file gives it. It reads and reports; it changes nothing.

    python3 sweep.py <folder> [<wiki folder>]
        exit 0 clean, 1 something to look at, 2 something that must not go

Every file is read: those with a text extension, and those with no extension
at all. A file it cannot read as text (a picture, a font, a sound) is listed
as skipped, with the reason, so the caller can decide; a file over the size
limit likewise. The check-up's own patterns are used when the check-up can be
found: the copy in this pack first, then the one ~/.config/moblee/package-path
names, which is an owner's file and so only a fallback. Without either, a
smaller built-in set stands in.
"""
from __future__ import annotations

import importlib.util
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEXT_EXT = {".md", ".markdown", ".txt", ".json", ".csv", ".tsv", ".html", ".htm", ".js", ".mjs", ".css", ".py",
            ".sh", ".zsh", ".bash", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".env", ".xml", ".plist", ".svg",
            ".pem", ".key", ".crt", ".cer", ".log", ".applescript", ".scpt", ".rtf", ".tex"}
# what may travel unread: pictures, fonts and sounds, which hold no text
MEDIA_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".bmp", ".tiff", ".heic",
             ".woff", ".woff2", ".ttf", ".otf", ".mp3", ".m4a", ".wav", ".aac", ".mp4", ".mov", ".pdf"}
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".build", "state", "dist", "build", ".next"}
MAX_BYTES = 12_000_000

# A small stand-in, used only when the check-up cannot be found.
FALLBACK_CRITICAL = [
    ("a private key", re.compile("-----BEGIN " + r"(?:[A-Z0-9]+ )*PRIVATE KEY-----")),
    ("an Amazon cloud access key", re.compile(r"\bAKIA" + r"[0-9A-Z]{16}\b")),
    ("a GitHub token", re.compile(r"\bgh[pousr]_" + r"[A-Za-z0-9]{36,}\b")),
    ("a key for Claude", re.compile(r"\bsk-" + r"ant-[A-Za-z0-9_\-]{30,}")),
    ("a key for ChatGPT", re.compile(r"\bsk-" + r"(?!ant-)(?:proj-)?[A-Za-z0-9_\-]{40,}")),
    ("a Google key", re.compile(r"\bAIza" + r"[0-9A-Za-z_\-]{35}(?![0-9A-Za-z_\-])")),
    ("a Tailscale key", re.compile(r"\btskey-" + r"[a-z]+-[A-Za-z0-9]{10,}")),
]
FALLBACK_REVIEW = [
    ("something that reads as a password", re.compile(r"(?i)\b(?:password|passwd|secret|api[_-]?key|token)\b\s*[:=]\s*['\"]?([^\s'\"]{8,})")),
    ("an email address", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
]


def find_pack() -> Path | None:
    cands = [HERE.parents[2]]  # skills/build/parts -> the pack, when run in place
    try:
        p = (Path(os.path.expanduser("~")) / ".config" / "moblee" / "package-path").read_text(encoding="utf-8").strip()
        if p:
            cands.append(Path(p).expanduser())
    except OSError:
        pass
    for c in cands:
        if (c / "scripts" / "moblee-doctor.py").is_file():
            return c
    return None


def load_doctor(pack: Path | None):
    if pack is None:
        return None
    try:
        spec = importlib.util.spec_from_file_location("moblee_doctor_for_sweep", pack / "scripts" / "moblee-doctor.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None


def seed_words(vault: Path | None, pack: Path | None, doctor) -> set:
    if doctor is None or vault is None:
        return set()
    try:
        words, _ = doctor.privacy_wordlist(vault, pack)
        return set(words or ())
    except Exception:
        return set()


def owner_names(vault: Path | None) -> list:
    """The owner's name as the wiki's rules file gives it, as whole words of
    three letters or more, so 'Sam' is looked for and 'a' is not."""
    if vault is None:
        return []
    names = set()
    for f in ("CLAUDE.md", "AGENTS.md"):
        p = vault / f
        try:
            text = p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""
        except OSError:
            text = ""
        m = re.search(r"knowledge base for \*{0,2}([^*\n]+?)\*{0,2} where", text)
        if m and "[Your Name]" not in m.group(1):
            # whole words of three letters or more, in any script
            for w in re.findall(r"[^\W\d_][^\W\d_'\-]{2,}", m.group(1)):
                if w.lower() not in NAME_STOP:
                    names.add(w)
    return sorted(names)


def read_as_text(p: Path) -> str | None:
    """The file as text, or None when it is not plain text. A file in the
    other common encodings (UTF-16 either way round, with its mark) is read
    as such, so that a key in it is seen; a file full of NUL bytes is not
    text and is said so, rather than read as nothing."""
    raw = p.read_bytes()
    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        try:
            return raw.decode("utf-16")
        except UnicodeDecodeError:
            return None
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    sample = raw[:65536]
    if sample and sample.count(b"\x00") > len(sample) // 64:
        return None
    return raw.decode("utf-8", errors="ignore")


NAME_STOP = {"the", "and", "for", "owner", "your", "name"}


def scan_text(text: str, doctor, seeds: set, names: list) -> tuple[list, list]:
    critical, review = [], []
    if doctor is not None:
        try:
            for level, kind, line in doctor.privacy_in_file(text, seeds):
                (critical if level == "critical" else review).append((kind, line))
        except Exception:
            doctor = None
    if doctor is None:
        for kind, rx in FALLBACK_CRITICAL:
            for m in rx.finditer(text):
                critical.append((kind, text.count("\n", 0, m.start()) + 1))
        for kind, rx in FALLBACK_REVIEW:
            for m in rx.finditer(text):
                review.append((kind, text.count("\n", 0, m.start()) + 1))
    for name in names:
        # as written, with its capitals: a name that is also an ordinary word
        # ("Will", "Grace") is then not seen in every sentence that uses the word
        for m in re.finditer(r"(?<!\w)" + re.escape(name) + r"(?!\w)", text):
            review.append((f"the owner's name ({name})", text.count("\n", 0, m.start()) + 1))
            break  # once per file is enough to say it
    return critical, review


def sweep(folder: Path, vault: Path | None = None) -> tuple[list, list, list, str]:
    """Returns (critical, review, skipped, source): the first two lists of
    (file, kind, line), the third of (file, reason) for files not read."""
    pack = find_pack()
    doctor = load_doctor(pack)
    seeds = seed_words(vault, pack, doctor)
    names = owner_names(vault)
    critical, review, skipped = [], [], []
    source = "the check-up's own patterns" if doctor is not None else "a built-in set (the check-up was not found)"
    for dirpath, dirnames, filenames in os.walk(folder):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for name in sorted(filenames):
            p = Path(dirpath) / name
            rel = str(p.relative_to(folder))
            if p.is_symlink():
                skipped.append((rel, "a link to somewhere else, which is never carried"))
                continue
            ext = p.suffix.lower()
            if ext in MEDIA_EXT:
                skipped.append((rel, "a picture, font, sound or PDF, which is not read"))
                continue
            if ext and ext not in TEXT_EXT and name.lower() not in (".env",):
                skipped.append((rel, f"a kind of file the sweep does not read ({ext})"))
                continue
            try:
                if p.stat().st_size > MAX_BYTES:
                    skipped.append((rel, "over the size the sweep reads"))
                    continue
                text = read_as_text(p)
            except OSError:
                skipped.append((rel, "could not be read"))
                continue
            if text is None:
                skipped.append((rel, "not plain text"))
                continue
            c, r = scan_text(text, doctor, seeds, names)
            critical += [(rel, k, ln) for k, ln in c]
            review += [(rel, k, ln) for k, ln in r]
    return critical, review, skipped, source


def sweep_file(path: Path, vault: Path | None = None) -> tuple[list, list]:
    """One file, for a page zipped from elsewhere."""
    pack = find_pack()
    doctor = load_doctor(pack)
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return [], []
    c, r = scan_text(text, doctor, seed_words(vault, pack, doctor), owner_names(vault))
    return [(path.name, k, ln) for k, ln in c], [(path.name, k, ln) for k, ln in r]


def report(critical: list, review: list, source: str, skipped: list | None = None, names: list | None = None) -> None:
    print(f"Swept with {source}.")
    if names is not None and not names:
        print("(no owner's name was found in the wiki's rules file, so none was looked for)")
    if not critical and not review and not skipped:
        print("Nothing found that should stay on the Mac.")
        return
    for rel, kind, line in critical:
        print(f"  MUST NOT GO   {rel}, line {line}: {kind}")
    for rel, kind, line in review:
        print(f"  look at this  {rel}, line {line}: {kind}")
    for rel, why in (skipped or []):
        print(f"  not read      {rel}: {why}")


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    folder = Path(sys.argv[1]).expanduser().resolve()
    if not folder.is_dir():
        print(f"{folder} is not a folder")
        return 2
    vault = Path(sys.argv[2]).expanduser().resolve() if len(sys.argv) > 2 else None
    critical, review, skipped, source = sweep(folder, vault)
    report(critical, review, source, skipped)
    return 2 if critical else (1 if review else 0)


if __name__ == "__main__":
    sys.exit(main())
