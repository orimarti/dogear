"""Command-line entry point."""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, TextIO

from dogear import __version__
from dogear.agents import Session, find_sessions, get_adapters
from dogear.config import AGENTS, Config, load_config
from dogear.detect import DetectionError, detect_current
from dogear.errors import DogearError
from dogear.favorites import default_label, find_by_session, new_favorite, ordered, resolve, unique_label, validate_label
from dogear.paths import config_path, favorites_path
from dogear.launch import build_command, display
from dogear.picker import pick
from dogear.proctree import default_table
from dogear.render import format_table
from dogear.setup_cmd import claude_plugin_installed, install_claude, install_codex
from dogear.store import load, transaction


def _run_fzf(args: list[str], text: str) -> tuple[int, str]:
    r = subprocess.run(args, input=text, stdout=subprocess.PIPE, text=True)
    return r.returncode, r.stdout


def _launch(cmd: list[str], cwd: str) -> int:
    from dogear.launch import launch

    return launch(cmd, cwd)


@dataclass
class Context:
    """Everything a command touches outside the filesystem stores, injectable for tests."""

    stdin: TextIO = field(default_factory=lambda: sys.stdin)
    stdout: TextIO = field(default_factory=lambda: sys.stdout)
    stderr: TextIO = field(default_factory=lambda: sys.stderr)
    exec_fn: Callable[[list[str], str], int] = _launch
    proc_table: Any = None
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc)
    stdin_isatty: bool = False
    stdout_isatty: bool = False
    which: Callable[[str], str | None] = shutil.which
    run_fzf: Callable[[list[str], str], tuple[int, str]] = _run_fzf
    pid: int = field(default_factory=os.getpid)

    @classmethod
    def from_env(cls) -> "Context":
        return cls(
            stdin_isatty=sys.stdin.isatty(),
            stdout_isatty=sys.stdout.isatty(),
        )

    @classmethod
    def for_test(cls, stdin: str = "", **overrides: Any) -> "Context":
        calls: list[tuple[list[str], str]] = []

        def record(cmd: list[str], cwd: str) -> int:
            calls.append((cmd, cwd))
            return 0

        ctx = cls(
            stdin=io.StringIO(stdin),
            stdout=io.StringIO(),
            stderr=io.StringIO(),
            exec_fn=record,
            now=lambda: datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
            which=lambda name: f"/fake/bin/{name}",
            run_fzf=lambda args, text: (130, ""),
            pid=os.getpid(),
        )
        ctx.exec_calls = calls  # type: ignore[attr-defined]
        for k, v in overrides.items():
            setattr(ctx, k, v)
        return ctx


SESSION_TOKEN = re.compile(r"^[0-9a-fA-F-]{8,}$")
RECENT_LIMIT = 50


# helpers --------------------------------------------------------------------


def _short_path(path: str) -> str:
    home = str(Path.home())
    if path == home:
        return "~"
    if path.startswith(home + os.sep):
        return "~" + path[len(home) :]
    return path


def _session_row(s: Session) -> str:
    when = datetime.fromtimestamp(s.mtime).strftime("%Y-%m-%d %H:%M") if s.mtime else "?"
    return f"{s.agent:<6}  {when}  {s.title[:50]:<50}  {_short_path(s.cwd)}"


def _norm_tags(tags: list[str] | None) -> list[str]:
    out: list[str] = []
    for t in tags or []:
        t = t.strip()
        if t and t not in out:
            out.append(t)
    return out


def _lookup(token: str, agent: str | None) -> Session:
    found = find_sessions(token, agent)
    if not found:
        where = f"{agent} " if agent else ""
        raise DogearError(f"no session matches '{token}' in the {where}session stores")
    if len(found) > 1:
        lines = "\n".join(f"  {s.agent:<6}  {s.session_id}  {s.title}" for s in found)
        raise DogearError(f"'{token}' matches {len(found)} sessions:\n{lines}\nuse a longer id or --agent")
    return found[0]


def _pick_session(ctx: Context, cfg: Config, sessions: list[Session], prompt: str) -> Session:
    i = pick([_session_row(s) for s in sessions], ctx=ctx, use_fzf=cfg.use_fzf, prompt=prompt)
    if i is None:
        raise DogearError("nothing chosen")
    return sessions[i]


def _recent_sessions() -> list[Session]:
    sessions = [s for a in get_adapters().values() for s in a.recent(RECENT_LIMIT)]
    return sorted(sessions, key=lambda s: s.mtime, reverse=True)[:RECENT_LIMIT]


