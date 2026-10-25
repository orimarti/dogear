import os
import sys

import pytest

from dogear import launch as launch_mod
from dogear.agents.claude import ClaudeAdapter
from dogear.agents.codex import CodexAdapter
from dogear.config import Config
from dogear.launch import build_command

ID = "8f1c2a3b-0000-4000-8000-000000000001"


def fav(agent="claude", args=""):
    return {"agent": agent, "session_id": ID, "args": args}


def test_claude_with_saved_args():
    assert build_command(Config(), fav(args="--model opus"), ClaudeAdapter(), None) == ["claude", "--model", "opus", "--resume", ID]


def test_codex_default():
    assert build_command(Config(), fav("codex"), CodexAdapter(), None) == ["codex", "resume", ID]


def test_config_base_command():
    cfg = Config(commands={"claude": "claude", "codex": "codex --full-auto"})
    assert build_command(cfg, fav("codex", "--x"), CodexAdapter(), None) == ["codex", "--full-auto", "--x", "resume", ID]


def test_extra_replaces_saved():
    assert build_command(Config(), fav(args="--model opus"), ClaudeAdapter(), ["--model", "x"]) == ["claude", "--model", "x", "--resume", ID]
    assert build_command(Config(), fav(args="--model opus"), ClaudeAdapter(), []) == ["claude", "--resume", ID]


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX exec path")
def test_launch_posix_execs_in_cwd(tmp_path, monkeypatch):
    seen = {}

    def fake_exec(file, argv):
        seen["file"], seen["argv"], seen["cwd"] = file, argv, os.getcwd()
        return 0

    monkeypatch.setattr(launch_mod.os, "execvp", fake_exec)
    before = os.getcwd()
    try:
        launch_mod.launch(["/bin/echo", "hi"], str(tmp_path))
    finally:
        os.chdir(before)
    assert seen["argv"] == ["/bin/echo", "hi"]
    assert os.path.realpath(seen["cwd"]) == os.path.realpath(tmp_path)
