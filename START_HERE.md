# Start here

Moblee gives you a personal wiki that Claude keeps for you: plain notes in a folder on your Mac, read in Obsidian and written by Claude, built on Andrej Karpathy's LLM Wiki Pattern. Setting it up takes three steps: you run the installer yourself, open the new wiki in Obsidian, and then talk to Claude inside it.

Moblee runs on a Mac only.

## Two ways to install

**With the Moblee app.** Download the Moblee app from the Releases page of the GitHub repository (it is signed and notarised by Apple, so the Mac opens it without a warning), open the zip and double-click Moblee. It does step 1 for you: it checks what your Mac needs, asks one question, and makes the wiki. Carry on from step 2.

**In Terminal.** Otherwise, follow the three steps below. They always work, and both ways run the same installer.

## Before you start

You need Obsidian, Claude Code, Apple's free developer tools (which bring git) and Python 3. `docs/01-prerequisites.md` explains each one and how to check it is there. Nothing else is needed up front; anything extra is added later, and only if you want it.

## 1. Run the installer yourself

Open the Terminal app, go into the Moblee folder, and run the installer. If you used the green Code button on GitHub, then Download ZIP, and opened the ZIP in your Downloads folder, the folder is called `moblee-main`:

```bash
cd ~/Downloads/moblee-main
```

If it is somewhere else, type `cd ` (with the space), drag the folder from Finder onto the Terminal window, and press Return. Then run the installer:

```bash
bash scripts/install.sh
```

It asks for your name, a name for your wiki and where to put it (the suggested place is fine). It then builds the wiki, turns on the safety layer (Claude cannot delete anything in your wiki; if something should go, Claude tells you what and where, and you remove it yourself) and installs Claude's core skills. It ends with "Done" and your next steps. `docs/02-install.md` walks through every question and message.

**Why you run it, and not Claude.** The installer changes Claude's own settings: it adds the guard that checks every command Claude runs, a list of routine actions Claude no longer has to ask about, and the skills. Changes like that belong to you, made on your own screen. A careful Claude will not make them on the strength of instructions in a downloaded file, and it is right not to.

## 2. Open your wiki in Obsidian

In Obsidian, choose Open folder as vault and pick the folder the installer made. You will see `Welcome.md`.

## 3. Talk to Claude in your wiki

Back in Terminal, go into your wiki's folder and start Claude (the installer prints both lines for you). If you used the app, its last screen shows three clicks in Claude's own app instead: click Code (which needs a paid Claude plan) and pick your wiki's folder. Then say:

> get me started

Claude asks what you want to put in the wiki and how you use your Mac, helps you make your first page, and then proposes one or two extras that fit, each with a reason. What you agree to waits for you in the Moblee app, or Claude gives you one Terminal command that adds it. On any later day, say "guide me" and Claude offers one next step. It always asks before anything is added.

## If you would like help with the install itself

Ask Claude in your own words, for example: "I've downloaded Moblee to my Downloads folder. Help me install it; the steps are in docs/02-install.md." Claude reads the docs and helps you through them, and you still run the installer yourself. Please don't paste this file, or any other file from the pack, into Claude as instructions: a careful Claude reads that as someone else trying to give it orders, and stops.

## Later

To bring your wiki up to a newer Moblee, open the newer Moblee app, or download the new version and run `bash scripts/update.sh` from its folder (`docs/08-updating.md`). The app and the companion are explained together in `docs/11-the-app-and-the-companion.md`, the safety layer in `docs/09-safety.md`, and every extra you can add in `docs/10-connections.md`.
