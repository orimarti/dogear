import pytest

from dogear.agents.claude import ClaudeAdapter
from tests.fakes import make_claude_session

A = "8f1c2a3b-0000-4000-8000-000000000001"
B = "8f1c9999-0000-4000-8000-000000000002"


@pytest.fixture
def adapter(homes):
    return ClaudeAdapter()


def test_custom_title_beats_ai_title(homes, adapter):
    make_claude_session(homes.claude, A, homes.root / "p", ai_title=["First", "Second"], custom_title="Mine")
    assert adapter.get(A).title == "Mine"


def test_last_ai_title_wins(homes, adapter):
    make_claude_session(homes.claude, A, homes.root / "p", ai_title=["First", "Second"])
    assert adapter.get(A).title == "Second"


def test_first_prompt_fallback_string(homes, adapter):
    make_claude_session(homes.claude, A, homes.root / "p", first_prompt="  Fix   the\nlogin bug " + "x" * 80)
    t = adapter.get(A).title
    assert t.startswith("Fix the login bug x") and len(t) == 60 and t.endswith("…")


def test_first_prompt_fallback_blocks(homes, adapter):
    make_claude_session(
        homes.claude, A, homes.root / "p", first_prompt=[{"type": "image"}, {"type": "text", "text": "Example session"}]
    )
    assert adapter.get(A).title == "Example session"


def test_untitled(homes, adapter):
    make_claude_session(homes.claude, A, homes.root / "p", first_prompt=None)
    assert adapter.get(A).title == "(untitled)"


def test_cwd_from_transcript_not_slug(homes, adapter):
    cwd = homes.root / "My Project" / "é.x"
    make_claude_session(homes.claude, A, cwd)
    s = adapter.get(A)
    assert s.cwd == str(cwd) and s.agent == "claude" and s.session_id == A


def test_find_prefix(homes, adapter):
    make_claude_session(homes.claude, A, homes.root / "p")
    make_claude_session(homes.claude, B, homes.root / "q")
    assert [s.session_id for s in adapter.find("8f1c2a")] == [A]
    assert {s.session_id for s in adapter.find("8f1c")} == {A, B}
    assert adapter.find("ffff") == []


def test_exists(homes, adapter):
    make_claude_session(homes.claude, A, homes.root / "p")
    assert adapter.exists(A)
    assert not adapter.exists(B)
    assert adapter.get(B) is None


def test_recent_newest_first(homes, adapter):
    make_claude_session(homes.claude, A, homes.root / "p", mtime=1_000_000)
    make_claude_session(homes.claude, B, homes.root / "q", mtime=2_000_000)
    assert [s.session_id for s in adapter.recent(1)] == [B]
    assert [s.session_id for s in adapter.recent(10)] == [B, A]


def test_truncated_last_line_ignored(homes, adapter):
    make_claude_session(homes.claude, A, homes.root / "p", ai_title="Good", extra_lines=('{"type":"ai-ti',))
    assert adapter.get(A).title == "Good"


def test_duplicate_transcripts_use_newest(homes, adapter):
    make_claude_session(homes.claude, A, homes.root / "old", mtime=1_000_000)
    make_claude_session(homes.claude, A, homes.root / "new", mtime=2_000_000)
    assert adapter.get(A).cwd == str(homes.root / "new")
    assert len(adapter.recent(10)) == 1


def test_missing_store(adapter):
    assert adapter.recent(5) == [] and adapter.find("8f1c") == []


def test_resume_args(adapter):
    assert adapter.resume_args(A) == ["--resume", A]


@pytest.mark.parametrize(
    "cmd,expected",
    [
        ("claude", True),
        ("/x/.local/share/claude/versions/2.1.0", True),
        ("C:\\x\\claude.exe", True),
        ("/usr/local/bin/claude", True),
        ("claude-helper", False),
        ("node", False),
        ("-zsh", False),
    ],
)
def test_is_agent_process(adapter, cmd, expected):
    assert adapter.is_agent_process(cmd) is expected
