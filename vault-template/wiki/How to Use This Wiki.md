# How to Use This Wiki

Welcome to your wiki. This document explains how the structure works, why it's designed this way, and how to use it day to day. No technical knowledge is assumed.

## What This Is

This is your personal knowledge base, a persistent, compounding artifact that grows smarter with every source added and every question asked. It follows the [[Karpathy LLM Wiki Pattern]]: instead of retrieving raw documents from scratch on every question (the way ChatGPT file uploads or NotebookLM work), the LLM incrementally builds and maintains a structured, interlinked wiki. Cross-references are already in place. Contradictions have been flagged. Synthesis reflects everything ingested to date.

You curate sources, direct analysis, and ask the right questions. Claude handles the bookkeeping, summarising, cross-referencing, filing, and maintenance. Obsidian is the IDE; Claude is the programmer; the wiki is the codebase.

## Your Daily Workflow

### Reading Your Wiki

1. Open Obsidian on your computer.
2. In the left sidebar, expand the **wiki/** folder.
3. Click any page to read it, it opens in reading mode by default.
4. Click the pencil icon (top right) if you want to edit.

### Adding New Content

**Method 1, via Cowork (easiest).**
Open Cowork and say things like:
- "I had a meeting about [Your Topic] today, add it to the wiki."
- "Process the new files in raw/."
- "Add this to my [Your Domain] page: [paste text]."
- "I read an interesting article about [Your Topic], here's the link."

**Method 2, Obsidian Web Clipper (best for articles).**
1. Install the Obsidian Web Clipper extension in Chrome.
2. When you're reading an article, click the clipper icon, it saves directly into `Clippings/` in your vault.
3. Open Cowork and say "Process the new clipping(s)."
4. The clipping includes the source URL, author, and date automatically.

**Method 3, drop files into raw/.**
1. Open Finder.
2. Navigate to your vault folder.
3. Drag any file into the **raw/** folder (HTML, PDF, screenshot, text file).
4. Next time you open Cowork or Claude Code, say "Process the new files in raw/."

### Searching

Press **Cmd + O** (Quick Switcher), type any word and it finds matching pages instantly. This is the fastest way to find anything.

Press **Cmd + Shift + F** (Global Search), searches the content of every file. Use this when you remember a specific phrase or name.

## Understanding the Graph View

The Graph View (the web of connected dots) shows how your wiki pages link to each other. Recommended settings:

- **Orphan notes are hidden**, you'll only see files that have connections.
- **Each wiki page has its own colour** so you can tell them apart at a glance.
- **Arrows show link direction**, which page links to which.

To open it: click the graph icon in the left sidebar, or press **Cmd + G**.

If it looks cluttered, click the settings gear (top right of the graph) and make sure "Show orphans" is **off**.

## Understanding Wiki Links

When you see text like `[[Your Domain]]` in a page, that's a clickable link to that domain's page. This is what makes the wiki powerful, everything is connected. When you click a link, it takes you to that page. When you're on a page, the right sidebar shows **backlinks**, every other page that links TO this one.

For example, if you're on a page named `Health`, backlinks will show you every other page in your vault that has ever referenced Health, regardless of whether you remembered to look there.

## The Folder Structure

```
[Your Vault]/
├── wiki/              ← Your knowledge pages (the brain)
│   ├── Index.md       ← Master catalogue of all pages
│   ├── log.md         ← Chronological activity log
│   └── _context.md    ← Working state and current threads
├── Clippings/         ← Web Clipper drops articles here (auto-processed)
├── raw/               ← Drop new content here manually
│   ├── processed/     ← Already-ingested files
│   └── HOW-TO-ADD-CONTENT.md
├── outputs/           ← Reports and generated documents
├── CLAUDE.md          ← The schema (rules for Claude)
└── Welcome.md         ← Where to start
```

## The Three Operations

This wiki has three core operations, all handled by Claude.

### 1. Ingest (adding new knowledge)

Drop a source into `raw/` or clip an article with the Web Clipper, then ask Claude to process it. Claude reads the source, extracts key information, writes or updates the relevant wiki pages, updates the [[Index]], and logs the action in `wiki/log.md`. A single source may touch 10–15 wiki pages. Sources are immutable, Claude reads from them but never modifies the originals.

### 2. Query (asking questions then saving answers)

Ask Claude questions against the wiki. Claude searches relevant pages, synthesises an answer with citations, and presents it. The important part: **good answers can be saved back into the wiki as new pages.** A comparison, an analysis, a connection, these are valuable and should not disappear into chat history. After a substantive answer, Claude will offer to save it as a wiki page so explorations compound in the knowledge base.

### 3. Lint (health-checking the wiki)

Periodically, ask Claude to health-check the wiki. Claude looks for: contradictions between pages, stale claims that newer sources have superseded, orphan pages with no inbound links, important concepts mentioned but lacking their own page, missing cross-references, and data gaps that could be filled. This keeps the wiki healthy as it grows. To trigger this, say: "Lint the wiki" or "Health-check the wiki."

## The Activity Log

`wiki/log.md` is a chronological, append-only record of everything that happens in the wiki, ingests, queries, lint passes. Each entry is timestamped and categorised. This gives you a timeline of the wiki's evolution and helps Claude understand what has been done recently across sessions.

## Tips

**You don't need to learn markdown.** Just read the wiki pages and use Cowork to update them. Claude handles all the formatting.

**The wiki is alive.** Every time you chat with Cowork about something, a meeting, a health update, a training session, an article you read, ask Claude to add it. The wiki should grow every week.

**Search is your friend.** You'll rarely need to browse, just press Cmd+O and type what you're looking for.

## How to Connect Notes with Wikilinks: A Practical Guide

This section teaches you how to manually create the links that make the wiki's web of knowledge work. It's simpler than it looks.

### The basics

A **wikilink** is just a page name wrapped in double square brackets. When you type `[[Your Page]]` inside any note, Obsidian does three things:
1. It turns the text into a **clickable link** to `Your Page.md`.
2. `Your Page.md` now shows this note in its **backlinks** (right sidebar).
3. The **Graph View** draws a line connecting the two notes.

That's it. Two square brackets on each side. The text inside must match a page name exactly (capitalisation matters).

### Step-by-step: linking from any note

1. Open the note you want to add a link to.
2. Click the pencil icon (top right) to enter **editing mode**.
3. Place your cursor where you want the link.
4. Type `[[`, Obsidian will immediately show a dropdown of all your pages.
5. Start typing the page name (e.g., "Hea...") and select it from the dropdown.
6. Obsidian auto-completes and closes the brackets for you: `[[Health]]`.
7. Click the reading-view icon (book icon, top right) to exit editing mode, your link is now live.

### Linking to a section within a page

If you want to link to a specific heading (not just the whole page), type:
`[[Your Page#Equipment]]`, this links directly to the Equipment section of the page.

After you type `[[Your Page#`, Obsidian shows a dropdown of all headings on that page.

### Displaying different text

Sometimes you want the link to say something other than the page name. Use a pipe (`|`):
`[[Health & Medical|my health page]]`, displays as "my health page" but links to `Health & Medical`.

### What to link and what not to

**Do link:**
- Any wiki page name when it's mentioned.
- Any person, topic, or concept that has its own page.

**Don't link:**
- The same page name more than once in the same paragraph (first mention is enough).
- Common words that happen to match a page name in a context where you don't mean the page.

### Finding unlinked notes

Press **Cmd + Shift + F** and search for a page name, if results appear in notes that don't have `[[That Page Name]]` as a link, those are connection opportunities.

Or open **Graph View** (Cmd + G) and look for isolated dots with no lines, those are orphan notes waiting to be connected.

### Practice exercise: connect three notes

Once you have at least three pages in your wiki, try this to build muscle memory:

1. Open one of your domain pages, find a mention of another domain that isn't already linked. Wrap it in `[[Other Domain]]`.
2. Open the other domain's page, find a mention back that isn't linked. Wrap it.
3. Open **Graph View**, watch the line appear.

Every link you add makes the wiki smarter.

## What to Ask Cowork

Here are the kinds of things you can say to keep the wiki growing.

**Ingest**: "Process the new clipping(s)." · "I had a meeting today, add it to my [Your Domain] page." · "Add this article to [Your Domain]." · "Process the new files in raw/."

**Query**: "What does my wiki say about [Your Topic]?" · "Summarise everything I know about [Your Topic]." · "Compare the two analyses on my [Your Domain] page." · "Create a briefing document from my [Your Domain] page."

**Save an answer**: "Yes, save that as a wiki page" (when Claude offers after a substantive answer).

**Lint**: "Lint the wiki." · "Health-check the wiki." · "What's missing from my [Your Domain] page?" · "Are there any contradictions in my [Your Domain] page?"

## Related Pages

→ [[Karpathy LLM Wiki Pattern]]
→ [[Index]]