def _current_or_pick(ctx: Context, cfg: Config) -> Session:
    table = ctx.proc_table or default_table()
    no_tty = "run dogear add <session-id> (find ids with claude --resume or codex resume)"
    try:
        current = detect_current(get_adapters(), table, ctx.pid)
    except DetectionError as e:
        if not ctx.stdin_isatty:
            raise
        print(f"dogear: could not tell which {e.agent} session this is; pick one", file=ctx.stderr)
        return _pick_session(ctx, cfg, e.candidates or _recent_sessions(), "session")
    if current:
        return current
    if not ctx.stdin_isatty:
        raise DogearError("not inside a Claude Code or Codex session and no TTY for a picker; " + no_tty)
    sessions = _recent_sessions()
    if not sessions:
        raise DogearError("no Claude Code or Codex sessions found")
    return _pick_session(ctx, cfg, sessions, "session")


# commands -------------------------------------------------------------------


def cmd_add(args: argparse.Namespace, ctx: Context) -> int:
    cfg = load_config()
    label = args.label
    token = args.session
    if token and SESSION_TOKEN.match(token):
        session = _lookup(token, args.agent)
    else:
        if token:
            if label:
                raise DogearError(f"got both a label '{token}' and -l {label}; give one")
            label = token
        session = _current_or_pick(ctx, cfg)
    if label is not None:
        validate_label(label)
    tags = _norm_tags(args.tags)
    with transaction(favorites_path()) as data:
        favs = data["favorites"]
        existing = find_by_session(favs, session.agent, session.session_id)
        if existing:
            changed = []
            if args.note is not None:
                existing["note"] = args.note
                changed.append("note")
            if args.tags is not None:
                existing["tags"] = tags
                changed.append("tags")
            if args.flags is not None:
                existing["args"] = args.flags
                changed.append("args")
            msg = f"already saved as {existing.get('label')}"
            if changed:
                msg += "; updated " + "/".join(changed)
            print(msg, file=ctx.stdout)
            return 0
        labels = {str(f.get("label")) for f in favs}
        label = unique_label(label or default_label(session), labels)
        fav = new_favorite(session, label=label, note=args.note or "", tags=tags, args=args.flags or "", now=ctx.now())
        favs.append(fav)
    print(f"saved {label} ({session.agent} · {session.title})", file=ctx.stdout)
    return 0


def _missing(favs: list[dict]) -> set[tuple[str, str]]:
    adapters = get_adapters()
    out = set()
    for f in favs:
        a = adapters.get(str(f.get("agent")))
        if a is None or not a.exists(str(f.get("session_id"))):
            out.add((str(f.get("agent")), str(f.get("session_id"))))
    return out


def _color(ctx: Context) -> bool:
    return ctx.stdout_isatty and "NO_COLOR" not in os.environ


def cmd_ls(args: argparse.Namespace, ctx: Context) -> int:
    favs = load(favorites_path())["favorites"]
    rows = list(enumerate(ordered(favs), 1))
    if args.tag:
        rows = [(n, f) for n, f in rows if args.tag in (f.get("tags") or [])]
    if args.agent:
        rows = [(n, f) for n, f in rows if f.get("agent") == args.agent]
    if args.json:
        print(json.dumps([f for _, f in rows], indent=2, ensure_ascii=False), file=ctx.stdout)
        return 0
    if not favs:
        print("no favourites yet — try dogear add", file=ctx.stdout)
        return 0
    if not rows:
        print("no favourites match", file=ctx.stdout)
        return 0
    width = shutil.get_terminal_size((100, 24)).columns
    table = format_table(rows, _missing([f for _, f in rows]), width=width, color=_color(ctx), home=str(Path.home()))
    print(table, file=ctx.stdout)
    return 0


def cmd_rename(args: argparse.Namespace, ctx: Context) -> int:
    validate_label(args.new_label)
    with transaction(favorites_path()) as data:
        fav = resolve(data["favorites"], args.ref)
        if any(f is not fav and f.get("label") == args.new_label for f in data["favorites"]):
            raise DogearError(f"label '{args.new_label}' is already used")
        old, fav["label"] = fav.get("label"), args.new_label
    print(f"renamed {old} → {args.new_label}", file=ctx.stdout)
    return 0


def cmd_note(args: argparse.Namespace, ctx: Context) -> int:
    with transaction(favorites_path()) as data:
        fav = resolve(data["favorites"], args.ref)
        fav["note"] = args.text
    print(f"{'cleared note of' if not args.text else 'noted'} {fav.get('label')}", file=ctx.stdout)
    return 0


def cmd_tag(args: argparse.Namespace, ctx: Context) -> int:
    if not args.changes:
        raise DogearError("give tags to change, e.g. dogear tag REF +work -old")
    with transaction(favorites_path()) as data:
        fav = resolve(data["favorites"], args.ref)
        tags = list(fav.get("tags") or [])
        for change in args.changes:
            if change.startswith("-"):
                tags = [t for t in tags if t != change[1:].strip()]
            else:
                tags = _norm_tags(tags + [change[1:] if change.startswith("+") else change])
        fav["tags"] = tags
    print(f"{fav.get('label')}: {','.join(tags) or '(no tags)'}", file=ctx.stdout)
    return 0


