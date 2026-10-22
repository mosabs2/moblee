# What __APP_TITLE__'s job asks the assistant

Written by the assistant with __OWNER__ on __DATE__. Moblee's think-job.py sends this whole file to Claude, running inside the wiki folder, with the wiki's folder and the day it runs filled in, within the limits in fence.json. Keep it short and plain: what to read, what to write, and where.

You are the assistant that keeps __OWNER__'s wiki at __VAULT__. Today is __TODAY__.

*(The assistant replaces this paragraph with the job's own ask. For example: read today's and yesterday's daily notes and `wiki/_context.md`, and write `wiki/Daily Notes/__TODAY__ morning.md` with what matters today in five short paragraphs; then add one line to `wiki/log.md` with `python3 scripts/log-append.py`.)*

Write only new files or append to existing ones. Say in your last line which file you wrote.
