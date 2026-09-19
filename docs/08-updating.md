# 08. Updating an existing vault

You never reinstall Moblee, and you never rebuild your wiki. Your pages, your log, your inbox and your daily notes are yours; the pack only ever replaces its own tooling around them.

## What an update changes, and what it never touches

An update replaces the scripts in `scripts/` and `dashboard/`, the skills in your Claude skills folder, the safety guard, and adds any new rules to `CLAUDE.md` by inserting them at named places rather than replacing the file. Inside `wiki/` it adds only `wiki/Identity.md` if you do not have one and, if you choose the learning path, its lessons page and one line for it in `wiki/Index.md`; it never touches your pages, `raw/`, `Clippings/`, your daily notes or the log (it only adds the `Daily Notes/_TEMPLATE.md` template if you have none). It commits the files it changed and leaves any work of yours that was not yet committed exactly as it was; the one exception is the learning-path line in `wiki/Index.md`, which it leaves uncommitted so that it goes in with your own next edits. Every file it replaces is first copied to `~/.config/moblee/backups/<date and time>/`, so nothing is lost even if you change your mind.

## How to update

1. Download the new Moblee package the same way you got the first one (a fresh `git clone`, or download and unzip). Keep it separate from your vault.
2. Open Terminal, go into the new Moblee folder, and run:

```
bash scripts/update.sh
```

3. It finds your vault by itself (it remembers where the installer put it). If it cannot, run `bash scripts/update.sh` followed by the path to your vault.
4. Answer the questions it may ask: whether to schedule the weekly health check, and whether to add the learning path. Wait for each question to appear before typing. Everything else is automatic.
5. When it says "Updated to", open Claude Code in your vault and say `orient`.

Running it twice is safe. Each step checks what is already there and skips it.

## If you would rather not use the Terminal

Ask whoever gave you Moblee for a clinic note. That is a file you drop into your `raw/` folder; your own Claude reads it, carries out the update step by step, and writes a report you can send back. One part still needs you: anything written into the hidden `~/.claude/` folder (the delete guard and its settings) has to be pasted into Terminal by you, because your Claude is not allowed to write there. The clinic note gives you the exact line to paste for that part.

## Adding the learning path later

The learning path is thirty-two short lessons on getting the most from the wiki, one an evening, with an optional reminder at nine each evening. It needs a Mac with Claude Code; the Windows track does not include it. The installer and the updater both ask whether you want it; if you said no, or want it now, run this from the folder where you downloaded Moblee (the same place you run the updater from), naming your vault:

```bash
python3 scripts/install-learning-path.py --vault ~/Wiki/MyWiki
```

Use `--hour 20` for a different reminder time, or `--no-reminder` to have the lessons without a notification. Running it again is safe: the lessons page, with its record of which lessons you have had, is never replaced. Then open Claude Code in your vault and say **lesson**. If the reminder never appears, allow notifications for Script Editor in System Settings, under Notifications.

## Checking what version you have

The file `VERSION` in your vault says which version of the pack it was last updated to. Vaults installed before v0.5 have no such file, and the updater treats them as "before 0.5".