def cmd_edit(args: argparse.Namespace, ctx: Context) -> int:
    with transaction(favorites_path()) as data:
        fav = resolve(data["favorites"], args.ref)
        fav["args"] = args.flags
    print(f"{fav.get('label')}: args = {args.flags!r}", file=ctx.stdout)
    return 0


def cmd_rm(args: argparse.Namespace, ctx: Context) -> int:
    with transaction(favorites_path()) as data:
        favs = data["favorites"]
        doomed = [resolve(favs, ref) for ref in args.refs]
        data["favorites"] = [f for f in favs if not any(f is d for d in doomed)]
    for d in dict((id(d), d) for d in doomed).values():
        print(f"removed {d.get('label')}", file=ctx.stdout)
    return 0


def cmd_prune(args: argparse.Namespace, ctx: Context) -> int:
    favs = load(favorites_path())["favorites"]
    missing = _missing(favs)
    gone = [f for f in favs if (str(f.get("agent")), str(f.get("session_id"))) in missing]
    if not gone:
        print("nothing to prune", file=ctx.stdout)
        return 0
    for f in gone:
        print(f"  {f.get('label')}  ({f.get('agent')} · {f.get('title')})", file=ctx.stdout)
    if not args.yes:
        if not ctx.stdin_isatty:
            raise DogearError("no TTY to confirm; rerun with --yes")
        print(f"remove {len(gone)} favourite(s)? [y/N] ", end="", file=ctx.stderr, flush=True)
        if ctx.stdin.readline().strip().lower() not in ("y", "yes"):
            print("kept them", file=ctx.stdout)
            return 0
    with transaction(favorites_path()) as data:
        keys = {(f.get("agent"), f.get("session_id")) for f in gone}
        data["favorites"] = [f for f in data["favorites"] if (f.get("agent"), f.get("session_id")) not in keys]
    print(f"removed {len(gone)} favourite(s)", file=ctx.stdout)
    return 0


def cmd_config(args: argparse.Namespace, ctx: Context) -> int:
    cfg = load_config()
    print(str(config_path()) if args.path else f"# {config_path()}", file=ctx.stdout)
    if not args.path:
        for agent in AGENTS:
            print(f"\n[{agent}]\ncommand = {json.dumps(cfg.commands[agent])}", file=ctx.stdout)
        print(f"\n[picker]\nuse_fzf = {json.dumps(cfg.use_fzf)}", file=ctx.stdout)
    return 0


def _open_fav(fav: dict, extra: list[str] | None, ctx: Context, cfg: Config) -> int:
    agent = str(fav.get("agent"))
    adapter = get_adapters().get(agent)
    if adapter is None:
        raise DogearError(f"{fav.get('label')}: unknown agent '{agent}'")
    sid = str(fav.get("session_id"))
    if not adapter.exists(sid):
        raise DogearError(f"{fav.get('label')}: the {agent} session {sid} no longer exists; remove it with dogear prune")
    cwd = str(fav.get("cwd") or "")
    if not cwd or not os.path.isdir(cwd):
        raise DogearError(f"{fav.get('label')}: folder {cwd or '(unknown)'} does not exist")
    cmd = build_command(cfg, fav, adapter, extra)
    exe = ctx.which(cmd[0]) if cmd else None
    if not exe:
        raise DogearError(
            f"command not found: {cmd[0] if cmd else '(empty)'}; set [{agent}] command in {config_path()}"
            " (shell aliases are not visible to dogear)"
        )
    print(display(cmd, cwd), file=ctx.stderr, flush=True)
    return ctx.exec_fn([exe, *cmd[1:]], cwd)


def cmd_open(args: argparse.Namespace, ctx: Context) -> int:
    cfg = load_config()
    fav = resolve(load(favorites_path())["favorites"], args.ref)
    return _open_fav(fav, args.extra, ctx, cfg)


def cmd_pick(args: argparse.Namespace, ctx: Context) -> int:
    cfg = load_config()
    favs = ordered(load(favorites_path())["favorites"])
    if not favs:
        print("no favourites yet — try dogear add", file=ctx.stdout)
        return 0
    rows = [f"{f.get('label')}  ·  {f.get('agent')}  ·  {f.get('title')}  ·  {_short_path(str(f.get('cwd', '')))}" for f in favs]
    previews = [f"{f.get('title')} / {f.get('cwd')} / {f.get('note') or ''}" for f in favs]
    i = pick(rows, ctx=ctx, use_fzf=cfg.use_fzf, prompt="open", previews=previews)
    if i is None:
        return 0
    return _open_fav(favs[i], None, ctx, cfg)


