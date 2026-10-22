import os
from dataclasses import dataclass
from pathlib import Path

import pytest


@dataclass
class Homes:
    root: Path
    home: Path
    dogear: Path
    claude: Path
    codex: Path


@pytest.fixture(autouse=True)
def homes(tmp_path, monkeypatch):
    """Point every store dogear knows about at a temp dir, for every test."""
    h = Homes(
        root=tmp_path,
        home=tmp_path / "home",
        dogear=tmp_path / "dogear",
        claude=tmp_path / "claude",
        codex=tmp_path / "codex",
    )
    h.home.mkdir()
    monkeypatch.setenv("HOME", str(h.home))
    monkeypatch.setenv("USERPROFILE", str(h.home))
    monkeypatch.setenv("APPDATA", str(h.home / "AppData"))
    monkeypatch.setenv("DOGEAR_HOME", str(h.dogear))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(h.claude))
    monkeypatch.setenv("CODEX_HOME", str(h.codex))
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    return h
