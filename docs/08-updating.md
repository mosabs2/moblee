# 08. Updating an existing vault

You never reinstall Moblee, and you never rebuild your wiki. Your pages, your log, your inbox and your daily notes are yours; the pack only ever replaces its own tooling around them.

## What an update changes, and what it never touches

An update replaces the scripts in `scripts/` and `dashboard/`, the skills in your Claude skills folder, the safety guard, and adds any new rules to `CLAUDE.md` by inserting them at named places rather than replacing the file. The only thing it ever adds inside `wiki/` is `wiki/Identity.md`, and only if you do not have one; it never touches your pages, `raw/`, `Clippings/`, `Daily Notes/` or the log, and it commits only the files it changed, leaving any work of yours that was not yet committed exactly as it was. Every file it replaces is first copied to `~/.config/moblee/backups/<date and time>/`, so nothing is lost even if you change your mind.

## How to update

1. Download the new Moblee package the same way you got the first one (a fresh `git clone`, or download and unzip). Keep it separate from your vault.
2. Open Terminal, go into the new Moblee folder, and run:

```
bash scripts/update.sh
```

3. It finds your vault by itself (it remembers where the installer put it). If it cannot, run `bash scripts/update.sh` followed by the path to your vault.
4. Answer the one question it may ask (whether to schedule the weekly health check). Everything else is automatic.
5. When it says "Updated to", open Claude Code in your vault and say `orient`.

Running it twice is safe. Each step checks what is already there and skips it.

## If you would rather not use the Terminal

Ask whoever gave you Moblee for a clinic note. That is a file you drop into your `raw/` folder; your own Claude reads it and does the update for you, step by step, and writes a report you can send back. Nothing about the update is different; only who types.

## Checking what version you have

The file `VERSION` in your vault says which version of the pack it was last updated to. Vaults installed before v0.5 have no such file, and the updater treats them as "before 0.5".
