# 01. Prerequisites

Moblee runs on a Mac only. It has been tested on Apple Silicon (M-series) machines running macOS 14 and later; it should work on earlier hardware as well, though connecting the Mac's own Calendar, Reminders, Mail and Notes needs macOS 14 (Sonoma) or later. Before running the installer, get the four pieces of software described here in place. Everything else (Homebrew, the PDF renderer, the video tools, the Chrome extensions) comes later, from the checklist, and only if you want it; see [10-connections.md](10-connections.md).

## Obsidian

Obsidian is the reader. It opens a folder of markdown files and gives you the graph view, the wikilink autocomplete, and the live preview. It's free for personal use.

Download Obsidian from [obsidian.md](https://obsidian.md) and drag the app into `Applications/`. Launch it once and dismiss the welcome screen; you do not need to create a vault yet. The Moblee installer creates the vault and you point Obsidian at it afterwards.

To verify Obsidian is installed and working, open `Applications/` and confirm `Obsidian.app` is there.

## Claude Code

You need the app of the assistant you will use: one of the two below, or both.

**With Claude:** Claude Code is the command-line interface to Claude. It is what you use for the heavier wiki sessions: ingesting batches of sources, running lint passes, doing PDF renders. You can also use Cowork (the desktop app) for casual capture, but Claude Code is the primary tool for serious wiki work.

Install instructions live at [claude.ai/code](https://claude.ai/code). At a minimum you'll need an Anthropic account; the install itself is typically a single command in your Terminal.

To verify Claude Code is installed, open Terminal (`Applications/Utilities/Terminal.app`) and run:

```
claude --version
```

You should see a version string. If you see "command not found", the installer's PATH step did not complete; see the Claude Code install docs for fixes.

**With ChatGPT:** ChatGPT's file-working agent is called Codex, and it is part of the ChatGPT app for Mac. Download the app from [chatgpt.com/download](https://chatgpt.com/download), open it and sign in with your ChatGPT account. OpenAI's pricing page lists the Free, Go, Plus, Pro, Business, Edu and Enterprise plans as including Codex, with limits that vary by plan. To verify, open `Applications/` and confirm `ChatGPT.app` is there.

## Apple's developer tools and git

Git is the version control system that backs the vault's audit trail. On macOS, git comes with Apple's free developer tools (the Command Line Tools), which you install once. Several checklist items need them too, so they only ever need installing once.

To install:

```
xcode-select --install
```

A window will appear asking to install the Command Line Tools. Click Install, then Agree. It usually takes 5 to 20 minutes and uses around 1.5 GB.

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

Python 3 runs the vault tooling (the weekly health check, the commit gate, the dashboard, the galaxy view) and the checklist itself. It comes with Apple's developer tools, so once those are in, this step is a one-line check. To verify:

```
python3 --version
```

If you see `Python 3.9` or anything later, you're set (the version that comes with the developer tools is enough). If you see "command not found" or a window offering to install the developer tools, finish the previous step first.

## Homebrew, and everything else, comes later

Homebrew is the free, standard way to install tools on a Mac. You do not need it before installing Moblee. If anything you tick on the checklist needs it, the checklist installs it for you: it asks for your Mac password once (typing it shows nothing on screen, which is normal) and takes 5 to 10 minutes. The PDF renderer, the video tools, the editing tools and the Chrome extensions are all checklist items in the same way, so there is nothing more to install by hand.

## Optional: Obsidian Web Clipper

The Obsidian Web Clipper is a browser extension that saves a clean markdown copy of any web page (with YAML frontmatter for source, author, and date) directly into a folder of your choice. It's the easiest way to feed reading material into the wiki's `Clippings/` inbox.

The checklist's Chrome item opens its page in the Chrome Web Store for you to add it; you can also install it yourself from the Chrome Web Store, the Firefox Add-ons store or the Safari extension gallery. Then, in the extension's settings, point its save location at the `Clippings/` folder inside your vault (which you'll create with the Moblee installer in a moment).

This is optional. You can also save sources by hand: drag PDFs into `raw/`, paste text into a markdown file under `raw/`, or save a webpage as markdown using any tool you prefer.

## Optional: Readwise

If you use [Readwise](https://readwise.io) and have its Obsidian sync set up, the Moblee vault template includes the `Clippings/Readwise/` folder structure and the corresponding rules in `CLAUDE.md`. Readwise will sync your highlights into `Clippings/Readwise/Articles/`, `Clippings/Readwise/Books/`, and `Clippings/Readwise/Tweets/`, and your assistant will handle them according to the rules.

You can ignore the Readwise paragraph in `CLAUDE.md` if you don't use Readwise; nothing else depends on it.

## Ready?

When you have Obsidian, Claude Code or the ChatGPT app, Apple's developer tools (with git) and Python 3 installed and verified, move on to [02-install.md](02-install.md).
