---
name: dogear
description: Save the current Claude Code session as a dogear favourite. Only when the user runs /dogear.
argument-hint: "[label] [-n note] [-t tag ...] [--args flags]"
disable-model-invocation: true
allowed-tools: Bash(command -v dogear), Bash(where dogear), Bash(dogear add *)
---

Save this session as a dogear favourite.

1. Check that the `dogear` command is installed: run `command -v dogear`
   (on Windows, `where dogear`).
2. If it is not installed, reply with exactly this line and stop:
   `dogear is not installed. Install it with: uv tool install dogear (or pipx install dogear)`
3. Otherwise run this once with the shell tool, passing the arguments unchanged:

   dogear add $ARGUMENTS

4. Reply with the command's output verbatim and nothing else. Do not retry,
   explain, or run any other command.
