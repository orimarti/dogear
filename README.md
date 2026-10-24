# dogear

> Dog-ear your Claude Code and Codex sessions: favorite, list and resume them from any folder.

You have hundreds of agent conversations spread over many folders, and a few of
them matter. dogear keeps a short list of those — like folding the corner of a
page — and reopens any of them with one command, from anywhere.

- Save the session you're in without leaving it: `/dogear` (Claude Code), `$dogear` (Codex), or `! dogear add`.
- Save any recent session from a normal terminal through a picker.
- `dogear` alone: pick a favourite, land in its folder, resumed.
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

Plain words work too: `/dogear save it as jobs, tag work` or just "dogear this
session as jobs" — the agent turns it into the right `dogear add` flags (and
renames the favourite if the session was already saved).

Use the plugin **or** `dogear setup claude`, not both. The plugin only provides
the slash command; the `dogear` CLI still comes from PyPI (the command tells you
if it's missing).

## 30-second tour

```sh
# inside a Claude Code or Codex session
/dogear jobs-api -t work            # or $dogear … in Codex, or: ! dogear add jobs-api -t work

# later, from any terminal
dogear ls
#  #  LABEL       AGENT   FOLDER          TITLE           TAGS  NOTE
#  1  jobs-api    claude  ~/code/jobs     New jobs api    work
#  2  docs-site   codex   ~/code/site     Docs refresh
dogear open jobs-api                 # cd ~/code/jobs && claude --resume <id>
dogear                               # or pick from a list (uses fzf if installed)
```

From a plain terminal, `dogear add` shows your 50 most recent sessions (both
agents) to choose from; `dogear add <session-id>` saves one directly (a unique
prefix of the id is enough).

| Command | What it does |
| --- | --- |
| `dogear add [SESSION\|LABEL] [-l LABEL] [-n NOTE] [-t TAG ...] [--args FLAGS] [--agent A]` | Save a session. A word that isn't a session id (8+ hex characters) is taken as the label for the current session. |
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

## Development

```sh
uv sync
uv run pytest
```

Tests use synthetic fixtures only; they never read your real `~/.claude` or `~/.codex`.

## License

MIT
