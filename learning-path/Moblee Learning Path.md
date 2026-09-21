---
type: Learning path
status: active
started:
lessons: 32
---

# Moblee Learning Path

Thirty-two short lessons, one an evening, on how to get the most out of this wiki and the assistant that keeps it. They distil what has proved useful in running this system day to day: the habits that matter, the tools that earn their place, and the mistakes worth skipping. Each lesson is a few sentences, the exact words to say, and one thing to try that evening. The order is deliberate. Foundations come first, then the housekeeping that keeps a wiki from turning into a dump, then the thinking tools, then the things that produce something you can show, and last the habits that hold it all together.

**How it works.** If you chose the evening reminder, a notification names the next lesson each evening at the time you chose (nine unless you set another). Whenever you are ready, open your assistant in the vault and say **"lesson"** (or "lesson 7" for a particular one). Your assistant gives the lesson in its own words, tied to what you have actually been doing, does the evening's step with you if you want, and records it in the Progress section at the bottom. If you have been away, say "orient" first. Skip an evening and the same lesson waits for you; nothing is lost by missing a night.

---

## Week one: the foundations

## Lesson 1: Start every session with one word

The wiki keeps its own working state in a few files that your assistant reads and you never need to open. Saying **orient** makes it read them and tell you where things stand: the date, what is active, anything waiting on you, and what is sitting in the inbox. Every other habit rests on this one, because it means you never have to carry the state in your head. Say it first thing each morning, and again after any gap of more than a few hours.

**Say:** "orient"

**This evening:** say it, read the answer, and notice what it already knows about your week.

## Lesson 2: Feed it, and let it do the filing

The wiki gets better in proportion to what you give it. Anything you read and care about goes into the `raw/` folder (PDFs, screenshots, exports, notes) or is clipped from the web with the Obsidian Web Clipper into `Clippings/`. Then you say ingest. Your assistant reads the source, updates every page it touches (a single article often touches five or ten), writes a dated log entry, moves the file to `processed/` and commits. You never file anything by hand. The first few sources feel thin. The value arrives when the tenth connects to the nine before it.

**Say:** "ingest the new files in raw"

**This evening:** drop three things you have read this month into `raw/` and ingest them.

## Lesson 3: Ask it, then keep the good answers

The most ordinary use of the wiki is asking it questions. What do I know about X? What have I said about Y before? What do these three sources have in common? Every answer cites the pages it drew on. When an answer is worth keeping, say "save this" and your assistant stages it for the wiki, so the thinking builds up over time instead of vanishing with the chat.

**Say:** "what do I know about [a subject]?" then, if the answer is good, "save this"

**This evening:** ask one question you would normally ask a friend, and save the answer if it deserves it.

## Lesson 4: Your own thoughts are the best pages

In a vault like this, the most valuable pages are rarely articles. They are your own views, your own accounts of things, your own reasoning. When you say something in conversation that you would want to find again in a year, say so. Your assistant captures it in your words and leaves them unpolished. This is how the wiki becomes yours rather than a library of other people's writing.

**Say:** "I think ... [your view]. Save this."

**This evening:** tell your assistant one thing you believe about your work, your studies or a habit you are building, and save it.

## Lesson 5: Open and close the day

Two words run the daily rhythm. **"today"** in the morning creates the day's note and gives you a brief: your plan, what is scheduled, which threads moved, what to watch. **"close the day"** in the evening writes a short reflection to the log, marks the day closed, and seeds tomorrow's plan with whatever carried over. Neither takes more than a minute. Say today before close the day, because today is the one that creates the note. After two weeks of both, the vault tracks what you are actually doing as well as what you have read.

**Say:** "today" in the morning; "close the day" in the evening

**This evening:** say "today" now, so the note exists, then "close the day". Tomorrow morning, say today.

## Lesson 6: Plan ahead with it

Once the daily notes exist, your assistant can plan into them. "Plan the week" lays out the coming days against what is active; "plan before [date]" works back from a deadline. It always proposes before it writes, so you can change the plan first. This is where a project, an exam timetable or a trip gets turned into days.

**Say:** "plan the week" or "plan before my exam on the 30th"

