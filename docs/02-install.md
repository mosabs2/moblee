# 02. Installing Moblee

This document walks through the step-by-step install of the Moblee starter pack on a Mac (Moblee runs on a Mac only). It assumes you have the prerequisites from [01-prerequisites.md](01-prerequisites.md) in place.

## The app route

From v0.8.1 there is a second way to install: the Moblee app, a small Mac app. It is offered as a zip named `Moblee` and its version number on the Releases page of the GitHub repository, signed and notarised by Apple, so the Mac opens it without a warning. The Terminal steps below always work too. From v0.9.0 the app asks which assistant you use (Claude, ChatGPT or both) and sets the wiki up for that choice.

You double-click the app and follow its screens. Each screen has one picture, one sentence and one button. If you opened it from Downloads, its first screen offers to move it to Applications, so that you can always find it again; press "Move it there" and it reopens by itself. After the welcome, it checks what the Mac needs: Apple's developer tools and Claude's app, with a Get button beside anything missing, and Obsidian, marked "Can wait". It asks one typed question, "What should Claude call you?", and then one question answered by a tap, "Which assistant do you use?". Before anything is made it says plainly what it is about to put on the Mac and where: the wiki's folder, the guard, and Claude's skills. It then builds the wiki, shown as six pictures that light up in turn: the wiki, its tools, its history, the guard, Claude's skills, and finishing. The last screen shows three numbered pictures: click Code in Claude's app, pick the wiki's folder, and say "get me started". The Open Claude button copies those words for you to paste, and "What did Moblee make?" lists everything that was put on the Mac. Every screen has a small speaker button that reads its sentence aloud; nothing is sent anywhere to do this. If a build stops, the big button is Try again, which finishes the same wiki and never starts a second one; the same is true if you close the app and open it again later. The Code tab in Claude's app needs a paid Claude plan.

**With ChatGPT:** after the build the app shows one more screen, the Trust step, with the five clicks and an "Open ChatGPT" button, and then offers to prove that the guard is running, which can take three minutes. The last screen's button is Open ChatGPT, and its pictures read: choose Work at the top, open your wiki folder, and say "get me started". <!-- verify on testdev --> An owner who already has a wiki is asked the same question the first time they press Update in this version, and can change the answer later from the app's home screen.

The wiki is named after you (for example "Sam Wiki") and placed in a `Wiki` folder in your home folder. If that name is taken, it gets a number. There are no other questions.

The app runs the pack's own `scripts/install.sh` underneath, so an app install and a Terminal install are the same install, and everything from Step 3 onwards applies to both. The app carries the pack inside it and copies it once to `~/Library/Application Support/Moblee/pack-<version>`, because the wiki's tools need the pack later (for the checklist and for updates). If the build stops, the button reads "Show what happened" and points you to the install diary described below.

## Step 1: get the Moblee package

The simplest way is GitHub's green Code button, then Download ZIP; open the ZIP and it unpacks to a folder called `moblee-main` (in your Downloads folder, `cd ~/Downloads/moblee-main`). If you use git, you can clone it instead:

```
git clone <repo-url> ~/moblee
cd ~/moblee
```

If you have it as a zip file, unzip it into your home directory and `cd` into the resulting folder. The exact location doesn't matter; the installer can be run from anywhere as long as you point it at the right folder.

To confirm you're in the right place:

```
ls
```

You should see `README.md`, `START_HERE.md`, `LICENSE`, and the `vault-template/`, `skills/`, `extras/`, `scripts/`, and `docs/` folders.

## Step 2: run the installer

From inside the Moblee folder:

```
bash scripts/install.sh
```

The script will ask you four questions:

1. **Your name**, used in the templates as the author of the vault. Default: `[Your Name]`.
2. **Vault name**, used as the folder name and substituted into template files. Default: `MyWiki`.
3. **Vault location**, where to put the vault. Default: `~/Wiki/<vault name>`.
4. **Which assistant** you will use with the wiki: Claude, ChatGPT or both. Default: Claude. You can change it later with the updater (`docs/08-updating.md`).

You can press Return at each prompt to accept the default.

After that, the script will:

