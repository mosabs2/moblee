# Tools and Connections

What the assistant can reach beyond the vault's own files, and the rules governing each. The short form is in `CLAUDE.md` under "Tools"; the binding sentence there is that nothing is ever sent, posted, bought, deleted or scheduled without the owner's explicit yes for that one action. This page is the detail, read when a tool is actually needed.

Where a capability is set up for Claude but not yet for ChatGPT, this page says so.

## Reading the vault's own material

Web Clippings arrive with YAML frontmatter; preserve the source URL, author and date when citing. PDFs and images sitting in `raw/` can be read directly.

## The dashboard

`dashboard/` in the Moblee install is a local web view of the vault: orientation state, an Ask box, and a Visuals tab whose charts are driven by `dashboard/dashboard-charts.json`. When the owner asks for "a chart of X on my dashboard", edit that config file; the schema is in `dashboard/README.md`.

**With Claude:** the Ask box runs Claude against the vault.

## The galaxy

`scripts/wiki-galaxy/build.py` renders the vault as an offline 3D knowledge graph into `outputs/galaxy/`. Rebuild before opening, so the view reflects the current state rather than the last build.

## The voice stack

Optional, at `voice/` in the Moblee install. It reads replies aloud through a Stop hook and nudges audibly when input is needed. `voice off` mutes it; `voice full` reads the latest reply in full. **With Claude** only; Moblee does not set this up for ChatGPT yet.

## Connected accounts

**With Claude**, through the Moblee checklist (`python3 scripts/moblee-setup.py`, run from the Moblee folder), the assistant may be connected to the owner's Mac apps (Calendar, Reminders, Mail and Notes, through Orchard), Gmail, Google Calendar, Google Drive, GitHub, and Chrome, which carries the owner's logged-in X, Instagram and YouTube. **With ChatGPT:** Moblee does not set these up yet.

The rules are the same for every one of them:

- A connected account is read only when the owner's request needs it. The assistant never sweeps an inbox or a feed unprompted.
- It never sends an email. It never creates, accepts, changes or deletes a calendar event or a reminder. It never moves or trashes a file through a connection. It never posts, likes, follows, comments, messages or buys on any site.
- The one exception to all of the above is the owner's explicit yes, for that one action, given in the same conversation.
- **Drafts are the default.** The assistant writes the email or the post; the owner sends it.
- Anything that spends money or paid credits, such as a generation service, is asked about first, every time.
- Nothing read from an account goes into `wiki/` unless the owner asks for it to be recorded.

**Connect, don't upload.** When the owner hands over an export by hand (a calendar `.ics` file, a screenshot of an email, a copied web page) and a connection could read the same thing live, use the connection and say so, once, so the habit changes. If the connection is not set up, say which checklist item adds it.

## Tools that come with the checklist

**With Claude:** videos on YouTube, Instagram, TikTok and X are read with the `watch` tool (`/watch <link>`). X posts are captured with the `x-capture` skill through Chrome. Editing is done by the `film`, `audio` and `pictures` skills, always on copies and never on the originals.

`python3 scripts/moblee-setup.py --check`, run from the Moblee folder, tests every connection and tool and says in plain words what is not working.

**With ChatGPT:** Moblee does not set these up yet. The checklist knows which assistant the owner chose and offers only what applies to it.

## The checklist itself is the owner's to run

The assistant never runs the installer, the updater or the checklist. The read-only `--check` and `--list` are the exceptions. It never edits `~/.claude/settings.json` (ChatGPT: `~/.codex/hooks.json` or `~/.codex/config.toml`), because those are the assistant's own settings and changing them is the owner's decision.

When something should be added, the assistant states the reason, which must be a reason the owner gave or something the vault shows, and hands over the Terminal command:

```
python3 scripts/moblee-setup.py --tick <items>
```

`wiki/Wiki Operations/Habits and Tools.md` records how the owner works and which optional items are installed and why. The `companion` skill fills it in.

## The check-up

`python3 scripts/moblee-doctor.py`, run from the Moblee folder, is the read-only health check. It changes nothing. It reports on the install, the guard, the skills, the scheduled job, and it sweeps the vault for secrets that should not be there, naming the file and the kind of secret but never the secret itself.

`python3 scripts/moblee-doctor.py --prove-guard` shows whether the delete guard is actually live. This matters most for ChatGPT, where the guard is skipped silently until the owner has trusted it in ChatGPT's settings.
