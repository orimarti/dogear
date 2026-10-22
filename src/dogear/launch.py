"""Build the resume command and hand the terminal over to the agent."""

from __future__ import annotations

import os
import shlex
import subprocess
import sys

from dogear.config import Config, split_command


def build_command(config: Config, fav: dict, adapter, extra: list[str] | None) -> list[str]:
    flags = extra if extra is not None else split_command(str(fav.get("args") or ""))
    return split_command(config.commands[adapter.name]) + flags + adapter.resume_args(str(fav["session_id"]))


def display(cmd: list[str], cwd: str) -> str:
    if os.name == "nt":
        return f'cd /d "{cwd}" && {subprocess.list2cmdline(cmd)}'
    return f"cd {shlex.quote(cwd)} && {shlex.join(cmd)}"


def launch(cmd: list[str], cwd: str) -> int:
    """Replace dogear with the agent (POSIX); run it as a child on Windows."""
    sys.stdout.flush()
    sys.stderr.flush()
    if os.name == "nt":
        return subprocess.run(cmd, cwd=cwd).returncode
    os.chdir(cwd)
    os.execvp(cmd[0], cmd)
    return 0  # only reached when execvp is replaced in tests
