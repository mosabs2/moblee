# 09. Safety: why Claude cannot delete your files

From v0.5 every Moblee vault carries a safety layer that is installed with the pack, not left to the owner to set up. It exists because a vault where Claude can delete is a vault where one wrong "yes" loses work, and the owner should never have to be the last line of defence.

## The three parts

**The delete guard.** A small program runs every time Claude is about to execute a shell command. It reads the command and refuses anything that would delete a file or folder, empty a folder, rewrite git history or force-push, however the command is spelled, including the indirect forms (a `find` that deletes, a piped delete, a one-line Python script that removes files). When it refuses, Claude is told to move the material instead. It fails safe: if the guard itself ever hits an error, the command runs as it would have before, so a bug in the guard can never freeze your Claude.

**The permission rules.** Claude Code asks permission before running commands. Without an allow list, it asks for almost everything, and an owner who is asked forty times an hour learns to click yes without reading, which defeats every other safeguard. Moblee writes a starter allow list for routine work (reading, searching, editing inside the vault, committing) and a deny list that refuses deletion and history rewriting at this layer too. The allow list is broad only because the guard inspects every command regardless of it.

**The rule in writing.** `CLAUDE.md` carries a hard rule: never delete without explicit approval in the same message, and finished material moves rather than goes. `wiki/Identity.md` carries the same commitment as part of who Claude is to you. The guard enforces the rule mechanically; the words are there so that Claude also understands it.

## What this means day to day

Say "delete" and Claude will say what it would rather do instead: move the file to an archive folder, or to `raw/processed/`. If you genuinely want something gone, say so for that specific item and confirm; Claude will name exactly what will go and wait for your yes, and even then it moves rather than deletes wherever it can.

Git keeps every version of every file in the vault. "Take me back to how the Index looked on 10 September" is always possible. You do not need to know how; your Claude does.

## Checking that the guard is on

Ask your Claude: "Is the delete guard installed and working?" It should run the guard's own test (a delete command is refused, a harmless one passes) and tell you the result. The updater and installer both run that test before they register the guard.