**This evening:** plan tomorrow.

## Lesson 7: Tell it what to hold you to

Your vault has a file, `Identity.md`, that says who your assistant is to you: verify rather than guess, challenge rather than flatter, never delete. One list in it starts empty and belongs to you. It holds the things you want your assistant to keep you honest about over time. It raises them, sparingly, for as long as they stay on the list.

**Say:** "read wiki/Identity.md, then ask me what I want to be held to, and write my answers under the list for that"

**This evening:** give it two things. You can add more at any time by saying "add this to how you work with me".

---

## Week two: housekeeping, and why the wiki stays organised

## Lesson 8: The five files you never open

Five files run the place. `CLAUDE.md` holds the rules (ChatGPT reads them as `AGENTS.md`; where the vault has both names, one is the real file and the other is a link to it). `wiki/_context.md` is the working state: active threads, open decisions, a watch list. `wiki/log.md` is the diary, with one dated entry per thing done and nothing ever rewritten. `wiki/Index.md` is the catalogue, one line per page. You met `wiki/Identity.md` in lesson 7. Your assistant reads them at the start of every session and writes them as it works. Rather than opening them, you ask about them: "what changed yesterday?", "what's on my watch list?", "what are my open decisions?".

Your assistant also keeps standing notes on how you work. **With Claude:** they sit in a memory folder under `~/.claude`, outside the vault. **With ChatGPT:** they sit on a wiki page, `wiki/Wiki Operations/Assistant Memory.md`.

**Say:** "what changed in the wiki this week?"

**This evening:** ask that, and then ask "what's on my watch list?"

## Lesson 9: The Saturday health check

If you installed the weekly schedule, the vault checks its own structure every Saturday morning (as long as the Mac is awake and you are logged in) and writes a report: links that go nowhere, pages nothing links to, log entries in the wrong form, files growing past their size limits. It runs on its own. A deeper check, for contradictions between pages and for claims a newer source has overtaken, runs when you ask for it, and is worth asking for once a month. The habit is to act on both. At your first session after Saturday, ask what the check found and let your assistant fix what it can.

**Say:** "what did the health check find? fix what you can and tell me what needs me"; monthly, "lint the wiki"

**This evening:** ask when it last ran and what it found.

## Lesson 10: Compacting, when the vault gets heavy

The state files are read in full at every session start, so they are kept light. When the health check says one is over its limit, or your assistant mentions the vault is getting heavy, say compact. It moves finished history out of the working files into an archive page behind one-line pointers, and asks before dropping or moving anything you might want. Nothing leaves the vault. This is how the wiki avoids becoming a heap of repeated information: its weight is measured every week and trimmed when you ask.

**Say:** "compact the wiki"

**This evening:** ask "is anything over its size limit?" and compact if so.

## Lesson 11: Git is your undo

Every version your assistant commits is kept by git, and it commits at the end of each piece of work. You never type git commands. **With Claude:** routine commits happen without asking. **With ChatGPT:** you are asked to approve each commit, and that is expected. You can always ask what changed on a given day, and you can ask the question that matters most: "how did my Projects page look on the 10th?" Your assistant shows you the earlier version and, if you want it back, copies the section into the current page with its editing tool. It restores by copying and never by rewinding, so nothing else changes. Regret is recoverable for anything that was committed, which is why the never-delete rule can be absolute. With ChatGPT, approve the commit when asked: work that is not committed has no earlier version.

**Say:** "show me the last ten changes" or "how did my [page] look a week ago?"

**This evening:** ask for the last ten changes and read them.

## Lesson 12: Nothing gets deleted, and how to tidy anyway

Your assistant cannot delete in your vault. A guard refuses the command before it runs, in the forms it knows, including indirect ones, and nothing you say to your assistant overrides it. A message beginning "Blocked by the vault safety gate" means the guard is working as intended. Tidying happens by moving: finished material goes to `processed/` or an `archive/` folder. If you really want something gone, your assistant names it and says where it is, and you remove it yourself in Finder.

**With Claude:** this holds as written.

