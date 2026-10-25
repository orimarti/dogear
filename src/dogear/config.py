"""Optional user configuration (config.toml)."""

from __future__ import annotations

import os
import shlex
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from dogear.errors import DogearError
from dogear.paths import config_path

AGENTS = ("claude", "codex")
FZF_MODES = ("auto", "always", "never")


@dataclass
class Config:
    commands: dict[str, str] = field(default_factory=lambda: {a: a for a in AGENTS})
    use_fzf: str = "auto"
    path: Path | None = None


def load_config(path: Path | None = None) -> Config:
    path = path or config_path()
    cfg = Config(path=path)
    if not path.exists():
        return cfg
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as e:
        raise DogearError(f"cannot read {path}: {e}") from None
    for agent in AGENTS:
        section = raw.get(agent, {})
        if "command" in section:
            cmd = section["command"]
            if not isinstance(cmd, str) or not cmd.strip():
                raise DogearError(f"{path}: [{agent}] command must be a non-empty string")
            cfg.commands[agent] = cmd
    use_fzf = raw.get("picker", {}).get("use_fzf", "auto")
    if use_fzf not in FZF_MODES:
        raise DogearError(f"{path}: [picker] use_fzf must be one of {', '.join(FZF_MODES)}")
    cfg.use_fzf = use_fzf
    return cfg


def split_command(s: str) -> list[str]:
    """Split a command line into argv (POSIX rules; Windows keeps backslashes)."""
    posix = os.name != "nt"
    parts = shlex.split(s, posix=posix)
    if not posix:
        parts = [p[1:-1] if len(p) >= 2 and p[0] == p[-1] == '"' else p for p in parts]
    return parts
