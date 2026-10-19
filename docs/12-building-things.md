# 12. Building things on your wiki

Owners build things on their wikis. A health dashboard over a fitness band's numbers. A planner for a course. A page that shows a season's scores. A concierge that books tables. You do not need to code to have one. You say what you want in your own words, and your assistant does the rest: it works out where the thing should live, plans it in a way you can say yes to, writes it, opens it on your screen to prove it works, and writes it down so that any later conversation knows it exists and how it works.

## How it goes

1. **You say what you want.** "I want a page that shows my gym sessions by week." "Make me something that checks the tide times every morning." Your assistant asks at most three questions, one at a time, and only the ones your words have not answered: what it should show or do, when you will look at it and on what, and what it needs to read.
2. **It plans it on one screen.** What it will look like, where it will live, what it will read and write, what it will cost (nothing, an account, money a month), what it will not do, and how long it will take. Nothing is written until you say yes. "Later" is fine.
3. **It writes the page first, then the code.** Every build has a page in your wiki, under `wiki/Projects/`, with the plan on it before a line of code exists. If the build stops halfway, the page says what was meant.
4. **It builds the smallest useful version**, from Moblee's standard parts: a small server that shows the page on your Mac only, a page in the Mac's own typeface, the files it reads and writes kept as plain files you can open, and, if it runs on a schedule, a job that leaves a record every time.
5. **It opens it on your screen.** You look at it together, with your real data. If it can fail (no internet, a website that changed, no data yet), your assistant makes it fail once on purpose, so you both know what it looks like when something is wrong before it ever is, and so you can see that it says so calmly rather than breaking silently.
6. **It writes it down and saves.** The page gets a dated line. Your own page in the wiki gets one line pointing at it. The wiki saves.
7. **It tells you how to open it**, in three lines, and stops.

Say "build me", "make me", "I want an app that", "I want a dashboard", or anything like it. The `build` skill does the work; the companion hands over to it when a wish is this size.

## Where things live

Two places, chosen by what the thing needs.

**In the wiki, at `apps/<name>/`**, for anything that runs on what the Mac already has: Python and a browser. Nearly everything an owner asks for is this. The wiki's history keeps every version of the code and the data, you can see the folder, and the thing comes with the wiki if you move it to another Mac.

**Outside the wiki, at `~/Apps/<name>/`**, for anything that needs installing (a language runtime, a database, packages) or must be reached from outside your Mac. Installs are large and change constantly and do not belong in a synced wiki. The wiki keeps the thing's page, a small pointer folder in `apps/`, and anything it produces that you would mind losing under `wiki/data/<name>/`. The folder outside gets its own history.

Whichever it is, the thing's page is `wiki/Projects/<Title>.md`, and `wiki/Projects.md` is the index of everything built, one short section each.

## The parts every build shares

- **The server** shows the page on your Mac only. Nothing on the network can reach it, and another website open in your browser cannot use it. It stops by itself when you close the tab, or after half an hour with nobody looking. Closing the tab is the only "off" you ever do.
- **The launcher**, `Open <Title>.app` in the thing's folder, starts the server if it is not running and opens the page. Double-click it, or keep it in the Dock. Or say "open <Title>" to your assistant.
- **The data** is plain files in `data/`: JSON, CSV, markdown. Yours. A change to the code never touches them. Every save keeps the previous copy.
- **A job**, if the thing runs on a schedule, writes a record every time it runs, succeed or fail, so a job that has quietly stopped is seen at the next check-up. You switch it on with two lines in a Terminal window of your own; your assistant never switches on anything that runs when you are not looking.
- **A secret** (an API key, a password) goes in your Mac's Keychain. You type it at a prompt; it never goes into a file in the wiki, onto a Terminal line, or into a conversation.
- **A port browsers accept.** The port is the number at the end of the page's address, like `:7412`. Browsers refuse a handful of them without saying why; Moblee chooses from a range they all accept.

## Changing a thing

Tell your assistant what you want different, in your own words. It says what will change and what will not, changes the code and never your data, shows you the result, and adds a dated line to the page. Every earlier version is in your wiki's history, and the page says which one to go back to.

## When something stops working

Say "something is wrong" to your assistant. The check-up reads every folder in `apps/` and says, in plain words, whether each thing's record is whole, whether its job last ran and succeeded, whether its port is one browsers accept, whether an install folder has crept into the wiki, and whether a thing recorded as living outside the wiki is still there. Each finding has an entry in the companion's field guide (F50 to F54) saying what fixes it and who does the fix. Nothing is deleted.

## What your assistant never does when building

It never installs software itself: an install is a Terminal line it gives you, or a Moblee item you press. It never switches on a scheduled job. It never writes a secret into a file. It never makes anything reachable from outside your Mac; that is a separate decision you would make knowingly, later. It never deletes, and it never overwrites your data. And it never builds on a wish of its own: a build starts from what you asked for.

## Moving something in that somebody else built

A thing built in another owner's wiki and sent to you as a folder is fitted the same way: your assistant reads it first, says in plain words what it does and what it needs, and asks before anything is installed. Anything in it that would run the installer for you, set up scheduled jobs without your hand, or keep a secret in a file is changed to Moblee's way before it is used. It then goes through the same loop as a new build, page and all.
