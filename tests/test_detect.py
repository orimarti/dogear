import time

import pytest

from dogear.agents import get_adapters
from dogear.detect import DetectionError, detect_current
from tests.fakes import FakeProcessTable, make_claude_session, make_codex_rollout, write_claude_live

C = "c1a0de00-0000-4000-8000-000000000001"
X = "c0de0000-0000-4000-8000-000000000001"
Y = "c0de0000-0000-4000-8000-000000000002"


def chain(top_cmd, **extra):
    return FakeProcessTable(
        {300: {"ppid": 200, "cmd": "dogear"}, 200: {"ppid": 100, "cmd": "/bin/zsh"}, 100: {"ppid": 1, "cmd": top_cmd, **extra}}
    )


def test_claude_live_session(homes):
    make_claude_session(homes.claude, C, homes.root / "p", ai_title="Example session")
    write_claude_live(homes.claude, 100, C, homes.root / "p")
    write_claude_live(homes.claude, 999, "deadbeef-0000-4000-8000-000000000000", homes.root / "q")
    s = detect_current(get_adapters(), chain("claude"), pid=300)
    assert s.session_id == C and s.title == "Example session"


def test_claude_live_without_transcript_yet(homes):
    write_claude_live(homes.claude, 100, C, homes.root / "p", name="fresh")
    s = detect_current(get_adapters(), chain("/u/.local/share/claude/versions/2.1.0"), pid=300)
    assert s.session_id == C and s.cwd == str(homes.root / "p") and s.title == "fresh"


def test_claude_without_sessions_file_refuses(homes):
    with pytest.raises(DetectionError) as e:
        detect_current(get_adapters(), chain("claude"), pid=300)
    assert e.value.candidates == []
    assert "dogear add <session-id>" in str(e.value)


def test_claude_sessions_file_pid_mismatch_ignored(homes):
    p = write_claude_live(homes.claude, 100, C, homes.root / "p")
    p.write_text(p.read_text().replace('"pid": 100', '"pid": 101'))
    with pytest.raises(DetectionError):
        detect_current(get_adapters(), chain("claude"), pid=300)


def test_codex_open_rollout(homes):
    r = make_codex_rollout(homes.codex, X, homes.root / "p")
    make_codex_rollout(homes.codex, Y, homes.root / "p", when="2026-01-03T00:00:00")
    s = detect_current(get_adapters(), chain("codex", files=["/dev/null", str(r)]), pid=300)
    assert s.session_id == X and s.agent == "codex"


def test_codex_two_candidates_refuses(homes):
    now = time.time()
    cwd = homes.root / "p"
    make_codex_rollout(homes.codex, X, cwd, mtime=now)
    make_codex_rollout(homes.codex, Y, cwd, when="2026-01-03T00:00:00", mtime=now)
    with pytest.raises(DetectionError) as e:
        detect_current(get_adapters(), chain("codex", cwd=str(cwd), start=now - 60), pid=300)
    assert {c.session_id for c in e.value.candidates} == {X, Y}
    assert X in str(e.value) and Y in str(e.value)


def test_codex_single_recent_candidate(homes):
    now = time.time()
    cwd = homes.root / "p"
    make_codex_rollout(homes.codex, X, cwd, mtime=now)
    make_codex_rollout(homes.codex, Y, cwd, when="2026-01-03T00:00:00", mtime=now - 7200)
    make_codex_rollout(homes.codex, "c0de0000-0000-4000-8000-000000000003", homes.root / "other", when="2026-01-04T00:00:00", mtime=now)
    s = detect_current(get_adapters(), chain("codex", cwd=str(cwd), start=now - 60), pid=300)
    assert s.session_id == X


def test_no_agent_ancestor(homes):
    assert detect_current(get_adapters(), chain("/bin/bash"), pid=300) is None


def test_nearest_agent_wins(homes):
    r = make_codex_rollout(homes.codex, X, homes.root / "p")
    write_claude_live(homes.claude, 50, C, homes.root / "p")
    t = FakeProcessTable(
        {300: {"ppid": 200, "cmd": "dogear"}, 200: {"ppid": 100, "cmd": "sh"}, 100: {"ppid": 50, "cmd": "codex", "files": [str(r)]}, 50: {"ppid": 1, "cmd": "claude"}}
    )
    assert detect_current(get_adapters(), t, pid=300).agent == "codex"
