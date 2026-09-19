# Building something made to measure

The items on the Moblee checklist are the same for everyone. What makes a wiki worth having is the part that is not: the thing built for one owner because of how that owner lives. This is the way to build it. Read `builders-rules.md` alongside.

## 1. Notice

A build starts from something seen, never from a wish to be useful. The signs: the owner does the same thing by hand for the third time; they ask for the same summary every week; they bring the same kind of file again and again; they say "I wish it could" or "I keep forgetting to". Look in `wiki/log.md` and on the owner's page for the pattern before proposing anything, so the proposal can name it: "You have pasted your training numbers in three Sundays running."

## 2. Propose one small thing

Say what would be built, in one or two lines, what it would save them, and what it would cost: their time now, any account it needs, any money. Propose the smallest version that would be useful this week. A page and a habit often beat a script; a script the owner starts by asking often beats one that runs by itself. Wait for a yes. A no goes under "Said no to" with the date.

## 3. Build it inside the vault

Everything made for the owner lives in the vault, where git keeps every version and the owner can see it: pages under `wiki/`, data under `wiki/data/`, scripts under `scripts/`, drafts of skills under `made-for-you/skills/`. Nothing is built in a temporary folder or a hidden place. Use what the Mac already has (its own Python, its own tools) before asking for anything to be installed; if something must be installed, that is a checklist item or the owner's own decision, never a quiet step.

## 4. Prove it, in front of the owner

Run it once with them watching, on their real material, and read the result together. If it fetches something, show what it fetched. If it writes a page, open the page. If it can fail (no network, a changed website, an expired sign-in), make it fail once on purpose and check that the failure is visible: a line in the log, a note on the page, a message the owner will see. A build is not finished until its failure has been seen to show itself.

## 5. Record it

On the owner's page under "Made for the owner": what it is, where it lives, how it is started, what it depends on, the date, and why it was built, in their words. In `wiki/log.md`, the usual entry. Commit. A build that is not written down is a build the next session will not know exists.

## 6. Look again in a month

At the next setup review, or a month on, check whether it is still used and still right. If it has quietly stopped, find out why before mending it; the owner's life may have moved on, which is a good reason to retire it. Retiring means moving it to an `archive/` folder and noting it on the page. Nothing is deleted.

## Sizes of build, smallest first

1. **A page and a phrase.** A template page and a sentence the owner says ("log my session"). Claude fills the page from the conversation. So that any later session knows the phrase, register it in one line under "Domain-specific patterns" in the vault's `CLAUDE.md` (the phrase, and the page it fills).
2. **A data file and a page.** A CSV under `wiki/data/` that grows, and a page that reads it.
3. **A script the owner starts by asking.** Under `scripts/`, run by Claude when asked. Fetches, converts, tidies.
4. **A skill.** When a build has its own way of being asked for and its own steps, it becomes a skill. Draft it under `made-for-you/skills/<name>/`, and it reaches Claude through the Moblee app (see the companion's "Building something made to measure").
5. **Something that runs by itself on a schedule.** The largest step, and the one most likely to fail unseen. Build it only after the by-hand version has been used for a few weeks, follow every scheduled-job rule in `builders-rules.md`, and tell the owner plainly that it will run when they are not looking and how they will know if it stops. The owner switches it on with Terminal lines Claude gives them; Claude never loads it.

Start at the smallest size that works. Move up only when the owner's use has outgrown it.
