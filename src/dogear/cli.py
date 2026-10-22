"""Command-line entry point."""

from __future__ import annotations

import argparse
import io
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, TextIO

from dogear import __version__
from dogear.errors import DogearError


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


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="dogear",
        description="Favourite, list and resume Claude Code and Codex sessions.",
    )
    p.add_argument("--version", action="store_true", help="show the version and exit")
    return p


def main(argv: list[str] | None = None, ctx: Context | None = None) -> int:
    ctx = ctx or Context.from_env()
    argv = sys.argv[1:] if argv is None else argv
    args = build_parser().parse_args(argv)
    try:
        if args.version:
            print(f"dogear {__version__}", file=ctx.stdout)
            return 0
        return 0
    except DogearError as e:
        print(f"dogear: {e}", file=ctx.stderr)
        return 1
