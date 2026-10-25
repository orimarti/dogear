import pytest

from dogear.agents import find_sessions
from dogear.agents.codex import CodexAdapter
from tests.fakes import append_codex_index, make_claude_session, make_codex_rollout

A = "ab12cd34-0000-4000-8000-00000000000a"
B = "ab12ffff-0000-4000-8000-00000000000b"


@pytest.fixture
def adapter(homes):
    return CodexAdapter()


def test_title_from_index_last_wins(homes, adapter):
    make_codex_rollout(homes.codex, A, homes.root / "p")
    append_codex_index(homes.codex, A, "First name")
    append_codex_index(homes.codex, B, "Other")
    append_codex_index(homes.codex, A, "Renamed")
    s = adapter.get(A)
    assert s.title == "Renamed" and s.cwd == str(homes.root / "p") and s.agent == "codex"


def test_no_index_untitled(homes, adapter):
    make_codex_rollout(homes.codex, A, homes.root / "p")
    assert adapter.get(A).title == "(untitled)"


def test_garbage_index_line_skipped(homes, adapter):
    make_codex_rollout(homes.codex, A, homes.root / "p")
    append_codex_index(homes.codex, A, "Good")
    with (homes.codex / "session_index.jsonl").open("a") as f:
        f.write('{"id": "ab12cd34-0000-4000-8000-00000000000a", "thread_na')
    assert adapter.get(A).title == "Good"


def test_two_rollouts_same_id_newest(homes, adapter):
    old = make_codex_rollout(homes.codex, A, homes.root / "old", when="2026-01-01T00:00:00", mtime=1_000_000)
    new = make_codex_rollout(homes.codex, A, homes.root / "new", when="2026-01-05T00:00:00", mtime=2_000_000)
    assert adapter.get(A).path == new != old
    assert [s.session_id for s in adapter.recent(10)] == [A]


def test_find_and_exists(homes, adapter):
    make_codex_rollout(homes.codex, A, homes.root / "p")
    make_codex_rollout(homes.codex, B, homes.root / "q")
    assert [s.session_id for s in adapter.find("ab12cd")] == [A]
    assert {s.session_id for s in adapter.find("ab12")} == {A, B}
    assert adapter.exists(A)
    assert not adapter.exists("ffffffff-0000-4000-8000-000000000000")


def test_recent_order(homes, adapter):
    make_codex_rollout(homes.codex, A, homes.root / "p", mtime=1_000_000)
    make_codex_rollout(homes.codex, B, homes.root / "q", when="2026-02-02T00:00:00", mtime=2_000_000)
    assert [s.session_id for s in adapter.recent(10)] == [B, A]


def test_resume_args(adapter):
    assert adapter.resume_args(A) == ["resume", A]


@pytest.mark.parametrize("cmd,expected", [("codex", True), ("/opt/x/bin/codex", True), ("codex.exe", True), ("codex-helper", False), ("node", False)])
def test_is_agent_process(adapter, cmd, expected):
    assert adapter.is_agent_process(cmd) is expected


def test_find_sessions_across_agents(homes):
    make_codex_rollout(homes.codex, A, homes.root / "p")
    make_claude_session(homes.claude, "ab12cd34-1111-4000-8000-000000000001", homes.root / "c")
    found = find_sessions("ab12cd34")
    assert {s.agent for s in found} == {"claude", "codex"}
    assert [s.agent for s in find_sessions("ab12cd34", agent="codex")] == ["codex"]