**With ChatGPT:** this holds once you have trusted the guard and proved it. ChatGPT skips a new or changed guard until you have reviewed it, and nothing on screen says so. There are five steps:

First open your wiki folder in ChatGPT (File menu, Open Folder). Until a folder has been opened in ChatGPT, its Hooks page is empty and does not say why. <!-- verify on testdev -->

1. Open the ChatGPT menu and choose Settings.
2. Choose Hooks, under the heading Coding.
3. Open "User config".
4. Press Trust beside the hook that ends `bash-guard.py`.
5. Turn its switch on.

If ChatGPT is open, quit it and open it again afterwards, so that it reads the whole rules file. You must do this again after any Moblee update that changes the guard. ChatGPT will not remind you. To prove the guard is live, run `python3 scripts/moblee-doctor.py --prove-guard` in Terminal, in the folder where you downloaded Moblee. In the Moblee app, press Prove the guard on the home screen. The proof uses a little of your ChatGPT allowance. OpenAI describes hooks as a guardrail and not a complete boundary, and a guard that crashes or takes too long lets the command through. ChatGPT's own sandbox is a second layer: by default the assistant does not write outside the wiki folder and the Mac's temporary folders without asking you. The sandbox does not stop a deletion inside the wiki; the guard does.

**Say:** "propose what could be archived, and move it if I agree"

**This evening:** ask that, and see what it suggests. With ChatGPT, do the Trust step first.

## Lesson 13: Permission prompts, and when to say yes

**With Claude:** Claude Code asks before running commands it has not already been allowed to run. The installer gave your vault a list of routine work it may do without asking (reading, searching, editing inside the vault, committing) and a list it may never do (deleting, rewriting history). Anything else still prompts, and the prompts you see should be for unusual commands. If the same safe command keeps prompting, tell Claude. It will add the command to the allowed list if it can; if it cannot (Claude Code sometimes declines to change its own settings), it will give you one line to paste into Terminal. Never approve anything that mentions deleting. The guard catches the command forms it knows about, but your own reading of the prompt is the real protection.

**With ChatGPT:** Moblee does not set this up for ChatGPT yet. ChatGPT asks you to approve each commit, and that is expected.

**Say:** "the command you just ran keeps asking permission; if it is safe, add it to the allow list or give me the line to paste"

**This evening:** nothing to do unless a prompt appears; then use the sentence above.

## Lesson 14: Keeping it organised as it grows

Keeping the wiki in clear sections and subsections is your assistant's job, and it has rules for it. One page per subject. Synthesis on the main page, with detail in dated notes underneath once a subject has three or four sources (a "cluster"). The Saturday check catches orphan pages and broken links, and the monthly lint catches contradictions and repetition. Your part is to ask. "Is anything duplicated?" "Should my reading notes on this subject become their own cluster?" "Does this page need splitting?" Avoid reorganising or renaming files by hand; tell your assistant what looks wrong and let it fix the structure, so the links stay whole.

**Say:** "is anything in the wiki duplicated or in the wrong place?"

**This evening:** ask that.

---

## Week three: thinking with it (the brain patterns)

## Lesson 15: Trace how your thinking has moved

The wiki remembers what you thought and when. "Trace" follows one idea through every page and log entry that touched it and shows how it changed. Ask it about anything you have written about more than twice: your work, a plan, a habit, a view on money. The answer often surprises, because you remember your current view and forget the path that led there.

**Say:** "trace how my thinking on [a subject] has changed"

**This evening:** trace one subject you have written about since the vault began.

## Lesson 16: Connect two things that do not obviously touch

"Connect" looks for bridges between two subjects the wiki holds separately. Sleep and study. Faith and finances. A hobby and your career. It finds the pages where they meet and says what the meeting implies. This pattern is the payoff for keeping everything in one vault instead of several.

**Say:** "connect [one subject] and [another]", for example "connect my sleep notes and my work"

**This evening:** connect two subjects you would never have put in one sentence.

## Lesson 17: What is quietly emerging

"Emerge" asks what the vault implies that nothing in it states: a theme building across recent sources, a concern that keeps appearing under different names, a decision forming before you have named it. It works best after a few weeks of ingesting. Ask it monthly.

