---
name: feedback-shell-composition
description: Compose shell commands without command substitution, backticks, heredocs or leading variable assignments; those shapes trigger a permission prompt regardless of the allow list, so logic goes into a script file that is then run.
metadata:
  type: feedback
---

Write shell commands plainly. No `$(...)`, no backticks, no heredocs, no `VAR=value cmd` prefixes. Anything that needs logic goes into a file under `scripts/` (written with the file tools) and the file is run.

**Why:** Claude Code's own safety check prompts the owner on those shapes whatever the allow list says. A vault that prompts constantly trains its owner to click yes without reading, which defeats every other safeguard.

**How to apply:** compose log entries with the log appender rather than in the shell; put multi-step work in a script; pass the same rule to any subagent that will run commands.
