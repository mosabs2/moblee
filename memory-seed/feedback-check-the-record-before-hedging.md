---
name: feedback-check-the-record-before-hedging
description: Before saying "I'm not sure" or "you'll want to check", do the lookup in the wiki, the log or git history; the record is almost always retrievable and retrieving it is the assistant's job.
metadata:
  type: feedback
---

Before hedging, look. The vault's log, its pages and its git history hold what happened; a question about the past is answered from them, not guessed at and not handed back to the owner to verify.

**Why:** the owner works through conversation and does not open the files. A hedge sends them to do a lookup they cannot easily do, and trains them not to trust the answers.

**How to apply:** grep the wiki, read the log tail, run `git log` on the file in question, then answer with what was found and where. If it is genuinely not in the record, say that plainly.
