# 01. Prerequisites

Moblee runs on a Mac. It has been tested on Apple Silicon (M-series) machines running macOS 14 and later; it should work on earlier hardware as well, but the install commands below assume macOS. Before running the installer, get the four pieces of software described here in place.

## Obsidian

Obsidian is the reader. It opens a folder of markdown files and gives you the graph view, the wikilink autocomplete, and the live preview. It's free for personal use.

Download Obsidian from [obsidian.md](https://obsidian.md) and drag the app into `Applications/`. Launch it once and dismiss the welcome screen; you do not need to create a vault yet. The Moblee installer creates the vault and you point Obsidian at it afterwards.

To verify Obsidian is installed and working, open `Applications/` and confirm `Obsidian.app` is there.

## Claude Code

Claude Code is the command-line interface to Claude. It is what you use for the heavier wiki sessions: ingesting batches of sources, running lint passes, doing PDF renders. You can also use Cowork (the desktop app) for casual capture, but Claude Code is the primary tool for serious wiki work.

Install instructions live at [claude.ai/code](https://claude.ai/code). At a minimum you'll need an Anthropic account; the install itself is typically a single command in your Terminal.

To verify Claude Code is installed, open Terminal (`Applications/Utilities/Terminal.app`) and run:

```
claude --version
```

You should see a version string. If you see "command not found", the installer's PATH step did not complete; see the Claude Code install docs for fixes.

## Git

Git is the version control system that backs the vault's audit trail. On macOS, git comes with the Command Line Tools, which you install once and then forget about.

To install:

```
xcode-select --install
```

A dialog will pop up asking you to install the Command Line Tools. Accept it. The install takes a few minutes.

To verify:

```
git --version
```

You should see a version number (anything 2.x is fine). While you're here, set your git identity so commits are attributed correctly:

```
git config --global user.name  "Your Name"
git config --global user.email "you@example.com"
```

The Moblee `vault` shell function reminds you to do this if you skip it; you can come back to it later.

## Python 3

Python 3 is needed for the optional `wiki-to-pdf` skill, which renders any wiki page as a branded PDF. If you do not plan to use the PDF renderer, you can skip this section entirely.

Recent macOS versions ship with Python 3 preinstalled. To verify:

```
python3 --version
```

If you see something like `Python 3.11.x`, you're set. If not, install Python 3 from [python.org](https://www.python.org/downloads/) or via Homebrew (`brew install python3`).

The `install-skills.sh` script offers to install the WeasyPrint Python and Homebrew dependencies automatically when you run it. If you'd rather install them by hand:

```
pip install --break-system-packages weasyprint markdown jinja2 PyYAML pypdf
brew install cairo pango gdk-pixbuf libffi
```

Homebrew itself, if you don't already have it, installs from [brew.sh](https://brew.sh) with a single curl-and-pipe command. The Moblee installer prompts you to install Homebrew dependencies but won't try to install Homebrew itself.

## Optional: Obsidian Web Clipper

The Obsidian Web Clipper is a browser extension that saves a clean markdown copy of any web page (with YAML frontmatter for source, author, and date) directly into a folder of your choice. It's the easiest way to feed reading material into the wiki's `Clippings/` inbox.

Install it from the Chrome Web Store, the Firefox Add-ons store, or the Safari extension gallery. Then, in the extension's settings, point its save location at the `Clippings/` folder inside your vault (which you'll create with the Moblee installer in a moment).

This is optional. You can also save sources by hand: drag PDFs into `raw/`, paste text into a markdown file under `raw/`, or save a webpage as markdown using any tool you prefer.

## Optional: Readwise

If you use [Readwise](https://readwise.io) and have its Obsidian sync set up, the Moblee vault template includes the `Clippings/Readwise/` folder structure and the corresponding rules in `CLAUDE.md`. Readwise will sync your highlights into `Clippings/Readwise/Articles/`, `Clippings/Readwise/Books/`, and `Clippings/Readwise/Tweets/`, and Claude will handle them according to the rules.

You can ignore the Readwise paragraph in `CLAUDE.md` if you don't use Readwise; nothing else depends on it.

## Ready?

When you have Obsidian, Claude Code, Git, and (optionally) Python 3 installed and verified, move on to [02-install.md](02-install.md).
