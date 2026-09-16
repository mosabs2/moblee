# The weekly schedule

This folder holds the pieces that run the structural health check on a timer, so the vault gets looked over once a week without anyone remembering to ask.

**What runs.** Every Saturday at 09:04, the Mac runs `scripts/lint-v2.py` inside the vault and writes a report to `outputs/lint/lint-v2-<date>.md` (for example `lint-v2-2026-10-03.md`). The checks are mechanical: log headers stamped correctly, links that point at pages which do not exist, pages nobody links to, files growing past their size caps, and so on. Nothing in the vault is changed; the report is the only thing written. There are no network calls and no commit.

**If the Mac is asleep** at 09:04, macOS runs the job when it next wakes, as long as you are logged in. If the Mac is shut down or you are logged out for the whole of Saturday, that week's run is skipped and the next one happens the following Saturday; nothing is lost, the check simply runs a week later. If the report for that day already exists (because you asked Claude to run the lint by hand, say), the scheduled run notices and does nothing.

**Installing it.** From the Moblee package folder, run `bash scripts/install-schedule.sh`. It copies `run-weekly-lint.sh` to `~/.config/moblee/`, writes the schedule to `~/Library/LaunchAgents/com.moblee.weekly-lint.plist`, and switches it on. Running the installer again is safe; it replaces what is there.

**Checking it ran.** Each run leaves a short log at `~/.config/moblee/logs/weekly-lint-<date>.log`. The last line says either where the report was written, that today's report already existed, or why the run failed in plain words. Logs older than 90 days are moved into `~/.config/moblee/logs/archive/`, never deleted. The easiest way to check is to ask Claude: "did the weekly lint run, and what did it find?" It can read the log folder and the newest report.

**Running it now.** `bash ~/.config/moblee/run-weekly-lint.sh` runs exactly what the schedule would run.

**Switching it off.** `launchctl bootout gui/$(id -u)/com.moblee.weekly-lint` stops the schedule; the files stay in place so it can be switched back on with the installer.

**Files here.** `run-weekly-lint.sh` is the job itself. `com.moblee.weekly-lint.plist.template` is the schedule, with `__HOME__` standing in for the home folder until the installer fills it in.