- Copy the `vault-template/` to your chosen location.
- Lay the rules file down under the name your assistant reads: `CLAUDE.md` for Claude, `AGENTS.md` for ChatGPT. With both, `CLAUDE.md` is the real file and `AGENTS.md` is a link to it. ChatGPT reads only the first 32 KiB of that file by default, so the installer raises the limit in `~/.codex/config.toml`.
- Substitute `[Your Name]`, `[Your Vault Name]`, and `[Your Vault]` placeholders inside all markdown, CSS, HTML, Python, and other text files.
- Copy the vault tooling into `scripts/` and `dashboard/`, and record the vault's location at `~/.config/moblee/vault-path` so the tooling can find it.
- Initialise a git repository in the new vault, make the first commit, and point git at the commit gate in `scripts/hooks/`.
- Install the safety layer: the delete guard (proved working before it is registered) and, for Claude, the starter permission rules. This step is not optional; if it fails, the installer stops and says why. `docs/09-safety.md` explains what it does.
- Seed four starting memories for your assistant. ChatGPT has no hand-written memory folder, so for ChatGPT they go on a wiki page, `wiki/Wiki Operations/Assistant Memory.md`.
- Install the eight core skills into `~/.claude/skills/` (for ChatGPT, `~/.agents/skills/`). There is no separate skills step to run.
- Tell you about the extras (Step 4 below) and ask whether you would rather choose them yourself now. The answer it expects is no: the easier way is to let Claude suggest them.
- Commit the settings and choices it wrote, so the vault starts clean, and print the next steps.

It takes a few minutes. You run the installer yourself, rather than asking your assistant to, because it changes your assistant's own settings (the guard, the skills and, for Claude, the permission rules); those changes are yours to make, on your own screen.

**With ChatGPT: the Trust step.** ChatGPT does not run a newly installed or changed guard until you have reviewed it. Until then the guard is skipped and nothing on screen says so. The installer prints the steps when they are due: open the ChatGPT menu, choose Settings, choose Hooks (under the Coding heading), open "User config", press Trust beside the hook whose command ends `bash-guard.py`, and turn its switch on. `docs/09-safety.md` says how to prove the guard afterwards.

**The install diary.** Every run of the installer, from Terminal or from the app, keeps a plain diary of its steps at `~/.config/moblee/install-diary.txt`: what ran, what passed, what failed and why. It holds no names, and it writes your home folder as `~`, so it is safe to pass to whoever is helping you if an install goes wrong. Each run adds to the end of the file; nothing in it is overwritten.

**Answers up front.** The three questions can also be answered on the command line, which is how the app runs the installer: `bash scripts/install.sh --name "Sam" --vault-name "MyWiki" --location "$HOME/Wiki/MyWiki"`. The assistant can be named the same way, with `--assistant claude`, `--assistant chatgpt` or `--assistant both`. Adding `--progress` prints one extra line per step for a program to read; you do not need it. A name that contains `&`, `|` or a backslash now arrives in your wiki exactly as you typed it.

**Updating later.** You never run the installer twice on the same vault; if you point it at an existing Moblee vault, it hands over to the updater instead of overwriting anything. When a new Moblee version comes out, download it and run the updater; see `docs/08-updating.md`.

## Step 3: open the vault in Obsidian

Launch Obsidian. On the welcome screen (or File, then Open vault), choose **Open folder as vault**. Navigate to the location you chose in Step 2 and select the vault folder. Obsidian will open it and you'll see `Welcome.md` in the file pane.

Click `Welcome.md` and read it.

## Step 4: choosing the extras

**With Claude:** this step applies as written. **With ChatGPT:** Moblee does not set this up for ChatGPT yet. You can still hold the first conversation: open the ChatGPT app, choose Work at the top, open the vault's folder as a project, and say **get me started**. <!-- verify on testdev -->

**The usual way: ask Claude.** With the vault open in Obsidian, go into the vault's folder in Terminal and type `claude` (or, in Claude's app, click Code and pick the vault's folder), and say **get me started**. Claude asks how you use your Mac, where your mail and calendar live, and what you read, watch and make. It helps you make your first page, then proposes one or two extras that clearly fit, each with its reason, time, space and cost. If you have the Moblee app, what you agree to waits there as a tile with an Add button (`docs/10-connections.md` says which items the app adds by itself and which need you at a Terminal window). If you installed from Terminal, Claude gives you one command to run from the Moblee folder, for example `python3 scripts/moblee-setup.py --tick videos`. That opens the checklist below with those items ticked. Your answers are kept on the wiki's `Habits and Tools` page, and on any later day you can say **guide me** for one next step, or **review my setup** to go over the whole setup. It asks before anything is added, and anything you say no to is not suggested again for ninety days.

