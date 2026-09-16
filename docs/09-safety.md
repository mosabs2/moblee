# 09. Safety: why Claude cannot delete your files

From v0.5 every Moblee vault carries a safety layer that is installed with the pack, not left to the owner to set up. It exists because a vault where Claude can delete is a vault where one wrong "yes" loses work, and the owner should never have to be the last line of defence.

## The three parts

**The delete guard.** A small program runs every time Claude is about to execute a shell command. It reads the command, and any script file the command would run, and refuses the destructive class: deleting a file or folder, emptying one, moving material out of the vault or into the Trash or a temporary folder, overwriting one page with another, rewriting git history, force-pushing, and the indirect spellings of all of these (a `find` that deletes, a piped delete, a one-line Python script, an AppleScript). When it refuses, Claude is told what to do instead: move the material within the vault, or tell you what should go so you can remove it yourself. No guard can promise to catch every spelling a determined attacker could invent, which is why the permission rules and the written rule sit alongside it. One design choice to know about: if the guard itself ever hits an internal error, it lets the command through rather than freezing your Claude (it fails open), so the guard is protection against a careless assistant, not a lock against a hostile one.

**The permission rules.** Claude Code asks permission before running commands. Without an allow list, it asks for almost everything, and an owner who is asked forty times an hour learns to click yes without reading, which defeats every other safeguard. Moblee writes a starter allow list for routine work (reading, searching, editing inside the vault, committing) and a deny list that refuses deletion and history rewriting at this layer too. The allow list is broad only because the guard inspects every command regardless of it.

**The rule in writing.** `CLAUDE.md` carries a hard rule: never delete without explicit approval in the same message, and finished material moves rather than goes. `wiki/Identity.md` carries the same commitment as part of who Claude is to you. The guard enforces the rule mechanically; the words are there so that Claude also understands it.

## What this means day to day

Say "delete" and Claude will say what it would rather do instead: move the file to an archive folder, or to `raw/processed/`. If you genuinely want something gone, Claude cannot do it for you: the guard refuses the command outright and there is no "yes" that overrides it from inside Claude Code. Claude will name exactly what should go and where it is, and you remove it yourself in Finder or in the Terminal. That is deliberate. The one person who can delete from your vault is you.

Git keeps every version of every file in the vault. "Take me back to how the Index looked on 10 September" is always possible. You do not need to know how; your Claude does.

## Things you may notice, and why

A few ordinary-looking actions are refused, on purpose. Claude cannot use `git stash`, or `git checkout` on a file that already exists, because both throw away uncommitted work; it can still restore a file that has gone missing from an earlier commit, and it can still make and switch branches. Claude cannot overwrite an existing page by redirecting output over it, or by copying or moving another file onto it; it edits pages with its editing tool and writes new ones with its writing tool. Claude cannot move anything out of the vault into a temporary folder, the Trash or another disk. And Claude cannot install or update the guard itself: that is done by the installer or the updater, from the Terminal, so that no conversation can weaken it.

## Checking that the guard is on

Ask your Claude: "Is the delete guard installed and working?" It should run the guard's own test (a delete command is refused, a harmless one passes) and tell you the result. The updater and installer both run that test before they register the guard.
