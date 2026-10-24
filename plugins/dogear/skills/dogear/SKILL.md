---
name: dogear
description: Save the current Claude Code session as a dogear favourite (bookmark) so it can be listed and resumed later from any folder. Use when the user runs /dogear or explicitly asks to dogear, bookmark or favourite this session. Not for browser bookmarks or bookmarks in code.
argument-hint: "[name] [tags, note, launch flags — plain words are fine]"
allowed-tools: Bash(command -v dogear), Bash(where dogear), Bash(dogear add *), Bash(dogear rename *)
---

Save this session as a dogear favourite.

The user's request: $ARGUMENTS
(If that is empty, use what the user just asked for; it may be nothing beyond "save it".)

1. Check that the `dogear` command is installed: run `command -v dogear`
   (on Windows, `where dogear`).
2. If it is not installed, reply with exactly this line and stop:
   `dogear is not installed. Install it with: uv tool install dogear (or pipx install dogear)`
3. Turn the request into one `dogear add` command:
   - Already in flag form (`my-label -t work -n "note"`): use it unchanged.
   - A name or label: put it first, as one word (lowercase, hyphens instead of
     spaces, not only digits).
   - Tags: `-t TAG ...`. A note: `-n "TEXT"`. Launch flags such as a model:
     `--args "FLAGS"`. Quote any value with spaces.
   - Nothing given: plain `dogear add`.
   - Never add a session id unless the user gave one.

   Examples:
   - "save with name testtest" → `dogear add testtest`
   - "call it jobs, tags work and client, note: auth half done" →
     `dogear add jobs -t work client -n "auth half done"`
   - "bookmark this with opus" → `dogear add --args "--model opus"`
4. Run that command once with the shell tool.
5. If the output says `already saved as OLD` and the user asked for a
   different name NEW, run `dogear rename OLD NEW` once.
6. Reply with the commands' output verbatim and nothing else. If a command
   fails, show its error and stop; do not retry or run anything else.
