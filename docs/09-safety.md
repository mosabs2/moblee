# 09. Safety: why your assistant cannot delete your files

From v0.5 every Moblee vault carries a safety layer that the pack installs itself, so with Claude the owner has nothing to set up. It exists because a vault where your assistant can delete is a vault where one wrong "yes" loses work, and the owner should never have to be the last line of defence.

With Claude, everything on this page holds from the moment the installer finishes. With ChatGPT, one step is yours: the page holds once you have done the Trust step below and proved the guard.

## The three parts

**The delete guard.** A small program runs every time your assistant is about to execute a shell command. With ChatGPT it also runs before ChatGPT's file-editing tool is used, because that tool can delete and move files. It reads the command, and any script file the command would run, and refuses the destructive class: deleting a file or folder, emptying one, moving material out of the vault or into the Trash or a temporary folder, overwriting one page with another, rewriting git history, force-pushing, and the indirect spellings of all of these (a `find` that deletes, a piped delete, a one-line Python script, an AppleScript). When it refuses, your assistant is told what to do instead: move the material within the vault, or tell you what should go so you can remove it yourself. No guard can promise to catch every spelling a determined attacker could invent, which is why the permission rules and the written rule sit alongside it. If the guard itself ever hits an internal error, it lets the command through rather than freezing your assistant (it fails open), so the guard protects against a careless assistant and would not stop a hostile one. The same is true on ChatGPT, where a guard that crashes or takes too long lets the command through, and OpenAI describes hooks as a guardrail and not a complete boundary.

**The permission rules.** **With Claude:** Claude Code asks permission before running commands. Without an allow list, it asks for almost everything, and an owner who is asked forty times an hour learns to click yes without reading, which defeats every other safeguard. Moblee writes a starter allow list for routine work (reading, searching, editing inside the vault, committing) and a deny list that refuses deletion and history rewriting at this layer too. The allow list is broad only because the guard inspects every command regardless of it.

**With ChatGPT:** Moblee does not set this up for ChatGPT yet. ChatGPT's own sandbox is the second layer there: in its default mode the agent does not write outside the wiki folder and the Mac's temporary folders, or use the network, without asking you, and it cannot change `.git`. The sandbox does not stop a deletion inside the wiki; the guard does.

**The rule in writing.** `CLAUDE.md` (for ChatGPT, `AGENTS.md`) carries a hard rule: your assistant never deletes; finished material moves, and if something should go it tells you what and where, and you remove it yourself. `wiki/Identity.md` carries the same commitment as part of who your assistant is to you. The guard enforces the rule mechanically; the words are there so that your assistant also understands it.

## With ChatGPT: the Trust step

ChatGPT does not run a newly installed or changed guard until you have reviewed it. Until then the guard is skipped, and nothing on screen says so. The installer and the updater print these steps when they are due:

1. Open the ChatGPT menu and choose Settings.
2. Choose Hooks, under the heading Coding.
3. Open "User config".
4. Press Trust beside the hook that ends `bash-guard.py`.
5. Turn its switch on.

If ChatGPT is open, quit it and open it again afterwards, so that it reads the whole rules file.

You must do this again after any Moblee update that changes the guard. ChatGPT will not remind you. Then prove that the guard is live, from the Moblee folder:

```
python3 scripts/moblee-doctor.py --prove-guard
```

In the Moblee app, press Prove the guard on the home screen.

The check-up asks ChatGPT's agent to remove a folder and delete a page in a scratch wiki, away from your own. It reports the guard as proved only if the agent was refused and both are still there. It can take three minutes and uses a little of your ChatGPT allowance. Without `--prove-guard` the check-up marks the Trust step `CANNOT SEE`, because ChatGPT's files do not show whether you have pressed Trust.

## What this means day to day

Say "delete" and your assistant will say what it would rather do instead: move the file to an archive folder, or to `raw/processed/`. If you genuinely want something gone, your assistant cannot do it for you: the guard refuses the command outright and there is no "yes" that overrides it from inside Claude Code, or from inside a ChatGPT conversation once the guard is trusted. Your assistant will name exactly what should go and where it is, and you remove it yourself in Finder or in the Terminal. That is deliberate. The one person who can delete from your vault is you.

Git keeps every committed version. "Take me back to how the Index looked on 10 September" works for anything that was committed. You do not need to know how; your assistant does. With ChatGPT, approve the commit when asked, because work that is not committed has no earlier version.

## Things you may notice, and why

A few ordinary-looking actions are refused, on purpose. Your assistant cannot use `git stash`, or `git checkout` on a file that already exists, because both throw away uncommitted work; it can still restore a file that has gone missing from an earlier commit, and it can still make and switch branches. It cannot overwrite an existing page by redirecting output over it, or by copying or moving another file onto it; it edits pages with its editing tool and writes new ones with its writing tool. It cannot move anything out of the vault into a temporary folder, the Trash or another disk. And your assistant is told never to install or change the guard: that is done by the installer or the updater, which you run from the Terminal or through the Moblee app. With ChatGPT, anything written outside the wiki folder needs your approval, so say no to any request that names `~/.codex/` or `~/.agents/`. The one exception is `brand.css`, the brand file you asked for with "design my brand".

With ChatGPT you are also asked to approve each commit, because ChatGPT's sandbox protects the vault's `.git` folder. That is expected.

## The Moblee app and the same principle

From v0.8.1 the Moblee app can install the wiki, update it and add the extras you agreed with Claude. The principle holds, because the app is run by you: every change to Claude's settings still begins with you pressing a button on your own screen, and the app does its work by running the pack's own scripts, the same ones a Terminal user runs. Claude's part is to write down what was agreed in a small file in your wiki; the app reads that file and never writes to your wiki. The checklist has an option, `--yes`, that the app uses to skip the "Start now?" question after you press a tile's Add button. That option is refused when the checklist is started from inside Claude Code, since installing is your act and never Claude's. If the delete guard is ever missing, the app's home screen says "The safety guard is off. Switch it back on." and shows a Repair button, which runs the pack's own safety installer (`safety/install-safety.py`). With ChatGPT the app shows the Trust step on a screen of its own after an install, an update or a repair that changes the guard, and its home screen has a "Prove the guard" button. A skill Claude has drafted for you is copied into `~/.claude/skills/` only when you press Add, and an older copy of the same skill is moved to `~/.config/moblee/backups/`, never deleted.

## Checking that the guard is on

**With Claude:** Ask your Claude: "Is the delete guard installed and working?" It should run the guard's own test (a delete command is refused, a harmless one passes) and tell you the result. The updater and installer both run that test before they register the guard.

**With ChatGPT:** The guard's own test cannot show whether ChatGPT is running it. Run `python3 scripts/moblee-doctor.py --prove-guard` from the Moblee folder, as described under the Trust step above. In the Moblee app, press Prove the guard on the home screen.