**The checklist.** Run on its own, or through the command Claude gives you, the checklist covers everything optional: your Mac's Calendar, Reminders, Mail and Notes; Gmail, Google Calendar and Google Drive; GitHub; Chrome with your X, Instagram and YouTube logins and the Obsidian Web Clipper; video watching; PDF, Word, PowerPoint and Excel; film, audio and picture editing; a news brief; trip pages; X capture; a skill maker; Obsidian extras; the paid options; and looking after the wiki (the weekly health check, the learning path, spoken replies, and the `vault` shortcut in Terminal).

Nothing is ticked at first, unless you came through Claude, in which case the items you agreed on are ticked. Each line says what the item does, about how long it takes, how much space it uses and what it costs. Items already working are marked `working`. Type the numbers of items to tick or untick (for example `3 7 12`), `all` for everything, `free` for everything free, or `none` to clear, then press Return on its own to accept. Before anything starts, the checklist shows the order it will work in, its estimate of time and space, and each moment it will need you at the keyboard, then asks "Start now?".

Be ready for the time and space. Ticking everything free takes **about an hour and a half the first time** and **several gigabytes**, most of it downloads of Apple's developer tools, Homebrew and the video renderer. Keep the Mac plugged in and awake. Nothing paid is ticked by default. The one paid option, creating new images, video, voices and music with ElevenLabs, is your own account and your own decision: as of September 2026 it has a free tier with small limits and paid plans from about $6 a month, so check elevenlabs.io/pricing before paying for anything.

The sign-ins are yours: your Mac password once for Homebrew, Allow on the Mac's permission pop-ups, Google on claude.ai's Connectors page, GitHub with a code in the browser, and two Chrome extensions. When each comes up, the checklist prints the steps in plain words, opens the right page and waits for you to press Return. Type `s` and Return to skip a step and finish it later.

At the end it checks every item it installed, prints `WORKING` or `NOT WORKING` with a reason, and saves the result in your vault under `outputs/setup/`. If you added any connections, quit Claude Code and open it again so it sees them; if you added Chrome, type `/chrome` inside Claude Code and switch it on.

**You can leave it for later.** Press Return with nothing ticked to install nothing extra. Run the checklist whenever you like from the Moblee folder:

```
python3 scripts/moblee-setup.py
```

and test that everything works, changing nothing, with:

```
python3 scripts/moblee-setup.py --check
```

`docs/10-connections.md` explains every item: what it connects, the exact sign-in steps, the cost, and what Claude will and will never do with it.

## Step 5: verify the install

A quick checklist to confirm everything is in place:

- The vault folder exists at the location you chose.
- The rules file is in the vault under the right name: `CLAUDE.md` for Claude, `AGENTS.md` for ChatGPT, and for both, `CLAUDE.md` with `AGENTS.md` as a link to it.
- `~/.claude/skills/` (for ChatGPT, `~/.agents/skills/`) contains the eight core skills: `brain/`, `compact/`, `companion/`, `galaxy/`, `wiki-capture/`, `wiki-interview/`, `wiki-to-pdf/`, `design-your-brand/` (plus any extras you ticked).
- With Claude: `~/.claude/hooks/bash-guard.py` exists, and the vault's `.claude/settings.local.json` lists the permission rules (the installer printed the counts).
- With ChatGPT: `~/.codex/hooks/bash-guard.py` exists, `~/.codex/hooks.json` holds its entry, you have done the Trust step, and `python3 scripts/moblee-doctor.py --prove-guard`, run from the Moblee folder, reports the guard as proved.
- The vault's `VERSION` file reads `0.8.1` for this release.
- `python3 scripts/moblee-doctor.py`, run from the Moblee folder, changes nothing and marks each finding `OK`, `LOOK` or `PROBLEM`.
- `python3 scripts/moblee-setup.py --check`, run from the Moblee folder, shows `WORKING` for each item you ticked.
- If you added the `vault` shortcut: typing `vault` in a new Terminal window takes you into the vault and prints the ready signal.
- Obsidian opens the vault and displays `Welcome.md`.
- With Claude: running `claude` in the vault's folder starts a Claude Code session that can see your vault.
- With ChatGPT: the vault's folder opens as a project in the ChatGPT app (choose Work at the top). <!-- verify on testdev -->

If anything is missing, run the installer again with the same answers (it finishes the job through the updater without touching what is already there), or run the checklist for a single item with `--only` and the item's key (`--list` prints the keys).

## What's next

You have a working vault. Move on to [03-first-conversation.md](03-first-conversation.md) to learn how to work with your assistant in this system, or jump to [04-first-ingest.md](04-first-ingest.md) to walk through ingesting your first piece of content.

The fastest path is to open your assistant in your vault and say "get me started"; it takes it from there.