**Say:** "what is quietly emerging in my wiki?"

**This evening:** ask, and save the answer if it names something real.

## Lesson 18: Challenge your own view

The whole system is built around this one. An assistant that only agrees with you is a diary, however clever. "Challenge my view that X" makes your assistant argue the other side from your own record: where you contradicted yourself, what a source you saved says against you, what you have not considered. Your identity file already tells it to challenge rather than flatter; this is how you invoke it on purpose.

**Say:** "challenge my view that [something you believe]"

**This evening:** pick a view you hold firmly and let it push.

## Lesson 19: What should I work on next

"Ideas" reads your active threads, your inbox and your watch list and proposes what deserves attention, judged against what you have said matters. It is good on a Sunday evening, or whenever the week feels shapeless.

**Say:** "what should I work on next?"

**This evening:** ask, and put one answer into tomorrow's plan.

## Lesson 20: Place a new source against what you already know

When something new arrives, an article or a paper, "synthesise" reads it against the whole vault before it is ingested: what it confirms, what it contradicts, what it adds. Use it on anything that might change your mind, so the ingest carries the argument as well as the summary.

**Say:** "synthesise this article against my wiki" (with the file in `raw/`)

**This evening:** clip one article and synthesise it before ingesting it.

## Lesson 21: Move things between active, open and watching

The context file holds three tiers: active threads, open decisions and a watch list. "Graduate" moves items between them. Promote a subject to active when it is live, close a decision once it is made, put something on the watch list when it is waiting on a date. Every move is logged with a reason. Ask for the tiers first, then move things until they match your life.

**Say:** "what's active, what's open and what am I watching?" then "promote X to active" or "close the Y decision"

**This evening:** make the tiers match the truth.

---

## Week four: things you can show

## Lesson 22: See the shape of it

"Galaxy" rebuilds a 3D map of every page and every link and opens it in your browser. Folders become colours, and pages nothing links to float alone. It is the fastest way to see what has grown and what has been left orphaned. Take a look every month or so.

**Say:** "galaxy"

**This evening:** open it and find one page that is floating on its own.

## Lesson 23: The dashboard

The dashboard is a local web page for the vault: orientation state, inbox counts, an ask box, a galaxy button, and a visuals tab of charts. The charts are defined in a small file your assistant edits for you, so a new chart takes one sentence. Any CSV file you keep in the vault can feed a chart, for example a fitness tracker export or a spending log. **With Claude:** the ask box runs Claude against the wiki. **With ChatGPT:** Moblee does not set this up for ChatGPT yet.

**Say:** in Terminal, in the vault folder, `python3 dashboard/server.py`, then open http://127.0.0.1:7373; to your assistant, "add a chart of [a CSV file in my vault] to the dashboard"

**This evening:** start it, look around, and ask for one chart.

## Lesson 24: Your brand, and PDFs of any page

"Design my brand" is a five-minute interview (colours, a typeface, a monogram) that sets how PDFs of your pages look. After it, "PDF up [page]" or "render my [page] as a PDF" produces something you would happily send to a colleague or a friend. PDF rendering needs some extra software on your Mac first (Homebrew and a few libraries). Your assistant cannot install that itself. It gives you one line to paste into Terminal, Terminal asks for your Mac password, and when it finishes you say "carry on". Do the brand tonight, and ask for the setup the first time you want a PDF.

**Say:** "design my brand" once; later, "give me the Terminal line to set up PDF rendering" and then "PDF up [page]"

**This evening:** design the brand.

## Lesson 25: Let it interview you

Some pages cannot be built from sources, because you are the source: a person you know, how a friendship started, why you chose your career, what a teacher taught you. "Interview me on X" runs a structured interview, checks names against the wiki, flags anything that contradicts what the vault already says, and writes the page in your words.

**Say:** "interview me on [a person, a decision or a project]"

**This evening:** give it fifteen minutes on one subject only you can speak to.

## Lesson 26: The inbox

