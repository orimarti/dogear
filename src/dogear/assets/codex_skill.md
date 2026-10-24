---
name: dogear
description: Save the current Codex session as a dogear favourite (bookmark) so it can be listed and resumed later from any folder. Use when the user invokes $dogear or explicitly asks to dogear, bookmark or favourite this session. Not for browser bookmarks or bookmarks in code.
---

Save this session as a dogear favourite.

The user's request is whatever they typed after `$dogear`, or what they just
asked for; it may be nothing beyond "save it".

1. Check that the `dogear` command is installed: run `command -v dogear`
   (on Windows, `where dogear`).
2. If it is not installed, reply with exactly this line and stop:
   `dogear is not installed. Install it with: uv tool install dogear (or pipx install dogear)`
3. Turn the request into one `dogear add` command:
   - Already in flag form (`my-label -t work -n "note"`): use it unchanged.
   - A name or label: put it first, as one word (lowercase, hyphens instead of
     spaces, not only digits).
   - Tags: one `-t TAG` per tag. A note: `-n "TEXT"`. Launch flags: `--args "FLAGS"`.
     Quote any value with spaces.
   - Nothing given: plain `dogear add`.
   - Never add a session id unless the user gave one.

   Examples:
   - "save with name testtest" → `dogear add testtest`
   - "call it jobs, tags work and client, note: auth half done" →
     `dogear add jobs -t work -t client -n "auth half done"`
4. Run that command once with the shell tool.
5. If the output says `already saved as OLD` and the user asked for a
   different name NEW, run `dogear rename OLD NEW` once.
6. Reply with the commands' output verbatim and nothing else. If a command
   fails, show its error and stop; do not retry or run anything else.