def cmd_setup(args: argparse.Namespace, ctx: Context) -> int:
    if args.agent == "claude":
        written = install_claude(args.force)
        usage = "type /dogear (or /dogear my-label -t work) in Claude Code to save the session"
    else:
        written = install_codex(args.force)
        usage = "type $dogear (or $dogear my-label -t work) in Codex to save the session"
    for path in written:
        print(f"wrote {path}", file=ctx.stdout)
    print(usage, file=ctx.stdout)
    if args.agent == "claude" and claude_plugin_installed():
        print(
            "dogear: note: the dogear Claude Code plugin is also installed (/dogear:dogear);"
            " you only need one of the two",
            file=ctx.stderr,
        )
    return 0


# parser ---------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="dogear",
        description="Favourite, list and resume Claude Code and Codex sessions.",
    )
    p.add_argument("--version", action="store_true", help="show the version and exit")
    sub = p.add_subparsers(dest="command", metavar="COMMAND")

    a = sub.add_parser("add", help="save a session as a favourite")
    a.add_argument("session", nargs="?", metavar="SESSION|LABEL", help="session id or prefix; any other word is a label for the current session")
    a.add_argument("-l", "--label")
    a.add_argument("-n", "--note")
    a.add_argument("-t", "--tag", dest="tags", action="extend", nargs="+", metavar="TAG")
    a.add_argument("--args", dest="flags", metavar="FLAGS", help='extra launch flags, e.g. --args "--model opus" or --args=--verbose')
    a.add_argument("--agent", choices=AGENTS)
    a.set_defaults(func=cmd_add)

    ls = sub.add_parser("ls", help="list favourites")
    ls.add_argument("-t", "--tag")
    ls.add_argument("--agent", choices=AGENTS)
    ls.add_argument("--json", action="store_true", help="print the raw favourites as JSON")
    ls.set_defaults(func=cmd_ls)

    r = sub.add_parser("rename", help="change a favourite's label")
    r.add_argument("ref", metavar="REF")
    r.add_argument("new_label", metavar="NEW_LABEL")
    r.set_defaults(func=cmd_rename)

    n = sub.add_parser("note", help='set a favourite\'s note ("" clears it)')
    n.add_argument("ref", metavar="REF")
    n.add_argument("text", metavar="TEXT")
    n.set_defaults(func=cmd_note)

    t = sub.add_parser("tag", help="add (+TAG) or remove (-TAG) tags")
    t.add_argument("ref", metavar="REF")
    t.add_argument("changes", nargs=argparse.REMAINDER, metavar="+TAG|-TAG")
    t.set_defaults(func=cmd_tag)

    e = sub.add_parser("edit", help="change a favourite's saved launch flags")
    e.add_argument("ref", metavar="REF")
    e.add_argument("--args", dest="flags", required=True, metavar="FLAGS")
    e.set_defaults(func=cmd_edit)

    rm = sub.add_parser("rm", help="remove favourites")
    rm.add_argument("refs", nargs="+", metavar="REF")
    rm.set_defaults(func=cmd_rm)

    pr = sub.add_parser("prune", help="remove favourites whose session no longer exists")
    pr.add_argument("--yes", action="store_true", help="don't ask")
    pr.set_defaults(func=cmd_prune)

    o = sub.add_parser("open", help="resume a favourite in its folder (flags after -- replace saved ones)")
    o.add_argument("ref", metavar="REF")
    o.set_defaults(func=cmd_open, extra=None)

    su = sub.add_parser("setup", help="install the /dogear command for an agent")
    su.add_argument("agent", choices=AGENTS)
    su.add_argument("--force", action="store_true", help="overwrite an existing file")
    su.set_defaults(func=cmd_setup)

    c = sub.add_parser("config", help="show the effective configuration")
    c.add_argument("--path", action="store_true", help="print only the config file path")
    c.set_defaults(func=cmd_config)
    return p


def main(argv: list[str] | None = None, ctx: Context | None = None) -> int:
    ctx = ctx or Context.from_env()
    argv = list(sys.argv[1:] if argv is None else argv)
    extra = None
    if argv[:1] == ["open"] and "--" in argv:
        i = argv.index("--")
        argv, extra = argv[:i], argv[i + 1 :]
    args = build_parser().parse_args(argv)
    if extra is not None:
        args.extra = extra
    try:
        if args.version:
            print(f"dogear {__version__}", file=ctx.stdout)
            return 0
        if args.command is None:
            return cmd_pick(args, ctx)
        return args.func(args, ctx)
    except DogearError as e:
        print(f"dogear: {e}", file=ctx.stderr)
        return 1
