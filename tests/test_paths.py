import sys
from pathlib import Path

import pytest

from dogear import paths


def test_dogear_home_env_wins(homes):
    assert paths.dogear_home() == homes.dogear
    assert paths.favorites_path() == homes.dogear / "favorites.json"
    assert paths.config_path() == homes.dogear / "config.toml"


@pytest.mark.skipif(sys.platform == "win32", reason="XDG is POSIX only")
def test_xdg_config_home(monkeypatch, tmp_path):
    monkeypatch.delenv("DOGEAR_HOME")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "x"))
    assert paths.dogear_home() == tmp_path / "x" / "dogear"


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX default")
def test_posix_default(monkeypatch, homes):
    monkeypatch.delenv("DOGEAR_HOME")
    assert paths.dogear_home() == homes.home / ".config" / "dogear"


def test_agent_homes(homes, monkeypatch):
    assert paths.claude_home() == homes.claude
    assert paths.codex_home() == homes.codex
    monkeypatch.delenv("CODEX_HOME")
    monkeypatch.delenv("CLAUDE_CONFIG_DIR")
    assert paths.codex_home() == Path.home() / ".codex"
    assert paths.claude_home() == Path.home() / ".claude"
