"""Regression tests for findings from the final review."""

import io
import os
import signal
import sys
from pathlib import Path

import pytest

from dogear import launch as launch_mod
from dogear import proctree
from dogear.agents.claude import ClaudeAdapter
from dogear.cli import Context
from tests.fakes import make_claude_session


def test_from_env_survives_unencodable_output(monkeypatch):
    out = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
    err = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
    monkeypatch.setattr(sys, "stdout", out)
    monkeypatch.setattr(sys, "stderr", err)
    ctx = Context.from_env()
    print("renamed a → b · 日本", file=ctx.stdout)
    print("→", file=ctx.stderr)


def test_run_survives_undecodable_output():
    # bytes that are invalid in UTF-8 and in many code pages
    code = "import sys; sys.stdout.buffer.write(bytes([0x81, 0xff, 0x41]))"
    assert proctree._run([sys.executable, "-c", code]) is not None


def test_windows_launch_ignores_ctrl_c_while_agent_runs(monkeypatch, tmp_path):
    seen = {}

    class FakePopen:
        def __init__(self, cmd, cwd):
            seen["cmd"], seen["cwd"] = cmd, cwd
            self.returncode = 7

        def wait(self):
            seen["handler"] = signal.getsignal(signal.SIGINT)
            return self.returncode

    before = signal.getsignal(signal.SIGINT)
    monkeypatch.setattr(launch_mod, "WINDOWS", True)
    monkeypatch.setattr(launch_mod.subprocess, "Popen", FakePopen)
    assert launch_mod.launch(["codex", "resume", "x"], str(tmp_path)) == 7
    assert seen["handler"] == signal.SIG_IGN
    assert signal.getsignal(signal.SIGINT) == before


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX process table")
def test_real_open_files_and_cwd_non_ascii(tmp_path):
    d = tmp_path / "My Project" / "é"
    d.mkdir(parents=True)
    t = proctree.default_table()
    f = d / "rollout-é.jsonl"
    before = os.getcwd()
    os.chdir(d)
    try:
        with f.open("w"):
            files = [os.path.realpath(p) for p in t.open_files(os.getpid())]
            assert os.path.realpath(f) in files
        assert os.path.realpath(t.cwd(os.getpid())) == os.path.realpath(d)
    finally:
        os.chdir(before)


@pytest.mark.parametrize(
    "argv,expected",
    [
        (["node", "/usr/lib/node_modules/@anthropic-ai/claude-code/cli.js", "--resume"], "/usr/lib/node_modules/@anthropic-ai/claude-code/cli.js"),
        (["claude"], "claude"),
        (["/usr/bin/node", "--max-old-space-size=4096", "/x/cli.js"], "/x/cli.js"),
        (["/bin/zsh", "-l"], "/bin/zsh"),
        ([], ""),
    ],
)
def test_effective_command(argv, expected):
    assert proctree.effective_command(argv) == expected


def test_npm_claude_is_agent_process():
    a = ClaudeAdapter()
    assert a.is_agent_process("/usr/lib/node_modules/@anthropic-ai/claude-code/cli.js")
    assert a.is_agent_process("C:\\npm\\node_modules\\@anthropic-ai\\claude-code\\cli.js")


def test_recent_survives_file_deleted_mid_listing(homes, monkeypatch):
    sid = "8f1c2a3b-0000-4000-8000-000000000001"
    p = make_claude_session(homes.claude, sid, homes.root / "p")
    a = ClaudeAdapter()
    real = a._transcripts

    def vanish(prefix=""):
        found = real(prefix)
        p.unlink()
        return found

    monkeypatch.setattr(a, "_transcripts", vanish)
    a.recent(10)  # must not raise


@pytest.mark.parametrize("agent", ["claude", "codex"])
def test_store_root_with_glob_metacharacters(homes, monkeypatch, agent):
    from dogear.agents import get_adapters
    from tests.fakes import make_codex_rollout

    sid = "8f1c2a3b-0000-4000-8000-000000000001"
    root = homes.root / "user[work]" / f".{agent}"
    if agent == "claude":
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(root))
        make_claude_session(root, sid, homes.root / "p")
    else:
        monkeypatch.setenv("CODEX_HOME", str(root))
        make_codex_rollout(root, sid, homes.root / "p")
    a = get_adapters()[agent]
    assert a.exists(sid)
    assert [s.session_id for s in a.find("8f1c")] == [sid]
    assert [s.session_id for s in a.recent(5)] == [sid]
