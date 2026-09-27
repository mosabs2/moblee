#!/usr/bin/env python3
"""Put an owner's own words into a v0.9.3 rules file, in three places.

This is the fixture behind the `owners_words` case. From v0.9.4 the updater
REPLACES the sections Moblee owns in a rules file and DROPS the ones whose
content has moved to a page of its own. The one rule that makes that safe is
that a section is only touched where its body still matches, word for word,
something Moblee shipped. A file an owner has written in is the case that
matters, so the fixture writes in it, in the three shapes a real owner produces:

  1. an extra bullet inside a section of Moblee's (## Hard rules);
  2. an extra paragraph at the end of another (## House style);
  3. a whole section of their own, under a heading Moblee has never shipped.

The three lines are printed, one per line, so the case can look for exactly
these words in the file afterwards and nowhere have to repeat them.

Usage: add-owner-words.py <path to CLAUDE.md>
"""
import sys
from pathlib import Path

BULLET = "- **Never touch the boat papers without asking me first.** They are not the wiki's business."
PARAGRAPH = ("Prices are written with the currency spelled out in full, because the owner reads "
             "the wiki on a phone and the symbols are too small to tell apart.")
SECTION_HEADING = "## How the owner files receipts"
SECTION_LINE = "Receipts go in a folder named for the month they were paid in, never for the month they arrived."


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    path = Path(sys.argv[1])
    text = path.read_text(encoding="utf-8")
    for anchor in ("## Hard rules\n\n", "## House style\n\n"):
        if anchor not in text:
            print(f"the fixture rules file has no {anchor.strip()} section; nothing written")
            return 1

    # 1. a bullet of their own, first in the list, inside a section of Moblee's
    text = text.replace("## Hard rules\n\n", "## Hard rules\n\n" + BULLET + "\n", 1)
    # 2. a paragraph of their own at the end of another section of Moblee's
    end_of_house_style = text.index("## Log timestamps")
    text = text[:end_of_house_style] + PARAGRAPH + "\n\n" + text[end_of_house_style:]
    # 3. a section that is theirs alone, under a heading Moblee has never shipped
    text = text.rstrip("\n") + "\n\n" + SECTION_HEADING + "\n\n" + SECTION_LINE + "\n"

    path.write_text(text, encoding="utf-8")
    print(BULLET)
    print(PARAGRAPH)
    print(SECTION_LINE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
