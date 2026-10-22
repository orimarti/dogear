"""`dogear setup`: the only code that writes into the agents' folders, and only when asked."""

from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path

from dogear.errors import DogearError
from dogear.paths import claude_home, codex_home


def _asset(name: str) -> bytes:
    return (files("dogear") / "assets" / name).read_bytes()


def _install(targets: list[tuple[Path, str]], force: bool) -> list[Path]:
    if not force:
        for path, _ in targets:
            if path.exists():
                raise DogearError(f"{path} already exists; rerun with --force to overwrite it")
    for path, name in targets:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(_asset(name))
    return [p for p, _ in targets]


def install_claude(force: bool) -> list[Path]:
    return _install([(claude_home() / "skills" / "dogear" / "SKILL.md", "claude_skill.md")], force)


def install_codex(force: bool) -> list[Path]:
    skill = codex_home() / "skills" / "dogear"
    return _install(
        [(skill / "SKILL.md", "codex_skill.md"), (skill / "agents" / "openai.yaml", "codex_openai.yaml")],
        force,
    )


def claude_plugin_installed() -> bool:
    """Read-only check of Claude Code's plugin registry for the dogear plugin."""
    try:
        data = json.loads((claude_home() / "plugins" / "installed_plugins.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return False
    plugins = data.get("plugins") if isinstance(data, dict) else None
    return isinstance(plugins, dict) and any(str(k).startswith("dogear@") for k in plugins)
