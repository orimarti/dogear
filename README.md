# dogear: bookmark and resume Claude Code & Codex sessions

> Bookmark, save and resume Claude Code and Codex sessions from any folder. A tiny session manager with names, tags and notes.

![dogear: save a session with /dogear, list it with dogear ls, resume it from any folder](https://raw.githubusercontent.com/orimarti/dogear/master/docs/demo.gif)

You have hundreds of Claude sessions and Codex sessions spread over many
folders, and a few of them matter. dogear keeps a short, named list of those —
like folding the corner of a page — and resumes any of them with one command,
from anywhere: it changes to the session's folder and runs `claude --resume` or
`codex resume` for you.

- Save the session you're in without leaving it: `/dogear` (Claude Code), `$dogear` (Codex), or `! dogear add`.
- Save any recent session from a normal terminal through a picker.
- One list for both agents, with your own names, tags and notes.
- `dogear` alone: pick a saved session, land in its folder, resumed.
- Python 3.11+, standard library only. macOS, Linux and Windows. No network access, ever.

## Install

```sh
uv tool install dogear      # or: pipx install dogear
```

Then, optionally, add the in-session command:

| Where | How | You type |
| --- | --- | --- |
| Claude Code, as a plugin | `/plugin install dogear --marketplace orimarti/dogear` (or `/plugin marketplace add orimarti/dogear` then `/plugin install dogear@dogear`) | `/dogear:dogear` |
| Claude Code, as a personal skill | `dogear setup claude` | `/dogear` |
| Codex | `dogear setup codex` | `$dogear` |

Plain words work too: `/dogear save it as todo, tag work` or just "dogear this
session as todo" — the agent turns it into the right `dogear add` flags (and
renames the favourite if the session was already saved).

Use the plugin **or** `dogear setup claude`, not both. The plugin only provides
the slash command; the `dogear` CLI still comes from PyPI (the command tells you
if it's missing).

## 30-second tour

```sh
# inside a Claude Code or Codex session
/dogear todo-app -t work            # or $dogear … in Codex, or: ! dogear add todo-app -t work

# later, from any terminal
dogear ls
#  #  LABEL      AGENT   FOLDER           TITLE           TAGS  NOTE
#  1  todo-app   claude  ~/code/todo-app  Add dark mode   work
#  2  docs-site  codex   ~/code/site      Docs refresh
dogear open todo-app                 # cd ~/code/todo-app && claude --resume <id>
dogear                               # or pick from a list (uses fzf if installed)
```

From a plain terminal, `dogear add` shows your 50 most recent sessions (both
agents) to choose from; `dogear add <session-id>` saves one directly (a unique
prefix of the id is enough).

| Command | What it does |
| --- | --- |
| `dogear add [SESSION\|LABEL] [-l LABEL] [-n NOTE] [-t TAG]... [--args FLAGS] [--agent A]` | Save a session. A word that isn't a session id (8+ hex characters) is taken as the label for the current session. Repeat `-t` (or use `-t a,b`) for several tags. Giving a label for a session that's already saved renames it. |
| `dogear ls [-t TAG] [--agent A] [--json]` | List favourites, newest first. `missing` marks sessions that no longer exist. |
| `dogear open REF [-- FLAGS]` | Resume a favourite in its folder. Flags after `--` replace its saved flags for this launch (`--` alone: no flags). |
| `dogear rename REF NEW` · `note REF TEXT` · `tag REF +a -b` · `edit REF --args FLAGS` · `rm REF ...` | Manage favourites. `REF` is a label or the number from `dogear ls`. |
| `dogear prune [--yes]` | Remove favourites whose session is gone. |
| `dogear setup claude\|codex [--force]` | Install the in-session command. |
| `dogear config [--path]` | Show the effective configuration. |

Flags that start with `-` need quoting with a space or an `=`:
`--args "--model opus"` or `--args=--verbose`.

## Configuration

Optional, at `~/.config/dogear/config.toml` (`$XDG_CONFIG_HOME/dogear`;
`%APPDATA%\dogear` on Windows; `$DOGEAR_HOME` overrides). Favourites live in
`favorites.json` next to it, so there's one folder to back up.

```toml
[claude]
command = "claude"          # e.g. "claude --dangerously-skip-permissions"

[codex]
command = "codex"           # e.g. "codex --full-auto"

[picker]
use_fzf = "auto"            # auto | always | never
```

**Shell aliases are invisible to dogear.** If you run `alias cc='claude --some-flag'`,
dogear can't see it — put the flags in `command` above instead. Per-favourite
flags (`--args`) are added after it.

## How it finds your sessions

dogear reads the agents' own files and never writes to them (the only exception
is `dogear setup`, when you ask for it). These are internal formats, not public
APIs, and may change between agent versions:

- **Claude Code**: transcripts in `~/.claude/projects/*/<id>.jsonl` (title from
  `/rename`, else the generated title, else your first prompt); running sessions
  in `~/.claude/sessions/<pid>.json`. `$CLAUDE_CONFIG_DIR` is respected.
- **Codex**: rollouts in `~/.codex/sessions/YYYY/MM/DD/rollout-*-<id>.jsonl`,
  titles in `~/.codex/session_index.jsonl`. `$CODEX_HOME` is respected.

To save "the current session", dogear walks up its parent processes to the
nearest `claude` or `codex` process and asks which session it is running. If it
can't tell for sure it refuses rather than guess, and shows the candidates. On
Windows this detection is best effort: if it fails, use `dogear add <session-id>`.

Resuming runs `claude --resume <id>` / `codex resume <id>` from the session's
folder. dogear replaces itself with the agent (on Windows it runs it and waits),
so your shell is where you left it when the agent exits.

## FAQ

### How do I resume a Claude Code session from another folder?

Save it once with `/dogear my-label` (or `dogear add` from a terminal). From
then on, `dogear open my-label` works from any directory: dogear changes to the
folder the session was started in and runs `claude --resume <id>` there.

### How do I resume a Codex session?

The same way. `$dogear my-label` inside Codex (after `dogear setup codex`), or
`dogear add` from a terminal, saves it; `dogear open my-label` runs
`codex resume <id>` in the right folder. Claude Code and Codex sessions share
one list.

### How do I save or bookmark a Claude Code session?

Inside the session, type `/dogear` with an optional name, tags or a note, in
flags or plain words: `/dogear todo-app -t work` or `/dogear save it as todo-app, tag work`.
From a terminal, `dogear add` lets you pick from your 50 most recent sessions.

### How is this different from `claude --resume` or `codex resume`?

Those pickers list every past session; dogear is the short list you chose to
keep, with names you'll remember, across both agents, and it starts each
session from the right folder. It uses the agents' own resume commands, so
nothing about the sessions themselves changes.

### Does dogear upload or modify my sessions?

No. It only reads the agents' files, never writes to them (except installing
the in-session command when you run `dogear setup`), and makes no network
requests.

## Development

```sh
uv sync
uv run pytest
```

Tests use synthetic fixtures only; they never read your real `~/.claude` or `~/.codex`.

## License

MIT
