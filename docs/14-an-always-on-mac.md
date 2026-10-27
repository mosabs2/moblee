# 14. An always-on Mac, for the owner who wants one

Most owners need none of this. Everything Moblee builds is made for a laptop that is closed for much of the day: a job that missed its hour runs once at the next wake, a morning page is written when the lid opens, and a page that must be reachable while the laptop sleeps goes on the web. Read on only if you want work to happen while your laptop is shut, flat or in another country.

## The idea in one paragraph

A small Mac that stays on at home becomes the place where work happens, and your laptop and your phone become the places where you ask for it and hear back. The laptop can be shut; the morning page is still written, the Saturday check still runs, the weekly copy of the wiki's history is still made, and your phone buzzes when something is ready. This is the pattern Moblee was built around, and the rest of this page describes it.

## What you would need

**A Mac.** A base Mac mini is ample. It needs a screen and keyboard for the first day only.

**A place.** Steady power, a wired connection if you can, and somewhere it will not be unplugged by mistake. A small battery backup (a UPS) is worth considering.

**Three settings, and one decision.** In System Settings: never sleep, start up again after a power cut, and wake for network access. Automatic login lets it come back by itself after a power cut, but that needs FileVault, the disk encryption, switched off, which means anyone holding the machine can read its disk. Make that decision on purpose, for the place it lives in, and write it down. With FileVault on, it waits at the unlock screen after a power cut until someone types the password.

**Accounts you mostly have.** Claude on a paid plan; Obsidian Sync (or another sync) so the wiki is the same on both machines, and never the iCloud Desktop folder, which background jobs cannot use; the ntfy app for alerts (Moblee's Alerts item); and a private network between your devices (Moblee's Reach item).

## How it fits Moblee

Install Moblee on the always-on Mac exactly as on a laptop. Then, in conversation, move the jobs you want running all the time: you switch a built thing's job on there, by pressing its tile in the Moblee app on that Mac, and your assistant takes it off the laptop's schedule for you and says when it has. One rule holds: only one Mac edits the wiki at a time; the other leaves notes in `raw/`. Obsidian Sync carries pages and scripts between them, but not Claude's settings, the delete guard or the scheduled jobs themselves, which the Moblee app on each Mac keeps.

## What it costs

A machine to look after. The things that go wrong are quiet: a job that stops without saying so, a permission macOS withdraws from a background program after an update, an external drive that drops off. Two habits cover most of it: every job alerts your phone when it fails (Moblee's jobs do), and once a month you ask your assistant to look at every job on the machine and say what is working and what is not.

## A setup order

1. On the laptop first, free of charge: get the wiki out of the Desktop, Documents and Downloads folders if it is in one (iCloud can hold those folders' files back from a job running on its own), and choose the Alerts item, so that the jobs you already have tell you when they fail.
2. The Mac itself: first boot with a screen, the three settings and the FileVault decision, Tailscale (or your own network), Claude, Obsidian, and Moblee.
3. The wiki on both: Obsidian Sync with all file types switched on, and the one-writer rule.
4. Move the jobs, one at a time, each with its alert, and watch each run once before moving the next.
5. The extras, when you want them: the Memory search item, Time Machine to an external drive, and spoken briefings of your own.

Nothing in this document installs or changes anything by itself; it is a plan to talk through with your assistant, a step at a time, with your yes before each.
