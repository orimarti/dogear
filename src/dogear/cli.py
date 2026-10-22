"""Command-line entry point."""

from __future__ import annotations

import argparse
import io
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
from dogear.favorites import default_label, find_by_session, new_favorite, unique_label, validate_label
from dogear.paths import favorites_path
from dogear.picker import pick
from dogear.proctree import default_table
from dogear.store import transaction


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
    return p


def main(argv: list[str] | None = None, ctx: Context | None = None) -> int:
    ctx = ctx or Context.from_env()
    argv = sys.argv[1:] if argv is None else argv
    args = build_parser().parse_args(argv)
    try:
        if args.version:
            print(f"dogear {__version__}", file=ctx.stdout)
            return 0
        if args.command is None:
            return 0
        return args.func(args, ctx)
    except DogearError as e:
        print(f"dogear: {e}", file=ctx.stderr)
        return 1