Plenty worth keeping happens outside a session with your assistant. A screenshot on your phone, an article someone sends you, a thought in the car: all of it reaches the wiki the same way, by landing in the `raw/` folder and being ingested the next time you say the word. From your phone, send it to yourself and drop it into `raw/` when you are back at the Mac. In a conversation with your assistant, "capture this" writes a proper note into `raw/` for you. Your assistant's own tools (an interview, a day close, a plan) write to the wiki directly, and that is fine. What never happens is you filing things by hand, and that is why the wiki stays clean.

**Say:** "capture this" during a conversation with your assistant; "ingest the new files in raw" after dropping things in

**This evening:** find one thing on your phone worth keeping, get it into `raw/`, and ingest it.

## Lesson 27: The voice

**With Claude:** if you installed the optional voice stack, replies are read aloud, and when Claude Code runs in Terminal it also nudges you audibly while it is waiting on you. The controls are one word each in Terminal: `voice off` for a quiet session, `voice on` to bring it back, `voice full` to hear the last reply in full, `voice stop` to interrupt, `voice status` to check. If you skipped it at install, `python3 voice/install-voice.py` from the Moblee download adds it later.

**With ChatGPT:** Moblee does not set this up for ChatGPT yet.

**Say:** `voice status` in Terminal

**This evening:** try `voice full` after a long answer.

## Lesson 28: Speak in someone's voice, carefully

Once the wiki documents a person in depth (a thinker you have read at length, a mentor your assistant has interviewed you about), "what would X say about Y" answers in a reconstruction of their voice. It is always labelled as a reconstruction and never presented as their words. Use it to think with, and never quote it as theirs. On someone the vault knows only thinly, it will say so and hedge, which is the right answer.

**Say:** "what would [a well-documented person] say about [a question]?"

**This evening:** try it on whoever your vault knows best, and notice how it labels the answer.

---

## Week five: the habits that hold it together

## Lesson 29: Dates, sources and honesty

A few rules keep the wiki trustworthy. They are your assistant's to keep, but you should know them. Dates are always absolute ("14 April 2026", never "last week"). Every ingested fact carries its source on the page. Anything your assistant is unsure of is marked `[Unverified]` instead of being smoothed over, and gaps are left blank rather than filled with guesses. When you append your own notes to the end of a clipped article, your assistant reads them as yours and treats them as the point. Ask it to mark uncertainty rather than guess; the rule is already in its identity file, but saying it once helps.

**Say:** "is there anything in my wiki marked unverified that I could settle?"

**This evening:** ask that.

## Lesson 30: The rhythm, on one line

Daily: today in the morning, close the day at night. Weekly: the Saturday check, acted on at your next session, and a plan for the week on Sunday. Monthly: the full written lint (weekly if you can manage it), galaxy, emerge, and compact if asked. Yearly: sit down with your assistant and ask how the two of you are working together and what should change.

**Say:** "plan the week, and put the Saturday check and the Sunday plan in it"

**This evening:** ask that.

## Lesson 31: Ask for challenge, and change the rules when they chafe

The failure to guard against is an assistant that flatters a caricature of you back at you. The cure is written into your identity file, and it works only if you use it. Ask to be challenged, say so when it is agreeing too easily, and tell it plainly when something annoys you. Your identity file is yours, and "add this to how you work with me" changes it. A wiki that never gets adjusted is one you will stop using.

**Say:** "you are agreeing with me too easily; push back" and, whenever something grates, "add this to how you work with me: ..."

**This evening:** give it one rule of your own.

## Lesson 32: When stuck, where to turn

This is the last lesson. From here, your assistant keeps coaching at every orient, and the Saturday check runs itself if the schedule is installed. When something breaks or puzzles you, describe it to your assistant first; it can read the vault's own rules and the logs, and it will tell you plainly if a fix needs you. The documentation that came with Moblee (the `docs/` folder in the download) covers installing, updating and the safety guard in more depth. Committed work can always be brought back: the guard, the commit gate and git see to that. With ChatGPT, the guard counts once it is trusted and proved (lesson 12).

**Say:** "something is not working: [describe what you saw]"

**This evening:** say "close the day", and keep going.

---

## Progress

Delivered lessons are recorded here by your assistant, one per line below this paragraph, newest last, in the form `- N, YYYY-MM-DD`.
