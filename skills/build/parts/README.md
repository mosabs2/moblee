# The standard parts

Every thing the build skill makes is laid down from these, by `scaffold.py`, so that no build invents its own server, its own job shape or its own place. The scaffold copies the ones a build needs into `apps/<name>/` with the name and title filled in, and never overwrites a file that is there.

- **`scaffold.py`** makes the folder, the parts, the README, the thing's page under `wiki/Projects/`, the `wiki/Projects.md` index if the wiki has none, and one line on `wiki/Index.md`. `--dry-run` shows what it would do. It makes nothing outside the wiki except, with `--outside`, nothing at all there: a tier-3 folder is the assistant's to set up by hand, with `git init`.
- **`server.py`** shows a page on this Mac only. What it must stay: bound to 127.0.0.1; refusing any request whose Host or Origin is not its own address; stopping when the tab closes or after half an hour unwatched; free of anything that deletes, moves or replaces a file, because the delete guard reads a script before it lets it run and would refuse the page's own server. Add routes under `/api/` for what the page needs; do not weaken the checks.
- **`moblee-app.js`** is loaded by every page: the heartbeat, the goodbye on close, `mobleeApp.load(name)` and `mobleeApp.save(name, value)` for the files in `data/`.
- **`index.html`** is the starting page: the Mac's own typeface, light and dark, nothing fetched from the internet. Build the page in it.
- **`job.py`** is the shape of anything on a schedule. `work()` is filled in; the record-keeping around it (`state/last-run.json`, `state/job-log.txt`) stays, because the check-up reads it. It appends or writes new dated files, never deletes or overwrites.
- **`launch-agent.plist`** schedules `job.py` with the Mac's own scheduler, named `com.moblee.<name>`. The owner loads it with the two lines in the README; the assistant never does.
- **`keychain.py`** keeps a secret in the Mac's Keychain. `set` asks at a prompt the owner types into and hands the secret to `security` on its standard input; `get` prints it for a script; `has` says whether one is there. Nothing secret goes on a command line, where Activity Monitor would show it, or into a file.
- **`README.template.md`**, **`record-page.md`** and **`projects-index.md`** are the words the scaffold fills in: the folder's README for the owner, the thing's page, and the index page.

The parts need only the Python and the browser the Mac already has. Anything that needs more is a tier-3 build and lives outside the wiki.
