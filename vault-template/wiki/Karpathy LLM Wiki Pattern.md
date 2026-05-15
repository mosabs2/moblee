# Karpathy LLM Wiki Pattern

A methodology for building personal knowledge bases using LLMs, originated by Andrej Karpathy in a viral tweet (2 April 2026) and accompanying [idea file](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) on GitHub.

## Core Idea

Instead of retrieving raw documents from scratch on every question (the way RAG systems, NotebookLM, and ChatGPT file uploads work), the LLM incrementally builds and maintains a persistent wiki, a structured, interlinked collection of markdown files. When a new source is added, the LLM reads it, extracts key information, and integrates it into the existing wiki. The knowledge is compiled once and kept current, not re-derived on every query.

The wiki is a persistent, compounding artifact. Cross-references are already in place. Contradictions have been flagged. Synthesis reflects everything ingested to date.

## Three-Layer Architecture

1. **Raw sources**: a curated collection of source documents (articles, papers, images, data files). Immutable, the LLM reads from them but never modifies them.
2. **The wiki**: a directory of LLM-generated markdown files: summaries, entity pages, concept pages, comparisons, an index, a synthesis. The LLM owns this layer entirely.
3. **The schema**: a configuration document (e.g., `CLAUDE.md`) that tells the LLM how the wiki is structured, what the conventions are, and what workflows to follow. The human and LLM co-evolve this over time.

## Core Operations

- **Ingest**: process a new source: read it, write a summary, update the index, update relevant pages across the wiki, log the action.
- **Query**: answer questions against the wiki with citations. Good answers can be filed back into the wiki as new pages.
- **Lint**: periodic health-check for contradictions, stale claims, orphan pages, missing cross-references, and data gaps.

## Key Insight

The tedious part of maintaining a knowledge base is not the reading or the thinking, it is the bookkeeping. Updating cross-references, keeping summaries current, noting when new data contradicts old claims. Humans abandon wikis because the maintenance burden grows faster than the value. LLMs handle this because the cost of maintenance is near zero.

The human's job: curate sources, direct the analysis, ask good questions, and think about what it all means. The LLM's job: everything else.

## Origin

Karpathy described the idea as related in spirit to Vannevar Bush's Memex (1945), a personal, curated knowledge store with associative trails between documents. Bush's vision was private, actively curated, with the connections between documents as valuable as the documents themselves. The part he could not solve was who does the maintenance.

Karpathy also introduced the concept of the "idea file": in the era of LLM agents, sharing the idea is more valuable than sharing specific code, because the other person's agent can customise and build it for their specific needs.

## This Wiki's Implementation

This vault follows the Karpathy pattern using Obsidian as the reader and Claude (via Cowork or Claude Code) as the LLM maintainer. See [[How to Use This Wiki]] for practical usage and `CLAUDE.md` (at the vault root) for the full schema.

## Source

- Andrej Karpathy, [@karpathy tweet thread](https://x.com/karpathy/status/2040470801506541998), 2 April 2026
- Andrej Karpathy, [llm-wiki idea file](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f), GitHub Gist

## Related Pages

→ [[How to Use This Wiki]]
→ [[Index]]
