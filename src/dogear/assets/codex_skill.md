---
name: dogear
description: Save the current Codex session as a dogear favourite. Use only when the user explicitly invokes $dogear.
---

Save this session as a dogear favourite.

The arguments are whatever the user typed after `$dogear` (for example
`$dogear my-label -t work`); there may be none.

1. Check that the `dogear` command is installed: run `command -v dogear`
   (on Windows, `where dogear`).
2. If it is not installed, reply with exactly this line and stop:
   `dogear is not installed. Install it with: uv tool install dogear (or pipx install dogear)`
3. Otherwise run `dogear add` once with the shell tool, followed by the
   user's arguments unchanged, e.g. `dogear add my-label -t work`.
4. Reply with the command's output verbatim and nothing else. Do not retry,
   explain, or run any other command.
