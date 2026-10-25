# dogear plugin for Claude Code

Adds `/dogear`, which bookmarks the Claude Code session you're in so you can
list it and resume it later from any folder. Give it a name, tags or a note in
plain words or as flags:

```text
/dogear:dogear
/dogear:dogear jobs-api -t work -n "auth half done"
/dogear:dogear save it as jobs, tag work
```

Later, from any terminal, `dogear ls` lists your saved sessions and
`dogear open jobs-api` (or `dogear` alone, to pick one) changes to the
session's folder and runs `claude --resume` for you.

## Requirements

The plugin is only the slash command. The bookmarks themselves are kept by the
`dogear` command-line tool from PyPI, which you install separately:

```sh
uv tool install dogear      # or: pipx install dogear
```

If the tool is missing, `/dogear` says so and stops.

## What it runs

The skill only runs these commands, and is limited to them by its
`allowed-tools` list: `command -v dogear` (or `where dogear` on Windows) to
check that the tool is installed, `dogear add ...` to save the session, and
`dogear rename ...` when the session was already saved under another name.

`dogear` reads Claude Code's local session files to find the current session
and stores your bookmarks in a single JSON file in its config folder
(`~/.config/dogear` by default). It never uses the network.

Full documentation, Codex support and the source:
https://github.com/orimarti/dogear (MIT licence).
