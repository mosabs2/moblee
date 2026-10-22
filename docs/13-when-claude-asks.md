# 13. When Claude asks, and when it says no

Claude asks before it does some things, and now and then it refuses to do one. Both are Claude's own behaviour, set by a switch you can see, and Moblee sets that switch for you. This page says what you will meet, what each thing means, and what to do, in the order you are likely to meet them.

## The switch beside where you type

In the Claude app, beside the box where you type, is a switch with four settings. It is Claude's working mode. Moblee sets your wiki to **Accept edits**, which means: when Claude changes a page in your wiki, or a file in something it has built for you, it just does it; when it wants to run a command, it asks, unless Moblee has already said that command is fine.

Moblee has said yes in advance to the ordinary ones: reading and searching, saving to your wiki's history, moving a file within the wiki, and from 0.12.0 the tools a build needs (the programs that fetch a thing's parts and run them, and a history of its own like the wiki's). Underneath every one of those sits the delete guard, which reads each command before it runs and refuses deletion in your wiki whatever the switch says (`09-safety.md`).

The other three settings: **Manual** (called Default in some versions of the app) asks before every edit as well, which is tiring and teaches you to press yes without reading. **Plan** lets Claude read and propose but change nothing, useful when you want to think first. **Auto** hands anything Moblee has not already settled to a separate check inside Claude, which decides for you and sometimes says no (below). You can change the switch at any time; Moblee only sets it when you have not chosen a setting yourself.

**One thing has to be true first:** Claude reads a folder's own rules only once it trusts the folder, which it asks you about the first time you open Claude there. Moblee marks your wiki's folder as trusted for you when it installs or updates, so you are never asked, and the rules apply from your first conversation. If you ever are asked, the answer is yes; and if Claude seems to ask before everything, Check my wiki says whether the folder is trusted and Repair puts it right.

## When Claude asks

A small card appears naming what Claude wants to do. You will see it for: installing software (an install is always yours); switching on a job that runs when you are not there; sending your wiki's history to a website such as GitHub; and anything to do with Claude's own settings folder, which asks whatever the switch is set to, by design. Read the card. If it names something you asked for, choose yes. If it names something you did not ask for, choose no and ask Claude what it was doing. The card may also offer a yes that means "and do not ask me again": never choose that on a card you did not understand. Choose the one-time yes, and ask.

If Claude asks for almost everything, something is missing: press **Check my wiki** in the Moblee app, which will say whether Moblee's rules are in place and offer Repair if they are not.

## When Claude says no

Sometimes a line appears saying an action was **denied by auto mode**, with a reason in square brackets, and the thing Claude was doing stops. This is Claude's own safety check, which runs when the switch is on Auto. It refuses anything that looks like your personal material being moved out of where it was found: for instance, when Claude has just read your conversations with it, or a folder of your sign-ins, and then tries to write a file or save to the wiki. Moblee cannot change this check, and it should not; it is there for you.

What to do, any one of these:

1. Say in your next message exactly what you want done, naming what Claude is reading and where it is writing. Claude may then try again.
2. If it was the check-up that was refused, press **Check my wiki** in the Moblee app instead. The app runs it outside Claude.
3. Move the switch to Accept edits or Manual. The same action then asks instead of refusing.

Moblee tells this check about its own two tools, the check-up and the end-of-reply save, so that they are settled before the check sees them. If Check my wiki says Auto mode has not been told about them, press Repair.

One habit keeps this from happening at all: when you ask Claude for a readout of your own conversations with it, ask in a conversation of its own, and press Check my wiki first if you want the check-up that day.

## When the delete guard refuses

That is a different message, beginning "Blocked by the vault safety gate". It means Claude tried to delete, overwrite or move something out of your wiki, or rewrite its history, and was stopped. Nothing is wrong. Claude will say what it wanted to do and offer to move the thing instead; if something truly should go, Claude names it and you remove it yourself (`09-safety.md`). From 0.12.0 the guard knows the difference between your wiki and a thing built outside it in the builds' home, `~/Apps`, so clearing a build's own generated folders there, or putting a file back in a thing Claude built, no longer trips it. Nothing in your wiki is ever cleared.
