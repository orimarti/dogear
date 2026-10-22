"""Where dogear and the agents keep their files."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def dogear_home() -> Path:
    if env := os.environ.get("DOGEAR_HOME"):
        return Path(env)
    if sys.platform == "win32":
        base = os.environ.get("APPDATA")
        return Path(base) / "dogear" if base else Path.home() / "AppData" / "Roaming" / "dogear"
    if xdg := os.environ.get("XDG_CONFIG_HOME"):
        return Path(xdg) / "dogear"
    return Path.home() / ".config" / "dogear"


def favorites_path() -> Path:
    return dogear_home() / "favorites.json"


def config_path() -> Path:
    return dogear_home() / "config.toml"


def claude_home() -> Path:
    env = os.environ.get("CLAUDE_CONFIG_DIR")
    return Path(env) if env else Path.home() / ".claude"


def codex_home() -> Path:
    env = os.environ.get("CODEX_HOME")
    return Path(env) if env else Path.home() / ".codex"
