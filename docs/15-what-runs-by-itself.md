# 15. What runs by itself, and what it needs from you

Nothing in Moblee runs on a timer until you have chosen it, and everything that does is made for a laptop that is closed for much of the day: a job that missed its hour runs once at the next wake, however many days were missed, and says so in its own record. Here is the whole list, in the order most owners take it.

## Three things that come with every wiki

Three small things run without being chosen, and none of them runs on a timer. **The delete guard** runs each time your assistant is about to run a command. **The end-of-reply save** runs each time a reply finishes, and saves the wiki's history. **The first-week tour** (from 0.16.0, with Claude) runs when a conversation starts: on your first five days of use it asks your assistant to offer one thing the wiki can do at the end of its first answer that day, and after that it says nothing. It reads and writes one small file, `~/.config/moblee/state/first-days.json`, uses no network, and if anything goes wrong it stays silent rather than hold a conversation up. "Stop the tour" ends it early.

**The mail pass is not on this list.** It runs only when you say "orient", and only once you have said yes to it.

## The Saturday check

The wiki checks itself every Saturday morning (the "Weekly health check" item) and writes a report. From 0.12.0 the same run first makes **a copy of the wiki's whole history** as one file, outside the wiki, under Moblee's own folder, and keeps every week's copy. Nothing is ever removed, and when there are more than about six months of them, Check my wiki says how many and names the oldest. It is a second copy on the same Mac: for a copy somewhere else, choose the GitHub item and ask your assistant to keep the wiki's history in a private place of its own on GitHub, or let Time Machine do it.

## The weekly tidy

The Saturday report used to be read by nobody. The "Weekly tidy" item puts a job behind it: after the check, Claude reads the report and puts right what can safely be put right (a link one page has and the other lacks, the line a new page is missing in the Index, a link to a page that was renamed), lists what it found and left (a claim past its date, a thing two pages say differently, a claim still marked unverified), and leaves the whole of it on one short page in plain words. Say "what did the tidy find" to hear it.

It runs within limits written down for it, never deletes, and stops after twenty changes. It needs the "Jobs that ask Claude while you are away" item, and each run uses a little of your allowance.

It also does the one tidying move that needs no judgement: the working-state file your assistant reads at the start of every conversation grows a note at every refresh, and the tidy moves the old notes into an archive page, losing nothing, so every conversation starts a little cheaper.

## The morning page

The "Your morning page" item writes you a page each morning, at half past six or at the first wake after it (ask your assistant to move the hour): what is on today, in your own terms; what moved in the last week on what you follow; what is waiting (the inbox, a job that failed); and one thing worth doing today, with its reason, if the record suggests one. It reads your daily notes, the working-state file, the last week of the log, the inbox and your jobs' own records, and nothing else. If you have the Mac apps item and a mailbox named "Wiki", anything you have sent there from your phone is saved into the wiki first. With the Alerts item, your phone is told when the page is ready, with its path. Say "morning" to hear it.

## Alerts

With the "Alerts on your phone" item, the tidy and the morning page send one line to your phone when they finish or fail, naming the file to look at and never sending it. Without it, the same line is kept in each job's own record. The Saturday check and the index refresh write to their own records instead, and Check my wiki reads those.

## Memory search's index

With the "Memory search" item, the index of your wiki's meaning refreshes in the background after every save that touched a page, and once a night at twenty to five or the next wake; only the sections that changed are read again, so an ordinary refresh takes seconds. It runs on this Mac alone and asks nothing of Claude. If the small model's program (Ollama) is not open, the refresh notes that and waits for the next one; the check-up says when an index has gone more than two weeks without one.

## What they cost

The Saturday check, the copy and the index refresh cost nothing. The tidy and the morning page each run Claude once: one run a week and one a day, which a Pro plan will notice and a Max plan will not; the item says so when it is offered, and nothing runs until you have chosen it.

## What they never do

Delete, move anything out of the wiki, rewrite history, or send anything but one line to your own phone. The tidy and the morning page wait when your laptop is on battery and low, and a failed run of either is recorded and alerted, never retried on its own. The Saturday check and the index refresh simply run again at their next time.
