# 04. Your first ingest: a worked example

This document walks through ingesting your first source from start to finish. The example uses a hypothetical New York Times article on home composting; substitute whatever you're actually reading.

## The setup

Suppose you read an article called "Why Your Compost Bin Smells, and How to Fix It" in the New York Times, dated 12 March 2026. You want to save the practical content so you can act on it later, and you also want to start a wiki page on home composting that future reading will build on. The article is open in your browser.

Your vault is at `~/Wiki/MyWiki`. You have Obsidian open with the vault loaded, Claude Code or the ChatGPT app installed, and the Obsidian Web Clipper extension in your browser.

## Step 1: clip the source

In your browser, click the Obsidian Web Clipper icon. The extension reads the page, extracts the main text, and saves a clean markdown file with YAML frontmatter (source URL, author, date) into your vault's `Clippings/` folder. The filename will be something like `Why Your Compost Bin Smells.md`.

Open Obsidian and confirm the file landed in `Clippings/`. You can preview it; it should be the article text without the surrounding ads and navigation.

If you don't use the Web Clipper, the equivalent is to save the page as a markdown file by hand into `Clippings/`, or drag a PDF copy into `raw/`. Anything in those two folders is fair game for the ingest pipeline.

## Step 2: start a Claude session

**With Claude:** Open Terminal. Type:

```
vault
```

The `vault` function cds into your vault, shows you what's changed since the last commit (you should see the new clipping listed as an untracked file), commits it under a "session start" message, prints recent history, and signals ready. Then:

```
claude
```

This starts a Claude Code session inside the vault. Claude immediately reads `CLAUDE.md` and `wiki/_context.md` so it knows your conventions and current working state.

**With ChatGPT:** Open the ChatGPT app, choose Work at the top, and open the vault's folder as a project. <!-- verify on testdev --> ChatGPT reads your conventions from `AGENTS.md`.

## Step 3: ask for the ingest

Type into the session:

> Ingest the new clipping in Clippings/.

Your assistant responds with a short acknowledgement and starts reading. You'll see it:

1. **Read the clipping**: open `Clippings/Why Your Compost Bin Smells.md` and parse the content.
2. **Search the wiki** for any existing pages that relate to composting, gardening, food waste, or household systems. On a fresh vault, there are no matches yet, so it proposes creating a new top-level page.
3. **Ask for confirmation** before creating that page. Something like: "There's no existing page on composting. May I create `wiki/Composting.md` as a new top-level domain?"

Answer yes. Your assistant continues.

4. **Write the page.** Following the house style in `CLAUDE.md`, it drafts `wiki/Composting.md` in paragraph form: what composting is at the level you might want to think about it, the source's specific claims about why bins smell (too wet, wrong carbon-to-nitrogen ratio, anaerobic pockets) and how to fix it, with the article cited inline.
5. **Add a source attribution line.** At the end of the section informed by the article, it appends `Source: [Why Your Compost Bin Smells, and How to Fix It](URL), New York Times, 12 March 2026.`
6. **Append a log entry.** In `wiki/log.md`, it appends:

   ```
   ## [2026-05-15 14:32 +03] ingest | Why Your Compost Bin Smells, NYT

   Ingested a New York Times article on home composting (12 March 2026). Created a new top-level page wiki/Composting.md covering the article's core claims (carbon-to-nitrogen ratio, moisture, aeration) and three specific fixes (turning, adding browns, draining excess water). Source moved to Clippings/processed/.
   ```

7. **Update the Index.** Because this is a new top-level page, it adds a one-line entry to the Domains section of `wiki/Index.md`: `[[Composting]]: home composting troubleshooting and practice.`
8. **Refresh _context.md** if the new page changes the working state. On a brand-new vault, it does: this is your first content. Your assistant bumps the Last refreshed line and adds a paragraph to the Recent significant additions section.
9. **Move the source.** `Clippings/Why Your Compost Bin Smells.md` moves to `Clippings/processed/Why Your Compost Bin Smells.md`.
10. **Commit to git.** Your assistant runs `git add .` and `git commit -m "ingest: Why Your Compost Bin Smells, NYT"`. With Claude this is automatic. (In Cowork rather than Claude Code, this step is deferred to your next `vault` invocation.) With ChatGPT you are asked to approve the commit, because ChatGPT's sandbox protects the vault's `.git` folder. That is expected.

## Step 4: inspect the result

In Obsidian, open `wiki/Composting.md`. You'll see the page your assistant wrote. Open `wiki/Index.md`; the new entry should be there. Open `wiki/log.md`; the dated entry is at the bottom. Open `Clippings/processed/`; the source has moved.

Click any `[[Wikilink]]` in `Composting.md`. Obsidian will offer to create the linked page if it doesn't exist yet, or jump to it if it does.

## Step 5: ask a follow-up

The wiki is now live. Try a query:

> What does my wiki say about composting?

Your assistant reads `wiki/Composting.md` and answers in your voice, citing the page. Because there's only one source so far, the answer is short. As you ingest more material (other articles on composting, a book on soil health, a note from a conversation with a friend who composts), the page accumulates and the answers get richer.

## What you've just demonstrated

By the end of this one ingest, you've used every piece of the system:

- A source was added to `Clippings/`.
- Your assistant read it and wrote into the wiki layer.
- A log entry was appended (append-only chronology).
- The Index was updated (one-line catalogue addition).
- `_context.md` was refreshed (working state moved).
- The source moved to `processed/` (file movement is part of ingest, not optional cleanup).
- A git commit captured the whole change atomically.

The same sequence repeats for every ingest, whatever the source and whichever pages it touches.

## What to do next

The next time you read something worth keeping, drop it in `Clippings/` or `raw/`, start a session as in Step 2 (with Claude, `vault` then `claude`), and ask your assistant to ingest. Within a few weeks the wiki will start having interesting cross-references; within a few months it becomes genuinely useful as a personal reference.

For the bundled skills (queries, PDF rendering, brand design), see [05-skills.md](05-skills.md). For the deeper "why" behind the system, see [06-karpathy-method.md](06-karpathy-method.md).
